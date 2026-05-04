import React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowDownUp,
  BookmarkCheck,
  BookmarkPlus,
  ChevronDown,
  ChevronRight,
  Clock,
  Copy,
  Download,
  History,
  Info,
  LayoutGrid,
  LineChart,
  MoreHorizontal,
  Play,
  Sparkles,
  Table2,
  TestTubeDiagonal,
} from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { analysisApi, DuplicateTaskError } from '../api/analysis';
import { backtestApi } from '../api/backtest';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { scannerApi } from '../api/scanner';
import { watchlistApi } from '../api/watchlist';
import { ApiErrorAlert, Drawer, Pagination, PillBadge, SectionShell } from '../components/common';
import { getDefaultRuleDateRange } from '../components/backtest/shared';
import { buildPointAndShootStrategyText } from '../components/backtest/strategyCatalog';
import { useI18n } from '../contexts/UiLanguageContext';
import {
  getSafariReadySurfaceClassName,
  shouldApplySafariA11yGuard,
  useSafariRenderReady,
  useSafariWarmActivation,
} from '../hooks/useSafariInteractionReady';
import type {
  ScannerCandidate,
  ScannerCandidateDiagnostic,
  ScannerCandidateDiagnosticStatus,
  ScannerCandidateOutcome,
  ScannerCoverageSummary,
  ScannerLabeledValue,
  ScannerProviderDiagnostics,
  ScannerReviewSummary,
  ScannerRunDetail,
  ScannerRunHistoryItem,
  ScannerStrategySimulationResult,
  ScannerThemeSuggestion,
  ScannerTheme,
  ScannerWatchlistComparison,
} from '../types/scanner';
import type { RuleBacktestRunResponse } from '../types/backtest';
import type { WatchlistItem } from '../types/watchlist';
import { buildLocalizedPath } from '../utils/localeRouting';
import {
  getScannerDetailOptions,
  getScannerProfileOptions,
  getScannerUniverseOptions,
  SCANNER_PROFILE_DEFAULTS,
} from './scannerPageShared';

const HISTORY_PAGE_SIZE = 8;
const SCANNER_BACKTEST_CONCURRENCY = 2;
const SCANNER_BACKTEST_INITIAL_CAPITAL = 100000;
const SCANNER_BACKTEST_FEE_BPS = 0;
const SCANNER_BACKTEST_SLIPPAGE_BPS = 0;
const SCANNER_BACKTEST_BENCHMARK_MODE = 'auto';

type PillOption = { value: string; label: string };
type ViewMode = 'cards' | 'table';
type CandidateFilter = 'selected' | 'pool' | 'rejected' | 'data_failed' | 'all';
type SortKey = 'score' | 'symbol' | 'target' | 'risk';
type SortDirection = 'asc' | 'desc';
type ScanScope = 'default' | 'theme' | 'symbols';
type ActionNotice = { tone: 'success' | 'warning' | 'danger'; message: string } | null;
type ScannerBacktestStatus = 'idle' | 'queued' | 'running' | 'completed' | 'failed' | 'skipped_existing';
type ScannerBacktestSource = 'official_selected' | 'preview_selected' | 'top_5' | 'current_filter' | 'manual';
type ScannerDisclosureIcon = 'info' | 'history' | 'backtest' | 'watchlist' | 'more';
type ScannerBacktestItem = {
  symbol: string;
  status: ScannerBacktestStatus;
  resultId?: number | string;
  totalReturnPct?: number | null;
  maxDrawdownPct?: number | null;
  sharpe?: number | null;
  tradeCount?: number | null;
  error?: string | null;
};
type ScannerComparisonState = {
  previousRun: ScannerRunDetail | null;
  bySymbol: Map<string, CandidateComparison>;
  chips: string[];
};
type CandidateComparison = {
  scoreDelta: number | null;
  previousStatus: ScannerCandidateDiagnosticStatus | null;
  currentStatus: ScannerCandidateDiagnosticStatus;
  label: string;
};
type ScannerValidationErrors = {
  run?: string;
  customSymbols?: string;
  theme?: string;
  customThemeLabel?: string;
  customThemePrompt?: string;
  customThemeManualSymbols?: string;
};

function normalizeCandidateSymbol(symbol?: string | null): string | null {
  const normalized = String(symbol || '').trim().toUpperCase();
  return normalized || null;
}

function getCandidateIdentity(candidate: ScannerCandidate): string {
  return normalizeCandidateSymbol(candidate.symbol) || `no-symbol-${candidate.rank}`;
}

function normalizeScannerMarket(market?: string | null): string | null {
  const normalized = String(market || '').trim().toUpperCase();
  return normalized === 'CN' || normalized === 'US' || normalized === 'HK' ? normalized : null;
}

function getWatchlistIdentity(market?: string | null, symbol?: string | null): string {
  const normalizedMarket = normalizeScannerMarket(market);
  const normalizedSymbol = normalizeCandidateSymbol(symbol);
  return normalizedMarket && normalizedSymbol ? `${normalizedMarket}:${normalizedSymbol}` : normalizedSymbol || '';
}

function buildWatchlistNotes(candidate: ScannerCandidate, runDetail: ScannerRunDetail | null, language: 'zh' | 'en'): string | null {
  const notes = [
    getKeyReason(candidate, runDetail, language),
    getRiskSummary(candidate, language),
    candidate.aiInterpretation?.watchPlan,
  ].filter((item): item is string => Boolean(item));
  return notes.length ? notes.slice(0, 3).join(language === 'en' ? ' | ' : ' ｜ ') : null;
}

function getWatchlistActionLabel(
  isTracked: boolean,
  isPending: boolean,
  isAuthBlocked: boolean,
  language: 'zh' | 'en',
): string {
  if (isPending) {
    return language === 'en' ? 'Saving...' : '保存中...';
  }
  if (isTracked) {
    return language === 'en' ? 'Tracked' : '已追踪';
  }
  if (isAuthBlocked) {
    return language === 'en' ? 'Sign in to track' : '登录后可追踪';
  }
  return language === 'en' ? 'Track' : '追踪';
}

function getWatchlistActionTitle(
  isTracked: boolean,
  isAuthBlocked: boolean,
  language: 'zh' | 'en',
): string | undefined {
  if (isTracked) {
    return language === 'en' ? 'This candidate is already tracked.' : '该候选已在观察名单中。';
  }
  if (isAuthBlocked) {
    return language === 'en' ? 'Sign in to save candidates to your watchlist.' : '请登录后再保存候选到你的观察名单。';
  }
  return language === 'en' ? 'Save this candidate to your watchlist.' : '保存到你的观察名单。';
}

function ScannerEmptyState({
  title,
  body,
  className = '',
}: {
  title: string;
  body: string;
  className?: string;
}) {
  return (
    <div className={`w-full flex flex-col items-center justify-center py-10 px-4 border border-white/5 border-dashed rounded-2xl bg-white/[0.01] ${className}`.trim()}>
      <div className="w-10 h-10 rounded-full bg-white/[0.02] border border-white/5 flex items-center justify-center mb-3">
        <svg className="w-5 h-5 text-white/20" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
      </div>
      <p className="text-white/40 text-sm font-medium text-center">{title}</p>
      <p className="text-white/20 text-xs mt-1 text-center">{body}</p>
    </div>
  );
}

function normalizeLabel(label?: string | null): string {
  return (label || '').trim().toLowerCase();
}

