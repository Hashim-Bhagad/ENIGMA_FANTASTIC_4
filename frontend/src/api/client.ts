import { Platform } from 'react-native';
import { colors } from '../theme';
import { session } from './session';

export type Nutrient = 'sodium_mg' | 'potassium_mg' | 'phosphorus_mg' | 'carbohydrates_g' | 'protein_g' | 'fat_g' | 'saturated_fat_g' | 'sugars_g' | 'fiber_g' | 'energy_kcal';
export type Allergen = 'wheat' | 'milk' | 'eggs' | 'soy' | 'peanuts' | 'tree_nuts' | 'sesame' | 'fish' | 'shellfish' | 'celery' | 'mustard' | 'lupin' | 'molluscs' | 'sulphites';
export type Sex = 'female' | 'male' | 'unspecified';
export type AgeBand = 'under_18' | '18_29' | '30_44' | '45_59' | '60_74' | '75_plus' | 'unspecified';
export type FoodSourceKind = 'openfoodfacts' | 'apify_off' | 'manual' | 'label_extraction' | 'demo' | 'dish';
export type FoodObservation = {
  name: string; brand: string | null; barcode: string | null; category: string | null;
  basis: '100g' | '100ml' | null; ingredients_text: string | null; advisories_text: string | null;
  ingredients_complete: boolean; advisories_complete: boolean; declared_allergens: Allergen[];
  precautionary_allergens: Allergen[]; reported_allergens: Allergen[];
  nutrients: Partial<Record<Nutrient, number | null>>;
  source: { kind: FoodSourceKind; reference: string; retrieved_at?: string | null; warnings: string[]; model?: string | null; edited_fields?: string[] };
};
export type ProfileData = { conditions: string[]; allergies: Allergen[]; ingredient_exclusions: string[]; limits: { nutrient: Nutrient; maximum: number; scope: 'daily' | 'portion'; source: string }[]; goals: { nutrient: Nutrient; direction: 'lower' | 'higher' }[]; preferences: string; sex?: Sex; age_band?: AgeBand };
export type SavedProfile = { id: string; version: number; data: ProfileData };

/** A frontend view model for one searchable/look-up-able product row. */
export type Product = {
  id: string; brand: string; name: string; category: string; icon: string; color: string;
  barcode: string; ingredients: string; advisory: string; sodium: number | null; basis: string;
  observation?: FoodObservation;
};

export type Finding = {
  code: string;
  group: 'conflict' | 'unresolved' | 'consideration';
  title: string;
  detail: string;
  next_step?: string | null;
  affects: string[];
  message: string;
  evidence: string[];
};
export type IngredientFinding = {
  canonical_group: string; canonical_identity?: string; subtype: string; matched_term: string;
  raw_evidence: string; start: number; end: number; wheat_allergen?: boolean;
};
export type AssessmentStatus = 'recorded_conflict' | 'needs_information' | 'no_matching_concern_found';
export type ProductProvenance = {
  product_id: string; barcode: string | null; snapshot_updated_at: string;
  source: { kind: string; reference: string; retrieved_at?: string | null; source_modified_at?: string | number | null };
  fields: { field: string; status: string; source_field: string | null; source_value: unknown; source_unit: string | null; value: unknown; unit: string | null; basis: string | null; transformation: string | null; reason: string | null }[];
  limitations?: string[];
  edited_fields?: string[];
  source_salt?: { source_field: string; source_value: unknown; source_unit: string; used_by_backend: boolean; reason: string } | null;
};
export type AssessmentResult = {
  rule_version: string; ingredient_taxonomy_version?: string;
  status: AssessmentStatus; status_reason: string;
  conflicts: Finding[]; unresolved: Finding[]; considerations: Finding[];
  ingredient_findings?: IngredientFinding[];
  source_warnings: string[];
  source_trace?: ProductProvenance | null;
  coverage: string; portion?: number | null;
  dish?: { ingredients: DishIngredient[]; cooking_notes: string[]; declarations_confirmed: boolean; portion_g?: number | null };
};
export type Assessment = { id: string; profile_id: string; profile_version: number; profile_snapshot?: ProfileData; food: FoodObservation; result: AssessmentResult; created_at: string };
export type HistoryPage = { assessments: Assessment[]; total: number };

export type CandidateComparison = { nutrient: Nutrient; original: number; replacement: number; difference: number; basis: string; improved: boolean };
export type RecommendationCandidate = {
  product_id: string; food: FoodObservation; assessment: AssessmentResult;
  comparisons: CandidateComparison[]; improvements: string[];
  verified: boolean; review_reasons: string[];
};
export type Recommendation = {
  id: string; assessment_id: string;
  candidates: RecommendationCandidate[]; needs_review: RecommendationCandidate[];
  excluded: { product_id: string; reason: string }[];
  ranking_method: string; fallback_reason?: string | null; message: string;
};
export type IngredientAlternatives = { alternatives: { ingredient: string; matched_ingredient: string; alternatives: string[]; reason: string; review_required: boolean }[]; catalog_version: string; note: string };
export type Photo = {
  uri: string;
  name?: string | null;
  mimeType?: string | null;
  // Web pickers hand back a File whose object URL can already be revoked, and the blob
  // request then yields nothing. The base64 payload is read while the file is still open.
  file?: Blob | null;
  base64?: string | null;
  // What the picker reported about the picked file. A phone camera hands back several
  // thousand pixels a side, which is far more than a label or a barcode needs: the size
  // decides whether the photo is shrunk before it is uploaded, and `fileSize` is what a
  // photo too large to send is reported by.
  width?: number | null;
  height?: number | null;
  fileSize?: number | null;
};

/** Turn a base64 payload into an uploadable File, or null when it is missing or empty. */
export function photoFileFromBase64(photo: Photo): File | null {
  const payload = photo.base64;
  if (!payload) return null;
  try {
    const binary = atob(payload);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    if (!bytes.length) return null;
    return new File([bytes], photo.name || 'label.jpg', { type: photo.mimeType || 'image/jpeg' });
  } catch {
    return null;
  }
}

export type ProfilesGuide = {
  profile_id: string; profile_version: number;
  exclusions: string[]; recorded_limits: ProfileData['limits']; comparison_goals: ProfileData['goals'];
  condition_information: { condition: string; message: string; source: string }[];
  unsupported_conditions: string[]; questions: string[]; coverage: string;
};

