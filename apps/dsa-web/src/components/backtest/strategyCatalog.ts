import type { NormalStrategyTemplate } from './pointAndShootTemplateOptions';

export type BacktestLanguage = 'zh' | 'en';

type LocalizedText = Record<BacktestLanguage, string>;

export type StrategyTemplateCategoryId = 'basic' | 'advanced' | 'professional';

export type StrategyTemplateParameter = {
  key: string;
  label: LocalizedText;
  value: string | number;
};

export type StrategyCatalogEntry = {
  id: string;
  strategyFamily: string;
  category: StrategyTemplateCategoryId;
  executable: boolean;
  name: LocalizedText;
  description: LocalizedText;
  logicSummary: LocalizedText;
  editorText: LocalizedText;
  defaultParameters: StrategyTemplateParameter[];
};

export const POINT_AND_SHOOT_TEMPLATE_IDS = [
  'macd_crossover',
  'moving_average_crossover',
  'rsi_threshold',
  'periodic_accumulation',
  'bollinger_breakout',
  'atr_breakout',
  'obv_trend_confirmation',
  'support_resistance_bounce',
  'macd_rsi_combo',
  'sma_bollinger_combo',
  'trend_momentum_volume_mix',
  'multi_indicator_trend_filter',
  'bollinger_rsi_reversion_combo',
  'triple_moving_average_trend_stack',
  'support_resistance_macd_combo',
  'vwap_volume_breakout_combo',
] as const satisfies readonly NormalStrategyTemplate[];

export const STRATEGY_CATEGORY_COPY: Record<
StrategyTemplateCategoryId,
{ title: LocalizedText; description: LocalizedText }
> = {
  basic: {
    title: {
      zh: '基础 / 默认策略',
      en: 'Basic / Default Strategies',
    },
    description: {
      zh: '仅保留当前 deterministic 引擎可直接载入的默认模板，供普通用户直接研究。',
      en: 'Keeps only the deterministic-ready presets that ordinary users can load directly.',
    },
  },
  advanced: {
    title: {
      zh: '进阶 / 扩展策略',
      en: 'Advanced / Extended Strategies',
    },
    description: {
      zh: '扩展更多经典量价、波动率与区间模板；已支持的条目可直接研究，其余保留参考。',
      en: 'Expands the catalog with classic price, volume, and volatility setups; loadable templates open directly while the rest remain as references.',
    },
  },
  professional: {
    title: {
      zh: '专业 / 组合策略',
      en: 'Professional / Combination Strategies',
    },
    description: {
      zh: '保留多指标联合确认模板，适合在专业模式中做组合研究与改写。',
      en: 'Keeps multi-indicator combination templates available for professional research and rewrite workflows.',
    },
  },
};

