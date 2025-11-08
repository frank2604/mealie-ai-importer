import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import { ChevronUpDownIcon, MagnifyingGlassIcon, PencilSquareIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { useTranslation } from "react-i18next";
import { PdfViewerPlaceholder } from "../components/PdfViewerPlaceholder";
import { ReviewModal } from "../components/Modals/ReviewModal";
import { layoutConfig } from "../../config/layout.config";
import { BadgeId } from "../../config/badges.config";
import {
  CandidateOption,
  ReviewData,
  ReviewIngredient,
  ReviewInstruction,
  FoodSelectionPayload,
  UnitSelectionPayload,
  fetchReviewData,
  updateReviewData
} from "../api/review";
import { useImportFlow } from "../context/ImportFlowContext";
import { BadgePill } from "../components/BadgePill";

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

interface ModalContext {
  entry: ReviewIngredient;
  target: "unit" | "ingredient";
}

interface SummaryFormState {
  portionsInput: string;
  totalTimeInput: string;
}

interface SearchableSelectProps {
  options: CandidateOption[];
  selectedId?: string | null;
  displayValue?: string | null;
  placeholder: string;
  clearLabel: string;
  disabled?: boolean;
  onChange: (option: CandidateOption | null) => void;
}

const MAX_RESULTS = 50;

const SearchableSelect: React.FC<SearchableSelectProps> = ({
  options,
  selectedId,
  displayValue,
  placeholder,
  clearLabel,
  disabled = false,
  onChange
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

const parseInteger = (value: string): number | null => {
  if (!value.trim()) {
    return null;
  }
  const parsed = Number.parseInt(value.trim(), 10);
  if (Number.isNaN(parsed)) {
    return null;
  }
  return parsed;
};

const enrichReviewData = (data: ReviewData): ReviewData => ({
  ...data,
  options: data.options ?? { foods: [], units: [] },
  ingredients: data.ingredients.map((item) => ({
    ...item,
    notes: item.notes ?? "",
    foodSelection:
      item.foodSelection ??
      ({
        mealieFoodId: item.foodMatch?.id ?? null,
        name: item.foodMatch?.name ?? item.name,
        badgeId: mapStatusToBadgeId(item.foodStatus),
        status: item.foodStatus ?? null
      } as FoodSelectionPayload),
    unitSelection:
      item.unitSelection ??
      ({
        mealieUnitId: item.unitMatch?.id ?? null,
        name: item.unitMatch?.name ?? item.unit ?? "",
        badgeId: mapStatusToBadgeId(item.unitStatus),
        status: item.unitStatus ?? null
      } as UnitSelectionPayload)
  }))
});

const createSummaryForm = (summary: ReviewData["summary"]): SummaryFormState => ({
  portionsInput: summary.portions != null ? String(summary.portions).replace(".", ",") : "",
  totalTimeInput: summary.totalTimeMinutes != null ? String(summary.totalTimeMinutes) : ""
});

const createPreparationSteps = (instructions: ReviewInstruction[]): Record<string, string> => {
  const steps: Record<string, string> = {};
  instructions.forEach((instruction) => {
    steps[instruction.id] = instruction.text;
  });
  return steps;
};

const buildUpdatePayload = (data: ReviewData) => ({
  summary: {
    title: data.summary.title,
    description: data.summary.description,
    portions: data.summary.portions ?? null,
    totalTimeMinutes: data.summary.totalTimeMinutes ?? null,
    categoryId: data.summary.categoryId ?? null,
    tagIds: data.summary.tagIds ?? []
  },
  ingredients: data.ingredients.map((item) => ({
    id: item.id,
    notes: item.notes ?? "",
    foodDecision: { ...item.foodDecision, notes: item.notes ?? "" },
    unitDecision: { ...item.unitDecision, notes: item.notes ?? "" },
    foodSelection: item.foodSelection ?? {
      mealieFoodId: item.foodMatch?.id ?? null,
      name: item.foodMatch?.name ?? item.name,
      badgeId: item.foodStatus ?? null,
      status: item.foodStatus ?? null
    },
    unitSelection: item.unitSelection ?? {
      mealieUnitId: item.unitMatch?.id ?? null,
      name: item.unitMatch?.name ?? item.unit ?? "",
      badgeId: item.unitStatus ?? null,
      status: item.unitStatus ?? null
    }
  })),
  instructions: data.instructions.map((item) => ({
    id: item.id,
    order: item.order,
    text: item.text,
    timerMinutes: item.timerMinutes ?? null
  }))
});

export const Step3Review: React.FC = () => {
  const { t } = useTranslation();
  const { runId } = useImportFlow();
  const unitPlaceholder = t("review.selection.unitPlaceholder");
  const foodPlaceholder = t("review.selection.foodPlaceholder");
  const clearSelectionLabel = t("review.selection.clear");

  const [reviewData, setReviewData] = useState<ReviewData | null>(null);
  const [summaryForm, setSummaryForm] = useState<SummaryFormState>({ portionsInput: "", totalTimeInput: "" });
  const [modalContext, setModalContext] = useState<ModalContext | null>(null);
  const [preparationSteps, setPreparationSteps] = useState<Record<string, string>>({});
  const [stepIngredients, setStepIngredients] = useState<Record<string, string[]>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const autoResizeTextarea = useCallback((textarea: HTMLTextAreaElement | null) => {
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${textarea.scrollHeight}px`;
  }, []);

  useEffect(() => {
    if (!runId) {
      setReviewData(null);
      setSummaryForm({ portionsInput: "", totalTimeInput: "" });
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
        setSummaryForm(createSummaryForm(enriched.summary));
        setPreparationSteps(createPreparationSteps(enriched.instructions));
        setStepIngredients({});
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
  }, [runId]);

  const persistChanges = useCallback(async (overrideData?: ReviewData | null) => {
    const snapshot = overrideData ?? reviewData;
    if (!runId || !snapshot) {
      return;
    }
    setIsSaving(true);
    setSaveError(null);
    try {
      const payload = buildUpdatePayload(snapshot);
      const updated = await updateReviewData(runId, payload);
      const enriched = enrichReviewData(updated);
      setReviewData(enriched);
      setSummaryForm(createSummaryForm(enriched.summary));
      setPreparationSteps(createPreparationSteps(enriched.instructions));
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsSaving(false);
    }
  }, [runId, reviewData]);

  const handleSummaryFieldChange = useCallback(
    (field: "title" | "description", value: string) => {
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

  const handlePortionsChange = useCallback((value: string) => {
    setSummaryForm((previous) => ({ ...previous, portionsInput: value }));
    setReviewData((previous) => {
      if (!previous) {
        return previous;
      }
      return {
        ...previous,
        summary: {
          ...previous.summary,
          portions: parseLocaleNumber(value)
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
          totalTimeMinutes: parseInteger(value)
        }
      };
    });
  }, []);

  const handleNoteChange = useCallback((entry: ReviewIngredient, value: string) => {
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
  }, []);

  const handleInstructionChange = useCallback((instruction: ReviewInstruction, value: string) => {
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
  }, []);

  const handleUnitSelection = useCallback(
    (ingredientId: string, option: CandidateOption | null) => {
      setReviewData((previous) => {
        if (!previous) {
          return previous;
        }
        const updatedIngredients = previous.ingredients.map((item) => {
          if (item.id !== ingredientId) {
            return item;
          }
          const nextBadge: BadgeId = option ? "manual" : "none";
          const updatedItem: ReviewIngredient = {
            ...item,
            unit: option?.name ?? item.unit,
            unitMatch: option
              ? { id: option.id, name: option.name ?? "", strategy: "manual" }
              : null,
            unitStatus: option ? "manual" : "none",
            unitSelection: {
              mealieUnitId: option ? option.id : null,
              name: option?.name ?? item.unit ?? "",
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
      setReviewData((previous) => {
        if (!previous) {
          return previous;
        }
        const updatedIngredients = previous.ingredients.map((item) => {
          if (item.id !== ingredientId) {
            return item;
          }
          const nextBadge: BadgeId = option ? "manual" : "new";
          const updatedItem: ReviewIngredient = {
            ...item,
            name: option?.name ?? item.name,
            foodMatch: option
              ? { id: option.id, name: option.name ?? "", strategy: "manual" }
              : null,
            foodStatus: option ? "manual" : "new",
            foodSelection: {
              mealieFoodId: option ? option.id : null,
              name: option?.name ?? item.name,
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

  const metaRows = useMemo(
    () => [
      {
        leftLabel: t("review.meta.portions"),
        leftValue: summaryForm.portionsInput,
        onLeftChange: handlePortionsChange,
        onLeftBlur: () => persistChanges(),
        rightLabel: t("review.meta.totalTime"),
        rightValue: summaryForm.totalTimeInput,
        onRightChange: handleTotalTimeChange,
        onRightBlur: () => persistChanges()
      }
    ],
    [handlePortionsChange, handleTotalTimeChange, persistChanges, summaryForm.portionsInput, summaryForm.totalTimeInput, t]
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
          "flex flex-col overflow-hidden border border-border bg-panel xl:min-h-0 xl:h-full",
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
                  value={reviewData.summary.title}
                  onChange={(event) => handleSummaryFieldChange("title", event.target.value)}
                  onBlur={() => persistChanges()}
                  className={clsx(
                    "focus-ring w-full border border-border bg-background px-4 py-3 text-xl font-semibold text-primary",
                    layoutConfig.borderRadius.medium
                  )}
                />
                <textarea
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
              <div className="overflow-x-auto">
                <table className="min-w-full border-t border-border text-sm">
                  <tbody>
                    {metaRows.map((row, index) => (
                      <tr key={`meta-${index}`} className={index % 2 === 1 ? "bg-background/40" : ""}>
                        <td className="border-t border-border px-4 py-3 text-xs font-semibold uppercase tracking-wide text-text/60">
                          {row.leftLabel}
                        </td>
                        <td className="border-t border-border px-4 py-3">
                          <input
                            value={row.leftValue}
                            onChange={(event) => row.onLeftChange(event.target.value)}
                            onBlur={row.onLeftBlur}
                            className={clsx(
                              "focus-ring w-full border border-border bg-background px-3 py-2 text-sm font-semibold text-text/85",
                              layoutConfig.borderRadius.medium
                            )}
                          />
                        </td>
                        <td className="border-t border-border px-4 py-3 text-xs font-semibold uppercase tracking-wide text-text/60">
                          {row.rightLabel}
                        </td>
                        <td className="border-t border-border px-4 py-3">
                          <input
                            value={row.rightValue}
                            onChange={(event) => row.onRightChange(event.target.value)}
                            onBlur={row.onRightBlur}
                            className={clsx(
                              "focus-ring w-full border border-border bg-background px-3 py-2 text-sm font-semibold text-text/85",
                              layoutConfig.borderRadius.medium
                            )}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
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
                {reviewData.ingredients.map((entry) => {
                  const displayAmount =
                    entry.amountText ??
                    (entry.amount != null ? String(entry.amount).replace(".", ",") : "") ??
                    "";
                  const unitBadgeId =
                    (entry.unitSelection?.badgeId as BadgeId | undefined) ??
                    mapStatusToBadgeId(entry.unitStatus) ??
                    null;
                  const foodBadgeId =
                    (entry.foodSelection?.badgeId as BadgeId | undefined) ??
                    mapStatusToBadgeId(entry.foodStatus) ??
                    null;
                  const isUnitResolved = !!unitBadgeId && unitBadgeId !== "new" && unitBadgeId !== "none";
                  const isFoodResolved = !!foodBadgeId && foodBadgeId !== "new";
                  const originalUnitLabel = entry.unitOriginalName ?? entry.unit ?? "";
                  const originalFoodLabel = entry.foodOriginalName ?? entry.name;

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
                              <div className="flex-1">
                                <SearchableSelect
                                  options={reviewData.options.units}
                                  selectedId={entry.unitMatch?.id ?? null}
                                  displayValue={entry.unitMatch?.name ?? entry.unit ?? ""}
                                  placeholder={unitPlaceholder}
                                  clearLabel={clearSelectionLabel}
                                  disabled={reviewData.options.units.length === 0}
                                  onChange={(option) => handleUnitSelection(entry.id, option)}
                                />
                              </div>
                            </div>
                            <button
                              type="button"
                              onClick={() => setModalContext({ entry, target: "unit" })}
                              className={clsx(
                                "focus-ring inline-flex h-8 w-8 items-center justify-center border border-border bg-background hover:border-primary/60 hover:text-primary",
                                layoutConfig.borderRadius.small
                              )}
                              aria-label={isUnitResolved ? t("review.actions.view") : t("review.actions.edit")}
                            >
                              {isUnitResolved ? (
                                <MagnifyingGlassIcon className="h-4 w-4" aria-hidden="true" />
                              ) : (
                                <PencilSquareIcon className="h-4 w-4" aria-hidden="true" />
                              )}
                            </button>
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
                              <div className="flex-1">
                                <SearchableSelect
                                  options={reviewData.options.foods}
                                  selectedId={entry.foodMatch?.id ?? null}
                                  displayValue={entry.foodMatch?.name ?? entry.name}
                                  placeholder={foodPlaceholder}
                                  clearLabel={clearSelectionLabel}
                                  disabled={reviewData.options.foods.length === 0}
                                  onChange={(option) => handleFoodSelection(entry.id, option)}
                                />
                              </div>
                            </div>
                            <button
                              type="button"
                              onClick={() => setModalContext({ entry, target: "ingredient" })}
                              className={clsx(
                                "focus-ring inline-flex h-8 w-8 items-center justify-center border border-border bg-background hover:border-primary/60 hover:text-primary",
                                layoutConfig.borderRadius.small
                              )}
                              aria-label={isFoodResolved ? t("review.actions.view") : t("review.actions.edit")}
                            >
                              {isFoodResolved ? (
                                <MagnifyingGlassIcon className="h-4 w-4" aria-hidden="true" />
                              ) : (
                                <PencilSquareIcon className="h-4 w-4" aria-hidden="true" />
                              )}
                            </button>
                          </div>
                        </div>

                        <div>
                          <label className="text-xs font-semibold uppercase tracking-wide text-text/60">
                            {t("review.table.labels.note")}
                          </label>
                          <textarea
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
                                  const ingredient = reviewData.ingredients.find((item) => item.id === ingredientId);
                                  if (!ingredient) return null;

                                  return (
                                    <span
                                      key={ingredientId}
                                      className={clsx(
                                        "inline-flex items-center bg-primary/10 text-primary",
                                        layoutConfig.spacing.item.gap,
                                        layoutConfig.borderRadius.small
                                      )}
                                    >
                                      <span className="text-xs font-semibold">
                                        {`${ingredient.amountText ?? ""} ${ingredient.unit ?? ""} ${ingredient.name}`}
                                      </span>
                                      <button
                                        type="button"
                                        onClick={() =>
                                          setStepIngredients((previous) => ({
                                            ...previous,
                                            [instruction.id]: previous[instruction.id].filter((id) => id !== ingredientId)
                                          }))
                                        }
                                        className="focus-ring hover:text-error"
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
                              onChange={(event) => {
                                const ingredientId = event.target.value;
                                if (ingredientId && !selected.includes(ingredientId)) {
                                  setStepIngredients((previous) => ({
                                    ...previous,
                                    [instruction.id]: [...(previous[instruction.id] || []), ingredientId]
                                  }));
                                }
                              }}
                              className={clsx(
                                "focus-ring w-full border border-border bg-background px-4 py-2 text-sm text-text",
                                layoutConfig.borderRadius.medium
                              )}
                            >
                              <option value="">{t("review.preparation.selectIngredient")}</option>
                              {reviewData.ingredients
                                .filter((ingredient) => !selected.includes(ingredient.id))
                                .map((ingredient) => (
                                  <option key={ingredient.id} value={ingredient.id}>
                                    {`${ingredient.amountText ?? ""} ${ingredient.unit ?? ""} ${ingredient.name}`}
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
              <div className={clsx("overflow-hidden border border-border bg-background", layoutConfig.borderRadius.medium)}>
                <div className="aspect-[4/3] w-full bg-secondary/40" aria-hidden="true" />
                <p className="px-4 py-3 text-sm text-text/70">{t("review.image.caption")}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <aside className={layoutConfig.step3.grid.rightColumnClasses}>
        <PdfViewerPlaceholder />
      </aside>

      <ReviewModal context={modalContext} onClose={() => setModalContext(null)} />
    </div>
  );
};
