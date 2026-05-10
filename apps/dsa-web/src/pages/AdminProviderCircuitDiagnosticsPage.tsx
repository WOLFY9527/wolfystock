import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Activity, CircuitBoard, Gauge, LockKeyhole, Radar, ShieldCheck } from 'lucide-react';
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
import { ApiErrorAlert, GlassCard } from '../components/common';
import { TerminalChip } from '../components/terminal/TerminalPrimitives';
import { useProductSurface } from '../hooks/useProductSurface';
import { cn } from '../utils/cn';
import { formatDateTime, formatNumber } from '../utils/format';

type Tone = 'neutral' | 'good' | 'warn' | 'danger' | 'info';

const UNSAFE_VALUE_PATTERN = /(https?:\/\/|www\.|\?|=|token|secret|cookie|session|password|bearer|apikey|api_key|stack|trace)/i;

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
  if (normalized === 'half_open') return 'warn';
  if (normalized === 'open' || normalized === 'disabled_by_operator' || normalized === 'provider_quota_depleted') return 'danger';
  if (normalized === 'degraded_cache_only') return 'warn';
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
    live_credentials_present_live_calls_disabled: '有凭证 / live 关闭',
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

function toneClass(tone: Tone): string {
  return {
    neutral: 'text-white',
    good: 'text-emerald-300',
    warn: 'text-amber-200',
    danger: 'text-rose-200',
    info: 'text-cyan-200',
  }[tone];
}

function chipVariant(tone: Tone): 'neutral' | 'success' | 'caution' | 'danger' | 'info' {
  const variants = {
    neutral: 'neutral',
    good: 'success',
    warn: 'caution',
    danger: 'danger',
    info: 'info',
  } as const;
  return variants[tone];
}

const SummaryTile: React.FC<{ label: string; value: string | number; note?: string; tone?: Tone }> = ({ label, value, note, tone = 'neutral' }) => (
  <div className="min-w-0 rounded-2xl border border-white/5 bg-black/20 px-4 py-3">
    <p className="truncate text-[10px] font-bold uppercase tracking-[0.18em] text-white/34">{label}</p>
    <p className={cn('mt-2 text-lg font-semibold leading-tight', toneClass(tone))}>{value}</p>
    {note ? <p className="mt-1 text-xs leading-5 text-white/42">{note}</p> : null}
  </div>
);

const ReadOnlyBadges: React.FC<{ data?: ProviderCircuitDiagnosticsBundle | null }> = ({ data }) => {
  const metadata = data?.states.metadata;
  return (
    <div className="flex flex-wrap gap-2">
      <TerminalChip variant="info">只读诊断</TerminalChip>
      <TerminalChip variant="success">
        {metadata?.noExternalCalls === true ? '不触发外部调用' : '外部调用未确认'}
      </TerminalChip>
      <TerminalChip variant="success">
        {metadata?.liveEnforcement === false ? '不执行熔断 enforcement' : '执行状态未确认'}
      </TerminalChip>
      <TerminalChip variant="neutral">ops:providers:read</TerminalChip>
    </div>
  );
};

const DimensionLine: React.FC<{
  provider: string;
  providerCategory?: string | null;
  routeFamily?: string | null;
}> = ({ provider, providerCategory, routeFamily }) => (
  <p className="mt-1 truncate font-mono text-[11px] text-white/42">
    {safeText(provider)} · {safeText(providerCategory, '未分组')} · {safeText(routeFamily, '全路由')}
  </p>
);

const CurrentStatesPanel: React.FC<{ items: ProviderCircuitStateItem[] }> = ({ items }) => (
  <GlassCard as="section" className="p-4 md:p-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">当前熔断状态</p>
        <h2 className="mt-1 text-lg font-semibold text-white">Provider / Category / Route</h2>
      </div>
      <TerminalChip variant="neutral">只读快照</TerminalChip>
    </div>
    {items.length === 0 ? (
      <div className="mt-4 rounded-2xl border border-white/5 bg-black/20 px-4 py-6 text-sm text-white/50">
        暂无 provider 熔断状态
      </div>
    ) : (
      <div className="mt-4 grid grid-cols-1 gap-3 2xl:grid-cols-2">
        {items.map((item, index) => (
          <article key={`${item.provider}-${item.providerCategory || 'all'}-${item.routeFamily || 'all'}-${index}`} className="min-w-0 rounded-2xl border border-white/5 bg-black/20 p-3.5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-white">{safeText(item.provider)}</p>
                <DimensionLine provider={item.provider} providerCategory={item.providerCategory} routeFamily={item.routeFamily} />
              </div>
              <TerminalChip variant={chipVariant(stateTone(item.state))} className="shrink-0 font-semibold">
                {stateLabel(item.state)}
              </TerminalChip>
            </div>
            <div className="mt-3 grid grid-cols-1 gap-2 text-[11px] text-white/44 sm:grid-cols-3">
              <p className="min-w-0">Reason bucket <span className="block truncate font-mono text-white/68">{bucketLabel(item.reasonBucket)}</span></p>
              <p className="min-w-0">Cooldown until <span className="block truncate font-mono text-white/68">{safeDate(item.cooldownUntil)}</span></p>
              <p className="min-w-0">Updated <span className="block truncate font-mono text-white/68">{safeDate(item.updatedAt)}</span></p>
            </div>
          </article>
        ))}
      </div>
    )}
  </GlassCard>
);

