import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import type { MarketOverviewItem, MarketOverviewPanel } from '../api/marketOverview';
import { marketOverviewApi } from '../api/marketOverview';
import type {
  CnShortSentimentResponse,
  MarketBriefingResponse,
  MarketFutureItem,
  MarketFuturesResponse,
  MarketTemperatureResponse,
  MarketTemperatureScore,
} from '../api/market';
import { marketApi } from '../api/market';
import { CryptoCard } from '../components/market-overview/CryptoCard';
import { FundsFlowCard } from '../components/market-overview/FundsFlowCard';
import { MacroIndicatorsCard } from '../components/market-overview/MacroIndicatorsCard';
import { MarketSentimentCard } from '../components/market-overview/MarketSentimentCard';
import { MarketOverviewCard } from '../components/market-overview/MarketOverviewCard';
import { VolatilityCard } from '../components/market-overview/VolatilityCard';
import { resolveMarketOverviewDisplayLabel } from '../components/market-overview/marketOverviewLabels';
import {
  DataFreshnessBadge,
  MARKET_OVERVIEW_CARD_TITLE_CLASS,
  MARKET_OVERVIEW_GHOST_CARD_CLASS,
  MarketOverviewPanelFooter,
  MarketOverviewRefreshButton,
  MarketOverviewSparkline,
} from '../components/market-overview/marketOverviewPrimitives';
import { useI18n } from '../contexts/UiLanguageContext';
import { GlassCard } from '../components/common';
import { cn } from '../utils/cn';

type PanelState = {
  indices?: MarketOverviewPanel;
  volatility?: MarketOverviewPanel;
  crypto?: MarketOverviewPanel;
  sentiment?: MarketOverviewPanel;
  fundsFlow?: MarketOverviewPanel;
  macro?: MarketOverviewPanel;
  cnIndices?: MarketOverviewPanel;
  cnBreadth?: MarketOverviewPanel;
  cnFlows?: MarketOverviewPanel;
  sectorRotation?: MarketOverviewPanel;
  rates?: MarketOverviewPanel;
  fxCommodities?: MarketOverviewPanel;
  temperature: MarketTemperatureResponse;
  briefing: MarketBriefingResponse;
  futures: MarketFuturesResponse;
  cnShortSentiment: CnShortSentimentResponse;
};

type PanelKey = keyof PanelState;
type CardKey = Exclude<PanelKey, 'temperature' | 'briefing'>;
type MarketOverviewTab = 'all' | 'us' | 'cn' | 'global' | 'crypto';
type CardCoverageKind = 'real' | 'mixed' | 'fallback';
type CryptoRealtimeStatus = 'live' | 'reconnecting' | 'snapshot';

const CATEGORY_LAYOUT: Record<MarketOverviewTab, {
  primary: CardKey[];
  secondary: CardKey[];
  fallback: CardKey[];
}> = {
  all: {
    primary: ['indices', 'cnIndices', 'crypto', 'volatility', 'fundsFlow', 'macro'],
    secondary: ['rates', 'fxCommodities', 'sentiment', 'futures'],
    fallback: ['cnBreadth', 'cnFlows', 'sectorRotation', 'cnShortSentiment'],
  },
  us: {
    primary: ['indices', 'volatility', 'fundsFlow', 'macro'],
    secondary: ['rates', 'sentiment', 'fxCommodities', 'futures'],
    fallback: [],
  },
  cn: {
    primary: ['cnIndices', 'cnBreadth', 'cnFlows', 'sectorRotation', 'cnShortSentiment'],
    secondary: ['futures', 'fxCommodities', 'rates'],
    fallback: [],
  },
  global: {
    primary: ['macro', 'rates', 'fxCommodities', 'indices'],
    secondary: ['volatility', 'futures', 'sentiment'],
    fallback: [],
  },
  crypto: {
    primary: ['crypto', 'volatility', 'macro'],
    secondary: ['fxCommodities', 'rates', 'sentiment'],
    fallback: [],
  },
};

const CATEGORY_CARDS: Record<MarketOverviewTab, CardKey[]> = Object.fromEntries(
  Object.entries(CATEGORY_LAYOUT).map(([tab, layout]) => [
    tab,
    [...layout.primary, ...layout.secondary, ...layout.fallback],
  ]),
) as Record<MarketOverviewTab, CardKey[]>;

const CARD_LAYOUT_META: Record<CardKey, {
  size: 'wide' | 'normal' | 'compact';
  priority: 'primary' | 'secondary' | 'fallback';
}> = {
  indices: { size: 'wide', priority: 'primary' },
  cnIndices: { size: 'wide', priority: 'primary' },
  crypto: { size: 'wide', priority: 'primary' },
  volatility: { size: 'normal', priority: 'primary' },
  fundsFlow: { size: 'normal', priority: 'primary' },
  macro: { size: 'normal', priority: 'primary' },
  rates: { size: 'normal', priority: 'secondary' },
  fxCommodities: { size: 'normal', priority: 'secondary' },
  sentiment: { size: 'compact', priority: 'secondary' },
  futures: { size: 'compact', priority: 'secondary' },
  cnBreadth: { size: 'normal', priority: 'fallback' },
  cnFlows: { size: 'normal', priority: 'fallback' },
  sectorRotation: { size: 'normal', priority: 'fallback' },
  cnShortSentiment: { size: 'compact', priority: 'fallback' },
};
const AUTO_REFRESH_MS = 60_000;
const PANEL_REQUEST_TIMEOUT_MS = 3_000;

const FALLBACK_TEMPERATURE: MarketTemperatureResponse = {
  source: 'fallback',
  sourceLabel: '备用数据',
  updatedAt: new Date(0).toISOString(),
  freshness: 'fallback',
  isFallback: true,
  warning: '当前真实数据不足，市场温度仅供界面演示',
  confidence: 0,
  reliableInputCount: 0,
  fallbackInputCount: 0,
  excludedInputCount: 0,
  isReliable: false,
  scores: {
    overall: { value: 50, label: '数据不足', trend: 'stable', description: '当前真实数据不足，市场温度仅供界面演示。' },
    usRiskAppetite: { value: 50, label: '数据不足', trend: 'stable', description: '当前真实数据不足，市场温度仅供界面演示。' },
    cnMoneyEffect: { value: 50, label: '数据不足', trend: 'stable', description: '当前真实数据不足，市场温度仅供界面演示。' },
    macroPressure: { value: 50, label: '数据不足', trend: 'stable', description: '当前真实数据不足，市场温度仅供界面演示。' },
    liquidity: { value: 50, label: '数据不足', trend: 'stable', description: '当前真实数据不足，市场温度仅供界面演示。' },
  },
};

const FALLBACK_BRIEFING: MarketBriefingResponse = {
  source: 'fallback',
  sourceLabel: '备用数据',
  updatedAt: new Date(0).toISOString(),
  freshness: 'fallback',
  isFallback: true,
  warning: '当前真实数据不足，暂不生成强市场判断。',
  confidence: 0,
  reliableInputCount: 0,
  fallbackInputCount: 0,
  excludedInputCount: 0,
  isReliable: false,
  items: [
    { title: '当前真实数据不足', message: '当前真实数据不足，暂不生成强市场判断。', severity: 'warning', category: 'risk', confidence: 0 },
    { title: '备用数据已降级', message: '备用示例数据仅用于保持界面结构，不参与市场温度评分。', severity: 'neutral', category: 'risk', confidence: 0 },
    { title: '等待真实行情源', message: '接入足够真实输入后，再恢复风险偏好、赚钱效应和流动性判断。', severity: 'neutral', category: 'risk', confidence: 0 },
  ],
};

