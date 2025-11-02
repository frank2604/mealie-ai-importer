import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { MagnifyingGlassIcon, PencilSquareIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { useTranslation } from "react-i18next";
import { PdfViewerPlaceholder } from "../components/PdfViewerPlaceholder";
import { ReviewModal } from "../components/Modals/ReviewModal";
import { layoutConfig } from "../../config/layout.config";


type ReviewStatus = "found" | "new" | "error" | "info";

interface SummaryMetaRow {
  leftLabel: string;
  leftValue: string;
  rightLabel: string;
  rightValue: string;
}

interface SummaryData {
  title: string;
  description: string;
  meta: SummaryMetaRow[];
}

interface SuggestedUnit {
  nameSingular: string;
  namePlural: string;
  abbreviationSingular: string;
  abbreviationPlural: string;
  useAbbreviation: boolean;
  supportsFraction: boolean;
}

interface SuggestedIngredient {
  nameSingular: string;
  namePlural: string;
  category: string;
  aliases: string;
}

interface IngredientReviewEntry {
  id: string;
  amount: string;
  unit: string;
  unitMapping: string;
  unitStatus: ReviewStatus;
  unitMethod?: string;
  unitConfidence?: string;
  unitNew?: SuggestedUnit;
  ingredient: string;
  ingredientMapping: string;
  ingredientStatus: ReviewStatus;
  ingredientMethod?: string;
  ingredientConfidence?: string;
  ingredientNew?: SuggestedIngredient;
  note: string;
}

interface PreparationRow {
  step: string;
  text: string;
}

interface ModalContext {
  entry: IngredientReviewEntry;
  target: "unit" | "ingredient";
}

const statusStyles: Record<ReviewStatus, string> = {
  found: "bg-success/15 text-success border-success/40",
  new: "bg-warning/15 text-warning border-warning/40",
  error: "bg-error/15 text-error border-error/40",
  info: "bg-info/15 text-info border-info/40"
};

export const Step3Review: React.FC = () => {
  const { t, i18n } = useTranslation();
  const [modalContext, setModalContext] = useState<ModalContext | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [preparationSteps, setPreparationSteps] = useState<Record<string, string>>({});
  const [stepIngredients, setStepIngredients] = useState<Record<string, string[]>>({});
  const [summary, setSummary] = useState<SummaryData>(() =>
    t("review.summary", { returnObjects: true }) as SummaryData
  );

  // Auto-Resize-Funktion für Textareas
  const autoResizeTextarea = useCallback((textarea: HTMLTextAreaElement | null) => {
    if (!textarea) return;

    // Höhe zurücksetzen, um die korrekte scrollHeight zu bekommen
    textarea.style.height = 'auto';
    // Neue Höhe basierend auf scrollHeight setzen
    textarea.style.height = `${textarea.scrollHeight}px`;
  }, []);

  const entries = useMemo(
    () =>
      (t("review.entries", { returnObjects: true }) as Omit<IngredientReviewEntry, "id">[]).map((entry, index) => ({
        ...entry,
        id: `entry-${index}`
      })),
    [t, i18n.resolvedLanguage]
  );

  const preparationRows = useMemo(
    () => t("review.preparation.rows", { returnObjects: true }) as PreparationRow[],
    [t, i18n.resolvedLanguage]
  );

  useEffect(() => {
    const data = t("review.summary", { returnObjects: true }) as SummaryData;
    setSummary(data);
  }, [t, i18n.resolvedLanguage]);

  useEffect(() => {
    const initialNotes: Record<string, string> = {};
    entries.forEach((entry) => {
      initialNotes[entry.id] = entry.note ?? "";
    });
    setNotes(initialNotes);
  }, [entries]);

  useEffect(() => {
    const initialSteps: Record<string, string> = {};
    const initialIngredients: Record<string, string[]> = {};
    preparationRows.forEach((row, index) => {
      const stepId = `step-${index}`;
      initialSteps[stepId] = row.text;
      initialIngredients[stepId] = [];
    });
    setPreparationSteps(initialSteps);
    setStepIngredients(initialIngredients);
  }, [preparationRows]);

  const handleMetaChange = (index: number, key: "leftValue" | "rightValue", value: string) => {
    setSummary((prev) => ({
      ...prev,
      meta: prev.meta.map((row, rowIndex) =>
        rowIndex === index
          ? {
              ...row,
              [key]: value
            }
          : row
      )
    }));
  };

  return (
    <div className={clsx(layoutConfig.step3.grid.gridClasses, layoutConfig.spacing.layout.columns)}>
      {/* Linke Spalte: Rezeptdaten */}
      <div className={clsx(
        "flex flex-col overflow-hidden border border-border bg-panel xl:min-h-0 xl:h-full",
        layoutConfig.borderRadius.large,
        layoutConfig.shadow.panel
      )}>
        <div className={clsx("scrollbar-rounded xl:min-h-0 xl:flex-1 xl:overflow-y-auto", layoutConfig.spacing.section.padding.x, layoutConfig.spacing.section.padding.y)} style={{ scrollbarGutter: 'stable' }}>
          <div className={clsx("pb-6", layoutConfig.spacing.section.vertical)}>
              <div className={clsx("overflow-hidden border border-border bg-background shadow-sm", layoutConfig.borderRadius.medium)}>
                <div className={clsx("border-b border-border", layoutConfig.spacing.section.padding.x, layoutConfig.spacing.section.padding.y)}>
                  <input
                    value={summary.title}
                    onChange={(event) =>
                      setSummary((prev) => ({
                        ...prev,
                        title: event.target.value
                      }))
                    }
                    className={clsx("focus-ring w-full border border-border bg-background px-4 py-3 text-xl font-semibold text-primary", layoutConfig.borderRadius.medium)}
                  />
                  <textarea
                    value={summary.description}
                    onChange={(event) => {
                      setSummary((prev) => ({
                        ...prev,
                        description: event.target.value
                      }));
                      autoResizeTextarea(event.target);
                    }}
                    ref={(el) => autoResizeTextarea(el)}
                    rows={1}
                    className={clsx("focus-ring mt-4 w-full resize-none overflow-hidden border border-border bg-background px-4 py-3 text-sm leading-relaxed text-text/75", layoutConfig.borderRadius.medium)}
                  />
                </div>
                <div className="overflow-x-auto">
                  <table className="min-w-full border-t border-border text-sm">
                    <tbody>
                      {summary.meta.map((row, index) => (
                        <tr key={`${row.leftLabel}-${index}`} className={index % 2 === 1 ? "bg-background/40" : ""}>
                          <td className="border-t border-border px-4 py-3 text-xs font-semibold uppercase tracking-wide text-text/60">
                            {row.leftLabel}
                          </td>
                          <td className="border-t border-border px-4 py-3">
                            <input
                              value={row.leftValue}
                              onChange={(event) => handleMetaChange(index, "leftValue", event.target.value)}
                              className={clsx("focus-ring w-full border border-border bg-background px-3 py-2 text-sm font-semibold text-text/85", layoutConfig.borderRadius.medium)}
                            />
                          </td>
                          <td className="border-t border-border px-4 py-3 text-xs font-semibold uppercase tracking-wide text-text/60">
                            {row.rightLabel}
                          </td>
                          <td className="border-t border-border px-4 py-3">
                            <input
                              value={row.rightValue}
                              onChange={(event) => handleMetaChange(index, "rightValue", event.target.value)}
                              className={clsx("focus-ring w-full border border-border bg-background px-3 py-2 text-sm font-semibold text-text/85", layoutConfig.borderRadius.medium)}
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className={clsx("border border-border bg-background shadow-sm", layoutConfig.spacing.element.vertical, layoutConfig.spacing.layout.container.x, layoutConfig.spacing.layout.container.y, layoutConfig.borderRadius.medium)}>
                <header>
                  <h3 className="text-lg font-semibold">{t("review.sections.ingredients")}</h3>
                </header>
                <div className={layoutConfig.spacing.item.vertical}>
                  {entries.map((entry) => {
                    const unitActionIcon =
                      entry.unitStatus === "found" ? (
                        <MagnifyingGlassIcon className="h-4 w-4" aria-hidden="true" />
                      ) : (
                        <PencilSquareIcon className="h-4 w-4" aria-hidden="true" />
                      );

                    const ingredientActionIcon =
                      entry.ingredientStatus === "found" ? (
                        <MagnifyingGlassIcon className="h-4 w-4" aria-hidden="true" />
                      ) : (
                        <PencilSquareIcon className="h-4 w-4" aria-hidden="true" />
                      );

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
                          {/* Zeile 1: Einheit */}
                          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                            <div>
                              <div className="flex items-baseline gap-2">
                                <span className="text-lg font-semibold text-text">{entry.amount}</span>
                                <span className="text-sm text-text/80">{entry.unit}</span>
                              </div>
                            </div>
                            <div className="flex items-center justify-between gap-3">
                              <div className="flex items-center gap-2">
                                <span
                                  className={clsx(
                                    "inline-flex items-center border px-2 py-0.5 text-[11px] font-semibold uppercase",
                                    layoutConfig.borderRadius.small,
                                    statusStyles[entry.unitStatus]
                                  )}
                                >
                                  {t(`review.status.${entry.unitStatus}`)}
                                </span>
                                <span className="font-medium text-text/85">{entry.unitMapping}</span>
                              </div>
                              <button
                                type="button"
                                onClick={() => setModalContext({ entry, target: "unit" })}
                                className={clsx(
                                  "focus-ring inline-flex h-8 w-8 items-center justify-center border border-border bg-background hover:border-primary/60 hover:text-primary",
                                  layoutConfig.borderRadius.small
                                )}
                                aria-label={
                                  entry.unitStatus === "found"
                                    ? t("review.actions.view")
                                    : t("review.actions.edit")
                                }
                              >
                                {unitActionIcon}
                              </button>
                            </div>
                          </div>

                          {/* Zeile 2: Zutat */}
                          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                            <div>
                              <div className="text-xs uppercase text-text/60">{t("review.table.labels.ingredient")}</div>
                              <div className="mt-1 font-semibold text-text">{entry.ingredient}</div>
                            </div>
                            <div className="flex items-center justify-between gap-3">
                              <div className="flex items-center gap-2">
                                <span
                                  className={clsx(
                                    "inline-flex items-center border px-2 py-0.5 text-[11px] font-semibold uppercase",
                                    layoutConfig.borderRadius.small,
                                    statusStyles[entry.ingredientStatus]
                                  )}
                                >
                                  {t(`review.status.${entry.ingredientStatus}`)}
                                </span>
                                <span className="font-medium text-text/85">{entry.ingredientMapping}</span>
                              </div>
                              <button
                                type="button"
                                onClick={() => setModalContext({ entry, target: "ingredient" })}
                                className={clsx(
                                  "focus-ring inline-flex h-8 w-8 items-center justify-center border border-border bg-background hover:border-primary/60 hover:text-primary",
                                  layoutConfig.borderRadius.small
                                )}
                                aria-label={
                                  entry.ingredientStatus === "found"
                                    ? t("review.actions.view")
                                    : t("review.actions.edit")
                                }
                              >
                                {ingredientActionIcon}
                              </button>
                            </div>
                          </div>

                          {/* Zeile 3: Notiz */}
                          <div>
                            <div className="text-xs uppercase text-text/60">{t("review.table.labels.note")}</div>
                            <textarea
                              value={notes[entry.id] ?? ""}
                              onChange={(event) => {
                                setNotes((prev) => ({
                                  ...prev,
                                  [entry.id]: event.target.value
                                }));
                                autoResizeTextarea(event.target);
                              }}
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

              <div className={clsx("border border-border bg-background shadow-sm", layoutConfig.spacing.element.vertical, layoutConfig.spacing.layout.container.x, layoutConfig.spacing.layout.container.y, layoutConfig.borderRadius.medium)}>
                <header>
                  <h3 className="text-lg font-semibold">{t("review.sections.preparation")}</h3>
                </header>
                <div className={layoutConfig.spacing.item.vertical}>
                  {preparationRows.map((row, index) => {
                    const stepId = `step-${index}`;
                    const selectedIngredients = stepIngredients[stepId] || [];

                    return (
                      <div
                        key={stepId}
                        className={clsx(
                          "border border-border bg-panel shadow-sm",
                          layoutConfig.spacing.element.padding.x,
                          layoutConfig.spacing.element.padding.y,
                          layoutConfig.borderRadius.medium
                        )}
                      >
                        <div className={layoutConfig.spacing.item.vertical}>
                          {/* Zeile 1: Schrittnummer + Textfeld */}
                          <div className="flex gap-3">
                            <div className="w-10 flex-shrink-0 text-center">
                              <span className="text-lg font-bold text-primary">{row.step}</span>
                            </div>
                            <div className="flex-1">
                              <textarea
                                value={preparationSteps[stepId] ?? row.text}
                                onChange={(event) => {
                                  setPreparationSteps((prev) => ({
                                    ...prev,
                                    [stepId]: event.target.value
                                  }));
                                  autoResizeTextarea(event.target);
                                }}
                                ref={(el) => autoResizeTextarea(el)}
                                rows={1}
                                className={clsx(
                                  "focus-ring w-full resize-none overflow-hidden border border-border bg-background px-4 py-3 text-sm leading-relaxed text-text/80",
                                  layoutConfig.borderRadius.medium
                                )}
                              />
                            </div>
                          </div>

                          {/* Zeile 2: Zutaten-Auswahl */}
                          <div className="flex gap-3">
                            <div className="w-10 flex-shrink-0" />
                            <div className="flex-1">
                              <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-text/60">
                                {t("review.preparation.labels.ingredients")}
                              </label>

                              {/* Ausgewählte Zutaten als Pillen */}
                              {selectedIngredients.length > 0 && (
                                <div className={clsx("mb-2 flex flex-wrap", layoutConfig.spacing.item.gap)}>
                                  {selectedIngredients.map((ingredientId) => {
                                    const ingredient = entries.find((e) => e.id === ingredientId);
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
                                          {ingredient.amount} {ingredient.unit} {ingredient.ingredient}
                                        </span>
                                        <button
                                          type="button"
                                          onClick={() =>
                                            setStepIngredients((prev) => ({
                                              ...prev,
                                              [stepId]: prev[stepId].filter((id) => id !== ingredientId)
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

                              {/* Dropdown zum Hinzufügen */}
                              <select
                                value=""
                                onChange={(event) => {
                                  const ingredientId = event.target.value;
                                  if (ingredientId && !selectedIngredients.includes(ingredientId)) {
                                    setStepIngredients((prev) => ({
                                      ...prev,
                                      [stepId]: [...(prev[stepId] || []), ingredientId]
                                    }));
                                  }
                                }}
                                className={clsx(
                                  "focus-ring w-full border border-border bg-background px-4 py-2 text-sm text-text",
                                  layoutConfig.borderRadius.medium
                                )}
                              >
                                <option value="">{t("review.preparation.selectIngredient")}</option>
                                {entries
                                  .filter((entry) => !selectedIngredients.includes(entry.id))
                                  .map((entry) => (
                                    <option key={entry.id} value={entry.id}>
                                      {entry.amount} {entry.unit} {entry.ingredient}
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

              <div className={clsx("border border-border bg-background shadow-sm", layoutConfig.spacing.element.vertical, layoutConfig.spacing.layout.container.x, layoutConfig.spacing.layout.container.y, layoutConfig.borderRadius.medium)}>
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

      {/* Rechte Spalte: PDF-Viewer */}
      <aside className={layoutConfig.step3.grid.rightColumnClasses}>
        <PdfViewerPlaceholder />
      </aside>

      <ReviewModal context={modalContext} onClose={() => setModalContext(null)} />
    </div>
  );
};
