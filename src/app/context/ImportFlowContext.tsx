import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import type { LogEntry } from "../components/LogViewer";
import { fetchActiveRun } from "../api/imports";

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

const STORAGE_KEY = "import-flow-state";

interface PersistedFlowState {
  uploadId: string | null;
  fileName: string | null;
  recipeName: string | null;
  runId: string | null;
  status: ImportStatus;
}

const hasWindow = typeof window !== "undefined";

const persistState = (state: PersistedFlowState) => {
  if (!hasWindow) {
    return;
  }
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // ignore storage issues
  }
};

const readPersistedState = (): PersistedFlowState | null => {
  if (!hasWindow) {
    return null;
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw);
    return {
      uploadId: parsed.uploadId ?? null,
      fileName: parsed.fileName ?? null,
      recipeName: parsed.recipeName ?? null,
      runId: parsed.runId ?? null,
      status: (parsed.status as ImportStatus) ?? "idle"
    };
  } catch {
    return null;
  }
};

const clearPersistedState = () => {
  if (!hasWindow) {
    return;
  }
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
};

const ImportFlowContext = createContext<ImportFlowContextValue | undefined>(undefined);

export const ImportFlowProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const persistedRef = useRef<PersistedFlowState | null>(null);
  if (persistedRef.current === null) {
    persistedRef.current = readPersistedState();
  }

  const [uploadId, setUploadId] = useState<string | null>(() => persistedRef.current?.uploadId ?? null);
  const [fileName, setFileName] = useState<string | null>(() => persistedRef.current?.fileName ?? null);
  const [recipeName, setRecipeName] = useState<string | null>(() => persistedRef.current?.recipeName ?? null);
  const [runId, setRunIdState] = useState<string | null>(() => persistedRef.current?.runId ?? null);
  const [status, setStatusState] = useState<ImportStatus>(() => persistedRef.current?.status ?? "idle");
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
    clearPersistedState();
  }, []);

  useEffect(() => {
    let active = true;
    fetchActiveRun()
      .then((run) => {
        if (!active) {
          return;
        }
        setRunIdState(run.runId);
        const nextStatus = (run.status as ImportStatus) ?? "analyzing";
        setStatusState(nextStatus);
        setRecipeName((prev) => prev ?? run.recipeName);
        persistState({
          uploadId,
          fileName,
          recipeName: run.recipeName ?? recipeName,
          runId: run.runId,
          status: nextStatus
        });
      })
      .catch(() => {
        const persisted = persistedRef.current;
        if (persisted?.runId && !runId) {
          setRunIdState(persisted.runId);
          setStatusState(persisted.status);
          setRecipeName((prev) => prev ?? persisted.recipeName);
        }
      });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    persistState({
      uploadId,
      fileName,
      recipeName,
      runId,
      status
    });
  }, [uploadId, fileName, recipeName, runId, status]);

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
