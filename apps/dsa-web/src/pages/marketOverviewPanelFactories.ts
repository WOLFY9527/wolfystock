import type { MarketOverviewPanel } from '../api/marketOverview';
import type {
  CnShortSentimentResponse,
  MarketBriefingResponse,
  MarketFuturesResponse,
  MarketTemperatureResponse,
} from '../api/market';
import type { PanelKey, PanelState } from '../components/market-overview/MarketOverviewWorkbench';

const UNAVAILABLE_TEMPERATURE_SCORE = {
  value: null as number | null,
  label: '数据不足',
  trend: 'stable' as const,
  description: '数据待补',
};

export const createUnavailableTemperature = (warning = '市场温度数据待补'): MarketTemperatureResponse => ({
  source: 'unavailable',
  sourceLabel: '待补数据',
  // No observation exists - do not invent epoch or client-now evidence timestamps.
  updatedAt: '',
  freshness: 'unavailable',
  isFallback: false,
  warning,
  confidence: 0,
  reliableInputCount: 0,
  fallbackInputCount: 0,
  excludedInputCount: 0,
  isReliable: false,
  temperatureAvailable: false,
  conclusionAllowed: false,
  disabledReason: 'missing_required_evidence',
  unavailableReason: 'market_overview_inputs_unavailable',
  scores: {
    overall: { ...UNAVAILABLE_TEMPERATURE_SCORE },
    usRiskAppetite: { ...UNAVAILABLE_TEMPERATURE_SCORE },
    cnMoneyEffect: { ...UNAVAILABLE_TEMPERATURE_SCORE },
    macroPressure: { ...UNAVAILABLE_TEMPERATURE_SCORE },
    liquidity: { ...UNAVAILABLE_TEMPERATURE_SCORE },
  },
});

export const createUnavailableBriefing = (warning = '市场简报数据待补'): MarketBriefingResponse => ({
  source: 'unavailable',
  sourceLabel: '待补数据',
  updatedAt: '',
  freshness: 'unavailable',
  isFallback: false,
  warning,
  confidence: 0,
  reliableInputCount: 0,
  fallbackInputCount: 0,
  excludedInputCount: 0,
  isReliable: false,
  items: [],
});

export const createUnavailableFutures = (warning = '期货数据待补'): MarketFuturesResponse => ({
  source: 'unavailable',
  sourceLabel: '待补数据',
  updatedAt: '',
  freshness: 'unavailable',
  isFallback: false,
  warning,
  items: [],
});

export const createUnavailableCnShortSentiment = (warning = '短线情绪数据待补'): CnShortSentimentResponse => ({
  source: 'unavailable',
  sourceLabel: '待补数据',
  updatedAt: '',
  freshness: 'unavailable',
  isFallback: false,
  warning,
  sentimentScore: 0,
  summary: '数据待补',
  metrics: {
    limitUpCount: 0,
    limitDownCount: 0,
    failedLimitUpRate: 0,
    maxConsecutiveLimitUps: 0,
    yesterdayLimitUpPerformance: 0,
    firstBoardCount: 0,
    secondBoardCount: 0,
    highBoardCount: 0,
    twentyCmLimitUpCount: 0,
    stRiskLevel: 'unknown',
  },
});

export function describePanelError(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error || '');
  const lower = message.toLowerCase();
  if (lower.includes('timeout') || lower.includes('timed out') || message.includes('超时')) {
    return '数据更新超时';
  }
  if (lower.includes('provider_down') || lower.includes('provider_error') || lower.includes('unavailable') || message.includes('不可用')) {
    return '部分数据暂不可用';
  }
  return '数据更新失败';
}

export function fallbackPanel(panelName: string, error: unknown): MarketOverviewPanel {
  const warning = describePanelError(error);
  // Error envelope without observation: preserve missing timestamps (not client-now or epoch).
  return {
    panelName,
    lastRefreshAt: '',
    status: 'failure',
    errorMessage: '更新失败：数据更新失败',
    source: 'error',
    sourceLabel: '数据更新中',
    updatedAt: '',
    asOf: undefined,
    freshness: 'error',
    isFallback: true,
    isStale: true,
    warning: `部分数据暂不可用，请稍后自动刷新。${warning}`,
    items: [],
  };
}

export function fallbackPanelValue(panelKey: PanelKey, error: unknown): PanelState[PanelKey] {
  switch (panelKey) {
    case 'temperature':
      return {
        ...createUnavailableTemperature(),
        warning: `市场温度数据待补。${describePanelError(error)}`,
      } as PanelState[PanelKey];
    case 'briefing':
      return {
        ...createUnavailableBriefing(),
        warning: `市场简报数据待补。${describePanelError(error)}`,
      } as PanelState[PanelKey];
    case 'futures':
      return {
        ...createUnavailableFutures(),
        warning: `期货数据待补。${describePanelError(error)}`,
      } as PanelState[PanelKey];
    case 'cnShortSentiment':
      return {
        ...createUnavailableCnShortSentiment(),
        warning: `短线情绪数据待补。${describePanelError(error)}`,
      } as PanelState[PanelKey];
    case 'indices':
      return fallbackPanel('IndexTrendsCard', error) as PanelState[PanelKey];
    case 'volatility':
      return fallbackPanel('VolatilityCard', error) as PanelState[PanelKey];
    case 'crypto':
      return fallbackPanel('CryptoCard', error) as PanelState[PanelKey];
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
    case 'usBreadth':
      return fallbackPanel('UsBreadthCard', error) as PanelState[PanelKey];
    case 'rates':
      return fallbackPanel('RatesCard', error) as PanelState[PanelKey];
    case 'fxCommodities':
      return fallbackPanel('FxCommoditiesCard', error) as PanelState[PanelKey];
  }
}

export const marketOverviewPanelFactoriesForTests = {
  createUnavailableTemperature: (warning?: string) => createUnavailableTemperature(warning),
  createUnavailableBriefing: (warning?: string) => createUnavailableBriefing(warning),
  createUnavailableFutures: (warning?: string) => createUnavailableFutures(warning),
  createUnavailableCnShortSentiment: (warning?: string) => createUnavailableCnShortSentiment(warning),
  fallbackPanel: (panelName: string, error: unknown) => fallbackPanel(panelName, error),
  fallbackPanelValue: (panelKey: PanelKey, error: unknown) => fallbackPanelValue(panelKey, error),
};