export type DishOptionNote = { code: string; label: string; detail: string; next_step: string };
export type DishOptions = { cooking_notes: DishOptionNote[]; unknowns: string[]; assumptions: string[] };
export type DishIngredient = { text: string; reference_code?: string | null; grams?: number | null };
/**
 * One line a meal check posts: the wording the typist wrote, plus the reference code a tapped
 * suggestion attached. Amounts are not collected on this screen, so none is ever sent.
 */
export type DishCheckLine = { text: string; reference_code?: string | null };
export type DishPayload = {
  profile_id: string; profile_version: number; name: string; ingredients: DishCheckLine[];
  cooking_notes: string[]; declarations_confirmed: boolean;
};
/** The editable meal draft the payload builder reads: wording, reference, notes, confirmation. */
export type DishCheckDraft = {
  name: string; ingredients: { text: string; referenceCode: string | null }[];
  cookingNotes: string[]; declarationsConfirmed: boolean;
};
export type DishMatch = { input_text: string; code: string; name: string; basis: string | null; grams: number | null; matched_by: string; note?: string | null };
export type DishUnmatched = { input_text: string; reason: string };
/** One ingredient the estimate had to leave out, and why. */
export type DishEstimateExclusion = { input_text: string; reason: string };
/**
 * The backend's per-100 g estimate. This screen never collects amounts, so `available` stays
 * false and only `assumptions` is ever shown: every check above is a wording check.
 */
export type DishEstimate = {
  available: boolean; basis: string | null; nutrients: Partial<Record<Nutrient, number | null>>;
  total_grams: number | null; assumptions: string[]; matched_count: number; matched_grams: number | null;
  excluded: DishEstimateExclusion[]; coverage_note: string;
};
/** The vocabulary the wording review must answer with; a row outside it is never shown. */
export const DISH_REVIEW_VERDICTS = ['avoid', 'limit', 'no_concern_found', 'cannot_determine'] as const;
export type DishReviewVerdict = (typeof DISH_REVIEW_VERDICTS)[number];
export type DishReviewStatus = 'applied' | 'skipped' | 'unavailable';
/** One reviewed wording line: a language judgement, never a verified label match. */
export type DishReviewRow = {
  input_text: string; verdict: DishReviewVerdict; reason: string | null;
  matched_restriction: string | null; confidence: string | null;
};
export type DishModelReview = { status: DishReviewStatus; verdicts: DishReviewRow[]; message: string; disclaimer: string };
/** A swap comes from the reviewed catalogue, or from a model suggestion screened the same way. */
export type DishAlternativeSource = 'catalogue' | 'model';
export type DishAlternativeOption = { text: string; why: string; conflicts: string[] };
export type DishAlternativeEntry = {
  input_text: string; reason: string; source: DishAlternativeSource; resolved_to?: string;
  options: DishAlternativeOption[]; note?: string;
};
export type DishAlternatives = { version: string; entries: DishAlternativeEntry[]; notes: string[] };
export type DishAssessment = {
  id: string;
  dish: {
    name: string; matches: DishMatch[]; unmatched: DishUnmatched[]; estimate: DishEstimate;
    /** Always present: applied, skipped (nothing needed reviewing), or unavailable. */
    model_review?: DishModelReview;
    /** Swaps for the flagged lines, screened against every recorded restriction. */
    alternatives?: DishAlternatives;
  };
  assessment: AssessmentResult;
};
export type ReferenceFood = { code: string; name: string; data: Record<string, unknown>; source: string };
export type ReferenceFoodsResult = { foods: ReferenceFood[]; usage: string };
export type FssaiVerification = {
  success: boolean;
  verification_type: string;
  verification_data?: {
    fssai_number?: string;
    company_name?: string;
    license_category_name?: string;
    status_desc?: string;
    license_active_flag?: boolean;
    address?: string;
    [key: string]: unknown;
  };
  credits_used?: number;
  processing_time_ms?: number;
};

/** A type-ahead waits for this many characters and this long a pause before asking the server. */
export const TYPE_AHEAD_MIN_CHARS = 2;
export const TYPE_AHEAD_DELAY_MS = 250;

/** What tapping one reference suggestion does, and what it does not do. */
export const REFERENCE_MATCH_NOTE = 'Reference match only: it supplies the composition used for the estimate and keeps the wording you typed.';

/** The term a type-ahead should search for, or null while the typed text is too short to be useful. */
export function typeAheadTerm(text: string, minLength = TYPE_AHEAD_MIN_CHARS): string | null {
  const term = text.trim();
  return term.length >= minLength ? term : null;
}

/** One line for a single reference suggestion: the name the backend ranked first, then its code. */
export function referenceSuggestionLabel(food: ReferenceFood): string {
  return `${food.name} · ${food.code}`;
}

/** Plain-language meaning of a meal-check status, so a status word is never left unexplained. */
export function dishStatusExplanation(status: AssessmentStatus): string {
  if (status === 'recorded_conflict') return 'At least one ingredient matched a restriction recorded in your profile, so this meal fails a recorded check.';
  if (status === 'needs_information') return 'A required check could not complete with the information available, so this result is inconclusive.';
  return 'Every supported check ran on the available ingredient declarations and found no match with your recorded restrictions. This is not an overall safety verdict.';
}

/**
 * The whole estimate section now, and the honest reason there is no per-100 g figure in it:
 * amounts are never collected, so nothing can be weighed.
 */
export const NO_AMOUNT_ESTIMATE_NOTE = 'Amounts are not collected here, so no per-100 g estimate is shown; the checks above are based on the ingredients you listed.';

/** The line under the ingredient heading: each row is judged by its wording, not by an amount. */
export const INGREDIENT_WORDING_NOTE = 'Every line is judged by the wording alone: no amount is collected, so nothing here is weighed or portioned.';

/** The chip for one reviewed wording: four verdicts, four distinct labels and tones. */
export type DishVerdictChip = { label: string; tone: 'red' | 'amber' | 'blue' | 'neutral' };

/**
 * Never render ``no_concern_found`` as safety: a wording that raised nothing was still only
 * read as language, so its chip says what was read rather than giving a clearance.
 */
