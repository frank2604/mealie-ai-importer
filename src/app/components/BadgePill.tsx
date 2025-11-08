import React, { useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import clsx from "clsx";
import {
  AdjustmentsHorizontalIcon,
  ExclamationTriangleIcon,
  FingerPrintIcon,
  MinusSmallIcon,
  PencilIcon,
  PlusSmallIcon,
  SparklesIcon
} from "@heroicons/react/24/outline";
import { badgeConfig, BadgeId, BadgeIconName } from "../../config/badges.config";
import { layoutConfig } from "../../config/layout.config";

const badgeIconMap: Record<BadgeIconName, React.ComponentType<React.SVGProps<SVGSVGElement>>> = {
  sparkles: SparklesIcon,
  "finger-print": FingerPrintIcon,
  adjustments: AdjustmentsHorizontalIcon,
  plus: PlusSmallIcon,
  pencil: PencilIcon,
  minus: MinusSmallIcon,
  warning: ExclamationTriangleIcon
};

const FALLBACK_CLASS = clsx(
  "inline-flex items-center border px-2 py-0.5 text-[11px] font-semibold uppercase",
  layoutConfig.borderRadius.small,
  "text-info border-info/40 bg-info/10"
);

const isBadgeId = (value: unknown): value is BadgeId => {
  if (typeof value !== "string") {
    return false;
  }
  return Object.prototype.hasOwnProperty.call(badgeConfig, value);
};

const resolvedLabelKey = (badgeId: BadgeId | null, fallbackStatus: string): string => {
  if (badgeId && badgeId.startsWith("found")) {
    return "review.status.found";
  }
  if (badgeId === "new" || badgeId === "manual" || badgeId === "none" || badgeId === "error") {
    return `review.status.${badgeId}`;
  }
  return `review.status.${fallbackStatus}`;
};

export interface BadgePillProps {
  badgeId?: string | null;
  fallbackStatus?: string;
}

export const BadgePill: React.FC<BadgePillProps> = ({ badgeId, fallbackStatus = "info" }) => {
  const { t } = useTranslation();
  const [isTooltipVisible, setIsTooltipVisible] = useState(false);
  const delayRef = useRef<number | null>(null);

  const handlePointerEnter = () => {
    if (delayRef.current) {
      window.clearTimeout(delayRef.current);
    }
    delayRef.current = window.setTimeout(() => {
      setIsTooltipVisible(true);
    }, 300);
  };

  const handlePointerLeave = () => {
    if (delayRef.current) {
      window.clearTimeout(delayRef.current);
      delayRef.current = null;
    }
    setIsTooltipVisible(false);
  };

  const normalizedId = useMemo(() => {
    if (!badgeId) {
      return null;
    }
    if (isBadgeId(badgeId)) {
      return badgeId;
    }
    if (badgeId === "found") {
      return "found_word";
    }
    return null;
  }, [badgeId]);

  const config = normalizedId ? badgeConfig[normalizedId] : undefined;
  const className = config?.className ?? FALLBACK_CLASS;
  const labelKey = resolvedLabelKey(normalizedId, fallbackStatus);
  const IconComponent = config ? badgeIconMap[config.icon] : null;
  const tooltip = config ? t(config.tooltipKey) : undefined;
  const label = t(labelKey);

  return (
    <span className="group relative inline-flex">
      <span
        className={className}
        aria-label={tooltip ?? label}
        onMouseEnter={handlePointerEnter}
        onMouseLeave={handlePointerLeave}
        onFocus={handlePointerEnter}
        onBlur={handlePointerLeave}
      >
        {IconComponent ? <IconComponent className="mr-1 h-3 w-3" aria-hidden="true" /> : null}
        {label}
      </span>
      {tooltip && isTooltipVisible ? (
        <span
          className={clsx(
            "pointer-events-none absolute left-1/2 top-full z-40 mt-1 hidden -translate-x-1/2 whitespace-nowrap border border-border bg-panel px-2 py-1 text-xs text-text shadow-lg",
            layoutConfig.borderRadius.small,
            "group-hover:block group-focus-within:block"
          )}
        >
          {tooltip}
        </span>
      ) : null}
    </span>
  );
};
