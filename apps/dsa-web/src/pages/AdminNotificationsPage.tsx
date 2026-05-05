import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { BellRing, CheckCircle2, Power, Send, ShieldCheck, Trash2, Webhook } from 'lucide-react';
import {
  adminNotificationsApi,
  type NotificationChannel,
  type NotificationChannelPayload,
  type NotificationChannelType,
  type NotificationEvent,
  type NotificationSeverity,
} from '../api/adminNotifications';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { ApiErrorAlert, Badge, Button, Checkbox, Disclosure, GlassCard, Input, Select } from '../components/common';
import { useI18n } from '../contexts/UiLanguageContext';
import { cn } from '../utils/cn';
import {
  describeAdminNotificationStatus,
  describeBooleanEnabled,
  type DisplayStatusTone,
} from '../utils/displayStatus';
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

const severityBadgeVariant: Record<NotificationSeverity, React.ComponentProps<typeof Badge>['variant']> = {
  info: 'info',
  warning: 'warning',
  critical: 'danger',
};

function severityLabel(value: NotificationSeverity, language: 'zh' | 'en'): string {
  if (language === 'en') return value;
  const labels: Record<NotificationSeverity, string> = {
    info: '信息',
    warning: '警告',
    critical: '严重',
  };
  return labels[value] || value;
}

function displayEventMessage(message: string | null | undefined, language: 'zh' | 'en'): string {
  const raw = String(message || '').trim();
  if (!raw || language !== 'zh') return raw;
  const normalized = raw.toLowerCase().replace(/[-\s]+/g, '_');
  if (normalized.includes('provider_timeout')) return '服务商请求超时';
  if (normalized.includes('provider_down')) return '服务商不可用';
  if (normalized.includes('provider_error')) return '服务商错误';
  if (normalized.includes('api_key')) return raw.replace(/api_key=\S+/gi, '凭据已脱敏');
  return raw;
}

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
  return language === 'en' ? 'Webhook target masked' : 'Webhook 目标已脱敏';
}

function eventTypesText(channel: NotificationChannel, language: 'zh' | 'en'): string {
  return channel.eventTypes.length ? channel.eventTypes.join(', ') : (language === 'en' ? 'All event types' : '全部事件类型');
}

function displayStatusBadgeVariant(tone: DisplayStatusTone): React.ComponentProps<typeof Badge>['variant'] {
  if (tone === 'success') return 'success';
  if (tone === 'warning') return 'warning';
  if (tone === 'danger') return 'danger';
  if (tone === 'info') return 'info';
  return 'default';
}

function coverageLabel(channel: NotificationChannel, language: 'zh' | 'en'): string {
  return `${language === 'en' ? 'Min level' : '最低级别'} ${severityLabel(channel.severityMin, language)} · ${eventTypesText(channel, language)}`;
}

function failureSummaryLabel(channel: NotificationChannel, deliveryError: StatusNotice | null, language: 'zh' | 'en'): string {
  if (deliveryError?.message) return deliveryError.message;
  const summary = String(channel.lastErrorSummary || '').toLowerCase();
  if (!summary) return language === 'en' ? 'No failure recorded' : '暂无失败记录';
  if (summary.includes('ssl')) return language === 'en' ? 'SSL certificate verification failed' : 'SSL 证书校验失败';
  if (summary.includes('timeout')) return language === 'en' ? 'Webhook delivery timed out' : 'Webhook 投递超时';
  if (summary.includes('webhook')) return language === 'en' ? 'Webhook delivery failed' : 'Webhook 投递失败';
  return language === 'en' ? channel.lastErrorSummary || 'Failed' : '失败';
}

