import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider, createBrowserRouter } from "react-router-dom";
import "./styles/index.css";
import "./i18n/i18n";
import { ThemeProvider } from "./theme/useTheme";
import { App } from "./app/App";
import { Step1Select } from "./app/routes/Step1Select";
import { Step2Analyze } from "./app/routes/Step2Analyze";
import { Step3Review } from "./app/routes/Step3Review";
import { Step4Transfer } from "./app/routes/Step4Transfer";
import { Settings } from "./app/routes/Settings";

const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      {
        index: true,
        element: <Step1Select />
      },
      {
        path: "analyze",
        element: <Step2Analyze />
      },
      {
        path: "review",
        element: <Step3Review />
      },
      {
        path: "transfer",
        element: <Step4Transfer />
      },
      {
        path: "settings",
        element: <Settings />
      }
    ]
  }
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider>
      <RouterProvider router={router} />
    </ThemeProvider>
  </React.StrictMode>
);
