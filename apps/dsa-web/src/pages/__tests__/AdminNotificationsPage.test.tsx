import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AdminNotificationsPage from '../AdminNotificationsPage';

const {
  listChannels,
  createChannel,
  updateChannel,
  testChannel,
  listNotifications,
  acknowledgeNotification,
} = vi.hoisted(() => ({
  listChannels: vi.fn(),
  createChannel: vi.fn(),
  updateChannel: vi.fn(),
  testChannel: vi.fn(),
  listNotifications: vi.fn(),
  acknowledgeNotification: vi.fn(),
}));

vi.mock('../../api/adminNotifications', () => ({
  adminNotificationsApi: {
    listChannels,
    createChannel,
    updateChannel,
    testChannel,
    listNotifications,
    acknowledgeNotification,
  },
}));

vi.mock('../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: 'en',
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
    lastSentAt: '2026-05-02T08:20:00Z',
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
    createdAt: '2026-05-02T08:00:00Z',
    updatedAt: '2026-05-02T08:00:00Z',
    lastTestedAt: '2026-05-02T08:15:00Z',
    lastSentAt: '2026-05-02T08:20:00Z',
    lastError: null,
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
    vi.clearAllMocks();
    listChannels.mockResolvedValue(channels);
    listNotifications.mockResolvedValue({ total: 1, limit: 100, offset: 0, items: notifications });
    createChannel.mockResolvedValue(channels[1]);
    updateChannel.mockResolvedValue({ ...channels[1], enabled: false });
    testChannel.mockResolvedValue({ success: true, channel: channels[1] });
    acknowledgeNotification.mockResolvedValue({ ...notifications[0], acknowledgedAt: '2026-05-02T08:30:00Z' });
  });

  it('renders notification channel list with masked webhook and token fields', async () => {
    render(<AdminNotificationsPage />);

    expect(await screen.findByText('Ops inbox')).toBeInTheDocument();
    const webhookRow = screen.getByTestId('notification-channel-2');
    expect(within(webhookRow).getByText('Ops webhook')).toBeInTheDocument();
    expect(within(webhookRow).getByText('https://hooks.example.test/***')).toBeInTheDocument();
    expect(within(webhookRow).getByText('********')).toBeInTheDocument();
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

  it('tests a channel and refreshes status with mocked API delivery', async () => {
    render(<AdminNotificationsPage />);

    const webhookRow = await screen.findByTestId('notification-channel-2');
    fireEvent.click(within(webhookRow).getByRole('button', { name: 'Test' }));

    await waitFor(() => {
      expect(testChannel).toHaveBeenCalledWith(2);
      expect(listChannels).toHaveBeenCalledTimes(2);
    });
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
});
