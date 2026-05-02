import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { BellRing, CheckCircle2, Power, Send, Trash2, Webhook } from 'lucide-react';
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
  systemChannel: string;
  webhookUrl: string;
  token: string;
};

type StatusNotice = {
  tone: 'success' | 'danger';
  message: string;
  details?: string[];
  rawMessage?: string | null;
};

const INITIAL_DRAFT: ChannelDraft = {
  name: '',
  type: 'system_channel',
  enabled: true,
  severityMin: 'warning',
  eventTypesText: '',
  systemChannel: 'discord',
  webhookUrl: '',
  token: '',
};

const SYSTEM_CHANNEL_OPTIONS = ['wechat', 'feishu', 'telegram', 'email', 'pushover', 'pushplus', 'serverchan3', 'custom', 'discord', 'slack', 'astrbot'];

const severityTone: Record<NotificationSeverity, string> = {
  info: 'border-cyan-300/25 bg-cyan-400/10 text-cyan-100',
  warning: 'border-amber-300/30 bg-amber-400/12 text-amber-100',
  critical: 'border-rose-300/35 bg-rose-500/14 text-rose-100',
};

function isSslDeliveryError(message?: string | null, code?: string | null): boolean {
  const text = `${code || ''} ${message || ''}`.toLowerCase();
  return /ssl_certificate_verify_failed|certificate verify failed|ssl certificate verification failed|ssl 证书|证书.*验证失败|证书校验失败/.test(text);
}

function formatDeliveryError(
  language: 'zh' | 'en',
  message?: string | null,
  code?: string | null,
  diagnostics?: Record<string, unknown>,
): StatusNotice | null {
  const rawMessage = String(message || '').trim();
  if (!rawMessage) {
    return null;
  }

  const troubleshooting = Array.isArray(diagnostics?.troubleshooting)
    ? diagnostics.troubleshooting.map((item) => String(item)).filter(Boolean)
    : [];

  if (isSslDeliveryError(rawMessage, code)) {
    if (language === 'en') {
      return {
        tone: 'danger',
        message: 'Webhook SSL certificate verification failed.',
        details: troubleshooting.length > 0 ? troubleshooting : [
          'Check the certificate chain, trusted CA, and hostname.',
          'Self-signed, expired, or proxy-rewritten TLS certificates can all trigger this failure.',
          'Confirm the TLS handshake succeeds from the server or proxy that reaches the webhook URL.',
        ],
        rawMessage,
      };
    }

    return {
      tone: 'danger',
      message: 'Webhook SSL 证书校验失败。',
      details: troubleshooting.length > 0 ? troubleshooting : [
        '请检查证书链、受信任 CA 和主机名是否匹配。',
        '自签名证书、过期证书或中间代理改写 TLS 证书链都可能导致校验失败。',
        '请在服务器或代理侧确认该 webhook URL 的 TLS 握手可以通过。',
      ],
      rawMessage,
    };
  }

  if (code === 'webhook_timeout' || /timeout|超时/i.test(rawMessage)) {
    return {
      tone: 'danger',
      message: language === 'en'
        ? 'Webhook delivery timed out.'
        : 'Webhook 投递超时。',
      details: language === 'en'
        ? [
          'Check the target service, DNS, proxy, and upstream latency.',
          'If the endpoint is behind a gateway, make sure the request can complete within the timeout window.',
        ]
        : [
          '请检查目标服务、DNS、代理和上游延迟。',
          '如果 webhook 目标位于网关之后，请确认请求能够在超时时间内完成。',
        ],
      rawMessage,
    };
  }

  if (code === 'webhook_delivery_failed') {
    return {
      tone: 'danger',
      message: language === 'en'
        ? 'Webhook delivery failed.'
        : 'Webhook 投递失败。',
      details: language === 'en'
        ? [
          'Check the target service, URL, credentials, and network connectivity.',
          'Use the raw diagnostic below if the target returned a specific HTTP status or payload error.',
        ]
        : [
          '请检查目标服务、URL、认证凭据和网络连通性。',
          '如果目标返回了具体的 HTTP 状态码或载荷错误，请继续参考下方原始诊断。',
        ],
      rawMessage,
    };
  }

  return {
    tone: 'danger',
    message: rawMessage,
    rawMessage,
    details: diagnostics && Object.keys(diagnostics).length > 0
      ? [JSON.stringify(diagnostics)]
      : undefined,
  };
}

function formatDate(value: string | null | undefined): string {
  return formatDateTimeValue(value);
}

