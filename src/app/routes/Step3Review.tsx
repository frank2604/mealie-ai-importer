import { useCallback, useEffect, useMemo, useRef, useState, Fragment } from "react";
import clsx from "clsx";
import { Dialog, Transition } from "@headlessui/react";
import Cropper from "react-easy-crop";
import type { Area } from "react-easy-crop";
import "react-easy-crop/react-easy-crop.css";
import { ChevronUpDownIcon, PencilSquareIcon, XMarkIcon, TrashIcon } from "@heroicons/react/24/outline";
import { useTranslation } from "react-i18next";
import { PdfViewer } from "../components/PdfViewer";
import { layoutConfig } from "../../config/layout.config";
import { BadgeId } from "../../config/badges.config";
import {
  CandidateOption,
  CategoryOption,
  ReviewData,
  ReviewIngredient,
  ReviewInstruction,
  FoodSelectionPayload,
  UnitSelectionPayload,
  PdfImageOption,
  fetchReviewData,
  updateReviewData,
  uploadRecipeImage,
  fetchPdfImages
} from "../api/review";
import { useImportFlow } from "../context/ImportFlowContext";
import { BadgePill } from "../components/BadgePill";
import { NewFoodModal, FoodCreateFormValues } from "../components/Modals/NewFoodModal";
import { NewUnitModal, UnitCreateFormValues } from "../components/Modals/NewUnitModal";
import { BASE_URL } from "../api/imports";
import { useStepNavigation } from "../App";

const mapStatusToBadgeId = (status?: string | null): BadgeId | null => {
  switch (status) {
    case "found_word":
    case "found_fuzzy":
    case "found_ai":
      return status as BadgeId;
    case "found":
      return "found_word";
    case "new":
      return "new";
    case "manual":
      return "manual";
    case "none":
      return "none";
    default:
      return null;
  }
};

interface SummaryFormState {
  servingsInput: string;
  yieldQuantityInput: string;
  yieldTextInput: string;
  totalTimeInput: string;
  prepTimeInput: string;
  performTimeInput: string;
  notesInput: string;
}

interface SearchableSelectProps {
  options: CandidateOption[];
  selectedId?: string | null;
  displayValue?: string | null;
  placeholder: string;
  clearLabel: string;
  disabled?: boolean;
  onChange: (option: CandidateOption | null) => void;
  extraActions?: { id: string; label: string; onSelect: () => void }[];
}

interface StepIngredientOption {
  id: string;
  foodLabel: string;
}

const MAX_RESULTS = 50;
type TagOption = CategoryOption & { category?: string | null; detail?: string | null };

const compareCandidateOptions = (a: CandidateOption, b: CandidateOption) => {
  const left = (a.name ?? a.id ?? "").toString();
  const right = (b.name ?? b.id ?? "").toString();
  return left.localeCompare(right, undefined, { sensitivity: "base" });
};

