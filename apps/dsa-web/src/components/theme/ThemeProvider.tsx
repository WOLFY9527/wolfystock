import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { ThemeProvider as NextThemesProvider, useTheme } from 'next-themes';
import {
  DEFAULT_THEME_MODE,
  ThemeStyleContext,
  type ThemeColorMode,
  type ThemeStyleContextValue,
  type ThemeStylePreset,
  getStoredThemeMode,
  getStoredThemeStyle,
  normalizeThemeMode,
  normalizeThemeStyle,
  THEME_MODE_STORAGE_KEY,
  THEME_STYLE_STORAGE_KEY,
  useThemeStyle,
} from './themeState';

type ThemeProviderProps = {
  children: React.ReactNode;
};

const ThemeStyleController: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { setTheme } = useTheme();
  const { colorMode, themeStyle } = useThemeStyle();

  useEffect(() => {
    if (typeof document === 'undefined') {
      return;
    }

    const normalizedThemeStyle = normalizeThemeStyle(themeStyle);
    const normalizedColorMode = normalizeThemeMode(colorMode);
    document.documentElement.classList.remove('light', 'dark');
    document.documentElement.classList.add(normalizedColorMode);
    document.documentElement.dataset.theme = normalizedColorMode;
    document.body.dataset.theme = normalizedColorMode;
    document.documentElement.dataset.themeStyle = normalizedThemeStyle;
    document.body.dataset.themeStyle = normalizedThemeStyle;
    document.documentElement.dataset.colorMode = normalizedColorMode;
    document.body.dataset.colorMode = normalizedColorMode;
    window.localStorage.setItem(THEME_STYLE_STORAGE_KEY, normalizedThemeStyle);
    window.localStorage.setItem(THEME_MODE_STORAGE_KEY, normalizedColorMode);
    void setTheme(normalizedColorMode);
  }, [colorMode, setTheme, themeStyle]);

  return <>{children}</>;
};

export const ThemeProvider: React.FC<ThemeProviderProps> = ({ children }) => {
  const [themeStyle, setThemeStyleState] = useState<ThemeStylePreset>(() => getStoredThemeStyle());
  const [colorMode, setColorModeState] = useState<ThemeColorMode>(() => getStoredThemeMode());

  const value = useMemo<ThemeStyleContextValue>(() => ({
    colorMode,
    setColorMode: (mode) => setColorModeState(normalizeThemeMode(mode)),
    themeStyle,
    setThemeStyle: (style) => setThemeStyleState(normalizeThemeStyle(style)),
  }), [colorMode, themeStyle]);

  return (
    <ThemeStyleContext.Provider value={value}>
      <NextThemesProvider
        attribute="class"
        defaultTheme={DEFAULT_THEME_MODE}
        storageKey={THEME_MODE_STORAGE_KEY}
        enableSystem={false}
        disableTransitionOnChange
      >
        <ThemeStyleController>{children}</ThemeStyleController>
      </NextThemesProvider>
    </ThemeStyleContext.Provider>
  );
};
