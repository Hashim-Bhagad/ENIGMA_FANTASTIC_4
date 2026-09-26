import { Platform } from 'react-native';
import { colors } from '../theme';
import { session } from './session';

export type Nutrient = 'sodium_mg' | 'potassium_mg' | 'phosphorus_mg' | 'carbohydrates_g' | 'protein_g' | 'fat_g' | 'saturated_fat_g' | 'sugars_g' | 'fiber_g' | 'energy_kcal';
export type Allergen = 'wheat' | 'milk' | 'eggs' | 'soy' | 'peanuts' | 'tree_nuts' | 'sesame' | 'fish' | 'shellfish';
export type FoodSourceKind = 'openfoodfacts' | 'apify_off' | 'manual' | 'label_extraction' | 'demo' | 'dish';
export type FoodObservation = {
  name: string; brand: string | null; barcode: string | null; category: string | null;
  basis: '100g' | '100ml' | null; ingredients_text: string | null; advisories_text: string | null;
  ingredients_complete: boolean; advisories_complete: boolean; declared_allergens: Allergen[];
  precautionary_allergens: Allergen[]; reported_allergens: Allergen[];
  nutrients: Partial<Record<Nutrient, number | null>>;
  source: { kind: FoodSourceKind; reference: string; retrieved_at?: string | null; warnings: string[]; model?: string | null; edited_fields?: string[] };
};
export type ProfileData = { conditions: string[]; allergies: Allergen[]; ingredient_exclusions: string[]; limits: { nutrient: Nutrient; maximum: number; scope: 'daily' | 'portion'; source: string }[]; goals: { nutrient: Nutrient; direction: 'lower' | 'higher' }[]; preferences: string };
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
export type CatalogResponse = { products: { id: string; food: FoodObservation; updated_at: string }[]; query_type?: string; live_requested?: boolean; live_status?: string; message?: string; skipped_records?: number };
export type Recipe = { id: string; name: string; ingredients: DishIngredient[]; source: Record<string, unknown>; review_status: string; warnings: string[] };
export type RecipePage = { recipes: Recipe[]; message?: string; pending_count?: number };

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
  referenceFoods: (token: string, q: string) => request<ReferenceFoodsResult>('/api/reference-foods?q=' + encodeURIComponent(q), token),
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
  dishesOptions: (token: string) => request<DishOptions>('/api/dishes/options', token),
  assessDish: (token: string, payload: DishPayload) => request<DishAssessment>('/api/dishes/assess', token, { method: 'POST', body: JSON.stringify(payload) }),
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
