import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Linking, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Button, Card, Field, PageHeader, Pill, Screen, SectionTitle } from '@/src/components/ui';
import { FindingsList, findingCount, statusTone } from '@/src/components/findings';
import { api, dishStatusExplanation, REFERENCE_MATCH_NOTE, referenceSuggestionLabel, TYPE_AHEAD_DELAY_MS, typeAheadTerm, type DishOptions, type Recipe, type ReferenceFood } from '@/src/api/client';
import { useApp, type DishDraft, type DishIngredientDraft } from '@/src/state/AppContext';
import { nutrientFields } from '@/src/data/nutrients';
import { colors, radius } from '@/src/theme';

/** Suggestions shown under one field; the backend already ranked them most-relevant first. */
const SUGGESTION_LIMIT = 6;
const HOW_THIS_WORKS = 'Ingredients you type → amounts in grams where you know them → how it is prepared → the result, which lists matches, unmatched ingredients, an estimate when the numbers allow, and anything that conflicts with your saved restrictions.';

let nextRow = 1;
const ingredientRow = (text = ''): DishIngredientDraft => ({ key: `ingredient-${Date.now()}-${nextRow++}`, text, referenceCode: null, grams: '' });

/** Text that only settles after a pause, so a type-ahead asks the server once the typist stops. */
function useDebouncedValue<T>(value: T, delay: number): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delay);
    return () => clearTimeout(timer);
  }, [delay, value]);
  return settled;
}

/** Everything that changes what a meal check means; compared against the checked draft. */
function draftSignature(draft: DishDraft): string {
  return JSON.stringify({
    name: draft.name.trim(), portion: draft.portion.trim(), confirmed: draft.declarationsConfirmed,
    notes: [...draft.cookingNotes].sort(), ingredients: draft.ingredients.map(row => [row.text.trim(), row.referenceCode, row.grams.trim()]),
  });
}

/**
 * One ingredient line with its own debounced type-ahead. Suggestions come from the ranked
 * reference search; a response that arrives after the query changed is discarded rather than shown.
 */
function IngredientRow({ index, row, token, removable, onChange, onRemove }: {
  index: number; row: DishIngredientDraft; token: string | null; removable: boolean;
  onChange: (changes: Partial<DishIngredientDraft>) => void; onRemove: () => void;
}) {
  const [suggestions, setSuggestions] = useState<ReferenceFood[]>([]);
  const [checking, setChecking] = useState(false);
  const [note, setNote] = useState('');
  const [noteError, setNoteError] = useState('');
  const [dismissedTerm, setDismissedTerm] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const term = typeAheadTerm(useDebouncedValue(row.text, TYPE_AHEAD_DELAY_MS));

  useEffect(() => {
    if (!token || !term || term === dismissedTerm) { setSuggestions([]); setChecking(false); setNote(''); setNoteError(''); return; }
    let active = true;
    setChecking(true); setNote(''); setNoteError('');
    api.referenceFoods(token, term, SUGGESTION_LIMIT)
      .then(result => {
        if (!active) return;
        setSuggestions(result.foods);
        if (!result.foods.length) setNote(`No IFCT reference matches “${term}”. Your wording is still checked as typed.`);
      })
      .catch(cause => { if (active) { setSuggestions([]); setNoteError(cause instanceof Error ? cause.message : 'Reference search failed.'); } })
      .finally(() => { if (active) setChecking(false); });
    return () => { active = false; };
  }, [dismissedTerm, retry, term, token]);

  const choose = (food: ReferenceFood) => { onChange({ referenceCode: food.code }); setDismissedTerm(term); };

  return <Card style={st.rowCard}>
    <View style={st.row}>
      <Text style={st.number}>{String(index + 1).padStart(2, '0')}</Text>
      <View style={{ flex: 1 }}>
        <Field
          label={`Ingredient ${index + 1}`}
          value={row.text}
          onChangeText={text => onChange({ text })}
          placeholder="Ingredient, including sauces and toppings"
          autoCorrect={false}
          returnKeyType="search"
          onSubmitEditing={() => { if (suggestions[0]) choose(suggestions[0]); }}
          hint={<>
            {checking ? <Text style={st.searching}>Checking reference foods…</Text> : null}
            {suggestions.length ? <>
              <View style={st.suggestions}>{suggestions.map(food => <Pressable key={food.code} accessibilityRole="button" accessibilityLabel={`Use reference ${food.name}, code ${food.code}`} onPress={() => choose(food)} style={({ pressed }) => [st.suggestion, pressed && { opacity: 0.85 }]}>
                <MaterialCommunityIcons name="food-variant" size={16} color={colors.primary} />
                <Text style={st.suggestionText}>{referenceSuggestionLabel(food)}</Text>
              </Pressable>)}</View>
              <Text style={st.note}>{REFERENCE_MATCH_NOTE} Press enter to take the first one.</Text>
            </> : null}
            {note ? <Text style={st.note}>{note}</Text> : null}
            {noteError ? <View style={st.noteRow}><Text accessibilityRole="alert" style={st.error}>{noteError}</Text><Pressable accessibilityRole="button" accessibilityLabel="Try the reference search again" onPress={() => setRetry(value => value + 1)}><Text style={st.link}>Try again</Text></Pressable></View> : null}
          </>}
        />
      </View>
      {removable ? <Pressable accessibilityRole="button" accessibilityLabel={`Remove ingredient ${index + 1}`} onPress={onRemove} style={st.iconButton}><MaterialCommunityIcons name="close" size={22} color={colors.muted} /></Pressable> : null}
    </View>
    <View style={st.row}>
      <View style={{ flex: 1 }}><Field label="Amount in recipe (g, optional)" value={row.grams} onChangeText={grams => onChange({ grams })} placeholder="Leave blank if unknown" keyboardType="numeric" /></View>
    </View>
    {row.referenceCode ? <View style={st.selected}><Pill label={`Reference: ${row.referenceCode}`} tone="blue" /><Pressable accessibilityRole="button" accessibilityLabel="Clear the selected reference" onPress={() => onChange({ referenceCode: null })}><Text style={st.link}>Clear</Text></Pressable></View> : null}
  </Card>;
}

