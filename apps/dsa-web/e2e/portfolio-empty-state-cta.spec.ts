import { expect, test, type Page, type Route } from '@playwright/test';
import { installPortfolioSmokeHarness } from './fixtures/portfolioSmoke';

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

type PortfolioTruthFixtureState = 'no_account' | 'account_no_holdings' | 'valuation_unavailable';

async function installPortfolioEmptyHarness(page: Page, truthState: PortfolioTruthFixtureState = 'account_no_holdings') {
  const noAccount = truthState === 'no_account';
  const valuationUnavailable = truthState === 'valuation_unavailable';
  const accountCount = noAccount ? 0 : 1;
  const totalCash = valuationUnavailable ? 0 : 5000;
  const portfolioTruth = noAccount
    ? {
      state: 'no_account',
      account_state: 'no_account',
      valuation_state: 'not_applicable',
      value_semantics: 'not_applicable',
      authoritative_total: null,
      covered_subtotal: null,
      account_count: 0,
      position_count: 0,
    }
    : valuationUnavailable
      ? {
        state: 'valuation_unavailable',
        account_state: 'no_holdings',
        valuation_state: 'unavailable',
        value_semantics: 'unavailable',
        authoritative_total: null,
        covered_subtotal: null,
        account_count: 1,
        position_count: 0,
      }
      : {
        state: 'account_no_holdings',
        account_state: 'no_holdings',
        valuation_state: 'fully_valued',
        value_semantics: 'authoritative_total',
        authoritative_total: 5000,
        covered_subtotal: null,
        account_count: 1,
        position_count: 0,
      };

  if (noAccount) {
    await page.route('**/api/v1/portfolio/accounts**', async (route) => {
      if (route.request().method() === 'GET') {
        await fulfillJson(route, { accounts: [] });
        return;
      }
      await route.fallback();
    });
  }
  await page.route('**/api/v1/portfolio/snapshot**', async (route) => {
    await fulfillJson(route, {
      as_of: '2026-04-15',
      cost_method: 'fifo',
      currency: 'USD',
      account_count: accountCount,
      realized_pnl: 0,
      unrealized_pnl: 0,
      fee_total: 0,
      tax_total: 0,
      fx_stale: false,
      portfolio_truth: portfolioTruth,
      total_cash: totalCash,
      total_market_value: 0,
      total_equity: totalCash,
      accounts: noAccount ? [] : [
        {
          account_id: 1,
          account_name: 'Launch Owner Main',
          owner_id: 'user-1',
          broker: 'IBKR',
          market: 'us',
          base_currency: 'USD',
          as_of: '2026-04-15',
          cost_method: 'fifo',
          total_cash: totalCash,
          total_market_value: 0,
          total_equity: totalCash,
          realized_pnl: 0,
          unrealized_pnl: 0,
          fee_total: 0,
          tax_total: 0,
          fx_stale: false,
          positions: [],
        },
      ],
    });
  });
  await page.route('**/api/v1/portfolio/risk**', async (route) => {
    await fulfillJson(route, {
      as_of: '2026-04-15',
      account_id: null,
      cost_method: 'fifo',
      currency: 'USD',
      thresholds: {},
      concentration: {
        total_market_value: 0,
        top_weight_pct: 0,
        alert: false,
        top_positions: [],
      },
      sector_concentration: {
        total_market_value: 0,
        top_weight_pct: 0,
        alert: false,
        top_sectors: [],
        coverage: {},
        errors: [],
      },
      drawdown: {
        series_points: 0,
        max_drawdown_pct: 0,
        current_drawdown_pct: 0,
        alert: false,
        fx_stale: false,
      },
      stop_loss: {
        near_alert: false,
        triggered_count: 0,
        near_count: 0,
        items: [],
      },
    });
  });
  await page.route('**/api/v1/portfolio/trades**', async (route) => {
    await fulfillJson(route, { items: [], total: 0, page: 1, page_size: 20 });
  });
  await page.route('**/api/v1/portfolio/cash-ledger**', async (route) => {
    await fulfillJson(route, { items: [], total: 0, page: 1, page_size: 20 });
  });
  await page.route('**/api/v1/portfolio/corporate-actions**', async (route) => {
    await fulfillJson(route, { items: [], total: 0, page: 1, page_size: 20 });
  });
}

async function expectNoHorizontalOverflow(page: Page) {
  await expect
    .poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth))
    .toBe(true);
}

async function openPortfolioEmptyState(page: Page, truthState: PortfolioTruthFixtureState = 'account_no_holdings') {
  await installPortfolioSmokeHarness(page);
  await installPortfolioEmptyHarness(page, truthState);
  await page.goto('/zh/portfolio');
  await page.waitForLoadState('domcontentloaded');
  await expect(page.getByTestId('portfolio-bento-page')).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId('portfolio-start-card')).toBeVisible();
}

