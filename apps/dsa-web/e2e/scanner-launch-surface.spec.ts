import type { Page, Route } from '@playwright/test';
import { expect, test } from './fixtures/appSmoke';

const forbiddenTradingAction = /买入按钮|建议买入|建议卖出|立即交易|下单|提交订单|订单载荷|开仓|平仓|加仓|减仓|place order|submit order|buy now|sell now/i;
const rawPayloadPattern = /raw\s+(payload|response)|provider\s+payload|debug\s+payload|payload_json|raw_provider_payload/i;
const collapsedStatePattern = /扫描器不可用|Scanner unavailable/;

type ScannerReadinessPayload = Record<string, unknown>;
type ScannerStateMatrixCase = {
  id: string;
  route: string;
  viewport: { width: number; height: number };
  statusPayload: ScannerReadinessPayload;
  runsPayload: Record<string, unknown>;
  runDetailPayload?: Record<string, unknown>;
  runDetailError?: { status: number; body: Record<string, unknown> };
  expectedText: RegExp;
  unexpectedText?: RegExp;
  expectsLedgerOverflow?: boolean;
  keyboard?: 'run-button' | 'ledger-row';
};

function scannerAuthStatus() {
  return {
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
  };
}

function scannerRunsPayload(runSummary?: Record<string, unknown>) {
  return {
    items: runSummary ? [runSummary] : [],
    total: runSummary ? 1 : 0,
    page: 1,
    page_size: 20,
  };
}

function scannerRunSummary(overrides: Record<string, unknown> = {}) {
  return {
    id: 11,
    market: 'cn',
    profile: 'cn_preopen_v1',
    profile_label: 'A-share Pre-open v1',
    status: 'completed',
    run_at: '2026-05-02T09:00:00Z',
    completed_at: '2026-05-02T09:00:00Z',
    watchlist_date: '2026-05-02',
    trigger_mode: 'manual',
    universe_name: 'cn_a_liquid_watchlist_v1',
    shortlist_size: 1,
    universe_size: 320,
    preselected_size: 72,
    evaluated_size: 48,
    source_summary: 'Mocked scanner payload',
    headline: 'Mock scanner shortlist for state matrix',
    universe_type: 'default',
    theme_id: null,
    theme_label: null,
    requested_symbols_count: 0,
    accepted_symbols_count: 0,
    rejected_symbols: [],
    top_symbols: ['NVDA'],
    notification_status: 'not_attempted',
    failure_reason: null,
    ...overrides,
  };
}

function scannerStatusPayload(overrides: Record<string, unknown> = {}) {
  return {
    market: 'cn',
    profile: 'cn_preopen_v1',
    watchlist_date: '2026-05-02',
    today_trading_day: true,
    schedule_enabled: false,
    schedule_run_immediately: false,
    notification_enabled: false,
    quality_summary: {
      available: true,
      review_window_days: 5,
      run_count: 1,
      reviewed_run_count: 1,
      reviewed_candidate_count: 1,
      strong_count: 1,
      mixed_count: 0,
      weak_count: 0,
    },
    data_readiness: {
      state: 'ready',
      market: 'cn',
      profile: 'cn_preopen_v1',
      universe_size: 320,
      scanner_universe_readiness: {
        status: 'available',
        market: 'cn',
        universe_size: 320,
        consumer_safe_message: '标的池已准备，可以按当前条件运行扫描。',
      },
      quote_coverage: 'available',
      history_coverage: 'available',
      freshness: 'available',
      candidate_evaluation_count: 48,
      selected_count: 1,
      rejected_count: 47,
      failed_count: 0,
      blocker_bucket: 'unknown',
      consumer_summary: '扫描器可用于观察。',
      next_data_action: '可以按当前条件运行扫描。',
    },
    ...overrides,
  };
}
const retryNoCandidateRun = {
  id: 11,
  market: 'cn',
  profile: 'cn_preopen_v1',
  profile_label: 'A-share Pre-open v1',
  status: 'empty',
  run_at: '2026-05-02T09:00:00Z',
  completed_at: '2026-05-02T09:00:00Z',
  watchlist_date: '2026-05-02',
  trigger_mode: 'manual',
  universe_name: 'cn_a_liquid_watchlist_v1',
  shortlist_size: 0,
  universe_size: 320,
  preselected_size: 72,
  evaluated_size: 48,
  source_summary: 'Mocked scanner payload',
  headline: 'Mock scanner empty result for retry verification',
  universe_notes: [],
  scoring_notes: [],
  universe_type: 'default',
  theme_id: null,
  theme_label: null,
  requested_symbols_count: 0,
  accepted_symbols_count: 0,
  rejected_symbols: [],
  diagnostics: {
    coverage_summary: {
      input_universe_size: 320,
      eligible_after_universe_fetch: 300,
      eligible_after_liquidity_filter: 244,
      eligible_after_data_availability_filter: 192,
      ranked_candidate_count: 48,
      shortlisted_count: 0,
      excluded_total: 48,
      excluded_by_reason: [{ reason: 'below_threshold', label: 'Screening condition not met', count: 48 }],
      likely_bottleneck: 'screening_threshold',
      likely_bottleneck_label: 'Screening threshold',
    },
    universe_selection: {
      universe_type: 'default',
      theme_id: null,
      theme_label: null,
      requested_symbols_count: 0,
      accepted_symbols_count: 0,
      rejected_symbols: [],
      universe_notes: [],
    },
  },
  notification: {
    attempted: false,
    status: 'not_attempted',
    success: null,
    channels: [],
    message: null,
    report_path: null,
    sent_at: null,
  },
  failure_reason: null,
  summary: {
    universe_count: 320,
    submitted_count: 320,
    evaluated_count: 48,
    selected_count: 0,
    rejected_count: 48,
    data_failed_count: 0,
    skipped_count: 0,
    error_count: 0,
    limited_by_result_cap: false,
  },
  shortlist: [],
  selected: [],
  candidates: [],
};
const previewNoCandidateRun = {
  ...retryNoCandidateRun,
  headline: 'Mock scanner no-candidate result with preview row',
  summary: {
    ...retryNoCandidateRun.summary,
    evaluated_count: 3,
    rejected_count: 3,
  },
  candidates: [
    {
      symbol: 'MARA',
      name: 'MARA Holdings',
      rank: 1,
      status: 'rejected',
      score: 61,
      provider: 'mock',
      reason: 'below liquidity threshold',
      failed_rules: ['below_liquidity_threshold'],
      missing_fields: [],
      metrics: { return20d: 3.1, trend: 8 },
    },
  ],
};

