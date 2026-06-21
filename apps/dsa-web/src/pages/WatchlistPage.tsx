import { useCallback, useEffect, useMemo, useState, type ComponentProps } from 'react';
import {
  BarChart3,
  CheckSquare,
  Copy,
  Play,
  RefreshCw,
  Search,
  Trash2,
} from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { analysisApi, DuplicateTaskError } from '../api/analysis';
import { backtestApi } from '../api/backtest';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { watchlistApi } from '../api/watchlist';
import { ConsumerProtectedFrame, ConsumerWorkspacePageShell, ConsumerWorkspaceScope } from '../components/layout/ConsumerWorkspaceShell';
import { ApiErrorAlert } from '../components/common/ApiErrorAlert';
import { ConsumerOnboardingCtaPanel } from '../components/common/ConsumerOnboardingCtaPanel';
import { Input } from '../components/common/Input';
import { Select } from '../components/common/Select';
import {
  ConsoleBoard,
  ConsoleContextRail,
  CompactFilterBar,
  DenseRows,
} from '../components/linear/LinearPrimitives';
import {
  CompactEmptyRow,
  DenseCommandBar,
  DensePageHeader,
  DenseSecondaryDisclosure,
  DenseStatusStrip,
  DenseTableShell,
} from '../components/terminal/DenseWorkbenchPrimitives';
import {
  TerminalButton,
  TerminalChip,
  TerminalNotice,
  TerminalPanel,
} from '../components/terminal/TerminalPrimitives';
import ResearchWorkspaceFlowPanel from '../components/research/ResearchWorkspaceFlowPanel';
import UserAlertsRailPanel from '../components/user-alerts/UserAlertsRailPanel';
import LeveragedEtfMapper from '../components/watchlist/LeveragedEtfMapper';
import WatchlistResearchQueuePanel from '../components/watchlist/WatchlistResearchQueuePanel';
import { useI18n } from '../contexts/UiLanguageContext';
import { useProductSurface } from '../hooks/useProductSurface';
import type { InvestorSignalContract } from '../types/scanner';
import type { WatchlistCatalystExposure, WatchlistItem, WatchlistResearchPriorityQueueItem, WatchlistScannerLineageV1 } from '../types/watchlist';
import type { RuleBacktestRunResponse } from '../types/backtest';
import { describeBooleanEnabled, describeDisplayStatus, type DisplayStatusTone } from '../utils/displayStatus';
import { buildLocalizedPath } from '../utils/localeRouting';
import {
  buildResearchWorkspacePath,
  normalizeResearchWorkspaceSource,
  parseResearchWorkspaceSearch,
} from '../utils/researchWorkspaceRoute';
import { getWatchlistRowResearchPacketConsumerCopy, type WatchlistRowResearchPacketConsumerCopy } from '../utils/researchQueueConsumerCopy';
import { sanitizeUserFacingDataIssue } from '../utils/userFacingDataIssues';

type SortKey = 'newest' | 'scannerScore' | 'backtestReturn' | 'historicalHitRate' | 'recentlyScored' | 'recentlyBacktested' | 'symbol' | 'market';
type EvidenceFilter = 'all' | 'hasScanner' | 'hasBacktest' | 'scannerSelected' | 'staleIntelligence';
type BatchStatus = 'requested' | 'running' | 'completed' | 'failed' | 'skipped';
type Notice = { tone: 'success' | 'warning' | 'danger'; message: string } | null;
type FailureReason = '数据不足' | '行情缺失' | '服务暂不可用' | '回测失败' | '扫描失败' | '超时' | '未知错误';
type BatchFailure = { label: FailureReason; detail?: string };
type WatchlistTrustState = 'fresh' | 'stale' | 'unknown';
type WatchlistScoreDisclosureState = 'fresh' | 'stale' | 'cached' | 'blocked' | 'limitedConfidence' | 'unknown' | 'failed';
type WatchlistScannerLineageCue = {
  label: string;
  detail: string;
} | null;
type WatchlistScannerLineageView = {
  summary: string;
  snapshotLabel: string;
  stateLabel: string;
  freshnessLabel: string;
  reason: string;
  nextStep: string;
  metadata: string[];
};
type WatchlistWorkflowKey = 'discovered' | 'pendingValidation' | 'observing' | 'alertRecorded' | 'needsRefresh';
type WatchlistWorkflowStep = {
  key: WatchlistWorkflowKey;
  label: string;
  variant: ComponentProps<typeof TerminalChip>['variant'];
};
type WatchlistInvestorSignalView = {
  confidenceLabel: string | null;
  freshnessLabel: string | null;
  stateLabel: string | null;
  explanation: string | null;
  reasonCodes: string[];
  contradictionCodes: string[];
};
type WatchlistCatalystExposureViewItem = {
  id: string;
  title: string;
  summary: string;
  statusLabels: string[];
  reasonLabels: string[];
  metadata: string[];
};
type WatchlistCatalystExposureView = {
  items: WatchlistCatalystExposureViewItem[];
  hiddenCount: number;
};
type WatchlistRowStatus = {
  priceLabel: string;
  updateLabel: string;
  researchStatusLabel: string;
  researchStatusVariant: ComponentProps<typeof TerminalChip>['variant'];
  missingSummary: string | null;
};
type WatchlistConclusionModel = {
  title: string;
  detail: string;
  freshCount: number;
  staleCount: number;
  unknownCount: number;
  limitedConfidenceCount: number;
  tone: 'success' | 'caution' | 'neutral';
};
type WatchlistEmptyPreviewItem = {
  label: string;
  value: string;
  detail: string;
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

function parseManualResearchSymbol(value: string): string {
  const token = normalizeText(value).split(/[\s,，;；]+/u)[0] || '';
  return token.toUpperCase().replace(/[^A-Z0-9._-]/g, '').slice(0, 24);
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

function buildWatchlistIdentityLabel(item: WatchlistItem, language: 'zh' | 'en'): string {
  const name = normalizeText(item.rowResearchPacket?.identity?.name || item.name);
  if (name) return name;
  const symbol = normalizeText(item.symbol).toUpperCase();
  const market = formatMarket(item.market);
  if (symbol && market !== '--') return `${market} ${symbol}`;
  if (symbol) return language === 'en' ? `Saved symbol ${symbol}` : `观察标的 ${symbol}`;
  return language === 'en' ? 'Saved symbol' : '观察标的';
}

function formatWatchlistOrigin(value?: string | null, language: 'zh' | 'en' = 'zh'): string {
  const token = normalizeToken(value);
  if (token === 'scanner' || token === 'scanner_run') return language === 'en' ? 'Research candidate' : '研究候选';
  if (token === 'portfolio') return language === 'en' ? 'Portfolio watch' : '组合观察';
  if (token === 'manual') return language === 'en' ? 'Manual add' : '手动加入';
  if (token === 'imported' || token === 'import') return language === 'en' ? 'Imported' : '批量导入';
  return language === 'en' ? 'Watch item' : '观察标的';
}

const WATCHLIST_DATE_TIME_FORMATTERS = {
  en: new Intl.DateTimeFormat('en-US', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }),
  zh: new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }),
} as const;

function formatDateTime(value?: string | null, language: 'zh' | 'en' = 'zh'): string {
  if (!value) return '--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return WATCHLIST_DATE_TIME_FORMATTERS[language].format(date);
}

