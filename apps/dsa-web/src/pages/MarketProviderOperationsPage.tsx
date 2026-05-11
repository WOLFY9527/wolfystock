import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Activity, ExternalLink, ServerCog } from 'lucide-react';
import {
  marketProviderOperationsApi,
  type AdminLogDrillThrough,
  type MarketProviderCacheState,
  type MarketProviderEventRollup,
  type MarketProviderOperationItem,
  type MarketProviderOperationsResponse,
  type MarketProviderOperationsSummary,
} from '../api/marketProviderOperations';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { ApiErrorAlert } from '../components/common';
import { DataFreshnessBadge } from '../components/market-overview/marketOverviewPrimitives';
import {
  TerminalButton,
  TerminalChip,
  TerminalDenseList,
  TerminalDenseTable,
  TerminalDisclosure,
  TerminalEmptyState,
  TerminalGrid,
  TerminalMetric,
  TerminalNestedBlock,
  TerminalNotice,
  TerminalPageShell,
  TerminalPanel,
  TerminalSectionHeader,
} from '../components/terminal';
import type { MarketProviderHealthStatus } from '../api/marketOverview';
import { useI18n } from '../contexts/UiLanguageContext';
import { cn } from '../utils/cn';
import { formatDateTime, formatNumber, formatPercent } from '../utils/format';

type StatusTone = 'live' | 'cache' | 'stale' | 'fallback' | 'partial' | 'unavailable' | 'error' | 'refreshing';

const STATUS_SET = new Set<StatusTone>(['live', 'cache', 'stale', 'fallback', 'partial', 'unavailable', 'error', 'refreshing']);
const SENSITIVE_FRAGMENT_PATTERN = /((?:token|secret|cookie|session|password|authorization|bearer|api[_-]?key|set-cookie|x-api-key)\s*[:=]?\s*)([^,\s]+)/gi;
const SENSITIVE_KEYWORD_PATTERN = /(token|secret|cookie|session|password|authorization|bearer|api[_-]?key|set-cookie|x-api-key)/i;
const SUMMARY_DEFAULTS: MarketProviderOperationsSummary = {
  totalItems: 0,
  liveCount: 0,
  cacheCount: 0,
  staleCount: 0,
  fallbackCount: 0,
  partialCount: 0,
  unavailableCount: 0,
  errorCount: 0,
  refreshingCount: 0,
  eventCount: 0,
  failureCount: 0,
  fallbackEventCount: 0,
  staleEventCount: 0,
  slowEventCount: 0,
};

function safeFiniteNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function safeCount(value: unknown): number {
  return safeFiniteNumber(value) ?? 0;
}

function normalizeSummary(summary?: Partial<MarketProviderOperationsSummary> | null): MarketProviderOperationsSummary {
  return {
    totalItems: safeCount(summary?.totalItems),
    liveCount: safeCount(summary?.liveCount),
    cacheCount: safeCount(summary?.cacheCount),
    staleCount: safeCount(summary?.staleCount),
    fallbackCount: safeCount(summary?.fallbackCount),
    partialCount: safeCount(summary?.partialCount),
    unavailableCount: safeCount(summary?.unavailableCount),
    errorCount: safeCount(summary?.errorCount),
    refreshingCount: safeCount(summary?.refreshingCount),
    eventCount: safeCount(summary?.eventCount),
    failureCount: safeCount(summary?.failureCount),
    fallbackEventCount: safeCount(summary?.fallbackEventCount),
    staleEventCount: safeCount(summary?.staleEventCount),
    slowEventCount: safeCount(summary?.slowEventCount),
  };
}

function normalizeStatus(value: unknown): StatusTone {
  const normalized = String(value || '').trim().toLowerCase().replace(/[-\s]+/g, '_');
  return STATUS_SET.has(normalized as StatusTone) ? normalized as StatusTone : 'unavailable';
}

function formatDisplayDate(value?: string | null, fallback = '暂无数据'): string {
  const formatted = formatDateTime(value);
  return formatted === '--' ? fallback : formatted;
}

