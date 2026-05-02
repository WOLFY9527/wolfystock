import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  BarChart3,
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
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { watchlistApi } from '../api/watchlist';
import { AuthGuardOverlay } from '../components/auth/AuthGuardOverlay';
import { ApiErrorAlert, Input, SectionShell, Select } from '../components/common';
import { useI18n } from '../contexts/UiLanguageContext';
import { useProductSurface } from '../hooks/useProductSurface';
import type { WatchlistItem } from '../types/watchlist';
import { buildLocalizedPath } from '../utils/localeRouting';

type SortKey = 'newest' | 'scannerScore' | 'symbol' | 'market';
type Notice = { tone: 'success' | 'warning' | 'danger'; message: string } | null;

const ACTION_BUTTON_CLASS = 'inline-flex h-8 items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 text-xs font-medium text-white/70 transition hover:bg-white/10 hover:text-white disabled:cursor-not-allowed disabled:opacity-45';
const ICON_BUTTON_CLASS = 'inline-flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-white/[0.04] text-white/55 transition hover:bg-white/10 hover:text-white disabled:cursor-not-allowed disabled:opacity-45';

function normalizeText(value?: string | null): string {
  return String(value || '').trim();
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
      search: 'Search',
      searchPlaceholder: 'Symbol or name',
      market: 'Market',
      source: 'Source',
      context: 'Theme / universe',
      sort: 'Sort',
      all: 'All',
      newest: 'Newest',
      scannerScore: 'Scanner score',
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
    subtitle: 'Track scanner candidates and continue analysis/backtesting',
    totalTracked: '追踪总数',
    marketsRepresented: '覆盖市场',
    scannerSourced: '扫描来源',
    recentlyAdded: '近期新增',
    search: '搜索',
    searchPlaceholder: '代码或名称',
    market: '市场',
    source: '来源',
    context: '主题 / 候选范围',
    sort: '排序',
    all: '全部',
    newest: '最新',
    scannerScore: '扫描分数',
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
  const [sortKey, setSortKey] = useState<SortKey>('newest');
  const [pendingAnalyzeId, setPendingAnalyzeId] = useState<number | null>(null);
  const [pendingRemoveId, setPendingRemoveId] = useState<number | null>(null);
  const [isRefreshingScores, setRefreshingScores] = useState(false);
  const [refreshStatus, setRefreshStatus] = useState<{ enabled: boolean; usTime: string; cnTime: string; hkTime: string } | null>(null);
  const [copiedId, setCopiedId] = useState<number | null>(null);

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
    return {
      total: items.length,
      markets: markets.size,
      scannerSourced,
      recent: items.filter(isRecentlyAdded).length,
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
      return matchesSearch && matchesMarket && matchesSource && matchesContext;
    });

    return rows.sort((left, right) => {
      if (sortKey === 'symbol') return left.symbol.localeCompare(right.symbol);
      if (sortKey === 'market') {
        const marketCompare = normalizeText(left.market).localeCompare(normalizeText(right.market));
        return marketCompare || left.symbol.localeCompare(right.symbol);
      }
      if (sortKey === 'scannerScore') {
        const leftScore = left.scannerScore ?? Number.NEGATIVE_INFINITY;
        const rightScore = right.scannerScore ?? Number.NEGATIVE_INFINITY;
        return rightScore - leftScore || (left.scannerRank ?? 9999) - (right.scannerRank ?? 9999);
      }
      return getItemTime(right) - getItemTime(left);
    });
  }, [contextFilter, items, marketFilter, query, sortKey, sourceFilter]);

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

  const handleRefreshScores = useCallback(async () => {
    setRefreshingScores(true);
    setNotice(null);
    try {
      const response = await watchlistApi.refreshScores({ force: true });
      const listResponse = await watchlistApi.listWatchlistItems();
      setItems(listResponse.items || []);
      setNotice({
        tone: response.failedCount > 0 ? 'warning' : 'success',
        message: `${copy.scoreRefreshComplete} ${response.updatedCount}/${response.updatedCount + response.skippedCount + response.failedCount}`,
      });
    } catch (err) {
      setNotice({ tone: 'danger', message: getParsedApiError(err).message });
    } finally {
      setRefreshingScores(false);
    }
  }, [copy.scoreRefreshComplete]);

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

  return (
    <main className="w-full flex-1 px-4 py-6 md:px-8 xl:px-12" data-testid="watchlist-page">
      <div className="flex w-full flex-col gap-5">
        <header className="flex flex-col gap-3 rounded-[24px] border border-white/5 bg-white/[0.02] px-5 py-5 backdrop-blur-sm md:flex-row md:items-end md:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase tracking-[0.24em] text-white/35">Scanner candidates</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-normal text-white md:text-3xl">{copy.title}</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-white/50">{copy.subtitle}</p>
          </div>
          <Link
            to={buildLocalizedPath('/scanner', language)}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-4 text-sm font-medium text-white/70 transition hover:bg-white/10 hover:text-white"
          >
            <ExternalLink className="h-4 w-4" />
            {copy.openScanner}
          </Link>
        </header>

        <section className="grid grid-cols-2 gap-3 lg:grid-cols-4" aria-label="watchlist summary">
          {[
            { label: copy.totalTracked, value: summary.total },
            { label: copy.marketsRepresented, value: summary.markets },
            { label: copy.scannerSourced, value: summary.scannerSourced },
            { label: copy.recentlyAdded, value: summary.recent },
          ].map((card) => (
            <div key={card.label} className="rounded-[20px] border border-white/5 bg-white/[0.02] px-4 py-4">
              <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-white/35">{card.label}</p>
              <p className="mt-3 text-2xl font-semibold text-white">{card.value}</p>
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
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2 text-sm backdrop-blur-md">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <span className="text-[10px] font-bold uppercase tracking-widest text-white/40">{copy.autoRefresh}</span>
              <span className="rounded-lg border border-emerald-400/20 bg-emerald-400/10 px-2 py-1 font-mono text-[11px] text-emerald-100">
                {refreshStatus?.enabled ? copy.enabled : '--'}
              </span>
              <span className="truncate font-mono text-[11px] text-white/45">
                US {refreshStatus?.usTime || '08:45'} / CN {refreshStatus?.cnTime || '09:00'} / HK {refreshStatus?.hkTime || '09:00'}
              </span>
            </div>
            <button
              type="button"
              onClick={() => void handleRefreshScores()}
              disabled={isRefreshingScores}
              className="inline-flex h-8 shrink-0 items-center gap-2 rounded-lg border border-cyan-300/20 bg-cyan-300/10 px-3 text-xs font-semibold text-cyan-100 transition hover:border-cyan-200/40 hover:bg-cyan-300/15 disabled:cursor-wait disabled:opacity-45"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isRefreshingScores ? 'animate-spin' : ''}`} />
              {isRefreshingScores ? copy.refreshingScores : copy.refreshScores}
            </button>
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
            <Input
              label={copy.search}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={copy.searchPlaceholder}
              trailingAction={<Search className="h-4 w-4 text-white/35" />}
            />
            <Select label={copy.market} value={marketFilter} onChange={setMarketFilter} options={marketOptions} />
            <Select label={copy.source} value={sourceFilter} onChange={setSourceFilter} options={sourceOptions} />
            <Select label={copy.context} value={contextFilter} onChange={setContextFilter} options={contextOptions} />
            <Select
              label={copy.sort}
              value={sortKey}
              onChange={(value) => setSortKey(value as SortKey)}
              options={[
                { value: 'newest', label: copy.newest },
                { value: 'scannerScore', label: copy.scannerScore },
                { value: 'symbol', label: copy.symbol },
                { value: 'market', label: copy.market },
              ]}
            />
          </div>

          <div className="overflow-x-auto no-scrollbar rounded-2xl border border-white/5">
            <table className="min-w-[1180px] w-full text-left text-sm">
              <thead className="bg-white/[0.03] text-[11px] uppercase tracking-[0.16em] text-white/35">
                <tr>
                  <th className="px-4 py-3 font-semibold">{copy.symbol}</th>
                  <th className="px-4 py-3 font-semibold">{copy.market}</th>
                  <th className="px-4 py-3 font-semibold">{copy.name}</th>
                  <th className="px-4 py-3 font-semibold">{copy.score}</th>
                  <th className="px-4 py-3 font-semibold">{copy.rank}</th>
                  <th className="px-4 py-3 font-semibold">{copy.lastScored}</th>
                  <th className="px-4 py-3 font-semibold">{copy.source}</th>
                  <th className="px-4 py-3 font-semibold">{copy.context}</th>
                  <th className="px-4 py-3 font-semibold">{copy.added}</th>
                  <th className="px-4 py-3 font-semibold">{copy.actions}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {filteredItems.map((item) => (
                  <tr key={item.id} data-testid={`watchlist-row-${item.symbol}`} className="bg-white/[0.01] text-white/70">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Clipboard className="h-4 w-4 text-white/30" />
                        <span className="font-semibold text-white">{item.symbol}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">{formatMarket(item.market)}</td>
                    <td className="px-4 py-3">{item.name || '--'}</td>
                    <td className="px-4 py-3">
                      <span className="inline-flex min-w-[3.5rem] justify-center rounded-full border border-sky-400/20 bg-sky-400/10 px-2 py-1 text-xs font-semibold text-sky-100">
                        {formatScore(item.scannerScore)}
                      </span>
                    </td>
                    <td className="px-4 py-3">{item.scannerRank ? `#${item.scannerRank}` : '--'}</td>
                    <td className="px-4 py-3">
                      <div className="flex max-w-[180px] flex-col gap-1">
                        <span className="truncate font-mono text-xs text-white/60">{formatDateTime(item.lastScoredAt, language)}</span>
                        <span className={`w-fit rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-widest ${
                          item.scoreStatus === 'fresh'
                            ? 'border-emerald-400/20 bg-emerald-400/10 text-emerald-100'
                            : item.scoreStatus === 'stale'
                              ? 'border-amber-400/20 bg-amber-400/10 text-amber-100'
                              : 'border-white/10 bg-white/[0.04] text-white/40'
                        }`} title={item.scoreError || item.scoreReason || undefined}>
                          {item.scoreStatus === 'fresh' ? copy.fresh : item.scoreStatus === 'stale' ? copy.stale : '--'}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3">{item.source || '--'}</td>
                    <td className="px-4 py-3">
                      <div className="flex max-w-[220px] flex-wrap gap-1.5">
                        {item.themeId ? <span className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-1 text-xs text-white/60">{item.themeId}</span> : null}
                        {item.universeType ? <span className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-1 text-xs text-white/60">{item.universeType}</span> : null}
                        {!item.themeId && !item.universeType ? '--' : null}
                      </div>
                    </td>
                    <td className="px-4 py-3">{formatDateTime(item.createdAt || item.updatedAt, language)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          className={ACTION_BUTTON_CLASS}
                          onClick={() => void handleAnalyze(item)}
                          disabled={pendingAnalyzeId === item.id}
                        >
                          <Play className="h-3.5 w-3.5" />
                          {pendingAnalyzeId === item.id ? copy.analyzing : copy.analyze}
                        </button>
                        <Link className={ACTION_BUTTON_CLASS} to={buildBacktestPath(item, language)}>
                          <BarChart3 className="h-3.5 w-3.5" />
                          {copy.backtest}
                        </Link>
                        <button
                          type="button"
                          aria-label={`${copy.copySymbol} ${item.symbol}`}
                          title={copiedId === item.id ? copy.copied : copy.copySymbol}
                          className={ICON_BUTTON_CLASS}
                          onClick={() => void handleCopy(item)}
                        >
                          <Copy className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          aria-label={`${copy.remove} ${item.symbol}`}
                          className={ICON_BUTTON_CLASS}
                          onClick={() => void handleRemove(item)}
                          disabled={pendingRemoveId === item.id}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
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
                className="mt-5 inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-4 text-sm font-medium text-white/70 transition hover:bg-white/10 hover:text-white"
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
