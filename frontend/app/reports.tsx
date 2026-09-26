import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { router } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import { Button, Card, PageHeader, Pill, Screen, SectionTitle } from '@/src/components/ui';
import { api, formatReferenceRange, HealthReportResult, LabParameter, parameterStatusTone, ReportConfirm, ReportFile, ReferenceSource, HealthReportSummary } from '@/src/api/client';
import { useApp } from '@/src/state/AppContext';
import { colors, radius } from '@/src/theme';

type EditableParameter = {
  key: string; label: string; unit: string; reference_low: number | null; reference_high: number | null;
  reference_source: ReferenceSource; raw_text: string | null; status: LabParameter['status']; value: string;
};

/** The model only reads the document; every row stays editable so a misread value can be corrected. */
function toEditableParameters(parameters: LabParameter[]): EditableParameter[] {
  return parameters.map(item => ({
    key: item.key, label: item.label, unit: item.unit || '', reference_low: item.reference_low ?? null,
    reference_high: item.reference_high ?? null, reference_source: item.reference_source || 'unknown',
    raw_text: item.raw_text ?? null, status: item.status || 'unknown',
    value: item.value == null ? '' : String(item.value),
  }));
}

/** A browser file picker. Cancelling resolves null so the caller always continues. */
function pickFileOnWeb(accept: string): Promise<ReportFile | null> {
  const { promise, resolve } = Promise.withResolvers<ReportFile | null>();
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = accept;
  const finish = (value: ReportFile | null) => { input.onchange = null; input.oncancel = null; resolve(value); };
  input.onchange = () => {
    const picked = input.files?.[0];
    finish(picked ? { uri: URL.createObjectURL(picked), name: picked.name, mimeType: picked.type || 'application/octet-stream' } : null);
  };
  input.oncancel = () => finish(null);
  input.click();
  return promise;
}

async function pickPhotoOnDevice(fromCamera: boolean): Promise<ReportFile | null> {
  const options = { mediaTypes: ['images'] as ImagePicker.MediaType[], quality: 0.9 };
  const result = fromCamera ? await ImagePicker.launchCameraAsync(options) : await ImagePicker.launchImageLibraryAsync(options);
  const asset = result.assets?.[0];
  if (result.canceled || !asset) return null;
  return { uri: asset.uri, name: asset.fileName, mimeType: asset.mimeType };
}

