import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { router } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Button, Card, PageHeader, Screen } from '@/src/components/ui';
import { useApp } from '@/src/state/AppContext';
import { colors } from '@/src/theme';

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
    <PageHeader eyebrow="SafeBitez" title={creating ? 'Create your account' : 'Welcome back'} subtitle="Sign in to load your saved food profile and checks." />
    {authState === 'session-error' && <Card style={st.error}><Text style={st.errorText}>{authError}</Text><Button title="Retry saved session" secondary compact onPress={() => void retrySession()} /></Card>}
    <Card style={st.form}>
      <View style={st.brand}><View style={st.logo}><MaterialCommunityIcons name="shield-outline" size={26} color={colors.primary} /></View><Text style={st.heading}>{creating ? 'Start your personal food guide' : 'Your profile, wherever you sign in'}</Text><Text style={st.copy}>Your profile and assessment history are saved to your account.</Text></View>
      <View style={{ gap: 7 }}><Text style={st.label}>EMAIL</Text><TextInput autoCapitalize="none" autoComplete="email" keyboardType="email-address" value={email} onChangeText={setEmail} placeholder="you@example.com" style={st.input} /></View>
      <View style={{ gap: 7 }}><Text style={st.label}>PASSWORD</Text><TextInput autoComplete={creating ? 'new-password' : 'current-password'} secureTextEntry value={password} onChangeText={setPassword} placeholder={creating ? 'At least 10 characters' : 'Your password'} style={st.input} /></View>
      {error ? <Text accessibilityRole="alert" style={st.errorText}>{error}</Text> : null}
      <Button title={busy ? 'Connecting…' : creating ? 'Create account' : 'Sign in'} icon="arrow-right" onPress={() => void submit()} />
      <Pressable onPress={() => { setCreating(value => !value); setError(''); }} style={st.switch}><Text style={st.switchText}>{creating ? 'Already have an account? Sign in' : 'New here? Create an account'}</Text></Pressable>
    </Card>
    <Text style={st.foot}>Food checks use the restrictions you record and the product information available. Missing label details remain unknown.</Text>
  </Screen>;
}

const st = StyleSheet.create({ form: { gap: 17 }, brand: { alignItems: 'center', gap: 8, paddingBottom: 5 }, logo: { width: 58, height: 58, borderRadius: 20, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.lavender }, heading: { color: colors.ink, fontSize: 18, fontWeight: '800', textAlign: 'center' }, copy: { color: colors.muted, fontSize: 12, lineHeight: 18, textAlign: 'center' }, label: { color: colors.muted, fontSize: 9, fontWeight: '800', letterSpacing: 1 }, input: { minHeight: 49, borderRadius: 14, borderWidth: 1, borderColor: colors.line, paddingHorizontal: 13, color: colors.ink, backgroundColor: '#FFFFFF' }, switch: { alignItems: 'center', paddingVertical: 5 }, switchText: { color: colors.primary, fontSize: 12, fontWeight: '700' }, error: { gap: 8, backgroundColor: colors.redBg }, errorText: { color: colors.red, fontSize: 12, lineHeight: 17 }, foot: { color: colors.subtle, fontSize: 10, lineHeight: 15, textAlign: 'center', paddingHorizontal: 18 } });
