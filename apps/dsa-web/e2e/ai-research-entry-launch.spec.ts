import { expect, test, type Page, type Route } from '@playwright/test';
import type { AnalysisReport } from '../src/types/analysis';

const viewports = [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
];

const forbiddenTradeActionPattern =
  /买入按钮|下单|立即交易|必买|稳赚|保证收益|理想买点|理想买入|二次买入|次级买点|止损|止盈|目标价|目标位|目标区间|仓位建议|guaranteed|best contract|AI recommends you buy|must buy|must sell|buy now|sell now|place order|you should buy|you should sell|ideal entry|secondary entry|stop loss|take profit|target zone|position sizing/i;
const rawProviderDebugPattern = /raw\s+(payload|provider)|debug\s+(payload|schema)|provider\s+payload|api[_\s-]?key|secret\s*[=:]|bearer\s+[a-z0-9._-]+/i;

const homeReportFixture: AnalysisReport = {
  meta: {
    id: 3,
    queryId: 'home-report-orcl',
    stockCode: 'ORCL',
    stockName: 'Oracle',
    companyName: 'Oracle Corporation',
    reportType: 'detailed',
    createdAt: '2026-05-09T08:00:00Z',
    reportGeneratedAt: '2026-05-09T08:03:00Z',
  },
  summary: {
    analysisSummary: 'Cloud backlog remains a research observation point.',
    operationAdvice: 'Continue observing.',
    trendPrediction: 'Research context remains constructive.',
    sentimentScore: 74,
  },
  details: {
    standardReport: {
      summaryPanel: {
        stock: 'Oracle Corporation',
        ticker: 'ORCL',
        score: 74,
        oneSentence: 'Cloud backlog remains a research observation point.',
        timeSensitivity: 'Short horizon',
      },
      decisionPanel: {
        confidence: 'Moderate',
        marketStructure: 'Evidence remains incomplete.',
        buildStrategy: 'Continue observing the research packet.',
      },
      reasonLayer: {
        topRisk: 'Fundamental coverage remains partial.',
        topCatalyst: 'Cloud backlog remains stable.',
      },
      coverageNotes: {
        coverageGaps: ['Earnings evidence remains incomplete.'],
        methodNotes: ['Research context only; not investment advice.'],
      },
    },
  },
  decisionTrace: {
    symbol: 'ORCL',
    market: 'US',
    generatedAt: '2026-05-09T08:03:00Z',
    dataSources: [{ name: 'Research packet', status: 'used' }],
  },
};

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function installAiResearchHarness(page: Page) {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (method === 'GET' && path === '/api/v1/auth/status') {
      return fulfillJson(route, {
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
      });
    }
    if (method === 'GET' && path === '/api/v1/auth/me') {
      return fulfillJson(route, {
        id: 'user-1',
        username: 'wolfy-user',
        displayName: 'Wolfy User',
        role: 'user',
        isAdmin: false,
        isAuthenticated: true,
        transitional: false,
        authEnabled: true,
      });
    }
    if (method === 'GET' && path === '/api/v1/history') {
      return fulfillJson(route, {
        total: 1,
        page: 1,
        limit: 20,
        items: [{
          id: 3,
          queryId: homeReportFixture.meta.queryId,
          stockCode: homeReportFixture.meta.stockCode,
          stockName: homeReportFixture.meta.stockName,
          companyName: homeReportFixture.meta.companyName,
          createdAt: homeReportFixture.meta.createdAt,
          generatedAt: homeReportFixture.meta.reportGeneratedAt,
          isTest: false,
        }],
      });
    }
    if (method === 'GET' && path === '/api/v1/history/3') {
      return fulfillJson(route, homeReportFixture);
    }
    if (method === 'GET' && path === '/api/v1/stocks/ORCL/evidence') {
      return fulfillJson(route, {
        stockEvidencePacket: {
          notInvestmentAdvice: true,
          confidenceCap: { value: 40 },
          claimBoundaries: [{ claim: 'direct_trade_action', allowed: false }],
          sourceRefs: [],
          dataGaps: [],
        },
      });
    }
    if (method === 'GET' && path === '/api/v1/stocks/ORCL/history') {
      return fulfillJson(route, {
        stockCode: 'ORCL',
        stockName: 'Oracle',
        period: 'daily',
        data: [
          { date: '2026-05-06', open: 120.2, high: 121.1, low: 119.8, close: 120.8, volume: 1200000 },
          { date: '2026-05-07', open: 120.8, high: 122.4, low: 120.5, close: 121.9, volume: 1320000 },
          { date: '2026-05-08', open: 121.9, high: 123.2, low: 121.1, close: 122.7, volume: 1410000 },
        ],
      });
    }
    if (method === 'GET' && path === '/api/v1/market/market-briefing') {
      return fulfillJson(route, {
        source: 'computed',
        updated_at: '2026-05-09T08:03:00Z',
        items: [],
      });
    }
    if (method === 'GET' && path === '/api/v1/dashboard/market-intelligence-overview') {
      return fulfillJson(route, {
        status: 'unavailable',
        as_of: '2026-05-09T08:03:00Z',
        market_pulse: {
          sp500: { label: 'S&P 500', value: '--', change: '--', status: 'unavailable' },
          nasdaq: { label: 'Nasdaq', value: '--', change: '--', status: 'unavailable' },
          russell2000: { label: 'Russell 2000', value: '--', change: '--', status: 'unavailable' },
          vix: { label: 'VIX', value: '--', change: '--', status: 'unavailable' },
          ten_year_yield: { label: '10Y yield', value: '--', change: '--', status: 'unavailable' },
          dollar_index: { label: 'Dollar index', value: '--', change: '--', status: 'unavailable' },
          market_breadth: { summary: 'Market breadth is unavailable.', status: 'unavailable' },
          liquidity_state: 'Unavailable',
        },
        market_brief: { headline: 'Market context unavailable.', summary: 'Research continues with report evidence only.', status: 'unavailable' },
        money_flow: { top_inflows: [], top_outflows: [], style_bias: 'Unavailable', offensive_defensive_bias: 'Unavailable', source_status: 'unavailable', status: 'unavailable' },
        liquidity_risk: { summary: 'Liquidity context unavailable.', volatility_tone: 'Unavailable', funding_stress: 'Unavailable', dollar_rate_pressure: 'Unavailable', status: 'unavailable' },
        sector_theme_rotation: { leading_themes: [], lagging_themes: [], diffusion: 'Unavailable', summary: 'Theme rotation unavailable.', status: 'unavailable' },
        research_queue: { status: 'unavailable', items: [] },
        data_quality: { state: 'unavailable', label: 'Unavailable', summary: 'Market context unavailable.', sections: {} },
        no_advice_disclosure: 'Research context only; not investment advice.',
      });
    }
    if (method === 'GET' && path === '/api/v1/stocks/ORCL/structure-decision') {
      return fulfillJson(route, {});
    }
    if (method === 'GET' && path === '/api/v1/analysis/tasks') {
      return fulfillJson(route, { tasks: [], total: 0 });
    }
    if (method === 'GET' && path === '/api/v1/analysis/tasks/stream') {
      return route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: 'event: heartbeat\ndata: {}\n\n',
      });
    }
    if (method === 'GET' && path === '/api/v1/agent/skills') {
      return fulfillJson(route, {
        skills: [
          { id: 'bull_trend', name: '趋势观察', description: '只读趋势观察' },
          { id: 'ma_cross', name: '均线系统', description: '均线结构复核' },
          { id: 'leader_strategy', name: '龙头策略', description: '相对强度观察' },
        ],
        default_skill_id: 'bull_trend',
      });
    }
    if (method === 'GET' && path === '/api/v1/agent/models') {
      return fulfillJson(route, {
        models: [{ deployment_id: 'auto', model: 'research-auto', provider: 'Wolfy', source: 'fixture', is_primary: true }],
      });
    }
    if (method === 'GET' && path === '/api/v1/agent/provider-health') {
      return fulfillJson(route, {
        routingMode: 'AUTO',
        currentProvider: 'Wolfy',
        currentModel: 'research-auto',
        providers: [{ id: 'wolfy', label: 'Wolfy', status: 'available', model: 'research-auto', selected: true }],
      });
    }
    if (method === 'GET' && path === '/api/v1/watchlist') {
      return fulfillJson(route, { items: [] });
    }
    if (method === 'GET' && path === '/api/v1/portfolio/snapshot') {
      return fulfillJson(route, { asOf: '2026-05-09', accounts: [] });
    }
    if (method === 'GET' && path === '/api/v1/scanner/recent-watchlists') {
      return fulfillJson(route, { items: [] });
    }
    if (method === 'GET' && path === '/api/v1/backtest/runs') {
      return fulfillJson(route, { total: 0, page: 1, limit: 1, items: [] });
    }

    return fulfillJson(route, { error: `Unhandled AI research harness route: ${method} ${path}` }, 500);
  });
}

