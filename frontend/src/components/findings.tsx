import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Card, Pill } from '@/src/components/ui';
import { colors, radius, typography } from '@/src/theme';
import type { AssessmentResult, AssessmentStatus, Finding } from '@/src/api/client';

/** Keep the existing status→tone mapping in one place for every assessment surface. */
export function statusTone(status: AssessmentStatus): 'red' | 'amber' | 'blue' {
  return status === 'recorded_conflict' ? 'red' : status === 'needs_information' ? 'amber' : 'blue';
}

const GROUPS = {
  conflict: { label: 'CONFLICT', tone: 'red', icon: 'alert-circle-outline', color: colors.red, bg: colors.redBg },
  unresolved: { label: 'NEEDS INFORMATION', tone: 'amber', icon: 'help-circle-outline', color: colors.amber, bg: colors.amberBg },
  consideration: { label: 'CONSIDERATION', tone: 'blue', icon: 'information-outline', color: colors.blue, bg: colors.blueBg },
} as const;

export function FindingCard({ finding }: { finding: Finding }) {
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const appearance = GROUPS[finding.group];
  return <Card style={st.finding}>
    <View style={[st.icon, { backgroundColor: appearance.bg }]}><MaterialCommunityIcons name={appearance.icon} size={21} color={appearance.color} /></View>
    <View style={{ flex: 1, gap: 6 }}>
      <View style={st.heading}><Text style={st.title}>{finding.title}</Text><Pill label={appearance.label} tone={appearance.tone} /></View>
      <Text style={st.detail}>{finding.detail}</Text>
      {finding.next_step ? <Text style={st.detail}><Text style={st.lead}>Next step: </Text>{finding.next_step}</Text> : null}
      {finding.affects.length > 0 ? <Text style={st.meta}>Affects: {finding.affects.join(', ')}</Text> : null}
      {finding.evidence.length > 0 ? <>
        <Pressable accessibilityRole="button" accessibilityState={{ expanded: evidenceOpen }} onPress={() => setEvidenceOpen(value => !value)} style={({ pressed }) => [st.toggleRow, pressed && st.pressed]}><Text style={st.toggle}>{evidenceOpen ? 'Hide evidence' : `Show evidence (${finding.evidence.length})`}</Text></Pressable>
        {evidenceOpen ? finding.evidence.map((item, index) => <Text key={index} selectable style={st.meta}>{'\u2022'} {item}</Text>) : null}
      </> : null}
    </View>
  </Card>;
}

/** The one renderer shared by packaged-product and cooked-meal assessments. */
export function FindingsList({ result }: { result: AssessmentResult }) {
  const rows: Finding[] = [...result.conflicts, ...result.unresolved, ...result.considerations];
  if (!rows.length) return <Card style={st.finding}><Text style={st.title}>No matching concern was found under these checks.</Text><Text style={st.detail}>This is not a universal safety or suitability guarantee.</Text></Card>;
  return <View style={{ gap: 10 }}>{rows.map((finding, index) => <FindingCard key={`${finding.code}-${index}`} finding={finding} />)}</View>;
}

export function findingCount(result: AssessmentResult): number {
  return result.conflicts.length + result.unresolved.length + result.considerations.length;
}

const st = StyleSheet.create({
  finding: { flexDirection: 'row', alignItems: 'flex-start', gap: 12, padding: 16 },
  icon: { width: 40, height: 40, borderRadius: radius.chip, alignItems: 'center', justifyContent: 'center' },
  heading: { alignItems: 'flex-start', gap: 8 },
  title: { flex: 1, color: colors.ink, fontSize: 16, lineHeight: 22, fontWeight: '800' },
  detail: { ...typography.body, color: colors.ink },
  lead: { fontWeight: '800' },
  meta: { ...typography.meta, color: colors.muted },
  toggleRow: { minHeight: 44, justifyContent: 'center' },
  toggle: { ...typography.bodyStrong, color: colors.primary },
  pressed: { opacity: 0.8 },
});
