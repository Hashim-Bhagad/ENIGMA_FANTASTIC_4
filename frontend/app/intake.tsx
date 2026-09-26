import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Linking, Pressable, StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Button, Card, PageHeader, Pill, Screen, SectionTitle } from '@/src/components/ui';
import { api, avoidSeverityLabel, avoidSeverityTone, confidenceLabel, evidenceReportLabel, formatEquivalent, formatEvidence, formatMeasuredLine, intakeBaselineLine, intakeProposedLine, IntakePlan, IntakeTarget } from '@/src/api/client';
import { useApp } from '@/src/state/AppContext';
import { colors, radius, typography } from '@/src/theme';

function nutrientDisplay(nutrient: string, plan: IntakePlan | null): string {
  return plan?.targets.find(item => item.nutrient === nutrient)?.label ?? nutrient.replaceAll('_', ' ');
}

function confidenceTone(confidence: IntakeTarget['confidence']): 'green' | 'blue' | 'amber' {
  return confidence === 'established' ? 'green' : confidence === 'clinician_only' ? 'amber' : 'blue';
}

export default function IntakeScreen() {
  const { token, profile, applyIntakeTarget, busyFor, error, clearError } = useApp();
  const [plan, setPlan] = useState<IntakePlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [planError, setPlanError] = useState('');
  const [openEvidence, setOpenEvidence] = useState<Record<string, boolean>>({});
  const [accepted, setAccepted] = useState('');
  const [acceptingKey, setAcceptingKey] = useState('');

  const loadPlan = useCallback(async () => {
    if (!token || !profile) { setPlan(null); return; }
    setLoading(true); setPlanError('');
    try { setPlan(await api.intakePlan(token, profile.id, profile.version)); }
    catch (cause) { setPlanError(cause instanceof Error ? cause.message : 'Your intake plan could not be loaded.'); }
    finally { setLoading(false); }
  }, [profile, token]);

  useEffect(() => { void loadPlan(); }, [loadPlan]);

  const accept = useCallback(async (target: IntakeTarget) => {
    clearError(); setAccepted(''); setAcceptingKey(target.rule_id);
    try {
      const updated = await applyIntakeTarget(target);
      const limit = updated.data.limits.find(item => item.nutrient === target.nutrient && item.scope === target.limit_scope);
      setAccepted(limit
        ? `Recorded: ${target.label} limited to ${limit.maximum}${target.unit ? ` ${target.unit}` : ''} ${limit.scope} · source “${limit.source}”.`
        : `Recorded ${target.label} in your saved profile.`);
      await loadPlan();
    } catch { /* The shared profile error is rendered below. */ }
    finally { setAcceptingKey(''); }
  }, [applyIntakeTarget, clearError, loadPlan]);

  const saving = busyFor('profile');

  if (!profile) return <Screen>
    <PageHeader title="Intake plan" subtitle="Proposals built from your records." back />
    <Card style={st.notice}><MaterialCommunityIcons name="account-alert-outline" size={19} color={colors.amber} /><Text style={st.noticeText}>Save a profile first. The plan needs your recorded conditions, sex and age band before it can propose anything.</Text></Card>
    <Button title="Go to your profile" icon="account-edit-outline" onPress={() => router.push('/(tabs)/profile')} />
  </Screen>;

  return <Screen>
    <PageHeader title="Intake plan" subtitle="Each line is a proposal until you accept it. Accepting records it as a limit in your saved profile." back />
    <Card style={st.notice}><MaterialCommunityIcons name="information-outline" size={18} color={colors.primary} /><Text style={st.noticeText}>This prototype does not diagnose. Values read from reports can be wrong, and a proposal is not medical advice. Entries marked “clinician review required” have no accept button on purpose: bring them to a clinician.</Text></Card>
    <View style={st.links}><Pressable accessibilityRole="link" onPress={() => router.push('/reports')}><Text style={st.link}>Reports used for this plan</Text></Pressable><Text style={st.cardSub}>{plan ? `${plan.reports_used.length} confirmed report${plan.reports_used.length === 1 ? '' : 's'} referenced` : 'No plan loaded yet'}</Text></View>

    {planError ? <Card style={st.errorCard}><Text accessibilityRole="alert" style={st.errorText}>{planError}</Text><Button title="Retry" compact secondary onPress={() => void loadPlan()} /></Card> : null}
    {error ? <Text accessibilityRole="alert" style={st.error}>{error}</Text> : null}
    {accepted ? <Card style={st.accepted}><MaterialCommunityIcons name="check-circle-outline" size={18} color={colors.green} /><Text style={st.acceptedText}>{accepted}</Text></Card> : null}
    {loading && !plan ? <Card style={st.empty}><ActivityIndicator size="small" color={colors.primary} /><Text style={st.cardSub}>Building your plan…</Text></Card> : null}

    {plan ? <>
      <SectionTitle title="Proposed targets" action={plan.version} />
      {plan.targets.length ? plan.targets.map(target => <Card key={target.rule_id} style={st.target}>
        <View style={st.targetHead}><View style={{ flex: 1 }}><Text style={st.targetTitle}>{target.label}</Text><Text style={st.cardSub}>{nutrientDisplay(target.nutrient, plan)} · {target.limit_scope}</Text></View><View style={st.pills}><Pill label={target.direction.toUpperCase()} tone="purple" /><Pill label={confidenceLabel(target.confidence)} tone={confidenceTone(target.confidence)} /></View></View>
        {target.display_value ? <><Text style={st.headline}>{target.display_value}</Text><Text style={st.proposed}>{intakeProposedLine(target)}</Text></> : <Text style={st.headline}>{intakeProposedLine(target)}</Text>}
        <Text style={st.baseline}>{intakeBaselineLine(target)}</Text>
        {target.equivalents.length ? <View style={st.subBlock}><Text style={st.fieldLabel}>THE SAME NUMBER IN KITCHEN UNITS</Text>{target.equivalents.map((item, index) => <Text key={index} style={st.cardSub}>{formatEquivalent(item)}</Text>)}</View> : null}
        {target.derivation ? <View style={st.subBlock}><Text style={st.fieldLabel}>HOW THIS NUMBER WAS DERIVED</Text><Text selectable style={st.cardSub}>{target.derivation}</Text></View> : null}
        {target.measured.length ? <View style={st.subBlock}><Text style={st.fieldLabel}>YOUR OWN MEASURED VALUES</Text>{target.measured.map((item, index) => <Text key={index} selectable style={st.cardSub}>{formatMeasuredLine(item)}</Text>)}</View> : null}
        <Text style={st.basis}>{target.basis}</Text>
        {target.requires_clinician
          ? <View style={st.clinician}><MaterialCommunityIcons name="stethoscope" size={16} color={colors.amber} /><Text style={st.clinicianText}>This needs a clinician’s decision. No accept control is shown; ask about it at your next appointment.</Text></View>
          : target.proposed_value != null && target.suggested_limit_source
            ? <Button title={acceptingKey === target.rule_id ? 'Recording…' : 'Use this target'} icon="clipboard-check-outline" compact loading={saving && acceptingKey === target.rule_id} disabled={saving} onPress={() => void accept(target)} />
            : <Text style={st.note}>This line has no proposable limit to record.</Text>}
        {target.evidence.length ? <>
          <Pressable accessibilityRole="button" accessibilityState={{ expanded: Boolean(openEvidence[target.rule_id]) }} onPress={() => setOpenEvidence(current => ({ ...current, [target.rule_id]: !current[target.rule_id] }))}><Text style={st.link}>{openEvidence[target.rule_id] ? 'Hide evidence' : `Show evidence (${target.evidence.length})`}</Text></Pressable>
          {openEvidence[target.rule_id] ? target.evidence.map((item, index) => <View key={index} style={st.evidence}><View style={st.evidenceHead}><Pill label={item.kind.toUpperCase()} tone={item.kind === 'lab' ? 'blue' : item.kind === 'condition' ? 'purple' : 'neutral'} />{evidenceReportLabel(item) ? <Text style={st.cardSub}>{evidenceReportLabel(item)}</Text> : null}</View><Text selectable style={st.evidenceText}>{formatEvidence(item)}</Text></View>) : null}
        </> : null}
        {target.questions.length ? <View style={st.questions}><Text style={st.fieldLabel}>QUESTIONS TO ASK</Text>{target.questions.map((question, index) => <Text key={index} style={st.cardSub}>{'\u2022'} {question}</Text>)}</View> : null}
      </Card>) : <Card style={st.empty}><MaterialCommunityIcons name="clipboard-text-outline" size={26} color={colors.subtle} /><Text style={st.cardTitle}>No proposals yet</Text><Text style={st.cardSub}>Add conditions or confirm a lab report, then load the plan again.</Text><Button title="Reload plan" compact secondary onPress={() => void loadPlan()} /></Card>}

      <SectionTitle title="What to avoid" action={plan.avoid.length ? `${plan.avoid.length} group${plan.avoid.length === 1 ? '' : 's'}` : undefined} />
      <Card style={st.notice}><MaterialCommunityIcons name="information-outline" size={18} color={colors.primary} /><Text style={st.noticeText}>These groups are derived from your recorded conditions and confirmed report values. A food that is not listed here is not implied safe: this is not a complete list of what matters for you.</Text></Card>
      {plan.avoid.length ? plan.avoid.map(group => <Card key={group.id} style={st.target}>
        <View style={st.targetHead}><Text style={[st.targetTitle, { flex: 1 }]}>{group.title}</Text><Pill label={avoidSeverityLabel(group.severity)} tone={avoidSeverityTone(group.severity)} /></View>
        <Text style={st.cardSub}>{group.detail}</Text>
        {group.items.length ? <View style={st.subBlock}>{group.items.map((item, index) => <View key={index} style={st.avoidItem}>
          <Text style={st.avoidLabel}>{item.label}</Text>
          {item.examples.length ? <Text style={st.cardSub}>Examples: {item.examples.join(', ')}</Text> : null}
          <Text style={st.cardSub}>{item.reason}</Text>
          {item.linked_nutrients.length ? <Text style={st.note}>Shows up as: {item.linked_nutrients.join(', ')}</Text> : null}
        </View>)}</View> : <Text style={st.note}>No item is listed for this group yet.</Text>}
        <View style={st.avoidMeta}><Pill label={confidenceLabel(group.confidence)} tone={confidenceTone(group.confidence)} />{group.sources.map((source, index) => <Pressable key={index} accessibilityRole="link" onPress={() => void Linking.openURL(source)}><Text style={st.link}>Open source guidance ↗</Text></Pressable>)}</View>
        {group.severity === 'ask' ? <Text style={st.note}>Ask entries are questions for your clinician or the kitchen, not confirmed restrictions.</Text> : null}
        {group.evidence.length ? <View style={st.subBlock}><Text style={st.fieldLabel}>WHAT TRIGGERED THIS</Text>{group.evidence.map((item, index) => <Text key={index} selectable style={st.cardSub}>{formatEvidence(item)}</Text>)}</View> : null}
      </Card>) : <Card style={st.empty}><MaterialCommunityIcons name="shield-check-outline" size={26} color={colors.subtle} /><Text style={st.cardTitle}>Nothing to avoid is derived yet</Text><Text style={st.cardSub}>No condition or confirmed report value in your profile currently points at a food group to avoid or limit. Add a condition or confirm a report, then load the plan again.</Text></Card>}

      {plan.conditions.length ? <><SectionTitle title="Conditions in this plan" />{plan.conditions.map(item => <Card key={item.slug} style={st.condition}>
        <View style={st.targetHead}><Text style={st.targetTitle}>{item.label}</Text><Pill label={confidenceLabel(item.guidance_confidence)} tone={confidenceTone(item.guidance_confidence)} /></View>
        <Text style={st.cardSub}>{item.awareness}</Text>
        {item.questions.map((question, index) => <Text key={index} style={st.cardSub}>{'\u2022'} {question}</Text>)}
        {item.sources.map((source, index) => <Pressable key={index} accessibilityRole="link" onPress={() => void Linking.openURL(source)}><Text style={st.link}>Open source guidance ↗</Text></Pressable>)}
      </Card>)}</> : null}
      {plan.unrecognised_conditions.length ? <Card style={st.notice}><MaterialCommunityIcons name="alert-outline" size={17} color={colors.amber} /><Text style={st.noticeText}>Not covered by active guidance in this prototype: {plan.unrecognised_conditions.join(', ')}. Ask a clinician for explicit limits instead of relying on a condition name.</Text></Card> : null}
      {plan.notes.length ? <Card style={st.notes}><Text style={st.fieldLabel}>PLAN NOTES</Text>{plan.notes.map((entry, index) => <Text key={index} style={st.cardSub}>{'\u2022'} {entry}</Text>)}</Card> : null}
      <Text style={st.coverage}>{plan.coverage}</Text>
    </> : null}

    <SectionTitle title="Recorded limits" action="Edit profile" onAction={() => router.push('/(tabs)/profile')} />
    <Card style={st.recorded}>
      {profile.data.limits.length ? profile.data.limits.map(limit => <View key={`${limit.nutrient}-${limit.scope}`} style={st.recordRow}><View style={{ flex: 1 }}><Text style={st.recordTitle}>{nutrientDisplay(limit.nutrient, plan)}</Text><Text style={st.cardSub}>{limit.scope} · {limit.source}</Text></View><Text style={st.recordValue}>{limit.maximum}</Text></View>)
        : <Text style={st.cardSub}>No limits recorded. Accepted targets appear here once saved.</Text>}
    </Card>
    <Text style={st.disclaimer}>A recorded limit is checked against a product’s stated amounts. It is not a diagnosis, and it is not a guarantee about any food.</Text>
  </Screen>;
}

