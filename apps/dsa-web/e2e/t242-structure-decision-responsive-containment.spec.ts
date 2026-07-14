import { expect, test, type Page, type Route } from '@playwright/test';

const timestamp = '2026-07-06T13:30:00Z';
const paths = [
  '/zh/stocks/AAPL/structure-decision',
  '/en/stocks/AAPL/structure-decision',
] as const;

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

function symbolFromStockPath(route: Route) {
  const parts = new URL(route.request().url()).pathname.split('/');
  const index = parts.indexOf('stocks');
  return decodeURIComponent(parts[index + 1] || 'AAPL').toUpperCase();
}

async function installStructureDecisionHarness(page: Page) {
  const currentUser = {
    id: 't242-user',
    username: 't242-user',
    displayName: 'T242 User',
    role: 'user',
    isAdmin: false,
    isAuthenticated: true,
    transitional: false,
    authEnabled: true,
  };

  await page.route('**/api/v1/auth/status**', async (route) => fulfillJson(route, {
    authEnabled: true,
    loggedIn: true,
    passwordSet: true,
    passwordChangeable: true,
    setupState: 'enabled',
    currentUser,
  }));
  await page.route('**/api/v1/auth/me**', async (route) => fulfillJson(route, currentUser));
  await page.route('**/api/v1/stocks/*/validate', async (route) => {
    const symbol = symbolFromStockPath(route);
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
    const symbol = symbolFromStockPath(route);
    await fulfillJson(route, {
      stock_code: symbol,
      stock_name: symbol,
      current_price: 211.32,
      change: 1.24,
      change_percent: 0.59,
      update_time: timestamp,
      freshness: 'delayed',
      source_confidence: {
        source_label: 'Playwright Fixture With Very Long Identity Label For Width Probe',
        as_of: timestamp,
        freshness: 'delayed',
        is_stale: false,
        is_partial: false,
        is_synthetic: false,
        is_unavailable: false,
      },
    });
  });
  await page.route('**/api/v1/stocks/*/research-packet', async (route) => {
    const symbol = symbolFromStockPath(route);
    await fulfillJson(route, {
      symbol,
      market: 'us',
      identity: {
        name: `${symbol} Semiconductor Infrastructure International Holdings Research Identity`,
        exchange: 'NASDAQ-GLOBAL-SELECT-MARKET-LONG-LABEL',
        sector: 'Technology Hardware Infrastructure',
        industry: 'Semiconductors And AI Infrastructure Equipment',
      },
      quote: { state: 'available', price: 211.32, change_percent: 0.59, as_of: timestamp },
      history: { state: 'available', bars: 90, period: 'daily', as_of: '2026-07-06' },
      structure: { state: 'available', label: 'Range-bound with long evidence label', confidence: 'medium', as_of: '2026-07-06' },
      fundamentals: { state: 'not_integrated', fields_available: [] },
      events: { state: 'missing', latest: [] },
      peer: { state: 'insufficient', benchmark: 'QQQ-LONG-BENCHMARK-LABEL' },
      missing_data: ['peer evidence with long label'],
      research_status: 'partial',
      next_data_action: 'Review comparable evidence before drawing conclusions.',
      observation_only: true,
      decision_grade: false,
      no_advice_disclosure: 'Research observation only.',
    });
  });
  await page.route('**/api/v1/stocks/*/structure-decision', async (route) => {
    const symbol = symbolFromStockPath(route);
    await fulfillJson(route, {
      schema_version: 'browser_qualification_stock_structure_fixture_v1',
      ticker: symbol,
      structure_state: 'range',
      confidence: 'medium',
      confidence_cap: {
        value: 55,
        label: 'Medium',
        reasons: ['Fixture route evidence is bounded but intentionally verbose for responsive ownership measurement.'],
      },
      confidence_state: {
        status: 'partial',
        label: 'Evidence limited',
        reasons: ['Peer evidence remains incomplete.'],
      },
      component_scores: {
        trend: 58,
        relativeStrength: 52,
        evidenceQuality: 45,
        volatilityCompression: 41,
        breakoutQuality: 39,
      },
      explanation: {
        why_this_structure: 'Price evidence remains range-bound in the browser qualification fixture with intentionally long explanatory text for containment testing.',
        what_confirms_it: ['Fresh price evidence remains available.'],
        what_invalidates_it: ['Evidence falls out of date.'],
        key_levels: [{ kind: 'support', value: 198.5, description: 'Fixture support level with long identity text.' }],
      },
      research_notes: {
        watch_next: ['Refresh quote evidence before deeper review.'],
        needs_more_evidence: ['Comparable peer evidence with long copy.'],
        risk_flags: ['Evidence is partial.'],
      },
      data_quality: {
        status: 'partial',
        period: 'daily',
        requested_days: 120,
        observed_bars: 90,
        usable_bars: 90,
        reason: 'Fixture route smoke coverage.',
      },
      missing_evidence: [{ kind: 'peer', message: 'Comparable evidence pending.' }],
      no_advice_disclosure: 'Research observation only.',
    });
  });
  await page.route('**/api/v1/stocks/*/history**', async (route) => {
    const symbol = symbolFromStockPath(route);
    await fulfillJson(route, {
      stock_code: symbol,
      stock_name: symbol,
      period: 'daily',
      source: 'playwright_fixture',
      source_confidence: {
        source_label: 'Playwright Fixture',
        as_of: timestamp,
        freshness: 'delayed',
        is_stale: false,
        is_partial: false,
        is_synthetic: false,
        is_unavailable: false,
      },
      data: [
        { date: '2026-07-01', open: 207.1, high: 211.2, low: 205.8, close: 209.6, volume: 21200000, change_percent: 0.8 },
        { date: '2026-07-02', open: 209.8, high: 213.1, low: 208.7, close: 211.4, volume: 23800000, change_percent: 0.86 },
        { date: '2026-07-03', open: 211.1, high: 214.5, low: 210.2, close: 213.8, volume: 22100000, change_percent: 1.14 },
      ],
    });
  });
  await page.route('**/api/v1/stocks/*/technical-indicators', async (route) => fulfillJson(route, {
    symbol: symbolFromStockPath(route),
    as_of: timestamp,
    summary: { trend: 'range', momentum: 'neutral', volatility: 'normal' },
    indicators: {
      rsi: 54,
      macd: { value: 0.12, signal: 0.08, histogram: 0.04 },
      moving_averages: { ma20: 208.4, ma50: 205.2 },
    },
    source_confidence: {
      source_label: 'Playwright Fixture',
      as_of: timestamp,
      freshness: 'delayed',
      is_stale: false,
      is_partial: false,
      is_synthetic: false,
      is_unavailable: false,
    },
  }));
  await page.route('**/api/v1/options/underlyings/*/structure', async (route) => {
    const symbol = decodeURIComponent(new URL(route.request().url()).pathname.split('/')[5] || 'AAPL').toUpperCase();
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
      zero_dte: {
        state: 'not_available',
        expiration: null,
        dte: null,
        contract_count: 0,
        call_open_interest: 0,
        put_open_interest: 0,
        call_volume: 0,
        put_volume: 0,
        open_interest_share: null,
        volume_share: null,
      },
      gamma_flip_level: { state: 'not_available', level: null, reason: 'authorized_structure_source_needed' },
      total_dealer_gamma_exposure: null,
      blocking_reasons: ['options_structure_unavailable'],
      warnings: [],
      next_evidence_needed: ['authorized_structure_source_needed'],
    });
  });
  await page.route('**/api/v1/stocks/*/evidence**', async (route) => fulfillJson(route, {
    symbol: 'AAPL',
    items: [],
    evidence_items: [],
    summary: { state: 'partial' },
    data_quality: { state: 'partial' },
  }));
}

