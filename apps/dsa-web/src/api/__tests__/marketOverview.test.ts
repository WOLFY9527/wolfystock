import { beforeEach, describe, expect, it, vi } from 'vitest';

const { get } = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock('../index', () => ({
  default: {
    get,
  },
}));

describe('marketOverviewApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('preserves panel freshness metadata and nested item synthetic flags from snake_case responses', async () => {
    const { marketOverviewApi } = await import('../marketOverview');

    get.mockResolvedValueOnce({
      data: {
        panel_name: 'IndexTrendsCard',
        last_refresh_at: '2026-06-07T09:00:00Z',
        status: 'success',
        source: 'recent_cache',
        source_label: 'Recent cache',
        updated_at: '2026-06-07T09:01:00Z',
        as_of: '2026-06-07T09:00:00Z',
        freshness: 'fallback',
        is_fallback: true,
        is_stale: true,
        is_partial: true,
        is_unavailable: false,
        warning: '最近可用快照',
        items: [
          {
            symbol: 'SPX',
            label: 'S&P 500',
            value: 5234.18,
            change_pct: -0.42,
            source: 'synthetic_placeholder',
            source_label: 'Synthetic placeholder',
            updated_at: '2026-06-07T09:01:00Z',
            as_of: '2026-06-07T09:00:00Z',
            freshness: 'synthetic',
            is_fallback: false,
            is_stale: false,
            is_partial: true,
            is_synthetic: true,
            is_unavailable: false,
          },
          {
            symbol: 'NDX',
            label: 'Nasdaq 100',
            value: null,
            source: 'provider_timeout_placeholder',
            source_label: 'Timeout placeholder',
            updated_at: '2026-06-07T09:01:00Z',
            as_of: '2026-06-07T09:00:00Z',
            freshness: 'unavailable',
            is_fallback: false,
            is_stale: false,
            is_partial: false,
            is_synthetic: false,
            is_unavailable: true,
          },
        ],
      },
    });

    const panel = await marketOverviewApi.getIndices();
    const firstItem = panel.items[0] as Record<string, unknown>;
    const secondItem = panel.items[1] as Record<string, unknown>;

    expect(get).toHaveBeenCalledWith('/api/v1/market-overview/indices');
    expect(panel.panelName).toBe('IndexTrendsCard');
    expect(panel.source).toBe('recent_cache');
    expect(panel.sourceLabel).toBe('Recent cache');
    expect(panel.updatedAt).toBe('2026-06-07T09:01:00Z');
    expect(panel.asOf).toBe('2026-06-07T09:00:00Z');
    expect(panel.freshness).toBe('fallback');
    expect(panel.isFallback).toBe(true);
    expect(panel.isStale).toBe(true);
    expect(panel.isPartial).toBe(true);
    expect(panel.isUnavailable).toBe(false);
    expect(panel.warning).toBe('最近可用快照');

    expect(firstItem.source).toBe('synthetic_placeholder');
    expect(firstItem.sourceLabel).toBe('Synthetic placeholder');
    expect(firstItem.updatedAt).toBe('2026-06-07T09:01:00Z');
    expect(firstItem.asOf).toBe('2026-06-07T09:00:00Z');
    expect(firstItem.freshness).toBe('synthetic');
    expect(firstItem.isFallback).toBe(false);
    expect(firstItem.isStale).toBe(false);
    expect(firstItem.isPartial).toBe(true);
    expect(firstItem.isSynthetic).toBe(true);
    expect(firstItem.isUnavailable).toBe(false);

    expect(secondItem.freshness).toBe('unavailable');
    expect(secondItem.isSynthetic).toBe(false);
    expect(secondItem.isUnavailable).toBe(true);
  });

  it('preserves partial overview sentiment panel status from snake_case responses', async () => {
    const { marketOverviewApi } = await import('../marketOverview');

    get.mockResolvedValueOnce({
      data: {
        panel_name: 'MarketSentimentCard',
        last_refresh_at: '2026-06-25T09:00:00Z',
        status: 'partial',
        source: 'alternative_me',
        source_label: 'Alternative.me',
        updated_at: '2026-06-25T09:01:00Z',
        as_of: '2026-06-25T09:00:00Z',
        freshness: 'live',
        is_partial: true,
        refresh_error: 'cnn unavailable',
        warning: '情绪指标部分可用，请结合来源与时效观察。',
        provider_health: {
          provider: 'alternative_me',
          status: 'partial',
          is_fallback: false,
          is_stale: false,
          is_refreshing: false,
          source_label: 'Alternative.me',
        },
        items: [
          {
            symbol: 'FGI',
            label: 'Fear & Greed',
            value: 35,
            unit: 'score',
            source: 'alternative_me',
            source_label: 'Alternative.me',
            freshness: 'live',
          },
        ],
      },
    });

    const panel = await marketOverviewApi.getSentiment();

    expect(panel.status).toBe('partial');
    expect(panel.isPartial).toBe(true);
    expect(panel.refreshError).toBe('cnn unavailable');
    expect(panel.providerHealth?.status).toBe('partial');
    expect(panel.items[0]?.value).toBe(35);
  });

  it('preserves backend providerFreshness proxy truth and consumer dataQuality', async () => {
    const { marketOverviewApi } = await import('../marketOverview');

    get.mockResolvedValueOnce({
      data: {
        panel_name: 'IndexTrendsCard',
        last_refresh_at: '2026-06-07T09:00:00Z',
        status: 'partial',
        source: 'yfinance_proxy',
        source_label: 'Yahoo Finance',
        source_type: 'unofficial_proxy',
        updated_at: '2026-06-07T09:01:00Z',
        as_of: '2026-06-07T09:00:00Z',
        freshness: 'proxy',
        is_proxy: true,
        source_confidence: 'proxy',
        provider_freshness: {
          state: 'proxy',
          label: '代理',
          available: true,
          source_confidence: 'proxy',
          is_proxy: true,
          is_stale: false,
          is_unavailable: false,
          as_of: '2026-06-07T09:00:00Z',
          source_label: 'Yahoo Finance',
          data_source: 'yfinance_proxy',
          degradation_reason: 'etf_proxy_for_index',
          proxy_for: 'SPX',
          proxy_symbol: 'SPY',
          proxy_label: 'S&P 500',
        },
        data_quality: {
          state: 'partial',
          label: '部分可用',
          available: false,
        },
        items: [
          {
            symbol: 'SPX',
            label: 'S&P 500 proxy (SPY ETF)',
            value: 520,
            source: 'yfinance_proxy',
            source_label: 'Yahoo Finance',
            source_type: 'unofficial_proxy',
            freshness: 'proxy',
            is_proxy: true,
            source_confidence: 'proxy',
            source_authority_allowed: false,
            score_contribution_allowed: false,
            proxy_for: 'SPX',
            proxy_symbol: 'SPY',
            proxy_label: 'S&P 500',
            provider_freshness: {
              state: 'proxy',
              is_proxy: true,
              proxy_for: 'SPX',
              proxy_symbol: 'SPY',
            },
            data_quality: {
              state: 'partial',
              label: '部分可用',
              available: false,
            },
          },
        ],
      },
    });

    const panel = await marketOverviewApi.getIndices();
    const item = panel.items[0];

    expect(panel.freshness).toBe('proxy');
    expect(panel.isProxy).toBe(true);
    expect(panel.sourceConfidence).toBe('proxy');
    expect(panel.providerFreshness).toMatchObject({
      state: 'proxy',
      isProxy: true,
      proxyFor: 'SPX',
      proxySymbol: 'SPY',
    });
    expect(panel.dataQuality).toEqual({
      state: 'partial',
      label: '部分可用',
      available: false,
    });
    expect(item).toMatchObject({
      freshness: 'proxy',
      isProxy: true,
      sourceConfidence: 'proxy',
      sourceAuthorityAllowed: false,
      scoreContributionAllowed: false,
      proxyFor: 'SPX',
      proxySymbol: 'SPY',
      providerFreshness: {
        state: 'proxy',
        isProxy: true,
      },
      dataQuality: {
        state: 'partial',
        label: '部分可用',
        available: false,
      },
    });
  });

  it('preserves backend breadth claim and metric coverage semantics through normalizePanel', async () => {
    const { marketOverviewApi } = await import('../marketOverview');

    get.mockResolvedValueOnce({
      data: {
        panel_name: 'ChinaBreadthCard',
        last_refresh_at: '2026-06-07T09:00:00Z',
        status: 'partial',
        source: 'computed_from_authorized_eod_grouped_daily',
        source_label: 'Authorized EOD breadth',
        updated_at: '2026-06-07T09:01:00Z',
        as_of: '2026-06-07T09:00:00Z',
        freshness: 'delayed',
        breadth_claim_type: 'computed_from_authorized_eod_grouped_daily',
        official_exchange_published_breadth: false,
        fulfilled_metrics: ['ADVANCERS', 'DECLINERS', 'UNCHANGED', 'ADVANCE_DECLINE_RATIO'],
        missing_metrics: ['NEW_HIGHS', 'NEW_LOWS', 'HIGH_LOW_RATIO'],
        metric_coverage_ratio: 4 / 7,
        broad_market_claim_allowed: true,
        reason_codes: ['partial_metric_coverage'],
        items: [
          {
            symbol: 'ADVANCERS',
            label: 'Advancers',
            value: 1800,
            freshness: 'delayed',
          },
        ],
      },
    });

    const panel = await marketOverviewApi.getIndices();

    expect(panel.breadthClaimType).toBe('computed_from_authorized_eod_grouped_daily');
    expect(panel.officialExchangePublishedBreadth).toBe(false);
    expect(panel.fulfilledMetrics).toEqual(['ADVANCERS', 'DECLINERS', 'UNCHANGED', 'ADVANCE_DECLINE_RATIO']);
    expect(panel.missingMetrics).toEqual(['NEW_HIGHS', 'NEW_LOWS', 'HIGH_LOW_RATIO']);
    expect(panel.metricCoverageRatio).toBeCloseTo(4 / 7);
    expect(panel.broadMarketClaimAllowed).toBe(true);
    expect(panel.reasonCodes).toEqual(['partial_metric_coverage']);
  });

  it('does not invent breadth coverage when backend omits it', async () => {
    const { marketOverviewApi } = await import('../marketOverview');

    get.mockResolvedValueOnce({
      data: {
        panel_name: 'IndexTrendsCard',
        last_refresh_at: '2026-06-07T09:00:00Z',
        status: 'success',
        source: 'yahoo',
        updated_at: '2026-06-07T09:01:00Z',
        as_of: '2026-06-07T09:00:00Z',
        freshness: 'live',
        items: [{ symbol: 'SPX', label: 'S&P 500', value: 5200 }],
      },
    });

    const panel = await marketOverviewApi.getIndices();

    expect(panel.breadthClaimType).toBeUndefined();
    expect(panel.metricCoverageRatio).toBeUndefined();
    expect(panel.fulfilledMetrics).toBeUndefined();
    expect(panel.missingMetrics).toBeUndefined();
    expect(panel.broadMarketClaimAllowed).toBeUndefined();
  });
});