const st = StyleSheet.create({
  notice: { flexDirection: 'row', alignItems: 'flex-start', gap: 9, backgroundColor: colors.lavender },
  noticeText: { flex: 1, color: colors.purpleInk, ...typography.meta },
  links: { flexDirection: 'row', alignItems: 'center', gap: 10, flexWrap: 'wrap' },
  link: { color: colors.primary, ...typography.meta, fontWeight: '700', paddingVertical: 6 },
  target: { gap: 10 },
  targetHead: { flexDirection: 'row', alignItems: 'flex-start', gap: 9 },
  targetTitle: { color: colors.ink, fontSize: 15, lineHeight: 22, fontWeight: '800' },
  pills: { alignItems: 'flex-end', gap: 5 },
  baseline: { ...typography.meta, color: colors.muted },
  proposed: { color: colors.ink, fontSize: 15, lineHeight: 22, fontWeight: '700' },
  basis: { ...typography.meta, color: colors.muted },
  headline: { color: colors.primaryDark, fontSize: 20, lineHeight: 26, fontWeight: '800' },
  subBlock: { gap: 4, borderTopWidth: 1, borderTopColor: colors.line, paddingTop: 10 },
  avoidItem: { gap: 3, paddingVertical: 6 },
  avoidLabel: { color: colors.ink, fontSize: 14, lineHeight: 20, fontWeight: '800' },
  avoidMeta: { flexDirection: 'row', alignItems: 'center', gap: 10, flexWrap: 'wrap' },
  clinician: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, backgroundColor: colors.amberBg, borderRadius: radius.chip, padding: 12 },
  clinicianText: { flex: 1, color: colors.amberInk, ...typography.meta },
  note: { ...typography.caption, color: colors.subtle },
  evidence: { borderTopWidth: 1, borderTopColor: colors.line, paddingTop: 10, gap: 4 },
  evidenceHead: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  evidenceText: { color: colors.ink, ...typography.meta },
  questions: { gap: 3, borderTopWidth: 1, borderTopColor: colors.line, paddingTop: 10 },
  fieldLabel: { ...typography.label, color: colors.muted },
  condition: { gap: 7 },
  notes: { gap: 4 },
  accepted: { flexDirection: 'row', alignItems: 'flex-start', gap: 9, backgroundColor: colors.greenBg },
  acceptedText: { flex: 1, color: colors.green, ...typography.meta, fontWeight: '700' },
  empty: { alignItems: 'center', gap: 7 },
  cardTitle: { color: colors.ink, ...typography.cardTitle },
  cardSub: { ...typography.meta, color: colors.muted },
  recorded: { gap: 10 },
  recordRow: { flexDirection: 'row', alignItems: 'center', gap: 10, borderTopWidth: 1, borderTopColor: colors.line, paddingTop: 10 },
  recordTitle: { color: colors.ink, fontSize: 14, lineHeight: 20, fontWeight: '700' },
  recordValue: { color: colors.primary, fontSize: 16, fontWeight: '800' },
  errorCard: { gap: 9, backgroundColor: colors.redBg },
  errorText: { ...typography.meta, color: colors.red },
  error: { ...typography.meta, color: colors.red },
  coverage: { textAlign: 'center', ...typography.caption, color: colors.subtle, paddingHorizontal: 15 },
  disclaimer: { textAlign: 'center', ...typography.caption, color: colors.subtle, paddingHorizontal: 15 },
});
