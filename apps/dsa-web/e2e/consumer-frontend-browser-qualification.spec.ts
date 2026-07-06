import type { Locator, Page, Route } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { expect, test } from './fixtures/appSmoke';
import { installPortfolioSmokeHarness } from './fixtures/portfolioSmoke';
import { buildHomeEvidencePacketShell } from './fixtures/smokeEvidence';

const viewports = [
  { width: 1440, height: 1000 },
  { width: 1024, height: 900 },
  { width: 768, height: 900 },
  { width: 390, height: 844 },
] as const;

type QualificationRoute = {
  key: string;
  label: string;
  path: string;
  readyTestId: string;
  type: 'standard' | 'portfolio';
  evidenceTestIds?: string[];
};

type FindingSeverity = 'P0' | 'P1' | 'P2';
type FindingCategory =
  | 'responsive'
  | 'accessibility'
  | 'body-overflow'
  | 'internal-overflow'
  | 'navigation'
  | 'keyboard';

type Finding = {
  severity: FindingSeverity;
  category: FindingCategory;
  route: string;
  viewport: string;
  state: string;
  symptom: string;
  probableOwner: string;
  reproductionSteps: string[];
};

type RouteViewportEvidence = {
  route: string;
  label: string;
  path: string;
  viewport: string;
  finalUrl: string;
  bodyOverflow: boolean;
  unexpectedFixedWidth: number;
  internalOverflowCount: number;
  stickyCollisionCount: number;
  navigationReachable: boolean;
  firstViewportHierarchy: string[];
  actionReachable: boolean;
  chartClippingCount: number;
  tableClippingCount: number;
  mobileStackingRisk: boolean;
  landmarkCount: number;
  h1Count: number;
  ariaCurrentCount: number;
  unlabeledFormControlCount: number;
  unnamedTableCount: number;
  focusVisible: boolean;
  stateMeaningColorOnlyRisk: boolean;
  evidenceSectionsVisible: string[];
  findings: Finding[];
};

type JourneyEvidence = {
  name: string;
  status: 'pass' | 'fail';
  route: string;
  viewport: string;
  notes: string[];
  findings: Finding[];
};

const timestamp = '2026-07-06T09:30:00Z';
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

const routes: QualificationRoute[] = [
  { key: 'home', label: 'Home', path: '/zh', readyTestId: 'home-bento-dashboard', type: 'standard', evidenceTestIds: ['home-research-console', 'home-research-chart-section'] },
  { key: 'market-overview', label: 'Market Overview', path: '/zh/market-overview', readyTestId: 'market-overview-shell', type: 'standard', evidenceTestIds: ['market-overview-decision-readiness'] },
  { key: 'radar', label: 'Radar', path: '/zh/research/radar', readyTestId: 'research-radar-page', type: 'standard', evidenceTestIds: ['research-radar-consumer-overview', 'research-radar-evidence-hub'] },
  { key: 'stock-research', label: 'Stock Research', path: '/zh/stocks/AAPL/structure-decision', readyTestId: 'stock-structure-decision-page', type: 'standard', evidenceTestIds: ['stock-consumer-research-summary', 'stock-first-viewport-summary-panel'] },
  { key: 'evidence', label: 'Evidence', path: '/zh/stocks/AAPL/structure-decision', readyTestId: 'stock-structure-decision-page', type: 'standard', evidenceTestIds: ['single-stock-evidence-pack-registry', 'stock-evidence-ledger'] },
  { key: 'structure-decision', label: 'Structure Decision', path: '/zh/stocks/AAPL/structure-decision', readyTestId: 'stock-structure-decision-page', type: 'standard', evidenceTestIds: ['stock-options-structure-surface', 'stock-quote-boundary-panel'] },
  { key: 'watchlist', label: 'Watchlist', path: '/zh/watchlist', readyTestId: 'watchlist-page', type: 'standard', evidenceTestIds: ['watchlist-candidate-list'] },
  { key: 'scanner', label: 'Scanner', path: '/zh/scanner', readyTestId: 'user-scanner-workspace', type: 'standard', evidenceTestIds: ['scanner-ranked-list', 'scanner-workflow-summary'] },
  { key: 'backtest', label: 'Backtest', path: '/zh/backtest', readyTestId: 'backtest-bento-page', type: 'standard', evidenceTestIds: ['normal-backtest-workspace', 'normal-backtest-execution-readiness'] },
  { key: 'backtest-result', label: 'Backtest result', path: '/zh/backtest/results/34', readyTestId: 'deterministic-backtest-result-page', type: 'standard', evidenceTestIds: ['backtest-result-report', 'backtest-report-chart'] },
  { key: 'scenario-lab', label: 'Scenario Lab', path: '/zh/scenario-lab', readyTestId: 'scenario-lab-page', type: 'standard', evidenceTestIds: ['scenario-lab-setup-idle'] },
  { key: 'portfolio', label: 'Portfolio', path: '/zh/portfolio', readyTestId: 'portfolio-bento-page', type: 'portfolio', evidenceTestIds: ['portfolio-summary-hero', 'portfolio-accounts-panel'] },
];

