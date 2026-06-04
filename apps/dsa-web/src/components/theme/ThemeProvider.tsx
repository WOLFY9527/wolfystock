import type React from 'react';
import {
  useEffect,
} from 'react';
import { ThemeProvider as NextThemesProvider, useTheme } from 'next-themes';

type ThemeStylePreset = 'spacex';
type RootThemeName = 'spacex';

type ThemeProviderProps = {
  children: React.ReactNode;
};

const THEME_STYLE_STORAGE_KEY = 'dsa-theme-style';
const DEFAULT_THEME_STYLE: ThemeStylePreset = 'spacex';

function toRootThemeName(style: ThemeStylePreset): RootThemeName {
  return style;
}

const ThemeStyleController: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { setTheme } = useTheme();
  const themeStyle = DEFAULT_THEME_STYLE;

  useEffect(() => {
    if (typeof document === 'undefined') {
      return;
    }

    const rootTheme = toRootThemeName(themeStyle);
    const colorMode = 'dark';
    document.documentElement.classList.remove('light');
    document.documentElement.classList.add('dark');
    document.documentElement.dataset.theme = rootTheme;
    document.body.dataset.theme = rootTheme;
    document.documentElement.dataset.colorMode = colorMode;
    document.body.dataset.colorMode = colorMode;
    window.localStorage.setItem(THEME_STYLE_STORAGE_KEY, themeStyle);
    void setTheme(colorMode);
  }, [setTheme, themeStyle]);

  return <>{children}</>;
};

export const ThemeProvider: React.FC<ThemeProviderProps> = ({ children }) => {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem={false}
      disableTransitionOnChange
    >
      <ThemeStyleController>{children}</ThemeStyleController>
    </NextThemesProvider>
  );
};
