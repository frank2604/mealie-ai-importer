import { BASE_URL } from "./imports";

export interface CategoryOption {
  id: string;
  name?: string | null;
  groupId?: string | null;
  slug?: string | null;
}

export interface TagCategory {
  category: string;
  tags: CategoryOption[];
}

export interface MatchInfo {
  id?: string | null;
  name?: string | null;
  strategy?: string | null;
}

export interface CandidateOption {
  id: string;
  name?: string | null;
  pluralName?: string | null;
  abbreviation?: string | null;
  pluralAbbreviation?: string | null;
}

export interface UnitSuggestion {
  name?: string | null;
  pluralName?: string | null;
  abbreviation?: string | null;
  pluralAbbreviation?: string | null;
  useAbbreviation?: boolean | null;
}

export interface FoodSuggestion {
  nameSingular?: string | null;
  namePlural?: string | null;
  aliases: string[];
  categoryId?: string | null;
  categoryName?: string | null;
}

export interface ReviewOptions {
  foods: CandidateOption[];
  units: CandidateOption[];
  foodCategories: CategoryOption[];
}

export interface FoodSelectionPayload {
  mealieFoodId?: string | null;
  name?: string | null;
  badgeId?: string | null;
  status?: string | null;
  newId?: string | null;
}

export interface UnitSelectionPayload {
  mealieUnitId?: string | null;
  name?: string | null;
  badgeId?: string | null;
  status?: string | null;
  newId?: string | null;
}

export interface ReviewIngredient {
  id: string;
  sectionIndex: number;
  ingredientIndex: number;
  sectionName?: string | null;
  amount?: number | null;
  amountText?: string | null;
  unit?: string | null;
  unitOriginalName?: string | null;
  name: string;
  foodOriginalName?: string | null;
  foodNewId?: string | null;
  unitNewId?: string | null;
  note?: string | null;
  notes?: string | null;
  foodStatus: string;
  foodMatch?: MatchInfo | null;
  foodSuggestion?: FoodSuggestion | null;
  foodDecision: Record<string, any>;
  unitStatus: string;
  unitMatch?: MatchInfo | null;
  unitSuggestion?: UnitSuggestion | null;
  unitDecision: Record<string, any>;
  foodSelection?: FoodSelectionPayload;
  unitSelection?: UnitSelectionPayload;
}

export interface ReviewInstruction {
  id: string;
  sectionIndex: number;
  stepIndex: number;
  order: number;
  text: string;
  timerMinutes?: number | null;
}

export interface ReviewAssets {
  pdfUrl?: string | null;
  imageUrl?: string | null;
}

export interface ReviewSummary {
  title: string;
  description: string;
  recipeServings?: number | null;
  recipeYieldQuantity?: number | null;
  recipeYield?: string | null;
  totalTime?: string | null;
  prepTime?: string | null;
  performTime?: string | null;
  categoryId?: string | null;
  tagIds: string[];
  availableCategories: CategoryOption[];
  availableTagCategories: TagCategory[];
}

export interface ReviewData {
  runId: string;
  summary: ReviewSummary;
  ingredients: ReviewIngredient[];
  instructions: ReviewInstruction[];
  assets: ReviewAssets;
  options: ReviewOptions;
}

export interface ImageUploadResponse {
  imageUrl: string;
}

export interface ReviewSummaryUpdatePayload {
  title: string;
  description: string;
  recipeServings?: number | null;
  recipeYieldQuantity?: number | null;
  recipeYield?: string | null;
  totalTime?: string | null;
  prepTime?: string | null;
  performTime?: string | null;
  categoryId?: string | null;
  tagIds: string[];
}

export interface ReviewIngredientUpdatePayload {
  id: string;
  notes?: string | null;
  foodDecision: Record<string, any>;
  unitDecision: Record<string, any>;
  foodSelection?: FoodSelectionPayload;
  unitSelection?: UnitSelectionPayload;
}

export interface ReviewInstructionUpdatePayload {
  id: string;
  order?: number | null;
  text: string;
  timerMinutes?: number | null;
}

export interface ReviewUpdatePayload {
  summary: ReviewSummaryUpdatePayload;
  ingredients: ReviewIngredientUpdatePayload[];
  instructions: ReviewInstructionUpdatePayload[];
}

const parseError = async (response: Response): Promise<Error> => {
  try {
    const data = await response.json();
    const detail = typeof data === "string" ? data : data?.detail;
    if (detail) {
      return new Error(detail);
    }
  } catch {
    // ignore – fall back to status text
  }
  return new Error(response.statusText || `Request failed with status ${response.status}`);
};

export const fetchReviewData = async (runId: string): Promise<ReviewData> => {
  const response = await fetch(`${BASE_URL}/imports/${encodeURIComponent(runId)}/review`, {
    method: "GET",
    credentials: "same-origin"
  });
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as ReviewData;
};

export const updateReviewData = async (runId: string, payload: ReviewUpdatePayload): Promise<ReviewData> => {
  const response = await fetch(`${BASE_URL}/imports/${encodeURIComponent(runId)}/review`, {
    method: "PUT",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as ReviewData;
};

export const uploadRecipeImage = async (runId: string, file: File): Promise<ImageUploadResponse> => {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${BASE_URL}/imports/${encodeURIComponent(runId)}/image`, {
    method: "POST",
    credentials: "same-origin",
    body: formData
  });
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as ImageUploadResponse;
};
