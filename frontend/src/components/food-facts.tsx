import React, { useState } from 'react';
import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';
import { Card, Pill } from '@/src/components/ui';
import { colors } from '@/src/theme';
import { nutrientFields } from '@/src/data/nutrients';
import type { FoodObservation, ProductProvenance } from '@/src/api/client';

export function FoodFacts({ food, trace }: { food: FoodObservation; trace?: ProductProvenance | null }) {
  const [expanded, setExpanded] = useState(false);
  const known = nutrientFields.filter(item => food.nutrients[item.key] != null);
  const missing = nutrientFields.filter(item => food.nutrients[item.key] == null);
  return <Card style={{ gap: 16 }}>
    <View style={s.heading}><Text style={s.title}>Nutrition & evidence</Text><Pill label={`${known.length}/10 nutrients recorded`} tone="blue" /></View>
    <Text style={s.copy}>{food.basis ? `Amounts per ${food.basis === '100g' ? '100 g' : '100 ml'}.` : 'No measured nutrient basis is available.'} Missing values stay unknown.</Text>
    {known.length ? <View style={s.grid}>{known.map(({ key, label, unit }) => <View key={key} style={s.cell}><Text style={s.label}>{label}</Text><Text style={s.value}>{food.nutrients[key]} <Text style={s.unit}>{unit}</Text></Text></View>)}</View> : null}
    {missing.length ? <View style={s.unknown}><Text style={s.label}>Not supplied</Text><Text style={s.copy}>{missing.map(item => item.label).join(' · ')}</Text></View> : null}
    <View style={{ gap: 8 }}><Text style={s.label}>Source: {food.source.kind.replaceAll('_', ' ')}</Text><Text selectable style={s.copy}>{food.source.reference}</Text>
      {food.source.retrieved_at ? <Text style={s.copy}>Retrieved: {food.source.retrieved_at}</Text> : null}
      {/^https?:\/\//i.test(food.source.reference) ? <Pressable accessibilityRole="link" onPress={() => void Linking.openURL(food.source.reference)} style={s.action}><Text style={s.actionText}>Open source record ↗</Text></Pressable> : null}
    </View>
    {trace ? <>
      <Pressable accessibilityRole="button" accessibilityState={{ expanded }} onPress={() => setExpanded(value => !value)} style={s.action}><Text style={s.actionText}>{expanded ? 'Hide field trace' : 'How were these values obtained?'}</Text></Pressable>
      {expanded ? trace.fields.filter(item => nutrientFields.some(field => field.key === item.field)).map(item => <View key={item.field} style={s.trace}><Text style={s.label}>{nutrientFields.find(field => field.key === item.field)?.label}</Text><Text selectable style={s.copy}>{item.source_field || 'Recorded observation'}: {item.source_value == null ? 'unknown' : String(item.source_value)} {item.source_unit || ''} → {item.value == null ? 'unknown' : String(item.value)} {item.unit || ''}</Text><Text style={s.copy}>{item.reason || item.transformation}</Text></View>) : null}
      {trace.edited_fields?.length ? <Text style={s.copy}>User corrections: {trace.edited_fields.join(', ')}. The trace retains the catalog values; nutrition above shows the submitted values.</Text> : null}
    </> : <Text style={s.copy}>{food.source.kind === 'dish' ? 'These ingredients were submitted by you. Recipe reference data does not verify the meal actually served.' : 'No catalog field trace is attached to this observation.'}</Text>}
  </Card>;
}

const s = StyleSheet.create({
  heading: { gap: 10 }, title: { fontSize: 18, fontWeight: '800', color: colors.ink },
  copy: { fontSize: 14, lineHeight: 21, color: colors.muted }, label: { fontSize: 13, lineHeight: 19, fontWeight: '700', color: colors.ink },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 }, cell: { flexGrow: 1, flexBasis: '44%', minWidth: 130, backgroundColor: colors.canvas, borderRadius: 14, padding: 14, gap: 8 },
  value: { fontSize: 23, color: colors.ink, fontWeight: '800' }, unit: { fontSize: 13, fontWeight: '500', color: colors.muted },
  unknown: { borderLeftWidth: 3, borderColor: colors.amber, paddingLeft: 12, gap: 5 },
  action: { minHeight: 44, justifyContent: 'center' }, actionText: { color: colors.primaryDark, fontSize: 14, fontWeight: '700' },
  trace: { gap: 6, borderTopWidth: 1, borderColor: colors.line, paddingTop: 12 },
});