function formatLatency(value?: number | null): string {
  const numeric = safeFiniteNumber(value);
  return numeric == null ? '—' : `${formatNumber(numeric, 0)} ms`;
}

function formatAgeMinutes(value?: number | null, fallback = '待统计'): string {
  const numeric = safeFiniteNumber(value);
  return numeric == null ? fallback : `${formatNumber(numeric, 0)} 分钟`;
}

function formatCountLabel(value?: unknown, fallback = '待统计'): string {
  const numeric = safeFiniteNumber(value);
  return numeric == null ? fallback : formatNumber(numeric, 0);
}

function safePercent(value?: unknown, fallback = '待统计'): string {
  const numeric = safeFiniteNumber(value);
  return numeric == null ? fallback : formatPercent(numeric, { mode: 'ratio' });
}

function safeRatio(numerator?: unknown, denominator?: unknown, fallback = '待统计'): string {
  const top = safeFiniteNumber(numerator);
  const bottom = safeFiniteNumber(denominator);
  if (top == null || bottom == null || bottom <= 0) return fallback;
  return formatPercent(top / bottom, { mode: 'ratio' });
}

function providerLabel(item: Pick<MarketProviderOperationItem, 'provider' | 'sourceLabel'>): string {
  return item.sourceLabel || item.provider || 'unknown';
}

function providerKey(item: Pick<MarketProviderOperationItem, 'provider' | 'cacheKey' | 'endpoint'>): string {
  return `${item.provider}::${item.cacheKey}::${item.endpoint}`;
}