const FALLBACK_FUTURES: MarketFuturesResponse = {
  source: 'fallback',
  sourceLabel: '备用数据',
  updatedAt: new Date(0).toISOString(),
  freshness: 'fallback',
  isFallback: true,
  warning: '备用示例数据，不代表当前行情',
  items: [
    { name: '纳指期货', symbol: 'NQ', value: 18420.5, change: 65.2, changePercent: 0.35, market: 'US', session: 'premarket', sparkline: [18320, 18380, 18420.5], source: 'fallback', sourceLabel: '备用数据', freshness: 'fallback', isFallback: true, warning: '备用示例数据，不代表当前行情' },
    { name: '标普500期货', symbol: 'ES', value: 5238.25, change: 14.5, changePercent: 0.28, market: 'US', session: 'premarket', sparkline: [5208, 5218, 5238.25], source: 'fallback', sourceLabel: '备用数据', freshness: 'fallback', isFallback: true, warning: '备用示例数据，不代表当前行情' },
    { name: '道指期货', symbol: 'YM', value: 38980, change: 72, changePercent: 0.19, market: 'US', session: 'premarket', sparkline: [38820, 38930, 38980], source: 'fallback', sourceLabel: '备用数据', freshness: 'fallback', isFallback: true, warning: '备用示例数据，不代表当前行情' },
    { name: '罗素2000期货', symbol: 'RTY', value: 2094.6, change: -3.8, changePercent: -0.18, market: 'US', session: 'premarket', sparkline: [2108, 2098, 2094.6], source: 'fallback', sourceLabel: '备用数据', freshness: 'fallback', isFallback: true, warning: '备用示例数据，不代表当前行情' },
    { name: '富时A50期货', symbol: 'CN00Y', value: 12580, change: 38, changePercent: 0.3, market: 'CN', session: 'day', sparkline: [12420, 12542, 12580], source: 'fallback', sourceLabel: '备用数据', freshness: 'fallback', isFallback: true, warning: '备用示例数据，不代表当前行情' },
    { name: '恒指期货', symbol: 'HSI_F', value: 17712, change: 128, changePercent: 0.73, market: 'HK', session: 'day', sparkline: [17490, 17640, 17712], source: 'fallback', sourceLabel: '备用数据', freshness: 'fallback', isFallback: true, warning: '备用示例数据，不代表当前行情' },
  ],
};

const FALLBACK_CRYPTO_PANEL: MarketOverviewPanel = {
  panelName: 'CryptoCard',
  lastRefreshAt: new Date(0).toISOString(),
  status: 'failure',
  source: 'fallback',
  sourceLabel: '备用数据',
  updatedAt: new Date(0).toISOString(),
  asOf: new Date(0).toISOString(),
  freshness: 'fallback',
  isFallback: true,
  isRefreshing: true,
  warning: '正在刷新，稍后自动更新',
  items: [
    { symbol: 'BTC', label: 'Bitcoin', value: 75800, unit: 'USD', changePct: -0.2, riskDirection: 'increasing', trend: [75220, 75640, 76110, 75800], source: 'fallback', sourceLabel: '备用数据', freshness: 'fallback', isFallback: true, warning: '正在刷新，稍后自动更新' },
    { symbol: 'ETH', label: 'Ethereum', value: 3120, unit: 'USD', changePct: -0.4, riskDirection: 'increasing', trend: [3090, 3148, 3162, 3120], source: 'fallback', sourceLabel: '备用数据', freshness: 'fallback', isFallback: true, warning: '正在刷新，稍后自动更新' },
    { symbol: 'BNB', label: 'BNB', value: 590, unit: 'USD', changePct: 0.3, riskDirection: 'decreasing', trend: [584, 588, 586, 590], source: 'fallback', sourceLabel: '备用数据', freshness: 'fallback', isFallback: true, warning: '正在刷新，稍后自动更新' },
  ],
};

const FALLBACK_CN_SHORT_SENTIMENT: CnShortSentimentResponse = {
  source: 'fallback',
  sourceLabel: '备用数据',
  updatedAt: new Date(0).toISOString(),
  freshness: 'fallback',
  isFallback: true,
  warning: '备用示例数据，不代表当前行情',
  sentimentScore: 50,
  summary: '暂未接入真实数据源，当前为备用示例数据。',
  metrics: {
    limitUpCount: 68,
    limitDownCount: 18,
    failedLimitUpRate: 24.5,
    maxConsecutiveLimitUps: 5,
    yesterdayLimitUpPerformance: 2.8,
    firstBoardCount: 42,
    secondBoardCount: 12,
    highBoardCount: 6,
    twentyCmLimitUpCount: 9,
    stRiskLevel: 'normal',
  },
};

type HeroAnchor = {
  key: string;
  label: string;
  item?: MarketOverviewItem;
};

function findPanelItem(panel: MarketOverviewPanel | undefined, symbols: string[]): MarketOverviewItem | undefined {
  const normalizedSymbols = symbols.map((symbol) => symbol.toUpperCase());
  return panel?.items.find((item) => normalizedSymbols.includes(item.symbol.toUpperCase()));
}

function buildHeroAnchors(panels: PanelState): HeroAnchor[] {
  return [
    { key: 'SPX', label: '标普500', item: findPanelItem(panels.indices, ['SPX']) },
    { key: 'CSI300', label: '沪深300', item: findPanelItem(panels.cnIndices, ['CSI300', '000300.SH']) || findPanelItem(panels.indices, ['CSI300']) },
    { key: 'BTC', label: '比特币', item: findPanelItem(panels.crypto, ['BTC']) },
    { key: 'VIX', label: '恐慌指数', item: findPanelItem(panels.volatility, ['VIX']) },
    { key: 'US10Y', label: '美债10年期', item: findPanelItem(panels.rates, ['US10Y']) || findPanelItem(panels.macro, ['US10Y']) },
    { key: 'DXY', label: '美元指数', item: findPanelItem(panels.fxCommodities, ['DXY']) || findPanelItem(panels.macro, ['DXY']) },
  ];
}

function formatHeroValue(value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '-';
  }
  return new Intl.NumberFormat('en-US', {
    maximumFractionDigits: Math.abs(value) >= 100 ? 2 : 3,
  }).format(value);
}

function formatHeroChange(value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return 'N/A';
  }
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}

function heroToneClass(item: MarketOverviewItem | undefined): string {
  if (!item || item.changePct == null) {
    return 'text-white/35';
  }
  return item.changePct >= 0
    ? 'text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.36)]'
    : 'text-rose-400 drop-shadow-[0_0_8px_rgba(251,113,133,0.36)]';
}

const CrossAssetHeroRibbon: React.FC<{ anchors: HeroAnchor[] }> = ({ anchors }) => (
  <GlassCard
    as="section"
    data-testid="market-overview-hero-ribbon"
    className={cn(MARKET_OVERVIEW_GHOST_CARD_CLASS, 'overflow-hidden p-0')}
    aria-label="Cross asset hero ribbon"
  >
    <div className="grid grid-cols-2 divide-x divide-y divide-white/5 sm:grid-cols-3 md:grid-cols-6 md:divide-y-0">
      {anchors.map((anchor) => {
        const displayLabel = anchor.item ? resolveMarketOverviewDisplayLabel(anchor.item) : { primary: anchor.label, secondary: anchor.key };
        return (
          <div
            key={anchor.key}
            data-testid={`market-overview-hero-${anchor.key}`}
            className="min-w-0 bg-white/[0.02] px-4 py-3.5"
          >
            <p className="block truncate text-[10px] font-semibold uppercase tracking-widest text-white/50">
              {displayLabel.primary}
              {displayLabel.secondary ? <span className="ml-1 text-white/28">({displayLabel.secondary})</span> : null}
            </p>
            <p className="mt-1 truncate font-mono text-[22px] font-semibold leading-none text-white md:text-2xl">
              {formatHeroValue(anchor.item?.value)}
            </p>
            <p className={`mt-1 font-mono text-xs font-semibold ${heroToneClass(anchor.item)}`}>
              {formatHeroChange(anchor.item?.changePct)}
            </p>
          </div>
        );
      })}
    </div>
  </GlassCard>
);

function formatNumber(value: number | null | undefined, digits = 2): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '-';
  }
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: digits }).format(value);
}

function scoreTone(score: MarketTemperatureScore, pressure = false): string {
  if (pressure) {
    return score.value >= 65 ? 'text-rose-400' : score.value >= 55 ? 'text-amber-300' : 'text-emerald-400';
  }
  return score.value >= 76 ? 'text-amber-200' : score.value >= 61 ? 'text-emerald-400' : score.value <= 45 ? 'text-sky-300' : 'text-white';
}

function confidenceLabel(confidence?: number): string {
  if (confidence === 0) {
    return '数据不足';
  }
  if (confidence == null) {
    return '中';
  }
  if (confidence >= 0.75) {
    return '高';
  }
  if (confidence >= 0.45) {
    return '中';
  }
  return '低';
}