export function dishVerdictChip(verdict: DishReviewVerdict): DishVerdictChip {
  if (verdict === 'avoid') return { label: 'AVOID', tone: 'red' };
  if (verdict === 'limit') return { label: 'LIMIT', tone: 'amber' };
  if (verdict === 'no_concern_found') return { label: 'NO CONCERN IN THIS WORDING', tone: 'blue' };
  return { label: 'COULD NOT JUDGE', tone: 'neutral' };
}

/** Why an empty verdict is not a clearance, in the words the chip cannot carry. */
export const NO_CONCERN_NOT_CLEARANCE = 'This wording raised nothing in the wording review. That is not a clearance: nothing about this line was verified.';

/** The reason one reviewed line got its verdict, with the restriction it relates to when known. */
export function dishReviewReason(row: DishReviewRow): string {
  const reason = row.reason?.trim() || 'The review gave no reason for this line.';
  return row.matched_restriction ? `${reason} Relates to your recorded restriction: ${row.matched_restriction}.` : reason;
}

/** One swap card as it renders: its label, its options as given, and any note left visible. */
export type DishAlternativeView = Omit<DishAlternativeEntry, 'note'> & { sourceLabel: string; note: string | null };

/** One view per flagged line. A note (removed conflicting options, spent budget) is never dropped. */
export function dishAlternativeViews(block: DishAlternatives | null | undefined): DishAlternativeView[] {
  return (block?.entries ?? []).map(entry => ({
    ...entry,
    sourceLabel: entry.source === 'catalogue' ? 'Reviewed swap' : 'Model suggestion',
    note: entry.note?.trim() ? entry.note : null,
  }));
}

/** The first ingredient row holding this typed wording, matched the way the backend matches it. */
export function ingredientRowKeyFor<T extends { key: string; text: string }>(rows: T[], inputText: string): string | null {
  const target = inputText.trim().toLowerCase();
  return rows.find(row => row.text.trim().toLowerCase() === target)?.key ?? null;
}

/**
 * Attach a chosen reference code to the first row holding this typed wording and leave every
 * other row untouched, so a suggestion from the result view lands on the ingredient it came from.
 */
export function attachReferenceToRows<T extends { key: string; text: string; referenceCode: string | null }>(rows: T[], inputText: string, code: string): T[] {
  const key = ingredientRowKeyFor(rows, inputText);
  if (key === null) return rows;
  return rows.map(row => row.key === key ? { ...row, referenceCode: code } : row);
}

/** One line a model drafted for a dish; a null amount means the model was not sure. */
export type DishDraftIngredient = { text: string; grams: number | null };
/** Provenance that keeps a draft out of the reviewed-template list. */
export type DishDraftSource = { kind: 'model_draft'; model: string; model_version: string };
/** A model's starting list for a dish name: editable, labelled, and never checked on arrival. */
export type DishDraftResponse = { name: string; ingredients: DishDraftIngredient[]; cooking_notes: string[]; source: DishDraftSource; warnings: string[]; message: string };

/** The action that asks for a draft when no reviewed template answers the search. */
export const DISH_DRAFT_ACTION = 'Draft this dish';

/** The label a drafted list always carries, wherever it appears. */
export const DISH_DRAFT_BANNER = 'Draft list — a model wrote this from the dish name. Correct every line before you check it.';

/** One editable row per drafted line: the wording only, since amounts are not collected. */
export function draftIngredientRows(draft: DishDraftResponse, keyPrefix: string): { key: string; text: string; referenceCode: string | null }[] {
  return draft.ingredients.map((item, index) => ({ key: `${keyPrefix}-${index + 1}`, text: item.text, referenceCode: null }));
}

/**
 * The exact body a meal check posts: the dish name, each typed wording with the reference code a
 * tapped suggestion attached, the cooking notes and the confirmation. No amount, no portion and
 * no serving weight is ever sent — the check judges the ingredients that were listed.
 */
export function dishAssessmentPayload(profile: SavedProfile, draft: DishCheckDraft): DishPayload {
  const name = draft.name.trim();
  if (!name) throw new ApiError('Enter the dish name before assessing.', 400, 'validation_error');
  const ingredients = draft.ingredients
    .filter(row => row.text.trim())
    .map(row => ({ text: row.text.trim(), reference_code: row.referenceCode }));
  if (!ingredients.length) throw new ApiError('Add at least one ingredient before assessing.', 400, 'validation_error');
  return { profile_id: profile.id, profile_version: profile.version, name, ingredients, cooking_notes: draft.cookingNotes, declarations_confirmed: draft.declarationsConfirmed };
}
export type CatalogResponse = { products: { id: string; food: FoodObservation; updated_at: string }[]; query_type?: string; live_requested?: boolean; live_status?: string; message?: string; skipped_records?: number };
export type Recipe = { id: string; name: string; ingredients: DishIngredient[]; source: Record<string, unknown>; review_status: string; warnings: string[] };
export type RecipePage = { recipes: Recipe[]; message?: string; pending_count?: number };

// --- Health reports and personal intake (mirrors the backend contract) -------------------
export const NUTRIENTS: Nutrient[] = ['sodium_mg', 'potassium_mg', 'phosphorus_mg', 'carbohydrates_g', 'protein_g', 'fat_g', 'saturated_fat_g', 'sugars_g', 'fiber_g', 'energy_kcal'];

/** Narrow an intake target's nutrient string to the recorded-limit vocabulary. */
export function isNutrient(value: string): value is Nutrient {
  return (NUTRIENTS as string[]).includes(value);
}

export type ReferenceSource = 'document' | 'standard' | 'unknown';
export type ParameterStatus = 'low' | 'normal' | 'high' | 'unknown';
export type GuidanceConfidence = 'established' | 'general_wellbeing' | 'clinician_only';
export type ReportStatus = 'extracted' | 'confirmed';

