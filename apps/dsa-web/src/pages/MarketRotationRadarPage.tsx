import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Gauge, RefreshCcw, Search, Signal, SlidersHorizontal, Waves } from 'lucide-react';
import { ApiErrorAlert, GlassCard } from '../components/common';
import { DataFreshnessBadge } from '../components/market-overview/marketOverviewPrimitives';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { marketRotationApi, type MarketRotationRadarResponse, type MarketRotationRiskLabel, type MarketRotationStage, type MarketRotationSummaryItem, type MarketRotationTheme, type MarketRotationTimeWindow } from '../api/marketRotation';
import { cn } from '../utils/cn';
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
    return 'N/A';
  }
  return `${value.toFixed(digits)}%`;
}

function signedPercent(value?: number | null, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return 'N/A';
  }
  return `${value >= 0 ? '+' : ''}${value.toFixed(digits)}%`;
}

function ratio(value?: number | null): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return 'N/A';
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

const SummaryCell: React.FC<{
  title: string;
  value: string;
  accent?: string;
  children?: React.ReactNode;
}> = ({ title, value, accent = 'text-white', children }) => (
  <div className="min-w-0 rounded-xl border border-white/5 bg-white/[0.025] px-3 py-3">
    <p className="truncate text-[10px] font-bold uppercase text-white/38">{title}</p>
    <p className={cn('mt-2 truncate text-sm font-semibold', accent)}>{value}</p>
    {children ? <div className="mt-2 min-w-0 text-[11px] leading-5 text-white/45">{children}</div> : null}
  </div>
);

const ThemeMetric: React.FC<{ label: string; value: string; tone?: string }> = ({ label, value, tone = 'text-white/78' }) => (
  <div className="min-w-0 rounded-lg border border-white/[0.04] bg-black/20 px-3 py-2">
    <p className="truncate text-[10px] font-semibold text-white/38">{label}</p>
    <p className={cn('mt-1 truncate font-mono text-sm font-semibold tabular-nums', tone)}>{value}</p>
  </div>
);

const EvidenceBadge: React.FC<{ children: React.ReactNode; tone?: 'neutral' | 'info' | 'warn' | 'ok' }> = ({ children, tone = 'neutral' }) => (
  <span
    className={cn(
      'inline-flex min-h-5 items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold leading-none',
      tone === 'info' && 'border-cyan-300/20 bg-cyan-300/10 text-cyan-100',
      tone === 'warn' && 'border-amber-300/24 bg-amber-300/10 text-amber-100',
      tone === 'ok' && 'border-emerald-300/20 bg-emerald-300/10 text-emerald-100',
      tone === 'neutral' && 'border-white/8 bg-white/[0.03] text-white/48',
    )}
  >
    {children}
  </span>
);

const WindowChip: React.FC<{ window: MarketRotationTimeWindow }> = ({ window }) => (
  <div className="min-w-0 rounded-lg border border-white/[0.04] bg-black/20 px-3 py-2">
    <p className="truncate text-[10px] font-semibold text-white/38">{window.label}</p>
    <p className={cn('mt-1 truncate text-[11px] font-semibold', window.available ? 'text-cyan-100' : 'text-white/35')}>
      {window.available ? signedPercent(window.changePercent, 1) : '待补齐'}
    </p>
  </div>
);

const RiskChip: React.FC<{ risk: MarketRotationRiskLabel }> = ({ risk }) => (
  <span className="inline-flex items-center rounded-full border border-amber-300/20 bg-amber-300/10 px-2 py-0.5 text-[10px] font-semibold text-amber-100">
    {RISK_LABELS[risk] || '风险待识别'}
  </span>
);

