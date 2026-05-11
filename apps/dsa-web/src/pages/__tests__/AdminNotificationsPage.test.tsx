import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AdminNotificationsPage from '../AdminNotificationsPage';

const {
  listChannels,
  createChannel,
  updateChannel,
  deleteChannel,
  testChannel,
  listNotifications,
  acknowledgeNotification,
  uiLanguageState,
} = vi.hoisted(() => ({
  listChannels: vi.fn(),
  createChannel: vi.fn(),
  updateChannel: vi.fn(),
  deleteChannel: vi.fn(),
  testChannel: vi.fn(),
  listNotifications: vi.fn(),
  acknowledgeNotification: vi.fn(),
  uiLanguageState: { current: 'en' as 'zh' | 'en' },
}));

vi.mock('../../api/adminNotifications', () => ({
  adminNotificationsApi: {
    listChannels,
    createChannel,
    updateChannel,
    deleteChannel,
    testChannel,
    listNotifications,
    acknowledgeNotification,
  },
}));

vi.mock('../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: uiLanguageState.current,
    t: (key: string) => key,
  }),
}));

const channels = [
  {
    id: 1,
    name: 'Ops inbox',
    type: 'in_app',
    enabled: true,
    severityMin: 'info',
    eventTypes: [],
    config: {},
    createdAt: '2026-05-02T08:00:00Z',
    updatedAt: '2026-05-02T08:00:00Z',
    lastTestedAt: null,
    lastTriggeredAt: '2026-05-02T08:20:00Z',
    lastSentAt: '2026-05-02T08:20:00Z',
    lastStatus: 'success',
    lastError: null,
  },
  {
    id: 2,
    name: 'Ops webhook',
    type: 'webhook',
    enabled: true,
    severityMin: 'warning',
    eventTypes: ['admin_logs.storage'],
    config: {
      webhookUrl: 'https://hooks.example.test/***',
      token: '********',
    },
    routeScope: 'log_notification_association',
    coverageSummary: 'admin_logs.storage; min_severity=warning',
    targetSummary: 'webhook:configured',
    createdAt: '2026-05-02T08:00:00Z',
    updatedAt: '2026-05-02T08:00:00Z',
    lastTestedAt: '2026-05-02T08:15:00Z',
    lastTriggeredAt: '2026-05-02T08:20:00Z',
    lastSentAt: '2026-05-02T08:20:00Z',
    lastStatus: 'provider_down',
    lastError: 'provider_down: webhook provider unavailable',
    lastErrorSummary: 'Webhook delivery failed',
    lastErrorCode: 'webhook_delivery_failed',
  },
];

const notifications = [
  {
    id: 10,
    eventType: 'admin_logs.storage',
    severity: 'critical',
    title: 'Admin Logs storage critical',
    message: 'Storage is over the hard limit',
    payload: {},
    fingerprint: 'admin_logs.storage:critical',
    createdAt: '2026-05-02T08:20:00Z',
    acknowledgedAt: null,
    acknowledgedBy: null,
    deliveryStatus: 'delivered',
  },
];

