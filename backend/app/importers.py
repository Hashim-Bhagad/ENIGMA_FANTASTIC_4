import argparse
import asyncio
import csv
import hashlib
import io
import json
import logging
import math
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.catalog import store_product
from app.config import get_settings
from app.db import make_engine
from app.integrations.apify import ApifyReader
from app.integrations.off import normalize_apify_off
from app.models import RecipeRecord, ReferenceFood
from app.schemas import FoodObservation

logger = logging.getLogger(__name__)

IFCT_BASE = "https://raw.githubusercontent.com/nodef/ifct2017/main/"
IFCT_COLUMNS = {
    "na": ("sodium_mg", "mg"),
    "k": ("potassium_mg", "mg"),
    "p": ("phosphorus_mg", "mg"),
    "protcnt": ("protein_g", "g"),
    "fatce": ("fat_g", "g"),
    "fibtg": ("fiber_g", "g"),
    # Available carbohydrate/free sugars are not silently equated to label total carbohydrate/sugars.
    "choavldf": ("available_carbohydrates_g", "g"),
    "fsugar": ("free_sugars_g", "g"),
    "enerc": ("energy_kcal", "kJ"),
}


def normalize_ifct(row: dict, units: dict) -> dict:
    nutrients, warnings = {}, []
    for column, (target, unit) in IFCT_COLUMNS.items():
        metadata = units.get(column)
        if metadata is None:
            warnings.append(f"No unit metadata for {column}; retained as unknown")
            nutrients[target] = None
            continue
        if metadata["unit"] != unit:
            raise ValueError(f"Unexpected IFCT unit for {column}; update and review the mapping")
        try:
            amount = float(row.get(column, "")) * float(metadata["factor"])
            if target == "energy_kcal":
                amount /= 4.184
            if not math.isfinite(amount) or amount < 0:
                amount = None
        except (ValueError, TypeError):
            amount = None
        nutrients[target] = round(amount, 6) if amount is not None else None
    return {
        "code": row["code"],
        "name": row["name"],
        "basis": "100g_edible_portion",
        "nutrients": nutrients,
        "local_names": row.get("lang"),
        "scientific_name": row.get("scie"),
        "group": row.get("grup"),
        "warnings": warnings,
        "usage": "Reference composition, not a branded-product measurement; preparation/quantity must be separately known.",
    }


def read_csv(path: Path):
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig"))))


async def download_ifct(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "compositions.csv": "compositions/index.csv",
        "representations.csv": "representations/index.csv",
        "LICENSE": "LICENSE",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        for name, remote in paths.items():
            response = await client.get(IFCT_BASE + remote)
            response.raise_for_status()
            (directory / name).write_bytes(response.content)
    manifest = {
        "source": "https://github.com/nodef/ifct2017",
        "retrieved_at": datetime.now(UTC).isoformat(),
        "files": {
            name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in paths
        },
        "license": "AGPL-3.0-or-later per repository; source-book rights are separate",
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2))


def import_ifct(session: Session, directory: Path):
    rows, units = (
        read_csv(directory / "compositions.csv"),
        read_csv(directory / "representations.csv"),
    )
    unit_map = {row["code"]: row for row in units}
    if len({r["code"] for r in rows}) != len(rows):
        raise ValueError("IFCT contains duplicate food codes")
    sha = hashlib.sha256((directory / "compositions.csv").read_bytes()).hexdigest()
    source = {
        "dataset": "IFCT 2017 nodef transcription",
        "url": "https://github.com/nodef/ifct2017",
        "sha256": sha,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "repository_license": "AGPL-3.0-or-later",
        "basis": "100g edible portion",
    }
    for row in rows:
        record = session.get(ReferenceFood, row["code"]) or ReferenceFood(code=row["code"])
        record.name, record.data, record.source = row["name"], normalize_ifct(row, unit_map), source
        session.add(record)
    session.commit()
    return {"reference_foods_imported": len(rows), "packaged_products_imported": 0}


def _record_source_id(raw: dict) -> str:
    barcode = raw.get("barcode")
    if isinstance(barcode, str) and barcode:
        return barcode
    return hashlib.sha256(json.dumps(raw, sort_keys=True, default=str).encode()).hexdigest()


def _safe_recipe_name(raw: dict) -> str:
    value = raw.get("title") or raw.get("name")
    if isinstance(value, str) and value.strip():
        return value.strip()[:300]
    return "Unreviewed recipe"


def _store_apify_record(session: Session, raw, source: str, dataset_id: str, category: str | None):
    if not isinstance(raw, dict):
        raise ValueError("Apify record is not an object and cannot be imported")
    if source == "off":
        food = normalize_apify_off(raw, dataset_id, category)
        store_product(session, food, _record_source_id(raw), raw)
        return
    # No actual recipe output was supplied/validated. Stage it without nutrition/suitability claims.
    key = hashlib.sha256(json.dumps(raw, sort_keys=True, default=str).encode()).hexdigest()
    record = session.get(RecipeRecord, key) or RecipeRecord(id=key)
    record.name = _safe_recipe_name(raw)
    record.raw = raw
    record.source = {"provider": "Apify food.com actor", "dataset_id": dataset_id}
    record.review_status = "pending_schema_validation"
    session.add(record)