const EventsPanel: React.FC<{ items: ProviderCircuitEventItem[] }> = ({ items }) => (
  <GlassCard as="section" className="p-4 md:p-5">
    <div className="flex items-start gap-3">
      <Radar className="mt-1 h-4 w-4 text-amber-200" aria-hidden="true" />
      <div>
        <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">Recent events</p>
        <h2 className="mt-1 text-base font-semibold text-white">最近熔断事件</h2>
      </div>
    </div>
    {items.length === 0 ? (
      <p className="mt-5 rounded-2xl border border-white/5 bg-black/20 px-4 py-5 text-sm text-white/50">暂无熔断事件</p>
    ) : (
      <div className="mt-5 space-y-3">
        {items.map((item, index) => (
          <article key={`${item.provider}-${item.eventType}-${item.createdAt || index}`} className="rounded-2xl border border-white/5 bg-black/20 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-white">{safeText(item.eventType)}</p>
                <DimensionLine provider={item.provider} providerCategory={item.providerCategory} routeFamily={item.routeFamily} />
              </div>
              <span className="shrink-0 font-mono text-[11px] text-white/42">{safeDate(item.createdAt)}</span>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-white/44 md:grid-cols-4">
              <p>State <span className="block truncate font-mono text-white/68">{stateLabel(item.fromState)} {'->'} {stateLabel(item.toState)}</span></p>
              <p>Reason bucket <span className="block truncate font-mono text-white/68">{bucketLabel(item.reasonBucket)}</span></p>
              <p>Request bucket <span className="block truncate font-mono text-white/68">{safeText(item.requestCountBucket)}</span></p>
              <p>Duration <span className="block truncate font-mono text-white/68">{safeText(item.durationBucketMs)} ms</span></p>
            </div>
          </article>
        ))}
      </div>
    )}
  </GlassCard>
);

const QuotaWindowsPanel: React.FC<{ items: ProviderQuotaWindowItem[] }> = ({ items }) => (
  <GlassCard as="section" className="p-4 md:p-5">
    <div className="flex items-start gap-3">
      <Gauge className="mt-1 h-4 w-4 text-cyan-200" aria-hidden="true" />
      <div>
        <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">Quota windows</p>
        <h2 className="mt-1 text-base font-semibold text-white">配额窗口</h2>
      </div>
    </div>
    {items.length === 0 ? (
      <p className="mt-5 rounded-2xl border border-white/5 bg-black/20 px-4 py-5 text-sm text-white/50">暂无配额窗口</p>
    ) : (
      <div className="mt-5 grid grid-cols-1 gap-3">
        {items.map((item, index) => (
          <article key={`${item.provider}-${item.windowStart}-${index}`} className="min-w-0 rounded-2xl border border-white/5 bg-black/20 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-white">{safeText(item.provider)}</p>
                <DimensionLine provider={item.provider} providerCategory={item.providerCategory} routeFamily={item.routeFamily} />
              </div>
              <TerminalChip variant="info" className="shrink-0 font-mono">
                {safeText(item.windowType)}
              </TerminalChip>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-white/44 md:grid-cols-4">
              <p>Requests <span className="block font-mono text-white/68">{formatNumber(item.requestCount, 0)}</span></p>
              <p>Rejected <span className="block font-mono text-rose-100/80">{formatNumber(item.rejectedCount, 0)}</span></p>
              <p>Success / Failure <span className="block font-mono text-white/68">{formatNumber(item.successCount, 0)} / {formatNumber(item.failureCount, 0)}</span></p>
              <p>Probe <span className="block font-mono text-white/68">{formatNumber(item.probeCount, 0)}</span></p>
              <p>Reserved / Consumed <span className="block font-mono text-white/68">{formatNumber(item.reservedUnits, 0)} / {formatNumber(item.consumedUnits, 0)}</span></p>
              <p>429 / 403 <span className="block font-mono text-white/68">{formatNumber(item.provider429Count, 0)} / {formatNumber(item.provider403Count, 0)}</span></p>
              <p>Cache / stale <span className="block font-mono text-white/68">{formatNumber(item.cacheOnlyCount, 0)} / {formatNumber(item.staleServedCount, 0)}</span></p>
              <p>Window <span className="block truncate font-mono text-white/68">{safeDate(item.windowStart)}</span></p>
            </div>
          </article>
        ))}
      </div>
    )}
  </GlassCard>
);

