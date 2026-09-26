# Frontend and meal-check mini sprint

Updated 2026-09-26. Adapted from the design-sprint-plan skill for four people and a 24-hour hackathon. This is the current build and testing plan; user interviews below are proposed, not completed research.

## Challenge and decisions

Help a person answer three questions: what conflicts with my recorded restrictions, what information is missing, and what can I do before eating?

The target journey is sign in → save restrictions → choose packaged food or cooked meal → review source/ingredients → assess → inspect evidence → request a change or compare alternatives → save history. Keep the existing Expo React Native mobile/web app and FastAPI/PostgreSQL backend.

User decisions: Food.com recipes from an existing Apify dataset are editable templates. Home cooks may add/remove ingredients. Restaurant diners use flagged ingredients and specific questions to ask for changes. IFCT is composition reference data for ingredients, not a recipe or packaged-product catalogue.

Sprint questions:

1. Can users distinguish a recorded conflict from missing information without reading every technical field?
2. Can they find the source and understand why one nutrient is known while another is unknown?
3. Can they edit a recipe and understand that reassessment applies to the proposed ingredient list, not proof of what a kitchen served?
4. Can they tell a fully checked replacement from a record requiring label review?

## Understand and compare directions

Considered three directions: a single nutrition score, a dense technical report, and a decision-first result with expandable evidence. Choose the last: a score obscures missing data and conflicting restrictions, while the dense report makes the next action hard to find.

Catalogue sources and acquisition options are documented in [product-catalogue-options.md](research/product-catalogue-options.md). Jev candidates, typed questions, gates and fallbacks are documented in [jev-impact-use-cases.md](research/jev-impact-use-cases.md).

## Storyboard

| Step | User sees | Data/action |
|---|---|---|
| Profile | Conditions, allergies, exclusions, clinician limits and comparison preferences | Save a versioned profile; no default invented clinician limits |
| Packaged food | Barcode, label photo, product search and saved catalogue | Cached lookup then source discovery; source and coverage on each product |
| Meal | Home/eating-out choice and Food.com template search | Only actual available validated recipe records; empty states remain honest |
| Edit | Ingredient rows, additions/removals, optional weights and IFCT references | Template starts unconfirmed; an edit clears completeness confirmation |
| Preparation | Sauce/mix, shared utensils/oil and salt/sugar prompts | Store known notes; notes do not automatically resolve cross-contact |
| Result | Conflict/unknown/note counts, clear explanations and next steps | Same deterministic restriction engine for labels and meal ingredient wording |
| Evidence | Recognized aliases, source, known nutrition, missing nutrition, raw field conversions | Preserve original wording and unit/basis; never render missing values as zero |
| Action | Ask the cook for changes, edit/reassess, or compare packaged swaps | A proposed recipe change must be confirmed in the actual kitchen |
| History | Saved food/profile snapshot and result | Reopen immutable evidence; changed profile requires fresh assessment |

No cooked-meal nutrient limit is evaluated using raw-ingredient density as though it measured the cooked serving. Missing recipe yield, retention and preparation data must stay explicit. A nutrient calculator is later work, separate from the ingredient restriction check.

## Four-person ownership and timebox

| Owner | Focus | Budget inside the 24-hour build |
|---|---|---|
| Frontend A | Search, review, nutrition/evidence layout, responsive sizing | 6 hours + 2 hours integration |
| Frontend B | Profile, editable recipes and meal flow | 6 hours + 2 hours integration |
| Backend A | Dish/recipe contracts, source import and provenance | 6 hours + 2 hours integration |
| Backend B | Rule validation, catalogue coverage and focused test/demo checks | 6 hours + 2 hours integration |

Use the first 90 minutes to agree on contracts and sketch narrow/mobile states. Reserve the last four hours for integration, user walkthroughs, fixes and rehearsal. The team appoints one decision maker; implementation choices above are the proposed direction.

## Prototype testing

Recruit five people for short walkthroughs if available. Ask them to think aloud; do not coach them toward the expected button.

- **Incomplete barcode record:** a product has sodium but no carbohydrate or ingredients. Ask what is known, what is missing and how they would verify it. Pass: no one interprets unknown as zero or sodium as salt.
- **Hidden ingredient:** profile excludes maida/wheat; label says all-purpose flour. Ask which wording caused the finding and where the evidence is. Pass: they can find the raw term and understand the alias match.
- **Home recipe:** choose a real template, add an ingredient relevant to their restrictions, reassess, then remove it as a proposed change. Pass: the new ingredient is assessed and removal does not imply the actual meal changed.
- **Restaurant:** use a recipe as reference with incomplete confirmation. Ask what to tell the cook. Pass: they formulate a specific ingredient/preparation question and retain unknowns.
- **Swap:** compare a checked candidate and a record needing review. Pass: they distinguish the tiers, units/basis and source confirmation requirement.

Record task outcome, time, misunderstanding, direct user quote and next fix. Stop and repair any false-safe interpretation before polish. After interviews, group repeated misunderstandings and select the three highest-impact changes.

Technical checks: TypeScript, Expo web export, backend focused/full suite, owned/versioned meal API smoke, missing-recipe state, label correction and source trace. Native camera and real package-photo quality need device testing; a web bundle passing does not test them.

## Jev implementation sequence

1. Keep mandatory conflicts and unresolved findings deterministic and visible.
2. Build a closed list of approved follow-up questions from those findings. Jev Choice may highlight the next useful question; fallback is deterministic priority. Log question IDs, model version and selection. It cannot hide mandatory checks or mark an unknown resolved.
3. Generate proposed recipe edits only from supported substitutions; reassess their full ingredient lists first. Jev Score ranks surviving proposals for taste/cuisine/effort. If evidence is incomplete, retain the unknown and request confirmation.
4. Preserve the current preference-ranking fallback for packaged swaps. Jev scores are never displayed as nutrient measurements or medical-safety probabilities.
5. Measure completion, useful kitchen questions and accepted verified swaps, not just inference speed.
