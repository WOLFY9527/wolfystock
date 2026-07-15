import { expect, test, type Page, type Route } from '@playwright/test';
import {
  expectNoHorizontalOverflow,
  fulfillJson,
  installSignedInSessionRoutes,
} from './fixtures/authenticatedRouteSmoke';

const timestamp = '2026-07-08T13:30:00Z';

function symbolFromStockRoute(route: Route): string {
  const pathname = new URL(route.request().url()).pathname;
  const parts = pathname.split('/');
  const stockIndex = parts.indexOf('stocks');
  const symbol = stockIndex >= 0 ? parts[stockIndex + 1] : 'AAPL';
  return decodeURIComponent(symbol || 'AAPL').toUpperCase();
}

function structurePayload(symbol: string) {
  return {
    schema_version: 't267_stock_structure_route_continuity_v1',
    ticker: symbol,
    structure_state: symbol === 'MSFT' ? 'pullback' : 'breakout',
    confidence: 'medium',
    confidence_cap: {
      value: 55,
      label: 'Medium',
      reasons: ['Peer evidence remains incomplete.'],
    },
    confidence_state: {
      status: 'partial',
      label: 'Evidence limited',
      reasons: ['Peer evidence remains incomplete.'],
    },
    component_scores: {
      trend: symbol === 'MSFT' ? 62 : 78,
      relativeStrength: 71,
      evidenceQuality: 45,
    },
    explanation: {
      why_this_structure: `${symbol} price evidence remains bounded by returned history and fixture quote freshness.`,
      what_confirms_it: ['Returned quote and history remain available.'],
      what_invalidates_it: ['Evidence falls out of date.'],
      key_levels: [{ kind: 'support', value: 198.5, description: 'Fixture support level.' }],
    },
    research_notes: {
      watch_next: ['Refresh quote evidence before deeper review.'],
      needs_more_evidence: ['Comparable peer evidence.'],
      risk_flags: ['Evidence is partial.'],
    },
    data_quality: {
      status: 'partial',
      period: 'daily',
      requested_days: 120,
      observed_bars: symbol === 'MSFT' ? 70 : 90,
      usable_bars: symbol === 'MSFT' ? 70 : 90,
      reason: 'Fixture route smoke coverage.',
    },
    missing_evidence: [{ kind: 'peer', message: 'Comparable evidence pending.' }],
    risk_observations: ['Evidence falls out of date.'],
    evidence_gaps: ['Comparable peer evidence.'],
    no_advice_disclosure: 'Research observation only.',
    observation_only: true,
    decision_grade: false,
  };
}

