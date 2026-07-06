import { expect, test, type Page, type Route } from '@playwright/test';

type RadarMode = 'candidate' | 'zero' | 'blocked';
type WatchlistMode = 'populated' | 'empty';

type HarnessOptions = {
  radarMode?: RadarMode;
  watchlistMode?: WatchlistMode;
};

const now = '2026-07-06T09:30:00Z';
const currentUser = {
  id: 't177-user',
  username: 't177-user',
  displayName: 'T177 User',
  role: 'user',
  isAdmin: false,
  isAuthenticated: true,
  transitional: false,
  authEnabled: true,
};

const requestLog: string[] = [];

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

function authStatus() {
  return {
    authEnabled: true,
    loggedIn: true,
    passwordSet: true,
    passwordChangeable: true,
    setupState: 'enabled',
    currentUser,
  };
}

function evidenceHub(status = 'available') {
  return {
    scannerCandidates: {
      key: 'scanner',
      label: 'Scanner candidates',
      status,
      summary: status === 'available' ? 'Scanner evidence is available for research review.' : 'Scanner evidence is not ready.',
      evidenceCount: status === 'available' ? 2 : 0,
      totalCount: 2,
      details: status === 'available' ? ['Relative strength evidence available.'] : ['Candidate generation unavailable.'],
      observationOnly: true,
      decisionGrade: false,
    },
    backtestSamples: {
      key: 'backtest',
      label: 'Backtest samples',
      status: 'partial',
      summary: 'Backtest samples are partial and need follow-up.',
      blocker: 'Historical sample is incomplete.',
      nextDataAction: 'Review historical validation before extending the loop.',
      evidenceCount: 1,
      totalCount: 2,
      details: ['Partial validation only.'],
      observationOnly: true,
      decisionGrade: false,
    },
    stockReadiness: {
      key: 'stock',
      label: 'Stock readiness',
      status: 'partial',
      summary: 'Stock readiness is partial.',
      evidenceCount: 1,
      totalCount: 2,
      observationOnly: true,
      decisionGrade: false,
    },
    dataActivation: {
      key: 'data',
      label: 'Data activation',
      status,
      summary: status === 'available' ? 'Market evidence is available.' : 'Market evidence is blocked.',
      evidenceCount: status === 'available' ? 2 : 0,
      totalCount: 2,
      observationOnly: true,
      decisionGrade: false,
    },
    missingEvidenceStates: [
      {
        key: 'quote-freshness',
        label: 'Quote freshness',
        status: 'partial',
        summary: 'Latest quote needs review before research confidence can increase.',
        nextDataAction: 'Review quote timestamp.',
        evidenceCount: 1,
        totalCount: 2,
        observationOnly: true,
        decisionGrade: false,
      },
    ],
  };
}

