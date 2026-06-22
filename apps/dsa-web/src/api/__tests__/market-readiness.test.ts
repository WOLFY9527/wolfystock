import { beforeEach, describe, expect, it, vi } from 'vitest';

const { get } = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock('../index', () => ({
  default: {
    get,
  },
}));

describe('marketApi.getDataReadiness', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads and normalizes the read-only market data readiness diagnostics response', async () => {
    const { marketApi } = await import('../market');
    get.mockResolvedValueOnce({
      data: {
        readiness_status: 'partial',
        diagnostic_only: true,
        provider_runtime_called: false,
        network_calls_enabled: false,
        representative_symbols: ['AAPL', 'SPY', 'BTC-USD'],
        checks: [
          {
            id: 'tushare_token',
            status: 'missing',
            severity: 'warning',
            user_facing_message: 'Tushare token is not configured.',
            remediation_hint: 'Set TUSHARE_TOKEN for local CN/HK diagnostics.',
            affects_surfaces: ['market_overview', 'liquidity_monitor'],
            secret_configured: false,
          },
          {
            id: 'optional_provider_dependencies',
            status: 'partial',
            severity: 'warning',
            user_facing_message: 'Some optional local provider dependencies are not importable.',
            remediation_hint: 'Install the missing local provider SDKs when required.',
            affects_surfaces: ['market_overview', 'liquidity_monitor'],
            details: {
              available_modules: ['tushare'],
              missing_modules: ['pytdx', 'akshare'],
            },
          },
        ],
        consumer_evidence_readiness_matrix: {
          contract_version: 'consumer_evidence_readiness_matrix_v1',
          diagnostic_only: true,
          network_calls_enabled: false,
          mutation_enabled: false,
          items: [
            {
              surface: 'market_overview',
              evidence_family: 'market_regime',
              required_inputs: ['macro context', 'liquidity context'],
              fulfilled_inputs: ['market overview read model'],
              missing_inputs: ['macro context'],
              stale_inputs: [],
              blocked_inputs: ['liquidity context'],
              observation_only_inputs: ['rotation context'],
              score_grade_inputs: ['market overview read model'],
              readiness_state: 'score_grade',
              confidence_cap_reason: 'Supporting families still cap confidence.',
              source_authority_reason: 'Supporting families need stronger display authority.',
              freshness_reason: 'Freshness is measured by each existing market surface before this matrix is shown.',
              next_diagnostic: 'Compare overview evidence families against current safe surface snapshots.',
              consumer_safe_summary: 'Market overview has one score-grade input, while supporting evidence remains capped or observational.',
            },
          ],
        },
      },
    });

    const payload = await marketApi.getDataReadiness({ symbols: ['AAPL', 'SPY', 'BTC-USD'] });

    expect(get).toHaveBeenCalledWith('/api/v1/market/data-readiness', {
      params: { symbols: 'AAPL,SPY,BTC-USD' },
    });
    expect(payload.readinessStatus).toBe('partial');
    expect(payload.diagnosticOnly).toBe(true);
    expect(payload.providerRuntimeCalled).toBe(false);
    expect(payload.networkCallsEnabled).toBe(false);
    expect(payload.representativeSymbols).toEqual(['AAPL', 'SPY', 'BTC-USD']);
    expect(payload.checks[0].secretConfigured).toBe(false);
    expect(payload.checks[1].details?.missingModules).toEqual(['pytdx', 'akshare']);
    expect(payload.consumerEvidenceReadinessMatrix?.contractVersion).toBe('consumer_evidence_readiness_matrix_v1');
    expect(payload.consumerEvidenceReadinessMatrix?.diagnosticOnly).toBe(true);
    expect(payload.consumerEvidenceReadinessMatrix?.items[0]).toMatchObject({
      surface: 'market_overview',
      evidenceFamily: 'market_regime',
      readinessState: 'score_grade',
      missingInputs: ['macro context'],
      blockedInputs: ['liquidity context'],
      observationOnlyInputs: ['rotation context'],
      scoreGradeInputs: ['market overview read model'],
      nextDiagnostic: 'Compare overview evidence families against current safe surface snapshots.',
    });
  });

  it('builds compact consumer evidence boundary labels without exposing matrix internals', async () => {
    const { buildConsumerEvidenceBoundaryView } = await import('../market');

    const view = buildConsumerEvidenceBoundaryView({
      contractVersion: 'consumer_evidence_readiness_matrix_v1',
      diagnosticOnly: true,
      networkCallsEnabled: false,
      mutationEnabled: false,
      items: [
        {
          surface: 'market_overview',
          evidenceFamily: 'market_regime',
          requiredInputs: ['market overview read model', 'market breadth context', 'rotation context', 'macro context', 'liquidity context'],
          fulfilledInputs: ['market overview read model'],
          missingInputs: ['market breadth context'],
          staleInputs: ['rotation context'],
          blockedInputs: ['macro context'],
          observationOnlyInputs: ['liquidity context'],
          scoreGradeInputs: ['market overview read model'],
          readinessState: 'score_grade',
          confidenceCapReason: 'internal cap reason',
          sourceAuthorityReason: 'source_authority_router_rejected',
          freshnessReason: 'freshness stale',
          nextDiagnostic: 'Compare raw provider cache diagnostics.',
          consumerSafeSummary: 'Market overview evidence summary.',
        },
      ],
    });

    expect(view.label).toBe('证据可用');
    expect(view.chips.map((chip) => chip.label)).toEqual([
      '证据可用',
      '市场总览读数可用',
      '市场广度待补',
      '板块轮动待更新',
      '风险状态仅观察',
    ]);
    expect(view.nextEvidence).toBe('下一步：补齐市场广度、宏观背景');
    expect(JSON.stringify(view)).not.toMatch(
      /contractVersion|market_overview|market_regime|confidenceCapReason|sourceAuthority|nextDiagnostic|consumerSafeSummary|provider|cache|debug|raw|buy|sell|target price|position sizing|买入|卖出|目标价|止损|仓位/i,
    );
  });

  it('keeps absent consumer evidence readiness fail-closed', async () => {
    const { buildConsumerEvidenceBoundaryView } = await import('../market');

    const view = buildConsumerEvidenceBoundaryView(undefined);

    expect(view.label).toBe('证据边界待确认');
    expect(view.chips.map((chip) => chip.label)).toContain('市场总览待补');
    expect(view.chips.map((chip) => chip.label)).toContain('广度待补');
    expect(view.chips.map((chip) => chip.label)).toContain('板块轮动待补');
    expect(view.chips.map((chip) => chip.label)).toContain('风险状态待补');
    expect(JSON.stringify(view)).not.toMatch(/证据可用|provider|cache|debug|raw|buy|sell|买入|卖出|目标价|止损|仓位/i);
  });
});

