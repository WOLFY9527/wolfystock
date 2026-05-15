import type { Page } from '@playwright/test';
import { expect, test } from './fixtures/appSmoke';

async function signIn(page: Page, redirectPath: string) {
  await page.goto(`/login?redirect=${encodeURIComponent(redirectPath)}`);
  await page.locator('#username').fill('wolfy-user');
  await page.locator('#password').fill('mock-password');
  await Promise.all([
    page.waitForResponse((response) => response.url().includes('/api/v1/auth/login') && response.status() === 200),
    page.getByRole('button', { name: /sign in|登录继续|授权进入工作台|完成设置并登录/i }).click(),
  ]);
  await page.waitForURL(/\/$/);
  await page.goto(redirectPath);
}

async function installPartialTemperaturePayload(page: Page) {
  await page.route('**/api/v1/market/temperature', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        source: 'computed',
        sourceLabel: 'Mock model',
        updatedAt: '2026-05-02T09:00:00Z',
        asOf: '2026-05-02T09:00:00Z',
        freshness: 'mock',
        isFallback: false,
        confidence: 0.18,
        reliableInputCount: 1,
        fallbackInputCount: 3,
        excludedInputCount: 2,
        isReliable: false,
        scores: {
          liquidity: {
            value: 51,
            label: '中性',
            trend: 'stable',
            description: '流动性输入部分可用。',
          },
        },
      }),
    });
  });
}

