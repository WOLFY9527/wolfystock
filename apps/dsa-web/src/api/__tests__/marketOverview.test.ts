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
});
