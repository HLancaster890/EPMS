"use client";

import { useTheme } from "@/components/layout/ThemeProvider";
import { themes } from "@/lib/theme";
import { useState, useRef, useEffect } from "react";

export function ThemeSwitcher({ minimal = false }: { minimal?: boolean }) {
  const { themeId, setTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const current = themes.find((t) => t.id === themeId);

  if (minimal) {
    return (
      <div className="relative" ref={ref}>
        <button
          onClick={() => setOpen(!open)}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-card-border bg-card text-sm hover:bg-table-row-hover transition-colors"
        >
          <span
            className="w-3 h-3 rounded-full"
            style={{ background: current?.colors.primary }}
          />
          <span className="text-xs text-muted">{current?.name}</span>
        </button>
        {open && (
          <div className="absolute right-0 top-full mt-1 w-56 rounded-xl border border-card-border bg-card shadow-2xl z-50 overflow-hidden">
            <div className="p-2">
              <p className="px-2 py-1 text-xs font-semibold text-muted uppercase tracking-wider">Theme</p>
              {themes.map((t) => (
                <button
                  key={t.id}
                  onClick={() => { setTheme(t.id); setOpen(false); }}
                  className={`w-full flex items-center gap-3 px-2 py-2 rounded-lg text-sm transition-colors ${
                    t.id === themeId ? "bg-primary/10 text-foreground" : "text-muted hover:bg-table-row-hover"
                  }`}
                >
                  <span
                    className="w-4 h-4 rounded-full flex-shrink-0"
                    style={{ background: t.colors.primary }}
                  />
                  <div className="text-left flex-1">
                    <p className="text-xs font-medium">{t.name}</p>
                    <p className="text-[10px] text-muted">{t.description}</p>
                  </div>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                    t.mode === "dark" ? "bg-white/10 text-white/60" : "bg-black/5 text-black/60"
                  }`}>
                    {t.mode}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-2 rounded-lg border border-card-border bg-card text-sm hover:bg-table-row-hover transition-colors w-full"
      >
        <span
          className="w-3 h-3 rounded-full"
          style={{ background: current?.colors.primary }}
        />
        <span>{current?.name}</span>
        <span className="ml-auto text-xs text-muted">{current?.mode}</span>
      </button>
      {open && (
        <div className="absolute left-0 top-full mt-1 w-full min-w-[220px] rounded-xl border border-card-border bg-card shadow-2xl z-50">
          <div className="p-2 space-y-0.5">
            <p className="px-2 py-1.5 text-xs font-semibold text-muted uppercase tracking-wider">Choose Theme</p>
            {themes.map((t) => (
              <button
                key={t.id}
                onClick={() => { setTheme(t.id); setOpen(false); }}
                className={`w-full flex items-center gap-3 px-2 py-2 rounded-lg text-sm transition-colors ${
                  t.id === themeId ? "bg-primary/10 text-foreground" : "text-muted hover:bg-table-row-hover"
                }`}
              >
                <span
                  className="w-4 h-4 rounded-full flex-shrink-0"
                  style={{ background: `linear-gradient(135deg, ${t.colors.primary}, ${t.colors.accent})` }}
                />
                <div className="text-left flex-1">
                  <p className="text-sm font-medium">{t.name}</p>
                  <p className="text-xs text-muted">{t.description}</p>
                </div>
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full capitalize ${
                  t.id === themeId ? "bg-primary/20 text-primary" :
                  t.mode === "dark" ? "bg-white/10 text-white/60" : "bg-black/5 text-black/60"
                }`}>
                  {t.mode}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