/** One measured value from a health report. `key` is the canonical lab parameter vocabulary. */
export type LabParameter = {
  key: string; label: string; value?: number | null; unit?: string | null;
  reference_low?: number | null; reference_high?: number | null;
  reference_source?: ReferenceSource; raw_text?: string | null; status?: ParameterStatus;
};
export type ReportConfirm = LabParameter;
export type HealthReportResult = {
  id: string; status: ReportStatus; collected_on?: string | null; parameters: LabParameter[];
  abnormal_parameters: string[]; warnings: string[]; confirmation_required: boolean;
  source: Record<string, unknown>; provider: Record<string, unknown>;
};
export type HealthReportSummary = {
  id: string; status: ReportStatus; collected_on?: string | null;
  parameter_count: number; abnormal_count: number; created_at: string;
};
export type HealthReportList = { reports: HealthReportSummary[]; total: number; limit: number; offset: number };
export type HealthReportConfirmRequest = { parameters: ReportConfirm[]; collected_on?: string | null; note?: string };
/** An uploaded report file. On web `uri` is an object URL; on native it is the picker asset URI. */
export type ReportFile = { uri: string; name?: string | null; mimeType?: string | null };

export type ConditionInfo = {
  slug: string; label: string; category: string; aliases: string[];
  nutrient_focus: string[]; awareness: string; questions: string[]; sources: string[];
  lab_links: string[]; guidance_confidence: GuidanceConfidence;
};
export type ConditionRegistry = { version: string; conditions: ConditionInfo[]; categories: string[]; coverage: string; notes: string[] };
export type IntakeEvidence = {
  kind: 'lab' | 'condition' | 'baseline'; label: string; detail: string;
  parameter_key?: string | null; value?: number | null; unit?: string | null;
  reference_low?: number | null; reference_high?: number | null; report_id?: string | null;
};
/** The same number in the units people cook with (grams of salt, teaspoons of sugar). */
export type IntakeEquivalent = { label: string; value: number; unit: string };
export type AvoidSeverity = 'avoid' | 'limit' | 'ask';
/** One concrete thing to avoid or limit, with the reason it is listed and what it links to. */
export type AvoidItem = { label: string; examples: string[]; reason: string; linked_nutrients: string[] };
/** A severity-bucketed group of avoid/limit/ask entries with the evidence that triggered it. */
export type AvoidGroup = {
  id: string; title: string; detail: string; severity: AvoidSeverity; items: AvoidItem[];
  confidence: GuidanceConfidence; sources: string[]; evidence: IntakeEvidence[];
};
export type IntakeTarget = {
  nutrient: string; label: string; unit: string; baseline_value?: number | null; baseline_source: string;
  proposed_value?: number | null; direction: 'lower' | 'higher' | 'maintain'; rule_id: string; basis: string;
  confidence: GuidanceConfidence; requires_clinician: boolean; evidence: IntakeEvidence[];
  questions: string[]; limit_scope: 'daily' | 'portion'; suggested_limit_source?: string | null;
  /** The same number in cooking units, e.g. "1500 mg sodium ≈ 3.8 g salt". */
  display_value?: string | null; equivalents: IntakeEquivalent[];
  /** The arithmetic in one sentence, so the number is never unexplained. */
  derivation?: string | null;
  /** The raw confirmed lab values behind this target, with units and reference ranges. */
  measured: IntakeEvidence[];
};
export type IntakePlan = {
  version: string; targets: IntakeTarget[]; avoid: AvoidGroup[]; conditions: ConditionInfo[]; unrecognised_conditions: string[];
  reports_used: string[]; notes: string[]; coverage: string;
};

/** EU-14 allergen labels shared by the profile picker and every product surface. */
export const EU_ALLERGENS: { value: Allergen; label: string }[] = [
  { value: 'wheat', label: 'Wheat' }, { value: 'milk', label: 'Milk' }, { value: 'eggs', label: 'Eggs' },
  { value: 'soy', label: 'Soy' }, { value: 'peanuts', label: 'Peanuts' }, { value: 'tree_nuts', label: 'Tree nuts' },
  { value: 'sesame', label: 'Sesame' }, { value: 'fish', label: 'Fish' }, { value: 'shellfish', label: 'Shellfish' },
  { value: 'celery', label: 'Celery' }, { value: 'mustard', label: 'Mustard' }, { value: 'lupin', label: 'Lupin' },
  { value: 'molluscs', label: 'Molluscs' }, { value: 'sulphites', label: 'Sulphites' },
];

export function allergenLabel(value: Allergen): string {
  return EU_ALLERGENS.find(option => option.value === value)?.label ?? value.replaceAll('_', ' ');
}

/** Prettify a free-text or registry condition value that is not in the current registry. */
export function conditionLabel(value: string, registry?: ConditionRegistry | null): string {
  return registry?.conditions.find(item => item.slug === value)?.label ?? value.replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase());
}

/** A printed reference range from whatever the report supplied; unknown parts stay explicit. */
export function formatReferenceRange(referenceLow?: number | null, referenceHigh?: number | null): string {
  if (referenceLow != null && referenceHigh != null) return `${referenceLow}–${referenceHigh}`;
  if (referenceLow != null) return `above ${referenceLow}`;
  if (referenceHigh != null) return `below ${referenceHigh}`;
  return 'not printed';
}

/** One readable line for a single intake evidence row. */
export function formatEvidence(evidence: IntakeEvidence): string {
  const parts: string[] = [evidence.label];
  if (evidence.parameter_key) {
    const value = evidence.value == null ? 'value not recorded' : `${evidence.value}${evidence.unit ? ` ${evidence.unit}` : ''}`;
    parts.push(`${value} (reference ${formatReferenceRange(evidence.reference_low, evidence.reference_high)})`);
  }
  if (evidence.detail) parts.push(evidence.detail);
  return parts.join(' · ');
}

/** Which report an evidence row came from, without printing the stored filename. */
export function evidenceReportLabel(evidence: IntakeEvidence): string | null {
  if (evidence.kind !== 'lab' || !evidence.report_id) return null;
  return `Report ${evidence.report_id.slice(0, 8)}`;
}

/** One measured value in plain words: your reading, its printed range, and the report behind it. */
export function formatMeasuredLine(evidence: IntakeEvidence): string {
  const value = evidence.value == null ? 'value not recorded' : `${evidence.value}${evidence.unit ? ` ${evidence.unit}` : ''}`;
  const range = formatReferenceRange(evidence.reference_low, evidence.reference_high);
  const report = evidenceReportLabel(evidence);
  const head = `your ${evidence.label}: ${value} (range ${range})`;
  return report ? `${head} · ${report}` : head;
}

