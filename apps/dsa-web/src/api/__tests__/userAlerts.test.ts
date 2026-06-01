import { beforeEach, describe, expect, it, vi } from 'vitest';

const { get, post, patch, del } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  del: vi.fn(),
}));

vi.mock('../index', () => ({
  default: {
    get,
    post,
    patch,
    delete: del,
  },
}));

describe('userAlertsApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('lists and normalizes owner-scoped in-app alert rules from the user alerts route', async () => {
    const { userAlertsApi } = await import('../userAlerts');
    get.mockResolvedValueOnce({
      data: {
        contract_version: 'user_alert_contract_v1',
        delivery_mode: 'in_app',
        in_app_only: true,
        owner_scoped: true,
        items: [
          {
            id: 7,
            contract_version: 'user_alert_contract_v1',
            rule_type: 'watchlist_price_threshold',
            symbol: 'NVDA',
            direction: 'above',
            threshold_price: 125.5,
            enabled: true,
            note: 'Watch only in app.',
            delivery_mode: 'in_app',
            in_app_only: true,
            owner_scoped: true,
            created_at: '2026-06-01T10:00:00Z',
            updated_at: '2026-06-01T11:00:00Z',
          },
        ],
      },
    });

    const result = await userAlertsApi.listRules();

    expect(get).toHaveBeenCalledWith('/api/v1/user-alerts/rules');
    expect(result).toEqual({
      contractVersion: 'user_alert_contract_v1',
      deliveryMode: 'in_app',
      inAppOnly: true,
      ownerScoped: true,
      items: [
        {
          id: 7,
          contractVersion: 'user_alert_contract_v1',
          ruleType: 'watchlist_price_threshold',
          symbol: 'NVDA',
          direction: 'above',
          thresholdPrice: 125.5,
          enabled: true,
          note: 'Watch only in app.',
          deliveryMode: 'in_app',
          inAppOnly: true,
          ownerScoped: true,
          createdAt: '2026-06-01T10:00:00Z',
          updatedAt: '2026-06-01T11:00:00Z',
        },
      ],
    });
  });

  it('serializes create and update payloads to backend snake_case fields', async () => {
    const { userAlertsApi } = await import('../userAlerts');
    post.mockResolvedValueOnce({
      data: {
        id: 7,
        contract_version: 'user_alert_contract_v1',
        rule_type: 'watchlist_price_threshold',
        symbol: 'NVDA',
        direction: 'above',
        threshold_price: 125.5,
        enabled: true,
        note: 'Watch only in app.',
        delivery_mode: 'in_app',
        in_app_only: true,
        owner_scoped: true,
      },
    });
    patch.mockResolvedValueOnce({
      data: {
        id: 7,
        contract_version: 'user_alert_contract_v1',
        rule_type: 'watchlist_price_threshold',
        symbol: 'NVDA',
        direction: 'below',
        threshold_price: 118.25,
        enabled: false,
        note: null,
        delivery_mode: 'in_app',
        in_app_only: true,
        owner_scoped: true,
      },
    });

    const created = await userAlertsApi.createRule({
      symbol: 'nvda',
      direction: 'above',
      thresholdPrice: 125.5,
      enabled: true,
      note: 'Watch only in app.',
    });
    const updated = await userAlertsApi.updateRule(7, {
      direction: 'below',
      thresholdPrice: 118.25,
      enabled: false,
      note: null,
    });

    expect(post).toHaveBeenCalledWith('/api/v1/user-alerts/rules', {
      symbol: 'nvda',
      direction: 'above',
      threshold_price: 125.5,
      enabled: true,
      note: 'Watch only in app.',
    });
    expect(patch).toHaveBeenCalledWith('/api/v1/user-alerts/rules/7', {
      direction: 'below',
      threshold_price: 118.25,
      enabled: false,
      note: null,
    });
    expect(created.thresholdPrice).toBe(125.5);
    expect(updated.direction).toBe('below');
    expect(updated.inAppOnly).toBe(true);
  });

  it('lists alert events with pagination params and preserves warning semantics', async () => {
    const { userAlertsApi } = await import('../userAlerts');
    get.mockResolvedValueOnce({
      data: {
        contract_version: 'user_alert_contract_v1',
        delivery_mode: 'in_app',
        in_app_only: true,
        owner_scoped: true,
        total: 1,
        limit: 50,
        offset: 10,
        items: [
          {
            id: 3,
            event_type: 'watchlist_price_threshold_triggered',
            rule_id: 7,
            symbol: 'NVDA',
            direction: 'above',
            threshold_price: 125.5,
            title: '价格阈值提醒',
            message: 'Not trading advice. No order placement.',
            delivery_mode: 'in_app',
            in_app_only: true,
            owner_scoped: true,
            read_at: null,
            created_at: '2026-06-01T12:00:00Z',
          },
        ],
      },
    });

    const result = await userAlertsApi.listEvents({ limit: 50, offset: 10 });

    expect(get).toHaveBeenCalledWith('/api/v1/user-alerts/events', {
      params: {
        limit: 50,
        offset: 10,
      },
    });
    expect(result.items[0]).toEqual(expect.objectContaining({
      eventType: 'watchlist_price_threshold_triggered',
      ruleId: 7,
      thresholdPrice: 125.5,
      message: 'Not trading advice. No order placement.',
      deliveryMode: 'in_app',
      inAppOnly: true,
      ownerScoped: true,
    }));
  });

  it('deletes rules through the owner-scoped route without touching admin notification endpoints', async () => {
    const { userAlertsApi } = await import('../userAlerts');
    del.mockResolvedValueOnce({
      data: {
        deleted: 1,
      },
    });

    const result = await userAlertsApi.deleteRule(7);
    const calledRoutes = [
      ...get.mock.calls.map((call) => String(call[0])),
      ...post.mock.calls.map((call) => String(call[0])),
      ...patch.mock.calls.map((call) => String(call[0])),
      ...del.mock.calls.map((call) => String(call[0])),
    ];

    expect(del).toHaveBeenCalledWith('/api/v1/user-alerts/rules/7');
    expect(result).toEqual({ deleted: 1 });
    expect(calledRoutes.some((route) => route.startsWith('/api/v1/admin/notification'))).toBe(false);
  });

  it('propagates backend validation errors without swallowing them', async () => {
    const { userAlertsApi } = await import('../userAlerts');
    post.mockRejectedValueOnce({
      response: {
        status: 400,
        data: {
          error: 'validation_error',
          message: 'threshold_price must be greater than 0',
        },
      },
    });

    await expect(userAlertsApi.createRule({
      symbol: 'AAPL',
      direction: 'above',
      thresholdPrice: 0,
    })).rejects.toMatchObject({
      response: {
        status: 400,
        data: {
          error: 'validation_error',
        },
      },
    });
  });
});
