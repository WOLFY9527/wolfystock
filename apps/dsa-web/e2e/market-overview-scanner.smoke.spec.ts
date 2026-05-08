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

test.describe('scanner and market overview smoke', () => {
  test('scanner keeps controls visible without horizontal overflow', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await signIn(page, '/scanner');

    await expect(page.getByTestId('user-scanner-bento-page')).toBeVisible();
    await expect(page.getByTestId('scanner-sidebar')).toBeVisible();
    await page.getByRole('button', { name: /展开 高级参数|expand advanced controls/i }).click();
    await page.getByRole('button', { name: /主题标的池|theme universe/i }).click();
    await expect(page.getByTestId('scanner-theme-control')).toBeVisible();
    await expect(page.getByTestId('scanner-theme-select')).toBeVisible();
    await expect(page.getByTestId('scanner-run-button')).toBeVisible();
    await page.getByRole('button', { name: /更多扫描操作|more scanner actions/i }).click();
    const moreActions = page.getByTestId('scanner-more-actions-panel');
    await expect(moreActions).toBeVisible();
    await expect(moreActions.getByRole('button', { name: /导出 csv|export csv/i })).toBeVisible();
    await expect(moreActions.getByRole('button', { name: /复制全部代码|copy all symbols/i })).toBeVisible();

    await expect(page.getByTestId('scanner-result-card-NVDA')).toBeVisible();
    await expect(page.getByRole('button', { name: /^分析$|^analyze$/i }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: /^复制$|^copy$/i }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: /^导出$|^export$/i }).first()).toBeVisible();

    const candidateScrollRegion = page.getByTestId('scanner-candidate-scroll-region');
    await expect(candidateScrollRegion).toBeVisible();
    await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);

    await expect(page.getByTestId('scanner-sidebar')).toBeVisible();

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
    await expect(page.getByRole('link', { name: /打开扫描器|open scanner/i }).first()).toBeVisible();
    await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  });

  test('scanner copy and export actions are clickable without console errors', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await signIn(page, '/scanner');

    await page.getByRole('button', { name: /^复制$|^copy$/i }).first().click();
    await expect(page.getByRole('button', { name: /^已复制$|^copied$/i }).first()).toBeVisible();

    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: /^导出$|^export$/i }).first().click();
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
});
