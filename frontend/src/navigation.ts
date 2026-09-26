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

/** What the app says when it cannot reach the API, naming the URL it actually tried. */
export function backendUnreachableNotice(baseUrl: string, detail?: string): { title: string; detail: string } {
  return {
    title: `Cannot reach the API at ${baseUrl}`,
    detail: [
      detail ? detail : 'The app could not open a connection to that address.',
      'Start it with: docker compose --env-file backend/.env up -d',
      'The API listens on port 8000; check EXPO_PUBLIC_API_URL in frontend/.env (then restart Expo, the value is baked in at build time).',
      'On a phone, use the computer\'s LAN address, or run adb reverse tcp:8000 tcp:8000 and set the URL to http://localhost:8000.',
    ].join(' '),
  };
}
