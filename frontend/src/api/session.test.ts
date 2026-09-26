import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('react-native', () => ({ Platform: { OS: 'web' } }));
vi.mock('expo-secure-store', () => ({ getItemAsync: vi.fn(), setItemAsync: vi.fn(), deleteItemAsync: vi.fn() }));

describe('session storage', () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.resetModules(); });

  it('reads, writes and clears the token through web localStorage', async () => {
    const store = new Map<string, string>();
    vi.stubGlobal('localStorage', {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => { store.set(key, value); },
      removeItem: (key: string) => { store.delete(key); },
    });
    const { session } = await import('./session');
    expect(await session.get()).toBeNull();
    await session.set('access-123');
    expect(store.get('safebitez.access-token')).toBe('access-123');
    expect(await session.get()).toBe('access-123');
    await session.clear();
    expect(await session.get()).toBeNull();
    expect(store.has('safebitez.access-token')).toBe(false);
  });

  it('reports no token when the browser has no localStorage', async () => {
    vi.stubGlobal('localStorage', undefined);
    const { session } = await import('./session');
    await expect(session.get()).resolves.toBeNull();
  });
});
