// Client for the Food Verse AI endpoints (/api/v1/ai/*) plus the browser-side
// media helpers (image downscaling, video frame extraction). No secrets here:
// all model calls happen on the server.
import { useEffect, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { ApiError, customFetch } from '@workspace/api-client-react';
import type { FoodScan } from '@workspace/api-client-react';

export type DietConvention = 'none' | 'vegetarian' | 'eggetarian' | 'vegan' | 'jain';
export type DietLabel = 'vegan' | 'vegetarian' | 'eggetarian' | 'non_vegetarian' | 'uncertain';

export const DIET_OPTIONS: { value: DietConvention; label: string }[] = [
  { value: 'none', label: 'No restriction' },
  { value: 'vegetarian', label: 'Vegetarian (dairy ok, no egg)' },
  { value: 'eggetarian', label: 'Eggetarian' },
  { value: 'vegan', label: 'Vegan' },
  { value: 'jain', label: 'Jain' },
];
export const DIET_LABEL_TEXT: Record<DietLabel, string> = {
  vegan: 'Vegan', vegetarian: 'Vegetarian', eggetarian: 'Eggetarian', non_vegetarian: 'Non-vegetarian', uncertain: 'Uncertain',
};
export const CERTAINTY_TEXT = { confirmed: 'confirmed', likely: 'likely', uncertain: 'uncertain' } as const;

export interface AiStatus {
  configured: boolean; provider: string; model: string; nutritionDatabase: boolean;
  limits: { maxImages: number; maxVideoFrames: number; maxImageBytes: number };
}
export interface Nutrients { calories: number; protein: number; carbs: number; fat: number; fiber: number; sugar?: number | null; sodiumMg?: number | null; consistent?: boolean }
export interface AnalysisItem {
  name: string; confidence: number; dietLabel: DietLabel; dietCertainty: 'confirmed' | 'likely' | 'uncertain'; dietBasis: string | null;
  fitsYourDiet: boolean | null;
  portion: { description: string; grams: number | null; estimated: boolean };
  ingredients: { name: string; evidence: 'observed' | 'inferred' | 'user_provided' }[];
  nutrition: Nutrients | null; micronutrients: string[]; visibleCues: string[];
  allergyAlerts: { allergen: string; ingredient: string; basis: string }[];
}
export interface MediaAnalysis {
  summary: string; items: AnalysisItem[]; imageQuality: 'good' | 'fair' | 'poor'; needsClearerImage: boolean;
  clarifyingQuestions: string[]; mealBalance: string | null; suggestions: { category: string; text: string }[]; caveats: string[];
  modelCaveats: string[]; nutritionAvailable: boolean; totals: Nutrients | null; method: 'vision' | 'frame_sampling' | 'text';
  framesAnalyzed: number; frameTimestamps: number[];
  preparationSteps?: { order: number; timestamp: number | null; description: string; ingredientsAdded: string[] }[];
  processSummary?: string | null;
}
export type AiFoodScan = FoodScan & { analysis?: MediaAnalysis | null };

export interface FoodInfoFood {
  name: string; alternativeNames: string[]; description: string; origin: string | null; category: string;
  dietLabel: DietLabel; dietCertainty: 'confirmed' | 'likely' | 'uncertain'; dietNotes: string | null; fitsYourDiet: boolean | null;
  ingredients: string[]; ingredientsKnown: boolean; preparation: string[]; servingDescription: string | null;
  nutritionPerServing: Nutrients | null; servingSizes: { label: string; grams: number | null; calories: number | null }[];
  allergens: string[]; allergyAlerts: string[]; healthNotes: string[]; regionalNotes: string | null;
  similarFoods: string[]; healthierAlternatives: string[]; dietaryAlternatives: string[]; confidence: number;
  verifiedReference: { source: string; matchedFood: string; per100g: Record<string, number> } | null;
}
export interface FoodInfoResult { answer: string; isSingleFood: boolean; clarifyingQuestion: string | null; food?: FoodInfoFood; disclaimer: string }
export interface IdentifiedIngredient { name: string; confidence: number; quantityEstimate: string | null; needsConfirmation: boolean; note: string | null }
export interface IngredientResult { ingredients: IdentifiedIngredient[]; imageQuality: 'good' | 'fair' | 'poor'; clarifyingQuestions: string[]; photosAnalyzed: number }
export interface Recipe {
  name: string; description: string; cuisine: string; dietLabel: DietLabel; prepMinutes: number; cookMinutes: number;
  difficulty: 'easy' | 'medium' | 'hard'; servings: number;
  ingredients: { name: string; quantity: string | null; optional: boolean; have?: boolean; assumedStaple?: boolean }[];
  steps: { text: string; heat: string | null; timerMinutes: number | null }[];
  nutritionPerServing: Nutrients | null; substitutions: { for: string; use: string; note: string | null }[];
  servingSuggestions: string[]; storage: string | null; safetyNotes: string[]; tags: string[];
  missingIngredients: string[]; assumedPantryStaples: string[]; availableIngredients: string[]; usesOnlyWhatYouHave: boolean;
}
export interface RecipeResult { recipes: Recipe[]; notes: string | null; clarifyingQuestion: string | null; removedForSafety: string[]; disclaimer: string }
export interface SuggestionsResult { ideas: { name: string; why: string; dietLabel: DietLabel; tags: string[]; approxCalories: number | null; ingredients: string[] }[]; notes: string | null; disclaimer: string }
export interface RecipePreferences {
  cuisine?: string; spiceLevel?: 'mild' | 'medium' | 'hot'; maxMinutes?: number; difficulty?: 'easy' | 'medium' | 'hard';
  servings?: number; equipment?: string[]; variation?: string;
}
export interface ImagePayload { data: string; mimeType: string; timestamp?: number }

export class AiRequestError extends Error {
  constructor(message: string, readonly code: string, readonly status: number) { super(message); this.name = 'AiRequestError'; }
}

function toAiError(error: unknown): AiRequestError {
  if (error instanceof ApiError) {
    const detail = (error.data as { detail?: unknown } | null)?.detail;
    if (detail && typeof detail === 'object' && !Array.isArray(detail) && typeof (detail as { message?: unknown }).message === 'string') {
      const d = detail as { code?: string; message: string };
      return new AiRequestError(d.message, d.code ?? 'error', error.status);
    }
    if (error.status === 413) return new AiRequestError('That upload is too large. Try a smaller file.', 'invalid_input', 413);
    if (error.status === 422) return new AiRequestError('Some of that input wasn’t valid. Please check it and try again.', 'invalid_input', 422);
    return new AiRequestError('Something went wrong on our side. Please try again.', 'upstream', error.status);
  }
  return new AiRequestError('We couldn’t reach the server. Check your connection and try again.', 'network', 0);
}

async function aiPost<T>(path: string, body: unknown): Promise<T> {
  try {
    return await customFetch<T>(`/api/v1/ai/${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  } catch (error) { throw toAiError(error); }
}

export const useAiStatus = () => useQuery<AiStatus>({
  queryKey: ['ai-status'], staleTime: 60_000, retry: 1,
  queryFn: () => customFetch<AiStatus>('/api/v1/ai/status', { method: 'GET' }),
});
export const useFoodInfo = () => useMutation<FoodInfoResult, AiRequestError, { query: string; dietConvention: DietConvention; ingredientList?: string[] }>({ mutationFn: v => aiPost('food-info', v) });
export const useAnalyzeMedia = () => useMutation<AiFoodScan, AiRequestError, {
  kind: 'image' | 'video' | 'text' | 'audio'; images?: ImagePayload[]; description?: string; fileName?: string | null; dietConvention: DietConvention;
}>({ mutationFn: v => aiPost('analyze-media', v) });
export const useIdentifyIngredients = () => useMutation<IngredientResult, AiRequestError, { images: ImagePayload[]; note?: string }>({ mutationFn: v => aiPost('identify-ingredients', v) });
export const useAiRecipes = () => useMutation<RecipeResult, AiRequestError, {
  ingredients: string[]; dish?: string; dietConvention: DietConvention; excludeIngredients?: string[]; preferences?: RecipePreferences;
  previousRecipe?: Recipe | null; followUp?: string;
}>({ mutationFn: v => aiPost('recipes', v) });
export const useAiSuggestions = () => useMutation<SuggestionsResult, AiRequestError, { goal?: string; dietConvention: DietConvention; ingredients?: string[]; context?: string }>({ mutationFn: v => aiPost('suggestions', v) });

/** Diet convention is a per-browser preference shared by the scanner and Chef AI. */
export function useDietConvention(): [DietConvention, (value: DietConvention) => void] {
  const [value, setValue] = useState<DietConvention>('none');
  useEffect(() => {
    try {
      const saved = localStorage.getItem('fv-diet') as DietConvention | null;
      if (saved && DIET_OPTIONS.some(o => o.value === saved)) setValue(saved);
    } catch { /* storage unavailable */ }
  }, []);
  return [value, next => { setValue(next); try { localStorage.setItem('fv-diet', next); } catch { /* ignore */ } }];
}

// ---------------------------------------------------------------- media helpers
const stripPrefix = (dataUrl: string) => dataUrl.slice(dataUrl.indexOf(',') + 1);

function drawToJpeg(source: CanvasImageSource, width: number, height: number, maxDim: number, quality: number): string {
  const scale = Math.min(1, maxDim / Math.max(width, height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.round(width * scale));
  canvas.height = Math.max(1, Math.round(height * scale));
  const context = canvas.getContext('2d');
  if (!context) throw new Error('Your browser can’t process images here.');
  context.fillStyle = '#fff';
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.drawImage(source, 0, 0, canvas.width, canvas.height);
  return stripPrefix(canvas.toDataURL('image/jpeg', quality));
}

/** Decode, downscale to <=1280px and re-encode as JPEG so uploads stay small and always in a supported format. */
export async function imageFileToPayload(file: File, maxDim = 1280): Promise<ImagePayload> {
  const url = URL.createObjectURL(file);
  try {
    const image = new Image();
    image.src = url;
    try { await image.decode(); } catch { throw new Error('This image format can’t be read by your browser. Try a JPG or PNG.'); }
    return { data: drawToJpeg(image, image.naturalWidth, image.naturalHeight, maxDim, 0.85), mimeType: 'image/jpeg' };
  } finally { URL.revokeObjectURL(url); }
}

const withTimeout = <T,>(promise: Promise<T>, ms: number, message: string) =>
  new Promise<T>((resolve, reject) => { const timer = window.setTimeout(() => reject(new Error(message)), ms); promise.then(value => { window.clearTimeout(timer); resolve(value); }, error => { window.clearTimeout(timer); reject(error); }); });

export const VIDEO_LIMITS = { maxBytes: 100 * 1024 * 1024, maxSeconds: 180, frames: 6 };

/** Pull evenly spaced frames from a local video; only these frames are ever analyzed. */
export async function extractVideoFrames(file: File, onProgress?: (done: number, total: number) => void): Promise<{ frames: ImagePayload[]; duration: number }> {
  const url = URL.createObjectURL(file);
  const video = document.createElement('video');
  video.muted = true; video.playsInline = true; video.preload = 'auto'; video.src = url;
  try {
    await withTimeout(new Promise<void>((resolve, reject) => {
      video.onloadedmetadata = () => resolve();
      video.onerror = () => reject(new Error('This video format can’t be read by your browser. Try an MP4 (H.264) or WEBM file.'));
    }), 20_000, 'The video took too long to load. Try a shorter clip.');
    const duration = video.duration;
    if (!Number.isFinite(duration) || duration <= 0) throw new Error('We couldn’t read this video’s length. Try a different file.');
    if (duration > VIDEO_LIMITS.maxSeconds) throw new Error(`Videos can be up to ${VIDEO_LIMITS.maxSeconds / 60} minutes. Try a shorter clip.`);
    const total = Math.max(2, Math.min(VIDEO_LIMITS.frames, Math.ceil(duration / 2)));
    const frames: ImagePayload[] = [];
    for (let index = 0; index < total; index += 1) {
      const time = Math.min(duration - 0.05, (duration * (index + 0.5)) / total);
      await withTimeout(new Promise<void>((resolve, reject) => {
        video.onseeked = () => resolve();
        video.onerror = () => reject(new Error('The video stopped responding while reading frames.'));
        video.currentTime = time;
      }), 15_000, 'Reading a video frame took too long. Try a shorter or smaller clip.');
      frames.push({ data: drawToJpeg(video, video.videoWidth, video.videoHeight, 768, 0.8), mimeType: 'image/jpeg', timestamp: Math.round(time * 10) / 10 });
      onProgress?.(index + 1, total);
    }
    return { frames, duration };
  } finally { video.removeAttribute('src'); video.load(); URL.revokeObjectURL(url); }
}
