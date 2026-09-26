import React, { useEffect, useState } from 'react';
import { Image, Linking, Pressable, StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Button, Card, Field, PageHeader, Pill, Screen } from '@/src/components/ui';
import { api, type Allergen, type FoodObservation, type ProductProvenance } from '@/src/api/client';
import { nutrientFields, nutrientInputs } from '@/src/data/nutrients';
import { useApp } from '@/src/state/AppContext';
import { colors, radius, typography } from '@/src/theme';

const ALLERGEN_OPTIONS: { value: Allergen; label: string }[] = [
  { value: 'wheat', label: 'Wheat' }, { value: 'milk', label: 'Milk' }, { value: 'eggs', label: 'Eggs' },
  { value: 'soy', label: 'Soy' }, { value: 'peanuts', label: 'Peanuts' }, { value: 'tree_nuts', label: 'Tree nuts' },
  { value: 'sesame', label: 'Sesame' }, { value: 'fish', label: 'Fish' }, { value: 'shellfish', label: 'Shellfish' },
];

export default function ReviewScreen() {
  const { product, setProduct, labelPhoto, setLabelPhoto, createAssessment, busyFor, error, clearError, token } = useApp();
  const original = product.observation;
  const [name, setName] = useState(product.name);
  const [barcodeValue, setBarcodeValue] = useState(product.barcode || product.observation?.barcode || '');
  const [ingredients, setIngredients] = useState(product.ingredients);
  const [advisory, setAdvisory] = useState(product.advisory);
  const [declared, setDeclared] = useState<Allergen[]>(original?.declared_allergens ?? []);
  const [nutrition, setNutrition] = useState(() => nutrientInputs(original));
  const [basis, setBasis] = useState(product.basis);
  const [portion, setPortion] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [validationError, setValidationError] = useState('');
  const [provenance, setProvenance] = useState<ProductProvenance | null>(null);
  const [traceOpen, setTraceOpen] = useState(false);
  useEffect(() => {
    setName(product.name); setIngredients(product.ingredients); setAdvisory(product.advisory);
    // The barcode that came with a scanned or photographed pack stays on screen and editable.
    setBarcodeValue(product.barcode || product.observation?.barcode || '');
    setDeclared(product.observation?.declared_allergens ?? []);
    setNutrition(nutrientInputs(product.observation)); setBasis(product.basis);
    setPortion(''); setConfirmed(false); setValidationError(''); setProvenance(null); setTraceOpen(false);
  }, [product.id]);
  useEffect(() => {
    let active = true;
    if (token && /^[0-9a-f-]{36}$/i.test(product.id)) {
      api.provenance(token, product.id).then(value => { if (active) setProvenance(value); }).catch(() => { /* The observation source remains visible when a catalog trace is unavailable. */ });
    }
    return () => { active = false; };
  }, [product.id, token]);

  const submit = async () => {
    clearError(); setValidationError('');
    const normalizedBasis: FoodObservation['basis'] = basis === 'per 100 g' ? '100g' : basis === 'per 100 ml' ? '100ml' : null;
    const nutrients: FoodObservation['nutrients'] = {};
    for (const { key, label } of nutrientFields) {
      const input = nutrition[key].trim();
      const value = input ? Number(input) : null;
      if (value !== null && (!Number.isFinite(value) || value < 0)) { setValidationError(`${label} must be a nonnegative number or left blank.`); return; }
      nutrients[key] = value;
    }
    if (!normalizedBasis && Object.values(nutrients).some(value => value != null)) { setValidationError('Select the nutrition basis printed on the label before entering amounts.'); return; }
    const changed = original ? [
      ...(name.trim() !== original.name ? ['name'] : []),
      ...((barcodeValue.trim() || null) !== (original.barcode || null) ? ['barcode'] : []),
      ...((ingredients.trim() || null) !== original.ingredients_text ? ['ingredients_text'] : []),
      ...((advisory.trim() || null) !== (original.advisories_text || null) ? ['advisories_text'] : []),
      ...(normalizedBasis !== original.basis ? ['basis'] : []),
      ...nutrientFields.filter(({ key }) => (nutrients[key] ?? null) !== (original.nutrients[key] ?? null)).map(({ key }) => key),
    ] : [];
    const observation: FoodObservation = {
      name: name.trim(), brand: original?.brand ?? (product.brand === 'Your label' ? null : product.brand),
      barcode: barcodeValue.trim() || null, category: original?.category ?? null,
      basis: normalizedBasis, ingredients_text: ingredients.trim() || null,
      advisories_text: confirmed ? advisory.trim() : advisory.trim() || null,
      ingredients_complete: confirmed && Boolean(ingredients.trim()), advisories_complete: confirmed,
      declared_allergens: declared, precautionary_allergens: original?.precautionary_allergens ?? [],
      reported_allergens: original?.reported_allergens ?? [], nutrients,
      source: original ? { ...original.source, edited_fields: [...new Set([...(original.source.edited_fields || []), ...changed])] } : { kind: 'manual', reference: 'User reviewed label', warnings: [], edited_fields: [] },
    };
    if (confirmed && !ingredients.trim()) { setValidationError('Enter the complete ingredient list before confirming it.'); return; }
    const grams = portion.trim() ? Number(portion) : null;
    if (grams !== null && (!Number.isFinite(grams) || grams <= 0)) { setValidationError('Portion must be a positive number or left blank.'); return; }
    const nextProduct = { ...product, name: observation.name, barcode: observation.barcode ?? '', ingredients: observation.ingredients_text || '', advisory: observation.advisories_text || '', sodium: observation.nutrients.sodium_mg ?? null, basis: normalizedBasis ? normalizedBasis === '100ml' ? 'per 100 ml' : 'per 100 g' : 'Not supplied', sample: false, observation };
    setProduct(nextProduct);
    try { await createAssessment(grams, observation); router.push('/assessment'); }
    catch { /* The shared API error is rendered below so the user can correct or retry. */ }
  };

  return <Screen>
    <PageHeader title="Review the label" subtitle="Correct the observations using the product in your hand." back backFallback="/(tabs)/scan" />
    <Card style={st.product}><View style={[st.productIcon, { backgroundColor: product.color }]}><Text style={{ fontSize: 27 }}>{product.icon}</Text></View><View style={{ flex: 1 }}><Pill label={product.category.toUpperCase()} tone="purple" /><Text style={st.productName}>{name}</Text><Text style={st.brand}>{product.brand} · {barcodeValue.trim() || 'barcode not entered'}</Text></View></Card>
    {labelPhoto && <Card style={st.photoCard}><View style={st.photoHeading}><View style={{ flex: 1 }}><Text style={st.photoTitle}>Label photo attached</Text><Text style={st.photoCopy}>Model extraction can be wrong. Compare each field with the actual package.</Text></View><Pressable accessibilityRole="button" accessibilityLabel="Remove label photo" onPress={() => setLabelPhoto(null)}><MaterialCommunityIcons name="close-circle-outline" size={21} color={colors.muted} /></Pressable></View><Image source={{ uri: labelPhoto }} resizeMode="cover" style={st.photo} /></Card>}
    {original?.source.warnings?.map((warning, index) => <Card key={index} style={st.warning}><MaterialCommunityIcons name="information-outline" size={17} color={colors.amber} /><Text style={st.warningText}>{warning}</Text></Card>)}
    {original ? <Card style={st.sourceCard}>
      <Text style={st.photoTitle}>Where this information came from</Text>
      <Text style={st.photoCopy}>{original.source.kind === 'openfoodfacts' ? 'Open Food Facts community record' : original.source.kind === 'label_extraction' ? 'AI reading of your uploaded label photo' : original.source.kind === 'demo' ? 'Synthetic demo record' : original.source.kind === 'apify_off' ? 'Imported Open Food Facts dataset' : 'Manually entered label observations'}</Text>
      <Text selectable style={st.photoCopy}>{original.source.reference}</Text>
      {original.source.retrieved_at ? <Text style={st.photoCopy}>Retrieved: {original.source.retrieved_at}</Text> : null}
      {/^https?:\/\//i.test(original.source.reference) ? <Pressable accessibilityRole="link" onPress={() => void Linking.openURL(original.source.reference)}><Text style={st.link}>Open source record ↗</Text></Pressable> : null}
      <Text style={st.photoCopy}>Sodium and salt are different fields. These amounts use the selected basis; blank values remain unknown. Confirm the current package.</Text>
      {provenance ? <><Pressable accessibilityRole="button" accessibilityState={{ expanded: traceOpen }} onPress={() => setTraceOpen(value => !value)}><Text style={st.link}>{traceOpen ? 'Hide value trace' : 'Show source fields and conversions'}</Text></Pressable>{traceOpen ? provenance.fields.filter(item => nutrientFields.some(field => field.key === item.field)).map(item => <View key={item.field} style={st.traceRow}><Text style={st.traceTitle}>{nutrientFields.find(field => field.key === item.field)?.label}: {item.value == null ? 'Unknown' : `${String(item.value)} ${item.unit || ''}`} {item.basis ? `/ ${item.basis}` : ''}</Text><Text selectable style={st.photoCopy}>{item.source_field || 'No source field'}{item.source_value == null ? '' : ` = ${typeof item.source_value === 'object' ? JSON.stringify(item.source_value) : String(item.source_value)} ${item.source_unit || ''}`}</Text><Text style={st.photoCopy}>{item.transformation || item.reason || item.status}</Text></View>) : null}</> : <Text style={st.photoCopy}>No catalog field trace is attached to this observation.</Text>}
      {traceOpen && provenance?.source_salt ? <Text selectable style={st.photoCopy}>Source salt field: {provenance.source_salt.source_value == null ? 'Unknown' : `${String(provenance.source_salt.source_value)} ${provenance.source_salt.source_unit}`}. {provenance.source_salt.reason}</Text> : null}
      <Text style={st.photoCopy}>The trace describes the saved source values. Your corrections below are saved separately with the assessment.</Text>
    </Card> : null}
    <Card style={st.fields}>
      <Field label="Product name" value={name} onChangeText={setName} />
      <Field label="Barcode (optional)" value={barcodeValue} onChangeText={setBarcodeValue} placeholder="Digits printed under the barcode" keyboardType="numeric" />
      <Text style={st.photoCopy}>A barcode keeps this pack attached to its saved record so the next lookup finds it. Leave it blank when the package carries none.</Text>
      <Field label="Ingredients" value={ingredients} onChangeText={setIngredients} placeholder="Enter the ingredient list" multiline />
      <Field label="Allergen advisory" value={advisory} onChangeText={setAdvisory} placeholder="Enter the exact may-contain statement, or leave blank" multiline />
      <View style={{ gap: 8 }}><Text style={st.basisLabel}>NUTRITION BASIS</Text><View style={st.bases}>{['per 100 g', 'per 100 ml', 'Not supplied'].map(option => <Pressable key={option} onPress={() => { if (option !== basis) { setNutrition(nutrientInputs()); setBasis(option); } }} style={[st.basisOption, basis === option && st.basisOptionSelected]}><Text style={[st.basisOptionText, basis === option && st.basisOptionTextSelected]}>{option}</Text></Pressable>)}</View><Text style={st.photoCopy}>Changing the basis clears amounts so values cannot be silently relabelled.</Text></View>
      {nutrientFields.map(({ key, label, unit }) => <Field key={key} label={`${label} (${unit}, optional)`} value={nutrition[key]} onChangeText={value => setNutrition(current => ({ ...current, [key]: value }))} placeholder="Leave blank if not listed" keyboardType="numeric" />)}
      <Field label={basis === 'per 100 ml' ? 'Portion checked (ml, optional)' : 'Portion checked (g, optional)'} value={portion} onChangeText={setPortion} placeholder="Needed to calculate your portion" keyboardType="numeric" />
    </Card>
    <Card style={st.fields}>
      <View style={{ gap: 8 }}><Text style={st.basisLabel}>DECLARED ALLERGENS PRINTED ON THE PACKAGE</Text><View style={st.bases}>{ALLERGEN_OPTIONS.map(option => { const active = declared.includes(option.value); return <Pressable key={option.value} accessibilityRole="checkbox" accessibilityState={{ checked: active }} accessibilityLabel={option.label} onPress={() => setDeclared(current => active ? current.filter(value => value !== option.value) : [...current, option.value])} style={[st.basisOption, active && st.basisOptionSelected]}><Text style={[st.basisOptionText, active && st.basisOptionTextSelected]}>{option.label}</Text></Pressable>; })}</View><Text style={st.photoCopy}>Select only allergens the package declares in the ingredient or contains statement. Leaving them unselected keeps the declaration unknown; the precautionary (may-contain) text stays in the advisory field above.</Text></View>
    </Card>
    <Pressable accessibilityRole="checkbox" accessibilityState={{ checked: confirmed }} accessibilityLabel="Confirm the ingredient list and advisory were checked against the package" onPress={() => setConfirmed(value => !value)} style={({ pressed }) => [st.confirm, pressed && st.pressed]}><MaterialCommunityIcons name={confirmed ? 'checkbox-marked' : 'checkbox-blank-outline'} size={23} color={confirmed ? colors.primary : colors.muted} /><Text style={st.confirmText}>I checked the complete ingredient list and allergen advisory against this package. If no advisory is printed, I left that field blank.</Text></Pressable>
    <Card style={st.tip}><MaterialCommunityIcons name="lightbulb-on-outline" size={18} color={colors.primary} /><Text style={st.tipText}>An unchecked declaration stays incomplete. Missing amounts remain unknown; a portion is needed for recorded limits.</Text></Card>
    {validationError || error ? <Text accessibilityRole="alert" style={st.error}>{validationError || error}</Text> : null}
    <Button title="Assess this product" icon="arrow-right" loading={busyFor('assess')} disabled={busyFor('assess')} onPress={() => void submit()} />
    <Text style={st.caption}>Your confirmed observations and profile version are sent to the backend and saved with this assessment.</Text>
  </Screen>;
}
const st = StyleSheet.create({
  sourceCard: { gap: 8, backgroundColor: colors.lavender },
  link: { color: colors.primary, ...typography.meta, fontWeight: '700', paddingVertical: 6 },
  traceRow: { borderTopWidth: 1, borderTopColor: colors.line, paddingTop: 10, gap: 3 },
  traceTitle: { color: colors.ink, fontSize: 14, lineHeight: 20, fontWeight: '700' },
  product: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 16 },
  productIcon: { width: 58, height: 58, borderRadius: radius.control, alignItems: 'center', justifyContent: 'center' },
  productName: { ...typography.cardTitle, color: colors.ink, marginTop: 8 },
  brand: { ...typography.meta, color: colors.muted, marginTop: 4 },
  photoCard: { gap: 12 },
  photoHeading: { flexDirection: 'row', alignItems: 'center', gap: 9 },
  photoTitle: { color: colors.ink, fontSize: 14, lineHeight: 20, fontWeight: '800' },
  photoCopy: { ...typography.meta, color: colors.muted, marginTop: 3 },
  photo: { width: '100%', height: 200, borderRadius: radius.control, backgroundColor: colors.canvas },
  fields: { gap: 16 },
  basisLabel: { ...typography.label, color: colors.muted },
  bases: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  basisOption: { paddingHorizontal: 14, paddingVertical: 10, backgroundColor: colors.canvas, borderRadius: radius.pill },
  basisOptionSelected: { backgroundColor: colors.primary },
  basisOptionText: { color: colors.muted, ...typography.meta, fontWeight: '700' },
  basisOptionTextSelected: { color: colors.onPrimary },
  confirm: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, paddingHorizontal: 3, paddingVertical: 6, minHeight: 44 },
  confirmText: { flex: 1, color: colors.ink, ...typography.meta },
  tip: { flexDirection: 'row', gap: 9, alignItems: 'flex-start', backgroundColor: colors.lavender },
  tipText: { flex: 1, color: colors.purpleInk, ...typography.meta },
  caption: { textAlign: 'center', ...typography.caption, color: colors.subtle, paddingHorizontal: 15 },
  error: { ...typography.meta, color: colors.red },
  warning: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, backgroundColor: colors.amberBg },
  warningText: { flex: 1, color: colors.amberInk, ...typography.meta },
  pressed: { opacity: 0.85 },
});
