import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Gauge, RefreshCcw, Search, Signal, SlidersHorizontal, Waves } from 'lucide-react';
import { ApiErrorAlert } from '../components/common';
import { EvidenceChips } from '../components/evidence/EvidenceChips';
import {
  ConsoleContextRail,
  DataWorkbenchFrame,
  DenseRows,
  WolfyCommandBar,
} from '../components/linear';
import { DataFreshnessBadge } from '../components/market-overview/marketOverviewPrimitives';
import {
  TerminalButton,
  TerminalChip,
  TerminalDisclosure,
  TerminalEmptyState,
  TerminalGrid,
  TerminalNestedBlock,
  TerminalNotice,
  TerminalPageHeading,
  TerminalPanel,
  TerminalSectionHeader,
} from '../components/terminal/TerminalPrimitives';
import { WideWorkspacePageShell } from '../components/layout/WideWorkspaceShell';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { marketRotationApi, type MarketRotationRadarResponse, type MarketRotationRiskLabel, type MarketRotationStage, type MarketRotationSummaryItem, type MarketRotationTheme, type MarketRotationTimeWindow } from '../api/marketRotation';
import { cn } from '../utils/cn';
import { normalizeRotationEvidence } from '../utils/evidenceDisplay';
import { sanitizeUserFacingDataIssue } from '../utils/userFacingDataIssues';

const TOP_THEME_LIMIT = 10;
const MARKET_OPTIONS = [
  { id: 'US', label: 'US' },
  { id: 'CN', label: 'A股' },
  { id: 'HK', label: 'HK' },
  { id: 'CRYPTO', label: 'Crypto' },
] as const;

const STAGE_LABELS: Record<MarketRotationStage, string> = {
  early_watch: '早期观察',
  confirmed_rotation: '确认轮动',
  extended_watch: '延展观察',
  cooling_watch: '降温观察',
  weak_or_no_signal: '信号较弱',
};

const RISK_LABELS: Record<MarketRotationRiskLabel, string> = {
  gap_fade_risk: '高开回落风险',
  thin_breadth: '广度偏薄',
  single_name_driven: '单一龙头驱动',
  stale_or_incomplete_windows: '时窗缺失/过期',
};

const TAXONOMY_PLACEHOLDERS = ['主题', '行业', '概念', 'ETF代理'];

type Bucket = {
  id: string;
  title: string;
  tone: string;
  items: MarketRotationTheme[];
  fallback: string;
};

type DataStateFields = {
  freshness?: MarketRotationTheme['freshness'];
  isFallback?: boolean;
  isStale?: boolean;
};

function scoreTone(score: number): string {
  if (score >= 75) {
    return 'text-emerald-300 drop-shadow-[0_0_10px_rgba(52,211,153,0.34)]';
  }
  if (score >= 60) {
    return 'text-cyan-200 drop-shadow-[0_0_10px_rgba(103,232,249,0.24)]';
  }
  if (score >= 45) {
    return 'text-amber-200';
  }
  return 'text-white/45';
}

function percent(value?: number | null, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '待确认';
  }
  return `${value.toFixed(digits)}%`;
}

function signedPercent(value?: number | null, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '待确认';
  }
  return `${value >= 0 ? '+' : ''}${value.toFixed(digits)}%`;
}

function ratio(value?: number | null): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '待确认';
  }
  return `${value.toFixed(2)}x`;
}

function isTaxonomyOnlyTheme(theme?: MarketRotationTheme): boolean {
  return Boolean(theme?.staticThemeOnly || theme?.dataQuality === 'taxonomy_only');
}

function compactConfidence(value?: number | null): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '0%';
  }
  return `${Math.round(value * 100)}%`;
}

function formatThemeStage(stage?: MarketRotationStage): string {
  return stage ? STAGE_LABELS[stage] || stage : '待识别';
}

function mapDataStateLabel(theme: DataStateFields): string {
  const candidate = theme as MarketRotationTheme;
  if (isTaxonomyOnlyTheme(candidate)) {
    return candidate.confidenceLabel || '待行情确认';
  }
  if (theme.isFallback || theme.freshness === 'fallback') {
    return '备用/静态';
  }
  if (theme.isStale || theme.freshness === 'stale') {
    return '过期待复核';
  }
  if (theme.freshness === 'delayed') {
    return '延迟可用';
  }
  if (theme.freshness === 'live') {
    return '实时';
  }
  return '缓存/部分';
}

function proxyMissingReasonLabel(reason?: string | null): string {
  const labels: Record<string, string> = {
    proxy_quote_missing: '代理行情待补齐',
    proxy_stale: '代理行情过期',
    proxy_windows_missing: '代理时窗待补齐',
  };
  return reason ? labels[reason] || '代理证据待复核' : '代理可用';
}

function isInternalRotationIssue(value?: string | null): boolean {
  const normalized = String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
  return /provider|timeout|schema|debug|raw|trace|cache|not_enough|unavailable|missing|insufficient|technical_indicators|fundamentals|earnings|optional_news/.test(normalized);
}

function sanitizeRotationText(value?: string | null, fallback = '数据不足，结论仅供观察'): string {
  const text = String(value || '').trim();
  if (!text) return fallback;
  return isInternalRotationIssue(text) ? sanitizeUserFacingDataIssue(text, 'zh') : text;
}

function sanitizeRotationNotes(notes?: string[]): string[] {
  return (notes || [])
    .map((note) => sanitizeRotationText(note, ''))
    .filter((note, index, array) => Boolean(note) && array.indexOf(note) === index);
}

function proxyQualityState(theme: MarketRotationTheme): string {
  if (theme.proxyQuality?.hasMissingRequiredProxy) {
    return '代理缺口';
  }
  if (theme.proxyQuality?.hasStaleProxy) {
    return '代理过期';
  }
  const total = theme.proxyQuality?.totalProxyCount ?? Object.keys(theme.benchmarkProxies || {}).length;
  const available = theme.proxyQuality?.availableProxyCount ?? total;
  return available < total ? '部分可用' : '代理完整';
}

