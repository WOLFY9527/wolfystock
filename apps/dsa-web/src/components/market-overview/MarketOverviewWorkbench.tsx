import type React from 'react';
import { useCallback, useMemo, useState } from 'react';
import type { MarketDataMeta, MarketOverviewItem, MarketOverviewPanel, MarketProviderHealthStatus } from '../../api/marketOverview';
import type {
  CnShortSentimentResponse,
  MarketBriefingResponse,
  MarketFuturesResponse,
  MarketTemperatureResponse,
  MarketTemperatureScore,
} from '../../api/market';
import {
  MARKET_OVERVIEW_TAB_CONFIG,
  type MarketOverviewModuleId,
  type MarketOverviewPulseMetricId,
  type MarketOverviewTab,
} from '../../pages/MarketOverviewTabConfig';
import { FundsFlowCard } from './FundsFlowCard';
import { MarketSentimentCard } from './MarketSentimentCard';
import { MarketOverviewCard } from './MarketOverviewCard';
import { VolatilityCard } from './VolatilityCard';
import {
  MarketOverviewWorkbenchGrid,
  type MarketOverviewActionHintView,
  type MarketOverviewCoverageRailView,
  type MarketOverviewExecutiveGroupView,
  type MarketOverviewQualityRailView,
  type MarketOverviewSignalWatchRailItem,
} from './MarketOverviewWorkbenchGrid';
import {
  MarketOverviewWorkbenchTopSurface,
  type MarketOverviewBriefingSummaryView,
  type MarketOverviewCategoryTabView,
  type MarketOverviewDataStateStripView,
  type MarketOverviewDecisionChipView,
  type MarketOverviewHeroAnchorView,
  type MarketOverviewTemperatureSummaryView,
} from './MarketOverviewWorkbenchTopSurface';
import { resolveMarketOverviewDisplayLabel } from './marketOverviewLabels';
import { formatMarketOverviewTimestamp } from './marketOverviewFormat';
import {
  MarketOverviewCardFrame,
  MarketOverviewDenseQuoteItem,
  MarketOverviewPanelFooter,
  MarketOverviewRefreshButton,
} from './marketOverviewPrimitives';
import { TerminalPageShell } from '../terminal';
import { useI18n } from '../../contexts/UiLanguageContext';
import { cn } from '../../utils/cn';

export type PanelState = {
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
  usBreadth?: MarketOverviewPanel;
  rates?: MarketOverviewPanel;
  fxCommodities?: MarketOverviewPanel;
  temperature: MarketTemperatureResponse;
  briefing: MarketBriefingResponse;
  futures: MarketFuturesResponse;
  cnShortSentiment: CnShortSentimentResponse;
};

export type PanelKey = keyof PanelState;
export type CryptoRealtimeStatus = 'live' | 'reconnecting' | 'snapshot';

type CardKey = Exclude<PanelKey, 'temperature' | 'briefing'>;
type CardCoverageKind = 'real' | 'mixed' | 'fallback';
type MarketOverviewRowTier = 'hero' | 'secondary' | 'deep';
type MarketOverviewRowColumns = 1 | 2 | 3;
type MarketOverviewLayoutRow = {
  id: string;
  tier: MarketOverviewRowTier;
  columns: MarketOverviewRowColumns;
  modules: MarketOverviewModuleId[];
  allowSingleFullWidth?: boolean;
};
type WorkbenchRail = MarketOverviewRowTier;
type HeroAnchor = {
  key: string;
  label: string;
  item?: MarketOverviewItem;
};
type MetricRegistryEntry = {
  label: string;
  symbols: string[];
  panelKeys: CardKey[];
};
type FreshnessCountKey = 'live' | 'delayed' | 'cached' | 'stale' | 'fallback' | 'mock' | 'error';
type DataQualitySummary = {
  status: string;
  counts: Record<FreshnessCountKey, number>;
  hasConcern: boolean;
};

const MODULE_COVERAGE_CARDS: Record<MarketOverviewModuleId, CardKey[]> = {
  globalIndices: ['indices'],
  usIndices: ['indices'],
  cnHkIndices: ['cnIndices'],
  cryptoCore: ['crypto'],
  volatility: ['volatility'],
  fundsFlow: ['fundsFlow'],
  sentiment: ['sentiment'],
  rates: ['rates'],
  fxCommodities: ['fxCommodities'],
  cryptoSnapshot: ['crypto'],
  cnSnapshot: ['cnIndices'],
  usRates: ['rates', 'fxCommodities'],
  usSentiment: ['sentiment'],
  usBreadth: ['usBreadth'],
  usSectorRotation: ['usBreadth'],
  macroContext: ['volatility', 'rates', 'fxCommodities', 'crypto'],
  cnBreadth: ['cnBreadth'],
  cnFlows: ['cnFlows'],
  sectorRotation: ['sectorRotation'],
  shortSentiment: ['cnShortSentiment'],
  fxCnhContext: ['fxCommodities', 'rates'],
  macroRates: ['rates'],
  macroFxCommodities: ['fxCommodities'],
  globalRisk: ['volatility', 'crypto', 'indices'],
  cryptoMomentum: ['crypto'],
  cryptoLiquidity: ['crypto'],
  cryptoRiskContext: ['fxCommodities', 'rates', 'volatility'],
  cryptoSentiment: ['sentiment'],
};

const CATEGORY_CARDS: Record<MarketOverviewTab, CardKey[]> = Object.fromEntries(
  Object.entries(MARKET_OVERVIEW_TAB_CONFIG).map(([tab, config]) => [
    tab,
    Array.from(new Set([...config.hero, ...config.modules].flatMap((moduleId) => MODULE_COVERAGE_CARDS[moduleId]))),
  ]),
) as Record<MarketOverviewTab, CardKey[]>;

const MODULE_LAYOUT_META: Record<MarketOverviewModuleId, {
  size: 'compact' | 'standard' | 'list' | 'large' | 'rail';
  priority: 'primary' | 'secondary' | 'fallback';
}> = {
  globalIndices: { size: 'large', priority: 'primary' },
  usIndices: { size: 'large', priority: 'primary' },
  cnHkIndices: { size: 'large', priority: 'primary' },
  cryptoCore: { size: 'large', priority: 'primary' },
  volatility: { size: 'standard', priority: 'primary' },
  fundsFlow: { size: 'standard', priority: 'primary' },
  rates: { size: 'list', priority: 'secondary' },
  fxCommodities: { size: 'list', priority: 'secondary' },
  cryptoSnapshot: { size: 'list', priority: 'secondary' },
  cnSnapshot: { size: 'list', priority: 'secondary' },
  usRates: { size: 'list', priority: 'secondary' },
  usSentiment: { size: 'compact', priority: 'secondary' },
  usBreadth: { size: 'compact', priority: 'fallback' },
  usSectorRotation: { size: 'compact', priority: 'fallback' },
  macroContext: { size: 'list', priority: 'secondary' },
  sentiment: { size: 'compact', priority: 'secondary' },
  cnBreadth: { size: 'standard', priority: 'fallback' },
  cnFlows: { size: 'standard', priority: 'fallback' },
  sectorRotation: { size: 'standard', priority: 'fallback' },
  shortSentiment: { size: 'compact', priority: 'fallback' },
  fxCnhContext: { size: 'list', priority: 'secondary' },
  macroRates: { size: 'list', priority: 'primary' },
  macroFxCommodities: { size: 'list', priority: 'primary' },
  globalRisk: { size: 'list', priority: 'secondary' },
  cryptoMomentum: { size: 'list', priority: 'primary' },
  cryptoLiquidity: { size: 'compact', priority: 'fallback' },
  cryptoRiskContext: { size: 'list', priority: 'secondary' },
  cryptoSentiment: { size: 'compact', priority: 'secondary' },
};

