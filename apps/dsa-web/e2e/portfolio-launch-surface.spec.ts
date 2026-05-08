import { expect, test } from '@playwright/test';
import { installPortfolioSmokeHarness } from './fixtures/portfolioSmoke';

const viewports = [
  { name: 'desktop', width: 1440, height: 1000 },
  { name: 'mobile', width: 390, height: 844 },
];

const forbiddenLaunchLabels = ['交易工作台', '股票买卖', '提交交易', '下单', '订单执行', '买入', '卖出'];
const requiredLedgerLabels = ['资产台账总览', '手工记账台', '手工记账', '流水记录', '持仓流水', '保存记录'];

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

test.describe('portfolio launch surface', () => {
  for (const viewport of viewports) {
    test(`answers account state, assets, attention, and secondary ledger on ${viewport.name}`, async ({ page }) => {
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

      const accountHero = page.getByTestId('portfolio-total-assets-card');
      const priorityPanel = page.getByTestId('portfolio-launch-priority-panel');
      const primaryGrid = page.getByTestId('portfolio-first-fold-primary-grid');
      const holdingsPanel = page.getByTestId('portfolio-current-holdings-panel');
      const manualPanel = page.getByTestId('portfolio-trade-station-card');
      const secondaryCallout = page.getByTestId('portfolio-manual-secondary-callout');

      await expect(accountHero).toBeVisible({ timeout: 15_000 });
      await expect(priorityPanel).toBeVisible({ timeout: 15_000 });
      await expect(primaryGrid).toContainText('持仓状态');
      await expect(primaryGrid).toContainText('现金状态');
      await expect(primaryGrid).toContainText('敞口状态');
      await expect(primaryGrid).toContainText('需要关注');
      await expect(holdingsPanel).toBeVisible({ timeout: 15_000 });
      await expect(secondaryCallout).toContainText('次级：手工记账');
      await expect(manualPanel).toContainText('仅用于手工记账');

      const heroBox = await accountHero.boundingBox();
      const priorityBox = await priorityPanel.boundingBox();
      const holdingsBox = await holdingsPanel.boundingBox();
      const manualBox = await manualPanel.boundingBox();
      expect(heroBox?.y ?? Infinity).toBeLessThan(220);
      expect(priorityBox?.y ?? Infinity).toBeLessThan(viewport.height * 0.6);
      expect(holdingsBox?.y ?? Infinity).toBeLessThan(manualBox?.y ?? 0);
      expect((manualBox?.y ?? 0) - (holdingsBox?.y ?? 0)).toBeGreaterThan(80);

      await expectVisibleTextPresent(page, requiredLedgerLabels);
      await expectVisibleTextAbsent(page, forbiddenLaunchLabels);
      await expectNoHorizontalOverflow(page);
      expect(consoleErrors).toEqual([]);
      expect(pageErrors).toEqual([]);
      expect(harness.requests.count('GET', '/api/v1/portfolio/snapshot')).toBeGreaterThan(0);
      expect(harness.requests.calls.filter((entry) => entry.startsWith('POST '))).toEqual([]);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    });
  }
});
