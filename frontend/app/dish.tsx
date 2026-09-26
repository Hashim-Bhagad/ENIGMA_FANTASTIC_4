import React, { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Card, PageHeader, Pill, Screen, Button } from '@/src/components/ui';
import { useApp } from '@/src/state/AppContext';
import { colors } from '@/src/theme';

const dishes = [
  { name: 'Paneer tikka', style: 'North Indian - grilled', icon: 'P', tags: ['Marinade', 'Shared grill'] },
  { name: 'Masala dosa', style: 'South Indian - fermented batter', icon: 'M', tags: ['Batter', 'Chutney'] },
  { name: 'Chole bhature', style: 'North Indian - curry & fried bread', icon: 'C', tags: ['Curry base', 'Frying oil'] },
  { name: 'Veg fried rice', style: 'Indo-Chinese - wok cooked', icon: 'V', tags: ['Sauce', 'Shared wok'] },
];
const questions = [
  'Does the dish or its marinade include any of my selected allergens?',
  'Are sauces, seasoning mixes, or toppings prepared separately?',
  'Is the same grill, pan, oil, or utensil used for other foods?',
];
export default function DishScreen() {
  const { allergens } = useApp();
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<(typeof dishes)[number] | null>(null);
  const [asked, setAsked] = useState<string[]>([]);
  const filtered = useMemo(() => dishes.filter(dish => dish.name.toLowerCase().includes(query.toLowerCase())), [query]);
  return <Screen>
    <PageHeader eyebrow="Eating out" title="Check a prepared dish" subtitle="Dish ingredients and preparation can vary. Use these prompts to ask the person preparing it." back />
    <Card style={st.disclaimer}><MaterialCommunityIcons name="chat-question-outline" size={19} color={colors.primary} /><Text style={st.disclaimerText}>A dish name is not an ingredient list. The result here is a question checklist, never a safety verdict.</Text></Card>
    {!selected ? <>
      <View style={st.search}><MaterialCommunityIcons name="magnify" size={20} color={colors.subtle} /><TextInput value={query} onChangeText={setQuery} placeholder="Search a dish" placeholderTextColor={colors.subtle} style={st.searchInput} /></View>
      <Text style={st.label}>DEMO DISHES</Text>
      <View style={{ gap: 9 }}>{filtered.map(dish => <Pressable key={dish.name} onPress={() => setSelected(dish)}><Card style={st.dishRow}><View style={st.dishIcon}><Text style={{ fontSize: 24 }}>{dish.icon}</Text></View><View style={{ flex: 1 }}><Text style={st.dishName}>{dish.name}</Text><Text style={st.dishSub}>{dish.style}</Text></View><MaterialCommunityIcons name="chevron-right" size={20} color={colors.subtle} /></Card></Pressable>)}</View>
      {!filtered.length && <Card style={st.empty}><Text style={st.dishName}>No dish match in this sample</Text><Text style={st.dishSub}>Try another name.</Text></Card>}
    </> : <>
      <Card style={st.selected}><View style={st.selectedTop}><View style={st.dishIcon}><Text style={{ fontSize: 24 }}>{selected.icon}</Text></View><View style={{ flex: 1 }}><Text style={st.dishName}>{selected.name}</Text><Text style={st.dishSub}>{selected.style}</Text></View><Pressable onPress={() => { setSelected(null); setAsked([]); }}><Text style={st.change}>Change</Text></Pressable></View><View style={st.tagRow}>{selected.tags.map(tag => <Pill key={tag} label={tag} tone="purple" />)}</View><View style={st.allergyNote}><MaterialCommunityIcons name="shield-outline" size={16} color={colors.red} /><Text style={st.allergyText}>Ask about your selected allergens: {allergens.length ? allergens.join(', ') : 'none selected'}.</Text></View></Card>
      <View style={st.stepHead}><Text style={st.stepTitle}>Questions for the preparer</Text><Pill label={`${asked.length}/${questions.length} asked`} tone="blue" /></View>
      <View style={{ gap: 9 }}>{questions.map((question, index) => { const done = asked.includes(question); return <Pressable key={question} onPress={() => setAsked(current => done ? current.filter(item => item !== question) : [...current, question])}><Card style={[st.question, done && st.questionDone]}><View style={[st.number, done && st.numberDone]}><Text style={[st.numberText, done && { color: '#FFFFFF' }]}>{done ? 'âœ“' : index + 1}</Text></View><Text style={st.questionText}>{question}</Text><MaterialCommunityIcons name={done ? 'check-circle' : 'circle-outline'} size={20} color={done ? colors.green : colors.subtle} /></Card></Pressable>; })}</View>
      <Card style={st.unknown}><MaterialCommunityIcons name="help-circle-outline" size={18} color={colors.amber} /><View style={{ flex: 1 }}><Text style={st.unknownTitle}>If they can't confirm</Text><Text style={st.unknownCopy}>Keep the ingredients or shared equipment unknown. Ask for another option with information you can verify.</Text></View></Card>
      <Button title="Finish dish check" icon="check" onPress={() => { setSelected(null); setAsked([]); }} secondary />
    </>}
  </Screen>;
}
const st = StyleSheet.create({
  disclaimer: { flexDirection: 'row', gap: 9, alignItems: 'flex-start', backgroundColor: colors.lavender }, disclaimerText: { flex: 1, color: colors.primaryDark, fontSize: 11, lineHeight: 16 }, search: { minHeight: 49, flexDirection: 'row', alignItems: 'center', gap: 9, paddingHorizontal: 13, borderRadius: 15, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: colors.line }, searchInput: { flex: 1, color: colors.ink, fontSize: 13 }, label: { color: colors.muted, fontSize: 9, fontWeight: '800', letterSpacing: 1 }, dishRow: { flexDirection: 'row', gap: 12, alignItems: 'center', padding: 13 }, dishIcon: { width: 47, height: 47, borderRadius: 16, backgroundColor: colors.orangeBg, alignItems: 'center', justifyContent: 'center' }, dishName: { color: colors.ink, fontSize: 13, fontWeight: '800' }, dishSub: { color: colors.muted, fontSize: 10, lineHeight: 14, marginTop: 4 }, empty: { alignItems: 'center', gap: 5, padding: 22 },
  selected: { gap: 13 }, selectedTop: { flexDirection: 'row', alignItems: 'center', gap: 11 }, change: { color: colors.primary, fontSize: 11, fontWeight: '800' }, tagRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 7 }, allergyNote: { flexDirection: 'row', gap: 8, alignItems: 'flex-start', padding: 10, backgroundColor: colors.redBg, borderRadius: 12 }, allergyText: { flex: 1, color: colors.red, fontSize: 10, lineHeight: 14, fontWeight: '600' }, stepHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }, stepTitle: { color: colors.ink, fontSize: 15, fontWeight: '800' }, question: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 13 }, questionDone: { backgroundColor: '#F5FBF7' }, number: { width: 27, height: 27, borderRadius: 10, backgroundColor: colors.lavender, alignItems: 'center', justifyContent: 'center' }, numberDone: { backgroundColor: colors.green }, numberText: { color: colors.primary, fontSize: 11, fontWeight: '800' }, questionText: { color: colors.ink, flex: 1, fontSize: 11, lineHeight: 16, fontWeight: '600' }, unknown: { flexDirection: 'row', alignItems: 'flex-start', gap: 9, backgroundColor: colors.amberBg }, unknownTitle: { color: '#785015', fontSize: 12, fontWeight: '800' }, unknownCopy: { color: '#785015', fontSize: 10, lineHeight: 14, marginTop: 3 },
});
