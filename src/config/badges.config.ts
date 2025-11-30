import { layoutConfig } from "./layout.config";

export type BadgeIconName = "sparkles" | "finger-print" | "adjustments" | "plus" | "pencil" | "minus" | "warning";

export interface BadgeConfig {
  id: string;
  icon: BadgeIconName;
  className: string;
  tooltipKey: string;
}

const baseBadgeClasses =
  "inline-flex items-center border px-2 py-0.5 text-[11px] font-semibold uppercase";

export const badgeConfig: Record<string, BadgeConfig> = {
  found_word: {
    id: "found_word",
    icon: "finger-print",
    className: `${baseBadgeClasses} text-success border-success/40 bg-success/10 ${layoutConfig.borderRadius.small}`,
    tooltipKey: "review.badges.foundWord"
  },
  found_fuzzy: {
    id: "found_fuzzy",
    icon: "adjustments",
    className: `${baseBadgeClasses} text-success border-success/40 bg-success/10 ${layoutConfig.borderRadius.small}`,
    tooltipKey: "review.badges.foundFuzzy"
  },
  found_ai: {
    id: "found_ai",
    icon: "sparkles",
    className: `${baseBadgeClasses} text-success border-success/40 bg-success/10 ${layoutConfig.borderRadius.small}`,
    tooltipKey: "review.badges.foundAi"
  },
  new: {
    id: "new",
    icon: "plus",
    className: `${baseBadgeClasses} text-warning border-warning/40 bg-warning/10 ${layoutConfig.borderRadius.small}`,
    tooltipKey: "review.badges.new"
  },
  manual: {
    id: "manual",
    icon: "pencil",
    className: `${baseBadgeClasses} text-info border-info/40 bg-info/10 ${layoutConfig.borderRadius.small}`,
    tooltipKey: "review.badges.manual"
  },
  none: {
    id: "none",
    icon: "warning",
    className: `${baseBadgeClasses} text-error/60 border-border/50 bg-background/50 ${layoutConfig.borderRadius.small}`,
    tooltipKey: "review.badges.none"
  },
  no_amount: {
    id: "no_amount",
    icon: "sparkles",
    className: `${baseBadgeClasses} text-success border-success/40 bg-success/10 ${layoutConfig.borderRadius.small}`,
    tooltipKey: "review.badges.noAmount"
  }
};

export type BadgeId = keyof typeof badgeConfig;
