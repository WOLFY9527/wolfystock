import { expect as pwExpect, type Page } from '@playwright/test';
import { expect as appExpect, test as appTest } from './fixtures/appSmoke';
import {
  expectNoHorizontalOverflow,
  fulfillJson,
  installSignedInSessionRoutes,
  openSignedInRoute,
} from './fixtures/authenticatedRouteSmoke';

type ReadinessState = 'available' | 'partial' | 'stale' | 'unavailable' | 'unknown';
type ProvenanceState = 'observed' | 'calculated' | 'delayed' | 'simulated' | 'fixture' | 'unavailable' | 'unknown';
type SourceClass = 'market_observation' | 'scanner_run' | 'rule_backtest_result' | 'simulated' | 'fixture' | 'unknown';

type Dimension = {
  state: ReadinessState;
  freshness_state: ReadinessState;
  source_class: SourceClass;
  provenance_state: ProvenanceState;
  as_of: string | null;
  reason?: string;
};

type Readiness = {
  contract_version: 'product_read_model_v1';
  state: ReadinessState;
  freshness_state: ReadinessState;
  identity_state: 'resolved';
  last_reviewed_at: string | null;
  score_freshness_implied: false;
  source_authority_implied: false;
  market_data: Dimension;
  scanner_evidence: Dimension;
  backtest_result: Dimension;
  blocked_reasons: string[];
};

const asOf = '2026-05-01T12:30:00Z';

function dimension(
  state: ReadinessState,
  provenance: ProvenanceState,
  source: SourceClass,
  reason?: string,
): Dimension {
  return {
    state,
    freshness_state: state,
    source_class: source,
    provenance_state: provenance,
    as_of: state === 'unknown' || state === 'unavailable' ? null : asOf,
    ...(reason ? { reason } : {}),
  };
}

function readiness(
  state: ReadinessState,
  market: Dimension,
  scanner: Dimension,
  backtest: Dimension,
  blockedReasons: string[] = [],
): Readiness {
  return {
    contract_version: 'product_read_model_v1',
    state,
    freshness_state: state,
    identity_state: 'resolved',
    last_reviewed_at: state === 'unknown' ? null : asOf,
    score_freshness_implied: false,
    source_authority_implied: false,
    market_data: market,
    scanner_evidence: scanner,
    backtest_result: backtest,
    blocked_reasons: blockedReasons,
  };
}

function item(
  id: number,
  symbol: string,
  researchReadiness: Readiness,
  options: {
    quoteState?: 'available' | 'missing' | 'stale' | 'unknown';
    scannerStatus?: string;
    backtest?: Record<string, unknown>;
    savedItemSource?: string;
    missingData?: string[];
    nextDataAction?: string;
  } = {},
) {
  const quoteState = options.quoteState ?? 'available';
  const hasScanner = Boolean(options.scannerStatus);
  return {
    id,
    symbol,
    market: 'us',
    identity: {
      canonical_symbol: symbol,
      display_symbol: symbol,
      market: 'us',
      display_name: `${symbol} Research Fixture`,
      identity_state: 'resolved',
    },
    name: `${symbol} Research Fixture`,
    source: options.savedItemSource ?? 'manual',
    scanner_run_id: hasScanner ? id + 100 : null,
    scanner_rank: options.scannerStatus === 'selected' ? id : null,
    scanner_score: options.scannerStatus === 'selected' ? 91 : null,
    last_scored_at: hasScanner ? asOf : null,
    score_source: hasScanner ? 'scanner_run' : null,
    score_status: options.scannerStatus === 'data_failed' ? 'unavailable' : 'fresh',
    research_readiness: researchReadiness,
    intelligence: {
      scanner: hasScanner
        ? {
            last_score: options.scannerStatus === 'selected' ? 91 : null,
            last_rank: options.scannerStatus === 'selected' ? id : null,
            status: options.scannerStatus,
            reason: 'Bounded scanner fixture for readiness rendering.',
            last_scanned_at: options.scannerStatus === 'selected' ? asOf : null,
          }
        : null,
      strategy_simulation: { status: researchReadiness.state === 'available' ? 'ready' : 'unknown' },
      backtest: options.backtest ?? {},
    },
    row_research_packet: {
      symbol,
      market: 'us',
      identity: {
        canonical_symbol: symbol,
        display_symbol: symbol,
        display_name: `${symbol} Research Fixture`,
        identity_state: 'resolved',
      },
      saved_item_source: options.savedItemSource ?? 'manual',
      quote: {
        state: quoteState,
        price: quoteState === 'available' ? 123.45 : null,
        change_percent: quoteState === 'available' ? 1.2 : null,
        as_of: quoteState === 'available' ? asOf : null,
      },
      provenance: {
        source_class: researchReadiness.market_data.source_class,
        provenance_state: researchReadiness.market_data.provenance_state,
        as_of: researchReadiness.market_data.as_of,
        freshness_state: researchReadiness.market_data.freshness_state,
      },
      scanner_lineage: {
        run_id: hasScanner ? id + 100 : null,
        rank: options.scannerStatus === 'selected' ? id : null,
        score: options.scannerStatus === 'selected' ? 91 : null,
        status: options.scannerStatus ?? null,
        last_scored_at: options.scannerStatus === 'selected' ? asOf : null,
      },
      research_status: researchReadiness.state === 'available'
        ? 'ready'
        : researchReadiness.state === 'partial'
          ? 'partial'
          : 'blocked',
      research_readiness: researchReadiness,
      missing_data: options.missingData ?? [],
      next_data_action: options.nextDataAction ?? 'Continue observation and review the evidence state.',
      observation_only: true,
      no_advice_disclosure: 'Observation-only research packet; no personalized action instruction.',
    },
    created_at: asOf,
    updated_at: asOf,
  };
}