const evidence: { responsive: RouteViewportEvidence[]; journeys: JourneyEvidence[] } = {
  responsive: [],
  journeys: [],
};
const strictQualification = process.env.STRICT_CONSUMER_FRONTEND_QUALIFICATION === '1';

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function installSignedInOverrides(page: Page) {
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

function symbolFromStockPath(route: Route) {
  const parts = new URL(route.request().url()).pathname.split('/');
  return decodeURIComponent(parts[4] || 'AAPL').toUpperCase();
}

async function installStockOverrides(page: Page) {
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
        source_label: 'Playwright Fixture',
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
      identity: { name: symbol, exchange: 'NASDAQ', sector: 'Technology', industry: 'Hardware' },
      quote: { state: 'available', price: 211.32, change_percent: 0.59, as_of: timestamp },
      history: { state: 'available', bars: 90, period: 'daily', as_of: '2026-07-06' },
      structure: { state: 'available', label: 'Range-bound', confidence: 'medium', as_of: '2026-07-06' },
      fundamentals: { state: 'not_integrated', fields_available: [] },
      events: { state: 'missing', latest: [] },
      peer: { state: 'insufficient', benchmark: 'QQQ' },
      missing_data: ['peer evidence'],
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
      confidence_cap: { value: 55, label: 'Medium', reasons: ['Fixture route evidence is bounded.'] },
      confidence_state: { status: 'partial', label: 'Evidence limited', reasons: ['Peer evidence remains incomplete.'] },
      component_scores: { trend: 58, relativeStrength: 52, evidenceQuality: 45 },
      explanation: {
        why_this_structure: 'Price evidence remains range-bound in the browser qualification fixture.',
        what_confirms_it: ['Fresh price evidence remains available.'],
        what_invalidates_it: ['Evidence falls out of date.'],
        key_levels: [{ kind: 'support', value: 198.5, description: 'Fixture support level.' }],
      },
      research_notes: {
        watch_next: ['Refresh quote evidence before deeper review.'],
        needs_more_evidence: ['Comparable peer evidence.'],
        risk_flags: ['Evidence is partial.'],
      },
      data_quality: { status: 'partial', period: 'daily', requested_days: 120, observed_bars: 90, usable_bars: 90, reason: 'Fixture route smoke coverage.' },
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

  await page.route('**/api/v1/stocks/*/technical-indicators', async (route) => {
    await fulfillJson(route, {
      symbol: symbolFromStockPath(route),
      as_of: timestamp,
      summary: {
        trend: 'range',
        momentum: 'neutral',
        volatility: 'normal',
      },
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
    });
  });

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
      gamma_flip_level: {
        state: 'not_available',
        level: null,
        reason: 'authorized_structure_source_needed',
      },
      total_dealer_gamma_exposure: null,
      blocking_reasons: ['options_structure_unavailable'],
      warnings: [],
      next_evidence_needed: ['authorized_structure_source_needed'],
    });
  });

  await page.route('**/api/v1/stocks/*/evidence**', async (route) => {
    await fulfillJson(route, buildHomeEvidencePacketShell(timestamp));
  });
}

async function installMarketOverviewOverrides(page: Page) {
  await page.route('**/api/v1/market/data-readiness**', async (route) => {
    await fulfillJson(route, {
      readiness_status: 'ready',
      diagnostic_only: true,
      provider_runtime_called: false,
      network_calls_enabled: false,
      representative_symbols: ['ORCL'],
      checks: [],
    });
  });

  await page.route('**/api/v1/market/professional-data-capabilities', async (route) => {
    await fulfillJson(route, {
      contract_version: 'browser_qualification_professional_data_capability_registry_v1',
      consumer_safe: true,
      summary: {
        total_capabilities: 0,
        live_count: 0,
        degraded_count: 0,
        entitlement_required_count: 0,
        configured_missing_count: 0,
        unavailable_count: 0,
        readiness_label: 'Fixture coverage only',
        operator_next_action: 'Use targeted UAT data fixtures for route verification.',
      },
      categories: [],
      capabilities: [],
      generated_at: timestamp,
    });
  });

  await page.route('**/api/v1/market/regime-read-model', async (route) => {
    await fulfillJson(route, {
      contract_version: 'browser_qualification_market_regime_read_model_v1',
      status: 'partial',
      symbols: ['SPY', 'QQQ'],
      regime: {
        label: 'fixture_observation',
        status: 'partial',
        source: 'browser_qualification_fixture',
      },
      product_summary: 'Browser qualification fixture keeps market overview data diagnostics bounded.',
      evidence_cards: [],
      symbol_context: [],
      surface_hints: [],
      missing_data_families: [],
      blocked_product_surfaces: [],
      readiness: {
        label: 'fixture_only',
        status: 'partial',
        missing_data_families: [],
        blocked_product_surfaces: [],
        next_operator_action: 'Run dedicated data UAT outside browser qualification coverage.',
      },
      data_quality: {
        adjusted_coverage_state: 'partial',
        ohlcv_coverage: { state: 'partial', required_bars: 60, available_symbols: ['SPY'], missing_symbols: [] },
        quote_snapshot_coverage: { state: 'partial', availability_state: 'partial', freshness_state: 'fixture', available_symbols: ['SPY'], missing_symbols: [], stale_symbols: [] },
        missing_data_families: [],
        blocked_product_surfaces: [],
      },
    });
  });
}