describe('AdminNotificationsPage', () => {
  beforeEach(() => {
    uiLanguageState.current = 'en';
    vi.clearAllMocks();
    listChannels.mockResolvedValue({ items: channels, availableSystemChannels: ['discord', 'email'] });
    listNotifications.mockResolvedValue({ total: 1, limit: 100, offset: 0, items: notifications });
    createChannel.mockResolvedValue(channels[1]);
    updateChannel.mockResolvedValue({ ...channels[1], enabled: false });
    deleteChannel.mockResolvedValue({ success: true, deletedScope: 'log_notification_association' });
    testChannel.mockResolvedValue({ success: true, dryRun: false, channel: channels[1] });
    acknowledgeNotification.mockResolvedValue({ ...notifications[0], acknowledgedAt: '2026-05-02T08:30:00Z' });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
  });

  it('renders notification rule coverage summary in chinese', async () => {
    uiLanguageState.current = 'zh';
    render(<AdminNotificationsPage />);

    expect(await screen.findByText('路由覆盖')).toBeInTheDocument();
    expect(screen.getByText('通知规则')).toBeInTheDocument();
    expect(screen.getAllByText('已启用').length).toBeGreaterThan(0);
    expect(screen.getByText('已配置通道')).toBeInTheDocument();
    expect(screen.getByText('覆盖事件')).toBeInTheDocument();
    expect(screen.getAllByText(/admin_logs\.storage/).length).toBeGreaterThan(0);
  });

  it('renders notification channel list without exposing webhook urls or tokens', async () => {
    render(<AdminNotificationsPage />);

    expect(await screen.findByText('Ops inbox')).toBeInTheDocument();
    const webhookRow = screen.getByTestId('notification-channel-2');
    expect(within(webhookRow).getByText('Ops webhook')).toBeInTheDocument();
    expect(within(webhookRow).getByText('Webhook target masked')).toBeInTheDocument();
    expect(screen.queryByText('https://hooks.example.test/***')).not.toBeInTheDocument();
    expect(screen.queryByText('********')).not.toBeInTheDocument();
  });

  it('renders the admin notifications route with terminal primitives', async () => {
    render(<AdminNotificationsPage />);

    expect(await screen.findByRole('heading', { level: 1, name: 'Admin notifications' })).toBeInTheDocument();
    expect(screen.getByTestId('admin-notifications-workspace')).toHaveAttribute('data-terminal-primitive', 'page-shell');
    expect(screen.getByTestId('admin-notifications-summary-grid')).toHaveAttribute('data-terminal-primitive', 'grid');
    expect(screen.getByTestId('admin-notifications-rules-panel')).toHaveAttribute('data-terminal-primitive', 'panel');
    expect(screen.getByTestId('admin-notifications-events-panel')).toHaveAttribute('data-terminal-primitive', 'panel');
  });

  it('renders localized chinese page copy when the ui language is zh', async () => {
    uiLanguageState.current = 'zh';
    render(<AdminNotificationsPage />);

    expect(await screen.findByText('管理员通知')).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: '刷新' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '创建通道' })).toBeInTheDocument();
    expect(screen.getByText('通知规则')).toBeInTheDocument();
    expect(screen.getByText('通知事件')).toBeInTheDocument();
    expect(screen.getAllByText('严重').length).toBeGreaterThan(0);
    expect(screen.queryByText('critical')).not.toBeInTheDocument();
  });

  it('maps raw statuses to chinese in default rule UI', async () => {
    uiLanguageState.current = 'zh';
    render(<AdminNotificationsPage />);

    const webhookRow = await screen.findByTestId('notification-channel-2');
    expect(within(webhookRow).getByText('服务异常')).toBeInTheDocument();
    expect(within(webhookRow).getByText('Webhook 投递失败。')).toBeInTheDocument();
    expect(screen.queryByText('provider_down')).not.toBeInTheDocument();
  });

  it('validates required create form fields before submitting', async () => {
    render(<AdminNotificationsPage />);

    fireEvent.click(await screen.findByRole('button', { name: 'Create channel' }));

    expect(await screen.findByText('Name is required.')).toBeInTheDocument();
    expect(createChannel).not.toHaveBeenCalled();
  });

  it('creates webhook channels from form values', async () => {
    render(<AdminNotificationsPage />);

    fireEvent.change(await screen.findByLabelText('Channel name'), { target: { value: 'Pager webhook' } });
    fireEvent.change(screen.getByLabelText('Channel type'), { target: { value: 'webhook' } });
    fireEvent.change(screen.getByLabelText('Webhook URL'), { target: { value: 'https://hooks.example.test/new' } });
    fireEvent.change(screen.getByLabelText('Bearer token'), { target: { value: 'secret-token' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create channel' }));

    await waitFor(() => {
      expect(createChannel).toHaveBeenCalledWith(expect.objectContaining({
        name: 'Pager webhook',
        type: 'webhook',
        config: {
          webhookUrl: 'https://hooks.example.test/new',
          token: 'secret-token',
        },
      }));
    });
  });

  it('creates log notification rules for existing system channels', async () => {
    render(<AdminNotificationsPage />);

    fireEvent.change(await screen.findByLabelText('Channel name'), { target: { value: 'Discord errors' } });
    fireEvent.change(screen.getByLabelText('Existing notification channel'), { target: { value: 'email' } });
    fireEvent.change(screen.getByLabelText('Minimum severity'), { target: { value: 'critical' } });
    fireEvent.change(screen.getByLabelText('Event types'), { target: { value: 'admin_logs.event' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create channel' }));

    await waitFor(() => {
      expect(createChannel).toHaveBeenCalledWith(expect.objectContaining({
        name: 'Discord errors',
        type: 'system_channel',
        severityMin: 'critical',
        eventTypes: ['admin_logs.event'],
        config: { channel: 'email' },
      }));
    });
  });

  it('tests a channel and refreshes status with mocked API delivery', async () => {
    render(<AdminNotificationsPage />);

    const webhookRow = await screen.findByTestId('notification-channel-2');
    fireEvent.click(within(webhookRow).getByRole('button', { name: 'Test send' }));

    await waitFor(() => {
      expect(testChannel).toHaveBeenCalledWith(2, { dryRun: false });
      expect(listChannels).toHaveBeenCalledTimes(2);
    });
  });

  it('dry-runs a channel and shows that no notification was sent', async () => {
    uiLanguageState.current = 'zh';
    testChannel.mockResolvedValueOnce({ success: true, dryRun: true, targetSummary: 'webhook:configured', channel: channels[1] });
    render(<AdminNotificationsPage />);

    const webhookRow = await screen.findByTestId('notification-channel-2');
    fireEvent.click(within(webhookRow).getByRole('button', { name: '仅验证' }));

    await waitFor(() => {
      expect(testChannel).toHaveBeenCalledWith(2, { dryRun: true });
    });
    expect(await screen.findByText('试运行通过，未发送真实通知。')).toBeInTheDocument();
  });

  it('deletes only the log notification association for a configured channel', async () => {
    uiLanguageState.current = 'zh';
    render(<AdminNotificationsPage />);

    const webhookRow = await screen.findByTestId('notification-channel-2');
    expect(within(webhookRow).getByText('仅解除日志路由绑定，不会删除系统通道。')).toBeInTheDocument();
    fireEvent.click(within(webhookRow).getByRole('button', { name: '解除绑定' }));

    await waitFor(() => {
      expect(deleteChannel).toHaveBeenCalledWith(2);
      expect(listChannels).toHaveBeenCalledTimes(2);
    });
    expect(await screen.findByText('仅解除日志路由绑定；系统通道仍保留。')).toBeInTheDocument();
  });

  it('shows localized ssl delivery diagnostics when webhook verification fails', async () => {
    uiLanguageState.current = 'zh';
    testChannel.mockResolvedValueOnce({
      success: false,
      errorCode: 'ssl_certificate_verify_failed',
      error: 'SSL certificate verification failed: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed',
      diagnostics: {
        summary: 'Webhook SSL 证书校验失败。',
        troubleshooting: ['请检查证书链。'],
      },
      channel: channels[1],
    });

    render(<AdminNotificationsPage />);

    const webhookRow = await screen.findByTestId('notification-channel-2');
    fireEvent.click(within(webhookRow).getByRole('button', { name: '测试发送' }));

    expect(await screen.findByText('Webhook SSL 证书校验失败。')).toBeInTheDocument();
    expect(
      await screen.findByText(
        (content, element) => element?.tagName?.toLowerCase() === 'li' && (element.textContent?.includes('请检查证书链。') ?? false),
      ),
    ).toBeInTheDocument();
    expect(screen.getByText('开发者细节')).toBeInTheDocument();
    expect(screen.getByTestId('notification-notice-raw-diagnostics')).toHaveAttribute('data-terminal-primitive', 'disclosure');
    expect(screen.getByTestId('notification-notice-raw-diagnostics')).not.toHaveAttribute('open');
  });

  it('shows localized english ssl delivery diagnostics when webhook verification fails', async () => {
    uiLanguageState.current = 'en';
    testChannel.mockResolvedValueOnce({
      success: false,
      errorCode: 'ssl_certificate_verify_failed',
      error: 'SSL certificate verification failed: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed',
      diagnostics: {
        summary: 'Webhook SSL certificate verification failed.',
        troubleshooting: ['Check the certificate chain.'],
      },
      channel: channels[1],
    });

    render(<AdminNotificationsPage />);

    const webhookRow = await screen.findByTestId('notification-channel-2');
    fireEvent.click(within(webhookRow).getByRole('button', { name: 'Test send' }));

    expect(await screen.findByText('Webhook SSL certificate verification failed.')).toBeInTheDocument();
    expect(
      await screen.findByText(
        (content, element) => element?.tagName?.toLowerCase() === 'li' && (element.textContent?.includes('Check the certificate chain.') ?? false),
      ),
    ).toBeInTheDocument();
    expect(screen.getByText('Developer details')).toBeInTheDocument();
  });

  it('renders notifications with severity and acknowledge action', async () => {
    render(<AdminNotificationsPage />);

    const eventRow = await screen.findByTestId('notification-event-10');
    expect(within(eventRow).getByText('Admin Logs storage critical')).toBeInTheDocument();
    expect(within(eventRow).getByText('critical')).toBeInTheDocument();

    fireEvent.click(within(eventRow).getByRole('button', { name: 'Acknowledge' }));

    await waitFor(() => {
      expect(acknowledgeNotification).toHaveBeenCalledWith(10);
      expect(listNotifications).toHaveBeenCalledTimes(2);
    });
  });

  it('renders compact chinese empty state when no rules exist', async () => {
    uiLanguageState.current = 'zh';
    listChannels.mockResolvedValueOnce({ items: [], availableSystemChannels: ['discord'] });
    listNotifications.mockResolvedValueOnce({ total: 0, limit: 100, offset: 0, items: [] });

    render(<AdminNotificationsPage />);

    expect((await screen.findAllByText('暂无通知规则。')).length).toBeGreaterThan(0);
    expect(screen.getByText('暂无通知事件。')).toBeInTheDocument();
    expect(screen.getByTestId('notification-rules-empty-state')).toHaveAttribute('data-terminal-primitive', 'empty-state');
    expect(screen.getByTestId('notification-events-empty-state')).toHaveAttribute('data-terminal-primitive', 'empty-state');
  });
});
