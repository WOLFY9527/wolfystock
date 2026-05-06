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
} from '../api/adminProviderCircuits';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { ApiErrorAlert, Badge, GlassCard } from '../components/common';
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

function toneClass(tone: Tone): string {
  return {
    neutral: 'text-white',
    good: 'text-emerald-300',
    warn: 'text-amber-200',
    danger: 'text-rose-200',
    info: 'text-cyan-200',
  }[tone];
}

const SummaryTile: React.FC<{ label: string; value: string | number; tone?: Tone }> = ({ label, value, tone = 'neutral' }) => (
  <div className="min-w-0 rounded-2xl border border-white/5 bg-black/20 px-4 py-3">
    <p className="truncate text-[10px] font-bold uppercase tracking-[0.18em] text-white/34">{label}</p>
    <p className={cn('mt-2 font-mono text-2xl font-semibold leading-none', toneClass(tone))}>{value}</p>
  </div>
);

const ReadOnlyBadges: React.FC<{ data?: ProviderCircuitDiagnosticsBundle | null }> = ({ data }) => {
  const metadata = data?.states.metadata;
  return (
    <div className="flex flex-wrap gap-2">
      <Badge variant="info" className="border-cyan-300/25 bg-cyan-400/10 text-cyan-100">只读诊断</Badge>
      <Badge variant="success" className="border-emerald-300/25 bg-emerald-400/10 text-emerald-100">
        {metadata?.noExternalCalls === true ? '不触发外部调用' : '外部调用未确认'}
      </Badge>
      <Badge variant="success" className="border-emerald-300/25 bg-emerald-400/10 text-emerald-100">
        {metadata?.liveEnforcement === false ? '不执行熔断 enforcement' : '执行状态未确认'}
      </Badge>
      <Badge variant="default" className="border-white/10 bg-white/[0.04] text-white/62">ops:providers:read</Badge>
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
      <Badge variant="default" className="border-white/10 bg-white/[0.04] text-white/58">只读快照</Badge>
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
              <span className={cn('shrink-0 rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[11px] font-semibold', toneClass(stateTone(item.state)))}>
                {stateLabel(item.state)}
              </span>
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
              <span className="shrink-0 rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 font-mono text-[11px] text-cyan-100">{safeText(item.windowType)}</span>
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
              <span className="shrink-0 rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[11px] font-semibold text-emerald-100">{bucketLabel(item.resultBucket)}</span>
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
    return {
      states: states.length,
      open: openCount,
      events: data?.events.items.length || 0,
      quotaWindows: data?.quotaWindows.items.length || 0,
      probeEvents: data?.probeEvents.items.length || 0,
    };
  }, [data]);

  if (!canReadProviders) {
    return null;
  }

  return (
    <div className="admin-provider-circuit-page flex min-h-0 w-full flex-1 flex-col overflow-y-auto no-scrollbar bg-[#050505] px-4 py-5 text-white md:px-6 xl:px-8">
      <GlassCard as="section" className="relative shrink-0 overflow-hidden p-5 md:p-6">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-300/50 to-transparent" />
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2 text-[10px] font-bold uppercase tracking-[0.22em] text-cyan-200/80">
              <CircuitBoard className="h-4 w-4" aria-hidden="true" />
              Provider circuit diagnostics
            </div>
            <h1 className="mt-3 text-3xl font-semibold tracking-normal text-white md:text-4xl">Provider 熔断诊断</h1>
            <p className="mt-3 max-w-4xl text-sm leading-6 text-white/54">
              {isLoading
                ? '正在读取只读诊断快照'
                : `生成 ${safeDate(data?.states.generatedAt)} · 只读观测 · 不改变 fallback / MarketCache`}
            </p>
          </div>
          <ReadOnlyBadges data={data} />
        </div>
        {error ? <ApiErrorAlert error={error} className="mt-5" /> : null}
        <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
          <SummaryTile label="状态" value={summary.states || '--'} tone="info" />
          <SummaryTile label="打开/阻断" value={summary.open || 0} tone={summary.open ? 'danger' : 'good'} />
          <SummaryTile label="事件" value={summary.events || '--'} tone="info" />
          <SummaryTile label="配额窗口" value={summary.quotaWindows || '--'} tone="neutral" />
          <SummaryTile label="探测" value={summary.probeEvents || '--'} tone="neutral" />
        </div>
      </GlassCard>

      {isLoading && !data && !error ? <LoadingState /> : null}

      <div className="mt-5 grid shrink-0 grid-cols-1 gap-5 xl:grid-cols-12">
        <div className="min-w-0 xl:col-span-8">
          <CurrentStatesPanel items={data?.states.items || []} />
        </div>
        <div className="min-w-0 space-y-5 xl:col-span-4">
          <BoundaryPanel />
          <ProbeEventsPanel items={data?.probeEvents.items || []} />
        </div>
      </div>

      <div className="mt-5 grid shrink-0 grid-cols-1 gap-5 xl:grid-cols-12">
        <div className="min-w-0 xl:col-span-7">
          <EventsPanel items={data?.events.items || []} />
        </div>
        <div className="min-w-0 xl:col-span-5">
          <QuotaWindowsPanel items={data?.quotaWindows.items || []} />
        </div>
      </div>
    </div>
  );
};

export default AdminProviderCircuitDiagnosticsPage;
