import { Stack, useRouter, useSegments } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AppProvider } from '@/src/state/AppContext';
import { colors } from '@/src/theme';
import { useEffect } from 'react';
import { ActivityIndicator, View } from 'react-native';
import { useApp } from '@/src/state/AppContext';

function SessionGate() {
  const { authState } = useApp();
  const segments = useSegments();
  const router = useRouter();
  useEffect(() => {
    const route = segments[0];
    if (authState === 'loading') return;
    if (authState === 'signed-out' || authState === 'session-error') {
      if (route !== 'login') router.replace('/login');
    } else if (authState === 'profile-missing') {
      if (route !== '(tabs)' || segments[1] !== 'profile') router.replace('/(tabs)/profile');
    } else if (authState === 'ready' && route === 'login') router.replace('/(tabs)/guide');
  }, [authState, router, segments]);
  if (authState === 'loading') return <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.canvas }}><ActivityIndicator color={colors.primary} /></View>;
  return null;
}

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <AppProvider>
        <StatusBar style="dark" />
        <SessionGate />
        <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.canvas } }}>
          <Stack.Screen name="login" />
          <Stack.Screen name="(tabs)" />
          <Stack.Screen name="review" options={{ presentation: 'card' }} />
          <Stack.Screen name="assessment" options={{ presentation: 'card' }} />
          <Stack.Screen name="replacements" options={{ presentation: 'card' }} />
          <Stack.Screen name="dish" options={{ presentation: 'card' }} />
        </Stack>
      </AppProvider>
    </SafeAreaProvider>
  );
}