/** One human-scale equivalent of the same number, e.g. "Salt: 3.8 g". */
export function formatEquivalent(equivalent: IntakeEquivalent): string {
  const amount = `${equivalent.value}${equivalent.unit ? ` ${equivalent.unit}` : ''}`;
  return equivalent.label ? `${equivalent.label}: ${amount}` : amount;
}

export function avoidSeverityLabel(severity: AvoidSeverity): string {
  if (severity === 'avoid') return 'AVOID';
  return severity === 'ask' ? 'ASK YOUR CLINICIAN' : 'LIMIT';
}

export function avoidSeverityTone(severity: AvoidSeverity): 'red' | 'amber' | 'blue' {
  if (severity === 'avoid') return 'red';
  return severity === 'ask' ? 'blue' : 'amber';
}

/** What is proposed for one nutrient, and who has to decide when nothing can be proposed. */
export function intakeProposedLine(target: IntakeTarget): string {
  if (target.proposed_value == null) {
    return target.requires_clinician ? 'No value is proposed here: a clinician needs to set this one.' : 'No change is proposed for this nutrient.';
  }
  const value = `${target.proposed_value}${target.unit ? ` ${target.unit}` : ''}`;
  return target.direction === 'lower' ? `Proposed daily limit: at most ${value}` : target.direction === 'higher' ? `Proposed target: at least ${value}` : `Proposed target: keep near ${value}`;
}

/** What is already recorded as the starting point, and where that number came from. */
export function intakeBaselineLine(target: IntakeTarget): string {
  if (target.baseline_value == null) return `No recorded baseline · ${target.baseline_source}`;
  return `Recorded baseline: ${target.baseline_value}${target.unit ? ` ${target.unit}` : ''} · ${target.baseline_source}`;
}

export function parameterStatusTone(status: ParameterStatus | undefined): 'red' | 'green' | 'amber' | 'neutral' {
  return status === 'high' || status === 'low' ? 'red' : status === 'normal' ? 'green' : 'neutral';
}

export function confidenceLabel(confidence: GuidanceConfidence): string {
  return confidence === 'established' ? 'established guidance' : confidence === 'clinician_only' ? 'clinician review required' : 'general wellbeing guidance';
}

const baseUrl = (process.env.EXPO_PUBLIC_API_URL || (Platform.OS === 'android' ? 'http://10.0.2.2:8000' : 'http://localhost:8000')).replace(/\/$/, '');

/** The URL every call is sent to, so a screen can show what it actually tried. */
export const API_BASE_URL = baseUrl;

/** Frontend-origin codes sit alongside the backend's documented error codes. */
export type ApiErrorCode =
  | 'validation_error' | 'unauthorized' | 'forbidden' | 'not_found' | 'conflict' | 'rate_limited'
  | 'payload_too_large' | 'unsupported_media_type' | 'provider_unavailable' | 'internal_error'
  | 'profile_version_stale' | 'timeout' | 'network';

export class ApiError extends Error {
  constructor(message: string, readonly status?: number, readonly code?: ApiErrorCode) { super(message); this.name = 'ApiError'; }
}

// --- The guided fallback when a barcode has no record --------------------------------
/** The optional fields that keep a photographed pack attached to its barcode and search name. */
export type LabelExtractionMeta = { barcode?: string | null; name?: string | null };

/** What a label extraction returned: the observation to correct, and whether the pack was saved. */
export type LabelExtractionResult = {
  food: FoodObservation;
  confirmation_required: boolean;
  /** True when a catalog record now answers this barcode, so the next lookup finds the pack. */
  saved: boolean;
  product_id: string | null;
};

/** One other retail code printed on the same photo. */
export type ScannedBarcode = { barcode: string; format: string };

/** What the server read out of a barcode photo, and what to do with it next. */
export type BarcodeScanResult = {
  /** The digits, always one of the retail lengths `isUsableBarcode` accepts. */
  barcode: string;
  /** The printed symbology the decoder recognised, e.g. `EAN-13`. */
  format: string;
  /** Further codes on the same photo, best first, when it held more than one. */
  alternatives: ScannedBarcode[];
  message: string;
};

/** The digit counts a printed retail barcode and the backend both accept. */
export function isUsableBarcode(value: string): boolean {
  return /^(?:[0-9]{8}|[0-9]{12,14})$/.test(value.trim());
}

/** One honest offer of the ingredient-list photo, and exactly what it will do with the barcode. */
export type LabelFallbackPrompt = {
  /** The barcode to send with the photo, or null when there is no usable barcode to carry. */
  barcode: string | null;
  title: string;
  detail: string;
};

/** The parts of a found catalog record that decide whether its answer is usable at all. */
export type FoundRecord = { barcode?: string | null; ingredients_text?: string | null };

/**
 * Decide whether a lookup that produced nothing usable should offer the ingredient-list photo.
 *
 * A missing record (404), a record that declares no ingredients, and an empty search are what a
 * photo can answer; a connection, sign-in, or server failure is not, so those offer nothing. A
 * barcode the backend rejects still offers the photo, but says plainly that the barcode cannot be
 * attached instead of dropping it silently.
 */
