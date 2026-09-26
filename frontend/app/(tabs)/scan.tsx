import React, { useMemo, useState } from 'react';
import { Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { router } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import { Button, Card, DemoBanner, PageHeader, Pill, Screen, SectionTitle } from '@/src/components/ui';
import { Product } from '@/src/data/demo';
import { useApp } from '@/src/state/AppContext';
import { colors } from '@/src/theme';

export default function ScanScreen() {
  const { products, setProduct, search, setSearch, setLabelPhoto } = useApp();
  const [barcode, setBarcode] = useState('');
  const [message, setMessage] = useState('');
  const [category, setCategory] = useState('All');
  const [cameraVisible, setCameraVisible] = useState(false);
  const [permission, requestPermission] = useCameraPermissions();
  const categories = ['All', 'Biscuits & crackers', 'Breakfast cereals', 'Savory snacks'];
  const visible = useMemo(() => products.filter(item => {
    const matchesSearch = `${item.brand} ${item.name} ${item.category} ${item.barcode}`.toLowerCase().includes(search.toLowerCase());
    const matchesCategory = category === 'All' || item.category.toLowerCase().includes(category.toLowerCase().replace('savory snacks', 'savory'));
    return matchesSearch && matchesCategory;
  }), [products, search, category]);

  const select = (product: Product) => { setProduct(product); setLabelPhoto(null); setSearch(''); setMessage(''); router.push('/review'); };
  const lookup = () => {
    const match = products.find(item => item.barcode === barcode.trim());
    if (match) select(match);
    else setMessage(barcode.trim() ? 'No matching demo record. You can still find a product below or enter its label details manually.' : 'Enter a barcode to look for a matching demo record.');
  };
  const openCamera = async () => {
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
    setCameraVisible(false);
    setBarcode(data);
    const match = products.find(item => item.barcode === data);
    if (match) select(match);
    else setMessage(`Barcode ${data} is not in this demo catalog. Search for the item or enter label details manually.`);
  };
  const addLabelPhoto = async () => {
    try {
      const result = Platform.OS === 'web'
        ? await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.85 })
        : await ImagePicker.launchCameraAsync({ mediaTypes: ['images'], quality: 0.85 });
      if (result.canceled || !result.assets[0]) return;
      setLabelPhoto(result.assets[0].uri);
      setProduct({ ...products[0], id: 'photo-entry', brand: 'Your label', name: 'New product', barcode: '', ingredients: '', advisory: '', sodium: null, basis: 'Not supplied', findings: [], sample: false });
      router.push('/review');
    } catch {
      setMessage('The photo could not be opened. You can enter the label details below instead.');
    }
  };

  return <Screen>
    <PageHeader eyebrow="Food check" title="Scan or search" subtitle="Find a packaged food, then review its label information before an assessment." />
    <DemoBanner />
    <Card style={st.scanCard}>
      <View style={st.scanGraphic}><View style={st.scanFrame}><MaterialCommunityIcons name="barcode-scan" size={33} color={colors.primary} /></View><View style={st.scanText}><Text style={st.cardTitle}>Scan a barcode</Text><Text style={st.cardSub}>Look up a product in the available catalog.</Text></View></View>
      {cameraVisible ? <View style={st.cameraShell}><CameraView style={st.camera} facing="back" barcodeScannerSettings={{ barcodeTypes: ['ean13', 'ean8', 'upc_a', 'upc_e', 'code128', 'qr'] }} onBarcodeScanned={onBarcode} /><View pointerEvents="none" style={st.scanOverlay}><View style={st.scanCorners} /></View><Pressable onPress={() => setCameraVisible(false)} style={st.cameraClose}><MaterialCommunityIcons name="close" color="#FFFFFF" size={20} /></Pressable><Text style={st.cameraHint}>Line up the barcode inside the frame</Text></View> : <Pressable onPress={openCamera} style={st.cameraButton}><MaterialCommunityIcons name="camera-outline" size={17} color={colors.primary} /><Text style={st.cameraButtonText}>{Platform.OS === 'web' ? 'Use a phone to scan' : 'Open camera scanner'}</Text></Pressable>}
      <View style={st.inputWrap}><MaterialCommunityIcons name="barcode" size={20} color={colors.subtle} /><TextInput value={barcode} onChangeText={setBarcode} keyboardType="numeric" placeholder="Enter barcode number" placeholderTextColor={colors.subtle} style={st.input} onSubmitEditing={lookup} returnKeyType="search" /><Pressable onPress={lookup} style={st.searchAction}><MaterialCommunityIcons name="arrow-right" color="#FFFFFF" size={20} /></Pressable></View>
      <Pressable onPress={addLabelPhoto} style={st.photoButton}><MaterialCommunityIcons name="camera-plus-outline" size={17} color={colors.primary} /><Text style={st.cameraButtonText}>{Platform.OS === 'web' ? 'Choose a label photo' : 'Take a label photo'}</Text></Pressable>
      {message ? <View style={st.message}><MaterialCommunityIcons name="information-outline" size={16} color={colors.amber} /><Text style={st.messageText}>{message}</Text></View> : null}
    </Card>
    <View style={st.orRow}><View style={st.rule} /><Text style={st.orText}>OR SEARCH DEMO CATALOG</Text><View style={st.rule} /></View>
    <View style={st.searchBox}><MaterialCommunityIcons name="magnify" size={21} color={colors.subtle} /><TextInput value={search} onChangeText={setSearch} placeholder="Search products or categories" placeholderTextColor={colors.subtle} style={st.searchInput} /></View>
    <View style={st.categoryRow}>{categories.map(item => <Pressable key={item} onPress={() => setCategory(item)} style={[st.category, category === item && st.categoryActive]}><Text style={[st.categoryText, category === item && st.categoryTextActive]}>{item}</Text></Pressable>)}</View>
    <SectionTitle title="Products to explore" action={`${visible.length} examples`} />
    <View style={{ gap: 10 }}>{visible.length ? visible.map(item => <ProductRow key={item.id} item={item} onPress={() => select(item)} />) : <Card style={{ alignItems: 'center', gap: 7 }}><MaterialCommunityIcons name="food-off-outline" size={30} color={colors.subtle} /><Text style={st.cardTitle}>No demo match</Text><Text style={st.cardSub}>Try a different name or category.</Text></Card>}</View>
    <Button title="Enter label details manually" icon="text-box-edit-outline" secondary onPress={() => { setLabelPhoto(null); setProduct({ ...products[0], id: 'manual-entry', brand: 'Your label', name: 'New product', barcode: '', ingredients: '', advisory: '', sodium: null, basis: 'Not supplied', findings: [], sample: false }); router.push('/review'); }} />
    <Pressable onPress={() => router.push('/dish')} style={st.dishRow}><View style={st.dishIcon}><MaterialCommunityIcons name="silverware-fork-knife" size={20} color={colors.primary} /></View><View style={{ flex: 1 }}><Text style={st.cardTitle}>Checking a prepared dish?</Text><Text style={st.cardSub}>Get questions to ask about ingredients and preparation.</Text></View><MaterialCommunityIcons name="chevron-right" size={20} color={colors.subtle} /></Pressable>
  </Screen>;
}

