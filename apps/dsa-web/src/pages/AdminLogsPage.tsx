import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { adminLogsApi, type AdminLogCleanupResponse, type AdminLogHealthSummary, type AdminLogStorageSummary, type BusinessEvent, type BusinessEventDetail, type BusinessEventListResponse, type ExecutionLogSessionDetail, type ExecutionLogSessionListResponse, type ExecutionLogSessionSummary, type ExecutionStep } from '../api/adminLogs';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import { ApiErrorAlert, Drawer, GlassCard } from '../components/common';
import { StatusBadge, getStatusLabel, normalizeStatus, type UnifiedStatus } from '../components/ui/StatusBadge';
import { useI18n } from '../contexts/UiLanguageContext';
import { formatDateTime as formatDateTimeValue, formatDurationMs } from '../utils/format';

type AdminLogsLanguage = 'zh' | 'en';
type TranslateFn = (key: string, params?: Record<string, string | number | undefined>) => string;
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

const LEVEL_CLASS: Record<LogLevel, string> = {
  DEBUG: 'border-white/10 bg-white/[0.04] text-white/50',
  INFO: 'border-white/10 bg-white/[0.05] text-white/62',
  NOTICE: 'border-cyan-300/25 bg-cyan-400/10 text-cyan-100',
  WARNING: 'border-amber-300/30 bg-amber-400/12 text-amber-100',
  ERROR: 'border-rose-300/35 bg-rose-500/14 text-rose-100',
  CRITICAL: 'border-red-300/45 bg-red-500/25 text-red-50 shadow-[0_0_24px_rgba(239,68,68,0.18)]',
};

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
    system: { zh: 'system', en: 'system' },
    auth: { zh: 'auth', en: 'auth' },
    market: { zh: 'market', en: 'market' },
    cache: { zh: 'cache', en: 'cache' },
    data_source: { zh: 'data_source', en: 'data_source' },
    analysis: { zh: 'analysis', en: 'analysis' },
    scanner: { zh: 'scanner', en: 'scanner' },
    backtest: { zh: 'backtest', en: 'backtest' },
    trading: { zh: 'trading', en: 'trading' },
    portfolio: { zh: 'portfolio', en: 'portfolio' },
    scheduler: { zh: 'scheduler', en: 'scheduler' },
    notification: { zh: 'notification', en: 'notification' },
    api: { zh: 'api', en: 'api' },
    security: { zh: 'security', en: 'security' },
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

function roleLabel(role: unknown, t: TranslateFn): string {
  const normalized = String(role || '').trim().toLowerCase();
  if (normalized === 'admin') return t('adminLogs.role.admin');
  if (normalized === 'user') return t('adminLogs.role.user');
  return text(role, t('adminLogs.unavailable'));
}

