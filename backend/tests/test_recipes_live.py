"""Live recipe search: bounded actor polling, tolerant conversion, honest serving.

The Apify HTTP API is replaced with ``httpx.MockTransport`` so the real client
code path runs (run start, polling, deadline, dataset read, conversion) without a
network call and without spending anything on the pay-per-result actor.
"""

import asyncio
import json
from datetime import datetime

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import rate_limit as rate_limit_module
from app.api import recipes as recipes_module
from app.config import Settings
from app.integrations import apify as apify_module
from app.integrations.apify import ApifyReader
from app.integrations.off import ProviderError
from app.models import RecipeRecord
from app.services import recipes_live as live
from app.services.recipes_live import SOURCE_NOTE, extract_grams, query_key
from tests.conftest import signup

APIFY = "https://api.apify.com/v2/"
TOKEN = "test-apify-token"
RUN_ID = "RUN1234567890"
DATASET_ID = "DS1234567890"
RUN_COST = 0.063
# The actor's real output shape (verified live): title/url/ingredients as list[str].
PANIR = {
    "id": "112304",
    "title": "Paneer Butter Masala",
    "url": "https://www.food.com/recipe/paneer-butter-masala-112304",
    "author": "crazy cook",
    "rating": 4.5,
    "servings": "5 serving(s)",
    "calories": 73.7,
    "ingredients": ["250   g    panir", "1       bay leaf", "1 cup rice", "salt, to taste"],
    "directions": ["Grind the onions.", "Simmer the gravy."],
    "tags": ["Indian"],
    "error": None,
}
LEMON_RICE = {
    "title": "Lemon Rice",
    "url": "https://www.food.com/recipe/lemon-rice-2",
    "ingredients": ["200 g rice", "1 lemon"],
    "error": None,
}


class ApifyStub:
    """A scripted Apify v2 API: starts one run, answers polling, serves one dataset."""

    def __init__(self, items=None, run_status="SUCCEEDED"):
        self.items = items if items is not None else [PANIR, LEMON_RICE]
        self.run_status = run_status
        self.requests: list[httpx.Request] = []

    @property
    def runs_started(self) -> int:
        return sum(1 for request in self.requests if request.method == "POST")

    @property
    def item_reads(self) -> int:
        return sum(1 for request in self.requests if self._is_item_read(request))

    @staticmethod
    def _is_item_read(request: httpx.Request) -> bool:
        path = str(request.url).split("?", 1)[0]
        return "/datasets/" in path and path.endswith("/items")

    def run_input(self) -> dict:
        return json.loads(self.requests[0].content)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url)
        if request.method == "POST" and url.startswith(APIFY + "acts/") and "/runs" in url:
            return httpx.Response(
                201,
                json={
                    "data": {
                        "id": RUN_ID,
                        "status": "READY",
                        "defaultDatasetId": DATASET_ID,
                        "usageTotalUsd": RUN_COST,
                    }
                },
            )
        if "/actor-runs/" in url:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "id": RUN_ID,
                        "status": self.run_status,
                        "defaultDatasetId": DATASET_ID,
                        "usageTotalUsd": RUN_COST,
                    }
                },
            )
        if self._is_item_read(request):
            return httpx.Response(200, json=self.items)
        return httpx.Response(404, json={"error": {"message": "unexpected request"}})


def settings_with(**overrides) -> Settings:
    values = {
        "apify_token": TOKEN,
        "recipes_live_enabled": True,
        "recipes_live_max_items": 5,
        "recipes_live_timeout_seconds": 10,
    }
    values.update(overrides)
    return Settings(**values)


def use_settings(monkeypatch, **overrides) -> Settings:
    """Point every module that reads settings at one test value, so no real token is used."""
    value = settings_with(**overrides)
    monkeypatch.setattr(recipes_module, "get_settings", lambda: value)
    monkeypatch.setattr(live, "get_settings", lambda: value)
    monkeypatch.setattr(rate_limit_module, "get_settings", lambda: value)
    return value


@pytest.fixture(autouse=True)
def safe_settings(monkeypatch):
    """Never let these tests see the token in backend/.env."""
    # Poll instantly: the deadline logic is still exercised, without real waiting.
    monkeypatch.setattr(apify_module, "POLL_INTERVAL_SECONDS", 0)
    return use_settings(monkeypatch)


@pytest.fixture
def mock_apify(client):
    """Swap the app's shared HTTP client for a MockTransport-backed one."""
    created: list[httpx.AsyncClient] = []

    def install(stub: ApifyStub) -> ApifyStub:
        http = httpx.AsyncClient(transport=httpx.MockTransport(stub))
        created.append(http)
        client.app.state.http = http
        return stub

    yield install
    for http in created:
        asyncio.run(http.aclose())