function hasInternalConsumerCopy(value?: string | null): boolean {
  const text = normalizeText(value).toLowerCase();
  if (!text) return false;
  return /sourceauthorityallowed|scorecontributionallowed|reasonfamilies|reasoncode|source_confidence|score_blocked|raw diagnostics?|json|debug|provider|proxy|fallback|cache\/status|cache|runtime|source ?tier|source ?authority|scannerrunid|scanner_run_id|scanner_run|source_freshness|observationonly|synthetic_fixture|official_macro_cache_status|stored_news_catalyst_proxy|exposure/.test(text);
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

function formatPriceValue(value: number, market?: string | null): string {
  const abs = Math.abs(value);
  const decimals = abs >= 1000 ? 0 : abs >= 100 ? 1 : 2;
  const formatted = new Intl.NumberFormat('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
  const normalizedMarket = normalizeMarket(market);
  if (normalizedMarket === 'US') return `$${formatted}`;
  if (normalizedMarket === 'HK') return `HK$${formatted}`;
  if (normalizedMarket === 'CN') return `¥${formatted}`;
  return formatted;
}

function readNumericField(source: unknown, keys: string[]): number | null {
  if (!source || typeof source !== 'object') return null;
  const record = source as Record<string, unknown>;
  for (const key of keys) {
    const value = record[key];
    if (typeof value === 'number' && Number.isFinite(value)) return value;
    if (typeof value === 'string') {
      const parsed = Number(value.replace(/,/g, '').trim());
      if (Number.isFinite(parsed)) return parsed;
    }
  }
  return null;
}

function getWatchlistPriceValue(item: WatchlistItem): number | null {
  const priceKeys = ['price', 'lastPrice', 'latestPrice', 'currentPrice', 'close', 'lastClose'];
  const direct = readNumericField(item, priceKeys);
  if (direct !== null) return direct;
  const packetQuote = item.rowResearchPacket?.quote;
  const packetPrice = readNumericField(packetQuote, priceKeys);
  if (packetPrice !== null) return packetPrice;
  const record = item as unknown as Record<string, unknown>;
  return readNumericField(record.quote, priceKeys)
    ?? readNumericField(record.marketData, priceKeys)
    ?? readNumericField(record.intelligence, priceKeys);
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
    item.rowResearchPacket?.quote?.asOf,
    item.rowResearchPacket?.scannerLineage?.lastScoredAt,
    item.intelligence?.backtest?.testedAt,
    item.intelligence?.scanner?.lastScannedAt,
    item.lastScoredAt,
    item.updatedAt,
  ].filter(Boolean) as string[];
  return values.reduce<string | null>((latest, value) => (
    !latest || getTime(value) > getTime(latest) ? value : latest
  ), null);
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
  return token.includes('fallback')
    || token.includes('proxy')
    || token.includes('source_confidence')
    || token.includes('score_blocked')
    || token.includes('sourceauthorityallowed=false')
    || token.includes('scorecontributionallowed=false')
    || token.includes('observationonly')
    || token.includes('authority_missing')
    || token.includes('score_rights_missing')
    || token.includes('unavailable')
    || token.includes('synthetic');
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

function hasScoreStatusContextAuthorityLimit(item: WatchlistItem): boolean {
  const context = item.scoreStatusContext;
  if (!context) return true;
  return context.sourceFreshnessImplied === false
    || context.sourceAuthorityImplied === false
    || normalizeToken(context.freshMeans) === 'persisted_scanner_score_refreshed';
}

function getScoreDisclosureState(item: WatchlistItem): WatchlistScoreDisclosureState {
  const status = normalizeToken(item.scoreStatus);
  if (['data_failed', 'provider_down', 'provider_error', 'failed', 'error', 'critical'].includes(status)) {
    return 'failed';
  }
  if (['blocked', 'score_blocked', 'paused', 'insufficient', 'insufficient_history', 'unavailable'].includes(status)) {
    return 'blocked';
  }
  if (['stale', 'partial'].includes(status)) return 'stale';
  if (['cached', 'cache', 'stored', 'snapshot'].includes(status)) return 'cached';
  if (hasLimitedConfidenceScoreContext(item)) return 'limitedConfidence';
  if (status === 'fresh') return 'fresh';
  return 'unknown';
}

function formatScoreDisclosureFreshness(item: WatchlistItem, value: string | null | undefined, language: 'zh' | 'en'): string {
  const state = getScoreDisclosureState(item);
  if (state === 'fresh') return language === 'en' ? 'Score recently refreshed' : '评分最近刷新';
  if (state === 'cached') return language === 'en' ? 'Saved score snapshot' : '已保存评分';
  if (state === 'blocked') return language === 'en' ? 'Observation only' : '仅作观察';
  if (state === 'stale' || state === 'limitedConfidence') return language === 'en' ? 'Recent available' : '最近可用';
  if (state === 'unknown') return language === 'en' ? 'Updating' : '更新中';
  return formatFreshness(value);
}

function formatScoreDisclosureStatus(state: WatchlistScoreDisclosureState, language: 'zh' | 'en'): string {
  if (language === 'en') {
    if (state === 'fresh') return 'Score refreshed';
    if (state === 'cached') return 'Saved score';
    if (state === 'blocked') return 'Observation only';
    if (state === 'stale' || state === 'limitedConfidence') return 'Limited confidence';
    if (state === 'failed') return 'Scan failed';
    return 'Updating';
  }
  if (state === 'fresh') return '评分已刷新';
  if (state === 'cached') return '已保存评分';
  if (state === 'blocked') return '仅作观察';
  if (state === 'stale' || state === 'limitedConfidence') return '置信度较低';
  if (state === 'failed') return '扫描失败';
  return '数据更新中';
}

function scoreDisclosureChipVariant(state: WatchlistScoreDisclosureState): React.ComponentProps<typeof TerminalChip>['variant'] {
  if (state === 'fresh') return 'success';
  if (state === 'failed') return 'danger';
  if (state === 'stale' || state === 'cached' || state === 'blocked' || state === 'limitedConfidence' || state === 'unknown') return 'caution';
  return 'neutral';
}

function formatScoreDisclosureNotice(item: WatchlistItem, state: WatchlistScoreDisclosureState, language: 'zh' | 'en'): string | null {
  if (state === 'fresh' && hasScoreStatusContextAuthorityLimit(item)) {
    return language === 'en'
      ? 'Score was recently refreshed; this does not prove source freshness or authority.'
      : '评分最近刷新；不代表来源实时或权威。';
  }
  if (state === 'stale') {
    return language === 'en'
      ? 'Using the most recent available data.'
      : '已使用最近一次可用数据。';
  }
  if (state === 'cached') {
    return language === 'en'
      ? 'Using a saved score snapshot; source freshness is not confirmed.'
      : '已使用已保存评分；来源实时性未确认。';
  }
  if (state === 'blocked') {
    return language === 'en'
      ? 'Score context is limited; keep this item in observation mode.'
      : '当前评分依据有限，先保持观察。';
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
  if (scoreDisclosureState === 'blocked') return '仅作观察';
  if (scoreDisclosureState === 'stale' || scoreDisclosureState === 'limitedConfidence') return '置信度较低';
  if (scoreDisclosureState === 'unknown') return hasScannerEvidence(item) ? '数据更新中' : '未扫描';
  if (['selected', 'verified', 'ready', 'fresh'].includes(status)) return '已验证';
  if (['preview', 'candidate', 'passed'].includes(status)) return '通过筛选';
  if (['rejected', 'not_selected', 'failed_filter'].includes(status)) return '未通过';
  if (simulationStatus === 'insufficient_history' || status === 'insufficient_history') return '数据不足';
  if (!hasScannerEvidence(item)) return '未扫描';
  return '通过筛选';
}

function getWorkflowLabel(key: WatchlistWorkflowKey, language: 'zh' | 'en'): string {
  if (language === 'en') {
    if (key === 'discovered') return 'Discovered';
    if (key === 'pendingValidation') return 'Pending validation';
    if (key === 'observing') return 'Observing';
    if (key === 'alertRecorded') return 'Alert recorded';
    return 'Needs refresh';
  }
  if (key === 'discovered') return '已发现';
  if (key === 'pendingValidation') return '待验证';
  if (key === 'observing') return '观察中';
  if (key === 'alertRecorded') return '提醒记录';
  return '需刷新';
}

function hasAlertRecordedCue(item: WatchlistItem): boolean {
  const note = normalizeText(item.notes).toLowerCase();
  return /\b(alert recorded|in-app alert|price alert|watchlist_price_threshold)\b|站内提醒|提醒记录|价格提醒|预警/.test(note);
}

function buildWatchlistWorkflowSteps(item: WatchlistItem, language: 'zh' | 'en'): WatchlistWorkflowStep[] {
  const steps: WatchlistWorkflowStep[] = [];
  const source = normalizeToken(item.source);
  const scoreState = getScoreDisclosureState(item);
  const hasScanner = hasScannerEvidence(item);
  const hasBacktest = hasBacktestEvidence(item);
  const discovered = source === 'scanner'
    || source === 'scanner_run'
    || Boolean(item.scannerRunId || item.scannerRank || getScannerScore(item) !== null);
  const needsRefresh = scoreState === 'failed'
    || scoreState === 'unknown'
    || isStaleIntelligence(item)
    || (!hasScanner && !hasBacktest);
  const pendingValidation = needsRefresh
    || scoreState === 'blocked'
    || scoreState === 'limitedConfidence'
    || !hasBacktest;
  const observing = hasScanner && !needsRefresh;
  const alertRecorded = hasAlertRecordedCue(item);

  if (discovered) {
    steps.push({ key: 'discovered', label: getWorkflowLabel('discovered', language), variant: 'neutral' });
  }
  if (pendingValidation) {
    steps.push({ key: 'pendingValidation', label: getWorkflowLabel('pendingValidation', language), variant: 'caution' });
  }
  if (observing) {
    steps.push({ key: 'observing', label: getWorkflowLabel('observing', language), variant: 'info' });
  }
  if (alertRecorded) {
    steps.push({ key: 'alertRecorded', label: getWorkflowLabel('alertRecorded', language), variant: 'neutral' });
  }
  if (needsRefresh) {
    steps.push({ key: 'needsRefresh', label: getWorkflowLabel('needsRefresh', language), variant: 'caution' });
  }

  return steps.length ? steps : [{ key: 'pendingValidation', label: getWorkflowLabel('pendingValidation', language), variant: 'caution' }];
}

function formatScannerReason(reason?: string | null, language: 'zh' | 'en' = 'zh'): string | null {
  const raw = String(reason || '').trim();
  if (!raw) return null;
  const normalized = raw.toLowerCase();
  if (/latest scanner score/.test(normalized)) {
    return language === 'en' ? 'Latest research score.' : '最新研究评分。';
  }
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

function formatLineageConsumerText(value: string | null | undefined, language: 'zh' | 'en', fallback: string): string {
  const safe = formatScannerReason(value, language);
  return safe || fallback;
}

function formatLineageDataState(lineage: WatchlistScannerLineageV1, language: 'zh' | 'en'): string {
  const state = normalizeToken(lineage.dataState);
  if (lineage.observationOnly || !lineage.scoreGradeAllowed || state === 'observation_only') {
    return language === 'en' ? 'Observation only' : '仅作观察';
  }
  if (state === 'available') return language === 'en' ? 'Ready to observe' : '可继续观察';
  if (state === 'insufficient') return language === 'en' ? 'Insufficient' : '数据不足';
  if (state === 'updating') return language === 'en' ? 'Updating' : '数据更新中';
  if (state === 'unavailable') return language === 'en' ? 'Unavailable' : '暂不可用';
  return language === 'en' ? 'Limited confidence' : '置信度较低';
}

function formatLineageFreshness(lineage: WatchlistScannerLineageV1, language: 'zh' | 'en'): string {
  if (language === 'zh') {
    const label = formatScannerReason(lineage.freshnessLabel, language);
    if (label) return label;
  }
  const state = normalizeToken(lineage.dataState);
  if (state === 'available') return language === 'en' ? 'Updated' : '已更新';
  if (state === 'updating') return language === 'en' ? 'Refreshing' : '数据更新中';
  if (state === 'unavailable') return language === 'en' ? 'Unavailable' : '暂不可用';
  if (state === 'insufficient') return language === 'en' ? 'Insufficient' : '数据不足';
  return language === 'en' ? 'Recent available' : '最近可用';
}

function formatLineageSnapshotLabel(lineage: WatchlistScannerLineageV1, language: 'zh' | 'en'): string {
  if (lineage.scoreSnapshotKind === 'post_add_refresh') {
    return language === 'en' ? 'Updated after save' : '保存后更新';
  }
  return language === 'en' ? 'Saved observation' : '已保存观察';
}

function buildScannerLineageView(
  lineage?: WatchlistScannerLineageV1 | null,
  language: 'zh' | 'en' = 'zh',
): WatchlistScannerLineageView | null {
  if (!lineage || lineage.contractVersion !== 'scanner_watchlist_lineage_v1' || normalizeToken(lineage.source) !== 'scanner') {
    return null;
  }
  const stateLabel = formatLineageDataState(lineage, language);
  const freshnessLabel = formatLineageFreshness(lineage, language);
  const snapshotLabel = formatLineageSnapshotLabel(lineage, language);
  const reason = formatLineageConsumerText(
    lineage.researchReason,
    language,
    language === 'en' ? 'Research observation.' : '研究观察',
  );
  const nextStep = formatLineageConsumerText(
    lineage.researchNextStep,
    language,
    language === 'en' ? 'Keep observing after more evidence.' : '补充证据后继续观察。',
  );
  const scoreLine = [
    typeof lineage.rankAtScan === 'number' ? `${language === 'en' ? 'Candidate order' : '候选序位'} #${lineage.rankAtScan}` : null,
    typeof lineage.scoreAtScan === 'number' ? `${language === 'en' ? 'Research score' : '研究评分'} ${formatScore(lineage.scoreAtScan)}` : null,
  ].filter(Boolean).join(' · ');
  const metadata = [
    scoreLine || null,
    lineage.runProfile ? (language === 'en' ? 'Research window recorded' : '研究窗口已记录') : null,
    lineage.runCompletedAt ? `${language === 'en' ? 'Research updated' : '研究更新'} ${formatDateTime(lineage.runCompletedAt, language)}` : null,
    lineage.watchlistAddedAt ? `${language === 'en' ? 'Saved' : '加入观察'} ${formatDateTime(lineage.watchlistAddedAt, language)}` : null,
    lineage.themeId ? (language === 'en' ? 'Theme context recorded' : '主题线索已记录') : null,
    lineage.universeType ? (language === 'en' ? 'Candidate scope recorded' : '候选范围已记录') : null,
  ].filter(Boolean) as string[];

  return {
    summary: `${language === 'en' ? 'Research workflow' : '研究流程记录'} · ${freshnessLabel} · ${stateLabel}`,
    snapshotLabel,
    stateLabel,
    freshnessLabel,
    reason,
    nextStep,
    metadata,
  };
}

function normalizeToken(value?: string | null): string {
  return normalizeText(value).toLowerCase();
}

const INVESTOR_SIGNAL_REASON_LABELS: Record<string, { zh: string; en: string }> = {
  fallback_source: { zh: '证据较弱', en: 'Limited evidence' },
  source_authority_missing: { zh: '证据仍待确认', en: 'Evidence still needs confirmation' },
  source_authority_router_rejected: { zh: '证据仍待确认', en: 'Evidence still needs confirmation' },
  score_rights_missing: { zh: '评分依据不足', en: 'Scoring evidence is limited' },
  score_contribution_not_allowed: { zh: '评分依据不足', en: 'Scoring evidence is limited' },
  observation_only: { zh: '仅供观察', en: 'Observation only' },
  observation_only_discount: { zh: '仅供观察', en: 'Observation only' },
  freshness_discount: { zh: '时效较弱', en: 'Freshness is limited' },
  source_tier_discount: { zh: '证据较弱', en: 'Limited evidence' },
  provider_unavailable: { zh: '部分数据暂不可用', en: 'Some data is temporarily unavailable' },
  partial_coverage: { zh: '覆盖不完整', en: 'Coverage is partial' },
  blocked: { zh: '暂不判断', en: 'Not enough evidence to judge' },
  mixed: { zh: '信号分化', en: 'Signals are mixed' },
};

const INVESTOR_SIGNAL_CONTRADICTION_LABELS: Record<string, { zh: string; en: string }> = {
  theme_rotation_mismatch: { zh: '主题轮动暂未同向', en: 'Theme rotation is still uneven' },
  capital_flow_signal_mismatch: { zh: '资金流向暂未同向', en: 'Capital-flow signals are still mixed' },
  market_regime_signal_mismatch: { zh: '市场环境暂未同向', en: 'Market-regime signals are still mixed' },
  theme_flow_state_signal_mismatch: { zh: '主题强弱暂未同向', en: 'Theme-flow signals are still mixed' },
  btc_not_confirming_growth_absorption: { zh: 'BTC 未确认当前吸纳', en: 'BTC is not confirming current absorption' },
  rates_not_easing_broadly: { zh: '利率线索尚未同步转松', en: 'Rates are not easing broadly yet' },
  gold_not_confirming_growth_absorption: { zh: '黄金未确认当前吸纳', en: 'Gold is not confirming current absorption' },
  cross_asset_rotation_split: { zh: '跨资产轮动暂未同向', en: 'Cross-asset rotation is still split' },
  mixed_signal_inputs: { zh: '多组线索暂未同向', en: 'Signals are still mixed' },
};

const INVESTOR_SIGNAL_FRESHNESS_LABELS: Record<string, { zh: string; en: string }> = {
  live: { zh: '已更新', en: 'Updated' },
  delayed: { zh: '更新中', en: 'Refreshing' },
  cached: { zh: '最近可用', en: 'Recent available' },
  stale: { zh: '较旧', en: 'Older context' },
  fallback: { zh: '最近可用', en: 'Recent available' },
  mock: { zh: '数据待确认', en: 'Context pending' },
  error: { zh: '暂不可用', en: 'Unavailable' },
};

const CATALYST_EXPOSURE_CATEGORY_LABELS: Record<string, { zh: string; en: string }> = {
  earnings_fundamental_snapshot: { zh: '基本面线索', en: 'Fundamental context' },
  stored_news_catalyst_proxy: { zh: '已保存新闻线索', en: 'Saved news context' },
  official_macro_cache_status: { zh: '宏观背景线索', en: 'Macro context' },
};

const CATALYST_EXPOSURE_STATUS_LABELS: Record<string, { zh: string; en: string }> = {
  delayed: { zh: '更新延迟', en: 'Delayed context' },
  proxy: { zh: '线索待确认', en: 'Context only' },
  stale: { zh: '较旧线索', en: 'Older context' },
  unverified: { zh: '待确认', en: 'Unconfirmed' },
};

const CATALYST_EXPOSURE_REASON_LABELS: Record<string, { zh: string; en: string }> = {
  observation_only: { zh: '仅供观察', en: 'Observation only' },
  delayed_evidence: { zh: '更新延迟', en: 'Delayed context' },
  stale_evidence: { zh: '较旧线索', en: 'Older context' },
  proxy_evidence_not_authoritative: { zh: '仅作线索', en: 'Context only' },
  not_earnings_calendar: { zh: '日程仍待确认', en: 'Calendar context unconfirmed' },
  fundamental_snapshot_present: { zh: '基本面线索已记录', en: 'Fundamental context saved' },
  official_macro_cache_status_present: { zh: '宏观线索已记录', en: 'Macro context saved' },
  stored_news_catalyst_proxy: { zh: '新闻线索已记录', en: 'News context saved' },
};

function formatInvestorSignalCode(code: string, language: 'zh' | 'en'): string {
  const normalized = normalizeToken(code);
  if (!normalized) return '';
  const label = INVESTOR_SIGNAL_REASON_LABELS[normalized];
  if (label) return label[language];
  return language === 'zh' ? '观察条件待确认' : 'Observation pending';
}

function formatInvestorSignalReason(code: string, language: 'zh' | 'en'): string {
  const normalized = normalizeToken(code);
  if (!normalized) return '';
  const label = INVESTOR_SIGNAL_REASON_LABELS[normalized];
  if (label) return label[language];
  return language === 'zh' ? '观察条件待确认' : 'Observation pending';
}

function formatInvestorSignalContradiction(code: string, language: 'zh' | 'en'): string {
  const normalized = normalizeToken(code);
  if (!normalized) return '';
  const labels = INVESTOR_SIGNAL_CONTRADICTION_LABELS[normalized];
  if (labels) return labels[language];
  return language === 'zh' ? '信号仍有分歧' : 'Signals remain mixed';
}

function formatInvestorSignalFreshness(freshness?: string | null, language: 'zh' | 'en' = 'zh'): string | null {
  const normalized = normalizeToken(freshness);
  if (!normalized) return null;
  const labels = INVESTOR_SIGNAL_FRESHNESS_LABELS[normalized];
  if (labels) return labels[language];
  return language === 'zh' ? '最近可用' : 'Recent available';
}

function formatInvestorSignalConfidence(signal?: InvestorSignalContract | null, language: 'zh' | 'en' = 'zh'): string | null {
  if (!signal) return null;
  if (signal.confidenceText) return signal.confidenceText;
  if (signal.confidenceLabel) return formatInvestorSignalCode(signal.confidenceLabel, language);
  if (typeof signal.confidence === 'string') return formatInvestorSignalCode(signal.confidence, language);
  if (typeof signal.confidence === 'number' && Number.isFinite(signal.confidence)) {
    return `${Math.round(signal.confidence * 100)}%`;
  }
  return null;
}

function formatInvestorSignalState(signal?: InvestorSignalContract | null, language: 'zh' | 'en' = 'zh'): string | null {
  if (!signal) return null;
  return signal.marketRegimeLabel
    || signal.capitalFlowLabel
    || signal.themeFlowLabel
    || (signal.marketRegime ? formatInvestorSignalCode(signal.marketRegime, language) : null)
    || (signal.capitalFlowRegime ? formatInvestorSignalCode(signal.capitalFlowRegime, language) : null)
    || (signal.themeFlowState ? formatInvestorSignalCode(signal.themeFlowState, language) : null);
}

function buildWatchlistInvestorSignalView(
  signal?: InvestorSignalContract | null,
  language: 'zh' | 'en' = 'zh',
): WatchlistInvestorSignalView | null {
  if (!signal) return null;
  const confidenceLabel = formatInvestorSignalConfidence(signal, language);
  const freshnessLabel = formatInvestorSignalFreshness(signal.freshness, language);
  const stateLabel = formatInvestorSignalState(signal, language);
  const explanation = normalizeText(signal.explanation);
  const reasonCodes = (signal.reasonCodes || [])
    .flatMap((code) => {
      const label = formatInvestorSignalReason(code, language);
      return label ? [label] : [];
    });
  const contradictionCodes = (signal.contradictionCodes || [])
    .flatMap((code) => {
      const label = formatInvestorSignalContradiction(code, language);
      return label ? [label] : [];
    });
  if (!confidenceLabel && !freshnessLabel && !stateLabel && !explanation && reasonCodes.length === 0 && contradictionCodes.length === 0) {
    return null;
  }
  return {
    confidenceLabel,
    freshnessLabel,
    stateLabel,
    explanation: explanation || null,
    reasonCodes,
    contradictionCodes,
  };
}

function formatCatalystExposureLabel(value: string, language: 'zh' | 'en'): string {
  const normalized = normalizeToken(value);
  if (!normalized) return '';
  const statusLabels = CATALYST_EXPOSURE_STATUS_LABELS[normalized];
  if (statusLabels) return statusLabels[language];
  const reasonLabels = CATALYST_EXPOSURE_REASON_LABELS[normalized];
  if (reasonLabels) return reasonLabels[language];
  return language === 'zh' ? '线索待确认' : 'Context pending';
}

function formatCatalystExposureTitle(item: WatchlistCatalystExposure, language: 'zh' | 'en'): string {
  const categoryLabels = CATALYST_EXPOSURE_CATEGORY_LABELS[normalizeToken(item.category)];
  if (categoryLabels) return categoryLabels[language];
  const title = normalizeText(item.title);
  if (title && !hasInternalConsumerCopy(title)) return title;
  return language === 'zh' ? '催化剂观察' : 'Catalyst context';
}

function formatCatalystExposureSummary(item: WatchlistCatalystExposure, language: 'zh' | 'en'): string {
  const category = normalizeToken(item.category);
  if (category === 'earnings_fundamental_snapshot') {
    return language === 'zh'
      ? '已保存基本面线索，适合继续观察。'
      : 'Saved fundamental context is available for observation.';
  }
  if (category === 'stored_news_catalyst_proxy') {
    return language === 'zh'
      ? '已保存新闻线索，可作为观察背景。'
      : 'Saved news context is available for observation.';
  }
  if (category === 'official_macro_cache_status') {
    return language === 'zh'
      ? '宏观背景较旧，阅读时降低置信度。'
      : 'Macro context is older, so read it with lower confidence.';
  }
  const summary = normalizeText(item.summary);
  if (summary && !hasInternalConsumerCopy(summary)) return summary;
  return language === 'zh' ? '已保存线索可供观察。' : 'Saved context is available for observation.';
}

function buildCatalystExposureMetadata(
  item: WatchlistCatalystExposure,
  language: 'zh' | 'en',
): string[] {
  return [
    item.timeframe ? `${language === 'zh' ? '时间范围' : 'Timeframe'} ${item.timeframe}` : null,
    item.asOf ? `${language === 'zh' ? '观察时间' : 'As of'} ${formatDateTime(item.asOf, language)}` : null,
    item.publishedAt ? `${language === 'zh' ? '发布时间' : 'Published'} ${formatDateTime(item.publishedAt, language)}` : null,
  ].filter(Boolean) as string[];
}

function buildWatchlistCatalystExposureView(
  exposures?: WatchlistCatalystExposure[] | null,
  language: 'zh' | 'en' = 'zh',
): WatchlistCatalystExposureView | null {
  const projected = (exposures || [])
    .filter((item) => normalizeText(item.title) || normalizeText(item.summary) || normalizeText(item.category))
    .slice(0, 3)
    .map((item) => ({
      id: item.id,
      title: formatCatalystExposureTitle(item, language),
      summary: formatCatalystExposureSummary(item, language),
      statusLabels: Array.from(new Set([
        formatCatalystExposureLabel(item.evidenceStatus || '', language),
        ...((item.evidenceLabels || []).map((label) => formatCatalystExposureLabel(label, language))),
      ].filter(Boolean))),
      reasonLabels: Array.from(new Set(
        (item.reasonCodes || [])
          .flatMap((code) => {
            const label = formatCatalystExposureLabel(code, language);
            return label ? [label] : [];
          }),
      )),
      metadata: buildCatalystExposureMetadata(item, language),
    }));
  if (!projected.length) return null;
  return {
    items: projected,
    hiddenCount: Math.max((exposures || []).length - projected.length, 0),
  };
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

  const topItem = items.reduce<WatchlistItem | null>((best, item) => {
    const score = getScannerScore(item);
    if (getTrustState(item) !== 'fresh' || score === null) return best;
    if (!best) return item;
    return score > (getScannerScore(best) ?? Number.NEGATIVE_INFINITY) ? item : best;
  }, null);
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
          ? `Review ${symbol}'s refreshed score state and observation summary.`
          : `查看 ${symbol} 的评分刷新状态与观察摘要。`);
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

function buildScannerLineageCue(item: WatchlistItem, language: 'zh' | 'en'): WatchlistScannerLineageCue {
  const source = normalizeToken(item.source);
  if (source !== 'scanner' && source !== 'scanner_run') return null;
  const lineage = item.intelligence?.scanner?.scannerLineageV1;
  if (lineage?.scoreSnapshotKind === 'post_add_refresh') {
    return language === 'en'
      ? {
        label: 'Updated after save',
        detail: 'Research score was refreshed after this item was saved; read it as a newer observation.',
      }
      : {
        label: '保存后更新',
        detail: '研究评分在保存后更新，可视为较新的观察记录。',
      };
  }
  if (!item.scannerRunId || !item.lastScoredAt || !item.createdAt) return null;
  const lastScoredTime = getTime(item.lastScoredAt);
  const createdTime = getTime(item.createdAt);
  if (!lastScoredTime || !createdTime || lastScoredTime <= createdTime + 60 * 1000) return null;

  return language === 'en'
    ? {
      label: 'Updated after save',
      detail: 'Research score was refreshed after this item was saved; read it as a newer observation.',
    }
    : {
      label: '保存后更新',
      detail: '研究评分在保存后更新，可视为较新的观察记录。',
    };
}

function buildWatchRiskNote(item: WatchlistItem, language: 'zh' | 'en'): string | null {
  const state = getScoreDisclosureState(item);
  const notice = formatScoreDisclosureNotice(item, state, language);
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
  const priceValue = getWatchlistPriceValue(item);
  if (priceValue === null && !normalizeText(item.name)) {
    return language === 'en' ? 'Review stock structure' : '查看个股结构';
  }
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

function buildWatchlistRowStatus(item: WatchlistItem, language: 'zh' | 'en'): WatchlistRowStatus {
  const priceValue = getWatchlistPriceValue(item);
  const latestTime = getLatestIntelligenceTime(item);
  const scoreState = getScoreDisclosureState(item);
  const hasResearch = hasScannerEvidence(item) || hasBacktestEvidence(item);
  const priceLabel = priceValue === null
    ? (language === 'en' ? 'Price unavailable' : '价格暂缺')
    : `${language === 'en' ? 'Price' : '价格'} ${formatPriceValue(priceValue, item.market)}`;
  const updateLabel = latestTime
    ? `${language === 'en' ? 'Updated' : '更新'} ${formatDateTime(latestTime, language)}`
    : (language === 'en' ? 'Update time unavailable' : '更新时间暂无');

  let researchStatusLabel = language === 'en' ? 'Research pending' : '研究待补充';
  let researchStatusVariant: WatchlistRowStatus['researchStatusVariant'] = 'neutral';
  if (scoreState === 'failed') {
    researchStatusLabel = language === 'en' ? 'Research unavailable' : '研究暂不可用';
    researchStatusVariant = 'danger';
  } else if (scoreState === 'fresh' && hasResearch) {
    researchStatusLabel = language === 'en' ? 'Research updated' : '研究已更新';
    researchStatusVariant = 'success';
  } else if (hasResearch) {
    researchStatusLabel = language === 'en' ? 'Review needed' : '研究待复核';
    researchStatusVariant = 'caution';
  }

  const missingParts = [
    priceValue === null ? (language === 'en' ? 'price' : '价格') : null,
    !latestTime ? (language === 'en' ? 'update time' : '更新时间') : null,
    !hasResearch ? (language === 'en' ? 'research status' : '研究状态') : null,
  ].filter(Boolean) as string[];
  const missingSummary = missingParts.length
    ? (language === 'en'
      ? `${missingParts.join(', ')} unavailable; use the next research check.`
      : `${missingParts.join('、')}暂缺，按下一步补充。`)
    : null;

  return {
    priceLabel,
    updateLabel,
    researchStatusLabel,
    researchStatusVariant,
    missingSummary,
  };
}

function buildWatchlistRowResearchPacketView(
  item: WatchlistItem,
  language: 'zh' | 'en',
): WatchlistRowResearchPacketConsumerCopy | null {
  return getWatchlistRowResearchPacketConsumerCopy(item.rowResearchPacket ?? null, language);
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
  const market = normalizeMarket(item.market);
  return buildResearchWorkspacePath('backtest', language, {
    symbol: item.symbol,
    market,
    source: normalizeResearchWorkspaceSource(item.source) || 'watchlist',
  });
}

function buildScannerPath(item: WatchlistItem, language: 'zh' | 'en'): string {
  const market = normalizeMarket(item.market);
  return buildResearchWorkspacePath('scanner', language, {
    symbol: item.symbol,
    market,
    source: 'watchlist',
  });
}

function buildStockStructurePath(item: WatchlistItem, language: 'zh' | 'en'): string {
  return buildLocalizedPath(`/stocks/${encodeURIComponent(item.symbol)}/structure-decision`, language);
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

function buildWatchlistManualResearchPath(symbol: string, language: 'zh' | 'en', taskId?: string | null): string {
  const params = new URLSearchParams({
    symbol,
    source: 'watchlist_empty',
  });
  if (taskId) params.set('task_id', taskId);
  return buildLocalizedPath(`/?${params.toString()}`, language);
}

function getCopy(language: 'zh' | 'en') {
  if (language === 'en') {
    return {
      title: 'Watchlist',
      subtitle: 'Clean monitoring list for research candidates.',
      totalTracked: 'Total tracked',
      marketsRepresented: 'Markets represented',
      scannerSourced: 'Research candidates',
      recentlyAdded: 'Recently added',
      trackedSymbols: 'Tracked symbols',
      scannerCoverage: 'Research scores',
      backtestCoverage: 'Backtest results',
      staleCoverage: 'Recent available',
      failureCoverage: 'Unavailable',
      latestUpdate: 'Latest update',
      filters: 'Filters',
      advancedFilters: 'Advanced filters',
      runtimeStatus: 'Processing status',
      batchActions: 'Batch actions',
      historyPrefix: 'HIST',
      hitPrefix: 'HIT',
      search: 'Search',
      searchPlaceholder: 'Symbol or name',
      market: 'Market',
      source: 'Added via',
      context: 'Theme / universe',
      sort: 'Sort',
      all: 'All',
      newest: 'Newest',
      scannerScore: 'Research score',
      backtestReturn: 'Backtest return',
      historicalHitRate: 'Historical hit rate',
      recentlyScored: 'Recently scored',
      recentlyBacktested: 'Recently backtested',
      evidence: 'Evidence',
      hasScanner: 'Has research score',
      hasBacktest: 'Has backtest evidence',
      scannerSelected: 'Research candidate',
      staleIntelligence: 'Recent available data',
      intelligence: 'Intelligence',
      scannerLineage: 'Research workflow context',
      investorSignal: 'Investor signal observation',
      investorSignalSummary: 'Saved research observation · collapsed by default',
      catalystExposures: 'Catalyst observation',
      catalystExposuresSummary: 'Saved observation context · collapsed by default',
      catalystExposuresReasons: 'Observation limits',
      catalystExposuresBounded: 'Showing the most recent saved items only',
      investorSignalState: 'State',
      investorSignalConfidence: 'Confidence',
      investorSignalFreshness: 'Observation freshness',
      investorSignalReasons: 'Current limits',
      investorSignalContradictions: 'Mixed signals',
      noEvidence: 'Evidence updating',
      batchBacktestFilter: 'Backtest current filter',
      batchScanFilter: 'Refresh current filter',
      selectedOnly: 'Selected only',
      clearSelection: 'Clear selection',
      refreshIntelligence: 'Refresh research view',
      scopeSelected: 'selected symbols',
      scopeFiltered: 'filtered symbols',
      emptyFilteredSet: 'Current filter is empty',
      noMatchedSymbols: 'No matching symbols',
      scanComplete: 'Research refresh completed.',
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
      autoRefresh: 'Scheduled update',
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
      emptyBody: 'Under the current saved coverage, no watchlist rows are available yet. Start with one manual symbol research task here, then save only if you decide to keep observing it.',
      emptyHelp: 'Saved rows return here after you explicitly keep a symbol for ongoing observation.',
      emptyPreviewEyebrow: 'Feature preview',
      emptyPreviewTitle: 'Example preview',
      emptyPreviewBody: 'A saved observation row can show source, evidence state, latest observation, and the next research step.',
      emptyPreviewItems: [
        { label: 'Saved observation', value: 'Symbol / market / source', detail: 'Real rows appear only after the user saves a symbol.' },
        { label: 'Evidence state', value: 'Research score / data state', detail: 'State labels explain freshness and limits without making a recommendation.' },
        { label: 'Next research step', value: 'Open analysis / refresh / backtest', detail: 'Actions are explicit user research steps, not execution shortcuts.' },
      ] as WatchlistEmptyPreviewItem[],
      emptyPreviewFootnote: 'Demo sample only. It is not persisted, counted as a watchlist item, exported as user data, or used by scanner ranking.',
      emptyScannerHelp: 'Keep the first step here focused on one-symbol research and explicit save decisions.',
      savedObservationHelp: 'Saved observations are created only after you explicitly save a symbol; this preview does not create one.',
      manualResearchLabel: 'Manual research symbol',
      manualResearchPlaceholder: 'TSLA',
      manualResearchHelp: 'Primary path: start one stock research task here without adding anything to Watchlist.',
      manualResearchButton: 'Research',
      enterManualSymbol: 'Enter one symbol before starting research.',
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
      scannerSourced: '研究候选',
      recentlyAdded: '近期新增',
      trackedSymbols: '观察标的数',
      scannerCoverage: '已有研究评分',
    backtestCoverage: '已有回测结果',
    staleCoverage: '最近可用',
    failureCoverage: '暂不可用',
    latestUpdate: '最近更新时间',
    filters: '筛选',
    advancedFilters: '高级筛选',
      runtimeStatus: '处理状态',
      batchActions: '批量操作',
    historyPrefix: '历史',
    hitPrefix: '命中',
    search: '搜索',
    searchPlaceholder: '代码或名称',
    market: '市场',
      source: '加入路径',
    context: '主题 / 候选范围',
    sort: '排序',
    all: '全部',
    newest: '最新',
      scannerScore: '研究评分',
    backtestReturn: '回测收益',
    historicalHitRate: '历史胜率',
    recentlyScored: '最近评分',
    recentlyBacktested: '最近回测',
    evidence: '证据筛选',
      hasScanner: '有研究评分',
      hasBacktest: '有回测证据',
      scannerSelected: '研究候选',
    staleIntelligence: '最近可用数据',
    intelligence: '观察依据',
      scannerLineage: '研究流程记录',
      investorSignal: '资金面观察信号',
      investorSignalSummary: '来自已保存的研究观察 · 默认收起',
      catalystExposures: '催化剂观察',
      catalystExposuresSummary: '来自已保存的观察线索 · 默认收起',
      catalystExposuresReasons: '观察边界',
    catalystExposuresBounded: '仅展示最近保存的线索',
    investorSignalState: '观察状态',
    investorSignalConfidence: '置信度',
    investorSignalFreshness: '观察时效',
    investorSignalReasons: '当前限制',
    investorSignalContradictions: '分歧线索',
      noEvidence: '依据更新中',
      batchBacktestFilter: '回测当前筛选',
      batchScanFilter: '刷新当前筛选',
    selectedOnly: '仅选中',
    clearSelection: '清除选择',
      refreshIntelligence: '刷新观察依据',
    scopeSelected: '已选中',
    scopeFiltered: '当前筛选',
    emptyFilteredSet: '当前筛选为空',
    noMatchedSymbols: '无匹配标的',
      scanComplete: '研究状态刷新完成。',
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
      autoRefresh: '定时更新',
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
      emptyBody: '当前已保存覆盖下还没有可用观察行。可先在这里手动研究一个代码，确认后再决定是否保存到观察列表。',
    emptyHelp: '只有你明确保留观察后，已保存的候选证据与状态才会回到这里。',
    emptyPreviewEyebrow: '功能预览',
    emptyPreviewTitle: '示例预览',
    emptyPreviewBody: '真实保存后，观察行会展示加入来源、证据状态、最近观察与下一步研究动作。',
    emptyPreviewItems: [
      { label: '保存观察', value: '代码 / 市场 / 加入路径', detail: '只有用户明确保存后，真实观察行才会出现。' },
      { label: '证据状态', value: '研究评分 / 数据状态', detail: '状态标签说明时效与限制，不给出推荐。' },
      { label: '下一步研究', value: '打开分析 / 刷新 / 回测', detail: '全部是用户触发的研究步骤，不是执行入口。' },
    ] as WatchlistEmptyPreviewItem[],
    emptyPreviewFootnote: '仅为演示样例；不会持久化，不计入观察名单数量，不导出为用户数据，也不会进入扫描器官方排名。',
    emptyScannerHelp: '这里优先保留单标的研究与明确保存观察的路径。',
    savedObservationHelp: '保存观察只会在你明确保存代码后创建；这里的预览不会创建观察项。',
    manualResearchLabel: '手动研究代码',
    manualResearchPlaceholder: 'TSLA',
    manualResearchHelp: '首选路径：先启动一个个股研究任务，不会把代码加入观察名单。',
    manualResearchButton: '研究',
    enterManualSymbol: '请先输入一个研究代码。',
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
  const { search: routeSearch } = useLocation();
  const { language } = useI18n();
  const { isGuest } = useProductSurface();
  const copy = getCopy(language);
  const routeContext = useMemo(() => parseResearchWorkspaceSearch(routeSearch), [routeSearch]);
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [researchPriorityQueue, setResearchPriorityQueue] = useState<WatchlistResearchPriorityQueueItem[]>([]);
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
  const [emptyResearchSymbol, setEmptyResearchSymbol] = useState('');
  const [isEmptyResearchPending, setIsEmptyResearchPending] = useState(false);
  const [backtestSessionKeys, setBacktestSessionKeys] = useState<Set<string>>(() => new Set());
  const [selectedIds, setSelectedIds] = useState<Set<number>>(() => new Set());
  const [useSelectedScope, setUseSelectedScope] = useState(false);
  const [activeItemId, setActiveItemId] = useState<number | null>(null);
  const [advancedFiltersOpen, setAdvancedFiltersOpen] = useState(false);

  useEffect(() => {
    document.title = language === 'en' ? 'Watchlist - WolfyStock' : '观察列表 - WolfyStock';
  }, [language]);

  useEffect(() => {
    if (routeContext.symbol) {
      setQuery(routeContext.symbol);
    }
    if (routeContext.market) {
      setMarketFilter(routeContext.market.toLowerCase());
    }
    if (routeContext.source === 'scanner') {
      setSourceFilter('scanner');
    }
  }, [routeContext.market, routeContext.source, routeContext.symbol]);

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
    watchlistApi.getResearchOverlay()
      .then((response) => {
        if (!isMounted) return;
        setResearchPriorityQueue(response.researchPriorityQueue || []);
      })
      .catch(() => {
        if (!isMounted) return;
        setResearchPriorityQueue([]);
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

  const marketOptions = useMemo(() => {
    const markets = Array.from(new Set(items.flatMap((item) => {
      const market = normalizeText(item.market).toLowerCase();
      return market ? [market] : [];
    }))).sort();
    return [
      { value: 'all', label: copy.all },
      ...markets.map((market) => ({ value: market, label: formatMarket(market) })),
    ];
  }, [copy.all, items]);

  const sourceOptions = useMemo(() => {
    const sources = Array.from(new Set(items.flatMap((item) => {
      const source = normalizeText(item.source).toLowerCase();
      return source ? [source] : [];
    }))).sort();
    return [
      { value: 'all', label: copy.all },
      ...sources.map((source) => ({ value: source, label: formatWatchlistOrigin(source, language) })),
    ];
  }, [copy.all, items, language]);

  const contextOptions = useMemo(() => {
    const options = new Map<string, string>();
    items.forEach((item) => {
      if (item.themeId) options.set(`theme:${item.themeId}`, `${copy.themePrefix}: ${item.themeId}`);
      if (item.universeType) options.set(`universe:${item.universeType}`, `${copy.universePrefix}: ${item.universeType}`);
    });
    return [
      { value: 'all', label: copy.all },
      ...Array.from(options.entries()).map(([value, label]) => ({ value, label })),
    ];
  }, [copy.all, copy.themePrefix, copy.universePrefix, items]);

  const summary = useMemo(() => {
    const markets = new Set(items.flatMap((item) => {
      const market = normalizeText(item.market).toLowerCase();
      return market ? [market] : [];
    }));
    const scannerSourced = items.filter((item) => normalizeText(item.source).toLowerCase() === 'scanner').length;
    const latestTime = items.reduce<string | null>((latest, item) => {
      const value = getLatestIntelligenceTime(item);
      return value && (!latest || getTime(value) > getTime(latest)) ? value : latest;
    }, null);
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
  }, [items]);

  const filteredItems = useMemo(() => {
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
  }, [contextFilter, evidenceFilter, items, marketFilter, query, sortKey, sourceFilter]);

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
  const emptyResearchParsedSymbol = useMemo(
    () => parseManualResearchSymbol(emptyResearchSymbol),
    [emptyResearchSymbol],
  );
  const watchlistConclusion = useMemo(
    () => buildWatchlistConclusion(filteredItems, language),
    [filteredItems, language],
  );

  const toggleSelected = useCallback((item: WatchlistItem) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(item.id)) next.delete(item.id);
      else next.add(item.id);
      setUseSelectedScope(next.size > 0);
      return next;
    });
  }, []);

  const handleAnalyze = useCallback(async (item: WatchlistItem) => {
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
  }, [copy.analyzeStarted, language, navigate]);

  const handleEmptyManualResearch = useCallback(async () => {
    const symbol = emptyResearchParsedSymbol;
    if (!symbol) {
      setNotice({ tone: 'warning', message: copy.enterManualSymbol });
      return;
    }

    setIsEmptyResearchPending(true);
    setNotice(null);
    try {
      const response = await analysisApi.analyzeAsync({
        stockCode: symbol,
        reportType: 'detailed',
        stockName: symbol,
        originalQuery: symbol,
        selectionSource: 'manual',
      });
      const taskId = extractAcceptedTaskId(response);
      navigate(buildWatchlistManualResearchPath(symbol, language, taskId));
    } catch (err) {
      if (err instanceof DuplicateTaskError) {
        navigate(buildWatchlistManualResearchPath(symbol, language, err.existingTaskId));
        return;
      }
      setNotice({ tone: 'danger', message: getParsedApiError(err).message });
    } finally {
      setIsEmptyResearchPending(false);
    }
  }, [copy.enterManualSymbol, emptyResearchParsedSymbol, language, navigate]);

  const handleRemove = useCallback(async (item: WatchlistItem) => {
    setPendingRemoveId(item.id);
    setNotice(null);
    try {
      await watchlistApi.removeWatchlistItem(item.id);
      setItems((current) => current.filter((row) => row.id !== item.id));
      setResearchPriorityQueue((current) => current.filter((row) => row.symbol !== item.symbol));
      setNotice({ tone: 'success', message: copy.removed });
    } catch (err) {
      setNotice({ tone: 'danger', message: getParsedApiError(err).message });
    } finally {
      setPendingRemoveId((current) => (current === item.id ? null : current));
    }
  }, [copy.removed]);

  const handleCopy = useCallback(async (item: WatchlistItem) => {
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
  }, [copy.clipboardUnavailable, copy.copied, copy.copyFailed]);

  const handleRefreshIntelligence = useCallback(async () => {
    setNotice(null);
    try {
      const [listResponse, statusResponse, overlayResponse] = await Promise.all([
        watchlistApi.listWatchlistItems(),
        watchlistApi.getRefreshStatus().catch(() => null),
        watchlistApi.getResearchOverlay().catch(() => null),
      ]);
      setItems(listResponse.items || []);
      setRefreshStatus(statusResponse);
      setResearchPriorityQueue(overlayResponse?.researchPriorityQueue || []);
    } catch (err) {
      setNotice({ tone: 'danger', message: getParsedApiError(err).message });
    }
  }, []);

  const handleRefreshScores = useCallback(async (targetItems?: WatchlistItem[]) => {
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
        symbols: targets.flatMap((item) => (item.symbol ? [item.symbol] : [])),
      } : { force: true });
      const [listResponse, overlayResponse] = await Promise.all([
        watchlistApi.listWatchlistItems(),
        watchlistApi.getResearchOverlay().catch(() => null),
      ]);
      const failures = Object.fromEntries(
        (response.results || [])
          .flatMap((result) => (
            normalizeText(result.status).toLowerCase() === 'failed'
              ? [[result.symbol, sanitizeFailureReason(result.message || '', '扫描失败')]]
              : []
          )),
      );
      setItems(listResponse.items || []);
      setResearchPriorityQueue(overlayResponse?.researchPriorityQueue || []);
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
  }, [copy.scanComplete, copy.scoreRefreshComplete, isBatchScanning, items]);

  const handleBatchBacktestCurrentFilter = useCallback(async () => {
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
  }, [actionItems, backtestSessionKeys, copy.batchBacktestComplete, copy.batchBacktestLabel, isBatchBacktesting]);

  if (isGuest) {
    return <ConsumerProtectedFrame moduleName={copy.signInModule} />;
  }

  const noticeClassName = notice?.tone === 'danger'
    ? 'border-rose-400/20 bg-rose-500/5 text-rose-100/80'
    : notice?.tone === 'warning'
      ? 'border-amber-300/20 bg-amber-300/5 text-amber-100/80'
      : 'border-emerald-400/20 bg-emerald-400/5 text-emerald-100/80';
  const autoRefreshStatus = describeBooleanEnabled(refreshStatus?.enabled, { language });
  const isWatchlistEmptyWorkspace = !isLoading && !error && items.length === 0;
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
  const activeScannerLineageCue = activeItem ? buildScannerLineageCue(activeItem, language) : null;
  const activeScannerLineageView = activeItem ? buildScannerLineageView(activeScanner?.scannerLineageV1, language) : null;
  const activeScannerStatusLabel = activeItem ? formatScannerStatus(activeItem) : '--';
  const activeBacktestStatusLabel = activeItem ? formatBacktestStatus(activeItem) : '--';
  const activeScannerReason = activeItem ? formatScannerReason(activeScanner?.reason, language) : null;
  const activeInvestorSignal = activeItem ? buildWatchlistInvestorSignalView(activeScanner?.investorSignal, language) : null;
  const activeCatalystExposures = activeItem ? buildWatchlistCatalystExposureView(activeItem.intelligence?.catalystExposures, language) : null;
  const activeWorkflowSteps = activeItem ? buildWatchlistWorkflowSteps(activeItem, language) : [];
  const activeScannerFailure = activeItem && (activeItem.scoreError || activeScanner?.reason)
    ? sanitizeFailureReason(activeItem.scoreError || activeScanner?.reason || '', '扫描失败')
    : null;
  const activeBacktestSummary = activeItem && hasBacktestMetrics(activeItem)
    ? `${language === 'zh' ? '收益' : 'Return'} ${formatPct(activeBacktest?.totalReturnPct)} · ${language === 'zh' ? '回撤' : 'DD'} ${formatPct(activeBacktest?.maxDrawdownPct)} · Sharpe ${formatRatio(activeBacktest?.sharpe)} · ${language === 'zh' ? '交易' : 'Trades'} ${activeBacktest?.tradeCount ?? '--'}`
    : copy.noEvidence;
  const activeObservationSummary = activeItem ? buildObservationSummary(activeItem, language) : copy.noEvidence;
  const activeRiskNote = activeItem ? buildWatchRiskNote(activeItem, language) : null;
  const activeNextActionLabel = activeItem ? buildNextActionLabel(activeItem, language) : '--';
  const activeIdentityLabel = activeItem ? buildWatchlistIdentityLabel(activeItem, language) : '';
  const activeSavedNote = activeItem ? normalizeText(activeItem.notes) : '';
  const activeContextTags = activeItem
    ? [
        activeItem.themeId ? `${copy.themePrefix}: ${activeItem.themeId}` : null,
        activeItem.universeType ? `${copy.universePrefix}: ${activeItem.universeType}` : null,
      ].filter(Boolean) as string[]
    : [];
  const activeHasEvidence = activeItem
    ? hasScannerEvidence(activeItem) || activeSimulation?.status === 'ready' || hasBacktestEvidence(activeItem)
    : false;
  const watchlistWorkflowSymbol = activeItem?.symbol || routeContext.symbol || null;
  const watchlistWorkflowMarket = activeItem?.market || routeContext.market || null;
  const watchlistWorkflowKnownEvidence = [
    activeItem
      ? (language === 'zh' ? `观察项已存在：${activeItem.symbol}` : `Observed item exists: ${activeItem.symbol}`)
      : watchlistWorkflowSymbol
        ? (language === 'zh' ? `当前筛选代码：${watchlistWorkflowSymbol}` : `Current filtered symbol: ${watchlistWorkflowSymbol}`)
        : null,
    activeObservationSummary !== copy.noEvidence ? activeObservationSummary : null,
    activeScannerLineageView?.summary,
    activeItem && hasBacktestMetrics(activeItem)
      ? activeBacktestSummary
      : null,
  ];
  const watchlistWorkflowMissingEvidence = [
    !activeItem && watchlistWorkflowSymbol
      ? (language === 'zh' ? '当前观察列表未识别到该代码记录' : 'No matching observation record is visible in Watchlist')
      : null,
    activeItem && !hasBacktestEvidence(activeItem)
      ? (language === 'zh' ? '回测验证待补充' : 'Backtest validation is still missing')
      : null,
    watchlistWorkflowSymbol
      ? (language === 'zh' ? '组合暴露与期权情景待核对' : 'Portfolio exposure and options scenario context need review')
      : null,
  ];
  const watchlistWorkflowStateNotes = [
    activeItem ? formatScoreDisclosureFreshness(activeItem, activeLatestTime, language) : null,
    activeScannerLineageView?.freshnessLabel,
    activeBacktestStatusLabel && activeBacktestStatusLabel !== '--' ? activeBacktestStatusLabel : null,
  ];
  const watchlistWorkflowSource = routeContext.source || normalizeResearchWorkspaceSource(activeItem?.source) || 'watchlist';
  const watchlistWorkflowNextSteps = [
    watchlistWorkflowSymbol
      ? (language === 'zh' ? '查看组合暴露，确认是否已有持仓上下文' : 'Review portfolio exposure to check existing holding context')
      : null,
    watchlistWorkflowSymbol
      ? (language === 'zh' ? '进入回测验证历史规则表现' : 'Open Backtest for historical rule validation')
      : null,
    watchlistWorkflowSymbol
      ? (language === 'zh' ? '进入期权实验室，仅查看情景准备度' : 'Open Options Lab for scenario readiness only')
      : null,
  ];
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
          action={undefined}
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

        {watchlistWorkflowSymbol ? (
          <ResearchWorkspaceFlowPanel
            language={language}
            current="watchlist"
            symbol={watchlistWorkflowSymbol}
            market={watchlistWorkflowMarket}
            source={watchlistWorkflowSource}
            knownEvidence={watchlistWorkflowKnownEvidence}
            missingEvidence={watchlistWorkflowMissingEvidence}
            stateNotes={watchlistWorkflowStateNotes}
            nextSteps={watchlistWorkflowNextSteps}
            testId="watchlist-research-workspace-flow"
          />
        ) : null}

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
        {!isWatchlistEmptyWorkspace ? (
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
        ) : null}

        <div
          data-testid="watchlist-board-shell"
          className={isWatchlistEmptyWorkspace ? 'grid min-w-0' : 'grid min-w-0 lg:grid-cols-[minmax(0,1fr)_340px]'}
        >
          <div data-layout-zone="PrimaryWorkRegion" data-testid="watchlist-primary-work-region" className="min-w-0">
            <ConsoleBoard className="rounded-none border-0 bg-transparent">
              {!isWatchlistEmptyWorkspace ? (
                <div className="flex min-w-0 items-center justify-between gap-3 border-b border-[color:var(--wolfy-divider)] px-4 py-3">
                  <div className="min-w-0">
                    <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">{copy.tableTitle}</p>
                    <p className="truncate text-xs text-[color:var(--wolfy-text-secondary)]">{copy.tableDescription}</p>
                  </div>
                  <TerminalChip variant="neutral" className="font-mono">
                    {actionScopeLabel}
                  </TerminalChip>
                </div>
              ) : null}
              {!isWatchlistEmptyWorkspace ? (
                <div
                  data-testid="watchlist-list-header"
                  className="hidden min-w-0 grid-cols-[minmax(0,1.35fr)_minmax(0,1.15fr)_minmax(0,1.05fr)_auto] gap-4 border-b border-[color:var(--wolfy-divider)] px-4 py-2 text-[11px] uppercase tracking-[0.18em] text-[color:var(--wolfy-text-muted)] lg:grid"
                >
                  <span>{language === 'en' ? 'Symbol' : '标的'}</span>
                  <span>{language === 'en' ? 'Price / update' : '价格 / 更新'}</span>
                  <span>{language === 'en' ? 'Research / next' : '研究 / 下一步'}</span>
                  <span className="text-right">{copy.actions}</span>
                </div>
              ) : null}
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
                    const scannerStatusLabel = formatScannerStatus(item);
                    const backtestStatusLabel = formatBacktestStatus(item, batchFailure);
                    const isActive = activeItem?.id === item.id;
                    const rowRiskNote = buildWatchRiskNote(item, language);
                    const scannerLineageCue = buildScannerLineageCue(item, language);
                    const originLabel = formatWatchlistOrigin(item.source, language);
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
                    const rowPacketView = buildWatchlistRowResearchPacketView(item, language);
                    const rowObservation = rowPacketView
                      ? rowPacketView.missingSummary || rowPacketView.researchStatusLabel
                      : buildObservationSummary(item, language);
                    const rowNextAction = rowPacketView ? rowPacketView.nextDataActionLabel : buildNextActionLabel(item, language);
                    const rowStatus = buildWatchlistRowStatus(item, language);
                    const identityLabel = buildWatchlistIdentityLabel(item, language);
                    const workflowSteps = buildWatchlistWorkflowSteps(item, language);
                    const rowStateLine = rowPacketView
                      ? [
                          rowPacketView.quoteStateLabel,
                          rowPacketView.researchStatusLabel,
                          rowPacketView.scannerLineageLabel,
                        ].filter(Boolean).join(' · ')
                      : [
                          `${copy.score} ${formatScore(score)}`,
                          typeof avgForward === 'number' ? `${copy.historyPrefix} ${formatPct(avgForward)}` : null,
                          typeof hitRate === 'number' ? `${copy.hitPrefix} ${Math.round(hitRate * 100)}%` : null,
                        ].filter(Boolean).join(' · ');
                    const rowNotes = rowPacketView
                      ? [
                          rowPacketView.missingSummary,
                          rowPacketView.nextDataActionLabel,
                        ].filter(Boolean).join(' · ')
                      : [
                          rowStatus.missingSummary,
                          !rowStatus.missingSummary ? rowRiskNote : null,
                          scannerLineageCue?.detail,
                        ].filter(Boolean).join(' ');
                    const priceLabel = rowPacketView
                      ? rowPacketView.quotePrice !== null
                        ? formatPriceValue(rowPacketView.quotePrice, item.market)
                        : rowPacketView.quoteStateLabel
                      : rowStatus.priceLabel;
                    const updateLabel = rowPacketView
                      ? rowPacketView.quoteAsOf
                        ? `${language === 'en' ? 'Updated' : '更新'} ${formatDateTime(rowPacketView.quoteAsOf, language)}`
                        : (language === 'en' ? 'Quote time pending' : '报价时间待确认')
                      : rowStatus.updateLabel;

                    return (
                      <article
                        key={item.id}
                        data-testid={`watchlist-row-${item.symbol}`}
                        className={`min-w-0 border-b border-[color:var(--wolfy-divider)] px-3 py-3 transition-colors md:px-4 ${isActive ? 'bg-white/[0.045]' : 'bg-transparent hover:bg-white/[0.02]'}`}
                      >
                        <div className="grid min-w-0 gap-3 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1.15fr)_minmax(0,1.05fr)_auto] lg:items-start lg:gap-4">
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
                              <p className="truncate text-sm text-white/78">{identityLabel}</p>
                              <p className="truncate text-[11px] text-white/45">{originLabel}</p>
                            </button>
                          </div>

                          <div className="min-w-0 space-y-2">
                            <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--wolfy-text-muted)]">
                              {language === 'en' ? 'Price / update' : '价格 / 更新'}
                            </p>
                            <p className="text-sm font-medium text-white/82">{priceLabel}</p>
                            <p className="font-mono text-xs text-white/55">{updateLabel}</p>
                            <div
                              data-testid={`watchlist-row-workflow-${item.symbol}`}
                              className="flex min-w-0 flex-wrap items-center gap-1.5"
                              aria-label={language === 'zh' ? `${item.symbol} 研究流程` : `${item.symbol} research workflow`}
                            >
                              <span className="text-[11px] text-white/38">{language === 'zh' ? '研究流程' : 'Workflow'}</span>
                              {rowPacketView ? (
                                <>
                                  <TerminalChip variant={rowPacketView.quoteStateVariant}>{rowPacketView.quoteStateLabel}</TerminalChip>
                                  <TerminalChip variant={rowPacketView.researchStatusVariant}>{rowPacketView.researchStatusLabel}</TerminalChip>
                                  <TerminalChip variant={rowPacketView.scannerLineageVariant}>{rowPacketView.scannerLineageLabel}</TerminalChip>
                                </>
                              ) : (
                                workflowSteps.map((step) => (
                                  <TerminalChip key={step.key} variant={step.variant}>{step.label}</TerminalChip>
                                ))
                              )}
                            </div>
                          </div>

                          <div className="min-w-0 space-y-2">
                            <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--wolfy-text-muted)]">
                              {language === 'en' ? 'Research / next' : '研究 / 下一步'}
                            </p>
                            <div className="flex min-w-0 flex-wrap items-center gap-1.5">
                              {rowPacketView ? (
                                <>
                                  <TerminalChip variant={rowPacketView.researchStatusVariant}>{rowPacketView.researchStatusLabel}</TerminalChip>
                                  <TerminalChip variant={rowPacketView.scannerLineageVariant}>{rowPacketView.scannerLineageLabel}</TerminalChip>
                                  {rowPacketView.noAdviceLabel ? (
                                    <TerminalChip variant="neutral">{rowPacketView.noAdviceLabel}</TerminalChip>
                                  ) : null}
                                </>
                              ) : (
                                <>
                                  <TerminalChip variant={rowStatus.researchStatusVariant}>{rowStatus.researchStatusLabel}</TerminalChip>
                                  <TerminalChip variant={backtestStatusVariant}>{backtestStatusLabel}</TerminalChip>
                                  {scannerLineageCue ? (
                                    <TerminalChip variant="neutral">{scannerLineageCue.label}</TerminalChip>
                                  ) : null}
                                </>
                              )}
                              {batchDisplayStatus ? (
                                <TerminalChip variant={terminalChipVariant(batchDisplayStatus.tone)} className="font-mono">
                                  {batchDisplayStatus.label}
                                </TerminalChip>
                              ) : null}
                            </div>
                            <p className="truncate text-xs font-mono text-white/55">{rowStateLine || `${copy.score} ${formatScore(score)}`}</p>
                            <p className="text-sm leading-6 text-white/72">{rowObservation}</p>
                            <p className="text-xs text-white/58">{language === 'en' ? 'Next' : '下一步'} {rowNextAction}</p>
                            {rowNotes ? (
                              <p className="text-xs leading-5 text-white/52" data-testid={`watchlist-row-note-${item.symbol}`}>
                                {rowNotes}
                              </p>
                            ) : scannerFailure && scannerStatusLabel === '扫描失败' ? (
                              <p className="text-xs leading-5 text-rose-100/75">{scannerFailure.label}</p>
                            ) : null}
                          </div>

                          <div className="flex min-w-0 flex-wrap items-center gap-2 lg:justify-end">
                            <TerminalButton
                              type="button"
                              variant="compact"
                              aria-label={`${language === 'zh' ? '查看个股结构' : 'Open stock structure'} ${item.symbol}`}
                              onClick={() => navigate(buildStockStructurePath(item, language))}
                            >
                              <Search className="h-3.5 w-3.5" />
                              {language === 'zh' ? '结构' : 'Structure'}
                            </TerminalButton>
                            <TerminalButton
                              type="button"
                              variant="compact"
                              aria-label={`${language === 'zh' ? '打开扫描器' : 'Open scanner'} ${item.symbol}`}
                              onClick={() => navigate(buildScannerPath(item, language))}
                            >
                              <RefreshCw className="h-3.5 w-3.5" />
                              {language === 'zh' ? '扫描器' : 'Scanner'}
                            </TerminalButton>
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
                  className={isWatchlistEmptyWorkspace
                    ? 'mx-auto min-h-[168px] w-full max-w-3xl flex-col items-center justify-center rounded-none border-0 bg-transparent px-4 py-8 text-center sm:min-h-[188px]'
                    : 'min-h-[72px] flex-col items-start justify-start rounded-none border-x-0 border-b-0 border-t border-[color:var(--wolfy-divider)] bg-transparent px-4 py-4 sm:flex-row sm:items-center sm:justify-between'
                  }
                  action={undefined}
                >
                  <div className="grid w-full min-w-0 gap-4">
                    <div className="space-y-1">
                    <p>{copy.emptyBody}</p>
                    <p className="text-[11px] text-white/45">{copy.emptyHelp}</p>
                    <p className="text-[11px] text-white/45">{copy.emptyScannerHelp}</p>
                    </div>

                    {isWatchlistEmptyWorkspace ? (
                      <ConsumerOnboardingCtaPanel
                        data-testid="watchlist-empty-onboarding-cta"
                        language={language}
                        title={language === 'en' ? 'Start with market context or one user-chosen symbol' : '先看市场语境，再选择一个你想观察的代码'}
                        actions={[
                          {
                            route: '/market-overview',
                            description: language === 'en'
                              ? 'Read the broad market context before choosing a symbol.'
                              : '先阅读市场背景，再决定是否继续进入标的研究。',
                          },
                          {
                            route: '/scanner',
                            description: language === 'en'
                              ? 'Run scanner only when you want a fresh candidate set.'
                              : '需要候选集合时，由你手动运行扫描。',
                          },
                          {
                            route: '/watchlist',
                            description: language === 'en'
                              ? 'Use the input below to research one symbol before saving it.'
                              : '用下方输入框先研究一个代码，确认后再保存观察。',
                          },
                          {
                            route: '/research/radar',
                            description: language === 'en'
                              ? 'Review the radar after scanner or watchlist activity.'
                              : '扫描或观察列表有活动后，再回到研究雷达。',
                          },
                        ]}
                        starterResearchWorkflow={language === 'en'
                          ? ['Open Market Overview.', 'Research one symbol here.', 'Run Scanner if you need candidates.', 'Return to Research Radar after activity.']
                          : ['打开市场概览。', '在这里研究一个你选择的代码。', '需要候选集合时再运行 Scanner。', '有活动后回到研究雷达。']}
                        firstRunChecklist={language === 'en'
                          ? ['No symbol is saved automatically.', 'No seeded watchlist item is created.', 'Scanner and account actions stay user-triggered.']
                          : ['不会自动保存代码。', '不会创建预置观察标的。', '扫描和账户动作都保持用户触发。']}
                        radarLabel={language === 'en' ? 'Review Research Radar' : '查看研究雷达'}
                      />
                    ) : null}

                    {isWatchlistEmptyWorkspace ? (
                      <div
                        data-testid="watchlist-empty-preview"
                        className="grid min-w-0 gap-3 rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-3 text-left"
                      >
                        <div className="flex min-w-0 flex-wrap items-center gap-2">
                          <TerminalChip variant="info">{copy.emptyPreviewEyebrow}</TerminalChip>
                          <span className="text-[11px] font-semibold text-white/72">{copy.emptyPreviewTitle}</span>
                        </div>
                        <p className="text-xs leading-5 text-white/58">{copy.emptyPreviewBody}</p>
                        <div className="grid min-w-0 gap-2 md:grid-cols-3">
                          {copy.emptyPreviewItems.map((item) => (
                            <div key={item.label} className="min-w-0 rounded-lg border border-white/8 bg-black/20 px-2.5 py-2">
                              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-white/38">{item.label}</p>
                              <p className="mt-1 text-xs font-medium text-white/76">{item.value}</p>
                              <p className="mt-1 text-[11px] leading-relaxed text-white/45">{item.detail}</p>
                            </div>
                          ))}
                        </div>
                        <p className="text-[11px] leading-relaxed text-white/42">{copy.emptyPreviewFootnote}</p>
                      </div>
                    ) : null}

                    {isWatchlistEmptyWorkspace ? (
                      <div
                        data-testid="watchlist-empty-manual-research"
                        data-research-path="primary"
                        className="grid min-w-0 gap-2 rounded-xl border border-indigo-300/18 bg-indigo-300/[0.07] px-3 py-3 text-left"
                      >
                        <div className="flex min-w-0 flex-wrap items-center gap-2">
                          <TerminalChip variant="info">{language === 'en' ? 'Primary research path' : '首选研究路径'}</TerminalChip>
                          <span className="text-[11px] text-white/48">
                            {language === 'en'
                              ? 'Research one symbol first; save only if you explicitly want to keep monitoring it.'
                              : '先研究单个代码；只有你明确要继续跟踪时，才再保存到观察列表。'}
                          </span>
                        </div>
                        <label htmlFor="watchlist-empty-manual-symbol" className="text-[11px] font-semibold text-white/78">
                          {copy.manualResearchLabel}
                        </label>
                        <p className="text-[11px] leading-relaxed text-white/45">{copy.manualResearchHelp}</p>
                        <div className="flex min-w-0 flex-col gap-2 sm:flex-row">
                          <input
                            id="watchlist-empty-manual-symbol"
                            data-testid="watchlist-empty-manual-symbol-input"
                            value={emptyResearchSymbol}
                            className="h-9 min-w-0 flex-1 rounded-md border border-white/10 bg-black/35 px-3 text-sm font-mono text-white outline-none placeholder:text-white/22 focus:border-indigo-300/50"
                            onChange={(event) => setEmptyResearchSymbol(event.target.value)}
                            aria-label={copy.manualResearchLabel}
                            placeholder={copy.manualResearchPlaceholder}
                          />
                          <TerminalButton
                            type="button"
                            variant="primary"
                            data-testid="watchlist-empty-manual-research-button"
                            className="h-9 px-3 text-xs"
                            disabled={!emptyResearchParsedSymbol || isEmptyResearchPending}
                            onClick={() => void handleEmptyManualResearch()}
                          >
                            <Play className="h-3.5 w-3.5" aria-hidden="true" />
                            {isEmptyResearchPending
                              ? copy.analyzing
                              : emptyResearchParsedSymbol
                                ? `${copy.manualResearchButton} ${emptyResearchParsedSymbol}`
                                : copy.manualResearchButton}
                          </TerminalButton>
                        </div>
                        <p className="text-[11px] leading-relaxed text-white/42">{copy.savedObservationHelp}</p>
                        <p className="pt-1 text-[11px] leading-relaxed text-white/42">{copy.emptyScannerHelp}</p>
                      </div>
                    ) : null}
                  </div>
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
                      <p className="truncate text-xs text-white/58">{activeIdentityLabel}</p>
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
                    {activeScannerLineageCue ? (
                      <TerminalChip variant="neutral">{activeScannerLineageCue.label}</TerminalChip>
                    ) : null}
                    <TerminalChip variant={activeBacktestStatusLabel === '已回测' ? 'success' : ['回测失败', '行情缺失', '服务暂不可用', '超时'].includes(activeBacktestStatusLabel) ? 'danger' : ['样本不足', '数据缺失'].includes(activeBacktestStatusLabel) ? 'caution' : 'neutral'}>
                      {activeBacktestStatusLabel}
                    </TerminalChip>
                  </div>
                  <div
                    data-testid="watchlist-detail-workflow"
                    className="mt-3 flex min-w-0 flex-wrap items-center gap-1.5"
                  >
                    <span className="text-[11px] text-white/40">{language === 'zh' ? '研究流程' : 'Workflow'}</span>
                    {activeWorkflowSteps.map((step) => (
                      <TerminalChip key={step.key} variant={step.variant}>{step.label}</TerminalChip>
                    ))}
                  </div>
                </section>

                <section className="grid min-w-0 gap-3 border-y border-[color:var(--wolfy-divider)] py-4">
                  <div className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-3">
                    <p className="text-[11px] text-white/40">{language === 'zh' ? '当前状态' : 'Current state'}</p>
                    <p className="mt-1 text-sm text-white/78">{formatScoreDisclosureFreshness(activeItem, activeLatestTime, language)}</p>
                    {activeScannerLineageCue ? (
                      <p className="mt-2 text-xs leading-5 text-white/52">{activeScannerLineageCue.detail}</p>
                    ) : null}
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

                {activeScannerLineageView ? (
                  <DenseSecondaryDisclosure
                    data-testid="watchlist-scanner-lineage"
                    variant="row"
                    title={copy.scannerLineage}
                    summary={activeScannerLineageView.summary}
                  >
                    <div className="space-y-3 text-xs leading-5 text-white/68">
                      <div className="flex min-w-0 flex-wrap gap-1.5">
                        <TerminalChip variant="neutral">{activeScannerLineageView.snapshotLabel}</TerminalChip>
                        <TerminalChip variant="caution">{activeScannerLineageView.stateLabel}</TerminalChip>
                        <TerminalChip variant="neutral">{activeScannerLineageView.freshnessLabel}</TerminalChip>
                      </div>
                      <div className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-2">
                        <p className="text-[11px] text-white/40">{language === 'zh' ? '研究原因' : 'Research reason'}</p>
                        <p className="mt-1 text-sm text-white/75">{activeScannerLineageView.reason}</p>
                      </div>
                      <div className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-2">
                        <p className="text-[11px] text-white/40">{language === 'zh' ? '下一步' : 'Next step'}</p>
                        <p className="mt-1 text-sm text-white/75">{activeScannerLineageView.nextStep}</p>
                      </div>
                      {activeScannerLineageView.metadata.length ? (
                        <div className="flex min-w-0 flex-wrap gap-2 text-[11px] text-white/45">
                          {activeScannerLineageView.metadata.map((label) => (
                            <span key={label}>{label}</span>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  </DenseSecondaryDisclosure>
                ) : null}

                <section className="min-w-0 py-4">
                  <div className="mb-3 flex min-w-0 items-center justify-between gap-3">
                    <h3 className="text-sm font-semibold text-white">{copy.intelligence}</h3>
                  </div>
                  <div className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-3 text-xs leading-5 text-white/68">
                    {activeBacktestSummary}
                  </div>
                </section>

                <UserAlertsRailPanel
                  symbol={activeItem.symbol}
                  language={language}
                />

                {activeCatalystExposures ? (
                  <DenseSecondaryDisclosure
                    data-testid="watchlist-catalyst-exposures"
                    variant="row"
                    title={copy.catalystExposures}
                    summary={copy.catalystExposuresSummary}
                  >
                    <div className="space-y-3 text-xs leading-5 text-white/68">
                      {activeCatalystExposures.items.map((exposure) => (
                        <div
                          key={exposure.id}
                          className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-3"
                        >
                          <p className="truncate text-sm text-white/82">{exposure.title}</p>
                          {exposure.summary ? (
                            <p className="mt-1 text-xs leading-5 text-white/65">{exposure.summary}</p>
                          ) : null}
                          {exposure.statusLabels.length ? (
                            <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
                              {exposure.statusLabels.map((label) => (
                                <TerminalChip key={`${exposure.id}:${label}`} variant="neutral">{label}</TerminalChip>
                              ))}
                            </div>
                          ) : null}
                          {exposure.metadata.length ? (
                            <div className="mt-2 flex min-w-0 flex-wrap gap-2 text-[11px] text-white/45">
                              {exposure.metadata.map((label) => (
                                <span key={`${exposure.id}:${label}`}>{label}</span>
                              ))}
                            </div>
                          ) : null}
                          {exposure.reasonLabels.length ? (
                            <div className="mt-2 space-y-1.5">
                              <p className="text-[11px] uppercase tracking-[0.18em] text-white/38">{copy.catalystExposuresReasons}</p>
                              <div className="flex min-w-0 flex-wrap gap-1.5">
                                {exposure.reasonLabels.map((label) => (
                                  <TerminalChip key={`${exposure.id}:reason:${label}`} variant="caution">{label}</TerminalChip>
                                ))}
                              </div>
                            </div>
                          ) : null}
                        </div>
                      ))}
                      {activeCatalystExposures.hiddenCount > 0 ? (
                        <p className="text-[11px] text-white/45">{copy.catalystExposuresBounded}</p>
                      ) : null}
                    </div>
                  </DenseSecondaryDisclosure>
                ) : null}

                {activeInvestorSignal ? (
                  <DenseSecondaryDisclosure
                    data-testid="watchlist-investor-signal"
                    variant="row"
                    title={copy.investorSignal}
                    summary={copy.investorSignalSummary}
                  >
                    <div className="space-y-3 text-xs leading-5 text-white/68">
                      <div className="grid min-w-0 gap-2 sm:grid-cols-3">
                        {activeInvestorSignal.stateLabel ? (
                          <div className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-2">
                            <p className="text-[11px] text-white/40">{copy.investorSignalState}</p>
                            <p className="mt-1 text-sm text-white/78">{activeInvestorSignal.stateLabel}</p>
                          </div>
                        ) : null}
                        {activeInvestorSignal.confidenceLabel ? (
                          <div className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-2">
                            <p className="text-[11px] text-white/40">{copy.investorSignalConfidence}</p>
                            <p className="mt-1 text-sm text-white/78">{activeInvestorSignal.confidenceLabel}</p>
                          </div>
                        ) : null}
                        {activeInvestorSignal.freshnessLabel ? (
                          <div className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-2">
                            <p className="text-[11px] text-white/40">{copy.investorSignalFreshness}</p>
                            <p className="mt-1 text-sm text-white/78">{activeInvestorSignal.freshnessLabel}</p>
                          </div>
                        ) : null}
                      </div>
                      {activeInvestorSignal.explanation ? (
                        <p data-testid="watchlist-investor-signal-explanation">{activeInvestorSignal.explanation}</p>
                      ) : null}
                      {activeInvestorSignal.reasonCodes.length ? (
                        <div className="space-y-1.5">
                          <p className="text-[11px] uppercase tracking-[0.18em] text-white/38">{copy.investorSignalReasons}</p>
                          <div className="flex min-w-0 flex-wrap gap-1.5">
                            {activeInvestorSignal.reasonCodes.map((reason) => (
                              <TerminalChip key={reason} variant="neutral">{reason}</TerminalChip>
                            ))}
                          </div>
                        </div>
                      ) : null}
                      {activeInvestorSignal.contradictionCodes.length ? (
                        <div className="space-y-1.5">
                          <p className="text-[11px] uppercase tracking-[0.18em] text-white/38">{copy.investorSignalContradictions}</p>
                          <div className="flex min-w-0 flex-wrap gap-1.5">
                            {activeInvestorSignal.contradictionCodes.map((reason) => (
                              <TerminalChip key={reason} variant="caution">{reason}</TerminalChip>
                            ))}
                          </div>
                        </div>
                      ) : null}
                    </div>
                  </DenseSecondaryDisclosure>
                ) : null}

                <LeveragedEtfMapper
                  defaultUnderlyingSymbol={activeItem.symbol}
                  language={language}
                  className="pt-4"
                />

                <DenseSecondaryDisclosure
                  data-testid="watchlist-data-notes"
                  variant="row"
                  title={language === 'zh' ? '数据备注' : 'Data notes'}
                  summary={language === 'zh' ? '默认收起' : 'Collapsed by default'}
                  className="pt-4"
                >
                  <div className="space-y-3 text-xs leading-5 text-white/62">
                    <p>{formatWatchlistOrigin(activeItem.source, language)}</p>
                    {activeSavedNote ? (
                      <div data-testid="watchlist-saved-note" className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-2">
                        <p className="text-[11px] text-white/40">{language === 'zh' ? '保存备注' : 'Observation note'}</p>
                        <p className="mt-1 whitespace-pre-wrap break-words text-white/72">{activeSavedNote}</p>
                      </div>
                    ) : null}
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
                      variant="compact"
                      onClick={() => navigate(buildStockStructurePath(activeItem, language))}
                    >
                      <Search className="h-3.5 w-3.5" />
                      {language === 'zh' ? '结构' : 'Structure'}
                    </TerminalButton>
                    <TerminalButton
                      type="button"
                      variant="compact"
                      onClick={() => navigate(buildScannerPath(activeItem, language))}
                    >
                      <RefreshCw className="h-3.5 w-3.5" />
                      {language === 'zh' ? '扫描器' : 'Scanner'}
                    </TerminalButton>
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

        {!isWatchlistEmptyWorkspace ? (
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
          <div className="border-t border-[color:var(--wolfy-divider)]">
            <WatchlistResearchQueuePanel
              queue={researchPriorityQueue}
              language={language}
            />
          </div>
        </div>
        ) : null}
      </DenseTableShell>
      </ConsumerWorkspacePageShell>
    </ConsumerWorkspaceScope>
  );
};

export default WatchlistPage;
