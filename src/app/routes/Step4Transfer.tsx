import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowDownTrayIcon } from "@heroicons/react/24/outline";
import clsx from "clsx";
import { LogViewer } from "../components/LogViewer";
import { layoutConfig } from "../../config/layout.config";
import { useImportFlow, type ImportStatus } from "../context/ImportFlowContext";
import { useStepNavigation } from "../App";
import { archiveRun, fetchRunLogs, fetchRunStatus, mapApiLogEntries, startTransfer, resetWorkspace } from "../api/imports";

const formatDuration = (start: string | null, end: string | null, nowMs: number): string => {
  if (!start) {
    return "–";
  }
  const startMs = Date.parse(start);
  const endMs = end ? Date.parse(end) : nowMs;
  if (Number.isNaN(startMs) || Number.isNaN(endMs) || endMs <= startMs) {
    return "00:00";
  }
  const totalSeconds = Math.floor((endMs - startMs) / 1000);
  const minutes = Math.floor(totalSeconds / 60)
    .toString()
    .padStart(2, "0");
  const seconds = (totalSeconds % 60).toString().padStart(2, "0");
  return `${minutes}:${seconds}`;
};

export const Step4Transfer: React.FC = () => {
  const { t } = useTranslation();
  const { setNextHandler, setNextDisabled, setNextLabel } = useStepNavigation();
  const navigate = useNavigate();
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
    resetTransferLogs,
    setRecipeNameValue,
    reset: resetFlow,
    setRunId
  } = useImportFlow();
  const [isPolling, setIsPolling] = useState(false);
  const [isStartingTransfer, setIsStartingTransfer] = useState(false);
  const [isArchiving, setIsArchiving] = useState(false);
  const [transferStart, setTransferStart] = useState<string | null>(null);
  const [transferEnd, setTransferEnd] = useState<string | null>(null);
  const [nowMs, setNowMs] = useState<number>(Date.now());
  const transferRequestedRef = useRef(false);
  const previousStatusRef = useRef<ImportStatus | null>(null);

  const logEntries = useMemo(() => transferLogs, [transferLogs]);

  const archiveAndReset = useCallback(
    async (navigateHome: boolean) => {
      if (!runId) {
        return;
      }
      setIsArchiving(true);
      try {
        setError(null);
        await archiveRun(runId);
        resetTransferLogs();
        resetFlow();
        setRunId(null);
        setStatus("idle");
        try {
          await resetWorkspace();
        } catch {
          // ignore reset errors
        }
        if (navigateHome) {
          navigate("/", { replace: true });
        }
      } catch (archiveError) {
        const message = archiveError instanceof Error ? archiveError.message : String(archiveError);
        setError(message);
      } finally {
        setIsArchiving(false);
      }
    },
    [navigate, resetFlow, resetTransferLogs, runId, setError, setRunId, setStatus]
  );

  const confirmAndArchive = useCallback(
    async (navigateHome: boolean) => {
      const confirmed = window.confirm(
        t("transfer.confirmArchive", {
          defaultValue: "Der Lauf wird archiviert und alle Schritte werden geleert. Möchtest du fortfahren?"
        })
      );
      if (!confirmed) {
        return;
      }
      await archiveAndReset(navigateHome);
    },
    [archiveAndReset, t]
  );

  useEffect(() => {
    setNextHandler(() => async () => {
      if (!runId || status !== "completed") {
        navigate("/", { replace: true });
        return false;
      }
      await confirmAndArchive(true);
      return true;
    });
    setNextLabel(t("transfer.actions.newImport"));
    setNextDisabled(status !== "completed" || !runId || isArchiving);
    return () => {
      setNextDisabled(false);
      setNextLabel(null);
      setNextHandler(null);
    };
  }, [archiveAndReset, navigate, runId, setNextDisabled, setNextHandler, setNextLabel, status, t, isArchiving]);

  useEffect(() => {
    transferRequestedRef.current = false;
    setTransferStart(null);
    setTransferEnd(null);
    setNowMs(Date.now());
    previousStatusRef.current = null;
  }, [runId]);

  const triggerTransfer = useCallback(async () => {
    // Synchroner Wiedereintritts-Schutz: Verhindert, dass ein Timing-Wettlauf
    // (Auto-Start + parallele Statusabfrage) die Übertragung doppelt startet.
    if (!runId || transferRequestedRef.current) {
      return;
    }
    transferRequestedRef.current = true;
    setIsStartingTransfer(true);
    resetTransferLogs();
    try {
      const result = await startTransfer(runId);
      const nextStatus = (result.status as ImportStatus) || "transferring";
      setStatus(nextStatus);
      // Timer sofort beim Auslösen der Übertragung starten. Sich auf eine
      // Statusabfrage zu verlassen, die den "transferring"-Moment sieht, verpasst
      // schnelle Übertragungen (2–3 s < 2 s-Abfrageintervall) – dann bleibt der
      // Timer auf "–" stehen.
      if (nextStatus === "transferring") {
        setTransferStart(new Date().toISOString());
        setTransferEnd(null);
        previousStatusRef.current = "transferring";
      }
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
          const prev = previousStatusRef.current;
          setStatus(mapped);
          if (mapped === "transferring" && prev !== "transferring") {
            setTransferStart(new Date().toISOString());
            setTransferEnd(null);
          }
          if (["completed", "failed", "aborted"].includes(mapped) && transferStart && !transferEnd) {
            setTransferEnd(new Date().toISOString());
          }
          previousStatusRef.current = mapped;
        }
        if (statusResult.recipeName) {
          setRecipeNameValue(statusResult.recipeName);
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
          // Race condition: transfer may complete before the first log poll returns
          // entries (log file just flushed). Retry log fetch up to 3× with 800 ms
          // delay so the log panel is never empty after a fast transfer.
          if (statusResult.status !== "review" && !logResult?.entries.length && active) {
            for (let retry = 0; retry < 3; retry++) {
              await new Promise((res) => window.setTimeout(res, 800));
              if (!active) break;
              try {
                const retryLogs = await fetchRunLogs(runId, transferCursor, "transfer");
                if (retryLogs?.entries.length) {
                  appendTransferLogs(mapApiLogEntries(retryLogs.entries), retryLogs.nextCursor);
                  break;
                }
              } catch {
                break;
              }
            }
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

  useEffect(() => {
    if (!transferStart || transferEnd) {
      return;
    }
    const intervalId = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(intervalId);
  }, [transferEnd, transferStart]);

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
  const transferDuration = useMemo(
    () => formatDuration(transferStart, transferEnd, nowMs),
    [nowMs, transferEnd, transferStart]
  );
  const showActivityBar = status === "transferring" || status === "starting";

  const helperText = !runId ? t("transfer.status.noRun") : isPolling ? t("transfer.status.polling") : undefined;

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
                "border border-border/60 bg-background/70",
                layoutConfig.spacing.element.padding.x,
                layoutConfig.spacing.element.padding.y,
                layoutConfig.borderRadius.medium
              )}
            >
              <div className="text-base font-semibold text-primary">{statusLabel}</div>
              {showActivityBar ? (
                <div className="relative mt-3 h-1 overflow-hidden rounded-full bg-primary/20">
                  <div className="absolute inset-y-0 left-0 w-1/3 rounded-full bg-primary/70 animate-indeterminate" />
                </div>
              ) : null}
              {helperText ? <div className="mt-2 text-xs text-text/60">{helperText}</div> : null}
              {recipeName ? (
                <div className="mt-4 text-sm text-text/70">{t("transfer.recipeLabel", { recipeName })}</div>
              ) : null}
              {runId ? <div className="text-xs text-text/60">{t("transfer.runIdLabel", { runId })}</div> : null}
              {error ? (
                <div className="mt-3 rounded border border-error/40 bg-error/10 px-3 py-2 text-xs text-error">
                  {error}
                </div>
              ) : null}
            </section>
            <section
              className={clsx(
                "border border-border bg-background/70",
                layoutConfig.spacing.element.padding.x,
                layoutConfig.spacing.element.padding.y,
                layoutConfig.borderRadius.medium
              )}
            >
              <div className="text-xs font-semibold uppercase tracking-wide text-text/60">
                {t("transfer.metrics.duration.title")}
              </div>
              <div className="mt-2 text-3xl font-semibold text-primary">{transferDuration}</div>
              <p className="mt-1 text-xs text-text/70">{t("transfer.metrics.duration.description")}</p>
            </section>
            {/* Footer actions removed from left column; archive via footer button */}
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
                className="min-h-0 flex-1"
                logs={logEntries}
                titleKey="transfer.logTitle"
                summaryKey="transfer.summary"
              />
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};
