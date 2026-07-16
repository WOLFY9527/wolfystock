import { describe, expect, it } from 'vitest';
import * as i18n from '../core';

type LocaleLoaderApi = {
  loadLocaleCatalog?: (language: 'zh' | 'en') => Promise<unknown>;
  activateLocaleCatalog?: (language: 'zh' | 'en', catalog: unknown) => void;
  createCachedLocaleCatalogLoader?: (
    loaders: Record<'zh' | 'en', () => Promise<unknown>>,
  ) => (language: 'zh' | 'en') => Promise<unknown>;
};

describe('locale catalog loading', () => {
  it('keeps existing synchronous test owners localized without a root bootstrap', () => {
    expect(i18n.translate('en', 'nav.home')).toBe('Home');
  });

  it('loads and activates only the requested catalog for synchronous translation', async () => {
    const loadLocaleCatalog = (i18n as LocaleLoaderApi).loadLocaleCatalog;
    const activateLocaleCatalog = (i18n as LocaleLoaderApi).activateLocaleCatalog;

    expect(loadLocaleCatalog).toBeTypeOf('function');
    expect(activateLocaleCatalog).toBeTypeOf('function');
    if (!loadLocaleCatalog || !activateLocaleCatalog) {
      return;
    }

    const catalog = await loadLocaleCatalog('zh');
    activateLocaleCatalog('zh', catalog);

    expect(i18n.translate('zh', 'nav.home')).toBe('首页');
    expect(i18n.getActiveUiLanguage()).toBe('zh');
  });

  it('retries a locale bundle after a transient loading failure', async () => {
    const createCachedLocaleCatalogLoader = (i18n as LocaleLoaderApi).createCachedLocaleCatalogLoader;

    expect(createCachedLocaleCatalogLoader).toBeTypeOf('function');
    if (!createCachedLocaleCatalogLoader) {
      return;
    }

    const expectedCatalog = { nav: { home: 'Home' } };
    let englishAttempts = 0;
    const loadCatalog = createCachedLocaleCatalogLoader({
      zh: async () => ({ nav: { home: '首页' } }),
      en: async () => {
        englishAttempts += 1;
        if (englishAttempts === 1) {
          throw new Error('transient locale chunk failure');
        }
        return expectedCatalog;
      },
    });

    await expect(loadCatalog('en')).rejects.toThrow('transient locale chunk failure');
    await expect(loadCatalog('en')).resolves.toBe(expectedCatalog);
    expect(englishAttempts).toBe(2);
  });
});
