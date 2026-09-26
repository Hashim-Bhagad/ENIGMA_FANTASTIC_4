import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { router } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import { Button, Card, Field, PageHeader, Pill, Screen, SectionTitle } from '@/src/components/ui';
import { api, isUsableBarcode, labelExtractionMessage, labelFallbackOffer, type FssaiVerification, type LabelFallbackPrompt, type Product } from '@/src/api/client';
import { useApp } from '@/src/state/AppContext';
import { colors, radius, typography } from '@/src/theme';

export default function ScanScreen() {
  const { product, products, setProduct, search, setSearch, setLabelPhoto, lookupBarcode, searchCatalog, extractLabel, busyFor, token, catalogMessage, loadCatalog } = useApp();
  const [barcode, setBarcode] = useState('');
  const [fssaiNumber, setFssaiNumber] = useState('');
  const [fssaiResult, setFssaiResult] = useState<FssaiVerification | null>(null);
  const [fssaiError, setFssaiError] = useState('');
  const [fssaiBusy, setFssaiBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [fallback, setFallback] = useState<LabelFallbackPrompt | null>(null);
  const [category, setCategory] = useState('All');
  const [cameraVisible, setCameraVisible] = useState(false);
  const [permission, requestPermission] = useCameraPermissions();
  const scanned = useRef(false);
  const busy = busyFor('search') || busyFor('barcode') || busyFor('label');
  useEffect(() => { if (token && !products.length) void loadCatalog().catch(() => undefined); }, [token, loadCatalog]);
  const categories = ['All', ...new Set(products.map(item => item.category))];
  const visible = useMemo(() => products.filter(item => category === 'All' || item.category === category), [products, category]);

  const select = (item: Product) => { setProduct(item); setLabelPhoto(null); setSearch(''); setMessage(''); setFallback(null); router.push('/review'); };
  const lookup = async (value = barcode) => {
    if (!value.trim()) { setMessage('Enter the barcode printed on the product.'); return; }
    setFallback(null);
    try { select(await lookupBarcode(value)); }
    catch (cause) {
      // A missing record is exactly what the ingredient-list photo can answer, so the
      // screen offers it instead of leaving the user with a bare error.
      const offer = labelFallbackOffer({ barcode: value, error: cause });
      setFallback(offer);
      setMessage(offer ? '' : cause instanceof Error ? cause.message : 'Product lookup failed.');
    }
  };
  const runSearch = async () => {
    if (search.trim().length < 2) { setMessage('Enter at least two characters to search the product catalog.'); return; }
    setMessage(''); setCategory('All'); setFallback(null);
    const query = search.trim();
    const typedBarcode = isUsableBarcode(query) ? query : '';
    try {
      const found = await searchCatalog(search);
      setFallback(labelFallbackOffer({ barcode: typedBarcode, query, resultCount: found.length }));
    }
    catch (cause) {
      const offer = labelFallbackOffer({ barcode: typedBarcode, query, error: cause });
      setFallback(offer);
      if (!offer) setMessage(cause instanceof Error ? cause.message : 'Product search failed.');
    }
  };
  const startManual = (code = '') => {
    setFallback(null); setLabelPhoto(null);
    setProduct({ ...product, id: `manual-${Date.now()}`, brand: 'Your label', name: 'New product', barcode: code, ingredients: '', advisory: '', sodium: null, basis: 'Not supplied', observation: undefined });
    router.push('/review');
  };
  const verifyFssai = async () => {
    const number = fssaiNumber.replace(/\s/g, '');
    if (!/^\d{14}$/.test(number)) { setFssaiError('Enter the 14-digit FSSAI license number printed on the package.'); setFssaiResult(null); return; }
    if (!token) { setFssaiError('Sign in before verifying a license.'); return; }
    setFssaiBusy(true); setFssaiError(''); setFssaiResult(null);
    try { setFssaiResult(await api.verifyFssai(token, number)); }
    catch (cause) { setFssaiError(cause instanceof Error ? cause.message : 'FSSAI verification failed.'); }
    finally { setFssaiBusy(false); }
  };
  const openCamera = async () => {
    scanned.current = false;
    if (Platform.OS === 'web') {
      setMessage('Use barcode entry or product search in the browser. Camera scanning is available in the native app.');
      return;
    }
    if (permission?.granted) { setCameraVisible(true); return; }
    const result = await requestPermission();
    if (result.granted) setCameraVisible(true);
    else setMessage('Camera access is needed to scan. You can still enter the barcode or search the sample catalog.');
  };
  const onBarcode = ({ data }: { data: string }) => {
    if (scanned.current) return;
    scanned.current = true;
    setCameraVisible(false);
    setBarcode(data);
    void lookup(data);
  };
  const addLabelPhoto = async () => {
    // The barcode from the failed lookup travels with the photo, or, when the entered
    // barcode cannot be attached, the message says so rather than dropping it silently.
    const typed = barcode.trim();
    const attached = isUsableBarcode(typed) ? typed : fallback?.barcode ?? null;
    const unusable = attached || !typed ? null : typed;
    try {
      const result = Platform.OS === 'web'
        ? await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.85 })
        : await ImagePicker.launchCameraAsync({ mediaTypes: ['images'], quality: 0.85 });
      if (result.canceled || !result.assets[0]) return;
      setMessage('Reading the label…');
      const outcome = await extractLabel(
        { uri: result.assets[0].uri, name: result.assets[0].fileName, mimeType: result.assets[0].mimeType },
        { barcode: attached, name: search.trim() || null },
      );
      setMessage(labelExtractionMessage(outcome, attached, unusable));
      setFallback(null);
      router.push('/review');
    } catch {
      setMessage('Label extraction failed. You can enter the package details manually.');
    }
  };

  return <Screen>
    <PageHeader title="Scan or search" subtitle="Find a packaged food, then review its label information before an assessment." />
    <Button title="Check a cooked meal" icon="silverware-fork-knife" secondary onPress={() => router.push('/dish')} />
    <Card style={st.scanCard}>
      <View style={st.scanGraphic}><View style={st.scanFrame}><MaterialCommunityIcons name="barcode-scan" size={33} color={colors.primary} /></View><View style={st.scanText}><Text style={st.cardTitle}>Scan a barcode</Text><Text style={st.cardSub}>Look up a product in the available catalog.</Text></View></View>
      {cameraVisible ? <View style={st.cameraShell}><CameraView style={st.camera} facing="back" barcodeScannerSettings={{ barcodeTypes: ['ean13', 'ean8', 'upc_a', 'upc_e'] }} onBarcodeScanned={onBarcode} /><View pointerEvents="none" style={st.scanOverlay}><View style={st.scanCorners} /></View><Pressable onPress={() => setCameraVisible(false)} style={st.cameraClose}><MaterialCommunityIcons name="close" color={colors.onPrimary} size={20} /></Pressable><Text style={st.cameraHint}>Line up the barcode inside the frame</Text></View> : <Pressable onPress={openCamera} style={st.cameraButton}><MaterialCommunityIcons name="camera-outline" size={17} color={colors.primary} /><Text style={st.cameraButtonText}>{Platform.OS === 'web' ? 'Use a phone to scan' : 'Open camera scanner'}</Text></Pressable>}
      <View style={st.inputWrap}><MaterialCommunityIcons name="barcode" size={20} color={colors.subtle} /><TextInput accessibilityLabel="Barcode number" value={barcode} onChangeText={setBarcode} keyboardType="numeric" placeholder="Enter barcode number" placeholderTextColor={colors.subtle} style={st.input} onSubmitEditing={() => void lookup()} returnKeyType="search" /><Pressable accessibilityRole="button" accessibilityLabel="Look up barcode" disabled={busy} onPress={() => void lookup()} style={st.searchAction}><MaterialCommunityIcons name={busy ? 'progress-clock' : 'arrow-right'} color={colors.onPrimary} size={20} /></Pressable></View>
      <Pressable onPress={addLabelPhoto} style={st.photoButton}><MaterialCommunityIcons name="camera-plus-outline" size={17} color={colors.primary} /><Text style={st.cameraButtonText}>{Platform.OS === 'web' ? 'Choose a label photo' : 'Take a label photo'}</Text></Pressable>
      {message ? <View style={st.message}><MaterialCommunityIcons name="information-outline" size={16} color={colors.amber} /><Text style={st.messageText}>{message}</Text></View> : null}
    </Card>
    {fallback ? <Card style={st.fallbackCard}>
      <View style={st.fallbackHead}><MaterialCommunityIcons name="barcode-off" size={20} color={colors.amberInk} /><View style={{ flex: 1 }}><Text style={st.fallbackTitle}>{fallback.title}</Text><Text style={st.fallbackText}>{fallback.detail}</Text></View></View>
      <Button title={Platform.OS === 'web' ? 'Choose a photo' : 'Take a label photo'} icon="camera-plus-outline" onPress={() => void addLabelPhoto()} />
      <Button title="Enter label details manually" icon="text-box-outline" secondary onPress={() => startManual(fallback.barcode ?? '')} />
      <Text style={st.fallbackNote}>The extracted list is an unchecked draft. You correct every field on the next screen before assessing it.</Text>
    </Card> : null}
    <Card style={st.fssaiCard}>
      <View><Text style={st.cardTitle}>Verify an FSSAI license</Text><Text style={st.cardSub}>Check the license number printed on a food package.</Text></View>
      <Field label="FSSAI license number" value={fssaiNumber} onChangeText={value => { setFssaiNumber(value.replace(/[^0-9]/g, '').slice(0, 14)); setFssaiError(''); }} placeholder="14 digits" keyboardType="numeric" onSubmitEditing={() => void verifyFssai()} returnKeyType="done" />
      <Button title="Verify license" icon="shield-check-outline" loading={fssaiBusy} disabled={fssaiBusy} onPress={() => void verifyFssai()} />
      {fssaiError ? <View style={st.message}><MaterialCommunityIcons name="alert-circle-outline" size={16} color={colors.amber} /><Text accessibilityRole="alert" style={st.messageText}>{fssaiError}</Text></View> : null}
      {fssaiResult ? <View style={st.fssaiResult}>
        <Pill label={fssaiResult.success ? (fssaiResult.verification_data?.license_active_flag === true ? 'LICENSE ACTIVE' : fssaiResult.verification_data?.license_active_flag === false ? 'LICENSE INACTIVE' : 'LOOKUP COMPLETE') : 'NOT VERIFIED'} tone={fssaiResult.success ? (fssaiResult.verification_data?.license_active_flag === false ? 'red' : 'green') : 'amber'} />
        {fssaiResult.verification_data?.company_name ? <Text style={st.cardTitle}>{fssaiResult.verification_data.company_name}</Text> : null}
        {fssaiResult.verification_data?.status_desc ? <Text style={st.cardSub}>{fssaiResult.verification_data.status_desc}</Text> : null}
        {fssaiResult.verification_data?.license_category_name ? <Text style={st.resultDetail}>License category: {fssaiResult.verification_data.license_category_name}</Text> : null}
        {fssaiResult.verification_data?.address ? <Text style={st.resultDetail}>{fssaiResult.verification_data.address}</Text> : null}
        <Text style={st.resultNote}>A license lookup does not confirm that this package or food is genuine or safe. Check the printed details against the current package.</Text>
      </View> : null}
    </Card>
    <View style={st.orRow}><View style={st.rule} /><Text style={st.orText}>OR SEARCH THE PRODUCT CATALOG</Text><View style={st.rule} /></View>
    <View style={st.searchBox}><MaterialCommunityIcons name="magnify" size={21} color={colors.subtle} /><TextInput accessibilityLabel="Search product name or brand" value={search} onChangeText={setSearch} onSubmitEditing={() => void runSearch()} returnKeyType="search" placeholder="Search product name or brand" placeholderTextColor={colors.subtle} style={st.searchInput} /><Pressable accessibilityRole="button" accessibilityLabel="Search product catalog" onPress={() => void runSearch()}><MaterialCommunityIcons name="arrow-right-circle" size={25} color={colors.primary} /></Pressable></View>
    <View style={st.categoryRow}>{categories.map(item => <Pressable key={item} accessibilityRole="button" accessibilityState={{ selected: category === item }} accessibilityLabel={`Filter by ${item}`} onPress={() => setCategory(item)} style={[st.category, category === item && st.categoryActive]}><Text style={[st.categoryText, category === item && st.categoryTextActive]}>{item.replaceAll('_', ' ')}</Text></Pressable>)}</View>
    <SectionTitle title="Product catalogue" action="Browse saved" onAction={() => { setSearch(''); setCategory('All'); void loadCatalog().catch(() => undefined); }} />
    {catalogMessage ? <Text style={st.cardSub}>{catalogMessage}</Text> : null}
    <View style={{ gap: 10 }}>{visible.length ? visible.map(item => <ProductRow key={item.id} item={item} onPress={() => select(item)} />) : <Card style={{ alignItems: 'center', gap: 7 }}><MaterialCommunityIcons name="food-off-outline" size={30} color={colors.subtle} /><Text style={st.cardTitle}>{busy ? 'Searching…' : 'No saved results yet'}</Text><Text style={st.cardSub}>Search by name or scan a barcode to query Open Food Facts.</Text></Card>}</View>
    <Button title="Enter label details manually" icon="text-box-outline" secondary onPress={() => startManual(isUsableBarcode(barcode) ? barcode.trim() : '')} />
  </Screen>;
}

