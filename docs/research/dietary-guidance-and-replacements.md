# Personalized dietary guidance and replacement engine

> Status: superseded — kept for provenance; current behaviour lives in `backend/README.md`. Banner added 2026-09-26. The assessment and replacement engines it proposed are now implemented in `backend/app/services/`; the proposal text below is retained as design history.

## Confirmed product direction

The team has four people and a 24-hour build window. The client is React Native, primarily for mobile use with web support; the backend is FastAPI.

The user has requested broad illness coverage, end-to-end explanations of what not to consume, and replacements for unsuitable foods. The suggestion engine is a core feature, not a stretch goal.

The user has confirmed packaged-product swaps as the first recommendation surface. Dish questions remain in scope as proposed; dish/recipe recommendations are later work.

The user has confirmed onboarding through selected conditions/allergies plus optional clinician-provided limits. Lab-report interpretation is excluded from this first version.

PostgreSQL is the confirmed persistent database. FastAPI mediates client access to it.

User sign-in with saved personal profiles is a confirmed first-release requirement.

## Translate broad coverage into implementable behavior

Use two layers:

1. **Condition knowledge:** supported dietary guidance, its source, necessary context, and explicit limits on what is known.
2. **Personal restrictions:** specific ingredient exclusions, exposure concerns, nutrient targets, and preferences actually applicable to this person.

The assessment and replacement engines operate on the second layer. Condition knowledge helps explain and collect those restrictions; it does not silently create an exhaustive banned-food list from a diagnosis.

Many conditions share dietary considerations, so the reusable engine can serve profiles with different illnesses. Complete automatic guidance for “most illnesses” is not a realistic 24-hour claim. An unlisted condition can still use explicit recorded restrictions, while the app clearly states that no condition-specific pack has been assessed.

## Condition packs

Each pack contains a condition identifier and aliases, guidance items, required profile context, reusable rule references, explanation templates, sources, review status, and coverage limitations. Do not generate arbitrary disease rules at runtime.

For the five groups in the problem statement, proposed behavior is:

| Group | Supported behavior to define | What must not be inferred |
| --- | --- | --- |
| Food allergies | Specific allergen matches, ingredient aliases, declared exposure advisories, and preparer questions | That absence from a label proves absence from the food |
| Diabetes | Carbohydrate/portion awareness, relevant ingredient explanations, and comparisons using available nutrition | Individual glucose response, insulin dosing, or a universal prohibited-food list |
| Hypertension | Sodium information, portion calculations, comparisons, and any compatible recorded target | That the presence of a sodium-containing additive proves a high sodium dose |
| CKD | Explicitly applicable restrictions and supported ingredient/nutrient observations | Potassium, phosphorus, or protein limits from the diagnosis or creatinine alone |
| PCOS | Evidence-supported general guidance and independently recorded restrictions | A universal PCOS-specific list of forbidden foods |

