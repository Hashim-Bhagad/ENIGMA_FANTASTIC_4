import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { router } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Button, Card, PageHeader, Screen } from '@/src/components/ui';
import { useApp } from '@/src/state/AppContext';
import { colors, radius, typography } from '@/src/theme';

export default function LoginScreen() {
  const { authenticate, retrySession, authState, authError, busy } = useApp();
  const [creating, setCreating] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const submit = async () => {
    setError('');
    try { await authenticate(email.trim(), password, creating); router.replace('/(tabs)/guide'); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not sign in.'); }
  };
  return <Screen>
    <PageHeader title={creating ? 'Create your account' : 'Welcome back'} subtitle="Sign in to load your saved food profile and checks." />
    {authState === 'session-error' && <Card style={st.error}><Text style={st.errorText}>{authError}</Text><Button title="Retry saved session" secondary compact onPress={() => void retrySession()} /></Card>}
    <Card style={st.form}>
      <View style={st.brand}><View style={st.logo}><MaterialCommunityIcons name="shield-outline" size={26} color={colors.primary} /></View><Text style={st.heading}>{creating ? 'Start your personal food guide' : 'Your profile, wherever you sign in'}</Text><Text style={st.copy}>Your profile and assessment history are saved to your account.</Text></View>
      <View style={{ gap: 7 }}><Text style={st.label}>EMAIL</Text><TextInput accessibilityLabel="Email" autoCapitalize="none" autoComplete="email" keyboardType="email-address" value={email} onChangeText={setEmail} placeholder="you@example.com" placeholderTextColor={colors.subtle} style={st.input} /></View>
      <View style={{ gap: 7 }}><Text style={st.label}>PASSWORD</Text><TextInput accessibilityLabel="Password" autoComplete={creating ? 'new-password' : 'current-password'} secureTextEntry value={password} onChangeText={setPassword} placeholder={creating ? 'At least 10 characters' : 'Your password'} placeholderTextColor={colors.subtle} style={st.input} /></View>
      {error ? <Text accessibilityRole="alert" style={st.errorText}>{error}</Text> : null}
      <Button title={busy ? 'Connecting…' : creating ? 'Create account' : 'Sign in'} icon="arrow-right" onPress={() => void submit()} />
      <Pressable onPress={() => { setCreating(value => !value); setError(''); }} style={({ pressed }) => [st.switch, pressed && st.pressed]}><Text style={st.switchText}>{creating ? 'Already have an account? Sign in' : 'New here? Create an account'}</Text></Pressable>
    </Card>
    <Text style={st.foot}>Food checks use the restrictions you record and the product information available. Missing label details remain unknown.</Text>
  </Screen>;
}

const st = StyleSheet.create({
  form: { gap: 18 }, brand: { alignItems: 'center', gap: 8, paddingBottom: 5 },
  logo: { width: 58, height: 58, borderRadius: radius.card, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.lavender },
  heading: { ...typography.title, color: colors.ink, textAlign: 'center' }, copy: { ...typography.meta, color: colors.muted, textAlign: 'center' },
  label: { ...typography.label, color: colors.muted }, input: { minHeight: 52, borderRadius: radius.control, borderWidth: 1, borderColor: colors.stroke, paddingHorizontal: 14, color: colors.ink, fontSize: 16, backgroundColor: colors.surface },
  switch: { alignItems: 'center', paddingVertical: 12 }, switchText: { ...typography.meta, color: colors.primary, fontWeight: '700' }, pressed: { opacity: 0.85 },
  error: { gap: 8, backgroundColor: colors.redBg }, errorText: { ...typography.meta, color: colors.red },
  foot: { ...typography.caption, color: colors.subtle, textAlign: 'center', paddingHorizontal: 18 },
});
