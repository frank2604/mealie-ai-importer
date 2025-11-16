import clsx from "clsx";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { layoutConfig } from "../../config/layout.config";

export type LogLevel = "INFO" | "OK" | "WARN" | "ERROR" | "AI";

export interface LogEntry {
  id: string;
  level: LogLevel;
  message: string;
  timestamp: string;
}

interface LogViewerProps {
  logs: LogEntry[];
  titleKey: string;
  summaryKey?: string;
  className?: string;
}

// Only expose filters for levels that can currently occur in the backend logs.
const levelOrder: LogLevel[] = ["INFO", "OK", "WARN", "ERROR"];

const levelColor: Record<LogLevel, string> = {
  INFO: "bg-info/10 text-info border-info/40",
  OK: "bg-success/10 text-success border-success/40",
  WARN: "bg-warning/10 text-warning border-warning/40",
  ERROR: "bg-error/10 text-error border-error/40",
  AI: "bg-accent/10 text-accent border-accent/40"
};

export const LogViewer: React.FC<LogViewerProps> = ({ logs, titleKey, summaryKey, className }) => {
  const { t } = useTranslation();
  const [activeFilter, setActiveFilter] = useState<LogLevel | "ALL">("ALL");
  const listRef = useRef<HTMLOListElement | null>(null);
  const stickToBottomRef = useRef(true);

  const filteredLogs = useMemo(() => {
    if (activeFilter === "ALL") {
      return logs;
    }
    return logs.filter((entry) => entry.level === activeFilter);
  }, [activeFilter, logs]);

  useEffect(() => {
    const container = listRef.current;
    if (!container) return;
    const handleScroll = () => {
      const isNearBottom = container.scrollHeight - container.clientHeight - container.scrollTop < 40;
      stickToBottomRef.current = isNearBottom;
    };
    container.addEventListener("scroll", handleScroll);
    return () => {
      container.removeEventListener("scroll", handleScroll);
    };
  }, []);

  useEffect(() => {
    if (activeFilter !== "ALL") {
      return;
    }
    const container = listRef.current;
    if (!container) {
      return;
    }
    if (stickToBottomRef.current) {
      container.scrollTop = container.scrollHeight;
    }
  }, [activeFilter, logs]);

  return (
    <div
      className={clsx(
        "flex h-full min-h-0 flex-col border border-border bg-panel overflow-hidden",
        layoutConfig.borderRadius.large,
        className
      )}
    >
      <div
        className={clsx(
          "sticky top-0 z-10 flex flex-wrap items-center justify-between border-b border-border bg-panel",
          layoutConfig.spacing.element.gap,
          layoutConfig.spacing.section.padding.x,
          layoutConfig.spacing.section.padding.y
        )}
      >
        <div>
          <h3 className="text-lg font-semibold">{t(titleKey)}</h3>
        </div>
        <div className={clsx("flex items-center", layoutConfig.spacing.item.gap)}>
          <button
            type="button"
            onClick={() => setActiveFilter("ALL")}
            className={clsx(
              "focus-ring border px-3 py-1 text-xs font-semibold",
              layoutConfig.borderRadius.small,
              activeFilter === "ALL"
                ? "border-primary bg-primary text-on-primary"
                : "border-border bg-background hover:border-primary/60 hover:text-primary"
            )}
          >
            {t("logViewer.filters.all")}
          </button>
          {levelOrder.map((level) => (
            <button
              key={level}
              type="button"
              onClick={() => setActiveFilter(level)}
              className={clsx(
                "focus-ring border px-3 py-1 text-xs font-semibold",
                layoutConfig.borderRadius.small,
                activeFilter === level
                  ? levelColor[level]
                  : "border-border bg-background hover:border-primary/60 hover:text-primary"
              )}
            >
              {t(`logViewer.filters.${level.toLowerCase()}`)}
            </button>
          ))}
        </div>
      </div>
      <ol
        ref={listRef}
        className={clsx("flex-1 overflow-y-auto", layoutConfig.spacing.item.vertical, layoutConfig.spacing.section.padding.x, layoutConfig.spacing.section.padding.y)}
        aria-label={t("logViewer.ariaLabel")}
      >
        {filteredLogs.map((entry) => (
          <li
            key={entry.id}
            className={clsx("flex items-start border border-border/60 bg-background/60 text-sm shadow-sm", layoutConfig.spacing.element.gap, layoutConfig.spacing.element.padding.x, layoutConfig.spacing.element.padding.y, layoutConfig.borderRadius.medium)}
          >
            <span className={clsx("mt-0.5 inline-flex items-center border text-[11px] font-bold uppercase", layoutConfig.spacing.item.gap, layoutConfig.spacing.button.badge.x, layoutConfig.spacing.button.badge.y, layoutConfig.borderRadius.small, levelColor[entry.level])}>
              {entry.level}
            </span>
            <div className="flex flex-1 flex-col">
              <p className="font-medium">{entry.message}</p>
              <span className="text-xs text-text/60">{entry.timestamp}</span>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
};