function isTemperatureReliable(data: MarketTemperatureResponse): boolean {
  return Boolean(
    data.isReliable !== false
    && (data.confidence == null || data.confidence >= 0.45)
    && (data.reliableInputCount == null || data.reliableInputCount >= 3),
  );
}

function isFallbackOnlyMeta(meta: {
  source?: string;
  freshness?: string;
  isFallback?: boolean;
  isReliable?: boolean;
  metadata?: { isReliable?: boolean };
  items?: Array<{ source?: string; freshness?: string; isFallback?: boolean }>;
}): boolean {
  const items = meta.items || [];
  return Boolean(
    meta.source === 'fallback'
    || meta.freshness === 'fallback'
    || meta.isFallback
    || meta.isReliable === false
    || meta.metadata?.isReliable === false
    || (items.length > 0 && items.every((item) => item.isFallback || item.freshness === 'fallback' || item.source === 'fallback')),
  );
}

function isItemFallback(item: { source?: string; freshness?: string; isFallback?: boolean }): boolean {
  return Boolean(item.isFallback || item.freshness === 'fallback' || item.source === 'fallback');
}

function getCardMeta(panels: PanelState, cardKey: CardKey): {
  source?: string;
  freshness?: string;
  isFallback?: boolean;
  isReliable?: boolean;
  metadata?: { isReliable?: boolean };
  items?: Array<{ source?: string; freshness?: string; isFallback?: boolean }>;
} {
  if (cardKey === 'futures') {
    return panels.futures;
  }
  if (cardKey === 'cnShortSentiment') {
    return panels.cnShortSentiment;
  }
  return panels[cardKey] || {};
}

function getCardCoverageKind(panels: PanelState, cardKey: CardKey): CardCoverageKind {
  const meta = getCardMeta(panels, cardKey);
  const items = meta.items || [];
  if (!meta.source && !meta.freshness && items.length === 0) {
    return 'fallback';
  }
  if (meta.source === 'error' || meta.freshness === 'error') {
    return 'mixed';
  }
  if (isFallbackOnlyMeta(meta)) {
    return 'fallback';
  }
  if (meta.source === 'mixed' || items.some(isItemFallback)) {
    return 'mixed';
  }
  return 'real';
}

function summarizeCardCoverage(panels: PanelState, cards: CardKey[]): Record<CardCoverageKind, number> {
  return cards.reduce<Record<CardCoverageKind, number>>((summary, cardKey) => {
    summary[getCardCoverageKind(panels, cardKey)] += 1;
    return summary;
  }, { real: 0, mixed: 0, fallback: 0 });
}

type FreshnessCountKey = 'live' | 'delayed' | 'cached' | 'stale' | 'fallback' | 'mock' | 'error';
type DataQualitySummary = {
  status: string;
  counts: Record<FreshnessCountKey, number>;
  hasConcern: boolean;
};

function collectFreshnessValues(panels: PanelState): FreshnessCountKey[] {
  const values: FreshnessCountKey[] = [];
  const push = (freshness?: string, isFallback?: boolean, isStale?: boolean) => {
    if (freshness && ['live', 'delayed', 'cached', 'stale', 'fallback', 'mock', 'error'].includes(freshness)) {
      values.push(freshness as FreshnessCountKey);
    } else if (isFallback) {
      values.push('fallback');
    } else if (isStale) {
      values.push('stale');
    } else {
      values.push('cached');
    }
  };
  const panelKeys: CardKey[] = ['indices', 'volatility', 'crypto', 'sentiment', 'fundsFlow', 'macro', 'cnIndices', 'cnBreadth', 'cnFlows', 'sectorRotation', 'rates', 'fxCommodities'];
  panelKeys.forEach((key) => {
    const panel = panels[key] as MarketOverviewPanel | undefined;
    if (!panel) {
      return;
    }
    push(panel.freshness, panel.isFallback, panel.isStale);
    panel.items.forEach((item) => push(item.freshness, item.isFallback, item.isStale));
  });
  push(panels.temperature.freshness, panels.temperature.isFallback, panels.temperature.isStale);
  push(panels.briefing.freshness, panels.briefing.isFallback, panels.briefing.isStale);
  push(panels.futures.freshness, panels.futures.isFallback, panels.futures.isStale);
  panels.futures.items.forEach((item) => push(item.freshness, item.isFallback, item.isStale));
  push(panels.cnShortSentiment.freshness, panels.cnShortSentiment.isFallback, panels.cnShortSentiment.isStale);
  return values;
}

function summarizeDataQuality(panels: PanelState): DataQualitySummary {
  const counts: Record<FreshnessCountKey, number> = {
    live: 0,
    delayed: 0,
    cached: 0,
    stale: 0,
    fallback: 0,
    mock: 0,
    error: 0,
  };
  collectFreshnessValues(panels).forEach((freshness) => {
    counts[freshness] += 1;
  });
  const status = counts.error > 0
    ? '异常'
    : counts.stale > 0
      ? '存在旧数据'
      : counts.fallback + counts.mock > 0
        ? '部分备用'
        : '良好';
  return {
    status,
    counts,
    hasConcern: counts.fallback + counts.mock + counts.stale + counts.error > 0,
  };
}