def run_search(stub: ApifyStub):
    """Call the reader directly, in its own loop, against one mock transport."""

    async def call():
        async with httpx.AsyncClient(transport=httpx.MockTransport(stub)) as http:
            reader = ApifyReader(http, TOKEN)
            return await reader.search_recipes("paneer butter masala", 2, 10, TOKEN)

    return asyncio.run(call())


def fetch(session, stub: ApifyStub, query="paneer butter masala", limit=5):
    async def call():
        async with httpx.AsyncClient(transport=httpx.MockTransport(stub)) as http:
            return await live.fetch_and_store(session, query, limit, client=http)

    return asyncio.run(call())


def seed_validated(session: Session, count: int, name="Masala Dal") -> None:
    for index in range(count):
        session.add(
            RecipeRecord(
                id=f"validated-{index}",
                name=f"{name} {index}",
                raw={"ingredients": [{"text": "1 cup dal", "grams": None}], "cooking_notes": []},
                source={"provider": "demo fixture"},
                review_status="validated",
            )
        )
    session.commit()


# --- The reader: one bounded run, a hard deadline, no leaked token --------------------------


def test_search_recipes_starts_one_bounded_run_and_returns_its_dataset():
    stub = ApifyStub()
    result = run_search(stub)

    assert result["run_id"] == RUN_ID
    assert result["dataset_id"] == DATASET_ID
    assert result["status"] == "SUCCEEDED"
    assert result["cost_usd"] == RUN_COST
    assert result["items"] == [PANIR, LEMON_RICE]
    assert stub.runs_started == 1, "exactly one billable run is started"
    assert stub.items and stub.item_reads == 1
    started = stub.requests[0]
    assert started.headers["Authorization"] == f"Bearer {TOKEN}"
    assert TOKEN not in str(started.url), "the token never travels in a URL"
    assert all(TOKEN not in str(request.url) for request in stub.requests)
    assert stub.run_input() == {
        "searchQuery": "paneer butter masala",
        "sortBy": "PERFORMANCE",
        "maxItems": 2,
    }
    assert started.url.params["timeout"] == "10", "the run is bounded server-side too"


def test_search_recipes_stops_at_the_deadline_without_reading_a_dataset():
    stub = ApifyStub(run_status="RUNNING")

    async def call():
        async with httpx.AsyncClient(transport=httpx.MockTransport(stub)) as http:
            with pytest.raises(ProviderError) as caught:
                await ApifyReader(http, TOKEN).search_recipes("paneer", 2, 0, TOKEN)
            return str(caught.value)

    message = asyncio.run(call())
    assert "did not finish in time" in message
    assert stub.item_reads == 0, "a run that never finishes yields no dataset read"


def test_search_recipes_reports_a_failed_run_and_imports_nothing():
    stub = ApifyStub(run_status="FAILED")

    async def call():
        async with httpx.AsyncClient(transport=httpx.MockTransport(stub)) as http:
            with pytest.raises(ProviderError) as caught:
                await ApifyReader(http, TOKEN).search_recipes("paneer", 2, 10, TOKEN)
            return str(caught.value)

    assert "FAILED" in asyncio.run(call())
    assert stub.item_reads == 0


def test_search_recipes_needs_a_token():
    stub = ApifyStub()

    async def call():
        async with httpx.AsyncClient(transport=httpx.MockTransport(stub)) as http:
            with pytest.raises(ProviderError):
                await ApifyReader(http).search_recipes("paneer", 2, 10, None)

    asyncio.run(call())
    assert stub.requests == [], "no run is started without a token"


# --- Conversion: a weight only when the line states one -------------------------------------


def test_grams_come_only_from_an_explicit_mass_in_the_line():
    assert extract_grams("200 g paneer") == 200
    assert extract_grams("250   g    panir") == 250, "the actor's column spacing is handled"
    assert extract_grams("1 kg potatoes") == 1000
    assert extract_grams("1/2 lb butter") == 226.8
    assert extract_grams("8 oz cream cheese") == 226.8
    # A volume, a count or a seasoning is not a mass, so it stays unknown.
    assert extract_grams("1 cup rice") is None
    assert extract_grams("1   inch    cinnamon stick") is None
    assert extract_grams("2       cloves") is None
    assert extract_grams("salt, to taste") is None
    assert extract_grams("500 mg salt") is None, "only g/kg/oz/lb are explicit masses here"
    assert extract_grams("0 g pepper") is None