const availableReadiness = readiness(
  'available',
  dimension('available', 'observed', 'market_observation'),
  dimension('available', 'calculated', 'scanner_run'),
  dimension('available', 'calculated', 'rule_backtest_result'),
);

const rows = [
  item(1, 'OBS', availableReadiness, {
    scannerStatus: 'selected',
    backtest: { last_result_id: 701, result_contract_available: true, trade_count: 12, total_return_pct: 8.4, tested_at: asOf },
  }),
  item(2, 'UNAV', readiness(
    'unavailable',
    dimension('unavailable', 'unavailable', 'unknown', 'Required market data is unavailable.'),
    dimension('unknown', 'unknown', 'unknown'),
    dimension('unknown', 'unknown', 'unknown'),
    ['market_data_unavailable'],
  ), { quoteState: 'missing', missingData: ['quote', 'price_history'], nextDataAction: 'Review the missing market evidence before continuing.' }),
  item(3, 'STALE', readiness(
    'stale',
    dimension('stale', 'delayed', 'market_observation', 'Market observation is stale.'),
    dimension('stale', 'calculated', 'scanner_run'),
    dimension('unknown', 'unknown', 'unknown'),
    ['market_data_stale', 'backtest_result_unknown'],
  ), { quoteState: 'stale', scannerStatus: 'selected', missingData: ['stale_market_observation'], nextDataAction: 'Confirm the observation time before relying on it.' }),
  item(4, 'PART', readiness(
    'partial',
    dimension('available', 'observed', 'market_observation'),
    dimension('partial', 'calculated', 'scanner_run'),
    dimension('unknown', 'unknown', 'unknown'),
    ['backtest_result_unknown'],
  ), { scannerStatus: 'partial', missingData: ['backtest_result'], nextDataAction: 'Review the remaining backtest evidence.' }),
  item(5, 'BLOCK', readiness(
    'unavailable',
    dimension('available', 'observed', 'market_observation'),
    dimension('available', 'calculated', 'scanner_run'),
    dimension('unavailable', 'unavailable', 'rule_backtest_result', 'No valid calculation evidence.'),
    ['backtest_result_unavailable'],
  ), { scannerStatus: 'selected', missingData: ['backtest_result'], nextDataAction: 'Review the blocked backtest evidence.' }),
  item(6, 'ZERO', availableReadiness, {
    scannerStatus: 'selected',
    backtest: { last_result_id: 702, result_contract_available: true, trade_count: 0, total_return_pct: 0, tested_at: asOf },
  }),
  item(12, 'CONTRA', readiness(
    'unavailable',
    dimension('available', 'observed', 'market_observation'),
    dimension('available', 'calculated', 'scanner_run'),
    dimension('unavailable', 'unavailable', 'rule_backtest_result', 'No valid calculation evidence.'),
    ['backtest_result_unavailable'],
  ), {
    scannerStatus: 'selected',
    backtest: {
      last_result_id: 703,
      status: 'completed',
      result_contract_available: false,
      trade_count: 9,
      total_return_pct: 11.2,
      tested_at: asOf,
    },
  }),
  item(7, 'SCNEMPTY', readiness(
    'partial',
    dimension('available', 'observed', 'market_observation'),
    dimension('unavailable', 'unavailable', 'scanner_run', 'Scanner returned no usable evidence.'),
    dimension('unknown', 'unknown', 'unknown'),
    ['scanner_evidence_unavailable'],
  ), { scannerStatus: 'empty', missingData: ['scanner_evidence'], nextDataAction: 'Review scanner coverage before continuing.' }),
  item(8, 'SCNFAIL', readiness(
    'partial',
    dimension('available', 'observed', 'market_observation'),
    dimension('unavailable', 'unavailable', 'scanner_run', 'Scanner data failed.'),
    dimension('unknown', 'unknown', 'unknown'),
    ['scanner_evidence_unavailable'],
  ), { scannerStatus: 'data_failed', missingData: ['scanner_evidence'], nextDataAction: 'Review the unavailable scanner evidence.' }),
  item(9, 'SIM', readiness(
    'available',
    dimension('available', 'simulated', 'simulated'),
    dimension('available', 'simulated', 'simulated'),
    dimension('available', 'calculated', 'rule_backtest_result'),
  ), { savedItemSource: 'simulated', scannerStatus: 'selected' }),
  item(10, 'FIX', readiness(
    'available',
    dimension('available', 'fixture', 'fixture'),
    dimension('available', 'fixture', 'fixture'),
    dimension('available', 'fixture', 'fixture'),
  ), { savedItemSource: 'fixture', scannerStatus: 'selected' }),
  item(11, 'UNK', readiness(
    'unknown',
    dimension('unknown', 'unknown', 'unknown'),
    dimension('unknown', 'unknown', 'unknown'),
    dimension('unknown', 'unknown', 'unknown'),
    ['market_data_unknown', 'scanner_evidence_unknown', 'backtest_result_unknown'],
  ), { quoteState: 'unknown', missingData: ['quote', 'price_history', 'scanner_evidence'], nextDataAction: 'Review stock structure before relying on this saved row.' }),
];