export function labelFallbackOffer(input: { barcode?: string | null; query?: string | null; error?: unknown; resultCount?: number; found?: FoundRecord | null }): LabelFallbackPrompt | null {
  const barcode = (input.barcode ?? '').trim();
  const query = (input.query ?? '').trim();
  const failure = input.error;
  const notFound = failure instanceof ApiError && (failure.status === 404 || failure.code === 'not_found');
  const malformed = failure instanceof ApiError && (failure.status === 422 || failure.code === 'validation_error');
  if (notFound || malformed) {
    if (malformed && barcode && !isUsableBarcode(barcode)) {
      return { barcode: null, title: `"${barcode}" is not a usable barcode`, detail: 'A barcode needs 8, 12, 13, or 14 digits, so this one cannot be attached to the photo. The photo is still read and saved as its own record.' };
    }
    if (barcode && isUsableBarcode(barcode)) {
      return { barcode, title: `No record for ${barcode}`, detail: `Photograph the ingredient list and review it yourself. The photo is saved against barcode ${barcode}, so the next lookup finds your pack.` };
    }
    if (!query) return null;
    return { barcode: null, title: `No results for "${query}"`, detail: 'Photograph the ingredient list and review it yourself. The photo is saved as its own record, so the next lookup by name finds it.' };
  }
  const found = input.found;
  if (found) {
    // A community record can exist and still carry nothing worth reviewing.
    if ((found.ingredients_text ?? '').trim()) return null;
    const code = barcode || (found.barcode ?? '').trim();
    if (code) return { barcode: code, title: `The record for ${code} has no ingredient declaration`, detail: `Photograph the pack and review it yourself. The photo is saved against barcode ${code}, so the next lookup finds your ingredients.` };
    if (!query) return null;
    return { barcode: null, title: `The record for "${query}" has no ingredient declaration`, detail: 'Photograph the pack and review it yourself. The photo is saved as its own record, so the next lookup by name finds it.' };
  }
  if (failure == null && input.resultCount === 0 && query) {
    return { barcode: null, title: `No results for "${query}"`, detail: 'Photograph the ingredient list and review it yourself. The photo is saved as its own record, so the next lookup by name finds it.' };
  }
  return null;
}

/**
 * What the scan screen says after an extraction: whether the pack is now findable by its
 * barcode, and a plain statement when the entered barcode could not be attached.
 */
export function labelExtractionMessage(result: { saved: boolean }, attachedBarcode?: string | null, unusableBarcode?: string | null): string {
  const review = 'Compare every extracted field with the package — a model reading is a draft, not a verified label.';
  if (unusableBarcode) return `${unusableBarcode} is not a usable barcode (8, 12, 13, or 14 digits), so the photo was saved without it. ${review}`;
  if (attachedBarcode && result.saved) return `Saved against barcode ${attachedBarcode} — the next lookup will find your label. ${review}`;
  if (attachedBarcode) return `The photo was read, but no record was saved against barcode ${attachedBarcode}. ${review}`;
  return review;
}

const DEFAULT_TIMEOUT_MS = 15_000;
const PHOTO_TIMEOUT_MS = 60_000;
const DRAFT_TIMEOUT_MS = 45_000;
const REPORT_TIMEOUT_MS = 90_000;
const HEALTH_TIMEOUT_MS = 8_000;
/**
 * A meal check can run two provider calls in sequence — the wording review, then the swap
 * suggestions — so the shared 15 s default is far too short for it.
 */
const DISH_TIMEOUT_MS = 90_000;
/**
 * Endpoints that wait on an outside provider (Open Food Facts for a barcode or live search,
 * Apify for a live recipe search, TheVerifico for a licence, and one model ranking call for
 * recommendations). Each is a network round trip outside our control, so 15 s is too short.
 */
const PROVIDER_TIMEOUT_MS = 45_000;
export const TIMEOUT_MESSAGE = 'The server did not respond in time. Check your connection and try again.';

// --- Fitting a phone photo under a route's upload limit ------------------------------
/** The longest edge a label or barcode photo keeps: plenty of detail, well under the byte caps. */
export const PHOTO_MAX_EDGE_PX = 1600;
/** JPEG quality for a shrunk photo: the print stays legible at a fraction of the original bytes. */
export const PHOTO_JPEG_QUALITY = 0.7;
/** What the label route accepts; a larger photo is refused on the phone, before it is sent. */
export const LABEL_PHOTO_LIMIT_BYTES = 5 * 1024 * 1024;
/** What the barcode-scan route accepts, for a photo the in-app camera could not read. */
export const BARCODE_PHOTO_LIMIT_BYTES = 8 * 1024 * 1024;

/**
 * Whether a picked photo is longer than the edge we upload. A picker that reported no
 * dimensions is left alone: guessing a resize would risk uploading a broken file, and the
 * server's own refusal is a better answer than a corrupted photo.
 */
export function needsPhotoResize(photo: { width?: number | null; height?: number | null }, maxEdge = PHOTO_MAX_EDGE_PX): boolean {
  const width = photo.width ?? 0;
  const height = photo.height ?? 0;
  return Number.isFinite(width) && Number.isFinite(height) && Math.max(width, height) > maxEdge;
}

/** Megabytes with a decimal only where it says something, the way the backend prints them. */
function megabytes(bytes: number): string {
  const value = bytes / 1048576;
  return `${Number.isInteger(value) ? value : value.toFixed(1)} MB`;
}

/**
 * Say a photo is still too large to send, or null when it fits. The threshold sits at 90% of
 * the route's limit so the user hears the size from the app, not from a rejected upload.
 */
export function photoSizeWarning(bytes: number | null | undefined, limitBytes: number): string | null {
  if (bytes == null || !Number.isFinite(bytes) || bytes <= Math.floor(limitBytes * 0.9)) return null;
  return `This photo is still ${megabytes(bytes)}; the limit is ${megabytes(limitBytes)}. Retake it at a lower resolution.`;
}

/** The file a photo is about to upload as, and how big it is when that is known. */
export type PreparedPhoto = { uri: string; name: string; mimeType: string; bytes: number | null };

/** The name a re-encoded photo uploads under: the picked name with a JPEG extension. */
function jpegPhotoName(name: string | null | undefined): string {
  const picked = (name ?? '').trim();
  return picked ? `${picked.replace(/\.[^./\\]+$/, '')}.jpg` : 'photo.jpg';
}

/**
 * Fit a native photo to the upload: one whose longest edge is above `maxEdge` is re-encoded at
 * that edge as a JPEG, and anything already smaller uploads as picked. A resize that fails
 * never blocks the upload — the picked file goes instead, with the size the picker reported, so
 * the caller can say the photo is still too large before the server has to.
 *
 * `bytes` is null for a photo that was shrunk: its exact size is not reported back, and it is
 * far under the cap by construction.
 */
