export const colors = {
  canvas: '#F6F6F9', surface: '#FFFFFF', ink: '#1A1C1E', muted: '#5F5C72', subtle: '#6B6880',
  primary: '#5C45FD', primaryDark: '#4220E5', lavender: '#EEEAFE', line: '#E9E7F0', stroke: '#98939F',
  green: '#0F7346', greenBg: '#E7F7EE', amber: '#8A5600', amberBg: '#FFF3D8',
  red: '#B23039', redBg: '#FDEBED', blue: '#1B6089', blueBg: '#EAF5FC', orangeBg: '#FFF0E4',
  // Text on solid brand/green surfaces and darker inks for tinted banners.
  onPrimary: '#FFFFFF', amberInk: '#785015', blueInk: '#285F7D', purpleInk: '#4E3AC2',
  // Soft surfaces, rules and shadows shared by cards, chips and toggles.
  canvasSoft: '#FBFAFF', lavenderSoft: '#F3F0FF', lavenderTint: '#F4F2FE', lavenderLine: '#EFECFF',
  greenTint: '#F5FBF7', chip: '#ECEBF1', rule: '#E9E7F0', track: '#DDDCE5',
  shadow: '#3525A8', camera: '#171525',
};

// One radius system: card surfaces, interactive controls, tiles, chips, pills, avatars.
export const radius = { card: 20, control: 14, tile: 14, chip: 12, pill: 999, avatar: 14 };

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 20, xxl: 28 };

export const typography = {
  display: { fontSize: 26, lineHeight: 32, fontWeight: '800' as const, letterSpacing: -0.4 },
  title: { fontSize: 20, lineHeight: 26, fontWeight: '800' as const, letterSpacing: -0.2 },
  section: { fontSize: 16, lineHeight: 22, fontWeight: '700' as const },
  cardTitle: { fontSize: 16, lineHeight: 22, fontWeight: '700' as const },
  body: { fontSize: 15, lineHeight: 22 },
  bodyStrong: { fontSize: 15, lineHeight: 22, fontWeight: '700' as const },
  meta: { fontSize: 13, lineHeight: 19 },
  label: { fontSize: 11, lineHeight: 15, fontWeight: '800' as const, letterSpacing: 0.9 },
  caption: { fontSize: 12, lineHeight: 17 },
  action: { fontSize: 15, lineHeight: 20, fontWeight: '700' as const },
};
