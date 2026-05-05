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

function limitationLabel(value: string): string {
  if (value.startsWith('cache_metadata_unavailable:')) {
    const key = value.split(':').slice(1).join(':') || 'unknown';
    return `缓存元数据未覆盖 ${key}`;
  }
  if (value === 'admin_logs_no_degraded_market_events_in_window') {
    return 'Admin Logs 窗口内暂无降级事件';
  }
  return value.replace(/_/g, ' ');
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
        窗口 {response?.window?.key || '24h'}
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
      aria-label={`${drill.label}（打开筛选后的 Admin Logs）`}
      title={`${drill.label}（打开筛选后的 Admin Logs）`}
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
        <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">数据源</p>
        <h2 className="mt-1 text-lg font-semibold text-white">数据源运维矩阵</h2>
      </div>
      <Badge variant="default" className="border-white/10 bg-white/[0.04] text-white/58">只读快照</Badge>
    </div>
    {items.length === 0 ? (
      <div className="mt-4 rounded-2xl border border-white/5 bg-black/20 px-4 py-6 text-sm text-white/50">
        暂无数据源运维条目
      </div>
    ) : (
      <div className="mt-4 grid grid-cols-1 gap-3 2xl:grid-cols-2">
        {items.map((item) => {
          const status = normalizeStatus(item.status);
          return (
            <article key={`${item.cacheKey}-${item.endpoint}`} className="min-w-0 rounded-2xl border border-white/5 bg-black/20 p-3.5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-white">{providerLabel(item)}</p>
                  <p className="mt-1 truncate font-mono text-[11px] text-white/42">{item.provider} · {item.domain}</p>
                </div>
                <div className="flex shrink-0 flex-wrap justify-end gap-1.5">
                  <DataFreshnessBadge status={status as MarketProviderHealthStatus} />
                  {item.isRefreshing ? <DataFreshnessBadge status="refreshing" /> : null}
                  {item.isFallback || item.fallbackUsed ? <DataFreshnessBadge status="fallback" /> : null}
                </div>
              </div>
              {item.warning ? <p className="mt-2 text-[11px] leading-4 text-amber-200/80">{item.warning}</p> : null}
              <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-white/44 md:grid-cols-4">
                <p className="min-w-0">卡片 <span className="block truncate font-mono text-white/68">{item.card}</span></p>
                <p className="min-w-0">缓存 <span className="block truncate font-mono text-white/68">{item.cacheKey}</span></p>
                <p className="min-w-0">更新 <span className="block truncate font-mono text-white/68">{formatDate(item.updatedAt)}</span></p>
                <p className="min-w-0">延迟 <span className="block truncate font-mono text-white/68">{compactNumber(item.latencyMs, 0)} ms</span></p>
              </div>
              <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                <p className="text-[11px] text-white/42">最近可用 <span className="font-mono text-white/65">{item.lastKnownGoodAgeMinutes ?? '--'} min</span></p>
                <DrillLink drill={item.adminLogDrillThrough} />
              </div>
              <Disclosure
                summary="运维细节"
                className="mt-3"
                bodyClassName="rounded-xl border border-white/5 bg-white/[0.025] p-3"
              >
                <dl className="grid gap-2 text-[11px] leading-5 text-white/50 sm:grid-cols-2">
                  <div className="min-w-0">
                    <dt className="text-white/34">API route</dt>
                    <dd className="break-words font-mono text-white/60">{item.endpoint}</dd>
                  </div>
                  <div className="min-w-0">
                    <dt className="text-white/34">source type</dt>
                    <dd className="break-words font-mono text-white/60">{item.sourceType || '--'}</dd>
                  </div>
                  <div className="min-w-0">
                    <dt className="text-white/34">asOf</dt>
                    <dd className="break-words font-mono text-white/60">{formatDate(item.asOf)}</dd>
                  </div>
                  <div className="min-w-0">
                    <dt className="text-white/34">最近异常</dt>
                    <dd className="break-words text-rose-100/70">{item.errorSummary ? '已脱敏，仅在 Admin Logs 查看' : '--'}</dd>
                  </div>
                </dl>
              </Disclosure>
            </article>
          );
        })}
      </div>
    )}
  </GlassCard>
);