const DataQualityOverview: React.FC<{ summary: DataQualitySummary }> = ({ summary }) => {
  const countItems: Array<[FreshnessCountKey, string]> = [
    ['live', '实时'],
    ['delayed', '延迟'],
    ['cached', '快照'],
    ['fallback', '备用'],
    ['stale', '旧数据'],
    ['mock', '模拟'],
    ['error', '异常'],
  ];
  return (
    <GlassCard as="section" data-testid="market-data-quality" className={MARKET_OVERVIEW_GHOST_CARD_CLASS}>
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-white/40">DATA QUALITY</p>
          <h2 className="mt-1 text-lg font-semibold text-white">当前数据质量：{summary.status}</h2>
          {summary.hasConcern ? (
            <p className="mt-1 text-xs leading-5 text-amber-200/75">部分数据为备用或旧快照，请以交易所/券商行情为准。</p>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          {countItems.filter(([key]) => summary.counts[key] > 0).map(([key, label]) => (
            <div key={key} className="flex items-center gap-1.5 rounded-lg border border-white/[0.06] bg-white/[0.025] px-2 py-1">
              <DataFreshnessBadge freshness={key} />
              <span className="font-mono text-xs text-white/70">{summary.counts[key]}</span>
              <span className="sr-only">{label}</span>
            </div>
          ))}
        </div>
      </div>
    </GlassCard>
  );
};

const CategoryCoverageSummary: React.FC<{
  label: string;
  summary: Record<CardCoverageKind, number>;
}> = ({ label, summary }) => (
  <div
    data-testid="market-overview-coverage-summary"
    className="rounded-lg border border-white/[0.06] bg-white/[0.025] px-4 py-3 text-sm text-white/70"
  >
    <span className="font-semibold text-white/82">{label}数据覆盖：</span>
    <span className="font-mono">真实 {summary.real} · 混合 {summary.mixed} · 备用 {summary.fallback}</span>
  </div>
);

const PendingDataSourceSection: React.FC<{
  expanded: boolean;
  fallbackCount: number;
  onToggle: () => void;
  children: React.ReactNode;
}> = ({ expanded, fallbackCount, onToggle, children }) => (
  <section
    data-testid="market-overview-fallback-section"
    className="w-full rounded-xl border border-white/5 bg-white/[0.02] p-3 backdrop-blur-md transition-all hover:border-white/10"
  >
    <button
      type="button"
      className="flex w-full items-center justify-between gap-4 text-left"
      aria-expanded={expanded}
      onClick={onToggle}
    >
      <div>
        <h2 className="text-sm font-semibold text-white/78">待接入真实数据源</h2>
        <p className="mt-1 text-xs leading-5 text-white/45">以下模块当前使用备用示例数据，不参与市场温度评分。</p>
      </div>
      <span className="shrink-0 rounded-full border border-white/[0.07] bg-white/[0.025] px-2.5 py-1 text-xs font-semibold text-white/55">
        {expanded ? '收起' : `展开 ${fallbackCount}`}
      </span>
    </button>
    {expanded ? <div className="mt-4">{children}</div> : null}
  </section>
);

const CategoryEmptyState: React.FC<{
  onShowPending: () => void;
}> = ({ onShowPending }) => (
  <section
    data-testid="market-overview-category-empty-state"
    className="rounded-xl border border-white/5 bg-white/[0.02] px-4 py-4 backdrop-blur-md transition-all hover:border-white/10"
  >
    <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <p className="text-sm leading-6 text-white/62">
        当前分类暂无可用真实数据，备用模块已移入待接入真实数据源。
      </p>
      <button
        type="button"
        className="w-fit rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-1.5 text-xs font-semibold text-white/68 transition hover:bg-white/[0.06] hover:text-white"
        onClick={onShowPending}
      >
        查看待接入模块
      </button>
    </div>
  </section>
);

const MarketTemperatureStrip: React.FC<{
  data: MarketTemperatureResponse;
  refreshing: boolean;
  onRefresh: () => void;
}> = ({ data, refreshing, onRefresh }) => {
  const { t } = useI18n();
  const [showPlaceholderScores, setShowPlaceholderScores] = useState(false);
  const scores: Array<{ key: keyof MarketTemperatureResponse['scores']; label: string; pressure?: boolean }> = [
    { key: 'overall', label: t('marketOverviewPage.temperature.overall') },
    { key: 'usRiskAppetite', label: t('marketOverviewPage.temperature.usRiskAppetite') },
    { key: 'cnMoneyEffect', label: t('marketOverviewPage.temperature.cnMoneyEffect') },
    { key: 'macroPressure', label: t('marketOverviewPage.temperature.macroPressure'), pressure: true },
    { key: 'liquidity', label: t('marketOverviewPage.temperature.liquidity') },
  ];
  const isReliable = isTemperatureReliable(data);
  const confidenceText = confidenceLabel(data.confidence);
  const shouldShowScores = isReliable || showPlaceholderScores;
  return (
    <GlassCard as="section" data-testid="market-temperature-strip" className={MARKET_OVERVIEW_GHOST_CARD_CLASS}>
      <div className="mb-3 flex items-center justify-between gap-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-white/40">{t('marketOverviewPage.temperature.eyebrow')}</p>
          <h2 className="mt-1 text-lg font-semibold text-white">{t('marketOverviewPage.temperature.title')}</h2>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
            <span className={cn(
              'rounded-full border px-2 py-0.5 font-semibold',
              isReliable ? 'border-emerald-300/20 bg-emerald-400/8 text-emerald-100' : 'border-orange-300/25 bg-orange-400/10 text-orange-100',
            )}>
              可信度：{confidenceText}
            </span>
            {data.reliableInputCount != null || data.excludedInputCount != null ? (
              <span className="text-white/38">
                真实输入 {data.reliableInputCount ?? 0} · 备用 {data.fallbackInputCount ?? 0} · 排除 {data.excludedInputCount ?? 0} · confidence {formatNumber(data.confidence, 2)}
              </span>
            ) : null}
          </div>
        </div>
        <MarketOverviewRefreshButton label={t('marketOverviewPage.refreshCard', { title: t('marketOverviewPage.temperature.title') })} refreshing={refreshing} onRefresh={onRefresh} />
      </div>
      {!isReliable ? (
        <div className="mb-3 rounded-lg border border-white/[0.06] bg-white/[0.025] px-3 py-3" data-testid="market-temperature-unreliable-summary">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-sm font-semibold text-white">市场温度：数据不足</p>
              <p className="mt-1 text-xs leading-5 text-white/55">
                {(data.reliableInputCount ?? 0) > 0 ? '真实输入不足，暂不生成综合判断。' : '当前真实数据源不足，暂不生成综合判断。'}
              </p>
            </div>
            <div className="flex flex-wrap gap-2 text-[11px] text-white/55">
              <span className="rounded-full border border-white/[0.06] bg-white/[0.025] px-2 py-1">真实 {data.reliableInputCount ?? 0}</span>
              <span className="rounded-full border border-white/[0.06] bg-white/[0.025] px-2 py-1">备用 {data.fallbackInputCount ?? 0}</span>
              <span className="rounded-full border border-white/[0.06] bg-white/[0.025] px-2 py-1">排除 {data.excludedInputCount ?? 0}</span>
              <span className="rounded-full border border-white/[0.06] bg-white/[0.025] px-2 py-1">confidence {formatNumber(data.confidence, 2)}</span>
            </div>
          </div>
          <button
            type="button"
            className="mt-3 rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-1.5 text-xs font-semibold text-white/65 transition hover:bg-white/[0.06] hover:text-white"
            aria-expanded={showPlaceholderScores}
            onClick={() => setShowPlaceholderScores((current) => !current)}
          >
            {showPlaceholderScores ? '收起占位评分' : '查看占位评分'}
          </button>
        </div>
      ) : null}
      {shouldShowScores ? (
        <div className="flex gap-2 overflow-x-auto pb-1 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {scores.map(({ key, label, pressure }) => {
            const score = data.scores[key];
            return (
              <div key={key} className={cn('min-w-[188px] flex-1 rounded-lg border px-3 py-2.5', isReliable ? 'border-white/[0.06] bg-white/[0.025]' : 'border-white/[0.045] bg-white/[0.015]')} title={score.description}>
                <div className="flex items-start justify-between gap-3">
                  <p className="text-[11px] font-semibold text-white/60">{label}</p>
                  <span className="rounded-full bg-white/[0.06] px-2 py-0.5 text-[10px] font-semibold text-white/55">{score.label}</span>
                </div>
                <div className="mt-2 flex items-end gap-2">
                  <span className={cn('font-mono text-3xl font-semibold leading-none', isReliable ? scoreTone(score, pressure) : 'text-white/55')}>{score.value}</span>
                  <span className="pb-0.5 text-[10px] uppercase tracking-widest text-white/30">{score.trend}</span>
                </div>
                <p className="mt-2 line-clamp-2 text-xs leading-5 text-white/45">{score.description}</p>
              </div>
            );
          })}
        </div>
      ) : null}
      <MarketOverviewPanelFooter
        meta={data}
        sourceLabel={data.sourceLabel || data.source}
      />
    </GlassCard>
  );
};

const severityClass: Record<string, string> = {
  positive: 'border-emerald-300/20 bg-emerald-400/8 text-emerald-100',
  neutral: 'border-white/8 bg-white/[0.025] text-white/70',
  warning: 'border-amber-300/20 bg-amber-400/8 text-amber-100',
  risk: 'border-rose-300/20 bg-rose-400/8 text-rose-100',
};

const MarketBriefingCard: React.FC<{
  data: MarketBriefingResponse;
  refreshing: boolean;
  onRefresh: () => void;
}> = ({ data, refreshing, onRefresh }) => {
  const { t } = useI18n();
  const title = t('marketOverviewPage.briefing.title');
  const hasWarning = Boolean(data.warning);
  const isReliable = !hasWarning && data.isReliable !== false && (data.confidence == null || data.confidence >= 0.45);
  return (
    <GlassCard as="section" data-testid="market-briefing-card" className={MARKET_OVERVIEW_GHOST_CARD_CLASS}>
      <div className="mb-3 flex items-center justify-between gap-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-white/40">{t('marketOverviewPage.briefing.eyebrow')}</p>
          <h2 className="mt-1 text-lg font-semibold text-white">{title}</h2>
        </div>
        <MarketOverviewRefreshButton label={t('marketOverviewPage.refreshCard', { title })} refreshing={refreshing} onRefresh={onRefresh} />
      </div>
      {data.warning ? (
        <div className="mb-3 rounded-lg border border-amber-300/25 bg-amber-400/10 px-3 py-2 text-xs leading-5 text-amber-100/85" data-testid="market-briefing-warning">
          {data.warning}
        </div>
      ) : null}
      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {data.items.slice(0, hasWarning || !isReliable ? 3 : 5).map((item) => {
          const lowConfidence = !isReliable || (item.confidence != null && item.confidence < 0.45);
          return (
          <article key={`${item.category}-${item.title}`} className={cn('rounded-lg border px-3 py-2.5', lowConfidence ? severityClass.neutral : severityClass[item.severity] || severityClass.neutral)}>
            <div className="flex items-start justify-between gap-2">
              <p className="text-xs font-semibold">{item.title}</p>
              {item.confidence != null ? <span className="shrink-0 text-[10px] text-white/35">{confidenceLabel(item.confidence)}</span> : null}
            </div>
            <p className="mt-1 text-xs leading-5 opacity-75">{item.message}</p>
          </article>
          );
        })}
      </div>
      <MarketOverviewPanelFooter
        meta={data}
        sourceLabel={data.sourceLabel || data.source}
      />
    </GlassCard>
  );
};

