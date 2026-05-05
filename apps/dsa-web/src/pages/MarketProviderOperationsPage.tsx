import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Activity, DatabaseZap, ExternalLink, LockKeyhole, Radar, ServerCog } from 'lucide-react';
import {
  marketProviderOperationsApi,
  type AdminLogDrillThrough,
  type MarketProviderCacheState,
  type MarketProviderEventRollup,
  type MarketProviderOperationItem,
  type MarketProviderOperationsResponse,
} from '../api/marketProviderOperations';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { ApiErrorAlert, Badge, Disclosure, GlassCard } from '../components/common';
import { DataFreshnessBadge } from '../components/market-overview/marketOverviewPrimitives';
import type { MarketProviderHealthStatus } from '../api/marketOverview';
import { useI18n } from '../contexts/UiLanguageContext';
import { cn } from '../utils/cn';
import { formatDateTime, formatNumber, formatPercent } from '../utils/format';

type StatusTone = 'live' | 'cache' | 'stale' | 'fallback' | 'partial' | 'unavailable' | 'error' | 'refreshing';

const STATUS_SET = new Set<StatusTone>(['live', 'cache', 'stale', 'fallback', 'partial', 'unavailable', 'error', 'refreshing']);

function normalizeStatus(value: unknown): StatusTone {
  const normalized = String(value || '').trim().toLowerCase().replace(/[-\s]+/g, '_');
  return STATUS_SET.has(normalized as StatusTone) ? normalized as StatusTone : 'unavailable';
}

function formatDate(value?: string | null): string {
  if (!value) return '--';
  return formatDateTime(value);
}

function compactNumber(value?: number | null, digits = 0): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '--';
  return formatNumber(value, digits);
}

function providerLabel(item: Pick<MarketProviderOperationItem, 'provider' | 'sourceLabel'>): string {
  return item.sourceLabel || item.provider || 'unknown';
}

function buildAdminLogHref(drill?: AdminLogDrillThrough): string | null {
  if (!drill?.route) return null;
  const query = new URLSearchParams();
  Object.entries(drill.query || {}).forEach(([key, value]) => {
    if (value) query.set(key, value);
  });
  if (drill.eventId) {
    query.set('eventId', drill.eventId);
  }
  const queryText = query.toString();
  return queryText ? `${drill.route}?${queryText}` : drill.route;
}

function safeMetadataSummary(response: MarketProviderOperationsResponse): Record<string, unknown> {
  return {
    generatedAt: response.generatedAt,
    window: response.window,
    counts: {
      items: response.items.length,
      eventRollups: response.eventRollups.length,
      cacheStates: response.cacheStates.length,
      limitations: response.limitations.length,
    },
    contract: {
      readOnly: response.metadata.readOnly === true,
      externalProviderCalls: response.metadata.externalProviderCalls === true,
      cacheMutation: response.metadata.cacheMutation === true,
      source: response.metadata.source,
    },
  };
}

const SummaryTile: React.FC<{
  label: string;
  value: number | string;
  tone?: 'neutral' | 'good' | 'warn' | 'danger' | 'info';
}> = ({ label, value, tone = 'neutral' }) => {
  const toneClass = {
    neutral: 'text-white',
    good: 'text-emerald-300',
    warn: 'text-amber-200',
    danger: 'text-rose-200',
    info: 'text-cyan-200',
  }[tone];
  return (
    <div className="min-w-0 rounded-2xl border border-white/5 bg-black/20 px-4 py-3">
      <p className="truncate text-[10px] font-bold uppercase tracking-[0.18em] text-white/34">{label}</p>
      <p className={cn('mt-2 font-mono text-2xl font-semibold leading-none', toneClass)}>{value}</p>
    </div>
  );
};

const ReadOnlyBadges: React.FC<{ response?: MarketProviderOperationsResponse | null }> = ({ response }) => {
  const metadata = response?.metadata || {};
  return (
    <div className="flex flex-wrap gap-2">
      <Badge variant="info" className="border-cyan-300/25 bg-cyan-400/10 text-cyan-100">
        只读
      </Badge>
      <Badge variant="success" className="border-emerald-300/25 bg-emerald-400/10 text-emerald-100">
        {metadata.externalProviderCalls === false ? '外部调用关闭' : '未确认外部调用'}
      </Badge>
      <Badge variant="success" className="border-emerald-300/25 bg-emerald-400/10 text-emerald-100">
        {metadata.cacheMutation === false ? '缓存不变更' : '缓存变更未确认'}
      </Badge>
      <Badge variant="default" className="border-white/10 bg-white/[0.04] text-white/62">
        Window {response?.window?.key || '24h'}
      </Badge>
    </div>
  );
};