async function installWatchlistRoutes(page: Page, fixtureItems: unknown[]) {
  await installSignedInSessionRoutes(page);
  await page.route('**/api/v1/watchlist/items', async (route) => fulfillJson(route, { items: fixtureItems }));
  await page.route('**/api/v1/watchlist/research-overlay', async (route) => fulfillJson(route, {
    schema_version: 'watchlist_research_overlay_v1',
    overlay_state: fixtureItems.length ? 'degraded' : 'available',
    research_summary: fixtureItems.length ? 'Some saved symbols need evidence review.' : 'No saved symbols require follow-up.',
    research_priority_queue: fixtureItems.length ? [{
      symbol: 'UNK',
      priority_tier: 'attention',
      priority_reason_safe_label: 'Research context needs attention.',
      evidence_age: { state: 'no_evidence', last_reviewed_at: null },
      missing_evidence: ['Price-history evidence', 'Scanner score evidence'],
      suggested_research_path: [{
        label: 'Stock Structure',
        route: '/stocks/UNK/structure-decision',
        section: 'watchlistResearchOverlay',
        reason: 'Review structure and context completeness first.',
      }],
      observation_only: true,
    }] : [],
    observation_only: true,
    decision_grade: false,
  }));
  await page.route('**/api/v1/watchlist/refresh-status', async (route) => fulfillJson(route, { enabled: false, running: false }));
  await page.route('**/api/v1/user-alerts/rules', async (route) => fulfillJson(route, { items: [] }));
  await page.route('**/api/v1/user-alerts/events', async (route) => fulfillJson(route, { items: [], total: 0, limit: 20, offset: 0 }));
}