async function installWatchlistOverrides(page: Page) {
  await page.route('**/api/v1/watchlist/items', async (route) => {
    await fulfillJson(route, {
      items: [
        {
          id: 1,
          symbol: 'NVDA',
          market: 'us',
          name: 'NVIDIA',
          source: 'scanner',
          scannerRunId: 42,
          scannerRank: 1,
          scannerScore: 94,
          lastScoredAt: '2026-07-06T09:30:00Z',
          scoreSource: 'scanner_run',
          scoreProfile: 'us_preopen_v1',
          scoreReason: 'Latest scanner score.',
          scoreStatus: 'fresh',
          scoreStatusContext: {
            scope: 'score_refresh_recency',
            freshMeans: 'persisted_scanner_score_refreshed',
            sourceFreshnessImplied: false,
            sourceAuthorityImplied: false,
          },
          scoreError: null,
          intelligence: {
            scanner: {
              lastScore: 94,
              lastRank: 1,
              status: 'selected',
              theme: 'ai-momentum',
              themeLabel: 'AI Momentum',
              profile: 'us_preopen_v1',
              reason: 'Latest scanner score.',
              lastScannedAt: '2026-07-06T09:30:00Z',
            },
            strategySimulation: {
              lookbackDays: 90,
              forwardDays: 5,
              avgForwardReturnPct: 3.2,
              hitRate: 0.56,
              avgExcessReturnPct: 2.1,
              selectionCount: 5,
              dataCoverage: 0.83,
              status: 'ready',
            },
            backtest: {
              lastResultId: 33,
              totalReturnPct: 24.6,
              maxDrawdownPct: -8.2,
              sharpe: 1.34,
              tradeCount: 6,
              testedAt: '2026-07-06T09:30:00Z',
            },
          },
          themeId: 'ai-momentum',
          universeType: 'theme',
          notes: null,
          createdAt: '2026-07-06T08:00:00Z',
          updatedAt: '2026-07-06T09:00:00Z',
        },
      ],
    });
  });

  await page.route('**/api/v1/watchlist/research-overlay', async (route) => {
    await fulfillJson(route, {
      schema_version: 'watchlist_research_overlay_v1',
      overlay_state: 'ready',
      research_summary: 'Browser qualification fixture keeps watchlist overlay bounded.',
      research_priority_queue: [],
      observation_only: true,
      decision_grade: false,
      data_quality: { state: 'partial', item_count: 0 },
    });
  });
}

function cockpitPayload() {
  return {
    schemaVersion: 'market_decision_cockpit.v1',
    generatedAt: timestamp,
    marketRegimeDecision: {
      regime: 'riskOn',
      confidence: 'medium',
      confidenceScore: 0.68,
      driverScores: {
        breadthParticipation: { score: 58, evidenceState: 'score_grade' },
        volatilityStructure: { score: 72, evidenceState: 'score_grade' },
      },
    },
    researchQueuePreview: { topCandidates: [], queueQuality: 'mixed', evidenceGaps: [], previewOnly: true },
    optionsStructureStatus: { gammaEvidenceStatus: 'unavailable', observationOnly: true, decisionGrade: false, missingEvidence: [] },
    cockpitSummary: { whatChanged: [], whyItMatters: [], whatToWatch: [], confidenceLimits: [] },
    noAdviceDisclosure: 'Research context only.',
    dataQuality: { status: 'partial' },
  };
}

function scenarioPayload() {
  return {
    schemaVersion: 'market_scenario_lab_engine.v1',
    contractStatus: {
      state: 'degraded',
      label: 'Scenario constrained by evidence gaps',
      message: 'Scenario comparison is available, but incomplete evidence keeps the result observation-only.',
    },
    selectedScenario: {
      presetId: 'volatilitySpike',
      name: 'volatilitySpike',
      label: 'Volatility stress observation',
      category: 'Stress frame',
      description: 'Stress selected drivers to compare research-context sensitivity.',
      inputAssumptions: ['Uses market context supplied with the request.'],
      expectedDriverImpacts: [{ driver: 'Volatility structure', direction: 'pressure', magnitude: 'high' }],
      evidenceLimits: ['Breadth and volatility observations need fresh confirmation before the frame can strengthen.'],
    },
    baseMarketContext: {
      label: 'Decision Cockpit market context',
      message: 'Base regime context was supplied by the request and is treated as observation-only evidence.',
      evidenceState: 'degraded',
      scoringDriverCount: 6,
    },
    baseRegime: { regime: 'riskOn', confidence: 'medium', confidenceScore: 0.68 },
    scenarioRegime: { regime: 'mixed', confidence: 'low', confidenceScore: 0.43 },
    baselineReadiness: {
      status: 'partial',
      baselineSnapshot: { state: 'partial', available: false, lastUpdated: timestamp, affectedComponents: ['baselineSnapshot'] },
      marketFrame: { state: 'available', available: true, lastUpdated: timestamp, affectedComponents: [] },
      driverInputs: { state: 'partial', availableDriverKeys: ['breadthParticipation', 'volatilityStructure'], missingDriverKeys: ['dealerGamma'], affectedDriverKeys: ['dealerGamma'] },
      evidenceCompleteness: { state: 'partial', gaps: ['baselineSnapshot', 'dealerGamma'] },
      observationOnly: true,
      blocked: false,
      affectedBaselineComponents: ['baselineSnapshot'],
      affectedDriverKeys: ['dealerGamma'],
      evidenceGaps: ['baselineSnapshot', 'dealerGamma'],
      lastUpdated: timestamp,
    },
    confidenceDelta: -0.25,
    driverDeltas: { breadthParticipation: -75, volatilityStructure: -145 },
    changedDrivers: ['breadthParticipation', 'volatilityStructure'],
    scenarioSummary: ['Breadth participation weakens quickly under the selected stress.'],
    whatWouldConfirm: ['Score-grade evidence would need to show stressed drivers moving together.'],
    whatWouldInvalidate: ['The scenario frame weakens if score-grade evidence does not move with the selected shocks.'],
    evidenceLimits: ['Breadth and volatility observations need fresh confirmation before the frame can strengthen.'],
    noAdviceDisclosure: 'Research planning only.',
  };
}

