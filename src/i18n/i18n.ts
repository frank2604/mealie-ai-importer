import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import de from "./locales/de/common.json";
import en from "./locales/en/common.json";

export const resources = {
  de: { common: de },
  en: { common: en }
} as const;

export const availableLanguages = ["de", "en"] as const;

const fallbackLng = "de";

void i18n.use(initReactI18next).init({
  resources,
  lng: fallbackLng,
  fallbackLng,
  defaultNS: "common",
  interpolation: {
    escapeValue: false
  }
});

export default i18n;
