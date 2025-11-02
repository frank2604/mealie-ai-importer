const withOpacityValue = (variable) => {
  return ({ opacityValue }) => {
    if (opacityValue !== undefined) {
      return `rgb(var(${variable}) / ${opacityValue})`;
    }
    return `rgb(var(${variable}) / 1)`;
  };
};

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: withOpacityValue("--primary-rgb"),
        accent: withOpacityValue("--accent-rgb"),
        secondary: withOpacityValue("--secondary-rgb"),
        success: withOpacityValue("--success-rgb"),
        info: withOpacityValue("--info-rgb"),
        warning: withOpacityValue("--warning-rgb"),
        error: withOpacityValue("--error-rgb"),
        "on-primary": "var(--on-primary)",
        "on-secondary": "var(--on-secondary)",
        border: withOpacityValue("--border-rgb"),
        panel: withOpacityValue("--panel-rgb"),
        background: withOpacityValue("--background-rgb"),
        text: withOpacityValue("--text-rgb")
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"]
      },
      boxShadow: {
        focus: "0 0 0 3px var(--primary)"
      }
    }
  },
  plugins: [require("@tailwindcss/forms")]
};
