import type React from 'react';
import { useEffect, useState } from 'react';
import { Activity, ExternalLink } from 'lucide-react';
import { marketApi, type MarketDataReadinessCheck, type MarketDataReadinessResponse } from '../api/market';
import {
  marketProviderOperationsApi,
  type AdminLogDrillThrough,
  type MarketProviderCacheState,
  type MarketProviderEventRollup,
  type MarketProviderOperationItem,
  type ProviderOperationsMatrixResponse,
  type ProviderOperationsMatrixRow,
  type MarketProviderOperationsResponse,
  type MarketProviderOperationsSummary,
} from '../api/marketProviderOperations';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { ApiErrorAlert } from '../components/common/ApiErrorAlert';
import { Input } from '../components/common/Input';
import { DataFreshnessBadge } from '../components/market-overview/marketOverviewPrimitives';
import AdminDrillThroughStrip from '../components/admin/AdminDrillThroughStrip';
import AdminOpsL0OverviewStrip, { type AdminOpsTrustState } from '../components/admin/AdminOpsL0OverviewStrip';
import AdminOpsSectionHeading from '../components/admin/AdminOpsSectionHeading';
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
} from '../components/terminal/TerminalPrimitives';
import type { MarketProviderHealthStatus } from '../api/marketOverview';
import { useI18n } from '../contexts/UiLanguageContext';
import { cn } from '../utils/cn';
import { formatDateTime, formatNumber, formatPercent } from '../utils/format';
import { marketIntelligenceReasonLabel } from '../utils/marketIntelligenceGuidance';
import { productSetupSurfaceFromCurrentQuery, type ProductSetupSurface } from '../utils/productSetupSurface';

type StatusTone = 'live' | 'cache' | 'stale' | 'fallback' | 'partial' | 'unavailable' | 'error' | 'refreshing';
type ProviderOpsTopSummaryData = {
  availableSources: string[];
  missingSources: string[];
  diagnosticSources: string[];
  affectedSurfaces: string[];
};
type ReadinessDiagnosticGroupId = 'credentials' | 'localCache' | 'coverage' | 'runtime' | 'other';
type DisclosureSeverity = 'blocked' | 'warning' | 'info' | 'ok';
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
const EMPTY_PROVIDER_MATRIX_ROWS: ProviderOperationsMatrixRow[] = [];
const EMPTY_READINESS_CHECKS: MarketDataReadinessCheck[] = [];
const PROVIDER_OPS_DIAGNOSTIC_SURFACE = '数据源运维 / 系统诊断';
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
const MATRIX_SUMMARY_DEFAULTS = {
  totalRows: 0,
  observationOnlyRows: 0,
  inertMetadataOnlyRows: 0,
  missingProviderRows: 0,
  scoreEligibleRows: 0,
  paidDataLikelyRequiredRows: 0,
};
const ADMIN_SECTION_HEADING_CLASSNAME =
  '[&_[data-terminal-primitive=section-header]_p]:text-[12px] [&_[data-terminal-primitive=section-header]_p]:font-medium [&_[data-terminal-primitive=section-header]_h2]:text-lg [&_[data-terminal-primitive=section-header]_h2]:font-semibold md:[&_[data-terminal-primitive=section-header]_h2]:text-xl';

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
    ready: '已就绪',
    partial: '部分就绪',
    missing: '缺失',
    misconfigured: '配置异常',
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
    error: '阻断',
    warning: '注意',
    info: '信息',
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
    portfolio: 'Portfolio',
    watchlist: 'Watchlist',
    options_lab: 'Options Lab',
    stock_history: 'US parquet history',
  }[surface] || surface.replace(/_/g, ' ');
}

function formatReadableList(values: string[], empty = '暂无可展示项'): string {
  if (!values.length) return empty;
  const visible = values.slice(0, 3);
  const suffix = values.length > visible.length ? ` 等 ${formatNumber(values.length, 0)} 项` : '';
  return `${visible.join('、')}${suffix}`;
}

function matrixRowHasMissingSetup(row: ProviderOperationsMatrixRow): boolean {
  const runtimeState = String(row.runtimeState || '').toLowerCase();
  const credentialState = String(row.credentialState || '').toLowerCase();
  const dependencyState = String(row.dependencyState || '').toLowerCase();
  const sourceType = String(row.sourceType || '').toLowerCase();
  return sourceType === 'missing'
    || runtimeState === 'missing'
    || runtimeState === 'credential_missing'
    || runtimeState === 'missing_provider_configuration'
    || credentialState === 'missing'
    || dependencyState === 'dependency_missing'
    || Boolean(row.missingProviderReason);
}

function matrixRowIsPrimaryAvailable(row: ProviderOperationsMatrixRow): boolean {
  return !matrixRowHasMissingSetup(row)
    && row.sourceAuthorityAllowed === true
    && row.scoreContributionAllowed === true
    && row.scoreEligible === true
    && row.observationOnly !== true
    && row.inertMetadataOnly !== true;
}

function matrixRowIsDiagnosticOnly(row: ProviderOperationsMatrixRow): boolean {
  return row.observationOnly === true
    || row.inertMetadataOnly === true
    || row.diagnosticOnly === true
    || row.scoreContributionAllowed === false
    || row.scoreEligible === false;
}

function operationItemIsAvailable(item: MarketProviderOperationItem): boolean {
  const status = normalizeStatus(item.status);
  return (status === 'live' || status === 'cache') && !item.errorSummary && !item.isFallback && !item.fallbackUsed && !item.isStale;
}

function readinessCheckName(check: MarketDataReadinessCheck): string {
  if (check.id === 'tushare_token') return 'Tushare 覆盖凭据';
  if (check.id === 'local_us_parquet_representative_files') return '本地美股历史缓存';
  return sanitizeCodeLabel(check.id).replace(/_/g, ' ');
}

function readinessCheckMessage(check: MarketDataReadinessCheck): string {
  if (check.id === 'tushare_token') return 'Tushare 覆盖凭据未配置，相关 CN/HK 市场上下文只能保持缺口提示。';
  if (check.id === 'local_us_parquet_representative_files') return '部分代表样本缺少本地历史缓存，离线覆盖检查只能显示部分就绪。';
  return sanitizeOperatorText(check.userFacingMessage);
}

function readinessCheckGuidance(check: MarketDataReadinessCheck): string {
  if (check.id === 'tushare_token') return '沿现有凭据配置路径处理，返回本页确认就绪状态；本页不读取或显示密钥值。';
  if (check.id === 'local_us_parquet_representative_files') return '同步已批准的本地历史缓存，或缩小代表样本范围后重新检查。';
  return check.remediationHint ? sanitizeOperatorText(check.remediationHint) : '按现有配置路径处理后，再返回本页确认状态。';
}

function readinessDiagnosticGroupId(check: MarketDataReadinessCheck): ReadinessDiagnosticGroupId {
  const id = check.id.toLowerCase();
  if (check.secretConfigured === false || id.includes('token') || id.includes('credential') || id.includes('key')) return 'credentials';
  if (id.includes('parquet') || id.includes('cache') || id.includes('file') || id.includes('history')) return 'localCache';
  if (check.status === 'ready') return 'coverage';
  if (id.includes('runtime') || id.includes('network') || id.includes('provider')) return 'runtime';
  return 'other';
}

