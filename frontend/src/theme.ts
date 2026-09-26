export const colors = {
  canvas: '#F2F7F7', surface: '#FFFFFF', ink: '#152E32', muted: '#50686D', subtle: '#60777C',
  primary: '#086F73', primaryDark: '#07575B', lavender: '#E1F2F1', line: '#DDE8E8', stroke: '#819A9F',
  green: '#0F7346', greenBg: '#E7F7EE', amber: '#8A5600', amberBg: '#FFF3D8',
  red: '#B23039', redBg: '#FDEBED', blue: '#1B6089', blueBg: '#EAF5FC', orangeBg: '#FFF0E4',
  // Text on solid brand/green surfaces and darker inks for tinted banners.
  onPrimary: '#FFFFFF', amberInk: '#785015', blueInk: '#285F7D', purpleInk: '#07575B',
  // Soft surfaces, rules and shadows shared by cards, chips and toggles.
  canvasSoft: '#F8FCFC', lavenderSoft: '#EDF7F6', lavenderTint: '#EAF5F4', lavenderLine: '#D3E9E7',
  greenTint: '#F5FBF7', chip: '#E4EEEE', rule: '#DDE8E8', track: '#CEDDDD',
  shadow: '#183B40', camera: '#132D31',
  hero: '#123F44', heroText: '#D1E9E8', accent: '#CBEA82', accentInk: '#284419',
};

// One radius system: card surfaces, interactive controls, tiles, chips, pills, avatars.
export const radius = { card: 24, control: 14, tile: 14, chip: 12, pill: 999, avatar: 14 };

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 20, xxl: 28 };

export const typography = {
  display: { fontSize: 30, lineHeight: 37, fontWeight: '800' as const, letterSpacing: -0.4 },
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
