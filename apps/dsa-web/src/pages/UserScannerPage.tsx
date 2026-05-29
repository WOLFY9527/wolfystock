import React, { Suspense, lazy } from 'react';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ArrowDownUp,
  BookmarkPlus,
  ChevronDown,
  Copy,
  Download,
  History,
  LineChart,
  MoreHorizontal,
  Play,
  Sparkles,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { analysisApi, DuplicateTaskError } from '../api/analysis';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { scannerApi } from '../api/scanner';
import { watchlistApi } from '../api/watchlist';
import { ScannerActionButton as ActionButton } from '../components/scanner/ScannerActionButton';
import {
  ScannerCandidateDetailPanel,
  ScannerCandidateDiagnosticRow,
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
} from '../components/scanner/useScannerBacktestLab';
import type { ScannerBacktestItem } from '../components/scanner/scannerBacktestShared';
import {
  TerminalButton,
  TerminalChip,
  TerminalNestedBlock,
  TerminalPanel,
} from '../components/terminal/TerminalPrimitives';
import {
  CompactEmptyRow,
  DenseCommandBar,
  DensePageHeader,
  DenseStatusStrip,
  DenseTableShell,
} from '../components/terminal/DenseWorkbenchPrimitives';
import { ConsumerWorkspacePageShell, ConsumerWorkspaceScope } from '../components/layout/ConsumerWorkspaceShell';
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
import type { TrustDisclosureBucket } from '../utils/trustDisclosure';
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

const LazyScannerBacktestLab = lazy(async () => {
  const module = await import('../components/scanner/ScannerBacktestLab');
  return { default: module.ScannerBacktestLab };
});

const {
  getRunProviderDiagnostics,
  hasRunDiagnosticsContent,
} = ScannerDiagnosticsPanel;

const HISTORY_PAGE_SIZE = 8;

const SCANNER_TIMESTAMP_FMT_EN = new Intl.DateTimeFormat('en-US', {
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
});
const SCANNER_TIMESTAMP_FMT_ZH = new Intl.DateTimeFormat('zh-CN', {
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
});
const SCANNER_DATE_FMT_EN = new Intl.DateTimeFormat('en-US', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
});
const SCANNER_DATE_FMT_ZH = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
});

