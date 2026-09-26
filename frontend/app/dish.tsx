import React, { useEffect, useState } from 'react';
import { Linking, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Button, Card, Field, PageHeader, Pill, Screen, SectionTitle } from '@/src/components/ui';
import { FindingsList, findingCount, statusTone } from '@/src/components/findings';
import { api, type DishOptions, type Recipe, type ReferenceFood } from '@/src/api/client';
import { useApp, type DishIngredientDraft } from '@/src/state/AppContext';
import { nutrientFields } from '@/src/data/nutrients';
import { colors } from '@/src/theme';

let nextRow = 1;
const ingredientRow = (text = ''): DishIngredientDraft => ({ key: `ingredient-${Date.now()}-${nextRow++}`, text, referenceCode: null, grams: '' });

export default function DishScreen() {
  const { token, profile, dishDraft, setDishDraft, assessDish, busyFor, clearError, error, dishResult, clearDish } = useApp();
  const [mode, setMode] = useState<'home' | 'restaurant'>('home');
  const [query, setQuery] = useState('');
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [catalogNote, setCatalogNote] = useState('');
  const [recipeBusy, setRecipeBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [suggestions, setSuggestions] = useState<Record<string, ReferenceFood[]>>({});
  const [referenceBusy, setReferenceBusy] = useState<string | null>(null);
  const [options, setOptions] = useState<DishOptions | null>(null);
  const [optionsError, setOptionsError] = useState('');
  useEffect(() => {
    if (!token) return;
    let active = true;
    api.dishesOptions(token)
      .then(value => { if (active) { setOptions(value); setOptionsError(''); } })
      .catch(cause => { if (active) setOptionsError(cause instanceof Error ? cause.message : 'Preparation options could not be loaded.'); });
    return () => { active = false; };
  }, [token]);

  const searchRecipes = async (term: string) => {
    if (!token) return;
    setRecipeBusy(true); setMessage('');
    try { const page = await api.recipes(token, term.trim()); setRecipes(page.recipes); setCatalogNote(page.message || 'Recipe ingredients are a starting point. Confirm your preparation.'); }
    catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Could not load recipe templates.'); }
    finally { setRecipeBusy(false); }
  };
  useEffect(() => { void searchRecipes(''); }, [token]);
  const updateRow = (key: string, changes: Partial<DishIngredientDraft>) => {
    setDishDraft({ ...dishDraft, declarationsConfirmed: false, ingredients: dishDraft.ingredients.map(row => row.key === key ? { ...row, ...changes } : row) });
    if ('text' in changes) setSuggestions(current => ({ ...current, [key]: [] }));
  };
  const selectRecipe = (item: Recipe) => {
    setRecipe(item); setSuggestions({});
    setDishDraft({ ...dishDraft, name: item.name, ingredients: item.ingredients.map(ingredient => ({ ...ingredientRow(ingredient.text), referenceCode: ingredient.reference_code || null, grams: ingredient.grams == null ? '' : String(ingredient.grams) })), declarationsConfirmed: false });
  };
  const findReference = async (row: DishIngredientDraft) => {
    if (!token || !row.text.trim()) return;
    setReferenceBusy(row.key); setMessage('');
    try { const result = await api.referenceFoods(token, row.text.trim()); setSuggestions(current => ({ ...current, [row.key]: result.foods })); if (!result.foods.length) setMessage('No IFCT reference matched this search. The typed ingredient can still be checked.'); }
    catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Reference search failed.'); }
    finally { setReferenceBusy(null); }
  };
  const submit = async () => {
    clearError(); setMessage('');
    try { await assessDish(); }
    catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Meal assessment failed.'); }
  };
  const chooseMode = (value: 'home' | 'restaurant') => {
    setMode(value);
    setDishDraft({ ...dishDraft, declarationsConfirmed: false, cookingNotes: [...dishDraft.cookingNotes.filter(note => note !== 'restaurant_prepared'), ...(value === 'restaurant' ? ['restaurant_prepared'] : [])] });
  };

  return <Screen>
    <PageHeader eyebrow="Meal check" title="What goes into your meal?" subtitle="Start from a recipe or enter ingredients. Make the check reflect the food you plan to eat." back />
    <View style={s.modes}>{(['home', 'restaurant'] as const).map(value => <Pressable key={value} accessibilityRole="button" accessibilityState={{ selected: mode === value }} onPress={() => chooseMode(value)} style={[s.mode, mode === value && s.modeActive]}><MaterialCommunityIcons name={value === 'home' ? 'home-outline' : 'silverware-fork-knife'} size={20} color={mode === value ? colors.primary : colors.muted} /><Text style={[s.modeText, mode === value && { color: colors.primary }]}>{value === 'home' ? 'Cooking at home' : 'Eating out'}</Text></Pressable>)}</View>
    <Card style={s.intro}><Text style={s.title}>{mode === 'home' ? 'Check your recipe before cooking' : 'Prepare questions for the kitchen'}</Text><Text style={s.copy}>{mode === 'home' ? 'Adjust the ingredient list, including sauces, oil, salt, toppings and additions. Matches show what conflicts with your saved restrictions.' : 'A recipe describes one version of a dish. Ask the cook to confirm ingredients and request changes before treating it as your actual meal.'}</Text></Card>
    <SectionTitle title="Start from a recipe" />
    <View style={s.search}><MaterialCommunityIcons name="magnify" size={22} color={colors.muted} /><TextInput accessibilityLabel="Search recipe catalogue" value={query} onChangeText={setQuery} onSubmitEditing={() => void searchRecipes(query)} placeholder="Search Food.com recipe templates" placeholderTextColor={colors.subtle} style={s.searchInput} returnKeyType="search" /><Pressable accessibilityRole="button" accessibilityLabel="Search recipes" disabled={recipeBusy} onPress={() => void searchRecipes(query)} style={s.iconButton}><MaterialCommunityIcons name="arrow-right" size={22} color={colors.primary} /></Pressable></View>
    {recipeBusy ? <Text style={s.copy}>Loading recipe templates…</Text> : recipes.length ? recipes.map(item => <Pressable key={item.id} accessibilityRole="button" accessibilityLabel={`Use recipe ${item.name}`} onPress={() => selectRecipe(item)}><Card style={s.recipeRow}><View style={{ flex: 1, gap: 6 }}><Text style={s.title}>{item.name}</Text><Text style={s.copy}>{item.ingredients.length} ingredients · recipe reference</Text></View><MaterialCommunityIcons name="plus-circle-outline" size={24} color={colors.primary} /></Card></Pressable>) : <Card><Text style={s.title}>No recipe templates available for this search</Text><Text style={s.copy}>You can check your own ingredient list below. IFCT provides ingredient references; it does not contain complete recipes.</Text></Card>}
    {catalogNote ? <Text style={s.meta}>{catalogNote}</Text> : null}
    {recipe ? <Card style={{ gap: 8 }}><Pill label="Recipe template selected" tone="blue" /><Text style={s.title}>{recipe.name}</Text>{recipe.warnings.map((warning, index) => <Text key={index} style={s.copy}>{warning}</Text>)}{typeof recipe.source.reference === 'string' && /^https?:\/\//.test(recipe.source.reference) ? <Pressable accessibilityRole="link" onPress={() => void Linking.openURL(String(recipe.source.reference))} style={s.iconButton}><Text style={s.link}>Open recipe source ↗</Text></Pressable> : null}</Card> : null}
    <SectionTitle title="Your actual ingredients" action={`${dishDraft.ingredients.length}/40`} />
    <Field label="Meal name" value={dishDraft.name} onChangeText={name => setDishDraft({ ...dishDraft, name })} placeholder="e.g. My paneer curry" />
    {dishDraft.ingredients.map((row, index) => <Card key={row.key} style={{ gap: 12 }}>
      <View style={s.row}><Text style={s.number}>{String(index + 1).padStart(2, '0')}</Text><View style={{ flex: 1 }}><Field label={`Ingredient ${index + 1}`} value={row.text} onChangeText={text => updateRow(row.key, { text, referenceCode: null })} placeholder="Ingredient, including subingredients" /></View>{dishDraft.ingredients.length > 1 ? <Pressable accessibilityRole="button" accessibilityLabel={`Remove ingredient ${index + 1}`} onPress={() => setDishDraft({ ...dishDraft, declarationsConfirmed: false, ingredients: dishDraft.ingredients.filter(item => item.key !== row.key) })} style={s.iconButton}><MaterialCommunityIcons name="close" size={22} color={colors.muted} /></Pressable> : null}</View>
      <View style={s.row}><View style={{ flex: 1 }}><Field label="Amount in recipe (g, optional)" value={row.grams} onChangeText={grams => updateRow(row.key, { grams })} placeholder="Leave blank if unknown" keyboardType="numeric" /></View><Button title="Find in IFCT" secondary compact loading={referenceBusy === row.key} disabled={!row.text.trim()} onPress={() => void findReference(row)} /></View>
      {row.referenceCode ? <Pill label={`Reference selected: ${row.referenceCode}`} tone="blue" /> : null}
      {(suggestions[row.key] || []).map(food => <Pressable key={food.code} accessibilityRole="button" accessibilityLabel={`Choose IFCT reference ${food.name}`} onPress={() => { updateRow(row.key, { referenceCode: food.code }); setSuggestions(current => ({ ...current, [row.key]: [] })); }} style={s.suggestion}><Text style={s.link}>{food.name} · {food.code}</Text><Text style={s.meta}>Reference match only; your typed ingredient wording is retained.</Text></Pressable>)}
    </Card>)}
    <Button title="Add an ingredient or topping" icon="plus" secondary disabled={dishDraft.ingredients.length >= 40} onPress={() => setDishDraft({ ...dishDraft, declarationsConfirmed: false, ingredients: [...dishDraft.ingredients, ingredientRow()] })} />
    <Text style={s.meta}>IFCT matches are optional. Raw ingredient composition does not establish cooked-meal nutrients or replace a package label.</Text>
    <SectionTitle title="Preparation & unknowns" />
    <View style={s.chips}>{(options?.cooking_notes || []).map(note => { const selected = dishDraft.cookingNotes.includes(note.code); return <Pressable key={note.code} accessibilityRole="checkbox" accessibilityState={{ checked: selected }} accessibilityHint={note.detail} onPress={() => setDishDraft({ ...dishDraft, cookingNotes: selected ? dishDraft.cookingNotes.filter(item => item !== note.code) : [...dishDraft.cookingNotes, note.code] })} style={[s.chip, selected && s.chipActive]}><Text style={[s.copy, selected && { color: colors.primaryDark }]}>{note.label}</Text></Pressable>; })}</View>
    {optionsError ? <Text accessibilityRole="alert" style={s.error}>{optionsError}</Text> : null}
    {options ? <Card style={{ gap: 8 }}><Text style={s.meta}>Preparation details this check cannot see:</Text>{options.unknowns.map(item => <Text key={item} style={s.meta}>· {item}</Text>)}{options.assumptions.map(item => <Text key={item} style={s.meta}>· {item}</Text>)}</Card> : null}
    <Pressable accessibilityRole="checkbox" accessibilityState={{ checked: dishDraft.declarationsConfirmed }} onPress={() => setDishDraft({ ...dishDraft, declarationsConfirmed: !dishDraft.declarationsConfirmed })} style={s.confirm}><MaterialCommunityIcons name={dishDraft.declarationsConfirmed ? 'checkbox-marked' : 'checkbox-blank-outline'} color={colors.primary} size={25} /><Text style={[s.copy, { flex: 1 }]}>The cook has confirmed the full ingredient list, including sauces, mixes and toppings.</Text></Pressable>
    <Text style={s.meta}>Ingredient confirmation does not confirm shared-equipment or cross-contact details. Those remain questions for the cook.</Text>
    <Field label="Your serving (g, optional)" value={dishDraft.portion} onChangeText={portion => setDishDraft({ ...dishDraft, portion })} placeholder="Leave blank if unknown" keyboardType="numeric" />
    {message || error ? <Text accessibilityRole="alert" style={s.error}>{message || error}</Text> : null}
    <Button title={mode === 'home' ? 'Check ingredients before cooking' : 'Find concerns & questions to ask'} icon="arrow-right" loading={busyFor('dish')} disabled={!profile || !dishDraft.name.trim() || !dishDraft.ingredients.some(row => row.text.trim())} onPress={() => void submit()} />
    {dishResult ? <>
      <SectionTitle title="Meal check result" action={`${findingCount(dishResult.assessment)} items`} />
      <Card style={{ gap: 10 }}>
        <View style={s.row}><Text style={[s.title, { flex: 1 }]}>{dishResult.dish.name}</Text><Pill label={dishResult.assessment.status.replaceAll('_', ' ').toUpperCase()} tone={statusTone(dishResult.assessment.status)} /></View>
        <Text style={s.copy}>{dishResult.assessment.status_reason}</Text>
        <Text style={s.meta}>{dishResult.dish.matches.length} ingredient(s) matched to IFCT references · {dishResult.dish.unmatched.length} unmatched</Text>
        {dishResult.dish.matches.map(match => <Text key={`${match.input_text}-${match.code}`} selectable style={s.meta}>{match.input_text} → {match.name} ({match.code}){match.grams == null ? ', amount unknown' : `, ${match.grams} g`} · matched by {match.matched_by}</Text>)}
        {dishResult.dish.unmatched.map(item => <Text key={item.input_text} selectable style={s.meta}>{item.input_text} → not matched: {item.reason}</Text>)}
        {dishResult.dish.estimate.available
          ? <><Text style={s.meta}>Estimated per 100 g from reference composition ({dishResult.dish.estimate.total_grams} g total as entered):</Text>{nutrientFields.filter(field => dishResult.dish.estimate.nutrients[field.key] != null).map(field => <Text key={field.key} style={s.meta}>{field.label}: {dishResult.dish.estimate.nutrients[field.key]} {field.unit}</Text>)}</>
          : <Text style={s.meta}>No nutrient estimate: every ingredient needs a matched reference and a weight in grams. The ingredient-name checks still apply.</Text>}
        {dishResult.dish.estimate.assumptions.map((assumption, index) => <Text key={`assumption-${index}`} style={s.meta}>· {assumption}</Text>)}
      </Card>
      <FindingsList result={dishResult.assessment} />
      <Button title="Clear this meal check" icon="close-circle-outline" secondary onPress={() => { clearDish(); setMessage(''); }} />
    </> : null}
  </Screen>;
}
const s = StyleSheet.create({
  modes: { flexDirection: 'row', gap: 10 }, mode: { flex: 1, minHeight: 58, borderRadius: 16, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center', gap: 5, borderWidth: 1, borderColor: colors.line }, modeActive: { borderColor: colors.primary, backgroundColor: colors.lavender }, modeText: { fontSize: 13, fontWeight: '700', color: colors.muted },
  intro: { gap: 8, backgroundColor: colors.lavenderSoft }, title: { fontSize: 16, lineHeight: 23, fontWeight: '800', color: colors.ink }, copy: { fontSize: 14, lineHeight: 21, color: colors.muted }, meta: { fontSize: 12, lineHeight: 19, color: colors.muted },
  search: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingLeft: 14, backgroundColor: colors.surface, borderRadius: 16, borderWidth: 1, borderColor: colors.line }, searchInput: { flex: 1, minHeight: 54, color: colors.ink, fontSize: 14 }, iconButton: { minWidth: 44, minHeight: 44, alignItems: 'center', justifyContent: 'center' },
  recipeRow: { flexDirection: 'row', alignItems: 'center', gap: 12 }, row: { flexDirection: 'row', alignItems: 'center', gap: 10 }, number: { fontSize: 14, color: colors.primary, fontWeight: '800' }, link: { fontSize: 14, lineHeight: 20, color: colors.primaryDark, fontWeight: '700' }, suggestion: { padding: 12, borderRadius: 12, backgroundColor: colors.canvas, gap: 5 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 }, chip: { paddingHorizontal: 12, paddingVertical: 12, borderRadius: 14, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line }, chipActive: { backgroundColor: colors.lavender, borderColor: colors.primary }, confirm: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, backgroundColor: colors.surface, borderRadius: 16, padding: 16 }, error: { fontSize: 14, lineHeight: 21, color: colors.red },
});
