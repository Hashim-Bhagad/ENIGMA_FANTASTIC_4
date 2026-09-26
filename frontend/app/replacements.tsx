import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Card, DemoBanner, PageHeader, Pill, Screen } from '@/src/components/ui';
import { useApp } from '@/src/state/AppContext';
import { colors } from '@/src/theme';

export default function ReplacementsScreen() {
  const { product, products, setProduct } = useApp();
  const candidates = products.filter(item => item.id !== product.id && item.category === product.category);
  return <Screen>
    <PageHeader eyebrow="Compare options" title="Similar products" subtitle={`Same category as ${product.name}.`} back />
    <DemoBanner />
    <Card style={st.context}><View style={st.contextIcon}><MaterialCommunityIcons name="swap-horizontal" size={20} color={colors.primary} /></View><View style={{ flex: 1 }}><Text style={st.title}>Your comparison focus</Text><Text style={st.copy}>Compare like with like, then check every selected restriction.</Text></View><Pill label={product.category} tone="purple" /></Card>
    <View style={st.note}><MaterialCommunityIcons name="information-outline" size={17} color={colors.amber} /><Text style={st.noteText}>The frontend has no product assessment service. These sample records have not passed your full profile checks and are not recommendations.</Text></View>
    {candidates.length ? <>
      <View style={st.heading}><Text style={st.headingTitle}>Available sample comparison</Text><Text style={st.headingSub}>Based on category only · demo values</Text></View>
      {candidates.map(item => <Card key={item.id} style={st.product}>
        <View style={st.productTop}><View style={[st.food, { backgroundColor: item.color }]}><Text style={{ fontSize: 24 }}>{item.icon}</Text></View><View style={{ flex: 1 }}><Text style={st.brand}>{item.brand}</Text><Text style={st.title}>{item.name}</Text><Text style={st.copy}>{item.category}</Text></View><Pill label="NEEDS CHECKS" tone="amber" /></View>
        <View style={st.compare}><View style={st.compareCell}><Text style={st.compareLabel}>SODIUM · CURRENT</Text><Text style={st.compareValue}>{product.sodium == null ? 'Not listed' : `${product.sodium} mg`}</Text><Text style={st.compareUnit}>{product.basis}</Text></View><MaterialCommunityIcons name="arrow-right" size={19} color={colors.subtle} /><View style={st.compareCell}><Text style={st.compareLabel}>SODIUM · EXAMPLE</Text><Text style={st.compareValue}>{item.sodium == null ? 'Not listed' : `${item.sodium} mg`}</Text><Text style={st.compareUnit}>{item.basis}</Text></View></View>
        {item.findings.some(value => value.kind === 'unknown') && <View style={st.pending}><MaterialCommunityIcons name="help-circle-outline" size={16} color={colors.blue} /><Text style={st.pendingText}>Allergen and facility information is incomplete in this demo record.</Text></View>}
        <Pressable onPress={() => { setProduct(item); router.push('/review'); }} style={st.reviewLink}><Text style={st.reviewLinkText}>Review this label</Text><MaterialCommunityIcons name="arrow-right" size={16} color={colors.primary} /></Pressable>
      </Card>)}
    </> : <Card style={st.empty}><View style={st.emptyIcon}><MaterialCommunityIcons name="magnify" color={colors.primary} size={22} /></View><Text style={st.title}>No comparable sample yet</Text><Text style={st.copy}>This frontend only has sample products. Add a catalog service and verified product records before showing alternatives.</Text></Card>}
    <Card style={st.rule}><MaterialCommunityIcons name="check-decagram-outline" size={20} color={colors.green} /><View style={{ flex: 1 }}><Text style={st.title}>What a real comparison needs</Text><Text style={st.copy}>A matching category, complete relevant label evidence, all profile checks, and nutrient values on a compatible basis.</Text></View></Card>
  </Screen>;
}
const st = StyleSheet.create({
  context: { flexDirection: 'row', alignItems: 'center', gap: 11, padding: 14 }, contextIcon: { width: 42, height: 42, borderRadius: 14, backgroundColor: colors.lavender, alignItems: 'center', justifyContent: 'center' }, title: { color: colors.ink, fontSize: 13, lineHeight: 18, fontWeight: '800' }, copy: { color: colors.muted, fontSize: 10, lineHeight: 15, marginTop: 3 }, note: { flexDirection: 'row', gap: 8, alignItems: 'flex-start', backgroundColor: colors.amberBg, borderRadius: 14, padding: 12 }, noteText: { color: '#785015', flex: 1, fontSize: 10, lineHeight: 15 }, heading: { gap: 3 }, headingTitle: { fontSize: 15, color: colors.ink, fontWeight: '800' }, headingSub: { fontSize: 10, color: colors.muted },
  product: { gap: 14, padding: 15 }, productTop: { flexDirection: 'row', alignItems: 'center', gap: 10 }, food: { width: 48, height: 48, borderRadius: 16, alignItems: 'center', justifyContent: 'center' }, brand: { color: colors.muted, fontSize: 9, fontWeight: '700', marginBottom: 3 }, compare: { backgroundColor: colors.canvas, borderRadius: 14, flexDirection: 'row', alignItems: 'center', padding: 12, gap: 9 }, compareCell: { flex: 1, gap: 4 }, compareLabel: { color: colors.muted, fontSize: 8, letterSpacing: .5, fontWeight: '800' }, compareValue: { color: colors.ink, fontSize: 15, fontWeight: '800' }, compareUnit: { color: colors.subtle, fontSize: 9 }, pending: { backgroundColor: colors.blueBg, flexDirection: 'row', alignItems: 'center', gap: 7, borderRadius: 11, padding: 9 }, pendingText: { flex: 1, color: '#285F7D', fontSize: 10, lineHeight: 14 }, reviewLink: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, alignSelf: 'flex-start' }, reviewLinkText: { color: colors.primary, fontSize: 11, fontWeight: '800' }, empty: { alignItems: 'center', gap: 8, padding: 24 }, emptyIcon: { width: 46, height: 46, borderRadius: 16, backgroundColor: colors.lavender, alignItems: 'center', justifyContent: 'center' }, rule: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, backgroundColor: colors.greenBg },
});