async function installScenarioOverrides(page: Page) {
  await page.route('**/api/v1/market/decision-cockpit**', async (route) => {
    await fulfillJson(route, cockpitPayload());
  });
  await page.route('**/api/v1/market/scenario-lab**', async (route) => {
    await fulfillJson(route, scenarioPayload());
  });
}

async function installRadarOverrides(page: Page) {
  const radarPayload = {
    schema_version: 'research_radar_api_v1',
    generated_at: timestamp,
    research_queue: [
      {
        symbol: 'NVDA',
        ticker: 'NVDA',
        priority: 'observe',
        research_bias: 'strengthContinuation',
        driver_scores: { relative_strength: 72, liquidity: 61 },
        why_on_radar: ['Relative strength remains visible, but evidence is still partial.'],
        what_to_verify: ['Refresh comparable peer evidence before drawing conclusions.'],
        invalidation_observations: ['Evidence falls out of date.'],
        risk_flags: ['Evidence is partial.'],
        evidence_quality: { status: 'partial', score: 54 },
      },
    ],
    aggregate_summary: {
      queue_quality: 'mixed',
      priority_counts: { observe: 1 },
      source: { scanner_run_id: 11, market: 'us' },
    },
    evidence_gaps: ['peer evidence'],
    market_context_fit: 'neutral',
    no_advice_disclosure: 'Research-only queue.',
    data_quality: { status: 'partial', missing_evidence: ['peer evidence'] },
    evidence_hub: {
      scanner_candidates: {
        key: 'scanner',
        label: 'Scanner candidates',
        status: 'available',
        summary: 'Scanner candidate evidence is available for radar review.',
        next_data_action: 'Refresh scanner when candidate evidence needs a newer observation window.',
        evidence_count: 1,
        total_count: 1,
        symbols: ['NVDA'],
        details: ['NVDA is available for radar review.'],
        observation_only: true,
        decision_grade: false,
      },
      backtest_samples: {
        key: 'backtest',
        label: 'Backtest samples',
        status: 'blocked',
        summary: 'Backtest samples are unavailable for radar symbols.',
        blocker: 'Backtest samples have not been prepared for the radar symbols.',
        next_data_action: 'Open Backtest and prepare or refresh samples for the radar symbols.',
        evidence_count: 0,
        total_count: 1,
        symbols: ['NVDA'],
        details: ['NVDA has no prepared backtest samples.'],
        observation_only: true,
        decision_grade: false,
      },
      stock_readiness: {
        key: 'stock',
        label: 'Stock readiness',
        status: 'available',
        summary: 'Stock technical readiness is available for radar symbols.',
        next_data_action: 'Refresh daily price history and technical evidence for radar symbols.',
        evidence_count: 1,
        total_count: 1,
        symbols: ['NVDA'],
        details: ['NVDA has technical readiness evidence.'],
        observation_only: true,
        decision_grade: false,
      },
      data_activation: {
        key: 'data',
        label: 'Data activation',
        status: 'partial',
        summary: 'Research Radar evidence is partially activated.',
        blocker: 'Backtest samples have not been prepared for the radar symbols.',
        next_data_action: 'Resolve blocked evidence slices, then refresh Research Radar.',
        evidence_count: 2,
        total_count: 3,
        details: ['Scanner candidates status available.', 'Backtest samples status blocked.', 'Stock readiness status available.'],
        observation_only: true,
        decision_grade: false,
      },
      missing_evidence_states: [],
    },
  };
  const queuePayload = {
    schema_version: 'research_queue_v1',
    research_queue: [
      {
        queue_item_id: 'scanner-NVDA-run-11-rank-1-item-1',
        source_surface: 'scanner',
        symbol: 'NVDA',
        title: 'Scanner candidate review',
        priority_tier: 'follow_up',
        why_queued: ['Scanner candidate is available for follow-up research review.'],
        evidence_used: ['Technicals available', 'Liquidity available'],
        evidence_gaps: [],
        freshness: { state: 'current', last_reviewed_at: timestamp },
        suggested_research_path: [
          {
            label: 'Stock Structure',
            route: '/stocks/NVDA/structure-decision',
            section: 'scannerResearchOverlay',
            reason: 'Open symbol structure detail.',
          },
        ],
        observation_only: true,
        decision_grade: false,
      },
    ],
    aggregate_summary: {
      item_count: 1,
      limit: 5,
      bounded: false,
      by_source_surface: { scanner: 1 },
      by_priority_tier: { follow_up: 1 },
      queue_quality: 'mixed',
    },
    source_surfaces_aggregated: ['scanner'],
    evidence_gaps: [],
    data_quality: {
      state: 'ready',
      item_count: 1,
      source_surfaces_available: ['scanner'],
      source_surfaces_expected: ['scanner', 'watchlist', 'market', 'manual_gap'],
      fail_closed: true,
    },
    no_advice_disclosure: 'Research-only queue; verify evidence gaps before further review.',
    observation_only: true,
    decision_grade: false,
  };

  await page.route('**/api/v1/research/radar**', async (route) => {
    await fulfillJson(route, radarPayload);
  });
  await page.route('**/api/v1/research/queue**', async (route) => {
    await fulfillJson(route, queuePayload);
  });
}

