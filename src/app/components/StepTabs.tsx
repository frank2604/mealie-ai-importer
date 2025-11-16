import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import clsx from "clsx";
import type { StepDefinition, StepId } from "../../app/stepConfig";
import { layoutConfig } from "../../config/layout.config";

interface StepTabsProps {
  steps: StepDefinition[];
  currentStepId: StepId;
  onStepChange: (step: StepDefinition) => void;
  isStepDisabled?: (step: StepDefinition, index: number) => boolean;
}

export const StepTabs: React.FC<StepTabsProps> = ({ steps, currentStepId, onStepChange, isStepDisabled }) => {
  const { t } = useTranslation();

  const currentIndex = useMemo(() => steps.findIndex((step) => step.id === currentStepId), [steps, currentStepId]);

  const handleKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") {
      return;
    }

    event.preventDefault();

    const nextIndex =
      event.key === "ArrowRight" ? (index + 1) % steps.length : (index - 1 + steps.length) % steps.length;

    onStepChange(steps[nextIndex]);
  };

  return (
    <div
      role="tablist"
      aria-label={t("app.title")}
      className={clsx("grid w-full grid-cols-1", layoutConfig.spacing.element.gap, "sm:grid-cols-2 lg:grid-cols-4")}
    >
      {steps.map((step, index) => {
        const isActive = step.id === currentStepId;
        const disabled = isStepDisabled ? isStepDisabled(step, index) : false;
        const status = index < currentIndex ? "completed" : isActive ? "active" : "upcoming";
        return (
          <button
            key={step.id}
            role="tab"
            aria-selected={isActive}
            tabIndex={isActive || !disabled ? 0 : -1}
            onKeyDown={(event) => handleKeyDown(event, index)}
            onClick={() => {
              if (disabled) return;
              onStepChange(step);
            }}
            className={clsx(
              "focus-ring flex h-full w-full items-center gap-3 border px-4 py-3 text-left transition-colors",
              layoutConfig.borderRadius.medium,
              status === "completed" && "border-success/70 bg-success/10 text-success hover:border-success",
              status === "active" && "border-primary bg-primary/10 text-primary hover:border-primary",
              status === "upcoming" && "border-border bg-panel hover:border-primary/50 hover:text-primary",
              disabled && "cursor-not-allowed opacity-50 hover:border-border hover:text-text"
            )}
            disabled={disabled}
          >
            <span
              className={clsx(
                "flex h-8 w-8 items-center justify-center text-sm font-bold",
                layoutConfig.borderRadius.small,
                status === "completed" && "bg-success text-on-primary",
                status === "active" && "bg-primary text-on-primary",
                status === "upcoming" && "bg-secondary text-on-secondary"
              )}
            >
              {index + 1}
            </span>
            <span className="flex flex-col text-sm">
              <span className="font-semibold">{t(step.titleKey)}</span>
              <span className="text-xs text-text/70">{t(step.subtitleKey)}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
};