export default function ReportsScreen() {
  const { token } = useApp();
  const [reports, setReports] = useState<HealthReportSummary[]>([]);
  const [listError, setListError] = useState('');
  const [listBusy, setListBusy] = useState(false);
  const [review, setReview] = useState<HealthReportResult | null>(null);
  const [rows, setRows] = useState<EditableParameter[]>([]);
  const [collectedOn, setCollectedOn] = useState('');
  const [note, setNote] = useState('');
  const [extracting, setExtracting] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [message, setMessage] = useState('');
  const [formError, setFormError] = useState('');
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);

  const loadReports = useCallback(async () => {
    if (!token) return;
    setListBusy(true); setListError('');
    try { setReports((await api.reports(token, 20, 0)).reports); }
    catch (cause) { setListError(cause instanceof Error ? cause.message : 'Saved reports could not be loaded.'); }
    finally { setListBusy(false); }
  }, [token]);

  useEffect(() => { void loadReports(); }, [loadReports]);

  const upload = useCallback(async (file: ReportFile | null) => {
    if (!token || !file) return;
    setExtracting(true); setFormError(''); setMessage('Reading the report…');
    try {
      const result = await api.extractReport(token, file);
      setReview(result); setRows(toEditableParameters(result.parameters));
      setCollectedOn(result.collected_on || ''); setNote('');
      setMessage('Compare every value with the document, correct anything that is wrong, then confirm.');
      await loadReports();
    } catch (cause) {
      setFormError(cause instanceof Error ? cause.message : 'The report could not be read.');
      setMessage('');
    } finally { setExtracting(false); }
  }, [loadReports, token]);

  const choose = useCallback(async (kind: 'image' | 'pdf' | 'camera') => {
    if (Platform.OS === 'web') {
      await upload(await pickFileOnWeb(kind === 'pdf' ? 'application/pdf' : 'image/jpeg,image/png'));
      return;
    }
    await upload(await pickPhotoOnDevice(kind === 'camera'));
  }, [upload]);

  const confirm = useCallback(async () => {
    if (!token || !review) return;
    const parameters: ReportConfirm[] = [];
    for (const row of rows) {
      const raw = row.value.trim();
      const value = raw ? Number(raw) : null;
      if (value !== null && !Number.isFinite(value)) { setFormError(`${row.label} must be a number or left blank.`); return; }
      parameters.push({ key: row.key, label: row.label, value, unit: row.unit || null, reference_low: row.reference_low, reference_high: row.reference_high, reference_source: row.reference_source, raw_text: row.raw_text, status: row.status });
    }
    setConfirming(true); setFormError('');
    try {
      const updated = await api.confirmReport(token, review.id, { parameters, collected_on: collectedOn.trim() || null, note: note.trim() });
      setReview(updated); setRows(toEditableParameters(updated.parameters));
      setMessage('Confirmed. These values can inform your personal intake plan.');
      await loadReports();
    } catch (cause) { setFormError(cause instanceof Error ? cause.message : 'The confirmed values could not be saved.'); }
    finally { setConfirming(false); }
  }, [collectedOn, loadReports, note, review, rows, token]);

  const remove = useCallback(async (id: string) => {
    if (!token) return;
    setFormError('');
    try {
      await api.deleteReport(token, id);
      if (review?.id === id) { setReview(null); setRows([]); }
      setPendingDelete(null);
      await loadReports();
    } catch (cause) { setFormError(cause instanceof Error ? cause.message : 'The report could not be deleted.'); }
  }, [loadReports, review, token]);

  const confirmed = review?.status === 'confirmed';

  return <Screen>
    <PageHeader eyebrow="Your health data" title="Lab reports" subtitle="Upload a blood test or panel, check what was read, then confirm the values you want to keep." back />
    <Card style={st.upload}>
      <View style={st.uploadHead}><View style={st.uploadIcon}><MaterialCommunityIcons name="file-document-outline" size={22} color={colors.primary} /></View><View style={{ flex: 1 }}><Text style={st.cardTitle}>Add a report</Text><Text style={st.cardSub}>Photos of a printed report (JPEG or PNG){Platform.OS === 'web' ? ', or a PDF file' : ''}.</Text></View></View>
      {Platform.OS === 'web'
        ? <View style={st.actions}><Button title="Choose a JPEG or PNG" icon="image-outline" loading={extracting} disabled={extracting} onPress={() => void choose('image')} /><Button title="Choose a PDF file" icon="file-pdf-box" secondary disabled={extracting} onPress={() => void choose('pdf')} /></View>
        : <View style={st.actions}><Button title="Take a report photo" icon="camera-outline" loading={extracting} disabled={extracting} onPress={() => void choose('camera')} /><Button title="Choose a report photo" icon="image-outline" secondary disabled={extracting} onPress={() => void choose('image')} /><Text style={st.note}>PDF upload is available in the browser version. On this device, photograph the report or choose a saved image.</Text></View>}
      {extracting ? <View style={st.progress}><ActivityIndicator size="small" color={colors.primary} /><Text style={st.cardSub}>Reading the document… this can take up to a minute.</Text></View> : null}
      {message ? <Text style={st.message}>{message}</Text> : null}
      <Text style={st.note}>The uploaded file itself is not stored. Only the extracted values, a short hash of the file, and what you confirm are kept.</Text>
    </Card>

    {formError ? <Text accessibilityRole="alert" style={st.error}>{formError}</Text> : null}
    {review ? <Card style={st.review}>
      <View style={st.reviewHead}><View style={{ flex: 1 }}><Pill label={confirmed ? 'CONFIRMED' : 'NOT YET CONFIRMED'} tone={confirmed ? 'green' : 'amber'} /><Text style={st.cardTitle}>{rows.length} value{rows.length === 1 ? '' : 's'} read{review.abnormal_parameters.length ? ` · ${review.abnormal_parameters.length} flagged` : ''}</Text><Text style={st.cardSub}>Status is calculated by the backend from the printed reference range; your edits are saved as you confirm them.</Text></View></View>
      {review.warnings.map((warning, index) => <View key={index} style={st.warning}><MaterialCommunityIcons name="alert-outline" size={16} color={colors.amber} /><Text style={st.warningText}>{warning}</Text></View>)}
      <View style={st.rows}>{rows.map(row => <View key={row.key} style={st.paramRow}>
        <View style={{ flex: 1 }}>
          <Text style={st.paramLabel}>{row.label}</Text>
          <Text style={st.paramMeta}>{row.unit || 'unit not printed'} · reference {formatReferenceRange(row.reference_low, row.reference_high)}{row.reference_source === 'document' ? ' · printed on the report' : row.reference_source === 'standard' ? ' · standard range' : ''}</Text>
        </View>
        <TextInput accessibilityLabel={`Value for ${row.label}`} value={row.value} onChangeText={value => setRows(current => current.map(item => item.key === row.key ? { ...item, value } : item))} keyboardType="numeric" placeholder="blank = not recorded" placeholderTextColor={colors.subtle} style={st.paramInput} />
        <Pill label={(row.status || 'unknown').toUpperCase()} tone={parameterStatusTone(row.status)} />
      </View>)}</View>
      <View style={st.fields}><Text style={st.fieldLabel}>COLLECTION DATE (OPTIONAL)</Text><TextInput accessibilityLabel="Collection date" value={collectedOn} onChangeText={setCollectedOn} placeholder="e.g. 2026-05-14 as printed" placeholderTextColor={colors.subtle} style={st.input} /><Text style={st.fieldLabel}>NOTE (OPTIONAL)</Text><TextInput accessibilityLabel="Report note" value={note} onChangeText={setNote} placeholder="Anything you want to remember about this report" placeholderTextColor={colors.subtle} style={st.input} /></View>
      <Button title={confirmed ? 'Save corrected values again' : 'Confirm these values'} icon="check" loading={confirming} disabled={confirming} onPress={() => void confirm()} />
      <Text style={st.note}>Nothing becomes a limit here. Confirmed values inform proposals on your personal intake screen, and only you can accept a target.</Text>
    </Card> : null}

    <SectionTitle title="Saved reports" action="Refresh" onAction={() => void loadReports()} />
    {listError ? <Card style={st.warningCard}><Text accessibilityRole="alert" style={st.warningText}>{listError}</Text><Button title="Retry" compact secondary onPress={() => void loadReports()} /></Card> : null}
    {listBusy && !reports.length ? <Card style={st.empty}><ActivityIndicator size="small" color={colors.primary} /><Text style={st.cardSub}>Loading saved reports…</Text></Card> : null}
    {!listBusy && !reports.length ? <Card style={st.empty}><MaterialCommunityIcons name="file-search-outline" size={26} color={colors.subtle} /><Text style={st.cardTitle}>No reports yet</Text><Text style={st.cardSub}>Upload one above to read its values.</Text></Card> : null}
    {reports.map(item => <Card key={item.id} style={st.savedRow}>
      <View style={{ flex: 1 }}>
        <Pill label={item.status === 'confirmed' ? 'CONFIRMED' : 'NOT YET CONFIRMED'} tone={item.status === 'confirmed' ? 'green' : 'amber'} />
        <Text style={st.cardTitle}>{item.parameter_count} value{item.parameter_count === 1 ? '' : 's'}{item.abnormal_count ? ` · ${item.abnormal_count} flagged` : ''}</Text>
        <Text style={st.cardSub}>{item.collected_on ? `Collected ${item.collected_on} · ` : ''}Added {new Date(item.created_at).toLocaleString()}</Text>
      </View>
      <View style={st.savedActions}>
        <Pressable accessibilityRole="link" accessibilityLabel="Ask about these values in the intake plan" onPress={() => router.push('/intake')}><Text style={st.link}>Ask about these values</Text></Pressable>
        {pendingDelete === item.id
          ? <View style={st.confirmDelete}><Pressable accessibilityRole="button" accessibilityLabel="Confirm delete report" onPress={() => void remove(item.id)}><Text style={st.deleteConfirm}>Delete</Text></Pressable><Pressable accessibilityRole="button" accessibilityLabel="Cancel delete" onPress={() => setPendingDelete(null)}><Text style={st.link}>Cancel</Text></Pressable></View>
          : <Pressable accessibilityRole="button" accessibilityLabel="Delete report" onPress={() => setPendingDelete(item.id)}><Text style={st.delete}>Delete</Text></Pressable>}
      </View>
    </Card>)}
    <Button title="Open your personal intake plan" icon="clipboard-pulse-outline" secondary onPress={() => router.push('/intake')} />
    <Text style={st.disclaimer}>Report values are read by a model and can be wrong. This prototype does not diagnose or treat anything; confirm anything you act on with a clinician.</Text>
  </Screen>;
}

