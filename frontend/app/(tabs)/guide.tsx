import React, { useCallback, useEffect, useState } from 'react';
import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';
import { router, useFocusEffect } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Button, Card, Disclosure, PageHeader, Pill, Screen, SectionTitle } from '@/src/components/ui';
import { API_BASE_URL } from '@/src/api/client';
import { backendUnreachableNotice } from '@/src/navigation';
import { statusTone } from '@/src/components/findings';
import { api, ConditionRegistry, conditionLabel, EU_ALLERGENS } from '@/src/api/client';
import { useApp } from '@/src/state/AppContext';
import { colors, radius, typography } from '@/src/theme';

export default function GuideScreen() {
  const { email, token, profile, history, historyTotal, loadHistory, openAssessment, guide, guideError, loadGuide, busyFor, apiStatus, apiDetail, checkApi } = useApp();
  const [registry, setRegistry] = useState<ConditionRegistry | null>(null);
  const [openError, setOpenError] = useState('');
  // Re-probe on focus as well: an outage that starts after sign-in should show up here rather
  // than only as a failed refresh inside individual cards.
  useFocusEffect(useCallback(() => { void checkApi(); void loadHistory(); void loadGuide(); }, [checkApi, loadHistory, loadGuide]));
  useEffect(() => {
    let active = true;
    if (token) void api.conditions(token).then(value => { if (active) setRegistry(value); }).catch(() => undefined);
    return () => { active = false; };
  }, [token]);
  // The home screen describes the saved assessment profile, never unsaved editor state.
  const saved = profile?.data;
  const allergies = (saved?.allergies ?? []).map(value => EU_ALLERGENS.find(item => item.value === value)?.label ?? value);
  const conditions = saved?.conditions ?? [];
  const name = email.split('@')[0] || 'there';
  const open = async (id: string) => {
    setOpenError('');
    try { await openAssessment(id); router.push('/assessment'); }
    catch (cause) { setOpenError(cause instanceof Error ? cause.message : 'This check could not be opened. Please try again.'); }
  };
  const unreachable = apiStatus === 'unreachable' ? backendUnreachableNotice(API_BASE_URL, apiDetail) : null;
  return <Screen>
    {unreachable ? <Card style={{ gap: 10, borderColor: colors.red, borderWidth: 1 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <MaterialCommunityIcons name="server-network-off" size={20} color={colors.red} />
        <Text style={{ flex: 1, color: colors.ink, fontSize: 15, fontWeight: '800' }}>{unreachable.title}</Text>
      </View>
      <Text style={{ color: colors.muted, fontSize: 13, lineHeight: 19 }}>{unreachable.detail}</Text>
      <Button title="Try again" icon="refresh" secondary loading={apiStatus === 'checking'} onPress={() => void checkApi()} />
    </Card> : null}
    <View style={st.brandRow}><View style={st.brandLockup}><View style={st.brandMark}><MaterialCommunityIcons name="leaf" size={21} color={colors.onPrimary} /></View><Text style={st.wordmark}>SafeBitez<Text style={{ color: colors.primary }}>.</Text></Text></View><Pressable accessibilityRole="button" accessibilityLabel="Open your profile" onPress={() => router.push('/(tabs)/profile')} style={st.avatar}><Text style={st.avatarText}>{name.slice(0, 1).toUpperCase()}</Text></Pressable></View>
    <View style={st.hero}>
      <View style={st.heroTop}><Text style={st.heroEyebrow}>YOUR EVERYDAY FOOD COMPANION</Text><MaterialCommunityIcons name="silverware-fork-knife" size={26} color={colors.accent} /></View>
      <Text accessibilityRole="header" style={st.heroTitle}>A little clarity.{ '\n' }Before every bite.</Text>
      <Text style={st.heroCopy}>Hi {name}. Start with what's on your plate. We'll check the available ingredients against your saved restrictions.</Text>
      <View style={st.heroFooter}><MaterialCommunityIcons name="text-box-check-outline" size={18} color={colors.accent} /><Text style={st.heroNote}>Your ingredients. Your profile. Evidence you can read.</Text></View>
    </View>
    <SectionTitle title="What are you checking?" />
    <View style={st.choices}>
      <FoodChoice title="Packaged food" copy="Search a product, enter a barcode, or read a label photo." icon="barcode-scan" action="Find a product" onPress={() => router.push('/(tabs)/scan')} />
      <FoodChoice title="A cooked meal" copy="Explore a dish, then confirm its ingredients and preparation." icon="silverware-fork-knife" action="Check a meal" meal onPress={() => router.push('/dish')} />
    </View>
    <SectionTitle title="Your saved profile" action="Edit profile" onAction={() => router.push('/(tabs)/profile')} />
    <Card style={st.profileCard}>
      <View style={st.row}><View style={st.icon}><MaterialCommunityIcons name="account-check-outline" size={24} color={colors.primary} /></View><View style={{ flex: 1 }}><Text style={st.cardTitle}>Made personal to you</Text><Text style={st.copy}>These are the settings used for new checks.</Text></View><Pill label={profile ? `Version ${profile.version}` : 'Set up'} tone={profile ? 'blue' : 'amber'} /></View>
      <View style={st.chips}>{allergies.map(item => <Pill key={item} label={item} tone="red" />)}{conditions.map(item => <Pill key={item} label={conditionLabel(item, registry)} tone="purple" />)}{saved?.ingredient_exclusions.map(item => <Pill key={`exclusion-${item}`} label={item} tone="amber" />)}{!allergies.length && !conditions.length && !saved?.ingredient_exclusions.length ? <Text style={st.copy}>No allergies, conditions or ingredient exclusions recorded.</Text> : null}</View>
      {saved?.limits.map(limit => <Text key={`${limit.nutrient}-${limit.scope}`} style={st.copy}>{limit.nutrient.replaceAll('_', ' ')}: {limit.maximum} maximum · {limit.scope.replaceAll('_', ' ')}</Text>)}
    </Card>
    <SectionTitle title="Recent checks" action="View history" onAction={() => router.push('/(tabs)/history')} />
    {openError ? <Text accessibilityRole="alert" style={st.errorText}>{openError}</Text> : null}
    {history.length ? <View style={{ gap: 10 }}>{history.slice(0, 3).map(item => <Pressable key={item.id} accessibilityRole="button" accessibilityLabel={`Open ${item.food.name}`} onPress={() => void open(item.id)} style={({ pressed }) => pressed && st.pressed}><Card style={st.row}><View style={st.icon}><MaterialCommunityIcons name={item.food.source.kind === 'dish' ? 'silverware-fork-knife' : 'food-apple-outline'} size={23} color={colors.primary} /></View><View style={{ flex: 1 }}><Text style={st.cardTitle}>{item.food.name}</Text><Text style={st.copy}>{new Date(item.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</Text><View style={{ marginTop: 8 }}><Pill label={item.result.status.replaceAll('_', ' ')} tone={statusTone(item.result.status)} /></View></View><MaterialCommunityIcons name="chevron-right" size={22} color={colors.muted} /></Card></Pressable>)}<Text style={st.caption}>{historyTotal} saved checks in your history</Text></View> : <Card style={st.profileCard}><Text style={st.cardTitle}>{busyFor('history') ? 'Loading your recent checks…' : 'Your first check starts here'}</Text><Text style={st.copy}>Choose a packaged food or a cooked meal above. Completed assessments are saved here with the profile used.</Text></Card>}
    <SectionTitle title="Beyond the label" />
    <View style={st.choices}><Pressable accessibilityRole="button" onPress={() => router.push('/reports')} style={st.utility}><MaterialCommunityIcons name="file-document-outline" size={24} color={colors.primary} /><Text style={st.cardTitle}>Lab reports</Text><Text style={st.copy}>Upload and confirm your results.</Text><Text style={st.link}>Open reports →</Text></Pressable><Pressable accessibilityRole="button" onPress={() => router.push('/intake')} style={st.utility}><MaterialCommunityIcons name="clipboard-pulse-outline" size={24} color={colors.primary} /><Text style={st.cardTitle}>Personal intake</Text><Text style={st.copy}>Review proposed nutrient targets.</Text><Text style={st.link}>Review your plan →</Text></Pressable></View>
    <Disclosure title="Guidance for your profile" subtitle="Recorded checks, condition information and useful questions.">
      {guideError ? <><Text accessibilityRole="alert" style={st.errorText}>{guideError}</Text><Button title="Retry guidance" secondary onPress={() => void loadGuide()} /></> : !guide ? <Text style={st.copy}>{busyFor('guide') ? 'Loading guidance…' : 'Save your profile to see guidance.'}</Text> : <>
        <Text style={st.label}>INGREDIENTS TO CHECK</Text><View style={st.chips}>{guide.exclusions.length ? guide.exclusions.map(item => <Pill key={item} label={item.replaceAll('_', ' ')} tone="red" />) : <Text style={st.copy}>None recorded.</Text>}</View>
        {guide.recorded_limits.map(limit => <Text key={`${limit.nutrient}-${limit.scope}`} style={st.copy}>{limit.nutrient.replaceAll('_', ' ')}: max {limit.maximum} · {limit.scope} · {limit.source}</Text>)}
        {guide.comparison_goals.length ? <View style={st.chips}>{guide.comparison_goals.map(goal => <Pill key={goal.nutrient} label={`${goal.nutrient.replaceAll('_', ' ')}: ${goal.direction}`} tone="blue" />)}</View> : null}
        {guide.condition_information.map(item => <View key={item.condition} style={st.guidance}><Text style={st.cardTitle}>{item.condition}</Text><Text style={st.copy}>{item.message}</Text><Pressable accessibilityRole="link" onPress={() => void Linking.openURL(item.source)}><Text style={st.link}>Read source guidance ↗</Text></Pressable></View>)}
        {guide.unsupported_conditions.length ? <Text style={st.notice}>Guidance is not available for: {guide.unsupported_conditions.join(', ')}. Record explicit restrictions provided by your clinician.</Text> : null}
        {guide.questions.map((question, index) => <Text key={index} style={st.copy}>• {question}</Text>)}<Text style={st.caption}>{guide.coverage}</Text>
      </>}
    </Disclosure>
    <Text style={st.footer}>A clearer picture of what's known. Missing information stays unknown; a check is not a food-safety guarantee.</Text>
  </Screen>;
}

function FoodChoice({ title, copy, icon, action, meal = false, onPress }: { title: string; copy: string; icon: keyof typeof MaterialCommunityIcons.glyphMap; action: string; meal?: boolean; onPress: () => void }) {
  return <Pressable accessibilityRole="button" accessibilityLabel={`${title}. ${action}`} onPress={onPress} style={({ pressed }) => [st.choice, meal && st.mealChoice, pressed && st.pressed]}><View style={[st.choiceIcon, meal && { backgroundColor: colors.orangeBg }]}><MaterialCommunityIcons name={icon} size={28} color={meal ? colors.amberInk : colors.primary} /></View><Text style={st.choiceTitle}>{title}</Text><Text style={st.copy}>{copy}</Text><View style={st.choiceAction}><Text style={st.link}>{action}</Text><MaterialCommunityIcons name="arrow-right" size={20} color={colors.primary} /></View></Pressable>;
}
const st = StyleSheet.create({
  brandRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }, brandLockup: { flexDirection: 'row', alignItems: 'center', gap: 9 }, brandMark: { backgroundColor: colors.primary, width: 36, height: 36, borderRadius: 12, alignItems: 'center', justifyContent: 'center' }, wordmark: { ...typography.title, color: colors.ink, letterSpacing: -0.7 }, avatar: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.lavender, alignItems: 'center', justifyContent: 'center' }, avatarText: { ...typography.bodyStrong, color: colors.primary },
  hero: { borderRadius: 28, backgroundColor: colors.hero, padding: 26, gap: 17 }, heroTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 10 }, heroEyebrow: { ...typography.label, color: colors.accent, flex: 1 }, heroTitle: { fontSize: 38, lineHeight: 44, fontWeight: '800', letterSpacing: -1.3, color: colors.onPrimary }, heroCopy: { ...typography.body, color: colors.heroText, maxWidth: 540 }, heroFooter: { flexDirection: 'row', gap: 8, borderTopWidth: 1, borderColor: '#376066', paddingTop: 17, alignItems: 'center' }, heroNote: { ...typography.caption, color: colors.heroText, flex: 1 },
  choices: { flexDirection: 'row', flexWrap: 'wrap', gap: 14 }, choice: { flexGrow: 1, flexBasis: 260, backgroundColor: colors.surface, padding: 22, borderRadius: radius.card, borderWidth: 1, borderColor: colors.lavenderLine, gap: 10 }, mealChoice: { borderColor: '#E7E2D7' }, choiceIcon: { width: 54, height: 54, borderRadius: 18, backgroundColor: colors.lavender, alignItems: 'center', justifyContent: 'center', marginBottom: 5 }, choiceTitle: { ...typography.title, color: colors.ink }, choiceAction: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 },
  profileCard: { gap: 16 }, row: { flexDirection: 'row', alignItems: 'center', gap: 12 }, icon: { width: 44, height: 44, borderRadius: 14, backgroundColor: colors.lavenderSoft, alignItems: 'center', justifyContent: 'center' }, cardTitle: { ...typography.cardTitle, color: colors.ink }, copy: { ...typography.meta, color: colors.muted, marginTop: 3 }, chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 }, caption: { ...typography.caption, color: colors.muted }, utility: { flexGrow: 1, flexBasis: 240, padding: 20, borderRadius: radius.card, backgroundColor: colors.lavenderSoft, gap: 9 }, link: { ...typography.meta, fontWeight: '700', color: colors.primary, paddingVertical: 8 }, label: { ...typography.label, color: colors.muted }, guidance: { gap: 6, borderTopWidth: 1, borderColor: colors.line, paddingTop: 16 }, notice: { ...typography.meta, color: colors.amberInk, backgroundColor: colors.amberBg, padding: 12, borderRadius: radius.chip }, errorText: { ...typography.meta, color: colors.red }, footer: { ...typography.caption, color: colors.muted, textAlign: 'center', paddingHorizontal: 16 }, pressed: { opacity: 0.8 },
});