test.describe('portfolio empty-state CTA', () => {
  test('suppresses operator CTAs on desktop while keeping consumer research entrypoints', async ({ page }) => {
    const consoleErrors: string[] = [];
    const pageErrors: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error') {
        consoleErrors.push(message.text());
      }
    });
    page.on('pageerror', (error) => pageErrors.push(error.message));

    await page.setViewportSize({ width: 1440, height: 1000 });
    await openPortfolioEmptyState(page, 'no_account');

    const commandStrip = page.getByTestId('portfolio-command-strip');
    const emptyWorkflowColumn = page.getByTestId('portfolio-empty-workflow-column');

    await expect(commandStrip.getByRole('button', { name: '添加持仓' })).toHaveCount(0);
    await expect(commandStrip.getByRole('button', { name: '导入记录' })).toHaveCount(0);
    await expect(commandStrip.getByRole('button', { name: '同步数据' })).toHaveCount(0);
    await expect(emptyWorkflowColumn.getByRole('button', { name: '添加持仓' })).toHaveCount(0);
    await expect(emptyWorkflowColumn.getByRole('button', { name: '导入记录' })).toHaveCount(0);
    await expect(emptyWorkflowColumn.getByRole('button', { name: '同步数据' })).toHaveCount(0);
    await expect(emptyWorkflowColumn.getByRole('link', { name: '先看市场概览' })).toHaveAttribute('href', '/zh/market-overview');
    await expect(emptyWorkflowColumn.getByRole('link', { name: '运行 Scanner' })).toHaveAttribute('href', '/zh/scanner');
    await expect(emptyWorkflowColumn.getByRole('link', { name: '查看研究雷达' })).toHaveAttribute('href', '/zh/research/radar');
    await expect(emptyWorkflowColumn).toContainText('首次配置路径');
    await expect(emptyWorkflowColumn).toContainText('保存后会在下方自动展开真实持仓、风险摘要与近期活动。');
    await expect(page.getByTestId('portfolio-start-card')).toContainText('创建或导入首个组合');
    await expect(page.getByTestId('portfolio-total-assets-value')).toHaveText('尚未创建组合');
    await expect(page.getByTestId('portfolio-total-assets-value')).not.toContainText('USD 0.00');
    await expectNoHorizontalOverflow(page);
    expect(consoleErrors.filter((entry) => !entry.includes('ERR_NETWORK_CHANGED'))).toEqual([]);
    expect(pageErrors).toEqual([]);
    await page.unrouteAll({ behavior: 'ignoreErrors' });
  });

  test('keeps the empty-state CTA stack readable at 390px without header duplication', async ({ page }) => {
    const consoleErrors: string[] = [];
    const pageErrors: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error') {
        consoleErrors.push(message.text());
      }
    });
    page.on('pageerror', (error) => pageErrors.push(error.message));

    await page.setViewportSize({ width: 390, height: 844 });
    await openPortfolioEmptyState(page, 'valuation_unavailable');

    const commandStrip = page.getByTestId('portfolio-command-strip');
    const emptyWorkflowColumn = page.getByTestId('portfolio-empty-workflow-column');

    await expect(commandStrip.getByRole('button', { name: '添加持仓' })).toHaveCount(0);
    await expect(commandStrip.getByRole('button', { name: '导入记录' })).toHaveCount(0);
    await expect(commandStrip.getByRole('button', { name: '同步数据' })).toHaveCount(0);
    await expect(emptyWorkflowColumn.getByRole('button', { name: '添加持仓' })).toHaveCount(0);
    await expect(emptyWorkflowColumn.getByRole('button', { name: '导入记录' })).toHaveCount(0);
    await expect(emptyWorkflowColumn.getByRole('link', { name: '先看市场概览' })).toBeVisible();
    await expect(emptyWorkflowColumn.getByRole('link', { name: '查看研究雷达' })).toBeVisible();
    await expect(page.getByTestId('portfolio-total-assets-value')).toHaveText('估值暂不可用');
    await expect(page.getByTestId('portfolio-total-assets-value')).not.toContainText('USD 0.00');
    await expectNoHorizontalOverflow(page);

    const layout = await emptyWorkflowColumn.evaluate((node) => {
      const element = node as HTMLElement;
      const onboardingCta = element.querySelector('[data-testid="portfolio-empty-onboarding-cta"]') as HTMLElement | null;
      const startCard = element.querySelector('[data-testid="portfolio-start-card"]') as HTMLElement | null;
      const helpText = element.querySelector('[data-testid="portfolio-empty-help"]') as HTMLElement | null;

      if (!onboardingCta || !startCard || !helpText) {
        return null;
      }

      const ctaRect = onboardingCta.getBoundingClientRect();
      const startRect = startCard.getBoundingClientRect();
      const helpRect = helpText.getBoundingClientRect();

      return {
        cardTop: startRect.top,
        ctaBottom: ctaRect.bottom,
        helpTop: helpRect.top,
        cardBottom: startRect.bottom,
      };
    });

    expect(layout).not.toBeNull();
    expect(layout?.cardTop ?? 0).toBeGreaterThanOrEqual((layout?.ctaBottom ?? 0) - 1);
    expect(layout?.helpTop ?? 0).toBeGreaterThanOrEqual((layout?.cardBottom ?? 0) - 1);
    expect(consoleErrors).toEqual([]);
    expect(pageErrors).toEqual([]);
    await page.unrouteAll({ behavior: 'ignoreErrors' });
  });
});
