import React, { useCallback, useEffect, useState } from 'react';
import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Button, Card, PageHeader, Pill, Screen, SectionTitle } from '@/src/components/ui';
import { statusTone } from '@/src/components/findings';
import { api, ConditionRegistry, conditionLabel, confidenceLabel, IntakePlan } from '@/src/api/client';
import { useApp } from '@/src/state/AppContext';
import { colors, radius, typography } from '@/src/theme';

function guidanceTone(confidence: 'established' | 'general_wellbeing' | 'clinician_only'): 'green' | 'blue' | 'amber' {
  return confidence === 'established' ? 'green' : confidence === 'clinician_only' ? 'amber' : 'blue';
}

export default function GuideScreen() {
  const { email, token, profile, conditions, allergens, sodiumLimit, history, loadHistory, openAssessment, guide, guideError, loadGuide, busyFor } = useApp();
  const [registry, setRegistry] = useState<ConditionRegistry | null>(null);
  const [plan, setPlan] = useState<IntakePlan | null>(null);
  useEffect(() => { void loadHistory(); }, [loadHistory]);
  useEffect(() => { void loadGuide(); }, [loadGuide]);
  const loadRecords = useCallback(async () => {
    if (!token) return;
    try { setRegistry(await api.conditions(token)); } catch { setRegistry(null); }
    if (!profile) { setPlan(null); return; }
    try { setPlan(await api.intakePlan(token, profile.id, profile.version)); } catch { setPlan(null); }
  }, [profile, token]);
  useEffect(() => { void loadRecords(); }, [loadRecords]);
  const profileName = email.split('@')[0] || 'Food guide';
  const latest = history[0];
  return <Screen>
    <PageHeader title={`Welcome, ${profileName}`} subtitle="Check packaged food against the restrictions you have saved." right={<View style={st.avatar}><Text style={st.avatarText}>{profileName.slice(0, 1).toUpperCase()}</Text></View>} />
    <Card style={st.hero}><View style={st.heroTop}><View style={{ flex: 1 }}><Pill label="PROFILE SAVED TO YOUR ACCOUNT" tone="green" icon="check-circle-outline" /><Text style={st.heroTitle}>Know what's in{ '\n' }your next bite.</Text><Text style={st.heroCopy}>Scan a barcode, search a product, or take a label photo for review.</Text></View><View style={st.heroIcon}><MaterialCommunityIcons name="leaf" size={39} color={colors.green} /></View></View><Button title="Check a packaged food" icon="barcode-scan" onPress={() => router.push('/(tabs)/scan')} /></Card>
    <SectionTitle title="Your saved profile" action="Edit" onAction={() => router.push('/(tabs)/profile')} />
    <Card style={st.profileCard}><Text style={st.label}>ALLERGENS TO CHECK</Text><View style={st.chips}>{allergens.length ? allergens.map(item => <Pill key={item} label={item} tone="red" />) : <Text style={st.cardSub}>No allergies selected</Text>}</View>{conditions.length > 0 && <><Text style={st.label}>CONDITIONS RECORDED</Text><View style={st.chips}>{conditions.map(item => <Pill key={item} label={conditionLabel(item, registry)} tone="purple" />)}</View></>}<View style={st.notice}><MaterialCommunityIcons name="information-outline" size={17} color={colors.amber} /><Text style={st.noticeText}>{sodiumLimit ? `Daily sodium limit recorded: ${sodiumLimit} mg. A product portion is evaluated only when its amount and portion size are known.` : 'Add personal limits from guidance you trust in your profile.'}</Text></View></Card>
    <SectionTitle title="Guidance for your profile" action={guide ? `v${guide.profile_version}` : undefined} />
    {guideError ? <Card style={st.error}><Text accessibilityRole="alert" style={st.errorText}>{guideError}</Text><Button title="Retry guidance" compact secondary onPress={() => void loadGuide()} /></Card>
      : !guide ? <Card style={st.recent}><MaterialCommunityIcons name="progress-clock" size={20} color={colors.primary} /><Text style={st.cardSub}>{busyFor('guide') ? 'Loading guidance…' : 'No saved profile guidance yet.'}</Text></Card>
        : <>
          <Card style={st.profileCard}>
            <Text style={st.label}>EXCLUSIONS THE BACKEND WILL CHECK</Text>
            <View style={st.chips}>{guide.exclusions.length ? guide.exclusions.map(item => <Pill key={item} label={item.replaceAll('_', ' ')} tone="red" />) : <Text style={st.cardSub}>None recorded</Text>}</View>
            {guide.recorded_limits.length > 0 && <><Text style={st.label}>RECORDED LIMITS</Text>{guide.recorded_limits.map(limit => <Text key={`${limit.nutrient}-${limit.scope}`} style={st.cardSub}>{limit.nutrient.replaceAll('_', ' ')}: max {limit.maximum} · {limit.scope} · {limit.source}</Text>)}</>}
            {guide.comparison_goals.length > 0 && <><Text style={st.label}>COMPARISON GOALS</Text><View style={st.chips}>{guide.comparison_goals.map(goal => <Pill key={goal.nutrient} label={`${goal.nutrient.replaceAll('_', ' ')} ${goal.direction}`} tone="blue" />)}</View></>}
          </Card>
          {guide.condition_information.map(item => <Card key={item.condition} style={st.profileCard}><Text style={st.cardTitle}>{item.condition}</Text><Text style={st.cardSub}>{item.message}</Text><Pressable accessibilityRole="link" onPress={() => void Linking.openURL(item.source)}><Text style={st.link}>Open source guidance ↗</Text></Pressable></Card>)}
          {guide.unsupported_conditions.length > 0 && <Card style={st.notice}><MaterialCommunityIcons name="alert-outline" size={17} color={colors.amber} /><Text style={st.noticeText}>Not covered by active guidance in this prototype: {guide.unsupported_conditions.join(', ')}. Record explicit restrictions from a clinician instead of relying on the condition name.</Text></Card>}
          <Card style={st.profileCard}><Text style={st.label}>QUESTIONS TO ASK</Text>{guide.questions.map((question, index) => <Text key={index} style={st.cardSub}>{'\u2022'} {question}</Text>)}</Card>
          <Text style={st.footer}>{guide.coverage}</Text>
        </>}
    <SectionTitle title="Condition information" action={registry ? `registry v${registry.version}` : undefined} />
    {conditions.length === 0
      ? <Card style={st.recent}><Text style={st.cardSub}>Record a condition in your profile to see its information here.</Text></Card>
      : conditions.map(value => {
        const info = registry?.conditions.find(item => item.slug === value);
        if (!info) return <Card key={value} style={st.notice}><MaterialCommunityIcons name="alert-outline" size={17} color={colors.amber} /><Text style={st.noticeText}>{conditionLabel(value, registry)} is not covered by active guidance in this prototype. Ask a clinician for explicit limits instead of relying on the name.</Text></Card>;
        return <Card key={value} style={st.profileCard}>
          <View style={st.registryHead}><Text style={st.cardTitle}>{info.label}</Text><Pill label={confidenceLabel(info.guidance_confidence)} tone={guidanceTone(info.guidance_confidence)} /></View>
          <Text style={st.cardSub}>{info.awareness}</Text>
          {info.questions.map((question, index) => <Text key={index} style={st.cardSub}>{'\u2022'} {question}</Text>)}
          {info.sources.map((source, index) => <Pressable key={index} accessibilityRole="link" onPress={() => void Linking.openURL(source)}><Text style={st.link}>Open source guidance ↗</Text></Pressable>)}
        </Card>;
      })}
    <SectionTitle title="Personal intake" action="Open plan" onAction={() => router.push('/intake')} />
    <Card style={st.profileCard}>
      {plan
        ? <>
          <Text style={st.cardSub}>{plan.targets.length} target{plan.targets.length === 1 ? '' : 's'} proposed from {plan.reports_used.length} confirmed report{plan.reports_used.length === 1 ? '' : 's'} and your recorded conditions.</Text>
          {plan.targets.some(target => target.requires_clinician) ? <Pill label={`${plan.targets.filter(target => target.requires_clinician).length} NEED CLINICIAN REVIEW`} tone="amber" /> : null}
          {plan.notes.length ? <Text style={st.cardSub}>{plan.notes[0]}</Text> : null}
        </>
        : <Text style={st.cardSub}>Add conditions or confirm a lab report to get personalised targets.</Text>}
      <View style={st.links}><Button title="Upload a lab report" icon="file-document-outline" secondary onPress={() => router.push('/reports')} /><Button title="Review intake plan" icon="clipboard-pulse-outline" secondary onPress={() => router.push('/intake')} /></View>
    </Card>
    <SectionTitle title="Recent checks" action="See history" onAction={() => router.push('/(tabs)/history')} />
    {latest ? <Pressable accessibilityRole="button" accessibilityLabel={`Open ${latest.food.name}`} onPress={() => { void openAssessment(latest.id).then(() => router.push('/assessment')); }} style={({ pressed }) => pressed && st.pressed}><Card style={st.recent}><View style={st.foodIcon}><MaterialCommunityIcons name="food-apple-outline" size={22} color={colors.primary} /></View><View style={{ flex: 1 }}><Text style={st.cardTitle}>{latest.food.name}</Text><Text style={st.cardSub}>{new Date(latest.created_at).toLocaleString()}</Text></View><Pill label={latest.result.status.replaceAll('_', ' ')} tone={statusTone(latest.result.status)} /></Card></Pressable> : <Card style={st.recent}><View style={{ flex: 1 }}><Text style={st.cardTitle}>No checks yet</Text><Text style={st.cardSub}>Completed assessments will appear here.</Text></View></Card>}
    <Text style={st.footer}>The guide reports available evidence and missing information; it does not guarantee food safety.</Text>
  </Screen>;
}
const st = StyleSheet.create({
  avatar: { width: 44, height: 44, borderRadius: radius.avatar, backgroundColor: colors.lavender, alignItems: 'center', justifyContent: 'center' },
  avatarText: { color: colors.primary, fontSize: 17, fontWeight: '800' },
  hero: { padding: 20, backgroundColor: colors.canvasSoft, borderWidth: 1, borderColor: colors.lavenderLine, gap: 16 },
  heroTop: { flexDirection: 'row', gap: 12, alignItems: 'center' },
  heroTitle: { ...typography.display, color: colors.ink, marginTop: 14 },
  heroCopy: { ...typography.body, color: colors.muted, marginTop: 8, maxWidth: 360 },
  heroIcon: { width: 68, height: 68, borderRadius: radius.card, backgroundColor: colors.lavender, alignItems: 'center', justifyContent: 'center' },
  profileCard: { gap: 14 },
  label: { ...typography.label, color: colors.muted },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  cardTitle: { ...typography.cardTitle, color: colors.ink },
  cardSub: { ...typography.meta, color: colors.muted, marginTop: 4 },
  notice: { flexDirection: 'row', gap: 8, alignItems: 'flex-start', backgroundColor: colors.amberBg, padding: 12, borderRadius: radius.chip },
  noticeText: { flex: 1, ...typography.meta, color: colors.amberInk },
  recent: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 16 },
  foodIcon: { width: 44, height: 44, borderRadius: radius.avatar, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.lavender },
  link: { ...typography.meta, color: colors.primary, fontWeight: '700', paddingVertical: 4 },
  registryHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 9 },
  links: { flexDirection: 'row', flexWrap: 'wrap', gap: 9 },
  error: { backgroundColor: colors.redBg, gap: 9 },
  errorText: { ...typography.meta, color: colors.red },
  footer: { textAlign: 'center', ...typography.caption, color: colors.subtle, paddingHorizontal: 15 },
  pressed: { opacity: 0.9 },
});