function channelTarget(channel: NotificationChannel, language: 'zh' | 'en'): string {
  if (channel.type === 'in_app') return language === 'en' ? 'Admin in-app inbox' : '管理员站内收件箱';
  if (channel.type === 'system_channel') {
    const systemChannel = channel.config.channel;
    return typeof systemChannel === 'string' && systemChannel
      ? `${language === 'en' ? 'Existing system channel' : '已有系统通道'}: ${systemChannel}`
      : (language === 'en' ? 'Existing system channel' : '已有系统通道');
  }
  const url = channel.config.webhookUrl || channel.config.webhook_url;
  return typeof url === 'string' && url ? url : (language === 'en' ? 'Webhook target hidden' : 'Webhook 目标已隐藏');
}

function channelToken(channel: NotificationChannel): string | null {
  const token = channel.config.token || channel.config.secret;
  return typeof token === 'string' && token ? token : null;
}

function eventTypesText(channel: NotificationChannel, language: 'zh' | 'en'): string {
  return channel.eventTypes.length ? channel.eventTypes.join(', ') : (language === 'en' ? 'All event types' : '全部事件类型');
}

function deliveryStatusLabel(status: string, language: 'zh' | 'en'): string {
  const normalized = String(status || '').toLowerCase();
  if (normalized === 'delivered') return language === 'en' ? 'Delivered' : '已投递';
  if (normalized === 'partial') return language === 'en' ? 'Partially delivered' : '部分投递';
  if (normalized === 'failed') return language === 'en' ? 'Delivery failed' : '投递失败';
  if (normalized === 'no_channels') return language === 'en' ? 'No matching channels' : '无匹配通道';
  if (normalized === 'pending') return language === 'en' ? 'Pending' : '待处理';
  return status;
}

function acknowledgedLabel(value: string | null | undefined, language: 'zh' | 'en'): string {
  return value
    ? `${language === 'en' ? 'Acknowledged' : '已确认'} ${formatDate(value)}`
    : (language === 'en' ? 'Unacknowledged' : '未确认');
}