function scannerDataReadiness(overrides: Record<string, unknown> = {}) {
  return {
    state: 'ready',
    market: 'cn',
    profile: 'cn_preopen_v1',
    universe_size: 320,
    scanner_universe_readiness: {
      status: 'available',
      market: 'cn',
      universe_size: 320,
      consumer_safe_message: '标的池已准备，可以按当前条件运行扫描。',
    },
    quote_coverage: 'available',
    history_coverage: 'available',
    freshness: 'available',
    candidate_evaluation_count: 48,
    selected_count: 1,
    rejected_count: 47,
    failed_count: 0,
    blocker_bucket: 'unknown',
    consumer_summary: '扫描器可用于观察。',
    next_data_action: '可以按当前条件运行扫描。',
    ...overrides,
  };
}

function controlledCandidate(overrides: Record<string, unknown> = {}) {
  const symbol = typeof overrides.symbol === 'string' ? overrides.symbol : 'NVDA';
  return {
    symbol,
    name: 'NVIDIA',
    company_name: 'NVIDIA Corp',
    rank: 1,
    score: 91,
    quality_hint: '研究证据较完整',
    reason_summary: '相对强度保持，量能和趋势条件通过当前研究门槛。',
    reasons: ['相对强度保持，量能和趋势条件通过当前研究门槛。'],
    key_metrics: [
      { label: '相对强度', value: '较强' },
      { label: '成交活跃度', value: '充分' },
    ],
    feature_signals: [
      { label: '趋势', value: '改善' },
      { label: '波动', value: '可观察' },
    ],
    risk_notes: ['若市场数据继续缺口，需要先补证再深入研究。'],
    watch_context: [{ label: '下一步', value: '查看个股研究与证据页。' }],
    boards: ['semis'],
    tags: [{ name: '研究候选', description: '通过当前研究门槛。', tone: 'blue' }],
    appeared_in_recent_runs: 1,
    last_trade_date: '2026-05-01',
    scan_timestamp: '2026-05-02T09:00:00Z',
    diagnostics: {},
    ...overrides,
  };
}

function controlledCandidateDiagnostic(overrides: Record<string, unknown> = {}) {
  return {
    symbol: 'NVDA',
    name: 'NVIDIA',
    rank: 1,
    status: 'selected',
    score: 91,
    provider: 'controlled',
    reason: '相对强度保持，量能和趋势条件通过当前研究门槛。',
    failed_rules: [],
    missing_fields: [],
    metrics: { relative_strength: 'strong', liquidity: 'sufficient' },
    metadata: {},
    ...overrides,
  };
}

