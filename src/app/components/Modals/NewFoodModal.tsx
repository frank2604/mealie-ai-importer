import { Dialog, Transition } from "@headlessui/react";
import clsx from "clsx";
import { Fragment, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { layoutConfig } from "../../../config/layout.config";
import { CategoryOption, ReviewIngredient } from "../../api/review";

export interface FoodCreateFormValues {
  nameSingular?: string | null;
  namePlural?: string | null;
  aliases?: string[];
  categoryId?: string | null;
  categoryName?: string | null;
  description?: string | null;
}

interface NewFoodModalProps {
  entry: ReviewIngredient | null;
  categories: CategoryOption[];
  isOpen: boolean;
  onClose: () => void;
  onSave: (ingredientId: string, values: FoodCreateFormValues) => void;
}

export const NewFoodModal: React.FC<NewFoodModalProps> = ({ entry, categories, isOpen, onClose, onSave }) => {
  const { t } = useTranslation();
  const [nameSingular, setNameSingular] = useState("");
  const [namePlural, setNamePlural] = useState("");
  const [aliasesInput, setAliasesInput] = useState("");
  const [categoryId, setCategoryId] = useState<string>("");
  const [description, setDescription] = useState("");

  useEffect(() => {
    if (!entry) {
      setNameSingular("");
      setNamePlural("");
      setAliasesInput("");
      setCategoryId("");
      setDescription("");
      return;
    }
    const decision = (entry.foodDecision || {}) as Record<string, any>;
    const createPayload = (decision.create || {}) as FoodCreateFormValues;
    setNameSingular(
      (createPayload.nameSingular ??
        entry.foodSuggestion?.nameSingular ??
        entry.foodOriginalName ??
        entry.name) ??
        ""
    );
    setNamePlural((createPayload.namePlural ?? entry.foodSuggestion?.namePlural) ?? "");
    setAliasesInput((createPayload.aliases ?? entry.foodSuggestion?.aliases ?? []).join(", "));
    setCategoryId(createPayload.categoryId ?? entry.foodSuggestion?.categoryId ?? "");
    setDescription(createPayload.description ?? "");
  }, [entry]);

  const handleSave = () => {
    if (!entry) {
      return;
    }
    const trimmedAliases = aliasesInput
      .split(",")
      .map((value) => value.trim())
      .filter((value) => value.length > 0);
    const selectedCategory = categories.find((category) => category.id === categoryId);
    const payload: FoodCreateFormValues = {
      nameSingular: nameSingular || null,
      namePlural: namePlural || null,
      aliases: trimmedAliases,
      categoryId: categoryId || null,
      categoryName: selectedCategory?.name ?? null,
      description: description || null
    };
    onSave(entry.id, payload);
    onClose();
  };

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
              <Dialog.Panel
                className={clsx(
                  "w-full max-w-2xl transform overflow-hidden border border-border bg-panel p-6 text-left align-middle shadow-xl transition-all",
                  layoutConfig.borderRadius.large
                )}
              >
                <Dialog.Title as="h3" className="text-xl font-semibold text-primary">
                  {t("review.newFoodModal.title", { value: entry?.foodOriginalName ?? entry?.name ?? "" })}
                </Dialog.Title>

                <div className="mt-6 space-y-4">
                  <div>
                    <label className="block text-sm font-semibold text-text/70">
                      {t("review.newFoodModal.nameSingular")}
                    </label>
                    <input
                      value={nameSingular}
                      onChange={(event) => setNameSingular(event.target.value)}
                      className={clsx(
                        "mt-1 w-full border border-border bg-background px-3 py-2 text-sm text-text",
                        layoutConfig.borderRadius.medium
                      )}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-semibold text-text/70">
                      {t("review.newFoodModal.namePlural")}
                    </label>
                    <input
                      value={namePlural}
                      onChange={(event) => setNamePlural(event.target.value)}
                      className={clsx(
                        "mt-1 w-full border border-border bg-background px-3 py-2 text-sm text-text",
                        layoutConfig.borderRadius.medium
                      )}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-semibold text-text/70">
                      {t("review.newFoodModal.aliases")}
                    </label>
                    <textarea
                      value={aliasesInput}
                      onChange={(event) => setAliasesInput(event.target.value)}
                      rows={2}
                      className={clsx(
                        "mt-1 w-full border border-border bg-background px-3 py-2 text-sm text-text",
                        layoutConfig.borderRadius.medium
                      )}
                      placeholder={t("review.newFoodModal.aliasPlaceholder")}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-semibold text-text/70">
                      {t("review.newFoodModal.category")}
                    </label>
                    <select
                      value={categoryId}
                      onChange={(event) => setCategoryId(event.target.value)}
                      className={clsx(
                        "mt-1 w-full border border-border bg-background px-3 py-2 text-sm text-text",
                        layoutConfig.borderRadius.medium
                      )}
                    >
                      <option value="">{t("review.newFoodModal.categoryPlaceholder")}</option>
                      {categories.map((category) => (
                        <option key={category.id} value={category.id}>
                          {category.name ?? category.id}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-semibold text-text/70">
                      {t("review.newFoodModal.description")}
                    </label>
                    <textarea
                      value={description}
                      onChange={(event) => setDescription(event.target.value)}
                      rows={3}
                      className={clsx(
                        "mt-1 w-full border border-border bg-background px-3 py-2 text-sm text-text",
                        layoutConfig.borderRadius.medium
                      )}
                    />
                  </div>
                </div>

                <div className="mt-6 flex justify-end gap-3">
                  <button
                    type="button"
                    onClick={onClose}
                    className={clsx(
                      "focus-ring inline-flex items-center border border-border px-4 py-2 text-sm font-semibold text-text hover:border-primary/50 hover:text-primary",
                      layoutConfig.borderRadius.small
                    )}
                  >
                    {t("review.newFoodModal.cancel")}
                  </button>
                  <button
                    type="button"
                    onClick={handleSave}
                    className={clsx(
                      "focus-ring inline-flex items-center bg-primary px-4 py-2 text-sm font-semibold text-on-primary hover:bg-primary/90",
                      layoutConfig.borderRadius.small
                    )}
                  >
                    {t("review.newFoodModal.save")}
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