function asRecordList(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => !!item && typeof item === 'object' && !Array.isArray(item)) : [];
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function detailForSummary(summary: ExecutionLogSessionSummary): ExecutionLogSessionDetail {
  const mockDetail = MOCK_WOLFY_LOG_DETAILS.find((item) => item.sessionId === summary.sessionId);
  if (mockDetail) return mockDetail;
  return {
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
  };
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

function storageStatusLabel(value: string | undefined, locale: AdminLogsLanguage): string {
  const normalized = String(value || 'ok').toLowerCase();
  if (normalized === 'critical') return locale === 'zh' ? 'Critical' : 'Critical';
  if (normalized === 'warning') return locale === 'zh' ? 'Warning' : 'Warning';
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

function healthStatusLabel(status: unknown, locale: AdminLogsLanguage): string {
  const normalized = String(status || 'healthy').trim().toLowerCase();
  if (normalized === 'failing') return locale === 'zh' ? 'Failing' : 'Failing';
  if (normalized === 'degraded') return locale === 'zh' ? 'Degraded' : 'Degraded';
  return locale === 'zh' ? 'Healthy' : 'Healthy';
}

function healthStatusTone(status: unknown): string {
  const normalized = String(status || 'healthy').trim().toLowerCase();
  if (normalized === 'failing') return 'border-rose-300/30 bg-rose-500/10 text-rose-100';
  if (normalized === 'degraded') return 'border-amber-300/28 bg-amber-400/10 text-amber-100';
  return 'border-emerald-300/25 bg-emerald-400/10 text-emerald-100';
}

function compactHealthList(items: AdminLogHealthSummary['failuresByProvider'] | undefined): string {
  if (!items?.length) return '--';
  return items.slice(0, 3).map((item) => `${text(item.label || item.key)} ${item.count}`).join(' · ');
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
  if (severity === 'failed') return locale === 'zh' ? 'Failed' : 'Failed';
  if (severity === 'degraded') return locale === 'zh' ? 'Degraded' : 'Degraded';
  return locale === 'zh' ? 'Success' : 'Success';
}

function severityClass(severity: EventSeverity): string {
  if (severity === 'failed') return 'border-rose-300/25 bg-rose-500/10 text-rose-100';
  if (severity === 'degraded') return 'border-amber-300/25 bg-amber-400/10 text-amber-100';
  return 'border-emerald-300/20 bg-emerald-400/10 text-emerald-100';
}

function summaryTitle(severity: EventSeverity, locale: AdminLogsLanguage): string {
  if (severity === 'failed') return locale === 'zh' ? 'Root Cause' : 'Root Cause';
  if (severity === 'degraded') return locale === 'zh' ? 'Degradation Summary' : 'Degradation Summary';
  return locale === 'zh' ? 'Execution Summary' : 'Execution Summary';
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

function detailForBusinessEvent(event: BusinessEvent): BusinessEventDetail {
  return {
    ...event,
    steps: [],
  };
}

function JsonBlock({ value }: { value: unknown }) {
  if (value == null || value === '') return <span>--</span>;
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return <span>{String(value)}</span>;
  }
  return (
    <pre className="mt-2 max-h-44 overflow-auto rounded-xl border border-white/5 bg-black/30 p-3 text-[11px] leading-5 text-white/68">
      {JSON.stringify(sanitizeDisplayValue(value), null, 2)}
    </pre>
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
  const reason = text(item.reason || item.error || item.failureReason, '');
  const fallback = text(item.fallback || item.fallbackChain || item.retryFallback, '');
  return (
    <details className="rounded-2xl border border-white/6 bg-white/[0.025] p-4" open={index === 0}>
      <summary className="cursor-pointer list-none">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-[10px] uppercase tracking-[0.2em] text-white/36">{type === 'llm' ? 'LLM' : 'API'} #{index + 1}</p>
            <h4 className="mt-1 text-sm font-semibold text-foreground">{name}</h4>
          </div>
          <StatusBadge status={status} label={statusLabel(status, locale)} className="shrink-0" variant="soft" size="sm" />
        </div>
      </summary>
      <div className="mt-4 grid gap-4 text-xs text-secondary-text lg:grid-cols-2">
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
    </details>
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
      const response = await adminLogsApi.cleanupLogs({ useRetention: true, dryRun: true });
      setCleanupPreview(response);
      setCleanupMessage(`${response.matchedLogCount} logs would be deleted before ${formatDateTime(response.cutoff, locale)}.`);
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setIsCleanupBusy(false);
    }
  }, [locale]);

  const confirmCleanup = useCallback(async () => {
    const expectedCount = cleanupPreview?.matchedLogCount ?? storageSummary?.logsOlderThanRetentionCount ?? 0;
    const cutoff = cleanupPreview?.cutoff || storageSummary?.retentionCutoff || '';
    const confirmed = window.confirm(
      `Delete ${expectedCount} admin logs older than cutoff date ${formatDateTime(cutoff, locale)}? This action cannot be undone.`,
    );
    if (!confirmed) return;
    setIsCleanupBusy(true);
    setCleanupMessage(null);
    try {
      const response = await adminLogsApi.cleanupLogs({ useRetention: true, dryRun: false });
      setCleanupPreview(response);
      setCleanupMessage(`Deleted ${response.deletedLogCount} logs and ${response.deletedEventCount} events.`);
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
    setSelectedDetail(detailForSummary(summary));
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
    setSelectedBusinessDetail(detailForBusinessEvent(event));
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
  const topCategory = healthSummary.failuresByCategory?.[0];
  const latestCriticalError = healthSummary.latestCriticalError || healthSummary.topRecentErrors?.[0] || null;

  return (
    <section data-testid="admin-logs-workspace" className="flex min-h-0 w-full min-w-0 flex-1 flex-col gap-4 overflow-x-hidden">
      <GlassCard as="section" className="overflow-hidden p-0">
        <div className="relative px-4 py-4 sm:px-5">
          <div className="relative flex min-w-0 flex-col gap-4">
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-emerald-200/70">WolfyStock Ops Trace</p>
              <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">{t('adminLogs.pageTitle')}</h1>
              <p className="mt-1 max-w-4xl text-xs leading-5 text-secondary-text">{t('adminLogs.pageSubtitle')}</p>
              <div role="tablist" aria-label={locale === 'zh' ? '日志视图' : 'Log views'} className="mt-4 flex max-w-full gap-2 overflow-x-auto pb-1 sm:flex-wrap sm:overflow-visible">
                {(['business', 'analysis', 'scanner', 'backtest', 'data_source', 'security', 'raw'] as LogsTab[]).map((tab) => (
                  <button
                    key={tab}
                    type="button"
                    role="tab"
                    aria-selected={activeTab === tab}
                    className={`shrink-0 rounded-lg border px-3 py-1.5 text-xs font-semibold transition ${activeTab === tab ? 'border-emerald-300/45 bg-emerald-400/14 text-emerald-50' : 'border-white/8 bg-white/[0.035] text-secondary-text hover:border-white/15 hover:bg-white/[0.055]'}`}
                    onClick={() => setActiveTab(tab)}
                  >
                    {tabLabel(tab, locale)}
                  </button>
                ))}
              </div>
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
                    className="input-surface h-9 w-full min-w-0 rounded-lg px-3 text-sm"
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
                    className="input-surface h-9 w-full min-w-0 rounded-lg px-3 text-sm"
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
                placeholder={activeTab === 'analysis' ? 'TSLA / AAPL / NVDA' : (locale === 'zh' ? '事件 / request id / symbol / source / user' : 'Event / request id / symbol / source / user')}
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
              />
              {activeTab !== 'raw' ? (
                <select
                  aria-label={locale === 'zh' ? '状态筛选' : 'Status filter'}
                  className="input-surface h-9 w-full min-w-0 rounded-lg px-3 text-sm"
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
                className="input-surface h-9 w-full min-w-0 rounded-lg px-3 text-sm"
                value={sinceFilter}
                onChange={(event) => setSinceFilter(event.target.value as (typeof SINCE_OPTIONS)[number])}
              >
                {SINCE_OPTIONS.map((option) => (
                  <option key={option} value={option}>{sinceLabel(option, locale)}</option>
                ))}
              </select>
              {activeTab === 'raw' ? <button
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
              </button> : null}
              <button type="button" className="btn-secondary h-9 rounded-lg px-4 text-sm sm:col-span-2 xl:col-span-1" onClick={() => void loadSessions()} disabled={isLoadingList}>
                {isLoadingList ? t('adminLogs.loading') : t('adminLogs.refreshButton')}
              </button>
            </div>
            <p className="text-xs text-muted-text">{t('adminLogs.filterHintDetailed', { count: activeTab === 'raw' ? filteredSessions.length : businessTotal })}</p>
          </div>
        </div>
      </GlassCard>

      {error ? <ApiErrorAlert error={error} /> : null}

      <section
        data-testid="admin-logs-storage-summary"
        className="grid grid-cols-1 gap-2 rounded-xl border border-white/8 bg-black/20 p-2.5 sm:grid-cols-2 lg:grid-cols-[8rem_9rem_10rem_10rem_minmax(12rem,1fr)_auto]"
      >
        <div className={`rounded-lg border px-3 py-2 ${storageStatusTone(storageSummary?.status)}`}>
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] opacity-70">{locale === 'zh' ? 'Storage' : 'Storage'}</p>
          <p className="mt-1 text-base font-semibold">{storageStatusLabel(storageSummary?.status, locale)}</p>
        </div>
        <div className="rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-white/38">{locale === 'zh' ? 'Log count' : 'Log count'}</p>
          <p className="mt-1 text-base font-semibold text-foreground">{storageSummary?.totalLogCount ?? '--'}</p>
          <p className="text-[11px] text-muted-text">{storageSummary?.totalEventCount ?? '--'} events</p>
        </div>
        <div className="rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-white/38">{locale === 'zh' ? 'Retention' : 'Retention'}</p>
          <p className="mt-1 text-base font-semibold text-foreground">{storageSummary?.retentionDays ?? '--'} days</p>
          <p className="text-[11px] text-muted-text">{storageSummary?.logsOlderThanRetentionCount ?? 0} older</p>
        </div>
        <div className="rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-white/38">{locale === 'zh' ? 'Oldest' : 'Oldest'}</p>
          <p className="mt-1 truncate text-sm font-semibold text-foreground">{formatDateTime(storageSummary?.oldestLogTimestamp, locale)}</p>
          <p className="text-[11px] text-muted-text">{formatStorageBytes(storageSummary?.estimatedStorageBytes)}</p>
        </div>
        <div className="min-w-0 rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-white/38">{locale === 'zh' ? 'Cleanup guidance' : 'Cleanup guidance'}</p>
          <p className="mt-1 truncate text-sm text-foreground" title={storageSummary?.recommendedCleanupAction || ''}>
            {storageSummary?.recommendedCleanupAction || (locale === 'zh' ? 'Storage summary unavailable' : 'Storage summary unavailable')}
          </p>
          {cleanupMessage ? <p className="mt-1 text-[11px] text-emerald-100">{cleanupMessage}</p> : null}
        </div>
        <div className="flex min-w-0 flex-col gap-2 sm:flex-row lg:flex-col">
          <button
            type="button"
            className="btn-secondary h-9 rounded-lg px-3 text-xs"
            onClick={() => void previewCleanup()}
            disabled={isCleanupBusy || !storageSummary}
          >
            {isCleanupBusy ? t('adminLogs.loading') : 'Preview cleanup'}
          </button>
          <button
            type="button"
            className="rounded-lg border border-rose-300/25 bg-rose-500/10 px-3 py-2 text-xs font-semibold text-rose-100 transition hover:bg-rose-500/16 disabled:cursor-not-allowed disabled:opacity-50"
            onClick={() => void confirmCleanup()}
            disabled={isCleanupBusy || !storageSummary || (cleanupPreview?.matchedLogCount ?? storageSummary.logsOlderThanRetentionCount) <= 0}
          >
            Clean logs older than retention
          </button>
        </div>
      </section>

      <section
        data-testid="admin-logs-health-summary"
        className="grid grid-cols-1 gap-2 rounded-xl border border-white/8 bg-black/20 p-2.5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-[10rem_9rem_9rem_minmax(10rem,1fr)_minmax(10rem,1fr)_minmax(12rem,1.2fr)]"
      >
        <div className={`rounded-lg border px-3 py-2 ${healthStatusTone(healthSummary.status)}`}>
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] opacity-70">{locale === 'zh' ? 'Overall status' : 'Overall status'}</p>
          <p className="mt-1 text-base font-semibold">{healthStatusLabel(healthSummary.status, locale)}</p>
        </div>
        <div className="rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2 text-secondary-text">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-white/38">{locale === 'zh' ? 'Failures' : 'Failures'}</p>
          <p className="mt-1 text-base font-semibold text-foreground">{healthSummary.failedEvents} / {healthSummary.totalEvents}</p>
          <p className="text-[11px] text-muted-text">{Math.round((healthSummary.failureRate || 0) * 100)}% · {healthSummary.warningEvents} warning</p>
        </div>
        <div className="rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2 text-secondary-text">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-white/38">{locale === 'zh' ? 'Warnings' : 'Warnings'}</p>
          <p className="mt-1 text-base font-semibold text-foreground">{healthSummary.warningEvents}</p>
          <p className="text-[11px] text-muted-text">{healthSummary.slowEvents} slow</p>
        </div>
        <div className="min-w-0 rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-white/38">{locale === 'zh' ? 'Top failing feature' : 'Top failing feature'}</p>
          <p className="mt-1 truncate text-sm font-semibold text-foreground" title={text(topCategory?.label || topCategory?.key)}>{text(topCategory?.label || topCategory?.key)}</p>
          <p className="text-[11px] text-muted-text">{topCategory ? `${topCategory.count} events` : '--'}</p>
        </div>
        <div className="min-w-0 rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-white/38">{locale === 'zh' ? 'Provider / reason' : 'Provider / reason'}</p>
          <p className="mt-1 truncate text-sm text-foreground" title={compactHealthList(healthSummary.failuresByProvider)}>{compactHealthList(healthSummary.failuresByProvider)}</p>
          <p className="truncate text-[11px] text-muted-text" title={compactHealthList(healthSummary.failuresByReason)}>{compactHealthList(healthSummary.failuresByReason)}</p>
        </div>
        <div className="min-w-0 rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-white/38">{locale === 'zh' ? 'Latest critical error' : 'Latest critical error'}</p>
          <p className="mt-1 truncate text-sm font-semibold text-foreground" title={text(latestCriticalError?.event || latestCriticalError?.category)}>{text(latestCriticalError?.event || latestCriticalError?.category)}</p>
          <p className="truncate text-[11px] text-muted-text" title={text(latestCriticalError?.errorSummary || latestCriticalError?.reason)}>{text(latestCriticalError?.errorSummary || latestCriticalError?.reason)}</p>
        </div>
      </section>

      <GlassCard as="section" className="min-h-0 p-4">
        <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-foreground">{t('adminLogs.sessionListTitle')}</h2>
            <p className="mt-1 text-xs text-muted-text">{locale === 'zh' ? '点击查看详情会打开右侧抽屉，调用链和数据源可独立折叠。' : 'View Details opens a right drawer; LLM and data-source chains collapse independently.'}</p>
          </div>
          <p className="text-[10px] uppercase tracking-[0.22em] text-white/36">{activeTab === 'raw' ? filteredSessions.length : businessTotal} records</p>
        </div>
        {activeTab !== 'raw' ? (
          businessEvents.length === 0 ? (
            <div className="rounded-2xl bg-white/[0.02] px-4 py-6">
              <p className="text-sm font-medium text-foreground">{t('adminLogs.noSessionsTitle')}</p>
              <p className="mt-1 text-sm text-muted-text">{t('adminLogs.noSessionsBody')}</p>
            </div>
          ) : (
            <div className="overflow-hidden rounded-xl border border-white/6 bg-black/15">
              <div data-testid="business-events-table-shell" className="overflow-x-auto">
                <div className="min-w-[1040px]">
                  <div className="grid grid-cols-[8.5rem_minmax(9rem,0.9fr)_8.5rem_minmax(13rem,1.25fr)_8rem_minmax(12rem,1.2fr)_minmax(10rem,1fr)_6rem] gap-3 border-b border-white/6 px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-white/38">
                    <div>{locale === 'zh' ? '时间' : 'Time'}</div>
                    <div>{locale === 'zh' ? '事件' : 'Event'}</div>
                    <div>{locale === 'zh' ? '状态 / 严重度' : 'Status / Severity'}</div>
                    <div>{locale === 'zh' ? 'Reason' : 'Reason'}</div>
                    <div>{locale === 'zh' ? 'Actor' : 'Actor'}</div>
                    <div>{locale === 'zh' ? 'Context' : 'Context'}</div>
                    <div>{locale === 'zh' ? 'Source / Provider' : 'Source / Provider'}</div>
                    <div>{locale === 'zh' ? '操作' : 'Action'}</div>
                  </div>
                  <div className="max-h-[min(34vh,21rem)] divide-y divide-white/6 overflow-y-auto">
                    {businessEvents.map((item) => {
                      const status = normalizeStatus(item.status);
                      const actorType = actorBadgeLabel(item.actorType);
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
                      const reason = text(item.reason, isFailedStatus(item.status) ? 'unknown' : '--');
                      const errorSummary = text(item.errorSummary || item.rootCauseSummary, '');
                      const traceValue = item.traceId || item.requestId;
                      const stepLabel = stepStatsLabel(item, locale);
                      return (
                        <div key={item.id} data-testid="business-event-row" className="grid grid-cols-[8.5rem_minmax(9rem,0.9fr)_8.5rem_minmax(13rem,1.25fr)_8rem_minmax(12rem,1.2fr)_minmax(10rem,1fr)_6rem] items-center gap-3 px-3 py-2.5">
                          <p className="truncate text-xs text-secondary-text" title={formatDateTime(item.startedAt, locale)}>{formatDateTime(item.startedAt, locale)}</p>
                          <div className="min-w-0">
                            <p className="truncate text-sm font-semibold text-foreground" title={text(item.event || item.symbol)}>{text(item.event || item.symbol)}</p>
                            <p className="mt-0.5 truncate text-[11px] text-muted-text" title={text(item.type)}>{text(item.eventType || item.type)}</p>
                          </div>
                          <div className="min-w-0">
                            <StatusBadge status={status} label={statusLabel(status, locale)} variant="soft" size="sm" />
                            <span data-testid="event-severity-pill" className={`mt-1 inline-flex w-fit rounded-full border px-2 py-0.5 text-[11px] font-semibold ${severityClass(severity)}`}>
                              {severityLabel(severity, locale)}
                            </span>
                          </div>
                          <div className="min-w-0">
                            <p className="line-clamp-2 text-xs font-medium leading-5 text-foreground" title={errorSummary || reason || stepLabel}>{errorSummary || reason || stepLabel}</p>
                            <p className="mt-1 truncate text-[11px] text-muted-text" title={stepLabel}>{stepLabel}</p>
                          </div>
                          <div className="min-w-0">
                            <span className="inline-flex w-fit rounded-full border border-emerald-300/20 bg-emerald-400/10 px-2 py-0.5 text-[11px] font-semibold text-emerald-100">{actorType}</span>
                            <p className="mt-1 truncate text-[11px] text-muted-text" title={actorSecondary}>{actorSecondary}</p>
                          </div>
                          <div className="min-w-0">
                            <p className="truncate text-xs font-medium text-foreground" title={contextPrimary}>{contextPrimary}</p>
                            <p className="mt-1 truncate text-[11px] text-muted-text" title={contextSecondary || text(item.summary)}>{contextSecondary || text(item.summary)}</p>
                            <p className="mt-0.5 truncate text-[11px] text-muted-text" title={text(traceValue)}>{traceValue ? `trace ${shortIdentifier(traceValue)}` : '--'}</p>
                          </div>
                          <div className="min-w-0">
                            <p className="truncate text-xs text-secondary-text" title={sourcePrimary}>{sourcePrimary}</p>
                            <p className="mt-1 truncate text-[11px] text-muted-text" title={sourceSecondary}>{sourceSecondary || '--'}</p>
                          </div>
                          <button type="button" className="btn-secondary w-fit rounded-lg px-2.5 py-1 text-xs" onClick={() => void openBusinessDetail(item)}>
                            {t('adminLogs.viewDetails')}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
              <div data-testid="admin-logs-pagination" className="flex flex-wrap items-center justify-between gap-3 border-t border-white/6 px-3 py-2.5">
                <p className="text-xs text-muted-text">{locale === 'zh' ? `第 ${Math.floor(pageOffset / PAGE_SIZE) + 1} 页` : `Page ${Math.floor(pageOffset / PAGE_SIZE) + 1}`}</p>
                <div className="flex gap-2">
                  <button type="button" className="btn-secondary rounded-lg px-3 py-1 text-xs" disabled={pageOffset <= 0 || isLoadingList} onClick={() => setPageOffset((current) => Math.max(0, current - PAGE_SIZE))}>
                    {locale === 'zh' ? '上一页' : 'Previous'}
                  </button>
                  <button type="button" className="btn-secondary rounded-lg px-3 py-1 text-xs" disabled={!businessHasMore || isLoadingList} onClick={() => setPageOffset((current) => current + PAGE_SIZE)}>
                    {locale === 'zh' ? '下一页' : 'Next'}
                  </button>
                </div>
              </div>
            </div>
          )
        ) : filteredSessions.length === 0 ? (
          <div className="rounded-2xl bg-white/[0.02] px-4 py-6">
            <p className="text-sm font-medium text-foreground">{t('adminLogs.noSessionsTitle')}</p>
            <p className="mt-1 text-sm text-muted-text">{t('adminLogs.noSessionsBody')}</p>
          </div>
        ) : (
          <div className="overflow-hidden rounded-xl border border-white/6 bg-black/15">
            <div data-testid="raw-logs-table-shell" className="overflow-x-auto">
              <div className="min-w-[880px]">
                <div className="grid grid-cols-[9rem_5.5rem_7rem_minmax(10rem,1fr)_minmax(13rem,1.35fr)_minmax(9rem,1fr)_6rem] gap-3 border-b border-white/6 px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-white/38">
                  <div>{locale === 'zh' ? '时间' : 'Time'}</div>
                  <div>level</div>
                  <div>category</div>
                  <div>{locale === 'zh' ? '事件' : 'Event'}</div>
                  <div>message</div>
                  <div>{locale === 'zh' ? '来源 / 请求' : 'Source / request'}</div>
                  <div>{locale === 'zh' ? '操作' : 'Action'}</div>
                </div>
                <div className="max-h-[min(34vh,21rem)] divide-y divide-white/6 overflow-y-auto">
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
                        <span className={`inline-flex w-fit rounded-full border px-2 py-0.5 text-[11px] font-semibold ${LEVEL_CLASS[level]}`}>{level}</span>
                        <span className="inline-flex w-fit rounded-full border border-white/10 bg-white/[0.035] px-2 py-0.5 text-[11px] text-secondary-text">{categoryLabel(category, locale)}</span>
                        <p className="min-w-0 truncate text-sm font-semibold text-foreground">{eventName}</p>
                        <p className="min-w-0 truncate text-xs text-secondary-text" title={message}>{message}</p>
                        <p className="min-w-0 truncate text-xs text-muted-text" title={source}>{source}</p>
                        <button type="button" className="btn-secondary w-fit rounded-lg px-2.5 py-1 text-xs" onClick={() => void openDetail(item)}>
                          {t('adminLogs.viewDetails')}
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        )}
      </GlassCard>

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
            <section className="rounded-3xl border border-white/8 bg-black/25 p-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="mb-3 flex items-center gap-2">
                    <span className="inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.04] text-sm font-bold text-emerald-100">{text(businessDetail.category).slice(0, 1).toUpperCase()}</span>
                    <StatusBadge status={drawerStatus} label={statusLabel(drawerStatus, locale)} variant="soft" size="sm" />
                    <span className={`inline-flex min-h-6 items-center rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${severityClass(businessSeverity)}`}>
                      {severityLabel(businessSeverity, locale)}
                    </span>
                  </div>
                  <h2 className="break-words text-2xl font-semibold text-foreground">{text(businessDetail.event || businessDetail.symbol)}</h2>
                  <p className="mt-2 text-sm text-secondary-text">{businessDetail.summary} · {categoryLabel(businessDetail.category, locale)} · {text(businessDetail.type)} · {formatDateTime(businessDetail.startedAt, locale)}</p>
                </div>
                <div className="grid gap-2 text-xs text-secondary-text">
                  <button type="button" className="btn-secondary rounded-xl px-3 py-1.5 text-xs" onClick={() => void copyTextValue(buildBusinessDebugSummary(businessDetail))}>
                    {locale === 'zh' ? 'Copy debug summary' : 'Copy debug summary'}
                  </button>
                  <span>{locale === 'zh' ? '耗时' : 'Duration'}: <span className="text-foreground">{formatDuration(businessDetail.durationMs)}</span></span>
                  <span>{locale === 'zh' ? '步骤统计' : 'Step stats'}: <span className="text-foreground">{stepStatsLabel(businessDetail, locale)}</span></span>
                </div>
              </div>
              <div className="mt-4">
                <section data-testid="root-cause-section" className={`rounded-2xl border p-4 ${summarySectionClass(businessSeverity)}`}>
                  <h3 className="text-sm font-semibold text-foreground">{summaryTitle(businessSeverity, locale)}</h3>
                  <div className="mt-3 grid gap-2 text-xs text-secondary-text md:grid-cols-2">
                    <p>{locale === 'zh' ? '状态' : 'Status'}: <span className="text-foreground">{statusLabel(drawerStatus, locale)}</span></p>
                    <p>{locale === 'zh' ? '原因' : 'Reason'}: <span className="text-foreground">{text(businessDetail.reason, locale === 'zh' ? '原因未确认' : 'Reason unknown')}</span></p>
                    <p>{locale === 'zh' ? 'Actor' : 'Actor'}: <span className="text-foreground">{actorBadgeLabel(businessDetail.actorType)} · {businessActorLabel}</span></p>
                    <p>{locale === 'zh' ? 'Context' : 'Context'}: <span className="text-foreground">{businessContextLabel}</span></p>
                    <p>{locale === 'zh' ? 'Source / Provider' : 'Source / Provider'}: <span className="text-foreground">{businessSourceLabel}</span></p>
                    <p>{locale === 'zh' ? 'Route / Endpoint' : 'Route / Endpoint'}: <span className="text-foreground">{text([businessDetail.route, businessDetail.endpoint].filter(Boolean).join(' / '), locale === 'zh' ? '未记录' : 'Not recorded')}</span></p>
                    <p>{locale === 'zh' ? '耗时' : 'Duration'}: <span className="text-foreground">{formatDuration(businessDetail.durationMs)}</span></p>
                    <p className="md:col-span-2">{locale === 'zh' ? '错误摘要' : 'Error summary'}: <span className="text-foreground" title={text(businessDetail.errorSummary || businessDetail.rootCauseSummary)}>{text(businessDetail.errorSummary || businessDetail.rootCauseSummary, locale === 'zh' ? '未记录' : 'Not recorded')}</span></p>
                    <p className="md:col-span-2">
                      request/trace id: <span className="text-foreground">{text(businessTraceValue, locale === 'zh' ? '未记录' : 'Not recorded')}</span>
                      {businessTraceValue ? (
                        <button type="button" className="ml-2 text-[11px] font-semibold text-emerald-100 underline decoration-emerald-300/30 underline-offset-2" onClick={() => void copyTextValue(businessTraceValue)}>
                          {locale === 'zh' ? '复制' : 'Copy'}
                        </button>
                      ) : null}
                    </p>
                    <p className="md:col-span-2">{locale === 'zh' ? 'Step trace' : 'Step trace'}: <span className="text-foreground">{traceAvailabilityLabel(businessDetail, locale)}</span></p>
                  </div>
                  {!businessDetail.reason ? (
                    <p className="mt-3 text-xs text-muted-text">{locale === 'zh' ? '原因未确认：该事件没有附加结构化 reason。' : 'Reason unknown: no structured reason was attached to this event.'}</p>
                  ) : null}
                </section>
              </div>
              <div className="mt-4">
                <p className="text-[10px] uppercase tracking-[0.18em] text-white/36">metadata</p>
                <JsonBlock value={businessDetail.metadata || {}} />
              </div>
            </section>

            <section className="rounded-3xl border border-white/8 bg-white/[0.018] p-5">
              <h3 className="text-sm font-semibold text-foreground">{locale === 'zh' ? '调用链 timeline' : 'Call-chain timeline'}</h3>
              <div className="mt-4 space-y-3">
                {businessSteps.length ? businessSteps.map((step: ExecutionStep, index: number) => {
                  const status = normalizeStatus(step.status);
                  return (
                    <details key={`${step.name}-${index}`} className="rounded-2xl border border-white/6 bg-black/20 px-3 py-3 text-xs" open={index === 0 || status === 'failed' || status === 'error'}>
                      <summary className="cursor-pointer list-none">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div>
                            <p className="font-medium text-foreground">{text(step.label || step.name)} · {formatDuration(step.durationMs)}</p>
                            <p className="mt-1 text-muted-text">{[step.category, step.provider, step.model, step.endpoint || step.apiPath].map((value) => String(value || '').trim()).filter(Boolean).join(' · ') || '--'}</p>
                          </div>
                          <StatusBadge status={status} label={statusLabel(status, locale)} variant="soft" size="sm" />
                        </div>
                      </summary>
                      <div className="mt-3 grid gap-2 text-secondary-text md:grid-cols-2">
                        <p>{locale === 'zh' ? '开始' : 'Started'}: <span className="text-foreground">{formatDateTime(step.startedAt, locale)}</span></p>
                        <p>{locale === 'zh' ? '结束' : 'Finished'}: <span className="text-foreground">{formatDateTime(step.finishedAt, locale)}</span></p>
                        <p>{locale === 'zh' ? '原因' : 'Reason'}: <span className="text-foreground">{text(status === 'skipped' ? skippedReasonLabel(step.reason, locale) : step.reason)}</span></p>
                        <p>{locale === 'zh' ? '错误类型' : 'Error type'}: <span className="text-foreground">{text(step.errorType)}</span></p>
                        <p className="md:col-span-2">{locale === 'zh' ? '消息' : 'Message'}: <span className="text-foreground">{text(sanitizeDisplayValue(status === 'skipped' ? (step.message || skippedReasonLabel(step.reason, locale)) : (step.errorMessage || step.message)))}</span></p>
                        <div className="md:col-span-2">
                          <p className="text-[10px] uppercase tracking-[0.18em] text-white/36">metadata</p>
                          <JsonBlock value={step.metadata || {}} />
                        </div>
                      </div>
                    </details>
                  );
                }) : <p className="text-sm text-muted-text">{t('adminLogs.emptyTimelineBody')}</p>}
              </div>
            </section>
          </div>
        ) : drawerDetail ? (
          <div className="space-y-5">
            {detailError ? <ApiErrorAlert error={detailError} /> : null}
            {isLoadingDetail ? <p className="text-sm text-muted-text">{t('adminLogs.loading')}</p> : null}
            <section className="rounded-3xl border border-white/8 bg-black/25 p-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="mb-3 flex items-center gap-2">
                    <span className="inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.04] text-sm font-bold text-emerald-100">{operationIcon(drawerOperationType)}</span>
                    <StatusBadge status={drawerStatus} label={statusLabel(drawerStatus, locale)} variant="soft" size="sm" />
                    <span className={`inline-flex min-h-6 items-center rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${severityClass(rawSeverity)}`}>
                      {severityLabel(rawSeverity, locale)}
                    </span>
                  </div>
                  <h2 className="break-words text-2xl font-semibold text-foreground">
                    {text(operationDetail.target || readable.operationTarget || drawerDetail.name || drawerDetail.code)}
                  </h2>
                  <p className="mt-2 text-sm text-secondary-text">{operationLabel(drawerOperationType, locale)} · {formatDateTime(drawerDetail.startedAt, locale)}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button type="button" className="btn-secondary rounded-xl px-3 py-1.5 text-xs" onClick={() => void copyTextValue(buildRawDebugSummary(drawerDetail))}>
                    {locale === 'zh' ? 'Copy debug summary' : 'Copy debug summary'}
                  </button>
                  <button type="button" className="btn-secondary rounded-xl px-3 py-1.5 text-xs" onClick={() => void copyLogJson(drawerDetail)}>
                    {t('adminLogs.copyDetails')}
                  </button>
                  <button type="button" className="btn-secondary rounded-xl px-3 py-1.5 text-xs" onClick={() => downloadLogJson(drawerDetail)}>
                    {t('adminLogs.exportDetails')}
                  </button>
                </div>
              </div>
              <div className="mt-5 grid gap-3 text-sm md:grid-cols-2 xl:grid-cols-4">
                <p className="text-secondary-text">{t('adminLogs.actor')}: <span className="text-foreground">{text(readable.actorDisplay || readable.actorUsername, 'admin')}</span></p>
                <p className="text-secondary-text">{t('adminLogs.actorRole')}: <span className="text-foreground">{roleLabel(readable.actorRole, t)}</span></p>
                <p className="text-secondary-text">{t('adminLogs.operationType')}: <span className="text-foreground">{text(operationDetail.operationType || readable.operationType || operationLabel(drawerOperationType, locale))}</span></p>
                <p className="text-secondary-text">{t('adminLogs.keyMetric')}: <span className="text-foreground">{text(operationDetail.keyMetric || readable.keyMetric, t('adminLogs.unavailable'))}</span></p>
              </div>
            </section>

            <section data-testid="root-cause-section" className={`rounded-3xl border p-5 ${summarySectionClass(rawSeverity)}`}>
              <h3 className="text-sm font-semibold text-foreground">{summaryTitle(rawSeverity, locale)}</h3>
              <div className="mt-4 grid gap-2 text-sm text-secondary-text md:grid-cols-2">
                <p>{locale === 'zh' ? '状态' : 'Status'}: <span className="text-foreground">{statusLabel(drawerStatus, locale)}</span></p>
                <p>{locale === 'zh' ? '原因' : 'Reason'}: <span className="text-foreground">{text(readable.reason || readable.topFailureReason, locale === 'zh' ? '原因未确认' : 'Reason unknown')}</span></p>
                <p>{locale === 'zh' ? 'Actor' : 'Actor'}: <span className="text-foreground">{actorBadgeLabel(readable.actorType || readable.actorRole)} · {text(readable.actorDisplay || readable.actorUsername || readable.actorSessionId, locale === 'zh' ? '未记录' : 'Not recorded')}</span></p>
                <p>{locale === 'zh' ? 'Context' : 'Context'}: <span className="text-foreground">{text(readable.contextLabel || readable.operationTarget || drawerDetail.code || drawerDetail.name, locale === 'zh' ? '未记录' : 'Not recorded')}</span></p>
                <p>{locale === 'zh' ? 'Source / Provider' : 'Source / Provider'}: <span className="text-foreground">{text([readable.provider, readable.source].filter(Boolean).join(' / '), locale === 'zh' ? '未记录' : 'Not recorded')}</span></p>
                <p>{locale === 'zh' ? 'Route / Endpoint' : 'Route / Endpoint'}: <span className="text-foreground">{text(readable.endpoint, locale === 'zh' ? '未记录' : 'Not recorded')}</span></p>
                <p>{locale === 'zh' ? '耗时' : 'Duration'}: <span className="text-foreground">{formatDuration(operationDetail.durationMs || drawerDetail.summary?.durationMs)}</span></p>
                <p className="md:col-span-2">{locale === 'zh' ? '错误摘要' : 'Error summary'}: <span className="text-foreground" title={rawRootCause}>{rawRootCause}</span></p>
                <p className="md:col-span-2">
                  request/trace id: <span className="text-foreground">{text(rawTraceValue, locale === 'zh' ? '未记录' : 'Not recorded')}</span>
                  {rawTraceValue ? (
                    <button type="button" className="ml-2 text-[11px] font-semibold text-emerald-100 underline decoration-emerald-300/30 underline-offset-2" onClick={() => void copyTextValue(rawTraceValue)}>
                      {locale === 'zh' ? '复制' : 'Copy'}
                    </button>
                  ) : null}
                </p>
                <p className="md:col-span-2">{locale === 'zh' ? 'Step trace' : 'Step trace'}: <span className="text-foreground">{drawerDetail.events.length ? (locale === 'zh' ? '已记录事件明细' : 'Event trace attached') : (locale === 'zh' ? '未附加步骤级 trace。' : 'No step-level trace was attached to this event.')}</span></p>
              </div>
              {!(readable.reason || readable.topFailureReason) ? (
                <p className="mt-3 text-xs text-muted-text">{locale === 'zh' ? '原因未确认：该事件没有附加结构化 reason。' : 'Reason unknown: no structured reason was attached to this event.'}</p>
              ) : null}
            </section>

            {drawerOperationType === 'system_operation' ? (
              <section data-testid="system-operation-detail" className="rounded-3xl border border-white/8 bg-white/[0.018] p-5">
                <h3 className="text-sm font-semibold text-foreground">{locale === 'zh' ? '系统操作详情' : 'System operation details'}</h3>
                <div className="mt-4 grid gap-3 text-sm md:grid-cols-2">
                  <p className="text-secondary-text"><span>{locale === 'zh' ? '操作类型:' : 'Operation type:'}</span> <span className="text-foreground">{text(systemOperation.action || operationDetail.operationType || readable.operationType)}</span></p>
                  <p className="text-secondary-text"><span>{locale === 'zh' ? '操作用户:' : 'Operation user:'}</span> <span className="text-foreground">{text(systemOperation.actor || readable.actorDisplay || readable.actorUsername, 'admin')}</span></p>
                  <p className="text-secondary-text"><span>{locale === 'zh' ? '操作时间:' : 'Operation time:'}</span> <span className="text-foreground">{formatDateTime(systemOperation.time || drawerDetail.startedAt, locale)}</span></p>
                  <p className="text-secondary-text"><span>{locale === 'zh' ? '执行结果:' : 'Result:'}</span> <span className="text-foreground">{text(systemOperation.status || operationDetail.finalResult || operationDetail.status || readable.operationStatus)}</span></p>
                  <p className="text-secondary-text md:col-span-2"><span>{locale === 'zh' ? '失败原因:' : 'Failure reason:'}</span> <span className="text-foreground">{text(systemOperation.reason || readable.topFailureReason, '--')}</span></p>
                </div>
              </section>
            ) : null}

            <details className="rounded-3xl border border-white/8 bg-white/[0.018] p-5" open>
              <summary className="cursor-pointer text-sm font-semibold text-foreground">{locale === 'zh' ? 'LLM 调用链' : 'LLM call chain'}</summary>
              <div className="mt-4 space-y-3">
                {aiCalls.length ? aiCalls.map((item, index) => (
                  <CallCard key={`${text(item.model)}-${index}`} item={item} index={index} type="llm" locale={locale} />
                )) : <p className="text-sm text-muted-text">{t('adminLogs.emptyOperationTable')}</p>}
              </div>
            </details>

            <details className="rounded-3xl border border-white/8 bg-white/[0.018] p-5" open>
              <summary className="cursor-pointer text-sm font-semibold text-foreground">{locale === 'zh' ? '数据源调用' : 'Data source calls'}</summary>
              <div className="mt-4 space-y-3">
                {dataSourceCalls.length ? dataSourceCalls.map((item, index) => (
                  <CallCard key={`${text(item.api || item.source)}-${index}`} item={item} index={index} type="data" locale={locale} />
                )) : <p className="text-sm text-muted-text">{t('adminLogs.emptyOperationTable')}</p>}
              </div>
            </details>

            <section className="grid gap-4 xl:grid-cols-2">
              <details className="rounded-3xl border border-white/8 bg-white/[0.018] p-5" open>
                <summary className="cursor-pointer text-sm font-semibold text-foreground">{locale === 'zh' ? '系统回退记录' : 'System fallback records'}</summary>
                <div className="mt-4 space-y-2">
                  {systemFallbacks.length ? systemFallbacks.map((item, index) => (
                    <p key={`${text(item.source)}-${index}`} className="rounded-2xl border border-amber-300/15 bg-amber-400/5 px-3 py-2 text-xs text-amber-100">
                      {text(item.source)} · {text(item.message)}
                    </p>
                  )) : <p className="text-sm text-muted-text">{locale === 'zh' ? '暂无系统回退。' : 'No system fallback recorded.'}</p>}
                </div>
              </details>
              <section className="rounded-3xl border border-white/8 bg-white/[0.018] p-5">
                <h3 className="text-sm font-semibold text-foreground">{locale === 'zh' ? '最终执行结果' : 'Final result'}</h3>
                <p className="mt-3 text-sm leading-6 text-secondary-text">
                  {text(operationDetail.finalResult || readable.summaryParagraph || readable.topFailureReason || operationDetail.status || drawerDetail.overallStatus, t('adminLogs.unavailable'))}
                </p>
              </section>
            </section>

            <details className="rounded-3xl border border-white/8 bg-white/[0.018] p-5" open>
              <summary className="cursor-pointer text-sm font-semibold text-foreground">{t('adminLogs.operationTimelineTitle')}</summary>
              <div className="mt-4 space-y-2">
                {timeline.length ? timeline.map((item, index) => {
                  const status = normalizeStatus(String(item.status || ''));
                  return (
                    <div key={`${text(item.label)}-${index}`} className="rounded-2xl border border-white/6 bg-black/20 px-3 py-3 text-xs">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="font-medium text-foreground">{text(item.label)}</p>
                        <StatusBadge status={status} label={statusLabel(status, locale)} variant="soft" size="sm" />
                      </div>
                      <p className="mt-1 text-muted-text">{text(item.timestamp)} · {text(item.category)}</p>
                    </div>
                  );
                }) : <p className="text-sm text-muted-text">{t('adminLogs.emptyTimelineBody')}</p>}
              </div>
            </details>

            <details className="rounded-3xl border border-white/8 bg-white/[0.018] p-5" open>
              <summary className="cursor-pointer text-sm font-semibold text-foreground">{locale === 'zh' ? 'metadata 详情' : 'Metadata detail'}</summary>
              <div className="mt-4 space-y-3">
                {drawerDetail.events.length ? drawerDetail.events.map((event) => (
                  <div key={event.id} className="rounded-2xl border border-white/6 bg-black/20 px-3 py-3 text-xs">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`inline-flex rounded-full border px-2 py-0.5 font-semibold ${LEVEL_CLASS[normalizeLogLevel(event.level)]}`}>{normalizeLogLevel(event.level)}</span>
                      <span className="text-secondary-text">{categoryLabel(event.category || event.phase, locale)}</span>
                      <span className="text-foreground">{text(event.eventName || event.step)}</span>
                    </div>
                    <JsonBlock value={event.detail || {}} />
                  </div>
                )) : <p className="text-sm text-muted-text">{t('adminLogs.emptyTimelineBody')}</p>}
              </div>
            </details>

            <details className="rounded-3xl border border-rose-400/15 bg-rose-500/[0.025] p-5" open>
              <summary className="cursor-pointer text-sm font-semibold text-foreground">{t('adminLogs.diagnosticsTitle')}</summary>
              <div className="mt-4 space-y-2">
                {diagnostics.length ? diagnostics.map((item, index) => (
                  <div key={`${text(item.source)}-${index}`} className="rounded-2xl border border-rose-400/15 bg-rose-500/5 px-3 py-3 text-xs">
                    <p className="text-rose-100">{text(item.message)}</p>
                    <p className="mt-1 text-muted-text">{text(item.source)} · {text(item.severity)}</p>
                  </div>
                )) : <p className="text-sm text-muted-text">{t('adminLogs.noDiagnostics')}</p>}
              </div>
            </details>
          </div>
        ) : (
          <p className="text-sm text-muted-text">{t('adminLogs.selectSessionBody')}</p>
        )}
      </Drawer>
    </section>
  );
};

export default AdminLogsPage;