const AdminNotificationsPage: React.FC = () => {
  const { language } = useI18n();
  const isEnglish = language === 'en';
  const text = useCallback((en: string, zh: string) => (isEnglish ? en : zh), [isEnglish]);
  const [channels, setChannels] = useState<NotificationChannel[]>([]);
  const [availableSystemChannels, setAvailableSystemChannels] = useState<string[]>([]);
  const [events, setEvents] = useState<NotificationEvent[]>([]);
  const [draft, setDraft] = useState<ChannelDraft>(INITIAL_DRAFT);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<StatusNotice | null>(null);
  const [error, setError] = useState<ParsedApiError | null>(null);

  const loadAll = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [channelPayload, eventPayload] = await Promise.all([
        adminNotificationsApi.listChannels(),
        adminNotificationsApi.listNotifications(),
      ]);
      setChannels(channelPayload.items);
      setAvailableSystemChannels(channelPayload.availableSystemChannels);
      if (channelPayload.availableSystemChannels.length) {
        setDraft((current) => (
          channelPayload.availableSystemChannels.includes(current.systemChannel)
            ? current
            : { ...current, systemChannel: channelPayload.availableSystemChannels[0] }
        ));
      }
      setEvents(eventPayload.items || []);
    } catch (err) {
      setError(getParsedApiError(err));
      setChannels([]);
      setAvailableSystemChannels([]);
      setEvents([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    document.title = isEnglish ? 'Admin Notifications - WolfyStock' : '管理通知 - WolfyStock';
  }, [isEnglish]);

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
    } else if (draft.type === 'system_channel') {
      config.channel = draft.systemChannel.trim();
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
      setFormError(text('Name is required.', '名称为必填项。'));
      return;
    }
    if (payload.type === 'webhook' && !String(payload.config.webhookUrl || '').trim()) {
      setFormError(text('Webhook URL is required.', 'Webhook URL 为必填项。'));
      return;
    }
    if (payload.type === 'system_channel' && !String(payload.config.channel || '').trim()) {
      setFormError(text('Existing channel is required.', '已有通道为必填项。'));
      return;
    }
    setIsSaving(true);
    try {
      await adminNotificationsApi.createChannel(payload);
      setDraft(INITIAL_DRAFT);
      setNotice({ tone: 'success', message: text('Channel saved.', '通道已保存。') });
      await loadAll();
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setIsSaving(false);
    }
  }, [loadAll, payload, text]);

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
      if (response.success) {
        setNotice({ tone: 'success', message: text('Test notification accepted.', '测试通知已发送。') });
      } else {
        const failure = formatDeliveryError(language as 'zh' | 'en', response.error, response.errorCode, response.diagnostics);
        setNotice(failure || {
          tone: 'danger',
          message: text('Test notification failed.', '测试通知失败。'),
          rawMessage: response.error || null,
        });
      }
      await loadAll();
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setBusyId(null);
    }
  }, [language, loadAll, text]);

  const deleteChannel = useCallback(async (channelId: number) => {
    setBusyId(channelId);
    setNotice(null);
    try {
      await adminNotificationsApi.deleteChannel(channelId);
      setNotice({ tone: 'success', message: text('Log notification route removed.', '日志通知关联已移除。') });
      await loadAll();
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setBusyId(null);
    }
  }, [loadAll, text]);

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
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-emerald-200/70">{text('Operational alerts', '运维告警')}</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">{text('Admin notifications', '管理员通知')}</h1>
            <p className="mt-1 max-w-3xl text-xs leading-5 text-secondary-text">
              {text(
                'Route Admin Logs, scanner, market data, and future provider alerts to in-app records or a controlled webhook.',
                '将管理员日志、扫描器、市场数据和后续的供应商告警路由到站内记录或受控 webhook。',
              )}
            </p>
          </div>
          <button type="button" className="btn-secondary h-9 rounded-lg px-3 text-xs" onClick={() => void loadAll()} disabled={isLoading}>
            {isLoading ? text('Refreshing', '刷新中') : text('Refresh', '刷新')}
          </button>
        </div>
      </GlassCard>

      {error ? <ApiErrorAlert error={error} /> : null}
      {notice ? (
        <div className={cn('rounded-lg border px-3 py-2 text-xs', notice.tone === 'success' ? 'border-emerald-300/20 bg-emerald-400/10 text-emerald-100' : 'border-rose-300/20 bg-rose-500/10 text-rose-100')}>
          <p>{notice.message}</p>
          {notice.details?.length ? (
            <ul className="mt-2 space-y-1 text-[11px] leading-5 opacity-90">
              {notice.details.map((detail) => (
                <li key={detail}>• {detail}</li>
              ))}
            </ul>
          ) : null}
          {notice.rawMessage && notice.rawMessage !== notice.message ? (
            <details className="mt-2 rounded-md border border-white/10 bg-black/10 px-2 py-1">
              <summary className="cursor-pointer text-[11px] uppercase tracking-[0.16em] text-secondary-text">
                {text('View raw diagnostic', '查看原始诊断')}
              </summary>
              <pre className="mt-2 whitespace-pre-wrap break-words text-[11px] leading-5 text-secondary-text">{notice.rawMessage}</pre>
            </details>
          ) : null}
        </div>
      ) : null}

      <section className="grid min-h-0 grid-cols-1 gap-4 xl:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)]">
        <GlassCard as="form" className="space-y-3 p-4" onSubmit={(event) => {
          event.preventDefault();
          void createChannel();
        }}>
          <div>
            <h2 className="text-sm font-semibold text-foreground">{text('Channel setup', '通道设置')}</h2>
            <p className="mt-1 text-xs text-muted-text">{text('Create a low-risk in-app or webhook route. Secrets are masked after save.', '创建一个低风险的站内或 webhook 通道。保存后密钥会被遮罩。')}</p>
          </div>
          <label className="block space-y-1">
            <span className="text-xs font-semibold text-secondary-text">{text('Channel name', '通道名称')}</span>
            <input
              aria-label={text('Channel name', '通道名称')}
              className="input-surface h-9 w-full rounded-lg px-3 text-sm"
              value={draft.name}
              onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))}
            />
          </label>
          <label className="block space-y-1">
            <span className="text-xs font-semibold text-secondary-text">{text('Channel type', '通道类型')}</span>
            <select
              aria-label={text('Channel type', '通道类型')}
              className="input-surface h-9 w-full rounded-lg px-3 text-sm"
              value={draft.type}
              onChange={(event) => setDraft((current) => ({ ...current, type: event.target.value as NotificationChannelType }))}
            >
              <option value="system_channel">{text('Existing channel', '已有通道')}</option>
              <option value="in_app">{text('In-app', '站内')}</option>
              <option value="webhook">Webhook</option>
            </select>
          </label>
          <label className="block space-y-1">
            <span className="text-xs font-semibold text-secondary-text">{text('Minimum severity', '最低严重级别')}</span>
            <select
              aria-label={text('Minimum severity', '最低严重级别')}
              className="input-surface h-9 w-full rounded-lg px-3 text-sm"
              value={draft.severityMin}
              onChange={(event) => setDraft((current) => ({ ...current, severityMin: event.target.value as NotificationSeverity }))}
            >
              <option value="info">{text('info', '信息')}</option>
              <option value="warning">{text('warning', '警告')}</option>
              <option value="critical">{text('critical', '严重')}</option>
            </select>
          </label>
          <label className="block space-y-1">
            <span className="text-xs font-semibold text-secondary-text">{text('Event types', '事件类型')}</span>
            <input
              aria-label={text('Event types', '事件类型')}
              className="input-surface h-9 w-full rounded-lg px-3 text-sm"
              placeholder="admin_logs.storage, scanner.failure"
              value={draft.eventTypesText}
              onChange={(event) => setDraft((current) => ({ ...current, eventTypesText: event.target.value }))}
            />
          </label>
          {draft.type === 'system_channel' ? (
            <label className="block space-y-1">
              <span className="text-xs font-semibold text-secondary-text">{text('Existing notification channel', '已有通知通道')}</span>
              <select
                aria-label={text('Existing notification channel', '已有通知通道')}
                className="input-surface h-9 w-full rounded-lg px-3 text-sm"
                value={draft.systemChannel}
                onChange={(event) => setDraft((current) => ({ ...current, systemChannel: event.target.value }))}
              >
                {(availableSystemChannels.length ? availableSystemChannels : SYSTEM_CHANNEL_OPTIONS).map((channel) => (
                  <option key={channel} value={channel}>{channel}</option>
                ))}
              </select>
              <p className="text-[11px] leading-4 text-muted-text">
                {text('Uses credentials already configured in System Settings.', '使用系统设置中已经配置的凭据。')}
              </p>
            </label>
          ) : null}
          {draft.type === 'webhook' ? (
            <>
              <label className="block space-y-1">
                <span className="text-xs font-semibold text-secondary-text">{text('Webhook URL', 'Webhook 地址')}</span>
                <input
                  aria-label={text('Webhook URL', 'Webhook 地址')}
                  className="input-surface h-9 w-full rounded-lg px-3 text-sm"
                  placeholder="https://hooks.example.test/..."
                  value={draft.webhookUrl}
                  onChange={(event) => setDraft((current) => ({ ...current, webhookUrl: event.target.value }))}
                />
              </label>
              <label className="block space-y-1">
                <span className="text-xs font-semibold text-secondary-text">{text('Bearer token', 'Bearer 令牌')}</span>
                <input
                  aria-label={text('Bearer token', 'Bearer 令牌')}
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
            {text('Enabled', '启用')}
          </label>
          {formError ? <p className="text-xs text-rose-100">{formError}</p> : null}
          <button type="submit" className="btn-primary h-9 rounded-lg px-4 text-sm" disabled={isSaving}>
            {isSaving ? text('Saving', '保存中') : text('Create channel', '创建通道')}
          </button>
        </GlassCard>

        <div className="grid min-h-0 grid-cols-1 gap-4">
          <GlassCard as="section" className="min-h-0 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-foreground">{text('Channels', '通知通道')}</h2>
                <p className="mt-1 text-xs text-muted-text">{text(`${channels.length} configured routes`, `${channels.length} 个已配置通道`)}</p>
              </div>
              <BellRing className="h-4 w-4 text-emerald-100/70" />
            </div>
            <div className="overflow-hidden rounded-xl border border-white/6 bg-black/15">
              <div className="divide-y divide-white/6">
                {channels.length ? channels.map((channel) => {
                  const deliveryError = formatDeliveryError(language as 'zh' | 'en', channel.lastError, channel.lastErrorCode, channel.lastErrorDiagnostics);

                  return (
                  <div key={channel.id} data-testid={`notification-channel-${channel.id}`} className="grid gap-3 px-3 py-3 md:grid-cols-[minmax(9rem,1fr)_minmax(12rem,1.2fr)_8rem_9rem_13rem] md:items-center">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-foreground">{channel.name}</p>
                      <p className="mt-1 flex items-center gap-1 text-[11px] text-muted-text">
                        {channel.type === 'webhook' ? <Webhook className="h-3 w-3" /> : <BellRing className="h-3 w-3" />}
                        {channel.type === 'system_channel'
                          ? text('Existing channel', '已有通道')
                          : channel.type === 'webhook'
                            ? text('Webhook', 'Webhook')
                            : text('In-app', '站内')}
                      </p>
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-xs text-secondary-text" title={channelTarget(channel, language as 'zh' | 'en')}>{channelTarget(channel, language as 'zh' | 'en')}</p>
                      {channelToken(channel) ? <p className="mt-1 truncate text-[11px] text-muted-text">{channelToken(channel)}</p> : null}
                      <p className="mt-1 truncate text-[11px] text-muted-text">{eventTypesText(channel, language as 'zh' | 'en')}</p>
                      {deliveryError ? (
                        <div className="mt-2 space-y-1 text-[11px] leading-5 text-rose-100">
                          <p className="truncate" title={channel.lastError || undefined}>
                            {deliveryError.message}
                          </p>
                          {deliveryError.details?.length ? (
                            <ul className="space-y-1 opacity-90">
                              {deliveryError.details.slice(0, 2).map((detail) => (
                                <li key={detail}>• {detail}</li>
                              ))}
                            </ul>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                    <div>
                      <span className={cn('inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold', severityTone[channel.severityMin])}>{channel.severityMin}</span>
                      <p className={cn('mt-1 text-[11px]', channel.enabled ? 'text-emerald-100' : 'text-white/45')}>{channel.enabled ? text('Enabled', '已启用') : text('Disabled', '已禁用')}</p>
                    </div>
                    <div className="text-[11px] text-muted-text">
                      <p>{text('Tested', '最近测试')}: {formatDate(channel.lastTestedAt)}</p>
                      <p>{text('Sent', '最近投递')}: {formatDate(channel.lastSentAt)}</p>
                    </div>
                    <div className="flex flex-wrap gap-2 md:justify-end">
                      <button
                        type="button"
                        className="btn-secondary h-8 rounded-lg px-3 text-xs"
                        onClick={() => void toggleChannel(channel)}
                        disabled={busyId === channel.id}
                      >
                        <Power className="h-3 w-3" />
                        {channel.enabled ? text('Disable', '停用') : text('Enable', '启用')}
                      </button>
                      <button
                        type="button"
                        className="btn-secondary h-8 rounded-lg px-3 text-xs"
                        onClick={() => void testChannel(channel.id)}
                        disabled={busyId === channel.id}
                      >
                        <Send className="h-3 w-3" />
                        {text('Test', '测试')}
                      </button>
                      {channel.enabled ? (
                        <button
                          type="button"
                          className="btn-secondary h-8 rounded-lg px-3 text-xs text-rose-100"
                          onClick={() => void deleteChannel(channel.id)}
                          disabled={busyId === channel.id}
                          title={text('Remove this route from log notifications only', '仅从日志通知中移除此关联')}
                        >
                          <Trash2 className="h-3 w-3" />
                          {text('Delete', '删除')}
                        </button>
                      ) : null}
                    </div>
                  </div>
                ); }) : (
                  <p className="px-3 py-6 text-sm text-muted-text">{text('No notification channels configured.', '暂无通知通道。')}</p>
                )}
              </div>
            </div>
          </GlassCard>

          <GlassCard as="section" className="min-h-0 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-foreground">{text('Notifications', '通知事件')}</h2>
                <p className="mt-1 text-xs text-muted-text">{text('Recent operational alert events and acknowledgement state.', '最近的运维告警事件与确认状态。')}</p>
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
                      <p className="mt-1 truncate text-[11px] text-muted-text" title={event.message}>{event.eventType} · {deliveryStatusLabel(event.deliveryStatus, language as 'zh' | 'en')}</p>
                    </div>
                    <div>
                      <span className={cn('inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold', severityTone[event.severity])}>{event.severity}</span>
                      <p className="mt-1 text-[11px] text-muted-text">{acknowledgedLabel(event.acknowledgedAt, language as 'zh' | 'en')}</p>
                    </div>
                    <div className="md:text-right">
                      <button
                        type="button"
                        className="btn-secondary h-8 rounded-lg px-3 text-xs"
                        onClick={() => void acknowledge(event.id)}
                        disabled={Boolean(event.acknowledgedAt) || busyId === event.id}
                      >
                        {text('Acknowledge', '确认')}
                      </button>
                    </div>
                  </div>
                )) : (
                  <p className="px-3 py-6 text-sm text-muted-text">{text('No notification events yet.', '暂无通知事件。')}</p>
                )}
              </div>
            </div>
          </GlassCard>
        </div>
      </section>
      <p className="sr-only">{text('Current language:', '当前语言：')} {language}</p>
    </section>
  );
};

export default AdminNotificationsPage;
