import { expect, test, type Page, type Route } from '@playwright/test';

const mockCurrentUser = {
  id: 7,
  username: 'watchlist-user',
  email: 'watchlist@example.com',
  isAdmin: false,
};

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function installWatchlistEmptyHarness(page: Page) {
  await page.route('**/api/v1/auth/status**', async (route) => {
    await fulfillJson(route, {
      authEnabled: true,
      loggedIn: true,
      passwordSet: true,
      passwordChangeable: true,
      setupState: 'enabled',
      currentUser: mockCurrentUser,
    });
  });
  await page.route('**/api/v1/auth/me**', async (route) => {
    await fulfillJson(route, mockCurrentUser);
  });
  await page.route('**/api/v1/watchlist/items', async (route) => {
    await fulfillJson(route, { items: [] });
  });
  await page.route('**/api/v1/watchlist/refresh-status', async (route) => {
    await fulfillJson(route, {
      enabled: true,
      usTime: '08:45',
      cnTime: '09:00',
      hkTime: '09:00',
      status: 'idle',
      lastRunAt: null,
      nextRunAt: null,
    });
  });
  await page.route('**/api/v1/user-alerts/rules', async (route) => {
    await fulfillJson(route, {
      contract_version: 'user_alert_contract_v1',
      delivery_mode: 'in_app',
      in_app_only: true,
      owner_scoped: true,
      items: [],
    });
  });
  await page.route('**/api/v1/user-alerts/events**', async (route) => {
    await fulfillJson(route, {
      contract_version: 'user_alert_contract_v1',
      delivery_mode: 'in_app',
      in_app_only: true,
      owner_scoped: true,
      total: 0,
      limit: 20,
      offset: 0,
      items: [],
    });
  });
}

async function expectNoHorizontalOverflow(page: Page) {
  await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

async function openWatchlistEmptyState(page: Page) {
  await installWatchlistEmptyHarness(page);
  await page.goto('/zh/watchlist');
  await page.waitForLoadState('domcontentloaded');
  await expect(page).not.toHaveURL(/\/guest(?:$|[/?#])/);
  await expect(page.getByTestId('watchlist-page')).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId('watchlist-compact-empty-state')).toBeVisible();
}

test('keeps a single primary scanner CTA in the empty state on desktop', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await openWatchlistEmptyState(page);

  const headerStrip = page.getByTestId('watchlist-header-strip');
  const emptyState = page.getByTestId('watchlist-compact-empty-state');
  const boardShell = page.getByTestId('watchlist-board-shell');
  const scannerButton = page.getByRole('button', { name: '打开扫描器' });

  await expect(scannerButton).toHaveCount(1);
  await expect(headerStrip.getByRole('button', { name: '打开扫描器' })).toHaveCount(0);
  await expect(emptyState).toContainText(/从(?:研究)?扫描器添加标的到观察列表/);
  await expect(emptyState).toContainText('添加后可在这里查看已保存的候选证据与状态。');
  await expect(page.getByTestId('watchlist-compact-filter-bar')).toHaveCount(0);
  await expect(page.getByTestId('watchlist-advanced-filters')).toHaveCount(0);
  await expect(page.getByTestId('watchlist-list-header')).toHaveCount(0);
  await expect(page.getByTestId('watchlist-command-bar')).toHaveCount(0);
  await expect(boardShell).not.toHaveClass(/lg:grid-cols-\[minmax\(0,1fr\)_340px\]/);
  await expectNoHorizontalOverflow(page);
});

test('stacks the empty-state CTA cleanly at 390px without overlap', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openWatchlistEmptyState(page);

  const headerStrip = page.getByTestId('watchlist-header-strip');
  const emptyState = page.getByTestId('watchlist-compact-empty-state');
  const scannerButton = page.getByRole('button', { name: '打开扫描器' });

  await expect(scannerButton).toHaveCount(1);
  await expect(headerStrip.getByRole('button', { name: '打开扫描器' })).toHaveCount(0);
  await expect(emptyState).toContainText(/从(?:研究)?扫描器添加标的到观察列表/);
  await expect(page.getByTestId('watchlist-compact-filter-bar')).toHaveCount(0);
  await expect(page.getByTestId('watchlist-command-bar')).toHaveCount(0);
  await expectNoHorizontalOverflow(page);

  const layout = await emptyState.evaluate((node) => {
    const element = node as HTMLElement;
    const [content, action] = Array.from(element.children) as HTMLElement[];
    const contentRect = content.getBoundingClientRect();
    const actionRect = action.getBoundingClientRect();
    return {
      actionTop: actionRect.top,
      contentBottom: contentRect.bottom,
      actionLeft: actionRect.left,
      contentLeft: contentRect.left,
    };
  });

  expect(layout.actionTop).toBeGreaterThanOrEqual(layout.contentBottom - 1);
  expect(layout.actionLeft).toBeGreaterThanOrEqual(layout.contentLeft - 1);
});
