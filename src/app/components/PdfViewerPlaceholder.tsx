import clsx from "clsx";
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  MagnifyingGlassMinusIcon,
  MagnifyingGlassPlusIcon
} from "@heroicons/react/24/outline";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { layoutConfig } from "../../config/layout.config";

interface PdfViewerPlaceholderProps {
  totalPages?: number;
  className?: string;
}

export const PdfViewerPlaceholder: React.FC<PdfViewerPlaceholderProps> = ({ totalPages = 8, className }) => {
  const { t } = useTranslation();
  const [currentPage, setCurrentPage] = useState(1);
  const [zoomLevel, setZoomLevel] = useState(100);

  const goPrev = () => setCurrentPage((page) => Math.max(1, page - 1));
  const goNext = () => setCurrentPage((page) => Math.min(totalPages, page + 1));
  const zoomOut = () => setZoomLevel((level) => Math.max(50, level - 10));
  const zoomIn = () => setZoomLevel((level) => Math.min(200, level + 10));

  return (
    <div className={clsx("flex h-full flex-col border border-border bg-panel", layoutConfig.borderRadius.large, className)}>
      <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
        <div>
          <h3 className="text-base font-semibold">{t("review.pdfPlaceholder.title")}</h3>
          <p className="text-xs text-text/70">{t("review.pdfPlaceholder.description")}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={zoomOut}
            className={clsx("focus-ring inline-flex items-center border border-border bg-background px-3 py-1 text-xs font-semibold hover:border-primary/60 hover:text-primary", layoutConfig.borderRadius.small)}
            aria-label={t("review.pdfPlaceholder.pager.zoomOut")}
          >
            <MagnifyingGlassMinusIcon className="h-4 w-4" aria-hidden="true" />
          </button>
          <span className="text-xs font-semibold text-text/80">{zoomLevel}%</span>
          <button
            type="button"
            onClick={zoomIn}
            className={clsx("focus-ring inline-flex items-center border border-border bg-background px-3 py-1 text-xs font-semibold hover:border-primary/60 hover:text-primary", layoutConfig.borderRadius.small)}
            aria-label={t("review.pdfPlaceholder.pager.zoomIn")}
          >
            <MagnifyingGlassPlusIcon className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>
      <div className="flex flex-1 flex-col gap-4 px-6 py-6 text-center text-sm text-text/70 min-h-0 overflow-hidden">
        <div className="flex flex-1 items-center justify-center min-h-0">
          <div className={clsx("aspect-[3/4] max-h-full w-full max-w-full border border-border bg-background/80 shadow-inner", layoutConfig.borderRadius.medium)} />
        </div>
        <p>{t("pdf.placeholder")}</p>
      </div>
      <div className="flex items-center justify-between gap-4 border-t border-border px-4 py-3 text-xs font-semibold">
        <button
          type="button"
          onClick={goPrev}
          className={clsx("focus-ring inline-flex items-center gap-1 border border-border bg-background px-3 py-1 hover:border-primary/60 hover:text-primary", layoutConfig.borderRadius.small)}
        >
          <ChevronLeftIcon className="h-4 w-4" aria-hidden="true" />
          {t("review.pdfPlaceholder.pager.prev")}
        </button>
        <span className={clsx("bg-secondary/80 px-3 py-1 text-on-secondary", layoutConfig.borderRadius.small)}>
          {t("review.pdfPlaceholder.pager.page", { current: currentPage, total: totalPages })}
        </span>
        <button
          type="button"
          onClick={goNext}
          className={clsx("focus-ring inline-flex items-center gap-1 border border-border bg-background px-3 py-1 hover:border-primary/60 hover:text-primary", layoutConfig.borderRadius.small)}
        >
          {t("review.pdfPlaceholder.pager.next")}
          <ChevronRightIcon className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
};