export default function DishScreen() {
  const { token, profile, dishDraft, setDishDraft, assessDish, busyFor, clearError, error, dishResult, clearDish } = useApp();
  const [mode, setMode] = useState<'home' | 'restaurant'>('home');
  const [query, setQuery] = useState('');
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [recipeNote, setRecipeNote] = useState('');
  const [recipeBusy, setRecipeBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [options, setOptions] = useState<DishOptions | null>(null);
  const [optionsError, setOptionsError] = useState('');
  /** The draft the visible result was produced from, so a changed meal is never shown as checked. */
  const [checked, setChecked] = useState<{ signature: string; declarationsConfirmed: boolean } | null>(null);
  const recipeRequest = useRef(0);
  const debouncedQuery = useDebouncedValue(query, TYPE_AHEAD_DELAY_MS);

  useEffect(() => {
    if (!token) return;
    let active = true;
    api.dishesOptions(token)
      .then(value => { if (active) { setOptions(value); setOptionsError(''); } })
      .catch(cause => { if (active) setOptionsError(cause instanceof Error ? cause.message : 'Preparation options could not be loaded.'); });
    return () => { active = false; };
  }, [token]);

  const searchRecipes = useCallback(async (term: string) => {
    if (!token) return;
    const request = ++recipeRequest.current;
    setRecipeBusy(true);
    try {
      const page = await api.recipes(token, term);
      // A slower earlier search never overwrites the list for the term on screen.
      if (recipeRequest.current !== request) return;
      setRecipes(page.recipes); setRecipeNote(page.message || '');
    } catch (cause) {
      if (recipeRequest.current === request) { setRecipes([]); setMessage(cause instanceof Error ? cause.message : 'Could not load recipe templates.'); }
    } finally {
      if (recipeRequest.current === request) setRecipeBusy(false);
    }
  }, [token]);
  useEffect(() => { void searchRecipes(debouncedQuery); }, [debouncedQuery, searchRecipes]);

  const updateRow = (key: string, changes: Partial<DishIngredientDraft>) => {
    // Editing the wording changes the list, so the earlier confirmation no longer covers it.
    // Choosing a reference or recording a weight leaves the confirmed list intact.
    const wordingChanged = 'text' in changes;
    setDishDraft({
      ...dishDraft,
      declarationsConfirmed: wordingChanged ? false : dishDraft.declarationsConfirmed,
      ingredients: dishDraft.ingredients.map(row => row.key === key ? { ...row, ...changes, ...(wordingChanged ? { referenceCode: null } : {}) } : row),
    });
  };
  const selectRecipe = (item: Recipe) => {
    setRecipe(item);
    setDishDraft({ ...dishDraft, name: item.name, ingredients: item.ingredients.map(ingredient => ({ ...ingredientRow(ingredient.text), referenceCode: ingredient.reference_code || null, grams: ingredient.grams == null ? '' : String(ingredient.grams) })), declarationsConfirmed: false });
  };
  const submit = async () => {
    clearError(); setMessage('');
    const signature = draftSignature(dishDraft);
    const declarationsConfirmed = dishDraft.declarationsConfirmed;
    try { await assessDish(); setChecked({ signature, declarationsConfirmed }); }
    catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Meal assessment failed.'); }
  };
  const chooseMode = (value: 'home' | 'restaurant') => {
    setMode(value);
    setDishDraft({ ...dishDraft, declarationsConfirmed: false, cookingNotes: [...dishDraft.cookingNotes.filter(note => note !== 'restaurant_prepared'), ...(value === 'restaurant' ? ['restaurant_prepared'] : [])] });
  };

  const typedIngredients = dishDraft.ingredients.filter(row => row.text.trim()).length;
  const resultOutOfDate = Boolean(dishResult && checked && checked.signature !== draftSignature(dishDraft));
  const resultConfirmable = Boolean(dishResult && checked);

  return <Screen>
    <PageHeader eyebrow="Meal check" title="What goes into your meal?" subtitle="Start from a recipe or enter ingredients. Make the check reflect the food you plan to eat." back />
    <View style={st.modes}>{(['home', 'restaurant'] as const).map(value => <Pressable key={value} accessibilityRole="button" accessibilityState={{ selected: mode === value }} onPress={() => chooseMode(value)} style={[st.mode, mode === value && st.modeActive]}><MaterialCommunityIcons name={value === 'home' ? 'home-outline' : 'silverware-fork-knife'} size={20} color={mode === value ? colors.primary : colors.muted} /><Text style={[st.modeText, mode === value && { color: colors.primary }]}>{value === 'home' ? 'Cooking at home' : 'Eating out'}</Text></Pressable>)}</View>
    <Card style={st.intro}><Text style={st.title}>{mode === 'home' ? 'Check your recipe before cooking' : 'Prepare questions for the kitchen'}</Text><Text style={st.copy}>{mode === 'home' ? 'Adjust the ingredient list, including sauces, oil, salt, toppings and additions. Matches show what conflicts with your saved restrictions.' : 'A recipe describes one version of a dish. Ask the cook to confirm ingredients and request changes before treating it as your actual meal.'}</Text><Text style={st.meta}>How this check works: {HOW_THIS_WORKS}</Text></Card>

    <SectionTitle title="Start from a recipe" action={recipe ? 'Template selected' : undefined} />
    <View style={st.search}><MaterialCommunityIcons name="magnify" size={22} color={colors.muted} /><TextInput accessibilityLabel="Search recipe catalogue" value={query} onChangeText={setQuery} placeholder="Search Food.com recipe templates" placeholderTextColor={colors.subtle} style={st.searchInput} returnKeyType="search" autoCorrect={false} /><Pressable accessibilityRole="button" accessibilityLabel="Search recipes now" disabled={recipeBusy} onPress={() => void searchRecipes(query.trim())} style={st.iconButton}><MaterialCommunityIcons name="arrow-right" size={22} color={colors.primary} /></Pressable></View>
    <Text style={st.note}>{typedIngredients ? 'Recipe template names are searched as you type.' : 'Type at least two characters and template names appear here as you type.'}</Text>
    {recipeBusy ? <Text style={st.meta}>Searching recipe templates…</Text> : null}
    {recipes.length
      ? recipes.map(item => <Pressable key={item.id} accessibilityRole="button" accessibilityLabel={`Use recipe ${item.name}`} onPress={() => selectRecipe(item)}><Card style={st.recipeRow}><View style={{ flex: 1, gap: 6 }}><Text style={st.title}>{item.name}</Text><Text style={st.copy}>{item.ingredients.length} ingredients · recipe reference</Text></View><MaterialCommunityIcons name="plus-circle-outline" size={24} color={colors.primary} /></Card></Pressable>)
      : !recipeBusy ? <Card style={st.empty}><MaterialCommunityIcons name="book-search-outline" size={26} color={colors.subtle} /><Text style={st.title}>{recipeNote || 'No recipe templates match this search.'}</Text><Text style={st.copy}>You can check your own ingredient list below. IFCT provides ingredient references; it does not contain complete recipes.</Text></Card> : null}
    {recipes.length && recipeNote ? <Text style={st.meta}>{recipeNote}</Text> : null}
    {recipe ? <Card style={{ gap: 8 }}><Pill label="Recipe template selected" tone="blue" /><Text style={st.title}>{recipe.name}</Text>{recipe.warnings.map((warning, index) => <Text key={index} style={st.copy}>{warning}</Text>)}{typeof recipe.source.reference === 'string' && /^https?:\/\//.test(recipe.source.reference) ? <Pressable accessibilityRole="link" onPress={() => void Linking.openURL(String(recipe.source.reference))} style={st.iconButton}><Text style={st.link}>Open recipe source ↗</Text></Pressable> : null}</Card> : null}

    <SectionTitle title="Your actual ingredients" action={`${dishDraft.ingredients.length}/40`} />
    <Field label="Meal name" value={dishDraft.name} onChangeText={name => setDishDraft({ ...dishDraft, name })} placeholder="e.g. My paneer curry" />
    {!typedIngredients && !recipe ? <Card style={st.empty}><MaterialCommunityIcons name="silverware-variant" size={26} color={colors.subtle} /><Text style={st.title}>Nothing typed yet</Text><Text style={st.copy}>Add the first ingredient below, or start from a recipe template above. Suggestions appear under the field as you type; nothing is checked until you press the button at the bottom.</Text><Text style={st.meta}>{HOW_THIS_WORKS}</Text></Card> : null}
    {dishDraft.ingredients.map((row, index) => <IngredientRow key={row.key} index={index} row={row} token={token} removable={dishDraft.ingredients.length > 1} onChange={changes => updateRow(row.key, changes)} onRemove={() => setDishDraft({ ...dishDraft, declarationsConfirmed: false, ingredients: dishDraft.ingredients.filter(item => item.key !== row.key) })} />)}
    <Button title="Add an ingredient or topping" icon="plus" secondary disabled={dishDraft.ingredients.length >= 40} onPress={() => setDishDraft({ ...dishDraft, declarationsConfirmed: false, ingredients: [...dishDraft.ingredients, ingredientRow()] })} />
    <Text style={st.meta}>IFCT matches are optional. Raw ingredient composition does not establish cooked-meal nutrients or replace a package label.</Text>

    <SectionTitle title="Preparation & unknowns" />
    <View style={st.chips}>{(options?.cooking_notes || []).map(note => { const selected = dishDraft.cookingNotes.includes(note.code); return <Pressable key={note.code} accessibilityRole="checkbox" accessibilityState={{ checked: selected }} accessibilityHint={note.detail} onPress={() => setDishDraft({ ...dishDraft, cookingNotes: selected ? dishDraft.cookingNotes.filter(item => item !== note.code) : [...dishDraft.cookingNotes, note.code] })} style={[st.chip, selected && st.chipActive]}><Text style={[st.copy, selected && { color: colors.primaryDark }]}>{note.label}</Text></Pressable>; })}</View>
    {optionsError ? <Text accessibilityRole="alert" style={st.error}>{optionsError}</Text> : null}
    {options ? <Card style={{ gap: 8 }}><Text style={st.meta}>Preparation details this check cannot see:</Text>{options.unknowns.map(item => <Text key={item} style={st.meta}>· {item}</Text>)}{options.assumptions.map(item => <Text key={item} style={st.meta}>· {item}</Text>)}</Card> : null}

    <SectionTitle title="Before you run the check" />
    <Card style={[st.confirm, dishDraft.declarationsConfirmed && st.confirmOn]}>
      <Pressable accessibilityRole="checkbox" accessibilityState={{ checked: dishDraft.declarationsConfirmed }} accessibilityLabel="Confirm the cook listed every ingredient" onPress={() => setDishDraft({ ...dishDraft, declarationsConfirmed: !dishDraft.declarationsConfirmed })} style={st.confirmRow}>
        <MaterialCommunityIcons name={dishDraft.declarationsConfirmed ? 'checkbox-marked' : 'checkbox-blank-outline'} color={colors.primary} size={28} />
        <View style={{ flex: 1 }}><Text style={st.confirmTitle}>The cook confirmed the full ingredient list</Text><Text style={st.copy}>Include sauces, mixes, oil, salt and toppings. This is what lets the check treat the declarations as complete.</Text></View>
      </Pressable>
      <Text style={st.confirmState}>{dishDraft.declarationsConfirmed ? 'Confirmed. The checks can reach a conclusion about the declarations you listed.' : 'Not confirmed. With this unticked, missing or incomplete declarations stay unknown and the checks stay inconclusive.'}</Text>
      <Text style={st.meta}>Ingredient confirmation does not confirm shared-equipment or cross-contact details. Those remain questions for the cook.</Text>
    </Card>
    <Field label="Your serving (g, optional)" value={dishDraft.portion} onChangeText={portion => setDishDraft({ ...dishDraft, portion })} placeholder="Leave blank if unknown" keyboardType="numeric" />

    {message || error ? <Text accessibilityRole="alert" style={st.error}>{message || error}</Text> : null}
    <Button title={mode === 'home' ? 'Check ingredients before cooking' : 'Find concerns & questions to ask'} icon="arrow-right" loading={busyFor('dish')} disabled={!profile || !dishDraft.name.trim() || !typedIngredients} onPress={() => void submit()} />

    {dishResult ? <>
      <SectionTitle title="Meal check result" action={`${findingCount(dishResult.assessment)} items`} />
      {resultOutOfDate ? <Card style={st.notice}><MaterialCommunityIcons name="alert-outline" size={17} color={colors.amber} /><Text style={st.noticeText}>This meal changed after the check ran. The result below describes the earlier list — press the check button again to update it.</Text></Card> : null}
      <Card style={{ gap: 10 }}>
        <View style={st.row}><Text style={[st.title, { flex: 1 }]}>{dishResult.dish.name}</Text><Pill label={dishResult.assessment.status.replaceAll('_', ' ').toUpperCase()} tone={statusTone(dishResult.assessment.status)} /></View>
        <Text style={st.copy}>{dishStatusExplanation(dishResult.assessment.status)}</Text>
        <Text style={st.meta}>{dishResult.assessment.status_reason}</Text>
        {resultConfirmable ? <Text style={st.meta}>{checked?.declarationsConfirmed ? 'You confirmed the cook listed the full ingredient list, so these checks treat the declarations as complete.' : 'The ingredient list was not confirmed as complete, so anything unlisted stays unknown and the checks remain inconclusive.'}</Text> : null}
        <View style={st.block}>
          <Text style={st.blockTitle}>Matched to a reference ({dishResult.dish.matches.length})</Text>
          {dishResult.dish.matches.length
            ? dishResult.dish.matches.map(match => <Text key={`${match.input_text}-${match.code}`} selectable style={st.meta}>{match.input_text} → {match.name} ({match.code}){match.grams == null ? ', amount unknown' : `, ${match.grams} g`} · matched by {match.matched_by}</Text>)
            : <Text style={st.meta}>No typed ingredient matched an IFCT reference. The ingredient-name checks still run.</Text>}
        </View>
        <View style={st.block}>
          <Text style={st.blockTitle}>Not matched ({dishResult.dish.unmatched.length})</Text>
          {dishResult.dish.unmatched.length
            ? dishResult.dish.unmatched.map(item => <Text key={item.input_text} selectable style={st.meta}>{item.input_text} → not matched: {item.reason}</Text>)
            : <Text style={st.meta}>Every typed ingredient matched a reference.</Text>}
        </View>
        <View style={st.block}>
          <Text style={st.blockTitle}>Estimate</Text>
          {dishResult.dish.estimate.available
            ? <><Text style={st.meta}>Estimated per 100 g of this meal{dishResult.dish.estimate.total_grams == null ? '' : `, from the ${dishResult.dish.estimate.total_grams} g entered in total`}:</Text>{nutrientFields.filter(field => dishResult.dish.estimate.nutrients[field.key] != null).map(field => <Text key={field.key} style={st.meta}>{field.label}: {dishResult.dish.estimate.nutrients[field.key]} {field.unit}</Text>)}</>
            : <Text style={st.meta}>No nutrient estimate: every ingredient needs a matched reference and a weight in grams. The ingredient-name checks still apply.</Text>}
          {dishResult.dish.estimate.assumptions.map((assumption, index) => <Text key={`assumption-${index}`} style={st.meta}>· {assumption}</Text>)}
        </View>
      </Card>
      <FindingsList result={dishResult.assessment} />
      <Button title="Clear this meal check" icon="close-circle-outline" secondary onPress={() => { clearDish(); setChecked(null); setMessage(''); }} />
    </> : null}
  </Screen>;
}

const st = StyleSheet.create({
  modes: { flexDirection: 'row', gap: 10 }, mode: { flex: 1, minHeight: 58, borderRadius: 16, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center', gap: 5, borderWidth: 1, borderColor: colors.line }, modeActive: { borderColor: colors.primary, backgroundColor: colors.lavender }, modeText: { fontSize: 13, fontWeight: '700', color: colors.muted },
  intro: { gap: 8, backgroundColor: colors.lavenderSoft }, title: { fontSize: 16, lineHeight: 23, fontWeight: '800', color: colors.ink }, copy: { fontSize: 14, lineHeight: 21, color: colors.muted }, meta: { fontSize: 12, lineHeight: 19, color: colors.muted },
  search: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingLeft: 14, backgroundColor: colors.surface, borderRadius: 16, borderWidth: 1, borderColor: colors.line }, searchInput: { flex: 1, minHeight: 54, color: colors.ink, fontSize: 14 }, iconButton: { minWidth: 44, minHeight: 44, alignItems: 'center', justifyContent: 'center' },
  recipeRow: { flexDirection: 'row', alignItems: 'center', gap: 12 }, row: { flexDirection: 'row', alignItems: 'center', gap: 10 }, rowCard: { gap: 12 }, number: { fontSize: 14, color: colors.primary, fontWeight: '800' }, link: { fontSize: 14, lineHeight: 20, color: colors.primaryDark, fontWeight: '700' },
  suggestions: { gap: 6, marginTop: 8 }, suggestion: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 12, paddingVertical: 10, borderRadius: radius.chip, backgroundColor: colors.lavenderTint, borderWidth: 1, borderColor: colors.lavenderLine }, suggestionText: { flex: 1, color: colors.ink, fontSize: 13, lineHeight: 18, fontWeight: '700' },
  searching: { marginTop: 7, color: colors.primary, fontSize: 12, fontWeight: '700' }, note: { marginTop: 7, color: colors.subtle, fontSize: 11, lineHeight: 16 }, noteRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 7, flexWrap: 'wrap' }, selected: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  empty: { alignItems: 'center', gap: 8, paddingVertical: 22 }, block: { gap: 4, borderTopWidth: 1, borderTopColor: colors.line, paddingTop: 8 }, blockTitle: { color: colors.muted, letterSpacing: 1, fontSize: 9, fontWeight: '800' },
  notice: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, backgroundColor: colors.amberBg }, noticeText: { flex: 1, color: colors.amberInk, fontSize: 12, lineHeight: 17, fontWeight: '700' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 }, chip: { paddingHorizontal: 12, paddingVertical: 12, borderRadius: 14, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line }, chipActive: { backgroundColor: colors.lavender, borderColor: colors.primary },
  confirm: { gap: 10, borderWidth: 2, borderColor: colors.line }, confirmOn: { borderColor: colors.primary, backgroundColor: colors.lavenderSoft }, confirmRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 11 }, confirmTitle: { color: colors.ink, fontSize: 16, lineHeight: 22, fontWeight: '800', marginBottom: 4 }, confirmState: { color: colors.primaryDark, fontSize: 12, lineHeight: 17, fontWeight: '700' },
  error: { fontSize: 14, lineHeight: 21, color: colors.red },
});
