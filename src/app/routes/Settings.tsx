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
                </div>
                <ChevronDownIcon
                  className={clsx("h-5 w-5 transition-transform", open ? "rotate-180 text-primary" : "text-text/60")}
                />
              </Disclosure.Button>
              <Disclosure.Panel className="space-y-4 px-6 pb-6">
                {[
                  {
                    id: "analysis",
                    title: t("settings.prompts.analysis"),
                    freeValue: t("settings.prompts.analysisPlaceholder"),
                    systemLabel: t("settings.prompts.analysisSystem"),
                    systemValue: t("settings.prompts.analysisSystemPlaceholder")
                  },
                  {
                    id: "ingredients",
                    title: t("settings.prompts.ingredients"),
                    freeValue: t("settings.prompts.ingredientsPlaceholder"),
                    systemLabel: t("settings.prompts.ingredientsSystem"),
                    systemValue: t("settings.prompts.ingredientsSystemPlaceholder")
                  },
                  {
                    id: "units",
                    title: t("settings.prompts.units"),
                    freeValue: t("settings.prompts.unitsPlaceholder"),
                    systemLabel: t("settings.prompts.unitsSystem"),
                    systemValue: t("settings.prompts.unitsSystemPlaceholder")
                  },
                  {
                    id: "metadata",
                    title: t("settings.prompts.metadata"),
                    freeValue: t("settings.prompts.metadataPlaceholder"),
                    systemLabel: t("settings.prompts.metadataSystem"),
                    systemValue: t("settings.prompts.metadataSystemPlaceholder")
                  }
                ].map((section) => (
                  <Disclosure key={section.id}>
                    {({ open: moduleOpen }) => (
                      <div
                        className={clsx(
                          "border border-border bg-background/80 shadow-sm",
                          layoutConfig.borderRadius.medium
                        )}
                      >
                        <Disclosure.Button className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left">
                          <span className="text-sm font-semibold text-text">{section.title}</span>
                          <ChevronDownIcon
                            className={clsx(
                              "h-4 w-4 transition-transform",
                              moduleOpen ? "rotate-180 text-primary" : "text-text/60"
                            )}
                          />
                        </Disclosure.Button>
                        <Disclosure.Panel className={clsx("space-y-3 border-t border-border/60 px-4 py-4")}>
                          <div className="space-y-2">
                            <label htmlFor={`${section.id}-prompt-free`} className="text-xs font-semibold uppercase tracking-wide text-text/60">
                              {t("settings.prompts.freeLabel")}
                            </label>
                            <textarea
                              id={`${section.id}-prompt-free`}
                              rows={4}
                              readOnly
                              value={section.freeValue}
                              className={clsx(
                                "focus-ring w-full border border-border bg-background px-4 py-3 text-sm text-text/80",
                                layoutConfig.borderRadius.medium
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
                              readOnly
                              value={section.systemValue}
                              className={clsx(
                                "focus-ring w-full border border-dashed border-border bg-background/70 px-4 py-3 text-xs text-text/70",
                                layoutConfig.borderRadius.medium
                              )}
                            />
                          </div>
                        </Disclosure.Panel>
                      </div>
                    )}
                  </Disclosure>
                ))}
              </Disclosure.Panel>
            </div>
          )}
        </Disclosure>
      </div>
    </div>
  );
};