function controlledCandidateRun(overrides: Record<string, unknown> = {}) {
  const candidate = controlledCandidate();
  return {
    id: 11,
    market: 'cn',
    profile: 'cn_preopen_v1',
    profile_label: 'A-share Pre-open v1',
    status: 'completed',
    run_at: '2026-05-02T09:00:00Z',
    completed_at: '2026-05-02T09:00:00Z',
    watchlist_date: '2026-05-02',
    trigger_mode: 'manual',
    universe_name: 'cn_a_liquid_watchlist_v1',
    shortlist_size: 1,
    universe_size: 320,
    preselected_size: 72,
    evaluated_size: 48,
    source_summary: 'Mocked scanner payload',
    headline: 'Controlled scanner candidate result',
    universe_notes: [],
    scoring_notes: [],
    universe_type: 'default',
    theme_id: null,
    theme_label: null,
    requested_symbols_count: 0,
    accepted_symbols_count: 0,
    rejected_symbols: [],
    diagnostics: {
      coverage_summary: {
        input_universe_size: 320,
        eligible_after_universe_fetch: 300,
        eligible_after_liquidity_filter: 244,
        eligible_after_data_availability_filter: 192,
        ranked_candidate_count: 48,
        shortlisted_count: 1,
        excluded_total: 47,
        excluded_by_reason: [],
        likely_bottleneck: null,
        likely_bottleneck_label: null,
      },
      universe_selection: {
        universe_type: 'default',
        theme_id: null,
        theme_label: null,
        requested_symbols_count: 0,
        accepted_symbols_count: 0,
        rejected_symbols: [],
        universe_notes: [],
      },
    },
    notification: {
      attempted: false,
      status: 'not_attempted',
      success: null,
      channels: [],
      message: null,
      report_path: null,
      sent_at: null,
    },
    failure_reason: null,
    summary: {
      universe_count: 320,
      submitted_count: 320,
      evaluated_count: 48,
      selected_count: 1,
      rejected_count: 47,
      data_failed_count: 0,
      skipped_count: 0,
      error_count: 0,
      limited_by_result_cap: false,
    },
    shortlist: [candidate],
    selected: [candidate],
    candidates: [controlledCandidateDiagnostic()],
    ...overrides,
  };
}

function collectApiRequests(page: Page) {
  const requests: Array<{ method: string; path: string; url: string }> = [];
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith('/api/v1/')) {
      requests.push({ method: request.method(), path: url.pathname, url: request.url() });
    }
  });
  return requests;
}

function getPassiveReadViolations(requests: Array<{ method: string; path: string }>) {
  return requests.filter((request) => {
    if (request.method !== 'GET' && request.method !== 'HEAD') return true;
    return /refresh-scores|refresh_scores|activate|activation|provider.*probe|probe.*provider|universe.*refresh|refresh.*universe|production.*write|write.*production/i.test(request.path);
  });
}

function getUnsafeScannerActionRequests(requests: Array<{ method: string; path: string }>) {
  return requests.filter((request) => (
    /refresh-scores|refresh_scores|activate|activation|provider.*probe|probe.*provider|universe.*refresh|refresh.*universe|radar/i.test(request.path)
  ));
}

