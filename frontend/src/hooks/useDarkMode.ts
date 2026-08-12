import { useEffect, useState } from "react";

import { storageGet, storageSet } from "@/lib/storage";

export const THEMES = ["light", "soft", "deep"] as const;
export type ThemeName = typeof THEMES[number];

const DEFAULT_THEME: ThemeName = "light";

function initialTheme(): ThemeName {
  const saved = storageGet("vr-theme");
  if (saved === "dark") return "soft";
  if (THEMES.includes(saved as ThemeName)) return saved as ThemeName;
  return DEFAULT_THEME;
}

/** Bright default, a soft gray workspace, and one blue night preset. */
export function useDarkMode() {
  const [theme, setTheme] = useState<ThemeName>(initialTheme);
  const isDark = theme === "deep";

  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove("light", "dark", "theme-soft", "theme-deep");
    if (theme === "light") root.classList.add("light");
    if (theme === "soft") root.classList.add("theme-soft");
    if (theme === "deep") root.classList.add("dark", "theme-deep");
    storageSet("vr-theme", theme);
  }, [theme]);

  return { theme, setTheme, isDark };
}
