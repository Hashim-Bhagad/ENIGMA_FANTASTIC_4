# Documentation index

This directory holds the prototype's design history and verification evidence.
Current, code-verified behaviour lives in [`../backend/README.md`](../backend/README.md);
this index is a map of everything else.

## Current behaviour

- [Backend README](../backend/README.md) — API surface, behaviours, verification, and CI.
- [Frontend README](../frontend/README.md) — Expo setup and the public API URL.
- [Root README](../README.md) — one-page orientation.

## Guides and scripts

- [Backend mentoring script](backend-mentoring-script.md) — a walkthrough of the backend for a
  mentor or demo audience, refreshed 2026-09-26 against the current implementation.

## Verification evidence

- [Source and importer verification (2026-09-26)](source-verification/adapter-validation-2026-09-26.md)
  — bounded probes of IFCT, Open Food Facts, Apify, and Barcode List.
- [Reported barcode audit (8909081007163)](source-verification/barcode-8909081007163.md).
- [Initial HTTP probes](source-verification/initial-http-probes.json).
- Provider live checks are recorded beside their scripts:
  [`backend/scripts/provider-live-verification.md`](../backend/scripts/provider-live-verification.md)
  and [`backend/scripts/runtime-api-smoke.md`](../backend/scripts/runtime-api-smoke.md).

## Research and planning history

These documents drove the build. Each carries a dated status banner; they are kept for
provenance and are **not** the current contract.

- [Plan review and implementation direction](research/project-plan-review.md) — superseded.
- [Personalized dietary guidance and replacement engine](research/dietary-guidance-and-replacements.md)
  — superseded; its engines are implemented under `backend/app/services/`.
- [TypeSafe Jev integration proposal](research/typesafe-jev-integration-plan.md) — superseded; the
  adapter shipped and passed a bounded live check on 2026-09-26.
- [Comparable apps and FitFork reuse assessment](research/competitor-and-fitfork-research.md) —
  historical notes.
- [Hidden-ingredient problem notes](research/hidden-ingredient-risk-app-notes.md) — historical notes.
- [Product catalog options](research/product-catalogue-options.md) — historical notes; catalog
  acquisition plan and source limits.

## Archive

- [Backend foundation implementation plan](archive/backend-implementation-plan.md) — executed;
  retained for provenance.
