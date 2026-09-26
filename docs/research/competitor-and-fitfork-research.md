# Comparable apps and FitFork reuse assessment

Research date: 26 September 2026.

Scope: official product/support documentation for comparable apps, and read-only inspection of `/home/hashim/FitFork`. This is a planning and reuse assessment, not an implementation or a hands-on benchmark of the commercial apps.

## Recommendation

Combine Fig's restriction-specific explanations, Spoonful's scan-to-swap flow, FoodSwitch's comparable-product approach, Yuka's quick summary/history, and Cronometer's target editing and missing-food recovery. Adapt selected FitFork backend and client-state patterns. Build a new packaged-product evidence and replacement pipeline using FastAPI and PostgreSQL, with React Native screens.

LLMs are useful for label extraction, query interpretation, and grounded explanations. TypeSafe Jev is a proposed addition for bounded category/preference judgments and ranking already assessed replacement candidates. Keep source observations, clinical rule applicability, numeric comparisons, and final candidate eligibility explicit and reproducible. See [the detailed Jev integration proposal](/home/hashim/ENIGMA_FANTASTIC_4/typesafe-jev-integration-plan.md).

## Competitor findings

The original assertion that ingredient apps only handle lifestyle choices is too broad. Fig and Spoonful explicitly address allergies and other dietary restrictions. A better project position is personalized Indian packaged-food decisions, explicit recorded clinician limits, traceable label evidence, and clear missing-data behavior. This is a proposed differentiation, not a verified claim that no competitor does it.

| App | Documented behavior | Pattern to adapt | Important distinction |
| --- | --- | --- | --- |
| Fig | Personalized restrictions, ingredient/allergen matching, product scan/search, ingredient-specific explanations | Multiple restrictions in one profile; tap a finding to understand its personal relevance | Its no-match indicator refers to available declarations, not proof of overall safety |
| Spoonful | Multiple diets, scanning, swaps, search, dietitian notes, history, and favorites | Make “Find replacements” the next action from a concern; use candidate cards and saved products | Their diet labels and catalog cannot substitute for our evidence or clinical review |
| Yuka | Product analysis, similar-product recommendations, scan history; search/offline/preferences are documented premium capabilities | Quick summary followed by details, history, and visible alternatives | General product quality is different from matching an individual's clinical restrictions |
| FoodSwitch | Barcode nutrition profiles, similar-product swaps, nutrient-focused switches, missing-product photo submission; official page lists India | Same-category comparisons, explicit nutrient objective, photo recovery, missing nutrient shown distinctly | Its FAQ says its general healthier choices may need more specific advice for particular diseases |
| Cronometer | Custom nutrient targets/maximum thresholds, barcode/manual entry, custom-food creation | Editable clinician-provided target fields; recover from an unknown barcode without a dead end | Its consumption diary is a different task from scanning a product; scans must not become intake automatically |

