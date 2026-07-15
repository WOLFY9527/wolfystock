import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { StrictMode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { UiLanguageProvider, useI18n } from '../contexts/UiLanguageContext';
import {
  activateLocaleCatalog,
  UI_LANGUAGE_STORAGE_KEY,
} from '../i18n/core';
import { enCatalog } from '../i18n/catalogs/en';
import { zhCatalog } from '../i18n/catalogs/zh';

const { catalogLoaderMock, useAuthMock } = vi.hoisted(() => ({
  catalogLoaderMock: vi.fn(),
  useAuthMock: vi.fn(),
}));

vi.mock('../i18n/core', async () => {
  const actual = await vi.importActual<typeof import('../i18n/core')>('../i18n/core');
  return {
    ...actual,
    loadLocaleCatalog: catalogLoaderMock,
  };
});

vi.mock('../contexts/AuthContext', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
  useAuth: () => useAuthMock(),
}));

vi.mock('../components/common/BrandedLoadingScreen', () => ({
  BrandedLoadingScreen: () => null,
}));

vi.mock('../components/layout/Shell', async () => {
  const { Outlet } = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  const { useI18n: useActualI18n } = await vi.importActual<typeof import('../contexts/UiLanguageContext')>('../contexts/UiLanguageContext');

  function Shell() {
    const { language, t, toggleLanguage } = useActualI18n();

    return (
      <main>
        <output data-testid="active-language">{language}</output>
        <output data-testid="translated-home">{t('nav.home')}</output>
        <button type="button" onClick={toggleLanguage}>switch language</button>
        <Outlet />
      </main>
    );
  }

  return { Shell };
});

vi.mock('../pages/GuestHomePage', () => ({
  default: function GuestHomePageMock() {
    const { t } = useI18n();
    return <p data-testid="guest-copy">{t('nav.home')}</p>;
  },
}));

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((complete) => {
    resolve = complete;
  });
  return { promise, resolve };
}

function navigateBrowserRoute(path: string) {
  act(() => {
    window.history.pushState({}, '', path);
    window.dispatchEvent(new PopStateEvent('popstate'));
  });
}

describe('App locale routing', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/zh/guest');
    window.localStorage.clear();
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'zh');
    document.documentElement.lang = 'zh';
    activateLocaleCatalog('zh', zhCatalog);
    catalogLoaderMock.mockReset();
    catalogLoaderMock.mockImplementation((language: 'zh' | 'en') => Promise.resolve(language === 'en' ? enCatalog : zhCatalog));
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: false,
      isLoading: false,
      loadError: null,
      refreshStatus: vi.fn(),
      setupState: 'enabled',
    });
  });

  it('keeps a Chinese-to-English user switch after Router effects settle', async () => {
    render(
      <StrictMode>
        <UiLanguageProvider>
          <App />
        </UiLanguageProvider>
      </StrictMode>,
    );

    expect(await screen.findByTestId('guest-copy')).toHaveTextContent('首页');

    fireEvent.click(screen.getByRole('button', { name: 'switch language' }));

    await waitFor(() => expect(screen.getByTestId('active-language')).toHaveTextContent('en'));
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(window.location.pathname).toBe('/en/guest');
    expect(screen.getByTestId('active-language')).toHaveTextContent('en');
    expect(screen.getByTestId('translated-home')).toHaveTextContent('Home');
    expect(screen.getByTestId('guest-copy')).toHaveTextContent('Home');
    expect(window.localStorage.getItem(UI_LANGUAGE_STORAGE_KEY)).toBe('en');
    expect(document.documentElement.lang).toBe('en');
  });

  it('keeps an English-to-Chinese user switch after Router effects settle', async () => {
    window.history.replaceState({}, '', '/en/guest');
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'en');
    document.documentElement.lang = 'en';
    activateLocaleCatalog('en', enCatalog);

    render(
      <StrictMode>
        <UiLanguageProvider>
          <App />
        </UiLanguageProvider>
      </StrictMode>,
    );
    expect(await screen.findByTestId('guest-copy')).toHaveTextContent('Home');

    fireEvent.click(screen.getByRole('button', { name: 'switch language' }));

    await waitFor(() => expect(screen.getByTestId('active-language')).toHaveTextContent('zh'));
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(window.location.pathname).toBe('/zh/guest');
    expect(screen.getByTestId('translated-home')).toHaveTextContent('首页');
    expect(screen.getByTestId('guest-copy')).toHaveTextContent('首页');
    expect(window.localStorage.getItem(UI_LANGUAGE_STORAGE_KEY)).toBe('zh');
    expect(document.documentElement.lang).toBe('zh');
  });

  it.each([
    ['zh', '首页'],
    ['en', 'Home'],
  ] as const)('initializes direct /%s/guest routes with the matching active catalog', async (language, translatedHome) => {
    window.history.replaceState({}, '', `/${language}/guest`);
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, language === 'zh' ? 'en' : 'zh');
    document.documentElement.lang = language;
    activateLocaleCatalog(language, language === 'en' ? enCatalog : zhCatalog);

    render(
      <UiLanguageProvider>
        <App />
      </UiLanguageProvider>,
    );

    expect(await screen.findByTestId('guest-copy')).toHaveTextContent(translatedHome);
    expect(screen.getByTestId('active-language')).toHaveTextContent(language);
    expect(catalogLoaderMock).not.toHaveBeenCalled();
  });

  it('keeps the newer route locale when an older catalog request resolves afterward', async () => {
    const delayedEnglishCatalog = createDeferred<typeof enCatalog>();
    catalogLoaderMock.mockImplementation((language: 'zh' | 'en') => (
      language === 'en' ? delayedEnglishCatalog.promise : Promise.resolve(zhCatalog)
    ));

    render(
      <UiLanguageProvider>
        <App />
      </UiLanguageProvider>,
    );
    expect(await screen.findByTestId('guest-copy')).toHaveTextContent('首页');

    navigateBrowserRoute('/en/guest');
    await waitFor(() => expect(catalogLoaderMock).toHaveBeenCalledWith('en'));

    navigateBrowserRoute('/zh/guest');
    await act(async () => {
      delayedEnglishCatalog.resolve(enCatalog);
      await delayedEnglishCatalog.promise;
    });

    await act(async () => {
      await Promise.resolve();
    });
    expect(window.location.pathname).toBe('/zh/guest');
    expect(screen.getByTestId('active-language')).toHaveTextContent('zh');
    expect(screen.getByTestId('translated-home')).toHaveTextContent('首页');
    expect(document.documentElement.lang).toBe('zh');
    expect(window.localStorage.getItem(UI_LANGUAGE_STORAGE_KEY)).toBe('zh');
  });

  it('keeps the committed locale and route unchanged when a target catalog fails to load', async () => {
    catalogLoaderMock.mockImplementation((language: 'zh' | 'en') => (
      language === 'en' ? Promise.reject(new Error('English catalog failed')) : Promise.resolve(zhCatalog)
    ));

    render(
      <UiLanguageProvider>
        <App />
      </UiLanguageProvider>,
    );
    expect(await screen.findByTestId('guest-copy')).toHaveTextContent('首页');

    fireEvent.click(screen.getByRole('button', { name: 'switch language' }));
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(window.location.pathname).toBe('/zh/guest');
    expect(screen.getByTestId('active-language')).toHaveTextContent('zh');
    expect(screen.getByTestId('translated-home')).toHaveTextContent('首页');
    expect(document.documentElement.lang).toBe('zh');
    expect(window.localStorage.getItem(UI_LANGUAGE_STORAGE_KEY)).toBe('zh');
  });
});