const ModeControls: React.FC<{
  selectedMarket: string;
  supportedMarkets: string[];
  onMarketChange: (market: string) => void;
}> = ({ selectedMarket, supportedMarkets, onMarketChange }) => (
  <section data-testid="rotation-radar-mode-controls" className="mt-4 grid min-w-0 grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
    <div className="min-w-0 rounded-2xl border border-white/5 bg-white/[0.02] p-3">
      <div className="mb-2 flex items-center gap-2 text-[10px] font-bold uppercase text-white/38">
        <SlidersHorizontal className="h-3.5 w-3.5 text-cyan-200/70" aria-hidden="true" />
        市场
      </div>
      <div className="flex min-w-0 gap-2 overflow-x-auto no-scrollbar">
        {MARKET_OPTIONS.filter((market) => !supportedMarkets.length || supportedMarkets.includes(market.id)).map((market) => (
          <button
            key={market.id}
            type="button"
            data-testid={`rotation-market-tab-${market.id}`}
            aria-pressed={selectedMarket === market.id}
            className={cn(
              'shrink-0 rounded-lg border px-3 py-1.5 text-xs font-semibold transition-all',
              selectedMarket === market.id
                ? 'border-cyan-200/24 bg-cyan-200/[0.08] text-cyan-50'
                : 'border-white/[0.04] bg-white/[0.015] text-white/48 hover:border-white/10 hover:bg-white/[0.04] hover:text-white/75',
            )}
            onClick={() => onMarketChange(market.id)}
          >
            {market.label}
          </button>
        ))}
      </div>
    </div>
    <div className="min-w-0 rounded-2xl border border-white/5 bg-white/[0.02] p-3">
      <div className="mb-2 flex items-center gap-2 text-[10px] font-bold uppercase text-white/38">
        <Gauge className="h-3.5 w-3.5 text-cyan-200/70" aria-hidden="true" />
        分类层级
      </div>
      <div className="flex min-w-0 gap-2 overflow-x-auto no-scrollbar">
        {TAXONOMY_PLACEHOLDERS.map((mode, index) => (
          <button
            key={mode}
            type="button"
            className={cn(
              'shrink-0 rounded-lg border px-3 py-1.5 text-xs font-semibold transition-all',
              index === 0
                ? 'border-white/10 bg-white/[0.055] text-white/75'
                : 'border-white/[0.04] bg-white/[0.015] text-white/35',
            )}
            disabled
          >
            {mode}
          </button>
        ))}
      </div>
    </div>
  </section>
);

const LeaderRow: React.FC<{
  theme: MarketRotationTheme;
  rank: number;
  selected: boolean;
  onSelect: () => void;
}> = ({ theme, rank, selected, onSelect }) => {
  const taxonomyOnly = isTaxonomyOnlyTheme(theme);
  return (
  <button
    type="button"
    data-testid={`rotation-radar-leader-row-${theme.id}`}
    onClick={onSelect}
    className={cn(
      'grid w-full min-w-0 grid-cols-[2rem_minmax(0,1.2fr)_4.25rem_4.5rem] items-center gap-2 rounded-xl border px-3 py-2.5 text-left transition-all sm:grid-cols-[2rem_minmax(0,1.4fr)_5rem_5rem_5rem_5rem]',
      selected ? 'border-cyan-200/24 bg-cyan-200/[0.065]' : 'border-white/[0.045] bg-black/20 hover:border-white/10 hover:bg-white/[0.03]',
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
    </span>
    <span className={cn('text-right font-mono text-lg font-semibold tabular-nums', taxonomyOnly ? 'text-white/46' : scoreTone(theme.rotationScore))}>
      {taxonomyOnly ? '主题库' : theme.rotationScore}
    </span>
    <span className="hidden text-right font-mono text-xs text-emerald-200 tabular-nums sm:block">{taxonomyOnly ? '待接入' : signedPercent(theme.relativeStrength?.averageRelativeStrengthPercent)}</span>
    <span className="hidden text-right font-mono text-xs text-cyan-100 tabular-nums sm:block">{taxonomyOnly ? '分类' : ratio(theme.volume?.averageRelativeVolume)}</span>
    <span className="text-right font-mono text-xs text-white/58 tabular-nums">{taxonomyOnly ? '观察' : percent(theme.breadth?.percentUp, 0)}</span>
  </button>
  );
};

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
      'grid w-full min-w-0 grid-cols-[minmax(0,1fr)_4rem_4rem] items-center gap-2 rounded-lg border px-3 py-2 text-left text-xs transition-all',
      selected ? 'border-cyan-200/20 bg-cyan-200/[0.055]' : 'border-white/[0.04] bg-black/20 hover:bg-white/[0.03]',
    )}
  >
    <span className="min-w-0">
      <span className="block truncate font-semibold text-white/76">{theme.name}</span>
      <span className="block truncate text-[10px] text-white/35">{theme.englishName || theme.focus || theme.benchmark}</span>
    </span>
    <span className={cn('text-right font-mono font-semibold tabular-nums', isTaxonomyOnlyTheme(theme) ? 'text-white/44' : scoreTone(theme.rotationScore))}>
      {isTaxonomyOnlyTheme(theme) ? '主题库' : theme.rotationScore}
    </span>
    <span className="text-right text-white/42">{isTaxonomyOnlyTheme(theme) ? '分类观察' : formatThemeStage(theme.stage)}</span>
  </button>
);