const DENSE_QUOTE_MODULES = new Set<MarketOverviewModuleId>([
  'globalIndices',
  'usIndices',
  'cnHkIndices',
  'cryptoCore',
  'rates',
  'fxCommodities',
  'cryptoSnapshot',
  'cnSnapshot',
  'usRates',
  'macroContext',
  'fxCnhContext',
  'macroRates',
  'macroFxCommodities',
  'globalRisk',
  'cryptoMomentum',
  'cryptoRiskContext',
]);

function buildCategoryLayout(tab: MarketOverviewTab): MarketOverviewLayoutRow[] {
  const config = MARKET_OVERVIEW_TAB_CONFIG[tab];
  const rows: MarketOverviewLayoutRow[] = [];
  if (config.hero.length > 0) {
    rows.push({
      id: `${tab}-hero`,
      tier: 'hero',
      columns: Math.min(config.hero.length, 2) as MarketOverviewRowColumns,
      modules: config.hero,
      allowSingleFullWidth: true,
    });
  }
  for (let index = 0; index < config.modules.length; index += 2) {
    const modules = config.modules.slice(index, index + 2);
    rows.push({
      id: `${tab}-modules-${index / 2 + 1}`,
      tier: index < 4 ? 'secondary' : 'deep',
      columns: Math.min(modules.length, 2) as MarketOverviewRowColumns,
      modules,
      allowSingleFullWidth: false,
    });
  }
  return rows;
}

const CATEGORY_LAYOUT: Record<MarketOverviewTab, MarketOverviewLayoutRow[]> = {
  all: buildCategoryLayout('all'),
  us: buildCategoryLayout('us'),
  cn: buildCategoryLayout('cn'),
  global: buildCategoryLayout('global'),
  crypto: buildCategoryLayout('crypto'),
};

const MARKET_OVERVIEW_METRIC_REGISTRY: Record<MarketOverviewPulseMetricId, MetricRegistryEntry> = {
  SPX: { label: '标普500', symbols: ['SPX', '^GSPC', 'S&P 500'], panelKeys: ['indices'] },
  NDX: { label: '纳斯达克100', symbols: ['NDX', '^NDX', 'NASDAQ 100'], panelKeys: ['indices'] },
  DJI: { label: '道琼斯工业平均指数', symbols: ['DJI', 'DJIA', '^DJI', 'DOW JONES'], panelKeys: ['indices'] },
  RUT: { label: '罗素2000', symbols: ['RUT', '^RUT', 'RUSSELL 2000'], panelKeys: ['indices'] },
  SHCOMP: { label: '上证指数', symbols: ['SHCOMP', '000001.SH', '000001.SS', 'SH000001', 'SHANGHAI COMPOSITE'], panelKeys: ['cnIndices', 'indices'] },
  SZCOMP: { label: '深证成指', symbols: ['SZCOMP', '399001.SZ', 'SZ399001', 'SHENZHEN COMPONENT'], panelKeys: ['cnIndices', 'indices'] },
  CHINEXT: { label: '创业板指', symbols: ['CHINEXT', '399006.SZ', 'SZ399006'], panelKeys: ['cnIndices'] },
  CSI300: { label: '沪深300', symbols: ['CSI300', '000300.SH', '000300.SS', 'CSI 300'], panelKeys: ['cnIndices', 'indices'] },
  HSI: { label: '恒生指数', symbols: ['HSI', 'HANG SENG INDEX'], panelKeys: ['cnIndices', 'indices'] },
  HSTECH: { label: '恒生科技指数', symbols: ['HSTECH', 'HANG SENG TECH'], panelKeys: ['cnIndices'] },
  A50: { label: '富时A50', symbols: ['A50', 'CN00Y', 'FTSE A50'], panelKeys: ['cnIndices', 'fxCommodities'] },
  BTC: { label: '比特币', symbols: ['BTC', 'BITCOIN'], panelKeys: ['crypto'] },
  ETH: { label: '以太坊', symbols: ['ETH', 'ETHEREUM'], panelKeys: ['crypto'] },
  SOL: { label: 'Solana', symbols: ['SOL', 'SOLANA'], panelKeys: ['crypto'] },
  BNB: { label: 'BNB', symbols: ['BNB'], panelKeys: ['crypto'] },
  VIX: { label: 'VIX 恐慌指数', symbols: ['VIX'], panelKeys: ['volatility'] },
  VVIX: { label: 'VVIX', symbols: ['VVIX'], panelKeys: ['volatility'] },
  US10Y: { label: '美国10年期国债收益率', symbols: ['US10Y', 'US 10Y', '10Y YIELD'], panelKeys: ['rates', 'macro'] },
  US2Y: { label: '美国2年期国债收益率', symbols: ['US2Y', 'US 2Y', '2Y YIELD'], panelKeys: ['rates', 'macro'] },
  US30Y: { label: '美国30年期国债收益率', symbols: ['US30Y', 'US 30Y', '30Y YIELD'], panelKeys: ['rates', 'macro'] },
  DXY: { label: '美元指数', symbols: ['DXY', 'US DOLLAR INDEX'], panelKeys: ['fxCommodities', 'macro'] },
  USDJPY: { label: 'USD/JPY', symbols: ['USDJPY', 'USD/JPY'], panelKeys: ['fxCommodities', 'macro'] },
  USDCNH: { label: 'USD/CNH', symbols: ['USDCNH', 'USD/CNH'], panelKeys: ['fxCommodities', 'macro'] },
  GOLD: { label: '黄金', symbols: ['GOLD', 'GOLD FUTURES'], panelKeys: ['fxCommodities'] },
  WTI: { label: 'WTI 原油', symbols: ['WTI', 'OIL', 'WTI CRUDE'], panelKeys: ['fxCommodities'] },
};

const MARKET_OVERVIEW_SIGNAL_WATCH: Record<MarketOverviewTab, MarketOverviewPulseMetricId[]> = {
  all: ['VIX', 'US10Y', 'DXY', 'BTC'],
  us: ['VIX', 'US10Y', 'DXY', 'NDX'],
  cn: ['CSI300', 'HSI', 'HSTECH', 'USDCNH'],
  global: ['US10Y', 'DXY', 'GOLD', 'WTI', 'VIX'],
  crypto: ['BTC', 'ETH', 'SOL', 'DXY'],
};

function findPanelItem(panel: MarketOverviewPanel | undefined, symbols: string[]): MarketOverviewItem | undefined {
  const normalizedSymbols = symbols.map((symbol) => symbol.toUpperCase());
  return panel?.items.find((item) => normalizedSymbols.includes(item.symbol.toUpperCase()));
}

function panelByCardKey(panels: PanelState, cardKey: CardKey): MarketOverviewPanel | undefined {
  if (cardKey === 'futures' || cardKey === 'cnShortSentiment') {
    return undefined;
  }
  return panels[cardKey];
}

function findMetricItem(panels: PanelState, metricId: MarketOverviewPulseMetricId): MarketOverviewItem | undefined {
  const entry = MARKET_OVERVIEW_METRIC_REGISTRY[metricId];
  for (const panelKey of entry.panelKeys) {
    const item = findPanelItem(panelByCardKey(panels, panelKey), entry.symbols);
    if (item) {
      return item;
    }
  }
  return undefined;
}

function missingMetricItem(metricId: MarketOverviewPulseMetricId): MarketOverviewItem {
  const entry = MARKET_OVERVIEW_METRIC_REGISTRY[metricId];
  return {
    symbol: metricId,
    label: entry.label,
    value: null,
    unit: '',
    changePct: null,
    changeText: '未接入',
    riskDirection: 'neutral',
    trend: [],
    source: 'unavailable',
    sourceLabel: '未接入',
    freshness: 'cached',
    hoverDetails: ['等待数据'],
  };
}

