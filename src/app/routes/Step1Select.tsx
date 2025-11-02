import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import clsx from "clsx";
import { DropZone } from "../components/DropZone";
import { layoutConfig } from "../../config/layout.config";
import { useImportFlow } from "../context/ImportFlowContext";
import { useStepNavigation } from "../App";
import { startAnalysis, uploadPdf } from "../api/imports";

export const Step1Select: React.FC = () => {
  const { t } = useTranslation();
  const {
    uploadId,
    fileName,
    recipeName,
    runId,
    status,
    error,
    setUploadInfo,
    setRunId,
    setStatus,
    setError,
    resetLogs
  } = useImportFlow();
  const { setNextHandler, setNextDisabled } = useStepNavigation();
  const [localError, setLocalError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const hints = t("select.hints", { returnObjects: true }) as string[];

  const statusMessage = useMemo(() => {
    switch (status) {
      case "uploading":
        return t("select.status.uploading");
      case "uploaded":
        return t("select.status.uploaded");
      case "starting":
        return t("select.status.starting");
      case "analyzing":
        return t("select.status.analyzing");
      case "completed":
        return t("select.status.completed");
      case "failed":
        return t("select.status.failed");
      case "aborted":
        return t("select.status.aborted");
      default:
        return null;
    }
  }, [status, t]);

  const handleUpload = useCallback(
    async (files: FileList) => {
      const file = files.item(0);
      if (!file) {
        return;
      }
      if (file.type && file.type !== "application/pdf") {
        const message = t("select.errors.unsupportedType");
        setLocalError(message);
        setError(message);
        return;
      }
      setLocalError(null);
      setError(null);
      setIsUploading(true);
      setStatus("uploading");
      setNextDisabled(true);
      resetLogs();
      try {
        const response = await uploadPdf(file);
        setUploadInfo(response);
        setLocalError(null);
        setNextDisabled(false);
      } catch (uploadError) {
        const message = uploadError instanceof Error ? uploadError.message : t("select.errors.uploadFailed");
        setLocalError(message);
        setError(message);
        setStatus("failed");
        setNextDisabled(true);
      } finally {
        setIsUploading(false);
      }
    },
    [resetLogs, setError, setNextDisabled, setStatus, setUploadInfo, t]
  );

  useEffect(() => {
    setNextDisabled(Boolean(!uploadId && !runId) || status === "uploading" || status === "starting");
  }, [runId, setNextDisabled, status, uploadId]);

  useEffect(() => {
    setNextHandler(async () => {
      if (runId) {
        return true;
      }
      if (!uploadId) {
        const message = t("select.errors.noUpload");
        setLocalError(message);
        setError(message);
        return false;
      }
      setStatus("starting");
      setNextDisabled(true);
      try {
        const response = await startAnalysis(uploadId);
        setRunId(response.runId);
        setStatus("analyzing");
        setError(null);
        return true;
      } catch (analysisError) {
        const message = analysisError instanceof Error ? analysisError.message : t("select.errors.analysisFailed");
        setLocalError(message);
        setError(message);
        setStatus("failed");
        setNextDisabled(false);
        return false;
      }
    });

    return () => {
      setNextHandler(null);
      setNextDisabled(false);
    };
  }, [runId, uploadId, setNextHandler, setRunId, setStatus, setNextDisabled, setError, t]);

  return (
    <div className="flex-1 overflow-y-auto">
      <div className={clsx("grid lg:grid-cols-[3fr,2fr]", layoutConfig.spacing.layout.columns)}>
        <div className={clsx("border border-border bg-panel shadow-sm", layoutConfig.spacing.element.vertical, layoutConfig.spacing.layout.container.x, layoutConfig.spacing.layout.container.y, layoutConfig.borderRadius.large)}>
          <h2 className="text-2xl font-semibold">{t("steps.select.title")}</h2>
          <p className="text-sm text-text/70">{t("steps.select.subtitle")}</p>
          <ul className={clsx("text-sm text-text/80", layoutConfig.spacing.element.vertical)}>
            {hints.map((hint) => (
              <li key={hint} className={clsx("border border-border/70 bg-background/80", layoutConfig.spacing.element.padding.x, layoutConfig.spacing.element.padding.y, layoutConfig.borderRadius.medium)}>
                {hint}
              </li>
            ))}
          </ul>
          <div className={clsx("mt-6 rounded-md border border-border/70 bg-background/60 p-4 text-sm text-text/80", layoutConfig.borderRadius.medium)}>
            {fileName ? (
              <div className="flex flex-col gap-1">
                <span className="font-semibold text-primary">{t("select.selectedFile", { fileName })}</span>
                {recipeName ? <span className="text-xs text-text/60">{t("select.recipeName", { recipeName })}</span> : null}
              </div>
            ) : (
              <span>{t("select.noFileSelected")}</span>
            )}
            {statusMessage ? <div className="mt-3 text-xs text-text/70">{statusMessage}</div> : null}
            {(localError || error) && (
              <div className="mt-3 rounded border border-error/40 bg-error/10 px-3 py-2 text-xs text-error">
                {localError ?? error}
              </div>
            )}
            {isUploading ? <div className="mt-3 text-xs text-text/60">{t("select.status.uploading")}</div> : null}
          </div>
        </div>
        <DropZone onFilesSelected={handleUpload} />
      </div>
    </div>
  );
};
