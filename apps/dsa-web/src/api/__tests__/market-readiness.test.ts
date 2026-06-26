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
        cross_asset_driver_readiness: {
          contract_version: 'cross_asset_driver_readiness_v1',
          consumer_safe: true,
          diagnostic_only: true,
          network_calls_enabled: false,
          external_provider_calls: false,
          mutation_enabled: false,
          supported_states: ['available', 'missing', 'stale', 'insufficient_history', 'not_configured'],
          consumer_summary: 'Cross-asset drivers are reported as data-readiness inputs only; no market conclusion is inferred.',
          summary: {
            total_drivers: 2,
            available_count: 1,
            missing_count: 1,
            stale_count: 0,
            insufficient_history_count: 0,
            not_configured_count: 0,
          },
          drivers: [
            {
              category: 'equities_index',
              label: 'Equities/index trend',
              supported: true,
              state: 'available',
              configured_identifiers: [
                { kind: 'symbol', value: 'SPY', market: 'us' },
                { kind: 'symbol', value: 'QQQ', market: 'us' },
              ],
              cached_ohlcv: {
                required_bars: 60,
                usable_bars: 82,
                missing_bars: 0,
                cache_state: 'cache_hit',
                freshness_state: 'fresh',
                latest_bar_date: '2026-06-25',
              },
              missing_reasons: [],
              consumer_safe_summary: 'Configured data is present for readiness evaluation.',
            },
            {
              category: 'credit',
              label: 'Credit spreads',
              supported: false,
              state: 'not_configured',
              configured_identifiers: [],
              cached_ohlcv: {
                required_bars: 60,
                usable_bars: 0,
                missing_bars: 60,
                cache_state: 'not_applicable',
                freshness_state: 'unknown',
                latest_bar_date: null,
              },
              missing_reasons: ['not_configured'],
              consumer_safe_summary: 'Driver category is not configured for readiness evaluation.',
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
    expect(payload.crossAssetDriverReadiness?.contractVersion).toBe('cross_asset_driver_readiness_v1');
    expect(payload.crossAssetDriverReadiness?.networkCallsEnabled).toBe(false);
    expect(payload.crossAssetDriverReadiness?.drivers[0]).toMatchObject({
      category: 'equities_index',
      state: 'available',
      configuredIdentifiers: [
        { kind: 'symbol', value: 'SPY', market: 'us' },
        { kind: 'symbol', value: 'QQQ', market: 'us' },
      ],
      cachedOhlcv: {
        requiredBars: 60,
        usableBars: 82,
        missingBars: 0,
      },
    });
  });

  it('builds compact cross-asset driver readiness labels without implying a regime conclusion', async () => {
    const { buildCrossAssetDriverReadinessView } = await import('../market');

    const view = buildCrossAssetDriverReadinessView({
      contractVersion: 'cross_asset_driver_readiness_v1',
      consumerSafe: true,
      diagnosticOnly: true,
      networkCallsEnabled: false,
      externalProviderCalls: false,
      mutationEnabled: false,
      supportedStates: ['available', 'missing', 'stale', 'insufficient_history', 'not_configured'],
      consumerSummary: 'Cross-asset drivers are reported as data-readiness inputs only; no market conclusion is inferred.',
      summary: {},
      drivers: [
        {
          category: 'equities_index',
          label: 'Equities/index trend',
          supported: true,
          state: 'available',
          configuredIdentifiers: [{ kind: 'symbol', value: 'SPY', market: 'us' }],
          cachedOhlcv: {
            requiredBars: 60,
            usableBars: 90,
            missingBars: 0,
            cacheState: 'cache_hit',
            freshnessState: 'fresh',
            latestBarDate: '2026-06-25',
          },
          missingReasons: [],
          consumerSafeSummary: 'Configured data is present for readiness evaluation.',
        },
        {
          category: 'oil_energy',
          label: 'Oil/energy',
          supported: true,
          state: 'insufficient_history',
          configuredIdentifiers: [{ kind: 'symbol', value: 'USO', market: 'us' }],
          cachedOhlcv: {
            requiredBars: 60,
            usableBars: 12,
            missingBars: 48,
            cacheState: 'cache_hit',
            freshnessState: 'fresh',
            latestBarDate: '2026-06-25',
          },
          missingReasons: ['insufficient_history'],
          consumerSafeSummary: 'Configured data exists but lacks required history.',
        },
      ],
    });

    expect(view.label).toBe('跨资产驱动部分可用');
    expect(view.chips.map((chip) => chip.label)).toEqual([
      'Equities/index trend: 可用 (SPY)',
      'Oil/energy: 历史不足 (USO)',
    ]);
    expect(JSON.stringify(view)).not.toMatch(
      /risk-on|risk-off|liquidity|inflation|recession|provider|runtime|raw|debug|cacheKey|requestId|traceId|buy|sell|target price|position sizing|买入|卖出|目标价|止损|仓位/i,
    );
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
          total_families: 5,
          ready_count: 0,
          partial_count: 1,
          missing_count: 1,
          blocked_count: 1,
          unauthorized_count: 1,
          stale_count: 0,
          observation_only_count: 1,
          planned_count: 0,
          provider_hydration_allowed_count: 2,
          score_trading_authority_allowed_count: 0,
        },
        acquisition_priority_queue: [
          {
            family_key: 'options_chains',
            family_label: 'Options Chains',
            priority: 'critical',
            priority_reason: '关键队列：影响 1 个产品面，1 项能力阻断或降级；当前行动为 确认期权链授权。',
            readiness_state: 'unauthorized',
            primary_blocker_type: 'entitlement',
            affected_surface_count: 1,
            blocked_or_degraded_capability_count: 1,
            external_entitlement_required: true,
            protected_domain_review_required: true,
            next_concrete_step: '收集授权与字段覆盖证据，不接入数据源运行链路。',
            required_evidence: ['授权证明', '字段覆盖清单'],
            consumer_safe_warning: '工程补数队列；当前不是决策级证据，不生成交易指令。',
          },
          {
            family_key: 'stock_quote_spine',
            family_label: 'Stock Quote Spine',
            priority: 'high',
            priority_reason: '高优先级队列：影响 2 个产品面，1 项能力阻断或降级；当前行动为 补齐报价骨架集成。',
            readiness_state: 'partial',
            primary_blocker_type: 'provider-integration',
            affected_surface_count: 2,
            blocked_or_degraded_capability_count: 1,
            external_entitlement_required: false,
            protected_domain_review_required: true,
            next_concrete_step: '定义报价/OHLCV 快照读模型并补齐来源权限字段。',
            required_evidence: ['授权报价快照', '日线 as-of 血缘'],
            consumer_safe_warning: '工程补数队列；当前不是决策级证据，不生成交易指令。',
          },
          {
            family_key: 'news_catalyst_intelligence',
            family_label: 'News / Catalyst Intelligence',
            priority: 'critical',
            priority_reason: '关键队列：影响 2 个产品面，2 项能力阻断或降级；当前行动为 补齐数据契约。',
            readiness_state: 'missing',
            primary_blocker_type: 'schema-contract',
            affected_surface_count: 2,
            blocked_or_degraded_capability_count: 2,
            external_entitlement_required: false,
            protected_domain_review_required: true,
            next_concrete_step: 'Define missing/stale/not_configured states.',
            required_evidence: ['字段契约', '缺失状态定义'],
            consumer_safe_warning: '工程补数队列；当前不是决策级证据，不生成交易指令。',
          },
          {
            family_key: 'macro_rates',
            family_label: 'Macro / Rates',
            priority: 'medium',
            priority_reason: '中优先级队列：影响 1 个产品面，0 项能力阻断或降级；当前行动为 补齐数据集成证据。',
            readiness_state: 'observation-only',
            primary_blocker_type: 'provider-integration',
            affected_surface_count: 1,
            blocked_or_degraded_capability_count: 0,
            external_entitlement_required: false,
            protected_domain_review_required: true,
            next_concrete_step: '持久化官方宏观序列并附覆盖和时效状态。',
            required_evidence: ['覆盖证据'],
            consumer_safe_warning: '工程补数队列；当前不是决策级证据，不生成交易指令。',
          },
          {
            family_key: 'ready_family',
            family_label: 'Ready Family',
            priority: 'low',
            priority_reason: '低优先级监控：影响 1 个产品面，0 项能力阻断或降级；当前行动为 保持证据监控。',
            readiness_state: 'ready',
            primary_blocker_type: 'unknown',
            affected_surface_count: 1,
            blocked_or_degraded_capability_count: 0,
            external_entitlement_required: false,
            protected_domain_review_required: false,
            next_concrete_step: '保持只读监控，不新增阻断行动。',
            required_evidence: ['周期性 freshness 检查'],
            consumer_safe_warning: '当前家族已就绪，仅保留工程监控。',
          },
        ],
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
            integration_action_plan: [
              {
                action_key: 'stock_quote_spine.provider_integration',
                action_label: '补齐报价骨架集成',
                action_type: 'provider-integration',
                priority: 'high',
                status: 'ready-to-start',
                reason: '报价和日线血缘尚未统一。',
                required_evidence: ['授权报价快照', '日线 as-of 血缘'],
                blocked_by: ['持久化快照缺口'],
                affected_surfaces_or_capabilities: ['Watchlist 行级价格', 'Portfolio 估值'],
                next_concrete_step: '定义报价/OHLCV 快照读模型并补齐来源权限字段。',
                requires_external_provider_license_work: false,
                requires_protected_domain_review: true,
              },
              {
                action_key: 'stock_quote_spine.evidence_validation',
                action_label: '验证报价血缘证据',
                action_type: 'evidence-validation',
                priority: 'high',
                status: 'waiting-evidence',
                reason: '需要证明来源权限、时效和覆盖范围。',
                required_evidence: ['覆盖率摘要', 'freshness evidence'],
                blocked_by: ['目标环境证据未齐'],
                affected_surfaces_or_capabilities: ['Scanner 候选解释'],
                next_concrete_step: '在目标环境采集脱敏覆盖和时效证据。',
                requires_external_provider_license_work: false,
                requires_protected_domain_review: true,
              },
            ],
          },
          {
            family_key: 'news_catalyst_intelligence',
            consumer_label: 'News / Catalyst Intelligence',
            status: 'missing',
            authority_state: 'not_configured',
            freshness_state: 'unavailable',
            entitlement_or_licensing_blocker: null,
            integration_blocker: 'No approved news or catalyst layer is configured.',
            source_evidence_state: 'not_configured',
            next_integration_step: 'Define a provider-neutral capability map.',
            provider_hydration_allowed: false,
            score_trading_authority_allowed: false,
            consumer_safe_description: 'News and catalyst inputs are missing.',
            capability_map: [
              {
                capability_key: 'stock_news',
                consumer_label: 'Stock news readiness',
                state: 'not_configured',
                freshness_state: 'unavailable',
                scope: 'stock',
                evidence_state: 'no_provider_or_cache',
                missing_reason: 'No stock news data layer is configured.',
                operator_next_action: 'Define the stock-news read contract before connecting data.',
              },
              {
                capability_key: 'market_news',
                consumer_label: 'Market news readiness',
                state: 'missing',
                freshness_state: 'unavailable',
                scope: 'market',
                evidence_state: 'no_curated_market_news_feed',
                missing_reason: 'No market news feed is attached.',
                operator_next_action: 'Add a market-news capability contract.',
              },
              {
                capability_key: 'earnings_calendar',
                consumer_label: 'Earnings/calendar readiness',
                state: 'missing',
                freshness_state: 'unavailable',
                scope: 'calendar',
                evidence_state: 'sample_or_scaffold_only',
                missing_reason: 'Existing helpers are sample-bounded.',
                operator_next_action: 'Promote only a verified calendar read model.',
              },
              {
                capability_key: 'macro_policy_catalyst',
                consumer_label: 'Macro/policy catalyst readiness',
                state: 'stale',
                freshness_state: 'stale',
                scope: 'macro_policy',
                evidence_state: 'static_or_observation_only',
                missing_reason: 'Policy event feed is not fresh.',
                operator_next_action: 'Attach a durable policy-event snapshot contract.',
              },
            ],
            surface_impact_matrix: [
              {
                surface_key: 'stock_detail',
                consumer_label: 'Stock Detail',
                impact_state: 'blocked',
                impact_reason: 'Stock pages must show missing news data.',
                affected_capability: 'Stock news and catalysts readiness',
                next_evidence_step: 'Add stock news readiness states.',
              },
              {
                surface_key: 'market_overview',
                consumer_label: 'Market Overview',
                impact_state: 'blocked',
                impact_reason: 'Market overview must not imply current market news.',
                affected_capability: 'Market news and policy catalysts readiness',
                next_evidence_step: 'Add event snapshot readiness.',
              },
            ],
            integration_action_plan: [
              {
                action_key: 'news_catalyst_intelligence.schema_contract',
                action_label: '补齐数据契约',
                action_type: 'schema-contract',
                priority: 'high',
                status: 'planned',
                reason: 'News/catalyst readiness contract is missing.',
                required_evidence: ['字段契约', '缺失状态定义'],
                blocked_by: ['contract missing'],
                affected_surfaces_or_capabilities: ['Stock news and catalysts readiness'],
                next_concrete_step: 'Define missing/stale/not_configured states.',
                requires_external_provider_license_work: false,
                requires_protected_domain_review: true,
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
            integration_action_plan: [
              {
                action_key: 'options_chains.provider_entitlement',
                action_label: '确认期权链授权',
                action_type: 'provider-entitlement',
                priority: 'critical',
                status: 'waiting-entitlement',
                reason: '期权链访问、展示、存储和使用权尚未证明。',
                required_evidence: ['授权证明', '字段覆盖清单'],
                blocked_by: ['权益证明缺失'],
                affected_surfaces_or_capabilities: ['Options Lab 链观察'],
                next_concrete_step: '收集授权与字段覆盖证据，不接入数据源运行链路。',
                requires_external_provider_license_work: true,
                requires_protected_domain_review: true,
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
    expect(view.summary.totalFamilies).toBe(5);
    expect(view.groups.map((group) => [group.groupId, group.groupLabel, group.families.length])).toEqual([
      ['quote_market', '报价 / 市场骨架', 1],
      ['news_catalyst', '新闻 / 催化', 1],
      ['options', '期权与衍生结构', 2],
      ['macro_liquidity_credit', '宏观 / 流动性 / 信用', 1],
      ['backtest_research', '回测 / 研究血缘', 0],
      ['scenario', '情景基线', 0],
      ['portfolio', '组合估值', 0],
      ['positioning_flows', '持仓 / 资金流', 0],
    ]);
    expect(view.families.map((family) => [family.familyKey, family.familyLabel, family.status.label])).toEqual([
      ['stock_quote_spine', '股票报价骨架', '部分可用'],
      ['news_catalyst_intelligence', 'News / Catalyst Intelligence', '待补证'],
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
    const newsCapabilityFamily = view.families.find((family) => family.familyKey === 'news_catalyst_intelligence');
    expect(newsCapabilityFamily).toMatchObject({
      groupId: 'news_catalyst',
      groupLabel: '新闻 / 催化',
      status: { label: '待补证', variant: 'caution' },
      authorityState: { label: '待补证', variant: 'caution' },
      freshnessState: { label: '不可用', variant: 'danger' },
      dataHydrationAllowed: '不允许',
      scoreTradingAuthorityAllowed: '不允许',
    });
    expect(newsCapabilityFamily?.capabilityMap.map((item) => [item.capabilityKey, item.state, item.freshnessState])).toEqual([
      ['stock_news', 'not_configured', 'unavailable'],
      ['market_news', 'missing', 'unavailable'],
      ['earnings_calendar', 'missing', 'unavailable'],
      ['macro_policy_catalyst', 'stale', 'stale'],
    ]);
    expect(newsCapabilityFamily?.surfaceImpactMatrix.map((item) => [item.surfaceKey, item.impactState.label])).toEqual([
      ['stock_detail', '阻断'],
      ['market_overview', '阻断'],
    ]);
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
    expect(view.families.find((family) => family.familyKey === 'stock_quote_spine')?.integrationActionPlan[0]).toMatchObject(
      {
        actionKey: 'stock_quote_spine.provider_integration',
        actionLabel: '补齐报价骨架集成',
        actionType: { label: 'Provider integration', variant: 'info' },
        priority: { label: '高', variant: 'caution' },
        status: { label: '可开始', variant: 'info' },
        requiredEvidence: ['授权报价快照', '日线 as-of 血缘'],
        blockedBy: ['持久化快照缺口'],
        affectedSurfacesOrCapabilities: ['Watchlist 行级价格', 'Portfolio 估值'],
        externalProviderLicenseWork: '不需要外部授权',
        protectedDomainReview: '需要保护域复核',
      },
    );
    expect(view.families.find((family) => family.familyKey === 'options_chains')?.integrationActionPlan[0]).toMatchObject({
      actionType: { label: 'Provider entitlement', variant: 'danger' },
      priority: { label: '关键', variant: 'danger' },
      status: { label: '等待授权', variant: 'danger' },
      externalProviderLicenseWork: '需要外部授权',
      protectedDomainReview: '需要保护域复核',
    });
    expect(view.families.find((family) => family.familyKey === 'options_chains')?.scoreTradingAuthorityAllowed).toBe('不允许');
    expect(view.families.find((family) => family.familyKey === 'options_chains')?.surfaceImpactMatrix[0].impactState.label).toBe('阻断');
    expect(view.families.find((family) => family.familyKey === 'gamma_dealer_positioning')?.dataHydrationAllowed).toBe('不允许');
    expect(view.families.find((family) => family.familyKey === 'gamma_dealer_positioning')?.surfaceImpactMatrix[0].impactState.label).toBe('待补证');
    expect(view.acquisitionPriorityQueue.map((item) => item.priority.label)).toEqual([
      '关键',
      '高',
      '关键',
      '中',
      '低',
    ]);
    expect(view.acquisitionPriorityQueue[0]).toMatchObject({
      familyKey: 'options_chains',
      familyLabel: '期权链',
      primaryBlockerType: { label: '授权阻断', variant: 'danger' },
      readinessState: { label: '未授权', variant: 'danger' },
      affectedSurfaceCount: 1,
      blockedOrDegradedCapabilityCount: 1,
      externalEntitlementRequired: '需要外部授权',
      protectedDomainReviewRequired: '需要保护域复核',
      requiredEvidence: ['授权证明', '字段覆盖清单'],
    });
    expect(view.acquisitionPriorityQueue[1]).toMatchObject({
      familyKey: 'stock_quote_spine',
      primaryBlockerType: { label: '数据接入', variant: 'info' },
      priorityReason: '高优先级队列：影响 2 个产品面，1 项能力阻断或降级；当前行动为 补齐报价骨架集成。',
      nextConcreteStep: '定义报价/OHLCV 快照读模型并补齐来源权限字段。',
    });
    expect(view.acquisitionPriorityQueue[2]).toMatchObject({
      familyKey: 'news_catalyst_intelligence',
      primaryBlockerType: { label: '契约补齐', variant: 'caution' },
      readinessState: { label: '待补证', variant: 'caution' },
      nextConcreteStep: 'Define missing/stale/not_configured states.',
    });
    expect(view.workbench.blockedMissingPartialFamilyCount).toBe(3);
    expect(view.workbench.urgentQueueCount).toBe(4);
    expect(view.workbench.blockerTypeCounts).toEqual(expect.arrayContaining([
      expect.objectContaining({ key: 'entitlement', label: '授权阻断', count: 1 }),
      expect.objectContaining({ key: 'provider-integration', label: '数据接入', count: 2 }),
      expect.objectContaining({ key: 'schema-contract', label: '契约补齐', count: 1 }),
      expect.objectContaining({ key: 'unknown', label: '阻断待确认', count: 0 }),
    ]));
    expect(view.workbench.priorityCounts).toEqual(expect.arrayContaining([
      expect.objectContaining({ key: 'critical', label: '关键', count: 2 }),
      expect.objectContaining({ key: 'high', label: '高', count: 1 }),
      expect.objectContaining({ key: 'medium', label: '中', count: 1 }),
    ]));
    expect(view.workbench.topNextActions.map((item) => item.familyKey)).toEqual([
      'news_catalyst_intelligence',
      'options_chains',
      'stock_quote_spine',
    ]);
    expect(view.workbench.topNextActions[0]).toMatchObject({
      familyKey: 'news_catalyst_intelligence',
      priorityKey: 'critical',
      affectedSurfaceCount: 2,
      nextConcreteStep: 'Define missing/stale/not_configured states.',
    });
    expect(view.workbench.lanes.find((lane) => lane.key === 'protected-review')?.items.map((item) => item.familyKey)).toEqual([
      'news_catalyst_intelligence',
      'options_chains',
      'stock_quote_spine',
      'macro_rates',
    ]);
    expect(view.workbench.lanes.find((lane) => lane.key === 'external-entitlement')?.items.map((item) => item.familyKey)).toEqual([
      'options_chains',
    ]);
    expect(view.workbench.lanes.find((lane) => lane.key === 'evidence-validation')?.items.map((item) => item.familyKey)).toEqual([
      'stock_quote_spine',
    ]);
    expect(view.workbench.topNextActions.map((item) => item.familyKey)).not.toContain('ready_family');
    expect(JSON.stringify(view.workbench)).not.toMatch(/ready_family|requestId|traceId|rawProviderPayload|cacheKey|credential|env|debug|buy|sell|hold|target price|stop loss|position sizing|买入|卖出|目标价|止损|仓位|推荐|最佳|最优|赢家|fake headline|breaking news|latest news/i);
    expect(JSON.stringify(view)).not.toMatch(/requestId|traceId|rawProviderPayload|cacheKey|credential|env|debug|api[_-]?key|buy|sell|target price|stop loss|position sizing|买入|卖出|目标价|止损|仓位|fake headline|breaking news|latest news/i);
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
            integration_action_plan: [
              {
                action_key: 'rawProviderPayload requestId',
                action_label: 'debug cacheKey action',
                action_type: 'provider-integration',
                priority: 'critical',
                status: 'ready-to-start',
                reason: 'traceId raw dump',
                required_evidence: ['api_key secret evidence'],
                blocked_by: ['cookie blocker'],
                affected_surfaces_or_capabilities: ['debug surface'],
                next_concrete_step: 'token=secret next step',
                requires_external_provider_license_work: true,
                requires_protected_domain_review: true,
              },
            ],
          },
        ],
        acquisition_priority_queue: [
          {
            family_key: 'unknown_new_family',
            family_label: 'Unknown New Family',
            priority_reason: 'rawProviderPayload requestId traceId',
            primary_blocker_type: 'provider-integration',
            next_concrete_step: 'token=secret next step',
            required_evidence: ['api_key secret evidence'],
            consumer_safe_warning: 'debug raw dump',
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
    expect(family.integrationActionPlan).toMatchObject([
      {
        actionKey: 'unknown_new_family.manual_review',
        actionLabel: '行动项待复核',
        actionType: { label: 'Manual review', variant: 'neutral' },
        priority: { label: '中', variant: 'info' },
        status: { label: '计划中', variant: 'neutral' },
        reason: '原因待补证。',
        requiredEvidence: ['证据待补证'],
        blockedBy: ['阻断项待补证'],
        affectedSurfacesOrCapabilities: ['影响面待补证'],
        nextConcreteStep: '下一步待补证。',
      },
    ]);
    expect(view.acquisitionPriorityQueue).toMatchObject([
      {
        familyKey: 'unknown_new_family',
        familyLabel: 'Unknown New Family',
        priority: { label: '中', variant: 'info' },
        readinessState: { label: '待补证', variant: 'caution' },
        primaryBlockerType: { label: '数据接入', variant: 'info' },
        affectedSurfaceCount: 0,
        blockedOrDegradedCapabilityCount: 0,
        nextConcreteStep: '下一步待补证。',
        requiredEvidence: ['证据待补证'],
        consumerSafeWarning: '工程补数队列；当前不是决策级证据。',
      },
    ]);
    expect(view.groups.find((group) => group.groupId === 'other')?.families[0]?.familyKey).toBe('unknown_new_family');
    expect(JSON.stringify(view)).not.toMatch(/已就绪|已解锁|权限 可用|新鲜|requestId|traceId|rawProviderPayload|cacheKey|token|secret|debug/i);
  });
});
