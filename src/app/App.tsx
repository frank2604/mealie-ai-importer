import { useCallback } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import clsx from "clsx";
import { availableLanguages } from "../i18n/i18n";
import { StepTabs } from "./components/StepTabs";
import { StickyFooter } from "./components/StickyFooter";
import { useTheme } from "../theme/useTheme";
import { getStepByPath, stepDefinitions } from "./stepConfig";
import { layoutConfig } from "../config/layout.config";

const settingsPath = "/settings";

export const App: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const activeLanguage = (i18n.resolvedLanguage ?? i18n.language) as (typeof availableLanguages)[number];
  const { theme, toggleTheme } = useTheme();

  const currentPath = location.pathname;
  const isOnSettings = currentPath.startsWith(settingsPath);
  const currentStep = getStepByPath(currentPath) ?? stepDefinitions[0];

  const currentStepIndex = currentStep.index;
  const isFirstStep = currentStepIndex === 0;
  const isLastStep = currentStepIndex === stepDefinitions.length - 1;

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
    const nextStep = stepDefinitions[currentStepIndex + 1];
    navigate(nextStep.path);
  };

  const handleCancel = () => {
    navigate(stepDefinitions[0].path);
  };

  const changeLanguage = useCallback(
    (lng: (typeof availableLanguages)[number]) => {
      void i18n.changeLanguage(lng);
    },
    [i18n]
  );

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background text-text">
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="sticky top-0 z-40 border-b border-border/70 bg-background/95 backdrop-blur">
          <div className="mx-auto flex w-full max-w-7xl items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
            <Link to="/" className="focus-ring flex items-center gap-2 text-lg font-semibold text-primary">
              <span>{t("app.title")}</span>
            </Link>
            <div className="flex items-center gap-3">
              <div className="hidden text-sm font-medium text-text/70 sm:block">{t("app.subtitle")}</div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={toggleTheme}
                  className={clsx("focus-ring border border-border bg-panel px-3 py-1 text-sm font-medium text-text hover:border-primary/50 hover:text-primary", layoutConfig.borderRadius.small)}
                  aria-label={t("theme.toggle")}
                >
                  {theme === "light" ? t("theme.light") : t("theme.dark")}
                </button>
                <div className={clsx("flex overflow-hidden border border-border bg-panel", layoutConfig.borderRadius.small)}>
                  {availableLanguages.map((lng) => (
                    <button
                      key={lng}
                      type="button"
                      onClick={() => changeLanguage(lng)}
                      className={`focus-ring px-3 py-1 text-sm font-medium ${
                        activeLanguage === lng ? "bg-primary text-on-primary" : "text-text hover:bg-secondary/60"
                      }`}
                      aria-pressed={activeLanguage === lng}
                      aria-label={t("language.toggle")}
                    >
                      {t(`language.${lng}`)}
                    </button>
                  ))}
                </div>
                <Link
                  to={settingsPath}
                  className={clsx(
                    "focus-ring border border-border bg-panel px-3 py-1 text-sm font-semibold hover:border-primary/50 hover:text-primary",
                    layoutConfig.borderRadius.small,
                    isOnSettings && "border-primary text-primary"
                  )}
                >
                  {t("navigation.settings")}
                </Link>
              </div>
            </div>
          </div>
          {!isOnSettings && (
            <div className="border-t border-border/60 bg-background/95">
              <div className="mx-auto w-full max-w-7xl px-4 py-4 sm:px-6 lg:px-8">
                <StepTabs
                  currentStepId={currentStep.id}
                  steps={stepDefinitions}
                  onStepChange={(step) => navigate(step.path)}
                />
              </div>
            </div>
          )}
        </div>

        <main className={clsx("mx-auto flex w-full max-w-7xl flex-1 flex-col overflow-hidden px-4 sm:px-6 lg:px-8", layoutConfig.spacing.layout.page.y)}>
          <div className="flex min-h-0 flex-1 flex-col">
            <Outlet />
          </div>
        </main>
      </div>

      {!isOnSettings && (
        <StickyFooter
          isFirstStep={isFirstStep}
          isLastStep={isLastStep}
          onBack={handleBack}
          onNext={handleNext}
          onCancel={handleCancel}
        />
      )}
    </div>
  );
};