function radarPayload(mode: RadarMode = 'candidate') {
  const common = {
    schemaVersion: 'research_radar_v1',
    generatedAt: now,
    aggregateSummary: {
      queueQuality: mode === 'blocked' ? 'blocked' : mode === 'zero' ? 'partial' : 'partial',
      priorityCounts: mode === 'candidate' ? { high: 1, medium: 1 } : {},
      source: { scannerRunId: 177, market: 'US', profile: 't177' },
    },
    evidenceGaps: ['Quote freshness needs review.'],
    marketContextFit: mode === 'blocked' ? 'Market evidence is not ready.' : 'Market context supports research review only.',
    noAdviceDisclosure: 'Research observation only; not investment advice.',
    dataQuality: {
      status: mode === 'blocked' ? 'blocked' : mode === 'zero' ? 'partial' : 'partial',
      missingEvidence: mode === 'blocked' ? ['Market evidence unavailable'] : ['Quote freshness needs review'],
    },
    evidenceHub: evidenceHub(mode === 'blocked' ? 'blocked' : 'available'),
    emptyStateActions: [
      { label: 'Open watchlist', route: '/watchlist', description: 'Review saved observation tasks.' },
      { label: 'Open stock research', route: '/stocks/ALFA/structure-decision', description: 'Review symbol evidence.' },
    ],
    starterResearchWorkflow: ['Review market context.', 'Inspect candidate evidence.', 'Continue in stock research.'],
    firstRunChecklist: ['No candidate is fabricated.', 'No provider refresh is triggered.'],
    suggestedResearchEntrypoints: [
      { surface: 'watchlist', route: '/watchlist', description: 'Review saved observation tasks.' },
    ],
  };

  if (mode === 'candidate') {
    return {
      ...common,
      researchQueue: [
        {
          symbol: 'ALFA',
          ticker: 'ALFA',
          priority: 'high',
          researchBias: 'observation',
          driverScores: {
            relativeStrength: 70,
            volumeSupport: 58,
            evidenceQuality: 46,
          },
          whyOnRadar: ['Relative strength crossed the research threshold.'],
          whatToVerify: ['Review structure evidence and quote timestamp.'],
          invalidationObservations: ['Volume confirmation remains partial.'],
          riskFlags: ['Quote freshness is partial.'],
          evidenceQuality: { status: 'partial', score: 64 },
        },
        {
          symbol: 'BETA',
          ticker: 'BETA',
          priority: 'medium',
          driverScores: { structureQuality: 52 },
          whyOnRadar: ['Structure quality remains under review.'],
          whatToVerify: ['Review support evidence.'],
          riskFlags: ['Evidence is incomplete.'],
          evidenceQuality: { status: 'partial', score: 52 },
        },
      ],
      marketLevelFallback: null,
      onboardingGuidance: {
        title: 'Candidate results available',
        summary: 'Use the queue to inspect evidence and limitations.',
        conditionsDetected: ['Partial freshness'],
      },
    };
  }

  return {
    ...common,
    researchQueue: [],
    marketLevelFallback: mode === 'blocked'
      ? {
          available: true,
          label: 'Market evidence not ready',
          summary: 'Candidate generation is unavailable because market evidence is not ready.',
          candidateGenerationExecuted: false,
          candidateUnavailableReason: 'market_evidence_unavailable',
          regime: { label: 'Unavailable', status: 'unavailable' },
          productSummary: 'Research universe or market evidence is not ready, so candidate rows are withheld.',
          evidenceCards: [
            {
              cardId: 'market-data',
              title: 'Market evidence',
              status: 'unavailable',
              severity: 'blocked',
              headline: 'Market evidence is not ready for candidate generation.',
              reasons: ['Market data unavailable.'],
              observationOnly: true,
              decisionGrade: false,
            },
          ],
          readiness: {
            label: 'blocked',
            status: 'blocked',
            missingDataFamilies: ['Market evidence'],
            blockedProductSurfaces: ['Research Radar'],
            nextOperatorAction: 'Wait for market evidence before reviewing candidates.',
          },
          missingDataFamilies: ['Market evidence'],
          blockedProductSurfaces: ['Research Radar'],
          nextOperatorAction: 'Wait for market evidence before reviewing candidates.',
          observationOnly: true,
          decisionGrade: false,
        }
      : null,
    onboardingGuidance: {
      title: mode === 'blocked' ? 'Candidate generation unavailable' : 'No candidates met current conditions',
      summary: mode === 'blocked'
        ? 'Market evidence must be ready before candidate rows can be shown.'
        : 'No symbols passed the current research conditions.',
      conditionsDetected: mode === 'blocked' ? ['Market evidence unavailable'] : ['No candidates'],
    },
  };
}

function researchQueuePayload() {
  return {
    schemaVersion: 'research_queue_v1',
    researchQueue: [
      {
        queueItemId: 'watchlist-ALFA',
        sourceSurface: 'watchlist',
        symbol: 'ALFA',
        title: 'Watchlist follow-up',
        priorityTier: 'follow_up',
        whyQueued: ['Saved observation needs quote freshness review.'],
        evidenceUsed: ['Watchlist row evidence.'],
        evidenceGaps: ['Quote freshness needs review.'],
        freshness: { state: 'needs_review', lastReviewedAt: now },
        suggestedResearchPath: [
          {
            label: 'Stock Structure',
            route: '/stocks/ALFA/structure-decision',
            section: 'watchlist',
            reason: 'Review stock evidence.',
          },
        ],
        observationOnly: true,
      },
    ],
    aggregateSummary: {
      itemCount: 1,
      limit: 5,
      bounded: false,
      bySourceSurface: { watchlist: 1 },
      byPriorityTier: { follow_up: 1 },
    },
    sourceSurfacesAggregated: ['watchlist'],
    evidenceGaps: ['Quote freshness needs review.'],
    dataQuality: {
      state: 'partial',
      itemCount: 1,
      sourceSurfacesAvailable: ['watchlist'],
      sourceSurfacesExpected: ['scanner', 'watchlist', 'market', 'manual_gap'],
      failClosed: true,
    },
    noAdviceDisclosure: 'Research-only queue.',
    observationOnly: true,
    decisionGrade: false,
  };
}

