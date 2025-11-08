import { Dialog, Transition } from "@headlessui/react";
import clsx from "clsx";
import { Fragment, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { layoutConfig } from "../../../config/layout.config";
import { ReviewIngredient } from "../../api/review";

export interface UnitCreateFormValues {
  name?: string | null;
  pluralName?: string | null;
  abbreviation?: string | null;
  pluralAbbreviation?: string | null;
  useAbbreviation?: boolean;
}

interface NewUnitModalProps {
  entry: ReviewIngredient | null;
  isOpen: boolean;
  onClose: () => void;
  onSave: (ingredientId: string, values: UnitCreateFormValues) => void;
}

export const NewUnitModal: React.FC<NewUnitModalProps> = ({ entry, isOpen, onClose, onSave }) => {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [pluralName, setPluralName] = useState("");
  const [abbreviation, setAbbreviation] = useState("");
  const [pluralAbbreviation, setPluralAbbreviation] = useState("");
  const [useAbbreviation, setUseAbbreviation] = useState(false);

  useEffect(() => {
    if (!entry) {
      setName("");
      setPluralName("");
      setAbbreviation("");
      setPluralAbbreviation("");
      setUseAbbreviation(false);
      return;
    }
    const decision = (entry.unitDecision || {}) as Record<string, any>;
    const createPayload = (decision.create || {}) as UnitCreateFormValues;
    setName((createPayload.name ?? entry.unitSuggestion?.name ?? entry.unitOriginalName ?? entry.unit ?? "") ?? "");
    setPluralName((createPayload.pluralName ?? entry.unitSuggestion?.pluralName) ?? "");
    setAbbreviation((createPayload.abbreviation ?? entry.unitSuggestion?.abbreviation) ?? "");
    setPluralAbbreviation((createPayload.pluralAbbreviation ?? entry.unitSuggestion?.pluralAbbreviation) ?? "");
    setUseAbbreviation(createPayload.useAbbreviation ?? false);
  }, [entry]);

  const handleSave = () => {
    if (!entry) {
      return;
    }
    const payload: UnitCreateFormValues = {
      name: name || null,
      pluralName: pluralName || null,
      abbreviation: abbreviation || null,
      pluralAbbreviation: pluralAbbreviation || null,
      useAbbreviation
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
                  "w-full max-w-xl transform overflow-hidden border border-border bg-panel p-6 text-left align-middle shadow-xl transition-all",
                  layoutConfig.borderRadius.large
                )}
              >
                <Dialog.Title as="h3" className="text-xl font-semibold text-primary">
                  {t("review.newUnitModal.title", { value: entry?.unitOriginalName ?? entry?.unit ?? "" })}
                </Dialog.Title>

                <div className="mt-6 space-y-4">
                  <div>
                    <label className="block text-sm font-semibold text-text/70">
                      {t("review.newUnitModal.name")}
                    </label>
                    <input
                      value={name}
                      onChange={(event) => setName(event.target.value)}
                      className={clsx(
                        "mt-1 w-full border border-border bg-background px-3 py-2 text-sm text-text",
                        layoutConfig.borderRadius.medium
                      )}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-semibold text-text/70">
                      {t("review.newUnitModal.pluralName")}
                    </label>
                    <input
                      value={pluralName}
                      onChange={(event) => setPluralName(event.target.value)}
                      className={clsx(
                        "mt-1 w-full border border-border bg-background px-3 py-2 text-sm text-text",
                        layoutConfig.borderRadius.medium
                      )}
                    />
                  </div>
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <div>
                      <label className="block text-sm font-semibold text-text/70">
                        {t("review.newUnitModal.abbreviation")}
                      </label>
                      <input
                        value={abbreviation}
                        onChange={(event) => setAbbreviation(event.target.value)}
                        className={clsx(
                          "mt-1 w-full border border-border bg-background px-3 py-2 text-sm text-text",
                          layoutConfig.borderRadius.medium
                        )}
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-semibold text-text/70">
                        {t("review.newUnitModal.pluralAbbreviation")}
                      </label>
                      <input
                        value={pluralAbbreviation}
                        onChange={(event) => setPluralAbbreviation(event.target.value)}
                        className={clsx(
                          "mt-1 w-full border border-border bg-background px-3 py-2 text-sm text-text",
                          layoutConfig.borderRadius.medium
                        )}
                      />
                    </div>
                  </div>
                  <label className="flex items-center gap-2 text-sm font-semibold text-text/70">
                    <input
                      type="checkbox"
                      checked={useAbbreviation}
                      onChange={(event) => setUseAbbreviation(event.target.checked)}
                      className="h-4 w-4 border-border text-primary focus:ring-primary"
                    />
                    {t("review.newUnitModal.useAbbreviation")}
                  </label>
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
                    {t("review.newUnitModal.cancel")}
                  </button>
                  <button
                    type="button"
                    onClick={handleSave}
                    className={clsx(
                      "focus-ring inline-flex items-center bg-primary px-4 py-2 text-sm font-semibold text-on-primary hover:bg-primary/90",
                      layoutConfig.borderRadius.small
                    )}
                  >
                    {t("review.newUnitModal.save")}
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
