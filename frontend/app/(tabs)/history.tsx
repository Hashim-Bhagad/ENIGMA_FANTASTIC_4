import React, { useCallback, useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { router, useFocusEffect } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Button, Card, PageHeader, Pill, Screen } from '@/src/components/ui';
import { statusTone } from '@/src/components/findings';
import { useApp } from '@/src/state/AppContext';
import { colors, radius, typography } from '@/src/theme';

export default function HistoryScreen() {
  const { history, historyTotal, hasMoreHistory, loadHistory, loadMoreHistory, openAssessment, busyFor, error } = useApp();
  const [query, setQuery] = useState('');
  // Refresh whenever the tab regains focus so new checks appear.
  useFocusEffect(useCallback(() => { void loadHistory(); }, [loadHistory]));
  const items = useMemo(() => history.filter(row => row.food.name.toLowerCase().includes(query.toLowerCase())), [history, query]);
  const open = async (id: string) => { try { await openAssessment(id); router.push('/assessment'); } catch { /* History refresh remains available if the record has changed. */ } };
  const loading = busyFor('history') && history.length === 0;
  return <Screen>
    <PageHeader title="History" subtitle="Assessments saved to your account." />
    <View style={st.search}><MaterialCommunityIcons name="magnify" size={20} color={colors.subtle} /><TextInput accessibilityLabel="Search your checks" value={query} onChangeText={setQuery} placeholder="Search your checks" placeholderTextColor={colors.subtle} style={st.searchInput} /></View>
    {error ? <Card style={st.error}><Text accessibilityRole="alert" style={st.errorText}>{error}</Text><Button title="Retry" compact secondary onPress={() => void loadHistory()} /></Card> : null}
    <Text style={st.heading}>{loading ? 'Loading checks…' : `${items.length} of ${historyTotal} checks`}</Text>
    {items.length ? <View style={{ gap: 10 }}>{items.map(item => {
      const tone = statusTone(item.result.status);
      return <Pressable key={item.id} accessibilityRole="button" accessibilityLabel={`Open ${item.food.name}`} onPress={() => void open(item.id)} style={({ pressed }) => pressed && st.pressed}><Card style={st.row}><View style={st.icon}><MaterialCommunityIcons name="food-apple-outline" size={22} color={colors.primary} /></View><View style={{ flex: 1 }}><Text style={st.name}>{item.food.name}</Text><Text style={st.date}>{new Date(item.created_at).toLocaleString()}</Text><View style={{ marginTop: 8 }}><Pill label={item.result.status.replaceAll('_', ' ')} tone={tone} /></View></View><MaterialCommunityIcons name="chevron-right" size={20} color={colors.subtle} /></Card></Pressable>;
    })}</View> : <Card style={st.empty}><MaterialCommunityIcons name="text-search" size={32} color={colors.subtle} /><Text style={st.name}>{loading ? 'Loading your history' : 'Nothing here yet'}</Text><Text style={st.date}>Complete a product assessment and it will be saved here.</Text></Card>}
    {hasMoreHistory && !query ? <Button title={busyFor('history') ? 'Loading…' : 'Load more'} loading={busyFor('history')} icon="chevron-down" secondary onPress={() => void loadMoreHistory()} /> : null}
    <Card style={st.info}><MaterialCommunityIcons name="clock-alert-outline" size={19} color={colors.blue} /><Text style={st.infoText}>Each assessment keeps the profile version and label observations used. If your profile changes, create a new assessment.</Text></Card>
  </Screen>;
}
const st = StyleSheet.create({
  search: { minHeight: 52, flexDirection: 'row', alignItems: 'center', gap: 9, paddingHorizontal: 14, borderRadius: radius.control, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.stroke },
  searchInput: { flex: 1, color: colors.ink, fontSize: 16 },
  heading: { ...typography.bodyStrong, color: colors.ink },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 16 },
  icon: { width: 48, height: 48, borderRadius: radius.tile, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.lavender },
  name: { ...typography.cardTitle, color: colors.ink },
  date: { ...typography.meta, color: colors.muted, marginTop: 4 },
  empty: { alignItems: 'center', gap: 8, padding: 28 },
  info: { backgroundColor: colors.blueBg, flexDirection: 'row', gap: 10, alignItems: 'flex-start' },
  infoText: { color: colors.blueInk, flex: 1, ...typography.meta },
  error: { backgroundColor: colors.redBg, gap: 9 },
  errorText: { ...typography.meta, color: colors.red },
  pressed: { opacity: 0.9 },
});