def import_records(
    session: Session, records, source: str, dataset_id: str, category: str | None = None
) -> dict:
    """Stage one bounded batch of raw Apify records.

    Each row is written inside its own savepoint, so a single unusable or
    conflicting record is skipped with a reason instead of aborting the batch.
    """
    imported = 0
    skipped_reasons: list[dict] = []
    for index, raw in enumerate(records):
        try:
            with session.begin_nested():
                _store_apify_record(session, raw, source, dataset_id, category)
            imported += 1
        except (ValueError, TypeError, IntegrityError) as exc:
            skipped_reasons.append({"record_index": index, "reason": str(exc)[:200]})
            logger.warning("skipped Apify record index=%s type=%s", index, type(exc).__name__)
    return {
        "imported": imported,
        "skipped": len(skipped_reasons),
        "skipped_reasons": skipped_reasons,
    }


async def import_apify(
    session: Session,
    source: str,
    dataset_id: str | None,
    run_id: str | None,
    limit: int,
    category: str | None,
):
    settings = get_settings()
    token = settings.apify_token.get_secret_value() if settings.apify_token else None
    imported, skipped, offset = 0, 0, 0
    skipped_reasons: list[dict] = []
    async with httpx.AsyncClient(timeout=30) as client:
        reader = ApifyReader(client, token)
        dataset_id = dataset_id or await reader.run_dataset(run_id)
        while imported + skipped < limit:
            page = await reader.items(
                dataset_id, limit=min(100, limit - imported - skipped), offset=offset
            )
            if not page:
                break
            summary = import_records(session, page, source, dataset_id, category)
            imported += summary["imported"]
            skipped += summary["skipped"]
            skipped_reasons.extend(summary["skipped_reasons"])
            offset += len(page)
            # Commit each bounded page; no database transaction is held for the next network request.
            session.commit()
    return {
        "imported": imported,
        "skipped": skipped,
        "skipped_reasons": skipped_reasons,
        "dataset_id": dataset_id,
        "source": source,
        "status": "requires_label_confirmation" if source == "off" else "staged_for_review",
    }


def import_demo(session: Session, path: Path):
    foods = json.loads(path.read_text())
    for index, row in enumerate(foods):
        food = FoodObservation.model_validate(row)
        if food.source.kind != "demo":
            raise ValueError("Demo importer requires clearly marked demo observations")
        store_product(session, food, f"demo-{index}", row)
    session.commit()
    return {
        "demo_products": len(foods),
        "warning": "Synthetic fixtures; not commercial label measurements",
    }


def import_reviewed_products(session: Session, path: Path):
    """Load operator-reviewed package declarations, never inferred OFF facts.

    Validate the entire file before changing the catalog. Stable source IDs and
    barcode uniqueness let a reviewed label update its existing catalog record.
    """
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list) or not 1 <= len(records) <= 1000:
        raise ValueError("Reviewed products must be a list of 1 to 1000 records")
    parsed, identifiers = [], set()
    for record in records:
        if not isinstance(record, dict) or set(record) != {"source_id", "food"}:
            raise ValueError("Each reviewed product requires only source_id and food")
        source_id = record["source_id"]
        if not isinstance(source_id, str) or not 1 <= len(source_id.strip()) <= 200:
            raise ValueError("Reviewed product source_id must contain 1 to 200 characters")
        source_id = source_id.strip()
        if source_id in identifiers:
            raise ValueError("Reviewed product source IDs must be unique within the file")
        identifiers.add(source_id)
        food = FoodObservation.model_validate(record["food"])
        if food.source.kind != "manual":
            raise ValueError("Reviewed products require manual source provenance")
        if not food.category or not food.ingredients_complete or not food.advisories_complete:
            raise ValueError(
                "Review the food category, full ingredients, and advisory panel before import"
            )
        parsed.append((source_id, food))
    for source_id, food in parsed:
        store_product(
            session, food, source_id, {"reviewed_observation": food.model_dump(mode="json")}
        )
    session.commit()
    return {"reviewed_products": len(parsed), "source": "operator-reviewed package declarations"}


def main():
    parser = argparse.ArgumentParser(
        description="Source import tools; no scraper runs are launched"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    ifct = sub.add_parser("ifct")
    ifct.add_argument("--directory", type=Path, default=Path("data/raw/ifct2017"))
    ifct.add_argument("--download", action="store_true")
    apify = sub.add_parser("apify")
    apify.add_argument("--source", choices=["off", "recipes"], required=True)
    ids = apify.add_mutually_exclusive_group(required=True)
    ids.add_argument("--dataset-id")
    ids.add_argument("--run-id")
    apify.add_argument("--limit", type=int, default=100)
    apify.add_argument("--category")
    demo = sub.add_parser("demo")
    demo.add_argument("--file", type=Path, default=Path("data/demo_products.json"))
    reviewed = sub.add_parser("reviewed-products")
    reviewed.add_argument("--file", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "ifct" and args.download:
        asyncio.run(download_ifct(args.directory))
    if args.command == "apify" and not 1 <= args.limit <= 1000:
        parser.error("--limit must be between 1 and 1000")
    with Session(make_engine(get_settings().database_url)) as session:
        if args.command == "ifct":
            result = import_ifct(session, args.directory)
        elif args.command == "apify":
            result = asyncio.run(
                import_apify(
                    session, args.source, args.dataset_id, args.run_id, args.limit, args.category
                )
            )
        elif args.command == "reviewed-products":
            result = import_reviewed_products(session, args.file)
        else:
            result = import_demo(session, args.file)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