function isThemeStale(theme: DataStateFields): boolean {
  return Boolean(theme.isStale || theme.freshness === 'stale');
}

function summaryTitle(items: MarketRotationSummaryItem[], fallback: string): string {
  return items.length ? items.map((item) => item.name).join(' / ') : fallback;
}

function deriveTopThemes(themes: MarketRotationTheme[], limit = TOP_THEME_LIMIT): MarketRotationTheme[] {
  return [...themes]
    .sort((a, b) => {
      if (b.rotationScore !== a.rotationScore) {
        return b.rotationScore - a.rotationScore;
      }
      return b.confidence - a.confidence;
    })
    .slice(0, limit);
}

function resolveSummaryThemes(themes: MarketRotationTheme[], summaryItems: MarketRotationSummaryItem[]): MarketRotationTheme[] {
  const themeById = new Map(themes.map((theme) => [theme.id, theme]));
  return summaryItems
    .map((item) => themeById.get(item.id))
    .filter((theme): theme is MarketRotationTheme => Boolean(theme));
}

function deriveWeakeningThemes(themes: MarketRotationTheme[]): MarketRotationTheme[] {
  return [...themes]
    .filter((theme) => theme.stage === 'cooling_watch' || theme.stage === 'weak_or_no_signal' || theme.rotationScore < 50)
    .sort((a, b) => a.rotationScore - b.rotationScore)
    .slice(0, 4);
}

function deriveParticipationBuckets(themes: MarketRotationTheme[]): Bucket[] {
  const sorted = deriveTopThemes(themes, themes.length);
  const rising = sorted
    .filter((theme) => theme.rotationScore >= 62 && Number(theme.volume?.averageRelativeVolume) >= 1.05 && Number(theme.relativeStrength?.averageRelativeStrengthPercent) > 0)
    .slice(0, 4);
  const broad = sorted
    .filter((theme) => Number(theme.breadth?.percentUp) >= 70 || Number(theme.leadership?.broadParticipationPercent) >= 55)
    .slice(0, 4);
  const narrow = sorted
    .filter((theme) => Number(theme.leadership?.leadershipConcentrationPercent) >= 50 || theme.riskLabels.includes('single_name_driven') || theme.riskLabels.includes('thin_breadth'))
    .slice(0, 4);

  return [
    { id: 'rising', title: '新近走强', tone: 'text-emerald-200', items: rising, fallback: '暂无扩张确认' },
    { id: 'weakening', title: '走弱降温', tone: 'text-amber-200', items: deriveWeakeningThemes(themes), fallback: '暂无降温列表' },
    { id: 'broad', title: '广泛参与', tone: 'text-cyan-200', items: broad, fallback: '广度待补齐' },
    { id: 'narrow', title: '窄幅龙头', tone: 'text-rose-200', items: narrow, fallback: '未见明显集中' },
  ];
}

