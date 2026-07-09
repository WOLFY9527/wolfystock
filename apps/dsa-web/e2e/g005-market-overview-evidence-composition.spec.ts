import { expect, test, type Page } from './fixtures/appSmoke';
import { captureShellVisualEvidence } from './fixtures/shellVisualEvidence';

const OPERATOR_ONLY_READINESS_PATHS = [
  '/api/v1/market/data-readiness',
  '/api/v1/market/professional-data-capabilities',
] as const;

async function signInToMarketOverview(page: Page) {
  await page.goto('/login?redirect=/zh/market-overview');
  await page.locator('#username').fill('wolfy-user');
  await page.locator('#password').fill('mock-password');
  await Promise.all([
    page.waitForResponse((response) => response.url().includes('/api/v1/auth/login') && response.status() === 200),
    page.getByRole('button', { name: /sign in|登录继续|授权进入工作台|完成设置并登录/i }).click(),
  ]);
  await page.goto('/zh/market-overview');
  await expect(page.getByTestId('market-overview-workbench')).toBeVisible({ timeout: 20_000 });
}

test.describe('G005 Market Overview evidence composition', () => {
  test('desktop research anatomy composition and consumer operator boundary', async ({ page, consoleErrors }) => {
    const operatorCalls: string[] = [];
    page.on('request', (request) => {
      const path = new URL(request.url()).pathname;
      if (OPERATOR_ONLY_READINESS_PATHS.some((candidate) => path === candidate)) {
        operatorCalls.push(path);
      }
    });

    await page.setViewportSize({ width: 1440, height: 960 });
    await signInToMarketOverview(page);

    await expect(page.getByTestId('market-overview-observation-head')).toBeVisible();
    await expect(page.getByTestId('market-overview-observation-head')).toHaveAttribute('data-research-density', 'research');
    await expect(page.getByRole('heading', { level: 1, name: '市场状态概览' })).toHaveCount(1);
    await expect(page.getByTestId('market-overview-top-verdict')).toBeVisible();
    await expect(page.getByTestId('market-overview-data-quality-composition')).toBeVisible();
    await expect(page.getByTestId('market-overview-research-risk-limits')).toBeVisible();
    await expect(page.getByTestId('market-overview-next-research-action')).toBeVisible();
    await expect(page.getByTestId('market-overview-main-grid')).toHaveAttribute(
      'data-market-overview-composition',
      'grouped-evidence',
    );
    await expect(page.locator('[data-evidence-group-role]').first()).toBeVisible();

    // Manual refresh ownership: one card refresh targets one logical resource.
    const volatilityPath = '/api/v1/market-overview/volatility';
    let volatilityHits = 0;
    page.on('request', (request) => {
      if (new URL(request.url()).pathname === volatilityPath) {
        volatilityHits += 1;
      }
    });
    const refreshButton = page.getByRole('button', {
      name: /(?:刷新\s*波动率与风险压力|refresh.*volatility)/i,
    });
    if (await refreshButton.count()) {
      const before = volatilityHits;
      await refreshButton.first().click();
      await expect.poll(() => volatilityHits).toBeGreaterThan(before);
      // Allow a short settle window; ownership must not fan out to operator readiness.
      await page.waitForTimeout(500);
    }

    expect(operatorCalls).toEqual([]);
    expect(consoleErrors.filter((entry) => !entry.includes('favicon') && !entry.includes('ECharts'))).toEqual([]);

    await captureShellVisualEvidence(page, 'g005-market-overview-desktop', { width: 1440, height: 960 });
  });

  test('mobile stacked research composition remains usable', async ({ page, consoleErrors }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await signInToMarketOverview(page);

    const observationHead = page.getByTestId('market-overview-observation-head');
    await expect(observationHead).toBeVisible();
    const observationBox = await observationHead.boundingBox();
    expect(observationBox).not.toBeNull();
    expect(observationBox!.width).toBeLessThanOrEqual(390);
    expect(observationBox!.x).toBeGreaterThanOrEqual(0);

    await expect(page.getByTestId('market-overview-data-quality-composition')).toBeVisible();
    await expect(page.getByTestId('market-overview-summary-strip')).toBeVisible();
    await expect(page.getByTestId('market-overview-next-research-action')).toBeVisible();

    // No horizontal page overflow from composition chrome.
    const hasHorizontalOverflow = await page.evaluate(() => {
      const root = document.documentElement;
      return root.scrollWidth > root.clientWidth + 1;
    });
    expect(hasHorizontalOverflow).toBe(false);

    expect(consoleErrors.filter((entry) => !entry.includes('favicon') && !entry.includes('ECharts'))).toEqual([]);

    await captureShellVisualEvidence(page, 'g005-market-overview-mobile', { width: 390, height: 844 });
  });
});
