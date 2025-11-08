import { useCallback, useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { MagnifyingGlassIcon, PencilSquareIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { useTranslation } from "react-i18next";
import { PdfViewerPlaceholder } from "../components/PdfViewerPlaceholder";
import { ReviewModal } from "../components/Modals/ReviewModal";
import { layoutConfig } from "../../config/layout.config";
import {
  ReviewData,
  ReviewIngredient,
  ReviewInstruction,
  fetchReviewData,
  updateReviewData
} from "../api/review";
import { useImportFlow } from "../context/ImportFlowContext";

type ReviewStatus = "found" | "new" | "error" | "info";

interface ModalContext {
  entry: ReviewIngredient;
  target: "unit" | "ingredient";
}

interface SummaryFormState {
  portionsInput: string;
  totalTimeInput: string;
}

const statusStyles: Record<ReviewStatus, string> = {
  found: "bg-success/15 text-success border-success/40",
  new: "bg-warning/15 text-warning border-warning/40",
  error: "bg-error/15 text-error border-error/40",
  info: "bg-info/15 text-info border-info/40"
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
  ingredients: data.ingredients.map((item) => ({
    ...item,
    notes: item.notes ?? ""
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
    unitDecision: { ...item.unitDecision, notes: item.notes ?? "" }
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

  const persistChanges = useCallback(async () => {
    if (!runId || !reviewData) {
      return;
    }
    setIsSaving(true);
    setSaveError(null);
    try {
      const payload = buildUpdatePayload(reviewData);
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

  const metaRows = useMemo(
    () => [
      {
        leftLabel: t("review.meta.portions"),
        leftValue: summaryForm.portionsInput,
        onLeftChange: handlePortionsChange,
        onLeftBlur: persistChanges,
        rightLabel: t("review.meta.totalTime"),
        rightValue: summaryForm.totalTimeInput,
        onRightChange: handleTotalTimeChange,
        onRightBlur: persistChanges
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
                  onBlur={persistChanges}
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
                  onBlur={persistChanges}
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
                  const unitActionIcon =
                    entry.unitStatus === "found" ? (
                      <MagnifyingGlassIcon className="h-4 w-4" aria-hidden="true" />
                    ) : (
                      <PencilSquareIcon className="h-4 w-4" aria-hidden="true" />
                    );

                  const ingredientActionIcon =
                    entry.foodStatus === "found" ? (
                      <MagnifyingGlassIcon className="h-4 w-4" aria-hidden="true" />
                    ) : (
                      <PencilSquareIcon className="h-4 w-4" aria-hidden="true" />
                    );

                  const displayAmount =
                    entry.amountText ??
                    (entry.amount != null ? String(entry.amount).replace(".", ",") : "") ??
                    "";

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
                              <span className="text-sm text-text/80">{entry.unit ?? ""}</span>
                            </div>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <div className="flex items-center gap-2">
                              <span
                                className={clsx(
                                  "inline-flex items-center border px-2 py-0.5 text-[11px] font-semibold uppercase",
                                  layoutConfig.borderRadius.small,
                                  statusStyles[(entry.unitStatus as ReviewStatus) || "info"]
                                )}
                              >
                                {t(`review.status.${entry.unitStatus as ReviewStatus}`)}
                              </span>
                              <span className="font-medium text-text/85">
                                {entry.unitMatch?.name ?? t("review.noMapping")}
                              </span>
                            </div>
                            <button
                              type="button"
                              onClick={() => setModalContext({ entry, target: "unit" })}
                              className={clsx(
                                "focus-ring inline-flex h-8 w-8 items-center justify-center border border-border bg-background hover:border-primary/60 hover:text-primary",
                                layoutConfig.borderRadius.small
                              )}
                              aria-label={
                                entry.unitStatus === "found" ? t("review.actions.view") : t("review.actions.edit")
                              }
                            >
                              {unitActionIcon}
                            </button>
                          </div>
                        </div>

                        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                            <div>
                              <div className="text-xs uppercase text-text/60">{t("review.table.labels.ingredient")}</div>
                              <div className="font-semibold text-text">{entry.name}</div>
                            </div>
                          <div className="flex items-center justify-between gap-3">
                            <div className="flex items-center gap-2">
                              <span
                                className={clsx(
                                  "inline-flex items-center border px-2 py-0.5 text-[11px] font-semibold uppercase",
                                  layoutConfig.borderRadius.small,
                                  statusStyles[(entry.foodStatus as ReviewStatus) || "info"]
                                )}
                              >
                                {t(`review.status.${entry.foodStatus as ReviewStatus}`)}
                              </span>
                              <span className="font-medium text-text/85">
                                {entry.foodMatch?.name ?? t("review.noMapping")}
                              </span>
                            </div>
                            <button
                              type="button"
                              onClick={() => setModalContext({ entry, target: "ingredient" })}
                              className={clsx(
                                "focus-ring inline-flex h-8 w-8 items-center justify-center border border-border bg-background hover:border-primary/60 hover:text-primary",
                                layoutConfig.borderRadius.small
                              )}
                              aria-label={
                                entry.foodStatus === "found" ? t("review.actions.view") : t("review.actions.edit")
                              }
                            >
                              {ingredientActionIcon}
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
                            onBlur={persistChanges}
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
                              onBlur={persistChanges}
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
                                        layoutConfig.spacing.button.badge.x,
                                        layoutConfig.spacing.button.badge.y,
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