function ProductRow({ item, onPress }: { item: Product; onPress: () => void }) {
  return <Pressable accessibilityRole="button" accessibilityLabel={`Review ${item.brand} ${item.name}`} onPress={onPress} style={({ pressed }) => pressed && st.pressed}><Card style={st.productRow}><View style={[st.productIcon, { backgroundColor: item.color }]}><Text style={{ fontSize: 24 }}>{item.icon}</Text></View><View style={{ flex: 1 }}><Text style={st.brand}>{item.brand}</Text><Text style={st.cardTitle}>{item.name}</Text><Text style={st.cardSub}>{item.category.replaceAll('_', ' ')}</Text><View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 8 }}><Pill label={item.observation?.ingredients_text ? 'Ingredients recorded' : 'Ingredients missing'} tone={item.observation?.ingredients_text ? 'blue' : 'amber'} /><Pill label={`${Object.values(item.observation?.nutrients || {}).filter(value => value != null).length}/10 nutrients`} tone="neutral" /></View><Text style={st.cardSub}>{item.observation?.source.kind.replaceAll('_', ' ')} · Confirm the label</Text></View><MaterialCommunityIcons name="arrow-top-right" size={19} color={colors.primary} /></Card></Pressable>;
}
const st = StyleSheet.create({
  scanCard: { gap: 16, padding: 18 },
  scanGraphic: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  scanFrame: { width: 52, height: 52, borderRadius: radius.tile, backgroundColor: colors.lavender, alignItems: 'center', justifyContent: 'center' },
  scanText: { flex: 1 },
  cardTitle: { ...typography.cardTitle, color: colors.ink },
  cardSub: { ...typography.meta, color: colors.muted, marginTop: 4 },
  cameraButton: { minHeight: 48, borderRadius: radius.control, backgroundColor: colors.lavender, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 7 },
  photoButton: { minHeight: 48, borderRadius: radius.control, backgroundColor: colors.lavenderTint, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 7 },
  cameraButtonText: { color: colors.primary, ...typography.action },
  cameraShell: { height: 240, borderRadius: radius.card, overflow: 'hidden', backgroundColor: colors.camera, position: 'relative', alignItems: 'center', justifyContent: 'center' },
  camera: { ...StyleSheet.absoluteFill },
  scanOverlay: { ...StyleSheet.absoluteFill, alignItems: 'center', justifyContent: 'center' },
  scanCorners: { width: 240, height: 110, borderWidth: 2, borderColor: '#FFFFFF', borderRadius: radius.control, backgroundColor: 'transparent' },
  cameraClose: { position: 'absolute', right: 10, top: 10, width: 44, height: 44, borderRadius: radius.control, backgroundColor: 'rgba(20,18,40,.65)', alignItems: 'center', justifyContent: 'center' },
  cameraHint: { position: 'absolute', bottom: 12, color: '#FFFFFF', backgroundColor: 'rgba(20,18,40,.6)', paddingHorizontal: 12, paddingVertical: 7, overflow: 'hidden', borderRadius: radius.pill, ...typography.meta, fontWeight: '700' },
  inputWrap: { flexDirection: 'row', alignItems: 'center', gap: 10, borderWidth: 1, borderColor: colors.stroke, backgroundColor: colors.surface, borderRadius: radius.control, minHeight: 54, paddingHorizontal: 12 },
  input: { flex: 1, color: colors.ink, fontSize: 16 },
  searchAction: { width: 44, height: 44, borderRadius: radius.control, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center' },
  message: { flexDirection: 'row', gap: 8, backgroundColor: colors.amberBg, borderRadius: radius.chip, padding: 12 },
  messageText: { color: colors.amberInk, flex: 1, ...typography.meta },
  fallbackCard: { gap: 12, backgroundColor: colors.amberBg },
  fallbackHead: { flexDirection: 'row', alignItems: 'flex-start', gap: 9 },
  fallbackTitle: { color: colors.amberInk, fontSize: 14, lineHeight: 20, fontWeight: '800' },
  fallbackText: { color: colors.amberInk, ...typography.meta, marginTop: 4 },
  fallbackNote: { ...typography.caption, color: colors.amberInk },
  orRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  rule: { height: 1, backgroundColor: colors.rule, flex: 1 },
  orText: { fontSize: 11, lineHeight: 15, fontWeight: '800', letterSpacing: 1, color: colors.subtle },
  searchBox: { flexDirection: 'row', alignItems: 'center', gap: 9, minHeight: 54, borderRadius: radius.control, backgroundColor: colors.surface, paddingHorizontal: 14, borderWidth: 1, borderColor: colors.stroke },
  searchInput: { color: colors.ink, flex: 1, fontSize: 16 },
  categoryRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  category: { paddingHorizontal: 14, paddingVertical: 12, borderRadius: radius.pill, backgroundColor: colors.chip },
  categoryActive: { backgroundColor: colors.primary },
  categoryText: { ...typography.meta, fontWeight: '700', color: colors.muted },
  categoryTextActive: { color: colors.onPrimary },
  productRow: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14 },
  productIcon: { width: 50, height: 50, borderRadius: radius.avatar, alignItems: 'center', justifyContent: 'center' },
  brand: { color: colors.muted, fontSize: 12, lineHeight: 16, fontWeight: '800', letterSpacing: .5, marginBottom: 3 },
  pressed: { opacity: 0.9 },
  fssaiCard: { gap: 14 },
  fssaiResult: { gap: 7, borderTopWidth: 1, borderTopColor: colors.line, paddingTop: 13 },
  resultDetail: { ...typography.meta, color: colors.ink },
  resultNote: { ...typography.caption, color: colors.muted, marginTop: 3 },
});
