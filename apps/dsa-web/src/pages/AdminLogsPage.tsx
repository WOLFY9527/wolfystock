import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { adminLogsApi, type AdminLogCleanupResponse, type AdminLogHealthSummary, type AdminLogStorageSummary, type BusinessEvent, type BusinessEventDetail, type BusinessEventListResponse, type ExecutionLogSessionDetail, type ExecutionLogSessionListResponse, type ExecutionLogSessionSummary, type ExecutionStep } from '../api/adminLogs';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import { ApiErrorAlert, Drawer } from '../components/common';
import {
  TerminalButton,
  TerminalChip,
  TerminalDenseList,
  TerminalDenseTable,
  TerminalEmptyState,
  TerminalMetric,
  TerminalNestedBlock,
  TerminalNotice,
  TerminalPageShell,
  TerminalPanel,
  TerminalSectionHeader,
} from '../components/terminal';
import { getStatusLabel, normalizeStatus, type UnifiedStatus } from '../components/ui/StatusBadge';
import { useI18n } from '../contexts/UiLanguageContext';
import { describeAdminLogLevel } from '../utils/displayStatus';
import { formatDateTime as formatDateTimeValue, formatDurationMs } from '../utils/format';

type AdminLogsLanguage = 'zh' | 'en';
type OperationType = 'single_stock_analysis' | 'market_scan' | 'backtest' | 'system_operation' | 'other';
type LogLevel = 'DEBUG' | 'INFO' | 'NOTICE' | 'WARNING' | 'ERROR' | 'CRITICAL';
type LevelFilter = 'all' | 'warning_plus' | 'error_plus' | LogLevel;
type LogCategory = 'system' | 'auth' | 'market' | 'cache' | 'data_source' | 'analysis' | 'scanner' | 'backtest' | 'trading' | 'portfolio' | 'scheduler' | 'notification' | 'api' | 'security';
type LogsTab = 'business' | 'analysis' | 'scanner' | 'backtest' | 'data_source' | 'security' | 'raw';
type EventSeverity = 'success' | 'degraded' | 'failed';

const LEVEL_FILTER_OPTIONS: LevelFilter[] = ['all', 'warning_plus', 'error_plus', 'DEBUG', 'INFO', 'NOTICE', 'WARNING', 'ERROR', 'CRITICAL'];
const CATEGORY_OPTIONS: LogCategory[] = ['system', 'auth', 'market', 'cache', 'data_source', 'analysis', 'scanner', 'backtest', 'trading', 'portfolio', 'scheduler', 'notification', 'api', 'security'];
const SINCE_OPTIONS = ['15m', '1h', '24h', '7d'] as const;
const STATUS_FILTER_OPTIONS = ['all', 'success', 'partial', 'failed', 'skipped', 'running', 'unknown', 'cancelled'] as const;
const PAGE_SIZE = 20;
type TerminalChipVariant = 'neutral' | 'success' | 'caution' | 'danger' | 'info';

function statusChipVariant(status: UnifiedStatus): TerminalChipVariant {
  if (status === 'success') return 'success';
  if (status === 'failed' || status === 'error' || status === 'cancelled') return 'danger';
  if (status === 'partial' || status === 'warning') return 'caution';
  if (status === 'running' || status === 'info') return 'info';
  return 'neutral';
}

function levelChipVariant(level: LogLevel): TerminalChipVariant {
  if (level === 'NOTICE') return 'info';
  if (level === 'WARNING') return 'caution';
  if (level === 'ERROR' || level === 'CRITICAL') return 'danger';
  return 'neutral';
}

function StatusChip({
  status,
  locale,
  className = '',
}: {
  status: UnifiedStatus;
  locale: AdminLogsLanguage;
  className?: string;
}) {
  const extraClassName = className ? ` ${className}` : '';
  return (
    <TerminalChip
      variant={statusChipVariant(status)}
      className={`justify-center font-semibold${extraClassName}`}
      data-status={status}
    >
      {statusLabel(status, locale)}
    </TerminalChip>
  );
}

function AdminLogLevelPill({
  value,
  locale,
  className = 'w-fit justify-center font-semibold',
}: {
  value: unknown;
  locale: AdminLogsLanguage;
  className?: string;
}) {
  const level = normalizeLogLevel(String(value || ''));
  const descriptor = describeAdminLogLevel(level, { language: locale });
  return (
    <TerminalChip variant={levelChipVariant(level)} className={className}>
      {descriptor.label}
    </TerminalChip>
  );
}

const MOCK_WOLFY_LOG_DETAILS: ExecutionLogSessionDetail[] = [
  {
    sessionId: 'mock-analysis-tsla',
    code: 'TSLA',
    name: 'TSLA analysis',
    overallStatus: 'partial_success',
    truthLevel: 'mock',
    startedAt: '2026-04-29T20:40:00',
    endedAt: '2026-04-29T20:42:12',
    readableSummary: {
      actorDisplay: 'admin',
      actorRole: 'admin',
      sessionKind: 'user_activity',
      subsystem: 'analysis',
      operationCategory: 'single_stock_analysis',
      operationType: '单股票分析',
      operationTarget: 'TSLA',
      operationStatus: '部分失败',
      keyMetric: 'LLM fallback used',
      finalAiModel: 'alpaca',
      aiAttemptsCount: 2,
      aiFallbackUsed: true,
      dataFallbackUsed: true,
      topFailureReason: '高负载 / Yahoo 超时',
      summaryParagraph: '主模型失败后回退到 alpaca，Finnhub 数据成功，Yahoo 数据超时，最终报告部分生成。',
    },
    operationDetail: {
      operationCategory: 'single_stock_analysis',
      operationType: '单股票分析',
      target: 'TSLA',
      status: '部分失败',
      keyMetric: 'LLM fallback used',
      aiCalls: [
        {
          model: 'deepseek-v4-pro',
          version: '1.0',
          request: { temperature: 0.2, max_tokens: 3200, symbol: 'TSLA' },
          response: { error: 'rate_limited' },
          status: '失败',
          reason: '高负载',
          fallback: '回退使用 alpaca',
        },
        {
          model: 'alpaca',
          version: '2026-04',
          request: { temperature: 0.1, symbol: 'TSLA' },
          response: { decision: 'hold', confidence: 0.61 },
          status: '成功',
          fallback: '备用模型完成',
        },
      ],
      dataSourceCalls: [
        {
          api: 'Finnhub',
          request: { symbol: 'TSLA', modules: ['quote', 'news'] },
          response: { quote: 'ok', newsCount: 8 },
          status: '成功',
        },
        {
          api: 'Yahoo',
          request: { symbol: 'TSLA', range: '6mo' },
          response: { error: 'timeout' },
          status: '失败',
          reason: '超时',
        },
      ],
      timeline: [
        { timestamp: '2026-04-29T20:40:00', label: '单股票分析启动', category: 'analysis', status: '成功' },
        { timestamp: '2026-04-29T20:40:18', label: 'deepseek-v4-pro 高负载失败', category: 'llm', status: '失败' },
        { timestamp: '2026-04-29T20:41:03', label: 'alpaca 回退完成', category: 'llm', status: '成功' },
      ],
      diagnostics: [
        { severity: 'warning', message: '回退到备用模型', source: 'LLM Router' },
        { severity: 'error', message: 'Yahoo 超时', source: 'Yahoo' },
      ],
    },
    events: [],
  },
  {
    sessionId: 'mock-scan-us-preopen',
    name: 'US pre-open scanner',
    overallStatus: 'success',
    truthLevel: 'mock',
    startedAt: '2026-04-29T19:20:00',
    endedAt: '2026-04-29T19:22:44',
    readableSummary: {
      actorDisplay: 'admin',
      actorRole: 'admin',
      sessionKind: 'admin_action',
      subsystem: 'scanner',
      operationCategory: 'market_scan',
      operationType: '市场扫描',
      operationTarget: 'US pre-open',
      operationStatus: '成功',
      keyMetric: 'Shortlist 12',
      scannerShortlistCount: 12,
      scannerProvidersUsed: ['alpaca', 'finnhub'],
      summaryParagraph: '扫描完成，数据源全部成功，输出 12 个候选标的。',
    },
    operationDetail: {
      operationCategory: 'market_scan',
      operationType: '市场扫描',
      target: 'US pre-open',
      status: '成功',
      keyMetric: 'Shortlist 12',
      aiCalls: [],
      dataSourceCalls: [
        { api: 'Alpaca', request: { market: 'us', profile: 'preopen' }, response: { symbols: 450 }, status: '成功' },
        { api: 'Finnhub', request: { market: 'us', modules: ['news'] }, response: { newsCount: 72 }, status: '成功' },
      ],
      timeline: [
        { timestamp: '2026-04-29T19:20:00', label: '扫描启动', category: 'scanner', status: '成功' },
        { timestamp: '2026-04-29T19:22:44', label: '候选名单生成', category: 'scanner', status: '成功' },
      ],
      diagnostics: [],
    },
    events: [],
  },
  {
    sessionId: 'mock-backtest-ma-cross',
    name: 'MA crossover backtest',
    overallStatus: 'failed',
    truthLevel: 'mock',
    startedAt: '2026-04-29T18:05:00',
    endedAt: '2026-04-29T18:05:19',
    readableSummary: {
      actorDisplay: 'admin',
      actorRole: 'admin',
      sessionKind: 'user_activity',
      subsystem: 'analysis',
      operationCategory: 'backtest',
      operationType: '回测',
      operationTarget: 'MA crossover',
      operationStatus: '失败',
      keyMetric: 'Data gap',
      topFailureReason: '历史数据不足',
    },
    operationDetail: {
      operationCategory: 'backtest',
      operationType: '回测',
      target: 'MA crossover',
      status: '失败',
      keyMetric: 'Data gap',
      aiCalls: [],
      dataSourceCalls: [
        { api: 'Local Parquet', request: { symbol: 'MSFT', range: '5y' }, response: { rows: 0 }, status: '失败', reason: '历史数据不足' },
      ],
      timeline: [
        { timestamp: '2026-04-29T18:05:00', label: '回测启动', category: 'backtest', status: '成功' },
        { timestamp: '2026-04-29T18:05:19', label: '历史数据不足，任务终止', category: 'data', status: '失败' },
      ],
      diagnostics: [
        { severity: 'error', message: 'Local parquet returned no rows', source: 'Backtest Engine' },
      ],
    },
    events: [],
  },
  {
    sessionId: 'mock-system-login-admin',
    name: 'Admin login',
    overallStatus: 'success',
    truthLevel: 'mock',
    startedAt: '2026-04-29T20:59:00',
    endedAt: '2026-04-29T20:59:02',
    readableSummary: {
      actorDisplay: 'admin',
      actorRole: 'admin',
      sessionKind: 'system_event',
      subsystem: 'auth',
      operationCategory: 'system_operation',
      operationType: '系统操作',
      operationTarget: '登录',
      operationStatus: '成功',
      keyMetric: '管理员登录',
      summaryParagraph: '管理员 admin 登录成功，系统记录认证事件。',
    },
    operationDetail: {
      operationCategory: 'system_operation',
      operationType: '系统操作',
      target: '登录',
      status: '成功',
      keyMetric: '管理员登录',
      systemOperation: {
        action: 'login',
        actor: 'admin',
        time: '2026-04-29T20:59:00',
        status: '成功',
        reason: '',
      },
      aiCalls: [],
      dataSourceCalls: [],
      systemFallbacks: [],
      finalResult: '成功',
      timeline: [
        { timestamp: '2026-04-29T20:59:00', label: '管理员登录成功', category: 'auth', status: '成功' },
      ],
      diagnostics: [],
    },
    events: [],
  },
];

function text(value: unknown, fallback = '--'): string {
  const normalized = String(value ?? '').trim();
  return normalized || fallback;
}

function normalizeOperationType(summary?: ExecutionLogSessionSummary['readableSummary']): OperationType {
  const raw = `${summary?.operationCategory || ''} ${summary?.operationType || ''} ${summary?.subsystem || ''}`.toLowerCase();
  if (raw.includes('backtest') || raw.includes('回测')) return 'backtest';
  if (raw.includes('market_scan') || raw.includes('scanner') || raw.includes('扫描')) return 'market_scan';
  if (raw.includes('system_operation') || raw.includes('system_event') || raw.includes('auth') || raw.includes('系统操作') || raw.includes('登录') || raw.includes('注册') || raw.includes('修改密码') || raw.includes('权限')) return 'system_operation';
  if (raw.includes('single_stock') || raw.includes('单股票') || raw.includes('analysis')) return 'single_stock_analysis';
  return 'other';
}

function operationIcon(type: OperationType): string {
  if (type === 'single_stock_analysis') return 'A';
  if (type === 'market_scan') return 'S';
  if (type === 'backtest') return 'B';
  if (type === 'system_operation') return 'O';
  return 'L';
}

function operationLabel(type: OperationType, locale: AdminLogsLanguage): string {
  const labels: Record<OperationType, { zh: string; en: string }> = {
    single_stock_analysis: { zh: '单股票分析', en: 'Single stock analysis' },
    market_scan: { zh: '市场扫描', en: 'Market scan' },
    backtest: { zh: '回测', en: 'Backtest' },
    system_operation: { zh: '系统操作', en: 'System operation' },
    other: { zh: '其他', en: 'Other' },
  };
  return labels[type][locale];
}

function statusLabel(status: UnifiedStatus, locale: AdminLogsLanguage): string {
  if (locale === 'zh') return getStatusLabel(status);
  const labels: Record<UnifiedStatus, string> = {
    success: 'Success',
    failed: 'Failed',
    error: 'Failed',
    running: 'Running',
    pending: 'Pending',
    partial: 'Partial failure',
    skipped: 'Skipped',
    unknown: 'Unknown',
    cancelled: 'Cancelled',
    warning: 'Warning',
    info: 'Info',
    disabled: 'Disabled',
  };
  return labels[status];
}

function normalizeLogLevel(value?: string | null): LogLevel {
  const normalized = String(value || '').trim().toUpperCase();
  if (['DEBUG', 'INFO', 'NOTICE', 'WARNING', 'ERROR', 'CRITICAL'].includes(normalized)) return normalized as LogLevel;
  return 'INFO';
}

