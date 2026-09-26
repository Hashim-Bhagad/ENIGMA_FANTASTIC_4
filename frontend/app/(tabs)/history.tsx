import React, { useCallback, useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { router, useFocusEffect } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Button, Card, PageHeader, Pill, Screen } from '@/src/components/ui';
import { statusTone } from '@/src/components/findings';
import { useApp } from '@/src/state/AppContext';
import { colors, radius } from '@/src/theme';

export default function HistoryScreen() {
  const { history, historyTotal, hasMoreHistory, loadHistory, loadMoreHistory, openAssessment, busyFor, error } = useApp();
  const [query, setQuery] = useState('');
  // Refresh whenever the tab regains focus so new checks appear.
  useFocusEffect(useCallback(() => { void loadHistory(); }, [loadHistory]));
  const items = useMemo(() => history.filter(row => row.food.name.toLowerCase().includes(query.toLowerCase())), [history, query]);
  const open = async (id: string) => { try { await openAssessment(id); router.push('/assessment'); } catch { /* History refresh remains available if the record has changed. */ } };
  const loading = busyFor('history') && history.length === 0;
  return <Screen>
    <PageHeader eyebrow="Your activity" title="History" subtitle="Assessments saved to your account." />
    <View style={st.search}><MaterialCommunityIcons name="magnify" size={20} color={colors.subtle} /><TextInput accessibilityLabel="Search your checks" value={query} onChangeText={setQuery} placeholder="Search your checks" placeholderTextColor={colors.subtle} style={st.searchInput} /></View>
    {error ? <Card style={st.error}><Text accessibilityRole="alert" style={st.errorText}>{error}</Text><Button title="Retry" compact secondary onPress={() => void loadHistory()} /></Card> : null}
    <Text style={st.heading}>{loading ? 'Loading checks…' : `${items.length} of ${historyTotal} checks`}</Text>
    {items.length ? <View style={{ gap: 10 }}>{items.map(item => {
      const tone = statusTone(item.result.status);
      return <Pressable key={item.id} accessibilityRole="button" accessibilityLabel={`Open ${item.food.name}`} onPress={() => void open(item.id)}><Card style={st.row}><View style={st.icon}><MaterialCommunityIcons name="food-apple-outline" size={22} color={colors.primary} /></View><View style={{ flex: 1 }}><Text style={st.name}>{item.food.name}</Text><Text style={st.date}>{new Date(item.created_at).toLocaleString()}</Text><View style={{ marginTop: 8 }}><Pill label={item.result.status.replaceAll('_', ' ')} tone={tone} /></View></View><MaterialCommunityIcons name="chevron-right" size={20} color={colors.subtle} /></Card></Pressable>;
    })}</View> : <Card style={st.empty}><MaterialCommunityIcons name="text-search" size={32} color={colors.subtle} /><Text style={st.name}>{loading ? 'Loading your history' : 'Nothing here yet'}</Text><Text style={st.date}>Complete a product assessment and it will be saved here.</Text></Card>}
    {hasMoreHistory && !query ? <Button title={busyFor('history') ? 'Loading…' : 'Load more'} loading={busyFor('history')} icon="chevron-down" secondary onPress={() => void loadMoreHistory()} /> : null}
    <Card style={st.info}><MaterialCommunityIcons name="clock-alert-outline" size={19} color={colors.blue} /><Text style={st.infoText}>Each assessment keeps the profile version and label observations used. If your profile changes, create a new assessment.</Text></Card>
  </Screen>;
}
const st = StyleSheet.create({ search: { minHeight: 49, flexDirection: 'row', alignItems: 'center', gap: 9, paddingHorizontal: 13, borderRadius: radius.input, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line }, searchInput: { flex: 1, color: colors.ink, fontSize: 13 }, heading: { fontSize: 15, color: colors.ink, fontWeight: '800' }, row: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14 }, icon: { width: 49, height: 49, borderRadius: radius.tile, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.lavender }, name: { color: colors.ink, fontSize: 13, fontWeight: '700' }, date: { color: colors.muted, fontSize: 10, lineHeight: 15, marginTop: 4 }, empty: { alignItems: 'center', gap: 7, padding: 28 }, info: { backgroundColor: colors.blueBg, flexDirection: 'row', gap: 10, alignItems: 'flex-start' }, infoText: { color: colors.blueInk, flex: 1, fontSize: 11, lineHeight: 16 }, error: { backgroundColor: colors.redBg, gap: 9 }, errorText: { color: colors.red, fontSize: 12, lineHeight: 17 } });
