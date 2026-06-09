import { afterEach, describe, expect, it, vi } from 'vitest';
import apiClient from '../index';
import * as marketModule from '../market';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('market API path join hygiene', () => {
  it('normalizes market endpoint joins without introducing double slashes', () => {
    const buildMarketApiPath = (marketModule as { buildMarketApiPath?: (path: string) => string }).buildMarketApiPath;

    expect(buildMarketApiPath?.('/crypto')).toBe('/api/v1/market/crypto');
    expect(buildMarketApiPath?.('crypto')).toBe('/api/v1/market/crypto');
  });

  it('normalizes absolute market stream URLs without double slashes after /api/v1', () => {
    const buildMarketApiUrl = (marketModule as {
      buildMarketApiUrl?: (baseUrl: string, path: string) => string;
    }).buildMarketApiUrl;

    expect(buildMarketApiUrl?.('https://example.com/api/v1/', '/market/crypto/stream'))
      .toBe('https://example.com/api/v1/market/crypto/stream');
    expect(buildMarketApiUrl?.('https://example.com/api/v1', 'market/crypto/stream'))
      .toBe('https://example.com/api/v1/market/crypto/stream');
  });
});

describe('market temperature evidence normalization', () => {
  it('projects raw provider and runtime source labels into canonical consumer data states', () => {
    const cases = [
      ['PROVIDER ALTERNATIVE_ME', '可用'],
      ['ALTERNATIVE.ME', '可用'],
      ['YFINANCE', '可用'],
      ['YAHOO FINANCE', '可用'],
      ['CBOE', '可用'],
      ['BINANCE', '可用'],
      ['REAL', '可用'],
      ['MIXED', '部分可用'],
      ['FALLBACK', '延迟可用'],
      ['ETF flow proxy', 'ETF 资金流指标'],
      ['Institutional pressure proxy', '机构压力指标'],
      ['Industry breadth proxy', '行业广度指标'],
      ['Binance Futures', '可用'],
      ['local cache', '延迟可用'],
      ['synthetic fixture', '证据不足'],
    ] as const;

    for (const [rawLabel, productLabel] of cases) {
      const normalized = marketModule.normalizeMarketConsumerText(rawLabel);
      expect(normalized, rawLabel).toBe(productLabel);
      expect(normalized, rawLabel).not.toMatch(
        /ALTERNATIVE\.?ME|YFINANCE|YAHOO FINANCE|Yahoo Finance|CBOE|BINANCE|Binance Futures|REAL|MIXED|FALLBACK|fallback|proxy|cache|synthetic|mock|provider/i,
      );
    }
  });

  it('rewrites fallback demo wording into consumer-safe observation copy', () => {
    const panel = marketModule.normalizeMarketOverviewPanelConsumerCopy({
      panelName: 'ChinaIndicesCard',
      lastRefreshAt: '2026-06-01T09:00:00Z',
      status: 'success',
      source: 'fallback',
      sourceLabel: '备用数据',
      warning: '备用示例数据，不代表当前行情',
      items: [
        {
          symbol: 'CSI300',
          label: '沪深300',
          source: 'fallback',
          sourceLabel: '备用数据',
          freshness: 'fallback',
          warning: '当前真实数据不足，市场温度仅供界面演示。',
          hoverDetails: ['备用示例数据仅用于保持界面结构'],
        },
      ],
    });

    expect(panel.sourceLabel).toBe('延迟可用');
    expect(panel.warning).toBe('已使用最近一次可用数据，不代表当前实时行情');
    expect(panel.items[0].sourceLabel).toBe('延迟可用');
    expect(panel.items[0].warning).toBe('当前关键数据不足，暂不形成方向判断。');
    expect(panel.items[0].hoverDetails).toEqual(['最近可用数据仅保留市场结构观察']);
  });

  it('projects market overview proxy item labels before UI rendering', () => {
    const panel = marketModule.normalizeMarketOverviewPanelConsumerCopy({
      panelName: 'FundsFlowCard',
      lastRefreshAt: '2026-06-01T09:00:00Z',
      status: 'success',
      source: 'mixed',
      sourceLabel: 'MIXED',
      items: [
        { symbol: 'ETF_FLOW_PROXY', label: 'ETF flow proxy' },
        { symbol: 'INST_PRESSURE', label: 'Institutional pressure proxy' },
        { symbol: 'INDUSTRY_BREADTH', label: 'Industry breadth proxy' },
      ],
    });

    expect(panel.items.map((item) => item.label)).toEqual([
      'ETF 资金流指标',
      '机构压力指标',
      '行业广度指标',
    ]);
  });

  it('preserves additive regime summary payloads from snake_case responses', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValueOnce({
      data: {
        source: 'computed',
        updated_at: '2026-06-01T09:00:00Z',
        conclusion_allowed: false,
        scores: {
          overall: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
          us_risk_appetite: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
          cn_money_effect: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
          macro_pressure: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
          liquidity: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
        },
        regime_summary: {
          label: 'growth-led risk-on',
          title: 'Growth-led risk-on watch',
          diagnostic_only: true,
          observation_only: true,
          source_authority_allowed: false,
          score_contribution_allowed: false,
          not_investment_advice: true,
          drivers: [
            {
              key: 'watch:capital_flow_signal',
              label: 'Capital flow signal',
              detail: 'Liquidity still leans into growth leadership.',
            },
          ],
          blockers: [],
          contradictions: [],
          confidence: {
            value: 0.62,
            label: 'medium',
          },
          confidence_caps: [
            {
              key: 'partial_context_only',
              label: 'Partial context only',
              detail: 'Signal remains observation-only.',
            },
          ],
          next_watch_items: [
            {
              key: 'rotation_follow_through',
              label: 'Rotation follow-through',
              detail: 'Need fresh confirmation from leadership breadth.',
            },
          ],
          explanation: 'Liquidity and rotation still lean risk-on, but authority stays fail-closed.',
        },
      },
    });

    const payload = await marketModule.marketApi.getTemperature();

    expect(payload.regimeSummary?.label).toBe('growth-led risk-on');
    expect(payload.regimeSummary?.drivers[0]).toEqual({
      key: 'watch:capital_flow_signal',
      label: 'Capital flow signal',
      detail: 'Liquidity still leans into growth leadership.',
    });
    expect(payload.regimeSummary?.confidence).toEqual({
      value: 0.62,
      label: 'medium',
    });
    expect(payload.regimeSummary?.confidenceCaps[0].key).toBe('partial_context_only');
    expect(payload.regimeSummary?.nextWatchItems[0].key).toBe('rotation_follow_through');
  });

  it('preserves source-confidence fields without accepting unlabeled market evidence', () => {
    const payload = marketModule.normalizeMarketTemperatureResponse({
      source: 'computed',
      updatedAt: '2026-05-20T10:00:00+08:00',
      marketRegimeSynthesis: {
        primaryRegime: 'risk_on',
        secondaryRegimes: ['liquidity_support'],
        regimeScores: { risk_on: 0.7 },
        topDrivers: [
          {
            key: 'market:liquidity',
            label: 'Liquidity support',
            source: 'liquidity_monitor',
            sourceTier: 'official_public',
            trustLevel: 'reliable',
            freshness: 'delayed',
            observationOnly: false,
            scoreContributionAllowed: true,
            discountReasons: ['stale', ''],
            degradationReason: 'delayed_source',
          },
          {
            key: 'market:missing_label',
            reason: 'missing label should still be rejected for market synthesis',
          } as never,
        ],
        counterEvidence: [],
        dataGaps: [],
        narrativeBullets: ['Liquidity support is the top driver.'],
      },
      scores: {
        overall: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
        usRiskAppetite: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
        cnMoneyEffect: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
        macroPressure: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
        liquidity: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
      },
    });

    expect(payload.marketRegimeSynthesis?.topDrivers).toHaveLength(1);
    expect(payload.marketRegimeSynthesis?.topDrivers[0]).toMatchObject({
      key: 'market:liquidity',
      label: 'Liquidity support',
      source: 'liquidity_monitor',
      sourceTier: 'official_public',
      trustLevel: 'reliable',
      freshness: 'delayed',
      observationOnly: false,
      scoreContributionAllowed: true,
      discountReasons: ['stale'],
      degradationReason: 'delayed_source',
    });
  });

  it('preserves market decision semantics without dropping boundaries or gaps', () => {
    const payload = marketModule.normalizeMarketTemperatureResponse({
      source: 'computed',
      updatedAt: '2026-05-21T10:00:00+08:00',
      marketDecisionSemantics: {
        version: 'market_decision_semantics_v1',
        posture: 'offensive',
        postureConfidence: {
          value: 62,
          label: 'medium',
          capReasons: ['counter_evidence_present'],
        },
        exposureBias: 'risk_on_watch',
        styleTilts: [{ tilt: 'liquidity_beta_watch', label: 'Liquidity beta watch', detail: 'Watch-only.' }],
        confirmationSignals: [{ signal: 'liquidity_alignment', detail: 'Liquidity should remain expanding.' }],
        invalidationTriggers: [{ trigger: 'liquidity_stops_expanding', detail: 'Liquidity turns mixed.' }],
        counterEvidence: [{ surface: 'market_regime_synthesis', key: 'rates:US10Y', label: 'US10Y' }],
        dataGaps: [{ surface: 'liquidity_impulse_synthesis', key: 'official:fed_liquidity', label: 'Fed liquidity' }],
        claimBoundaries: [{ claim: 'direct_trade_action', allowed: false, reasonCode: 'not_investment_advice' }],
        notInvestmentAdvice: true,
      },
      scores: {
        overall: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
        usRiskAppetite: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
        cnMoneyEffect: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
        macroPressure: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
        liquidity: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
      },
    } as never);

    const semantics = (payload as { marketDecisionSemantics?: Record<string, unknown> }).marketDecisionSemantics;

    expect(semantics).toMatchObject({
      posture: 'offensive',
      exposureBias: 'risk_on_watch',
      notInvestmentAdvice: true,
    });
    expect(semantics?.postureConfidence).toMatchObject({
      value: 62,
      label: 'medium',
      capReasons: ['counter_evidence_present'],
    });
    expect(semantics?.dataGaps).toEqual([
      expect.objectContaining({ key: 'official:fed_liquidity', label: 'Fed liquidity' }),
    ]);
    expect(semantics?.claimBoundaries).toEqual([
      expect.objectContaining({ claim: 'direct_trade_action', allowed: false }),
    ]);
  });
});

