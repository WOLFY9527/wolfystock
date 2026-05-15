import type { Page } from '@playwright/test';
import { expect, test } from './fixtures/appSmoke';

const forbiddenTradingAction = /买入按钮|建议买入|建议卖出|立即交易|下单|提交订单|订单载荷|开仓|平仓|加仓|减仓|place order|submit order|buy now|sell now/i;
const rawPayloadPattern = /raw\s+(payload|response)|provider\s+payload|debug\s+payload|payload_json|raw_provider_payload/i;

async function assertScannerLaunchViewport(page: Page, viewport: { width: number; height: number }) {
  await page.setViewportSize(viewport);
  await page.route('**/api/v1/auth/status', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        authEnabled: true,
        loggedIn: true,
        passwordSet: true,
        passwordChangeable: true,
        setupState: 'enabled',
        currentUser: {
          id: 'user-1',
          username: 'wolfy-user',
          displayName: 'Wolfy User',
          role: 'user',
          isAdmin: false,
          isAuthenticated: true,
          transitional: false,
          authEnabled: true,
        },
      }),
    });
  });
  await page.goto('/zh/scanner');
  await page.waitForLoadState('domcontentloaded');

  const launchSummary = page.getByTestId('scanner-launch-evidence-summary');
  const candidateRegion = page.getByTestId('scanner-candidate-scroll-region');
  const firstCandidate = page.getByTestId('scanner-result-card-NVDA');
  const configPanel = page.getByTestId('scanner-sidebar');

  await expect(page.getByTestId('user-scanner-bento-page')).toBeVisible({ timeout: 15_000 });
  await expect(launchSummary).toBeVisible();
  await expect(launchSummary).toContainText(/证据置信/);
  await expect(launchSummary).toContainText(/数据就绪/);
  await expect(launchSummary).toContainText(/下一步观察/);
  await expect(candidateRegion).toBeVisible();
  await expect(firstCandidate).toBeVisible();
  await expect(firstCandidate).toContainText('NVDA');

  const summaryBox = await launchSummary.boundingBox();
  const candidateBox = await firstCandidate.boundingBox();
  const configBox = await configPanel.boundingBox();
  expect(summaryBox).not.toBeNull();
  expect(candidateBox).not.toBeNull();
  expect(configBox).not.toBeNull();
  expect(summaryBox?.y ?? 0).toBeLessThan(configBox?.y ?? Number.MAX_SAFE_INTEGER);
  expect(candidateBox?.y ?? 0).toBeLessThan(configBox?.y ?? Number.MAX_SAFE_INTEGER);
  expect(candidateBox?.y ?? 0).toBeLessThan(viewport.height * 2);

  await expect(page.getByTestId('scanner-diagnostics-panel')).toHaveCount(0);
  await expect(page.getByTestId('scanner-result-history-summary')).toHaveCount(0);
  await expect(page.getByTestId('scanner-strategy-preview')).toHaveCount(0);
  await expect(page.getByTestId('scanner-advanced-controls')).toBeVisible();

  const bodyText = await page.locator('body').innerText();
  expect(bodyText).not.toMatch(forbiddenTradingAction);
  expect(bodyText).not.toMatch(rawPayloadPattern);
  await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

test.describe('scanner launch surface', () => {
  test('candidate and evidence lead the zh scanner first fold', async ({ page }) => {
    await assertScannerLaunchViewport(page, { width: 1440, height: 1000 });
    await assertScannerLaunchViewport(page, { width: 390, height: 844 });
  });
});
