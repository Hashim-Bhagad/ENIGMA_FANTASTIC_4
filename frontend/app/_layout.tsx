import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AppProvider } from '@/src/state/AppContext';
import { colors } from '@/src/theme';

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <AppProvider>
        <StatusBar style="dark" backgroundColor={colors.canvas} />
        <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.canvas } }}>
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
