import type { LogEntry } from "../components/LogViewer";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api";
export const BASE_URL = API_BASE_URL.endsWith("/") ? API_BASE_URL.slice(0, -1) : API_BASE_URL;

export interface UploadPdfResult {
  uploadId: string;
  fileName: string;
  recipeName: string;
}

export interface StartAnalysisResult {
  runId: string;
  status: string;
  recipeName: string;
  startedAt: string;
}

export interface RunStatusResult {
  runId: string;
  status: string;
  recipeName: string;
  startedAt: string;
  completedAt?: string;
  error?: string;
}

export interface ApiLogEntry {
  id: string;
  level: string;
  message: string;
  timestamp: string;
}

export interface RunLogResult {
  entries: ApiLogEntry[];
  nextCursor: number;
}

export interface ActiveRunResult {
  runId: string;
  status: string;
  recipeName: string;
  startedAt: string;
  completedAt?: string;
}

const mapLogLevel = (level: string): LogEntry["level"] => {
  const normalized = level.toUpperCase();
  if (normalized === "WARN" || normalized === "WARNING") {
    return "WARN";
  }
  if (normalized === "ERROR" || normalized === "CRITICAL") {
    return "ERROR";
  }
  return "INFO";
};

const parseError = async (response: Response): Promise<Error> => {
  try {
    const data = await response.json();
    const detail = typeof data === "string" ? data : data?.detail;
    if (detail) {
      return new Error(detail);
    }
  } catch {
    // ignore – fall back to status text
  }
  return new Error(response.statusText || `Request failed with status ${response.status}`);
};

export const uploadPdf = async (file: File): Promise<UploadPdfResult> => {
  const body = new FormData();
  body.append("file", file, file.name);

  const response = await fetch(`${BASE_URL}/imports/upload`, {
    method: "POST",
    body,
    credentials: "same-origin"
  });

  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as UploadPdfResult;
};

export const startAnalysis = async (uploadId: string): Promise<StartAnalysisResult> => {
  const response = await fetch(`${BASE_URL}/imports/${uploadId}/start`, {
    method: "POST",
    credentials: "same-origin"
  });
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as StartAnalysisResult;
};

export const fetchRunStatus = async (runId: string): Promise<RunStatusResult | null> => {
  const response = await fetch(`${BASE_URL}/imports/${runId}`, {
    method: "GET",
    credentials: "same-origin"
  });
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as RunStatusResult;
};

export const fetchRunLogs = async (runId: string, after = 0): Promise<RunLogResult | null> => {
  const query = after > 0 ? `?after=${after}` : "";
  const response = await fetch(`${BASE_URL}/imports/${encodeURIComponent(runId)}/logs${query}`, {
    method: "GET",
    credentials: "same-origin"
  });
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as RunLogResult;
};

export const mapApiLogEntries = (entries: ApiLogEntry[]): LogEntry[] =>
  entries.map((entry) => ({
    id: entry.id,
    level: mapLogLevel(entry.level),
    message: entry.message,
    timestamp: entry.timestamp
  }));

export const fetchActiveRun = async (): Promise<ActiveRunResult> => {
  const response = await fetch(`${BASE_URL}/imports/active`, {
    method: "GET",
    credentials: "same-origin"
  });
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as ActiveRunResult;
};

export const resetWorkspace = async (): Promise<void> => {
  const response = await fetch(`${BASE_URL}/imports/workspace`, {
    method: "DELETE",
    credentials: "same-origin"
  });
  if (!response.ok) {
    throw await parseError(response);
  }
};
