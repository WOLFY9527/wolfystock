export type MarketOverviewTab = 'all' | 'us' | 'cn' | 'global' | 'crypto';

export type MarketOverviewPulseMetricId =
  | 'SPX'
  | 'NDX'
  | 'DJI'
  | 'RUT'
  | 'SHCOMP'
  | 'SZCOMP'
  | 'CHINEXT'
  | 'CSI300'
  | 'HSI'
  | 'HSTECH'
  | 'A50'
  | 'BTC'
  | 'ETH'
  | 'SOL'
  | 'BNB'
  | 'VIX'
  | 'VVIX'
  | 'US10Y'
  | 'US2Y'
  | 'US30Y'
  | 'DXY'
  | 'USDJPY'
  | 'USDCNH'
  | 'GOLD'
  | 'WTI';

export type MarketOverviewModuleId =
  | 'globalIndices'
  | 'usIndices'
  | 'cnHkIndices'
  | 'cryptoCore'
  | 'volatility'
  | 'fundsFlow'
  | 'sentiment'
  | 'rates'
  | 'fxCommodities'
  | 'cryptoSnapshot'
  | 'cnSnapshot'
  | 'usRates'
  | 'usSentiment'
  | 'usBreadth'
  | 'usSectorRotation'
  | 'macroContext'
  | 'cnBreadth'
  | 'cnFlows'
  | 'sectorRotation'
  | 'shortSentiment'
  | 'fxCnhContext'
  | 'macroRates'
  | 'macroFxCommodities'
  | 'globalRisk'
  | 'cryptoMomentum'
  | 'cryptoLiquidity'
  | 'cryptoRiskContext'
  | 'cryptoSentiment';

export type MarketOverviewRailId = 'coverage' | 'quality' | 'signalWatch' | 'actionHint';

export const MARKET_OVERVIEW_TAB_CONFIG: Record<MarketOverviewTab, {
  label: string;
  pulse: MarketOverviewPulseMetricId[];
  hero: MarketOverviewModuleId[];
  modules: MarketOverviewModuleId[];
  rail: MarketOverviewRailId[];
}> = {
  all: {
    label: '全部',
    pulse: ['SPX', 'CSI300', 'HSI', 'BTC', 'VIX', 'US10Y', 'DXY'],
    hero: ['globalIndices'],
    modules: ['volatility', 'fundsFlow', 'sentiment', 'rates', 'fxCommodities', 'cryptoSnapshot', 'cnSnapshot'],
    rail: ['coverage', 'quality', 'signalWatch', 'actionHint'],
  },
  us: {
    label: '美股',
    pulse: ['SPX', 'NDX', 'DJI', 'RUT', 'VIX', 'US10Y', 'DXY'],
    hero: ['usIndices'],
    modules: ['volatility', 'usRates', 'usSentiment', 'usBreadth', 'usSectorRotation', 'macroContext'],
    rail: ['coverage', 'quality', 'signalWatch', 'actionHint'],
  },
  cn: {
    label: 'A股/港股',
    pulse: ['SHCOMP', 'SZCOMP', 'CHINEXT', 'CSI300', 'HSI', 'HSTECH', 'A50', 'USDCNH'],
    hero: ['cnHkIndices'],
    modules: ['cnBreadth', 'cnFlows', 'sectorRotation', 'shortSentiment', 'fxCnhContext'],
    rail: ['coverage', 'quality', 'signalWatch', 'actionHint'],
  },
  global: {
    label: '全球宏观',
    pulse: ['US10Y', 'DXY', 'USDJPY', 'USDCNH', 'GOLD', 'WTI', 'VIX', 'BTC'],
    hero: ['macroRates'],
    modules: ['macroFxCommodities', 'globalRisk', 'sentiment', 'volatility'],
    rail: ['coverage', 'quality', 'signalWatch', 'actionHint'],
  },
  crypto: {
    label: '加密货币',
    pulse: ['BTC', 'ETH', 'SOL', 'BNB'],
    hero: ['cryptoCore'],
    modules: ['cryptoMomentum', 'cryptoLiquidity', 'cryptoRiskContext', 'cryptoSentiment'],
    rail: ['coverage', 'quality', 'signalWatch', 'actionHint'],
  },
};
