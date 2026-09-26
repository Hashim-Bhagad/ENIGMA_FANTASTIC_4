import React, { useEffect } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Button, Card, PageHeader, Pill, Screen, SectionTitle } from '@/src/components/ui';
import { useApp } from '@/src/state/AppContext';
import { colors, radius, typography } from '@/src/theme';
import { toProduct, type RecommendationCandidate } from '@/src/api/client';
import { nutrientFields } from '@/src/data/nutrients';

export default function ReplacementsScreen() {
  const { product, assessment, recommendation, getRecommendations, busyFor, error, clearError } = useApp();
  useEffect(() => {
    if (assessment && recommendation?.assessment_id !== assessment.id) void getRecommendations().catch(() => undefined);
  }, [assessment, recommendation?.assessment_id, getRecommendations]);
  const busy = busyFor('recommend');
  const retry = () => { clearError(); void getRecommendations().catch(() => undefined); };
  const verified = recommendation ? recommendation.candidates.filter(candidate => candidate.verified) : [];
  const unverified = recommendation ? [...recommendation.candidates.filter(candidate => !candidate.verified), ...(recommendation.needs_review || [])] : [];
  return <Screen>
    <PageHeader title="Eligible replacements" subtitle={`Options checked against your profile for ${product.name}.`} back backFallback="/assessment" />
    <Card style={st.context}><View style={st.contextIcon}><MaterialCommunityIcons name="shield-check-outline" size={20} color={colors.primary} /></View><View style={{ flex: 1 }}><Text style={st.title}>Eligibility comes first</Text><Text style={st.copy}>The backend filters conflicts and missing required checks before comparing nutrients. A candidate still needs its current package confirmed.</Text></View></Card>
    {busy && !recommendation && <Card style={st.empty}><MaterialCommunityIcons name="progress-clock" size={26} color={colors.primary} /><Text style={st.copy}>Checking comparable products…</Text></Card>}
    {error ? <Card style={st.error}><Text style={st.errorText}>{error}</Text><Button title="Try again" compact secondary onPress={retry} /></Card> : null}
    {!assessment ? <Card style={st.empty}><Text style={st.title}>Assess a product first</Text><Text style={st.copy}>Replacement search uses the saved assessment and profile version.</Text><Button title="Review a product" icon="barcode-scan" compact onPress={() => router.push('/(tabs)/scan')} /></Card> : null}
    {recommendation && <>
      <Card style={st.summary}><Pill label={recommendation.ranking_method.replaceAll('_', ' ').toUpperCase()} tone="purple" /><Text style={st.copy}>{recommendation.message}</Text>{recommendation.fallback_reason && <Text style={st.note}>Preference ranking was unavailable; candidates remain in deterministic order.</Text>}</Card>
      <SectionTitle title="Passed recorded checks" action={`${verified.length} found`} />
      {verified.length ? <View style={{ gap: 10 }}>{verified.map((candidate, index) => <CandidateCard key={`verified-${candidate.product_id}-${index}`} candidate={candidate} />)}</View> : <Card style={st.empty}><MaterialCommunityIcons name="magnify" size={27} color={colors.subtle} /><Text style={st.title}>No checked improvement found</Text><Text style={st.copy}>The current catalog may lack comparable category or label information. The backend did not relax your recorded checks.</Text></Card>}
      <SectionTitle title="Needs label review" action={`${unverified.length} found`} />
      <Card style={st.warning}><MaterialCommunityIcons name="alert-outline" size={18} color={colors.amber} /><Text style={st.warningText}>These candidates failed a required verification step. The catalog data could not confirm them against your recorded restrictions. Confirm the current package and label before treating any of them as suitable; being listed here does not mean they are safe.</Text></Card>
      {unverified.length ? <View style={{ gap: 10 }}>{unverified.map((candidate, index) => <CandidateCard key={`unverified-${candidate.product_id}-${index}`} candidate={candidate} />)}</View> : <Card style={st.empty}><Text style={st.title}>No additional record needs review</Text><Text style={st.copy}>This search returned no additional records for the review tier.</Text></Card>}
      {recommendation.excluded.length > 0 && <Card style={st.excluded}><Text style={st.title}>{recommendation.excluded.length} catalog options excluded</Text><Text style={st.copy}>They did not meet the recorded conflict, information, category or nutrient-comparison checks.</Text></Card>}
    </>}
    <Button title="Back to assessment" icon="arrow-left" secondary onPress={() => (router.canGoBack() ? router.back() : router.replace('/assessment'))} />
  </Screen>;
}