const ProbeEventsPanel: React.FC<{ items: ProviderProbeEventItem[] }> = ({ items }) => (
  <GlassCard as="section" className="p-4 md:p-5">
    <div className="flex items-start gap-3">
      <ShieldCheck className="mt-1 h-4 w-4 text-emerald-200" aria-hidden="true" />
      <div>
        <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">Probe events</p>
        <h2 className="mt-1 text-base font-semibold text-white">探测事件</h2>
      </div>
    </div>
    {items.length === 0 ? (
      <p className="mt-5 rounded-2xl border border-white/5 bg-black/20 px-4 py-5 text-sm text-white/50">暂无探测事件</p>
    ) : (
      <div className="mt-5 space-y-3">
        {items.map((item, index) => (
          <article key={`${item.provider}-${item.probeType}-${item.createdAt || index}`} className="rounded-2xl border border-white/5 bg-black/20 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-white">{safeText(item.probeType)}</p>
                <DimensionLine provider={item.provider} providerCategory={item.providerCategory} routeFamily={item.routeFamily} />
              </div>
              <TerminalChip variant="success" className="shrink-0 font-semibold">
                {bucketLabel(item.resultBucket)}
              </TerminalChip>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-white/44 md:grid-cols-3">
              <p>Source <span className="block truncate font-mono text-white/68">{safeText(item.probeSource)}</span></p>
              <p>Duration <span className="block truncate font-mono text-white/68">{safeText(item.durationBucketMs)} ms</span></p>
              <p>Created <span className="block truncate font-mono text-white/68">{safeDate(item.createdAt)}</span></p>
            </div>
          </article>
        ))}
      </div>
    )}
  </GlassCard>
);

