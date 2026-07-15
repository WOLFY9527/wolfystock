import {
  activateLocaleCatalog,
  getStoredUiLanguage,
  loadLocaleCatalog,
  type UiLanguage,
} from './core';
import { parseLocaleFromPathname } from '../utils/localeRouting';

export function resolveInitialUiLanguage(): UiLanguage {
  if (typeof window !== 'undefined') {
    const routeLanguage = parseLocaleFromPathname(window.location.pathname);
    if (routeLanguage) {
      return routeLanguage;
    }
  }
  return getStoredUiLanguage();
}

export async function initializeUiLanguageForFirstRender(): Promise<UiLanguage> {
  const language = resolveInitialUiLanguage();
  const catalog = await loadLocaleCatalog(language);
  activateLocaleCatalog(language, catalog);

  if (typeof document !== 'undefined') {
    document.documentElement.lang = language;
  }

  return language;
}

export async function renderAfterI18nInitialization(
  render: () => void,
  initialize = initializeUiLanguageForFirstRender,
): Promise<void> {
  await initialize();
  render();
}