Sources: [Fig ingredient evaluation](https://foodisgood.com/support/how-does-fig-evaluate-ingredients/), [Fig status explanations](https://foodisgood.com/support/what-do-the-green-yellow-and-red-colors-mean/), [Spoonful product overview](https://spoonfulapp.com/), [Spoonful feature comparison](https://support.spoonfulapp.com/kb/spoonful-basic-vs-spoonful-unlimited-plans/), [Yuka application](https://yuka.io/en/app/), [FoodSwitch official overview/FAQ](https://www.georgeinstitute.org/our-research/research-projects/the-foodswitch-app), [Cronometer targets](https://support.cronometer.com/hc/en-us/articles/360060170532-Nutrient-Targets), [Cronometer custom-food creation](https://support.cronometer.com/hc/en-us/articles/360019866351-Mobile-Create-a-Custom-Food), [Cronometer scanner flow](https://cronometer.com/blog/how-to-use-the-barcode-scanner/).

The primary pages document these capabilities; they do not establish observed speed, accuracy, usability ratings, or Indian catalog coverage. No numerical UX scores are assigned without hands-on testing. Older support articles remain useful for patterns but may not describe the newest screen layouts.

## Feature decisions for our app

| Pattern | Proposed implementation | Priority |
| --- | --- | --- |
| Combined restriction profile | Saved conditions, specific allergies/exclusions, optional clinician limits, separate preferences | Core, already requested |
| Ingredient drill-down | Raw phrase, canonical match, rule/source, personal relevance, uncertainty | Core |
| Actionable swap | Findings screen opens two or three assessed candidates | Core |
| Equivalent-basis comparison | Compare per 100 g/ml or compatible portions; show original units | Core |
| Barcode miss recovery | Capture ingredients/advisories/nutrition; validate and correct observations | Core |
| History | Reopen owned assessment snapshots and linked recommendations | Core saved-account flow |
| Text plus status icon/color | Distinguish recorded conflict, consideration, and missing information | Core presentation |
| Favorites/shopping list | Save a replacement for later, always reassess against current profile/version | Optional after core flow works |
| Report a data issue | Record corrected observation without overwriting shared catalog | Useful; first release can keep assessment-local corrections |
| Ingredient-change alerts | Compare observed product versions and surface relevant differences | Later; depends on reliable updates and notification infrastructure |
| Full offline assessment | Local catalog/rules and synchronization | Later; server caching alone is not client offline support |

Fig documents ingredient-change alerts for saved products. We can first show observation dates and version changes when reopening a result; complete proactive alerts require more infrastructure. [Fig Ingredient Alerts](https://foodisgood.com/support/how-can-i-be-alerted-if-ingredients-in-my-favorite-products-change/)

The result should always retain known concerns alongside unknown fields. A green color must not hide an unreadable advisory panel. A star or generic quality score must not be labeled an FSSAI rating or personalized medical verdict.

## FitFork: what is actually present

FitFork's source is a FastAPI backend with MongoDB persistence and a Vite/React DOM frontend. It includes registration/login, saved fitness-oriented profiles, recipe text search with dietary/allergen filters, Gemini meal generation, chat, and Google Calendar integration.

The inspected search implementation is MongoDB text search plus filters. The checked-in code does not implement the vector-search pipeline claimed in some documentation. Treat the code as the capability reference. [Search implementation](/home/hashim/FitFork/backend/app/db/mongodb.py:146)

The saved screenshots provide design references. They were not treated as proof of live screen behavior; the profile reference uses sliders while the inspected page implements browser form inputs.

## Code reuse map

| FitFork source | Reuse value | Required adaptation |
| --- | --- | --- |
| [Authentication helpers](/home/hashim/FitFork/backend/app/api/auth.py:25) | Password verification, token creation, current-user dependency structure | PostgreSQL repository, immutable user-ID subject, deliberate token policy, required configured signing secret |
| [Account/profile endpoints](/home/hashim/FitFork/backend/app/api/endpoints.py:45) | Sign-up, login, current-user/profile route structure | Our route contracts, owner-scoped profiles, conditions/limits, profile versioning |
| [Pydantic schemas](/home/hashim/FitFork/backend/app/models/schemas.py:5) | Typed request/response organization | Replace fitness/recipe schemas with observations, restrictions, units/bases, findings, and recommendation schemas |
| [Frontend API client](/home/hashim/FitFork/frontend/src/api.js:5) | Central API access and error handling | Expo configuration, native token storage/navigation, web adapter, image uploads, our endpoint names |
| [Authentication context](/home/hashim/FitFork/frontend/src/context/AuthContext.jsx:6) | Sign-in state and saved-profile loading flow | Remove browser-only storage; clear old account state before loading another profile; handle profile-load failure explicitly |
| [Profile page](/home/hashim/FitFork/frontend/src/pages/ProfilePage.jsx:1) | Selection chips, editable fields, save/loading/error states | Rebuild with React Native components; remove required body metrics and fitness-goal assumptions |
| [Search page](/home/hashim/FitFork/frontend/src/pages/SearchPage.jsx:1) | Query, loading, empty-result, and card flow | Packaged-product categories/results; do not require height to search; use consumer-readable errors |
| [Gemini service](/home/hashim/FitFork/backend/app/services/meal_planner.py:13) | Backend model client and structured-response orchestration | Bounded extraction/explanation/replacement tasks, explicit schemas, candidate/evidence checks, timeout/retry/fallback behavior |
| [Import script](/home/hashim/FitFork/backend/scripts/import_recipes_mongo.py:21) | Batch-import structure | New product source/schema, PostgreSQL writes, validation, repeatable imports, preserved provenance |

No inspected file is a drop-in module for the new full stack. Authentication helpers and service organization can save work; the MongoDB persistence and DOM UI need adaptation. Recipes and fitness-target computation are not the selected first recommendation surface.

## Required corrections before adopting FitFork behavior

### Restriction matching

The recipe filter uses `$in` for selected diet tags, so matching any one tag is enough. Our engine must evaluate every supported applicable restriction. Missing allergen metadata must not be treated as a completed check. [Filter source](/home/hashim/FitFork/backend/app/db/mongodb.py:157)

The enrichment notebook uses substring matching for allergen detection. An isolated reproduction of that matching logic produced:

| Input | Current matches | Issue |
| --- | --- | --- |
| `almond milk` | `dairy`, `tree_nuts` | “milk” alone wrongly asserts dairy origin for this phrase |
| `rice flour` | `wheat` | “flour” alone wrongly asserts wheat origin |
| `eggplant` | `eggs` | Substring creates a false match |
| `sesame seeds` | none | Sesame is absent from this dictionary despite being offered in the profile UI |

The profile UI uses `tree nuts`, while enrichment uses `tree_nuts`; the direct exclusion filter does not normalize that mismatch. Use canonical IDs, phrase/context matching, and ambiguity handling. [Notebook, cell 6](/home/hashim/FitFork/data/data_enriching.ipynb)

### Generated recommendations

FitFork passes recipe titles, IDs, and macros to Gemini, then checks the returned JSON against Pydantic models. The inspected path does not verify every generated recipe ID, ingredient claim, or nutrient value against retrieved observations. A valid-shaped response is not that verification. [Generation path](/home/hashim/FitFork/backend/app/services/meal_planner.py:36)

For our app, the model can choose IDs from assessed candidates. FastAPI checks membership, candidate eligibility, and claimed comparisons before returning suggestions. An empty eligible set returns a no-match explanation, even if a model proposes an attractive replacement.

### Authentication and packaging

The auth helper has a default development signing secret. Adopt the flow with required configured signing credentials rather than carrying that fallback into a hosted app. [Auth configuration](/home/hashim/FitFork/backend/app/api/auth.py:11)

The frontend client uses `localStorage`, `window.location`, and Vite environment variables. These browser APIs require native/web adapters. [API client](/home/hashim/FitFork/frontend/src/api.js:3)

The model service imports `google.genai`, but `google-genai` is not explicitly listed in the inspected requirements. Reconcile and pin dependencies during implementation; this review does not establish runtime installability. [Requirements](/home/hashim/FitFork/backend/requirements.txt:1)

## FitFork data audit

Counts below were computed from the local raw files, not copied from README claims.

| File | Actual contents | Useful reuse | Unsuitable use |
| --- | --- | --- | --- |
| [train.json](/home/hashim/FitFork/data/raw/train.json) | 39,774 entries; keys `id`, `cuisine`, `ingredients`; 20 cuisine labels | Ingredient vocabulary examples, phrase/alias test cases, later cuisine work | Barcode lookup, branded-product nutrition, condition-to-food clinical evidence |
| [epi_r.csv](/home/hashim/FitFork/data/raw/epi_r.csv) | 20,052 rows and 680 columns, including title/rating/calories/protein/fat/sodium and tags | Later recipe-category exploration after provenance and quality checks | Personalized packaged-product suitability or verified allergen absence |
| [data_enriching.ipynb](/home/hashim/FitFork/data/data_enriching.ipynb) | Cuisine classifier and recipe enrichment/allergen heuristics | Pipeline organization and test cases, after correction | Automatically trustworthy clinical labels or nutrient measurements |

In `epi_r.csv`, 4,119 rows lack a finite sodium value and 4,117 lack a finite calories value. The maximum raw sodium value is 27,675,110 and the maximum calories value is 30,111,218. These are extreme outliers requiring investigation; the CSV itself does not provide an explicit serving/100-g basis field. It contains neither a full ingredient-list column nor barcode identifiers.

The notebook creates empty ingredient/allergen lists for the Epicurious rows, estimates carbohydrate by subtraction, estimates fiber as a fraction of that estimate, writes zero for sugar and saturated fat, and marks nutrition valid. Preserve absent values as unknown and estimates as estimates; do not adopt these outputs as measured product facts. [Notebook, cells 4 and 6](/home/hashim/FitFork/data/data_enriching.ipynb)

The import script expects `data/processed/final_recipes_enriched.jsonl`; that file is absent from this checkout. The notebook also references `food_com_cleaned.jsonl`, which is absent from the inspected inventory. The documented 226,000-plus ready-to-query corpus is therefore not established by the local files. [Import path](/home/hashim/FitFork/backend/scripts/import_recipes_mongo.py:15)

The README claims MIT licensing, but the referenced root `LICENSE` file is absent. Dataset provenance/license documents were not found in the inspected raw-data directory. Record ownership and dataset source terms before copying third-party material; a code-license statement does not establish the dataset's terms. This is an unresolved provenance finding, not a conclusion that the team cannot reuse its own work.

## Proposed LLM integration

The user has explicitly allowed considering LLMs for parsing and recommendations. FitFork's Gemini client is a reasonable adapter starting point; provider/model choice and budget remain open.

| Task | Model input | Structured output | Backend check |
| --- | --- | --- | --- |
| Label parsing | Captured label image or OCR text | Raw phrases, ingredients/nested ingredients, advisory statements, nutrient values/units/basis, missing/ambiguous fields | Shape, numeric/unit consistency, declared evidence, user correction before assessment |
| Query interpretation | User search plus supported category/goal vocabulary | Category, preference, comparison objective | Recognized fields only; no new clinical restrictions silently activated |
| Ingredient interpretation | Raw phrase plus curated canonical concepts | Candidate concept IDs, supporting phrase, ambiguity | Dictionary membership; unresolved aliases remain unconfirmed |
| Replacement selection | Eligible candidate IDs, verified comparisons, preferences | Ordered candidate IDs and evidence references | Membership, no duplicates, full restriction checks, supported improvement |
| Plain-language explanation | Existing findings and source IDs | Explanation associated with finding/evidence IDs | No new facts/thresholds; numeric claims assembled or checked in code |
| Clinical content preparation | Approved guidance sources | Draft pack content with citations and limitations | Evidence review before activation; no arbitrary runtime disease prescriptions |

[Gemini structured outputs](https://ai.google.dev/gemini-api/docs/structured-output) support JSON-schema-shaped responses, and [image understanding](https://ai.google.dev/gemini-api/docs/image-understanding) supports image input. These capabilities do not establish measured label accuracy or clinical validity.

For the first build, prioritize one model-backed label parser. Make replacement selection/explanation a second bounded call only if it improves on transparent sorting/templates. Avoid a broad autonomous agent that searches arbitrary products and declares them suitable.

### TypeSafe Jev: researched fit

The user clarified that “jev” refers to TypeSafe's flagship System One model. Its typed Choice, Score, and Noul outputs suit bounded decisions. We propose one optional preference-scoring call after complete restriction checks and numeric comparisons, with backend-controlled ordering. [TypeSafe introduction](https://docs.typesafe.ai/introduction)

Jev currently accepts text/JSON, so label-photo extraction remains a separate multimodal model/OCR task. [Supported state](https://docs.typesafe.ai/concepts/state) The vendor's documented limitations include arithmetic and generation; neither nutrient calculations nor free-form dietary guidance belongs in Jev. [Known limitations](https://docs.typesafe.ai/model-jaggedness/jev-1.13)

Its confidence statistic concerns the model's answer distribution; it is not patient risk or source completeness. Use it to fall back on uncertain preference/category decisions. [Confidence](https://docs.typesafe.ai/confidence) API access and latency have not been tested. The [integration proposal](/home/hashim/ENIGMA_FANTASTIC_4/typesafe-jev-integration-plan.md) specifies backend boundaries, a sample request, persistence, evaluation, and the 24-hour sequence.

Treat label text and retrieved pages as data, including any text that resembles model instructions. Missing or unreadable values stay null. If the model times out or produces unsupported output, retain editable manual input and deterministic assessment/recommendation behavior.

Store parser/model/prompt version and extracted-versus-corrected observations with provenance. Send only the restrictions/candidate facts needed by the task, not account credentials or unrelated clinical history. Provider/model configuration stays in FastAPI.

## End-to-end build recommendation

1. Adapt FitFork's auth/current-user/profile flow to PostgreSQL and our condition/restriction schema.
2. Create the shared React Native profile, guide, scan/search, correction, findings, and replacement views.
3. Seed comparable Indian packaged products with actual label observations.
4. Implement canonical ingredient matching and complete restriction evaluation.
5. Add live barcode lookup and model-assisted label parsing behind the same observation contract.
6. Filter and compare replacement candidates; optionally use the model to interpret preferences and explain checked comparisons.
7. Persist owned assessment/recommendation snapshots and expose history.
8. Add favorites or additional dish questions only after that flow works.

Keep general fitness macro targets, large recipe ingestion, weekly generated meal plans, and calendar integration outside this packaged-product release. They do not resolve the chosen core data/rule dependencies.

## What “end to end” must demonstrate

- New account → saved profile → app restart/sign-in → same owned profile.
- Known barcode → sourced observations → personalized finding → checked replacement → saved history.
- Unknown/incomplete barcode → image/text extraction → user correction → assessment → candidate comparisons.
- Multiple restrictions → an attractive but conflicting candidate is rejected.
- Missing relevant information → explicit unknown/no-match behavior.
- Model/provider failure → usable manual/saved-data path.
- Profile edit → current reassessment; prior history retains its original snapshot.
- Two accounts → isolated profiles and history.
- Mobile capture → backend upload → PostgreSQL persistence, with web entry/upload fallback.

## Verification performed and remaining limits

Read backend/client source, documentation, dependency manifests, raw datasets, relevant notebook cells, and a saved profile design reference. Parsed 14 backend Python files for syntax without importing/executing the application; all parsed. Computed raw-data counts/missing values and reproduced four allergen-matching cases independently from the notebook dictionary.

No commercial app was installed/tested, no FitFork database or external model was contacted, no runtime/end-to-end behavior was established, and no FitFork source was changed. Live checks belong to implementation once the design is settled.

Reviewed TypeSafe's introduction, state, primitives/API, confidence, models, Python asynchronous client, composite-scoring pattern, and documented Jev limitations. This was documentation research; no TypeSafe API request was made and no performance claim was verified independently.
