import { useEffect, useMemo, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { LogViewer, LogEntry } from "../components/LogViewer";
import clsx from "clsx";
import { layoutConfig } from "../../config/layout.config";
import { useImportFlow } from "../context/ImportFlowContext";
import { useStepNavigation } from "../App";
import { fetchRunLogs, fetchRunStatus, mapApiLogEntries } from "../api/imports";
import { fetchReviewData, type ReviewData, type ReviewIngredient } from "../api/review";

interface MetricValue {
  total: number | null;
  newlyAdded: number | null;
}

export const Step2Analyze: React.FC = () => {
  const { t } = useTranslation();
  const {
    runId,
    status,
    error,
    analysisLogs,
    analysisCursor,
    appendAnalysisLogs,
    setStatus,
    setError,
    setRunId
  } = useImportFlow();
  const { setNextHandler, setNextDisabled } = useStepNavigation();
  const [isPolling, setIsPolling] = useState(false);
  const [ingredientMetric, setIngredientMetric] = useState<MetricValue>({ total: null, newlyAdded: null });
  const [unitMetric, setUnitMetric] = useState<MetricValue>({ total: null, newlyAdded: null });
  const logEntries = useMemo<LogEntry[]>(() => analysisLogs, [analysisLogs]);
  const refreshMetrics = useCallback(
    async (currentRunId: string) => {
      try {
        const data = await fetchReviewData(currentRunId);
        const ingredientsMetric = computeIngredientMetric(data);
        const unitsMetric = computeUnitMetric(data);
        setIngredientMetric(ingredientsMetric);
        setUnitMetric(unitsMetric);
      } catch {
        // ignore – metrics remain empty
      }
    },
    []
  );

  useEffect(() => {
    setNextHandler(null);
    if (!runId) {
      setNextDisabled(true);
      return () => {
        setNextDisabled(false);
      };
    }
    setNextDisabled(!["review", "completed"].includes(status));
    return () => {
      setNextDisabled(false);
    };
  }, [runId, setNextDisabled, setNextHandler, status]);

  useEffect(() => {
    if (!runId) {
      return;
    }
    let active = true;
    let timeoutId: number | undefined;

    const poll = async () => {
      setIsPolling(true);
      try {
        const [statusResult, logResult] = await Promise.all([
          fetchRunStatus(runId),
          fetchRunLogs(runId, analysisCursor, "analysis")
        ]);
        if (!active) {
          return;
        }
        if (!statusResult) {
          setRunId(null);
          setStatus("idle");
          setError(null);
          setIsPolling(false);
          return;
        }
        if (!active) {
          return;
        }
        if (statusResult.status === "running") {
          setStatus("analyzing");
        } else if (statusResult.status === "starting") {
          setStatus("starting");
        } else if (statusResult.status === "review") {
          setStatus("review");
        } else if (statusResult.status === "transferring") {
          setStatus("transferring");
        } else if (statusResult.status === "completed") {
          setStatus("completed");
        } else if (statusResult.status === "failed") {
          setStatus("failed");
        } else if (statusResult.status === "aborted") {
          setStatus("aborted");
        }
        if (statusResult.error) {
          setError(statusResult.error);
        }
        if (logResult?.entries.length) {
          appendAnalysisLogs(mapApiLogEntries(logResult.entries), logResult.nextCursor);
        }
        if (["review", "completed", "failed", "aborted"].includes(statusResult.status)) {
          setNextDisabled(!["review", "completed"].includes(statusResult.status));
          setIsPolling(false);
          if (["review", "completed"].includes(statusResult.status) && runId) {
            void refreshMetrics(runId);
          }
          return;
        }
        timeoutId = window.setTimeout(poll, 2000);
      } catch (pollError) {
        if (!active) {
          return;
        }
        const message = pollError instanceof Error ? pollError.message : String(pollError);
        setError(message);
        timeoutId = window.setTimeout(poll, 5000);
      }
    };

    poll();

    return () => {
      active = false;
      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }
      setIsPolling(false);
    };
  }, [analysisCursor, appendAnalysisLogs, refreshMetrics, runId, setError, setNextDisabled, setStatus, setRunId]);

  useEffect(() => {
    if (!runId) {
      setIngredientMetric({ total: null, newlyAdded: null });
      setUnitMetric({ total: null, newlyAdded: null });
      return;
    }
    if (["review", "completed"].includes(status) && !isPolling) {
      void refreshMetrics(runId);
    }
  }, [isPolling, refreshMetrics, runId, status]);

  const statusLabel = useMemo(() => {
    switch (status) {
      case "starting":
        return t("analyze.status.starting");
      case "analyzing":
        return t("analyze.status.running");
      case "review":
        return t("analyze.status.review");
      case "transferring":
        return t("analyze.status.transferring");
      case "completed":
        return t("analyze.status.completed");
      case "failed":
        return t("analyze.status.failed");
      case "aborted":
        return t("analyze.status.aborted");
      default:
        return t("analyze.status.idle");
    }
  }, [status, t]);
  const showActivityBar = ["starting", "analyzing", "transferring"].includes(status);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex-1 min-h-0 overflow-y-auto">
        <div
          className={clsx(
            "grid h-full flex-1 grid-cols-1 grid-rows-[auto_minmax(0,1fr)] gap-6 xl:grid-cols-[2fr_3fr] xl:grid-rows-none",
            layoutConfig.spacing.layout.columns
          )}
        >
          <aside
            className={clsx(
              "flex flex-col gap-4 border border-border bg-panel self-start",
              layoutConfig.borderRadius.large,
              layoutConfig.spacing.section.padding.x,
              layoutConfig.spacing.section.padding.y
            )}
          >
            <section
              className={clsx(
                "border border-border/70 bg-background/70 text-sm",
                layoutConfig.spacing.element.padding.x,
                layoutConfig.spacing.element.padding.y,
                layoutConfig.borderRadius.medium
              )}
            >
              <div className="font-semibold text-primary">{statusLabel}</div>
              {showActivityBar ? (
                <div className="relative mt-3 h-1 overflow-hidden rounded-full bg-primary/20">
                  <div className="absolute inset-y-0 left-0 w-1/3 rounded-full bg-primary/70 animate-indeterminate" />
                </div>
              ) : null}
              {isPolling ? <div className="mt-2 text-xs text-text/60">{t("analyze.status.polling")}</div> : null}
              {error ? (
                <div className="mt-2 rounded border border-error/40 bg-error/10 px-3 py-2 text-xs text-error">
                  {error}
                </div>
              ) : null}
              {!runId ? <div className="mt-2 text-xs text-text/60">{t("analyze.status.noRun")}</div> : null}
            </section>

            <div className="grid gap-3 sm:grid-cols-2">
              <MetricCard
                title={t("analyze.metrics.ingredients.title")}
              description={t("analyze.metrics.ingredients.description")}
              value={ingredientMetric.total}
              delta={ingredientMetric.newlyAdded}
            />
            <MetricCard
              title={t("analyze.metrics.units.title")}
              description={t("analyze.metrics.units.description")}
              value={unitMetric.total}
              delta={unitMetric.newlyAdded}
            />
          </div>

          </aside>

          <section
            className={clsx(
              "flex min-h-[400px] flex-col overflow-hidden border border-border bg-panel",
              layoutConfig.borderRadius.large,
              layoutConfig.shadow.panel
            )}
          >
            <div
              className={clsx(
                "flex min-h-0 flex-1 flex-col",
                layoutConfig.spacing.section.padding.x,
                layoutConfig.spacing.section.padding.y
              )}
            >
              <LogViewer
                className={clsx("min-h-0 flex-1")}
                logs={logEntries}
                titleKey="analyze.logTitle"
                summaryKey="analyze.summary"
              />
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};