function matchesSearch(theme: MarketRotationTheme, query: string): boolean {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  const haystack = [
    theme.name,
    theme.englishName,
    theme.focus,
    theme.benchmark,
    theme.sectorBenchmark,
    ...(theme.membersConfigured || []),
    ...(theme.mappedConcepts || []),
    ...(theme.representativeLabels || []),
    ...(theme.representativeSymbols || []),
    ...(theme.leadership?.topMembers || []).map((member) => `${member.symbol} ${member.name || ''}`),
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  return haystack.includes(normalized);
}

function rotationEvidenceSummary(theme: MarketRotationTheme) {
  if (!theme.rotationStateEvidence) return null;
  return normalizeRotationEvidence({ rotationStateEvidence: theme.rotationStateEvidence });
}

function marketLabel(market: string): string {
  return MARKET_OPTIONS.find((option) => option.id === market)?.label || market;
}

const ThemeMetric: React.FC<{ label: string; value: string; tone?: string }> = ({ label, value, tone = 'text-white/78' }) => (
  <div className="min-w-0 rounded-md border border-white/[0.05] bg-black/15 px-3 py-2">
    <p className="truncate text-[10px] font-semibold text-white/38">{label}</p>
    <p className={cn('mt-1 truncate font-mono text-sm font-semibold tabular-nums', tone)}>{value}</p>
  </div>
);

const WindowChip: React.FC<{ window: MarketRotationTimeWindow }> = ({ window }) => (
  <TerminalNestedBlock className="min-w-0 px-3 py-2">
    <p className="truncate text-[10px] font-semibold text-white/38">{window.label}</p>
    <p className={cn('mt-1 truncate text-[11px] font-semibold', window.available ? 'text-cyan-100' : 'text-white/35')}>
      {window.available ? signedPercent(window.changePercent, 1) : '待补齐'}
    </p>
  </TerminalNestedBlock>
);

const RiskChip: React.FC<{ risk: MarketRotationRiskLabel }> = ({ risk }) => (
  <TerminalChip variant="caution" className="px-2 py-0.5 text-[10px] font-semibold">
    {RISK_LABELS[risk] || '风险待识别'}
  </TerminalChip>
);

const CommandBar: React.FC<{
  selectedMarket: string;
  supportedMarkets: string[];
  searchQuery: string;
  onMarketChange: (market: string) => void;
  onSearchChange: (value: string) => void;
  loading: boolean;
  freshness?: MarketRotationRadarResponse['freshness'];
  onRefresh: () => void;
}> = ({ selectedMarket, supportedMarkets, searchQuery, onMarketChange, onSearchChange, loading, freshness, onRefresh }) => (
  <WolfyCommandBar
    data-testid="rotation-radar-mode-controls"
    className="min-h-[132px] gap-y-3 sm:min-h-[118px] lg:min-h-11"
    leading={(
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <div className="inline-flex items-center gap-2 text-[10px] font-bold uppercase text-white/35">
          <SlidersHorizontal className="h-3.5 w-3.5 text-cyan-200/70" aria-hidden="true" />
          市场
        </div>
        <div className="flex min-w-0 gap-2 overflow-x-auto no-scrollbar">
          {MARKET_OPTIONS.filter((market) => !supportedMarkets.length || supportedMarkets.includes(market.id)).map((market) => (
            <TerminalButton
              key={market.id}
              type="button"
              variant="compact"
              data-testid={`rotation-market-tab-${market.id}`}
              aria-pressed={selectedMarket === market.id}
              className={cn(
                'shrink-0',
                selectedMarket === market.id
                  ? 'border-cyan-200/24 bg-cyan-200/[0.08] text-cyan-50 hover:bg-cyan-200/[0.1] hover:text-cyan-50'
                  : 'text-white/48 hover:border-white/10 hover:bg-white/[0.04] hover:text-white/75',
              )}
              onClick={() => onMarketChange(market.id)}
            >
              {market.label}
            </TerminalButton>
          ))}
        </div>
      </div>
    )}
    trailing={(
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <TerminalNestedBlock data-testid="rotation-radar-freshness" className="inline-flex items-center gap-2 px-3 py-2">
          <span className="text-[10px] font-bold uppercase text-white/35">新鲜度</span>
          <DataFreshnessBadge freshness={freshness || 'fallback'} />
        </TerminalNestedBlock>
        <TerminalButton
          variant="compact"
          className="h-10 w-10 rounded-xl px-0 py-0 text-white/50 disabled:cursor-wait disabled:text-white/30"
          onClick={onRefresh}
          disabled={loading}
          aria-label="刷新资金轮动雷达"
        >
          <RefreshCcw className={cn('h-4 w-4', loading ? 'animate-spin' : '')} aria-hidden="true" />
        </TerminalButton>
      </div>
    )}
  >
    <div className="flex min-w-0 flex-col gap-2 lg:flex-row lg:items-center lg:gap-3">
      <label className="relative min-w-0 flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/35" aria-hidden="true" />
        <input
          className="h-10 w-full rounded-lg border border-white/10 bg-black/25 py-2 pl-9 pr-3 text-sm text-white/78 outline-none transition-all placeholder:text-white/30 focus:border-cyan-200/30 focus:bg-white/[0.035]"
          value={searchQuery}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="搜索主题、英文名或成员"
        />
      </label>
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <div className="inline-flex items-center gap-2 text-[10px] font-bold uppercase text-white/35">
          <Gauge className="h-3.5 w-3.5 text-cyan-200/70" aria-hidden="true" />
          分类层级
        </div>
        {TAXONOMY_PLACEHOLDERS.map((mode, index) => (
          <TerminalButton
            key={mode}
            type="button"
            variant="compact"
            className={cn(
              'shrink-0',
              index === 0
                ? 'border-white/10 bg-white/[0.055] text-white/75 hover:bg-white/[0.055] hover:text-white/75'
                : 'cursor-default text-white/35 hover:border-white/10 hover:bg-white/[0.03] hover:text-white/35',
            )}
            disabled
          >
            {mode}
          </TerminalButton>
        ))}
      </div>
    </div>
  </WolfyCommandBar>
);

const SummaryBand: React.FC<{
  payload: MarketRotationRadarResponse;
}> = ({ payload }) => {
  const items = [
    { key: 'market', label: '市场', value: marketLabel(payload.market || 'US') },
    { key: 'source', label: '来源', value: payload.sourceLabel || '待确认' },
    { key: 'top', label: '领涨', value: summaryTitle(payload.summary.strongestThemes, '等待真实行情') },
    { key: 'accelerating', label: '扩张', value: summaryTitle(payload.summary.acceleratingThemes, '暂无扩张确认') },
    { key: 'fading', label: '降温', value: summaryTitle(payload.summary.fadingThemes, '暂无降温列表') },
    { key: 'watch', label: '观察信号', value: String(payload.summary.watchlistSignals?.length ?? 0) },
  ];

  return (
    <TerminalPanel data-testid="rotation-radar-summary-band" dense className="min-h-[104px] gap-0 overflow-visible p-0 sm:min-h-[76px]">
      <div className="flex min-w-0 items-center gap-2 border-b border-[color:var(--wolfy-divider)] px-3 py-2 text-[10px] font-bold uppercase text-white/35">
        <Signal className="h-3.5 w-3.5 text-cyan-200/70" aria-hidden="true" />
        轮动状态
      </div>
      <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-2 px-3 py-2 text-xs">
        {items.map((item, index) => (
          <div
            key={item.key}
            className={cn(
              'flex min-w-0 items-baseline gap-1.5 pr-4',
              index < items.length - 1 && 'border-r border-[color:var(--wolfy-divider)]',
            )}
          >
            <span className="shrink-0 text-[11px] text-[color:var(--wolfy-text-muted)]">{item.label}</span>
            <span className="truncate font-mono text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{item.value}</span>
          </div>
        ))}
      </div>
    </TerminalPanel>
  );
};

const LeaderRow: React.FC<{
  theme: MarketRotationTheme;
  rank: number;
  selected: boolean;
  onSelect: () => void;
}> = ({ theme, rank, selected, onSelect }) => {
  const taxonomyOnly = isTaxonomyOnlyTheme(theme);
  const evidenceSummary = rotationEvidenceSummary(theme);
  return (
    <button
      type="button"
      data-testid={`rotation-radar-leader-row-${theme.id}`}
      onClick={onSelect}
      className={cn(
        'grid w-full min-w-0 grid-cols-[2.25rem_minmax(0,1.5fr)_4.5rem_4rem] items-center gap-2 px-3 py-3 text-left transition-colors md:grid-cols-[2.25rem_minmax(0,1.55fr)_4.75rem_4.75rem_4.5rem]',
        selected ? 'bg-cyan-200/[0.06]' : 'hover:bg-white/[0.025]',
      )}
    >
      <span className="font-mono text-xs text-white/38 tabular-nums">{rank.toString().padStart(2, '0')}</span>
      <span className="min-w-0">
        <span className="flex min-w-0 items-center gap-2">
          <span className="truncate text-sm font-semibold text-white/84">{theme.name}</span>
          <DataFreshnessBadge freshness={theme.freshness} className="hidden px-1.5 text-[9px] sm:inline-flex" />
        </span>
        <span className="mt-1 block truncate text-[11px] text-white/38">
          {taxonomyOnly ? '主题库已载入 · 待行情确认' : `${formatThemeStage(theme.stage)} · ${mapDataStateLabel(theme)}`}
        </span>
        {evidenceSummary ? (
          <EvidenceChips summary={evidenceSummary} maxLabels={2} className="mt-1 hidden sm:flex" />
        ) : null}
      </span>
      <span className={cn('text-right font-mono text-lg font-semibold tabular-nums', taxonomyOnly ? 'text-white/46' : scoreTone(theme.rotationScore))}>
        {taxonomyOnly ? '主题库' : theme.rotationScore}
      </span>
      <span className="hidden text-right font-mono text-xs text-emerald-200 tabular-nums md:block">
        {taxonomyOnly ? '待接入' : signedPercent(theme.relativeStrength?.averageRelativeStrengthPercent)}
      </span>
      <span className="hidden text-right font-mono text-xs text-cyan-100 tabular-nums md:block">
        {taxonomyOnly ? '分类' : ratio(theme.volume?.averageRelativeVolume)}
      </span>
      <span className="text-right font-mono text-xs text-white/58 tabular-nums">{taxonomyOnly ? '观察' : percent(theme.breadth?.percentUp, 0)}</span>
    </button>
  );
};

const LaggardRow: React.FC<{
  theme: MarketRotationTheme;
  selected: boolean;
  onSelect: () => void;
}> = ({ theme, selected, onSelect }) => (
  <button
    type="button"
    data-testid={`rotation-radar-laggard-row-${theme.id}`}
    onClick={onSelect}
    className={cn(
      'grid w-full min-w-0 grid-cols-[minmax(0,1fr)_3.5rem] gap-2 px-3 py-3 text-left transition-colors',
      selected ? 'bg-amber-300/[0.07]' : 'hover:bg-white/[0.025]',
    )}
  >
    <span className="min-w-0">
      <span className="block truncate text-sm font-semibold text-white/78">{theme.name}</span>
      <span className="mt-1 block truncate text-[11px] text-white/38">
        {isTaxonomyOnlyTheme(theme) ? '分类观察' : `${formatThemeStage(theme.stage)} · ${mapDataStateLabel(theme)}`}
      </span>
    </span>
    <span className={cn('text-right font-mono text-sm font-semibold tabular-nums', isTaxonomyOnlyTheme(theme) ? 'text-white/44' : scoreTone(theme.rotationScore))}>
      {isTaxonomyOnlyTheme(theme) ? '观察' : theme.rotationScore}
    </span>
  </button>
);

const CompactThemeRow: React.FC<{
  theme: MarketRotationTheme;
  selected: boolean;
  onSelect: () => void;
}> = ({ theme, selected, onSelect }) => (
  <button
    type="button"
    data-testid={`rotation-radar-universe-row-${theme.id}`}
    onClick={onSelect}
    className={cn(
      'grid w-full min-w-0 grid-cols-[minmax(0,1fr)_4rem_4.5rem] items-center gap-2 px-3 py-2.5 text-left text-xs transition-colors',
      selected ? 'bg-cyan-200/[0.06]' : 'hover:bg-white/[0.025]',
    )}
  >
    <span className="min-w-0">
      <span className="block truncate font-semibold text-white/76">{theme.name}</span>
      <span className="block truncate text-[10px] text-white/35">{theme.englishName || theme.focus || theme.benchmark}</span>
    </span>
    <span className={cn('text-right font-mono font-semibold tabular-nums', isTaxonomyOnlyTheme(theme) ? 'text-white/44' : scoreTone(theme.rotationScore))}>
      {isTaxonomyOnlyTheme(theme) ? '主题库' : theme.rotationScore}
    </span>
    <span className="text-right text-[11px] text-white/42">{isTaxonomyOnlyTheme(theme) ? '分类观察' : formatThemeStage(theme.stage)}</span>
  </button>
);

const BucketPanel: React.FC<{ buckets: Bucket[] }> = ({ buckets }) => (
  <section data-testid="rotation-radar-buckets">
    <DataWorkbenchFrame>
      <div className="grid min-w-0 gap-0 md:grid-cols-2 xl:grid-cols-4">
        {buckets.map((bucket, index) => (
          <div
            key={bucket.id}
            className={cn(
              'min-w-0 px-3 py-3',
              index > 0 && 'border-t border-white/[0.05] md:border-t-0',
              index % 2 === 1 && 'md:border-l md:border-white/[0.05] xl:border-l-0',
              index > 1 && 'xl:border-l xl:border-white/[0.05]',
            )}
          >
            <p className={cn('text-[10px] font-bold uppercase', bucket.tone)}>{bucket.title}</p>
            <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
              {bucket.items.length ? bucket.items.map((theme) => (
                <TerminalChip key={theme.id} className="max-w-full truncate border-white/8 bg-black/20 px-2 py-1 text-[11px] text-white/62">
                  {theme.name}
                </TerminalChip>
              )) : (
                <TerminalChip className="truncate border-white/8 bg-black/20 px-2 py-1 text-[11px] text-white/36">{bucket.fallback}</TerminalChip>
              )}
            </div>
          </div>
        ))}
      </div>
    </DataWorkbenchFrame>
  </section>
);

const WatchlistMemberRow: React.FC<{ member: {
  symbol?: string;
  name?: string;
  roleLabel?: string;
  freshnessLabel?: string;
  changePercent?: number | null;
  relativeStrengthVsBenchmark?: number | null;
  observed?: boolean;
}; }> = ({ member }) => (
  <div className="flex min-w-0 items-center justify-between gap-3 rounded-md border border-white/[0.04] bg-black/15 px-3 py-2">
    <span className="min-w-0">
      <span className="block truncate text-sm font-semibold text-white/82">{member.symbol || '--'}</span>
      <span className="block truncate text-[11px] text-white/38">{member.roleLabel || member.name || '观察成员'} · {member.freshnessLabel || '待补齐'}</span>
    </span>
    <span className="shrink-0 text-right text-[11px] text-white/50">
      <span className="block font-mono text-sm text-cyan-100">{signedPercent(member.relativeStrengthVsBenchmark ?? member.changePercent)}</span>
      <span className="block">{member.observed ? '已观察' : '待补齐'}</span>
    </span>
  </div>
);

const ThemeDetailPanel: React.FC<{
  theme?: MarketRotationTheme;
  proxyResetKey: number;
}> = ({ theme, proxyResetKey }) => {
  if (!theme) {
    return null;
  }
  const leaders = theme.leadership?.topMembers || [];
  const laggards = theme.themeDetail?.laggardMembers || [];
  const alertCandidates = theme.alertCandidates || [];
  const detailMembers = theme.themeDetail?.leadershipMembers?.length ? theme.themeDetail.leadershipMembers : [];
  const proxyValues = Object.values(theme.benchmarkProxies || {});
  const nextWatch = alertCandidates[0];
  const taxonomyOnly = isTaxonomyOnlyTheme(theme);
  const dataWarning = Boolean(theme.isFallback || theme.freshness === 'fallback' || isThemeStale(theme));
  const evidenceNotes = sanitizeRotationNotes(theme.evidence);
  const riskExplanationNotes = sanitizeRotationNotes(theme.riskExplanations);
  const evidenceSummary = rotationEvidenceSummary(theme);
  const explanation = sanitizeRotationText(
    theme.stageExplanation,
    `${theme.name} 当前以轮动强度、相对强弱、成交额扩张、广度和同步性作为观察依据。`,
  );

  return (
    <ConsoleContextRail data-testid="rotation-theme-detail-panel" className="xl:sticky xl:top-4">
      <div className="min-w-0 px-1 py-3">
        <div className="flex min-w-0 items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase text-white/35">选中主题</p>
            <h2 className="mt-1 truncate text-lg font-semibold text-white">{theme.name}</h2>
            <p className="mt-1 truncate text-[11px] text-white/38">{theme.englishName} · {theme.focus || theme.benchmark}</p>
          </div>
          <div className="shrink-0 text-right">
            <p className={cn('font-mono text-4xl font-semibold leading-none tabular-nums', taxonomyOnly ? 'text-white/44' : scoreTone(theme.rotationScore))}>
              {taxonomyOnly ? '主题库' : theme.rotationScore}
            </p>
            <p className="mt-1 text-[10px] font-bold uppercase text-white/35">{taxonomyOnly ? '分类状态' : '轮动强度'}</p>
          </div>
        </div>

        <div className="mt-3 flex min-w-0 flex-wrap items-center gap-1.5">
          <TerminalChip variant="info">{formatThemeStage(theme.stage)}</TerminalChip>
          <TerminalChip>{taxonomyOnly ? theme.confidenceLabel || '待行情确认' : `置信度 ${compactConfidence(theme.confidence)}`}</TerminalChip>
          <TerminalChip variant={dataWarning ? 'caution' : 'success'}>{mapDataStateLabel(theme)}</TerminalChip>
          {!taxonomyOnly ? <DataFreshnessBadge freshness={theme.freshness} className="px-1.5 text-[9px]" /> : null}
        </div>
        {evidenceSummary ? (
          <EvidenceChips summary={evidenceSummary} maxLabels={3} className="mt-2" />
        ) : null}
      </div>

      <div className="min-w-0 px-1 py-3">
        {taxonomyOnly ? (
          <TerminalNotice variant="info" className="grid gap-2 px-3 py-3 text-[11px] leading-5">
            <p>主题库已载入，行情评分待本地数据覆盖，仅作分类观察。</p>
            <p>{theme.themeDetail?.dataStateLabel || '待接入本地行情'} · {theme.themeDetail?.nextStep || '本地行情覆盖后可计算轮动强度。'}</p>
          </TerminalNotice>
        ) : dataWarning ? (
          <TerminalNotice variant="caution" className="text-[11px] leading-5">
            当前主题包含备用、过期或部分数据，只能作为观察线索，不能标记为实时结论。
          </TerminalNotice>
        ) : null}

        <TerminalNotice variant="neutral" className="mt-3 text-[12px] leading-5 text-white/58">
          {explanation}
        </TerminalNotice>
      </div>

      {taxonomyOnly ? (
        <div className="min-w-0 px-1 py-3">
          <div>
            <p className="text-[10px] font-bold uppercase text-white/35">映射概念</p>
            <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
              {(theme.themeDetail?.mappedConcepts || theme.mappedConcepts || []).slice(0, 8).map((concept) => (
                <TerminalChip key={concept} variant="info">{concept}</TerminalChip>
              ))}
              {!(theme.themeDetail?.mappedConcepts || theme.mappedConcepts || []).length ? <TerminalChip>待补齐</TerminalChip> : null}
            </div>
          </div>
          <div className="mt-4">
            <p className="text-[10px] font-bold uppercase text-white/35">代表标签 / 符号</p>
            <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
              {(theme.themeDetail?.representativeLabels || theme.representativeLabels || theme.membersConfigured || []).slice(0, 8).map((label) => (
                <TerminalChip key={label}>{label}</TerminalChip>
              ))}
            </div>
          </div>
        </div>
      ) : null}
      {!taxonomyOnly ? (
        <>
          <div className="min-w-0 px-1 py-3">
            <div className="grid grid-cols-2 gap-2">
              <ThemeMetric label="相对强弱" value={signedPercent(theme.relativeStrength?.averageRelativeStrengthPercent)} tone={Number(theme.relativeStrength?.averageRelativeStrengthPercent) >= 0 ? 'text-emerald-200' : 'text-rose-300'} />
              <ThemeMetric label="成交扩张" value={ratio(theme.volume?.averageRelativeVolume)} tone={Number(theme.volume?.averageRelativeVolume) >= 1.1 ? 'text-cyan-200' : 'text-white/58'} />
              <ThemeMetric label="上涨广度" value={percent(theme.breadth?.percentUp)} />
              <ThemeMetric label="跑赢基准" value={percent(theme.breadth?.percentOutperformingBenchmark)} />
              <ThemeMetric label="同步性" value={percent(theme.synchronization?.sameDirectionPercent)} />
              <ThemeMetric label="龙头集中" value={percent(theme.leadership?.leadershipConcentrationPercent)} />
            </div>
          </div>

          <div className="min-w-0 px-1 py-3">
            <p className="text-[10px] font-bold uppercase text-white/35">下一观察 / 风险</p>
            <TerminalNotice variant="info" className="mt-2 text-[11px] leading-5 text-cyan-50/62">
              {nextWatch?.symbol
                ? `${nextWatch.symbol} · ${nextWatch.signalLabel || nextWatch.label || '观察信号'} · ${nextWatch.readOnly ? '只读证据' : '待确认'}`
                : '等待可靠候选补齐，保持只读观察'}
            </TerminalNotice>
            <div className="mt-2 flex min-w-0 flex-wrap items-center gap-1.5">
              {theme.riskLabels.length ? theme.riskLabels.map((risk) => <RiskChip key={risk} risk={risk} />) : (
                <TerminalChip variant="success">暂无高亮风险</TerminalChip>
              )}
              <TerminalChip>非交易指令</TerminalChip>
            </div>
          </div>

          <div className="min-w-0 px-1 py-3">
            <p className="text-[10px] font-bold uppercase text-white/35">领先 / 落后成员</p>
            <div className="mt-2 grid gap-3">
              <div>
                <p className="mb-2 text-[10px] font-semibold uppercase text-white/35">领先成员</p>
                <div className="grid gap-2">
                  {leaders.length ? leaders.slice(0, 4).map((leader) => (
                    <div key={leader.symbol} className="flex min-w-0 items-center justify-between gap-3 rounded-md border border-white/[0.04] bg-black/15 px-3 py-2">
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-semibold text-white/82">{leader.symbol}</span>
                        <span className="block truncate text-[11px] text-white/38">{leader.name || leader.symbol}</span>
                      </span>
                      <span className="shrink-0 text-right font-mono text-sm text-emerald-200 tabular-nums">{signedPercent(leader.relativeStrengthVsBenchmark ?? leader.changePercent)}</span>
                    </div>
                  )) : detailMembers.length ? detailMembers.slice(0, 4).map((member) => (
                    <WatchlistMemberRow key={`${member.symbol || 'leader'}-${member.roleLabel || 'leader'}`} member={member} />
                  )) : (
                    <TerminalEmptyState className="min-h-[72px] justify-start px-3 py-2 text-sm text-white/45">代表成员待快照补齐</TerminalEmptyState>
                  )}
                </div>
              </div>
              <div>
                <p className="mb-2 text-[10px] font-semibold uppercase text-white/35">落后 / 待验证成员</p>
                <div className="grid gap-2">
                  {laggards.length ? laggards.slice(0, 4).map((member) => (
                    <WatchlistMemberRow key={`${member.symbol || 'laggard'}-${member.roleLabel || 'laggard'}`} member={member} />
                  )) : (
                    <TerminalEmptyState className="min-h-[72px] justify-start px-3 py-2 text-sm text-white/45">暂无落后成员快照</TerminalEmptyState>
                  )}
                </div>
              </div>
            </div>
          </div>

          <div className="min-w-0 px-1 py-3">
            <TerminalDisclosure
              key={`${theme.id}-${proxyResetKey}`}
              data-testid={`rotation-theme-proxy-details-${theme.id}`}
              title="数据诊断"
              summary={(
                <span data-testid={`rotation-proxy-quality-summary-${theme.id}`} className="inline-flex min-w-0 flex-wrap items-center gap-1.5">
                  <TerminalChip variant={theme.proxyQuality?.hasMissingRequiredProxy || theme.proxyQuality?.hasStaleProxy ? 'caution' : 'success'}>
                    {proxyQualityState(theme)}
                  </TerminalChip>
                  <TerminalChip>
                    覆盖 {theme.proxyQuality?.availableProxyCount ?? proxyValues.length}/{theme.proxyQuality?.totalProxyCount ?? proxyValues.length}
                  </TerminalChip>
                  <TerminalChip>{percent(theme.proxyQuality?.coveragePercent)}</TerminalChip>
                  <DataFreshnessBadge freshness={theme.proxyQuality?.freshness || theme.freshness} className="px-1.5 text-[9px]" />
                </span>
              )}
            >
              <div className="grid gap-2 text-[11px] text-white/48">
                {theme.proxyQuality?.explanation ? <p className="leading-5">{sanitizeRotationText(theme.proxyQuality.explanation)}</p> : null}
                {proxyValues.map((proxy) => (
                  <div
                    key={proxy.symbol}
                    data-testid={`rotation-proxy-row-${proxy.symbol}`}
                    className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-2 rounded-lg border border-white/[0.04] bg-white/[0.02] px-3 py-2"
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-semibold text-white/82">{proxy.symbol}</span>
                      <span className="block truncate text-[11px] text-white/38">{proxy.role === 'sector_proxy' ? '行业代理' : '市场代理'}</span>
                    </span>
                    <span className="shrink-0 text-right">
                      <span className="block font-mono text-sm text-cyan-100">{signedPercent(proxy.relativeStrength)}</span>
                      <span className="block text-[10px] text-white/42">{proxyMissingReasonLabel(proxy.quality?.missingReason)}</span>
                    </span>
                  </div>
                ))}
                {theme.timeWindows ? (
                  <div className="grid grid-cols-2 gap-2">
                    {(['5m', '15m', '60m', '1d'] as const).map((window) => (
                      <WindowChip key={window} window={theme.timeWindows?.[window] || {
                        window,
                        label: window,
                        available: false,
                        freshness: 'fallback',
                        isFallback: true,
                        isStale: false,
                        reason: 'window_unavailable',
                      }} />
                    ))}
                  </div>
                ) : null}
              </div>
            </TerminalDisclosure>
          </div>
        </>
      ) : null}

      <div className="min-w-0 px-1 py-3">
        <TerminalDisclosure
          data-testid={`rotation-theme-evidence-details-${theme.id}`}
          title="证据详情"
          summary={evidenceNotes.length || riskExplanationNotes.length ? '观察证据与风险说明默认折叠' : '暂无额外证据'}
        >
          <div className="grid gap-1 text-[11px] leading-5 text-white/48">
            {evidenceNotes.slice(0, 5).map((item) => <p key={item} className="truncate">· {item}</p>)}
            {riskExplanationNotes.slice(0, 3).map((item) => <p key={item} className="truncate">· {item}</p>)}
            {!evidenceNotes.length && !riskExplanationNotes.length ? <p>暂无额外证据。</p> : null}
          </div>
        </TerminalDisclosure>
      </div>
    </ConsoleContextRail>
  );
};

const LoadingPanel: React.FC = () => (
  <TerminalPanel as="section" role="status" aria-label="正在读取资金轮动雷达">
    <div className="flex items-center gap-3 text-white/60">
      <RefreshCcw className="h-4 w-4 animate-spin" aria-hidden="true" />
      <span className="text-sm">正在读取资金轮动雷达...</span>
    </div>
  </TerminalPanel>
);

const MarketRotationRadarPage: React.FC = () => {
  const [payload, setPayload] = useState<MarketRotationRadarResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [selectedMarket, setSelectedMarket] = useState('US');
  const [selectedThemeId, setSelectedThemeId] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [proxyDisclosureSeed, setProxyDisclosureSeed] = useState(0);

  const loadRadar = useCallback(async (market = selectedMarket) => {
    setLoading(true);
    setError(null);
    try {
      const nextPayload = await marketRotationApi.getRotationRadar(market);
      setPayload(nextPayload);
      setSelectedThemeId(nextPayload.themes[0]?.id || '');
      setSearchQuery('');
      setProxyDisclosureSeed((seed) => seed + 1);
    } catch (nextError) {
      setError({ ...getParsedApiError(nextError), title: '读取资金轮动雷达失败' });
    } finally {
      setLoading(false);
    }
  }, [selectedMarket]);

  useEffect(() => {
    void loadRadar(selectedMarket);
  }, [loadRadar, selectedMarket]);

  const headlineThemes = useMemo(
    () => resolveSummaryThemes(payload?.themes || [], payload?.summary.strongestThemes || []),
    [payload?.themes, payload?.summary.strongestThemes],
  );
  const weakeningThemes = useMemo(() => deriveWeakeningThemes(payload?.themes || []), [payload?.themes]);
  const filteredThemes = useMemo(
    () => (payload?.themes || []).filter((theme) => matchesSearch(theme, searchQuery)),
    [payload?.themes, searchQuery],
  );
  const buckets = useMemo(() => deriveParticipationBuckets(payload?.themes || []), [payload?.themes]);

  const selectedTheme = useMemo(
    () => payload?.themes.find((theme) => theme.id === selectedThemeId) || payload?.themes[0],
    [payload, selectedThemeId],
  );

  return (
    <div
      data-testid="market-rotation-radar-page"
      data-bento-surface="true"
      className="bento-surface-root flex min-h-0 w-full min-w-0 flex-1 flex-col gap-6 overflow-y-auto overflow-x-hidden no-scrollbar text-white"
    >
      <WideWorkspacePageShell className="flex min-h-0 flex-1 py-5 md:py-6">
        <TerminalPanel as="section" dense className="relative shrink-0 overflow-hidden">
          <TerminalPageHeading
            eyebrow="资金轮动 / Rotation Radar"
            title="资金轮动雷达"
            action={<TerminalChip variant="info">RotationMonitor</TerminalChip>}
          />
        </TerminalPanel>

        {error ? (
          <TerminalPanel as="section">
            <ApiErrorAlert error={error} />
          </TerminalPanel>
        ) : null}

        {loading && !payload ? <LoadingPanel /> : null}

        {payload ? (
          <>
            {payload.warning ? (
              <TerminalNotice variant="caution" className="flex items-start gap-2 px-4 py-3 text-sm leading-6">
                <AlertTriangle className="mt-1 h-4 w-4 shrink-0" aria-hidden="true" />
                <span>{sanitizeRotationText(payload.warning)}</span>
              </TerminalNotice>
            ) : null}

            <CommandBar
              selectedMarket={selectedMarket}
              supportedMarkets={payload.supportedMarkets || ['US', 'CN', 'HK', 'CRYPTO']}
              searchQuery={searchQuery}
              onMarketChange={setSelectedMarket}
              onSearchChange={setSearchQuery}
              loading={loading}
              freshness={payload.freshness}
              onRefresh={() => void loadRadar()}
            />

            <SummaryBand payload={payload} />

            <TerminalGrid className="gap-4" data-workbench-split="8:4">
              <section className="min-w-0 space-y-4 xl:col-span-8" aria-label="今日轮动 Top-N">
                <DataWorkbenchFrame data-testid="rotation-radar-leader-list">
                  <div className="grid min-w-0 gap-0 md:grid-cols-[minmax(0,1.55fr)_minmax(260px,0.65fr)]">
                    <section className="min-w-0 border-b border-white/[0.05] md:border-b-0 md:border-r md:border-white/[0.05]">
                      <div className="flex min-w-0 items-start justify-between gap-3 border-b border-white/[0.05] px-3 py-3">
                        <TerminalSectionHeader eyebrow="主题板块榜单" title={headlineThemes.length ? `领涨 Top ${headlineThemes.length}` : '暂无头部排名'} />
                        <div className="hidden min-w-0 grid-cols-[4.75rem_4.75rem_4.5rem] gap-2 text-right text-[10px] font-semibold uppercase text-white/32 md:grid">
                          <span>相对</span>
                          <span>量能</span>
                          <span>广度</span>
                        </div>
                      </div>
                      {headlineThemes.length ? (
                        <DenseRows>
                          {headlineThemes.map((theme, index) => (
                            <LeaderRow
                              key={theme.id}
                              theme={theme}
                              rank={index + 1}
                              selected={selectedTheme?.id === theme.id}
                              onSelect={() => {
                                setSelectedThemeId(theme.id);
                                setProxyDisclosureSeed((seed) => seed + 1);
                              }}
                            />
                          ))}
                        </DenseRows>
                      ) : (
                        <div className="p-3">
                          <TerminalEmptyState className="min-h-[104px] justify-start text-sm text-white/42">
                            {payload.summary.noHeadlineReason || '没有可用于头部排名'}
                          </TerminalEmptyState>
                        </div>
                      )}
                    </section>

                    <aside className="min-w-0">
                      <div className="border-b border-white/[0.05] px-3 py-3">
                        <TerminalSectionHeader eyebrow="降温 / 弱信号" title="观察退潮与分歧" />
                      </div>
                      {weakeningThemes.length ? (
                        <DenseRows>
                          {weakeningThemes.map((theme) => (
                            <LaggardRow
                              key={theme.id}
                              theme={theme}
                              selected={selectedTheme?.id === theme.id}
                              onSelect={() => {
                                setSelectedThemeId(theme.id);
                                setProxyDisclosureSeed((seed) => seed + 1);
                              }}
                            />
                          ))}
                        </DenseRows>
                      ) : (
                        <div className="p-3">
                          <TerminalEmptyState className="min-h-[72px] justify-start text-sm text-white/42">暂无降温主题。</TerminalEmptyState>
                        </div>
                      )}
                    </aside>
                  </div>
                </DataWorkbenchFrame>

                <BucketPanel buckets={buckets} />

                <DataWorkbenchFrame data-testid="rotation-radar-universe-list">
                  <div className="border-b border-white/[0.05] px-3 py-3">
                    <TerminalSectionHeader
                      eyebrow="主题 / 行业板"
                      title={`${filteredThemes.length}/${payload.themes.length} 个条目，紧凑选择。`}
                    />
                  </div>
                  <div className="max-h-80 overflow-y-auto no-scrollbar">
                    {filteredThemes.length ? (
                      <DenseRows>
                        {filteredThemes.map((theme) => (
                          <CompactThemeRow
                            key={theme.id}
                            theme={theme}
                            selected={selectedTheme?.id === theme.id}
                            onSelect={() => {
                              setSelectedThemeId(theme.id);
                              setProxyDisclosureSeed((seed) => seed + 1);
                            }}
                          />
                        ))}
                      </DenseRows>
                    ) : (
                      <div className="p-3">
                        <TerminalEmptyState className="min-h-[72px] justify-start text-sm text-white/42">没有匹配主题。</TerminalEmptyState>
                      </div>
                    )}
                  </div>
                </DataWorkbenchFrame>
              </section>

              <div className="min-w-0 xl:col-span-4">
                <ThemeDetailPanel
                  theme={selectedTheme}
                  proxyResetKey={proxyDisclosureSeed}
                />
              </div>
            </TerminalGrid>

            <TerminalDisclosure
              data-testid="rotation-radar-mechanics-details"
              title="新鲜度 / 来源说明"
              summary="默认折叠"
              className="rounded-2xl p-4 text-sm text-white/55"
            >
              <div className="grid gap-3 text-[11px] text-white/46">
                <div className="flex min-w-0 flex-wrap items-center gap-2">
                  <TerminalChip>{marketLabel(payload.market || selectedMarket)}</TerminalChip>
                  <TerminalChip>{payload.sourceLabel || '待确认'}</TerminalChip>
                  <DataFreshnessBadge freshness={payload.freshness || 'fallback'} className="px-1.5 text-[9px]" />
                  <TerminalChip>Top-N {headlineThemes.length}/{payload.themes.length}</TerminalChip>
                </div>
                <Gauge className="h-4 w-4 text-cyan-200/70" aria-hidden="true" />
                <span>当前为静态主题库，本地行情覆盖后可计算轮动强度。</span>
                <Signal className="ml-2 h-4 w-4 text-emerald-200/70" aria-hidden="true" />
                <span>不代表实时买卖信号，不触发交易、通知、组合或新的外部数据请求。</span>
                <Waves className="ml-2 h-4 w-4 text-white/40" aria-hidden="true" />
                <span>{payload.noAdviceDisclosure}</span>
              </div>
            </TerminalDisclosure>
          </>
        ) : null}
      </WideWorkspacePageShell>
    </div>
  );
};

export default MarketRotationRadarPage;