const FuturesPremarketCard: React.FC<{
  data: MarketFuturesResponse;
  loading?: boolean;
  refreshing?: boolean;
  onRefresh: () => void;
}> = ({ data, loading = false, refreshing = false, onRefresh }) => {
  const { t } = useI18n();
  const title = t('marketOverviewPage.cards.futures.title');
  const panel: MarketOverviewPanel = {
    panelName: 'FuturesPremarketCard',
    status: data.isFallback ? 'failure' : 'success',
    lastRefreshAt: data.updatedAt,
    source: data.source,
    sourceLabel: data.sourceLabel,
    updatedAt: data.updatedAt,
    asOf: data.asOf,
    freshness: data.freshness,
    isFallback: data.isFallback,
    isStale: data.isStale,
    delayMinutes: data.delayMinutes,
    warning: data.warning,
    items: [],
  };
  const fallbackOnly = isFallbackOnlyMeta({ ...data, items: data.items });
  return (
    <GlassCard as="section" className={cn(MARKET_OVERVIEW_GHOST_CARD_CLASS, 'flex h-full flex-col', fallbackOnly ? 'border-orange-300/12' : '')}>
      <div className="mb-6 flex items-center justify-between gap-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-white/40">{t('marketOverviewPage.cards.futures.eyebrow')}</p>
          <h2 className={cn(MARKET_OVERVIEW_CARD_TITLE_CLASS, 'mt-2')}>{title}</h2>
          <p className="mt-1 text-sm text-white/55">{t('marketOverviewPage.cards.futures.description')}</p>
        </div>
        <MarketOverviewRefreshButton label={t('marketOverviewPage.refreshCard', { title })} refreshing={refreshing} onRefresh={onRefresh} />
      </div>
      {fallbackOnly ? (
        <div className="mb-3 rounded-lg border border-orange-300/20 bg-orange-400/8 px-3 py-2 text-xs leading-5 text-orange-100/85" data-testid="market-overview-fallback-only-notice">
          <p className="font-semibold">暂未接入真实数据源</p>
          <p className="text-orange-100/70">当前为备用示例数据，不参与市场温度评分</p>
        </div>
      ) : null}
      <div className="flex flex-col">
        {data.items.map((item: MarketFutureItem) => {
          const positive = (item.changePercent || 0) >= 0;
          const mutedTone = item.isFallback || item.freshness === 'fallback' || item.source === 'fallback';
          return (
            <article key={item.symbol} className="flex min-h-12 items-center gap-3 border-b border-white/[0.045] py-2.5 last:border-b-0">
              <div className="w-32 shrink-0 min-w-0">
                <p className="truncate text-[10px] font-semibold tracking-widest text-white/65">{item.name}</p>
                <p className="mt-0.5 truncate text-[9px] font-semibold uppercase tracking-widest text-white/25">{item.symbol} / {item.market}</p>
                <div className="mt-1">
                  <DataFreshnessBadge freshness={item.freshness || data.freshness || (item.source === 'fallback' ? 'fallback' : 'cached')} className="px-1.5 text-[9px]" />
                </div>
              </div>
              <div className="w-24 shrink-0">
                <MarketOverviewSparkline values={item.sparkline} tone={mutedTone ? 'text-white/30' : positive ? 'text-emerald-400' : 'text-rose-400'} className="h-8" />
              </div>
              <div className="min-w-0 flex-1 text-right font-mono">
                <p className="truncate text-lg font-semibold leading-none text-white">{formatNumber(item.value)}</p>
                <p className={cn('mt-1 text-[11px] font-bold leading-none', mutedTone ? 'text-white/45' : positive ? 'text-emerald-400' : 'text-rose-400')}>
                  {item.changePercent == null ? 'N/A' : `${item.changePercent >= 0 ? '+' : ''}${item.changePercent.toFixed(2)}%`}
                </p>
              </div>
            </article>
          );
        })}
      </div>
      {loading ? <div className="mt-3 rounded-lg border border-white/8 bg-white/[0.03] p-3 text-sm text-white/60">{t('marketOverviewPage.loading')}</div> : null}
      <MarketOverviewPanelFooter panel={panel} sourceLabel={data.sourceLabel || `${t('marketOverviewPage.cards.futures.source')}: ${data.source.toUpperCase()}`} />
    </GlassCard>
  );
};

const CnShortSentimentCard: React.FC<{
  data: CnShortSentimentResponse;
  loading?: boolean;
  refreshing?: boolean;
  onRefresh: () => void;
}> = ({ data, loading = false, refreshing = false, onRefresh }) => {
  const { t } = useI18n();
  const title = t('marketOverviewPage.cards.cnShortSentiment.title');
  const panel: MarketOverviewPanel = {
    panelName: 'CnShortSentimentCard',
    status: data.isFallback ? 'failure' : 'success',
    lastRefreshAt: data.updatedAt,
    items: [],
    ...data,
  };
  const metrics = [
    ['limitUpCount', t('marketOverviewPage.cards.cnShortSentiment.metrics.limitUpCount'), data.metrics.limitUpCount],
    ['limitDownCount', t('marketOverviewPage.cards.cnShortSentiment.metrics.limitDownCount'), data.metrics.limitDownCount],
    ['failedLimitUpRate', t('marketOverviewPage.cards.cnShortSentiment.metrics.failedLimitUpRate'), `${data.metrics.failedLimitUpRate}%`],
    ['maxConsecutiveLimitUps', t('marketOverviewPage.cards.cnShortSentiment.metrics.maxConsecutiveLimitUps'), data.metrics.maxConsecutiveLimitUps],
    ['yesterdayLimitUpPerformance', t('marketOverviewPage.cards.cnShortSentiment.metrics.yesterdayLimitUpPerformance'), `${data.metrics.yesterdayLimitUpPerformance >= 0 ? '+' : ''}${data.metrics.yesterdayLimitUpPerformance}%`],
    ['firstBoardCount', t('marketOverviewPage.cards.cnShortSentiment.metrics.firstBoardCount'), data.metrics.firstBoardCount],
    ['secondBoardCount', t('marketOverviewPage.cards.cnShortSentiment.metrics.secondBoardCount'), data.metrics.secondBoardCount],
    ['highBoardCount', t('marketOverviewPage.cards.cnShortSentiment.metrics.highBoardCount'), data.metrics.highBoardCount],
    ['twentyCmLimitUpCount', t('marketOverviewPage.cards.cnShortSentiment.metrics.twentyCmLimitUpCount'), data.metrics.twentyCmLimitUpCount],
  ] as const;
  const fallbackOnly = isFallbackOnlyMeta(data);
  return (
    <GlassCard as="section" className={cn(MARKET_OVERVIEW_GHOST_CARD_CLASS, 'flex h-full flex-col', fallbackOnly ? 'border-orange-300/12' : '')}>
      <div className="mb-5 flex items-center justify-between gap-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-white/40">{t('marketOverviewPage.cards.cnShortSentiment.eyebrow')}</p>
          <h2 className={cn(MARKET_OVERVIEW_CARD_TITLE_CLASS, 'mt-2')}>{title}</h2>
        </div>
        <MarketOverviewRefreshButton label={t('marketOverviewPage.refreshCard', { title })} refreshing={refreshing} onRefresh={onRefresh} />
      </div>
      {fallbackOnly ? (
        <div className="mb-3 rounded-lg border border-orange-300/20 bg-orange-400/8 px-3 py-2 text-xs leading-5 text-orange-100/85" data-testid="market-overview-fallback-only-notice">
          <p className="font-semibold">暂未接入真实数据源</p>
          <p className="text-orange-100/70">当前为备用示例数据，不参与市场温度评分</p>
        </div>
      ) : null}
      <div className={MARKET_OVERVIEW_GHOST_CARD_CLASS}>
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="text-xs text-white/45">{t('marketOverviewPage.cards.cnShortSentiment.score')}</p>
            <p className={cn('mt-1 font-mono text-4xl font-semibold', fallbackOnly ? 'text-white/55' : 'text-emerald-400')}>{data.sentimentScore}</p>
          </div>
          <p className="max-w-[220px] text-right text-xs leading-5 text-white/55">{data.summary}</p>
        </div>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2">
        {metrics.map(([key, label, value]) => (
          <div key={key} className={MARKET_OVERVIEW_GHOST_CARD_CLASS}>
            <p className="truncate text-[10px] text-white/38">{label}</p>
            <p className="mt-1 font-mono text-sm font-semibold text-white">{value}</p>
          </div>
        ))}
      </div>
      {loading ? <div className="mt-3 rounded-lg border border-white/8 bg-white/[0.03] p-3 text-sm text-white/60">{t('marketOverviewPage.loading')}</div> : null}
      <MarketOverviewPanelFooter panel={panel} sourceLabel={data.sourceLabel || `${t('marketOverviewPage.cards.cnShortSentiment.source')}: ${data.source.toUpperCase()}`} />
    </GlassCard>
  );
};

