import { ChangeEvent, useEffect, useMemo, useState } from "react";
import { Disclosure } from "@headlessui/react";
import { ChevronDownIcon } from "@heroicons/react/24/outline";
import clsx from "clsx";
import { useTranslation } from "react-i18next";
import { layoutConfig } from "../../config/layout.config";
import { useTheme } from "../../theme/useTheme";
import { availableLanguages } from "../../i18n/i18n";
import { fetchPrompts, savePrompts, type PromptLocaleConfig } from "../api/prompts";

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

  const promptModules = useMemo(
    () => [
      { id: "analysis", labelKey: "settings.prompts.analysis" },
      { id: "instructions", labelKey: "settings.prompts.instructions" },
      { id: "ingredients", labelKey: "settings.prompts.ingredients" },
      { id: "units", labelKey: "settings.prompts.units" },
      { id: "metadata", labelKey: "settings.prompts.metadata" }
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
        setHasPromptChanges(false);
      })
      .catch((error: Error) => {
        setPromptsError(error.message);
      })
      .finally(() => {
        setPromptsLoading(false);
      });
  }, []);

  const currentLocale = useMemo(() => (resolvedLanguage ?? "de").split("-")[0], [resolvedLanguage]);

  const currentPromptConfig = useMemo(() => {
    const localeData = promptData[currentLocale] || promptDefaults[currentLocale] || {};
    const fallback: PromptLocaleConfig = {};
    promptModules.forEach((module) => {
      const defaults = promptDefaults[currentLocale]?.[module.id] || { free: "", system: "" };
      const existing = localeData[module.id] || {};
      fallback[module.id] = {
        free: existing.free ?? defaults.free,
        system: existing.system ?? defaults.system
      };
    });
    return fallback;
  }, [currentLocale, promptData, promptDefaults, promptModules]);

  const handleThemeChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const value = event.target.value as "light" | "dark";
    setTheme(value);
  };

  const handleLanguageChange = (event: ChangeEvent<HTMLSelectElement>) => {
    void i18n.changeLanguage(event.target.value);
  };

  const updatePromptValue = (moduleId: string, field: "free" | "system", value: string) => {
    setPromptData((previous) => {
      const next = { ...previous };
      const localeEntry = { ...(next[currentLocale] || {}) };
      const defaults = promptDefaults[currentLocale]?.[moduleId] || { free: "", system: "" };
      const existing = localeEntry[moduleId] || defaults;
      const updatedEntry = {
        free: existing.free ?? defaults.free ?? "",
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
    const defaultFree = promptDefaults[currentLocale]?.[moduleId]?.free ?? "";
    const defaultSystem = promptDefaults[currentLocale]?.[moduleId]?.system ?? "";
    setPromptData((previous) => {
      const next = { ...previous };
      const localeEntry = { ...(next[currentLocale] || {}) };
      localeEntry[moduleId] = {
        free: defaultFree,
        system: defaultSystem
      };
      next[currentLocale] = localeEntry;
      return next;
    });
    setHasPromptChanges(true);
  };

  const handleResetLocale = () => {
    setPromptData((previous) => {
      const next = { ...previous };
      const localeDefaults = promptDefaults[currentLocale] || {};
      next[currentLocale] = Object.entries(localeDefaults).reduce<PromptLocaleConfig>((acc, [moduleId, config]) => {
        acc[moduleId] = { ...config };
        return acc;
      }, {});
      return next;
    });
    setHasPromptChanges(true);
  };

  const handleSavePrompts = async () => {
    setIsSavingPrompts(true);
    setPromptsError(null);
    try {
      const response = await savePrompts(promptData);
      setPromptData(response.prompts);
      setPromptDefaults(response.defaults);
      setHasPromptChanges(false);
    } catch (error) {
      setPromptsError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsSavingPrompts(false);
    }
  };

  return (
    <div className="w-full space-y-6">
      <header className={clsx("border border-border bg-panel p-6 shadow-sm", layoutConfig.borderRadius.large)}>
        <h1 className="text-2xl font-semibold text-primary">{t("settings.title")}</h1>
        <p className="mt-2 text-sm text-text/70">{t("settings.subtitle")}</p>
      </header>
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
      <div className="space-y-4">
        <div className={clsx("border border-border bg-panel shadow-sm", layoutConfig.borderRadius.large)}>
          <div className="flex w-full items-center justify-between gap-3 px-6 py-4 text-left">
            <div>
              <h2 className="text-lg font-semibold">{t("settings.prompts.title")}</h2>
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
                  const moduleConfig = currentPromptConfig[section.id] || {
                    free: "",
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
                              htmlFor={`${section.id}-prompt-free`}
                              className="text-xs font-semibold uppercase tracking-wide text-text/60"
                            >
                              {t("settings.prompts.freeLabel")}
                            </label>
                            <textarea
                              id={`${section.id}-prompt-free`}
                              rows={4}
                              disabled={promptsLoading}
                              value={moduleConfig.free}
                              onChange={(event) => updatePromptValue(section.id, "free", event.target.value)}
                              className={clsx(
                                "focus-ring w-full border border-border bg-background px-4 py-3 text-sm text-text/80",
                                layoutConfig.borderRadius.medium,
                                promptsLoading && "opacity-60 cursor-not-allowed"
                              )}
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
                              rows={4}
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
                    disabled={promptsLoading || isSavingPrompts}
                    onClick={handleResetLocale}
                    className={clsx(
                      "focus-ring border border-border px-4 py-2 text-sm font-semibold text-text hover:border-primary/60 hover:text-primary disabled:opacity-50",
                      layoutConfig.borderRadius.small
                    )}
                  >
                    {t("buttons.reset")}
                  </button>
                  <button
                    type="button"
                    disabled={!hasPromptChanges || promptsLoading || isSavingPrompts}
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
