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

describe('professional data capability registry normalization', () => {
  it('normalizes categories, statuses, and consumer-safe fields from the registry endpoint', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValueOnce({
      data: {
        contract_version: 'professional_data_capability_registry_v1',
        consumer_safe: true,
        summary: {
          total_capabilities: 6,
          live_count: 1,
          degraded_count: 1,
          entitlement_required_count: 1,
          configured_missing_count: 1,
          not_implemented_count: 2,
        },
        categories: [
          'options_structure',
          'market_breadth_flows',
          'sector_rotation',
          'macro_cross_asset_regime',
          'stock_research_data',
          'backtest_data_availability',
        ],
        capabilities: [
          {
            capability_id: 'options.chain',
            label: 'Options chain',
            category: 'options_structure',
            status: 'entitlement_required',
            source_label: 'Options Lab readiness boundary',
            reason: 'Options chain display is blocked until entitlement evidence is verified.',
            freshness: 'Unavailable until rights are proven.',
            providerClass: 'Must never render',
          },
          {
            capability_id: 'market.breadth_flows',
            label: 'Market breadth and flows',
            category: 'market_breadth_flows',
            status: 'degraded',
            source_label: 'Market readiness registry',
            reason: 'Breadth context exists with incomplete source authority.',
            freshness: 'Partial and delayed.',
          },
          {
            capability_id: 'market.sector_rotation',
            label: 'Sector rotation',
            category: 'sector_rotation',
            status: 'degraded',
            source_label: 'Market rotation readiness registry',
            reason: 'Membership and quote authority remain incomplete.',
            freshness: 'Partial and delayed.',
          },
          {
            capability_id: 'macro.cross_asset_regime',
            label: 'Macro and cross-asset regime',
            category: 'macro_cross_asset_regime',
            status: 'live',
            source_label: 'Macro readiness registry',
            reason: 'Stored macro rows are available for observation.',
            freshness: 'Stored or delayed observations.',
          },
          {
            capability_id: 'stock.news',
            label: 'Stock news and catalysts',
            category: 'stock_research_data',
            status: 'configured_missing',
            source_label: 'Single-stock readiness registry',
            reason: 'Catalyst evidence is not consistently configured.',
            freshness: 'Missing or inconsistent across symbols.',
          },
          {
            capability_id: 'backtest.data_availability',
            label: 'Backtest data availability',
            category: 'backtest_data_availability',
            status: 'not_implemented',
            source_label: 'Backtest readiness registry',
            reason: 'requestId rawPayload token should be redacted',
            freshness: 'Research-useful, but lineage is incomplete.',
          },
        ],
      },
    });

    const payload = await marketModule.marketApi.getProfessionalDataCapabilities();
    const view = marketModule.buildProfessionalDataCapabilityRegistryView(payload);

    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/market/professional-data-capabilities');
    expect(view.summary.totalCapabilities).toBe(6);
    expect(view.categories.map((category) => category.categoryKey)).toEqual([
      'options_structure',
      'market_breadth_flows',
      'sector_rotation',
      'macro_cross_asset_regime',
      'stock_research_data',
      'backtest_data_availability',
    ]);
    expect(view.categories[0].items[0]).toMatchObject({
      label: 'Options chain',
      status: { key: 'entitlement_required', label: '需授权', variant: 'danger' },
      sourceLabel: 'Options Lab readiness boundary',
    });
    expect(view.categories[5].items[0].detail).toBe('Research-useful, but lineage is incomplete.');
    expect(view.statusCounts.map((item) => item.label)).toEqual([
      '可用 1',
      '降级 1',
      '需授权 1',
      '配置待补 1',
      '未实现 2',
    ]);
    expect(JSON.stringify(view)).not.toMatch(
      /providerClass|providerName|providerAttempted|requiredProviderClass|sourceAuthorityRouter|endpointHost|apiKeyPresent|exceptionClass|exceptionChain|requestId|traceId|cacheKey|rawPayload|credential|token|env/i,
    );
  });
});