async function fulfillJson(route: Route, body: Record<string, unknown>, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

async function installScannerStateRoutes(page: Page, matrixCase: ScannerStateMatrixCase) {
  await page.route('**/api/v1/auth/status', async (route) => fulfillJson(route, scannerAuthStatus()));
  await page.route('**/api/v1/scanner/status**', async (route) => fulfillJson(route, matrixCase.statusPayload));
  await page.route(/\/api\/v1\/scanner\/runs(?:\?.*)?$/, async (route) => fulfillJson(route, matrixCase.runsPayload));
  await page.route('**/api/v1/scanner/runs/11', async (route) => {
    if (matrixCase.runDetailError) {
      await fulfillJson(route, matrixCase.runDetailError.body, matrixCase.runDetailError.status);
      return;
    }
    await fulfillJson(route, matrixCase.runDetailPayload || controlledCandidateRun());
  });
  await page.route('**/api/v1/scanner/run', async (route) => fulfillJson(route, matrixCase.runDetailPayload || retryNoCandidateRun));
}

async function assertNoBodyOverflow(page: Page) {
  await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

async function assertNoConsumerLeakage(page: Page) {
  const bodyText = await page.locator('body').innerText();
  expect(bodyText).not.toMatch(forbiddenTradingAction);
  expect(bodyText).not.toMatch(rawPayloadPattern);
  expect(bodyText).not.toMatch(collapsedStatePattern);
  expect(bodyText).not.toMatch(/source_missing|source_policy_unknown|activationReady|candidate_generation_blocked|sourceClass|contractVersion|cache internals|provider routing|payload_json|raw diagnostics/i);
  expect(bodyText).not.toContain('暂无结果');
}

const scannerStateMatrixCases: ScannerStateMatrixCase[] = [
  {
    id: 'idle-not-run',
    route: '/zh/scanner',
    viewport: { width: 1440, height: 1000 },
    statusPayload: scannerStatusPayload({
      quality_summary: {
        available: false,
        review_window_days: 5,
        run_count: 0,
        reviewed_run_count: 0,
        reviewed_candidate_count: 0,
        strong_count: 0,
        mixed_count: 0,
        weak_count: 0,
      },
      data_readiness: scannerDataReadiness({
        state: 'not_run',
        quote_coverage: 'unknown',
        history_coverage: 'unknown',
        freshness: 'unknown',
        candidate_evaluation_count: 0,
        selected_count: 0,
        rejected_count: 0,
        consumer_summary: '尚未运行扫描。',
        next_data_action: '先直接启动一次扫描。',
      }),
    }),
    runsPayload: scannerRunsPayload(),
    expectedText: /未运行|等待运行/,
    keyboard: 'run-button',
  },
  {
    id: 'universe-membership-blocked',
    route: '/zh/scanner',
    viewport: { width: 1440, height: 1000 },
    statusPayload: scannerStatusPayload({
      data_readiness: scannerDataReadiness({
        state: 'blocked',
        universe_size: 0,
        scanner_universe_readiness: {
          status: 'universe_missing',
          market: 'cn',
          universe_size: 0,
          consumer_safe_message: '标的池尚未准备完成。',
        },
        quote_coverage: 'unknown',
        history_coverage: 'unknown',
        freshness: 'unknown',
        candidate_evaluation_count: 0,
        selected_count: 0,
        rejected_count: 0,
        blocker_bucket: 'missing_universe',
        consumer_summary: '标的池尚未准备完成。',
        next_data_action: '等待标的池准备完成后再运行扫描。',
      }),
    }),
    runsPayload: scannerRunsPayload(),
    expectedText: /标的池成员|标的池缺失|标的池尚未准备完成/,
    unexpectedText: /市场数据尚不足|当前暂时无法生成候选/,
  },
  {
    id: 'market-data-blocked',
    route: '/zh/scanner',
    viewport: { width: 390, height: 844 },
    statusPayload: scannerStatusPayload({
      data_readiness: scannerDataReadiness({
        state: 'blocked',
        quote_coverage: 'missing',
        history_coverage: 'missing',
        freshness: 'stale',
        candidate_evaluation_count: 0,
        selected_count: 0,
        rejected_count: 0,
        blocker_bucket: 'missing_history',
        consumer_summary: '市场数据尚不足。',
        next_data_action: '等待历史数据补齐后再运行扫描。',
      }),
    }),
    runsPayload: scannerRunsPayload(),
    expectedText: /市场数据|历史数据待补|市场数据尚不足/,
    unexpectedText: /标的池缺失|当前暂时无法生成候选/,
  },
  {
    id: 'candidate-generation-blocked',
    route: '/zh/scanner',
    viewport: { width: 1440, height: 1000 },
    statusPayload: scannerStatusPayload({
      data_readiness: scannerDataReadiness({
        state: 'blocked',
        candidate_evaluation_count: 0,
        selected_count: 0,
        rejected_count: 0,
        blocker_bucket: 'profile_filters_rejected_all',
        consumer_summary: '当前暂时无法生成候选。',
        next_data_action: '放宽当前条件后再尝试生成候选。',
      }),
    }),
    runsPayload: scannerRunsPayload(),
    expectedText: /候选生成|条件过窄|当前暂时无法生成候选/,
    unexpectedText: /标的池缺失|历史数据待补/,
  },
  {
    id: 'valid-zero-result',
    route: '/zh/scanner',
    viewport: { width: 1440, height: 1000 },
    statusPayload: scannerStatusPayload({
      data_readiness: scannerDataReadiness({
        selected_count: 0,
        rejected_count: 48,
        consumer_summary: '当前条件下没有候选通过研究门槛。',
        next_data_action: '可调整范围或手动研究单个代码。',
      }),
    }),
    runsPayload: scannerRunsPayload(scannerRunSummary({ status: 'empty', shortlist_size: 0, top_symbols: [] })),
    runDetailPayload: retryNoCandidateRun,
    expectedText: /本次未形成入选候选|未形成官方入选候选|无候选/,
    unexpectedText: /标的池缺失|历史数据待补/,
  },
  {
    id: 'controlled-candidate-result',
    route: '/zh/scanner?source=scanner-state-matrix',
    viewport: { width: 768, height: 900 },
    statusPayload: scannerStatusPayload(),
    runsPayload: scannerRunsPayload(scannerRunSummary()),
    runDetailPayload: controlledCandidateRun(),
    expectedText: /当前候选 NVDA|排序首位|NVDA/,
    expectsLedgerOverflow: true,
    keyboard: 'ledger-row',
  },
  {
    id: 'stale-partial-data-trust',
    route: '/zh/scanner',
    viewport: { width: 1440, height: 1000 },
    statusPayload: scannerStatusPayload({
      data_readiness: scannerDataReadiness({
        state: 'partial',
        quote_coverage: 'partial',
        history_coverage: 'stale',
        freshness: 'stale',
        failed_count: 2,
        consumer_summary: '扫描器可用于观察，部分数据仍需复核。',
        next_data_action: '继续复核市场数据完整度。',
      }),
    }),
    runsPayload: scannerRunsPayload(scannerRunSummary()),
    runDetailPayload: controlledCandidateRun({
      summary: {
        universe_count: 320,
        submitted_count: 320,
        evaluated_count: 48,
        selected_count: 1,
        rejected_count: 45,
        data_failed_count: 2,
        skipped_count: 0,
        error_count: 0,
        limited_by_result_cap: false,
      },
    }),
    expectedText: /部分可用|待更新|继续复核市场数据完整度|数据受限/,
  },
  {
    id: 'request-error',
    route: '/zh/scanner',
    viewport: { width: 1440, height: 1000 },
    statusPayload: scannerStatusPayload(),
    runsPayload: scannerRunsPayload(scannerRunSummary()),
    runDetailError: {
      status: 500,
      body: {
        message: 'raw provider payload source_missing diagnostic should stay hidden',
      },
    },
    expectedText: /扫描未完成|扫描读取失败|失败/,
  },
];

async function assertScannerLaunchViewport(page: Page, viewport: { width: number; height: number }) {
  await page.setViewportSize(viewport);
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
  await page.goto('/zh/scanner');
  await page.waitForLoadState('domcontentloaded');

  const launchSummary = page.getByTestId('scanner-status-strip');
  const conclusionBand = page.getByTestId('scanner-conclusion-band');
  const candidateRegion = page.getByTestId('scanner-candidate-scroll-region');
  const firstCandidate = page.getByTestId('scanner-result-row-NVDA');
  const denseShell = page.getByTestId('scanner-launch-bar');
  const commandPanel = page.getByTestId('scanner-command-panel');
  const commandBar = page.getByTestId('scanner-command-bar');
  const resultsPanel = page.getByTestId('scanner-results-panel');
  const summaryRail = page.getByTestId('scanner-summary-rail');
  const resultTable = page.getByTestId('scanner-result-table');
  const inlineDetailPanel = page.getByTestId('scanner-inline-detail-panel');
  const detailRail = page.getByTestId('scanner-detail-rail');
  const focusCandidate = page.getByTestId('scanner-result-detail-NVDA');

  await expect(page.getByTestId('user-scanner-workspace')).toBeVisible({ timeout: 15_000 });
  await expect(denseShell).toBeVisible();
  await expect(commandPanel).toBeVisible();
  await expect(commandBar).toBeVisible();
  await expect(resultsPanel).toBeVisible();
  await expect(summaryRail).toBeVisible();
  await expect(conclusionBand).toBeVisible();
  await expect(launchSummary).toBeVisible();
  await expect(conclusionBand).toContainText(/当前候选|Current candidate|证据不足|Evidence insufficient|等待扫描|Waiting for a scan/);
  await expect(launchSummary).toContainText(/排序首位|Top ranked|Best candidate/);
  await expect(launchSummary).toContainText(/候选分布|Candidate mix/);
  await expect(launchSummary).toContainText(/信号状态|Signal state/);
  await expect(candidateRegion).toBeVisible();
  await expect(resultTable).toBeVisible();
  await expect(firstCandidate).toBeVisible();
  await expect(firstCandidate).toContainText('NVDA');
  await expect(summaryRail).toContainText(/工作区摘要|Workspace summary/);
  await expect(summaryRail).toContainText(/候选|Candidates/);
  await expect(summaryRail).toContainText(/淘汰|Rejected/);
  await expect(summaryRail).toContainText(/数据受限|Limited/);
  if (await detailRail.count()) {
    await expect(detailRail).toBeVisible();
  } else {
    await expect(inlineDetailPanel).toBeVisible();
  }
  await expect(focusCandidate).toContainText(/当前信号|Why now/);
  await expect(focusCandidate).toContainText(/候选说明|Candidate notes/);
  await expect(page.getByTestId('scanner-control-rail')).toHaveCount(0);
  await expect(page.getByTestId('scanner-sidebar')).toHaveCount(0);
  await expect(page.getByTestId('scanner-bento-grid')).toHaveCount(0);
  await expect(page.getByTestId('scanner-card-wall')).toHaveCount(0);

  const launchBox = await commandBar.boundingBox();
  const commandPanelBox = await commandPanel.boundingBox();
  const conclusionBox = await conclusionBand.boundingBox();
  const summaryBox = await launchSummary.boundingBox();
  const candidateRegionBox = await candidateRegion.boundingBox();
  const resultBox = await denseShell.boundingBox();
  const resultsPanelBox = await resultsPanel.boundingBox();
  const summaryRailBox = await summaryRail.boundingBox();
  const viewportWidth = viewport.width;
  expect(launchBox).not.toBeNull();
  expect(commandPanelBox).not.toBeNull();
  expect(conclusionBox).not.toBeNull();
  expect(summaryBox).not.toBeNull();
  expect(candidateRegionBox).not.toBeNull();
  expect(resultBox).not.toBeNull();
  expect(resultsPanelBox).not.toBeNull();
  expect(summaryRailBox).not.toBeNull();
  expect(summaryBox?.y ?? 0).toBeGreaterThan(conclusionBox?.y ?? 0);
  expect(candidateRegionBox?.y ?? 0).toBeGreaterThan(summaryBox?.y ?? 0);
  expect(candidateRegionBox?.y ?? 0).toBeGreaterThan((launchBox?.y ?? 0) - 1);
  if (viewportWidth >= 768) {
    const readinessFirstLimit = viewportWidth >= 1024 ? 1.35 : 1.55;
    expect(candidateRegionBox?.y ?? 0).toBeLessThan(viewport.height * readinessFirstLimit);
  }
  if (viewportWidth >= 1024) {
    expect(resultBox?.width ?? 0).toBeGreaterThan(viewportWidth * 0.62);
    expect(summaryRailBox?.x ?? 0).toBeGreaterThan((resultBox?.x ?? 0) + (resultBox?.width ?? 0) - 1);
    expect(summaryRailBox?.width ?? 0).toBeGreaterThan(220);
  } else {
    expect(resultBox?.width ?? 0).toBeGreaterThan(viewportWidth * 0.72);
    expect(summaryRailBox?.y ?? 0).toBeGreaterThan((resultBox?.y ?? 0) + (resultBox?.height ?? 0) - 1);
  }

  const secondaryDisclosures = [
    page.getByTestId('scanner-diagnostics-disclosure'),
    page.getByTestId('scanner-run-comparison-strip'),
    page.getByTestId('scanner-strategy-experiment'),
  ];
  for (const disclosure of secondaryDisclosures) {
    if (await disclosure.count()) {
      await expect(disclosure).toBeVisible();
      await expect(disclosure).not.toHaveAttribute('open');
      const disclosureBox = await disclosure.boundingBox();
      expect(disclosureBox?.y ?? Number.POSITIVE_INFINITY).toBeGreaterThan(candidateRegionBox?.y ?? 0);
    }
  }
  await expect(page.getByTestId('scanner-diagnostics-panel')).toHaveCount(0);
  await expect(page.getByTestId('scanner-result-history-summary')).toHaveCount(0);
  await expect(page.getByTestId('scanner-strategy-preview')).toHaveCount(0);
  await expect(page.getByTestId('scanner-advanced-controls')).toHaveCount(0);

  const bodyText = await page.locator('body').innerText();
  expect(bodyText).not.toMatch(forbiddenTradingAction);
  expect(bodyText).not.toMatch(rawPayloadPattern);
  expect(bodyText).not.toMatch(/Details|provider|fallback|proxy|raw|reasonCode|reasonFamilies|source-confidence|sourceConfidence|MarketCache|bucket|runtime|diagnostic|diagnostics/i);
  await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

test.describe('scanner launch surface', () => {
  test('candidate and evidence lead the zh scanner first fold', async ({ page }) => {
    await assertScannerLaunchViewport(page, { width: 1440, height: 1000 });
    await assertScannerLaunchViewport(page, { width: 1920, height: 1080 });
    await assertScannerLaunchViewport(page, { width: 768, height: 900 });
    await assertScannerLaunchViewport(page, { width: 390, height: 844 });
  });

  for (const matrixCase of scannerStateMatrixCases) {
    test(`separates scanner state: ${matrixCase.id}`, async ({ page, consoleErrors }) => {
      const apiRequests = collectApiRequests(page);
      await installScannerStateRoutes(page, matrixCase);

      await page.setViewportSize(matrixCase.viewport);
      await page.goto(matrixCase.route);
      await page.waitForLoadState('domcontentloaded');

      const expectedPath = new URL(`http://wolfy.local${matrixCase.route}`).pathname;
      expect(new URL(page.url()).pathname).toBe(expectedPath);
      expect(new URL(page.url()).pathname).toMatch(/^\/zh\/scanner$/);

      const surface = page.getByTestId('user-scanner-workspace');
      const conclusionBand = page.getByTestId('scanner-conclusion-band');
      const assertionTarget = matrixCase.id === 'request-error' ? page.locator('body') : conclusionBand;
      await expect(surface).toBeVisible({ timeout: 15_000 });
      await expect(assertionTarget).toContainText(matrixCase.expectedText);
      if (matrixCase.unexpectedText) {
        await expect(page.locator('body')).not.toContainText(matrixCase.unexpectedText);
      }

      expect(getPassiveReadViolations(apiRequests)).toEqual([]);
      if (matrixCase.id !== 'request-error') {
        await expect(page.getByTestId('scanner-workbench-empty-state').or(page.getByTestId('scanner-result-table'))).toBeVisible();
      }

      if (matrixCase.expectsLedgerOverflow) {
        const rankedList = page.getByTestId('scanner-ranked-list');
        await expect(rankedList).toBeVisible();
        await expect.poll(async () => rankedList.evaluate((element) => element.scrollWidth >= element.clientWidth)).toBe(true);
      }

      if (matrixCase.keyboard === 'ledger-row') {
        const firstRow = page.getByTestId('scanner-ranked-row-NVDA');
        await expect(firstRow).toBeVisible();
        await firstRow.focus();
        await page.keyboard.press('Enter');
        await expect(page.getByTestId('scanner-result-detail-NVDA')).toBeVisible();
      }

      if (matrixCase.keyboard === 'run-button') {
        const passiveRequestCount = apiRequests.length;
        const runButton = page.getByRole('button', { name: '启动扫描' });
        await expect(runButton).toBeEnabled();
        await runButton.focus();
        await page.keyboard.press('Enter');
        await expect.poll(() => apiRequests.filter((request) => request.method === 'POST' && request.path === '/api/v1/scanner/run').length).toBe(1);
        expect(getPassiveReadViolations(apiRequests.slice(0, passiveRequestCount))).toEqual([]);
        await expect(page.getByTestId('scanner-run-feedback')).toContainText(/扫描|候选|完成|未形成/);
      }

      if (matrixCase.id === 'request-error') {
        await expect(page.getByRole('alert')).toContainText(/扫描未完成|内部错误详情已隐藏/);
        consoleErrors.splice(0, consoleErrors.length);
      }

      expect(getUnsafeScannerActionRequests(apiRequests)).toEqual([]);
      await assertNoConsumerLeakage(page);
      await assertNoBodyOverflow(page);
      expect(consoleErrors).toEqual([]);
    });
  }

  test('keeps scanner loading distinct while history is pending', async ({ page, consoleErrors }) => {
    const apiRequests = collectApiRequests(page);
    let releaseRuns!: () => void;
    const runsPending = new Promise<void>((resolve) => {
      releaseRuns = resolve;
    });

    await page.route('**/api/v1/auth/status', async (route) => fulfillJson(route, scannerAuthStatus()));
    await page.route('**/api/v1/scanner/status**', async (route) => fulfillJson(route, scannerStatusPayload({
      data_readiness: scannerDataReadiness({
        state: 'ready',
        consumer_summary: '扫描器可用于观察。',
        next_data_action: '可以按当前条件运行扫描。',
      }),
    })));
    await page.route(/\/api\/v1\/scanner\/runs(?:\?.*)?$/, async (route) => {
      await runsPending;
      await fulfillJson(route, scannerRunsPayload());
    });

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/zh/scanner');
    await page.waitForLoadState('domcontentloaded');

    await expect(page.getByTestId('scanner-conclusion-band')).toContainText(/正在读取最近扫描|等待扫描/);
    await expect(page.locator('body')).not.toContainText('暂无结果');
    expect(getPassiveReadViolations(apiRequests)).toEqual([]);
    await assertNoConsumerLeakage(page);
    await assertNoBodyOverflow(page);
    expect(consoleErrors).toEqual([]);

    releaseRuns();
    await expect(page.getByTestId('scanner-workbench-empty-state')).toContainText(/尚未运行扫描|先直接启动一次扫描/);
  });

  test('shows first-run guidance with one primary scan CTA when no scan history exists', async ({ page }) => {
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
    await page.route('**/api/v1/scanner/runs**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: [],
          total: 0,
          page: 1,
          page_size: 20,
        }),
      });
    });
    await page.route('**/api/v1/scanner/status**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          market: 'cn',
          profile: 'cn_preopen_v1',
          watchlist_date: '2026-05-02',
          today_trading_day: true,
          schedule_enabled: false,
          schedule_run_immediately: false,
          notification_enabled: false,
          quality_summary: {
            available: false,
            review_window_days: 5,
            run_count: 0,
            reviewed_run_count: 0,
            reviewed_candidate_count: 0,
            strong_count: 0,
            mixed_count: 0,
            weak_count: 0,
          },
          data_readiness: {
            state: 'not_run',
            market: 'cn',
            profile: 'cn_preopen_v1',
            blocker_bucket: 'unknown',
            quote_coverage: 'unknown',
            history_coverage: 'unknown',
            freshness: 'unknown',
          },
        }),
      });
    });

    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto('/zh/scanner');
    await page.waitForLoadState('domcontentloaded');

    const conclusionBand = page.getByTestId('scanner-conclusion-band');
    const emptyState = page.getByTestId('scanner-workbench-empty-state');
    const runButton = page.getByRole('button', { name: '启动扫描' });

    await expect(conclusionBand).toContainText('首次使用：先运行一次扫描');
    await expect(conclusionBand).toContainText('扫描器会先按当前范围筛出可继续观察的候选。');
    await expect(conclusionBand).toContainText('A股 · 默认市场池 · 300 只 · 60 条详评');
    await expect(emptyState).toContainText('尚未运行扫描');
    await expect(emptyState).toContainText('扫描器会先按当前范围整理候选与观察线索。');
    await expect(emptyState).toContainText('先直接启动一次扫描');
    await expect(emptyState).toContainText('打开历史记录');
    await expect(runButton).toHaveCount(1);
    await expect(page.getByRole('button', { name: '重新扫描' })).toHaveCount(0);
    await expect(page.locator('body')).not.toContainText(forbiddenTradingAction);
    await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  });

  test('retries loaded run params with a valid shortlist fallback in the workspace layout', async ({ page }) => {
    let postedRunRequest: unknown = null;

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
    await page.route('**/api/v1/scanner/runs/11', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(retryNoCandidateRun),
      });
    });
    await page.route('**/api/v1/scanner/run', async (route) => {
      postedRunRequest = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...retryNoCandidateRun, id: 12 }),
      });
    });

    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto('/zh/scanner');
    await page.waitForLoadState('domcontentloaded');

    await expect(page.getByTestId('scanner-summary-rail')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('scanner-command-panel')).toBeVisible();
    const runFacts = page.getByTestId('scanner-run-facts');
    await expect(runFacts).toBeVisible();
    await expect(runFacts).toContainText('运行事实');
    await expect(runFacts).toContainText('市场');
    await expect(runFacts).toContainText('A股');
    await expect(runFacts).toContainText('策略');
    await expect(runFacts).toContainText('A-share Pre-open');
    await expect(runFacts).toContainText('运行时间');
    await expect(runFacts).toContainText('完成时间');
    await expect(runFacts).toContainText('观察日期');
    await expect(runFacts).toContainText('标的池');
    await expect(runFacts).toContainText('320');
    await expect(runFacts).toContainText('预筛');
    await expect(runFacts).toContainText('72');
    await expect(runFacts).toContainText('评估');
    await expect(runFacts).toContainText('48');
    await expect(runFacts).toContainText('入选');
    await expect(runFacts).toContainText('0');
    await expect(runFacts).not.toContainText(/provider|reasonCode|below_threshold|raw/i);
    await expect(page.getByTestId('scanner-history-scope-hint')).toContainText('个人历史仅基于当前账号可访问的扫描记录');
    await expect(page.getByRole('button', { name: '重新扫描' })).toBeEnabled();
    await page.getByRole('button', { name: '重新扫描' }).click();

    await expect.poll(() => JSON.stringify(postedRunRequest)).toBe(JSON.stringify({
      market: 'cn',
      profile: 'cn_preopen_v1',
      shortlist_size: 5,
      universe_limit: 320,
      detail_limit: 72,
    }));
  });

  test('shows no-candidate next steps with manual research handoff', async ({ page }) => {
    let watchlistRequest: unknown = null;
    let analysisRequest: unknown = null;

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
    await page.route(/\/api\/v1\/scanner\/runs(?:\?.*)?$/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: [{
            id: 11,
            market: 'cn',
            profile: 'cn_preopen_v1',
            profile_label: 'A-share Pre-open v1',
            status: 'empty',
            run_at: '2026-05-02T09:00:00Z',
            completed_at: '2026-05-02T09:00:00Z',
            watchlist_date: '2026-05-02',
            trigger_mode: 'manual',
            universe_name: 'cn_a_liquid_watchlist_v1',
            shortlist_size: 0,
            universe_size: 320,
            preselected_size: 72,
            evaluated_size: 48,
            source_summary: 'Mocked scanner payload',
            headline: 'Mock scanner no-candidate result with preview row',
            universe_type: 'default',
            theme_id: null,
            theme_label: null,
            requested_symbols_count: 0,
            accepted_symbols_count: 0,
            rejected_symbols: [],
            top_symbols: [],
            notification_status: 'not_attempted',
            failure_reason: null,
          }],
          total: 1,
          page: 1,
          page_size: 20,
        }),
      });
    });
    await page.route('**/api/v1/scanner/runs/11', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(previewNoCandidateRun),
      });
    });
    await page.route('**/api/v1/watchlist/items', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ items: [] }),
        });
        return;
      }
      watchlistRequest = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 2002,
          symbol: 'TSLA',
          market: 'cn',
          name: 'TSLA',
          source: 'scanner',
          created_at: '2026-05-02T09:00:00Z',
          updated_at: '2026-05-02T09:00:00Z',
        }),
      });
    });
    await page.route('**/api/v1/analysis/analyze', async (route) => {
      analysisRequest = route.request().postDataJSON();
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({
          taskId: 'task-manual-tsla',
          status: 'accepted',
          message: 'Accepted',
        }),
      });
    });

    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto('/zh/scanner');
    await page.waitForLoadState('domcontentloaded');

    const nextSteps = page.getByTestId('scanner-workflow-next-steps');
    await expect(nextSteps).toBeVisible({ timeout: 15_000 });
    await expect(nextSteps).toContainText('下一步');
    await expect(nextSteps).toContainText('首选研究路径');
    await expect(nextSteps).toContainText('换市场或配置');
    await expect(nextSteps).toContainText(/未形成官方入选候选|不代表市场没有机会/);
    await expect(nextSteps).toContainText('查看历史');
    await expect(nextSteps).toContainText('可选保存路径');
    await expect(nextSteps).not.toContainText(/功能预览|示例预览|此演示样例不是实时扫描结果/);
    await expect(nextSteps.getByRole('link', { name: /打开 Watchlist/i })).toHaveAttribute('href', '/zh/watchlist');
    await expect(nextSteps.getByRole('link', { name: /打开 Market Overview/i })).toHaveAttribute('href', '/zh/market-overview');

    await nextSteps.getByLabel(/手动补充研究代码/).fill('TSLA');
    await nextSteps.getByRole('button', { name: /加入观察名单 TSLA/ }).click();
    await expect.poll(() => JSON.stringify(watchlistRequest)).toContain('TSLA');
    await expect(nextSteps.getByRole('button', { name: /已在观察名单|Already in Watchlist/ })).toBeVisible();

    await nextSteps.getByLabel(/手动补充研究代码/).fill('TSLA');
    await nextSteps.getByRole('button', { name: /研究 TSLA/ }).click();
    await expect.poll(() => JSON.stringify(analysisRequest)).toContain('TSLA');

    const bodyText = await page.locator('body').innerText();
    expect(bodyText).not.toMatch(/provider|reasonCode|fallback_source|below_liquidity_threshold|raw diagnostics|payload_json/i);
    await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  });
});
