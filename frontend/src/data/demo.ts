export type Finding = { kind: 'flag' | 'caution' | 'unknown' | 'note'; title: string; detail: string; evidence?: string };
export type Product = {
  id: string; brand: string; name: string; category: string; icon: string; color: string;
  barcode: string; ingredients: string; advisory: string; sodium: number | null; basis: string; servingSize?: string;
  findings: Finding[]; sample: boolean;
};

// These deliberately invented records exist only to make the frontend flow reviewable.
export const demoProducts: Product[] = [
  {
    id: 'crackers-01', brand: 'Demo Pantry', name: 'Roasted Peanut Crackers', category: 'Biscuits & crackers', icon: '🥨', color: '#FFF0E2', barcode: '8901000000012',
    ingredients: 'Wheat flour, roasted peanuts (12%), rice bran oil, salt, spices.', advisory: 'Made in a facility that also processes tree nuts.', sodium: 640, basis: 'per 100 g', sample: true,
    findings: [
      { kind: 'flag', title: 'Peanut listed in ingredients', detail: 'Peanuts are one of your selected allergens. The label names roasted peanuts directly.', evidence: '“roasted peanuts (12%)”' },
      { kind: 'caution', title: 'Shared facility advisory', detail: 'The pack says tree nuts are handled at this facility. This is an advisory statement, separate from the ingredient list.', evidence: '“also processes tree nuts”' },
      { kind: 'note', title: 'Sodium information found', detail: '640 mg per 100 g is shown on this demo label. It has not been compared to a personal limit.', evidence: 'Demo value · 640 mg / 100 g' },
    ],
  },
  {
    id: 'crackers-02', brand: 'Demo Pantry', name: 'Jeera Millet Crackers', category: 'Biscuits & crackers', icon: '🍘', color: '#EDE9FF', barcode: '8901000000043',
    ingredients: 'Millet flour, rice flour, sunflower oil, cumin, salt.', advisory: 'No advisory statement in this sample record.', sodium: 390, basis: 'per 100 g', sample: true,
    findings: [{ kind: 'unknown', title: 'Label data is incomplete', detail: 'This sample has no independently verified allergen or facility information. It cannot be described as allergy-safe.' }],
  },
  {
    id: 'cereal-01', brand: 'Demo Pantry', name: 'Cocoa Oat Crunch', category: 'Breakfast cereals', icon: '🥣', color: '#E7F3FF',
    barcode: '8901000000029', ingredients: 'Oats, cocoa, cane sugar, sunflower oil.', advisory: 'May contain peanuts.', sodium: null, basis: 'Not supplied', sample: true,
    findings: [{ kind: 'caution', title: 'Possible peanut exposure', detail: 'The advisory names peanuts. An advisory is not proof that peanut is present.', evidence: '“May contain peanuts”' }, { kind: 'unknown', title: 'Sodium not supplied', detail: 'The sample record has no sodium value.' }],
  },
  {
    id: 'snack-01', brand: 'Demo Pantry', name: 'Baked Lentil Puffs', category: 'Savory packaged snacks', icon: '🫘', color: '#E9F8EF',
    barcode: '8901000000036', ingredients: 'Lentil flour, tapioca starch, sunflower oil, paprika.', advisory: 'Contains wheat.', sodium: 510, basis: 'per 100 g', sample: true,
    findings: [{ kind: 'unknown', title: 'Needs your label checked', detail: 'This record is illustrative. Confirm the physical pack and any omitted ingredients or advisories before assessing.' }],
  },
];

export const demoProfile = {
  name: 'Aarav', email: 'aarav@example.com', conditions: ['Food allergy'], allergens: ['Peanuts', 'Tree nuts'],
  limits: [{ name: 'Sodium', amount: 'Personal limit not set', note: 'No limit has been entered' }], preferences: ['Vegetarian'],
};

export const demoHistory = [
  { id: 'crackers-01', product: 'Roasted Peanut Crackers', date: 'Today · 10:42 AM', status: '2 findings', tone: 'red' as const, icon: '🥨', color: '#FFF0E2' },
  { id: 'cereal-01', product: 'Cocoa Oat Crunch', date: 'Yesterday · 6:18 PM', status: 'Needs checking', tone: 'amber' as const, icon: '🥣', color: '#E7F3FF' },
  { id: 'snack-01', product: 'Baked Lentil Puffs', date: 'Sep 22 · 4:05 PM', status: 'Review saved', tone: 'blue' as const, icon: '🫘', color: '#E9F8EF' },
];
