# Provider live verification

Checked on 2026-09-26 through the production `ModelAssist` methods using the configured Fireworks and TypeSafe credentials. Keys and authorization headers were not printed. Only generated synthetic food data was sent.

- **Fireworks label extraction:** The full production image plus JSON Schema request returned a validated `FoodObservation` from `accounts/fireworks/models/deepseek-v4p1-flash`. The generated image contained `INGREDIENTS: RICE FLOUR, MAIDA, SALT`; extraction returned `RICE FLOUR, MAIDA, SALT`. With no product name or nutrition panel visible, the adapter used its explicit unidentified-product placeholder, left the nutrition basis unknown, retained all 10 nutrient fields as unknown, and marked the label for confirmation. The live verifier caps generated output at 512 tokens and limits the call to 18 seconds. Normal extraction defaults to a 2048-token cap, configurable through `LABEL_MAX_TOKENS` from 128 to 4096.
- **TypeSafe Jev preference ranking:** The production `rank_preferences` method returned `deterministic_with_jev_preference_ties` from `jev-1.13.0` for two eligible, synthetic candidates tied on their comparison value. Both candidates received validated score/confidence/probability data; the candidates stayed in their deterministic priority group.
- **Docs:** Fireworks’ model page lists the exact V4.1 model as Ready and image-input supported; its vision guide documents Chat Completions with base64 image data URLs; its structured-output guide documents the `json_schema` response format. TypeSafe’s quick start documents `POST /v1/systemone`, the `model/state/questions` request, and typed Score answers with confidence/probabilities.

Re-run explicitly from the repository root with:

```sh
UV_CACHE_DIR=/tmp/ingredient-risk-uv-cache UV_LINK_MODE=copy \
  uv --directory backend run python scripts/provider_live_verify.py --live
```

Use `--provider fireworks` or `--provider typesafe` to run just one adapter. Each call uses synthetic input and may incur a small provider usage charge. The successful image check confirms basic extraction and schema compatibility for this synthetic case; it does not establish reading accuracy on real package photographs.

Primary references: [DeepSeek V4.1 Flash model page](https://fireworks.ai/models/deepseek-ai/deepseek-v4p1-flash), [Fireworks vision guide](https://docs.fireworks.ai/guides/querying-vision-language-models), [Fireworks structured outputs](https://docs.fireworks.ai/structured-responses/structured-response-formatting), [TypeSafe quick start](https://docs.typesafe.ai/introduction/quickstart).