function toDisplayText(value: unknown): string | null {
  if (value == null) return null;
  if (typeof value === 'string') return value.trim() || null;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function parseFirstNumericValue(value?: string | null): number | null {
  if (!value) return null;
  const match = value.match(/-?\d+(?:\.\d+)?/);
  if (!match) return null;
  const parsed = Number.parseFloat(match[0]);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatPercent(value?: number | null): string {
  if (value == null || !Number.isFinite(value)) return '--';
  return `${value > 0 ? '+' : ''}${value.toFixed(1)}%`;
}

function formatMetricNumber(value?: number | null, digits = 2): string {
  if (value == null || !Number.isFinite(value)) return '--';
  return value.toFixed(digits);
}

function formatTimestamp(value?: string | null, language: 'zh' | 'en' = 'zh'): string {
  if (!value) return '--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(language === 'en' ? 'en-US' : 'zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function formatDateOnly(value?: string | null, language: 'zh' | 'en' = 'zh'): string {
  if (!value) return '--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(language === 'en' ? 'en-US' : 'zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date);
}

function scoreBadgeClass(score: number): string {
  if (score >= 90) return 'bg-white/[0.08] text-white border-white/12';
  if (score >= 80) return 'bg-indigo-500/12 text-indigo-200 border-indigo-500/20';
  return 'bg-white/[0.04] text-white/72 border-white/10';
}

function findCandidateValue(
  candidate: ScannerCandidate,
  keywords: string[],
): string | null {
  const entries = [
    ...(candidate.keyMetrics || []),
    ...(candidate.watchContext || []),
    ...(candidate.featureSignals || []),
  ];
  const match = entries.find((entry) => keywords.some((keyword) => normalizeLabel(entry.label).includes(keyword)));
  return match?.value?.trim() || null;
}

function getEntryRange(candidate: ScannerCandidate): string | null {
  return findCandidateValue(candidate, ['建仓', '入场', 'entry', 'buy', 'support']);
}

function getTargetPrice(candidate: ScannerCandidate): string | null {
  return findCandidateValue(candidate, ['目标', 'target', 'tp', 'resistance']);
}

function getStopLoss(candidate: ScannerCandidate): string | null {
  return findCandidateValue(candidate, ['止损', 'stop', 'invalid']);
}

function getRiskScore(candidate: ScannerCandidate): number | null {
  const riskValue = findCandidateValue(candidate, ['risk score', 'risk/score', '风险评分', '风险分']);
  return parseFirstNumericValue(riskValue);
}

function getRiskSummary(candidate: ScannerCandidate, language: 'zh' | 'en'): string {
  return candidate.riskNotes?.[0] || candidate.aiInterpretation?.riskInterpretation || (language === 'en' ? 'No risk note provided' : '未提供风险说明');
}

function getKeyReason(candidate: ScannerCandidate, runDetail: ScannerRunDetail | null, language: 'zh' | 'en'): string {
  return candidate.reasonSummary
    || candidate.reasons?.[0]
    || candidate.featureSignals?.[0]?.value
    || runDetail?.scoringNotes?.[0]
    || (language === 'en' ? 'No selection note provided' : '未提供入选说明');
}

function getSourceBadge(candidate: ScannerCandidate, runDetail: ScannerRunDetail | null, language: 'zh' | 'en'): string | null {
  const candidateProvider = getProviderDiagnostics(candidate.diagnostics)?.quoteSourceUsed
    || getProviderDiagnostics(candidate.diagnostics)?.snapshotSourceUsed
    || getProviderDiagnostics(candidate.diagnostics)?.historySourceUsed;
  const runProvider = runDetail ? getRunProviderDiagnostics(runDetail)?.quoteSourceUsed
    || getRunProviderDiagnostics(runDetail)?.snapshotSourceUsed
    || getRunProviderDiagnostics(runDetail)?.historySourceUsed : null;
  return candidateProvider || runProvider || runDetail?.sourceSummary || (language === 'en' ? 'scanner payload' : '扫描载荷');
}

function getRunCoverageSummary(runDetail: ScannerRunDetail): ScannerCoverageSummary | null {
  const diagnostics = runDetail.diagnostics || {};
  return isRecord(diagnostics.coverageSummary) ? diagnostics.coverageSummary as unknown as ScannerCoverageSummary : null;
}

function getProviderDiagnostics(value?: ScannerRunDetail['diagnostics'] | ScannerCandidate['diagnostics']): ScannerProviderDiagnostics | null {
  if (!value) return null;
  const diagnostics = value as Record<string, unknown>;
  return isRecord(diagnostics.providerDiagnostics) ? diagnostics.providerDiagnostics as unknown as ScannerProviderDiagnostics : null;
}

function getRunProviderDiagnostics(runDetail: ScannerRunDetail): ScannerProviderDiagnostics | null {
  return getProviderDiagnostics(runDetail.diagnostics);
}

function getAiDiagnostics(runDetail: ScannerRunDetail): Record<string, unknown> | null {
  const diagnostics = runDetail.diagnostics || {};
  return isRecord(diagnostics.aiInterpretation) ? diagnostics.aiInterpretation : null;
}

function getCandidateDiagnostics(runDetail: ScannerRunDetail | null): ScannerCandidateDiagnostic[] {
  return Array.isArray(runDetail?.candidates) ? runDetail.candidates : [];
}

function getDiagnosticReason(candidate: ScannerCandidateDiagnostic, language: 'zh' | 'en'): string {
  return candidate.reason
    || candidate.failedRules?.[0]?.replace(/_/g, ' ')
    || candidate.missingFields?.[0]
    || (language === 'en' ? 'No diagnostic reason' : '未提供诊断原因');
}

function normalizeDiagnosticText(value?: string | null): string {
  return String(value || '').trim().toLowerCase().replace(/[_-]+/g, ' ');
}

function formatFriendlyProvider(value?: string | null, language: 'zh' | 'en' = 'zh'): string {
  const normalized = normalizeDiagnosticText(value);
  if (!normalized) return '--';
  if (normalized.includes('local db') || normalized.includes('local')) return language === 'en' ? 'Local data' : '本地数据';
  if (normalized.includes('alpaca')) return 'Alpaca';
  return String(value || '').trim();
}

function formatFriendlyDiagnosticReason(candidate: ScannerCandidateDiagnostic, language: 'zh' | 'en'): string {
  const rawReason = getDiagnosticReason(candidate, language);
  const text = [
    candidate.status,
    candidate.reason,
    ...(candidate.failedRules || []),
    ...(candidate.missingFields || []),
  ].map(normalizeDiagnosticText).join(' ');
  if (normalizeDiagnosticStatus(candidate.status) === 'selected') {
    return language === 'en' ? 'Passed screening' : '通过筛选';
  }
  if (candidate.status === 'data_failed' || candidate.status === 'error') return language === 'en' ? 'Data thin' : '数据不足';
  if (/missing|history|quote|data|field|not enough|unavailable/.test(text)) return language === 'en' ? 'Data thin' : '数据不足';
  if (/liquidity|volume|turnover|amount/.test(text)) return language === 'en' ? 'Liquidity weak' : '流动性不足';
  if (/price/.test(text)) return language === 'en' ? 'Price below threshold' : '价格低于阈值';
  if (/momentum|relative strength|strength|return/.test(text)) return language === 'en' ? 'Momentum weak' : '动量不足';
  if (/trend|moving average|breakout|\bma\b/.test(text)) return language === 'en' ? 'Trend weak' : '趋势不足';
  if (/score|threshold|rank/.test(text)) return language === 'en' ? 'Score below threshold' : '分数低于阈值';
  if (/passed/.test(normalizeDiagnosticText(rawReason))) return language === 'en' ? 'Passed screening' : '通过筛选';
  return rawReason;
}

function formatCandidateDataQuality(candidate: ScannerCandidateDiagnostic, language: 'zh' | 'en'): string {
  const status = normalizeDiagnosticStatus(candidate.status);
  const text = [
    candidate.reason,
    ...(candidate.failedRules || []),
    ...(candidate.missingFields || []),
  ].map(normalizeDiagnosticText).join(' ');
  if (/quote|realtime|snapshot/.test(text)) return language === 'en' ? 'Realtime missing' : '实时缺失';
  if (status === 'data_failed' || status === 'error' || /missing|history|data|field|not enough|unavailable/.test(text)) {
    return language === 'en' ? 'Data thin' : '数据不足';
  }
  const provider = formatFriendlyProvider(candidate.provider, language);
  if (provider === (language === 'en' ? 'Local data' : '本地数据')) return provider;
  return language === 'en' ? 'Verified' : '已验证';
}

function normalizeDiagnosticStatus(status: ScannerCandidateDiagnostic['status']): ScannerCandidateDiagnosticStatus {
  return status || 'skipped';
}

function diagnosticStatusLabel(status: ScannerCandidateDiagnostic['status'], language: 'zh' | 'en'): string {
  const labels: Record<ScannerCandidateDiagnosticStatus, { zh: string; en: string }> = {
    selected: { zh: '入选', en: 'Selected' },
    rejected: { zh: '淘汰', en: 'Rejected' },
    data_failed: { zh: '数据失败', en: 'Data failed' },
    skipped: { zh: '跳过', en: 'Skipped' },
    error: { zh: '错误', en: 'Error' },
    evaluated: { zh: '已评估', en: 'Evaluated' },
  };
  const normalizedStatus = normalizeDiagnosticStatus(status);
  return labels[normalizedStatus]?.[language] || normalizedStatus;
}

function diagnosticStatusClass(status: ScannerCandidateDiagnostic['status']): string {
  const normalizedStatus = normalizeDiagnosticStatus(status);
  if (normalizedStatus === 'selected') return 'border-emerald-400/25 bg-emerald-400/10 text-emerald-100 shadow-[0_0_18px_rgba(16,185,129,0.12)]';
  if (normalizedStatus === 'rejected') return 'border-white/10 bg-white/[0.035] text-white/58';
  if (normalizedStatus === 'data_failed' || normalizedStatus === 'error') return 'border-rose-400/25 bg-rose-400/10 text-rose-100 shadow-[0_0_18px_rgba(244,63,94,0.10)]';
  return 'border-amber-400/20 bg-amber-400/10 text-amber-100';
}

function diagnosticScoreValue(candidate: ScannerCandidateDiagnostic): string {
  return candidate.score == null ? 'DATA' : `${candidate.score}/100`;
}

function isOfficialSelected(candidate: ScannerCandidateDiagnostic): boolean {
  return normalizeDiagnosticStatus(candidate.status) === 'selected';
}

function isDataUnavailable(candidate: ScannerCandidateDiagnostic): boolean {
  const status = normalizeDiagnosticStatus(candidate.status);
  return status === 'data_failed' || status === 'error' || status === 'skipped';
}

function isPreviewSelected(candidate: ScannerCandidateDiagnostic, threshold: number): boolean {
  return candidate.score != null && Number.isFinite(candidate.score) && candidate.score >= threshold && !isDataUnavailable(candidate);
}

function getScannerBacktestConfig() {
  const { startDate, endDate } = getDefaultRuleDateRange();
  return {
    startDate,
    endDate,
    initialCapital: SCANNER_BACKTEST_INITIAL_CAPITAL,
    feeBps: SCANNER_BACKTEST_FEE_BPS,
    slippageBps: SCANNER_BACKTEST_SLIPPAGE_BPS,
    benchmarkMode: SCANNER_BACKTEST_BENCHMARK_MODE,
    strategyTemplate: 'moving_average_crossover' as const,
  };
}

function getScannerBacktestKey(symbol: string): string {
  const config = getScannerBacktestConfig();
  return [
    symbol,
    config.startDate,
    config.endDate,
    config.initialCapital,
    config.feeBps,
    config.slippageBps,
    config.benchmarkMode,
    config.strategyTemplate,
  ].join('|');
}

function getBacktestErrorMessage(error: unknown, language: 'zh' | 'en'): string {
  if (error instanceof Error && error.message) return error.message;
  const parsed = getParsedApiError(error);
  return parsed.message || (error instanceof Error ? error.message : '') || (language === 'en' ? 'Backtest failed.' : '回测失败。');
}

function getSharpeFromRun(run: RuleBacktestRunResponse): number | null {
  const summary = run.summary || {};
  const value = summary.sharpe ?? summary.sharpeRatio ?? summary['sharpe_ratio'];
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function mapRuleRunToScannerBacktestItem(run: RuleBacktestRunResponse, status: ScannerBacktestStatus = 'completed'): ScannerBacktestItem {
  return {
    symbol: normalizeCandidateSymbol(run.code) || run.code,
    status,
    resultId: run.id,
    totalReturnPct: run.totalReturnPct ?? null,
    maxDrawdownPct: run.maxDrawdownPct ?? null,
    sharpe: getSharpeFromRun(run),
    tradeCount: run.tradeCount ?? null,
    error: run.noResultMessage || run.statusMessage || null,
  };
}

function dedupeBacktestCandidates(candidates: ScannerCandidate[]): ScannerCandidate[] {
  const seen = new Set<string>();
  const items: ScannerCandidate[] = [];
  candidates.forEach((candidate) => {
    const symbol = normalizeCandidateSymbol(candidate.symbol);
    if (!symbol || seen.has(symbol)) return;
    seen.add(symbol);
    items.push({ ...candidate, symbol });
  });
  return items;
}

function inferPreviewThreshold(runDetail: ScannerRunDetail | null, diagnostics: ScannerCandidateDiagnostic[]): number {
  const selectedScores = diagnostics
    .filter(isOfficialSelected)
    .map((candidate) => candidate.score)
    .filter((score): score is number => score != null && Number.isFinite(score));
  if (selectedScores.length) {
    const floor = Math.floor(Math.min(...selectedScores) / 10) * 10 - 10;
    return Math.max(40, Math.min(60, floor || 50));
  }
  const summarySelected = runDetail?.summary?.selectedCount ?? runDetail?.shortlist?.length ?? 0;
  return summarySelected > 0 ? 50 : 60;
}

function previewDecisionLabel(
  candidate: ScannerCandidateDiagnostic,
  threshold: number,
  language: 'zh' | 'en',
): string {
  if (isOfficialSelected(candidate)) return language === 'en' ? 'Official' : '官方';
  if (isDataUnavailable(candidate)) return language === 'en' ? 'Data failed' : '数据失败';
  if (isPreviewSelected(candidate, threshold)) return language === 'en' ? 'Preview' : '预览';
  return language === 'en' ? 'Rejected' : '淘汰';
}

function previewDecisionClass(candidate: ScannerCandidateDiagnostic, threshold: number): string {
  if (isOfficialSelected(candidate)) return 'border-emerald-400/25 bg-emerald-400/10 text-emerald-100';
  if (isDataUnavailable(candidate)) return 'border-rose-400/25 bg-rose-400/10 text-rose-100';
  if (isPreviewSelected(candidate, threshold)) return 'border-blue-400/25 bg-blue-400/10 text-blue-100 shadow-[0_0_14px_rgba(59,130,246,0.12)]';
  return 'border-white/10 bg-white/[0.035] text-white/58';
}

function sortDiagnosticsForDecision(
  candidates: ScannerCandidateDiagnostic[],
  threshold: number,
): ScannerCandidateDiagnostic[] {
  return [...candidates].sort((left, right) => {
    const leftOfficial = isOfficialSelected(left) ? 1 : 0;
    const rightOfficial = isOfficialSelected(right) ? 1 : 0;
    if (leftOfficial !== rightOfficial) return rightOfficial - leftOfficial;
    const leftPreview = isPreviewSelected(left, threshold) ? 1 : 0;
    const rightPreview = isPreviewSelected(right, threshold) ? 1 : 0;
    if (leftPreview !== rightPreview) return rightPreview - leftPreview;
    const scoreCompare = (right.score ?? Number.NEGATIVE_INFINITY) - (left.score ?? Number.NEGATIVE_INFINITY);
    if (scoreCompare !== 0) return scoreCompare;
    return (left.rank ?? Number.MAX_SAFE_INTEGER) - (right.rank ?? Number.MAX_SAFE_INTEGER);
  });
}

function formatScoreDelta(delta: number | null): string | null {
  if (delta == null || !Number.isFinite(delta)) return null;
  if (delta === 0) return '0';
  return `${delta > 0 ? '+' : ''}${delta}`;
}

type RejectionBucketKey = 'trend' | 'momentum' | 'liquidity' | 'risk' | 'data' | 'score' | 'other';

function rejectionBucketLabel(key: RejectionBucketKey, language: 'zh' | 'en'): string {
  const labels: Record<RejectionBucketKey, { zh: string; en: string }> = {
    trend: { zh: '趋势不足', en: 'Trend weak' },
    momentum: { zh: '动量不足', en: 'Momentum weak' },
    liquidity: { zh: '流动性不足', en: 'Liquidity weak' },
    risk: { zh: '风险过高', en: 'Risk high' },
    data: { zh: '数据不足', en: 'Data thin' },
    score: { zh: '分数不足', en: 'Score low' },
    other: { zh: '其他', en: 'Other' },
  };
  return labels[key][language];
}

function normalizeRejectionBucket(candidate: ScannerCandidateDiagnostic): RejectionBucketKey {
  const text = [
    candidate.status,
    candidate.reason,
    ...(candidate.failedRules || []),
    ...(candidate.missingFields || []),
  ].filter(Boolean).join(' ').toLowerCase();
  if (candidate.status === 'data_failed' || candidate.status === 'error') return 'data';
  if (/missing|history|quote|data|field|not_enough|unavailable/.test(text)) return 'data';
  if (/liquidity|volume|turnover|amount/.test(text)) return 'liquidity';
  if (/risk|volatility|drawdown|stop/.test(text)) return 'risk';
  if (/momentum|relative_strength|strength|return/.test(text)) return 'momentum';
  if (/trend|ma|moving_average|breakout/.test(text)) return 'trend';
  if (/score|threshold|rank/.test(text)) return 'score';
  return 'other';
}

function buildRejectionBuckets(candidates: ScannerCandidateDiagnostic[], language: 'zh' | 'en'): ScannerLabeledValue[] {
  const counts = new Map<RejectionBucketKey, number>();
  candidates
    .filter((candidate) => candidate.status !== 'selected')
    .forEach((candidate) => {
      const bucket = normalizeRejectionBucket(candidate);
      counts.set(bucket, (counts.get(bucket) || 0) + 1);
    });
  const order: RejectionBucketKey[] = ['trend', 'momentum', 'liquidity', 'risk', 'data', 'score', 'other'];
  return order
    .map((key) => ({ label: rejectionBucketLabel(key, language), value: String(counts.get(key) || 0) }))
    .filter((item) => item.value !== '0');
}

function getSelectedDiagnosticCandidate(
  diagnostics: ScannerCandidateDiagnostic[],
  shortlist: ScannerCandidate[],
  selectedSymbol: string | null,
): ScannerCandidateDiagnostic | null {
  if (selectedSymbol) {
    const normalized = normalizeCandidateSymbol(selectedSymbol);
    const match = diagnostics.find((candidate) => normalizeCandidateSymbol(candidate.symbol) === normalized);
    if (match) return match;
  }
  return diagnostics.find((candidate) => candidate.status === 'selected')
    || (shortlist[0] ? diagnostics.find((candidate) => normalizeCandidateSymbol(candidate.symbol) === normalizeCandidateSymbol(shortlist[0].symbol)) || null : null)
    || diagnostics[0]
    || null;
}

function buildDecisionSummary(
  runDetail: ScannerRunDetail,
  shortlist: ScannerCandidate[],
  diagnostics: ScannerCandidateDiagnostic[],
  language: 'zh' | 'en',
): { headline: string; best: string; reason: string; data: string } {
  const summary = runDetail.summary;
  if (!summary) {
    return {
      headline: language === 'en' ? 'Scan completed · inspect candidate diagnostics' : '扫描完成 · 查看候选诊断',
      best: language === 'en' ? 'Best candidate: --' : '最佳候选：--',
      reason: language === 'en' ? 'Main rejection: diagnostics limited' : '主要淘汰原因：诊断有限',
      data: language === 'en' ? 'Data status: diagnostics limited' : '数据状态：诊断有限',
    };
  }
  const selectedCount = summary.selectedCount ?? shortlist.length;
  const dataFailedCount = summary.dataFailedCount ?? diagnostics.filter((candidate) => candidate.status === 'data_failed' || candidate.status === 'error').length;
  const evaluatedCount = summary.evaluatedCount ?? runDetail.evaluatedSize ?? diagnostics.length;
  const bestDiagnostic = diagnostics.find((candidate) => candidate.status === 'selected')
    || diagnostics.find((candidate) => candidate.score != null)
    || null;
  const bestSymbol = normalizeCandidateSymbol(shortlist[0]?.symbol || bestDiagnostic?.symbol);
  const bestScore = shortlist[0]?.score ?? bestDiagnostic?.score ?? null;
  const rejectionBuckets = buildRejectionBuckets(diagnostics, language);
  return {
    headline: selectedCount
      ? (language === 'en' ? `Scan: ${selectedCount} selected / ${evaluatedCount} evaluated` : `本次扫描：${selectedCount} 个入选 / ${evaluatedCount} 个评估`)
      : (language === 'en' ? `Scan: no selected / ${evaluatedCount} evaluated` : `本次扫描：暂无入选 / ${evaluatedCount} 个评估`),
    best: bestSymbol
      ? `${language === 'en' ? 'Best candidate' : '最佳候选'}: ${bestSymbol} · ${bestScore == null ? '--' : `${bestScore}/100`}`.replace('最佳候选:', '最佳候选：')
      : (language === 'en' ? 'Best candidate: --' : '最佳候选：--'),
    reason: language === 'en'
      ? `Main rejection: ${rejectionBuckets[0]?.label || 'n/a'}`
      : `主要淘汰原因：${rejectionBuckets[0]?.label || '暂无'}`,
    data: dataFailedCount
      ? (language === 'en' ? `Data status: ${dataFailedCount} data failed` : `数据状态：${dataFailedCount} 个数据失败`)
      : (language === 'en' ? 'Data status: no data failures' : '数据状态：无数据失败'),
  };
}

function diagnosticToCandidate(candidate: ScannerCandidateDiagnostic): ScannerCandidate {
  return {
    symbol: candidate.symbol,
    name: candidate.name || candidate.symbol,
    companyName: candidate.name || candidate.symbol,
    rank: candidate.rank || 0,
    score: Number(candidate.score || 0),
    qualityHint: null,
    reasonSummary: candidate.reason || candidate.failedRules?.[0] || '',
    reasons: [candidate.reason, ...(candidate.failedRules || [])].filter((item): item is string => Boolean(item)),
    keyMetrics: Object.entries(candidate.metrics || {}).slice(0, 6).map(([label, value]) => ({ label, value: String(value ?? '--') })),
    featureSignals: [],
    riskNotes: [],
    watchContext: [],
    boards: [],
    appearedInRecentRuns: 0,
    lastTradeDate: null,
    scanTimestamp: null,
    aiInterpretation: {
      available: false,
      status: 'skipped',
      summary: null,
      opportunityType: null,
      riskInterpretation: null,
      watchPlan: null,
      reviewCommentary: null,
      provider: null,
      model: null,
      generatedAt: null,
      message: null,
    },
    realizedOutcome: {
      reviewStatus: 'pending',
      outcomeLabel: 'pending',
      thesisMatch: 'pending',
      reviewWindowDays: 3,
    },
    diagnostics: {},
  };
}

function buildInspectorWhySelected(candidate: ScannerCandidateDiagnostic, language: 'zh' | 'en'): string[] {
  const status = normalizeDiagnosticStatus(candidate.status);
  const friendlyReason = formatFriendlyDiagnosticReason(candidate, language);
  const notes = status === 'selected'
    ? [
      language === 'en' ? 'Passed current screening' : '通过当前筛选条件',
      candidate.score != null ? (language === 'en' ? 'Score reached the active threshold' : '评分达到当前阈值') : null,
      candidate.missingFields?.length ? null : (language === 'en' ? 'No required fields missing' : '关键数据未缺失'),
    ]
    : [
      friendlyReason,
      language === 'en' ? 'Did not meet the active scanner threshold' : '未满足当前扫描阈值',
    ];
  return notes.filter((item, index, array): item is string => Boolean(item) && array.indexOf(item) === index).slice(0, 4);
}

function buildInspectorRiskNotes(
  candidate: ScannerCandidateDiagnostic,
  runDetail: ScannerRunDetail | null | undefined,
  language: 'zh' | 'en',
): string[] {
  const source = formatFriendlyProvider(candidate.provider, language);
  const notes = [
    candidate.score != null && candidate.score <= 65
      ? (language === 'en' ? `Score is not a strong signal (${candidate.score}/100)` : `评分不算强信号（${candidate.score}/100）`)
      : null,
    ...((candidate.failedRules || []).map((rule) => formatFriendlyDiagnosticReason({ ...candidate, reason: rule, failedRules: [rule] }, language))),
    candidate.missingFields?.length
      ? (language === 'en' ? `${candidate.missingFields.length} missing data fields` : `${candidate.missingFields.length} 个缺失字段`)
      : null,
    runDetail?.summary?.selectedCount === 1
      ? (language === 'en' ? 'Only one selected candidate; sample is narrow' : '本次只有 1 个候选，样本偏窄')
      : null,
    source !== '--' ? (language === 'en' ? `Data source includes ${source}; verify freshness` : `数据源包含 ${source}，需确认实时性`) : null,
  ].filter((item, index, array): item is string => Boolean(item) && array.indexOf(item) === index);
  return notes.slice(0, 4);
}

function buildRunComparison(
  currentRun: ScannerRunDetail | null,
  previousRun: ScannerRunDetail | null,
  threshold: number,
  language: 'zh' | 'en',
): ScannerComparisonState {
  if (!currentRun || !previousRun) {
    return { previousRun: previousRun || null, bySymbol: new Map(), chips: [] };
  }
  const previousBySymbol = new Map(
    getCandidateDiagnostics(previousRun).map((candidate) => [normalizeCandidateSymbol(candidate.symbol), candidate] as const),
  );
  const currentCandidates = getCandidateDiagnostics(currentRun);
  const bySymbol = new Map<string, CandidateComparison>();
  const chips: string[] = [];

  currentCandidates.forEach((candidate) => {
    const symbol = normalizeCandidateSymbol(candidate.symbol);
    if (!symbol) return;
    const previous = previousBySymbol.get(symbol);
    const currentStatus = normalizeDiagnosticStatus(candidate.status);
    const previousStatus = previous ? normalizeDiagnosticStatus(previous.status) : null;
    const scoreDelta = previous?.score != null && candidate.score != null ? Math.round(candidate.score - previous.score) : null;
    let label = previous
      ? (language === 'en' ? 'Still in candidates' : '继续候选')
      : (language === 'en' ? 'New candidate' : '新增候选');
    if (!previous) {
      label = isOfficialSelected(candidate)
        ? (language === 'en' ? 'New selected' : '新入选')
        : (language === 'en' ? 'New candidate' : '新增候选');
    } else if (previousStatus === 'selected' && currentStatus === 'selected') {
      label = language === 'en' ? 'retained selected' : '继续入选';
    } else if (previousStatus === 'selected' && currentStatus !== 'selected') {
      label = language === 'en' ? 'selected to rejected' : '由入选转淘汰';
    } else if (previousStatus !== 'selected' && currentStatus === 'selected') {
      label = language === 'en' ? 'New selected' : '新入选';
    } else if (scoreDelta != null && scoreDelta > 0) {
      label = language === 'en' ? 'score up' : '评分上升';
    } else if (scoreDelta != null && scoreDelta < 0) {
      label = language === 'en' ? 'score down' : '评分下降';
    } else if (isPreviewSelected(candidate, threshold) && !isPreviewSelected(previous, threshold)) {
      label = language === 'en' ? 'New preview selected' : '新预览入选';
    } else if (!isPreviewSelected(candidate, threshold) && isPreviewSelected(previous, threshold)) {
      label = language === 'en' ? 'preview to rejected' : '由预览入选转淘汰';
    }
    bySymbol.set(symbol, { scoreDelta, previousStatus, currentStatus, label });
  });

  currentCandidates.slice(0, 8).forEach((candidate) => {
    const symbol = normalizeCandidateSymbol(candidate.symbol);
    const comparison = symbol ? bySymbol.get(symbol) : null;
    if (!symbol || !comparison) return;
    const delta = formatScoreDelta(comparison.scoreDelta);
    chips.push([symbol, comparison.label, delta ? `score ${delta}` : null].filter(Boolean).join(' · '));
  });
  previousBySymbol.forEach((_previous, symbol) => {
    if (!symbol || currentCandidates.some((candidate) => normalizeCandidateSymbol(candidate.symbol) === symbol)) return;
    chips.push(`${symbol} · ${language === 'en' ? 'removed candidate' : '移出候选'}`);
  });

  return { previousRun, bySymbol, chips: chips.slice(0, 8) };
}

function findPreviousComparableRunId(
  currentRun: ScannerRunDetail | null,
  historyItems: ScannerRunHistoryItem[],
): number | null {
  if (!currentRun) return null;
  const currentMarket = String(currentRun.market || '').toLowerCase();
  const currentProfile = currentRun.profile || '';
  const currentThemeId = currentRun.themeId || null;
  const currentUniverseType = currentRun.universeType || '';
  const match = historyItems.find((item) => {
    if (item.id === currentRun.id) return false;
    if (String(item.market || '').toLowerCase() !== currentMarket) return false;
    if ((item.profile || '') !== currentProfile) return false;
    if ((item.universeType || '') !== currentUniverseType) return false;
    return (item.themeId || null) === currentThemeId;
  });
  return match?.id || null;
}

function formatProviderDiagnostics(provider: ScannerProviderDiagnostics | null, language: 'zh' | 'en'): string | null {
  if (!provider) return null;
  const sources = [
    provider.quoteSourceUsed,
    provider.snapshotSourceUsed,
    provider.historySourceUsed,
    ...(provider.providersUsed || []),
  ].filter((item): item is string => Boolean(item));
  const sourceCopy = Array.from(new Set(sources)).slice(0, 3).join(' / ');
  const fallbackCopy = provider.fallbackOccurred
    ? (language === 'en' ? `fallback ${provider.fallbackCount}` : `降级 ${provider.fallbackCount}`)
    : (language === 'en' ? 'no fallback' : '未降级');
  const warningCopy = provider.providerWarnings?.length
    ? String(provider.providerWarnings.length)
    : null;
  return [
    sourceCopy || provider.configuredPrimaryProvider,
    fallbackCopy,
    warningCopy ? (language === 'en' ? `${warningCopy} warnings` : `${warningCopy} 条警告`) : null,
  ].filter(Boolean).join(' · ');
}

function parseCustomSymbols(value: string): string[] {
  return Array.from(
    new Set(
      value
        .split(/[\s,，;；]+/)
        .map((symbol) => symbol.trim().toUpperCase())
        .filter(Boolean),
    ),
  );
}

function getSymbolTokenCount(value: string): number {
  return value.split(/[\s,，;；]+/).map((symbol) => symbol.trim()).filter(Boolean).length;
}

function getThemeLabel(theme: ScannerTheme, language: 'zh' | 'en'): string {
  return language === 'en' ? theme.labelEn : theme.labelZh;
}

function buildCustomThemeId(label: string): string {
  const slug = label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 48);
  return `custom_${slug || 'scanner_theme'}`;
}

function hasReviewSummary(review?: ScannerReviewSummary | null): boolean {
  return Boolean(review?.available || review?.reviewedCount || review?.candidateCount);
}

function hasComparison(comparison?: ScannerWatchlistComparison | null): boolean {
  return Boolean(comparison?.available || comparison?.newCount || comparison?.retainedCount || comparison?.droppedCount);
}

function hasOutcome(outcome?: ScannerCandidateOutcome | null): boolean {
  return Boolean(outcome && (outcome.reviewStatus !== 'pending' || outcome.outcomeLabel !== 'pending' || outcome.reviewWindowReturnPct != null));
}

function dedupeTickerSymbols(symbols: string[]): string[] {
  return Array.from(
    new Set(
      symbols
        .map((symbol) => symbol.trim())
        .filter(Boolean),
    ),
  );
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function formatHistoryHeadline(
  headline: string | null | undefined,
  topSymbols: string[],
  fallbackTitle: string,
): { title: string; detail: string | null; symbols: string[] } {
  const symbols = dedupeTickerSymbols(topSymbols);
  const trimmedHeadline = headline?.trim() || '';
  if (!trimmedHeadline) {
    return { title: fallbackTitle, detail: null, symbols };
  }

  if (!symbols.length) {
    return { title: trimmedHeadline, detail: null, symbols };
  }

  const symbolPattern = new RegExp(`\\b(?:${symbols.map(escapeRegExp).join('|')})\\b`, 'i');
  const explicitSplit = trimmedHeadline.match(/^(.*?)[：:]\s*(.+)$/);
  if (explicitSplit && symbolPattern.test(explicitSplit[2] || '')) {
    return {
      title: explicitSplit[1]?.trim() || fallbackTitle,
      detail: null,
      symbols,
    };
  }

  const firstSymbolIndex = trimmedHeadline.search(symbolPattern);
  if (firstSymbolIndex > 0) {
    const titleCandidate = trimmedHeadline.slice(0, firstSymbolIndex).replace(/[/,，:：\-\s]+$/, '').trim();
    if (titleCandidate) {
      return {
        title: titleCandidate,
        detail: null,
        symbols,
      };
    }
  }

  return { title: trimmedHeadline, detail: null, symbols };
}

function statusVariant(status?: string | null): 'success' | 'warning' | 'danger' | 'history' {
  if (status === 'completed') return 'success';
  if (status === 'empty') return 'warning';
  if (status === 'failed') return 'danger';
  return 'history';
}

function marketVariant(market?: string | null): 'success' | 'info' | 'warning' | 'history' {
  if (market === 'us') return 'success';
  if (market === 'hk') return 'warning';
  if (market === 'cn') return 'info';
  return 'history';
}

function csvEscape(value: string | number | null | undefined): string {
  const normalized = value == null ? '' : String(value);
  if (!/[",\n]/.test(normalized)) return normalized;
  return `"${normalized.replace(/"/g, '""')}"`;
}

type ScannerExportRow = {
  rank: number;
  symbol: string;
  name: string;
  scannerScore: number;
  entryRange: string;
  target: string;
  stop: string;
  reason: string;
  risk: string;
  universeType: string;
  theme: string;
  generatedAt: string;
  runId: number | string;
};

function buildScannerExportRow(
  candidate: ScannerCandidate,
  runDetail: ScannerRunDetail,
  language: 'zh' | 'en',
): ScannerExportRow {
  return {
    rank: candidate.rank,
    symbol: candidate.symbol,
    name: candidate.companyName || candidate.name,
    scannerScore: candidate.score,
    entryRange: getEntryRange(candidate) || '',
    target: getTargetPrice(candidate) || '',
    stop: getStopLoss(candidate) || '',
    reason: getKeyReason(candidate, runDetail, language),
    risk: getRiskSummary(candidate, language),
    universeType: runDetail.universeType || '',
    theme: runDetail.themeLabel || runDetail.themeId || '',
    generatedAt: runDetail.completedAt || runDetail.runAt || '',
    runId: runDetail.id,
  };
}

function buildScannerCsv(rows: ScannerExportRow[]): string {
  const headers = ['rank', 'symbol', 'name', 'scannerScore', 'entryRange', 'target', 'stop', 'reason', 'risk', 'universeType', 'theme', 'generatedAt', 'runId'];
  return [
    headers.join(','),
    ...rows.map((row) => headers.map((header) => csvEscape(row[header as keyof ScannerExportRow])).join(',')),
  ].join('\n');
}

function buildScannerExportFilename(runDetail: ScannerRunDetail, suffix = 'results'): string {
  const datePart = (runDetail.watchlistDate || runDetail.completedAt || runDetail.runAt || new Date().toISOString()).slice(0, 10);
  const safeDatePart = datePart.replace(/[^0-9-]/g, '') || 'unknown-date';
  const safeMarket = (runDetail.market || 'scanner').toLowerCase();
  return `scanner_${safeMarket}_${safeDatePart}_run-${runDetail.id}_${suffix}.csv`;
}

function downloadScannerCsv(filename: string, csv: string): void {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(objectUrl);
}

function ActionButton({
  label,
  icon,
  onClick,
  href,
  disabled = false,
  title,
  variant = 'default',
  testId,
}: {
  label: string;
  icon?: React.ReactNode;
  onClick?: (event: React.MouseEvent<HTMLElement>) => void;
  href?: string;
  disabled?: boolean;
  title?: string;
  variant?: 'default' | 'primary';
  testId?: string;
}) {
  const className = [
    'inline-flex min-w-0 items-center justify-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs transition-colors',
    variant === 'primary'
      ? 'border-emerald-300/15 bg-emerald-300/[0.12] text-emerald-100 shadow-[0_0_14px_rgba(16,185,129,0.16)] hover:border-emerald-200/30 hover:bg-emerald-300/[0.18]'
      : 'border-white/10 bg-white/5 text-white/70 hover:bg-white/10 hover:text-white',
    disabled ? 'cursor-not-allowed border-white/5 bg-white/[0.02] text-white/28 hover:bg-white/[0.02] hover:text-white/28' : '',
  ].join(' ');
  const content = (
    <>
      {icon}
      <span>{label}</span>
    </>
  );

  if (href && !disabled) {
    return (
      <Link
        to={href}
        data-testid={testId}
        onClick={(event) => {
          event.stopPropagation();
          onClick?.(event);
        }}
        title={title}
        className={className}
      >
        {content}
      </Link>
    );
  }

  return (
    <button
      type="button"
      data-testid={testId}
      onClick={(event) => {
        event.stopPropagation();
        onClick?.(event);
      }}
      disabled={disabled}
      title={title}
      className={className}
    >
      {content}
    </button>
  );
}

function PillTagGroup({
  label,
  value,
  options,
  onChange,
  variant = 'default',
  testId,
}: {
  label: string;
  value: string;
  options: PillOption[];
  onChange: (next: string) => void;
  variant?: 'default' | 'market';
  testId?: string;
}) {
  const isMarketGroup = variant === 'market';

  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <span className="text-[10px] uppercase tracking-[0.16em] text-white/40">{label}</span>
      <div
        className={isMarketGroup
          ? 'ui-scroll-x-quiet flex min-w-0 max-w-full rounded-xl border border-white/5 bg-black/40 p-1'
          : 'flex min-w-0 flex-wrap gap-2'}
        role="group"
        aria-label={label}
        data-testid={testId}
      >
        {options.map((option) => {
          const isActive = option.value === value;
          return (
            <button
              key={option.value}
              type="button"
              aria-pressed={isActive}
              onClick={() => onChange(option.value)}
              className={isActive
                ? isMarketGroup
                  ? 'min-w-0 shrink-0 rounded-lg bg-white/10 px-4 py-1 text-sm font-bold text-white shadow-[0_2px_10px_rgba(0,0,0,0.5)] transition-all'
                  : 'min-w-0 rounded-full border border-white/10 bg-white/10 px-3 py-1 text-xs text-white transition-colors'
                : isMarketGroup
                  ? 'min-w-0 shrink-0 rounded-lg bg-transparent px-4 py-1 text-sm font-medium text-white/40 transition-all hover:text-white/70'
                  : 'min-w-0 rounded-full border border-white/5 bg-transparent px-3 py-1 text-xs text-white/50 transition-colors hover:bg-white/[0.05]'}
            >
              <span className="ui-truncate block max-w-full">{option.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function FieldChip({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex max-w-full items-center gap-1 rounded-md border border-white/8 bg-white/[0.035] px-1.5 py-0.5 text-[10px] text-white/72">
      <span className="shrink-0 text-white/36">{label}</span>
      <span className="min-w-0 truncate">{value}</span>
    </span>
  );
}

function LabeledValueGrid({
  items,
  empty,
}: {
  items: ScannerLabeledValue[];
  empty: string;
}) {
  if (!items.length) {
    return <p className="text-xs text-white/32">{empty}</p>;
  }
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <FieldChip key={`${item.label}-${item.value}`} label={item.label} value={item.value} />
      ))}
    </div>
  );
}

function NotesList({ notes, empty }: { notes: string[]; empty: string }) {
  if (!notes.length) {
    return <p className="text-xs text-white/32">{empty}</p>;
  }
  return (
    <ul className="space-y-1">
      {notes.map((note) => (
        <li key={note} className="text-xs leading-relaxed text-white/64">
          {note}
        </li>
      ))}
    </ul>
  );
}

function DetailSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-white/5 bg-black/20 p-2.5">
      <h5 className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-white/38">{title}</h5>
      {children}
    </section>
  );
}

function AdvancedDisclosure({
  title,
  summary,
  icon = 'info',
  children,
  testId,
  defaultOpen = false,
  open: controlledOpen,
  onToggle,
}: {
  title: string;
  summary?: string;
  icon?: ScannerDisclosureIcon;
  children: React.ReactNode;
  testId: string;
  defaultOpen?: boolean;
  open?: boolean;
  onToggle?: (nextOpen: boolean) => void;
}) {
  const [uncontrolledOpen, setUncontrolledOpen] = useState(defaultOpen);
  const open = controlledOpen ?? uncontrolledOpen;
  const iconClassName = 'h-3.5 w-3.5 shrink-0 text-white/38';
  const leadingIcon = {
    info: <Info className={iconClassName} aria-hidden="true" />,
    history: <History className={iconClassName} aria-hidden="true" />,
    backtest: <LineChart className={iconClassName} aria-hidden="true" />,
    watchlist: <BookmarkPlus className={iconClassName} aria-hidden="true" />,
    more: <MoreHorizontal className={iconClassName} aria-hidden="true" />,
  }[icon];
  const actionLabel = open
    ? (title.match(/[A-Za-z]/) ? `Collapse ${title}` : `收起 ${title}`)
    : (title.match(/[A-Za-z]/) ? `Expand ${title}` : `展开 ${title}`);

  return (
    <section
      data-testid={testId}
      className="rounded-xl border border-white/5 bg-white/[0.02] px-2.5 py-2 text-xs backdrop-blur-md transition-all hover:border-white/10"
    >
      <div className="flex min-w-0 items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          {leadingIcon}
          <div className="min-w-0">
            <h3 className="truncate text-[10px] font-bold uppercase tracking-widest text-white/40">{title}</h3>
            {summary ? <p className="mt-0.5 truncate text-[11px] text-white/38">{summary}</p> : null}
          </div>
        </div>
        <button
          type="button"
          aria-expanded={open}
          aria-label={actionLabel}
          onClick={() => {
            const nextOpen = !open;
            if (controlledOpen == null) {
              setUncontrolledOpen(nextOpen);
            }
            onToggle?.(nextOpen);
          }}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-white/8 bg-white/[0.035] px-2 py-1 text-[11px] text-white/58 hover:bg-white/[0.07] hover:text-white"
        >
          {open ? <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" /> : <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />}
          <span>{open ? (title.match(/[A-Za-z]/) ? 'Collapse' : '收起') : (title.match(/[A-Za-z]/) ? 'Expand' : '展开')}</span>
        </button>
      </div>
      {open ? <div className="mt-2">{children}</div> : null}
    </section>
  );
}

function CandidateDetailPanel({
  candidate,
  runDetail,
  language,
  onAnalyze,
  onCopy,
  onExport,
  onTrack,
  onBacktest,
  isAnalyzing,
  isCopied,
  isTracked,
  isTrackPending,
  isWatchlistAuthBlocked,
  backtestActionLabel,
  backtestItem,
}: {
  candidate: ScannerCandidate;
  runDetail: ScannerRunDetail;
  language: 'zh' | 'en';
  onAnalyze: (candidate: ScannerCandidate) => void;
  onCopy: (candidate: ScannerCandidate) => void;
  onExport: (candidate: ScannerCandidate) => void;
  onTrack: (candidate: ScannerCandidate) => void;
  onBacktest: (candidate: ScannerCandidate) => void;
  isAnalyzing: boolean;
  isCopied: boolean;
  isTracked: boolean;
  isTrackPending: boolean;
  isWatchlistAuthBlocked: boolean;
  backtestActionLabel: string;
  backtestItem?: ScannerBacktestItem;
}) {
  const candidateProvider = getProviderDiagnostics(candidate.diagnostics);
  const ai = candidate.aiInterpretation;
  const entryRange = getEntryRange(candidate);
  const targetPrice = getTargetPrice(candidate);
  const stopLoss = getStopLoss(candidate);

  return (
    <div
      data-testid={`scanner-result-detail-${getCandidateIdentity(candidate)}`}
      className="mt-3 grid gap-2.5 rounded-2xl border border-white/8 bg-black/25 p-3 md:grid-cols-2"
    >
      <div className="md:col-span-2 flex flex-wrap gap-2">
        <ActionButton
          label={isAnalyzing ? (language === 'en' ? 'Analyzing...' : '分析中...') : (language === 'en' ? 'Analyze' : '分析')}
          icon={<Play className="h-3.5 w-3.5" />}
          onClick={() => onAnalyze(candidate)}
          disabled={isAnalyzing}
          variant="primary"
        />
        <ActionButton
          label={isCopied ? (language === 'en' ? 'Copied' : '已复制') : (language === 'en' ? 'Copy symbol' : '复制代码')}
          icon={<Copy className="h-3.5 w-3.5" />}
          onClick={() => onCopy(candidate)}
        />
        <ActionButton
          label={getWatchlistActionLabel(isTracked, isTrackPending, isWatchlistAuthBlocked, language)}
          icon={isTracked ? <BookmarkCheck className="h-3.5 w-3.5" /> : <BookmarkPlus className="h-3.5 w-3.5" />}
          onClick={() => onTrack(candidate)}
          disabled={isTrackPending || isTracked}
          variant={isTracked ? 'default' : 'primary'}
          title={getWatchlistActionTitle(isTracked, isWatchlistAuthBlocked, language)}
        />
        <ActionButton
          label={language === 'en' ? 'Export candidate' : '导出该候选'}
          icon={<Download className="h-3.5 w-3.5" />}
          onClick={() => onExport(candidate)}
        />
        <ActionButton
          label={backtestItem?.status === 'running' || backtestItem?.status === 'queued' ? (language === 'en' ? 'Running' : '运行中') : (language === 'en' ? 'Backtest' : '回测')}
          icon={<TestTubeDiagonal className="h-3.5 w-3.5" />}
          onClick={() => onBacktest(candidate)}
          disabled={!normalizeCandidateSymbol(candidate.symbol) || backtestItem?.status === 'running' || backtestItem?.status === 'queued'}
          title={!normalizeCandidateSymbol(candidate.symbol) ? backtestActionLabel : undefined}
        />
      </div>
      <div className="md:col-span-2">
        <ScannerBacktestResultStrip item={backtestItem} language={language} />
      </div>
      <DetailSection title={language === 'en' ? 'Key metrics' : '关键指标'}>
        <LabeledValueGrid items={candidate.keyMetrics || []} empty={language === 'en' ? 'No key metrics provided' : '未提供关键指标'} />
      </DetailSection>
      <DetailSection title={language === 'en' ? 'Feature signals' : '特征信号'}>
        <LabeledValueGrid items={candidate.featureSignals || []} empty={language === 'en' ? 'No feature signals provided' : '未提供特征信号'} />
      </DetailSection>
      <DetailSection title={language === 'en' ? 'Risk notes' : '风险说明'}>
        <NotesList notes={candidate.riskNotes || []} empty={language === 'en' ? 'No risk notes provided' : '未提供风险说明'} />
      </DetailSection>
      <DetailSection title={language === 'en' ? 'Trade plan fields' : '交易计划字段'}>
        <div className="flex flex-wrap gap-2">
          {entryRange ? <FieldChip label={language === 'en' ? 'Entry' : '建仓'} value={entryRange} /> : null}
          {targetPrice ? <FieldChip label={language === 'en' ? 'Target' : '目标'} value={targetPrice} /> : null}
          {stopLoss ? <FieldChip label={language === 'en' ? 'Stop' : '止损'} value={stopLoss} /> : null}
          {!entryRange && !targetPrice && !stopLoss ? (
            <p className="text-xs text-white/32">{language === 'en' ? 'No explicit entry, target, or stop fields were provided.' : '未提供明确建仓、目标或止损字段。'}</p>
          ) : null}
        </div>
      </DetailSection>
      <DetailSection title={language === 'en' ? 'Why selected' : '入选依据'}>
        <NotesList
          notes={[
            candidate.reasonSummary,
            ...(candidate.reasons || []),
            ...(runDetail.scoringNotes || []),
          ].filter((item): item is string => Boolean(item))}
          empty={language === 'en' ? 'No selection notes provided' : '未提供入选说明'}
        />
      </DetailSection>
      <DetailSection title={language === 'en' ? 'AI interpretation' : 'AI 解读'}>
        {ai?.available ? (
          <div className="space-y-2 text-xs leading-relaxed text-white/64">
            {ai.provider || ai.model ? (
              <p>
                <span className="text-white/36">{language === 'en' ? 'Provider' : '供应商'}: </span>
                {[ai.provider, ai.model].filter(Boolean).join(' / ')}
              </p>
            ) : null}
            {ai.summary ? <p>{ai.summary}</p> : null}
            {ai.watchPlan ? <p>{ai.watchPlan}</p> : null}
            {ai.riskInterpretation ? <p>{ai.riskInterpretation}</p> : null}
            {!ai.summary && !ai.watchPlan && !ai.riskInterpretation ? <p>{ai.status}</p> : null}
          </div>
        ) : (
          <p className="text-xs text-white/32">{ai?.status || (language === 'en' ? 'AI interpretation not available' : 'AI 解读不可用')}</p>
        )}
      </DetailSection>
      {hasOutcome(candidate.realizedOutcome) ? (
        <DetailSection title={language === 'en' ? 'Realized outcome' : '实际表现'}>
          <div className="flex flex-wrap gap-2">
            <FieldChip label={language === 'en' ? 'Outcome' : '结果'} value={candidate.realizedOutcome.outcomeLabel} />
            <FieldChip label={language === 'en' ? 'Thesis' : '验证'} value={candidate.realizedOutcome.thesisMatch} />
            {candidate.realizedOutcome.reviewWindowReturnPct != null ? (
              <FieldChip label={language === 'en' ? 'Window return' : '窗口收益'} value={formatPercent(candidate.realizedOutcome.reviewWindowReturnPct)} />
            ) : null}
            {candidate.realizedOutcome.benchmarkCode ? (
              <FieldChip label={language === 'en' ? 'Benchmark' : '基准'} value={candidate.realizedOutcome.benchmarkCode} />
            ) : null}
          </div>
        </DetailSection>
      ) : null}
      {candidateProvider ? (
        <DetailSection title={language === 'en' ? 'Candidate provenance' : '候选来源'}>
          <p className="text-xs leading-relaxed text-white/64">{formatProviderDiagnostics(candidateProvider, language)}</p>
        </DetailSection>
      ) : null}
    </div>
  );
}

function CandidateInspector({
  candidate,
  runDetail,
  language,
  previewThreshold,
  comparison,
  onAnalyze,
  onCopy,
  onExport,
  onTrack,
  onBacktest,
  isAnalyzing,
  isCopied,
  isTracked,
  isTrackPending,
  isWatchlistAuthBlocked,
  backtestActionLabel,
  backtestItem,
  testId = 'scanner-candidate-inspector',
}: {
  candidate: ScannerCandidateDiagnostic;
  runDetail?: ScannerRunDetail | null;
  language: 'zh' | 'en';
  previewThreshold: number;
  comparison?: CandidateComparison | null;
  onAnalyze: (candidate: ScannerCandidate) => void;
  onCopy: (candidate: ScannerCandidate) => void;
  onExport: (candidate: ScannerCandidate) => void;
  onTrack: (candidate: ScannerCandidate) => void;
  onBacktest: (candidate: ScannerCandidate) => void;
  isAnalyzing: boolean;
  isCopied: boolean;
  isTracked: boolean;
  isTrackPending: boolean;
  isWatchlistAuthBlocked: boolean;
  backtestActionLabel: string;
  backtestItem?: ScannerBacktestItem;
  testId?: string;
}) {
  const actionCandidate = diagnosticToCandidate(candidate);
  const rawMetrics = Object.entries(candidate.metrics || {}).slice(0, 8);
  const status = normalizeDiagnosticStatus(candidate.status);
  const missingCount = candidate.missingFields?.length || 0;
  const previewSelected = isPreviewSelected(candidate, previewThreshold);
  const delta = formatScoreDelta(comparison?.scoreDelta ?? null);
  const whySelected = buildInspectorWhySelected(candidate, language);
  const riskNotes = buildInspectorRiskNotes(candidate, runDetail, language);
  const providerLabel = formatFriendlyProvider(candidate.provider, language);
  const dataQualityLabel = formatCandidateDataQuality(candidate, language);
  const [showDeveloperFields, setShowDeveloperFields] = useState(false);
  const officialStatusCopy = isOfficialSelected(candidate)
    ? (language === 'en' ? 'Official selected' : '官方入选')
    : (language === 'en' ? 'Official rejected' : '官方淘汰');
  const previewStatusCopy = previewSelected
    ? (language === 'en' ? `Threshold ${previewThreshold} preview selected` : `阈值 ${previewThreshold} 预览入选`)
    : (language === 'en' ? `Threshold ${previewThreshold} preview rejected` : `阈值 ${previewThreshold} 预览淘汰`);

  return (
    <aside
      data-testid={testId}
      className="flex max-h-full min-h-0 flex-col overflow-hidden rounded-xl border border-white/5 bg-white/[0.02] text-sm backdrop-blur-md transition-all hover:border-white/10"
    >
      <div className="border-b border-white/5 px-3 py-3">
        <div className="flex min-w-0 items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex min-w-0 items-center gap-2">
              <span className="truncate font-mono text-lg font-bold text-white">{candidate.symbol || '--'}</span>
              <span className={`inline-flex shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-widest ${diagnosticStatusClass(status)}`}>
                {diagnosticStatusLabel(status, language)}
              </span>
            </div>
            <p className="mt-1 truncate text-xs text-white/40">{candidate.name || candidate.symbol || '--'}</p>
            <p className="mt-1 text-xs text-white/62">
              {officialStatusCopy}
              {candidate.score != null ? ` · ${candidate.score}/100` : ''}
            </p>
          </div>
          <div className="shrink-0 text-right">
            <p className="text-[10px] font-bold uppercase tracking-widest text-white/40">{language === 'en' ? 'Rank' : '排名'}</p>
            <p className="font-mono text-sm font-semibold text-white">{candidate.rank ? `#${candidate.rank}` : '--'}</p>
          </div>
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          <FieldChip label={language === 'en' ? 'Status' : '状态'} value={diagnosticStatusLabel(status, language)} />
          <FieldChip label={language === 'en' ? 'Source' : '来源'} value={providerLabel} />
          <FieldChip label={language === 'en' ? 'Quality' : '质量'} value={dataQualityLabel} />
          <FieldChip label={language === 'en' ? 'Preview' : '预览'} value={previewStatusCopy} />
          <FieldChip label={language === 'en' ? 'Missing' : '缺失'} value={String(missingCount)} />
          {delta ? <FieldChip label={language === 'en' ? 'Prev' : '较上次'} value={delta} /> : null}
          {comparison?.label ? <FieldChip label={language === 'en' ? 'Change' : '变化'} value={comparison.label} /> : null}
        </div>
      </div>

      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3 no-scrollbar">
        <DetailSection title={language === 'en' ? 'Why selected' : '为什么入选'}>
          <NotesList
            notes={whySelected}
            empty={language === 'en' ? 'No decision notes provided' : '未提供决策说明'}
          />
        </DetailSection>

        <DetailSection title={language === 'en' ? 'Main risks' : '主要风险'}>
          <NotesList
            notes={riskNotes}
            empty={language === 'en' ? 'No major risks provided' : '未提供主要风险'}
          />
        </DetailSection>

        <DetailSection title={language === 'en' ? 'Next steps' : '下一步'}>
          <div className="grid grid-cols-2 gap-1.5">
            <ActionButton
              label={isAnalyzing ? (language === 'en' ? 'Analyzing...' : '分析中...') : (language === 'en' ? 'Analyze' : '分析')}
              icon={<Play className="h-3.5 w-3.5" />}
              onClick={() => onAnalyze(actionCandidate)}
              disabled={isAnalyzing}
              variant="primary"
            />
            <ActionButton
              label={backtestItem?.status === 'running' || backtestItem?.status === 'queued' ? (language === 'en' ? 'Running' : '运行中') : (language === 'en' ? 'Backtest' : '回测')}
              icon={<TestTubeDiagonal className="h-3.5 w-3.5" />}
              onClick={() => onBacktest(actionCandidate)}
              disabled={!normalizeCandidateSymbol(actionCandidate.symbol) || backtestItem?.status === 'running' || backtestItem?.status === 'queued'}
              title={!normalizeCandidateSymbol(actionCandidate.symbol) ? backtestActionLabel : undefined}
            />
            <ActionButton
              label={getWatchlistActionLabel(isTracked, isTrackPending, isWatchlistAuthBlocked, language)}
              icon={isTracked ? <BookmarkCheck className="h-3.5 w-3.5" /> : <BookmarkPlus className="h-3.5 w-3.5" />}
              onClick={() => onTrack(actionCandidate)}
              disabled={isTracked || isTrackPending || isWatchlistAuthBlocked}
              title={getWatchlistActionTitle(isTracked, isWatchlistAuthBlocked, language)}
            />
            <ActionButton
              label={language === 'en' ? 'View diagnostics' : '查看诊断'}
              icon={<Info className="h-3.5 w-3.5" />}
              onClick={() => setShowDeveloperFields((current) => !current)}
            />
          </div>
          <ScannerBacktestResultStrip item={backtestItem} language={language} />
        </DetailSection>

        <AdvancedDisclosure
          testId={`${testId}-rules-disclosure`}
          title={language === 'en' ? 'Rule diagnostics' : '规则诊断'}
          summary={formatFriendlyDiagnosticReason(candidate, language)}
          icon="info"
        >
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
            <NotesList notes={candidate.failedRules || []} empty={language === 'en' ? 'No failed rules' : '无失败规则'} />
            <NotesList notes={candidate.missingFields || []} empty={language === 'en' ? 'No missing fields' : '无缺失字段'} />
          </div>
        </AdvancedDisclosure>

        <AdvancedDisclosure
          testId={`${testId}-quality-disclosure`}
          title={language === 'en' ? 'Data quality' : '数据质量'}
          summary={language === 'en' ? `${dataQualityLabel} · ${providerLabel}` : `${dataQualityLabel} · ${providerLabel}`}
          icon="history"
        >
          <div className="flex flex-wrap gap-1.5">
            <FieldChip label={language === 'en' ? 'Provider' : '来源'} value={providerLabel} />
            <FieldChip label={language === 'en' ? 'Status' : '状态'} value={diagnosticStatusLabel(status, language)} />
            <FieldChip label={language === 'en' ? 'Quality' : '质量'} value={dataQualityLabel} />
            <FieldChip label={language === 'en' ? 'Missing' : '缺失'} value={String(missingCount)} />
            {rawMetrics.length
              ? rawMetrics.map(([key, value]) => (
                <FieldChip key={`${candidate.symbol}-${key}`} label={key} value={String(value ?? '--')} />
              ))
              : null}
          </div>
        </AdvancedDisclosure>

        <AdvancedDisclosure
          testId={`${testId}-developer-disclosure`}
          title={language === 'en' ? 'Developer fields' : '开发者字段'}
          summary={language === 'en' ? 'Raw metrics, copy, and export tools' : '原始指标、复制与导出工具'}
          icon="more"
          open={showDeveloperFields}
          onToggle={setShowDeveloperFields}
        >
          <div className="space-y-2">
            <div className="flex flex-wrap gap-1.5">
              <ActionButton
                label={isCopied ? (language === 'en' ? 'Copied' : '已复制') : (language === 'en' ? 'Copy' : '复制')}
                icon={<Copy className="h-3.5 w-3.5" />}
                onClick={() => onCopy(actionCandidate)}
              />
              <ActionButton
                label={language === 'en' ? 'Export' : '导出'}
                icon={<Download className="h-3.5 w-3.5" />}
                onClick={() => onExport(actionCandidate)}
              />
            </div>
            <div className="flex flex-wrap gap-1.5">
              {rawMetrics.length
                ? rawMetrics.map(([key, value]) => (
                  <FieldChip key={`${candidate.symbol}-${key}`} label={key} value={String(value ?? '--')} />
                ))
                : <p className="text-xs text-white/32">{language === 'en' ? 'No raw metrics' : '无原始指标'}</p>}
            </div>
          </div>
        </AdvancedDisclosure>
      </div>
    </aside>
  );
}

function ScannerBacktestResultStrip({
  item,
  language,
}: {
  item?: ScannerBacktestItem;
  language: 'zh' | 'en';
}) {
  if (!item || item.status === 'idle') return null;
  const statusLabel = {
    queued: language === 'en' ? 'Queued' : '排队',
    running: language === 'en' ? 'Running' : '运行中',
    completed: language === 'en' ? 'Completed' : '完成',
    failed: language === 'en' ? 'Failed' : '失败',
    skipped_existing: language === 'en' ? 'Reused' : '复用',
    idle: language === 'en' ? 'Idle' : '空闲',
  }[item.status];
  const resultHref = item.resultId ? buildLocalizedPath(`/backtest/results/${item.resultId}`, language) : null;
  return (
    <div data-testid={`scanner-backtest-status-${item.symbol}`} className="mt-2 flex min-w-0 flex-wrap items-center gap-1.5 rounded-lg border border-white/5 bg-black/20 px-2 py-1.5 text-[11px] text-white/52">
      <span className="shrink-0 rounded border border-white/10 bg-white/[0.04] px-1.5 py-0.5 font-bold uppercase tracking-widest text-white/45">{statusLabel}</span>
      {item.status === 'completed' || item.status === 'skipped_existing' ? (
        <>
          <span className={item.totalReturnPct != null && item.totalReturnPct >= 0 ? 'font-mono text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.4)]' : 'font-mono text-rose-400 drop-shadow-[0_0_8px_rgba(251,113,133,0.4)]'}>
            {formatPercent(item.totalReturnPct)}
          </span>
          <span className="font-mono text-rose-400 drop-shadow-[0_0_8px_rgba(251,113,133,0.4)]">{formatPercent(item.maxDrawdownPct)}</span>
          <span className="font-mono text-white/70">{formatMetricNumber(item.sharpe)}</span>
          {resultHref ? <Link className="shrink-0 text-blue-200 hover:text-blue-100" to={resultHref}>{language === 'en' ? 'Report' : '查看报告'}</Link> : null}
        </>
      ) : null}
      {item.status === 'failed' && item.error ? <span className="min-w-0 truncate text-rose-300" title={item.error}>{item.error}</span> : null}
    </div>
  );
}

function ScannerBacktestLab({
  language,
  items,
  isRunning,
  onRunBatch,
  onCopySymbol,
  counts,
}: {
  language: 'zh' | 'en';
  items: ScannerBacktestItem[];
  isRunning: boolean;
  onRunBatch: (source: ScannerBacktestSource) => void;
  onCopySymbol: (symbol: string) => void;
  counts: Record<ScannerBacktestSource, number>;
}) {
  const config = getScannerBacktestConfig();
  const requested = items.length;
  const running = items.filter((item) => item.status === 'queued' || item.status === 'running').length;
  const completed = items.filter((item) => item.status === 'completed').length;
  const failed = items.filter((item) => item.status === 'failed').length;
  const skipped = items.filter((item) => item.status === 'skipped_existing').length;
  const statusText = language === 'en'
    ? `requested ${requested} / running ${running} / completed ${completed} / failed ${failed} / skipped ${skipped}`
    : `请求 ${requested} / 运行 ${running} / 完成 ${completed} / 失败 ${failed} / 复用 ${skipped}`;

  return (
    <section data-testid="scanner-backtest-lab" className="grid gap-3 rounded-xl border border-white/5 bg-white/[0.015] p-3 text-xs">
      <div className="flex min-w-0 items-center gap-2">
        <LineChart className="h-3.5 w-3.5 text-white/38" aria-hidden="true" />
        <h3 className="text-[10px] font-bold uppercase tracking-widest text-white/40">{language === 'en' ? 'Backtest Lab' : '回测实验室'}</h3>
      </div>
      <div className="grid gap-3 text-xs">
        <div className="grid gap-2 rounded-xl border border-white/5 bg-black/20 p-3 sm:grid-cols-2 xl:grid-cols-4">
          <FieldChip label={language === 'en' ? 'Mode' : '模式'} value={language === 'en' ? 'Candidate single-symbol backtest' : '候选单标的回测'} />
          <FieldChip label={language === 'en' ? 'Range' : '区间'} value={`${config.startDate} - ${config.endDate}`} />
          <FieldChip label={language === 'en' ? 'Capital' : '资金'} value={String(config.initialCapital)} />
          <FieldChip label={language === 'en' ? 'Benchmark' : '基准'} value={config.benchmarkMode} />
          <FieldChip label={language === 'en' ? 'Fee/slip' : '费用/滑点'} value={`${config.feeBps}/${config.slippageBps} bps`} />
          <FieldChip label={language === 'en' ? 'Strategy' : '策略'} value={language === 'en' ? 'Default MA deterministic template' : '默认均线确定性模板'} />
        </div>
        <div className="flex max-w-full flex-wrap gap-1.5">
          <ActionButton label={language === 'en' ? 'Official selected' : '回测官方入选'} icon={<TestTubeDiagonal className="h-3.5 w-3.5" />} onClick={() => onRunBatch('official_selected')} disabled={isRunning || counts.official_selected === 0} variant="primary" />
          <ActionButton label={language === 'en' ? 'Preview selected' : '回测预览入选'} icon={<TestTubeDiagonal className="h-3.5 w-3.5" />} onClick={() => onRunBatch('preview_selected')} disabled={isRunning || counts.preview_selected === 0} />
          <ActionButton label={language === 'en' ? 'Top 5' : '回测前 5 名'} icon={<TestTubeDiagonal className="h-3.5 w-3.5" />} onClick={() => onRunBatch('top_5')} disabled={isRunning || counts.top_5 === 0} />
          <ActionButton label={language === 'en' ? 'Filtered' : '回测当前筛选'} icon={<TestTubeDiagonal className="h-3.5 w-3.5" />} onClick={() => onRunBatch('current_filter')} disabled={isRunning || counts.current_filter === 0} />
        </div>
        <div className="rounded-lg border border-white/5 bg-black/20 px-3 py-2 font-mono text-[11px] text-white/45">{statusText}</div>
        {items.length ? (
          <div className="overflow-x-auto no-scrollbar rounded-xl border border-white/5 bg-white/[0.02]">
            <table className="min-w-[720px] w-full text-left text-[11px]">
              <thead className="border-b border-white/5 text-[10px] uppercase tracking-widest text-white/40">
                <tr>
                  <th className="px-2 py-2">{language === 'en' ? 'Symbol' : '代码'}</th>
                  <th className="px-2 py-2">{language === 'en' ? 'Status' : '状态'}</th>
                  <th className="px-2 py-2">{language === 'en' ? 'Return' : '收益'}</th>
                  <th className="px-2 py-2">{language === 'en' ? 'Drawdown' : '回撤'}</th>
                  <th className="px-2 py-2">{language === 'en' ? 'Sharpe' : '夏普'}</th>
                  <th className="px-2 py-2">{language === 'en' ? 'Trades' : '交易'}</th>
                  <th className="px-2 py-2">{language === 'en' ? 'Actions' : '操作'}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const resultHref = item.resultId ? buildLocalizedPath(`/backtest/results/${item.resultId}`, language) : null;
                  return (
                    <tr key={item.symbol} className="border-b border-white/5 text-white/62">
                      <td className="px-2 py-2 font-mono text-white">{item.symbol}</td>
                      <td className="px-2 py-2">{item.status}</td>
                      <td className="px-2 py-2 font-mono">{formatPercent(item.totalReturnPct)}</td>
                      <td className="px-2 py-2 font-mono">{formatPercent(item.maxDrawdownPct)}</td>
                      <td className="px-2 py-2 font-mono">{formatMetricNumber(item.sharpe)}</td>
                      <td className="px-2 py-2 font-mono">{item.tradeCount ?? '--'}</td>
                      <td className="px-2 py-2">
                        <div className="flex gap-1.5">
                          {resultHref ? <Link className="rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-white/70 hover:bg-white/10" to={resultHref}>{language === 'en' ? 'Report' : '查看报告'}</Link> : null}
                          <button type="button" className="rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-white/70 hover:bg-white/10" onClick={() => onCopySymbol(item.symbol)}>{language === 'en' ? 'Copy' : '复制'}</button>
                        </div>
                        {item.status === 'failed' && item.error ? <p className="mt-1 max-w-[220px] truncate text-rose-300" title={item.error}>{item.error}</p> : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function simulationToneClass(value?: number | null): string {
  if (value == null || !Number.isFinite(value)) return 'font-mono text-white/50';
  return value >= 0
    ? 'font-mono text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.4)]'
    : 'font-mono text-rose-400 drop-shadow-[0_0_8px_rgba(251,113,133,0.4)]';
}

function formatRatio(value?: number | null): string {
  if (value == null || !Number.isFinite(value)) return '--';
  return `${(value * 100).toFixed(0)}%`;
}

function ScannerStrategySimulationPanel({
  language,
  lookbackDays,
  forwardDays,
  onLookbackDaysChange,
  onForwardDaysChange,
  onRun,
  result,
  isLoading,
  error,
  disabled,
}: {
  language: 'zh' | 'en';
  lookbackDays: number;
  forwardDays: number;
  onLookbackDaysChange: (value: number) => void;
  onForwardDaysChange: (value: number) => void;
  onRun: () => void;
  result: ScannerStrategySimulationResult | null;
  isLoading: boolean;
  error?: string | null;
  disabled: boolean;
}) {
  const statusLabel = result?.status === 'ready'
    ? (language === 'en' ? 'ready' : '就绪')
    : result?.status === 'partial'
      ? (language === 'en' ? 'partial' : '部分')
      : result?.status === 'insufficient_history'
        ? (language === 'en' ? 'insufficient history' : '历史不足')
        : result?.status === 'failed'
          ? (language === 'en' ? 'failed' : '失败')
          : (language === 'en' ? 'idle' : '待运行');
  const summary = result?.summary;
  const compactMessage = disabled
    ? (language === 'en' ? 'Run one scan first, then inspect strategy history.' : '先运行一次扫描，再查看策略历史模拟')
    : result?.status === 'insufficient_history'
      ? (result.warnings[0] || (language === 'en' ? `Insufficient scans · ${result.window.runCount} comparable runs` : `历史扫描不足 · 当前只有 ${result.window.runCount} 次可比较运行`))
      : null;

  return (
    <section
      data-testid="scanner-strategy-simulation"
      className="rounded-xl border border-white/5 bg-white/[0.015] p-3 text-xs"
    >
      <div className="flex min-w-0 items-center gap-2">
        <Clock className="h-3.5 w-3.5 text-white/38" aria-hidden="true" />
        <h3 className="truncate text-[10px] font-bold uppercase tracking-widest text-white/40">
                          {language === 'en' ? `History sim · ${lookbackDays}D · Forward ${forwardDays}D` : `历史模拟 · 回看 ${lookbackDays}D · 持有 ${forwardDays}D`}
        </h3>
      </div>
      <div className="mt-2 grid gap-3" data-testid="scanner-strategy-simulation-body">
        <div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
          <div className="min-w-0">
            <span className="mb-1 block text-[10px] font-bold uppercase tracking-widest text-white/40">{language === 'en' ? 'Lookback' : '回看'}</span>
            <div className="ui-scroll-x-quiet flex gap-1 rounded-lg border border-white/5 bg-black/30 p-0.5">
              {[30, 90, 180].map((value) => (
                <button
                  key={value}
                  type="button"
                  className={`shrink-0 rounded-md px-2.5 py-1 font-mono text-[11px] ${lookbackDays === value ? 'bg-white/10 text-white' : 'text-white/45 hover:text-white/75'}`}
                  onClick={() => onLookbackDaysChange(value)}
                >
                  {value}D
                </button>
              ))}
            </div>
          </div>
          <div className="min-w-0">
            <span className="mb-1 block text-[10px] font-bold uppercase tracking-widest text-white/40">{language === 'en' ? 'Forward' : '持有'}</span>
            <div className="ui-scroll-x-quiet flex gap-1 rounded-lg border border-white/5 bg-black/30 p-0.5">
              {[1, 5, 10, 20].map((value) => (
                <button
                  key={value}
                  type="button"
                  className={`shrink-0 rounded-md px-2.5 py-1 font-mono text-[11px] ${forwardDays === value ? 'bg-white/10 text-white' : 'text-white/45 hover:text-white/75'}`}
                  onClick={() => onForwardDaysChange(value)}
                >
                  {value}D
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-end">
            <ActionButton
              label={isLoading ? (language === 'en' ? 'Running' : '运行中') : (language === 'en' ? 'Run sim' : '运行模拟')}
              icon={<Play className="h-3.5 w-3.5" />}
              onClick={onRun}
              disabled={disabled || isLoading}
              variant="primary"
            />
          </div>
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-2 rounded-lg border border-white/5 bg-black/20 px-3 py-2">
          <span className="text-[10px] font-bold uppercase tracking-widest text-white/40">{language === 'en' ? 'Status' : '状态'}</span>
          <span className="font-mono text-white/72" data-testid="scanner-strategy-simulation-status">{statusLabel}</span>
          {compactMessage ? <span className="min-w-0 truncate text-white/50" data-testid="scanner-strategy-simulation-compact-message">{compactMessage}</span> : null}
          {error ? <span className="min-w-0 truncate text-rose-300" data-testid="scanner-strategy-simulation-error">{error}</span> : null}
        </div>
        {summary && result?.status !== 'insufficient_history' ? (
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-6" data-testid="scanner-strategy-simulation-summary">
            {[
              [language === 'en' ? 'Runs' : '历史批次', String(summary.historicalRuns)],
              [language === 'en' ? 'Events' : '入选事件', String(summary.selectionEvents)],
              [language === 'en' ? 'Avg fwd' : '平均远期', formatPercent(summary.avgForwardReturnPct)],
              [language === 'en' ? 'Hit' : '命中率', formatRatio(summary.hitRate)],
              [language === 'en' ? 'Excess' : '超额', formatPercent(summary.avgExcessReturnPct)],
              [language === 'en' ? 'Coverage' : '覆盖率', formatRatio(summary.dataCoverage)],
            ].map(([label, value]) => (
              <div key={label} className="min-w-0 rounded-xl border border-white/5 bg-black/20 px-3 py-2">
                <span className="block truncate text-[10px] font-bold uppercase tracking-widest text-white/40">{label}</span>
                <span className={`${String(label).includes('Avg') || String(label).includes('Excess') || String(label).includes('平均') || String(label).includes('超额') ? simulationToneClass(parseFirstNumericValue(value)) : 'font-mono text-white/78'} block truncate text-sm`}>{value}</span>
              </div>
            ))}
          </div>
        ) : null}
        {result?.warnings.length ? (
          <div className="grid gap-1 rounded-lg border border-amber-300/10 bg-amber-300/[0.04] px-3 py-2 text-[11px] text-amber-100/70" data-testid="scanner-strategy-simulation-warnings">
            {result.warnings.map((warning) => <span key={warning} className="truncate">{warning}</span>)}
          </div>
        ) : null}
        {result?.runs.length ? (
          <div className="overflow-x-auto no-scrollbar rounded-xl border border-white/5 bg-white/[0.02]" data-testid="scanner-strategy-simulation-runs">
            <table className="min-w-[720px] w-full text-left text-[11px]">
              <thead className="border-b border-white/5 text-[10px] uppercase tracking-widest text-white/40">
                <tr>
                  <th className="px-2 py-2">Run</th>
                  <th className="px-2 py-2">{language === 'en' ? 'Selected' : '入选'}</th>
                  <th className="px-2 py-2">{language === 'en' ? 'Rejected' : '淘汰'}</th>
                  <th className="px-2 py-2">{language === 'en' ? 'Symbols' : '标的'}</th>
                  <th className="px-2 py-2">Forward</th>
                  <th className="px-2 py-2">Benchmark</th>
                  <th className="px-2 py-2">Excess</th>
                </tr>
              </thead>
              <tbody>
                {result.runs.map((item) => (
                  <tr key={item.runId} className="border-b border-white/5 text-white/62">
                    <td className="px-2 py-2 font-mono text-white">#{item.runId}</td>
                    <td className="px-2 py-2 font-mono">{item.selectedCount}</td>
                    <td className="px-2 py-2 font-mono">{item.rejectedCount}</td>
                    <td className="max-w-[180px] truncate px-2 py-2 font-mono text-white/72" title={item.selectedSymbols.join(', ')}>{item.selectedSymbols.join(', ') || '--'}</td>
                    <td className={`px-2 py-2 ${simulationToneClass(item.avgForwardReturnPct)}`}>{formatPercent(item.avgForwardReturnPct)}</td>
                    <td className={`px-2 py-2 ${simulationToneClass(item.benchmarkReturnPct)}`}>{formatPercent(item.benchmarkReturnPct)}</td>
                    <td className={`px-2 py-2 ${simulationToneClass(item.excessReturnPct)}`}>{formatPercent(item.excessReturnPct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        {result?.symbols.length ? (
          <div className="overflow-x-auto no-scrollbar rounded-xl border border-white/5 bg-white/[0.02]" data-testid="scanner-strategy-simulation-symbols">
            <table className="min-w-[680px] w-full text-left text-[11px]">
              <thead className="border-b border-white/5 text-[10px] uppercase tracking-widest text-white/40">
                <tr>
                  <th className="px-2 py-2">Symbol</th>
                  <th className="px-2 py-2">{language === 'en' ? 'Count' : '次数'}</th>
                  <th className="px-2 py-2">Score</th>
                  <th className="px-2 py-2">Forward</th>
                  <th className="px-2 py-2">Hit</th>
                  <th className="px-2 py-2">Best</th>
                  <th className="px-2 py-2">Worst</th>
                </tr>
              </thead>
              <tbody>
                {result.symbols.map((item) => (
                  <tr key={item.symbol} className="border-b border-white/5 text-white/62">
                    <td className="px-2 py-2 font-mono text-white">{item.symbol}</td>
                    <td className="px-2 py-2 font-mono">{item.selectionCount}</td>
                    <td className="px-2 py-2 font-mono">{formatMetricNumber(item.avgScore, 1)}</td>
                    <td className={`px-2 py-2 ${simulationToneClass(item.avgForwardReturnPct)}`}>{formatPercent(item.avgForwardReturnPct)}</td>
                    <td className="px-2 py-2 font-mono">{formatRatio(item.hitRate)}</td>
                    <td className={`px-2 py-2 ${simulationToneClass(item.bestForwardReturnPct)}`}>{formatPercent(item.bestForwardReturnPct)}</td>
                    <td className={`px-2 py-2 ${simulationToneClass(item.worstForwardReturnPct)}`}>{formatPercent(item.worstForwardReturnPct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function hasRunDiagnosticsContent(runDetail: ScannerRunDetail): boolean {
  const coverage = getRunCoverageSummary(runDetail);
  const provider = getRunProviderDiagnostics(runDetail);
  const aiDiagnostics = getAiDiagnostics(runDetail);
  return Boolean(coverage
    || provider
    || runDetail.universeNotes.length
    || runDetail.scoringNotes.length
    || hasReviewSummary(runDetail.reviewSummary)
    || hasComparison(runDetail.comparisonToPrevious)
    || aiDiagnostics);
}

function DiagnosticsPanel({
  runDetail,
  language,
}: {
  runDetail: ScannerRunDetail;
  language: 'zh' | 'en';
}) {
  const coverage = getRunCoverageSummary(runDetail);
  const provider = getRunProviderDiagnostics(runDetail);
  const aiDiagnostics = getAiDiagnostics(runDetail);
  const hasAnyDiagnostics = hasRunDiagnosticsContent(runDetail);

  if (!hasAnyDiagnostics) return null;

  return (
    <section data-testid="scanner-diagnostics-panel" className="mt-3 rounded-xl border border-white/5 bg-white/[0.015] p-3">
      <h3 className="text-[10px] font-bold uppercase tracking-widest text-white/40">
        {language === 'en' ? 'Diagnostics and replay notes' : '诊断与复盘说明'}
      </h3>
      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        {coverage ? (
          <DetailSection title={language === 'en' ? 'Coverage summary' : '覆盖摘要'}>
            <div className="flex flex-wrap gap-2">
              <FieldChip label={language === 'en' ? 'Input' : '输入'} value={String(coverage.inputUniverseSize)} />
              <FieldChip label={language === 'en' ? 'Liquidity' : '流动性后'} value={String(coverage.eligibleAfterLiquidityFilter)} />
              <FieldChip label={language === 'en' ? 'Data OK' : '数据可用'} value={String(coverage.eligibleAfterDataAvailabilityFilter)} />
              <FieldChip label={language === 'en' ? 'Ranked' : '已排名'} value={String(coverage.rankedCandidateCount)} />
              <FieldChip label={language === 'en' ? 'Selected' : '入选'} value={String(coverage.shortlistedCount)} />
              {coverage.likelyBottleneckLabel || coverage.likelyBottleneck ? (
                <FieldChip label={language === 'en' ? 'Bottleneck' : '瓶颈'} value={coverage.likelyBottleneckLabel || coverage.likelyBottleneck || ''} />
              ) : null}
            </div>
          </DetailSection>
        ) : null}
        {provider ? (
          <DetailSection title={language === 'en' ? 'Provider diagnostics' : '供应商诊断'}>
            <p className="text-xs leading-relaxed text-white/64">{formatProviderDiagnostics(provider, language)}</p>
            {provider.providerWarnings?.length ? <NotesList notes={provider.providerWarnings} empty="" /> : null}
          </DetailSection>
        ) : null}
        {runDetail.universeNotes.length ? (
          <DetailSection title={language === 'en' ? 'Universe notes' : '候选范围说明'}>
            <NotesList notes={runDetail.universeNotes} empty="" />
          </DetailSection>
        ) : null}
        {runDetail.scoringNotes.length ? (
          <DetailSection title={language === 'en' ? 'Scoring notes' : '评分说明'}>
            <NotesList notes={runDetail.scoringNotes} empty="" />
          </DetailSection>
        ) : null}
        {hasReviewSummary(runDetail.reviewSummary) ? (
          <DetailSection title={language === 'en' ? 'Review summary' : '复盘摘要'}>
            <div className="flex flex-wrap gap-2">
              <FieldChip label={language === 'en' ? 'Status' : '状态'} value={runDetail.reviewSummary.reviewStatus} />
              <FieldChip label={language === 'en' ? 'Reviewed' : '已复盘'} value={`${runDetail.reviewSummary.reviewedCount}/${runDetail.reviewSummary.candidateCount}`} />
              {runDetail.reviewSummary.hitRatePct != null ? <FieldChip label={language === 'en' ? 'Hit rate' : '命中率'} value={formatPercent(runDetail.reviewSummary.hitRatePct)} /> : null}
              {runDetail.reviewSummary.avgReviewWindowReturnPct != null ? <FieldChip label={language === 'en' ? 'Avg return' : '平均收益'} value={formatPercent(runDetail.reviewSummary.avgReviewWindowReturnPct)} /> : null}
            </div>
          </DetailSection>
        ) : null}
        {hasComparison(runDetail.comparisonToPrevious) ? (
          <DetailSection title={language === 'en' ? 'Comparison to previous' : '相对上次变化'}>
            <div className="flex flex-wrap gap-2">
              <FieldChip label={language === 'en' ? 'New' : '新增'} value={String(runDetail.comparisonToPrevious.newCount)} />
              <FieldChip label={language === 'en' ? 'Retained' : '保留'} value={String(runDetail.comparisonToPrevious.retainedCount)} />
              <FieldChip label={language === 'en' ? 'Dropped' : '移出'} value={String(runDetail.comparisonToPrevious.droppedCount)} />
            </div>
          </DetailSection>
        ) : null}
        {aiDiagnostics ? (
          <DetailSection title={language === 'en' ? 'AI status' : 'AI 状态'}>
            <div className="flex flex-wrap gap-2">
              {Object.entries(aiDiagnostics)
                .map(([key, value]) => [key, toDisplayText(value)] as const)
                .filter((entry): entry is readonly [string, string] => Boolean(entry[1]))
                .slice(0, 6)
                .map(([key, value]) => <FieldChip key={key} label={key} value={value} />)}
            </div>
          </DetailSection>
        ) : null}
      </div>
    </section>
  );
}

const UserScannerPage: React.FC = () => {
  const { isReady: isSafariReady, surfaceRef } = useSafariRenderReady();
  const shouldGuardA11y = shouldApplySafariA11yGuard();
  const { t, language } = useI18n();
  const navigate = useNavigate();
  const [market, setMarket] = useState<'cn' | 'us' | 'hk'>('cn');
  const [profile, setProfile] = useState('cn_preopen_v1');
  const [shortlistSize, setShortlistSize] = useState('5');
  const [universeLimit, setUniverseLimit] = useState('300');
  const [detailLimit, setDetailLimit] = useState('60');
  const [scanScope, setScanScope] = useState<ScanScope>('default');
  const [themes, setThemes] = useState<ScannerTheme[]>([]);
  const [themeId, setThemeId] = useState('');
  const [customThemeLabel, setCustomThemeLabel] = useState('');
  const [customThemePrompt, setCustomThemePrompt] = useState('');
  const [customThemeManualSymbols, setCustomThemeManualSymbols] = useState('');
  const [themeSuggestions, setThemeSuggestions] = useState<ScannerThemeSuggestion[]>([]);
  const [isGeneratingTheme, setIsGeneratingTheme] = useState(false);
  const [customSymbols, setCustomSymbols] = useState('');
  const [runDetail, setRunDetail] = useState<ScannerRunDetail | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [historyItems, setHistoryItems] = useState<ScannerRunHistoryItem[]>([]);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [isRunning, setIsRunning] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [pageError, setPageError] = useState<ParsedApiError | null>(null);
  const [historyError, setHistoryError] = useState<ParsedApiError | null>(null);
  const [actionNotice, setActionNotice] = useState<ActionNotice>(null);
  const [validationErrors, setValidationErrors] = useState<ScannerValidationErrors>({});
  const [isHistoryDrawerOpen, setIsHistoryDrawerOpen] = useState(false);
  const [watchlistItems, setWatchlistItems] = useState<WatchlistItem[]>([]);
  const [watchlistAuthBlocked, setWatchlistAuthBlocked] = useState(false);
  const [pendingWatchlistIdentity, setPendingWatchlistIdentity] = useState<string | null>(null);
  const [pendingBatchWatchlistAction, setPendingBatchWatchlistAction] = useState<string | null>(null);
  const [isMoreActionsOpen, setIsMoreActionsOpen] = useState(false);
  const [rowMoreSymbol, setRowMoreSymbol] = useState<string | null>(null);
  const [isRejectionSummaryOpen, setIsRejectionSummaryOpen] = useState(false);
  const [isDeveloperDiagnosticsOpen, setIsDeveloperDiagnosticsOpen] = useState(false);
  const [previousRunDetail, setPreviousRunDetail] = useState<ScannerRunDetail | null>(null);
  const [previewThreshold, setPreviewThreshold] = useState(50);
  const [viewMode, setViewMode] = useState<ViewMode>('cards');
  const [sortKey, setSortKey] = useState<SortKey>('score');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [expandedSymbol, setExpandedSymbol] = useState<string | null>(null);
  const [inspectorSymbol, setInspectorSymbol] = useState<string | null>(null);
  const [pendingAnalyzeSymbol, setPendingAnalyzeSymbol] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [candidateFilter, setCandidateFilter] = useState<CandidateFilter>('pool');
  const [backtestItemsBySymbol, setBacktestItemsBySymbol] = useState<Record<string, ScannerBacktestItem>>({});
  const [isBacktestBatchRunning, setIsBacktestBatchRunning] = useState(false);
  const [simulationLookbackDays, setSimulationLookbackDays] = useState(90);
  const [simulationForwardDays, setSimulationForwardDays] = useState(5);
  const [strategySimulation, setStrategySimulation] = useState<ScannerStrategySimulationResult | null>(null);
  const [isStrategySimulationLoading, setIsStrategySimulationLoading] = useState(false);
  const [strategySimulationError, setStrategySimulationError] = useState<string | null>(null);
  const inFlightBacktestKeysRef = useRef<Set<string>>(new Set());
  const completedBacktestKeysRef = useRef<Map<string, ScannerBacktestItem>>(new Map());

  useEffect(() => {
    document.title = t('scanner.documentTitle');
  }, [t]);

  const profileOptions = useMemo(() => getScannerProfileOptions(market, t), [market, t]);
  const universeOptions = useMemo(() => getScannerUniverseOptions(market, language), [language, market]);
  const detailOptions = useMemo(() => getScannerDetailOptions(market, language), [language, market]);
  const marketThemes = useMemo(
    () => themes.filter((theme) => theme.market === market),
    [market, themes],
  );
  const configuredMarketThemes = useMemo(
    () => marketThemes.filter((theme) => theme.symbols.length > 0),
    [marketThemes],
  );
  const unconfiguredMarketThemes = useMemo(
    () => marketThemes.filter((theme) => theme.symbols.length === 0),
    [marketThemes],
  );
  const selectedTheme = useMemo(
    () => marketThemes.find((theme) => theme.id === themeId) || null,
    [marketThemes, themeId],
  );
  const parsedCustomSymbols = useMemo(() => parseCustomSymbols(customSymbols), [customSymbols]);
  const parsedThemeManualSymbols = useMemo(() => parseCustomSymbols(customThemeManualSymbols), [customThemeManualSymbols]);
  const customSymbolTokenCount = useMemo(() => getSymbolTokenCount(customSymbols), [customSymbols]);
  const customThemeManualSymbolTokenCount = useMemo(() => getSymbolTokenCount(customThemeManualSymbols), [customThemeManualSymbols]);

  const handleMarketChange = useCallback((nextMarket: string) => {
    const normalizedMarket = nextMarket === 'us' ? 'us' : nextMarket === 'hk' ? 'hk' : 'cn';
    const defaults = SCANNER_PROFILE_DEFAULTS[normalizedMarket];
    setMarket(normalizedMarket);
    setProfile(defaults.profile);
    setShortlistSize(defaults.shortlistSize);
    setUniverseLimit(defaults.universeLimit);
    setDetailLimit(defaults.detailLimit);
    setThemeId('');
    setValidationErrors({});
  }, []);

  useEffect(() => {
    let isMounted = true;
    scannerApi.getThemes()
      .then((response) => {
        if (!isMounted) return;
        setThemes(response.items || []);
      })
      .catch((error) => {
        if (!isMounted) return;
        setPageError(getParsedApiError(error));
      });
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (scanScope !== 'theme') return;
    if (selectedTheme?.market === market) return;
    const firstConfiguredTheme = marketThemes.find((theme) => theme.symbols.length > 0);
    setThemeId(firstConfiguredTheme?.id || '');
  }, [market, marketThemes, scanScope, selectedTheme?.market]);

  useEffect(() => {
    let isMounted = true;
    watchlistApi.listWatchlistItems()
      .then((response) => {
        if (!isMounted) return;
        setWatchlistItems(response.items || []);
        setWatchlistAuthBlocked(false);
      })
      .catch((error) => {
        if (!isMounted) return;
        const parsedError = getParsedApiError(error);
        if (parsedError.isAuthError || parsedError.status === 401 || parsedError.status === 403 || parsedError.status === 405) {
          setWatchlistAuthBlocked(true);
          return;
        }
        setWatchlistItems([]);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const loadRun = useCallback(async (runId: number) => {
    try {
      const response = await scannerApi.getRun(runId);
      setRunDetail(response);
      setSelectedRunId(response.id);
      setExpandedSymbol(null);
      setPageError(null);
    } catch (error) {
      setPageError(getParsedApiError(error));
    }
  }, []);

  const fetchHistory = useCallback(async (page = 1, preferredRunId?: number | null) => {
    setIsLoadingHistory(true);
    try {
      const response = await scannerApi.getRuns({
        market,
        profile,
        page,
        limit: HISTORY_PAGE_SIZE,
      });
      setHistoryItems(response.items);
      setHistoryTotal(response.total);
      setHistoryPage(response.page);
      setHistoryError(null);

      const targetRunId = preferredRunId
        || (selectedRunId && response.items.some((item) => item.id === selectedRunId) ? selectedRunId : null)
        || response.items[0]?.id
        || null;
      if (targetRunId && targetRunId !== selectedRunId) {
        void loadRun(targetRunId);
      }
      if (!targetRunId) {
        setRunDetail(null);
        setSelectedRunId(null);
      }
    } catch (error) {
      setHistoryError(getParsedApiError(error));
    } finally {
      setIsLoadingHistory(false);
    }
  }, [loadRun, market, profile, selectedRunId]);

  useEffect(() => {
    setRunDetail(null);
    setSelectedRunId(null);
    setExpandedSymbol(null);
    setStrategySimulation(null);
    setStrategySimulationError(null);
  }, [market, profile]);

  useEffect(() => {
    void fetchHistory(1);
  }, [fetchHistory]);

  const handleRun = useCallback(async () => {
    const nextErrors: ScannerValidationErrors = {};
    const parsedShortlistSize = Number.parseInt(shortlistSize, 10);
    const parsedUniverseLimit = Number.parseInt(universeLimit, 10);
    const parsedDetailLimit = Number.parseInt(detailLimit, 10);
    if (!Number.isFinite(parsedShortlistSize) || parsedShortlistSize < 1) {
      nextErrors.run = language === 'en' ? 'Choose a valid shortlist size.' : '请选择有效的入选数量。';
    }
    if (!Number.isFinite(parsedUniverseLimit) || parsedUniverseLimit < 50) {
      nextErrors.run = language === 'en' ? 'Universe size must be at least 50.' : '候选池数量至少为 50。';
    }
    if (!Number.isFinite(parsedDetailLimit) || parsedDetailLimit < 10) {
      nextErrors.run = language === 'en' ? 'Detail evaluation count must be at least 10.' : '详细评估数量至少为 10。';
    }
    if (scanScope === 'theme' && (!selectedTheme || selectedTheme.symbols.length === 0)) {
      nextErrors.theme = language === 'en' ? 'Select a configured theme before running.' : '请先选择已配置成分股的主题。';
    }
    if (scanScope === 'symbols') {
      if (customSymbolTokenCount > 0 && parsedCustomSymbols.length === 0) {
        nextErrors.customSymbols = language === 'en' ? 'Enter at least one valid symbol.' : '请输入至少一个有效标的代码。';
      } else if (parsedCustomSymbols.length === 0) {
        nextErrors.customSymbols = language === 'en' ? 'Enter one or more symbols before running.' : '运行前请输入一个或多个标的代码。';
      } else if (parsedCustomSymbols.length > 80) {
        nextErrors.customSymbols = language === 'en' ? 'Use 80 symbols or fewer.' : '自定义标的最多 80 个。';
      }
    }
    if (Object.keys(nextErrors).length) {
      setValidationErrors(nextErrors);
      return;
    }
    setIsRunning(true);
    try {
      const response = await scannerApi.run({
        market,
        profile,
        shortlistSize: parsedShortlistSize,
        universeLimit: parsedUniverseLimit,
        detailLimit: parsedDetailLimit,
        ...(scanScope !== 'default' ? { universeType: scanScope } : {}),
        ...(scanScope === 'theme' ? { themeId } : {}),
        ...(scanScope === 'symbols' ? { symbols: parsedCustomSymbols } : {}),
      });
      setRunDetail(response);
      setSelectedRunId(response.id);
      setExpandedSymbol(null);
      setValidationErrors({});
      setPageError(null);
      await fetchHistory(1, response.id);
    } catch (error) {
      setPageError(getParsedApiError(error));
    } finally {
      setIsRunning(false);
    }
  }, [customSymbolTokenCount, detailLimit, fetchHistory, language, market, parsedCustomSymbols, profile, scanScope, selectedTheme, shortlistSize, themeId, universeLimit]);

  const handleGenerateTheme = useCallback(async () => {
    const label = customThemeLabel.trim();
    const prompt = customThemePrompt.trim();
    const nextErrors: ScannerValidationErrors = {};
    if (label.length < 2) {
      nextErrors.customThemeLabel = language === 'en' ? 'Theme name must be at least 2 characters.' : '主题名称至少需要 2 个字符。';
    } else if (label.length > 80) {
      nextErrors.customThemeLabel = language === 'en' ? 'Theme name must be 80 characters or fewer.' : '主题名称最多 80 个字符。';
    }
    if (prompt.length < 12) {
      nextErrors.customThemePrompt = language === 'en' ? 'Criteria must be at least 12 characters.' : '筛选条件至少需要 12 个字符。';
    } else if (prompt.length > 600) {
      nextErrors.customThemePrompt = language === 'en' ? 'Criteria must be 600 characters or fewer.' : '筛选条件最多 600 个字符。';
    }
    if (parsedThemeManualSymbols.length > 50) {
      nextErrors.customThemeManualSymbols = language === 'en' ? 'Manual additions are limited to 50 symbols.' : '手动补充标的最多 50 个。';
    } else if (customThemeManualSymbolTokenCount > 0 && parsedThemeManualSymbols.length === 0) {
      nextErrors.customThemeManualSymbols = language === 'en' ? 'Enter valid symbols or leave this field empty.' : '请输入有效标的代码，或留空。';
    }
    if (Object.keys(nextErrors).length) {
      setValidationErrors(nextErrors);
      return;
    }
    setIsGeneratingTheme(true);
    try {
      const response = await scannerApi.createTheme({
        id: buildCustomThemeId(label),
        label,
        market,
        prompt,
        manualSymbols: parsedThemeManualSymbols,
      });
      setThemes((current) => [
        ...current.filter((theme) => theme.id !== response.theme.id),
        response.theme,
      ]);
      setThemeId(response.theme.id);
      setThemeSuggestions(response.suggestions || []);
      setValidationErrors({});
      setActionNotice({
        tone: 'success',
        message: language === 'en'
          ? `Generated ${response.theme.symbols.length} symbols for ${getThemeLabel(response.theme, language)}.`
          : `已为 ${getThemeLabel(response.theme, language)} 生成 ${response.theme.symbols.length} 个标的。`,
      });
      setPageError(null);
    } catch (error) {
      setPageError(getParsedApiError(error));
    } finally {
      setIsGeneratingTheme(false);
    }
  }, [customThemeLabel, customThemeManualSymbolTokenCount, customThemePrompt, language, market, parsedThemeManualSymbols]);

  const handleSortChange = useCallback((nextSortKey: SortKey) => {
    if (sortKey === nextSortKey) {
      setSortDirection((current) => current === 'asc' ? 'desc' : 'asc');
      return;
    }
    setSortKey(nextSortKey);
    setSortDirection(nextSortKey === 'symbol' ? 'asc' : 'desc');
  }, [sortKey]);

  const totalHistoryPages = useMemo(
    () => Math.max(1, Math.ceil(historyTotal / HISTORY_PAGE_SIZE)),
    [historyTotal],
  );
  const trackedWatchlistIdentitySet = useMemo(
    () => new Set(watchlistItems.map((item) => getWatchlistIdentity(item.market, item.symbol))),
    [watchlistItems],
  );
  const runScannerButton = useSafariWarmActivation<HTMLButtonElement>(() => {
    void handleRun();
  });
  const generateThemeButton = useSafariWarmActivation<HTMLButtonElement>(() => {
    void handleGenerateTheme();
  });
  const openHistoryDrawerButton = useSafariWarmActivation<HTMLButtonElement>(() => setIsHistoryDrawerOpen(true));
  const shortlistCount = runDetail?.shortlist?.length ?? 0;
  const generatedAt = runDetail?.completedAt || runDetail?.runAt || null;
  const runDisabled = isRunning;
  const generateThemeDisabled = isGeneratingTheme;

  const sortedCandidates = useMemo(() => {
    const candidates = [...(runDetail?.shortlist || [])];
    const directionMultiplier = sortDirection === 'asc' ? 1 : -1;
    return candidates.sort((left, right) => {
      let compare = 0;
      if (sortKey === 'symbol') {
        compare = left.symbol.localeCompare(right.symbol);
      } else if (sortKey === 'target') {
        const leftTarget = parseFirstNumericValue(getTargetPrice(left));
        const rightTarget = parseFirstNumericValue(getTargetPrice(right));
        compare = (leftTarget ?? Number.NEGATIVE_INFINITY) - (rightTarget ?? Number.NEGATIVE_INFINITY);
      } else if (sortKey === 'risk') {
        const leftRisk = getRiskScore(left);
        const rightRisk = getRiskScore(right);
        compare = (leftRisk ?? Number.NEGATIVE_INFINITY) - (rightRisk ?? Number.NEGATIVE_INFINITY);
      } else {
        compare = left.score - right.score;
      }
      if (compare === 0) return left.rank - right.rank;
      return compare * directionMultiplier;
    });
  }, [runDetail?.shortlist, sortDirection, sortKey]);
  const diagnosticCandidates = useMemo(() => getCandidateDiagnostics(runDetail), [runDetail]);
  const hasCandidateDiagnostics = diagnosticCandidates.length > 0;
  const inferredPreviewThreshold = useMemo(
    () => inferPreviewThreshold(runDetail, diagnosticCandidates),
    [diagnosticCandidates, runDetail],
  );
  useEffect(() => {
    if (!runDetail) return;
    setPreviewThreshold(inferredPreviewThreshold);
  }, [inferredPreviewThreshold, runDetail]);
  const previewSelectedDiagnostics = useMemo(
    () => diagnosticCandidates.filter((candidate) => isPreviewSelected(candidate, previewThreshold)),
    [diagnosticCandidates, previewThreshold],
  );
  const previewAddedDiagnostics = useMemo(
    () => previewSelectedDiagnostics.filter((candidate) => !isOfficialSelected(candidate)),
    [previewSelectedDiagnostics],
  );
  const officialSelectedDiagnostics = useMemo(
    () => diagnosticCandidates.filter(isOfficialSelected),
    [diagnosticCandidates],
  );
  const decisionSummary = useMemo(
    () => runDetail ? buildDecisionSummary(runDetail, sortedCandidates, diagnosticCandidates, language) : null,
    [diagnosticCandidates, language, runDetail, sortedCandidates],
  );
  const rejectionBuckets = useMemo(
    () => buildRejectionBuckets(diagnosticCandidates, language),
    [diagnosticCandidates, language],
  );
  const previewCandidates = useMemo(
    () => diagnosticCandidates.filter((candidate) => candidate.status !== 'selected').slice(0, 5),
    [diagnosticCandidates],
  );
  const comparisonState = useMemo(
    () => buildRunComparison(runDetail, previousRunDetail, previewThreshold, language),
    [language, previewThreshold, previousRunDetail, runDetail],
  );
  const inspectorCandidate = useMemo(
    () => getSelectedDiagnosticCandidate(diagnosticCandidates, sortedCandidates, inspectorSymbol),
    [diagnosticCandidates, inspectorSymbol, sortedCandidates],
  );
  const filteredDiagnosticCandidates = useMemo(() => {
    if (candidateFilter === 'selected') {
      return diagnosticCandidates.filter((candidate) => candidate.status === 'selected');
    }
    if (candidateFilter === 'pool') {
      return diagnosticCandidates;
    }
    if (candidateFilter === 'rejected') {
      return diagnosticCandidates.filter((candidate) => candidate.status === 'rejected');
    }
    if (candidateFilter === 'data_failed') {
      return diagnosticCandidates.filter((candidate) => candidate.status === 'data_failed' || candidate.status === 'error');
    }
    return diagnosticCandidates;
  }, [candidateFilter, diagnosticCandidates]);
  const decisionSortedDiagnosticCandidates = useMemo(
    () => sortDiagnosticsForDecision(filteredDiagnosticCandidates, previewThreshold),
    [filteredDiagnosticCandidates, previewThreshold],
  );
  const selectedOnlyView = !hasCandidateDiagnostics || candidateFilter === 'selected';
  const topFiveDiagnostics = useMemo(
    () => sortDiagnosticsForDecision(diagnosticCandidates, previewThreshold).slice(0, 5),
    [diagnosticCandidates, previewThreshold],
  );
  const backtestItems = useMemo(
    () => Object.values(backtestItemsBySymbol).sort((left, right) => left.symbol.localeCompare(right.symbol)),
    [backtestItemsBySymbol],
  );
  const backtestCounts = useMemo<Record<ScannerBacktestSource, number>>(() => ({
    official_selected: dedupeBacktestCandidates(sortedCandidates).length,
    preview_selected: dedupeBacktestCandidates(previewSelectedDiagnostics.map(diagnosticToCandidate)).length,
    top_5: dedupeBacktestCandidates(topFiveDiagnostics.map(diagnosticToCandidate)).length,
    current_filter: dedupeBacktestCandidates(decisionSortedDiagnosticCandidates.map(diagnosticToCandidate)).length,
    manual: 1,
  }), [decisionSortedDiagnosticCandidates, previewSelectedDiagnostics, sortedCandidates, topFiveDiagnostics]);
  const activeSimulationTheme = runDetail?.themeId || (scanScope === 'theme' ? themeId : null);
  const strategySimulationDisabled = !runDetail || (runDetail.universeType === 'theme' && !runDetail.themeId);

  const handleStrategySimulation = useCallback(async () => {
    if (!runDetail) return;
    setIsStrategySimulationLoading(true);
    try {
      const response = await scannerApi.getStrategySimulation({
        theme: activeSimulationTheme || undefined,
        profile: runDetail.profile || profile,
        market: runDetail.market || market,
        lookbackDays: simulationLookbackDays,
        forwardDays: simulationForwardDays,
        limit: 50,
      });
      setStrategySimulation(response);
      setStrategySimulationError(null);
    } catch (error) {
      const parsed = getParsedApiError(error);
      setStrategySimulationError(parsed.message || (language === 'en' ? 'Simulation failed.' : '历史模拟失败。'));
    } finally {
      setIsStrategySimulationLoading(false);
    }
  }, [activeSimulationTheme, language, market, profile, runDetail, simulationForwardDays, simulationLookbackDays]);

  const runScannerBacktests = useCallback(async (source: ScannerBacktestSource, candidates: ScannerCandidate[]) => {
    const targetCandidates = dedupeBacktestCandidates(candidates);
    if (!targetCandidates.length) return;
    if (source !== 'manual' && isBacktestBatchRunning) return;

    const queue: ScannerCandidate[] = [];
    targetCandidates.forEach((candidate) => {
      const symbol = normalizeCandidateSymbol(candidate.symbol);
      if (!symbol) return;
      const key = getScannerBacktestKey(symbol);
      const existing = completedBacktestKeysRef.current.get(key);
      if (existing) {
        setBacktestItemsBySymbol((current) => ({
          ...current,
          [symbol]: { ...existing, status: 'skipped_existing' },
        }));
        return;
      }
      if (inFlightBacktestKeysRef.current.has(key)) return;
      inFlightBacktestKeysRef.current.add(key);
      queue.push({ ...candidate, symbol });
      setBacktestItemsBySymbol((current) => ({
        ...current,
        [symbol]: { symbol, status: 'queued' },
      }));
    });
    if (!queue.length) return;

    const config = getScannerBacktestConfig();
    const runOne = async (candidate: ScannerCandidate) => {
      const symbol = normalizeCandidateSymbol(candidate.symbol);
      if (!symbol) return;
      const key = getScannerBacktestKey(symbol);
      setBacktestItemsBySymbol((current) => ({
        ...current,
        [symbol]: { ...(current[symbol] || { symbol }), status: 'running' },
      }));
      try {
        const strategyText = buildPointAndShootStrategyText(language, config.strategyTemplate, {
          code: symbol,
          startDate: config.startDate,
          endDate: config.endDate,
          initialCapital: String(config.initialCapital),
        });
        const response = await backtestApi.runRuleBacktest({
          code: symbol,
          strategyText,
          startDate: config.startDate,
          endDate: config.endDate,
          lookbackBars: 252,
          initialCapital: config.initialCapital,
          feeBps: config.feeBps,
          slippageBps: config.slippageBps,
          benchmarkMode: config.benchmarkMode,
          confirmed: true,
          waitForCompletion: true,
        });
        const item = mapRuleRunToScannerBacktestItem(response, response.status === 'failed' ? 'failed' : 'completed');
        completedBacktestKeysRef.current.set(key, item);
        setBacktestItemsBySymbol((current) => ({
          ...current,
          [symbol]: item,
        }));
      } catch (error) {
        setBacktestItemsBySymbol((current) => ({
          ...current,
          [symbol]: {
            symbol,
            status: 'failed',
            error: getBacktestErrorMessage(error, language),
          },
        }));
      } finally {
        inFlightBacktestKeysRef.current.delete(key);
      }
    };

    if (source !== 'manual') setIsBacktestBatchRunning(true);
    try {
      for (let index = 0; index < queue.length; index += SCANNER_BACKTEST_CONCURRENCY) {
        await Promise.all(queue.slice(index, index + SCANNER_BACKTEST_CONCURRENCY).map(runOne));
      }
    } finally {
      if (source !== 'manual') setIsBacktestBatchRunning(false);
    }
  }, [isBacktestBatchRunning, language]);

  const handleBacktestCandidate = useCallback((candidate: ScannerCandidate) => {
    void runScannerBacktests('manual', [candidate]);
  }, [runScannerBacktests]);

  const handleBacktestBatch = useCallback((source: ScannerBacktestSource) => {
    if (source === 'official_selected') {
      void runScannerBacktests(source, sortedCandidates);
    } else if (source === 'preview_selected') {
      void runScannerBacktests(source, previewSelectedDiagnostics.map(diagnosticToCandidate));
    } else if (source === 'top_5') {
      void runScannerBacktests(source, topFiveDiagnostics.map(diagnosticToCandidate));
    } else if (source === 'current_filter') {
      void runScannerBacktests(source, decisionSortedDiagnosticCandidates.map(diagnosticToCandidate));
    }
  }, [decisionSortedDiagnosticCandidates, previewSelectedDiagnostics, runScannerBacktests, sortedCandidates, topFiveDiagnostics]);

  useEffect(() => {
    if (!hasCandidateDiagnostics && candidateFilter !== 'selected') {
      setCandidateFilter('selected');
    }
  }, [candidateFilter, hasCandidateDiagnostics]);

  useEffect(() => {
    if (!hasCandidateDiagnostics) {
      setInspectorSymbol(null);
      return;
    }
    const current = getSelectedDiagnosticCandidate(diagnosticCandidates, sortedCandidates, inspectorSymbol);
    if (current && (!inspectorSymbol || normalizeCandidateSymbol(current.symbol) !== normalizeCandidateSymbol(inspectorSymbol))) {
      setInspectorSymbol(current.symbol);
    }
  }, [diagnosticCandidates, hasCandidateDiagnostics, inspectorSymbol, sortedCandidates]);

  useEffect(() => {
    let isMounted = true;
    const previousRunId = findPreviousComparableRunId(runDetail, historyItems);
    if (!runDetail || !previousRunId) {
      setPreviousRunDetail(null);
      return () => {
        isMounted = false;
      };
    }
    scannerApi.getRun(previousRunId)
      .then((response) => {
        if (!isMounted) return;
        setPreviousRunDetail(response);
      })
      .catch(() => {
        if (!isMounted) return;
        setPreviousRunDetail(null);
      });
    return () => {
      isMounted = false;
    };
  }, [historyItems, runDetail]);

  const historyCards = useMemo(() => historyItems.map((item) => {
    const fallbackTitle = item.market === 'us'
      ? t('scanner.currentRunFallbackUs')
      : item.market === 'hk'
        ? t('scanner.currentRunFallbackHk')
        : t('scanner.currentRunFallbackCn');
    const matchedSymbols = dedupeTickerSymbols(item.topSymbols);
    return {
      ...item,
      historyHeadline: formatHistoryHeadline(item.headline, item.topSymbols, fallbackTitle),
      matchedSymbols: matchedSymbols.slice(0, 10),
      overflowSymbolCount: Math.max(0, matchedSymbols.length - 10),
    };
  }), [historyItems, t]);
  const emptyStateTitle = language === 'en' ? 'No matching scanner results' : '当前无匹配的扫描结果';
  const emptyStateBody = language === 'en' ? 'Adjust the filters on the left or try again later' : '请调整左侧参数或稍后再试';
  const backtestUnavailableLabel = language === 'en'
    ? 'Backtest handoff requires a candidate symbol.'
    : '回测交接需要候选标的代码。';
  const primarySelectedCandidate = sortedCandidates[0] || (inspectorCandidate ? diagnosticToCandidate(inspectorCandidate) : null);
  const singleSelectedSymbol = sortedCandidates.length === 1 ? normalizeCandidateSymbol(sortedCandidates[0]?.symbol) : null;
  const primaryBacktestItem = primarySelectedCandidate ? backtestItemsBySymbol[normalizeCandidateSymbol(primarySelectedCandidate.symbol) || ''] : undefined;
  const primaryWatchlistIdentity = primarySelectedCandidate ? getWatchlistIdentity(runDetail?.market || market, primarySelectedCandidate.symbol) : '';
  const isPrimaryTracked = Boolean(primaryWatchlistIdentity && trackedWatchlistIdentitySet.has(primaryWatchlistIdentity));
  const isPrimaryTrackPending = pendingWatchlistIdentity === primaryWatchlistIdentity;
  const handleAnalyzeCandidate = useCallback(async (candidate: ScannerCandidate) => {
    setPendingAnalyzeSymbol(candidate.symbol);
    setActionNotice(null);
    try {
      await analysisApi.analyzeAsync({
        stockCode: candidate.symbol,
        reportType: 'detailed',
        stockName: candidate.name,
        originalQuery: candidate.symbol,
        selectionSource: 'manual',
      });
      navigate(buildLocalizedPath('/', language));
    } catch (error) {
      if (error instanceof DuplicateTaskError) {
        navigate(buildLocalizedPath('/', language));
        return;
      }
      const parsedError = getParsedApiError(error);
      setActionNotice({
        tone: 'danger',
        message: parsedError.message,
      });
    } finally {
      setPendingAnalyzeSymbol((current) => (current === candidate.symbol ? null : current));
    }
  }, [language, navigate]);

  const handleCopyText = useCallback(async (text: string, nextCopiedKey: string) => {
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error(language === 'en' ? 'Clipboard is not available in this browser.' : '当前浏览器不支持剪贴板。');
      }
      await navigator.clipboard.writeText(text);
      setCopiedKey(nextCopiedKey);
      setActionNotice(null);
    } catch (error) {
      setActionNotice({
        tone: 'danger',
        message: error instanceof Error ? error.message : (language === 'en' ? 'Copy failed.' : '复制失败。'),
      });
    }
  }, [language]);

  const handleExportRows = useCallback((rows: ScannerExportRow[], filename: string) => {
    try {
      downloadScannerCsv(filename, buildScannerCsv(rows));
      setActionNotice(null);
    } catch (error) {
      setActionNotice({
        tone: 'danger',
        message: error instanceof Error ? error.message : (language === 'en' ? 'Export failed.' : '导出失败。'),
      });
    }
  }, [language]);

  const handleTrackCandidate = useCallback(async (candidate: ScannerCandidate) => {
    const candidateMarket = normalizeScannerMarket(runDetail?.market || market);
    if (!candidateMarket) return;
    const candidateIdentity = getWatchlistIdentity(candidateMarket, candidate.symbol);
    if (!candidateIdentity || trackedWatchlistIdentitySet.has(candidateIdentity)) {
      return;
    }

    setPendingWatchlistIdentity(candidateIdentity);
    setActionNotice(null);
    try {
      const savedItem = await watchlistApi.addWatchlistItem({
        symbol: candidate.symbol,
        market: candidateMarket.toLowerCase(),
        name: candidate.companyName || candidate.name,
        source: 'scanner',
        scannerRunId: runDetail?.id,
        scannerRank: candidate.rank,
        scannerScore: candidate.score,
        themeId: runDetail?.themeId || undefined,
        universeType: runDetail?.universeType || undefined,
        notes: buildWatchlistNotes(candidate, runDetail, language) || undefined,
      });
      setWatchlistItems((current) => {
        const nextIdentity = getWatchlistIdentity(savedItem.market, savedItem.symbol);
        const remaining = current.filter((item) => getWatchlistIdentity(item.market, item.symbol) !== nextIdentity);
        return [savedItem, ...remaining];
      });
      setWatchlistAuthBlocked(false);
      setActionNotice({
        tone: 'success',
        message: language === 'en' ? 'Saved to your watchlist.' : '已加入观察名单。',
      });
    } catch (error) {
      const parsedError = getParsedApiError(error);
      if (parsedError.isAuthError || parsedError.status === 401 || parsedError.status === 403 || parsedError.status === 405) {
        setWatchlistAuthBlocked(true);
        setActionNotice({
          tone: 'warning',
          message: language === 'en'
            ? 'Sign in to save candidates to your watchlist.'
            : '请登录后再保存候选到你的观察名单。',
        });
      } else {
        setActionNotice({
          tone: 'danger',
          message: parsedError.message,
        });
      }
    } finally {
      setPendingWatchlistIdentity((current) => (current === candidateIdentity ? null : current));
    }
  }, [language, market, runDetail, trackedWatchlistIdentitySet]);

  const handleBatchTrackCandidates = useCallback(async (batchKey: string, candidates: ScannerCandidate[]) => {
    const candidateMarket = normalizeScannerMarket(runDetail?.market || market);
    if (!candidateMarket || !candidates.length) return;
    const uniqueCandidates = candidates.reduce<ScannerCandidate[]>((items, candidate) => {
      const identity = getWatchlistIdentity(candidateMarket, candidate.symbol);
      if (!identity || items.some((item) => getWatchlistIdentity(candidateMarket, item.symbol) === identity)) return items;
      return [...items, candidate];
    }, []);
    let alreadyExists = 0;
    let added = 0;
    const toAdd = uniqueCandidates.filter((candidate) => {
      const identity = getWatchlistIdentity(candidateMarket, candidate.symbol);
      if (trackedWatchlistIdentitySet.has(identity)) {
        alreadyExists += 1;
        return false;
      }
      return true;
    });
    setPendingBatchWatchlistAction(batchKey);
    setActionNotice(null);
    try {
      const savedItems: WatchlistItem[] = [];
      for (const candidate of toAdd) {
        const savedItem = await watchlistApi.addWatchlistItem({
          symbol: candidate.symbol,
          market: candidateMarket.toLowerCase(),
          name: candidate.companyName || candidate.name,
          source: 'scanner',
          scannerRunId: runDetail?.id,
          scannerRank: candidate.rank,
          scannerScore: candidate.score,
          themeId: runDetail?.themeId || undefined,
          universeType: runDetail?.universeType || undefined,
          notes: buildWatchlistNotes(candidate, runDetail, language) || undefined,
        });
        savedItems.push(savedItem);
        added += 1;
      }
      if (savedItems.length) {
        setWatchlistItems((current) => {
          const savedIdentities = new Set(savedItems.map((item) => getWatchlistIdentity(item.market, item.symbol)));
          return [...savedItems, ...current.filter((item) => !savedIdentities.has(getWatchlistIdentity(item.market, item.symbol)))];
        });
      }
      setWatchlistAuthBlocked(false);
      setActionNotice({
        tone: 'success',
        message: language === 'en'
          ? `Added ${added} · already existed ${alreadyExists}`
          : `已加入 ${added} 个 · 已存在 ${alreadyExists} 个`,
      });
    } catch (error) {
      const parsedError = getParsedApiError(error);
      if (parsedError.isAuthError || parsedError.status === 401 || parsedError.status === 403 || parsedError.status === 405) {
        setWatchlistAuthBlocked(true);
        setActionNotice({
          tone: 'warning',
          message: language === 'en'
            ? 'Sign in to save candidates to your watchlist.'
            : '请登录后再保存候选到你的观察名单。',
        });
      } else {
        setActionNotice({ tone: 'danger', message: parsedError.message });
      }
    } finally {
      setPendingBatchWatchlistAction((current) => (current === batchKey ? null : current));
    }
  }, [language, market, runDetail, trackedWatchlistIdentitySet]);

  return (
    <>
      <div
        ref={surfaceRef}
        data-testid="user-scanner-bento-page"
        data-bento-surface="true"
        aria-hidden={shouldGuardA11y && !isSafariReady ? true : undefined}
        aria-live={shouldGuardA11y ? (isSafariReady ? 'polite' : 'off') : undefined}
	        className={getSafariReadySurfaceClassName(
	          isSafariReady,
	          'bento-surface-root flex w-full flex-1 flex-col min-w-0 bg-transparent text-foreground',
	        )}
	      >
	        <main
	          data-testid="user-scanner-workspace"
	          className="w-full flex-1 flex flex-col min-w-0"
	        >
          {pageError ? <ApiErrorAlert error={pageError} /> : null}
          {actionNotice ? (
            <div
              role={actionNotice.tone === 'danger' ? 'alert' : 'status'}
              className={`rounded-2xl border px-4 py-3 text-sm ${
                actionNotice.tone === 'danger'
                  ? 'border-red-400/20 bg-red-400/10 text-red-100'
                  : actionNotice.tone === 'warning'
                    ? 'border-amber-400/20 bg-amber-400/10 text-amber-100'
                    : 'border-emerald-400/20 bg-emerald-400/10 text-emerald-100'
              }`}
            >
              {actionNotice.message}
            </div>
          ) : null}

	          <div className="flex w-full flex-1 min-w-0 flex-col gap-3 xl:flex-row xl:items-start">
	            <section
	              data-testid="scanner-sidebar"
	              className="flex w-full shrink-0 flex-col rounded-[16px] border border-white/5 bg-white/[0.015] p-3 xl:sticky xl:top-[calc(var(--shell-masthead-height)+1.25rem)] xl:w-[268px] xl:self-start 2xl:w-[288px]"
	            >
	              <SectionShell
	                className="flex flex-col rounded-[24px] p-0 bg-transparent shadow-none"
	                contentClassName="flex flex-col space-y-0"
	              >
	                <div
	                  data-testid="scanner-sidebar-scroll-region"
	                  className="flex flex-col gap-2.5"
	                >
                    <div className="flex items-center justify-between gap-2 border-b border-white/5 pb-1">
                      <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-white/40">
                        {language === 'en' ? 'Basic scan' : '基础扫描'}
                      </span>
                    </div>
	                  <PillTagGroup label={t('scanner.marketLabel')} value={market} onChange={(next) => handleMarketChange(next as 'cn' | 'us' | 'hk')} options={[{ value: 'cn', label: t('scanner.marketCn') }, { value: 'us', label: t('scanner.marketUs') }, { value: 'hk', label: t('scanner.marketHk') }]} variant="market" testId="scanner-market-toggle" />
	                  <PillTagGroup label={t('scanner.profileLabel')} value={profile} onChange={setProfile} options={profileOptions} />
	                  <PillTagGroup label={t('scanner.shortlistLabel')} value={shortlistSize} onChange={setShortlistSize} options={[{ value: '5', label: language === 'en' ? 'Top 5' : '前 5' }, { value: '8', label: language === 'en' ? 'Top 8' : '前 8' }, { value: '10', label: language === 'en' ? 'Top 10' : '前 10' }]} />
	                  <AdvancedDisclosure
	                    testId="scanner-advanced-controls"
	                    title={language === 'en' ? 'Advanced controls' : '高级参数'}
	                    summary={language === 'en' ? 'Candidate size · evaluation depth · scan scope' : '候选上限 · 评估深度 · 扫描范围'}
	                    icon="more"
	                  >
	                  <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-1">
	                    <PillTagGroup label={t('scanner.universeLabel')} value={universeLimit} onChange={setUniverseLimit} options={universeOptions} />
	                    <PillTagGroup label={t('scanner.detailLabel')} value={detailLimit} onChange={setDetailLimit} options={detailOptions} />
	                  </div>
                  <PillTagGroup
                    label={language === 'en' ? 'Scan scope' : '扫描范围'}
                    value={scanScope}
                    onChange={(next) => setScanScope(next as ScanScope)}
                    options={[
                      { value: 'default', label: language === 'en' ? 'Default market universe' : '默认市场池' },
                      { value: 'theme', label: language === 'en' ? 'Theme universe' : '主题标的池' },
                      { value: 'symbols', label: language === 'en' ? 'Custom symbols' : '自定义标的' },
                    ]}
                    testId="scanner-scope-selector"
                  />
                  {scanScope === 'theme' ? (
                    <div className="flex min-w-0 flex-col gap-1.5" data-testid="scanner-theme-control">
                      <span className="text-[10px] uppercase tracking-[0.16em] text-white/40">{language === 'en' ? 'Theme' : '主题'}</span>
                      <div className="select-field__control ui-control-shell group relative min-w-0 w-full max-w-full">
                        <select
                          data-testid="scanner-theme-select"
                          value={themeId}
                          onChange={(event) => setThemeId(event.target.value)}
                          aria-invalid={Boolean(validationErrors.theme)}
                          aria-describedby={validationErrors.theme ? 'scanner-theme-error' : undefined}
                          className="select-surface absolute inset-0 z-10 h-full w-full min-w-0 cursor-pointer rounded-lg opacity-0 outline-none"
                        >
                          <option value="">{language === 'en' ? 'Select a theme' : '选择主题'}</option>
                          {configuredMarketThemes.length ? (
                            <optgroup label={language === 'en' ? 'Ready seed lists' : '可用 seed 主题'}>
                              {configuredMarketThemes.map((theme) => (
                                <option key={theme.id} value={theme.id}>
                                  {getThemeLabel(theme, language)} · {theme.symbols.length}
                                </option>
                              ))}
                            </optgroup>
                          ) : null}
                          {unconfiguredMarketThemes.length ? (
                            <optgroup label={language === 'en' ? 'Unavailable / unconfigured' : '未配置'}>
                              {unconfiguredMarketThemes.map((theme) => (
                                <option key={theme.id} value={theme.id} disabled>
                                  {getThemeLabel(theme, language)} · {language === 'en' ? 'not configured' : '未配置'}
                                </option>
                              ))}
                            </optgroup>
                          ) : null}
                        </select>
                        <div
                          aria-hidden="true"
                          className={`select-field__overlay pointer-events-none flex h-full min-h-[2.25rem] w-full min-w-0 items-center rounded-lg border bg-black/40 px-2.5 py-1.5 text-xs text-white transition-all ${
                            validationErrors.theme
                              ? 'border-rose-500/50 text-rose-100'
                              : 'border-white/8 group-focus-within:border-indigo-400/50'
                          }`}
                        >
                          <span className="select-field__value min-w-0 flex-1 truncate">
                            {selectedTheme
                              ? `${getThemeLabel(selectedTheme, language)} · ${selectedTheme.symbols.length}`
                              : (language === 'en' ? 'Select a theme' : '选择主题')}
                          </span>
                          <ChevronDown className="select-field__icon ui-control-icon ml-2 h-4 w-4 shrink-0 text-white/40" aria-hidden="true" />
                        </div>
                      </div>
                      {selectedTheme && !selectedTheme.symbols.length ? (
                        <p className="text-[11px] leading-relaxed text-amber-100/72">
                          {language === 'en' ? 'This theme is not configured yet.' : '该主题尚未配置成分股。'}
                        </p>
                      ) : null}
                      {validationErrors.theme ? (
                        <p id="scanner-theme-error" role="alert" className="text-[11px] leading-relaxed text-rose-100/82">
                          {validationErrors.theme}
                        </p>
                      ) : null}
                      <div className="mt-2 flex flex-col gap-2 rounded-xl border border-white/5 bg-white/[0.02] p-2.5" data-testid="scanner-ai-theme-builder">
                        <div className="flex items-center gap-2 text-[11px] font-medium text-white/70">
                          <Sparkles className="h-3.5 w-3.5 text-indigo-200/80" aria-hidden="true" />
                          <span>{language === 'en' ? 'AI custom theme' : 'AI 自定义主题'}</span>
                        </div>
                        <input
                          data-testid="scanner-ai-theme-label-input"
                          value={customThemeLabel}
                          onChange={(event) => setCustomThemeLabel(event.target.value)}
                          aria-invalid={Boolean(validationErrors.customThemeLabel)}
                          aria-describedby={validationErrors.customThemeLabel ? 'scanner-ai-theme-label-error' : undefined}
                          maxLength={80}
                          placeholder={language === 'en' ? 'White House Stocks' : 'White House Stocks'}
                          className="w-full rounded-lg border border-white/8 bg-black/40 px-2.5 py-1.5 text-xs text-white outline-none placeholder:text-white/20 focus:border-indigo-400/50"
                        />
                        {validationErrors.customThemeLabel ? (
                          <p id="scanner-ai-theme-label-error" role="alert" className="text-[11px] leading-relaxed text-rose-100/82">
                            {validationErrors.customThemeLabel}
                          </p>
                        ) : null}
                        <textarea
                          data-testid="scanner-ai-theme-prompt-input"
                          value={customThemePrompt}
                          onChange={(event) => setCustomThemePrompt(event.target.value)}
                          aria-invalid={Boolean(validationErrors.customThemePrompt)}
                          aria-describedby={validationErrors.customThemePrompt ? 'scanner-ai-theme-prompt-error' : undefined}
                          maxLength={600}
                          rows={3}
                          placeholder={language === 'en' ? 'Stocks associated with White House policy, federal contracts, and government decisions.' : '例如：与白宫政策、联邦合同和政府决策相关的股票。'}
                          className="w-full resize-none rounded-lg border border-white/8 bg-black/40 px-2.5 py-1.5 text-xs text-white outline-none placeholder:text-white/20 focus:border-indigo-400/50"
                        />
                        {validationErrors.customThemePrompt ? (
                          <p id="scanner-ai-theme-prompt-error" role="alert" className="text-[11px] leading-relaxed text-rose-100/82">
                            {validationErrors.customThemePrompt}
                          </p>
                        ) : null}
                        <input
                          data-testid="scanner-ai-theme-manual-symbols-input"
                          value={customThemeManualSymbols}
                          onChange={(event) => setCustomThemeManualSymbols(event.target.value)}
                          aria-invalid={Boolean(validationErrors.customThemeManualSymbols)}
                          aria-describedby={validationErrors.customThemeManualSymbols ? 'scanner-ai-theme-manual-symbols-error' : undefined}
                          placeholder={language === 'en' ? 'Optional: add symbols, e.g. NVDA PLTR' : '可选：手动补充代码，例如 NVDA PLTR'}
                          className="w-full rounded-lg border border-white/8 bg-black/40 px-2.5 py-1.5 text-xs text-white outline-none placeholder:text-white/20 focus:border-indigo-400/50"
                        />
                        {validationErrors.customThemeManualSymbols ? (
                          <p id="scanner-ai-theme-manual-symbols-error" role="alert" className="text-[11px] leading-relaxed text-rose-100/82">
                            {validationErrors.customThemeManualSymbols}
                          </p>
                        ) : null}
                        <button
                          ref={generateThemeButton.ref}
                          type="button"
                          disabled={generateThemeDisabled}
                          onPointerUp={generateThemeButton.onPointerUp}
                          onClick={generateThemeButton.onClick}
                          className="inline-flex h-8 shrink-0 items-center justify-center gap-2 rounded-lg border border-indigo-300/20 bg-indigo-300/10 px-3 text-xs font-medium text-indigo-100 transition hover:border-indigo-200/35 hover:bg-indigo-300/15 disabled:cursor-not-allowed disabled:opacity-45"
                        >
                          <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
                          <span>{isGeneratingTheme ? (language === 'en' ? 'Generating...' : '生成中...') : (language === 'en' ? 'Generate theme' : '生成主题')}</span>
                        </button>
                        {themeSuggestions.length ? (
                          <div className="flex flex-col gap-1.5" data-testid="scanner-ai-theme-suggestions">
                            {themeSuggestions.slice(0, 6).map((suggestion) => (
                              <div key={suggestion.symbol} className="shrink-0 rounded-lg border border-white/5 bg-black/20 px-2.5 py-1.5">
                                <div className="flex items-center justify-between gap-2 text-[11px] text-white/75">
                                  <span className="font-semibold text-white">{suggestion.symbol}</span>
                                  <span>{Math.round(suggestion.confidence * 100)}%</span>
                                </div>
                                <p className="mt-1 text-[10px] leading-snug text-white/45">{suggestion.reason}</p>
                              </div>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    </div>
                  ) : null}
	                  {scanScope === 'symbols' ? (
                    <div className="flex flex-col gap-1.5" data-testid="scanner-custom-symbols-control">
                      <span className="text-[10px] uppercase tracking-[0.16em] text-white/40">{language === 'en' ? 'Symbols' : '代码'}</span>
                      <textarea
                        data-testid="scanner-custom-symbols-input"
                        value={customSymbols}
                        onChange={(event) => setCustomSymbols(event.target.value)}
                        aria-invalid={Boolean(validationErrors.customSymbols)}
                        aria-describedby={validationErrors.customSymbols ? 'scanner-custom-symbols-error' : undefined}
                        rows={3}
                        placeholder={language === 'en' ? 'MARA RIOT CLSK' : 'MARA RIOT CLSK'}
                        className="w-full resize-none rounded-lg border border-white/8 bg-black/40 px-2.5 py-1.5 text-xs text-white outline-none placeholder:text-white/20 focus:border-indigo-400/50"
                      />
                      <p className="text-[11px] text-white/45">
                        {language === 'en' ? `Parsed ${parsedCustomSymbols.length}` : `已解析 ${parsedCustomSymbols.length}`}
                      </p>
                      {validationErrors.customSymbols ? (
                        <p id="scanner-custom-symbols-error" role="alert" className="text-[11px] leading-relaxed text-rose-100/82">
                          {validationErrors.customSymbols}
                        </p>
                      ) : null}
	                    </div>
	                  ) : null}
	                  </AdvancedDisclosure>
                  {validationErrors.run ? (
                    <p role="alert" className="text-[11px] leading-relaxed text-rose-100/82">
                      {validationErrors.run}
                    </p>
                  ) : null}
                  <div className="mt-auto flex shrink-0 flex-col gap-2 pt-4 pb-4">
                    <button
                      ref={runScannerButton.ref}
                      type="button"
                      onClick={runScannerButton.onClick}
                      onPointerUp={runScannerButton.onPointerUp}
                      disabled={runDisabled}
                      aria-busy={isRunning}
                      data-testid="scanner-run-button"
                      className="group flex w-full items-center justify-center gap-2 rounded-xl border border-indigo-500/30 bg-indigo-500/10 px-5 py-3 text-sm font-bold text-indigo-300 transition-all hover:border-indigo-500/50 hover:bg-indigo-500/20 hover:shadow-[0_0_20px_rgba(99,102,241,0.16)] active:scale-95 disabled:pointer-events-none disabled:opacity-60 disabled:shadow-none disabled:transform-none xl:sticky xl:bottom-0"
                    >
                      <Play className="h-4 w-4 group-hover:animate-pulse" />
                      <span>{isRunning ? t('scanner.running') : t('scanner.run')}</span>
                    </button>
                  </div>
                </div>
              </SectionShell>
            </section>

	            <section
	              data-testid="scanner-results-pane"
	              className="flex min-h-[520px] flex-1 min-w-0 flex-col rounded-[16px] border border-white/5 bg-white/[0.01]"
	            >
              <div data-testid="user-scanner-bento-hero" className="flex shrink-0 flex-col gap-2 border-b border-white/5 px-3 py-2.5">
                <div className="flex flex-col justify-between gap-3 lg:flex-row lg:items-center">
                  <div className="flex min-w-0 flex-wrap items-center gap-2 text-xs text-white/45">
                    <span className="font-semibold text-white/78">{language === 'en' ? 'Results' : '扫描结果'}</span>
                    <span className="rounded-full border border-white/8 bg-white/[0.04] px-2 py-0.5 text-white/60">
                      {language === 'en' ? `${shortlistCount} selected` : `入选 ${shortlistCount}`}
                    </span>
                    {generatedAt ? <span>{formatTimestamp(generatedAt, language)}</span> : null}
                    {runDetail ? <span className="truncate">{`${runDetail.market.toUpperCase()} · ${runDetail.profileLabel || runDetail.profile}`}</span> : null}
                  </div>
                  <div className="flex min-w-0 flex-col gap-2 sm:items-end">
                    {runDetail && primarySelectedCandidate ? (
                      <div className="grid w-full min-w-0 grid-cols-1 gap-1.5 sm:w-auto sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto_auto]">
	                        <div
	                          data-testid="scanner-primary-actions"
	                          className="grid min-w-0 grid-cols-1 gap-1.5 sm:col-span-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto_auto]"
	                        >
                          <ActionButton
                            label={singleSelectedSymbol
                              ? (language === 'en' ? `Analyze ${singleSelectedSymbol}` : `分析 ${singleSelectedSymbol}`)
                              : (language === 'en' ? 'Analyze selected' : '分析入选')}
                            icon={<Play className="h-3.5 w-3.5" />}
                            onClick={() => void handleAnalyzeCandidate(primarySelectedCandidate)}
                            disabled={pendingAnalyzeSymbol === primarySelectedCandidate.symbol}
                            variant="primary"
                          />
                          <ActionButton
                            label={primaryBacktestItem?.status === 'running' || primaryBacktestItem?.status === 'queued'
                              ? (language === 'en' ? 'Running' : '运行中')
                              : singleSelectedSymbol
                              ? (language === 'en' ? `Backtest ${singleSelectedSymbol}` : `回测 ${singleSelectedSymbol}`)
                              : (language === 'en' ? 'Backtest selected' : '回测入选')}
                            icon={<TestTubeDiagonal className="h-3.5 w-3.5" />}
                            onClick={() => void handleBacktestCandidate(primarySelectedCandidate)}
                            disabled={!normalizeCandidateSymbol(primarySelectedCandidate.symbol) || primaryBacktestItem?.status === 'running' || primaryBacktestItem?.status === 'queued'}
                            title={!normalizeCandidateSymbol(primarySelectedCandidate.symbol) ? backtestUnavailableLabel : undefined}
                          />
	                          <ActionButton
	                            label={language === 'en' ? 'Save to watchlist' : '加入观察'}
                            icon={isPrimaryTracked ? <BookmarkCheck className="h-3.5 w-3.5" /> : <BookmarkPlus className="h-3.5 w-3.5" />}
                            onClick={() => {
                              if (sortedCandidates.length > 1) {
                                void handleBatchTrackCandidates('official', sortedCandidates);
                                return;
                              }
                              void handleTrackCandidate(primarySelectedCandidate);
                            }}
                            disabled={watchlistAuthBlocked || isPrimaryTracked || isPrimaryTrackPending || Boolean(pendingBatchWatchlistAction)}
	                            title={getWatchlistActionTitle(isPrimaryTracked, watchlistAuthBlocked, language)}
	                          />
	                          <div data-testid="scanner-more-actions" className="relative min-w-0">
	                            <button
	                              type="button"
	                              aria-expanded={isMoreActionsOpen}
	                              aria-label={language === 'en' ? 'More scanner actions' : '更多扫描操作'}
	                              onClick={() => setIsMoreActionsOpen((current) => !current)}
	                              className="inline-flex h-full w-full min-w-0 items-center justify-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-2.5 py-1 text-xs text-white/70 hover:bg-white/10 hover:text-white"
	                            >
	                              <MoreHorizontal className="h-3.5 w-3.5" aria-hidden="true" />
	                              <span>{language === 'en' ? 'More' : '更多'}</span>
	                            </button>
	                            {isMoreActionsOpen ? (
	                          <div data-testid="scanner-more-actions-panel" className="mt-2 grid min-w-[220px] gap-1.5 rounded-lg border border-white/5 bg-black/90 p-2 backdrop-blur-md">
	                            <ActionButton
	                              label={language === 'en' ? 'Export CSV' : '导出 CSV'}
                              icon={<Download className="h-3.5 w-3.5" />}
                              onClick={() => handleExportRows(
                                sortedCandidates.map((candidate) => buildScannerExportRow(candidate, runDetail, language)),
                                buildScannerExportFilename(runDetail),
                              )}
                              disabled={!sortedCandidates.length}
                            />
                            <ActionButton
                              label={language === 'en' ? 'Copy all symbols' : '复制全部代码'}
                              icon={<Copy className="h-3.5 w-3.5" />}
                              onClick={() => void handleCopyText(sortedCandidates.map((candidate) => candidate.symbol).join(', '), 'all-symbols')}
                              disabled={!sortedCandidates.length}
                            />
                            <ActionButton
                              label={language === 'en' ? 'Copy top 5' : '复制前 5'}
                              icon={<Copy className="h-3.5 w-3.5" />}
                              onClick={() => void handleCopyText(sortedCandidates.slice(0, 5).map((candidate) => candidate.symbol).join(', '), 'top-5-symbols')}
                              disabled={!sortedCandidates.length}
                            />
	                            <button
	                              ref={openHistoryDrawerButton.ref}
	                              type="button"
                              data-testid="user-scanner-bento-drawer-trigger"
	                              onClick={openHistoryDrawerButton.onClick}
                              onPointerUp={openHistoryDrawerButton.onPointerUp}
                              className="inline-flex min-w-0 items-center justify-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-2.5 py-1 text-xs text-white/70 transition-colors hover:bg-white/10 hover:text-white"
	                            >
	                              <History className="h-3.5 w-3.5" aria-hidden="true" />
	                              <span>{language === 'en' ? 'Historical replay' : '历史扫描回放'}</span>
	                            </button>
	                            <ActionButton
	                              label={language === 'en' ? 'Add official selected' : '加入全部入选'}
	                              icon={<BookmarkPlus className="h-3.5 w-3.5" />}
	                              onClick={() => void handleBatchTrackCandidates('official', sortedCandidates)}
	                              disabled={Boolean(pendingBatchWatchlistAction) || watchlistAuthBlocked || !sortedCandidates.length}
	                            />
	                            <ActionButton
	                              label={language === 'en' ? 'Add preview selected' : '加入预览入选'}
	                              icon={<BookmarkPlus className="h-3.5 w-3.5" />}
	                              onClick={() => void handleBatchTrackCandidates('preview', previewSelectedDiagnostics.map(diagnosticToCandidate))}
	                              disabled={Boolean(pendingBatchWatchlistAction) || watchlistAuthBlocked || !previewSelectedDiagnostics.length}
	                            />
	                            <ActionButton
	                              label={language === 'en' ? 'Add top 5' : '加入前 5 名'}
	                              icon={<BookmarkPlus className="h-3.5 w-3.5" />}
	                              onClick={() => void handleBatchTrackCandidates('top5', sortDiagnosticsForDecision(diagnosticCandidates, previewThreshold).slice(0, 5).map(diagnosticToCandidate))}
	                              disabled={Boolean(pendingBatchWatchlistAction) || watchlistAuthBlocked || !diagnosticCandidates.length}
	                            />
	                            <ActionButton
	                              label={language === 'en' ? 'Add filtered' : '加入当前筛选'}
	                              icon={<BookmarkPlus className="h-3.5 w-3.5" />}
	                              onClick={() => void handleBatchTrackCandidates('filtered', decisionSortedDiagnosticCandidates.map(diagnosticToCandidate))}
	                              disabled={Boolean(pendingBatchWatchlistAction) || watchlistAuthBlocked || !decisionSortedDiagnosticCandidates.length}
	                            />
	                            <ActionButton
	                              label={language === 'en' ? 'Batch backtest' : '批量回测'}
	                              icon={<LineChart className="h-3.5 w-3.5" />}
	                              onClick={() => handleBacktestBatch('official_selected')}
	                              disabled={isBacktestBatchRunning || backtestCounts.official_selected === 0}
	                            />
	                          </div>
	                            ) : null}
	                          </div>
	                        </div>
	                      </div>
                    ) : (
                      <button
                        ref={openHistoryDrawerButton.ref}
                        type="button"
                        data-testid="user-scanner-bento-drawer-trigger"
                        onClick={openHistoryDrawerButton.onClick}
                        onPointerUp={openHistoryDrawerButton.onPointerUp}
                        className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.05] px-2.5 py-1 text-xs text-white/80 transition-colors hover:bg-white/[0.1]"
                      >
	                        <History className="h-4 w-4" aria-hidden="true" />
                        <span>{language === 'en' ? 'Historical replay' : '历史扫描回放'}</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {runDetail ? (
                <div className="shrink-0 border-b border-white/5 px-3 py-2" data-testid="scanner-diagnostic-summary">
                  <div data-testid="scanner-summary-counters" className="flex flex-wrap items-center gap-1.5 rounded-xl border border-white/5 bg-white/[0.02] px-2.5 py-2 backdrop-blur-md">
                    {[
                      [language === 'en' ? 'UNIVERSE' : '候选范围', runDetail.summary?.universeCount ?? runDetail.acceptedSymbolsCount ?? runDetail.universeSize],
                      [language === 'en' ? 'EVALUATED' : '已评估', runDetail.summary?.evaluatedCount ?? runDetail.evaluatedSize],
                      [language === 'en' ? 'SELECTED' : '入选', runDetail.summary?.selectedCount ?? shortlistCount],
                      [language === 'en' ? 'REJECTED' : '淘汰', runDetail.summary?.rejectedCount ?? 0],
                      [language === 'en' ? 'DATA FAILED' : '数据失败', runDetail.summary?.dataFailedCount ?? 0],
                      [language === 'en' ? 'SKIPPED' : '跳过', runDetail.summary?.skippedCount ?? 0],
                    ].map(([label, value]) => (
                      <span key={label} className="inline-flex items-baseline gap-1 rounded-lg border border-white/5 bg-black/20 px-2 py-1">
                        <span className="text-[10px] font-bold uppercase tracking-widest text-white/40">{label}</span>
                        <span className="font-mono text-xs text-white/78">{value}</span>
                      </span>
                    ))}
                  </div>
                  {decisionSummary ? (
                    <div
                      data-testid="scanner-decision-summary"
                      className="mt-2 rounded-xl border border-white/5 bg-white/[0.02] px-2.5 py-2 text-xs backdrop-blur-md"
                    >
                      <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-white/78">
                        <span className="font-medium">{decisionSummary.headline}</span>
                        <span className="font-mono text-white/72">{decisionSummary.best}</span>
                      </div>
                      <p className="mt-1 min-w-0 truncate text-[11px] text-white/46" title={`${decisionSummary.reason} · ${decisionSummary.data}`}>
                        {[decisionSummary.reason, decisionSummary.data].join(' · ')}
                      </p>
                      <p className="mt-1 min-w-0 truncate text-[11px] text-white/34">
                        {[
                          comparisonState.previousRun && comparisonState.chips.length
                            ? (language === 'en' ? 'candidate pool changed this run' : '本次发生候选池交换')
                            : null,
                          runDetail.summary?.limitedByResultCap
                            ? (language === 'en' ? 'result cap active' : '结果上限生效')
                            : null,
                          formatProviderDiagnostics(getRunProviderDiagnostics(runDetail), language),
                        ].filter(Boolean).join(' · ')}
                      </p>
                    </div>
                  ) : null}
                  {hasCandidateDiagnostics ? (
                    <div
                      data-testid="scanner-strategy-preview"
                      className="mt-2 rounded-xl border border-white/5 bg-white/[0.015] px-2.5 py-2 text-xs"
                    >
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-white/40">
                          <LineChart className="h-3.5 w-3.5" aria-hidden="true" />
                          {language === 'en' ? 'Threshold preview' : '阈值预览'}
                        </span>
                        {[40, 50, 60].map((threshold) => (
                          <button
                            key={threshold}
                            type="button"
                            aria-pressed={previewThreshold === threshold}
                            onClick={() => setPreviewThreshold(threshold)}
                            className={`rounded-md border px-2 py-0.5 font-mono text-[11px] ${previewThreshold === threshold ? 'border-blue-400/30 bg-blue-400/12 text-blue-100' : 'border-white/10 bg-white/5 text-white/58 hover:bg-white/10'}`}
                          >
                            {threshold}
                          </button>
                        ))}
                        <span className="inline-flex items-baseline gap-1 rounded-md border border-white/8 bg-black/20 px-2 py-0.5">
                          <span className="text-white/40">{language === 'en' ? 'Official ' : '官方 '}</span>
                          <span className="font-mono text-white/82">{runDetail.summary?.selectedCount ?? officialSelectedDiagnostics.length}</span>
                        </span>
                        <span className="inline-flex items-baseline gap-1 rounded-md border border-blue-400/20 bg-blue-400/10 px-2 py-0.5">
                          <span className="text-blue-100/70">{language === 'en' ? 'Preview ' : '预览 '}</span>
                          <span className="font-mono text-blue-100">{previewSelectedDiagnostics.length}</span>
                        </span>
                        <span className="font-mono text-[11px] text-white/62">
                          {`${previewSelectedDiagnostics.length - (runDetail.summary?.selectedCount ?? officialSelectedDiagnostics.length) >= 0 ? '+' : ''}${previewSelectedDiagnostics.length - (runDetail.summary?.selectedCount ?? officialSelectedDiagnostics.length)}`}
                        </span>
                      </div>
                    </div>
                  ) : null}
                  {rejectionBuckets.length || hasRunDiagnosticsContent(runDetail) ? (
                    <div className="mt-2 rounded-xl border border-white/5 bg-white/[0.02] px-2.5 py-2 text-xs backdrop-blur-md">
                      <div data-testid="scanner-diagnostics-summary" className="flex min-w-0 flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                        <p className="min-w-0 truncate text-white/64">
                          {language === 'en'
                            ? `Diagnostic summary: evaluated ${runDetail.summary?.evaluatedCount ?? runDetail.evaluatedSize}, selected ${runDetail.summary?.selectedCount ?? shortlistCount}, main rejection ${rejectionBuckets[0]?.label || 'n/a'}`
                            : `诊断摘要：本次评估 ${runDetail.summary?.evaluatedCount ?? runDetail.evaluatedSize}，只入选 ${runDetail.summary?.selectedCount ?? shortlistCount}，主要淘汰原因：${rejectionBuckets[0]?.label || '暂无'}`}
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          <ActionButton
                            label={language === 'en' ? 'View rejection reasons' : '查看淘汰原因'}
                            onClick={() => setIsRejectionSummaryOpen((current) => !current)}
                          />
                          <ActionButton
                            label={language === 'en' ? 'Developer diagnostics' : '开发者诊断'}
                            onClick={() => setIsDeveloperDiagnosticsOpen((current) => !current)}
                          />
                        </div>
                      </div>
                      {isRejectionSummaryOpen && rejectionBuckets.length ? (
                        <div data-testid="scanner-rejection-aggregate" className="mt-2 flex min-w-0 flex-wrap items-center gap-1.5">
                          {rejectionBuckets.map((bucket) => (
                            <button
                              key={bucket.label}
                              type="button"
                              onClick={() => setCandidateFilter(bucket.label === rejectionBucketLabel('data', language) ? 'data_failed' : 'rejected')}
                              className="inline-flex max-w-full items-baseline gap-1 rounded-md border border-white/10 bg-white/5 px-1.5 py-0.5 text-[10px] text-white/62 hover:bg-white/10"
                            >
                              <span className="truncate">{bucket.label}</span>
                              <span className="font-mono text-white/82">{bucket.value}</span>
                            </button>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              ) : null}

              {runDetail && hasCandidateDiagnostics ? (
                <div className="shrink-0 border-b border-white/5 px-3 py-2" data-testid="scanner-candidate-filters">
                  <div className="ui-scroll-x-quiet flex min-w-0 max-w-full gap-1 rounded-lg border border-white/5 bg-black/30 p-0.5" role="group" aria-label={language === 'en' ? 'Candidate diagnostics filter' : '候选诊断过滤'}>
                    {([
                      ['selected', language === 'en' ? 'Selected' : '入选'],
                      ['pool', language === 'en' ? 'Candidate pool' : '候选池'],
                      ['rejected', language === 'en' ? 'Rejected' : '淘汰'],
                      ['data_failed', language === 'en' ? 'Data failed' : '数据失败'],
                      ['all', language === 'en' ? 'All' : '全部'],
                    ] as const).map(([key, label]) => (
                      <button
                        key={key}
                        type="button"
                        onClick={() => setCandidateFilter(key)}
                        className={`inline-flex shrink-0 items-center rounded-md px-2.5 py-1 text-xs ${candidateFilter === key ? 'bg-white/10 text-white' : 'text-white/45 hover:text-white/75'}`}
                      >
                        <span className="ui-truncate block">{label}</span>
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}

              <div className="flex shrink-0 flex-col gap-2 border-b border-white/5 px-3 py-2 lg:flex-row lg:items-center lg:justify-between">
                <div className="ui-scroll-x-quiet flex min-w-0 max-w-full rounded-lg border border-white/5 bg-black/30 p-0.5" role="group" aria-label={language === 'en' ? 'Result view mode' : '结果视图'}>
                  <button
                    type="button"
                    onClick={() => setViewMode('cards')}
                    disabled={!selectedOnlyView}
                    className={`inline-flex min-w-0 shrink-0 items-center gap-2 rounded-md px-2.5 py-1 text-xs ${viewMode === 'cards' && selectedOnlyView ? 'bg-white/10 text-white' : 'text-white/45 hover:text-white/75'} disabled:cursor-not-allowed disabled:opacity-35`}
                  >
                    <LayoutGrid className="h-3.5 w-3.5" />
                    <span className="ui-truncate">{language === 'en' ? 'Card view' : '卡片视图'}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setViewMode('table')}
                    className={`inline-flex min-w-0 shrink-0 items-center gap-2 rounded-md px-2.5 py-1 text-xs ${viewMode === 'table' ? 'bg-white/10 text-white' : 'text-white/45 hover:text-white/75'}`}
                  >
                    <Table2 className="h-3.5 w-3.5" />
                    <span className="ui-truncate">{language === 'en' ? 'Table view' : '表格视图'}</span>
                  </button>
                </div>
                <div className="flex flex-wrap items-center gap-2 text-xs text-white/42">
                  <span>{language === 'en' ? 'Sort by' : '排序'}</span>
                  {([
                    ['score', language === 'en' ? 'scanner score' : '扫描评分'],
                    ['symbol', language === 'en' ? 'symbol' : '代码'],
                    ['target', language === 'en' ? 'target price' : '目标价'],
                    ['risk', language === 'en' ? 'risk/score' : '风险/评分'],
                  ] as const).map(([key, label]) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => handleSortChange(key)}
                      className={`inline-flex items-center gap-1 rounded-lg border px-2 py-0.5 ${sortKey === key ? 'border-white/16 bg-white/[0.08] text-white' : 'border-white/5 bg-white/[0.02] text-white/48 hover:text-white/75'}`}
                    >
                      {label}
                      {sortKey === key ? <ArrowDownUp className="h-3 w-3" /> : null}
                    </button>
                  ))}
                </div>
              </div>

	              <div data-testid="scanner-candidate-scroll-region" className="px-3 py-3">
	                <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(300px,360px)] 2xl:grid-cols-[minmax(0,1fr)_minmax(340px,420px)]">
                  <div className="min-w-0">
                {!selectedOnlyView ? (
                  decisionSortedDiagnosticCandidates.length ? (
                    <div data-testid="scanner-candidate-diagnostics-table" className="space-y-1.5">
                      {decisionSortedDiagnosticCandidates.map((candidate) => {
                        const activeRunDetail = runDetail as ScannerRunDetail;
                        const diagnosticCandidate = diagnosticToCandidate(candidate);
                        const candidateMarket = normalizeScannerMarket(activeRunDetail.market || market);
                        const candidateIdentity = getWatchlistIdentity(candidateMarket, candidate.symbol);
                        const isTracked = Boolean(candidateIdentity && trackedWatchlistIdentitySet.has(candidateIdentity));
                        const isTrackPending = pendingWatchlistIdentity === candidateIdentity;
                        const backtestItem = backtestItemsBySymbol[normalizeCandidateSymbol(candidate.symbol) || ''];
                        const isExpanded = expandedSymbol === candidate.symbol;
                        const metricItems = Object.entries(candidate.metrics || {}).slice(0, 8);
                        const comparison = comparisonState.bySymbol.get(normalizeCandidateSymbol(candidate.symbol) || '');
                        const scoreDelta = formatScoreDelta(comparison?.scoreDelta ?? null);
                        const previewSelected = isPreviewSelected(candidate, previewThreshold);
                        const isPrimaryActionAnalyze = isOfficialSelected(candidate) || previewSelected;
                        const isInspectorActive = normalizeCandidateSymbol(inspectorCandidate?.symbol) === normalizeCandidateSymbol(candidate.symbol);
                        const isMoreOpen = rowMoreSymbol === candidate.symbol;
                        const friendlyReason = formatFriendlyDiagnosticReason(candidate, language);
                        const dataQuality = formatCandidateDataQuality(candidate, language);
                        const providerLabel = formatFriendlyProvider(candidate.provider, language);
                        const isSelectedCandidate = isOfficialSelected(candidate);
                        return (
                          <article
                            key={`diagnostic-${candidate.symbol}`}
                            data-testid={`scanner-candidate-row-${candidate.symbol}`}
                            data-selected={isSelectedCandidate ? 'true' : undefined}
                            onClick={() => {
                              setInspectorSymbol(candidate.symbol);
                              setExpandedSymbol(candidate.symbol);
                            }}
                            className={`rounded-xl border px-3 py-2 text-sm backdrop-blur-md transition-all ${isSelectedCandidate ? 'border-emerald-400/20 bg-emerald-400/[0.045] shadow-[inset_2px_0_0_rgba(52,211,153,0.32)]' : isInspectorActive ? 'border-cyan-400/16 bg-cyan-400/[0.035]' : 'border-white/7 bg-white/[0.018] hover:border-white/12 hover:bg-white/[0.028]'}`}
                          >
                            <div className="grid min-w-0 grid-cols-1 gap-2 md:grid-cols-[minmax(74px,0.55fr)_minmax(56px,0.4fr)_minmax(92px,0.7fr)_minmax(92px,0.6fr)_minmax(0,1.5fr)_minmax(108px,0.75fr)_auto_auto] md:items-center">
                              <div className="min-w-0">
                                <p className={`inline-flex shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-[0.12em] ${previewDecisionClass(candidate, previewThreshold)}`}>
                                  {previewDecisionLabel(candidate, previewThreshold, language)}
                                </p>
                              </div>
                              <div className="font-mono text-[11px] text-white/42">{candidate.rank ? `#${candidate.rank}` : '--'}</div>
                              <div className="min-w-0">
                                <p className={`truncate font-mono text-sm font-semibold ${isSelectedCandidate ? 'text-emerald-50' : 'text-white/86'}`}>{candidate.symbol || '--'}</p>
                                <p className="truncate text-[11px] text-white/32">{candidate.name || candidate.symbol || '--'}</p>
                              </div>
                              <div className={`font-mono text-xs font-semibold ${isSelectedCandidate ? 'text-emerald-100' : 'text-white/78'}`}>
                                {candidate.score == null ? '--' : `${candidate.score}/100`}
                                {scoreDelta ? <span className="ml-1 text-[10px] text-white/42">{scoreDelta}</span> : null}
                              </div>
                              <div className="min-w-0">
                                <p className="truncate text-xs text-white/68" title={getDiagnosticReason(candidate, language)}>
                                  {friendlyReason}
                                </p>
                              </div>
                              <div className="min-w-0">
                                <p className="truncate text-[11px] text-white/58" title={candidate.provider || '--'}>
                                  {dataQuality}
                                </p>
                                <p className="truncate text-[10px] text-white/32">
                                  {providerLabel}
                                </p>
                              </div>
                              <ActionButton
                                label={isPrimaryActionAnalyze ? (language === 'en' ? 'Analyze' : '分析') : (language === 'en' ? 'View' : '查看')}
                                onClick={(event) => {
                                  event.stopPropagation();
                                  setInspectorSymbol(candidate.symbol);
                                  setExpandedSymbol(candidate.symbol);
                                  if (isPrimaryActionAnalyze) {
                                    void handleAnalyzeCandidate(diagnosticCandidate);
                                  }
                                }}
                                disabled={isPrimaryActionAnalyze ? pendingAnalyzeSymbol === candidate.symbol : false}
                                variant={isPrimaryActionAnalyze ? 'primary' : 'default'}
                              />
                              <div className="relative">
                                <ActionButton
                                  label={language === 'en' ? 'More' : '更多'}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    setRowMoreSymbol((current) => current === candidate.symbol ? null : candidate.symbol);
                                  }}
                                />
                              </div>
                            </div>
                            {isMoreOpen ? (
                              <div data-testid={`scanner-candidate-row-more-${candidate.symbol}`} className="mt-2 grid gap-1.5 rounded-xl border border-white/5 bg-black/20 p-2 sm:grid-cols-2 xl:grid-cols-4">
                                <ActionButton
                                  label={backtestItem?.status === 'running' || backtestItem?.status === 'queued' ? (language === 'en' ? 'Running' : '运行中') : (language === 'en' ? 'Backtest' : '回测')}
                                  onClick={() => void handleBacktestCandidate(diagnosticCandidate)}
                                  disabled={!normalizeCandidateSymbol(candidate.symbol) || backtestItem?.status === 'running' || backtestItem?.status === 'queued'}
                                  title={!normalizeCandidateSymbol(candidate.symbol) ? backtestUnavailableLabel : undefined}
                                />
                                <ActionButton
                                  label={getWatchlistActionLabel(isTracked, isTrackPending, watchlistAuthBlocked, language)}
                                  onClick={() => void handleTrackCandidate(diagnosticCandidate)}
                                  disabled={isTracked || isTrackPending || watchlistAuthBlocked}
                                  title={getWatchlistActionTitle(isTracked, watchlistAuthBlocked, language)}
                                />
                                <ActionButton
                                  label={copiedKey === `candidate:${candidate.symbol}` ? (language === 'en' ? 'Copied' : '已复制') : (language === 'en' ? 'Copy' : '复制')}
                                  onClick={() => void handleCopyText(candidate.symbol, `candidate:${candidate.symbol}`)}
                                />
                                <ActionButton
                                  label={language === 'en' ? 'Export' : '导出'}
                                  onClick={() => {
                                    if (!runDetail) return;
                                    handleExportRows(
                                      [buildScannerExportRow(diagnosticCandidate, runDetail, language)],
                                      buildScannerExportFilename(runDetail, `candidate-${candidate.symbol}`),
                                    );
                                  }}
                                />
                              </div>
                            ) : null}
                            {isExpanded ? (
                              <div data-testid={`scanner-candidate-detail-${candidate.symbol}`} className="mt-2 grid gap-2 border-t border-white/5 pt-2 text-xs text-white/58 md:grid-cols-3">
                                <DetailSection title={language === 'en' ? 'Rule result' : '规则结果'}>
                                  <NotesList
                                    notes={[
                                      friendlyReason,
                                      ...(candidate.failedRules || []),
                                    ]}
                                    empty={language === 'en' ? 'No failed rules' : '无失败规则'}
                                  />
                                </DetailSection>
                                <DetailSection title={language === 'en' ? 'Missing fields' : '缺失字段'}>
                                  <NotesList notes={candidate.missingFields || []} empty={language === 'en' ? 'No missing fields' : '无缺失字段'} />
                                </DetailSection>
                                <DetailSection title={language === 'en' ? 'Diagnostics' : '诊断数据'}>
                                  <div className="flex flex-wrap gap-1.5">
                                    <FieldChip label={language === 'en' ? 'Provider' : '来源'} value={candidate.provider || '--'} />
                                    {metricItems.length
                                      ? metricItems.map(([key, value]) => (
                                        <FieldChip key={`${candidate.symbol}-${key}`} label={key} value={String(value ?? '--')} />
                                      ))
                                      : <span className="text-xs text-white/32">{language === 'en' ? 'No metrics' : '无指标'}</span>}
                                  </div>
                                </DetailSection>
                              </div>
                            ) : null}
                          </article>
                        );
                      })}
                    </div>
                  ) : (
                    <ScannerEmptyState
                      title={language === 'en' ? 'No candidates in this filter' : '当前过滤无候选'}
                      body={language === 'en' ? 'Switch to Candidate pool or All to inspect the full submitted universe.' : '切换到候选池或全部查看完整提交范围。'}
                    />
                  )
                ) : sortedCandidates.length ? (
                  viewMode === 'cards' ? (
                    <>
                    <div className="grid grid-cols-1 gap-2.5 xl:grid-cols-2">
                    {sortedCandidates.map((candidate) => {
                      const isExpanded = expandedSymbol === candidate.symbol;
                      const candidateIdentity = getCandidateIdentity(candidate);
                      const candidateWatchlistIdentity = getWatchlistIdentity(runDetail?.market || market, candidate.symbol);
                      const isTracked = trackedWatchlistIdentitySet.has(candidateWatchlistIdentity);
                      const isTrackPending = pendingWatchlistIdentity === candidateWatchlistIdentity;
                      const backtestItem = backtestItemsBySymbol[normalizeCandidateSymbol(candidate.symbol) || ''];
                      const entryRange = getEntryRange(candidate);
                      const targetPrice = getTargetPrice(candidate);
                      const stopLoss = getStopLoss(candidate);
                      const sourceBadge = getSourceBadge(candidate, runDetail, language);
                      return (
                        <article
                          key={`watchlist-${candidateIdentity}`}
                          data-testid={`scanner-result-card-${candidateIdentity}`}
                          onClick={() => setInspectorSymbol(candidate.symbol)}
                          className="rounded-xl border border-white/5 bg-white/[0.02] p-3 transition-colors hover:border-white/16 hover:bg-white/[0.04]"
                        >
                          <div className="flex justify-between items-start gap-3">
                            <div className="min-w-0 flex flex-col gap-1.5">
                              <div className="flex flex-wrap items-baseline gap-2 min-w-0">
                                <span className="rounded-md border border-white/10 bg-white/[0.06] px-1.5 py-0.5 text-[10px] text-white/58">#{candidate.rank}</span>
                                <h3 className="text-lg font-bold text-white tracking-tight">{candidate.symbol}</h3>
                                <span className="text-xs text-white/40 font-medium truncate max-w-[180px]">
                                  {candidate.companyName || candidate.name}
                                </span>
                              </div>
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="inline-flex rounded border border-emerald-400/25 bg-emerald-400/10 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-widest text-emerald-100">
                                  {language === 'en' ? 'Official' : '官方'}
                                </span>
                                <span className={`inline-flex rounded border px-1.5 py-0.5 text-[10px] font-bold ${scoreBadgeClass(candidate.score)}`}>
                                  {language === 'en' ? `scanner score ${candidate.score}/100` : `扫描评分 ${candidate.score}/100`}
                                </span>
                                {candidate.aiInterpretation?.available ? (
                                  <span className="inline-flex rounded border border-indigo-400/20 bg-indigo-400/10 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-100">
                                    {language === 'en' ? 'AI interpretation' : 'AI 解读'}
                                    {candidate.aiInterpretation.provider ? ` · ${candidate.aiInterpretation.provider}` : ''}
                                  </span>
                                ) : null}
                                {sourceBadge ? (
                                  <span className="inline-flex max-w-[220px] truncate rounded border border-white/8 bg-white/[0.035] px-1.5 py-0.5 text-[10px] text-white/45">
                                    {sourceBadge}
                                  </span>
                                ) : null}
                                {isTracked ? (
                                  <span className="inline-flex rounded border border-emerald-400/20 bg-emerald-400/10 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-100">
                                    {language === 'en' ? 'Tracked' : '已追踪'}
                                  </span>
                                ) : null}
                              </div>
                            </div>
	                            <button
	                              type="button"
	                              onClick={(event) => {
	                                event.stopPropagation();
	                                setInspectorSymbol(candidate.symbol);
	                                setExpandedSymbol(isExpanded ? null : candidate.symbol);
	                              }}
                              className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-white/8 bg-white/[0.04] px-2.5 py-1 text-xs text-white/65 hover:bg-white/[0.08]"
                            >
                              {language === 'en' ? 'Detail' : '详情'}
                              {isExpanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                            </button>
                          </div>

                          <div className="mt-2.5 grid gap-2">
                            <section>
                              <p className="line-clamp-1 text-xs leading-relaxed text-white/66">{getKeyReason(candidate, runDetail, language)}</p>
                              {candidate.featureSignals?.length ? (
                                <div className="mt-1.5 flex flex-wrap gap-1.5">
                                  {candidate.featureSignals.slice(0, 2).map((signal) => (
                                    <FieldChip key={`${candidate.symbol}-${signal.label}-${signal.value}`} label={signal.label} value={signal.value} />
                                  ))}
                                </div>
                              ) : null}
                            </section>

                            <section className="grid grid-cols-3 gap-2 rounded-lg border border-white/5 bg-black/20 p-2">
                              <div>
                                <div className="text-[10px] text-white/40 mb-1 uppercase">{language === 'en' ? 'Entry range' : '建仓区间'}</div>
                                <div className="truncate text-xs text-white font-medium">{entryRange || '--'}</div>
                              </div>
                              <div>
                                <div className="text-[10px] text-white/40 mb-1 uppercase">{language === 'en' ? 'Target price' : '目标价'}</div>
                                <div className="truncate text-xs font-medium text-white">{targetPrice || '--'}</div>
                              </div>
                              <div>
                                <div className="text-[10px] text-white/40 mb-1 uppercase">{language === 'en' ? 'Stop loss' : '止损位'}</div>
                                <div className="truncate text-xs text-red-300 font-medium">{stopLoss || '--'}</div>
                              </div>
                            </section>

                            {candidate.keyMetrics?.length ? (
                              <section>
                                <LabeledValueGrid items={candidate.keyMetrics.slice(0, 3)} empty="" />
                              </section>
                            ) : null}

                            <div className="flex flex-wrap gap-1.5 pt-0.5">
                              <ActionButton
                                label={pendingAnalyzeSymbol === candidate.symbol ? (language === 'en' ? 'Analyzing...' : '分析中...') : (language === 'en' ? 'Analyze' : '分析')}
                                icon={<Play className="h-3.5 w-3.5" />}
                                onClick={() => void handleAnalyzeCandidate(candidate)}
                                disabled={pendingAnalyzeSymbol === candidate.symbol}
                                variant="primary"
                              />
                              <ActionButton
                                label={backtestItem?.status === 'running' || backtestItem?.status === 'queued' ? (language === 'en' ? 'Running' : '运行中') : (language === 'en' ? 'Backtest' : '回测')}
                                icon={<TestTubeDiagonal className="h-3.5 w-3.5" />}
                                onClick={() => void handleBacktestCandidate(candidate)}
                                disabled={!normalizeCandidateSymbol(candidate.symbol) || backtestItem?.status === 'running' || backtestItem?.status === 'queued'}
                                title={!normalizeCandidateSymbol(candidate.symbol) ? backtestUnavailableLabel : undefined}
                              />
                              <ActionButton
                                label={getWatchlistActionLabel(isTracked, isTrackPending, watchlistAuthBlocked, language)}
                                icon={isTracked ? <BookmarkCheck className="h-3.5 w-3.5" /> : <BookmarkPlus className="h-3.5 w-3.5" />}
                                onClick={() => void handleTrackCandidate(candidate)}
                                disabled={isTracked || isTrackPending}
                                variant={isTracked ? 'default' : 'primary'}
                                title={getWatchlistActionTitle(isTracked, watchlistAuthBlocked, language)}
                              />
                              <ActionButton
                                label={copiedKey === `candidate:${candidate.symbol}` ? (language === 'en' ? 'Copied' : '已复制') : (language === 'en' ? 'Copy' : '复制')}
                                icon={<Copy className="h-3.5 w-3.5" />}
                                onClick={() => void handleCopyText(candidate.symbol, `candidate:${candidate.symbol}`)}
                              />
                              <ActionButton
                                label={language === 'en' ? 'Export' : '导出'}
                                icon={<Download className="h-3.5 w-3.5" />}
                                onClick={() => {
                                  if (!runDetail) return;
                                  handleExportRows(
                                    [buildScannerExportRow(candidate, runDetail, language)],
                                    buildScannerExportFilename(runDetail, `candidate-${candidate.symbol}`),
                                  );
                                }}
                              />
                            </div>
                            <ScannerBacktestResultStrip item={backtestItem} language={language} />
                          </div>

                          {isExpanded && runDetail ? (
                            <CandidateDetailPanel
                              candidate={candidate}
                              runDetail={runDetail}
                              language={language}
                              onAnalyze={(nextCandidate) => void handleAnalyzeCandidate(nextCandidate)}
                              onCopy={(nextCandidate) => void handleCopyText(nextCandidate.symbol, `candidate:${nextCandidate.symbol}`)}
                              onExport={(nextCandidate) => handleExportRows(
                                [buildScannerExportRow(nextCandidate, runDetail, language)],
                                buildScannerExportFilename(runDetail, `candidate-${nextCandidate.symbol}`),
                              )}
                              onTrack={(nextCandidate) => void handleTrackCandidate(nextCandidate)}
                              onBacktest={(nextCandidate) => void handleBacktestCandidate(nextCandidate)}
                              isAnalyzing={pendingAnalyzeSymbol === candidate.symbol}
                              isCopied={copiedKey === `candidate:${candidate.symbol}`}
                              isTracked={isTracked}
                              isTrackPending={isTrackPending}
                              isWatchlistAuthBlocked={watchlistAuthBlocked}
                              backtestActionLabel={backtestUnavailableLabel}
                              backtestItem={backtestItem}
                            />
                          ) : null}
                        </article>
                      );
                    })}
                    </div>
                    {previewCandidates.length ? (
                      <div
                        data-testid="scanner-candidate-preview"
                        className="mt-3 rounded-xl border border-white/5 bg-white/[0.02] p-3 text-sm backdrop-blur-md transition-all hover:border-white/10"
                      >
                        <div className="mb-2 flex min-w-0 flex-wrap items-center gap-1.5 text-[11px] text-white/45">
                          <span className="rounded-md border border-blue-400/20 bg-blue-400/10 px-2 py-0.5 text-blue-100/80">
                            {language === 'en'
                              ? `Threshold ${previewThreshold} preview can select ${previewSelectedDiagnostics.length}`
                              : `阈值 ${previewThreshold} 预览可入选 ${previewSelectedDiagnostics.length} 个`}
                          </span>
                        </div>
                        <div className="mb-2 flex min-w-0 items-center justify-between gap-2">
                          <span className="min-w-0 truncate text-xs text-white/58">
                            {language === 'en'
                              ? `${runDetail?.summary?.universeCount ? Math.max(0, runDetail.summary.universeCount - sortedCandidates.length) : previewCandidates.length} other candidates were not selected`
                              : `其余 ${runDetail?.summary?.universeCount ? Math.max(0, runDetail.summary.universeCount - sortedCandidates.length) : previewCandidates.length} 个候选未入选`}
                          </span>
                          <button
                            type="button"
                            onClick={() => setCandidateFilter('pool')}
                            className="shrink-0 rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-xs text-white/70 hover:bg-white/10"
                          >
                            {language === 'en' ? 'View all candidates' : '查看全部候选'}
                          </button>
                        </div>
                        {previewAddedDiagnostics.length ? (
                          <div data-testid="scanner-preview-added-list" className="mb-2 grid gap-1.5">
                            {previewAddedDiagnostics.slice(0, 4).map((candidate) => (
                              <button
                                key={`preview-added-${candidate.symbol}`}
                                type="button"
                                data-testid={`scanner-preview-added-${candidate.symbol}`}
                                onClick={() => {
                                  setInspectorSymbol(candidate.symbol);
                                  setCandidateFilter('pool');
                                }}
                                className="grid min-w-0 grid-cols-[minmax(54px,0.45fr)_minmax(72px,0.55fr)_minmax(0,1fr)] items-center gap-2 rounded-lg border border-blue-400/15 bg-blue-400/[0.06] px-2 py-1.5 text-left text-xs hover:bg-blue-400/10"
                              >
                                <span className="truncate font-mono font-semibold text-blue-100">{candidate.symbol}</span>
                                <span className="truncate font-mono text-blue-100/58">{diagnosticScoreValue(candidate)}</span>
                                <span className="truncate text-white/50" title={getDiagnosticReason(candidate, language)}>
                                  {getDiagnosticReason(candidate, language)}
                                </span>
                              </button>
                            ))}
                          </div>
                        ) : null}
                        <div className="grid gap-1.5">
                          {previewCandidates.map((candidate) => (
                            <button
                              key={`preview-${candidate.symbol}`}
                              type="button"
                              onClick={() => {
                                setInspectorSymbol(candidate.symbol);
                                setCandidateFilter('pool');
                              }}
                              className="grid min-w-0 grid-cols-[minmax(54px,0.45fr)_minmax(72px,0.55fr)_minmax(0,1fr)] items-center gap-2 rounded-lg border border-white/5 bg-black/20 px-2 py-1.5 text-left text-xs hover:bg-white/[0.04]"
                            >
                              <span className="truncate font-mono font-semibold text-white/78">{candidate.symbol}</span>
                              <span className="truncate font-mono text-white/42">{diagnosticScoreValue(candidate)}</span>
                              <span className="truncate text-white/50" title={getDiagnosticReason(candidate, language)}>
                                {getDiagnosticReason(candidate, language)}
                              </span>
                            </button>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    </>
                ) : (
                  <div data-testid="scanner-result-table" className="overflow-x-auto no-scrollbar rounded-xl border border-white/5 bg-white/[0.02]">
                    <table className="min-w-[980px] w-full border-collapse text-left text-xs">
                      <thead className="border-b border-white/5 bg-black/25 text-[10px] uppercase tracking-[0.16em] text-white/38">
                        <tr>
                          <th className="px-2.5 py-2">{language === 'en' ? 'Rank' : '排名'}</th>
                          <th className="px-2.5 py-2">{language === 'en' ? 'Symbol' : '代码'}</th>
                          <th className="px-2.5 py-2">{language === 'en' ? 'Name' : '名称'}</th>
                          <th className="px-2.5 py-2">{language === 'en' ? 'Scanner score' : '扫描评分'}</th>
                          <th className="px-2.5 py-2">{language === 'en' ? 'Entry range' : '建仓区间'}</th>
                          <th className="px-2.5 py-2">{language === 'en' ? 'Target price' : '目标价'}</th>
                          <th className="px-2.5 py-2">{language === 'en' ? 'Stop loss' : '止损位'}</th>
                          <th className="px-2.5 py-2">{language === 'en' ? 'Key reason' : '关键原因'}</th>
                          <th className="px-2.5 py-2">{language === 'en' ? 'Risk summary' : '风险摘要'}</th>
                          <th className="px-2.5 py-2">{language === 'en' ? 'Data/source' : '数据/来源'}</th>
                          <th className="px-2.5 py-2">{language === 'en' ? 'Actions' : '操作'}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sortedCandidates.map((candidate) => {
                          const isExpanded = expandedSymbol === candidate.symbol;
                          const candidateIdentity = getCandidateIdentity(candidate);
                          const candidateWatchlistIdentity = getWatchlistIdentity(runDetail?.market || market, candidate.symbol);
                          const isTracked = trackedWatchlistIdentitySet.has(candidateWatchlistIdentity);
                          const isTrackPending = pendingWatchlistIdentity === candidateWatchlistIdentity;
                          const backtestItem = backtestItemsBySymbol[normalizeCandidateSymbol(candidate.symbol) || ''];
                          return (
                            <React.Fragment key={`table-${candidateIdentity}`}>
                              <tr
                                data-testid={`scanner-result-row-${candidateIdentity}`}
                                className="cursor-pointer border-b border-white/5 text-white/72 hover:bg-white/[0.035]"
                                onClick={() => {
                                  setInspectorSymbol(candidate.symbol);
                                  setExpandedSymbol(isExpanded ? null : candidate.symbol);
                                }}
                              >
                                <td className="px-2.5 py-2 text-white/45">#{candidate.rank}</td>
                                <td className="px-2.5 py-2 font-semibold text-white">{candidate.symbol}</td>
                                <td className="px-2.5 py-2 text-white/55">{candidate.companyName || candidate.name}</td>
                                <td className="px-2.5 py-2">
                                  <span className={`inline-flex rounded border px-1.5 py-0.5 text-[10px] font-bold ${scoreBadgeClass(candidate.score)}`}>
                                    {candidate.score}/100
                                  </span>
                                </td>
                                <td className="px-2.5 py-2">{getEntryRange(candidate) || '--'}</td>
                                <td className="px-2.5 py-2">{getTargetPrice(candidate) || '--'}</td>
                                <td className="px-2.5 py-2">{getStopLoss(candidate) || '--'}</td>
                                <td className="max-w-[220px] px-2.5 py-2 text-white/62">{getKeyReason(candidate, runDetail, language)}</td>
                                <td className="max-w-[180px] px-2.5 py-2 text-white/52">{getRiskSummary(candidate, language)}</td>
                                <td className="max-w-[180px] px-2.5 py-2 text-white/42">{getSourceBadge(candidate, runDetail, language) || '--'}</td>
                                <td className="px-2.5 py-2">
                                  <div className="flex flex-wrap gap-1.5">
                                    <ActionButton
                                      label={language === 'en' ? 'Analyze' : '分析'}
                                      onClick={(event) => {
                                        event.stopPropagation();
                                        void handleAnalyzeCandidate(candidate);
                                      }}
                                      disabled={pendingAnalyzeSymbol === candidate.symbol}
                                      variant="primary"
                                    />
                                    <ActionButton
                                      label={getWatchlistActionLabel(isTracked, isTrackPending, watchlistAuthBlocked, language)}
                                      icon={isTracked ? <BookmarkCheck className="h-3.5 w-3.5" /> : <BookmarkPlus className="h-3.5 w-3.5" />}
                                      onClick={(event) => {
                                        event.stopPropagation();
                                        void handleTrackCandidate(candidate);
                                      }}
                                      disabled={isTracked || isTrackPending}
                                      variant={isTracked ? 'default' : 'primary'}
                                      title={getWatchlistActionTitle(isTracked, watchlistAuthBlocked, language)}
                                    />
                                    <ActionButton
                                      label={copiedKey === `candidate:${candidate.symbol}` ? (language === 'en' ? 'Copied' : '已复制') : (language === 'en' ? 'Copy' : '复制')}
                                      onClick={(event) => {
                                        event.stopPropagation();
                                        void handleCopyText(candidate.symbol, `candidate:${candidate.symbol}`);
                                      }}
                                    />
                                    <ActionButton
                                      label={language === 'en' ? 'Detail' : '详情'}
                                      onClick={(event) => {
                                        event.stopPropagation();
                                        setExpandedSymbol(isExpanded ? null : candidate.symbol);
                                      }}
                                    />
                                    <ActionButton
                                      label={backtestItem?.status === 'running' || backtestItem?.status === 'queued' ? (language === 'en' ? 'Running' : '运行中') : (language === 'en' ? 'Backtest' : '回测')}
                                      onClick={(event) => {
                                        event.stopPropagation();
                                        void handleBacktestCandidate(candidate);
                                      }}
                                      disabled={!normalizeCandidateSymbol(candidate.symbol) || backtestItem?.status === 'running' || backtestItem?.status === 'queued'}
                                      title={!normalizeCandidateSymbol(candidate.symbol) ? backtestUnavailableLabel : undefined}
                                    />
                                  </div>
                                </td>
                              </tr>
                              {isExpanded && runDetail ? (
                                <tr>
                                  <td colSpan={11} className="border-b border-white/5 px-3 pb-4">
                                    <CandidateDetailPanel
                                      candidate={candidate}
                                      runDetail={runDetail}
                                      language={language}
                                      onAnalyze={(nextCandidate) => void handleAnalyzeCandidate(nextCandidate)}
                                      onCopy={(nextCandidate) => void handleCopyText(nextCandidate.symbol, `candidate:${nextCandidate.symbol}`)}
                                      onExport={(nextCandidate) => handleExportRows(
                                        [buildScannerExportRow(nextCandidate, runDetail, language)],
                                        buildScannerExportFilename(runDetail, `candidate-${nextCandidate.symbol}`),
                                      )}
                                      onTrack={(nextCandidate) => void handleTrackCandidate(nextCandidate)}
                                      onBacktest={(nextCandidate) => void handleBacktestCandidate(nextCandidate)}
                                      isAnalyzing={pendingAnalyzeSymbol === candidate.symbol}
                                      isCopied={copiedKey === `candidate:${candidate.symbol}`}
                                      isTracked={isTracked}
                                      isTrackPending={isTrackPending}
                                      isWatchlistAuthBlocked={watchlistAuthBlocked}
                                      backtestActionLabel={backtestUnavailableLabel}
                                      backtestItem={backtestItem}
                                    />
                                  </td>
                                </tr>
                              ) : null}
                            </React.Fragment>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )
              ) : (
                <ScannerEmptyState
                  title={runDetail?.summary?.selectedCount === 0 && diagnosticCandidates.length ? (language === 'en' ? 'No selected candidates' : '本次无入选候选') : emptyStateTitle}
                  body={runDetail?.summary?.selectedCount === 0 && diagnosticCandidates.length
                    ? (language === 'en' ? 'Open Candidate pool or All to inspect rejected and data-failed candidates.' : '切换到候选池或全部查看淘汰与数据失败原因。')
                    : pageError?.message || emptyStateBody}
                />
              )}
                    {runDetail && inspectorCandidate ? (() => {
                      const mobileMarket = normalizeScannerMarket(runDetail.market || market);
                      const mobileWatchlistIdentity = getWatchlistIdentity(mobileMarket, inspectorCandidate.symbol);
                      const mobileTracked = Boolean(mobileWatchlistIdentity && trackedWatchlistIdentitySet.has(mobileWatchlistIdentity));
                      const mobileTrackPending = pendingWatchlistIdentity === mobileWatchlistIdentity;
                      const mobileBacktestItem = backtestItemsBySymbol[normalizeCandidateSymbol(inspectorCandidate.symbol) || ''];
                      return (
                        <div className="mt-3 xl:hidden">
                          <CandidateInspector
                            candidate={inspectorCandidate}
                            runDetail={runDetail}
                            language={language}
                            previewThreshold={previewThreshold}
                            comparison={comparisonState.bySymbol.get(normalizeCandidateSymbol(inspectorCandidate.symbol) || '')}
                            onAnalyze={(nextCandidate) => void handleAnalyzeCandidate(nextCandidate)}
                            onCopy={(nextCandidate) => void handleCopyText(nextCandidate.symbol, `candidate:${nextCandidate.symbol}`)}
                            onExport={(nextCandidate) => handleExportRows(
                              [buildScannerExportRow(nextCandidate, runDetail, language)],
                              buildScannerExportFilename(runDetail, `candidate-${nextCandidate.symbol}`),
                            )}
                            onTrack={(nextCandidate) => void handleTrackCandidate(nextCandidate)}
                            onBacktest={(nextCandidate) => void handleBacktestCandidate(nextCandidate)}
                            isAnalyzing={pendingAnalyzeSymbol === inspectorCandidate.symbol}
                            isCopied={copiedKey === `candidate:${inspectorCandidate.symbol}`}
                            isTracked={mobileTracked}
                            isTrackPending={mobileTrackPending}
                            isWatchlistAuthBlocked={watchlistAuthBlocked}
                            backtestActionLabel={backtestUnavailableLabel}
                            backtestItem={mobileBacktestItem}
                            testId="scanner-mobile-candidate-inspector"
                          />
                        </div>
                      );
                    })() : null}
                  </div>

                  {runDetail && inspectorCandidate ? (() => {
                    const inspectorMarket = normalizeScannerMarket(runDetail.market || market);
                    const inspectorWatchlistIdentity = getWatchlistIdentity(inspectorMarket, inspectorCandidate.symbol);
                    const inspectorTracked = Boolean(inspectorWatchlistIdentity && trackedWatchlistIdentitySet.has(inspectorWatchlistIdentity));
                    const inspectorTrackPending = pendingWatchlistIdentity === inspectorWatchlistIdentity;
                    const inspectorBacktestItem = backtestItemsBySymbol[normalizeCandidateSymbol(inspectorCandidate.symbol) || ''];
                    return (
                      <div className="hidden min-h-0 xl:block">
                        <div className="sticky top-0 max-h-[calc(100vh-190px)] min-h-0 overflow-y-auto pr-1 no-scrollbar">
                          <CandidateInspector
                            candidate={inspectorCandidate}
                            runDetail={runDetail}
                            language={language}
                            previewThreshold={previewThreshold}
                            comparison={comparisonState.bySymbol.get(normalizeCandidateSymbol(inspectorCandidate.symbol) || '')}
                            onAnalyze={(nextCandidate) => void handleAnalyzeCandidate(nextCandidate)}
                            onCopy={(nextCandidate) => void handleCopyText(nextCandidate.symbol, `candidate:${nextCandidate.symbol}`)}
                            onExport={(nextCandidate) => handleExportRows(
                              [buildScannerExportRow(nextCandidate, runDetail, language)],
                              buildScannerExportFilename(runDetail, `candidate-${nextCandidate.symbol}`),
                            )}
                            onTrack={(nextCandidate) => void handleTrackCandidate(nextCandidate)}
                            onBacktest={(nextCandidate) => void handleBacktestCandidate(nextCandidate)}
                            isAnalyzing={pendingAnalyzeSymbol === inspectorCandidate.symbol}
                            isCopied={copiedKey === `candidate:${inspectorCandidate.symbol}`}
                            isTracked={inspectorTracked}
                            isTrackPending={inspectorTrackPending}
                            isWatchlistAuthBlocked={watchlistAuthBlocked}
                            backtestActionLabel={backtestUnavailableLabel}
                            backtestItem={inspectorBacktestItem}
                          />
                        </div>
                      </div>
                    );
                  })() : null}
                </div>
              </div>

              {runDetail && hasCandidateDiagnostics ? (
                <div data-testid="scanner-secondary-sections" className="border-t border-white/5 px-3 py-3">
                  <div className="grid gap-2.5">
                    {rejectionBuckets.length || hasRunDiagnosticsContent(runDetail) ? (
                      <AdvancedDisclosure
                        testId="scanner-diagnostics-disclosure"
                        title={language === 'en' ? 'Diagnostic details' : '诊断详情'}
                        summary={language === 'en'
                          ? `Evaluated ${runDetail.summary?.evaluatedCount ?? runDetail.evaluatedSize}, selected ${runDetail.summary?.selectedCount ?? shortlistCount}, main rejection: ${rejectionBuckets[0]?.label || 'n/a'}`
                          : `本次共评估 ${runDetail.summary?.evaluatedCount ?? runDetail.evaluatedSize}，只入选 ${runDetail.summary?.selectedCount ?? shortlistCount}，主要淘汰原因：${rejectionBuckets[0]?.label || '暂无'}`}
                        icon="info"
                        open={isDeveloperDiagnosticsOpen}
                        onToggle={setIsDeveloperDiagnosticsOpen}
                      >
                        <DiagnosticsPanel runDetail={runDetail} language={language} />
                      </AdvancedDisclosure>
                    ) : null}
                    <AdvancedDisclosure
                      testId="scanner-run-comparison-strip"
                      title={language === 'en' ? 'History comparison' : '历史对比'}
                      summary={comparisonState.previousRun && comparisonState.chips.length
                        ? `${language === 'en' ? 'Compared with previous run' : '上次对比'}：${comparisonState.chips[0]}`
                        : (language === 'en' ? 'No previous comparable run' : '暂无上次扫描对比')}
                      icon="history"
                    >
                      <div className="ui-scroll-x-quiet flex max-w-full items-center gap-1.5">
                        <span className="shrink-0 text-[10px] font-bold uppercase tracking-widest text-white/40">
                          {language === 'en' ? 'Compared with previous run' : '上次对比'}
                        </span>
                        {comparisonState.previousRun && comparisonState.chips.length ? (
                          comparisonState.chips.map((chip) => (
                            <span key={chip} className="shrink-0 rounded-md border border-white/8 bg-black/20 px-2 py-0.5 text-white/62">
                              {chip}
                            </span>
                          ))
                        ) : (
                          <span className="shrink-0 rounded-md border border-white/8 bg-black/20 px-2 py-0.5 text-white/42">
                            {language === 'en' ? 'No previous comparable run' : '暂无上次扫描对比'}
                          </span>
                        )}
                      </div>
                    </AdvancedDisclosure>
                    <AdvancedDisclosure
                      testId="scanner-strategy-experiment"
                      title={language === 'en' ? 'Strategy experiment' : '策略实验区'}
                      summary={language === 'en' ? 'History simulation · batch backtest · recent results' : '历史模拟 · 批量回测 · 最近结果'}
                      icon="backtest"
                    >
                      <div className="grid gap-3">
                        <ScannerStrategySimulationPanel
                          language={language}
                          lookbackDays={simulationLookbackDays}
                          forwardDays={simulationForwardDays}
                          onLookbackDaysChange={setSimulationLookbackDays}
                          onForwardDaysChange={setSimulationForwardDays}
                          onRun={() => void handleStrategySimulation()}
                          result={strategySimulation}
                          isLoading={isStrategySimulationLoading}
                          error={strategySimulationError}
                          disabled={strategySimulationDisabled}
                        />
                        <ScannerBacktestLab
                          language={language}
                          items={backtestItems}
                          isRunning={isBacktestBatchRunning}
                          onRunBatch={handleBacktestBatch}
                          onCopySymbol={(symbol) => void handleCopyText(symbol, `backtest:${symbol}`)}
                          counts={backtestCounts}
                        />
                      </div>
                    </AdvancedDisclosure>
                  </div>
                </div>
              ) : null}
            </section>
          </div>
        </main>
      </div>

      <Drawer
        isOpen={isHistoryDrawerOpen}
        onClose={() => setIsHistoryDrawerOpen(false)}
        title={language === 'en' ? 'Historical scan replay' : '历史扫描回放'}
        width="max-w-4xl"
      >
        <div data-testid="user-scanner-bento-drawer" className="ml-auto w-full max-w-4xl rounded-l-[40px] bg-transparent p-6 text-foreground sm:p-8">
          <div className="grid gap-6">
            <div>
              <p className="text-[11px] uppercase tracking-[0.18em] text-muted-text">{language === 'en' ? 'Historical scan replay' : '历史扫描回放'}</p>
              <h2 className="mt-1 text-xl text-foreground">{language === 'en' ? 'Recent scanner runs' : '近期扫描记录'}</h2>
            </div>

            {historyError ? <ApiErrorAlert error={historyError} /> : null}
            {isLoadingHistory ? <div className="theme-panel-subtle rounded-[28px] px-4 py-5 text-sm text-secondary-text">{t('scanner.loadingHistory')}</div> : null}
            {!isLoadingHistory && historyCards.length ? (
              <div className="space-y-3">
                {historyCards.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => {
                      void loadRun(item.id);
                      setIsHistoryDrawerOpen(false);
                    }}
                    className={`w-full flex flex-col gap-3 bg-white/[0.02] border border-white/5 rounded-2xl p-5 hover:bg-white/[0.04] transition-colors text-left ${item.id === selectedRunId ? 'border-white/15 bg-white/[0.05]' : ''}`}
                  >
                    <div className="flex w-full max-w-full items-start gap-3 overflow-hidden">
                      <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <PillBadge variant={marketVariant(item.market)}>{item.market === 'us' ? t('scanner.marketUs') : item.market === 'hk' ? t('scanner.marketHk') : t('scanner.marketCn')}</PillBadge>
                          <PillBadge variant={statusVariant(item.status)}>{t(`scanner.status.${item.status}`)}</PillBadge>
                          {item.watchlistDate ? <PillBadge variant="history">{formatDateOnly(item.watchlistDate, language)}</PillBadge> : null}
                          <PillBadge variant="history">{item.profileLabel || item.profile}</PillBadge>
                        </div>
                        <h4 className="mt-3 mb-2 w-full truncate font-bold text-white">
                          {item.historyHeadline.title}
                        </h4>
                        {item.historyHeadline.detail ? (
                          <p className="break-words whitespace-normal w-full text-sm text-white/70 leading-relaxed">
                            {item.historyHeadline.detail}
                          </p>
                        ) : null}
                        <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-secondary-text">
                          <span>{`${t('scanner.metricShortlist')}: ${item.shortlistSize}`}</span>
                          <span>{`${t('scanner.metricUniverse')}: ${item.universeSize}`}</span>
                          <span>{`${language === 'en' ? 'Evaluated' : '已评估'}: ${item.evaluatedSize}`}</span>
                          <span>{formatTimestamp(item.runAt, language)}</span>
                        </div>
                        {hasReviewSummary(item.reviewSummary) || hasComparison(item.changeSummary) ? (
                          <div className="mt-2 flex flex-wrap gap-2">
                            {hasComparison(item.changeSummary) ? (
                              <span className="rounded border border-white/8 bg-white/[0.035] px-2 py-1 text-[10px] text-white/52">
                                {language === 'en'
                                  ? `new ${item.changeSummary.newCount} · retained ${item.changeSummary.retainedCount} · dropped ${item.changeSummary.droppedCount}`
                                  : `新增 ${item.changeSummary.newCount} · 保留 ${item.changeSummary.retainedCount} · 移出 ${item.changeSummary.droppedCount}`}
                              </span>
                            ) : null}
                            {hasReviewSummary(item.reviewSummary) ? (
                              <span className="rounded border border-white/8 bg-white/[0.035] px-2 py-1 text-[10px] text-white/52">
                                {language === 'en'
                                  ? `reviewed ${item.reviewSummary.reviewedCount}/${item.reviewSummary.candidateCount}`
                                  : `复盘 ${item.reviewSummary.reviewedCount}/${item.reviewSummary.candidateCount}`}
                              </span>
                            ) : null}
                          </div>
                        ) : null}
                        {item.matchedSymbols.length ? (
                          <div className="product-chip-list product-chip-list--tight mt-3 w-full" data-testid={`scanner-history-symbols-${item.id}`}>
                            {item.matchedSymbols.map((symbol) => (
                              <span
                                key={`${item.id}-${symbol}`}
                                className="product-chip shrink-0 text-[10px] px-2 py-1"
                              >
                                {symbol}
                              </span>
                            ))}
                            {item.overflowSymbolCount > 0 ? (
                              <span className="product-chip shrink-0 text-[10px] px-2 py-1">
                                +{item.overflowSymbolCount}
                              </span>
                            ) : null}
                          </div>
                        ) : null}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            ) : null}
            {!isLoadingHistory && !historyItems.length ? <ScannerEmptyState title={emptyStateTitle} body={emptyStateBody} className="py-12" /> : null}
            {totalHistoryPages > 1 ? <div className="pt-2"><Pagination currentPage={historyPage} totalPages={totalHistoryPages} onPageChange={(page) => void fetchHistory(page)} /></div> : null}
          </div>
        </div>
      </Drawer>
    </>
  );
};

export default UserScannerPage;
