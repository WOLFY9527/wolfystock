import { beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from '../index';
import { buildAlpacaQuoteAuthorityReadinessView, marketRotationApi } from '../marketRotation';

vi.mock('../index', () => ({
  default: {
    get: vi.fn(),
  },
}));

describe('marketRotationApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('normalizes Alpaca quote authority readiness into consumer-facing labels', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: {
        endpoint: '/api/v1/market/rotation-radar',
        generated_at: '2026-05-07T09:50:00Z',
        source: 'computed',
        freshness: 'delayed',
        is_fallback: false,
        is_stale: false,
        no_advice_disclosure: '仅用于观察资金轮动迹象，非买卖建议。',
        metadata: {
          no_external_calls: true,
        },
        benchmarks: {},
        etf_leadership_diagnostics: {
          enabled: false,
          evidence: [],
        },
        summary: {
          strongest_themes: [],
          accelerating_themes: [],
          fading_themes: [],
          watchlist_signals: [],
          safe_wording: [],
        },
        themes: [],
        alpaca_quote_authority_readiness: {
          provider_configured: false,
          source_authority: 'unavailable',
          fallback_used: true,
          score_contribution_allowed: false,
          quote_coverage_by_family: [
            {
              family_id: 'broad_us_market',
              family_label: 'Broad US market',
              configured_symbols: ['SPY', 'QQQ', 'IWM'],
              available_symbols: ['SPY', 'QQQ'],
              missing_symbols: ['IWM'],
              stale_symbols: [],
              observation_only_symbols: ['IWM'],
              configured_count: 3,
              available_count: 2,
              missing_count: 1,
              stale_count: 0,
              score_authority_allowed_count: 0,
              observation_only_count: 3,
              fallback_or_limited_sample_used: true,
              symbols: [
                {
                  symbol: 'SPY',
                  configured: true,
                  quote_available: true,
                  missing: false,
                  stale: false,
                  source_authority_allowed: false,
                  score_contribution_allowed: false,
                  fallback_or_limited_sample_used: true,
                  source_family: 'configured_provider',
                  provider_class: 'configured_quote',
                },
              ],
            },
          ],
        },
      },
    } as never);

    const payload = await marketRotationApi.getRotationRadar();
    const view = buildAlpacaQuoteAuthorityReadinessView(payload.alpacaQuoteAuthorityReadiness);

    expect(payload.alpacaQuoteAuthorityReadiness?.providerConfigured).toBe(false);
    expect(payload.alpacaQuoteAuthorityReadiness?.sourceAuthority).toBe('unavailable');
    expect(payload.alpacaQuoteAuthorityReadiness?.fallbackUsed).toBe(true);
    expect(payload.alpacaQuoteAuthorityReadiness?.quoteCoverageByFamily?.[0]).toMatchObject({
      familyId: 'broad_us_market',
      configuredSymbols: ['SPY', 'QQQ', 'IWM'],
      availableSymbols: ['SPY', 'QQQ'],
      missingSymbols: ['IWM'],
      observationOnlySymbols: ['IWM'],
      scoreAuthorityAllowedCount: 0,
      fallbackOrLimitedSampleUsed: true,
    });
    expect(payload.alpacaQuoteAuthorityReadiness?.quoteCoverageByFamily?.[0]?.symbols?.[0]).toMatchObject({
      symbol: 'SPY',
      quoteAvailable: true,
      sourceAuthorityAllowed: false,
      scoreContributionAllowed: false,
      sourceFamily: 'configured_provider',
      providerClass: 'configured_quote',
    });
    expect(view.label).toBe('ETF引用待补');
    expect(view.chips.map((chip) => chip.label)).toEqual(['ETF引用待补', '备用样本观察', '仅观察']);
    expect(`${view.label} ${view.detail} ${view.chips.map((chip) => chip.label).join(' ')}`).not.toMatch(
      /Alpaca部分可用|Alpaca待配置|Alpaca可用|Alpaca未配置|回退观察/,
    );
    expect(`${view.label} ${view.detail}`).not.toMatch(
      /authorized|unavailable|partial|unknown|fallbackUsed|providerConfigured|sourceAuthority|scoreContributionAllowed|provider|runtime|credential/i,
    );
  });

  it('loads and normalizes the rotation radar response without raw provider details', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: {
        endpoint: '/api/v1/market/rotation-radar',
        generated_at: '2026-05-07T09:50:00Z',
        source: 'computed',
        source_label: '主题篮子计算',
        freshness: 'delayed',
        is_fallback: false,
        is_stale: false,
        no_advice_disclosure: '仅用于观察资金轮动迹象，非买卖建议。',
        metadata: {
          no_external_calls: true,
          schema_version: 'market_rotation_radar_phase4_v1',
          time_windows: ['5m', '15m', '60m', '1d'],
          proxy_quality_required: true,
          alerts_are_read_only_evidence: true,
          notification_delivery_enabled: false,
        },
        benchmarks: {
          QQQ: {
            symbol: 'QQQ',
            change_percent: 0.8,
            time_windows: {
              '1d': { window: '1d', label: '日内/日线', available: true, change_percent: 0.8, freshness: 'delayed', is_fallback: false, is_stale: false },
            },
            freshness: 'delayed',
            is_fallback: false,
            is_stale: false,
          },
        },
        etf_leadership_diagnostics: {
          enabled: true,
          source: 'alpaca_etf_authority_spine',
          as_of: '2026-05-07T09:45:00Z',
          eligible_symbols: ['SPY', 'QQQ', 'IWM', 'SMH', 'SOXX', 'IGV'],
          leading_symbols: ['SMH', 'SOXX', 'QQQ'],
          lagging_symbols: ['IWM', 'IGV', 'SPY'],
          leadership_spread: 1.24,
          confidence_label: 'high',
          reason_codes: ['bounded_etf_authority_active'],
          evidence: [
            {
              symbol: 'SMH',
              source_label: 'Alpaca SIP',
              freshness: 'live',
              source_authority_allowed: true,
              score_contribution_allowed: true,
              reason_codes: [],
            },
            {
              symbol: 'SPY',
              source_label: 'Alpaca SIP',
              freshness: 'live',
              source_authority_allowed: true,
              score_contribution_allowed: true,
              reason_codes: [],
            },
          ],
        },
        summary: {
          strongest_themes: [
            {
              id: 'ai_applications',
              name: 'AI 应用',
              rotation_score: 78,
              confidence: 0.72,
              stage: 'confirmed_rotation',
              freshness: 'delayed',
              is_fallback: false,
              risk_labels: [],
              signal_type: 'relative_strength',
              flow_evidence_type: 'proxy_only',
              flow_language_allowed: false,
              source_authority_allowed: true,
              evidence_quality: 'degraded_proxy',
              data_gaps: ['true_flow_data_missing', 'flow_methodology_missing'],
              theme_flow_signal: {
                contract_version: 'investor_signal_contract_v1',
                diagnostic_only: true,
                observation_only: true,
                authority_grant: false,
                decision_grade: false,
                source_authority_allowed: false,
                score_contribution_allowed: false,
                market_regime: 'risk_on',
                market_regime_label: '风险偏好回升',
                capital_flow_regime: 'inflow',
                capital_flow_label: '资金净流入观察',
                theme_flow_state: 'leading',
                theme_flow_label: '主线领涨观察',
                confidence_label: 'medium',
                confidence_text: '中',
                freshness: 'cached',
                reason_codes: ['source_authority_missing', 'score_rights_missing'],
                contradiction_codes: [],
                confidence: 0.72,
                is_fallback: false,
                is_stale: false,
                is_partial: false,
                explanation: 'AI leadership still leads the tape.',
              },
            },
          ],
          accelerating_themes: [],
          fading_themes: [],
          observation_themes: [
            {
              id: 'robotics',
              name: '机器人',
              rotation_score: 41,
              confidence: 0.38,
              stage: 'early_watch',
              freshness: 'fallback',
              is_fallback: true,
              risk_labels: ['stale_or_incomplete_windows'],
              signal_type: 'observation_only',
            },
          ],
          taxonomy_themes: [
            {
              id: 'local_taxonomy',
              name: '本地主题观察',
              rotation_score: 18,
              confidence: 0.12,
              stage: 'weak_or_no_signal',
              freshness: 'fallback',
              is_fallback: true,
              risk_labels: ['stale_or_incomplete_windows'],
              signal_type: 'taxonomy_fallback',
            },
          ],
          eligible_theme_count: 3,
          headline_eligible_theme_count: 1,
          observation_theme_count: 1,
          headline_warning: '当前头部主题仅满足代理证据，不代表真实资金流。',
          no_headline_reason: '等待真实行情覆盖后再生成头部排名。',
          ranking_policy: '仅 headlineEligible 主题参与头部排序；observation/taxonomy 仅作说明。',
          rotation_family_rollup: [
            {
              family_id: 'ai',
              family_name: 'AI',
              theme_ids: ['ai_applications'],
              theme_names: ['AI 应用'],
              leader_theme_ids: ['ai_applications'],
              theme_count: 1,
              signal_theme_count: 1,
              average_rotation_score: 78,
              average_confidence: 0.72,
              theme_flow_signal: {
                contract_version: 'investor_signal_contract_v1',
                diagnostic_only: true,
                observation_only: true,
                authority_grant: false,
                decision_grade: false,
                source_authority_allowed: false,
                score_contribution_allowed: false,
                market_regime: 'risk_on',
                market_regime_label: '风险偏好回升',
                capital_flow_regime: 'inflow',
                capital_flow_label: '资金净流入观察',
                theme_flow_state: 'leading',
                theme_flow_label: '主线领涨观察',
                confidence_label: 'medium',
                confidence_text: '中',
                freshness: 'fallback',
                reason_codes: ['source_authority_missing', 'score_rights_missing'],
                contradiction_codes: [],
                confidence: 0.72,
                is_fallback: true,
                is_stale: false,
                is_partial: false,
                explanation: 'AI leadership still leads the tape.',
              },
            },
          ],
          watchlist_signals: [
            { theme_id: 'ai_applications', symbol: 'APP', label: '关注候选', signal: 'confirmed_rotation', signal_label: '确认轮动', read_only: true, delivery_enabled: false },
          ],
          safe_wording: ['资金轮动迹象', '非买卖建议'],
        },
        consumer_evidence_snapshot: {
          market: 'US',
          generated_at: '2026-05-07T09:50:00Z',
          freshness: 'partial',
          is_fallback: false,
          is_stale: false,
          is_partial: true,
          headline_eligible_theme_count: 1,
          observation_theme_count: 1,
          taxonomy_theme_count: 1,
          score_contribution_allowed: false,
          reason_codes: ['partial_source'],
          provider_state: {
            present: true,
            status: 'partial',
            source_type: 'proxy_bundle',
            source_tier: 'public_proxy',
            provider_tier: 'mixed',
            freshness: 'partial',
            source_authority_allowed: false,
            score_contribution_allowed: false,
            no_external_calls: true,
          },
          etf_proxy_summary: {
            present: true,
            proxy_only: true,
            fund_flow_authority_allowed: false,
            enabled: true,
            source: 'alpaca_etf_authority_spine',
            reason_codes: ['bounded_etf_authority_active'],
          },
          themes: [
            {
              id: 'ai_applications',
              name: 'AI 应用',
              rank_eligible: true,
              headline_eligible: true,
              ranking_lane: 'headline',
              observation_only: false,
              taxonomy_only: false,
              score_contribution_allowed: true,
              freshness: 'delayed',
              is_fallback: false,
              is_stale: false,
              is_partial: false,
              evidence_quality: 'degraded_proxy',
              data_gaps: ['true_flow_data_missing'],
            },
          ],
          rotation_family_rollup: [
            {
              family_id: 'ai',
              family_name: 'AI',
              theme_ids: ['ai_applications'],
              theme_names: ['AI 应用'],
              leader_theme_ids: ['ai_applications'],
              theme_count: 1,
              signal_theme_count: 1,
              average_rotation_score: 78,
              average_confidence: 0.72,
              theme_flow_signal: {
                theme_flow_state: 'leading',
                freshness: 'fallback',
              },
            },
          ],
        },
        themes: [
          {
            id: 'ai_applications',
            name: 'AI 应用',
            english_name: 'AI Applications',
            rotation_score: 78,
            sector_benchmark: 'IGV',
            confidence: 0.72,
            stage: 'confirmed_rotation',
            stage_explanation: '价格、量能、广度和同步性同时满足阈值。置信度 72%，分钟级时窗待补齐。',
            risk_labels: [],
            risk_explanations: [],
            newsless_rotation: true,
            persistence_score: 0.78,
            persistence_evidence: {
              score: 0.78,
              label: '跨时窗延续',
              available_windows: ['5m', '15m', '60m', '1d'],
              missing_windows: [],
              stale_or_fallback_windows: [],
              explanation: '跨时窗延续：可用 5m/15m/60m/1d，缺失 无，备用/过期 无。',
            },
            alert_candidates: [
              {
                theme_id: 'ai_applications',
                theme_name: 'AI 应用',
                symbol: 'APP',
                label: '关注候选',
                signal: 'confirmed_rotation',
                signal_label: '确认轮动',
                confidence: 0.72,
                persistence_score: 0.78,
                read_only: true,
                delivery_enabled: false,
                reasons: ['AI 应用：确认轮动'],
                sort_explanation: '按主题轮动强度、置信度、跨时窗持续证据、成员相对强弱和量能扩张排序；仅用于观察信号排队，非买卖建议。',
              },
            ],
            freshness: 'delayed',
            is_fallback: false,
            is_stale: false,
            signal_type: 'relative_strength',
            flow_evidence_type: 'proxy_only',
            flow_language_allowed: false,
            source_authority_allowed: true,
            evidence_quality: 'degraded_proxy',
            data_gaps: ['true_flow_data_missing', 'flow_methodology_missing'],
            theme_flow_signal: {
              contract_version: 'investor_signal_contract_v1',
              diagnostic_only: true,
              observation_only: true,
              authority_grant: false,
              decision_grade: false,
              source_authority_allowed: false,
              score_contribution_allowed: false,
              market_regime: 'risk_on',
              market_regime_label: '风险偏好回升',
              capital_flow_regime: 'inflow',
              capital_flow_label: '资金净流入观察',
              theme_flow_state: 'leading',
              theme_flow_label: '主线领涨观察',
              confidence_label: 'medium',
              confidence_text: '中',
              freshness: 'cached',
              reason_codes: ['source_authority_missing', 'score_rights_missing'],
              contradiction_codes: [],
              confidence: 0.72,
              is_fallback: false,
              is_stale: false,
              is_partial: false,
              explanation: 'AI leadership still leads the tape.',
            },
            evidence: ['无明显新闻的同步异动'],
            relative_strength: { average_relative_strength_percent: 2.6 },
            proxy_quality: {
              label: 'ETF 代理完整',
              coverage_percent: 100,
              available_proxy_count: 4,
              total_proxy_count: 4,
              required_proxies: ['QQQ', 'SPY', 'IWM', 'IGV'],
              freshness: 'delayed',
              has_missing_required_proxy: false,
              has_stale_proxy: false,
              missing_reasons: {},
              explanation: 'ETF 代理完整：ETF 代理覆盖 4/4，缺口 无。',
            },
            benchmark_proxies: {
              IGV: {
                symbol: 'IGV',
                role: 'sector_proxy',
                relative_strength: 2.2,
                freshness: 'delayed',
                is_fallback: false,
                is_stale: false,
                quality: {
                  symbol: 'IGV',
                  available: true,
                  freshness: 'delayed',
                  is_fallback: false,
                  is_stale: false,
                  has_required_windows: true,
                  missing_reason: null,
                  quality_label: '可用代理',
                  coverage_contribution: 1,
                },
              },
            },
            time_windows: {
              '5m': { window: '5m', label: '5分钟', available: false, freshness: 'fallback', is_fallback: true, is_stale: false, reason: 'window_unavailable' },
              '15m': { window: '15m', label: '15分钟', available: false, freshness: 'fallback', is_fallback: true, is_stale: false, reason: 'window_unavailable' },
              '60m': { window: '60m', label: '60分钟', available: false, freshness: 'fallback', is_fallback: true, is_stale: false, reason: 'window_unavailable' },
              '1d': { window: '1d', label: '日内/日线', available: true, change_percent: 3.2, freshness: 'delayed', is_fallback: false, is_stale: false },
            },
            volume: { average_relative_volume: 1.8 },
            breadth: { percent_up: 88, percent_outperforming_benchmark: 88 },
            synchronization: { same_direction_percent: 88 },
            leadership: { top_members: [{ symbol: 'APP', name: 'APP', change_percent: 5.1 }] },
            theme_correlation_breadth_snapshot: {
              contract_version: 'theme_correlation_breadth_snapshot_v1',
              theme: { id: 'ai_applications', name: 'AI 应用', market: 'US' },
              participation_state: 'broad_group',
              leadership_concentration: {
                state: 'balanced',
                percent: 36,
                broad_participation_percent: 64,
                top_members: ['APP', 'PLTR'],
              },
              correlation_evidence: {
                state: 'aligned',
                same_direction_percent: 88,
                above_vwap_percent: 82,
                persistence_percent: 76,
              },
              breadth_evidence: {
                state: 'broad',
                observed_members: 3,
                configured_members: 3,
                coverage_percent: 100,
                percent_up: 88,
                percent_outperforming_benchmark: 88,
              },
              stale_inputs: [],
              missing_inputs: [],
              observation_boundary: {
                scope: 'existing_theme_fields',
                ranking_impact: 'none',
                data_mutation: 'none',
                data_fetches: 'none',
              },
              research_next_steps: ['Watch whether broad participation persists across the next observation window.'],
            },
            theme_detail: { watchlist_safe: true, safe_action_label: '仅观察，不构成买卖建议' },
            members: [],
            no_advice_disclosure: '仅用于观察资金轮动迹象，非买卖建议。',
          },
        ],
      },
    } as never);

    const payload = await marketRotationApi.getRotationRadar();

    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/market/rotation-radar');
    expect(payload.generatedAt).toBe('2026-05-07T09:50:00Z');
    expect(payload.metadata.noExternalCalls).toBe(true);
    expect(payload.metadata.proxyQualityRequired).toBe(true);
    expect(payload.summary.strongestThemes[0].rotationScore).toBe(78);
    expect(payload.summary.strongestThemes[0].signalType).toBe('relative_strength');
    expect(payload.summary.observationThemes).toHaveLength(1);
    expect(payload.summary.observationThemes?.[0].signalType).toBe('observation_only');
    expect(payload.summary.taxonomyThemes).toHaveLength(1);
    expect(payload.summary.taxonomyThemes?.[0].signalType).toBe('taxonomy_fallback');
    expect(payload.summary.eligibleThemeCount).toBe(3);
    expect(payload.summary.headlineEligibleThemeCount).toBe(1);
    expect(payload.summary.observationThemeCount).toBe(1);
    expect(payload.summary.strongestThemes[0].themeFlowSignal?.themeFlowState).toBe('leading');
    expect(payload.summary.rotationFamilyRollup?.[0].familyId).toBe('ai');
    expect(payload.summary.rotationFamilyRollup?.[0].themeFlowSignal?.freshness).toBe('fallback');
    expect(payload.etfLeadershipDiagnostics.enabled).toBe(true);
    expect(payload.etfLeadershipDiagnostics.source).toBe('alpaca_etf_authority_spine');
    expect(payload.etfLeadershipDiagnostics.leadingSymbols).toEqual(['SMH', 'SOXX', 'QQQ']);
    expect(payload.etfLeadershipDiagnostics.laggingSymbols).toEqual(['IWM', 'IGV', 'SPY']);
    expect(payload.consumerEvidenceSnapshot?.freshness).toBe('partial');
    expect(payload.consumerEvidenceSnapshot?.rotationFamilyRollup[0].themeFlowSignal?.themeFlowState).toBe('leading');
    expect(payload.consumerEvidenceSnapshot?.providerState.sourceType).toBe('proxy_bundle');
    expect(payload.etfLeadershipDiagnostics.evidence[0]).toMatchObject({
      symbol: 'SMH',
      sourceLabel: 'Alpaca SIP',
      freshness: 'live',
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: true,
      reasonCodes: [],
    });
    expect(payload.summary.headlineWarning).toBe('当前头部主题仅满足代理证据，不代表真实资金流。');
    expect(payload.summary.noHeadlineReason).toBe('等待真实行情覆盖后再生成头部排名。');
    expect(payload.summary.rankingPolicy).toBe('仅 headlineEligible 主题参与头部排序；observation/taxonomy 仅作说明。');
    expect(payload.themes[0].englishName).toBe('AI Applications');
    expect(payload.themes[0].newslessRotation).toBe(true);
    expect(payload.themes[0].flowEvidenceType).toBe('proxy_only');
    expect(payload.themes[0].flowLanguageAllowed).toBe(false);
    expect(payload.themes[0].sourceAuthorityAllowed).toBe(true);
    expect(payload.themes[0].evidenceQuality).toBe('degraded_proxy');
    expect(payload.themes[0].dataGaps).toContain('true_flow_data_missing');
    expect(payload.themes[0].persistenceEvidence?.label).toBe('跨时窗延续');
    expect(payload.themes[0].themeFlowSignal?.themeFlowState).toBe('leading');
    expect(payload.themes[0].themeFlowSignal?.freshness).toBe('cached');
    expect(payload.themes[0].themeCorrelationBreadthSnapshot).toMatchObject({
      participationState: 'broad_group',
      leadershipConcentration: {
        state: 'balanced',
        percent: 36,
        broadParticipationPercent: 64,
        topMembers: ['APP', 'PLTR'],
      },
      correlationEvidence: {
        state: 'aligned',
        sameDirectionPercent: 88,
        aboveVwapPercent: 82,
        persistencePercent: 76,
      },
      breadthEvidence: {
        state: 'broad',
        observedMembers: 3,
        configuredMembers: 3,
        coveragePercent: 100,
        percentUp: 88,
        percentOutperformingBenchmark: 88,
      },
      staleInputs: [],
      missingInputs: [],
      observationBoundary: {
        scope: 'existing_theme_fields',
        rankingImpact: 'none',
        dataMutation: 'none',
        dataFetches: 'none',
      },
    });
    expect(payload.themes[0].themeCorrelationBreadthSnapshot?.researchNextSteps).toEqual([
      'Watch whether broad participation persists across the next observation window.',
    ]);
    expect(payload.themes[0].alertCandidates?.[0].readOnly).toBe(true);
    expect(payload.themes[0].alertCandidates?.[0].sortExplanation).toContain('非买卖建议');
    expect(payload.summary.watchlistSignals[0].label).toBe('关注候选');
    expect(payload.themes[0].timeWindows?.['1d'].available).toBe(true);
    expect(payload.themes[0].proxyQuality?.coveragePercent).toBe(100);
    expect(payload.themes[0].benchmarkProxies?.IGV.quality?.missingReason).toBeNull();
    expect(payload.themes[0].benchmarkProxies?.IGV.role).toBe('sector_proxy');
    expect(payload.themes[0].themeDetail?.watchlistSafe).toBe(true);
    expect(JSON.stringify(payload).toLowerCase()).not.toContain('raw_payload');
  });

  it('passes an optional market query when loading radar taxonomy', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: {
        endpoint: '/api/v1/market/rotation-radar',
        market: 'CN',
        supported_markets: ['US', 'CN', 'HK', 'CRYPTO'],
        generated_at: '2026-05-07T09:50:00Z',
        source: 'local_taxonomy',
        source_label: '静态主题库',
        freshness: 'fallback',
        is_fallback: true,
        is_stale: false,
        warning: '当前为静态主题库，本地行情覆盖后可计算轮动强度。',
        no_advice_disclosure: '仅用于观察资金轮动迹象，非买卖建议。',
        metadata: {
          no_external_calls: true,
          taxonomy_only_theme_count: 1,
        },
        etf_leadership_diagnostics: {
          enabled: false,
          source: 'alpaca_etf_authority_spine',
          as_of: '2026-05-07T09:45:00Z',
          eligible_symbols: [],
          leading_symbols: [],
          lagging_symbols: [],
          leadership_spread: null,
          confidence_label: 'disabled',
          reason_codes: ['market_not_supported'],
          evidence: [],
        },
        benchmarks: {},
        summary: {
          strongest_themes: [],
          accelerating_themes: [],
          fading_themes: [],
          watchlist_signals: [],
          safe_wording: ['分类观察', '非买卖建议'],
        },
        themes: [
          {
            id: 'CN:theme_cluster:ai_compute',
            market: 'CN',
            name: 'AI算力',
            english_name: 'AI Compute',
            focus: 'GPU供应链、算力租赁、数据中心与服务器',
            benchmark: 'CN_LOCAL_TAXONOMY',
            sector_benchmark: null,
            members_configured: ['寒武纪', '中科曙光'],
            rotation_score: 18,
            confidence: 0.12,
            confidence_label: '待行情确认',
            data_quality: 'taxonomy_only',
            static_theme_only: true,
            signal_type: 'taxonomy_fallback',
            flow_evidence_type: 'none',
            flow_language_allowed: false,
            source_authority_allowed: false,
            evidence_quality: 'taxonomy_only',
            data_gaps: ['taxonomy_only', 'true_flow_data_missing'],
            stage: 'weak_or_no_signal',
            stage_explanation: '主题库已载入，行情评分待本地数据覆盖，仅作分类观察。',
            risk_labels: ['stale_or_incomplete_windows'],
            risk_explanations: ['行情评分待本地数据覆盖。'],
            newsless_rotation: false,
            freshness: 'fallback',
            is_fallback: true,
            is_stale: false,
            evidence: ['主题库已载入', '行情评分待本地数据覆盖', '仅作分类观察'],
            relative_strength: {},
            time_windows: {},
            volume: {},
            breadth: {},
            synchronization: {},
            leadership: {},
            theme_detail: {
              mapped_concepts: ['算力租赁', '服务器'],
              representative_labels: ['寒武纪', '中科曙光'],
              data_state_label: '待接入本地行情',
              next_step: '本地行情覆盖后可计算轮动强度。',
            },
            members: [],
            no_advice_disclosure: '仅用于观察资金轮动迹象，非买卖建议。',
          },
        ],
      },
    } as never);

    const payload = await marketRotationApi.getRotationRadar('CN');

    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/market/rotation-radar', { params: { market: 'CN' } });
    expect(payload.market).toBe('CN');
    expect(payload.supportedMarkets).toEqual(['US', 'CN', 'HK', 'CRYPTO']);
    expect(payload.etfLeadershipDiagnostics.enabled).toBe(false);
    expect(payload.etfLeadershipDiagnostics.confidenceLabel).toBe('disabled');
    expect(payload.etfLeadershipDiagnostics.reasonCodes).toEqual(['market_not_supported']);
    expect(payload.summary.observationThemes).toBeUndefined();
    expect(payload.summary.taxonomyThemes).toBeUndefined();
    expect(payload.summary.eligibleThemeCount).toBeUndefined();
    expect(payload.summary.headlineEligibleThemeCount).toBeUndefined();
    expect(payload.summary.observationThemeCount).toBeUndefined();
    expect(payload.summary.headlineWarning).toBeUndefined();
    expect(payload.summary.noHeadlineReason).toBeUndefined();
    expect(payload.summary.rankingPolicy).toBeUndefined();
    expect(payload.themes[0].staticThemeOnly).toBe(true);
    expect(payload.themes[0].dataQuality).toBe('taxonomy_only');
    expect(payload.themes[0].confidenceLabel).toBe('待行情确认');
    expect(payload.themes[0].signalType).toBe('taxonomy_fallback');
    expect(payload.themes[0].evidenceQuality).toBe('taxonomy_only');
    expect(payload.themes[0].dataGaps).toContain('taxonomy_only');
    expect(payload.themes[0].themeDetail?.mappedConcepts).toContain('算力租赁');
  });

  it('preserves consumer evidence metadata fields at the frontend boundary', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: {
        endpoint: '/api/v1/market/rotation-radar',
        generated_at: '2026-05-07T10:00:00Z',
        source: 'synthetic_boundary_fixture',
        source_label: 'Synthetic Boundary Fixture',
        freshness: 'unavailable',
        is_fallback: true,
        is_stale: true,
        metadata: {},
        benchmarks: {},
        summary: {
          strongest_themes: [],
          accelerating_themes: [],
          fading_themes: [],
          watchlist_signals: [],
          safe_wording: [],
        },
        themes: [],
        consumer_evidence_snapshot: {
          market: 'US',
          generated_at: '2026-05-07T10:00:00Z',
          as_of: '2026-05-07T09:58:00Z',
          freshness: 'unavailable',
          is_fallback: true,
          is_stale: true,
          is_partial: true,
          authority_grant: false,
          score_contribution_allowed: false,
          reason_codes: ['synthetic_fixture', 'provider_timeout'],
          provider_state: {
            present: true,
            status: 'unavailable',
            quote_mode: 'synthetic',
            source_type: 'synthetic_bundle',
            source_tier: 'synthetic_internal',
            provider_tier: 'degraded_cache',
            freshness: 'unavailable',
            as_of: '2026-05-07T09:58:00Z',
            coverage: {
              requested_symbol_count: 6,
              usable_symbol_count: 0,
              coverage_percent: 0,
            },
            source_authority_allowed: false,
            score_contribution_allowed: false,
            no_external_calls: true,
          },
          etf_proxy_summary: {
            present: true,
            proxy_only: true,
            label: 'Synthetic proxy watch',
            fund_flow_authority_allowed: false,
            enabled: false,
            source: 'synthetic_proxy_pack',
            as_of: '2026-05-07T09:58:00Z',
            eligible_symbol_count: 0,
            leading_symbols: ['QQQ', '', null],
            lagging_symbols: ['IWM', '', null],
            reason_codes: ['synthetic_fixture', 'provider_timeout'],
          },
          themes: [
            {
              id: 'ai_applications',
              name: 'AI 应用',
              rank_eligible: false,
              headline_eligible: false,
              ranking_lane: 'observation',
              observation_only: true,
              taxonomy_only: false,
              score_contribution_allowed: false,
              freshness: 'unavailable',
              is_fallback: true,
              is_stale: true,
              is_partial: true,
              evidence_quality: 'synthetic_only',
              data_gaps: ['synthetic_fixture', 'provider_timeout'],
            },
          ],
          rotation_family_rollup: [
            {
              family_id: 'ai',
              family_name: 'AI',
              theme_ids: ['ai_applications'],
              theme_names: ['AI 应用'],
              leader_theme_ids: ['ai_applications'],
              theme_count: 1,
              signal_theme_count: 0,
              average_rotation_score: null,
              average_confidence: null,
              theme_flow_signal: {
                theme_flow_state: 'unavailable',
                freshness: 'unavailable',
              },
            },
          ],
        },
      },
    } as never);

    const payload = await marketRotationApi.getRotationRadar();

    expect(payload.source).toBe('synthetic_boundary_fixture');
    expect(payload.sourceLabel).toBe('Synthetic Boundary Fixture');
    expect(payload.freshness).toBe('unavailable');
    expect(payload.isFallback).toBe(true);
    expect(payload.isStale).toBe(true);
    expect(payload.consumerEvidenceSnapshot).toMatchObject({
      market: 'US',
      generatedAt: '2026-05-07T10:00:00Z',
      asOf: '2026-05-07T09:58:00Z',
      freshness: 'unavailable',
      isFallback: true,
      isStale: true,
      isPartial: true,
      authorityGrant: false,
      scoreContributionAllowed: false,
      reasonCodes: ['synthetic_fixture', 'provider_timeout'],
    });
    expect(payload.consumerEvidenceSnapshot?.providerState).toMatchObject({
      present: true,
      status: 'unavailable',
      quoteMode: 'synthetic',
      sourceType: 'synthetic_bundle',
      sourceTier: 'synthetic_internal',
      providerTier: 'degraded_cache',
      freshness: 'unavailable',
      asOf: '2026-05-07T09:58:00Z',
      sourceAuthorityAllowed: false,
      scoreContributionAllowed: false,
      noExternalCalls: true,
      coverage: {
        requestedSymbolCount: 6,
        usableSymbolCount: 0,
        coveragePercent: 0,
      },
    });
    expect(payload.consumerEvidenceSnapshot?.etfProxySummary).toMatchObject({
      present: true,
      proxyOnly: true,
      label: 'Synthetic proxy watch',
      fundFlowAuthorityAllowed: false,
      enabled: false,
      source: 'synthetic_proxy_pack',
      asOf: '2026-05-07T09:58:00Z',
      eligibleSymbolCount: 0,
      leadingSymbols: ['QQQ'],
      laggingSymbols: ['IWM'],
      reasonCodes: ['synthetic_fixture', 'provider_timeout'],
    });
    expect(payload.consumerEvidenceSnapshot?.themes).toEqual([
      expect.objectContaining({
        id: 'ai_applications',
        freshness: 'unavailable',
        isFallback: true,
        isStale: true,
        isPartial: true,
        evidenceQuality: 'synthetic_only',
        dataGaps: ['synthetic_fixture', 'provider_timeout'],
      }),
    ]);
    expect(payload.consumerEvidenceSnapshot?.rotationFamilyRollup[0]).toMatchObject({
      familyId: 'ai',
      familyName: 'AI',
      themeIds: ['ai_applications'],
      themeNames: ['AI 应用'],
      leaderThemeIds: ['ai_applications'],
      themeCount: 1,
      signalThemeCount: 0,
    });
    expect(payload.consumerEvidenceSnapshot?.rotationFamilyRollup[0].themeFlowSignal).toMatchObject({
      themeFlowState: 'unavailable',
      freshness: 'unavailable',
    });
  });
});
