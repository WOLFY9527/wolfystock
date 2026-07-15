import { describe, expect, it } from 'vitest';
import * as i18n from '../core';

type LocaleLoaderApi = {
  loadLocaleCatalog?: (language: 'zh' | 'en') => Promise<unknown>;
  activateLocaleCatalog?: (language: 'zh' | 'en', catalog: unknown) => void;
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
});
