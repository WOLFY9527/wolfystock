import React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArrowDownUp,
  BookmarkCheck,
  BookmarkPlus,
  ChevronDown,
  ChevronUp,
  Copy,
  Download,
  LayoutGrid,
  PanelRightOpen,
  Play,
  Sparkles,
  Table2,
  TestTubeDiagonal,
} from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { analysisApi, DuplicateTaskError } from '../api/analysis';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { scannerApi } from '../api/scanner';
import { watchlistApi } from '../api/watchlist';
import { ApiErrorAlert, Drawer, Pagination, PillBadge, SectionShell } from '../components/common';
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
  ScannerThemeSuggestion,
  ScannerTheme,
  ScannerWatchlistComparison,
} from '../types/scanner';
import type { WatchlistItem } from '../types/watchlist';
import { buildLocalizedPath } from '../utils/localeRouting';
import {
  getScannerDetailOptions,
  getScannerProfileOptions,
  getScannerUniverseOptions,
  SCANNER_PROFILE_DEFAULTS,
} from './scannerPageShared';

const HISTORY_PAGE_SIZE = 8;

type PillOption = { value: string; label: string };
type ViewMode = 'cards' | 'table';
type CandidateFilter = 'selected' | 'pool' | 'rejected' | 'data_failed' | 'all';
type SortKey = 'score' | 'symbol' | 'target' | 'risk';
type SortDirection = 'asc' | 'desc';
type ScanScope = 'default' | 'theme' | 'symbols';
type ActionNotice = { tone: 'success' | 'warning' | 'danger'; message: string } | null;
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

