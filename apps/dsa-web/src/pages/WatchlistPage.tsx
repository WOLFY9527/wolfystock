import { useEffect, useMemo, useState, type ComponentProps } from 'react';
import {
  BarChart3,
  CheckSquare,
  Copy,
  ExternalLink,
  Play,
  RefreshCw,
  Search,
  Trash2,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { analysisApi, DuplicateTaskError } from '../api/analysis';
import { backtestApi } from '../api/backtest';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { watchlistApi } from '../api/watchlist';
import { ConsumerProtectedFrame, ConsumerWorkspacePageShell, ConsumerWorkspaceScope } from '../components/layout/ConsumerWorkspaceShell';
import { ApiErrorAlert, Input, Select } from '../components/common';
import {
  ConsoleBoard,
  ConsoleContextRail,
  CompactFilterBar,
  DenseRows,
} from '../components/linear';
import {
  CompactEmptyRow,
  DenseCommandBar,
  DensePageHeader,
  DenseSecondaryDisclosure,
  DenseStatusStrip,
  DenseTableShell,
  TerminalButton,
  TerminalChip,
  TerminalNotice,
  TerminalPanel,
} from '../components/terminal';
import { useI18n } from '../contexts/UiLanguageContext';
import { useProductSurface } from '../hooks/useProductSurface';
import type { WatchlistItem } from '../types/watchlist';
import type { RuleBacktestRunResponse } from '../types/backtest';
import { describeBooleanEnabled, describeDisplayStatus, type DisplayStatusTone } from '../utils/displayStatus';
import { buildLocalizedPath } from '../utils/localeRouting';
import { sanitizeUserFacingDataIssue } from '../utils/userFacingDataIssues';

type SortKey = 'newest' | 'scannerScore' | 'backtestReturn' | 'historicalHitRate' | 'recentlyScored' | 'recentlyBacktested' | 'symbol' | 'market';
type EvidenceFilter = 'all' | 'hasScanner' | 'hasBacktest' | 'scannerSelected' | 'staleIntelligence';
type BatchStatus = 'requested' | 'running' | 'completed' | 'failed' | 'skipped';
type Notice = { tone: 'success' | 'warning' | 'danger'; message: string } | null;
type FailureReason = '数据不足' | '行情缺失' | '服务暂不可用' | '回测失败' | '扫描失败' | '超时' | '未知错误';
type BatchFailure = { label: FailureReason; detail?: string };
type WatchlistTrustState = 'fresh' | 'stale' | 'unknown';
type WatchlistScoreDisclosureState = 'fresh' | 'stale' | 'limitedConfidence' | 'unknown' | 'failed';
type WatchlistConclusionModel = {
  title: string;
  detail: string;
  freshCount: number;
  staleCount: number;
  unknownCount: number;
  limitedConfidenceCount: number;
  tone: 'success' | 'caution' | 'neutral';
};
type BatchProgress = {
  kind: 'scan' | 'backtest';
  total: number;
  completed: number;
  succeeded: number;
  failed: number;
  currentSymbol: string | null;
  failures: Record<string, BatchFailure>;
} | null;

type WatchlistMonitoringTone = 'success' | 'caution' | 'neutral';

const ROW_SELECTION_BUTTON_CLASS = 'inline-flex h-[32px] w-[32px] shrink-0 items-center justify-center rounded-lg border transition hover:border-white/30 hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/35';

function normalizeText(value?: string | null): string {
  return String(value || '').trim();
}

function terminalChipVariant(tone: DisplayStatusTone): React.ComponentProps<typeof TerminalChip>['variant'] {
  if (tone === 'success') return 'success';
  if (tone === 'warning') return 'caution';
  if (tone === 'danger') return 'danger';
  if (tone === 'info') return 'info';
  return 'neutral';
}

function normalizeMarket(value?: string | null): string {
  return normalizeText(value).toUpperCase();
}

function formatMarket(value?: string | null): string {
  const market = normalizeMarket(value);
  if (market === 'CN') return 'A股';
  if (market === 'HK') return '港股';
  if (market === 'US') return 'US';
  return market || '--';
}

function formatWatchlistOrigin(value?: string | null, language: 'zh' | 'en' = 'zh'): string {
  const token = normalizeToken(value);
  if (token === 'scanner' || token === 'scanner_run') return language === 'en' ? 'Scanner candidate' : '扫描候选';
  if (token === 'portfolio') return language === 'en' ? 'Portfolio watch' : '组合观察';
  if (token === 'manual') return language === 'en' ? 'Manual add' : '手动加入';
  if (token === 'imported' || token === 'import') return language === 'en' ? 'Imported' : '批量导入';
  return language === 'en' ? 'Watch item' : '观察标的';
}

function formatDateTime(value?: string | null, language: 'zh' | 'en' = 'zh'): string {
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

function getItemTime(item: WatchlistItem): number {
  const value = item.updatedAt || item.createdAt;
  if (!value) return 0;
  const parsed = new Date(value).getTime();
  return Number.isNaN(parsed) ? 0 : parsed;
}

function isRecentlyAdded(item: WatchlistItem): boolean {
  if (!item.createdAt) return false;
  const parsed = new Date(item.createdAt).getTime();
  if (Number.isNaN(parsed)) return false;
  return Date.now() - parsed <= 7 * 24 * 60 * 60 * 1000;
}

function formatScore(value?: number | null): string {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(1) : '--';
}

function formatPct(value?: number | null): string {
  return typeof value === 'number' && Number.isFinite(value) ? `${value >= 0 ? '+' : ''}${value.toFixed(1)}%` : '--';
}

function formatRatio(value?: number | null): string {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(2) : '--';
}

function getNumeric(value?: number | null): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : Number.NEGATIVE_INFINITY;
}

function getTime(value?: string | null): number {
  if (!value) return 0;
  const parsed = new Date(value).getTime();
  return Number.isNaN(parsed) ? 0 : parsed;
}

function getScannerScore(item: WatchlistItem): number | null {
  return item.scannerScore ?? item.intelligence?.scanner?.lastScore ?? null;
}

function getScannerStatus(item: WatchlistItem): string {
  return normalizeText(item.intelligence?.scanner?.status || item.scoreStatus || 'unknown') || 'unknown';
}

function getBacktestReturn(item: WatchlistItem): number | null {
  return item.intelligence?.backtest?.totalReturnPct ?? null;
}

function hasBacktestMetrics(item: WatchlistItem): boolean {
  const backtest = item.intelligence?.backtest;
  return typeof backtest?.totalReturnPct === 'number'
    || typeof backtest?.maxDrawdownPct === 'number'
    || typeof backtest?.sharpe === 'number'
    || typeof backtest?.tradeCount === 'number';
}

function getHitRate(item: WatchlistItem): number | null {
  return item.intelligence?.strategySimulation?.hitRate ?? null;
}

function hasScannerEvidence(item: WatchlistItem): boolean {
  return getScannerScore(item) !== null || Boolean(item.scannerRunId || item.intelligence?.scanner?.profile);
}

function hasBacktestEvidence(item: WatchlistItem): boolean {
  return item.intelligence?.backtest?.lastResultId != null || hasBacktestMetrics(item);
}

function isStaleIntelligence(item: WatchlistItem): boolean {
  return normalizeText(item.scoreStatus).toLowerCase() === 'stale'
    || normalizeText(item.intelligence?.strategySimulation?.status).toLowerCase() === 'partial';
}

function hasFailureOrNoData(item: WatchlistItem): boolean {
  const scannerStatus = normalizeText(item.intelligence?.scanner?.status || item.scoreStatus).toLowerCase();
  const simulationStatus = normalizeText(item.intelligence?.strategySimulation?.status).toLowerCase();
  return ['data_failed', 'provider_down', 'provider_error', 'error', 'failed', 'critical'].includes(scannerStatus)
    || ['insufficient_history', 'data_failed', 'no_data', 'missing_data', 'partial'].includes(simulationStatus)
    || (!hasScannerEvidence(item) && !hasBacktestEvidence(item));
}

function getLatestIntelligenceTime(item: WatchlistItem): string | null {
  const values = [
    item.intelligence?.backtest?.testedAt,
    item.intelligence?.scanner?.lastScannedAt,
    item.lastScoredAt,
    item.updatedAt,
  ].filter(Boolean) as string[];
  return values.sort((left, right) => getTime(right) - getTime(left))[0] || null;
}

function formatFreshness(value?: string | null): string {
  if (!value) return '时间未知';
  const parsed = new Date(value).getTime();
  if (Number.isNaN(parsed)) return '时间未知';
  const ageMs = Date.now() - parsed;
  if (ageMs < 0) return '刚刚';
  if (ageMs <= 60 * 60 * 1000) return '刚刚';
  if (ageMs <= 24 * 60 * 60 * 1000) return '今日';
  if (ageMs <= 7 * 24 * 60 * 60 * 1000) return '今日';
  return '已过期';
}

function isFallbackTrustSource(value?: string | null): boolean {
  const token = normalizeToken(value);
  return token.includes('fallback') || token.includes('proxy');
}

function hasLimitedConfidenceScoreContext(item: WatchlistItem): boolean {
  return [
    item.scoreSource,
    item.scoreStatus,
    item.scoreReason,
    item.intelligence?.scanner?.status,
    item.intelligence?.scanner?.reason,
  ].some(isFallbackTrustSource);
}

function getScoreDisclosureState(item: WatchlistItem): WatchlistScoreDisclosureState {
  const status = normalizeToken(item.scoreStatus);
  if (['data_failed', 'provider_down', 'provider_error', 'failed', 'error', 'critical'].includes(status)) {
    return 'failed';
  }
  if (hasLimitedConfidenceScoreContext(item)) return 'limitedConfidence';
  if (['stale', 'partial'].includes(status)) return 'stale';
  if (status === 'fresh') return 'fresh';
  return 'unknown';
}

function formatScoreDisclosureFreshness(item: WatchlistItem, value: string | null | undefined, language: 'zh' | 'en'): string {
  const state = getScoreDisclosureState(item);
  if (state === 'stale' || state === 'limitedConfidence') return language === 'en' ? 'Recent available' : '最近可用';
  if (state === 'unknown') return language === 'en' ? 'Updating' : '更新中';
  return formatFreshness(value);
}

function formatScoreDisclosureStatus(state: WatchlistScoreDisclosureState, language: 'zh' | 'en'): string {
  if (language === 'en') {
    if (state === 'fresh') return 'Signal fresh';
    if (state === 'stale' || state === 'limitedConfidence') return 'Limited confidence';
    if (state === 'failed') return 'Scan failed';
    return 'Updating';
  }
  if (state === 'fresh') return '信号最新';
  if (state === 'stale' || state === 'limitedConfidence') return '置信度较低';
  if (state === 'failed') return '扫描失败';
  return '数据更新中';
}

function scoreDisclosureChipVariant(state: WatchlistScoreDisclosureState): React.ComponentProps<typeof TerminalChip>['variant'] {
  if (state === 'fresh') return 'success';
  if (state === 'failed') return 'danger';
  if (state === 'stale' || state === 'limitedConfidence' || state === 'unknown') return 'caution';
  return 'neutral';
}

function scannerStatusChipVariant(label: string): React.ComponentProps<typeof TerminalChip>['variant'] {
  if (label === '扫描失败') return 'danger';
  if (label === '已验证' || label === '通过筛选') return 'info';
  if (['置信度较低', '数据更新中', '最近数据'].includes(label)) return 'caution';
  return 'neutral';
}

function formatScoreDisclosureNotice(state: WatchlistScoreDisclosureState, language: 'zh' | 'en'): string | null {
  if (state === 'stale') {
    return language === 'en'
      ? 'Using the most recent available data.'
      : '已使用最近一次可用数据。';
  }
  if (state === 'limitedConfidence') {
    return language === 'en'
      ? 'Some watchlist data is temporarily unavailable; using the most recent available data.'
      : '部分自选股数据暂不可用，已使用最近一次可用数据。';
  }
  if (state === 'unknown') {
    return language === 'en'
      ? 'Data is updating and will refresh shortly.'
      : '数据更新中，稍后将自动刷新。';
  }
  return null;
}

function formatScannerStatus(item: WatchlistItem): string {
  const status = normalizeText(item.intelligence?.scanner?.status || item.scoreStatus).toLowerCase();
  const simulationStatus = normalizeText(item.intelligence?.strategySimulation?.status).toLowerCase();
  const scoreDisclosureState = getScoreDisclosureState(item);
  if (scoreDisclosureState === 'failed') return '扫描失败';
  if (['data_failed', 'provider_down', 'provider_error', 'error', 'failed', 'critical'].includes(status)) return '扫描失败';
  if (scoreDisclosureState === 'stale' || scoreDisclosureState === 'limitedConfidence') return '置信度较低';
  if (scoreDisclosureState === 'unknown') return hasScannerEvidence(item) ? '数据更新中' : '未扫描';
  if (['selected', 'verified', 'ready', 'fresh'].includes(status)) return '已验证';
  if (['preview', 'candidate', 'passed'].includes(status)) return '通过筛选';
  if (['rejected', 'not_selected', 'failed_filter'].includes(status)) return '未通过';
  if (simulationStatus === 'insufficient_history' || status === 'insufficient_history') return '数据不足';
  if (!hasScannerEvidence(item)) return '未扫描';
  return '通过筛选';
}

function formatScannerReason(reason?: string | null, language: 'zh' | 'en' = 'zh'): string | null {
  const raw = String(reason || '').trim();
  if (!raw) return null;
  const normalized = raw.toLowerCase();
  if (normalized === 'unknown' || normalized.includes('debug') || normalized.includes('critical')) {
    return null;
  }
  if (
    /fallback|proxy|reasonfamilies|reasoncode|sourceauthorityallowed|scorecontributionallowed|observationonly|source_confidence|score_blocked|raw diagnostics?|json/.test(normalized)
  ) {
    return null;
  }
  if (/provider|timeout|history|missing|insufficient|not_enough|unavailable|data_failed/.test(normalized)) {
    return sanitizeUserFacingDataIssue(raw, language);
  }
  if (/^[a-z0-9_:-]+$/.test(raw)) {
    return null;
  }
  return raw;
}

function normalizeToken(value?: string | null): string {
  return normalizeText(value).toLowerCase();
}

function getTrustState(item: WatchlistItem): WatchlistTrustState {
  const state = getScoreDisclosureState(item);
  if (state === 'fresh') return 'fresh';
  if (state === 'unknown') return 'unknown';
  return 'stale';
}

function hasLimitedConfidenceDisclosure(item: WatchlistItem): boolean {
  return isFallbackTrustSource(item.scoreSource)
    || isFallbackTrustSource(item.source)
    || isFallbackTrustSource(item.scoreReason)
    || isFallbackTrustSource(item.intelligence?.scanner?.reason)
    || isFallbackTrustSource(item.intelligence?.scanner?.status);
}

function buildWatchlistConclusion(items: WatchlistItem[], language: 'zh' | 'en'): WatchlistConclusionModel {
  let freshCount = 0;
  let staleCount = 0;
  let unknownCount = 0;
  let limitedConfidenceCount = 0;

  items.forEach((item) => {
    const state = getTrustState(item);
    if (state === 'fresh') freshCount += 1;
    else if (state === 'stale') staleCount += 1;
    else unknownCount += 1;

    if (hasLimitedConfidenceDisclosure(item)) {
      limitedConfidenceCount += 1;
    }
  });

  const topItem = [...items]
    .filter((item) => getTrustState(item) === 'fresh' && getScannerScore(item) !== null)
    .sort((left, right) => (getScannerScore(right) ?? Number.NEGATIVE_INFINITY) - (getScannerScore(left) ?? Number.NEGATIVE_INFINITY))[0] || null;
  if (!items.length) {
    return {
      title: language === 'en' ? 'Needs watch items' : '需要观察标的',
      detail: language === 'en'
        ? 'Add scanner candidates before treating this page as evidence.'
        : '先从扫描器加入候选，再将观察列表作为证据。',
      freshCount,
      staleCount,
      unknownCount,
      limitedConfidenceCount,
      tone: 'neutral',
    };
  }
  if (!topItem) {
    return {
      title: language === 'en' ? 'Data updating' : '数据更新中',
      detail: language === 'en'
        ? 'Some items need a refresh before reference.'
        : '部分项目需要刷新后再参考。',
      freshCount,
      staleCount,
      unknownCount,
      limitedConfidenceCount,
      tone: 'caution',
    };
  }

  const symbol = normalizeText(topItem.symbol).toUpperCase() || topItem.symbol || '--';
  const detail = limitedConfidenceCount > 0
    ? (language === 'en'
      ? 'Current signal confidence is limited; use for observation only.'
      : '当前信号置信度较低，仅供观察。')
    : staleCount > 0
      ? (language === 'en'
        ? 'Some watchlist data is temporarily unavailable; using the most recent available data.'
        : '部分自选股数据暂不可用，已使用最近一次可用数据。')
      : unknownCount > 0
        ? (language === 'en'
          ? 'Data is updating and will refresh shortly.'
          : '数据更新中，稍后将自动刷新。')
        : (language === 'en'
          ? `Review ${symbol}'s score freshness, confidence, and backtest summary.`
          : `查看 ${symbol} 的评分鲜度、置信度和回测概览。`);
  return {
    title: language === 'en' ? `Current focus ${symbol}` : `当前焦点 ${symbol}`,
    detail,
    freshCount,
    staleCount,
    unknownCount,
    limitedConfidenceCount,
    tone: staleCount || unknownCount || limitedConfidenceCount ? 'caution' : 'success',
  };
}

function formatMonitoringStateLabel(tone: WatchlistMonitoringTone, total: number, language: 'zh' | 'en'): string {
  if (total === 0) return language === 'en' ? 'Waiting for watch items' : '等待加入观察';
  if (tone === 'success') return language === 'en' ? 'Ready to monitor' : '可继续观察';
  if (tone === 'caution') return language === 'en' ? 'Needs attention' : '需要留意';
  return language === 'en' ? 'Monitoring' : '监控中';
}

function buildObservationSummary(item: WatchlistItem, language: 'zh' | 'en'): string {
  const latestTime = getLatestIntelligenceTime(item);
  const hitRate = item.intelligence?.strategySimulation?.hitRate;
  const returnPct = item.intelligence?.backtest?.totalReturnPct;
  const parts: string[] = [];

  if (latestTime) {
    parts.push(`${language === 'en' ? 'Updated' : '更新'} ${formatDateTime(latestTime, language)}`);
  }
  if (typeof hitRate === 'number') {
    parts.push(`${language === 'en' ? 'Hit' : '命中'} ${Math.round(hitRate * 100)}%`);
  }
  if (typeof returnPct === 'number') {
    parts.push(`${language === 'en' ? 'Backtest' : '回测'} ${formatPct(returnPct)}`);
  }

  if (parts.length === 0) {
    return language === 'en' ? 'Waiting for more watch evidence.' : '等待更多观察数据。';
  }

  return parts.join(' · ');
}

function buildWatchRiskNote(item: WatchlistItem, language: 'zh' | 'en'): string | null {
  const state = getScoreDisclosureState(item);
  const notice = formatScoreDisclosureNotice(state, language);
  if (notice) return notice;
  if (state === 'failed') {
    return language === 'en'
      ? 'This signal is temporarily unavailable. Refresh before using it.'
      : '当前信号暂不可用，刷新后再参考。';
  }
  if (!hasScannerEvidence(item) && !hasBacktestEvidence(item)) {
    return language === 'en'
      ? 'Data is updating and will refresh shortly.'
      : '数据更新中，稍后将自动刷新。';
  }
  if (normalizeText(item.intelligence?.strategySimulation?.status).toLowerCase() === 'insufficient_history') {
    return language === 'en'
      ? 'History is still limited, so keep this item in observation mode.'
      : '样本仍然有限，先保持观察。';
  }
  return null;
}

function buildNextActionLabel(item: WatchlistItem, language: 'zh' | 'en'): string {
  const state = getScoreDisclosureState(item);
  if (state === 'failed' || state === 'unknown') {
    return language === 'en' ? 'Refresh and review' : '刷新后再看';
  }
  if (!hasBacktestEvidence(item)) {
    return language === 'en' ? 'Run backtest' : '补充回测';
  }
  if (hasLimitedConfidenceDisclosure(item)) {
    return language === 'en' ? 'Keep observing' : '保持观察';
  }
  return language === 'en' ? 'Open analysis' : '进入分析';
}

function formatBacktestStatus(item: WatchlistItem, failure?: BatchFailure): string {
  if (failure) return failure.label;
  const simulationStatus = normalizeText(item.intelligence?.strategySimulation?.status).toLowerCase();
  if (hasBacktestEvidence(item)) return '已回测';
  if (simulationStatus === 'insufficient_history') return '样本不足';
  if (['data_failed', 'no_data', 'missing_data'].includes(simulationStatus)) return '数据缺失';
  return '未回测';
}

function sanitizeFailureReason(error: unknown, fallback: FailureReason): BatchFailure {
  const raw = error instanceof Error ? error.message : typeof error === 'string' ? error : '';
  const value = raw.toLowerCase();
  let label: FailureReason = fallback;
  if (value.includes('provider') || value.includes('service') || value.includes('unavailable') || value.includes('down')) label = '服务暂不可用';
  else if (value.includes('timeout') || value.includes('timed out')) label = '超时';
  else if (value.includes('quote') || value.includes('market') || value.includes('missing')) label = '行情缺失';
  else if (value.includes('insufficient') || value.includes('sample')) label = '数据不足';
  else if (!raw) label = fallback;
  return { label, detail: raw || undefined };
}

function formatDateInput(date: Date): string {
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function buildDefaultBacktestWindow(): { startDate: string; endDate: string } {
  const end = new Date(Date.now());
  const start = new Date(end);
  start.setFullYear(start.getFullYear() - 1);
  return { startDate: formatDateInput(start), endDate: formatDateInput(end) };
}

function buildBacktestIntelligence(run: RuleBacktestRunResponse): NonNullable<WatchlistItem['intelligence']>['backtest'] {
  return {
    lastResultId: run.id,
    totalReturnPct: run.totalReturnPct ?? null,
    maxDrawdownPct: run.maxDrawdownPct ?? null,
    sharpe: run.sharpeRatio ?? null,
    tradeCount: run.tradeCount ?? null,
    testedAt: run.completedAt || run.runAt || null,
  };
}

function buildBacktestPath(item: WatchlistItem, language: 'zh' | 'en'): string {
  const params = new URLSearchParams({
    symbol: item.symbol,
    source: 'scanner',
    origin: 'watchlist',
    watchlistItemId: String(item.id),
  });
  const market = normalizeMarket(item.market);
  if (market) params.set('market', market);
  if (item.scannerRunId) params.set('scannerRunId', String(item.scannerRunId));
  if (item.scannerRank) params.set('scannerRank', String(item.scannerRank));
  if (item.themeId) params.set('themeId', item.themeId);
  if (item.universeType) params.set('universeType', item.universeType);
  return buildLocalizedPath(`/backtest?${params.toString()}`, language);
}

function extractAcceptedTaskId(response: Awaited<ReturnType<typeof analysisApi.analyzeAsync>>): string | null {
  if ('taskId' in response) {
    return response.taskId;
  }
  return response.accepted?.[0]?.taskId || response.duplicates?.[0]?.existingTaskId || null;
}

function buildWatchlistAnalysisPath(item: WatchlistItem, taskId: string, language: 'zh' | 'en'): string {
  const params = new URLSearchParams({
    symbol: item.symbol,
    task_id: taskId,
    source: 'watchlist',
  });
  const market = normalizeMarket(item.market);
  if (market) params.set('market', market);
  return buildLocalizedPath(`/?${params.toString()}`, language);
}

function getCopy(language: 'zh' | 'en') {
  if (language === 'en') {
    return {
      title: 'Watchlist',
      subtitle: 'Clean monitoring list for scanner candidates.',
      totalTracked: 'Total tracked',
      marketsRepresented: 'Markets represented',
      scannerSourced: 'Scanner-sourced',
      recentlyAdded: 'Recently added',
      trackedSymbols: 'Tracked symbols',
      scannerCoverage: 'Scanner results',
      backtestCoverage: 'Backtest results',
      staleCoverage: 'Recent available',
      failureCoverage: 'Unavailable',
      latestUpdate: 'Latest update',
      filters: 'Filters',
      advancedFilters: 'Advanced filters',
      runtimeStatus: 'Batch progress',
      batchActions: 'Batch actions',
      historyPrefix: 'HIST',
      hitPrefix: 'HIT',
      search: 'Search',
      searchPlaceholder: 'Symbol or name',
      market: 'Market',
      source: 'Added from',
      context: 'Theme / universe',
      sort: 'Sort',
      all: 'All',
      newest: 'Newest',
      scannerScore: 'Scanner score',
      backtestReturn: 'Backtest return',
      historicalHitRate: 'Historical hit rate',
      recentlyScored: 'Recently scored',
      recentlyBacktested: 'Recently backtested',
      evidence: 'Evidence',
      hasScanner: 'Has scanner evidence',
      hasBacktest: 'Has backtest evidence',
      scannerSelected: 'Selected by scanner',
      staleIntelligence: 'Recent available data',
      intelligence: 'Intelligence',
      noEvidence: 'Evidence updating',
      batchBacktestFilter: 'Backtest current filter',
      batchScanFilter: 'Scan current filter',
      selectedOnly: 'Selected only',
      clearSelection: 'Clear selection',
      refreshIntelligence: 'Refresh intelligence',
      scopeSelected: 'selected symbols',
      scopeFiltered: 'filtered symbols',
      emptyFilteredSet: 'Current filter is empty',
      noMatchedSymbols: 'No matching symbols',
      scanComplete: 'Scanner refresh completed.',
      batchBacktesting: 'Backtesting...',
      batchBacktestComplete: 'Watchlist backtest completed.',
      batchBacktestLabel: 'Single-symbol watchlist backtest',
      batchBacktestMeta: 'symbols · concurrency 2',
      resultPrefix: 'Result',
      symbol: 'Symbol',
      name: 'Name',
      score: 'Score',
      rank: 'Rank',
      lastScored: 'Last scored',
      scoreFreshness: 'Score freshness',
      signalTrust: 'Signal trust',
      trustUpdated: 'Trust updated',
      refreshScores: 'Refresh scores',
      refreshingScores: 'Refreshing...',
      autoRefresh: 'Auto refresh',
      enabled: 'Enabled',
      stale: 'Stale',
      fresh: 'Fresh',
      sourceUnknownNeedsRefresh: 'Data is updating and will refresh shortly.',
      added: 'Added',
      actions: 'Actions',
      analyze: 'Analyze',
      analyzing: 'Analyzing...',
      backtest: 'Backtest',
      remove: 'Remove',
      removing: 'Removing...',
      copySymbol: 'Copy symbol',
      copied: 'Copied',
      emptyTitle: 'No tracked candidates yet.',
      emptyBody: 'No watched symbols yet. Add candidates from Scanner, or adjust filters to review existing evidence.',
      openScanner: 'Open Scanner',
      tableTitle: 'Monitoring list',
      tableDescription: 'Rows keep state, observation, and actions aligned.',
      loading: 'Loading watchlist...',
      removed: 'Removed from watchlist.',
      copyFailed: 'Copy failed.',
      clipboardUnavailable: 'Clipboard is not available in this browser.',
      analyzeStarted: 'Analysis started.',
      scoreRefreshComplete: 'Scores refreshed.',
      signInModule: 'Watchlist',
      themePrefix: 'Theme',
      universePrefix: 'Universe',
    };
  }
  return {
    title: '观察列表',
    subtitle: '清晰跟踪每个标的的状态变化',
    totalTracked: '追踪总数',
    marketsRepresented: '覆盖市场',
    scannerSourced: '扫描来源',
    recentlyAdded: '近期新增',
    trackedSymbols: '观察标的数',
    scannerCoverage: '已有扫描结果',
    backtestCoverage: '已有回测结果',
    staleCoverage: '最近可用',
    failureCoverage: '暂不可用',
    latestUpdate: '最近更新时间',
    filters: '筛选',
    advancedFilters: '高级筛选',
    runtimeStatus: '批量进度',
    batchActions: '批量操作',
    historyPrefix: '历史',
    hitPrefix: '命中',
    search: '搜索',
    searchPlaceholder: '代码或名称',
    market: '市场',
    source: '加入方式',
    context: '主题 / 候选范围',
    sort: '排序',
    all: '全部',
    newest: '最新',
    scannerScore: '扫描分数',
    backtestReturn: '回测收益',
    historicalHitRate: '历史胜率',
    recentlyScored: '最近评分',
    recentlyBacktested: '最近回测',
    evidence: '证据筛选',
    hasScanner: '有扫描证据',
    hasBacktest: '有回测证据',
    scannerSelected: '扫描入选',
    staleIntelligence: '最近可用数据',
    intelligence: '观察依据',
    noEvidence: '依据更新中',
    batchBacktestFilter: '回测当前筛选',
    batchScanFilter: '扫描当前筛选',
    selectedOnly: '仅选中',
    clearSelection: '清除选择',
    refreshIntelligence: '刷新情报',
    scopeSelected: '已选中',
    scopeFiltered: '当前筛选',
    emptyFilteredSet: '当前筛选为空',
    noMatchedSymbols: '无匹配标的',
    scanComplete: '扫描刷新完成。',
    batchBacktesting: '回测中...',
    batchBacktestComplete: '观察列表回测完成。',
    batchBacktestLabel: '观察列表单标的回测',
    batchBacktestMeta: '个标的 · 并发 2',
    resultPrefix: '结果',
    symbol: '代码',
    name: '名称',
    score: '分数',
    rank: '排名',
    lastScored: '评分时间',
    scoreFreshness: '评分状态',
    signalTrust: '信号状态',
    trustUpdated: '信号更新时间',
    refreshScores: '刷新评分',
    refreshingScores: '刷新中...',
    autoRefresh: '自动刷新',
    enabled: '已启用',
    stale: '过期',
    fresh: '最新',
    sourceUnknownNeedsRefresh: '数据更新中，稍后将自动刷新。',
    added: '加入时间',
    actions: '操作',
    analyze: '分析',
    analyzing: '分析中...',
    backtest: '回测',
    remove: '移除',
    removing: '移除中...',
    copySymbol: '复制代码',
    copied: '已复制',
    emptyTitle: '还没有观察标的',
    emptyBody: '先从扫描器加入候选，再回到这里持续跟踪状态变化。',
    openScanner: '打开扫描器',
    tableTitle: '监控列表',
    tableDescription: '按行查看状态、观察与操作。',
    loading: '正在加载观察列表...',
    removed: '已从观察列表移除。',
    copyFailed: '复制失败。',
    clipboardUnavailable: '当前浏览器不支持剪贴板。',
    analyzeStarted: '已启动分析。',
    scoreRefreshComplete: '评分已刷新。',
    signInModule: '观察列表',
    themePrefix: '主题',
    universePrefix: '候选范围',
  };
}

function WatchlistConclusionBand({
  model,
  trackedCount,
  monitoringStateLabel,
  language,
}: {
  model: WatchlistConclusionModel;
  trackedCount: number;
  monitoringStateLabel: string;
  language: 'zh' | 'en';
}) {
  const toneVariant: ComponentProps<typeof TerminalChip>['variant'] = model.tone === 'success'
    ? 'success'
    : model.tone === 'caution'
      ? 'caution'
      : 'neutral';
  return (
    <TerminalPanel
      as="section"
      dense
      data-testid="watchlist-conclusion-band"
      className="grid gap-3 px-4 py-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-start"
    >
      <div className="min-w-0">
        <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--wolfy-text-muted)]">
          {language === 'en' ? 'Monitoring state' : '监控状态'}
        </p>
        <div className="mt-1 flex min-w-0 flex-wrap items-center gap-2">
          <h2 className="truncate text-xl font-semibold text-white md:text-2xl">{model.title}</h2>
          <TerminalChip variant={toneVariant} className="shrink-0">
            {monitoringStateLabel}
          </TerminalChip>
          <TerminalChip variant="neutral" className="font-mono">
            {language === 'en' ? 'Tracked' : '观察标的'} {trackedCount}
          </TerminalChip>
        </div>
        <p className="mt-2 text-sm leading-6 text-white/72">
          {model.detail}
        </p>
      </div>
      <div className="grid min-w-[180px] grid-cols-2 gap-2 text-xs md:w-[220px]">
        <div className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-2">
          <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">{language === 'en' ? 'Fresh' : '最新'}</p>
          <p className="mt-1 font-mono text-base font-semibold text-white">{model.freshCount}</p>
        </div>
        <div className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-2">
          <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">{language === 'en' ? 'Attention' : '需留意'}</p>
          <p className="mt-1 font-mono text-base font-semibold text-white">
            {model.staleCount + model.unknownCount + model.limitedConfidenceCount}
          </p>
        </div>
      </div>
    </TerminalPanel>
  );
}

