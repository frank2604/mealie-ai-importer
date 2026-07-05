import { createContext, useContext, useMemo, useRef, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import clsx from "clsx";
import { ArrowLeftIcon, Cog6ToothIcon } from "@heroicons/react/24/outline";
import { StepTabs } from "./components/StepTabs";
import { StickyFooter } from "./components/StickyFooter";
import { getStepByPath, stepDefinitions } from "./stepConfig";
import { layoutConfig } from "../config/layout.config";
import { useImportFlow } from "./context/ImportFlowContext";
import { resetWorkspace as resetWorkspaceApi, archiveRun, resetWorkspace } from "./api/imports";

const settingsPath = "/settings";

type StepNextHandler = () => boolean | Promise<boolean>;

interface StepNavigationContextValue {
  setNextHandler: (handler: StepNextHandler | null) => void;
  setNextDisabled: (disabled: boolean) => void;
  setNextLabel: (label: string | null) => void;
}

const StepNavigationContext = createContext<StepNavigationContextValue | undefined>(undefined);

export function useStepNavigation(): StepNavigationContextValue {
  const context = useContext(StepNavigationContext);
  if (!context) {
    throw new Error("useStepNavigation muss innerhalb des StepNavigationContext verwendet werden.");
  }
  return context;
}

const statusToMaxStepIndex = (status: string | null): number => {
  switch (status) {
    case "review":
      return 1; // Analyse abgeschlossen
    case "transferring":
      return 2; // Review abgeschlossen, Transfer läuft
    case "completed":
      return 3; // alles erledigt
    case "failed":
    case "aborted":
      return 2; // bis Review fertig
    case "starting":
    case "analyzing":
    case "uploading":
    case "uploaded":
    default:
      return 0; // nur Auswahl abgeschlossen
  }
};

const AppShell: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { reset: resetFlow, status: runStatus, runId, isOccupied } = useImportFlow();
  const nextHandlerRef = useRef<StepNextHandler | null>(null);
  const [isNextDisabled, setIsNextDisabled] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [nextLabelOverride, setNextLabelOverride] = useState<string | null>(null);

  const currentPath = location.pathname;
  const isOnSettings = currentPath.startsWith(settingsPath);
  const currentStep = getStepByPath(currentPath) ?? stepDefinitions[0];

  const currentStepIndex = currentStep.index;
  const isFirstStep = currentStepIndex === 0;
  const isLastStep = currentStepIndex === stepDefinitions.length - 1;
  const isRunning = ["uploading", "starting", "analyzing", "transferring"].includes(runStatus);
  const isBackDisabled = isRunning;
  const maxStepIndex = statusToMaxStepIndex(runStatus);
  const settingsBackTarget =
    (location.state as { from?: string } | undefined)?.from ?? stepDefinitions[0].path;
  const navigationContextValue = useMemo(
    () => ({
      setNextHandler: (handler: StepNextHandler | null) => {
        nextHandlerRef.current = handler;
      },
      setNextDisabled: (disabled: boolean) => {
        setIsNextDisabled(disabled);
      },
      setNextLabel: (label: string | null) => {
        setNextLabelOverride(label);
      }
    }),
    []
  );

  const handleBack = () => {
    if (isBackDisabled) {
      return;
    }
    if (isFirstStep) {
      return;
    }
    const previousStep = stepDefinitions[currentStepIndex - 1];
    navigate(previousStep.path);
  };

  const handleNext = () => {
    const maybeHandler = nextHandlerRef.current;
    let result: boolean | Promise<boolean>;
    try {
      result = maybeHandler ? maybeHandler() : true;
    } catch {
      result = false;
    }
    Promise.resolve(result)
      .then((shouldContinue) => {
        if (shouldContinue === false) {
          return;
        }
        if (currentStep.id === "transfer" && runStatus === "completed" && runId) {
          const confirmed = window.confirm(
            t("transfer.confirmArchive", {
              defaultValue: "Der Lauf wird archiviert und alle Schritte werden geleert. Möchtest du fortfahren?"
            })
          );
          if (!confirmed) {
            return;
          }
          archiveRun(runId)
            .catch(() => {})
            .finally(() => {
              resetFlow();
              resetWorkspace().finally(() => {
                navigate("/", { replace: true });
              });
            });
          return;
        }
        const nextStep = stepDefinitions[currentStepIndex + 1];
        if (nextStep) {
          navigate(nextStep.path);
        }
      })
      .catch((error) => {
        // eslint-disable-next-line no-console
        console.error("Navigation zum nächsten Schritt fehlgeschlagen:", error);
      });
  };

  const handleCancel = async () => {
    if (isCancelling) {
      return;
    }
    const confirmed = window.confirm(t("confirmations.cancelImport"));
    if (!confirmed) {
      return;
    }
    setIsCancelling(true);
    try {
      await resetWorkspaceApi();
      resetFlow();
      navigate(stepDefinitions[0].path, { replace: true });
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error("Zurücksetzen des Workspaces fehlgeschlagen:", error);
      const message = error instanceof Error ? error.message : String(error);
      alert(t("errors.resetFailed", { message }));
    } finally {
      setIsCancelling(false);
    }
  };

  const handleSettingsBack = () => {
    navigate(settingsBackTarget, { replace: true });
  };

  return (
    <StepNavigationContext.Provider value={navigationContextValue}>
      <div className="flex h-screen flex-col overflow-hidden bg-background text-text">
        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="sticky top-0 z-40 border-b border-border/70 bg-background/95 backdrop-blur">
          {isOnSettings ? (
            <div className={clsx("flex w-full items-center justify-between gap-4 py-4", layoutConfig.spacing.layout.page.x)}>
              <button
                type="button"
                onClick={handleSettingsBack}
                className={clsx(
                  "focus-ring inline-flex items-center gap-2 border border-border bg-panel px-4 py-2 text-sm font-semibold text-text hover:border-primary/60 hover:text-primary",
                  layoutConfig.borderRadius.small
                )}
              >
                <ArrowLeftIcon className="h-5 w-5" aria-hidden="true" />
                {t("buttons.back")}
              </button>
              <div className="flex flex-col items-end">
                <span className="text-lg font-semibold text-primary">{t("settings.title")}</span>
                <span className="hidden text-sm text-text/70 sm:block">{t("settings.subtitle")}</span>
              </div>
            </div>
          ) : (
            <>
              <div className={clsx("flex w-full items-center justify-between gap-4 py-4", layoutConfig.spacing.layout.page.x)}>
                <Link to="/" className="focus-ring flex items-baseline gap-2 text-lg font-semibold text-primary">
                  <span>{t("app.title")}</span>
                  <span className="text-xs font-normal text-text/40" title={t("app.versionLabel", { version: __APP_VERSION__ })}>
                    v{__APP_VERSION__}
                  </span>
                </Link>
                <div className="flex items-center gap-3">
                  <div className="hidden text-sm font-medium text-text/70 sm:block">{t("app.subtitle")}</div>
                  <button
                    type="button"
                    onClick={() => {
                      if (isRunning) return;
                      navigate(settingsPath, { state: { from: currentPath } });
                    }}
                    aria-label={t("navigation.settings")}
                    disabled={isRunning}
                    className={clsx(
                      "focus-ring inline-flex items-center justify-center border border-border bg-panel p-2",
                      layoutConfig.borderRadius.small,
                      isRunning
                        ? "cursor-not-allowed text-text/40"
                        : isOnSettings
                          ? "border-primary text-primary"
                          : "text-text hover:border-primary/50 hover:text-primary"
                    )}
                  >
                    <Cog6ToothIcon className="h-5 w-5" aria-hidden="true" />
                  </button>
                </div>
              </div>
              <div className="border-t border-border/60 bg-background/95">
                <div className={clsx("w-full py-4", layoutConfig.spacing.layout.page.x)}>
                  <StepTabs
                    currentStepId={currentStep.id}
                    steps={stepDefinitions}
                    isStepDisabled={(_, index) => {
                      if (index === currentStepIndex) return false;
                      if (!runId) return true;
                      if (isRunning) return true;
                      return index > maxStepIndex;
                    }}
                    onStepChange={(step) => {
                      nextHandlerRef.current = null;
                      navigate(step.path);
                    }}
                  />
                </div>
              </div>
            </>
          )}
        </div>

            <main
              className={clsx(
                "flex w-full flex-1 min-h-0 flex-col overflow-y-auto",
                layoutConfig.spacing.layout.page.x,
                layoutConfig.spacing.layout.page.y
              )}
            >
              {isOccupied && (
                <div className="mb-4 flex items-start gap-3 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-amber-800 dark:border-amber-600 dark:bg-amber-950/40 dark:text-amber-300">
                  <span className="mt-0.5 text-lg leading-none">⚠️</span>
                  <div>
                    <p className="font-semibold">{t("app.occupied.title")}</p>
                    <p className="mt-0.5 text-sm">{t("app.occupied.message")}</p>
                  </div>
                </div>
              )}
              <Outlet />
            </main>
        </div>

        {!isOnSettings && (
          <StickyFooter
            isFirstStep={isFirstStep}
            isLastStep={isLastStep}
            isNextDisabled={isNextDisabled}
            isCancelDisabled={isCancelling}
            isBackDisabled={isBackDisabled}
            nextLabelOverride={nextLabelOverride}
            onBack={handleBack}
            onNext={handleNext}
            onCancel={handleCancel}
          />
        )}
      </div>
    </StepNavigationContext.Provider>
  );
};

export const App: React.FC = () => <AppShell />;