function buildMetricItems(panels: PanelState, metricIds: MarketOverviewPulseMetricId[]): MarketOverviewItem[] {
  return metricIds.map((metricId) => findMetricItem(panels, metricId) || missingMetricItem(metricId));
}

function firstSourcePanelForMetrics(panels: PanelState, metricIds: MarketOverviewPulseMetricId[]): MarketOverviewPanel | undefined {
  for (const metricId of metricIds) {
    for (const panelKey of MARKET_OVERVIEW_METRIC_REGISTRY[metricId].panelKeys) {
      const panel = panelByCardKey(panels, panelKey);
      if (panel) {
        return panel;
      }
    }
  }
  return undefined;
}

function buildMetricPanel(
  panels: PanelState,
  panelName: string,
  metricIds: MarketOverviewPulseMetricId[],
): MarketOverviewPanel {
  const basePanel = firstSourcePanelForMetrics(panels, metricIds);
  return {
    panelName,
    lastRefreshAt: basePanel?.lastRefreshAt || new Date(0).toISOString(),
    status: basePanel?.status || 'success',
    source: basePanel?.source || 'unavailable',
    sourceLabel: basePanel?.sourceLabel || '未接入',
    updatedAt: basePanel?.updatedAt,
    asOf: basePanel?.asOf,
    freshness: basePanel?.freshness || 'cached',
    isFallback: basePanel?.isFallback,
    isStale: basePanel?.isStale,
    warning: basePanel?.warning,
    items: buildMetricItems(panels, metricIds),
  };
}

function buildFilteredPanel(
  sourcePanel: MarketOverviewPanel | undefined,
  panelName: string,
  symbols: string[],
  fallbackItems: MarketOverviewItem[] = [],
): MarketOverviewPanel {
  const symbolSet = new Set(symbols);
  const items = sourcePanel?.items.filter((item) => symbolSet.has(item.symbol)) || [];
  const updatedAt = sourcePanel?.updatedAt || new Date(0).toISOString();
  return {
    panelName,
    lastRefreshAt: sourcePanel?.lastRefreshAt || updatedAt,
    status: sourcePanel?.status || 'success',
    source: sourcePanel?.source || 'unavailable',
    sourceLabel: sourcePanel?.sourceLabel || '未接入',
    updatedAt,
    asOf: sourcePanel?.asOf,
    freshness: sourcePanel?.freshness || 'fallback',
    isFallback: sourcePanel?.isFallback,
    isStale: sourcePanel?.isStale,
    warning: sourcePanel?.warning,
    items: items.length > 0 ? items : fallbackItems,
  };
}

function unavailableMarketItem(symbol: string, label: string, message: string): MarketOverviewItem {
  return {
    symbol,
    label,
    value: null,
    unit: '',
    changePct: null,
    changeText: message,
    riskDirection: 'neutral',
    trend: [],
    source: 'unavailable',
    sourceLabel: '未接入',
    freshness: 'fallback',
    isFallback: true,
    warning: message,
    hoverDetails: [message],
  };
}

function buildCryptoLiquidityPanel(sourcePanel: MarketOverviewPanel | undefined): MarketOverviewPanel {
  const fallbackItems = [
    unavailableMarketItem('BTC_FUNDING', 'BTC 资金费率', '暂不可用'),
    unavailableMarketItem('ETH_FUNDING', 'ETH 资金费率', '暂不可用'),
    unavailableMarketItem('SOL_FUNDING', 'SOL 资金费率', '暂不可用'),
    unavailableMarketItem('BNB_FUNDING', 'BNB 资金费率', '暂不可用'),
    unavailableMarketItem('STABLECOIN_LIQUIDITY', '稳定币流动性', '未接入'),
    unavailableMarketItem('BTC_DOMINANCE', 'BTC 占比', '未接入'),
  ];
  const panel = buildFilteredPanel(
    sourcePanel,
    'CryptoLiquidityModule',
    ['BTC_FUNDING', 'ETH_FUNDING', 'SOL_FUNDING', 'BNB_FUNDING', 'STABLECOIN_LIQUIDITY', 'BTC_DOMINANCE'],
    fallbackItems,
  );
  const existingSymbols = new Set(panel.items.map((item) => item.symbol));
  return {
    ...panel,
    items: [
      ...panel.items,
      ...fallbackItems.filter((item) => !existingSymbols.has(item.symbol)),
    ],
  };
}

function buildHeroAnchors(panels: PanelState, metricIds: MarketOverviewPulseMetricId[]): HeroAnchor[] {
  return metricIds.map((metricId) => {
    const entry = MARKET_OVERVIEW_METRIC_REGISTRY[metricId];
    return {
      key: metricId,
      label: entry.label,
      item: findMetricItem(panels, metricId) || missingMetricItem(metricId),
    };
  });
}

function formatHeroValue(value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return 'N/A';
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

function formatCoverageSummaryLine(label: string, summary: Record<CardCoverageKind, number>, language: 'zh' | 'en'): string {
  if (language === 'en') {
    return `Coverage (${label}): real ${summary.real} | mixed ${summary.mixed} | fallback ${summary.fallback}`;
  }
  return `${label}数据覆盖：真实 ${summary.real} | 混合 ${summary.mixed} | 备用 ${summary.fallback}`;
}

function buildMarketOverviewSummaryText(params: {
  activeCategoryLabel: string;
  coverageSummary: Record<CardCoverageKind, number>;
  dataQuality: DataQualitySummary;
  heroAnchors: HeroAnchor[];
  language: 'zh' | 'en';
  temperature: MarketTemperatureResponse;
  briefing: MarketBriefingResponse;
}): string {
  const {
    activeCategoryLabel,
    coverageSummary,
    dataQuality,
    heroAnchors,
    language,
    temperature,
    briefing,
  } = params;

  const heroLine = heroAnchors
    .slice(0, 3)
    .map((anchor) => {
      const displayLabel = anchor.item
        ? resolveMarketOverviewDisplayLabel(anchor.item, language)
        : { primary: anchor.label, secondary: anchor.key };
      return `${displayLabel.primary} ${formatHeroValue(anchor.item?.value)} (${formatHeroChange(anchor.item?.changePct)})`;
    })
    .join(' | ');

  const briefingLine = briefing.items
    .slice(0, 3)
    .map((item) => `${item.title}: ${item.message}`)
    .join(language === 'en' ? ' | ' : '；');

  const lines = language === 'en'
    ? [
      `Market Overview | ${activeCategoryLabel}`,
      `Market temperature: ${temperature.scores.overall.label} (${temperature.scores.overall.value})`,
      `Data quality: ${dataQuality.status}`,
      formatCoverageSummaryLine(activeCategoryLabel, coverageSummary, language),
      `Cross asset snapshot: ${heroLine}`,
      `Briefing: ${briefingLine}`,
    ]
    : [
      `市场总览 | ${activeCategoryLabel}`,
      `市场温度：${temperature.scores.overall.label}（${temperature.scores.overall.value}）`,
      `数据质量：${dataQuality.status}`,
      formatCoverageSummaryLine(activeCategoryLabel, coverageSummary, language),
      `跨资产快照：${heroLine}`,
      `市场解读：${briefingLine}`,
    ];

  return lines.join('\n');
}

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
  const panelKeys: CardKey[] = ['indices', 'volatility', 'crypto', 'sentiment', 'fundsFlow', 'macro', 'cnIndices', 'cnBreadth', 'cnFlows', 'sectorRotation', 'usBreadth', 'rates', 'fxCommodities'];
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
      ? '存在过期数据'
      : counts.fallback + counts.mock > 0
        ? '部分备用'
        : '良好';
  return {
    status,
    counts,
    hasConcern: counts.fallback + counts.mock + counts.stale + counts.error > 0,
  };
}