export const BUILT_IN_STRATEGY_CATALOG: StrategyCatalogEntry[] = [
  {
    id: 'macd_crossover',
    strategyFamily: 'macd_crossover',
    category: 'basic',
    executable: true,
    name: { zh: 'MACD 金叉 / 死叉', en: 'MACD bullish / bearish crossover' },
    description: { zh: '经典趋势模板，用 MACD 金叉买入、死叉卖出。', en: 'Classic trend template that buys on a MACD bullish crossover and exits on a bearish crossover.' },
    logicSummary: { zh: '当 MACD 线向上穿过信号线时买入，向下跌破时卖出。', en: 'Buy when the MACD line crosses above the signal line and exit on the reverse crossover.' },
    editorText: { zh: 'MACD 金叉买入，死叉卖出', en: 'Buy on a MACD bullish crossover and sell on a bearish crossover' },
    defaultParameters: [
      { key: 'fastPeriod', label: { zh: '快线周期', en: 'Fast period' }, value: 12 },
      { key: 'slowPeriod', label: { zh: '慢线周期', en: 'Slow period' }, value: 26 },
      { key: 'signalPeriod', label: { zh: '信号周期', en: 'Signal period' }, value: 9 },
    ],
  },
  {
    id: 'moving_average_crossover',
    strategyFamily: 'moving_average_crossover',
    category: 'basic',
    executable: true,
    name: { zh: '均线交叉（SMA / EMA）', en: 'Moving-average crossover (SMA / EMA)' },
    description: { zh: '短均线上穿长均线买入，下穿卖出，适合普通用户入门。', en: 'Buy when a short moving average crosses above a long moving average, and exit on the reverse crossover.' },
    logicSummary: { zh: '默认使用 5 日与 20 日均线观察趋势切换。', en: 'Uses a default 5-day versus 20-day crossover to detect trend changes.' },
    editorText: { zh: '5日均线上穿20日均线买入，下穿卖出', en: 'Buy when the 5-day moving average crosses above the 20-day average, and sell on the reverse crossover' },
    defaultParameters: [
      { key: 'fastPeriod', label: { zh: '快线周期', en: 'Fast period' }, value: 5 },
      { key: 'slowPeriod', label: { zh: '慢线周期', en: 'Slow period' }, value: 20 },
      { key: 'averageType', label: { zh: '均线类型', en: 'Average type' }, value: 'SMA' },
    ],
  },
  {
    id: 'rsi_threshold',
    strategyFamily: 'rsi_threshold',
    category: 'basic',
    executable: true,
    name: { zh: 'RSI 超买 / 超卖', en: 'RSI overbought / oversold' },
    description: { zh: '用 RSI 判断超卖买入与超买卖出。', en: 'Uses RSI oversold and overbought thresholds for entries and exits.' },
    logicSummary: { zh: '默认 RSI14 低于 30 买入，高于 70 卖出。', en: 'Default behavior buys when RSI14 drops below 30 and exits above 70.' },
    editorText: { zh: 'RSI14 低于30买入，高于70卖出', en: 'Buy when RSI14 drops below 30 and sell when it rises above 70' },
    defaultParameters: [
      { key: 'period', label: { zh: 'RSI 周期', en: 'RSI period' }, value: 14 },
      { key: 'lowerThreshold', label: { zh: '超卖阈值', en: 'Oversold threshold' }, value: 30 },
      { key: 'upperThreshold', label: { zh: '超买阈值', en: 'Overbought threshold' }, value: 70 },
    ],
  },
  {
    id: 'periodic_accumulation',
    strategyFamily: 'periodic_accumulation',
    category: 'basic',
    executable: true,
    name: { zh: '定投策略', en: 'Periodic accumulation' },
    description: { zh: '按固定频率持续买入，适合验证长期资金部署。', en: 'Buys on a fixed cadence to test steady capital deployment.' },
    logicSummary: { zh: '默认每月投入固定金额，直到区间结束。', en: 'Invests a fixed amount on a monthly cadence until the backtest window ends.' },
    editorText: { zh: '每月定投1000美元', en: 'Invest 1000 USD every month' },
    defaultParameters: [
      { key: 'cadence', label: { zh: '定投频率', en: 'Cadence' }, value: 'monthly' },
      { key: 'amount', label: { zh: '每次金额', en: 'Amount per trade' }, value: 1000 },
      { key: 'cashPolicy', label: { zh: '现金策略', en: 'Cash policy' }, value: 'stop_when_insufficient_cash' },
    ],
  },
  {
    id: 'bollinger_breakout',
    strategyFamily: 'bollinger_breakout',
    category: 'advanced',
    executable: true,
    name: { zh: '布林带突破', en: 'Bollinger Band breakout' },
    description: { zh: '价格上破上轨时追随突破，回落时退出。', en: 'Follows upside breakouts above the upper Bollinger Band and exits on weakness.' },
    logicSummary: { zh: '收盘价突破上轨买入，跌回中轨或下轨卖出。', en: 'Buy when price closes above the upper band and exit on a move back to the middle or lower band.' },
    editorText: { zh: '收盘价突破布林带上轨买入，跌回中轨卖出', en: 'Buy when price closes above the upper Bollinger Band and sell when it falls back to the middle band' },
    defaultParameters: [
      { key: 'period', label: { zh: '带宽周期', en: 'Band period' }, value: 20 },
      { key: 'stdDev', label: { zh: '标准差倍数', en: 'Standard deviation' }, value: 2 },
      { key: 'exitLine', label: { zh: '离场参考', en: 'Exit line' }, value: 'middle_band' },
    ],
  },
  {
    id: 'previous_high_low_breakout',
    strategyFamily: 'previous_high_low_breakout',
    category: 'advanced',
    executable: false,
    name: { zh: '前高 / 前低突破', en: 'Previous high / low breakout' },
    description: { zh: '突破前高追涨，跌破前低离场，逻辑直观。', en: 'Buy on a break above a recent high and exit on a break below a recent low.' },
    logicSummary: { zh: '突破前 20 日高点买入，跌破前 10 日低点卖出。', en: 'Buy on a break above the prior 20-day high and exit below the prior 10-day low.' },
    editorText: { zh: '突破前20日最高价买入，跌破前10日最低价卖出', en: 'Buy on a break above the previous 20-day high and sell below the previous 10-day low' },
    defaultParameters: [
      { key: 'entryLookback', label: { zh: '突破观察窗口', en: 'Entry lookback' }, value: 20 },
      { key: 'exitLookback', label: { zh: '离场观察窗口', en: 'Exit lookback' }, value: 10 },
    ],
  },
  {
    id: 'simple_momentum',
    strategyFamily: 'simple_momentum',
    category: 'advanced',
    executable: false,
    name: { zh: '简单动量', en: 'Simple momentum' },
    description: { zh: '上涨动能延续时跟随，适合做基础趋势验证。', en: 'Rides basic momentum when recent performance stays strong.' },
    logicSummary: { zh: '近 20 日涨幅转正并创新高买入，跌破 10 日低点卖出。', en: 'Buy when the 20-day return turns positive and price makes a new short-term high, then exit below the 10-day low.' },
    editorText: { zh: '近20日涨幅转正并创新高买入，跌破10日低点卖出', en: 'Buy when the 20-day return turns positive and price makes a fresh high, then sell below the 10-day low' },
    defaultParameters: [
      { key: 'momentumLookback', label: { zh: '动量窗口', en: 'Momentum lookback' }, value: 20 },
      { key: 'exitLookback', label: { zh: '离场窗口', en: 'Exit lookback' }, value: 10 },
    ],
  },
  {
    id: 'simple_mean_reversion',
    strategyFamily: 'simple_mean_reversion',
    category: 'advanced',
    executable: false,
    name: { zh: '简单均值回归', en: 'Simple mean reversion' },
    description: { zh: '价格短期偏离均值后，等待回归反弹。', en: 'Looks for short-term deviations from the mean and a snap-back move.' },
    logicSummary: { zh: '价格低于 20 日均线 5% 买入，回到均线附近卖出。', en: 'Buy when price trades 5% below the 20-day average and exit near the mean.' },
    editorText: { zh: '价格低于20日均线5%买入，回到均线附近卖出', en: 'Buy when price trades 5% below the 20-day average and sell when it returns near the mean' },
    defaultParameters: [
      { key: 'meanPeriod', label: { zh: '均值周期', en: 'Mean period' }, value: 20 },
      { key: 'entryDeviationPct', label: { zh: '入场偏离', en: 'Entry deviation' }, value: '5%' },
      { key: 'exitTarget', label: { zh: '离场目标', en: 'Exit target' }, value: 'mean_retest' },
    ],
  },
  {
    id: 'ema_pullback_trend',
    strategyFamily: 'ema_pullback_trend',
    category: 'advanced',
    executable: false,
    name: { zh: 'EMA 回踩趋势', en: 'EMA pullback trend' },
    description: { zh: '趋势向上时等待回踩短期 EMA 再介入。', en: 'Waits for an orderly pullback into a rising EMA before entering.' },
    logicSummary: { zh: 'EMA20 在 EMA60 上方时，价格回踩 EMA20 再转强买入。', en: 'When EMA20 stays above EMA60, buy after price pulls back to EMA20 and turns back up.' },
    editorText: { zh: 'EMA20 在 EMA60 上方时，价格回踩 EMA20 再转强买入', en: 'Buy when EMA20 stays above EMA60 and price pulls back to EMA20 before turning up again' },
    defaultParameters: [
      { key: 'fastPeriod', label: { zh: '短 EMA', en: 'Fast EMA' }, value: 20 },
      { key: 'slowPeriod', label: { zh: '长 EMA', en: 'Slow EMA' }, value: 60 },
      { key: 'stopLossPct', label: { zh: '止损', en: 'Stop loss' }, value: '4%' },
    ],
  },
  {
    id: 'price_channel_breakout',
    strategyFamily: 'price_channel_breakout',
    category: 'advanced',
    executable: false,
    name: { zh: '价格通道突破', en: 'Price channel breakout' },
    description: { zh: '用价格通道判断区间突破与失效。', en: 'Uses a simple price channel to detect breakouts and breakdown exits.' },
    logicSummary: { zh: '突破 20 日通道上沿买入，跌破 10 日通道下沿卖出。', en: 'Buy above the 20-day channel high and exit below the 10-day channel low.' },
    editorText: { zh: '突破20日价格通道上沿买入，跌破10日通道下沿卖出', en: 'Buy above the 20-day price channel high and sell below the 10-day channel low' },
    defaultParameters: [
      { key: 'entryChannel', label: { zh: '入场通道', en: 'Entry channel' }, value: 20 },
      { key: 'exitChannel', label: { zh: '离场通道', en: 'Exit channel' }, value: 10 },
    ],
  },
  {
    id: 'rsi_mean_reversion',
    strategyFamily: 'rsi_mean_reversion',
    category: 'advanced',
    executable: false,
    name: { zh: 'RSI 均值回归', en: 'RSI mean reversion' },
    description: { zh: '更偏交易型的反转思路，等待超卖反弹。', en: 'A more tactical mean-reversion setup that looks for oversold rebounds.' },
    logicSummary: { zh: 'RSI2 跌破 10 买入，反弹到 60 附近卖出。', en: 'Buy when RSI2 falls below 10 and exit after it rebounds toward 60.' },
    editorText: { zh: 'RSI2 低于10买入，反弹到60附近卖出', en: 'Buy when RSI2 falls below 10 and sell when it rebounds toward 60' },
    defaultParameters: [
      { key: 'period', label: { zh: 'RSI 周期', en: 'RSI period' }, value: 2 },
      { key: 'entryThreshold', label: { zh: '入场阈值', en: 'Entry threshold' }, value: 10 },
      { key: 'exitThreshold', label: { zh: '离场阈值', en: 'Exit threshold' }, value: 60 },
    ],
  },
  {
    id: 'bollinger_band_reversion',
    strategyFamily: 'bollinger_band_reversion',
    category: 'advanced',
    executable: false,
    name: { zh: '布林带回归', en: 'Bollinger Band reversion' },
    description: { zh: '价格跌出下轨后，等待回归中轨。', en: 'Looks for a rebound after price stretches below the lower band.' },
    logicSummary: { zh: '价格跌破下轨买入，回到中轨或上轨减仓离场。', en: 'Buy when price drops below the lower band and exit as it reverts toward the middle or upper band.' },
    editorText: { zh: '价格跌破布林带下轨买入，回到中轨卖出', en: 'Buy when price drops below the lower Bollinger Band and sell when it reverts to the middle band' },
    defaultParameters: [
      { key: 'period', label: { zh: '带宽周期', en: 'Band period' }, value: 20 },
      { key: 'stdDev', label: { zh: '标准差倍数', en: 'Standard deviation' }, value: 2 },
      { key: 'exitLine', label: { zh: '回归目标', en: 'Reversion target' }, value: 'middle_band' },
    ],
  },
  {
    id: 'volume_breakout',
    strategyFamily: 'volume_breakout',
    category: 'advanced',
    executable: false,
    name: { zh: '成交量突破', en: 'Volume breakout' },
    description: { zh: '量价同时放大时介入，适合观察放量突破。', en: 'Focuses on breakouts that are confirmed by expanding volume.' },
    logicSummary: { zh: '价格突破平台高点且成交量大于 20 日均量 1.5 倍时买入。', en: 'Buy when price breaks a recent range high with volume at least 1.5x the 20-day average.' },
    editorText: { zh: '价格突破平台高点且成交量放大到20日均量1.5倍时买入', en: 'Buy when price breaks the range high and volume expands to 1.5x the 20-day average' },
    defaultParameters: [
      { key: 'priceLookback', label: { zh: '平台窗口', en: 'Price lookback' }, value: 20 },
      { key: 'volumeMultiplier', label: { zh: '放量倍数', en: 'Volume multiplier' }, value: '1.5x' },
      { key: 'exitRule', label: { zh: '离场规则', en: 'Exit rule' }, value: 'fall_back_into_range' },
    ],
  },
  {
    id: 'price_volume_divergence',
    strategyFamily: 'price_volume_divergence',
    category: 'advanced',
    executable: false,
    name: { zh: '价量背离', en: 'Price-volume divergence' },
    description: { zh: '用价格创新高而量能转弱的背离信号观察风险。', en: 'Tracks divergence when price pushes higher but volume support fades.' },
    logicSummary: { zh: '价格创新高但量能未同步放大时减仓或离场。', en: 'Exit or reduce when price makes a fresh high without confirming volume expansion.' },
    editorText: { zh: '价格创新高但量能不再放大时减仓离场', en: 'Reduce or exit when price makes a new high but volume no longer confirms' },
    defaultParameters: [
      { key: 'priceLookback', label: { zh: '价格窗口', en: 'Price window' }, value: 20 },
      { key: 'volumeLookback', label: { zh: '量能窗口', en: 'Volume window' }, value: 20 },
    ],
  },
  {
    id: 'support_resistance_bounce',
    strategyFamily: 'support_resistance_bounce',
    category: 'advanced',
    executable: true,
    name: { zh: '支撑 / 阻力反弹', en: 'Support / resistance bounce' },
    description: { zh: '接近支撑位企稳时买入，接近阻力位减仓。', en: 'Looks for a bounce near support and trims near resistance.' },
    logicSummary: { zh: '回踩前低或平台支撑企稳买入，接近前高或阻力位卖出。', en: 'Buy after price stabilizes near support and exit as it approaches prior resistance.' },
    editorText: { zh: '回踩支撑企稳买入，接近阻力位卖出', en: 'Buy after price stabilizes near support and sell as it approaches resistance' },
    defaultParameters: [
      { key: 'supportLookback', label: { zh: '支撑观察窗', en: 'Support lookback' }, value: 20 },
      { key: 'resistanceLookback', label: { zh: '阻力观察窗', en: 'Resistance lookback' }, value: 20 },
    ],
  },
  {
    id: 'prior_day_range_breakout',
    strategyFamily: 'prior_day_range_breakout',
    category: 'advanced',
    executable: false,
    name: { zh: '前一日区间突破', en: 'Prior-day range breakout' },
    description: { zh: '常见波段模板，用前一日高低点做突破确认。', en: 'A swing-trading template that uses the prior day range as the trigger.' },
    logicSummary: { zh: '突破前一日高点买入，跌回前一日低点附近卖出。', en: 'Buy above the prior day high and exit on a fade back toward the prior day low.' },
    editorText: { zh: '突破前一日高点买入，跌回前一日低点附近卖出', en: 'Buy above the prior day high and sell when price fades back toward the prior day low' },
    defaultParameters: [
      { key: 'referenceRange', label: { zh: '参考区间', en: 'Reference range' }, value: 'prior_day' },
      { key: 'confirmation', label: { zh: '确认方式', en: 'Confirmation' }, value: 'close_above_high' },
    ],
  },
  {
    id: 'atr_breakout',
    strategyFamily: 'atr_breakout',
    category: 'advanced',
    executable: true,
    name: { zh: 'ATR 波动突破', en: 'ATR volatility breakout' },
    description: { zh: '用 ATR 扩张确认波动放大，再跟随价格突破。', en: 'Uses ATR expansion to confirm rising volatility before following a price breakout.' },
    logicSummary: { zh: 'ATR14 扩张且价格突破前高时买入，跌回突破位下方卖出。', en: 'Buy when ATR14 expands and price breaks a prior high, then exit if price falls back below the breakout zone.' },
    editorText: { zh: 'ATR14 扩张且价格突破前高时买入，跌回突破位下方卖出', en: 'Buy when ATR14 expands and price breaks a prior high, then sell if price falls back below the breakout zone' },
    defaultParameters: [
      { key: 'atrPeriod', label: { zh: 'ATR 周期', en: 'ATR period' }, value: 14 },
      { key: 'atrExpansion', label: { zh: '波动扩张', en: 'ATR expansion' }, value: '20d high' },
      { key: 'breakoutLookback', label: { zh: '突破窗口', en: 'Breakout lookback' }, value: 20 },
    ],
  },
  {
    id: 'obv_trend_confirmation',
    strategyFamily: 'obv_trend_confirmation',
    category: 'advanced',
    executable: true,
    name: { zh: 'OBV 趋势确认', en: 'OBV trend confirmation' },
    description: { zh: '用能量潮指标确认量价同步上行，再顺势参与。', en: 'Uses On-Balance Volume to confirm price and volume rising together before entering.' },
    logicSummary: { zh: '价格站上均线且 OBV 同步创新高时买入，OBV 转弱时离场。', en: 'Buy when price holds above its moving average and OBV prints a new high, then exit when OBV weakens.' },
    editorText: { zh: '价格站上均线且 OBV 同步创新高时买入，OBV 转弱时卖出', en: 'Buy when price stays above its moving average and OBV confirms with a new high, then sell when OBV weakens' },
    defaultParameters: [
      { key: 'trendAverage', label: { zh: '趋势均线', en: 'Trend average' }, value: 50 },
      { key: 'obvLookback', label: { zh: 'OBV 观察窗', en: 'OBV lookback' }, value: 20 },
      { key: 'exitSignal', label: { zh: '离场信号', en: 'Exit signal' }, value: 'obv_lower_high' },
    ],
  },
  {
    id: 'stochastic_reversal',
    strategyFamily: 'stochastic_reversal',
    category: 'advanced',
    executable: false,
    name: { zh: '随机指标反转', en: 'Stochastic reversal' },
    description: { zh: '用随机指标捕捉超卖区反弹与超买区钝化。', en: 'Uses the stochastic oscillator to catch oversold reversals and manage overbought exits.' },
    logicSummary: { zh: 'K 线在 20 下方上穿 D 线买入，K 线跌回 80 下方卖出。', en: 'Buy when %K crosses above %D below 20, then exit when %K falls back under 80.' },
    editorText: { zh: '随机指标 K 线在20下方上穿 D 线买入，跌回80下方卖出', en: 'Buy when stochastic %K crosses above %D below 20, then sell when %K falls back under 80' },
    defaultParameters: [
      { key: 'kPeriod', label: { zh: 'K 周期', en: 'K period' }, value: 14 },
      { key: 'dPeriod', label: { zh: 'D 周期', en: 'D period' }, value: 3 },
      { key: 'oversoldLevel', label: { zh: '超卖位', en: 'Oversold level' }, value: 20 },
    ],
  },
  {
    id: 'donchian_breakout',
    strategyFamily: 'donchian_breakout',
    category: 'advanced',
    executable: false,
    name: { zh: '唐奇安通道突破', en: 'Donchian channel breakout' },
    description: { zh: '用唐奇安通道跟踪趋势突破，并以较短通道控制离场。', en: 'Tracks trend breakouts with a Donchian channel and uses a shorter channel for exits.' },
    logicSummary: { zh: '突破 20 日通道上沿买入，跌破 10 日通道下沿卖出。', en: 'Buy above the 20-day Donchian high and exit below the 10-day Donchian low.' },
    editorText: { zh: '突破20日唐奇安通道上沿买入，跌破10日下沿卖出', en: 'Buy above the 20-day Donchian channel high and sell below the 10-day channel low' },
    defaultParameters: [
      { key: 'entryChannel', label: { zh: '入场通道', en: 'Entry channel' }, value: 20 },
      { key: 'exitChannel', label: { zh: '离场通道', en: 'Exit channel' }, value: 10 },
      { key: 'riskNote', label: { zh: '风控备注', en: 'Risk note' }, value: 'breakout_follow' },
    ],
  },
  {
    id: 'macd_rsi_combo',
    strategyFamily: 'macd_rsi_combo',
    category: 'professional',
    executable: true,
    name: { zh: 'MACD + RSI 共振', en: 'MACD + RSI combo' },
    description: { zh: '用趋势和动量双确认减少单指标噪音。', en: 'Combines trend and momentum confirmation to reduce single-indicator noise.' },
    logicSummary: { zh: 'MACD 金叉且 RSI14 上穿 50 买入，任一信号走弱时卖出。', en: 'Buy when MACD turns bullish and RSI14 rises above 50, then exit when either signal weakens.' },
    editorText: { zh: 'MACD金叉且RSI14上穿50买入，任一信号走弱卖出', en: 'Buy when MACD turns bullish and RSI14 rises above 50, then sell when either signal weakens' },
    defaultParameters: [
      { key: 'macd', label: { zh: 'MACD 参数', en: 'MACD parameters' }, value: '12/26/9' },
      { key: 'rsiPeriod', label: { zh: 'RSI 周期', en: 'RSI period' }, value: 14 },
      { key: 'rsiConfirm', label: { zh: '动量确认', en: 'Momentum confirm' }, value: 50 },
    ],
  },
  {
    id: 'sma_bollinger_combo',
    strategyFamily: 'sma_bollinger_combo',
    category: 'professional',
    executable: true,
    name: { zh: 'SMA + 布林带组合', en: 'SMA + Bollinger combo' },
    description: { zh: '先判断趋势方向，再用波动率带筛掉假突破。', en: 'Uses trend direction first and Bollinger structure second to filter weak breakouts.' },
    logicSummary: { zh: 'SMA20 在 SMA60 上方且价格重新站上布林带中轨时买入。', en: 'Buy when SMA20 stays above SMA60 and price reclaims the Bollinger middle band.' },
    editorText: { zh: 'SMA20 在 SMA60 上方且价格重回布林带中轨上方时买入', en: 'Buy when SMA20 stays above SMA60 and price reclaims the Bollinger middle band' },
    defaultParameters: [
      { key: 'trendWindow', label: { zh: '趋势均线', en: 'Trend averages' }, value: '20 / 60' },
      { key: 'bollinger', label: { zh: '布林带参数', en: 'Bollinger settings' }, value: '20 / 2' },
    ],
  },
  {
    id: 'trend_momentum_volume_mix',
    strategyFamily: 'trend_momentum_volume_mix',
    category: 'professional',
    executable: true,
    name: { zh: '趋势 + 动量 + 量能混合', en: 'Trend + momentum + volume mix' },
    description: { zh: '把趋势、动量、量能三类信号放在一套规则里联合确认。', en: 'Mixes trend, momentum, and volume into a single confirmation stack.' },
    logicSummary: { zh: '均线多头、RSI 强势且放量突破同时出现时买入。', en: 'Buy only when moving averages align, RSI stays strong, and a volume-confirmed breakout appears together.' },
    editorText: { zh: '均线多头、RSI 强势且放量突破同时出现时买入', en: 'Buy when moving averages align, RSI stays strong, and a volume-confirmed breakout appears together' },
    defaultParameters: [
      { key: 'maStack', label: { zh: '均线结构', en: 'MA stack' }, value: '20 / 60 / 120' },
      { key: 'rsiThreshold', label: { zh: 'RSI 强势线', en: 'RSI strength line' }, value: 55 },
      { key: 'volumeMultiplier', label: { zh: '放量倍数', en: 'Volume multiplier' }, value: '1.5x' },
    ],
  },
  {
    id: 'multi_indicator_trend_filter',
    strategyFamily: 'multi_indicator_trend_filter',
    category: 'professional',
    executable: true,
    name: { zh: '多指标趋势过滤', en: 'Multi-indicator trend filter' },
    description: { zh: '先用趋势过滤市场状态，再在强势区间内触发入场。', en: 'Filters for favorable regime first, then triggers entries only inside strong trend windows.' },
    logicSummary: { zh: '价格位于长期均线上方、MACD 为正且 ATR 扩张时才允许入场。', en: 'Allow entries only when price is above the long-term average, MACD stays positive, and ATR is expanding.' },
    editorText: { zh: '价格位于长期均线上方、MACD 为正且波动率扩张时才允许入场', en: 'Only allow entries when price is above the long-term average, MACD is positive, and volatility is expanding' },
    defaultParameters: [
      { key: 'trendAverage', label: { zh: '长期均线', en: 'Trend average' }, value: 120 },
      { key: 'atrPeriod', label: { zh: 'ATR 周期', en: 'ATR period' }, value: 14 },
      { key: 'macdBias', label: { zh: 'MACD 偏向', en: 'MACD bias' }, value: 'positive_histogram' },
    ],
  },
  {
    id: 'bollinger_rsi_reversion_combo',
    strategyFamily: 'bollinger_rsi_reversion_combo',
    category: 'professional',
    executable: true,
    name: { zh: '布林带 + RSI 回归组合', en: 'Bollinger + RSI reversion combo' },
    description: { zh: '把波动率带与 RSI 超卖信号叠加，减少单一反转信号误判。', en: 'Stacks Bollinger structure with RSI oversold confirmation to reduce noisy reversal entries.' },
    logicSummary: { zh: '价格跌破下轨且 RSI2 低于 10 时买入，回到中轨或 RSI 回到 60 卖出。', en: 'Buy when price falls below the lower band and RSI2 drops under 10, then exit at the middle band or RSI 60.' },
    editorText: { zh: '价格跌破布林带下轨且 RSI2 低于10时买入，回到中轨或 RSI 回到60卖出', en: 'Buy when price falls below the lower Bollinger Band and RSI2 drops under 10, then sell at the middle band or RSI 60' },
    defaultParameters: [
      { key: 'bollinger', label: { zh: '布林带参数', en: 'Bollinger settings' }, value: '20 / 2' },
      { key: 'rsiPeriod', label: { zh: 'RSI 周期', en: 'RSI period' }, value: 2 },
      { key: 'rsiEntry', label: { zh: 'RSI 入场位', en: 'RSI entry' }, value: 10 },
    ],
  },
  {
    id: 'triple_moving_average_trend_stack',
    strategyFamily: 'triple_moving_average_trend_stack',
    category: 'professional',
    executable: true,
    name: { zh: '三重均线趋势栈', en: 'Triple moving-average trend stack' },
    description: { zh: '用短中长期均线排序确认趋势，只在多头排列内参与。', en: 'Uses short, medium, and long moving-average alignment to confirm a clean trend stack.' },
    logicSummary: { zh: 'SMA20 > SMA60 > SMA120 且价格回踩 SMA20 再转强时买入。', en: 'Buy when SMA20 stays above SMA60 above SMA120 and price rebounds after retesting SMA20.' },
    editorText: { zh: 'SMA20 大于 SMA60 且 SMA60 大于 SMA120，价格回踩 SMA20 转强时买入', en: 'Buy when SMA20 is above SMA60 above SMA120 and price turns back up after retesting SMA20' },
    defaultParameters: [
      { key: 'maStack', label: { zh: '均线结构', en: 'MA stack' }, value: '20 / 60 / 120' },
      { key: 'entryTrigger', label: { zh: '入场触发', en: 'Entry trigger' }, value: 'pullback_to_fast_ma' },
      { key: 'trendFilter', label: { zh: '趋势过滤', en: 'Trend filter' }, value: 'stacked_bullish' },
    ],
  },
  {
    id: 'support_resistance_macd_combo',
    strategyFamily: 'support_resistance_macd_combo',
    category: 'professional',
    executable: true,
    name: { zh: '支撑阻力 + MACD 组合', en: 'Support / resistance + MACD combo' },
    description: { zh: '先看关键位，再用 MACD 确认反弹或突破是否有效。', en: 'Blends key support and resistance levels with MACD confirmation for cleaner entries.' },
    logicSummary: { zh: '价格在支撑位企稳且 MACD 金叉时买入，接近阻力位或 MACD 死叉时卖出。', en: 'Buy when price holds support and MACD turns bullish, then exit near resistance or on a bearish MACD crossover.' },
    editorText: { zh: '价格在支撑位企稳且 MACD 金叉时买入，接近阻力位或 MACD 死叉时卖出', en: 'Buy when price holds support and MACD turns bullish, then sell near resistance or on a bearish MACD crossover' },
    defaultParameters: [
      { key: 'supportLookback', label: { zh: '支撑观察窗', en: 'Support lookback' }, value: 20 },
      { key: 'resistanceLookback', label: { zh: '阻力观察窗', en: 'Resistance lookback' }, value: 20 },
      { key: 'macd', label: { zh: 'MACD 参数', en: 'MACD parameters' }, value: '12 / 26 / 9' },
    ],
  },
  {
    id: 'vwap_volume_breakout_combo',
    strategyFamily: 'vwap_volume_breakout_combo',
    category: 'professional',
    executable: true,
    name: { zh: 'VWAP + 放量突破组合', en: 'VWAP + volume breakout combo' },
    description: { zh: '把 VWAP 站稳和放量突破叠加，适合做更严格的突破筛选。', en: 'Stacks VWAP reclaim with volume-confirmed breakouts for stricter breakout validation.' },
    logicSummary: { zh: '价格重回 VWAP 上方且突破平台高点并放量时买入，跌回 VWAP 下方卖出。', en: 'Buy when price reclaims VWAP, breaks range highs, and volume expands, then exit below VWAP.' },
    editorText: { zh: '价格重回 VWAP 上方且突破平台高点并放量时买入，跌回 VWAP 下方卖出', en: 'Buy when price reclaims VWAP, breaks range highs, and volume expands, then sell below VWAP' },
    defaultParameters: [
      { key: 'vwapAnchor', label: { zh: 'VWAP 锚点', en: 'VWAP anchor' }, value: 'session' },
      { key: 'priceLookback', label: { zh: '平台窗口', en: 'Price lookback' }, value: 20 },
      { key: 'volumeMultiplier', label: { zh: '放量倍数', en: 'Volume multiplier' }, value: '1.8x' },
    ],
  },
];