function CandidateCard({ candidate }: { candidate: RecommendationCandidate }) {
  const { setProduct, setLabelPhoto } = useApp();
  const review = () => { setProduct(toProduct(candidate.product_id, candidate.food)); setLabelPhoto(null); router.push('/review'); };
  return <Card style={st.product}>
    <View style={st.productTop}><View style={st.food}><MaterialCommunityIcons name="food-apple-outline" size={22} color={colors.primary} /></View><View style={{ flex: 1 }}><Text style={st.brand}>{candidate.food.brand || candidate.food.category}</Text><Text style={st.title}>{candidate.food.name}</Text></View><Pill label={candidate.verified ? 'CHECKS PASSED' : 'REVIEW REQUIRED'} tone={candidate.verified ? 'green' : 'amber'} /></View>
    {candidate.review_reasons?.length > 0 && <View style={st.reasons}>{candidate.review_reasons.map((reason, index) => <Text key={index} style={st.reasonText}>{'\u2022'} {reason.replaceAll('_', ' ')}</Text>)}</View>}
    {candidate.comparisons.map((comparison, itemIndex) => <View key={`${comparison.nutrient}-${itemIndex}`} style={st.compare}><View style={{ flex: 1 }}><Text style={st.compareLabel}>{nutrientFields.find(field => field.key === comparison.nutrient)?.label || comparison.nutrient}</Text><Text style={st.compareValue}>{comparison.original} → {comparison.replacement} {nutrientFields.find(field => field.key === comparison.nutrient)?.unit}</Text><Text style={st.copy}>{comparison.difference > 0 ? '+' : ''}{comparison.difference} {nutrientFields.find(field => field.key === comparison.nutrient)?.unit} / {comparison.basis}</Text></View><MaterialCommunityIcons name={comparison.improved ? 'check-circle-outline' : 'minus-circle-outline'} size={20} color={comparison.improved ? colors.green : colors.amber} /></View>)}
    {candidate.improvements.map(value => <Pill key={value} label={value.replaceAll('_', ' ')} tone="blue" />)}
    <Text style={st.note}>Source: {candidate.food.source.kind.replaceAll('_', ' ')}. Confirm this product's current package before relying on catalog details.</Text><Button title="Review this product & assess" icon="text-box-check-outline" secondary onPress={review} />
  </Card>;
}

const st = StyleSheet.create({
  context: { flexDirection: 'row', gap: 11, alignItems: 'flex-start', backgroundColor: colors.canvasSoft },
  contextIcon: { width: 40, height: 40, borderRadius: radius.chip, backgroundColor: colors.lavender, alignItems: 'center', justifyContent: 'center' },
  title: { color: colors.ink, fontSize: 17, lineHeight: 24, fontWeight: '800' },
  copy: { ...typography.body, color: colors.muted, marginTop: 4 },
  summary: { gap: 9 },
  note: { ...typography.meta, color: colors.subtle },
  product: { gap: 14 },
  productTop: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 12 },
  food: { width: 44, height: 44, borderRadius: radius.tile, backgroundColor: colors.lavender, alignItems: 'center', justifyContent: 'center' },
  brand: { ...typography.meta, color: colors.muted, marginBottom: 4 },
  compare: { flexDirection: 'row', alignItems: 'center', borderTopWidth: 1, borderColor: colors.line, paddingTop: 12 },
  compareLabel: { color: colors.muted, ...typography.meta, fontWeight: '700' },
  compareValue: { color: colors.ink, fontSize: 22, lineHeight: 28, fontWeight: '800', marginTop: 4 },
  empty: { alignItems: 'center', gap: 9, padding: 24 },
  excluded: { backgroundColor: colors.blueBg },
  warning: { backgroundColor: colors.amberBg, flexDirection: 'row', gap: 9, alignItems: 'flex-start' },
  warningText: { flex: 1, color: colors.amberInk, ...typography.body },
  reasons: { gap: 4, borderTopWidth: 1, borderColor: colors.line, paddingTop: 10 },
  reasonText: { color: colors.amberInk, ...typography.meta },
  error: { backgroundColor: colors.redBg, gap: 9 },
  errorText: { ...typography.meta, color: colors.red },
});