const BucketPanel: React.FC<{ buckets: Bucket[] }> = ({ buckets }) => (
  <section data-testid="rotation-radar-buckets" className="grid min-w-0 grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
    {buckets.map((bucket) => (
      <div key={bucket.id} className="min-w-0 rounded-2xl border border-white/5 bg-white/[0.02] p-3">
        <p className={cn('text-[10px] font-bold uppercase', bucket.tone)}>{bucket.title}</p>
        <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
          {bucket.items.length ? bucket.items.map((theme) => (
            <span key={theme.id} className="max-w-full truncate rounded-full border border-white/8 bg-black/20 px-2 py-1 text-[11px] text-white/62">
              {theme.name}
            </span>
          )) : (
            <span className="truncate rounded-full border border-white/8 bg-black/20 px-2 py-1 text-[11px] text-white/36">{bucket.fallback}</span>
          )}
        </div>
      </div>
    ))}
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
  <div className="flex min-w-0 items-center justify-between gap-3 rounded-xl border border-white/[0.04] bg-black/20 px-3 py-2">
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
  isProxyOpen: boolean;
  onProxyToggle: (open: boolean) => void;
}> = ({ theme, isProxyOpen, onProxyToggle }) => {
  if (!theme) {
    return null;
  }
  const leaders = theme.leadership?.topMembers || [];
  const alertCandidates = theme.alertCandidates || [];
  const detailMembers = theme.themeDetail?.leadershipMembers?.length ? theme.themeDetail.leadershipMembers : [];
  const proxyValues = Object.values(theme.benchmarkProxies || {});
  const nextWatch = alertCandidates[0];
  const taxonomyOnly = isTaxonomyOnlyTheme(theme);
  const dataWarning = Boolean(theme.isFallback || theme.freshness === 'fallback' || isThemeStale(theme));
  const evidenceNotes = sanitizeRotationNotes(theme.evidence);
  const riskExplanationNotes = sanitizeRotationNotes(theme.riskExplanations);
  const explanation = sanitizeRotationText(
    theme.stageExplanation,
    `${theme.name} 当前以轮动强度、相对强弱、成交额扩张、广度和同步性作为观察依据。`,
  );

  return (
    <GlassCard as="aside" data-testid="rotation-theme-detail-panel" className="p-4 md:p-5 xl:sticky xl:top-4">
      <div className="flex min-w-0 items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10px] font-bold uppercase text-white/35">单主题详情</p>
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
        <EvidenceBadge tone="info">{formatThemeStage(theme.stage)}</EvidenceBadge>
        <EvidenceBadge>{taxonomyOnly ? theme.confidenceLabel || '待行情确认' : `置信度 ${compactConfidence(theme.confidence)}`}</EvidenceBadge>
        <EvidenceBadge tone={dataWarning ? 'warn' : 'ok'}>{mapDataStateLabel(theme)}</EvidenceBadge>
        {!taxonomyOnly ? <DataFreshnessBadge freshness={theme.freshness} className="px-1.5 text-[9px]" /> : null}
      </div>

      {taxonomyOnly ? (
        <div className="mt-3 grid gap-2 rounded-xl border border-cyan-200/12 bg-cyan-200/[0.045] px-3 py-3 text-[11px] leading-5 text-cyan-50/70">
          <p>主题库已载入，行情评分待本地数据覆盖，仅作分类观察。</p>
          <p>{theme.themeDetail?.dataStateLabel || '待接入本地行情'} · {theme.themeDetail?.nextStep || '本地行情覆盖后可计算轮动强度。'}</p>
        </div>
      ) : dataWarning ? (
        <p className="mt-3 rounded-xl border border-amber-300/15 bg-amber-300/10 px-3 py-2 text-[11px] leading-5 text-amber-100/75">
          当前主题包含备用、过期或部分数据，只能作为观察线索，不能标记为实时结论。
        </p>
      ) : null}

      <p className="mt-3 rounded-xl border border-white/[0.04] bg-black/20 px-3 py-2 text-[12px] leading-5 text-white/58">
        {explanation}
      </p>

      {taxonomyOnly ? (
        <div className="mt-4 grid gap-3">
          <div>
            <p className="text-[10px] font-bold uppercase text-white/35">映射概念</p>
            <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
              {(theme.themeDetail?.mappedConcepts || theme.mappedConcepts || []).slice(0, 8).map((concept) => (
                <EvidenceBadge key={concept} tone="info">{concept}</EvidenceBadge>
              ))}
              {!(theme.themeDetail?.mappedConcepts || theme.mappedConcepts || []).length ? <EvidenceBadge>待补齐</EvidenceBadge> : null}
            </div>
          </div>
          <div>
            <p className="text-[10px] font-bold uppercase text-white/35">代表标签 / 符号</p>
            <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
              {(theme.themeDetail?.representativeLabels || theme.representativeLabels || theme.membersConfigured || []).slice(0, 8).map((label) => (
                <EvidenceBadge key={label}>{label}</EvidenceBadge>
              ))}
            </div>
          </div>
        </div>
      ) : (
      <div className="mt-4 grid grid-cols-2 gap-2">
        <ThemeMetric label="相对强弱" value={signedPercent(theme.relativeStrength?.averageRelativeStrengthPercent)} tone={Number(theme.relativeStrength?.averageRelativeStrengthPercent) >= 0 ? 'text-emerald-200' : 'text-rose-300'} />
        <ThemeMetric label="成交扩张" value={ratio(theme.volume?.averageRelativeVolume)} tone={Number(theme.volume?.averageRelativeVolume) >= 1.1 ? 'text-cyan-200' : 'text-white/58'} />
        <ThemeMetric label="上涨广度" value={percent(theme.breadth?.percentUp)} />
        <ThemeMetric label="跑赢基准" value={percent(theme.breadth?.percentOutperformingBenchmark)} />
        <ThemeMetric label="同步性" value={percent(theme.synchronization?.sameDirectionPercent)} />
        <ThemeMetric label="龙头集中" value={percent(theme.leadership?.leadershipConcentrationPercent)} />
      </div>
      )}

      {!taxonomyOnly ? <div className="mt-5">
        <p className="text-[10px] font-bold uppercase text-white/35">下一观察 / 风险</p>
        <div className="mt-2 rounded-xl border border-cyan-200/10 bg-cyan-200/[0.035] px-3 py-2 text-[11px] leading-5 text-cyan-50/62">
          {nextWatch?.symbol
            ? `${nextWatch.symbol} · ${nextWatch.signalLabel || nextWatch.label || '观察信号'} · ${nextWatch.readOnly ? '只读证据' : '待确认'}`
            : '等待可靠候选补齐，保持只读观察'}
        </div>
        <div className="mt-2 flex min-w-0 flex-wrap items-center gap-1.5">
          {theme.riskLabels.length ? theme.riskLabels.map((risk) => <RiskChip key={risk} risk={risk} />) : (
            <EvidenceBadge tone="ok">暂无高亮风险</EvidenceBadge>
          )}
          <EvidenceBadge>非交易指令</EvidenceBadge>
        </div>
      </div> : null}

      {!taxonomyOnly ? <div className="mt-5">
        <p className="text-[10px] font-bold uppercase text-white/35">代表成员 / 代理</p>
        <div className="mt-2 grid gap-2">
          {leaders.length ? leaders.slice(0, 4).map((leader) => (
            <div key={leader.symbol} className="flex min-w-0 items-center justify-between gap-3 rounded-xl border border-white/[0.04] bg-black/20 px-3 py-2">
              <span className="min-w-0">
                <span className="block truncate text-sm font-semibold text-white/82">{leader.symbol}</span>
                <span className="block truncate text-[11px] text-white/38">{leader.name || leader.symbol}</span>
              </span>
              <span className="shrink-0 text-right font-mono text-sm text-emerald-200 tabular-nums">{signedPercent(leader.relativeStrengthVsBenchmark ?? leader.changePercent)}</span>
            </div>
          )) : detailMembers.length ? detailMembers.slice(0, 4).map((member) => (
            <WatchlistMemberRow key={`${member.symbol || 'leader'}-${member.roleLabel || 'leader'}`} member={member} />
          )) : (
            <p className="rounded-xl border border-white/[0.04] bg-black/20 px-3 py-2 text-sm text-white/45">代表成员待快照补齐</p>
          )}
        </div>
      </div> : null}

      {!taxonomyOnly ? <details
        data-testid={`rotation-theme-proxy-details-${theme.id}`}
        className="mt-5 rounded-xl border border-white/[0.04] bg-black/20 px-3 py-2"
        onToggle={(event) => onProxyToggle(event.currentTarget.open)}
      >
        <summary className="cursor-pointer list-none">
          <div className="flex min-w-0 flex-wrap items-center gap-1.5">
            <span className="mr-1 text-[10px] font-bold uppercase text-white/35">数据诊断</span>
            <span data-testid={`rotation-proxy-quality-summary-${theme.id}`} className="flex min-w-0 flex-wrap items-center gap-1.5">
              <EvidenceBadge tone={theme.proxyQuality?.hasMissingRequiredProxy || theme.proxyQuality?.hasStaleProxy ? 'warn' : 'ok'}>
                {proxyQualityState(theme)}
              </EvidenceBadge>
              <EvidenceBadge>
                覆盖 {theme.proxyQuality?.availableProxyCount ?? proxyValues.length}/{theme.proxyQuality?.totalProxyCount ?? proxyValues.length}
              </EvidenceBadge>
              <EvidenceBadge>{percent(theme.proxyQuality?.coveragePercent)}</EvidenceBadge>
              <DataFreshnessBadge freshness={theme.proxyQuality?.freshness || theme.freshness} className="px-1.5 text-[9px]" />
            </span>
          </div>
        </summary>
        {isProxyOpen ? (
          <div className="mt-3 grid gap-2 text-[11px] text-white/48">
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
        ) : null}
      </details> : null}

      <details className="mt-3 rounded-xl border border-white/[0.04] bg-black/20 px-3 py-2">
        <summary className="cursor-pointer list-none text-[10px] font-bold uppercase text-white/35">证据详情</summary>
        <div className="mt-2 grid gap-1 text-[11px] leading-5 text-white/48">
          {evidenceNotes.slice(0, 5).map((item) => <p key={item} className="truncate">· {item}</p>)}
          {riskExplanationNotes.slice(0, 3).map((item) => <p key={item} className="truncate">· {item}</p>)}
          {!evidenceNotes.length && !riskExplanationNotes.length ? <p>暂无额外证据。</p> : null}
        </div>
      </details>
    </GlassCard>
  );
};