async function installQualificationOverrides(page: Page) {
  await installSignedInOverrides(page);
  await installStockOverrides(page);
  await installMarketOverviewOverrides(page);
  await installWatchlistOverrides(page);
  await installScenarioOverrides(page);
  await installRadarOverrides(page);
}

async function waitForRoute(page: Page, route: QualificationRoute, options: { portfolioOperatorMode?: boolean } = {}) {
  if (route.type === 'portfolio') {
    if (options.portfolioOperatorMode) {
      await page.addInitScript(() => {
        window.sessionStorage.setItem('dsa-admin-surface-mode', 'admin');
      });
    }
    await installPortfolioSmokeHarness(page, { operatorMode: options.portfolioOperatorMode });
  }
  await page.goto(route.path);
  await page.waitForLoadState('domcontentloaded');
  await expect(page.getByTestId(route.readyTestId), route.label).toBeVisible({ timeout: 15_000 });
  await page.waitForLoadState('networkidle', { timeout: 5_000 }).catch(() => undefined);
  await page.waitForTimeout(250);
}

function defect(
  severity: FindingSeverity,
  category: FindingCategory,
  route: QualificationRoute,
  viewport: string,
  symptom: string,
  probableOwner: string,
  steps: string[],
): Finding {
  return {
    severity,
    category,
    route: route.label,
    viewport,
    state: 'signed-in consumer fixture',
    symptom,
    probableOwner,
    reproductionSteps: [`Open ${route.path}`, `Set viewport ${viewport}`, ...steps],
  };
}