const DrillLink: React.FC<{ drill?: AdminLogDrillThrough; className?: string }> = ({ drill, className }) => {
  const href = buildAdminLogHref(drill);
  if (!drill?.label || !href) return null;
  return (
    <a
      href={href}
      className={cn('inline-flex min-h-8 items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[11px] font-semibold text-white/62 transition hover:border-cyan-300/25 hover:text-cyan-100', className)}
    >
      {drill.label}
      <ExternalLink className="h-3 w-3" aria-hidden="true" />
    </a>
  );
};

const ProviderOperationsPanel: React.FC<{ items: MarketProviderOperationItem[] }> = ({ items }) => (
  <GlassCard as="section" className="p-4 md:p-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">Providers</p>
        <h2 className="mt-1 text-lg font-semibold text-white">数据源运维矩阵</h2>
      </div>
      <Badge variant="default" className="border-white/10 bg-white/[0.04] text-white/58">Read only</Badge>
    </div>
    {items.length === 0 ? (
      <div className="mt-5 rounded-2xl border border-white/5 bg-black/20 px-4 py-8 text-sm text-white/50">
        暂无数据源运维条目
      </div>
    ) : (
      <div className="mt-5 overflow-x-auto no-scrollbar">
        <table className="min-w-[860px] w-full border-separate border-spacing-y-2 text-left">
          <thead className="text-[10px] uppercase tracking-[0.18em] text-white/34">
            <tr>
              <th className="px-3 py-2">来源</th>
              <th className="px-3 py-2">状态</th>
              <th className="px-3 py-2">时间</th>
              <th className="px-3 py-2">缓存</th>
              <th className="px-3 py-2">事件</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const status = normalizeStatus(item.status);
              return (
                <tr key={`${item.cacheKey}-${item.endpoint}`} className="rounded-2xl bg-white/[0.018] text-sm text-white/70">
                  <td className="rounded-l-2xl border-y border-l border-white/5 px-3 py-3 align-top">
                    <p className="font-semibold text-white">{providerLabel(item)}</p>
                    <p className="mt-1 font-mono text-[11px] text-white/40">{item.provider}</p>
                    <p className="mt-1 text-[11px] text-white/34">{item.domain} · {item.sourceType || 'source'}</p>
                  </td>
                  <td className="border-y border-white/5 px-3 py-3 align-top">
                    <div className="flex flex-wrap gap-1.5">
                      <DataFreshnessBadge status={status as MarketProviderHealthStatus} />
                      {item.isRefreshing ? <DataFreshnessBadge status="refreshing" /> : null}
                      {item.isFallback || item.fallbackUsed ? <DataFreshnessBadge status="fallback" /> : null}
                    </div>
                    {item.warning ? <p className="mt-2 text-[11px] leading-4 text-amber-200/80">{item.warning}</p> : null}
                  </td>
                  <td className="border-y border-white/5 px-3 py-3 align-top font-mono text-[11px] text-white/52">
                    <p>asOf {formatDate(item.asOf)}</p>
                    <p className="mt-1">update {formatDate(item.updatedAt)}</p>
                    <p className="mt-1">latency {compactNumber(item.latencyMs, 0)} ms</p>
                  </td>
                  <td className="border-y border-white/5 px-3 py-3 align-top">
                    <p className="font-mono text-xs text-white/72">{item.cacheKey}</p>
                    <p className="mt-1 text-[11px] text-white/42">{item.card}</p>
                    <p className="mt-1 text-[11px] text-white/42">last good {item.lastKnownGoodAgeMinutes ?? '--'} min</p>
                  </td>
                  <td className="rounded-r-2xl border-y border-r border-white/5 px-3 py-3 align-top">
                    <p className="max-w-[220px] truncate text-[11px] text-white/44">{item.endpoint}</p>
                    {item.errorSummary ? <p className="mt-1 max-w-[220px] truncate text-[11px] text-rose-200/70">最近异常已脱敏</p> : null}
                    <DrillLink drill={item.adminLogDrillThrough} className="mt-2" />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    )}
  </GlassCard>
);

const CacheStatesPanel: React.FC<{ cacheStates: MarketProviderCacheState[] }> = ({ cacheStates }) => (
  <GlassCard as="section" className="p-4 md:p-5">
    <div className="flex items-start gap-3">
      <DatabaseZap className="mt-1 h-4 w-4 text-cyan-200" aria-hidden="true" />
      <div>
        <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">Cache</p>
        <h2 className="mt-1 text-base font-semibold text-white">缓存状态</h2>
      </div>
    </div>
    {cacheStates.length === 0 ? (
      <p className="mt-5 rounded-2xl border border-white/5 bg-black/20 px-4 py-5 text-sm text-white/50">暂无缓存状态</p>
    ) : (
      <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {cacheStates.map((state) => {
          const status = normalizeStatus(state.status);
          return (
            <div key={state.cacheKey} className="min-w-0 rounded-2xl border border-white/5 bg-black/20 p-4">
              <div className="flex items-start justify-between gap-3">
                <p className="min-w-0 truncate font-mono text-sm font-semibold text-white">{state.cacheKey}</p>
                <DataFreshnessBadge status={status as MarketProviderHealthStatus} />
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-white/44">
                <p>TTL <span className="font-mono text-white/68">{state.ttlSeconds ?? '--'}s</span></p>
                <p>Snapshot <span className="font-mono text-white/68">{state.persistentSnapshotAvailable ? 'yes' : 'no'}</span></p>
                <p className="col-span-2">Fetched <span className="font-mono text-white/68">{formatDate(state.fetchedAt)}</span></p>
                <p className="col-span-2">Expires <span className="font-mono text-white/68">{formatDate(state.expiresAt)}</span></p>
              </div>
              {state.isRefreshing || state.isFresh === false || state.lastError ? (
                <div className="mt-3 rounded-xl border border-amber-300/15 bg-amber-400/8 px-3 py-2 text-[11px] leading-4 text-amber-100/80">
                  {state.isRefreshing ? '刷新中 · ' : ''}
                  {state.isFresh === false ? '缓存已过期 · ' : ''}
                  {state.lastError ? '最近错误已脱敏' : '等待下一次读取快照'}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    )}
  </GlassCard>
);

const EventRollupsPanel: React.FC<{ eventRollups: MarketProviderEventRollup[] }> = ({ eventRollups }) => (
  <GlassCard as="section" className="p-4 md:p-5">
    <div className="flex items-start gap-3">
      <Radar className="mt-1 h-4 w-4 text-amber-200" aria-hidden="true" />
      <div>
        <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">Events</p>
        <h2 className="mt-1 text-base font-semibold text-white">市场事件回卷</h2>
      </div>
    </div>
    {eventRollups.length === 0 ? (
      <p className="mt-5 rounded-2xl border border-white/5 bg-black/20 px-4 py-5 text-sm text-white/50">窗口内暂无降级事件</p>
    ) : (
      <div className="mt-5 space-y-3">
        {eventRollups.map((rollup) => (
          <div key={`${rollup.provider}-${rollup.endpoint || rollup.card || rollup.latestLogEventId}`} className="rounded-2xl border border-white/5 bg-black/20 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-semibold text-white">{rollup.provider}</p>
                <p className="mt-1 text-[11px] text-white/40">{rollup.card || rollup.endpoint || rollup.category || 'market provider'}</p>
              </div>
              <DrillLink drill={rollup.adminLogDrillThrough} />
            </div>
            <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-5">
              <SummaryTile label="事件" value={rollup.eventCount} tone="info" />
              <SummaryTile label="失败" value={rollup.failureCount} tone={rollup.failureCount ? 'danger' : 'neutral'} />
              <SummaryTile label="备用" value={rollup.fallbackCount} tone={rollup.fallbackCount ? 'warn' : 'neutral'} />
              <SummaryTile label="慢请求" value={rollup.slowCount} tone={rollup.slowCount ? 'warn' : 'neutral'} />
              <SummaryTile label="失败率" value={formatPercent(rollup.failureRate, { mode: 'ratio' })} tone={rollup.failureRate > 0 ? 'danger' : 'good'} />
            </div>
            {rollup.topReasons.length ? (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {rollup.topReasons.map((reason) => (
                  <Badge key={reason} variant="default" className="border-white/10 bg-white/[0.035] text-white/58">{reason}</Badge>
                ))}
              </div>
            ) : null}
          </div>
        ))}
      </div>
    )}
  </GlassCard>
);

const LimitationsPanel: React.FC<{ response: MarketProviderOperationsResponse }> = ({ response }) => (
  <GlassCard as="section" className="p-4 md:p-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">Limitations</p>
        <h2 className="mt-1 text-base font-semibold text-white">限制与开发者细节</h2>
      </div>
      <DrillLink drill={response.adminLogDrillThrough} />
    </div>
    <div className="mt-4 flex flex-wrap gap-2">
      {response.limitations.length ? response.limitations.map((limitation) => (
        <Badge key={limitation} variant="warning" className="border-amber-300/25 bg-amber-400/10 text-amber-100">
          {limitation}
        </Badge>
      )) : (
        <Badge variant="success" className="border-emerald-300/25 bg-emerald-400/10 text-emerald-100">暂无限制</Badge>
      )}
    </div>
    <Disclosure
      summary="开发者 / 响应形状"
      className="mt-5"
      bodyClassName="rounded-2xl border border-white/5 bg-black/20 p-3"
    >
      <pre className="max-h-72 overflow-y-auto no-scrollbar whitespace-pre-wrap break-words text-[11px] leading-5 text-white/50">
        {JSON.stringify(safeMetadataSummary(response), null, 2)}
      </pre>
    </Disclosure>
  </GlassCard>
);

const MarketProviderOperationsPage: React.FC = () => {
  const { language } = useI18n();
  const [response, setResponse] = useState<MarketProviderOperationsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);

  useEffect(() => {
    let cancelled = false;
    marketProviderOperationsApi.getOperations()
      .then((payload) => {
        if (!cancelled) setResponse(payload);
      })
      .catch((apiError) => {
        if (!cancelled) {
          const parsed = getParsedApiError(apiError);
          setError({ ...parsed, title: '读取市场数据源运维失败' });
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const summary = response?.summary;
  const summaryTiles = useMemo(() => {
    if (!summary) return [];
    return [
      { label: 'Provider', value: summary.totalItems, tone: 'info' as const },
      { label: 'Live', value: summary.liveCount, tone: 'good' as const },
      { label: 'Fallback', value: summary.fallbackCount, tone: summary.fallbackCount ? 'warn' as const : 'neutral' as const },
      { label: 'Errors', value: summary.errorCount + summary.failureCount, tone: summary.errorCount + summary.failureCount ? 'danger' as const : 'neutral' as const },
      { label: 'Refreshing', value: summary.refreshingCount, tone: summary.refreshingCount ? 'info' as const : 'neutral' as const },
      { label: 'Events', value: summary.eventCount, tone: summary.eventCount ? 'info' as const : 'neutral' as const },
    ];
  }, [summary]);

  return (
    <div className="market-provider-operations-page flex min-h-0 w-full flex-1 flex-col overflow-y-auto no-scrollbar bg-[#050505] px-4 py-5 text-white md:px-6 xl:px-8">
      <GlassCard as="section" className="relative shrink-0 overflow-hidden p-5 md:p-6">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-300/50 to-transparent" />
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2 text-[10px] font-bold uppercase tracking-[0.22em] text-cyan-200/80">
              <ServerCog className="h-4 w-4" aria-hidden="true" />
              Admin Operations
            </div>
            <h1 className="mt-3 text-3xl font-semibold tracking-normal text-white md:text-4xl">市场数据源运维</h1>
            <p className="mt-3 max-w-4xl text-sm leading-6 text-white/54">
              {isLoading
                ? '正在读取市场数据源运维快照'
                : `生成 ${formatDate(response?.generatedAt)} · 窗口 ${response?.window?.key || '24h'} · 只读快照`}
            </p>
          </div>
          <ReadOnlyBadges response={response} />
        </div>
        {error ? <ApiErrorAlert error={error} className="mt-5" /> : null}
        <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          {summaryTiles.length ? summaryTiles.map((tile) => (
            <SummaryTile key={tile.label} label={tile.label} value={tile.value} tone={tile.tone} />
          )) : (
            <>
              <SummaryTile label="Provider" value="--" />
              <SummaryTile label="Live" value="--" />
              <SummaryTile label="Fallback" value="--" />
              <SummaryTile label="Events" value="--" />
            </>
          )}
        </div>
      </GlassCard>

      <div className="mt-5 grid shrink-0 grid-cols-1 gap-5 xl:grid-cols-12">
        <div className="min-w-0 xl:col-span-8">
          <ProviderOperationsPanel items={response?.items || []} />
        </div>
        <div className="min-w-0 space-y-5 xl:col-span-4">
          <GlassCard as="section" className="p-4 md:p-5">
            <div className="flex items-start gap-3">
              <LockKeyhole className="mt-1 h-4 w-4 text-emerald-200" aria-hidden="true" />
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">Guardrail</p>
                <h2 className="mt-1 text-base font-semibold text-white">只读边界</h2>
                <p className="mt-2 text-sm leading-6 text-white/50">
                  前端只读取现有运维快照，不触发数据源请求、不改变缓存、不改变 provider 排序。
                </p>
              </div>
            </div>
          </GlassCard>
          <CacheStatesPanel cacheStates={response?.cacheStates || []} />
        </div>
      </div>

      <div className="mt-5 grid shrink-0 grid-cols-1 gap-5 xl:grid-cols-12">
        <div className="min-w-0 xl:col-span-7">
          <EventRollupsPanel eventRollups={response?.eventRollups || []} />
        </div>
        {response ? (
          <div className="min-w-0 xl:col-span-5">
            <LimitationsPanel response={response} />
          </div>
        ) : (
          <GlassCard as="section" className="p-5 xl:col-span-5">
            <div className="flex items-center gap-2 text-sm text-white/50">
              <Activity className="h-4 w-4" aria-hidden="true" />
              等待运维快照
            </div>
          </GlassCard>
        )}
      </div>
      <span className="sr-only">{language === 'zh' ? '市场数据源运维只读页面' : 'Market provider operations read-only page'}</span>
    </div>
  );
};

export default MarketProviderOperationsPage;
