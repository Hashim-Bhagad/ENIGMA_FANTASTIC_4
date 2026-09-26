import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  allergenLabel, attachReferenceToRows, avoidSeverityLabel, avoidSeverityTone, confidenceLabel,
  DISH_DRAFT_ACTION, DISH_DRAFT_BANNER, dishStatusExplanation, draftIngredientRows, estimateCoverageLine, EU_ALLERGENS,
  evidenceReportLabel, formatEquivalent, formatEvidence,
  formatMeasuredLine, formatReferenceRange, ingredientRowKeyFor, intakeBaselineLine, intakeProposedLine, isNutrient,
  parameterStatusTone, PARTIAL_ESTIMATE_FLOOR_NOTE, referenceSuggestionLabel, TYPE_AHEAD_DELAY_MS,
  TYPE_AHEAD_MIN_CHARS, typeAheadTerm, type DishDraftResponse, type IntakeTarget,
} from './client';

// The client and the session module import native modules; stubbing them keeps the
// transport tests in plain Node without a React Native runtime.
vi.mock('react-native', () => ({ Platform: { OS: 'web' } }));
vi.mock('expo-secure-store', () => ({ getItemAsync: vi.fn(), setItemAsync: vi.fn(), deleteItemAsync: vi.fn() }));

type FetchInit = { signal?: AbortSignal } & Record<string, unknown>;

function fakeLocalStorage() {
  const store = new Map<string, string>();
  const removeItem = vi.fn((key: string) => { store.delete(key); });
  return { store, removeItem, api: { getItem: (key: string) => store.get(key) ?? null, setItem: (key: string, value: string) => { store.set(key, value); }, removeItem } };
}

describe('api client transport', () => {
  // Each case re-imports the module after vi.resetModules() because the client captures
  // its base URL and unauthorized hook at module load. The specifier is a literal.
  beforeEach(() => { vi.resetModules(); delete process.env.EXPO_PUBLIC_API_URL; });
  afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

  it('keeps the backend code and detail on a typed error', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 409, json: async () => ({ detail: 'Profile changed; reload it before saving', code: 'profile_version_stale' }) })));
    const { api, ApiError } = await import('./client');
    const failure = await api.me('token').catch((cause: unknown) => cause);
    expect(failure).toBeInstanceOf(ApiError);
    expect(failure).toMatchObject({ status: 409, code: 'profile_version_stale', message: 'Profile changed; reload it before saving' });
  });

  it('joins FastAPI validation detail into a message', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 422, json: async () => ({ detail: [{ msg: 'field required' }, { msg: 'value is not valid' }], code: 'validation_error' }) })));
    const { api } = await import('./client');
    const failure = await api.me('token').catch((cause: unknown) => cause);
    expect(failure).toMatchObject({ status: 422, code: 'validation_error', message: 'field required, value is not valid' });
  });

  it('falls back to the status message when the error body is not JSON', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 500, json: async () => { throw new Error('not json'); } })));
    const { api } = await import('./client');
    const failure = await api.me('token').catch((cause: unknown) => cause);
    expect(failure).toMatchObject({ status: 500, message: 'Request failed (500)' });
  });

  it('clears the stored token and runs the unauthorized hook on 401', async () => {
    const storage = fakeLocalStorage();
    storage.store.set('safebitez.access-token', 'stale-token');
    vi.stubGlobal('localStorage', storage.api);
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 401, json: async () => ({ detail: 'Not authenticated', code: 'unauthorized' }) })));
    const { api, setUnauthorizedHandler } = await import('./client');
    const onUnauthorized = vi.fn();
    setUnauthorizedHandler(onUnauthorized);
    const failure = await api.me('stale-token').catch((cause: unknown) => cause);
    expect(failure).toMatchObject({ status: 401, code: 'unauthorized' });
    expect(storage.removeItem).toHaveBeenCalledWith('safebitez.access-token');
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    setUnauthorizedHandler(null);
  });

  it('aborts a stalled request and surfaces a timeout error', async () => {
    vi.useFakeTimers();
    // A fetch that only settles when the client aborts, so the timeout path is the sole outcome.
    vi.stubGlobal('fetch', vi.fn((_url: string, init: FetchInit) => new Promise<never>((_resolve, reject) => {
      // Settle only when the client aborts, so the timeout path is the sole outcome. Written
      // with the Promise constructor rather than Promise.withResolvers (Node 22+) so the test
      // also runs on the Node 20 CI image.
      init.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
    })));
    const { api, TIMEOUT_MESSAGE } = await import('./client');
    const assertion = expect(api.me('token')).rejects.toMatchObject({ code: 'timeout', message: TIMEOUT_MESSAGE });
    await vi.advanceTimersByTimeAsync(15_000);
    await assertion;
  });

  it('resolves the base URL from the environment and strips a trailing slash', async () => {
    process.env.EXPO_PUBLIC_API_URL = 'http://api.example.test/';
    const fetchMock = vi.fn(async (_url: string, _init: FetchInit) => ({ ok: true, status: 200, json: async () => ({ id: '1', email: 'a@b.c' }) }));
    vi.stubGlobal('fetch', fetchMock);
    const { api } = await import('./client');
    await api.me('token');
    expect(fetchMock.mock.calls[0]?.[0]).toBe('http://api.example.test/api/auth/me');
  });
});

