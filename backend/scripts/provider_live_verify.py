"""Opt-in live contract check using the production ModelAssist methods.

Run from the repository root:
  UV_CACHE_DIR=/tmp/ingredient-risk-uv-cache UV_LINK_MODE=copy \
    uv --directory backend run python scripts/provider_live_verify.py --live

Only a generated ingredient image and synthetic preference candidates are sent.
The script prints response summaries, never API keys or response headers.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image, ImageDraw

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.config import get_settings  # noqa: E402
from app.integrations.models import ModelAssist  # noqa: E402
from app.integrations.off import ProviderError  # noqa: E402


def synthetic_image() -> bytes:
    image = Image.new("RGB", (420, 160), "white")
    ImageDraw.Draw(image).text((18, 25), "INGREDIENTS: RICE FLOUR, MAIDA, SALT", fill="black")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def synthetic_candidates() -> dict:
    return {
        "ranking_method": "deterministic",
        "fallback_reason": None,
        "candidates": [
            {
                "product_id": "synthetic_plain",
                "food": {
                    "name": "Plain rice crackers",
                    "category": "crackers",
                    "ingredients_text": "rice flour, salt",
                },
                "comparisons": [{"replacement": 120}],
            },
            {
                "product_id": "synthetic_mild",
                "food": {
                    "name": "Mild rice crackers",
                    "category": "crackers",
                    "ingredients_text": "rice flour, a little salt",
                },
                "comparisons": [{"replacement": 120}],
            },
        ],
    }


async def verify(provider: str) -> dict:
    base_settings = get_settings()
    # Keep the real model IDs/keys while bounding response tokens and total latency.
    settings = base_settings.model_copy(update={"label_timeout": 18, "label_max_tokens": 512})
    output = {}
    async with asyncio.timeout(25):
        async with httpx.AsyncClient(timeout=20) as client:
            assistant = ModelAssist(client, settings)
            if provider in {"all", "fireworks"} and settings.fireworks_api_key:
                try:
                    food = await assistant.extract_label(synthetic_image(), "image/png")
                    output["fireworks"] = {
                        "status": "passed",
                        "model": food.source.model,
                        "name_present": bool(food.name),
                        "extracted_ingredients": food.ingredients_text,
                        "basis": food.basis,
                        "nutrient_fields": len(food.nutrients),
                        "known_nutrient_count": sum(
                            value is not None for value in food.nutrients.values()
                        ),
                        "requires_confirmation": (
                            not food.ingredients_complete and not food.advisories_complete
                        ),
                    }
                except (ProviderError, TimeoutError, ValueError) as exc:
                    output["fireworks"] = {
                        "status": "failed",
                        "error_type": type(exc).__name__,
                    }
            elif provider in {"all", "fireworks"}:
                output["fireworks"] = {"status": "not configured"}

            if provider in {"all", "typesafe"} and settings.typesafe_api_key:
                result = await assistant.rank_preferences(
                    synthetic_candidates(), "plain, mild crackers"
                )
                output["typesafe"] = {
                    "status": "passed"
                    if result.get("ranking_method") == "deterministic_with_jev_preference_ties"
                    else "fallback",
                    "model": result.get("model"),
                    "ranking_method": result.get("ranking_method"),
                    "fallback_reason": result.get("fallback_reason"),
                    "candidate_ids": [item["product_id"] for item in result["candidates"]],
                    "score_ids": sorted(result.get("preference_scores", {})),
                }
            elif provider in {"all", "typesafe"}:
                output["typesafe"] = {"status": "not configured"}
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true", help="send the bounded synthetic provider requests"
    )
    parser.add_argument(
        "--provider",
        choices=("all", "fireworks", "typesafe"),
        default="all",
        help="select which production adapter to exercise",
    )
    args = parser.parse_args()
    if not args.live:
        parser.error("pass --live to send the bounded synthetic requests")
    print(json.dumps(asyncio.run(verify(args.provider)), indent=2))


if __name__ == "__main__":
    main()
