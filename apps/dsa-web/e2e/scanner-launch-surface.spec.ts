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
  const rankedWorkbench = page.getByTestId('scanner-ranked-workbench');
  const rankedList = page.getByTestId('scanner-ranked-list');
  const firstCandidate = page.getByTestId('scanner-ranked-row-NVDA');
  const configPanel = page.getByTestId('scanner-control-rail');

  await expect(page.getByTestId('user-scanner-bento-page')).toBeVisible({ timeout: 15_000 });
  await expect(launchSummary).toBeVisible();
  await expect(launchSummary).toContainText(/证据置信/);
  await expect(launchSummary).toContainText(/数据就绪/);
  await expect(launchSummary).toContainText(/下一步观察/);
  await expect(rankedWorkbench).toBeVisible();
  await expect(rankedList).toBeVisible();
  await expect(candidateRegion).toBeVisible();
  await expect(firstCandidate).toBeVisible();
  await expect(firstCandidate).toContainText('NVDA');

  const summaryBox = await launchSummary.boundingBox();
  const candidateBox = await firstCandidate.boundingBox();
  const configBox = await configPanel.boundingBox();
  expect(summaryBox).not.toBeNull();
  expect(candidateBox).not.toBeNull();
  expect(configBox).not.toBeNull();
  if (viewport.width >= 1280) {
    expect(candidateBox?.y ?? 0).toBeLessThan(600);
    expect(candidateBox?.y ?? 0).toBeLessThan(viewport.height);
  } else {
    expect(configBox?.y ?? 0).toBeLessThan(candidateBox?.y ?? Number.MAX_SAFE_INTEGER);
  }
  if (viewport.width >= 1280 && await page.getByTestId('scanner-diagnostics-disclosure').count()) {
    const diagnosticsDisclosureBox = await page.getByTestId('scanner-diagnostics-disclosure').boundingBox();
    expect(candidateBox?.y ?? 0).toBeLessThan(diagnosticsDisclosureBox?.y ?? Number.MAX_SAFE_INTEGER);
  }

  if (await page.getByTestId('scanner-diagnostics-disclosure').count()) {
    await expect(page.getByTestId('scanner-diagnostics-disclosure')).not.toHaveAttribute('open', '');
  }
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

  test('1440 keeps the ranked list dominant without a persistent detail rail', async ({ page }) => {
    await assertScannerLaunchViewport(page, { width: 1440, height: 1000 });

    await expect(page.getByTestId('scanner-detail-rail')).toHaveCount(0);
    await page.getByTestId('scanner-ranked-row-MOCK2').click();
    await expect(page.getByTestId('scanner-inline-detail-panel')).toContainText('MOCK2');
  });

  test('1920 uses the detail rail without shrinking the center ranking below minimum width', async ({ page }) => {
    await assertScannerLaunchViewport(page, { width: 1920, height: 1080 });

    const rankedList = page.getByTestId('scanner-ranked-list');
    const detailRail = page.getByTestId('scanner-detail-rail');
    await expect(detailRail).toBeVisible();
    await expect(detailRail).toContainText('NVDA');

    const rankedListBox = await rankedList.boundingBox();
    const detailRailBox = await detailRail.boundingBox();
    expect(rankedListBox).not.toBeNull();
    expect(detailRailBox).not.toBeNull();
    expect(rankedListBox?.width ?? 0).toBeGreaterThanOrEqual(820);
    expect(detailRailBox?.width ?? 0).toBeGreaterThanOrEqual(320);

    await page.getByTestId('scanner-ranked-row-MOCK2').click();
    await expect(detailRail).toContainText('MOCK2');
  });

  test('tablet keeps detail inline and avoids a persistent rail', async ({ page }) => {
    await assertScannerLaunchViewport(page, { width: 768, height: 1024 });

    await expect(page.getByTestId('scanner-detail-rail')).toHaveCount(0);
    await page.getByTestId('scanner-ranked-row-MOCK2').click();
    await expect(page.getByTestId('scanner-inline-detail-panel')).toContainText('MOCK2');
  });
});
