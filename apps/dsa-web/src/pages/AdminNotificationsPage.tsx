import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { BellRing, CheckCircle2, Power, Send, Webhook } from 'lucide-react';
import {
  adminNotificationsApi,
  type NotificationChannel,
  type NotificationChannelPayload,
  type NotificationChannelType,
  type NotificationEvent,
  type NotificationSeverity,
} from '../api/adminNotifications';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { ApiErrorAlert, GlassCard } from '../components/common';
import { useI18n } from '../contexts/UiLanguageContext';
import { cn } from '../utils/cn';
import { formatDateTime as formatDateTimeValue } from '../utils/format';

type ChannelDraft = {
  name: string;
  type: NotificationChannelType;
  enabled: boolean;
  severityMin: NotificationSeverity;
  eventTypesText: string;
  webhookUrl: string;
  token: string;
};

const INITIAL_DRAFT: ChannelDraft = {
  name: '',
  type: 'in_app',
  enabled: true,
  severityMin: 'warning',
  eventTypesText: '',
  webhookUrl: '',
  token: '',
};

const severityTone: Record<NotificationSeverity, string> = {
  info: 'border-cyan-300/25 bg-cyan-400/10 text-cyan-100',
  warning: 'border-amber-300/30 bg-amber-400/12 text-amber-100',
  critical: 'border-rose-300/35 bg-rose-500/14 text-rose-100',
};

function formatDate(value: string | null | undefined): string {
  return formatDateTimeValue(value);
}

function channelTarget(channel: NotificationChannel): string {
  if (channel.type === 'in_app') return 'Admin in-app inbox';
  const url = channel.config.webhookUrl || channel.config.webhook_url;
  return typeof url === 'string' && url ? url : 'Webhook target hidden';
}

function channelToken(channel: NotificationChannel): string | null {
  const token = channel.config.token || channel.config.secret;
  return typeof token === 'string' && token ? token : null;
}

function eventTypesText(channel: NotificationChannel): string {
  return channel.eventTypes.length ? channel.eventTypes.join(', ') : 'All event types';
}

