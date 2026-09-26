# High-impact Jev use cases for SafeBitez

## Recommendation

Jev is most useful here as a small semantic decision service: give it a bounded state, ask typed Choice/Score/Noul questions, validate the answer, then let normal backend code decide what happens next. TypeSafe describes Choice as picking from a fixed set, Score as rating against ordered descriptive levels, and Noul as the probability of a yes/no proposition. Independent questions can be batched in one request, but each question sees the same state and does not depend on answers to another question. Complex decisions should be decomposed and recombined in code. ([Introduction](https://docs.typesafe.ai/introduction), [Choice](https://docs.typesafe.ai/primitives/choice), [Score](https://docs.typesafe.ai/primitives/score), [Noul](https://docs.typesafe.ai/primitives/noul))

**Jev must not make a medical-safety decision.** Its confidence is derived from the distribution over the model's answers; it is not probability of harm, source truth, clinical validity, or label completeness. A Score is a position on the rubric the team wrote, not a measured nutrient or health rating. Noul's 0–1 is probability that its yes/no statement is true, not a calibrated patient-risk percentage. Let the deterministic assessment code own restriction matching, clinical thresholds, nutrient conversions, candidate eligibility, and missing-information blockers. ([Confidence](https://docs.typesafe.ai/confidence), [Score interpretation](https://docs.typesafe.ai/primitives/score))

## Five use cases, ranked for this app

| Priority | Use case | Primitive | Why it helps | Allowed effect |
|---|---|---|---|---|
| **1 — MVP candidate** | Choose the next label question when several fields block an assessment | Choice | Converts a long “incomplete product” state into one understandable next step | Order/show one prompt from backend-computed blockers; never mark any blocker resolved |
| **2 — Already implemented; MVP feature** | Rank already eligible product swaps by the user's stated taste/use preferences | Score | Makes code-eligible alternatives more practical without relaxing a restriction | Reorder only candidates tied on deterministic nutrient comparisons |
| **3 — Useful follow-up** | Choose the most useful next action or explanation card | Choice | Adapts the interface to the user's request and the evidence already available | Select one ID from a closed set of reviewed screens/actions; backend still validates availability |
| **4 — Later, operator-facing** | Triage catalog/label submissions for human review | Choice (or Score for queue priority) | Helps reviewers notice likely variant mismatches or panel discrepancies in contributed data | Sort a review queue; never publish or approve the record automatically |
| **5 — Later dish flow** | Clarify an ambiguous ingredient phrase in a dish/recipe | Choice | Handles local names and broad phrases that exact dictionary matching cannot safely resolve | Present candidate meanings for user selection; never assert an allergy concept or calculate nutrition from a guess |

### 1. Ask the most useful next label question

The backend already knows which missing fields block a given assessment: it can derive blockers from the profile's recorded restrictions and the observation's missing basis, ingredients, advisory, or nutrients. Jev could choose the clearest next prompt among **those precomputed blockers**, especially when several are missing at once. Do not ask Jev which clinical checks matter; code has that list.

Example state: `{"task":"finish this product label","blockers":[{"id":"ingredient_panel","prompt":"Photograph the full ingredients list"},{"id":"advisory_panel","prompt":"Photograph the 'may contain' statement"},{"id":"nutrition_basis","prompt":"Photograph the serving/basis heading"}]}`.

```json
{
  "next_prompt": {
    "type": "choice",
    "instructions": "Which one available prompt should be shown next to make progress on this incomplete label? Choose only an id present in blockers; prefer a clear, answerable photo request.",
    "criteria": {
      "ingredient_panel": "Ask for a readable photo of the complete ingredients list.",
      "advisory_panel": "Ask for a readable photo of the allergen or precautionary statement.",
      "nutrition_basis": "Ask for the nutrition table heading showing whether amounts are per serving, per 100 g, or per 100 ml."
    }
  }
}
```

**Code gate and effect:** check returned ID membership in the computed blocker IDs; show only the corresponding approved prompt. The user must provide/correct evidence before the blocker changes. If the answer is missing, invalid, low-confidence, timed out, or a sole blocker, use fixed deterministic order (ingredients/advisories before optional comparisons) and leave the assessment status unchanged. This improves completion flow, not dietary interpretation.

### 2. Rank eligible swaps against practical preferences

This is the safest user-facing Jev use already wired into [`ModelAssist.rank_preferences`](../../backend/app/integrations/models.py) and recommendation orchestration. It receives at most the backend's candidate set plus the user's preference text, makes per-candidate Score questions, validates answer keys/types/ranges/distributions, requires a demo confidence floor, and only reorders within candidates tied on the deterministic checked comparison values. Candidate filtering, conflicts, nutrients, and eligibility remain code-owned. The backend sends neither account identity nor the patient's conditions to Jev.

Example state: `{"preference":"plain and mild, available as an individual snack","candidates":{"p1":{"name":"Plain crackers","category":"crackers"},"p2":{"name":"Spiced crackers","category":"crackers"}}}`.

```json
{
  "candidate_p1": {
    "type": "score",
    "instructions": "Using only the supplied description, rate how well candidate p1 matches the user's flavor and use preference. Do not assess health suitability.",
    "criteria": ["Clearly conflicts", "Partial match or not enough description", "Clearly matches"]
  }
}
```

The current live contract check succeeded on two synthetic candidates; it showed Jev preference tie-breaking while retaining deterministic priority groups. Keep the current fallback to numeric ordering on uncertainty/provider failure. Never display the preference Score as a health score or treat it as measured product evidence. ([Provider verification](../../backend/scripts/provider-live-verification.md), [composite scoring](https://docs.typesafe.ai/patterns/composite-scoring))

### 3. Personalize the next user action from approved options

After an assessment, the app can choose among available, reviewed action cards: `show_verified_swaps`, `ask_for_missing_label`, `explain_current_finding`, or `save_for_later`. State should contain the user's immediate request (for example, “I need a quick snack now”), the current UI task, and the IDs the backend says are available. Avoid sending a diagnosis when a generic blocker/action state will do.

Example question: **“Which available action best responds to the user's request while helping them make progress?”** Choice options are the IDs above, each described with when it applies. Do not ask “what is safe for this patient?”

**Code gate and effect:** returned action ID must be in the available action list, and its preconditions must still hold at render time. A swap card is only offered when eligible candidates exist; a missing-label card is only offered when there are blockers. Use a deterministic fallback order if Jev is uncertain or unavailable. This is a UX routing choice; no new assessment claim is created.

### 4. Triage submitted catalog records for review

Compare two supplied observations of an exact product variant: for example, an OFF record and an operator-entered package transcription, with field-level differences already computed by code. Ask Choice to classify the discrepancy as `formatting_only`, `possible_variant_mismatch`, `material_label_difference`, or `insufficient_evidence`. This is about allocating human attention, not deciding which source is right.

**Code gate and effect:** every record remains unreviewed until a human checks the physical package or authorized source. Choice can raise the review priority when its class is not `formatting_only`; low confidence maps to `insufficient_evidence`. Keep original values and source provenance from both records. Never copy a model-picked value into the active observation, and never let a Noul like “is this record correct?” auto-approve it. For a large future queue, a three-level Score could rank review urgency using explicit descriptions; its score still does not represent clinical severity.

This feature is useful after user submissions accumulate, but it is lower priority than scan/assessment/swap in a one-day prototype because it requires versioned observations and an operator queue.

### 5. Clarify ambiguous dish/recipe ingredient input

For a dish ingredient such as “starch,” a regional name, or a transliterated phrase, first retrieve a small list of possible ingredient/reference-food IDs using deterministic exact aliases or lexical search. Ask Choice among those IDs plus `unknown` using only the raw phrase, locale if explicitly supplied, and candidate names/definitions. Jev can help phrase a clarification, but it must not turn a likely match into a confirmed ingredient.

Example state: `{"phrase":"starch","locale":"en-IN","candidates":{"rice_starch":"starch extracted from rice","corn_starch":"starch extracted from maize","unknown":"none of these or source not stated"}}`; question: “Which candidate meaning is best supported by this phrase and context?”

**Code gate and effect:** if the choice is `unknown` or confidence is below the task's evaluated threshold, retain the ingredient as unmatched and ask the user which source was used. Even a confident Choice appears as a proposal for explicit user confirmation; only the confirmed candidate ID can enter the dish estimator. Nutrition arithmetic and completeness checks remain in Python. For allergy assessment, a suggestion alone is never evidence that an allergen is absent/present.

## How to implement without letting model outputs drift into facts

Use the existing backend service boundary and one request per user operation. Keep payloads small and purpose-specific; strip account/email/token data, send only the necessary product fields, and treat label/user text as untrusted data. Include a closed output vocabulary and an explicit `unknown`/`insufficient_evidence` path. Validate response model ID, exact question IDs, expected primitive types, finite ranges, and whether every returned ID belongs to the input set. Do not make a model question depend on another model question in the same batch; TypeSafe evaluates them independently. ([Introduction](https://docs.typesafe.ai/introduction), [Choice request/response](https://docs.typesafe.ai/primitives/choice))

Use confidence only to route **semantic UI/review decisions**: high may allow automatic display of a low-stakes prompt, medium should ask/confirm, low should fall back or request human review. TypeSafe itself says thresholds depend on consequences and task evaluation; set them per action, not globally. Noul has no separate confidence property, so avoid using it for multi-option triage or any medical gate. ([Confidence](https://docs.typesafe.ai/confidence), [Noul](https://docs.typesafe.ai/primitives/noul))

For every feature, keep a deterministic no-provider path and record model/version, question/rubric version, result ID, confidence/distribution where applicable, latency, and fallback reason. Do not persist full personal payloads or SDK request logs unnecessarily. The currently implemented Jev adapter uses bounded raw HTTPX to `POST https://api.typesafe.ai/v1/systemone` with a five-second timeout; docs may recommend an SDK, but changing transport is not required to test these use cases. The provider-live verification document reports a synthetic ranking check; no clinical performance or production-latency claim follows from it.

## 24-hour priority

1. Keep the existing preference tie-breaker as the only live Jev feature; exercise both success and fallback during the demo.
2. Add a missing-label next-prompt choice only if the team has time after end-to-end capture → correction → assessment is working. The deterministic blocker list is already the source of truth.
3. If showcasing an additional Jev interaction, build approved-action routing with a tiny fixed option set; it has low risk and low implementation cost.
4. Defer catalog-review triage and dish-phrase clarification until there is a reviewed queue and a real labeled evaluation set. For now, exact alias matching plus explicit user selection is safer and testable.

Measure each candidate feature against a no-Jev baseline using a small, human-labeled set: correct next prompt/action/semantic ranking, uncertainty/fallback rate, wrong confident choices, and latency. In tests, force Jev on/off and assert that the same medical conflicts, unresolved checks, numeric comparisons, and replacement eligibility are returned. Any observed effect on those values is a release blocker.

## Official references

- [Introduction: typed questions, parallel independent answers, composition in code](https://docs.typesafe.ai/introduction)
- [Choice: fixed options and confidence/probability outputs](https://docs.typesafe.ai/primitives/choice)
- [Score: ordered rubric, score, distribution and confidence](https://docs.typesafe.ai/primitives/score)
- [Noul: yes/no probability; no separate confidence](https://docs.typesafe.ai/primitives/noul)
- [Confidence: route actions according to stakes](https://docs.typesafe.ai/confidence)
- [Composite scoring: score separate dimensions, combine in code](https://docs.typesafe.ai/patterns/composite-scoring)
- [Existing backend integration plan](typesafe-jev-integration-plan.md)
- [Current backend behavior and tests](../../backend/app/integrations/models.py)
- [Bounded live provider verification](../../backend/scripts/provider-live-verification.md)