const POINT_AND_SHOOT_TEMPLATE_SET = new Set<string>(POINT_AND_SHOOT_TEMPLATE_IDS);

export const POINT_AND_SHOOT_TEMPLATES = BUILT_IN_STRATEGY_CATALOG.filter(
  (template): template is StrategyCatalogEntry & { id: NormalStrategyTemplate } =>
    template.executable && POINT_AND_SHOOT_TEMPLATE_SET.has(template.id),
);

const BACKTEST_STRATEGY_COPY_REPLACEMENTS: Array<[RegExp, string]> = [
  [/买入条件/g, '入场规则样本'],
  [/卖出条件/g, '退出规则样本'],
  [/持续买入/g, '持续投入样本'],
  [/买入并持有/g, '持有参照'],
  [/买入持有/g, '持有参照'],
  [/买入/g, '入场规则样本'],
  [/卖出/g, '退出规则样本'],
  [/减仓或离场/g, '暴露收缩或退出规则样本'],
  [/减仓离场/g, '暴露收缩或退出规则样本'],
  [/减仓/g, '暴露收缩规则样本'],
  [/离场/g, '退出规则样本'],
  [/介入/g, '开始观察'],
  [/参与/g, '观察'],
  [/开仓/g, '开启观察'],
  [/建仓/g, '建立观察状态'],
  [/加仓/g, '暴露扩展规则样本'],
  [/止损/g, '风险退出规则'],
  [/止盈/g, '上方参考退出规则'],
  [/\bbuy(?:s|ing)?\b/gi, 'entry rule sample'],
  [/\bsell(?:s|ing)?\b/gi, 'exit rule sample'],
  [/\breduce or exit\b/gi, 'exposure reduction or exit rule sample'],
  [/\bexit(?:s|ing)?\b/gi, 'exit rule sample'],
  [/\benter(?:s|ing)?\b/gi, 'start observing'],
  [/\btrims?\b/gi, 'tracks exposure reduction'],
  [/\bstop[-\s]?loss\b/gi, 'risk exit rule'],
  [/\btake[-\s]?profit\b/gi, 'upside reference exit rule'],
];

