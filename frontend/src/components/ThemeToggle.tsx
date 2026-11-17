"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

type Theme = "light" | "dark";

/** Dark is the default workspace theme; a stored choice always wins. */
export function ThemeToggle({ className = "" }: { className?: string }) {
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    const stored = window.localStorage.getItem("clipgen-theme") as Theme | null;
    const next = stored === "light" || stored === "dark" ? stored : "dark";
    setTheme(next);
    applyTheme(next);
  }, []);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    applyTheme(next);
    window.localStorage.setItem("clipgen-theme", next);
  };

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className={`cg-btn ${className}`}
      title={theme === "dark" ? "Ganti ke tema terang" : "Ganti ke tema gelap"}
    >
      {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      <span className="shell-label">{theme === "dark" ? "Tema terang" : "Tema gelap"}</span>
    </button>
  );
}

function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle("dark", theme === "dark");
}