const CacheStatesPanel: React.FC<{ cacheStates: MarketProviderCacheState[] }> = ({ cacheStates }) => (
  <GlassCard as="section" className="p-4 md:p-5">
    <div className="flex items-start gap-3">
      <DatabaseZap className="mt-1 h-4 w-4 text-cyan-200" aria-hidden="true" />
      <div>
        <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">缓存</p>
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
        <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">事件</p>
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
                <p className="mt-1 text-[11px] text-white/40">{rollup.card || rollup.category || 'market provider'}</p>
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
            <Disclosure
              summary="事件细节"
              className="mt-3"
              bodyClassName="rounded-xl border border-white/5 bg-white/[0.025] p-3"
            >
              <dl className="grid gap-2 text-[11px] leading-5 text-white/50 sm:grid-cols-2">
                <div className="min-w-0">
                  <dt className="text-white/34">API route</dt>
                  <dd className="break-words font-mono text-white/60">{rollup.endpoint || '--'}</dd>
                </div>
                <div className="min-w-0">
                  <dt className="text-white/34">latest event</dt>
                  <dd className="break-words font-mono text-white/60">{rollup.latestLogEventId || '--'}</dd>
                </div>
                <div className="min-w-0 sm:col-span-2">
                  <dt className="text-white/34">top reasons</dt>
                  <dd className="break-words font-mono text-white/60">{rollup.topReasons.length ? rollup.topReasons.join(' · ') : '--'}</dd>
                </div>
              </dl>
            </Disclosure>
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
        <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">限制</p>
        <h2 className="mt-1 text-base font-semibold text-white">限制与开发者细节</h2>
      </div>
      <DrillLink drill={response.adminLogDrillThrough} />
    </div>
    <div className="mt-4 flex flex-wrap gap-2">
      {response.limitations.length ? response.limitations.map((limitation) => (
        <span
          key={limitation}
          className="inline-flex min-h-6 items-center rounded-full border border-amber-300/25 bg-amber-400/10 px-2.5 py-0.5 text-[11px] font-medium leading-5 text-amber-100"
        >
          {limitationLabel(limitation)}
        </span>
      )) : (
        <Badge variant="success" className="border-emerald-300/25 bg-emerald-400/10 text-emerald-100">暂无限制</Badge>
      )}
    </div>
    {response.limitations.length ? (
      <Disclosure
        summary="原始限制代码"
        className="mt-4"
        bodyClassName="rounded-2xl border border-white/5 bg-black/20 p-3"
      >
        <ul className="space-y-1 text-[11px] leading-5 text-white/50">
          {response.limitations.map((limitation) => (
            <li key={limitation} className="break-words font-mono">{limitation}</li>
          ))}
        </ul>
      </Disclosure>
    ) : null}
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

const LoadingOperationsState: React.FC = () => (
  <GlassCard as="section" className="mt-5 p-4 md:p-5" role="status" aria-label="正在读取市场数据源运维快照">
    <div className="flex items-center gap-3">
      <Activity className="h-4 w-4 animate-pulse text-cyan-200" aria-hidden="true" />
      <div>
        <p className="text-sm font-semibold text-white">正在读取只读运维快照</p>
        <p className="mt-1 text-xs text-white/46">不会触发外部 provider 调用，也不会变更缓存。</p>
      </div>
    </div>
    <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
      {[0, 1, 2].map((index) => (
        <div key={index} className="h-24 rounded-2xl border border-white/5 bg-black/20" />
      ))}
    </div>
  </GlassCard>
);

const EmptyErrorState: React.FC = () => (
  <GlassCard as="section" className="mt-5 p-5">
    <div className="flex items-center gap-2 text-sm text-white/50">
      <Activity className="h-4 w-4" aria-hidden="true" />
      运维快照暂不可用
    </div>
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
      { label: '数据源', value: summary.totalItems, tone: 'info' as const },
      { label: '实时', value: summary.liveCount, tone: 'good' as const },
      { label: '备用', value: summary.fallbackCount, tone: summary.fallbackCount ? 'warn' as const : 'neutral' as const },
      { label: '异常', value: summary.errorCount + summary.failureCount, tone: summary.errorCount + summary.failureCount ? 'danger' as const : 'neutral' as const },
      { label: '刷新', value: summary.refreshingCount, tone: summary.refreshingCount ? 'info' as const : 'neutral' as const },
      { label: '事件', value: summary.eventCount, tone: summary.eventCount ? 'info' as const : 'neutral' as const },
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
              运维快照
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
              <SummaryTile label="数据源" value="--" />
              <SummaryTile label="实时" value="--" />
              <SummaryTile label="备用" value="--" />
              <SummaryTile label="事件" value="--" />
            </>
          )}
        </div>
      </GlassCard>

      {isLoading && !response && !error ? <LoadingOperationsState /> : null}
      {error && !response && !isLoading ? <EmptyErrorState /> : null}
      {!isLoading && (response || !error) ? (
        <>
          <div className="mt-5 grid shrink-0 grid-cols-1 gap-5 xl:grid-cols-12">
            <div className="min-w-0 xl:col-span-8">
              <ProviderOperationsPanel items={response?.items || []} />
            </div>
            <div className="min-w-0 space-y-5 xl:col-span-4">
              <GlassCard as="section" className="p-4 md:p-5">
                <div className="flex items-start gap-3">
                  <LockKeyhole className="mt-1 h-4 w-4 text-emerald-200" aria-hidden="true" />
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">边界</p>
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
        </>
      ) : null}
      <span className="sr-only">{language === 'zh' ? '市场数据源运维只读页面' : 'Market provider operations read-only page'}</span>
    </div>
  );
};

export default MarketProviderOperationsPage;
