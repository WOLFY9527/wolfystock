import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Activity, ExternalLink } from 'lucide-react';
import { marketApi, type MarketDataReadinessCheck, type MarketDataReadinessResponse } from '../api/market';
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
  TerminalPageHeading,
  TerminalPageShell,
  TerminalPanel,
  TerminalSectionHeader,
} from '../components/terminal';
import type { MarketProviderHealthStatus } from '../api/marketOverview';
import { useI18n } from '../contexts/UiLanguageContext';
import { cn } from '../utils/cn';
import { formatDateTime, formatNumber, formatPercent } from '../utils/format';

type StatusTone = 'live' | 'cache' | 'stale' | 'fallback' | 'partial' | 'unavailable' | 'error' | 'refreshing';
type TickflowProjection = {
  provider?: unknown;
  market?: unknown;
  diagnosticTarget?: unknown;
  status?: unknown;
  credentialState?: unknown;
  credentialConfigured?: unknown;
  reachabilityState?: unknown;
  tickflowReachable?: unknown;
  breadthEntitlementState?: unknown;
  breadthEntitlementUsable?: unknown;
  reasonCode?: unknown;
  observedSource?: unknown;
  sourceType?: unknown;
  summary?: unknown;
};

const STATUS_SET = new Set<StatusTone>(['live', 'cache', 'stale', 'fallback', 'partial', 'unavailable', 'error', 'refreshing']);
const SENSITIVE_FRAGMENT_PATTERN = /((?:token|secret|cookie|session|password|authorization|bearer|api[_-]?key|set-cookie|x-api-key)\s*[:=]?\s*)([^,\s]+)/gi;
const SENSITIVE_KEYWORD_PATTERN = /(token|secret|cookie|session|password|authorization|bearer|api[_-]?key|set-cookie|x-api-key)/i;
const EMPTY_PROVIDER_ITEMS: MarketProviderOperationItem[] = [];
const EMPTY_PROVIDER_CACHE_STATES: MarketProviderCacheState[] = [];
const EMPTY_PROVIDER_EVENT_ROLLUPS: MarketProviderEventRollup[] = [];
const EMPTY_READINESS_CHECKS: MarketDataReadinessCheck[] = [];
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function readTickflowProjection(metadata: Record<string, unknown> | null | undefined): TickflowProjection | null {
  const providerDiagnostics = isRecord(metadata?.providerDiagnostics) ? metadata.providerDiagnostics : null;
  const projection = isRecord(providerDiagnostics?.tickflowCnBreadth) ? providerDiagnostics.tickflowCnBreadth : null;
  return projection as TickflowProjection | null;
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

function readinessStatusLabel(status: string): string {
  return {
    ready: 'ready',
    partial: 'partial',
    missing: 'missing',
    misconfigured: 'misconfigured',
  }[status] || status;
}

function readinessStatusVariant(status: string): 'neutral' | 'success' | 'caution' | 'danger' | 'info' {
  if (status === 'ready') return 'success';
  if (status === 'partial') return 'info';
  if (status === 'missing') return 'caution';
  if (status === 'misconfigured') return 'danger';
  return 'neutral';
}

function readinessSeverityLabel(severity: string): string {
  return {
    error: 'error',
    warning: 'warning',
    info: 'info',
  }[severity] || severity;
}

function readinessSeverityVariant(severity: string): 'neutral' | 'success' | 'caution' | 'danger' | 'info' {
  if (severity === 'error') return 'danger';
  if (severity === 'warning') return 'caution';
  if (severity === 'info') return 'info';
  return 'neutral';
}

function surfaceLabel(surface: string): string {
  return {
    market_overview: 'Market Overview',
    liquidity_monitor: 'Liquidity Monitor',
    rotation_radar: 'Rotation Radar',
    stock_history: 'US parquet history',
  }[surface] || surface.replace(/_/g, ' ');
}

function summarizeReadinessFacts(check: MarketDataReadinessCheck): string[] {
  if (typeof check.secretConfigured === 'boolean') {
    return [];
  }
  const details = check.details;
  if (!details || typeof details !== 'object') {
    return [];
  }

  const facts: string[] = [];
  const envKeys = Array.isArray(details.envKeys) ? details.envKeys.map((key) => String(key)).filter(Boolean) : [];
  const envKey = typeof details.envKey === 'string' ? details.envKey.trim() : '';
  const availableModules = Array.isArray(details.availableModules) ? details.availableModules.map((name) => String(name)).filter(Boolean) : [];
  const missingModules = Array.isArray(details.missingModules) ? details.missingModules.map((name) => String(name)).filter(Boolean) : [];
  const representativeSymbols = Array.isArray(details.representativeSymbols) ? details.representativeSymbols.map((symbol) => String(symbol)).filter(Boolean) : [];
  const missingSymbols = Array.isArray(details.missingSymbols) ? details.missingSymbols.map((symbol) => String(symbol)).filter(Boolean) : [];
  const existingCount = typeof details.existingCount === 'number' ? details.existingCount : null;

  if (envKeys.length) {
    facts.push(`env: ${envKeys.join(', ')}`);
  } else if (envKey) {
    facts.push(`env: ${envKey}`);
  }
  if (availableModules.length) {
    facts.push(`available: ${availableModules.join(', ')}`);
  }
  if (missingModules.length) {
    facts.push(`missing: ${missingModules.join(', ')}`);
  }
  if (representativeSymbols.length) {
    facts.push(`symbols: ${representativeSymbols.join(', ')}`);
  }
  if (missingSymbols.length) {
    facts.push(`missing symbols: ${missingSymbols.join(', ')}`);
  }
  if (existingCount != null) {
    facts.push(`existing: ${formatNumber(existingCount, 0)}`);
  }
  return facts;
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

function tickflowLabel(value: unknown): string {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'key_missing' || normalized === 'missing' || normalized === 'not_configured') return 'Key 未配置';
  if (normalized === 'key_configured' || normalized === 'configured') return 'Key 已配置';
  return 'Key 待统计';
}

function tickflowCredentialVariant(value: unknown): 'neutral' | 'success' | 'caution' | 'danger' | 'info' {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'key_configured' || normalized === 'configured') return 'success';
  if (normalized === 'key_missing' || normalized === 'missing' || normalized === 'not_configured') return 'caution';
  return 'neutral';
}

