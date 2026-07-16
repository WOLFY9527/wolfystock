import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { UiLanguageProvider, useI18n } from '../UiLanguageContext';
import {
  activateLocaleCatalog,
  loadLocaleCatalog,
  UI_LANGUAGE_STORAGE_KEY,
} from '../../i18n/core';
import { enCatalog } from '../../i18n/catalogs/en';
import { zhCatalog } from '../../i18n/catalogs/zh';

const loadLocaleCatalogMock = vi.hoisted(() => vi.fn());

vi.mock('../../i18n/core', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../i18n/core')>();
  return {
    ...actual,
    loadLocaleCatalog: loadLocaleCatalogMock,
  };
});

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
    loadLocaleCatalogMock.mockReset();
    loadLocaleCatalogMock.mockImplementation(async (language: 'zh' | 'en') => (
      language === 'en' ? enCatalog : zhCatalog
    ));
    const loadedZhCatalog = await loadLocaleCatalog('zh');
    activateLocaleCatalog('zh', loadedZhCatalog);
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

  it('keeps the active locale when the target bundle fails to load', async () => {
    loadLocaleCatalogMock.mockRejectedValueOnce(new Error('locale chunk unavailable'));

    render(
      <UiLanguageProvider>
        <LanguageProbe />
      </UiLanguageProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'toggle' }));

    await waitFor(() => expect(loadLocaleCatalogMock).toHaveBeenCalledWith('en'));
    expect(screen.getByTestId('language')).toHaveTextContent('zh');
    expect(screen.getByTestId('label')).toHaveTextContent('首页');
    expect(window.localStorage.getItem(UI_LANGUAGE_STORAGE_KEY)).toBe('zh');
    expect(document.documentElement.lang).toBe('zh');
  });
});
