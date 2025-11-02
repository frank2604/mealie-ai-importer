import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { ArrowDownTrayIcon } from "@heroicons/react/24/outline";
import { LogViewer, LogEntry } from "../components/LogViewer";
import clsx from "clsx";
import { layoutConfig } from "../../config/layout.config";

interface SummaryItem {
  title: string;
  value: string;
  description: string;
}

export const Step4Transfer: React.FC = () => {
  const { t, i18n } = useTranslation();

  const logEntries = useMemo(() => {
    const source = t("transfer.logEntries", { returnObjects: true }) as Array<{
      level: LogEntry["level"];
      message: string;
      time: string;
    }>;
    return source.map((entry, index) => ({
      id: `transfer-${index}`,
      level: entry.level,
      message: entry.message,
      timestamp: entry.time
    }));
  }, [t, i18n.resolvedLanguage]);

  const summaryItems = useMemo(() => {
    const source = t("transfer.summaryItems", { returnObjects: true }) as SummaryItem[];
    return source;
  }, [t, i18n.resolvedLanguage]);

  return (
    <div className="flex-1 overflow-y-auto">
      <div className={clsx("grid xl:grid-cols-[2fr,1fr]", layoutConfig.spacing.layout.columns)}>
        <div className={clsx("flex flex-col", layoutConfig.spacing.layout.columns)}>
          <LogViewer logs={logEntries} titleKey="transfer.logTitle" summaryKey="transfer.summary" />
        </div>
        <aside className={clsx("flex h-full flex-col border border-border bg-panel shadow-sm", layoutConfig.spacing.section.gap, layoutConfig.spacing.layout.container.x, layoutConfig.spacing.layout.container.y, layoutConfig.borderRadius.large)}>
          <header>
            <h3 className="text-lg font-semibold">{t("steps.transfer.title")}</h3>
            <p className="mt-2 text-sm text-text/70">{t("steps.transfer.subtitle")}</p>
          </header>
          <div className={layoutConfig.spacing.element.vertical}>
            {summaryItems.map((item) => (
              <div key={item.title} className={clsx("border border-border/70 bg-background/80", layoutConfig.spacing.element.padding.x, layoutConfig.spacing.element.padding.y, layoutConfig.borderRadius.medium)}>
                <div className="text-xs font-semibold uppercase tracking-wide text-text/60">{item.title}</div>
                <div className={clsx("mt-1 flex items-baseline", layoutConfig.spacing.item.gap)}>
                  <span className="text-2xl font-semibold text-primary">{item.value}</span>
                  <span className="text-xs text-text/60">{item.description}</span>
                </div>
              </div>
            ))}
          </div>
          <button
            type="button"
            className={clsx("focus-ring mt-auto inline-flex items-center justify-center border border-border bg-panel text-sm font-semibold text-text hover:border-primary/60 hover:text-primary", layoutConfig.spacing.item.gap, layoutConfig.spacing.button.default.x, layoutConfig.spacing.button.default.y, layoutConfig.borderRadius.small)}
          >
            <ArrowDownTrayIcon className="h-4 w-4" aria-hidden="true" />
            {t("transfer.archive")}
          </button>
        </aside>
      </div>
    </div>
  );
};