function reachabilityLabel(value: unknown): { label: string; variant: 'neutral' | 'success' | 'caution' | 'danger' | 'info' } {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'reachable') return { label: '可达', variant: 'success' };
  if (normalized === 'timeout') return { label: '超时', variant: 'caution' };
  if (normalized === 'unreachable') return { label: '不可达', variant: 'danger' };
  return { label: '待观测', variant: 'neutral' };
}

function entitlementLabel(value: unknown): { label: string; variant: 'neutral' | 'success' | 'caution' | 'danger' | 'info' } {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'usable' || normalized === 'breadth_entitlement_usable') return { label: '权限可用', variant: 'success' };
  if (normalized === 'permission_denied') return { label: '权限拒绝', variant: 'danger' };
  if (normalized === 'empty') return { label: '空响应', variant: 'caution' };
  if (normalized === 'malformed') return { label: '返回异常', variant: 'caution' };
  if (normalized === 'timeout') return { label: '超时', variant: 'caution' };
  if (normalized === 'unreachable') return { label: '不可达', variant: 'danger' };
  return { label: '权限待观测', variant: 'neutral' };
}

const TickflowEntitlementRow: React.FC<{ projection: TickflowProjection }> = ({ projection }) => {
  const keyBadge = tickflowLabel(projection.credentialState || projection.status);
  const reachability = reachabilityLabel(projection.reachabilityState);
  const entitlement = entitlementLabel(projection.breadthEntitlementState || projection.status);

  return (
    <TerminalNestedBlock className="px-3 py-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-widest text-white/35">TickFlow A股宽度</p>
          <p className="mt-1 text-sm font-semibold text-white">权限诊断</p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <TerminalChip variant={tickflowCredentialVariant(projection.credentialState || projection.status)}>{keyBadge}</TerminalChip>
          <TerminalChip variant={reachability.variant}>{reachability.label}</TerminalChip>
          <TerminalChip variant={entitlement.variant}>{entitlement.label}</TerminalChip>
        </div>
      </div>
    </TerminalNestedBlock>
  );
};

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
}> = ({ response, selectedItem }) => {
  const tickflowProjection = readTickflowProjection(response.metadata);
  return (
    <TerminalPanel as="section" className="col-span-12">
      <TerminalSectionHeader
        eyebrow="二级详情"
        title="限制与快照摘要"
        action={response.limitations.length ? <TerminalChip variant="caution">{response.limitations.length} 条限制</TerminalChip> : <TerminalChip variant="neutral">暂无限制</TerminalChip>}
      />
      {tickflowProjection ? <div className="mt-4"><TickflowEntitlementRow projection={tickflowProjection} /></div> : null}
      <div className="mt-4 flex flex-wrap gap-2">
        {response.limitations.length ? response.limitations.map((limitation) => (
          <TerminalChip key={limitation} variant="caution">{limitationLabel(limitation)}</TerminalChip>
        )) : <TerminalChip variant="neutral">暂无限制</TerminalChip>}
      </div>
      <TerminalDisclosure
        title="二级细节：限制代码、快照摘要、追踪标识"
        summary="默认折叠"
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
};

const MarketDataReadinessPanel: React.FC<{
  data: MarketDataReadinessResponse | null;
  isLoading: boolean;
  error: ParsedApiError | null;
  symbolInput: string;
  onSymbolInputChange: (value: string) => void;
  onSymbolSubmit: () => void;
}> = ({ data, isLoading, error, symbolInput, onSymbolInputChange, onSymbolSubmit }) => {
  const checks = data?.checks ?? EMPTY_READINESS_CHECKS;
  const groupedChecks = useMemo(() => {
    const order = ['error', 'warning', 'info'];
    return order
      .map((severity) => ({
        severity,
        items: checks
          .filter((check) => check.severity === severity)
          .sort((left, right) => left.status.localeCompare(right.status) || left.id.localeCompare(right.id)),
      }))
      .filter((group) => group.items.length > 0);
  }, [checks]);

  return (
    <TerminalPanel as="section" className="col-span-12">
      <TerminalSectionHeader
        eyebrow="本地只读诊断"
        title="本地行情就绪诊断"
        action={data ? <TerminalChip variant={readinessStatusVariant(data.readinessStatus)}>{readinessStatusLabel(data.readinessStatus)}</TerminalChip> : <TerminalChip variant="neutral">待读取</TerminalChip>}
      />
      <div className="mt-4 grid gap-3 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <TerminalNestedBlock className="px-3 py-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[10px] uppercase tracking-widest text-white/35">representative symbols</p>
              <p className="mt-1 text-sm font-semibold text-white">代表样本</p>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {data?.representativeSymbols?.length ? data.representativeSymbols.map((symbol) => (
                <TerminalChip key={symbol} variant="neutral">{symbol}</TerminalChip>
              )) : <TerminalChip variant="neutral">未提供</TerminalChip>}
            </div>
          </div>
          <div className="mt-3 flex flex-col gap-2 md:flex-row md:items-end">
            <label className="min-w-0 flex-1">
              <span className="mb-1.5 block text-[11px] text-white/42">代表符号</span>
              <input
                aria-label="代表符号"
                type="text"
                value={symbolInput}
                onChange={(event) => onSymbolInputChange(event.target.value)}
                placeholder="AAPL, SPY, BTC-USD"
                className="h-10 w-full rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 text-sm text-white outline-none transition placeholder:text-white/28 focus:border-[color:var(--wolfy-divider)]"
              />
            </label>
            <TerminalButton variant="secondary" className="min-h-10 md:min-w-28" onClick={onSymbolSubmit} disabled={isLoading}>
              更新样本
            </TerminalButton>
          </div>
          <p className="mt-2 text-[11px] leading-5 text-white/42">只发送可选 symbol query 到 `/api/v1/market/data-readiness`，不触发 provider runtime，也不读取 secret 值。</p>
        </TerminalNestedBlock>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <TerminalMetric label="diagnosticOnly" value={String(data?.diagnosticOnly ?? true)} valueClassName="text-sm" />
          <TerminalMetric label="providerRuntimeCalled" value={String(data?.providerRuntimeCalled ?? false)} valueClassName="text-sm" />
          <TerminalMetric label="networkCallsEnabled" value={String(data?.networkCallsEnabled ?? false)} valueClassName="text-sm" />
        </div>
      </div>

      <TerminalNotice variant="info" className="mt-4">
        这个面板只解释本地 readiness 与缺口来源，不改写 Market Overview、Liquidity Monitor 或 Rotation Radar 的既有结论。
      </TerminalNotice>

      {error ? <ApiErrorAlert error={error} className="mt-4" /> : null}

      {isLoading && !data ? (
        <div className="mt-4">
          <TerminalEmptyState title="正在读取 readiness">保持只读；不会触发外部数据源调用。</TerminalEmptyState>
        </div>
      ) : null}

      {!isLoading && !error ? (
        <div className="mt-4 space-y-4">
          {!groupedChecks.length ? (
            <TerminalEmptyState title="暂无 readiness 检查项">接口未返回检查项时，不前端推断环境健康度。</TerminalEmptyState>
          ) : groupedChecks.map((group) => (
            <div key={group.severity}>
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <TerminalChip variant={readinessSeverityVariant(group.severity)}>{readinessSeverityLabel(group.severity)}</TerminalChip>
                <span className="text-[11px] text-white/42">{formatNumber(group.items.length, 0)} checks</span>
              </div>
              <TerminalDenseList>
                {group.items.map((check) => {
                  const facts = summarizeReadinessFacts(check);
                  return (
                    <TerminalNestedBlock key={check.id} className="px-3 py-2.5">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="font-mono text-[11px] text-white/48">{check.id}</p>
                          <p className="mt-1 text-sm font-semibold text-white">{check.userFacingMessage}</p>
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          <TerminalChip variant={readinessStatusVariant(check.status)}>{readinessStatusLabel(check.status)}</TerminalChip>
                          {typeof check.secretConfigured === 'boolean' ? (
                            <TerminalChip variant={check.secretConfigured ? 'success' : 'caution'}>
                              {check.secretConfigured ? '已配置' : '未配置'}
                            </TerminalChip>
                          ) : null}
                        </div>
                      </div>
                      {check.remediationHint ? <p className="mt-2 text-[11px] leading-5 text-white/62">{check.remediationHint}</p> : null}
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {check.affectsSurfaces.map((surface) => (
                          <TerminalChip key={`${check.id}-${surface}`} variant="neutral">{surfaceLabel(surface)}</TerminalChip>
                        ))}
                      </div>
                      {facts.length ? <p className="mt-2 font-mono text-[11px] leading-5 text-white/42">{facts.join(' · ')}</p> : null}
                    </TerminalNestedBlock>
                  );
                })}
              </TerminalDenseList>
            </div>
          ))}
        </div>
      ) : null}
    </TerminalPanel>
  );
};

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
  const [readiness, setReadiness] = useState<MarketDataReadinessResponse | null>(null);
  const [selectedProviderKey, setSelectedProviderKey] = useState<string | null>(null);
  const [readinessSymbolsInput, setReadinessSymbolsInput] = useState('');
  const [submittedReadinessSymbols, setSubmittedReadinessSymbols] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isReadinessLoading, setIsReadinessLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [readinessError, setReadinessError] = useState<ParsedApiError | null>(null);

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

  useEffect(() => {
    let cancelled = false;
    marketApi.getDataReadiness(submittedReadinessSymbols ? { symbols: submittedReadinessSymbols } : undefined)
      .then((payload) => {
        if (!cancelled) setReadiness(payload);
      })
      .catch((apiError) => {
        if (!cancelled) {
          const parsed = getParsedApiError(apiError);
          setReadinessError({ ...parsed, title: '读取本地行情 readiness 失败' });
        }
      })
      .finally(() => {
        if (!cancelled) setIsReadinessLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [submittedReadinessSymbols]);

  const submitReadinessSymbols = () => {
    setReadinessError(null);
    setIsReadinessLoading(true);
    setSubmittedReadinessSymbols(readinessSymbolsInput.trim());
  };

  const items = response?.items ?? EMPTY_PROVIDER_ITEMS;
  const cacheStates = response?.cacheStates ?? EMPTY_PROVIDER_CACHE_STATES;
  const eventRollups = response?.eventRollups ?? EMPTY_PROVIDER_EVENT_ROLLUPS;
  const summary = useMemo(() => normalizeSummary(response?.summary ?? SUMMARY_DEFAULTS), [response?.summary]);
  const degradedCount = summary.fallbackCount + summary.partialCount + summary.unavailableCount + summary.errorCount + summary.failureCount;
  const preferredProvider = useMemo(() => selectPreferredProvider(items), [items]);

  const effectiveSelectedProviderKey = useMemo(() => {
    if (!items.length) {
      return null;
    }
    if (selectedProviderKey && items.some((item) => providerKey(item) === selectedProviderKey)) {
      return selectedProviderKey;
    }
    return providerKey(preferredProvider || items[0]);
  }, [items, preferredProvider, selectedProviderKey]);

  const selectedItem = useMemo(
    () => items.find((item) => providerKey(item) === effectiveSelectedProviderKey) || preferredProvider || null,
    [effectiveSelectedProviderKey, items, preferredProvider],
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
    <div data-testid="market-provider-operations-page" className="market-provider-operations-page flex min-h-0 w-full flex-1 flex-col overflow-y-auto no-scrollbar text-white">
      <TerminalPageShell className="py-5 md:py-6">
        <TerminalPanel as="section" className="relative overflow-hidden">
          <TerminalPageHeading
            eyebrow="数据源就绪台"
            title="数据源运维"
            action={<ReadOnlyBadges response={response} />}
          />
          <p className="mt-3 max-w-4xl text-sm leading-6 text-white/54">
            {isLoading
              ? '正在读取市场数据源运维快照'
              : `先看健康、熔断、失败率与缓存，再下钻限制、快照摘要与追踪标识。生成 ${formatDisplayDate(response?.generatedAt, '待统计')} · 窗口 ${response?.window?.key || '24h'} · 只读快照`}
          </p>
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
        {!isLoading ? (
          <TerminalGrid>
            {response ? (
              <>
                <ProviderOperationsTable items={items} selectedKey={effectiveSelectedProviderKey} onSelect={setSelectedProviderKey} />
                <ProviderDetailsPanel item={selectedItem} />
                <EventRollupsPanel eventRollups={eventRollups} />
                <CacheStatesPanel cacheStates={cacheStates} />
              </>
            ) : null}
            <MarketDataReadinessPanel
              data={readiness}
              isLoading={isReadinessLoading}
              error={readinessError}
              symbolInput={readinessSymbolsInput}
              onSymbolInputChange={setReadinessSymbolsInput}
              onSymbolSubmit={submitReadinessSymbols}
            />
            {response ? <DiagnosticsPanel response={response} selectedItem={selectedItem} /> : null}
          </TerminalGrid>
        ) : null}
      </TerminalPageShell>
      <span className="sr-only">{language === 'zh' ? '市场数据源运维只读页面' : 'Market provider operations read-only page'}</span>
    </div>
  );
};

export default MarketProviderOperationsPage;