async function expectNoHorizontalOverflow(page: Page) {
  await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

async function expectCleanLaunchText(page: Page) {
  const firstViewportText = await page.locator('body').innerText();
  expect(firstViewportText).not.toMatch(forbiddenTradeActionPattern);
  expect(firstViewportText).not.toMatch(rawProviderDebugPattern);
}

test.describe('AI research entry launch surfaces', () => {
  test.beforeEach(async ({ page }) => {
    await installAiResearchHarness(page);
  });

  test('Home report drawer preserves evidence, export, print, Escape, and overflow contracts across viewports', async ({ page, context }) => {
    const consoleErrors: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error' && !message.text().includes('favicon.ico')) {
        consoleErrors.push(message.text());
      }
    });
    page.on('response', (response) => {
      if (response.status() >= 500) {
        consoleErrors.push(`${response.status()} ${response.url()}`);
      }
    });
    page.on('pageerror', (error) => consoleErrors.push(error.message));
    await page.addInitScript(() => {
      window.localStorage.setItem('dsa-selected-history-id', '3');
    });

    for (const viewport of viewports) {
      await page.setViewportSize(viewport);

      await page.goto('/zh');
      await page.waitForLoadState('domcontentloaded');
      await expect(page.getByTestId('home-bento-dashboard')).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('home-bento-research-state-row')).toBeVisible();
      await expect(page.getByTestId('home-bento-card-strategy')).toHaveAttribute('data-research-card', 'research-actions');
      await expect(page.getByTestId('home-bento-card-tech')).toHaveAttribute('data-research-card', 'risk-context');
      await expectNoHorizontalOverflow(page);
      await expectCleanLaunchText(page);

      const fullReportTrigger = page.getByRole('button', { name: '完整报告' });
      await fullReportTrigger.click();
      const reportDrawer = page.getByTestId('home-bento-full-report-drawer');
      const technicalDetails = page.getByTestId('home-bento-full-report-technical-details');
      await expect(reportDrawer).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('home-bento-report-executive-summary')).toBeVisible();
      await expect(reportDrawer).toContainText('AI 洞察仅供参考，不构成投资建议。');
      await expect(technicalDetails).not.toHaveAttribute('open');
      await technicalDetails.locator('summary').click();
      await expect(technicalDetails).toHaveAttribute('open');
      await expectNoHorizontalOverflow(page);
      await expectCleanLaunchText(page);

      if (viewport.width > 390) {
        const origin = new URL(page.url()).origin;
        await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin });
        await reportDrawer.getByRole('button', { name: '复制报告' }).click();
        await expect(reportDrawer.getByRole('button', { name: '已复制' })).toBeVisible();

        const downloadPromise = page.waitForEvent('download');
        await reportDrawer.getByRole('button', { name: '导出 Markdown' }).click();
        const download = await downloadPromise;
        expect(download.suggestedFilename()).toMatch(/^WolfyStock_Oracle-Corporation_ORCL_\d{8}\.md$/);

        const popupPromise = page.waitForEvent('popup');
        await reportDrawer.getByRole('button', { name: '导出 PDF' }).click();
        const printPage = await popupPromise;
        await expect(printPage.locator('#wolfystock-print-report')).toContainText('AI 洞察仅供参考，不构成投资建议。');
        await printPage.close();
      }

      await page.keyboard.press('Escape');
      await expect(reportDrawer).toBeHidden({ timeout: 15_000 });
      await expect(fullReportTrigger).toBeFocused();
    }

    expect(consoleErrors).toEqual([]);
  });
});
