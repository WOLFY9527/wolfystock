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
          schema_version: 'market_rotation_radar_mvp_v1',
        },
        benchmarks: {
          QQQ: {
            symbol: 'QQQ',
            change_percent: 0.8,
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
          safe_wording: ['资金轮动迹象', '非买卖建议'],
        },
        themes: [
          {
            id: 'ai_applications',
            name: 'AI 应用',
            english_name: 'AI Applications',
            rotation_score: 78,
            confidence: 0.72,
            stage: 'confirmed_rotation',
            risk_labels: [],
            newsless_rotation: true,
            freshness: 'delayed',
            is_fallback: false,
            is_stale: false,
            evidence: ['无明显新闻的同步异动'],
            relative_strength: { average_relative_strength_percent: 2.6 },
            volume: { average_relative_volume: 1.8 },
            breadth: { percent_up: 88, percent_outperforming_benchmark: 88 },
            synchronization: { same_direction_percent: 88 },
            leadership: { top_members: [{ symbol: 'APP', name: 'APP', change_percent: 5.1 }] },
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
    expect(JSON.stringify(payload).toLowerCase()).not.toContain('raw_payload');
  });
});