const st = StyleSheet.create({
  upload: { gap: 13 }, uploadHead: { flexDirection: 'row', alignItems: 'center', gap: 12 }, uploadIcon: { width: 47, height: 47, borderRadius: radius.input, backgroundColor: colors.lavender, alignItems: 'center', justifyContent: 'center' },
  actions: { gap: 9 }, progress: { flexDirection: 'row', alignItems: 'center', gap: 9 }, cardTitle: { color: colors.ink, fontSize: 15, lineHeight: 21, fontWeight: '700', marginTop: 6 }, cardSub: { color: colors.muted, fontSize: 11, lineHeight: 16, marginTop: 4 },
  message: { color: colors.primary, fontSize: 11, lineHeight: 16, fontWeight: '700' }, note: { color: colors.subtle, fontSize: 10, lineHeight: 14 },
  review: { gap: 13 }, reviewHead: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 }, warning: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, backgroundColor: colors.amberBg, borderRadius: radius.chip, padding: 10 }, warningText: { flex: 1, color: colors.amberInk, fontSize: 11, lineHeight: 15 },
  rows: { gap: 9 }, paramRow: { flexDirection: 'row', alignItems: 'center', gap: 9, borderTopWidth: 1, borderTopColor: colors.line, paddingTop: 9 }, paramLabel: { color: colors.ink, fontSize: 12, fontWeight: '800' }, paramMeta: { color: colors.muted, fontSize: 10, lineHeight: 14, marginTop: 3 }, paramInput: { width: 78, minHeight: 42, borderWidth: 1, borderColor: colors.line, borderRadius: radius.chip, paddingHorizontal: 10, color: colors.ink, fontSize: 12, backgroundColor: colors.canvas },
  fields: { gap: 7 }, fieldLabel: { color: colors.muted, letterSpacing: 1, fontSize: 9, fontWeight: '800' }, input: { minHeight: 44, borderRadius: radius.input, borderWidth: 1, borderColor: colors.line, paddingHorizontal: 12, color: colors.ink, fontSize: 12, backgroundColor: colors.surface },
  empty: { alignItems: 'center', gap: 7 }, warningCard: { gap: 9, backgroundColor: colors.redBg }, savedRow: { flexDirection: 'row', alignItems: 'center', gap: 11 }, savedActions: { alignItems: 'flex-end', gap: 7 }, confirmDelete: { flexDirection: 'row', alignItems: 'center', gap: 11 }, link: { color: colors.primary, fontSize: 11, fontWeight: '700' }, delete: { color: colors.muted, fontSize: 11, fontWeight: '700' }, deleteConfirm: { color: colors.red, fontSize: 11, fontWeight: '800' },
  error: { color: colors.red, fontSize: 12, lineHeight: 17 }, disclaimer: { textAlign: 'center', color: colors.subtle, fontSize: 10, lineHeight: 15, paddingHorizontal: 15 },
});