export function backtestStrategyDisplayCopy(value: string): string {
  return BACKTEST_STRATEGY_COPY_REPLACEMENTS.reduce(
    (text, [pattern, replacement]) => text.replace(pattern, replacement),
    value,
  );
}

function sanitizeStrategyLocalizedText(text: LocalizedText): LocalizedText {
  return {
    zh: backtestStrategyDisplayCopy(text.zh),
    en: backtestStrategyDisplayCopy(text.en),
  };
}

function sanitizeStrategyCatalogEntry(entry: StrategyCatalogEntry): StrategyCatalogEntry {
  return {
    ...entry,
    description: sanitizeStrategyLocalizedText(entry.description),
    logicSummary: sanitizeStrategyLocalizedText(entry.logicSummary),
    editorText: sanitizeStrategyLocalizedText(entry.editorText),
    defaultParameters: entry.defaultParameters.map((parameter) => ({
      ...parameter,
      label: sanitizeStrategyLocalizedText(parameter.label),
    })),
  };
}

export function getStrategyCatalogEntry(templateId: string): StrategyCatalogEntry | undefined {
  const template = BUILT_IN_STRATEGY_CATALOG.find((item) => item.id === templateId);
  return template ? sanitizeStrategyCatalogEntry(template) : undefined;
}

