import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Button, Card, PageHeader, Pill, Screen, SectionTitle } from '@/src/components/ui';
import { useApp } from '@/src/state/AppContext';
import { colors, radius } from '@/src/theme';

const allergens = ['Peanuts', 'Tree nuts', 'Milk', 'Eggs', 'Wheat', 'Sesame', 'Soy', 'Fish', 'Shellfish'];
const conditions = ['Diabetes', 'High blood pressure', 'Kidney disease', 'PCOS'];

export default function ProfileScreen() {
  const { email, profile, profileDraft, setProfileDraft, allergens: selectedAllergens, toggleAllergen, conditions: selectedConditions, toggleCondition, sodiumLimit, setSodiumLimit, saveProfile, signOut, busyFor, error, clearError } = useApp();
  const [saved, setSaved] = useState(false);
  const [limitOpen, setLimitOpen] = useState(Boolean(sodiumLimit));
  const [exclusion, setExclusion] = useState('');
  const vegetarian = profileDraft.preferences.toLowerCase().includes('vegetarian');
  const saving = busyFor('profile');
  const doSave = async () => { clearError(); try { await saveProfile(); setSaved(true); } catch { setSaved(false); } };
  const addExclusion = () => {
    const value = exclusion.trim();
    if (value.length < 2 || profileDraft.ingredient_exclusions.includes(value)) { setExclusion(''); return; }
    setProfileDraft({ ...profileDraft, ingredient_exclusions: [...profileDraft.ingredient_exclusions, value] });
    setExclusion(''); setSaved(false);
  };
  const removeExclusion = (value: string) => {
    setProfileDraft({ ...profileDraft, ingredient_exclusions: profileDraft.ingredient_exclusions.filter(item => item !== value) });
    setSaved(false);
  };
  return <Screen>
    <PageHeader eyebrow="Personal details" title="Your profile" subtitle="These saved settings are used for your product checks." />
    <Card style={st.identity}><View style={st.avatar}><Text style={st.avatarText}>{(email || 'A').slice(0, 1).toUpperCase()}</Text></View><View style={{ flex: 1 }}><Text style={st.name}>{email.split('@')[0] || 'Your account'}</Text><Text style={st.email}>{email}</Text></View><Pill label={profile ? `SAVED · V${profile.version}` : 'SETUP REQUIRED'} tone={profile ? 'green' : 'amber'} /></Card>
    {!profile && <Card style={st.notice}><Text style={st.hintText}>Choose the restrictions you want to track, then save your profile to finish account setup.</Text></Card>}
    <Card style={st.card}><SectionTitle title="Conditions for your guide" /><Text style={st.help}>A condition alone does not create foods to avoid. Some condition guidance is not active in this prototype.</Text><View style={st.chips}>{conditions.map(item => { const active = selectedConditions.includes(item); return <Pressable key={item} accessibilityRole="button" accessibilityState={{ selected: active }} accessibilityLabel={item} onPress={() => { toggleCondition(item); setSaved(false); }} style={[st.chip, active && st.chipSelected]}><MaterialCommunityIcons name={active ? 'check-circle' : 'plus-circle-outline'} size={15} color={active ? colors.primary : colors.muted} /><Text style={[st.chipText, active && st.chipSelectedText]}>{item}</Text></Pressable>; })}</View><Text style={st.conditionNote}>Active awareness guidance: diabetes, hypertension and individually recorded CKD limits. PCOS and other conditions require further review.</Text></Card>
    <Card style={st.card}><SectionTitle title="Allergies and ingredients" /><Text style={st.help}>Matches in the ingredient list and precautionary statements are reported separately.</Text><View style={st.chips}>{allergens.map(item => { const active = selectedAllergens.includes(item); return <Pressable key={item} accessibilityRole="button" accessibilityState={{ selected: active }} accessibilityLabel={item} onPress={() => { toggleAllergen(item); setSaved(false); }} style={[st.chip, active && st.chipActive]}><MaterialCommunityIcons name={active ? 'check-circle' : 'plus-circle-outline'} size={15} color={active ? colors.red : colors.muted} /><Text style={[st.chipText, active && st.chipTextActive]}>{item}</Text></Pressable>; })}</View><Text style={st.conditionNote}>An incomplete product declaration remains unknown; no match is not a safety guarantee.</Text>
      <Text style={st.label}>INGREDIENT EXCLUSIONS</Text>
      <Text style={st.help}>Words or phrases to flag in ingredient lists below the nine allergens. Each entry needs at least two characters.</Text>
      {profileDraft.ingredient_exclusions.length > 0 ? <View style={st.chips}>{profileDraft.ingredient_exclusions.map(item => <Pressable key={item} accessibilityRole="button" accessibilityLabel={`Remove exclusion ${item}`} onPress={() => removeExclusion(item)} style={st.exclusion}><Text style={st.exclusionText}>{item}</Text><MaterialCommunityIcons name="close" size={13} color={colors.muted} /></Pressable>)}</View> : <Text style={st.conditionNote}>No extra ingredient exclusions recorded.</Text>}
      <View style={st.exclusionRow}><TextInput accessibilityLabel="Add an ingredient exclusion" value={exclusion} onChangeText={setExclusion} onSubmitEditing={addExclusion} placeholder="e.g. palm oil" placeholderTextColor={colors.subtle} style={[st.inputBox, { flex: 1 }]} /><Button title="Add" compact secondary onPress={addExclusion} /></View>
    </Card>
    <Card style={st.card}><SectionTitle title="Personal sodium limit" /><Text style={st.help}>Only enter a limit from guidance you trust. It will be recorded with this profile.</Text><Pressable accessibilityRole="button" accessibilityLabel={limitOpen ? 'Close limit entry' : 'Add a daily limit'} onPress={() => setLimitOpen(value => !value)} style={st.addLimit}><MaterialCommunityIcons name={limitOpen ? 'minus' : 'plus'} size={17} color={colors.primary} /><Text style={st.addText}>{limitOpen ? 'Close limit entry' : sodiumLimit ? 'Edit daily limit' : 'Add a daily limit'}</Text></Pressable>{limitOpen && <View style={st.limitEditor}><Text style={st.help}>Daily sodium maximum · mg</Text><TextInput accessibilityLabel="Daily sodium maximum in milligrams" value={sodiumLimit} onChangeText={value => { setSodiumLimit(value); setSaved(false); }} keyboardType="numeric" placeholder="Enter the amount" placeholderTextColor={colors.subtle} style={st.inputBox} /><Text style={st.conditionNote}>A daily limit shows a portion’s contribution. The app does not track your full day’s intake.</Text></View>}</Card>
    <Card style={st.card}><SectionTitle title="Food preferences" /><Text style={st.help}>Used only to help order otherwise eligible replacement products.</Text><Pressable accessibilityRole="switch" accessibilityState={{ checked: vegetarian }} accessibilityLabel="Vegetarian preference" onPress={() => { const preferences = vegetarian ? '' : 'Vegetarian'; setProfileDraft({ ...profileDraft, preferences }); setSaved(false); }} style={st.preference}><View style={{ flex: 1 }}><Text style={st.limitTitle}>Vegetarian preference</Text><Text style={st.help}>Does not change allergy or nutrient checks</Text></View><View style={[st.toggle, vegetarian && st.toggleOn]}><View style={[st.knob, vegetarian && st.knobOn]} /></View></Pressable></Card>
    {error ? <Text accessibilityRole="alert" style={st.error}>{error}</Text> : null}
    <Button title={saving ? 'Saving…' : saved ? 'Profile saved to your account' : profile ? 'Save profile changes' : 'Save and continue'} loading={saving} disabled={saving} icon={saved && !saving ? 'check' : 'content-save-outline'} onPress={() => void doSave()} />
    <Pressable accessibilityRole="button" accessibilityLabel="Sign out" onPress={() => void signOut()} style={st.signOut}><MaterialCommunityIcons name="logout" size={17} color={colors.muted} /><Text style={st.signOutText}>Sign out</Text></Pressable>
    <Text style={st.disclaimer}>Profile updates create a new version. Existing assessments remain tied to the version used when they were created.</Text>
  </Screen>;
}

