import { useTheme } from "../../theme/useTheme";
import { useTranslation } from "react-i18next";
import clsx from "clsx";
import { layoutConfig } from "../../config/layout.config";

export const ThemePreview: React.FC = () => {
  const { theme } = useTheme();
  const { t } = useTranslation();
  const currentThemeLabel = t(`theme.${theme}`);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-sm font-medium text-text/70">
        <span>{t("settings.theme.current")}</span>
        <span className={clsx("bg-primary px-3 py-1 text-xs font-semibold text-on-primary", layoutConfig.borderRadius.small)}>
          {currentThemeLabel}
        </span>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className={clsx("border border-border bg-panel p-4 shadow-sm", layoutConfig.borderRadius.medium)}>
          <div className="text-xs font-semibold uppercase tracking-wide text-text/60">Buttons</div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className={clsx("bg-primary px-3 py-1 text-xs font-semibold text-on-primary", layoutConfig.borderRadius.small)}>Primary</span>
            <span className={clsx("border border-border px-3 py-1 text-xs font-semibold text-text", layoutConfig.borderRadius.small)}>Secondary</span>
            <span className={clsx("bg-accent px-3 py-1 text-xs font-semibold text-on-primary", layoutConfig.borderRadius.small)}>Accent</span>
          </div>
        </div>
        <div className={clsx("border border-border bg-panel p-4 shadow-sm", layoutConfig.borderRadius.medium)}>
          <div className="text-xs font-semibold uppercase tracking-wide text-text/60">Status</div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className={clsx("bg-success/20 px-3 py-1 text-xs font-semibold text-success", layoutConfig.borderRadius.small)}>Success</span>
            <span className={clsx("bg-warning/20 px-3 py-1 text-xs font-semibold text-warning", layoutConfig.borderRadius.small)}>Warning</span>
            <span className={clsx("bg-error/20 px-3 py-1 text-xs font-semibold text-error", layoutConfig.borderRadius.small)}>Error</span>
            <span className={clsx("bg-info/20 px-3 py-1 text-xs font-semibold text-info", layoutConfig.borderRadius.small)}>Info</span>
          </div>
        </div>
      </div>
      <div className={clsx("border border-border bg-panel p-4 shadow-sm", layoutConfig.borderRadius.medium)}>
        <div className="text-xs font-semibold uppercase tracking-wide text-text/60">Preview</div>
        <div className="mt-3 space-y-2 text-sm">
          <div className={clsx("border border-border bg-background px-4 py-3", layoutConfig.borderRadius.medium)}>
            <div className="text-xs font-semibold text-text/70">Card header</div>
            <div className="mt-1 text-text/80">AI-basierte Vorschläge erscheinen hier.</div>
          </div>
          <div className={clsx("flex items-center justify-between border border-border px-4 py-3", layoutConfig.borderRadius.medium)}>
            <span>Status Badge</span>
            <span className={clsx("bg-primary px-3 py-1 text-xs font-semibold text-on-primary", layoutConfig.borderRadius.small)}>Active</span>
          </div>
        </div>
      </div>
    </div>
  );
};