function buildScannerBacktestPath(
  candidate: ScannerCandidate,
  runDetail: ScannerRunDetail | null,
  language: 'zh' | 'en',
): string | null {
  const symbol = normalizeCandidateSymbol(candidate.symbol);
  if (!symbol || !runDetail) return null;

  const params = new URLSearchParams({
    symbol,
    source: 'scanner',
    scannerRunId: String(runDetail.id),
    scannerRank: String(candidate.rank),
  });
  const market = normalizeScannerMarket(runDetail.market);
  if (market) params.set('market', market);
  if (runDetail.profile) params.set('scannerProfile', runDetail.profile);
  if (runDetail.themeId) params.set('themeId', runDetail.themeId);
  if (runDetail.universeType) params.set('universeType', runDetail.universeType);

  return buildLocalizedPath(`/backtest?${params.toString()}`, language);
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

function diagnosticMetricValue(candidate: ScannerCandidateDiagnostic, key: string): string {
  const camelKey = key.replace(/_([a-z])/g, (_, char: string) => char.toUpperCase());
  const value = candidate.metrics?.[key] ?? candidate.metrics?.[camelKey];
  if (value === null || value === undefined || value === '') return '--';
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(2);
  return String(value);
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
    'inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs transition-colors',
    variant === 'primary'
      ? 'border-indigo-500/25 bg-indigo-500/10 text-indigo-100 hover:border-indigo-500/45 hover:bg-indigo-500/15'
      : 'border-white/8 bg-white/[0.04] text-white/70 hover:bg-white/[0.08] hover:text-white',
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
        onClick={onClick}
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
      onClick={onClick}
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
    <div className="flex flex-col gap-1.5">
      <span className="text-[10px] uppercase tracking-[0.16em] text-white/40">{label}</span>
      <div
        className={isMarketGroup ? 'flex w-fit rounded-xl border border-white/5 bg-black/40 p-1' : 'flex flex-wrap gap-2'}
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
                  ? 'rounded-lg bg-white/10 px-4 py-1 text-sm font-bold text-white shadow-[0_2px_10px_rgba(0,0,0,0.5)] transition-all'
                  : 'rounded-full border border-white/10 bg-white/10 px-3 py-1 text-xs text-white transition-colors'
                : isMarketGroup
                  ? 'rounded-lg bg-transparent px-4 py-1 text-sm font-medium text-white/40 transition-all hover:text-white/70'
                  : 'rounded-full border border-white/5 bg-transparent px-3 py-1 text-xs text-white/50 transition-colors hover:bg-white/[0.05]'}
            >
              {option.label}
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

function CandidateDetailPanel({
  candidate,
  runDetail,
  language,
  onAnalyze,
  onCopy,
  onExport,
  onTrack,
  isAnalyzing,
  isCopied,
  isTracked,
  isTrackPending,
  isWatchlistAuthBlocked,
  backtestActionLabel,
  backtestHref,
}: {
  candidate: ScannerCandidate;
  runDetail: ScannerRunDetail;
  language: 'zh' | 'en';
  onAnalyze: (candidate: ScannerCandidate) => void;
  onCopy: (candidate: ScannerCandidate) => void;
  onExport: (candidate: ScannerCandidate) => void;
  onTrack: (candidate: ScannerCandidate) => void;
  isAnalyzing: boolean;
  isCopied: boolean;
  isTracked: boolean;
  isTrackPending: boolean;
  isWatchlistAuthBlocked: boolean;
  backtestActionLabel: string;
  backtestHref: string | null;
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
          label={language === 'en' ? 'Backtest' : '回测'}
          icon={<TestTubeDiagonal className="h-3.5 w-3.5" />}
          href={backtestHref || undefined}
          disabled={!backtestHref}
          title={!backtestHref ? backtestActionLabel : undefined}
        />
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
  const hasAnyDiagnostics = coverage
    || provider
    || runDetail.universeNotes.length
    || runDetail.scoringNotes.length
    || hasReviewSummary(runDetail.reviewSummary)
    || hasComparison(runDetail.comparisonToPrevious)
    || aiDiagnostics;

  if (!hasAnyDiagnostics) return null;

  return (
    <details data-testid="scanner-diagnostics-panel" className="mt-3 rounded-xl border border-white/5 bg-white/[0.015] p-3">
      <summary className="cursor-pointer text-xs font-semibold text-white/62">
        {language === 'en' ? 'Diagnostics and replay notes' : '诊断与复盘说明'}
      </summary>
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
    </details>
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
  const [viewMode, setViewMode] = useState<ViewMode>('cards');
  const [sortKey, setSortKey] = useState<SortKey>('score');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [expandedSymbol, setExpandedSymbol] = useState<string | null>(null);
  const [pendingAnalyzeSymbol, setPendingAnalyzeSymbol] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [candidateFilter, setCandidateFilter] = useState<CandidateFilter>('selected');

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
  const selectedOnlyView = !hasCandidateDiagnostics || candidateFilter === 'selected';

  useEffect(() => {
    if (!hasCandidateDiagnostics && candidateFilter !== 'selected') {
      setCandidateFilter('selected');
    }
  }, [candidateFilter, hasCandidateDiagnostics]);

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
          'bento-surface-root flex w-full flex-1 flex-col min-h-0 min-w-0 bg-transparent text-foreground xl:h-[calc(100vh-96px)] xl:overflow-hidden',
        )}
      >
        <main
          data-testid="user-scanner-workspace"
          className="w-full flex-1 flex flex-col min-h-0 min-w-0"
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

          <div className="flex w-full flex-1 min-h-0 min-w-0 flex-col gap-3 xl:flex-row xl:overflow-hidden">
            <section
              data-testid="scanner-sidebar"
              className="flex w-full shrink-0 flex-col overflow-hidden rounded-[16px] border border-white/5 bg-white/[0.015] p-3 max-h-[calc(100vh-120px)] xl:h-full xl:w-[268px] xl:max-h-[calc(100vh-120px)] 2xl:w-[288px]"
            >
              <SectionShell
                className="h-full flex flex-1 flex-col min-h-0 rounded-[24px] p-0 bg-transparent shadow-none"
                contentClassName="h-full flex flex-1 flex-col min-h-0 space-y-0"
              >
                <div
                  data-testid="scanner-sidebar-scroll-region"
                  className="flex flex-1 flex-col min-h-0 gap-2.5 overflow-y-auto no-scrollbar"
                >
                  <PillTagGroup label={t('scanner.marketLabel')} value={market} onChange={(next) => handleMarketChange(next as 'cn' | 'us' | 'hk')} options={[{ value: 'cn', label: t('scanner.marketCn') }, { value: 'us', label: t('scanner.marketUs') }, { value: 'hk', label: t('scanner.marketHk') }]} variant="market" testId="scanner-market-toggle" />
                  <PillTagGroup label={t('scanner.profileLabel')} value={profile} onChange={setProfile} options={profileOptions} />
                  <div className="grid gap-2.5 sm:grid-cols-3 xl:grid-cols-1">
                    <PillTagGroup label={t('scanner.shortlistLabel')} value={shortlistSize} onChange={setShortlistSize} options={[{ value: '5', label: language === 'en' ? 'Top 5' : '前 5' }, { value: '8', label: language === 'en' ? 'Top 8' : '前 8' }, { value: '10', label: language === 'en' ? 'Top 10' : '前 10' }]} />
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
                    <div className="flex flex-col gap-1.5" data-testid="scanner-theme-control">
                      <span className="text-[10px] uppercase tracking-[0.16em] text-white/40">{language === 'en' ? 'Theme' : '主题'}</span>
                      <select
                        data-testid="scanner-theme-select"
                        value={themeId}
                        onChange={(event) => setThemeId(event.target.value)}
                        aria-invalid={Boolean(validationErrors.theme)}
                        aria-describedby={validationErrors.theme ? 'scanner-theme-error' : undefined}
                        className="w-full rounded-lg border border-white/8 bg-black/40 px-2.5 py-1.5 text-xs text-white outline-none focus:border-indigo-400/50"
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
              className="flex flex-1 min-h-[520px] min-w-0 flex-col overflow-hidden rounded-[16px] border border-white/5 bg-white/[0.01] xl:min-h-0"
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
                  <div className="flex flex-wrap items-center gap-2">
                    {runDetail && sortedCandidates.length ? (
                      <>
                        <ActionButton
                          label={language === 'en' ? 'Export CSV' : '导出 CSV'}
                          icon={<Download className="h-3.5 w-3.5" />}
                          onClick={() => handleExportRows(
                            sortedCandidates.map((candidate) => buildScannerExportRow(candidate, runDetail, language)),
                            buildScannerExportFilename(runDetail),
                          )}
                        />
                        <ActionButton
                          label={language === 'en' ? 'Copy all symbols' : '复制全部代码'}
                          icon={<Copy className="h-3.5 w-3.5" />}
                          onClick={() => void handleCopyText(sortedCandidates.map((candidate) => candidate.symbol).join(', '), 'all-symbols')}
                        />
                        <ActionButton
                          label={language === 'en' ? 'Copy top 5' : '复制前 5'}
                          icon={<Copy className="h-3.5 w-3.5" />}
                          onClick={() => void handleCopyText(sortedCandidates.slice(0, 5).map((candidate) => candidate.symbol).join(', '), 'top-5-symbols')}
                        />
                      </>
                    ) : null}
                    <button
                      ref={openHistoryDrawerButton.ref}
                      type="button"
                      data-testid="user-scanner-bento-drawer-trigger"
                      onClick={openHistoryDrawerButton.onClick}
                      onPointerUp={openHistoryDrawerButton.onPointerUp}
                      className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.05] px-2.5 py-1 text-xs text-white/80 transition-colors hover:bg-white/[0.1]"
                    >
                      <PanelRightOpen className="h-4 w-4" />
                      <span>{language === 'en' ? 'Historical replay' : '历史扫描回放'}</span>
                    </button>
                  </div>
                </div>
              </div>

              {runDetail ? (
                <div className="shrink-0 border-b border-white/5 px-3 py-2" data-testid="scanner-diagnostic-summary">
                  <div className="flex flex-wrap items-center gap-2 rounded-xl border border-white/5 bg-white/[0.02] px-2.5 py-2 backdrop-blur-md">
                    {[
                      ['UNIVERSE', runDetail.summary?.universeCount ?? runDetail.acceptedSymbolsCount ?? runDetail.universeSize],
                      ['EVALUATED', runDetail.summary?.evaluatedCount ?? runDetail.evaluatedSize],
                      ['SELECTED', runDetail.summary?.selectedCount ?? shortlistCount],
                      ['REJECTED', runDetail.summary?.rejectedCount ?? 0],
                      ['DATA FAILED', runDetail.summary?.dataFailedCount ?? 0],
                      ['SKIPPED', runDetail.summary?.skippedCount ?? 0],
                    ].map(([label, value]) => (
                      <span key={label} className="inline-flex items-baseline gap-1.5 rounded-lg border border-white/5 bg-black/20 px-2 py-1">
                        <span className="text-[10px] font-bold uppercase tracking-widest text-white/40">{label}</span>
                        <span className="font-mono text-xs text-white/78">{value}</span>
                      </span>
                    ))}
                    <span className="min-w-0 flex-1 truncate text-[11px] text-white/36">
                      {runDetail.summary?.limitedByResultCap
                        ? (language === 'en' ? 'Result cap limited diagnostics' : '结果上限限制了诊断')
                        : (language === 'en' ? 'Diagnostics cover the submitted universe' : '诊断覆盖本次提交候选池')}
                    </span>
                  </div>
                  {runDetail.summary?.selectedCount === 1 && (runDetail.summary?.rejectedCount || runDetail.summary?.dataFailedCount || runDetail.summary?.skippedCount) ? (
                    <button
                      type="button"
                      onClick={() => setCandidateFilter('all')}
                      className="mt-1.5 text-[11px] text-white/45 hover:text-white/75"
                    >
                      {language === 'en'
                        ? `${(runDetail.summary.universeCount || 1) - 1} other candidates were not selected. View rejection reasons.`
                        : `其余 ${(runDetail.summary.universeCount || 1) - 1} 个候选未入选，查看淘汰原因`}
                    </button>
                  ) : null}
                </div>
              ) : null}

              {runDetail && hasCandidateDiagnostics ? (
                <div className="shrink-0 border-b border-white/5 px-3 py-2" data-testid="scanner-candidate-filters">
                  <div className="flex w-fit max-w-full gap-1 overflow-x-auto rounded-lg border border-white/5 bg-black/30 p-0.5 no-scrollbar" role="group" aria-label={language === 'en' ? 'Candidate diagnostics filter' : '候选诊断过滤'}>
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
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}

              <div className="flex shrink-0 flex-col gap-2 border-b border-white/5 px-3 py-2 lg:flex-row lg:items-center lg:justify-between">
                <div className="flex w-fit rounded-lg border border-white/5 bg-black/30 p-0.5" role="group" aria-label={language === 'en' ? 'Result view mode' : '结果视图'}>
                  <button
                    type="button"
                    onClick={() => setViewMode('cards')}
                    disabled={!selectedOnlyView}
                    className={`inline-flex items-center gap-2 rounded-md px-2.5 py-1 text-xs ${viewMode === 'cards' && selectedOnlyView ? 'bg-white/10 text-white' : 'text-white/45 hover:text-white/75'} disabled:cursor-not-allowed disabled:opacity-35`}
                  >
                    <LayoutGrid className="h-3.5 w-3.5" />
                    {language === 'en' ? 'Card view' : '卡片视图'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setViewMode('table')}
                    className={`inline-flex items-center gap-2 rounded-md px-2.5 py-1 text-xs ${viewMode === 'table' ? 'bg-white/10 text-white' : 'text-white/45 hover:text-white/75'}`}
                  >
                    <Table2 className="h-3.5 w-3.5" />
                    {language === 'en' ? 'Table view' : '表格视图'}
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

              <div data-testid="scanner-candidate-scroll-region" className="min-h-0 flex-1 overflow-y-auto px-3 py-3 no-scrollbar">
                {!selectedOnlyView ? (
                  filteredDiagnosticCandidates.length ? (
                    <div data-testid="scanner-candidate-diagnostics-table" className="space-y-1.5">
                      {filteredDiagnosticCandidates.map((candidate) => {
                        const activeRunDetail = runDetail as ScannerRunDetail;
                        const diagnosticCandidate = diagnosticToCandidate(candidate);
                        const candidateMarket = normalizeScannerMarket(activeRunDetail.market || market);
                        const candidateIdentity = getWatchlistIdentity(candidateMarket, candidate.symbol);
                        const isTracked = Boolean(candidateIdentity && trackedWatchlistIdentitySet.has(candidateIdentity));
                        const isTrackPending = pendingWatchlistIdentity === candidateIdentity;
                        const backtestHref = buildScannerBacktestPath(diagnosticCandidate, activeRunDetail, language);
                        const isExpanded = expandedSymbol === candidate.symbol;
                        const metricItems = Object.entries(candidate.metrics || {}).slice(0, 8);
                        return (
                          <article
                            key={`diagnostic-${candidate.symbol}`}
                            data-testid={`scanner-candidate-row-${candidate.symbol}`}
                            className="rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2 text-sm backdrop-blur-md transition-all hover:border-white/10"
                          >
                            <div
                              role="button"
                              tabIndex={0}
                              className="grid w-full min-w-0 grid-cols-1 items-center gap-2 text-left md:grid-cols-[minmax(150px,0.9fr)_minmax(180px,1fr)_minmax(220px,1.3fr)]"
                              onClick={() => setExpandedSymbol(isExpanded ? null : candidate.symbol)}
                              onKeyDown={(event) => {
                                if (event.key === 'Enter' || event.key === ' ') {
                                  event.preventDefault();
                                  setExpandedSymbol(isExpanded ? null : candidate.symbol);
                                }
                              }}
                              aria-expanded={isExpanded}
                            >
                              <span className="min-w-0">
                                <span className="flex min-w-0 items-center gap-2">
                                  <span className={`inline-flex shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-[0.12em] ${diagnosticStatusClass(candidate.status)}`}>
                                    {diagnosticStatusLabel(candidate.status, language)}
                                  </span>
                                  {candidate.rank ? <span className="font-mono text-[11px] text-white/35">#{candidate.rank}</span> : null}
                                  <span className="min-w-0 truncate font-mono text-sm font-semibold text-white">{candidate.symbol}</span>
                                </span>
                                <span className="mt-1 flex min-w-0 gap-1.5 text-[11px] text-white/36">
                                  <span className="min-w-0 truncate">{candidate.name || candidate.symbol}</span>
                                  <span className="shrink-0 text-white/20">/</span>
                                  <span className="min-w-0 truncate">{candidate.provider || '--'}</span>
                                </span>
                              </span>
                              <span className="flex min-w-0 flex-wrap items-center gap-1.5">
                                <FieldChip label={language === 'en' ? 'Score' : '评分'} value={candidate.score == null ? '--' : `${candidate.score}/100`} />
                                <FieldChip label="20D" value={diagnosticMetricValue(candidate, 'return_20d')} />
                                <FieldChip label={language === 'en' ? 'Trend' : '趋势'} value={diagnosticMetricValue(candidate, 'trend')} />
                              </span>
                              <span className="flex min-w-0 flex-col gap-1 md:items-end">
                                <span className="w-full min-w-0 truncate text-xs text-white/58 md:text-right" title={getDiagnosticReason(candidate, language)}>
                                  {getDiagnosticReason(candidate, language)}
                                </span>
                                <span className="flex max-w-full flex-wrap gap-1.5 md:justify-end">
                                  <ActionButton
                                    label={language === 'en' ? 'Analyze' : '分析'}
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      void handleAnalyzeCandidate(diagnosticCandidate);
                                    }}
                                    disabled={pendingAnalyzeSymbol === candidate.symbol}
                                    variant="primary"
                                  />
                                  <ActionButton
                                    label={getWatchlistActionLabel(isTracked, isTrackPending, watchlistAuthBlocked, language)}
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      void handleTrackCandidate(diagnosticCandidate);
                                    }}
                                    disabled={isTracked || isTrackPending || watchlistAuthBlocked}
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
                                    label={language === 'en' ? 'Backtest' : '回测'}
                                    onClick={(event) => {
                                      event.stopPropagation();
                                    }}
                                    href={backtestHref || undefined}
                                    disabled={!backtestHref}
                                    title={!backtestHref ? backtestUnavailableLabel : undefined}
                                  />
                                </span>
                              </span>
                            </div>
                            {isExpanded ? (
                              <div data-testid={`scanner-candidate-detail-${candidate.symbol}`} className="mt-2 grid gap-2 border-t border-white/5 pt-2 text-xs text-white/58 md:grid-cols-3">
                                <DetailSection title={language === 'en' ? 'Rule result' : '规则结果'}>
                                  <NotesList
                                    notes={[
                                      getDiagnosticReason(candidate, language),
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
                    <div className="grid grid-cols-1 gap-2.5 xl:grid-cols-2">
                    {sortedCandidates.map((candidate) => {
                      const isExpanded = expandedSymbol === candidate.symbol;
                      const candidateIdentity = getCandidateIdentity(candidate);
                      const candidateWatchlistIdentity = getWatchlistIdentity(runDetail?.market || market, candidate.symbol);
                      const isTracked = trackedWatchlistIdentitySet.has(candidateWatchlistIdentity);
                      const isTrackPending = pendingWatchlistIdentity === candidateWatchlistIdentity;
                      const backtestHref = buildScannerBacktestPath(candidate, runDetail, language);
                      const entryRange = getEntryRange(candidate);
                      const targetPrice = getTargetPrice(candidate);
                      const stopLoss = getStopLoss(candidate);
                      const sourceBadge = getSourceBadge(candidate, runDetail, language);
                      return (
                        <article
                          key={`watchlist-${candidateIdentity}`}
                          data-testid={`scanner-result-card-${candidateIdentity}`}
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
                              onClick={() => setExpandedSymbol(isExpanded ? null : candidate.symbol)}
                              className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-white/8 bg-white/[0.04] px-2.5 py-1 text-xs text-white/65 hover:bg-white/[0.08]"
                            >
                              {language === 'en' ? 'Detail' : '详情'}
                              {isExpanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
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
                              <ActionButton
                                label={language === 'en' ? 'Backtest' : '回测'}
                                icon={<TestTubeDiagonal className="h-3.5 w-3.5" />}
                                href={backtestHref || undefined}
                                disabled={!backtestHref}
                                title={!backtestHref ? backtestUnavailableLabel : undefined}
                              />
                            </div>
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
                              isAnalyzing={pendingAnalyzeSymbol === candidate.symbol}
                              isCopied={copiedKey === `candidate:${candidate.symbol}`}
                              isTracked={isTracked}
                              isTrackPending={isTrackPending}
                              isWatchlistAuthBlocked={watchlistAuthBlocked}
                              backtestActionLabel={backtestUnavailableLabel}
                              backtestHref={backtestHref}
                            />
                          ) : null}
                        </article>
                      );
                    })}
                  </div>
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
                          const backtestHref = buildScannerBacktestPath(candidate, runDetail, language);
                          return (
                            <React.Fragment key={`table-${candidateIdentity}`}>
                              <tr
                                data-testid={`scanner-result-row-${candidateIdentity}`}
                                className="cursor-pointer border-b border-white/5 text-white/72 hover:bg-white/[0.035]"
                                onClick={() => setExpandedSymbol(isExpanded ? null : candidate.symbol)}
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
                                      label={language === 'en' ? 'Backtest' : '回测'}
                                      onClick={(event) => {
                                        event.stopPropagation();
                                      }}
                                      href={backtestHref || undefined}
                                      disabled={!backtestHref}
                                      title={!backtestHref ? backtestUnavailableLabel : undefined}
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
                                      isAnalyzing={pendingAnalyzeSymbol === candidate.symbol}
                                      isCopied={copiedKey === `candidate:${candidate.symbol}`}
                                      isTracked={isTracked}
                                      isTrackPending={isTrackPending}
                                      isWatchlistAuthBlocked={watchlistAuthBlocked}
                                      backtestActionLabel={backtestUnavailableLabel}
                                      backtestHref={backtestHref}
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

                {runDetail ? <DiagnosticsPanel runDetail={runDetail} language={language} /> : null}
              </div>
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