appTest.describe('T727 Watchlist research readiness and provenance truth', () => {
  appTest('keeps an empty pool useful without inventing evidence', async ({ page, unhandledApiRoutes }) => {
    await installWatchlistRoutes(page, []);
    await openSignedInRoute(page, '/zh/watchlist');
    const emptyState = page.getByTestId('watchlist-compact-empty-state');
    await appExpect(emptyState).toBeVisible();
    await appExpect(emptyState).toContainText('还没有观察标的');
    await appExpect(emptyState).toContainText('它不会自动保存任何标的');
    await expectNoHorizontalOverflow(page);
    pwExpect(unhandledApiRoutes).toEqual([]);
  });

  appTest('renders the filled-pool readiness matrix without provenance collapse', async ({ page, unhandledApiRoutes }) => {
    await installWatchlistRoutes(page, rows);
    await page.route('**/api/v1/**', async (route) => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      if (request.method() === 'POST' && path === '/api/v1/analysis/analyze') {
        return fulfillJson(route, {
          error: 'llm_model_unavailable',
          code: 'llm_model_unavailable',
          message: 'AI analysis capability is unavailable in this environment.',
          status: 503,
          retryable: false,
          detail: {
            capabilityState: 'not_configured',
            reasonCode: 'analysis_model_not_configured',
          },
        }, 503);
      }
      if (request.method() === 'GET' && path === '/api/v1/stocks/OBS/validate') {
        return fulfillJson(route, {
          stockCode: 'OBS',
          normalizedSymbol: 'OBS',
          market: 'us',
          status: 'valid',
          valid: true,
          exists: true,
        });
      }
      if (path.includes('/OBS')) {
        return fulfillJson(route, {});
      }
      return route.fallback();
    });
    await openSignedInRoute(page, '/zh/watchlist');
    await appExpect(page.getByTestId('watchlist-page')).toBeVisible();

    await appExpect(page.getByTestId('watchlist-row-OBS')).toContainText('研究包可用');
    await appExpect(page.getByTestId('watchlist-row-OBS')).toContainText('观测数据');
    await appExpect(page.getByTestId('watchlist-row-UNAV')).toContainText('研究包待生成');
    await appExpect(page.getByTestId('watchlist-row-STALE')).toContainText('研究包部分可用');
    await appExpect(page.getByTestId('watchlist-row-PART')).toContainText('研究包部分可用');
    await appExpect(page.getByTestId('watchlist-row-BLOCK')).toContainText('研究包待生成');
    await appExpect(page.getByTestId('watchlist-row-ZERO')).toContainText('研究包可用');
    await appExpect(page.getByTestId('watchlist-row-CONTRA')).toContainText('研究包待生成');
    await appExpect(page.getByTestId('watchlist-row-SCNEMPTY')).toContainText('研究包部分可用');
    await appExpect(page.getByTestId('watchlist-row-SCNFAIL')).toContainText('研究包部分可用');
    await appExpect(page.getByTestId('watchlist-row-SIM')).toContainText('模拟数据');
    await appExpect(page.getByTestId('watchlist-row-FIX')).toContainText('测试数据');
    await appExpect(page.getByTestId('watchlist-row-UNK')).toContainText('研究包待生成');

    await appExpect(page.getByTestId('watchlist-row-UNAV')).toContainText('补报价与历史');
    await appExpect(page.getByTestId('watchlist-row-STALE')).toContainText('确认报价');
    await appExpect(page.getByTestId('watchlist-row-UNK')).toContainText('查看个股结构');
    await appExpect(page.getByTestId('watchlist-research-queue')).toContainText('证据待补');

    await page.getByRole('button', { name: '查看详情 OBS' }).click();
    await appExpect(page.getByTestId('watchlist-detail-rail')).toBeVisible();
    await appExpect(page.getByTestId('watchlist-detail-rail')).toContainText('下一步');
    await appExpect(page.getByTestId('watchlist-page')).not.toContainText(/买入|卖出|下单|provider_trace|raw_provider_payload|source_authority_allowed/i);

    await page.getByRole('button', { name: '查看详情 CONTRA' }).click();
    await appExpect(page.getByTestId('watchlist-detail-rail')).toContainText('未回测');
    await appExpect(page.getByRole('button', { name: '结果 703' })).not.toBeVisible();
    const contradictoryRow = page.getByTestId('watchlist-row-CONTRA');
    await contradictoryRow.getByRole('button', { name: '更多操作 CONTRA' }).click();
    await appExpect(contradictoryRow.getByRole('menuitem', { name: '结果 703' })).toHaveCount(0);

    const observableRow = page.getByTestId('watchlist-row-OBS');
    await observableRow.getByRole('button', { name: '更多操作 OBS' }).click();
    await observableRow.getByRole('menuitem', { name: '分析' }).click();
    const capabilityNotice = page.getByRole('status').filter({ hasText: '当前环境未提供 AI 分析能力' });
    await appExpect(capabilityNotice).toContainText('仍可继续查看该标的已保存的研究证据');
    await appExpect(capabilityNotice.getByRole('button', { name: '查看研究证据' })).toBeVisible();
    await appExpect(capabilityNotice.getByRole('button', { name: /重试/ })).toHaveCount(0);
    await appExpect(page).toHaveURL(/\/zh\/watchlist$/);

    await capabilityNotice.getByRole('button', { name: '查看研究证据' }).click();
    await appExpect(page).toHaveURL(/\/zh\/stocks\/OBS\/structure-decision\?symbol=OBS&market=US&source=watchlist$/);
    await expectNoHorizontalOverflow(page);
    pwExpect(unhandledApiRoutes).toEqual([]);
  });
});
