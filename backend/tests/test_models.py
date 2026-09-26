import asyncio

import httpx

from app.config import Settings
from app.integrations.models import ModelAssist


def candidates():
    return {
        "candidates": [
            {
                "product_id": "one",
                "food": {
                    "name": "Herbed crackers",
                    "category": "crackers",
                    "ingredients_text": "Rice",
                },
                "comparisons": [{"replacement": 200}],
            },
            {
                "product_id": "two",
                "food": {
                    "name": "Plain crackers",
                    "category": "crackers",
                    "ingredients_text": "Rice",
                },
                "comparisons": [{"replacement": 200}],
            },
            {
                "product_id": "three",
                "food": {
                    "name": "Plain crackers with more sodium",
                    "category": "crackers",
                    "ingredients_text": "Rice",
                },
                "comparisons": [{"replacement": 300}],
            },
        ],
        "ranking_method": "deterministic",
        "fallback_reason": None,
    }


def test_jev_reorders_only_nutrient_ties_and_sends_no_identity():
    def handler(request):
        import json

        payload = json.loads(request.content)
        assert "email" not in payload["state"] and "conditions" not in payload["state"]
        return httpx.Response(
            200,
            json={
                "model": "jev-1.13.0",
                "answers": {
                    "candidate_0": {
                        "type": "score",
                        "score": 0,
                        "confidence": 1,
                        "probabilities": {"0": 1, "1": 0, "2": 0},
                    },
                    "candidate_1": {
                        "type": "score",
                        "score": 2,
                        "confidence": 1,
                        "probabilities": {"0": 0, "1": 0, "2": 1},
                    },
                    "candidate_2": {
                        "type": "score",
                        "score": 2,
                        "confidence": 1,
                        "probabilities": {"0": 0, "1": 0, "2": 1},
                    },
                },
            },
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            service = ModelAssist(client, Settings(typesafe_api_key="test-provider-key"))
            return await service.rank_preferences(candidates(), "Plain crackers")

    result = asyncio.run(run())
    assert [x["product_id"] for x in result["candidates"]] == ["two", "one", "three"]


def test_model_errors_and_malformed_responses_keep_deterministic_candidates():
    for body, status in [({}, 429), ({"model": "jev-1.13.0", "answers": {}}, 200)]:

        async def run(body=body, status=status):
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda request, body=body, status=status: httpx.Response(status, json=body)
                )
            ) as client:
                service = ModelAssist(client, Settings(typesafe_api_key="test-provider-key"))
                return await service.rank_preferences(candidates(), "Plain")

        result = asyncio.run(run())
        assert result["ranking_method"] == "deterministic"
        assert [x["product_id"] for x in result["candidates"]] == ["one", "two", "three"]
        assert result["fallback_reason"] == "jev_uncertain_or_unavailable"


def test_fireworks_image_extraction_keeps_arithmetic_in_code():
    import json

    def handler(request):
        assert str(request.url) == "https://api.fireworks.ai/inference/v1/chat/completions"
        payload = json.loads(request.content)
        assert payload["model"] == "accounts/fireworks/models/deepseek-v4p1-flash"
        assert payload["max_tokens"] == 2048
        assert payload["response_format"]["type"] == "json_schema"
        assert "nutrients" in payload["response_format"]["json_schema"]["schema"]["properties"]
        assert payload["messages"][0]["content"][1]["image_url"]["url"].startswith(
            "data:image/png;base64,"
        )
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {
                                    "name": "Test label",
                                    "ingredients_text": "Rice, salt",
                                    "advisories_text": None,
                                    "basis": "100g",
                                    "nutrients": {
                                        "sodium_mg": {"value": 0.0428, "unit": "g"},
                                        "energy_kcal": {"value": 1490, "unit": "kJ"},
                                        "phosphorus_mg": {"value": 788, "unit": "g"},
                                        "sugars_g": {"value": 0, "unit": "g"},
                                        "fiber_g": {"value": 1, "unit": None},
                                    },
                                }
                            )
                        },
                    }
                ]
            },
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await ModelAssist(
                client, Settings(fireworks_api_key="test-provider-key")
            ).extract_label(b"test", "image/png")

    food = asyncio.run(run())
    assert food.nutrients["sodium_mg"] == 42.8
    assert round(food.nutrients["energy_kcal"], 2) == 356.12
    assert food.nutrients["sugars_g"] == 0
    assert food.nutrients["phosphorus_mg"] is None
    assert food.nutrients["fiber_g"] is None
    assert not food.ingredients_complete and not food.advisories_complete
    assert food.source.model == "accounts/fireworks/models/deepseek-v4p1-flash"


def test_fireworks_unusable_or_truncated_outputs_require_manual_entry():
    import pytest

    from app.integrations.off import ProviderError

    responses = [
        httpx.Response(401, json={}),
        httpx.Response(
            200, json={"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]}
        ),
        httpx.Response(
            200, json={"choices": [{"finish_reason": "stop", "message": {"content": "not JSON"}}]}
        ),
    ]
    for response in responses:

        async def run(response=response):
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(lambda request: response)
            ) as client:
                return await ModelAssist(
                    client, Settings(fireworks_api_key="test-provider-key")
                ).extract_label(b"test", "image/png")

        with pytest.raises(ProviderError, match="manually"):
            asyncio.run(run())


def test_serving_only_label_does_not_invent_a_100g_basis():
    from app.integrations.models import normalize_label

    food = normalize_label(
        {
            "name": "Serving-only label",
            "ingredients_text": None,
            "advisories_text": None,
            "basis": None,
            "nutrients": {"sodium_mg": {"value": 150, "unit": "mg"}},
        },
        "test-model",
    )
    assert food.basis is None
    assert food.nutrients["sodium_mg"] is None


def test_missing_label_product_name_uses_explicit_placeholder():
    from app.integrations.models import normalize_label

    food = normalize_label(
        {
            "name": None,
            "ingredients_text": "Rice flour, salt",
            "advisories_text": None,
            "basis": None,
            "nutrients": {},
        },
        "test-model",
    )
    assert food.name == "Unidentified product from label photo"
