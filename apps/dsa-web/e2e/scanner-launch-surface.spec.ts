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
  const conclusionBand = page.getByTestId('scanner-conclusion-band');
  const candidateRegion = page.getByTestId('scanner-candidate-scroll-region');
  const firstCandidate = page.getByTestId('scanner-result-row-NVDA');
  const denseShell = page.getByTestId('scanner-launch-bar');
  const commandBar = page.getByTestId('scanner-command-bar');
  const resultTable = page.getByTestId('scanner-result-table');
  const inlineDetailPanel = page.getByTestId('scanner-inline-detail-panel');
  const detailRail = page.getByTestId('scanner-detail-rail');
  const focusCandidate = page.getByTestId('scanner-result-detail-NVDA');

  await expect(page.getByTestId('user-scanner-workspace')).toBeVisible({ timeout: 15_000 });
  await expect(denseShell).toBeVisible();
  await expect(commandBar).toBeVisible();
  await expect(conclusionBand).toBeVisible();
  await expect(launchSummary).toBeVisible();
  await expect(conclusionBand).toContainText(/当前候选|Current candidate|证据不足|Evidence insufficient|等待扫描|Waiting for a scan/);
  await expect(launchSummary).toContainText(/最佳候选|Best candidate/);
  await expect(launchSummary).toContainText(/候选分布|Candidate mix/);
  await expect(launchSummary).toContainText(/信号状态|Signal state/);
  await expect(candidateRegion).toBeVisible();
  await expect(resultTable).toBeVisible();
  await expect(firstCandidate).toBeVisible();
  await expect(firstCandidate).toContainText('NVDA');
  if (await detailRail.count()) {
    await expect(detailRail).toBeVisible();
  } else {
    await expect(inlineDetailPanel).toBeVisible();
  }
  await expect(focusCandidate).toContainText(/当前信号|Why now/);
  await expect(focusCandidate).toContainText(/候选说明|Candidate notes/);
  await expect(page.getByTestId('scanner-control-rail')).toHaveCount(0);
  await expect(page.getByTestId('scanner-sidebar')).toHaveCount(0);
  await expect(page.getByTestId('scanner-bento-grid')).toHaveCount(0);
  await expect(page.getByTestId('scanner-card-wall')).toHaveCount(0);

  const launchBox = await commandBar.boundingBox();
  const conclusionBox = await conclusionBand.boundingBox();
  const summaryBox = await launchSummary.boundingBox();
  const candidateRegionBox = await candidateRegion.boundingBox();
  const resultBox = await denseShell.boundingBox();
  const viewportWidth = viewport.width;
  expect(launchBox).not.toBeNull();
  expect(conclusionBox).not.toBeNull();
  expect(summaryBox).not.toBeNull();
  expect(candidateRegionBox).not.toBeNull();
  expect(resultBox).not.toBeNull();
  expect(resultBox?.width ?? 0).toBeGreaterThan(viewportWidth * 0.72);
  expect(summaryBox?.y ?? 0).toBeGreaterThan(conclusionBox?.y ?? 0);
  expect(candidateRegionBox?.y ?? 0).toBeGreaterThan(summaryBox?.y ?? 0);
  expect(candidateRegionBox?.y ?? 0).toBeGreaterThan((launchBox?.y ?? 0) - 1);
  const firstRowLimit = viewportWidth >= 1024 ? 0.78 : viewportWidth >= 768 ? 0.92 : 1.1;
  expect(candidateRegionBox?.y ?? 0).toBeLessThan(viewport.height * firstRowLimit);
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
      expect(disclosureBox?.y ?? Number.POSITIVE_INFINITY).toBeGreaterThan(candidateRegionBox?.y ?? 0);
    }
  }
  await expect(page.getByTestId('scanner-diagnostics-panel')).toHaveCount(0);
  await expect(page.getByTestId('scanner-result-history-summary')).toHaveCount(0);
  await expect(page.getByTestId('scanner-strategy-preview')).toHaveCount(0);
  await expect(page.getByTestId('scanner-advanced-controls')).toHaveCount(0);

  const bodyText = await page.locator('body').innerText();
  expect(bodyText).not.toMatch(forbiddenTradingAction);
  expect(bodyText).not.toMatch(rawPayloadPattern);
  expect(bodyText).not.toMatch(/Details|provider|fallback|proxy|raw|reasonCode|reasonFamilies|source-confidence|sourceConfidence|MarketCache|bucket|runtime|diagnostic|diagnostics/i);
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
