import { useCallback, useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { Document, Page, pdfjs } from "react-pdf";
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  MagnifyingGlassMinusIcon,
  MagnifyingGlassPlusIcon
} from "@heroicons/react/24/outline";
import workerSrc from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { useTranslation } from "react-i18next";
import { layoutConfig } from "../../config/layout.config";

pdfjs.GlobalWorkerOptions.workerSrc = workerSrc;

interface PdfViewerProps {
  src?: string | null;
  className?: string;
}

const MIN_ZOOM = 0.5;
const MAX_ZOOM = 2;
const ZOOM_STEP = 0.1;

export const PdfViewer: React.FC<PdfViewerProps> = ({ src, className }) => {
  const { t } = useTranslation();
  const [pageNumber, setPageNumber] = useState(1);
  const [numPages, setNumPages] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPageNumber(1);
    setError(null);
    setNumPages(0);
    if (src) {
      setIsLoading(true);
    } else {
      setIsLoading(false);
    }
  }, [src]);

  const handleDocumentLoad = useCallback(
    ({ numPages }: { numPages: number }) => {
      setNumPages(numPages);
      setIsLoading(false);
    },
    []
  );

  const handleDocumentError = useCallback((event: Error) => {
    setError(event.message);
    setIsLoading(false);
  }, []);

  const goPrevious = () => setPageNumber((current) => Math.max(1, current - 1));
  const goNext = () => setPageNumber((current) => Math.min(numPages || 1, current + 1));
  const zoomIn = () => setZoom((value) => Math.min(MAX_ZOOM, +(value + ZOOM_STEP).toFixed(2)));
  const zoomOut = () => setZoom((value) => Math.max(MIN_ZOOM, +(value - ZOOM_STEP).toFixed(2)));
  const resetZoom = () => setZoom(1);

  const fileSource = useMemo(() => {
    if (!src) {
      return null;
    }
    return { url: src, withCredentials: true };
  }, [src]);

  const headerStatus = !src ? t("review.pdfViewer.noPdf") : isLoading ? t("review.pdfViewer.loading") : null;

  return (
    <div className={clsx("flex h-full flex-col border border-border bg-panel", layoutConfig.borderRadius.large, className)}>
      <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
        <div>
          <h3 className="text-base font-semibold">{t("review.pdfViewer.title")}</h3>
          {headerStatus ? <p className="text-xs text-text/70">{headerStatus}</p> : null}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={zoomOut}
            disabled={!src || zoom <= MIN_ZOOM}
            className={clsx(
              "focus-ring inline-flex items-center border border-border bg-background px-3 py-1 text-xs font-semibold hover:border-primary/60 hover:text-primary disabled:cursor-not-allowed disabled:opacity-50",
              layoutConfig.borderRadius.small
            )}
            aria-label={t("review.pdfViewer.zoomOut")}
          >
            <MagnifyingGlassMinusIcon className="h-4 w-4" aria-hidden="true" />
          </button>
          <span className="text-xs font-semibold text-text/80">{Math.round(zoom * 100)}%</span>
          <button
            type="button"
            onClick={zoomIn}
            disabled={!src || zoom >= MAX_ZOOM}
            className={clsx(
              "focus-ring inline-flex items-center border border-border bg-background px-3 py-1 text-xs font-semibold hover:border-primary/60 hover:text-primary disabled:cursor-not-allowed disabled:opacity-50",
              layoutConfig.borderRadius.small
            )}
            aria-label={t("review.pdfViewer.zoomIn")}
          >
            <MagnifyingGlassPlusIcon className="h-4 w-4" aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={resetZoom}
            disabled={!src || zoom === 1}
            className={clsx(
              "focus-ring inline-flex items-center border border-border bg-background px-3 py-1 text-xs font-semibold hover:border-primary/60 hover:text-primary disabled:cursor-not-allowed disabled:opacity-50",
              layoutConfig.borderRadius.small
            )}
          >
            {t("review.pdfViewer.resetZoom")}
          </button>
        </div>
      </div>
      <div className="flex-1 min-h-0 overflow-hidden bg-background/60">
        {!src ? (
          <div className="flex h-full items-center justify-center px-6 text-center text-sm text-text/70">{t("review.pdfViewer.noPdf")}</div>
        ) : error ? (
          <div className="flex h-full items-center justify-center px-6 text-center text-sm text-error">
            {t("review.pdfViewer.error", { message: error })}
          </div>
        ) : (
          <div className="h-full overflow-auto px-4 py-4">
            <div className="flex justify-center">
              <Document
                file={fileSource}
                onLoadSuccess={handleDocumentLoad}
                onLoadError={handleDocumentError}
                loading={<div className="text-sm text-text/70">{t("review.pdfViewer.loading")}</div>}
                error={<div className="text-sm text-error">{t("review.pdfViewer.error", { message: "" })}</div>}
              >
                <Page
                  pageNumber={pageNumber}
                  scale={zoom}
                  renderTextLayer={false}
                  renderAnnotationLayer={false}
                  className={clsx("mx-auto shadow-sm", layoutConfig.borderRadius.medium)}
                />
              </Document>
            </div>
          </div>
        )}
      </div>
      <div className="flex items-center justify-between gap-4 border-t border-border px-4 py-3 text-xs font-semibold">
        <button
          type="button"
          onClick={goPrevious}
          disabled={!src || pageNumber <= 1}
          className={clsx(
            "focus-ring inline-flex items-center gap-1 border border-border bg-background px-3 py-1 hover:border-primary/60 hover:text-primary disabled:cursor-not-allowed disabled:opacity-50",
            layoutConfig.borderRadius.small
          )}
        >
          <ChevronLeftIcon className="h-4 w-4" aria-hidden="true" />
          {t("review.pdfViewer.prev")}
        </button>
        <span className={clsx("bg-secondary/80 px-3 py-1 text-on-secondary", layoutConfig.borderRadius.small)}>
          {numPages > 0
            ? t("review.pdfViewer.pageIndicator", { current: pageNumber, total: numPages })
            : t("review.pdfViewer.pageIndicator", { current: 0, total: 0 })}
        </span>
        <button
          type="button"
          onClick={goNext}
          disabled={!src || pageNumber >= numPages}
          className={clsx(
            "focus-ring inline-flex items-center gap-1 border border-border bg-background px-3 py-1 hover:border-primary/60 hover:text-primary disabled:cursor-not-allowed disabled:opacity-50",
            layoutConfig.borderRadius.small
          )}
        >
          {t("review.pdfViewer.next")}
          <ChevronRightIcon className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