describe('marketApi.getDataSourceGapRegistry', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads the read-only data source gap registry and builds a consumer-safe data map view', async () => {
    const { buildDataSourceGapRegistryView, marketApi } = await import('../market');
    get.mockResolvedValueOnce({
      data: {
        contract_version: 'data_source_gap_registry_v1',
        diagnostic_only: true,
        provider_runtime_called: false,
        network_calls_enabled: false,
        score_authority_allowed: false,
        summary: {
          total_families: 4,
          ready_count: 0,
          partial_count: 1,
          missing_count: 0,
          blocked_count: 1,
          unauthorized_count: 1,
          stale_count: 0,
          observation_only_count: 1,
          planned_count: 0,
          provider_hydration_allowed_count: 2,
          score_trading_authority_allowed_count: 0,
        },
        families: [
          {
            family_key: 'stock_quote_spine',
            consumer_label: 'Stock Quote Spine',
            status: 'partial',
            authority_state: 'blocked',
            freshness_state: 'delayed',
            entitlement_or_licensing_blocker: null,
            integration_blocker: 'Durable quote/OHLCV snapshots are still missing.',
            source_evidence_state: 'fragmented_runtime_evidence',
            next_integration_step: 'Land bounded snapshot storage.',
            provider_hydration_allowed: true,
            score_trading_authority_allowed: false,
            consumer_safe_description: 'Quote paths exist, but lineage is incomplete.',
            surface_impact_matrix: [
              {
                surface_key: 'watchlist',
                consumer_label: 'Watchlist',
                impact_state: 'degraded',
                impact_reason: '保存标的不能从分散报价路径推断行级新鲜度。',
                affected_capability: '行级价格、更新时间、研究状态',
                next_evidence_step: '让 watchlist row packet 引用明确的报价/日线快照 ID。',
              },
              {
                surface_key: 'backtest_parameter_sweep',
                consumer_label: 'Backtest / Parameter Sweep',
                impact_state: 'observation-only',
                impact_reason: '历史 bars 的来源、调整基准和可复现快照仍不完整。',
                affected_capability: '研究级回测数据边界、参数扫读回边界',
                next_evidence_step: '补齐数据集 ID、调整基准、交易日历和缺失 bars 策略。',
              },
            ],
          },
          {
            family_key: 'macro_rates',
            consumer_label: 'Macro / Rates',
            status: 'observation-only',
            authority_state: 'observation-only',
            freshness_state: 'cached',
            source_evidence_state: 'diagnostic_contract',
            next_integration_step: 'Persist official macro rows.',
            provider_hydration_allowed: true,
            score_trading_authority_allowed: false,
            consumer_safe_description: 'Diagnostic only.',
            surface_impact_matrix: [
              {
                surface_key: 'market_overview',
                consumer_label: 'Market Overview',
                impact_state: 'observation-only',
                impact_reason: '官方宏观行还不是完整产品数据包。',
                affected_capability: '利率压力、宏观风险摘要',
                next_evidence_step: '持久化官方宏观序列并附覆盖和时效状态。',
              },
            ],
          },
          {
            family_key: 'options_chains',
            consumer_label: 'Options Chains',
            status: 'unauthorized',
            authority_state: 'unauthorized',
            freshness_state: 'unavailable',
            entitlement_or_licensing_blocker: 'OPRA rights are not proven.',
            integration_blocker: 'No authorized chain store.',
            source_evidence_state: 'rights_unproven',
            next_integration_step: 'Attach entitlement proof.',
            provider_hydration_allowed: false,
            score_trading_authority_allowed: false,
            consumer_safe_description: 'Options chains remain unavailable.',
            surface_impact_matrix: [
              {
                surface_key: 'options_lab',
                consumer_label: 'Options Lab',
                impact_state: 'blocked',
                impact_reason: '授权期权链、展示权、存储权和字段覆盖未证明。',
                affected_capability: '链、IV、Greeks、OI、成交量观察',
                next_evidence_step: '先补齐权益证明包和字段覆盖证据。',
              },
            ],
          },
          {
            family_key: 'gamma_dealer_positioning',
            consumer_label: 'Gamma / Dealer Positioning',
            status: 'blocked',
            authority_state: 'unauthorized',
            freshness_state: 'unavailable',
            entitlement_or_licensing_blocker: 'Rights and methodology are not proven.',
            integration_blocker: 'No approved exposure methodology.',
            source_evidence_state: 'rights_unproven',
            next_integration_step: 'Approve inputs and methodology.',
            provider_hydration_allowed: false,
            score_trading_authority_allowed: false,
            consumer_safe_description: 'Gamma remains blocked.',
            surface_impact_matrix: [
              {
                surface_key: 'market_overview',
                consumer_label: 'Market Overview',
                impact_state: 'unknown',
                impact_reason: '未证明的期权结构不能进入市场风险第一读。',
                affected_capability: '期权结构风险背景',
                next_evidence_step: '在 Options Lab 方法通过前保持未知。',
              },
            ],
          },
        ],
        metadata: {
          request_id: 'req-secret',
          trace_id: 'trace-secret',
          raw_provider_payloads_included: false,
          cache_key: 'internal-cache',
        },
      },
    });

    const payload = await marketApi.getDataSourceGapRegistry();
    const view = buildDataSourceGapRegistryView(payload);

    expect(get).toHaveBeenCalledWith('/api/v1/market/data-source-gap-registry');
    expect(payload.providerRuntimeCalled).toBe(false);
    expect(payload.networkCallsEnabled).toBe(false);
    expect(payload.scoreAuthorityAllowed).toBe(false);
    expect(view.summary.totalFamilies).toBe(4);
    expect(view.groups.map((group) => [group.groupId, group.groupLabel, group.families.length])).toEqual([
      ['quote_market', '报价 / 市场骨架', 1],
      ['options', '期权与衍生结构', 2],
      ['macro_liquidity_credit', '宏观 / 流动性 / 信用', 1],
      ['backtest_research', '回测 / 研究血缘', 0],
      ['scenario', '情景基线', 0],
      ['portfolio', '组合估值', 0],
      ['positioning_flows', '持仓 / 资金流', 0],
    ]);
    expect(view.families.map((family) => [family.familyKey, family.familyLabel, family.status.label])).toEqual([
      ['stock_quote_spine', '股票报价骨架', '部分可用'],
      ['macro_rates', '宏观与利率', '仅观察'],
      ['options_chains', '期权链', '未授权'],
      ['gamma_dealer_positioning', 'Gamma / Dealer Positioning', '阻断'],
    ]);
    expect(view.families.find((family) => family.familyKey === 'stock_quote_spine')).toMatchObject({
      groupId: 'quote_market',
      groupLabel: '报价 / 市场骨架',
      dataHydrationAllowed: '允许',
      scoreTradingAuthorityAllowed: '不允许',
    });
    expect(view.families.find((family) => family.familyKey === 'stock_quote_spine')?.surfaceImpactMatrix).toMatchObject([
      {
        surfaceKey: 'watchlist',
        surfaceLabel: 'Watchlist',
        impactState: { label: '降级', variant: 'caution' },
        affectedCapability: '行级价格、更新时间、研究状态',
      },
      {
        surfaceKey: 'backtest_parameter_sweep',
        surfaceLabel: '回测 / 参数扫描',
        impactState: { label: '仅观察', variant: 'neutral' },
      },
    ]);
    expect(view.families.find((family) => family.familyKey === 'options_chains')?.scoreTradingAuthorityAllowed).toBe('不允许');
    expect(view.families.find((family) => family.familyKey === 'options_chains')?.surfaceImpactMatrix[0].impactState.label).toBe('阻断');
    expect(view.families.find((family) => family.familyKey === 'gamma_dealer_positioning')?.dataHydrationAllowed).toBe('不允许');
    expect(view.families.find((family) => family.familyKey === 'gamma_dealer_positioning')?.surfaceImpactMatrix[0].impactState.label).toBe('待补证');
    expect(JSON.stringify(view)).not.toMatch(/requestId|traceId|rawProviderPayload|cacheKey|credential|env|debug|api[_-]?key|buy|sell|target price|stop loss|position sizing|买入|卖出|目标价|止损|仓位/i);
  });

  it('keeps missing registry family fields fail-closed instead of overclaiming readiness', async () => {
    const { buildDataSourceGapRegistryView, marketApi } = await import('../market');
    get.mockResolvedValueOnce({
      data: {
        diagnostic_only: true,
        provider_runtime_called: false,
        network_calls_enabled: false,
        score_authority_allowed: false,
        summary: { total_families: 1 },
        families: [
          {
            family_key: 'unknown_new_family',
            consumer_label: 'Unknown New Family',
            surface_impact_matrix: [
              {
                surface_key: 'unknown_surface',
                consumer_label: 'requestId secret surface',
                impact_state: 'unlocked',
                impact_reason: 'rawProviderPayload requestId traceId',
                affected_capability: 'debug cacheKey capability',
                next_evidence_step: 'token=secret next step',
              },
            ],
          },
        ],
      },
    });

    const payload = await marketApi.getDataSourceGapRegistry();
    const view = buildDataSourceGapRegistryView(payload);
    const family = view.families[0];

    expect(family.familyKey).toBe('unknown_new_family');
    expect(family.status.label).toBe('待补证');
    expect(family.authorityState.label).toBe('阻断');
    expect(family.freshnessState.label).toBe('待补证');
    expect(family.dataHydrationAllowed).toBe('待补证');
    expect(family.scoreTradingAuthorityAllowed).toBe('待补证');
    expect(family.consumerSafeDescription).toBe('数据说明待补证。');
    expect(family.surfaceImpactMatrix).toMatchObject([
      {
        surfaceLabel: '影响面待补证',
        impactState: { label: '待补证', variant: 'caution' },
        impactReason: '影响原因待补证。',
        affectedCapability: '影响能力待补证。',
        nextEvidenceStep: '下一证据步骤待补证。',
      },
    ]);
    expect(view.groups.find((group) => group.groupId === 'other')?.families[0]?.familyKey).toBe('unknown_new_family');
    expect(JSON.stringify(view)).not.toMatch(/已就绪|已解锁|权限 可用|新鲜|requestId|traceId|rawProviderPayload|cacheKey|token|secret|debug/i);
  });
});
