import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Card, DemoBanner, PageHeader, Pill, Screen, Button, SectionTitle } from '@/src/components/ui';
import { useApp } from '@/src/state/AppContext';
import { colors } from '@/src/theme';

export default function AssessmentScreen() {
  const { product, allergens, saved, toggleSaved, sodiumLimit } = useApp();
  const findings = product.sample ? product.findings.filter(finding => {
    const detail = `${finding.title} ${finding.detail}`.toLowerCase();
    if (detail.includes('peanut')) return allergens.some(item => item.toLowerCase().includes('peanut'));
    if (detail.includes('tree nut')) return allergens.some(item => item.toLowerCase().includes('tree nut'));
    return true;
  }) : [];
  return <Screen>
    <PageHeader eyebrow="Your label check" title="Assessment" subtitle={product.name} back right={<Pressable accessibilityRole="button" accessibilityLabel={saved.includes(product.id) ? 'Remove saved assessment' : 'Save assessment'} onPress={() => toggleSaved(product.id)} style={st.save}><MaterialCommunityIcons name={saved.includes(product.id) ? 'bookmark' : 'bookmark-outline'} size={19} color={colors.primary} /></Pressable>} />
    <DemoBanner />
    <Card style={st.summary}>
      <View style={st.summaryTop}><View style={[st.productIcon, { backgroundColor: product.color }]}><Text style={{ fontSize: 26 }}>{product.icon}</Text></View><View style={{ flex: 1 }}><Text style={st.brand}>{product.brand} · {product.category}</Text><Text style={st.productName}>{product.name}</Text><Text style={st.brand}>Checked against: {allergens.length ? allergens.join(', ') : 'No allergens selected'}</Text></View></View>
      <View style={st.summaryDivider} />
      <View style={st.summaryFooter}><MaterialCommunityIcons name="text-box-check-outline" size={18} color={colors.primary} /><Text style={st.summaryCopy}>{product.sample ? 'Illustrative example findings · Not a clinical verdict' : 'Manual label entry · No assessment engine connected'}</Text></View>
    </Card>
    {!product.sample ? <Card style={st.empty}><View style={st.unknownCircle}><MaterialCommunityIcons name="help-circle-outline" size={27} color={colors.amber} /></View><Text style={st.emptyTitle}>Your label is saved</Text><Text style={st.emptyCopy}>The frontend can capture your corrections, but it has no ingredient-matching service yet. No suitability result was generated.</Text><Pill label="ASSESSMENT ENGINE NOT CONNECTED" tone="amber" /></Card> : <>
      <View style={st.resultHeader}><View style={st.resultMark}><MaterialCommunityIcons name="text-box-search-outline" size={25} color={colors.primary} /></View><View style={{ flex: 1 }}><Text style={st.resultTitle}>Label observations</Text><Text style={st.resultSub}>Review each item with its source text.</Text></View><Pill label={`${findings.length} items`} tone="purple" /></View>
      <View style={{ gap: 10 }}>{findings.map((finding, index) => {
        const tone = finding.kind === 'flag' ? 'red' : finding.kind === 'caution' ? 'amber' : finding.kind === 'unknown' ? 'blue' : 'neutral';
        const icon = finding.kind === 'flag' ? 'alert-circle-outline' : finding.kind === 'caution' ? 'alert-outline' : finding.kind === 'unknown' ? 'help-circle-outline' : 'information-outline';
        const accent = finding.kind === 'flag' ? colors.red : finding.kind === 'caution' ? colors.amber : finding.kind === 'unknown' ? colors.blue : colors.primary;
        return <Card key={`${finding.title}-${index}`} style={st.finding}><View style={[st.findingIcon, { backgroundColor: finding.kind === 'flag' ? colors.redBg : finding.kind === 'caution' ? colors.amberBg : finding.kind === 'unknown' ? colors.blueBg : colors.lavender }]}><MaterialCommunityIcons name={icon} size={20} color={accent} /></View><View style={{ flex: 1, gap: 6 }}><View style={st.findingHeading}><Text style={st.findingTitle}>{finding.title}</Text><Pill label={finding.kind === 'flag' ? 'DECLARED' : finding.kind === 'caution' ? 'ADVISORY' : finding.kind === 'unknown' ? 'UNKNOWN' : 'INFO'} tone={tone} /></View><Text style={st.findingDetail}>{finding.detail}</Text>{finding.evidence && <View style={st.evidence}><Text style={st.evidenceLabel}>LABEL TEXT</Text><Text style={st.evidenceText}>{finding.evidence}</Text></View>}</View></Card>;
      })}{findings.length === 0 && <Card style={st.emptyFinding}><Text style={st.findingTitle}>No selected-allergen match in this example</Text><Text style={st.findingDetail}>That is not a confirmation that the product is suitable. The sample label and catalog are not verified.</Text></Card>}</View>
      <Card style={st.limitCard}><View style={st.limitIcon}><MaterialCommunityIcons name="counter" size={19} color={colors.blue} /></View><View style={{ flex: 1 }}><Text style={st.findingTitle}>Nutrition snapshot</Text><Text style={st.findingDetail}>{product.sodium == null ? 'Sodium amount is not available in this record.' : `Sodium · ${product.sodium} ${product.basis}`}</Text><Text style={st.limitHelp}>{sodiumLimit ? `Your entered limit is ${sodiumLimit} mg/day. This preview does not compare product values with it.` : 'No personal sodium limit is recorded. This is not a pass or exceed result.'}</Text></View></Card>
    </>}
    <Card style={st.scope}><MaterialCommunityIcons name="book-open-variant" size={18} color={colors.primary} /><View style={{ flex: 1 }}><Text style={st.findingTitle}>What this check covers</Text><Text style={st.findingDetail}>Only the label details and recorded restrictions shown here. Missing data stays unknown; it does not mean a food is safe or suitable.</Text></View></Card>
    <SectionTitle title="Next step" />
    <Button title="Compare replacements" icon="swap-horizontal" onPress={() => router.push('/replacements')} />
    <Button title="Edit label details" icon="pencil-outline" secondary onPress={() => router.push('/review')} />
  </Screen>;
}
const st = StyleSheet.create({
  save: { width: 40, height: 40, borderRadius: 14, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center' }, summary: { gap: 13 }, summaryTop: { flexDirection: 'row', alignItems: 'center', gap: 12 }, productIcon: { width: 54, height: 54, borderRadius: 18, alignItems: 'center', justifyContent: 'center' }, productName: { color: colors.ink, fontSize: 15, fontWeight: '800', marginTop: 4 }, brand: { color: colors.muted, fontSize: 10, lineHeight: 15 }, summaryDivider: { height: 1, backgroundColor: colors.line }, summaryFooter: { flexDirection: 'row', alignItems: 'center', gap: 8 }, summaryCopy: { color: colors.primaryDark, fontSize: 10, fontWeight: '700' },
  resultHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 2 }, resultMark: { width: 43, height: 43, borderRadius: 15, backgroundColor: colors.redBg, alignItems: 'center', justifyContent: 'center' }, resultTitle: { fontSize: 15, color: colors.ink, fontWeight: '800' }, resultSub: { fontSize: 10, color: colors.muted, marginTop: 3 }, finding: { flexDirection: 'row', alignItems: 'flex-start', gap: 11, padding: 14 }, findingIcon: { width: 38, height: 38, borderRadius: 13, alignItems: 'center', justifyContent: 'center' }, findingHeading: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 6 }, findingTitle: { flex: 1, color: colors.ink, fontSize: 12, lineHeight: 16, fontWeight: '800' }, findingDetail: { color: colors.muted, fontSize: 11, lineHeight: 16 }, evidence: { backgroundColor: colors.canvas, padding: 9, borderRadius: 10, marginTop: 2 }, evidenceLabel: { color: colors.subtle, fontSize: 8, letterSpacing: .8, fontWeight: '800' }, evidenceText: { color: colors.ink, fontSize: 11, fontWeight: '700', marginTop: 4 },
  limitCard: { flexDirection: 'row', alignItems: 'flex-start', gap: 11 }, limitIcon: { width: 38, height: 38, borderRadius: 13, backgroundColor: colors.blueBg, alignItems: 'center', justifyContent: 'center' }, limitHelp: { color: colors.blue, fontSize: 10, lineHeight: 14, marginTop: 5 }, scope: { flexDirection: 'row', gap: 10, alignItems: 'flex-start', backgroundColor: '#F3F0FF' }, empty: { alignItems: 'center', gap: 9, padding: 23 }, emptyFinding: { backgroundColor: colors.blueBg, gap: 7 }, unknownCircle: { width: 52, height: 52, borderRadius: 18, backgroundColor: colors.amberBg, alignItems: 'center', justifyContent: 'center' }, emptyTitle: { color: colors.ink, fontWeight: '800', fontSize: 15 }, emptyCopy: { color: colors.muted, fontSize: 12, textAlign: 'center', lineHeight: 18 },
});
