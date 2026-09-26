import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Card, DemoBanner, PageHeader, Pill, Screen, SectionTitle } from '@/src/components/ui';
import { demoProfile } from '@/src/data/demo';
import { useApp } from '@/src/state/AppContext';
import { colors } from '@/src/theme';

const options = ['Peanuts', 'Tree nuts', 'Milk', 'Eggs', 'Wheat', 'Sesame', 'Soy'];
export default function ProfileScreen() {
  const { allergens, toggleAllergen, conditions, toggleCondition, profileName, setProfileName, sodiumLimit, setSodiumLimit } = useApp();
  const [nameDraft, setNameDraft] = useState(profileName);
  const [saved, setSaved] = useState(false);
  const [vegetarian, setVegetarian] = useState(true);
  const [limitOpen, setLimitOpen] = useState(false);
  return <Screen>
    <PageHeader eyebrow="Personal details" title="Your profile" subtitle="Keep your selected ingredients and personal limits in one place." />
    <DemoBanner />
    <Card style={st.identity}>
      <View style={st.avatar}><Text style={st.avatarText}>{(profileName || 'A').slice(0, 1).toUpperCase()}</Text></View>
      <View style={{ flex: 1 }}><Text style={st.name}>{profileName}</Text><Text style={st.email}>{demoProfile.email} - demo account</Text></View>
      <Pill label="LOCAL PREVIEW" tone="purple" />
    </Card>
    <Card style={st.card}><SectionTitle title="About you" /><Text style={st.help}>A name helps identify your guide on this device.</Text><View style={st.inputWrap}><TextInput value={nameDraft} onChangeText={value => { setNameDraft(value); setSaved(false); }} placeholder="Your name" placeholderTextColor={colors.subtle} style={st.input} /></View></Card>
    <Card style={st.card}>
      <View style={st.section}><View style={[st.icon, { backgroundColor: colors.lavender }]}><MaterialCommunityIcons name="clipboard-heart-outline" size={20} color={colors.primary} /></View><View style={{ flex: 1 }}><Text style={st.sectionTitle}>Conditions for your guide</Text><Text style={st.help}>Select any that apply. A condition alone does not create foods to avoid.</Text></View></View>
      <View style={st.chips}>{['Food allergy', 'Diabetes', 'High blood pressure', 'Kidney disease', 'PCOS'].map(item => { const active = conditions.includes(item); return <Pressable key={item} onPress={() => { toggleCondition(item); setSaved(false); }} style={[st.chip, active && st.chipSelected]}><MaterialCommunityIcons name={active ? 'check-circle' : 'plus-circle-outline'} size={15} color={active ? colors.primary : colors.muted} /><Text style={[st.chipText, active && st.chipSelectedText]}>{item}</Text></Pressable>; })}</View>
      <Text style={st.conditionNote}>Condition-specific guidance requires reviewed evidence and may not be available in this preview.</Text>
    </Card>
    <Card style={st.card}>
      <View style={st.section}><View style={st.icon}><MaterialCommunityIcons name="shield-alert-outline" size={20} color={colors.red} /></View><View style={{ flex: 1 }}><Text style={st.sectionTitle}>Allergies & exclusions</Text><Text style={st.help}>Choose ingredients you want each label check to look for.</Text></View></View>
      <View style={st.chips}>{options.map(item => { const active = allergens.includes(item); return <Pressable key={item} onPress={() => { toggleAllergen(item); setSaved(false); }} style={[st.chip, active && st.chipActive]}><MaterialCommunityIcons name={active ? 'check-circle' : 'plus-circle-outline'} size={15} color={active ? colors.red : colors.muted} /><Text style={[st.chipText, active && st.chipTextActive]}>{item}</Text></Pressable>; })}</View>
      <View style={st.hint}><MaterialCommunityIcons name="information-outline" size={16} color={colors.amber} /><Text style={st.hintText}>An ingredient match and a "may contain" statement are shown separately in an assessment.</Text></View>
    </Card>
    <Card style={st.card}>
      <View style={st.section}><View style={[st.icon, { backgroundColor: colors.blueBg }]}><MaterialCommunityIcons name="tune-variant" size={20} color={colors.blue} /></View><View style={{ flex: 1 }}><Text style={st.sectionTitle}>Personal limits</Text><Text style={st.help}>Only add numeric limits from a source you trust.</Text></View></View>
      <View style={st.limit}><View style={{ flex: 1 }}><Text style={st.limitTitle}>Sodium</Text><Text style={st.help}>{sodiumLimit ? `${sodiumLimit} mg/day - preview only` : 'No personal limit recorded'}</Text></View><Pill label={sodiumLimit ? 'PREVIEW' : 'NOT SET'} tone={sodiumLimit ? 'blue' : 'neutral'} /></View>
      <Pressable onPress={() => setLimitOpen(value => !value)} style={st.addLimit}><MaterialCommunityIcons name={limitOpen ? 'minus' : 'plus'} size={17} color={colors.primary} /><Text style={st.addText}>{limitOpen ? 'Close limit entry' : 'Add a clinician-provided limit'}</Text></Pressable>
      {limitOpen && <View style={st.limitEditor}><Text style={st.help}>Daily sodium limit - mg</Text><TextInput value={sodiumLimit} onChangeText={value => { setSodiumLimit(value); setSaved(false); }} keyboardType="numeric" placeholder="Enter amount from your clinician" placeholderTextColor={colors.subtle} style={st.inputBox} /><Text style={st.conditionNote}>This local preview does not yet apply limits to an assessment.</Text></View>}
    </Card>
    <Card style={st.card}>
      <View style={st.section}><View style={[st.icon, { backgroundColor: colors.greenBg }]}><MaterialCommunityIcons name="leaf" size={20} color={colors.green} /></View><View style={{ flex: 1 }}><Text style={st.sectionTitle}>Food preferences</Text><Text style={st.help}>Preferences are separate from allergies and limits.</Text></View></View>
      <Pressable onPress={() => { setVegetarian(value => !value); setSaved(false); }} style={st.preference}><View style={{ flex: 1 }}><Text style={st.limitTitle}>Vegetarian</Text><Text style={st.help}>Use as a preference when comparing options</Text></View><View style={[st.toggle, vegetarian && st.toggleOn]}><View style={[st.knob, vegetarian && st.knobOn]} /></View></Pressable>
    </Card>
    <Pressable onPress={() => { setProfileName(nameDraft.trim() || 'Aarav'); setSaved(true); }} style={st.save}><MaterialCommunityIcons name={saved ? 'check' : 'content-save-outline'} size={18} color="#FFFFFF" /><Text style={st.saveText}>{saved ? 'Changes saved on this device' : 'Save profile'}</Text></Pressable>
    <Text style={st.disclaimer}>Your selected conditions can guide what the app asks about; they do not create a complete list of foods to avoid.</Text>
  </Screen>;
}
const st = StyleSheet.create({
  identity: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 15 }, avatar: { width: 48, height: 48, backgroundColor: colors.primary, borderRadius: 17, alignItems: 'center', justifyContent: 'center' }, avatarText: { color: '#FFFFFF', fontSize: 20, fontWeight: '800' }, name: { color: colors.ink, fontSize: 14, fontWeight: '800' }, email: { color: colors.muted, fontSize: 10, marginTop: 4 },
  card: { gap: 14 }, section: { flexDirection: 'row', alignItems: 'center', gap: 11 }, icon: { width: 42, height: 42, borderRadius: 14, backgroundColor: colors.redBg, alignItems: 'center', justifyContent: 'center' }, sectionTitle: { color: colors.ink, fontSize: 14, fontWeight: '700' }, help: { color: colors.muted, fontSize: 11, lineHeight: 16, marginTop: 4 }, inputWrap: { minHeight: 48, borderRadius: 14, borderWidth: 1, borderColor: colors.line, paddingHorizontal: 12, justifyContent: 'center' }, input: { color: colors.ink, fontSize: 13 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 }, chip: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 11, paddingVertical: 9, borderRadius: 999, backgroundColor: colors.canvas }, chipActive: { backgroundColor: colors.redBg }, chipText: { color: colors.muted, fontSize: 11, fontWeight: '700' }, chipTextActive: { color: colors.red }, chipSelected: { backgroundColor: colors.lavender }, chipSelectedText: { color: colors.primary }, conditionNote: { color: colors.subtle, fontSize: 10, lineHeight: 14 }, inputBox: { minHeight: 46, borderRadius: 14, borderWidth: 1, borderColor: colors.line, paddingHorizontal: 12, color: colors.ink, fontSize: 12 }, limitEditor: { gap: 7, paddingTop: 2 }, hint: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, backgroundColor: colors.amberBg, borderRadius: 12, padding: 10 }, hintText: { color: '#785015', fontSize: 10, lineHeight: 14, flex: 1 },
  limit: { flexDirection: 'row', alignItems: 'center', borderTopWidth: 1, borderColor: colors.line, paddingTop: 13 }, limitTitle: { color: colors.ink, fontSize: 12, fontWeight: '700' }, addLimit: { flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start' }, addText: { color: colors.primary, fontSize: 11, fontWeight: '700' }, preference: { flexDirection: 'row', alignItems: 'center', borderTopWidth: 1, borderColor: colors.line, paddingTop: 13 }, toggle: { width: 41, height: 24, borderRadius: 999, backgroundColor: '#DDDCE5', padding: 3, justifyContent: 'center' }, toggleOn: { backgroundColor: colors.primary }, knob: { width: 18, height: 18, borderRadius: 9, backgroundColor: '#FFFFFF' }, knobOn: { alignSelf: 'flex-end' }, save: { minHeight: 50, borderRadius: 999, backgroundColor: colors.primary, flexDirection: 'row', gap: 8, alignItems: 'center', justifyContent: 'center' }, saveText: { color: '#FFFFFF', fontSize: 13, fontWeight: '800' }, disclaimer: { textAlign: 'center', color: colors.subtle, fontSize: 10, lineHeight: 15, paddingHorizontal: 15 },
});