const WatchlistPage: React.FC = () => {
  const navigate = useNavigate();
  const { language } = useI18n();
  const { isGuest } = useProductSurface();
  const copy = getCopy(language);
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const [query, setQuery] = useState('');
  const [marketFilter, setMarketFilter] = useState('all');
  const [sourceFilter, setSourceFilter] = useState('all');
  const [contextFilter, setContextFilter] = useState('all');
  const [evidenceFilter, setEvidenceFilter] = useState<EvidenceFilter>('all');
  const [sortKey, setSortKey] = useState<SortKey>('newest');
  const [pendingAnalyzeId, setPendingAnalyzeId] = useState<number | null>(null);
  const [pendingRemoveId, setPendingRemoveId] = useState<number | null>(null);
  const [isRefreshingScores, setRefreshingScores] = useState(false);
  const [refreshStatus, setRefreshStatus] = useState<{ enabled: boolean; usTime: string; cnTime: string; hkTime: string } | null>(null);
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [batchStatuses, setBatchStatuses] = useState<Record<string, BatchStatus>>({});
  const [batchFailures, setBatchFailures] = useState<Record<string, BatchFailure>>({});
  const [batchProgress, setBatchProgress] = useState<BatchProgress>(null);
  const [isBatchBacktesting, setIsBatchBacktesting] = useState(false);
  const [isBatchScanning, setIsBatchScanning] = useState(false);
  const [backtestSessionKeys, setBacktestSessionKeys] = useState<Set<string>>(() => new Set());
  const [selectedIds, setSelectedIds] = useState<Set<number>>(() => new Set());
  const [useSelectedScope, setUseSelectedScope] = useState(false);
  const [activeItemId, setActiveItemId] = useState<number | null>(null);
  const [advancedFiltersOpen, setAdvancedFiltersOpen] = useState(false);

  useEffect(() => {
    document.title = language === 'en' ? 'Watchlist - WolfyStock' : '观察列表 - WolfyStock';
  }, [language]);

  useEffect(() => {
    if (isGuest) return;
    let isMounted = true;
    setIsLoading(true);
    watchlistApi.listWatchlistItems()
      .then((response) => {
        if (!isMounted) return;
        setItems(response.items || []);
        setError(null);
      })
      .catch((err) => {
        if (!isMounted) return;
        setError(getParsedApiError(err));
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, [isGuest]);

  useEffect(() => {
    if (isGuest) return;
    let isMounted = true;
    watchlistApi.getRefreshStatus()
      .then((response) => {
        if (!isMounted) return;
        setRefreshStatus(response);
      })
      .catch(() => {
        if (!isMounted) return;
        setRefreshStatus(null);
      });
    return () => {
      isMounted = false;
    };
  }, [isGuest]);

  const marketOptions = (() => {
    const markets = Array.from(new Set(items.map((item) => normalizeText(item.market).toLowerCase()).filter(Boolean))).sort();
    return [
      { value: 'all', label: copy.all },
      ...markets.map((market) => ({ value: market, label: formatMarket(market) })),
    ];
  })();

  const sourceOptions = (() => {
    const sources = Array.from(new Set(items.map((item) => normalizeText(item.source).toLowerCase()).filter(Boolean))).sort();
    return [
      { value: 'all', label: copy.all },
      ...sources.map((source) => ({ value: source, label: formatWatchlistOrigin(source, language) })),
    ];
  })();

  const contextOptions = (() => {
    const options = new Map<string, string>();
    items.forEach((item) => {
      if (item.themeId) options.set(`theme:${item.themeId}`, `${copy.themePrefix}: ${item.themeId}`);
      if (item.universeType) options.set(`universe:${item.universeType}`, `${copy.universePrefix}: ${item.universeType}`);
    });
    return [
      { value: 'all', label: copy.all },
      ...Array.from(options.entries()).map(([value, label]) => ({ value, label })),
    ];
  })();

  const summary = (() => {
    const markets = new Set(items.map((item) => normalizeText(item.market).toLowerCase()).filter(Boolean));
    const scannerSourced = items.filter((item) => normalizeText(item.source).toLowerCase() === 'scanner').length;
    const latestTime = items.map(getLatestIntelligenceTime).filter(Boolean).sort((left, right) => getTime(right) - getTime(left))[0] || null;
    return {
      total: items.length,
      markets: markets.size,
      scannerSourced,
      recent: items.filter(isRecentlyAdded).length,
      scannerResults: items.filter(hasScannerEvidence).length,
      backtestResults: items.filter(hasBacktestEvidence).length,
      stale: items.filter(isStaleIntelligence).length,
      failedOrNoData: items.filter(hasFailureOrNoData).length,
      latestTime,
    };
  })();

  const filteredItems = (() => {
    const search = query.trim().toLowerCase();
    const rows = items.filter((item) => {
      const matchesSearch = !search
        || item.symbol.toLowerCase().includes(search)
        || normalizeText(item.name).toLowerCase().includes(search);
      const matchesMarket = marketFilter === 'all' || normalizeText(item.market).toLowerCase() === marketFilter;
      const matchesSource = sourceFilter === 'all' || normalizeText(item.source).toLowerCase() === sourceFilter;
      const matchesContext = contextFilter === 'all'
        || `theme:${item.themeId || ''}` === contextFilter
        || `universe:${item.universeType || ''}` === contextFilter;
      const matchesEvidence = evidenceFilter === 'all'
        || (evidenceFilter === 'hasScanner' && hasScannerEvidence(item))
        || (evidenceFilter === 'hasBacktest' && hasBacktestEvidence(item))
        || (evidenceFilter === 'scannerSelected' && getScannerStatus(item) === 'selected')
        || (evidenceFilter === 'staleIntelligence' && isStaleIntelligence(item));
      return matchesSearch && matchesMarket && matchesSource && matchesContext && matchesEvidence;
    });

    return rows.sort((left, right) => {
      if (sortKey === 'symbol') return left.symbol.localeCompare(right.symbol);
      if (sortKey === 'market') {
        const marketCompare = normalizeText(left.market).localeCompare(normalizeText(right.market));
        return marketCompare || left.symbol.localeCompare(right.symbol);
      }
      if (sortKey === 'scannerScore') {
        const leftScore = getScannerScore(left) ?? Number.NEGATIVE_INFINITY;
        const rightScore = getScannerScore(right) ?? Number.NEGATIVE_INFINITY;
        return rightScore - leftScore || (left.scannerRank ?? 9999) - (right.scannerRank ?? 9999);
      }
      if (sortKey === 'backtestReturn') return getNumeric(getBacktestReturn(right)) - getNumeric(getBacktestReturn(left));
      if (sortKey === 'historicalHitRate') return getNumeric(getHitRate(right)) - getNumeric(getHitRate(left));
      if (sortKey === 'recentlyScored') return getTime(right.intelligence?.scanner?.lastScannedAt || right.lastScoredAt) - getTime(left.intelligence?.scanner?.lastScannedAt || left.lastScoredAt);
      if (sortKey === 'recentlyBacktested') return getTime(right.intelligence?.backtest?.testedAt) - getTime(left.intelligence?.backtest?.testedAt);
      return getItemTime(right) - getItemTime(left);
    });
  })();

  useEffect(() => {
    setSelectedIds((current) => {
      const validIds = new Set(items.map((item) => item.id));
      const next = new Set(Array.from(current).filter((id) => validIds.has(id)));
      return next.size === current.size ? current : next;
    });
  }, [items]);

  useEffect(() => {
    if (selectedIds.size === 0 && useSelectedScope) {
      setUseSelectedScope(false);
    }
  }, [selectedIds.size, useSelectedScope]);

  useEffect(() => {
    if (filteredItems.length === 0) {
      if (activeItemId !== null) setActiveItemId(null);
      return;
    }
    if (!filteredItems.some((item) => item.id === activeItemId)) {
      setActiveItemId(filteredItems[0].id);
    }
  }, [activeItemId, filteredItems]);

  const selectedItems = useMemo(
    () => filteredItems.filter((item) => selectedIds.has(item.id)),
    [filteredItems, selectedIds],
  );
  const activeItem = useMemo(
    () => filteredItems.find((item) => item.id === activeItemId) ?? filteredItems[0] ?? null,
    [activeItemId, filteredItems],
  );
  const actionItems = useSelectedScope && selectedItems.length > 0 ? selectedItems : filteredItems;
  const actionScopeLabel = actionItems.length === 0
    ? copy.emptyFilteredSet
    : `${useSelectedScope && selectedItems.length > 0 ? copy.scopeSelected : copy.scopeFiltered} ${actionItems.length} ${language === 'zh' ? '个标的' : 'symbols'}`;
  const isActionDisabled = actionItems.length === 0 || isBatchBacktesting || isBatchScanning;
  const watchlistConclusion = buildWatchlistConclusion(filteredItems, language);

  const toggleSelected = (item: WatchlistItem) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(item.id)) next.delete(item.id);
      else next.add(item.id);
      setUseSelectedScope(next.size > 0);
      return next;
    });
  };

  const handleAnalyze = async (item: WatchlistItem) => {
    setPendingAnalyzeId(item.id);
    setNotice(null);
    try {
      const response = await analysisApi.analyzeAsync({
        stockCode: item.symbol,
        reportType: 'detailed',
        stockName: item.name || undefined,
        originalQuery: item.symbol,
        selectionSource: 'manual',
      });
      const taskId = extractAcceptedTaskId(response);
      setNotice({ tone: 'success', message: copy.analyzeStarted });
      navigate(taskId ? buildWatchlistAnalysisPath(item, taskId, language) : buildLocalizedPath('/', language));
    } catch (err) {
      if (err instanceof DuplicateTaskError) {
        navigate(buildWatchlistAnalysisPath(item, err.existingTaskId, language));
        return;
      }
      setNotice({ tone: 'danger', message: getParsedApiError(err).message });
    } finally {
      setPendingAnalyzeId((current) => (current === item.id ? null : current));
    }
  };

  const handleRemove = async (item: WatchlistItem) => {
    setPendingRemoveId(item.id);
    setNotice(null);
    try {
      await watchlistApi.removeWatchlistItem(item.id);
      setItems((current) => current.filter((row) => row.id !== item.id));
      setNotice({ tone: 'success', message: copy.removed });
    } catch (err) {
      setNotice({ tone: 'danger', message: getParsedApiError(err).message });
    } finally {
      setPendingRemoveId((current) => (current === item.id ? null : current));
    }
  };

  const handleCopy = async (item: WatchlistItem) => {
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error(copy.clipboardUnavailable);
      }
      await navigator.clipboard.writeText(item.symbol);
      setCopiedId(item.id);
      setNotice({ tone: 'success', message: `${item.symbol} ${copy.copied}` });
    } catch (err) {
      setNotice({ tone: 'danger', message: err instanceof Error ? err.message : copy.copyFailed });
    }
  };

  const handleRefreshIntelligence = async () => {
    setNotice(null);
    try {
      const [listResponse, statusResponse] = await Promise.all([
        watchlistApi.listWatchlistItems(),
        watchlistApi.getRefreshStatus().catch(() => null),
      ]);
      setItems(listResponse.items || []);
      setRefreshStatus(statusResponse);
    } catch (err) {
      setNotice({ tone: 'danger', message: getParsedApiError(err).message });
    }
  };

  const handleRefreshScores = async (targetItems?: WatchlistItem[]) => {
    const targets = targetItems || items;
    if (targets.length === 0 || isBatchScanning) return;
    setRefreshingScores(true);
    setIsBatchScanning(true);
    setBatchFailures({});
    setBatchProgress({
      kind: 'scan',
      total: targets.length,
      completed: 0,
      succeeded: 0,
      failed: 0,
      currentSymbol: targets[0]?.symbol || null,
      failures: {},
    });
    setNotice(null);
    try {
      const response = await watchlistApi.refreshScores(targetItems ? {
        force: true,
        symbols: targets.map((item) => item.symbol).filter(Boolean),
      } : { force: true });
      const listResponse = await watchlistApi.listWatchlistItems();
      const failures = Object.fromEntries(
        (response.results || [])
          .filter((result) => normalizeText(result.status).toLowerCase() === 'failed')
          .map((result) => [result.symbol, sanitizeFailureReason(result.message || '', '扫描失败')]),
      );
      setItems(listResponse.items || []);
      setBatchFailures(failures);
      setBatchProgress({
        kind: 'scan',
        total: targets.length,
        completed: targets.length,
        succeeded: Math.max(0, targets.length - Object.keys(failures).length),
        failed: Object.keys(failures).length,
        currentSymbol: null,
        failures,
      });
      setNotice({
        tone: response.failedCount > 0 ? 'warning' : 'success',
        message: `${targetItems ? copy.scanComplete : copy.scoreRefreshComplete} ${response.updatedCount}/${response.updatedCount + response.skippedCount + response.failedCount}`,
      });
    } catch (err) {
      const failure = sanitizeFailureReason(err, '扫描失败');
      const failures = Object.fromEntries(targets.map((item) => [item.symbol, failure]));
      setBatchFailures(failures);
      setBatchProgress({
        kind: 'scan',
        total: targets.length,
        completed: targets.length,
        succeeded: 0,
        failed: targets.length,
        currentSymbol: null,
        failures,
      });
      setNotice({ tone: 'danger', message: failure.label });
    } finally {
      setRefreshingScores(false);
      setIsBatchScanning(false);
    }
  };

  const handleBatchBacktestCurrentFilter = async () => {
    if (isBatchBacktesting) return;
    const uniqueItems = Array.from(
      new Map(actionItems.map((item) => [normalizeText(item.symbol).toUpperCase(), item])).values(),
    ).filter((item) => normalizeText(item.symbol));
    if (uniqueItems.length === 0) return;

    const { startDate, endDate } = buildDefaultBacktestWindow();
    const pendingItems = uniqueItems.filter((item) => {
      const key = `${normalizeText(item.symbol).toUpperCase()}:${startDate}:${endDate}:watchlist-default`;
      return !backtestSessionKeys.has(key);
    });
    const skippedItems = uniqueItems.filter((item) => !pendingItems.includes(item));
    if (skippedItems.length > 0) {
      setBatchStatuses((current) => ({
        ...current,
        ...Object.fromEntries(skippedItems.map((item) => [item.symbol, 'skipped' as BatchStatus])),
      }));
    }
    if (pendingItems.length === 0) return;

    setIsBatchBacktesting(true);
    setNotice(null);
    setBatchFailures({});
    setBatchProgress({
      kind: 'backtest',
      total: pendingItems.length,
      completed: 0,
      succeeded: 0,
      failed: 0,
      currentSymbol: pendingItems[0]?.symbol || null,
      failures: {},
    });
    setBatchStatuses((current) => ({
      ...current,
      ...Object.fromEntries(pendingItems.map((item) => [item.symbol, 'requested' as BatchStatus])),
    }));

    let cursor = 0;
    let completed = 0;
    let failed = 0;
    const runOne = async (item: WatchlistItem) => {
      const symbol = normalizeText(item.symbol).toUpperCase();
      const key = `${symbol}:${startDate}:${endDate}:watchlist-default`;
      setBacktestSessionKeys((current) => new Set(current).add(key));
      setBatchStatuses((current) => ({ ...current, [item.symbol]: 'running' }));
      setBatchProgress((current) => current ? { ...current, currentSymbol: item.symbol } : current);
      try {
        const run = await backtestApi.runRuleBacktest({
          code: item.symbol,
          strategyText: copy.batchBacktestLabel,
          startDate,
          endDate,
          initialCapital: 100000,
          feeBps: 0,
          slippageBps: 0,
          benchmarkMode: 'auto',
          confirmed: true,
          waitForCompletion: true,
        });
        completed += 1;
        setItems((current) => current.map((row) => (
          normalizeText(row.symbol).toUpperCase() === symbol
            ? {
                ...row,
                intelligence: {
                  ...(row.intelligence || {}),
                  backtest: buildBacktestIntelligence(run),
                },
              }
            : row
        )));
        setBatchStatuses((current) => ({ ...current, [item.symbol]: 'completed' }));
        setBatchProgress((current) => current ? {
          ...current,
          completed: current.completed + 1,
          succeeded: current.succeeded + 1,
          currentSymbol: null,
        } : current);
      } catch (err) {
        failed += 1;
        const failure = sanitizeFailureReason(err, '回测失败');
        setBatchFailures((current) => ({ ...current, [item.symbol]: failure }));
        setBatchStatuses((current) => ({ ...current, [item.symbol]: 'failed' }));
        setBatchProgress((current) => current ? {
          ...current,
          completed: current.completed + 1,
          failed: current.failed + 1,
          currentSymbol: null,
          failures: { ...current.failures, [item.symbol]: failure },
        } : current);
      }
    };

    const worker = async () => {
      while (cursor < pendingItems.length) {
        const next = pendingItems[cursor];
        cursor += 1;
        await runOne(next);
      }
    };

    try {
      await Promise.all(Array.from({ length: Math.min(2, pendingItems.length) }, () => worker()));
      setNotice({
        tone: failed > 0 ? 'warning' : 'success',
        message: `${copy.batchBacktestComplete} ${completed}/${pendingItems.length}`,
      });
    } finally {
      setIsBatchBacktesting(false);
    }
  };

  if (isGuest) {
    return <ConsumerProtectedFrame moduleName={copy.signInModule} />;
  }

  const noticeClassName = notice?.tone === 'danger'
    ? 'border-rose-400/20 bg-rose-500/5 text-rose-100/80'
    : notice?.tone === 'warning'
      ? 'border-amber-300/20 bg-amber-300/5 text-amber-100/80'
      : 'border-emerald-400/20 bg-emerald-400/5 text-emerald-100/80';
  const autoRefreshStatus = describeBooleanEnabled(refreshStatus?.enabled, { language });
  const scannerPath = buildLocalizedPath('/scanner', language);
  const attentionCount = watchlistConclusion.staleCount + watchlistConclusion.unknownCount + watchlistConclusion.limitedConfidenceCount;
  const monitoringStateLabel = formatMonitoringStateLabel(watchlistConclusion.tone, filteredItems.length, language);
  const statusItems = [
    { label: copy.trackedSymbols, value: summary.total },
    { label: language === 'en' ? 'Needs attention' : '需留意项目', value: attentionCount },
    { label: copy.latestUpdate, value: summary.latestTime ? formatDateTime(summary.latestTime, language) : (language === 'zh' ? '暂无情报' : 'No intelligence') },
  ];
  const activeScanner = activeItem?.intelligence?.scanner;
  const activeSimulation = activeItem?.intelligence?.strategySimulation;
  const activeBacktest = activeItem?.intelligence?.backtest;
  const activeScore = activeItem ? getScannerScore(activeItem) : null;
  const activeLatestTime = activeItem ? getLatestIntelligenceTime(activeItem) : null;
  const activeScoreDisclosureState = activeItem ? getScoreDisclosureState(activeItem) : 'unknown';
  const activeScannerStatusLabel = activeItem ? formatScannerStatus(activeItem) : '--';
  const activeBacktestStatusLabel = activeItem ? formatBacktestStatus(activeItem) : '--';
  const activeScannerReason = activeItem ? formatScannerReason(activeScanner?.reason, language) : null;
  const activeScannerFailure = activeItem && (activeItem.scoreError || activeScanner?.reason)
    ? sanitizeFailureReason(activeItem.scoreError || activeScanner?.reason || '', '扫描失败')
    : null;
  const activeBacktestSummary = activeItem && hasBacktestMetrics(activeItem)
    ? `${language === 'zh' ? '收益' : 'Return'} ${formatPct(activeBacktest?.totalReturnPct)} · ${language === 'zh' ? '回撤' : 'DD'} ${formatPct(activeBacktest?.maxDrawdownPct)} · Sharpe ${formatRatio(activeBacktest?.sharpe)} · ${language === 'zh' ? '交易' : 'Trades'} ${activeBacktest?.tradeCount ?? '--'}`
    : copy.noEvidence;
  const activeObservationSummary = activeItem ? buildObservationSummary(activeItem, language) : copy.noEvidence;
  const activeRiskNote = activeItem ? buildWatchRiskNote(activeItem, language) : null;
  const activeNextActionLabel = activeItem ? buildNextActionLabel(activeItem, language) : '--';
  const activeContextTags = activeItem
    ? [
        activeItem.themeId ? `${copy.themePrefix}: ${activeItem.themeId}` : null,
        activeItem.universeType ? `${copy.universePrefix}: ${activeItem.universeType}` : null,
      ].filter(Boolean) as string[]
    : [];
  const activeHasEvidence = activeItem
    ? hasScannerEvidence(activeItem) || activeSimulation?.status === 'ready' || hasBacktestEvidence(activeItem)
    : false;
  const runtimeStatusLabel = batchProgress
    ? `${batchProgress.completed}/${batchProgress.total}`
    : isBatchBacktesting
      ? copy.batchBacktesting
      : isBatchScanning
        ? copy.batchScanFilter
        : language === 'zh'
          ? '空闲'
          : 'Idle';
  const runtimeStatusTone = batchProgress
    ? 'info'
    : isBatchBacktesting || isBatchScanning
      ? 'warning'
      : 'neutral';

  return (
    <ConsumerWorkspaceScope data-testid="watchlist-wide-workspace-scope" className="min-h-0 flex-1">
      <ConsumerWorkspacePageShell data-testid="watchlist-page" className="flex-1">
      <div data-layout-zone="HeaderStrip" data-testid="watchlist-header-strip" className="flex min-w-0 flex-col gap-3">
        <DensePageHeader
          eyebrow={language === 'zh' ? '监控队列' : 'Monitoring board'}
          title={copy.title}
          action={(
            <TerminalButton
              type="button"
              variant="secondary"
              className="h-9 px-3 text-xs"
              onClick={() => navigate(scannerPath)}
            >
              <ExternalLink className="h-4 w-4" />
              {copy.openScanner}
            </TerminalButton>
          )}
        />

        <WatchlistConclusionBand
          model={watchlistConclusion}
          trackedCount={summary.total}
          monitoringStateLabel={monitoringStateLabel}
          language={language}
        />

        <DenseStatusStrip
          data-testid="watchlist-status-strip"
          ariaLabel="watchlist summary"
          items={statusItems}
        />

        {notice ? (
          <TerminalNotice className={noticeClassName} role="status">
            {notice.message}
          </TerminalNotice>
        ) : null}

        {error ? (
          <TerminalPanel as="section" dense>
            <ApiErrorAlert error={error} />
          </TerminalPanel>
        ) : null}
      </div>

      <DenseTableShell data-testid="watchlist-watch-board" variant="board">
        <CompactFilterBar
          data-testid="watchlist-compact-filter-bar"
          className="min-h-0 rounded-none border-x-0 border-t-0 px-3 py-2"
          leading={<span className="text-[11px] font-medium uppercase tracking-[0.18em] text-[color:var(--wolfy-text-muted)]">{copy.filters}</span>}
        >
          <div className="flex min-w-0 flex-col gap-2">
            <div
              data-testid="watchlist-filter-grid"
              className="grid min-w-0 grid-cols-2 gap-2 md:flex md:flex-wrap md:items-end"
            >
              <div data-testid="watchlist-primary-filters" className="col-span-2 min-w-0 md:flex-[2_1_20rem]">
                <Input
                  label={copy.search}
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder={copy.searchPlaceholder}
                  containerClassName="min-w-0"
                  trailingAction={<Search className="h-4 w-4 text-white/35" />}
                />
              </div>
              <div className="min-w-0 md:flex-[0_0_9rem]">
                <Select label={copy.market} value={marketFilter} onChange={setMarketFilter} options={marketOptions} className="min-w-0" />
              </div>
              <div className="min-w-0 md:flex-[0_0_10.5rem]">
                <Select
                  label={copy.sort}
                  value={sortKey}
                  onChange={(value) => setSortKey(value as SortKey)}
                  className="min-w-0"
                  options={[
                    { value: 'newest', label: copy.newest },
                    { value: 'scannerScore', label: copy.scannerScore },
                    { value: 'backtestReturn', label: copy.backtestReturn },
                    { value: 'historicalHitRate', label: copy.historicalHitRate },
                    { value: 'recentlyScored', label: copy.recentlyScored },
                    { value: 'recentlyBacktested', label: copy.recentlyBacktested },
                    { value: 'symbol', label: copy.symbol },
                    { value: 'market', label: copy.market },
                  ]}
                />
              </div>
              <div className="min-w-0 md:flex-[0_0_9.5rem]">
                <Select label={copy.source} value={sourceFilter} onChange={setSourceFilter} options={sourceOptions} className="min-w-0" />
              </div>
              <div className="min-w-0">
                <TerminalButton
                  type="button"
                  variant="secondary"
                  className="h-9 w-full px-3 text-xs"
                  aria-expanded={advancedFiltersOpen}
                  aria-controls="watchlist-advanced-filter-grid"
                  onClick={() => setAdvancedFiltersOpen((current) => !current)}
                >
                  {copy.advancedFilters}
                </TerminalButton>
              </div>
            </div>
            <div
              data-testid="watchlist-advanced-filters"
              className="flex min-w-0 flex-col gap-2 border-t border-[color:var(--wolfy-divider)] pt-2"
            >
              <div className="flex min-w-0 items-center justify-between gap-2">
                <div className="flex min-w-0 items-center gap-2">
                  <span className="text-[11px] text-[color:var(--wolfy-text-muted)]">{copy.advancedFilters}</span>
                  <TerminalChip variant="neutral">{advancedFiltersOpen ? copy.enabled : language === 'zh' ? '默认收起' : 'Collapsed'}</TerminalChip>
                </div>
              </div>
              {advancedFiltersOpen ? (
                <div
                  id="watchlist-advanced-filter-grid"
                  data-testid="watchlist-advanced-filter-grid"
                  className="grid min-w-0 grid-cols-1 gap-2 md:grid-cols-2"
                >
                  <Select label={copy.context} value={contextFilter} onChange={setContextFilter} options={contextOptions} className="min-w-0" />
                  <Select
                    label={copy.evidence}
                    value={evidenceFilter}
                    onChange={(value) => setEvidenceFilter(value as EvidenceFilter)}
                    className="min-w-0"
                    options={[
                      { value: 'all', label: copy.all },
                      { value: 'hasScanner', label: copy.hasScanner },
                      { value: 'hasBacktest', label: copy.hasBacktest },
                      { value: 'scannerSelected', label: copy.scannerSelected },
                      { value: 'staleIntelligence', label: copy.staleIntelligence },
                    ]}
                  />
                </div>
              ) : null}
            </div>
          </div>
        </CompactFilterBar>

        <div
          data-testid="watchlist-board-shell"
          className="grid min-w-0 lg:grid-cols-[minmax(0,1fr)_340px]"
        >
          <div data-layout-zone="PrimaryWorkRegion" data-testid="watchlist-primary-work-region" className="min-w-0">
            <ConsoleBoard className="rounded-none border-0 bg-transparent">
              <div className="flex min-w-0 items-center justify-between gap-3 border-b border-[color:var(--wolfy-divider)] px-4 py-3">
                <div className="min-w-0">
                  <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">{copy.tableTitle}</p>
                  <p className="truncate text-xs text-[color:var(--wolfy-text-secondary)]">{copy.tableDescription}</p>
                </div>
                <TerminalChip variant="neutral" className="font-mono">
                  {actionScopeLabel}
                </TerminalChip>
              </div>
              <div
                data-testid="watchlist-list-header"
                className="hidden min-w-0 grid-cols-[minmax(0,1.35fr)_minmax(0,0.95fr)_minmax(0,1.2fr)_auto] gap-4 border-b border-[color:var(--wolfy-divider)] px-4 py-2 text-[11px] uppercase tracking-[0.18em] text-[color:var(--wolfy-text-muted)] lg:grid"
              >
                <span>{language === 'en' ? 'Symbol' : '标的'}</span>
                <span>{language === 'en' ? 'State' : '状态'}</span>
                <span>{language === 'en' ? 'Observation' : '观察'}</span>
                <span className="text-right">{copy.actions}</span>
              </div>
              {isLoading ? (
                <TerminalPanel as="section" dense className="py-8 text-center text-sm text-white/45" role="status">
                  {copy.loading}
                </TerminalPanel>
              ) : filteredItems.length > 0 ? (
                <DenseRows data-testid="watchlist-candidate-list">
                  {filteredItems.map((item) => {
                    const scanner = item.intelligence?.scanner;
                    const strategySimulation = item.intelligence?.strategySimulation;
                    const backtest = item.intelligence?.backtest;
                    const score = getScannerScore(item);
                    const hitRate = strategySimulation?.hitRate;
                    const avgForward = strategySimulation?.avgForwardReturnPct;
                    const batchStatus = batchStatuses[item.symbol];
                    const batchFailure = batchFailures[item.symbol];
                    const scannerFailure = item.scoreError || scanner?.reason
                      ? sanitizeFailureReason(item.scoreError || scanner?.reason || '', '扫描失败')
                      : null;
                    const latestTime = getLatestIntelligenceTime(item);
                    const scannerStatusLabel = formatScannerStatus(item);
                    const backtestStatusLabel = formatBacktestStatus(item, batchFailure);
                    const isActive = activeItem?.id === item.id;
                    const scoreDisclosureState = getScoreDisclosureState(item);
                    const scoreDisclosureStatusLabel = formatScoreDisclosureStatus(scoreDisclosureState, language);
                    const rowRiskNote = buildWatchRiskNote(item, language);
                    const originLabel = formatWatchlistOrigin(item.source, language);
                    const scoreFreshnessVariant = scoreDisclosureChipVariant(scoreDisclosureState);
                    const backtestStatusVariant = backtestStatusLabel === '已回测'
                      ? 'success'
                      : ['回测失败', '行情缺失', '服务暂不可用', '超时'].includes(backtestStatusLabel)
                        ? 'danger'
                        : ['样本不足', '数据缺失'].includes(backtestStatusLabel)
                          ? 'caution'
                          : 'neutral';
                    const batchDisplayStatus = batchStatus
                      ? describeDisplayStatus(
                          batchStatus === 'completed'
                            ? 'success'
                            : batchStatus === 'failed'
                              ? 'failed'
                              : batchStatus === 'running'
                                ? 'info'
                                : batchStatus === 'skipped'
                                  ? 'disabled'
                                  : 'pending',
                          batchStatus === 'running' ? '运行中' : batchStatus === 'completed' ? '完成' : batchStatus === 'failed' ? '失败' : batchStatus === 'skipped' ? '已跳过' : '等待',
                          { language },
                        )
                      : null;
                    const rowObservation = buildObservationSummary(item, language);
                    const rowNextAction = buildNextActionLabel(item, language);
                    const rowStateLine = [
                      `${copy.score} ${formatScore(score)}`,
                      typeof avgForward === 'number' ? `${copy.historyPrefix} ${formatPct(avgForward)}` : null,
                      typeof hitRate === 'number' ? `${copy.hitPrefix} ${Math.round(hitRate * 100)}%` : null,
                    ].filter(Boolean).join(' · ');

                    return (
                      <article
                        key={item.id}
                        data-testid={`watchlist-row-${item.symbol}`}
                        className={`min-w-0 border-b border-[color:var(--wolfy-divider)] px-3 py-3 transition-colors md:px-4 ${isActive ? 'bg-white/[0.045]' : 'bg-transparent hover:bg-white/[0.02]'}`}
                      >
                        <div className="grid min-w-0 gap-3 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,0.95fr)_minmax(0,1.2fr)_auto] lg:items-start lg:gap-4">
                          <div className="flex min-w-0 gap-3">
                            <button
                              type="button"
                              className={`${ROW_SELECTION_BUTTON_CLASS} ${
                                selectedIds.has(item.id)
                                  ? 'border-cyan-300 bg-cyan-300/30 shadow-[0_0_10px_rgba(103,232,249,0.25)]'
                                  : 'border-white/15 bg-white/[0.03] hover:border-white/30'
                              }`}
                              role="checkbox"
                              aria-checked={selectedIds.has(item.id)}
                              aria-label={`${language === 'zh' ? '选择' : 'Select'} ${item.symbol}`}
                              onClick={() => toggleSelected(item)}
                            >
                              <span
                                aria-hidden="true"
                                className={`h-3 w-3 rounded-sm border transition ${
                                  selectedIds.has(item.id)
                                    ? 'border-cyan-100 bg-cyan-100 shadow-[0_0_8px_rgba(103,232,249,0.35)]'
                                    : 'border-white/20 bg-transparent'
                                }`}
                              />
                            </button>
                            <button
                              type="button"
                              aria-pressed={isActive}
                              aria-label={`${language === 'zh' ? '查看详情' : 'View details'} ${item.symbol}`}
                              className={`flex min-w-0 flex-1 flex-col items-start gap-1 rounded-lg border px-3 py-2 text-left transition ${
                                isActive
                                  ? 'border-[color:var(--wolfy-accent)] bg-[var(--wolfy-surface-input)]'
                                  : 'border-transparent bg-transparent hover:border-[color:var(--wolfy-border-subtle)] hover:bg-white/[0.02]'
                              }`}
                              onClick={() => setActiveItemId(item.id)}
                            >
                              <div className="flex min-w-0 flex-wrap items-center gap-2">
                                <span className="font-semibold text-white">{item.symbol}</span>
                                <TerminalChip variant="neutral">{formatMarket(item.market)}</TerminalChip>
                                {isRecentlyAdded(item) ? <TerminalChip variant="info">{copy.recentlyAdded}</TerminalChip> : null}
                              </div>
                              <p className="truncate text-sm text-white/78">{item.name || '--'}</p>
                              <p className="truncate text-[11px] text-white/45">{originLabel}</p>
                            </button>
                          </div>

                          <div className="min-w-0 space-y-2">
                            <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--wolfy-text-muted)]">
                              {language === 'en' ? 'State' : '状态'}
                            </p>
                            <div className="flex min-w-0 flex-wrap items-center gap-1.5">
                              <TerminalChip variant={scoreFreshnessVariant} className="font-mono uppercase tracking-widest">
                                {scoreDisclosureStatusLabel}
                              </TerminalChip>
                              <TerminalChip variant={scannerStatusChipVariant(scannerStatusLabel)}>
                                {scannerStatusLabel}
                              </TerminalChip>
                              <TerminalChip variant={backtestStatusVariant}>{backtestStatusLabel}</TerminalChip>
                              {batchDisplayStatus ? (
                                <TerminalChip variant={terminalChipVariant(batchDisplayStatus.tone)} className="font-mono">
                                  {batchDisplayStatus.label}
                                </TerminalChip>
                              ) : null}
                            </div>
                            <p className="truncate text-xs font-mono text-white/55">{rowStateLine || `${copy.score} ${formatScore(score)}`}</p>
                          </div>

                          <div className="min-w-0 space-y-2">
                            <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--wolfy-text-muted)]">
                              {language === 'en' ? 'Observation' : '观察'}
                            </p>
                            <p className="text-sm leading-6 text-white/72">{rowObservation}</p>
                            <div className="flex min-w-0 flex-wrap items-center gap-2 text-xs">
                              {latestTime ? <span className="font-mono text-white/45">{copy.latestUpdate} {formatDateTime(latestTime, language)}</span> : null}
                              <span className="text-white/55">{language === 'en' ? 'Next' : '下一步'} {rowNextAction}</span>
                            </div>
                            {rowRiskNote ? (
                              <p className="text-xs leading-5 text-white/52" data-testid={`watchlist-row-note-${item.symbol}`}>
                                {rowRiskNote}
                              </p>
                            ) : scannerFailure && scannerStatusLabel === '扫描失败' ? (
                              <p className="text-xs leading-5 text-rose-100/75">{scannerFailure.label}</p>
                            ) : null}
                          </div>

                          <div className="flex min-w-0 flex-wrap items-center gap-2 lg:justify-end">
                            <TerminalButton
                              type="button"
                              variant="compact"
                              onClick={() => void handleAnalyze(item)}
                              disabled={pendingAnalyzeId === item.id}
                            >
                              <Play className="h-3.5 w-3.5" />
                              {pendingAnalyzeId === item.id ? copy.analyzing : copy.analyze}
                            </TerminalButton>
                            <TerminalButton
                              type="button"
                              variant="compact"
                              onClick={() => navigate(buildBacktestPath(item, language))}
                            >
                              <BarChart3 className="h-3.5 w-3.5" />
                              {copy.backtest}
                            </TerminalButton>
                            {backtest?.lastResultId != null ? (
                              <TerminalButton
                                type="button"
                                variant="compact"
                                className="font-mono text-[11px]"
                                onClick={() => navigate(buildLocalizedPath(`/backtest/results/${backtest.lastResultId}`, language))}
                              >
                                {copy.resultPrefix} {backtest.lastResultId}
                              </TerminalButton>
                            ) : null}
                            <TerminalButton
                              type="button"
                              aria-label={`${copy.copySymbol} ${item.symbol}`}
                              title={copiedId === item.id ? copy.copied : copy.copySymbol}
                              variant="compact"
                              className="h-[34px] min-h-[34px] w-[34px] px-0 text-white/55"
                              onClick={() => void handleCopy(item)}
                            >
                              <Copy className="h-3.5 w-3.5" />
                            </TerminalButton>
                            <TerminalButton
                              type="button"
                              aria-label={`${copy.remove} ${item.symbol}`}
                              variant="danger"
                              className="h-[34px] min-h-[34px] w-[34px] px-0"
                              onClick={() => void handleRemove(item)}
                              disabled={pendingRemoveId === item.id}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </TerminalButton>
                          </div>
                        </div>
                      </article>
                    );
                  })}
                </DenseRows>
              ) : (
                <CompactEmptyRow
                  data-testid="watchlist-compact-empty-state"
                  title={copy.emptyTitle}
                  className="rounded-none border-x-0 border-b-0 border-t border-[color:var(--wolfy-divider)] bg-transparent px-4 py-4 min-h-[72px]"
                  action={(
                    <TerminalButton
                      type="button"
                      variant="secondary"
                      className="h-9 px-3 text-xs"
                      onClick={() => navigate(scannerPath)}
                    >
                      <ExternalLink className="h-4 w-4" />
                      {copy.openScanner}
                    </TerminalButton>
                  )}
                >
                  {copy.emptyBody}
                </CompactEmptyRow>
              )}
            </ConsoleBoard>
          </div>

          {filteredItems.length > 0 && activeItem ? (
            <div
              data-layout-zone="ContextRail"
              data-linear-primitive="context-rail"
              data-testid="watchlist-detail-rail"
              className="min-w-0 border-t border-[color:var(--wolfy-divider)] lg:border-l lg:border-t-0"
            >
              <ConsoleContextRail className="rounded-none border-0 bg-[var(--wolfy-surface-rail)] px-4 py-4">
                <section className="min-w-0 pb-4">
                  <div className="flex min-w-0 items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-[11px] text-white/40">{language === 'zh' ? '已选项目' : 'Selected item'}</p>
                      <h2 className="truncate text-base font-semibold text-white">{activeItem.symbol}</h2>
                      <p className="truncate text-xs text-white/58">{activeItem.name || '--'}</p>
                    </div>
                    <TerminalChip variant="neutral">{formatMarket(activeItem.market)}</TerminalChip>
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-1.5">
                    <TerminalChip variant="info" className="font-mono text-cyan-100">
                      {language === 'zh' ? '分数' : 'SCORE'} {formatScore(activeScore)}
                    </TerminalChip>
                    <TerminalChip variant={scoreDisclosureChipVariant(activeScoreDisclosureState)}>
                      {formatScoreDisclosureStatus(activeScoreDisclosureState, language)}
                    </TerminalChip>
                    <TerminalChip variant={activeBacktestStatusLabel === '已回测' ? 'success' : ['回测失败', '行情缺失', '服务暂不可用', '超时'].includes(activeBacktestStatusLabel) ? 'danger' : ['样本不足', '数据缺失'].includes(activeBacktestStatusLabel) ? 'caution' : 'neutral'}>
                      {activeBacktestStatusLabel}
                    </TerminalChip>
                  </div>
                </section>

                <section className="grid min-w-0 gap-3 border-y border-[color:var(--wolfy-divider)] py-4">
                  <div className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-3">
                    <p className="text-[11px] text-white/40">{language === 'zh' ? '当前状态' : 'Current state'}</p>
                    <p className="mt-1 text-sm text-white/78">{formatScoreDisclosureFreshness(activeItem, activeLatestTime, language)}</p>
                  </div>
                  <div className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-3">
                    <p className="text-[11px] text-white/40">{language === 'zh' ? '风险提示' : 'Risk note'}</p>
                    <p className="mt-1 text-sm text-white/78">{activeRiskNote || (language === 'en' ? 'State is stable for observation.' : '当前状态适合继续观察。')}</p>
                  </div>
                  <div className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-3">
                    <p className="text-[11px] text-white/40">{language === 'zh' ? '下一步' : 'Next step'}</p>
                    <p className="mt-1 text-sm text-white/78">{activeNextActionLabel}</p>
                  </div>
                </section>

                <section className="min-w-0 py-4">
                  <div className="mb-3 flex min-w-0 items-center justify-between gap-3">
                    <h3 className="text-sm font-semibold text-white">{language === 'zh' ? '观察摘要' : 'Observation summary'}</h3>
                  </div>
                  <div className="space-y-3">
                    <p className="text-sm leading-6 text-white/72">{activeObservationSummary}</p>
                    <div className="divide-y divide-[color:var(--wolfy-divider)]">
                      {[
                        { label: copy.lastScored, value: formatDateTime(activeItem.lastScoredAt, language) },
                        { label: copy.added, value: formatDateTime(activeItem.createdAt || activeItem.updatedAt, language) },
                        { label: copy.latestUpdate, value: activeLatestTime ? formatDateTime(activeLatestTime, language) : '--' },
                      ].map((row) => (
                        <div key={String(row.label)} className="flex min-w-0 items-start justify-between gap-4 py-2.5 text-[11px]">
                          <span className="truncate text-white/38">{row.label}</span>
                          <span className="min-w-0 text-right text-white/68">{row.value}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </section>

                <section className="min-w-0 py-4">
                  <div className="mb-3 flex min-w-0 items-center justify-between gap-3">
                    <h3 className="text-sm font-semibold text-white">{copy.intelligence}</h3>
                  </div>
                  <div className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-3 text-xs leading-5 text-white/68">
                    {activeBacktestSummary}
                  </div>
                </section>

                <DenseSecondaryDisclosure
                  data-testid="watchlist-data-notes"
                  variant="row"
                  title={language === 'zh' ? '数据备注' : 'Data notes'}
                  summary={language === 'zh' ? '默认收起' : 'Collapsed by default'}
                  className="pt-4"
                >
                  <div className="space-y-3 text-xs leading-5 text-white/62">
                    <p>{formatWatchlistOrigin(activeItem.source, language)}</p>
                    {activeScannerReason ? <p>{activeScannerReason}</p> : null}
                    {!activeHasEvidence ? <p>{copy.sourceUnknownNeedsRefresh}</p> : null}
                    {activeContextTags.length ? (
                      <div className="flex min-w-0 flex-wrap gap-1.5">
                        {activeContextTags.map((tag) => (
                          <TerminalChip key={tag} variant="neutral">{tag}</TerminalChip>
                        ))}
                      </div>
                    ) : null}
                    {activeScannerFailure && activeScannerStatusLabel === '扫描失败' ? <p>{activeScannerFailure.label}</p> : null}
                    {typeof activeSimulation?.avgForwardReturnPct === 'number' || typeof activeSimulation?.hitRate === 'number' ? (
                      <p>
                        {copy.historyPrefix} {formatPct(activeSimulation?.avgForwardReturnPct)} · {copy.hitPrefix} {typeof activeSimulation?.hitRate === 'number' ? `${Math.round(activeSimulation.hitRate * 100)}%` : '--'}
                      </p>
                    ) : null}
                  </div>
                </DenseSecondaryDisclosure>

                <section className="min-w-0 pt-4">
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <TerminalButton
                      type="button"
                      variant="secondary"
                      onClick={() => void handleAnalyze(activeItem)}
                      disabled={pendingAnalyzeId === activeItem.id}
                    >
                      <Play className="h-3.5 w-3.5" />
                      {pendingAnalyzeId === activeItem.id ? copy.analyzing : copy.analyze}
                    </TerminalButton>
                    <TerminalButton
                      type="button"
                      variant="compact"
                      onClick={() => navigate(buildBacktestPath(activeItem, language))}
                    >
                      <BarChart3 className="h-3.5 w-3.5" />
                      {copy.backtest}
                    </TerminalButton>
                    {activeBacktest?.lastResultId != null ? (
                      <TerminalButton
                        type="button"
                        variant="compact"
                        onClick={() => navigate(buildLocalizedPath(`/backtest/results/${activeBacktest.lastResultId}`, language))}
                      >
                        {copy.resultPrefix} {activeBacktest.lastResultId}
                      </TerminalButton>
                    ) : null}
                    <TerminalButton
                      type="button"
                      aria-label={`${copy.copySymbol} ${activeItem.symbol}`}
                      variant="compact"
                      onClick={() => void handleCopy(activeItem)}
                    >
                      <Copy className="h-3.5 w-3.5" />
                      {copy.copySymbol}
                    </TerminalButton>
                    <TerminalButton
                      type="button"
                      variant="danger"
                      onClick={() => void handleRemove(activeItem)}
                      disabled={pendingRemoveId === activeItem.id}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      {copy.remove}
                    </TerminalButton>
                  </div>
                </section>
              </ConsoleContextRail>
            </div>
          ) : null}
        </div>

        <div data-layout-zone="SecondaryDeck" data-testid="watchlist-secondary-deck" className="min-w-0 border-t border-[color:var(--wolfy-divider)]">
          <DenseCommandBar
            data-testid="watchlist-command-bar"
            className="border-t-0"
            heading={copy.batchActions}
            summary={<span data-testid="watchlist-action-scope">{copy.runtimeStatus} · {actionScopeLabel}</span>}
            notice={actionItems.length === 0 ? <TerminalChip variant="caution">{copy.noMatchedSymbols}</TerminalChip> : null}
            progress={batchProgress ? (
              <p data-testid="watchlist-batch-progress" className="text-xs text-white/55">
                {batchProgress.completed} / {batchProgress.total}
                {batchProgress.currentSymbol ? ` · ${batchProgress.currentSymbol}` : ''}
                {' · '}
                {language === 'zh' ? '成功' : 'Success'} {batchProgress.succeeded}
                {' · '}
                {language === 'zh' ? '失败' : 'Failed'} {batchProgress.failed}
              </p>
            ) : null}
            actions={(
              <>
              <TerminalButton
                type="button"
                variant="compact"
                onClick={() => void handleRefreshScores(actionItems)}
                disabled={isActionDisabled}
              >
                <RefreshCw className={`h-3.5 w-3.5 ${isBatchScanning ? 'animate-spin' : ''}`} />
                {copy.batchScanFilter}
              </TerminalButton>
              <TerminalButton
                type="button"
                variant="secondary"
                onClick={() => void handleBatchBacktestCurrentFilter()}
                disabled={isActionDisabled}
              >
                <BarChart3 className="h-3.5 w-3.5" />
                {isBatchBacktesting ? copy.batchBacktesting : copy.batchBacktestFilter}
              </TerminalButton>
              <TerminalButton
                type="button"
                variant="compact"
                aria-pressed={useSelectedScope && selectedItems.length > 0}
                onClick={() => setUseSelectedScope((current) => selectedItems.length > 0 ? !current : current)}
                disabled={selectedItems.length === 0}
              >
                <CheckSquare className="h-3.5 w-3.5" />
                {copy.selectedOnly}
              </TerminalButton>
              <TerminalButton
                type="button"
                variant="compact"
                onClick={() => {
                  setSelectedIds(new Set());
                  setUseSelectedScope(false);
                }}
                disabled={selectedIds.size === 0}
              >
                {copy.clearSelection}
              </TerminalButton>
              <TerminalButton type="button" variant="compact" onClick={() => void handleRefreshIntelligence()}>
                <RefreshCw className="h-3.5 w-3.5" />
                {copy.refreshIntelligence}
              </TerminalButton>
              <TerminalButton
                type="button"
                variant="compact"
                className="disabled:cursor-wait"
                onClick={() => void handleRefreshScores()}
                disabled={isRefreshingScores}
              >
                <RefreshCw className={`h-3.5 w-3.5 ${isRefreshingScores ? 'animate-spin' : ''}`} />
                {isRefreshingScores ? copy.refreshingScores : copy.refreshScores}
              </TerminalButton>
              </>
            )}
          />
          <div
            data-testid="watchlist-runtime-status"
            className="flex min-w-0 flex-wrap items-center justify-between gap-2 border-t border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] px-3 py-2"
          >
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <span className="text-[11px] text-[color:var(--wolfy-text-muted)]">{copy.autoRefresh}</span>
              <TerminalChip variant={terminalChipVariant(autoRefreshStatus.tone)} className="font-mono">
                {refreshStatus ? autoRefreshStatus.label : '--'}
              </TerminalChip>
              <span className="truncate font-mono text-[11px] text-white/45">
                US {refreshStatus?.usTime || '08:45'} / CN {refreshStatus?.cnTime || '09:00'} / HK {refreshStatus?.hkTime || '09:00'}
              </span>
            </div>
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <span className="text-[11px] text-[color:var(--wolfy-text-muted)]">{copy.runtimeStatus}</span>
              <TerminalChip variant={terminalChipVariant(runtimeStatusTone)} className="font-mono">
                {runtimeStatusLabel}
              </TerminalChip>
            </div>
          </div>
        </div>
      </DenseTableShell>
      </ConsumerWorkspacePageShell>
    </ConsumerWorkspaceScope>
  );
};

export default WatchlistPage;
