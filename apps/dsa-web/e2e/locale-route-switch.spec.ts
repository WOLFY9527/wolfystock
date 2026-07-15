import { expect, type Page } from '@playwright/test';
import { expect as appExpect, test as appTest } from './fixtures/appSmoke';

type LocaleState = {
  language: string;
  locale: string | null;
  path: string;
};

type RouteTraceEntry = {
  type: 'push' | 'replace';
  url: string;
};

declare global {
  interface Window {
    __localeRouteTrace?: RouteTraceEntry[];
  }
}

async function readLocaleState(page: Page): Promise<LocaleState> {
  return page.evaluate(() => ({
    language: document.documentElement.lang,
    locale: window.localStorage.getItem('dsa-ui-language'),
    path: `${window.location.pathname}${window.location.search}${window.location.hash}`,
  }));
}

async function settleLocale(page: Page, expected: LocaleState) {
  await expect.poll(() => readLocaleState(page)).toEqual(expected);
  await page.evaluate(async () => {
    await Promise.resolve();
    await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
    await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
  });
  await expect(readLocaleState(page)).resolves.toEqual(expected);
}

async function switchLanguage(page: Page, expected: LocaleState) {
  const toggle = page.getByRole('button', { name: /切换语言|Switch language/ });
  if (!await toggle.isVisible()) {
    await page.getByRole('button', { name: /打开导航菜单|Open navigation/ }).click();
  }
  await toggle.click();
  await settleLocale(page, expected);
}

appTest.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.__localeRouteTrace = [];
    const replaceState = window.history.replaceState.bind(window.history);
    window.history.replaceState = (state, title, url) => {
      window.__localeRouteTrace?.push({ type: 'replace', url: String(url) });
      return replaceState(state, title, url);
    };
    const pushState = window.history.pushState.bind(window.history);
    window.history.pushState = (state, title, url) => {
      window.__localeRouteTrace?.push({ type: 'push', url: String(url) });
      return pushState(state, title, url);
    };
  });
});

appTest('keeps a guest Chinese-to-English language switch stable after route effects settle', async ({ page }) => {
  await page.goto('/zh/guest');
  await appExpect(page.getByTestId('guest-home-clean-search')).toBeVisible();
  await switchLanguage(page, {
    language: 'en',
    locale: 'en',
    path: '/en/guest',
  });
  await appExpect(page.getByTestId('guest-home-clean-search')).toContainText(/Stock Research Workspace|Guest Research Console/);
});

appTest('keeps bidirectional guest switching, route suffixes, history, chunks, and visible copy aligned', async ({ page }) => {
  const requestedLocaleChunks: string[] = [];
  const consoleErrors: string[] = [];
  page.on('response', (response) => {
    const url = response.url();
    if (/\/assets\/(?:zh|en)-[^/]+\.js$/.test(url)) {
      requestedLocaleChunks.push(url);
    }
  });
  page.on('console', (message) => {
    if (message.type() === 'error') {
      consoleErrors.push(message.text());
    }
  });

  const initialPath = '/zh/guest?source=locale-switch#controls';
  const englishPath = '/en/guest?source=locale-switch#controls';
  await page.goto(initialPath);
  await appExpect(page.getByTestId('guest-home-clean-search')).toBeVisible();
  await settleLocale(page, { language: 'zh', locale: 'zh', path: initialPath });
  await expect.poll(() => requestedLocaleChunks.some((url) => /\/assets\/zh-[^/]+\.js$/.test(url))).toBe(true);
  expect(requestedLocaleChunks.some((url) => /\/assets\/en-[^/]+\.js$/.test(url))).toBe(false);
  await appExpect(page.getByRole('heading', { name: 'WolfyStock 研究控制台' })).toBeVisible();

  await switchLanguage(page, { language: 'en', locale: 'en', path: englishPath });
  await appExpect(page.getByRole('heading', { name: 'WolfyStock Research Console' })).toBeVisible();
  await expect.poll(() => requestedLocaleChunks.some((url) => /\/assets\/en-[^/]+\.js$/.test(url))).toBe(true);

  await switchLanguage(page, { language: 'zh', locale: 'zh', path: initialPath });
  await appExpect(page.getByRole('heading', { name: 'WolfyStock 研究控制台' })).toBeVisible();

  for (let index = 0; index < 10; index += 1) {
    const language = index % 2 === 0 ? 'en' : 'zh';
    await switchLanguage(page, {
      language,
      locale: language,
      path: language === 'en' ? englishPath : initialPath,
    });
  }

  expect(await page.evaluate(() => window.__localeRouteTrace)).toEqual(
    expect.arrayContaining([
      { type: 'replace', url: englishPath },
      { type: 'replace', url: initialPath },
    ]),
  );

  await switchLanguage(page, { language: 'en', locale: 'en', path: englishPath });
  const historyPath = '/zh/guest?source=locale-history#back-forward';
  await page.goto(historyPath);
  await appExpect(page.getByTestId('guest-home-clean-search')).toBeVisible();
  await settleLocale(page, { language: 'zh', locale: 'zh', path: historyPath });

  await page.goBack();
  await appExpect(page.getByTestId('guest-home-clean-search')).toBeVisible();
  await settleLocale(page, { language: 'en', locale: 'en', path: englishPath });

  await page.goForward();
  await appExpect(page.getByTestId('guest-home-clean-search')).toBeVisible();
  await settleLocale(page, { language: 'zh', locale: 'zh', path: historyPath });

  expect(consoleErrors).toEqual([]);
});
