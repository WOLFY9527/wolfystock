import { expect, test } from '@playwright/test';
import { installPortfolioSmokeHarness } from './fixtures/portfolioSmoke';

const viewports = [
  { name: 'desktop', width: 1440, height: 1000 },
  { name: 'mobile', width: 390, height: 844 },
];

const forbiddenLaunchLabels = ['交易工作台', '股票买卖', '提交交易', '下单', '订单执行', '买入', '卖出'];
const requiredLedgerLabels = ['当前持仓', '历史记录', '手工记账台', '手工记账', '持仓流水', '保存记录'];
const forbiddenInternalLeakagePattern =
  /\braw\b|\bdebug\b|\bschema\b|\btrace\b|\bprompt\b|\btoken\b|\bcookie\b|\bauthorization\b|provider_timeout|MarketCache|local_db|fixture|mock|synthetic|generatedCandidates|failedCandidates/i;

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

function walkKeys(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.flatMap(walkKeys);
  }
  if (value && typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>).flatMap(([key, entry]) => [key, ...walkKeys(entry)]);
  }
  return [];
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
      const summaryCoreRow = page.getByTestId('portfolio-summary-core-row');
      const summaryAuxRow = page.getByTestId('portfolio-summary-aux-row');
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
      await expect(summaryCoreRow).toBeVisible({ timeout: 15_000 });
      await expect(summaryAuxRow).toBeVisible({ timeout: 15_000 });
      await expect(summaryCoreRow).toContainText('总市值');
      await expect(summaryCoreRow).toContainText('总盈亏');
      await expect(summaryAuxRow).toContainText('总现金');
      await expect(summaryAuxRow).toContainText('持仓');
      await expect(summaryAuxRow).toContainText('风险状态');
      await expect(summaryAuxRow).toContainText('状态快照');
      await expect(primaryLane).toBeVisible({ timeout: 15_000 });
      await expect(secondaryLane).toBeVisible({ timeout: 15_000 });
      await expect(activityLane).toBeVisible({ timeout: 15_000 });
      await expect(manualLane).toBeVisible({ timeout: 15_000 });
      await expect(holdingsPanel).toBeVisible({ timeout: 15_000 });
      await expect(riskPanel).toBeVisible({ timeout: 15_000 });
      await expect(activityPanel).toBeVisible({ timeout: 15_000 });
      await expect(manualPanel).toContainText('手工记账入口');
      await expect(activityPanel).toContainText('历史记录');

      const heroBox = await accountHero.boundingBox();
      const summaryCoreBox = await summaryCoreRow.boundingBox();
      const summaryAuxBox = await summaryAuxRow.boundingBox();
      const primaryBox = await primaryLane.boundingBox();
      const secondaryBox = await secondaryLane.boundingBox();
      const activityBox = await activityLane.boundingBox();
      const manualLaneBox = await manualLane.boundingBox();
      expect(heroBox?.y ?? Infinity).toBeLessThan(viewport.name === 'mobile' ? viewport.height * 0.38 : 280);
      expect(summaryCoreBox?.y ?? Infinity).toBeLessThan(summaryAuxBox?.y ?? 0);
      const summaryTypeScale = await page.evaluate(() => {
        const readFontSize = (testId: string) => {
          const element = document.querySelector(`[data-testid="${testId}"]`);
          return element ? Number.parseFloat(window.getComputedStyle(element).fontSize) : 0;
        };
        return {
          marketValue: readFontSize('portfolio-summary-market-value'),
          pnlValue: readFontSize('portfolio-summary-pnl-value'),
          cashValue: readFontSize('portfolio-summary-cash-value'),
        };
      });
      expect(summaryTypeScale.marketValue).toBeGreaterThan(summaryTypeScale.cashValue);
      expect(summaryTypeScale.pnlValue).toBeGreaterThan(summaryTypeScale.cashValue);
      const titleTypeScale = await page.evaluate(() => {
        const pageTitle = document.querySelector('[data-testid="portfolio-total-assets-card"] h1');
        const visibleSectionHeadings = Array.from(document.querySelectorAll('h2')).filter((element) => {
          const rect = element.getBoundingClientRect();
          return rect.width > 0 && rect.height > 0;
        });
        const pageTitleFontSize = pageTitle ? Number.parseFloat(window.getComputedStyle(pageTitle).fontSize) : 0;
        const maxSectionHeadingFontSize = Math.max(
          0,
          ...visibleSectionHeadings.map((element) => Number.parseFloat(window.getComputedStyle(element).fontSize)),
        );

        return { pageTitleFontSize, maxSectionHeadingFontSize };
      });
      expect(titleTypeScale.pageTitleFontSize).toBeGreaterThan(titleTypeScale.maxSectionHeadingFontSize);

      if (viewport.name === 'desktop') {
        expect(primaryBox).not.toBeNull();
        expect(secondaryBox).not.toBeNull();
        expect(activityBox).not.toBeNull();
        expect(manualLaneBox).not.toBeNull();

        expect((primaryBox?.width ?? 0) / Math.max(1, secondaryBox?.width ?? 0)).toBeGreaterThan(1.35);
        expect((activityBox?.width ?? 0) / Math.max(1, manualLaneBox?.width ?? 0)).toBeGreaterThan(1.35);
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
      const bodyText = await page.locator('body').innerText();
      expect(bodyText).not.toMatch(forbiddenInternalLeakagePattern);
      await expectNoHorizontalOverflow(page);
      expect(consoleErrors).toEqual([]);
      expect(pageErrors).toEqual([]);
      expect(harness.requests.count('GET', '/api/v1/portfolio/snapshot')).toBeGreaterThan(0);
      expect(harness.requests.count('GET', '/api/v1/portfolio/risk')).toBeGreaterThan(0);
      expect(harness.requests.calls.filter((entry) => entry.startsWith('POST '))).toEqual([]);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    });
  }

  test('runs bounded portfolio scenario risk smoke inside the risk rail', async ({ page }) => {
    const consoleErrors: string[] = [];
    const pageErrors: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error') {
        consoleErrors.push(message.text());
      }
    });
    page.on('pageerror', (error) => pageErrors.push(error.message));

    await page.setViewportSize({ width: 1440, height: 1000 });
    const harness = await installPortfolioSmokeHarness(page);
    await page.goto('/zh/portfolio');
    await page.waitForLoadState('domcontentloaded');
    await waitForPortfolioSurface(page);

    const riskPanel = page.getByTestId('portfolio-risk-card');
    const disclosure = page.getByTestId('portfolio-scenario-risk-disclosure');
    await expect(riskPanel).toContainText('查看压力情景');
    await expect(riskPanel).toContainText('默认折叠，只使用当前页面可见持仓。');
    await expect(disclosure).not.toHaveAttribute('open');

    const riskBox = await riskPanel.boundingBox();
    const disclosureBox = await disclosure.boundingBox();
    expect(riskBox).not.toBeNull();
    expect(disclosureBox).not.toBeNull();
    expect((disclosureBox?.x ?? 0) + 1).toBeGreaterThanOrEqual(riskBox?.x ?? Infinity);
    expect((disclosureBox?.y ?? 0) + 1).toBeGreaterThanOrEqual(riskBox?.y ?? Infinity);
    expect((disclosureBox?.x ?? 0) + (disclosureBox?.width ?? 0)).toBeLessThanOrEqual((riskBox?.x ?? 0) + (riskBox?.width ?? 0) + 1);

    const trigger = disclosure.locator('button').first();
    await expect(trigger).toHaveAttribute('aria-label', '展开 查看压力情景');
    await disclosure.scrollIntoViewIfNeeded();
    await trigger.evaluate((element: HTMLButtonElement) => element.click());
    await expect(disclosure).toHaveAttribute('open', '');

    await page.getByLabel('冲击幅度（%）').fill('-8');
    await page.getByRole('button', { name: '运行压力情景' }).click();

    const resultPanel = page.getByTestId('portfolio-scenario-risk-result');
    await expect(resultPanel).toBeVisible({ timeout: 10_000 });
    await expect(resultPanel).toContainText('预估影响');
    await expect(resultPanel).toContainText('覆盖范围与缺口会显式展示，不会替你推断缺失暴露。');
    await expect(resultPanel).toContainText('数据不足 / 需补充映射');
    await expect(resultPanel).toContainText('现金缓冲');
    await expect(resultPanel).toContainText('USD cash');
    await expect(resultPanel).toContainText('theme_mapping_pending');
    await expect(resultPanel).toContainText('scenario_coverage_incomplete');
    await expect(resultPanel).toContainText('不触发经纪商同步');
    await expect(resultPanel).toContainText('不改动账务结果');
    await expect(resultPanel).toContainText('不触发任何下单');
    await expect(resultPanel).toContainText('不构成投资建议');

    expect(harness.requests.count('POST', '/api/v1/portfolio/scenario-risk')).toBe(1);
    expect(harness.scenarioRiskPayloads).toHaveLength(1);
    expect(harness.scenarioRiskPayloads[0]).toEqual({
      asOf: '2026-04-15',
      positions: [
        {
          symbol: 'AAPL',
          weightPct: 100,
          marketValue: 1600,
          marketValueBase: 1600,
          bucketLabel: 'Launch Owner Main',
          currency: 'USD',
        },
      ],
      exposures: [],
      scenarioShocks: [
        {
          name: 'symbol_aapl_down_-8',
          shocks: {
            AAPL: {
              shockPct: -8,
            },
          },
        },
      ],
    });

    const sentPayloadText = JSON.stringify(harness.scenarioRiskPayloads[0]);
    expect(sentPayloadText).not.toMatch(/accountId|broker|providerRefresh|syncToken|order|trade|portfolioMutation/i);
    expect(walkKeys(harness.scenarioRiskPayloads[0])).not.toEqual(
      expect.arrayContaining(['accountId', 'broker', 'providerRefresh', 'syncToken', 'orderId', 'tradeId', 'portfolioMutation']),
    );

    const resultBox = await resultPanel.boundingBox();
    expect(resultBox).not.toBeNull();
    expect((resultBox?.x ?? 0) + 1).toBeGreaterThanOrEqual(riskBox?.x ?? Infinity);
    expect((resultBox?.x ?? 0) + (resultBox?.width ?? 0)).toBeLessThanOrEqual((riskBox?.x ?? 0) + (riskBox?.width ?? 0) + 1);

    await expectNoHorizontalOverflow(page);
    expect(consoleErrors).toEqual([]);
    expect(pageErrors).toEqual([]);
    await page.unrouteAll({ behavior: 'ignoreErrors' });
  });
});
