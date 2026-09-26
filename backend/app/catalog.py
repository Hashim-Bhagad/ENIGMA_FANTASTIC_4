import logging

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.integrations.off import normalize_off, normalize_off_category
from app.models import Product
from app.schemas import FoodObservation

logger = logging.getLogger(__name__)

# Source kinds that both describe the same upstream Open Food Facts catalog and
# may refresh each other.
OFF_KINDS = {"openfoodfacts", "apify_off"}


def _may_update(existing_kind: str, incoming_kind: str) -> bool:
    if existing_kind == incoming_kind:
        return True
    return existing_kind in OFF_KINDS and incoming_kind in OFF_KINDS


def store_product(session: Session, food: FoodObservation, source_id: str, raw: dict):
    """Upsert an observation into the shared catalog without silent re-sourcing.

    A stored record is only updated when the incoming source kind matches it, or
    when both are Open Food Facts variants. A barcode that collides with a
    record of a different kind is reported as a WARNING and the existing row is
    returned unchanged (with the warning attached to its in-memory observation).
    """
    match = (Product.source_kind == food.source.kind) & (Product.source_id == source_id)
    if food.barcode:
        match = or_(match, Product.barcode == food.barcode)
    product = session.scalar(select(Product).where(match))
    if product is None:
        product = Product()
        session.add(product)
    elif not _may_update(product.source_kind, food.source.kind):
        warning = (
            f"Barcode {food.barcode} already belongs to a {product.source_kind} record; "
            f"the incoming {food.source.kind} record was not saved to avoid silently "
            "re-sourcing it."
        )
        logger.warning("catalog collision: %s", warning)
        # Attach the warning to the in-memory observation only. The nested mutation
        # is not tracked by SQLAlchemy, so the stored row is left unchanged.
        observation = product.observation or {}
        observation.setdefault("source", {}).setdefault("warnings", []).append(warning)
        return product
    product.name, product.barcode, product.category = food.name, food.barcode, food.category
    product.source_kind, product.source_id = food.source.kind, source_id
    product.observation, product.raw = food.model_dump(mode="json"), raw
    session.flush()
    return product


def store_off(session: Session, raw: dict):
    code = str(raw.get("code", ""))
    if not code:
        raise ValueError("OFF record has no product code")
    existing = session.scalar(select(Product).where(Product.barcode == code))
    # A user-reviewed label is higher-trust than the community catalog. Keep it
    # intact when a later barcode lookup happens to find the same code in OFF.
    if existing and existing.source_kind in {"manual", "label_extraction"}:
        return existing

    category = None
    if existing and existing.category:
        prior_tags = existing.raw.get("categories_tags") if isinstance(existing.raw, dict) else None
        prior_inferred, _ = normalize_off_category(prior_tags)
        # Categories that matched the prior OFF tags were inferred and should
        # refresh with the upstream record. A different saved category is a
        # local curation override and remains in force.
        if existing.category != prior_inferred:
            category = existing.category
    return store_product(session, normalize_off(raw, category), code, raw)


def product_response(product: Product):
    return {
        "id": product.id,
        "food": product.observation,
        "updated_at": product.updated_at.isoformat(),
    }