type PillOption = { value: string; label: string };
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
type ScannerTrustSummary = {
  cappedCount: number;
  fallbackCount: number;
  proxyCount: number;
  staleCount: number;
  partialCount: number;
  limitedCount: number;
  buckets: TrustDisclosureBucket[];
  terms: string[];
};
type ScannerConclusionModel = {
  state: 'waiting' | 'top-candidate' | 'no-candidate' | 'insufficient';
  title: string;
  detail: string;
  candidateCount: number;
  trustSummary: ScannerTrustSummary;
  tone: 'neutral' | 'success' | 'caution' | 'danger';
};
type ScannerWorkbenchEmptyState = {
  title: string;
  body: string;
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

function getNestedRecord(parent: Record<string, unknown> | null, ...keys: string[]): Record<string, unknown> | null {
  for (const key of keys) {
    const value = parent?.[key];
    if (isRecord(value)) return value;
  }
  return null;
}

function getNestedString(parent: Record<string, unknown> | null, ...keys: string[]): string | null {
  for (const key of keys) {
    const value = parent?.[key];
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return null;
}

function getNestedNumber(parent: Record<string, unknown> | null, ...keys: string[]): number | null {
  for (const key of keys) {
    const value = parent?.[key];
    if (typeof value === 'number' && Number.isFinite(value)) return value;
  }
  return null;
}

function getNestedBoolean(parent: Record<string, unknown> | null, ...keys: string[]): boolean | null {
  for (const key of keys) {
    const value = parent?.[key];
    if (typeof value === 'boolean') return value;
  }
  return null;
}

function getNestedStringArray(parent: Record<string, unknown> | null, ...keys: string[]): string[] {
  for (const key of keys) {
    const value = parent?.[key];
    if (Array.isArray(value)) {
      return value.reduce<string[]>((acc, item) => {
        if (typeof item === 'string' && item.trim()) acc.push(item.trim());
        return acc;
      }, []);
    }
  }
  return [];
}

function addUniqueBucket(buckets: TrustDisclosureBucket[], bucket: TrustDisclosureBucket) {
  if (!buckets.includes(bucket)) buckets.push(bucket);
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

function stripScannerConsumerTrustSource(source: ScannerCandidate | ScannerCandidateDiagnostic): ScannerCandidate | ScannerCandidateDiagnostic {
  if ('metadata' in source) {
    return {
      ...source,
      metadata: {},
    };
  }
  return {
    ...source,
    diagnostics: {},
  };
}

function consumerTrustNoticeFromBuckets(buckets: TrustDisclosureBucket[], language: 'zh' | 'en'): string | null {
  if (buckets.includes('stale') || buckets.includes('fallback')) {
    return language === 'en'
      ? 'Some results use the latest available data.'
      : '部分结果使用最近一次可用数据。';
  }
  if (buckets.includes('partial') || buckets.includes('proxy')) {
    return language === 'en'
      ? 'Some scan data is temporarily unavailable; current results are for observation.'
      : '部分扫描数据暂不可用，当前结果仅供观察。';
  }
  if (buckets.includes('confidence') || buckets.includes('observe-only')) {
    return language === 'en'
      ? 'Current candidate confidence is low.'
      : '当前候选信号置信度较低。';
  }
  return null;
}

function getScannerConsumerQualityNotice(source: ScannerCandidate | ScannerCandidateDiagnostic, language: 'zh' | 'en'): string | null {
  return consumerTrustNoticeFromBuckets(scannerTrustBucketsForSource(source).buckets, language);
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
  return (language === 'en' ? SCANNER_TIMESTAMP_FMT_EN : SCANNER_TIMESTAMP_FMT_ZH).format(date);
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
  if (['provider_down', 'provider_error', 'provider_failed', 'data_source_error'].includes(normalized)) return language === 'en' ? 'Data unavailable' : '数据暂不可用';
  if (['local_data', 'local', 'local_cache', 'local_snapshot'].includes(normalized)) return language === 'en' ? 'Recent available data' : '最近可用数据';
  if (['fallback', 'fallback_data', 'degraded'].includes(normalized)) return language === 'en' ? 'Recent available data' : '最近可用数据';
  if (['partial', 'partial_data', 'partial_success'].includes(normalized)) return language === 'en' ? 'Partial data' : '部分数据';
  if (!normalized || normalized === 'unknown') return language === 'en' ? 'Unconfirmed' : '未确认';
  return language === 'en' ? 'Unconfirmed' : '未确认';
}

function sanitizeScannerErrorSummary(value?: string | null, language: 'zh' | 'en' = 'zh'): string | null {
  const normalized = normalizeRunState(value);
  if (!normalized) return null;
  if (normalized.includes('timeout')) return language === 'en' ? 'Timeout' : '超时';
  if (String(value || '').includes('超时')) return language === 'en' ? 'Timeout' : '超时';
  if (normalized.includes('provider')) return language === 'en' ? 'Data unavailable' : '数据暂不可用';
  if (normalized.includes('history') || normalized.includes('missing') || normalized.includes('insufficient') || normalized.includes('not_enough')) {
    return language === 'en' ? 'Insufficient data' : '数据不足';
  }
  if (String(value || '').includes('不可用') || String(value || '').includes('缺失') || String(value || '').includes('不足')) {
    return language === 'en' ? 'Insufficient data' : '数据不足';
  }
  if (normalized.includes('candidate') || normalized.includes('shortlist') || normalized === 'empty') return language === 'en' ? 'No candidates' : '无候选';
  if (normalized.includes('fallback')) return language === 'en' ? 'Recent available data' : '最近可用数据';
  if (normalized.includes('local')) return language === 'en' ? 'Recent available data' : '最近可用数据';
  if (normalized.includes('partial')) return language === 'en' ? 'Partial data' : '部分数据';
  if (normalized.includes('failed') || normalized.includes('error')) return language === 'en' ? 'Failed' : '失败';
  return compactScannerStateLabel(value, language);
}

function formatDateOnly(value?: string | null, language: 'zh' | 'en' = 'zh'): string {
  if (!value) return '--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return (language === 'en' ? SCANNER_DATE_FMT_EN : SCANNER_DATE_FMT_ZH).format(date);
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
  return notes.reduce<string[]>((acc, item) => {
    const raw = String(item || '').trim();
    if (!raw) return acc;
    const sanitized = sanitizeScannerUserText(item, language, '');
    if (sanitized && acc.indexOf(sanitized) === -1) acc.push(sanitized);
    return acc;
  }, []);
}

function sanitizeScannerFieldLabel(label: string, language: 'zh' | 'en'): string {
  const normalized = normalizeLabel(label);
  if (['entry', 'entry range', '建仓', '入场', 'buy'].includes(normalized)) {
    return language === 'en' ? 'Observation zone' : '观察区';
  }
  if (['target', 'target price', '目标', '目标价'].includes(normalized)) {
    return language === 'en' ? 'Reference range' : '参考区间';
  }
  if (['stop', 'stop loss', '止损', '止损位'].includes(normalized)) {
    return language === 'en' ? 'Risk boundary' : '风险边界';
  }
  return label;
}

function sanitizeScannerLabeledValues(items: ScannerLabeledValue[] | undefined, language: 'zh' | 'en'): ScannerLabeledValue[] {
  return (items || []).map((item) => {
    const labelHasInternalDetail = isInternalScannerIssue(item.label);
    const valueHasInternalDetail = isInternalScannerIssue(item.value);
    if (!labelHasInternalDetail && !valueHasInternalDetail) {
      return {
        ...item,
        label: sanitizeScannerFieldLabel(item.label, language),
      };
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
    || (language === 'en' ? 'No data note' : '未提供数据说明');
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
  if (normalized.includes('local db') || normalized.includes('local')) return language === 'en' ? 'Recent available data' : '最近可用数据';
  return language === 'en' ? 'Available' : '可用';
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
  const trustNotice = getScannerConsumerQualityNotice(candidate, language);
  if (trustNotice) return trustNotice;
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
  if (provider === (language === 'en' ? 'Recent available data' : '最近可用数据')) return provider;
  return language === 'en' ? 'Verified' : '已验证';
}

function normalizeDiagnosticStatus(status: ScannerCandidateDiagnostic['status']): ScannerCandidateDiagnosticStatus {
  return status || 'skipped';
}

function diagnosticStatusLabel(status: ScannerCandidateDiagnostic['status'], language: 'zh' | 'en'): string {
  const labels: Record<ScannerCandidateDiagnosticStatus, { zh: string; en: string }> = {
    selected: { zh: '入选', en: 'Selected' },
    rejected: { zh: '淘汰', en: 'Rejected' },
    data_failed: { zh: '数据受限', en: 'Limited data' },
    skipped: { zh: '跳过', en: 'Skipped' },
    error: { zh: '数据暂不可用', en: 'Data unavailable' },
    evaluated: { zh: '已评估', en: 'Evaluated' },
  };
  const normalizedStatus = normalizeDiagnosticStatus(status);
  return labels[normalizedStatus]?.[language] || normalizedStatus;
}

function isOfficialSelected(candidate: ScannerCandidateDiagnostic): boolean {
  return normalizeDiagnosticStatus(candidate.status) === 'selected';
}

function isDataUnavailable(candidate: ScannerCandidateDiagnostic): boolean {
  const status = normalizeDiagnosticStatus(candidate.status);
  return status === 'data_failed' || status === 'error' || status === 'skipped';
}

function scannerTrustBucketsForSource(source: ScannerCandidate | ScannerCandidateDiagnostic): { buckets: TrustDisclosureBucket[]; terms: string[] } {
  const root = isRecord(source) ? source : null;
  const containers = [
    getNestedRecord(root, 'diagnostics'),
    getNestedRecord(root, 'metadata'),
  ].filter((value): value is Record<string, unknown> => Boolean(value));
  const buckets: TrustDisclosureBucket[] = [];
  const terms: string[] = [];

  containers.forEach((container) => {
    const explainability = getNestedRecord(container, 'scoreExplainability', 'score_explainability');
    const evidencePacket = getNestedRecord(container, 'evidencePacket', 'evidence_packet');
    const sourceConfidence = getNestedRecord(explainability, 'sourceConfidence', 'source_confidence')
      || getNestedRecord(evidencePacket, 'sourceConfidence', 'source_confidence');
    const providerObservation = getNestedRecord(evidencePacket, 'providerObservation', 'provider_observation');
    const freshnessDetail = getNestedRecord(evidencePacket, 'freshnessDetail', 'freshness_detail');
    const capReason = getNestedString(explainability, 'capReason', 'cap_reason')
      || getNestedString(evidencePacket, 'capReason', 'cap_reason')
      || getNestedString(sourceConfidence, 'capReason', 'cap_reason');
    const degradationReason = getNestedString(explainability, 'degradationReason', 'degradation_reason')
      || getNestedString(evidencePacket, 'degradationReason', 'degradation_reason')
      || getNestedString(sourceConfidence, 'degradationReason', 'degradation_reason');
    const scoreConfidence = getNestedNumber(explainability, 'scoreConfidence', 'score_confidence')
      ?? getNestedNumber(evidencePacket, 'scoreConfidence', 'score_confidence')
      ?? getNestedNumber(sourceConfidence, 'confidenceWeight', 'confidence_weight');
    const scoreGradeAllowed = getNestedBoolean(explainability, 'scoreGradeAllowed', 'score_grade_allowed');
    const scoreContributionAllowed = getNestedBoolean(sourceConfidence, 'scoreContributionAllowed', 'score_contribution_allowed')
      ?? getNestedBoolean(providerObservation, 'scoreContributionAllowed', 'score_contribution_allowed');
    const observationOnly = getNestedBoolean(sourceConfidence, 'observationOnly', 'observation_only')
      ?? getNestedBoolean(providerObservation, 'observationOnly', 'observation_only')
      ?? (scoreGradeAllowed === false || scoreContributionAllowed === false ? true : null);
    const fallbackFlag = getNestedBoolean(sourceConfidence, 'isFallback', 'is_fallback')
      ?? (normalizeRunState(getNestedString(sourceConfidence, 'freshness')) === 'fallback'
        || normalizeRunState(getNestedString(evidencePacket, 'freshnessState', 'freshness_state')) === 'fallback');
    const staleFlag = getNestedBoolean(sourceConfidence, 'isStale', 'is_stale')
      ?? (normalizeRunState(getNestedString(evidencePacket, 'freshnessState', 'freshness_state')) === 'stale');
    const partialFlag = getNestedBoolean(sourceConfidence, 'isPartial', 'is_partial')
      ?? (normalizeRunState(getNestedString(evidencePacket, 'dataQualityState', 'data_quality_state')) === 'partial');
    const sourceLabel = getNestedString(sourceConfidence, 'sourceLabel', 'source_label', 'source');
    const proxyFlag = getNestedBoolean(sourceConfidence, 'proxyOnly', 'proxy_only')
      ?? /proxy/.test(normalizeRunState([capReason, degradationReason, sourceLabel].filter(Boolean).join(' ')));
    const quoteFreshness = getNestedString(freshnessDetail, 'quoteState', 'quote_state');
    const historyFreshness = getNestedString(freshnessDetail, 'historyState', 'history_state');

    [
      capReason,
      degradationReason,
      sourceLabel,
      getNestedString(sourceConfidence, 'freshness'),
      getNestedString(evidencePacket, 'freshnessState', 'freshness_state'),
      getNestedString(evidencePacket, 'dataQualityState', 'data_quality_state'),
      quoteFreshness,
      historyFreshness,
      ...getNestedStringArray(evidencePacket, 'userFacingLabels', 'warningFlags'),
    ].forEach((term) => {
      if (term) terms.push(term);
    });

    if (capReason || scoreGradeAllowed === false || (scoreConfidence != null && scoreConfidence < 0.7)) addUniqueBucket(buckets, 'confidence');
    if (fallbackFlag) addUniqueBucket(buckets, 'fallback');
    if (proxyFlag) addUniqueBucket(buckets, 'proxy');
    if (staleFlag || normalizeRunState(quoteFreshness) === 'stale' || normalizeRunState(historyFreshness) === 'stale') addUniqueBucket(buckets, 'stale');
    if (partialFlag) addUniqueBucket(buckets, 'partial');
    if (observationOnly) addUniqueBucket(buckets, 'observe-only');
    if (scoreGradeAllowed === false || scoreContributionAllowed === false) addUniqueBucket(buckets, 'observe-only');
  });

  return { buckets, terms };
}

function buildScannerTrustSummary(runDetail: ScannerRunDetail | null): ScannerTrustSummary {
  const empty: ScannerTrustSummary = {
    cappedCount: 0,
    fallbackCount: 0,
    proxyCount: 0,
    staleCount: 0,
    partialCount: 0,
    limitedCount: 0,
    buckets: [],
    terms: [],
  };
  if (!runDetail) return empty;

  const sources = getCandidateDiagnostics(runDetail).length
    ? getCandidateDiagnostics(runDetail)
    : runDetail.shortlist || [];

  const summary = sources.reduce<ScannerTrustSummary>((current, source) => {
    const { buckets, terms } = scannerTrustBucketsForSource(source);
    const hasCapped = buckets.includes('confidence');
    const hasFallback = buckets.includes('fallback');
    const hasProxy = buckets.includes('proxy');
    const hasStale = buckets.includes('stale');
    const hasPartial = buckets.includes('partial');
    const hasLimited = hasCapped || hasFallback || hasProxy || hasStale;
    buckets.forEach((bucket) => addUniqueBucket(current.buckets, bucket));
    terms.forEach((term) => {
      if (!current.terms.includes(term)) current.terms.push(term);
    });
    return {
      cappedCount: current.cappedCount + Number(hasCapped),
      fallbackCount: current.fallbackCount + Number(hasFallback),
      proxyCount: current.proxyCount + Number(hasProxy),
      staleCount: current.staleCount + Number(hasStale),
      partialCount: current.partialCount + Number(hasPartial),
      limitedCount: current.limitedCount + Number(hasLimited),
      buckets: current.buckets,
      terms: current.terms,
    };
  }, { ...empty, buckets: [], terms: [] });

  if (runDetail.summary?.limitedByResultCap) {
    addUniqueBucket(summary.buckets, 'confidence');
    summary.cappedCount += 1;
    summary.limitedCount = Math.max(summary.limitedCount, 1);
    summary.terms.push('result capped');
  }

  return summary;
}

function buildScannerConclusion(runDetail: ScannerRunDetail | null, language: 'zh' | 'en'): ScannerConclusionModel {
  const trustSummary = buildScannerTrustSummary(runDetail);
  if (!runDetail) {
    return {
      state: 'waiting',
      title: language === 'en' ? 'Waiting for a scan' : '等待扫描',
      detail: language === 'en'
        ? 'Run or open a scan to see the candidate evidence summary.'
        : '运行或打开一次扫描后，可查看候选证据摘要。',
      candidateCount: 0,
      trustSummary,
      tone: 'neutral',
    };
  }

  const selectedCount = getRunSummaryCount(runDetail, 'selectedCount', runDetail.shortlist?.length || 0);
  const rejectedCount = getRunSummaryCount(runDetail, 'rejectedCount', 0);
  const failedCount = getRunSummaryCount(runDetail, 'dataFailedCount', 0) + getRunSummaryCount(runDetail, 'errorCount', 0);
  const diagnostics = getCandidateDiagnostics(runDetail);
  const allDiagnosticsUnavailable = diagnostics.length > 0 && diagnostics.every(isDataUnavailable);
  const runState = normalizeRunState(runDetail.status);
  const evidenceInsufficient = selectedCount === 0
    && (runState === 'failed'
      || runState === 'error'
      || allDiagnosticsUnavailable
      || (failedCount > 0 && rejectedCount === 0));

  if (evidenceInsufficient) {
    return {
      state: 'insufficient',
      title: language === 'en' ? 'Evidence insufficient' : '证据不足',
      detail: language === 'en'
        ? 'Refresh quotes or history evidence before treating this scan as evidence.'
        : '补齐行情或历史证据后，再将本次扫描视为证据。',
      candidateCount: selectedCount,
      trustSummary,
      tone: 'danger',
    };
  }

  const topCandidate = runDetail.shortlist?.[0]
    || diagnostics.find(isOfficialSelected)
    || null;
  if (selectedCount <= 0 || !topCandidate) {
    return {
      state: 'no-candidate',
      title: language === 'en' ? 'No usable candidate' : '本次无可用候选',
      detail: language === 'en'
        ? 'Continue observing the rejection mix and the next scan before treating this pool as evidence.'
        : '继续观察淘汰分布与下一次扫描变化，再将候选池视为证据。',
      candidateCount: selectedCount,
      trustSummary,
      tone: 'caution',
    };
  }

  const symbol = normalizeCandidateSymbol(topCandidate.symbol) || topCandidate.symbol || '--';
  return {
    state: 'top-candidate',
    title: language === 'en' ? `Current candidate ${symbol}` : `当前候选 ${symbol}`,
    detail: language === 'en'
      ? `Observe ${symbol}'s next update against the observation zone, reference range, and risk boundary before treating it as evidence.`
      : `观察 ${symbol} 的下一次更新，并对照观察区、参考区间与风险边界后再作为证据。`,
    candidateCount: selectedCount,
    trustSummary,
    tone: trustSummary.limitedCount > 0 ? 'caution' : 'success',
  };
}

function buildScannerWorkbenchEmptyState({
  candidateFilter,
  diagnosticCandidates,
  language,
  pageErrorSummary,
  runDetail,
}: {
  candidateFilter: CandidateFilter;
  diagnosticCandidates: ScannerCandidateDiagnostic[];
  language: 'zh' | 'en';
  pageErrorSummary: string | null;
  runDetail: ScannerRunDetail | null;
}): ScannerWorkbenchEmptyState {
  if (pageErrorSummary) {
    return {
      title: language === 'en' ? 'Scanner fetch failed' : '扫描读取失败',
      body: language === 'en'
        ? `${pageErrorSummary}. Retry later or open history.`
        : `${pageErrorSummary}。可稍后重试或打开历史记录。`,
    };
  }

  if (!runDetail) {
    return {
      title: language === 'en' ? 'No scan has run yet' : '尚未运行扫描',
      body: language === 'en'
        ? 'Use the top command bar to check market, universe, detailed review, and shortlist controls; open history for previous runs.'
        : '先在顶部命令栏确认市场、范围、评估深度与候选上限；如需已有结果可打开历史记录。',
    };
  }

  const selectedCount = getRunSummaryCount(runDetail, 'selectedCount', runDetail.shortlist?.length || 0);
  const rejectedCount = getRunSummaryCount(runDetail, 'rejectedCount', 0);
  const failedCount = getRunSummaryCount(runDetail, 'dataFailedCount', 0) + getRunSummaryCount(runDetail, 'errorCount', 0);
  const runState = normalizeRunState(runDetail.status);
  const allDiagnosticsUnavailable = diagnosticCandidates.length > 0 && diagnosticCandidates.every(isDataUnavailable);
  const evidenceInsufficient = selectedCount === 0
    && (runState === 'failed'
      || runState === 'error'
      || allDiagnosticsUnavailable
      || (failedCount > 0 && rejectedCount === 0));

  if (evidenceInsufficient) {
    return {
      title: language === 'en' ? 'Limited data or evidence insufficient' : '数据受限或证据不足',
      body: language === 'en'
        ? 'Switch the candidate view to Limited data to inspect row-level notes; retry later or open history.'
        : '切换候选视图到数据受限，查看行级说明；可稍后重试或打开历史记录。',
    };
  }

  if (selectedCount === 0 && diagnosticCandidates.length > 0) {
    return {
      title: language === 'en' ? 'No selected candidates' : '本次无入选候选',
      body: language === 'en'
        ? 'Switch the candidate view to Candidate pool or All to inspect rejected and limited-data rows, or adjust shortlist, universe, and detailed review controls in the top command bar.'
        : '切换候选视图到候选池或全部，查看淘汰与数据受限行；也可在顶部命令栏调整候选上限、范围或评估深度。',
    };
  }

  if (candidateFilter === 'data_failed') {
    return {
      title: language === 'en' ? 'No limited-data rows in this view' : '当前无数据受限行',
      body: language === 'en'
        ? 'Switch the candidate view to Candidate pool or All, or retry later if data availability changed.'
        : '切换候选视图到候选池或全部；如数据可用性变化，可稍后重试。',
    };
  }

  return {
    title: language === 'en' ? 'No rows in the current filter' : '当前过滤无候选行',
    body: language === 'en'
      ? 'Switch the candidate view, inspect limited-data rows, or adjust market, universe, detailed review, and shortlist controls in the top command bar.'
      : '切换候选视图、查看数据受限行，或在顶部命令栏调整市场、范围、评估深度与候选上限。',
  };
}

function isPreviewSelected(candidate: ScannerCandidateDiagnostic, threshold: number): boolean {
  return candidate.score != null && Number.isFinite(candidate.score) && candidate.score >= threshold && !isDataUnavailable(candidate);
}

function inferPreviewThreshold(runDetail: ScannerRunDetail | null, diagnostics: ScannerCandidateDiagnostic[]): number {
  const selectedScores = diagnostics.reduce<number[]>((acc, candidate) => {
    if (isOfficialSelected(candidate) && candidate.score != null && Number.isFinite(candidate.score)) {
      acc.push(candidate.score);
    }
    return acc;
  }, []);
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
  if (isDataUnavailable(candidate)) return language === 'en' ? 'Limited data' : '数据受限';
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
  for (const candidate of candidates) {
    if (candidate.status === 'selected') continue;
    const bucket = normalizeRejectionBucket(candidate);
    counts.set(bucket, (counts.get(bucket) || 0) + 1);
  }
  const order: RejectionBucketKey[] = ['trend', 'momentum', 'liquidity', 'risk', 'data', 'score', 'other'];
  return order.reduce<Array<{ label: string; value: string }>>((acc, key) => {
    const value = String(counts.get(key) || 0);
    if (value !== '0') acc.push({ label: rejectionBucketLabel(key, language), value });
    return acc;
  }, []);
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

function fallbackDiagnosticFromCandidate(candidate: ScannerCandidate): ScannerCandidateDiagnostic {
  return {
    symbol: candidate.symbol,
    name: candidate.companyName || candidate.name,
    rank: candidate.rank,
    status: 'selected',
    score: candidate.score,
    provider: null,
    reason: candidate.reasonSummary,
    failedRules: [],
    missingFields: [],
    metrics: Object.fromEntries((candidate.keyMetrics || []).map((item) => [item.label, item.value])),
    metadata: {},
  };
}

function formatWorkbenchWatchSummary(
  candidate: ScannerCandidate,
  language: 'zh' | 'en',
): string {
  const entryRange = getEntryRange(candidate);
  const targetPrice = getTargetPrice(candidate);
  if (!entryRange && !targetPrice) {
    return language === 'en' ? 'No explicit observation band' : '未提供明确观察区';
  }
  return [
    entryRange ? `${language === 'en' ? 'Observation zone' : '观察区'} ${entryRange}` : null,
    targetPrice ? `${language === 'en' ? 'Reference range' : '参考区间'} ${targetPrice}` : null,
  ].filter(Boolean).join(' · ');
}

function formatWorkbenchRangeSummary(
  candidate: ScannerCandidate,
  language: 'zh' | 'en',
): string {
  const stopLoss = getStopLoss(candidate);
  const riskSummary = getRiskSummary(candidate, language);
  if (!stopLoss && !riskSummary) {
    return language === 'en' ? 'No explicit risk boundary' : '未提供明确风险边界';
  }
  return [
    stopLoss ? `${language === 'en' ? 'Risk boundary' : '风险边界'} ${stopLoss}` : null,
    riskSummary || null,
  ].filter(Boolean).join(' · ');
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
        .flatMap((symbol) => {
          const trimmed = symbol.trim().toUpperCase();
          return trimmed ? [trimmed] : [];
        }),
    ),
  );
}

function getSymbolTokenCount(value: string): number {
  return value.split(/[\s,，;；]+/).reduce((count, symbol) => count + (symbol.trim() ? 1 : 0), 0);
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
        .flatMap((symbol) => {
          const trimmed = symbol.trim();
          return trimmed ? [trimmed] : [];
        }),
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
  observationZone: string;
  referenceRange: string;
  riskBoundary: string;
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
    observationZone: getEntryRange(candidate) || '',
    referenceRange: getTargetPrice(candidate) || '',
    riskBoundary: getStopLoss(candidate) || '',
    reason: getKeyReason(candidate, runDetail, language),
    risk: getRiskSummary(candidate, language),
    universeType: runDetail.universeType || '',
    theme: runDetail.themeLabel || runDetail.themeId || '',
    generatedAt: runDetail.completedAt || runDetail.runAt || '',
    runId: runDetail.id,
  };
}

function buildScannerCsv(rows: ScannerExportRow[]): string {
  const headers = ['rank', 'symbol', 'name', 'scannerScore', 'observationZone', 'referenceRange', 'riskBoundary', 'reason', 'risk', 'universeType', 'theme', 'generatedAt', 'runId'];
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
  compact = false,
}: {
  label: string;
  value: string;
  options: PillOption[];
  onChange: (next: string) => void;
  variant?: 'default' | 'market';
  testId?: string;
  compact?: boolean;
}) {
  const isMarketGroup = variant === 'market';

  return (
    <div className={compact ? 'flex min-w-0 flex-col gap-1 md:flex-row md:items-center md:gap-2' : 'flex min-w-0 flex-col gap-1.5'}>
      <span className={compact ? 'shrink-0 text-[10px] uppercase tracking-[0.16em] text-white/40' : 'text-[10px] uppercase tracking-[0.16em] text-white/40'}>{label}</span>
      <fieldset
        className={isMarketGroup
          ? 'ui-scroll-x-quiet flex min-w-0 max-w-full rounded-xl border border-white/5 bg-black/40 p-1'
          : 'border-0 p-0 flex min-w-0 flex-wrap gap-1.5'}
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
                  ? 'min-w-0 shrink-0 rounded-lg bg-white/10 px-3 py-1 text-xs font-bold text-white shadow-[0_2px_10px_rgba(0,0,0,0.5)] transition-all'
                  : 'min-w-0 rounded-full border border-white/10 bg-white/10 px-2.5 py-1 text-xs text-white transition-colors'
                : isMarketGroup
                  ? 'min-w-0 shrink-0 rounded-lg bg-transparent px-3 py-1 text-xs font-medium text-white/40 transition-all hover:text-white/70'
                  : 'min-w-0 rounded-full border border-white/5 bg-transparent px-2.5 py-1 text-xs text-white/50 transition-colors hover:bg-white/[0.05]'}
              onClick={() => onChange(option.value)}
            >
              <span className="ui-truncate block max-w-full">{option.label}</span>
            </button>
          );
        })}
      </fieldset>
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
          <CompactEmptyRow data-testid="scanner-history-empty-state" title={language === 'en' ? 'No scan history yet' : '暂无历史扫描'} className="min-h-[64px] px-3 py-2">
            {language === 'en' ? 'Run one scan to compare results.' : '运行一次扫描后可查看对比'}
          </CompactEmptyRow>
        ) : null}
        {currentSummary && !previousSummary ? (
          <CompactEmptyRow data-testid="scanner-previous-empty-state" className="min-h-[56px] px-3 py-2">
            {language === 'en' ? 'No previous scan · run once more to compare.' : '暂无历史扫描 · 运行一次扫描后可查看对比'}
          </CompactEmptyRow>
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

function ScannerConclusionBand({
  model,
  scopeLabel,
  dataStateLabel,
  latestLabel,
  language,
}: {
  model: ScannerConclusionModel;
  scopeLabel: string;
  dataStateLabel: string;
  latestLabel: string;
  language: 'zh' | 'en';
}) {
  const toneVariant: React.ComponentProps<typeof TerminalChip>['variant'] = model.tone === 'success'
    ? 'success'
    : model.tone === 'danger'
      ? 'danger'
      : model.tone === 'caution'
        ? 'caution'
        : 'neutral';
  const trust = model.trustSummary;
  const trustNotice = consumerTrustNoticeFromBuckets(trust.buckets, language);

  return (
    <TerminalPanel
      as="section"
      dense
      data-testid="scanner-conclusion-band"
      className="grid gap-3 p-3 md:grid-cols-[minmax(0,1fr)_minmax(220px,0.44fr)]"
    >
      <div className="min-w-0">
        <div className="flex min-w-0 flex-wrap items-center gap-1.5">
          <TerminalChip variant={toneVariant} className="shrink-0">
            {dataStateLabel}
          </TerminalChip>
          <TerminalChip variant="neutral" className="max-w-full font-mono">
            {scopeLabel}
          </TerminalChip>
          <TerminalChip variant="neutral" className="shrink-0 font-mono">
            {latestLabel}
          </TerminalChip>
        </div>
        <div className="mt-3 min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-white/40">
            {language === 'en' ? 'Candidate discovery surface' : '候选发现工作台'}
          </p>
          <div className="mt-1 flex min-w-0 flex-wrap items-end gap-2">
            <h2 className="truncate text-xl font-semibold text-white md:text-2xl">{model.title}</h2>
            <span className="text-xs text-white/44">
              {language === 'en' ? 'Candidates' : '候选'} {model.candidateCount}
            </span>
          </div>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-white/64">
            {model.detail}
          </p>
        </div>
      </div>
      <div className="grid gap-2 rounded-2xl border border-white/8 bg-white/[0.02] p-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-white/40">
            {language === 'en' ? 'Primary cue' : '当前提示'}
          </p>
          <p className="mt-1 text-sm leading-relaxed text-white/72">
            {model.state === 'top-candidate'
              ? (language === 'en' ? 'Review the ranked table first, then inspect the selected candidate rail.' : '先看排名主表，再查看右侧当前候选。')
              : model.state === 'waiting'
                ? (language === 'en' ? 'Choose the market scope, then run a scan or open history.' : '先确认市场范围，再启动扫描或打开历史记录。')
                : (language === 'en' ? 'Use the ranked rows as evidence and keep diagnostics collapsed until needed.' : '先使用候选行作为主证据，只有需要时再展开数据说明。')}
          </p>
        </div>
        {trustNotice ? (
          <div className="border-t border-white/8 pt-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-white/40">
              {language === 'en' ? 'Data cue' : '数据提示'}
            </p>
            <p className="mt-1 text-xs leading-relaxed text-white/58">
              {trustNotice}
            </p>
          </div>
        ) : null}
      </div>
    </TerminalPanel>
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
  const [previousRunDetail, setPreviousRunDetail] = useState<ScannerRunDetail | null>(null);
  const [previewThreshold, setPreviewThreshold] = useState(50);
  const [sortKey, setSortKey] = useState<SortKey>('score');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [inspectorSymbol, setInspectorSymbol] = useState<string | null>(null);
  const [pendingAnalyzeSymbol, setPendingAnalyzeSymbol] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [candidateFilter, setCandidateFilter] = useState<CandidateFilter>('selected');
  const [simulationLookbackDays, setSimulationLookbackDays] = useState(90);
  const [simulationForwardDays, setSimulationForwardDays] = useState(5);
  const [strategySimulation, setStrategySimulation] = useState<ScannerStrategySimulationResult | null>(null);
  const [isStrategySimulationLoading, setIsStrategySimulationLoading] = useState(false);
  const [strategySimulationError, setStrategySimulationError] = useState<string | null>(null);
  const [viewportWidth, setViewportWidth] = useState(() => (typeof window === 'undefined' ? 1440 : window.innerWidth));
  const selectedRunIdRef = useRef<number | null>(null);

  useEffect(() => {
    document.title = t('scanner.documentTitle');
  }, [t]);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const handleResize = () => setViewportWidth(window.innerWidth);
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const profileOptions = getScannerProfileOptions(market, t);
  const universeOptions = getScannerUniverseOptions(market, language);
  const detailOptions = getScannerDetailOptions(market, language);
  const marketThemes = themes.filter((theme) => theme.market === market);
  const configuredMarketThemes = marketThemes.filter((theme) => theme.symbols.length > 0);
  const unconfiguredMarketThemes = marketThemes.filter((theme) => theme.symbols.length === 0);
  const selectedTheme = marketThemes.find((theme) => theme.id === themeId) || null;
  const parsedCustomSymbols = parseCustomSymbols(customSymbols);
  const parsedThemeManualSymbols = parseCustomSymbols(customThemeManualSymbols);
  const customSymbolTokenCount = getSymbolTokenCount(customSymbols);
  const customThemeManualSymbolTokenCount = getSymbolTokenCount(customThemeManualSymbols);

  const handleMarketChange = (nextMarket: string) => {
    const normalizedMarket = nextMarket === 'us' ? 'us' : nextMarket === 'hk' ? 'hk' : 'cn';
    const defaults = SCANNER_PROFILE_DEFAULTS[normalizedMarket];
    setMarket(normalizedMarket);
    setProfile(defaults.profile);
    setShortlistSize(defaults.shortlistSize);
    setUniverseLimit(defaults.universeLimit);
    setDetailLimit(defaults.detailLimit);
    setThemeId('');
    setValidationErrors({});
  };

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
  }, [market, profile, loadRun]);

  useEffect(() => {
    setRunDetail(null);
    selectedRunIdRef.current = null;
    setSelectedRunId(null);
    setStrategySimulation(null);
    setStrategySimulationError(null);
  }, [market, profile]);

  useEffect(() => {
    void fetchHistory(1);
  }, [fetchHistory]);

  const handleRun = async () => {
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
      setValidationErrors({});
      setPageError(null);
      await fetchHistory(1, response.id);
    } catch (error) {
      setPageError(getParsedApiError(error));
    } finally {
      setIsRunning(false);
    }
  };

  const handleGenerateTheme = async () => {
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
  };

  const handleSortChange = (nextSortKey: SortKey) => {
    if (sortKey === nextSortKey) {
      setSortDirection((current) => current === 'asc' ? 'desc' : 'asc');
      return;
    }
    setSortKey(nextSortKey);
    setSortDirection(nextSortKey === 'symbol' ? 'asc' : 'desc');
  };

  const totalHistoryPages = Math.max(1, Math.ceil(historyTotal / HISTORY_PAGE_SIZE));
  const trackedWatchlistIdentitySet = new Set(watchlistItems.map((item) => getWatchlistIdentity(item.market, item.symbol)));
  const {
    ref: runScannerButtonRef,
    onClick: handleRunScannerClick,
    onPointerUp: handleRunScannerPointerUp,
  } = useSafariWarmActivation<HTMLButtonElement>(() => {
    void handleRun();
  });
  const {
    ref: generateThemeButtonRef,
    onClick: handleGenerateThemeClick,
    onPointerUp: handleGenerateThemePointerUp,
  } = useSafariWarmActivation<HTMLButtonElement>(() => {
    void handleGenerateTheme();
  });
  const {
    ref: openHistoryDrawerButtonRef,
    onClick: handleOpenHistoryDrawerClick,
    onPointerUp: handleOpenHistoryDrawerPointerUp,
  } = useSafariWarmActivation<HTMLButtonElement>(() => setIsHistoryDrawerOpen(true));
  const shortlistCount = runDetail?.shortlist?.length ?? 0;
  const generatedAt = runDetail?.completedAt || runDetail?.runAt || null;
  const runDisabled = isRunning;
  const generateThemeDisabled = isGeneratingTheme;

  const sortedCandidates = (() => {
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
  })();
  const diagnosticCandidates = getCandidateDiagnostics(runDetail);
  const hasCandidateDiagnostics = diagnosticCandidates.length > 0;
  const inferredPreviewThreshold = inferPreviewThreshold(runDetail, diagnosticCandidates);
  useEffect(() => {
    if (!runDetail) return;
    setPreviewThreshold(inferredPreviewThreshold);
  }, [inferredPreviewThreshold, runDetail]);
  const previewSelectedDiagnostics = diagnosticCandidates.filter((candidate) => isPreviewSelected(candidate, previewThreshold));
  const officialSelectedDiagnostics = diagnosticCandidates.filter(isOfficialSelected);
  const rejectionBuckets = buildRejectionBuckets(diagnosticCandidates, language);
  const comparisonState = buildRunComparison(runDetail, previousRunDetail, previewThreshold, language);
  const currentRunSummary = buildScannerRunSummary(language === 'en' ? 'Current scan' : '本次扫描', runDetail, language);
  const recentRunSummary = buildHistoryItemSummary(language === 'en' ? 'Latest scan' : '最近扫描', historyItems[0] || null, language);
  const previousRunSummary = buildScannerRunSummary(language === 'en' ? 'Previous scan' : '上次扫描', previousRunDetail, language);
  const comparisonHighlights = buildRunComparisonHighlights(runDetail, previousRunDetail, comparisonState, language);
  const filteredDiagnosticCandidates = (() => {
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
  })();
  const decisionSortedDiagnosticCandidates = sortDiagnosticsForDecision(filteredDiagnosticCandidates, previewThreshold);
  const shortlistCandidateBySymbol = new Map(sortedCandidates.map((candidate) => [normalizeCandidateSymbol(candidate.symbol), candidate] as const));
  const workbenchDiagnostics = hasCandidateDiagnostics ? decisionSortedDiagnosticCandidates : sortedCandidates.map(fallbackDiagnosticFromCandidate);
  const activeDetailDiagnostic = (() => {
    if (!workbenchDiagnostics.length) return null;
    const normalizedInspector = normalizeCandidateSymbol(inspectorSymbol);
    if (normalizedInspector) {
      const matched = workbenchDiagnostics.find((candidate) => normalizeCandidateSymbol(candidate.symbol) === normalizedInspector);
      if (matched) return matched;
    }
    return workbenchDiagnostics[0] || null;
  })();
  const activeDetailCandidate = (() => {
    if (!activeDetailDiagnostic) return null;
    return shortlistCandidateBySymbol.get(normalizeCandidateSymbol(activeDetailDiagnostic.symbol)) || diagnosticToCandidate(activeDetailDiagnostic);
  })();
  const topFiveDiagnostics = sortDiagnosticsForDecision(diagnosticCandidates, previewThreshold).slice(0, 5);
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
      current_filter: workbenchDiagnostics.map((candidate) => shortlistCandidateBySymbol.get(normalizeCandidateSymbol(candidate.symbol)) || diagnosticToCandidate(candidate)),
    },
  });
  const activeDetailBacktestItem = getBacktestItem(activeDetailCandidate?.symbol);
  const activeDetailWatchlistIdentity = activeDetailDiagnostic
    ? getWatchlistIdentity(runDetail?.market || market, activeDetailDiagnostic.symbol)
    : '';
  const activeDetailTracked = Boolean(activeDetailWatchlistIdentity && trackedWatchlistIdentitySet.has(activeDetailWatchlistIdentity));
  const activeDetailTrackPending = pendingWatchlistIdentity === activeDetailWatchlistIdentity;
  const activeSimulationTheme = runDetail?.themeId || (scanScope === 'theme' ? themeId : null);
  const strategySimulationDisabled = !runDetail || (runDetail.universeType === 'theme' && !runDetail.themeId);
  const showDetailRail = viewportWidth >= 1600 && Boolean(activeDetailCandidate);

  const handleStrategySimulation = async () => {
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
  };

  useEffect(() => {
    if (!hasCandidateDiagnostics && candidateFilter !== 'selected') {
      setCandidateFilter('selected');
    }
  }, [candidateFilter, hasCandidateDiagnostics]);

  useEffect(() => {
    if (!workbenchDiagnostics.length) {
      setInspectorSymbol(null);
      return;
    }
    const current = activeDetailDiagnostic;
    if (current && (!inspectorSymbol || normalizeCandidateSymbol(current.symbol) !== normalizeCandidateSymbol(inspectorSymbol))) {
      setInspectorSymbol(current.symbol);
    }
  }, [activeDetailDiagnostic, inspectorSymbol, workbenchDiagnostics]);

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

  const historyCards = historyItems.map((item) => {
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
  });
  const emptyStateTitle = language === 'en' ? 'No scan has run yet' : '尚未运行扫描';
  const emptyStateBody = language === 'en'
    ? 'Use the top command bar to check market, universe, detailed review, and shortlist controls.'
    : '先在顶部命令栏确认市场、范围、评估深度与候选上限。';
  const pageErrorSummary = pageError ? sanitizeScannerErrorSummary(pageError.message, language) || compactScannerStateLabel('failed', language) : null;
  const workbenchEmptyState = buildScannerWorkbenchEmptyState({
      candidateFilter,
      diagnosticCandidates,
      language,
      pageErrorSummary,
      runDetail,
    });
  const handleAnalyzeCandidate = async (candidate: ScannerCandidate) => {
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
  };

  const handleCopyText = async (text: string, nextCopiedKey: string) => {
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
  };

  const handleExportRows = (rows: ScannerExportRow[], filename: string) => {
    try {
      downloadScannerCsv(filename, buildScannerCsv(rows));
      setActionNotice(null);
    } catch (error) {
      setActionNotice({
        tone: 'danger',
        message: error instanceof Error ? error.message : (language === 'en' ? 'Export failed.' : '导出失败。'),
      });
    }
  };

  const handleTrackCandidate = async (candidate: ScannerCandidate) => {
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
  };

  const handleBatchTrackCandidates = async (batchKey: string, candidates: ScannerCandidate[]) => {
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
  };

  const getBacktestActionLabel = (item?: ScannerBacktestItem) => (
    item?.status === 'running' || item?.status === 'queued'
      ? (language === 'en' ? 'Running' : '运行中')
      : (language === 'en' ? 'Backtest' : '回测')
  );

  const renderCandidateDetailPanel = (
    candidate: ScannerCandidate,
    isTracked: boolean,
    isTrackPending: boolean,
    summaryOverride?: string | null,
    backtestItem?: ScannerBacktestItem,
  ) => {
    if (!runDetail) return null;
    const ai = candidate.aiInterpretation;
    const detailQualityNotice = getScannerConsumerQualityNotice(candidate, language);
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
    const compactNotes = sanitizeScannerNotes([
      candidate.reasonSummary,
      ...(candidate.reasons || []),
      ...(runDetail.scoringNotes || []),
    ], language);
    const compactRiskNotes = sanitizeScannerNotes(candidate.riskNotes || [], language);
    const compactMetricItems = sanitizeScannerLabeledValues(candidate.keyMetrics, language).slice(0, 3);
    const compactAiLines = [ai?.summary, ai?.watchPlan, ai?.riskInterpretation].filter((item): item is string => Boolean(item)).slice(0, 2);

    return (
      <div data-testid={`scanner-result-detail-${getCandidateIdentity(candidate)}`} className="space-y-3">
        <div className="rounded-xl border border-white/8 bg-white/[0.02] p-3">
          <div className="flex min-w-0 items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex min-w-0 items-center gap-2">
                <span className="truncate font-mono text-lg font-semibold text-white">{candidate.symbol || '--'}</span>
                <span className="rounded border border-white/8 bg-white/[0.04] px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-white/72">
                  {language === 'en' ? 'Focus candidate' : '当前候选'}
                </span>
              </div>
              <p className="mt-1 truncate text-xs text-white/42">{candidate.companyName || candidate.name || candidate.symbol || '--'}</p>
              {detailQualityNotice ? (
                <p className="mt-2 max-w-[32rem] text-[11px] leading-relaxed text-white/52">
                  {detailQualityNotice}
                </p>
              ) : null}
            </div>
            <div className="shrink-0 text-right">
              <div className="flex flex-wrap justify-end gap-1.5">
                <FieldChip label={language === 'en' ? 'Score' : '评分'} value={candidate.score != null ? `${candidate.score}/100` : '--'} />
                <FieldChip label={language === 'en' ? 'Rank' : '排名'} value={candidate.rank ? `#${candidate.rank}` : '--'} />
              </div>
            </div>
          </div>
        </div>

        <div className="grid gap-2 rounded-xl border border-white/8 bg-white/[0.015] p-3">
          <div className="grid grid-cols-[56px_minmax(0,1fr)] gap-2 border-b border-white/8 pb-2">
            <span className="text-[10px] uppercase tracking-[0.14em] text-white/36">{language === 'en' ? 'Why now' : '当前信号'}</span>
            <p className="min-w-0 text-xs leading-relaxed text-white/72">
              {summaryOverride || compactNotes[0] || candidate.reasonSummary || compactMetricItems[0]?.value || ai?.status || (language === 'en' ? 'No decision note' : '暂无结论')}
            </p>
          </div>
          <div className="grid grid-cols-[56px_minmax(0,1fr)] gap-2 border-b border-white/8 pb-2">
            <span className="text-[10px] uppercase tracking-[0.14em] text-white/36">{language === 'en' ? 'Risk' : '风险'}</span>
            <p className="min-w-0 text-xs leading-relaxed text-white/64">
              {compactRiskNotes[0] || candidate.riskNotes?.[0] || (language === 'en' ? 'No risk note' : '暂无风险说明')}
            </p>
          </div>
          <div className="grid grid-cols-[56px_minmax(0,1fr)] gap-2">
            <span className="text-[10px] uppercase tracking-[0.14em] text-white/36">{language === 'en' ? 'Next' : '下一步'}</span>
            <div className="flex min-w-0 flex-wrap gap-1.5">
              {getEntryRange(candidate) ? <FieldChip label={language === 'en' ? 'Observation zone' : '观察区'} value={getEntryRange(candidate) || '--'} /> : null}
              {getTargetPrice(candidate) ? <FieldChip label={language === 'en' ? 'Reference range' : '参考区间'} value={getTargetPrice(candidate) || '--'} /> : null}
              {getStopLoss(candidate) ? <FieldChip label={language === 'en' ? 'Risk boundary' : '风险边界'} value={getStopLoss(candidate) || '--'} /> : null}
              {!getEntryRange(candidate) && !getTargetPrice(candidate) && !getStopLoss(candidate) ? (
                <span className="text-xs text-white/44">
                  {language === 'en' ? 'Watch the next update before acting on this idea.' : '先观察下一次更新，再决定是否继续跟踪。'}
                </span>
              ) : null}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap gap-1.5">
          {compactMetricItems.slice(0, 2).map((item) => (
            <FieldChip key={`${item.label}-${item.value}`} label={item.label} value={item.value} />
          ))}
          {outcomeItems.slice(0, 2).map((item) => (
            <FieldChip key={`${item.label}-${item.value}`} label={item.label} value={item.value} />
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <ActionButton
            label={pendingAnalyzeSymbol === candidate.symbol ? (language === 'en' ? 'Analyzing...' : '分析中...') : (language === 'en' ? 'Analyze' : '分析')}
            icon={<Play className="size-3.5" />}
            onClick={() => void handleAnalyzeCandidate(candidate)}
            disabled={pendingAnalyzeSymbol === candidate.symbol}
            variant="compact"
          />
          <ActionButton
            label={getWatchlistActionLabel(isTracked, isTrackPending, watchlistAuthBlocked, language)}
            icon={<BookmarkPlus className="size-3.5" />}
            onClick={() => void handleTrackCandidate(candidate)}
            disabled={isTrackPending || isTracked || watchlistAuthBlocked}
            variant="compact"
            title={getWatchlistActionTitle(isTracked, watchlistAuthBlocked, language)}
          />
          <ActionButton
            label={getBacktestActionLabel(backtestItem)}
            icon={<LineChart className="size-3.5" />}
            onClick={() => void handleBacktestCandidate(candidate)}
            disabled={!candidate.symbol || backtestItem?.status === 'running' || backtestItem?.status === 'queued'}
            title={!normalizeCandidateSymbol(candidate.symbol) ? backtestUnavailableLabel : undefined}
            variant="compact"
          />
          <ActionButton
            label={copiedKey === `candidate:${candidate.symbol}` ? (language === 'en' ? 'Copied' : '已复制') : (language === 'en' ? 'Copy symbol' : '复制代码')}
            icon={<Copy className="size-3.5" />}
            onClick={() => void handleCopyText(candidate.symbol, `candidate:${candidate.symbol}`)}
            variant="compact"
          />
          <ActionButton
            label={language === 'en' ? 'Export' : '导出'}
            icon={<Download className="size-3.5" />}
            onClick={() => handleExportRows(
              [buildScannerExportRow(candidate, runDetail, language)],
              buildScannerExportFilename(runDetail, `candidate-${candidate.symbol}`),
            )}
            variant="compact"
          />
        </div>

        <AdvancedDisclosure
          testId={`scanner-result-detail-more-${getCandidateIdentity(candidate)}`}
          title={language === 'en' ? 'Candidate notes' : '候选说明'}
          summary={language === 'en' ? 'Metrics, signals, realized outcome, supporting context' : '指标、信号、复盘结果与补充说明'}
          icon="more"
        >
          <div className="max-h-[min(34vh,20rem)] overflow-y-auto no-scrollbar ui-scroll-y-quiet">
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
              aiLines={compactAiLines}
              aiUnavailableText={sanitizeScannerUserText(ai?.status, language, language === 'en' ? 'AI interpretation not available' : 'AI 解读不可用')}
              outcomeItems={outcomeItems}
              providerNotes={null}
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
          </div>
        </AdvancedDisclosure>
      </div>
    );
  };

  const scannerScopeLabel = runDetail
    ? `${runDetail.market.toUpperCase()} · ${runDetail.universeType === 'theme' ? (language === 'en' ? 'Theme universe' : '主题标的池') : runDetail.universeType === 'custom' || runDetail.universeType === 'symbols' ? (language === 'en' ? 'Custom symbols' : '自定义标的') : (language === 'en' ? 'Default universe' : '默认市场池')}`
    : `${market.toUpperCase()} · ${scanScope === 'theme' ? (language === 'en' ? 'Theme universe' : '主题标的池') : scanScope === 'symbols' ? (language === 'en' ? 'Custom symbols' : '自定义标的') : (language === 'en' ? 'Default universe' : '默认市场池')}`;
  const scannerThemeLabel = runDetail?.themeLabel || runDetail?.themeId || (selectedTheme ? getThemeLabel(selectedTheme, language) : (language === 'en' ? 'No theme' : '无主题'));
  const scannerDataStateLabel = runDetail
    ? `${normalizeRunState(runDetail.status) === 'failed' || normalizeRunState(runDetail.status) === 'error' ? `${currentRunSummary?.statusLabel || compactScannerStateLabel(runDetail.status, language)} · ` : ''}${getRunDataStatusLabel(runDetail, language)}`
    : (language === 'en' ? 'Waiting' : '等待');
  const scannerConclusion = buildScannerConclusion(runDetail, language);
  const heroLatestLabel = `${language === 'en' ? 'Latest' : '最近'} ${generatedAt ? formatTimestamp(generatedAt, language) : '--'}`;
  const scannerStatusItems = [
    {
      label: language === 'en' ? 'Best candidate' : '最佳候选',
      value: activeDetailCandidate
        ? `${activeDetailCandidate.symbol || '--'} · ${activeDetailCandidate.companyName || activeDetailCandidate.name || '--'}`
        : (scannerConclusion.state === 'waiting'
          ? (language === 'en' ? 'Waiting for a scan' : '等待扫描')
          : (language === 'en' ? 'No candidate yet' : '暂无候选')),
    },
    {
      label: language === 'en' ? 'Candidate mix' : '候选分布',
      value: `${shortlistCount} / ${runDetail?.summary?.rejectedCount ?? 0} / ${runDetail?.summary?.dataFailedCount ?? 0}`,
    },
    {
      label: language === 'en' ? 'Signal state' : '信号状态',
      value: generatedAt ? `${scannerDataStateLabel} · ${formatTimestamp(generatedAt, language)}` : scannerDataStateLabel,
    },
  ];

  return (
    <>
      <div
        ref={surfaceRef}
        data-testid="scanner-ranking-board-page"
        aria-hidden={shouldGuardA11y && !isSafariReady ? true : undefined}
        aria-live={shouldGuardA11y ? (isSafariReady ? 'polite' : 'off') : undefined}
        className={getSafariReadySurfaceClassName(
          isSafariReady,
          'flex w-full flex-1 flex-col min-w-0 bg-transparent text-foreground',
        )}
      >
          <ConsumerWorkspaceScope data-testid="scanner-wide-workspace-scope" className="flex-1">
	        <ConsumerWorkspacePageShell
	          data-testid="user-scanner-workspace"
	          className="flex-1 gap-3"
	        >
            <div data-testid="scanner-header-strip" className="flex min-w-0 flex-col gap-3">
              {/* <TerminalPageHeading /> marker: DensePageHeader emits the page-level h1. */}
              <DensePageHeader
                data-testid="scanner-page-heading"
                eyebrow={runDetail ? `${runDetail.market.toUpperCase()} · ${runDetail.profileLabel || runDetail.profile}` : (language === 'en' ? 'Candidate workbench' : '候选工作台')}
                title={language === 'en' ? 'Scanner' : '扫描器'}
                action={(
                  <TerminalButton
                    ref={openHistoryDrawerButtonRef}
                    type="button"
                    variant="secondary"
                    data-testid="scanner-history-trigger"
                    onClick={handleOpenHistoryDrawerClick}
                    onPointerUp={handleOpenHistoryDrawerPointerUp}
                    className="h-9 px-3 text-xs"
                  >
                    <History className="size-3.5" aria-hidden="true" />
                    <span>{language === 'en' ? 'History' : '历史'}</span>
                  </TerminalButton>
                )}
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
                  className={`border-y px-3 py-2 text-sm ${
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

              <ScannerConclusionBand
                model={scannerConclusion}
                scopeLabel={scannerScopeLabel}
                dataStateLabel={scannerDataStateLabel}
                latestLabel={heroLatestLabel}
                language={language}
              />
              <DenseStatusStrip
                data-testid="scanner-status-strip"
                ariaLabel={language === 'en' ? 'Scanner summary strip' : '扫描摘要条'}
                items={scannerStatusItems}
                className="ui-scroll-x-quiet flex-nowrap overflow-x-auto border-y border-white/10 bg-transparent px-2 py-1"
              />
            </div>

		          <div data-testid="scanner-workspace-grid" className="w-full flex-1 min-w-0">
                <DenseTableShell
                  data-testid="scanner-launch-bar"
                  variant="board"
                  className="flex min-h-[520px] flex-1 flex-col"
                >
                  <DenseCommandBar
                    data-testid="scanner-command-bar"
                    className="bg-transparent p-2"
                  >
                    <div className="grid min-w-0 grid-cols-2 gap-1 xl:grid-cols-[minmax(112px,0.55fr)_minmax(150px,0.72fr)_minmax(106px,0.45fr)_minmax(156px,0.72fr)_minmax(118px,0.5fr)_minmax(118px,0.5fr)_auto] xl:items-end">
                      <PillTagGroup compact label={t('scanner.marketLabel')} value={market} onChange={(next) => handleMarketChange(next as 'cn' | 'us' | 'hk')} options={[{ value: 'cn', label: t('scanner.marketCn') }, { value: 'us', label: t('scanner.marketUs') }, { value: 'hk', label: t('scanner.marketHk') }]} variant="market" testId="scanner-market-toggle" />
                      <PillTagGroup compact label={t('scanner.profileLabel')} value={profile} onChange={setProfile} options={profileOptions} />
                      <PillTagGroup compact label={t('scanner.shortlistLabel')} value={shortlistSize} onChange={setShortlistSize} options={[{ value: '5', label: language === 'en' ? 'Top 5' : '前 5' }, { value: '8', label: language === 'en' ? 'Top 8' : '前 8' }, { value: '10', label: language === 'en' ? 'Top 10' : '前 10' }]} />
                      <div data-testid="scanner-launch-controls" className="contents">
                        <PillTagGroup
                          compact
                          label={language === 'en' ? 'Universe' : '标的池'}
                          value={scanScope}
                          onChange={(next) => setScanScope(next as ScanScope)}
                          options={[
                            { value: 'default', label: language === 'en' ? 'Default market universe' : '默认市场池' },
                            { value: 'theme', label: language === 'en' ? 'Theme universe' : '主题标的池' },
                            { value: 'symbols', label: language === 'en' ? 'Custom symbols' : '自定义标的' },
                          ]}
                          testId="scanner-scope-selector"
                        />
                        <PillTagGroup compact label={t('scanner.universeLabel')} value={universeLimit} onChange={setUniverseLimit} options={universeOptions} />
                        <PillTagGroup compact label={t('scanner.detailLabel')} value={detailLimit} onChange={setDetailLimit} options={detailOptions} />
                      </div>
                      <TerminalButton
                        ref={runScannerButtonRef}
                        type="button"
                        onClick={handleRunScannerClick}
                        onPointerUp={handleRunScannerPointerUp}
                        disabled={runDisabled}
                        aria-busy={isRunning}
                        data-testid="scanner-run-button"
                        className="group col-span-2 h-8 w-full px-3 text-sm font-bold active:scale-95 disabled:pointer-events-none xl:col-span-1 xl:min-w-[132px]"
                        variant="primary"
                      >
                        <Play className="size-4 group-hover:animate-pulse" />
                        <span>{isRunning ? t('scanner.running') : (language === 'zh' ? '启动扫描' : t('scanner.run'))}</span>
                      </TerminalButton>
                    </div>
                    {scanScope !== 'default' ? (
                      <AdvancedDisclosure
                        testId="scanner-advanced-controls"
                        title={language === 'en' ? 'Advanced controls' : '高级参数'}
                        summary={language === 'en' ? 'Theme or custom-symbol inputs only' : '仅主题或自定义标的输入'}
                        icon="more"
                      >
                        {scanScope === 'theme' ? (
                          <div className="flex min-w-0 flex-col gap-1.5" data-testid="scanner-theme-control">
                            <span className="text-[10px] uppercase tracking-[0.16em] text-white/40">{language === 'en' ? 'Theme' : '主题'}</span>
                            <div className="select-field__control ui-control-shell group relative min-w-0 w-full max-w-full">
                              <select
                                data-testid="scanner-theme-select"
                                value={themeId}
                                className="select-surface absolute inset-0 z-10 size-full min-w-0 cursor-pointer appearance-none truncate rounded-lg pr-10 opacity-0 outline-none"
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
                                <ChevronDown className="select-field__icon ui-control-icon ml-2 size-4 shrink-0 text-white/40" aria-hidden="true" />
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
                            <div className="mt-2 flex flex-col gap-2 border-t border-white/8 pt-2" data-testid="scanner-ai-theme-builder">
                              <div className="flex items-center gap-2 text-[11px] font-medium text-white/70">
                                <Sparkles className="size-3.5 text-indigo-200/80" aria-hidden="true" />
                                <span>{language === 'en' ? 'AI custom theme' : 'AI 自定义主题'}</span>
                              </div>
                              <input
                                data-testid="scanner-ai-theme-label-input"
                                value={customThemeLabel}
                                className="w-full appearance-none rounded-lg border border-white/8 bg-black/40 px-2.5 py-1.5 text-xs text-white outline-none placeholder:text-white/20 focus:border-indigo-400/50"
                                onChange={(event) => setCustomThemeLabel(event.target.value)}
                                aria-label={language === 'en' ? 'AI custom theme name' : 'AI 自定义主题名称'}
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
                                aria-label={language === 'en' ? 'AI custom theme criteria' : 'AI 自定义主题筛选条件'}
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
                                aria-label={language === 'en' ? 'Manual symbol additions' : '手动补充标的代码'}
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
                                ref={generateThemeButtonRef}
                                type="button"
                                variant="secondary"
                                disabled={generateThemeDisabled}
                                onPointerUp={handleGenerateThemePointerUp}
                                onClick={handleGenerateThemeClick}
                                className="h-8 px-3 text-xs"
                              >
                                <Sparkles className="size-3.5" aria-hidden="true" />
                                <span>{isGeneratingTheme ? (language === 'en' ? 'Generating...' : '生成中...') : (language === 'en' ? 'Generate theme' : '生成主题')}</span>
                              </TerminalButton>
                              {themeSuggestions.length ? (
                                <div className="flex flex-col gap-1.5" data-testid="scanner-ai-theme-suggestions">
                                  {themeSuggestions.slice(0, 6).map((suggestion) => (
                                    <div key={suggestion.symbol} className="shrink-0 border-t border-white/8 px-0 py-1.5">
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
                              aria-label={language === 'en' ? 'Custom symbols' : '自定义代码'}
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
                    ) : null}
                    {validationErrors.run ? (
                      <p role="alert" className="text-[11px] leading-relaxed text-rose-100/82">
                        {validationErrors.run}
                      </p>
                    ) : null}
                  </DenseCommandBar>

                  <div data-testid="scanner-ranked-workbench" className="flex min-h-0 flex-1 min-w-0 flex-col border-t border-white/10">
                    <div data-testid="scanner-primary-actions" className="flex shrink-0 flex-row flex-wrap items-center justify-between gap-2 p-2">
                      <div className="flex min-w-0 flex-row flex-wrap items-center gap-2">
                        {runDetail && hasCandidateDiagnostics ? (
                          <div data-testid="scanner-compact-filter-bar" className="min-w-0">
                            <fieldset data-testid="scanner-candidate-filters" className="border-0 p-0 ui-scroll-x-quiet flex min-w-0 max-w-full gap-1 border-r border-white/10 pr-2" aria-label={language === 'en' ? 'Candidate view' : '候选视图'}>
                              {([
                                ['selected', language === 'en' ? 'Selected' : '入选'],
                                ['pool', language === 'en' ? 'Candidate pool' : '候选池'],
                                ['rejected', language === 'en' ? 'Rejected' : '淘汰'],
                                ['data_failed', language === 'en' ? 'Limited data' : '数据受限'],
                                ['all', language === 'en' ? 'All' : '全部'],
                              ] as const).map(([key, label]) => (
                                <button
                                  key={key}
                                  type="button"
                                  className={`inline-flex shrink-0 items-center rounded-md border px-2 py-0.5 text-xs ${
                                    candidateFilter === key
                                      ? 'border-white/16 bg-white/[0.08] text-white'
                                      : 'border-transparent text-white/45 hover:text-white/75'
                                  }`}
                                  onClick={() => setCandidateFilter(key)}
                                >
                                  <span className="ui-truncate block">{label}</span>
                                </button>
                              ))}
                            </fieldset>
                          </div>
                        ) : null}
                        <div data-testid="scanner-ranked-sortbar" className="flex flex-wrap items-center gap-1.5 text-xs text-white/42">
                          <span>{language === 'en' ? 'Sort by' : '排序'}</span>
                          {([
                            ['score', language === 'en' ? 'scanner score' : '扫描评分'],
                            ['symbol', language === 'en' ? 'symbol' : '代码'],
                            ['target', language === 'en' ? 'reference range' : '参考区间'],
                            ['risk', language === 'en' ? 'risk' : '风险'],
                          ] as const).map(([key, label]) => (
                            <button
                              key={key}
                              type="button"
                              className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 ${sortKey === key ? 'border-white/16 bg-white/[0.08] text-white' : 'border-white/5 bg-white/[0.02] text-white/48 hover:text-white/75'}`}
                              onClick={() => handleSortChange(key)}
                            >
                              {label}
                              {sortKey === key ? <ArrowDownUp className="size-3" /> : null}
                            </button>
                          ))}
                        </div>
                      </div>
                      <div className="flex min-w-0 flex-row flex-wrap items-center justify-end gap-2">
                        {runDetail ? (
                          <div data-testid="scanner-summary-counters" className="flex flex-wrap items-center gap-1.5 text-[11px] text-white/42">
                            {[
                              [language === 'en' ? 'Evaluated' : '已评估', runDetail.summary?.evaluatedCount ?? runDetail.evaluatedSize],
                              [language === 'en' ? 'Selected' : '入选', runDetail.summary?.selectedCount ?? shortlistCount],
                              [language === 'en' ? 'Rejected' : '淘汰', runDetail.summary?.rejectedCount ?? 0],
                              [language === 'en' ? 'Limited data' : '数据受限', runDetail.summary?.dataFailedCount ?? 0],
                            ].map(([label, value]) => (
                              <span key={String(label)} className="inline-flex items-baseline gap-1 rounded-md border border-white/8 bg-white/[0.03] px-2 py-0.5">
                                <span className="text-white/36">{label}</span>
                                <span className="font-mono text-white/78">{value}</span>
                              </span>
                            ))}
                          </div>
                        ) : null}
                        <div data-testid="scanner-more-actions" className="relative min-w-0">
                          <TerminalButton
                            type="button"
                            variant="compact"
                            aria-expanded={isMoreActionsOpen}
                            aria-label={language === 'en' ? 'More scanner actions' : '更多扫描操作'}
                            className="h-8 px-2.5 py-1 text-xs"
                            onClick={() => setIsMoreActionsOpen((current) => !current)}
                          >
                            <MoreHorizontal className="size-3.5" aria-hidden="true" />
                            <span>{language === 'en' ? 'More' : '更多'}</span>
                          </TerminalButton>
                          {isMoreActionsOpen ? (
                            <div data-testid="scanner-more-actions-panel" className="absolute right-0 z-20 mt-2 grid min-w-[220px] gap-1.5 rounded-xl border border-white/10 bg-black/90 p-2 shadow-xl">
                              <ActionButton
                                label={language === 'en' ? 'Export CSV' : '导出 CSV'}
                                icon={<Download className="size-3.5" />}
                                onClick={() => runDetail && handleExportRows(
                                  sortedCandidates.map((candidate) => buildScannerExportRow(candidate, runDetail, language)),
                                  buildScannerExportFilename(runDetail),
                                )}
                                disabled={!runDetail || !sortedCandidates.length}
                              />
                              <ActionButton
                                label={language === 'en' ? 'Copy all symbols' : '复制全部代码'}
                                icon={<Copy className="size-3.5" />}
                                onClick={() => void handleCopyText(sortedCandidates.map((candidate) => candidate.symbol).join(', '), 'all-symbols')}
                                disabled={!sortedCandidates.length}
                              />
                              <ActionButton
                                label={language === 'en' ? 'Copy top 5' : '复制前 5'}
                                icon={<Copy className="size-3.5" />}
                                onClick={() => void handleCopyText(sortedCandidates.slice(0, 5).map((candidate) => candidate.symbol).join(', '), 'top-5-symbols')}
                                disabled={!sortedCandidates.length}
                              />
                              <ActionButton
                                label={language === 'en' ? 'Add official selected' : '加入全部入选'}
                                icon={<BookmarkPlus className="size-3.5" />}
                                onClick={() => void handleBatchTrackCandidates('official', sortedCandidates)}
                                disabled={Boolean(pendingBatchWatchlistAction) || watchlistAuthBlocked || !sortedCandidates.length}
                              />
                              <ActionButton
                                label={language === 'en' ? 'Add preview selected' : '加入预览入选'}
                                icon={<BookmarkPlus className="size-3.5" />}
                                onClick={() => void handleBatchTrackCandidates('preview', previewSelectedDiagnostics.map(diagnosticToCandidate))}
                                disabled={Boolean(pendingBatchWatchlistAction) || watchlistAuthBlocked || !previewSelectedDiagnostics.length}
                              />
                              <ActionButton
                                label={language === 'en' ? 'Add filtered' : '加入当前筛选'}
                                icon={<BookmarkPlus className="size-3.5" />}
                                onClick={() => void handleBatchTrackCandidates('filtered', workbenchDiagnostics.map((candidate) => shortlistCandidateBySymbol.get(normalizeCandidateSymbol(candidate.symbol)) || diagnosticToCandidate(candidate)))}
                                disabled={Boolean(pendingBatchWatchlistAction) || watchlistAuthBlocked || !workbenchDiagnostics.length}
                              />
                              <ActionButton
                                label={language === 'en' ? 'Batch backtest' : '批量回测'}
                                icon={<LineChart className="size-3.5" />}
                                onClick={() => handleBacktestBatch('official_selected')}
                                disabled={isBacktestBatchRunning || backtestCounts.official_selected === 0}
                              />
                            </div>
                          ) : null}
                        </div>
                      </div>
                    </div>

                    <div
                      data-testid="scanner-workbench-detail-layout"
                      className={`grid min-h-0 flex-1 min-w-0 gap-3 p-2 ${showDetailRail ? 'xl:grid-cols-[minmax(820px,1fr)_minmax(320px,340px)]' : 'grid-cols-1'}`}
                    >
                      <div data-testid="scanner-primary-work-region" className="min-w-0">
                        {workbenchDiagnostics.length ? (
                          <div
                            data-testid="scanner-ranked-list"
                            className="overflow-x-auto overscroll-x-contain rounded-xl border border-white/5 bg-white/[0.02] [-webkit-overflow-scrolling:touch]"
                            aria-label={language === 'en' ? 'Ranked scanner results' : '扫描排名结果'}
                          >
                            <div data-testid="scanner-result-table" className="contents md:block md:min-w-[1220px]">
                              <div className="hidden items-center gap-3 border-b border-white/5 bg-black/[0.18] px-3 py-2 text-[10px] font-bold uppercase tracking-[0.14em] text-white/38 md:grid md:grid-cols-[64px_minmax(180px,1fr)_92px_110px_minmax(220px,1.3fr)_minmax(150px,0.9fr)_minmax(190px,1fr)_auto]">
                                <span>{language === 'en' ? 'Rank' : '排名'}</span>
                                <span>{language === 'en' ? 'Symbol / name' : '代码 / 名称'}</span>
                                <span>{language === 'en' ? 'Score' : '评分'}</span>
                                <span>{language === 'en' ? 'Status' : '状态'}</span>
                                <span>{language === 'en' ? 'Why now' : '当前信号'}</span>
                                <span>{language === 'en' ? 'Data quality' : '数据质量'}</span>
                                <span>{language === 'en' ? 'Next / risk' : '下一步 / 风险'}</span>
                                <span className="text-right">{language === 'en' ? 'Actions' : '操作'}</span>
                              </div>
                              <div data-testid="scanner-candidate-scroll-region" className="min-w-0 max-h-[min(52vh,34rem)] overflow-y-auto overscroll-y-contain no-scrollbar ui-scroll-y-quiet [-webkit-overflow-scrolling:touch]">
                                {workbenchDiagnostics.map((candidate) => {
                                  const activeRunDetail = runDetail;
                                  if (!activeRunDetail) return null;
                                  const sourceCandidate = shortlistCandidateBySymbol.get(normalizeCandidateSymbol(candidate.symbol)) || diagnosticToCandidate(candidate);
                                  const candidateMarket = normalizeScannerMarket(activeRunDetail.market || market);
                                  const candidateIdentity = getWatchlistIdentity(candidateMarket, candidate.symbol);
                                  const isTracked = Boolean(candidateIdentity && trackedWatchlistIdentitySet.has(candidateIdentity));
                                  const isTrackPending = pendingWatchlistIdentity === candidateIdentity;
                                  const backtestItem = getBacktestItem(sourceCandidate.symbol);
                                  const comparison = comparisonState.bySymbol.get(normalizeCandidateSymbol(candidate.symbol) || '');
                                  return (
                                    <ScannerCandidateDiagnosticRow
                                      key={`ranked-${candidate.symbol}`}
                                      candidate={candidate}
                                      language={language}
                                      isSelectedCandidate={normalizeCandidateSymbol(activeDetailDiagnostic?.symbol) === normalizeCandidateSymbol(candidate.symbol)}
                                      isExpanded={false}
                                      isMoreOpen={rowMoreSymbol === candidate.symbol}
                                      displayName={sourceCandidate.companyName || sourceCandidate.name || candidate.name || candidate.symbol || '--'}
                                      keyReason={isOfficialSelected(candidate) ? getKeyReason(sourceCandidate, runDetail, language) : formatFriendlyDiagnosticReason(candidate, language)}
                                      previewLabel={previewDecisionLabel(candidate, previewThreshold, language)}
                                      previewBadgeClassName={previewDecisionClass(candidate, previewThreshold)}
                                      dataQualityLabel={formatCandidateDataQuality(candidate, language)}
                                      watchSummary={formatWorkbenchWatchSummary(sourceCandidate, language)}
                                      rangeSummary={formatWorkbenchRangeSummary(sourceCandidate, language)}
                                      evidenceSummary={null}
                                      scoreLabel={candidate.score == null ? '--' : `${candidate.score}/100`}
                                      trustSources={[stripScannerConsumerTrustSource(sourceCandidate), stripScannerConsumerTrustSource(candidate)]}
                                      scoreDelta={formatScoreDelta(comparison?.scoreDelta ?? null)}
                                      comparisonLabel={comparison?.label || null}
                                      statusLabel={diagnosticStatusLabel(candidate.status, language)}
                                      watchlistActionLabel={getWatchlistActionLabel(isTracked, isTrackPending, watchlistAuthBlocked, language)}
                                      watchlistActionTitle={getWatchlistActionTitle(isTracked, watchlistAuthBlocked, language)}
                                      copyLabel={copiedKey === `candidate:${candidate.symbol}` ? (language === 'en' ? 'Copied' : '已复制') : (language === 'en' ? 'Copy' : '复制')}
                                      exportLabel={language === 'en' ? 'Export' : '导出'}
                                      isTracked={isTracked}
                                      isTrackPending={isTrackPending}
                                      isWatchlistAuthBlocked={watchlistAuthBlocked}
                                      isAnalyzing={pendingAnalyzeSymbol === sourceCandidate.symbol}
                                      backtestLabel={getBacktestActionLabel(backtestItem)}
                                      backtestTitle={!normalizeCandidateSymbol(sourceCandidate.symbol) ? backtestUnavailableLabel : undefined}
                                      backtestItem={backtestItem}
                                      onSelect={() => setInspectorSymbol(sourceCandidate.symbol)}
                                      onAnalyze={() => void handleAnalyzeCandidate(sourceCandidate)}
                                      onBacktest={() => void handleBacktestCandidate(sourceCandidate)}
                                      onTrack={() => void handleTrackCandidate(sourceCandidate)}
                                      onCopy={() => void handleCopyText(sourceCandidate.symbol, `candidate:${candidate.symbol}`)}
                                      onExport={() => handleExportRows(
                                        [buildScannerExportRow(sourceCandidate, activeRunDetail, language)],
                                        buildScannerExportFilename(activeRunDetail, `candidate-${candidate.symbol}`),
                                      )}
                                      onToggleMore={() => setRowMoreSymbol((current) => current === candidate.symbol ? null : candidate.symbol)}
                                    />
                                  );
                                })}
                              </div>
                            </div>
                          </div>
                        ) : (
                          <CompactEmptyRow
                            data-testid="scanner-workbench-empty-state"
                            title={workbenchEmptyState.title}
                            className="m-0 min-h-[120px]"
                          >
                            {workbenchEmptyState.body}
                          </CompactEmptyRow>
                        )}

                      </div>

                      {activeDetailCandidate ? (
                        <div data-testid="scanner-context-rail" className="min-w-0">
                          {!showDetailRail ? (
                          <div data-testid="scanner-inline-detail-panel" className="max-h-[min(72vh,42rem)] overflow-y-auto rounded-xl border border-white/5 bg-black/20 p-3 no-scrollbar ui-scroll-y-quiet">
                            <div data-testid={`scanner-candidate-detail-${activeDetailCandidate.symbol || 'unknown'}`} className="contents">
                              <div data-testid="scanner-candidate-inspector" className="contents">
                                <div className="mb-2 flex min-w-0 flex-wrap items-center gap-1.5 text-[11px] text-white/48">
                                  <span className="font-semibold text-white/72">{language === 'en' ? 'Focus candidate' : '当前候选'}</span>
                                  <span className="rounded-md border border-white/8 bg-white/[0.04] px-2 py-0.5 font-mono text-white/72">{activeDetailCandidate.symbol || '--'}</span>
                                  {activeDetailDiagnostic ? (
                                    <span className="rounded-md border border-white/8 bg-white/[0.04] px-2 py-0.5">
                                      {diagnosticStatusLabel(activeDetailDiagnostic.status, language)}
                                    </span>
                                  ) : null}
                                  {activeDetailDiagnostic ? (
                                    <span className="rounded-md border border-white/8 bg-white/[0.04] px-2 py-0.5 text-white/58">
                                      {formatCandidateDataQuality(activeDetailDiagnostic, language)}
                                    </span>
                                  ) : null}
                                </div>
                                {activeDetailDiagnostic ? (
                                  <p className="mb-2 text-xs text-white/58">
                                    {language === 'en' ? 'Keep the ranked rows visible and use this rail for the current candidate only.' : '先保持主表可见，右侧只保留当前候选的关键信息。'}
                                  </p>
                                ) : null}
                                {renderCandidateDetailPanel(
                                  activeDetailCandidate,
                                  activeDetailTracked,
                                  activeDetailTrackPending,
                                  activeDetailDiagnostic
                                    ? (isOfficialSelected(activeDetailDiagnostic)
                                      ? getKeyReason(activeDetailCandidate, runDetail, language)
                                      : formatFriendlyDiagnosticReason(activeDetailDiagnostic, language))
                                    : null,
                                  activeDetailBacktestItem,
                                )}
                              </div>
                            </div>
                          </div>
                          ) : null}

                          {showDetailRail ? (
                          <aside data-testid="scanner-detail-rail" className="sticky top-4 self-start max-h-[min(72vh,42rem)] overflow-y-auto rounded-xl border border-white/5 bg-black/20 p-3 no-scrollbar ui-scroll-y-quiet">
                            <div data-testid={`scanner-candidate-detail-${activeDetailCandidate.symbol || 'unknown'}`} className="contents">
                              <div data-testid="scanner-candidate-inspector" className="contents">
                                <div className="mb-2 flex min-w-0 flex-wrap items-center gap-1.5 text-[11px] text-white/48">
                                  <span className="font-semibold text-white/72">{language === 'en' ? 'Focus candidate' : '当前候选'}</span>
                                  <span className="rounded-md border border-white/8 bg-white/[0.04] px-2 py-0.5 font-mono text-white/72">{activeDetailCandidate.symbol || '--'}</span>
                                  {activeDetailDiagnostic ? (
                                    <span className="rounded-md border border-white/8 bg-white/[0.04] px-2 py-0.5">
                                      {diagnosticStatusLabel(activeDetailDiagnostic.status, language)}
                                    </span>
                                  ) : null}
                                  {activeDetailDiagnostic ? (
                                    <span className="rounded-md border border-white/8 bg-white/[0.04] px-2 py-0.5 text-white/58">
                                      {formatCandidateDataQuality(activeDetailDiagnostic, language)}
                                    </span>
                                  ) : null}
                                </div>
                                {activeDetailDiagnostic ? (
                                  <p className="mb-2 text-xs text-white/58">
                                    {language === 'en' ? 'Keep the ranked rows visible and use this rail for the current candidate only.' : '先保持主表可见，右侧只保留当前候选的关键信息。'}
                                  </p>
                                ) : null}
                                {renderCandidateDetailPanel(
                                  activeDetailCandidate,
                                  activeDetailTracked,
                                  activeDetailTrackPending,
                                  activeDetailDiagnostic
                                    ? (isOfficialSelected(activeDetailDiagnostic)
                                      ? getKeyReason(activeDetailCandidate, runDetail, language)
                                      : formatFriendlyDiagnosticReason(activeDetailDiagnostic, language))
                                    : null,
                                  activeDetailBacktestItem,
                                )}
                              </div>
                            </div>
                          </aside>
                          ) : null}
                        </div>
                      ) : null}
                    </div>

                    {runDetail && hasCandidateDiagnostics ? (
                      <div data-testid="scanner-secondary-deck" className="border-t border-white/10 px-2 py-0">
                        <div data-testid="scanner-secondary-sections" className="grid gap-2 xl:grid-cols-2 2xl:grid-cols-4">
                          <AdvancedDisclosure
                            testId="scanner-run-status-disclosure"
                            title={language === 'en' ? 'Run status' : '运行状态'}
                            summary={language === 'en'
                              ? `Evaluated ${runDetail.summary?.evaluatedCount ?? runDetail.evaluatedSize} · selected ${runDetail.summary?.selectedCount ?? shortlistCount}`
                              : `评估 ${runDetail.summary?.evaluatedCount ?? runDetail.evaluatedSize} · 入选 ${runDetail.summary?.selectedCount ?? shortlistCount}`}
                            icon="info"
                          >
                            <div className="max-h-[min(28vh,18rem)] overflow-y-auto no-scrollbar ui-scroll-y-quiet space-y-2">
                              <div className="grid gap-1.5 rounded-xl border border-white/8 bg-white/[0.02] p-3 text-xs">
                                <div className="flex items-center justify-between gap-2 border-b border-white/8 pb-1.5">
                                  <span className="text-[10px] uppercase tracking-[0.14em] text-white/36">{language === 'en' ? 'Data' : '数据'}</span>
                                  <span className="truncate font-mono text-white/72">{scannerDataStateLabel}</span>
                                </div>
                                <div className="flex items-center justify-between gap-2 border-b border-white/8 pb-1.5">
                                  <span className="text-[10px] uppercase tracking-[0.14em] text-white/36">{language === 'en' ? 'Latest' : '最近'}</span>
                                  <span className="truncate font-mono text-white/72">{generatedAt ? formatTimestamp(generatedAt, language) : '--'}</span>
                                </div>
                                <div className="flex items-center justify-between gap-2">
                                  <span className="text-[10px] uppercase tracking-[0.14em] text-white/36">{language === 'en' ? 'Theme' : '主题'}</span>
                                  <span className="truncate font-mono text-white/72">{scannerThemeLabel}</span>
                                </div>
                              </div>
                            </div>
                          </AdvancedDisclosure>

                          {rejectionBuckets.length || hasRunDiagnosticsContent(runDetail) ? (
                            <AdvancedDisclosure
                              testId="scanner-diagnostics-disclosure"
                              title={language === 'en' ? 'Data notes' : '数据说明'}
                              summary={language === 'en'
                                ? `Evaluated ${runDetail.summary?.evaluatedCount ?? runDetail.evaluatedSize} · main rejection ${rejectionBuckets[0]?.label || 'n/a'}`
                                : `评估 ${runDetail.summary?.evaluatedCount ?? runDetail.evaluatedSize} · 主要淘汰 ${rejectionBuckets[0]?.label || '暂无'}`}
                              icon="info"
                            >
                              <div className="max-h-[min(34vh,20rem)] overflow-y-auto no-scrollbar ui-scroll-y-quiet">
                                <div data-testid="scanner-diagnostics-summary" className="mb-2 border-t border-white/8 py-2 text-xs">
                                  <div className="flex min-w-0 flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                                    <p className="min-w-0 text-white/64">
                                      {language === 'en'
                                        ? `Evaluated ${runDetail.summary?.evaluatedCount ?? runDetail.evaluatedSize} · selected ${runDetail.summary?.selectedCount ?? shortlistCount} · main rejection ${rejectionBuckets[0]?.label || 'n/a'}`
                                        : `评估 ${runDetail.summary?.evaluatedCount ?? runDetail.evaluatedSize} · 入选 ${runDetail.summary?.selectedCount ?? shortlistCount} · 主要淘汰 ${rejectionBuckets[0]?.label || '暂无'}`}
                                    </p>
                                    <ActionButton
                                      label={language === 'en' ? 'Rejection mix' : '淘汰分布'}
                                      onClick={() => setIsRejectionSummaryOpen((current) => !current)}
                                    />
                                  </div>
                                  {isRejectionSummaryOpen && rejectionBuckets.length ? (
                                    <div data-testid="scanner-rejection-aggregate" className="mt-2 flex min-w-0 flex-wrap items-center gap-1.5">
                                      {rejectionBuckets.map((bucket) => (
                                        <button
                                          key={bucket.label}
                                          type="button"
                                          className="inline-flex max-w-full items-baseline gap-1 border-b border-white/15 px-1.5 py-0.5 text-[10px] text-white/62 hover:text-white"
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
                              </div>
                            </AdvancedDisclosure>
                          ) : null}

                          <AdvancedDisclosure
                            testId="scanner-run-comparison-strip"
                            title={language === 'en' ? 'Comparison records' : '比较记录'}
                            summary={comparisonState.previousRun && comparisonState.chips.length
                              ? `${language === 'en' ? 'Compared with previous run' : '上次对比'}：${comparisonState.chips[0]}`
                              : (language === 'en' ? 'No previous comparable run' : '暂无上次扫描对比')}
                            icon="history"
                          >
                            <div className="max-h-[min(28vh,18rem)] overflow-y-auto no-scrollbar ui-scroll-y-quiet space-y-2">
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
                                    <span key={chip} className="shrink-0 border-b border-white/15 px-1.5 py-0.5 text-white/62">
                                      {chip}
                                    </span>
                                  ))
                                ) : (
                                  <span className="shrink-0 border-b border-white/15 px-1.5 py-0.5 text-white/42">
                                    {language === 'en' ? 'No previous comparable run' : '暂无上次扫描对比'}
                                  </span>
                                )}
                              </div>
                            </div>
                          </AdvancedDisclosure>

                          <AdvancedDisclosure
                            testId="scanner-strategy-experiment"
                            title={language === 'en' ? 'Backtest setup' : '回测准备'}
                            summary={language === 'en' ? 'Simulation · batch backtest · recent results' : '模拟 · 批量回测 · 最近结果'}
                            icon="backtest"
                          >
                            <div className="max-h-[min(38vh,24rem)] overflow-y-auto no-scrollbar ui-scroll-y-quiet space-y-3">
                              <div
                                data-testid="scanner-strategy-preview"
                                className="border-t border-white/8 py-2 text-xs"
                              >
                                <div className="flex flex-wrap items-center gap-1.5">
                                  <span className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-white/40">
                                    <LineChart className="size-3.5" aria-hidden="true" />
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
                              <Suspense fallback={null}>
                                <LazyScannerBacktestLab
                                  language={language}
                                  items={backtestItems}
                                  isRunning={isBacktestBatchRunning}
                                  onRunBatch={handleBacktestBatch}
                                  onCopySymbol={(symbol) => void handleCopyText(symbol, `backtest:${symbol}`)}
                                  counts={backtestCounts}
                                />
                              </Suspense>
                            </div>
                          </AdvancedDisclosure>
                        </div>
                      </div>
                    ) : null}
                  </div>
                </DenseTableShell>
		          </div>
	        </ConsumerWorkspacePageShell>
          </ConsumerWorkspaceScope>
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
