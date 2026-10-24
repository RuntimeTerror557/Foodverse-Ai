// AI-powered panels for the Scanner and Chef AI pages. They reuse the app's existing
// classes (panel, eyebrow, tag-list, macro-grid, button, text-input...) so the visual
// design stays consistent; only a few `.ai-*` helpers were added to index.css.
import { type ReactNode, useState } from 'react';
import { AlertTriangle, ArrowRight, Camera, Check, CircleHelp, Lightbulb, Search, ShieldCheck, Sparkles } from 'lucide-react';
import {
  CERTAINTY_TEXT, DIET_LABEL_TEXT, DIET_OPTIONS, imageFileToPayload, useAiSuggestions, useFoodInfo, useIdentifyIngredients,
  type AiStatus, type AnalysisItem, type DietConvention, type DietLabel, type FoodInfoFood, type MediaAnalysis, type Nutrients, type Recipe,
} from '@/lib/food-ai';

const pretty = (value: string) => value.replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase());

export function DietBadge({ label, certainty }: { label: DietLabel; certainty?: keyof typeof CERTAINTY_TEXT }) {
  return <span className={`ai-diet ai-diet-${label}`} data-testid={`badge-diet-${label}`}>
    {DIET_LABEL_TEXT[label]}{certainty && label !== 'uncertain' && <small> · {CERTAINTY_TEXT[certainty]}</small>}
  </span>;
}

export function FitsDiet({ fits }: { fits: boolean | null | undefined }) {
  if (fits === null) return <span className="ai-fit ai-fit-unknown"><CircleHelp size={12} /> Can’t tell if this suits your diet</span>;
  if (fits === false) return <span className="ai-fit ai-fit-no"><AlertTriangle size={12} /> Doesn’t match your diet</span>;
  if (fits === true) return <span className="ai-fit ai-fit-yes"><Check size={12} /> Fits your diet</span>;
  return null;
}

export function AiSetupNotice({ status }: { status?: AiStatus }) {
  if (!status || status.configured) return null;
  return <div className="ai-notice" role="status" data-testid="notice-ai-not-configured"><AlertTriangle size={16} />
    <span><strong>AI features aren’t switched on yet.</strong> The server needs an AI key (<code>GEMINI_API_KEY</code>, <code>XAI_API_KEY</code> or <code>ANTHROPIC_API_KEY</code>) before it can analyze food or write recipes.</span></div>;
}

