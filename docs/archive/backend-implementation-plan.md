# Backend foundation implementation plan

> Status: executed — kept for provenance; current behaviour lives in `backend/README.md`. Banner added 2026-09-26. This plan was carried out; the code and verification sections below are historical.

**Goal:** Verify supplied sources and deliver a runnable uv-managed, Docker-containerized FastAPI/PostgreSQL backend supporting the first assessment-to-replacement journey.

**Architecture:** A single backend owns identity, profiles, observations, assessment snapshots, and recommendations. Source adapters normalize observations without inventing unknowns. Optional model calls are isolated from deterministic eligibility and numeric comparison.

**Stack:** Python 3.12, uv, FastAPI, SQLAlchemy, PostgreSQL, Alembic, HTTPX, Pydantic, pytest, Docker Compose.

**Spec:** Existing `project-plan-review.md`, `dietary-guidance-and-replacements.md`, and `typesafe-jev-integration-plan.md`; the user's explicit instruction starts implementation.

## Constraints

- PostgreSQL is application storage; SQLite is permitted only as a fast unit-test harness.
- Native/web clients call FastAPI, never PostgreSQL or keyed providers directly.
- Missing nutrients remain null; declared ingredients and precautionary advisories remain distinct.
- Dataset reachability is separate from data quality, source terms, and clinical suitability.
- Do not start paid Apify scraper runs during verification.
- All personal routes are owner scoped; stale profile versions are rejected.
- Candidate eligibility is deterministic; models only assist extraction and preference ranking.
- Docker startup runs migrations, and readiness verifies the database.
- Synthetic demo fixtures are visibly marked and never presented as actual commercial products.

## Deliverables and checks

1. **Verify sources:** HTTP probes and sample audit for supplied actors/run, IFCT CSV/units, OFF product/search, Barcode List. Save response metadata and data-quality findings. Formula check: IFCT `na=0.0027` × declared factor `1000` = `2.7 mg`; unknown values stay null.
2. **Bootstrap:** `backend/pyproject.toml`, lockfile, settings, Dockerfile, root Compose, environment example, README. Verify `uv sync --locked`, image build, Compose configuration, container liveness/readiness.
3. **Persist accounts and profiles:** models, Alembic migration, password hashing/JWT, account/profile routes. Verify register/login/profile reload, stale writes, and two-account isolation.
4. **Acquire food observations:** direct OFF lookup/search with timeouts, raw-data quality warnings, import commands for IFCT and existing Apify datasets. Verify sodium grams-to-mg conversion, outlier quarantine, unknown-field preservation, idempotent imports, source metadata.
5. **Assess and replace:** pure assessment/alias matching, owned persisted findings, comparison eligibility and history, guide. Verify eggplant is not egg, almond milk is not dairy by substring, advisory concerns coexist with missing fields, different bases cannot compare, exclusions apply to all candidates, daily limit contribution is not a per-food allowance.
6. **Model adapters:** Fireworks DeepSeek V4.1 Flash label extraction (user-selected replacement for Gemini) and optional Jev preference scores, explicit missing-key/timeout fallback. Verify typed responses, candidate membership and total timeout behavior using mocked providers and bounded live checks when credentials exist.
7. **Integration:** run tests and lint, migrate real PostgreSQL, exercise registration-to-history through HTTP, and record a fresh verification summary. Preserve remaining source/model limitations in documentation.

Implementation stays in this task. Existing planning notes and any unrelated files are preserved.