export async function preparePhotoForUpload(photo: Photo, fallbackName = 'photo.jpg', maxEdge = PHOTO_MAX_EDGE_PX): Promise<PreparedPhoto> {
  const pickedName = photo.name?.trim() || fallbackName;
  const picked: PreparedPhoto = { uri: photo.uri, name: pickedName, mimeType: photo.mimeType || 'image/jpeg', bytes: photo.fileSize ?? null };
  if (Platform.OS === 'web' || !needsPhotoResize(photo, maxEdge)) return picked;
  try {
    // Deferred on purpose: `expo-image-manipulator` is a native module that throws when it is
    // loaded outside the app, so a static import would break the web bundle and the Node tests.
    const { ImageManipulator, SaveFormat } = await import('expo-image-manipulator');
    const context = ImageManipulator.manipulate(photo.uri);
    // One edge is enough: the other follows the aspect ratio.
    context.resize((photo.width ?? 0) >= (photo.height ?? 0) ? { width: maxEdge } : { height: maxEdge });
    const image = await context.renderAsync();
    const saved = await image.saveAsync({ compress: PHOTO_JPEG_QUALITY, format: SaveFormat.JPEG });
    context.release();
    image.release();
    return { uri: saved.uri, name: jpegPhotoName(pickedName), mimeType: 'image/jpeg', bytes: null };
  } catch {
    // Resizing is a convenience, never a requirement: the picked photo still goes.
    return picked;
  }
}

let unauthorizedHandler: (() => void) | null = null;
/** Register a global reaction to any 401. The stored token is cleared before it runs. */
export function setUnauthorizedHandler(handler: (() => void) | null) { unauthorizedHandler = handler; }

function detailMessage(detail: unknown, fallback: string): string {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map(item => (item && typeof item === 'object' && 'msg' in item ? String((item as { msg?: unknown }).msg ?? '') : ''))
      .filter(Boolean);
    if (messages.length) return messages.join(', ');
  }
  return fallback;
}