test.describe('scanner and market overview smoke', () => {
  test('scanner keeps controls visible without horizontal overflow', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await signIn(page, '/scanner');

    await expect(page.getByTestId('user-scanner-bento-page')).toBeVisible();
    await expect(page.getByTestId('scanner-launch-bar')).toBeVisible();
    await expect(page.getByTestId('scanner-control-rail')).toHaveCount(0);
    await expect(page.getByTestId('scanner-sidebar')).toHaveCount(0);
    await page.getByTestId('scanner-scope-selector').getByRole('button', { name: /主题标的池|theme universe/i }).click();
    await page.getByRole('button', { name: /展开 高级参数|expand advanced controls/i }).click();
    await expect(page.getByTestId('scanner-theme-control')).toBeVisible();
    await expect(page.getByTestId('scanner-theme-select')).toBeVisible();
    await expect(page.getByTestId('scanner-run-button')).toBeVisible();
    await page.getByRole('button', { name: /更多扫描操作|more scanner actions/i }).click();
    const moreActions = page.getByTestId('scanner-more-actions-panel');
    await expect(moreActions).toBeVisible();
    await expect(moreActions.getByRole('button', { name: /导出 csv|export csv/i })).toBeVisible();
    await expect(moreActions.getByRole('button', { name: /复制全部代码|copy all symbols/i })).toBeVisible();
    await page.getByRole('button', { name: /更多扫描操作|more scanner actions/i }).click();
    await expect(moreActions).toHaveCount(0);

    await expect(page.getByTestId('scanner-result-table')).toBeVisible();
    await expect(page.getByTestId('scanner-result-row-NVDA')).toBeVisible();
    await expect(page.getByRole('button', { name: /^分析$|^analyze$/i }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: /^复制$|^copy$/i }).first()).toBeVisible();
    await page.getByTestId('scanner-result-row-NVDA').getByRole('button', { name: /详情|detail/i }).click();
    await expect(page.getByTestId('scanner-result-detail-NVDA').getByRole('button', { name: /导出该候选|export candidate/i })).toBeVisible();

    const candidateScrollRegion = page.getByTestId('scanner-candidate-scroll-region');
    await expect(candidateScrollRegion).toBeVisible();
    await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);

    await expect(page.getByTestId('scanner-launch-bar')).toBeVisible();

    await page.goto('/watchlist');
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByTestId('watchlist-page')).toBeVisible();
    await expect(page.getByTestId('watchlist-filter-grid')).toBeVisible();
    await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  });

  test('scanner and watchlist stay usable on mobile launch viewport', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await signIn(page, '/scanner');

    await expect(page.getByTestId('user-scanner-bento-page')).toBeVisible();
    await expect(page.getByTestId('scanner-results-pane')).toBeVisible();
    await expect(page.getByTestId('scanner-candidate-scroll-region')).toBeVisible();
    await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);

    await page.goto('/watchlist');
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByTestId('watchlist-page')).toBeVisible();
    await expect(page.getByRole('heading', { name: /观察列表|watchlist/i })).toBeVisible();
    await expect(page.getByTestId('watchlist-filter-grid')).toBeVisible();
    await expect(page.getByTestId('watchlist-page')).toContainText(/观察列表|watchlist/i);
    await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  });

  test('scanner copy and export actions are clickable without console errors', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await signIn(page, '/scanner');

    await page.getByRole('button', { name: /^复制$|^copy$/i }).first().click();
    await expect(page.getByRole('button', { name: /^已复制$|^copied$/i }).first()).toBeVisible();

    await page.getByTestId('scanner-result-row-NVDA').getByRole('button', { name: /详情|detail/i }).click();
    const downloadPromise = page.waitForEvent('download');
    await page.getByTestId('scanner-result-detail-NVDA').getByRole('button', { name: /导出该候选|export candidate/i }).click();
    const download = await downloadPromise;
    expect(await download.suggestedFilename()).toContain('scanner_cn_');
  });

  test('market overview keeps top metrics visible with no ghost vertical overflow', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await signIn(page, '/market-overview');

    await expect(page.getByTestId('market-overview-shell')).toBeVisible();
    await expect(page.getByTestId('market-overview-category-tabs')).toBeVisible();
    await expect(page.getByTestId('market-overview-hero-ribbon')).toBeVisible();
    await expect(page.getByTestId('market-overview-status-strip')).toBeVisible();
    await expect(page.getByTestId('market-overview-side-rail')).toBeVisible();
    await expect(page.getByTestId('market-overview-card-indices')).toBeVisible();
    await expect(page.getByTestId('market-overview-card-volatility')).toBeVisible();
    await expect(page.getByTestId('market-overview-card-fundsFlow')).toBeVisible();

    const viewport = page.viewportSize();
    expect(viewport).not.toBeNull();
    const topStackBox = await page.getByTestId('market-overview-top-stack').boundingBox();
    expect(topStackBox).not.toBeNull();
    expect((topStackBox?.y ?? 0) + (topStackBox?.height ?? 0)).toBeLessThanOrEqual((viewport?.height ?? 0) - 8);

    const rails = await Promise.all([
      page.getByTestId('market-overview-primary-rail').boundingBox(),
      page.getByTestId('market-overview-side-rail').boundingBox(),
    ]);
    expect(rails[0]).not.toBeNull();
    expect(rails[1]).not.toBeNull();
    expect((rails[1]?.width ?? 0) < (rails[0]?.width ?? 0)).toBe(true);

    const exportSummaryButton = page.getByTestId('market-overview-export-summary');
    await expect(exportSummaryButton).toBeVisible();
    await expect(exportSummaryButton).toBeEnabled();
    await exportSummaryButton.click();
    await expect(exportSummaryButton).toContainText(/已复制摘要|summary copied/i);

    const copiedSummary = await page.evaluate(() => (window as Window & { __pwClipboardText?: string }).__pwClipboardText || '');
    expect(copiedSummary).toContain('市场总览');
    expect(copiedSummary).toContain('市场温度');
    expect(copiedSummary).toContain('市场解读');
  });

  test('market overview degrades partial temperature payload without blanking', async ({ page }) => {
    await installPartialTemperaturePayload(page);

    const viewports = [
      { width: 1440, height: 1000 },
      { width: 390, height: 844 },
    ];

    for (const [index, viewport] of viewports.entries()) {
      await page.setViewportSize(viewport);
      if (index === 0) {
        await signIn(page, '/zh/market-overview');
      } else {
        await page.goto('/zh/market-overview');
        await page.waitForLoadState('domcontentloaded');
      }

      await expect(page.getByTestId('market-overview-shell')).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('market-overview-temperature-summary')).toContainText(/数据不足/);
      await expect(page.getByTestId('market-temperature-unreliable-summary')).toBeVisible();
      await expect(page.getByTestId('market-decision-text')).toContainText(/数据不足|数据可用：存在延迟源/);
      await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
      await expect(await page.locator('body').innerText()).not.toMatch(/raw|payload/i);
    }
  });
});