function ProductRow({ item, onPress }: { item: Product; onPress: () => void }) {
  return <Pressable onPress={onPress}><Card style={st.productRow}><View style={[st.productIcon, { backgroundColor: item.color }]}><Text style={{ fontSize: 24 }}>{item.icon}</Text></View><View style={{ flex: 1 }}><Text style={st.brand}>{item.brand}</Text><Text style={st.cardTitle}>{item.name}</Text><Text style={st.cardSub}>{item.category}</Text></View><MaterialCommunityIcons name="arrow-top-right" size={19} color={colors.primary} /></Card></Pressable>;
}
const st = StyleSheet.create({
  scanCard: { gap: 15, padding: 16 }, scanGraphic: { flexDirection: 'row', alignItems: 'center', gap: 12 }, scanFrame: { width: 51, height: 51, borderRadius: 17, backgroundColor: colors.lavender, alignItems: 'center', justifyContent: 'center' }, scanText: { flex: 1 }, cardTitle: { color: colors.ink, fontSize: 13, fontWeight: '700' }, cardSub: { color: colors.muted, fontSize: 11, lineHeight: 16, marginTop: 4 }, cameraButton: { minHeight: 42, borderRadius: 13, backgroundColor: colors.lavender, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 7 }, photoButton: { minHeight: 42, borderRadius: 13, backgroundColor: '#F4F2FE', flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 7 }, cameraButtonText: { color: colors.primary, fontSize: 11, fontWeight: '800' }, cameraShell: { height: 220, borderRadius: 17, overflow: 'hidden', backgroundColor: '#171525', position: 'relative', alignItems: 'center', justifyContent: 'center' }, camera: { ...StyleSheet.absoluteFillObject }, scanOverlay: { ...StyleSheet.absoluteFillObject, alignItems: 'center', justifyContent: 'center' }, scanCorners: { width: 220, height: 100, borderWidth: 2, borderColor: '#FFFFFF', borderRadius: 14, backgroundColor: 'transparent' }, cameraClose: { position: 'absolute', right: 10, top: 10, width: 34, height: 34, borderRadius: 12, backgroundColor: 'rgba(20,18,40,.65)', alignItems: 'center', justifyContent: 'center' }, cameraHint: { position: 'absolute', bottom: 12, color: '#FFFFFF', backgroundColor: 'rgba(20,18,40,.6)', paddingHorizontal: 10, paddingVertical: 6, overflow: 'hidden', borderRadius: 999, fontSize: 10, fontWeight: '700' }, inputWrap: { flexDirection: 'row', alignItems: 'center', gap: 10, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.canvas, borderRadius: 16, minHeight: 53, paddingHorizontal: 12 }, input: { flex: 1, color: colors.ink, fontSize: 13 }, searchAction: { width: 34, height: 34, borderRadius: 12, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center' }, message: { flexDirection: 'row', gap: 7, backgroundColor: colors.amberBg, borderRadius: 12, padding: 10 }, messageText: { color: '#785015', flex: 1, fontSize: 11, lineHeight: 15 },
  orRow: { flexDirection: 'row', alignItems: 'center', gap: 10 }, rule: { height: 1, backgroundColor: '#E7E5ED', flex: 1 }, orText: { fontSize: 9, fontWeight: '800', letterSpacing: 1, color: colors.subtle }, searchBox: { flexDirection: 'row', alignItems: 'center', gap: 9, minHeight: 50, borderRadius: 16, backgroundColor: colors.surface, paddingHorizontal: 13, borderWidth: 1, borderColor: colors.line }, searchInput: { color: colors.ink, flex: 1, fontSize: 13 },
  categoryRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 7 }, category: { paddingHorizontal: 12, paddingVertical: 9, borderRadius: 999, backgroundColor: '#ECEBF1' }, categoryActive: { backgroundColor: colors.primary }, categoryText: { fontSize: 10, fontWeight: '700', color: colors.muted }, categoryTextActive: { color: '#FFFFFF' }, productRow: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 13 }, productIcon: { width: 49, height: 49, borderRadius: 17, alignItems: 'center', justifyContent: 'center' }, brand: { color: colors.muted, fontSize: 9, fontWeight: '700', letterSpacing: .5, marginBottom: 3 }, dishRow: { flexDirection: 'row', alignItems: 'center', gap: 11, backgroundColor: '#F0EDFF', padding: 14, borderRadius: 19 }, dishIcon: { width: 42, height: 42, borderRadius: 14, backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center' },
});
