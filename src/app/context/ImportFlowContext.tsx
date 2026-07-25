import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import type { LogEntry } from "../components/LogViewer";
import { fetchActiveRun, fetchRunStatus } from "../api/imports";

export type ImportStatus =
  | "idle"
  | "uploading"
  | "uploaded"
  | "starting"
  | "analyzing"
  | "review"
  | "transferring"
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
  analysisLogs: LogEntry[];
  analysisCursor: number;
  transferLogs: LogEntry[];
  transferCursor: number;
  setUploadInfo: (info: UploadInfo) => void;
  setRunId: (runId: string | null) => void;
  setStatus: (status: ImportStatus) => void;
  setError: (message: string | null) => void;
  appendAnalysisLogs: (entries: LogEntry[], nextCursor: number) => void;
  appendTransferLogs: (entries: LogEntry[], nextCursor: number) => void;
  resetLogs: () => void;
  resetTransferLogs: () => void;
  reset: () => void;
  setRecipeNameValue: (name: string | null) => void;
  hasExternalUpdate: boolean;
  acknowledgeExternalUpdate: () => void;
  /** True when the app detected on load that another session is actively running
   *  an import (analyzing / transferring). Shows a blocking banner so the user
   *  knows they should wait. */
  isOccupied: boolean;
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
  const [analysisLogs, setAnalysisLogs] = useState<LogEntry[]>([]);
  const [analysisCursor, setAnalysisCursor] = useState(0);
  const [transferLogs, setTransferLogs] = useState<LogEntry[]>([]);
  const [transferCursor, setTransferCursor] = useState(0);
  const [hasExternalUpdate, setHasExternalUpdate] = useState(false);
  const [isOccupied, setIsOccupied] = useState(false);

  const setUploadInfo = useCallback(({ uploadId: id, fileName: name, recipeName: recipe }: UploadInfo) => {
    setUploadId(id);
    setFileName(name);
    setRecipeName(recipe);
    setStatusState("uploaded");
    setErrorState(null);
    setAnalysisLogs([]);
    setAnalysisCursor(0);
    setTransferLogs([]);
    setTransferCursor(0);
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

  const setRecipeNameValue = useCallback((name: string | null) => {
    setRecipeName(name);
  }, []);

  const appendAnalysisLogs = useCallback(
    (entries: LogEntry[], nextCursor: number) => {
      if (entries.length === 0 && nextCursor === analysisCursor) {
        return;
      }
      setAnalysisLogs((previous) => {
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
      setAnalysisCursor(nextCursor);
    },
    [analysisCursor]
  );

  const appendTransferLogs = useCallback(
    (entries: LogEntry[], nextCursor: number) => {
      if (entries.length === 0 && nextCursor === transferCursor) {
        return;
      }
      setTransferLogs((previous) => {
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
      setTransferCursor(nextCursor);
    },
    [transferCursor]
  );

  const resetLogs = useCallback(() => {
    setAnalysisLogs([]);
    setAnalysisCursor(0);
    setTransferLogs([]);
    setTransferCursor(0);
  }, []);

  const resetTransferLogs = useCallback(() => {
    setTransferLogs([]);
    setTransferCursor(0);
  }, []);

  const reset = useCallback(() => {
    setUploadId(null);
    setFileName(null);
    setRecipeName(null);
    setRunIdState(null);
    setStatusState("idle");
    setErrorState(null);
    setAnalysisLogs([]);
    setAnalysisCursor(0);
    setTransferLogs([]);
    setTransferCursor(0);
    clearPersistedState();
  }, []);

  const acknowledgeExternalUpdate = useCallback(() => {
    setHasExternalUpdate(false);
  }, []);

  useEffect(() => {
    let active = true;
    fetchActiveRun()
      .then((run) => {
        if (!active) {
          return;
        }
        const nextStatus = (run.status as ImportStatus) ?? "analyzing";
        // Detect if another browser session is actively running an import that
        // this session did not start. Show an "occupied" banner in that case.
        const persisted = persistedRef.current;
        const isForeignRun =
          ["analyzing", "transferring", "starting"].includes(nextStatus) &&
          persisted?.runId !== run.runId;
        if (isForeignRun) {
          setIsOccupied(true);
        }
        setRunIdState(run.runId);
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
        // The server reports no active run (GET /imports/active -> 404). A
        // runId was already restored from localStorage by the useState
        // initializers above, but it may be stale — e.g. an archived run from
        // an earlier session on this browser. Validate it: if that run no
        // longer exists, reset to a clean state so a fresh upload -> analyze
        // can start. Leaving a dead runId in place wedges the UI into polling a
        // 404 run and silently blocks new imports (exactly what happened for a
        // second user whose browser still held an old runId).
        const staleId = runId ?? persistedRef.current?.runId ?? null;
        if (!staleId) {
          return;
        }
        fetchRunStatus(staleId)
          .then((result) => {
            if (!active) {
              return;
            }
            if (!result) {
              persistedRef.current = null;
              reset();
            }
          })
          .catch(() => {
            // Network error while validating — leave state untouched and retry
            // on the next load rather than wiping a possibly-live run.
          });
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

  useEffect(() => {
    const handleStorage = (event: StorageEvent) => {
      if (event.key !== STORAGE_KEY || !event.newValue) {
        return;
      }
      try {
        const parsed = JSON.parse(event.newValue);
        if (parsed.runId && parsed.runId !== runId) {
          setRunIdState(parsed.runId);
        }
        if (parsed.status && parsed.status !== status) {
          setStatusState(parsed.status as ImportStatus);
        }
        if (parsed.recipeName && parsed.recipeName !== recipeName) {
          setRecipeName(parsed.recipeName);
        }
        if (parsed.uploadId && parsed.uploadId !== uploadId) {
          setUploadId(parsed.uploadId);
        }
        if (parsed.fileName && parsed.fileName !== fileName) {
          setFileName(parsed.fileName);
        }
        setHasExternalUpdate(true);
      } catch {
        // ignore
      }
    };
    window.addEventListener("storage", handleStorage);
    return () => {
      window.removeEventListener("storage", handleStorage);
    };
  }, [fileName, recipeName, runId, status, uploadId]);

  const value = useMemo(
    () => ({
      uploadId,
      fileName,
      recipeName,
      runId,
      status,
      error,
      analysisLogs,
      analysisCursor,
      transferLogs,
      transferCursor,
      setUploadInfo,
      setRunId,
      setStatus,
      setError,
      appendAnalysisLogs,
      appendTransferLogs,
      resetLogs,
      resetTransferLogs,
      reset,
      setRecipeNameValue,
      hasExternalUpdate,
      acknowledgeExternalUpdate,
      isOccupied
    }),
    [
      analysisCursor,
      analysisLogs,
      appendAnalysisLogs,
      appendTransferLogs,
      error,
      fileName,
      recipeName,
      reset,
      resetLogs,
      resetTransferLogs,
      setRecipeNameValue,
      runId,
      setError,
      acknowledgeExternalUpdate,
      setRunId,
      setStatus,
      hasExternalUpdate,
      isOccupied,
      setUploadInfo,
      status,
      transferCursor,
      transferLogs,
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
