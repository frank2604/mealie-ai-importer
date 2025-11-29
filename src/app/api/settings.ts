import { BASE_URL } from "./imports";

export interface ApiKeys {
  mealieToken: string | null;
  mealieBaseUrl: string | null;
  llmApiKey: string | null;
  llmModel: string | null;
  llmVisionModel: string | null;
}

const parseError = async (response: Response): Promise<Error> => {
  try {
    const data = await response.json();
    const detail = typeof data === "string" ? data : data?.detail;
    if (detail) {
      return new Error(detail);
    }
  } catch {
    // ignore
  }
  return new Error(response.statusText || `Request failed with status ${response.status}`);
};

export const fetchApiKeys = async (): Promise<ApiKeys> => {
  const response = await fetch(`${BASE_URL}/settings/api-keys`, { method: "GET", credentials: "same-origin" });
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as ApiKeys;
};

export const saveApiKeys = async (payload: Partial<ApiKeys>): Promise<ApiKeys> => {
  const response = await fetch(`${BASE_URL}/settings/api-keys`, {
    method: "PUT",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as ApiKeys;
};
