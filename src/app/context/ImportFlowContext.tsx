import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { LogEntry } from "../components/LogViewer";

export type ImportStatus =
  | "idle"
  | "uploading"
  | "uploaded"
  | "starting"
  | "analyzing"
  | "completed"
  | "failed"
  | "aborted";

interface UploadInfo {
  uploadId: string;
  fileName: string;
  recipeName: string;
}

interface ImportFlowContextValue {
  uploadId: string | null;
  fileName: string | null;
  recipeName: string | null;
  runId: string | null;
  status: ImportStatus;
  error: string | null;
  logs: LogEntry[];
  logCursor: number;
  setUploadInfo: (info: UploadInfo) => void;
  setRunId: (runId: string | null) => void;
  setStatus: (status: ImportStatus) => void;
  setError: (message: string | null) => void;
  appendLogs: (entries: LogEntry[], nextCursor: number) => void;
  resetLogs: () => void;
  reset: () => void;
}

const ImportFlowContext = createContext<ImportFlowContextValue | undefined>(undefined);

export const ImportFlowProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [recipeName, setRecipeName] = useState<string | null>(null);
  const [runId, setRunIdState] = useState<string | null>(null);
  const [status, setStatusState] = useState<ImportStatus>("idle");
  const [error, setErrorState] = useState<string | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [logCursor, setLogCursor] = useState(0);

  const setUploadInfo = useCallback(({ uploadId: id, fileName: name, recipeName: recipe }: UploadInfo) => {
    setUploadId(id);
    setFileName(name);
    setRecipeName(recipe);
    setStatusState("uploaded");
    setErrorState(null);
    setLogs([]);
    setLogCursor(0);
    setRunIdState(null);
  }, []);

  const setRunId = useCallback((id: string | null) => {
    setRunIdState(id);
  }, []);

  const setStatus = useCallback((nextStatus: ImportStatus) => {
    setStatusState(nextStatus);
  }, []);

  const setError = useCallback((message: string | null) => {
    setErrorState(message);
  }, []);

  const appendLogs = useCallback(
    (entries: LogEntry[], nextCursor: number) => {
      if (entries.length === 0 && nextCursor === logCursor) {
        return;
      }
      setLogs((previous) => {
        if (!entries.length) {
          return previous;
        }
        const existingIds = new Set(previous.map((entry) => entry.id));
        const merged = [...previous];
        for (const entry of entries) {
          if (!existingIds.has(entry.id)) {
            merged.push(entry);
          }
        }
        return merged;
      });
      setLogCursor(nextCursor);
    },
    [logCursor]
  );

  const resetLogs = useCallback(() => {
    setLogs([]);
    setLogCursor(0);
  }, []);

  const reset = useCallback(() => {
    setUploadId(null);
    setFileName(null);
    setRecipeName(null);
    setRunIdState(null);
    setStatusState("idle");
    setErrorState(null);
    setLogs([]);
    setLogCursor(0);
  }, []);

  const value = useMemo(
    () => ({
      uploadId,
      fileName,
      recipeName,
      runId,
      status,
      error,
      logs,
      logCursor,
      setUploadInfo,
      setRunId,
      setStatus,
      setError,
      appendLogs,
      resetLogs,
      reset
    }),
    [
      appendLogs,
      error,
      fileName,
      logCursor,
      logs,
      recipeName,
      reset,
      resetLogs,
      runId,
      setError,
      setRunId,
      setStatus,
      setUploadInfo,
      status,
      uploadId
    ]
  );

  return <ImportFlowContext.Provider value={value}>{children}</ImportFlowContext.Provider>;
};

export const useImportFlow = (): ImportFlowContextValue => {
  const context = useContext(ImportFlowContext);
  if (!context) {
    throw new Error("useImportFlow muss innerhalb eines ImportFlowProvider verwendet werden.");
  }
  return context;
};
