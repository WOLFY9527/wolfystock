import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Activity, ChevronDown, ChevronRight } from 'lucide-react';
import {
  adminProviderCircuitsApi,
  type ProviderCircuitDiagnosticsBundle,
  type ProviderCircuitEventItem,
  type ProviderCircuitStateItem,
  type ProviderProbeEventItem,
  type ProviderQuotaWindowItem,
  type ProviderSlaReadinessItem,
} from '../api/adminProviderCircuits';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { ApiErrorAlert } from '../components/common';
import {
  TerminalButton,
  TerminalChip,
  TerminalGrid,
  TerminalMetric,
  TerminalNestedBlock,
  TerminalNotice,
  TerminalPageHeading,
  TerminalPageShell,
  TerminalPanel,
  TerminalSectionHeader,
} from '../components/terminal';
import AdminOpsL0OverviewStrip from '../components/admin/AdminOpsL0OverviewStrip';
import AdminOpsSectionHeading from '../components/admin/AdminOpsSectionHeading';
import { useProductSurface } from '../hooks/useProductSurface';
import { cn } from '../utils/cn';
import { formatDateTime, formatNumber } from '../utils/format';

type Tone = 'neutral' | 'good' | 'warn' | 'danger' | 'info';

type OperationalVerdictLevel = 'LIVE' | 'DEGRADED' | 'BLOCKED' | 'LOADING' | 'ERROR';

interface SummaryMetric {
  label: string;
  value: string;
  subvalue: string;
  tone: Tone;
}

interface OperatorActionItem {
  id: string;
  issue: string;
  impact: string;
  nextAction: string;
  tone: Tone;
  priority: number;
}

interface OperationalSummary {
  states: number;
  open: number;
  warn: number;
  events: number;
  quotaWindows: number;
  quotaRejected: number;
  quotaLimitOrAuth: number;
  probeEvents: number;
  failedProbes: number;
  slaReadiness: number;
  slaBlocked: number;
  slaCredentialGaps: number;
  slaWatch: number;
}

interface OperationalVerdict {
  level: OperationalVerdictLevel;
  title: string;
  description: string;
  impact: string;
  nextAction: string;
  tone: Tone;
}

interface DiagnosticsDisclosureProps {
  title: React.ReactNode;
  summary?: React.ReactNode;
  defaultOpen?: boolean;
  className?: string;
  children: React.ReactNode;
}

const UNSAFE_VALUE_PATTERN = /(https?:\/\/|www\.|\?|=|token|secret|cookie|session|password|bearer|apikey|api_key|stack|trace)/i;

