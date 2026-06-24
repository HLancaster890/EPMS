"use client";

import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import { themes, getThemeById, getDefaultTheme, type Theme } from "@/lib/theme";

interface ThemeContextValue {
  theme: Theme;
  setTheme: (id: string) => void;
  themeId: string;
  isDark: boolean;
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: getDefaultTheme(),
  setTheme: () => {},
  themeId: "midnight-indigo",
  isDark: true,
});

export function useTheme() {
  return useContext(ThemeContext);
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [themeId, setThemeId] = useState<string>("midnight-indigo");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("epms_theme");
    if (stored && themes.some((t) => t.id === stored)) {
      setThemeId(stored);
    }
    setMounted(true);
  }, []);

  useEffect(() => {
    if (mounted) {
      document.documentElement.setAttribute("data-theme", themeId);
      localStorage.setItem("epms_theme", themeId);
    }
  }, [themeId, mounted]);

  const setTheme = useCallback((id: string) => {
    if (themes.some((t) => t.id === id)) {
      setThemeId(id);
    }
  }, []);

  const theme = getThemeById(themeId);

  if (!mounted) {
    return <>{children}</>;
  }

  return (
    <ThemeContext.Provider
      value={{
        theme,
        setTheme,
        themeId,
        isDark: theme.mode === "dark",
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
}
