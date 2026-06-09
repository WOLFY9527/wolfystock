import type { MarketOverviewItem } from '../../api/marketOverview';
import type { UiLanguage } from '../../i18n/core';

export type MarketOverviewDisplayLabel = {
  primary: string;
  secondary?: string;
};

const PROXY_INDICATOR_LABEL_MAP: Record<string, MarketOverviewDisplayLabel> = {
  'ETF FLOW PROXY': { primary: 'ETF 资金流指标' },
  'INSTITUTIONAL PRESSURE PROXY': { primary: '机构压力指标' },
  'INDUSTRY BREADTH PROXY': { primary: '行业广度指标' },
};

const ZH_LABEL_MAP: Record<string, MarketOverviewDisplayLabel> = {
  ...PROXY_INDICATOR_LABEL_MAP,
  SPX: { primary: '标普500', secondary: 'SPX' },
  '^GSPC': { primary: '标普500', secondary: 'SPX' },
  'S&P 500': { primary: '标普500', secondary: 'SPX' },
  NDX: { primary: '纳斯达克100', secondary: 'NDX' },
  'NASDAQ 100': { primary: '纳斯达克100', secondary: 'NDX' },
  NASDAQ: { primary: '纳斯达克100', secondary: 'NDX' },
  IXIC: { primary: '纳斯达克综合指数', secondary: 'IXIC' },
  '^IXIC': { primary: '纳斯达克综合指数', secondary: 'IXIC' },
  'NASDAQ COMPOSITE': { primary: '纳斯达克综合指数', secondary: 'IXIC' },
  DJI: { primary: '道琼斯工业平均指数', secondary: 'DJI' },
  DJIA: { primary: '道琼斯工业平均指数', secondary: 'DJI' },
  '^DJI': { primary: '道琼斯工业平均指数', secondary: 'DJI' },
  'DOW JONES': { primary: '道琼斯工业平均指数', secondary: 'DJI' },
  'DOW JONES INDUSTRIAL AVERAGE': { primary: '道琼斯工业平均指数', secondary: 'DJI' },
  RUT: { primary: '罗素2000', secondary: 'RUT' },
  'RUSSELL 2000': { primary: '罗素2000', secondary: 'RUT' },
  SHCOMP: { primary: '上证指数', secondary: '000001.SH' },
  '000001.SH': { primary: '上证指数', secondary: '000001.SH' },
  SH000001: { primary: '上证指数', secondary: '000001.SH' },
  'SHANGHAI COMPOSITE': { primary: '上证指数', secondary: '000001.SH' },
  SZCOMP: { primary: '深证成指', secondary: '399001.SZ' },
  '399001.SZ': { primary: '深证成指', secondary: '399001.SZ' },
  SZ399001: { primary: '深证成指', secondary: '399001.SZ' },
  'SHENZHEN COMPONENT': { primary: '深证成指', secondary: '399001.SZ' },
  CHINEXT: { primary: '创业板指', secondary: '399006.SZ' },
  '399006.SZ': { primary: '创业板指', secondary: '399006.SZ' },
  SZ399006: { primary: '创业板指', secondary: '399006.SZ' },
  CSI300: { primary: '沪深300', secondary: 'CSI300' },
  '000300.SH': { primary: '沪深300', secondary: '000300.SH' },
  'CSI 300': { primary: '沪深300', secondary: 'CSI300' },
  HSI: { primary: '恒生指数', secondary: 'HSI' },
  'HANG SENG INDEX': { primary: '恒生指数', secondary: 'HSI' },
  HSTECH: { primary: '恒生科技指数', secondary: 'HSTECH' },
  'HANG SENG TECH': { primary: '恒生科技指数', secondary: 'HSTECH' },
  A50: { primary: '富时A50', secondary: 'A50' },
  CN00Y: { primary: '富时A50', secondary: 'A50' },
  US10Y: { primary: '美国10年期国债收益率', secondary: 'US10Y' },
  '10Y YIELD': { primary: '美国10年期国债收益率', secondary: 'US10Y' },
  'US 10Y': { primary: '美国10年期国债收益率', secondary: 'US10Y' },
  US2Y: { primary: '美国2年期国债收益率', secondary: 'US2Y' },
  'US 2Y': { primary: '美国2年期国债收益率', secondary: 'US2Y' },
  US30Y: { primary: '美国30年期国债收益率', secondary: 'US30Y' },
  'US 30Y': { primary: '美国30年期国债收益率', secondary: 'US30Y' },
  DXY: { primary: '美元指数', secondary: 'DXY' },
  'US DOLLAR INDEX': { primary: '美元指数', secondary: 'DXY' },
  USDJPY: { primary: 'USD/JPY', secondary: 'USDJPY' },
  'USD/JPY': { primary: 'USD/JPY', secondary: 'USDJPY' },
  USDCNH: { primary: 'USD/CNH', secondary: 'USDCNH' },
  'USD/CNH': { primary: 'USD/CNH', secondary: 'USDCNH' },
  WTI: { primary: 'WTI 原油', secondary: 'WTI' },
  OIL: { primary: 'WTI 原油', secondary: 'WTI' },
  'WTI CRUDE': { primary: 'WTI 原油', secondary: 'WTI' },
  BRENT: { primary: '布伦特原油', secondary: 'BRENT' },
  'BRENT CRUDE': { primary: '布伦特原油', secondary: 'BRENT' },
  GOLD: { primary: '黄金', secondary: 'GOLD' },
  'GOLD FUTURES': { primary: '黄金', secondary: 'GOLD' },
  VIX: { primary: 'VIX 恐慌指数', secondary: 'VIX' },
  VVIX: { primary: 'VVIX', secondary: 'VVIX' },
  FEDFUNDS: { primary: '联邦基金利率' },
  'FED FUNDS': { primary: '联邦基金利率' },
  'FEDERAL FUNDS RATE': { primary: '联邦基金利率' },
  BTC: { primary: '比特币', secondary: 'BTC' },
  BITCOIN: { primary: '比特币', secondary: 'BTC' },
  ETH: { primary: '以太坊', secondary: 'ETH' },
  ETHEREUM: { primary: '以太坊', secondary: 'ETH' },
  SOL: { primary: 'Solana', secondary: 'SOL' },
  SOLANA: { primary: 'Solana', secondary: 'SOL' },
  BNB: { primary: 'BNB', secondary: 'BNB' },
};

