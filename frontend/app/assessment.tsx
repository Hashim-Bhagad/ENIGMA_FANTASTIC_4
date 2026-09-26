import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Button, Card, PageHeader, Pill, Screen, SectionTitle } from '@/src/components/ui';
import { FindingsList, findingCount, statusTone } from '@/src/components/findings';
import { useApp } from '@/src/state/AppContext';
import { colors } from '@/src/theme';
import { FoodFacts } from '@/src/components/food-facts';

export default function AssessmentScreen() {
  const { assessment } = useApp();
  if (!assessment) return <Screen><PageHeader eyebrow="Your label check" title="No assessment yet" subtitle="Review a product label and ask the backend to assess it first." back /><Button title="Scan or search a product" icon="barcode-scan" onPress={() => router.push('/(tabs)/scan')} /></Screen>;
  const result = assessment.result;
  const isMeal = assessment.food.source.kind === 'dish';
  const tone = statusTone(result.status);
  const checkedAllergies = assessment.profile_snapshot?.allergies;
  const sourceNote = assessment.food.source.kind === 'label_extraction'
    ? 'These observations came from a model reading of your label photo. You reviewed and confirmed them before this assessment.'
    : assessment.food.source.kind === 'demo'
      ? 'This record is illustrative sample data, not a verified catalog entry.'
      : null;
  return <Screen>
    <PageHeader eyebrow={isMeal ? "Your meal check" : "Your label check"} title="Your food assessment" subtitle={assessment.food.name} back />
    <Card style={st.summary}>
      <View style={st.summaryRow}><View style={{ gap: 6 }}><Text style={st.brand}>{isMeal ? 'Submitted meal ingredients' : assessment.food.brand || 'Product label'} · {assessment.food.category || 'Unclassified'}</Text><Text style={st.productName}>{assessment.food.name}</Text><Text style={st.brand}>Profile version {assessment.profile_version} · {assessment.food.basis || 'No comparable nutrient basis'}</Text></View><Pill label={result.status.replaceAll('_', ' ').toUpperCase()} tone={tone} /></View>
      <View style={st.divider} />
      <Text accessibilityRole="header" style={st.statusReason}>{result.status_reason || (result.conflicts.length ? "A recorded restriction matches this food." : result.unresolved.length ? "More information is needed for your recorded checks." : "No matching concern was found under these checks.")}</Text><View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}><Pill label={`${result.conflicts.length} conflicts`} tone="red" /><Pill label={`${result.unresolved.length} unknowns`} tone="amber" /><Pill label={`${result.considerations.length} notes`} tone="blue" /></View>
      <Text style={st.coverage}>{result.coverage}</Text>
      <Text style={st.checked}>Allergies checked: {checkedAllergies ? checkedAllergies.length ? checkedAllergies.join(', ').replaceAll('_', ' ') : 'None in this saved profile' : `Saved profile version ${assessment.profile_version}`}</Text>
    </Card>
    <FoodFacts food={assessment.food} trace={result.source_trace} />
    {sourceNote ? <Card style={st.scope}><MaterialCommunityIcons name="information-outline" size={18} color={colors.primary} /><Text style={st.coverage}>{sourceNote}</Text></Card> : null}
    {isMeal ? <Card style={st.scope}><View style={{ flex: 1, gap: 8 }}><Text style={st.findingTitle}>Before cooking or ordering</Text>{result.conflicts.map((item, index) => <Text selectable key={index} style={st.coverage}>Ask whether the cook can omit or replace {item.evidence?.length ? item.evidence.join(", ") : item.affects?.join(", ") || "the flagged ingredient"}. Confirm sauces, toppings and shared utensils before reassessing the changed meal.</Text>)}{!result.conflicts.length ? <Text style={st.coverage}>Ask the cook to confirm the full ingredients and shared equipment. A recipe reference cannot establish what the restaurant serves.</Text> : null}<Text style={st.coverage}>Removing an ingredient from this list records a proposed change. It does not confirm the change happened in the kitchen.</Text></View></Card> : null}
    <SectionTitle title="Findings" action={`${findingCount(result)} items`} />
    <FindingsList result={result} />
    {result.source_warnings.map((warning, index) => <Card key={`warning-${index}`} style={st.warning}><MaterialCommunityIcons name="information-outline" size={17} color={colors.amber} /><Text style={st.warningText}>{warning}</Text></Card>)}
    {result.ingredient_findings?.length ? <Card style={{ gap: 10 }}><Text style={st.findingTitle}>Recognized ingredient names</Text>{result.ingredient_findings.map((item, index) => <Text selectable key={index} style={st.coverage}>“{item.raw_evidence}” → {(item.canonical_identity || item.subtype).replaceAll('_', ' ')}</Text>)}<Text style={st.coverage}>Names matched against vocabulary {result.ingredient_taxonomy_version || 'unknown'}. Recognition does not establish a nutrient amount.</Text></Card> : null}
    {result.ingredient_findings?.length ? <Card style={st.scope}><MaterialCommunityIcons name="format-list-bulleted" size={18} color={colors.blue} /><Text style={st.coverage}>Ingredient terms are matched against a versioned vocabulary (v{result.ingredient_taxonomy_version ?? 'unknown'}). A recognized name is not a nutrient amount, proof of hidden contents, or a clinical conclusion.</Text></Card> : null}
    <Card style={st.scope}><MaterialCommunityIcons name="book-open-variant" size={18} color={colors.primary} /><View style={{ flex: 1 }}><Text style={st.findingTitle}>Assessment saved</Text><Text style={st.coverage}>This record stores the food observations and profile version used. Update your profile and reassess to apply changed restrictions.</Text></View></Card>
    <SectionTitle title="Next step" />
    {!isMeal ? <Button title="Compare packaged replacements" icon="swap-horizontal" onPress={() => router.push('/replacements')} /> : <Button title="Edit ingredients & reassess" icon="pencil-outline" onPress={() => router.push('/dish')} />}
    <Button title="Check a cooked meal" icon="silverware-fork-knife" onPress={() => router.push('/dish')} />
    <Button title="Check another product" icon="barcode-scan" secondary onPress={() => router.push('/(tabs)/scan')} />
  </Screen>;
}
const st = StyleSheet.create({ summary: { gap: 12 }, summaryRow: { gap: 12, alignItems: 'flex-start' }, brand: { color: colors.muted, fontSize: 13, lineHeight: 19 }, productName: { color: colors.ink, fontSize: 23, lineHeight: 30, fontWeight: '800', marginVertical: 4 }, divider: { height: 1, backgroundColor: colors.line }, statusReason: { color: colors.ink, fontSize: 16, lineHeight: 24, fontWeight: '700' }, coverage: { color: colors.muted, fontSize: 14, lineHeight: 21 }, checked: { color: colors.primaryDark, fontSize: 13, fontWeight: '700' }, findingTitle: { flex: 1, color: colors.ink, fontSize: 15, lineHeight: 22, fontWeight: '800' }, warning: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, backgroundColor: colors.amberBg }, warningText: { flex: 1, color: colors.amberInk, fontSize: 14, lineHeight: 21 }, scope: { flexDirection: 'row', gap: 10, alignItems: 'flex-start', backgroundColor: colors.lavenderSoft } });
