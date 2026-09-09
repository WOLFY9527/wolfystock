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
    symbol: 'NVDA',
    name: 'NVIDIA',
    company_name: 'NVIDIA Corp',
    rank: 1,
    score: 82,
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
        state: 'ready',
        market: 'us',
        profile: 'us_historical_research_v1',
        universe_size: 180,
        quote_coverage: 'unknown',
        history_coverage: 'available',
        freshness: 'historical',
        selected_count: 1,
        rejected_count: 39,
        failed_count: 0,
        blocker_bucket: 'unknown',
        consumer_summary: 'Historical research evidence is available through the selected cutoff.',
        next_data_action: 'Review the cutoff-bound evidence; refresh separately for current-market research.',
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
    candidates: [{ symbol: 'NVDA', name: 'NVIDIA', rank: 1, status: 'selected', score: 82 }],
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
      top_symbols: ['NVDA'],
      notification_status: 'not_attempted',
      change_summary: run.comparison_to_previous,
    }],
  };
}

async function installHistoricalRoutes(page: Page) {
  let historicalRunAvailable = false;
  let submittedRequest: Record<string, unknown> | null = null;
  const historyUrls: string[] = [];

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
  await expect(page.getByTestId('scanner-consumer-status-sentence')).toContainText(`through ${cutoff}`);
  await expect(page.getByTestId('scanner-consumer-status-sentence')).not.toContainText(/today|pre-open/i);
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

  const layout = await page.evaluate(() => ({
    viewport: window.innerWidth,
    documentWidth: document.documentElement.scrollWidth,
    controlRight: document.querySelector<HTMLElement>('[data-testid="scanner-historical-mode-control"]')?.getBoundingClientRect().right || 0,
  }));
  expect(layout.documentWidth).toBeLessThanOrEqual(layout.viewport + 1);
  expect(layout.controlRight).toBeLessThanOrEqual(layout.viewport + 1);

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