function assignPanelValue(nextPanels: PanelState, panelKey: PanelKey, value: PanelState[PanelKey]): void {
  switch (panelKey) {
    case 'indices':
    case 'volatility':
    case 'crypto':
    case 'sentiment':
    case 'fundsFlow':
    case 'macro':
    case 'cnIndices':
    case 'cnBreadth':
    case 'cnFlows':
    case 'sectorRotation':
    case 'rates':
    case 'fxCommodities':
      nextPanels[panelKey] = value as MarketOverviewPanel;
      break;
    case 'temperature':
      nextPanels.temperature = value as MarketTemperatureResponse;
      break;
    case 'briefing':
      nextPanels.briefing = value as MarketBriefingResponse;
      break;
    case 'futures':
      nextPanels.futures = value as MarketFuturesResponse;
      break;
    case 'cnShortSentiment':
      nextPanels.cnShortSentiment = value as CnShortSentimentResponse;
      break;
  }
}

function describePanelError(error: unknown): string {
  return error instanceof Error ? error.message : String(error || 'market panel unavailable');
}

function fallbackPanel(panelName: string, error: unknown): MarketOverviewPanel {
  const updatedAt = new Date().toISOString();
  const message = describePanelError(error);
  return {
    panelName,
    lastRefreshAt: updatedAt,
    status: 'failure',
    errorMessage: `更新失败：${message}`,
    source: 'error',
    sourceLabel: '数据源异常',
    updatedAt,
    asOf: updatedAt,
    freshness: 'error',
    isFallback: true,
    isStale: true,
    warning: '数据源暂不可用，请稍后自动刷新。',
    items: [],
  };
}

function fallbackPanelValue(panelKey: PanelKey, error: unknown): PanelState[PanelKey] {
  switch (panelKey) {
    case 'temperature':
      return {
        ...FALLBACK_TEMPERATURE,
        updatedAt: new Date().toISOString(),
        warning: `数据源暂不可用，请稍后自动刷新。${describePanelError(error)}`,
      } as PanelState[PanelKey];
    case 'briefing':
      return {
        ...FALLBACK_BRIEFING,
        updatedAt: new Date().toISOString(),
        warning: `数据源暂不可用，请稍后自动刷新。${describePanelError(error)}`,
      } as PanelState[PanelKey];
    case 'futures':
      return {
        ...FALLBACK_FUTURES,
        updatedAt: new Date().toISOString(),
        isRefreshing: true,
        warning: `数据源暂不可用，请稍后自动刷新。${describePanelError(error)}`,
      } as PanelState[PanelKey];
    case 'cnShortSentiment':
      return {
        ...FALLBACK_CN_SHORT_SENTIMENT,
        updatedAt: new Date().toISOString(),
        isRefreshing: true,
        warning: `数据源暂不可用，请稍后自动刷新。${describePanelError(error)}`,
      } as PanelState[PanelKey];
    case 'indices':
      return fallbackPanel('IndexTrendsCard', error) as PanelState[PanelKey];
    case 'volatility':
      return fallbackPanel('VolatilityCard', error) as PanelState[PanelKey];
    case 'crypto':
      return {
        ...FALLBACK_CRYPTO_PANEL,
        lastRefreshAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        asOf: new Date().toISOString(),
        warning: `正在刷新，稍后自动更新。${describePanelError(error)}`,
      } as PanelState[PanelKey];
    case 'sentiment':
      return fallbackPanel('MarketSentimentCard', error) as PanelState[PanelKey];
    case 'fundsFlow':
      return fallbackPanel('FundsFlowCard', error) as PanelState[PanelKey];
    case 'macro':
      return fallbackPanel('MacroIndicatorsCard', error) as PanelState[PanelKey];
    case 'cnIndices':
      return fallbackPanel('ChinaIndicesCard', error) as PanelState[PanelKey];
    case 'cnBreadth':
      return fallbackPanel('ChinaBreadthCard', error) as PanelState[PanelKey];
    case 'cnFlows':
      return fallbackPanel('ChinaFlowsCard', error) as PanelState[PanelKey];
    case 'sectorRotation':
      return fallbackPanel('SectorRotationCard', error) as PanelState[PanelKey];
    case 'rates':
      return fallbackPanel('RatesCard', error) as PanelState[PanelKey];
    case 'fxCommodities':
      return fallbackPanel('FxCommoditiesCard', error) as PanelState[PanelKey];
  }
}

function withPanelTimeout<T>(promise: Promise<T>, panelKey: PanelKey): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => {
      reject(new Error(`${String(panelKey)} request timed out`));
    }, PANEL_REQUEST_TIMEOUT_MS);
    promise.then(
      (value) => {
        window.clearTimeout(timer);
        resolve(value);
      },
      (error) => {
        window.clearTimeout(timer);
        reject(error);
      },
    );
  });
}

function debugMarketPanel(panelKey: PanelKey, status: 'loading' | 'success' | 'fallback' | 'error'): void {
  if (import.meta.env.DEV && import.meta.env.MODE !== 'test') {
    console.debug(`[market-overview] ${String(panelKey)} ${status}`);
  }
}

