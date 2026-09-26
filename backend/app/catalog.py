from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.integrations.off import normalize_off, normalize_off_category
from app.models import Product
from app.schemas import FoodObservation


def store_product(session: Session, food: FoodObservation, source_id: str, raw: dict):
    match = (Product.source_kind == food.source.kind) & (Product.source_id == source_id)
    if food.barcode:
        match = or_(match, Product.barcode == food.barcode)
    product = session.scalar(select(Product).where(match))
    if product is None:
        product = Product()
        session.add(product)
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