const normalizeKey = (value?: string | null): string => (value ?? "").trim().toLowerCase();

const buildIngredientKey = (ingredient: ReviewIngredient): string => {
  const source =
    ingredient.foodSelection?.name ||
    ingredient.foodOriginalName ||
    ingredient.name ||
    ingredient.foodMatch?.name ||
    `${ingredient.sectionIndex}:${ingredient.ingredientIndex}`;
  const normalized = normalizeKey(source);
  return normalized || `${ingredient.sectionIndex}:${ingredient.ingredientIndex}`;
};

const buildUnitKey = (ingredient: ReviewIngredient): string | null => {
  const source =
    ingredient.unitSelection?.name ||
    ingredient.unitOriginalName ||
    ingredient.unit ||
    ingredient.unitMatch?.name ||
    null;
  if (!source) {
    return null;
  }
  return normalizeKey(source) || source;
};

const isNewIngredient = (ingredient: ReviewIngredient): boolean => {
  const status = (ingredient.foodStatus || "").toLowerCase();
  return (
    status === "new" ||
    Boolean(ingredient.foodNewId) ||
    (!ingredient.foodMatch?.id && Boolean(ingredient.foodSuggestion))
  );
};

const isNewUnit = (ingredient: ReviewIngredient): boolean => {
  const status = (ingredient.unitStatus || "").toLowerCase();
  return (
    status === "new" ||
    Boolean(ingredient.unitNewId) ||
    (!ingredient.unitMatch?.id && Boolean(ingredient.unitSuggestion))
  );
};

const computeIngredientMetric = (data: ReviewData): MetricValue => {
  const uniqueIngredients = new Set<string>();
  const newIngredients = new Set<string>();
  data.ingredients.forEach((ingredient) => {
    const key = buildIngredientKey(ingredient);
    uniqueIngredients.add(key);
    if (isNewIngredient(ingredient)) {
      newIngredients.add(key);
    }
  });
  return { total: uniqueIngredients.size, newlyAdded: newIngredients.size };
};

const computeUnitMetric = (data: ReviewData): MetricValue => {
  const uniqueUnits = new Set<string>();
  const newUnits = new Set<string>();
  data.ingredients.forEach((ingredient) => {
    const key = buildUnitKey(ingredient);
    if (!key) {
      return;
    }
    uniqueUnits.add(key);
    if (isNewUnit(ingredient)) {
      newUnits.add(key);
    }
  });
  return { total: uniqueUnits.size, newlyAdded: newUnits.size };
};

interface MetricCardProps {
  title: string;
  description: string;
  value: number | null;
  delta: number | null;
}

const MetricCard: React.FC<MetricCardProps> = ({ title, description, value, delta }) => (
  <div
    className={clsx(
      "border border-border bg-panel shadow-sm",
      layoutConfig.spacing.layout.container.x,
      layoutConfig.spacing.layout.container.y,
      layoutConfig.borderRadius.large
    )}
  >
    <div className="text-xs font-semibold uppercase tracking-wide text-text/60">{title}</div>
    <div className={clsx("mt-2 flex items-baseline", layoutConfig.spacing.item.gap)}>
      <span className="text-3xl font-semibold text-primary">{value === null ? "–" : value}</span>
      {delta !== null ? <span className="text-sm font-semibold text-success">+{delta}</span> : null}
    </div>
    <p className="mt-1 text-xs text-text/70">{description}</p>
  </div>
);
