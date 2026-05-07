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
          schema_version: 'market_rotation_radar_phase3_v1',
          time_windows: ['5m', '15m', '60m', '1d'],
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
            { id: 'ai_applications', name: 'AI 应用', rotation_score: 78, confidence: 0.72, stage: 'confirmed_rotation', freshness: 'delayed', is_fallback: false, risk_labels: [] },
          ],
          accelerating_themes: [],
          fading_themes: [],
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
              },
            ],
            freshness: 'delayed',
            is_fallback: false,
            is_stale: false,
            evidence: ['无明显新闻的同步异动'],
            relative_strength: { average_relative_strength_percent: 2.6 },
            benchmark_proxies: {
              IGV: { symbol: 'IGV', role: 'sector_proxy', relative_strength: 2.2, freshness: 'delayed', is_fallback: false, is_stale: false },
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
    expect(payload.summary.strongestThemes[0].rotationScore).toBe(78);
    expect(payload.themes[0].englishName).toBe('AI Applications');
    expect(payload.themes[0].newslessRotation).toBe(true);
    expect(payload.themes[0].persistenceEvidence?.label).toBe('跨时窗延续');
    expect(payload.themes[0].alertCandidates?.[0].readOnly).toBe(true);
    expect(payload.summary.watchlistSignals[0].label).toBe('关注候选');
    expect(payload.themes[0].timeWindows?.['1d'].available).toBe(true);
    expect(payload.themes[0].benchmarkProxies?.IGV.role).toBe('sector_proxy');
    expect(payload.themes[0].themeDetail?.watchlistSafe).toBe(true);
    expect(JSON.stringify(payload).toLowerCase()).not.toContain('raw_payload');
  });
});
