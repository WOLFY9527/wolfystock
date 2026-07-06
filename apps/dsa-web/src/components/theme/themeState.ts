import { createContext, useContext } from 'react';

export type ThemeStylePreset = 'paper';
export type ThemeColorMode = 'light' | 'dark';

export type ThemeStyleContextValue = {
  colorMode: ThemeColorMode;
  setColorMode: (mode: ThemeColorMode) => void;
  themeStyle: ThemeStylePreset;
  setThemeStyle: (style: ThemeStylePreset) => void;
};

export const THEME_STYLE_STORAGE_KEY = 'dsa-theme-style';
export const THEME_MODE_STORAGE_KEY = 'dsa-theme-mode';
export const DEFAULT_THEME_STYLE: ThemeStylePreset = 'paper';
export const DEFAULT_THEME_MODE: ThemeColorMode = 'light';

export function normalizeThemeStyle(value?: string | null): ThemeStylePreset {
  if (value === 'paper' || value === 'spacex') {
    return DEFAULT_THEME_STYLE;
  }
  return DEFAULT_THEME_STYLE;
}

export function normalizeThemeMode(value?: string | null): ThemeColorMode {
  return value === 'light' || value === 'dark' ? value : DEFAULT_THEME_MODE;
}

export function getStoredThemeStyle(): ThemeStylePreset {
  if (typeof window === 'undefined') {
    return DEFAULT_THEME_STYLE;
  }

  return normalizeThemeStyle(window.localStorage.getItem(THEME_STYLE_STORAGE_KEY));
}

export function getStoredThemeMode(): ThemeColorMode {
  if (typeof window === 'undefined') {
    return DEFAULT_THEME_MODE;
  }

  return normalizeThemeMode(window.localStorage.getItem(THEME_MODE_STORAGE_KEY));
}

const defaultThemeStyleContext: ThemeStyleContextValue = {
  colorMode: DEFAULT_THEME_MODE,
  setColorMode: () => undefined,
  themeStyle: DEFAULT_THEME_STYLE,
  setThemeStyle: () => undefined,
};

export const ThemeStyleContext = createContext<ThemeStyleContextValue>(defaultThemeStyleContext);

export function useThemeStyle(): ThemeStyleContextValue {
  return useContext(ThemeStyleContext);
}
