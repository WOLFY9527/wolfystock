import { expect, test } from '@playwright/test';
import { installPortfolioSmokeHarness } from './fixtures/portfolioSmoke';

const viewports = [
  { name: 'desktop', width: 1440, height: 1000 },
  { name: 'mobile', width: 390, height: 844 },
];

const forbiddenLaunchLabels = ['交易工作台', '股票买卖', '提交交易', '下单', '订单执行', '买入', '卖出'];
const requiredLedgerLabels = ['当前持仓', '历史记录', '手工记账台', '手工记账', '持仓流水', '保存记录'];

async function expectNoHorizontalOverflow(page: import('@playwright/test').Page) {
  const overflow = await page.evaluate(() => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth));
  expect(overflow).toBeLessThanOrEqual(1);
}

async function expectVisibleTextAbsent(page: import('@playwright/test').Page, labels: string[]) {
  const bodyText = await page.locator('body').innerText();
  const visibleLines = bodyText.split(/\s+/).map((line) => line.trim()).filter(Boolean);
  for (const label of labels) {
    expect(visibleLines).not.toContain(label);
  }
}

async function expectVisibleTextPresent(page: import('@playwright/test').Page, labels: string[]) {
  const bodyText = await page.locator('body').innerText();
  for (const label of labels) {
    expect(bodyText).toContain(label);
  }
}

async function waitForPortfolioSurface(page: import('@playwright/test').Page) {
  const surface = page.getByTestId('portfolio-bento-page');
  await expect(surface).toBeVisible({ timeout: 15_000 });
  await page.waitForFunction(() => {
    const element = document.querySelector('[data-testid="portfolio-bento-page"]');
    return Boolean(
      element &&
      element.classList.contains('opacity-100') &&
      element.classList.contains('pointer-events-auto'),
    );
  });
}

test.describe('portfolio launch surface', () => {
  for (const viewport of viewports) {
    test(`keeps portfolio workspace lanes usable on ${viewport.name}`, async ({ page }) => {
      const consoleErrors: string[] = [];
      const pageErrors: string[] = [];
      page.on('console', (message) => {
        if (message.type() === 'error') {
          consoleErrors.push(message.text());
        }
      });
      page.on('pageerror', (error) => pageErrors.push(error.message));

      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      const harness = await installPortfolioSmokeHarness(page);
      await page.goto('/zh/portfolio');
      await page.waitForLoadState('domcontentloaded');
      await waitForPortfolioSurface(page);

      const accountHero = page.getByTestId('portfolio-total-assets-card');
      const workspaceLanes = page.getByTestId('portfolio-workspace-lanes');
      const primaryLane = page.getByTestId('portfolio-primary-lane');
      const secondaryLane = page.getByTestId('portfolio-secondary-lane');
      const activityLane = page.getByTestId('portfolio-activity-lane');
      const manualLane = page.getByTestId('portfolio-manual-lane');
      const holdingsPanel = page.getByTestId('portfolio-current-holdings-panel');
      const riskPanel = page.getByTestId('portfolio-risk-card');
      const activityPanel = page.getByTestId('portfolio-history-full');
      const manualPanel = page.getByTestId('portfolio-trade-station-card');

      await expect(workspaceLanes).toBeVisible({ timeout: 15_000 });
      await expect(primaryLane).toBeVisible({ timeout: 15_000 });
      await expect(secondaryLane).toBeVisible({ timeout: 15_000 });
      await expect(activityLane).toBeVisible({ timeout: 15_000 });
      await expect(manualLane).toBeVisible({ timeout: 15_000 });
      await expect(holdingsPanel).toBeVisible({ timeout: 15_000 });
      await expect(riskPanel).toBeVisible({ timeout: 15_000 });
      await expect(activityPanel).toBeVisible({ timeout: 15_000 });
      await expect(manualPanel).toContainText('仅用于手工记账');
      await expect(activityPanel).toContainText('历史记录');

      const heroBox = await accountHero.boundingBox();
      const primaryBox = await primaryLane.boundingBox();
      const secondaryBox = await secondaryLane.boundingBox();
      const activityBox = await activityLane.boundingBox();
      const manualLaneBox = await manualLane.boundingBox();
      expect(heroBox?.y ?? Infinity).toBeLessThan(viewport.name === 'mobile' ? viewport.height * 0.38 : 280);

      if (viewport.name === 'desktop') {
        expect(primaryBox).not.toBeNull();
        expect(secondaryBox).not.toBeNull();
        expect(activityBox).not.toBeNull();
        expect(manualLaneBox).not.toBeNull();

        expect((primaryBox?.width ?? 0) / Math.max(1, secondaryBox?.width ?? 0)).toBeGreaterThan(1.45);
        expect((activityBox?.width ?? 0) / Math.max(1, manualLaneBox?.width ?? 0)).toBeGreaterThan(1.45);
        expect(Math.abs((primaryBox?.x ?? 0) - (activityBox?.x ?? 0))).toBeLessThanOrEqual(12);
        expect(Math.abs((secondaryBox?.x ?? 0) - (manualLaneBox?.x ?? 0))).toBeLessThanOrEqual(12);
        expect(Math.abs((primaryBox?.y ?? 0) - (secondaryBox?.y ?? 0))).toBeLessThanOrEqual(20);
        expect((manualLaneBox?.y ?? 0) - (secondaryBox?.y ?? 0)).toBeGreaterThan(40);
      } else {
        const holdingsBox = await holdingsPanel.boundingBox();
        const riskBox = await riskPanel.boundingBox();
        const activityPanelBox = await activityPanel.boundingBox();
        const manualBox = await manualPanel.boundingBox();

        expect(holdingsBox?.y ?? Infinity).toBeLessThan(riskBox?.y ?? 0);
        expect(riskBox?.y ?? Infinity).toBeLessThan(activityPanelBox?.y ?? 0);
        expect(activityPanelBox?.y ?? Infinity).toBeLessThan(manualBox?.y ?? 0);
      }

      await expectVisibleTextPresent(page, requiredLedgerLabels);
      await expectVisibleTextAbsent(page, forbiddenLaunchLabels);
      await expectNoHorizontalOverflow(page);
      expect(consoleErrors).toEqual([]);
      expect(pageErrors).toEqual([]);
      expect(harness.requests.count('GET', '/api/v1/portfolio/snapshot')).toBeGreaterThan(0);
      expect(harness.requests.count('GET', '/api/v1/portfolio/risk')).toBeGreaterThan(0);
      expect(harness.requests.calls.filter((entry) => entry.startsWith('POST '))).toEqual([]);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    });
  }
});
