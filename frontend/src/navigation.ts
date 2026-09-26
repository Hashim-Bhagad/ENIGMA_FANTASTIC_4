/**
 * Navigation fallbacks that cannot dead-end.
 *
 * A screen opened from a deep link, or reached after a `replace` redirect (the session gate uses
 * one), has nothing to pop. React Navigation answers `router.back()` with a development warning
 * and the control appears to do nothing, so the back arrow falls back to a real destination.
 */

/** The tab the app treats as home. */
export const HOME_TAB = '/(tabs)/guide';

/** What a back action should do: pop when possible, otherwise replace with the fallback. */
export function backAction(canGoBack: boolean, fallback: string = HOME_TAB): { replace?: string } {
  return canGoBack ? {} : { replace: fallback };
}
