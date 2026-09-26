import React, { useEffect } from 'react';
import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Button, Card, PageHeader, Pill, Screen, SectionTitle } from '@/src/components/ui';
import { statusTone } from '@/src/components/findings';
import { useApp } from '@/src/state/AppContext';
import { colors, radius } from '@/src/theme';

export default function GuideScreen() {
  const { email, conditions, allergens, sodiumLimit, history, loadHistory, openAssessment, guide, guideError, loadGuide, busyFor } = useApp();
  useEffect(() => { void loadHistory(); }, [loadHistory]);
  useEffect(() => { void loadGuide(); }, [loadGuide]);
  const profileName = email.split('@')[0] || 'Food guide';
  const latest = history[0];
  return <Screen>
    <PageHeader eyebrow="Your food companion" title={`Welcome, ${profileName}`} subtitle="Check packaged food against the restrictions you have saved." right={<View style={st.avatar}><Text style={st.avatarText}>{profileName.slice(0, 1).toUpperCase()}</Text></View>} />
    <Card style={st.hero}><View style={st.heroTop}><View style={{ flex: 1 }}><Pill label="PROFILE SAVED TO YOUR ACCOUNT" tone="green" icon="check-circle-outline" /><Text style={st.heroTitle}>Know what's in{ '\n' }your next bite.</Text><Text style={st.heroCopy}>Scan a barcode, search a product, or take a label photo for review.</Text></View><View style={st.heroIcon}><MaterialCommunityIcons name="leaf" size={39} color={colors.green} /></View></View><Button title="Check a packaged food" icon="barcode-scan" onPress={() => router.push('/(tabs)/scan')} /></Card>
    <SectionTitle title="Your saved profile" action="Edit" onAction={() => router.push('/(tabs)/profile')} />
    <Card style={st.profileCard}><Text style={st.label}>ALLERGENS TO CHECK</Text><View style={st.chips}>{allergens.length ? allergens.map(item => <Pill key={item} label={item} tone="red" />) : <Text style={st.cardSub}>No allergies selected</Text>}</View>{conditions.length > 0 && <><Text style={st.label}>CONDITIONS RECORDED</Text><View style={st.chips}>{conditions.map(item => <Pill key={item} label={item} tone="purple" />)}</View></>}<View style={st.notice}><MaterialCommunityIcons name="information-outline" size={17} color={colors.amber} /><Text style={st.noticeText}>{sodiumLimit ? `Daily sodium limit recorded: ${sodiumLimit} mg. A product portion is evaluated only when its amount and portion size are known.` : 'Add personal limits from guidance you trust in your profile.'}</Text></View></Card>
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
    <SectionTitle title="Recent checks" action="See history" onAction={() => router.push('/(tabs)/history')} />
    {latest ? <Pressable accessibilityRole="button" accessibilityLabel={`Open ${latest.food.name}`} onPress={() => { void openAssessment(latest.id).then(() => router.push('/assessment')); }}><Card style={st.recent}><View style={st.foodIcon}><MaterialCommunityIcons name="food-apple-outline" size={22} color={colors.primary} /></View><View style={{ flex: 1 }}><Text style={st.cardTitle}>{latest.food.name}</Text><Text style={st.cardSub}>{new Date(latest.created_at).toLocaleString()}</Text></View><Pill label={latest.result.status.replaceAll('_', ' ')} tone={statusTone(latest.result.status)} /></Card></Pressable> : <Card style={st.recent}><View style={{ flex: 1 }}><Text style={st.cardTitle}>No checks yet</Text><Text style={st.cardSub}>Completed assessments will appear here.</Text></View></Card>}
    <Text style={st.footer}>The guide reports available evidence and missing information; it does not guarantee food safety.</Text>
  </Screen>;
}
const st = StyleSheet.create({ avatar: { width: 40, height: 40, borderRadius: radius.input, backgroundColor: colors.lavender, alignItems: 'center', justifyContent: 'center' }, avatarText: { color: colors.primary, fontSize: 17, fontWeight: '800' }, hero: { padding: 20, backgroundColor: colors.canvasSoft, borderWidth: 1, borderColor: colors.lavenderLine, gap: 16 }, heroTop: { flexDirection: 'row', gap: 10, alignItems: 'center' }, heroTitle: { color: colors.ink, fontSize: 25, lineHeight: 30, fontWeight: '800', marginTop: 13 }, heroCopy: { color: colors.muted, fontSize: 13, lineHeight: 19, marginTop: 7, maxWidth: 340 }, heroIcon: { width: 68, height: 68, borderRadius: 24, backgroundColor: colors.lavender, alignItems: 'center', justifyContent: 'center' }, profileCard: { gap: 13 }, label: { color: colors.muted, letterSpacing: 1, fontSize: 9, fontWeight: '800' }, chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 }, cardTitle: { color: colors.ink, fontSize: 14, fontWeight: '700' }, cardSub: { color: colors.muted, fontSize: 11, lineHeight: 16, marginTop: 4 }, notice: { flexDirection: 'row', gap: 8, alignItems: 'flex-start', backgroundColor: colors.amberBg, padding: 11, borderRadius: radius.chip }, noticeText: { flex: 1, color: colors.amberInk, fontSize: 11, lineHeight: 15 }, recent: { flexDirection: 'row', alignItems: 'center', gap: 11, padding: 13 }, foodIcon: { width: 44, height: 44, borderRadius: radius.input, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.lavender }, link: { color: colors.primary, fontSize: 11, fontWeight: '700', paddingVertical: 2 }, error: { backgroundColor: colors.redBg, gap: 9 }, errorText: { color: colors.red, fontSize: 12, lineHeight: 17 }, footer: { textAlign: 'center', color: colors.subtle, fontSize: 10, lineHeight: 15, paddingHorizontal: 15 } });