describe('market temperature evidence normalization', () => {
  it('normalizes official risk source readiness and maps it to consumer labels', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValueOnce({
      data: {
        readiness_status: 'ready',
        diagnostic_only: true,
        provider_runtime_called: false,
        network_calls_enabled: false,
        representative_symbols: [],
        checks: [],
        official_risk_source_readiness: {
          bundle_state: 'partial',
          vix: { state: 'ready', freshness: 'live' },
          rates: { state: 'stale', freshness: 'stale' },
          fed_liquidity: { state: 'blocked', freshness: 'unavailable' },
        },
      },
    });

    const payload = await marketModule.marketApi.getDataReadiness();
    const view = marketModule.buildOfficialRiskSourceReadinessView(payload.officialRiskSourceReadiness);

    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/market/data-readiness', {});
    expect(payload.officialRiskSourceReadiness?.bundleState).toBe('partial');
    expect(payload.officialRiskSourceReadiness?.fedLiquidity?.state).toBe('blocked');
    expect(view.bundleLabel).toBe('官方风险源部分可用');
    expect(view.chips.map((chip) => chip.label)).toEqual(['VIX可用', '利率待更新', 'Fed流动性待补']);
    expect(`${view.bundleLabel} ${view.chips.map((chip) => chip.label).join(' ')}`).not.toMatch(
      /authorized|unavailable|partial|unknown|fallbackUsed|providerConfigured|sourceAuthority|scoreContributionAllowed|provider|runtime|credential/i,
    );
  });

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
    expect(panel.items[0].warning).toBe('数据待补');
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

  it('preserves additive market regime synthesis research fields for the UI projection', () => {
    const payload = marketModule.normalizeMarketTemperatureResponse({
      source: 'computed',
      updatedAt: '2026-06-16T10:00:00+08:00',
      marketRegimeSynthesis: {
        contractVersion: 'market_regime_synthesis_research_v1',
        primaryRegime: 'risk_on_liquidity_expansion',
        secondaryRegimes: ['goldilocks_soft_landing'],
        regimeScores: { risk_on_liquidity_expansion: 0.72 },
        regimeLabel: 'Risk-supportive liquidity expansion',
        regimePosture: 'risk_supportive',
        evidenceFamilies: [
          {
            key: 'marketOverview',
            label: 'Market overview',
            state: 'supported',
            pillars: ['risk_appetite'],
            evidenceCount: 2,
            supportiveCount: 1,
            contradictoryCount: 1,
            missingCount: 0,
            freshness: 'cached',
            observationOnly: true,
          },
        ],
        supportiveEvidence: [
          {
            key: 'indices:SPX',
            label: 'SPX',
            family: 'marketOverview',
            pillar: 'risk_appetite',
            direction: 'positive',
            freshness: 'cached',
            observationOnly: true,
          },
        ],
        contradictoryEvidence: [
          {
            key: 'rates:US10Y',
            label: 'US10Y',
            family: 'marketOverview',
            pillar: 'rates_pressure',
            reason: 'contradictory_evidence',
            observationOnly: true,
          },
        ],
        missingEvidence: [
          {
            key: 'breadth:CN',
            label: 'A股宽度',
            family: 'breadth',
            pillar: 'breadth_health',
            reason: 'missing_evidence',
            observationOnly: true,
          },
        ],
        confidenceCap: {
          value: 0.58,
          label: 'medium',
          reasons: ['contradictory_evidence'],
        },
        observationBoundary: {
          observationOnly: true,
          decisionGrade: false,
          sourceAuthorityAllowed: false,
          scoreContributionAllowed: false,
          consumerActionBoundary: 'no_advice',
          notInvestmentAdvice: true,
          detail: 'Research synthesis only; evidence is not promoted into execution or personalized direction.',
        },
        researchNextSteps: [
          {
            key: 'review_contradictions',
            label: 'Review contradictory evidence',
            detail: 'Compare the conflicting families before treating one regime as dominant.',
          },
        ],
        generatedAt: '2026-06-16T02:00:00Z',
        freshness: 'cached',
        topDrivers: [],
        counterEvidence: [],
        dataGaps: [],
        narrativeBullets: [],
      },
      scores: {
        overall: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
        usRiskAppetite: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
        cnMoneyEffect: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
        macroPressure: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
        liquidity: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
      },
    } as never);

    expect(payload.marketRegimeSynthesis?.contractVersion).toBe('market_regime_synthesis_research_v1');
    expect(payload.marketRegimeSynthesis?.regimeLabel).toBe('Risk-supportive liquidity expansion');
    expect(payload.marketRegimeSynthesis?.regimePosture).toBe('risk_supportive');
    expect(payload.marketRegimeSynthesis?.evidenceFamilies[0]).toMatchObject({
      key: 'marketOverview',
      state: 'supported',
      freshness: 'cached',
      observationOnly: true,
    });
    expect(payload.marketRegimeSynthesis?.supportiveEvidence[0]).toMatchObject({
      key: 'indices:SPX',
      label: 'SPX',
      family: 'marketOverview',
    });
    expect(payload.marketRegimeSynthesis?.contradictoryEvidence[0].label).toBe('US10Y');
    expect(payload.marketRegimeSynthesis?.missingEvidence[0].label).toBe('A股宽度');
    expect(payload.marketRegimeSynthesis?.confidenceCap).toEqual({
      value: 0.58,
      label: 'medium',
      reasons: ['contradictory_evidence'],
    });
    expect(payload.marketRegimeSynthesis?.observationBoundary).toMatchObject({
      observationOnly: true,
      decisionGrade: false,
      consumerActionBoundary: 'no_advice',
      notInvestmentAdvice: true,
    });
    expect(payload.marketRegimeSynthesis?.researchNextSteps[0].key).toBe('review_contradictions');
    expect(payload.marketRegimeSynthesis?.freshness).toBe('cached');
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
