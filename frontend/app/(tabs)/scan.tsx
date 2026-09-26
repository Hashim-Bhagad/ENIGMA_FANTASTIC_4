import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { router } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import { Button, Card, PageHeader, Pill, Screen, SectionTitle } from '@/src/components/ui';
import { type Product } from '@/src/api/client';
import { useApp } from '@/src/state/AppContext';
import { colors, radius } from '@/src/theme';

export default function ScanScreen() {
  const { product, products, setProduct, search, setSearch, setLabelPhoto, lookupBarcode, searchCatalog, extractLabel, busyFor, token, catalogMessage, loadCatalog } = useApp();
  const [barcode, setBarcode] = useState('');
  const [message, setMessage] = useState('');
  const [category, setCategory] = useState('All');
  const [cameraVisible, setCameraVisible] = useState(false);
  const [permission, requestPermission] = useCameraPermissions();
  const scanned = useRef(false);
  const busy = busyFor('search') || busyFor('barcode') || busyFor('label');
  useEffect(() => { if (token && !products.length) void loadCatalog().catch(() => undefined); }, [token, loadCatalog]);
  const categories = ['All', ...new Set(products.map(item => item.category))];
  const visible = useMemo(() => products.filter(item => category === 'All' || item.category === category), [products, category]);

  const select = (item: Product) => { setProduct(item); setLabelPhoto(null); setSearch(''); setMessage(''); router.push('/review'); };
  const lookup = async (value = barcode) => {
    if (!value.trim()) { setMessage('Enter the barcode printed on the product.'); return; }
    try { select(await lookupBarcode(value)); }
    catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Product lookup failed.'); }
  };
  const runSearch = async () => {
    if (search.trim().length < 2) { setMessage('Enter at least two characters to search the product catalog.'); return; }
    setMessage(''); setCategory('All');
    try { await searchCatalog(search); }
    catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Product search failed.'); }
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
    try {
      const result = Platform.OS === 'web'
        ? await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.85 })
        : await ImagePicker.launchCameraAsync({ mediaTypes: ['images'], quality: 0.85 });
      if (result.canceled || !result.assets[0]) return;
      setMessage('Reading the label…');
      await extractLabel({ uri: result.assets[0].uri, name: result.assets[0].fileName, mimeType: result.assets[0].mimeType });
      setMessage('Review every extracted field against the package before assessing.');
      router.push('/review');
    } catch {
      setMessage('Label extraction failed. You can enter the package details manually.');
    }
  };

  return <Screen>
    <PageHeader eyebrow="Food check" title="Scan or search" subtitle="Find a packaged food, then review its label information before an assessment." />
    <Button title="Check a cooked meal" icon="silverware-fork-knife" secondary onPress={() => router.push('/dish')} />
    <Card style={st.scanCard}>
      <View style={st.scanGraphic}><View style={st.scanFrame}><MaterialCommunityIcons name="barcode-scan" size={33} color={colors.primary} /></View><View style={st.scanText}><Text style={st.cardTitle}>Scan a barcode</Text><Text style={st.cardSub}>Look up a product in the available catalog.</Text></View></View>
      {cameraVisible ? <View style={st.cameraShell}><CameraView style={st.camera} facing="back" barcodeScannerSettings={{ barcodeTypes: ['ean13', 'ean8', 'upc_a', 'upc_e'] }} onBarcodeScanned={onBarcode} /><View pointerEvents="none" style={st.scanOverlay}><View style={st.scanCorners} /></View><Pressable onPress={() => setCameraVisible(false)} style={st.cameraClose}><MaterialCommunityIcons name="close" color={colors.onPrimary} size={20} /></Pressable><Text style={st.cameraHint}>Line up the barcode inside the frame</Text></View> : <Pressable onPress={openCamera} style={st.cameraButton}><MaterialCommunityIcons name="camera-outline" size={17} color={colors.primary} /><Text style={st.cameraButtonText}>{Platform.OS === 'web' ? 'Use a phone to scan' : 'Open camera scanner'}</Text></Pressable>}
      <View style={st.inputWrap}><MaterialCommunityIcons name="barcode" size={20} color={colors.subtle} /><TextInput value={barcode} onChangeText={setBarcode} keyboardType="numeric" placeholder="Enter barcode number" placeholderTextColor={colors.subtle} style={st.input} onSubmitEditing={() => void lookup()} returnKeyType="search" /><Pressable accessibilityRole="button" accessibilityLabel="Look up barcode" disabled={busy} onPress={() => void lookup()} style={st.searchAction}><MaterialCommunityIcons name={busy ? 'progress-clock' : 'arrow-right'} color={colors.onPrimary} size={20} /></Pressable></View>
      <Pressable onPress={addLabelPhoto} style={st.photoButton}><MaterialCommunityIcons name="camera-plus-outline" size={17} color={colors.primary} /><Text style={st.cameraButtonText}>{Platform.OS === 'web' ? 'Choose a label photo' : 'Take a label photo'}</Text></Pressable>
      {message ? <View style={st.message}><MaterialCommunityIcons name="information-outline" size={16} color={colors.amber} /><Text style={st.messageText}>{message}</Text></View> : null}
    </Card>
    <View style={st.orRow}><View style={st.rule} /><Text style={st.orText}>OR SEARCH THE PRODUCT CATALOG</Text><View style={st.rule} /></View>
    <View style={st.searchBox}><MaterialCommunityIcons name="magnify" size={21} color={colors.subtle} /><TextInput value={search} onChangeText={setSearch} onSubmitEditing={() => void runSearch()} returnKeyType="search" placeholder="Search product name or brand" placeholderTextColor={colors.subtle} style={st.searchInput} /><Pressable accessibilityRole="button" accessibilityLabel="Search product catalog" onPress={() => void runSearch()}><MaterialCommunityIcons name="arrow-right-circle" size={25} color={colors.primary} /></Pressable></View>
    <View style={st.categoryRow}>{categories.map(item => <Pressable key={item} accessibilityRole="button" accessibilityState={{ selected: category === item }} accessibilityLabel={`Filter by ${item}`} onPress={() => setCategory(item)} style={[st.category, category === item && st.categoryActive]}><Text style={[st.categoryText, category === item && st.categoryTextActive]}>{item.replaceAll('_', ' ')}</Text></Pressable>)}</View>
    <SectionTitle title="Product catalogue" action="Browse saved" onAction={() => { setSearch(''); setCategory('All'); void loadCatalog().catch(() => undefined); }} />
    {catalogMessage ? <Text style={st.cardSub}>{catalogMessage}</Text> : null}
    <View style={{ gap: 10 }}>{visible.length ? visible.map(item => <ProductRow key={item.id} item={item} onPress={() => select(item)} />) : <Card style={{ alignItems: 'center', gap: 7 }}><MaterialCommunityIcons name="food-off-outline" size={30} color={colors.subtle} /><Text style={st.cardTitle}>{busy ? 'Searching…' : 'No saved results yet'}</Text><Text style={st.cardSub}>Search by name or scan a barcode to query Open Food Facts.</Text></Card>}</View>
    <Button title="Enter label details manually" icon="text-box-outline" secondary onPress={() => { setLabelPhoto(null); setProduct({ ...product, id: `manual-${Date.now()}`, brand: 'Your label', name: 'New product', barcode: '', ingredients: '', advisory: '', sodium: null, basis: 'Not supplied', observation: undefined }); router.push('/review'); }} />
  </Screen>;
}