const AdminNotificationsPage: React.FC = () => {
  const { language } = useI18n();
  const [channels, setChannels] = useState<NotificationChannel[]>([]);
  const [events, setEvents] = useState<NotificationEvent[]>([]);
  const [draft, setDraft] = useState<ChannelDraft>(INITIAL_DRAFT);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<ParsedApiError | null>(null);

  const loadAll = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [channelItems, eventPayload] = await Promise.all([
        adminNotificationsApi.listChannels(),
        adminNotificationsApi.listNotifications(),
      ]);
      setChannels(channelItems);
      setEvents(eventPayload.items || []);
    } catch (err) {
      setError(getParsedApiError(err));
      setChannels([]);
      setEvents([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    document.title = 'Admin Notifications - WolfyStock';
  }, []);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const payload = useMemo<NotificationChannelPayload>(() => {
    const config: Record<string, unknown> = {};
    if (draft.type === 'webhook') {
      config.webhookUrl = draft.webhookUrl.trim();
      if (draft.token.trim()) {
        config.token = draft.token.trim();
      }
    }
    return {
      name: draft.name.trim(),
      type: draft.type,
      enabled: draft.enabled,
      severityMin: draft.severityMin,
      eventTypes: draft.eventTypesText
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean),
      config,
    };
  }, [draft]);

  const createChannel = useCallback(async () => {
    setFormError(null);
    setNotice(null);
    if (!payload.name) {
      setFormError('Name is required.');
      return;
    }
    if (payload.type === 'webhook' && !String(payload.config.webhookUrl || '').trim()) {
      setFormError('Webhook URL is required.');
      return;
    }
    setIsSaving(true);
    try {
      await adminNotificationsApi.createChannel(payload);
      setDraft(INITIAL_DRAFT);
      setNotice('Channel saved.');
      await loadAll();
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setIsSaving(false);
    }
  }, [loadAll, payload]);

  const toggleChannel = useCallback(async (channel: NotificationChannel) => {
    setBusyId(channel.id);
    setNotice(null);
    try {
      await adminNotificationsApi.updateChannel(channel.id, { enabled: !channel.enabled });
      await loadAll();
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setBusyId(null);
    }
  }, [loadAll]);

  const testChannel = useCallback(async (channelId: number) => {
    setBusyId(channelId);
    setNotice(null);
    try {
      const response = await adminNotificationsApi.testChannel(channelId);
      setNotice(response.success ? 'Test notification accepted.' : (response.error || 'Test notification failed.'));
      await loadAll();
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setBusyId(null);
    }
  }, [loadAll]);

  const acknowledge = useCallback(async (eventId: number) => {
    setBusyId(eventId);
    setNotice(null);
    try {
      await adminNotificationsApi.acknowledgeNotification(eventId);
      await loadAll();
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setBusyId(null);
    }
  }, [loadAll]);

  return (
    <section data-testid="admin-notifications-workspace" className="flex min-h-0 w-full min-w-0 flex-1 flex-col gap-4 overflow-x-hidden">
      <GlassCard as="section" className="p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-emerald-200/70">Operational alerts</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">Admin notifications</h1>
            <p className="mt-1 max-w-3xl text-xs leading-5 text-secondary-text">
              Route Admin Logs, scanner, market data, and future provider alerts to in-app records or a controlled webhook.
            </p>
          </div>
          <button type="button" className="btn-secondary h-9 rounded-lg px-3 text-xs" onClick={() => void loadAll()} disabled={isLoading}>
            {isLoading ? 'Refreshing' : 'Refresh'}
          </button>
        </div>
      </GlassCard>

      {error ? <ApiErrorAlert error={error} /> : null}
      {notice ? <p className="rounded-lg border border-emerald-300/20 bg-emerald-400/10 px-3 py-2 text-xs text-emerald-100">{notice}</p> : null}

      <section className="grid min-h-0 grid-cols-1 gap-4 xl:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)]">
        <GlassCard as="form" className="space-y-3 p-4" onSubmit={(event) => {
          event.preventDefault();
          void createChannel();
        }}>
          <div>
            <h2 className="text-sm font-semibold text-foreground">Channel setup</h2>
            <p className="mt-1 text-xs text-muted-text">Create a low-risk in-app or webhook route. Secrets are masked after save.</p>
          </div>
          <label className="block space-y-1">
            <span className="text-xs font-semibold text-secondary-text">Channel name</span>
            <input
              aria-label="Channel name"
              className="input-surface h-9 w-full rounded-lg px-3 text-sm"
              value={draft.name}
              onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))}
            />
          </label>
          <label className="block space-y-1">
            <span className="text-xs font-semibold text-secondary-text">Channel type</span>
            <select
              aria-label="Channel type"
              className="input-surface h-9 w-full rounded-lg px-3 text-sm"
              value={draft.type}
              onChange={(event) => setDraft((current) => ({ ...current, type: event.target.value as NotificationChannelType }))}
            >
              <option value="in_app">In-app</option>
              <option value="webhook">Webhook</option>
            </select>
          </label>
          <label className="block space-y-1">
            <span className="text-xs font-semibold text-secondary-text">Minimum severity</span>
            <select
              aria-label="Minimum severity"
              className="input-surface h-9 w-full rounded-lg px-3 text-sm"
              value={draft.severityMin}
              onChange={(event) => setDraft((current) => ({ ...current, severityMin: event.target.value as NotificationSeverity }))}
            >
              <option value="info">info</option>
              <option value="warning">warning</option>
              <option value="critical">critical</option>
            </select>
          </label>
          <label className="block space-y-1">
            <span className="text-xs font-semibold text-secondary-text">Event types</span>
            <input
              aria-label="Event types"
              className="input-surface h-9 w-full rounded-lg px-3 text-sm"
              placeholder="admin_logs.storage, scanner.failure"
              value={draft.eventTypesText}
              onChange={(event) => setDraft((current) => ({ ...current, eventTypesText: event.target.value }))}
            />
          </label>
          {draft.type === 'webhook' ? (
            <>
              <label className="block space-y-1">
                <span className="text-xs font-semibold text-secondary-text">Webhook URL</span>
                <input
                  aria-label="Webhook URL"
                  className="input-surface h-9 w-full rounded-lg px-3 text-sm"
                  placeholder="https://hooks.example.test/..."
                  value={draft.webhookUrl}
                  onChange={(event) => setDraft((current) => ({ ...current, webhookUrl: event.target.value }))}
                />
              </label>
              <label className="block space-y-1">
                <span className="text-xs font-semibold text-secondary-text">Bearer token</span>
                <input
                  aria-label="Bearer token"
                  type="password"
                  className="input-surface h-9 w-full rounded-lg px-3 text-sm"
                  value={draft.token}
                  onChange={(event) => setDraft((current) => ({ ...current, token: event.target.value }))}
                />
              </label>
            </>
          ) : null}
          <label className="flex items-center gap-2 text-xs font-semibold text-secondary-text">
            <input
              type="checkbox"
              checked={draft.enabled}
              onChange={(event) => setDraft((current) => ({ ...current, enabled: event.target.checked }))}
            />
            Enabled
          </label>
          {formError ? <p className="text-xs text-rose-100">{formError}</p> : null}
          <button type="submit" className="btn-primary h-9 rounded-lg px-4 text-sm" disabled={isSaving}>
            {isSaving ? 'Saving' : 'Create channel'}
          </button>
        </GlassCard>

        <div className="grid min-h-0 grid-cols-1 gap-4">
          <GlassCard as="section" className="min-h-0 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-foreground">Channels</h2>
                <p className="mt-1 text-xs text-muted-text">{channels.length} configured routes</p>
              </div>
              <BellRing className="h-4 w-4 text-emerald-100/70" />
            </div>
            <div className="overflow-hidden rounded-xl border border-white/6 bg-black/15">
              <div className="divide-y divide-white/6">
                {channels.length ? channels.map((channel) => (
                  <div key={channel.id} data-testid={`notification-channel-${channel.id}`} className="grid gap-3 px-3 py-3 md:grid-cols-[minmax(9rem,1fr)_minmax(12rem,1.2fr)_8rem_9rem_10rem] md:items-center">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-foreground">{channel.name}</p>
                      <p className="mt-1 flex items-center gap-1 text-[11px] text-muted-text">
                        {channel.type === 'webhook' ? <Webhook className="h-3 w-3" /> : <BellRing className="h-3 w-3" />}
                        {channel.type}
                      </p>
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-xs text-secondary-text" title={channelTarget(channel)}>{channelTarget(channel)}</p>
                      {channelToken(channel) ? <p className="mt-1 truncate text-[11px] text-muted-text">{channelToken(channel)}</p> : null}
                      <p className="mt-1 truncate text-[11px] text-muted-text">{eventTypesText(channel)}</p>
                    </div>
                    <div>
                      <span className={cn('inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold', severityTone[channel.severityMin])}>{channel.severityMin}</span>
                      <p className={cn('mt-1 text-[11px]', channel.enabled ? 'text-emerald-100' : 'text-white/45')}>{channel.enabled ? 'enabled' : 'disabled'}</p>
                    </div>
                    <div className="text-[11px] text-muted-text">
                      <p>tested: {formatDate(channel.lastTestedAt)}</p>
                      <p>sent: {formatDate(channel.lastSentAt)}</p>
                      {channel.lastError ? <p className="truncate text-rose-100" title={channel.lastError}>{channel.lastError}</p> : null}
                    </div>
                    <div className="flex flex-wrap gap-2 md:justify-end">
                      <button
                        type="button"
                        className="btn-secondary h-8 rounded-lg px-3 text-xs"
                        onClick={() => void toggleChannel(channel)}
                        disabled={busyId === channel.id}
                      >
                        <Power className="h-3 w-3" />
                        {channel.enabled ? 'Disable' : 'Enable'}
                      </button>
                      <button
                        type="button"
                        className="btn-secondary h-8 rounded-lg px-3 text-xs"
                        onClick={() => void testChannel(channel.id)}
                        disabled={busyId === channel.id}
                      >
                        <Send className="h-3 w-3" />
                        Test
                      </button>
                    </div>
                  </div>
                )) : (
                  <p className="px-3 py-6 text-sm text-muted-text">No notification channels configured.</p>
                )}
              </div>
            </div>
          </GlassCard>

          <GlassCard as="section" className="min-h-0 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-foreground">Notifications</h2>
                <p className="mt-1 text-xs text-muted-text">Recent operational alert events and acknowledgement state.</p>
              </div>
              <CheckCircle2 className="h-4 w-4 text-emerald-100/70" />
            </div>
            <div className="overflow-hidden rounded-xl border border-white/6 bg-black/15">
              <div className="divide-y divide-white/6">
                {events.length ? events.map((event) => (
                  <div key={event.id} data-testid={`notification-event-${event.id}`} className="grid gap-3 px-3 py-3 md:grid-cols-[8rem_minmax(12rem,1fr)_9rem_7rem] md:items-center">
                    <p className="text-xs text-secondary-text">{formatDate(event.createdAt)}</p>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-foreground">{event.title}</p>
                      <p className="mt-1 truncate text-[11px] text-muted-text" title={event.message}>{event.eventType} · {event.deliveryStatus}</p>
                    </div>
                    <div>
                      <span className={cn('inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold', severityTone[event.severity])}>{event.severity}</span>
                      <p className="mt-1 text-[11px] text-muted-text">{event.acknowledgedAt ? `acknowledged ${formatDate(event.acknowledgedAt)}` : 'unacknowledged'}</p>
                    </div>
                    <div className="md:text-right">
                      <button
                        type="button"
                        className="btn-secondary h-8 rounded-lg px-3 text-xs"
                        onClick={() => void acknowledge(event.id)}
                        disabled={Boolean(event.acknowledgedAt) || busyId === event.id}
                      >
                        Acknowledge
                      </button>
                    </div>
                  </div>
                )) : (
                  <p className="px-3 py-6 text-sm text-muted-text">No notification events yet.</p>
                )}
              </div>
            </div>
          </GlassCard>
        </div>
      </section>
      <p className="sr-only">Current language: {language}</p>
    </section>
  );
};

export default AdminNotificationsPage;
