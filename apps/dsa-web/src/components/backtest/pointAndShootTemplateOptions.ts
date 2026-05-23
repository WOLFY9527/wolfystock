type BacktestLanguage = 'zh' | 'en';

export const POINT_AND_SHOOT_TEMPLATE_OPTIONS = [
  { id: 'macd_crossover', name: { zh: 'MACD 金叉 / 死叉', en: 'MACD bullish / bearish crossover' } },
  { id: 'moving_average_crossover', name: { zh: '均线交叉（SMA / EMA）', en: 'Moving-average crossover (SMA / EMA)' } },
  { id: 'rsi_threshold', name: { zh: 'RSI 超买 / 超卖', en: 'RSI overbought / oversold' } },
  { id: 'periodic_accumulation', name: { zh: '定投策略', en: 'Periodic accumulation' } },
  { id: 'bollinger_breakout', name: { zh: '布林带突破', en: 'Bollinger Band breakout' } },
  { id: 'support_resistance_bounce', name: { zh: '支撑 / 阻力反弹', en: 'Support / resistance bounce' } },
  { id: 'atr_breakout', name: { zh: 'ATR 波动突破', en: 'ATR breakout' } },
  { id: 'obv_trend_confirmation', name: { zh: 'OBV 趋势确认', en: 'OBV trend confirmation' } },
  { id: 'macd_rsi_combo', name: { zh: 'MACD + RSI 共振', en: 'MACD + RSI combo' } },
  { id: 'sma_bollinger_combo', name: { zh: 'SMA + 布林带组合', en: 'SMA + Bollinger combo' } },
  { id: 'trend_momentum_volume_mix', name: { zh: '趋势 + 动量 + 量能混合', en: 'Trend + momentum + volume mix' } },
  { id: 'multi_indicator_trend_filter', name: { zh: '多指标趋势过滤', en: 'Multi-indicator trend filter' } },
  { id: 'bollinger_rsi_reversion_combo', name: { zh: '布林带 + RSI 回归组合', en: 'Bollinger + RSI reversion combo' } },
  { id: 'triple_moving_average_trend_stack', name: { zh: '三重均线趋势栈', en: 'Triple moving-average trend stack' } },
  { id: 'support_resistance_macd_combo', name: { zh: '支撑阻力 + MACD 组合', en: 'Support / resistance + MACD combo' } },
  { id: 'vwap_volume_breakout_combo', name: { zh: 'VWAP + 放量突破组合', en: 'VWAP + volume breakout combo' } },
] as const;

export type NormalStrategyTemplate = typeof POINT_AND_SHOOT_TEMPLATE_OPTIONS[number]['id'];

export function getPointAndShootTemplateName(template: NormalStrategyTemplate, language: BacktestLanguage): string {
  const option = POINT_AND_SHOOT_TEMPLATE_OPTIONS.find((item) => item.id === template);
  return option?.name[language] || '--';
}
