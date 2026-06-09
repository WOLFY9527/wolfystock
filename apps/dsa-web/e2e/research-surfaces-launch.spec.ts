import { test as appTest, expect as appExpect } from './fixtures/appSmoke';
import type { Locator, Page } from '@playwright/test';
import {
  expectNoHorizontalOverflow,
  openProductRouteWithHarness,
  test as productTest,
  expect as productExpect,
} from './fixtures/productAuth';

const viewports = [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
];

async function expectBefore(
  first: Locator,
  second: Locator,
) {
  const firstBox = await first.boundingBox();
  const secondBox = await second.boundingBox();
  productExpect(firstBox).not.toBeNull();
  productExpect(secondBox).not.toBeNull();
  productExpect(firstBox?.y ?? 0).toBeLessThan(secondBox?.y ?? Number.POSITIVE_INFINITY);
}

async function installAuthenticatedAppSmokeSession(page: Page) {
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
}

productTest.describe('Options Lab launch research surface', () => {
  productTest('keeps conclusion and assumptions ahead of option-chain detail', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await openProductRouteWithHarness(page, '/options-lab');

      const decision = page.getByTestId('options-lab-decision-engine');
      const assumptions = page.getByTestId('options-lab-assumptions-panel');
      const chainPanel = page.getByTestId('options-lab-chain-panel').first();
      const strategyDetails = page.getByTestId('options-lab-analysis-details');

      await productExpect(page.getByRole('heading', { name: '期权实验室' })).toBeVisible();
      await productExpect(decision).toBeVisible();
      await productExpect(decision).toContainText('情景判断');
      await productExpect(decision).toContainText('判断指标');
      await productExpect(page.getByTestId('options-lab-risk-boundary-panel')).toContainText('风险边界');
      await productExpect(decision).toContainText('演示/延迟数据');
      await productExpect(assumptions).toBeVisible();
      await productExpect(chainPanel).toBeVisible();
      await productExpect(strategyDetails.getByRole('button', { name: /展开/ })).toHaveAttribute('aria-expanded', 'false');
      await expectBefore(assumptions, decision);
      await expectBefore(decision, chainPanel);

      const heroBox = await page.getByTestId('options-lab-product-hero').boundingBox();
      productExpect(heroBox?.y ?? viewport.height).toBeLessThan(viewport.height);
      await productExpect(page.getByTestId('options-lab-product-hero')).toContainText('期权数据暂不可用，情景分析已暂停。');
      await productExpect(page.getByTestId('options-lab-product-hero')).toContainText('不构成执行指令');
      await expectNoHorizontalOverflow(page);

      await productExpect(page.getByTestId('options-lab-calls-table')).toBeVisible();
      await strategyDetails.getByRole('button', { name: /展开/ }).click();
      await productExpect(strategyDetails.getByRole('button', { name: /收起/ })).toHaveAttribute('aria-expanded', 'true');
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });
});

appTest.describe('Backtest result launch research surface', () => {
  appTest('keeps KPI conclusion ahead of evidence, exports, trace, and ledger detail', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await installAuthenticatedAppSmokeSession(page);
      await page.goto('/zh/backtest/results/34');
      await page.waitForLoadState('domcontentloaded');

      const hero = page.getByTestId('deterministic-result-page-hero');
      const kpis = page.getByTestId('deterministic-result-kpi-strip');
      const summary = page.getByTestId('backtest-report-summary');
      const resultSummary = page.getByTestId('backtest-report-result-summary');
      const chart = page.getByTestId('backtest-report-chart');
      const tradeTable = page.getByTestId('backtest-report-trade-table');
      const evidence = page.getByTestId('backtest-report-evidence-details');
      const dataQuality = page.getByTestId('backtest-report-data-quality');
      const advancedDetails = page.getByTestId('backtest-report-advanced-details');
      const secondaryActions = page.getByTestId('deterministic-result-secondary-actions');

      await appExpect(hero).toBeVisible({ timeout: 15_000 });
      await appExpect(kpis).toBeVisible();
      await appExpect(summary).toBeVisible();
      await appExpect(resultSummary).toContainText('研究结论');
      await appExpect(resultSummary).toContainText('总收益');
      await appExpect(resultSummary).toContainText('最大回撤');
      await appExpect(resultSummary).toContainText('交易次数');
      await appExpect(resultSummary).toContainText('诊断材料');
      await appExpect(secondaryActions).toBeVisible();
      await appExpect(evidence).not.toHaveJSProperty('open', true);
      await expectNoHorizontalOverflow(page);

      const kpiBox = await kpis.boundingBox();
      appExpect(kpiBox?.y ?? viewport.height).toBeLessThan(viewport.height);
      await expectBefore(summary, chart);
      await expectBefore(chart, tradeTable);
      await expectBefore(tradeTable, evidence);
      await appExpect(page.getByTestId('backtest-report-ledger-table')).toHaveCount(0);

      await evidence.locator('summary').click();
      await appExpect(evidence).toHaveJSProperty('open', true);
      await appExpect(dataQuality).toBeVisible();
      await appExpect(advancedDetails).toBeVisible();
      await advancedDetails.getByRole('button').first().click();
      await appExpect(page.getByText(/执行明细仅提供导出/)).toBeVisible();
      await advancedDetails.getByRole('button', { name: /展开每日账本/ }).click();
      await appExpect(page.getByTestId('backtest-report-ledger-table')).toBeVisible();
    }
  });
});
