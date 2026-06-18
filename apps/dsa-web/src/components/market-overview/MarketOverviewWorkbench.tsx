import type React from 'react';
import { Suspense, lazy, useState } from 'react';
import type { MarketDataMeta, MarketOverviewItem, MarketOverviewPanel, MarketProviderHealthStatus } from '../../api/marketOverview';
import type {
  CnShortSentimentResponse,
  MarketDecisionSemantics,
  MarketDecisionSemanticsClaimBoundary,
  MarketDecisionSemanticsItem,
  MarketDirectionReadiness,
  MarketDirectionReadinessPillar,
  MarketBriefingResponse,
  MarketRegimeSynthesis,
  MarketRegimeSynthesisEvidenceItem,
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
import type {
  MarketOverviewContextHighlightView,
  MarketOverviewExecutiveGroupView,
} from './MarketOverviewWorkbenchGrid';
import {
  MarketOverviewWorkbenchTopSurface,
  MarketOverviewVisualEvidenceStrip,
  type MarketOverviewBriefingSummaryView,
  type MarketOverviewCategoryTabView,
  type MarketOverviewDataStateStripView,
  type MarketOverviewDecisionChipView,
  type MarketOverviewDecisionSemanticsBoundaryView,
  type MarketOverviewDecisionSemanticsLineView,
  type MarketOverviewDecisionSemanticsView,
  type MarketOverviewDirectionReadinessView,
  type MarketOverviewHeroAnchorView,
  type MarketOverviewRegimeSummaryView,
  type MarketOverviewTemperatureSummaryView,
  type MarketOverviewVisualEvidenceCardView,
} from './MarketOverviewWorkbenchTopSurface';
import type { MarketRegimeSynthesisEvidenceView, MarketRegimeSynthesisHeaderView } from './MarketRegimeSynthesisHeader';
import { resolveMarketOverviewDisplayLabel } from './marketOverviewLabels';
import { formatMarketOverviewTimestamp } from './marketOverviewFormat';
import {
  MarketOverviewCardFrame,
  MarketOverviewDenseQuoteItem,
  MarketOverviewPanelFooter,
  MarketOverviewRefreshButton,
} from './marketOverviewPrimitives';
import { TerminalChip, TerminalGrid, TerminalPanel } from '../terminal/TerminalPrimitives';
import { useI18n } from '../../contexts/UiLanguageContext';
import { cn } from '../../utils/cn';
import { mapConsumerStatusText } from '../../utils/consumerStatusLabels';
import type { OfficialMacroAuthorityRecord } from '../common/officialMacroAuthorityDiagnosticsData';
import {
  buildMarketDirectionalSummary,
  marketIntelligenceReasonLabel,
  type MarketDirectionalSummary,
} from '../../utils/marketIntelligenceGuidance';
import { buildMarketIntelligenceEvidenceMarkdown } from '../../utils/marketIntelligenceEvidenceExport';

const MARKET_OVERVIEW_GRID_FALLBACK_MIN_MS = 120;

const LazyMarketOverviewWorkbenchGrid = lazy(async () => {
  const [module] = await Promise.all([
    import('./MarketOverviewWorkbenchGrid'),
    new Promise((resolve) => setTimeout(resolve, MARKET_OVERVIEW_GRID_FALLBACK_MIN_MS)),
  ]);
  return { default: module.MarketOverviewWorkbenchGrid };
});

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
type MarketOverviewSectionMeta = {
  eyebrow: string;
  title: string;
  detail: string;
};
type EvidenceSnapshotCopyState = 'idle' | 'copied' | 'failed';

function evidenceSnapshotCopyLabel(
  language: 'zh' | 'en',
  state: EvidenceSnapshotCopyState,
  isAvailable: boolean,
): string {
  if (!isAvailable) {
    return language === 'en' ? 'Evidence snapshot unavailable' : '证据快照暂不可用';
  }
  if (state === 'copied') {
    return language === 'en' ? 'Evidence snapshot copied' : '证据快照已复制';
  }
  if (state === 'failed') {
    return language === 'en' ? 'Copy failed. Try again' : '复制失败，请重试';
  }
  return language === 'en' ? 'Copy evidence snapshot' : '复制证据快照';
}
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
type FreshnessCountKey = 'live' | 'delayed' | 'cached' | 'stale' | 'fallback' | 'mock' | 'error' | 'unavailable';
type DataQualitySummary = {
  status: string;
  counts: Record<FreshnessCountKey, number>;
  hasConcern: boolean;
};
type TopLevelDataStatusKind =
  | 'refreshing'
  | 'delayedAvailable'
  | 'proxyPartialAvailable'
  | 'mixedDataAvailable'
  | 'fallbackOnlyUnavailable';
type TopLevelDataStatus = {
  kind: TopLevelDataStatusKind;
  headline: string;
  detail?: string;
  hasUsableData: boolean;
  hasMissingPanels: boolean;
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
  'volatility',
  'fundsFlow',
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

const DENSE_QUOTE_ROW_FIT_CLASS = [
  "[&_[data-testid='market-overview-dense-quote-grid']]:min-w-0",
  "[&_[data-testid='market-overview-dense-quote-grid']]:overflow-x-hidden",
  "[&_[data-testid='market-overview-dense-quote-item']]:overflow-hidden",
  "[&_[data-testid='market-overview-dense-quote-item']]:grid-cols-[minmax(0,1fr)_minmax(0,0.72fr)_minmax(44px,56px)_minmax(62px,max-content)_minmax(64px,max-content)]",
  "[&_[data-testid='market-overview-dense-quote-sparkline']]:w-[56px]",
  "[&_[data-testid='market-overview-quote-value']]:min-w-[62px]",
  "[&_[data-testid='market-overview-quote-change']]:min-w-[64px]",
  "max-[720px]:[&_[data-testid='market-overview-dense-quote-item']]:grid-cols-[minmax(0,1fr)_minmax(44px,56px)_minmax(62px,max-content)]",
  "max-[720px]:[&_[data-testid='market-overview-dense-quote-sparkline']]:w-[56px]",
  "max-[520px]:[&_[data-testid='market-overview-dense-quote-item']]:grid-cols-[minmax(0,1fr)_minmax(62px,max-content)]",
  "max-[520px]:[&_[data-testid='market-overview-dense-quote-sparkline']]:hidden",
  "max-[520px]:[&_[data-testid='market-overview-quote-value']]:col-start-2",
  "max-[520px]:[&_[data-testid='market-overview-quote-change']]:col-start-2",
].join(' ');

const MODULE_CARD_TEST_ID: Partial<Record<MarketOverviewModuleId, string>> = {
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

const US_BREADTH_AD_SYMBOLS = ['ADVANCERS', 'DECLINERS', 'UNCHANGED', 'ADVANCE_DECLINE_RATIO'];
const US_BREADTH_HIGH_LOW_SYMBOLS = ['NEW_HIGHS', 'NEW_LOWS', 'HIGH_LOW_RATIO'];
const US_BREADTH_ALL_SYMBOLS = [...US_BREADTH_AD_SYMBOLS, ...US_BREADTH_HIGH_LOW_SYMBOLS];
const US_BREADTH_PROXY_SYMBOLS = ['SECTORS_UP', 'SECTORS_DOWN', 'STRONGEST_SECTOR', 'WEAKEST_SECTOR', 'RSP_SPY', 'IWM_SPY', 'QQQ_SPY', 'SECTOR_PROXY_UNAVAILABLE'];
const MARKET_OVERVIEW_CRYPTO_CONSUMER_DESCRIPTION = '跟踪 BTC、ETH、BNB 的现价、24H 涨跌和 7D 走势；异常时显示最近一次可用快照。';
const US_BREADTH_HIGH_LOW_LABELS: Record<string, string> = {
  NEW_HIGHS: 'NEW_HIGHS',
  NEW_LOWS: 'NEW_LOWS',
  HIGH_LOW_RATIO: 'HIGH_LOW_RATIO',
};
const US_BREADTH_INPUT_LABELS: Record<string, string> = {
  ADVANCERS: '上涨家数',
  DECLINERS: '下跌家数',
  UNCHANGED: '平盘家数',
  ADVANCE_DECLINE_RATIO: '上涨/下跌比',
  NEW_HIGHS: '新高家数',
  NEW_LOWS: '新低家数',
  HIGH_LOW_RATIO: '新高/新低比',
};
const US_BREADTH_FRESHNESS_LABELS: Record<string, string> = {
  live: '可用',
  delayed: '延迟可用',
  cached: '延迟可用',
  stale: '延迟可用',
  fallback: '延迟可用',
  mock: '证据不足',
  error: '暂不可用',
  unavailable: '暂不可用',
};

type UsBreadthTruthStripView = {
  stateLabel: string;
  stateVariant: 'neutral' | 'success' | 'caution' | 'info' | 'danger';
  sourceLabel: string;
  sourceVariant: 'neutral' | 'success' | 'caution' | 'info';
  freshnessLabel: string;
  freshnessVariant: 'neutral' | 'success' | 'caution' | 'info' | 'danger';
  coverageLabel: string;
  coverageVariant: 'neutral' | 'success' | 'caution' | 'info';
  summary: string;
  missingSummary: string | null;
};

const numberFormatCache = new Map<number, Intl.NumberFormat>();
function getCachedNumberFormat(maximumFractionDigits: number): Intl.NumberFormat {
  let fmt = numberFormatCache.get(maximumFractionDigits);
  if (!fmt) {
    fmt = Intl.NumberFormat('en-US', { maximumFractionDigits });
    numberFormatCache.set(maximumFractionDigits, fmt);
  }
  return fmt;
}

function buildCategoryLayout(tab: MarketOverviewTab): MarketOverviewLayoutRow[] {
  const config = MARKET_OVERVIEW_TAB_CONFIG[tab];
  const rows: MarketOverviewLayoutRow[] = [];
  const promoteTopSummaryCards = tab === 'all' && config.hero.length === 1 && config.modules.length >= 2;
  const topRowModules = promoteTopSummaryCards
    ? [config.hero[0], ...config.modules.slice(0, 2)]
    : config.hero;
  if (config.hero.length > 0) {
    rows.push({
      id: `${tab}-hero`,
      tier: 'hero',
      columns: Math.min(topRowModules.length, 3) as MarketOverviewRowColumns,
      modules: topRowModules,
      allowSingleFullWidth: true,
    });
  }
  const remainingModules = promoteTopSummaryCards ? config.modules.slice(2) : config.modules;
  for (let index = 0; index < remainingModules.length; index += 2) {
    const modules = remainingModules.slice(index, index + 2);
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

const CATEGORY_SECTION_META: Record<MarketOverviewTab, Record<string, MarketOverviewSectionMeta>> = {
  all: {
    'all-hero': { eyebrow: '核心指数', title: '先看大盘方向', detail: '用全球核心指数判断风险偏好是否同向。' },
    'all-modules-1': { eyebrow: '风险与资金', title: '再看波动、资金与情绪', detail: '确认上涨或下跌是否得到波动和资金面的支持。' },
    'all-modules-2': { eyebrow: '利率与大类', title: '跟踪利率、汇率与商品压力', detail: '判断宏观约束是否开始压制风险资产。' },
    'all-modules-3': { eyebrow: '跨市场补充', title: '补看加密与中港市场', detail: '观察是否出现跨资产背离或区域分化。' },
  },
  us: {
    'us-hero': { eyebrow: '美股基准', title: '先看四大指数是否共振', detail: '指数方向先于风格与行业细节。' },
    'us-modules-1': { eyebrow: '压力与利率', title: '确认波动与利率是否抬头', detail: '风险偏好改善需要波动回落与利率稳定配合。' },
    'us-modules-2': { eyebrow: '情绪与宽度', title: '看上涨是否扩散', detail: '情绪与宽度决定行情是否只是权重股驱动。' },
    'us-modules-3': { eyebrow: '轮动与宏观', title: '观察行业切换与外部约束', detail: '宏观压力若转强，宽度改善往往难以持续。' },
  },
  cn: {
    'cn-hero': { eyebrow: 'A/H 核心', title: '先看 A 股与港股主指数', detail: '指数状态决定后续对宽度和短线情绪的解释方式。' },
    'cn-modules-1': { eyebrow: '宽度与资金', title: '确认赚钱效应是否扩散', detail: '宽度与资金流决定反弹是全面修复还是局部抱团。' },
    'cn-modules-2': { eyebrow: '轮动与短线', title: '看主题轮动和短线热度', detail: '用于判断情绪是否过热或仍处于修复早期。' },
    'cn-modules-3': { eyebrow: '外部压力', title: '补看汇率与外部扰动', detail: 'CNH 与外部利率压力常决定持续性。' },
  },
  global: {
    'global-hero': { eyebrow: '利率主线', title: '先看全球利率约束', detail: '利率是当前跨资产最核心的定价变量之一。' },
    'global-modules-1': { eyebrow: '外汇与商品', title: '观察美元与实物资产', detail: '美元、黄金、原油常用于识别避险或再通胀交易。' },
    'global-modules-2': { eyebrow: '风险状态', title: '补看波动与情绪', detail: '确认宏观定价是否已传导到风险资产。' },
  },
  crypto: {
    'crypto-hero': { eyebrow: '加密核心', title: '先看主流币方向', detail: 'BTC 与 ETH 先决定市场是风险扩张还是防守切换。' },
    'crypto-modules-1': { eyebrow: '动量与流动性', title: '确认上涨是否有资金支持', detail: '动量延续需要流动性与资金费率配合。' },
    'crypto-modules-2': { eyebrow: '外部压力', title: '补看宏观与情绪约束', detail: '美元、利率与波动压力会改变加密风险承受力。' },
  },
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
    freshness: 'unavailable',
    isUnavailable: true,
    sourceTier: 'unavailable',
    trustLevel: 'unavailable',
    degradationReason: 'metric_unavailable',
    degradationReasons: ['metric_unavailable'],
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
    ...(sourcePanel || {}),
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

function isPolygonComputedUsBreadth(panel?: MarketOverviewPanel): boolean {
  const sourceText = [
    panel?.source,
    panel?.sourceLabel,
    panel?.sourceType,
    panel?.breadthClaimType,
  ].filter(Boolean).join(' ').toLowerCase();
  const itemSymbols = new Set((panel?.items || []).map((item) => item.symbol));
  const fulfilledMetrics = new Set(panel?.fulfilledMetrics || []);
  const hasAdMetrics = US_BREADTH_AD_SYMBOLS.some((symbol) => itemSymbols.has(symbol) || fulfilledMetrics.has(symbol));
  return hasAdMetrics && sourceText.includes('polygon');
}

function hasStructuredUsBreadthMetrics(panel?: MarketOverviewPanel): boolean {
  const itemSymbols = new Set((panel?.items || []).map((item) => item.symbol));
  const fulfilledMetrics = new Set(panel?.fulfilledMetrics || []);
  return US_BREADTH_ALL_SYMBOLS.some((symbol) => itemSymbols.has(symbol) || fulfilledMetrics.has(symbol));
}

function formatUsBreadthInputLabel(symbol: string): string {
  return US_BREADTH_INPUT_LABELS[symbol] || US_BREADTH_HIGH_LOW_LABELS[symbol] || symbol;
}

function missingUsBreadthMetricItem(symbol: string, panel?: MarketOverviewPanel): MarketOverviewItem {
  const highLowMissing = US_BREADTH_HIGH_LOW_SYMBOLS.includes(symbol);
  const message = highLowMissing ? '高低点宽度缺失' : '宽度指标缺失';
  return {
    ...unavailableMarketItem(symbol, formatUsBreadthInputLabel(symbol), message),
    source: panel?.source || 'computed_from_authorized_polygon_grouped_daily',
    sourceLabel: panel?.sourceLabel || 'Polygon grouped daily',
    sourceType: panel?.sourceType,
    sourceTier: panel?.sourceTier,
    trustLevel: panel?.trustLevel,
    asOf: panel?.asOf,
    updatedAt: panel?.updatedAt,
    providerHealth: panel?.providerHealth,
    isFallback: false,
    isPartial: true,
    isUnavailable: true,
    sourceAuthorityAllowed: false,
    scoreContributionAllowed: false,
    sourceAuthorityReason: panel?.sourceAuthorityReason || 'polygon_high_low_history_unavailable',
    reasonCodes: panel?.reasonCodes,
    warning: message,
    hoverDetails: [message, '未伪造 NEW_HIGHS / NEW_LOWS / HIGH_LOW_RATIO'],
  };
}

function buildUsBreadthPanel(sourcePanel: MarketOverviewPanel | undefined): MarketOverviewPanel {
  if (hasStructuredUsBreadthMetrics(sourcePanel) && !isPolygonComputedUsBreadth(sourcePanel)) {
    const panel = buildFilteredPanel(
      sourcePanel,
      'UsBreadthStructuredModule',
      US_BREADTH_ALL_SYMBOLS,
    );
    const existingSymbols = new Set(panel.items.map((item) => item.symbol));
    const missingMetricSymbols = Array.from(new Set(sourcePanel?.missingMetrics || []))
      .filter((symbol) => US_BREADTH_ALL_SYMBOLS.includes(symbol) && !existingSymbols.has(symbol));
    return {
      ...panel,
      items: [
        ...panel.items,
        ...missingMetricSymbols.map((symbol) => missingUsBreadthMetricItem(symbol, sourcePanel)),
      ],
    };
  }

  if (!isPolygonComputedUsBreadth(sourcePanel)) {
    return buildFilteredPanel(
      sourcePanel,
      'UsBreadthProxyModule',
      US_BREADTH_PROXY_SYMBOLS,
    );
  }

  const panel = buildFilteredPanel(
    sourcePanel,
    'UsBreadthPolygonModule',
    [...US_BREADTH_AD_SYMBOLS, ...US_BREADTH_HIGH_LOW_SYMBOLS],
  );
  const existingSymbols = new Set(panel.items.map((item) => item.symbol));
  const missingMetricSymbols = Array.from(new Set(sourcePanel?.missingMetrics || []))
    .filter((symbol) => US_BREADTH_HIGH_LOW_SYMBOLS.includes(symbol) && !existingSymbols.has(symbol));

  return {
    ...panel,
    sourceLabel: panel.sourceLabel || 'Polygon grouped daily',
    isPartial: panel.isPartial ?? missingMetricSymbols.length > 0,
    items: [
      ...panel.items,
      ...missingMetricSymbols.map((symbol) => missingUsBreadthMetricItem(symbol, sourcePanel)),
    ],
  };
}

function buildUsBreadthDisclosure(panel?: MarketOverviewPanel): {
  eyebrow: string;
  description: string;
  sourceLabel: string;
  notice: string;
} {
  if (hasStructuredUsBreadthMetrics(panel) && !isPolygonComputedUsBreadth(panel)) {
    const fullCoverage = !panel?.isPartial && (panel?.missingMetrics || []).length === 0;
    return {
      eyebrow: '市场宽度',
      description: fullCoverage ? '上涨/下跌与新高/新低统计较完整' : '上涨/下跌与高低点统计仍待补齐',
      sourceLabel: '宽度快照',
      notice: fullCoverage ? '宽度统计较完整，可配合风险判断。' : '宽度统计仍有缺口，建议先结合其他风险信号观察。',
    };
  }
  if (isPolygonComputedUsBreadth(panel)) {
    const highLowMissing = (panel?.missingMetrics || []).some((symbol) => US_BREADTH_HIGH_LOW_SYMBOLS.includes(symbol));
    return {
      eyebrow: '市场宽度',
      description: `上涨/下跌统计可用${highLowMissing ? '，新高/新低仍待补齐' : '，可辅助判断扩散度'}`,
      sourceLabel: '宽度快照',
      notice: '当前宽度统计仍不完整，仅供观察。',
    };
  }
  return {
    eyebrow: '市场宽度',
    description: '行业强弱快照',
    sourceLabel: '宽度快照',
    notice: '当前只能看到局部广度线索，先作为观察参考。',
  };
}

function buildUsBreadthCoverage(panel?: MarketOverviewPanel): {
  fulfilledCount: number;
  requiredCount: number;
  missingSymbols: string[];
} {
  const fulfilled = new Set(
    (panel?.fulfilledMetrics || []).filter((symbol) => US_BREADTH_ALL_SYMBOLS.includes(symbol)),
  );
  if (fulfilled.size === 0) {
    (panel?.items || []).forEach((item) => {
      if (US_BREADTH_ALL_SYMBOLS.includes(item.symbol) && item.isUnavailable !== true) {
        fulfilled.add(item.symbol);
      }
    });
  }

  const missing = new Set(
    (panel?.missingMetrics || []).filter((symbol) => US_BREADTH_ALL_SYMBOLS.includes(symbol)),
  );
  if (fulfilled.size > 0 && missing.size === 0) {
    US_BREADTH_ALL_SYMBOLS.forEach((symbol) => {
      if (!fulfilled.has(symbol)) {
        missing.add(symbol);
      }
    });
  }
  if (fulfilled.size === 0 && missing.size === 0) {
    US_BREADTH_ALL_SYMBOLS.forEach((symbol) => missing.add(symbol));
  }

  return {
    fulfilledCount: fulfilled.size,
    requiredCount: US_BREADTH_ALL_SYMBOLS.length,
    missingSymbols: US_BREADTH_ALL_SYMBOLS.filter((symbol) => missing.has(symbol)),
  };
}

function buildUsBreadthTruthStripView(panel?: MarketOverviewPanel): UsBreadthTruthStripView {
  const coverage = buildUsBreadthCoverage(panel);
  const structuredMetrics = hasStructuredUsBreadthMetrics(panel);
  const sourceText = [
    panel?.source,
    panel?.sourceLabel,
    panel?.sourceType,
    panel?.sourceTier,
  ].filter(Boolean).join(' ').toLowerCase();
  const unavailable = panel?.isUnavailable === true
    || panel?.source === 'unavailable'
    || panel?.freshness === 'unavailable';
  const staleOrFallback = panel?.isFallback === true
    || panel?.isStale === true
    || ['stale', 'fallback', 'mock', 'error'].includes(String(panel?.freshness || ''));
  const coverageGap = coverage.missingSymbols.length > 0;
  const proxyOnly = !structuredMetrics
    || sourceText.includes('proxy')
    || sourceText.includes('unofficial')
    || panel?.sourceAuthorityReason === 'representative_sample_not_full_market_breadth'
    || (panel?.routeRejectedReasonCodes || []).includes('representative_sample_not_full_market_breadth');
  const scoreGradeReady = structuredMetrics
    && panel?.sourceAuthorityAllowed === true
    && panel?.scoreContributionAllowed === true
    && panel?.observationOnly !== true
    && !staleOrFallback
    && !unavailable
    && !coverageGap;

  const sourceLabel = unavailable
    ? '待补数据'
    : scoreGradeReady
      ? '统计较完整'
      : coverageGap
        ? '统计待补'
        : proxyOnly || staleOrFallback
          ? '仅作观察'
          : '宽度待确认';
  const stateLabel = scoreGradeReady
    ? '宽度可参考'
    : unavailable
      ? '宽度不足'
      : '宽度仅观察';
  const stateVariant = scoreGradeReady
    ? 'success'
    : unavailable
      ? 'neutral'
      : proxyOnly
        ? 'info'
        : 'caution';
  const freshnessLabel = US_BREADTH_FRESHNESS_LABELS[String(panel?.freshness || 'cached')] || '待确认';
  const freshnessVariant = panel?.freshness === 'live'
    ? 'success'
    : panel?.freshness === 'delayed' || panel?.freshness === 'cached'
      ? 'neutral'
      : panel?.freshness === 'stale'
        ? 'caution'
        : panel?.freshness === 'fallback' || panel?.freshness === 'mock'
          ? 'info'
          : panel?.freshness === 'unavailable'
            ? 'danger'
            : 'caution';
  const coverageLabel = `覆盖 ${coverage.fulfilledCount}/${coverage.requiredCount}`;
  const coverageVariant = scoreGradeReady
    ? 'success'
    : coverageGap
      ? 'caution'
      : structuredMetrics
        ? 'info'
        : 'neutral';
  const limitedMissing = coverage.missingSymbols.slice(0, 4).map((symbol) => formatUsBreadthInputLabel(symbol));
  const missingSummary = coverageGap && (structuredMetrics || unavailable)
    ? `缺口：${limitedMissing.join('、')}${coverage.missingSymbols.length > 4 ? ` 等${coverage.missingSymbols.length}项` : ''}`
    : null;
  const summary = scoreGradeReady
    ? '当前宽度扩散统计较完整，可与指数和波动一起参考。'
    : unavailable
      ? '当前宽度统计不足，先观察指数与波动是否继续共振。'
      : coverageGap
        ? '当前宽度统计仍有缺口，只适合作为辅助观察。'
        : staleOrFallback
          ? '当前显示最近一次可用宽度快照，时效可能延迟。'
          : '当前宽度线索可见，但仍需结合更多信号确认。';

  return {
    stateLabel,
    stateVariant,
    sourceLabel,
    sourceVariant: scoreGradeReady ? 'success' : proxyOnly || staleOrFallback ? 'info' : 'caution',
    freshnessLabel,
    freshnessVariant,
    coverageLabel,
    coverageVariant,
    summary,
    missingSummary,
  };
}

const UsBreadthTruthStrip: React.FC<{
  panel?: MarketOverviewPanel;
}> = ({ panel }) => {
  const view = buildUsBreadthTruthStripView(panel);
  return (
    <div
      data-testid="market-overview-us-breadth-truth-strip"
      className="rounded-lg border border-white/[0.06] bg-black/10 px-3 py-2.5"
    >
      <div className="flex min-w-0 flex-wrap gap-1.5">
        <TerminalChip variant={view.stateVariant}>{view.stateLabel}</TerminalChip>
        <TerminalChip variant={view.sourceVariant}>{view.sourceLabel}</TerminalChip>
        <TerminalChip variant={view.freshnessVariant}>{view.freshnessLabel}</TerminalChip>
        <TerminalChip variant={view.coverageVariant}>{view.coverageLabel}</TerminalChip>
      </div>
      <p className="mt-2 text-[11px] leading-5 text-white/68">{view.summary}</p>
      {view.missingSummary ? (
        <p className="mt-1 text-[11px] leading-5 text-white/52">{view.missingSummary}</p>
      ) : null}
    </div>
  );
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

function canRenderVisualEvidencePoint(item?: MarketOverviewItem): item is MarketOverviewItem {
  return Boolean(
    item
      && typeof item.value === 'number'
      && Number.isFinite(item.value)
      && Array.isArray(item.trend)
      && item.trend.filter((value) => Number.isFinite(value)).length >= 2,
  );
}

function buildVisualEvidencePoint(
  item: MarketOverviewItem | undefined,
  language: 'zh' | 'en',
): MarketOverviewVisualEvidenceCardView['points'][number] | null {
  if (!canRenderVisualEvidencePoint(item)) {
    return null;
  }
  const display = resolveMarketOverviewDisplayLabel(item, language);
  return {
    key: item.symbol,
    label: display.primary,
    valueText: formatHeroValue(item.value),
    changeText: formatHeroChange(item.changePct),
    toneClass: heroToneClass(item),
    sparkline: Array.isArray(item.trend) ? item.trend : [],
  };
}

function firstVisualItems(
  items: Array<MarketOverviewItem | undefined>,
  language: 'zh' | 'en',
  limit = 2,
): MarketOverviewVisualEvidenceCardView['points'] {
  return items
    .map((item) => buildVisualEvidencePoint(item, language))
    .filter((item): item is NonNullable<typeof item> => Boolean(item))
    .slice(0, limit);
}

function buildVisualEvidenceCards(params: {
  activeCategory: MarketOverviewTab;
  panels: PanelState;
  language: 'zh' | 'en';
}): MarketOverviewVisualEvidenceCardView[] {
  const { activeCategory, panels, language } = params;
  const watchMetricIds = MARKET_OVERVIEW_SIGNAL_WATCH[activeCategory].slice(0, 2);
  const corePoints = firstVisualItems(
    [
      ...watchMetricIds.map((metricId) => findMetricItem(panels, metricId)),
      findMetricItem(panels, 'SPX'),
      findMetricItem(panels, 'CSI300'),
      findMetricItem(panels, 'BTC'),
    ],
    language,
  );
  const riskPoints = firstVisualItems(
    [
      findMetricItem(panels, 'VIX'),
      findMetricItem(panels, 'US10Y'),
      findMetricItem(panels, 'DXY'),
    ],
    language,
  );
  const flowCandidates = [
    ...(panels.sectorRotation?.items || []),
    ...(panels.fundsFlow?.items || []),
    ...buildFilteredPanel(
      panels.usBreadth,
      'VisualSectorFlowPanel',
      ['STRONGEST_SECTOR', 'WEAKEST_SECTOR', 'XLK', 'XLF', 'XLY', 'XLE', 'XLV', 'XLI', 'XLP', 'XLU'],
    ).items,
  ].filter((item, index, array) => array.findIndex((candidate) => candidate.symbol === item.symbol) === index);
  const flowPoints = firstVisualItems(flowCandidates, language);

  return [
    {
      id: 'core-trends',
      eyebrow: '核心趋势',
      title: activeCategory === 'cn' ? '核心指数迷你趋势' : activeCategory === 'crypto' ? '核心资产迷你趋势' : '核心市场迷你趋势',
      summary: '只基于当前已加载点位展示短线轨迹，不扩展结论边界。',
      unavailableCopy: '核心趋势图形证据缺失，当前保持观察。',
      points: corePoints,
    },
    {
      id: 'risk-pressure',
      eyebrow: '风险压力',
      title: 'VIX / 风险压力',
      summary: '优先展示波动、利率与美元压力；缺失时不补推断。',
      unavailableCopy: '风险压力图形证据缺失，当前保持观察。',
      points: riskPoints,
    },
    {
      id: 'flow-rotation',
      eyebrow: '资金与轮动',
      title: 'ETF / 行业 / 资金流',
      summary: '仅展示现有资金与行业线索，避免将观察信号提升为判断。',
      unavailableCopy: '资金与轮动图形证据缺失，当前保持观察。',
      points: flowPoints,
    },
  ];
}

function formatHeroValue(value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '待确认';
  }
  return getCachedNumberFormat(Math.abs(value) >= 100 ? 2 : 3).format(value);
}

function formatHeroChange(value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '待确认';
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

function buildMarketOverviewEvidenceSnapshotMarkdown(params: {
  activeCategoryLabel: string;
  coverageSummary: Record<CardCoverageKind, number>;
  dataQuality: DataQualitySummary;
  heroAnchors: HeroAnchor[];
  language: 'zh' | 'en';
  temperature: MarketTemperatureResponse;
  briefing: MarketBriefingResponse;
  regimeSynthesis?: MarketRegimeSynthesisHeaderView;
  directionalSummary: MarketDirectionalSummary;
  decisionSemantics?: MarketOverviewDecisionSemanticsView;
  dataState: MarketOverviewDataStateStripView;
  localSnapshotSavedAt?: string;
}): string {
  const {
    activeCategoryLabel,
    coverageSummary,
    dataQuality,
    heroAnchors,
    language,
    temperature,
    briefing,
    regimeSynthesis,
    directionalSummary,
    decisionSemantics,
    dataState,
    localSnapshotSavedAt,
  } = params;
  const heroEvidence = heroAnchors.slice(0, 3).map((anchor) => {
    const displayLabel = anchor.item
      ? resolveMarketOverviewDisplayLabel(anchor.item, language)
      : { primary: anchor.label, secondary: anchor.key };
    return {
      label: displayLabel.primary,
      meta: `${formatHeroValue(anchor.item?.value)} (${formatHeroChange(anchor.item?.changePct)})`,
    };
  });
  const briefingEvidence = briefing.items.slice(0, 2).map((item) => ({
    label: item.title,
    meta: item.message,
  }));
  const synthesisEvidence = [
    ...(regimeSynthesis?.topDrivers || []),
    ...(regimeSynthesis?.counterEvidence || []),
  ].slice(0, 3).map((item) => ({
    label: item.label,
    meta: item.meta,
  }));
  const missingPillars = decisionSemantics?.directionReadiness?.missingPillars.map((pillar) => pillar.reasonCode || pillar.label) ?? [];
  const dataGaps = [
    ...(regimeSynthesis?.dataGaps || []).map((item) => item.meta || item.label),
    ...(decisionSemantics?.dataGaps.map((item) => item.meta || item.label) ?? []),
    ...missingPillars,
    dataState.hasUnavailable ? 'Some evidence is still unavailable.' : '',
    dataState.hasFallback ? 'Some data is delayed or partial.' : '',
  ];
  const nextSteps = [
    ...directionalSummary.watchItems,
    ...(decisionSemantics?.invalidationTriggers.map((item) => item.meta || item.label) ?? []),
    ...(decisionSemantics?.confirmationSignals.map((item) => item.meta || item.label) ?? []),
  ];
  const freshnessLabel = dataState.isRefreshing
    ? 'Refresh in progress'
    : dataState.hasUnavailable
      ? 'Some evidence unavailable'
      : dataState.staleCount > 0 || dataState.hasFallback
        ? 'Delayed or partial data'
        : 'Loaded evidence current';
  const consumerDataQualityLabel = mapConsumerStatusText(dataQuality.status, 'en');

  return buildMarketIntelligenceEvidenceMarkdown({
    title: `Market Intelligence Evidence Snapshot | ${activeCategoryLabel}`,
    locale: 'en',
    generatedAt: new Date(),
    regimeObservation: {
      title: regimeSynthesis?.title || directionalSummary.currentLabel,
      summary: regimeSynthesis?.summary || directionalSummary.currentLabel,
      confidenceLabel: regimeSynthesis
        ? `${regimeSynthesis.confidenceLabel}${regimeSynthesis.confidenceValueText ? ` · ${regimeSynthesis.confidenceValueText}` : ''}`
        : directionalSummary.confidenceLabel,
    },
    evidenceUsed: [
      {
        label: language === 'en' ? 'Market temperature' : '市场温度',
        meta: `${temperature.scores.overall.label} (${formatNumber(temperature.scores.overall.value, 0)})`,
      },
      {
        label: language === 'en' ? 'Data quality' : '数据质量',
        meta: `${consumerDataQualityLabel} · ${activeCategoryLabel}: available ${coverageSummary.real}, partial ${coverageSummary.mixed}, delayed ${coverageSummary.fallback}`,
      },
      ...heroEvidence,
      ...briefingEvidence,
      ...synthesisEvidence,
    ],
    evidenceGaps: dataGaps,
    dataFreshness: {
      label: freshnessLabel,
      asOf: temperature.asOf || briefing.asOf || temperature.updatedAt || briefing.updatedAt || localSnapshotSavedAt,
      notes: [
        dataState.updatedAtLabel ? `Last local snapshot: ${dataState.updatedAtLabel}` : '',
        dataState.needsRefresh ? 'Refresh may be needed before using this as a stronger research read.' : '',
      ],
    },
    researchNextSteps: nextSteps,
  });
}

function formatNumber(value: number | null | undefined, digits = 2): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '-';
  }
  return getCachedNumberFormat(digits).format(value);
}

function formatPercent(value?: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '';
  }
  return `${Math.round(value * 100)}%`;
}

function scoreTone(score: MarketTemperatureScore, pressure = false): string {
  if (pressure) {
    return score.value >= 65 ? 'text-rose-400' : score.value >= 55 ? 'text-amber-300' : 'text-emerald-400';
  }
  return score.value >= 76 ? 'text-amber-200' : score.value >= 61 ? 'text-emerald-400' : score.value <= 45 ? 'text-sky-300' : 'text-white';
}

const MarketOverviewWorkbenchGridFallback: React.FC<{ language: 'zh' | 'en' }> = ({ language }) => {
  const isEnglish = language === 'en';
  const loadingLabel = isEnglish ? 'Loading grid' : '加载总览网格';
  const loadingTitle = isEnglish ? 'Preparing market panels' : '正在准备市场面板';
  const loadingLine = isEnglish ? 'Top-level state stays live while the workbench grid loads.' : '状态和快照已就绪，网格面板正在懒加载。';
  const railTitle = isEnglish ? 'Coverage rail' : '侧栏摘要';
  const railLine = isEnglish ? 'The side rail returns without changing labels or data semantics.' : '侧栏会在网格返回后保持原有标签与数据语义。';

  return (
    <TerminalGrid data-testid="market-overview-grid-loading" data-workbench-split="9:3" aria-busy="true" className="gap-4">
      <section
        data-testid="market-overview-primary-rail-loading"
        data-mobile-order="main"
        className="flex min-w-0 flex-col gap-4 xl:col-span-9"
      >
        <TerminalPanel dense className="min-h-[152px] bg-white/[0.02]">
          <div className="flex h-full min-w-0 flex-col justify-between gap-4">
            <div className="flex min-w-0 items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-[10px] font-bold uppercase tracking-widest text-white/40">
                  {isEnglish ? 'Workbench' : 'Workbench'}
                </p>
                <p className="mt-1 text-sm font-semibold text-white/82">{loadingTitle}</p>
              </div>
              <TerminalChip variant="info" className="shrink-0 px-2 py-1 text-[10px] font-bold uppercase tracking-widest">
                {loadingLabel}
              </TerminalChip>
            </div>
            <p className="max-w-2xl text-xs leading-5 text-white/46">{loadingLine}</p>
            <div className="grid min-w-0 grid-cols-1 gap-3 md:grid-cols-2">
              {Array.from({ length: 2 }).map((_, index) => (
                <div
                  key={index}
                  className="min-h-[72px] rounded-xl border border-white/[0.04] bg-white/[0.03]"
                  aria-hidden="true"
                />
              ))}
            </div>
          </div>
        </TerminalPanel>
        <div className="grid min-w-0 grid-cols-1 gap-4 md:grid-cols-2">
          {Array.from({ length: 2 }).map((_, index) => (
            <TerminalPanel key={index} dense className="min-h-[148px] bg-white/[0.02]">
              <div className="flex h-full min-w-0 flex-col gap-3">
                <div className="h-3 w-24 rounded-full bg-white/[0.08]" aria-hidden="true" />
                <div className="h-6 w-40 rounded-full bg-white/[0.06]" aria-hidden="true" />
                <div className="mt-auto space-y-2">
                  <div className="h-3 w-full rounded-full bg-white/[0.05]" aria-hidden="true" />
                  <div className="h-3 w-5/6 rounded-full bg-white/[0.05]" aria-hidden="true" />
                  <div className="h-3 w-2/3 rounded-full bg-white/[0.05]" aria-hidden="true" />
                </div>
              </div>
            </TerminalPanel>
          ))}
        </div>
      </section>
      <aside
        data-testid="market-overview-side-rail-loading"
        data-mobile-order="rail"
        className="flex min-w-0 flex-col gap-3 xl:col-span-3"
      >
        <TerminalPanel dense className="min-h-[152px] bg-white/[0.02]">
          <div className="flex h-full min-w-0 flex-col gap-3">
            <p className="text-[10px] font-bold uppercase tracking-widest text-white/40">{railTitle}</p>
            <p className="text-sm font-semibold text-white/82">{loadingLabel}</p>
            <p className="text-xs leading-5 text-white/46">{railLine}</p>
            <div className="mt-auto space-y-2">
              <div className="h-3 w-full rounded-full bg-white/[0.05]" aria-hidden="true" />
              <div className="h-3 w-4/5 rounded-full bg-white/[0.05]" aria-hidden="true" />
              <div className="h-3 w-3/5 rounded-full bg-white/[0.05]" aria-hidden="true" />
            </div>
          </div>
        </TerminalPanel>
      </aside>
    </TerminalGrid>
  );
};

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

function regimeConfidenceLabel(label?: string | null, confidence?: number | null): string {
  const normalized = String(label || '').trim().toLowerCase();
  if (normalized === 'high') {
    return '高';
  }
  if (normalized === 'medium') {
    return '中';
  }
  if (normalized === 'low') {
    return '低';
  }
  if (normalized === 'insufficient') {
    return '数据不足';
  }
  if (!normalized) {
    return confidenceLabel(typeof confidence === 'number' ? confidence : undefined);
  }
  return label || confidenceLabel(typeof confidence === 'number' ? confidence : undefined);
}

function regimeLabel(regime?: string | null, language: 'zh' | 'en' = 'zh'): string {
  const labels = language === 'en'
    ? {
      risk_on_liquidity_expansion: 'Risk-on liquidity expansion',
      risk_off_deleveraging: 'Risk-off deleveraging',
      rates_shock_duration_pressure: 'Rates shock / duration pressure',
      dollar_squeeze: 'Dollar squeeze',
      credit_or_funding_stress: 'Credit or funding stress',
      term_premium_or_inflation_scare: 'Term premium / inflation scare',
      goldilocks_soft_landing: 'Goldilocks soft landing',
      nacho_mega_cap_defensive_rotation: 'Mega-cap defensive rotation',
      china_policy_divergence: 'China policy divergence',
      data_insufficient: 'Insufficient data',
    }
    : {
      risk_on_liquidity_expansion: '风险偏好修复 / 流动性扩张',
      risk_off_deleveraging: '去杠杆式风险回避',
      rates_shock_duration_pressure: '利率冲击 / 久期承压',
      dollar_squeeze: '美元走强挤压风险资产',
      credit_or_funding_stress: '信用 / 资金压力',
      term_premium_or_inflation_scare: '期限溢价 / 再通胀担忧',
      goldilocks_soft_landing: '软着陆 / 金发姑娘',
      nacho_mega_cap_defensive_rotation: '大盘权重防御轮动',
      china_policy_divergence: '中国政策分化',
      data_insufficient: '数据不足',
    };
  if (!regime) {
    return language === 'en' ? 'No synthesis conclusion' : '综合结论待返回';
  }
  return labels[regime as keyof typeof labels] || (language === 'en' ? 'Market state pending' : '市场状态待确认');
}

function regimePostureLabel(posture?: string | null, language: 'zh' | 'en' = 'zh'): string {
  const labels = language === 'en'
    ? {
      risk_supportive: 'Risk-supportive watch',
      risk_defensive: 'Risk-defensive watch',
      mixed_or_transition: 'Transition watch',
      data_insufficient: 'Evidence insufficient',
    }
    : {
      risk_supportive: '风险支持观察',
      risk_defensive: '风险防御观察',
      mixed_or_transition: '过渡观察',
      data_insufficient: '证据不足',
    };
  if (!posture) {
    return language === 'en' ? 'Transition watch' : '过渡观察';
  }
  return labels[posture as keyof typeof labels] || (language === 'en' ? 'Transition watch' : '过渡观察');
}

function regimeResearchFreshnessLabel(freshness?: string | null, language: 'zh' | 'en' = 'zh'): string {
  const normalized = String(freshness || '').trim().toLowerCase();
  if (!normalized) {
    return language === 'en' ? 'Delayed available' : '延迟可用';
  }
  if (normalized === 'live' || normalized === 'fresh') {
    return language === 'en' ? 'Available' : '可用';
  }
  if (normalized === 'cached' || normalized === 'delayed' || normalized === 'partial') {
    return language === 'en' ? 'Delayed available' : '延迟可用';
  }
  if (normalized === 'stale') {
    return language === 'en' ? 'Stale' : '过期';
  }
  if (normalized === 'fallback' || normalized === 'mock' || normalized === 'synthetic' || normalized === 'unavailable' || normalized === 'error') {
    return language === 'en' ? 'Unavailable' : '暂不可用';
  }
  return language === 'en' ? 'Delayed available' : '延迟可用';
}

function regimeResearchFamilyStateLabel(state?: string | null, language: 'zh' | 'en' = 'zh'): string {
  const normalized = String(state || '').trim().toLowerCase();
  const labels = language === 'en'
    ? {
      supported: 'Supported',
      missing: 'Missing',
      discounted: 'Discounted',
    }
    : {
      supported: '已支持',
      missing: '待补',
      discounted: '已折价',
    };
  if (!normalized) {
    return language === 'en' ? 'Missing' : '待补';
  }
  return labels[normalized as keyof typeof labels] || (language === 'en' ? 'Missing' : '待补');
}

function regimeResearchFamilyStateVariant(state?: string | null): 'neutral' | 'success' | 'caution' | 'danger' | 'info' {
  const normalized = String(state || '').trim().toLowerCase();
  if (normalized === 'supported') {
    return 'success';
  }
  if (normalized === 'discounted') {
    return 'info';
  }
  return 'caution';
}

function regimeResearchNextStepLabel(key?: string | null, language: 'zh' | 'en' = 'zh'): string {
  const normalized = String(key || '').trim().toLowerCase();
  const labels = language === 'en'
    ? {
      fill_missing_evidence: 'Re-check missing evidence',
      review_contradictions: 'Review contradictions',
      respect_confidence_cap: 'Respect confidence cap',
      monitor_persistence: 'Monitor persistence',
    }
    : {
      fill_missing_evidence: '补齐缺失证据',
      review_contradictions: '复核反证',
      respect_confidence_cap: '保持置信上限',
      monitor_persistence: '继续观察',
    };
  if (!normalized) {
    return language === 'en' ? 'Continue observing' : '继续观察';
  }
  return labels[normalized as keyof typeof labels] || (language === 'en' ? 'Continue observing' : '继续观察');
}

function regimePillarLabel(pillar?: string | null, language: 'zh' | 'en' = 'zh'): string {
  const labels = language === 'en'
    ? {
      risk_appetite: 'Risk appetite',
      rates_pressure: 'Rates pressure',
      dollar_pressure: 'Dollar pressure',
      volatility_stress: 'Volatility stress',
      liquidity_impulse: 'Liquidity impulse',
      crypto_risk_beta: 'Crypto risk beta',
      breadth_health: 'Breadth health',
      china_risk_appetite: 'China risk appetite',
      rotation_leadership: 'Rotation quality',
    }
    : {
      risk_appetite: '风险偏好',
      rates_pressure: '利率压力',
      dollar_pressure: '美元压力',
      volatility_stress: '波动压力',
      liquidity_impulse: '流动性脉冲',
      crypto_risk_beta: '加密风险偏好',
      breadth_health: '市场宽度',
      china_risk_appetite: '中国风险偏好',
      rotation_leadership: '轮动质量',
    };
  if (!pillar) {
    return language === 'en' ? 'Coverage' : '覆盖';
  }
  return labels[pillar as keyof typeof labels] || (language === 'en' ? 'Coverage' : '覆盖');
}

function regimeGapReasonLabel(reason?: string | null, language: 'zh' | 'en' = 'zh'): string {
  const labels = language === 'en'
    ? {
      unknown_pillar: 'Coverage pending',
      missing_direction_or_magnitude: 'Direction pending',
      source_tier_discount: 'Data boundary pending',
      trust_discount: 'Data boundary pending',
      freshness_discount: 'DELAYED',
      observation_only_discount: 'OBSERVATION_ONLY',
      unscorable_quality: 'INSUFFICIENT',
      missing_scoring_evidence: 'INSUFFICIENT',
      conflicts_with_primary_regime: 'Counter signal',
      provider_unavailable: 'UNAVAILABLE',
      unavailable: 'UNAVAILABLE',
    }
    : {
      unknown_pillar: '覆盖待确认',
      missing_direction_or_magnitude: '方向待确认',
      source_tier_discount: '数据边界待确认',
      trust_discount: '数据边界待确认',
      freshness_discount: '延迟可用',
      observation_only_discount: '仅供观察',
      unscorable_quality: '证据不足',
      missing_scoring_evidence: '证据不足',
      conflicts_with_primary_regime: '反向信号',
      provider_unavailable: '暂不可用',
      unavailable: '暂不可用',
    };
  if (!reason) {
    return language === 'en' ? 'Data boundary pending' : '数据边界待确认';
  }
  return labels[reason as keyof typeof labels] || (language === 'en' ? 'Data boundary pending' : '数据边界待确认');
}

function synthesisEvidenceMeta(
  item: MarketRegimeSynthesisEvidenceItem,
  kind: 'driver' | 'counter' | 'gap',
  language: 'zh' | 'en',
): string {
  const pillar = regimePillarLabel(item.pillar, language);
  if (kind === 'driver') {
    const direction = item.direction === 'positive'
      ? (language === 'en' ? 'supports' : '顺势')
      : item.direction === 'negative'
        ? (language === 'en' ? 'offsets' : '逆势')
        : (language === 'en' ? 'signal' : '信号');
    const discount = item.discountReasons?.[0]
      ? regimeGapReasonLabel(item.discountReasons[0], language)
      : '';
    const signal = typeof item.signal === 'number'
      ? `${language === 'en' ? 'signal' : '信号'} ${item.signal > 0 ? '+' : ''}${item.signal.toFixed(2)}`
      : '';
    return [pillar, direction, signal, discount].filter(Boolean).join(' · ');
  }
  if (kind === 'counter') {
    const signal = typeof item.signal === 'number'
      ? `${language === 'en' ? 'signal' : '信号'} ${item.signal > 0 ? '+' : ''}${item.signal.toFixed(2)}`
      : '';
    return [
      pillar,
      regimeGapReasonLabel(item.reason || 'conflicts_with_primary_regime', language),
      signal,
    ].filter(Boolean).join(' · ');
  }
  return [
    pillar,
    regimeGapReasonLabel(item.reason || item.degradationReason, language),
  ].filter(Boolean).join(' · ');
}

function buildRegimeEvidenceView(
  items: MarketRegimeSynthesisEvidenceItem[],
  kind: 'driver' | 'counter' | 'gap',
  limit: number,
  language: 'zh' | 'en',
): MarketRegimeSynthesisEvidenceView[] {
  const displayLabelForItem = (item: MarketRegimeSynthesisEvidenceItem): string => {
    const symbol = item.key.includes(':') ? item.key.split(':').pop() || item.key : item.key;
    const display = resolveMarketOverviewDisplayLabel({
      symbol,
      label: item.label || symbol,
    } as MarketOverviewItem, language);
    return display.primary || item.label || symbol;
  };

  return items.slice(0, limit).map((item) => ({
    key: item.key,
    label: displayLabelForItem(item),
    meta: synthesisEvidenceMeta(item, kind, language),
  }));
}

function buildMarketRegimeSynthesisView(
  synthesis: MarketRegimeSynthesis | undefined,
  decisionReliable: boolean,
  language: 'zh' | 'en',
): MarketRegimeSynthesisHeaderView | undefined {
  if (!synthesis) {
    return undefined;
  }

  const confidenceValueText = formatPercent(synthesis.confidence);
  const confidenceCapValueText = formatPercent(synthesis.confidenceCap?.value);
  const lowConfidence = (
    synthesis.primaryRegime === 'data_insufficient'
    || synthesis.confidenceLabel === 'insufficient'
    || (typeof synthesis.confidence === 'number' && synthesis.confidence < 0.45)
    || !decisionReliable
  );
  const evidenceQuality = synthesis.evidenceQuality || {};
  const scoringEvidenceCount = typeof evidenceQuality.scoringEvidenceCount === 'number'
    ? evidenceQuality.scoringEvidenceCount
    : (Array.isArray(synthesis.topDrivers) ? synthesis.topDrivers.length : 0);
  const scoringPillarCount = typeof evidenceQuality.scoringPillarCount === 'number'
    ? evidenceQuality.scoringPillarCount
    : undefined;
  const discountedEvidenceCount = typeof evidenceQuality.discountedEvidenceCount === 'number'
    ? evidenceQuality.discountedEvidenceCount
    : undefined;
  const dataGapCount = typeof evidenceQuality.dataGapCount === 'number'
    ? evidenceQuality.dataGapCount
    : (Array.isArray(synthesis.dataGaps) ? synthesis.dataGaps.length : 0);
  const topDrivers = Array.isArray(synthesis.topDrivers) ? synthesis.topDrivers : [];
  const counterEvidence = Array.isArray(synthesis.counterEvidence) ? synthesis.counterEvidence : [];
  const dataGaps = Array.isArray(synthesis.dataGaps) ? synthesis.dataGaps : [];
  const evidenceFamilies = Array.isArray(synthesis.evidenceFamilies) ? synthesis.evidenceFamilies : [];
  const supportiveEvidence = Array.isArray(synthesis.supportiveEvidence) ? synthesis.supportiveEvidence : [];
  const contradictoryEvidence = Array.isArray(synthesis.contradictoryEvidence) ? synthesis.contradictoryEvidence : [];
  const missingEvidence = Array.isArray(synthesis.missingEvidence) ? synthesis.missingEvidence : [];
  const researchNextSteps = Array.isArray(synthesis.researchNextSteps) ? synthesis.researchNextSteps : [];

  return {
    state: lowConfidence ? 'insufficient' : 'ready',
    title: lowConfidence && synthesis.primaryRegime !== 'data_insufficient'
      ? `${regimeLabel(synthesis.primaryRegime, language)}${language === 'en' ? ' (low confidence)' : '（待确认）'}`
      : regimeLabel(synthesis.primaryRegime, language),
    summary: lowConfidence
      ? (language === 'en'
        ? 'Coverage or confidence is below threshold. Show explicit evidence, counter signals, and gaps without promoting a strong market-state call.'
        : '当前覆盖或置信度不足，只展示可验证驱动、反证和数据缺口，不升级为强结论。')
      : (language === 'en'
        ? `Top drivers ${Math.min(topDrivers.length, 3)} · counter evidence ${Math.min(counterEvidence.length, 3)} · data gaps ${Math.min(dataGapCount, 3)}`
        : `主要驱动 ${Math.min(topDrivers.length, 3)} 项 · 反证 ${Math.min(counterEvidence.length, 3)} 项 · 数据缺口 ${Math.min(dataGapCount, 3)} 项`),
    stateChipLabel: lowConfidence
      ? (synthesis.primaryRegime === 'data_insufficient'
        ? (language === 'en' ? 'INSUFFICIENT' : '证据不足')
        : (language === 'en' ? 'OBSERVATION_ONLY' : '仅供观察'))
      : (language === 'en' ? 'AVAILABLE' : '可用'),
    stateChipVariant: lowConfidence ? 'caution' : 'success',
    primaryRegimeCode: synthesis.primaryRegime,
    primaryRegimeLabel: lowConfidence
      ? (language === 'en' ? 'INSUFFICIENT' : '证据不足')
      : (language === 'en' ? 'AVAILABLE' : '可用'),
    confidenceLabel: regimeConfidenceLabel(synthesis.confidenceLabel, synthesis.confidence),
    confidenceValueText,
    qualityLine: [
      `${language === 'en' ? 'Evidence' : '证据'} ${scoringEvidenceCount}`,
      scoringPillarCount != null ? `${language === 'en' ? 'Pillars' : '支柱'} ${scoringPillarCount}/9` : '',
      discountedEvidenceCount != null ? `${language === 'en' ? 'Discounted' : '折价'} ${discountedEvidenceCount}` : '',
    ].filter(Boolean).join(' · '),
    topDrivers: buildRegimeEvidenceView(topDrivers, 'driver', 3, language),
    counterEvidence: buildRegimeEvidenceView(counterEvidence, 'counter', 3, language),
    dataGaps: buildRegimeEvidenceView(dataGaps, 'gap', 3, language),
    postureLabel: regimePostureLabel(synthesis.regimePosture, language),
    freshnessLabel: regimeResearchFreshnessLabel(synthesis.freshness, language),
    confidenceCapLabel: regimeConfidenceLabel(synthesis.confidenceCap?.label, synthesis.confidenceCap?.value),
    confidenceCapValueText,
    evidenceFamilies: evidenceFamilies.slice(0, 5).map((family) => ({
      key: family.key,
      label: marketOverviewConsumerSemanticsText(family.label, language === 'en' ? 'Evidence family' : '证据家族'),
      stateLabel: regimeResearchFamilyStateLabel(family.state, language),
      stateVariant: regimeResearchFamilyStateVariant(family.state),
      summary: [
        `${language === 'en' ? 'Evidence' : '证据'} ${family.evidenceCount}`,
        family.supportiveCount ? `${language === 'en' ? 'Support' : '支持'} ${family.supportiveCount}` : '',
        family.contradictoryCount ? `${language === 'en' ? 'Counter' : '反证'} ${family.contradictoryCount}` : '',
        family.missingCount ? `${language === 'en' ? 'Missing' : '待补'} ${family.missingCount}` : '',
      ].filter(Boolean).join(' · '),
      freshnessLabel: regimeResearchFreshnessLabel(family.freshness, language),
    })),
    supportiveEvidence: buildRegimeEvidenceView(supportiveEvidence, 'driver', 3, language),
    contradictoryEvidence: buildRegimeEvidenceView(contradictoryEvidence, 'counter', 3, language),
    missingEvidence: buildRegimeEvidenceView(missingEvidence, 'gap', 3, language),
    researchNextSteps: researchNextSteps.slice(0, 3).map((step) => ({
      key: step.key,
      label: regimeResearchNextStepLabel(step.key, language),
      meta: marketOverviewConsumerSemanticsText(step.detail, language === 'en' ? 'Continue evidence review.' : '继续复核证据。'),
    })),
    notInvestmentAdvice: Boolean(synthesis.notInvestmentAdvice),
  };
}

function buildMarketOverviewRegimeSummaryView(
  summary: MarketTemperatureResponse['regimeSummary'],
  language: 'zh' | 'en',
): MarketOverviewRegimeSummaryView | undefined {
  if (!summary?.title || !summary.label) {
    return undefined;
  }

  const toLineItems = (items: Array<{ key: string; label: string; detail: string }>): MarketOverviewDecisionSemanticsLineView[] => (
    items.map((item, index) => ({
      key: item.key,
      label: marketOverviewConsumerSemanticsText(item.label, `${language === 'en' ? 'Observation' : '观察'} ${index + 1}`),
      meta: marketOverviewConsumerSemanticsText(item.detail),
    }))
  );

  return {
    title: marketOverviewConsumerSemanticsText(summary.title, language === 'en' ? 'Market state pending' : '市场状态待确认'),
    label: marketOverviewConsumerSemanticsText(summary.label, language === 'en' ? 'OBSERVATION_ONLY' : '仅供观察'),
    confidenceLabel: language === 'en' ? 'Confidence' : '置信度',
    confidenceValueText: [
      regimeConfidenceLabel(summary.confidence?.label, summary.confidence?.value),
      formatPercent(summary.confidence?.value),
    ].filter(Boolean).join(' · '),
    explanation: marketOverviewConsumerSemanticsText(summary.explanation, language === 'en' ? 'Data boundary pending confirmation.' : '数据边界待确认。'),
    drivers: toLineItems(summary.drivers),
    blockers: toLineItems(summary.blockers),
    contradictions: toLineItems(summary.contradictions),
    nextWatchItems: toLineItems(summary.nextWatchItems),
  };
}

function marketDecisionSemanticsText(value: unknown): string {
  return typeof value === 'string' || typeof value === 'number' ? String(value) : '';
}

const MARKET_OVERVIEW_CONSUMER_UNSAFE_PATTERN = /\b(?:REAL|MIXED|FALLBACK|REGIME|ALTERNATIVE\.?ME|YFINANCE|CBOE|BINANCE|Yahoo Finance|Binance Futures|provider|sourceTier|sourceLabel|reasonCode|diagnosticOnly|scoreContributionAllowed|sourceAuthorityAllowed|authorityGrant|raw|debug|backend|cache|schema|synthetic|mock|proxy|fallback)\b|market_regime_synthesis|Conflicts With Primary Regime|ETF flow proxy|Institutional pressure proxy|Industry breadth proxy/i;
const MARKET_OVERVIEW_INTERNAL_TOKEN_PATTERN = /^[a-z0-9]+(?:_[a-z0-9]+)+$/i;

function marketOverviewConsumerSemanticsText(value: unknown, fallback = ''): string {
  const text = marketDecisionSemanticsText(value).trim();
  if (!text) {
    return fallback;
  }
  if (MARKET_OVERVIEW_INTERNAL_TOKEN_PATTERN.test(text)) {
    const reasonLabel = marketIntelligenceReasonLabel(text, 'zh');
    return reasonLabel === '数据边界待确认' ? fallback : reasonLabel;
  }
  const projected = text
    .replace(/market_regime_synthesis/gi, '市场状态')
    .replace(/Conflicts With Primary Regime/gi, '反向信号')
    .replace(/ETF flow proxy/gi, 'ETF 资金流指标')
    .replace(/Institutional pressure proxy/gi, '机构压力指标')
    .replace(/Industry breadth proxy/gi, '行业广度指标')
    .replace(/\bREAL\b/g, 'AVAILABLE')
    .replace(/\bMIXED\b/g, 'PARTIAL')
    .replace(/\bFALLBACK\b/g, 'DELAYED')
    .replace(/\breal\b/g, 'available')
    .replace(/\bmixed\b/g, 'partial')
    .replace(/\bfallback\b/g, 'delayed')
    .replace(/\bproxy\b/gi, 'partial data')
    .replace(/\bprovider\b/gi, 'data')
    .trim();
  if (!projected || MARKET_OVERVIEW_CONSUMER_UNSAFE_PATTERN.test(projected)) {
    return fallback;
  }
  return projected;
}

function marketDecisionPostureLabel(posture: string, language: 'zh' | 'en'): string {
  const labels = language === 'en'
    ? {
      offensive: 'Risk appetite watch',
      defensive: 'Risk-control watch',
      neutral: 'Balanced watch',
      data_insufficient: 'Insufficient evidence',
    }
    : {
      offensive: '风险偏好观察',
      defensive: '风险控制观察',
      neutral: '均衡观察',
      data_insufficient: '证据不足',
    };
  return labels[posture as keyof typeof labels] || posture;
}

function marketDecisionExposureLabel(exposureBias: string, language: 'zh' | 'en'): string {
  const labels = language === 'en'
    ? {
      risk_on_watch: 'Risk-on watch',
      risk_control_watch: 'Risk-control watch',
      balanced_watch: 'Balanced watch',
      no_bias_data_insufficient: 'No bias',
    }
    : {
      risk_on_watch: '风险偏好观察',
      risk_control_watch: '风险控制观察',
      balanced_watch: '均衡观察',
      no_bias_data_insufficient: '无观察偏向',
    };
  return labels[exposureBias as keyof typeof labels] || exposureBias;
}

function marketDecisionBoundaryLabel(claim: string, language: 'zh' | 'en'): string {
  const labels = language === 'en'
    ? {
      observational_posture_watch: 'Posture boundary',
      style_tilt_watch: 'Style boundary',
      direct_trade_action: 'Execution boundary',
      position_size_guidance: 'Sizing boundary',
      personalized_suitability: 'Suitability boundary',
    }
    : {
      observational_posture_watch: '姿态边界',
      style_tilt_watch: '风格边界',
      direct_trade_action: '交易动作边界',
      position_size_guidance: '执行尺度边界',
      personalized_suitability: '适配边界',
    };
  return labels[claim as keyof typeof labels] || claim;
}

function marketDecisionSemanticsLine(
  item: MarketDecisionSemanticsItem,
  index: number,
  fallbackPrefix: string,
): MarketOverviewDecisionSemanticsLineView {
  const rawLabel = (
    marketDecisionSemanticsText(item.label)
    || marketDecisionSemanticsText(item.detail)
    || marketDecisionSemanticsText(item.signal)
    || marketDecisionSemanticsText(item.trigger)
    || marketDecisionSemanticsText(item.tilt)
    || marketDecisionSemanticsText(item.key)
    || `${fallbackPrefix} ${index + 1}`
  );
  const label = marketOverviewConsumerSemanticsText(rawLabel, `${fallbackPrefix} ${index + 1}`);
  const meta = [
    item.reason || item.reasonCode ? marketIntelligenceReasonLabel(marketDecisionSemanticsText(item.reason || item.reasonCode)) : '',
    marketOverviewConsumerSemanticsText(item.surface),
    marketDecisionSemanticsText(item.label) ? marketOverviewConsumerSemanticsText(item.detail) : '',
  ].filter(Boolean).join(' · ');
  return {
    key: `${fallbackPrefix}-${marketDecisionSemanticsText(item.key) || label}-${index}`,
    label,
    meta,
  };
}

function marketDecisionBoundaryLine(
  item: MarketDecisionSemanticsClaimBoundary,
  index: number,
  language: 'zh' | 'en',
): MarketOverviewDecisionSemanticsBoundaryView {
  const claim = marketDecisionSemanticsText(item.claim) || `boundary_${index + 1}`;
  return {
    key: `${claim}-${index}`,
    label: marketDecisionBoundaryLabel(claim, language),
    allowed: item.allowed === true,
    reasonCode: marketDecisionSemanticsText(item.reasonCode),
  };
}

function marketDirectionReadinessStatusLabel(status: string, language: 'zh' | 'en'): string {
  const labels = language === 'en'
    ? {
      direction_ready: 'Direction-ready',
      partial_context_only: 'Context-only',
      data_insufficient: 'Data insufficient',
    }
    : {
      direction_ready: '方向可用',
      partial_context_only: '仅作上下文',
      data_insufficient: '数据不足',
    };
  return labels[status as keyof typeof labels] || status;
}

function marketDirectionReadinessStatusVariant(status: string): MarketOverviewDirectionReadinessView['statusVariant'] {
  if (status === 'direction_ready') {
    return 'success';
  }
  if (status === 'partial_context_only') {
    return 'caution';
  }
  if (status === 'data_insufficient') {
    return 'danger';
  }
  return 'neutral';
}

function marketDirectionReadinessPillarLine(
  item: MarketDirectionReadinessPillar,
  index: number,
  fallbackPrefix: string,
): MarketOverviewDirectionReadinessView['scoreGradePillars'][number] {
  const pillar = marketDecisionSemanticsText(item.pillar);
  const label = marketDecisionSemanticsText(item.label) || pillar || `${fallbackPrefix} ${index + 1}`;
  return {
    key: `${fallbackPrefix}-${pillar || label}-${index}`,
    label,
    reasonCode: marketDecisionSemanticsText(item.reasonCode),
  };
}

function buildMarketDirectionReadinessView(
  readiness: MarketDirectionReadiness | undefined,
  language: 'zh' | 'en',
): MarketOverviewDirectionReadinessView | undefined {
  if (!readiness) {
    return undefined;
  }
  return {
    status: readiness.status,
    statusLabel: marketDirectionReadinessStatusLabel(readiness.status, language),
    statusVariant: marketDirectionReadinessStatusVariant(readiness.status),
    confidenceLabel: regimeConfidenceLabel(readiness.confidenceLabel),
    scoreGradeCount: readiness.scoreGradePillars.count,
    observationOnlyCount: readiness.observationOnlyPillars.count,
    missingCount: readiness.missingPillars.count,
    scoreGradePillars: readiness.scoreGradePillars.items.map((item, index) => marketDirectionReadinessPillarLine(item, index, 'score')),
    observationOnlyPillars: readiness.observationOnlyPillars.items.map((item, index) => marketDirectionReadinessPillarLine(item, index, 'observation')),
    missingPillars: readiness.missingPillars.items.map((item, index) => marketDirectionReadinessPillarLine(item, index, 'missing')),
    blockingReasons: readiness.blockingReasons,
    notInvestmentAdvice: readiness.notInvestmentAdvice,
  };
}

function buildMarketDecisionSemanticsView(
  semantics: MarketDecisionSemantics | undefined,
  language: 'zh' | 'en',
): MarketOverviewDecisionSemanticsView | undefined {
  if (!semantics) {
    return undefined;
  }
  const confidenceValue = semantics.postureConfidence.value;
  const confidenceLabelText = regimeConfidenceLabel(
    semantics.postureConfidence.label,
    typeof confidenceValue === 'number' ? confidenceValue / 100 : undefined,
  );
  return {
    postureLabel: marketDecisionPostureLabel(semantics.posture, language),
    confidenceLabel: confidenceLabelText,
    confidenceValueText: typeof confidenceValue === 'number' ? String(confidenceValue) : '',
    exposureBiasLabel: marketDecisionExposureLabel(semantics.exposureBias, language),
    insufficient: semantics.posture === 'data_insufficient' || semantics.postureConfidence.label === 'insufficient',
    capReasons: semantics.postureConfidence.capReasons,
    styleTilts: semantics.styleTilts.map((item, index) => marketDecisionSemanticsLine(item, index, 'style')),
    confirmationSignals: semantics.confirmationSignals.map((item, index) => marketDecisionSemanticsLine(item, index, 'confirm')),
    invalidationTriggers: semantics.invalidationTriggers.map((item, index) => marketDecisionSemanticsLine(item, index, 'invalidate')),
    counterEvidence: semantics.counterEvidence.map((item, index) => marketDecisionSemanticsLine(item, index, 'counter')),
    dataGaps: semantics.dataGaps.map((item, index) => marketDecisionSemanticsLine(item, index, 'gap')),
    directionReadiness: buildMarketDirectionReadinessView(semantics.directionReadiness, language),
    claimBoundaries: semantics.claimBoundaries.map((item, index) => marketDecisionBoundaryLine(item, index, language)),
    notInvestmentAdvice: semantics.notInvestmentAdvice,
  };
}

function isTemperatureReliable(data: MarketTemperatureResponse): boolean {
  return Boolean(
    data.temperatureAvailable !== false
    && data.conclusionAllowed !== false
    && data.isReliable !== false
    && (data.confidence == null || data.confidence >= 0.45)
    && (data.reliableInputCount == null || data.reliableInputCount >= 3),
  );
}

function hasInsufficientReliableInputs(data: MarketTemperatureResponse): boolean {
  const requiredReliableInputCount = data.requiredReliableInputCount ?? 3;
  const requiredReliablePanelCount = data.requiredReliablePanelCount ?? 3;
  const reliableInputShortfall = data.reliableInputCount != null && data.reliableInputCount < requiredReliableInputCount;
  const reliablePanelShortfall = data.reliablePanelCount != null && data.reliablePanelCount < requiredReliablePanelCount;

  return Boolean(
    data.insufficientReliableInputs
    || data.disabledReason === 'insufficient_reliable_inputs'
    || data.unavailableReason === 'insufficient_reliable_inputs'
    || reliableInputShortfall
    || reliablePanelShortfall
  );
}

function temperatureDisabledStateLabel(data: MarketTemperatureResponse): string {
  if (data.temperatureAvailable === false || data.conclusionAllowed === false || data.isReliable === false) {
    if (hasInsufficientReliableInputs(data)) {
      return '可靠输入不足';
    }
    return '暂不判定';
  }
  return data.scores.overall.label || '数据不足';
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
    if (freshness && ['live', 'delayed', 'cached', 'stale', 'fallback', 'mock', 'error', 'unavailable'].includes(freshness)) {
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
    unavailable: 0,
  };
  collectFreshnessValues(panels).forEach((freshness) => {
    counts[freshness] += 1;
  });
  const status = counts.error + counts.unavailable > 0
    ? '部分数据暂不可用'
    : counts.stale > 0
      ? '存在过期数据'
      : counts.fallback + counts.mock > 0
        ? '延迟可用'
        : '可用';
  return {
    status,
    counts,
    hasConcern: counts.fallback + counts.mock + counts.stale + counts.error + counts.unavailable > 0,
  };
}

function summarizeTopLevelDataStatus(params: {
  activeCategory: MarketOverviewTab;
  panels: PanelState;
  coverageSummary: Record<CardCoverageKind, number>;
  loading: boolean;
  refreshingPanel: PanelKey | null;
}): TopLevelDataStatus {
  const {
    activeCategory,
    panels,
    coverageSummary,
    loading,
    refreshingPanel,
  } = params;
  const categoryStatuses = CATEGORY_CARDS[activeCategory].map((cardKey) => resolveProviderStatus(getCardMeta(panels, cardKey) as Partial<MarketDataMeta>));
  const usableCount = coverageSummary.real + coverageSummary.mixed;
  const hasRefreshing = loading || refreshingPanel !== null || categoryStatuses.some((status) => status === 'refreshing');
  const hasMissingPanels = coverageSummary.fallback > 0 || categoryStatuses.some((status) => ['partial', 'unavailable', 'error'].includes(status));

  if (usableCount === 0) {
    return hasRefreshing
      ? {
        kind: 'refreshing',
        headline: '正在更新',
        hasUsableData: false,
        hasMissingPanels: true,
      }
      : {
        kind: 'fallbackOnlyUnavailable',
        headline: '部分数据暂不可用',
        hasUsableData: false,
        hasMissingPanels: true,
      };
  }

  if (coverageSummary.real > 0 && coverageSummary.mixed > 0) {
    return {
      kind: 'mixedDataAvailable',
      headline: '数据可用：部分信号待确认',
      detail: hasMissingPanels ? '部分数据暂不可用' : undefined,
      hasUsableData: true,
      hasMissingPanels,
    };
  }

  if (coverageSummary.mixed > 0) {
    return {
      kind: 'proxyPartialAvailable',
      headline: '数据可用：部分信号待确认',
      detail: hasMissingPanels ? '部分数据暂不可用' : undefined,
      hasUsableData: true,
      hasMissingPanels,
    };
  }

  return {
    kind: 'delayedAvailable',
    headline: '数据可用：已使用最近一次可用数据',
    detail: hasMissingPanels ? '部分数据暂不可用' : undefined,
    hasUsableData: true,
    hasMissingPanels,
  };
}

function formatTopLevelDataStatus(status: TopLevelDataStatus): string {
  return status.detail ? `${status.headline} · ${status.detail}` : status.headline;
}

function explainTopLevelDataStatus(status: TopLevelDataStatus): string {
  switch (status.kind) {
    case 'refreshing':
      return '数据更新中，稍后将自动刷新。';
    case 'fallbackOnlyUnavailable':
      return '部分数据暂不可用，当前评分已暂停。';
    case 'mixedDataAvailable':
      return '当前信号置信度较低，仅供观察。';
    case 'proxyPartialAvailable':
      return '当前信号置信度较低，仅供观察。';
    case 'delayedAvailable':
      return '已使用最近一次可用数据。';
    default:
      return formatTopLevelDataStatus(status);
  }
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
  topLevelDataStatus: TopLevelDataStatus;
}): { text: string; chips: MarketOverviewDecisionChipView[] } {
  const { activeCategory, panels, dataQuality, topLevelDataStatus } = params;
  const temperature = panels.temperature;
  const reliable = isTemperatureReliable(temperature);

  const vix = findPanelItem(panels.volatility, ['VIX']);
  const btc = findPanelItem(panels.crypto, ['BTC']);
  const spx = findPanelItem(panels.indices, ['SPX']);
  const csi = findPanelItem(panels.cnIndices, ['CSI300', '000300.SH']) || findPanelItem(panels.indices, ['CSI300']);
  const us10y = findPanelItem(panels.rates, ['US10Y']) || findPanelItem(panels.macro, ['US10Y']);
  const dxy = findPanelItem(panels.fxCommodities, ['DXY']) || findPanelItem(panels.macro, ['DXY']);
  const hsi = findPanelItem(panels.cnIndices, ['HSI']);

  const fallbackRiskLabel = topLevelDataStatus.kind === 'refreshing'
    ? '刷新中'
    : topLevelDataStatus.hasUsableData
      ? '观察中'
      : '数据不足';
  const riskLabel = reliable ? scoreStateLabel(temperature.scores.overall) : fallbackRiskLabel;
  const disabledLabel = temperatureDisabledStateLabel(temperature);
  const liquidityLabel = reliable ? scoreStateLabel(temperature.scores.liquidity) : topLevelDataStatus.hasUsableData ? '部分可用' : disabledLabel;
  const breadthLabel = reliable ? scoreStateLabel(temperature.scores.cnMoneyEffect) : topLevelDataStatus.hasUsableData ? '部分可用' : disabledLabel;
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
      text: explainTopLevelDataStatus(topLevelDataStatus),
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

  const qualityHint = dataQuality.hasConcern ? ` · ${mapConsumerStatusText(dataQuality.status, 'zh')}` : '';
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
  if (meta?.isUnavailable || meta?.source === 'unavailable' || meta?.freshness === 'unavailable') {
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

const MarketOverviewSection: React.FC<{
  rowId: string;
  meta: MarketOverviewSectionMeta;
  children: React.ReactNode;
}> = ({ rowId, meta, children }) => (
  <section data-testid={`market-overview-section-${rowId}`} className="flex min-w-0 flex-col gap-3">
    <div className="flex min-w-0 flex-col gap-1.5">
      <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-white/36">{meta.eyebrow}</p>
      <div className="flex min-w-0 flex-col gap-1 lg:flex-row lg:items-end lg:justify-between">
        <h2 className="text-base font-semibold text-white/86">{meta.title}</h2>
        <p className="max-w-3xl text-[11px] leading-5 text-white/44">{meta.detail}</p>
      </div>
    </div>
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
        {metrics.length > 6 ? <p className="text-[10px] text-white/38">其余 {metrics.length - 6} 项已折叠</p> : null}
        {loading ? <div className="mt-3 rounded-lg border border-white/8 bg-white/[0.03] p-3 text-sm text-white/60">{t('marketOverviewPage.loading')}</div> : null}
        <MarketOverviewPanelFooter panel={panel} sourceLabel={data.sourceLabel || (fallbackOnly ? '延迟可用' : '可用')} />
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
  notice?: string;
  insightStrip?: React.ReactNode;
  refreshing?: boolean;
  onRefresh?: () => void;
}> = ({
  moduleId,
  title,
  eyebrow,
  description,
  panel,
  sourceLabel,
  notice,
  insightStrip,
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
            {notice ? <p className="mt-1 truncate text-[10px] leading-4 text-white/38">{notice}</p> : null}
          </div>
          {onRefresh ? (
            <MarketOverviewRefreshButton
              label={t('marketOverviewPage.refreshCard', { title })}
              refreshing={refreshing}
              onRefresh={onRefresh}
            />
          ) : null}
        </div>
        {insightStrip}
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
          <p className="text-[10px] text-white/38">其余 {hiddenItemCount} 项已折叠</p>
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
  showAdminDiagnostics?: boolean;
  onRefreshPanel: (panelKey: PanelKey) => void;
};

function useMarketOverviewWorkbenchModel({
  panels,
  loading,
  localSnapshotSavedAt,
  refreshErrorCount,
  refreshingPanel,
  cryptoRealtimeStatus,
  isCnShortSentimentBootstrapping,
  onRefreshPanel,
}: Omit<MarketOverviewWorkbenchProps, 'heading' | 'showAdminDiagnostics'>) {
  const { language, t } = useI18n();
  const [activeCategory, setActiveCategory] = useState<MarketOverviewTab>('all');
  const [exportSummaryFeedback, setExportSummaryFeedback] = useState<EvidenceSnapshotCopyState>('idle');

  const categoryTabs: MarketOverviewCategoryTabView[] = [
    { key: 'all', label: t('marketOverviewPage.categories.all') },
    { key: 'us', label: t('marketOverviewPage.categories.us') },
    { key: 'cn', label: t('marketOverviewPage.categories.cn') },
    { key: 'global', label: t('marketOverviewPage.categories.macro') },
    { key: 'crypto', label: t('marketOverviewPage.categories.crypto') },
  ];
  const handleCategoryChange = (tab: MarketOverviewTab) => {
    if (tab !== activeCategory) {
      setExportSummaryFeedback('idle');
    }
    setActiveCategory(tab);
  };

  const activeTabConfig = MARKET_OVERVIEW_TAB_CONFIG[activeCategory];
  const heroAnchors = buildHeroAnchors(panels, activeTabConfig.pulse);
  const dataQuality = summarizeDataQuality(panels);
  const coverageSummary = summarizeCardCoverage(panels, CATEGORY_CARDS[activeCategory]);
  const activeCategoryLabel = categoryTabs.find((tab) => tab.key === activeCategory)?.label || '';
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
          {cryptoRealtimeStatus === 'live' ? '实时' : cryptoRealtimeStatus === 'reconnecting' ? '重连中' : '最近快照'}
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
          description={MARKET_OVERVIEW_CRYPTO_CONSUMER_DESCRIPTION}
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

  const usBreadthModulePanel = buildUsBreadthPanel(panels.usBreadth);
  const usBreadthDisclosure = buildUsBreadthDisclosure(panels.usBreadth);

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
        eyebrow={usBreadthDisclosure.eyebrow}
        description={usBreadthDisclosure.description}
        notice={usBreadthDisclosure.notice}
        panel={usBreadthModulePanel}
        sourceLabel={usBreadthDisclosure.sourceLabel}
        insightStrip={<UsBreadthTruthStrip panel={panels.usBreadth} />}
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
        description="美股行业强弱线索"
        panel={buildFilteredPanel(
          panels.usBreadth,
          'UsSectorHealthModule',
          ['STRONGEST_SECTOR', 'WEAKEST_SECTOR', 'XLK', 'XLF', 'XLY', 'XLE', 'XLV', 'XLI', 'XLP', 'XLU', 'SECTOR_PROXY_UNAVAILABLE'],
        )}
        sourceLabel="部分可用"
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
        description="资金费率；稳定币与占比在证据补齐前保持不可用"
        panel={buildCryptoLiquidityPanel(panels.crypto)}
        sourceLabel="部分可用 / 证据不足"
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

  const renderModule = (moduleId: MarketOverviewModuleId, rank: number, rail: WorkbenchRail = 'hero') => {
    const layoutMeta = MODULE_LAYOUT_META[moduleId];
    const cardTestId = MODULE_CARD_TEST_ID[moduleId] || moduleId;
    const denseQuoteModule = DENSE_QUOTE_MODULES.has(moduleId);
    return (
      <div
        key={moduleId}
        data-testid={`market-overview-card-${cardTestId}`}
        data-market-overview-module={moduleId}
        data-market-card-rank={rank}
        data-market-card-row={rail}
        data-market-card-size={layoutMeta.size}
        data-market-card-density={denseQuoteModule ? 'dense-quote' : 'standard'}
        className={cn(
          'h-full min-w-0 w-full overflow-hidden',
          denseQuoteModule ? DENSE_QUOTE_ROW_FIT_CLASS : '',
        )}
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
    const sectionMeta = CATEGORY_SECTION_META[activeCategory][row.id] || {
      eyebrow: '市场分组',
      title: '市场分组',
      detail: '按主题查看当前市场状态。',
    };
    return (
      <MarketOverviewSection key={row.id} rowId={row.id} meta={sectionMeta}>
        <MarketOverviewRow row={plannedRow}>{children}</MarketOverviewRow>
      </MarketOverviewSection>
    );
  };

  const topLevelDataStatus = summarizeTopLevelDataStatus({
    activeCategory,
    panels,
    coverageSummary,
    loading,
    refreshingPanel,
  });
  const marketDecision = buildMarketDecision({ activeCategory, panels, dataQuality, topLevelDataStatus });
  const decisionReliable = isTemperatureReliable(panels.temperature);
  const disabledLabel = temperatureDisabledStateLabel(panels.temperature);
  const regimeSynthesisView = buildMarketRegimeSynthesisView(
    panels.temperature.marketRegimeSynthesis,
    decisionReliable,
    language,
  );
  const regimeSummaryView = buildMarketOverviewRegimeSummaryView(
    panels.temperature.regimeSummary,
    language,
  );
  const decisionSemanticsView = buildMarketDecisionSemanticsView(
    panels.temperature.marketDecisionSemantics,
    language,
  );
  const directionalSummaryView = buildMarketDirectionalSummary({
    temperature: panels.temperature,
    briefing: panels.briefing,
    panels: {
      sectorRotation: panels.sectorRotation,
      fundsFlow: panels.fundsFlow,
      crypto: panels.crypto,
    },
    decisionReliable,
    locale: language,
  });
  const dataStateStatuses = collectDataStateMeta(panels).map(resolveProviderStatus);
  const fallbackCount = dataQuality.counts.fallback + dataQuality.counts.mock;
  const unavailableCount = dataStateStatuses.filter((status) => status === 'partial' || status === 'unavailable' || status === 'error').length + refreshErrorCount;
  const officialMacroRecords: OfficialMacroAuthorityRecord[] =
    (panels.macro?.items || []).map((item) => ({
      key: item.symbol,
      label: item.label,
      sourceLabel: item.sourceLabel,
      sourceTier: item.sourceTier,
      trustLevel: item.trustLevel,
      freshness: item.freshness,
      asOf: item.asOf,
      isFallback: item.isFallback,
      isUnavailable: item.isUnavailable,
      isPartial: item.isPartial,
      observationOnly: item.observationOnly,
      sourceAuthorityAllowed: item.sourceAuthorityAllowed,
      scoreContributionAllowed: item.scoreContributionAllowed,
      sourceAuthorityReason: item.sourceAuthorityReason,
      sourceAuthorityRouteRejected: item.sourceAuthorityRouteRejected,
      routeRejectedReasonCodes: item.routeRejectedReasonCodes,
      officialSeriesId: item.officialSeriesId,
      officialObservationDate: item.officialObservationDate,
      officialAsOf: item.officialAsOf,
    }));
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
    valueText: decisionReliable ? formatNumber(panels.temperature.scores.overall.value, 0) : '暂不判定',
    toneClass: decisionReliable ? scoreTone(panels.temperature.scores.overall) : 'text-white/45',
    label: decisionReliable ? panels.temperature.scores.overall.label : disabledLabel,
    confidenceLabel: confidenceLabel(panels.temperature.confidence),
    reliableInputCount: panels.temperature.reliableInputCount ?? 0,
    fallbackInputCount: panels.temperature.fallbackInputCount ?? 0,
    excludedInputCount: panels.temperature.excludedInputCount ?? 0,
  };
  const exportSummaryText = buildMarketOverviewEvidenceSnapshotMarkdown({
    activeCategoryLabel,
    coverageSummary,
    dataQuality,
    heroAnchors,
    language,
    temperature: panels.temperature,
    briefing: panels.briefing,
    regimeSynthesis: regimeSynthesisView,
    directionalSummary: directionalSummaryView,
    decisionSemantics: decisionSemanticsView,
    dataState: dataStateView,
    localSnapshotSavedAt,
  });
  const clipboardWriteText = typeof navigator === 'undefined'
    ? null
    : navigator.clipboard?.writeText?.bind(navigator.clipboard);
  const canCopyEvidenceSnapshot = Boolean(clipboardWriteText && exportSummaryText.trim());

  const handleExportSummary = () => {
    if (!clipboardWriteText || !exportSummaryText.trim()) {
      setExportSummaryFeedback('failed');
      return;
    }
    void clipboardWriteText(exportSummaryText)
      .then(() => {
        setExportSummaryFeedback('copied');
      })
      .catch(() => {
        setExportSummaryFeedback('failed');
      });
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
  const watchMetricLabels = MARKET_OVERVIEW_SIGNAL_WATCH[activeCategory]
    .slice(0, 3)
    .map((metricId) => findMetricItem(panels, metricId)?.label || metricId)
    .join(' · ');
  const contextHighlights: MarketOverviewContextHighlightView[] = [
    {
      id: 'top-risk',
      eyebrow: '当前风险',
      title: decisionSemanticsView?.counterEvidence[0]?.label || directionalSummaryView.blockingDrivers[0] || '暂无突出反证',
      detail: decisionSemanticsView?.counterEvidence[0]?.meta || directionalSummaryView.blockingTitle,
    },
    {
      id: 'next-watch',
      eyebrow: '下一观察',
      title: decisionSemanticsView?.invalidationTriggers[0]?.label || directionalSummaryView.watchItems[0] || '等待下一项确认信号',
      detail: decisionSemanticsView?.invalidationTriggers[0]?.meta || watchMetricLabels || directionalSummaryView.watchTitle,
    },
    {
      id: 'data-status',
      eyebrow: '数据状态',
      title: formatTopLevelDataStatus(topLevelDataStatus),
      detail: dataStateView.updatedAtLabel
        ? `最近更新：${dataStateView.updatedAtLabel}`
        : explainTopLevelDataStatus(topLevelDataStatus),
    },
  ];
  const executiveGroups: MarketOverviewExecutiveGroupView[] = [
    { id: 'us', label: 'US', focus: 'SPX / VIX', cardKey: 'indices', item: findMetricItem(panels, 'SPX') },
    { id: 'cn', label: 'CN/HK', focus: 'CSI300 / HSI', cardKey: 'cnIndices', item: findMetricItem(panels, 'CSI300') || findMetricItem(panels, 'HSI') },
    { id: 'macro', label: 'MACRO', focus: 'US10Y / DXY', cardKey: 'rates', item: findMetricItem(panels, 'US10Y') || findMetricItem(panels, 'DXY') },
    { id: 'crypto', label: 'CRYPTO', focus: 'BTC / ETH', cardKey: 'crypto', item: findMetricItem(panels, 'BTC') },
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
  const heroRows = activeRows.reduce<React.ReactNode[]>((acc, row, index) => { if (row.tier === 'hero') { const node = renderPlannedRow(row, index); if (node) acc.push(node); } return acc; }, []);
  const secondaryRows = activeRows.reduce<React.ReactNode[]>((acc, row, index) => { if (row.tier === 'secondary') { const node = renderPlannedRow(row, index); if (node) acc.push(node); } return acc; }, []);
  const deepRows = activeRows.reduce<React.ReactNode[]>((acc, row, index) => { if (row.tier === 'deep') { const node = renderPlannedRow(row, index); if (node) acc.push(node); } return acc; }, []);
  const visualEvidenceCards = buildVisualEvidenceCards({
    activeCategory,
    panels,
    language,
  });

  return {
    language,
    activeCategory,
    categoryTabs,
    setActiveCategory: handleCategoryChange,
    handleExportSummary,
    exportLabel: evidenceSnapshotCopyLabel(language, exportSummaryFeedback, canCopyEvidenceSnapshot),
    exportDisabled: !canCopyEvidenceSnapshot,
    directionalSummaryView,
    regimeSynthesisView,
    regimeSummaryView,
    marketDecision,
    decisionReliable,
    decisionSemanticsView,
    dataStateView,
    temperatureSummary,
    briefingSummary,
    officialMacroRecords,
    heroAnchorViews,
    visualEvidenceCards,
    showContextRail: activeTabConfig.rail.length > 0,
    contextHighlights,
    executiveGroups,
    showExecutiveGroups: activeCategory === 'all',
    heroRows,
    secondaryRows,
    deepRows,
    showDeepSection: activeRows.some((row) => row.tier === 'deep') || activeCategory === 'all',
  };
}

export const MarketOverviewWorkbench: React.FC<MarketOverviewWorkbenchProps> = ({
  heading,
  showAdminDiagnostics = false,
  ...modelProps
}) => {
  const {
    language,
    activeCategory,
    categoryTabs,
    setActiveCategory,
    handleExportSummary,
    exportLabel,
    exportDisabled,
    directionalSummaryView,
    regimeSynthesisView,
    regimeSummaryView,
    marketDecision,
    decisionReliable,
    decisionSemanticsView,
    dataStateView,
    temperatureSummary,
    briefingSummary,
    officialMacroRecords,
    heroAnchorViews,
    visualEvidenceCards,
    showContextRail,
    contextHighlights,
    executiveGroups,
    showExecutiveGroups,
    heroRows,
    secondaryRows,
    deepRows,
    showDeepSection,
  } = useMarketOverviewWorkbenchModel(modelProps);

  return (
    <div
      data-testid="market-overview-workbench"
      data-bento-surface="true"
      className="bento-surface-root flex min-h-0 w-full min-w-0 flex-1 flex-col gap-6 overflow-y-auto overflow-x-hidden no-scrollbar text-white"
    >
      <MarketOverviewWorkbenchTopSurface
        heading={heading}
        directionalSummary={directionalSummaryView}
        regimeSynthesis={regimeSynthesisView}
        regimeSummary={regimeSummaryView}
        decisionText={marketDecision.text}
        decisionChips={marketDecision.chips}
        decisionReliable={decisionReliable}
        decisionSemantics={decisionSemanticsView}
        dataState={dataStateView}
        temperatureSummary={temperatureSummary}
        briefingSummary={briefingSummary}
        officialMacroRecords={officialMacroRecords}
        categoryTabs={categoryTabs}
        activeCategory={activeCategory}
        onCategoryChange={setActiveCategory}
        exportLabel={exportLabel}
        exportDisabled={exportDisabled}
        onExportSummary={handleExportSummary}
        heroAnchors={heroAnchorViews}
        showAdminDiagnostics={showAdminDiagnostics}
      />
      <Suspense fallback={<MarketOverviewWorkbenchGridFallback language={language} />}>
        <LazyMarketOverviewWorkbenchGrid
          heroRows={heroRows}
          secondaryRows={secondaryRows}
          deepRows={deepRows}
          showDeepSection={showDeepSection}
          showContextRail={showContextRail}
          contextHighlights={contextHighlights}
          executiveGroups={executiveGroups}
          showExecutiveGroups={showExecutiveGroups}
        />
      </Suspense>
      <MarketOverviewVisualEvidenceStrip cards={visualEvidenceCards} />
    </div>
  );
};
