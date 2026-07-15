import { beforeEach, describe, expect, it } from 'vitest';
import {
  getActiveUiLanguage,
  UI_LANGUAGE_STORAGE_KEY,
  translate,
} from '../core';
import {
  initializeUiLanguageForFirstRender,
  renderAfterI18nInitialization,
} from '../bootstrap';

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((complete) => {
    resolve = complete;
  });
  return { promise, resolve };
}

describe('i18n root bootstrap', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/en/guest');
    window.localStorage.clear();
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'zh');
    document.documentElement.lang = '';
  });

  it('resolves the route locale and activates it before the first render', async () => {
    await initializeUiLanguageForFirstRender();

    expect(document.documentElement.lang).toBe('en');
    expect(translate('en', 'nav.home')).toBe('Home');
    expect(getActiveUiLanguage()).toBe('en');
  });

  it('keeps the Chinese route locale ahead of persisted English before the first render', async () => {
    window.history.replaceState({}, '', '/zh/guest');
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'en');

    await initializeUiLanguageForFirstRender();

    expect(document.documentElement.lang).toBe('zh');
    expect(translate('zh', 'nav.home')).toBe('首页');
    expect(getActiveUiLanguage()).toBe('zh');
  });

  it('does not call the root renderer until i18n initialization settles', async () => {
    const initialization = createDeferred<'zh' | 'en'>();
    let rendered = false;
    const boot = renderAfterI18nInitialization(
      () => {
        rendered = true;
      },
      () => initialization.promise,
    );

    await Promise.resolve();
    expect(rendered).toBe(false);

    initialization.resolve('en');
    await boot;

    expect(rendered).toBe(true);
  });
});