function levelFilterLabel(value: LevelFilter, locale: AdminLogsLanguage): string {
  const labels: Record<LevelFilter, { zh: string; en: string }> = {
    all: { zh: '全部', en: 'All' },
    warning_plus: { zh: 'WARNING+', en: 'WARNING+' },
    error_plus: { zh: 'ERROR+', en: 'ERROR+' },
    DEBUG: { zh: 'DEBUG', en: 'DEBUG' },
    INFO: { zh: 'INFO', en: 'INFO' },
    NOTICE: { zh: 'NOTICE', en: 'NOTICE' },
    WARNING: { zh: 'WARNING', en: 'WARNING' },
    ERROR: { zh: 'ERROR', en: 'ERROR' },
    CRITICAL: { zh: 'CRITICAL', en: 'CRITICAL' },
  };
  return labels[value][locale];
}

function categoryLabel(value: string | null | undefined, locale: AdminLogsLanguage): string {
  const key = String(value || 'system').trim();
  const labels: Record<string, { zh: string; en: string }> = {
    system: { zh: '系统', en: 'system' },
    auth: { zh: '认证', en: 'auth' },
    market: { zh: '市场', en: 'market' },
    cache: { zh: '缓存', en: 'cache' },
    data_source: { zh: '数据源', en: 'data_source' },
    analysis: { zh: '分析', en: 'analysis' },
    scanner: { zh: '扫描器', en: 'scanner' },
    backtest: { zh: '回测', en: 'backtest' },
    trading: { zh: '交易', en: 'trading' },
    portfolio: { zh: '组合', en: 'portfolio' },
    scheduler: { zh: '调度', en: 'scheduler' },
    notification: { zh: '通知', en: 'notification' },
    api: { zh: 'API', en: 'api' },
    security: { zh: '安全', en: 'security' },
  };
  return (labels[key] || { zh: key, en: key })[locale];
}

function sinceLabel(value: string, locale: AdminLogsLanguage): string {
  const labels: Record<string, { zh: string; en: string }> = {
    '15m': { zh: '最近 15 分钟', en: 'Last 15 minutes' },
    '1h': { zh: '最近 1 小时', en: 'Last 1 hour' },
    '24h': { zh: '最近 24 小时', en: 'Last 24 hours' },
    '7d': { zh: '最近 7 天', en: 'Last 7 days' },
  };
  return (labels[value] || labels['24h'])[locale];
}

function asRecordList(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => !!item && typeof item === 'object' && !Array.isArray(item)) : [];
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function formatDateTime(value: unknown, locale: AdminLogsLanguage): string {
  void locale;
  return formatDateTimeValue(value);
}

function formatDuration(value: unknown): string {
  return formatDurationMs(value);
}

function formatStorageBytes(value: unknown): string {
  const bytes = Number(value);
  if (!Number.isFinite(bytes) || bytes <= 0) return '--';
  if (bytes >= 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${Math.round(bytes)} B`;
}

function storageBytes(summary: AdminLogStorageSummary | null): number | null {
  if (!summary?.storageSizeAvailable) return null;
  const value = typeof summary.sizeBytes === 'number' ? summary.sizeBytes : (typeof summary.storageSizeBytes === 'number' ? summary.storageSizeBytes : summary.estimatedStorageBytes);
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function storageMeasurementLabel(summary: AdminLogStorageSummary | null, locale: AdminLogsLanguage): string {
  const scope = String(summary?.measurementScope || '').trim();
  if (scope === 'postgres_tables') return locale === 'zh' ? 'PostgreSQL 表容量' : 'PostgreSQL table size';
  if (scope === 'sqlite_database_file') return locale === 'zh' ? 'SQLite 数据库文件' : 'SQLite database file';
  return locale === 'zh' ? '容量来源不可用' : 'Measurement unavailable';
}

function storageUnavailableReason(summary: AdminLogStorageSummary | null, locale: AdminLogsLanguage): string {
  const raw = String(summary?.measurementReason || '').trim();
  if (!raw) return locale === 'zh' ? '未返回容量测量原因' : 'No measurement reason returned';
  if (locale !== 'zh') return raw;
  if (/database path unavailable/i.test(raw)) return '数据库路径不可用';
  if (/permission denied/i.test(raw)) return '没有权限读取容量';
  if (/unsupported dialect/i.test(raw)) return '当前数据库类型暂不支持表级容量';
  if (/database engine unavailable/i.test(raw)) return '数据库引擎不可用';
  return raw;
}

function clampPercent(value: unknown): number {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 0;
  return Math.max(0, Math.min(100, numeric));
}

function storageStatusLabel(value: string | undefined, locale: AdminLogsLanguage): string {
  const normalized = String(value || 'ok').toLowerCase();
  if (normalized === 'critical') return locale === 'zh' ? '严重' : 'Critical';
  if (normalized === 'warning') return locale === 'zh' ? '警告' : 'Warning';
  return locale === 'zh' ? 'OK' : 'OK';
}

function storageStatusTone(value: string | undefined): string {
  const normalized = String(value || 'ok').toLowerCase();
  if (normalized === 'critical') return 'border-rose-300/35 bg-rose-500/14 text-rose-100';
  if (normalized === 'warning') return 'border-amber-300/30 bg-amber-400/12 text-amber-100';
  return 'border-emerald-300/25 bg-emerald-400/10 text-emerald-100';
}

function statusFilterLabel(value: (typeof STATUS_FILTER_OPTIONS)[number], locale: AdminLogsLanguage): string {
  const labels: Record<(typeof STATUS_FILTER_OPTIONS)[number], { zh: string; en: string }> = {
    all: { zh: '全部状态', en: 'All status' },
    success: { zh: '成功', en: 'Success' },
    partial: { zh: '部分失败', en: 'Partial failure' },
    failed: { zh: '失败', en: 'Failed' },
    skipped: { zh: '跳过', en: 'Skipped' },
    running: { zh: '运行中', en: 'Running' },
    unknown: { zh: '未确认', en: 'Unknown' },
    cancelled: { zh: '已取消', en: 'Cancelled' },
  };
  return labels[value][locale];
}

function tabLabel(value: LogsTab, locale: AdminLogsLanguage): string {
  const labels: Record<LogsTab, { zh: string; en: string }> = {
    business: { zh: '业务事件', en: 'Business events' },
    analysis: { zh: '股票分析', en: 'Stock analysis' },
    scanner: { zh: '扫描器', en: 'Scanner' },
    backtest: { zh: '回测', en: 'Backtest' },
    data_source: { zh: '数据源', en: 'Data sources' },
    security: { zh: '安全事件', en: 'Security events' },
    raw: { zh: '原始日志', en: 'Raw logs' },
  };
  return labels[value][locale];
}

function skippedReasonLabel(value: unknown, locale: AdminLogsLanguage): string {
  const key = String(value || '').trim();
  const labels: Record<string, { zh: string; en: string }> = {
    previous_model_succeeded: { zh: '主模型已成功，无需调用备用模型', en: 'Primary model succeeded; backup model was not called' },
    previous_provider_succeeded: { zh: '主数据源已成功，无需调用备用源', en: 'Primary provider succeeded; backup provider was not called' },
    missing_api_key: { zh: '未配置 API Key，已跳过', en: 'API key not configured; skipped' },
    not_configured: { zh: '未配置 API Key，已跳过', en: 'API key not configured; skipped' },
    circuit_open: { zh: '数据源暂时不可用，已跳过', en: 'Provider circuit is open; skipped' },
    provider_unhealthy: { zh: '数据源暂时不可用，已跳过', en: 'Provider unhealthy; skipped' },
    unsupported_market: { zh: '当前市场不适用，已跳过', en: 'Unsupported market; skipped' },
    disabled_by_strategy: { zh: '策略未启用，已跳过', en: 'Disabled by strategy; skipped' },
  };
  return labels[key]?.[locale] || key;
}

function stepStatsLabel(
  counts: {
    status?: string | null;
    stepTraceAvailable?: boolean | null;
    stepCount?: number | null;
    successStepCount?: number | null;
    skippedStepCount?: number | null;
    failedStepCount?: number | null;
    unknownStepCount?: number | null;
  },
  locale: AdminLogsLanguage,
): string {
  const success = counts.successStepCount || 0;
  const skipped = counts.skippedStepCount || 0;
  const failed = counts.failedStepCount || 0;
  const unknown = counts.unknownStepCount || 0;
  const total = counts.stepCount || success + skipped + failed + unknown;
  const status = normalizeStatus(String(counts.status || ''));
  if ((status === 'failed' || status === 'error') && total === 0) {
    return locale === 'zh' ? '失败 · 无步骤明细' : 'Failed · No step trace';
  }
  return locale === 'zh'
    ? `成功 ${success} · 跳过 ${skipped} · 失败 ${failed} · 未确认 ${unknown}`
    : `Success ${success} · Skipped ${skipped} · Failed ${failed} · Unknown ${unknown}`;
}

function traceAvailabilityLabel(
  counts: {
    status?: string | null;
    stepTraceAvailable?: boolean | null;
    stepCount?: number | null;
    successStepCount?: number | null;
    skippedStepCount?: number | null;
    failedStepCount?: number | null;
    unknownStepCount?: number | null;
  },
  locale: AdminLogsLanguage,
): string {
  const success = counts.successStepCount || 0;
  const skipped = counts.skippedStepCount || 0;
  const failed = counts.failedStepCount || 0;
  const unknown = counts.unknownStepCount || 0;
  const total = counts.stepCount || success + skipped + failed + unknown;
  if (total > 0 || counts.stepTraceAvailable) return locale === 'zh' ? '已记录步骤明细' : 'Step trace attached';
  const status = normalizeStatus(String(counts.status || ''));
  if (status === 'failed' || status === 'error') {
    return locale === 'zh'
      ? '该事件在步骤级 trace 记录前已失败。'
      : 'This event failed before step-level trace was recorded.';
  }
  return locale === 'zh' ? '未附加步骤级 trace。' : 'No step-level trace was attached to this event.';
}

function shortIdentifier(value: unknown): string {
  const raw = String(value ?? '').trim();
  if (!raw) return '--';
  if (raw.length <= 14) return raw;
  return `${raw.slice(0, 7)}...${raw.slice(-5)}`;
}

function actorBadgeLabel(value: unknown): string {
  const normalized = String(value || 'unknown').trim().toLowerCase();
  if (['admin', 'user', 'guest', 'anonymous', 'system'].includes(normalized)) return normalized;
  return 'unknown';
}

function actorBadgeDisplay(value: unknown, locale: AdminLogsLanguage): string {
  const normalized = actorBadgeLabel(value);
  if (locale !== 'zh') return normalized;
  const labels: Record<string, string> = {
    admin: '管理员',
    user: '用户',
    guest: '访客',
    anonymous: '匿名',
    system: '系统',
    unknown: '未知',
  };
  return labels[normalized] || normalized;
}

function healthStatusLabel(status: unknown, locale: AdminLogsLanguage): string {
  const normalized = String(status || 'healthy').trim().toLowerCase();
  if (normalized === 'failing') return locale === 'zh' ? '故障' : 'Failing';
  if (normalized === 'degraded') return locale === 'zh' ? '降级' : 'Degraded';
  return locale === 'zh' ? '健康' : 'Healthy';
}

function healthStatusTone(status: unknown): string {
  const normalized = String(status || 'healthy').trim().toLowerCase();
  if (normalized === 'failing') return 'border-rose-300/30 bg-rose-500/10 text-rose-100';
  if (normalized === 'degraded') return 'border-amber-300/28 bg-amber-400/10 text-amber-100';
  return 'border-emerald-300/25 bg-emerald-400/10 text-emerald-100';
}

function friendlyRawStatusLabel(value: unknown, locale: AdminLogsLanguage): string {
  const raw = text(value, '');
  if (!raw || locale !== 'zh') return raw || '--';
  const normalized = raw.trim().toLowerCase().replace(/[-\s]+/g, '_');
  const labels: Record<string, string> = {
    unknown: '未确认',
    provider_error: '服务商错误',
    provider_down: '服务商不可用',
    source_error: '数据源错误',
    request_timeout: '请求超时',
    timeout: '超时',
    unavailable: '不可用',
    fallback: '已回退',
    cache: '缓存',
  };
  return labels[normalized] || raw;
}

function compactHealthList(items: AdminLogHealthSummary['failuresByProvider'] | undefined, locale: AdminLogsLanguage): string {
  if (!items?.length) return '--';
  return items.slice(0, 3).map((item) => `${friendlyRawStatusLabel(item.label || item.key, locale)} ${item.count}`).join(' · ');
}

function localizedRecommendedCleanupAction(value: string | null | undefined, locale: AdminLogsLanguage): string {
  const message = String(value || '').trim();
  if (!message) return locale === 'zh' ? '存储摘要暂不可用' : 'Storage summary unavailable';
  if (locale !== 'zh') return message;
  if (/over the hard limit/i.test(message)) return '存储已超过硬限制。请运行容量清理；最早可删日志仍受最小保留天数保护。';
  if (/over the soft limit/i.test(message)) return '存储已超过软限制。请先预览保留期清理或容量清理。';
  if (/Storage size unavailable/i.test(message)) return '存储大小暂不可用；保留期和行数检查仍然有效。';
  if (/No cleanup needed/i.test(message)) return '无需清理。';
  if (/Preview cleanup/i.test(message)) return '请先预览清理，再删除超过保留期的日志。';
  return message;
}

function countLabel(count: number | null | undefined, singular: string, plural: string, zhUnit: string, locale: AdminLogsLanguage): string {
  const value = Number(count ?? 0).toLocaleString();
  if (locale === 'zh') return `${value} ${zhUnit}`;
  return `${value} ${Number(count ?? 0) === 1 ? singular : plural}`;
}

function isFailedStatus(value: unknown): boolean {
  const status = normalizeStatus(String(value || ''));
  return status === 'failed' || status === 'error';
}

function hasDegradationSignal(value: unknown): boolean {
  return /fallback|degraded|partial|stale|timeout|circuit|unhealthy|fallback_used|回退|降级|部分|超时/i.test(String(value || ''));
}

function businessEventSeverity(event: BusinessEvent | BusinessEventDetail): EventSeverity {
  const status = normalizeStatus(event.status);
  if (status === 'failed' || status === 'error') return 'failed';
  const signal = [
    event.status,
    event.eventType,
    event.type,
    event.reason,
    event.errorSummary,
    event.rootCauseSummary,
    event.summary,
  ].join(' ');
  if (status === 'partial' || status === 'warning' || hasDegradationSignal(signal)) return 'degraded';
  return 'success';
}

function rawEventSeverity(detail: ExecutionLogSessionDetail): EventSeverity {
  const readable = detail.readableSummary || {};
  const operationDetail = detail.operationDetail || {};
  const status = normalizeStatus(String(operationDetail.status || readable.operationStatus || detail.overallStatus || ''));
  const level = normalizeLogLevel(readable.logLevel);
  if (status === 'failed' || status === 'error' || level === 'ERROR' || level === 'CRITICAL') return 'failed';
  const signal = [
    operationDetail.status,
    operationDetail.finalResult,
    readable.reason,
    readable.topFailureReason,
    readable.errorSummary,
    readable.eventMessage,
    readable.summaryParagraph,
  ].join(' ');
  if (status === 'partial' || status === 'warning' || level === 'WARNING' || hasDegradationSignal(signal)) return 'degraded';
  return 'success';
}

function severityLabel(severity: EventSeverity, locale: AdminLogsLanguage): string {
  if (severity === 'failed') return locale === 'zh' ? '失败' : 'Failed';
  if (severity === 'degraded') return locale === 'zh' ? '降级' : 'Degraded';
  return locale === 'zh' ? '成功' : 'Success';
}

function severityChipVariant(severity: EventSeverity): TerminalChipVariant {
  if (severity === 'failed') return 'danger';
  if (severity === 'degraded') return 'caution';
  return 'success';
}

function SeverityChip({
  severity,
  locale,
  className = '',
}: {
  severity: EventSeverity;
  locale: AdminLogsLanguage;
  className?: string;
}) {
  const textToneClass = severity === 'failed'
    ? 'text-rose-100'
    : severity === 'degraded'
      ? 'text-amber-100'
      : 'text-emerald-100';
  const extraClassName = className ? ` ${className}` : '';
  return (
    <TerminalChip
      variant={severityChipVariant(severity)}
      data-testid="event-severity-pill"
      className={`justify-center font-semibold ${textToneClass}${extraClassName}`}
    >
      {severityLabel(severity, locale)}
    </TerminalChip>
  );
}

function summaryTitle(severity: EventSeverity, locale: AdminLogsLanguage): string {
  if (severity === 'failed') return locale === 'zh' ? '根因' : 'Root Cause';
  if (severity === 'degraded') return locale === 'zh' ? '降级摘要' : 'Degradation Summary';
  return locale === 'zh' ? '执行摘要' : 'Execution Summary';
}

function summarySectionClass(severity: EventSeverity): string {
  if (severity === 'failed') return 'border-rose-300/12 bg-rose-500/[0.035]';
  if (severity === 'degraded') return 'border-amber-300/16 bg-amber-400/[0.04]';
  return 'border-emerald-300/12 bg-emerald-400/[0.035]';
}

function safeDebugSummaryPayload(payload: Record<string, unknown>): string {
  return JSON.stringify(sanitizeDisplayValue(payload), null, 2);
}

function buildBusinessDebugSummary(detail: BusinessEventDetail): string {
  return safeDebugSummaryPayload({
    event: detail.event,
    status: detail.status,
    severity: businessEventSeverity(detail),
    reason: detail.reason,
    actor: [detail.actorType, detail.actorLabel || detail.userId].filter(Boolean).join(' / '),
    context: detail.contextLabel || detail.symbol || detail.subject,
    source: detail.source,
    provider: detail.provider,
    requestId: detail.requestId,
    traceId: detail.traceId,
    route: detail.route,
    endpoint: detail.endpoint,
    errorSummary: detail.errorSummary,
    rootCauseSummary: detail.rootCauseSummary,
  });
}

function buildRawDebugSummary(detail: ExecutionLogSessionDetail): string {
  const readable = detail.readableSummary || {};
  const operationDetail = detail.operationDetail || {};
  return safeDebugSummaryPayload({
    event: readable.eventName || detail.name || detail.code,
    status: operationDetail.status || readable.operationStatus || detail.overallStatus,
    severity: rawEventSeverity(detail),
    reason: readable.reason || readable.topFailureReason,
    actor: readable.actorDisplay || readable.actorUsername || readable.actorSessionId,
    context: readable.contextLabel || readable.operationTarget || operationDetail.target || detail.code || detail.name,
    source: readable.source,
    provider: readable.provider,
    requestId: readable.requestId || readable.actorRequestId,
    traceId: readable.traceId || detail.queryId,
    route: undefined,
    endpoint: readable.endpoint,
    errorSummary: readable.errorSummary,
    rootCauseSummary: readable.topFailureReason || readable.summaryParagraph,
  });
}

function sanitizeDisplayValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map((item) => sanitizeDisplayValue(item));
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value as Record<string, unknown>).map(([key, item]) => {
      const normalized = key.toLowerCase().replace(/[-\s]/g, '_');
      if (/api_?key|token|authorization|secret|password/.test(normalized)) return [key, '***'];
      return [key, sanitizeDisplayValue(item)];
    }));
  }
  if (typeof value === 'string') {
    return value
      .replace(/([?&](?:api[-_]?key|token|access_token|secret|password|authorization)=)[^&#\s]+/gi, '$1***')
      .replace(/\b(api[-_]?key|apikey|access[-_]?token|token|authorization|secret|password)\b\s*[:=]\s*([^\s,;&]+)/gi, '$1=***')
      .replace(/\bBearer\s+[A-Za-z0-9._~+/=-]+/gi, 'Bearer ***');
  }
  return value;
}

function JsonBlock({ value }: { value: unknown }) {
  if (value == null || value === '') return <span>--</span>;
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return <span>{String(value)}</span>;
  }
  return (
    <pre className="mt-2 max-h-44 overflow-auto no-scrollbar rounded-xl border border-white/[0.02] bg-black/30 p-3 text-[11px] leading-5 text-white/68">
      {JSON.stringify(sanitizeDisplayValue(value), null, 2)}
    </pre>
  );
}

function AdminLogsTerminalSection({
  title,
  summary,
  children,
  defaultOpen = false,
  className = '',
  'data-testid': dataTestId,
}: {
  title: React.ReactNode;
  summary?: React.ReactNode;
  children: React.ReactNode;
  defaultOpen?: boolean;
  className?: string;
  'data-testid'?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const titleText = typeof title === 'string' ? title : '';
  const actionLabel = open ? `收起 ${titleText}` : `展开 ${titleText}`;
  return (
    <TerminalPanel
      dense
      data-testid={dataTestId || 'admin-logs-disclosure'}
      data-terminal-primitive="disclosure"
      className={`text-xs ${className}`.trim()}
    >
      <div className="flex min-w-0 items-center justify-between gap-2">
        <div className="min-w-0">
          <h3 className="truncate text-[10px] font-bold uppercase tracking-widest text-white/40">{title}</h3>
          {summary ? <p className="mt-0.5 truncate text-[11px] text-white/38">{summary}</p> : null}
        </div>
        <TerminalButton
          type="button"
          variant="compact"
          aria-expanded={open}
          aria-label={actionLabel}
          className="shrink-0 px-2 py-1 text-[11px]"
          onClick={() => setOpen((current) => !current)}
        >
          {open ? '收起' : '展开'}
        </TerminalButton>
      </div>
      {open ? <div className="mt-2">{children}</div> : null}
    </TerminalPanel>
  );
}

function CallCard({
  item,
  index,
  type,
  locale,
}: {
  item: Record<string, unknown>;
  index: number;
  type: 'llm' | 'data';
  locale: AdminLogsLanguage;
}) {
  const name = type === 'llm' ? text(item.model) : text(item.api || item.source);
  const status = normalizeStatus(String(item.status || ''));
  const reason = friendlyRawStatusLabel(item.reason || item.error || item.failureReason, locale);
  const fallback = text(item.fallback || item.fallbackChain || item.retryFallback, '');
  return (
    <AdminLogsTerminalSection
      title={`${type === 'llm' ? 'LLM' : 'API'} #${index + 1}`}
      summary={name}
      defaultOpen={index === 0}
      className="px-4 py-3"
    >
      <div className="mb-3 flex flex-wrap items-center justify-end gap-2">
        <StatusChip status={status} locale={locale} />
      </div>
      <div className="grid gap-4 text-xs text-secondary-text lg:grid-cols-2">
        <div>
          <p className="text-[10px] uppercase tracking-[0.18em] text-white/36">{locale === 'zh' ? '请求参数' : 'Request'}</p>
          <JsonBlock value={item.request || item.params || item.requestParams} />
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-[0.18em] text-white/36">{locale === 'zh' ? '响应' : 'Response'}</p>
          <JsonBlock value={item.response || item.result} />
        </div>
        {type === 'llm' ? (
          <p className="break-words">{locale === 'zh' ? '版本' : 'Version'}: <span className="text-foreground">{text(item.version)}</span></p>
        ) : null}
        <p className="break-words">{locale === 'zh' ? '失败原因' : 'Failure reason'}: <span className="text-foreground">{reason || '--'}</span></p>
        <p className="break-words lg:col-span-2">{locale === 'zh' ? '回退情况' : 'Fallback'}: <span className="text-foreground">{fallback || '--'}</span></p>
      </div>
    </AdminLogsTerminalSection>
  );
}