async function collectRouteEvidence(page: Page, route: QualificationRoute, viewport: string): Promise<RouteViewportEvidence> {
  const metrics = await page.evaluate(() => {
    const viewportWidth = document.documentElement.clientWidth;
    const viewportHeight = window.innerHeight;
    const visible = (element: Element) => {
      const style = window.getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return style.display !== 'none'
        && style.visibility !== 'hidden'
        && Number(style.opacity) !== 0
        && rect.width > 0
        && rect.height > 0
        && rect.bottom > 0
        && rect.right > 0
        && rect.top < viewportHeight
        && rect.left < viewportWidth;
    };
    const text = (element: Element) => (element.textContent || '').replace(/\s+/g, ' ').trim();
    const isFocusable = (element: Element) => {
      const tag = element.tagName.toLowerCase();
      if (['button', 'input', 'select', 'textarea', 'a'].includes(tag)) {
        return !(element as HTMLButtonElement).disabled && (!element.hasAttribute('href') ? tag !== 'a' : true);
      }
      return element.hasAttribute('tabindex') || element.getAttribute('role') === 'button' || element.getAttribute('role') === 'menuitem';
    };
    const hasHorizontalScrollBoundary = (element: HTMLElement) => {
      let current: HTMLElement | null = element;
      while (current && current !== document.body) {
        const style = window.getComputedStyle(current);
        if (/(auto|scroll|hidden|clip)/.test(style.overflowX) && current.scrollWidth > current.clientWidth + 2) {
          return true;
        }
        current = current.parentElement;
      }
      return false;
    };
    const mainRect = document.querySelector('main')?.getBoundingClientRect();
    const bodyText = document.body.innerText || '';
    const overflowingElements = Array.from(document.body.querySelectorAll<HTMLElement>('body *'))
      .filter((element) => visible(element))
      .filter((element) => {
        const rect = element.getBoundingClientRect();
        return (rect.left < -2 || rect.right > viewportWidth + 2) && !hasHorizontalScrollBoundary(element);
      });
    const unexpectedFixedWidth = Array.from(document.body.querySelectorAll<HTMLElement>('body *'))
      .filter((element) => visible(element))
      .filter((element) => {
        const style = window.getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return style.width.endsWith('px') && rect.width > viewportWidth + 2;
      }).length;
    const chartClippingCount = Array.from(document.body.querySelectorAll<HTMLElement>('canvas, [data-chart-engine], [data-chart-kind], [data-testid*="chart"], [data-testid*="visual"], svg[data-chart], svg[aria-label*="chart" i]'))
      .filter((element) => visible(element))
      .filter((element) => {
        const rect = element.getBoundingClientRect();
        return rect.right > viewportWidth + 2 || rect.left < -2 || rect.height < 80 || rect.width < 80;
      }).length;
    const tableClippingCount = Array.from(document.body.querySelectorAll<HTMLElement>('table, [role="table"], [data-testid*="table"], [data-testid*="ledger"], [data-testid*="list"]'))
      .filter((element) => visible(element))
      .filter((element) => {
        const rect = element.getBoundingClientRect();
        return (rect.right > viewportWidth + 2 || rect.left < -2) && !hasHorizontalScrollBoundary(element);
      }).length;
    const firstViewportHierarchy = Array.from(document.body.querySelectorAll('h1,h2,h3,[role="heading"], main p, main button, main a'))
      .filter((element) => visible(element))
      .map(text)
      .filter((value, index, values) => value.length >= 2 && value.length <= 120 && values.indexOf(value) === index)
      .slice(0, 12);
    const unlabeledFormControlCount = Array.from(document.body.querySelectorAll<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>('input, select, textarea'))
      .filter((element) => visible(element))
      .filter((element) => {
        const id = element.getAttribute('id');
        const hasLabel = Boolean(id && document.querySelector(`label[for="${CSS.escape(id)}"]`));
        const hasName = Boolean(element.getAttribute('aria-label') || element.getAttribute('aria-labelledby') || element.getAttribute('title') || element.getAttribute('placeholder'));
        return !hasLabel && !hasName && element.type !== 'hidden';
      }).length;
    const unnamedTableCount = Array.from(document.body.querySelectorAll('table, [role="table"]'))
      .filter((element) => visible(element))
      .filter((element) => !element.getAttribute('aria-label') && !element.getAttribute('aria-labelledby') && !element.querySelector('caption')).length;
    const stickyCollisionCount = Array.from(document.body.querySelectorAll<HTMLElement>('[style*="fixed"], [style*="sticky"], .fixed, .sticky'))
      .filter((element) => visible(element))
      .filter((element) => {
        const rect = element.getBoundingClientRect();
        return Boolean(mainRect && rect.bottom > mainRect.top + 8 && rect.top < mainRect.top + 8 && rect.width > viewportWidth * 0.6);
      }).length;
    const navigationReachable = Boolean(document.querySelector('nav, [role="navigation"], [data-testid*="nav"], [data-testid*="shell"]'));
    const actionReachable = Array.from(document.body.querySelectorAll('button, a[href], input, select, textarea, [role="button"], [role="menuitem"]')).some((element) => visible(element) && isFocusable(element));
    const landmarks = Array.from(document.body.querySelectorAll('main, nav, header, footer, aside, [role="main"], [role="navigation"], [role="banner"], [role="contentinfo"], [role="complementary"]'));
    const ariaCurrentCount = document.body.querySelectorAll('[aria-current="page"], [aria-current="true"]').length;
    const stateMeaningColorOnlyRisk = /green|red|emerald|rose|amber|lime|text-(red|green|emerald|rose|amber)/i.test(document.body.innerHTML)
      && !/(状态|state|可用|不足|partial|available|blocked|missing|延迟|观察|ready|unavailable)/i.test(bodyText);
    return {
      bodyOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
      unexpectedFixedWidth,
      internalOverflowCount: overflowingElements.length,
      stickyCollisionCount,
      navigationReachable,
      firstViewportHierarchy,
      actionReachable,
      chartClippingCount,
      tableClippingCount,
      mobileStackingRisk: viewportWidth <= 390 && firstViewportHierarchy.length < 2,
      landmarkCount: landmarks.length,
      h1Count: document.querySelectorAll('h1').length,
      ariaCurrentCount,
      unlabeledFormControlCount,
      unnamedTableCount,
      stateMeaningColorOnlyRisk,
    };
  });

  const focusVisible = await verifyFocusVisible(page);
  const evidenceSectionsVisible: string[] = [];
  for (const testId of route.evidenceTestIds || []) {
    if (await page.getByTestId(testId).first().isVisible().catch(() => false)) {
      evidenceSectionsVisible.push(testId);
    }
  }

  const findings: Finding[] = [];
  const owner = `${route.label} frontend owner`;
  if (metrics.bodyOverflow) {
    findings.push(defect('P1', 'body-overflow', route, viewport, 'Document creates horizontal body overflow.', owner, ['Inspect documentElement scrollWidth versus clientWidth.']));
  }
  if (metrics.unexpectedFixedWidth > 0) {
    findings.push(defect('P2', 'responsive', route, viewport, `${metrics.unexpectedFixedWidth} visible elements use fixed width wider than the viewport.`, owner, ['Inspect visible fixed-width elements.']));
  }
  if (metrics.internalOverflowCount > 0) {
    findings.push(defect('P2', 'internal-overflow', route, viewport, `${metrics.internalOverflowCount} visible elements overflow their container or viewport.`, owner, ['Inspect table/list/chart containers for internal overflow.']));
  }
  if (!metrics.navigationReachable) {
    findings.push(defect('P1', 'navigation', route, viewport, 'No reachable navigation landmark or shell navigation detected.', 'Shell/navigation owner', ['Inspect landmarks and nav controls.']));
  }
  if (!metrics.actionReachable) {
    findings.push(defect('P1', 'responsive', route, viewport, 'No focusable primary action or route control is reachable in viewport.', owner, ['Inspect first viewport controls.']));
  }
  if (metrics.chartClippingCount > 0) {
    findings.push(defect('P2', 'responsive', route, viewport, `${metrics.chartClippingCount} chart/visual elements appear clipped.`, owner, ['Inspect chart/visual bounding boxes.']));
  }
  if (metrics.tableClippingCount > 0) {
    findings.push(defect('P2', 'internal-overflow', route, viewport, `${metrics.tableClippingCount} table/list/ledger elements appear clipped.`, owner, ['Inspect table/list/ledger bounding boxes.']));
  }
  if (metrics.landmarkCount === 0) {
    findings.push(defect('P1', 'accessibility', route, viewport, 'No semantic landmarks detected.', owner, ['Inspect main/nav/header landmark structure.']));
  }
  if (metrics.h1Count !== 1) {
    findings.push(defect('P2', 'accessibility', route, viewport, `Expected one h1, found ${metrics.h1Count}.`, owner, ['Inspect heading hierarchy.']));
  }
  if (metrics.unlabeledFormControlCount > 0) {
    findings.push(defect('P1', 'accessibility', route, viewport, `${metrics.unlabeledFormControlCount} visible form controls lack accessible names.`, owner, ['Inspect visible inputs/selects/textareas.']));
  }
  if (metrics.unnamedTableCount > 0) {
    findings.push(defect('P2', 'accessibility', route, viewport, `${metrics.unnamedTableCount} visible tables lack caption or accessible name.`, owner, ['Inspect table captions or aria labels.']));
  }
  if (!focusVisible) {
    findings.push(defect('P1', 'accessibility', route, viewport, 'Keyboard focus is not visibly indicated on first reachable control.', owner, ['Press Tab and inspect active element focus outline.']));
  }
  if (metrics.stateMeaningColorOnlyRisk) {
    findings.push(defect('P2', 'accessibility', route, viewport, 'State styling may rely on color without nearby textual state meaning.', owner, ['Inspect visible status chips and state labels.']));
  }

  return {
    route: route.key,
    label: route.label,
    path: route.path,
    viewport,
    finalUrl: page.url(),
    ...metrics,
    focusVisible,
    evidenceSectionsVisible,
    findings,
  };
}

