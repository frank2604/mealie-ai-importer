export type StepId = "select" | "analyze" | "review" | "transfer";

export interface StepDefinition {
  id: StepId;
  path: string;
  index: number;
  titleKey: string;
  subtitleKey: string;
}

export const stepDefinitions: StepDefinition[] = [
  {
    id: "select",
    path: "/",
    index: 0,
    titleKey: "steps.select.title",
    subtitleKey: "steps.select.subtitle"
  },
  {
    id: "analyze",
    path: "/analyze",
    index: 1,
    titleKey: "steps.analyze.title",
    subtitleKey: "steps.analyze.subtitle"
  },
  {
    id: "review",
    path: "/review",
    index: 2,
    titleKey: "steps.review.title",
    subtitleKey: "steps.review.subtitle"
  },
  {
    id: "transfer",
    path: "/transfer",
    index: 3,
    titleKey: "steps.transfer.title",
    subtitleKey: "steps.transfer.subtitle"
  }
];

export const getStepByPath = (path: string) =>
  stepDefinitions.find((step) => (step.path === "/" ? path === "/" : path.startsWith(step.path)));
