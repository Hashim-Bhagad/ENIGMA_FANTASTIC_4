import React, { useState } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleProp, StyleSheet, Text, TextInput, View, ViewStyle } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { colors, radius, space, typography } from '@/src/theme';
import { HOME_TAB, backAction } from '@/src/navigation';

export function Screen({ children, scroll = true, style }: React.PropsWithChildren<{ scroll?: boolean; style?: StyleProp<ViewStyle> }>) {
  return <SafeAreaView edges={['top']} style={s.safe}><KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={[s.frame, style]}>{scroll ? <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={s.content} showsVerticalScrollIndicator={false}>{children}</ScrollView> : children}</KeyboardAvoidingView></SafeAreaView>;
}
export function PageHeader({ eyebrow, title, subtitle, back = false, backFallback = HOME_TAB, right }: { eyebrow?: string; title: string; subtitle?: string; back?: boolean; backFallback?: string; right?: React.ReactNode }) {
  const goBack = () => {
    const fallback = backAction(router.canGoBack(), backFallback);
    if (fallback.replace) router.replace(fallback.replace as never);
    else router.back();
  };
  return <View style={s.headerRow}>{back && <Pressable accessibilityRole="button" accessibilityLabel="Go back" onPress={goBack} style={({ pressed }) => [s.back, pressed && s.pressed]}><MaterialCommunityIcons name="arrow-left" size={22} color={colors.ink} /></Pressable>}<View style={{ flex: 1 }}>
    {eyebrow ? <Text style={s.eyebrow}>{eyebrow.toUpperCase()}</Text> : null}<Text accessibilityRole="header" style={s.title}>{title}</Text>{subtitle ? <Text style={s.subtitle}>{subtitle}</Text> : null}
  </View>{right}</View>;
}
export function Card({ children, style }: React.PropsWithChildren<{ style?: StyleProp<ViewStyle> }>) { return <View style={[s.card, style]}>{children}</View>; }
export function SectionTitle({ title, action, onAction }: { title: string; action?: string; onAction?: () => void }) {
  return <View style={s.sectionRow}><Text accessibilityRole="header" style={s.sectionTitle}>{title}</Text>{action && onAction ? <Pressable accessibilityRole="button" accessibilityLabel={action} onPress={onAction} style={({ pressed }) => pressed && s.pressed}><Text style={s.actionText}>{action}</Text></Pressable> : action ? <Text style={s.subtitle}>{action}</Text> : null}</View>;
}
export function Button({ title, onPress, secondary = false, icon, compact = false, style, disabled = false, loading = false }: { title: string; onPress: () => void; secondary?: boolean; icon?: keyof typeof MaterialCommunityIcons.glyphMap; compact?: boolean; style?: StyleProp<ViewStyle>; disabled?: boolean; loading?: boolean }) {
  const inactive = disabled || loading;
  const accent = secondary ? colors.primary : colors.onPrimary;
  return <Pressable accessibilityRole="button" accessibilityLabel={title} accessibilityState={{ disabled: inactive, busy: loading }} disabled={inactive} onPress={onPress} style={({ pressed }) => [s.button, secondary && s.buttonSecondary, compact && s.buttonCompact, inactive && s.buttonDisabled, pressed && !inactive && { opacity: 0.9, transform: [{ scale: 0.985 }] }, style]}>
    {loading ? <ActivityIndicator size="small" color={accent} /> : icon ? <MaterialCommunityIcons name={icon} size={19} color={accent} /> : null}
    <Text style={[s.buttonText, secondary && s.buttonSecondaryText, compact && { fontSize: 14 }]}>{title}</Text>
  </Pressable>;
}
export function Pill({ label, tone = 'neutral', icon }: { label: string; tone?: 'neutral' | 'green' | 'amber' | 'red' | 'blue' | 'purple'; icon?: keyof typeof MaterialCommunityIcons.glyphMap }) {
  const tones = { neutral: [colors.canvas, colors.muted], green: [colors.greenBg, colors.green], amber: [colors.amberBg, colors.amber], red: [colors.redBg, colors.red], blue: [colors.blueBg, colors.blue], purple: [colors.lavender, colors.primaryDark] } as const;
  return <View style={[s.pill, { backgroundColor: tones[tone][0] }]}>{icon && <MaterialCommunityIcons name={icon} size={14} color={tones[tone][1]} />}<Text style={[s.pillText, { color: tones[tone][1] }]}>{label}</Text></View>;
}
export function Field({ label, value, onChangeText, placeholder, keyboardType, multiline = false, onSubmitEditing, returnKeyType, autoCorrect, hint }: { label: string; value: string; onChangeText: (value: string) => void; placeholder?: string; keyboardType?: 'default' | 'numeric' | 'email-address'; multiline?: boolean; onSubmitEditing?: () => void; returnKeyType?: 'default' | 'done' | 'next' | 'search'; autoCorrect?: boolean; hint?: React.ReactNode }) {
  const [focused, setFocused] = useState(false);
  return <View style={{ gap: space.sm }}><Text style={s.fieldLabel}>{label}</Text><TextInput accessibilityLabel={label} value={value} onChangeText={onChangeText} onFocus={() => setFocused(true)} onBlur={() => setFocused(false)} placeholder={placeholder} placeholderTextColor={colors.subtle} keyboardType={keyboardType} multiline={multiline} onSubmitEditing={onSubmitEditing} returnKeyType={returnKeyType} autoCorrect={autoCorrect} textAlignVertical={multiline ? 'top' : 'center'} style={[s.input, focused && s.inputFocused, multiline && { minHeight: 104, paddingTop: 14 }]} />{hint}</View>;
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.canvas }, frame: { flex: 1, width: '100%', maxWidth: 960, alignSelf: 'center' }, content: { paddingHorizontal: space.xl, paddingTop: space.xxl, paddingBottom: 40, gap: 22 },
  headerRow: { flexDirection: 'row', alignItems: 'center', gap: space.md, marginBottom: 3 }, back: { width: 44, height: 44, borderRadius: radius.control, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line, alignItems: 'center', justifyContent: 'center' }, pressed: { opacity: 0.85, transform: [{ scale: 0.98 }] },
  eyebrow: { ...typography.label, color: colors.primary, marginBottom: 6 }, title: { ...typography.display, color: colors.ink }, subtitle: { ...typography.body, color: colors.muted, marginTop: 6, maxWidth: 560 },
  card: { backgroundColor: colors.surface, borderRadius: radius.card, borderWidth: 1, borderColor: colors.line, padding: 18, shadowColor: colors.shadow, shadowOpacity: .025, shadowRadius: 16, shadowOffset: { width: 0, height: 6 }, elevation: 1 },
  sectionRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space.sm, marginBottom: -4 }, sectionTitle: { ...typography.section, color: colors.ink, flexShrink: 1 }, actionText: { ...typography.meta, color: colors.primary, fontWeight: '700', paddingVertical: 12 },
  button: { backgroundColor: colors.primary, minHeight: 52, borderRadius: radius.control, paddingHorizontal: 20, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 9 }, buttonSecondary: { backgroundColor: colors.surface, borderColor: colors.stroke, borderWidth: 1 }, buttonCompact: { minHeight: 44, paddingHorizontal: 16 }, buttonDisabled: { opacity: 0.5 }, buttonText: { ...typography.action, color: colors.onPrimary }, buttonSecondaryText: { color: colors.primary },
  pill: { alignSelf: 'flex-start', borderRadius: radius.pill, paddingHorizontal: 11, paddingVertical: 6, flexDirection: 'row', alignItems: 'center', gap: 5 }, pillText: { fontSize: 11, lineHeight: 15, fontWeight: '800' },
  fieldLabel: { ...typography.meta, color: colors.ink, fontWeight: '700' }, input: { borderWidth: 1, borderColor: colors.stroke, borderRadius: radius.control, backgroundColor: colors.surface, color: colors.ink, minHeight: 50, paddingHorizontal: 14, fontSize: 16 }, inputFocused: { borderColor: colors.primary },
});