async function verifyFocusVisible(page: Page) {
  await page.keyboard.press('Tab');
  return page.evaluate(() => {
    const active = document.activeElement as HTMLElement | null;
    if (!active || active === document.body) return false;
    const style = window.getComputedStyle(active);
    const rect = active.getBoundingClientRect();
    return rect.width > 0
      && rect.height > 0
      && (style.outlineStyle !== 'none'
        || Number.parseFloat(style.outlineWidth || '0') > 0
        || style.boxShadow !== 'none'
        || active.matches(':focus-visible'));
  });
}

async function safeClick(locator: Locator) {
  if (await locator.count()) {
    await locator.first().click();
    return true;
  }
  return false;
}

async function recordJourney(
  page: Page,
  name: string,
  route: QualificationRoute,
  viewport: string,
  body: () => Promise<string[]>,
) {
  const findings: Finding[] = [];
  let status: JourneyEvidence['status'] = 'pass';
  let notes: string[] = [];
  try {
    notes = await body();
  } catch (error) {
    status = 'fail';
    const message = error instanceof Error ? error.message : String(error);
    findings.push(defect('P1', 'keyboard', route, viewport, message, `${route.label} frontend owner`, [`Run keyboard journey "${name}".`]));
    notes = [message];
  }
  evidence.journeys.push({ name, status, route: route.label, viewport, notes, findings });
  if (strictQualification) {
    expect(status, `${name} keyboard journey`).toBe('pass');
  }
}

function writeQualificationEvidence() {
  const outputPath = process.env.CONSUMER_FRONTEND_QUALIFICATION_OUTPUT
    ? path.resolve(process.env.CONSUMER_FRONTEND_QUALIFICATION_OUTPUT)
    : path.resolve(process.cwd(), 'test-results', 'consumer-frontend-browser-qualification.json');
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(
    outputPath,
    JSON.stringify(
      {
        schemaVersion: 'wolfystock_consumer_frontend_browser_qualification_v1',
        generatedAt: new Date().toISOString(),
        viewports,
        routes,
        ...evidence,
      },
      null,
      2,
    ),
  );
}

function expectNoProductionDefectsWhenStrict(routeEvidence: RouteViewportEvidence) {
  if (!strictQualification) return;
  expect(routeEvidence.findings, `${routeEvidence.label} ${routeEvidence.viewport} production qualification defects`).toEqual([]);
}

test.afterEach(() => {
  writeQualificationEvidence();
});

test.describe('consumer frontend browser qualification matrix', () => {
  for (const route of routes.filter((entry) => entry.type === 'standard')) {
    for (const viewport of viewports) {
      test(`${route.label} qualifies responsive and accessibility boundary at ${viewport.width}x${viewport.height}`, async ({ page }) => {
        await page.setViewportSize(viewport);
        await installQualificationOverrides(page);
        await waitForRoute(page, route);

        const routeEvidence = await collectRouteEvidence(page, route, `${viewport.width}x${viewport.height}`);
        evidence.responsive.push(routeEvidence);

        await expect(page.getByTestId(route.readyTestId), `${route.label} route loaded`).toBeVisible();
        expectNoProductionDefectsWhenStrict(routeEvidence);
      });
    }
  }

  for (const viewport of viewports) {
    test(`Portfolio qualifies responsive and accessibility boundary at ${viewport.width}x${viewport.height}`, async ({ page }) => {
      const route = routes.find((entry) => entry.key === 'portfolio');
      if (!route) throw new Error('Portfolio route missing from qualification matrix.');
      await page.setViewportSize(viewport);
      await waitForRoute(page, route);

      const routeEvidence = await collectRouteEvidence(page, route, `${viewport.width}x${viewport.height}`);
      evidence.responsive.push(routeEvidence);

      await expect(page.getByTestId(route.readyTestId), `${route.label} route loaded`).toBeVisible();
      expectNoProductionDefectsWhenStrict(routeEvidence);
    });
  }
});

