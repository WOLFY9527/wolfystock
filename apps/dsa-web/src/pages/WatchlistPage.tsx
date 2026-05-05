import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  BarChart3,
  CheckSquare,
  Clipboard,
  Copy,
  ExternalLink,
  Play,
  RefreshCw,
  Search,
  Trash2,
} from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { analysisApi, DuplicateTaskError } from '../api/analysis';
import { backtestApi } from '../api/backtest';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { watchlistApi } from '../api/watchlist';
import { AuthGuardOverlay } from '../components/auth/AuthGuardOverlay';
import { ApiErrorAlert, Badge, Button, Input, SectionShell, Select } from '../components/common';
import { StatusBadge } from '../components/ui/StatusBadge';
import { useI18n } from '../contexts/UiLanguageContext';
import { useProductSurface } from '../hooks/useProductSurface';
import type { WatchlistItem } from '../types/watchlist';
import type { RuleBacktestRunResponse } from '../types/backtest';
import { describeBooleanEnabled, describeDisplayStatus, type DisplayStatusTone } from '../utils/displayStatus';
import { buildLocalizedPath } from '../utils/localeRouting';

type SortKey = 'newest' | 'scannerScore' | 'backtestReturn' | 'historicalHitRate' | 'recentlyScored' | 'recentlyBacktested' | 'symbol' | 'market';
type EvidenceFilter = 'all' | 'hasScanner' | 'hasBacktest' | 'scannerSelected' | 'staleIntelligence';
type BatchStatus = 'requested' | 'running' | 'completed' | 'failed' | 'skipped';
type Notice = { tone: 'success' | 'warning' | 'danger'; message: string } | null;
type FailureReason = '数据不足' | '行情缺失' | '服务暂不可用' | '回测失败' | '扫描失败' | '超时' | '未知错误';
type BatchFailure = { label: FailureReason; detail?: string };
type BatchProgress = {
  kind: 'scan' | 'backtest';
  total: number;
  completed: number;
  succeeded: number;
  failed: number;
  currentSymbol: string | null;
  failures: Record<string, BatchFailure>;
} | null;

const ROW_SELECTION_BUTTON_CLASS = 'inline-flex h-[32px] w-[32px] shrink-0 items-center justify-center rounded-lg border transition hover:border-white/30 hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/35';
const WATCHLIST_BUTTON_CLASS = 'border-white/10 bg-white/[0.04] text-white/70 hover:bg-white/10 hover:text-white';
const WATCHLIST_ICON_BUTTON_CLASS = 'h-[36px] min-h-[36px] w-[36px] px-0 text-white/55 sm:h-[34px] sm:min-h-[34px] sm:w-[34px]';
const WATCHLIST_LINK_BUTTON_CLASS = 'inline-flex min-h-[34px] items-center justify-center gap-2 rounded-[var(--theme-button-radius)] border border-white/10 bg-white/[0.04] px-3 text-[0.72rem] font-normal text-white/70 whitespace-nowrap transition-[color,background-color,border-color,opacity,transform] duration-200 hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring)]';
const WATCHLIST_BADGE_CLASS = 'border-white/10 bg-white/[0.04] text-white/60';

function normalizeText(value?: string | null): string {
  return String(value || '').trim();
}

