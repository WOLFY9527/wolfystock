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

  const launchSummary = page.getByTestId('scanner-status-strip');
  const candidateRegion = page.getByTestId('scanner-candidate-scroll-region');
  const firstCandidate = page.getByTestId('scanner-result-row-NVDA');
  const denseShell = page.getByTestId('scanner-launch-bar');
  const commandBar = page.getByTestId('scanner-command-bar');
  const resultTable = page.getByTestId('scanner-result-table');

  await expect(page.getByTestId('user-scanner-bento-page')).toBeVisible({ timeout: 15_000 });
  await expect(denseShell).toBeVisible();
  await expect(commandBar).toBeVisible();
  await expect(launchSummary).toBeVisible();
  await expect(launchSummary).toContainText(/扫描/);
  await expect(launchSummary).toContainText(/入选/);
  await expect(launchSummary).toContainText(/数据/);
  await expect(candidateRegion).toBeVisible();
  await expect(resultTable).toBeVisible();
  await expect(firstCandidate).toBeVisible();
  await expect(firstCandidate).toContainText('NVDA');
  await expect(page.getByTestId('scanner-control-rail')).toHaveCount(0);
  await expect(page.getByTestId('scanner-sidebar')).toHaveCount(0);
  await expect(page.getByTestId('scanner-candidate-inspector')).toHaveCount(0);
  await expect(page.getByTestId('scanner-mobile-candidate-inspector')).toHaveCount(0);

  const launchBox = await commandBar.boundingBox();
  const summaryBox = await launchSummary.boundingBox();
  const candidateBox = await firstCandidate.boundingBox();
  const resultBox = await denseShell.boundingBox();
  const viewportWidth = viewport.width;
  expect(launchBox).not.toBeNull();
  expect(summaryBox).not.toBeNull();
  expect(candidateBox).not.toBeNull();
  expect(resultBox).not.toBeNull();
  expect(resultBox?.width ?? 0).toBeGreaterThan(viewportWidth * 0.72);
  expect(candidateBox?.y ?? 0).toBeGreaterThan(summaryBox?.y ?? 0);
  expect(candidateBox?.y ?? 0).toBeGreaterThan((launchBox?.y ?? 0) - 1);
  const firstRowLimit = viewportWidth >= 1024 ? 0.78 : viewportWidth >= 768 ? 0.92 : 1.1;
  expect(candidateBox?.y ?? 0).toBeLessThan(viewport.height * firstRowLimit);
  if (viewportWidth >= 1024) {
    expect(launchBox?.width ?? 0).toBeGreaterThan(viewportWidth * 0.72);
  }

  const secondaryDisclosures = [
    page.getByTestId('scanner-diagnostics-disclosure'),
    page.getByTestId('scanner-run-comparison-strip'),
    page.getByTestId('scanner-strategy-experiment'),
  ];
  for (const disclosure of secondaryDisclosures) {
    if (await disclosure.count()) {
      await expect(disclosure).toBeVisible();
      await expect(disclosure).not.toHaveAttribute('open');
      const disclosureBox = await disclosure.boundingBox();
      expect(disclosureBox?.y ?? Number.POSITIVE_INFINITY).toBeGreaterThan(candidateBox?.y ?? 0);
    }
  }
  await expect(page.getByTestId('scanner-diagnostics-panel')).toHaveCount(0);
  await expect(page.getByTestId('scanner-result-history-summary')).toHaveCount(0);
  await expect(page.getByTestId('scanner-strategy-preview')).toHaveCount(0);
  await expect(page.getByTestId('scanner-advanced-controls')).toHaveCount(0);

  const bodyText = await page.locator('body').innerText();
  expect(bodyText).not.toMatch(forbiddenTradingAction);
  expect(bodyText).not.toMatch(rawPayloadPattern);
  await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

test.describe('scanner launch surface', () => {
  test('candidate and evidence lead the zh scanner first fold', async ({ page }) => {
    await assertScannerLaunchViewport(page, { width: 1440, height: 1000 });
    await assertScannerLaunchViewport(page, { width: 1920, height: 1080 });
    await assertScannerLaunchViewport(page, { width: 768, height: 900 });
    await assertScannerLaunchViewport(page, { width: 390, height: 844 });
  });
});