[NIDDK CKD guidance](https://www.niddk.nih.gov/health-information/kidney-disease/chronic-kidney-disease-ckd/healthy-eating-adults-chronic-kidney-disease) supports individualizing kidney-related dietary needs. The [2023 international PCOS guideline](https://www.monash.edu/__data/assets/pdf_file/0003/3379521/Evidence-Based-Guidelines-2023.pdf) does not establish one superior diet composition for PCOS outcomes. These differences should shape product behavior rather than disappear behind a common red/green score.

For other illnesses, add a pack only when its guidance and required inputs are defined. A visible condition name is not evidence of full coverage. Report coverage per supported rule family, such as ingredient matching or sodium comparison, rather than merely counting illness names.

## Profile and onboarding

Proposed onboarding collects:

- Selected conditions and specific allergens; allow multiple selections.
- Explicit ingredient restrictions, including custom restrictions.
- Optional nutrient targets, their units and basis, and whether they came from a clinician or were entered for another reason.
- Applicable treatment context only when an active rule requires it. If the context is unknown, withhold that rule rather than guessing.
- Food preferences and dietary choices, kept distinct from clinical restrictions.
- Optional budget and brand/category preferences for replacements.

Do not ask users to type an entire clinical history. Use progressive questions linked to supported behavior. Do not convert daily targets into automatic per-meal limits without an explicit allocation.

Condition selection may activate sourced educational guidance. A quantitative clinical target needs its recorded basis. Custom restriction matching applies only to the restriction entered; it does not imply that guidance for the user's whole condition is complete.

## End-to-end product flow

1. **Personal guide:** show currently supported exclusions, recorded limits, ingredient names to look for, and questions to ask. Explain which selected conditions lack complete guidance.
2. **Food identification:** barcode lookup, catalog search, or label capture.
3. **Evidence confirmation:** show ingredients, advisory text, and nutrition observations for correction.
4. **Assessment:** produce personalized findings, including unresolved information.
5. **Action:** explain the relevant exclusion or consideration and whether quantity/context is needed.
6. **Replacements:** offer comparable candidates that have passed the supported checks and explain the measured improvement.
7. **Dish questions:** for uncertain preparation, provide targeted questions rather than a definitive food verdict.

Guide content, assessments, and replacement filtering must reuse the same versioned restriction data so that their advice does not contradict itself.

## Result model

Return separate findings rather than one overall “fit/unfit” boolean:

| Finding | Meaning | Replacement effect |
| --- | --- | --- |
| Recorded exclusion matched | Available evidence conflicts with an explicit ingredient restriction | Exclude candidates with that conflict |
| Declared possible exposure | Advisory text identifies an exposure concern | Apply the explicitly defined allergy-exposure policy; retain the advisory evidence |
| Compatible target exceeded | Valid nutrition amount exceeds a target with the same basis | Exclude candidates exceeding the same target |
| Nutrition/ingredient consideration | A supported concern merits comparison or portion awareness | Use it as a comparison objective, without converting it into a universal ban |
| Information missing or ambiguous | A supported restriction cannot be evaluated | Withhold a suitability claim and request the missing information |

An educational consideration is not a hard exclusion. This distinction is necessary for both explanations and recommendations.

## Replacement pipeline

Use a deterministic candidate pipeline for the prototype. Training a recommender is unnecessary; there is no validated preference/outcome dataset in the repository.

### 1. Retrieve comparable candidates

Start with the same food category and intended use: breakfast cereal for breakfast cereal, biscuit for biscuit, beverage for beverage. Use the small prepared catalog first. Do not require live API availability to produce the demo's replacements.

The source product's category may be missing. Let the user select it or return explicit inability to compare; do not guess silently. Product availability and prices remain unknown unless supplied by a supported source.

### 2. Check every candidate against the full profile

Evaluate candidate snapshots through the same assessment engine. Apply all active exclusions and targets, not just the issue that triggered the original warning.

Exclude known conflicts. Candidates with missing information needed for an active restriction cannot be presented as having passed that check. Unknown condition-specific coverage also remains visible; passing a limited rule set does not establish overall medical suitability.

Preference filters such as vegetarian choices are separate from clinical exclusions. If preferences leave no candidates, explain that rather than relaxing a clinical restriction.

### 3. Establish a valid improvement

Compare nutrient values on an equivalent basis: per 100 g, per 100 ml, or a compatible portion. A lower amount is not enough if it results solely from a smaller labeled serving.

For ingredient conflicts, explain the actual label difference and its limits. “Selected allergen is not declared in the available label information” is more precise than “allergy-safe.” Preparation and cross-contact may still be unresolved.

The objective must be known, such as lower sodium or a supported carbohydrate comparison. A lower nutrient amount is not universally better for every user. Consider fiber or other secondary attributes only when the supported profile rules and relevant data justify doing so.

### 4. Rank eligible improvements

Use transparent ordering:

1. Comparable intended use and no unresolved supported exclusion/target check.
2. Clear improvement on the triggering comparison objective.
3. Remaining applicable profile goals and tradeoffs.
4. User preferences and recorded budget, if available.

If objectives conflict, show the tradeoff or withhold a single “best” designation. Do not hide an unresolved conflict inside a weighted health score. Tie-break deterministically, for example by category match and product name, so demos are reproducible.

### 5. Explain the top two or three

Each suggestion should show product/category, reason for selection, equivalent-basis comparison, applicable checks performed, limitations, and source observation. Record the profile and rule-set version used.

Example with **synthetic demo values only**: product A has 600 mg sodium per 100 g; candidate B has 300 mg per 100 g. A valid comparison states that B has 50% less sodium on that basis. It does not state that B is clinically safe, locally stocked, or suitable for an unsupported restriction.

### 6. Handle no eligible replacement

Return an explicit reason: no comparable category, no improvement, known conflicts, or missing information. Offer a relevant next step such as scanning another product, confirming a missing panel, or asking a preparer about the recorded restriction.

Do not manufacture an alternative to make the interface look complete.

## Dishes and recipes

For the 24-hour build, packaged-product replacements are the confirmed primary recommendation surface. Retain curated dish questions, but defer dish and recipe replacement recommendations.

A recipe is a preparation specification, not evidence about an actual restaurant dish. An ingredient substitution must trigger reassessment of the complete recipe, including quantity-dependent findings when data exists. Do not treat an arbitrary missing ingredient as zero or infer nutrient totals from an incomplete recipe.

Large recipe-dataset ingestion can wait until the core replacement loop works. It does not automatically produce condition-appropriate or regionally practical alternatives.

## FastAPI contracts

Keep assessment and recommendation separate to make partial failures clear:

- `POST /api/profiles/guide`: owned saved profile ID/version → supported guidance, active restrictions, and coverage limitations.
- `POST /api/assessments`: owned saved profile ID/version + confirmed food snapshot + optional portion → persisted findings and unresolved checks.
- `POST /api/recommendations`: owned assessment ID + optional preferences → candidate comparisons or explicit no-match result using the saved profile/source snapshots.

Recommendation revalidates source and candidate observations server-side. Do not accept a frontend-provided “passed” flag as evidence. Store the catalog and rule set in PostgreSQL; version-controlled JSON can supply repeatable seed/import data. The backend exposes consistent models for both mobile and web.

## Team ownership and 24-hour priorities

- **Person A:** onboarding, personalized guide, assessment cards, and replacement comparison cards.
- **Person B:** FastAPI contracts, PostgreSQL models/migrations, product acquisition, guide/recommendation endpoints, and deployment.
- **Person C:** condition-pack content, restriction resolution, assessment rules, replacement filters/ranking, and expected-result cases.
- **Person D:** capture/upload, candidate label-data preparation, dish examples, and integration checks.

By hour four, demonstrate a saved product assessment through the app and backend. By hour eight, demonstrate one complete assessment-to-replacement path using saved candidates. Extend profile coverage and capture paths after these work.

Preparing candidate data is a dependency of recommendation quality. Assign candidate categories during the first two hours. Reduce category count before removing replacement filtering or unknown-data explanations.

## Acceptance cases

1. Same source food, two profiles: recommendations differ when their supported restrictions differ.
2. Candidate improves sodium but matches the selected allergy: it is excluded.
3. Candidate lacks nutrition required for an active target: it is not presented as having passed.
4. Candidate uses a smaller serving to appear better: compare on an equivalent basis.
5. Unsupported illness selected: its incomplete coverage is explicit, with custom recorded restrictions still usable.
6. CKD selected without an applicable potassium restriction: no potassium limit is invented.
7. PCOS selected: no universal forbidden-food list is generated.
8. Known conflict and unknown data coexist: both remain visible.
9. No eligible candidate: clear no-match explanation, with a practical next step.
10. Saved candidates are used during provider outage: provenance identifies them as saved observations.

## Decisions still open

1. Exact supported behavior and required inputs for each initial condition pack.
2. OCR choice and spending limit.
3. Target demo phones and standalone-build requirements.
4. Authentication implementation: proposed FastAPI email/password flow versus a managed identity provider.

This proposal broadens the architecture and makes replacements mandatory. It does not claim completed evidence review, clinical validation, or exhaustive illness coverage.

## Packaged-product implementation decisions

### Catalog preparation

Prepare three proposed comparison categories: biscuits/crackers, breakfast cereals, and savory packaged snacks. Categories can change to match products available to the team; their role is to provide comparable candidates, not to establish clinical categories.

Start with approximately five products per category. At least two candidates per demo source product must have enough relevant data for the intended profile. A nominal catalog of 25 products is less useful than 15 products that support a reproducible comparison.

Store:

| Field group | Required observations |
| --- | --- |
| Identity | Internal ID, barcode string if available, brand, name, variant, market |
| Comparison | Category ID, intended use, mass/volume basis, declared serving information |
| Ingredients | Original text, normalized concepts, nested ingredients, ambiguity notes |
| Allergy evidence | Separate ingredient/contains evidence and possible-exposure advisory text |
| Nutrition | Nutrient, amount, unit, basis, observation source; null for missing values |
| Provenance | Label/reference, source type, retrieval date, label observation date if known |
| Quality | Completeness per rule family, conflicts, and extraction/correction status |

Candidate records require the same evidence as the source product. A product name, front-of-pack claim, Nutri-Score, or FSSAI license cannot replace ingredient or nutrient evidence for personalized assessment.

### Data-source order

1. Use the prepared catalog for known demo items and fast local search.
2. Use live Open Food Facts lookup for other barcodes, with caching and partial-data handling.
3. Capture the actual pack when data is absent, incomplete, or inconsistent.
4. Let the user correct extracted text or manually enter missing observations.

IFCT can support later ingredient/dish work. Do not use raw ingredient composition to fill a branded product's missing sodium, potassium, or phosphorus without a validated recipe and quantities. A name-only barcode fallback may identify a candidate but cannot establish suitability.

For restrictions on nutrients often absent from the available label, the correct result may be no eligible comparison until additional data is supplied. Do not present an invented value or relax the restriction to obtain suggestions.

### Restriction types

Use a small set of explicit operations:

- `exclude_ingredient`: match a recorded ingredient or allergen exclusion.
- `evaluate_exposure_advisory`: preserve declared possible-exposure evidence and apply the defined policy.
- `compare_nutrient_target`: compare a valid amount against a compatible recorded target.
- `show_ingredient_consideration`: explain a supported ingredient/alias without assuming a prohibited food.
- `compare_nutrient_goal`: compare candidates on a supported, explicit objective without inventing a hard limit.
- `require_information`: identify a missing observation needed by another operation.

Each restriction specifies applicability, required observations, finding type, evidence source, and behavior if information is missing. A daily target cannot serve as a product-level pass/fail cutoff without an explicit relevant allocation.

### Candidate eligibility versus ranking

Keep two steps distinct:

**Eligibility:** comparable category/use; no known supported exclusion or compatible hard-target conflict; required information for those checks is present. If the condition coverage itself is incomplete, that limitation accompanies every result.

**Ranking:** among eligible candidates, require a demonstrable improvement on the selected objective. Then consider supported secondary goals and recorded preferences. Candidates with conflicting goals need an explained tradeoff, not a universal best-food claim.

If a profile has several findings, prioritize recorded exclusions in the display while retaining the full list. Where no specific comparison objective exists, request the goal rather than assuming that less carbohydrate, more protein, or lower calories is always appropriate.

### Recommendation card

Proposed card fields:

- Product name and category.
- Reason for suggesting it.
- The relevant source-versus-candidate comparison on an equivalent basis.
- Ingredient/advisory observations relevant to recorded exclusions.
- Checks performed and unresolved coverage limitations.
- Label/data source and whether the observation is saved or newly captured.
- A “View label evidence” action.

Do not show price, local availability, or a purchase button unless a supported source provides that information.

### Screen flow

Use five primary views, with extraction review as part of the product-input flow:

1. Profile setup/edit.
2. Personal guide and scan/search entry.
3. Product input and label correction.
4. Personalized findings.
5. Replacement list and candidate evidence.

The active profile remains visible on findings and replacements. Editing it invalidates those results and triggers reassessment. Changing portion invalidates quantity-based comparisons. Late responses from a previous profile must not overwrite the current profile's results.

### Contract consistency

Assessment and recommendations must identify the profile snapshot, source-product snapshot, and rule-set version used. Recommendations use the referenced assessment's saved snapshots. The backend assigns provenance classes to user-entered or corrected observations; a client-supplied flag cannot turn them into verified catalog data.

Record clear response reasons when suggestions are unavailable: unsupported category, no objective, no relevant improvement, known profile conflict, insufficient candidate information, or unavailable provider/catalog.

### Three replacement demonstrations

1. **Selected allergy:** source has a declared match; candidates with the same match are removed, and remaining label evidence and limitations are shown.
2. **Recorded sodium comparison goal:** candidates are compared on the same basis, and a measured reduction is explained.
3. **Multiple restrictions:** a candidate improves the comparison goal but matches another exclusion, so it is removed.

Include a fourth negative case if time allows: no eligible candidate because a required nutrient is missing. This demonstrates how the product handles the real-world information limitations in the problem statement.

## Confirmed onboarding: proposed field behavior

Keep the first onboarding short, with optional detail available afterwards:

| Step | Fields | Behavior |
| --- | --- | --- |
| 1. Conditions | Search/select multiple conditions; unlisted-condition entry | Show supported pack coverage; unlisted entry does not create new medical rules |
| 2. Allergies and exclusions | Specific allergens; optional explicit ingredient exclusions | Resolve only supported names/aliases; request confirmation for ambiguous terms |
| 3. Clinician-provided limits | Optional nutrient, amount, unit, basis, and origin | Store exactly as entered after validation; never claim the app verified the prescription |
| 4. Preferences | Optional dietary preference and category/budget preferences | Use for candidate selection, separately from clinical restrictions |
| 5. Review | Active restrictions and coverage gaps | Let the user correct the profile before first assessment |

Use supported selectable nutrient/unit combinations rather than interpreting arbitrary free-text clinical instructions. Preserve unknown context explicitly. Do not activate a new medical restriction by reading an unrecognized note.

Proposed profile fields are: `profile_id`, `profile_version`, `conditions`, `allergens`, `ingredient_exclusions`, `nutrient_limits`, `comparison_goals`, and `preferences`. Resolved rule applicability and coverage limitations are backend outputs, not client assertions.

For each recorded nutrient limit, store nutrient, positive amount, unit, basis, user-reported clinician origin, and optional note. The UI must distinguish user-reported origin from clinician verification. Invalid units or malformed values require correction, not silent conversion or clamping.

### Daily limits versus product decisions

When a daily target and a compatible portion value exist, display the portion's contribution to that target. Without a consumption log, do not display a remaining daily allowance or infer what else the user has eaten.

When an explicit compatible meal/portion limit exists, compare against that basis. Do not split a daily limit into three meals automatically.

Illustration using **synthetic values only**: a user records a daily sodium target of 2,000 mg. A product portion provides 300 mg. The app can show “15% of your recorded daily target.” It cannot infer that the product fits the user's remaining intake today. These numbers are not suggested clinical targets.

### No clinician limit supplied

Continue supported ingredient/allergen assessment and evidence-backed educational guidance. Show nutrition amounts and supported comparisons where an objective is defined. Do not fill the absent limit with an invented personalized prescription.

A missing clinical target is distinct from missing product data. The former may prevent a personalized threshold verdict; the latter may prevent even calculating a relevant amount. Explain each gap with its own next step.

### Conditions with incomplete guidance

Show which supported rule families apply, which context is missing, and which aspects have no implemented guidance. Do not produce a complete-looking guide by inserting generic prohibitions for every illness.

The personal guide should group recorded exclusions, recorded limits, supported awareness information, and outstanding checks. Recommendations reuse those resolved restrictions; they must not infer additional disease rules independently.

## PostgreSQL storage proposal

### Application boundary

React Native / Expo web → FastAPI → PostgreSQL.

FastAPI handles validation, identity/profile access, product acquisition, assessment, and recommendation. The client does not hold database credentials or execute database queries. OCR and product providers remain backend integrations.

Proposed backend tooling: SQLAlchemy 2.x for models and sessions, Alembic for migrations, and a PostgreSQL driver supported by the chosen deployment. Use one request-scoped database session. Do not share a session between concurrent requests or hold a transaction open while waiting for an external OCR/product API.

References: [SQLAlchemy session documentation](https://docs.sqlalchemy.org/en/20/orm/session_basics.html), [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html).

### Compact first-release schema

Use relational columns for identifiers, references, versions, category lookup, and timestamps. Use validated JSONB payloads for structured fields that are still evolving. [PostgreSQL JSONB documentation](https://www.postgresql.org/docs/current/datatype-json.html) describes its storage and indexing behavior; application validation is still needed to enforce the payload schema.

| Table | Relational columns | Main structured payload |
| --- | --- | --- |
| `users` | UUID, unique canonicalized email, created timestamp; password hash if using FastAPI-owned authentication | Account metadata; dietary data remains in profiles |
| `profiles` | UUID, user reference, version, display name, created/updated timestamps | Conditions, specific allergens, exclusions, clinician limits, comparison goals, preferences |
| `products` | UUID, nullable barcode string, variant/market key, name, brand, category ID, version, timestamps | Raw/normalized ingredients, separate advisory statements, nutrition observations, portions, source records, completeness/conflicts |
| `ingredient_dictionary` | Canonical ingredient ID, canonical name, version | Supported aliases, language tags, relationships, ambiguity notes |
| `condition_packs` | Stable condition ID, name, version, status | Guidance, required context, referenced rule versions, coverage limits, sources |
| `rules` | Stable rule ID, version, type, enabled/review status | Applicability, supported predicate parameters, required fields, explanation templates, sources |
| `dishes` | UUID, name, variant, version | Possible ingredients, preparer questions, source/limitations |
| `assessments` | UUID, user reference, profile reference, source product reference when present, created timestamp | Exact profile/product snapshots, portion, rule manifest, findings, unresolved checks |
| `recommendation_runs` | UUID, assessment reference, created timestamp | Candidate snapshots, eligible/rejected reasons, comparisons, ranking/objective, final suggestions |

This is a draft schema for the confirmed sign-in requirement. `profiles.user_id` identifies ownership; assessment ownership must agree with its profile's owner. Recommendations inherit ownership through their assessment. Products, ingredient dictionaries, rules, condition packs, and dishes are shared catalog data. A managed identity provider would change the user identity fields and remove application-managed password storage.

A rule's predicate payload selects supported application operations. It is configuration, not executable Python/SQL loaded from the database. Unknown operation types cannot be activated.

### Product lookup and caching

Seed the comparison catalog into `products`. Search the small catalog by name/brand and category. For an uncached barcode, fetch the provider outside a database transaction, validate the returned observations, then persist them with provenance.

Keep a barcode as text so leading zeroes survive. Product identity includes variant/market context where available; do not assume one barcode record resolves every formulation conflict. Define unique keys around the actual observation identity used by the catalog.

When the captured label disagrees with a shared record, create an assessment-specific corrected snapshot. Do not overwrite the shared catalog from an unreviewed user correction. Later reviewed edits can update the catalog version.

Start with indexes for barcode/identity lookup, category, profile history, and assessment history. The prepared catalog is small enough for simple name search. Add advanced search or JSONB indexes only when an actual query needs them.

### Reproducible assessments and recommendations

Store snapshots because profile and catalog records can change. An old result must retain the facts it used, including the rule IDs/versions and relevant evidence. Foreign keys alone cannot reproduce a result after the referenced row is edited.

New profile edits increment its version; new product edits increment the product version. Rules retain versioned rows with unique `(rule_id, version)` identity. A condition-pack version pins the rule versions it references.

Persist one assessment with its complete findings in a short transaction. Recommendation then links to that assessment and uses its snapshots and rule manifest. If the recommendation engine cannot execute an older rule version, return that reassessment is required rather than silently mixing versions.

Use an owned assessment ID plus optional preferences for the persisted recommendation flow. Candidate product versions and comparison snapshots belong in the recommendation result. A frontend change to profile or portion requires a new assessment. FastAPI determines ownership from authentication, not a client-provided user ID.

### Label images and OCR observations

Persist confirmed text, extracted observations, ambiguities, and source metadata in the assessment snapshot. Raw label photos can remain transient for the demo under the existing proposal. If retained photo evidence is required, add a bounded `label_assets` table with MIME type, size, checksum, and PostgreSQL `BYTEA` content; this is an optional storage decision, not an automatic retention policy.

Keep raw image bytes out of product JSONB and assessment response payloads. The five-MB image limit still applies to uploads. A product image/reference URL and an uploaded photo are different source types.

### Migrations, seeding, and deployment

Person B owns the first migration and database models. Person C supplies validated rule/alias/condition-pack seed records; Person D supplies product/dish records. Imports are repeatable and update only explicitly versioned seed records, not user corrections or assessment history.

Create the initial schema and load the small comparison catalog during the first two hours. Prove a FastAPI read/write against PostgreSQL early. By hour four, a persisted assessment should reach the app; by hour eight, a persisted recommendation should reference that assessment.

Use the same migrations for local and hosted databases. FastAPI's database URL stays in backend configuration. A phone reaches FastAPI, which reaches PostgreSQL; the phone does not connect to the database.

If PostgreSQL is temporarily unavailable, display a persistence/service error rather than imply a saved result. External-provider failure is separate: previously stored product observations can still support assessment while the database is available.

## Sign-in and saved-profile proposal

### Recommended first implementation

Use email/password sign-up and sign-in in FastAPI, with hashed passwords in PostgreSQL and expiring bearer access tokens. This keeps authentication in the selected backend. [FastAPI's security guide](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) describes password hashing and JWT verification; it recommends Argon2 and demonstrates `pwdlib` and `PyJWT`.

Alternative: a managed identity provider such as [Supabase Auth](https://supabase.com/docs/guides/auth). This can manage authentication while FastAPI validates identity and owns dietary logic. Choose it if the team already knows it or wants its account-recovery/email flows. This provider choice is still a proposal, not an accepted service dependency.

For a FastAPI-owned prototype, propose 30-minute access tokens, with subject set to the immutable user UUID. Put no conditions, allergies, or clinical limits in the token; those remain in the owned profile. Verify token signature, accepted algorithm, and expiry for protected requests.

Use [Expo SecureStore](https://docs.expo.dev/versions/latest/sdk/securestore/) for native token storage. The web client can keep the short-lived token in application memory and ask for sign-in again after reload/expiry. This is a deliberately small first-release session flow. A persistent web/refresh-token session is a separate design if required.

### User journey

1. Sign up or sign in.
2. Load the owned saved profile, or open onboarding if none exists.
3. Save profile edits and increment its version.
4. Scan/search and create an owned assessment.
5. Request recommendations for that assessment.
6. Reopen previous assessments and comparisons from owned history.
7. Sign out and clear the current client's credentials and profile state.

The first UI supports one personal profile per account; the schema can accommodate more without introducing household-management screens now.

### Proposed account/profile API

| Endpoint | Purpose |
| --- | --- |
| `POST /api/auth/register` | Create an email/password account if using FastAPI-owned authentication |
| `POST /api/auth/login` | Return a short-lived access token |
| `GET /api/auth/me` | Return the authenticated account identity |
| `GET /api/profiles/me` | Return the current personal profile or explicit onboarding-needed state |
| `PUT /api/profiles/me` | Create/update the owned profile with version handling |
| `GET /api/assessments` | Return the authenticated account's paginated history |
| `GET /api/assessments/{assessment_id}` | Return one owned result |
| `POST /api/recommendations` | Take an owned assessment ID and return/store eligible comparisons |

`POST /api/assessments` takes the saved profile ID/version, confirmed product observations, and optional portion. FastAPI loads and verifies the owned profile and rejects a stale version rather than silently using changed restrictions. The guide endpoint likewise uses the owned profile.

No protected route accepts a request's user ID as authority. Profile, history, assessment-detail, and recommendation queries must be scoped to the authenticated owner. Another account's object ID must not reveal that object's contents. Public product search remains separate from owned dietary data.

### Updated handoffs and checks

Person B owns registration/login, current-user validation, account/profile persistence, and owner-scoped queries. Person A owns sign-in screens, session state, onboarding/resume behavior, and expired-session handling. Person D checks the native and browser flows. Person C's assessment function continues to accept a resolved profile snapshot and needs no authentication logic.

Use two test accounts for the first integration. Verify saved profile reload after sign-in, version changes, expired-session behavior, and inability to open the other account's assessments/recommendations. These are necessary checks for the requested saved-profile behavior.

Target sign-in/profile integration by hour six alongside the source-product flow; the earlier hour-four assessment checkpoint can use an internal test account while the frontend sign-in screens are completed. Aim for the owned assessment-to-replacement path by hour eight. These remain planning checkpoints subject to actual team experience.

## Researched model assistance

The user has allowed LLMs for parsing/recommendations and identified TypeSafe Jev. Proposed division: a multimodal model extracts label photos to editable observations; Python applies restriction rules and computes comparable nutrient values; Jev optionally scores flavor/use preferences among already eligible improvements; templates or a grounded generative model explain the recorded findings.

Preserve the replacement gate before any semantic scoring. Neither a model's preference score nor its confidence may overcome an allergen conflict, incompatible comparison basis, or unknown field required for eligibility. A flavor tie-breaker is separate from recorded nutrient objectives. API failure must retain deterministic replacements and their reasons.

Keep Jev behind the existing recommendation endpoint, with server-owned candidate IDs and minimal preference context. Store ranking method, model/rubric versions, accepted scores, duration, and fallback reason in recommendation metadata. No separate model microservice or additional database is needed.

The [TypeSafe integration proposal](typesafe-jev-integration-plan.md) includes a concrete typed request and evaluation plan. The [competitor and FitFork review](competitor-and-fitfork-research.md) identifies reusable source patterns and dataset limitations. These were proposed changes to the architecture; both were subsequently implemented in the backend (see [`../../backend/README.md`](../../backend/README.md)).
