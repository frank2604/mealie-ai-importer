import { Dialog, Transition } from "@headlessui/react";
import clsx from "clsx";
import { Fragment } from "react";
import { useTranslation } from "react-i18next";
import { layoutConfig } from "../../../config/layout.config";

interface ConfirmModalProps {
  isOpen: boolean;
  message: string;
  title?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * In-app confirmation dialog. Replaces the native `window.confirm`, which
 * browsers silently suppress (returning false, no popup) after repeated
 * dialogs — that made critical flows like "start new import" appear frozen
 * until a page reload.
 */
export const ConfirmModal: React.FC<ConfirmModalProps> = ({
  isOpen,
  message,
  title,
  confirmLabel,
  cancelLabel,
  onConfirm,
  onCancel
}) => {
  const { t } = useTranslation();

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onCancel}>
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
                  "w-full max-w-md transform overflow-hidden border border-border bg-panel p-6 text-left align-middle shadow-xl transition-all",
                  layoutConfig.borderRadius.large
                )}
              >
                {title ? (
                  <Dialog.Title as="h3" className="text-lg font-semibold text-primary">
                    {title}
                  </Dialog.Title>
                ) : null}
                <p className={clsx("text-sm text-text/80", title ? "mt-2" : "")}>{message}</p>

                <div className="mt-6 flex justify-end gap-3">
                  <button
                    type="button"
                    onClick={onCancel}
                    className={clsx(
                      "focus-ring inline-flex items-center border border-border px-4 py-2 text-sm font-semibold text-text hover:border-primary/50 hover:text-primary",
                      layoutConfig.borderRadius.small
                    )}
                  >
                    {cancelLabel ?? t("buttons.cancel")}
                  </button>
                  <button
                    type="button"
                    onClick={onConfirm}
                    className={clsx(
                      "focus-ring inline-flex items-center bg-primary px-4 py-2 text-sm font-semibold text-on-primary hover:bg-primary/90",
                      layoutConfig.borderRadius.small
                    )}
                  >
                    {confirmLabel ?? t("buttons.confirm", { defaultValue: "Bestätigen" })}
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