function displayBadgeVariant(tone: DisplayStatusTone): React.ComponentProps<typeof Badge>['variant'] {
  if (tone === 'success') return 'success';
  if (tone === 'warning') return 'warning';
  if (tone === 'danger') return 'danger';
  if (tone === 'info') return 'info';
  return 'default';
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

function formatScannerStatus(item: WatchlistItem): string {
  const status = normalizeText(item.intelligence?.scanner?.status || item.scoreStatus).toLowerCase();
  const simulationStatus = normalizeText(item.intelligence?.strategySimulation?.status).toLowerCase();
  if (['selected', 'verified', 'ready', 'fresh'].includes(status)) return '已验证';
  if (['preview', 'candidate', 'passed'].includes(status)) return '通过筛选';
  if (['rejected', 'not_selected', 'failed_filter'].includes(status)) return '未通过';
  if (['data_failed', 'provider_down', 'provider_error', 'error', 'failed', 'critical'].includes(status)) return '扫描失败';
  if (simulationStatus === 'insufficient_history' || status === 'insufficient_history') return '数据不足';
  if (!hasScannerEvidence(item)) return '未扫描';
  return '通过筛选';
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
      subtitle: 'Track scanner candidates and continue analysis/backtesting',
      totalTracked: 'Total tracked',
      marketsRepresented: 'Markets represented',
      scannerSourced: 'Scanner-sourced',
      recentlyAdded: 'Recently added',
      trackedSymbols: 'Tracked symbols',
      scannerCoverage: 'Scanner results',
      backtestCoverage: 'Backtest results',
      staleCoverage: 'Stale intelligence',
      failureCoverage: 'Failed / no data',
      latestUpdate: 'Latest update',
      search: 'Search',
      searchPlaceholder: 'Symbol or name',
      market: 'Market',
      source: 'Source',
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
      staleIntelligence: 'Stale intelligence',
      intelligence: 'Intelligence',
      noEvidence: 'No strategy evidence',
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
      refreshScores: 'Refresh scores',
      refreshingScores: 'Refreshing...',
      autoRefresh: 'Pre-open auto update',
      enabled: 'Enabled',
      stale: 'Stale',
      fresh: 'Fresh',
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
      emptyBody: 'Add candidates from Scanner.',
      openScanner: 'Open Scanner',
      tableTitle: 'Tracked candidates',
      tableDescription: 'Scanner context is kept with each candidate so you can re-run analysis or hand it to Backtest.',
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
    subtitle: '跟踪扫描候选，继续分析与回测',
    totalTracked: '追踪总数',
    marketsRepresented: '覆盖市场',
    scannerSourced: '扫描来源',
    recentlyAdded: '近期新增',
    trackedSymbols: '观察标的数',
    scannerCoverage: '已有扫描结果',
    backtestCoverage: '已有回测结果',
    staleCoverage: '情报过期',
    failureCoverage: '失败 / 无数据',
    latestUpdate: '最近更新时间',
    search: '搜索',
    searchPlaceholder: '代码或名称',
    market: '市场',
    source: '来源',
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
    staleIntelligence: '证据过期',
    intelligence: '策略证据',
    noEvidence: '暂无策略证据',
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
    refreshScores: '刷新评分',
    refreshingScores: '刷新中...',
    autoRefresh: '开盘前自动更新',
    enabled: '已启用',
    stale: '过期',
    fresh: '最新',
    added: '加入时间',
    actions: '操作',
    analyze: '分析',
    analyzing: '分析中...',
    backtest: '回测',
    remove: '移除',
    removing: '移除中...',
    copySymbol: '复制代码',
    copied: '已复制',
    emptyTitle: '暂无追踪候选。',
    emptyBody: '从扫描器添加候选到观察列表。',
    openScanner: '打开扫描器',
    tableTitle: '追踪候选',
    tableDescription: '每个候选都保留扫描上下文，可继续分析或交接到回测。',
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

  const marketOptions = useMemo(() => {
    const markets = Array.from(new Set(items.map((item) => normalizeText(item.market).toLowerCase()).filter(Boolean))).sort();
    return [
      { value: 'all', label: copy.all },
      ...markets.map((market) => ({ value: market, label: formatMarket(market) })),
    ];
  }, [copy.all, items]);

  const sourceOptions = useMemo(() => {
    const sources = Array.from(new Set(items.map((item) => normalizeText(item.source).toLowerCase()).filter(Boolean))).sort();
    return [
      { value: 'all', label: copy.all },
      ...sources.map((source) => ({ value: source, label: source })),
    ];
  }, [copy.all, items]);

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

  const selectedItems = useMemo(
    () => filteredItems.filter((item) => selectedIds.has(item.id)),
    [filteredItems, selectedIds],
  );
  const actionItems = useSelectedScope && selectedItems.length > 0 ? selectedItems : filteredItems;
  const actionScopeLabel = actionItems.length === 0
    ? copy.emptyFilteredSet
    : `${useSelectedScope && selectedItems.length > 0 ? copy.scopeSelected : copy.scopeFiltered} ${actionItems.length} ${language === 'zh' ? '个标的' : 'symbols'}`;
  const isActionDisabled = actionItems.length === 0 || isBatchBacktesting || isBatchScanning;

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

  const handleRemove = useCallback(async (item: WatchlistItem) => {
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
      const [listResponse, statusResponse] = await Promise.all([
        watchlistApi.listWatchlistItems(),
        watchlistApi.getRefreshStatus().catch(() => null),
      ]);
      setItems(listResponse.items || []);
      setRefreshStatus(statusResponse);
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
    return (
      <div className="w-full h-full flex flex-col items-center justify-center">
        <AuthGuardOverlay moduleName={copy.signInModule} />
      </div>
    );
  }

  const noticeClassName = notice?.tone === 'danger'
    ? 'border-red-400/20 bg-red-400/10 text-red-100'
    : notice?.tone === 'warning'
      ? 'border-amber-400/20 bg-amber-400/10 text-amber-100'
      : 'border-emerald-400/20 bg-emerald-400/10 text-emerald-100';
  const autoRefreshStatus = describeBooleanEnabled(refreshStatus?.enabled, { language });

  return (
    <main className="w-full flex-1 px-4 py-6 xl:px-8" data-testid="watchlist-page">
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-5">
        <header className="flex flex-col gap-3 rounded-[24px] border border-white/5 bg-white/[0.02] px-5 py-5 backdrop-blur-sm md:flex-row md:items-end md:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-bold tracking-[0.24em] text-white/35">{language === 'zh' ? '扫描候选' : 'Scanner candidates'}</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-normal text-white md:text-3xl">{copy.title}</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-white/50">{copy.subtitle}</p>
          </div>
          <Link
            to={buildLocalizedPath('/scanner', language)}
            className={`${WATCHLIST_LINK_BUTTON_CLASS} h-10 px-4 text-sm font-medium`}
          >
            <ExternalLink className="h-4 w-4" />
            {copy.openScanner}
          </Link>
        </header>

        <section className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6" aria-label="watchlist summary">
          {[
            { label: copy.trackedSymbols, value: summary.total },
            { label: copy.scannerCoverage, value: summary.scannerResults || (summary.total ? copy.noEvidence : copy.noEvidence) },
            { label: copy.backtestCoverage, value: summary.backtestResults || (summary.total ? copy.noEvidence : copy.noEvidence) },
            { label: copy.staleCoverage, value: summary.stale },
            { label: copy.failureCoverage, value: summary.failedOrNoData },
            { label: copy.latestUpdate, value: summary.latestTime ? formatDateTime(summary.latestTime, language) : (language === 'zh' ? '暂无情报' : 'No intelligence') },
          ].map((card) => (
            <div key={card.label} className="rounded-[20px] border border-white/5 bg-white/[0.02] px-4 py-4">
              <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-white/35">{card.label}</p>
              <p className="mt-3 truncate text-2xl font-semibold text-white">{card.value}</p>
            </div>
          ))}
        </section>

        {notice ? (
          <div className={`rounded-2xl border px-4 py-3 text-sm ${noticeClassName}`} role="status">
            {notice.message}
          </div>
        ) : null}

        {error ? <ApiErrorAlert error={error} /> : null}

        <SectionShell
          title={copy.tableTitle}
          description={copy.tableDescription}
          contentClassName="space-y-4"
        >
          <div className="flex min-w-0 flex-wrap items-center justify-between gap-3 rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2 text-sm backdrop-blur-md">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <span className="text-[10px] font-bold uppercase tracking-widest text-white/40">{copy.autoRefresh}</span>
              <Badge variant={displayBadgeVariant(autoRefreshStatus.tone)} className="font-mono">
                {refreshStatus ? autoRefreshStatus.label : '--'}
              </Badge>
              <span className="truncate font-mono text-[11px] text-white/45">
                US {refreshStatus?.usTime || '08:45'} / CN {refreshStatus?.cnTime || '09:00'} / HK {refreshStatus?.hkTime || '09:00'}
              </span>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="shrink-0 border-cyan-300/20 bg-cyan-300/10 text-cyan-100 hover:border-cyan-200/40 hover:bg-cyan-300/15 disabled:cursor-wait"
              onClick={() => void handleRefreshScores()}
              disabled={isRefreshingScores}
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isRefreshingScores ? 'animate-spin' : ''}`} />
              {isRefreshingScores ? copy.refreshingScores : copy.refreshScores}
            </Button>
          </div>
          <div
            data-testid="watchlist-filter-grid"
            className="grid min-w-0 grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-6"
          >
            <Input
              label={copy.search}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={copy.searchPlaceholder}
              containerClassName="min-w-0"
              trailingAction={<Search className="h-4 w-4 text-white/35" />}
            />
            <Select label={copy.market} value={marketFilter} onChange={setMarketFilter} options={marketOptions} className="min-w-0" />
            <Select label={copy.source} value={sourceFilter} onChange={setSourceFilter} options={sourceOptions} className="min-w-0" />
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

          <div data-testid="watchlist-command-bar" className="flex min-w-0 flex-wrap items-center justify-between gap-3 rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2 backdrop-blur-md">
            <div className="min-w-0 space-y-1">
              <p className="text-[10px] font-bold uppercase tracking-widest text-white/40">{copy.batchBacktestLabel}</p>
              <p data-testid="watchlist-action-scope" className="truncate text-xs text-white/45">{actionScopeLabel} · {language === 'zh' ? '并发 2' : 'concurrency 2'}</p>
              {actionItems.length === 0 ? <p className="text-xs text-amber-300">{copy.noMatchedSymbols}</p> : null}
              {batchProgress ? (
                <p data-testid="watchlist-batch-progress" className="text-xs text-white/55">
                  {batchProgress.completed} / {batchProgress.total}
                  {batchProgress.currentSymbol ? ` · ${batchProgress.currentSymbol}` : ''}
                  {' · '}
                  {language === 'zh' ? '成功' : 'Success'} {batchProgress.succeeded}
                  {' · '}
                  {language === 'zh' ? '失败' : 'Failed'} {batchProgress.failed}
                </p>
              ) : null}
            </div>
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className={WATCHLIST_BUTTON_CLASS}
                onClick={() => void handleRefreshScores(actionItems)}
                disabled={isActionDisabled}
              >
                <RefreshCw className={`h-3.5 w-3.5 ${isBatchScanning ? 'animate-spin' : ''}`} />
                {copy.batchScanFilter}
              </Button>
              <Button
                type="button"
                variant="gradient"
                size="sm"
                glow
                onClick={() => void handleBatchBacktestCurrentFilter()}
                disabled={isActionDisabled}
              >
                <BarChart3 className="h-3.5 w-3.5" />
                {isBatchBacktesting ? copy.batchBacktesting : copy.batchBacktestFilter}
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className={WATCHLIST_BUTTON_CLASS}
                aria-pressed={useSelectedScope && selectedItems.length > 0}
                onClick={() => setUseSelectedScope((current) => selectedItems.length > 0 ? !current : current)}
                disabled={selectedItems.length === 0}
              >
                <CheckSquare className="h-3.5 w-3.5" />
                {copy.selectedOnly}
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className={WATCHLIST_BUTTON_CLASS}
                onClick={() => {
                  setSelectedIds(new Set());
                  setUseSelectedScope(false);
                }}
                disabled={selectedIds.size === 0}
              >
                {copy.clearSelection}
              </Button>
              <Button type="button" variant="ghost" size="sm" className={WATCHLIST_BUTTON_CLASS} onClick={() => void handleRefreshIntelligence()}>
                <RefreshCw className="h-3.5 w-3.5" />
                {copy.refreshIntelligence}
              </Button>
            </div>
          </div>

          <div className="overflow-x-auto no-scrollbar rounded-2xl border border-white/5">
            <table className="min-w-[1420px] w-full text-left text-sm">
              <thead className="bg-white/[0.03] text-[11px] uppercase tracking-[0.16em] text-white/35">
                <tr>
                  <th className="px-4 py-3 font-semibold">{copy.symbol}</th>
                  <th className="px-4 py-3 font-semibold">{copy.market}</th>
                  <th className="px-4 py-3 font-semibold">{copy.name}</th>
                  <th className="px-4 py-3 font-semibold">{copy.score}</th>
                  <th className="px-4 py-3 font-semibold">{copy.rank}</th>
                  <th className="px-4 py-3 font-semibold">{copy.lastScored}</th>
                  <th className="px-4 py-3 font-semibold">{copy.intelligence}</th>
                  <th className="px-4 py-3 font-semibold">{copy.source}</th>
                  <th className="px-4 py-3 font-semibold">{copy.context}</th>
                  <th className="px-4 py-3 font-semibold">{copy.added}</th>
                  <th className="px-4 py-3 font-semibold">{copy.actions}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {filteredItems.map((item) => {
                  const scanner = item.intelligence?.scanner;
                  const strategySimulation = item.intelligence?.strategySimulation;
                  const backtest = item.intelligence?.backtest;
                  const score = getScannerScore(item);
                  const hitRate = strategySimulation?.hitRate;
                  const avgForward = strategySimulation?.avgForwardReturnPct;
                  const returnPct = backtest?.totalReturnPct;
                  const hasAnyEvidence = hasScannerEvidence(item)
                    || strategySimulation?.status === 'ready'
                    || hasBacktestEvidence(item);
                  const batchStatus = batchStatuses[item.symbol];
                  const batchFailure = batchFailures[item.symbol];
                  const scannerFailure = item.scoreError || scanner?.reason
                    ? sanitizeFailureReason(item.scoreError || scanner?.reason || '', '扫描失败')
                    : null;
                  const latestTime = getLatestIntelligenceTime(item);
                    const scannerStatusLabel = formatScannerStatus(item);
                    const backtestStatusLabel = formatBacktestStatus(item, batchFailure);
                    const scoreFreshnessStatus = item.scoreStatus === 'fresh'
                      ? 'success'
                      : item.scoreStatus === 'stale'
                        ? 'warning'
                        : 'unknown';
                    const scannerStatus = scannerStatusLabel === '扫描失败'
                      ? 'failed'
                      : scannerStatusLabel === '已验证' || scannerStatusLabel === '通过筛选'
                        ? 'info'
                        : 'unknown';
                    const backtestStatus = backtestStatusLabel === '已回测'
                      ? 'success'
                      : ['回测失败', '行情缺失', '服务暂不可用', '超时'].includes(backtestStatusLabel)
                        ? 'failed'
                        : 'unknown';
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
                  return (
                  <tr key={item.id} data-testid={`watchlist-row-${item.symbol}`} className="bg-white/[0.01] text-white/70">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
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
                        <Clipboard className="h-4 w-4 text-white/30" />
                        <span className="font-semibold text-white">{item.symbol}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">{formatMarket(item.market)}</td>
                    <td className="px-4 py-3">{item.name || '--'}</td>
                    <td className="px-4 py-3">
                        <Badge variant="info" className="min-w-[3.5rem] font-mono font-semibold text-sky-100">
                          {formatScore(score)}
                        </Badge>
                    </td>
                    <td className="px-4 py-3">{item.scannerRank ? `#${item.scannerRank}` : '--'}</td>
                    <td className="px-4 py-3">
                      <div className="flex max-w-[180px] flex-col gap-1">
                        <span className="truncate font-mono text-xs text-white/60">{formatDateTime(item.lastScoredAt, language)}</span>
                          <StatusBadge status={scoreFreshnessStatus} label={formatFreshness(item.lastScoredAt || scanner?.lastScannedAt)} variant="soft" size="sm" className="w-fit uppercase tracking-widest" />
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex max-w-[420px] flex-wrap items-center gap-1.5 text-[11px]">
                          {!hasAnyEvidence ? (
                            <Badge variant="default" className="border-white/10 bg-white/[0.04] text-white/40">{copy.noEvidence}</Badge>
                          ) : null}
                          <StatusBadge status={scannerStatus} label={scannerStatusLabel} variant="soft" size="sm" />
                          {scannerStatusLabel === '扫描失败' && scannerFailure ? (
                            <StatusBadge status="failed" label={scannerFailure.label} variant="soft" size="sm" />
                          ) : null}
                          {score !== null ? (
                            <Badge variant="info" className="font-mono text-sky-100">{language === 'zh' ? '分数' : 'SCORE'} {formatScore(score)}</Badge>
                          ) : null}
                          {(scanner?.lastRank ?? item.scannerRank) ? <Badge variant="default" className={WATCHLIST_BADGE_CLASS}>{language === 'zh' ? '排名' : 'Rank'} #{scanner?.lastRank ?? item.scannerRank}</Badge> : null}
                          {scanner?.reason && !['provider_down', 'provider_error', 'critical', 'debug', 'unknown'].some((token) => scanner.reason?.toLowerCase().includes(token)) ? (
                            <Badge variant="default" className="max-w-[180px] justify-start truncate border-white/10 bg-white/[0.04] text-white/55">{scanner.reason}</Badge>
                          ) : null}
                          <Badge variant="default" className={WATCHLIST_BADGE_CLASS}>{formatFreshness(latestTime)}</Badge>
                          {typeof avgForward === 'number' || typeof hitRate === 'number' ? (
                            <Badge variant="default" className={`border-white/10 bg-white/[0.04] font-mono ${
                              (avgForward ?? 0) >= 0
                                ? 'text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.4)]'
                                : 'text-rose-400 drop-shadow-[0_0_8px_rgba(251,113,133,0.4)]'
                            }`}>
                              HIST {formatPct(avgForward)} · HIT {typeof hitRate === 'number' ? `${Math.round(hitRate * 100)}%` : '--'}
                            </Badge>
                          ) : null}
                          <StatusBadge status={backtestStatus} label={backtestStatusLabel} variant="soft" size="sm" />
                          {hasBacktestMetrics(item) ? (
                            <>
                              <Badge variant="default" className={`border-white/10 bg-white/[0.04] font-mono ${
                                (returnPct ?? 0) >= 0
                                  ? 'text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.4)]'
                                  : 'text-rose-400 drop-shadow-[0_0_8px_rgba(251,113,133,0.4)]'
                              }`}>
                                {language === 'zh' ? '收益' : 'Return'} {formatPct(returnPct)} · {language === 'zh' ? '回撤' : 'DD'} {formatPct(backtest?.maxDrawdownPct)} · Sharpe {formatRatio(backtest?.sharpe)} · {language === 'zh' ? '交易' : 'Trades'} {backtest?.tradeCount ?? '--'}
                              </Badge>
                              {backtest?.lastResultId != null ? (
                                <Link className={`${WATCHLIST_LINK_BUTTON_CLASS} min-h-6 px-2 py-0.5 font-mono text-[11px] text-white/55`} to={buildLocalizedPath(`/backtest/results/${backtest.lastResultId}`, language)}>
                                  {copy.resultPrefix} {backtest.lastResultId}
                                </Link>
                              ) : null}
                            </>
                          ) : null}
                          {batchFailure?.detail ? (
                            <details className="max-w-[180px] rounded-lg border border-white/10 bg-white/[0.04] px-2 py-1 text-white/45">
                              <summary className="cursor-pointer list-none">{language === 'zh' ? '开发者细节' : 'Developer details'}</summary>
                              <p className="mt-1 truncate text-[10px] text-white/35">{language === 'zh' ? '原始错误已隐藏' : 'Raw error hidden'}</p>
                            </details>
                          ) : null}
                          {batchDisplayStatus ? (
                            <Badge variant={displayBadgeVariant(batchDisplayStatus.tone)} className="font-mono">
                              {batchDisplayStatus.label}
                            </Badge>
                          ) : null}
                        </div>
                      </td>
                    <td className="px-4 py-3">{item.source || '--'}</td>
                    <td className="px-4 py-3">
                      <div className="flex max-w-[220px] flex-wrap gap-1.5">
                          {item.themeId ? <Badge variant="default" className={WATCHLIST_BADGE_CLASS}>{item.themeId}</Badge> : null}
                          {item.universeType ? <Badge variant="default" className={WATCHLIST_BADGE_CLASS}>{item.universeType}</Badge> : null}
                        {!item.themeId && !item.universeType ? '--' : null}
                      </div>
                    </td>
                    <td className="px-4 py-3">{formatDateTime(item.createdAt || item.updatedAt, language)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className={WATCHLIST_BUTTON_CLASS}
                            onClick={() => void handleAnalyze(item)}
                            disabled={pendingAnalyzeId === item.id}
                          >
                            <Play className="h-3.5 w-3.5" />
                            {pendingAnalyzeId === item.id ? copy.analyzing : copy.analyze}
                          </Button>
                          <Link className={WATCHLIST_LINK_BUTTON_CLASS} to={buildBacktestPath(item, language)}>
                            <BarChart3 className="h-3.5 w-3.5" />
                            {copy.backtest}
                          </Link>
                          <Button
                            type="button"
                            aria-label={`${copy.copySymbol} ${item.symbol}`}
                            title={copiedId === item.id ? copy.copied : copy.copySymbol}
                            variant="ghost"
                            size="sm"
                            className={`${WATCHLIST_BUTTON_CLASS} ${WATCHLIST_ICON_BUTTON_CLASS}`}
                            onClick={() => void handleCopy(item)}
                          >
                            <Copy className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            type="button"
                            aria-label={`${copy.remove} ${item.symbol}`}
                            variant="ghost"
                            size="sm"
                            className={`${WATCHLIST_BUTTON_CLASS} ${WATCHLIST_ICON_BUTTON_CLASS}`}
                            onClick={() => void handleRemove(item)}
                            disabled={pendingRemoveId === item.id}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                      </div>
                    </td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {isLoading ? (
            <div className="rounded-2xl border border-white/5 bg-white/[0.02] px-4 py-8 text-center text-sm text-white/45">
              {copy.loading}
            </div>
          ) : null}

          {!isLoading && filteredItems.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] px-5 py-10 text-center">
              <p className="text-base font-semibold text-white">{copy.emptyTitle}</p>
              <p className="mt-2 text-sm text-white/45">{copy.emptyBody}</p>
                <Link
                  to={buildLocalizedPath('/scanner', language)}
                  className={`${WATCHLIST_LINK_BUTTON_CLASS} mt-5 h-10 px-4 text-sm font-medium`}
                >
                <ExternalLink className="h-4 w-4" />
                {copy.openScanner}
              </Link>
            </div>
          ) : null}
        </SectionShell>
      </div>
    </main>
  );
};

export default WatchlistPage;
