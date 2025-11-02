import { ArrowLeftIcon, ArrowRightIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { useTranslation } from "react-i18next";
import clsx from "clsx";
import { layoutConfig } from "../../config/layout.config";

interface StickyFooterProps {
  isFirstStep: boolean;
  isLastStep: boolean;
  onBack: () => void;
  onNext: () => void;
  onCancel: () => void;
}

export const StickyFooter: React.FC<StickyFooterProps> = ({ isFirstStep, isLastStep, onBack, onNext, onCancel }) => {
  const { t } = useTranslation();

  return (
    <footer className="border-t border-border bg-panel/95 backdrop-blur">
      <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8">
        <button
          type="button"
          onClick={onCancel}
          className={clsx("focus-ring inline-flex items-center gap-2 border border-border px-4 py-2 text-sm font-semibold text-text hover:border-error/60 hover:text-error", layoutConfig.borderRadius.small)}
        >
          <XMarkIcon className="h-4 w-4" aria-hidden="true" />
          {t("buttons.cancel")}
        </button>
        <div className="flex flex-1 items-center justify-end gap-3">
          <button
            type="button"
            onClick={onBack}
            disabled={isFirstStep}
            className={clsx(
              "focus-ring inline-flex items-center gap-2 border border-border px-4 py-2 text-sm font-semibold",
              layoutConfig.borderRadius.small,
              isFirstStep
                ? "cursor-not-allowed opacity-50"
                : "text-text hover:border-primary/60 hover:text-primary"
            )}
          >
            <ArrowLeftIcon className="h-4 w-4" aria-hidden="true" />
            {t("buttons.back")}
          </button>
          <button
            type="button"
            onClick={onNext}
            className={clsx("focus-ring inline-flex items-center gap-2 bg-primary px-5 py-2 text-sm font-semibold text-on-primary hover:bg-primary/90", layoutConfig.borderRadius.small)}
          >
            {isLastStep ? t("buttons.finish") : t("buttons.next")}
            <ArrowRightIcon className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>
    </footer>
  );
};