function downloadLogJson(detail: ExecutionLogSessionDetail): void {
  const blob = new Blob([JSON.stringify(sanitizeDisplayValue(detail), null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `wolfystock-log-${detail.sessionId}.json`;
  link.click();
  URL.revokeObjectURL(url);
}

async function copyLogJson(detail: ExecutionLogSessionDetail): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(JSON.stringify(sanitizeDisplayValue(detail), null, 2));
  }
}

async function copyTextValue(value: unknown): Promise<void> {
  const textValue = String(value ?? '').trim();
  if (!textValue || !navigator.clipboard?.writeText) return;
  await navigator.clipboard.writeText(textValue);
}

const AdminLogsPage: React.FC = () => {
  const { language, t } = useI18n();
  const locale = language as AdminLogsLanguage;
  const [activeTab, setActiveTab] = useState<LogsTab>('business');
  const [levelFilter, setLevelFilter] = useState<LevelFilter>('warning_plus');
  const [categoryFilter, setCategoryFilter] = useState<'all' | LogCategory>('all');
  const [statusFilter, setStatusFilter] = useState<(typeof STATUS_FILTER_OPTIONS)[number]>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [sinceFilter, setSinceFilter] = useState<(typeof SINCE_OPTIONS)[number]>('24h');
  const [showDebugLogs, setShowDebugLogs] = useState(false);
  const [businessEvents, setBusinessEvents] = useState<BusinessEvent[]>([]);
  const [businessTotal, setBusinessTotal] = useState(0);
  const [businessHasMore, setBusinessHasMore] = useState(false);
  const [businessHealth, setBusinessHealth] = useState<AdminLogHealthSummary | null>(null);
  const [pageOffset, setPageOffset] = useState(0);
  const [sessions, setSessions] = useState<ExecutionLogSessionSummary[]>([]);
  const [summary, setSummary] = useState<NonNullable<ExecutionLogSessionListResponse['summary']> | null>(null);
  const [storageSummary, setStorageSummary] = useState<AdminLogStorageSummary | null>(null);
  const [cleanupPreview, setCleanupPreview] = useState<AdminLogCleanupResponse | null>(null);
  const [cleanupMessage, setCleanupMessage] = useState<string | null>(null);
  const [isCleanupBusy, setIsCleanupBusy] = useState(false);
  const [selectedDetail, setSelectedDetail] = useState<ExecutionLogSessionDetail | null>(null);
  const [selectedBusinessDetail, setSelectedBusinessDetail] = useState<BusinessEventDetail | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [isLoadingList, setIsLoadingList] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [detailError, setDetailError] = useState<ParsedApiError | null>(null);
  const skipDebugClickRef = useRef(false);

  const loadStorageSummary = useCallback(async () => {
    try {
      const response = await adminLogsApi.getStorageSummary();
      setStorageSummary(response);
    } catch {
      setStorageSummary(null);
    }
  }, []);

  const loadSessions = useCallback(async () => {
    setIsLoadingList(true);
    setError(null);
    try {
      if (activeTab !== 'raw') {
        const category = activeTab === 'business' ? undefined : activeTab;
        const response: BusinessEventListResponse = await adminLogsApi.listBusinessEvents({
          category,
          minLevel: activeTab === 'scanner' ? 'INFO' : undefined,
          symbol: activeTab === 'analysis' ? searchQuery.trim() || undefined : undefined,
          status: statusFilter === 'all' ? undefined : statusFilter,
          query: activeTab === 'analysis' ? undefined : searchQuery.trim() || undefined,
          since: sinceFilter,
          limit: PAGE_SIZE,
          offset: pageOffset,
        });
        setBusinessEvents(response.items || []);
        setBusinessTotal(response.total || 0);
        setBusinessHasMore(Boolean(response.hasMore));
        setBusinessHealth(response.healthSummary || null);
        setSessions([]);
        setSummary(null);
        return;
      }
      const params: Parameters<typeof adminLogsApi.listSessions>[0] = {
        category: categoryFilter === 'all' ? undefined : categoryFilter,
        query: searchQuery.trim() || undefined,
        since: sinceFilter,
        limit: 100,
      };
      if (levelFilter === 'warning_plus') params.minLevel = 'WARNING';
      else if (levelFilter === 'error_plus') params.minLevel = 'ERROR';
      else if (levelFilter === 'all') params.minLevel = showDebugLogs ? 'DEBUG' : 'NOTICE';
      else params.level = levelFilter;
      const response = await adminLogsApi.listSessions({
        ...params,
      });
      const items = response.items || [];
      setSessions(items.length ? items : (import.meta.env.DEV ? MOCK_WOLFY_LOG_DETAILS : []));
      setSummary(response.summary || null);
      setBusinessHealth(null);
    } catch (err) {
      setError(getParsedApiError(err));
      if (activeTab === 'raw') {
        setSessions(import.meta.env.DEV ? MOCK_WOLFY_LOG_DETAILS : []);
      } else {
        setBusinessEvents([]);
        setBusinessTotal(0);
        setBusinessHasMore(false);
        setBusinessHealth(null);
      }
      setSummary(null);
    } finally {
      setIsLoadingList(false);
    }
  }, [activeTab, categoryFilter, levelFilter, pageOffset, searchQuery, showDebugLogs, sinceFilter, statusFilter]);

  const previewCleanup = useCallback(async () => {
    setIsCleanupBusy(true);
    setCleanupMessage(null);
    try {
      const response = await adminLogsApi.cleanupLogs({ mode: 'retention', useRetention: true, dryRun: true });
      setCleanupPreview(response);
      setCleanupMessage(locale === 'zh'
        ? `保留期清理预览：将在 ${formatDateTime(response.cutoff, locale)} 之前删除 ${response.matchedLogCount} 个会话和 ${response.matchedEventCount} 个事件。`
        : `Retention preview: ${response.matchedLogCount} sessions and ${response.matchedEventCount} events would be deleted before ${formatDateTime(response.cutoff, locale)}.`);
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setIsCleanupBusy(false);
    }
  }, [locale]);

  const previewCapacityCleanup = useCallback(async () => {
    setIsCleanupBusy(true);
    setCleanupMessage(null);
    try {
      const response = await adminLogsApi.cleanupLogs({ mode: 'capacity', dryRun: true });
      setCleanupPreview(response);
      setCleanupMessage(
        response.message
          ? localizedRecommendedCleanupAction(response.message, locale)
          : (locale === 'zh'
            ? `容量清理预览：将删除 ${response.matchedLogCount} 个会话和 ${response.matchedEventCount} 个事件。最小保留截止时间：${formatDateTime(response.cutoff, locale)}。`
            : `Capacity preview: ${response.matchedLogCount} sessions and ${response.matchedEventCount} events would be deleted. Minimum retention cutoff: ${formatDateTime(response.cutoff, locale)}.`),
      );
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setIsCleanupBusy(false);
    }
  }, [locale]);

  const confirmCleanup = useCallback(async () => {
    const expectedCount = cleanupPreview?.matchedLogCount ?? storageSummary?.logsOlderThanRetentionCount ?? 0;
    const cutoff = cleanupPreview?.cutoff || storageSummary?.retentionCutoff || '';
    const mode = cleanupPreview?.mode === 'capacity' ? 'capacity' : 'retention';
    const confirmed = window.confirm(
      locale === 'zh'
        ? [
          `确认对 ${expectedCount} 个管理员日志会话运行${mode === 'capacity' ? '容量' : '保留期'}清理？`,
          `预计事件数：${cleanupPreview?.matchedEventCount ?? 0}。`,
          `截止时间 / 最小保留保护：${formatDateTime(cutoff, locale)}。`,
          '此删除操作无法撤销。',
          '删除行后可能需要 PostgreSQL autovacuum 回收物理磁盘空间。',
        ].join('\n')
        : [
          `Run ${mode} cleanup for ${expectedCount} admin log sessions?`,
          `Estimated events: ${cleanupPreview?.matchedEventCount ?? 0}.`,
          `Cutoff/minimum retention protection: ${formatDateTime(cutoff, locale)}.`,
          'This deletion cannot be undone.',
          'Deleted rows may require PostgreSQL autovacuum to reclaim physical disk space.',
        ].join('\n'),
    );
    if (!confirmed) return;
    setIsCleanupBusy(true);
    setCleanupMessage(null);
    try {
      const response = await adminLogsApi.cleanupLogs(
        mode === 'capacity'
          ? { mode: 'capacity', dryRun: false }
          : { mode: 'retention', useRetention: true, dryRun: false },
      );
      setCleanupPreview(response);
      setCleanupMessage(locale === 'zh'
        ? `已删除 ${response.deletedLogCount} 个会话和 ${response.deletedEventCount} 个事件。${response.additionalCleanupNeeded ? ' 可能仍需继续清理。' : ''}`
        : `Deleted ${response.deletedLogCount} sessions and ${response.deletedEventCount} events.${response.additionalCleanupNeeded ? ' Additional cleanup may still be needed.' : ''}`);
      await Promise.all([loadStorageSummary(), loadSessions()]);
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setIsCleanupBusy(false);
    }
  }, [cleanupPreview, loadSessions, loadStorageSummary, locale, storageSummary]);

  useEffect(() => {
    document.title = t('adminLogs.documentTitle');
  }, [t]);

  useEffect(() => {
    setPageOffset(0);
  }, [activeTab, searchQuery, sinceFilter, statusFilter]);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    void loadStorageSummary();
  }, [loadStorageSummary]);

  const filteredSessions = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return sessions.filter((item) => {
      const summary = item.readableSummary || {};
      const category = String(summary.logCategory || '').trim();
      const level = normalizeLogLevel(summary.logLevel);
      const haystack = `${summary.eventName || ''} ${summary.eventMessage || ''} ${summary.requestId || ''} ${summary.source || ''} ${summary.actorDisplay || ''} ${summary.actorUsername || ''} ${summary.operationTarget || ''} ${item.code || ''} ${item.name || ''}`.toLowerCase();
      if (levelFilter === 'warning_plus' && !['WARNING', 'ERROR', 'CRITICAL'].includes(level)) return false;
      if (levelFilter === 'error_plus' && !['ERROR', 'CRITICAL'].includes(level)) return false;
      if (levelFilter === 'all' && !showDebugLogs && ['DEBUG', 'INFO'].includes(level)) return false;
      if (!['all', 'warning_plus', 'error_plus'].includes(levelFilter) && level !== levelFilter) return false;
      if (categoryFilter !== 'all' && category !== categoryFilter) return false;
      if (query && !haystack.includes(query)) return false;
      return true;
    }).sort((a, b) => {
      const left = a.startedAt ? new Date(a.startedAt).getTime() : 0;
      const right = b.startedAt ? new Date(b.startedAt).getTime() : 0;
      return right - left;
    });
  }, [categoryFilter, levelFilter, searchQuery, sessions, showDebugLogs]);

  const openDetail = useCallback(async (summary: ExecutionLogSessionSummary) => {
    setSelectedBusinessDetail(null);
    const mockDetail = MOCK_WOLFY_LOG_DETAILS.find((item) => item.sessionId === summary.sessionId);
    setSelectedDetail(mockDetail || {
      ...summary,
      events: [],
      operationDetail: {
        operationCategory: summary.readableSummary?.operationCategory,
        operationType: summary.readableSummary?.operationType,
        target: summary.readableSummary?.operationTarget || summary.code || summary.name,
        status: summary.readableSummary?.operationStatus || summary.overallStatus,
        keyMetric: summary.readableSummary?.keyMetric,
        aiCalls: [],
        dataSourceCalls: [],
        timeline: [],
        diagnostics: [],
      },
    });
    setIsDrawerOpen(true);
    setIsLoadingDetail(true);
    setDetailError(null);
    try {
      const detail = await adminLogsApi.getSessionDetail(summary.sessionId);
      setSelectedDetail(detail);
    } catch (err) {
      setDetailError(getParsedApiError(err));
    } finally {
      setIsLoadingDetail(false);
    }
  }, []);

  const openBusinessDetail = useCallback(async (event: BusinessEvent) => {
    setSelectedDetail(null);
    setSelectedBusinessDetail({
      ...event,
      steps: [],
    });
    setIsDrawerOpen(true);
    setIsLoadingDetail(true);
    setDetailError(null);
    try {
      const detail = await adminLogsApi.getBusinessEventDetail(event.id);
      setSelectedBusinessDetail(detail);
    } catch (err) {
      setDetailError(getParsedApiError(err));
    } finally {
      setIsLoadingDetail(false);
    }
  }, []);

  const toggleDebugLogs = useCallback(() => {
    setShowDebugLogs((current) => !current);
  }, []);

  const drawerDetail = selectedDetail;
  const businessDetail = selectedBusinessDetail;
  const readable = drawerDetail?.readableSummary || {};
  const operationDetail = drawerDetail?.operationDetail || {};
  const aiCalls = asRecordList(operationDetail.aiCalls);
  const dataSourceCalls = asRecordList(operationDetail.dataSourceCalls);
  const timeline = asRecordList(operationDetail.timeline);
  const businessSteps = businessDetail?.steps || [];
  const diagnostics = asRecordList(operationDetail.diagnostics);
  const explicitFallbacks = Array.isArray(operationDetail.systemFallbacks) ? operationDetail.systemFallbacks : [];
  const systemFallbacks = explicitFallbacks.length
    ? explicitFallbacks.map((item) => (typeof item === 'string' ? { source: 'System', message: item } : item)).filter((item): item is Record<string, unknown> => !!item && typeof item === 'object' && !Array.isArray(item))
    : diagnostics.filter((item) => /fallback|回退/i.test(`${item.message || ''} ${item.source || ''}`));
  const systemOperation = asRecord(operationDetail.systemOperation);
  const drawerStatus = normalizeStatus(String(businessDetail?.status || operationDetail.status || readable.operationStatus || drawerDetail?.overallStatus || ''));
  const businessSeverity = businessDetail ? businessEventSeverity(businessDetail) : 'success';
  const rawSeverity = drawerDetail ? rawEventSeverity(drawerDetail) : 'success';
  const drawerOperationType = normalizeOperationType(readable);
  const businessTraceValue = businessDetail?.traceId || businessDetail?.requestId;
  const businessActorLabel = text(businessDetail?.actorLabel || businessDetail?.userId, locale === 'zh' ? '未记录' : 'Not recorded');
  const businessContextLabel = text(businessDetail?.contextLabel || businessDetail?.symbol || businessDetail?.subject || businessDetail?.event, locale === 'zh' ? '未记录' : 'Not recorded');
  const businessSourceLabel = text([businessDetail?.provider, businessDetail?.source].filter(Boolean).join(' / '), locale === 'zh' ? '未记录' : 'Not recorded');
  const rawTraceValue = readable.traceId || readable.requestId || readable.actorRequestId || drawerDetail?.queryId;
  const rawRootCause = text(readable.errorSummary || readable.topFailureReason || readable.eventMessage || readable.summaryParagraph, locale === 'zh' ? '原因未确认' : 'Reason unknown');
  const rawActorRole = String(readable.actorRole || '').trim().toLowerCase();
  const computedSummary = useMemo(() => {
    const emptySummary = {
      errorCount: 0,
      warningCount: 0,
      dataSourceFailureCount: 0,
      slowRequestCount: 0,
      latestCriticalAt: null as string | null,
      totalFailedCount: 0,
      businessFailureCount: 0,
      providerFailureCount: 0,
      latestErrorReason: null as string | null,
    };
    if (activeTab !== 'raw') {
      return businessEvents.reduce(
        (acc, item) => {
          const status = normalizeStatus(item.status);
          if (status === 'failed' || status === 'error') {
            acc.errorCount += 1;
            acc.totalFailedCount += 1;
            acc.businessFailureCount += 1;
            if (!acc.latestErrorReason) acc.latestErrorReason = text(item.reason || item.errorSummary || item.rootCauseSummary, '');
          }
          if (status === 'partial') acc.warningCount += 1;
          if ((item.category === 'data_source' || item.provider || item.source) && ['failed', 'error', 'partial'].includes(status)) {
            acc.dataSourceFailureCount += 1;
            acc.providerFailureCount += 1;
          }
          return acc;
        },
        { ...emptySummary },
      );
    }
    if (summary) return { ...emptySummary, ...summary, totalFailedCount: summary.errorCount || 0, providerFailureCount: summary.dataSourceFailureCount || 0 };
    return filteredSessions.reduce(
      (acc, item) => {
        const readableSummary = item.readableSummary || {};
        const level = normalizeLogLevel(readableSummary.logLevel);
        const category = String(readableSummary.logCategory || '');
        const eventName = String(readableSummary.eventName || '');
        if (level === 'ERROR' || level === 'CRITICAL') {
          acc.errorCount += 1;
          acc.totalFailedCount += 1;
          if (!acc.latestErrorReason) acc.latestErrorReason = text(readableSummary.reason || readableSummary.errorSummary || readableSummary.topFailureReason || readableSummary.eventMessage, '');
        }
        if (level === 'WARNING') acc.warningCount += 1;
        if (category === 'data_source' && ['WARNING', 'ERROR', 'CRITICAL'].includes(level)) {
          acc.dataSourceFailureCount += 1;
          acc.providerFailureCount += 1;
        }
        if (eventName === 'SlowRequest' || eventName === 'MarketCacheColdStartSlow') acc.slowRequestCount += 1;
        if (level === 'CRITICAL' && item.startedAt && (!acc.latestCriticalAt || item.startedAt > acc.latestCriticalAt)) {
          acc.latestCriticalAt = item.startedAt;
        }
        return acc;
      },
      { ...emptySummary },
    );
  }, [activeTab, businessEvents, filteredSessions, summary]);
  const healthSummary = useMemo<AdminLogHealthSummary>(() => {
    const fallback: AdminLogHealthSummary = {
      totalEvents: activeTab === 'raw' ? filteredSessions.length : businessTotal,
      failedEvents: computedSummary.totalFailedCount || computedSummary.errorCount || 0,
      warningEvents: computedSummary.warningCount || 0,
      slowEvents: computedSummary.slowRequestCount || 0,
      failureRate: (activeTab === 'raw' ? filteredSessions.length : businessTotal)
        ? (computedSummary.totalFailedCount || computedSummary.errorCount || 0) / (activeTab === 'raw' ? filteredSessions.length : businessTotal)
        : 0,
      status: (computedSummary.totalFailedCount || computedSummary.errorCount || 0) > 0 ? 'degraded' : 'healthy',
      failuresByCategory: [],
      failuresByProvider: [],
      failuresByReason: [],
      actorBreakdown: [],
      topRecentErrors: [],
      latestCriticalError: null,
    };
    if (activeTab === 'raw') return summary?.healthSummary || fallback;
    return businessHealth || fallback;
  }, [activeTab, businessHealth, businessTotal, computedSummary, filteredSessions.length, summary]);
  const scannerSummary = useMemo(() => {
    const scannerEvents = businessEvents.filter((item) => item.category === 'scanner');
    const latest = scannerEvents[0] || null;
    const failed = scannerEvents.filter((item) => ['failed', 'error'].includes(normalizeStatus(item.status))).length;
    const success = scannerEvents.filter((item) => normalizeStatus(item.status) === 'success').length;
    const latestError = scannerEvents.find((item) => ['failed', 'error'].includes(normalizeStatus(item.status)));
    return { latest, failed, success, latestError };
  }, [businessEvents]);
  const topCategory = healthSummary.failuresByCategory?.[0];
  const latestCriticalError = healthSummary.latestCriticalError || healthSummary.topRecentErrors?.[0] || null;
  const currentStorageBytes = storageBytes(storageSummary);
  const softLimitBytes = storageSummary?.storageSoftLimitBytes ?? 512 * 1024 * 1024;
  const hardLimitBytes = storageSummary?.storageHardLimitBytes ?? 1024 * 1024 * 1024;
  const softPercent = clampPercent(storageSummary?.usedPercentageOfSoftLimit);
  const hardPercent = clampPercent(storageSummary?.usedPercentageOfHardLimit);
  const canRunCapacityCleanup = Boolean(storageSummary?.storageSizeAvailable && storageSummary.status === 'critical');
  const visibleRecordCount = activeTab === 'raw' ? filteredSessions.length : businessTotal;
  const operatorCurrentState = locale === 'zh'
    ? `${healthSummary.failedEvents} 个失败 / ${visibleRecordCount} 条记录`
    : `${healthSummary.failedEvents} failed / ${visibleRecordCount} records`;
  const operatorNextAction = healthSummary.failedEvents > 0
    ? (locale === 'zh' ? '先处理失败和数据源降级' : 'Review failures and data-source degradations first')
    : (locale === 'zh' ? '保持业务事件监控' : 'Keep monitoring business events');

  return (
    <section data-testid="admin-logs-workspace" className="flex min-h-0 w-full min-w-0 flex-1 flex-col gap-4 overflow-x-hidden">
      <TerminalPageShell data-testid="admin-logs-page-shell" className="min-h-0 flex-1 overflow-x-hidden py-5 md:py-6">
        <TerminalPanel as="section" data-testid="admin-logs-header-panel" className="overflow-hidden">
          <div className="flex min-w-0 flex-col gap-4">
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-emerald-200/70">{locale === 'zh' ? 'WolfyStock 运维追踪' : 'WolfyStock Ops Trace'}</p>
              <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">{t('adminLogs.pageTitle')}</h1>
              <p className="mt-1 max-w-4xl text-xs leading-5 text-secondary-text">
                {locale === 'zh' ? '业务事件优先，原始日志与调试细节留在高级标签。' : t('adminLogs.pageSubtitle')}
              </p>
            </div>

            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <TerminalMetric
                label={locale === 'zh' ? '页面用途' : 'Purpose'}
                value={locale === 'zh' ? '定位失败与审计线索' : 'Find failures and audit trails'}
                subvalue={locale === 'zh' ? '业务事件、状态、操作者、来源' : 'Business events, status, actor, source'}
                valueClassName="text-sm font-semibold tracking-normal"
              />
              <TerminalMetric
                label={locale === 'zh' ? '当前状态' : 'Current state'}
                value={operatorCurrentState}
                subvalue={`${healthStatusLabel(healthSummary.status, locale)} · ${healthSummary.warningEvents} ${locale === 'zh' ? '个警告' : 'warnings'}`}
                valueClassName="text-sm font-semibold tracking-normal"
              />
              <TerminalMetric
                label={locale === 'zh' ? '下一步' : 'Next action'}
                value={operatorNextAction}
                subvalue={locale === 'zh' ? '清理与原始日志保持二级入口' : 'Cleanup and raw logs stay secondary'}
                valueClassName="text-sm font-semibold tracking-normal"
              />
            </div>

            <div role="tablist" aria-label={locale === 'zh' ? '日志视图' : 'Log views'} className="flex max-w-full gap-2 overflow-x-auto no-scrollbar pb-1 sm:flex-wrap sm:overflow-visible">
              {(['business', 'analysis', 'scanner', 'backtest', 'data_source', 'security', 'raw'] as LogsTab[]).map((tab) => {
                const isActive = activeTab === tab;
                return (
                  <TerminalButton
                    key={tab}
                    type="button"
                    role="tab"
                    aria-selected={isActive}
                    variant={isActive ? 'compact' : 'secondary'}
                    className={`shrink-0 px-3 py-1.5 text-xs font-semibold ${isActive ? 'border-emerald-300/45 bg-emerald-400/14 text-emerald-50 hover:bg-emerald-400/18 hover:text-emerald-50' : 'text-secondary-text'}`}
                    onClick={() => setActiveTab(tab)}
                  >
                    {tabLabel(tab, locale)}
                  </TerminalButton>
                );
              })}
            </div>

            <div
              data-testid="admin-logs-filter-bar"
              className={`grid min-w-0 grid-cols-1 gap-2 sm:grid-cols-2 ${activeTab === 'raw' ? 'xl:grid-cols-[9.5rem_9.5rem_minmax(12rem,1fr)_9.5rem_auto_auto]' : 'xl:grid-cols-[minmax(14rem,1fr)_9.5rem_9.5rem_auto]'}`}
            >
              {activeTab === 'raw' ? (
                <>
                  <label className="sr-only" htmlFor="admin-logs-level-filter">{locale === 'zh' ? '级别筛选' : 'Level filter'}</label>
                  <select
                    id="admin-logs-level-filter"
                    aria-label={locale === 'zh' ? '级别筛选' : 'Level filter'}
                    className="input-surface h-9 w-full min-w-0 appearance-none truncate rounded-lg px-3 pr-10 text-sm"
                    value={levelFilter}
                    onChange={(event) => setLevelFilter(event.target.value as LevelFilter)}
                  >
                    {LEVEL_FILTER_OPTIONS.map((option) => (
                      <option key={option} value={option}>{levelFilterLabel(option, locale)}</option>
                    ))}
                  </select>
                  <label className="sr-only" htmlFor="admin-logs-category-filter">{locale === 'zh' ? '分类筛选' : 'Category filter'}</label>
                  <select
                    id="admin-logs-category-filter"
                    aria-label={locale === 'zh' ? '分类筛选' : 'Category filter'}
                    className="input-surface h-9 w-full min-w-0 appearance-none truncate rounded-lg px-3 pr-10 text-sm"
                    value={categoryFilter}
                    onChange={(event) => setCategoryFilter(event.target.value as 'all' | LogCategory)}
                  >
                    <option value="all">{locale === 'zh' ? '全部分类' : 'All categories'}</option>
                    {CATEGORY_OPTIONS.map((option) => (
                      <option key={option} value={option}>{categoryLabel(option, locale)}</option>
                    ))}
                  </select>
                </>
              ) : null}
              <label className="sr-only" htmlFor="admin-logs-search">{locale === 'zh' ? '搜索日志' : 'Search logs'}</label>
              <input
                id="admin-logs-search"
                aria-label={locale === 'zh' ? '搜索日志' : 'Search logs'}
                className="input-surface h-9 w-full min-w-0 rounded-lg px-3 text-sm"
                placeholder={activeTab === 'analysis' ? 'TSLA / AAPL / NVDA' : (locale === 'zh' ? '事件 / 请求 ID / 标的 / 来源 / 用户' : 'Event / request id / symbol / source / user')}
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
              />
              {activeTab !== 'raw' ? (
                <select
                  aria-label={locale === 'zh' ? '状态筛选' : 'Status filter'}
                  className="input-surface h-9 w-full min-w-0 appearance-none truncate rounded-lg px-3 pr-10 text-sm"
                  value={statusFilter}
                  onChange={(event) => setStatusFilter(event.target.value as (typeof STATUS_FILTER_OPTIONS)[number])}
                >
                  {STATUS_FILTER_OPTIONS.map((option) => (
                    <option key={option} value={option}>{statusFilterLabel(option, locale)}</option>
                  ))}
                </select>
              ) : null}
              <label className="sr-only" htmlFor="admin-logs-since-filter">{locale === 'zh' ? '时间范围' : 'Time range'}</label>
              <select
                id="admin-logs-since-filter"
                aria-label={locale === 'zh' ? '时间范围' : 'Time range'}
                className="input-surface h-9 w-full min-w-0 appearance-none truncate rounded-lg px-3 pr-10 text-sm"
                value={sinceFilter}
                onChange={(event) => setSinceFilter(event.target.value as (typeof SINCE_OPTIONS)[number])}
              >
                {SINCE_OPTIONS.map((option) => (
                  <option key={option} value={option}>{sinceLabel(option, locale)}</option>
                ))}
              </select>
              {activeTab === 'raw' ? (
                <button
                  type="button"
                  role="switch"
                  aria-checked={showDebugLogs}
                  aria-label={locale === 'zh' ? '显示调试日志' : 'Show debug logs'}
                  className="flex h-9 min-w-0 items-center gap-2 rounded-lg border border-white/8 bg-white/[0.035] px-3 text-xs text-secondary-text transition hover:border-white/15 hover:bg-white/[0.055]"
                  onMouseDown={(event) => {
                    event.preventDefault();
                    skipDebugClickRef.current = true;
                    toggleDebugLogs();
                  }}
                  onClick={() => {
                    if (skipDebugClickRef.current) {
                      skipDebugClickRef.current = false;
                      return;
                    }
                    toggleDebugLogs();
                  }}
                >
                  <span
                    className={`relative h-4 w-8 rounded-full border transition ${showDebugLogs ? 'border-cyan-300/60 bg-cyan-400/35' : 'border-white/15 bg-black/30'}`}
                    aria-hidden="true"
                  >
                    <span className={`absolute top-1/2 h-3 w-3 -translate-y-1/2 rounded-full bg-white transition ${showDebugLogs ? 'left-[1.05rem]' : 'left-0.5'}`} />
                  </span>
                  <span>{locale === 'zh' ? '显示调试日志' : 'Show debug logs'}</span>
                </button>
              ) : null}
              <TerminalButton
                type="button"
                variant="secondary"
                className="h-9 px-4 text-sm sm:col-span-2 xl:col-span-1"
                onClick={() => void loadSessions()}
                disabled={isLoadingList}
              >
                {isLoadingList ? t('adminLogs.loading') : t('adminLogs.refreshButton')}
              </TerminalButton>
            </div>

            <TerminalNotice variant="neutral">
              {t('adminLogs.filterHintDetailed', { count: activeTab === 'raw' ? filteredSessions.length : businessTotal })}
            </TerminalNotice>
          </div>
        </TerminalPanel>

        {error ? <ApiErrorAlert error={error} /> : null}

        <AdminLogsTerminalSection
          data-testid="admin-logs-storage-disclosure"
          title={locale === 'zh' ? '二级细节：日志容量与破坏性清理' : 'Secondary details: storage and destructive cleanup'}
          summary={locale === 'zh' ? '需确认' : 'confirmation required'}
          className="px-4 py-3"
        >
          <section
            data-testid="admin-logs-storage-summary"
            className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-[minmax(14rem,1.35fr)_9rem_10rem_10rem_minmax(12rem,1fr)_auto]"
          >
            <TerminalNestedBlock className={`min-w-0 ${storageStatusTone(storageSummary?.status)}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] opacity-70">{locale === 'zh' ? '日志容量' : 'LOG STORAGE'}</p>
                  {storageSummary?.storageSizeAvailable ? (
                    <>
                      <p className="mt-1 text-base font-semibold">
                        {locale === 'zh' ? '日志容量 ' : ''}{storageSummary.storageSizeLabel || storageSummary.sizeLabel || formatStorageBytes(currentStorageBytes)}
                      </p>
                      <p className="text-[11px] opacity-80">{storageMeasurementLabel(storageSummary, locale)} · {formatStorageBytes(softLimitBytes)} {locale === 'zh' ? '软限制' : 'soft'} · {formatStorageBytes(hardLimitBytes)} {locale === 'zh' ? '硬限制' : 'hard limit'}</p>
                    </>
                  ) : (
                    <>
                      <p className="mt-1 text-base font-semibold">{locale === 'zh' ? '容量暂不可用' : 'Size unavailable'}</p>
                      <p className="text-[11px] opacity-80">{storageUnavailableReason(storageSummary, locale)} · {locale === 'zh' ? '保留期检查仍在生效' : 'Retention checks active'}</p>
                    </>
                  )}
                </div>
                <TerminalChip variant={storageSummary?.status === 'critical' ? 'danger' : storageSummary?.status === 'warning' ? 'caution' : 'success'} className="shrink-0 font-semibold uppercase">
                  {storageStatusLabel(storageSummary?.status, locale)}
                </TerminalChip>
              </div>
              {storageSummary?.storageSizeAvailable ? (
                <div className="mt-2">
                  <div className="h-1.5 overflow-hidden rounded-full bg-black/35">
                    <div className="h-full rounded-full bg-current" style={{ width: `${Math.max(3, hardPercent)}%` }} />
                  </div>
                  <p className="mt-1 text-[10px] opacity-75">{softPercent}% {locale === 'zh' ? '软限制' : 'soft'} · {hardPercent}% {locale === 'zh' ? '硬限制' : 'hard'}</p>
                </div>
              ) : null}
            </TerminalNestedBlock>

            <TerminalMetric
              label={locale === 'zh' ? '日志规模' : 'LOG VOLUME'}
              value={countLabel(storageSummary?.totalLogCount, 'session', 'sessions', '会话', locale)}
              subvalue={countLabel(storageSummary?.totalEventCount, 'event', 'events', '事件', locale)}
              valueClassName="text-base"
            />
            <TerminalMetric
              label={locale === 'zh' ? '保留期' : 'Retention'}
              value={`${storageSummary?.retentionDays ?? '--'} ${locale === 'zh' ? '天' : 'days'}`}
              subvalue={`${locale === 'zh' ? '最少' : 'min'} ${storageSummary?.minimumRetentionDays ?? '--'} ${locale === 'zh' ? '天' : 'days'} · ${storageSummary?.logsOlderThanRetentionCount ?? 0} ${locale === 'zh' ? '条超期' : 'older'}`}
              valueClassName="text-base"
            />
            <TerminalMetric
              label={locale === 'zh' ? '最早日志' : 'OLDEST LOG'}
              value={formatDateTime(storageSummary?.oldestLogTimestamp, locale)}
              subvalue={locale === 'zh' ? '当前保留的最早会话 / 事件' : 'oldest retained session/event'}
              valueClassName="truncate text-sm font-semibold tracking-normal"
            />

            <div className="min-w-0 space-y-2">
              <TerminalNotice variant={storageSummary?.status === 'critical' ? 'danger' : storageSummary?.status === 'warning' ? 'caution' : 'neutral'}>
                <p className="font-medium text-white/88">{locale === 'zh' ? '清理建议' : 'Cleanup guidance'}</p>
                <p className="mt-1">{localizedRecommendedCleanupAction(storageSummary?.recommendedCleanupAction, locale)}</p>
                {storageSummary && ['warning', 'critical'].includes(String(storageSummary.status)) ? (
                  <a
                    href="/admin/notifications"
                    className="mt-1 inline-flex text-[11px] font-semibold text-emerald-100 underline-offset-4 hover:underline"
                  >
                    {locale === 'zh' ? '配置管理员通知通道' : 'Configure Admin notification channels'}
                  </a>
                ) : null}
              </TerminalNotice>
              {storageSummary?.postgresVacuumNote ? (
                <TerminalNotice variant="caution">
                  {locale === 'zh' ? '删除行后可能需要 PostgreSQL autovacuum 回收物理磁盘空间。' : storageSummary.postgresVacuumNote}
                </TerminalNotice>
              ) : null}
              {storageSummary?.autoCleanupEnabled && storageSummary?.status === 'critical' ? (
                <TerminalNotice variant="danger">
                  {locale === 'zh' ? '需要自动清理' : 'Auto cleanup required'}
                </TerminalNotice>
              ) : null}
              {cleanupMessage ? (
                <TerminalNotice variant="info">
                  {cleanupMessage}
                </TerminalNotice>
              ) : null}
            </div>

            <div className="flex min-w-0 flex-col gap-2 sm:flex-row lg:flex-col">
              <TerminalButton
                type="button"
                variant="secondary"
                className="h-9 px-3 text-xs"
                onClick={() => void previewCleanup()}
                disabled={isCleanupBusy || !storageSummary}
              >
                {isCleanupBusy ? t('adminLogs.loading') : (locale === 'zh' ? '预览保留期清理' : 'Preview retention cleanup')}
              </TerminalButton>
              <TerminalButton
                type="button"
                variant="secondary"
                className="h-9 px-3 text-xs"
                onClick={() => void previewCapacityCleanup()}
                disabled={isCleanupBusy || !storageSummary?.storageSizeAvailable}
              >
                {locale === 'zh' ? '预览容量清理' : 'Preview capacity cleanup'}
              </TerminalButton>
              <TerminalButton
                type="button"
                variant="danger"
                className="h-9 px-3 py-2 text-xs font-semibold"
                onClick={() => void confirmCleanup()}
                disabled={isCleanupBusy || !storageSummary || (cleanupPreview?.matchedLogCount ?? storageSummary.logsOlderThanRetentionCount) <= 0 || (cleanupPreview?.mode === 'capacity' && !canRunCapacityCleanup)}
              >
                {cleanupPreview?.mode === 'capacity'
                  ? (locale === 'zh' ? '按容量清理日志' : 'Run capacity cleanup')
                  : (locale === 'zh' ? '清理超过保留期的日志' : 'Clean logs older than retention')}
              </TerminalButton>
            </div>
          </section>
        </AdminLogsTerminalSection>

        <TerminalPanel as="section" data-testid="admin-logs-health-summary" dense>
          <TerminalSectionHeader
            eyebrow={locale === 'zh' ? '运维健康' : 'OPS HEALTH'}
            title={locale === 'zh' ? '业务事件健康摘要' : 'Business event health summary'}
            action={<TerminalChip variant={healthSummary.status === 'failing' ? 'danger' : healthSummary.status === 'degraded' ? 'caution' : 'success'}>{healthStatusLabel(healthSummary.status, locale)}</TerminalChip>}
          />
          <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-[10rem_9rem_9rem_minmax(10rem,1fr)_minmax(10rem,1fr)_minmax(12rem,1.2fr)]">
            <TerminalNestedBlock className={`min-w-0 ${healthStatusTone(healthSummary.status)}`}>
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] opacity-70">{locale === 'zh' ? '整体状态' : 'Overall status'}</p>
              <p className="mt-1 text-base font-semibold">{healthStatusLabel(healthSummary.status, locale)}</p>
            </TerminalNestedBlock>
            <TerminalMetric
              label={locale === 'zh' ? '失败' : 'Failures'}
              value={`${healthSummary.failedEvents} / ${healthSummary.totalEvents}`}
              subvalue={`${Math.round((healthSummary.failureRate || 0) * 100)}% · ${healthSummary.warningEvents} ${locale === 'zh' ? '警告' : 'warning'}`}
              valueClassName="text-base"
            />
            <TerminalMetric
              label={locale === 'zh' ? '警告' : 'Warnings'}
              value={healthSummary.warningEvents}
              subvalue={`${healthSummary.slowEvents} ${locale === 'zh' ? '慢请求' : 'slow'}`}
              valueClassName="text-base"
            />
            <TerminalMetric
              label={locale === 'zh' ? '主要失败功能' : 'Top failing feature'}
              value={friendlyRawStatusLabel(topCategory?.label || topCategory?.key, locale)}
              subvalue={topCategory ? countLabel(topCategory.count, 'event', 'events', '事件', locale) : '--'}
              valueClassName="truncate text-sm font-semibold tracking-normal"
            />
            <TerminalMetric
              label={locale === 'zh' ? '供应商 / 原因' : 'Provider / reason'}
              value={compactHealthList(healthSummary.failuresByProvider, locale)}
              subvalue={compactHealthList(healthSummary.failuresByReason, locale)}
              valueClassName="truncate text-sm font-semibold tracking-normal"
            />
            <TerminalMetric
              label={locale === 'zh' ? '最新严重错误' : 'Latest critical error'}
              value={text(latestCriticalError?.event || latestCriticalError?.category)}
              subvalue={friendlyRawStatusLabel(latestCriticalError?.errorSummary || latestCriticalError?.reason, locale)}
              valueClassName="truncate text-sm font-semibold tracking-normal"
            />
          </div>
        </TerminalPanel>

        {activeTab === 'scanner' ? (
          <TerminalPanel as="section" data-testid="admin-logs-scanner-summary" dense>
            <TerminalSectionHeader
              eyebrow={locale === 'zh' ? '扫描器摘要' : 'SCANNER'}
              title={locale === 'zh' ? '扫描器运行摘要' : 'Scanner execution summary'}
            />
            <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <TerminalMetric
                label={locale === 'zh' ? '最近一次扫描' : 'Latest scan'}
                value={text(scannerSummary.latest?.event, locale === 'zh' ? '暂无扫描' : 'No scan')}
                subvalue={`${formatDateTime(scannerSummary.latest?.startedAt, locale)} · ${formatDuration(scannerSummary.latest?.durationMs)}`}
                valueClassName="truncate text-sm font-semibold tracking-normal"
              />
              <TerminalMetric
                label={locale === 'zh' ? '成功 / 失败' : 'Success / failed'}
                value={`${scannerSummary.success} / ${scannerSummary.failed}`}
                subvalue={locale === 'zh' ? '包含 INFO 生命周期记录' : 'Includes INFO lifecycle records'}
                valueClassName="text-base"
              />
              <TerminalMetric
                label={locale === 'zh' ? '最近错误' : 'Latest error'}
                value={friendlyRawStatusLabel(scannerSummary.latestError?.errorSummary || scannerSummary.latestError?.reason, locale)}
                subvalue={text(scannerSummary.latestError?.event, locale === 'zh' ? '暂无失败扫描' : 'No failed scan')}
                valueClassName="truncate text-sm font-semibold tracking-normal"
              />
              <TerminalMetric
                label={locale === 'zh' ? '运行耗时' : 'Run duration'}
                value={formatDuration(scannerSummary.latest?.durationMs)}
                subvalue={locale === 'zh' ? '开始、完成、失败均进入日志中心' : 'Start, completion, and failure are logged'}
                valueClassName="text-base"
              />
            </div>
          </TerminalPanel>
        ) : null}

        <TerminalPanel as="section" className="min-h-0" dense>
          <TerminalSectionHeader
            eyebrow={locale === 'zh' ? '主队列' : 'MAIN QUEUE'}
            title={t('adminLogs.sessionListTitle')}
            action={<TerminalChip variant="neutral">{countLabel(activeTab === 'raw' ? filteredSessions.length : businessTotal, 'record', 'records', '记录', locale)}</TerminalChip>}
          />
          <TerminalNotice variant="neutral" className="mt-3">
            {locale === 'zh' ? '点击查看详情会打开右侧抽屉，调用链和数据源可独立折叠。' : 'View Details opens a right drawer; LLM and data-source chains collapse independently.'}
          </TerminalNotice>

          {activeTab !== 'raw' ? (
            businessEvents.length === 0 ? (
              <TerminalEmptyState className="mt-3 min-h-[88px]" title={activeTab === 'scanner' && locale === 'zh' ? '暂无扫描器日志' : t('adminLogs.noSessionsTitle')}>
                {activeTab === 'scanner' && locale === 'zh'
                  ? '暂无扫描器日志。运行一次扫描后，这里会显示扫描开始、完成、失败和耗时。'
                  : t('adminLogs.noSessionsBody')}
              </TerminalEmptyState>
            ) : (
              <TerminalDenseList data-testid="business-events-table-shell" className="mt-3 gap-0 overflow-hidden rounded-xl border border-white/6 bg-black/15">
                <div className="grid grid-cols-[6.25rem_minmax(0,1.15fr)_5.75rem_minmax(0,1fr)_4.5rem] gap-3 border-b border-white/6 px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-white/38 md:grid-cols-[7.25rem_minmax(0,1.1fr)_7.5rem_minmax(0,1.35fr)_6rem] xl:grid-cols-[8.5rem_minmax(9rem,0.9fr)_8.5rem_minmax(13rem,1.25fr)_8rem_minmax(12rem,1.2fr)_minmax(10rem,1fr)_6rem]">
                  <div>{locale === 'zh' ? '时间' : 'Time'}</div>
                  <div>{locale === 'zh' ? '事件' : 'Event'}</div>
                  <div>{locale === 'zh' ? '状态 / 严重度' : 'Status / Severity'}</div>
                  <div>{locale === 'zh' ? '原因' : 'Reason'}</div>
                  <div className="hidden xl:block">{locale === 'zh' ? '操作者' : 'Actor'}</div>
                  <div className="hidden xl:block">{locale === 'zh' ? '上下文' : 'Context'}</div>
                  <div className="hidden xl:block">{locale === 'zh' ? '来源 / 供应商' : 'Source / Provider'}</div>
                  <div>{locale === 'zh' ? '操作' : 'Action'}</div>
                </div>
                <div className="max-h-[min(34vh,21rem)] divide-y divide-white/6 overflow-y-auto no-scrollbar">
                  {businessEvents.map((item) => {
                    const status = normalizeStatus(item.status);
                    const actorRole = actorBadgeLabel(item.actorType);
                    const actorType = actorBadgeDisplay(item.actorType, locale);
                    const actorSecondary = text(item.actorLabel || item.userId || item.requestId, locale === 'zh' ? '未记录' : 'Not recorded');
                    const contextPrimary = text(item.contextLabel || item.symbol || item.subject || item.event, locale === 'zh' ? '未记录' : 'Not recorded');
                    const contextSecondary = [item.market, item.route || item.endpoint, item.component || item.feature]
                      .map((value) => String(value || '').trim())
                      .filter(Boolean)
                      .join(' · ');
                    const sourcePrimary = text(item.provider || item.source || item.category, locale === 'zh' ? '未记录' : 'Not recorded');
                    const sourceSecondary = [item.source && item.source !== item.provider ? item.source : null, item.category, item.type]
                      .map((value) => String(value || '').trim())
                      .filter(Boolean)
                      .filter((value, index, values) => values.indexOf(value) === index)
                      .join(' · ');
                    const severity = businessEventSeverity(item);
                    const reason = friendlyRawStatusLabel(item.reason || (isFailedStatus(item.status) ? 'unknown' : '--'), locale);
                    const errorSummary = friendlyRawStatusLabel(item.errorSummary || item.rootCauseSummary, locale);
                    const traceValue = item.traceId || item.requestId;
                    const stepLabel = stepStatsLabel(item, locale);
                    return (
                      <div key={item.id} data-testid="business-event-row" className="grid grid-cols-[6.25rem_minmax(0,1.15fr)_5.75rem_minmax(0,1fr)_4.5rem] items-center gap-3 px-3 py-2.5 md:grid-cols-[7.25rem_minmax(0,1.1fr)_7.5rem_minmax(0,1.35fr)_6rem] xl:grid-cols-[8.5rem_minmax(9rem,0.9fr)_8.5rem_minmax(13rem,1.25fr)_8rem_minmax(12rem,1.2fr)_minmax(10rem,1fr)_6rem]">
                        <p className="truncate text-xs text-secondary-text" title={formatDateTime(item.startedAt, locale)}>{formatDateTime(item.startedAt, locale)}</p>
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-foreground" title={text(item.event || item.symbol)}>{text(item.event || item.symbol)}</p>
                          <p className="mt-0.5 truncate text-[11px] text-muted-text" title={text(item.type)}>{text(item.eventType || item.type)}</p>
                        </div>
                        <div className="min-w-0 space-y-1">
                          <StatusChip status={status} locale={locale} className="w-fit" />
                          <SeverityChip severity={severity} locale={locale} className="w-fit" />
                        </div>
                        <div className="min-w-0">
                          <p className="line-clamp-2 text-xs font-medium leading-5 text-foreground" title={errorSummary || reason || stepLabel}>{errorSummary || reason || stepLabel}</p>
                          <p className="mt-1 truncate text-[11px] text-muted-text" title={stepLabel}>{stepLabel}</p>
                        </div>
                        <div className="hidden min-w-0 xl:block">
                          <TerminalChip variant={actorRole === 'admin' ? 'info' : actorRole === 'system' ? 'success' : actorRole === 'guest' || actorRole === 'anonymous' ? 'caution' : 'neutral'} className="w-fit font-semibold">{actorType}</TerminalChip>
                          <p className="mt-1 truncate text-[11px] text-muted-text" title={actorSecondary}>{actorSecondary}</p>
                        </div>
                        <div className="hidden min-w-0 xl:block">
                          <p className="truncate text-xs font-medium text-foreground" title={contextPrimary}>{contextPrimary}</p>
                          <p className="mt-1 truncate text-[11px] text-muted-text" title={contextSecondary || text(item.summary)}>{contextSecondary || text(item.summary)}</p>
                          <p className="mt-0.5 truncate text-[11px] text-muted-text" title={text(traceValue)}>{traceValue ? `trace ${shortIdentifier(traceValue)}` : '--'}</p>
                        </div>
                        <div className="hidden min-w-0 xl:block">
                          <p className="truncate text-xs text-secondary-text" title={sourcePrimary}>{sourcePrimary}</p>
                          <p className="mt-1 truncate text-[11px] text-muted-text" title={sourceSecondary}>{sourceSecondary || '--'}</p>
                        </div>
                        <TerminalButton type="button" variant="compact" className="w-fit px-2.5 py-1 text-xs" onClick={() => void openBusinessDetail(item)}>
                          {t('adminLogs.viewDetails')}
                        </TerminalButton>
                      </div>
                    );
                  })}
                </div>
                <div data-testid="admin-logs-pagination" className="flex flex-wrap items-center justify-between gap-3 border-t border-white/6 px-3 py-2.5">
                  <p className="text-xs text-muted-text">{locale === 'zh' ? `第 ${Math.floor(pageOffset / PAGE_SIZE) + 1} 页` : `Page ${Math.floor(pageOffset / PAGE_SIZE) + 1}`}</p>
                  <div className="flex gap-2">
                    <TerminalButton type="button" variant="compact" className="px-3 py-1 text-xs" disabled={pageOffset <= 0 || isLoadingList} onClick={() => setPageOffset((current) => Math.max(0, current - PAGE_SIZE))}>
                      {locale === 'zh' ? '上一页' : 'Previous'}
                    </TerminalButton>
                    <TerminalButton type="button" variant="compact" className="px-3 py-1 text-xs" disabled={!businessHasMore || isLoadingList} onClick={() => setPageOffset((current) => current + PAGE_SIZE)}>
                      {locale === 'zh' ? '下一页' : 'Next'}
                    </TerminalButton>
                  </div>
                </div>
              </TerminalDenseList>
            )
          ) : filteredSessions.length === 0 ? (
            <TerminalEmptyState className="mt-3 min-h-[88px]" title={t('adminLogs.noSessionsTitle')}>
              {t('adminLogs.noSessionsBody')}
            </TerminalEmptyState>
          ) : (
            <TerminalDenseTable data-testid="raw-logs-table-shell" className="mt-3 border-white/6 bg-black/15">
              <div className="min-w-[880px]">
                <div className="grid grid-cols-[9rem_5.5rem_7rem_minmax(10rem,1fr)_minmax(13rem,1.35fr)_minmax(9rem,1fr)_6rem] gap-3 border-b border-white/6 px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-white/38">
                  <div>{locale === 'zh' ? '时间' : 'Time'}</div>
                  <div>{locale === 'zh' ? '级别' : 'level'}</div>
                  <div>{locale === 'zh' ? '分类' : 'category'}</div>
                  <div>{locale === 'zh' ? '事件' : 'Event'}</div>
                  <div>{locale === 'zh' ? '消息' : 'message'}</div>
                  <div>{locale === 'zh' ? '来源 / 请求' : 'Source / request'}</div>
                  <div>{locale === 'zh' ? '操作' : 'Action'}</div>
                </div>
                <div className="max-h-[min(34vh,21rem)] divide-y divide-white/6 overflow-y-auto no-scrollbar">
                  {filteredSessions.map((item) => {
                    const summary = item.readableSummary || {};
                    const level = normalizeLogLevel(summary.logLevel);
                    const category = text(summary.logCategory, 'system');
                    const eventName = text(summary.eventName || item.name || item.taskId, t('adminLogs.unavailable'));
                    const message = text(summary.eventMessage || summary.topFailureReason || summary.summaryParagraph || summary.keyMetric, t('adminLogs.unavailable'));
                    const source = [summary.source, summary.requestId, summary.operationTarget || item.code]
                      .map((value) => String(value || '').trim())
                      .filter(Boolean)
                      .filter((value, index, values) => values.indexOf(value) === index)
                      .join(' · ') || t('adminLogs.unavailable');
                    return (
                      <div key={item.sessionId} data-testid="admin-log-row" className="grid grid-cols-[9rem_5.5rem_7rem_minmax(10rem,1fr)_minmax(13rem,1.35fr)_minmax(9rem,1fr)_6rem] items-center gap-3 px-3 py-2.5">
                        <p className="truncate text-xs text-secondary-text">{formatDateTime(item.startedAt, locale)}</p>
                        <AdminLogLevelPill value={level} locale={locale} />
                        <TerminalChip variant="neutral" className="w-fit">{categoryLabel(category, locale)}</TerminalChip>
                        <p className="min-w-0 truncate text-sm font-semibold text-foreground">{eventName}</p>
                        <p className="min-w-0 truncate text-xs text-secondary-text" title={message}>{message}</p>
                        <p className="min-w-0 truncate text-xs text-muted-text" title={source}>{source}</p>
                        <TerminalButton type="button" variant="compact" className="w-fit px-2.5 py-1 text-xs" onClick={() => void openDetail(item)}>
                          {t('adminLogs.viewDetails')}
                        </TerminalButton>
                      </div>
                    );
                  })}
                </div>
              </div>
            </TerminalDenseTable>
          )}
        </TerminalPanel>
      </TerminalPageShell>

      <Drawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        title={t('adminLogs.sessionDetailTitle')}
        width="max-w-[min(100vw,48rem)]"
      >
        {businessDetail ? (
          <div className="space-y-5">
            {detailError ? <ApiErrorAlert error={detailError} /> : null}
            {isLoadingDetail ? <p className="text-sm text-muted-text">{t('adminLogs.loading')}</p> : null}
            <TerminalPanel as="section" className="bg-black/25">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="mb-3 flex items-center gap-2">
                    <span className="inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.04] text-sm font-bold text-emerald-100">{text(businessDetail.category).slice(0, 1).toUpperCase()}</span>
                    <StatusChip status={drawerStatus} locale={locale} />
                    <SeverityChip severity={businessSeverity} locale={locale} />
                  </div>
                  <h2 className="break-words text-2xl font-semibold text-foreground">{text(businessDetail.event || businessDetail.symbol)}</h2>
                  <p className="mt-2 text-sm text-secondary-text">{businessDetail.summary} · {categoryLabel(businessDetail.category, locale)} · {text(businessDetail.type)} · {formatDateTime(businessDetail.startedAt, locale)}</p>
                </div>
                <div className="grid gap-2 text-xs text-secondary-text">
                  <TerminalButton type="button" variant="secondary" className="px-3 py-1.5 text-xs" onClick={() => void copyTextValue(buildBusinessDebugSummary(businessDetail))}>
                    {locale === 'zh' ? '复制执行摘要' : 'Copy execution summary'}
                  </TerminalButton>
                  <span>{locale === 'zh' ? '耗时' : 'Duration'}: <span className="text-foreground">{formatDuration(businessDetail.durationMs)}</span></span>
                  <span>{locale === 'zh' ? '步骤统计' : 'Step stats'}: <span className="text-foreground">{stepStatsLabel(businessDetail, locale)}</span></span>
                </div>
              </div>
              <div className="mt-4">
                <TerminalPanel data-testid="root-cause-section" dense className={summarySectionClass(businessSeverity)}>
                  <h3 className="text-sm font-semibold text-foreground">{summaryTitle(businessSeverity, locale)}</h3>
                  <div className="mt-3 grid gap-2 text-xs text-secondary-text md:grid-cols-2">
                    <p>{locale === 'zh' ? '状态' : 'Status'}: <span className="text-foreground">{statusLabel(drawerStatus, locale)}</span></p>
                    <p>{locale === 'zh' ? '原因' : 'Reason'}: <span className="text-foreground">{friendlyRawStatusLabel(businessDetail.reason || (locale === 'zh' ? '原因未确认' : 'Reason unknown'), locale)}</span></p>
                    <p>{locale === 'zh' ? '操作者' : 'Actor'}: <span className="text-foreground">{actorBadgeDisplay(businessDetail.actorType, locale)} · {businessActorLabel}</span></p>
                    <p>{locale === 'zh' ? '上下文' : 'Context'}: <span className="text-foreground">{businessContextLabel}</span></p>
                    <p>{locale === 'zh' ? '来源 / 供应商' : 'Source / Provider'}: <span className="text-foreground">{businessSourceLabel}</span></p>
                    <p>{locale === 'zh' ? '路由 / 端点' : 'Route / Endpoint'}: <span className="text-foreground">{text([businessDetail.route, businessDetail.endpoint].filter(Boolean).join(' / '), locale === 'zh' ? '未记录' : 'Not recorded')}</span></p>
                    <p>{locale === 'zh' ? '耗时' : 'Duration'}: <span className="text-foreground">{formatDuration(businessDetail.durationMs)}</span></p>
                    <p className="md:col-span-2">{locale === 'zh' ? '错误摘要' : 'Error summary'}: <span className="text-foreground" title={text(businessDetail.errorSummary || businessDetail.rootCauseSummary)}>{text(businessDetail.errorSummary || businessDetail.rootCauseSummary, locale === 'zh' ? '未记录' : 'Not recorded')}</span></p>
                    <p className="md:col-span-2">
                      {locale === 'zh' ? '请求 / trace id' : 'request/trace id'}: <span className="text-foreground">{text(businessTraceValue, locale === 'zh' ? '未记录' : 'Not recorded')}</span>
                      {businessTraceValue ? (
                        <TerminalButton type="button" variant="compact" className="ml-2 px-2 py-1 text-[11px]" onClick={() => void copyTextValue(businessTraceValue)}>
                          {locale === 'zh' ? '复制' : 'Copy'}
                        </TerminalButton>
                      ) : null}
                    </p>
                    <p className="md:col-span-2">{locale === 'zh' ? '步骤 trace' : 'Step trace'}: <span className="text-foreground">{traceAvailabilityLabel(businessDetail, locale)}</span></p>
                  </div>
                  {!businessDetail.reason ? (
                    <p className="mt-3 text-xs text-muted-text">{locale === 'zh' ? '原因未确认：该事件没有附加结构化 reason。' : 'Reason unknown: no structured reason was attached to this event.'}</p>
                  ) : null}
                </TerminalPanel>
              </div>
              <div className="mt-4">
                <AdminLogsTerminalSection title={locale === 'zh' ? '元数据' : 'Metadata'} defaultOpen={false} className="bg-black/20 px-3 py-3">
                  <JsonBlock value={businessDetail.metadata || {}} />
                </AdminLogsTerminalSection>
              </div>
            </TerminalPanel>

            {businessDetail.category === 'scanner' ? (
              <TerminalPanel data-testid="scanner-execution-summary">
                <TerminalSectionHeader
                  eyebrow={locale === 'zh' ? '扫描器执行' : 'SCANNER EXECUTION'}
                  title={locale === 'zh' ? '扫描器执行摘要' : 'Scanner execution summary'}
                />
                <div className="mt-4 grid gap-3 text-sm text-secondary-text md:grid-cols-3">
                  <p>{locale === 'zh' ? '市场 / 配置' : 'Market / config'}: <span className="text-foreground">{text([businessDetail.market, businessDetail.metadata?.configName || businessDetail.subject].filter(Boolean).join(' · '))}</span></p>
                  <p>{locale === 'zh' ? '评估 / 入选' : 'Evaluated / selected'}: <span className="text-foreground">{text(businessDetail.metadata?.evaluatedCount ?? businessDetail.metadata?.matchedCount ?? businessDetail.stepCount)} / {text(businessDetail.metadata?.selectedCount ?? businessDetail.metadata?.matchedCount ?? businessDetail.successStepCount)}</span></p>
                  <p>{locale === 'zh' ? '耗时' : 'Duration'}: <span className="text-foreground">{formatDuration(businessDetail.metadata?.durationMs ?? businessDetail.durationMs)}</span></p>
                  <p>{locale === 'zh' ? '数据失败 / 跳过' : 'Data failed / skipped'}: <span className="text-foreground">{text(businessDetail.metadata?.dataFailedCount ?? 0)} / {text(businessDetail.metadata?.skippedCount ?? businessDetail.skippedStepCount ?? 0)}</span></p>
                  <p>{locale === 'zh' ? 'Top 标的' : 'Top symbol'}: <span className="text-foreground">{text(businessDetail.metadata?.topSymbol)}</span></p>
                  <p>{locale === 'zh' ? '数据源摘要' : 'Provider summary'}: <span className="text-foreground">{text(businessDetail.metadata?.sourceProviderSummary || businessDetail.source)}</span></p>
                </div>
              </TerminalPanel>
            ) : null}

            <TerminalPanel>
              <TerminalSectionHeader
                eyebrow={locale === 'zh' ? '调用链' : 'CALL CHAIN'}
                title={locale === 'zh' ? '调用链时间线' : 'Call-chain timeline'}
              />
              <div className="mt-4 space-y-3">
                {businessSteps.length ? businessSteps.map((step: ExecutionStep, index: number) => {
                  const status = normalizeStatus(step.status);
                  return (
                    <AdminLogsTerminalSection key={`${step.name}-${index}`} title={`${text(step.label || step.name)} · ${formatDuration(step.durationMs)}`} summary={[step.category, step.provider, step.model, step.endpoint || step.apiPath].map((value) => String(value || '').trim()).filter(Boolean).join(' · ') || '--'} defaultOpen={index === 0 || status === 'failed' || status === 'error' || status === 'skipped' || status === 'unknown'} className="bg-black/20 px-3 py-3 text-xs">
                      <div className="mb-3 flex justify-end">
                        <StatusChip status={status} locale={locale} />
                      </div>
                      <div className="mt-3 grid gap-2 text-secondary-text md:grid-cols-2">
                        <p>{locale === 'zh' ? '开始' : 'Started'}: <span className="text-foreground">{formatDateTime(step.startedAt, locale)}</span></p>
                        <p>{locale === 'zh' ? '结束' : 'Finished'}: <span className="text-foreground">{formatDateTime(step.finishedAt, locale)}</span></p>
                        <p>{locale === 'zh' ? '原因' : 'Reason'}: <span className="text-foreground">{text(status === 'skipped' ? skippedReasonLabel(step.reason, locale) : step.reason)}</span></p>
                        <p>{locale === 'zh' ? '错误类型' : 'Error type'}: <span className="text-foreground">{text(step.errorType)}</span></p>
                        <p className="md:col-span-2">{locale === 'zh' ? '消息' : 'Message'}: <span className="text-foreground">{text(sanitizeDisplayValue(status === 'skipped' ? (step.message || skippedReasonLabel(step.reason, locale)) : (step.errorMessage || step.message)))}</span></p>
                        <div className="md:col-span-2">
                          <p className="text-[10px] uppercase tracking-[0.18em] text-white/36">{locale === 'zh' ? '元数据' : 'metadata'}</p>
                          <JsonBlock value={step.metadata || {}} />
                        </div>
                      </div>
                    </AdminLogsTerminalSection>
                  );
                }) : <p className="text-sm text-muted-text">{t('adminLogs.emptyTimelineBody')}</p>}
              </div>
            </TerminalPanel>
          </div>
        ) : drawerDetail ? (
          <div className="space-y-5">
            {detailError ? <ApiErrorAlert error={detailError} /> : null}
            {isLoadingDetail ? <p className="text-sm text-muted-text">{t('adminLogs.loading')}</p> : null}
            <TerminalPanel as="section" className="bg-black/25">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="mb-3 flex items-center gap-2">
                    <span className="inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.04] text-sm font-bold text-emerald-100">{operationIcon(drawerOperationType)}</span>
                    <StatusChip status={drawerStatus} locale={locale} />
                    <SeverityChip severity={rawSeverity} locale={locale} />
                  </div>
                  <h2 className="break-words text-2xl font-semibold text-foreground">
                    {text(operationDetail.target || readable.operationTarget || drawerDetail.name || drawerDetail.code)}
                  </h2>
                  <p className="mt-2 text-sm text-secondary-text">{operationLabel(drawerOperationType, locale)} · {formatDateTime(drawerDetail.startedAt, locale)}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <TerminalButton type="button" variant="secondary" className="px-3 py-1.5 text-xs" onClick={() => void copyTextValue(buildRawDebugSummary(drawerDetail))}>
                    {locale === 'zh' ? '复制执行摘要' : 'Copy execution summary'}
                  </TerminalButton>
                  <TerminalButton type="button" variant="secondary" className="px-3 py-1.5 text-xs" onClick={() => void copyLogJson(drawerDetail)}>
                    {t('adminLogs.copyDetails')}
                  </TerminalButton>
                  <TerminalButton type="button" variant="secondary" className="px-3 py-1.5 text-xs" onClick={() => downloadLogJson(drawerDetail)}>
                    {t('adminLogs.exportDetails')}
                  </TerminalButton>
                </div>
              </div>
              <div className="mt-5 grid gap-3 text-sm md:grid-cols-2 xl:grid-cols-4">
                <p className="text-secondary-text">{t('adminLogs.actor')}: <span className="text-foreground">{text(readable.actorDisplay || readable.actorUsername, 'admin')}</span></p>
                <p className="text-secondary-text">{t('adminLogs.actorRole')}: <span className="text-foreground">{rawActorRole === 'admin' ? t('adminLogs.role.admin') : rawActorRole === 'user' ? t('adminLogs.role.user') : text(readable.actorRole, t('adminLogs.unavailable'))}</span></p>
                <p className="text-secondary-text">{t('adminLogs.operationType')}: <span className="text-foreground">{text(operationDetail.operationType || readable.operationType || operationLabel(drawerOperationType, locale))}</span></p>
                <p className="text-secondary-text">{t('adminLogs.keyMetric')}: <span className="text-foreground">{text(operationDetail.keyMetric || readable.keyMetric, t('adminLogs.unavailable'))}</span></p>
              </div>
            </TerminalPanel>

            <TerminalPanel data-testid="root-cause-section" className={summarySectionClass(rawSeverity)}>
              <h3 className="text-sm font-semibold text-foreground">{summaryTitle(rawSeverity, locale)}</h3>
              <div className="mt-4 grid gap-2 text-sm text-secondary-text md:grid-cols-2">
                <p>{locale === 'zh' ? '状态' : 'Status'}: <span className="text-foreground">{statusLabel(drawerStatus, locale)}</span></p>
                <p>{locale === 'zh' ? '原因' : 'Reason'}: <span className="text-foreground">{friendlyRawStatusLabel(readable.reason || readable.topFailureReason || (locale === 'zh' ? '原因未确认' : 'Reason unknown'), locale)}</span></p>
                <p>{locale === 'zh' ? '操作者' : 'Actor'}: <span className="text-foreground">{actorBadgeDisplay(readable.actorType || readable.actorRole, locale)} · {text(readable.actorDisplay || readable.actorUsername || readable.actorSessionId, locale === 'zh' ? '未记录' : 'Not recorded')}</span></p>
                <p>{locale === 'zh' ? '上下文' : 'Context'}: <span className="text-foreground">{text(readable.contextLabel || readable.operationTarget || drawerDetail.code || drawerDetail.name, locale === 'zh' ? '未记录' : 'Not recorded')}</span></p>
                <p>{locale === 'zh' ? '来源 / 供应商' : 'Source / Provider'}: <span className="text-foreground">{text([readable.provider, readable.source].filter(Boolean).join(' / '), locale === 'zh' ? '未记录' : 'Not recorded')}</span></p>
                <p>{locale === 'zh' ? '路由 / 端点' : 'Route / Endpoint'}: <span className="text-foreground">{text(readable.endpoint, locale === 'zh' ? '未记录' : 'Not recorded')}</span></p>
                <p>{locale === 'zh' ? '耗时' : 'Duration'}: <span className="text-foreground">{formatDuration(operationDetail.durationMs || drawerDetail.summary?.durationMs)}</span></p>
                <p className="md:col-span-2">{locale === 'zh' ? '错误摘要' : 'Error summary'}: <span className="text-foreground" title={rawRootCause}>{rawRootCause}</span></p>
                <p className="md:col-span-2">
                  {locale === 'zh' ? '请求 / trace id' : 'request/trace id'}: <span className="text-foreground">{text(rawTraceValue, locale === 'zh' ? '未记录' : 'Not recorded')}</span>
                  {rawTraceValue ? (
                    <TerminalButton type="button" variant="compact" className="ml-2 px-2 py-1 text-[11px]" onClick={() => void copyTextValue(rawTraceValue)}>
                      {locale === 'zh' ? '复制' : 'Copy'}
                    </TerminalButton>
                  ) : null}
                </p>
                <p className="md:col-span-2">{locale === 'zh' ? '步骤 trace' : 'Step trace'}: <span className="text-foreground">{drawerDetail.events.length ? (locale === 'zh' ? '已记录事件明细' : 'Event trace attached') : (locale === 'zh' ? '未附加步骤级 trace。' : 'No step-level trace was attached to this event.')}</span></p>
              </div>
              {!(readable.reason || readable.topFailureReason) ? (
                <p className="mt-3 text-xs text-muted-text">{locale === 'zh' ? '原因未确认：该事件没有附加结构化 reason。' : 'Reason unknown: no structured reason was attached to this event.'}</p>
              ) : null}
            </TerminalPanel>

            {drawerOperationType === 'system_operation' ? (
              <TerminalPanel data-testid="system-operation-detail">
                <TerminalSectionHeader title={locale === 'zh' ? '系统操作详情' : 'System operation details'} />
                <div className="mt-4 grid gap-3 text-sm md:grid-cols-2">
                  <p className="text-secondary-text"><span>{locale === 'zh' ? '操作类型:' : 'Operation type:'}</span> <span className="text-foreground">{text(systemOperation.action || operationDetail.operationType || readable.operationType)}</span></p>
                  <p className="text-secondary-text"><span>{locale === 'zh' ? '操作用户:' : 'Operation user:'}</span> <span className="text-foreground">{text(systemOperation.actor || readable.actorDisplay || readable.actorUsername, 'admin')}</span></p>
                  <p className="text-secondary-text"><span>{locale === 'zh' ? '操作时间:' : 'Operation time:'}</span> <span className="text-foreground">{formatDateTime(systemOperation.time || drawerDetail.startedAt, locale)}</span></p>
                  <p className="text-secondary-text"><span>{locale === 'zh' ? '执行结果:' : 'Result:'}</span> <span className="text-foreground">{text(systemOperation.status || operationDetail.finalResult || operationDetail.status || readable.operationStatus)}</span></p>
                  <p className="text-secondary-text md:col-span-2"><span>{locale === 'zh' ? '失败原因:' : 'Failure reason:'}</span> <span className="text-foreground">{friendlyRawStatusLabel(systemOperation.reason || readable.topFailureReason || '--', locale)}</span></p>
                </div>
              </TerminalPanel>
            ) : null}

            <AdminLogsTerminalSection title={locale === 'zh' ? 'LLM 调用链' : 'LLM call chain'} defaultOpen={false} className="px-5 py-4">
              <div className="mt-4 space-y-3">
                {aiCalls.length ? aiCalls.map((item, index) => (
                  <CallCard key={`${text(item.model)}-${index}`} item={item} index={index} type="llm" locale={locale} />
                )) : <p className="text-sm text-muted-text">{t('adminLogs.emptyOperationTable')}</p>}
              </div>
            </AdminLogsTerminalSection>

            <AdminLogsTerminalSection title={locale === 'zh' ? '数据源调用' : 'Data source calls'} defaultOpen={false} className="px-5 py-4">
              <div className="mt-4 space-y-3">
                {dataSourceCalls.length ? dataSourceCalls.map((item, index) => (
                  <CallCard key={`${text(item.api || item.source)}-${index}`} item={item} index={index} type="data" locale={locale} />
                )) : <p className="text-sm text-muted-text">{t('adminLogs.emptyOperationTable')}</p>}
              </div>
            </AdminLogsTerminalSection>

            <section className="grid gap-4 xl:grid-cols-2">
              <AdminLogsTerminalSection title={locale === 'zh' ? '系统回退记录' : 'System fallback records'} defaultOpen={false} className="px-5 py-4">
                <div className="mt-4 space-y-2">
                  {systemFallbacks.length ? systemFallbacks.map((item, index) => (
                    <TerminalNotice key={`${text(item.source)}-${index}`} variant="caution">
                      {text(item.source)} · {text(item.message)}
                    </TerminalNotice>
                  )) : <p className="text-sm text-muted-text">{locale === 'zh' ? '暂无系统回退。' : 'No system fallback recorded.'}</p>}
                </div>
              </AdminLogsTerminalSection>
              <TerminalPanel>
                <TerminalSectionHeader title={locale === 'zh' ? '最终执行结果' : 'Final result'} />
                <p className="mt-3 text-sm leading-6 text-secondary-text">
                  {text(operationDetail.finalResult || readable.summaryParagraph || readable.topFailureReason || operationDetail.status || drawerDetail.overallStatus, t('adminLogs.unavailable'))}
                </p>
              </TerminalPanel>
            </section>

            <AdminLogsTerminalSection title={t('adminLogs.operationTimelineTitle')} defaultOpen={false} className="px-5 py-4">
              <div className="mt-4 space-y-2">
                {timeline.length ? timeline.map((item, index) => {
                  const status = normalizeStatus(String(item.status || ''));
                  return (
                    <TerminalNestedBlock key={`${text(item.label)}-${index}`} className="text-xs">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="font-medium text-foreground">{text(item.label)}</p>
                        <StatusChip status={status} locale={locale} />
                      </div>
                      <p className="mt-1 text-muted-text">{text(item.timestamp)} · {text(item.category)}</p>
                    </TerminalNestedBlock>
                  );
                }) : <p className="text-sm text-muted-text">{t('adminLogs.emptyTimelineBody')}</p>}
              </div>
            </AdminLogsTerminalSection>

            <AdminLogsTerminalSection title={locale === 'zh' ? '元数据详情' : 'Metadata detail'} defaultOpen={false} className="px-5 py-4">
              <div className="mt-4 space-y-3">
                {drawerDetail.events.length ? drawerDetail.events.map((event) => (
                  <TerminalNestedBlock key={event.id} className="text-xs">
                    <div className="flex flex-wrap items-center gap-2">
                      <AdminLogLevelPill value={event.level} locale={locale} className="w-fit font-semibold" />
                      <span className="text-secondary-text">{categoryLabel(event.category || event.phase, locale)}</span>
                      <span className="text-foreground">{text(event.eventName || event.step)}</span>
                    </div>
                    <JsonBlock value={event.detail || {}} />
                  </TerminalNestedBlock>
                )) : <p className="text-sm text-muted-text">{t('adminLogs.emptyTimelineBody')}</p>}
              </div>
            </AdminLogsTerminalSection>

            <AdminLogsTerminalSection title={t('adminLogs.diagnosticsTitle')} defaultOpen={false} className="border-rose-400/15 bg-rose-500/[0.025] px-5 py-4">
              <div className="mt-4 space-y-2">
                {diagnostics.length ? diagnostics.map((item, index) => (
                  <TerminalNotice key={`${text(item.source)}-${index}`} variant="danger">
                    <p>{text(item.message)}</p>
                    <p className="mt-1 text-muted-text">{text(item.source)} · {text(item.severity)}</p>
                  </TerminalNotice>
                )) : <p className="text-sm text-muted-text">{t('adminLogs.noDiagnostics')}</p>}
              </div>
            </AdminLogsTerminalSection>
          </div>
        ) : (
          <p className="text-sm text-muted-text">{t('adminLogs.selectSessionBody')}</p>
        )}
      </Drawer>
    </section>
  );
};

export default AdminLogsPage;