/** A fetch stub for the web upload path: it answers the object-URL read, then the API call. */
function uploadFetch(apiResponse: { ok: boolean; status: number; json?: () => Promise<unknown> }) {
  const calls: { url: string; init: FetchInit }[] = [];
  const fetchMock = vi.fn(async (url: string, init?: FetchInit) => {
    calls.push({ url, init: init ?? {} });
    if (url.startsWith('blob:')) return { ok: true, status: 200, blob: async () => new Blob(['%PDF-1.4']) };
    return { ok: apiResponse.ok, status: apiResponse.status, json: apiResponse.json ?? (async () => ({})) };
  });
  return { fetchMock, calls };
}

const lastCall = (calls: { url: string; init: FetchInit }[]) => {
  const call = calls.at(-1);
  if (!call) throw new Error('fetch was not called');
  return { url: call.url, init: call.init, headers: (call.init.headers ?? {}) as Record<string, string> };
};

describe('api client reports, conditions and intake contract', () => {
  beforeEach(() => { vi.resetModules(); delete process.env.EXPO_PUBLIC_API_URL; });
  afterEach(() => { vi.unstubAllGlobals(); vi.resetModules(); });

  it('loads the condition registry with the bearer token', async () => {
    const fetchMock = vi.fn(async (_url: string, _init: FetchInit) => ({ ok: true, status: 200, json: async () => ({ version: 'r1', conditions: [], categories: [], coverage: 'coverage', notes: [] }) }));
    vi.stubGlobal('fetch', fetchMock);
    const { api } = await import('./client');
    await api.conditions('token');
    expect(fetchMock.mock.calls[0]?.[0]).toBe('http://localhost:8000/api/conditions');
    expect((fetchMock.mock.calls[0]?.[1] as FetchInit).headers).toMatchObject({ Authorization: 'Bearer token' });
  });

  it('pages saved reports and encodes the report id in the path', async () => {
    const fetchMock = vi.fn(async (_url: string, _init: FetchInit) => ({ ok: true, status: 200, json: async () => ({ reports: [], total: 0, limit: 20, offset: 0 }) }));
    vi.stubGlobal('fetch', fetchMock);
    const { api } = await import('./client');
    await api.reports('token');
    await api.reports('token', 5, 10);
    await api.report('token', 'report/1');
    expect(fetchMock.mock.calls.map(call => call[0])).toEqual([
      'http://localhost:8000/api/reports?limit=20&offset=0',
      'http://localhost:8000/api/reports?limit=5&offset=10',
      'http://localhost:8000/api/reports/report%2F1',
    ]);
  });

  it('uploads a report file as multipart without setting a JSON content type', async () => {
    const { fetchMock, calls } = uploadFetch({ ok: true, status: 200, json: async () => ({ id: 'r1', status: 'extracted', parameters: [], abnormal_parameters: [], warnings: [], confirmation_required: true, source: {}, provider: {} }) });
    vi.stubGlobal('fetch', fetchMock);
    const { api } = await import('./client');
    await api.extractReport('token', { uri: 'blob:http://localhost/abc', name: 'panel.pdf', mimeType: 'application/pdf' });
    const { url, init, headers } = lastCall(calls);
    expect(url).toBe('http://localhost:8000/api/reports/extract');
    expect(init.method).toBe('POST');
    expect(headers.Authorization).toBe('Bearer token');
    // The runtime must set the multipart boundary itself.
    expect(headers['Content-Type']).toBeUndefined();
    expect(init.body).toBeInstanceOf(FormData);
    const file = (init.body as FormData).get('file') as File;
    expect(file.name).toBe('panel.pdf');
    expect(file.type).toBe('application/pdf');
  });

  it('posts the corrected values as JSON when confirming a report', async () => {
    const fetchMock = vi.fn(async (_url: string, _init: FetchInit) => ({ ok: true, status: 200, json: async () => ({ id: 'r1', status: 'confirmed', parameters: [], abnormal_parameters: [], warnings: [], confirmation_required: false, source: {}, provider: {} }) }));
    vi.stubGlobal('fetch', fetchMock);
    const { api } = await import('./client');
    const parameters = [{ key: 'potassium', label: 'Potassium', value: 5.6, unit: 'mmol/L', reference_low: 3.5, reference_high: 5.1, reference_source: 'document' as const, status: 'high' as const }];
    await api.confirmReport('token', 'r1', { parameters, collected_on: '2026-05-14', note: 'fasting sample' });
    const { url, init, headers } = lastCall(fetchMock.mock.calls.map(call => ({ url: call[0], init: call[1] })));
    expect(url).toBe('http://localhost:8000/api/reports/r1/confirm');
    expect(init.method).toBe('POST');
    expect(headers['Content-Type']).toBe('application/json');
    expect(JSON.parse(init.body as string)).toEqual({ parameters, collected_on: '2026-05-14', note: 'fasting sample' });
  });

  it('deletes a saved report and resolves without a body', async () => {
    const fetchMock = vi.fn(async (_url: string, _init: FetchInit) => ({ ok: true, status: 204 }));
    vi.stubGlobal('fetch', fetchMock);
    const { api } = await import('./client');
    await expect(api.deleteReport('token', 'r1')).resolves.toBeUndefined();
    expect(fetchMock.mock.calls[0]?.[0]).toBe('http://localhost:8000/api/reports/r1');
    expect((fetchMock.mock.calls[0]?.[1] as FetchInit).method).toBe('DELETE');
  });

  it('asks for an intake plan with the profile id and version', async () => {
    const fetchMock = vi.fn(async (_url: string, _init: FetchInit) => ({ ok: true, status: 200, json: async () => ({ version: 'p1', targets: [], conditions: [], unrecognised_conditions: [], reports_used: [], notes: [], coverage: 'coverage' }) }));
    vi.stubGlobal('fetch', fetchMock);
    const { api } = await import('./client');
    await api.intakePlan('token', 'profile-1', 3);
    expect(fetchMock.mock.calls[0]?.[0]).toBe('http://localhost:8000/api/intake/plan');
    expect(JSON.parse((fetchMock.mock.calls[0]?.[1] as FetchInit).body as string)).toEqual({ profile_id: 'profile-1', profile_version: 3 });
  });

  it('sends the ranked reference-food query with an explicit limit', async () => {
    const fetchMock = vi.fn(async (_url: string, _init: FetchInit) => ({ ok: true, status: 200, json: async () => ({ foods: [], usage: 'usage' }) }));
    vi.stubGlobal('fetch', fetchMock);
    const { api } = await import('./client');
    await api.referenceFoods('token', 'paneer cheese', 6);
    await api.referenceFoods('token', 'rice');
    expect(fetchMock.mock.calls.map(call => call[0])).toEqual([
      'http://localhost:8000/api/reference-foods?q=paneer%20cheese&limit=6',
      'http://localhost:8000/api/reference-foods?q=rice',
    ]);
  });

  it('carries the cooking-unit numbers, derivation and avoid groups through the plan', async () => {
    const payload = {
      version: 'p2',
      targets: [{
        nutrient: 'sodium_mg', label: 'Sodium', unit: 'mg', baseline_value: 2100, baseline_source: 'blood pressure rule',
        proposed_value: 1500, direction: 'lower', rule_id: 'bp-sodium', basis: 'basis', confidence: 'established',
        requires_clinician: false, evidence: [], questions: [], limit_scope: 'daily', suggested_limit_source: 'Clinician guidance',
        display_value: '1500 mg sodium ≈ 3.8 g salt',
        equivalents: [{ label: 'Salt', value: 3.8, unit: 'g' }],
        derivation: 'Systolic blood pressure 138 mmHg is at or above 130 mmHg → sodium ceiling 1500 mg/day (≈3.8 g salt)',
        measured: [{ kind: 'lab', label: 'Systolic blood pressure', detail: '', parameter_key: 'bp_systolic', value: 138, unit: 'mmHg', reference_high: 130 }],
      }],
      avoid: [{
        id: 'bp-salt', title: 'Salt-heavy foods', detail: 'Raised blood pressure', severity: 'limit',
        items: [{ label: 'Processed meats', examples: ['sausage'], reason: 'High sodium', linked_nutrients: ['sodium_mg'] }],
        confidence: 'established', sources: ['https://example.test/guideline'], evidence: [{ kind: 'lab', label: 'Systolic blood pressure', detail: '' }],
      }],
      conditions: [], unrecognised_conditions: [], reports_used: ['r1'], notes: [], coverage: 'coverage',
    };
    const fetchMock = vi.fn(async (_url: string, _init: FetchInit) => ({ ok: true, status: 200, json: async () => payload }));
    vi.stubGlobal('fetch', fetchMock);
    const { api } = await import('./client');
    const plan = await api.intakePlan('token', 'profile-1', 2);
    expect(plan.targets[0]?.display_value).toBe('1500 mg sodium ≈ 3.8 g salt');
    expect(plan.targets[0]?.equivalents[0]).toEqual({ label: 'Salt', value: 3.8, unit: 'g' });
    expect(plan.targets[0]?.derivation).toMatch(/138 mmHg/);
    expect(plan.targets[0]?.measured[0]?.value).toBe(138);
    expect(plan.avoid[0]?.severity).toBe('limit');
    expect(plan.avoid[0]?.items[0]?.linked_nutrients).toEqual(['sodium_mg']);
    expect(plan.avoid[0]?.evidence).toHaveLength(1);
  });

  it('keeps the documented error codes on report upload failures', async () => {
    const { fetchMock } = uploadFetch({ ok: false, status: 429, json: async () => ({ detail: 'Too many reports in a short time', code: 'rate_limited' }) });
    vi.stubGlobal('fetch', fetchMock);
    const { api, ApiError } = await import('./client');
    const failure = await api.extractReport('token', { uri: 'blob:http://localhost/abc', name: 'panel.jpg', mimeType: 'image/jpeg' }).catch((cause: unknown) => cause);
    expect(failure).toBeInstanceOf(ApiError);
    expect(failure).toMatchObject({ status: 429, code: 'rate_limited', message: 'Too many reports in a short time' });
  });
});

