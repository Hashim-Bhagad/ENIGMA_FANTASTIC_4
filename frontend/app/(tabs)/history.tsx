import React, { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { router } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Card, PageHeader, Pill, Screen, SectionTitle } from '@/src/components/ui';
import { demoHistory } from '@/src/data/demo';
import { useApp } from '@/src/state/AppContext';
import { colors } from '@/src/theme';

export default function HistoryScreen() {
  const { products, setProduct, saved, toggleSaved } = useApp();
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<'All checks' | 'Saved'>('All checks');
  const items = useMemo(() => demoHistory.filter(row => {
    const matchesQuery = row.product.toLowerCase().includes(query.toLowerCase());
    const matchesFilter = filter === 'All checks' || saved.includes(row.id);
    return matchesQuery && matchesFilter;
  }), [query, filter, saved]);
  return <Screen>
    <PageHeader eyebrow="Your activity" title="History" subtitle="Reopen saved assessments and the product details you reviewed." />
    <View style={st.search}><MaterialCommunityIcons name="magnify" size={20} color={colors.subtle} /><TextInput value={query} onChangeText={setQuery} placeholder="Search your checks" placeholderTextColor={colors.subtle} style={st.searchInput} /></View>
    <View style={st.filters}>{(['All checks', 'Saved'] as const).map(value => <Pressable key={value} onPress={() => setFilter(value)} style={[st.filter, filter === value && st.filterActive]}><Text style={[st.filterText, filter === value && st.filterTextActive]}>{value}{value === 'Saved' ? ` - ${saved.length}` : ''}</Text></Pressable>)}</View>
    <SectionTitle title="Recent checks" action={`${items.length} shown`} />
    {items.length ? <View style={{ gap: 10 }}>{items.map(item => {
      const product = products.find(value => value.id === item.id) ?? products[0];
      const tone = item.tone === 'red' ? 'red' : item.tone === 'amber' ? 'amber' : 'blue';
      return <Pressable key={item.id} onPress={() => { setProduct(product); router.push('/assessment'); }}><Card style={st.row}>
        <View style={[st.icon, { backgroundColor: item.color }]}><Text style={{ fontSize: 23 }}>{item.icon}</Text></View>
        <View style={{ flex: 1 }}><Text style={st.name}>{item.product}</Text><Text style={st.date}>{item.date}</Text><View style={{ marginTop: 8 }}><Pill label={item.status} tone={tone} /></View></View>
        <Pressable accessibilityRole="button" accessibilityLabel={saved.includes(item.id) ? 'Remove from saved' : 'Save assessment'} onPress={event => { event.stopPropagation(); toggleSaved(item.id); }} style={st.bookmark}><MaterialCommunityIcons name={saved.includes(item.id) ? 'bookmark' : 'bookmark-outline'} color={saved.includes(item.id) ? colors.primary : colors.muted} size={19} /></Pressable>
      </Card></Pressable>;
    })}</View> : <Card style={st.empty}><MaterialCommunityIcons name="text-search" size={32} color={colors.subtle} /><Text style={st.name}>Nothing here yet</Text><Text style={st.date}>Try another search or choose All checks.</Text></Card>}
    <Card style={st.info}><MaterialCommunityIcons name="clock-alert-outline" size={19} color={colors.blue} /><Text style={st.infoText}>A saved assessment keeps the details you reviewed. If your profile changes, reassess the food to use your current details.</Text></Card>
  </Screen>;
}
const st = StyleSheet.create({
  search: { minHeight: 49, flexDirection: 'row', alignItems: 'center', gap: 9, paddingHorizontal: 13, borderRadius: 15, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: colors.line }, searchInput: { flex: 1, color: colors.ink, fontSize: 13 },
  filters: { flexDirection: 'row', gap: 8 }, filter: { borderRadius: 999, paddingHorizontal: 14, paddingVertical: 9, backgroundColor: '#ECEBF1' }, filterActive: { backgroundColor: colors.primary }, filterText: { color: colors.muted, fontSize: 11, fontWeight: '700' }, filterTextActive: { color: '#FFFFFF' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14 }, icon: { width: 49, height: 49, borderRadius: 16, alignItems: 'center', justifyContent: 'center' }, name: { color: colors.ink, fontSize: 13, fontWeight: '700' }, date: { color: colors.muted, fontSize: 10, lineHeight: 15, marginTop: 4 }, bookmark: { width: 34, height: 34, alignItems: 'center', justifyContent: 'center' }, empty: { alignItems: 'center', gap: 7, padding: 28 }, info: { backgroundColor: colors.blueBg, flexDirection: 'row', gap: 10, alignItems: 'flex-start' }, infoText: { color: '#285F7D', flex: 1, fontSize: 11, lineHeight: 16 },
});