function describeDirectionalItem(item?: MarketOverviewItem, fallbackLabel = 'N/A'): string {
  if (!item) {
    return fallbackLabel;
  }
  const label = item.label || item.symbol;
  if (item.changePct == null || !Number.isFinite(item.changePct)) {
    return `${label} 中性`;
  }
  if (item.changePct > 0.15) {
    return `${label} 偏强`;
  }
  if (item.changePct < -0.15) {
    return `${label} 偏弱`;
  }
  return `${label} 横盘`;
}

function scoreStateLabel(score: MarketTemperatureScore, pressure = false): string {
  if (pressure) {
    return score.value >= 65 ? '偏高' : score.value >= 55 ? '中性偏高' : score.value <= 40 ? '偏低' : '中性';
  }
  return score.label || (score.value >= 60 ? '偏强' : score.value <= 45 ? '偏弱' : '中性');
}

function buildDecisionChipVariant(value: number, pressure = false): MarketOverviewDecisionChipView['variant'] {
  if (pressure) {
    return value >= 65 ? 'danger' : value >= 55 ? 'caution' : 'success';
  }
  return value >= 60 ? 'success' : value <= 45 ? 'info' : 'neutral';
}

function buildMarketDecision(params: {
  activeCategory: MarketOverviewTab;
  panels: PanelState;
  dataQuality: DataQualitySummary;
}): { text: string; chips: MarketOverviewDecisionChipView[] } {
  const { activeCategory, panels, dataQuality } = params;
  const temperature = panels.temperature;
  const reliable = isTemperatureReliable(temperature);
  const hasLoadedSignals = CATEGORY_CARDS[activeCategory].some((cardKey) => {
    const meta = getCardMeta(panels, cardKey);
    return Boolean(meta.source || meta.freshness || (meta.items?.length || 0) > 0);
  });
  if (!reliable && !hasLoadedSignals) {
    const watchSignals = MARKET_OVERVIEW_SIGNAL_WATCH[activeCategory].slice(0, 3).join(' / ');
    return {
      text: '数据不足 · 等待更多实时源',
      chips: [
        { label: '风险', value: '数据不足', variant: 'caution' },
        { label: '流动性', value: 'N/A', variant: 'neutral' },
        { label: '宽度', value: 'N/A', variant: 'neutral' },
        { label: '观察', value: watchSignals, variant: 'neutral' },
      ],
    };
  }

  const vix = findPanelItem(panels.volatility, ['VIX']);
  const btc = findPanelItem(panels.crypto, ['BTC']);
  const spx = findPanelItem(panels.indices, ['SPX']);
  const csi = findPanelItem(panels.cnIndices, ['CSI300', '000300.SH']) || findPanelItem(panels.indices, ['CSI300']);
  const us10y = findPanelItem(panels.rates, ['US10Y']) || findPanelItem(panels.macro, ['US10Y']);
  const dxy = findPanelItem(panels.fxCommodities, ['DXY']) || findPanelItem(panels.macro, ['DXY']);
  const hsi = findPanelItem(panels.cnIndices, ['HSI']);

  const riskLabel = reliable ? scoreStateLabel(temperature.scores.overall) : '数据不足';
  const liquidityLabel = reliable ? scoreStateLabel(temperature.scores.liquidity) : 'N/A';
  const breadthLabel = reliable ? scoreStateLabel(temperature.scores.cnMoneyEffect) : 'N/A';
  const watchSignals = MARKET_OVERVIEW_SIGNAL_WATCH[activeCategory]
    .map((metricId) => findMetricItem(panels, metricId)?.symbol || metricId)
    .slice(0, 3)
    .join(' / ') || '实时源';
  const chips: MarketOverviewDecisionChipView[] = [
    { label: '风险', value: riskLabel, variant: reliable ? buildDecisionChipVariant(temperature.scores.overall.value) : 'caution' },
    { label: '流动性', value: liquidityLabel, variant: reliable ? buildDecisionChipVariant(temperature.scores.liquidity.value) : 'neutral' },
    { label: '宽度', value: breadthLabel, variant: reliable ? buildDecisionChipVariant(temperature.scores.cnMoneyEffect.value) : 'neutral' },
    { label: '观察', value: watchSignals, variant: 'neutral' },
  ];

  if (!reliable) {
    return {
      text: '数据不足 · 等待更多实时源',
      chips,
    };
  }

  const compareUsCn = typeof spx?.changePct === 'number' && typeof csi?.changePct === 'number'
    ? spx.changePct >= csi.changePct ? '美股强于A股' : 'A股强于美股'
    : '跨市场强弱待确认';
  const texts: Record<MarketOverviewTab, string> = {
    all: `风险${riskLabel} · ${compareUsCn} · ${describeDirectionalItem(btc, 'BTC 待确认')} · 重点观察 ${watchSignals}`,
    us: `美股风险${scoreStateLabel(temperature.scores.usRiskAppetite)} · ${describeDirectionalItem(vix, 'VIX 待确认')} · ${describeDirectionalItem(spx, '标普500 待确认')}`,
    cn: `A股宽度${breadthLabel} · ${describeDirectionalItem(csi, '沪深300 待确认')} · ${describeDirectionalItem(hsi, '港股待确认')}`,
    global: `宏观压力${scoreStateLabel(temperature.scores.macroPressure, true)} · ${describeDirectionalItem(dxy, 'DXY 待确认')} · ${describeDirectionalItem(us10y, 'US10Y 待确认')}`,
    crypto: `${describeDirectionalItem(btc, 'BTC 待确认')} · ${describeDirectionalItem(findPanelItem(panels.crypto, ['ETH']), 'ETH 待确认')} · 宏观风险${riskLabel}`,
  };

  const qualityHint = dataQuality.hasConcern ? ` · ${dataQuality.status}` : '';
  return {
    text: `${texts[activeCategory]}${qualityHint}`,
    chips,
  };
}

function resolveProviderStatus(meta?: Partial<MarketDataMeta>): MarketProviderHealthStatus {
  if (meta?.providerHealth?.status) {
    return meta.providerHealth.status;
  }
  if (meta?.isRefreshing) {
    return 'refreshing';
  }
  if (meta?.source === 'unavailable') {
    return 'unavailable';
  }
  if (meta?.freshness === 'error') {
    return 'error';
  }
  if (meta?.isFallback || meta?.source === 'fallback' || meta?.freshness === 'fallback' || meta?.freshness === 'mock') {
    return 'fallback';
  }
  if (meta?.isStale || meta?.freshness === 'stale') {
    return 'stale';
  }
  if (meta?.freshness === 'live') {
    return 'live';
  }
  return 'cache';
}

function collectDataStateMeta(panels: PanelState): Array<Partial<MarketDataMeta>> {
  const panelKeys: CardKey[] = ['indices', 'volatility', 'crypto', 'sentiment', 'fundsFlow', 'macro', 'cnIndices', 'cnBreadth', 'cnFlows', 'sectorRotation', 'usBreadth', 'rates', 'fxCommodities'];
  const entries: Array<Partial<MarketDataMeta>> = [];
  panelKeys.forEach((key) => {
    const panel = panels[key] as MarketOverviewPanel | undefined;
    if (panel) {
      entries.push(panel);
    }
  });
  entries.push(panels.temperature, panels.briefing, panels.futures, panels.cnShortSentiment);
  return entries;
}

function shouldSuppressRepeatedItemStatus(panel: MarketOverviewPanel, item: MarketOverviewItem): boolean {
  const panelStatus = resolveProviderStatus(panel);
  if (!['fallback', 'stale', 'refreshing', 'error', 'unavailable', 'partial'].includes(panelStatus)) {
    return false;
  }
  return resolveProviderStatus(item) === panelStatus;
}

