'use client';

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { Monitor, Moon, Sun } from 'lucide-react';

export type ColorTheme = 'light' | 'dark' | 'system';

const STORAGE_KEY = 'progear-color-theme';
const THEMES: { value: ColorTheme; label: string; icon: typeof Sun }[] = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'system', label: 'System', icon: Monitor },
];

const ThemeContext = createContext<{
  theme: ColorTheme;
  setTheme: (theme: ColorTheme) => void;
} | null>(null);

function isColorTheme(value: string | null): value is ColorTheme {
  return value === 'light' || value === 'dark' || value === 'system';
}

function applyTheme(theme: ColorTheme) {
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const isDark = theme === 'dark' || (theme === 'system' && prefersDark);
  document.documentElement.classList.toggle('dark', isDark);
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = isDark ? 'dark' : 'light';
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ColorTheme>('light');

  useEffect(() => {
    let storedTheme: string | null = null;
    try {
      storedTheme = window.localStorage.getItem(STORAGE_KEY);
    } catch {
      // Light remains the explicit first-visit default.
    }
    const initialTheme = isColorTheme(storedTheme) ? storedTheme : 'light';
    setThemeState(initialTheme);
    applyTheme(initialTheme);
  }, []);

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const onSystemThemeChange = () => {
      if (theme === 'system') applyTheme('system');
    };
    media.addEventListener('change', onSystemThemeChange);
    return () => media.removeEventListener('change', onSystemThemeChange);
  }, [theme]);

  const setTheme = useCallback((nextTheme: ColorTheme) => {
    try {
      window.localStorage.setItem(STORAGE_KEY, nextTheme);
    } catch {
      // Theme still applies for the current page when storage is unavailable.
    }
    setThemeState(nextTheme);
    applyTheme(nextTheme);
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function ThemeSelector({ iconOnly = false }: { iconOnly?: boolean }) {
  const context = useContext(ThemeContext);
  if (!context) return null;

  return (
    <div
      className="flex items-center gap-1 rounded-xl border border-slate-200 bg-white/95 p-1.5 shadow-sm backdrop-blur dark:border-slate-700 dark:bg-slate-900/95"
      role="group"
      aria-label="Color theme"
    >
      {THEMES.map(({ value, label, icon: Icon }) => {
        const active = context.theme === value;
        return (
          <button
            key={value}
            type="button"
            aria-pressed={active}
            aria-label={`${label} theme`}
            title={`${label} theme`}
            onClick={() => context.setTheme(value)}
            className={`flex items-center gap-1.5 rounded-lg text-xs font-medium transition ${iconOnly ? 'p-2' : 'px-2.5 py-2'} ${
              active
                ? 'bg-slate-900 text-white shadow-sm dark:bg-white dark:text-slate-900'
                : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
            }`}
          >
            <Icon className="h-3.5 w-3.5" />
            <span className={iconOnly ? 'sr-only' : 'hidden sm:inline'}>{label}</span>
          </button>
        );
      })}
    </div>
  );
}
