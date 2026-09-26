import React, { useEffect, useState } from 'react';
import { Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Button, Card, DemoBanner, Field, PageHeader, Pill, Screen } from '@/src/components/ui';
import { useApp } from '@/src/state/AppContext';
import { colors } from '@/src/theme';

export default function ReviewScreen() {
  const { product, setProduct, labelPhoto, setLabelPhoto } = useApp();
  const [name, setName] = useState(product.name);
  const [ingredients, setIngredients] = useState(product.ingredients);
  const [advisory, setAdvisory] = useState(product.advisory);
  const [sodium, setSodium] = useState(product.sodium == null ? '' : String(product.sodium));
  const [basis, setBasis] = useState(product.basis);
  const [servingSize, setServingSize] = useState(product.servingSize ?? '');
  const [changed, setChanged] = useState(!product.sample);
  useEffect(() => { setName(product.name); setIngredients(product.ingredients); setAdvisory(product.advisory); setSodium(product.sodium == null ? '' : String(product.sodium)); setBasis(product.basis); setServingSize(product.servingSize ?? ''); setChanged(!product.sample); }, [product.id]);
  const save = () => {
    const parsedSodium = sodium.trim() ? Number(sodium) : null;
    setProduct({ ...product, name, ingredients, advisory, sodium: parsedSodium !== null && Number.isFinite(parsedSodium) ? parsedSodium : null, basis, servingSize, sample: !changed });
    router.push('/assessment');
  };
  return <Screen>
    <PageHeader eyebrow="Before the check" title="Review the label" subtitle="Confirm the product and make corrections from the pack in your hand." back />
    <DemoBanner />
    <Card style={st.product}><View style={[st.productIcon, { backgroundColor: product.color }]}><Text style={{ fontSize: 27 }}>{product.icon}</Text></View><View style={{ flex: 1 }}><Pill label={product.category.toUpperCase()} tone="purple" /><Text style={st.productName}>{name}</Text><Text style={st.brand}>{product.brand} · {product.barcode || 'barcode not entered'}</Text></View></Card>
    {labelPhoto && <Card style={st.photoCard}><View style={st.photoHeading}><View style={{ flex: 1 }}><Text style={st.photoTitle}>Label photo attached</Text><Text style={st.photoCopy}>The photo is shown for your reference; it is not uploaded or read automatically.</Text></View><Pressable accessibilityRole="button" accessibilityLabel="Remove label photo" onPress={() => setLabelPhoto(null)}><MaterialCommunityIcons name="close-circle-outline" size={21} color={colors.muted} /></Pressable></View><Image source={{ uri: labelPhoto }} resizeMode="cover" style={st.photo} /></Card>}
    <View style={st.step}><View style={st.stepNo}><Text style={st.stepNoText}>1</Text></View><View style={{ flex: 1 }}><Text style={st.stepTitle}>Check what the label says</Text><Text style={st.stepCopy}>Keep ingredient and advisory statements in their own fields. Leave anything unreadable blank.</Text></View></View>
    <Card style={st.fields}>
      <Field label="Product name" value={name} onChangeText={value => { setName(value); setChanged(true); }} />
      <Field label="Ingredients" value={ingredients} onChangeText={value => { setIngredients(value); setChanged(true); }} placeholder="Enter the ingredient list" multiline />
      <Field label="Allergen advisory" value={advisory} onChangeText={value => { setAdvisory(value); setChanged(true); }} placeholder="For example: may contain …" multiline />
      <Field label="Sodium amount (mg, optional)" value={sodium} onChangeText={value => { setSodium(value); setChanged(true); }} placeholder="Leave blank if not shown" keyboardType="numeric" />
      <View style={{ gap: 8 }}><Text style={st.basisLabel}>NUTRITION BASIS</Text><View style={st.bases}>{['per 100 g', 'per 100 ml', 'per serving', 'Not supplied'].map(option => <Pressable key={option} onPress={() => { setBasis(option); setChanged(true); }} style={[st.basisOption, basis === option && st.basisOptionSelected]}><Text style={[st.basisOptionText, basis === option && st.basisOptionTextSelected]}>{option}</Text></Pressable>)}</View></View>
      {basis === 'per serving' && <Field label="Serving size (g or ml)" value={servingSize} onChangeText={value => { setServingSize(value); setChanged(true); }} placeholder="Enter the stated serving size" keyboardType="numeric" />}
    </Card>
    <View style={st.tip}><MaterialCommunityIcons name="lightbulb-on-outline" size={18} color={colors.primary} /><Text style={st.tipText}>Check the package variant and serving basis. A blank field means “not available”, not zero.</Text></View>
    <Button title="Save label and view assessment" icon="arrow-right" onPress={save} />
    <Text style={st.caption}>This frontend preview stores corrections in memory for this session. No label is sent to a server.</Text>
  </Screen>;
}
const st = StyleSheet.create({
  product: { flexDirection: 'row', alignItems: 'center', gap: 13, padding: 15 }, productIcon: { width: 58, height: 58, borderRadius: 19, alignItems: 'center', justifyContent: 'center' }, productName: { color: colors.ink, fontSize: 16, fontWeight: '800', marginTop: 8 }, brand: { color: colors.muted, fontSize: 10, marginTop: 4 }, photoCard: { gap: 11 }, photoHeading: { flexDirection: 'row', alignItems: 'center', gap: 9 }, photoTitle: { color: colors.ink, fontSize: 12, fontWeight: '800' }, photoCopy: { color: colors.muted, fontSize: 10, lineHeight: 14, marginTop: 3 }, photo: { width: '100%', height: 180, borderRadius: 14, backgroundColor: colors.canvas },
  step: { flexDirection: 'row', alignItems: 'flex-start', gap: 11, paddingHorizontal: 2 }, stepNo: { width: 24, height: 24, borderRadius: 12, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center' }, stepNoText: { color: '#FFFFFF', fontSize: 11, fontWeight: '800' }, stepTitle: { color: colors.ink, fontSize: 13, fontWeight: '800' }, stepCopy: { color: colors.muted, fontSize: 11, lineHeight: 16, marginTop: 3 },
  fields: { gap: 15 }, basisLabel: { fontSize: 8, letterSpacing: .8, color: colors.muted, fontWeight: '800' }, bases: { flexDirection: 'row', flexWrap: 'wrap', gap: 7 }, basisOption: { paddingHorizontal: 10, paddingVertical: 8, backgroundColor: colors.canvas, borderRadius: 999 }, basisOptionSelected: { backgroundColor: colors.primary }, basisOptionText: { color: colors.muted, fontSize: 10, fontWeight: '700' }, basisOptionTextSelected: { color: '#FFFFFF' },
  tip: { flexDirection: 'row', gap: 9, alignItems: 'flex-start', backgroundColor: colors.lavender, padding: 12, borderRadius: 14 }, tipText: { flex: 1, color: '#4E3AC2', fontSize: 11, lineHeight: 16 }, caption: { textAlign: 'center', color: colors.subtle, fontSize: 10, lineHeight: 14, paddingHorizontal: 15 },
});
