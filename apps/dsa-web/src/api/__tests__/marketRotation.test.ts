import { beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from '../index';
import { marketRotationApi } from '../marketRotation';

vi.mock('../index', () => ({
  default: {
    get: vi.fn(),
  },
}));

describe('marketRotationApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
          watchlist_signals: [
            { theme_id: 'ai_applications', symbol: 'APP', label: '关注候选', signal: 'confirmed_rotation', signal_label: '确认轮动', read_only: true, delivery_enabled: false },
          ],
          safe_wording: ['资金轮动迹象', '非买卖建议'],
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
});
