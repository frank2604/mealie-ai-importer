import { ArrowUpTrayIcon } from "@heroicons/react/24/outline";
import clsx from "clsx";
import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { layoutConfig } from "../../config/layout.config";

interface DropZoneProps {
  onFilesSelected?: (files: FileList) => void;
}

export const DropZone: React.FC<DropZoneProps> = ({ onFilesSelected }) => {
  const { t } = useTranslation();
  const [isDragging, setIsDragging] = useState(false);

  const handleDragOver = (event: React.DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (event: React.DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (event: React.DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragging(false);
    if (event.dataTransfer.files && event.dataTransfer.files.length > 0) {
      onFilesSelected?.(event.dataTransfer.files);
    }
  };

  const handleChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      if (event.target.files) {
        onFilesSelected?.(event.target.files);
      }
    },
    [onFilesSelected]
  );

  return (
    <label
      className={clsx(
        "focus-ring flex flex-col items-center justify-center border-2 border-dashed px-6 py-16 text-center transition-colors",
        layoutConfig.borderRadius.large,
        isDragging ? "border-primary bg-primary/10" : "border-border bg-panel hover:border-primary/70"
      )}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <input type="file" accept="application/pdf" className="sr-only" onChange={handleChange} />
      <span className={clsx("flex h-16 w-16 items-center justify-center bg-primary/10 text-primary", layoutConfig.borderRadius.small)}>
        <ArrowUpTrayIcon className="h-8 w-8" aria-hidden="true" />
      </span>
      <span className="mt-6 text-xl font-semibold">{t("dropzone.title")}</span>
      <span className="mt-2 max-w-lg text-sm text-text/70">{t("dropzone.subtitle")}</span>
      <span className={clsx("mt-4 bg-secondary px-4 py-2 text-sm font-semibold text-on-secondary", layoutConfig.borderRadius.small)}>
        {t("dropzone.browse")}
      </span>
      <span className="mt-3 text-xs text-text/60">{t("dropzone.hint")}</span>
    </label>
  );
};