describe('api client dish draft contract', () => {
  // Each case re-imports the client after vi.resetModules(), as above, because it captures
  // its base URL at module load; the specifier stays a literal for the bundler.
  beforeEach(() => { vi.resetModules(); delete process.env.EXPO_PUBLIC_API_URL; });
  afterEach(() => { vi.unstubAllGlobals(); vi.resetModules(); });

  it('asks for a draft by dish name and returns the labelled model list', async () => {
    const payload = {
      name: 'Fried rice',
      ingredients: [{ text: 'Cooked rice', grams: 600 }, { text: 'Soy sauce', grams: null }],
      cooking_notes: ['pan_fried'],
      source: { kind: 'model_draft', model: 'accounts/fireworks/models/x', model_version: 'reported-v2' },
      warnings: ['The model drafted this list from the dish name "Fried rice" alone.'],
      message: 'A model wrote this starting list from the dish name.',
    };
    const fetchMock = vi.fn(async (_url: string, _init: FetchInit) => ({ ok: true, status: 200, json: async () => payload }));
    vi.stubGlobal('fetch', fetchMock);
    const { api } = await import('./client');
    const draft = await api.draftDish('token', 'Fried rice');
    const { url, init, headers } = lastCall(fetchMock.mock.calls.map(call => ({ url: call[0], init: call[1] })));
    expect(url).toBe('http://localhost:8000/api/dishes/draft');
    expect(init.method).toBe('POST');
    expect(headers.Authorization).toBe('Bearer token');
    expect(JSON.parse(init.body as string)).toEqual({ name: 'Fried rice' });
    expect(draft.source).toEqual({ kind: 'model_draft', model: 'accounts/fireworks/models/x', model_version: 'reported-v2' });
    expect(draft.ingredients[1]?.grams).toBeNull();
  });

  it('keeps provider_unavailable on a failed draft so the screen can fall back to typing', async () => {
    const detail = 'Drafting an ingredient list failed or returned unusable output; type the ingredients yourself instead.';
    const fetchMock = vi.fn(async (_url: string, _init: FetchInit) => ({ ok: false, status: 503, json: async () => ({ detail, code: 'provider_unavailable' }) }));
    vi.stubGlobal('fetch', fetchMock);
    const { api, ApiError } = await import('./client');
    const failure = await api.draftDish('token', 'Fried rice').catch((cause: unknown) => cause);
    expect(failure).toBeInstanceOf(ApiError);
    expect(failure).toMatchObject({ status: 503, code: 'provider_unavailable', message: detail });
    expect((failure as Error).message).toMatch(/type the ingredients yourself/);
  });
});

