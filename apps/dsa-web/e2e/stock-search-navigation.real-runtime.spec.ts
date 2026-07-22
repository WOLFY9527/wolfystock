import { expect, test } from '@playwright/test';

type RuntimeWindow = Window & {
  __t665RuntimePushes?: number;
  __t665RuntimeReplaces?: number;
  __t665RuntimeUnloads?: number;
};

test('qualifies stock search navigation against the managed runtime', async ({ page }) => {
  test.setTimeout(120_000);

  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  const failedRequests: string[] = [];
  const errorResponses: string[] = [];
  let documentNavigations = 0;
  let documentLoads = 0;

  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  page.on('pageerror', (error) => pageErrors.push(error.message));
  page.on('requestfailed', (request) => {
    failedRequests.push(`${request.method()} ${request.url()} :: ${request.failure()?.errorText || 'unknown'}`);
  });
  page.on('response', (response) => {
    if (response.status() >= 400) errorResponses.push(`${response.status()} ${response.url()}`);
  });
  page.on('framenavigated', (frame) => {
    if (frame === page.mainFrame()) documentNavigations += 1;
  });
  page.on('load', () => {
    documentLoads += 1;
  });

  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await expect(page.getByTestId('home-bento-omnibar-input')).toBeVisible({ timeout: 30_000 });
  await page.evaluate(() => {
    const trackedWindow = window as RuntimeWindow;
    trackedWindow.__t665RuntimePushes = 0;
    trackedWindow.__t665RuntimeReplaces = 0;
    trackedWindow.__t665RuntimeUnloads = 0;
    const originalPushState = window.history.pushState.bind(window.history);
    const originalReplaceState = window.history.replaceState.bind(window.history);
    window.history.pushState = function pushState(...args) {
      trackedWindow.__t665RuntimePushes = (trackedWindow.__t665RuntimePushes || 0) + 1;
      return originalPushState(...args);
    };
    window.history.replaceState = function replaceState(...args) {
      trackedWindow.__t665RuntimeReplaces = (trackedWindow.__t665RuntimeReplaces || 0) + 1;
      return originalReplaceState(...args);
    };
    window.addEventListener('beforeunload', () => {
      trackedWindow.__t665RuntimeUnloads = (trackedWindow.__t665RuntimeUnloads || 0) + 1;
    });
  });

  const homeInput = page.getByTestId('home-bento-omnibar-input');
  await homeInput.fill('AAPL');
  await homeInput.press('Enter');
  await expect(page).toHaveURL(/\/stocks\/AAPL\/structure-decision\?symbol=AAPL&source=manual$/);

  await page.goBack();
  await expect(page).toHaveURL(/\/$/);
  await homeInput.fill('AAPL');
  await page.getByTestId('home-bento-analyze-button').click();
  await expect(page).toHaveURL(/\/stocks\/AAPL\/structure-decision\?symbol=AAPL&source=manual$/);

  await page.goBack();
  await expect(page).toHaveURL(/\/$/);
  await homeInput.fill('600519');
  await page.getByTestId('home-bento-analyze-button').click();
  await expect(page).toHaveURL(/\/stocks\/600519\/structure-decision\?symbol=600519&source=manual$/);

  await page.goBack();
  await expect(page).toHaveURL(/\/$/);
  await homeInput.fill('0700.HK');
  await homeInput.press('Enter');
  await expect(page).toHaveURL(/\/stocks\/0700\.HK\/structure-decision\?symbol=0700\.HK&source=manual$/);

  await page.goBack();
  await expect(page).toHaveURL(/\/$/);
  await homeInput.fill('not-a-symbol!');
  await page.getByTestId('home-bento-analyze-button').click();
  await expect(page.getByText('请输入格式正确的股票代码')).toBeVisible();
  await expect(page).toHaveURL(/\/$/);
  await homeInput.fill('');
  await page.getByTestId('home-bento-analyze-button').click();
  await expect(page.getByText('请输入股票代码后再开始分析')).toBeVisible();
  await expect(page).toHaveURL(/\/$/);

  const shellSearch = page.getByRole('search', { name: '按股票代码打开个股研究' });
  const shellInput = shellSearch.getByRole('textbox', { name: '个股' });
  await shellInput.fill('AAPL');
  await shellInput.press('Enter');
  await expect(page).toHaveURL(/\/stocks\/AAPL\/structure-decision$/);

  await page.goBack();
  await expect(page).toHaveURL(/\/$/);
  const shellAfterBack = page.getByRole('search', { name: '按股票代码打开个股研究' });
  const shellInputAfterBack = shellAfterBack.getByRole('textbox', { name: '个股' });
  await shellInputAfterBack.fill('AAPL');
  await shellInputAfterBack.press('Escape');
  await expect(shellAfterBack.getByTestId('shell-stock-search-popover')).toHaveCount(0);
  await expect(shellInputAfterBack).not.toBeFocused();
  await shellInputAfterBack.fill('AAPL');
  await shellAfterBack.getByRole('button', { name: '打开 AAPL 美股 ticker 语境' }).click();
  await expect(page).toHaveURL(/\/stocks\/AAPL\/structure-decision$/);

  await page.goBack();
  await expect(page).toHaveURL(/\/$/);
  const runtimeCounters = await page.evaluate(() => {
    const trackedWindow = window as RuntimeWindow;
    return {
      pushes: trackedWindow.__t665RuntimePushes || 0,
      replaces: trackedWindow.__t665RuntimeReplaces || 0,
      unloads: trackedWindow.__t665RuntimeUnloads || 0,
    };
  });
  const overlays = await page.locator('[role="alertdialog"]').count();

  expect(runtimeCounters.pushes).toBe(6);
  expect(runtimeCounters.replaces).toBe(0);
  expect(runtimeCounters.unloads).toBe(0);
  expect(documentLoads).toBe(1);
  expect(overlays).toBe(0);
  expect(pageErrors).toEqual([]);
  console.log(JSON.stringify({
    runtimeCounters,
    documentNavigations,
    documentLoads,
    overlays,
    consoleErrors,
    pageErrors,
    failedRequests,
    errorResponses,
    finalUrl: page.url(),
  }));
});
