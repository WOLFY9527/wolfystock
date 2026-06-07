import { expect, test, type Page, type Route } from '@playwright/test';
import { installPortfolioSmokeHarness } from './fixtures/portfolioSmoke';

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function installPortfolioEmptyHarness(page: Page) {
  await page.route('**/api/v1/portfolio/snapshot**', async (route) => {
    await fulfillJson(route, {
      as_of: '2026-04-15',
      cost_method: 'fifo',
      currency: 'USD',
      account_count: 1,
      realized_pnl: 0,
      unrealized_pnl: 0,
      fee_total: 0,
      tax_total: 0,
      fx_stale: false,
      total_cash: 5000,
      total_market_value: 0,
      total_equity: 5000,
      accounts: [
        {
          account_id: 1,
          account_name: 'Launch Owner Main',
          owner_id: 'user-1',
          broker: 'IBKR',
          market: 'us',
          base_currency: 'USD',
          as_of: '2026-04-15',
          cost_method: 'fifo',
          total_cash: 5000,
          total_market_value: 0,
          total_equity: 5000,
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

async function openPortfolioEmptyState(page: Page) {
  await installPortfolioSmokeHarness(page);
  await installPortfolioEmptyHarness(page);
  await page.goto('/zh/portfolio');
  await page.waitForLoadState('domcontentloaded');
  await expect(page.getByTestId('portfolio-bento-page')).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId('portfolio-start-card')).toBeVisible();
}

test.describe('portfolio empty-state CTA', () => {
  test('suppresses duplicate header CTAs on desktop while keeping the empty-state actions', async ({ page }) => {
    const consoleErrors: string[] = [];
    const pageErrors: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error') {
        consoleErrors.push(message.text());
      }
    });
    page.on('pageerror', (error) => pageErrors.push(error.message));

    await page.setViewportSize({ width: 1440, height: 1000 });
    await openPortfolioEmptyState(page);

    const commandStrip = page.getByTestId('portfolio-command-strip');
    const emptyWorkflowColumn = page.getByTestId('portfolio-empty-workflow-column');

    await expect(commandStrip.getByRole('button', { name: '添加持仓' })).toHaveCount(0);
    await expect(commandStrip.getByRole('button', { name: '导入记录' })).toHaveCount(0);
    await expect(commandStrip.getByRole('button', { name: '同步数据' })).toHaveCount(0);
    await expect(emptyWorkflowColumn.getByRole('button', { name: '添加持仓' })).toHaveCount(1);
    await expect(emptyWorkflowColumn.getByRole('button', { name: '导入记录' })).toHaveCount(1);
    await expect(emptyWorkflowColumn).toContainText('完成后可在右侧查看风险与数据说明。');
    await expectNoHorizontalOverflow(page);
    expect(consoleErrors).toEqual([]);
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
    await openPortfolioEmptyState(page);

    const commandStrip = page.getByTestId('portfolio-command-strip');
    const emptyWorkflowColumn = page.getByTestId('portfolio-empty-workflow-column');

    await expect(commandStrip.getByRole('button', { name: '添加持仓' })).toHaveCount(0);
    await expect(commandStrip.getByRole('button', { name: '导入记录' })).toHaveCount(0);
    await expect(commandStrip.getByRole('button', { name: '同步数据' })).toHaveCount(0);
    await expect(emptyWorkflowColumn.getByRole('button', { name: '添加持仓' })).toHaveCount(1);
    await expect(emptyWorkflowColumn.getByRole('button', { name: '导入记录' })).toHaveCount(1);
    await expectNoHorizontalOverflow(page);

    const layout = await emptyWorkflowColumn.evaluate((node) => {
      const element = node as HTMLElement;
      const startCard = element.querySelector('[data-testid="portfolio-start-card"]') as HTMLElement | null;
      const actionRow = element.querySelector('.mt-3.flex.flex-wrap.gap-2') as HTMLElement | null;
      const helpText = element.querySelector('[data-testid="portfolio-empty-help"]') as HTMLElement | null;

      if (!startCard || !actionRow || !helpText) {
        return null;
      }

      const startRect = startCard.getBoundingClientRect();
      const actionRect = actionRow.getBoundingClientRect();
      const helpRect = helpText.getBoundingClientRect();

      return {
        actionTop: actionRect.top,
        cardBottom: startRect.bottom,
        helpTop: helpRect.top,
        actionBottom: actionRect.bottom,
      };
    });

    expect(layout).not.toBeNull();
    expect(layout?.actionTop ?? 0).toBeGreaterThanOrEqual((layout?.cardBottom ?? 0) - 1);
    expect(layout?.helpTop ?? 0).toBeGreaterThanOrEqual((layout?.actionBottom ?? 0) - 1);
    expect(consoleErrors).toEqual([]);
    expect(pageErrors).toEqual([]);
    await page.unrouteAll({ behavior: 'ignoreErrors' });
  });
});
