import type { LocaleCatalog } from './catalogs/types';

export type UiLanguage = 'zh' | 'en';

export const UI_LANGUAGE_STORAGE_KEY = 'dsa-ui-language';

type TranslateVars = Record<string, string | number | undefined>;
type CatalogLoader = () => Promise<LocaleCatalog>;

const catalogLoaders = {
  zh: () => import('./catalogs/zh').then((module) => module.zhCatalog),
  en: () => import('./catalogs/en').then((module) => module.enCatalog),
} satisfies Record<UiLanguage, CatalogLoader>;

const testCatalogs: Record<UiLanguage, LocaleCatalog> | null = import.meta.env.MODE === 'test'
  ? {
    zh: (await import('./catalogs/zh')).zhCatalog,
    en: (await import('./catalogs/en')).enCatalog,
  }
  : null;

let activeLanguage: UiLanguage | null = null;
let activeCatalog: LocaleCatalog | null = null;

export function normalizeUiLanguage(value?: string | null): UiLanguage {
  return value === 'en' ? 'en' : 'zh';
}

function getByPath(target: Record<string, unknown>, path: string): string | undefined {
  return path.split('.').reduce<unknown>((current, key) => {
    if (current && typeof current === 'object') {
      return (current as Record<string, unknown>)[key];
    }
    return undefined;
  }, target) as string | undefined;
}

function interpolate(template: string, vars?: TranslateVars): string {
  if (!vars) {
    return template;
  }
  return template.replace(/\{(\w+)\}/g, (_, key: string) => String(vars[key] ?? ''));
}

export function getStoredUiLanguage(): UiLanguage {
  if (typeof window === 'undefined') {
    return 'zh';
  }
  return normalizeUiLanguage(window.localStorage.getItem(UI_LANGUAGE_STORAGE_KEY));
}

export function setStoredUiLanguage(language: UiLanguage): void {
  if (typeof window === 'undefined') {
    return;
  }
  window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, language);
}

export function createCachedLocaleCatalogLoader(loaders: Record<UiLanguage, CatalogLoader>) {
  const loadedCatalogs = new Map<UiLanguage, Promise<LocaleCatalog>>();

  return (language: UiLanguage): Promise<LocaleCatalog> => {
    const normalized = normalizeUiLanguage(language);
    const existing = loadedCatalogs.get(normalized);
    if (existing) {
      return existing;
    }

    const catalog = loaders[normalized]().catch((error: unknown) => {
      if (loadedCatalogs.get(normalized) === catalog) {
        loadedCatalogs.delete(normalized);
      }
      throw error;
    });
    loadedCatalogs.set(normalized, catalog);
    return catalog;
  };
}

export const loadLocaleCatalog = createCachedLocaleCatalogLoader(catalogLoaders);

export function activateLocaleCatalog(language: UiLanguage, catalog: LocaleCatalog): void {
  activeLanguage = normalizeUiLanguage(language);
  activeCatalog = catalog;
}

export function getActiveUiLanguage(): UiLanguage | null {
  return activeLanguage;
}

export function translate(language: UiLanguage, key: string, vars?: TranslateVars): string {
  const localized = activeLanguage === language && activeCatalog
    ? getByPath(activeCatalog as Record<string, unknown>, key)
    : testCatalogs
      ? getByPath(testCatalogs[language] as Record<string, unknown>, key)
      : undefined;
  return interpolate(localized ?? key, vars);
}

export function translateForCurrentLanguage(key: string, vars?: TranslateVars): string {
  return translate(activeLanguage ?? getStoredUiLanguage(), key, vars);
}
