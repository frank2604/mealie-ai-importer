import { Disclosure } from "@headlessui/react";
import { ChevronDownIcon } from "@heroicons/react/24/outline";
import clsx from "clsx";
import { useTranslation } from "react-i18next";
import { ThemePreview } from "../components/ThemePreview";
import { layoutConfig } from "../../config/layout.config";

export const Settings: React.FC = () => {
  const { t } = useTranslation();

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header className={clsx("border border-border bg-panel p-6 shadow-sm", layoutConfig.borderRadius.large)}>
        <h1 className="text-2xl font-semibold text-primary">{t("settings.title")}</h1>
        <p className="mt-2 text-sm text-text/70">{t("settings.subtitle")}</p>
      </header>
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
