import type React from 'react';
import { useCallback, useEffect, useState } from 'react';
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
import { ApiErrorAlert } from '../components/common/ApiErrorAlert';
import { Checkbox } from '../components/common/Checkbox';
import { Input } from '../components/common/Input';
import { Select } from '../components/common/Select';
import {
  TerminalButton,
  TerminalChip,
  TerminalDenseList,
  TerminalDisclosure,
  TerminalEmptyState,
  TerminalGrid,
  TerminalMetric,
  TerminalNestedBlock,
  TerminalNotice,
  TerminalPageHeading,
  TerminalPageShell,
  TerminalPanel,
  TerminalSectionHeader,
} from '../components/terminal/TerminalPrimitives';
import AdminOpsL0OverviewStrip, { type AdminOpsTrustState } from '../components/admin/AdminOpsL0OverviewStrip';
import { useI18n } from '../contexts/UiLanguageContext';
import { useProductSurface } from '../hooks/useProductSurface';
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
  diagnosticDetails?: string | null;
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

type TerminalChipVariant = React.ComponentProps<typeof TerminalChip>['variant'];

const severityChipVariant: Record<NotificationSeverity, TerminalChipVariant> = {
  info: 'info',
  warning: 'caution',
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

const DELIVERY_SECRET_KEY_PATTERN = /(token|secret|password|cookie|session|authorization|bearer|credential|api[_-]?key|webhook|url|payload|raw|body|trace|stack|prompt)/i;
const DELIVERY_SECRET_VALUE_PATTERN = /(https?:\/\/|www\.|token=|api[_-]?key=|secret=|password=|cookie=|authorization|bearer\s+|payload|traceback|stack trace|internal_|diagnostic[_-]?ref|backend[_-]?field|provider)/i;

function sanitizeDeliveryText(value: unknown, fallback: string): string {
  const text = String(value ?? '').trim();
  if (!text) return fallback;
  if (DELIVERY_SECRET_VALUE_PATTERN.test(text)) return fallback;
  return text.slice(0, 180);
}

function sanitizeTroubleshooting(items: unknown, fallback: string[]): string[] {
  if (!Array.isArray(items)) return fallback;
  const sanitized = items.flatMap((item) => {
    const text = sanitizeDeliveryText(item, '');
    return text ? [text] : [];
  });
  return sanitized.length ? sanitized : fallback;
}

function summarizeDeliveryDiagnostics(diagnostics?: Record<string, unknown>): string | null {
  if (!diagnostics || !Object.keys(diagnostics).length) return null;
  const safeEntries = Object.entries(diagnostics)
    .filter(([key]) => !DELIVERY_SECRET_KEY_PATTERN.test(key))
    .flatMap(([key, value]) => {
      if (value === null || value === undefined || typeof value === 'object') return [];
      const safeValue = sanitizeDeliveryText(value, '');
      return safeValue ? [[key, safeValue] as const] : [];
    })
    .slice(0, 6);
  if (!safeEntries.length) return null;
  return JSON.stringify(Object.fromEntries(safeEntries), null, 2);
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
  const safeRawMessage = sanitizeDeliveryText(
    rawMessage,
    language === 'en' ? 'Delivery error details were redacted.' : '投递错误细节已脱敏。',
  );
  const diagnosticDetails = summarizeDeliveryDiagnostics(diagnostics);
  const sslFallback = language === 'en'
    ? [
      'Check the certificate chain, trusted CA, and hostname.',
      'Self-signed, expired, or proxy-rewritten TLS certificates can all trigger this failure.',
      'Confirm the TLS handshake succeeds from the server or proxy that reaches the webhook URL.',
    ]
    : [
      '请检查证书链、受信任 CA 和主机名是否匹配。',
      '自签名证书、过期证书或中间代理改写 TLS 证书链都可能导致校验失败。',
      '请在服务器或代理侧确认该 webhook URL 的 TLS 握手可以通过。',
    ];
  const troubleshooting = sanitizeTroubleshooting(diagnostics?.troubleshooting, sslFallback);

  if (isSslDeliveryError(rawMessage, code)) {
    if (language === 'en') {
      return {
        tone: 'danger',
        message: 'Webhook SSL certificate verification failed.',
        details: troubleshooting,
        rawMessage: safeRawMessage,
      };
    }

    return {
      tone: 'danger',
      message: 'Webhook SSL 证书校验失败。',
      details: troubleshooting,
      rawMessage: safeRawMessage,
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
      rawMessage: safeRawMessage,
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
          'Use the sanitized diagnostic below if the target returned a specific HTTP status.',
        ]
        : [
          '请检查目标服务、URL、认证凭据和网络连通性。',
          '如果目标返回了具体的 HTTP 状态码，请继续参考下方脱敏诊断。',
        ],
      rawMessage: safeRawMessage,
    };
  }

  return {
    tone: 'danger',
    message: language === 'en'
      ? 'Notification delivery failed.'
      : '通知投递失败。',
    rawMessage: safeRawMessage,
    details: language === 'en'
      ? ['Review the collapsed operator diagnostics before retrying this route.']
      : ['请先展开下方运维诊断并核对后，再重试该路由。'],
    diagnosticDetails,
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

function displayStatusChipVariant(tone: DisplayStatusTone): TerminalChipVariant {
  if (tone === 'success') return 'success';
  if (tone === 'warning') return 'caution';
  if (tone === 'danger') return 'danger';
  if (tone === 'info') return 'info';
  return 'neutral';
}

function noticeVariant(tone: StatusNotice['tone']): React.ComponentProps<typeof TerminalNotice>['variant'] {
  return tone === 'success' ? 'info' : 'danger';
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
  const { canReadNotifications } = useProductSurface();
  const isEnglish = language === 'en';
  const text = (en: string, zh: string) => (isEnglish ? en : zh);
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

  const routeSummary = (() => {
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
  })();
  const unacknowledgedCriticalEvents = events.filter((event) => event.severity === 'critical' && !event.acknowledgedAt).length;
  const latestOperationalTimestamp = (() => {
    const timestamps = [
      ...channels.flatMap((channel) => [channel.lastTriggeredAt, channel.lastSentAt, channel.updatedAt, channel.createdAt]),
      ...events.map((event) => event.createdAt),
    ].filter(Boolean) as string[];
    if (timestamps.length === 0) return null;
    return timestamps.reduce((latest, current) => (
      new Date(current).getTime() > new Date(latest).getTime() ? current : latest
    ));
  })();
  const l0TrustState: AdminOpsTrustState = error && channels.length === 0 && events.length === 0
    ? 'blocked'
    : isLoading && channels.length === 0 && events.length === 0
      ? 'unknown'
      : routeSummary.missingTargets > 0
        ? 'degraded'
        : unacknowledgedCriticalEvents > 0
          ? 'review_required'
          : routeSummary.enabledRoutes > 0
            ? 'healthy'
            : 'observe';
  const l0Impact = text(
    `${routeSummary.enabledRoutes} enabled routes, ${unacknowledgedCriticalEvents} critical alerts need acknowledgement.`,
    `${routeSummary.enabledRoutes} 条已启用路由，${unacknowledgedCriticalEvents} 条严重告警待确认。`,
  );
  const l0RecommendedAction = routeSummary.missingTargets > 0
    ? text('Fix unconfigured targets before sending new tests.', '先补齐未配置目标，再发送测试通知。')
    : unacknowledgedCriticalEvents > 0
      ? text('Acknowledge critical alerts, then inspect the affected channel.', '先确认严重告警，再检查对应通道。')
      : text('Keep route coverage current and dry-run when ownership changes.', '保持路由覆盖，通道变更时先做试运行。');

  const loadAll = useCallback(async () => {
    if (!canReadNotifications) {
      setChannels([]);
      setAvailableSystemChannels([]);
      setEvents([]);
      setError(null);
      setIsLoading(false);
      return;
    }
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
  }, [canReadNotifications]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const payload: NotificationChannelPayload = (() => {
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
        .flatMap((item) => {
          const eventType = item.trim();
          return eventType ? [eventType] : [];
        }),
      config,
    };
  })();

  async function createChannel() {
    if (!canReadNotifications) return;
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
  }

  async function toggleChannel(channel: NotificationChannel) {
    if (!canReadNotifications) return;
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
  }

  async function testChannel(channelId: number, dryRun: boolean) {
    if (!canReadNotifications) return;
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
          rawMessage: response.error ? sanitizeDeliveryText(response.error, text('Delivery error details were redacted.', '投递错误细节已脱敏。')) : null,
        });
      }
      await loadAll();
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setBusyId(null);
    }
  }

  async function deleteChannel(channelId: number) {
    if (!canReadNotifications) return;
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
  }

  async function acknowledge(eventId: number) {
    if (!canReadNotifications) return;
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
  }

  if (!canReadNotifications) {
    return (
      <TerminalPageShell
        data-testid="admin-notifications-workspace"
        className="min-h-0 flex-1 overflow-x-hidden py-5 md:py-6"
      >
        <TerminalPageHeading
          eyebrow={text('Operational alerts', '运维告警')}
          title={text('Admin notifications', '管理员通知')}
          action={<TerminalChip variant="danger">{text('Missing capability', '缺少权限')}</TerminalChip>}
        />
        <TerminalNotice data-testid="admin-notifications-capability-denied" variant="danger">
          {text(
            'Notifications are fail-closed because this account is missing the notifications capability.',
            '当前账号缺少通知管理权限，通知页面已 fail-closed。',
          )}
        </TerminalNotice>
      </TerminalPageShell>
    );
  }

  return (
    <TerminalPageShell
      data-testid="admin-notifications-workspace"
      className="min-h-0 flex-1 overflow-x-hidden py-5 md:py-6"
    >
      <TerminalPanel as="section" className="relative overflow-hidden">
        <TerminalPageHeading
          eyebrow={text('Operational alerts', '运维告警')}
          title={text('Admin notifications', '管理员通知')}
          action={(
            <TerminalButton
              type="button"
              variant="secondary"
              className="px-3 text-xs"
              onClick={() => void loadAll()}
              disabled={isLoading}
            >
              {isLoading ? text('Refreshing', '刷新中') : text('Refresh', '刷新')}
            </TerminalButton>
          )}
        />
        <p className="mt-3 max-w-3xl text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
          {text(
            'Route Admin Logs, scanner, market data, and future provider alerts to in-app records or a controlled webhook.',
            '将管理员日志、扫描器、市场数据和后续的供应商告警路由到站内记录或受控 webhook。',
          )}
        </p>
        <AdminOpsL0OverviewStrip
          dataTestId="admin-notifications-l0-overview-strip"
          className="mt-5"
          language={language as 'zh' | 'en'}
          systemTrustState={l0TrustState}
          impact={l0Impact}
          recommendedAction={l0RecommendedAction}
          evidenceRef={text('Notification events / notification rules', '通知事件 / 通知规则')}
          lastUpdated={formatDate(latestOperationalTimestamp)}
        />
      </TerminalPanel>

      {error ? <ApiErrorAlert error={error} /> : null}
      {notice ? (
        <TerminalNotice variant={noticeVariant(notice.tone)}>
          <p>{notice.message}</p>
          {notice.details?.length ? (
            <ul className="mt-2 space-y-1 text-[11px] leading-5 opacity-90">
              {notice.details.map((detail) => (
                <li key={detail}>• {detail}</li>
              ))}
            </ul>
          ) : null}
          {(notice.rawMessage && notice.rawMessage !== notice.message) || notice.diagnosticDetails ? (
            <TerminalDisclosure
              data-testid="notification-notice-raw-diagnostics"
              title={text('L4 sanitized delivery diagnostics: error summary / channel state', 'L4 已脱敏投递诊断：错误摘要 / 渠道状态')}
              summary={text('Collapsed by default · sanitized message only', '默认收起 · 仅显示脱敏消息')}
              className="mt-3"
            >
              <pre className="whitespace-pre-wrap break-words text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">
                {[
                  notice.rawMessage && notice.rawMessage !== notice.message ? notice.rawMessage : null,
                  notice.diagnosticDetails,
                ].filter(Boolean).join('\n\n')}
              </pre>
            </TerminalDisclosure>
          ) : null}
        </TerminalNotice>
      ) : null}

      <TerminalPanel as="section">
        <TerminalSectionHeader
          eyebrow={text('Route coverage', '路由覆盖')}
          title={channels.length
            ? text('Log notification rules mapped to safe operator channels.', '日志通知规则与安全运维通道的覆盖情况。')
            : text('No rules exist yet.', '暂无通知规则。')}
          action={<TerminalChip variant="info"><ShieldCheck className="h-3.5 w-3.5" />{text('Operator route', '运维路由')}</TerminalChip>}
        />
        <TerminalGrid data-testid="admin-notifications-summary-grid" className="mt-4">
          <div className="col-span-12 grid grid-cols-2 gap-3 md:grid-cols-4">
          {[
            { label: text('Enabled', '已启用'), value: routeSummary.enabledRoutes, tone: 'text-[color:var(--wolfy-market-up)]' },
            { label: text('Configured channels', '已配置通道'), value: channels.length, tone: 'text-[color:var(--wolfy-text-primary)]' },
            { label: text('Disabled', '已停用'), value: routeSummary.disabledRoutes, tone: 'text-[color:var(--wolfy-text-muted)]' },
            { label: text('Unconfigured', '未配置'), value: routeSummary.missingTargets, tone: routeSummary.missingTargets ? 'text-[color:var(--state-warning-text)]' : 'text-[color:var(--wolfy-text-muted)]' },
          ].map((item) => (
            <TerminalMetric
              key={item.label}
              label={item.label}
              value={item.value}
              valueClassName={cn('text-xl font-semibold', item.tone)}
            />
          ))}
          </div>
        {channels.length ? (
          <>
            <div className="col-span-12 xl:col-span-6">
              <TerminalNestedBlock>
                <p className="text-[11px] font-semibold text-[color:var(--wolfy-text-muted)]">{text('Grouped routes', '路由分组')}</p>
                <p className="mt-2 break-words text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                  {Object.entries(routeSummary.grouped).map(([label, count]) => `${label} × ${count}`).join(' · ')}
                </p>
              </TerminalNestedBlock>
            </div>
            <div className="col-span-12 xl:col-span-6">
              <TerminalNestedBlock>
                <p className="text-[11px] font-semibold text-[color:var(--wolfy-text-muted)]">{text('Covered events', '覆盖事件')}</p>
                <p className="mt-2 break-words text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                  {routeSummary.categories.join(' · ')}
                </p>
              </TerminalNestedBlock>
            </div>
          </>
        ) : null}
        </TerminalGrid>
      </TerminalPanel>

      <TerminalGrid className="min-h-0">
        <TerminalPanel as="section" dense className="col-span-12 xl:col-span-4">
          <form
            className="space-y-3"
            onSubmit={(event) => {
              event.preventDefault();
              void createChannel();
            }}
          >
          <TerminalSectionHeader
            eyebrow={text('Channel setup', '通道设置')}
            title={text('Create a low-risk in-app or webhook route.', '创建一个低风险的站内或 webhook 通道。')}
            action={<TerminalChip variant="neutral">{text('Masked after save', '保存后脱敏')}</TerminalChip>}
          />
          <p className="text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{text('Secrets are masked after save.', '保存后密钥会被遮罩。')}</p>
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
            containerClassName="min-h-[40px] rounded-xl border border-white/[0.02] bg-black/20 px-3 py-2"
          />
          {formError ? <TerminalNotice variant="danger">{formError}</TerminalNotice> : null}
          <TerminalButton type="submit" variant="primary" className="w-full" disabled={isSaving}>
            {isSaving ? text('Saving', '保存中') : text('Create channel', '创建通道')}
          </TerminalButton>
          </form>
        </TerminalPanel>

        <div className="col-span-12 grid min-h-0 grid-cols-1 gap-6 xl:col-span-8">
          <TerminalPanel as="section" data-testid="admin-notifications-rules-panel" className="min-h-0">
            <TerminalSectionHeader
              eyebrow={text('Notification rules', '通知规则')}
              title={text(`${channels.length} configured routes`, `${channels.length} 条已配置路由`)}
              action={<TerminalChip variant="info"><BellRing className="h-3.5 w-3.5" />{text('Route bindings', '路由绑定')}</TerminalChip>}
            />
            <TerminalDenseList className="mt-4 gap-3">
                {channels.length ? channels.map((channel) => {
                  const deliveryError = formatDeliveryError(language as 'zh' | 'en', channel.lastError, channel.lastErrorCode, channel.lastErrorDiagnostics);
                  const enabledStatus = describeBooleanEnabled(channel.enabled, { language: language as 'zh' | 'en' });
                  const lastStatus = describeAdminNotificationStatus(channel.lastStatus, { language: language as 'zh' | 'en' });

                  return (
                  <TerminalNestedBlock key={channel.id} data-testid={`notification-channel-${channel.id}`} className="grid gap-3 lg:grid-cols-[minmax(12rem,1fr)_minmax(16rem,1.35fr)_minmax(11rem,0.85fr)_minmax(13rem,0.95fr)] lg:items-start">
                    <div className="min-w-0 space-y-2">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-[color:var(--wolfy-text-muted)]">{channel.name}</p>
                        <p className="mt-1 flex items-center gap-1 text-[11px] text-[color:var(--wolfy-text-muted)]">
                          {channel.type === 'webhook' ? <Webhook className="h-3 w-3" /> : <BellRing className="h-3 w-3" />}
                          {scopeLabel(channel, language as 'zh' | 'en')} · {channel.type === 'system_channel'
                            ? text('Existing channel', '已有通道')
                            : channel.type === 'webhook'
                              ? text('Webhook', 'Webhook')
                              : text('In-app', '站内')}
                        </p>
                      </div>
                      <TerminalChip variant={displayStatusChipVariant(enabledStatus.tone)}>
                        {enabledStatus.label}
                      </TerminalChip>
                    </div>
                    <TerminalNestedBlock className="min-w-0">
                      <p className="text-[11px] font-semibold text-[color:var(--wolfy-text-muted)]">{text('Route coverage', '路由覆盖')}</p>
                      <p className="mt-1 break-words text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{coverageLabel(channel, language as 'zh' | 'en')}</p>
                      <p className="mt-2 text-[11px] font-semibold text-[color:var(--wolfy-text-muted)]">{text('Destination', '目标通道')}</p>
                      <p className="mt-1 break-words text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{channelTarget(channel, language as 'zh' | 'en')}</p>
                    </TerminalNestedBlock>
                    <div className="min-w-0 space-y-2 text-[11px] text-[color:var(--wolfy-text-muted)]">
                      <div>
                        <TerminalChip variant={severityChipVariant[channel.severityMin]}>
                          {severityLabel(channel.severityMin, language as 'zh' | 'en')}
                        </TerminalChip>
                      </div>
                      <p>
                        {text('Last trigger', '最近触发')}: <span className="text-[color:var(--wolfy-text-secondary)]">{formatDate(channel.lastTriggeredAt || channel.lastSentAt)}</span>
                      </p>
                      <p>
                        {text('Last status', '最近状态')}: <TerminalChip variant={displayStatusChipVariant(lastStatus.tone)}>{lastStatus.label}</TerminalChip>
                      </p>
                      <p>
                        {text('Last failure', '最近失败')}: <span className="text-[color:var(--wolfy-text-secondary)]">{failureSummaryLabel(channel, deliveryError, language as 'zh' | 'en')}</span>
                      </p>
                    </div>
                    <div className="flex min-w-0 flex-wrap gap-2 lg:justify-end">
                      <TerminalButton
                        type="button"
                        variant="compact"
                        onClick={() => void testChannel(channel.id, true)}
                        disabled={busyId === channel.id}
                      >
                        <ShieldCheck className="h-3 w-3" />
                        {text('Dry run', '仅验证')}
                      </TerminalButton>
                      <TerminalButton
                        type="button"
                        variant="compact"
                        onClick={() => void toggleChannel(channel)}
                        disabled={busyId === channel.id}
                      >
                        <Power className="h-3 w-3" />
                        {channel.enabled ? text('Disable', '停用') : text('Enable', '启用')}
                      </TerminalButton>
                      <TerminalButton
                        type="button"
                        variant="compact"
                        onClick={() => void testChannel(channel.id, false)}
                        disabled={busyId === channel.id}
                      >
                        <Send className="h-3 w-3" />
                        {text('Test send', '测试发送')}
                      </TerminalButton>
                      <TerminalButton
                        type="button"
                        variant="danger"
                        onClick={() => void deleteChannel(channel.id)}
                        disabled={busyId === channel.id}
                        title={text('Only unbind the log notification route; system channel is not deleted.', '仅解除日志路由绑定；不会删除系统通道。')}
                      >
                        <Trash2 className="h-3 w-3" />
                        {text('Unbind', '解除绑定')}
                      </TerminalButton>
                      <p className="basis-full text-[11px] leading-4 text-[color:var(--wolfy-text-muted)] lg:text-right">
                        {text('Only removes the log route binding. The system channel is not deleted.', '仅解除日志路由绑定，不会删除系统通道。')}
                      </p>
                    </div>
                  </TerminalNestedBlock>
                ); }) : (
                  <TerminalEmptyState data-testid="notification-rules-empty-state" title={text('No notification rules configured.', '暂无通知规则。')}>
                    {text('Create the first operator route on the left and keep delivery diagnostics secondary.', '在左侧创建第一条运维路由，原始投递诊断默认保持为次级信息。')}
                  </TerminalEmptyState>
                )}
            </TerminalDenseList>
          </TerminalPanel>

          <TerminalPanel as="section" data-testid="admin-notifications-events-panel" className="min-h-0">
            <TerminalSectionHeader
              eyebrow={text('Notifications', '通知事件')}
              title={text('Recent operational alert events and acknowledgement state.', '最近的运维告警事件与确认状态。')}
              action={<TerminalChip variant="info"><CheckCircle2 className="h-3.5 w-3.5" />{text('Recent events', '最近事件')}</TerminalChip>}
            />
            <TerminalDenseList className="mt-4 gap-3">
                {events.length ? events.map((event) => (
                  <TerminalNestedBlock key={event.id} data-testid={`notification-event-${event.id}`} className="grid gap-3 md:grid-cols-[8rem_minmax(12rem,1fr)_9rem_7rem] md:items-center">
                    <p className="text-xs text-[color:var(--wolfy-text-secondary)]">{formatDate(event.createdAt)}</p>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-[color:var(--wolfy-text-muted)]">{event.title}</p>
                      <p className="mt-1 truncate text-[11px] text-[color:var(--wolfy-text-muted)]" title={displayEventMessage(event.message, language as 'zh' | 'en')}>{event.eventType} · {describeAdminNotificationStatus(event.deliveryStatus, { language: language as 'zh' | 'en' }).label}</p>
                    </div>
                    <div>
                      <TerminalChip variant={severityChipVariant[event.severity]}>{severityLabel(event.severity, language as 'zh' | 'en')}</TerminalChip>
                      <p className="mt-1 text-[11px] text-[color:var(--wolfy-text-muted)]">{acknowledgedLabel(event.acknowledgedAt, language as 'zh' | 'en')}</p>
                    </div>
                    <div className="md:text-right">
                      <TerminalButton
                        type="button"
                        variant="compact"
                        onClick={() => void acknowledge(event.id)}
                        disabled={Boolean(event.acknowledgedAt) || busyId === event.id}
                      >
                        {text('Acknowledge', '确认')}
                      </TerminalButton>
                    </div>
                  </TerminalNestedBlock>
                )) : (
                  <TerminalEmptyState data-testid="notification-events-empty-state" title={text('No notification events yet.', '暂无通知事件。')}>
                    {text('Acknowledge actions appear here after operational alerts are recorded.', '运维告警产生后，会在这里显示确认动作。')}
                  </TerminalEmptyState>
                )}
            </TerminalDenseList>
          </TerminalPanel>
        </div>
      </TerminalGrid>
      <p className="sr-only">{text('Current language:', '当前语言：')} {language}</p>
    </TerminalPageShell>
  );
};

export default AdminNotificationsPage;
