import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Card, DemoBanner, PageHeader, Pill, Screen, SectionTitle, Button, MiniIcon } from '@/src/components/ui';
import { demoHistory } from '@/src/data/demo';
import { colors } from '@/src/theme';
import { useApp } from '@/src/state/AppContext';

export default function GuideScreen() {
  const { profileName, product, setProduct, products, conditions, allergens, sodiumLimit } = useApp();
  return <Screen>
    <PageHeader eyebrow="Your food companion" title={`Good morning, ${profileName}`} subtitle="A clear place to check labels and keep your food preferences close." right={<View style={st.avatar}><Text style={st.avatarText}>{profileName.slice(0, 1)}</Text></View>} />
    <DemoBanner />
    <Card style={st.hero}>
      <View style={st.heroTop}><View style={{ flex: 1 }}><Pill label="YOUR PROFILE IS READY" tone="green" icon="check-circle-outline" /><Text style={st.heroTitle}>Know what's in{ '\n' }your next bite.</Text><Text style={st.heroCopy}>Check a packaged food against the ingredients and limits you've recorded.</Text></View><View style={st.heroIcon}><MaterialCommunityIcons name="leaf" size={39} color={colors.green} /><View style={st.spark}><MaterialCommunityIcons name="sparkles" size={17} color={colors.primary} /></View></View></View>
      <Button title="Check a packaged food" icon="barcode-scan" onPress={() => router.push('/scan')} />
      <Pressable onPress={() => router.push('/dish')} style={st.dishLink}><MaterialCommunityIcons name="silverware-fork-knife" size={17} color={colors.primary} /><Text style={st.dishLinkText}>Checking a dish at a restaurant?</Text><MaterialCommunityIcons name="arrow-right" size={17} color={colors.primary} /></Pressable>
    </Card>
    <SectionTitle title="Your food profile" action="Edit profile" onAction={() => router.push('/profile')} />
    <Card style={st.profileCard}>
      <View style={st.profileHead}><MiniIcon icon="shield-heart-outline" color={colors.primary} bg={colors.lavender} /><View style={{ flex: 1 }}><Text style={st.cardTitle}>Personal guide</Text><Text style={st.cardSub}>These are the details you've chosen to track</Text></View><MaterialCommunityIcons name="chevron-right" size={21} color={colors.subtle} /></View>
      <View style={st.divider} />
      <Text style={st.label}>ALLERGENS TO CHECK</Text><View style={st.chips}>{allergens.length ? allergens.map(item => <Pill key={item} label={item} tone="red" />) : <Text style={st.cardSub}>None selected</Text>}</View>
      {conditions.length > 0 && <><Text style={st.label}>SELECTED CONDITIONS</Text><View style={st.chips}>{conditions.map(item => <Pill key={item} label={item} tone="purple" />)}</View></>}
      <View style={st.notice}><MaterialCommunityIcons name="information-outline" size={17} color={colors.amber} /><Text style={st.noticeText}>{sodiumLimit ? `Sodium limit entered: ${sodiumLimit} mg/day. This preview does not apply it to checks.` : 'No personal nutrient limits set. Add a clinician-provided limit in your profile if you have one.'}</Text></View>
    </Card>
    <SectionTitle title="Pick up where you left off" action="See history" onAction={() => router.push('/history')} />
    <Pressable onPress={() => { setProduct(products.find(item => item.id === demoHistory[0].id) ?? product); router.push('/assessment'); }}>
      <Card style={st.recent}><View style={[st.foodIcon, { backgroundColor: demoHistory[0].color }]}><Text style={{ fontSize: 24 }}>{demoHistory[0].icon}</Text></View><View style={{ flex: 1 }}><Text style={st.cardTitle}>{demoHistory[0].product}</Text><Text style={st.cardSub}>{demoHistory[0].date}</Text></View><Pill label="2 findings" tone="red" /><MaterialCommunityIcons name="chevron-right" size={19} color={colors.subtle} /></Card>
    </Pressable>
    <View style={st.footer}><MaterialCommunityIcons name="heart-outline" size={14} color={colors.subtle} /><Text style={st.footerText}>Food choices are personal. Your guide only reflects details you've recorded.</Text></View>
  </Screen>;
}

const st = StyleSheet.create({
  avatar: { width: 40, height: 40, borderRadius: 15, backgroundColor: colors.lavender, alignItems: 'center', justifyContent: 'center' }, avatarText: { color: colors.primary, fontSize: 17, fontWeight: '800' },
  hero: { padding: 20, backgroundColor: '#FBFAFF', borderWidth: 1, borderColor: '#EFECFF', gap: 16 }, heroTop: { flexDirection: 'row', gap: 4, alignItems: 'center' }, heroTitle: { color: colors.ink, fontSize: 25, lineHeight: 30, fontWeight: '800', letterSpacing: -.45, marginTop: 13 }, heroCopy: { color: colors.muted, fontSize: 13, lineHeight: 19, marginTop: 7, maxWidth: 340 }, heroIcon: { width: 78, height: 78, borderRadius: 27, backgroundColor: '#EEEAFE', alignItems: 'center', justifyContent: 'center', position: 'relative' }, spark: { position: 'absolute', right: -5, top: -7, backgroundColor: '#FFFFFF', borderRadius: 10, padding: 5 },
  dishLink: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 7, paddingTop: 1 }, dishLinkText: { color: colors.primary, fontSize: 12, fontWeight: '700' },
  profileCard: { gap: 15 }, profileHead: { flexDirection: 'row', alignItems: 'center', gap: 12 }, cardTitle: { color: colors.ink, fontSize: 14, fontWeight: '700' }, cardSub: { color: colors.muted, fontSize: 11, lineHeight: 16, marginTop: 4 }, divider: { height: 1, backgroundColor: colors.line }, label: { color: colors.muted, letterSpacing: 1, fontSize: 9, fontWeight: '800' }, chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: -7 }, notice: { flexDirection: 'row', gap: 8, alignItems: 'flex-start', backgroundColor: colors.amberBg, padding: 11, borderRadius: 13 }, noticeText: { flex: 1, color: '#785015', fontSize: 11, lineHeight: 15 },
  recent: { flexDirection: 'row', alignItems: 'center', gap: 11, padding: 13 }, foodIcon: { width: 44, height: 44, borderRadius: 15, alignItems: 'center', justifyContent: 'center' }, footer: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', gap: 6, paddingVertical: 3 }, footerText: { maxWidth: 300, textAlign: 'center', color: colors.subtle, fontSize: 10, lineHeight: 14 },
});