function scopeLabel(channel: NotificationChannel, language: 'zh' | 'en'): string {
  const scope = String(channel.routeScope || 'log_notification_association');
  if (scope === 'log_notification_association') {
    return language === 'en' ? 'Log notification route' : '日志通知路由';
  }
  return language === 'en' ? 'Notification route' : '通知路由';
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

  const routeSummary = useMemo(() => {
    const enabledRoutes = channels.filter((channel) => channel.enabled).length;
    const disabledRoutes = channels.filter((channel) => !channel.enabled).length;
    const missingTargets = channels.filter((channel) => String(channel.targetSummary || '').includes('unconfigured')).length;
    const grouped = channels.reduce<Record<string, number>>((acc, channel) => {
      const key = channel.type === 'system_channel'
        ? `${text('Existing', '已有通道')}:${String(channel.config.channel || text('Unconfigured', '未配置'))}`
        : channel.type === 'webhook'
          ? text('Webhook route', 'Webhook 路由')
          : text('In-app route', '站内路由');
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    const categories = Array.from(new Set(channels.flatMap((channel) => (
      channel.eventTypes.length ? channel.eventTypes : [text('All event types', '全部事件类型')]
    ))));
    return {
      enabledRoutes,
      disabledRoutes,
      missingTargets,
      grouped,
      categories,
    };
  }, [channels, text]);

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

  const testChannel = useCallback(async (channelId: number, dryRun: boolean) => {
    setBusyId(channelId);
    setNotice(null);
    try {
      const response = await adminNotificationsApi.testChannel(channelId, { dryRun });
      if (response.success) {
        setNotice({
          tone: 'success',
          message: dryRun
            ? text('Dry run passed. No notification was sent.', '试运行通过，未发送真实通知。')
            : text('Test notification accepted.', '测试通知已发送。'),
        });
      } else {
        const failure = formatDeliveryError(language as 'zh' | 'en', response.error, response.errorCode, response.diagnostics);
        setNotice(failure || {
          tone: 'danger',
          message: dryRun ? text('Dry run failed.', '试运行失败。') : text('Test notification failed.', '测试通知失败。'),
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
    const confirmed = window.confirm(text(
      'Remove only this log notification route association? The configured system channel and credentials will not be deleted.',
      '仅解除日志路由绑定？这不会删除系统通道或已配置凭据。',
    ));
    if (!confirmed) return;
    setBusyId(channelId);
    setNotice(null);
    try {
      const response = await adminNotificationsApi.deleteChannel(channelId);
      setNotice({
        tone: 'success',
        message: response.deletedScope === 'log_notification_association'
          ? text('Only the log notification route binding was removed. The system channel remains configured.', '仅解除日志路由绑定；系统通道仍保留。')
          : text('Log notification route removed.', '日志通知关联已移除。'),
      });
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
          <Button type="button" variant="secondary" size="sm" onClick={() => void loadAll()} isLoading={isLoading} loadingText={text('Refreshing', '刷新中')}>
            {text('Refresh', '刷新')}
          </Button>
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
            <Disclosure
              className="mt-2 rounded-md border border-white/10 bg-black/10 px-2 py-1"
              summaryClassName="cursor-pointer text-[11px] uppercase tracking-[0.16em] text-secondary-text"
              bodyClassName="mt-2"
              summary={text('Developer details', '开发者细节')}
            >
              <pre className="mt-2 whitespace-pre-wrap break-words text-[11px] leading-5 text-secondary-text">{notice.rawMessage}</pre>
            </Disclosure>
          ) : null}
        </div>
      ) : null}

      <GlassCard as="section" className="p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-foreground">{text('Route coverage', '路由覆盖')}</h2>
            <p className="mt-1 text-xs text-muted-text">
              {channels.length
                ? text('Log notification rules mapped to safe operator channels.', '日志通知规则与安全运维通道的覆盖情况。')
                : text('No rules exist yet.', '暂无通知规则。')}
            </p>
          </div>
          <ShieldCheck className="h-4 w-4 text-emerald-100/70" />
        </div>
        <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-4">
          {[
            { label: text('Enabled', '已启用'), value: routeSummary.enabledRoutes, tone: 'text-emerald-100' },
            { label: text('Configured channels', '已配置通道'), value: channels.length, tone: 'text-white' },
            { label: text('Disabled', '已停用'), value: routeSummary.disabledRoutes, tone: 'text-white/55' },
            { label: text('Unconfigured', '未配置'), value: routeSummary.missingTargets, tone: routeSummary.missingTargets ? 'text-amber-100' : 'text-white/55' },
          ].map((item) => (
            <div key={item.label} className="rounded-xl border border-white/[0.06] bg-black/20 px-3 py-3">
              <p className="text-[11px] font-semibold text-muted-text">{item.label}</p>
              <p className={cn('mt-2 text-xl font-semibold', item.tone)}>{item.value}</p>
            </div>
          ))}
        </div>
        {channels.length ? (
          <div className="mt-3 grid gap-2 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <div className="rounded-xl border border-white/[0.06] bg-black/20 px-3 py-3">
              <p className="text-[11px] font-semibold text-muted-text">{text('Grouped routes', '路由分组')}</p>
              <p className="mt-2 break-words text-xs leading-5 text-secondary-text">
                {Object.entries(routeSummary.grouped).map(([label, count]) => `${label} × ${count}`).join(' · ')}
              </p>
            </div>
            <div className="rounded-xl border border-white/[0.06] bg-black/20 px-3 py-3">
              <p className="text-[11px] font-semibold text-muted-text">{text('Covered events', '覆盖事件')}</p>
              <p className="mt-2 break-words text-xs leading-5 text-secondary-text">
                {routeSummary.categories.join(' · ')}
              </p>
            </div>
          </div>
        ) : null}
      </GlassCard>

      <section className="grid min-h-0 grid-cols-1 gap-4 xl:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)]">
        <GlassCard as="form" className="space-y-3 p-4" onSubmit={(event) => {
          event.preventDefault();
          void createChannel();
        }}>
          <div>
            <h2 className="text-sm font-semibold text-foreground">{text('Channel setup', '通道设置')}</h2>
            <p className="mt-1 text-xs text-muted-text">{text('Create a low-risk in-app or webhook route. Secrets are masked after save.', '创建一个低风险的站内或 webhook 通道。保存后密钥会被遮罩。')}</p>
          </div>
          <Input
            label={text('Channel name', '通道名称')}
            value={draft.name}
            onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))}
          />
          <Select
            label={text('Channel type', '通道类型')}
            value={draft.type}
            onChange={(value) => setDraft((current) => ({ ...current, type: value as NotificationChannelType }))}
            options={[
              { value: 'system_channel', label: text('Existing channel', '已有通道') },
              { value: 'in_app', label: text('In-app', '站内') },
              { value: 'webhook', label: 'Webhook' },
            ]}
          />
          <Select
            label={text('Minimum severity', '最低严重级别')}
            value={draft.severityMin}
            onChange={(value) => setDraft((current) => ({ ...current, severityMin: value as NotificationSeverity }))}
            options={[
              { value: 'info', label: text('info', '信息') },
              { value: 'warning', label: text('warning', '警告') },
              { value: 'critical', label: text('critical', '严重') },
            ]}
          />
          <Input
            label={text('Event types', '事件类型')}
            placeholder="admin_logs.storage, scanner.failure"
            value={draft.eventTypesText}
            onChange={(event) => setDraft((current) => ({ ...current, eventTypesText: event.target.value }))}
          />
          {draft.type === 'system_channel' ? (
            <div className="space-y-1">
              <Select
                label={text('Existing notification channel', '已有通知通道')}
                value={draft.systemChannel}
                onChange={(value) => setDraft((current) => ({ ...current, systemChannel: value }))}
                options={(availableSystemChannels.length ? availableSystemChannels : SYSTEM_CHANNEL_OPTIONS).map((channel) => ({
                  value: channel,
                  label: channel,
                }))}
              />
              <p className="text-[11px] leading-4 text-muted-text">
                {text('Uses credentials already configured in System Settings.', '使用系统设置中已经配置的凭据。')}
              </p>
            </div>
          ) : null}
          {draft.type === 'webhook' ? (
            <>
              <Input
                label={text('Webhook URL', 'Webhook 地址')}
                placeholder="https://hooks.example.test/..."
                value={draft.webhookUrl}
                onChange={(event) => setDraft((current) => ({ ...current, webhookUrl: event.target.value }))}
              />
              <Input
                label={text('Bearer token', 'Bearer 令牌')}
                type="password"
                value={draft.token}
                onChange={(event) => setDraft((current) => ({ ...current, token: event.target.value }))}
              />
            </>
          ) : null}
          <Checkbox
            label={text('Enabled', '启用')}
            checked={draft.enabled}
            onChange={(event) => setDraft((current) => ({ ...current, enabled: event.target.checked }))}
            containerClassName="min-h-[40px] rounded-lg border border-white/[0.06] bg-black/10 px-3 py-2"
          />
          {formError ? <p className="text-xs text-rose-100">{formError}</p> : null}
          <Button type="submit" variant="primary" size="md" isLoading={isSaving} loadingText={text('Saving', '保存中')} className="w-full">
            {text('Create channel', '创建通道')}
          </Button>
        </GlassCard>

        <div className="grid min-h-0 grid-cols-1 gap-4">
          <GlassCard as="section" className="min-h-0 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-foreground">{text('Notification rules', '通知规则')}</h2>
                <p className="mt-1 text-xs text-muted-text">{text(`${channels.length} configured routes`, `${channels.length} 条已配置路由`)}</p>
              </div>
              <BellRing className="h-4 w-4 text-emerald-100/70" />
            </div>
            <div className="overflow-hidden rounded-xl border border-white/6 bg-black/15">
              <div className="divide-y divide-white/6">
                {channels.length ? channels.map((channel) => {
                  const deliveryError = formatDeliveryError(language as 'zh' | 'en', channel.lastError, channel.lastErrorCode, channel.lastErrorDiagnostics);
                  const enabledStatus = describeBooleanEnabled(channel.enabled, { language: language as 'zh' | 'en' });
                  const lastStatus = describeAdminNotificationStatus(channel.lastStatus, { language: language as 'zh' | 'en' });

                  return (
                  <div key={channel.id} data-testid={`notification-channel-${channel.id}`} className="grid gap-3 px-3 py-3 lg:grid-cols-[minmax(12rem,1fr)_minmax(16rem,1.4fr)_minmax(11rem,0.8fr)_minmax(13rem,0.9fr)] lg:items-start">
                    <div className="min-w-0 space-y-2">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-foreground">{channel.name}</p>
                        <p className="mt-1 flex items-center gap-1 text-[11px] text-muted-text">
                          {channel.type === 'webhook' ? <Webhook className="h-3 w-3" /> : <BellRing className="h-3 w-3" />}
                          {scopeLabel(channel, language as 'zh' | 'en')} · {channel.type === 'system_channel'
                            ? text('Existing channel', '已有通道')
                            : channel.type === 'webhook'
                              ? text('Webhook', 'Webhook')
                              : text('In-app', '站内')}
                        </p>
                      </div>
                      <Badge variant={displayStatusBadgeVariant(enabledStatus.tone)}>
                        {enabledStatus.label}
                      </Badge>
                    </div>
                    <div className="min-w-0 rounded-xl border border-white/[0.04] bg-black/20 px-3 py-2">
                      <p className="text-[11px] font-semibold text-muted-text">{text('Route coverage', '路由覆盖')}</p>
                      <p className="mt-1 break-words text-xs leading-5 text-secondary-text">{coverageLabel(channel, language as 'zh' | 'en')}</p>
                      <p className="mt-2 text-[11px] font-semibold text-muted-text">{text('Destination', '目标通道')}</p>
                      <p className="mt-1 break-words text-xs leading-5 text-secondary-text">{channelTarget(channel, language as 'zh' | 'en')}</p>
                    </div>
                    <div className="min-w-0 space-y-2 text-[11px] text-muted-text">
                      <div>
                        <Badge variant={severityBadgeVariant[channel.severityMin]}>
                          {severityLabel(channel.severityMin, language as 'zh' | 'en')}
                        </Badge>
                      </div>
                      <p>
                        {text('Last trigger', '最近触发')}: <span className="text-secondary-text">{formatDate(channel.lastTriggeredAt || channel.lastSentAt)}</span>
                      </p>
                      <p>
                        {text('Last status', '最近状态')}: <Badge variant={displayStatusBadgeVariant(lastStatus.tone)}>{lastStatus.label}</Badge>
                      </p>
                      <p>
                        {text('Last failure', '最近失败')}: <span className="text-secondary-text">{failureSummaryLabel(channel, deliveryError, language as 'zh' | 'en')}</span>
                      </p>
                    </div>
                    <div className="flex min-w-0 flex-wrap gap-2 lg:justify-end">
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={() => void testChannel(channel.id, true)}
                        disabled={busyId === channel.id}
                      >
                        <ShieldCheck className="h-3 w-3" />
                        {text('Dry run', '仅验证')}
                      </Button>
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={() => void toggleChannel(channel)}
                        disabled={busyId === channel.id}
                      >
                        <Power className="h-3 w-3" />
                        {channel.enabled ? text('Disable', '停用') : text('Enable', '启用')}
                      </Button>
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={() => void testChannel(channel.id, false)}
                        disabled={busyId === channel.id}
                      >
                        <Send className="h-3 w-3" />
                        {text('Test send', '测试发送')}
                      </Button>
                      <Button
                        type="button"
                        variant="danger-subtle"
                        size="sm"
                        onClick={() => void deleteChannel(channel.id)}
                        disabled={busyId === channel.id}
                        title={text('Only unbind the log notification route; system channel is not deleted.', '仅解除日志路由绑定；不会删除系统通道。')}
                      >
                        <Trash2 className="h-3 w-3" />
                        {text('Unbind', '解除绑定')}
                      </Button>
                      <p className="basis-full text-[11px] leading-4 text-muted-text lg:text-right">
                        {text('Only removes the log route binding. The system channel is not deleted.', '仅解除日志路由绑定，不会删除系统通道。')}
                      </p>
                    </div>
                  </div>
                ); }) : (
                  <p className="px-3 py-6 text-sm text-muted-text">{text('No notification rules configured.', '暂无通知规则。')}</p>
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
                      <p className="mt-1 truncate text-[11px] text-muted-text" title={displayEventMessage(event.message, language as 'zh' | 'en')}>{event.eventType} · {describeAdminNotificationStatus(event.deliveryStatus, { language: language as 'zh' | 'en' }).label}</p>
                    </div>
                    <div>
                      <Badge variant={severityBadgeVariant[event.severity]}>{severityLabel(event.severity, language as 'zh' | 'en')}</Badge>
                      <p className="mt-1 text-[11px] text-muted-text">{acknowledgedLabel(event.acknowledgedAt, language as 'zh' | 'en')}</p>
                    </div>
                    <div className="md:text-right">
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={() => void acknowledge(event.id)}
                        disabled={Boolean(event.acknowledgedAt) || busyId === event.id}
                      >
                        {text('Acknowledge', '确认')}
                      </Button>
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
