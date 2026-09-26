import { Tabs } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { colors } from '@/src/theme';

const icons: Record<string, keyof typeof MaterialCommunityIcons.glyphMap> = {
  guide: 'compass-outline', scan: 'barcode-scan', history: 'history', profile: 'account-circle-outline',
};
const labels: Record<string, string> = { guide: 'Guide', scan: 'Scan', history: 'History', profile: 'Profile' };

export default function TabLayout() {
  return (
    <Tabs screenOptions={({ route }) => ({
      headerShown: false,
      tabBarActiveTintColor: colors.primary,
      tabBarInactiveTintColor: colors.muted,
      tabBarLabelStyle: { fontSize: 11, fontWeight: '700', marginBottom: 3 },
      tabBarStyle: { height: 72, paddingTop: 8, paddingBottom: 7, backgroundColor: '#FFFFFF', borderTopWidth: 0, elevation: 10, shadowColor: '#3525A8', shadowOpacity: 0.08, shadowRadius: 18 },
      tabBarIcon: ({ color, size }) => <MaterialCommunityIcons name={icons[route.name] ?? 'circle-outline'} color={color} size={size} />,
      tabBarLabel: labels[route.name] ?? route.name,
    })}>
      <Tabs.Screen name="guide" />
      <Tabs.Screen name="scan" />
      <Tabs.Screen name="history" />
      <Tabs.Screen name="profile" />
    </Tabs>
  );
}
