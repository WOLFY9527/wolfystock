import React, { Suspense, lazy } from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowDownUp,
  BookmarkPlus,
  ChevronDown,
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
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { analysisApi, DuplicateTaskError } from '../api/analysis';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { scannerApi } from '../api/scanner';
import { watchlistApi } from '../api/watchlist';
import {
  ScannerBacktestLab,
} from '../components/scanner/ScannerBacktestLab';
import { ScannerActionButton as ActionButton } from '../components/scanner/ScannerActionButton';
import {
  ScannerCandidateCard,
  ScannerCandidateDetailPanel,
  ScannerCandidateDiagnosticRow,
  ScannerCandidateInspector,
  ScannerCandidateTableRow,
} from '../components/scanner/ScannerCandidatePresenters';
import {
  AdvancedDisclosure,
  FieldChip,
} from '../components/scanner/ScannerDisplayAtoms';
import { ScannerStrategySimulationPanelFallback } from '../components/scanner/ScannerStrategySimulationPanelFallback';
import {
  ScannerHistoryDrawer,
  type ScannerHistoryDrawerItem,
} from '../components/scanner/ScannerHistoryDrawer';
import {
  ScannerDiagnosticsPanel,
} from '../components/scanner/ScannerDiagnosticsPanel';
import {
  useScannerBacktestLab,
  type ScannerBacktestItem,
} from '../components/scanner/useScannerBacktestLab';
import { SectionShell } from '../components/common';
import {
  TerminalButton,
  TerminalChip,
  TerminalEmptyState,
  TerminalGrid,
  TerminalNestedBlock,
  TerminalPageHeading,
  TerminalPageShell,
  TerminalPanel,
} from '../components/terminal';
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
  ScannerLabeledValue,
  ScannerReviewSummary,
  ScannerRunDetail,
  ScannerRunHistoryItem,
  ScannerStrategySimulationResult,
  ScannerThemeSuggestion,
  ScannerTheme,
  ScannerWatchlistComparison,
} from '../types/scanner';
import type { WatchlistItem } from '../types/watchlist';
import { buildLocalizedPath } from '../utils/localeRouting';
import { normalizeScannerEvidence } from '../utils/evidenceDisplay';
import { sanitizeUserFacingDataIssue } from '../utils/userFacingDataIssues';
import {
  getScannerDetailOptions,
  getScannerProfileOptions,
  getScannerUniverseOptions,
  SCANNER_PROFILE_DEFAULTS,
} from './scannerPageShared';

const LazyScannerStrategySimulationPanel = lazy(async () => {
  const module = await import('../components/scanner/ScannerStrategySimulationPanel');
  return { default: module.ScannerStrategySimulationPanel };
});

const {
  formatProviderDiagnostics,
  getProviderDiagnostics,
  getRunCoverageSummary,
  getRunProviderDiagnostics,
  hasRunDiagnosticsContent,
} = ScannerDiagnosticsPanel;

const HISTORY_PAGE_SIZE = 8;

