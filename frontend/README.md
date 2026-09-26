# SafeBitez frontend

Expo Router and React Native client for the FastAPI service in `../backend`. The mobile app and Expo web build share the same API client, account, profile, product, label, assessment, recommendation, and history flows.

## Run the backend

From the repository root, configure `backend/.env` from `backend/.env.example` and set the PostgreSQL password, a random JWT secret, and any provider keys you plan to use. Start PostgreSQL and the API:

```sh
docker compose --env-file backend/.env up --build -d
```

Run that command from the repository root. If your terminal is already in `backend/`, use:

```sh
docker compose --env-file .env -f ../compose.yaml up --build -d
```

Check `http://localhost:8000/health/ready` and open `http://localhost:8000/docs` for the API explorer. To load clearly marked synthetic products for a local demo, run `uv --directory backend run python -m app.importers demo` from the repository root.

## Run the app

```sh
cd frontend
npm install
cp .env.example .env
npm run start
```

Use `npm run web` for the browser, or start an Android/iOS development build. The default API URL is `http://localhost:8000` on web and iOS simulator and `http://10.0.2.2:8000` on the Android emulator. For a physical phone, set `EXPO_PUBLIC_API_URL` in `frontend/.env` to the computer's reachable LAN address, such as `http://192.168.1.20:8000`. Keep the phone and computer on the same network and allow the API port through the computer firewall.

Expo embeds `EXPO_PUBLIC_*` variables in the client bundle. Put only the backend's public base URL there, never database passwords, JWT signing secrets, or provider keys. The app stores the native access token with Expo SecureStore and uses browser local storage for the Expo web session.

## Connected journeys

- Create an account or sign in; load and save a backend-owned profile.
- Search product names/brands, scan a barcode with Expo Camera, or enter it manually.
- Upload a label photograph to the authenticated Fireworks extraction endpoint; review and correct the returned observations.
- Confirm the package declarations, submit an assessment using the current profile version, and render its findings.
- Review all ten supported nutrients, open the source record, and expand the raw-field/unit-conversion trace. Missing values stay unknown; changing the measurement basis clears the amounts for re-entry.
- Request eligible same-category replacements and reopen server-persisted assessment history.

Live product data can have missing fields and unverified source declarations. Label extraction requires user review. Recommendation results reflect only the candidate data and restrictions available in the backend catalog.

## Replacement tiers

Replacement results are shown as two clearly separated sections. **Verified candidates** passed the backend eligibility and verification checks. **Unverified candidates (confirm the label first)** failed a required verification step, and each row lists its `review_reasons`; the section carries a warning banner because a listed candidate is not a statement that it is safe. Confirm the current package and label before relying on any candidate.

## Cooked meals

`Check a cooked meal` (available from the scan tab, the assessment screen and `/dish`) submits a real ingredient list rather than a shown dish name:

- A dish name.
- Ingredient rows. Each row can search the IFCT reference foods (`GET /api/reference-foods?q=`) and pick one, or stay free text, plus optional grams.
- Cooking-note chips loaded from `GET /api/dishes/options`.
- A confirmation that every ingredient is listed and the dish has no packaged advisory panel.
- An optional portion size.

`POST /api/dishes/assess` returns ingredient matches, unmatched ingredients and an estimate the backend only produces when every ingredient has both a matched reference food and a gram amount; otherwise the estimate stays unavailable and its assumptions are shown. The assessment findings use the same renderer as the packaged-product assessment, so the status reason, `title`/`detail`/`next_step`/`affects` and collapsible `evidence` are read the same way. Nothing you do not list is inferred.

## Error handling

Every request has an `AbortController` timeout (15 seconds; 60 seconds for label extraction). A timeout surfaces as “The server did not respond in time.” rather than hanging. Error responses keep FastAPI's `detail` and add a stable `code`; the client reads both, joining a validation array into one message. Codes are `validation_error`, `unauthorized`, `forbidden`, `not_found`, `conflict`, `rate_limited`, `payload_too_large`, `unsupported_media_type`, `provider_unavailable`, `internal_error`, plus the frontend-origin `timeout` and `network` codes and the `profile_version_stale` conflict used to recover a stale profile save. Any `401` clears the stored token and routes the app back to the signed-out state.

## Local testing

`npm run typecheck` runs the TypeScript type checker and `npm run test` runs the Vitest suite (transport error normalisation, timeout aborting, base-URL resolution and the web localStorage session branch). The FastAPI service has its own dependencies and commands in `../backend/README.md`.