const MarketOverviewRow: React.FC<{
  row: MarketOverviewLayoutRow;
  children: React.ReactNode;
}> = ({ row, children }) => (
  <section
    data-testid="market-overview-row"
    data-row-id={row.id}
    data-row-tier={row.tier}
    data-row-columns={row.columns}
    className={cn(
      'grid w-full min-w-0 grid-cols-1 items-stretch gap-4',
      row.columns === 2 ? 'md:grid-cols-2 md:auto-rows-fr' : '',
      row.columns === 3 ? 'md:grid-cols-3 md:auto-rows-fr' : '',
    )}
  >
    {children}
  </section>
);

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
    <MarketOverviewCardFrame size="compact" className={cn('h-full', fallbackOnly ? 'border-orange-300/12' : '')}>
      <div className="flex h-full min-h-0 flex-col gap-3">
        <div className="flex shrink-0 items-center justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-white/40">{t('marketOverviewPage.cards.cnShortSentiment.eyebrow')}</p>
            <h2 className="mt-1 truncate text-sm font-semibold text-white/84">{title}</h2>
          </div>
          <MarketOverviewRefreshButton label={t('marketOverviewPage.refreshCard', { title })} refreshing={refreshing} onRefresh={onRefresh} />
        </div>
        <div className="min-w-0 rounded-lg border border-white/[0.06] bg-white/[0.025] px-3 py-2.5">
          <div className="flex items-end justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs text-white/45">{t('marketOverviewPage.cards.cnShortSentiment.score')}</p>
              <p className={cn('mt-1 font-mono text-2xl font-semibold', fallbackOnly ? 'text-white/55' : 'text-emerald-400')}>{data.sentimentScore}</p>
            </div>
            <p className="min-w-0 max-w-[220px] truncate text-right text-xs leading-5 text-white/55">{data.summary}</p>
          </div>
        </div>
        <div className="grid min-h-0 grid-cols-2 gap-2 overflow-y-auto no-scrollbar ui-scroll-y-quiet">
          {metrics.slice(0, 6).map(([key, label, value]) => (
            <div key={key} className="min-w-0 rounded-lg border border-white/[0.06] bg-white/[0.025] px-3 py-2">
              <p className="truncate text-[10px] text-white/38">{label}</p>
              <p className="mt-1 font-mono text-sm font-semibold text-white">{value}</p>
            </div>
          ))}
        </div>
        {metrics.length > 6 ? <p className="text-[10px] text-white/38">+{metrics.length - 6} 项保留在数据源快照中</p> : null}
        {loading ? <div className="mt-3 rounded-lg border border-white/8 bg-white/[0.03] p-3 text-sm text-white/60">{t('marketOverviewPage.loading')}</div> : null}
        <MarketOverviewPanelFooter panel={panel} sourceLabel={data.sourceLabel || `${t('marketOverviewPage.cards.cnShortSentiment.source')}: ${data.source.toUpperCase()}`} />
      </div>
    </MarketOverviewCardFrame>
  );
};

const ContextMetricModuleCard: React.FC<{
  moduleId: MarketOverviewModuleId;
  title: string;
  eyebrow: string;
  description: string;
  panel: MarketOverviewPanel;
  sourceLabel: string;
  refreshing?: boolean;
  onRefresh?: () => void;
}> = ({
  moduleId,
  title,
  eyebrow,
  description,
  panel,
  sourceLabel,
  refreshing = false,
  onRefresh,
}) => {
  const { t } = useI18n();
  const visibleItems = panel.items.slice(0, 8);
  const hiddenItemCount = Math.max(panel.items.length - visibleItems.length, 0);

  return (
    <MarketOverviewCardFrame
      size={MODULE_LAYOUT_META[moduleId].size}
      testId={`market-overview-module-${moduleId}`}
      className="h-full"
    >
      <div className="flex h-full min-h-0 flex-col gap-3">
        <div className="flex shrink-0 items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-white/40">{eyebrow}</p>
            <h2 className="mt-1 truncate text-sm font-semibold text-white/84">{title}</h2>
            <p className="mt-1 line-clamp-1 text-[11px] leading-4 text-white/42">{description}</p>
          </div>
          {onRefresh ? (
            <MarketOverviewRefreshButton
              label={t('marketOverviewPage.refreshCard', { title })}
              refreshing={refreshing}
              onRefresh={onRefresh}
            />
          ) : null}
        </div>
        <div className="flex min-h-0 flex-col overflow-y-auto no-scrollbar border-y border-white/[0.045] ui-scroll-y-quiet">
          {visibleItems.map((item) => (
            <MarketOverviewDenseQuoteItem
              key={`${moduleId}-${item.symbol}`}
              item={item}
              neutralLabel={t('marketOverviewPage.direction.neutral')}
              suppressFreshnessBadge={shouldSuppressRepeatedItemStatus(panel, item)}
            />
          ))}
        </div>
        {hiddenItemCount > 0 ? (
          <p className="text-[10px] text-white/38">+{hiddenItemCount} 项保留在数据源快照中</p>
        ) : null}
        <MarketOverviewPanelFooter panel={panel} sourceLabel={sourceLabel} />
      </div>
    </MarketOverviewCardFrame>
  );
};

export type MarketOverviewWorkbenchProps = {
  heading: React.ReactNode;
  panels: PanelState;
  loading: boolean;
  localSnapshotSavedAt?: string;
  refreshErrorCount: number;
  refreshingPanel: PanelKey | null;
  cryptoRealtimeStatus: CryptoRealtimeStatus;
  isCnShortSentimentBootstrapping: boolean;
  onRefreshPanel: (panelKey: PanelKey) => void;
};

