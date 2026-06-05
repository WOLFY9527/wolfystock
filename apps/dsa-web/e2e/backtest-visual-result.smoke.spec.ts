import type { Page, Route } from '@playwright/test';
import { expect, test } from './fixtures/appSmoke';

const desktopViewport = { width: 1440, height: 1000 };
const narrowViewport = { width: 390, height: 844 };

const forbiddenInternalPattern =
  /raw\s+(payload|response|schema|prompt|trace)|debug\s+(payload|response|schema|prompt|panel)|provider\s+(route|payload|response)|cache\s+(router|payload|response)|stack\s+trace|traceback|internal\s+reasoning|sourceAuthority|providerRoute|api[_\s-]?key\s*[=:]|password\s*[=:]|session[_\s-]?id\s*[=:]|secret\s*[=:]|bearer\s+[a-z0-9._-]+|sk-[a-z0-9_-]{12,}/i;
const forbiddenExecutionPattern =
  /买入按钮|建议买入|建议卖出|立即交易|提交订单|连接券商|连接经纪商|真实下单|立即下单|place order|submit order|connect broker|broker CTA|must buy|must sell|buy now|sell now|AI recommends you buy/i;

const signedInUser = {
  id: 'user-1',
  username: 'wolfy-user',
  displayName: 'Wolfy User',
  role: 'user',
  isAdmin: false,
  isAuthenticated: true,
  transitional: false,
  authEnabled: true,
};

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function installSignedInSessionRoutes(page: Page) {
  await page.route('**/api/v1/auth/status**', async (route) => {
    await fulfillJson(route, {
      authEnabled: true,
      loggedIn: true,
      passwordSet: true,
      passwordChangeable: true,
      setupState: 'enabled',
      currentUser: signedInUser,
    });
  });

  await page.route('**/api/v1/auth/me**', async (route) => {
    await fulfillJson(route, signedInUser);
  });
}

async function expectNoHorizontalOverflow(page: Parameters<typeof test>[0]['page']) {
  await expect
    .poll(async () => page.evaluate(() => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)))
    .toBeLessThanOrEqual(1);
}

async function expectConsumerSafeText(locator: ReturnType<Parameters<typeof test>[1]>['page']['locator']) {
  const text = await locator.innerText();
  expect(text).not.toMatch(forbiddenInternalPattern);
  expect(text).not.toMatch(forbiddenExecutionPattern);
}

test.describe('Backtest visual result smoke', () => {
  test('shows research-only result visuals without leakage or trading CTA copy', async ({ page }) => {
    for (const viewport of [desktopViewport, narrowViewport]) {
      await page.setViewportSize(viewport);
      await installSignedInSessionRoutes(page);
      await page.goto('/zh/backtest/results/34');
      await page.waitForLoadState('domcontentloaded');

      const pageShell = page.getByTestId('deterministic-backtest-result-page');
      const report = page.getByTestId('backtest-result-report');
      const summary = page.getByTestId('backtest-report-summary');
      const chartShell = page.getByTestId('deterministic-result-chart-shell');
      const chartWorkspace = page.getByTestId('deterministic-backtest-chart-workspace');
      const chartPanel = page.getByTestId('backtest-report-chart');
      const dashboardStage = page.getByTestId('deterministic-result-page-dashboard-stage');
      const riskDiagnostics = page.getByTestId('backtest-report-risk-diagnostics');
      const researchReview = page.getByTestId('backtest-report-research-quality-review');
      const evidenceDetails = page.getByTestId('backtest-report-evidence-details');
      const tradeTable = page.getByTestId('backtest-report-trade-table');
      const parametersTab = page.getByRole('tab', { name: '参数与假设' });
      const parameterMatrix = page.getByTestId('backtest-parameter-matrix');

      await expect(pageShell).toBeVisible({ timeout: 15_000 });
      await expect(report).toBeVisible();
      await expect(summary).toBeVisible();
      await expect(summary).toContainText('研究结论');
      await expect(summary).toContainText('非真实成交记录');
      await expect(chartPanel).toBeVisible();
      await expect(chartShell).toBeVisible();
      await expect(chartWorkspace).toBeVisible();
      await expect(chartWorkspace).toHaveAttribute('data-row-count', /[1-9]\d*/);
      await expect(chartWorkspace).toContainText('权益曲线 / 回撤 / 每日盈亏');
      await expect(chartWorkspace).toContainText('回撤');
      await expect(chartWorkspace).toContainText('日盈亏');
      await expect(dashboardStage).toBeVisible();
      await expect(riskDiagnostics).toBeVisible();
      await expect(riskDiagnostics).toContainText('回撤与压力解释');
      await expect(riskDiagnostics).toContainText('最大回撤');
      await expect(researchReview).toBeVisible();
      await expect(researchReview).toContainText('研究复核清单');
      await expect(researchReview).toContainText('反过拟合门禁');
      await expect(researchReview).toContainText('不代表样本外验证已完成');
      await expect(tradeTable).toBeVisible();
      await expect(report).toContainText('模拟买入事件');
      await expect(report).toContainText('模拟卖出事件');

      await expect(report).toContainText('仅用于复盘模拟执行路径');
      await expect(report).toContainText('模拟事件仅用于回测复盘，不构成交易指令');
      await expect(report).toContainText('不构成交易指令');
      await expect(evidenceDetails).toContainText('数据质量、执行假设和每日账本默认折叠');
      await expect(evidenceDetails).not.toHaveJSProperty('open', true);

      await expectConsumerSafeText(summary);
      await expectConsumerSafeText(chartPanel);
      await expectConsumerSafeText(riskDiagnostics);
      await expectConsumerSafeText(researchReview);
      await expectConsumerSafeText(tradeTable);

      await parametersTab.click();
      await expect(parameterMatrix).toBeVisible();
      await expect(parameterMatrix).toContainText('初始资金');
      await expect(parameterMatrix).toContainText('回看范围');
      await expect(parameterMatrix).toContainText('手续费 / 滑点');

      await expect(page.getByText(/mock-canary-place-order-payload/i)).toHaveCount(0);
      await expect(page.getByText(/mock-canary-broker-credentials/i)).toHaveCount(0);
      await expect(page.getByText(/mock-canary-raw-provider-payload/i)).toHaveCount(0);
      await expect(page.getByText(/debug|traceback|api[_\s-]?key|session[_\s-]?id/i)).toHaveCount(0);

      if (viewport.width <= 390) {
        await expectNoHorizontalOverflow(page);
      }

      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });
});
