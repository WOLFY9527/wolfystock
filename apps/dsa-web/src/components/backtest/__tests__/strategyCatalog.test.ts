import { describe, expect, it } from 'vitest';
import {
  BUILT_IN_STRATEGY_CATALOG,
  POINT_AND_SHOOT_TEMPLATE_IDS,
  POINT_AND_SHOOT_TEMPLATES,
  backtestStrategyDisplayCopy,
  buildPointAndShootStrategyDisplayText,
  buildPointAndShootStrategyText,
  getStrategyCatalogGroups,
} from '../strategyCatalog';

describe('strategyCatalog', () => {
  it('includes every deterministic-ready classic strategy in point-and-shoot mode', () => {
    expect([...POINT_AND_SHOOT_TEMPLATE_IDS]).toEqual([
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
    ]);
    expect(POINT_AND_SHOOT_TEMPLATES.map((template) => template.id)).toEqual([
      'macd_crossover',
      'moving_average_crossover',
      'rsi_threshold',
      'periodic_accumulation',
      'bollinger_breakout',
      'support_resistance_bounce',
      'atr_breakout',
      'obv_trend_confirmation',
      'macd_rsi_combo',
      'sma_bollinger_combo',
      'trend_momentum_volume_mix',
      'multi_indicator_trend_filter',
      'bollinger_rsi_reversion_combo',
      'triple_moving_average_trend_stack',
      'support_resistance_macd_combo',
      'vwap_volume_breakout_combo',
    ]);
    expect(POINT_AND_SHOOT_TEMPLATES.every((template) => template.executable)).toBe(true);
  });

  it('keeps all executable templates launchable for ordinary users and leaves unsupported templates as references', () => {
    const basicGroup = getStrategyCatalogGroups().find((group) => group.id === 'basic');

    expect(basicGroup?.templates.map((template) => template.id)).toEqual([
      'macd_crossover',
      'moving_average_crossover',
      'rsi_threshold',
      'periodic_accumulation',
    ]);
    expect(basicGroup?.templates.every((template) => template.executable)).toBe(true);

    const pointAndShootIds = new Set(POINT_AND_SHOOT_TEMPLATE_IDS);
    const referenceTemplates = BUILT_IN_STRATEGY_CATALOG.filter((template) => !pointAndShootIds.has(template.id as typeof POINT_AND_SHOOT_TEMPLATE_IDS[number]));

    expect(referenceTemplates.length).toBeGreaterThan(0);
    expect(referenceTemplates.every((template) => template.executable === false)).toBe(true);
  });

  it('keeps both executable and unsupported classic templates visible inside the professional catalog', () => {
    const groups = getStrategyCatalogGroups();
    const advancedGroup = groups.find((group) => group.id === 'advanced');
    const professionalGroup = groups.find((group) => group.id === 'professional');

    expect(advancedGroup?.templates.map((template) => template.id)).toEqual(expect.arrayContaining([
      'bollinger_breakout',
      'support_resistance_bounce',
      'volume_breakout',
      'atr_breakout',
      'obv_trend_confirmation',
      'stochastic_reversal',
    ]));
    expect(professionalGroup?.templates.map((template) => template.id)).toEqual(expect.arrayContaining([
      'macd_rsi_combo',
      'trend_momentum_volume_mix',
      'bollinger_rsi_reversion_combo',
      'triple_moving_average_trend_stack',
      'support_resistance_macd_combo',
    ]));
    expect(advancedGroup?.templates.find((template) => template.id === 'bollinger_breakout')?.executable).toBe(true);
    expect(advancedGroup?.templates.find((template) => template.id === 'volume_breakout')?.executable).toBe(false);
    expect(professionalGroup?.templates.find((template) => template.id === 'macd_rsi_combo')?.executable).toBe(true);
  });

  it('renders strategy cards and previews in observation language without changing submitted strategy text', () => {
    const rawStrategyText = buildPointAndShootStrategyText('zh', 'moving_average_crossover', {
      code: 'ORCL',
      startDate: '2026-01-01',
      endDate: '2026-12-31',
      initialCapital: '100000',
    });
    const displayStrategyText = buildPointAndShootStrategyDisplayText('zh', 'moving_average_crossover', {
      code: 'ORCL',
      startDate: '2026-01-01',
      endDate: '2026-12-31',
      initialCapital: '100000',
    });

    expect(rawStrategyText).toContain('买入');
    expect(rawStrategyText).toContain('卖出');
    expect(displayStrategyText).toContain('正向信号触发');
    expect(displayStrategyText).toContain('反向信号触发');
    expect(displayStrategyText).not.toMatch(/买入|卖出|止损|止盈|buy|sell|stop.?loss|take.?profit/i);

    const sanitizedCards = BUILT_IN_STRATEGY_CATALOG.map((template) => [
      backtestStrategyDisplayCopy(template.description.zh),
      backtestStrategyDisplayCopy(template.logicSummary.zh),
      backtestStrategyDisplayCopy(template.description.en),
      backtestStrategyDisplayCopy(template.logicSummary.en),
      ...template.defaultParameters.map((parameter) => backtestStrategyDisplayCopy(`${parameter.label.zh} ${parameter.label.en}`)),
    ].join(' ')).join(' ');

    expect(sanitizedCards).not.toMatch(/买入|卖出|止损|止盈|buy|sell|stop.?loss|take.?profit/i);
  });
});