export function DietSelect({ value, onChange, id }: { value: DietConvention; onChange: (value: DietConvention) => void; id: string }) {
  return <select id={id} className="text-input ai-select" value={value} onChange={event => onChange(event.target.value as DietConvention)} data-testid={`select-${id}`}>
    {DIET_OPTIONS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
  </select>;
}

const nutrientLine = (n: Nutrients) => `${n.calories} kcal · ${n.protein} g protein · ${n.carbs} g carbs · ${n.fat} g fat`;
const formatTime = (seconds: number | null) => (seconds === null ? '' : `${Math.floor(seconds / 60)}:${String(Math.round(seconds % 60)).padStart(2, '0')}`);

function ItemCard({ item }: { item: AnalysisItem }) {
  return <div className="ai-item" data-testid={`item-analysis-${item.name.toLowerCase().replaceAll(' ', '-')}`}>
    <div className="ai-item-head"><strong>{item.name}</strong><span className="ai-conf">{item.confidence}% sure</span></div>
    <div className="ai-item-meta"><DietBadge label={item.dietLabel} certainty={item.dietCertainty} /><FitsDiet fits={item.fitsYourDiet} /><span className="ai-portion">{item.portion.description}{item.portion.grams ? ` (~${Math.round(item.portion.grams)} g, estimated)` : ''}</span></div>
    {item.dietBasis && <p className="ai-fine">{item.dietBasis}</p>}
    {item.allergyAlerts.map(alert => <div className="allergy-warning ai-alert" key={`${alert.allergen}-${alert.ingredient}`}><AlertTriangle size={14} /><div><strong>Possible {alert.allergen}</strong><span>{alert.ingredient} — {alert.basis}. Check labels; this can’t confirm safety.</span></div></div>)}
    <div className="tag-list ai-ingredients">{item.ingredients.map(ing => <span key={ing.name} className={ing.evidence === 'observed' ? '' : 'ai-inferred'} title={ing.evidence === 'observed' ? 'Visible in the food' : ing.evidence === 'inferred' ? 'Inferred, not visible' : 'From your description'}>{ing.name}{ing.evidence === 'inferred' ? ' (inferred)' : ''}</span>)}</div>
    {item.nutrition ? <p className="ai-fine">≈ {nutrientLine(item.nutrition)} <em>(estimate)</em>{item.nutrition.consistent === false ? ' · numbers may not add up, treat with extra caution' : ''}</p> : <p className="ai-fine">Not enough information to estimate nutrition for this item.</p>}
  </div>;
}

export function AnalysisDetails({ analysis }: { analysis: MediaAnalysis }) {
  return <div className="ai-analysis" data-testid="analysis-details">
    {analysis.needsClearerImage && <div className="ai-notice" role="status"><Camera size={16} /><span><strong>A clearer picture would help.</strong> {analysis.clarifyingQuestions[0] ?? 'Try better light and a closer shot of the food.'}</span></div>}
    {analysis.summary && <p className="ai-summary">{analysis.summary}</p>}
    {analysis.items.length > 0 && <div className="ai-block"><span className="mini-heading">WHAT WE SPOTTED · {analysis.items.length} {analysis.items.length === 1 ? 'ITEM' : 'ITEMS'}</span>{analysis.items.map(item => <ItemCard key={item.name} item={item} />)}</div>}
    {analysis.preparationSteps && analysis.preparationSteps.length > 0 && <div className="ai-block"><span className="mini-heading">WHAT THE FRAMES SHOW, IN ORDER</span><ol className="ai-steps">{analysis.preparationSteps.map(step => <li key={step.order}>{step.timestamp !== null && <b>{formatTime(step.timestamp)}</b>} {step.description}{step.ingredientsAdded.length > 0 && <small> · added: {step.ingredientsAdded.join(', ')}</small>}</li>)}</ol>{analysis.processSummary && <p className="ai-fine">{analysis.processSummary}</p>}</div>}
    {analysis.mealBalance && <div className="ai-block"><span className="mini-heading">MEAL BALANCE</span><p className="ai-fine ai-body">{analysis.mealBalance}</p></div>}
    {analysis.suggestions.length > 0 && <div className="ai-block"><span className="mini-heading">SUGGESTIONS</span><ul className="ai-list">{analysis.suggestions.map((s, i) => <li key={`${i}-${s.text}`}><b>{pretty(s.category)}:</b> {s.text}</li>)}</ul></div>}
    {analysis.clarifyingQuestions.length > 0 && !analysis.needsClearerImage && <div className="ai-block"><span className="mini-heading">HELP US BE MORE PRECISE</span><ul className="ai-list">{analysis.clarifyingQuestions.map(q => <li key={q}>{q}</li>)}</ul></div>}
    <div className="ai-caveats"><ShieldCheck size={14} /><div>{[...analysis.caveats, ...analysis.modelCaveats].map(c => <p key={c}>{c}</p>)}{analysis.method === 'frame_sampling' && <p>{analysis.framesAnalyzed} frames were analyzed{analysis.frameTimestamps.length ? ` (at ${analysis.frameTimestamps.map(t => `${t}s`).join(', ')})` : ''}.</p>}</div></div>
  </div>;
}

function FoodCard({ food, disclaimer }: { food: FoodInfoFood; disclaimer: string }) {
  const n = food.nutritionPerServing;
  return <div className="ai-food" data-testid="card-food-info">
    <div className="ai-item-head"><h3>{food.name}</h3><span className="ai-conf">{food.confidence}% confident</span></div>
    {food.alternativeNames.length > 0 && <p className="ai-fine">Also known as {food.alternativeNames.join(', ')}</p>}
    <div className="ai-item-meta"><DietBadge label={food.dietLabel} certainty={food.dietCertainty} /><FitsDiet fits={food.fitsYourDiet} /><span className="ai-portion">{pretty(food.category)}{food.origin ? ` · ${food.origin}` : ''}</span></div>
    {food.dietNotes && <p className="ai-fine">{food.dietNotes}</p>}
    {food.description && <p className="ai-body">{food.description}</p>}
    {food.allergyAlerts.map(alert => <div className="allergy-warning ai-alert" key={alert}><AlertTriangle size={14} /><div><strong>Allergy note</strong><span>{alert}</span></div></div>)}
    {n && <><span className="mini-heading">PER SERVING{food.servingDescription ? ` · ${food.servingDescription.toUpperCase()}` : ''} · AI ESTIMATE</span>
      <div className="macro-grid"><div><span>Energy</span><strong>{n.calories}<small> kcal</small></strong></div><div><span>Protein</span><strong>{n.protein}<small> g</small></strong></div><div><span>Carbs</span><strong>{n.carbs}<small> g</small></strong></div><div><span>Fat</span><strong>{n.fat}<small> g</small></strong></div></div>
      <p className="ai-fine">Fiber {n.fiber} g{n.sugar != null ? ` · sugar ${n.sugar} g` : ''}{n.sodiumMg != null ? ` · sodium ${n.sodiumMg} mg` : ''}</p></>}
    {food.verifiedReference && <p className="ai-reference" data-testid="text-verified-reference"><ShieldCheck size={13} /> {food.verifiedReference.source} reference for “{food.verifiedReference.matchedFood}” (per 100 g): {food.verifiedReference.per100g.calories} kcal{food.verifiedReference.per100g.protein != null ? `, ${food.verifiedReference.per100g.protein} g protein` : ''}{food.verifiedReference.per100g.carbs != null ? `, ${food.verifiedReference.per100g.carbs} g carbs` : ''}{food.verifiedReference.per100g.fat != null ? `, ${food.verifiedReference.per100g.fat} g fat` : ''}.</p>}
    {food.servingSizes.length > 0 && <p className="ai-fine">Common servings: {food.servingSizes.map(s => `${s.label}${s.calories != null ? ` (~${s.calories} kcal)` : ''}`).join(' · ')}</p>}
    <span className="mini-heading">{food.ingredientsKnown ? 'TYPICAL INGREDIENTS' : 'LIKELY INGREDIENTS (RECIPE VARIES)'}</span>
    <div className="tag-list ai-ingredients">{food.ingredients.map(i => <span key={i}>{i}</span>)}</div>
    {food.allergens.length > 0 && <p className="ai-fine"><b>Commonly contains:</b> {food.allergens.join(', ')}</p>}
    {food.preparation.length > 0 && <p className="ai-fine"><b>Preparation:</b> {food.preparation.join(' → ')}</p>}
    {food.healthNotes.length > 0 && <ul className="ai-list">{food.healthNotes.map(h => <li key={h}>{h}</li>)}</ul>}
    {food.regionalNotes && <p className="ai-fine">{food.regionalNotes}</p>}
    {([['Similar foods', food.similarFoods], ['Healthier swaps', food.healthierAlternatives], ['Dietary alternatives', food.dietaryAlternatives]] as const).filter(([, list]) => list.length > 0).map(([title, list]) => <p className="ai-fine" key={title}><b>{title}:</b> {list.join(', ')}</p>)}
    <p className="estimate-note"><CircleHelp size={13} /> {disclaimer}</p>
  </div>;
}

const ASK_EXAMPLES = ['Is paneer butter masala vegetarian?', 'Calories in two rotis with dal', 'Which Gujarati snacks are high in protein?'];

/** Natural-language food search and personalised suggestions. */
export function FoodAssistant({ diet, onDietChange, status }: { diet: DietConvention; onDietChange: (value: DietConvention) => void; status?: AiStatus }) {
  const [query, setQuery] = useState('');
  const lookup = useFoodInfo();
  const ideas = useAiSuggestions();
  const [view, setView] = useState<'lookup' | 'ideas' | null>(null);
  const blocked = status ? !status.configured : false;
  const busy = lookup.isPending || ideas.isPending;
  const error = view === 'ideas' ? ideas.error : lookup.error;
  return <section className="panel ai-assistant" data-testid="panel-food-assistant">
    <div className="eyebrow">ASK ABOUT ANY FOOD</div><h2>Look it up, or ask in your own words.</h2>
    <p className="ai-fine ai-body">Indian, regional, international, packaged or homemade — search a name or ask a question. Classifications use ingredients, and say so when they’re uncertain.</p>
    <div className="ai-ask-row"><input className="text-input" value={query} maxLength={400} onChange={e => setQuery(e.target.value)} placeholder="e.g. rajma chawal, or “is this snack vegan?”" aria-label="Food name or question" data-testid="input-food-query"
      onKeyDown={e => { if (e.key === 'Enter' && query.trim().length > 1 && !busy && !blocked) { setView('lookup'); lookup.mutate({ query, dietConvention: diet }); } }} />
      <button className="button button-primary" disabled={query.trim().length < 2 || busy || blocked} onClick={() => { setView('lookup'); lookup.mutate({ query, dietConvention: diet }); }} data-testid="button-food-lookup"><Search size={15} />{lookup.isPending ? 'Looking…' : 'Look up'}</button>
      <button className="button button-outline" disabled={busy || blocked} onClick={() => { setView('ideas'); ideas.mutate({ dietConvention: diet, context: query }); }} data-testid="button-food-ideas"><Lightbulb size={15} />{ideas.isPending ? 'Thinking…' : 'Suggest ideas'}</button></div>
    <div className="ai-ask-row ai-ask-diet"><label className="field-label" htmlFor="ask-diet">Diet</label><DietSelect id="ask-diet" value={diet} onChange={onDietChange} /></div>
    <div className="suggestions">{ASK_EXAMPLES.map(example => <button key={example} onClick={() => setQuery(example)} data-testid={`button-ask-example-${example.length}`}>{example}</button>)}</div>
    {error && <div className="inline-error" role="alert" data-testid="text-ai-error">{error.message}</div>}
    {view === 'lookup' && lookup.data && <div className="ai-result" data-testid="result-food-lookup"><p className="ai-answer">{lookup.data.answer}</p>
      {lookup.data.clarifyingQuestion && <div className="ai-notice"><CircleHelp size={15} /><span>{lookup.data.clarifyingQuestion}</span></div>}
      {lookup.data.food ? <FoodCard food={lookup.data.food} disclaimer={lookup.data.disclaimer} /> : <p className="estimate-note"><CircleHelp size={13} /> {lookup.data.disclaimer}</p>}</div>}
    {view === 'ideas' && ideas.data && <div className="ai-result" data-testid="result-food-ideas"><span className="mini-heading">IDEAS FOR YOU</span>
      {ideas.data.ideas.map(idea => <div className="ai-item" key={idea.name}><div className="ai-item-head"><strong>{idea.name}</strong>{idea.approxCalories != null && <span className="ai-conf">≈ {idea.approxCalories} kcal</span>}</div><div className="ai-item-meta"><DietBadge label={idea.dietLabel} /></div><p className="ai-fine">{idea.why}</p><div className="tag-list ai-ingredients">{idea.ingredients.map(i => <span key={i}>{i}</span>)}</div></div>)}
      {ideas.data.notes && <p className="ai-fine">{ideas.data.notes}</p>}<p className="estimate-note"><CircleHelp size={13} /> {ideas.data.disclaimer}</p></div>}
  </section>;
}

/** Photo of the user's ingredients -> confirmable list. */
export function IngredientPhoto({ onUse, disabled }: { onUse: (names: string[]) => void; disabled?: boolean }) {
  const identify = useIdentifyIngredients();
  const [picked, setPicked] = useState<Record<string, boolean>>({});
  const [localError, setLocalError] = useState('');
  const onFile = async (file?: File) => {
    if (!file) return;
    setLocalError('');
    if (!file.type.startsWith('image/')) { setLocalError('Please choose an image file.'); return; }
    if (file.size > 20 * 1024 * 1024) { setLocalError('Choose a photo smaller than 20 MB.'); return; }
    try {
      const payload = await imageFileToPayload(file);
      identify.mutate({ images: [payload] }, { onSuccess: result => setPicked(Object.fromEntries(result.ingredients.map(i => [i.name, !i.needsConfirmation]))) });
    } catch (error) { setLocalError(error instanceof Error ? error.message : 'We couldn’t read that photo.'); }
  };
  const result = identify.data;
  return <div className="ai-photo" data-testid="panel-ingredient-photo">
    <label className={`button button-outline ai-photo-button ${disabled ? 'is-disabled' : ''}`} htmlFor="ingredient-photo"><Camera size={15} />{identify.isPending ? 'Looking at your photo…' : 'Add a photo of your ingredients'}
      <input id="ingredient-photo" type="file" accept="image/*" capture="environment" disabled={disabled || identify.isPending} onChange={e => { void onFile(e.target.files?.[0]); e.target.value = ''; }} data-testid="input-ingredient-photo" /></label>
    {(localError || identify.error) && <div className="inline-error" role="alert">{localError || identify.error?.message}</div>}
    {result && <div className="ai-photo-result">
      {result.ingredients.length === 0 ? <p className="ai-fine">{result.clarifyingQuestions[0] ?? 'We couldn’t make out any ingredients. Try a clearer, closer photo.'}</p> : <>
        <span className="mini-heading">WE SPOTTED — TAP TO CONFIRM</span>
        <div className="tag-list ai-chips">{result.ingredients.map(i => <button type="button" key={i.name} className={`ai-chip ${picked[i.name] ? 'on' : ''}`} aria-pressed={!!picked[i.name]} onClick={() => setPicked({ ...picked, [i.name]: !picked[i.name] })} data-testid={`chip-ingredient-${i.name.toLowerCase().replaceAll(' ', '-')}`}>{picked[i.name] && <Check size={11} />}{i.name}{i.needsConfirmation && <small> · not sure</small>}</button>)}</div>
        {result.ingredients.some(i => i.needsConfirmation) && <p className="ai-fine">Items marked “not sure” are off by default — switch on only what’s really in your kitchen.</p>}
        <button type="button" className="button button-primary" disabled={!Object.values(picked).some(Boolean)} onClick={() => onUse(result.ingredients.filter(i => picked[i.name]).map(i => i.name))} data-testid="button-use-photo-ingredients">Use these ingredients <ArrowRight size={14} /></button></>}
    </div>}
  </div>;
}

export function RecipeDetails({ recipe, extra }: { recipe: Recipe; extra?: ReactNode }) {
  const n = recipe.nutritionPerServing;
  return <div className="ai-recipe" data-testid="recipe-details">
    <p className="ai-body">{recipe.description}</p>
    <div className="ai-item-meta"><DietBadge label={recipe.dietLabel} /><span className="ai-portion">{recipe.cuisine} · {pretty(recipe.difficulty)}</span></div>
    <span className="mini-heading">INGREDIENTS</span>
    <ul className="ai-ingredient-list">{recipe.ingredients.map(i => <li key={i.name} className={i.have ? 'have' : i.assumedStaple ? 'staple' : i.optional ? 'optional' : 'missing'}>
      <span>{i.have ? <Check size={12} /> : i.assumedStaple ? '•' : '+'}</span><b>{i.name}</b>{i.quantity && <small>{i.quantity}</small>}{i.optional && <em>optional</em>}</li>)}</ul>
    {recipe.missingIngredients.length > 0
      ? <div className="ai-notice" data-testid="notice-missing-ingredients"><ShoppingNote items={recipe.missingIngredients} /></div>
      : <p className="ai-fine ai-ok"><Check size={12} /> You have everything this recipe needs{recipe.assumedPantryStaples.length ? ` (assuming pantry staples: ${recipe.assumedPantryStaples.join(', ')})` : ''}.</p>}
    {n && <><span className="mini-heading">PER SERVING · AI ESTIMATE</span><p className="ai-fine">{nutrientLine(n)} · fiber {n.fiber} g</p></>}
    {extra}
    {recipe.servingSuggestions.length > 0 && <p className="ai-fine"><b>To serve:</b> {recipe.servingSuggestions.join(' · ')}</p>}
    {recipe.storage && <p className="ai-fine"><b>Storage:</b> {recipe.storage}</p>}
    {recipe.safetyNotes.length > 0 && <ul className="ai-list">{recipe.safetyNotes.map(s => <li key={s}>{s}</li>)}</ul>}
  </div>;
}

function ShoppingNote({ items }: { items: string[] }) {
  return <><Sparkles size={15} /><span><strong>You’d still need:</strong> {items.join(', ')}. Substitutions are listed below where we have an idea.</span></>;
}