const SearchableSelect: React.FC<SearchableSelectProps> = ({
  options,
  selectedId,
  displayValue,
  placeholder,
  clearLabel,
  disabled = false,
  onChange,
  extraActions = []
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const containerRef = useRef<HTMLDivElement | null>(null);

  const selectedOption = useMemo(
    () => options.find((option) => option.id === selectedId) ?? null,
    [options, selectedId]
  );

  const filteredOptions = useMemo(() => {
    const term = query.trim().toLowerCase();
    const base = term
      ? options.filter((option) => (option.name ?? "").toLowerCase().includes(term))
      : options;
    return base.slice(0, MAX_RESULTS);
  }, [options, query]);

  useEffect(() => {
    if (!isOpen) {
      setQuery("");
      return;
    }
    const handleClick = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => {
      document.removeEventListener("mousedown", handleClick);
    };
  }, [isOpen]);

  const handleSelect = (option: CandidateOption | null) => {
    onChange(option);
    setIsOpen(false);
    setQuery("");
  };

  const renderLabel = (option: CandidateOption | null) => {
    if (!option) {
      return displayValue || placeholder;
    }
    const parts = [option.name];
    if (option.abbreviation) {
      parts.push(`(${option.abbreviation})`);
    }
    return parts.filter(Boolean).join(" ");
  };

  return (
    <div ref={containerRef} className="relative w-full">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setIsOpen((prev) => !prev)}
        className={clsx(
          "focus-ring flex w-full items-center justify-between border border-border bg-background px-3 py-2 text-sm font-medium text-text",
          layoutConfig.borderRadius.medium,
          disabled ? "cursor-not-allowed opacity-50" : "hover:border-primary/60 hover:text-primary"
        )}
      >
        <span className="truncate text-left">{renderLabel(selectedOption)}</span>
        <ChevronUpDownIcon className="ml-2 h-4 w-4 text-text/60" aria-hidden="true" />
      </button>
      {isOpen && !disabled ? (
        <div className={clsx("absolute z-40 mt-1 w-full border border-border/60 bg-panel shadow-lg", layoutConfig.borderRadius.medium)}>
          <div className="border-b border-border/60">
            <input
              autoFocus
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={placeholder}
              className="w-full border-0 bg-transparent px-3 py-2 text-sm text-text outline-none"
            />
          </div>
          <div className="max-h-60 overflow-auto">
            <button
              type="button"
              className="flex w-full items-center px-3 py-2 text-left text-xs text-text/70 hover:bg-background/60"
              onClick={() => handleSelect(null)}
            >
              {clearLabel}
            </button>
            {extraActions.map((action) => (
              <button
                type="button"
                key={action.id}
                className="flex w-full items-center px-3 py-2 text-left text-xs text-primary hover:bg-background/60"
                onClick={() => {
                  action.onSelect();
                  setIsOpen(false);
                  setQuery("");
                }}
              >
                {action.label}
              </button>
            ))}
            {filteredOptions.map((option) => (
              <button
                type="button"
                key={option.id}
                onClick={() => handleSelect(option)}
                className={clsx(
                  "flex w-full flex-col px-3 py-2 text-left text-sm hover:bg-background/80",
                  option.id === selectedId ? "bg-primary/10 text-primary" : "text-text"
                )}
              >
                <span className="font-medium">{option.name ?? option.id}</span>
                {option.abbreviation ? (
                  <span className="text-xs text-text/60">{option.abbreviation}</span>
                ) : null}
              </button>
            ))}
            {filteredOptions.length === 0 ? (
              <div className="px-3 py-2 text-xs text-text/60">—</div>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
};
interface TagMultiSelectProps {
  options: TagOption[];
  selectedIds: string[];
  placeholder: string;
  searchPlaceholder: string;
  onChange: (ids: string[]) => void;
}

const TagSelectionList: React.FC<TagMultiSelectProps & { categories: string[]; activeCategory: string | null; onCategoryToggle: (category: string | null) => void }> = ({
  options,
  selectedIds,
  placeholder,
  searchPlaceholder,
  onChange,
  categories,
  activeCategory,
  onCategoryToggle
}) => {
  const [query, setQuery] = useState("");
  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);
  const filteredOptions = useMemo(() => {
    const term = query.trim().toLowerCase();
    return options.filter((option) => {
      const name = (option.name ?? option.id).toLowerCase();
      const category = (option.category ?? "").toLowerCase();
      const matchesQuery = !term || name.includes(term) || category.includes(term);
      const matchesCategory = !activeCategory || option.category === activeCategory;
      return matchesQuery && matchesCategory;
    });
  }, [activeCategory, options, query]);

  const toggleSelection = (id: string) => {
    if (selectedSet.has(id)) {
      onChange(selectedIds.filter((item) => item !== id));
    } else {
      onChange([...selectedIds, id]);
    }
  };

  const removeSelection = (id: string) => {
    onChange(selectedIds.filter((item) => item !== id));
  };

  return (
    <div className={clsx("border border-border bg-background", layoutConfig.borderRadius.medium)}>
      <div className="border-b border-border/60 px-3 py-2">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={searchPlaceholder}
          className="w-full border-0 bg-transparent text-sm text-text outline-none"
        />
      </div>
      {categories.length ? (
        <div className="flex flex-wrap gap-2 border-b border-border/60 px-3 py-2">
          {categories.map((category) => {
            const isActive = category === activeCategory;
            return (
              <button
                type="button"
                key={category}
                onClick={() => onCategoryToggle(isActive ? null : category)}
                className={clsx(
                  "inline-flex items-center border px-2 py-1 text-xs font-semibold",
                  layoutConfig.borderRadius.small,
                  isActive ? "border-primary bg-primary/10 text-primary" : "border-border text-text/70 hover:text-primary hover:border-primary/50"
                )}
              >
                {category}
              </button>
            );
          })}
        </div>
      ) : null}
      <div className="max-h-[32rem] overflow-auto">
        {filteredOptions.length === 0 ? (
          <div className="px-3 py-2 text-xs text-text/60">{placeholder}</div>
        ) : (
          filteredOptions.map((option) => {
            const isSelected = selectedSet.has(option.id);
            return (
              <label
                key={option.id}
                className={clsx(
                  "flex cursor-pointer items-center gap-3 px-3 py-2 text-sm",
                  isSelected ? "bg-primary/10 text-primary" : "text-text/80"
                )}
              >
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={() => toggleSelection(option.id)}
                  className="h-4 w-4 border-border text-primary focus:ring-primary"
                />
                <div className="flex flex-col">
                  <span className="font-semibold">{option.name ?? option.id}</span>
                  {option.category ? <span className="text-xs text-text/60">{option.category}</span> : null}
                </div>
              </label>
            );
          })
        )}
      </div>
    </div>
  );
};

interface TagSelectionModalProps extends TagMultiSelectProps {
  isOpen: boolean;
  onClose: () => void;
  categories: string[];
  activeCategory: string | null;
  onCategoryToggle: (category: string | null) => void;
}

const TagSelectionModal: React.FC<TagSelectionModalProps> = ({ isOpen, onClose, options, selectedIds, placeholder, searchPlaceholder, onChange, categories, activeCategory, onCategoryToggle }) => {
  const { t } = useTranslation();

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-40" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-200"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-150"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4 text-center">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-200"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-150"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel
                className={clsx(
                  "w-full max-w-4xl transform overflow-hidden border border-border bg-panel p-6 text-left align-middle shadow-xl transition-all",
                  layoutConfig.borderRadius.large
                )}
              >
                <Dialog.Title className="text-xl font-semibold text-primary">{t("review.meta.tags")}</Dialog.Title>
                <div className="mt-4" style={{ maxHeight: "80vh" }}>
                  <TagSelectionList
                    options={options}
                    selectedIds={selectedIds}
                    placeholder={placeholder}
                    searchPlaceholder={searchPlaceholder}
                    onChange={onChange}
                    categories={categories}
                    activeCategory={activeCategory}
                    onCategoryToggle={onCategoryToggle}
                  />
                </div>
                <div className="mt-4 flex justify-end">
                  <button
                    type="button"
                    onClick={onClose}
                    className={clsx(
                      "focus-ring inline-flex items-center bg-primary px-4 py-2 text-sm font-semibold text-on-primary hover:bg-primary/90",
                      layoutConfig.borderRadius.small
                    )}
                  >
                    {t("review.modal.close")}
                  </button>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
};

const getFoodCreatePayload = (entry: ReviewIngredient): FoodCreateFormValues => {
  const decision = (entry.foodDecision || {}) as Record<string, any>;
  return (decision.create || {}) as FoodCreateFormValues;
};

const getUnitCreatePayload = (entry: ReviewIngredient): UnitCreateFormValues => {
  const decision = (entry.unitDecision || {}) as Record<string, any>;
  return (decision.create || {}) as UnitCreateFormValues;
};

const getFoodSuggestionBaseName = (entry: ReviewIngredient): string => {
  const create = getFoodCreatePayload(entry);
  return (
    create.nameSingular ??
    entry.foodSuggestion?.nameSingular ??
    entry.foodOriginalName ??
    entry.name
  );
};

const getIngredientSelectionKey = (entry: ReviewIngredient): string | null =>
  entry.foodSelection?.newId ?? entry.foodSelection?.mealieFoodId ?? entry.foodMatch?.id ?? null;

const getUnitSuggestionBaseName = (entry: ReviewIngredient): string => {
  const create = getUnitCreatePayload(entry);
  return (
    create.name ??
    entry.unitSuggestion?.name ??
    entry.unitOriginalName ??
    entry.unit ??
    ""
  );
};

const parseLocaleNumber = (value: string): number | null => {
  if (!value.trim()) {
    return null;
  }
  const normalized = value.replace(",", ".").trim();
  const parsed = Number.parseFloat(normalized);
  if (Number.isNaN(parsed)) {
    return null;
  }
  return parsed;
};

const enrichReviewData = (data: ReviewData): ReviewData => {
  const legacySummary = data.summary as Record<string, unknown>;
  const normalizedSummary = {
    ...data.summary,
    recipeServings:
      data.summary.recipeServings ??
      (typeof legacySummary.portions === "number" ? (legacySummary.portions as number) : null),
    totalTime:
      data.summary.totalTime ??
      (typeof legacySummary.totalTimeMinutes === "number"
        ? String(legacySummary.totalTimeMinutes)
        : (legacySummary.totalTimeMinutes as string | null) ??
          (typeof legacySummary.total_time_minutes === "number"
            ? String(legacySummary.total_time_minutes)
            : null))
  };

  return {
    ...data,
    summary: normalizedSummary,
    options: {
      foods: data.options?.foods ?? [],
      units: data.options?.units ?? [],
      foodCategories: data.options?.foodCategories ?? []
    },
    ingredients: data.ingredients.map((item) => ({
      ...item,
      notes: item.notes ?? "",
      foodSelection:
        item.foodSelection ??
        ({
          mealieFoodId: item.foodMatch?.id ?? null,
          newId: item.foodNewId ?? null,
          name: item.foodMatch?.name ?? item.name,
          badgeId: mapStatusToBadgeId(item.foodStatus),
          status: item.foodStatus ?? null
        } as FoodSelectionPayload),
      unitSelection:
        item.unitSelection ??
        ({
          mealieUnitId: item.unitMatch?.id ?? null,
          newId: item.unitNewId ?? null,
          name: item.unitMatch?.name ?? item.unit ?? "",
          badgeId: mapStatusToBadgeId(item.unitStatus),
          status: item.unitStatus ?? null
        } as UnitSelectionPayload)
    }))
  };
};

const createSummaryForm = (summary: ReviewData["summary"]): SummaryFormState => ({
  servingsInput: summary.recipeServings != null ? String(summary.recipeServings).replace(".", ",") : "",
  yieldQuantityInput: summary.recipeYieldQuantity != null ? String(summary.recipeYieldQuantity).replace(".", ",") : "",
  yieldTextInput: summary.recipeYield ?? "",
  totalTimeInput: summary.totalTime ?? "",
  prepTimeInput: summary.prepTime ?? "",
  performTimeInput: summary.performTime ?? "",
  notesInput: summary.notes ?? ""
});

const createPreparationSteps = (instructions: ReviewInstruction[]): Record<string, string> => {
  const steps: Record<string, string> = {};
  instructions.forEach((instruction) => {
    steps[instruction.id] = instruction.text;
  });
  return steps;
};

const createStepIngredientMap = (instructions: ReviewInstruction[]): Record<string, string[]> => {
  const map: Record<string, string[]> = {};
  instructions.forEach((instruction) => {
    map[instruction.id] = [...(instruction.ingredientIds ?? [])];
  });
  return map;
};

const buildUpdatePayload = (data: ReviewData) => ({
  summary: {
    title: data.summary.title,
      description: data.summary.description,
    notes: data.summary.notes ?? null,
    recipeServings: data.summary.recipeServings ?? null,
    recipeYieldQuantity: data.summary.recipeYieldQuantity ?? null,
    recipeYield: data.summary.recipeYield ?? null,
    totalTime: data.summary.totalTime ?? null,
    prepTime: data.summary.prepTime ?? null,
    performTime: data.summary.performTime ?? null,
    categoryId: data.summary.categoryId ?? null,
    tagIds: data.summary.tagIds ?? []
    },
  ingredients: data.ingredients.map((item) => ({
    id: item.id,
    notes: item.notes ?? "",
    ...(item.deleted ? { deleted: true } : {}),
    foodDecision: { ...item.foodDecision, notes: item.notes ?? "" },
    unitDecision: { ...item.unitDecision, notes: item.notes ?? "" },
    foodSelection: item.foodSelection ?? {
      mealieFoodId: item.foodMatch?.id ?? null,
      name: item.foodMatch?.name ?? item.name,
      badgeId: item.foodStatus ?? null,
      status: item.foodStatus ?? null,
      newId: item.foodNewId ?? null
    },
    unitSelection: item.unitSelection ?? {
      mealieUnitId: item.unitMatch?.id ?? null,
      name: item.unitMatch?.name ?? item.unit ?? "",
      badgeId: item.unitStatus ?? null,
      status: item.unitStatus ?? null,
      newId: item.unitNewId ?? null
    }
  })),
    instructions: data.instructions.map((item) => ({
      id: item.id,
      order: item.order,
      text: item.text,
      timerMinutes: item.timerMinutes ?? null,
      ingredientIds: (item.ingredientIds ?? []).filter((id) => {
        const ing = data.ingredients.find((x) => x.id === id);
        return !ing?.deleted;
      })
    }))
});

export const Step3Review: React.FC = () => {
  const { t } = useTranslation();
  const { runId, status, setError, setRecipeNameValue } = useImportFlow();
  const { setNextHandler, setNextDisabled } = useStepNavigation();
  const unitPlaceholder = t("review.selection.unitPlaceholder");
  const foodPlaceholder = t("review.selection.foodPlaceholder");
  const clearSelectionLabel = t("review.selection.clear");

  const [reviewData, setReviewData] = useState<ReviewData | null>(null);
  const [summaryForm, setSummaryForm] = useState<SummaryFormState>({
    servingsInput: "",
    yieldQuantityInput: "",
    yieldTextInput: "",
    totalTimeInput: "",
    prepTimeInput: "",
    performTimeInput: "",
    notesInput: ""
  });
  const [foodModalEntry, setFoodModalEntry] = useState<ReviewIngredient | null>(null);
  const [newFoodDraft, setNewFoodDraft] = useState<ReviewIngredient | null>(null);
  const [unitModalEntry, setUnitModalEntry] = useState<ReviewIngredient | null>(null);
  const [isTagModalOpen, setIsTagModalOpen] = useState(false);
  const [activeTagCategory, setActiveTagCategory] = useState<string | null>(null);
  const [isImageUploading, setIsImageUploading] = useState(false);
  const [imageError, setImageError] = useState<string | null>(null);
  const [isDragActive, setIsDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [isCropModalOpen, setIsCropModalOpen] = useState(false);
  const [imageOverrideUrl, setImageOverrideUrl] = useState<string | null>(null);
  const [pdfImages, setPdfImages] = useState<PdfImageOption[]>([]);
  const [selectedPdfImageId, setSelectedPdfImageId] = useState<string | null>(null);
  const [crop, setCrop] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [croppedAreaPixels, setCroppedAreaPixels] = useState<Area | null>(null);
  const [preparationSteps, setPreparationSteps] = useState<Record<string, string>>({});
  const [stepIngredients, setStepIngredients] = useState<Record<string, string[]>>({});
  const ingredientSelectionKeyRef = useRef<Record<string, string | null>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const isReadOnly = status === "transferring" || status === "completed";
  const visibleIngredients = useMemo(
    () => reviewData?.ingredients.filter((ing) => !ing.deleted) ?? [],
    [reviewData?.ingredients]
  );
  const sortedFoodOptions = useMemo(() => {
    if (!reviewData) {
      return [];
    }
    return [...reviewData.options.foods].sort(compareCandidateOptions);
  }, [reviewData]);
  const sortedUnitOptions = useMemo(() => {
    if (!reviewData) {
      return [];
    }
    return [...reviewData.options.units].sort(compareCandidateOptions);
  }, [reviewData]);
  const sortedFoodCategories = useMemo(() => {
    if (!reviewData) {
      return [];
    }
    return [...reviewData.options.foodCategories].sort((a, b) => {
      const left = (a.name ?? a.id ?? "").toString();
      const right = (b.name ?? b.id ?? "").toString();
      return left.localeCompare(right, undefined, { sensitivity: "base" });
    });
  }, [reviewData]);
  const sortedCategoryOptions = useMemo(() => {
    if (!reviewData) {
      return [];
    }
    return (reviewData.summary.availableCategories || [])
      .map((category) => ({
        id: category.id,
        name: category.name ?? category.id
      }))
      .sort(compareCandidateOptions);
  }, [reviewData]);
  const sortedTagOptions = useMemo(() => {
    if (!reviewData) {
      return [];
    }
    const groups = reviewData.summary.availableTagCategories || [];
    const flattened: TagOption[] = [];
    groups.forEach((group) => {
      (group.tags || []).forEach((tag) => {
        if (tag.id) {
          const splitParts = (value: string | null | undefined) =>
            (value || "")
              .split("|")
              .map((part) => part.trim())
              .filter(Boolean);
          const nameParts = splitParts(tag.name);
          const detailParts = splitParts(tag.detail ?? tag.name);
          const categoryFromName = nameParts.length > 1 ? nameParts[0] : undefined;
          const category = group.category ?? categoryFromName ?? tag.category ?? null;
          const detail =
            (detailParts.length > 1 && detailParts.slice(1).join(" | ")) ||
            (detailParts.length === 1 ? detailParts[0] : nameParts.slice(1).join(" | ")) ||
            detailParts.join(" | ") ||
            nameParts.slice(1).join(" | ") ||
            tag.detail ||
            tag.name ||
            tag.id;
          flattened.push({
            ...tag,
            name: detail,
            detail: detail,
            category
          });
        }
      });
    });
    return flattened.sort((a, b) => {
      const left = (a.name ?? a.id ?? "").toString();
      const right = (b.name ?? b.id ?? "").toString();
      return left.localeCompare(right, undefined, { sensitivity: "base" });
    });
  }, [reviewData]);
  const availableTagCategories = useMemo(() => {
    if (!reviewData) {
      return [];
    }
    const categories = (reviewData.summary.availableTagCategories || [])
      .map((group) => group.category)
      .filter((category): category is string => Boolean(category));
    return Array.from(new Set(categories));
  }, [reviewData]);
  const selectedTagDetails = useMemo(() => {
    if (!reviewData) {
      return [];
    }
    const ids = reviewData.summary.tagIds ?? [];
    return ids.map((id) => {
      const match = sortedTagOptions.find((option) => option.id === id);
      return (
        match ?? {
          id,
          name: id,
          category: null,
          detail: null
        }
      );
    });
  }, [reviewData, sortedTagOptions]);
  const stepIngredientOptions = useMemo<StepIngredientOption[]>(() => {
    if (!visibleIngredients.length) {
      return [];
    }
    const options = visibleIngredients
      .map((ingredient) => {
        const selectedFoodId =
          ingredient.foodSelection?.newId ??
          ingredient.foodSelection?.mealieFoodId ??
          ingredient.foodMatch?.id ??
          null;
        if (!selectedFoodId) {
          return null;
        }
        const foodLabel =
          ingredient.foodSelection?.newId
            ? getFoodSuggestionBaseName(ingredient)
            : ingredient.foodMatch?.name ?? ingredient.foodSelection?.name ?? ingredient.name;
        if (!foodLabel) {
          return null;
        }
        return {
          id: ingredient.id,
          foodLabel
        };
      })
      .filter((option): option is StepIngredientOption => Boolean(option));
    options.sort((a, b) => a.foodLabel.localeCompare(b.foodLabel, undefined, { sensitivity: "base" }));
    return options;
  }, [visibleIngredients]);
  const stepIngredientOptionMap = useMemo(() => {
    const map = new Map<string, StepIngredientOption>();
    stepIngredientOptions.forEach((option) => {
      map.set(option.id, option);
    });
    return map;
  }, [stepIngredientOptions]);
  const formatStepIngredientLabel = useCallback((option: StepIngredientOption) => option.foodLabel, []);
  const imageAspectClass = layoutConfig.images?.aspectRatio ?? "aspect-video";

  const resolveAssetUrl = useCallback((rawUrl: string | null | undefined) => {
    if (!rawUrl) {
      return null;
    }
    if (/^https?:\/\//i.test(rawUrl)) {
      return rawUrl;
    }
    if (BASE_URL.startsWith("http")) {
      const apiRoot = BASE_URL.replace(/\/api$/, "");
      return `${apiRoot}${rawUrl}`;
    }
    return rawUrl;
  }, []);

  const currentImageUrl = useMemo(() => {
    if (imageOverrideUrl) {
      return imageOverrideUrl;
    }
    return resolveAssetUrl(reviewData?.assets?.imageUrl);
  }, [imageOverrideUrl, resolveAssetUrl, reviewData?.assets?.imageUrl]);
  const currentPdfUrl = useMemo(() => {
    const rawUrl = reviewData?.assets?.pdfUrl;
    if (!rawUrl) {
      return null;
    }
    if (/^https?:\/\//i.test(rawUrl)) {
      return rawUrl;
    }
    if (BASE_URL.startsWith("http")) {
      const apiRoot = BASE_URL.replace(/\/api$/, "");
      return `${apiRoot}${rawUrl}`;
    }
    return rawUrl;
  }, [reviewData?.assets?.pdfUrl]);

  const autoResizeTextarea = useCallback((textarea: HTMLTextAreaElement | null) => {
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${textarea.scrollHeight}px`;
  }, []);

  useEffect(() => {
    if (!runId) {
      setReviewData(null);
      setSummaryForm({
        servingsInput: "",
        yieldQuantityInput: "",
        yieldTextInput: "",
        totalTimeInput: "",
        prepTimeInput: "",
        performTimeInput: ""
      });
      setPreparationSteps({});
      setStepIngredients({});
      return;
    }

    let isActive = true;
    setIsLoading(true);
    setLoadError(null);

    fetchReviewData(runId)
      .then((data) => {
        if (!isActive) return;
        const enriched = enrichReviewData(data);
        setReviewData(enriched);
        setImageOverrideUrl(null);
        setSummaryForm(createSummaryForm(enriched.summary));
        setPreparationSteps(createPreparationSteps(enriched.instructions));
        setStepIngredients(createStepIngredientMap(enriched.instructions));
        setRecipeNameValue(enriched.summary.title);
      })
      .catch((error: Error) => {
        if (!isActive) return;
        setLoadError(error.message);
        setReviewData(null);
      })
      .finally(() => {
        if (isActive) {
          setIsLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, [runId, setRecipeNameValue]);

  useEffect(() => {
    if (!runId) {
      setPdfImages([]);
      setSelectedPdfImageId(null);
      return;
    }
    fetchPdfImages(runId)
      .then((images) => {
        setPdfImages(images);
        setSelectedPdfImageId(images[0]?.id ?? null);
      })
      .catch(() => {
        setPdfImages([]);
        setSelectedPdfImageId(null);
      });
  }, [runId]);

  useEffect(() => {
    if (reviewData?.summary.title) {
      setRecipeNameValue(reviewData.summary.title);
    }
  }, [reviewData?.summary.title, setRecipeNameValue]);

  const persistChanges = useCallback(
    async (overrideData?: ReviewData | null) => {
      const snapshot = overrideData ?? reviewData;
      if (!runId || !snapshot || isReadOnly) {
        return;
      }
      setIsSaving(true);
      setSaveError(null);
      try {
        const payload = buildUpdatePayload(snapshot);
        const updated = await updateReviewData(runId, payload);
        const enriched = enrichReviewData(updated);
        setReviewData(enriched);
        setImageOverrideUrl(null);
        setSummaryForm(createSummaryForm(enriched.summary));
      setPreparationSteps(createPreparationSteps(enriched.instructions));
      setStepIngredients((prev) => {
        const next = createStepIngredientMap(enriched.instructions);
        // avoid needless state churn if unchanged
        const same =
          Object.keys(prev).length === Object.keys(next).length &&
          Object.entries(next).every(([k, v]) => {
            const prevIds = prev[k] || [];
            return prevIds.length === v.length && prevIds.every((id, idx) => id === v[idx]);
          });
        return same ? prev : next;
      });
      } catch (error) {
        setSaveError(error instanceof Error ? error.message : String(error));
      } finally {
        setIsSaving(false);
      }
    },
    [runId, reviewData, isReadOnly]
  );

  const updateInstructionIngredients = useCallback(
    (instructionId: string, ingredientIds: string[]) => {
      if (isReadOnly) return;
      setReviewData((previous) => {
        if (!previous) return previous;
        const updated = {
          ...previous,
          instructions: previous.instructions.map((inst) =>
            inst.id === instructionId ? { ...inst, ingredientIds } : inst
          )
        };
        void persistChanges(updated);
        return updated;
      });
    },
    [isReadOnly, persistChanges]
  );

  useEffect(() => {
    const disabled = !runId || !reviewData || isSaving || isLoading;
    setNextDisabled(disabled);
  }, [isLoading, isSaving, reviewData, runId, setNextDisabled]);

  useEffect(() => {
    setNextHandler(() => async () => {
      if (!runId || !reviewData) {
        return false;
      }
      setNextDisabled(true);
      try {
        await persistChanges();
        setError(null);
        return true;
      } catch (transferError) {
        const message = transferError instanceof Error ? transferError.message : String(transferError);
        setError(message);
        setNextDisabled(false);
        return false;
      }
    });
    return () => {
      setNextHandler(null);
    };
  }, [persistChanges, runId, setError, setNextDisabled, setNextHandler, reviewData]);

  useEffect(() => {
    if (!reviewData) {
      ingredientSelectionKeyRef.current = {};
      return;
    }
    const nextKeys: Record<string, string | null> = {};
    const removalIds: string[] = [];
    (visibleIngredients || []).forEach((ingredient) => {
      const key = getIngredientSelectionKey(ingredient);
      nextKeys[ingredient.id] = key;
      const previous = ingredientSelectionKeyRef.current[ingredient.id];
      if (previous !== undefined && previous !== key) {
        removalIds.push(ingredient.id);
      }
    });
    ingredientSelectionKeyRef.current = nextKeys;
    if (removalIds.length > 0) {
      const removalSet = new Set(removalIds);
      setStepIngredients((previous) => {
        if (Object.keys(previous).length === 0) {
          return previous;
        }
        let changed = false;
        const nextEntries = Object.entries(previous).map(([stepId, ids]) => {
          const filtered = ids.filter((id) => !removalSet.has(id));
          if (filtered.length !== ids.length) {
            changed = true;
          }
          return [stepId, filtered];
        });
        if (!changed) {
          return previous;
        }
        return Object.fromEntries(nextEntries) as Record<string, string[]>;
      });
    }
  }, [reviewData?.ingredients, visibleIngredients]);

  useEffect(() => {
    if (stepIngredientOptions.length === 0) {
      setStepIngredients((previous) => {
        if (Object.values(previous).every((items) => items.length === 0)) {
          return previous;
        }
        const cleared = Object.fromEntries(
          Object.keys(previous).map((stepId) => [stepId, [] as string[]])
        ) as Record<string, string[]>;
        return cleared;
      });
      return;
    }
    const allowedIds = new Set(stepIngredientOptions.map((option) => option.id));
    setStepIngredients((previous) => {
      if (Object.keys(previous).length === 0) {
        return previous;
      }
      let changed = false;
      const nextEntries = Object.entries(previous).map(([stepId, ids]) => {
        const filtered = ids.filter((id) => allowedIds.has(id));
        if (filtered.length !== ids.length) {
          changed = true;
        }
        return [stepId, filtered];
      });
      if (!changed) {
        return previous;
      }
      return Object.fromEntries(nextEntries) as Record<string, string[]>;
    });
  }, [stepIngredientOptions]);

  const handleSummaryFieldChange = useCallback(
    (field: "title" | "description" | "notes", value: string) => {
      setReviewData((previous) => {
        if (!previous) {
          return previous;
        }
        return {
          ...previous,
          summary: {
            ...previous.summary,
            [field]: value
          }
        };
      });
    },
    []
  );

  const handleServingsChange = useCallback((value: string) => {
    setSummaryForm((previous) => ({ ...previous, servingsInput: value }));
    setReviewData((previous) => {
      if (!previous) {
        return previous;
      }
      return {
        ...previous,
        summary: {
          ...previous.summary,
          recipeServings: parseLocaleNumber(value)
        }
      };
    });
  }, []);

  const handleTotalTimeChange = useCallback((value: string) => {
    setSummaryForm((previous) => ({ ...previous, totalTimeInput: value }));
    setReviewData((previous) => {
      if (!previous) {
        return previous;
      }
      return {
        ...previous,
        summary: {
          ...previous.summary,
          totalTime: value
        }
      };
    });
  }, []);

  const handleYieldQuantityChange = useCallback((value: string) => {
    setSummaryForm((previous) => ({ ...previous, yieldQuantityInput: value }));
    setReviewData((previous) => {
      if (!previous) {
        return previous;
      }
      return {
        ...previous,
        summary: {
          ...previous.summary,
          recipeYieldQuantity: parseLocaleNumber(value)
        }
      };
    });
  }, []);

  const handleYieldTextChange = useCallback((value: string) => {
    setSummaryForm((previous) => ({ ...previous, yieldTextInput: value }));
    setReviewData((previous) => {
      if (!previous) {
        return previous;
      }
      return {
        ...previous,
        summary: {
          ...previous.summary,
          recipeYield: value
        }
      };
    });
  }, []);

  const handleNotesChange = useCallback((value: string) => {
    setSummaryForm((previous) => ({ ...previous, notesInput: value }));
    setReviewData((previous) => {
      if (!previous) {
        return previous;
      }
      return {
        ...previous,
        summary: {
          ...previous.summary,
          notes: value
        }
      };
    });
  }, []);

  const handlePrepTimeChange = useCallback((value: string) => {
    setSummaryForm((previous) => ({ ...previous, prepTimeInput: value }));
    setReviewData((previous) => {
      if (!previous) {
        return previous;
      }
      return {
        ...previous,
        summary: {
          ...previous.summary,
          prepTime: value
        }
      };
    });
  }, []);

  const handlePerformTimeChange = useCallback((value: string) => {
    setSummaryForm((previous) => ({ ...previous, performTimeInput: value }));
    setReviewData((previous) => {
      if (!previous) {
        return previous;
      }
      return {
        ...previous,
        summary: {
          ...previous.summary,
          performTime: value
        }
      };
    });
  }, []);

  const handleCategorySelect = useCallback(
    (option: CandidateOption | null) => {
      if (isReadOnly) return;
      setReviewData((previous) => {
        if (!previous) {
          return previous;
        }
        const updated = {
          ...previous,
          summary: {
            ...previous.summary,
            categoryId: option?.id ?? null
          }
        };
        void persistChanges(updated);
        return updated;
      });
    },
    [persistChanges]
  );

  const handleTagsChange = useCallback(
    (ids: string[]) => {
      if (isReadOnly) return;
      setReviewData((previous) => {
        if (!previous) {
          return previous;
        }
        const updated = {
          ...previous,
          summary: {
            ...previous.summary,
            tagIds: ids
          }
        };
        void persistChanges(updated);
        return updated;
      });
    },
    [persistChanges]
  );

  const handleTagChipRemove = useCallback(
    (id: string) => {
      if (isReadOnly) return;
      const currentIds = reviewData?.summary.tagIds ?? [];
      handleTagsChange(currentIds.filter((tagId) => tagId !== id));
    },
    [handleTagsChange, reviewData?.summary.tagIds, isReadOnly]
  );

  const handleCategoryFilterToggle = useCallback((category: string | null) => {
    setActiveTagCategory(category);
  }, []);

  const handleImageUpload = useCallback(
    async (file: File | null | undefined) => {
      if (!runId || !file || isReadOnly) {
        return;
      }
      setIsImageUploading(true);
      setImageError(null);
      try {
        const response = await uploadRecipeImage(runId, file);
        const resolvedUrl = resolveAssetUrl(response.imageUrl);
        setReviewData((previous) => {
          if (!previous) {
            return previous;
          }
          return {
            ...previous,
            assets: {
              ...previous.assets,
              imageUrl: response.imageUrl
            }
          };
        });
        setImageOverrideUrl(resolvedUrl);
      } catch (error) {
        setImageError(error instanceof Error ? error.message : String(error));
      } finally {
        setIsImageUploading(false);
      }
    },
    [runId, resolveAssetUrl]
  );

  const handleCropComplete = useCallback((_croppedArea: Area, areaPixels: Area) => {
    setCroppedAreaPixels(areaPixels);
  }, []);

  // Reset Cropper state when das Bild wechselt oder der Dialog neu geöffnet wird
  useEffect(() => {
    if (!isCropModalOpen) return;
    setCrop({ x: 0, y: 0 });
    setZoom(1);
    setCroppedAreaPixels(null);
  }, [currentImageUrl, isCropModalOpen]);

  const handleCropSave = useCallback(async () => {
    if (!currentImageUrl || !croppedAreaPixels) {
      return;
    }
    try {
      const blob = await getCroppedBlob(currentImageUrl, croppedAreaPixels);
      if (!blob) {
        return;
      }
      const file = new File([blob], `cropped-${Date.now()}.jpg`, { type: blob.type || "image/jpeg" });
      await handleImageUpload(file);
      setIsCropModalOpen(false);
    } catch (error) {
      setImageError(error instanceof Error ? error.message : String(error));
    }
  }, [croppedAreaPixels, currentImageUrl, handleImageUpload]);

  const handleDropZoneDragOver = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragActive(true);
  }, []);

  const handleDropZoneDragLeave = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (event.currentTarget.contains(event.relatedTarget as Node)) {
      return;
    }
    setIsDragActive(false);
  }, []);

  const handleDropZoneDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setIsDragActive(false);
      const files = event.dataTransfer?.files;
      if (files && files.length > 0) {
        const file = Array.from(files).find((item) => item.type.startsWith("image/")) ?? files[0];
        void handleImageUpload(file);
      }
    },
    [handleImageUpload]
  );

  const dataUrlToFile = useCallback(async (dataUrl: string, name: string): Promise<File> => {
    const res = await fetch(dataUrl);
    const blob = await res.blob();
    return new File([blob], name, { type: blob.type || "image/jpeg" });
  }, []);

  const handleApplyPdfImage = useCallback(
    async (id?: string) => {
      const targetId = id ?? selectedPdfImageId;
      if (!targetId) return;
      const candidate = pdfImages.find((img) => img.id === targetId);
    if (!candidate) return;
    try {
      const file = await dataUrlToFile(candidate.dataUrl, `${candidate.id}.jpg`);
      await handleImageUpload(file);
      setImageOverrideUrl(candidate.dataUrl);
    } catch (error) {
      setImageError(error instanceof Error ? error.message : String(error));
    }
  },
    [dataUrlToFile, handleImageUpload, pdfImages, selectedPdfImageId]);

  const handleDeleteIngredient = useCallback(
    (ingredientId: string) => {
      if (isReadOnly) return;
      setReviewData((previous) => {
        if (!previous) {
          return previous;
        }
        const nextIngredients = previous.ingredients.map((item) =>
          item.id === ingredientId ? { ...item, deleted: true } : item
        );
        const nextStepIngredients: Record<string, string[]> = {};
        Object.entries(stepIngredients).forEach(([stepId, ids]) => {
          const filtered = ids.filter((id) => id !== ingredientId);
          if (filtered.length > 0) {
            nextStepIngredients[stepId] = filtered;
          }
        });
        const nextInstructions = previous.instructions.map((instruction) => ({
          ...instruction,
          ingredientIds: (instruction.ingredientIds || []).filter((id) => id !== ingredientId)
        }));
        const nextData: ReviewData = {
          ...previous,
          ingredients: nextIngredients,
          instructions: nextInstructions
        };
        setStepIngredients(nextStepIngredients);
        void persistChanges(nextData);
        return nextData;
      });
    },
    [isReadOnly, persistChanges, stepIngredients]
  );

  useEffect(() => {
    if (!isCropModalOpen) {
      setZoom(1);
      setCrop({ x: 0, y: 0 });
      setCroppedAreaPixels(null);
    }
  }, [isCropModalOpen]);

  const handleNoteChange = useCallback((entry: ReviewIngredient, value: string) => {
    if (isReadOnly) return;
    setReviewData((previous) => {
      if (!previous) {
        return previous;
      }
      return {
        ...previous,
        ingredients: previous.ingredients.map((item) =>
          item.id === entry.id
            ? {
                ...item,
                notes: value,
                foodDecision: { ...item.foodDecision, notes: value },
                unitDecision: { ...item.unitDecision, notes: value }
              }
            : item
        )
      };
    });
  }, [isReadOnly]);

  const handleFoodModalSave = useCallback(
    (ingredientId: string, values: FoodCreateFormValues) => {
      if (isReadOnly) return;
      setReviewData((previous) => {
        if (!previous) {
          return previous;
        }
        const updatedIngredients = previous.ingredients.map((item) => {
          if (item.id !== ingredientId) {
            return item;
          }
          const newId = item.foodNewId ?? item.foodSelection?.newId ?? `manual-${ingredientId}`;
          const nextCreate = {
            ...getFoodCreatePayload(item),
            ...values
          };
          const nextDecision = {
            ...(item.foodDecision || {}),
            create: nextCreate
          };
          return {
            ...item,
            foodDecision: nextDecision,
            foodMatch: null,
            foodStatus: "new",
            foodNewId: newId,
            foodSelection: {
              mealieFoodId: null,
              newId,
              name: values.nameSingular || item.name,
              badgeId: "new",
              status: "new"
            }
          };
        });
        const nextData = { ...previous, ingredients: updatedIngredients };
        void persistChanges(nextData);
        return nextData;
      });
      setFoodModalEntry(null);
      setNewFoodDraft(null);
    },
    [persistChanges]
  );

  const handleUnitModalSave = useCallback(
    (ingredientId: string, values: UnitCreateFormValues) => {
      if (isReadOnly) return;
      setReviewData((previous) => {
        if (!previous) {
          return previous;
        }
        const updatedIngredients = previous.ingredients.map((item) => {
          if (item.id !== ingredientId) {
            return item;
          }
          const nextCreate = {
            ...getUnitCreatePayload(item),
            ...values
          };
          const nextDecision = {
            ...(item.unitDecision || {}),
            create: nextCreate
          };
          return {
            ...item,
            unitDecision: nextDecision
          };
        });
        const nextData = { ...previous, ingredients: updatedIngredients };
        void persistChanges(nextData);
        return nextData;
      });
      setUnitModalEntry(null);
    },
    [persistChanges]
  );

  const handleInstructionChange = useCallback((instruction: ReviewInstruction, value: string) => {
    if (isReadOnly) return;
    setPreparationSteps((previous) => ({
      ...previous,
      [instruction.id]: value
    }));
    setReviewData((previous) => {
      if (!previous) {
        return previous;
      }
      return {
        ...previous,
        instructions: previous.instructions.map((item) =>
          item.id === instruction.id
            ? {
                ...item,
                text: value
              }
            : item
        )
      };
    });
  }, [isReadOnly]);

  const handleUnitSelection = useCallback(
    (ingredientId: string, option: CandidateOption | null) => {
      if (isReadOnly) return;
      setReviewData((previous) => {
        if (!previous) {
          return previous;
        }
        const updatedIngredients = previous.ingredients.map((item) => {
          if (item.id !== ingredientId) {
            return item;
          }
          const isSuggestion = option ? option.id === item.unitNewId : false;
          const nextBadge: BadgeId = isSuggestion ? "new" : option ? "manual" : "none";
          const updatedItem: ReviewIngredient = {
            ...item,
            unitMatch: isSuggestion
              ? null
              : option
                ? { id: option.id, name: option.name ?? "", strategy: "manual" }
                : null,
            unitStatus: isSuggestion ? "new" : option ? "manual" : "none",
            unitSelection: {
              mealieUnitId: isSuggestion ? null : option?.id ?? null,
              newId: isSuggestion ? item.unitNewId ?? option?.id ?? null : null,
              name: isSuggestion ? getUnitSuggestionBaseName(item) : option?.name ?? item.unit ?? "",
              badgeId: nextBadge,
              status: nextBadge
            }
          };
          return updatedItem;
        });
        const nextData = { ...previous, ingredients: updatedIngredients };
        void persistChanges(nextData);
        return nextData;
      });
    },
    [persistChanges]
  );

  const handleFoodSelection = useCallback(
    (ingredientId: string, option: CandidateOption | null) => {
      if (isReadOnly) return;
      setReviewData((previous) => {
        if (!previous) {
          return previous;
        }
        const updatedIngredients = previous.ingredients.map((item) => {
          if (item.id !== ingredientId) {
            return item;
          }
          const isSuggestion = option ? option.id === item.foodNewId : false;
          const nextBadge: BadgeId = isSuggestion ? "new" : option ? "manual" : "new";
          const updatedItem: ReviewIngredient = {
            ...item,
            foodMatch: isSuggestion
              ? null
              : option
                ? { id: option.id, name: option.name ?? "", strategy: "manual" }
                : null,
            foodStatus: isSuggestion ? "new" : option ? "manual" : "new",
            foodSelection: {
              mealieFoodId: isSuggestion ? null : option?.id ?? null,
              newId: isSuggestion ? item.foodNewId ?? option?.id ?? null : null,
              name: isSuggestion ? getFoodSuggestionBaseName(item) : option?.name ?? item.name,
              badgeId: nextBadge,
              status: nextBadge
            }
          };
          return updatedItem;
        });
        const nextData = { ...previous, ingredients: updatedIngredients };
        void persistChanges(nextData);
        return nextData;
      });
    },
    [persistChanges]
  );

  if (!runId) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-text/70">
        {t("review.noRunSelected")}
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-text/70">
        {t("review.loading")}
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-error">
        {loadError}
      </div>
    );
  }

  if (!reviewData) {
    return null;
  }

  return (
    <div className={clsx(layoutConfig.step3.grid.gridClasses, layoutConfig.spacing.layout.columns)}>
      <div
        className={clsx(
          "flex flex-col border border-border bg-panel xl:min-h-0 xl:h-full xl:overflow-hidden",
          layoutConfig.borderRadius.large,
          layoutConfig.shadow.panel
        )}
      >
        <div
          className={clsx(
            "scrollbar-rounded xl:min-h-0 xl:flex-1 xl:overflow-y-auto",
            layoutConfig.spacing.section.padding.x,
            layoutConfig.spacing.section.padding.y
          )}
          style={{ scrollbarGutter: "stable" }}
        >
          {isReadOnly ? (
            <div className="mb-4 rounded border border-border/70 bg-warning/10 px-4 py-3 text-sm text-text/80">
              {t("review.readonlyNotice")}
            </div>
          ) : null}
          <div className={clsx("pb-6", layoutConfig.spacing.section.vertical)}>
            <div
              className={clsx(
                "overflow-hidden border border-border bg-background shadow-sm",
                layoutConfig.borderRadius.medium
              )}
            >
              <div
                className={clsx(
                  "border-b border-border",
                  layoutConfig.spacing.section.padding.x,
                  layoutConfig.spacing.section.padding.y
                )}
              >
                <input
                  disabled={isReadOnly}
                  value={reviewData.summary.title}
                  onChange={(event) => handleSummaryFieldChange("title", event.target.value)}
                  onBlur={() => persistChanges()}
                  className={clsx(
                    "focus-ring w-full border border-border bg-background px-4 py-3 text-xl font-semibold text-primary",
                    layoutConfig.borderRadius.medium
                  )}
                />
                <textarea
                  disabled={isReadOnly}
                  value={reviewData.summary.description}
                  onChange={(event) => {
                    handleSummaryFieldChange("description", event.target.value);
                    autoResizeTextarea(event.target);
                  }}
                  onBlur={() => persistChanges()}
                  ref={(el) => autoResizeTextarea(el)}
                  rows={1}
                  className={clsx(
                    "focus-ring mt-4 w-full resize-none overflow-hidden border border-border bg-background px-4 py-3 text-sm leading-relaxed text-text/75",
                    layoutConfig.borderRadius.medium
                  )}
                />
              </div>
              <div
                className={clsx(
                  "grid gap-4 border-t border-border px-4 py-4",
                  "md:grid-cols-3"
                )}
              >
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wide text-text/60">
                    {t("review.meta.portions")}
                  </label>
                <input
                  disabled={isReadOnly}
                  value={summaryForm.servingsInput}
                  onChange={(event) => handleServingsChange(event.target.value)}
                  onBlur={() => persistChanges()}
                  className={clsx(
                    "focus-ring mt-1 w-full border border-border bg-background px-3 py-2 text-sm font-semibold text-text/85",
                      layoutConfig.borderRadius.medium
                    )}
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wide text-text/60">
                    {t("review.meta.recipeYieldQuantity")}
                  </label>
                <input
                  disabled={isReadOnly}
                  value={summaryForm.yieldQuantityInput}
                  onChange={(event) => handleYieldQuantityChange(event.target.value)}
                  onBlur={() => persistChanges()}
                  className={clsx(
                    "focus-ring mt-1 w-full border border-border bg-background px-3 py-2 text-sm font-semibold text-text/85",
                      layoutConfig.borderRadius.medium
                    )}
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wide text-text/60">
                    {t("review.meta.recipeYield")}
                  </label>
                <input
                  disabled={isReadOnly}
                  value={summaryForm.yieldTextInput}
                  onChange={(event) => handleYieldTextChange(event.target.value)}
                  onBlur={() => persistChanges()}
                  className={clsx(
                    "focus-ring mt-1 w-full border border-border bg-background px-3 py-2 text-sm font-semibold text-text/85",
                      layoutConfig.borderRadius.medium
                    )}
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wide text-text/60">
                    {t("review.meta.totalTime")}
                  </label>
                <input
                  disabled={isReadOnly}
                  value={summaryForm.totalTimeInput}
                  onChange={(event) => handleTotalTimeChange(event.target.value)}
                  onBlur={() => persistChanges()}
                  className={clsx(
                    "focus-ring mt-1 w-full border border-border bg-background px-3 py-2 text-sm font-semibold text-text/85",
                      layoutConfig.borderRadius.medium
                    )}
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wide text-text/60">
                    {t("review.meta.prepTime")}
                  </label>
                <input
                  disabled={isReadOnly}
                  value={summaryForm.prepTimeInput}
                  onChange={(event) => handlePrepTimeChange(event.target.value)}
                  onBlur={() => persistChanges()}
                  className={clsx(
                    "focus-ring mt-1 w-full border border-border bg-background px-3 py-2 text-sm font-semibold text-text/85",
                      layoutConfig.borderRadius.medium
                    )}
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wide text-text/60">
                    {t("review.meta.performTime")}
                  </label>
                <input
                  disabled={isReadOnly}
                  value={summaryForm.performTimeInput}
                  onChange={(event) => handlePerformTimeChange(event.target.value)}
                  onBlur={() => persistChanges()}
                  className={clsx(
                    "focus-ring mt-1 w-full border border-border bg-background px-3 py-2 text-sm font-semibold text-text/85",
                      layoutConfig.borderRadius.medium
                    )}
                  />
                </div>
              </div>
              {isSaving ? (
                <div className="border-t border-border bg-background/80 px-4 py-2 text-xs text-text/60">
                  {t("review.saving")}
                </div>
              ) : saveError ? (
                <div className="border-t border-border bg-error/10 px-4 py-2 text-xs text-error">{saveError}</div>
              ) : null}
            </div>

            <div
              className={clsx(
                "border border-border bg-background px-4 py-4 shadow-sm",
                layoutConfig.spacing.element.vertical,
                layoutConfig.spacing.layout.container.x,
                layoutConfig.spacing.layout.container.y,
                layoutConfig.borderRadius.medium
              )}
            >
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-text/60">
                  {t("review.meta.category")}
                </label>
                <div className="mt-1">
                  <SearchableSelect
                    disabled={isReadOnly || sortedCategoryOptions.length === 0}
                    options={sortedCategoryOptions}
                    selectedId={reviewData.summary.categoryId ?? null}
                    displayValue={
                      sortedCategoryOptions.find((option) => option.id === (reviewData.summary.categoryId ?? ""))?.name ??
                      ""
                    }
                    placeholder={t("review.meta.categoryPlaceholder")}
                    clearLabel={t("review.selection.clear")}
                    onChange={(option) => handleCategorySelect(option)}
                  />
                </div>
              </div>
              <div className="mt-4">
                <label className="text-xs font-semibold uppercase tracking-wide text-text/60">
                  {t("review.meta.tags")}
                </label>
                <div className="mt-1 flex items-start gap-2">
                  <div
                    className={clsx(
                      "flex min-h-[44px] flex-1 flex-wrap gap-2 border border-border bg-background px-3 py-2",
                      layoutConfig.borderRadius.medium
                    )}
                  >
                    {selectedTagDetails.length === 0 ? (
                      <span className="text-sm text-text/50">{t("review.meta.tagsPlaceholder")}</span>
                    ) : (
                      selectedTagDetails.map((tag) => {
                        const rawName = tag.name ?? tag.id;
                        const rawDetail = tag.detail ?? rawName;
                        const splitParts = (value: string | null | undefined) =>
                          (value || "")
                            .split("|")
                            .map((part) => part.trim())
                            .filter(Boolean);

                        const detailParts = splitParts(rawDetail);
                        const nameParts = splitParts(rawName);

                        const inferredCategory = tag.category ?? (nameParts.length > 1 ? nameParts[0] : undefined);

                        let detail = detailParts.join(" | ");
                        if (inferredCategory && detail.startsWith(`${inferredCategory} |`)) {
                          detail = detailParts.slice(1).join(" | ");
                        }
                        if (!detail && nameParts.length > 1) {
                          detail = nameParts.slice(1).join(" | ");
                        }
                        if (!detail) {
                          detail = rawDetail || rawName || tag.id;
                        }

                        const display = inferredCategory ? `${inferredCategory} | ${detail}` : detail;
                        return (
                          <span
                            key={tag.id}
                            className={clsx(
                              "inline-flex items-center border border-primary/30 bg-primary/10 px-2 py-1 text-xs font-semibold text-primary",
                              layoutConfig.borderRadius.small
                            )}
                          >
                            {display}
                            <button
                              disabled={isReadOnly}
                              type="button"
                              onClick={() => handleTagChipRemove(tag.id)}
                              className="ml-1 text-primary hover:text-primary/70 disabled:opacity-50"
                              aria-label={t("review.meta.removeTag")}
                            >
                              ×
                            </button>
                          </span>
                        );
                      })
                    )}
                  </div>
                  <button
                    disabled={isReadOnly}
                    type="button"
                    onClick={() => setIsTagModalOpen(true)}
                    className={clsx(
                      "focus-ring inline-flex h-9 w-9 items-center justify-center border border-border bg-background hover:border-primary/60 hover:text-primary disabled:opacity-50",
                      layoutConfig.borderRadius.small
                    )}
                    aria-label={t("review.meta.editTags")}
                    title={t("review.meta.editTags")}
                  >
                    <PencilSquareIcon className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
                <div className="mt-4">
                  <label className="text-xs font-semibold uppercase tracking-wide text-text/60">
                    {t("review.meta.notes")}
                  </label>
                  <textarea
                    rows={2}
                    className={clsx(
                      "focus-ring mt-1 w-full border border-border bg-background px-3 py-2 text-sm text-text",
                      layoutConfig.borderRadius.medium
                    )}
                    value={summaryForm.notesInput}
                    onChange={(event) => handleNotesChange(event.target.value)}
                    placeholder={t("review.meta.notesPlaceholder")}
                    disabled={isReadOnly}
                  />
                </div>
              </div>
            </div>

            <div
              className={clsx(
                "border border-border bg-background shadow-sm",
                layoutConfig.spacing.element.vertical,
                layoutConfig.spacing.layout.container.x,
                layoutConfig.spacing.layout.container.y,
                layoutConfig.borderRadius.medium
              )}
            >
              <header>
                <h3 className="text-lg font-semibold">{t("review.sections.ingredients")}</h3>
              </header>
              <div className={layoutConfig.spacing.item.vertical}>
                {visibleIngredients.map((entry) => {
                  const displayAmount =
                    entry.amountText ??
                    (entry.amount != null ? String(entry.amount).replace(".", ",") : "") ??
                    "";
                  const hasAmount = Boolean(displayAmount.trim() || entry.amount != null);
                  const unitBadgeId =
                    (!hasAmount ? ("no_amount" as BadgeId) : undefined) ??
                    (entry.unitSelection?.badgeId as BadgeId | undefined) ??
                    mapStatusToBadgeId(entry.unitStatus) ??
                    null;
                  const foodBadgeId =
                    (entry.foodSelection?.badgeId as BadgeId | undefined) ??
                    mapStatusToBadgeId(entry.foodStatus) ??
                    null;
                  const originalUnitLabel = entry.unitOriginalName ?? entry.unit ?? "";
                  const originalFoodLabel = entry.foodOriginalName ?? entry.name;
                  const unitSuggestionLabel = getUnitSuggestionBaseName(entry);
                  const foodSuggestionLabel = getFoodSuggestionBaseName(entry);
                  const unitSuggestionOption =
                    entry.unitNewId && unitSuggestionLabel
                      ? {
                          id: entry.unitNewId,
                          name: t("review.selection.newUnitOption", { value: unitSuggestionLabel })
                        }
                      : null;
                  const foodSuggestionOption =
                    entry.foodNewId && foodSuggestionLabel
                      ? {
                          id: entry.foodNewId,
                          name: t("review.selection.newFoodOption", { value: foodSuggestionLabel })
                        }
                      : null;
                  const unitOptions = unitSuggestionOption
                    ? [
                        unitSuggestionOption,
                        ...sortedUnitOptions.filter((option) => option.id !== unitSuggestionOption.id)
                      ]
                    : sortedUnitOptions;
                  const foodOptions = foodSuggestionOption
                    ? [
                        foodSuggestionOption,
                        ...sortedFoodOptions.filter((option) => option.id !== foodSuggestionOption.id)
                      ]
                    : sortedFoodOptions;
                  const selectedUnitId =
                    entry.unitSelection?.newId ??
                    entry.unitSelection?.mealieUnitId ??
                    entry.unitMatch?.id ??
                    null;
                  const selectedFoodId =
                    entry.foodSelection?.newId ??
                    entry.foodSelection?.mealieFoodId ??
                    entry.foodMatch?.id ??
                    null;
                  const unitDisplayValue =
                    entry.unitSelection?.newId
                      ? unitSuggestionLabel
                      : entry.unitMatch?.name ?? entry.unitSelection?.name ?? entry.unit ?? "";
                  const foodDisplayValue =
                    entry.foodSelection?.newId
                      ? foodSuggestionLabel
                      : entry.foodMatch?.name ?? entry.foodSelection?.name ?? entry.name;
                  const showUnitModalButton = Boolean(entry.unitSelection?.newId);
                  const showFoodModalButton = Boolean(entry.foodSelection?.newId);

                  return (
                    <div
                      key={entry.id}
                      className={clsx(
                        "border border-border bg-panel shadow-sm",
                        layoutConfig.spacing.element.padding.x,
                        layoutConfig.spacing.element.padding.y,
                        layoutConfig.borderRadius.medium
                      )}
                    >
                      <div className={layoutConfig.spacing.item.vertical}>
                        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                          <div>
                            <div className="flex items-baseline gap-2">
                              <span className="text-lg font-semibold text-text">{displayAmount}</span>
                              <span className="text-sm text-text/80">{originalUnitLabel}</span>
                            </div>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <div className="flex w-full items-center gap-3">
                              <BadgePill badgeId={unitBadgeId} fallbackStatus="none" />
                              {showUnitModalButton ? (
                                <button
                                  type="button"
                                  disabled={isReadOnly}
                                  onClick={() => {
                                    if (isReadOnly) return;
                                    setUnitModalEntry(entry);
                                  }}
                                  className={clsx(
                                    "focus-ring inline-flex h-8 w-8 items-center justify-center border border-border bg-background hover:border-primary/60 hover:text-primary",
                                    layoutConfig.borderRadius.small
                                  )}
                                  aria-label={t("review.selection.editNewUnit")}
                                  title={t("review.selection.editNewUnit")}
                                >
                                  <PencilSquareIcon className="h-4 w-4" aria-hidden="true" />
                                </button>
                              ) : null}
                              <div className="flex-1">
                                <SearchableSelect
                                  options={unitOptions}
                                  selectedId={selectedUnitId}
                                  displayValue={unitDisplayValue}
                                  placeholder={unitPlaceholder}
                                  clearLabel={clearSelectionLabel}
                                  disabled={isReadOnly || unitOptions.length === 0}
                                  onChange={(option) => handleUnitSelection(entry.id, option)}
                                />
                              </div>
                            </div>
                          </div>
                        </div>

                        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                          <div>
                            <div className="text-xs uppercase text-text/60">{t("review.table.labels.ingredient")}</div>
                            <div className="font-semibold text-text">{originalFoodLabel}</div>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <div className="flex w-full items-center gap-3">
                              <BadgePill badgeId={foodBadgeId} fallbackStatus="new" />
                              {showFoodModalButton ? (
                                <button
                                  type="button"
                                  disabled={isReadOnly}
                                  onClick={() => {
                                    if (isReadOnly) return;
                                    setFoodModalEntry(entry);
                                  }}
                                  className={clsx(
                                    "focus-ring inline-flex h-8 w-8 items-center justify-center border border-border bg-background hover:border-primary/60 hover:text-primary",
                                    layoutConfig.borderRadius.small
                                  )}
                                  aria-label={t("review.selection.editNewFood")}
                                  title={t("review.selection.editNewFood")}
                                >
                                  <PencilSquareIcon className="h-4 w-4" aria-hidden="true" />
                                </button>
                              ) : null}
                              <div className="flex-1">
                                <SearchableSelect
                                  options={foodOptions}
                                  selectedId={selectedFoodId}
                                  displayValue={foodDisplayValue}
                                  placeholder={foodPlaceholder}
                                  clearLabel={clearSelectionLabel}
                                  disabled={isReadOnly || foodOptions.length === 0}
                                  onChange={(option) => handleFoodSelection(entry.id, option)}
                                  extraActions={[
                                    {
                                      id: "new-food-manual",
                                      label: t("review.selection.newFoodOption", { value: t("review.selection.newFoodManual") }),
                                      onSelect: () => {
                                        if (isReadOnly) return;
                                        setNewFoodDraft(entry);
                                        setFoodModalEntry(entry);
                                      }
                                    }
                                  ]}
                                />
                              </div>
                              <button
                                type="button"
                                disabled={isReadOnly}
                                onClick={() => handleDeleteIngredient(entry.id)}
                                className={clsx(
                                  "focus-ring inline-flex h-8 w-8 items-center justify-center border border-border bg-background hover:border-error/60 hover:text-error disabled:opacity-50",
                                  layoutConfig.borderRadius.small
                                )}
                                aria-label={t("review.actions.deleteIngredient")}
                                title={t("review.actions.deleteIngredient")}
                              >
                                <TrashIcon className="h-4 w-4" aria-hidden="true" />
                              </button>
                            </div>
                          </div>
                        </div>

                        <div>
                          <div className="flex items-center justify-between">
                            <label className="text-xs font-semibold uppercase tracking-wide text-text/60">
                              {t("review.table.labels.note")}
                            </label>
                          </div>
                          <textarea
                            disabled={isReadOnly}
                            value={entry.notes ?? ""}
                            onChange={(event) => {
                              handleNoteChange(entry, event.target.value);
                              autoResizeTextarea(event.target);
                            }}
                  onBlur={() => persistChanges()}
                            ref={(el) => autoResizeTextarea(el)}
                            rows={1}
                            className={clsx(
                              "focus-ring mt-2 w-full resize-none overflow-hidden border border-border bg-background px-4 py-2 text-sm text-text/80",
                              layoutConfig.borderRadius.medium
                            )}
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div
              className={clsx(
                "border border-border bg-background shadow-sm",
                layoutConfig.spacing.element.vertical,
                layoutConfig.spacing.layout.container.x,
                layoutConfig.spacing.layout.container.y,
                layoutConfig.borderRadius.medium
              )}
            >
              <header>
                <h3 className="text-lg font-semibold">{t("review.sections.preparation")}</h3>
              </header>
              <div className={layoutConfig.spacing.item.vertical}>
                {reviewData.instructions.map((instruction, index) => {
                  const selected = stepIngredients[instruction.id] || [];
                  const displayOrder = instruction.order || index + 1;

                  return (
                    <div
                      key={instruction.id}
                      className={clsx(
                        "border border-border bg-panel shadow-sm",
                        layoutConfig.spacing.element.padding.x,
                        layoutConfig.spacing.element.padding.y,
                        layoutConfig.borderRadius.medium
                      )}
                    >
                      <div className={layoutConfig.spacing.item.vertical}>
                        <div className="flex gap-3">
                          <div className="w-10 flex-shrink-0 text-center">
                            <span className="text-lg font-bold text-primary">{displayOrder}</span>
                          </div>
                          <div className="flex-1">
                            <textarea
                              disabled={isReadOnly}
                              value={preparationSteps[instruction.id] ?? instruction.text}
                              onChange={(event) => {
                                handleInstructionChange(instruction, event.target.value);
                                autoResizeTextarea(event.target);
                              }}
                              onBlur={() => persistChanges()}
                              ref={(el) => autoResizeTextarea(el)}
                              rows={1}
                              className={clsx(
                                "focus-ring w-full resize-none overflow-hidden border border-border bg-background px-4 py-3 text-sm leading-relaxed text-text/80",
                                layoutConfig.borderRadius.medium
                              )}
                            />
                          </div>
                        </div>

                        <div className="flex gap-3">
                          <div className="w-10 flex-shrink-0" />
                          <div className="flex-1">
                            <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-text/60">
                              {t("review.preparation.labels.ingredients")}
                            </label>

                            {selected.length > 0 && (
                              <div className={clsx("mb-2 flex flex-wrap", layoutConfig.spacing.item.gap)}>
                                {selected.map((ingredientId) => {
                                  const option = stepIngredientOptionMap.get(ingredientId);
                                  const ingredient = reviewData.ingredients.find((item) => item.id === ingredientId);
                                  if (!option && !ingredient) {
                                    return null;
                                  }
                                  const fallbackFoodLabel = ingredient
                                    ? ingredient.foodSelection?.newId
                                      ? getFoodSuggestionBaseName(ingredient)
                                      : ingredient.foodMatch?.name ??
                                        ingredient.foodSelection?.name ??
                                        ingredient.name
                                    : "";
                                  const displayLabel = option
                                    ? formatStepIngredientLabel(option)
                                    : fallbackFoodLabel;

                                  return (
                                    <span
                                      key={ingredientId}
                                      className={clsx(
                                        "inline-flex items-center bg-primary/10 text-primary",
                                        layoutConfig.spacing.item.gap,
                                        layoutConfig.borderRadius.small
                                      )}
                                    >
                                      <span className="text-xs font-semibold">{displayLabel}</span>
                                      <button
                                        type="button"
                                        disabled={isReadOnly}
                                        onClick={() => {
                                          if (isReadOnly) return;
                                          const current = stepIngredients[instruction.id] || [];
                                          const next = current.filter((id) => id !== ingredientId);
                                          setStepIngredients((previous) => ({
                                            ...previous,
                                            [instruction.id]: next
                                          }));
                                          updateInstructionIngredients(instruction.id, next);
                                        }}
                                        className="focus-ring hover:text-error disabled:opacity-50"
                                        aria-label={t("review.preparation.removeIngredient")}
                                      >
                                        <XMarkIcon className="h-3 w-3" />
                                      </button>
                                    </span>
                                  );
                                })}
                              </div>
                            )}

                            <select
                              value=""
                              disabled={isReadOnly}
                              onChange={(event) => {
                                if (isReadOnly) return;
                                const ingredientId = event.target.value;
                                if (ingredientId && !selected.includes(ingredientId)) {
                                  const next = [...selected, ingredientId];
                                  setStepIngredients((previous) => ({
                                    ...previous,
                                    [instruction.id]: next
                                  }));
                                  updateInstructionIngredients(instruction.id, next);
                                }
                              }}
                              className={clsx(
                                "focus-ring w-full border border-border bg-background px-4 py-2 text-sm text-text",
                                layoutConfig.borderRadius.medium,
                                isReadOnly && "opacity-60 cursor-not-allowed"
                              )}
                            >
                              <option value="">{t("review.preparation.selectIngredient")}</option>
                              {stepIngredientOptions
                                .filter((option) => !selected.includes(option.id))
                                .map((option) => (
                                  <option key={option.id} value={option.id}>
                                    {formatStepIngredientLabel(option)}
                                  </option>
                                ))}
                            </select>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div
              className={clsx(
                "border border-border bg-background shadow-sm",
                layoutConfig.spacing.element.vertical,
                layoutConfig.spacing.layout.container.x,
                layoutConfig.spacing.layout.container.y,
                layoutConfig.borderRadius.medium
              )}
            >
              <header>
                <h3 className="text-lg font-semibold">{t("review.sections.image")}</h3>
              </header>
              <div className="space-y-3">
                <div
                  className={clsx(
                    "relative overflow-hidden border border-border bg-background",
                    imageAspectClass,
                    layoutConfig.borderRadius.medium
                  )}
                >
                  {currentImageUrl ? (
                    <img src={currentImageUrl} alt={t("review.sections.image")} className="h-full w-full object-cover" />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center text-sm text-text/50">
                      {t("review.image.empty")}
                    </div>
                  )}
                  {isImageUploading ? (
                    <div className="absolute inset-0 flex items-center justify-center bg-background/70 text-sm font-semibold text-primary">
                      {t("review.image.uploading")}
                    </div>
                  ) : null}
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) {
                        void handleImageUpload(file);
                      }
                      event.target.value = "";
                    }}
                    disabled={isReadOnly}
                  />
                  <button
                    type="button"
                    onClick={() => {
                      if (isReadOnly) return;
                      fileInputRef.current?.click();
                    }}
                    disabled={isReadOnly || isImageUploading || !runId}
                    className={clsx(
                      "focus-ring inline-flex items-center border border-border bg-background px-4 py-2 text-sm font-semibold text-text hover:border-primary/60 hover:text-primary disabled:cursor-not-allowed disabled:opacity-50",
                      layoutConfig.borderRadius.medium
                    )}
                  >
                    {t("review.image.uploadButton")}
                  </button>
                  <div
                    onDragOver={(e) => {
                      if (isReadOnly) return;
                      handleDropZoneDragOver(e);
                    }}
                    onDragLeave={(e) => {
                      if (isReadOnly) return;
                      handleDropZoneDragLeave(e);
                    }}
                    onDrop={(e) => {
                      if (isReadOnly) return;
                      handleDropZoneDrop(e);
                    }}
                    className={clsx(
                      "flex h-11 flex-1 items-center justify-center border border-dashed text-xs",
                      layoutConfig.borderRadius.medium,
                      isDragActive ? "border-primary text-primary" : "border-border text-text/70"
                    )}
                  >
                    {t("review.image.dropHint")}
                  </div>
                  {pdfImages.length > 0 ? (
                    <div className="flex items-center gap-2">
                      <select
                        value={selectedPdfImageId ?? ""}
                        onChange={(e) => {
                          const nextId = e.target.value || null;
                          setSelectedPdfImageId(nextId);
                          if (nextId) {
                            void handleApplyPdfImage(nextId);
                          }
                        }}
                        disabled={isReadOnly}
                        className={clsx(
                          "h-11 w-auto max-w-xs border border-border bg-background px-3 pr-8 text-sm text-text truncate",
                          layoutConfig.borderRadius.medium
                        )}
                        title={pdfImages.find((img) => img.id === selectedPdfImageId)?.label}
                      >
                        {pdfImages.map((img) => (
                          <option key={img.id} value={img.id}>
                            {img.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  ) : null}
                  {currentImageUrl ? (
                    <button
                      type="button"
                      disabled={isReadOnly}
                      onClick={() => {
                        if (isReadOnly) return;
                        setIsCropModalOpen(true);
                      }}
                      className={clsx(
                        "focus-ring ml-auto inline-flex items-center border border-border bg-background px-4 py-2 text-sm font-semibold text-text hover:border-primary/60 hover:text-primary",
                        layoutConfig.borderRadius.medium
                      )}
                    >
                      {t("review.image.cropButton")}
                    </button>
                  ) : null}
                </div>
                {imageError ? <div className="text-sm text-error">{imageError}</div> : null}
              </div>
            </div>
          </div>
        </div>
      </div>

      <aside className={layoutConfig.step3.grid.rightColumnClasses}>
        <PdfViewer src={currentPdfUrl} />
      </aside>

      <NewFoodModal
        entry={foodModalEntry}
        categories={sortedFoodCategories}
        isOpen={Boolean(foodModalEntry)}
        onClose={() => setFoodModalEntry(null)}
        onSave={handleFoodModalSave}
      />
      <NewUnitModal
        entry={unitModalEntry}
        isOpen={Boolean(unitModalEntry)}
        onClose={() => setUnitModalEntry(null)}
        onSave={handleUnitModalSave}
      />
      {reviewData ? (
        <TagSelectionModal
          isOpen={isTagModalOpen}
          onClose={() => setIsTagModalOpen(false)}
          options={sortedTagOptions}
          selectedIds={reviewData.summary.tagIds ?? []}
          placeholder={t("review.meta.tagsPlaceholder")}
          searchPlaceholder={t("review.meta.tagsSearch")}
          onChange={handleTagsChange}
          categories={availableTagCategories}
          activeCategory={activeTagCategory}
          onCategoryToggle={handleCategoryFilterToggle}
        />
      ) : null}
      {currentImageUrl ? (
        <Transition appear show={isCropModalOpen} as={Fragment}>
          <Dialog as="div" className="relative z-40" onClose={() => setIsCropModalOpen(false)}>
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-200"
              enterFrom="opacity-0"
              enterTo="opacity-100"
              leave="ease-in duration-150"
              leaveFrom="opacity-100"
              leaveTo="opacity-0"
            >
              <div className="fixed inset-0 bg-black/40 backdrop-blur-sm" />
            </Transition.Child>

            <div className="fixed inset-0 overflow-y-auto">
              <div className="flex min-h-full items-center justify-center p-4 text-center">
                <Transition.Child
                  as={Fragment}
                  enter="ease-out duration-200"
                  enterFrom="opacity-0 scale-95"
                  enterTo="opacity-100 scale-100"
                  leave="ease-in duration-150"
                  leaveFrom="opacity-100 scale-100"
                  leaveTo="opacity-0 scale-95"
                >
                  <Dialog.Panel
                    className={clsx(
                      "w-full max-w-4xl transform overflow-hidden border border-border bg-panel p-6 text-left align-middle shadow-xl transition-all",
                      layoutConfig.borderRadius.large
                    )}
                  >
                    <Dialog.Title className="text-xl font-semibold text-primary">{t("review.image.cropModalTitle")}</Dialog.Title>
                    <div className="mt-4">
                      <div className="relative h-[60vh] w-full overflow-hidden">
                        <Cropper
                          key={currentImageUrl || "cropper"}
                          image={currentImageUrl}
                          crop={crop}
                          zoom={zoom}
                          aspect={16 / 10}
                          onCropChange={setCrop}
                          onZoomChange={setZoom}
                          onCropComplete={handleCropComplete}
                        />
                      </div>
                      <label className="mt-4 block text-xs font-semibold uppercase tracking-wide text-text/60">
                        {t("review.image.zoomLabel")}
                      </label>
                      <input
                        type="range"
                        min={1}
                        max={3}
                        step={0.1}
                        value={zoom}
                        onChange={(event) => setZoom(Number(event.target.value))}
                        className="mt-2 w-full"
                      />
                    </div>
                    <div className="mt-4 flex justify-end gap-3">
                      <button
                        type="button"
                        onClick={() => setIsCropModalOpen(false)}
                        className={clsx(
                          "focus-ring inline-flex items-center border border-border px-4 py-2 text-sm font-semibold text-text hover:border-primary/60 hover:text-primary",
                          layoutConfig.borderRadius.small
                        )}
                      >
                        {t("review.image.cropModalCancel")}
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleCropSave()}
                        className={clsx(
                          "focus-ring inline-flex items-center bg-primary px-4 py-2 text-sm font-semibold text-on-primary hover:bg-primary/90",
                          layoutConfig.borderRadius.small
                        )}
                      >
                        {t("review.image.cropModalApply")}
                      </button>
                    </div>
                  </Dialog.Panel>
                </Transition.Child>
              </div>
            </div>
          </Dialog>
        </Transition>
      ) : null}
    </div>
  );
};

const createImage = (url: string): Promise<HTMLImageElement> =>
  new Promise((resolve, reject) => {
    const image = new Image();
    image.addEventListener("load", () => resolve(image));
    image.addEventListener("error", (error) => reject(error));
    image.setAttribute("crossOrigin", "anonymous");
    image.src = url;
  });

const getCroppedBlob = async (
  imageSrc: string,
  pixelCrop: { x: number; y: number; width: number; height: number }
): Promise<Blob | null> => {
  const image = await createImage(imageSrc);
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return null;
  }
  canvas.width = pixelCrop.width;
  canvas.height = pixelCrop.height;
  ctx.drawImage(
    image,
    pixelCrop.x,
    pixelCrop.y,
    pixelCrop.width,
    pixelCrop.height,
    0,
    0,
    pixelCrop.width,
    pixelCrop.height
  );
  return new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(blob), "image/jpeg", 0.92);
  });
};
