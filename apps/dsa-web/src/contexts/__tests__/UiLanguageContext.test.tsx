import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { UiLanguageProvider, useI18n } from '../UiLanguageContext';
import {
  activateLocaleCatalog,
  loadLocaleCatalog,
  UI_LANGUAGE_STORAGE_KEY,
} from '../../i18n/core';

function LanguageProbe() {
  const { language, setLanguage, t, toggleLanguage } = useI18n();

  return (
    <>
      <output data-testid="language">{language}</output>
      <output data-testid="label">{t('nav.home')}</output>
      <button type="button" onClick={toggleLanguage}>toggle</button>
      <button type="button" onClick={() => setLanguage(language)}>select active</button>
    </>
  );
}

describe('UiLanguageProvider', () => {
  beforeEach(async () => {
    window.history.replaceState({}, '', '/zh/guest');
    window.localStorage.clear();
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'zh');
    const zhCatalog = await loadLocaleCatalog('zh');
    activateLocaleCatalog('zh', zhCatalog);
  });

  it('waits for the target catalog before committing a context-only language switch', async () => {
    render(
      <UiLanguageProvider>
        <LanguageProbe />
      </UiLanguageProvider>,
    );

    expect(screen.getByTestId('label')).toHaveTextContent('首页');

    fireEvent.click(screen.getByRole('button', { name: 'toggle' }));

    await waitFor(() => expect(screen.getByTestId('language')).toHaveTextContent('en'));
    expect(screen.getByTestId('label')).toHaveTextContent('Home');
    expect(window.location.pathname).toBe('/zh/guest');
    await waitFor(() => expect(window.localStorage.getItem(UI_LANGUAGE_STORAGE_KEY)).toBe('en'));
    expect(document.documentElement.lang).toBe('en');
  });

  it('keeps an already-active context-only locale idempotent', async () => {
    render(
      <UiLanguageProvider>
        <LanguageProbe />
      </UiLanguageProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'select active' }));
    await Promise.resolve();

    expect(screen.getByTestId('language')).toHaveTextContent('zh');
    expect(screen.getByTestId('label')).toHaveTextContent('首页');
    expect(window.location.pathname).toBe('/zh/guest');
    expect(window.localStorage.getItem(UI_LANGUAGE_STORAGE_KEY)).toBe('zh');
    expect(document.documentElement.lang).toBe('zh');
  });
});
