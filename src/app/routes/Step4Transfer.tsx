import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ArrowPathIcon, ArrowDownTrayIcon } from "@heroicons/react/24/outline";
import clsx from "clsx";
import { LogViewer } from "../components/LogViewer";
import { layoutConfig } from "../../config/layout.config";
import { useImportFlow, type ImportStatus } from "../context/ImportFlowContext";
import { useStepNavigation } from "../App";
import { fetchRunLogs, fetchRunStatus, mapApiLogEntries, startTransfer } from "../api/imports";

export const Step4Transfer: React.FC = () => {
  const { t } = useTranslation();
  const { setNextHandler, setNextDisabled } = useStepNavigation();
  const {
    runId,
    recipeName,
    status,
    error,
    transferLogs,
    transferCursor,
    appendTransferLogs,
    setError,
    setStatus,
    resetTransferLogs
  } = useImportFlow();
  const [isPolling, setIsPolling] = useState(false);
  const [isStartingTransfer, setIsStartingTransfer] = useState(false);
  const transferRequestedRef = useRef(false);

  const logEntries = useMemo(() => transferLogs, [transferLogs]);

  useEffect(() => {
    setNextHandler(null);
    setNextDisabled(true);
    return () => {
      setNextDisabled(false);
    };
  }, [setNextDisabled, setNextHandler]);

  useEffect(() => {
    transferRequestedRef.current = false;
  }, [runId]);

  const triggerTransfer = useCallback(async () => {
    if (!runId) {
      return;
    }
    transferRequestedRef.current = true;
    setIsStartingTransfer(true);
    resetTransferLogs();
    try {
      await startTransfer(runId);
      setStatus("transferring");
      setError(null);
    } catch (transferError) {
      const message = transferError instanceof Error ? transferError.message : String(transferError);
      setError(message);
      setStatus("review");
      transferRequestedRef.current = false;
    } finally {
      setIsStartingTransfer(false);
    }
  }, [resetTransferLogs, runId, setError, setStatus]);

  useEffect(() => {
    if (runId && status === "review" && !transferRequestedRef.current) {
      void triggerTransfer();
    }
  }, [runId, status, triggerTransfer]);

  useEffect(() => {
    if (!runId) {
      setIsPolling(false);
      return undefined;
    }
    let active = true;
    let timeoutId: number | undefined;

    const poll = async () => {
      setIsPolling(true);
      try {
        const [statusResult, logResult] = await Promise.all([
          fetchRunStatus(runId),
          fetchRunLogs(runId, transferCursor, "transfer")
        ]);
        if (!active) {
          return;
        }
        if (!statusResult) {
          setStatus("idle");
          setError(t("transfer.status.noRun"));
          setIsPolling(false);
          return;
        }
        const statusMap: Record<string, ImportStatus> = {
          transferring: "transferring",
          completed: "completed",
          review: "review",
          failed: "failed",
          aborted: "aborted",
          running: "analyzing",
          starting: "starting"
        };
        const mapped = statusMap[statusResult.status];
        if (mapped) {
          setStatus(mapped);
        }
        if (statusResult.error) {
          setError(statusResult.error);
        } else {
          setError(null);
        }
        if (logResult?.entries.length) {
          appendTransferLogs(mapApiLogEntries(logResult.entries), logResult.nextCursor);
        }
        if (["completed", "review", "failed", "aborted"].includes(statusResult.status)) {
          if (statusResult.status === "review") {
            transferRequestedRef.current = false;
          }
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
  }, [appendTransferLogs, runId, setError, setStatus, t, transferCursor]);

  const statusLabel = useMemo(() => {
    switch (status) {
      case "transferring":
        return t("transfer.status.transferring");
      case "completed":
        return t("transfer.status.completed");
      case "review":
        return t("transfer.status.review");
      case "failed":
        return t("transfer.status.failed");
      case "aborted":
        return t("transfer.status.aborted");
      default:
        return t("transfer.status.idle");
    }
  }, [status, t]);

  const helperText = !runId ? t("transfer.status.noRun") : isPolling ? t("transfer.status.polling") : undefined;
  const canStartTransfer = Boolean(runId) && !isStartingTransfer && status !== "transferring" && status !== "completed";
  const startButtonLabel = status === "failed" ? t("transfer.actions.retry") : t("transfer.actions.start");

  return (
    <div className="flex-1 overflow-y-auto">
      <div className={clsx("grid xl:grid-cols-[2fr,1fr]", layoutConfig.spacing.layout.columns)}>
        <div className={clsx("flex flex-col", layoutConfig.spacing.layout.columns)}>
          <LogViewer logs={logEntries} titleKey="transfer.logTitle" summaryKey="transfer.summary" />
        </div>
        <aside
          className={clsx(
            "flex h-full flex-col border border-border bg-panel shadow-sm",
            layoutConfig.spacing.section.gap,
            layoutConfig.spacing.layout.container.x,
            layoutConfig.spacing.layout.container.y,
            layoutConfig.borderRadius.large
          )}
        >
          <header>
            <h3 className="text-lg font-semibold">{t("steps.transfer.title")}</h3>
            <p className="mt-2 text-sm text-text/70">{t("steps.transfer.subtitle")}</p>
          </header>
          <section
            className={clsx(
              "border border-border/60 bg-background/70",
              layoutConfig.spacing.element.padding.x,
              layoutConfig.spacing.element.padding.y,
              layoutConfig.borderRadius.medium
            )}
          >
            <div className="text-xs font-semibold uppercase tracking-wide text-text/60">{t("transfer.summary")}</div>
            <div className="mt-2 text-base font-semibold text-primary">{statusLabel}</div>
            {helperText ? <div className="mt-1 text-xs text-text/60">{helperText}</div> : null}
            {recipeName ? <div className="mt-3 text-sm text-text/70">{t("transfer.recipeLabel", { recipeName })}</div> : null}
            {runId ? <div className="text-xs text-text/60">{t("transfer.runIdLabel", { runId })}</div> : null}
            {error ? (
              <div className="mt-3 rounded border border-error/40 bg-error/10 px-3 py-2 text-xs text-error">
                {error}
              </div>
            ) : null}
          </section>
          <div className="mt-auto">
            {status === "completed" ? (
              <button
                type="button"
                className={clsx(
                  "focus-ring inline-flex w-full items-center justify-center border border-border bg-panel text-sm font-semibold text-text hover:border-primary/60 hover:text-primary",
                  layoutConfig.spacing.item.gap,
                  layoutConfig.spacing.button.default.x,
                  layoutConfig.spacing.button.default.y,
                  layoutConfig.borderRadius.small
                )}
              >
                <ArrowDownTrayIcon className="h-4 w-4" aria-hidden="true" />
                {t("transfer.archive")}
              </button>
            ) : (
              <button
                type="button"
                onClick={() => {
                  transferRequestedRef.current = false;
                  void triggerTransfer();
                }}
                disabled={!canStartTransfer}
                className={clsx(
                  "focus-ring inline-flex w-full items-center justify-center border border-border bg-panel text-sm font-semibold text-text hover:border-primary/60 hover:text-primary disabled:cursor-not-allowed disabled:opacity-50",
                  layoutConfig.spacing.item.gap,
                  layoutConfig.spacing.button.default.x,
                  layoutConfig.spacing.button.default.y,
                  layoutConfig.borderRadius.small
                )}
              >
                <ArrowPathIcon className={clsx("h-4 w-4", isStartingTransfer && "animate-spin")} aria-hidden="true" />
                {startButtonLabel}
              </button>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
};
