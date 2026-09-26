# PS 3 — Plan review and proposed hackathon implementation direction

Reviewed: 26 September 2026.

> Status: superseded — kept for provenance; current behaviour lives in `backend/README.md`. Banner added 2026-09-26; this was a working planning document, not an approved implementation specification.

## Confirmed context

- The target is a hackathon demo or college prototype.
- The build window is 24 hours.
- Four people will build an application whose primary use is mobile, with web support.
- The backend will use FastAPI.
- The frontend will use React Native; the user has confirmed this is intentional for mobile and web use. Expo is the proposed tooling.
- The user wants broad illness coverage, a personalized explanation of what to avoid or limit, and a replacement suggestion engine as a core feature.
- Packaged-product swaps are the confirmed first recommendation surface; dish/recipe replacements are deferred.
- Onboarding uses selected conditions/allergies plus optional clinician-provided limits. Lab-report interpretation is excluded from the first version.
- PostgreSQL is the confirmed persistent database.
- User sign-in and saved personal profiles are confirmed first-release requirements.
- LLM assistance for parsing/recommendations is explicitly allowed. The user identified TypeSafe Jev for investigation; its use below is a researched proposal, not an implemented dependency.
- At review time the repository contained only research notes; the implementation has since been built (see the banner above).
- The original feature requests cover packaged-food search, barcode/label scanning, dish questions, recommendations, and FSSAI information.
- Expo tooling, target demo phones, individual skills, condition scope, and available budget have not yet been confirmed.

## Overall assessment

The notes are a useful research inventory. Their strongest ideas are ingredient aliases, personal relevance, label-photo fallback, plain-language explanations, and explicit handling of incomplete information. These directly address the problem statement.

They do not yet define a buildable decision-support system. The missing pieces are the first release boundary, evidence-backed rules, data contracts, uncertainty behavior, acceptance criteria, and ownership of each implementation step. Integrating more databases will not resolve these gaps by itself.

Proposed product promise: **Show which declared ingredients or nutrition values conflict with the person's recorded restrictions, explain the evidence, and identify what still needs checking.**

Here, “hidden” means aliases, compound ingredients, overlooked advisory statements, and misunderstood label claims. The prototype cannot discover an undeclared ingredient, adulterant, or unrecorded cross-contact from a barcode or photograph.

## Corrections to the existing notes

| Existing idea | Required correction | Effect on implementation |
| --- | --- | --- |
| Structured Open Food Facts data is “verified” | Structured formatting does not establish accuracy. OFF explicitly gives no assurance of accuracy or completeness. | Display source, completeness, and label-check status separately. |
| Map every additive to a disease warning | An additive name alone does not establish a clinically meaningful risk or nutrient dose. | Add only supported, narrowly scoped rules; leave unsupported mappings inactive. |
| “Sodium nitrite causes blood pressure spikes” | This specific explanation is unsupported in the notes. | Remove it; assess reported sodium against a recorded target when available. |
| Sugar-free means low diabetes risk | Total carbohydrate and portion information also matter. | Detect relevant aliases and show carbohydrate per selected portion; avoid predicting glucose response. |
| CKD automatically requires stricter potassium restrictions | Restrictions are individual and can change with treatment and clinical assessment. | Activate potassium/phosphorus restrictions only when explicitly recorded; do not infer limits from creatinine alone. |
| “Fine” or “safe” if nothing matched | Missing label data and unobserved preparation details remain possible. | Use “No matching concern found in the available information,” with unresolved checks visible. |
| Dish name determines ingredients | Recipes and kitchen practices vary. | Store possible ingredients and questions, not claims about the actual plate. |
| Scanning counts toward daily intake | A scan is not consumption. | Defer tracking; a later food log must record consumed portions explicitly. |
| Recommended intake tables supply clinical budgets | General reference values do not prescribe an individual's restrictions. | Distinguish reference information from a person’s recorded clinician-provided targets. |