describe('meal-check and report display helpers', () => {
  it('starts a type-ahead only once the typed text is worth searching for', () => {
    expect(typeAheadTerm('')).toBeNull();
    expect(typeAheadTerm('   ')).toBeNull();
    expect(typeAheadTerm('a')).toBeNull();
    expect(typeAheadTerm('  ab  ')).toBe('ab');
    expect(typeAheadTerm('paneer cheese')).toBe('paneer cheese');
    expect(typeAheadTerm('a', 1)).toBe('a');
  });

  it('labels a suggestion with the ranked name and its code', () => {
    expect(referenceSuggestionLabel({ code: 'IFCT-1', name: 'Rice, raw milled', data: {}, source: 'ifct' })).toBe('Rice, raw milled · IFCT-1');
  });

  it('explains every meal-check status differently', () => {
    const explanations = (['recorded_conflict', 'needs_information', 'no_matching_concern_found'] as const).map(status => dishStatusExplanation(status));
    expect(explanations.every(text => text.trim().length > 0)).toBe(true);
    expect(new Set(explanations).size).toBe(3);
    expect(dishStatusExplanation('recorded_conflict')).toMatch(/recorded/i);
    expect(dishStatusExplanation('needs_information')).toMatch(/inconclusive/i);
    expect(dishStatusExplanation('no_matching_concern_found')).toMatch(/not an overall safety verdict/i);
  });

  it('keeps the type-ahead knobs aligned with the agreed batch size', () => {
    expect(TYPE_AHEAD_MIN_CHARS).toBe(2);
    expect(TYPE_AHEAD_DELAY_MS).toBe(250);
    expect(typeAheadTerm('a'.repeat(TYPE_AHEAD_MIN_CHARS))).not.toBeNull();
  });

  it('prints a reference range only from the parts the report supplied', () => {
    expect(formatReferenceRange(3.5, 5.1)).toBe('3.5–5.1');
    expect(formatReferenceRange(3.5, null)).toBe('above 3.5');
    expect(formatReferenceRange(null, 5.1)).toBe('below 5.1');
    expect(formatReferenceRange(null, null)).toBe('not printed');
  });

  it('names the report behind a lab evidence row without printing the file name', () => {
    expect(evidenceReportLabel({ kind: 'lab', label: 'Potassium', detail: '', report_id: 'abcdef1234567890' })).toBe('Report abcdef12');
    expect(evidenceReportLabel({ kind: 'lab', label: 'Potassium', detail: '', report_id: null })).toBeNull();
    expect(evidenceReportLabel({ kind: 'condition', label: 'CKD', detail: 'x', report_id: 'abcdef1234567890' })).toBeNull();
  });

  it('summarises one evidence row, including what is missing', () => {
    expect(formatEvidence({ kind: 'lab', label: 'Serum potassium', detail: 'flagged high', parameter_key: 'potassium', value: 5.6, unit: 'mmol/L', reference_low: 3.5, reference_high: 5.1 }))
      .toBe('Serum potassium · 5.6 mmol/L (reference 3.5–5.1) · flagged high');
    expect(formatEvidence({ kind: 'lab', label: 'Serum potassium', detail: '', parameter_key: 'potassium', value: null, unit: 'mmol/L' }))
      .toBe('Serum potassium · value not recorded (reference not printed)');
    // A condition row carries no measurement, so no range may be invented for it.
    expect(formatEvidence({ kind: 'condition', label: 'Chronic kidney disease', detail: 'recorded in your profile' }))
      .toBe('Chronic kidney disease · recorded in your profile');
  });

  it('maps every EU-14 allergen to one distinct readable label', () => {
    expect(EU_ALLERGENS).toHaveLength(14);
    const labels = EU_ALLERGENS.map(option => option.label);
    expect(new Set(labels).size).toBe(14);
    expect(labels.every(label => label.length > 0 && !label.includes('_'))).toBe(true);
    expect(allergenLabel('tree_nuts')).toBe('Tree nuts');
    expect(allergenLabel('sulphites')).toBe('Sulphites');
    expect(EU_ALLERGENS.map(option => option.value)).toContain('molluscs');
  });

  it('gives clinician-only guidance its own label', () => {
    const labels = (['established', 'general_wellbeing', 'clinician_only'] as const).map(value => confidenceLabel(value));
    expect(new Set(labels).size).toBe(3);
    expect(confidenceLabel('clinician_only')).toMatch(/clinician/i);
  });

  it('tones a lab status by whether it is outside the printed range', () => {
    expect(parameterStatusTone('high')).toBe('red');
    expect(parameterStatusTone('low')).toBe('red');
    expect(parameterStatusTone('normal')).toBe('green');
    expect(parameterStatusTone('unknown')).toBe('neutral');
    expect(parameterStatusTone(undefined)).toBe('neutral');
  });

  it('only accepts recorded-limit nutrient names', () => {
    expect(isNutrient('sodium_mg')).toBe(true);
    expect(isNutrient('energy_kcal')).toBe(true);
    expect(isNutrient('vitamin_d_ug')).toBe(false);
  });

  it('reads a partial estimate as coverage of the weighed ingredients', () => {
    const estimate = { available: true, basis: '100g', nutrients: {}, total_grams: 200, assumptions: [], matched_count: 2, matched_grams: 200, excluded: [], coverage_note: '' };
    expect(estimateCoverageLine(estimate)).toBe('Estimated from 2 weighed ingredients · 200 g counted');
    expect(estimateCoverageLine({ ...estimate, matched_count: 1 })).toBe('Estimated from 1 weighed ingredient · 200 g counted');
    expect(estimateCoverageLine({ ...estimate, matched_grams: null })).toBe('Estimated from 2 weighed ingredients');
    expect(estimateCoverageLine({ ...estimate, available: false })).toMatch(/^No nutrient estimate/);
  });

  it('states that a partial estimate is a floor, never the whole dish', () => {
    expect(PARTIAL_ESTIMATE_FLOOR_NOTE).toMatch(/floor/i);
    expect(PARTIAL_ESTIMATE_FLOOR_NOTE).toMatch(/understated/i);
  });

  it('finds the ingredient row a result row came from', () => {
    const rows = [{ key: 'a', text: 'Salt' }, { key: 'b', text: '  Paneer  ' }, { key: 'c', text: 'salt' }];
    expect(ingredientRowKeyFor(rows, 'paneer')).toBe('b');
    expect(ingredientRowKeyFor(rows, 'SALT')).toBe('a');
    expect(ingredientRowKeyFor(rows, 'ghee')).toBeNull();
  });

  it('attaches a chosen reference to that row only, leaving the rest untouched', () => {
    const rows = [
      { key: 'a', text: 'Salt', referenceCode: null as string | null, grams: '' },
      { key: 'b', text: 'Paneer', referenceCode: null as string | null, grams: '100' },
    ];
    const attached = attachReferenceToRows(rows, '  paneer ', 'IFCT-9');
    expect(attached[1]).toMatchObject({ key: 'b', referenceCode: 'IFCT-9', grams: '100' });
    expect(attached[0]).toBe(rows[0]);
    expect(attached).toHaveLength(2);
    // Ids are attached by wording, so an unknown wording changes nothing.
    expect(attachReferenceToRows(rows, 'ghee', 'IFCT-9')).toEqual(rows);
  });

  it('reads one measured lab value with its range and report', () => {
    expect(formatMeasuredLine({ kind: 'lab', label: 'HbA1c', detail: '', parameter_key: 'hba1c', value: 7.4, unit: '%', reference_low: 4, reference_high: 5.6, report_id: 'abcdef1234567890' }))
      .toBe('your HbA1c: 7.4 % (range 4–5.6) · Report abcdef12');
    expect(formatMeasuredLine({ kind: 'lab', label: 'Creatinine', detail: '', value: null, unit: 'mg/dL' }))
      .toBe('your Creatinine: value not recorded (range not printed)');
  });

  it('formats a kitchen-unit equivalent as label and amount', () => {
    expect(formatEquivalent({ label: 'Salt', value: 3.8, unit: 'g' })).toBe('Salt: 3.8 g');
    expect(formatEquivalent({ label: 'Sugar', value: 6, unit: 'tsp' })).toBe('Sugar: 6 tsp');
  });

  it('gives every avoid severity its own chip and colour', () => {
    expect(avoidSeverityLabel('avoid')).toBe('AVOID');
    expect(avoidSeverityLabel('limit')).toBe('LIMIT');
    expect(avoidSeverityLabel('ask')).toMatch(/clinician/i);
    expect(new Set((['avoid', 'limit', 'ask'] as const).map(avoidSeverityLabel)).size).toBe(3);
    expect(avoidSeverityTone('avoid')).toBe('red');
    expect(avoidSeverityTone('limit')).toBe('amber');
    expect(avoidSeverityTone('ask')).toBe('blue');
  });

  it('fills editable rows from a model draft without attaching any reference', () => {
    const draft: DishDraftResponse = {
      name: 'Fried rice',
      ingredients: [{ text: 'Cooked rice', grams: 600 }, { text: 'Soy sauce', grams: null }],
      cooking_notes: ['pan_fried'],
      source: { kind: 'model_draft', model: 'accounts/fireworks/models/x', model_version: 'reported-v2' },
      warnings: ['The model drafted this list from the dish name.'],
      message: 'A model wrote this starting list from the dish name.',
    };
    const rows = draftIngredientRows(draft, 'draft-7');
    expect(rows).toEqual([
      { key: 'draft-7-1', text: 'Cooked rice', referenceCode: null, grams: '600' },
      { key: 'draft-7-2', text: 'Soy sauce', referenceCode: null, grams: '' },
    ]);
    // One prefix per draft keeps the row ids unique against rows already on screen.
    expect(draftIngredientRows(draft, 'draft-8').map(row => row.key)).toEqual(['draft-8-1', 'draft-8-2']);
  });

  it('labels a drafted list as a model suggestion everywhere it is named', () => {
    expect(DISH_DRAFT_ACTION).toBe('Draft this dish');
    expect(DISH_DRAFT_BANNER).toMatch(/^Draft list/);
    expect(DISH_DRAFT_BANNER).toMatch(/a model wrote this from the dish name/i);
    expect(DISH_DRAFT_BANNER).toMatch(/correct every line before you check it/i);
    expect(DISH_DRAFT_BANNER).not.toMatch(/recipe/i);
  });

  it('asks a clinician to set the value instead of implying one is applied', () => {
    const clinicianOnly: IntakeTarget = { nutrient: 'potassium_mg', label: 'Potassium', unit: 'mg', baseline_source: 'condition', direction: 'lower', rule_id: 'ckd-potassium', basis: 'basis', confidence: 'clinician_only', requires_clinician: true, evidence: [], questions: [], limit_scope: 'daily', equivalents: [], measured: [] };
    expect(intakeProposedLine(clinicianOnly)).toMatch(/clinician/i);
    expect(intakeProposedLine(clinicianOnly)).not.toMatch(/at most|at least/);
    expect(intakeProposedLine({ ...clinicianOnly, confidence: 'established', requires_clinician: false, proposed_value: 1500, direction: 'lower' })).toBe('Proposed daily limit: at most 1500 mg');
    expect(intakeBaselineLine({ ...clinicianOnly, baseline_value: 2100 })).toBe('Recorded baseline: 2100 mg · condition');
    expect(intakeBaselineLine(clinicianOnly)).toBe('No recorded baseline · condition');
  });
});
