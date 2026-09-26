import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.catalog import product_response, store_off
from app.db import get_session
from app.integrations.off import ProviderError
from app.models import Product, ReferenceFood
from app.services.provenance import product_provenance

router = APIRouter(prefix="/api", tags=["product acquisition"])


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
            .order_by(Product.name)
            .limit(limit)
        )
    )


@router.get("/products")
def search_saved(
    q: str = Query(default="", max_length=100),
    category: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=20, ge=1, le=50),
    session: Session = Depends(get_session),
):
    statement = select(Product)
    if q:
        text = search_pattern(q)
        statement = statement.where(
            or_(
                Product.name.ilike(text, escape="\\"),
                Product.raw["brands"].as_string().ilike(text, escape="\\"),
            )
        )
    if category:
        statement = statement.where(Product.category == category)
    return {
        "products": [
            product_response(x)
            for x in session.scalars(statement.order_by(Product.name).limit(limit))
        ]
    }


@router.get("/products/barcode/{barcode}")
async def lookup(
    barcode: str, request: Request, refresh: bool = False, session: Session = Depends(get_session)
):
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


@router.get("/products/search/live")
async def search_live(
    request: Request,
    q: str = Query(min_length=2, max_length=100),
    session: Session = Depends(get_session),
):
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
            products.append(store_off(session, record))
        except ValueError:
            skipped += 1
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


@router.get("/products/search")
async def search_products(
    request: Request,
    q: str = Query(min_length=2, max_length=100),
    include_live: bool = False,
    session: Session = Depends(get_session),
):
    q = q.strip()
    if len(q) < 2:
        raise HTTPException(422, "Enter at least two characters")
    if re.fullmatch(r"[0-9]{8}|[0-9]{12,14}", q):
        found = await lookup(q, request, False, session)
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
        live = await search_live(request, q, session)
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
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(404, "Product not found")
    return product_response(product)


@router.get("/products/{product_id}/provenance")
def get_product_provenance(product_id: str, session: Session = Depends(get_session)):
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
