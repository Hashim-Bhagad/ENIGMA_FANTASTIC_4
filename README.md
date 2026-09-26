# SafeBitez

SafeBitez is an Expo/React Native app and a FastAPI/PostgreSQL backend that turn recorded
allergies and conditions into explicit checks on food labels, with evidence and unknowns.

## Run it

Start the backend from the repository root after configuring `backend/.env`:

```sh
docker compose --env-file backend/.env up --build -d
```

API docs are at `http://localhost:8000/docs`; start the app from `frontend/`.

## Documentation

- [Documentation index](docs/README.md) — design history, research, and verification evidence.
- [Backend README](backend/README.md) — API surface, behaviours, and checks.
- [Frontend README](frontend/README.md) — Expo setup and the public API URL.

## Safety stance

Inference stays advisory: deterministic code runs the restriction checks and arithmetic,
replacements split into a verified tier and an unverified `needs_review` tier that are never
merged, and unknown data stays explicitly unknown rather than guessed.
