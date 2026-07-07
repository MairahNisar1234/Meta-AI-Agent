"use client";

import {
  createContext, useContext, useEffect, useState, type ReactNode,
} from "react";

type Theme = "dark" | "light";
interface Ctx { theme: Theme; toggle: () => void; }

const ThemeCtx = createContext<Ctx>({ theme: "dark", toggle: () => {} });

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    const stored = localStorage.getItem("theme") as Theme | null;
    const init: Theme =
      stored ?? (window.matchMedia("(prefers-color-scheme:light)").matches ? "light" : "dark");
    setTheme(init);
    document.documentElement.setAttribute("data-theme", init);
  }, []);

  const toggle = () => {
    setTheme((prev) => {
      const next: Theme = prev === "dark" ? "light" : "dark";
      localStorage.setItem("theme", next);
      document.documentElement.setAttribute("data-theme", next);
      return next;
    });
  };

  return <ThemeCtx.Provider value={{ theme, toggle }}>{children}</ThemeCtx.Provider>;
}

export function useTheme() {
  return useContext(ThemeCtx);
}