const DiagnosticsDisclosure: React.FC<DiagnosticsDisclosureProps> = ({ title, summary, defaultOpen = false, className, children }) => {
  const [open, setOpen] = useState(defaultOpen);
  const titleText = typeof title === 'string' ? title : '';
  const actionLabel = open ? `收起 ${titleText}` : `展开 ${titleText}`;

  return (
    <div
      data-testid="terminal-disclosure"
      data-terminal-primitive="disclosure"
      className={cn(
        'rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-2.5 py-2 text-xs transition-colors hover:border-[color:var(--wolfy-divider)]',
        className,
      )}
    >
      <div className="flex min-w-0 items-center justify-between gap-2">
        <div className="min-w-0">
          <span className="block truncate text-xs font-medium text-[color:var(--wolfy-text-secondary)]">{title}</span>
          {summary ? <span className="mt-0.5 block truncate text-[11px] text-[color:var(--wolfy-text-muted)]">{summary}</span> : null}
        </div>
        <TerminalButton
          variant="compact"
          aria-expanded={open}
          aria-label={actionLabel}
          className="shrink-0 px-2 py-1 text-[11px]"
          onClick={() => setOpen((current) => !current)}
        >
          {open ? <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" /> : <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />}
          <span>{open ? '收起' : '展开'}</span>
        </TerminalButton>
      </div>
      {open ? <div className="mt-2">{children}</div> : null}
    </div>
  );
};

function safeText(value?: string | number | null, fallback = '--'): string {
  if (value === null || value === undefined || value === '') return fallback;
  const text = String(value).trim();
  if (!text || UNSAFE_VALUE_PATTERN.test(text)) return '已脱敏';
  return text.slice(0, 80);
}

function safeDate(value?: string | null): string {
  if (!value) return '--';
  const text = safeText(value);
  return text === '已脱敏' ? text : formatDateTime(text);
}

function stateLabel(state?: string | null): string {
  const labels: Record<string, string> = {
    closed: '闭合',
    open: '打开',
    half_open: '半开',
    degraded_cache_only: '仅缓存降级',
    disabled_by_operator: '人工禁用',
    provider_quota_depleted: '配额耗尽',
  };
  return labels[String(state || '').toLowerCase()] || safeText(state, '未知');
}

function bucketLabel(value?: string | null): string {
  const labels: Record<string, string> = {
    timeout: '超时',
    provider_429: 'Provider 429',
    provider_403: 'Provider 403',
    provider_5xx: 'Provider 5xx',
    network_error: '网络错误',
    malformed_payload: '载荷异常',
    auth_or_key_invalid: '鉴权或密钥异常',
    quota_policy_block: '配额策略阻断',
    operator_disabled: '人工禁用',
    success: '成功',
    unknown: '未知',
  };
  return labels[String(value || '').toLowerCase()] || safeText(value, '未知');
}

function stateTone(state?: string | null): Tone {
  const normalized = String(state || '').toLowerCase();
  if (normalized === 'closed') return 'good';
  if (normalized === 'half_open' || normalized === 'degraded_cache_only') return 'warn';
  if (normalized === 'open' || normalized === 'disabled_by_operator' || normalized === 'provider_quota_depleted') return 'danger';
  return 'neutral';
}

function readinessTone(state?: string | null): Tone {
  const normalized = String(state || '').toLowerCase();
  if (normalized === 'dry_run_enabled' || normalized === 'observed') return 'good';
  if (normalized === 'missing_credentials' || normalized === 'live_credentials_present_live_calls_disabled') return 'warn';
  if (normalized === 'disabled' || normalized === 'sanitized_provider_error' || normalized === 'malformed_provider_payload') return 'danger';
  return 'neutral';
}

function freshnessLabel(value?: string | null): string {
  const labels: Record<string, string> = {
    fresh: '新鲜',
    stale: '滞后',
    expired: '过期',
    unknown: '未知',
  };
  return labels[String(value || '').toLowerCase()] || safeText(value, '未知');
}

function latencyLabel(value?: string | null): string {
  const labels: Record<string, string> = {
    normal: '正常',
    slow: '慢',
    critical: '严重',
    unknown: '未知',
  };
  return labels[String(value || '').toLowerCase()] || safeText(value, '未知');
}

function credentialLabel(value?: string | null): string {
  const labels: Record<string, string> = {
    disabled: '禁用',
    missing_credentials: '缺少凭证',
    live_credentials_present_live_calls_disabled: '有凭证 / 外呼关闭',
    dry_run_enabled: 'Dry-run',
    configured: '已配置',
    credentials_present: '有凭证',
    unknown: '未知',
  };
  return labels[String(value || '').toLowerCase()] || safeText(value, '未知');
}

function boolLabel(value?: boolean | null): string {
  return value ? '是' : '否';
}

const METRIC_VALUE_CLASS_BY_TONE: Record<Tone, string> = {
  neutral: 'text-white',
  good: 'text-emerald-300',
  warn: 'text-amber-300',
  danger: 'text-rose-300',
  info: 'text-cyan-300',
};

function chipVariant(tone: Tone): 'neutral' | 'success' | 'caution' | 'danger' | 'info' {
  return ({
    neutral: 'neutral',
    good: 'success',
    warn: 'caution',
    danger: 'danger',
    info: 'info',
  } as const)[tone];
}

function dimensionText(providerCategory?: string | null, routeFamily?: string | null): string {
  return `分类 ${safeText(providerCategory, '未分组')} · 路由 ${safeText(routeFamily, '全路由')}`;
}

function readinessNotice(item: ProviderSlaReadinessItem): string {
  if (item.liveHttpCallsEnabled === false) return '当前只读观测外部调用门禁，不会触发 provider 实际请求。';
  if (item.credentialsPresent === false) return '凭证未就绪，先核对凭证配置与开关。';
  if (item.wouldBlockCall) return '当前门禁判断会阻断调用，需先查看熔断与最近错误。';
  return '当前仅展示就绪信号与趋势，不改变排序、fallback 或配额语义。';
}

function bucketHasSignal(value?: string | number | null): boolean {
  if (value === null || value === undefined) return false;
  if (typeof value === 'number') return value > 0;
  const normalized = value.trim().toLowerCase();
  return normalized !== '' && normalized !== '0' && normalized !== '0_0' && normalized !== 'none' && normalized !== 'unknown';
}

function isProbeFailure(item: ProviderProbeEventItem): boolean {
  const normalized = String(item.resultBucket || '').toLowerCase();
  return normalized !== '' && normalized !== 'success';
}

function isSlaWatchItem(item: ProviderSlaReadinessItem): boolean {
  const latencyState = String(item.latencyState || '').toLowerCase();
  const freshnessState = String(item.freshnessState || '').toLowerCase();
  const errorState = String(item.errorState || '').toLowerCase();
  const circuitCandidate = String(item.circuitStateCandidate || '').toLowerCase();
  const advisoryState = String(item.circuitAdvisoryState || '').toLowerCase();
  return (
    item.wouldBlockCall === true
    || item.credentialsPresent === false
    || readinessTone(item.readinessState) === 'danger'
    || readinessTone(item.readinessState) === 'warn'
    || latencyState === 'slow'
    || latencyState === 'critical'
    || freshnessState === 'stale'
    || freshnessState === 'expired'
    || (errorState !== '' && errorState !== 'normal' && errorState !== 'unknown')
    || circuitCandidate === 'open'
    || circuitCandidate === 'half_open'
    || advisoryState.includes('open')
    || bucketHasSignal(item.trendSummary?.failureCountBucket)
    || bucketHasSignal(item.trendSummary?.provider429CountBucket)
    || bucketHasSignal(item.trendSummary?.provider403CountBucket)
  );
}

function quotaHasPressure(item: ProviderQuotaWindowItem): boolean {
  return item.rejectedCount > 0 || item.provider429Count > 0 || item.provider403Count > 0 || item.timeoutCount > 0;
}

function actionReasonLabel(value?: string | null): string {
  const labels: Record<string, string> = {
    timeout: '超时线索',
    provider_429: '限流 / 配额线索',
    provider_403: '授权拒绝线索',
    provider_5xx: 'provider 服务异常线索',
    network_error: '网络异常线索',
    malformed_payload: '载荷异常线索',
    auth_or_key_invalid: '鉴权或密钥异常线索',
    quota_policy_block: '配额策略阻断线索',
    operator_disabled: '人工禁用线索',
  };
  const normalized = String(value || '').toLowerCase();
  if (labels[normalized]) return labels[normalized];
  const sanitized = safeText(value, '异常线索');
  return sanitized === '已脱敏' ? '已脱敏线索' : `${sanitized} 线索`;
}

function buildOperationalSummary(data: ProviderCircuitDiagnosticsBundle | null): OperationalSummary {
  const states = data?.states.items || [];
  const quotaWindows = data?.quotaWindows.items || [];
  const probeEvents = data?.probeEvents.items || [];
  const slaReadiness = data?.slaReadiness.items || [];
  return {
    states: states.length,
    open: states.filter((item) => stateTone(item.state) === 'danger').length,
    warn: states.filter((item) => stateTone(item.state) === 'warn').length,
    events: data?.events.items.length || 0,
    quotaWindows: quotaWindows.length,
    quotaRejected: quotaWindows.reduce((total, item) => total + item.rejectedCount, 0),
    quotaLimitOrAuth: quotaWindows.filter((item) => item.provider429Count > 0 || item.provider403Count > 0).length,
    probeEvents: probeEvents.length,
    failedProbes: probeEvents.filter(isProbeFailure).length,
    slaReadiness: slaReadiness.length,
    slaBlocked: slaReadiness.filter((item) => item.wouldBlockCall).length,
    slaCredentialGaps: slaReadiness.filter((item) => item.credentialsPresent === false).length,
    slaWatch: slaReadiness.filter(isSlaWatchItem).length,
  };
}

function buildOperationalVerdict(
  summary: OperationalSummary,
  isLoading: boolean,
  hasData: boolean,
  hasError: boolean,
): OperationalVerdict {
  if (hasError) {
    return {
      level: 'ERROR',
      title: '无法确认 provider 熔断状态',
      description: '诊断 API 读取失败，当前页面不能给出可靠运维判断。',
      impact: '管理员需要先恢复诊断读取',
      nextAction: '查看错误提示并重试读取',
      tone: 'danger',
    };
  }
  if (isLoading && !hasData) {
    return {
      level: 'LOADING',
      title: '正在读取 provider 熔断快照',
      description: '只读取现有诊断 API，不触发 provider 调用。',
      impact: '等待快照后判断生产调用',
      nextAction: '读取完成后查看动作列表',
      tone: 'info',
    };
  }
  if (summary.open > 0 || summary.slaBlocked > 0 || summary.slaCredentialGaps > 0) {
    return {
      level: 'BLOCKED',
      title: 'Provider 熔断需要管理员处理',
      description: `${summary.open} 个熔断打开，${summary.slaBlocked + summary.slaCredentialGaps} 个 SLA / 凭证阻断信号。`,
      impact: '相关 provider 生产调用应暂缓',
      nextAction: '按下方动作列表先处理阻断项',
      tone: 'danger',
    };
  }
  if (summary.warn > 0 || summary.quotaRejected > 0 || summary.quotaLimitOrAuth > 0 || summary.failedProbes > 0 || summary.slaWatch > 0) {
    return {
      level: 'DEGRADED',
      title: 'Provider 熔断可用但有降级信号',
      description: `${summary.warn} 个降级观察，${summary.quotaRejected} 次配额拒绝，${summary.failedProbes} 个探测异常。`,
      impact: '可继续观察，但需处理高优先级风险',
      nextAction: '先核对动作列表中的配额、SLA 与探测项',
      tone: 'warn',
    };
  }
  return {
    level: 'LIVE',
    title: 'Provider 熔断当前可运营',
    description: `${summary.states} 个状态快照未显示阻断，事件和诊断细节默认后置。`,
    impact: '生产调用可继续按既有门禁观察',
    nextAction: '保持监控，必要时展开 L3 诊断',
    tone: 'good',
  };
}

function buildSummaryMetrics(summary: OperationalSummary): SummaryMetric[] {
  return [
    {
      label: '熔断状态',
      value: summary.open ? `${summary.open} 打开` : summary.warn ? `${summary.warn} 降级` : '未阻断',
      subvalue: `${summary.states} 个状态快照`,
      tone: summary.open ? 'danger' : summary.warn ? 'warn' : 'good',
    },
    {
      label: 'SLA 阻断',
      value: summary.slaBlocked || summary.slaCredentialGaps ? `${summary.slaBlocked + summary.slaCredentialGaps} 阻断` : summary.slaWatch ? `${summary.slaWatch} 观察` : '未阻断',
      subvalue: `${summary.slaReadiness} 个就绪信号`,
      tone: summary.slaBlocked || summary.slaCredentialGaps ? 'danger' : summary.slaWatch ? 'warn' : 'good',
    },
    {
      label: '配额压力',
      value: summary.quotaRejected ? `${summary.quotaRejected} 拒绝` : summary.quotaLimitOrAuth ? `${summary.quotaLimitOrAuth} 窗口异常` : '未见拒绝',
      subvalue: `${summary.quotaWindows} 个配额窗口`,
      tone: summary.quotaRejected || summary.quotaLimitOrAuth ? 'warn' : 'good',
    },
    {
      label: '探测结果',
      value: summary.failedProbes ? `${summary.failedProbes} 异常` : summary.probeEvents ? `${summary.probeEvents} 正常` : '暂无探测',
      subvalue: '事件 / bucket 默认折叠',
      tone: summary.failedProbes ? 'danger' : summary.probeEvents ? 'good' : 'neutral',
    },
  ];
}

function buildOperatorActions(data: ProviderCircuitDiagnosticsBundle | null): OperatorActionItem[] {
  if (!data) return [];

  const actions: OperatorActionItem[] = [];

  data.states.items.forEach((item, index) => {
    const tone = stateTone(item.state);
    if (tone !== 'danger' && tone !== 'warn') return;
    actions.push({
      id: `state-${item.provider}-${index}`,
      issue: `${safeText(item.provider)} 熔断${tone === 'danger' ? '打开' : '降级观察'}`,
      impact: tone === 'danger' ? '相关生产调用应暂缓，避免继续命中失败路径。' : '仍可观察，但当前 provider 处于降级或缓存路径。',
      nextAction: `核对 ${actionReasonLabel(item.reasonBucket)} 与冷却时间 ${safeDate(item.cooldownUntil)}。`,
      tone,
      priority: tone === 'danger' ? 10 : 30,
    });
  });

  data.slaReadiness.items.forEach((item, index) => {
    if (!isSlaWatchItem(item)) return;
    const blocked = item.wouldBlockCall || item.credentialsPresent === false || readinessTone(item.readinessState) === 'danger';
    actions.push({
      id: `sla-${item.provider}-${index}`,
      issue: `${safeText(item.provider)} SLA / 凭证需核对`,
      impact: blocked ? '门禁判断可能阻断 provider 调用。' : '延迟、错误或熔断建议显示该 provider 需要观察。',
      nextAction: item.credentialsPresent === false
        ? '先核对凭证配置与 provider 开关。'
        : '展开 L3 诊断查看最近错误 bucket 与趋势窗口。',
      tone: blocked ? 'danger' : 'warn',
      priority: blocked ? 15 : 35,
    });
  });

  data.quotaWindows.items.forEach((item, index) => {
    if (!quotaHasPressure(item)) return;
    actions.push({
      id: `quota-${item.provider}-${index}`,
      issue: `${safeText(item.provider)} 配额窗口出现拒绝或限流`,
      impact: `${formatNumber(item.rejectedCount, 0)} 次拒绝，${formatNumber(item.provider429Count + item.provider403Count, 0)} 次限流或授权拒绝会推高熔断风险。`,
      nextAction: '核对配额消耗、provider 授权与请求节奏。',
      tone: item.provider403Count > 0 ? 'danger' : 'warn',
      priority: item.provider403Count > 0 ? 18 : 28,
    });
  });

  data.probeEvents.items.forEach((item, index) => {
    if (!isProbeFailure(item)) return;
    actions.push({
      id: `probe-${item.provider}-${index}`,
      issue: `${safeText(item.provider)} 探测未成功`,
      impact: '连通性或可用性探测异常，可能影响后续 provider 判断。',
      nextAction: `查看 ${bucketLabel(item.resultBucket)} 探测结果与最近事件。`,
      tone: 'danger',
      priority: 20,
    });
  });

  return actions.sort((left, right) => left.priority - right.priority).slice(0, 4);
}

const CurrentStatesPanel: React.FC<{ items: ProviderCircuitStateItem[] }> = ({ items }) => (
  <TerminalPanel as="section" className="h-full">
    <TerminalSectionHeader
      eyebrow="当前熔断"
      title="当前熔断状态"
      action={<TerminalChip variant="neutral">{items.length ? `${formatNumber(items.length, 0)} 个状态快照` : '只读快照'}</TerminalChip>}
    />
    {items.length === 0 ? (
      <TerminalNotice variant="neutral" className="mt-4">
        暂无 provider 熔断状态
      </TerminalNotice>
    ) : (
      <div className="mt-4 grid grid-cols-1 gap-3 2xl:grid-cols-2">
        {items.map((item, index) => (
          <TerminalNestedBlock key={`${item.provider}-${item.providerCategory || 'all'}-${item.routeFamily || 'all'}-${index}`} className="min-w-0">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-white">{safeText(item.provider)}</p>
                <p className="mt-1 truncate font-mono text-[11px] text-white/42">
                  {dimensionText(item.providerCategory, item.routeFamily)}
                </p>
              </div>
              <TerminalChip variant={chipVariant(stateTone(item.state))} className="shrink-0 font-semibold">
                {stateLabel(item.state)}
              </TerminalChip>
            </div>
            <div className="mt-3 grid grid-cols-1 gap-2 text-[11px] text-white/44 sm:grid-cols-3">
              <p className="min-w-0">
                原因 bucket
                <span className="block truncate font-mono text-white/68">{bucketLabel(item.reasonBucket)}</span>
              </p>
              <p className="min-w-0">
                冷却至
                <span className="block truncate font-mono text-white/68">{safeDate(item.cooldownUntil)}</span>
              </p>
              <p className="min-w-0">
                更新时间
                <span className="block truncate font-mono text-white/68">{safeDate(item.updatedAt)}</span>
              </p>
            </div>
          </TerminalNestedBlock>
        ))}
      </div>
    )}
  </TerminalPanel>
);

const EventsPanel: React.FC<{ items: ProviderCircuitEventItem[] }> = ({ items }) => (
  <TerminalPanel as="section" dense>
    <TerminalSectionHeader eyebrow="事件" title="最近熔断事件" action={<TerminalChip variant="neutral">{items.length ? `${formatNumber(items.length, 0)} 条已脱敏事件` : '暂无事件'}</TerminalChip>} />
    {items.length === 0 ? (
      <TerminalNotice variant="neutral" className="mt-4">
        暂无熔断事件
      </TerminalNotice>
    ) : (
      <div className="mt-4 space-y-3">
        {items.map((item, index) => (
          <TerminalNestedBlock key={`${item.provider}-${item.eventType}-${item.createdAt || index}`} className="min-w-0">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-white">{safeText(item.eventType)}</p>
                <p className="mt-1 truncate font-mono text-[11px] text-white/42">
                  {dimensionText(item.providerCategory, item.routeFamily)}
                </p>
              </div>
              <span className="shrink-0 font-mono text-[11px] text-white/42">{safeDate(item.createdAt)}</span>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-white/44 md:grid-cols-4">
              <p>
                状态变化
                <span className="block truncate font-mono text-white/68">
                  {stateLabel(item.fromState)} {'->'} {stateLabel(item.toState)}
                </span>
              </p>
              <p>
                原因 bucket
                <span className="block truncate font-mono text-white/68">{bucketLabel(item.reasonBucket)}</span>
              </p>
              <p>
                请求 bucket
                <span className="block truncate font-mono text-white/68">{safeText(item.requestCountBucket)}</span>
              </p>
              <p>
                持续时间
                <span className="block truncate font-mono text-white/68">{safeText(item.durationBucketMs)} ms</span>
              </p>
            </div>
          </TerminalNestedBlock>
        ))}
      </div>
    )}
  </TerminalPanel>
);

const QuotaWindowsPanel: React.FC<{ items: ProviderQuotaWindowItem[] }> = ({ items }) => (
  <TerminalPanel as="section" dense>
    <TerminalSectionHeader eyebrow="配额" title="配额窗口" action={<TerminalChip variant="neutral">{items.length ? `${formatNumber(items.length, 0)} 个窗口` : '暂无窗口'}</TerminalChip>} />
    {items.length === 0 ? (
      <TerminalNotice variant="neutral" className="mt-4">
        暂无配额窗口
      </TerminalNotice>
    ) : (
      <div className="mt-4 grid grid-cols-1 gap-3">
        {items.map((item, index) => (
          <TerminalNestedBlock key={`${item.provider}-${item.windowStart}-${index}`} className="min-w-0">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-white">{safeText(item.provider)}</p>
                <p className="mt-1 truncate font-mono text-[11px] text-white/42">
                  {dimensionText(item.providerCategory, item.routeFamily)}
                </p>
              </div>
              <TerminalChip variant="info" className="shrink-0 font-mono">
                {safeText(item.windowType)}
              </TerminalChip>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-white/44 md:grid-cols-4">
              <p>
                请求数
                <span className="block font-mono text-white/68">{formatNumber(item.requestCount, 0)}</span>
              </p>
              <p>
                拒绝数
                <span className="block font-mono text-rose-100/80">{formatNumber(item.rejectedCount, 0)}</span>
              </p>
              <p>
                成功 / 失败
                <span className="block font-mono text-white/68">
                  {formatNumber(item.successCount, 0)} / {formatNumber(item.failureCount, 0)}
                </span>
              </p>
              <p>
                探测数
                <span className="block font-mono text-white/68">{formatNumber(item.probeCount, 0)}</span>
              </p>
              <p>
                预留 / 消耗
                <span className="block font-mono text-white/68">
                  {formatNumber(item.reservedUnits, 0)} / {formatNumber(item.consumedUnits, 0)}
                </span>
              </p>
              <p>
                429 / 403
                <span className="block font-mono text-white/68">
                  {formatNumber(item.provider429Count, 0)} / {formatNumber(item.provider403Count, 0)}
                </span>
              </p>
              <p>
                Cache / stale
                <span className="block font-mono text-white/68">
                  {formatNumber(item.cacheOnlyCount, 0)} / {formatNumber(item.staleServedCount, 0)}
                </span>
              </p>
              <p>
                窗口起点
                <span className="block truncate font-mono text-white/68">{safeDate(item.windowStart)}</span>
              </p>
            </div>
          </TerminalNestedBlock>
        ))}
      </div>
    )}
  </TerminalPanel>
);

const ProbeEventsPanel: React.FC<{ items: ProviderProbeEventItem[] }> = ({ items }) => (
  <TerminalPanel as="section" dense>
    <TerminalSectionHeader eyebrow="探测" title="探测事件" action={<TerminalChip variant="neutral">{items.length ? `${formatNumber(items.length, 0)} 条探测` : '暂无探测'}</TerminalChip>} />
    {items.length === 0 ? (
      <TerminalNotice variant="neutral" className="mt-4">
        暂无探测事件
      </TerminalNotice>
    ) : (
      <div className="mt-4 space-y-3">
        {items.map((item, index) => (
          <TerminalNestedBlock key={`${item.provider}-${item.probeType}-${item.createdAt || index}`} className="min-w-0">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-white">{safeText(item.probeType)}</p>
                <p className="mt-1 truncate font-mono text-[11px] text-white/42">
                  {dimensionText(item.providerCategory, item.routeFamily)}
                </p>
              </div>
              <TerminalChip variant="success" className="shrink-0 font-semibold">
                {bucketLabel(item.resultBucket)}
              </TerminalChip>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-white/44 md:grid-cols-3">
              <p>
                来源
                <span className="block truncate font-mono text-white/68">{safeText(item.probeSource)}</span>
              </p>
              <p>
                持续时间
                <span className="block truncate font-mono text-white/68">{safeText(item.durationBucketMs)} ms</span>
              </p>
              <p>
                创建时间
                <span className="block truncate font-mono text-white/68">{safeDate(item.createdAt)}</span>
              </p>
            </div>
          </TerminalNestedBlock>
        ))}
      </div>
    )}
  </TerminalPanel>
);

const SlaReadinessPanel: React.FC<{ items: ProviderSlaReadinessItem[] }> = ({ items }) => (
  <TerminalPanel as="section" className="col-span-12">
    <TerminalSectionHeader
      eyebrow="就绪度"
      title="Provider SLA / 凭证就绪"
      action={<TerminalChip variant="neutral">{items.length ? `${formatNumber(items.length, 0)} 个就绪信号 · 外呼关闭` : '只读 · 外部调用关闭'}</TerminalChip>}
    />
    {items.length === 0 ? (
      <TerminalNotice variant="neutral" className="mt-4">
        暂无 SLA / readiness 诊断
      </TerminalNotice>
    ) : (
      <div className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-2">
        {items.map((item, index) => {
          const itemKey = `${item.provider}-${item.providerCategory || 'all'}-${item.routeFamily || 'all'}-${index}`;

          return (
            <TerminalNestedBlock key={itemKey} className="min-w-0">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-white">{safeText(item.provider)}</p>
                    <p className="mt-1 truncate font-mono text-[11px] text-white/42">
                      {dimensionText(item.providerCategory, item.routeFamily)}
                    </p>
                  </div>
                  <TerminalChip variant={chipVariant(readinessTone(item.readinessState))} className="shrink-0 font-semibold">
                    {credentialLabel(item.credentialState)}
                  </TerminalChip>
                </div>

                <TerminalNotice
                  variant={item.wouldBlockCall ? 'caution' : item.credentialsPresent === false ? 'danger' : 'info'}
                  className="mt-3"
                >
                  {readinessNotice(item)}
                </TerminalNotice>

                <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-white/44 md:grid-cols-4">
                  <p>
                    延迟
                    <span className="block truncate font-mono text-white/68">
                      {latencyLabel(item.latencyState)} · {safeText(item.latencyBucketMs)} ms
                    </span>
                  </p>
                  <p>
                    新鲜度
                    <span className="block truncate font-mono text-white/68">
                      {freshnessLabel(item.freshnessState)} · {safeText(item.freshnessSeconds)} s
                    </span>
                  </p>
                  <p>
                    错误状态
                    <span className="block truncate font-mono text-white/68">
                      {safeText(item.errorState)} · {safeText(item.errorRate)}
                    </span>
                  </p>
                  <p>
                    阻断判断
                    <span className="block truncate font-mono text-white/68">{boolLabel(item.wouldBlockCall)}</span>
                  </p>
                </div>

                <div className="mt-3 grid grid-cols-2 gap-3">
                  <TerminalMetric
                    label="趋势请求"
                    value={safeText(item.trendSummary?.requestCountBucket, '0')}
                    valueClassName="text-sm"
                  />
                  <TerminalMetric
                    label="趋势失败"
                    value={safeText(item.trendSummary?.failureCountBucket, '0')}
                    valueClassName="text-sm"
                  />
                  <TerminalMetric
                    label="429 / 403"
                    value={`${safeText(item.trendSummary?.provider429CountBucket, '0')} / ${safeText(item.trendSummary?.provider403CountBucket, '0')}`}
                    valueClassName="text-sm"
                  />
                  <TerminalMetric
                    label="最近观察"
                    value={safeDate(item.trendSummary?.latestObservationAt)}
                    valueClassName="text-sm"
                  />
                </div>

                <DiagnosticsDisclosure title="L3 最近错误 buckets（已脱敏）" summary={`${(item.recentErrors || []).length} 项，默认收起`} className="mt-3">
                  {(item.recentErrors || []).length === 0 ? (
                    <p className="text-white/48">暂无错误 bucket</p>
                  ) : (
                    <div className="space-y-2">
                      {(item.recentErrors || []).map((error) => (
                        <p key={`${error.reasonBucket}-${error.latestAt || 'none'}`} className="font-mono text-white/60">
                          {bucketLabel(error.reasonBucket)} · {safeText(error.countBucket)} · {safeDate(error.latestAt)}
                        </p>
                      ))}
                    </div>
                  )}
                </DiagnosticsDisclosure>

                <DiagnosticsDisclosure title="L3 技术边界（只读 / 外呼 / 门禁）" summary="默认收起" className="mt-3">
                  <div className="grid grid-cols-1 gap-2 text-[11px] text-white/50 md:grid-cols-2">
                      <p>
                        调用门禁
                        <span className="block font-mono text-white/68">{boolLabel(item.liveHttpCallsEnabled)}</span>
                      </p>
                      <p>
                        Dry-run
                        <span className="block font-mono text-white/68">{boolLabel(item.dryRunEnabled)}</span>
                      </p>
                      <p>
                        排序 / fallback 变化
                        <span className="block font-mono text-white/68">
                          {boolLabel(item.wouldChangeProviderOrder)} / {boolLabel(item.wouldChangeFallbackBehavior)}
                        </span>
                      </p>
                      <p>
                        熔断建议
                        <span className="block font-mono text-white/68">
                          {safeText(item.circuitAdvisoryState)} / {stateLabel(item.circuitStateCandidate)}
                        </span>
                      </p>
                  </div>
                </DiagnosticsDisclosure>
              </TerminalNestedBlock>
            );
        })}
      </div>
    )}
  </TerminalPanel>
);

const BoundaryPanel: React.FC<{ data?: ProviderCircuitDiagnosticsBundle | null }> = ({ data }) => {
  const metadata = data?.states.metadata;

  return (
    <TerminalPanel as="aside" dense className="h-full">
      <TerminalSectionHeader eyebrow="边界" title="诊断观测" />
      <TerminalNotice variant="info" className="mt-4">
        当前为诊断观测，不会改变 provider fallback 或 MarketCache 行为。
      </TerminalNotice>
      <DiagnosticsDisclosure title="L3 技术边界（读取 / 外呼 / 门禁 / 脱敏）" summary="读取、外呼、门禁与脱敏信息默认收起" className="mt-3">
        <div className="grid grid-cols-1 gap-2 text-[11px] text-white/50">
          <p>
            读取边界
            <span className="block font-mono text-white/68">沿用既有 provider 读取门禁</span>
          </p>
          <p>
            只读 / 外呼 / 门禁
            <span className="block font-mono text-white/68">
              {metadata?.readOnly === true ? '只读' : '未确认'} / {metadata?.noExternalCalls === true ? '关闭' : '未确认'} / {metadata?.liveEnforcement === false ? '关闭' : '未确认'}
            </span>
          </p>
          <p>
            数据来源
            <span className="block font-mono text-white/68">{safeText(metadata?.dataSources?.join(', '), '未提供')}</span>
          </p>
          <p>
            Redaction
            <span className="block font-mono text-white/68">{safeText(metadata?.redaction?.join(', '), '未提供')}</span>
          </p>
        </div>
      </DiagnosticsDisclosure>
    </TerminalPanel>
  );
};

const OperationalVerdictPanel: React.FC<{ verdict: OperationalVerdict; generatedAt?: string | null }> = ({ verdict, generatedAt }) => (
  <TerminalNestedBlock data-testid="provider-circuit-operational-verdict" className="min-w-0 xl:w-[420px]">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="min-w-0">
        <p className="text-[11px] uppercase tracking-widest text-white/40">L0 运行判定</p>
        <p className={cn('mt-2 text-base font-semibold leading-6', METRIC_VALUE_CLASS_BY_TONE[verdict.tone])}>{verdict.title}</p>
      </div>
      <TerminalChip variant={chipVariant(verdict.tone)} className="shrink-0 font-semibold">
        {verdict.level}
      </TerminalChip>
    </div>
    <p className="mt-3 text-xs leading-5 text-white/58">{verdict.description}</p>
    <div className="mt-4 grid grid-cols-1 gap-3 text-[11px] text-white/44 sm:grid-cols-2">
      <p>
        运维影响
        <span className="mt-1 block text-white/72">{verdict.impact}</span>
      </p>
      <p>
        管理员下一步
        <span className="mt-1 block text-white/72">{verdict.nextAction}</span>
      </p>
    </div>
    <p className="mt-3 truncate font-mono text-[11px] text-white/34">生成 {safeDate(generatedAt)} · 只读观测</p>
  </TerminalNestedBlock>
);

const OperatorActionListPanel: React.FC<{ actions: OperatorActionItem[]; isLoading: boolean }> = ({ actions, isLoading }) => (
  <TerminalPanel as="section" data-testid="provider-circuit-action-list">
    <TerminalSectionHeader
      eyebrow="L2 动作队列"
      title="优先处理项"
      action={<TerminalChip variant={actions.length ? 'caution' : 'success'}>{isLoading ? '读取中' : `${actions.length} 项`}</TerminalChip>}
    />
    {isLoading ? (
      <TerminalNotice variant="neutral" className="mt-4">
        正在根据现有熔断、SLA、配额与探测快照生成动作队列。
      </TerminalNotice>
    ) : actions.length === 0 ? (
      <TerminalNotice variant="neutral" className="mt-4">
        暂无需要管理员处理的 provider 熔断动作；如需审计证据，可展开 L3 诊断细节。
      </TerminalNotice>
    ) : (
      <ol className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
        {actions.map((action, index) => (
          <li key={action.id}>
            <TerminalNestedBlock className="h-full min-w-0">
              <div className="flex min-w-0 items-start gap-3">
                <span className={cn('mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md border text-[11px] font-semibold', METRIC_VALUE_CLASS_BY_TONE[action.tone])}>
                  {index + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="min-w-0 text-sm font-semibold text-white">{action.issue}</p>
                    <TerminalChip variant={chipVariant(action.tone)} className="shrink-0">
                      {action.tone === 'danger' ? 'BLOCKED' : 'DEGRADED'}
                    </TerminalChip>
                  </div>
                  <dl className="mt-3 grid grid-cols-1 gap-2 text-xs leading-5 text-white/48 md:grid-cols-2">
                    <div className="min-w-0">
                      <dt className="font-medium text-white/38">影响</dt>
                      <dd className="mt-0.5 text-white/70">{action.impact}</dd>
                    </div>
                    <div className="min-w-0">
                      <dt className="font-medium text-white/38">下一步</dt>
                      <dd className="mt-0.5 text-white/70">{action.nextAction}</dd>
                    </div>
                  </dl>
                </div>
              </div>
            </TerminalNestedBlock>
          </li>
        ))}
      </ol>
    )}
  </TerminalPanel>
);

const LoadingState: React.FC = () => (
  <TerminalPanel as="section" role="status" aria-label="正在读取 provider 熔断诊断">
    <div className="flex items-center gap-3">
      <Activity className="h-4 w-4 animate-pulse text-cyan-200" aria-hidden="true" />
      <div>
        <p className="text-sm font-semibold text-white">正在读取 provider 熔断诊断</p>
        <p className="mt-1 text-xs text-white/46">只读取现有诊断 API，不触发 provider 调用。</p>
      </div>
    </div>
  </TerminalPanel>
);

const AdminProviderCircuitDiagnosticsPage: React.FC = () => {
  const { canReadProviders } = useProductSurface();
  const [data, setData] = useState<ProviderCircuitDiagnosticsBundle | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);

  useEffect(() => {
    if (!canReadProviders) {
      return;
    }
    let cancelled = false;
    adminProviderCircuitsApi.getDiagnostics({ limit: 50 })
      .then((payload) => {
        if (!cancelled) setData(payload);
      })
      .catch((apiError) => {
        if (!cancelled) {
          const parsed = getParsedApiError(apiError);
          setError({ ...parsed, title: '读取 provider 熔断诊断失败' });
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [canReadProviders]);

  const summary = useMemo(() => buildOperationalSummary(data), [data]);
  const operationalVerdict = useMemo(
    () => buildOperationalVerdict(summary, isLoading, Boolean(data), Boolean(error)),
    [data, error, isLoading, summary],
  );
  const summaryMetrics = useMemo(() => buildSummaryMetrics(summary), [summary]);
  const operatorActions = useMemo(() => buildOperatorActions(data), [data]);

  if (!canReadProviders) {
    return null;
  }

  return (
    <div data-testid="admin-provider-circuit-diagnostics-page" className="admin-provider-circuit-page flex min-h-0 w-full flex-1 overflow-y-auto no-scrollbar text-white">
      <TerminalPageShell className="flex min-h-0 flex-1 py-5 md:py-6">
        <TerminalPanel as="section" className="relative overflow-hidden">
          <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-300/50 to-transparent" />
          <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
            <div className="min-w-0 flex-1">
              <TerminalPageHeading eyebrow="生产调用门禁" title="Provider 熔断诊断" />
              <p className="mt-3 max-w-4xl text-sm leading-6 text-white/54">
                {isLoading
                  ? '正在读取只读诊断快照'
                  : '先判断生产调用是否可继续、哪里被阻断、需要管理员处理什么；事件、配额、探测与 bucket 细节默认折叠。'}
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <TerminalChip variant="info">只读诊断</TerminalChip>
                <TerminalChip variant={data?.states.metadata?.noExternalCalls === true ? 'success' : 'caution'}>
                  {data?.states.metadata?.noExternalCalls === true ? '不触发外部调用' : '外部调用状态待确认'}
                </TerminalChip>
                <TerminalChip variant={data?.states.metadata?.liveEnforcement === false ? 'success' : 'caution'}>
                  {data?.states.metadata?.liveEnforcement === false ? '不执行熔断门禁' : '熔断门禁状态待确认'}
                </TerminalChip>
              </div>
            </div>
            <OperationalVerdictPanel verdict={operationalVerdict} generatedAt={data?.states.generatedAt} />
          </div>
          <AdminOpsL0OverviewStrip
            dataTestId="provider-circuit-l0-overview-strip"
            className="mt-5"
            systemTrustState={
              operationalVerdict.level === 'LIVE'
                ? 'healthy'
                : operationalVerdict.level === 'DEGRADED'
                  ? 'degraded'
                  : operationalVerdict.level === 'BLOCKED' || operationalVerdict.level === 'ERROR'
                    ? 'blocked'
                    : 'unknown'
            }
            impact={operationalVerdict.impact}
            recommendedAction={operationalVerdict.nextAction}
            evidenceRef="L3 诊断细节 / 熔断、SLA、事件、配额、探测"
            lastUpdated={safeDate(data?.states.generatedAt)}
          />
          {error ? <ApiErrorAlert error={error} className="mt-5" /> : null}
        </TerminalPanel>

        <div data-testid="provider-circuit-summary-metrics" className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          {summaryMetrics.map((metric) => (
            <TerminalMetric
              key={metric.label}
              label={metric.label}
              value={metric.value}
              subvalue={metric.subvalue}
              valueClassName={cn('text-sm leading-5 md:text-base', METRIC_VALUE_CLASS_BY_TONE[metric.tone])}
            />
          ))}
        </div>

        {isLoading && !data && !error ? <LoadingState /> : null}

        <OperatorActionListPanel actions={operatorActions} isLoading={isLoading && !data && !error} />

        <DiagnosticsDisclosure
          title="L2 分组诊断：熔断状态 / 事件 / 配额 / 探测 / SLA"
          summary={`${formatNumber(summary.states, 0)} 个状态 · ${formatNumber(summary.events, 0)} 个事件 · ${formatNumber(summary.quotaWindows, 0)} 个配额窗口 · 已脱敏 bucket/边界默认折叠`}
          className="px-3 py-3"
        >
          <TerminalGrid>
            <AdminOpsSectionHeading
              eyebrow="L2 / Circuit State"
              title="熔断状态与当前门禁"
              description="先判断哪些 provider 已打开/半开，以及当前页面对外呼、门禁和 redaction 的只读边界。"
              action={<TerminalChip variant="neutral">{formatNumber(summary.states, 0)} 个状态快照</TerminalChip>}
            />
            <div className="col-span-12 xl:col-span-8">
              <CurrentStatesPanel items={data?.states.items || []} />
            </div>
            <div className="col-span-12 xl:col-span-4">
              <BoundaryPanel data={data} />
            </div>
            <AdminOpsSectionHeading
              eyebrow="L2 / SLA Readiness"
              title="SLA / 凭证就绪"
              description="把 SLA、freshness、latency、错误与凭证门禁放在单独分组里，避免和熔断事件混读。"
              action={<TerminalChip variant="neutral">{formatNumber(summary.slaReadiness, 0)} 个就绪信号</TerminalChip>}
            />
            <SlaReadinessPanel items={data?.slaReadiness.items || []} />
            <AdminOpsSectionHeading
              eyebrow="L2 / Events-Quota-Probe"
              title="熔断事件、配额窗口与探测事件"
              description="这组保留原有事件、quota 与 probe 细节，但让每个子面板各自表达数量和已脱敏 bucket 影响。"
              action={<TerminalChip variant="caution">{formatNumber(summary.events + summary.quotaWindows + summary.probeEvents, 0)} 条线索</TerminalChip>}
            />
            <div className="min-w-0 xl:col-span-4">
              <ProbeEventsPanel items={data?.probeEvents.items || []} />
            </div>
            <div className="min-w-0 xl:col-span-4">
              <EventsPanel items={data?.events.items || []} />
            </div>
            <div className="min-w-0 xl:col-span-4">
              <QuotaWindowsPanel items={data?.quotaWindows.items || []} />
            </div>
          </TerminalGrid>
        </DiagnosticsDisclosure>
      </TerminalPageShell>
      <span className="sr-only">Provider 熔断诊断只读页面</span>
    </div>
  );
};

export default AdminProviderCircuitDiagnosticsPage;