async function installStockStructureHarness(page: Page) {
  const passiveCalls: string[] = [];
  const mutationCalls: string[] = [];

  await installSignedInSessionRoutes(page);

  await page.route('**/api/v1/auth/preferences/notifications**', async (route) => {
    await fulfillJson(route, {
      channel: 'multi',
      enabled: false,
      email: null,
      emailEnabled: false,
      discordEnabled: false,
      discordWebhook: null,
      deliveryAvailable: false,
      emailDeliveryAvailable: false,
      discordDeliveryAvailable: false,
      updatedAt: timestamp,
    });
  });

  await page.route('**/api/v1/stocks/*/validate', async (route) => {
    passiveCalls.push('validate');
    const symbol = symbolFromStockRoute(route);
    await fulfillJson(route, {
      stock_code: symbol,
      normalized_symbol: symbol,
      market: 'us',
      status: 'valid',
      valid: true,
      exists: true,
      stock_name: symbol,
    });
  });

  await page.route('**/api/v1/stocks/*/quote', async (route) => {
    passiveCalls.push('quote');
    const symbol = symbolFromStockRoute(route);
    await fulfillJson(route, {
      stock_code: symbol,
      stock_name: `${symbol} Fixture Identity`,
      current_price: symbol === 'MSFT' ? 416.2 : 211.32,
      change: 1.24,
      change_percent: 0.59,
      update_time: timestamp,
      market_timestamp: timestamp,
      observed_at: timestamp,
      freshness: symbol === 'MSFT' ? 'stale' : 'delayed',
      is_stale: symbol === 'MSFT',
      is_partial: true,
      is_synthetic: false,
      is_unavailable: false,
      source_confidence: {
        source_label: 'Fixture quote boundary',
        as_of: timestamp,
        freshness: symbol === 'MSFT' ? 'stale' : 'delayed',
        is_stale: symbol === 'MSFT',
        is_partial: true,
        is_synthetic: false,
        is_unavailable: false,
        confidence_weight: 0.7,
        coverage: 0.8,
      },
    });
  });

  await page.route('**/api/v1/stocks/*/research-packet', async (route) => {
    passiveCalls.push('research-packet');
    const symbol = symbolFromStockRoute(route);
    await fulfillJson(route, {
      symbol,
      market: 'us',
      identity: {
        name: `${symbol} Fixture Identity`,
        exchange: 'NASDAQ',
        sector: 'Technology',
        industry: 'Software infrastructure',
      },
      quote: { state: symbol === 'MSFT' ? 'stale' : 'available', price: 211.32, change_percent: 0.59, as_of: timestamp },
      history: { state: 'partial', bars: symbol === 'MSFT' ? 70 : 90, period: 'daily', as_of: '2026-07-08' },
      structure: { state: 'partial', label: 'Fixture structure', confidence: 'medium', as_of: '2026-07-08' },
      fundamentals: { state: 'not_integrated', fields_available: [] },
      events: { state: 'missing', latest: [] },
      peer: { state: 'insufficient', benchmark: 'QQQ' },
      missing_data: ['peer_benchmark', 'filing_event_catalyst'],
      research_status: 'partial',
      next_data_action: 'Review comparable evidence before drawing conclusions.',
      observation_only: true,
      decision_grade: false,
      no_advice_disclosure: 'Research observation only.',
    });
  });

  await page.route('**/api/v1/stocks/*/structure-decision', async (route) => {
    passiveCalls.push('structure-decision');
    await fulfillJson(route, structurePayload(symbolFromStockRoute(route)));
  });

  await page.route('**/api/v1/stocks/*/history**', async (route) => {
    passiveCalls.push('history');
    const symbol = symbolFromStockRoute(route);
    await fulfillJson(route, {
      stock_code: symbol,
      stock_name: `${symbol} Fixture Identity`,
      period: 'daily',
      source: 'playwright_fixture',
      source_confidence: {
        source_label: 'Fixture history boundary',
        as_of: timestamp,
        freshness: symbol === 'MSFT' ? 'stale' : 'delayed',
        is_stale: symbol === 'MSFT',
        is_partial: true,
        is_synthetic: false,
        is_unavailable: false,
      },
      data: [
        { date: '2026-07-01', open: 207.1, high: 211.2, low: 205.8, close: 209.6, volume: 21200000 },
        { date: '2026-07-02', open: 209.8, high: 213.1, low: 208.7, close: 211.4, volume: 23800000 },
        { date: '2026-07-03', open: 211.1, high: 214.5, low: 210.2, close: 213.8, volume: 22100000 },
      ],
    });
  });

  await page.route('**/api/v1/stocks/*/technical-indicators', async (route) => {
    passiveCalls.push('technical-indicators');
    const symbol = symbolFromStockRoute(route);
    await fulfillJson(route, {
      contract_version: 'stock_technical_indicators_v1',
      symbol,
      status: symbol === 'MSFT' ? 'insufficient_history' : 'available',
      timeframe: 'daily',
      as_of: timestamp,
      freshness: symbol === 'MSFT' ? 'stale' : 'fresh',
      source_label: 'Fixture history boundary',
      data_quality: {
        status: symbol === 'MSFT' ? 'insufficient_history' : 'available',
        required_bars: 200,
        observed_bars: symbol === 'MSFT' ? 70 : 220,
        usable_bars: symbol === 'MSFT' ? 70 : 220,
        missing_bars: symbol === 'MSFT' ? 130 : 0,
        freshness: symbol === 'MSFT' ? 'stale' : 'fresh',
      },
      indicators: symbol === 'MSFT' ? {} : { rsi14: { value: 55.1 }, sma20: { value: 210.2 } },
      no_advice_disclosure: 'Research-only technical indicator context.',
    });
  });

  await page.route('**/api/v1/stocks/*/evidence**', async (route) => {
    passiveCalls.push('evidence');
    const symbol = symbolFromStockRoute(route);
    await fulfillJson(route, {
      symbols: [symbol],
      items: [
        {
          symbol,
          market: 'US',
          quote: { state: symbol === 'MSFT' ? 'stale' : 'available' },
          technical: { state: symbol === 'MSFT' ? 'partial' : 'available' },
          fundamental: null,
          news: null,
          symbol_evidence_readiness: {
            readiness_tier: symbol === 'MSFT' ? 'insufficient' : 'partial',
            evidence_used: ['quote', 'technical'],
            evidence_missing: ['fundamentals', 'events'],
            stale_inputs: symbol === 'MSFT' ? ['quote', 'history'] : [],
            data_quality_notes: ['Fixture evidence remains partial.'],
            observation_only: true,
            no_advice_disclosure: 'Research observation only.',
          },
        },
      ],
      meta: { generated_at: timestamp, source: 'playwright_fixture' },
    });
  });

  await page.route('**/api/v1/options/underlyings/*/structure', async (route) => {
    passiveCalls.push('options-structure');
    const parts = new URL(route.request().url()).pathname.split('/');
    const symbol = decodeURIComponent(parts[5] || 'AAPL').toUpperCase();
    await fulfillJson(route, {
      contract_version: 'options-structure-summary-v1',
      symbol,
      status: 'not_available',
      calculation_state: 'not_available',
      observation_only: true,
      decision_grade: false,
      provider_configured: false,
      spot_price: null,
      as_of: null,
      freshness: 'unknown',
      snapshot: {
        contract_version: 'option-chain-snapshot-v1',
        symbol,
        spot_price: null,
        as_of: null,
        freshness: 'unknown',
        contracts: [],
        missing_inputs: ['authorized_options_structure_source'],
      },
      strike_summaries: [],
      expiration_summaries: [],
      nearest_expirations: [],
      blocking_reasons: ['options_structure_unavailable'],
      warnings: [],
      next_evidence_needed: ['authorized_structure_source_needed'],
    });
  });

  page.on('request', (request) => {
    const url = new URL(request.url());
    if (!url.pathname.startsWith('/api/v1/')) return;
    if (/\/(scanner|backtest|scenario|portfolio|watchlist)\b/i.test(url.pathname)) {
      mutationCalls.push(`${request.method()} ${url.pathname}`);
    }
    if (request.method() !== 'GET' && !/\/auth\//.test(url.pathname)) {
      mutationCalls.push(`${request.method()} ${url.pathname}`);
    }
  });

  return { passiveCalls, mutationCalls };
}