def test_rows_are_stored_as_labelled_source_records(db_engine):
    stub = ApifyStub()
    with Session(db_engine) as session:
        summary = fetch(session, stub, limit=5)
        assert summary["created"] == 2 and summary["skipped"] == 0
        assert summary["run_id"] == RUN_ID and summary["cost_usd"] == RUN_COST

        records = list(session.scalars(select(RecipeRecord)))
        panir = next(row for row in records if row.name == "Paneer Butter Masala")

        assert panir.review_status == "imported_source"
        assert panir.raw["cooking_notes"] == []
        assert panir.raw["ingredients"] == [
            {"text": "250   g    panir", "grams": 250.0},
            {"text": "1       bay leaf", "grams": None},
            {"text": "1 cup rice", "grams": None},
            {"text": "salt, to taste", "grams": None},
        ], "lines are kept verbatim and only stated masses are filled in"
        assert panir.source == {
            "provider": "Apify food.com scraper",
            "actor": "parseforge/food-com-scraper",
            "actor_id": "L9lMlZe30ghx2Zdv3",
            "run_id": RUN_ID,
            "dataset_id": DATASET_ID,
            "query": "paneer butter masala",
            "query_key": "paneer butter masala",
            "retrieved_at": panir.source["retrieved_at"],
            "reference": "https://www.food.com/recipe/paneer-butter-masala-112304",
        }
        datetime.fromisoformat(panir.source["retrieved_at"])
        assert all(row.review_status == "imported_source" for row in records)


def test_unusable_rows_are_skipped_with_a_reason_and_never_abort_the_batch(db_engine):
    stub = ApifyStub(
        items=[
            PANIR,
            {"url": "https://www.food.com/recipe/unnamed"},
            {"title": "Too many", "ingredients": [f"{index} g thing" for index in range(41)]},
            {"title": "No lines", "ingredients": []},
        ]
    )
    with Session(db_engine) as session:
        summary = fetch(session, stub)

    assert summary["created"] == 1, "the one usable row is still stored"
    assert summary["skipped"] == 3
    reasons = [item["reason"] for item in summary["skipped_reasons"]]
    assert reasons == [
        "no recipe name",
        "more than 40 ingredient lines",
        "no ingredient lines",
    ]
    assert [item["record_index"] for item in summary["skipped_reasons"]] == [1, 2, 3]


def test_a_repeated_fetch_reuses_rows_instead_of_duplicating_them(db_engine):
    stub = ApifyStub()
    with Session(db_engine) as session:
        first = fetch(session, stub)
        second = fetch(session, stub)
        assert first["created"] == 2 and second["created"] == 0 and second["reused"] == 2
        assert session.scalar(select(func.count()).select_from(RecipeRecord)) == 2


# --- The endpoint: cached, fetched, disabled, unavailable -----------------------------------


def test_imported_rows_are_served_with_an_honest_label(client, mock_apify):
    headers = signup(client)
    mock_apify(ApifyStub())

    body = client.get("/api/recipes", params={"q": "paneer"}, headers=headers).json()

    assert body["live_status"] == "fetched"
    assert body["query"] == "paneer"
    assert len(body["recipes"]) == 2, "both rows stored for this query are served"
    row = next(item for item in body["recipes"] if item["name"] == "Paneer Butter Masala")
    assert row["review_status"] == "imported_source"
    assert row["review_status"] != "validated"
    assert row["source_note"] == SOURCE_NOTE
    assert SOURCE_NOTE in row["warnings"]
    assert row["declarations_confirmed"] is False
    assert row["source"]["provider"] == "Apify food.com scraper"
    assert [item["grams"] for item in row["ingredients"]][:2] == [250.0, None]
    assert body["pending_count"] == 2, "imported rows await review and are counted as such"
    assert "not confirmed" in body["message"]


def test_a_repeated_query_serves_the_cache_and_never_runs_again(client, mock_apify):
    headers = signup(client)
    stub = mock_apify(ApifyStub())

    first = client.get("/api/recipes", params={"q": "paneer"}, headers=headers).json()
    second = client.get("/api/recipes", params={"q": "paneeR"}, headers=headers).json()

    assert first["live_status"] == "fetched"
    assert second["live_status"] == "cached"
    assert stub.runs_started == 1, "the second search costs nothing"
    assert [row["id"] for row in first["recipes"]] == [row["id"] for row in second["recipes"]]


