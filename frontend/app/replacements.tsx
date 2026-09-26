import React, { useEffect } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Button, Card, PageHeader, Pill, Screen, SectionTitle } from '@/src/components/ui';
import { useApp } from '@/src/state/AppContext';
import { colors, radius } from '@/src/theme';
import type { RecommendationCandidate } from '@/src/api/client';

export default function ReplacementsScreen() {
  const { product, assessment, recommendation, getRecommendations, busy, error, clearError } = useApp();
  useEffect(() => {
    if (assessment && recommendation?.assessment_id !== assessment.id) void getRecommendations().catch(() => undefined);
  }, [assessment, recommendation?.assessment_id, getRecommendations]);
  const retry = () => { clearError(); void getRecommendations().catch(() => undefined); };
  const verified = recommendation ? recommendation.candidates.filter(candidate => candidate.verified) : [];
  const unverified = recommendation ? [...recommendation.candidates.filter(candidate => !candidate.verified), ...recommendation.needs_review] : [];
  return <Screen>
    <PageHeader eyebrow="Compare options" title="Eligible replacements" subtitle={`Options checked against your profile for ${product.name}.`} back />
    <Card style={st.context}><View style={st.contextIcon}><MaterialCommunityIcons name="shield-check-outline" size={20} color={colors.primary} /></View><View style={{ flex: 1 }}><Text style={st.title}>Eligibility comes first</Text><Text style={st.copy}>The backend filters conflicts and missing required checks before comparing nutrients. A candidate still needs its current package confirmed.</Text></View></Card>
    {busy && !recommendation && <Card style={st.empty}><MaterialCommunityIcons name="progress-clock" size={26} color={colors.primary} /><Text style={st.copy}>Checking comparable products…</Text></Card>}
    {error ? <Card style={st.error}><Text style={st.errorText}>{error}</Text><Button title="Try again" compact secondary onPress={retry} /></Card> : null}
    {!assessment ? <Card style={st.empty}><Text style={st.title}>Assess a product first</Text><Text style={st.copy}>Replacement search uses the saved assessment and profile version.</Text><Button title="Review a product" icon="barcode-scan" compact onPress={() => router.push('/(tabs)/scan')} /></Card> : null}
    {recommendation && <>
      <Card style={st.summary}><Pill label={recommendation.ranking_method.replaceAll('_', ' ').toUpperCase()} tone="purple" /><Text style={st.copy}>{recommendation.message}</Text>{recommendation.fallback_reason && <Text style={st.note}>Preference ranking was unavailable; candidates remain in deterministic order.</Text>}</Card>
      <SectionTitle title="Verified candidates" action={`${verified.length} found`} />
      {verified.length ? <View style={{ gap: 10 }}>{verified.map((candidate, index) => <CandidateCard key={`verified-${candidate.product_id}-${index}`} candidate={candidate} />)}</View> : <Card style={st.empty}><MaterialCommunityIcons name="magnify" size={27} color={colors.subtle} /><Text style={st.title}>No verified candidate found</Text><Text style={st.copy}>The current catalog may lack comparable category or label information. The backend did not relax your recorded checks.</Text></Card>}
      <SectionTitle title="Unverified candidates (confirm the label first)" action={`${unverified.length} found`} />
      <Card style={st.warning}><MaterialCommunityIcons name="alert-outline" size={18} color={colors.amber} /><Text style={st.warningText}>These candidates failed a required verification step. The catalog data could not confirm them against your recorded restrictions. Confirm the current package and label before treating any of them as suitable; being listed here does not mean they are safe.</Text></Card>
      {unverified.length ? <View style={{ gap: 10 }}>{unverified.map((candidate, index) => <CandidateCard key={`unverified-${candidate.product_id}-${index}`} candidate={candidate} />)}</View> : <Card style={st.empty}><Text style={st.title}>No unverified candidate listed</Text><Text style={st.copy}>Every returned candidate passed the current verification step.</Text></Card>}
      {recommendation.excluded.length > 0 && <Card style={st.excluded}><Text style={st.title}>{recommendation.excluded.length} catalog options excluded</Text><Text style={st.copy}>They did not meet the recorded conflict, information, category or nutrient-comparison checks.</Text></Card>}
    </>}
    <Button title="Back to assessment" icon="arrow-left" secondary onPress={() => router.back()} />
  </Screen>;
}

