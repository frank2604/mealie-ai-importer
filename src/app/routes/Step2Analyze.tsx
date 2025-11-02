import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { LogViewer, LogEntry } from "../components/LogViewer";
import clsx from "clsx";
import { layoutConfig } from "../../config/layout.config";
import { useImportFlow } from "../context/ImportFlowContext";
import { useStepNavigation } from "../App";
import { fetchRunLogs, fetchRunStatus, mapApiLogEntries } from "../api/imports";

interface MetricItem {
  id: string;
  value: string;
  delta: string;
  status: "up" | "down" | "neutral";
}

export const Step2Analyze: React.FC = () => {
  const { t } = useTranslation();
  const { runId, status, error, logs, logCursor, appendLogs, setStatus, setError } = useImportFlow();
  const { setNextHandler, setNextDisabled } = useStepNavigation();
  const [isPolling, setIsPolling] = useState(false);

  const logEntries = useMemo<LogEntry[]>(() => logs, [logs]);

  const metrics: MetricItem[] = [
    { id: "ingredients", value: "18", delta: "+3", status: "up" },
    { id: "units", value: "7", delta: "+1", status: "up" },
    { id: "confidence", value: "86%", delta: "+4%", status: "neutral" }
  ];

  useEffect(() => {
    setNextHandler(null);
    if (!runId) {
      setNextDisabled(true);
      return () => {
        setNextDisabled(false);
      };
    }
    setNextDisabled(status !== "completed");
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
        const [statusResult, logResult] = await Promise.all([fetchRunStatus(runId), fetchRunLogs(runId, logCursor)]);
        if (!active) {
          return;
        }
        if (statusResult.status === "running") {
          setStatus("analyzing");
        } else if (statusResult.status === "starting") {
          setStatus("starting");
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
        if (logResult.entries.length) {
          appendLogs(mapApiLogEntries(logResult.entries), logResult.nextCursor);
        }
        if (["completed", "failed", "aborted"].includes(statusResult.status)) {
          setNextDisabled(statusResult.status !== "completed");
          setIsPolling(false);
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
  }, [appendLogs, logCursor, runId, setError, setNextDisabled, setStatus]);

  const statusLabel = useMemo(() => {
    switch (status) {
      case "starting":
        return t("analyze.status.starting");
      case "analyzing":
        return t("analyze.status.running");
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

  return (
    <div className="flex-1 overflow-y-auto">
      <div className={clsx("grid xl:grid-cols-[2fr,1fr]", layoutConfig.spacing.layout.columns)}>
        <div className={clsx("flex flex-col", layoutConfig.spacing.layout.columns)}>
          <div className={clsx("grid sm:grid-cols-3", layoutConfig.spacing.section.gap)}>
            {metrics.map((item) => (
              <div key={item.id} className={clsx("border border-border bg-panel shadow-sm", layoutConfig.spacing.layout.container.x, layoutConfig.spacing.layout.container.y, layoutConfig.borderRadius.large)}>
                <div className="text-xs font-semibold uppercase tracking-wide text-text/60">
                  {t(`analyze.metrics.${item.id}.title`)}
                </div>
                <div className={clsx("mt-2 flex items-baseline", layoutConfig.spacing.item.gap)}>
                  <span className="text-3xl font-semibold text-primary">{item.value}</span>
                  <span
                    className={
                      item.status === "down"
                        ? "text-sm font-semibold text-error"
                        : item.status === "up"
                          ? "text-sm font-semibold text-success"
                          : "text-sm font-semibold text-text/60"
                    }
                  >
                    {item.delta}
                  </span>
                </div>
                <p className="mt-1 text-xs text-text/70">{t(`analyze.metrics.${item.id}.description`)}</p>
              </div>
            ))}
          </div>
          <LogViewer logs={logEntries} titleKey="analyze.logTitle" summaryKey="analyze.summary" />
        </div>
        <aside className={clsx("flex h-full flex-col justify-between border border-border bg-panel shadow-sm", layoutConfig.spacing.section.gap, layoutConfig.spacing.layout.container.x, layoutConfig.spacing.layout.container.y, layoutConfig.borderRadius.large)}>
          <section>
            <h3 className="text-lg font-semibold text-primary">{t("steps.analyze.title")}</h3>
            <p className="mt-2 text-sm text-text/70">{t("steps.analyze.subtitle")}</p>
            <div className="mt-4 rounded border border-border/70 bg-background/70 px-4 py-3 text-sm">
              <div className="font-semibold text-primary">{statusLabel}</div>
              {isPolling ? <div className="mt-2 text-xs text-text/60">{t("analyze.status.polling")}</div> : null}
              {error ? (
                <div className="mt-2 rounded border border-error/40 bg-error/10 px-3 py-2 text-xs text-error">
                  {error}
                </div>
              ) : null}
              {!runId ? <div className="mt-2 text-xs text-text/60">{t("analyze.status.noRun")}</div> : null}
            </div>
          </section>
          <section className={clsx("text-sm text-text/80", layoutConfig.spacing.element.vertical)}>
            {(t("analyze.checklist", { returnObjects: true }) as string[]).map((item) => (
              <div key={item} className={clsx("border border-border/70 bg-background/80", layoutConfig.spacing.element.padding.x, layoutConfig.spacing.element.padding.y, layoutConfig.borderRadius.medium)}>
                • {item}
              </div>
            ))}
          </section>
          <section className={clsx("border border-border bg-background/60 text-xs text-text/60", layoutConfig.spacing.element.padding.x, layoutConfig.spacing.element.padding.y, layoutConfig.borderRadius.medium)}>
            {t("notifications.comingSoon")}
          </section>
        </aside>
      </div>
    </div>
  );
};