function watchlistItem(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: overrides.id ?? 1,
    symbol: overrides.symbol ?? 'ALFA',
    market: overrides.market ?? 'US',
    identity: {
      canonicalSymbol: overrides.symbol ?? 'ALFA',
      displaySymbol: overrides.symbol ?? 'ALFA',
      market: overrides.market ?? 'US',
      exchange: 'NASDAQ',
      displayName: overrides.name ?? 'Alpha Research Inc.',
      identityState: 'available',
    },
    name: overrides.name ?? 'Alpha Research Inc.',
    source: overrides.source ?? 'scanner',
    scannerRunId: 177,
    scannerRank: 1,
    scannerScore: overrides.scannerScore ?? 82,
    lastScoredAt: overrides.lastScoredAt ?? now,
    scoreSource: 'scanner_run',
    scoreProfile: 't177',
    scoreReason: 'Relative strength crossed the research threshold.',
    scoreStatus: overrides.scoreStatus ?? 'stale',
    researchReadiness: {
      state: overrides.readinessState ?? 'partial',
      freshnessState: overrides.freshnessState ?? 'stale',
      identityState: 'available',
      lastReviewedAt: overrides.lastReviewedAt ?? now,
      scoreFreshnessImplied: false,
      sourceAuthorityImplied: false,
    },
    notes: 'Observation only; quote freshness needs review.',
    intelligence: {
      scanner: {
        lastScore: overrides.scannerScore ?? 82,
        lastRank: 1,
        status: 'selected',
        reason: 'Relative strength crossed the research threshold.',
        lastScannedAt: overrides.lastScoredAt ?? now,
        scannerLineageV1: {
          contractVersion: 'scanner_watchlist_lineage_v1',
          source: 'scanner',
          scannerRunId: 177,
          symbol: overrides.symbol ?? 'ALFA',
          market: overrides.market ?? 'US',
          rankAtScan: 1,
          scoreAtScan: overrides.scannerScore ?? 82,
          scoreSnapshotKind: 'saved_at_add',
          runProfile: 't177',
          runCompletedAt: now,
          watchlistAddedAt: now,
          researchReason: 'Relative strength crossed the research threshold.',
          researchNextStep: 'Review structure evidence and quote timestamp.',
          dataState: overrides.freshnessState === 'stale' ? 'limited' : 'available',
          freshnessLabel: overrides.freshnessState === 'stale' ? 'Needs review' : 'Available',
          noAdviceBoundary: true,
          observationOnly: true,
          scoreGradeAllowed: false,
        },
      },
      strategySimulation: {
        status: 'partial',
        avgForwardReturnPct: null,
        hitRate: null,
      },
      backtest: {
        lastResultId: 177,
        totalReturnPct: 14.2,
        maxDrawdownPct: -3.2,
        sharpe: 1.5,
        tradeCount: 5,
        testedAt: now,
      },
      catalystExposures: [
        {
          id: 'cat-1',
          symbol: overrides.symbol ?? 'ALFA',
          market: overrides.market ?? 'US',
          category: 'stored_news_catalyst_proxy',
          title: 'Stored catalyst proxy',
          summary: 'Catalyst evidence is delayed and observation-only.',
          evidenceStatus: 'stale',
          evidenceLabels: ['stale'],
          asOf: now,
          reasonCodes: ['observation_only', 'stale_evidence'],
          observationOnly: true,
        },
      ],
    },
    rowResearchPacket: {
      symbol: overrides.symbol ?? 'ALFA',
      market: String(overrides.market ?? 'US').toLowerCase(),
      identity: {
        canonicalSymbol: overrides.symbol ?? 'ALFA',
        displaySymbol: overrides.symbol ?? 'ALFA',
        displayName: overrides.name ?? 'Alpha Research Inc.',
        exchange: 'NASDAQ',
        identityState: 'available',
      },
      savedItemSource: 'scanner',
      quote: {
        state: overrides.quoteState ?? 'stale',
        price: overrides.price ?? 123.45,
        changePercent: overrides.changePercent ?? -1.25,
        asOf: overrides.quoteAsOf ?? '2026-07-05T20:00:00Z',
      },
      scannerLineage: {
        runId: 177,
        rank: 1,
        score: overrides.scannerScore ?? 82,
        status: 'selected',
        lastScoredAt: overrides.lastScoredAt ?? now,
      },
      researchStatus: overrides.researchStatus ?? 'partial',
      researchReadiness: {
        state: overrides.readinessState ?? 'partial',
        freshnessState: overrides.freshnessState ?? 'stale',
        identityState: 'available',
        lastReviewedAt: overrides.lastReviewedAt ?? now,
        scoreFreshnessImplied: false,
        sourceAuthorityImplied: false,
      },
      missingData: ['Quote freshness needs review.'],
      nextDataAction: 'Review structure evidence and quote timestamp.',
      observationOnly: true,
      noAdviceDisclosure: 'Research observation only.',
    },
    createdAt: now,
    updatedAt: now,
  };
}

