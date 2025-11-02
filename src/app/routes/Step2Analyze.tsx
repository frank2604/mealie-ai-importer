import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { LogViewer, LogEntry } from "../components/LogViewer";
import clsx from "clsx";
import { layoutConfig } from "../../config/layout.config";

interface MetricItem {
  id: string;
  value: string;
  delta: string;
  status: "up" | "down" | "neutral";
}

export const Step2Analyze: React.FC = () => {
  const { t, i18n } = useTranslation();

  const logEntries = useMemo(() => {
    const entries = t("analyze.logEntries", { returnObjects: true }) as Array<{
      level: LogEntry["level"];
      message: string;
      time: string;
    }>;

    return entries.map((entry, index) => ({
      id: `log-${index}`,
      level: entry.level,
      message: entry.message,
      timestamp: entry.time
    }));
  }, [t, i18n.resolvedLanguage]);

  const metrics: MetricItem[] = [
    { id: "ingredients", value: "18", delta: "+3", status: "up" },
    { id: "units", value: "7", delta: "+1", status: "up" },
    { id: "confidence", value: "86%", delta: "+4%", status: "neutral" }
  ];

  return (
    <div className="flex-1 overflow-y-auto">
      <div className={clsx("grid xl:grid-cols-[2fr,1fr]", layoutConfig.spacing.layout.columns)}>
        <div className={clsx("flex flex-col", layoutConfig.spacing.layout.columns)}>
          <div className={clsx("grid sm:grid-cols-3", layoutConfig.spacing.section.gap)}>
            {metrics.map((item) => (
              <div key={item.id} className={clsx("border border-border bg-panel shadow-sm", layoutConfig.spacing.layout.container.x, layoutConfig.spacing.layout.container.y, layoutConfig.borderRadius.large)}>
                <div className="text-xs font-semibold uppercase tracking-wide text-text/60">
                  {t(`analyze.metrics.${item.id}.title`)}
                </div>
                <div className={clsx("mt-2 flex items-baseline", layoutConfig.spacing.item.gap)}>
                  <span className="text-3xl font-semibold text-primary">{item.value}</span>
                  <span
                    className={
                      item.status === "down"
                        ? "text-sm font-semibold text-error"
                        : item.status === "up"
                          ? "text-sm font-semibold text-success"
                          : "text-sm font-semibold text-text/60"
                    }
                  >
                    {item.delta}
                  </span>
                </div>
                <p className="mt-1 text-xs text-text/70">{t(`analyze.metrics.${item.id}.description`)}</p>
              </div>
            ))}
          </div>
          <LogViewer logs={logEntries} titleKey="analyze.logTitle" summaryKey="analyze.summary" />
        </div>
        <aside className={clsx("flex h-full flex-col justify-between border border-border bg-panel shadow-sm", layoutConfig.spacing.section.gap, layoutConfig.spacing.layout.container.x, layoutConfig.spacing.layout.container.y, layoutConfig.borderRadius.large)}>
          <section>
            <h3 className="text-lg font-semibold text-primary">{t("steps.analyze.title")}</h3>
            <p className="mt-2 text-sm text-text/70">{t("steps.analyze.subtitle")}</p>
          </section>
          <section className={clsx("text-sm text-text/80", layoutConfig.spacing.element.vertical)}>
            {(t("analyze.checklist", { returnObjects: true }) as string[]).map((item) => (
              <div key={item} className={clsx("border border-border/70 bg-background/80", layoutConfig.spacing.element.padding.x, layoutConfig.spacing.element.padding.y, layoutConfig.borderRadius.medium)}>
                • {item}
              </div>
            ))}
          </section>
          <section className={clsx("border border-border bg-background/60 text-xs text-text/60", layoutConfig.spacing.element.padding.x, layoutConfig.spacing.element.padding.y, layoutConfig.borderRadius.medium)}>
            {t("notifications.comingSoon")}
          </section>
        </aside>
      </div>
    </div>
  );
};
