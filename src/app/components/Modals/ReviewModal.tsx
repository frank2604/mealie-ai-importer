import { Dialog, Switch, Transition } from "@headlessui/react";
import clsx from "clsx";
import { Fragment, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { layoutConfig } from "../../../config/layout.config";

type ReviewStatus = "found" | "new" | "error" | "info";

interface ReviewEntry {
  amount: string;
  unit: string;
  unitMapping: string;
  unitStatus: ReviewStatus;
  unitMethod?: string;
  unitConfidence?: string;
  unitNew?: {
    nameSingular: string;
    namePlural: string;
    abbreviationSingular: string;
    abbreviationPlural: string;
    useAbbreviation: boolean;
    supportsFraction: boolean;
  };
  ingredient: string;
  ingredientMapping: string;
  ingredientStatus: ReviewStatus;
  ingredientMethod?: string;
  ingredientConfidence?: string;
  ingredientNew?: {
    nameSingular: string;
    namePlural: string;
    category: string;
    aliases: string;
  };
  note: string;
}

export interface ModalContext {
  entry: ReviewEntry;
  target: "unit" | "ingredient";
}

interface ReviewModalProps {
  context: ModalContext | null;
  onClose: () => void;
}

const methodLabels: Record<string, string> = {
  "word-match": "review.modal.methods.word",
  fuzzy: "review.modal.methods.fuzzy",
  ai: "review.modal.methods.ai"
};

export const ReviewModal: React.FC<ReviewModalProps> = ({ context, onClose }) => {
  const { t, i18n } = useTranslation();
  const isOpen = Boolean(context);

  const [unitState, setUnitState] = useState(() => context?.entry.unitNew);
  const [ingredientState, setIngredientState] = useState(() => context?.entry.ingredientNew);

  useEffect(() => {
    setUnitState(context?.entry.unitNew);
    setIngredientState(context?.entry.ingredientNew);
  }, [context?.entry.unitNew, context?.entry.ingredientNew, i18n.resolvedLanguage]);

  const categories = useMemo(() => {
    const translated = t("review.modal.categories", { returnObjects: true }) as string[] | undefined;
    return translated && translated.length > 0 ? translated : defaultCategories;
  }, [t, i18n.resolvedLanguage]);

  if (!context) {
    return null;
  }

  const isUnit = context.target === "unit";
  const entry = context.entry;
  const status = isUnit ? entry.unitStatus : entry.ingredientStatus;
  const isFound = status === "found";

  const title = isUnit ? entry.unitMapping : entry.ingredientMapping;
  const subtitle = isFound
    ? t(isUnit ? "review.modal.unitFound.subtitle" : "review.modal.ingredientFound.subtitle")
    : t(isUnit ? "review.modal.unitNew.subtitle" : "review.modal.ingredientNew.subtitle");

  const methodKey = isUnit ? entry.unitMethod : entry.ingredientMethod;
  const confidence = isUnit ? entry.unitConfidence : entry.ingredientConfidence;

  const methodLabel = methodKey ? t(methodLabels[methodKey] ?? methodKey) : undefined;

  return (
    <Transition appear show={isOpen} as={Fragment}>
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
              <Dialog.Panel className={clsx("w-full max-w-2xl transform overflow-hidden border border-border bg-panel p-6 text-left align-middle shadow-xl transition-all", layoutConfig.borderRadius.large)}>
                <Dialog.Title as="h3" className="text-xl font-semibold text-primary">
                  {title}
                </Dialog.Title>
                <p className="mt-2 text-sm text-text/70">{subtitle}</p>

                {isFound ? (
                  <div className="mt-6 space-y-4 text-sm text-text/80">
                    <div className={clsx("border border-border/60 bg-background/40 px-4 py-3", layoutConfig.borderRadius.medium)}>
                      <span className="text-xs uppercase text-text/60">
                        {t("review.modal.methodLabel")}
                      </span>
                      <div className="mt-1 font-semibold">
                        {methodLabel ?? t("review.modal.methodUnknown")}
                      </div>
                    </div>
                    {confidence ? (
                      <div className={clsx("border border-border/60 bg-background/40 px-4 py-3", layoutConfig.borderRadius.medium)}>
                        <span className="text-xs uppercase text-text/60">{t("review.modal.confidenceLabel")}</span>
                        <div className="mt-1 font-semibold text-success">{confidence}</div>
                      </div>
                    ) : null}
                    <button
                      type="button"
                      onClick={onClose}
                      className={clsx("focus-ring inline-flex bg-primary px-4 py-2 text-sm font-semibold text-on-primary hover:bg-primary/90", layoutConfig.borderRadius.small)}
                    >
                      {t("review.modal.close")}
                    </button>
                  </div>
                ) : isUnit ? (
                  <div className="mt-6 space-y-5 text-sm text-text/80">
                    <table className="w-full border border-border text-sm">
                      <tbody>
                        <ReviewModalRow
                          label={t("review.modal.unitNew.fields.nameSingular")}
                          value={unitState?.nameSingular ?? ""}
                          onChange={(value) =>
                            setUnitState((prev) => ({
                              ...(prev ?? entry.unitNew ?? defaultUnitTemplate),
                              nameSingular: value
                            }))
                          }
                        />
                        <ReviewModalRow
                          label={t("review.modal.unitNew.fields.namePlural")}
                          value={unitState?.namePlural ?? ""}
                          onChange={(value) =>
                            setUnitState((prev) => ({
                              ...(prev ?? entry.unitNew ?? defaultUnitTemplate),
                              namePlural: value
                            }))
                          }
                        />
                        <ReviewModalRow
                          label={t("review.modal.unitNew.fields.abbreviationSingular")}
                          value={unitState?.abbreviationSingular ?? ""}
                          onChange={(value) =>
                            setUnitState((prev) => ({
                              ...(prev ?? entry.unitNew ?? defaultUnitTemplate),
                              abbreviationSingular: value
                            }))
                          }
                        />
                        <ReviewModalRow
                          label={t("review.modal.unitNew.fields.abbreviationPlural")}
                          value={unitState?.abbreviationPlural ?? ""}
                          onChange={(value) =>
                            setUnitState((prev) => ({
                              ...(prev ?? entry.unitNew ?? defaultUnitTemplate),
                              abbreviationPlural: value
                            }))
                          }
                        />
                        <ReviewModalSwitchRow
                          label={t("review.modal.unitNew.fields.useAbbreviation")}
                          checked={unitState?.useAbbreviation ?? true}
                          onChange={(checked) =>
                            setUnitState((prev) => ({
                              ...(prev ?? entry.unitNew ?? defaultUnitTemplate),
                              useAbbreviation: checked
                            }))
                          }
                        />
                        <ReviewModalSwitchRow
                          label={t("review.modal.unitNew.fields.supportsFraction")}
                          checked={unitState?.supportsFraction ?? false}
                          onChange={(checked) =>
                            setUnitState((prev) => ({
                              ...(prev ?? entry.unitNew ?? defaultUnitTemplate),
                              supportsFraction: checked
                            }))
                          }
                        />
                      </tbody>
                    </table>
                    <div className="flex justify-end gap-3">
                      <button
                        type="button"
                        onClick={onClose}
                        className={clsx("focus-ring inline-flex border border-border px-4 py-2 text-sm font-semibold text-text hover:border-primary/60 hover:text-primary", layoutConfig.borderRadius.small)}
                      >
                        {t("review.modal.cancel")}
                      </button>
                      <button
                        type="button"
                        onClick={onClose}
                        className={clsx("focus-ring inline-flex bg-primary px-4 py-2 text-sm font-semibold text-on-primary hover:bg-primary/90", layoutConfig.borderRadius.small)}
                      >
                        {t("review.modal.save")}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="mt-6 space-y-5 text-sm text-text/80">
                    <table className="w-full border border-border text-sm">
                      <tbody>
                        <ReviewModalRow
                          label={t("review.modal.ingredientNew.fields.nameSingular")}
                          value={ingredientState?.nameSingular ?? ""}
                          onChange={(value) =>
                            setIngredientState((prev) => ({
                              ...(prev ?? entry.ingredientNew ?? defaultIngredientTemplate),
                              nameSingular: value
                            }))
                          }
                        />
                        <ReviewModalRow
                          label={t("review.modal.ingredientNew.fields.namePlural")}
                          value={ingredientState?.namePlural ?? ""}
                          onChange={(value) =>
                            setIngredientState((prev) => ({
                              ...(prev ?? entry.ingredientNew ?? defaultIngredientTemplate),
                              namePlural: value
                            }))
                          }
                        />
                        <ReviewModalSelectRow
                          label={t("review.modal.ingredientNew.fields.category")}
                          value={ingredientState?.category ?? ""}
                          options={categories}
                          onChange={(value) =>
                            setIngredientState((prev) => ({
                              ...(prev ?? entry.ingredientNew ?? defaultIngredientTemplate),
                              category: value
                            }))
                          }
                        />
                        <ReviewModalRow
                          label={t("review.modal.ingredientNew.fields.aliases")}
                          value={ingredientState?.aliases ?? ""}
                          onChange={(value) =>
                            setIngredientState((prev) => ({
                              ...(prev ?? entry.ingredientNew ?? defaultIngredientTemplate),
                              aliases: value
                            }))
                          }
                        />
                      </tbody>
                    </table>
                    <div className="flex justify-end gap-3">
                      <button
                        type="button"
                        onClick={onClose}
                        className={clsx("focus-ring inline-flex border border-border px-4 py-2 text-sm font-semibold text-text hover:border-primary/60 hover:text-primary", layoutConfig.borderRadius.small)}
                      >
                        {t("review.modal.cancel")}
                      </button>
                      <button
                        type="button"
                        onClick={onClose}
                        className={clsx("focus-ring inline-flex bg-primary px-4 py-2 text-sm font-semibold text-on-primary hover:bg-primary/90", layoutConfig.borderRadius.small)}
                      >
                        {t("review.modal.save")}
                      </button>
                    </div>
                  </div>
                )}
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
};

interface RowProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
}

const ReviewModalRow: React.FC<RowProps> = ({ label, value, onChange }) => (
  <tr className="border-t border-border">
    <td className="w-1/3 px-4 py-3 text-sm font-semibold text-text/70">{label}</td>
    <td className="px-4 py-3">
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={clsx("focus-ring w-full border border-border bg-background px-4 py-2 text-sm", layoutConfig.borderRadius.small)}
      />
    </td>
  </tr>
);

interface SwitchRowProps {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}

const ReviewModalSwitchRow: React.FC<SwitchRowProps> = ({ label, checked, onChange }) => (
  <tr className="border-t border-border">
    <td className="w-1/3 px-4 py-3 text-sm font-semibold text-text/70">{label}</td>
    <td className="px-4 py-3">
      <Switch
        checked={checked}
        onChange={onChange}
        className={clsx(
          checked ? "bg-primary" : "bg-border",
          "relative inline-flex h-6 w-11 items-center transition-colors focus-ring",
          layoutConfig.borderRadius.small
        )}
      >
        <span
          className={clsx(
            checked ? "translate-x-6" : "translate-x-1",
            "inline-block h-4 w-4 transform bg-panel transition-transform",
            layoutConfig.borderRadius.small
          )}
        />
      </Switch>
    </td>
  </tr>
);

const defaultCategories = [
  "Gemüse",
  "Obst",
  "Gewürze",
  "Fleisch",
  "Fisch",
  "Getreide",
  "Milchprodukte",
  "Saucen"
];

const defaultUnitTemplate = {
  nameSingular: "",
  namePlural: "",
  abbreviationSingular: "",
  abbreviationPlural: "",
  useAbbreviation: true,
  supportsFraction: false
};

const defaultIngredientTemplate = {
  nameSingular: "",
  namePlural: "",
  category: "",
  aliases: ""
};

interface SelectRowProps {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}

const ReviewModalSelectRow: React.FC<SelectRowProps> = ({ label, value, options, onChange }) => (
  <tr className="border-t border-border">
    <td className="w-1/3 px-4 py-3 text-sm font-semibold text-text/70">{label}</td>
    <td className="px-4 py-3">
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={clsx("focus-ring w-full border border-border bg-background px-4 py-2 text-sm", layoutConfig.borderRadius.small)}
      >
        {options.map((category) => (
          <option key={category} value={category}>
            {category}
          </option>
        ))}
      </select>
    </td>
  </tr>
);