describe('market snapshot normalization', () => {
  it('preserves US breadth authority and partial coverage metadata', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValueOnce({
      data: {
        source: 'computed_from_authorized_polygon_grouped_daily',
        source_label: 'Polygon grouped daily',
        source_type: 'authorized_computed',
        freshness: 'delayed',
        is_partial: true,
        breadth_claim_type: 'computed_from_authorized_eod_grouped_daily',
        official_exchange_published_breadth: false,
        fulfilled_metrics: ['ADVANCERS', 'DECLINERS', 'UNCHANGED', 'ADVANCE_DECLINE_RATIO'],
        missing_metrics: ['NEW_HIGHS', 'NEW_LOWS', 'HIGH_LOW_RATIO'],
        metric_coverage_ratio: 4 / 7,
        source_authority_allowed: true,
        score_contribution_allowed: true,
        broad_market_claim_allowed: true,
        source_authority_reason: 'authorized_polygon_eod_grouped_daily',
        reason_codes: ['polygon_high_low_history_unavailable'],
        route_rejected_reason_codes: ['official_exchange_published_breadth_unavailable'],
        provider_health: {
          provider: 'polygon',
          status: 'partial',
          is_fallback: false,
          is_stale: false,
          is_refreshing: false,
          source_label: 'Polygon grouped daily',
        },
        warning: 'High/low breadth unavailable.',
        updated_at: '2026-05-22T04:00:00Z',
        as_of: '2026-05-21',
        items: [
          {
            symbol: 'ADVANCERS',
            label: 'Advancers',
            value: 2874,
            source_authority_allowed: true,
            score_contribution_allowed: true,
            fulfilled_metrics: ['ADVANCERS'],
            missing_metrics: ['NEW_HIGHS', 'NEW_LOWS', 'HIGH_LOW_RATIO'],
            reason_codes: ['polygon_high_low_history_unavailable'],
            provider_health: {
              provider: 'polygon',
              status: 'partial',
              is_fallback: false,
              is_stale: false,
              is_refreshing: false,
              source_label: 'Polygon grouped daily',
            },
          },
        ],
      },
    });

    const panel = await marketModule.marketApi.getUsBreadth();

    expect(panel).toMatchObject({
      source: 'computed_from_authorized_polygon_grouped_daily',
      sourceLabel: 'Polygon grouped daily',
      sourceType: 'authorized_computed',
      freshness: 'delayed',
      isPartial: true,
      breadthClaimType: 'computed_from_authorized_eod_grouped_daily',
      officialExchangePublishedBreadth: false,
      fulfilledMetrics: ['ADVANCERS', 'DECLINERS', 'UNCHANGED', 'ADVANCE_DECLINE_RATIO'],
      missingMetrics: ['NEW_HIGHS', 'NEW_LOWS', 'HIGH_LOW_RATIO'],
      metricCoverageRatio: 4 / 7,
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: true,
      broadMarketClaimAllowed: true,
      sourceAuthorityReason: 'authorized_polygon_eod_grouped_daily',
      reasonCodes: ['polygon_high_low_history_unavailable'],
      routeRejectedReasonCodes: ['official_exchange_published_breadth_unavailable'],
      providerHealth: expect.objectContaining({ provider: 'polygon', status: 'partial' }),
      warning: 'High/low breadth unavailable.',
    });
    expect(panel.items[0]).toMatchObject({
      symbol: 'ADVANCERS',
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: true,
      fulfilledMetrics: ['ADVANCERS'],
      missingMetrics: ['NEW_HIGHS', 'NEW_LOWS', 'HIGH_LOW_RATIO'],
      reasonCodes: ['polygon_high_low_history_unavailable'],
      providerHealth: expect.objectContaining({ provider: 'polygon', status: 'partial' }),
    });
  });
});