function sanitizeOperatorText(value?: string | number | null, fallback = '暂无数据'): string {
  if (value === null || value === undefined || value === '') return fallback;
  const text = String(value).trim();
  if (!text) return fallback;
  const redacted = text.replace(SENSITIVE_FRAGMENT_PATTERN, '$1[已脱敏]');
  if (SENSITIVE_KEYWORD_PATTERN.test(redacted)) return '已脱敏';
  return redacted.slice(0, 120);
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
  if (drill.eventId) query.set('eventId', drill.eventId);
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

function statusChipVariant(status: StatusTone): 'neutral' | 'success' | 'caution' | 'danger' | 'info' {
  if (status === 'live') return 'success';
  if (status === 'cache' || status === 'refreshing' || status === 'partial') return 'info';
  if (status === 'stale' || status === 'fallback') return 'caution';
  if (status === 'error') return 'danger';
  return 'neutral';
}

function statusLabel(status: StatusTone): string {
  return {
    live: '实时',
    cache: '缓存',
    stale: '过期',
    fallback: '备用',
    partial: '部分数据',
    unavailable: '待统计',
    error: '异常',
    refreshing: '刷新中',
  }[status];
}

function circuitLabel(item: MarketProviderOperationItem): string {
  if (item.errorSummary) return '异常';
  if (item.isFallback || item.fallbackUsed) return '备用';
  if (item.isStale) return '过期';
  if (item.isRefreshing) return '刷新中';
  return '正常';
}

function circuitVariant(item: MarketProviderOperationItem): 'neutral' | 'success' | 'caution' | 'danger' | 'info' {
  if (item.errorSummary) return 'danger';
  if (item.isFallback || item.fallbackUsed || item.isStale) return 'caution';
  if (item.isRefreshing) return 'info';
  return 'success';
}

function lastFailureLabel(item: MarketProviderOperationItem): string {
  if (item.errorSummary) return sanitizeOperatorText(item.errorSummary);
  if (item.warning) return sanitizeOperatorText(item.warning);
  return '暂无数据';
}

function providerRiskLabel(item: MarketProviderOperationItem): string {
  if (item.errorSummary) return '最近有异常，先核对失败原因与 Admin Logs。';
  if (item.isFallback || item.fallbackUsed) return '当前存在备用路径，需确认主数据源恢复时点。';
  if (item.isStale) return '缓存已滞后，需核对更新时间与快照年龄。';
  if (item.isRefreshing) return '数据正在刷新，注意避免把短时刷新误判为故障。';
  return '当前快照稳定，维持只读观察。';
}

function providerNextAction(item: MarketProviderOperationItem): string {
  if (item.errorSummary) return '进入 Admin Logs 追踪最近异常，再确认缓存快照是否可回退。';
  if (item.isFallback || item.fallbackUsed) return '先确认主 provider 是否恢复，再决定是否继续接受备用快照。';
  if (item.isStale) return '核对更新时间、TTL 与最后可用时间，确认是否属于预期滞后。';
  if (item.isRefreshing) return '等待刷新结束后再判断是否需要进入异常追踪。';
  return '保持只读监控，优先关注新的失败或熔断事件。';
}

function selectPreferredProvider(items: MarketProviderOperationItem[]): MarketProviderOperationItem | null {
  if (!items.length) return null;
  return [...items].sort((left, right) => {
    const leftScore = Number(Boolean(left.errorSummary)) * 10
      + Number(Boolean(left.isFallback || left.fallbackUsed)) * 6
      + Number(Boolean(left.isStale)) * 4
      + Number(Boolean(left.isRefreshing)) * 2;
    const rightScore = Number(Boolean(right.errorSummary)) * 10
      + Number(Boolean(right.isFallback || right.fallbackUsed)) * 6
      + Number(Boolean(right.isStale)) * 4
      + Number(Boolean(right.isRefreshing)) * 2;
    return rightScore - leftScore;
  })[0];
}

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

const ReadOnlyBadges: React.FC<{ response?: MarketProviderOperationsResponse | null }> = ({ response }) => {
  const metadata = response?.metadata || {};
  return (
    <div className="flex flex-wrap gap-2">
      <TerminalChip variant="info">只读</TerminalChip>
      <TerminalChip variant={metadata.externalProviderCalls === false ? 'success' : 'caution'}>
        {metadata.externalProviderCalls === false ? '外部调用关闭' : '外部调用未确认'}
      </TerminalChip>
      <TerminalChip variant={metadata.cacheMutation === false ? 'success' : 'caution'}>
        {metadata.cacheMutation === false ? '缓存不变更' : '缓存变更未确认'}
      </TerminalChip>
      <TerminalChip variant="neutral">窗口 {response?.window?.key || '24h'}</TerminalChip>
    </div>
  );
};

const ProviderOperationsTable: React.FC<{
  items: MarketProviderOperationItem[];
  selectedKey: string | null;
  onSelect: (key: string) => void;
}> = ({ items, selectedKey, onSelect }) => (
  <TerminalPanel as="section" className="col-span-12 xl:col-span-8">
    <TerminalSectionHeader
      eyebrow="数据源健康"
      title="数据源运维"
      action={<TerminalChip variant="neutral">只读快照</TerminalChip>}
    />
    <div className="mt-4">
      {items.length === 0 ? (
        <TerminalEmptyState title="暂无数据源运维条目">缺失快照时只显示只读边界，不推断 provider 运行状态。</TerminalEmptyState>
      ) : (
        <TerminalDenseTable>
          <table className="min-w-full table-fixed">
            <thead className="bg-black/20 text-[10px] uppercase tracking-widest text-white/35">
              <tr className="border-b border-white/5 text-left">
                <th className="px-3 py-3 font-medium">数据源</th>
                <th className="px-3 py-3 font-medium">状态</th>
                <th className="px-3 py-3 font-medium">新鲜度</th>
                <th className="px-3 py-3 font-medium">熔断</th>
                <th className="px-3 py-3 font-medium">最近异常</th>
                <th className="px-3 py-3 font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const key = providerKey(item);
                const selected = key === selectedKey;
                const status = normalizeStatus(item.status);
                return (
                  <tr key={key} className={cn('border-b border-white/[0.04] align-top', selected ? 'bg-white/[0.03]' : 'bg-transparent')}>
                    <td className="px-3 py-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-white">{providerLabel(item)}</p>
                        <p className="mt-1 truncate font-mono text-[11px] text-white/42">{item.provider} · {item.domain}</p>
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex flex-wrap gap-1.5">
                        <TerminalChip variant={statusChipVariant(status)}>{statusLabel(status)}</TerminalChip>
                        {item.isRefreshing ? <TerminalChip variant="info">刷新中</TerminalChip> : null}
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <div className="space-y-1">
                        <DataFreshnessBadge status={status as MarketProviderHealthStatus} />
                        <p className="text-[11px] text-white/42">{formatDisplayDate(item.updatedAt, '待统计')}</p>
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <TerminalChip variant={circuitVariant(item)}>{circuitLabel(item)}</TerminalChip>
                    </td>
                    <td className="px-3 py-3">
                      <p className="line-clamp-2 text-[11px] leading-5 text-white/60">{lastFailureLabel(item)}</p>
                    </td>
                    <td className="px-3 py-3">
                      <TerminalButton
                        variant={selected ? 'secondary' : 'compact'}
                        className="w-full sm:w-auto"
                        onClick={() => onSelect(key)}
                      >
                        {selected ? '当前已聚焦' : '查看诊断'}
                      </TerminalButton>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </TerminalDenseTable>
      )}
    </div>
  </TerminalPanel>
);

const ProviderDetailsPanel: React.FC<{ item: MarketProviderOperationItem | null }> = ({ item }) => (
  <TerminalPanel as="section" className="col-span-12 xl:col-span-4">
    <TerminalSectionHeader eyebrow="熔断状态" title={item ? providerLabel(item) : '待统计'} />
    {item ? (
      <>
        <div className="mt-4 grid grid-cols-2 gap-3">
          <TerminalMetric label="状态" value={<DataFreshnessBadge status={normalizeStatus(item.status) as MarketProviderHealthStatus} />} valueClassName="text-sm font-sans" />
          <TerminalMetric label="缓存" value={item.cacheKey || '待统计'} valueClassName="truncate text-xs font-semibold" />
          <TerminalMetric label="最近成功" value={formatAgeMinutes(item.lastKnownGoodAgeMinutes)} valueClassName="text-sm" />
          <TerminalMetric label="最近异常" value={lastFailureLabel(item)} valueClassName="truncate text-xs font-semibold" />
        </div>
        <TerminalNotice variant={item.errorSummary ? 'danger' : item.isFallback || item.fallbackUsed || item.isStale ? 'caution' : 'info'} className="mt-4">
          {providerRiskLabel(item)}
        </TerminalNotice>
        <div className="mt-4 grid gap-3">
          <TerminalMetric label="下一步" value={providerNextAction(item)} valueClassName="text-xs font-sans leading-5" />
          <TerminalMetric label="延迟" value={formatLatency(item.latencyMs)} valueClassName="text-sm" />
        </div>
        <TerminalDenseList className="mt-4">
          <TerminalNestedBlock className="px-3 py-2">
            <p className="text-[10px] uppercase tracking-widest text-white/35">provider ID</p>
            <p className="mt-1 font-mono text-[11px] text-white/65">{item.provider}</p>
          </TerminalNestedBlock>
          <TerminalNestedBlock className="px-3 py-2">
            <p className="text-[10px] uppercase tracking-widest text-white/35">API</p>
            <p className="mt-1 font-mono text-[11px] text-white/65">{item.endpoint}</p>
          </TerminalNestedBlock>
          <DrillLink drill={item.adminLogDrillThrough} />
        </TerminalDenseList>
      </>
    ) : (
      <div className="mt-4">
        <TerminalEmptyState title="待统计">暂无可聚焦的数据源，保留只读边界与诊断入口。</TerminalEmptyState>
      </div>
    )}
  </TerminalPanel>
);

const CacheStatesPanel: React.FC<{ cacheStates: MarketProviderCacheState[] }> = ({ cacheStates }) => (
  <TerminalPanel as="section" className="col-span-12 xl:col-span-5">
    <TerminalSectionHeader eyebrow="缓存状态" title="缓存状态" />
    <div className="mt-4">
      {cacheStates.length === 0 ? (
        <TerminalEmptyState title="暂无缓存状态">没有可用快照时，不推断 TTL 或刷新表现。</TerminalEmptyState>
      ) : (
        <TerminalDenseList>
          {cacheStates.map((state) => {
            const status = normalizeStatus(state.status);
            return (
              <TerminalNestedBlock key={state.cacheKey}>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate font-mono text-[11px] text-white/72">{state.cacheKey}</p>
                    <p className="mt-1 text-[11px] text-white/42">
                      TTL {formatCountLabel(state.ttlSeconds, '待统计')}s · 读取 {formatDisplayDate(state.fetchedAt, '待统计')}
                    </p>
                  </div>
                  <TerminalChip variant={statusChipVariant(status)}>{status}</TerminalChip>
                </div>
                {state.lastError ? (
                  <p className="mt-2 text-[11px] leading-5 text-white/58">{sanitizeOperatorText(state.lastError)}</p>
                ) : null}
              </TerminalNestedBlock>
            );
          })}
        </TerminalDenseList>
      )}
    </div>
  </TerminalPanel>
);

const EventRollupsPanel: React.FC<{ eventRollups: MarketProviderEventRollup[] }> = ({ eventRollups }) => (
  <TerminalPanel as="section" className="col-span-12 xl:col-span-7">
    <TerminalSectionHeader eyebrow="最近异常" title="最近异常" />
    <div className="mt-4">
      {eventRollups.length === 0 ? (
        <TerminalEmptyState title="窗口内暂无异常">异常回卷为空时，不把缺失数据误报成健康或失败。</TerminalEmptyState>
      ) : (
        <TerminalDenseList>
          {eventRollups.map((rollup) => {
            const failureRateLabel = safePercent(rollup.failureRate, safeRatio(rollup.failureCount, rollup.eventCount));
            const primaryReason = rollup.topReasons.length ? sanitizeOperatorText(rollup.topReasons[0]) : '暂无数据';
            return (
              <TerminalNestedBlock key={`${rollup.provider}-${rollup.endpoint || rollup.card || rollup.latestLogEventId}`}>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-white">{rollup.provider}</p>
                    <p className="mt-1 text-[11px] text-white/42">{rollup.card || rollup.category || 'market provider'}</p>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    <TerminalChip variant={rollup.failureCount > 0 ? 'danger' : 'neutral'}>失败 {formatCountLabel(rollup.failureCount, '0')}</TerminalChip>
                    <TerminalChip variant={rollup.fallbackCount > 0 ? 'caution' : 'neutral'}>失败率 {failureRateLabel}</TerminalChip>
                  </div>
                </div>
                <p className="mt-2 text-[11px] leading-5 text-white/58">{primaryReason}</p>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-white/42">
                  <span>{formatDisplayDate(rollup.latestStartedAt, '待统计')}</span>
                  <DrillLink drill={rollup.adminLogDrillThrough} />
                </div>
              </TerminalNestedBlock>
            );
          })}
        </TerminalDenseList>
      )}
    </div>
  </TerminalPanel>
);

const DiagnosticsPanel: React.FC<{
  response: MarketProviderOperationsResponse;
  selectedItem: MarketProviderOperationItem | null;
}> = ({ response, selectedItem }) => (
  <TerminalPanel as="section" className="col-span-12">
    <TerminalSectionHeader
      eyebrow="诊断详情"
      title="诊断详情"
      action={response.limitations.length ? <TerminalChip variant="caution">{response.limitations.length} 条限制</TerminalChip> : <TerminalChip variant="neutral">暂无限制</TerminalChip>}
    />
    <div className="mt-4 flex flex-wrap gap-2">
      {response.limitations.length ? response.limitations.map((limitation) => (
        <TerminalChip key={limitation} variant="caution">{limitationLabel(limitation)}</TerminalChip>
      )) : <TerminalChip variant="neutral">暂无限制</TerminalChip>}
    </div>
    <TerminalDisclosure
      title="诊断详情"
      summary="原始限制代码、只读摘要、追踪标识默认折叠"
      className="mt-4"
      data-testid="market-provider-diagnostics-disclosure"
    >
      <div className="grid gap-4 xl:grid-cols-3">
        <TerminalNestedBlock>
          <p className="text-[10px] uppercase tracking-widest text-white/35">限制代码</p>
          <ul className="mt-2 space-y-1 text-[11px] leading-5 text-white/58">
            {response.limitations.length ? response.limitations.map((limitation) => (
              <li key={limitation} className="break-words font-mono">{limitation}</li>
            )) : <li className="text-white/40">暂无原始限制代码</li>}
          </ul>
        </TerminalNestedBlock>
        <TerminalNestedBlock className="xl:col-span-2">
          <p className="text-[10px] uppercase tracking-widest text-white/35">JSON</p>
          <pre className="mt-2 max-h-72 overflow-y-auto no-scrollbar whitespace-pre-wrap break-words text-[11px] leading-5 text-white/58">
            {JSON.stringify({
              summary: safeMetadataSummary(response),
              selectedProvider: selectedItem ? {
                provider: selectedItem.provider,
                cacheKey: selectedItem.cacheKey,
                endpoint: selectedItem.endpoint,
                status: normalizeStatus(selectedItem.status),
                latestLogEventId: selectedItem.adminLogDrillThrough?.eventId || null,
              } : null,
            }, null, 2)}
          </pre>
        </TerminalNestedBlock>
      </div>
    </TerminalDisclosure>
  </TerminalPanel>
);

const LoadingOperationsState: React.FC = () => (
  <TerminalPanel as="section" role="status" aria-label="正在读取市场数据源运维快照">
    <div className="flex items-center gap-3">
      <Activity className="h-4 w-4 animate-pulse text-cyan-200" aria-hidden="true" />
      <div>
        <p className="text-sm font-semibold text-white">正在读取只读运维快照</p>
        <p className="mt-1 text-xs text-white/46">不会触发外部 provider 调用，也不会变更缓存。</p>
      </div>
    </div>
    <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
      {[0, 1, 2].map((index) => (
        <TerminalNestedBlock key={index} className="h-24" aria-hidden="true" />
      ))}
    </div>
  </TerminalPanel>
);

const EmptyErrorState: React.FC = () => (
  <TerminalPanel as="section">
    <div className="flex items-center gap-2 text-sm text-white/50">
      <Activity className="h-4 w-4" aria-hidden="true" />
      运维快照暂不可用
    </div>
  </TerminalPanel>
);

const MarketProviderOperationsPage: React.FC = () => {
  const { language } = useI18n();
  const [response, setResponse] = useState<MarketProviderOperationsResponse | null>(null);
  const [selectedProviderKey, setSelectedProviderKey] = useState<string | null>(null);
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

  const items = response?.items || [];
  const cacheStates = response?.cacheStates || [];
  const eventRollups = response?.eventRollups || [];
  const summary = useMemo(() => normalizeSummary(response?.summary || SUMMARY_DEFAULTS), [response?.summary]);
  const degradedCount = summary.fallbackCount + summary.partialCount + summary.unavailableCount + summary.errorCount + summary.failureCount;
  const preferredProvider = useMemo(() => selectPreferredProvider(items), [items]);

  useEffect(() => {
    if (!items.length) {
      if (selectedProviderKey !== null) setSelectedProviderKey(null);
      return;
    }
    if (!selectedProviderKey || !items.some((item) => providerKey(item) === selectedProviderKey)) {
      setSelectedProviderKey(providerKey(preferredProvider || items[0]));
    }
  }, [items, preferredProvider, selectedProviderKey]);

  const selectedItem = useMemo(
    () => items.find((item) => providerKey(item) === selectedProviderKey) || preferredProvider || null,
    [items, preferredProvider, selectedProviderKey],
  );

  const topException = useMemo(() => {
    const withReason = eventRollups.find((rollup) => rollup.topReasons.length) || null;
    if (withReason) return sanitizeOperatorText(withReason.topReasons[0]);
    const withItemError = items.find((item) => item.errorSummary || item.warning) || null;
    return withItemError ? lastFailureLabel(withItemError) : '暂无数据';
  }, [eventRollups, items]);

  const operatorMetrics = useMemo(() => {
    const totalItems = summary.totalItems || items.length;
    const healthValue = totalItems > 0 ? `${formatNumber(summary.liveCount, 0)}/${formatNumber(totalItems, 0)} 实时` : '暂无数据';
    const circuitValue = totalItems > 0 ? (degradedCount > 0 ? `${formatNumber(degradedCount, 0)} 降级` : '正常') : '待统计';
    const cacheValue = cacheStates.length > 0
      ? cacheStates.some((state) => state.isRefreshing)
        ? '刷新中'
        : cacheStates.some((state) => state.isFresh === false)
          ? `${formatNumber(cacheStates.filter((state) => state.isFresh === false).length, 0)} 过期`
          : `${formatNumber(cacheStates.length, 0)} 正常`
      : '待统计';

    return [
      { label: '数据源健康', value: healthValue, subvalue: totalItems > 0 ? `共 ${formatNumber(totalItems, 0)} 个数据源` : '暂无 provider 快照' },
      { label: '熔断状态', value: circuitValue, subvalue: degradedCount > 0 ? '优先核对降级与失败路径' : '当前未见降级聚合' },
      { label: '失败率', value: safeRatio(summary.failureCount, summary.eventCount), subvalue: summary.eventCount > 0 ? `事件 ${formatNumber(summary.eventCount, 0)}` : '待统计' },
      { label: '缓存状态', value: cacheValue, subvalue: cacheStates.length > 0 ? `快照 ${formatNumber(cacheStates.length, 0)}` : '暂无缓存快照' },
      { label: '最近异常', value: topException, subvalue: eventRollups.length > 0 ? '保留异常可见性，但不暴露敏感内容' : '窗口内暂无异常' },
    ];
  }, [cacheStates, degradedCount, eventRollups.length, items.length, summary, topException]);

  return (
    <div data-testid="market-provider-operations-page" className="market-provider-operations-page flex min-h-0 w-full flex-1 flex-col overflow-y-auto no-scrollbar bg-[#050505] px-4 py-5 text-white md:px-6 xl:px-8">
      <TerminalPageShell>
        <TerminalPanel as="section" className="relative overflow-hidden">
          <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-300/50 to-transparent" />
          <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2 text-[10px] font-bold uppercase tracking-[0.22em] text-cyan-200/80">
                <ServerCog className="h-4 w-4" aria-hidden="true" />
                数据源就绪台
              </div>
              <h1 className="mt-3 text-3xl font-semibold tracking-normal text-white md:text-4xl">数据源运维</h1>
              <p className="mt-3 max-w-4xl text-sm leading-6 text-white/54">
                {isLoading
                  ? '正在读取市场数据源运维快照'
                  : `先看健康、熔断、失败率与缓存，再下钻诊断详情。生成 ${formatDisplayDate(response?.generatedAt, '待统计')} · 窗口 ${response?.window?.key || '24h'} · 只读快照`}
              </p>
            </div>
            <ReadOnlyBadges response={response} />
          </div>
          {error ? <ApiErrorAlert error={error} className="mt-5" /> : null}
        </TerminalPanel>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-5">
          {operatorMetrics.map((metric) => (
            <TerminalMetric
              key={metric.label}
              label={metric.label}
              value={metric.value}
              subvalue={metric.subvalue}
              valueClassName="text-sm leading-5 md:text-base"
            />
          ))}
        </div>

        <TerminalNotice variant="info">
          前端只读取现有运维快照，不触发数据源请求、不改变缓存、不改变 provider 排序，也不隐藏真实失败。
        </TerminalNotice>

        {isLoading && !response && !error ? <LoadingOperationsState /> : null}
        {error && !response && !isLoading ? <EmptyErrorState /> : null}
        {!isLoading && (response || !error) ? (
          <>
            <TerminalGrid>
              <ProviderOperationsTable items={items} selectedKey={selectedProviderKey} onSelect={setSelectedProviderKey} />
              <ProviderDetailsPanel item={selectedItem} />
              <EventRollupsPanel eventRollups={eventRollups} />
              <CacheStatesPanel cacheStates={cacheStates} />
              {response ? <DiagnosticsPanel response={response} selectedItem={selectedItem} /> : null}
            </TerminalGrid>
          </>
        ) : null}
      </TerminalPageShell>
      <span className="sr-only">{language === 'zh' ? '市场数据源运维只读页面' : 'Market provider operations read-only page'}</span>
    </div>
  );
};

export default MarketProviderOperationsPage;