const EN_LABEL_MAP: Record<string, MarketOverviewDisplayLabel> = {
  ...PROXY_INDICATOR_LABEL_MAP,
  SPX: { primary: 'S&P 500', secondary: 'SPX' },
  '^GSPC': { primary: 'S&P 500', secondary: 'SPX' },
  'S&P 500': { primary: 'S&P 500', secondary: 'SPX' },
  NDX: { primary: 'Nasdaq 100', secondary: 'NDX' },
  'NASDAQ 100': { primary: 'Nasdaq 100', secondary: 'NDX' },
  DJI: { primary: 'Dow Jones Industrial Average', secondary: 'DJI' },
  DJIA: { primary: 'Dow Jones Industrial Average', secondary: 'DJI' },
  '^DJI': { primary: 'Dow Jones Industrial Average', secondary: 'DJI' },
  'DOW JONES': { primary: 'Dow Jones Industrial Average', secondary: 'DJI' },
  RUT: { primary: 'Russell 2000', secondary: 'RUT' },
  'RUSSELL 2000': { primary: 'Russell 2000', secondary: 'RUT' },
  SHCOMP: { primary: 'Shanghai Composite', secondary: '000001.SH' },
  '000001.SH': { primary: 'Shanghai Composite', secondary: '000001.SH' },
  SH000001: { primary: 'Shanghai Composite', secondary: '000001.SH' },
  'SHANGHAI COMPOSITE': { primary: 'Shanghai Composite', secondary: '000001.SH' },
  SZCOMP: { primary: 'Shenzhen Component', secondary: '399001.SZ' },
  '399001.SZ': { primary: 'Shenzhen Component', secondary: '399001.SZ' },
  SZ399001: { primary: 'Shenzhen Component', secondary: '399001.SZ' },
  'SHENZHEN COMPONENT': { primary: 'Shenzhen Component', secondary: '399001.SZ' },
  CHINEXT: { primary: 'ChiNext', secondary: '399006.SZ' },
  '399006.SZ': { primary: 'ChiNext', secondary: '399006.SZ' },
  SZ399006: { primary: 'ChiNext', secondary: '399006.SZ' },
  CSI300: { primary: 'CSI 300', secondary: 'CSI300' },
  '000300.SH': { primary: 'CSI 300', secondary: '000300.SH' },
  'CSI 300': { primary: 'CSI 300', secondary: 'CSI300' },
  HSI: { primary: 'Hang Seng Index', secondary: 'HSI' },
  'HANG SENG INDEX': { primary: 'Hang Seng Index', secondary: 'HSI' },
  HSTECH: { primary: 'Hang Seng TECH', secondary: 'HSTECH' },
  'HANG SENG TECH': { primary: 'Hang Seng TECH', secondary: 'HSTECH' },
  A50: { primary: 'FTSE China A50', secondary: 'A50' },
  CN00Y: { primary: 'FTSE China A50', secondary: 'A50' },
  US10Y: { primary: 'US 10Y Treasury Yield', secondary: 'US10Y' },
  '10Y YIELD': { primary: 'US 10Y Treasury Yield', secondary: 'US10Y' },
  'US 10Y': { primary: 'US 10Y Treasury Yield', secondary: 'US10Y' },
  US2Y: { primary: 'US 2Y Treasury Yield', secondary: 'US2Y' },
  'US 2Y': { primary: 'US 2Y Treasury Yield', secondary: 'US2Y' },
  US30Y: { primary: 'US 30Y Treasury Yield', secondary: 'US30Y' },
  'US 30Y': { primary: 'US 30Y Treasury Yield', secondary: 'US30Y' },
  DXY: { primary: 'US Dollar Index', secondary: 'DXY' },
  'US DOLLAR INDEX': { primary: 'US Dollar Index', secondary: 'DXY' },
  USDJPY: { primary: 'USD/JPY', secondary: 'USDJPY' },
  'USD/JPY': { primary: 'USD/JPY', secondary: 'USDJPY' },
  USDCNH: { primary: 'USD/CNH', secondary: 'USDCNH' },
  'USD/CNH': { primary: 'USD/CNH', secondary: 'USDCNH' },
  WTI: { primary: 'WTI Crude', secondary: 'WTI' },
  OIL: { primary: 'WTI Crude', secondary: 'WTI' },
  'WTI CRUDE': { primary: 'WTI Crude', secondary: 'WTI' },
  BRENT: { primary: 'Brent Crude', secondary: 'BRENT' },
  'BRENT CRUDE': { primary: 'Brent Crude', secondary: 'BRENT' },
  GOLD: { primary: 'Gold', secondary: 'GOLD' },
  'GOLD FUTURES': { primary: 'Gold', secondary: 'GOLD' },
  VIX: { primary: 'VIX Fear Index', secondary: 'VIX' },
  VVIX: { primary: 'VVIX', secondary: 'VVIX' },
  BTC: { primary: 'Bitcoin', secondary: 'BTC' },
  BITCOIN: { primary: 'Bitcoin', secondary: 'BTC' },
  ETH: { primary: 'Ethereum', secondary: 'ETH' },
  ETHEREUM: { primary: 'Ethereum', secondary: 'ETH' },
  SOL: { primary: 'Solana', secondary: 'SOL' },
  SOLANA: { primary: 'Solana', secondary: 'SOL' },
  BNB: { primary: 'BNB', secondary: 'BNB' },
};

function normalizeToken(value?: string | null): string {
  return (value || '').replace(/\s+/g, ' ').trim().toUpperCase();
}

export function resolveMarketOverviewDisplayLabel(
  item: Pick<MarketOverviewItem, 'symbol' | 'label'>,
  language: UiLanguage = 'zh',
): MarketOverviewDisplayLabel {
  const labelMap = language === 'en' ? EN_LABEL_MAP : ZH_LABEL_MAP;
  const bySymbol = labelMap[normalizeToken(item.symbol)];
  if (bySymbol) {
    return bySymbol;
  }
  const byLabel = labelMap[normalizeToken(item.label)];
  if (byLabel) {
    return byLabel;
  }
  return {
    primary: item.label || item.symbol,
    secondary: item.symbol && item.symbol !== item.label ? item.symbol : undefined,
  };
}