async function collectContainmentMetrics(page: Page) {
  return page.evaluate(() => {
    const pick = (element: Element | null) => {
      if (!(element instanceof HTMLElement)) return null;
      return {
        scrollWidth: element.scrollWidth,
        clientWidth: element.clientWidth,
        overflow: Math.max(0, element.scrollWidth - element.clientWidth),
      };
    };
    const visible = (element: Element) => {
      const style = window.getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) !== 0 && rect.width > 0 && rect.height > 0;
    };
    const localScrollOwners = Array.from(document.querySelectorAll<HTMLElement>('body *'))
      .filter((element) => visible(element))
      .filter((element) => /(auto|scroll)/.test(window.getComputedStyle(element).overflowX) && element.scrollWidth > element.clientWidth + 2);
    const focusables = Array.from(document.querySelectorAll<HTMLElement>('button,a[href],input,select,textarea,[tabindex]:not([tabindex="-1"]),[role="button"],[role="menuitem"]'))
      .filter((element) => visible(element));
    const clippedFocusableCount = focusables.filter((element) => {
      const rect = element.getBoundingClientRect();
      return rect.left < -1 || rect.right > window.innerWidth + 1 || rect.top < -1 || rect.bottom > document.documentElement.scrollHeight + 1;
    }).length;
    const largestOverflowingDescendant = localScrollOwners
      .map((element) => ({
        testId: element.getAttribute('data-testid'),
        overflow: Math.max(0, element.scrollWidth - element.clientWidth),
      }))
      .sort((left, right) => right.overflow - left.overflow)[0] || null;

    return {
      document: pick(document.documentElement),
      body: pick(document.body),
      pageOwner: pick(document.querySelector('[data-testid="stock-structure-decision-page"]')),
      localHorizontalScrollOwnerCount: localScrollOwners.length,
      localHorizontalScrollOwners: localScrollOwners.map((element) => element.getAttribute('data-testid')).filter(Boolean),
      largestOverflowingDescendant,
      clippedFocusableCount,
      actionReachability: focusables.some((element) => {
        const rect = element.getBoundingClientRect();
        return rect.right > 0 && rect.left < window.innerWidth && rect.bottom > 0 && rect.top < window.innerHeight;
      }),
    };
  });
}

test.describe('T242 Structure Decision responsive containment', () => {
  for (const path of paths) {
    test(`contains page-owner overflow for ${path}`, async ({ page }) => {
        await installStructureDecisionHarness(page);
        await page.goto(path);
        await page.getByTestId('stock-structure-decision-page').waitFor({ state: 'visible', timeout: 15_000 });
        await page.waitForLoadState('networkidle', { timeout: 5_000 }).catch(() => undefined);
        await page.getByTestId('stock-evidence-ledger-scroll').focus();

        const metrics = await collectContainmentMetrics(page);

        expect(metrics.document?.overflow).toBe(0);
        expect(metrics.body?.overflow).toBe(0);
        expect(metrics.pageOwner?.overflow).toBe(0);
        expect(metrics.localHorizontalScrollOwners).toContain('stock-evidence-ledger-scroll');
        expect(metrics.largestOverflowingDescendant?.testId).toBeTruthy();
        expect(metrics.clippedFocusableCount).toBe(0);
        expect(metrics.actionReachability).toBe(true);
        await expect(page.getByTestId('stock-evidence-ledger-scroll')).toBeFocused();
    });
  }
});
