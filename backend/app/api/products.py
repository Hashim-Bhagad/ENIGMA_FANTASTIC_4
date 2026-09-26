import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.catalog import product_response, store_off
from app.db import get_session
from app.integrations.off import ProviderError
from app.models import Product, ReferenceFood
from app.rate_limit import rate_limit
from app.security import current_user
from app.services.provenance import product_provenance

logger = logging.getLogger(__name__)

# Every product route is authenticated (see the router dependency) because reads
# can write provider records into the shared catalog.
router = APIRouter(
    prefix="/api", tags=["product acquisition"], dependencies=[Depends(current_user)]
)


def search_pattern(query: str) -> str:
    # Treat user-entered %, _ and backslashes as literal characters in SQL LIKE.
    return "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def saved_search(session: Session, query: str, limit: int):
    text = search_pattern(query)
    return list(
        session.scalars(
            select(Product)
            .where(
                or_(
                    Product.name.ilike(text, escape="\\"),
                    Product.raw["brands"].as_string().ilike(text, escape="\\"),
                )
            )
            .order_by(Product.name, Product.id)
            .limit(limit)
        )
    )


@router.get("/products")
def search_saved(
    q: str = Query(default="", max_length=100),
    category: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    """List saved catalog products with a stable order and total count.

    Requires a bearer token; unauthenticated calls are rejected before any query.
    """
    filters = []
    if q:
        text = search_pattern(q)
        filters.append(
            or_(
                Product.name.ilike(text, escape="\\"),
                Product.raw["brands"].as_string().ilike(text, escape="\\"),
            )
        )
    if category:
        filters.append(Product.category == category)
    total = session.scalar(select(func.count()).select_from(Product).where(*filters)) or 0
    rows = session.scalars(
        select(Product)
        .where(*filters)
        .order_by(Product.name, Product.id)
        .offset(offset)
        .limit(limit)
    )
    return {
        "products": [product_response(x) for x in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/products/barcode/{barcode}",
    dependencies=[Depends(rate_limit("provider_reads", 30, 60, "user"))],
)
async def lookup(
    barcode: str,
    request: Request,
    response: Response,
    refresh: bool = False,
    session: Session = Depends(get_session),
):
    """Look up one barcode, optionally refreshing from Open Food Facts.

    Requires a bearer token: a refresh may write the provider record into the
    shared catalog, so anonymous callers can no longer trigger catalog writes.
    """
    response.headers["Cache-Control"] = "no-store"
    if not re.fullmatch(r"[0-9]{8}|[0-9]{12,14}", barcode):
        raise HTTPException(422, "Enter an 8, 12, 13, or 14 digit barcode")
    existing = session.scalar(select(Product).where(Product.barcode == barcode))
    if existing and not refresh:
        return {**product_response(existing), "lookup_source": "saved_snapshot"}
    # Release the read transaction before waiting for the provider.
    session.rollback()
    try:
        raw = await request.app.state.off.product(barcode)
    except ProviderError as exc:
        raise HTTPException(503, str(exc)) from exc
    if raw is None:
        raise HTTPException(
            404, "Product not found; capture its label or enter the declaration manually"
        )
    try:
        product = store_off(session, raw)
        session.commit()
    except IntegrityError:
        session.rollback()
        product = session.scalar(select(Product).where(Product.barcode == barcode))
        if product is None:
            raise HTTPException(409, "Catalog changed; retry lookup") from None
    return {
        **product_response(product),
        "lookup_source": "openfoodfacts"
        if product.source_kind == "openfoodfacts"
        else "reviewed_snapshot",
    }


@router.get(
    "/products/search/live",
    dependencies=[Depends(rate_limit("provider_reads", 30, 60, "user"))],
)
async def search_live(
    request: Request,
    response: Response,
    q: str = Query(min_length=2, max_length=100),
    session: Session = Depends(get_session),
):
    """Search Open Food Facts and cache the results in the shared catalog.

    Requires a bearer token. One conflicting record is skipped and counted
    instead of discarding the whole batch.
    """
    response.headers["Cache-Control"] = "no-store"
    q = q.strip()
    if len(q) < 2:
        raise HTTPException(422, "Enter at least two characters")
    try:
        records = await request.app.state.off.search(q)
    except ProviderError as exc:
        raise HTTPException(503, str(exc)) from exc
    products, skipped = [], 0
    for record in records:
        try:
            with session.begin_nested():
                products.append(store_off(session, record))
        except (ValueError, IntegrityError) as exc:
            skipped += 1
            logger.warning("skipped live search record: %s", type(exc).__name__)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, "Catalog changed; retry search") from exc
    return {
        "products": [product_response(x) for x in products],
        "skipped_records": skipped,
        "source": "openfoodfacts",
        "message": "Results are source records requiring label confirmation.",
    }


@router.get(
    "/products/search",
    dependencies=[Depends(rate_limit("provider_reads", 30, 60, "user"))],
)
async def search_products(
    request: Request,
    response: Response,
    q: str = Query(min_length=2, max_length=100),
    include_live: bool = False,
    session: Session = Depends(get_session),
):
    """Unified search over saved products and, optionally, Open Food Facts.

    Requires a bearer token; ``include_live=true`` can write provider records.
    """
    response.headers["Cache-Control"] = "no-store"
    q = q.strip()
    if len(q) < 2:
        raise HTTPException(422, "Enter at least two characters")
    if re.fullmatch(r"[0-9]{8}|[0-9]{12,14}", q):
        found = await lookup(q, request, response, False, session)
        return {
            "products": [{key: found[key] for key in ("id", "food", "updated_at")}],
            "query_type": "barcode",
            "lookup_source": found["lookup_source"],
        }
    products = [product_response(x) for x in saved_search(session, q, 20)]
    if not include_live:
        return {"products": products, "query_type": "product_name", "live_requested": False}
    session.rollback()
    try:
        live = await search_live(request, response, q, session)
    except HTTPException as exc:
        if exc.status_code != 503:
            raise
        return {
            "products": products,
            "query_type": "product_name",
            "live_requested": True,
            "live_status": "unavailable",
            "message": exc.detail,
        }
    merged = {x["id"]: x for x in products + live["products"]}
    return {
        "products": list(merged.values()),
        "query_type": "product_name",
        "live_requested": True,
        "live_status": "completed",
        "skipped_records": live["skipped_records"],
    }


@router.get("/products/{product_id}")
def get_product(product_id: str, session: Session = Depends(get_session)):
    """Return one saved catalog product. Requires a bearer token."""
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(404, "Product not found")
    return product_response(product)


@router.get("/products/{product_id}/provenance")
def get_product_provenance(product_id: str, session: Session = Depends(get_session)):
    """Return the saved source trace for one product. Requires a bearer token."""
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(404, "Product source snapshot not found")
    return product_provenance(product)


@router.get("/reference-foods")
def reference_foods(
    q: str = Query(min_length=1, max_length=100),
    limit: int = Query(default=10, ge=1, le=30),
    session: Session = Depends(get_session),
):
    """Search ingredient-composition reference foods. Requires a bearer token."""
    text = search_pattern(q)
    rows = session.scalars(
        select(ReferenceFood)
        .where(or_(ReferenceFood.code == q, ReferenceFood.name.ilike(text, escape="\\")))
        .limit(limit)
    )
    return {
        "foods": [
            {"code": r.code, "name": r.name, "data": r.data, "source": r.source} for r in rows
        ],
        "usage": "Ingredient composition reference; not a packaged-product label or prepared-dish measurement.",
    }
