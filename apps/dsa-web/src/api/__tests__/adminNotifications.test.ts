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

  it('normalizes available existing system channels from list response', async () => {
    const { adminNotificationsApi } = await import('../adminNotifications');
    get.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 2,
            name: 'System Discord',
            type: 'system_channel',
            enabled: true,
            severity_min: 'warning',
            event_types: ['admin_logs.event'],
            config: { channel: 'discord' },
          },
        ],
        available_system_channels: ['discord', 'email'],
      },
    });

    const result = await adminNotificationsApi.listChannels();

    expect(result.availableSystemChannels).toEqual(['discord', 'email']);
    expect(result.items[0]).toEqual(expect.objectContaining({
      type: 'system_channel',
      eventTypes: ['admin_logs.event'],
    }));
  });

  it('deletes a log notification channel association through the admin route', async () => {
    const { adminNotificationsApi } = await import('../adminNotifications');
    del.mockResolvedValueOnce({ data: { success: true, deleted_scope: 'log_notification_association' } });

    await adminNotificationsApi.deleteChannel(2);

    expect(del).toHaveBeenCalledWith('/api/v1/admin/notification-channels/2');
  });
});
