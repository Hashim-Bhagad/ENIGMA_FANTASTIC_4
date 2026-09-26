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
export type Photo = { uri: string; name?: string | null; mimeType?: string | null };

export type ProfilesGuide = {
  profile_id: string; profile_version: number;
  exclusions: string[]; recorded_limits: ProfileData['limits']; comparison_goals: ProfileData['goals'];
  condition_information: { condition: string; message: string; source: string }[];
  unsupported_conditions: string[]; questions: string[]; coverage: string;
};

export type DishOptionNote = { code: string; label: string; detail: string; next_step: string };
export type DishOptions = { cooking_notes: DishOptionNote[]; unknowns: string[]; assumptions: string[] };
export type DishIngredient = { text: string; reference_code?: string | null; grams?: number | null };
export type DishPayload = {
  profile_id: string; profile_version: number; name: string; ingredients: DishIngredient[];
  cooking_notes: string[]; declarations_confirmed: boolean; portion_g?: number | null;
};
export type DishMatch = { input_text: string; code: string; name: string; basis: string | null; grams: number | null; matched_by: string };
export type DishUnmatched = { input_text: string; reason: string };
export type DishEstimate = { available: boolean; basis: string | null; nutrients: Partial<Record<Nutrient, number | null>>; total_grams: number | null; assumptions: string[] };
export type DishAssessment = {
  id: string;
  dish: { name: string; matches: DishMatch[]; unmatched: DishUnmatched[]; estimate: DishEstimate };
  assessment: AssessmentResult;
};
export type ReferenceFood = { code: string; name: string; data: Record<string, unknown>; source: string };
export type ReferenceFoodsResult = { foods: ReferenceFood[]; usage: string };

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
export type IntakeTarget = {
  nutrient: string; label: string; unit: string; baseline_value?: number | null; baseline_source: string;
  proposed_value?: number | null; direction: 'lower' | 'higher' | 'maintain'; rule_id: string; basis: string;
  confidence: GuidanceConfidence; requires_clinician: boolean; evidence: IntakeEvidence[];
  questions: string[]; limit_scope: 'daily' | 'portion'; suggested_limit_source?: string | null;
};
export type IntakePlan = {
  version: string; targets: IntakeTarget[]; conditions: ConditionInfo[]; unrecognised_conditions: string[];
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

export function parameterStatusTone(status: ParameterStatus | undefined): 'red' | 'green' | 'amber' | 'neutral' {
  return status === 'high' || status === 'low' ? 'red' : status === 'normal' ? 'green' : 'neutral';
}

export function confidenceLabel(confidence: GuidanceConfidence): string {
  return confidence === 'established' ? 'established guidance' : confidence === 'clinician_only' ? 'clinician review required' : 'general wellbeing guidance';
}

const baseUrl = (process.env.EXPO_PUBLIC_API_URL || (Platform.OS === 'android' ? 'http://10.0.2.2:8000' : 'http://localhost:8000')).replace(/\/$/, '');

/** Frontend-origin codes sit alongside the backend's documented error codes. */
export type ApiErrorCode =
  | 'validation_error' | 'unauthorized' | 'forbidden' | 'not_found' | 'conflict' | 'rate_limited'
  | 'payload_too_large' | 'unsupported_media_type' | 'provider_unavailable' | 'internal_error'
  | 'profile_version_stale' | 'timeout' | 'network';

export class ApiError extends Error {
  constructor(message: string, readonly status?: number, readonly code?: ApiErrorCode) { super(message); this.name = 'ApiError'; }
}

const DEFAULT_TIMEOUT_MS = 15_000;
const LABEL_TIMEOUT_MS = 60_000;
const REPORT_TIMEOUT_MS = 90_000;
export const TIMEOUT_MESSAGE = 'The server did not respond in time. Check your connection and try again.';

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

export const api = {
  register: (email: string, password: string) => request<{ user: { id: string; email: string }; access_token: string }>('/api/auth/register', undefined, { method: 'POST', body: JSON.stringify({ email, password }) }),
  login: (email: string, password: string) => request<{ user: { id: string; email: string }; access_token: string }>('/api/auth/login', undefined, { method: 'POST', body: JSON.stringify({ email, password }) }),
  me: (token: string) => request<{ id: string; email: string }>('/api/auth/me', token),
  profile: (token: string) => request<SavedProfile>('/api/profiles/me', token),
  saveProfile: (token: string, data: ProfileData, expectedVersion: number | null) => request<SavedProfile>('/api/profiles/me', token, { method: 'PUT', body: JSON.stringify({ expected_version: expectedVersion, data }) }),
  profilesGuide: (token: string, profileId: string, profileVersion: number) => request<ProfilesGuide>('/api/profiles/guide', token, { method: 'POST', body: JSON.stringify({ profile_id: profileId, profile_version: profileVersion }) }),
  catalog: (token: string) => request<CatalogResponse>('/api/products?limit=50', token),
  search: (token: string, query: string, live = true) => request<CatalogResponse>('/api/products/search?q=' + encodeURIComponent(query) + `&include_live=${live}`, token),
  recipes: (token: string, query: string) => request<RecipePage>('/api/recipes?q=' + encodeURIComponent(query), token),
  barcode: (token: string, code: string) => request<{ id: string; food: FoodObservation; updated_at: string; lookup_source: string }>(`/api/products/barcode/${encodeURIComponent(code)}`, token),
  provenance: (token: string, id: string) => request<ProductProvenance>(`/api/products/${encodeURIComponent(id)}/provenance`, token),
  referenceFoods: (token: string, q: string, limit?: number) => request<ReferenceFoodsResult>(`/api/reference-foods?q=${encodeURIComponent(q)}${limit == null ? '' : `&limit=${limit}`}`, token),
  extractLabel: async (token: string, photo: Photo) => {
    const form = new FormData();
    if (Platform.OS === 'web') {
      const blob = await (await fetch(photo.uri)).blob();
      form.append('file', new File([blob], photo.name || 'label.jpg', { type: photo.mimeType || blob.type || 'image/jpeg' }));
    } else {
      form.append('file', { uri: photo.uri, name: photo.name || 'label.jpg', type: photo.mimeType || 'image/jpeg' } as unknown as Blob);
    }
    return request<{ food: FoodObservation; confirmation_required: boolean }>('/api/labels/extract', token, { method: 'POST', body: form }, LABEL_TIMEOUT_MS);
  },
  assess: (token: string, profile: SavedProfile, food: FoodObservation, portion: number | null) => request<Assessment>('/api/assessments', token, { method: 'POST', body: JSON.stringify({ profile_id: profile.id, profile_version: profile.version, food, portion }) }),
  history: async (token: string, limit = 20, offset = 0): Promise<HistoryPage> => {
    const page = await request<{ assessments: Assessment[]; total?: number; limit?: number; offset?: number }>(`/api/assessments?limit=${limit}&offset=${offset}`, token);
    return { assessments: page.assessments, total: page.total ?? offset + page.assessments.length };
  },
  assessment: (token: string, id: string) => request<Assessment>(`/api/assessments/${encodeURIComponent(id)}`, token),
  recommend: (token: string, assessmentId: string, preferences?: string) => request<Recommendation>('/api/recommendations', token, { method: 'POST', body: JSON.stringify({ assessment_id: assessmentId, preferences }) }),
  ingredientAlternatives: (token: string, ingredients: string[]) => request<IngredientAlternatives>('/api/ingredient-alternatives', token, { method: 'POST', body: JSON.stringify({ ingredients }) }),
  dishesOptions: (token: string) => request<DishOptions>('/api/dishes/options', token),
  assessDish: (token: string, payload: DishPayload) => request<DishAssessment>('/api/dishes/assess', token, { method: 'POST', body: JSON.stringify(payload) }),
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
