/* eslint-disable react-refresh/only-export-components */
import type React from 'react';
import { createContext, use, useCallback, useEffect, useRef, useState } from 'react';
import {
  activateLocaleCatalog,
  getStoredUiLanguage,
  loadLocaleCatalog,
  normalizeUiLanguage,
  setStoredUiLanguage,
  translate,
  type UiLanguage,
} from '../i18n/core';
import { buildLocalizedPath, parseLocaleFromPathname, shouldLocalizePath } from '../utils/localeRouting';

type TranslateVars = Record<string, string | number | undefined>;

type UiLanguageContextValue = {
  language: UiLanguage;
  setLanguage: (language: UiLanguage) => void;
  toggleLanguage: () => void;
  t: (key: string, vars?: TranslateVars) => string;
};

function resolveInitialLanguage(): UiLanguage {
  if (typeof window !== 'undefined') {
    const routeLanguage = parseLocaleFromPathname(window.location.pathname);
    if (routeLanguage) {
      return routeLanguage;
    }
  }
  return getStoredUiLanguage();
}

function syncCurrentPathToLanguage(nextLanguage: UiLanguage): void {
  if (typeof window === 'undefined' || !shouldLocalizePath(window.location.pathname)) {
    return;
  }
  const currentPath = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  const nextPath = buildLocalizedPath(currentPath, nextLanguage);
  if (nextPath === currentPath) {
    return;
  }
  window.history.replaceState(window.history.state, '', nextPath);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

const defaultLanguage = resolveInitialLanguage();

const defaultContextValue: UiLanguageContextValue = {
  language: defaultLanguage,
  setLanguage: () => undefined,
  toggleLanguage: () => undefined,
  t: (key, vars) => translate(defaultLanguage, key, vars),
};

const UiLanguageContext = createContext<UiLanguageContextValue>(defaultContextValue);

export const UiLanguageProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [language, setLanguageState] = useState<UiLanguage>(() => resolveInitialLanguage());
  const latestLanguageRequest = useRef(0);

  useEffect(() => {
    setStoredUiLanguage(language);
    document.documentElement.lang = normalizeUiLanguage(language);
  }, [language]);

  const commitLanguage = useCallback(async (nextLanguage: UiLanguage) => {
    const normalized = normalizeUiLanguage(nextLanguage);
    const requestId = latestLanguageRequest.current + 1;
    latestLanguageRequest.current = requestId;

    const catalog = await loadLocaleCatalog(normalized);
    if (latestLanguageRequest.current !== requestId) {
      return;
    }

    activateLocaleCatalog(normalized, catalog);
    syncCurrentPathToLanguage(normalized);
    setLanguageState(normalized);
  }, []);

  const setLanguage = useCallback((nextLanguage: UiLanguage) => {
    void commitLanguage(nextLanguage);
  }, [commitLanguage]);

  const toggleLanguage = useCallback(() => {
    void commitLanguage(language === 'zh' ? 'en' : 'zh');
  }, [commitLanguage, language]);

  const t = (key: string, vars?: TranslateVars) => translate(language, key, vars);

  const value: UiLanguageContextValue = {
    language,
    setLanguage,
    toggleLanguage,
    t,
  };

  return (
    <UiLanguageContext.Provider value={value}>
      {children}
    </UiLanguageContext.Provider>
  );
};

export function useI18n(): UiLanguageContextValue {
  return use(UiLanguageContext);
}
