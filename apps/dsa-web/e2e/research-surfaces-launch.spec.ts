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
      const assumptions = page.getByTestId('options-lab-assumptions-row');
      const chainDetails = page.getByTestId('options-lab-chain-details');
      const strategyDetails = page.getByTestId('options-lab-strategy-details');

      await productExpect(page.getByRole('heading', { name: '期权实验室' })).toBeVisible();
      await productExpect(decision).toBeVisible();
      await productExpect(decision).toContainText('情景结论');
      await productExpect(decision).toContainText('数据准备度');
      await productExpect(decision).toContainText('主要风险边界');
      await productExpect(decision).toContainText('演示/延迟数据');
      await productExpect(assumptions).toBeVisible();
      await productExpect(chainDetails).not.toHaveJSProperty('open', true);
      await productExpect(strategyDetails).not.toHaveJSProperty('open', true);
      await expectBefore(decision, assumptions);
      await expectBefore(assumptions, chainDetails);

      const decisionBox = await decision.boundingBox();
      productExpect(decisionBox?.y ?? viewport.height).toBeLessThan(viewport.height);
      await expectNoHorizontalOverflow(page);

      await chainDetails.locator('summary').click();
      await productExpect(page.getByTestId('options-lab-calls-table')).toBeVisible();
      await strategyDetails.locator('summary').filter({ hasText: '策略对比明细' }).click();
      await productExpect(page.getByTestId('options-lab-strategy-comparison')).toBeVisible();
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

      const hero = page.getByTestId('deterministic-result-page-bento-hero');
      const kpis = page.getByTestId('deterministic-result-kpi-bento');
      const summary = page.getByTestId('backtest-report-summary');
      const chart = page.getByTestId('backtest-report-chart');
      const tradeTable = page.getByTestId('backtest-report-trade-table');
      const evidence = page.getByTestId('backtest-report-evidence-details');
      const secondaryActions = page.getByTestId('deterministic-result-secondary-actions');

      await appExpect(hero).toBeVisible({ timeout: 15_000 });
      await appExpect(kpis).toBeVisible();
      await appExpect(summary).toBeVisible();
      await appExpect(summary).toContainText('研究结论');
      await appExpect(summary).toContainText('表现');
      await appExpect(summary).toContainText('回撤');
      await appExpect(summary).toContainText('交易');
      await appExpect(summary).toContainText('可靠性');
      await appExpect(secondaryActions).not.toHaveJSProperty('open', true);
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
      await page.getByRole('button', { name: /开发者细节/ }).click();
      await appExpect(page.getByText(/原始执行轨迹仅提供导出/)).toBeVisible();
      await page.getByRole('button', { name: /展开每日账本/ }).click();
      await appExpect(page.getByTestId('backtest-report-ledger-table')).toBeVisible();
    }
  });
});