const SlaReadinessPanel: React.FC<{ items: ProviderSlaReadinessItem[] }> = ({ items }) => (
  <GlassCard as="section" className="p-4 md:p-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">SLA readiness</p>
        <h2 className="mt-1 text-base font-semibold text-white">Provider SLA / 凭证就绪</h2>
      </div>
      <TerminalChip variant="neutral">只读 · 无 live call</TerminalChip>
    </div>
    {items.length === 0 ? (
      <p className="mt-5 rounded-2xl border border-white/5 bg-black/20 px-4 py-5 text-sm text-white/50">暂无 SLA/readiness 诊断</p>
    ) : (
      <div className="mt-5 grid grid-cols-1 gap-3">
        {items.map((item, index) => (
          <article key={`${item.provider}-${item.providerCategory || 'all'}-${item.routeFamily || 'all'}-${index}`} className="min-w-0 rounded-2xl border border-white/5 bg-black/20 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-white">{safeText(item.provider)}</p>
                <DimensionLine provider={item.provider} providerCategory={item.providerCategory} routeFamily={item.routeFamily} />
              </div>
              <TerminalChip variant={chipVariant(readinessTone(item.readinessState))} className="shrink-0 font-semibold">
                {credentialLabel(item.credentialState)}
              </TerminalChip>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-white/44 md:grid-cols-4">
              <p>Latency <span className="block truncate font-mono text-white/68">{latencyLabel(item.latencyState)} · {safeText(item.latencyBucketMs)} ms</span></p>
              <p>Freshness <span className="block truncate font-mono text-white/68">{freshnessLabel(item.freshnessState)} · {safeText(item.freshnessSeconds)} s</span></p>
              <p>Error state <span className="block truncate font-mono text-white/68">{safeText(item.errorState)} · {safeText(item.errorRate)}</span></p>
              <p>Circuit advisory <span className="block truncate font-mono text-white/68">{safeText(item.circuitAdvisoryState)} / {stateLabel(item.circuitStateCandidate)}</span></p>
              <p>Credentials <span className="block truncate font-mono text-white/68">{boolLabel(item.credentialsPresent)} · dry-run {boolLabel(item.dryRunEnabled)}</span></p>
              <p>Live calls <span className="block truncate font-mono text-white/68">{boolLabel(item.liveHttpCallsEnabled)}</span></p>
              <p>Ordering / fallback <span className="block truncate font-mono text-white/68">{boolLabel(item.wouldChangeProviderOrder)} / {boolLabel(item.wouldChangeFallbackBehavior)}</span></p>
              <p>Would block <span className="block truncate font-mono text-white/68">{boolLabel(item.wouldBlockCall)}</span></p>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 rounded-2xl border border-white/5 bg-white/[0.02] px-3 py-2 text-[11px] text-white/44 md:grid-cols-4">
              <p>Trend requests <span className="block truncate font-mono text-white/68">{safeText(item.trendSummary?.requestCountBucket, '0')}</span></p>
              <p>Trend failures <span className="block truncate font-mono text-white/68">{safeText(item.trendSummary?.failureCountBucket, '0')}</span></p>
              <p>Trend 429 / 403 <span className="block truncate font-mono text-white/68">{safeText(item.trendSummary?.provider429CountBucket, '0')} / {safeText(item.trendSummary?.provider403CountBucket, '0')}</span></p>
              <p>Latest observation <span className="block truncate font-mono text-white/68">{safeDate(item.trendSummary?.latestObservationAt)}</span></p>
            </div>
            <details className="mt-3 rounded-2xl border border-white/5 bg-white/[0.02] px-3 py-2 text-[11px] text-white/48">
              <summary className="cursor-pointer select-none text-white/60">最近错误 buckets</summary>
              <div className="mt-2 space-y-1">
                {(item.recentErrors || []).length === 0 ? (
                  <p>暂无错误 bucket</p>
                ) : item.recentErrors.map((error) => (
                  <p key={`${error.reasonBucket}-${error.latestAt || 'none'}`} className="font-mono">
                    {bucketLabel(error.reasonBucket)} · {safeText(error.countBucket)} · {safeDate(error.latestAt)}
                  </p>
                ))}
              </div>
            </details>
          </article>
        ))}
      </div>
    )}
  </GlassCard>
);

const BoundaryPanel: React.FC = () => (
  <GlassCard as="section" className="p-4 md:p-5">
    <div className="flex items-start gap-3">
      <LockKeyhole className="mt-1 h-4 w-4 text-emerald-200" aria-hidden="true" />
      <div>
        <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">边界</p>
        <h2 className="mt-1 text-base font-semibold text-white">诊断观测</h2>
        <p className="mt-2 text-sm leading-6 text-white/50">
          当前为诊断观测，不会改变 provider fallback 或 MarketCache 行为。
        </p>
      </div>
    </div>
  </GlassCard>
);

