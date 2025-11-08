import { Dialog, Transition } from "@headlessui/react";
import clsx from "clsx";
import { Fragment } from "react";
import { useTranslation } from "react-i18next";
import { layoutConfig } from "../../../config/layout.config";
import { BadgeId } from "../../../config/badges.config";
import { ReviewIngredient } from "../../api/review";
import { BadgePill } from "../BadgePill";

export interface ModalContext {
  entry: ReviewIngredient;
  target: "unit" | "ingredient";
}

interface ReviewModalProps {
  context: ModalContext | null;
  onClose: () => void;
}

const mapStatusToBadgeId = (status?: string | null): BadgeId | null => {
  switch (status) {
    case "found_word":
    case "found_fuzzy":
    case "found_ai":
      return status as BadgeId;
    case "found":
      return "found_word";
    case "new":
      return "new";
    case "manual":
      return "manual";
    case "none":
      return "none";
    default:
      return null;
  }
};

export const ReviewModal: React.FC<ReviewModalProps> = ({ context, onClose }) => {
  const { t } = useTranslation();

  if (!context) {
    return null;
  }

  const { entry, target } = context;
  const isUnit = target === "unit";
  const selectionBadgeId = (isUnit ? entry.unitSelection?.badgeId : entry.foodSelection?.badgeId) as
    | BadgeId
    | undefined;
  const rawStatus = isUnit ? entry.unitStatus : entry.foodStatus;
  const badgeId = selectionBadgeId ?? mapStatusToBadgeId(rawStatus);
  const fallbackStatus = isUnit ? "none" : "new";
  const match = isUnit ? entry.unitMatch : entry.foodMatch;
  const candidates = isUnit ? entry.unitCandidates : entry.foodCandidates;
  const suggestion = isUnit ? entry.unitSuggestion : entry.foodSuggestion;
  const title = isUnit ? entry.unitMatch?.name ?? entry.unit ?? "" : entry.foodMatch?.name ?? entry.name;

  return (
    <Transition appear show as={Fragment}>
      <Dialog as="div" className="relative z-40" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-200"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-150"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4 text-center">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-200"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-150"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel
                className={clsx(
                  "w-full max-w-2xl transform overflow-hidden border border-border bg-panel p-6 text-left align-middle shadow-xl transition-all",
                  layoutConfig.borderRadius.large
                )}
              >
                <Dialog.Title as="h3" className="text-xl font-semibold text-primary">
                  {title}
                </Dialog.Title>
                <div className="mt-4 inline-flex">
                  <BadgePill badgeId={badgeId ?? null} fallbackStatus={fallbackStatus} />
                </div>

                <div className="mt-6 space-y-6 text-sm text-text/80">
                  <section className="space-y-2">
                    <h4 className="text-xs font-semibold uppercase tracking-wide text-text/60">
                      {t("review.modal.currentMapping")}
                    </h4>
                    {match?.name ? (
                      <div className="rounded-md border border-border/60 bg-background/60 px-4 py-3">
                        <div className="font-semibold text-text">{match.name}</div>
                        {match.strategy ? (
                          <div className="text-xs text-text/60">
                            {t("review.modal.strategy", { strategy: match.strategy })}
                          </div>
                        ) : null}
                      </div>
                    ) : (
                      <div className="rounded-md border border-dashed border-border/60 px-4 py-3 text-xs text-text/60">
                        {t("review.modal.noMapping")}
                      </div>
                    )}
                  </section>

                  <section className="space-y-2">
                    <h4 className="text-xs font-semibold uppercase tracking-wide text-text/60">
                      {t("review.modal.candidates")}
                    </h4>
                    {candidates.length > 0 ? (
                      <ul className="space-y-2">
                        {candidates.map((candidate) => (
                          <li
                            key={candidate.id}
                            className={clsx(
                              "flex items-center justify-between border border-border/60 bg-background/60 px-4 py-2",
                              layoutConfig.borderRadius.medium
                            )}
                          >
                            <div>
                              <div className="font-semibold text-text">{candidate.name}</div>
                              {candidate.pluralName ? (
                                <div className="text-xs text-text/60">
                                  {t("review.modal.plural", { value: candidate.pluralName })}
                                </div>
                              ) : null}
                              {isUnit && (candidate.abbreviation || candidate.pluralAbbreviation) ? (
                                <div className="text-xs text-text/60">
                                  {[
                                    candidate.abbreviation ? t("review.modal.abbreviation", { value: candidate.abbreviation }) : null,
                                    candidate.pluralAbbreviation ? t("review.modal.abbreviationPlural", { value: candidate.pluralAbbreviation }) : null
                                  ]
                                    .filter(Boolean)
                                    .join(" · ")}
                                </div>
                              ) : null}
                            </div>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <div className="rounded-md border border-dashed border-border/60 px-4 py-3 text-xs text-text/60">
                        {t("review.modal.noCandidates")}
                      </div>
                    )}
                  </section>

                  {suggestion ? (
                    <section className="space-y-2">
                      <h4 className="text-xs font-semibold uppercase tracking-wide text-text/60">
                        {t("review.modal.suggestion.title")}
                      </h4>
                      <div className={clsx("border border-border/60 bg-background/60 px-4 py-3", layoutConfig.borderRadius.medium)}>
                        {isUnit ? (
                          <div className="space-y-1">
                            {suggestion.name ? (
                              <div className="font-semibold text-text">{suggestion.name}</div>
                            ) : null}
                            {suggestion.pluralName ? (
                              <div className="text-xs text-text/60">
                                {t("review.modal.plural", { value: suggestion.pluralName })}
                              </div>
                            ) : null}
                            {(suggestion.abbreviation || suggestion.pluralAbbreviation) && (
                              <div className="text-xs text-text/60">
                                {[
                                  suggestion.abbreviation
                                    ? t("review.modal.abbreviation", { value: suggestion.abbreviation })
                                    : null,
                                  suggestion.pluralAbbreviation
                                    ? t("review.modal.abbreviationPlural", { value: suggestion.pluralAbbreviation })
                                    : null
                                ]
                                  .filter(Boolean)
                                  .join(" · ")}
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="space-y-1">
                            {suggestion.nameSingular ? (
                              <div className="font-semibold text-text">{suggestion.nameSingular}</div>
                            ) : null}
                            {suggestion.namePlural ? (
                              <div className="text-xs text-text/60">
                                {t("review.modal.plural", { value: suggestion.namePlural })}
                              </div>
                            ) : null}
                            {suggestion.categoryName ? (
                              <div className="text-xs text-text/60">
                                {t("review.modal.category", { value: suggestion.categoryName })}
                              </div>
                            ) : null}
                            {suggestion.aliases?.length ? (
                              <div className="text-xs text-text/60">
                                {t("review.modal.aliases", { value: suggestion.aliases.join(", ") })}
                              </div>
                            ) : null}
                          </div>
                        )}
                      </div>
                    </section>
                  ) : null}
                </div>

                <div className="mt-6 flex justify-end">
                  <button
                    type="button"
                    onClick={onClose}
                    className={clsx(
                      "focus-ring inline-flex items-center bg-primary px-4 py-2 text-sm font-semibold text-on-primary hover:bg-primary/90",
                      layoutConfig.borderRadius.small
                    )}
                  >
                    {t("review.modal.close")}
                  </button>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
};