function CandidateCard({ candidate }: { candidate: RecommendationCandidate }) {
  return <Card style={st.product}>
    <View style={st.productTop}><View style={st.food}><MaterialCommunityIcons name="food-apple-outline" size={22} color={colors.primary} /></View><View style={{ flex: 1 }}><Text style={st.brand}>{candidate.food.brand || candidate.food.category}</Text><Text style={st.title}>{candidate.food.name}</Text></View><Pill label={candidate.verified ? 'VERIFIED' : 'UNVERIFIED'} tone={candidate.verified ? 'green' : 'amber'} /></View>
    {candidate.review_reasons.length > 0 && <View style={st.reasons}>{candidate.review_reasons.map((reason, index) => <Text key={index} style={st.reasonText}>{'\u2022'} {reason.replaceAll('_', ' ')}</Text>)}</View>}
    {candidate.comparisons.map((comparison, itemIndex) => <View key={`${comparison.nutrient}-${itemIndex}`} style={st.compare}><View style={{ flex: 1 }}><Text style={st.compareLabel}>{comparison.nutrient.replaceAll('_', ' ').toUpperCase()}</Text><Text style={st.compareValue}>{comparison.original} → {comparison.replacement}</Text><Text style={st.copy}>{comparison.difference > 0 ? '+' : ''}{comparison.difference} per {comparison.basis}</Text></View><MaterialCommunityIcons name={comparison.improved ? 'trending-down' : 'trending-up'} size={20} color={comparison.improved ? colors.green : colors.amber} /></View>)}
    {candidate.improvements.map(value => <Pill key={value} label={value.replaceAll('_', ' ')} tone="blue" />)}
    <Text style={st.note}>Review this product's current package and source warnings before relying on catalog details.</Text>
  </Card>;
}

const st = StyleSheet.create({ context: { flexDirection: 'row', gap: 11, alignItems: 'flex-start', backgroundColor: colors.canvasSoft }, contextIcon: { width: 40, height: 40, borderRadius: radius.chip, backgroundColor: colors.lavender, alignItems: 'center', justifyContent: 'center' }, title: { color: colors.ink, fontSize: 13, fontWeight: '800' }, copy: { color: colors.muted, fontSize: 11, lineHeight: 16, marginTop: 4 }, summary: { gap: 9 }, note: { color: colors.subtle, fontSize: 10, lineHeight: 14 }, product: { gap: 13 }, productTop: { flexDirection: 'row', alignItems: 'center', gap: 10 }, food: { width: 43, height: 43, borderRadius: radius.input, backgroundColor: colors.lavender, alignItems: 'center', justifyContent: 'center' }, brand: { color: colors.muted, fontSize: 9, marginBottom: 3 }, compare: { flexDirection: 'row', alignItems: 'center', borderTopWidth: 1, borderColor: colors.line, paddingTop: 11 }, compareLabel: { color: colors.muted, fontSize: 9, fontWeight: '800' }, compareValue: { color: colors.ink, fontSize: 15, fontWeight: '800', marginTop: 4 }, empty: { alignItems: 'center', gap: 9, padding: 24 }, excluded: { backgroundColor: colors.blueBg }, warning: { backgroundColor: colors.amberBg, flexDirection: 'row', gap: 9, alignItems: 'flex-start' }, warningText: { flex: 1, color: colors.amberInk, fontSize: 11, lineHeight: 16 }, reasons: { gap: 3, borderTopWidth: 1, borderColor: colors.line, paddingTop: 10 }, reasonText: { color: colors.amberInk, fontSize: 10, lineHeight: 14 }, error: { backgroundColor: colors.redBg, gap: 9 }, errorText: { color: colors.red, fontSize: 12, lineHeight: 17 } });
