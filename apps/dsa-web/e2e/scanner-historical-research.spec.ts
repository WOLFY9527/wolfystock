import type { Page, Route } from '@playwright/test';
import { expect, test } from './fixtures/appSmoke';

const cutoff = '2024-12-31';

function fulfillJson(route: Route, body: Record<string, unknown>) {
  return route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

function historicalCandidate() {
  return {
    symbol: 'AAPL',
    name: 'Apple',
    company_name: 'Apple Inc.',
    rank: 1,
    score: 74.3,
    quality_hint: 'Historical evidence available through the cutoff.',
    reason_summary: 'Cutoff-bound trend and liquidity evidence passed the research screen.',
    reasons: ['Historical trend and liquidity evidence passed the research screen.'],
    key_metrics: [{ label: 'Historical cutoff', value: cutoff }],
    feature_signals: [{ label: 'Replay state', value: 'Historical development' }],
    risk_notes: ['Historical evidence does not establish current-market conditions.'],
    watch_context: [{ label: 'Next step', value: 'Review the same cutoff-bound evidence.' }],
    boards: ['semiconductors'],
    appeared_in_recent_runs: 1,
    last_trade_date: cutoff,
    scan_timestamp: '2026-09-08T10:30:00Z',
    ai_interpretation: { available: false, status: 'unavailable' },
    realized_outcome: {
      review_status: 'pending',
      outcome_label: 'Pending',
      thesis_match: 'unknown',
      review_window_days: 5,
    },
    historical_ohlcv_readiness: {
      as_of: cutoff,
      required_bars: 180,
      usable_bars: 180,
      missing_bars: 0,
    },
    diagnostics: {},
  };
}

function historicalRun() {
  const candidate = historicalCandidate();
  return {
    id: 84,
    market: 'us',
    profile: 'us_historical_research_v1',
    profile_label: 'US Historical Research Scanner v1',
    evaluation_mode: 'historical_development',
    evaluation_cutoff: cutoff,
    status: 'completed',
    run_at: '2026-09-08T10:30:00Z',
    completed_at: '2026-09-08T10:31:00Z',
    watchlist_date: cutoff,
    trigger_mode: 'manual',
    universe_name: 'us_historical_research_v1',
    shortlist_size: 1,
    universe_size: 180,
    preselected_size: 40,
    evaluated_size: 40,
    source_summary: 'Cutoff-bound local historical evidence.',
    headline: `Historical research replay through ${cutoff}`,
    universe_notes: [],
    scoring_notes: [],
    universe_type: 'default',
    theme_id: null,
    theme_label: null,
    requested_symbols_count: 0,
    accepted_symbols_count: 0,
    rejected_symbols: [],
    diagnostics: {
      data_readiness: {
        state: 'blocked',
        market: 'us',
        profile: 'us_historical_research_v1',
        universe_size: 180,
        quote_coverage: 'unknown',
        history_coverage: 'available',
        freshness: 'stale',
        selected_count: 1,
        rejected_count: 39,
        failed_count: 0,
        blocker_bucket: 'stale_universe',
        consumer_summary: 'Historical research evidence is available through the selected cutoff.',
        next_data_action: 'Refresh the scanner scope before scanning again.',
        scanner_universe_readiness: {
          contract_version: 'scanner_universe_readiness_v1',
          status: 'stale',
          market: 'US',
          universe_size: 180,
          last_updated_at: `${cutoff}T00:00:00+00:00`,
          freshness_state: `universe_modified:${cutoff}`,
          required_data_classes: ['universe', 'historical_ohlcv', 'quote_snapshot'],
          available_data_classes: ['universe', 'historical_ohlcv'],
          missing_data_classes: ['quote_snapshot'],
          blocked_product_surfaces: ['Scanner'],
          consumer_safe_message: 'Scanner scope is stale and must be refreshed before scanning.',
          consumer_safe: true,
        },
      },
    },
    summary: {
      universe_count: 180,
      submitted_count: 180,
      evaluated_count: 40,
      selected_count: 1,
      rejected_count: 39,
      data_failed_count: 0,
      skipped_count: 0,
      error_count: 0,
      limited_by_result_cap: false,
    },
    notification: { attempted: false, status: 'not_attempted', channels: [] },
    comparison_to_previous: {
      available: false,
      new_count: 0,
      retained_count: 0,
      dropped_count: 0,
      new_symbols: [],
      retained_symbols: [],
      dropped_symbols: [],
    },
    review_summary: {
      available: false,
      review_window_days: 5,
      review_status: 'pending',
      candidate_count: 1,
      reviewed_count: 0,
      pending_count: 1,
      strong_count: 0,
      mixed_count: 0,
      weak_count: 0,
    },
    shortlist: [candidate],
    selected: [candidate],
    candidates: [{
      symbol: 'AAPL',
      name: 'Apple',
      rank: 1,
      status: 'selected',
      score: 74.3,
      historical_ohlcv_readiness: candidate.historical_ohlcv_readiness,
    }],
  };
}

function historicalRuns() {
  const run = historicalRun();
  return {
    total: 1,
    page: 1,
    limit: 8,
    items: [{
      ...run,
      top_symbols: ['AAPL'],
      notification_status: 'not_attempted',
      change_summary: run.comparison_to_previous,
    }],
  };
}

async function installCurrentResearchUnavailableRoutes(page: Page) {
  await page.route('**/api/v1/stocks/AAPL/validate', (route) => fulfillJson(route, {
    stock_code: 'AAPL',
    normalized_symbol: 'AAPL',
    market: 'us',
    status: 'valid',
    valid: true,
    exists: true,
    stock_name: 'Apple',
  }));
  await page.route('**/api/v1/stocks/AAPL/quote', (route) => fulfillJson(route, {
    stock_code: 'AAPL',
    stock_name: 'Apple',
    current_price: null,
    update_time: null,
    availability_state: 'unavailable',
    is_unavailable: true,
    unavailable_reason: 'Current quote is unavailable.',
    missing_requirements: ['current_quote'],
  }));
  await page.route('**/api/v1/stocks/AAPL/research-packet', (route) => fulfillJson(route, {
    symbol: 'AAPL',
    market: 'us',
    identity: { name: 'Apple', exchange: 'NASDAQ', sector: 'Technology', industry: 'Hardware' },
    quote: { state: 'unavailable', price: null, change_percent: null, as_of: null },
    history: { state: 'unavailable', bars: 0, period: 'daily', as_of: null },
    structure: { state: 'unavailable', label: null, confidence: 'low', as_of: null },
    missing_data: ['Current quote and history are unavailable.'],
    research_status: 'partial',
    observation_only: true,
    decision_grade: false,
    no_advice_disclosure: 'Research observation only.',
  }));
  await page.route('**/api/v1/stocks/AAPL/structure-decision', (route) => fulfillJson(route, {
    schema_version: 'stock_structure_decision_api_v1',
    ticker: 'AAPL',
    structure_state: 'low_confidence',
    confidence: 'low',
    confidence_cap: { value: 20, label: 'Low', reasons: ['Current history is unavailable.'] },
    confidence_state: { status: 'evidence incomplete', label: 'Low', reasons: ['Current history is unavailable.'] },
    component_scores: {},
    explanation: {
      why_this_structure: 'Current structure cannot be established.',
      what_confirms_it: [],
      what_invalidates_it: [],
      key_levels: [],
    },
    research_notes: {
      watch_next: ['Refresh current data separately.'],
      needs_more_evidence: ['Current quote and history.'],
      risk_flags: [],
    },
    data_quality: {
      status: 'unavailable',
      period: 'daily',
      requested_days: 90,
      observed_bars: 0,
      usable_bars: 0,
      reason: 'history_unavailable',
    },
    historical_ohlcv_readiness: {
      required_bars: 90,
      usable_bars: 0,
      missing_bars: 90,
      overall_state: 'blocked',
      consumer_safe: true,
    },
    missing_evidence: [{ kind: 'history', message: 'Current history is unavailable.' }],
    no_advice_disclosure: 'Research observation only.',
    observation_only: true,
    decision_grade: false,
  }));
  await page.route('**/api/v1/stocks/AAPL/history**', (route) => fulfillJson(route, {
    stock_code: 'AAPL',
    stock_name: 'Apple',
    period: 'daily',
    diagnostics: {
      status: 'unavailable',
      reason: 'current_history_unavailable',
      message: 'Current history is unavailable.',
      requested_days: 90,
      rows: 0,
    },
    source_confidence: {
      is_unavailable: true,
      coverage: 0,
    },
    data: [],
  }));
  await page.route('**/api/v1/stocks/AAPL/technical-indicators', (route) => fulfillJson(route, {
    contract_version: 'stock_technical_indicators_v1',
    symbol: 'AAPL',
    status: 'missing_cache',
    timeframe: 'daily',
    as_of: null,
    freshness: 'unknown',
    data_quality: { status: 'missing', required_bars: 90, observed_bars: 0, usable_bars: 0, missing_bars: 90 },
    indicators: {},
    observation_only: true,
    decision_grade: false,
  }));
  await page.route('**/api/v1/stocks/AAPL/evidence**', (route) => fulfillJson(route, {
    stock_evidence_packet: {
      not_investment_advice: true,
      confidence_cap: { value: 20 },
      claim_boundaries: [],
      source_refs: [],
      data_gaps: ['Current evidence unavailable.'],
    },
  }));
  await page.route('**/api/v1/options/underlyings/AAPL/structure', (route) => fulfillJson(route, {
    contract_version: 'options-structure-summary-v1',
    symbol: 'AAPL',
    status: 'not_available',
    calculation_state: 'not_available',
    observation_only: true,
    decision_grade: false,
    spot_price: null,
    as_of: null,
    freshness: 'unknown',
    snapshot: { symbol: 'AAPL', spot_price: null, as_of: null, freshness: 'unknown', contracts: [] },
    strike_summaries: [],
    expiration_summaries: [],
    nearest_expirations: [],
    blocking_reasons: [],
    warnings: [],
    next_evidence_needed: [],
  }));
}

async function installHistoricalRoutes(page: Page) {
  let historicalRunAvailable = false;
  let submittedRequest: Record<string, unknown> | null = null;
  const historyUrls: string[] = [];

  await installCurrentResearchUnavailableRoutes(page);

  await page.route('**/api/v1/auth/status', (route) => fulfillJson(route, {
    authEnabled: true,
    loggedIn: true,
    passwordSet: true,
    passwordChangeable: true,
    setupState: 'enabled',
    currentUser: {
      id: 'historical-research-user',
      username: 'historical-research-user',
      displayName: 'Historical Research User',
      role: 'user',
      isAdmin: false,
      isAuthenticated: true,
      transitional: false,
      authEnabled: true,
    },
  }));
  await page.route('**/api/v1/scanner/readiness**', (route) => {
    const url = new URL(route.request().url());
    const historical = url.searchParams.get('profile') === 'us_historical_research_v1';
    return fulfillJson(route, {
      market: historical ? 'us' : (url.searchParams.get('market') || 'cn'),
      profile: historical ? 'us_historical_research_v1' : (url.searchParams.get('profile') || 'cn_preopen_v1'),
      data_readiness: {
        state: historical ? 'ready' : 'not_run',
        market: historical ? 'us' : (url.searchParams.get('market') || 'cn'),
        profile: historical ? 'us_historical_research_v1' : (url.searchParams.get('profile') || 'cn_preopen_v1'),
        history_coverage: historical ? 'available' : 'unknown',
        quote_coverage: 'unknown',
        freshness: historical ? 'historical' : 'unknown',
        blocker_bucket: 'unknown',
      },
    });
  });
  await page.route(/\/api\/v1\/scanner\/runs(?:\?.*)?$/, (route) => {
    historyUrls.push(route.request().url());
    const url = new URL(route.request().url());
    const historical = url.searchParams.get('profile') === 'us_historical_research_v1';
    return fulfillJson(route, historical && historicalRunAvailable
      ? historicalRuns()
      : { total: 0, page: 1, limit: 8, items: [] });
  });
  await page.route('**/api/v1/scanner/runs/84', (route) => fulfillJson(route, historicalRun()));
  await page.route('**/api/v1/scanner/run', async (route) => {
    submittedRequest = route.request().postDataJSON() as Record<string, unknown>;
    historicalRunAvailable = true;
    await fulfillJson(route, historicalRun());
  });

  return {
    getSubmittedRequest: () => submittedRequest,
    getHistoryUrls: () => historyUrls,
  };
}

test('launches, discovers, and reopens cutoff-bound historical Scanner research', async ({ page }, testInfo) => {
  const passiveResearchRequests: Array<{ method: string; path: string }> = [];
  let recordPassiveResearch = false;
  page.on('request', (request) => {
    if (!recordPassiveResearch) return;
    passiveResearchRequests.push({
      method: request.method(),
      path: new URL(request.url()).pathname,
    });
  });
  const evidence = await installHistoricalRoutes(page);
  await page.goto('/en/scanner');

  await expect(page.getByTestId('user-scanner-workspace')).toBeVisible({ timeout: 15_000 });
  await page.getByTestId('scanner-market-toggle').getByRole('button', { name: 'US' }).click();
  await page.getByRole('button', { name: 'US Historical Research' }).click();

  const historicalControl = page.getByTestId('scanner-historical-mode-control');
  const cutoffInput = page.getByTestId('scanner-historical-cutoff-input');
  await expect(historicalControl).toBeVisible();
  await expect(cutoffInput).toHaveValue('');
  await expect(page.getByTestId('scanner-historical-mode-notice')).toContainText('Development replay');
  await expect(page.getByTestId('scanner-historical-mode-notice')).toContainText('not live or current-market data');

  await cutoffInput.fill(cutoff);
  await page.getByTestId('scanner-run-button').click();

  await expect.poll(evidence.getSubmittedRequest).toEqual(expect.objectContaining({
    market: 'us',
    profile: 'us_historical_research_v1',
    evaluation_mode: 'historical_development',
    evaluation_cutoff: cutoff,
  }));
  await expect.poll(() => evidence.getHistoryUrls().some((value) => {
    const url = new URL(value);
    return url.searchParams.get('market') === 'us'
      && url.searchParams.get('profile') === 'us_historical_research_v1';
  })).toBe(true);

  await expect(page.getByTestId('scanner-page-profile-label')).toContainText('US Historical Research');
  await expect(page.getByTestId('scanner-consumer-status-sentence')).toContainText('completed with 1 candidate');
  await expect(page.getByTestId('scanner-consumer-status-sentence')).not.toContainText(/today|pre-open/i);
  await expect(page.getByTestId('scanner-consumer-readiness-summary')).toContainText('Universe snapshot 12/31/2024 is stale for a new current-market run');
  await expect(page.getByTestId('scanner-consumer-next-action')).toContainText('Refresh the universe before a new current-market run');
  await expect(page.getByTestId('scanner-conclusion-band')).toContainText('Historical run completed');
  await expect(page.getByTestId('scanner-conclusion-band')).toContainText('Candidates 1');
  await expect(page.getByTestId('scanner-conclusion-band')).not.toContainText('must be refreshed before scanning');
  await expect(page.getByTestId('scanner-run-facts')).toContainText('Historical development replay');
  await expect(cutoffInput).toHaveValue(cutoff);
  await expect(page.getByTestId('scanner-run-facts')).toContainText('12/31/2024');

  await page.getByTestId('scanner-history-trigger').click();
  const historyDrawer = page.getByTestId('user-scanner-bento-drawer');
  await expect(historyDrawer).toContainText(`Historical research replay through ${cutoff}`);
  await expect(historyDrawer).toContainText('Development replay');
  await expect(historyDrawer).toContainText('Cutoff 12/31/2024');
  await historyDrawer.getByRole('button', { name: new RegExp(`Historical research replay through ${cutoff}`) }).click();
  await expect(page.getByTestId('scanner-page-profile-label')).toContainText('US Historical Research');

  recordPassiveResearch = true;
  const candidateRow = page.getByTestId('scanner-result-row-AAPL');
  await candidateRow.getByRole('button', { name: 'Detail' }).click();
  await page.getByTestId('scanner-result-detail-AAPL').getByRole('button', { name: 'Analyze' }).click();

  await expect(page).toHaveURL(/\/en\/stocks\/AAPL\/structure-decision\?symbol=AAPL&market=US&source=scanner&scannerRunId=84$/);
  const scannerEvidence = page.getByTestId('scanner-historical-evidence-panel');
  await expect(scannerEvidence).toBeVisible();
  await expect(scannerEvidence).toContainText('Scanner historical evidence');
  await expect(scannerEvidence).toContainText('74.3');
  await expect(scannerEvidence).toContainText('Usable historical bars');
  await expect(scannerEvidence).toContainText('180');
  await expect(scannerEvidence).toContainText('Missing historical bars');
  await expect(scannerEvidence).toContainText('Development replay');
  await expect(scannerEvidence).toContainText('Not current data');
  await expect(page.getByTestId('scanner-historical-current-separation')).toContainText('never filled from this replay');

  const currentHistory = page.getByTestId('stock-history-readiness-panel');
  await expect(currentHistory).toContainText('Available bars');
  await expect(currentHistory).toContainText('Required bars');
  await expect(currentHistory).toContainText('Missing bars');
  await expect(currentHistory).toContainText('90');
  await expect(page.getByTestId('stock-quote-boundary-panel')).toContainText('unavailable');
  await expect(page.getByTestId('stock-history-empty-chart-state')).toContainText('Chart unavailable');

  await page.reload();
  await expect(page.getByTestId('scanner-historical-evidence-panel')).toContainText('Usable historical bars');
  await expect.poll(() => passiveResearchRequests.filter((request) => request.method === 'GET' && request.path === '/api/v1/scanner/runs/84').length).toBeGreaterThanOrEqual(2);
  expect(passiveResearchRequests.filter((request) => (
    request.method !== 'GET'
    && (/^\/api\/v1\/scanner\//.test(request.path)
      || /^\/api\/v1\/watchlist/.test(request.path)
      || /^\/api\/v1\/research\/queue/.test(request.path))
  ))).toEqual([]);

  const layout = await page.evaluate(() => ({
    viewport: window.innerWidth,
    documentWidth: document.documentElement.scrollWidth,
    controlRight: document.querySelector<HTMLElement>('[data-testid="scanner-historical-mode-control"]')?.getBoundingClientRect().right || 0,
  }));
  expect(layout.documentWidth).toBeLessThanOrEqual(layout.viewport + 1);
  expect(layout.controlRight).toBeLessThanOrEqual(layout.viewport + 1);

  recordPassiveResearch = false;
  await page.goto('/zh/scanner');
  await page.getByTestId('scanner-market-toggle').getByRole('button', { name: '美股' }).click();
  await page.getByRole('button', { name: '美股历史研究回放' }).click();
  await expect(page.getByTestId('scanner-historical-mode-notice')).toContainText('开发回放');
  await expect(page.getByTestId('scanner-historical-mode-notice')).toContainText('不是实时或当前市场数据');
  await expect(page.getByTestId('scanner-historical-cutoff-input')).toHaveValue('');

  testInfo.annotations.push({
    type: 'historical-scanner-viewport',
    description: `${testInfo.project.name}:${layout.viewport}px`,
  });
});