type PillOption = { value: string; label: string };
type ViewMode = 'cards' | 'table';
type CandidateFilter = 'selected' | 'pool' | 'rejected' | 'data_failed' | 'all';
type SortKey = 'score' | 'symbol' | 'target' | 'risk';
type SortDirection = 'asc' | 'desc';
type ScanScope = 'default' | 'theme' | 'symbols';
type ActionNotice = { tone: 'success' | 'warning' | 'danger'; message: string } | null;
type ScannerComparisonState = {
  previousRun: ScannerRunDetail | null;
  bySymbol: Map<string, CandidateComparison>;
  chips: string[];
};
type CandidateComparison = {
  scoreDelta: number | null;
  rankDelta: number | null;
  previousStatus: ScannerCandidateDiagnosticStatus | null;
  currentStatus: ScannerCandidateDiagnosticStatus;
  label: string;
};
type ScannerRunSummary = {
  title: string;
  statusLabel: string;
  bestCandidate: string;
  candidateCount: number;
  rejectedCount: number;
  failedCount: number;
  dataStatusLabel: string;
  durationLabel: string;
  runTimeLabel: string;
  errorSummary: string | null;
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

function normalizeLabel(label?: string | null): string {
  return (label || '').trim().toLowerCase();
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function getScannerEvidencePayload(candidate: ScannerCandidate | ScannerCandidateDiagnostic): Record<string, unknown> | null {
  const containers = [
    isRecord((candidate as ScannerCandidate).diagnostics) ? (candidate as ScannerCandidate).diagnostics : null,
    isRecord((candidate as ScannerCandidateDiagnostic).metadata) ? (candidate as ScannerCandidateDiagnostic).metadata : null,
  ].filter((value): value is Record<string, unknown> => Boolean(value));

  for (const container of containers) {
    if (isRecord(container.evidence_packet) || isRecord(container.evidencePacket)) {
      return container;
    }
  }

  return null;
}

function getScannerEvidenceSummary(candidate: ScannerCandidate | ScannerCandidateDiagnostic) {
  const payload = getScannerEvidencePayload(candidate);
  return payload ? normalizeScannerEvidence(payload) : null;
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

function formatDurationMs(startedAt?: string | null, completedAt?: string | null): string {
  if (!startedAt || !completedAt) return '--';
  const started = new Date(startedAt).getTime();
  const completed = new Date(completedAt).getTime();
  if (!Number.isFinite(started) || !Number.isFinite(completed) || completed < started) return '--';
  const durationMs = completed - started;
  if (durationMs < 1000) return `${durationMs}ms`;
  const seconds = Math.round(durationMs / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}m ${remainingSeconds}s`;
}

function normalizeRunState(value?: string | null): string {
  return String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
}

function compactScannerStateLabel(value?: string | null, language: 'zh' | 'en' = 'zh'): string {
  const normalized = normalizeRunState(value);
  if (['success', 'succeeded', 'completed', 'complete', 'ready'].includes(normalized)) return language === 'en' ? 'Completed' : '完成';
  if (['failed', 'failure', 'error', 'data_failed'].includes(normalized)) return language === 'en' ? 'Failed' : '失败';
  if (normalized === 'timeout' || normalized === 'timed_out' || normalized.includes('timeout')) return language === 'en' ? 'Timeout' : '超时';
  if (['empty', 'no_candidates', 'no_candidate', 'no_shortlist'].includes(normalized)) return language === 'en' ? 'No candidates' : '无候选';
  if (['insufficient_data', 'data_insufficient', 'not_enough_history', 'missing_history'].includes(normalized)) return language === 'en' ? 'Insufficient data' : '数据不足';
  if (['provider_down', 'provider_error', 'provider_failed', 'data_source_error'].includes(normalized)) return language === 'en' ? 'External data unavailable' : '部分外部数据暂不可用';
  if (['local_data', 'local', 'local_cache', 'local_snapshot'].includes(normalized)) return language === 'en' ? 'Local data' : '本地数据';
  if (['fallback', 'fallback_data', 'degraded'].includes(normalized)) return language === 'en' ? 'Fallback data' : '备用数据';
  if (['partial', 'partial_data', 'partial_success'].includes(normalized)) return language === 'en' ? 'Partial data' : '部分数据';
  if (!normalized || normalized === 'unknown') return language === 'en' ? 'Unconfirmed' : '未确认';
  return language === 'en' ? 'Unconfirmed' : '未确认';
}

function sanitizeScannerErrorSummary(value?: string | null, language: 'zh' | 'en' = 'zh'): string | null {
  const normalized = normalizeRunState(value);
  if (!normalized) return null;
  if (normalized.includes('timeout')) return language === 'en' ? 'Timeout' : '超时';
  if (String(value || '').includes('超时')) return language === 'en' ? 'Timeout' : '超时';
  if (normalized.includes('provider')) return language === 'en' ? 'External data unavailable' : '部分外部数据暂不可用';
  if (normalized.includes('history') || normalized.includes('missing') || normalized.includes('insufficient') || normalized.includes('not_enough')) {
    return language === 'en' ? 'Insufficient data' : '数据不足';
  }
  if (String(value || '').includes('不可用') || String(value || '').includes('缺失') || String(value || '').includes('不足')) {
    return language === 'en' ? 'Insufficient data' : '数据不足';
  }
  if (normalized.includes('candidate') || normalized.includes('shortlist') || normalized === 'empty') return language === 'en' ? 'No candidates' : '无候选';
  if (normalized.includes('fallback')) return language === 'en' ? 'Fallback data' : '备用数据';
  if (normalized.includes('local')) return language === 'en' ? 'Local data' : '本地数据';
  if (normalized.includes('partial')) return language === 'en' ? 'Partial data' : '部分数据';
  if (normalized.includes('failed') || normalized.includes('error')) return language === 'en' ? 'Failed' : '失败';
  return compactScannerStateLabel(value, language);
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

function isInternalScannerIssue(value?: string | null): boolean {
  const normalized = normalizeRunState(value);
  if (!normalized) return false;
  return /provider|timeout|schema|debug|raw|trace|cache|not_enough|unavailable|missing|insufficient|data_failed|technical_indicators|fundamentals|earnings|optional_news/.test(normalized);
}

function sanitizeScannerUserText(value: string | null | undefined, language: 'zh' | 'en', fallback: string): string {
  const text = String(value || '').trim();
  if (!text) return fallback;
  return isInternalScannerIssue(text) ? sanitizeUserFacingDataIssue(text, language) : text;
}

function sanitizeScannerNotes(notes: Array<string | null | undefined>, language: 'zh' | 'en'): string[] {
  return notes
    .filter((item): item is string => Boolean(String(item || '').trim()))
    .map((item) => sanitizeScannerUserText(item, language, ''))
    .filter((item, index, array) => Boolean(item) && array.indexOf(item) === index);
}

function sanitizeScannerLabeledValues(items: ScannerLabeledValue[] | undefined, language: 'zh' | 'en'): ScannerLabeledValue[] {
  return (items || []).map((item) => {
    const labelHasInternalDetail = isInternalScannerIssue(item.label);
    const valueHasInternalDetail = isInternalScannerIssue(item.value);
    if (!labelHasInternalDetail && !valueHasInternalDetail) {
      return item;
    }
    return {
      label: language === 'en' ? 'Data note' : '数据说明',
      value: sanitizeUserFacingDataIssue(`${item.label} ${item.value}`, language),
    };
  });
}

function getRiskSummary(candidate: ScannerCandidate, language: 'zh' | 'en'): string {
  return sanitizeScannerUserText(
    candidate.riskNotes?.[0] || candidate.aiInterpretation?.riskInterpretation,
    language,
    language === 'en' ? 'No risk note provided' : '未提供风险说明',
  );
}

function getKeyReason(candidate: ScannerCandidate, runDetail: ScannerRunDetail | null, language: 'zh' | 'en'): string {
  return sanitizeScannerUserText(
    candidate.reasonSummary
    || candidate.reasons?.[0]
    || candidate.featureSignals?.[0]?.value
    || runDetail?.scoringNotes?.[0],
    language,
    language === 'en' ? 'No selection note provided' : '未提供入选说明',
  );
}

function getSourceBadge(candidate: ScannerCandidate, runDetail: ScannerRunDetail | null, language: 'zh' | 'en'): string | null {
  const candidateProvider = getProviderDiagnostics(candidate.diagnostics)?.quoteSourceUsed
    || getProviderDiagnostics(candidate.diagnostics)?.snapshotSourceUsed
    || getProviderDiagnostics(candidate.diagnostics)?.historySourceUsed;
  const runProvider = runDetail ? getRunProviderDiagnostics(runDetail)?.quoteSourceUsed
    || getRunProviderDiagnostics(runDetail)?.snapshotSourceUsed
    || getRunProviderDiagnostics(runDetail)?.historySourceUsed : null;
  const friendly = formatFriendlyProvider(candidateProvider || runProvider || runDetail?.sourceSummary || null, language);
  return friendly === '--' ? (language === 'en' ? 'Data ready for observation' : '数据可用于观察') : friendly;
}

function getRunSummaryCount(runDetail: ScannerRunDetail, key: keyof NonNullable<ScannerRunDetail['summary']>, fallback = 0): number {
  const value = runDetail.summary?.[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function getRunBestCandidate(runDetail: ScannerRunDetail, language: 'zh' | 'en'): string {
  const best = runDetail.shortlist?.[0] || runDetail.selected?.[0] || null;
  if (!best) return language === 'en' ? 'None' : '暂无';
  const score = best.score != null && Number.isFinite(best.score) ? ` · ${best.score}/100` : '';
  return `${normalizeCandidateSymbol(best.symbol) || best.symbol || '--'}${score}`;
}

function getRunDataStatusLabel(runDetail: ScannerRunDetail, language: 'zh' | 'en'): string {
  const provider = getRunProviderDiagnostics(runDetail);
  const status = normalizeRunState(runDetail.status);
  const failureReason = normalizeRunState(runDetail.failureReason);
  const failedCount = getRunSummaryCount(runDetail, 'dataFailedCount', 0) + getRunSummaryCount(runDetail, 'errorCount', 0);
  const selectedCount = getRunSummaryCount(runDetail, 'selectedCount', runDetail.shortlist?.length || 0);
  const providerText = [
    provider?.fallbackOccurred ? 'fallback' : null,
    provider?.providerFailureCount ? 'provider_error' : null,
    provider?.missingDataSymbolCount ? 'partial' : null,
    provider?.quoteSourceUsed,
    provider?.snapshotSourceUsed,
    provider?.historySourceUsed,
  ].filter(Boolean).join(' ');
  const text = normalizeRunState([status, failureReason, providerText].join(' '));
  if (status === 'empty' || selectedCount === 0 && runDetail.status === 'empty') return compactScannerStateLabel('no_candidates', language);
  if (failedCount > 0 && provider?.providerFailureCount) return compactScannerStateLabel('provider_error', language);
  if (failedCount > 0) return compactScannerStateLabel('insufficient_data', language);
  if (text.includes('provider_error') || text.includes('provider_down')) return compactScannerStateLabel('provider_error', language);
  if (text.includes('fallback')) return compactScannerStateLabel('fallback', language);
  if (text.includes('local')) return compactScannerStateLabel('local_data', language);
  if (text.includes('partial')) return compactScannerStateLabel('partial', language);
  if (status === 'failed' || status === 'error') return compactScannerStateLabel('failed', language);
  if (status === 'completed' || status === 'success') return language === 'en' ? 'Verified' : '已验证';
  return compactScannerStateLabel('unknown', language);
}

function buildScannerRunSummary(
  title: string,
  runDetail: ScannerRunDetail | null,
  language: 'zh' | 'en',
): ScannerRunSummary | null {
  if (!runDetail) return null;
  const selectedCount = getRunSummaryCount(runDetail, 'selectedCount', runDetail.shortlist?.length || 0);
  const rejectedCount = getRunSummaryCount(runDetail, 'rejectedCount', Math.max(0, (runDetail.evaluatedSize || 0) - selectedCount));
  const failedCount = getRunSummaryCount(runDetail, 'dataFailedCount', 0) + getRunSummaryCount(runDetail, 'errorCount', 0);
  return {
    title,
    statusLabel: compactScannerStateLabel(runDetail.status, language),
    bestCandidate: getRunBestCandidate(runDetail, language),
    candidateCount: selectedCount,
    rejectedCount,
    failedCount,
    dataStatusLabel: getRunDataStatusLabel(runDetail, language),
    durationLabel: formatDurationMs(runDetail.runAt, runDetail.completedAt),
    runTimeLabel: formatTimestamp(runDetail.runAt || runDetail.completedAt, language),
    errorSummary: sanitizeScannerErrorSummary(runDetail.failureReason, language),
  };
}

function buildHistoryItemSummary(
  title: string,
  item: ScannerRunHistoryItem | null,
  language: 'zh' | 'en',
): ScannerRunSummary | null {
  if (!item) return null;
  const failedCount = item.status === 'failed' ? 1 : 0;
  return {
    title,
    statusLabel: compactScannerStateLabel(item.status, language),
    bestCandidate: item.topSymbols?.[0] || (language === 'en' ? 'None' : '暂无'),
    candidateCount: item.shortlistSize || item.topSymbols?.length || 0,
    rejectedCount: Math.max(0, (item.evaluatedSize || 0) - (item.shortlistSize || item.topSymbols?.length || 0)),
    failedCount,
    dataStatusLabel: sanitizeScannerErrorSummary(item.failureReason, language) || compactScannerStateLabel(item.status === 'empty' ? 'no_candidates' : item.status, language),
    durationLabel: formatDurationMs(item.runAt, item.completedAt),
    runTimeLabel: formatTimestamp(item.runAt || item.completedAt, language),
    errorSummary: sanitizeScannerErrorSummary(item.failureReason, language),
  };
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
  if (normalized.includes('provider down') || normalized.includes('provider error') || normalized.includes('provider failed')) return compactScannerStateLabel('provider_error', language);
  if (normalized === 'unknown') return compactScannerStateLabel('unknown', language);
  if (normalized.includes('fallback')) return compactScannerStateLabel('fallback', language);
  if (normalized.includes('local db') || normalized.includes('local')) return language === 'en' ? 'Local data' : '本地数据';
  return language === 'en' ? 'External data available' : '外部数据可用';
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
  if (candidate.status === 'data_failed' || candidate.status === 'error') return sanitizeUserFacingDataIssue(text || rawReason, language);
  if (/provider|timeout|missing|history|quote|data|field|not enough|unavailable/.test(text)) return sanitizeUserFacingDataIssue(text || rawReason, language);
  if (/liquidity|volume|turnover|amount/.test(text)) return language === 'en' ? 'Liquidity weak' : '流动性不足';
  if (/price/.test(text)) return language === 'en' ? 'Price below threshold' : '价格低于阈值';
  if (/momentum|relative strength|strength|return/.test(text)) return language === 'en' ? 'Momentum weak' : '动量不足';
  if (/trend|moving average|breakout|\bma\b/.test(text)) return language === 'en' ? 'Trend weak' : '趋势不足';
  if (/score|threshold|rank/.test(text)) return language === 'en' ? 'Score below threshold' : '分数低于阈值';
  if (/passed/.test(normalizeDiagnosticText(rawReason))) return language === 'en' ? 'Passed screening' : '通过筛选';
  return language === 'en' ? 'Screening condition not met' : '未达到筛选条件';
}

function formatCandidateDataQuality(candidate: ScannerCandidateDiagnostic, language: 'zh' | 'en'): string {
  const status = normalizeDiagnosticStatus(candidate.status);
  const text = [
    candidate.reason,
    ...(candidate.failedRules || []),
    ...(candidate.missingFields || []),
  ].map(normalizeDiagnosticText).join(' ');
  if (/quote|realtime|snapshot/.test(text)) return sanitizeUserFacingDataIssue(text || 'data_missing', language);
  if (status === 'data_failed' || status === 'error' || /provider|timeout|missing|history|data|field|not enough|unavailable/.test(text)) {
    return sanitizeUserFacingDataIssue(text || candidate.reason, language);
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
      ? (language === 'en' ? 'Data status: partial data missing' : '数据状态：部分数据缺失')
      : (language === 'en' ? 'Data status: enough for observation' : '数据状态：可用于观察'),
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
    source !== '--' ? (language === 'en' ? `${source}; verify freshness` : `${source}，需确认实时性`) : null,
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
    const rankDelta = previous?.rank != null && candidate.rank != null ? previous.rank - candidate.rank : null;
    let label = previous
      ? (language === 'en' ? 'Still a candidate' : '连续候选')
      : (language === 'en' ? 'First seen' : '首次出现');
    if (!previous) {
      label = isOfficialSelected(candidate)
        ? (language === 'en' ? 'New candidate' : '新晋候选')
        : (language === 'en' ? 'First seen' : '首次出现');
    } else if (previousStatus === 'selected' && currentStatus === 'selected') {
      label = language === 'en' ? 'Retained selected' : '连续入选';
    } else if (previousStatus === 'selected' && currentStatus !== 'selected') {
      label = language === 'en' ? 'Selected last run' : '上次入选';
    } else if (previousStatus !== 'selected' && currentStatus === 'selected') {
      label = language === 'en' ? 'Failed last run' : '上次未通过';
    } else if (rankDelta != null && rankDelta > 0) {
      label = language === 'en' ? 'Rank up' : '排名上升';
    } else if (rankDelta != null && rankDelta < 0) {
      label = language === 'en' ? 'Rank down' : '排名下降';
    } else if (scoreDelta != null && scoreDelta > 0) {
      label = language === 'en' ? 'Score up' : '评分上升';
    } else if (scoreDelta != null && scoreDelta < 0) {
      label = language === 'en' ? 'Score down' : '评分下降';
    } else if (isPreviewSelected(candidate, threshold) && !isPreviewSelected(previous, threshold)) {
      label = language === 'en' ? 'New preview selected' : '新预览入选';
    } else if (!isPreviewSelected(candidate, threshold) && isPreviewSelected(previous, threshold)) {
      label = language === 'en' ? 'Preview dropped' : '预览转淘汰';
    }
    bySymbol.set(symbol, { scoreDelta, rankDelta, previousStatus, currentStatus, label });
  });

  currentCandidates.slice(0, 8).forEach((candidate) => {
    const symbol = normalizeCandidateSymbol(candidate.symbol);
    const comparison = symbol ? bySymbol.get(symbol) : null;
    if (!symbol || !comparison) return;
    const delta = formatScoreDelta(comparison.scoreDelta);
    chips.push([symbol, comparison.label, delta ? (language === 'en' ? `score ${delta}` : `分数 ${delta}`) : null].filter(Boolean).join(' · '));
  });
  previousBySymbol.forEach((_previous, symbol) => {
    if (!symbol || currentCandidates.some((candidate) => normalizeCandidateSymbol(candidate.symbol) === symbol)) return;
    chips.push(`${symbol} · ${language === 'en' ? 'Dropped candidate' : '移出候选'}`);
  });

  return { previousRun, bySymbol, chips: chips.slice(0, 8) };
}

function buildRunComparisonHighlights(
  currentRun: ScannerRunDetail | null,
  previousRun: ScannerRunDetail | null,
  comparisonState: ScannerComparisonState,
  language: 'zh' | 'en',
): ScannerLabeledValue[] {
  if (!currentRun || !previousRun) return [];
  const currentCount = getRunSummaryCount(currentRun, 'selectedCount', currentRun.shortlist?.length || 0);
  const previousCount = getRunSummaryCount(previousRun, 'selectedCount', previousRun.shortlist?.length || 0);
  const currentBest = normalizeCandidateSymbol(currentRun.shortlist?.[0]?.symbol);
  const previousBest = normalizeCandidateSymbol(previousRun.shortlist?.[0]?.symbol);
  const currentScore = currentRun.shortlist?.[0]?.score;
  const previousScore = previousRun.shortlist?.[0]?.score;
  const scoreDelta = currentScore != null && previousScore != null ? Math.round(currentScore - previousScore) : null;
  const currentDataStatus = getRunDataStatusLabel(currentRun, language);
  const previousDataStatus = getRunDataStatusLabel(previousRun, language);
  const items: ScannerLabeledValue[] = [];

  const countDelta = currentCount - previousCount;
  if (countDelta > 0) {
    items.push({ label: language === 'en' ? 'Candidates' : '候选增加', value: `+${countDelta}` });
  } else if (countDelta < 0) {
    items.push({ label: language === 'en' ? 'Candidates' : '候选减少', value: String(countDelta) });
  }
  if (currentBest && previousBest && currentBest !== previousBest) {
    items.push({ label: language === 'en' ? 'Best changed' : '最佳候选变化', value: `${previousBest} -> ${currentBest}` });
  }
  if (scoreDelta != null && scoreDelta !== 0) {
    items.push({ label: language === 'en' ? 'Score' : '分数变化', value: formatScoreDelta(scoreDelta) || '0' });
  }
  if (currentDataStatus !== previousDataStatus) {
    items.push({ label: language === 'en' ? 'Data status' : '数据状态变化', value: `${previousDataStatus} -> ${currentDataStatus}` });
  }
  if (normalizeRunState(currentRun.status) === 'failed') {
    items.push({ label: language === 'en' ? 'Run state' : '运行状态', value: language === 'en' ? 'Run failed' : '运行失败' });
  } else if (currentCount === 0) {
    items.push({ label: language === 'en' ? 'Run state' : '运行状态', value: language === 'en' ? 'No candidates' : '无候选' });
  } else if (currentDataStatus === (language === 'en' ? 'Insufficient data' : '数据不足')) {
    items.push({ label: language === 'en' ? 'Run state' : '运行状态', value: language === 'en' ? 'Insufficient data' : '数据不足' });
  }
  comparisonState.chips.slice(0, 3).forEach((chip) => {
    items.push({ label: language === 'en' ? 'Candidate' : '候选变化', value: chip });
  });
  return items.slice(0, 8);
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
              className={isActive
                ? isMarketGroup
                  ? 'min-w-0 shrink-0 rounded-lg bg-white/10 px-4 py-1 text-sm font-bold text-white shadow-[0_2px_10px_rgba(0,0,0,0.5)] transition-all'
                  : 'min-w-0 rounded-full border border-white/10 bg-white/10 px-3 py-1 text-xs text-white transition-colors'
                : isMarketGroup
                  ? 'min-w-0 shrink-0 rounded-lg bg-transparent px-4 py-1 text-sm font-medium text-white/40 transition-all hover:text-white/70'
                  : 'min-w-0 rounded-full border border-white/5 bg-transparent px-3 py-1 text-xs text-white/50 transition-colors hover:bg-white/[0.05]'}
              onClick={() => onChange(option.value)}
            >
              <span className="ui-truncate block max-w-full">{option.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function ScannerResultHistorySummary({
  currentSummary,
  recentSummary,
  previousSummary,
  comparisonItems,
  hasHistory,
  language,
}: {
  currentSummary: ScannerRunSummary | null;
  recentSummary: ScannerRunSummary | null;
  previousSummary: ScannerRunSummary | null;
  comparisonItems: ScannerLabeledValue[];
  hasHistory: boolean;
  language: 'zh' | 'en';
}) {
  const visibleSummaries = [currentSummary, recentSummary, previousSummary]
    .filter((item, index, array): item is ScannerRunSummary => Boolean(item) && array.findIndex((other) => other?.title === item?.title) === index);

  return (
    <section data-testid="scanner-result-history-summary" className="shrink-0 border-b border-white/5 px-3 py-2">
      <TerminalPanel dense className="grid gap-2 p-2.5">
        <div className="flex min-w-0 items-center justify-between gap-2">
          <div className="min-w-0">
            <h3 className="truncate text-[10px] font-bold uppercase tracking-widest text-white/40">{language === 'en' ? 'Result history' : '结果历史'}</h3>
            <p className="mt-0.5 truncate text-[11px] text-white/42">{language === 'en' ? 'Current run, latest run, and previous comparable run' : '本次扫描、最近扫描与上次扫描对比'}</p>
          </div>
        </div>
        {visibleSummaries.length ? (
          <div className="grid gap-2 xl:grid-cols-3">
            {visibleSummaries.map((summary) => (
              <TerminalNestedBlock key={summary.title} className="min-w-0 p-2.5" data-testid={`scanner-run-summary-${summary.title}`}>
                <div className="flex min-w-0 items-center justify-between gap-2">
                  <span className="truncate text-[10px] font-bold uppercase tracking-widest text-white/40">{summary.title}</span>
                  <TerminalChip variant="neutral" className="shrink-0 px-1.5 py-0.5 text-[10px] font-sans text-white/62">{summary.statusLabel}</TerminalChip>
                </div>
                <div className="mt-2 grid grid-cols-2 gap-1.5 text-[11px] sm:grid-cols-3">
                  <FieldChip label="最佳候选" value={summary.bestCandidate} />
                  <FieldChip label="候选数量" value={String(summary.candidateCount)} />
                  <FieldChip label="淘汰数量" value={String(summary.rejectedCount)} />
                  <FieldChip label="失败数量" value={String(summary.failedCount)} />
                  <FieldChip label="数据状态" value={summary.dataStatusLabel} />
                  <FieldChip label="耗时" value={summary.durationLabel} />
                </div>
                <p className="mt-2 truncate text-[11px] text-white/42">
                  运行时间：<span className="font-mono text-white/58">{summary.runTimeLabel}</span>
                  {summary.errorSummary ? <span className="text-rose-200/80"> · {summary.errorSummary}</span> : null}
                </p>
              </TerminalNestedBlock>
            ))}
          </div>
        ) : null}
        {!hasHistory && !currentSummary ? (
          <TerminalEmptyState data-testid="scanner-history-empty-state" title={language === 'en' ? 'No scan history yet' : '暂无历史扫描'} className="min-h-[64px] px-3 py-2">
            {language === 'en' ? 'Run one scan to compare results.' : '运行一次扫描后可查看对比'}
          </TerminalEmptyState>
        ) : null}
        {currentSummary && !previousSummary ? (
          <TerminalEmptyState data-testid="scanner-previous-empty-state" className="min-h-[56px] px-3 py-2">
            {language === 'en' ? 'No previous scan · run once more to compare.' : '暂无历史扫描 · 运行一次扫描后可查看对比'}
          </TerminalEmptyState>
        ) : null}
        {comparisonItems.length ? (
          <div data-testid="scanner-run-comparison-compact" className="flex min-w-0 flex-wrap gap-1.5">
            {comparisonItems.map((item) => (
              <FieldChip key={`${item.label}-${item.value}`} label={item.label} value={item.value} />
            ))}
          </div>
        ) : null}
      </TerminalPanel>
    </section>
  );
}

function ScannerLaunchEvidenceSummary({
  runDetail,
  decisionSummary,
  shortlistCount,
  generatedAt,
  language,
}: {
  runDetail: ScannerRunDetail | null;
  decisionSummary: ReturnType<typeof buildDecisionSummary> | null;
  shortlistCount: number;
  generatedAt: string | null;
  language: 'zh' | 'en';
}) {
  const coverage = runDetail ? getRunCoverageSummary(runDetail) : null;
  const provider = runDetail ? getRunProviderDiagnostics(runDetail) : null;
  const evaluatedCount = runDetail?.summary?.evaluatedCount ?? runDetail?.evaluatedSize ?? 0;
  const dataReadyCount = coverage?.eligibleAfterDataAvailabilityFilter ?? evaluatedCount;
  const missingCount = provider?.missingDataSymbolCount ?? runDetail?.summary?.dataFailedCount ?? 0;
  const readinessLabel = runDetail ? getRunDataStatusLabel(runDetail, language) : (language === 'en' ? 'Waiting for scan' : '等待扫描');
  const readinessPlainText = !runDetail
    ? (language === 'en' ? 'Waiting for scan' : '等待扫描')
    : missingCount > 0
      ? (language === 'en' ? 'Partial data missing' : '部分数据缺失')
      : dataReadyCount > 0
        ? (language === 'en' ? 'Enough data for observation' : '数据可用于观察')
        : readinessLabel;
  const stateLabel = runDetail ? compactScannerStateLabel(runDetail.status, language) : (language === 'en' ? 'No scan loaded' : '暂无扫描');
  const nextStep = !runDetail
    ? (language === 'en' ? 'Run or open a recent scan to inspect candidates.' : '运行扫描或打开近期扫描后查看候选。')
    : shortlistCount > 0
      ? (language === 'en' ? 'Open the leading candidate evidence, then add only validated names to watchlist.' : '先查看头部候选证据，再把确认需要跟踪的标的加入观察。')
      : (language === 'en' ? 'No shortlist yet. Inspect data readiness before changing scope.' : '本次暂无候选，先检查数据可用性，再调整范围。');

  return (
    <section data-testid="scanner-launch-evidence-summary" className="grid gap-2 border-b border-white/5 px-3 py-3 lg:grid-cols-[minmax(0,1.2fr)_minmax(220px,0.8fr)]">
      <TerminalPanel dense className="p-3">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <TerminalChip variant="success" className="rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest text-emerald-100/85">
            {stateLabel}
          </TerminalChip>
          <TerminalChip variant="neutral" className="rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest text-white/50">
            {language === 'en' ? `${shortlistCount} candidates` : `${shortlistCount} 个候选`}
          </TerminalChip>
          {generatedAt ? <span className="font-mono text-[11px] text-white/42">{formatTimestamp(generatedAt, language)}</span> : null}
        </div>
        <h2 className="mt-2 text-base font-semibold tracking-tight text-white">
          {decisionSummary?.headline || (language === 'en' ? 'Candidate evidence is waiting for a scan' : '候选证据等待扫描')}
        </h2>
        <p className="mt-1 line-clamp-2 text-sm leading-relaxed text-white/62">
          {decisionSummary ? [decisionSummary.reason, decisionSummary.data].filter(Boolean).join(language === 'en' ? ' · ' : ' · ') : nextStep}
        </p>
      </TerminalPanel>
      <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-1">
        <TerminalNestedBlock>
          <span className="block text-[10px] font-bold uppercase tracking-widest text-white/38">{language === 'en' ? 'Evidence confidence' : '证据置信'}</span>
          <span className="mt-1 block font-mono text-lg font-semibold text-emerald-100">{decisionSummary?.best || '--'}</span>
        </TerminalNestedBlock>
        <TerminalNestedBlock>
          <span className="block text-[10px] font-bold uppercase tracking-widest text-white/38">{language === 'en' ? 'Data readiness' : '数据就绪'}</span>
          <span className="mt-1 block text-sm font-medium text-white/78">{readinessLabel}</span>
          <span className="mt-0.5 block text-[11px] text-white/42">{readinessPlainText}</span>
        </TerminalNestedBlock>
        <TerminalNestedBlock>
          <span className="block text-[10px] font-bold uppercase tracking-widest text-white/38">{language === 'en' ? 'Next observation' : '下一步观察'}</span>
          <span className="mt-1 block text-xs leading-relaxed text-white/62">{nextStep}</span>
        </TerminalNestedBlock>
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
  const [isDataNotesOpen, setIsDataNotesOpen] = useState(false);
  const [previousRunDetail, setPreviousRunDetail] = useState<ScannerRunDetail | null>(null);
  const [previewThreshold, setPreviewThreshold] = useState(50);
  const [viewMode, setViewMode] = useState<ViewMode>('cards');
  const [sortKey, setSortKey] = useState<SortKey>('score');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [expandedSymbol, setExpandedSymbol] = useState<string | null>(null);
  const [inspectorSymbol, setInspectorSymbol] = useState<string | null>(null);
  const [pendingAnalyzeSymbol, setPendingAnalyzeSymbol] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [candidateFilter, setCandidateFilter] = useState<CandidateFilter>('selected');
  const [simulationLookbackDays, setSimulationLookbackDays] = useState(90);
  const [simulationForwardDays, setSimulationForwardDays] = useState(5);
  const [strategySimulation, setStrategySimulation] = useState<ScannerStrategySimulationResult | null>(null);
  const [isStrategySimulationLoading, setIsStrategySimulationLoading] = useState(false);
  const [strategySimulationError, setStrategySimulationError] = useState<string | null>(null);
  const selectedRunIdRef = useRef<number | null>(null);

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
      selectedRunIdRef.current = response.id;
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

      const currentSelectedRunId = selectedRunIdRef.current;
      const targetRunId = preferredRunId
        || (currentSelectedRunId && response.items.some((item) => item.id === currentSelectedRunId) ? currentSelectedRunId : null)
        || response.items[0]?.id
        || null;
      if (targetRunId && targetRunId !== currentSelectedRunId) {
        void loadRun(targetRunId);
      }
      if (!targetRunId) {
        setRunDetail(null);
        selectedRunIdRef.current = null;
        setSelectedRunId(null);
      }
    } catch (error) {
      setHistoryError(getParsedApiError(error));
    } finally {
      setIsLoadingHistory(false);
    }
  }, [loadRun, market, profile]);

  useEffect(() => {
    setRunDetail(null);
    selectedRunIdRef.current = null;
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
      selectedRunIdRef.current = response.id;
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
  const currentRunSummary = useMemo(
    () => buildScannerRunSummary(language === 'en' ? 'Current scan' : '本次扫描', runDetail, language),
    [language, runDetail],
  );
  const recentRunSummary = useMemo(
    () => buildHistoryItemSummary(language === 'en' ? 'Latest scan' : '最近扫描', historyItems[0] || null, language),
    [historyItems, language],
  );
  const previousRunSummary = useMemo(
    () => buildScannerRunSummary(language === 'en' ? 'Previous scan' : '上次扫描', previousRunDetail, language),
    [language, previousRunDetail],
  );
  const comparisonHighlights = useMemo(
    () => buildRunComparisonHighlights(runDetail, previousRunDetail, comparisonState, language),
    [comparisonState, language, previousRunDetail, runDetail],
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
  const {
    backtestCounts,
    backtestItems,
    backtestUnavailableLabel,
    getBacktestItem,
    handleBacktestBatch,
    handleBacktestCandidate,
    isBacktestBatchRunning,
  } = useScannerBacktestLab({
    language,
    batchCandidatesBySource: {
      official_selected: sortedCandidates,
      preview_selected: previewSelectedDiagnostics.map(diagnosticToCandidate),
      top_5: topFiveDiagnostics.map(diagnosticToCandidate),
      current_filter: decisionSortedDiagnosticCandidates.map(diagnosticToCandidate),
    },
  });
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
    const historyHeadline = formatHistoryHeadline(item.headline, item.topSymbols, fallbackTitle);
    return {
      id: item.id,
      marketLabel: item.market === 'us' ? t('scanner.marketUs') : item.market === 'hk' ? t('scanner.marketHk') : t('scanner.marketCn'),
      marketVariant: marketVariant(item.market),
      statusLabel: compactScannerStateLabel(item.status, language),
      statusVariant: statusVariant(item.status),
      watchlistDateLabel: item.watchlistDate ? formatDateOnly(item.watchlistDate, language) : null,
      profileLabel: item.profileLabel || item.profile,
      title: historyHeadline.title,
      detail: historyHeadline.detail,
      shortlistSize: item.shortlistSize,
      universeSize: item.universeSize,
      evaluatedSize: item.evaluatedSize,
      runAtLabel: formatTimestamp(item.runAt, language),
      comparisonLabel: hasComparison(item.changeSummary)
        ? (language === 'en'
          ? `new ${item.changeSummary.newCount} · retained ${item.changeSummary.retainedCount} · dropped ${item.changeSummary.droppedCount}`
          : `新增 ${item.changeSummary.newCount} · 保留 ${item.changeSummary.retainedCount} · 移出 ${item.changeSummary.droppedCount}`)
        : null,
      reviewLabel: hasReviewSummary(item.reviewSummary)
        ? (language === 'en'
          ? `reviewed ${item.reviewSummary.reviewedCount}/${item.reviewSummary.candidateCount}`
          : `复盘 ${item.reviewSummary.reviewedCount}/${item.reviewSummary.candidateCount}`)
        : null,
      matchedSymbols: matchedSymbols.slice(0, 10),
      overflowSymbolCount: Math.max(0, matchedSymbols.length - 10),
    } satisfies ScannerHistoryDrawerItem;
  }), [historyItems, language, t]);
  const emptyStateTitle = language === 'en' ? 'No matching scanner results' : '当前无匹配的扫描结果';
  const emptyStateBody = language === 'en' ? 'Adjust the filters on the left or try again later' : '请调整左侧参数或稍后再试';
  const pageErrorSummary = pageError ? sanitizeScannerErrorSummary(pageError.message, language) || compactScannerStateLabel('failed', language) : null;
  const primarySelectedCandidate = sortedCandidates[0] || (inspectorCandidate ? diagnosticToCandidate(inspectorCandidate) : null);
  const singleSelectedSymbol = sortedCandidates.length === 1 ? normalizeCandidateSymbol(sortedCandidates[0]?.symbol) : null;
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

  const getBacktestActionLabel = useCallback((item?: ScannerBacktestItem) => (
    item?.status === 'running' || item?.status === 'queued'
      ? (language === 'en' ? 'Running' : '运行中')
      : (language === 'en' ? 'Backtest' : '回测')
  ), [language]);

  const renderCandidateDetailPanel = useCallback((
    candidate: ScannerCandidate,
    isTracked: boolean,
    isTrackPending: boolean,
    backtestItem?: ScannerBacktestItem,
  ) => {
    if (!runDetail) return null;
    const candidateProvider = getProviderDiagnostics(candidate.diagnostics);
    const ai = candidate.aiInterpretation;
    const outcomeItems = hasOutcome(candidate.realizedOutcome)
      ? [
        { label: language === 'en' ? 'Outcome' : '结果', value: candidate.realizedOutcome.outcomeLabel },
        { label: language === 'en' ? 'Thesis' : '验证', value: candidate.realizedOutcome.thesisMatch },
        ...(candidate.realizedOutcome.reviewWindowReturnPct != null
          ? [{ label: language === 'en' ? 'Window return' : '窗口收益', value: formatPercent(candidate.realizedOutcome.reviewWindowReturnPct) }]
          : []),
        ...(candidate.realizedOutcome.benchmarkCode
          ? [{ label: language === 'en' ? 'Benchmark' : '基准', value: candidate.realizedOutcome.benchmarkCode }]
          : []),
      ]
      : [];

    return (
      <ScannerCandidateDetailPanel
        candidate={candidate}
        candidateIdentity={getCandidateIdentity(candidate)}
        language={language}
        evidenceSummary={getScannerEvidenceSummary(candidate)}
        keyMetricItems={sanitizeScannerLabeledValues(candidate.keyMetrics, language)}
        featureSignalItems={sanitizeScannerLabeledValues(candidate.featureSignals, language)}
        riskNotes={sanitizeScannerNotes(candidate.riskNotes || [], language)}
        entryRange={getEntryRange(candidate)}
        targetPrice={getTargetPrice(candidate)}
        stopLoss={getStopLoss(candidate)}
        selectionNotes={sanitizeScannerNotes([
          candidate.reasonSummary,
          ...(candidate.reasons || []),
          ...(runDetail.scoringNotes || []),
        ], language)}
        aiLines={[ai?.summary, ai?.watchPlan, ai?.riskInterpretation].filter((item): item is string => Boolean(item))}
        aiUnavailableText={sanitizeScannerUserText(ai?.status, language, language === 'en' ? 'AI interpretation not available' : 'AI 解读不可用')}
        outcomeItems={outcomeItems}
        providerNotes={candidateProvider ? formatProviderDiagnostics(candidateProvider, language) : null}
        onAnalyze={() => void handleAnalyzeCandidate(candidate)}
        onCopy={() => void handleCopyText(candidate.symbol, `candidate:${candidate.symbol}`)}
        onExport={() => handleExportRows(
          [buildScannerExportRow(candidate, runDetail, language)],
          buildScannerExportFilename(runDetail, `candidate-${candidate.symbol}`),
        )}
        onTrack={() => void handleTrackCandidate(candidate)}
        onBacktest={() => void handleBacktestCandidate(candidate)}
        isAnalyzing={pendingAnalyzeSymbol === candidate.symbol}
        isCopied={copiedKey === `candidate:${candidate.symbol}`}
        isTracked={isTracked}
        isTrackPending={isTrackPending}
        isWatchlistAuthBlocked={watchlistAuthBlocked}
        watchlistActionLabel={getWatchlistActionLabel(isTracked, isTrackPending, watchlistAuthBlocked, language)}
        watchlistActionTitle={getWatchlistActionTitle(isTracked, watchlistAuthBlocked, language)}
        backtestLabel={getBacktestActionLabel(backtestItem)}
        backtestTitle={!normalizeCandidateSymbol(candidate.symbol) ? backtestUnavailableLabel : undefined}
        backtestItem={backtestItem}
      />
    );
  }, [
    backtestUnavailableLabel,
    copiedKey,
    formatProviderDiagnostics,
    getBacktestActionLabel,
    handleAnalyzeCandidate,
    handleBacktestCandidate,
    handleCopyText,
    handleExportRows,
    handleTrackCandidate,
    language,
    pendingAnalyzeSymbol,
    runDetail,
    watchlistAuthBlocked,
  ]);

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
	        <TerminalPageShell
	          data-testid="user-scanner-workspace"
	          className="flex-1 min-w-0"
	        >
            <TerminalPageHeading
              data-testid="scanner-page-heading"
              title={language === 'en' ? 'Scanner' : '扫描器'}
            />
	          {pageError ? (
	            <div className="mx-3 mt-3 rounded-xl border border-rose-400/20 bg-rose-400/10 px-3 py-2 text-sm text-rose-100" role="alert" data-testid="scanner-page-error-summary">
	              <div className="flex flex-wrap items-center gap-2">
	                <span className="font-medium">{language === 'en' ? 'Scan did not complete' : '扫描未完成'}</span>
	                <span className="rounded border border-rose-300/20 bg-black/20 px-1.5 py-0.5 text-[11px]">{pageErrorSummary}</span>
	              </div>
	              <p className="mt-2 text-xs text-rose-50/70">
	                {language === 'en' ? 'Internal error details are hidden on this page.' : '内部错误详情已隐藏。'}
	              </p>
	            </div>
	          ) : null}
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

		          <TerminalGrid data-testid="scanner-workspace-grid" className="w-full flex-1 min-w-0">
		            <TerminalPanel
                  as="section"
		              data-testid="scanner-control-rail"
		              className="order-1 flex w-full shrink-0 flex-col xl:sticky xl:top-4 xl:col-span-3"
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
                          className="select-surface absolute inset-0 z-10 h-full w-full min-w-0 cursor-pointer appearance-none truncate rounded-lg pr-10 opacity-0 outline-none"
                          onChange={(event) => setThemeId(event.target.value)}
                          aria-invalid={Boolean(validationErrors.theme)}
                          aria-describedby={validationErrors.theme ? 'scanner-theme-error' : undefined}
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
                          className="w-full appearance-none rounded-lg border border-white/8 bg-black/40 px-2.5 py-1.5 text-xs text-white outline-none placeholder:text-white/20 focus:border-indigo-400/50"
                          onChange={(event) => setCustomThemeLabel(event.target.value)}
                          aria-invalid={Boolean(validationErrors.customThemeLabel)}
                          aria-describedby={validationErrors.customThemeLabel ? 'scanner-ai-theme-label-error' : undefined}
                          maxLength={80}
                          placeholder={language === 'en' ? 'White House Stocks' : 'White House Stocks'}
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
                          className="w-full appearance-none rounded-lg border border-white/8 bg-black/40 px-2.5 py-1.5 text-xs text-white outline-none placeholder:text-white/20 focus:border-indigo-400/50"
                          onChange={(event) => setCustomThemeManualSymbols(event.target.value)}
                          aria-invalid={Boolean(validationErrors.customThemeManualSymbols)}
                          aria-describedby={validationErrors.customThemeManualSymbols ? 'scanner-ai-theme-manual-symbols-error' : undefined}
                          placeholder={language === 'en' ? 'Optional: add symbols, e.g. NVDA PLTR' : '可选：手动补充代码，例如 NVDA PLTR'}
                        />
                        {validationErrors.customThemeManualSymbols ? (
                          <p id="scanner-ai-theme-manual-symbols-error" role="alert" className="text-[11px] leading-relaxed text-rose-100/82">
                            {validationErrors.customThemeManualSymbols}
                          </p>
                        ) : null}
                        <TerminalButton
                          ref={generateThemeButton.ref}
                          type="button"
                          variant="secondary"
                          disabled={generateThemeDisabled}
                          onPointerUp={generateThemeButton.onPointerUp}
                          onClick={generateThemeButton.onClick}
                          className="h-8 px-3 text-xs"
                        >
                          <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
                          <span>{isGeneratingTheme ? (language === 'en' ? 'Generating...' : '生成中...') : (language === 'en' ? 'Generate theme' : '生成主题')}</span>
                        </TerminalButton>
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
	                    <TerminalButton
	                      ref={runScannerButton.ref}
	                      type="button"
	                      onClick={runScannerButton.onClick}
                      onPointerUp={runScannerButton.onPointerUp}
	                      disabled={runDisabled}
	                      aria-busy={isRunning}
	                      data-testid="scanner-run-button"
	                      className="group flex w-full px-5 py-3 text-sm font-bold active:scale-95 disabled:pointer-events-none xl:sticky xl:bottom-0"
                        variant="primary"
	                    >
	                      <Play className="h-4 w-4 group-hover:animate-pulse" />
	                      <span>{isRunning ? t('scanner.running') : (language === 'zh' ? '启动扫描' : t('scanner.run'))}</span>
	                    </TerminalButton>
                  </div>
                </div>
              </SectionShell>
	            </TerminalPanel>

		            <TerminalPanel
                  as="section"
		              data-testid="scanner-results-stage"
		              className="order-2 flex min-h-[520px] flex-1 min-w-0 flex-col xl:col-span-9"
		            >
              <div data-testid="scanner-results-pane" className="flex min-h-0 flex-1 min-w-0 flex-col">
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
	                      <div className="grid w-full min-w-0 grid-cols-1 gap-1.5 sm:w-auto sm:grid-cols-[minmax(0,1fr)_auto]">
		                        <div
		                          data-testid="scanner-primary-actions"
		                          className="grid min-w-0 grid-cols-1 gap-1.5 sm:col-span-2 sm:grid-cols-[minmax(0,1fr)_auto]"
		                        >
		                          <ActionButton
		                            label={singleSelectedSymbol
		                              ? (language === 'en' ? `View ${singleSelectedSymbol}` : `查看 ${singleSelectedSymbol}`)
		                              : (language === 'en' ? 'View leading evidence' : '查看头号证据')}
	                            icon={<Info className="h-3.5 w-3.5" />}
		                            onClick={() => {
		                              setInspectorSymbol(primarySelectedCandidate.symbol);
		                              setExpandedSymbol(primarySelectedCandidate.symbol);
		                            }}
		                            variant="secondary"
			                          />
		                          <div data-testid="scanner-more-actions" className="relative min-w-0">
		                            <TerminalButton
		                              type="button"
                              variant="secondary"
		                              aria-expanded={isMoreActionsOpen}
		                              aria-label={language === 'en' ? 'More scanner actions' : '更多扫描操作'}
		                              className="h-full w-full px-2.5 py-1 text-xs"
		                              onClick={() => setIsMoreActionsOpen((current) => !current)}
		                            >
		                              <MoreHorizontal className="h-3.5 w-3.5" aria-hidden="true" />
		                              <span>{language === 'en' ? 'More' : '更多'}</span>
		                            </TerminalButton>
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
		                            <TerminalButton
		                              ref={openHistoryDrawerButton.ref}
		                              type="button"
                              variant="compact"
	                              data-testid="user-scanner-bento-drawer-trigger"
		                              onClick={openHistoryDrawerButton.onClick}
	                              onPointerUp={openHistoryDrawerButton.onPointerUp}
		                              className="w-full px-2.5 py-1 text-xs"
		                            >
		                              <History className="h-3.5 w-3.5" aria-hidden="true" />
		                              <span>{language === 'en' ? 'Historical replay' : '历史扫描回放'}</span>
		                            </TerminalButton>
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
	                      <TerminalButton
	                        ref={openHistoryDrawerButton.ref}
	                        type="button"
                        variant="secondary"
	                        data-testid="user-scanner-bento-drawer-trigger"
	                        onClick={openHistoryDrawerButton.onClick}
	                        onPointerUp={openHistoryDrawerButton.onPointerUp}
	                        className="px-2.5 py-1 text-xs"
	                      >
		                        <History className="h-4 w-4" aria-hidden="true" />
	                        <span>{language === 'en' ? 'Historical replay' : '历史扫描回放'}</span>
	                      </TerminalButton>
                    )}
                  </div>
                </div>
              </div>

	              <ScannerLaunchEvidenceSummary
	                runDetail={runDetail}
	                decisionSummary={decisionSummary}
	                shortlistCount={shortlistCount}
	                generatedAt={generatedAt}
	                language={language}
	              />

              {runDetail ? (
                <div className="shrink-0 border-b border-white/5 px-3 py-2" data-testid="scanner-diagnostic-summary">
                  <div data-testid="scanner-summary-counters" className="flex flex-wrap items-center gap-1.5 rounded-xl border border-white/5 bg-white/[0.02] px-2.5 py-2 backdrop-blur-md">
                    {[
                      [language === 'en' ? 'Universe' : '候选范围', runDetail.summary?.universeCount ?? runDetail.acceptedSymbolsCount ?? runDetail.universeSize],
                      [language === 'en' ? 'Evaluated' : '已评估', runDetail.summary?.evaluatedCount ?? runDetail.evaluatedSize],
                      [language === 'en' ? 'Selected' : '入选', runDetail.summary?.selectedCount ?? shortlistCount],
                      [language === 'en' ? 'Not selected' : '未入选', runDetail.summary?.rejectedCount ?? 0],
                      [language === 'en' ? 'Data thin' : '数据不足', runDetail.summary?.dataFailedCount ?? 0],
                      [language === 'en' ? 'Not processed' : '暂未处理', runDetail.summary?.skippedCount ?? 0],
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
                        ].filter(Boolean).join(' · ')}
                      </p>
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
                        className={`inline-flex shrink-0 items-center rounded-md px-2.5 py-1 text-xs ${candidateFilter === key ? 'bg-white/10 text-white' : 'text-white/45 hover:text-white/75'}`}
                        onClick={() => setCandidateFilter(key)}
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
                    disabled={!selectedOnlyView}
                    className={`inline-flex min-w-0 shrink-0 items-center gap-2 rounded-md px-2.5 py-1 text-xs ${viewMode === 'cards' && selectedOnlyView ? 'bg-white/10 text-white' : 'text-white/45 hover:text-white/75'} disabled:cursor-not-allowed disabled:opacity-35`}
                    onClick={() => setViewMode('cards')}
                  >
                    <LayoutGrid className="h-3.5 w-3.5" />
                    <span className="ui-truncate">{language === 'en' ? 'Card view' : '卡片视图'}</span>
                  </button>
                  <button
                    type="button"
                    className={`inline-flex min-w-0 shrink-0 items-center gap-2 rounded-md px-2.5 py-1 text-xs ${viewMode === 'table' ? 'bg-white/10 text-white' : 'text-white/45 hover:text-white/75'}`}
                    onClick={() => setViewMode('table')}
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
                    ['target', language === 'en' ? 'upper watch' : '上方观察'],
                    ['risk', language === 'en' ? 'risk/score' : '风险/评分'],
                  ] as const).map(([key, label]) => (
                    <button
                      key={key}
                      type="button"
                      className={`inline-flex items-center gap-1 rounded-lg border px-2 py-0.5 ${sortKey === key ? 'border-white/16 bg-white/[0.08] text-white' : 'border-white/5 bg-white/[0.02] text-white/48 hover:text-white/75'}`}
                      onClick={() => handleSortChange(key)}
                    >
                      {label}
                      {sortKey === key ? <ArrowDownUp className="h-3 w-3" /> : null}
                    </button>
                  ))}
                </div>
              </div>

		              <div data-testid="scanner-candidate-scroll-region" className="px-3 py-3">
		                <div className="grid gap-3">
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
                        const backtestItem = getBacktestItem(candidate.symbol);
                        const isExpanded = expandedSymbol === candidate.symbol;
                        const comparison = comparisonState.bySymbol.get(normalizeCandidateSymbol(candidate.symbol) || '');
                        const scoreDelta = formatScoreDelta(comparison?.scoreDelta ?? null);
                        const isInspectorActive = normalizeCandidateSymbol(inspectorCandidate?.symbol) === normalizeCandidateSymbol(candidate.symbol);
                        const isMoreOpen = rowMoreSymbol === candidate.symbol;
                        const friendlyReason = formatFriendlyDiagnosticReason(candidate, language);
                        const dataQualityLabel = formatCandidateDataQuality(candidate, language);
                        const evidenceSummary = getScannerEvidenceSummary(candidate);
                        const isSelectedCandidate = isOfficialSelected(candidate);
                        const statusLabel = diagnosticStatusLabel(candidate.status, language);
                        const missingCount = candidate.missingFields?.length || 0;
                        const failedRuleNotes = Array.from(new Set([
                          friendlyReason,
                          ...(candidate.failedRules || []).map((item) => sanitizeUserFacingDataIssue(item, language)),
                        ]));
                        const missingFieldNotes = Array.from(new Set((candidate.missingFields || []).map((item) => sanitizeUserFacingDataIssue(item, language))));
                        return (
                          <ScannerCandidateDiagnosticRow
                            key={`diagnostic-${candidate.symbol}`}
                            candidate={candidate}
                            language={language}
                            isSelectedCandidate={isSelectedCandidate}
                            isInspectorActive={isInspectorActive}
                            isExpanded={isExpanded}
                            isMoreOpen={isMoreOpen}
                            previewLabel={previewDecisionLabel(candidate, previewThreshold, language)}
                            previewBadgeClassName={previewDecisionClass(candidate, previewThreshold)}
                            friendlyReason={friendlyReason}
                            dataQualityLabel={dataQualityLabel}
                            evidenceSummary={evidenceSummary}
                            scoreLabel={candidate.score == null ? '--' : `${candidate.score}/100`}
                            scoreDelta={scoreDelta}
                            comparisonLabel={comparison?.label || null}
                            statusLabel={statusLabel}
                            missingCount={missingCount}
                            failedRuleNotes={failedRuleNotes}
                            missingFieldNotes={missingFieldNotes}
                            watchlistActionLabel={getWatchlistActionLabel(isTracked, isTrackPending, watchlistAuthBlocked, language)}
                            watchlistActionTitle={getWatchlistActionTitle(isTracked, watchlistAuthBlocked, language)}
                            isTracked={isTracked}
                            isTrackPending={isTrackPending}
                            isWatchlistAuthBlocked={watchlistAuthBlocked}
                            backtestLabel={getBacktestActionLabel(backtestItem)}
                            backtestTitle={!normalizeCandidateSymbol(candidate.symbol) ? backtestUnavailableLabel : undefined}
                            backtestItem={backtestItem}
                            copyLabel={copiedKey === `candidate:${candidate.symbol}` ? (language === 'en' ? 'Copied' : '已复制') : (language === 'en' ? 'Copy' : '复制')}
                            onSelect={() => {
                              setInspectorSymbol(candidate.symbol);
                              setExpandedSymbol(candidate.symbol);
                            }}
                            onViewEvidence={() => {
                              setInspectorSymbol(candidate.symbol);
                              setExpandedSymbol(candidate.symbol);
                            }}
                            onToggleMore={() => setRowMoreSymbol((current) => current === candidate.symbol ? null : candidate.symbol)}
                            onBacktest={() => void handleBacktestCandidate(diagnosticCandidate)}
                            onTrack={() => void handleTrackCandidate(diagnosticCandidate)}
                            onCopy={() => void handleCopyText(candidate.symbol, `candidate:${candidate.symbol}`)}
                            onExport={() => {
                              handleExportRows(
                                [buildScannerExportRow(diagnosticCandidate, runDetail, language)],
                                buildScannerExportFilename(runDetail, `candidate-${candidate.symbol}`),
                              );
                            }}
                          />
                        );
                      })}
                    </div>
                  ) : (
                    <TerminalEmptyState
                      title={language === 'en' ? 'No candidates in this filter' : '当前过滤无候选'}
                      className="w-full"
                    >
                      {language === 'en' ? 'Switch to Candidate pool or All to inspect the full submitted universe.' : '切换到候选池或全部查看完整提交范围。'}
                    </TerminalEmptyState>
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
                      const backtestItem = getBacktestItem(candidate.symbol);
                      const entryRange = getEntryRange(candidate);
	                      const targetPrice = getTargetPrice(candidate);
	                      const stopLoss = getStopLoss(candidate);
	                      const comparison = comparisonState.bySymbol.get(normalizeCandidateSymbol(candidate.symbol) || '');
                        const evidenceSummary = getScannerEvidenceSummary(candidate);
                      return (
                        <ScannerCandidateCard
                          key={`watchlist-${candidateIdentity}`}
                          candidate={candidate}
                          candidateIdentity={candidateIdentity}
                          language={language}
                          isExpanded={isExpanded}
                          isTracked={isTracked}
                          isTrackPending={isTrackPending}
                          comparisonLabel={comparison?.label || null}
                          scoreBadgeClassName={scoreBadgeClass(candidate.score)}
                          keyReason={getKeyReason(candidate, runDetail, language)}
                          entryRange={entryRange}
                          targetPrice={targetPrice}
                          stopLoss={stopLoss}
                          evidenceSummary={evidenceSummary}
                          featureSignalItems={sanitizeScannerLabeledValues(candidate.featureSignals, language)}
                          keyMetricItems={sanitizeScannerLabeledValues(candidate.keyMetrics, language)}
                          watchlistActionLabel={getWatchlistActionLabel(isTracked, isTrackPending, watchlistAuthBlocked, language)}
                          watchlistActionTitle={getWatchlistActionTitle(isTracked, watchlistAuthBlocked, language)}
                          onSelect={() => setInspectorSymbol(candidate.symbol)}
                          onToggleDetail={() => {
                            setInspectorSymbol(candidate.symbol);
                            setExpandedSymbol(isExpanded ? null : candidate.symbol);
                          }}
                          onViewEvidence={() => setExpandedSymbol(isExpanded ? null : candidate.symbol)}
                          onTrack={() => void handleTrackCandidate(candidate)}
                          detailPanel={renderCandidateDetailPanel(candidate, isTracked, isTrackPending, backtestItem)}
                          backtestItem={backtestItem}
                        />
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
		                          <TerminalButton
		                            type="button"
                              variant="compact"
		                            className="shrink-0 px-2 py-1 text-xs"
		                            onClick={() => setCandidateFilter('pool')}
		                          >
	                            {language === 'en' ? 'View all candidates' : '查看全部候选'}
	                          </TerminalButton>
                        </div>
                        {previewAddedDiagnostics.length ? (
                          <div data-testid="scanner-preview-added-list" className="mb-2 grid gap-1.5">
                            {previewAddedDiagnostics.slice(0, 4).map((candidate) => (
		                              <TerminalButton
		                                key={`preview-added-${candidate.symbol}`}
		                                type="button"
                                variant="compact"
		                                data-testid={`scanner-preview-added-${candidate.symbol}`}
		                                className="grid w-full min-w-0 grid-cols-[minmax(54px,0.45fr)_minmax(72px,0.55fr)_minmax(0,1fr)] items-center justify-start gap-2 px-2 py-1.5 text-left text-xs"
		                                onClick={() => {
		                                  setInspectorSymbol(candidate.symbol);
		                                  setCandidateFilter('pool');
		                                }}
		                              >
                                <span className="truncate font-mono font-semibold text-blue-100">{candidate.symbol}</span>
                                <span className="truncate font-mono text-blue-100/58">{diagnosticScoreValue(candidate)}</span>
                                <span className="truncate text-white/50" title={formatFriendlyDiagnosticReason(candidate, language)}>
                                  {formatFriendlyDiagnosticReason(candidate, language)}
                                </span>
		                              </TerminalButton>
                            ))}
                          </div>
                        ) : null}
                        <div className="grid gap-1.5">
                          {previewCandidates.map((candidate) => (
		                            <TerminalButton
		                              key={`preview-${candidate.symbol}`}
		                              type="button"
                              variant="compact"
		                              className="grid w-full min-w-0 grid-cols-[minmax(54px,0.45fr)_minmax(72px,0.55fr)_minmax(0,1fr)] items-center justify-start gap-2 px-2 py-1.5 text-left text-xs"
		                              onClick={() => {
		                                setInspectorSymbol(candidate.symbol);
		                                setCandidateFilter('pool');
		                              }}
		                            >
                              <span className="truncate font-mono font-semibold text-white/78">{candidate.symbol}</span>
                              <span className="truncate font-mono text-white/42">{diagnosticScoreValue(candidate)}</span>
                              <span className="truncate text-white/50" title={formatFriendlyDiagnosticReason(candidate, language)}>
                                {formatFriendlyDiagnosticReason(candidate, language)}
                              </span>
		                            </TerminalButton>
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
                          <th className="px-2.5 py-2">{language === 'en' ? 'Watch range' : '观察区间'}</th>
                          <th className="px-2.5 py-2">{language === 'en' ? 'Upper watch' : '上方观察'}</th>
                          <th className="px-2.5 py-2">{language === 'en' ? 'Risk boundary' : '风险边界'}</th>
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
                          const backtestItem = getBacktestItem(candidate.symbol);
                          return (
                            <ScannerCandidateTableRow
                              key={`table-${candidateIdentity}`}
                              candidate={candidate}
                              candidateIdentity={candidateIdentity}
                              language={language}
                              isExpanded={isExpanded}
                              entryRange={getEntryRange(candidate)}
                              targetPrice={getTargetPrice(candidate)}
                              stopLoss={getStopLoss(candidate)}
                              keyReason={getKeyReason(candidate, runDetail, language)}
                              riskSummary={getRiskSummary(candidate, language)}
                              sourceBadge={getSourceBadge(candidate, runDetail, language) || '--'}
                              scoreBadgeClassName={scoreBadgeClass(candidate.score)}
                              watchlistActionLabel={getWatchlistActionLabel(isTracked, isTrackPending, watchlistAuthBlocked, language)}
                              watchlistActionTitle={getWatchlistActionTitle(isTracked, watchlistAuthBlocked, language)}
                              copyLabel={copiedKey === `candidate:${candidate.symbol}` ? (language === 'en' ? 'Copied' : '已复制') : (language === 'en' ? 'Copy' : '复制')}
                              backtestLabel={getBacktestActionLabel(backtestItem)}
                              backtestTitle={!normalizeCandidateSymbol(candidate.symbol) ? backtestUnavailableLabel : undefined}
                              isTracked={isTracked}
                              isTrackPending={isTrackPending}
                              isAnalyzing={pendingAnalyzeSymbol === candidate.symbol}
                              isBacktestDisabled={!normalizeCandidateSymbol(candidate.symbol) || backtestItem?.status === 'running' || backtestItem?.status === 'queued'}
                              detailPanel={renderCandidateDetailPanel(candidate, isTracked, isTrackPending, backtestItem)}
                              onSelect={() => {
                                setInspectorSymbol(candidate.symbol);
                                setExpandedSymbol(isExpanded ? null : candidate.symbol);
                              }}
                              onAnalyze={() => void handleAnalyzeCandidate(candidate)}
                              onTrack={() => void handleTrackCandidate(candidate)}
                              onCopy={() => void handleCopyText(candidate.symbol, `candidate:${candidate.symbol}`)}
                              onToggleDetail={() => setExpandedSymbol(isExpanded ? null : candidate.symbol)}
                              onBacktest={() => void handleBacktestCandidate(candidate)}
                            />
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )
              ) : (
                <TerminalEmptyState
                  title={runDetail?.summary?.selectedCount === 0 && diagnosticCandidates.length ? (language === 'en' ? 'No selected candidates' : '本次无入选候选') : emptyStateTitle}
                  className="w-full"
                >
                  {runDetail?.summary?.selectedCount === 0 && diagnosticCandidates.length
                    ? (language === 'en' ? 'Open Candidate pool or All to inspect rejected and data-failed candidates.' : '切换到候选池或全部查看淘汰与数据失败原因。')
	                    : pageErrorSummary || emptyStateBody}
                </TerminalEmptyState>
              )}
                    {runDetail && inspectorCandidate ? (() => {
                      const mobileMarket = normalizeScannerMarket(runDetail.market || market);
                      const mobileWatchlistIdentity = getWatchlistIdentity(mobileMarket, inspectorCandidate.symbol);
                      const mobileTracked = Boolean(mobileWatchlistIdentity && trackedWatchlistIdentitySet.has(mobileWatchlistIdentity));
                      const mobileTrackPending = pendingWatchlistIdentity === mobileWatchlistIdentity;
                      const mobileBacktestItem = getBacktestItem(inspectorCandidate.symbol);
                      const mobileInspectorCandidate = diagnosticToCandidate(inspectorCandidate);
                      const mobileComparison = comparisonState.bySymbol.get(normalizeCandidateSymbol(inspectorCandidate.symbol) || '');
                      const mobileStatus = normalizeDiagnosticStatus(inspectorCandidate.status);
                      const mobileEvidenceSummary = getScannerEvidenceSummary(inspectorCandidate);
                      const mobileDataQualityLabel = formatCandidateDataQuality(inspectorCandidate, language);
                      return (
                        <div className="mt-3" data-testid="scanner-mobile-candidate-inspector">
                          <ScannerCandidateInspector
                            candidate={inspectorCandidate}
                            language={language}
                            evidenceSummary={mobileEvidenceSummary}
                            statusLabel={diagnosticStatusLabel(mobileStatus, language)}
                            statusClassName={diagnosticStatusClass(mobileStatus)}
                            officialStatusCopy={isOfficialSelected(inspectorCandidate)
                              ? (language === 'en' ? 'Official selected' : '官方入选')
                              : (language === 'en' ? 'Official rejected' : '官方淘汰')}
                            previewStatusCopy={isPreviewSelected(inspectorCandidate, previewThreshold)
                              ? (language === 'en' ? `Threshold ${previewThreshold} preview selected` : `阈值 ${previewThreshold} 预览入选`)
                              : (language === 'en' ? `Threshold ${previewThreshold} preview rejected` : `阈值 ${previewThreshold} 预览淘汰`)}
                            dataQualityLabel={mobileDataQualityLabel}
                            comparisonLabel={mobileComparison?.label || null}
                            comparisonDelta={formatScoreDelta(mobileComparison?.scoreDelta ?? null)}
                            whySelectedNotes={buildInspectorWhySelected(inspectorCandidate, language)}
                            riskNotes={buildInspectorRiskNotes(inspectorCandidate, runDetail, language)}
                            failedRuleNotes={Array.from(new Set((inspectorCandidate.failedRules || []).map((item) => sanitizeUserFacingDataIssue(item, language))))}
                            missingFieldNotes={Array.from(new Set((inspectorCandidate.missingFields || []).map((item) => sanitizeUserFacingDataIssue(item, language))))}
                            missingCount={inspectorCandidate.missingFields?.length || 0}
                            onCopy={() => void handleCopyText(inspectorCandidate.symbol, `candidate:${inspectorCandidate.symbol}`)}
                            onExport={() => handleExportRows(
                              [buildScannerExportRow(mobileInspectorCandidate, runDetail, language)],
                              buildScannerExportFilename(runDetail, `candidate-${inspectorCandidate.symbol}`),
                            )}
                            onTrack={() => void handleTrackCandidate(mobileInspectorCandidate)}
                            isCopied={copiedKey === `candidate:${inspectorCandidate.symbol}`}
                            isTracked={mobileTracked}
                            isTrackPending={mobileTrackPending}
                            isWatchlistAuthBlocked={watchlistAuthBlocked}
                            watchlistActionLabel={getWatchlistActionLabel(mobileTracked, mobileTrackPending, watchlistAuthBlocked, language)}
                            watchlistActionTitle={getWatchlistActionTitle(mobileTracked, watchlistAuthBlocked, language)}
                            backtestItem={mobileBacktestItem}
                            testId="scanner-candidate-inspector"
                          />
                        </div>
                      );
                    })() : null}
                  </div>

                </div>
              </div>

              {runDetail && hasCandidateDiagnostics ? (
                <div data-testid="scanner-secondary-sections" className="border-t border-white/5 px-3 py-3">
                  <div className="grid gap-2.5">
                    {rejectionBuckets.length || hasRunDiagnosticsContent(runDetail) ? (
                      <AdvancedDisclosure
                        testId="scanner-diagnostics-disclosure"
                        title={language === 'en' ? 'Data notes' : '数据说明'}
                        summary={language === 'en'
                          ? `Evaluated ${runDetail.summary?.evaluatedCount ?? runDetail.evaluatedSize}, selected ${runDetail.summary?.selectedCount ?? shortlistCount}, main rejection: ${rejectionBuckets[0]?.label || 'n/a'}`
                          : `本次共评估 ${runDetail.summary?.evaluatedCount ?? runDetail.evaluatedSize}，只入选 ${runDetail.summary?.selectedCount ?? shortlistCount}，主要淘汰原因：${rejectionBuckets[0]?.label || '暂无'}`}
                        icon="info"
                        open={isDataNotesOpen}
                        onToggle={setIsDataNotesOpen}
                      >
                        <div data-testid="scanner-diagnostics-summary" className="mb-3 rounded-xl border border-white/5 bg-black/20 px-3 py-2 text-xs">
                          <div className="flex min-w-0 flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                            <p className="min-w-0 text-white/64">
                              {language === 'en'
                                ? `Evaluated ${runDetail.summary?.evaluatedCount ?? runDetail.evaluatedSize}, selected ${runDetail.summary?.selectedCount ?? shortlistCount}, main rejection ${rejectionBuckets[0]?.label || 'n/a'}`
                                : `本次评估 ${runDetail.summary?.evaluatedCount ?? runDetail.evaluatedSize}，入选 ${runDetail.summary?.selectedCount ?? shortlistCount}，主要淘汰原因：${rejectionBuckets[0]?.label || '暂无'}`}
                            </p>
                            <ActionButton
                              label={language === 'en' ? 'View rejection reasons' : '查看淘汰原因'}
                              onClick={() => setIsRejectionSummaryOpen((current) => !current)}
                            />
                          </div>
                          {isRejectionSummaryOpen && rejectionBuckets.length ? (
                            <div data-testid="scanner-rejection-aggregate" className="mt-2 flex min-w-0 flex-wrap items-center gap-1.5">
                              {rejectionBuckets.map((bucket) => (
                                <button
                                  key={bucket.label}
                                  type="button"
                                  className="inline-flex max-w-full items-baseline gap-1 rounded-md border border-white/10 bg-white/5 px-1.5 py-0.5 text-[10px] text-white/62 hover:bg-white/10"
                                  onClick={() => setCandidateFilter(bucket.label === rejectionBucketLabel('data', language) ? 'data_failed' : 'rejected')}
                                >
                                  <span className="truncate">{bucket.label}</span>
                                  <span className="font-mono text-white/82">{bucket.value}</span>
                                </button>
                              ))}
                            </div>
                          ) : null}
                        </div>
                        <ScannerDiagnosticsPanel runDetail={runDetail} language={language} />
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
                      <ScannerResultHistorySummary
                        currentSummary={currentRunSummary}
                        recentSummary={recentRunSummary}
                        previousSummary={previousRunSummary}
                        comparisonItems={comparisonHighlights}
                        hasHistory={historyItems.length > 0}
                        language={language}
                      />
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
                        <div
                          data-testid="scanner-strategy-preview"
                          className="rounded-xl border border-white/5 bg-black/20 px-3 py-2 text-xs"
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
                                className={`rounded-md border px-2 py-0.5 font-mono text-[11px] ${previewThreshold === threshold ? 'border-blue-400/30 bg-blue-400/12 text-blue-100' : 'border-white/10 bg-white/5 text-white/58 hover:bg-white/10'}`}
                                onClick={() => setPreviewThreshold(threshold)}
                              >
                                {threshold}
                              </button>
                            ))}
                            <FieldChip label={language === 'en' ? 'Official' : '官方'} value={String(runDetail.summary?.selectedCount ?? officialSelectedDiagnostics.length)} />
                            <FieldChip label={language === 'en' ? 'Preview' : '预览'} value={String(previewSelectedDiagnostics.length)} />
                          </div>
                        </div>
                        <Suspense fallback={<ScannerStrategySimulationPanelFallback language={language} />}>
                          <LazyScannerStrategySimulationPanel
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
                        </Suspense>
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
              </div>
	            </TerminalPanel>
		          </TerminalGrid>
		        </TerminalPageShell>
      </div>

      <ScannerHistoryDrawer
        isOpen={isHistoryDrawerOpen}
        onClose={() => setIsHistoryDrawerOpen(false)}
        language={language}
        historyError={historyError}
        isLoadingHistory={isLoadingHistory}
        items={historyCards}
        selectedRunId={selectedRunId}
        emptyStateTitle={emptyStateTitle}
        emptyStateBody={emptyStateBody}
        loadingLabel={t('scanner.loadingHistory')}
        shortlistMetricLabel={t('scanner.metricShortlist')}
        universeMetricLabel={t('scanner.metricUniverse')}
        evaluatedMetricLabel={language === 'en' ? 'Evaluated' : '已评估'}
        historyPage={historyPage}
        totalHistoryPages={totalHistoryPages}
        onPageChange={(page) => void fetchHistory(page)}
        onSelectRun={(runId) => {
          void loadRun(runId);
          setIsHistoryDrawerOpen(false);
        }}
      />
    </>
  );
};

export default UserScannerPage;