Clinical context: [CDC carbohydrate guidance](https://www.cdc.gov/diabetes/healthy-eating/carb-counting-manage-blood-sugar.html) explains the relevance of total carbohydrates and starches. [NIDDK CKD guidance](https://www.niddk.nih.gov/health-information/kidney-disease/chronic-kidney-disease-ckd/healthy-eating-adults-chronic-kidney-disease) describes individualized potassium, phosphorus, protein, and sodium needs. These are grounding sources, not completed clinical validation of this app.

Source corrections: [OFF API documentation](https://openfoodfacts.github.io/openfoodfacts-server/api/) describes contributor data limitations, currently recommends v3 for new integrations, and documents request limits and identification requirements. The notes’ v2 examples should therefore be revisited during integration. Search and product lookup need separate endpoint decisions.

The existing FSSAI distinction is useful: licensing and establishment hygiene information are separate from personal dietary suitability. [FSSAI describes hygiene ratings for establishments](https://southregion.fssai.gov.in/pdf/hr.pdf). A missing verification result must be shown as unavailable, rather than evidence that a license is invalid.

## Three feasible approaches

| Approach | Strength | Cost or limitation |
| --- | --- | --- |
| **A. Evidence-backed rules with assisted extraction — recommended** | Findings are reproducible, traceable, and easy to demonstrate. | Requires a small curated vocabulary and explicit rules. |
| B. LLM-led interpretation and recommendations | Can handle varied text and produce fluent explanations quickly. | Harder to prevent invented ingredients, inconsistent decisions, and unsupported medical claims. |
| C. Broad multi-API nutrition platform | More search and recommendation breadth. | Integration work and inconsistent data consume time before the core decision flow works. |

Start with A. Use a multimodal model or OCR for editable label extraction. TypeSafe Jev can optionally make bounded category/preference judgments and help order already eligible improvements. Python makes findings from confirmed data and performs numerical comparisons. Explanation templates remain sufficient; a generative model may reword grounded findings. Models must not change restrictions, thresholds, or missing-data status. See [the researched model integration plan](typesafe-jev-integration-plan.md) and [competitor/FitFork assessment](competitor-and-fitfork-research.md).

## Proposed first-release scope

Proposed for the confirmed 24-hour window, subject to team capacity:

1. One active profile supporting multiple selected restrictions and allergies.
2. Search over a small local packaged-food catalog, plus live barcode lookup.
3. Barcode entry as a fallback to camera scanning.
4. Ingredient, allergen-advisory, and nutrition-panel photo capture with editable extracted text.
5. Alias normalization and personalized findings with evidence snippets.
6. A curated dish-question flow covering common local dishes.
7. A replacement engine with a small same-category comparison catalog, assessed against all supported profile restrictions.
8. A personalized guide summarizing supported exclusions, limits, and questions to ask.

Plan broad coverage through reusable dietary restrictions, condition-specific evidence packs, and explicit clinician-provided restrictions. See [the detailed guidance and replacement proposal](dietary-guidance-and-replacements.md). Selecting an illness must not imply that complete guidance for that illness exists.

Updated planning quantities: approximately 15–25 packaged items arranged into a few comparison categories, 5 dishes, and a small evidence-backed rule set. Include at least two candidate alternatives for each product used in a replacement demo. These are preparation targets, not coverage claims. Rule count follows supported evidence and scenarios; it must not grow merely to populate a disease dropdown.

For this time limit, build generic ingredient-exclusion, exposure-advisory, nutrient-comparison, and unknown-data behavior. Activate condition-specific behavior only when the relevant evidence and profile inputs exist. Do not invent a universal carbohydrate cutoff. Ingredient aliases are explanatory findings; they are not automatic prohibitions for diabetes.

Time-box camera and OCR integration. Use a familiar or readily available extractor with a text-correction step. If photo extraction cannot be made reliable within its allotted window, ship editable label-text input and clearly describe OCR as incomplete. Photo upload alone is not label scanning.

Defer household management, consumption tracking, crowdsourced publication, lab-driven threshold changes, large recipe ingestion, and automated FSSAI scraping. A manual FSSAI lookup link can be included with a clear “not checked” state.

## Proposed architecture and responsibilities

Use one application and one backend, or a framework with equivalent server routes. Keep the following responsibilities separate within that codebase; microservices are unnecessary for the prototype.

| Module | Responsibility | Output |
| --- | --- | --- |
| Profile | Record selected allergies, restrictions, and any supplied targets | Structured profile with target provenance |
| Product acquisition | Query local catalog and OFF; handle misses, rate limits, and timeouts | Product candidate or explicit lookup failure |
| Label extraction | Extract panel text and values; let the user correct them | Raw and corrected observations |
| Normalization | Resolve aliases, nested ingredients, label statements, and nutrient units | Normalized facts with traceable evidence |
| Assessment | Evaluate versioned rules against profile and available facts | Findings plus unresolved checks |
| Presentation | Explain personal relevance, source, and next action | Result cards |
| Dish questions | Match curated possible ingredients to selected restrictions | Questions for the preparer |
| Alternatives | Apply all supported profile filters and compare eligible items | Bounded suggestions with limitations |
| Optional semantic ranking | Ask Jev narrowly defined preference questions about eligible candidates | Secondary preference order or deterministic fallback |

Use the selected React Native frontend and FastAPI backend. Mobile camera scanning is central to the primary app, while the web version shares profile, search, correction, and result flows. [ML Kit text recognition documentation](https://developers.google.com/ml-kit/vision/text-recognition/v2) provides Android/iOS entry points; a native integration would need separate Expo compatibility checks and would not automatically provide browser OCR.

### Stack direction after team clarification

The user has confirmed React Native for a primarily mobile app with web support. Recommend Expo + TypeScript for the shared client, with Expo Router if the team is familiar with it. [Expo's official web guide](https://docs.expo.dev/workflow/web/) explains React Native Web support. This is one frontend codebase with small platform-specific capture/upload adapters.

Keep client capture and backend extraction separate. Mobile and web clients supply a label photo or text; FastAPI receives it and returns editable extraction observations. The upload adapter converts the mobile photo URI or browser image bytes into the agreed multipart payload; sending a device-local file path alone will not give the backend access to that photo.

Recommend `expo-camera` for mobile photo capture and barcode detection. [Expo Camera documentation](https://docs.expo.dev/versions/latest/sdk/camera/) lists it as included in Expo Go and documents web-specific behavior. Check scanning on an actual demo phone early. Web must retain barcode entry and image upload if its camera/scanner path is unavailable. Debounce repeated barcode events so the same product does not trigger multiple simultaneous lookups.

For the 24-hour demonstration, propose running the mobile app in Expo Go when the selected dependencies support it, plus a browser-accessible web build. Expo Go is a demo runtime, not a standalone shipped app. A standalone installable build is an additional deliverable if the hackathon requires one; do not make app-store publication part of this schedule.

Provide a phone-reachable API base URL. A phone's `localhost` points to the phone, not the teammate's laptop. Use a reachable development address during local testing and an HTTPS backend for the hosted demo. Confirm the phone-to-backend connection before adding live scanning.

Use PostgreSQL as the persistent source of truth for accounts, owned profiles, products, ingredient aliases, condition packs, rules, dish data, and owned assessment/recommendation history. JSON files can be seed/import inputs, while runtime reads use the database. Product lookup results can be cached there with source and retrieval timestamps. See the database and sign-in sections in [the detailed proposal](dietary-guidance-and-replacements.md).

FastAPI validates request and response shapes. External product/OCR calls stay behind the backend. Keep provider keys there if any are required. If frontend and backend use different origins, configure the frontend origin explicitly as described in [FastAPI's CORS guide](https://fastapi.tiangolo.com/tutorial/cors/).

### Proposed API boundary

This is a draft contract, to settle alongside profile fields and finding types before coding.

| Endpoint | Input | Output / behavior |
| --- | --- | --- |
| `GET /api/health` | None | Backend readiness; no dependence on external providers |
| `GET /api/products?q=...` | Search text | Matches from the prepared local catalog |
| `GET /api/products/barcode/{barcode}` | Barcode string | Local or live product observation, with source and missing fields |
| `POST /api/labels/extract` | Label image and panel type | Extracted observations, original text, and ambiguities; no dietary verdict |
| `POST /api/assessments` | Owned saved profile ID/version, confirmed product observations, optional portion | Persisted findings, evidence, unresolved checks, and rule manifest |
| `POST /api/recommendations` | Owned assessment ID and optional preferences | Reassessed candidates using the saved snapshots, comparative reasons, and explicit no-match behavior |
| `POST /api/profiles/guide` | Owned saved profile ID/version | Supported exclusions, limits, condition coverage, and questions to ask |
| `GET /api/dishes` | Optional search text | Curated dish names and variants |
| `POST /api/dishes/{dish_id}/questions` | Supported profile restrictions | Relevant preparer questions and composition limitations |

Send the confirmed product snapshot to assessment rather than only a product ID. This lets the same engine assess corrected OCR, manual input, and catalog observations without overwriting shared data. Backend validation and normalization still apply to that snapshot.

A barcode miss returns an explicit not-found response that the frontend routes to label entry. Provider unavailability is a different error. A partial product record may still be assessed and return known findings plus unknowns. Missing nutrition is not a transport error.

For label uploads, [FastAPI's file-upload guide](https://fastapi.tiangolo.com/tutorial/request-files/) documents multipart uploads and `UploadFile`. The image endpoint and JSON assessment endpoint are separate. Proposed limits are one JPEG/PNG image up to 5 MB per extraction request, transient processing, and no permanent image storage. Select the OCR implementation after confirming deployment support and budget.

## Packaged-food flow

1. Select a profile; its identity remains visible throughout the result.
2. Scan or enter a barcode, or search the local catalog.
3. Confirm product identity, variant, and region where available.
4. Inspect whether relevant ingredient, advisory, and nutrient data exists.
5. If the product is missing, incomplete, or disagrees with the physical pack, offer label capture or manual entry. OCR is also a fallback for partial records, not only total lookup misses.
6. Show the extracted ingredients, advisory statements, values, units, and nutrient basis for correction before assessment.
7. Evaluate the recorded restrictions and return findings and unresolved checks.
8. Offer an eligible alternative only when its relevant data has been assessed.

A catalog match and a captured pack can disagree. Preserve the observations independently, explain the mismatch, and request confirmation. Do not silently merge conflicting ingredients or invent a complete current label.

## Minimum data contracts

**Profile:** identifier, display name, specific allergies, selected conditions, explicit restrictions, optional nutrient targets, target units and basis, target origin, and profile version. Avoid collecting birth dates, medications, or lab reports until a supported feature needs them.

**Product:** barcode as a string, name, variant, region, raw ingredient text, normalized ingredient concepts, separate “contains” and “may contain” statements, nutrition observations, portion information, source reference, retrieval timestamp, observation timestamp if known, and completeness by field. Retrieval time does not prove the label is current.

**Nutrition observation:** nutrient, amount, unit, basis (per 100 g, per 100 ml, or stated serving), serving mass/volume when known, and source. Missing values are null, never zero. Keep salt and sodium distinct and preserve the original observation if converting.

**Ingredient match:** raw phrase, canonical concept, match method, evidence location, and ambiguity. Normalize synonyms carefully; a token occurring inside a different word is not a confirmed match. Keep compound ingredients and advisory language intact. Marketing negations such as “peanut-free” must not be interpreted as “contains peanut.”

**Rule:** identifier, version, supported profile trigger, matching predicate, finding type, required fields, action template, evidence reference, review status, and behavior when evidence is insufficient. Unreviewed prototype rules must be identifiable and must not be described as clinically validated.

**Assessment:** profile version, product snapshot, rule-set version, findings, evidence snippets, missing fields, unresolved ambiguities, and data-source status. Retain enough provenance to reproduce a result.

## Decision and uncertainty behavior

Use individual findings rather than an opaque numerical “health score.” Proposed finding types:

- **Declared allergen match:** the ingredient or contains statement matches a selected allergy.
- **Possible allergen exposure:** advisory text identifies potential exposure; it is not proof of actual presence.
- **Recorded target exceeded:** a supported amount and basis exceed a compatible target recorded in the profile.
- **Ingredient awareness:** a supported alias was detected, but its quantity or individual effect cannot be determined.
- **Needs checking:** relevant data is absent, unreadable, contradictory, or ambiguous.

Positive evidence can produce a finding even when other fields are missing. Missing data blocks reassurance, not the display of known concerns. Several finding types may coexist.

Cross-contact is a separate concern from declared ingredients. [FDA allergy guidance](https://www.fda.gov/food/nutrition-food-labeling-and-critical-foods/food-allergies) explains this distinction. Its US labeling rules are not being adopted as Indian regulatory requirements.

Keep extraction reliability, source status, and rule support separate. Do not display a made-up “92% clinically safe” confidence score. User correction means the text was checked by that user, not that the product received medical verification.

Nutrient calculation: when a valid per-100-g value and gram portion exist, portion amount = value × portion grams / 100. Do not convert volume to mass without density information, infer quantities from ingredient order, or compare a single product to an unrecorded daily consumption total.

Multi-condition handling: evaluate every supported restriction. An alternative cannot cancel an allergy finding because it has lower sodium. Record conflicting targets explicitly; do not average them or invent a clinical resolution.

## Dish mode

Store dish name, regional variants, possible ingredients, common additions, and preparer questions. Examples should say “Some versions use…” rather than “This dish contains…” unless actual ingredients have been provided.

For an allergy, questions may cover the ingredient, sauces/toppings, and shared utensils or cooking equipment. For sodium awareness, ask about added salt, stock, premixed seasoning, and sauces. A dish name alone does not support a numeric sodium estimate.

If the preparer cannot confirm, retain the unknown state. Suggested recipe ingredients cannot establish what is in a wedding buffet serving.

## Recommendation boundary

The replacement engine is now a required first-release feature. Prefer a small comparison catalog over general claims that recipes “benefit” a disease. Reassess each candidate using the same rules and all selected restrictions. Compare equivalent nutrition bases and explain the measured reason, such as lower sodium per 100 g. The detailed guidance/replacement proposal defines filtering, ranking, and fallback behavior.

Do not describe alternatives as safe for allergies solely because no match was found. Exclude candidates with known conflicts; withhold or clearly qualify candidates with unresolved relevant data. If no eligible suggestion exists, say so rather than manufacturing one.

## Suggested build order and exit criteria

| Stage | Concrete output | Exit criterion |
| --- | --- | --- |
| 1. Lock scope | Confirmed scenarios, supported profile fields, and deferred features | Each proposed feature has a demo purpose and owner |
| 2. Prepare evidence and fixtures | Small alias table, supported rules, labeled product/dish examples | Every active rule has a source and defined unknown behavior |
| 3. Build assessment core | Profile + product snapshot → structured findings | Known matches, ambiguous data, and unit handling behave as specified |
| 4. Build a complete manual-input flow | Profile → confirmed label text → result | A judge can finish a meaningful assessment without external services |
| 5. Add acquisition | Barcode lookup, camera input, OCR corrections | Lookup miss, partial record, poor image, and timeout all have usable fallbacks |
| 6. Add dish mode and eligible swaps | Curated questions and comparisons | Dish assumptions are labeled; alternatives respect every supported restriction |
| 7. Rehearse demo | Reliable mobile/browser flow with representative scenarios | Demo survives network loss using visibly labeled saved examples |

Build the manual-input vertical flow before depending on camera and live data. The team size is now confirmed as four; actual member names and strengths still need mapping to the proposed roles below.

### Proposed ownership for four people

| Owner | Primary responsibility | First handoff |
| --- | --- | --- |
| Person A — frontend | Shared mobile/web profile, product search/input, correction form, and result cards | Render agreed response examples while the API is being built |
| Person B — backend | FastAPI contracts, PostgreSQL models/migrations, validation, product lookup, cache, and deployment | Serve the seeded product catalog and assessment route |
| Person C — rules and evidence | Alias mapping, assessment function, supported rules, and expected-result cases | Provide a pure Python assessment function using the agreed models |
| Person D — capture and integration | Mobile barcode/photo path, web fallbacks, OCR feasibility, curated dish examples, and end-to-end checks | Prove capture on the intended phone and provide two real label examples |

Person B owns shared backend models; Person A owns shared frontend types and navigation. Person C owns assessment internals; Person D owns capture components and platform upload adapters, and hands OCR integration to Person B through the extraction contract. Assign file boundaries before work starts so two people do not change shared contracts independently.

At the two-hour checkpoint, freeze the first contract examples. By hour four, connect a saved product through the frontend and backend to a real assessment. Use contract-shaped fixtures only for screens whose backend is still pending, and replace them before the final demo. Integrate again at hours eight and fourteen; do not leave the first integration to the last few hours.

Deploy a minimal reachable frontend/backend early, then check deployment again after image extraction is introduced. Native OCR dependencies can behave differently on a host than on a teammate's laptop. Keep the local prepared catalog available when live lookup fails; identify its saved-snapshot status in the UI.

### Proposed 24-hour checkpoints

These are elapsed-time checkpoints for the team, not person-hour estimates. They assume familiarity with the chosen stack and must be adjusted when team capacity is known.

| Time | Focus | Checkpoint |
| --- | --- | --- |
| Hours 0–2 | Confirm scope, three demo stories, schema, and small evidence-backed rule set | No unresolved ambiguity in what each demo finding means |
| Hours 2–5 | Implement normalization and assessment against saved examples | Alias, allergen, sodium, and missing-data findings work |
| Hours 5–10 | Connect profile, manual product input/search, result UI, and first saved-candidate replacements | Complete assessment-to-replacement flow; first replacement handoff by hour eight |
| Hours 10–14 | Live barcode lookup and time-boxed camera/OCR integration | Misses and incomplete records reach editable input; extraction limitations remain visible |
| Hours 14–17 | Refine personalized guide/replacements and add five dish checklists | All use the same supported profile restrictions |
| Hours 17–21 | Evaluate representative cases and fix failures | Known false reassurance and unit/matching errors are resolved |
| Hours 21–24 | Freeze features, rehearse, and prepare submission | Saved examples work with unavailable network; claims match implemented behavior |

If behind at hour 10, reduce catalog breadth and dish count while preserving one complete assessment-to-replacement flow. If behind at hour 14, stop adding external integrations. In the final three hours, fix only failures affecting the demo or result correctness.

### Three proposed demo stories

1. A sugar-free product includes a refined-flour alias: show the matched label phrase and carbohydrate information if available, without predicting a glucose spike.
2. A product declares a selected allergen, or carries a relevant advisory statement: distinguish these findings and show their source text.
3. A buffet dish has variable ingredients: generate specific preparer questions and keep its actual composition unknown until confirmed.

Use explicitly labeled sample profiles and saved snapshots. Any artificial nutrient values must be identified as synthetic; actual product claims require the corresponding label evidence.

## Required evaluation scenarios

Prepare approximately 30–50 labeled cases sized to the supported rules. Prefer an independent reviewer to check expected results. Clinical review is an additional requirement before extending claims to real-user clinical use; a hackathon test set is not that validation.

- Exact allergen, alias, compound ingredient, advisory statement, and negated marketing phrase.
- Allergy and intolerance represented as different profile inputs.
- Refined-flour/carbohydrate awareness without invented nutrient quantities or glucose predictions.
- Missing sodium, missing portion, per-serving versus per-100-g basis, and incompatible units.
- OCR decimal loss, wrong units, truncated ingredient list, and contradictory label/catalog data.
- Unknown ingredient without an invented explanation.
- Multi-condition candidate that improves one nutrient but conflicts with an allergy.
- Dish variant and unknown preparation/cross-contact information.
- Scan without consumption, so no daily intake changes.
- API unavailable, barcode unknown, and camera permission denied.

Track rule correctness, false reassurance cases, relevant-field extraction accuracy, correction frequency, demo coverage, and latency. Report results against the curated dataset; do not generalize them to all Indian products.

## Next planning decisions

Work through these in order:

1. Confirm Expo/demo distribution requirements, map the four members to responsibilities, and settle spending limit.
2. Exact condition-pack behavior, supported restriction inputs, and end-to-end demo scenarios within the requested broad coverage.
3. Profile restrictions and meaning of each result state.
4. Rule inventory, evidence sources, and who reviews each rule.
5. Screen flow, data schema, and API contracts.
6. Implementation tasks, owners, dependencies, and time estimates.

Preserve the original research notes as background. Promote proposals in this document into the final specification only after the corresponding choices are settled.
