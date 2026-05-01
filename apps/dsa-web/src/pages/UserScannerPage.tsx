import React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArrowDownUp,
  ChevronDown,
  ChevronUp,
  Copy,
  Download,
  LayoutGrid,
  PanelRightOpen,
  Play,
  Table2,
  TestTubeDiagonal,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { analysisApi, DuplicateTaskError } from '../api/analysis';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { scannerApi } from '../api/scanner';
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
  ScannerCandidateOutcome,
  ScannerCoverageSummary,
  ScannerLabeledValue,
  ScannerProviderDiagnostics,
  ScannerReviewSummary,
  ScannerRunDetail,
  ScannerRunHistoryItem,
  ScannerTheme,
  ScannerWatchlistComparison,
} from '../types/scanner';
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
type SortKey = 'score' | 'symbol' | 'target' | 'risk';
type SortDirection = 'asc' | 'desc';
type Tone = 'info' | 'success' | 'warning' | 'danger' | 'history';
type ScanScope = 'default' | 'theme' | 'symbols';
type ActionNotice = { tone: 'success' | 'warning' | 'danger'; message: string } | null;

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
    <div className={`w-full flex flex-col items-center justify-center py-16 px-4 border border-white/5 border-dashed rounded-2xl bg-white/[0.01] ${className}`.trim()}>
      <div className="w-12 h-12 rounded-full bg-white/[0.02] border border-white/5 flex items-center justify-center mb-4">
        <svg className="w-6 h-6 text-white/20" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
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

function formatDuration(start?: string | null, end?: string | null, language: 'zh' | 'en' = 'zh'): string {
  if (!start || !end) return '--';
  const startTime = new Date(start).getTime();
  const endTime = new Date(end).getTime();
  if (Number.isNaN(startTime) || Number.isNaN(endTime) || endTime <= startTime) return '--';
  const totalSeconds = Math.round((endTime - startTime) / 1000);
  if (totalSeconds < 60) {
    return language === 'en' ? `${totalSeconds}s` : `${totalSeconds}秒`;
  }
  const totalMinutes = Math.round(totalSeconds / 60);
  if (totalMinutes < 60) {
    return language === 'en' ? `${totalMinutes}m` : `${totalMinutes}分钟`;
  }
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return language === 'en' ? `${hours}h ${minutes}m` : `${hours}小时${minutes}分钟`;
}

function scoreBadgeClass(score: number): string {
  if (score >= 90) return 'bg-white/[0.08] text-white border-white/12';
  if (score >= 80) return 'bg-indigo-500/12 text-indigo-200 border-indigo-500/20';
  return 'bg-white/[0.04] text-white/72 border-white/10';
}

