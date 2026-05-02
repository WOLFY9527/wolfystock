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

describe('adminNotificationsApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('posts channel creation to the registered admin notification route', async () => {
    const { adminNotificationsApi } = await import('../adminNotifications');
    post.mockResolvedValueOnce({
      data: {
        id: 1,
        name: 'Ops inbox',
        type: 'in_app',
        enabled: true,
        severity_min: 'warning',
        event_types: [],
        config: {},
      },
    });

    await adminNotificationsApi.createChannel({
      name: 'Ops inbox',
      type: 'in_app',
      enabled: true,
      severityMin: 'warning',
      eventTypes: [],
      config: {},
    });

    expect(post).toHaveBeenCalledWith(
      '/api/v1/admin/notification-channels',
      expect.objectContaining({
        name: 'Ops inbox',
        type: 'in_app',
        severity_min: 'warning',
        event_types: [],
      }),
    );
  });
});
