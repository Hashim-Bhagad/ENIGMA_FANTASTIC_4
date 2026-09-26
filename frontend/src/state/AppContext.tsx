import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { Allergen, api, ApiError, Assessment, DishAssessment, DishPayload, EU_ALLERGENS, FoodObservation, IntakeTarget, isNutrient, ProfilesGuide, ProfileData, Recommendation, SavedProfile, setUnauthorizedHandler, toProduct, type Product } from '@/src/api/client';
import { session } from '@/src/api/session';

export type AuthState = 'loading' | 'signed-out' | 'profile-missing' | 'ready' | 'session-error';
export type Operation = 'auth' | 'search' | 'barcode' | 'label' | 'assess' | 'recommend' | 'history' | 'profile' | 'guide' | 'dish';

export type DishIngredientDraft = { key: string; text: string; referenceCode: string | null; grams: string };
export type DishDraft = { name: string; ingredients: DishIngredientDraft[]; cookingNotes: string[]; declarationsConfirmed: boolean; portion: string };

const EMPTY_PROFILE: ProfileData = { conditions: [], allergies: [], ingredient_exclusions: [], limits: [], goals: [], preferences: '' };
const EMPTY_DISH: DishDraft = { name: '', ingredients: [{ key: 'row-1', text: '', referenceCode: null, grams: '' }], cookingNotes: [], declarationsConfirmed: false, portion: '' };
const UI_TO_ALLERGEN: Record<string, Allergen> = Object.fromEntries(EU_ALLERGENS.map(({ value, label }) => [label, value]));
const ALLERGEN_TO_UI = Object.fromEntries(EU_ALLERGENS.map(({ value, label }) => [value, label])) as Record<Allergen, string>;
const EMPTY_FOOD: FoodObservation = { name: 'New product', brand: null, barcode: null, category: null, basis: null, ingredients_text: null, advisories_text: null, ingredients_complete: false, advisories_complete: false, declared_allergens: [], precautionary_allergens: [], reported_allergens: [], nutrients: {}, source: { kind: 'manual', reference: 'User entered label observations', warnings: [] } };
const HISTORY_PAGE_SIZE = 20;

type AppContextValue = {
  authState: AuthState; authError: string; token: string | null; email: string;
  authenticate: (email: string, password: string, create: boolean) => Promise<void>;
  retrySession: () => Promise<void>; signOut: () => Promise<void>;
  profile: SavedProfile | null; profileDraft: ProfileData; setProfileDraft: (data: ProfileData) => void; saveProfile: () => Promise<void>; applyIntakeTarget: (target: IntakeTarget) => Promise<SavedProfile>;
  product: Product; setProduct: (product: Product) => void; products: Product[]; setProducts: (products: Product[]) => void;
  search: string; setSearch: (value: string) => void; catalogMessage: string; loadCatalog: () => Promise<void>; searchCatalog: (query: string) => Promise<void>; lookupBarcode: (barcode: string) => Promise<Product>;
  allergens: string[]; toggleAllergen: (value: string) => void; conditions: string[]; toggleCondition: (value: string) => void;
  labelPhoto: string | null; setLabelPhoto: (uri: string | null) => void; sodiumLimit: string; setSodiumLimit: (value: string) => void;
  extractLabel: (photo: { uri: string; name?: string | null; mimeType?: string | null }) => Promise<Product>;
  assessment: Assessment | null; createAssessment: (portion: number | null, food?: FoodObservation) => Promise<Assessment>;
  recommendation: Recommendation | null; getRecommendations: () => Promise<Recommendation>;
  history: Assessment[]; historyTotal: number; hasMoreHistory: boolean; loadHistory: () => Promise<void>; loadMoreHistory: () => Promise<void>; openAssessment: (id: string) => Promise<void>;
  guide: ProfilesGuide | null; guideError: string; loadGuide: () => Promise<void>;
  dishDraft: DishDraft; setDishDraft: (draft: DishDraft) => void; dishResult: DishAssessment | null; assessDish: (draft?: DishDraft) => Promise<DishAssessment>; clearDish: () => void;
  busy: boolean; busyFor: (name: Operation) => boolean; error: string; clearError: () => void;
};