function ProductRow({ item, onPress }: { item: Product; onPress: () => void }) {
  return <Pressable accessibilityRole="button" accessibilityLabel={`Review ${item.brand} ${item.name}`} onPress={onPress}><Card style={st.productRow}><View style={[st.productIcon, { backgroundColor: item.color }]}><Text style={{ fontSize: 24 }}>{item.icon}</Text></View><View style={{ flex: 1 }}><Text style={st.brand}>{item.brand}</Text><Text style={st.cardTitle}>{item.name}</Text><Text style={st.cardSub}>{item.category.replaceAll('_', ' ')}</Text><View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 8 }}><Pill label={item.observation?.ingredients_text ? 'Ingredients recorded' : 'Ingredients missing'} tone={item.observation?.ingredients_text ? 'blue' : 'amber'} /><Pill label={`${Object.values(item.observation?.nutrients || {}).filter(value => value != null).length}/10 nutrients`} tone="neutral" /></View><Text style={st.cardSub}>{item.observation?.source.kind.replaceAll('_', ' ')} · Confirm the label</Text></View><MaterialCommunityIcons name="arrow-top-right" size={19} color={colors.primary} /></Card></Pressable>;
}
const st = StyleSheet.create({
  scanCard: { gap: 15, padding: 16 }, scanGraphic: { flexDirection: 'row', alignItems: 'center', gap: 12 }, scanFrame: { width: 51, height: 51, borderRadius: 17, backgroundColor: colors.lavender, alignItems: 'center', justifyContent: 'center' }, scanText: { flex: 1 }, cardTitle: { color: colors.ink, fontSize: 16, lineHeight: 23, fontWeight: '700' }, cardSub: { color: colors.muted, fontSize: 14, lineHeight: 21, marginTop: 4 }, cameraButton: { minHeight: 42, borderRadius: 13, backgroundColor: colors.lavender, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 7 }, photoButton: { minHeight: 42, borderRadius: 13, backgroundColor: colors.lavenderTint, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 7 }, cameraButtonText: { color: colors.primary, fontSize: 14, fontWeight: '800' }, cameraShell: { height: 220, borderRadius: 17, overflow: 'hidden', backgroundColor: colors.camera, position: 'relative', alignItems: 'center', justifyContent: 'center' }, camera: { ...StyleSheet.absoluteFill }, scanOverlay: { ...StyleSheet.absoluteFill, alignItems: 'center', justifyContent: 'center' }, scanCorners: { width: 220, height: 100, borderWidth: 2, borderColor: '#FFFFFF', borderRadius: 14, backgroundColor: 'transparent' }, cameraClose: { position: 'absolute', right: 10, top: 10, width: 44, height: 44, borderRadius: 12, backgroundColor: 'rgba(20,18,40,.65)', alignItems: 'center', justifyContent: 'center' }, cameraHint: { position: 'absolute', bottom: 12, color: '#FFFFFF', backgroundColor: 'rgba(20,18,40,.6)', paddingHorizontal: 10, paddingVertical: 6, overflow: 'hidden', borderRadius: 999, fontSize: 13, fontWeight: '700' }, inputWrap: { flexDirection: 'row', alignItems: 'center', gap: 10, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.canvas, borderRadius: 16, minHeight: 53, paddingHorizontal: 12 }, input: { flex: 1, color: colors.ink, fontSize: 13 }, searchAction: { width: 44, height: 44, borderRadius: 12, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center' }, message: { flexDirection: 'row', gap: 7, backgroundColor: colors.amberBg, borderRadius: 12, padding: 10 }, messageText: { color: colors.amberInk, flex: 1, fontSize: 11, lineHeight: 15 },
  orRow: { flexDirection: 'row', alignItems: 'center', gap: 10 }, rule: { height: 1, backgroundColor: colors.rule, flex: 1 }, orText: { fontSize: 9, fontWeight: '800', letterSpacing: 1, color: colors.subtle }, searchBox: { flexDirection: 'row', alignItems: 'center', gap: 9, minHeight: 50, borderRadius: 16, backgroundColor: colors.surface, paddingHorizontal: 13, borderWidth: 1, borderColor: colors.line }, searchInput: { color: colors.ink, flex: 1, fontSize: 13 },
  categoryRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 7 }, category: { paddingHorizontal: 12, paddingVertical: 12, borderRadius: radius.pill, backgroundColor: colors.chip }, categoryActive: { backgroundColor: colors.primary }, categoryText: { fontSize: 13, fontWeight: '700', color: colors.muted }, categoryTextActive: { color: colors.onPrimary }, productRow: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 13 }, productIcon: { width: 49, height: 49, borderRadius: radius.avatar, alignItems: 'center', justifyContent: 'center' }, brand: { color: colors.muted, fontSize: 12, fontWeight: '700', letterSpacing: .5, marginBottom: 3 },
});