function watchlistPayload(mode: WatchlistMode = 'populated') {
  if (mode === 'empty') return { items: [] };
  return {
    items: [
      watchlistItem(),
      watchlistItem({
        id: 2,
        symbol: 'BETA',
        name: 'Beta Evidence Ltd.',
        market: 'HK',
        scannerScore: 58,
        scoreStatus: 'partial',
        readinessState: 'partial',
        freshnessState: 'partial',
        quoteState: 'available',
        price: 88.1,
        changePercent: 0.42,
      }),
    ],
  };
}

function watchlistOverlayPayload(mode: WatchlistMode = 'populated') {
  return {
    schemaVersion: 'watchlist_research_overlay_v1',
    overlayState: mode === 'empty' ? 'empty' : 'partial',
    researchSummary: mode === 'empty'
      ? 'No saved symbols are available for review.'
      : 'Saved symbols need freshness review.',
    researchPriorityQueue: mode === 'empty' ? [] : [
      {
        symbol: 'ALFA',
        priorityTier: 'follow_up',
        priorityReasonSafeLabel: 'Quote freshness needs review.',
        evidenceAge: { state: 'needs_review', lastReviewedAt: now },
        missingEvidence: ['Quote freshness needs review.'],
        suggestedResearchPath: [
          {
            label: 'Stock Structure',
            route: '/stocks/ALFA/structure-decision',
            section: 'watchlist',
            reason: 'Review stock evidence.',
          },
        ],
        observationOnly: true,
      },
    ],
    observationOnly: true,
    decisionGrade: false,
  };
}

function refreshStatusPayload() {
  return {
    enabled: true,
    usTime: '09:30',
    cnTime: '21:30',
    hkTime: '21:30',
    status: 'idle',
    lastRunAt: null,
    nextRunAt: null,
  };
}

async function installT177Harness(page: Page, options: HarnessOptions = {}) {
  const radarMode = options.radarMode ?? 'candidate';
  const watchlistMode = options.watchlistMode ?? 'populated';
  requestLog.length = 0;

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();
    const path = url.pathname;
    requestLog.push(`${method} ${path}`);

    if (method === 'GET' && path === '/api/v1/auth/status') return fulfillJson(route, authStatus());
    if (method === 'GET' && path === '/api/v1/auth/me') return fulfillJson(route, currentUser);
    if (method === 'GET' && path === '/api/v1/agent/status') return fulfillJson(route, { enabled: false });
    if (method === 'GET' && path === '/api/v1/history') return fulfillJson(route, { total: 0, page: 1, limit: 20, items: [] });
    if (method === 'GET' && path === '/api/v1/analysis/tasks') return fulfillJson(route, { tasks: [], total: 0 });
    if (method === 'GET' && path === '/api/v1/research/radar') return fulfillJson(route, radarPayload(radarMode));
    if (method === 'GET' && path === '/api/v1/research/queue') return fulfillJson(route, researchQueuePayload());
    if (method === 'GET' && path === '/api/v1/watchlist/items') return fulfillJson(route, watchlistPayload(watchlistMode));
    if (method === 'GET' && path === '/api/v1/watchlist/research-overlay') return fulfillJson(route, watchlistOverlayPayload(watchlistMode));
    if (method === 'GET' && path === '/api/v1/watchlist/refresh-status') return fulfillJson(route, refreshStatusPayload());
    if (method === 'GET' && path === '/api/v1/user-alerts/rules') {
      return fulfillJson(route, {
        contract_version: 'user_alert_contract_v1',
        delivery_mode: 'in_app',
        in_app_only: true,
        owner_scoped: true,
        items: [],
      });
    }
    if (method === 'GET' && path === '/api/v1/user-alerts/events') {
      return fulfillJson(route, {
        contract_version: 'user_alert_contract_v1',
        delivery_mode: 'in_app',
        in_app_only: true,
        owner_scoped: true,
        total: 0,
        limit: 20,
        offset: 0,
        items: [],
      });
    }
    if (method === 'POST' && path === '/api/v1/analysis/async') {
      return fulfillJson(route, { task_id: 'task-177', status: 'accepted' });
    }

    return fulfillJson(route, { error: `Unhandled T177 harness route: ${method} ${path}` }, 500);
  });
}