function buildProviderOpsTopSummary(
  items: MarketProviderOperationItem[],
  rows: ProviderOperationsMatrixRow[],
  checks: MarketDataReadinessCheck[],
): ProviderOpsTopSummaryData {
  const availableSources: string[] = [];
  const availableSourceSet = new Set<string>();
  const missingSources: string[] = [];
  const missingSourceSet = new Set<string>();
  const diagnosticSources: string[] = [];
  const diagnosticSourceSet = new Set<string>();
  const affectedSurfaces: string[] = [];
  const affectedSurfaceSet = new Set<string>();

  const pushUniqueValue = (list: string[], seen: Set<string>, value: string): void => {
    if (!value || seen.has(value)) return;
    seen.add(value);
    list.push(value);
  };

  for (const item of items) {
    if (operationItemIsAvailable(item)) {
      pushUniqueValue(availableSources, availableSourceSet, providerLabel(item));
    }
  }

  for (const row of rows) {
    if (matrixRowIsPrimaryAvailable(row)) {
      pushUniqueValue(availableSources, availableSourceSet, sourceGapName(row));
    }
    if (matrixRowHasMissingSetup(row)) {
      pushUniqueValue(missingSources, missingSourceSet, sourceGapName(row));
    }
    if (matrixRowIsDiagnosticOnly(row)) {
      pushUniqueValue(diagnosticSources, diagnosticSourceSet, sourceGapName(row));
    }
    for (const surface of resolveChecklistMatrixSurfaces(row)) {
      if (surface === PROVIDER_OPS_DIAGNOSTIC_SURFACE) continue;
      pushUniqueValue(affectedSurfaces, affectedSurfaceSet, surface);
    }
  }

  for (const check of checks) {
    if (shouldIncludeChecklistReadinessCheck(check)) {
      pushUniqueValue(missingSources, missingSourceSet, readinessCheckName(check));
    }
    for (const surface of resolveChecklistReadinessSurfaces(check)) {
      if (surface === PROVIDER_OPS_DIAGNOSTIC_SURFACE) continue;
      pushUniqueValue(affectedSurfaces, affectedSurfaceSet, surface);
    }
  }

  return {
    availableSources,
    missingSources,
    diagnosticSources,
    affectedSurfaces: affectedSurfaces.length ? affectedSurfaces : [PROVIDER_OPS_DIAGNOSTIC_SURFACE],
  };
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
  const collectStringValues = (values: unknown): string[] => {
    if (!Array.isArray(values)) return [];
    const normalizedValues: string[] = [];
    for (const value of values) {
      const normalized = String(value ?? '').trim();
      if (!normalized) continue;
      normalizedValues.push(normalized);
    }
    return normalizedValues;
  };

  const envKeys = collectStringValues(details.envKeys);
  const envKey = typeof details.envKey === 'string' ? details.envKey.trim() : '';
  const availableModules = collectStringValues(details.availableModules);
  const missingModules = collectStringValues(details.missingModules);
  const representativeSymbols = collectStringValues(details.representativeSymbols);
  const missingSymbols = collectStringValues(details.missingSymbols);
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

function sanitizeCodeLabel(value?: string | null, fallback = '暂无数据'): string {
  if (!value) return fallback;
  return sanitizeOperatorText(value, fallback);
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

const ADMIN_LOG_ROUTES = new Set(['/zh/admin/logs', '/en/admin/logs']);
const ADMIN_LOG_TABS = new Set(['business', 'analysis', 'scanner', 'backtest', 'data_source', 'security', 'raw']);
const ADMIN_LOG_WINDOWS = new Set(['15m', '1h', '24h', '7d']);

function sanitizeAdminLogSearchText(value: unknown, maxLength = 80): string | null {
  const cleaned = String(value || '')
    .replace(/https?:\/\/\S+|www\.\S+/gi, ' ')
    .replace(SENSITIVE_FRAGMENT_PATTERN, '$1 ')
    .replace(/\b(token|secret|cookie|session|password|bearer|api[_-]?key|stack|trace|payload|prompt|credential)\b[:=]?\S*/gi, ' ')
    .replace(/[^a-zA-Z0-9 _:-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, maxLength);
  return cleaned || null;
}

function sanitizeAdminLogCode(value: unknown, maxLength = 80): string | null {
  const cleaned = String(value || '')
    .replace(/https?:\/\/\S+|www\.\S+/gi, '')
    .replace(SENSITIVE_FRAGMENT_PATTERN, '$1')
    .replace(/\b(token|secret|cookie|session|password|bearer|api[_-]?key|stack|trace|payload|prompt|credential)\b[:=]?\S*/gi, '')
    .replace(/[^a-zA-Z0-9:_-]/g, '')
    .trim()
    .slice(0, maxLength);
  return cleaned || null;
}

function buildAdminLogHref(drill?: AdminLogDrillThrough): string | null {
  if (!drill?.route || !ADMIN_LOG_ROUTES.has(drill.route)) return null;
  const query = new URLSearchParams();
  const params = drill.query || {};
  const tab = sanitizeAdminLogCode(params.tab, 24);
  if (tab && ADMIN_LOG_TABS.has(tab)) query.set('tab', tab);
  const queryTextValue = [
    params.query,
    params.provider,
    params.source,
    params.surface,
    params.domain,
  ].flatMap((value) => {
    const safe = sanitizeAdminLogSearchText(value);
    return safe ? [safe] : [];
  }).filter((value, index, values) => values.indexOf(value) === index).join(' ');
  const safeQueryText = sanitizeAdminLogSearchText(queryTextValue);
  if (safeQueryText) query.set('query', safeQueryText);
  const since = String(params.since || '');
  if (ADMIN_LOG_WINDOWS.has(since)) query.set('since', since);
  const eventId = sanitizeAdminLogCode(drill.eventId || params.eventId);
  if (eventId) query.set('eventId', eventId);
  const requestId = sanitizeAdminLogCode(params.requestId);
  if (requestId) query.set('requestId', requestId);
  const userId = sanitizeAdminLogCode(params.userId);
  if (userId) query.set('userId', userId);
  const queryText = query.toString().replace(/\+/g, '%20');
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

function matrixStateVariant(value?: string | null): 'neutral' | 'success' | 'caution' | 'danger' | 'info' {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'runtime_metadata' || normalized === 'present' || normalized === 'installed') return 'success';
  if (normalized === 'credential_missing' || normalized === 'dependency_missing' || normalized === 'missing_provider_configuration') return 'caution';
  if (normalized === 'missing') return 'caution';
  if (normalized === 'observation_only') return 'info';
  return 'neutral';
}

function matrixGateVariant(value: boolean | undefined): 'neutral' | 'success' | 'caution' {
  if (value === true) return 'success';
  if (value === false) return 'caution';
  return 'neutral';
}

function matrixGateLabel(label: string, value: boolean): string {
  return `${label}=${value ? 'true' : 'false'}`;
}

function matrixCacheRequired(row: ProviderOperationsMatrixRow): boolean {
  return row.cacheRequired === true || (row.routerReasonCodes || []).includes('cache_required');
}

function matrixReasonCodes(row: ProviderOperationsMatrixRow): string[] {
  const reasons: string[] = [];
  const seen = new Set<string>();
  const pushReason = (value: string | null | undefined): void => {
    if (!value || seen.has(value)) return;
    seen.add(value);
    reasons.push(value);
  };

  for (const value of row.routerReasonCodes || []) {
    pushReason(value);
  }
  for (const value of row.reasonCodes || []) {
    pushReason(value);
  }
  pushReason(row.missingProviderReason);
  pushReason(row.degradationReason);

  return reasons.slice(0, 4);
}

type SourceGapCapability = {
  id: string;
  title: string;
  match: (row: ProviderOperationsMatrixRow) => boolean;
};

type SetupChecklistBadge = {
  label: string;
  variant: 'neutral' | 'success' | 'caution' | 'danger' | 'info';
};

type SetupChecklistEntry = {
  key: string;
  surface: string;
  title: string;
  whyItMatters: string;
  safeNextStep: string;
  badges: SetupChecklistBadge[];
};
type BetaReadinessChecklistItem = {
  key: string;
  title: string;
  detail: string;
  nextStep: string;
  severity: DisclosureSeverity;
  badges: SetupChecklistBadge[];
};
type ProviderOpsActionQueueItem = {
  key: string;
  title: string;
  scope: string;
  action: string;
  severity: DisclosureSeverity;
};

const SOURCE_GAP_CAPABILITIES: SourceGapCapability[] = [
  {
    id: 'p0MarketDirection',
    title: 'P0 市场方向判断',
    match: (row) => capabilityHaystack(row).some((value) => (
      value.includes('market_overview')
      || value.includes('fed_liquidity')
      || value.includes('macro')
      || value.includes('rates')
      || value.includes('credit')
    )),
  },
  {
    id: 'p1LiquidityDirection',
    title: 'P1 流动性方向',
    match: (row) => capabilityHaystack(row).some((value) => (
      value.includes('liquidity_monitor')
      || value.includes('liquidity_impulse')
      || value.includes('liquidity')
      || value.includes('funding')
    )),
  },
  {
    id: 'p2ThemeRotation',
    title: 'P2 主题轮动',
    match: (row) => capabilityHaystack(row).some((value) => (
      value.includes('rotation')
      || value.includes('theme')
      || value.includes('etf')
      || value.includes('flow')
    )),
  },
  {
    id: 'p3RegionalFutures',
    title: 'P3 区域 / 期货确认',
    match: (row) => capabilityHaystack(row).some((value) => (
      value.includes('cn')
      || value.includes('hk')
      || value.includes('china')
      || value.includes('tushare')
      || value.includes('tickflow')
      || value.includes('baostock')
      || value.includes('futures')
      || value.includes('risk')
      || value.includes('volatility')
      || value.includes('vix')
      || value.includes('options')
    )),
  },
];

const CHECKLIST_SURFACE_ORDER = [
  'Market Overview',
  'Liquidity Monitor',
  'Rotation Radar',
  'Scanner',
  'Portfolio',
  'Watchlist',
  'Options Lab',
  'Backtest',
  PROVIDER_OPS_DIAGNOSTIC_SURFACE,
] as const;

const READINESS_DIAGNOSTIC_GROUPS: Array<{
  id: ReadinessDiagnosticGroupId;
  title: string;
  description: string;
}> = [
  { id: 'credentials', title: '凭据配置', description: '只判断是否缺少已声明凭据，不展示密钥值。' },
  { id: 'localCache', title: '本地缓存/历史文件', description: '确认离线快照、parquet 或本地覆盖是否满足代表样本。' },
  { id: 'coverage', title: '覆盖已就绪', description: '当前检查没有阻断项，继续保持只读观察。' },
  { id: 'runtime', title: '运行边界', description: '确认数据源运行时与网络调用边界没有被前端改变。' },
  { id: 'other', title: '其他诊断', description: '保留未归类检查，但降低原始 ID 的视觉优先级。' },
];

function capabilityHaystack(row: ProviderOperationsMatrixRow): string[] {
  const values: string[] = [];
  const pushNormalized = (value: unknown): void => {
    const normalized = String(value ?? '').trim().toLowerCase();
    if (!normalized) return;
    values.push(normalized);
  };

  pushNormalized(row.providerId);
  pushNormalized(row.providerName);
  pushNormalized(row.providerCategory);
  pushNormalized(row.sourceType);
  pushNormalized(row.sourceTier);
  pushNormalized(row.trustLevel);
  pushNormalized(row.runtimeState);
  pushNormalized(row.credentialState);
  pushNormalized(row.dependencyState);
  pushNormalized(row.authorityBasis);
  pushNormalized(row.universe);
  pushNormalized(row.missingProviderReason);
  pushNormalized(row.degradationReason);

  for (const value of row.supportedCapabilities || []) pushNormalized(value);
  for (const value of row.affectedSurfaces || []) pushNormalized(value);
  for (const value of row.routerReasonCodes || []) pushNormalized(value);
  for (const value of row.reasonCodes || []) pushNormalized(value);
  for (const value of row.fulfilledMetrics || []) pushNormalized(value);
  for (const value of row.missingMetrics || []) pushNormalized(value);
  for (const value of row.requiredSourceTiers || []) pushNormalized(value);

  return values;
}

function sourceGapCurrentState(row: ProviderOperationsMatrixRow): string {
  const reasons = matrixReasonCodes(row);
  const primary = row.runtimeState || row.credentialState || row.dependencyState || row.degradationReason || reasons[0];
  return marketIntelligenceReasonLabel(primary, 'zh');
}

function sourceGapImpact(row: ProviderOperationsMatrixRow): string {
  const sourceType = String(row.sourceType || '').toLowerCase();
  const conservativeOnly = row.observationOnly === true
    || row.inertMetadataOnly === true
    || row.diagnosticOnly === true
    || sourceType.includes('snapshot')
    || sourceType.includes('fixture')
    || matrixCacheRequired(row);
  if (row.sourceAuthorityAllowed === false) {
    return '补足可用性说明，并减少备用/代理/缺失状态；是否进入评分仍由既有 source-confidence gates 决定。';
  }
  if (conservativeOnly) {
    return '改善数据覆盖披露；仅用于诊断/观察/配置指引，是否进入评分仍由既有 source-confidence gates 决定。';
  }
  if (row.scoreContributionAllowed === false || row.scoreEligible === false) {
    return '补足可用性说明，并减少备用/代理/缺失状态；是否进入评分仍由既有 source-confidence gates 决定。';
  }
  return '补足可用性说明，并继续沿既有 source-confidence gates 判断是否可用于对应产品面。';
}

function sourceGapRequiredWork(row: ProviderOperationsMatrixRow): string {
  if (row.credentialState === 'missing' || row.keyRequired) {
    return '沿现有运行路径补齐所需凭证。';
  }
  if (row.runtimeState === 'missing_provider_configuration' || row.missingProviderReason) {
    return '补齐既有数据源运行配置，并满足缓存与时效门槛。';
  }
  if (row.dependencyState === 'dependency_missing') {
    return '补齐既有依赖，再让运行时证据进入页面。';
  }
  if (matrixCacheRequired(row)) {
    return '填充已批准的缓存路径，并保持 freshness 达标。';
  }
  return '继续保持数据源运行时、缓存与来源权限门槛通过。';
}

function sourceGapBlocksScoreGrade(row: ProviderOperationsMatrixRow): boolean {
  return row.scoreEligible !== true || row.scoreContributionAllowed !== true || row.sourceAuthorityAllowed !== true;
}

function isPolygonBreadthProjection(row: ProviderOperationsMatrixRow): boolean {
  return row.providerId === 'polygon_us_grouped_daily';
}

function sourceGapBadges(row: ProviderOperationsMatrixRow): Array<{ label: string; variant: 'neutral' | 'success' | 'caution' | 'danger' | 'info' }> {
  if (!isPolygonBreadthProjection(row)) return [];
  const fulfilled = new Set(row.fulfilledMetrics || []);
  const missing = new Set(row.missingMetrics || []);
  const badges: Array<{ label: string; variant: 'neutral' | 'success' | 'caution' | 'danger' | 'info' }> = [];
  if (fulfilled.has('ADVANCERS') && fulfilled.has('DECLINERS')) {
    badges.push({ label: '仅涨跌家数', variant: 'info' });
  }
  if (missing.has('NEW_HIGHS') || missing.has('NEW_LOWS') || missing.has('HIGH_LOW_RATIO')) {
    badges.push({ label: '高低点缺失', variant: 'caution' });
  }
  if (row.sourceFreshnessEvidence?.freshness) {
    badges.push({ label: `EOD ${sanitizeCodeLabel(row.sourceFreshnessEvidence.freshness)}`, variant: 'neutral' });
  }
  if (row.coverageCount != null) {
    badges.push({ label: `coverage ${formatNumber(row.coverageCount, 0)}`, variant: 'neutral' });
  }
  return badges;
}

function sourceGapRowsForCapability(rows: ProviderOperationsMatrixRow[], capability: SourceGapCapability): ProviderOperationsMatrixRow[] {
  const matches: ProviderOperationsMatrixRow[] = [];
  for (const row of rows) {
    if (!capability.match(row)) continue;
    if (!sourceGapBlocksScoreGrade(row) && row.sourceType !== 'missing' && !row.inertMetadataOnly) continue;
    matches.push(row);
    if (matches.length >= 3) break;
  }
  return matches;
}

function sourceGapName(row: ProviderOperationsMatrixRow): string {
  return row.sourceLabel || row.providerName || row.providerId;
}

function checklistSurfaceLabel(surface: string): string | null {
  const normalized = String(surface || '').trim().toLowerCase();
  if (!normalized) return null;
  if (normalized === 'market_overview') return 'Market Overview';
  if (normalized === 'liquidity_monitor' || normalized === 'liquidity_impulse') return 'Liquidity Monitor';
  if (normalized === 'rotation_radar') return 'Rotation Radar';
  if (normalized === 'scanner') return 'Scanner';
  if (normalized === 'portfolio') return 'Portfolio';
  if (normalized === 'watchlist') return 'Watchlist';
  if (normalized === 'options_lab') return 'Options Lab';
  if (normalized === 'backtest') return 'Backtest';
  if (normalized === 'provider_ops' || normalized === 'system_diagnostics' || normalized === 'stock_history') {
    return PROVIDER_OPS_DIAGNOSTIC_SURFACE;
  }
  return null;
}

function resolveChecklistSurfaces(surfaces: string[] | undefined): string[] {
  const labels: string[] = [];
  const seen = new Set<string>();
  for (const surface of surfaces || []) {
    const label = checklistSurfaceLabel(surface);
    if (!label || seen.has(label)) continue;
    seen.add(label);
    labels.push(label);
  }
  return labels.length ? labels : [PROVIDER_OPS_DIAGNOSTIC_SURFACE];
}

function resolveChecklistMatrixSurfaces(row: ProviderOperationsMatrixRow): string[] {
  return resolveChecklistSurfaces(
    row.productAffectedSurfaces?.length ? row.productAffectedSurfaces : row.affectedSurfaces,
  );
}

function resolveChecklistReadinessSurfaces(check: MarketDataReadinessCheck): string[] {
  return resolveChecklistSurfaces(
    check.productAffectedSurfaces?.length ? check.productAffectedSurfaces : check.affectsSurfaces,
  );
}

function pushChecklistBadge(
  badges: SetupChecklistBadge[],
  condition: boolean,
  label: SetupChecklistBadge['label'],
  variant: SetupChecklistBadge['variant'],
): void {
  if (!condition || badges.some((badge) => badge.label === label)) return;
  badges.push({ label, variant });
}

function checklistBadgesForMatrixRow(row: ProviderOperationsMatrixRow): SetupChecklistBadge[] {
  const badges: SetupChecklistBadge[] = [];
  pushChecklistBadge(badges, row.keyRequired === true || row.credentialState === 'missing', 'credential required', 'caution');
  pushChecklistBadge(badges, row.paidDataLikelyRequired === true, 'paid likely', 'caution');
  pushChecklistBadge(badges, matrixCacheRequired(row), 'cache required', 'info');
  pushChecklistBadge(
    badges,
    row.sourceTier === 'official_public' && matrixCacheRequired(row) && row.noDefaultLiveHttpCalls === true,
    'official-public cache-only',
    'neutral',
  );
  pushChecklistBadge(badges, row.enabledByDefault === false, 'disabled by default', 'neutral');
  pushChecklistBadge(
    badges,
    row.providerId === 'official_public.fed_liquidity' || (row.supportedCapabilities || []).includes('fed_liquidity'),
    'aggregate-supported',
    'info',
  );
  pushChecklistBadge(badges, row.observationOnly === true, 'observation-only', 'info');
  pushChecklistBadge(badges, sourceGapBlocksScoreGrade(row), 'score-blocked', 'caution');
  pushChecklistBadge(
    badges,
    row.sourceType === 'missing' || row.runtimeState === 'missing_provider_configuration' || Boolean(row.missingProviderReason),
    'missing provider',
    'danger',
  );
  return badges;
}

function checklistBadgesForReadinessCheck(check: MarketDataReadinessCheck): SetupChecklistBadge[] {
  const badges: SetupChecklistBadge[] = [];
  pushChecklistBadge(badges, check.secretConfigured === false, 'credential required', 'caution');
  pushChecklistBadge(
    badges,
    check.id === 'local_us_parquet_representative_files' || check.id.includes('cache') || check.id.includes('parquet'),
    'cache required',
    'info',
  );
  return badges;
}

function checklistBadgeDisplayLabel(label: string): string {
  return {
    'observation-only': '仅观察',
    'score-blocked': '评分阻断',
    'disabled by default': '默认关闭',
    'cache required': '需要缓存',
    'credential required': '需要凭据',
    'paid likely': '可能需付费',
    'aggregate-supported': '聚合证据',
    'official-public cache-only': '官方公开缓存',
    'missing provider': '缺少数据源配置',
  }[label] || label;
}

function disclosureSeverityVariant(severity: DisclosureSeverity): 'neutral' | 'success' | 'caution' | 'danger' | 'info' {
  if (severity === 'blocked') return 'danger';
  if (severity === 'warning') return 'caution';
  if (severity === 'info') return 'info';
  return 'success';
}

function disclosureSeverityLabel(severity: DisclosureSeverity): string {
  return {
    blocked: '阻断',
    warning: '需处理',
    info: '观察',
    ok: '正常',
  }[severity];
}

function checklistEntrySeverity(entry: SetupChecklistEntry): DisclosureSeverity {
  if (entry.badges.some((badge) => badge.variant === 'danger')) return 'blocked';
  if (entry.badges.some((badge) => badge.variant === 'caution')) return 'warning';
  if (entry.badges.some((badge) => badge.variant === 'info')) return 'info';
  return 'ok';
}

function severityWeight(severity: DisclosureSeverity): number {
  return {
    blocked: 0,
    warning: 1,
    info: 2,
    ok: 3,
  }[severity];
}

function defaultChecklistWhyItMatters(title: string, conservativeOnly = false): string {
  if (conservativeOnly) {
    return `${title} 仅用于诊断/观察/配置指引，用来补足可用性说明并改善数据覆盖披露；是否进入评分仍由既有 source-confidence gates 决定。`;
  }
  return `${title} 已在本页出现，说明现有就绪诊断或来源可信度依赖会影响对应产品面；是否进入评分仍由既有 source-confidence gates 决定。`;
}

function defaultChecklistNextStep(title: string, conservativeOnly = false): string {
  if (conservativeOnly) {
    return `沿现有 ${title} 配置路径处理，优先减少备用/代理/缺失状态，再回到本页确认覆盖披露是否补齐；本页保持只读。`;
  }
  return `沿现有 ${title} 配置路径处理，再返回本页确认就绪状态；本页保持只读。`;
}

function checklistCopyForMatrixRow(row: ProviderOperationsMatrixRow): Pick<SetupChecklistEntry, 'title' | 'whyItMatters' | 'safeNextStep'> {
  if (row.providerId === 'polygon_us_grouped_daily') {
    return {
      title: sourceGapName(row),
      whyItMatters: '美股 grouped-daily 宽度可以辅助解释美股大盘背景，但高低点指标缺失时只能改善数据覆盖披露；是否进入评分仍由既有 source-confidence gates 决定。',
      safeNextStep: '保持 Polygon grouped-daily 宽度走已批准的凭据与缓存路径，先补齐覆盖并减少缺失状态，再观察主背景披露是否完整。',
    };
  }
  if (row.providerId === 'official_public.fed_liquidity') {
    return {
      title: sourceGapName(row),
      whyItMatters: 'Fed 聚合证据可以补充广义流动性背景，但未配置前仅用于补足可用性说明与覆盖披露；是否进入评分仍由既有 source-confidence gates 决定。',
      safeNextStep: '补齐既有 Fed liquidity 聚合证据缓存，先减少缺失状态并让背景披露完整，同时保持只读边界。',
    };
  }
  if (row.providerId === 'official_public.cn_money_market_cache') {
    return {
      title: sourceGapName(row),
      whyItMatters: '官方公开 money-market 缓存有助于观察短端流动性背景，但仍仅用于诊断/观察/配置指引；是否进入评分仍由既有 source-confidence gates 决定。',
      safeNextStep: '刷新已批准的官方公开 money-market 缓存快照，改善数据覆盖披露；本页只确认状态。',
    };
  }
  if (row.providerId === 'cache.cn_hk_connect_daily') {
    return {
      title: sourceGapName(row),
      whyItMatters: 'CN/HK connect 缓存可以解释区域轮动背景，但缺少 southbound 时只用于改善数据覆盖披露；是否进入评分仍由既有 source-confidence gates 决定。',
      safeNextStep: '刷新 CN/HK connect 缓存快照，减少覆盖缺口并保持不新增实时数据源调用。',
    };
  }
  if (row.providerId === 'authorized.cn_index_futures_feed') {
    return {
      title: sourceGapName(row),
      whyItMatters: '指数期货授权源可以补充区域风险确认，但是否进入评分仍由既有授权与 source-confidence gates 决定。',
      safeNextStep: '完成现有授权 feed 配置后，再返回本页确认期货确认链路是否通过。',
    };
  }
  if (row.providerId === 'tushare_pro') {
    return {
      title: sourceGapName(row),
      whyItMatters: 'Tushare 覆盖可以补齐 CN/HK 日频背景，但是否进入评分仍由既有 source-confidence gates 决定，不承诺更高信号质量或投资准确性。',
      safeNextStep: '沿现有 Tushare 凭据配置路径处理，并继续避免在本页显示密钥值。',
    };
  }
  const title = sourceGapName(row);
  const conservativeOnly = row.observationOnly === true
    || row.inertMetadataOnly === true
    || row.diagnosticOnly === true
    || matrixCacheRequired(row)
    || String(row.sourceType || '').toLowerCase().includes('snapshot')
    || String(row.sourceType || '').toLowerCase().includes('fixture');
  return {
    title,
    whyItMatters: defaultChecklistWhyItMatters(title, conservativeOnly),
    safeNextStep: defaultChecklistNextStep(title, conservativeOnly),
  };
}

function checklistCopyForReadinessCheck(check: MarketDataReadinessCheck): Pick<SetupChecklistEntry, 'title' | 'whyItMatters' | 'safeNextStep'> {
  if (check.id === 'tushare_token') {
    return {
      title: 'Tushare',
      whyItMatters: 'Tushare 覆盖可以补齐 CN/HK 市场背景，但是否进入评分仍由既有 source-confidence gates 决定，不承诺更高信号质量或投资准确性。',
      safeNextStep: '沿现有 Tushare 凭据配置路径处理，并继续避免在本页显示密钥值。',
    };
  }
  if (check.id === 'local_us_parquet_representative_files') {
    return {
      title: '本地美股历史缓存',
      whyItMatters: '本地美股历史覆盖决定离线检查能确认哪些磁盘数据；缺文件时仅用于诊断/观察/配置指引，并改善数据覆盖披露。',
      safeNextStep: '同步已批准的本地美股 parquet/cache 覆盖，先减少缺失状态，再期待代表样本检查清空。',
    };
  }
  const title = sanitizeCodeLabel(check.id);
  return {
    title,
    whyItMatters: defaultChecklistWhyItMatters(title, true),
    safeNextStep: defaultChecklistNextStep(title, true),
  };
}

function shouldIncludeChecklistMatrixRow(row: ProviderOperationsMatrixRow): boolean {
  return row.keyRequired === true
    || row.paidDataLikelyRequired === true
    || matrixCacheRequired(row)
    || row.enabledByDefault === false
    || row.observationOnly === true
    || row.scoreEligible !== true
    || row.scoreContributionAllowed !== true
    || row.sourceAuthorityAllowed !== true
    || row.runtimeState === 'missing_provider_configuration'
    || Boolean(row.missingProviderReason);
}

function shouldIncludeChecklistReadinessCheck(check: MarketDataReadinessCheck): boolean {
  return check.status !== 'ready'
    || check.secretConfigured === false
    || check.id === 'local_us_parquet_representative_files';
}

function buildSetupChecklistEntries(
  rows: ProviderOperationsMatrixRow[],
  checks: MarketDataReadinessCheck[],
): SetupChecklistEntry[] {
  const entries: SetupChecklistEntry[] = [];

  for (const row of rows) {
    if (!shouldIncludeChecklistMatrixRow(row)) continue;
    const copy = checklistCopyForMatrixRow(row);
    const badges = checklistBadgesForMatrixRow(row);
    for (const surface of resolveChecklistMatrixSurfaces(row)) {
      entries.push({
        key: `matrix:${row.providerId}:${surface}`,
        surface,
        title: copy.title,
        whyItMatters: copy.whyItMatters,
        safeNextStep: copy.safeNextStep,
        badges,
      });
    }
  }

  for (const check of checks) {
    if (!shouldIncludeChecklistReadinessCheck(check)) continue;
    const copy = checklistCopyForReadinessCheck(check);
    const badges = checklistBadgesForReadinessCheck(check);
    for (const surface of resolveChecklistReadinessSurfaces(check)) {
      entries.push({
        key: `readiness:${check.id}:${surface}`,
        surface,
        title: copy.title,
        whyItMatters: copy.whyItMatters,
        safeNextStep: copy.safeNextStep,
        badges,
      });
    }
  }

  return entries;
}

function betaReadinessStatusSeverity(status?: string | null): DisclosureSeverity {
  const normalized = String(status || '').trim().toLowerCase();
  if (normalized === 'missing' || normalized === 'misconfigured') return 'blocked';
  if (normalized === 'partial') return 'warning';
  if (normalized === 'ready') return 'ok';
  return 'info';
}

function buildBetaReadinessChecklistItems(
  items: MarketProviderOperationItem[],
  rows: ProviderOperationsMatrixRow[],
  checks: MarketDataReadinessCheck[],
  topSummary: ProviderOpsTopSummaryData,
  summary: MarketProviderOperationsSummary,
  readinessStatus?: string | null,
): BetaReadinessChecklistItem[] {
  const blockedSetupCount = rows.filter(matrixRowHasMissingSetup).length;
  const nonReadyChecks = checks.filter((check) => shouldIncludeChecklistReadinessCheck(check));
  const cacheRequiredCount = rows.filter((row) => matrixCacheRequired(row)).length;
  const degradedSignals = summary.fallbackCount + summary.partialCount + summary.staleCount + summary.unavailableCount + summary.errorCount + summary.failureCount;
  const fallbackSignals = summary.fallbackCount + summary.fallbackEventCount;
  const staleSignals = summary.staleCount + summary.staleEventCount;
  const liveReadyCount = items.filter(operationItemIsAvailable).length;
  const observeOnlyCount = topSummary.diagnosticSources.length;
  const representativeStatus = readinessStatusLabel(readinessStatus || 'missing');
  const firstReadinessAction = nonReadyChecks[0] ? readinessCheckGuidance(nonReadyChecks[0]) : '继续保持本地样本与缓存覆盖处于只读可验证状态。';

  return [
    {
      key: 'setup',
      title: '数据源配置',
      detail: blockedSetupCount > 0 || topSummary.missingSources.length > 0
        ? `待补齐 ${formatNumber(topSummary.missingSources.length || blockedSetupCount, 0)} 项：${formatReadableList(topSummary.missingSources, '当前未见配置缺口')}`
        : '当前没有新增配置阻断项，可继续沿现有来源契约观察。',
      nextStep: blockedSetupCount > 0 || topSummary.missingSources.length > 0
        ? '先沿现有凭据、授权 feed、缓存与 provider 配置路径补齐，再回本页确认。'
        : '保持只读观察，不新增数据源或运行时调用。',
      severity: blockedSetupCount > 0 || topSummary.missingSources.length > 0 ? 'blocked' : 'ok',
      badges: [
        { label: `需补齐 ${formatNumber(topSummary.missingSources.length || blockedSetupCount, 0)} 项`, variant: blockedSetupCount > 0 || topSummary.missingSources.length > 0 ? 'danger' : 'success' },
        { label: `可用 ${formatNumber(liveReadyCount, 0)} 项`, variant: liveReadyCount > 0 ? 'success' : 'neutral' },
      ],
    },
    {
      key: 'readiness',
      title: '本地样本与缓存',
      detail: `就绪状态 ${representativeStatus} · readiness 检查 ${formatNumber(nonReadyChecks.length, 0)} 项待关注 · 需要缓存 ${formatNumber(cacheRequiredCount, 0)} 条契约`,
      nextStep: firstReadinessAction,
      severity: betaReadinessStatusSeverity(readinessStatus),
      badges: [
        { label: representativeStatus, variant: readinessStatus === 'ready' ? 'success' : readinessStatus === 'partial' ? 'caution' : 'danger' },
        { label: `检查 ${formatNumber(nonReadyChecks.length, 0)} 项`, variant: nonReadyChecks.length ? 'caution' : 'success' },
      ],
    },
    {
      key: 'degraded',
      title: '降级 / 备用观察',
      detail: `备用 ${formatNumber(fallbackSignals, 0)} · 过期 ${formatNumber(staleSignals, 0)} · 部分 ${formatNumber(summary.partialCount, 0)} · 失败 ${formatNumber(summary.failureCount + summary.errorCount, 0)}`,
      nextStep: degradedSignals > 0
        ? '先核对 fallback、stale、partial 与失败路径，再通过 Admin Logs / 熔断页确认是否仍适合 beta 观察。'
        : '当前未见明显降级信号，继续保持只读观测。',
      severity: degradedSignals > 0 ? 'warning' : 'ok',
      badges: [
        { label: `降级 ${formatNumber(degradedSignals, 0)}`, variant: degradedSignals > 0 ? 'caution' : 'success' },
        { label: summary.refreshingCount > 0 ? `刷新中 ${formatNumber(summary.refreshingCount, 0)}` : '无刷新阻塞', variant: summary.refreshingCount > 0 ? 'info' : 'neutral' },
      ],
    },
    {
      key: 'observe',
      title: '仅观察来源',
      detail: observeOnlyCount > 0
        ? `${formatNumber(observeOnlyCount, 0)} 项仅用于诊断/观察：${formatReadableList(topSummary.diagnosticSources, '暂无仅观察项')}`
        : '当前没有额外仅观察来源置顶到 beta checklist。',
      nextStep: observeOnlyCount > 0
        ? '把这些来源当作 beta 期间的说明与覆盖线索，不把它们提升成默认结论证据。'
        : '继续沿现有 source-confidence gates 解释数据可用性。',
      severity: observeOnlyCount > 0 ? 'info' : 'ok',
      badges: [
        { label: `仅观察 ${formatNumber(observeOnlyCount, 0)} 项`, variant: observeOnlyCount > 0 ? 'info' : 'success' },
        { label: `影响页 ${formatNumber(topSummary.affectedSurfaces.length, 0)} 个`, variant: 'neutral' },
      ],
    },
  ];
}

function buildProviderActionQueue(
  items: MarketProviderOperationItem[],
  rows: ProviderOperationsMatrixRow[],
  checks: MarketDataReadinessCheck[],
): ProviderOpsActionQueueItem[] {
  const queue: ProviderOpsActionQueueItem[] = [];
  const seen = new Set<string>();
  const pushItem = (item: ProviderOpsActionQueueItem): void => {
    if (seen.has(item.key) || queue.length >= 4) return;
    seen.add(item.key);
    queue.push(item);
  };

  for (const row of rows) {
    if (!matrixRowHasMissingSetup(row) && !sourceGapBlocksScoreGrade(row)) continue;
    const surfaces = resolveChecklistMatrixSurfaces(row).filter((surface) => surface !== PROVIDER_OPS_DIAGNOSTIC_SURFACE);
    pushItem({
      key: `matrix:${row.providerId}`,
      title: `${sourceGapName(row)} 需要运维确认`,
      scope: formatReadableList(surfaces, '数据源运维'),
      action: sourceGapRequiredWork(row),
      severity: matrixRowHasMissingSetup(row) ? 'blocked' : 'warning',
    });
  }

  for (const check of checks) {
    if (check.status === 'ready' && check.severity !== 'warning' && check.severity !== 'error') continue;
    pushItem({
      key: `readiness:${check.id}`,
      title: readinessCheckName(check),
      scope: formatReadableList(resolveChecklistReadinessSurfaces(check), '本地就绪诊断'),
      action: readinessCheckGuidance(check),
      severity: check.severity === 'error' ? 'blocked' : 'warning',
    });
  }

  for (const item of items) {
    if (!item.errorSummary && !item.warning && !item.isFallback && !item.fallbackUsed && !item.isStale) continue;
    pushItem({
      key: `provider:${providerKey(item)}`,
      title: providerLabel(item),
      scope: item.card || item.domain || '数据源运维',
      action: providerNextAction(item),
      severity: item.errorSummary ? 'blocked' : 'warning',
    });
  }

  return queue.sort((left, right) => severityWeight(left.severity) - severityWeight(right.severity) || left.title.localeCompare(right.title)).slice(0, 4);
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
  const providerScore = (item: MarketProviderOperationItem): number => (
    Number(Boolean(item.errorSummary)) * 10
    + Number(Boolean(item.isFallback || item.fallbackUsed)) * 6
    + Number(Boolean(item.isStale)) * 4
    + Number(Boolean(item.isRefreshing)) * 2
  );

  let preferred = items[0];
  let preferredScore = providerScore(preferred);

  for (let index = 1; index < items.length; index += 1) {
    const candidate = items[index];
    const candidateScore = providerScore(candidate);
    if (candidateScore <= preferredScore) continue;
    preferred = candidate;
    preferredScore = candidateScore;
  }

  return preferred;
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

const ProviderOpsTopSummary: React.FC<{
  data: ProviderOpsTopSummaryData;
  isLoading: boolean;
}> = ({ data, isLoading }) => {
  const summaryItems = [
    {
      label: '数据源可用',
      value: isLoading ? '读取中' : `${formatNumber(data.availableSources.length, 0)} 项`,
      detail: formatReadableList(data.availableSources, '暂无实时或可计分来源'),
      variant: data.availableSources.length ? 'success' : 'neutral',
    },
    {
      label: '需补齐',
      value: isLoading ? '读取中' : `${formatNumber(data.missingSources.length, 0)} 项`,
      detail: formatReadableList(data.missingSources, '当前未见配置缺口'),
      variant: data.missingSources.length ? 'caution' : 'success',
    },
    {
      label: '仅诊断/观察',
      value: isLoading ? '读取中' : `${formatNumber(data.diagnosticSources.length, 0)} 项`,
      detail: formatReadableList(data.diagnosticSources, '暂无仅观察项'),
      variant: data.diagnosticSources.length ? 'info' : 'neutral',
    },
    {
      label: '影响产品页',
      value: isLoading ? '读取中' : `${formatNumber(data.affectedSurfaces.length, 0)} 个`,
      detail: formatReadableList(data.affectedSurfaces, '仅数据源运维诊断'),
      variant: 'neutral',
    },
  ] as const;

  return (
    <div data-testid="market-provider-readability-summary" className="mt-5 rounded-lg border border-white/[0.07] bg-white/[0.025] p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-white/34">首屏摘要</p>
          <p className="mt-1 text-sm font-semibold text-white/84">先确认状态、缺口、观察边界和影响页面</p>
        </div>
        <TerminalChip variant="info">不改变数据源语义</TerminalChip>
      </div>
      <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-4">
        {summaryItems.map((item) => (
          <div key={item.label} className="min-w-0 rounded-md border border-white/[0.06] bg-black/10 px-3 py-2.5">
            <div className="flex items-center justify-between gap-2">
              <p className="text-[11px] font-medium text-white/50">{item.label}</p>
              <TerminalChip variant={item.variant}>{item.value}</TerminalChip>
            </div>
            <p className="mt-2 line-clamp-2 text-xs leading-5 text-white/72">{item.detail}</p>
          </div>
        ))}
      </div>
    </div>
  );
};

const ProviderOpsActionQueue: React.FC<{
  items: ProviderOpsActionQueueItem[];
  isLoading: boolean;
}> = ({ items, isLoading }) => (
  <div data-testid="market-provider-action-queue" className="mt-3 rounded-lg border border-white/[0.07] bg-black/10 px-3 py-3">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div className="min-w-0">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-white/34">L1 行动队列</p>
        <p className="mt-1 text-sm font-semibold text-white/84">优先处理少量阻断和注意项</p>
      </div>
      <TerminalChip variant={items.length ? 'caution' : 'success'}>
        {isLoading ? '读取中' : items.length ? `${formatNumber(items.length, 0)} 项` : '暂无待办'}
      </TerminalChip>
    </div>
    <div className="mt-3 grid gap-2">
      {isLoading && !items.length ? (
        <p className="text-[11px] leading-5 text-white/40">正在汇总行动队列；不触发额外 provider 调用。</p>
      ) : null}
      {!isLoading && !items.length ? (
        <p className="text-[11px] leading-5 text-white/44">当前没有需要置顶处理的 provider 缺口；继续保持只读观察。</p>
      ) : null}
      {items.map((item) => (
        <div key={item.key} className="grid min-w-0 gap-2 rounded-md border border-white/[0.06] bg-white/[0.025] px-3 py-2.5 md:grid-cols-[minmax(0,0.95fr)_minmax(0,0.7fr)_minmax(0,1.35fr)] md:items-center">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-1.5">
              <TerminalChip variant={disclosureSeverityVariant(item.severity)}>{disclosureSeverityLabel(item.severity)}</TerminalChip>
              <p className="min-w-0 truncate text-xs font-semibold text-white/82">{item.title}</p>
            </div>
          </div>
          <p className="min-w-0 truncate text-[11px] leading-5 text-white/52">影响：{item.scope}</p>
          <p className="min-w-0 text-[11px] leading-5 text-white/62">下一步：{item.action}</p>
        </div>
      ))}
    </div>
  </div>
);

const SourceGapBoard: React.FC<{ rows: ProviderOperationsMatrixRow[] }> = ({ rows }) => (
  <div data-testid="market-provider-source-gap-board" className="mt-4 grid min-w-0 gap-3 xl:grid-cols-2">
    {SOURCE_GAP_CAPABILITIES.map((capability) => {
      const gapRows = sourceGapRowsForCapability(rows, capability);
      return (
        <TerminalNestedBlock key={capability.id} className="min-w-0 bg-black/10">
          <div className="flex min-w-0 items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-white/34">优先级路线图</p>
              <p className="mt-1 truncate text-sm font-semibold text-white/82">{capability.title}</p>
            </div>
            <TerminalChip variant={gapRows.length ? 'caution' : 'success'}>
              {gapRows.length ? `${gapRows.length} 项待补齐` : '已清空'}
            </TerminalChip>
          </div>
          <div className="mt-3 grid gap-2">
            {gapRows.length ? gapRows.map((row) => {
              const badges = sourceGapBadges(row);
              return (
                <div key={`${capability.id}-${row.providerId}`} className="rounded-md border border-white/[0.06] bg-white/[0.025] px-3 py-2">
                  <p className="truncate text-xs font-semibold text-white/78">{sourceGapName(row)}</p>
                  {badges.length ? (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {badges.map((badge) => (
                        <TerminalChip key={`${row.providerId}-${badge.label}`} variant={badge.variant}>{badge.label}</TerminalChip>
                      ))}
                    </div>
                  ) : null}
                  <p className="mt-1 text-[11px] leading-5 text-white/48">
                    当前为什么不可用：{marketIntelligenceReasonLabel(row.missingProviderReason || row.degradationReason || row.runtimeState, 'zh')}
                  </p>
                  <p className="mt-1 text-[11px] leading-5 text-white/48">
                    解锁能力：{sourceGapImpact(row)}
                  </p>
                  <p className="mt-1 text-[11px] leading-5 text-white/48">
                    当前状态：{sourceGapCurrentState(row)}
                  </p>
                  <p className="mt-1 text-[11px] leading-5 text-white/48">
                    所需工作：{sourceGapRequiredWork(row)}
                  </p>
                  <p className="mt-1 text-[11px] font-semibold text-amber-100/72">
                    阻断评分级结论：{sourceGapBlocksScoreGrade(row) ? '是' : '否'}
                  </p>
                </div>
              );
            }) : (
              <p className="text-[11px] leading-5 text-white/38">当前没有可见的阻断项。</p>
            )}
          </div>
        </TerminalNestedBlock>
      );
    })}
  </div>
);

const SourceGapDisclosure: React.FC<{ rows: ProviderOperationsMatrixRow[] }> = ({ rows }) => {
  const [open, setOpen] = useState(false);
  const gapCount = rows.filter(matrixRowHasMissingSetup).length;
  return (
    <TerminalNestedBlock
      data-testid="market-provider-source-gap-disclosure"
      data-open={open ? 'true' : 'false'}
      className="mt-4 bg-black/10 px-2.5 py-2"
    >
      <div className="flex min-w-0 items-center justify-between gap-2">
        <div className="min-w-0">
          <h3 className="truncate text-xs font-medium text-[color:var(--wolfy-text-secondary)]">L2 来源缺口：影响产品面 / 解锁能力 / 下一步</h3>
          <p className="mt-0.5 truncate text-[11px] text-[color:var(--wolfy-text-muted)]">
            默认折叠 · {formatNumber(gapCount, 0)} 个缺口线索 · 仅显示已脱敏原因与工作说明
          </p>
        </div>
        <TerminalButton
          variant="compact"
          aria-expanded={open}
          aria-label={`${open ? '收起' : '展开'} L2 来源缺口：影响产品面 / 解锁能力 / 下一步`}
          onClick={() => setOpen((current) => !current)}
        >
          {open ? '收起' : '展开'}
        </TerminalButton>
      </div>
      {open ? <SourceGapBoard rows={rows} /> : null}
    </TerminalNestedBlock>
  );
};

const ProviderSetupChecklistPanel: React.FC<{
  rows: ProviderOperationsMatrixRow[];
  checks: MarketDataReadinessCheck[];
  isLoading: boolean;
  surfaceFocus: ProductSetupSurface | null;
  topSummary: ProviderOpsTopSummaryData;
  summary: MarketProviderOperationsSummary;
  operationItems: MarketProviderOperationItem[];
  readinessStatus?: string | null;
}> = ({ rows, checks, isLoading, surfaceFocus, topSummary, summary, operationItems, readinessStatus }) => {
  const entries = buildSetupChecklistEntries(rows, checks);
  const betaReadinessItems = buildBetaReadinessChecklistItems(
    operationItems,
    rows,
    checks,
    topSummary,
    summary,
    readinessStatus,
  );
  const groups: Array<{ surface: string; items: SetupChecklistEntry[]; severity: DisclosureSeverity }> = [];

  for (const surface of CHECKLIST_SURFACE_ORDER) {
    const items = entries
      .filter((entry) => entry.surface === surface)
      .sort((left, right) => left.title.localeCompare(right.title));
    if (!items.length) continue;
    const severity = items.reduce<DisclosureSeverity>((current, item) => (
      severityWeight(checklistEntrySeverity(item)) < severityWeight(current) ? checklistEntrySeverity(item) : current
    ), 'ok');
    groups.push({ surface, items, severity });
  }
  return (
    <TerminalNestedBlock data-testid="market-provider-setup-checklist" className="mt-4 bg-black/10 px-3 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-white/34">Beta readiness</p>
          <p className="mt-1 text-sm font-semibold text-white/82">数据源配置清单</p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <TerminalChip variant="neutral">{formatNumber(groups.length, 0)} 个产品面</TerminalChip>
          <TerminalChip variant="info">{formatNumber(entries.length, 0)} 个配置项</TerminalChip>
        </div>
      </div>
      <p className="mt-2 text-[11px] leading-5 text-white/48">
        只读展示现有数据源缺口会影响哪些产品面、缺少哪类依赖，以及下一步应沿哪个既有配置路径处理；仅用于诊断/观察/配置指引，是否进入评分仍由既有 source-confidence gates 决定。
      </p>
      <div data-testid="market-provider-beta-readiness-checklist" className="mt-3 grid gap-2">
        {betaReadinessItems.map((item) => (
          <div
            key={item.key}
            data-testid={`market-provider-beta-readiness-${item.key}`}
            className="grid min-w-0 gap-2 rounded-md border border-white/[0.06] bg-white/[0.025] px-3 py-2.5 md:grid-cols-[minmax(0,0.8fr)_minmax(0,1.25fr)]"
          >
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-1.5">
                <TerminalChip variant={disclosureSeverityVariant(item.severity)}>{disclosureSeverityLabel(item.severity)}</TerminalChip>
                <p className="min-w-0 truncate text-xs font-semibold text-white/84">{item.title}</p>
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {item.badges.map((badge) => (
                  <TerminalChip key={`${item.key}-${badge.label}`} variant={badge.variant}>{badge.label}</TerminalChip>
                ))}
              </div>
            </div>
            <div className="min-w-0">
              <p className="text-[11px] leading-5 text-white/56">{item.detail}</p>
              <p className="mt-1 text-[11px] leading-5 text-white/66">下一步：{item.nextStep}</p>
            </div>
          </div>
        ))}
      </div>
      {surfaceFocus ? (
        <div
          data-testid="market-provider-setup-surface-focus"
          className="mt-3 rounded-md border border-cyan-200/12 bg-cyan-300/[0.035] px-3 py-2 text-[11px] leading-5 text-white/56"
        >
          <span className="font-semibold text-cyan-100/82">已按 {surfaceFocus.label} 聚焦：</span>
          {' '}
          默认只标记该产品面，细节仍需按需展开，避免首屏变成完整清单墙。以下清单来自现有 productAffectedSurfaces，用于确认覆盖缺口；仅改善数据覆盖披露，不会改变评分规则。
        </div>
      ) : null}

      {isLoading && !entries.length ? (
        <p className="mt-3 text-[11px] leading-5 text-white/38">正在汇总配置清单；仍然只读，不触发数据源运行时。</p>
      ) : null}

      {!isLoading && !groups.length ? (
        <p className="mt-3 text-[11px] leading-5 text-white/38">当前没有额外配置阻断项；完整矩阵与技术诊断仍保留在下方。</p>
      ) : null}

      {groups.length ? (
        <div className="mt-3 grid gap-2">
          {groups.map((group) => (
            <TerminalDisclosure
              key={group.surface}
              data-testid={`market-provider-setup-surface-${group.surface.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`}
              title={group.surface}
              summary={`${formatNumber(group.items.length, 0)} 项 · ${disclosureSeverityLabel(group.severity)} · 默认折叠`}
              className={cn(
                'bg-white/[0.025]',
                surfaceFocus?.label === group.surface ? 'border-cyan-200/20 bg-cyan-300/[0.035]' : '',
              )}
            >
              <div className="space-y-2">
                {group.items.map((entry) => (
                  <div key={entry.key} className="rounded-md border border-white/[0.05] bg-black/10 px-3 py-2.5">
                    <p className="text-xs font-semibold text-white/78">{entry.title}</p>
                    {entry.badges.length ? (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {entry.badges.map((badge) => (
                          <TerminalChip key={`${entry.key}-${badge.label}`} variant={badge.variant}>
                            {checklistBadgeDisplayLabel(badge.label)}
                          </TerminalChip>
                        ))}
                      </div>
                    ) : null}
                    <p className="mt-2 text-[11px] leading-5 text-white/54">
                      影响说明：{entry.whyItMatters}
                    </p>
                    <p className="mt-1 text-[11px] leading-5 text-white/62">
                      安全下一步：{entry.safeNextStep}
                    </p>
                  </div>
                ))}
              </div>
            </TerminalDisclosure>
          ))}
        </div>
      ) : null}
    </TerminalNestedBlock>
  );
};

const ProviderOperationsMatrixPanel: React.FC<{
  response: ProviderOperationsMatrixResponse | null;
  readiness: MarketDataReadinessResponse | null;
  isLoading: boolean;
  isReadinessLoading: boolean;
  error: ParsedApiError | null;
  surfaceFocus: ProductSetupSurface | null;
  topSummary: ProviderOpsTopSummaryData;
  opsSummary: MarketProviderOperationsSummary;
  operationItems: MarketProviderOperationItem[];
}> = ({ response, readiness, isLoading, isReadinessLoading, error, surfaceFocus, topSummary, opsSummary, operationItems }) => {
  const rows = response?.rows ?? EMPTY_PROVIDER_MATRIX_ROWS;
  const summary = response?.summary ?? MATRIX_SUMMARY_DEFAULTS;
  const checks = readiness?.checks ?? EMPTY_READINESS_CHECKS;

  return (
    <TerminalPanel as="section" className="col-span-12">
      <TerminalSectionHeader
        eyebrow="路线图"
        title="数据源优先级路线图"
        action={(
          <div className="flex flex-wrap gap-1.5">
            <TerminalChip variant="neutral">{formatNumber(summary.totalRows, 0)} 条来源契约</TerminalChip>
            <TerminalChip variant="info">{formatNumber(summary.observationOnlyRows, 0)} 条仅观察</TerminalChip>
            <TerminalChip variant="success">{formatNumber(summary.scoreEligibleRows, 0)} 条可计分</TerminalChip>
          </div>
        )}
      />
      <p className="mt-2 text-[11px] leading-5 text-white/42">
        先看哪些缺口真正阻断了产品首屏结论，再按需展开完整数据源矩阵。这里仍保持只读，不触发数据源运行时，不展示密钥、原始 URL、原始载荷或本地路径。
      </p>

      {error ? <ApiErrorAlert error={error} className="mt-4" /> : null}

      {isLoading && !response ? (
        <div className="mt-4">
          <TerminalEmptyState title="正在读取数据源矩阵">保持只读，只请求 `/api/v1/admin/providers/operations-matrix`。</TerminalEmptyState>
        </div>
      ) : null}

      {!isLoading && !error && !rows.length ? (
        <div className="mt-4">
          <TerminalEmptyState title="暂无数据源矩阵行">接口未返回行时，不在前端推断数据源就绪状态或来源权限。</TerminalEmptyState>
        </div>
      ) : null}

      {!isLoading && (rows.length || checks.length) ? (
        <>
          <ProviderSetupChecklistPanel
            rows={rows}
            checks={checks}
            isLoading={isLoading || isReadinessLoading}
            surfaceFocus={surfaceFocus}
            topSummary={topSummary}
            summary={opsSummary}
            operationItems={operationItems}
            readinessStatus={readiness?.readinessStatus}
          />
        </>
      ) : null}

      {!isLoading && rows.length ? (
        <>
          <SourceGapDisclosure rows={rows} />
          <TerminalDisclosure
            data-testid="market-provider-matrix-disclosure"
            title="L4 完整数据源矩阵：来源 / 就绪 / 门槛 / 原因代码（已脱敏）"
            summary={`默认折叠 · ${formatNumber(rows.length, 0)} 行 · ${formatNumber(summary.paidDataLikelyRequiredRows, 0)} 行含付费/配额线索 · 原因代码仅限 L4`}
            className="mt-2 bg-black/10"
          >
            <div className="mb-2 flex items-center justify-between gap-2 rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-[11px] leading-5 text-white/54 sm:hidden">
              <span>左右滑动查看完整矩阵列</span>
              <span className="shrink-0 text-white/38">滚动仅限表格区域</span>
            </div>
            <TerminalDenseTable
              data-testid="market-provider-matrix-table-shell"
              className="-mx-4 overflow-x-auto overscroll-x-contain px-4 [-webkit-overflow-scrolling:touch] sm:mx-0 sm:px-0"
            >
              <table className="min-w-[52rem] table-fixed">
                <thead className="bg-black/20 text-[10px] uppercase tracking-widest text-white/35">
                  <tr className="border-b border-white/5 text-left">
                    <th className="px-3 py-3 font-medium">数据源</th>
                    <th className="px-3 py-3 font-medium">来源</th>
                    <th className="px-3 py-3 font-medium">就绪状态</th>
                    <th className="px-3 py-3 font-medium">门槛</th>
                    <th className="px-3 py-3 font-medium">原因代码</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => {
                    const reasonCodes = matrixReasonCodes(row);
                    return (
                      <tr key={row.providerId} className="border-b border-white/[0.04] align-top">
                        <td className="px-3 py-3">
                          <div className="min-w-0">
                            <p className="truncate text-sm font-semibold text-white">{row.providerName || row.providerId}</p>
                            <p className="mt-1 truncate font-mono text-[11px] text-white/42">{row.providerId}</p>
                          </div>
                        </td>
                        <td className="px-3 py-3">
                          <div className="flex flex-wrap gap-1.5">
                            {row.sourceType ? <TerminalChip variant="neutral">{sanitizeCodeLabel(row.sourceType)}</TerminalChip> : null}
                            {row.sourceTier ? <TerminalChip variant="neutral">{sanitizeCodeLabel(row.sourceTier)}</TerminalChip> : null}
                          </div>
                        </td>
                        <td className="px-3 py-3">
                          <div className="flex flex-wrap gap-1.5">
                            {row.runtimeState ? <TerminalChip variant={matrixStateVariant(row.runtimeState)}>{sanitizeCodeLabel(row.runtimeState)}</TerminalChip> : null}
                            {row.credentialState ? <TerminalChip variant={matrixStateVariant(row.credentialState)}>{sanitizeCodeLabel(row.credentialState)}</TerminalChip> : null}
                            {row.dependencyState ? <TerminalChip variant={matrixStateVariant(row.dependencyState)}>{sanitizeCodeLabel(row.dependencyState)}</TerminalChip> : null}
                          </div>
                        </td>
                        <td className="px-3 py-3">
                          <div className="flex flex-wrap gap-1.5">
                            <TerminalChip variant={matrixCacheRequired(row) ? 'info' : 'neutral'}>
                              {matrixCacheRequired(row) ? 'cache-required' : 'cache-optional'}
                            </TerminalChip>
                            <TerminalChip variant={matrixGateVariant(row.scoreContributionAllowed)}>
                              {matrixGateLabel('score', row.scoreContributionAllowed === true)}
                            </TerminalChip>
                            {typeof row.sourceAuthorityAllowed === 'boolean' ? (
                              <TerminalChip variant={matrixGateVariant(row.sourceAuthorityAllowed)}>
                                {matrixGateLabel('sourceAuthority', row.sourceAuthorityAllowed)}
                              </TerminalChip>
                            ) : null}
                          </div>
                        </td>
                        <td className="px-3 py-3">
                          {reasonCodes.length ? (
                            <div className="flex flex-wrap gap-1.5">
                              {reasonCodes.map((reason) => (
                                <TerminalChip key={`${row.providerId}-${reason}`} variant="caution">{sanitizeCodeLabel(reason)}</TerminalChip>
                              ))}
                            </div>
                          ) : (
                            <p className="text-[11px] text-white/42">暂无数据</p>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </TerminalDenseTable>
          </TerminalDisclosure>
        </>
      ) : null}
    </TerminalPanel>
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
          <table className="min-w-[44rem] table-fixed">
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
  <TerminalPanel as="section" data-testid="market-provider-detail-panel" className="col-span-12 xl:col-span-4">
    <TerminalSectionHeader eyebrow="L3 诊断抽屉" title={item ? providerLabel(item) : '选择数据源'} />
    {item ? (
      <>
        <p className="mt-3 text-[11px] leading-5 text-white/46">
          已通过表格行“查看诊断”打开；行级状态仍保留在左侧表格，这里只展示所选数据源的 bounded 诊断摘要。
        </p>
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
            <p className="text-[10px] uppercase tracking-widest text-white/35">数据源 ID</p>
            <p data-testid="market-provider-detail-provider-id" className="mt-1 max-w-full break-all font-mono text-[11px] text-white/65">{item.provider}</p>
          </TerminalNestedBlock>
          <TerminalNestedBlock className="px-3 py-2">
            <p className="text-[10px] uppercase tracking-widest text-white/35">接口引用</p>
            <p data-testid="market-provider-detail-endpoint" className="mt-1 max-w-full break-words text-[11px] text-white/65">
              已脱敏，仅保留产品面诊断引用
            </p>
          </TerminalNestedBlock>
          <DrillLink drill={item.adminLogDrillThrough} />
        </TerminalDenseList>
      </>
    ) : (
      <div className="mt-4">
        <TerminalEmptyState title="诊断默认收起">先在左侧数据源表格查看行摘要；需要诊断时再点击“查看诊断”。</TerminalEmptyState>
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
                  <TerminalChip variant={statusChipVariant(status)}>{statusLabel(status)}</TerminalChip>
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
                    <p className="mt-1 text-[11px] text-white/42">{rollup.card || rollup.category || '市场数据源'}</p>
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
  matrixSummary: ProviderOperationsMatrixResponse['summary'] | null;
}> = ({ response, selectedItem, matrixSummary }) => {
  const tickflowProjection = readTickflowProjection(response.metadata);
  const paidRows = matrixSummary?.paidDataLikelyRequiredRows ?? 0;
  const missingRows = matrixSummary?.missingProviderRows ?? 0;
  return (
    <TerminalPanel as="section" className="col-span-12">
      <TerminalSectionHeader
        eyebrow="L2 配额 / 成本线索"
        title="配额 / 成本线索与下钻"
        action={(
          <div className="flex flex-wrap gap-1.5">
            <TerminalChip variant={paidRows > 0 ? 'caution' : 'neutral'}>付费线索 {formatNumber(paidRows, 0)}</TerminalChip>
            <TerminalChip variant={missingRows > 0 ? 'caution' : 'neutral'}>缺口 {formatNumber(missingRows, 0)}</TerminalChip>
            <TerminalChip variant={response.limitations.length ? 'caution' : 'neutral'}>限制 {formatNumber(response.limitations.length, 0)}</TerminalChip>
          </div>
        )}
      />
      <p className="mt-2 text-[11px] leading-5 text-white/46">
        这里只汇总既有付费/缺口/限制线索，并保留到 Admin Logs 的下钻入口；不新增配额 API，不扩展原始 provider 载荷。
      </p>
      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-4">
        <TerminalMetric label="可能需付费" value={formatNumber(paidRows, 0)} valueClassName="text-sm" />
        <TerminalMetric label="失败 / 降级" value={formatNumber(response.summary.failureCount + response.summary.fallbackCount + response.summary.staleCount, 0)} valueClassName="text-sm" />
        <TerminalMetric label="限制代码" value={formatNumber(response.limitations.length, 0)} valueClassName="text-sm" />
        <TerminalMetric label="追踪标识" value={selectedItem ? providerLabel(selectedItem) : 'Admin Logs'} valueClassName="truncate text-sm" />
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <DrillLink drill={response.adminLogDrillThrough} />
        {selectedItem ? <DrillLink drill={selectedItem.adminLogDrillThrough} /> : null}
      </div>
      {tickflowProjection ? <div className="mt-4"><TickflowEntitlementRow projection={tickflowProjection} /></div> : null}
      <div className="mt-4 flex flex-wrap gap-2">
        {response.limitations.length ? response.limitations.map((limitation) => (
          <TerminalChip key={limitation} variant="caution">{limitationLabel(limitation)}</TerminalChip>
        )) : <TerminalChip variant="neutral">暂无限制</TerminalChip>}
      </div>
      <TerminalDisclosure
        title="L4 已脱敏细节：限制代码 / 快照摘要 / 追踪标识"
        summary="默认折叠 · 原始代码与追踪标识只保留在 L4 摘要"
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
  const groupedChecks: Array<(typeof READINESS_DIAGNOSTIC_GROUPS)[number] & { items: MarketDataReadinessCheck[] }> = [];
  for (const group of READINESS_DIAGNOSTIC_GROUPS) {
    const items = checks
      .filter((check) => readinessDiagnosticGroupId(check) === group.id)
      .sort((left, right) => left.severity.localeCompare(right.severity) || left.status.localeCompare(right.status) || readinessCheckName(left).localeCompare(readinessCheckName(right)));
    if (!items.length) continue;
    groupedChecks.push({ ...group, items });
  }

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
            <div className="min-w-0 flex-1">
              <Input
                aria-label="代表符号"
                label="代表符号"
                labelClassName="mb-1.5 block text-[11px] font-normal text-white/42"
                type="text"
                value={symbolInput}
                onChange={(event) => onSymbolInputChange(event.target.value)}
                placeholder="AAPL, SPY, BTC-USD"
                className="h-10 px-3 text-white placeholder:text-white/28"
              />
            </div>
            <TerminalButton variant="secondary" className="min-h-10 md:min-w-28" onClick={onSymbolSubmit} disabled={isLoading}>
              更新样本
            </TerminalButton>
          </div>
          <p className="mt-2 text-[11px] leading-5 text-white/42">只发送可选代表符号参数到 `/api/v1/market/data-readiness`，不触发数据源运行时，也不读取密钥值。</p>
        </TerminalNestedBlock>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <TerminalMetric label="只读诊断" value={data?.diagnosticOnly === false ? '否' : '是'} valueClassName="text-sm" />
          <TerminalMetric label="运行时调用" value={data?.providerRuntimeCalled ? '已触发' : '未触发'} valueClassName="text-sm" />
          <TerminalMetric label="网络调用" value={data?.networkCallsEnabled ? '已开启' : '关闭'} valueClassName="text-sm" />
        </div>
      </div>

      <TerminalNotice variant="info" className="mt-4">
        这个面板只解释本地就绪诊断与缺口来源，不改写 Market Overview、Liquidity Monitor 或 Rotation Radar 的既有结论。
      </TerminalNotice>

      {error ? <ApiErrorAlert error={error} className="mt-4" /> : null}

      {isLoading && !data ? (
        <div className="mt-4">
          <TerminalEmptyState title="正在读取就绪诊断">保持只读；不会触发外部数据源调用。</TerminalEmptyState>
        </div>
      ) : null}

      {!isLoading && !error ? (
        <div className="mt-4 space-y-2">
          {!groupedChecks.length ? (
            <TerminalEmptyState title="暂无就绪检查项">接口未返回检查项时，不在前端推断环境健康度。</TerminalEmptyState>
          ) : groupedChecks.map((group) => {
            const hasBlockingOrWarning = group.items.some((check) => check.severity === 'error' || check.severity === 'warning' || check.status === 'missing' || check.status === 'misconfigured');
            return (
              <TerminalDisclosure
                key={group.id}
                data-testid={`market-provider-readiness-group-${group.id}`}
                title={group.title}
                summary={`${formatNumber(group.items.length, 0)} 项 · ${hasBlockingOrWarning ? '默认展开' : '默认折叠'} · ${group.description}`}
                defaultOpen={hasBlockingOrWarning}
                className="bg-black/10"
              >
              <TerminalDenseList>
                {group.items.map((check) => {
                  const facts = summarizeReadinessFacts(check);
                  return (
                    <TerminalNestedBlock key={check.id} className="px-3 py-2.5">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="text-[10px] font-semibold uppercase tracking-widest text-white/34">就绪检查</p>
                          <p className="mt-1 text-sm font-semibold text-white">{readinessCheckName(check)}</p>
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          <TerminalChip variant={readinessStatusVariant(check.status)}>{readinessStatusLabel(check.status)}</TerminalChip>
                          <TerminalChip variant={readinessSeverityVariant(check.severity)}>{readinessSeverityLabel(check.severity)}</TerminalChip>
                          {typeof check.secretConfigured === 'boolean' ? (
                            <TerminalChip variant={check.secretConfigured ? 'success' : 'caution'}>
                              {check.secretConfigured ? '已配置' : '未配置'}
                            </TerminalChip>
                          ) : null}
                        </div>
                      </div>
                      <p className="mt-2 text-[11px] leading-5 text-white/62">{readinessCheckMessage(check)}</p>
                      <p className="mt-1 text-[11px] leading-5 text-white/54">下一步：{readinessCheckGuidance(check)}</p>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {resolveChecklistReadinessSurfaces(check).map((surface) => (
                          <TerminalChip key={`${check.id}-${surface}`} variant="neutral">{surface}</TerminalChip>
                        ))}
                      </div>
                      <TerminalDisclosure
                        title="L4 已脱敏样本差异：诊断 ID / 影响面 / 样本缺口"
                        summary="默认折叠 · 原始诊断 ID、影响面与样本差异摘要只在 L4 展开"
                        className="mt-2 bg-black/10"
                      >
                        <div className="space-y-2 text-[11px] leading-5 text-white/50">
                          <p><span className="text-white/34">诊断 ID：</span><span className="font-mono">{sanitizeCodeLabel(check.id)}</span></p>
                          <div className="flex flex-wrap gap-1.5">
                            {check.affectsSurfaces.map((surface) => (
                              <TerminalChip key={`${check.id}-${surface}`} variant="neutral">{surfaceLabel(surface)}</TerminalChip>
                            ))}
                          </div>
                          {facts.length ? <p className="font-mono text-white/42">{facts.join(' · ')}</p> : null}
                        </div>
                      </TerminalDisclosure>
                    </TerminalNestedBlock>
                  );
                })}
              </TerminalDenseList>
              </TerminalDisclosure>
            );
          })}
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
  const surfaceFocus = productSetupSurfaceFromCurrentQuery();
  const [response, setResponse] = useState<MarketProviderOperationsResponse | null>(null);
  const [matrixResponse, setMatrixResponse] = useState<ProviderOperationsMatrixResponse | null>(null);
  const [readiness, setReadiness] = useState<MarketDataReadinessResponse | null>(null);
  const [selectedProviderKey, setSelectedProviderKey] = useState<string | null>(null);
  const [readinessSymbolsInput, setReadinessSymbolsInput] = useState('');
  const [submittedReadinessSymbols, setSubmittedReadinessSymbols] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isMatrixLoading, setIsMatrixLoading] = useState(true);
  const [isReadinessLoading, setIsReadinessLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [matrixError, setMatrixError] = useState<ParsedApiError | null>(null);
  const [readinessError, setReadinessError] = useState<ParsedApiError | null>(null);

  useEffect(() => {
    document.title = language === 'en' ? 'Provider Ops - WolfyStock' : '数据源运维 - WolfyStock';
  }, [language]);

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
    marketProviderOperationsApi.getOperationsMatrix()
      .then((payload) => {
        if (!cancelled) setMatrixResponse(payload);
      })
      .catch((apiError) => {
        if (!cancelled) {
          const parsed = getParsedApiError(apiError);
          setMatrixError({ ...parsed, title: '读取 provider operations matrix 失败' });
        }
      })
      .finally(() => {
        if (!cancelled) setIsMatrixLoading(false);
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
          setReadinessError({ ...parsed, title: '读取本地行情就绪诊断失败' });
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
  const matrixRows = matrixResponse?.rows ?? EMPTY_PROVIDER_MATRIX_ROWS;
  const readinessChecks = readiness?.checks ?? EMPTY_READINESS_CHECKS;
  const cacheStates = response?.cacheStates ?? EMPTY_PROVIDER_CACHE_STATES;
  const eventRollups = response?.eventRollups ?? EMPTY_PROVIDER_EVENT_ROLLUPS;
  const summary = normalizeSummary(response?.summary ?? SUMMARY_DEFAULTS);
  const degradedCount = summary.fallbackCount + summary.partialCount + summary.unavailableCount + summary.errorCount + summary.failureCount;
  const preferredProvider = selectPreferredProvider(items);

  const effectiveSelectedProviderKey = selectedProviderKey && items.some((item) => providerKey(item) === selectedProviderKey)
    ? selectedProviderKey
    : null;
  const selectedItem = items.find((item) => providerKey(item) === effectiveSelectedProviderKey) || null;
  const drillContextItem = selectedItem || preferredProvider;

  const withReason = eventRollups.find((rollup) => rollup.topReasons.length) || null;
  const withItemError = items.find((item) => item.errorSummary || item.warning) || null;
  const topException = withReason ? sanitizeOperatorText(withReason.topReasons[0]) : withItemError ? lastFailureLabel(withItemError) : '暂无数据';

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

  const operatorMetrics = [
    { label: '数据源健康', value: healthValue, subvalue: totalItems > 0 ? `共 ${formatNumber(totalItems, 0)} 个数据源` : '暂无 provider 快照' },
    { label: '熔断状态', value: circuitValue, subvalue: degradedCount > 0 ? '优先核对降级与失败路径' : '当前未见降级聚合' },
    { label: '失败率', value: safeRatio(summary.failureCount, summary.eventCount), subvalue: summary.eventCount > 0 ? `事件 ${formatNumber(summary.eventCount, 0)}` : '待统计' },
    { label: '缓存状态', value: cacheValue, subvalue: cacheStates.length > 0 ? `快照 ${formatNumber(cacheStates.length, 0)}` : '暂无缓存快照' },
    { label: '最近异常', value: topException, subvalue: eventRollups.length > 0 ? '保留异常可见性，但不暴露敏感内容' : '窗口内暂无异常' },
  ];

  const topSummary = buildProviderOpsTopSummary(items, matrixRows, readinessChecks);
  const actionQueueItems = buildProviderActionQueue(items, matrixRows, readinessChecks);
  const l0TrustState: AdminOpsTrustState = error && !response
    ? 'blocked'
    : isLoading && !response
      ? 'unknown'
      : degradedCount > 0 || readiness?.readinessStatus === 'partial'
        ? 'degraded'
        : summary.totalItems > 0
          ? 'healthy'
          : 'observe';
  const l0Impact = topSummary.affectedSurfaces.length
    ? `${formatNumber(degradedCount, 0)} 个降级信号，影响 ${formatReadableList(topSummary.affectedSurfaces, '影响面待汇总')}`
    : (degradedCount > 0 ? `${formatNumber(degradedCount, 0)} 个降级信号待核对` : '当前未见跨页面影响汇总');
  const l0RecommendedAction = topSummary.missingSources.length > 0
    ? '先看来源缺口，再核对本地就绪诊断。'
    : degradedCount > 0
      ? '先看失败率、熔断与缓存，再下钻最近异常。'
      : '保持只读观察，按需切换影响面。';

  return (
    <div data-testid="market-provider-operations-page" className="market-provider-operations-page flex min-h-0 min-w-0 w-full flex-1 flex-col overflow-x-hidden overflow-y-auto no-scrollbar text-white">
      <TerminalPageShell className="min-w-0 overflow-x-hidden py-5 md:py-6">
        <TerminalPanel as="section" className="relative overflow-hidden">
          <TerminalPageHeading
            eyebrow="数据源维护"
            title="数据源维护路线图"
            action={<ReadOnlyBadges response={response} />}
          />
          <p className="mt-3 max-w-4xl text-sm leading-6 text-white/54">
            {isLoading
              ? '正在读取数据源维护快照'
              : `先看路线图与阻断项，再按需下钻健康、熔断、失败率与缓存。生成 ${formatDisplayDate(response?.generatedAt, '待统计')} · 窗口 ${response?.window?.key || '24h'} · 只读快照`}
          </p>
          <AdminOpsL0OverviewStrip
            dataTestId="market-provider-l0-overview-strip"
            className="mt-5"
            systemTrustState={l0TrustState}
            impact={l0Impact}
            recommendedAction={l0RecommendedAction}
            evidenceRef="路线图 / 本地行情就绪诊断 / Admin Logs"
            lastUpdated={formatDisplayDate(response?.generatedAt, '待统计')}
          />
          <AdminDrillThroughStrip
            className="mt-4"
            items={[
              {
                label: '查看相关日志',
                target: 'logs',
                evidenceType: '数据源症状',
                reason: '从当前窗口回看数据源失败、备用与缓存事件。',
                params: { since: response?.window?.key || '24h', query: 'market provider' },
              },
              {
                label: '查看熔断与配额',
                target: 'providerCircuits',
                evidenceType: '数据源名称',
                reason: '继续核对熔断、配额拒绝与探测事件。',
                params: { provider: drillContextItem?.provider || response?.eventRollups?.[0]?.provider || '', since: response?.window?.key || '24h' },
              },
              {
                label: '查看成本观测',
                target: 'cost',
                evidenceType: '数据源成本窗口',
                reason: '确认数据源成本、缓存命中与重复调用线索。',
                params: { area: 'provider', window: response?.window?.key || '24h' },
              },
              {
                label: '查看证据工作流',
                target: 'evidence',
                evidenceType: 'sanitized evidence ref',
                reason: '核对离线证据包、runbook 与 schema 边界。',
                params: { ref: 'provider_bundle' },
                hash: 'schema-ref',
              },
            ]}
          />
          <ProviderOpsTopSummary data={topSummary} isLoading={isLoading || isMatrixLoading || isReadinessLoading} />
          <ProviderOpsActionQueue items={actionQueueItems} isLoading={isLoading || isMatrixLoading || isReadinessLoading} />
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
          前端只读取现有运维快照，不触发数据源请求、不改变缓存、不改变数据源排序，也不隐藏真实失败。
        </TerminalNotice>

        {isLoading && !response && !error ? <LoadingOperationsState /> : null}
        {error && !response && !isLoading ? <EmptyErrorState /> : null}
        {!isLoading ? (
          <TerminalGrid>
            <AdminOpsSectionHeading
              dataTestId="market-provider-section-ops-status"
              eyebrow="L1 / 数据源就绪"
              title="数据源就绪与运维状态"
              description="先看当前数据源状态、熔断、缓存和最近异常，再决定是否需要下钻到矩阵或 Admin Logs。"
              action={<TerminalChip variant="neutral">{formatNumber(items.length, 0)} 个数据源快照</TerminalChip>}
              className={ADMIN_SECTION_HEADING_CLASSNAME}
            />
            {response ? (
              <>
                <ProviderOperationsTable items={items} selectedKey={effectiveSelectedProviderKey} onSelect={setSelectedProviderKey} />
                <ProviderDetailsPanel item={selectedItem} />
              </>
            ) : null}
            <AdminOpsSectionHeading
              dataTestId="market-provider-section-matrix"
              eyebrow="L2 / 运维矩阵"
              title="来源缺口、配置清单与完整矩阵"
              description="这一组只重排既有来源缺口、配置动作和完整矩阵，不改变评分、fallback、数据源顺序或就绪语义。"
              action={<TerminalChip variant="info">{formatNumber(matrixRows.length, 0)} 条矩阵行</TerminalChip>}
              className={ADMIN_SECTION_HEADING_CLASSNAME}
            />
            <ProviderOperationsMatrixPanel
              response={matrixResponse}
              readiness={readiness}
              isLoading={isMatrixLoading}
              isReadinessLoading={isReadinessLoading}
              error={matrixError}
              surfaceFocus={surfaceFocus}
              topSummary={topSummary}
              opsSummary={summary}
              operationItems={items}
            />
            <AdminOpsSectionHeading
              dataTestId="market-provider-section-readiness"
              eyebrow="L2 / 本地就绪"
              title="本地数据就绪与样本诊断"
              description="继续把本地行情只读诊断放在独立分组中，明确它解释的是环境/样本覆盖，而不是数据源运行时行为。"
              action={<TerminalChip variant={readiness?.readinessStatus === 'ready' ? 'success' : readiness?.readinessStatus === 'partial' ? 'caution' : 'neutral'}>{readiness ? readinessStatusLabel(readiness.readinessStatus) : '待读取'}</TerminalChip>}
              className={ADMIN_SECTION_HEADING_CLASSNAME}
            />
            <MarketDataReadinessPanel
              data={readiness}
              isLoading={isReadinessLoading}
              error={readinessError}
              symbolInput={readinessSymbolsInput}
              onSymbolInputChange={setReadinessSymbolsInput}
              onSymbolSubmit={submitReadinessSymbols}
            />
            <AdminOpsSectionHeading
              dataTestId="market-provider-section-cost"
              eyebrow="L2 / 配额与成本"
              title="配额 / 成本线索与下钻"
              description="保留既有失败、缓存、限制代码和 Admin Logs 下钻入口，把付费/配额线索集中到一组里展示。"
              action={<TerminalChip variant="caution">{formatNumber((matrixResponse?.summary?.paidDataLikelyRequiredRows ?? 0) + (response?.limitations.length ?? 0), 0)} 个线索</TerminalChip>}
              className={ADMIN_SECTION_HEADING_CLASSNAME}
            />
            {response ? (
              <>
                <EventRollupsPanel eventRollups={eventRollups} />
                <CacheStatesPanel cacheStates={cacheStates} />
                <DiagnosticsPanel response={response} selectedItem={selectedItem} matrixSummary={matrixResponse?.summary ?? null} />
              </>
            ) : null}
          </TerminalGrid>
        ) : null}
      </TerminalPageShell>
      <span className="sr-only">{language === 'zh' ? '市场数据源运维只读页面' : 'Market provider operations read-only page'}</span>
    </div>
  );
};

export default MarketProviderOperationsPage;
