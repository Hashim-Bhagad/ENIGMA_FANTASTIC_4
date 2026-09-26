# Gap remediation — 2026-09-26

Every item is an audited gap from the repository review, what changed, and how it was verified.
Verification is reproduced at the end; nothing here is claimed from reading alone.

## Fixed

| # | Gap | Change | Evidence |
| --- | --- | --- | --- |
| 1 | Replacement flow returned nothing for allergy users because every community record was filtered as `unresolved` | Two-tier result: `candidates` (verified) and `needs_review` (blocked only by missing information, each with `review_reasons`). Tiers never merge; the message states that no check was relaxed | `app/services/recommendations.py`, live check "community candidate surfaces as needs_review with reasons", `tests/test_recommendations.py` |
| 2 | Vague findings ("has not been confirmed") | Every finding carries `code`, `group`, `title`, `detail`, `next_step`, `affects`; unresolved entries are deduplicated; the result carries `status_reason`. Wording names the source, the panel/nutrient and the action, and adapts to cooked dishes | `app/services/assessment.py`, `tests/test_explanations.py`, UI check of `/assessment` |
| 3 | No way to check a cooked meal | `POST /api/dishes/assess` + `GET /api/dishes/options`: dish ingredients resolve to IFCT reference foods (explicit code, else exact normalized name — never fuzzy), a per-100 g estimate appears only when every ingredient is matched *and* weighed, preparation notes produce explained considerations, and the dish is persisted as an assessment so history/detail keep working | `app/services/dishes.py`, `app/api/dishes.py`, `tests/test_dishes.py`, live checks |
| 4 | Unauthenticated GETs wrote to the shared catalog | Every `/api/*` route requires a bearer token except `POST /api/auth/register` and `POST /api/auth/login`; provider reads send `Cache-Control: no-store`; catalog updates never re-source a record across kinds | `app/api/*.py`, `app/catalog.py`, `tests/test_api.py` |
| 5 | No abuse controls on paid providers or login | Per-scope token buckets (`auth` 10/min per IP, `labels/extract` 10/min per user, provider reads 30/min, recommendations 20/min), `429` + `Retry-After` + code `rate_limited`, request-body cap (6 MiB default) with a bounded drain so clients read the 413 instead of a reset connection | `app/rate_limit.py`, `app/main.py`, `tests/test_api.py`, live checks |
| 6 | No logging, message-only errors | Structured logging for provider failures, rate-limit rejections and unexpected errors (no secrets, no bodies); stable `code` next to FastAPI's `detail` for every error response | `app/errors.py`, `app/main.py`, `app/integrations/*` |
| 7 | Matching used two normalization regimes and dropped same-subtype aliases | Allergen/exclusion matching shares the taxonomy normalizer (NFKC, casefolding, dash/quote mapping, span-preserving), and same-subtype alias variants are mapped | `app/services/ingredient_taxonomy.py`, `app/services/assessment.py`, `tests/test_assessment.py` |
| 8 | One malformed Apify row aborted the import | Per-record validation with skip-and-count summaries; barcodes validated against the schema pattern; no `str()` of dicts/lists | `app/integrations/off.py`, `app/importers.py`, `tests/test_sources.py` |
| 9 | Provenance reported a confirmed-absent advisory as "missing" | Field status now distinguishes `available`, `confirmed_absent`, `missing` and `unusable`, and carries the completeness flags | `app/services/provenance.py`, `tests/test_provenance.py` |
| 10 | Silent profile-save failures, no 401 recovery, no timeouts, history never refreshed, 50-row cap | Save errors surface and rethrow; `profile_version_stale` re-fetches the profile and keeps the draft; a 401 anywhere clears the session; requests have timeouts (15 s, 60 s for label extraction); the assessment refresh updates history; history pages with `offset`/`total` | `frontend/src/api/client.ts`, `frontend/src/state/AppContext.tsx`, `frontend/src/api/*.test.ts` |
| 11 | Guide and reference data unreachable from the UI; dish questions were hardcoded | The guide tab renders `POST /api/profiles/guide`; the cooked-meal screen searches `/api/reference-foods` and `/api/recipes`; preparation vocabulary comes from `GET /api/dishes/options`; dead demo data removed | `frontend/app/(tabs)/guide.tsx`, `frontend/app/dish.tsx`, `frontend/README.md` |
| 12 | No frontend tests, no CI, no portable docs or license | `vitest` transport/session tests, GitHub Actions running ruff + SQLite and Postgres pytest + typecheck + frontend tests, MIT `LICENSE` + `NOTICE` for AGPL/ODbL data, docs index with research/archive triage and corrected stale claims | `.github/workflows/ci.yml`, `LICENSE`, `NOTICE`, `docs/README.md` |
| 13 | Only SQLite-backed tests; migration drift invisible | `TEST_DATABASE_URL` Postgres mode builds the schema from Alembic, per-test truncation, an empty-database migration + drift test, and Postgres-only contract tests (`FOR UPDATE` locking, JSONB search, length/unique enforcement, tz round-trip) | `backend/tests/conftest.py`, `tests/test_migrations.py`, `tests/test_postgres_contracts.py` |

## Deliberate limitations (not defects)

- **Rate limiting is per process.** Single uvicorn worker today; a shared store is required before running multiple replicas.
- **No idempotency keys** on assessments or recommendations. Only `PUT /api/profiles/me` is retry-safe (an identical payload returns the current version).
- **The verified replacement tier still needs operator-reviewed records.** Community records now surface in `needs_review`, not as verified candidates. `backend/data/demo_products.json` holds four cracker fixtures.
- **Recipe templates are read-only and empty until reviewed rows exist.** `GET /api/recipes` returns an explanatory empty page; the cooked-meal flow works without it.
- **Dish estimates cover label nutrients only.** IFCT available carbohydrate and free sugars are deliberately not mapped to label totals; the estimate says so.
- **Frontend tests cover the transport and session only.** No component or end-to-end browser suite is committed.
- **`backend/.env` still holds real-looking provider keys.** They are gitignored and excluded from Docker builds, but rotate them before sharing the folder. Stale `GEMINI_*` entries were removed.

## Verification (reproduced on the committed tree)

```sh
cd backend
uv run pytest -q                                        # 87 passed, 8 skipped
uv run ruff check app tests scripts && uv run ruff format --check app tests scripts
TEST_DATABASE_URL=postgresql+psycopg://dietary:<pw>@localhost:5433/dietary_test uv run pytest -q   # 95 passed
uv run python scripts/runtime_api_smoke.py              # result: passed
cd ../frontend
npx tsc --noEmit                                        # clean
npm run test                                            # 8 passed
```

A throwaway HTTP script additionally exercised the new surface against the rebuilt Compose stack
(22 checks): 401 on an unauthenticated catalog read, dish options with codes and labels, an IFCT
match producing a per-100 g estimate, an unmatched ingredient producing no estimate with a reason,
dish blockers phrased for cooking rather than a pack, `profile_version_stale` on a stale dish
request, verified vs unverified replacement tiers with no overlap, `413 payload_too_large`, and
`429` with `Retry-After`. The script was disposable; the durable checks live in
`scripts/runtime_api_smoke.py` and the test suite.

## Notes on the working tree

A second coding process was editing this repository during the review and remediation (it added
`/api/recipes`, `RecipeRecord`, the `FoodFacts` component and its own commits). Its work was kept
where it agreed with the frozen contracts and consolidated where it duplicated them — the
`POST /api/assessments/dish` alias was removed in favour of `POST /api/dishes/assess`, and
`/api/recipes` now requires authentication like every other `/api` route.