async function expectNoPageOverflow(page: Page) {
  await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

async function expectNoAdviceOrRawDiagnostics(page: Page) {
  const body = page.locator('body');
  await expect(body).not.toContainText(/买入|卖出|持有|目标价|止损|仓位建议|buy now|sell now|target price|position sizing/i);
  await expect(body).not.toContainText(/requestId|traceId|contractVersion|sourceClass|provider routing|raw lineage|backend stack/i);
}

function expectNoReadSideEffects() {
  expect(requestLog.some((entry) => entry.startsWith('POST /api/v1/watchlist'))).toBe(false);
  expect(requestLog.some((entry) => entry.includes('/refresh-scores'))).toBe(false);
  expect(requestLog.some((entry) => entry.includes('/scanner'))).toBe(false);
}

test.describe('T177 Radar and Watchlist research continuity', () => {
  test('qualifies Radar candidate workflow on desktop and narrow viewports', async ({ page }) => {
    const consoleErrors: string[] = [];
    const pageErrors: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error' && !message.text().includes('favicon.ico')) consoleErrors.push(message.text());
    });
    page.on('pageerror', (error) => pageErrors.push(error.message));

    for (const viewport of [
      { width: 1440, height: 1000 },
      { width: 1024, height: 900 },
      { width: 390, height: 844 },
    ]) {
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      await installT177Harness(page, { radarMode: 'candidate', watchlistMode: 'populated' });
      await page.setViewportSize(viewport);
      await page.goto('/zh/research/radar?market=us&limit=5');
      await page.waitForLoadState('domcontentloaded');

      await expect(page).toHaveURL(/\/zh\/research\/radar\?market=us&limit=5/);
      await expect(page.getByTestId('research-radar-page')).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('research-radar-candidate-ledger')).toBeVisible();
      await expect(page.getByTestId('research-radar-selected-candidate-detail')).toBeVisible();
      await expect(page.getByTestId('research-radar-factor-bars')).toContainText('70');
      await expect(page.getByTestId('research-radar-selected-candidate-detail')).toContainText(/数据时效|Data freshness/);
      await expect(page.getByTestId('research-radar-selected-candidate-detail')).toContainText(/Quote freshness is partial|报价|时效|partial/i);

      const betaButton = page.getByRole('button', { name: /查看 BETA 研究细节|Inspect BETA/ });
      await betaButton.focus();
      await page.keyboard.press('Enter');
      await expect(page.getByTestId('research-radar-selected-candidate-detail')).toContainText('BETA');

      const stockLink = page.getByRole('link', { name: '查看个股研究' });
      await expect(stockLink).toHaveAttribute('href', /\/zh\/stocks\/BETA\/structure-decision\?symbol=BETA&market=US/);
      const watchlistLink = page.getByRole('link', { name: '打开观察列表视图' });
      await expect(watchlistLink).toHaveAttribute('href', /\/zh\/watchlist\?symbol=BETA&market=US&source=scanner/);
      await watchlistLink.focus();
      await page.keyboard.press('Enter');
      await expect(page).toHaveURL(/\/zh\/watchlist\?symbol=BETA&market=US&source=scanner/);

      await expectNoPageOverflow(page);
      await expectNoAdviceOrRawDiagnostics(page);
      expectNoReadSideEffects();
      expect(pageErrors).toEqual([]);
      expect(consoleErrors).toEqual([]);
    }
  });

  test('qualifies Radar zero and blocked readiness states', async ({ page }) => {
    const consoleErrors: string[] = [];
    const pageErrors: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error' && !message.text().includes('favicon.ico')) consoleErrors.push(message.text());
    });
    page.on('pageerror', (error) => pageErrors.push(error.message));

    await installT177Harness(page, { radarMode: 'zero', watchlistMode: 'empty' });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto('/zh/research/radar?market=us&limit=5');
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByTestId('research-radar-queue-empty-state')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('research-radar-page')).toContainText(/No candidates met current conditions|当前没有研究候选|暂无候选/i);
    await expect(page.getByTestId('research-radar-market-level-fallback')).toHaveCount(0);
    await expectNoPageOverflow(page);
    await expectNoAdviceOrRawDiagnostics(page);
    expectNoReadSideEffects();

    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await installT177Harness(page, { radarMode: 'blocked', watchlistMode: 'empty' });
    await page.goto('/zh/research/radar?market=us&limit=5');
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByTestId('research-radar-queue-empty-state')).toBeVisible({ timeout: 15_000 });
    await page.getByTestId('research-radar-diagnostics-disclosure').locator('summary').click();
    await expect(page.getByTestId('research-radar-market-level-fallback')).toBeVisible();
    await expect(page.getByTestId('research-radar-market-level-fallback')).toContainText(/候选生成未执行|Candidate generation not executed/);
    await expect(page.getByTestId('research-radar-market-level-fallback')).toContainText(/Market evidence|市场证据/);
    await expectNoPageOverflow(page);
    await expectNoAdviceOrRawDiagnostics(page);
    expectNoReadSideEffects();
    expect(pageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });

  test('qualifies Watchlist ledger, empty route retention, and stock handoff', async ({ page }) => {
    const consoleErrors: string[] = [];
    const pageErrors: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error' && !message.text().includes('favicon.ico')) consoleErrors.push(message.text());
    });
    page.on('pageerror', (error) => pageErrors.push(error.message));

    for (const viewport of [
      { width: 390, height: 844 },
      { width: 1024, height: 900 },
    ]) {
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      await installT177Harness(page, { radarMode: 'candidate', watchlistMode: 'populated' });
      await page.setViewportSize(viewport);
      await page.goto('/zh/watchlist?symbol=ALFA&market=US');
      await page.waitForLoadState('domcontentloaded');
      await expect(page).toHaveURL(/\/zh\/watchlist\?symbol=ALFA&market=US/);
      await expect(page.getByTestId('watchlist-page')).toBeVisible({ timeout: 15_000 });
      await expect(page.getByRole('table', { name: '观察列表研究台账' })).toBeVisible();
      await expect(page.getByTestId('watchlist-detail-rail')).toBeVisible();
      await expect(page.getByTestId('watchlist-detail-rail')).toContainText('ALFA');
      await expect(page.getByTestId('watchlist-detail-rail')).toContainText(/数据备注|Data notes|当前状态|Current state/);

      const ledgerOverflow = await page.getByTestId('watchlist-primary-work-region').evaluate((node) => {
        const element = node as HTMLElement;
        const table = element.querySelector('[data-testid="watchlist-candidate-list"]') as HTMLElement | null;
        return {
          bodyOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
          internalOverflow: Boolean(table && table.scrollWidth > element.clientWidth),
        };
      });
      expect(ledgerOverflow.bodyOverflow).toBe(false);
      if (viewport.width === 390) expect(ledgerOverflow.internalOverflow).toBe(true);
    }

    await page.goto('/zh/watchlist');
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByTestId('watchlist-row-BETA')).toBeVisible({ timeout: 15_000 });
    const betaDetailButton = page.getByRole('button', { name: /查看详情 BETA|View details BETA/ });
    await betaDetailButton.focus();
    await page.keyboard.press('Enter');
    await expect(page.getByTestId('watchlist-detail-rail')).toContainText('BETA');

    const structureButton = page.getByTestId('watchlist-detail-rail').getByRole('button', { name: /结构|Structure/ }).first();
    await structureButton.focus();
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(/\/zh\/stocks\/BETA\/structure-decision/);

    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await installT177Harness(page, { radarMode: 'candidate', watchlistMode: 'empty' });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto('/zh/watchlist');
    await page.waitForLoadState('domcontentloaded');
    await expect(page).toHaveURL(/\/zh\/watchlist$/);
    await expect(page.getByTestId('watchlist-compact-empty-state')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('watchlist-empty-preview')).toHaveCount(0);
    await expect(page.getByTestId('watchlist-candidate-list')).toHaveCount(0);
    await expectNoPageOverflow(page);
    await expectNoAdviceOrRawDiagnostics(page);
    expectNoReadSideEffects();
    expect(pageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });
});