const st = StyleSheet.create({
  identity: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 15 }, avatar: { width: 48, height: 48, backgroundColor: colors.primary, borderRadius: radius.avatar, alignItems: 'center', justifyContent: 'center' }, avatarText: { color: colors.onPrimary, fontSize: 20, fontWeight: '800' }, name: { color: colors.ink, fontSize: 14, fontWeight: '800' }, email: { color: colors.muted, fontSize: 10, marginTop: 4 },
  card: { gap: 14 }, label: { color: colors.muted, letterSpacing: 1, fontSize: 9, fontWeight: '800', marginTop: 4 }, help: { color: colors.muted, fontSize: 11, lineHeight: 16, marginTop: -8 }, chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 }, chip: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 11, paddingVertical: 9, borderRadius: radius.pill, backgroundColor: colors.canvas }, chipActive: { backgroundColor: colors.redBg }, chipText: { color: colors.muted, fontSize: 11, fontWeight: '700' }, chipTextActive: { color: colors.red }, chipSelected: { backgroundColor: colors.lavender }, chipSelectedText: { color: colors.primary }, conditionNote: { color: colors.subtle, fontSize: 10, lineHeight: 14 },
  exclusion: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 11, paddingVertical: 9, borderRadius: radius.pill, backgroundColor: colors.lavenderSoft }, exclusionText: { color: colors.ink, fontSize: 11, fontWeight: '700' }, exclusionRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 2 },
  addLimit: { flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start' }, addText: { color: colors.primary, fontSize: 11, fontWeight: '700' }, limitEditor: { gap: 7 }, inputBox: { minHeight: 46, borderRadius: radius.input, borderWidth: 1, borderColor: colors.line, paddingHorizontal: 12, color: colors.ink, fontSize: 12, backgroundColor: colors.surface }, preference: { flexDirection: 'row', alignItems: 'center', borderTopWidth: 1, borderColor: colors.line, paddingTop: 13 }, limitTitle: { color: colors.ink, fontSize: 12, fontWeight: '700' }, toggle: { width: 41, height: 24, borderRadius: radius.pill, backgroundColor: colors.track, padding: 3, justifyContent: 'center' }, toggleOn: { backgroundColor: colors.primary }, knob: { width: 18, height: 18, borderRadius: 9, backgroundColor: colors.surface }, knobOn: { alignSelf: 'flex-end' },
  signOut: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 8 }, signOutText: { color: colors.muted, fontSize: 12, fontWeight: '700' }, disclaimer: { textAlign: 'center', color: colors.subtle, fontSize: 10, lineHeight: 15, paddingHorizontal: 15 }, notice: { backgroundColor: colors.amberBg }, hintText: { color: colors.amberInk, fontSize: 11, lineHeight: 15 }, error: { color: colors.red, fontSize: 12, lineHeight: 17 },
});