async function expectStockIdentity(page: Page, symbol: string) {
  await expect(page).toHaveURL(new RegExp(`/stocks/${symbol}/structure-decision`));
  await expect(page.getByTestId('stock-structure-decision-page')).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId('stock-research-identity-header')).toContainText(symbol);
  await expect(page.getByTestId('stock-current-research-conclusion')).toContainText(symbol);
  await expect(page.getByTestId('stock-current-research-conclusion')).toContainText(/支持证据|Supporting evidence/);
  await expect(page.getByTestId('stock-factor-evidence-panel')).toBeVisible();
  await expect(page.getByTestId('stock-risk-triggers-panel')).toBeVisible();
  await expect(page.getByTestId('stock-evidence-ledger')).toBeVisible();
  await expectNoHorizontalOverflow(page);
}

test.describe('T267 stock structure route continuity', () => {
  test('keeps ticker identity through direct entry, refresh, locale entry, and SPA navigation without passive-read mutations', async ({ page }) => {
    const errors: string[] = [];
    const warnings: string[] = [];
    const echartsMessages: string[] = [];
    page.on('console', (message) => {
      if (message.text().includes('[ECharts]')) {
        echartsMessages.push(`${message.type()}: ${message.text()}`);
      }
      if (message.type() === 'error') {
        errors.push(message.text());
      }
      if (message.type() === 'warning') {
        warnings.push(message.text());
      }
    });
    page.on('pageerror', (error) => errors.push(error.message));

    const { passiveCalls, mutationCalls } = await installStockStructureHarness(page);

    await page.goto('/zh/stocks/AAPL/structure-decision');
    await expectStockIdentity(page, 'AAPL');
    await expect(page.getByTestId('stock-current-research-conclusion')).toContainText('不确定性');
    await expect(page.getByTestId('stock-evidence-ledger')).toContainText('部分可用');

    await page.reload();
    await expectStockIdentity(page, 'AAPL');

    await page.goto('/en/stocks/AAPL/structure-decision');
    await expectStockIdentity(page, 'AAPL');
    await expect(page.getByTestId('stock-current-research-conclusion')).toContainText('Uncertainty');

    await page.goto('/zh/stocks/MSFT/structure-decision?symbol=MSFT&source=scanner');
    await expectStockIdentity(page, 'MSFT');
    await expect(page.getByTestId('stock-evidence-ledger')).toContainText(/可能延迟|暂不可用|历史样本不足/);
    await expect(page.getByTestId('stock-evidence-ledger')).not.toContainText(/\bstale\b|raw|provider|cache|traceId|requestId/i);

    await page.getByTestId('research-workspace-link-stock-structure').click();
    await expectStockIdentity(page, 'MSFT');

    await page.goto('/zh/stocks/AAPL/structure-decision');
    await expectStockIdentity(page, 'AAPL');

    expect(mutationCalls).toEqual([]);
    expect(passiveCalls).toEqual(expect.arrayContaining([
      'validate',
      'quote',
      'research-packet',
      'structure-decision',
      'history',
      'technical-indicators',
      'evidence',
      'options-structure',
    ]));
    expect({ errors, warnings, echartsMessages }).toEqual({
      errors: [],
      warnings: [],
      echartsMessages: [],
    });
  });
});