const LoadingState: React.FC = () => (
  <GlassCard as="section" className="mt-5 p-4 md:p-5" role="status" aria-label="正在读取 provider 熔断诊断">
    <div className="flex items-center gap-3">
      <Activity className="h-4 w-4 animate-pulse text-cyan-200" aria-hidden="true" />
      <div>
        <p className="text-sm font-semibold text-white">正在读取 provider 熔断诊断</p>
        <p className="mt-1 text-xs text-white/46">只读取现有诊断 API，不触发 provider 调用。</p>
      </div>
    </div>
  </GlassCard>
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

  const summary = useMemo(() => {
    const states = data?.states.items || [];
    const openCount = states.filter((item) => stateTone(item.state) === 'danger').length;
    const warnCount = states.filter((item) => stateTone(item.state) === 'warn').length;
    return {
      states: states.length,
      open: openCount,
      warn: warnCount,
      events: data?.events.items.length || 0,
      quotaWindows: data?.quotaWindows.items.length || 0,
      probeEvents: data?.probeEvents.items.length || 0,
      slaReadiness: data?.slaReadiness.items.length || 0,
    };
  }, [data]);

  if (!canReadProviders) {
    return null;
  }
  const productionCallState = isLoading && !data
    ? '读取中'
    : summary.open
      ? '部分生产调用应暂缓'
      : summary.warn
        ? '可继续但需观察降级'
        : '可继续观察';
  const blockedState = summary.open
    ? `${summary.open} 个熔断打开`
    : summary.warn
      ? `${summary.warn} 个降级观察`
      : '未发现阻断';

  return (
    <div data-testid="admin-provider-circuit-diagnostics-page" className="admin-provider-circuit-page flex min-h-0 w-full flex-1 flex-col overflow-y-auto no-scrollbar bg-[#050505] px-4 py-5 text-white md:px-6 xl:px-8">
      <GlassCard as="section" className="relative shrink-0 overflow-hidden p-5 md:p-6">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-300/50 to-transparent" />
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2 text-[10px] font-bold uppercase tracking-[0.22em] text-cyan-200/80">
              <CircuitBoard className="h-4 w-4" aria-hidden="true" />
              生产调用门禁
            </div>
            <h1 className="mt-3 text-3xl font-semibold tracking-normal text-white md:text-4xl">Provider 熔断诊断</h1>
            <p className="mt-3 max-w-4xl text-sm leading-6 text-white/54">
              {isLoading
                ? '正在读取只读诊断快照'
                : `先判断生产调用是否可继续、哪里被阻断、是否缺凭证；路由、bucket、配额、探测细节默认后置。生成 ${safeDate(data?.states.generatedAt)} · 只读观测`}
            </p>
          </div>
          <ReadOnlyBadges data={data} />
        </div>
        {error ? <ApiErrorAlert error={error} className="mt-5" /> : null}
        <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          <SummaryTile label="页面用途" value="定位 provider 熔断风险" note="SLA、熔断、配额与探测集中查看" tone="info" />
          <SummaryTile label="当前状态" value={productionCallState} note="只读判断，不改变 provider fallback 或 MarketCache" tone={summary.open ? 'danger' : summary.warn ? 'warn' : 'good'} />
          <SummaryTile
            label="当前阻断"
            value={blockedState}
            note={`${summary.warn} 个降级观察 · ${summary.states || 0} 个状态快照`}
            tone={summary.open ? 'danger' : summary.warn ? 'warn' : 'good'}
          />
          <SummaryTile label="下一步" value={summary.open || summary.warn ? '先核对凭证与当前熔断' : '保持观察，必要时展开诊断细节'} note="事件、配额、探测细节默认后置" tone={summary.open || summary.warn ? 'warn' : 'neutral'} />
        </div>
        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
          <SummaryTile label="需关注" value={`${summary.open} 打开 / ${summary.warn} 降级`} tone={summary.open ? 'danger' : summary.warn ? 'warn' : 'good'} />
          <SummaryTile label="就绪度" value={`${summary.slaReadiness || 0} 个 SLA`} note={`${summary.probeEvents || 0} 个探测事件`} tone="info" />
          <SummaryTile label="诊断范围" value={`${summary.events || 0} 事件 / ${summary.quotaWindows || 0} 配额窗口`} tone="neutral" />
        </div>
      </GlassCard>

      {isLoading && !data && !error ? <LoadingState /> : null}

      <div className="mt-5 shrink-0">
        <SlaReadinessPanel items={data?.slaReadiness.items || []} />
      </div>

      <div className="mt-5 grid shrink-0 grid-cols-1 gap-5 xl:grid-cols-12">
        <div className="min-w-0 xl:col-span-8">
          <CurrentStatesPanel items={data?.states.items || []} />
        </div>
        <div className="min-w-0 space-y-5 xl:col-span-4">
          <BoundaryPanel />
        </div>
      </div>

      <details className="mt-5 rounded-[20px] border border-white/5 bg-white/[0.02] p-4 backdrop-blur-md [&>summary::-webkit-details-marker]:hidden">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-xl text-sm font-semibold text-white/76 outline-none transition-colors focus-visible:ring-2 focus-visible:ring-cyan-300/30">
          <span>二级细节：探测、事件、配额窗口、路由 bucket</span>
          <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[11px] font-medium text-white/42">默认折叠</span>
        </summary>
        <div className="mt-5 grid shrink-0 grid-cols-1 gap-5 xl:grid-cols-12">
          <div className="min-w-0 xl:col-span-4">
            <ProbeEventsPanel items={data?.probeEvents.items || []} />
          </div>
          <div className="min-w-0 xl:col-span-4">
            <EventsPanel items={data?.events.items || []} />
          </div>
          <div className="min-w-0 xl:col-span-4">
            <QuotaWindowsPanel items={data?.quotaWindows.items || []} />
          </div>
        </div>
      </details>
    </div>
  );
};

export default AdminProviderCircuitDiagnosticsPage;
