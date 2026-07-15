/* eslint-disable react-refresh/only-export-components */
import type React from 'react';
import { createContext, use, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  activateLocaleCatalog,
  getActiveUiLanguage,
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

type RouteLanguageNavigator = (language: UiLanguage) => void;

type UiLanguageRouteSyncValue = {
  registerRouteLanguageNavigator: (navigator: RouteLanguageNavigator) => () => void;
  syncLanguageFromRoute: (language: UiLanguage) => Promise<boolean>;
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

const defaultLanguage = resolveInitialLanguage();

const defaultContextValue: UiLanguageContextValue = {
  language: defaultLanguage,
  setLanguage: () => undefined,
  toggleLanguage: () => undefined,
  t: (key, vars) => translate(defaultLanguage, key, vars),
};

const UiLanguageContext = createContext<UiLanguageContextValue>(defaultContextValue);

const UiLanguageRouteSyncContext = createContext<UiLanguageRouteSyncValue | null>(null);

export const UiLanguageProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [language, setLanguageState] = useState<UiLanguage>(() => resolveInitialLanguage());
  const currentLanguage = useRef(language);
  const latestLanguageRequest = useRef(0);
  const routeLanguageNavigator = useRef<RouteLanguageNavigator | null>(null);

  useEffect(() => {
    currentLanguage.current = language;
    setStoredUiLanguage(language);
    document.documentElement.lang = normalizeUiLanguage(language);
  }, [language]);

  const commitLanguage = useCallback(async (nextLanguage: UiLanguage): Promise<boolean> => {
    const normalized = normalizeUiLanguage(nextLanguage);
    const requestId = latestLanguageRequest.current + 1;
    latestLanguageRequest.current = requestId;

    if (currentLanguage.current === normalized && getActiveUiLanguage() === normalized) {
      return true;
    }

    let catalog;
    try {
      catalog = await loadLocaleCatalog(normalized);
    } catch {
      return false;
    }
    if (latestLanguageRequest.current !== requestId) {
      return false;
    }

    activateLocaleCatalog(normalized, catalog);
    currentLanguage.current = normalized;
    setLanguageState(normalized);
    return true;
  }, []);

  const registerRouteLanguageNavigator = useCallback((navigator: RouteLanguageNavigator) => {
    routeLanguageNavigator.current = navigator;
    return () => {
      if (routeLanguageNavigator.current === navigator) {
        routeLanguageNavigator.current = null;
      }
    };
  }, []);

  const setLanguage = useCallback((nextLanguage: UiLanguage) => {
    const normalized = normalizeUiLanguage(nextLanguage);
    const navigateToLanguage = routeLanguageNavigator.current;
    if (navigateToLanguage) {
      void commitLanguage(normalized).then((committed) => {
        if (committed) {
          navigateToLanguage(normalized);
        }
      });
      return;
    }
    void commitLanguage(normalized);
  }, [commitLanguage]);

  const toggleLanguage = useCallback(() => {
    setLanguage(language === 'zh' ? 'en' : 'zh');
  }, [language, setLanguage]);

  const t = (key: string, vars?: TranslateVars) => translate(language, key, vars);

  const value: UiLanguageContextValue = {
    language,
    setLanguage,
    toggleLanguage,
    t,
  };

  const routeSyncValue = useMemo<UiLanguageRouteSyncValue>(() => ({
    registerRouteLanguageNavigator,
    syncLanguageFromRoute: commitLanguage,
  }), [commitLanguage, registerRouteLanguageNavigator]);

  return (
    <UiLanguageContext.Provider value={value}>
      <UiLanguageRouteSyncContext.Provider value={routeSyncValue}>
        {children}
      </UiLanguageRouteSyncContext.Provider>
    </UiLanguageContext.Provider>
  );
};

export function useI18n(): UiLanguageContextValue {
  return use(UiLanguageContext);
}

export const UiLanguageRouteSynchronizer: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const routeSync = use(UiLanguageRouteSyncContext);
  const routeLanguage = parseLocaleFromPathname(location.pathname);

  if (!routeSync) {
    throw new Error('UiLanguageRouteSynchronizer must be rendered inside UiLanguageProvider');
  }

  const navigateToLanguage = useCallback((nextLanguage: UiLanguage) => {
    const currentPath = `${location.pathname}${location.search}${location.hash}`;
    const nextPath = shouldLocalizePath(location.pathname)
      ? buildLocalizedPath(currentPath, nextLanguage)
      : currentPath;

    if (nextPath === currentPath) {
      void routeSync.syncLanguageFromRoute(nextLanguage);
      return;
    }

    navigate(nextPath, { replace: true });
  }, [location.hash, location.pathname, location.search, navigate, routeSync]);

  useLayoutEffect(() => routeSync.registerRouteLanguageNavigator(navigateToLanguage), [navigateToLanguage, routeSync]);

  useEffect(() => {
    if (routeLanguage) {
      void routeSync.syncLanguageFromRoute(routeLanguage);
    }
  }, [routeLanguage, routeSync]);

  return null;
};