def test_an_imported_row_can_be_fetched_by_id(client, mock_apify):
    headers = signup(client)
    mock_apify(ApifyStub())
    listed = client.get("/api/recipes", params={"q": "lemon"}, headers=headers).json()
    row = next(item for item in listed["recipes"] if item["name"] == "Lemon Rice")

    response = client.get(f"/api/recipes/{row['id']}", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["review_status"] == "imported_source"
    assert body["source_note"] == SOURCE_NOTE
    assert body["source"]["reference"] == "https://www.food.com/recipe/lemon-rice-2"


def test_a_failed_live_fetch_degrades_to_an_empty_state_not_a_500(client, mock_apify):
    headers = signup(client)
    mock_apify(ApifyStub(run_status="FAILED"))

    response = client.get("/api/recipes", params={"q": "paneer"}, headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["live_status"] == "unavailable"
    assert body["recipes"] == []
    assert body["pending_count"] == 0
    assert "FAILED" in body["message"] and "your own ingredient list" in body["message"]


def test_a_live_timeout_returns_the_cached_state_instead_of_a_500(client, mock_apify, monkeypatch):
    """A run that never finishes is reported plainly, not raised as a 5xx.

    ``recipes_live_timeout_seconds`` has a 10s floor, so the test builds the same
    settings object past its validation to compress the deadline; production can
    never configure a shorter one, and the code path is identical.
    """
    stalled = Settings.model_construct(
        apify_token=SecretStr(TOKEN),
        recipes_live_enabled=True,
        recipes_live_max_items=5,
        recipes_live_timeout_seconds=0,
    )
    monkeypatch.setattr(recipes_module, "get_settings", lambda: stalled)
    monkeypatch.setattr(live, "get_settings", lambda: stalled)
    headers = signup(client)
    stub = mock_apify(ApifyStub(run_status="RUNNING"))

    response = client.get("/api/recipes", params={"q": "paneer"}, headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["live_status"] == "unavailable"
    assert body["recipes"] == []
    assert "did not finish in time" in body["message"]
    assert stub.item_reads == 0, "a run that never finishes yields no dataset read"


def test_live_search_is_disabled_without_a_token(client, mock_apify, monkeypatch):
    use_settings(monkeypatch, apify_token=None)
    headers = signup(client)
    stub = mock_apify(ApifyStub())

    response = client.get("/api/recipes", params={"q": "paneer"}, headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["live_status"] == "disabled"
    assert body["recipes"] == []
    assert stub.requests == [], "nothing is requested without a token"


def test_live_search_is_disabled_when_the_setting_is_off(client, mock_apify, monkeypatch):
    use_settings(monkeypatch, recipes_live_enabled=False)
    headers = signup(client)
    stub = mock_apify(ApifyStub())

    body = client.get("/api/recipes", params={"q": "paneer"}, headers=headers).json()

    assert body["live_status"] == "disabled"
    assert stub.runs_started == 0


def test_a_rich_local_result_set_skips_the_live_run(client, db_engine, mock_apify):
    headers = signup(client)
    stub = mock_apify(ApifyStub())
    with Session(db_engine) as session:
        seed_validated(session, 5)

    body = client.get("/api/recipes", params={"q": "dal"}, headers=headers).json()

    assert len(body["recipes"]) == 5
    assert body["live_status"] == "cached"
    assert stub.runs_started == 0, "five reviewed rows already answer this search"
    assert "confirm" in body["message"]


def test_live_attempts_are_rate_limited(client, mock_apify, monkeypatch):
    use_settings(monkeypatch, rate_limit_recipes_live_per_minute=1)
    headers = signup(client)
    stub = mock_apify(ApifyStub())

    first = client.get("/api/recipes", params={"q": "paneer"}, headers=headers)
    second = client.get("/api/recipes", params={"q": "lemon rice"}, headers=headers)

    assert first.status_code == 200, first.text
    assert first.json()["live_status"] == "fetched"
    assert second.status_code == 429, second.text
    assert second.json()["code"] == "rate_limited"
    assert int(second.headers["Retry-After"]) >= 1
    assert stub.runs_started == 1, "the throttled attempt never reaches the actor"


def test_cached_reads_are_not_throttled(client, mock_apify, monkeypatch):
    use_settings(monkeypatch, rate_limit_recipes_live_per_minute=1)
    headers = signup(client)
    mock_apify(ApifyStub())
    client.get("/api/recipes", params={"q": "paneer"}, headers=headers)

    for _ in range(3):
        response = client.get("/api/recipes", params={"q": "paneer"}, headers=headers)
        assert response.status_code == 200 and response.json()["live_status"] == "cached"


def test_live_spend_is_capped_by_the_setting(client, mock_apify, monkeypatch):
    use_settings(monkeypatch, recipes_live_max_items=2)
    headers = signup(client)
    stub = mock_apify(ApifyStub())

    body = client.get("/api/recipes", params={"q": "paneer", "limit": 20}, headers=headers).json()

    assert stub.run_input()["maxItems"] == 2
    assert body["live_status"] == "fetched"


def test_query_key_normalises_so_one_cache_serves_one_query():
    assert query_key("  Paneer   Butter ") == "paneer butter"
    assert query_key("") == ""
    assert live.query_key("A" * 200) == "a" * 100
