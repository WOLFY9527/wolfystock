import type { Page } from '@playwright/test';
import { expect, test } from './fixtures/appSmoke';

type SearchNavigationWindow = Window & {
  __t665SearchMarker?: string;
  __t665RouteTransitions?: number;
};

async function stabilizeUnrelatedData(page: Page) {
  await page.route('**/api/v1/analysis/preview', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        query_id: 't665-preview',
        stock_code: 'AAPL',
        stock_name: 'Apple',
        preview_scope: 'guest',
        report: {
          meta: { query_id: 't665-preview', stock_code: 'AAPL', stock_name: 'Apple', report_type: 'brief' },
          summary: { analysis_summary: 'Preview unavailable for route qualification.', sentiment_score: 50 },
        },
      }),
    });
  });
  await page.route('**/api/v1/stocks/**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });
  await page.route('**/api/v1/options/**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });
}

async function markClientSession(page: Page) {
  await page.evaluate(() => {
    const trackedWindow = window as SearchNavigationWindow;
    trackedWindow.__t665SearchMarker = 'spa-search-session';
    trackedWindow.__t665RouteTransitions = 0;
    const originalPushState = window.history.pushState.bind(window.history);
    window.history.pushState = function pushState(...args) {
      trackedWindow.__t665RouteTransitions = (trackedWindow.__t665RouteTransitions || 0) + 1;
      return originalPushState(...args);
    };
  });
}

async function expectSpaMarker(page: Page) {
  await expect.poll(() => page.evaluate(() => (window as SearchNavigationWindow).__t665SearchMarker)).toBe('spa-search-session');
}

test('home stock search reaches the canonical route through keyboard, button, and suggestions', async ({ page }) => {
  const failedRequests: string[] = [];
  const errorResponses: string[] = [];
  page.on('requestfailed', (request) => failedRequests.push(`${request.method()} ${request.url()}`));
  page.on('response', (response) => {
    if (response.status() >= 400) errorResponses.push(`${response.status()} ${response.url()}`);
  });

  await stabilizeUnrelatedData(page);
  await page.goto('/');
  await expect(page.getByTestId('home-bento-omnibar-input')).toBeVisible();
  await markClientSession(page);

  const homeInput = page.getByTestId('home-bento-omnibar-input');
  await homeInput.fill('AAPL');
  await homeInput.press('Enter');
  await expect(page).toHaveURL(/\/stocks\/AAPL\/structure-decision\?symbol=AAPL&source=manual$/);
  await expectSpaMarker(page);
  await expect.poll(() => page.evaluate(() => (window as SearchNavigationWindow).__t665RouteTransitions)).toBe(1);

  await page.goBack();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId('home-bento-omnibar-input')).toBeVisible();
  await homeInput.fill('AAPL');
  await page.getByTestId('home-bento-analyze-button').click();
  await expect(page).toHaveURL(/\/stocks\/AAPL\/structure-decision\?symbol=AAPL&source=manual$/);
  await expectSpaMarker(page);
  await expect.poll(() => page.evaluate(() => (window as SearchNavigationWindow).__t665RouteTransitions)).toBe(2);

  await page.goBack();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId('home-bento-omnibar-input')).toBeVisible();
  await homeInput.fill('600519');
  await page.getByTestId('home-bento-analyze-button').click();
  await expect(page).toHaveURL(/\/stocks\/600519\/structure-decision\?symbol=600519&source=manual$/);
  await expectSpaMarker(page);
  await expect.poll(() => page.evaluate(() => (window as SearchNavigationWindow).__t665RouteTransitions)).toBe(3);

  await page.goBack();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId('home-bento-omnibar-input')).toBeVisible();
  await homeInput.fill('0700.HK');
  await homeInput.press('Enter');
  await expect(page).toHaveURL(/\/stocks\/0700\.HK\/structure-decision\?symbol=0700\.HK&source=manual$/);
  await expectSpaMarker(page);
  await expect.poll(() => page.evaluate(() => (window as SearchNavigationWindow).__t665RouteTransitions)).toBe(4);

  await page.goBack();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId('home-bento-omnibar-input')).toBeVisible();
  await homeInput.fill('not-a-symbol!');
  await page.getByTestId('home-bento-analyze-button').click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByText('请输入格式正确的股票代码')).toBeVisible();
  await homeInput.fill('');
  await page.getByTestId('home-bento-analyze-button').click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByText('请输入股票代码后再开始分析')).toBeVisible();
  await expect.poll(() => page.evaluate(() => (window as SearchNavigationWindow).__t665RouteTransitions)).toBe(4);

  const isMobile = page.viewportSize()?.width !== undefined && (page.viewportSize()?.width || 0) < 700;
  if (isMobile) {
    const menuTrigger = page.getByRole('button', { name: '打开导航菜单' });
    await menuTrigger.click();
  }
  const shellSearch = page.getByRole('search', { name: '按股票代码打开个股研究' });
  await expect(shellSearch).toBeVisible();
  const shellInput = shellSearch.getByRole('textbox', { name: '个股' });
  await shellInput.fill('AAPL');
  await shellInput.press('Enter');
  await expect(page).toHaveURL(/\/stocks\/AAPL\/structure-decision$/);
  await expectSpaMarker(page);
  await expect.poll(() => page.evaluate(() => (window as SearchNavigationWindow).__t665RouteTransitions)).toBe(5);

  await page.goBack();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId('home-bento-omnibar-input')).toBeVisible();
  if (isMobile) {
    const menuTrigger = page.getByRole('button', { name: '打开导航菜单' });
    await menuTrigger.click();
  }
  const shellSearchAfterBack = page.getByRole('search', { name: '按股票代码打开个股研究' });
  const shellInputAfterBack = shellSearchAfterBack.getByRole('textbox', { name: '个股' });
  await shellInputAfterBack.fill('AAPL');
  await shellInputAfterBack.press('Escape');
  await expect(shellSearchAfterBack.getByTestId('shell-stock-search-popover')).toHaveCount(0);
  await expect(page).toHaveURL(/\/$/);
  if (isMobile) {
    const menuTrigger = page.getByRole('button', { name: '打开导航菜单' });
    await expect(page.getByTestId('shell-mobile-navigation-menu')).toHaveCount(0);
    await expect(menuTrigger).toBeFocused();
    await menuTrigger.click();
  } else {
    await expect(shellInputAfterBack).not.toBeFocused();
  }
  await shellInputAfterBack.fill('AAPL');
  await shellSearchAfterBack.getByRole('button', { name: '打开 AAPL 美股 ticker 语境' }).click();
  await expect(page).toHaveURL(/\/stocks\/AAPL\/structure-decision$/);
  await expectSpaMarker(page);
  await expect.poll(() => page.evaluate(() => (window as SearchNavigationWindow).__t665RouteTransitions)).toBe(6);

  await expect(page.locator('[role="alertdialog"]')).toHaveCount(0);
  expect(failedRequests).toEqual([]);
  expect(errorResponses).toEqual([]);
});