test.describe('consumer frontend keyboard journey qualification', () => {
  test('representative navigation search menus and product row journeys are keyboard reachable', async ({ page }) => {
    const viewport = '390x844';
    await page.setViewportSize({ width: 390, height: 844 });
    await installQualificationOverrides(page);

    const homeRoute = routes.find((entry) => entry.key === 'home')!;
    await waitForRoute(page, homeRoute);
    await recordJourney(page, 'navigation', homeRoute, viewport, async () => {
      await page.keyboard.press('Tab');
      const activeTag = await page.evaluate(() => document.activeElement?.tagName || '');
      expect(activeTag).not.toBe('');
      return [`First keyboard target: ${activeTag}`];
    });
    await recordJourney(page, 'search', homeRoute, viewport, async () => {
      const search = page.getByRole('textbox', { name: /搜索|Search|symbol|代码/i }).first();
      await expect(search).toBeVisible({ timeout: 10_000 });
      await search.focus();
      await expect(search).toBeFocused();
      await search.fill('AAPL');
      await page.keyboard.press('Escape');
      return ['Search textbox accepted keyboard focus and Escape without trapping focus.'];
    });

    const scannerRoute = routes.find((entry) => entry.key === 'scanner')!;
    await waitForRoute(page, scannerRoute);
    await recordJourney(page, 'More menu', scannerRoute, viewport, async () => {
      const opened = await safeClick(page.getByRole('button', { name: /更多扫描操作|more scanner actions|更多|More/i }));
      expect(opened).toBe(true);
      await page.keyboard.press('Escape');
      return ['More menu opened and Escape was accepted.'];
    });
    await recordJourney(page, 'Scanner run/result', scannerRoute, viewport, async () => {
      const button = page.getByTestId('scanner-run-button').or(page.getByRole('button', { name: /运行|扫描|Run|Scanner/i })).first();
      await expect(button).toBeVisible({ timeout: 10_000 });
      await button.focus();
      await expect(button).toBeFocused();
      return ['Scanner run control is keyboard focusable.'];
    });

    const radarRoute = routes.find((entry) => entry.key === 'radar')!;
    await waitForRoute(page, radarRoute);
    await recordJourney(page, 'Radar candidate selection', radarRoute, viewport, async () => {
      const candidate = page.getByRole('button', { name: /查看 NVDA 研究细节|Inspect NVDA/i }).first();
      await expect(candidate).toBeVisible({ timeout: 10_000 });
      await candidate.focus();
      await expect(candidate).toBeFocused();
      await page.keyboard.press('Enter');
      return ['Radar candidate accepted keyboard focus and Enter.'];
    });

    const watchlistRoute = routes.find((entry) => entry.key === 'watchlist')!;
    await waitForRoute(page, watchlistRoute);
    await recordJourney(page, 'Watchlist row', watchlistRoute, viewport, async () => {
      const rowAction = page.getByTestId('watchlist-row-NVDA').getByRole('button', { name: /查看详情 NVDA|View details NVDA/i });
      await expect(rowAction).toBeVisible({ timeout: 10_000 });
      await rowAction.focus();
      await expect(rowAction).toBeFocused();
      return ['Watchlist first row/action is keyboard focusable.'];
    });

    const backtestRoute = routes.find((entry) => entry.key === 'backtest')!;
    await waitForRoute(page, backtestRoute);
    await recordJourney(page, 'Backtest setup', backtestRoute, viewport, async () => {
      const input = page.getByLabel(/标的代码|Ticker|symbol/i).first();
      await expect(input).toBeVisible({ timeout: 10_000 });
      await input.focus();
      await expect(input).toBeFocused();
      return ['Backtest ticker input is keyboard focusable.'];
    });

    const scenarioRoute = routes.find((entry) => entry.key === 'scenario-lab')!;
    await waitForRoute(page, scenarioRoute);
    await recordJourney(page, 'Scenario evaluate', scenarioRoute, viewport, async () => {
      const evaluate = page.getByRole('button', { name: /评估情景|Evaluate/i }).first();
      await expect(evaluate).toBeVisible({ timeout: 10_000 });
      await evaluate.focus();
      await expect(evaluate).toBeFocused();
      await page.keyboard.press('Enter');
      await expect(page.getByTestId('scenario-lab-first-read-summary')).toBeVisible({ timeout: 15_000 });
      return ['Scenario evaluate works from keyboard.'];
    });
  });

  test('portfolio row and import entry are keyboard reachable', async ({ page }) => {
    const route = routes.find((entry) => entry.key === 'portfolio')!;
    const viewport = '390x844';
    await page.setViewportSize({ width: 390, height: 844 });
    await waitForRoute(page, route, { portfolioOperatorMode: true });
    await recordJourney(page, 'Portfolio row/import entry', route, viewport, async () => {
      const importLauncher = page.getByTestId('portfolio-next-action-panel').getByRole('button', { name: /同步数据|Sync data/i });
      await expect(importLauncher).toBeVisible({ timeout: 10_000 });
      await importLauncher.focus();
      await expect(importLauncher).toBeFocused();
      await page.keyboard.press('Enter');
      const importEntry = page.getByLabel(/选择导入文件|Choose import file/i);
      await expect(importEntry).toBeVisible({ timeout: 10_000 });
      await importEntry.focus();
      await expect(importEntry).toBeFocused();
      const importEntryVisible = await page.getByText(/导入|Import|IBKR|broker/i).first().isVisible().catch(() => false);
      expect(importEntryVisible).toBe(true);
      return ['Portfolio import launcher is keyboard focusable in operator fixture.', 'Import file entry is keyboard focusable.', 'Import entry copy is visible.'];
    });
  });
});
