import { beforeEach, describe, expect, it, vi } from 'vitest';

const { get, post } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock('../index', () => ({
  default: {
    get,
    post,
  },
}));

describe('adminLogsApi incident timeline helpers', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('requests the incident timeline route with admin lookup params', async () => {
    const { adminLogsApi } = await import('../adminLogs');
    get.mockResolvedValueOnce({
      data: {
        lookup: {
          session_id: 'session-1',
          request_id: 'req-1',
          query_id: 'query-1',
          symbol: 'TSLA',
          date_from: '2026-05-18T08:00:00Z',
          date_to: null,
          limit: 60,
        },
        total: 1,
        hooks: [],
        items: [
          {
            id: 'event-1',
            kind: 'data_quality',
            status: 'failed',
            severity: 'error',
            title: 'Quote missing',
            navigation: {
              session_id: 'session-1',
              business_event_id: 'analysis-tsla',
            },
          },
        ],
        empty_state: {
          reason: null,
          read_only: true,
          message: null,
        },
        metadata: {
          read_only: true,
        },
      },
    });

    const result = await adminLogsApi.getIncidentTimeline({
      sessionId: 'session-1',
      requestId: 'req-1',
      queryId: 'query-1',
      symbol: 'TSLA',
      since: '24h',
      limit: 60,
    });

    expect(get).toHaveBeenCalledWith('/api/v1/admin/logs/incident-timeline', {
      params: {
        session_id: 'session-1',
        request_id: 'req-1',
        query_id: 'query-1',
        symbol: 'TSLA',
        since: '24h',
        date_from: undefined,
        date_to: undefined,
        limit: 60,
      },
    });
    expect(result.lookup.sessionId).toBe('session-1');
    expect(result.items[0].navigation.businessEventId).toBe('analysis-tsla');
    expect(result.emptyState.readOnly).toBe(true);
  });

  it('normalizes data-missing drilldown samples into frontend-safe arrays', async () => {
    const { adminLogsApi } = await import('../adminLogs');
    get.mockResolvedValueOnce({
      data: {
        total: 1,
        items: [
          {
            affected_surface: 'home_quote_panel',
            symbol: 'TSLA',
            market: 'US',
            missing_domain: 'news',
            provider: 'newsapi',
            source: 'Yahoo',
            freshness_status: 'missing',
            fallback_used: true,
            stale: false,
            partial: true,
            reason_code: 'timeout',
            latest_seen_at: '2026-05-18T08:00:00Z',
            count: 2,
            sample_event_ids: ['evt-1'],
            sample_session_ids: ['session-1'],
            sample_business_event_ids: ['analysis-tsla'],
          },
        ],
      },
    });

    const result = await adminLogsApi.listDataMissingDrilldown({ since: '24h', limit: 4 });

    expect(get).toHaveBeenCalledWith('/api/v1/admin/logs/data-missing-drilldown', {
      params: {
        since: '24h',
        date_from: undefined,
        date_to: undefined,
        limit: 4,
      },
    });
    expect(result.items[0]).toEqual(expect.objectContaining({
      affectedSurface: 'home_quote_panel',
      missingDomain: 'news',
      sampleSessionIds: ['session-1'],
      sampleBusinessEventIds: ['analysis-tsla'],
    }));
  });
});