const LoadingPanel: React.FC = () => (
  <GlassCard as="section" className="p-5" role="status" aria-label="正在读取资金轮动雷达">
    <div className="flex items-center gap-3 text-white/60">
      <RefreshCcw className="h-4 w-4 animate-spin" aria-hidden="true" />
      <span className="text-sm">正在读取资金轮动雷达...</span>
    </div>
  </GlassCard>
);

const MarketRotationRadarPage: React.FC = () => {
  const [payload, setPayload] = useState<MarketRotationRadarResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [selectedMarket, setSelectedMarket] = useState('US');
  const [selectedThemeId, setSelectedThemeId] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [proxyOpenThemeId, setProxyOpenThemeId] = useState<string>('');

  const loadRadar = useCallback(async (market = selectedMarket) => {
    setLoading(true);
    setError(null);
    try {
      const nextPayload = await marketRotationApi.getRotationRadar(market);
      setPayload(nextPayload);
      setSelectedThemeId(nextPayload.themes[0]?.id || '');
      setProxyOpenThemeId('');
      setSearchQuery('');
    } catch (nextError) {
      setError({ ...getParsedApiError(nextError), title: '读取资金轮动雷达失败' });
    } finally {
      setLoading(false);
    }
  }, [selectedMarket]);

  useEffect(() => {
    void loadRadar(selectedMarket);
  }, [loadRadar, selectedMarket]);

  const rankedThemes = useMemo(() => deriveTopThemes(payload?.themes || []), [payload?.themes]);
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
      className="bento-surface-root flex min-h-0 w-full flex-1 flex-col overflow-y-auto overflow-x-hidden no-scrollbar bg-[#050505] px-4 py-5 text-white md:px-6 xl:px-8"
    >
      <GlassCard as="section" className="relative shrink-0 overflow-hidden p-5 md:p-6">
        <div className="relative z-10 flex min-w-0 flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase text-cyan-200/55">Market Rotation Radar</p>
            <h1 className="mt-2 text-2xl font-semibold text-white md:text-3xl">资金轮动雷达</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-white/50">
              紧凑 Top-N 观察台。当前仅重排既有主题篮子数据，不新增行情或新闻请求。
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <div data-testid="rotation-radar-freshness" className="inline-flex items-center gap-2 rounded-xl border border-white/8 bg-black/20 px-3 py-2">
              <span className="text-[10px] font-bold uppercase text-white/35">数据新鲜度</span>
              <DataFreshnessBadge freshness={payload?.freshness || 'fallback'} />
            </div>
            <button
              type="button"
              className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-white/50 transition-all hover:bg-white/10 hover:text-white disabled:cursor-wait disabled:text-white/30"
              onClick={() => void loadRadar()}
              disabled={loading}
              aria-label="刷新资金轮动雷达"
            >
              <RefreshCcw className={cn('h-4 w-4', loading ? 'animate-spin' : '')} aria-hidden="true" />
            </button>
          </div>
        </div>
      </GlassCard>

      {error ? (
        <GlassCard as="section" className="mt-4 p-5">
          <ApiErrorAlert error={error} />
        </GlassCard>
      ) : null}

      {loading && !payload ? (
        <div className="mt-4">
          <LoadingPanel />
        </div>
      ) : null}

      {payload ? (
        <>
          {payload.warning ? (
            <div className="mt-4 flex items-start gap-2 rounded-xl border border-amber-300/15 bg-amber-300/10 px-4 py-3 text-sm leading-6 text-amber-100/80">
              <AlertTriangle className="mt-1 h-4 w-4 shrink-0" aria-hidden="true" />
              <span>{sanitizeRotationText(payload.warning)}</span>
            </div>
          ) : null}

          <section data-testid="rotation-radar-summary-band" className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <SummaryCell title="Top-N" value={`${rankedThemes.length}/${payload.themes.length}`} accent="text-cyan-200">
              <span>默认显示前 {TOP_THEME_LIMIT} 个主题。</span>
            </SummaryCell>
            <SummaryCell title="最强主题" value={summaryTitle(payload.summary.strongestThemes, rankedThemes[0]?.name || '等待真实行情')} accent="text-emerald-200" />
            <SummaryCell title="扩张主题" value={summaryTitle(payload.summary.acceleratingThemes, '暂无扩张确认')} accent="text-cyan-200" />
            <SummaryCell title="降温/弱信号" value={summaryTitle(payload.summary.fadingThemes, '暂无降温列表')} accent="text-amber-200" />
          </section>

          <ModeControls
            selectedMarket={selectedMarket}
            supportedMarkets={payload.supportedMarkets || ['US', 'CN', 'HK', 'CRYPTO']}
            onMarketChange={setSelectedMarket}
          />

          <div className="mt-4 grid min-w-0 grid-cols-1 gap-4 xl:grid-cols-12 xl:items-start">
            <section className="min-w-0 space-y-4 xl:col-span-8" aria-label="今日轮动 Top-N">
              <GlassCard as="section" className="p-4">
                <div className="flex min-w-0 items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[10px] font-bold uppercase text-white/35">Top-N Radar</p>
                    <h2 className="mt-1 truncate text-base font-semibold text-white">轮动领导榜</h2>
                  </div>
                  <div className="hidden min-w-0 grid-cols-[5rem_5rem_5rem] gap-2 text-right text-[10px] font-semibold uppercase text-white/32 sm:grid">
                    <span>相对</span>
                    <span>量能</span>
                    <span>广度</span>
                  </div>
                </div>
                <div data-testid="rotation-radar-leader-list" className="mt-3 grid gap-2">
                  {rankedThemes.map((theme, index) => (
                    <LeaderRow
                      key={theme.id}
                      theme={theme}
                      rank={index + 1}
                      selected={selectedTheme?.id === theme.id}
                      onSelect={() => {
                        setSelectedThemeId(theme.id);
                        setProxyOpenThemeId('');
                      }}
                    />
                  ))}
                </div>
              </GlassCard>

              <BucketPanel buckets={buckets} />

              <GlassCard as="section" data-testid="rotation-radar-universe-list" className="p-4">
                <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <p className="text-[10px] font-bold uppercase text-white/35">完整主题库</p>
                    <p className="mt-1 truncate text-sm text-white/50">{filteredThemes.length}/{payload.themes.length} 个条目，紧凑列表选择。</p>
                  </div>
                  <label className="relative min-w-0 sm:w-72">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/35" aria-hidden="true" />
                    <input
                      className="h-10 w-full rounded-xl border border-white/10 bg-black/30 py-2 pl-9 pr-3 text-sm text-white/78 outline-none transition-all placeholder:text-white/30 focus:border-cyan-200/30 focus:bg-white/[0.035]"
                      value={searchQuery}
                      onChange={(event) => setSearchQuery(event.target.value)}
                      placeholder="搜索主题、英文名或成员"
                    />
                  </label>
                </div>
                <div className="mt-3 grid max-h-80 gap-1.5 overflow-y-auto no-scrollbar">
                  {filteredThemes.map((theme) => (
                    <CompactThemeRow
                      key={theme.id}
                      theme={theme}
                      selected={selectedTheme?.id === theme.id}
                      onSelect={() => {
                        setSelectedThemeId(theme.id);
                        setProxyOpenThemeId('');
                      }}
                    />
                  ))}
                  {!filteredThemes.length ? (
                    <p className="rounded-xl border border-white/[0.04] bg-black/20 px-3 py-3 text-sm text-white/42">没有匹配主题。</p>
                  ) : null}
                </div>
              </GlassCard>
            </section>

            <div className="min-w-0 xl:col-span-4">
              <ThemeDetailPanel
                theme={selectedTheme}
                isProxyOpen={selectedTheme ? proxyOpenThemeId === selectedTheme.id : false}
                onProxyToggle={(open) => setProxyOpenThemeId(open && selectedTheme ? selectedTheme.id : '')}
              />
            </div>
          </div>

          <details
            data-testid="rotation-radar-mechanics-details"
            className="mt-4 rounded-2xl border border-white/5 bg-white/[0.02] p-4 text-sm text-white/55"
          >
            <summary className="cursor-pointer list-none text-[11px] font-bold uppercase text-white/42">
              数据说明
            </summary>
            <div className="mt-3 flex min-w-0 flex-wrap items-center gap-2 text-[11px] text-white/46">
              <Gauge className="h-4 w-4 text-cyan-200/70" aria-hidden="true" />
              <span>当前为静态主题库，本地行情覆盖后可计算轮动强度。</span>
              <Signal className="ml-2 h-4 w-4 text-emerald-200/70" aria-hidden="true" />
              <span>不代表实时买卖信号，不触发交易、通知、组合或新的外部数据请求。</span>
              <Waves className="ml-2 h-4 w-4 text-white/40" aria-hidden="true" />
              <span>{payload.noAdviceDisclosure}</span>
            </div>
          </details>
        </>
      ) : null}
    </div>
  );
};

export default MarketRotationRadarPage;