const Context = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: React.PropsWithChildren) {
  const [authState, setAuthState] = useState<AuthState>('loading');
  const [token, setToken] = useState<string | null>(null);
  const [email, setEmail] = useState('');
  const [authError, setAuthError] = useState('');
  const [error, setError] = useState('');
  const [operations, setOperations] = useState<Partial<Record<Operation, boolean>>>({});
  const [profile, setProfile] = useState<SavedProfile | null>(null);
  const [profileDraft, setProfileDraft] = useState<ProfileData>(EMPTY_PROFILE);
  const [product, setProduct] = useState<Product>(() => toProduct('new-label', EMPTY_FOOD));
  const [products, setProducts] = useState<Product[]>([]);
  const [search, setSearch] = useState('');
  const [catalogMessage, setCatalogMessage] = useState('');
  const [labelPhoto, setLabelPhoto] = useState<string | null>(null);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [history, setHistory] = useState<Assessment[]>([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [guide, setGuide] = useState<ProfilesGuide | null>(null);
  const [guideError, setGuideError] = useState('');
  const [dishDraft, setDishDraft] = useState<DishDraft>(EMPTY_DISH);
  const [dishResult, setDishResult] = useState<DishAssessment | null>(null);

  const withOperation = useCallback(async <T,>(name: Operation, task: () => Promise<T>): Promise<T> => {
    setOperations(current => ({ ...current, [name]: true }));
    try { return await task(); }
    finally { setOperations(current => ({ ...current, [name]: false })); }
  }, []);

  const hydrate = useCallback(async (accessToken: string, currentEmail?: string) => {
    setToken(accessToken);
    const identity = currentEmail ? { email: currentEmail } : await api.me(accessToken);
    setEmail(identity.email);
    try {
      const current = await api.profile(accessToken);
      setProfile(current); setProfileDraft(current.data); setAuthState('ready');
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 404) {
        setProfile(null); setProfileDraft(EMPTY_PROFILE); setAuthState('profile-missing');
      } else throw cause;
    }
  }, []);

  const resetSessionState = useCallback(() => {
    setToken(null); setEmail(''); setProfile(null); setProfileDraft(EMPTY_PROFILE);
    setAssessment(null); setRecommendation(null); setHistory([]); setHistoryTotal(0);
    setGuide(null); setGuideError(''); setDishResult(null); setError('');
  }, []);

  const restoreSession = useCallback(async () => {
    setAuthState('loading'); setAuthError('');
    const existing = await session.get();
    if (!existing) { setToken(null); setAuthState('signed-out'); return; }
    try { await hydrate(existing); }
    catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) { await session.clear(); resetSessionState(); setAuthState('signed-out'); }
      else { setAuthError(cause instanceof Error ? cause.message : 'Could not load your account.'); setAuthState('session-error'); }
    }
  }, [hydrate, resetSessionState]);

  useEffect(() => { void restoreSession(); }, [restoreSession]);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      // The client already cleared the stored token before invoking this hook.
      resetSessionState(); setAuthError(''); setAuthState('signed-out');
    });
    return () => setUnauthorizedHandler(null);
  }, [resetSessionState]);

  const authenticate = useCallback(async (userEmail: string, password: string, create: boolean) => {
    await withOperation('auth', async () => {
      setError('');
      const result = create ? await api.register(userEmail, password) : await api.login(userEmail, password);
      await session.set(result.access_token);
      await hydrate(result.access_token, result.user.email);
    });
  }, [hydrate, withOperation]);

  const signOut = useCallback(async () => {
    await session.clear();
    resetSessionState(); setAuthState('signed-out');
  }, [resetSessionState]);

  const persistProfile = useCallback(async (draft: ProfileData) => {
    if (!token) throw new ApiError('Sign in before saving your profile.', 401, 'unauthorized');
    setError('');
    try {
      const updated = await api.saveProfile(token, draft, profile?.version ?? null);
      setProfile(updated); setProfileDraft(updated.data); setAuthState('ready');
      return updated;
    } catch (cause) {
      if (cause instanceof ApiError && (cause.code === 'profile_version_stale' || cause.status === 409)) {
        // Keep the user's edits and adopt the server version so a retry can succeed.
        try { const current = await api.profile(token); setProfile(current); } catch { /* The save error below still explains the conflict. */ }
        setError('Your saved profile changed elsewhere. We kept your current edits; review them and save again to store them.');
      } else {
        setError(cause instanceof Error ? cause.message : 'Your profile could not be saved.');
      }
      throw cause;
    }
  }, [profile, token]);

  const saveProfile = useCallback(async () => {
    await withOperation('profile', () => persistProfile(profileDraft));
  }, [persistProfile, profileDraft, withOperation]);

  /**
   * Record one confirmed intake target as a profile limit. A proposal only becomes a limit
   * once the user accepts it here; the plan itself never writes to the profile.
   */
  const applyIntakeTarget = useCallback(async (target: IntakeTarget) => {
    if (!profile) throw new ApiError('Save a profile before recording a target.', 409, 'conflict');
    if (!isNutrient(target.nutrient) || target.proposed_value == null || !target.suggested_limit_source) {
      throw new ApiError('This target cannot be recorded from the plan.', 400, 'validation_error');
    }
    const nutrient = target.nutrient;
    const maximum = target.proposed_value;
    const source = target.suggested_limit_source;
    const nextDraft: ProfileData = {
      ...profileDraft,
      limits: [...profileDraft.limits.filter(limit => !(limit.nutrient === nutrient && limit.scope === target.limit_scope)), { nutrient, maximum, scope: target.limit_scope, source }],
      goals: target.direction === 'maintain' ? profileDraft.goals.filter(goal => goal.nutrient !== nutrient) : [...profileDraft.goals.filter(goal => goal.nutrient !== nutrient), { nutrient, direction: target.direction }],
    };
    return withOperation('profile', () => persistProfile(nextDraft));
  }, [persistProfile, profile, profileDraft, withOperation]);

  const toggleAllergen = useCallback((label: string) => {
    const key = UI_TO_ALLERGEN[label]; if (!key) return;
    setProfileDraft(current => ({ ...current, allergies: current.allergies.includes(key) ? current.allergies.filter(x => x !== key) : [...current.allergies, key] }));
  }, []);
  const toggleCondition = useCallback((slug: string) => {
    setProfileDraft(current => ({ ...current, conditions: current.conditions.includes(slug) ? current.conditions.filter(value => value !== slug) : [...current.conditions, slug] }));
  }, []);
  const setSodiumLimit = useCallback((value: string) => {
    setProfileDraft(current => {
      const limits = current.limits.filter(limit => !(limit.nutrient === 'sodium_mg' && limit.scope === 'daily'));
      const goals = current.goals.filter(goal => goal.nutrient !== 'sodium_mg');
      if (!value.trim()) return { ...current, limits, goals };
      const maximum = Number(value);
      if (!Number.isFinite(maximum) || maximum <= 0) return current;
      return { ...current, limits: [...limits, { nutrient: 'sodium_mg', maximum, scope: 'daily', source: 'User-entered clinician-provided limit' }], goals: [...goals, { nutrient: 'sodium_mg', direction: 'lower' }] };
    });
  }, []);

  const searchCatalog = useCallback(async (query: string) => {
    if (!token) throw new ApiError('Sign in to search products.', 401, 'unauthorized');
    await withOperation('search', async () => {
      setError('');
      try { const result = await api.search(token, query.trim(), true); setProducts(result.products.map(item => toProduct(item.id, item.food))); setCatalogMessage(result.live_status === 'unavailable' ? `Showing saved records. Live search is unavailable. ${result.message || ''}` : result.live_status === 'completed' ? 'Saved records and Open Food Facts results. Confirm each current package label.' : 'Saved product records. Confirm each current package label.'); }
      catch (cause) { setError(cause instanceof Error ? cause.message : 'Product search failed.'); throw cause; }
    });
  }, [token, withOperation]);
  const loadCatalog = useCallback(async () => {
    if (!token) return;
    await withOperation('search', async () => {
      setError('');
      try { const result = await api.catalog(token); setProducts(result.products.map(item => toProduct(item.id, item.food))); setCatalogMessage('Up to 50 saved product records. Search to discover more through Open Food Facts.'); }
      catch (cause) { setError(cause instanceof Error ? cause.message : 'Catalog could not be loaded.'); throw cause; }
    });
  }, [token, withOperation]);
  const lookupBarcode = useCallback(async (code: string) => {
    if (!token) throw new ApiError('Sign in to look up a barcode.', 401, 'unauthorized');
    return withOperation('barcode', async () => {
      setError('');
      try { const result = await api.barcode(token, code.trim()); const next = toProduct(result.id, result.food); setProduct(next); setProducts(current => [next, ...current.filter(item => item.id !== next.id)]); return next; }
      catch (cause) { setError(cause instanceof Error ? cause.message : 'Barcode lookup failed.'); throw cause; }
    });
  }, [token, withOperation]);
  const extractLabel = useCallback(async (photo: { uri: string; name?: string | null; mimeType?: string | null }) => {
    if (!token) throw new ApiError('Sign in to extract a label.', 401, 'unauthorized');
    return withOperation('label', async () => {
      setError('');
      try { const result = await api.extractLabel(token, photo); setLabelPhoto(photo.uri); const next = toProduct(`photo-${Date.now()}`, result.food); setProduct(next); return next; }
      catch (cause) { setError(cause instanceof Error ? cause.message : 'Label extraction failed.'); throw cause; }
    });
  }, [token, withOperation]);

  const refreshHistory = useCallback(async () => {
    if (!token) return;
    const page = await api.history(token, HISTORY_PAGE_SIZE, 0);
    setHistory(page.assessments); setHistoryTotal(page.total);
  }, [token]);

  const createAssessment = useCallback(async (portion: number | null, food?: FoodObservation) => {
    if (!token || !profile) throw new ApiError('Save a profile before assessing a product.', 409, 'conflict');
    return withOperation('assess', async () => {
      setError('');
      try {
        const observation = food ?? product.observation ?? { ...EMPTY_FOOD, name: product.name, brand: product.brand, barcode: product.barcode || null, ingredients_text: product.ingredients || null, advisories_text: product.advisory, basis: product.basis === 'per 100 g' ? '100g' : product.basis === 'per 100 ml' ? '100ml' : null, nutrients: product.sodium == null ? {} : { sodium_mg: product.sodium } };
        const next = await api.assess(token, profile, observation, portion);
        setAssessment(next); setRecommendation(null);
        // Surface the new check in history without requiring an app restart.
        void refreshHistory().catch(() => undefined);
        return next;
      }
      catch (cause) { setError(cause instanceof Error ? cause.message : 'Assessment failed.'); throw cause; }
    });
  }, [product, profile, token, refreshHistory, withOperation]);

  const getRecommendations = useCallback(async () => {
    if (!token || !assessment) throw new ApiError('Create an assessment before requesting replacements.', 409, 'conflict');
    return withOperation('recommend', async () => {
      setError('');
      try { const next = await api.recommend(token, assessment.id, profileDraft.preferences || undefined); setRecommendation(next); return next; }
      catch (cause) { setError(cause instanceof Error ? cause.message : 'Replacement search failed.'); throw cause; }
    });
  }, [assessment, profileDraft.preferences, token, withOperation]);

  const loadHistory = useCallback(async () => {
    if (!token) return;
    await withOperation('history', async () => {
      setError('');
      try { await refreshHistory(); }
      catch (cause) { setError(cause instanceof Error ? cause.message : 'History could not be loaded.'); }
    });
  }, [token, refreshHistory, withOperation]);

  const hasMoreHistory = history.length < historyTotal;

  const loadMoreHistory = useCallback(async () => {
    if (!token || !hasMoreHistory) return;
    await withOperation('history', async () => {
      setError('');
      try {
        const page = await api.history(token, HISTORY_PAGE_SIZE, history.length);
        setHistory(current => [...current, ...page.assessments.filter(item => !current.some(existing => existing.id === item.id))]);
        setHistoryTotal(page.total);
      } catch (cause) { setError(cause instanceof Error ? cause.message : 'More history could not be loaded.'); }
    });
  }, [token, hasMoreHistory, history.length, withOperation]);

  const openAssessment = useCallback(async (id: string) => {
    if (!token) throw new ApiError('Sign in to open assessment history.', 401, 'unauthorized');
    const opened = await api.assessment(token, id); setAssessment(opened); setProduct(toProduct(opened.id, opened.food)); setRecommendation(null);
  }, [token]);

  const loadGuide = useCallback(async () => {
    if (!token || !profile) { setGuide(null); return; }
    await withOperation('guide', async () => {
      setGuideError('');
      try { setGuide(await api.profilesGuide(token, profile.id, profile.version)); }
      catch (cause) { setGuideError(cause instanceof Error ? cause.message : 'Guidance could not be loaded.'); }
    });
  }, [token, profile, withOperation]);

  /**
   * Assess a draft. Callers that attach a reference or an amount from the result view pass the
   * updated draft directly, so the check never runs against the state it is replacing.
   */
  const assessDish = useCallback(async (draft?: DishDraft) => {
    const source = draft ?? dishDraft;
    if (!token || !profile) throw new ApiError('Save a profile before assessing a cooked meal.', 409, 'conflict');
    const name = source.name.trim();
    if (!name) throw new ApiError('Enter the dish name before assessing.', 400, 'validation_error');
    const ingredients: DishPayload['ingredients'] = [];
    for (const row of source.ingredients) {
      const text = row.text.trim();
      if (!text) continue;
      const grams = row.grams.trim() ? Number(row.grams) : null;
      if (grams !== null && (!Number.isFinite(grams) || grams <= 0)) throw new ApiError('Ingredient grams must be a positive number or left blank.', 400, 'validation_error');
      ingredients.push({ text, reference_code: row.referenceCode, grams });
    }
    if (!ingredients.length) throw new ApiError('Add at least one ingredient before assessing.', 400, 'validation_error');
    const portionG = source.portion.trim() ? Number(source.portion) : null;
    if (portionG !== null && (!Number.isFinite(portionG) || portionG <= 0)) throw new ApiError('Portion must be a positive number or left blank.', 400, 'validation_error');
    const payload: DishPayload = { profile_id: profile.id, profile_version: profile.version, name, ingredients, cooking_notes: source.cookingNotes, declarations_confirmed: source.declarationsConfirmed, portion_g: portionG };
    return withOperation('dish', async () => {
      setError('');
      try { const result = await api.assessDish(token, payload); setDishResult(result); return result; }
      catch (cause) { setError(cause instanceof Error ? cause.message : 'The cooked meal could not be assessed.'); throw cause; }
    });
  }, [dishDraft, profile, token, refreshHistory, withOperation]);

  const clearDish = useCallback(() => { setDishResult(null); setDishDraft(EMPTY_DISH); }, []);

  const allergens = profileDraft.allergies.map(value => ALLERGEN_TO_UI[value]).filter(Boolean);
  const conditions = profileDraft.conditions;
  const sodiumLimit = String(profileDraft.limits.find(item => item.nutrient === 'sodium_mg' && item.scope === 'daily')?.maximum ?? '');
  const busy = Object.values(operations).some(Boolean);
  const busyFor = useCallback((name: Operation) => Boolean(operations[name]), [operations]);
  const value = useMemo<AppContextValue>(() => ({
    authState, authError, token, email, authenticate, retrySession: restoreSession, signOut,
    profile, profileDraft, setProfileDraft, saveProfile, applyIntakeTarget,
    product, setProduct, products, setProducts,
    search, setSearch, catalogMessage, loadCatalog, searchCatalog, lookupBarcode, allergens, toggleAllergen, conditions, toggleCondition,
    labelPhoto, setLabelPhoto, sodiumLimit, setSodiumLimit, extractLabel,
    assessment, createAssessment, recommendation, getRecommendations,
    history, historyTotal, hasMoreHistory, loadHistory, loadMoreHistory, openAssessment,
    guide, guideError, loadGuide,
    dishDraft, setDishDraft, dishResult, assessDish, clearDish,
    busy, busyFor, error, clearError: () => setError(''),
  }), [authState, authError, token, email, authenticate, restoreSession, signOut, profile, profileDraft, saveProfile, applyIntakeTarget, product, products, search, catalogMessage, loadCatalog, searchCatalog, lookupBarcode, allergens, toggleAllergen, conditions, toggleCondition, labelPhoto, sodiumLimit, setSodiumLimit, extractLabel, assessment, createAssessment, recommendation, getRecommendations, history, historyTotal, hasMoreHistory, loadHistory, loadMoreHistory, openAssessment, guide, guideError, loadGuide, dishDraft, dishResult, assessDish, clearDish, busy, busyFor, error]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useApp() {
  const context = useContext(Context);
  if (!context) throw new Error('useApp must be used inside AppProvider');
  return context;
}