async function request<T>(path: string, token?: string, init: RequestInit = {}, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        ...(init.body && !(init.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    });
  } catch {
    if (controller.signal.aborted) throw new ApiError(TIMEOUT_MESSAGE, undefined, 'timeout');
    const hostHint = Platform.OS === 'android' ? ' For a physical phone, set EXPO_PUBLIC_API_URL to your computer’s LAN IP and port 8000.' : '';
    throw new ApiError(`Cannot reach the backend at ${baseUrl}. Start Docker Compose and check the API URL.${hostHint}`, undefined, 'network');
  } finally {
    clearTimeout(timer);
  }
  if (!response.ok) {
    let detail: unknown;
    let code: unknown;
    try {
      const data = (await response.json()) as { detail?: unknown; code?: unknown };
      detail = data.detail;
      code = data.code;
    } catch { /* Keep the status message when the server did not return JSON. */ }
    if (response.status === 401) {
      await session.clear();
      unauthorizedHandler?.();
    }
    throw new ApiError(detailMessage(detail, `Request failed (${response.status})`), response.status, typeof code === 'string' ? (code as ApiErrorCode) : undefined);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

/**
 * The multipart `file` field for a picked photo: a real File on web (built from the base64 the
 * picker read, so a revoked blob: URL cannot empty the upload), and the resized native file
 * elsewhere. A native photo that is still over `limitBytes` after the resize is refused here,
 * with its size, so the user hears why instead of receiving a bare 413.
 */
async function photoForm(photo: Photo, limitBytes: number, fallbackName: string): Promise<FormData> {
  const form = new FormData();
  if (Platform.OS === 'web') {
    // Prefer the file the picker already handed us: its blob: URL can be revoked before we
    // fetch it (net::ERR_FILE_NOT_FOUND), which made every web upload fail. Only fall back to
    // fetching the URI when no file was supplied.
    const fromBase64 = photoFileFromBase64(photo);
    const supplied = fromBase64 ?? (photo.file instanceof Blob && photo.file.size > 0 ? photo.file : null);
    let blob: Blob;
    if (supplied) {
      blob = supplied;
    } else {
      blob = await (await fetch(photo.uri)).blob();
    }
    if (!blob.size) throw new ApiError('The picked photo could not be read. Choose it again.', undefined, 'network');
    form.append('file', new File([blob], photo.name || fallbackName, { type: photo.mimeType || blob.type || 'image/jpeg' }));
    return form;
  }
  const prepared = await preparePhotoForUpload(photo, fallbackName);
  const tooLarge = photoSizeWarning(prepared.bytes, limitBytes);
  if (tooLarge) throw new ApiError(tooLarge, undefined, 'payload_too_large');
  form.append('file', { uri: prepared.uri, name: prepared.name, type: prepared.mimeType } as unknown as Blob);
  return form;
}

export const api = {
  register: (email: string, password: string) => request<{ user: { id: string; email: string }; access_token: string }>('/api/auth/register', undefined, { method: 'POST', body: JSON.stringify({ email, password }) }),
  login: (email: string, password: string) => request<{ user: { id: string; email: string }; access_token: string }>('/api/auth/login', undefined, { method: 'POST', body: JSON.stringify({ email, password }) }),
  me: (token: string) => request<{ id: string; email: string }>('/api/auth/me', token),
  // Unauthenticated readiness probe: the one call that works before sign-in and tells the app
  // whether a failure is the backend being down rather than the request being wrong.
  health: () => request<{ status: string; migrations?: string }>('/health/ready', undefined, {}, HEALTH_TIMEOUT_MS),
  profile: (token: string) => request<SavedProfile>('/api/profiles/me', token),
  saveProfile: (token: string, data: ProfileData, expectedVersion: number | null) => request<SavedProfile>('/api/profiles/me', token, { method: 'PUT', body: JSON.stringify({ expected_version: expectedVersion, data }) }),
  profilesGuide: (token: string, profileId: string, profileVersion: number) => request<ProfilesGuide>('/api/profiles/guide', token, { method: 'POST', body: JSON.stringify({ profile_id: profileId, profile_version: profileVersion }) }),
  catalog: (token: string) => request<CatalogResponse>('/api/products?limit=50', token),
  search: (token: string, query: string, live = true) => request<CatalogResponse>('/api/products/search?q=' + encodeURIComponent(query) + `&include_live=${live}`, token, {}, PROVIDER_TIMEOUT_MS),
  recipes: (token: string, query: string) => request<RecipePage>('/api/recipes?q=' + encodeURIComponent(query), token, {}, PROVIDER_TIMEOUT_MS),
  barcode: (token: string, code: string) => request<{ id: string; food: FoodObservation; updated_at: string; lookup_source: string }>(`/api/products/barcode/${encodeURIComponent(code)}`, token, {}, PROVIDER_TIMEOUT_MS),
  verifyFssai: (token: string, fssaiNumber: string) => request<FssaiVerification>('/api/verification/fssai', token, { method: 'POST', body: JSON.stringify({ fssai_number: fssaiNumber }) }, PROVIDER_TIMEOUT_MS),
  provenance: (token: string, id: string) => request<ProductProvenance>(`/api/products/${encodeURIComponent(id)}/provenance`, token),
  referenceFoods: (token: string, q: string, limit?: number) => request<ReferenceFoodsResult>(`/api/reference-foods?q=${encodeURIComponent(q)}${limit == null ? '' : `&limit=${limit}`}`, token),
  extractLabel: async (token: string, photo: Photo, meta?: LabelExtractionMeta) => {
    const form = await photoForm(photo, LABEL_PHOTO_LIMIT_BYTES, 'label.jpg');
    // A barcode sent with the photo makes the extracted record answer that barcode next time.
    const barcode = meta?.barcode?.trim();
    if (barcode) form.append('barcode', barcode);
    const name = meta?.name?.trim();
    if (name) form.append('name', name);
    return request<LabelExtractionResult>('/api/labels/extract', token, { method: 'POST', body: form }, PHOTO_TIMEOUT_MS);
  },
  /**
   * Read a barcode from a photo, for the codes the in-app camera could not see: it is the
   * browser's only scanner, and the native fallback when the camera window is unusable.
   */
  scanBarcode: async (token: string, photo: Photo) => {
    const form = await photoForm(photo, BARCODE_PHOTO_LIMIT_BYTES, 'barcode.jpg');
    return request<BarcodeScanResult>('/api/barcodes/scan', token, { method: 'POST', body: form }, PHOTO_TIMEOUT_MS);
  },
  assess: (token: string, profile: SavedProfile, food: FoodObservation, portion: number | null) => request<Assessment>('/api/assessments', token, { method: 'POST', body: JSON.stringify({ profile_id: profile.id, profile_version: profile.version, food, portion }) }),
  history: async (token: string, limit = 20, offset = 0): Promise<HistoryPage> => {
    const page = await request<{ assessments: Assessment[]; total?: number; limit?: number; offset?: number }>(`/api/assessments?limit=${limit}&offset=${offset}`, token);
    return { assessments: page.assessments, total: page.total ?? offset + page.assessments.length };
  },
  assessment: (token: string, id: string) => request<Assessment>(`/api/assessments/${encodeURIComponent(id)}`, token),
  recommend: (token: string, assessmentId: string, preferences?: string) => request<Recommendation>('/api/recommendations', token, { method: 'POST', body: JSON.stringify({ assessment_id: assessmentId, preferences }) }, PROVIDER_TIMEOUT_MS),
  ingredientAlternatives: (token: string, ingredients: string[]) => request<IngredientAlternatives>('/api/ingredient-alternatives', token, { method: 'POST', body: JSON.stringify({ ingredients }) }),
  dishesOptions: (token: string) => request<DishOptions>('/api/dishes/options', token),
  assessDish: (token: string, payload: DishPayload) => request<DishAssessment>('/api/dishes/assess', token, { method: 'POST', body: JSON.stringify(payload) }, DISH_TIMEOUT_MS),
  /** Ask the model for a starting ingredient list; nothing is checked until the user runs it. */
  draftDish: (token: string, name: string) => request<DishDraftResponse>('/api/dishes/draft', token, { method: 'POST', body: JSON.stringify({ name }) }, DRAFT_TIMEOUT_MS),
  conditions: (token: string) => request<ConditionRegistry>('/api/conditions', token),
  reports: (token: string, limit = 20, offset = 0) => request<HealthReportList>(`/api/reports?limit=${limit}&offset=${offset}`, token),
  report: (token: string, id: string) => request<HealthReportResult>(`/api/reports/${encodeURIComponent(id)}`, token),
  extractReport: async (token: string, file: ReportFile) => {
    const form = new FormData();
    if (Platform.OS === 'web') {
      const blob = await (await fetch(file.uri)).blob();
      form.append('file', new File([blob], file.name || 'report.pdf', { type: file.mimeType || blob.type || 'application/pdf' }));
    } else {
      form.append('file', { uri: file.uri, name: file.name || 'report.jpg', type: file.mimeType || 'image/jpeg' } as unknown as Blob);
    }
    return request<HealthReportResult>('/api/reports/extract', token, { method: 'POST', body: form }, REPORT_TIMEOUT_MS);
  },
  confirmReport: (token: string, id: string, payload: HealthReportConfirmRequest) => request<HealthReportResult>(`/api/reports/${encodeURIComponent(id)}/confirm`, token, { method: 'POST', body: JSON.stringify(payload) }),
  deleteReport: (token: string, id: string) => request<void>(`/api/reports/${encodeURIComponent(id)}`, token, { method: 'DELETE' }),
  intakePlan: (token: string, profileId: string, profileVersion: number) => request<IntakePlan>('/api/intake/plan', token, { method: 'POST', body: JSON.stringify({ profile_id: profileId, profile_version: profileVersion }) }),
};

export function toProduct(id: string, food: FoodObservation): Product {
  return {
    id, brand: food.brand || 'Product record', name: food.name,
    category: food.category || 'Unclassified product', icon: '🥫', color: colors.lavender,
    barcode: food.barcode || '', ingredients: food.ingredients_text || '', advisory: food.advisories_text || '',
    sodium: food.nutrients.sodium_mg ?? null, basis: food.basis ? `per 100 ${food.basis === '100ml' ? 'ml' : 'g'}` : 'Not supplied',
    observation: food,
  };
}

/**
 * The blank, user-editable pack the manual-entry path opens. No catalog observation is
 * attached, and the barcode that is already known (typed, or from a failed lookup) is kept
 * on it so the packed details still answer that barcode later.
 */
export function manualProduct(base: Product, barcode: string): Product {
  return {
    ...base, id: `manual-${Date.now()}`, brand: 'Your label', name: 'New product', barcode,
    ingredients: '', advisory: '', sodium: null, basis: 'Not supplied', observation: undefined,
  };
}
