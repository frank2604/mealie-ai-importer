import { useTranslation } from "react-i18next";
import { DropZone } from "../components/DropZone";
import clsx from "clsx";
import { layoutConfig } from "../../config/layout.config";

export const Step1Select: React.FC = () => {
  const { t } = useTranslation();
  const hints = t("select.hints", { returnObjects: true }) as string[];

  return (
    <div className="flex-1 overflow-y-auto">
      <div className={clsx("grid lg:grid-cols-[3fr,2fr]", layoutConfig.spacing.layout.columns)}>
        <div className={clsx("border border-border bg-panel shadow-sm", layoutConfig.spacing.element.vertical, layoutConfig.spacing.layout.container.x, layoutConfig.spacing.layout.container.y, layoutConfig.borderRadius.large)}>
          <h2 className="text-2xl font-semibold">{t("steps.select.title")}</h2>
          <p className="text-sm text-text/70">{t("steps.select.subtitle")}</p>
          <ul className={clsx("text-sm text-text/80", layoutConfig.spacing.element.vertical)}>
            {hints.map((hint) => (
              <li key={hint} className={clsx("border border-border/70 bg-background/80", layoutConfig.spacing.element.padding.x, layoutConfig.spacing.element.padding.y, layoutConfig.borderRadius.medium)}>
                {hint}
              </li>
            ))}
          </ul>
        </div>
        <DropZone />
      </div>
    </div>
  );
};
