import { BASE_URL } from "./imports";

export interface PromptModuleConfig {
  user1: string;
  user2: string;
  system: string;
}

export interface LlmModuleConfig {
  model: string | null;
  temperature: number | null;
  top_p: number | null;
  max_output_tokens: number | null;
}

export interface LlmModelOption {
  id: string;
  supportsSampling: boolean;
}

export type PromptLocaleConfig = Record<string, PromptModuleConfig>;

export interface PromptResponse {
  prompts: Record<string, PromptLocaleConfig>;
  defaults: Record<string, PromptLocaleConfig>;
  llmConfig: Record<string, LlmModuleConfig>;
  llmDefaults: Record<string, LlmModuleConfig>;
  llmModels: LlmModelOption[];
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

export const fetchPrompts = async (): Promise<PromptResponse> => {
  const response = await fetch(`${BASE_URL}/prompts`, {
    method: "GET",
    credentials: "same-origin"
  });
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as PromptResponse;
};

export const savePrompts = async (
  payload: PromptResponse["prompts"],
  llmConfig: PromptResponse["llmConfig"]
): Promise<PromptResponse> => {
  const response = await fetch(`${BASE_URL}/prompts`, {
    method: "PUT",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompts: payload, llmConfig })
  });
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as PromptResponse;
};
