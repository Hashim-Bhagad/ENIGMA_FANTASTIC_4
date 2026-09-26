import type { FoodObservation, Nutrient } from '@/src/api/client';

export const nutrientFields: { key: Nutrient; label: string; unit: string }[] = [
  { key: 'sodium_mg', label: 'Sodium', unit: 'mg' },
  { key: 'potassium_mg', label: 'Potassium', unit: 'mg' },
  { key: 'phosphorus_mg', label: 'Phosphorus', unit: 'mg' },
  { key: 'carbohydrates_g', label: 'Carbohydrates', unit: 'g' },
  { key: 'protein_g', label: 'Protein', unit: 'g' },
  { key: 'fat_g', label: 'Total fat', unit: 'g' },
  { key: 'saturated_fat_g', label: 'Saturated fat', unit: 'g' },
  { key: 'sugars_g', label: 'Sugars', unit: 'g' },
  { key: 'fiber_g', label: 'Fibre', unit: 'g' },
  { key: 'energy_kcal', label: 'Energy', unit: 'kcal' },
];

export function nutrientInputs(food?: FoodObservation): Record<Nutrient, string> {
  return Object.fromEntries(nutrientFields.map(({ key }) => [key, food?.nutrients[key] == null ? '' : String(food.nutrients[key])])) as Record<Nutrient, string>;
}
