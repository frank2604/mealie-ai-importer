import type { ChangeEvent } from "react";
import { Disclosure } from "@headlessui/react";
import { ChevronDownIcon } from "@heroicons/react/24/outline";
import clsx from "clsx";
import { useTranslation } from "react-i18next";
import { ThemePreview } from "../components/ThemePreview";
import { layoutConfig } from "../../config/layout.config";
import { useTheme } from "../../theme/useTheme";
import { availableLanguages } from "../../i18n/i18n";

export const Settings: React.FC = () => {
  const { t, i18n } = useTranslation();
  const { theme, setTheme } = useTheme();
  const resolvedLanguage = i18n.resolvedLanguage ?? i18n.language;
  const activeLanguage = (availableLanguages.includes(resolvedLanguage as (typeof availableLanguages)[number])
    ? resolvedLanguage
    : availableLanguages[0]) as (typeof availableLanguages)[number];

  const handleThemeChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const value = event.target.value as "light" | "dark";
    setTheme(value);
  };

  const handleLanguageChange = (event: ChangeEvent<HTMLSelectElement>) => {
    void i18n.changeLanguage(event.target.value);
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6">
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
        <Disclosure defaultOpen>
          {({ open }) => (
            <div className={clsx("border border-border bg-panel shadow-sm", layoutConfig.borderRadius.large)}>
              <Disclosure.Button className="flex w-full items-center justify-between gap-3 px-6 py-4 text-left">
                <div>
                  <h2 className="text-lg font-semibold">{t("settings.theme.title")}</h2>
                  <p className="text-sm text-text/70">{t("settings.theme.description")}</p>
                </div>
                <ChevronDownIcon
                  className={clsx("h-5 w-5 transition-transform", open ? "rotate-180 text-primary" : "text-text/60")}
                />
              </Disclosure.Button>
              <Disclosure.Panel className="px-6 pb-6">
                <ThemePreview />
              </Disclosure.Panel>
            </div>
          )}
        </Disclosure>
        <Disclosure>
          {({ open }) => (
            <div className={clsx("border border-border bg-panel shadow-sm", layoutConfig.borderRadius.large)}>
              <Disclosure.Button className="flex w-full items-center justify-between gap-3 px-6 py-4 text-left">
                <div>
                  <h2 className="text-lg font-semibold">{t("settings.prompts.title")}</h2>
                  <p className="text-sm text-text/70">{t("settings.prompts.description")}</p>
                </div>
                <ChevronDownIcon
                  className={clsx("h-5 w-5 transition-transform", open ? "rotate-180 text-primary" : "text-text/60")}
                />
              </Disclosure.Button>
              <Disclosure.Panel className="space-y-4 px-6 pb-6">
                <div>
                  <label htmlFor="analysis-prompt" className="text-sm font-semibold text-text">
                    {t("settings.prompts.analysis")}
                  </label>
                  <textarea
                    id="analysis-prompt"
                    rows={4}
                    readOnly
                    value={t("settings.prompts.analysisPlaceholder")}
                    className={clsx("focus-ring mt-2 w-full border border-border bg-background px-4 py-3 text-sm text-text/80", layoutConfig.borderRadius.medium)}
                  />
                </div>
                <div>
                  <label htmlFor="suggestion-prompt" className="text-sm font-semibold text-text">
                    {t("settings.prompts.suggestion")}
                  </label>
                  <textarea
                    id="suggestion-prompt"
                    rows={4}
                    readOnly
                    value={t("settings.prompts.suggestionPlaceholder")}
                    className={clsx("focus-ring mt-2 w-full border border-border bg-background px-4 py-3 text-sm text-text/80", layoutConfig.borderRadius.medium)}
                  />
                </div>
                <div className={clsx("border border-accent/40 bg-accent/10 px-4 py-3 text-xs text-accent", layoutConfig.borderRadius.medium)}>
                  {t("notifications.comingSoon")}
                </div>
              </Disclosure.Panel>
            </div>
          )}
        </Disclosure>
      </div>
    </div>
  );
};
