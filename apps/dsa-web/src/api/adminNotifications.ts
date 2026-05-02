import apiClient from './index';
import { toCamelCase } from './utils';

export type NotificationSeverity = 'info' | 'warning' | 'critical';
export type NotificationChannelType = 'in_app' | 'webhook' | 'system_channel';

export interface NotificationChannel {
  id: number;
  name: string;
  type: NotificationChannelType;
  enabled: boolean;
  severityMin: NotificationSeverity;
  eventTypes: string[];
  config: Record<string, unknown>;
  createdAt?: string | null;
  updatedAt?: string | null;
  lastTestedAt?: string | null;
  lastSentAt?: string | null;
  lastError?: string | null;
  lastErrorCode?: string | null;
  lastErrorDiagnostics?: Record<string, unknown>;
}

export interface NotificationChannelPayload {
  name: string;
  type: NotificationChannelType;
  enabled: boolean;
  severityMin: NotificationSeverity;
  eventTypes: string[];
  config: Record<string, unknown>;
}

export interface NotificationChannelListPayload {
  items: NotificationChannel[];
  availableSystemChannels: string[];
}

export interface NotificationEvent {
  id: number;
  eventType: string;
  severity: NotificationSeverity;
  title: string;
  message: string;
  payload: Record<string, unknown>;
  fingerprint?: string | null;
  createdAt?: string | null;
  acknowledgedAt?: string | null;
  acknowledgedBy?: string | null;
  deliveryStatus: string;
}

export interface NotificationEventListResponse {
  total: number;
  limit: number;
  offset: number;
  items: NotificationEvent[];
}

export interface NotificationChannelTestResult {
  success: boolean;
  error?: string | null;
  errorCode?: string | null;
  diagnostics?: Record<string, unknown>;
  channel: NotificationChannel;
}

function toApiPayload(payload: Partial<NotificationChannelPayload>) {
  return {
    ...payload,
    severity_min: payload.severityMin,
    event_types: payload.eventTypes,
    config: payload.config
      ? {
        ...payload.config,
        webhook_url: payload.config.webhookUrl,
      }
      : undefined,
  };
}

function normalizeChannel(payload: Record<string, unknown>): NotificationChannel {
  const normalized = toCamelCase<NotificationChannel>(payload);
  return {
    ...normalized,
    eventTypes: Array.isArray(normalized.eventTypes) ? normalized.eventTypes : [],
    config: normalized.config && typeof normalized.config === 'object' ? normalized.config : {},
  };
}

function normalizeEvent(payload: Record<string, unknown>): NotificationEvent {
  const normalized = toCamelCase<NotificationEvent>(payload);
  return {
    ...normalized,
    payload: normalized.payload && typeof normalized.payload === 'object' ? normalized.payload : {},
  };
}

export const adminNotificationsApi = {
  async listChannels(): Promise<NotificationChannelListPayload> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/admin/notification-channels');
    const normalized = toCamelCase<{ items?: Record<string, unknown>[]; availableSystemChannels?: unknown[] }>(response.data);
    return {
      items: Array.isArray(normalized.items) ? normalized.items.map(normalizeChannel) : [],
      availableSystemChannels: Array.isArray(normalized.availableSystemChannels)
        ? normalized.availableSystemChannels.map((item) => String(item)).filter(Boolean)
        : [],
    };
  },

  async createChannel(payload: NotificationChannelPayload): Promise<NotificationChannel> {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/admin/notification-channels',
      toApiPayload(payload),
    );
    return normalizeChannel(response.data);
  },

  async updateChannel(channelId: number, payload: Partial<NotificationChannelPayload>): Promise<NotificationChannel> {
    const response = await apiClient.patch<Record<string, unknown>>(
      `/api/v1/admin/notification-channels/${encodeURIComponent(String(channelId))}`,
      toApiPayload(payload),
    );
    return normalizeChannel(response.data);
  },

  async deleteChannel(channelId: number): Promise<void> {
    await apiClient.delete(`/api/v1/admin/notification-channels/${encodeURIComponent(String(channelId))}`);
  },

  async testChannel(channelId: number): Promise<NotificationChannelTestResult> {
    const response = await apiClient.post<Record<string, unknown>>(
      `/api/v1/admin/notification-channels/${encodeURIComponent(String(channelId))}/test`,
    );
    const normalized = toCamelCase<NotificationChannelTestResult & { channel: Record<string, unknown> }>(response.data);
    return {
      success: Boolean(normalized.success),
      error: normalized.error || null,
      errorCode: normalized.errorCode || null,
      diagnostics: normalized.diagnostics && typeof normalized.diagnostics === 'object' ? normalized.diagnostics : {},
      channel: normalizeChannel(normalized.channel || {}),
    };
  },

  async listNotifications(): Promise<NotificationEventListResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/admin/notifications');
    const normalized = toCamelCase<NotificationEventListResponse>(response.data);
    return {
      total: Number(normalized.total || 0),
      limit: Number(normalized.limit || 100),
      offset: Number(normalized.offset || 0),
      items: Array.isArray(normalized.items)
        ? normalized.items.map((item) => normalizeEvent(item as unknown as Record<string, unknown>))
        : [],
    };
  },

  async acknowledgeNotification(eventId: number): Promise<NotificationEvent> {
    const response = await apiClient.post<Record<string, unknown>>(
      `/api/v1/admin/notifications/${encodeURIComponent(String(eventId))}/ack`,
    );
    const normalized = toCamelCase<{ event?: Record<string, unknown> }>(response.data);
    return normalizeEvent(normalized.event || response.data);
  },
};
