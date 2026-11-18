const defaultTheme = require("tailwindcss/defaultTheme");

// Design tokens live in src/app/globals.css as space-separated RGB channels so
// opacity utilities (bg-brand/10) keep working in both themes.
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;

/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter Variable"', "Inter", ...defaultTheme.fontFamily.sans],
      },
      colors: {
        // Semantic tokens: prefer these in new code.
        canvas: token("canvas"),
        surface: token("surface"),
        elevated: token("elevated"),
        line: token("line"),
        "line-strong": token("line-strong"),
        ink: token("ink"),
        "ink-muted": token("ink-muted"),
        "ink-subtle": token("ink-subtle"),
        brand: {
          DEFAULT: token("brand"),
          strong: token("brand-strong"),
          soft: token("brand-soft"),
        },
        accent: token("accent"),
        // Legacy neutral scale re-pointed at the workspace palette so existing
        // `slate-*` classes pick up the new dark canvas (#111318) and
        // elevated surface (#20232B) without rewriting every component.
        slate: {
          50: "#F6F7FB",
          100: "#EEF0F6",
          200: "#E2E5EE",
          300: "#C9CEDB",
          400: "#A3A9B8",
          500: "#6B7282",
          600: "#565D6D",
          700: "#3A3F4D",
          800: "#2A2E39",
          900: "#20232B",
          950: "#111318",
        },
      },
      borderRadius: {
        panel: "14px",
      },
      transitionTimingFunction: {
        out: "cubic-bezier(0.2, 0, 0, 1)",
      },
    },
  },
  plugins: [],
};
