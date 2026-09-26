# Local API runtime smoke check

This check targets the running Docker Compose stack and uses a generated throwaway account plus synthetic foods. It does not call Fireworks, Jev, Open Food Facts, or Apify.

Start the services from the repository root:

```sh
docker compose --env-file backend/.env up -d --build
```

If your terminal is already in `backend/`, use `docker compose --env-file .env -f ../compose.yaml up -d --build` instead.

Run the real HTTP flow from the repository root (the host must be able to reach `127.0.0.1:8000` and PostgreSQL on `127.0.0.1:5433`):

```sh
UV_CACHE_DIR=/tmp/ingredient-risk-uv-cache UV_LINK_MODE=copy \
  uv --directory backend run python scripts/runtime_api_smoke.py
```

The script inserts one synthetic replacement product, registers two generated accounts, saves one profile, assesses a synthetic `maida` product against a wheat allergy, asks for a replacement, checks persisted assessment and recommendation history, and confirms another account receives `404` for the assessment. It prints generated record IDs but never prints tokens, passwords, or `.env` values.

The check leaves its throwaway accounts and synthetic products in the local database so the responses can be inspected. Use a disposable local database if the records should not persist.
