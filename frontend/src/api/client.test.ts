import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

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
    vi.stubGlobal('fetch', vi.fn((_url: string, init: FetchInit) => {
      const { promise, reject } = Promise.withResolvers<never>();
      init.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
      return promise;
    }));
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