const MarketOverviewPage: React.FC = () => {
  const { t } = useI18n();
  const [panels, setPanels] = useState<PanelState>({
    temperature: FALLBACK_TEMPERATURE,
    briefing: FALLBACK_BRIEFING,
    futures: FALLBACK_FUTURES,
    cnShortSentiment: FALLBACK_CN_SHORT_SENTIMENT,
  });
  const [loading, setLoading] = useState(true);
  const [refreshingPanel, setRefreshingPanel] = useState<PanelKey | null>(null);
  const [activeCategory, setActiveCategory] = useState<MarketOverviewTab>('all');
  const [fallbackSectionExpanded, setFallbackSectionExpanded] = useState(false);
  const [cryptoRealtimeStatus, setCryptoRealtimeStatus] = useState<CryptoRealtimeStatus>('snapshot');

  const loadPanels = useCallback(async (cancelledRef?: { current: boolean }) => {
    setLoading(true);
    const requests: Array<[PanelKey, () => Promise<PanelState[PanelKey]>]> = [
      ['indices', marketOverviewApi.getIndices],
      ['volatility', marketOverviewApi.getVolatility],
      ['crypto', marketApi.getCrypto],
      ['sentiment', marketApi.getSentiment],
      ['fundsFlow', marketOverviewApi.getFundsFlow],
      ['macro', marketOverviewApi.getMacro],
      ['cnIndices', marketApi.getCnIndices],
      ['cnBreadth', marketApi.getCnBreadth],
      ['cnFlows', marketApi.getCnFlows],
      ['sectorRotation', marketApi.getSectorRotation],
      ['rates', marketApi.getRates],
      ['fxCommodities', marketApi.getFxCommodities],
      ['temperature', marketApi.getTemperature],
      ['briefing', marketApi.getMarketBriefing],
      ['futures', marketApi.getFutures],
      ['cnShortSentiment', marketApi.getCnShortSentiment],
    ];
    let remaining = requests.length;
    const markSettled = () => {
      remaining -= 1;
      if (remaining <= 0 && !cancelledRef?.current) {
        setLoading(false);
      }
    };

    await Promise.allSettled(requests.map(async ([panelKey, loadPanel]) => {
      debugMarketPanel(panelKey, 'loading');
      try {
        const panel = await withPanelTimeout(loadPanel(), panelKey);
        if (!cancelledRef?.current) {
          setPanels((currentPanels) => {
            const nextPanels = { ...currentPanels };
            assignPanelValue(nextPanels, panelKey, panel);
            return nextPanels;
          });
        }
        debugMarketPanel(panelKey, 'success');
      } catch (error) {
        if (!cancelledRef?.current) {
          setPanels((currentPanels) => {
            const nextPanels = { ...currentPanels };
            if (!currentPanels[panelKey]) {
              assignPanelValue(nextPanels, panelKey, fallbackPanelValue(panelKey, error));
            }
            return nextPanels;
          });
        }
        debugMarketPanel(panelKey, 'fallback');
      } finally {
        markSettled();
      }
    }));
  }, []);

  const refreshPanel = useCallback(async (
    panelKey: PanelKey,
    loadPanel: () => Promise<PanelState[PanelKey]>,
  ) => {
    setRefreshingPanel(panelKey);
    debugMarketPanel(panelKey, 'loading');
    try {
      const panel = await withPanelTimeout(loadPanel(), panelKey);
      setPanels((currentPanels) => {
        const nextPanels = { ...currentPanels };
        assignPanelValue(nextPanels, panelKey, panel);
        return nextPanels;
      });
      debugMarketPanel(panelKey, 'success');
    } catch (error) {
      setPanels((currentPanels) => {
        if (currentPanels[panelKey]) {
          return currentPanels;
        }
        const nextPanels = { ...currentPanels };
        assignPanelValue(nextPanels, panelKey, fallbackPanelValue(panelKey, error));
        return nextPanels;
      });
      debugMarketPanel(panelKey, 'fallback');
    } finally {
      setRefreshingPanel((currentPanel) => (currentPanel === panelKey ? null : currentPanel));
    }
  }, []);

  useEffect(() => {
    const cancelledRef = { current: false };

    void loadPanels(cancelledRef).catch(() => {
      if (!cancelledRef.current) {
        setLoading(false);
      }
    });

    return () => {
      cancelledRef.current = true;
    };
  }, [loadPanels]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      const cancelledRef = { current: false };
      void loadPanels(cancelledRef);
    }, AUTO_REFRESH_MS);
    return () => {
      window.clearInterval(timer);
    };
  }, [loadPanels]);

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.EventSource === 'undefined') {
      setCryptoRealtimeStatus('snapshot');
      return undefined;
    }
    const eventSource = new window.EventSource(marketApi.cryptoStreamUrl(), { withCredentials: true });
    eventSource.onopen = () => {
      setCryptoRealtimeStatus('live');
    };
    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as Record<string, unknown>;
        const panel = marketApi.normalizeCryptoStreamPayload(payload);
        setPanels((currentPanels) => ({
          ...currentPanels,
          crypto: panel,
        }));
        setCryptoRealtimeStatus(panel.freshness === 'live' ? 'live' : 'snapshot');
      } catch {
        setCryptoRealtimeStatus('snapshot');
      }
    };
    eventSource.onerror = () => {
      setCryptoRealtimeStatus('reconnecting');
    };
    return () => {
      eventSource.close();
    };
  }, []);

  useEffect(() => {
    setFallbackSectionExpanded(false);
  }, [activeCategory]);

  const categoryTabs = useMemo<Array<{ key: MarketOverviewTab; label: string }>>(() => [
    { key: 'all', label: t('marketOverviewPage.categories.all') },
    { key: 'us', label: t('marketOverviewPage.categories.us') },
    { key: 'cn', label: t('marketOverviewPage.categories.cn') },
    { key: 'global', label: t('marketOverviewPage.categories.macro') },
    { key: 'crypto', label: t('marketOverviewPage.categories.crypto') },
  ], [t]);

  const cardNodes = useMemo<Record<CardKey, React.ReactNode>>(() => ({
    futures: (
      <FuturesPremarketCard
        data={panels.futures}
        loading={loading && panels.futures === FALLBACK_FUTURES}
        refreshing={refreshingPanel === 'futures'}
        onRefresh={() => {
          void refreshPanel('futures', marketApi.getFutures);
        }}
      />
    ),
    cnShortSentiment: (
      <CnShortSentimentCard
        data={panels.cnShortSentiment}
        loading={loading && panels.cnShortSentiment === FALLBACK_CN_SHORT_SENTIMENT}
        refreshing={refreshingPanel === 'cnShortSentiment'}
        onRefresh={() => {
          void refreshPanel('cnShortSentiment', marketApi.getCnShortSentiment);
        }}
      />
    ),
    indices: (
      <MarketOverviewCard
        title={t('marketOverviewPage.cards.indexTrends.title')}
        eyebrow={t('marketOverviewPage.cards.indexTrends.eyebrow')}
        description={t('marketOverviewPage.cards.indexTrends.description')}
        sourceLabel={t('marketOverviewPage.cards.indexTrends.source')}
        panel={panels.indices}
        loading={loading && !panels.indices}
        refreshing={refreshingPanel === 'indices'}
        onRefresh={() => {
          void refreshPanel('indices', marketOverviewApi.getIndices);
        }}
      />
    ),
    volatility: (
      <VolatilityCard
        panel={panels.volatility}
        loading={loading && !panels.volatility}
        refreshing={refreshingPanel === 'volatility'}
        onRefresh={() => {
          void refreshPanel('volatility', marketOverviewApi.getVolatility);
        }}
      />
    ),
    crypto: (
      <CryptoCard
        panel={panels.crypto}
        loading={loading && !panels.crypto}
        refreshing={refreshingPanel === 'crypto'}
        realtimeStatus={cryptoRealtimeStatus}
        onRefresh={() => {
          void refreshPanel('crypto', marketApi.getCrypto);
        }}
      />
    ),
    sentiment: (
      <MarketSentimentCard
        panel={panels.sentiment}
        loading={loading && !panels.sentiment}
        refreshing={refreshingPanel === 'sentiment'}
        onRefresh={() => {
          void refreshPanel('sentiment', marketApi.getSentiment);
        }}
      />
    ),
    fundsFlow: (
      <FundsFlowCard
        panel={panels.fundsFlow}
        loading={loading && !panels.fundsFlow}
        refreshing={refreshingPanel === 'fundsFlow'}
        onRefresh={() => {
          void refreshPanel('fundsFlow', marketOverviewApi.getFundsFlow);
        }}
      />
    ),
    macro: (
      <MacroIndicatorsCard
        panel={panels.macro}
        loading={loading && !panels.macro}
        refreshing={refreshingPanel === 'macro'}
        onRefresh={() => {
          void refreshPanel('macro', marketOverviewApi.getMacro);
        }}
      />
    ),
    cnIndices: (
      <MarketOverviewCard
        title={t('marketOverviewPage.cards.cnIndices.title')}
        eyebrow={t('marketOverviewPage.cards.cnIndices.eyebrow')}
        description={t('marketOverviewPage.cards.cnIndices.description')}
        sourceLabel={t('marketOverviewPage.cards.cnIndices.source')}
        panel={panels.cnIndices}
        loading={loading && !panels.cnIndices}
        refreshing={refreshingPanel === 'cnIndices'}
        onRefresh={() => {
          void refreshPanel('cnIndices', marketApi.getCnIndices);
        }}
      />
    ),
    cnBreadth: (
      <MarketOverviewCard
        title={t('marketOverviewPage.cards.cnBreadth.title')}
        eyebrow={t('marketOverviewPage.cards.cnBreadth.eyebrow')}
        description={t('marketOverviewPage.cards.cnBreadth.description')}
        sourceLabel={t('marketOverviewPage.cards.cnBreadth.source')}
        panel={panels.cnBreadth}
        loading={loading && !panels.cnBreadth}
        refreshing={refreshingPanel === 'cnBreadth'}
        onRefresh={() => {
          void refreshPanel('cnBreadth', marketApi.getCnBreadth);
        }}
      />
    ),
    cnFlows: (
      <MarketOverviewCard
        title={t('marketOverviewPage.cards.cnFlows.title')}
        eyebrow={t('marketOverviewPage.cards.cnFlows.eyebrow')}
        description={t('marketOverviewPage.cards.cnFlows.description')}
        sourceLabel={t('marketOverviewPage.cards.cnFlows.source')}
        panel={panels.cnFlows}
        loading={loading && !panels.cnFlows}
        refreshing={refreshingPanel === 'cnFlows'}
        onRefresh={() => {
          void refreshPanel('cnFlows', marketApi.getCnFlows);
        }}
      />
    ),
    sectorRotation: (
      <MarketOverviewCard
        title={t('marketOverviewPage.cards.sectorRotation.title')}
        eyebrow={t('marketOverviewPage.cards.sectorRotation.eyebrow')}
        description={t('marketOverviewPage.cards.sectorRotation.description')}
        sourceLabel={t('marketOverviewPage.cards.sectorRotation.source')}
        panel={panels.sectorRotation ? { ...panels.sectorRotation, items: panels.sectorRotation.items.slice(0, 5) } : undefined}
        loading={loading && !panels.sectorRotation}
        refreshing={refreshingPanel === 'sectorRotation'}
        onRefresh={() => {
          void refreshPanel('sectorRotation', marketApi.getSectorRotation);
        }}
      />
    ),
    rates: (
      <MarketOverviewCard
        title={t('marketOverviewPage.cards.rates.title')}
        eyebrow={t('marketOverviewPage.cards.rates.eyebrow')}
        description={t('marketOverviewPage.cards.rates.description')}
        sourceLabel={t('marketOverviewPage.cards.rates.source')}
        panel={panels.rates}
        loading={loading && !panels.rates}
        refreshing={refreshingPanel === 'rates'}
        onRefresh={() => {
          void refreshPanel('rates', marketApi.getRates);
        }}
      />
    ),
    fxCommodities: (
      <MarketOverviewCard
        title={t('marketOverviewPage.cards.fxCommodities.title')}
        eyebrow={t('marketOverviewPage.cards.fxCommodities.eyebrow')}
        description={t('marketOverviewPage.cards.fxCommodities.description')}
        sourceLabel={t('marketOverviewPage.cards.fxCommodities.source')}
        panel={panels.fxCommodities}
        loading={loading && !panels.fxCommodities}
        refreshing={refreshingPanel === 'fxCommodities'}
        onRefresh={() => {
          void refreshPanel('fxCommodities', marketApi.getFxCommodities);
        }}
      />
    ),
  }), [cryptoRealtimeStatus, loading, panels, refreshPanel, refreshingPanel, t]);

  const heroAnchors = useMemo(() => buildHeroAnchors(panels), [panels]);
  const dataQuality = useMemo(() => summarizeDataQuality(panels), [panels]);
  const coverageSummary = useMemo(() => summarizeCardCoverage(panels, CATEGORY_CARDS[activeCategory]), [activeCategory, panels]);
  const activeCategoryLabel = categoryTabs.find((tab) => tab.key === activeCategory)?.label || '';
  const activeLayout = CATEGORY_LAYOUT[activeCategory];
  const primaryCandidates = activeLayout.primary.filter((cardKey) => getCardCoverageKind(panels, cardKey) !== 'fallback');
  const secondaryCandidates = activeLayout.secondary.filter((cardKey) => getCardCoverageKind(panels, cardKey) !== 'fallback');
  const promotedSecondaryCount = primaryCandidates.length < 2 ? Math.min(2 - primaryCandidates.length, secondaryCandidates.length) : 0;
  const promotedSecondary = secondaryCandidates.slice(0, promotedSecondaryCount);
  const primaryOrder = [...primaryCandidates, ...promotedSecondary];
  const secondaryOrder = secondaryCandidates.filter((cardKey) => !promotedSecondary.includes(cardKey));
  const fallbackOnlyOrder = CATEGORY_CARDS[activeCategory].filter((cardKey) => (
    getCardCoverageKind(panels, cardKey) === 'fallback' || activeLayout.fallback.includes(cardKey)
  ));
  const showCategoryEmptyState = activeCategory !== 'all' && primaryOrder.length === 0 && fallbackOnlyOrder.length > 0;

  const renderCard = (cardKey: CardKey, rank: number, rail: 'primary' | 'side' | 'fallback' = 'primary') => {
    const layoutMeta = CARD_LAYOUT_META[cardKey];
    return (
    <div
      key={cardKey}
      data-testid={`market-overview-card-${cardKey}`}
      data-market-card-rank={rank}
      data-market-card-size={layoutMeta.size}
      className={cn(
        'min-w-0 w-full',
        rail === 'primary' && layoutMeta.size === 'wide' ? 'lg:col-span-2' : '',
      )}
    >
      {cardNodes[cardKey]}
    </div>
    );
  };

  const renderCardGrid = (rankOrder: CardKey[], rail: 'primary' | 'side' | 'fallback') => (
    <div className={cn(
      'grid w-full grid-cols-1 gap-4',
      rail === 'primary' ? 'lg:grid-cols-2' : '',
      rail === 'fallback' ? 'lg:grid-cols-2 xl:grid-cols-1' : '',
    )}>
      {rankOrder.map((cardKey, index) => renderCard(cardKey, index, rail))}
    </div>
  );

  const renderFallbackSection = () => (
    fallbackOnlyOrder.length > 0 ? (
      <PendingDataSourceSection
        expanded={fallbackSectionExpanded}
        fallbackCount={fallbackOnlyOrder.length}
        onToggle={() => setFallbackSectionExpanded((current) => !current)}
      >
        {renderCardGrid(fallbackOnlyOrder, 'fallback')}
      </PendingDataSourceSection>
    ) : null
  );

  const renderDeterministicGrid = () => (
    <main data-testid="market-overview-main-grid" className="grid grid-cols-1 items-start gap-6 xl:grid-cols-12">
      <section data-testid="market-overview-primary-rail" className="grid min-w-0 grid-cols-1 gap-6 lg:grid-cols-2 xl:col-span-8">
        {showCategoryEmptyState ? (
          <div className="lg:col-span-2">
            <CategoryEmptyState onShowPending={() => setFallbackSectionExpanded(true)} />
          </div>
        ) : null}
        {primaryOrder.map((cardKey, index) => renderCard(cardKey, index, 'primary'))}
      </section>
      <aside data-testid="market-overview-side-rail" className="flex min-w-0 flex-col gap-6 xl:col-span-4">
        <CategoryCoverageSummary label={activeCategoryLabel} summary={coverageSummary} />
        {secondaryOrder.length > 0 ? renderCardGrid(secondaryOrder, 'side') : null}
        {renderFallbackSection()}
      </aside>
    </main>
  );

  return (
    <div className="flex min-h-0 w-full flex-1 flex-col bg-[#030303] text-white">
      <div className="flex-1 overflow-y-auto pb-12 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        <section data-testid="market-overview-page-container" className="mx-auto flex w-full max-w-[1280px] flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
          <div className="sticky top-0 z-10 -mx-4 overflow-x-auto border-b border-white/5 bg-[#030303]/95 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            <div className="flex w-max min-w-full gap-2 rounded-lg bg-white/[0.03] p-1">
              {categoryTabs.map((tab) => (
                <button
                  key={tab.key}
                  type="button"
                  aria-pressed={activeCategory === tab.key}
                  onClick={() => setActiveCategory(tab.key)}
                  className={`whitespace-nowrap rounded-md px-3 py-2 text-xs font-semibold transition ${
                    activeCategory === tab.key
                      ? 'bg-white/10 text-white shadow-sm'
                      : 'bg-transparent text-white/45 hover:text-white/75'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>
          <CrossAssetHeroRibbon anchors={heroAnchors} />
          <MarketTemperatureStrip
            data={panels.temperature}
            refreshing={refreshingPanel === 'temperature'}
            onRefresh={() => {
              void refreshPanel('temperature', marketApi.getTemperature);
            }}
          />
          <DataQualityOverview summary={dataQuality} />
          <MarketBriefingCard
            data={panels.briefing}
            refreshing={refreshingPanel === 'briefing'}
            onRefresh={() => {
              void refreshPanel('briefing', marketApi.getMarketBriefing);
            }}
          />
          {renderDeterministicGrid()}
        </section>
      </div>
    </div>
  );
};

export default MarketOverviewPage;
