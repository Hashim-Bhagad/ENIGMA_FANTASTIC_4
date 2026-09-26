# Food source and importer verification — 2026-09-26

## What was checked

The checks below use bounded read-only HTTP requests, except for the IFCT database import, which upserts the source's reference-food rows. No Apify actor was started. The Open Food Facts request used one public barcode. No credentials or authorization headers were printed.

| Source or path | Result | What it establishes |
|---|---|---|
| IFCT 2017 `compositions/index.csv` | HTTP 200; 1,154,715 bytes | The public composition CSV is reachable. It has 542 unique food codes locally. |
| IFCT 2017 `representations/index.csv` | HTTP 200; 4,194 bytes | The unit/factor metadata used by the importer is reachable. |
| IFCT local normalization | 542 rows, 542 distinct codes; each of the nine mapped source fields has 542 finite values | Sodium, potassium, phosphorus, protein, fat, fiber, available carbohydrate, free sugars, and energy normalize with the recorded representation factors. Available carbohydrate and free sugars remain distinct from label total carbohydrate and total sugars. |
| IFCT sample `A001` | sodium 2.7 mg, potassium 433 mg, phosphorus 374 mg, energy 356.118547 kcal per 100 g edible portion | The importer applies the metadata factor and converts kJ to kcal in code. This is a reference-food composition, not a branded-product value. |
| IFCT PostgreSQL import | Ran twice; both runs reported 542 imported and 0 packaged products | The primary-key upsert is repeatable. The healthy `dietary-risk` PostgreSQL container was used. |
| Open Food Facts product API, barcode `3017620422003` | HTTP 200 through the implemented adapter | A real product record normalized at a stated `100g` basis; source sodium `0.0428 g` became `42.8 mg`. The product's ingredient/advisory completeness remains false. |
| Supplied Apify run `svCjf5DtStMudLn88` | Run lookup HTTP 200; status `SUCCEEDED`; dataset `h5n0pJBId8vHhHMNT`; one item | `ApifyReader.run_dataset` and `.items` work against the supplied completed run. No paid run was launched. |
| Supplied flattened Open Food Facts Apify item | One Bhujia record, barcode `8904004400052`; `sodium_100g` is `788`, with no unit or nutrition basis metadata | The adapter stores the raw source record and advisory, but leaves the normalized basis and sodium unknown. It does not guess that `788` means mg or reinterpret the outlier. |
| Apify Food.com actor metadata | HTTP 200; actor identified as `parseforge/food-com-scraper` | The actor listing is reachable. The input-schema endpoint checked returned HTTP 404, and no completed Food.com output was supplied or fetched. Actual recipe extraction and any nutrition fields remain unvalidated. |
| Barcode-list page | HTTP 200 in the initial probe; response is HTML | It is a web page, not a verified structured product API. It should not be a nutrition or ingredient authority without a separately validated extraction path. |

The composition file's SHA-256 is `8d27bacfd6a73454971b8c73ccc06420ee236fcdae78b26d60442175e4a0aa22`. Repository license metadata identifies the transcription as AGPL-3.0-or-later; rights for the source book are separate. Review those terms before redistribution or deployment.

## Adapter behavior

- Open Food Facts uses its product v3 endpoint for barcode lookup and the separately exercised legacy search endpoint for text search. Product results are normalized only when the source states a compatible `100g` or `100ml` basis. Its nutrient values in `*_100g` are treated according to the source's gram representation; sodium, potassium, and phosphorus convert to milligrams. Non-finite or implausible measurements become unknown with a warning.
- Open Food Facts `allergens_tags` may combine evidence from different parts of a contributed record, so they are retained as `reported_allergens`, separate from ingredient-derived `declared_allergens` and `traces_tags`-derived `precautionary_allergens`. None of these source fields proves that the physical package was completely reviewed.
- The flattened Apify Open Food Facts export does not provide reliable units or basis fields. Its nutrient values therefore remain unknown. The complete raw item is kept in the product's raw record for traceability.
- IFCT data imports to reference foods only. It is not used to fill missing packaged-product labels or infer a recipe's nutrition.
- Recipe rows are staged as `pending_schema_validation`; staging does not imply validated recipe fields, nutrition, or suitability.

## Verification commands and test evidence

From `backend/`:

```sh
./.venv/bin/pytest -q tests/test_sources.py
./.venv/bin/ruff check app/integrations/off.py app/integrations/apify.py app/importers.py
./.venv/bin/python -m app.importers ifct --directory data/raw/ifct2017
```

Source normalization tests: **5 passed**. Ruff: **all checks passed**. The IFCT importer was run twice against PostgreSQL and reported **542** on both runs. Live adapter checks returned one existing Apify item and one Open Food Facts barcode result as described above.

## References

- [IFCT 2017 transcription repository](https://github.com/nodef/ifct2017)
- [Open Food Facts API documentation](https://openfoodfacts.github.io/openfoodfacts-server/api/)
- [Apify actor run metadata API](https://docs.apify.com/api/v2/actor-run-get)
- [Apify dataset items API](https://docs.apify.com/api/v2/dataset-items-get)
- [Food.com scraper actor listing](https://apify.com/parseforge/food-com-scraper)
- [Open Food Facts scraper actor listing](https://apify.com/gentle_cloud/open-food-facts-scraper)
