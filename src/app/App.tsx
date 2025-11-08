import { createContext, useContext, useMemo, useRef, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import clsx from "clsx";
import { ArrowLeftIcon, Cog6ToothIcon } from "@heroicons/react/24/outline";
import { StepTabs } from "./components/StepTabs";
import { StickyFooter } from "./components/StickyFooter";
import { getStepByPath, stepDefinitions } from "./stepConfig";
import { layoutConfig } from "../config/layout.config";
import { ImportFlowProvider, useImportFlow } from "./context/ImportFlowContext";
import { resetWorkspace as resetWorkspaceApi } from "./api/imports";

const settingsPath = "/settings";

type StepNextHandler = () => boolean | Promise<boolean>;

interface StepNavigationContextValue {
  setNextHandler: (handler: StepNextHandler | null) => void;
  setNextDisabled: (disabled: boolean) => void;
}

const StepNavigationContext = createContext<StepNavigationContextValue | undefined>(undefined);

export function useStepNavigation(): StepNavigationContextValue {
  const context = useContext(StepNavigationContext);
  if (!context) {
    throw new Error("useStepNavigation muss innerhalb des StepNavigationContext verwendet werden.");
  }
  return context;
}

const AppShell: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { reset: resetFlow } = useImportFlow();
  const nextHandlerRef = useRef<StepNextHandler | null>(null);
  const [isNextDisabled, setIsNextDisabled] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);

  const currentPath = location.pathname;
  const isOnSettings = currentPath.startsWith(settingsPath);
  const currentStep = getStepByPath(currentPath) ?? stepDefinitions[0];

  const currentStepIndex = currentStep.index;
  const isFirstStep = currentStepIndex === 0;
  const isLastStep = currentStepIndex === stepDefinitions.length - 1;
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
    }),
    []
  );

  const handleBack = () => {
    if (isFirstStep) {
      return;
    }
    const previousStep = stepDefinitions[currentStepIndex - 1];
    navigate(previousStep.path);
  };

  const handleNext = () => {
    if (isLastStep) {
      return;
    }
    const maybeHandler = nextHandlerRef.current;
    const result = maybeHandler ? maybeHandler() : true;
    Promise.resolve(result)
      .then((shouldContinue) => {
        if (shouldContinue === false) {
          return;
        }
        const nextStep = stepDefinitions[currentStepIndex + 1];
        navigate(nextStep.path);
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
                <Link to="/" className="focus-ring flex items-center gap-2 text-lg font-semibold text-primary">
                  <span>{t("app.title")}</span>
                </Link>
                <div className="flex items-center gap-3">
                  <div className="hidden text-sm font-medium text-text/70 sm:block">{t("app.subtitle")}</div>
                  <Link
                    to={settingsPath}
                    state={{ from: currentPath }}
                    aria-label={t("navigation.settings")}
                    className={clsx(
                      "focus-ring inline-flex items-center justify-center border border-border bg-panel p-2 hover:border-primary/50",
                      layoutConfig.borderRadius.small,
                      isOnSettings ? "border-primary text-primary" : "text-text hover:text-primary"
                    )}
                  >
                    <Cog6ToothIcon className="h-5 w-5" aria-hidden="true" />
                  </Link>
                </div>
              </div>
              <div className="border-t border-border/60 bg-background/95">
                <div className={clsx("w-full py-4", layoutConfig.spacing.layout.page.x)}>
                  <StepTabs
                    currentStepId={currentStep.id}
                    steps={stepDefinitions}
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

            <main className={clsx("flex w-full flex-1 flex-col overflow-hidden", layoutConfig.spacing.layout.page.x, layoutConfig.spacing.layout.page.y)}>
              <div className="flex min-h-0 flex-1 flex-col">
                <Outlet />
              </div>
            </main>
        </div>

        {!isOnSettings && (
          <StickyFooter
            isFirstStep={isFirstStep}
            isLastStep={isLastStep}
            isNextDisabled={isNextDisabled}
            isCancelDisabled={isCancelling}
            onBack={handleBack}
            onNext={handleNext}
            onCancel={handleCancel}
          />
        )}
      </div>
    </StepNavigationContext.Provider>
  );
};

export const App: React.FC = () => (
  <ImportFlowProvider>
    <AppShell />
  </ImportFlowProvider>
);