export const MarketOverviewWorkbench: React.FC<MarketOverviewWorkbenchProps> = ({
  heading,
  panels,
  loading,
  localSnapshotSavedAt,
  refreshErrorCount,
  refreshingPanel,
  cryptoRealtimeStatus,
  isCnShortSentimentBootstrapping,
  onRefreshPanel,
}) => {
  const { language, t } = useI18n();
  const [activeCategory, setActiveCategory] = useState<MarketOverviewTab>('all');
  const [exportSummaryFeedback, setExportSummaryFeedback] = useState<string | null>(null);

  const categoryTabs = useMemo<MarketOverviewCategoryTabView[]>(() => [
    { key: 'all', label: t('marketOverviewPage.categories.all') },
    { key: 'us', label: t('marketOverviewPage.categories.us') },
    { key: 'cn', label: t('marketOverviewPage.categories.cn') },
    { key: 'global', label: t('marketOverviewPage.categories.macro') },
    { key: 'crypto', label: t('marketOverviewPage.categories.crypto') },
  ], [t]);

  const activeTabConfig = MARKET_OVERVIEW_TAB_CONFIG[activeCategory];
  const heroAnchors = useMemo(() => buildHeroAnchors(panels, activeTabConfig.pulse), [activeTabConfig.pulse, panels]);
  const dataQuality = useMemo(() => summarizeDataQuality(panels), [panels]);
  const coverageSummary = useMemo(() => summarizeCardCoverage(panels, CATEGORY_CARDS[activeCategory]), [activeCategory, panels]);
  const activeCategoryLabel = categoryTabs.find((tab) => tab.key === activeCategory)?.label || '';
  const exportSummaryText = useMemo(() => buildMarketOverviewSummaryText({
    activeCategoryLabel,
    coverageSummary,
    dataQuality,
    heroAnchors,
    language,
    temperature: panels.temperature,
    briefing: panels.briefing,
  }), [activeCategoryLabel, coverageSummary, dataQuality, heroAnchors, language, panels.briefing, panels.temperature]);
  const activeRows = CATEGORY_LAYOUT[activeCategory];

  const globalIndicesCard = (
    <MarketOverviewCard
      title={t('marketOverviewPage.cards.indexTrends.title')}
      eyebrow={t('marketOverviewPage.cards.indexTrends.eyebrow')}
      description={t('marketOverviewPage.cards.indexTrends.description')}
      sourceLabel={t('marketOverviewPage.cards.indexTrends.source')}
      panel={panels.indices}
      loading={loading && !panels.indices}
      refreshing={refreshingPanel === 'indices'}
      variant="denseQuote"
      onRefresh={() => {
        onRefreshPanel('indices');
      }}
    />
  );

  const cryptoSnapshotCard = (
    <div className="flex h-full min-h-0 flex-col gap-2">
      <div className="flex items-center justify-end">
        <span className="rounded-full border border-white/[0.08] bg-white/[0.03] px-2 py-0.5 text-[10px] font-semibold uppercase text-white/55">
          {cryptoRealtimeStatus === 'live' ? 'Live' : cryptoRealtimeStatus === 'reconnecting' ? 'Reconnecting' : 'Snapshot'}
        </span>
      </div>
      {cryptoRealtimeStatus === 'reconnecting' ? (
        <div className="rounded-lg border border-amber-300/20 bg-amber-400/8 px-3 py-2 text-xs text-amber-100/80">
          实时连接断开，显示最近快照
        </div>
      ) : null}
      <div className="min-h-0 flex-1">
        <MarketOverviewCard
          title={t('marketOverviewPage.cards.crypto.title')}
          eyebrow={t('marketOverviewPage.cards.crypto.eyebrow')}
          description={t('marketOverviewPage.cards.crypto.description')}
          sourceLabel={t('marketOverviewPage.cards.crypto.source')}
          panel={panels.crypto}
          loading={loading && !panels.crypto}
          refreshing={refreshingPanel === 'crypto'}
          variant="denseQuote"
          onRefresh={() => {
            onRefreshPanel('crypto');
          }}
        />
      </div>
    </div>
  );

  const moduleNodes: Record<MarketOverviewModuleId, React.ReactNode> = {
    globalIndices: globalIndicesCard,
    usIndices: (
      <ContextMetricModuleCard
        moduleId="usIndices"
        title="US Index Core"
        eyebrow="US PRICE ACTION"
        description="SPX / NDX / DJI / RUT"
        panel={buildMetricPanel(panels, 'UsIndexCoreModule', ['SPX', 'NDX', 'DJI', 'RUT'])}
        sourceLabel={t('marketOverviewPage.cards.indexTrends.source')}
        refreshing={refreshingPanel === 'indices'}
        onRefresh={() => {
          onRefreshPanel('indices');
        }}
      />
    ),
    cnHkIndices: (
      <ContextMetricModuleCard
        moduleId="cnHkIndices"
        title={t('marketOverviewPage.cards.cnIndices.title')}
        eyebrow="A股 / 港股"
        description="上证 / 深成 / 创业板 / 沪深300 / 恒生 / A50 / USDCNH"
        panel={buildMetricPanel(panels, 'CnHkIndexCoreModule', ['SHCOMP', 'SZCOMP', 'CHINEXT', 'CSI300', 'HSI', 'HSTECH', 'A50', 'USDCNH'])}
        sourceLabel={t('marketOverviewPage.cards.cnIndices.source')}
        refreshing={refreshingPanel === 'cnIndices'}
        onRefresh={() => {
          onRefreshPanel('cnIndices');
        }}
      />
    ),
    cryptoCore: (
      <ContextMetricModuleCard
        moduleId="cryptoCore"
        title="加密核心"
        eyebrow="加密资产"
        description="BTC / ETH / SOL / BNB"
        panel={buildMetricPanel(panels, 'CryptoCoreModule', ['BTC', 'ETH', 'SOL', 'BNB'])}
        sourceLabel={t('marketOverviewPage.cards.crypto.source')}
        refreshing={refreshingPanel === 'crypto'}
        onRefresh={() => {
          onRefreshPanel('crypto');
        }}
      />
    ),
    volatility: (
      <VolatilityCard
        panel={panels.volatility}
        loading={loading && !panels.volatility}
        refreshing={refreshingPanel === 'volatility'}
        onRefresh={() => {
          onRefreshPanel('volatility');
        }}
      />
    ),
    fundsFlow: (
      <FundsFlowCard
        panel={panels.fundsFlow}
        loading={loading && !panels.fundsFlow}
        refreshing={refreshingPanel === 'fundsFlow'}
        onRefresh={() => {
          onRefreshPanel('fundsFlow');
        }}
      />
    ),
    sentiment: (
      <MarketSentimentCard
        panel={panels.sentiment}
        loading={loading && !panels.sentiment}
        refreshing={refreshingPanel === 'sentiment'}
        onRefresh={() => {
          onRefreshPanel('sentiment');
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
        variant="denseQuote"
        onRefresh={() => {
          onRefreshPanel('rates');
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
        variant="denseQuote"
        onRefresh={() => {
          onRefreshPanel('fxCommodities');
        }}
      />
    ),
    cryptoSnapshot: cryptoSnapshotCard,
    cnSnapshot: (
      <MarketOverviewCard
        title={t('marketOverviewPage.cards.cnIndices.title')}
        eyebrow={t('marketOverviewPage.cards.cnIndices.eyebrow')}
        description={t('marketOverviewPage.cards.cnIndices.description')}
        sourceLabel={t('marketOverviewPage.cards.cnIndices.source')}
        panel={panels.cnIndices}
        loading={loading && !panels.cnIndices}
        refreshing={refreshingPanel === 'cnIndices'}
        variant="denseQuote"
        onRefresh={() => {
          onRefreshPanel('cnIndices');
        }}
      />
    ),
    usRates: (
      <ContextMetricModuleCard
        moduleId="usRates"
        title="US Rates"
        eyebrow="RATES / USD"
        description="US10Y / US2Y / US30Y / DXY"
        panel={buildMetricPanel(panels, 'UsRatesModule', ['US10Y', 'US2Y', 'US30Y', 'DXY'])}
        sourceLabel={t('marketOverviewPage.cards.rates.source')}
        refreshing={refreshingPanel === 'rates' || refreshingPanel === 'fxCommodities'}
        onRefresh={() => {
          onRefreshPanel('rates');
        }}
      />
    ),
    usSentiment: (
      <MarketSentimentCard
        panel={panels.sentiment}
        loading={loading && !panels.sentiment}
        refreshing={refreshingPanel === 'sentiment'}
        onRefresh={() => {
          onRefreshPanel('sentiment');
        }}
      />
    ),
    usBreadth: (
      <ContextMetricModuleCard
        moduleId="usBreadth"
        title="美股宽度"
        eyebrow="宽度代理"
        description="行业 ETF 代理 / RSP vs SPY / IWM vs SPY"
        panel={buildFilteredPanel(
          panels.usBreadth,
          'UsBreadthProxyModule',
          ['SECTORS_UP', 'SECTORS_DOWN', 'STRONGEST_SECTOR', 'WEAKEST_SECTOR', 'RSP_SPY', 'IWM_SPY', 'QQQ_SPY', 'SECTOR_PROXY_UNAVAILABLE'],
        )}
        sourceLabel="行业 ETF 代理"
        refreshing={refreshingPanel === 'usBreadth'}
        onRefresh={() => {
          onRefreshPanel('usBreadth');
        }}
      />
    ),
    usSectorRotation: (
      <ContextMetricModuleCard
        moduleId="usSectorRotation"
        title="行业健康度"
        eyebrow="行业 ETF"
        description="美股行业 ETF 强弱代理"
        panel={buildFilteredPanel(
          panels.usBreadth,
          'UsSectorHealthModule',
          ['STRONGEST_SECTOR', 'WEAKEST_SECTOR', 'XLK', 'XLF', 'XLY', 'XLE', 'XLV', 'XLI', 'XLP', 'XLU', 'SECTOR_PROXY_UNAVAILABLE'],
        )}
        sourceLabel="Yahoo Finance"
        refreshing={refreshingPanel === 'usBreadth'}
        onRefresh={() => {
          onRefreshPanel('usBreadth');
        }}
      />
    ),
    macroContext: (
      <ContextMetricModuleCard
        moduleId="macroContext"
        title="宏观压力"
        eyebrow="辅助上下文"
        description="DXY / US10Y / VIX / BTC"
        panel={buildMetricPanel(panels, 'UsMacroContextModule', ['DXY', 'US10Y', 'VIX', 'BTC'])}
        sourceLabel="宏观上下文"
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
          onRefreshPanel('cnBreadth');
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
          onRefreshPanel('cnFlows');
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
          onRefreshPanel('sectorRotation');
        }}
      />
    ),
    shortSentiment: (
      <CnShortSentimentCard
        data={panels.cnShortSentiment}
        loading={isCnShortSentimentBootstrapping}
        refreshing={refreshingPanel === 'cnShortSentiment'}
        onRefresh={() => {
          onRefreshPanel('cnShortSentiment');
        }}
      />
    ),
    fxCnhContext: (
      <ContextMetricModuleCard
        moduleId="fxCnhContext"
        title="CNH / 外部压力"
        eyebrow="FX / RATES"
        description="USDCNH / DXY / US10Y"
        panel={buildMetricPanel(panels, 'CnhContextModule', ['USDCNH', 'DXY', 'US10Y'])}
        sourceLabel={t('marketOverviewPage.cards.fxCommodities.source')}
      />
    ),
    macroRates: (
      <ContextMetricModuleCard
        moduleId="macroRates"
        title="利率核心"
        eyebrow="全球宏观"
        description="US10Y / US2Y / US30Y"
        panel={buildMetricPanel(panels, 'MacroRatesModule', ['US10Y', 'US2Y', 'US30Y'])}
        sourceLabel={t('marketOverviewPage.cards.rates.source')}
        refreshing={refreshingPanel === 'rates'}
        onRefresh={() => {
          onRefreshPanel('rates');
        }}
      />
    ),
    macroFxCommodities: (
      <ContextMetricModuleCard
        moduleId="macroFxCommodities"
        title="外汇 / 商品"
        eyebrow="美元 / 实物资产"
        description="DXY / USDJPY / USDCNH / GOLD / WTI"
        panel={buildMetricPanel(panels, 'MacroFxCommoditiesModule', ['DXY', 'USDJPY', 'USDCNH', 'GOLD', 'WTI'])}
        sourceLabel={t('marketOverviewPage.cards.fxCommodities.source')}
        refreshing={refreshingPanel === 'fxCommodities'}
        onRefresh={() => {
          onRefreshPanel('fxCommodities');
        }}
      />
    ),
    globalRisk: (
      <ContextMetricModuleCard
        moduleId="globalRisk"
        title="全球风险"
        eyebrow="风险资产"
        description="VIX / BTC / SPX"
        panel={buildMetricPanel(panels, 'GlobalRiskModule', ['VIX', 'BTC', 'SPX'])}
        sourceLabel="风险上下文"
      />
    ),
    cryptoMomentum: (
      <ContextMetricModuleCard
        moduleId="cryptoMomentum"
        title="加密动量"
        eyebrow="趋势"
        description="BTC / ETH / SOL / BNB 的 24H 动量"
        panel={buildMetricPanel(panels, 'CryptoMomentumModule', ['BTC', 'ETH', 'SOL', 'BNB'])}
        sourceLabel={t('marketOverviewPage.cards.crypto.source')}
        refreshing={refreshingPanel === 'crypto'}
        onRefresh={() => {
          onRefreshPanel('crypto');
        }}
      />
    ),
    cryptoLiquidity: (
      <ContextMetricModuleCard
        moduleId="cryptoLiquidity"
        title="加密流动性"
        eyebrow="资金费率 / 流动性"
        description="资金费率；稳定币与占比在可靠数据源接入前保持不可用"
        panel={buildCryptoLiquidityPanel(panels.crypto)}
        sourceLabel="Binance Futures / 未接入上下文"
        refreshing={refreshingPanel === 'crypto'}
        onRefresh={() => {
          onRefreshPanel('crypto');
        }}
      />
    ),
    cryptoRiskContext: (
      <ContextMetricModuleCard
        moduleId="cryptoRiskContext"
        title="加密风险上下文"
        eyebrow="宏观压力"
        description="DXY / US10Y / VIX 作为辅助风险压力"
        panel={buildMetricPanel(panels, 'CryptoRiskContextModule', ['DXY', 'US10Y', 'VIX'])}
        sourceLabel="宏观压力"
      />
    ),
    cryptoSentiment: (
      <MarketSentimentCard
        panel={panels.sentiment}
        loading={loading && !panels.sentiment}
        refreshing={refreshingPanel === 'sentiment'}
        onRefresh={() => {
          onRefreshPanel('sentiment');
        }}
      />
    ),
  };

  const hasRenderableModule = (moduleId: MarketOverviewModuleId): boolean => {
    if (loading) {
      return true;
    }
    if (moduleId === 'shortSentiment') {
      return Boolean(panels.cnShortSentiment.summary || panels.cnShortSentiment.warning);
    }
    if (moduleId === 'cryptoLiquidity') {
      return true;
    }
    const cards = MODULE_COVERAGE_CARDS[moduleId];
    if (cards.length === 0) {
      return true;
    }
    const panel = cards.map((cardKey) => panels[cardKey] as MarketOverviewPanel | undefined)
      .find((candidate) => candidate?.errorMessage || (candidate?.items?.length || 0) > 0);
    return Boolean(panel?.errorMessage || (panel?.items?.length || 0) > 0);
  };

  const moduleCardTestId: Partial<Record<MarketOverviewModuleId, string>> = {
    globalIndices: 'indices',
    usIndices: 'indices',
    cnHkIndices: 'cnIndices',
    cryptoSnapshot: 'crypto',
    cnSnapshot: 'cnIndices',
    shortSentiment: 'cnShortSentiment',
    macroRates: 'rates',
    macroFxCommodities: 'fxCommodities',
    usSentiment: 'sentiment',
    cryptoSentiment: 'sentiment',
  };

  const renderModule = (moduleId: MarketOverviewModuleId, rank: number, rail: WorkbenchRail = 'hero') => {
    const layoutMeta = MODULE_LAYOUT_META[moduleId];
    const cardTestId = moduleCardTestId[moduleId] || moduleId;
    return (
      <div
        key={moduleId}
        data-testid={`market-overview-card-${cardTestId}`}
        data-market-overview-module={moduleId}
        data-market-card-rank={rank}
        data-market-card-row={rail}
        data-market-card-size={layoutMeta.size}
        data-market-card-density={DENSE_QUOTE_MODULES.has(moduleId) ? 'dense-quote' : 'standard'}
        className="h-full min-w-0 w-full overflow-hidden"
      >
        {moduleNodes[moduleId]}
      </div>
    );
  };

  const renderPlannedRow = (row: MarketOverviewLayoutRow, rowIndex: number) => {
    const modules = row.modules.filter(hasRenderableModule);
    if (modules.length === 0) {
      return null;
    }
    const plannedRow = modules.length === 1 && row.allowSingleFullWidth
      ? { ...row, columns: 1 as const }
      : { ...row, columns: Math.min(row.columns, modules.length) as MarketOverviewRowColumns };
    const children = modules.map((moduleId, moduleIndex) => renderModule(moduleId, rowIndex * 10 + moduleIndex, row.tier));
    return <MarketOverviewRow key={row.id} row={plannedRow}>{children}</MarketOverviewRow>;
  };

  const handleExportSummary = useCallback(async () => {
    await navigator.clipboard.writeText(exportSummaryText);
    setExportSummaryFeedback(language === 'en' ? 'Summary copied' : '已复制摘要');
  }, [exportSummaryText, language]);

  const marketDecision = buildMarketDecision({ activeCategory, panels, dataQuality });
  const decisionReliable = isTemperatureReliable(panels.temperature);
  const dataStateStatuses = collectDataStateMeta(panels).map(resolveProviderStatus);
  const fallbackCount = dataQuality.counts.fallback + dataQuality.counts.mock;
  const unavailableCount = dataStateStatuses.filter((status) => status === 'partial' || status === 'unavailable' || status === 'error').length + refreshErrorCount;
  const dataStateView: MarketOverviewDataStateStripView = {
    availableCount: dataQuality.counts.live + dataQuality.counts.delayed + dataQuality.counts.cached,
    fallbackCount,
    staleCount: dataQuality.counts.stale,
    hasUnavailable: unavailableCount > 0,
    unavailableCount,
    hasFallback: fallbackCount > 0,
    needsRefresh: dataQuality.counts.stale > 0 || refreshErrorCount > 0 || !localSnapshotSavedAt,
    isRefreshing: loading || refreshingPanel !== null,
    updatedAtLabel: formatMarketOverviewTimestamp(localSnapshotSavedAt) || '',
    variant: unavailableCount > 0 || dataQuality.hasConcern
      ? 'caution'
      : loading || refreshingPanel !== null
        ? 'info'
        : 'neutral',
  };
  const temperatureSummary: MarketOverviewTemperatureSummaryView = {
    reliable: decisionReliable,
    valueText: decisionReliable ? formatNumber(panels.temperature.scores.overall.value, 0) : 'N/A',
    toneClass: decisionReliable ? scoreTone(panels.temperature.scores.overall) : 'text-white/45',
    label: decisionReliable ? panels.temperature.scores.overall.label : '数据不足',
    confidenceLabel: confidenceLabel(panels.temperature.confidence),
    reliableInputCount: panels.temperature.reliableInputCount ?? 0,
    fallbackInputCount: panels.temperature.fallbackInputCount ?? 0,
    excludedInputCount: panels.temperature.excludedInputCount ?? 0,
  };
  const briefingSummary: MarketOverviewBriefingSummaryView = {
    confidenceLabel: confidenceLabel(panels.briefing.confidence),
    toneClass: panels.briefing.isReliable === false || panels.briefing.isFallback ? 'text-amber-200' : 'text-white',
    leadMessage: panels.briefing.items[0]?.message || panels.briefing.warning || '暂无简报',
    warning: panels.briefing.warning || undefined,
  };
  const heroAnchorViews = heroAnchors.map<MarketOverviewHeroAnchorView>((anchor) => {
    const displayLabel = anchor.item
      ? resolveMarketOverviewDisplayLabel(anchor.item, language)
      : { primary: anchor.label, secondary: anchor.key };
    return {
      key: anchor.key,
      primaryLabel: displayLabel.primary,
      secondaryLabel: displayLabel.secondary,
      valueText: formatHeroValue(anchor.item?.value),
      changeText: formatHeroChange(anchor.item?.changePct),
      changeToneClass: heroToneClass(anchor.item),
    };
  });
  const coverageRail: MarketOverviewCoverageRailView = {
    label: activeCategoryLabel,
    real: coverageSummary.real,
    mixed: coverageSummary.mixed,
    fallback: coverageSummary.fallback,
    total: coverageSummary.real + coverageSummary.mixed + coverageSummary.fallback,
  };
  const qualityRail: MarketOverviewQualityRailView = {
    status: dataQuality.status,
    availableCount: dataQuality.counts.live + dataQuality.counts.delayed + dataQuality.counts.cached,
    fallbackCount: dataQuality.counts.fallback,
    staleCount: dataQuality.counts.stale,
    errorCount: dataQuality.counts.error,
    hasConcern: dataQuality.hasConcern,
  };
  const signalWatchItems = MARKET_OVERVIEW_SIGNAL_WATCH[activeCategory].map<MarketOverviewSignalWatchRailItem>((metricId) => {
    const item = findMetricItem(panels, metricId) || missingMetricItem(metricId);
    return {
      label: metricId,
      changeText: formatHeroChange(item.changePct),
      changeToneClass: heroToneClass(item),
    };
  });
  const actionHint: MarketOverviewActionHintView = {
    title: decisionReliable ? '同步观察' : '安全状态',
    line: decisionReliable ? '优先观察风险、流动性、宽度是否同向变化' : '等待实时源补齐后再生成强判断',
  };
  const executiveGroups: MarketOverviewExecutiveGroupView[] = [
    { id: 'us', label: 'US', focus: 'SPX / VIX', cardKey: 'indices', item: findPanelItem(panels.indices, ['SPX']) },
    { id: 'cn', label: 'CN/HK', focus: 'CSI300 / HSI', cardKey: 'cnIndices', item: findPanelItem(panels.cnIndices, ['CSI300', '000300.SH']) || findPanelItem(panels.cnIndices, ['HSI']) },
    { id: 'macro', label: 'MACRO', focus: 'US10Y / DXY', cardKey: 'rates', item: findPanelItem(panels.rates, ['US10Y']) || findPanelItem(panels.fxCommodities, ['DXY']) },
    { id: 'crypto', label: 'CRYPTO', focus: 'BTC / ETH', cardKey: 'crypto', item: findPanelItem(panels.crypto, ['BTC']) },
  ].map((group) => {
    const coverage = getCardCoverageKind(panels, group.cardKey as CardKey);
    return {
      id: group.id,
      label: group.label,
      focus: group.focus,
      valueText: formatHeroValue(group.item?.value),
      changeText: formatHeroChange(group.item?.changePct),
      changeToneClass: heroToneClass(group.item),
      freshness: getCardMeta(panels, group.cardKey as CardKey).freshness as MarketOverviewPanel['freshness'],
      coverage,
    };
  });
  const heroRows = activeRows.filter((row) => row.tier === 'hero').map(renderPlannedRow).filter(Boolean) as React.ReactNode[];
  const secondaryRows = activeRows.filter((row) => row.tier === 'secondary').map(renderPlannedRow).filter(Boolean) as React.ReactNode[];
  const deepRows = activeRows.filter((row) => row.tier === 'deep').map(renderPlannedRow).filter(Boolean) as React.ReactNode[];

  return (
    <div
      data-testid="market-overview-shell"
      data-bento-surface="true"
      className="bento-surface-root flex min-h-0 w-full min-w-0 flex-1 flex-col gap-6 bg-[#030303] text-white"
    >
      <TerminalPageShell data-testid="market-overview-workbench" className="flex min-h-0 flex-1">
        <MarketOverviewWorkbenchTopSurface
          heading={heading}
          decisionText={marketDecision.text}
          decisionChips={marketDecision.chips}
          decisionReliable={decisionReliable}
          dataState={dataStateView}
          temperatureSummary={temperatureSummary}
          briefingSummary={briefingSummary}
          categoryTabs={categoryTabs}
          activeCategory={activeCategory}
          onCategoryChange={setActiveCategory}
          exportLabel={exportSummaryFeedback || (language === 'en' ? 'Export' : '复制摘要')}
          onExportSummary={() => {
            void handleExportSummary();
          }}
          heroAnchors={heroAnchorViews}
        />
        <MarketOverviewWorkbenchGrid
          heroRows={heroRows}
          secondaryRows={secondaryRows}
          deepRows={deepRows}
          showDeepSection={activeRows.some((row) => row.tier === 'deep') || activeCategory === 'all'}
          showCoverageRail={activeTabConfig.rail.includes('coverage')}
          showQualityRail={activeTabConfig.rail.includes('quality')}
          showSignalWatchRail={activeTabConfig.rail.includes('signalWatch')}
          showActionHintRail={activeTabConfig.rail.includes('actionHint')}
          coverageRail={coverageRail}
          qualityRail={qualityRail}
          signalWatchItems={signalWatchItems}
          actionHint={actionHint}
          executiveGroups={executiveGroups}
          showExecutiveGroups={activeCategory === 'all'}
        />
      </TerminalPageShell>
    </div>
  );
};
