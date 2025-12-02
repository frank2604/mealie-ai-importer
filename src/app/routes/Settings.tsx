import { ChangeEvent, useEffect, useMemo, useState, useCallback } from "react";
import { Disclosure } from "@headlessui/react";
import { ChevronDownIcon } from "@heroicons/react/24/outline";
import clsx from "clsx";
import { useTranslation } from "react-i18next";
import { layoutConfig } from "../../config/layout.config";
import { useTheme } from "../../theme/useTheme";
import { availableLanguages } from "../../i18n/i18n";
import {
  fetchPrompts,
  savePrompts,
  type PromptLocaleConfig,
  type LlmModuleConfig,
  type LlmModelOption
} from "../api/prompts";
import { fetchApiKeys, saveApiKeys, type ApiKeys } from "../api/settings";

export const Settings: React.FC = () => {
  const { t, i18n } = useTranslation();
  const { theme, setTheme } = useTheme();
  const resolvedLanguage = i18n.resolvedLanguage ?? i18n.language;
  const activeLanguage = (availableLanguages.includes(resolvedLanguage as (typeof availableLanguages)[number])
    ? resolvedLanguage
    : availableLanguages[0]) as (typeof availableLanguages)[number];

  const [promptData, setPromptData] = useState<Record<string, PromptLocaleConfig>>({});
  const [promptDefaults, setPromptDefaults] = useState<Record<string, PromptLocaleConfig>>({});
  const [promptsLoading, setPromptsLoading] = useState(false);
  const [promptsError, setPromptsError] = useState<string | null>(null);
  const [isSavingPrompts, setIsSavingPrompts] = useState(false);
  const [hasPromptChanges, setHasPromptChanges] = useState(false);
  const [isAdminOverrideEnabled, setIsAdminOverrideEnabled] = useState(false);
  const [llmConfig, setLlmConfig] = useState<Record<string, LlmModuleConfig>>({});
  const [llmDefaults, setLlmDefaults] = useState<Record<string, LlmModuleConfig>>({});
  const [hasLlmChanges, setHasLlmChanges] = useState(false);
  const [llmModels, setLlmModels] = useState<LlmModelOption[]>([]);
  const [apiKeys, setApiKeys] = useState<ApiKeys>({
    mealieToken: null,
    mealieBaseUrl: null,
    llmApiKey: null,
    llmModel: null,
    llmVisionModel: null
  });
  const [apiKeysLoading, setApiKeysLoading] = useState(false);
  const [apiKeysError, setApiKeysError] = useState<string | null>(null);
  const [apiKeysSaving, setApiKeysSaving] = useState(false);
  const [hasApiKeyChanges, setHasApiKeyChanges] = useState(false);

  const promptModules = useMemo(
    () => [
      { id: "analysis", labelKey: "settings.prompts.analysis" },
      { id: "instructions", labelKey: "settings.prompts.instructions" },
      { id: "ingredients", labelKey: "settings.prompts.ingredients" },
      { id: "foodForms", labelKey: "settings.prompts.foodForms" },
      { id: "units", labelKey: "settings.prompts.units" },
      { id: "unitForms", labelKey: "settings.prompts.unitForms" },
      { id: "metadata", labelKey: "settings.prompts.metadata" },
      { id: "imageCrop", labelKey: "settings.prompts.imageCrop" }
    ],
    []
  );

  useEffect(() => {
    setPromptsLoading(true);
    setPromptsError(null);
    fetchPrompts()
      .then((response) => {
        setPromptData(response.prompts);
        setPromptDefaults(response.defaults);
        setLlmConfig(response.llmConfig || {});
        setLlmDefaults(response.llmDefaults || {});
        setLlmModels(response.llmModels || []);
        setHasPromptChanges(false);
        setHasLlmChanges(false);
      })
      .catch((error: Error) => {
        setPromptsError(error.message);
      })
      .finally(() => {
        setPromptsLoading(false);
      });
  }, []);

  useEffect(() => {
    setApiKeysLoading(true);
    setApiKeysError(null);
    fetchApiKeys()
      .then((response) => {
        setApiKeys(response);
        setHasApiKeyChanges(false);
      })
      .catch((error: Error) => {
        setApiKeysError(error.message);
      })
      .finally(() => setApiKeysLoading(false));
  }, []);

  const currentLocale = useMemo(() => (resolvedLanguage ?? "de").split("-")[0], [resolvedLanguage]);

  const currentPromptConfig = useMemo(() => {
    const localeData = promptData[currentLocale] || promptDefaults[currentLocale] || {};
    const fallback: PromptLocaleConfig = {};
    promptModules.forEach((module) => {
      const defaults = promptDefaults[currentLocale]?.[module.id] || { user1: "", user2: "", system: "" };
      const existing = localeData[module.id] || {};
      fallback[module.id] = {
        user1: existing.user1 ?? defaults.user1,
        user2: existing.user2 ?? defaults.user2,
        system: existing.system ?? defaults.system
      };
    });
    return fallback;
  }, [currentLocale, promptData, promptDefaults, promptModules]);

  const currentLlmConfig = useMemo(() => {
    const combined: Record<string, LlmModuleConfig> = {};
    promptModules.forEach((module) => {
      const defaults = llmDefaults[module.id] || {
        model: "",
        temperature: null,
        top_p: null,
        max_output_tokens: null
      };
      const existing = llmConfig[module.id] || {};
      combined[module.id] = {
        model: existing.model ?? defaults.model ?? "",
        temperature: existing.temperature ?? defaults.temperature ?? null,
        top_p: existing.top_p ?? defaults.top_p ?? null,
        max_output_tokens: existing.max_output_tokens ?? defaults.max_output_tokens ?? null
      };
    });
    return combined;
  }, [llmConfig, llmDefaults, promptModules]);

  const supportsSampling = useCallback(
    (modelId: string | null | undefined): boolean => {
      if (!modelId) return true;
      const found = llmModels.find((entry) => entry.id === modelId);
      if (found) return Boolean(found.supportsSampling);
      return true;
    },
    [llmModels]
  );

  const handleThemeChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const value = event.target.value as "light" | "dark";
    setTheme(value);
  };

  const handleLanguageChange = (event: ChangeEvent<HTMLSelectElement>) => {
    void i18n.changeLanguage(event.target.value);
  };

  const updatePromptValue = (moduleId: string, field: "user1" | "user2" | "system", value: string) => {
    setPromptData((previous) => {
      const next = { ...previous };
      const localeEntry = { ...(next[currentLocale] || {}) };
      const defaults = promptDefaults[currentLocale]?.[moduleId] || { user1: "", user2: "", system: "" };
      const existing = localeEntry[moduleId] || defaults;
      const updatedEntry = {
        user1: existing.user1 ?? defaults.user1 ?? "",
        user2: existing.user2 ?? defaults.user2 ?? "",
        system: existing.system ?? defaults.system ?? ""
      };
      updatedEntry[field] = value;
      localeEntry[moduleId] = updatedEntry;
      next[currentLocale] = localeEntry;
      return next;
    });
    setHasPromptChanges(true);
  };

  const handleResetModule = (moduleId: string) => {
    const confirmed = window.confirm(t("settings.prompts.resetModuleConfirm"));
    if (!confirmed) {
      return;
    }
    const defaultUser1 = promptDefaults[currentLocale]?.[moduleId]?.user1 ?? "";
    const defaultUser2 = promptDefaults[currentLocale]?.[moduleId]?.user2 ?? "";
    const defaultSystem = promptDefaults[currentLocale]?.[moduleId]?.system ?? "";
    const defaultLlm = llmDefaults[moduleId] || {
      model: "",
      temperature: null,
      top_p: null,
      max_output_tokens: null
    };
    setPromptData((previous) => {
      const next = { ...previous };
      const localeEntry = { ...(next[currentLocale] || {}) };
      localeEntry[moduleId] = {
        user1: defaultUser1,
        user2: defaultUser2,
        system: defaultSystem
      };
      next[currentLocale] = localeEntry;
      return next;
    });
    setLlmConfig((previous) => ({
      ...previous,
      [moduleId]: defaultLlm
    }));
    setHasPromptChanges(true);
    setHasLlmChanges(true);
  };

  const handleSavePrompts = async () => {
    setIsSavingPrompts(true);
    setPromptsError(null);
    try {
      const response = await savePrompts(promptData, llmConfig);
      setPromptData(response.prompts);
      setPromptDefaults(response.defaults);
      setLlmConfig(response.llmConfig || {});
      setLlmDefaults(response.llmDefaults || {});
      setLlmModels(response.llmModels || []);
      setHasPromptChanges(false);
      setHasLlmChanges(false);
    } catch (error) {
      setPromptsError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsSavingPrompts(false);
    }
  };

  const handleApiKeyChange = (field: keyof ApiKeys, value: string) => {
    setApiKeys((prev) => ({ ...prev, [field]: value }));
    setHasApiKeyChanges(true);
  };

  const handleLlmConfigChange = (
    moduleId: string,
    field: keyof LlmModuleConfig,
    value: string
  ) => {
    setLlmConfig((prev) => {
      const next = { ...prev };
      const entry = { ...(next[moduleId] || {}) };
      if (field === "temperature" || field === "top_p") {
        entry[field] = value === "" ? null : Number(value);
      } else if (field === "max_output_tokens") {
        entry[field] = value === "" ? null : Number.parseInt(value, 10);
      } else {
        entry[field] = value;
      }
      next[moduleId] = entry as LlmModuleConfig;
      return next;
    });
    setHasLlmChanges(true);
  };

  const handleSaveApiKeys = async () => {
    setApiKeysSaving(true);
    setApiKeysError(null);
    try {
      const response = await saveApiKeys(apiKeys);
      setApiKeys(response);
      setHasApiKeyChanges(false);
    } catch (error) {
      setApiKeysError(error instanceof Error ? error.message : String(error));
    } finally {
      setApiKeysSaving(false);
    }
  };

  return (
    <div className="w-full space-y-6">
      <section className={clsx("border border-border bg-panel p-6 shadow-sm", layoutConfig.borderRadius.large)}>
        <header>
          <h2 className="text-lg font-semibold">{t("settings.general.title")}</h2>
          <p className="mt-2 text-sm text-text/70">{t("settings.general.description")}</p>
        </header>
        <div className={clsx("mt-6 space-y-4")}>
          <div className="space-y-2">
            <label htmlFor="settings-theme" className="text-sm font-semibold text-text">
              {t("settings.general.themeLabel")}
            </label>
            <select
              id="settings-theme"
              value={theme}
              onChange={handleThemeChange}
              className={clsx(
                "focus-ring w-full border border-border bg-background px-4 py-2 text-sm font-medium text-text",
                layoutConfig.borderRadius.medium
              )}
            >
              <option value="light">{t("theme.light")}</option>
              <option value="dark">{t("theme.dark")}</option>
            </select>
          </div>
          <div className="space-y-2">
            <label htmlFor="settings-language" className="text-sm font-semibold text-text">
              {t("settings.general.languageLabel")}
            </label>
            <select
              id="settings-language"
              value={activeLanguage}
              onChange={handleLanguageChange}
              className={clsx(
                "focus-ring w-full border border-border bg-background px-4 py-2 text-sm font-medium text-text",
                layoutConfig.borderRadius.medium
              )}
            >
              {availableLanguages.map((lng) => (
                <option key={lng} value={lng}>
                  {t(`language.${lng}`)}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>
      <Disclosure defaultOpen={false}>
        {({ open }) => (
          <section className={clsx("border border-border bg-panel p-6 shadow-sm", layoutConfig.borderRadius.large)}>
            <Disclosure.Button className="flex w-full items-center justify-between text-left">
              <div>
                <h2 className="text-lg font-semibold">{t("settings.api.title")}</h2>
                <p className="mt-1 text-sm text-text/70">{t("settings.api.description")}</p>
              </div>
              <ChevronDownIcon
                className={clsx("h-4 w-4 transition-transform", open ? "rotate-180 text-primary" : "text-text/60")}
              />
            </Disclosure.Button>
            <Disclosure.Panel className="mt-4">
              <div className="space-y-4">
                {apiKeysError ? <div className="text-sm text-error">{apiKeysError}</div> : null}
                <div className="space-y-2">
                  <label htmlFor="settings-mealie-base" className="text-sm font-semibold text-text">
                    {t("settings.api.mealieBaseUrl")}
                  </label>
                  <input
                    id="settings-mealie-base"
                    type="text"
                    value={apiKeys.mealieBaseUrl ?? ""}
                    onChange={(event) => handleApiKeyChange("mealieBaseUrl", event.target.value)}
                    className={clsx(
                      "focus-ring w-full border border-border bg-background px-4 py-2 text-sm font-medium text-text",
                      layoutConfig.borderRadius.medium
                    )}
                    placeholder={t("settings.api.mealieBaseUrlPlaceholder")}
                    disabled={apiKeysLoading || apiKeysSaving}
                  />
                </div>
                <div className="space-y-2">
                  <label htmlFor="settings-mealie-token" className="text-sm font-semibold text-text">
                    {t("settings.api.mealieToken")}
                  </label>
                  <input
                    id="settings-mealie-token"
                    type="password"
                    value={apiKeys.mealieToken ?? ""}
                    onChange={(event) => handleApiKeyChange("mealieToken", event.target.value)}
                    className={clsx(
                      "focus-ring w-full border border-border bg-background px-4 py-2 text-sm font-medium text-text",
                      layoutConfig.borderRadius.medium
                    )}
                    placeholder={t("settings.api.mealieTokenPlaceholder")}
                    disabled={apiKeysLoading || apiKeysSaving}
                  />
                </div>
                <div className="space-y-2">
                  <label htmlFor="settings-llm-api-key" className="text-sm font-semibold text-text">
                    {t("settings.api.llmApiKey")}
                  </label>
                  <input
                    id="settings-llm-api-key"
                    type="password"
                    value={apiKeys.llmApiKey ?? ""}
                    onChange={(event) => handleApiKeyChange("llmApiKey", event.target.value)}
                    className={clsx(
                      "focus-ring w-full border border-border bg-background px-4 py-2 text-sm font-medium text-text",
                      layoutConfig.borderRadius.medium
                    )}
                    placeholder={t("settings.api.llmApiKeyPlaceholder")}
                    disabled={apiKeysLoading || apiKeysSaving}
                  />
                </div>
                <div className="space-y-2">
                  <label htmlFor="settings-llm-model" className="text-sm font-semibold text-text">
                    {t("settings.api.llmModel")}
                  </label>
                  <input
                    id="settings-llm-model"
                    type="text"
                    value={apiKeys.llmModel ?? ""}
                    onChange={(event) => handleApiKeyChange("llmModel", event.target.value)}
                    className={clsx(
                      "focus-ring w-full border border-border bg-background px-4 py-2 text-sm font-medium text-text",
                      layoutConfig.borderRadius.medium
                    )}
                    placeholder={t("settings.api.llmModelPlaceholder")}
                    disabled={apiKeysLoading || apiKeysSaving}
                  />
                </div>
                <div className="space-y-2">
                  <label htmlFor="settings-llm-vision-model" className="text-sm font-semibold text-text">
                    {t("settings.api.llmVisionModel")}
                  </label>
                  <input
                    id="settings-llm-vision-model"
                    type="text"
                    value={apiKeys.llmVisionModel ?? ""}
                    onChange={(event) => handleApiKeyChange("llmVisionModel", event.target.value)}
                    className={clsx(
                      "focus-ring w-full border border-border bg-background px-4 py-2 text-sm font-medium text-text",
                      layoutConfig.borderRadius.medium
                    )}
                    placeholder={t("settings.api.llmVisionModelPlaceholder")}
                    disabled={apiKeysLoading || apiKeysSaving}
                  />
                </div>
                <div className="flex justify-end">
                  <button
                    type="button"
                    disabled={!hasApiKeyChanges || apiKeysSaving || apiKeysLoading}
                    onClick={handleSaveApiKeys}
                    className={clsx(
                      "focus-ring border border-primary bg-primary px-4 py-2 text-sm font-semibold text-on-primary disabled:opacity-50",
                      layoutConfig.borderRadius.small
                    )}
                  >
                    {apiKeysSaving ? t("buttons.saving") : t("buttons.save")}
                  </button>
                </div>
              </div>
            </Disclosure.Panel>
          </section>
        )}
      </Disclosure>
      <div className="space-y-4">
        <div className={clsx("border border-border bg-panel shadow-sm", layoutConfig.borderRadius.large)}>
          <div className="flex w-full items-center justify-between gap-3 px-6 py-4 text-left">
            <div>
              <h2 className="text-lg font-semibold">{t("settings.prompts.title")}</h2>
              <p className="text-sm text-text/70">{t("settings.prompts.description")}</p>
            </div>
            <label className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-text/60">
              <input
                type="checkbox"
                className="h-4 w-4 accent-primary"
                checked={isAdminOverrideEnabled}
                onChange={(event) => setIsAdminOverrideEnabled(event.target.checked)}
              />
              <span>{t("settings.prompts.adminToggleLabel")}</span>
            </label>
          </div>
          <div className="space-y-4 px-6 pb-6">
            {promptModules.map((section) => {
                  const llm = currentLlmConfig[section.id] || {
                    model: "",
                    temperature: null,
                    top_p: null,
                    max_output_tokens: null
                  };
                  const moduleConfig = currentPromptConfig[section.id] || {
                    user1: "",
                    user2: "",
                    system: promptDefaults[currentLocale]?.[section.id]?.system ?? ""
                  };
                  return (
                    <Disclosure key={section.id}>
                      {({ open: moduleOpen }) => (
                        <div
                          className={clsx(
                            "border border-border bg-background/80 shadow-sm",
                          layoutConfig.borderRadius.medium
                        )}
                      >
                        <Disclosure.Button className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left">
                          <span className="text-sm font-semibold text-text">{t(section.labelKey)}</span>
                          <ChevronDownIcon
                            className={clsx(
                              "h-4 w-4 transition-transform",
                              moduleOpen ? "rotate-180 text-primary" : "text-text/60"
                            )}
                          />
                        </Disclosure.Button>
                        <Disclosure.Panel className={clsx("space-y-3 border-t border-border/60 px-4 py-4")}>
                          <div className="space-y-2">
                            <label
                              htmlFor={`${section.id}-prompt-user1`}
                              className="text-xs font-semibold uppercase tracking-wide text-text/60"
                            >
                              {t("settings.prompts.user1Label")}
                            </label>
                            <textarea
                              id={`${section.id}-prompt-user1`}
                              rows={8}
                              disabled={promptsLoading}
                              value={moduleConfig.user1}
                              onChange={(event) => updatePromptValue(section.id, "user1", event.target.value)}
                              className={clsx(
                                "focus-ring w-full border border-border bg-background px-4 py-3 text-sm text-text/80",
                                layoutConfig.borderRadius.medium,
                                promptsLoading && "opacity-60 cursor-not-allowed"
                              )}
                            />
                          </div>
                          <div className="space-y-2">
                            <label
                              htmlFor={`${section.id}-prompt-user2`}
                              className="text-xs font-semibold uppercase tracking-wide text-text/60"
                            >
                              {t("settings.prompts.user2Label")}
                            </label>
                            <textarea
                              id={`${section.id}-prompt-user2`}
                              rows={8}
                              readOnly={!isAdminOverrideEnabled || promptsLoading}
                              disabled={promptsLoading}
                              value={moduleConfig.user2}
                              className={clsx(
                                "focus-ring w-full border px-4 py-3 text-xs text-text/70",
                                layoutConfig.borderRadius.medium,
                                promptsLoading && "opacity-60 cursor-not-allowed",
                                isAdminOverrideEnabled
                                  ? "border-border bg-background text-text/80 text-sm"
                                  : "border-dashed border-border bg-background/70"
                              )}
                              onChange={(event) => {
                                if (!isAdminOverrideEnabled || promptsLoading) {
                                  return;
                                }
                                updatePromptValue(section.id, "user2", event.target.value);
                              }}
                            />
                          </div>
                          <div className="space-y-2">
                            <label
                              htmlFor={`${section.id}-prompt-system`}
                              className="text-xs font-semibold uppercase tracking-wide text-text/60"
                            >
                              {t("settings.prompts.systemLabel")}
                            </label>
                            <textarea
                              id={`${section.id}-prompt-system`}
                              rows={8}
                              readOnly={!isAdminOverrideEnabled || promptsLoading}
                              disabled={promptsLoading}
                              value={moduleConfig.system}
                              className={clsx(
                                "focus-ring w-full border px-4 py-3 text-xs text-text/70",
                                layoutConfig.borderRadius.medium,
                                promptsLoading && "opacity-60 cursor-not-allowed",
                                isAdminOverrideEnabled
                                  ? "border-border bg-background text-text/80 text-sm"
                                  : "border-dashed border-border bg-background/70"
                              )}
                              onChange={(event) => {
                                if (!isAdminOverrideEnabled || promptsLoading) {
                                  return;
                                }
                                updatePromptValue(section.id, "system", event.target.value);
                              }}
                            />
                          </div>
                          <div className="space-y-2">
                            <div className="text-xs font-semibold uppercase tracking-wide text-text/60">
                              {t("settings.prompts.llmSettings")}
                            </div>
                            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                              <div className="space-y-1">
                                <label className="text-xs font-semibold uppercase tracking-wide text-text/60">
                                  {t("settings.prompts.model")}
                                </label>
                                <select
                                  value={llm.model ?? ""}
                                  onChange={(event) => handleLlmConfigChange(section.id, "model", event.target.value)}
                                  disabled={promptsLoading}
                                  className={clsx(
                                    "focus-ring w-full border border-border bg-background px-3 py-2 text-sm text-text",
                                    layoutConfig.borderRadius.medium,
                                    promptsLoading && "opacity-60 cursor-not-allowed"
                                  )}
                                >
                                  <option value="">{t("settings.prompts.modelPlaceholder")}</option>
                                  {llmModels.map((option) => (
                                    <option key={option.id} value={option.id}>
                                      {option.id}
                                    </option>
                                  ))}
                                </select>
                              </div>
                              {supportsSampling(llm.model) ? (
                                <>
                                  <div className="space-y-1">
                                    <label className="text-xs font-semibold uppercase tracking-wide text-text/60">
                                      {t("settings.prompts.temperature")}
                                    </label>
                                    <input
                                      type="number"
                                      step="0.1"
                                      value={
                                        llm.temperature === null || llm.temperature === undefined ? "" : llm.temperature
                                      }
                                      onChange={(event) =>
                                        handleLlmConfigChange(section.id, "temperature", event.target.value)
                                      }
                                      disabled={promptsLoading}
                                      className={clsx(
                                        "focus-ring w-full border border-border bg-background px-3 py-2 text-sm text-text",
                                        layoutConfig.borderRadius.medium,
                                        promptsLoading && "opacity-60 cursor-not-allowed"
                                      )}
                                    />
                                  </div>
                                  <div className="space-y-1">
                                    <label className="text-xs font-semibold uppercase tracking-wide text-text/60">
                                      {t("settings.prompts.topP")}
                                    </label>
                                    <input
                                      type="number"
                                      step="0.05"
                                      min="0"
                                      max="1"
                                      value={llm.top_p === null || llm.top_p === undefined ? "" : llm.top_p}
                                      onChange={(event) =>
                                        handleLlmConfigChange(section.id, "top_p", event.target.value)
                                      }
                                      disabled={promptsLoading}
                                      className={clsx(
                                        "focus-ring w-full border border-border bg-background px-3 py-2 text-sm text-text",
                                        layoutConfig.borderRadius.medium,
                                        promptsLoading && "opacity-60 cursor-not-allowed"
                                      )}
                                    />
                                  </div>
                                </>
                              ) : null}
                              <div className="space-y-1">
                                <label className="text-xs font-semibold uppercase tracking-wide text-text/60">
                                  {t("settings.prompts.maxTokens")}
                                </label>
                                <input
                                  type="number"
                                  min="1"
                                  value={llm.max_output_tokens ?? ""}
                                  onChange={(event) => {
                                    const prev = llm.max_output_tokens;
                                    const raw = event.target.value;
                                    const parsed = Number(raw);
                                    if (Number.isNaN(parsed)) {
                                      handleLlmConfigChange(section.id, "max_output_tokens", "");
                                      return;
                                    }
                                    if (prev !== null && prev !== undefined && Math.abs(parsed - prev) <= 1) {
                                      const direction = parsed >= prev ? 1 : -1;
                                      const snapped =
                                        direction > 0
                                          ? Math.ceil((prev + 1) / 50) * 50
                                          : Math.max(0, Math.floor((prev - 1) / 50) * 50);
                                      handleLlmConfigChange(section.id, "max_output_tokens", String(snapped));
                                    } else {
                                      handleLlmConfigChange(section.id, "max_output_tokens", raw);
                                    }
                                  }}
                                  disabled={promptsLoading}
                                  className={clsx(
                                    "focus-ring w-full border border-border bg-background px-3 py-2 text-sm text-text",
                                    layoutConfig.borderRadius.medium,
                                    promptsLoading && "opacity-60 cursor-not-allowed"
                                  )}
                                />
                              </div>
                            </div>
                          </div>
                          <div className="flex justify-end pt-2">
                            <button
                              type="button"
                              disabled={promptsLoading || isSavingPrompts}
                              onClick={() => handleResetModule(section.id)}
                              className={clsx(
                                "text-xs font-semibold text-primary hover:text-primary/80 disabled:opacity-50"
                              )}
                            >
                              {t("buttons.reset")}
                            </button>
                          </div>
                        </Disclosure.Panel>
                      </div>
                    )}
                  </Disclosure>
                );
                })}
                {promptsError ? (
                  <div className="text-sm text-error">{promptsError}</div>
                ) : null}
                <div className="flex items-center justify-end gap-3 pt-2">
                  <button
                    type="button"
                    disabled={(!hasPromptChanges && !hasLlmChanges) || promptsLoading || isSavingPrompts}
                    onClick={handleSavePrompts}
                    className={clsx(
                      "focus-ring border border-primary bg-primary px-4 py-2 text-sm font-semibold text-on-primary disabled:opacity-50",
                      layoutConfig.borderRadius.small
                    )}
                  >
                    {isSavingPrompts ? t("buttons.saving") : t("buttons.save")}
                  </button>
                </div>
          </div>
        </div>
      </div>
    </div>
  );
};