export function getStrategyCatalogGroups(): Array<{
  id: StrategyTemplateCategoryId;
  title: LocalizedText;
  description: LocalizedText;
  templates: StrategyCatalogEntry[];
}> {
  return (['basic', 'advanced', 'professional'] as StrategyTemplateCategoryId[]).map((category) => ({
    id: category,
    title: STRATEGY_CATEGORY_COPY[category].title,
    description: STRATEGY_CATEGORY_COPY[category].description,
    templates: BUILT_IN_STRATEGY_CATALOG.filter((template) => template.category === category).map(sanitizeStrategyCatalogEntry),
  }));
}

export function buildPointAndShootStrategyText(
  language: BacktestLanguage,
  template: NormalStrategyTemplate,
  payload: {
    code: string;
    startDate: string;
    endDate: string;
    initialCapital: string;
  },
): string {
  const resolvedCode = payload.code || (language === 'en' ? 'the selected ticker' : '当前标的');
  const resolvedStart = payload.startDate || (language === 'en' ? 'the start date' : '开始日期');
  const resolvedEnd = payload.endDate || (language === 'en' ? 'the end date' : '结束日期');
  const resolvedCapital = payload.initialCapital || '100000';
  const selectedTemplate = getStrategyCatalogEntry(template);
  const editorText = selectedTemplate?.editorText[language]
    || (language === 'en'
      ? 'Use the 5-day moving average crossing above the 20-day average as the entry rule sample, and the reverse crossover as the exit rule sample'
      : '5日均线上穿20日均线作为入场规则样本，下穿作为退出规则样本');

  return language === 'en'
    ? `Use initial capital ${resolvedCapital}. Backtest ${resolvedCode} from ${resolvedStart} to ${resolvedEnd}. ${editorText}.`
    : `初始资金 ${resolvedCapital}，回测 ${resolvedCode} 在 ${resolvedStart} 到 ${resolvedEnd} 的表现，${editorText}。`;
}

export function buildPointAndShootStrategyDisplayText(
  language: BacktestLanguage,
  template: NormalStrategyTemplate,
  payload: {
    code: string;
    startDate: string;
    endDate: string;
    initialCapital: string;
  },
): string {
  return backtestStrategyDisplayCopy(buildPointAndShootStrategyText(language, template, payload));
}