/** Additional context stays available without crowding the primary task. */
export function Disclosure({ title, subtitle, children }: React.PropsWithChildren<{ title: string; subtitle?: string }>) {
  const [open, setOpen] = useState(false);
  return <Card style={{ gap: open ? 18 : 0 }}>
    <Pressable accessibilityRole="button" accessibilityState={{ expanded: open }} onPress={() => setOpen(value => !value)} style={{ minHeight: 44, flexDirection: 'row', alignItems: 'center', gap: 12 }}>
      <View style={{ flex: 1 }}><Text style={s.sectionTitle}>{title}</Text>{subtitle ? <Text style={s.subtitle}>{subtitle}</Text> : null}</View>
      <MaterialCommunityIcons name={open ? 'chevron-up' : 'chevron-down'} size={22} color={colors.primary} />
    </Pressable>
    {open ? children : null}
  </Card>;
}

export function FlowSteps({ current }: { current: 0 | 1 | 2 }) {
  return <View accessibilityLabel={`Step ${current + 1} of 3: ${['Find food', 'Review label', 'Read findings'][current]}`} style={{ flexDirection: 'row', gap: 8 }}>
    {['Find food', 'Review label', 'Read findings'].map((label, index) => <View key={label} style={{ flex: 1, gap: 7 }}>
      <View style={{ height: 3, borderRadius: 2, backgroundColor: index <= current ? colors.primary : colors.line }} />
      <Text style={{ ...typography.caption, color: index === current ? colors.primaryDark : colors.muted, fontWeight: index === current ? '700' : '400' }}>{index + 1}. {label}</Text>
    </View>)}
  </View>;
}
