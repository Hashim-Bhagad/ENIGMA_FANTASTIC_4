import React from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleProp, StyleSheet, Text, TextInput, View, ViewStyle } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { colors, radius } from '@/src/theme';

export function Screen({ children, scroll = true, style }: React.PropsWithChildren<{ scroll?: boolean; style?: StyleProp<ViewStyle> }>) {
  return <SafeAreaView edges={['top']} style={s.safe}><View style={[s.frame, style]}>{scroll ? <ScrollView contentContainerStyle={s.content} showsVerticalScrollIndicator={false}>{children}</ScrollView> : children}</View></SafeAreaView>;
}
export function PageHeader({ eyebrow, title, subtitle, back = false, right }: { eyebrow?: string; title: string; subtitle?: string; back?: boolean; right?: React.ReactNode }) {
  return <View style={s.headerRow}>{back && <Pressable accessibilityRole="button" accessibilityLabel="Go back" onPress={() => router.back()} style={s.back}><MaterialCommunityIcons name="arrow-left" size={22} color={colors.ink} /></Pressable>}<View style={{ flex: 1 }}>
    {eyebrow ? <Text style={s.eyebrow}>{eyebrow.toUpperCase()}</Text> : null}<Text style={s.title}>{title}</Text>{subtitle ? <Text style={s.subtitle}>{subtitle}</Text> : null}
  </View>{right}</View>;
}
export function Card({ children, style }: React.PropsWithChildren<{ style?: StyleProp<ViewStyle> }>) { return <View style={[s.card, style]}>{children}</View>; }
export function SectionTitle({ title, action, onAction }: { title: string; action?: string; onAction?: () => void }) {
  return <View style={s.sectionRow}><Text accessibilityRole="header" style={s.sectionTitle}>{title}</Text>{action && <Pressable accessibilityRole="button" accessibilityLabel={action} onPress={onAction}><Text style={s.actionText}>{action}</Text></Pressable>}</View>;
}
export function Button({ title, onPress, secondary = false, icon, compact = false, style, disabled = false, loading = false }: { title: string; onPress: () => void; secondary?: boolean; icon?: keyof typeof MaterialCommunityIcons.glyphMap; compact?: boolean; style?: StyleProp<ViewStyle>; disabled?: boolean; loading?: boolean }) {
  const inactive = disabled || loading;
  const accent = secondary ? colors.primary : colors.onPrimary;
  return <Pressable accessibilityRole="button" accessibilityLabel={title} accessibilityState={{ disabled: inactive, busy: loading }} disabled={inactive} onPress={onPress} style={({ pressed }) => [s.button, secondary && s.buttonSecondary, compact && s.buttonCompact, inactive && s.buttonDisabled, pressed && !inactive && { opacity: 0.88, transform: [{ scale: 0.985 }] }, style]}>
    {loading ? <ActivityIndicator size="small" color={accent} /> : icon ? <MaterialCommunityIcons name={icon} size={18} color={accent} /> : null}
    <Text style={[s.buttonText, secondary && s.buttonSecondaryText, compact && { fontSize: 13 }]}>{title}</Text>
  </Pressable>;
}
export function Pill({ label, tone = 'neutral', icon }: { label: string; tone?: 'neutral' | 'green' | 'amber' | 'red' | 'blue' | 'purple'; icon?: keyof typeof MaterialCommunityIcons.glyphMap }) {
  const tones = { neutral: [colors.canvas, colors.muted], green: [colors.greenBg, colors.green], amber: [colors.amberBg, colors.amber], red: [colors.redBg, colors.red], blue: [colors.blueBg, colors.blue], purple: [colors.lavender, colors.primaryDark] } as const;
  return <View style={[s.pill, { backgroundColor: tones[tone][0] }]}>{icon && <MaterialCommunityIcons name={icon} size={13} color={tones[tone][1]} />}<Text style={[s.pillText, { color: tones[tone][1] }]}>{label}</Text></View>;
}
export function Field({ label, value, onChangeText, placeholder, keyboardType, multiline = false, onSubmitEditing, returnKeyType, autoCorrect, hint }: { label: string; value: string; onChangeText: (value: string) => void; placeholder?: string; keyboardType?: 'default' | 'numeric' | 'email-address'; multiline?: boolean; onSubmitEditing?: () => void; returnKeyType?: 'default' | 'done' | 'next' | 'search'; autoCorrect?: boolean; hint?: React.ReactNode }) {
  return <View style={{ gap: 7 }}><Text style={s.fieldLabel}>{label}</Text><TextInput accessibilityLabel={label} value={value} onChangeText={onChangeText} placeholder={placeholder} placeholderTextColor={colors.subtle} keyboardType={keyboardType} multiline={multiline} onSubmitEditing={onSubmitEditing} returnKeyType={returnKeyType} autoCorrect={autoCorrect} textAlignVertical={multiline ? 'top' : 'center'} style={[s.input, multiline && { minHeight: 96, paddingTop: 13 }]} />{hint}</View>;
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.canvas }, frame: { flex: 1, width: '100%', maxWidth: 840, alignSelf: 'center' }, content: { paddingHorizontal: 20, paddingTop: 16, paddingBottom: 30, gap: 18 },
  headerRow: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 3 }, back: { width: 42, height: 42, borderRadius: radius.input, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center' },
  eyebrow: { fontSize: 10, lineHeight: 14, letterSpacing: 1.4, color: colors.primary, fontWeight: '800', marginBottom: 5 }, title: { color: colors.ink, fontSize: 27, lineHeight: 33, fontWeight: '800', letterSpacing: -.65 }, subtitle: { color: colors.muted, fontSize: 13, lineHeight: 19, marginTop: 5, maxWidth: 500 },
  card: { backgroundColor: colors.surface, borderRadius: radius.card, padding: 18, shadowColor: colors.shadow, shadowOpacity: .045, shadowRadius: 14, shadowOffset: { width: 0, height: 5 }, elevation: 1 },
  sectionRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: -6 }, sectionTitle: { fontSize: 17, lineHeight: 23, fontWeight: '700', color: colors.ink }, actionText: { color: colors.primary, fontSize: 12, fontWeight: '700' },
  button: { backgroundColor: colors.primary, minHeight: 50, borderRadius: radius.pill, paddingHorizontal: 19, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 9 }, buttonSecondary: { backgroundColor: colors.surface, borderColor: colors.line, borderWidth: 1 }, buttonCompact: { minHeight: 40, paddingHorizontal: 15 }, buttonDisabled: { opacity: 0.55 }, buttonText: { color: colors.onPrimary, fontSize: 14, fontWeight: '700' }, buttonSecondaryText: { color: colors.primary },
  pill: { alignSelf: 'flex-start', borderRadius: radius.pill, paddingHorizontal: 10, paddingVertical: 6, flexDirection: 'row', alignItems: 'center', gap: 5 }, pillText: { fontSize: 10, lineHeight: 13, fontWeight: '800' },
  fieldLabel: { color: colors.ink, fontSize: 12, fontWeight: '700' }, input: { borderWidth: 1, borderColor: colors.line, borderRadius: radius.input, backgroundColor: colors.surface, color: colors.ink, minHeight: 48, paddingHorizontal: 14, fontSize: 14 },
});