function noteBadgeClass(tone: Tone = 'history'): string {
  const classes: Record<Tone, string> = {
    info: 'border-sky-400/20 bg-sky-400/10 text-sky-100',
    success: 'border-emerald-400/20 bg-emerald-400/10 text-emerald-100',
    warning: 'border-amber-400/20 bg-amber-400/10 text-amber-100',
    danger: 'border-red-400/20 bg-red-400/10 text-red-100',
    history: 'border-white/10 bg-white/[0.04] text-white/70',
  };
  return classes[tone];
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

function formatCoverageSummary(coverage: ScannerCoverageSummary | null, runDetail: ScannerRunDetail | null, language: 'zh' | 'en'): string | null {
  if (coverage) {
    const scanned = coverage.inputUniverseSize || runDetail?.universeSize || 0;
    const ranked = coverage.rankedCandidateCount || runDetail?.evaluatedSize || 0;
    const selected = coverage.shortlistedCount || runDetail?.shortlist?.length || 0;
    const bottleneck = coverage.likelyBottleneckLabel || coverage.likelyBottleneck;
    const base = language === 'en'
      ? `${scanned} scanned · ${ranked} ranked · ${selected} selected`
      : `扫描 ${scanned} · 排名 ${ranked} · 入选 ${selected}`;
    return bottleneck ? `${base} · ${bottleneck}` : base;
  }
  if (!runDetail) return null;
  return language === 'en'
    ? `${runDetail.universeSize} scanned · ${runDetail.shortlist?.length ?? runDetail.shortlistSize} selected`
    : `扫描 ${runDetail.universeSize} · 入选 ${runDetail.shortlist?.length ?? runDetail.shortlistSize}`;
}

function formatNotesSummary(notes: string[], language: 'zh' | 'en'): string | null {
  if (!notes.length) return null;
  const first = notes[0];
  return language === 'en' ? `${notes.length} notes · ${first}` : `${notes.length} 条 · ${first}`;
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

function getThemeLabel(theme: ScannerTheme, language: 'zh' | 'en'): string {
  return language === 'en' ? theme.labelEn : theme.labelZh;
}

function getRunUniverseSummary(runDetail: ScannerRunDetail | null, language: 'zh' | 'en'): string | null {
  if (!runDetail || !runDetail.universeType || runDetail.universeType === 'default') return null;
  const label = runDetail.themeLabel || (runDetail.universeType === 'theme' ? runDetail.themeId : null);
  const typeLabel = runDetail.universeType === 'theme'
    ? (language === 'en' ? 'Theme' : '主题')
    : (language === 'en' ? 'Custom' : '自定义');
  const counts = `${runDetail.acceptedSymbolsCount}/${runDetail.requestedSymbolsCount}`;
  const rejected = runDetail.rejectedSymbols?.length
    ? (language === 'en' ? ` · ${runDetail.rejectedSymbols.length} rejected` : ` · ${runDetail.rejectedSymbols.length} 个无效`)
    : '';
  return [typeLabel, label, counts].filter(Boolean).join(' · ') + rejected;
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
  disabled = false,
  title,
  variant = 'default',
  testId,
}: {
  label: string;
  icon?: React.ReactNode;
  onClick?: (event: React.MouseEvent<HTMLButtonElement>) => void;
  disabled?: boolean;
  title?: string;
  variant?: 'default' | 'primary';
  testId?: string;
}) {
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={[
        'inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs transition-colors',
        variant === 'primary'
          ? 'border-indigo-500/25 bg-indigo-500/10 text-indigo-100 hover:border-indigo-500/45 hover:bg-indigo-500/15'
          : 'border-white/8 bg-white/[0.04] text-white/70 hover:bg-white/[0.08] hover:text-white',
        disabled ? 'cursor-not-allowed border-white/5 bg-white/[0.02] text-white/28 hover:bg-white/[0.02] hover:text-white/28' : '',
      ].join(' ')}
    >
      {icon}
      <span>{label}</span>
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
    <div className="flex flex-col gap-2">
      <span className="text-xs uppercase tracking-widest text-white/40">{label}</span>
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
                  ? 'rounded-lg bg-white/10 px-5 py-1.5 text-sm font-bold text-white shadow-[0_2px_10px_rgba(0,0,0,0.5)] transition-all'
                  : 'rounded-full border border-white/10 bg-white/10 px-4 py-1.5 text-sm text-white transition-colors'
                : isMarketGroup
                  ? 'rounded-lg bg-transparent px-5 py-1.5 text-sm font-medium text-white/40 transition-all hover:text-white/70'
                  : 'rounded-full border border-white/5 bg-transparent px-4 py-1.5 text-sm text-white/50 transition-colors hover:bg-white/[0.05]'}
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
    <span className="inline-flex max-w-full items-center gap-1 rounded-md border border-white/8 bg-white/[0.035] px-2 py-1 text-[11px] text-white/72">
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
    <ul className="space-y-1.5">
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
    <section className="rounded-xl border border-white/5 bg-black/20 p-3">
      <h5 className="mb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-white/38">{title}</h5>
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
  isAnalyzing,
  isCopied,
  backtestUnavailableLabel,
}: {
  candidate: ScannerCandidate;
  runDetail: ScannerRunDetail;
  language: 'zh' | 'en';
  onAnalyze: (candidate: ScannerCandidate) => void;
  onCopy: (candidate: ScannerCandidate) => void;
  onExport: (candidate: ScannerCandidate) => void;
  isAnalyzing: boolean;
  isCopied: boolean;
  backtestUnavailableLabel: string;
}) {
  const candidateProvider = getProviderDiagnostics(candidate.diagnostics);
  const ai = candidate.aiInterpretation;
  const entryRange = getEntryRange(candidate);
  const targetPrice = getTargetPrice(candidate);
  const stopLoss = getStopLoss(candidate);

  return (
    <div
      data-testid={`scanner-result-detail-${candidate.symbol}`}
      className="mt-4 grid gap-3 rounded-2xl border border-white/8 bg-black/25 p-4 md:grid-cols-2"
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
          label={language === 'en' ? 'Export candidate' : '导出该候选'}
          icon={<Download className="h-3.5 w-3.5" />}
          onClick={() => onExport(candidate)}
        />
        <ActionButton
          label={language === 'en' ? 'Backtest' : '回测'}
          icon={<TestTubeDiagonal className="h-3.5 w-3.5" />}
          disabled
          title={backtestUnavailableLabel}
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
    <details data-testid="scanner-diagnostics-panel" className="mt-5 rounded-2xl border border-white/5 bg-white/[0.02] p-4" open>
      <summary className="cursor-pointer text-sm font-semibold text-white/78">
        {language === 'en' ? 'Diagnostics and replay notes' : '诊断与复盘说明'}
      </summary>
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
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
  const [isHistoryDrawerOpen, setIsHistoryDrawerOpen] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('cards');
  const [sortKey, setSortKey] = useState<SortKey>('score');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [expandedSymbol, setExpandedSymbol] = useState<string | null>(null);
  const [pendingAnalyzeSymbol, setPendingAnalyzeSymbol] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

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
  const selectedTheme = useMemo(
    () => marketThemes.find((theme) => theme.id === themeId) || null,
    [marketThemes, themeId],
  );
  const parsedCustomSymbols = useMemo(() => parseCustomSymbols(customSymbols), [customSymbols]);

  const handleMarketChange = useCallback((nextMarket: string) => {
    const normalizedMarket = nextMarket === 'us' ? 'us' : nextMarket === 'hk' ? 'hk' : 'cn';
    const defaults = SCANNER_PROFILE_DEFAULTS[normalizedMarket];
    setMarket(normalizedMarket);
    setProfile(defaults.profile);
    setShortlistSize(defaults.shortlistSize);
    setUniverseLimit(defaults.universeLimit);
    setDetailLimit(defaults.detailLimit);
    setThemeId('');
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
    setIsRunning(true);
    try {
      const response = await scannerApi.run({
        market,
        profile,
        shortlistSize: Number.parseInt(shortlistSize, 10),
        universeLimit: Number.parseInt(universeLimit, 10),
        detailLimit: Number.parseInt(detailLimit, 10),
        ...(scanScope !== 'default' ? { universeType: scanScope } : {}),
        ...(scanScope === 'theme' ? { themeId } : {}),
        ...(scanScope === 'symbols' ? { symbols: parsedCustomSymbols } : {}),
      });
      setRunDetail(response);
      setSelectedRunId(response.id);
      setExpandedSymbol(null);
      setPageError(null);
      await fetchHistory(1, response.id);
    } catch (error) {
      setPageError(getParsedApiError(error));
    } finally {
      setIsRunning(false);
    }
  }, [detailLimit, fetchHistory, market, parsedCustomSymbols, profile, scanScope, shortlistSize, themeId, universeLimit]);

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
  const runScannerButton = useSafariWarmActivation<HTMLButtonElement>(() => {
    void handleRun();
  });
  const openHistoryDrawerButton = useSafariWarmActivation<HTMLButtonElement>(() => setIsHistoryDrawerOpen(true));
  const shortlistCount = runDetail?.shortlist?.length ?? 0;
  const generatedAt = runDetail?.completedAt || runDetail?.runAt || null;
  const elapsedTime = formatDuration(runDetail?.runAt, runDetail?.completedAt, language);
  const coverageSummary = runDetail ? getRunCoverageSummary(runDetail) : null;
  const providerDiagnostics = runDetail ? getRunProviderDiagnostics(runDetail) : null;
  const universeSummary = getRunUniverseSummary(runDetail, language);
  const runDisabled = isRunning
    || (scanScope === 'theme' && (!selectedTheme || selectedTheme.symbols.length === 0))
    || (scanScope === 'symbols' && parsedCustomSymbols.length === 0);
  const qualityItems = [
    {
      label: language === 'en' ? 'Scan scope' : '扫描范围',
      value: universeSummary,
      tone: 'info' as Tone,
    },
    {
      label: language === 'en' ? 'Coverage' : '覆盖',
      value: formatCoverageSummary(coverageSummary, runDetail, language),
      tone: 'info' as Tone,
    },
    {
      label: language === 'en' ? 'Provider' : '供应商',
      value: formatProviderDiagnostics(providerDiagnostics, language),
      tone: providerDiagnostics?.fallbackOccurred ? 'warning' as Tone : 'success' as Tone,
    },
    {
      label: language === 'en' ? 'Universe notes' : '候选说明',
      value: runDetail ? formatNotesSummary(runDetail.universeNotes || [], language) : null,
      tone: 'history' as Tone,
    },
    {
      label: language === 'en' ? 'Scoring notes' : '评分说明',
      value: runDetail ? formatNotesSummary(runDetail.scoringNotes || [], language) : null,
      tone: 'history' as Tone,
    },
  ].filter((item): item is { label: string; value: string; tone: Tone } => Boolean(item.value));

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
    ? 'Backtest handoff not available yet.'
    : '回测交接暂不可用。';

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
          'bento-surface-root flex w-full flex-1 flex-col gap-6 min-h-0 min-w-0 bg-transparent text-foreground',
        )}
      >
        <main
          data-testid="user-scanner-workspace"
          className="w-full flex-1 flex flex-col gap-6 min-h-0 min-w-0"
        >
          <header className="shrink-0 flex justify-between items-start mb-3 mt-0">
            <div>
              <p className="text-[10px] uppercase tracking-[0.28em] text-white/36">TACTICAL ROUTER</p>
              <h1 className="mt-3 text-[1.7rem] tracking-[-0.03em] text-foreground md:text-[1.9rem]">{language === 'en' ? 'MARKET SCANNER' : '市场扫描'}</h1>
            </div>
          </header>

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

          <div className="flex w-full flex-1 min-h-0 min-w-0 flex-col gap-6 xl:flex-row">
            <section
              data-testid="scanner-sidebar"
              className="w-full xl:w-[320px] 2xl:w-[360px] shrink-0 flex flex-col gap-6 bg-white/[0.02] border border-white/5 rounded-[24px] p-6 h-fit sticky top-6"
            >
              <SectionShell className="rounded-[24px] p-0 bg-transparent shadow-none">
                <div className="flex flex-col gap-6">
                  <PillTagGroup label={t('scanner.marketLabel')} value={market} onChange={(next) => handleMarketChange(next as 'cn' | 'us' | 'hk')} options={[{ value: 'cn', label: t('scanner.marketCn') }, { value: 'us', label: t('scanner.marketUs') }, { value: 'hk', label: t('scanner.marketHk') }]} variant="market" testId="scanner-market-toggle" />
                  <PillTagGroup label={t('scanner.profileLabel')} value={profile} onChange={setProfile} options={profileOptions} />
                  <PillTagGroup label={t('scanner.shortlistLabel')} value={shortlistSize} onChange={setShortlistSize} options={[{ value: '5', label: language === 'en' ? 'Top 5' : '前 5' }, { value: '8', label: language === 'en' ? 'Top 8' : '前 8' }, { value: '10', label: language === 'en' ? 'Top 10' : '前 10' }]} />
                  <PillTagGroup label={t('scanner.universeLabel')} value={universeLimit} onChange={setUniverseLimit} options={universeOptions} />
                  <PillTagGroup label={t('scanner.detailLabel')} value={detailLimit} onChange={setDetailLimit} options={detailOptions} />
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
                    <div className="flex flex-col gap-2" data-testid="scanner-theme-control">
                      <span className="text-xs uppercase tracking-widest text-white/40">{language === 'en' ? 'Theme' : '主题'}</span>
                      <select
                        data-testid="scanner-theme-select"
                        value={themeId}
                        onChange={(event) => setThemeId(event.target.value)}
                        className="w-full rounded-xl border border-white/8 bg-black/40 px-3 py-2 text-sm text-white outline-none focus:border-indigo-400/50"
                      >
                        <option value="">{language === 'en' ? 'Select a theme' : '选择主题'}</option>
                        {marketThemes.map((theme) => (
                          <option key={theme.id} value={theme.id} disabled={!theme.symbols.length}>
                            {getThemeLabel(theme, language)} · {theme.symbols.length || (language === 'en' ? 'not configured' : '未配置')}
                          </option>
                        ))}
                      </select>
                      {selectedTheme ? (
                        <p className="text-xs leading-relaxed text-white/45">
                          {selectedTheme.description}
                          {' '}
                          {language === 'en' ? `${selectedTheme.symbols.length} symbols` : `${selectedTheme.symbols.length} 只标的`}
                          {selectedTheme.requiresManualMaintenance ? (language === 'en' ? ' · requires manual maintenance' : ' · 需要人工维护') : ''}
                        </p>
                      ) : (
                        <p className="text-xs leading-relaxed text-white/32">
                          {language === 'en' ? 'Only themes matching the selected market are shown.' : '仅显示当前市场对应的主题。'}
                        </p>
                      )}
                    </div>
                  ) : null}
                  {scanScope === 'symbols' ? (
                    <div className="flex flex-col gap-2" data-testid="scanner-custom-symbols-control">
                      <span className="text-xs uppercase tracking-widest text-white/40">{language === 'en' ? 'Symbols' : '代码'}</span>
                      <textarea
                        data-testid="scanner-custom-symbols-input"
                        value={customSymbols}
                        onChange={(event) => setCustomSymbols(event.target.value)}
                        rows={4}
                        placeholder={language === 'en' ? 'MARA RIOT CLSK' : 'MARA RIOT CLSK'}
                        className="w-full resize-none rounded-xl border border-white/8 bg-black/40 px-3 py-2 text-sm text-white outline-none placeholder:text-white/20 focus:border-indigo-400/50"
                      />
                      <p className="text-xs text-white/45">
                        {language === 'en' ? `Parsed ${parsedCustomSymbols.length}` : `已解析 ${parsedCustomSymbols.length}`}
                      </p>
                    </div>
                  ) : null}
                  <div className="flex flex-col gap-4">
                    <button
                      ref={runScannerButton.ref}
                      type="button"
                      onClick={runScannerButton.onClick}
                      onPointerUp={runScannerButton.onPointerUp}
                      disabled={runDisabled}
                      aria-busy={isRunning}
                      data-testid="scanner-run-button"
                      className="group mt-8 flex w-full items-center justify-center gap-2 rounded-xl border border-indigo-500/30 bg-indigo-500/10 px-8 py-4 text-sm font-bold text-indigo-400 transition-all hover:border-indigo-500/50 hover:bg-indigo-500/20 hover:shadow-[0_0_25px_rgba(99,102,241,0.2)] active:scale-95 disabled:pointer-events-none disabled:opacity-60 disabled:shadow-none disabled:transform-none"
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
              className="flex-1 min-h-0 min-w-0 overflow-y-auto no-scrollbar pb-24"
            >
              <div data-testid="user-scanner-bento-hero" className="mb-5 flex shrink-0 flex-col gap-4 border-b border-white/5 pb-4">
                <div className="flex flex-col justify-between gap-3 lg:flex-row lg:items-end">
                  <div className="min-w-0">
                    <h2 className="text-xl font-bold text-white mb-1">{language === 'en' ? 'Scanner workbench' : '扫描工作台'}</h2>
                    <div className="flex flex-wrap items-center gap-2 text-xs text-white/40">
                      <span>
                        {language === 'en' ? 'Generated:' : '生成时间：'}
                        {generatedAt ? ` ${formatTimestamp(generatedAt, language)}` : ' --'}
                      </span>
                      <span className="w-1 h-1 rounded-full bg-white/20" aria-hidden="true" />
                      <span>
                        {language === 'en' ? 'Elapsed:' : '耗时：'}
                        {` ${elapsedTime}`}
                      </span>
                      {runDetail ? (
                        <>
                          <span className="w-1 h-1 rounded-full bg-white/20" aria-hidden="true" />
                          <span>{`${runDetail.market.toUpperCase()} · ${runDetail.profileLabel || runDetail.profile}`}</span>
                        </>
                      ) : null}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-3">
                    <span
                      data-testid="user-scanner-bento-hero-shortlist-value"
                      className="shrink-0 rounded-full border border-white/12 bg-white/[0.08] px-3 py-1 text-xs font-bold text-white"
                    >
                      {language === 'en' ? `${shortlistCount} symbols selected` : `入选 ${shortlistCount} 只标的`}
                    </span>
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
                      className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.05] px-3 py-1.5 text-sm text-white/80 transition-colors hover:bg-white/[0.1]"
                    >
                      <PanelRightOpen className="h-4 w-4" />
                      <span>{language === 'en' ? 'Historical replay' : '历史扫描回放'}</span>
                    </button>
                  </div>
                </div>

                {qualityItems.length ? (
                  <div data-testid="scanner-quality-strip" className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                    {qualityItems.map((item) => (
                      <div key={item.label} className={`min-w-0 rounded-xl border px-3 py-2 ${noteBadgeClass(item.tone)}`}>
                        <p className="text-[10px] uppercase tracking-[0.16em] opacity-65">{item.label}</p>
                        <p className="mt-1 truncate text-xs font-medium">{item.value}</p>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>

              <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div className="flex w-fit rounded-xl border border-white/5 bg-black/30 p-1" role="group" aria-label={language === 'en' ? 'Result view mode' : '结果视图'}>
                  <button
                    type="button"
                    onClick={() => setViewMode('cards')}
                    className={`inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs ${viewMode === 'cards' ? 'bg-white/10 text-white' : 'text-white/45 hover:text-white/75'}`}
                  >
                    <LayoutGrid className="h-3.5 w-3.5" />
                    {language === 'en' ? 'Card view' : '卡片视图'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setViewMode('table')}
                    className={`inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs ${viewMode === 'table' ? 'bg-white/10 text-white' : 'text-white/45 hover:text-white/75'}`}
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
                      className={`inline-flex items-center gap-1 rounded-lg border px-2.5 py-1 ${sortKey === key ? 'border-white/16 bg-white/[0.08] text-white' : 'border-white/5 bg-white/[0.02] text-white/48 hover:text-white/75'}`}
                    >
                      {label}
                      {sortKey === key ? <ArrowDownUp className="h-3 w-3" /> : null}
                    </button>
                  ))}
                </div>
              </div>

              {sortedCandidates.length ? (
                viewMode === 'cards' ? (
                  <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                    {sortedCandidates.map((candidate) => {
                      const isExpanded = expandedSymbol === candidate.symbol;
                      const entryRange = getEntryRange(candidate);
                      const targetPrice = getTargetPrice(candidate);
                      const stopLoss = getStopLoss(candidate);
                      const sourceBadge = getSourceBadge(candidate, runDetail, language);
                      return (
                        <article
                          key={`watchlist-${candidate.symbol}`}
                          data-testid={`scanner-result-card-${candidate.symbol}`}
                          className="rounded-2xl border border-white/5 bg-white/[0.02] p-5 transition-colors hover:border-white/16 hover:bg-white/[0.04]"
                        >
                          <div className="flex justify-between items-start gap-4">
                            <div className="min-w-0 flex flex-col gap-1.5">
                              <div className="flex flex-wrap items-baseline gap-2 min-w-0">
                                <span className="rounded-md border border-white/10 bg-white/[0.06] px-1.5 py-0.5 text-[10px] text-white/58">#{candidate.rank}</span>
                                <h3 className="text-xl font-bold text-white tracking-tight">{candidate.symbol}</h3>
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

                          <div className="mt-4 grid gap-3">
                            <section>
                              <p className="mb-1 text-[10px] uppercase tracking-[0.18em] text-white/34">{language === 'en' ? 'Why selected' : '入选依据'}</p>
                              <p className="text-sm leading-relaxed text-white/66">{getKeyReason(candidate, runDetail, language)}</p>
                              {candidate.featureSignals?.length ? (
                                <div className="mt-2 flex flex-wrap gap-1.5">
                                  {candidate.featureSignals.slice(0, 4).map((signal) => (
                                    <FieldChip key={`${candidate.symbol}-${signal.label}-${signal.value}`} label={signal.label} value={signal.value} />
                                  ))}
                                </div>
                              ) : null}
                            </section>

                            <section className="grid grid-cols-1 gap-2 rounded-xl border border-white/5 bg-black/20 p-3 sm:grid-cols-3">
                              <div>
                                <div className="text-[10px] text-white/40 mb-1 uppercase">{language === 'en' ? 'Entry range' : '建仓区间'}</div>
                                <div className="text-sm text-white font-medium">{entryRange || '--'}</div>
                              </div>
                              <div>
                                <div className="text-[10px] text-white/40 mb-1 uppercase">{language === 'en' ? 'Target price' : '目标价'}</div>
                                <div className="text-sm font-medium text-white">{targetPrice || '--'}</div>
                              </div>
                              <div>
                                <div className="text-[10px] text-white/40 mb-1 uppercase">{language === 'en' ? 'Stop loss' : '止损位'}</div>
                                <div className="text-sm text-red-300 font-medium">{stopLoss || '--'}</div>
                              </div>
                            </section>

                            <section>
                              <p className="mb-1 text-[10px] uppercase tracking-[0.18em] text-white/34">{language === 'en' ? 'Risk notes' : '风险说明'}</p>
                              <p className="text-sm leading-relaxed text-white/58">{getRiskSummary(candidate, language)}</p>
                            </section>

                            {candidate.keyMetrics?.length ? (
                              <section>
                                <p className="mb-2 text-[10px] uppercase tracking-[0.18em] text-white/34">{language === 'en' ? 'Metrics' : '指标'}</p>
                                <LabeledValueGrid items={candidate.keyMetrics.slice(0, 5)} empty="" />
                              </section>
                            ) : null}

                            <div className="flex flex-wrap gap-2 pt-1">
                              <ActionButton
                                label={pendingAnalyzeSymbol === candidate.symbol ? (language === 'en' ? 'Analyzing...' : '分析中...') : (language === 'en' ? 'Analyze' : '分析')}
                                icon={<Play className="h-3.5 w-3.5" />}
                                onClick={() => void handleAnalyzeCandidate(candidate)}
                                disabled={pendingAnalyzeSymbol === candidate.symbol}
                                variant="primary"
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
                                disabled
                                title={backtestUnavailableLabel}
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
                              isAnalyzing={pendingAnalyzeSymbol === candidate.symbol}
                              isCopied={copiedKey === `candidate:${candidate.symbol}`}
                              backtestUnavailableLabel={backtestUnavailableLabel}
                            />
                          ) : null}
                        </article>
                      );
                    })}
                  </div>
                ) : (
                  <div data-testid="scanner-result-table" className="overflow-x-auto rounded-2xl border border-white/5 bg-white/[0.02]">
                    <table className="min-w-[980px] w-full border-collapse text-left text-sm">
                      <thead className="border-b border-white/5 bg-black/25 text-[10px] uppercase tracking-[0.16em] text-white/38">
                        <tr>
                          <th className="px-3 py-3">{language === 'en' ? 'Rank' : '排名'}</th>
                          <th className="px-3 py-3">{language === 'en' ? 'Symbol' : '代码'}</th>
                          <th className="px-3 py-3">{language === 'en' ? 'Name' : '名称'}</th>
                          <th className="px-3 py-3">{language === 'en' ? 'Scanner score' : '扫描评分'}</th>
                          <th className="px-3 py-3">{language === 'en' ? 'Entry range' : '建仓区间'}</th>
                          <th className="px-3 py-3">{language === 'en' ? 'Target price' : '目标价'}</th>
                          <th className="px-3 py-3">{language === 'en' ? 'Stop loss' : '止损位'}</th>
                          <th className="px-3 py-3">{language === 'en' ? 'Key reason' : '关键原因'}</th>
                          <th className="px-3 py-3">{language === 'en' ? 'Risk summary' : '风险摘要'}</th>
                          <th className="px-3 py-3">{language === 'en' ? 'Data/source' : '数据/来源'}</th>
                          <th className="px-3 py-3">{language === 'en' ? 'Actions' : '操作'}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sortedCandidates.map((candidate) => {
                          const isExpanded = expandedSymbol === candidate.symbol;
                          return (
                            <React.Fragment key={`table-${candidate.symbol}`}>
                              <tr
                                data-testid={`scanner-result-row-${candidate.symbol}`}
                                className="cursor-pointer border-b border-white/5 text-white/72 hover:bg-white/[0.035]"
                                onClick={() => setExpandedSymbol(isExpanded ? null : candidate.symbol)}
                              >
                                <td className="px-3 py-3 text-white/45">#{candidate.rank}</td>
                                <td className="px-3 py-3 font-semibold text-white">{candidate.symbol}</td>
                                <td className="px-3 py-3 text-white/55">{candidate.companyName || candidate.name}</td>
                                <td className="px-3 py-3">
                                  <span className={`inline-flex rounded border px-1.5 py-0.5 text-[10px] font-bold ${scoreBadgeClass(candidate.score)}`}>
                                    {candidate.score}/100
                                  </span>
                                </td>
                                <td className="px-3 py-3">{getEntryRange(candidate) || '--'}</td>
                                <td className="px-3 py-3">{getTargetPrice(candidate) || '--'}</td>
                                <td className="px-3 py-3">{getStopLoss(candidate) || '--'}</td>
                                <td className="max-w-[220px] px-3 py-3 text-white/62">{getKeyReason(candidate, runDetail, language)}</td>
                                <td className="max-w-[180px] px-3 py-3 text-white/52">{getRiskSummary(candidate, language)}</td>
                                <td className="max-w-[180px] px-3 py-3 text-white/42">{getSourceBadge(candidate, runDetail, language) || '--'}</td>
                                <td className="px-3 py-3">
                                  <div className="flex flex-wrap gap-2">
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
                                      isAnalyzing={pendingAnalyzeSymbol === candidate.symbol}
                                      isCopied={copiedKey === `candidate:${candidate.symbol}`}
                                      backtestUnavailableLabel={backtestUnavailableLabel}
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
                  title={emptyStateTitle}
                  body={pageError?.message || emptyStateBody}
                />
              )}

              {runDetail ? <DiagnosticsPanel runDetail={runDetail} language={language} /> : null}
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
