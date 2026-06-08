import type {
  RuleBacktestDrawdownRegimeAttribution,
  RuleBacktestParseResponse,
  RuleBacktestParsedStrategy,
  RuleBacktestRunRequest,
  RuleBacktestRunResponse,
} from '../../types/backtest';
import type { DeterministicBacktestNormalizedResult } from './normalizeDeterministicBacktestResult';
import { getAutoBenchmarkMode, getBenchmarkModeLabel, getStrategySpecValue } from './shared';
import { getRuleStrategyTypeLabel } from './strategyInspectability';

type BacktestLanguage = 'zh' | 'en';
type DrawdownAttributionState = 'available' | 'partial' | 'unavailable';

const DRAWDOWN_ATTRIBUTION_BUCKET_ORDER = [
  'peak',
  'shallow',
  'moderate',
  'deep',
  'severe',
  'unknown',
] as const;

export type RuleScenarioPlanId =
  | 'benchmark_modes'
  | 'cost_stress'
  | 'lookback_window'
  | 'ma_window_variants'
  | 'macd_signal_variants'
  | 'rsi_threshold_variants';

export type RuleScenarioVariant = {
  id: string;
  label: string;
  description: string;
  request: RuleBacktestRunRequest;
};

export type RuleScenarioPlan = {
  id: RuleScenarioPlanId;
  label: string;
  description: string;
  variants: RuleScenarioVariant[];
};

export type RuleBacktestPreset = {
  id: string;
  kind: 'saved' | 'recent';
  name: string;
  savedAt: string;
  sourceRunId?: number | null;
  code: string;
  strategyText: string;
  startDate: string;
  endDate: string;
  lookbackBars: string;
  initialCapital: string;
  feeBps: string;
  slippageBps: string;
  benchmarkMode: string;
  benchmarkCode: string;
};

export type RuleRunNarrative = {
  verdict: string;
  headline: string;
  benchmarkLabel: string;
  drawdownLabel: string;
  activityLabel: string;
  qualityLabel: string;
  detail: string;
};

export const RULE_BACKTEST_PRESET_STORAGE_KEY = 'wolfystock.ruleBacktestPresets.v1';

const MAX_SAVED_PRESETS = 6;
const MAX_RECENT_PRESETS = 4;

function asFiniteNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function trimText(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function pctLabel(value: number | null | undefined, digits = 2): string {
  if (value == null || !Number.isFinite(value)) return '--';
  return `${value.toFixed(digits)}%`;
}

function moneyLabel(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '--';
  return value.toFixed(2);
}

function numberLabel(value: number | null | undefined, digits = 0): string {
  if (value == null || !Number.isFinite(value)) return '--';
  return value.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function drawdownPctLabel(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '--';
  return pctLabel(value > 0 ? -value : value);
}

function dedupeVariants(variants: RuleScenarioVariant[]): RuleScenarioVariant[] {
  const seen = new Set<string>();
  return variants.filter((variant) => {
    const key = JSON.stringify({
      strategyText: variant.request.strategyText,
      lookbackBars: variant.request.lookbackBars,
      feeBps: variant.request.feeBps,
      slippageBps: variant.request.slippageBps,
      benchmarkMode: variant.request.benchmarkMode,
      benchmarkCode: variant.request.benchmarkCode,
      parsedStrategy: variant.request.parsedStrategy,
    });
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function getParsedStrategyFamily(run: Pick<RuleBacktestRunResponse, 'parsedStrategy'>): string {
  return trimText(String(
    getStrategySpecValue((run.parsedStrategy.strategySpec as Record<string, unknown> | undefined), ['strategy_type'])
      || run.parsedStrategy.strategyKind
      || run.parsedStrategy.detectedStrategyFamily
      || '',
  ));
}

function getRuleStrategySpec(parsedStrategy: RuleBacktestParsedStrategy | RuleBacktestParseResponse['parsedStrategy'] | null | undefined): Record<string, unknown> | undefined {
  if (!parsedStrategy) return undefined;
  if (parsedStrategy.strategySpec && typeof parsedStrategy.strategySpec === 'object') {
    return parsedStrategy.strategySpec as Record<string, unknown>;
  }
  if (parsedStrategy.setup && typeof parsedStrategy.setup === 'object') {
    return parsedStrategy.setup;
  }
  return undefined;
}

function getMaWindowSummary(spec: Record<string, unknown> | undefined): string | null {
  const fast = asFiniteNumber(getStrategySpecValue(spec, ['signal', 'fast_period']));
  const slow = asFiniteNumber(getStrategySpecValue(spec, ['signal', 'slow_period']));
  if (fast == null || slow == null) return null;
  const fastType = trimText(getStrategySpecValue(spec, ['signal', 'fast_type'])) || 'simple';
  const slowType = trimText(getStrategySpecValue(spec, ['signal', 'slow_type'])) || 'simple';
  const fastLabel = `${fastType === 'ema' ? 'EMA' : 'SMA'}${fast}`;
  const slowLabel = `${slowType === 'ema' ? 'EMA' : 'SMA'}${slow}`;
  return `${fastLabel}/${slowLabel}`;
}

function getMacdSummary(spec: Record<string, unknown> | undefined): string | null {
  const fast = asFiniteNumber(getStrategySpecValue(spec, ['signal', 'fast_period']));
  const slow = asFiniteNumber(getStrategySpecValue(spec, ['signal', 'slow_period']));
  const signal = asFiniteNumber(getStrategySpecValue(spec, ['signal', 'signal_period']));
  if (fast == null || slow == null || signal == null) return null;
  return `MACD ${fast}/${slow}/${signal}`;
}

function getRsiSummary(spec: Record<string, unknown> | undefined): string | null {
  const period = asFiniteNumber(getStrategySpecValue(spec, ['signal', 'period']));
  const lower = asFiniteNumber(getStrategySpecValue(spec, ['signal', 'lower_threshold']));
  const upper = asFiniteNumber(getStrategySpecValue(spec, ['signal', 'upper_threshold']));
  if (period == null || lower == null || upper == null) return null;
  return `RSI${period} ${lower}/${upper}`;
}

export function getRuleRunSetupHighlights(
  run: Pick<RuleBacktestRunResponse, 'code' | 'parsedStrategy' | 'lookbackBars' | 'feeBps' | 'slippageBps' | 'benchmarkMode' | 'benchmarkCode'>,
  language: BacktestLanguage = 'zh',
): string[] {
  const spec = getRuleStrategySpec(run.parsedStrategy);
  const family = getParsedStrategyFamily(run);
  const highlights: string[] = [];

  if (family === 'moving_average_crossover') {
    const summary = getMaWindowSummary(spec);
    if (summary) highlights.push(summary);
  } else if (family === 'macd_crossover') {
    const summary = getMacdSummary(spec);
    if (summary) highlights.push(summary);
  } else if (family === 'rsi_threshold') {
    const summary = getRsiSummary(spec);
    if (summary) highlights.push(summary);
  } else if (family === 'periodic_accumulation') {
    const frequency = trimText(String(getStrategySpecValue(spec, ['schedule', 'frequency']) || ''));
    const quantity = asFiniteNumber(getStrategySpecValue(spec, ['entry', 'order', 'quantity']));
    const amount = asFiniteNumber(getStrategySpecValue(spec, ['entry', 'order', 'amount']));
    if (frequency) highlights.push(language === 'en' ? `Frequency ${frequency}` : `频率 ${frequency}`);
    if (quantity != null) highlights.push(language === 'en' ? `${quantity} shares/trade` : `${quantity} 股/次`);
    if (amount != null) highlights.push(language === 'en' ? `${amount} amount/trade` : `${amount} 金额/次`);
  }

  highlights.push(language === 'en' ? `Lookback ${run.lookbackBars} bars` : `回看 ${run.lookbackBars} bars`);
  highlights.push(language === 'en' ? `Fees/slippage ${Number(run.feeBps ?? 0).toFixed(1)}/${Number(run.slippageBps ?? 0).toFixed(1)}bp` : `费滑 ${Number(run.feeBps ?? 0).toFixed(1)}/${Number(run.slippageBps ?? 0).toFixed(1)}bp`);
  highlights.push(getBenchmarkModeLabel((run.benchmarkMode as Parameters<typeof getBenchmarkModeLabel>[0]) || 'auto', run.code, run.benchmarkCode || undefined, language));
  return highlights.slice(0, 4);
}

function getDrawdownLabel(value: number | null | undefined, language: BacktestLanguage = 'zh'): string {
  const resolved = Math.abs(asFiniteNumber(value) ?? 0);
  if (resolved < 4) return language === 'en' ? 'Light drawdown' : '轻微回撤';
  if (resolved < 10) return language === 'en' ? 'Moderate drawdown' : '中等回撤';
  return language === 'en' ? 'Deep drawdown' : '较深回撤';
}

function getTradeActivityLabel(tradeCount: number, language: BacktestLanguage = 'zh'): string {
  if (tradeCount <= 2) return language === 'en' ? 'Low frequency' : '低频';
  if (tradeCount <= 8) return language === 'en' ? 'Medium frequency' : '中频';
  return language === 'en' ? 'High frequency' : '高频';
}

function getQualityLabel(
  run: Pick<RuleBacktestRunResponse, 'winRatePct' | 'avgTradeReturnPct'>,
  language: BacktestLanguage = 'zh',
): string {
  const winRate = asFiniteNumber(run.winRatePct);
  const avgTradeReturn = asFiniteNumber(run.avgTradeReturnPct);
  if (winRate != null && avgTradeReturn != null) {
    if (winRate >= 60 && avgTradeReturn >= 1) return language === 'en' ? 'Signal quality looks steady' : '信号质量较稳';
    if (winRate < 45 || avgTradeReturn < 0) return language === 'en' ? 'Signal quality looks weak' : '信号质量偏弱';
  }
  if (winRate != null) {
    if (winRate >= 60) return language === 'en' ? 'Win rate looks steady' : '胜率较稳';
    if (winRate < 45) return language === 'en' ? 'Win rate looks weak' : '胜率偏弱';
  }
  return language === 'en' ? 'Quality needs more samples' : '质量待结合更多样本观察';
}

function asObjectRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' ? value as Record<string, unknown> : null;
}

function getObjectField(record: Record<string, unknown> | null, key: string): unknown {
  return record ? record[key] : undefined;
}

function hasObjectFields(record: Record<string, unknown> | null): boolean {
  return Boolean(record && Object.keys(record).length > 0);
}

function getFiniteNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function normalizeRobustnessState(value: unknown): 'available' | 'partial' | 'unavailable' | 'insufficient_history' | null {
  const normalized = String(value || '').trim().toLowerCase().replaceAll('-', '_');
  if (normalized === 'available' || normalized === 'partial' || normalized === 'unavailable' || normalized === 'insufficient_history') {
    return normalized;
  }
  return null;
}

function getRobustnessStateText(value: unknown, language: BacktestLanguage = 'zh'): string {
  const normalized = normalizeRobustnessState(value);
  if (normalized === 'available') return language === 'en' ? 'available' : '可用';
  if (normalized === 'partial') return language === 'en' ? 'partial' : '部分可用';
  if (normalized === 'unavailable') return language === 'en' ? 'unavailable' : '不可用';
  if (normalized === 'insufficient_history') return language === 'en' ? 'insufficient history' : '样本不足';
  return language === 'en' ? 'unavailable' : '不可用';
}

function getStressScenarioFriendlyLabel(
  scenarioKey: unknown,
  rawLabel: unknown,
  language: BacktestLanguage = 'zh',
  fallbackIndex?: number,
): string {
  const normalized = String(scenarioKey || '').trim().toLowerCase();
  if (normalized === 'single_day_shock_down_15') return language === 'en' ? 'Single-day shock down 15%' : '单日冲击下跌 15%';
  if (normalized === 'volatility_whipsaw') return language === 'en' ? 'Volatility whipsaw' : '波动率来回扫';
  if (normalized === 'gap_down_open') return language === 'en' ? 'Gap-down open' : '跳空低开';

  const text = trimText(rawLabel);
  if (text) return text;
  if (typeof fallbackIndex === 'number') {
    return language === 'en' ? `Stress scenario ${fallbackIndex + 1}` : `压力场景 ${fallbackIndex + 1}`;
  }
  return language === 'en' ? 'Stress scenario' : '压力场景';
}

function getStoredDrawdownAttribution(
  run: Pick<RuleBacktestRunResponse, 'summary'>,
): RuleBacktestDrawdownRegimeAttribution | null {
  const summary = asObjectRecord(run.summary);
  const attribution = asObjectRecord(getObjectField(summary, 'drawdownRegimeAttribution'));
  return attribution as RuleBacktestDrawdownRegimeAttribution | null;
}

function normalizeDrawdownAttributionState(value: unknown): DrawdownAttributionState {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'available' || normalized === 'partial' || normalized === 'unavailable') {
    return normalized;
  }
  return 'unavailable';
}

function getDrawdownAttributionStateText(
  state: DrawdownAttributionState,
  language: BacktestLanguage = 'zh',
): string {
  if (state === 'available') return language === 'en' ? 'Available' : '可用';
  if (state === 'partial') return language === 'en' ? 'Partial' : '部分可用';
  return language === 'en' ? 'Not provided' : '未提供';
}

function getDrawdownAttributionSourceText(
  source: unknown,
  state: DrawdownAttributionState,
  language: BacktestLanguage = 'zh',
): string {
  if (state === 'unavailable' || String(source || '').trim().toLowerCase() === 'unavailable') {
    return language === 'en' ? 'Not provided' : '当前未提供';
  }
  return language === 'en' ? 'Stored audit-row summary' : '已存审计行汇总';
}

function getDrawdownAttributionBucketLabel(
  key: string,
  language: BacktestLanguage = 'zh',
): string {
  if (key === 'peak') return language === 'en' ? 'Peak' : '高点区间';
  if (key === 'shallow') return language === 'en' ? 'Shallow' : '浅度回撤';
  if (key === 'moderate') return language === 'en' ? 'Moderate' : '中度回撤';
  if (key === 'deep') return language === 'en' ? 'Deep' : '深度回撤';
  if (key === 'severe') return language === 'en' ? 'Severe' : '严重回撤';
  return language === 'en' ? 'Unclassified' : '未归类';
}

function getOrderedDrawdownAttributionBuckets(
  attribution: RuleBacktestDrawdownRegimeAttribution | null,
): Array<[string, NonNullable<RuleBacktestDrawdownRegimeAttribution['bucketCounts']>[string]]> {
  const bucketCounts = attribution?.bucketCounts;
  if (!bucketCounts || typeof bucketCounts !== 'object') {
    return [];
  }

  return DRAWDOWN_ATTRIBUTION_BUCKET_ORDER.reduce((acc, key) => {
    if (asObjectRecord(bucketCounts[key])) {
      acc.push([key, bucketCounts[key]!]);
    }
    return acc;
  }, [] as Array<[string, NonNullable<RuleBacktestDrawdownRegimeAttribution['bucketCounts']>[string]]>);
}

function buildDrawdownAttributionAppendix(
  run: Pick<RuleBacktestRunResponse, 'summary'>,
  language: BacktestLanguage = 'zh',
): string[] {
  const attribution = getStoredDrawdownAttribution(run);
  const state = normalizeDrawdownAttributionState(attribution?.state);
  const classifiedRows = attribution?.contributionSummaries?.classifiedRows;
  const missingRows = attribution?.contributionSummaries?.missingRows;
  const bucketRows = getOrderedDrawdownAttributionBuckets(attribution);
  const authorityLine = language === 'en'
    ? 'Summarizes drawdown phases from stored audit rows only. It explains drawdown sources and does not change return, max drawdown, trade, chart, or report-conclusion authority.'
    : '基于已存审计行的回撤阶段汇总，仅用于解释回撤来源；不改变收益、最大回撤、交易、图表或报告结论口径。';
  const lines: string[] = [
    language === 'en' ? '## Drawdown phase attribution appendix' : '## 回撤阶段归因附录',
    '',
    `- ${authorityLine}`,
    `- ${language === 'en' ? 'State' : '状态'}：${getDrawdownAttributionStateText(state, language)}`,
    `- ${language === 'en' ? 'Source' : '来源'}：${getDrawdownAttributionSourceText(attribution?.source, state, language)}`,
  ];

  if (!attribution) {
    lines.push(`- ${language === 'en' ? 'This result does not include drawdown phase attribution.' : '当前结果未提供回撤阶段归因。'}`);
    return lines;
  }

  if (classifiedRows?.count != null || bucketRows.length > 0) {
    lines.push(
      `- ${language === 'en' ? 'Classified rows / buckets' : '已归类行 / 桶数'}：${numberLabel(classifiedRows?.count, 0)} / ${numberLabel(bucketRows.length, 0)}`,
    );
  }
  if (classifiedRows?.sharePct != null) {
    lines.push(`- ${language === 'en' ? 'Classified share' : '已归类占比'}：${pctLabel(classifiedRows.sharePct)}`);
  }
  if (missingRows?.sharePct != null) {
    lines.push(`- ${language === 'en' ? 'Missing share' : '缺失占比'}：${pctLabel(missingRows.sharePct)}`);
  }

  if (bucketRows.length === 0) {
    lines.push(`- ${language === 'en' ? 'No drawdown-phase bucket detail is available.' : '当前结果未提供可展示的回撤阶段分桶明细。'}`);
    return lines;
  }

  bucketRows.forEach(([key, bucket]) => {
    lines.push(
      `- ${getDrawdownAttributionBucketLabel(key, language)}：${language === 'en'
        ? `rows ${numberLabel(bucket.count, 0)} · share ${pctLabel(bucket.sharePct)} · average depth ${drawdownPctLabel(bucket.avgDepthPct)} · worst depth ${drawdownPctLabel(bucket.worstDepthPct)}`
        : `行数 ${numberLabel(bucket.count, 0)} · 占比 ${pctLabel(bucket.sharePct)} · 平均深度 ${drawdownPctLabel(bucket.avgDepthPct)} · 最深回撤 ${drawdownPctLabel(bucket.worstDepthPct)}`}`,
    );
  });

  return lines;
}

function buildRobustnessAppendix(
  run: Pick<RuleBacktestRunResponse, 'robustnessAnalysis'>,
  language: BacktestLanguage = 'zh',
): string[] | null {
  const robustnessAnalysis = asObjectRecord(run.robustnessAnalysis);
  if (!robustnessAnalysis) return null;

  const walkForward = asObjectRecord(getObjectField(robustnessAnalysis, 'walkForward'));
  const walkForwardAggregate = asObjectRecord(getObjectField(walkForward, 'aggregateMetrics'));
  const monteCarlo = asObjectRecord(getObjectField(robustnessAnalysis, 'monteCarlo'));
  const monteCarloAggregate = asObjectRecord(getObjectField(monteCarlo, 'aggregateMetrics'));
  const stressTests = asObjectRecord(getObjectField(robustnessAnalysis, 'stressTests'));
  const worstScenario = asObjectRecord(getObjectField(stressTests, 'worstScenario'));
  const stressScenarios = Array.isArray(getObjectField(stressTests, 'scenarios'))
    ? getObjectField(stressTests, 'scenarios') as unknown[]
    : [];
  const hasRobustnessData = Boolean(
    getObjectField(robustnessAnalysis, 'state')
    || hasObjectFields(walkForward)
    || hasObjectFields(monteCarlo)
    || hasObjectFields(stressTests),
  );

  if (!hasRobustnessData) return null;

  const lines: string[] = [
    language === 'en' ? '## Robustness appendix' : '## 稳健性附录',
    '',
  ];

  const walkForwardState = getRobustnessStateText(getObjectField(walkForward, 'state') ?? getObjectField(robustnessAnalysis, 'state'), language);
  const walkForwardWindowCount = getFiniteNumber(getObjectField(walkForward, 'windowCount'));
  const walkForwardMeanReturn = getFiniteNumber(getObjectField(walkForwardAggregate, 'meanTotalReturnPct'));
  const walkForwardDrawdown = getFiniteNumber(
    getObjectField(walkForwardAggregate, 'maxDrawdownPct')
    ?? getObjectField(walkForwardAggregate, 'meanMaxDrawdownPct'),
  );
  lines.push(language === 'en' ? '- Walk-forward / out-of-sample' : '- Walk-forward / 样本外检验');
  lines.push(`  - ${language === 'en' ? 'State' : '状态'}：${walkForwardState}`);
  if (walkForwardWindowCount != null) lines.push(`  - ${language === 'en' ? 'Window count' : '窗口数'}：${numberLabel(walkForwardWindowCount, 0)}`);
  if (walkForwardMeanReturn != null) lines.push(`  - ${language === 'en' ? 'Mean return' : '平均收益'}：${pctLabel(walkForwardMeanReturn)}`);
  if (walkForwardDrawdown != null) lines.push(`  - ${language === 'en' ? 'Drawdown' : '回撤'}：${drawdownPctLabel(walkForwardDrawdown)}`);
  if (
    walkForwardState === (language === 'en' ? 'insufficient history' : '样本不足')
    && walkForwardWindowCount == null
    && walkForwardMeanReturn == null
    && walkForwardDrawdown == null
  ) {
    lines.push(`  - ${language === 'en' ? 'Insufficient history to show detail' : '样本不足，暂无可展示的明细。'}`);
  }

  const monteCarloState = getRobustnessStateText(getObjectField(monteCarlo, 'state') ?? getObjectField(robustnessAnalysis, 'state'), language);
  const p05Return = getFiniteNumber(getObjectField(monteCarloAggregate, 'p05TotalReturnPct'));
  const medianReturn = getFiniteNumber(getObjectField(monteCarloAggregate, 'medianTotalReturnPct'));
  const p95Return = getFiniteNumber(getObjectField(monteCarloAggregate, 'p95TotalReturnPct'));
  const meanReturn = getFiniteNumber(getObjectField(monteCarloAggregate, 'meanTotalReturnPct'));
  const worstMaxDrawdown = getFiniteNumber(getObjectField(monteCarloAggregate, 'worstMaxDrawdownPct'));
  const simulationCount = getFiniteNumber(getObjectField(monteCarlo, 'simulationCount'));
  const seed = getFiniteNumber(getObjectField(monteCarlo, 'seed'));
  lines.push(language === 'en' ? '- Monte Carlo distribution' : '- 蒙特卡洛分布');
  lines.push(`  - ${language === 'en' ? 'State' : '状态'}：${monteCarloState}`);
  if (p05Return != null || medianReturn != null || p95Return != null || meanReturn != null) {
    lines.push(`  - ${language === 'en' ? 'P05 / median / P95 / mean total return' : 'P05 / 中位 / P95 / 平均总收益'}：${[
      p05Return,
      medianReturn,
      p95Return,
      meanReturn,
    ].map((value) => pctLabel(value)).join(' / ')}`);
  }
  if (worstMaxDrawdown != null) lines.push(`  - ${language === 'en' ? 'Worst max drawdown' : '最差最大回撤'}：${drawdownPctLabel(worstMaxDrawdown)}`);
  if (simulationCount != null) lines.push(`  - ${language === 'en' ? 'Simulation count' : '模拟次数'}：${numberLabel(simulationCount, 0)}`);
  if (seed != null) lines.push(`  - ${language === 'en' ? 'Seed' : '随机种子'}：${numberLabel(seed, 0)}`);
  if (
    p05Return == null
    && medianReturn == null
    && p95Return == null
    && meanReturn == null
    && worstMaxDrawdown == null
    && simulationCount == null
    && seed == null
  ) {
    lines.push(`  - ${language === 'en' ? 'No distributable summary is available yet' : '当前结果未提供可展示的分布摘要。'}`);
  }

  const stressState = getRobustnessStateText(getObjectField(stressTests, 'state') ?? getObjectField(robustnessAnalysis, 'state'), language);
  const scenarioCount = getFiniteNumber(getObjectField(stressTests, 'scenarioCount'));
  const worstScenarioLabel = getStressScenarioFriendlyLabel(
    getObjectField(worstScenario, 'scenarioKey'),
    getObjectField(worstScenario, 'label'),
    language,
  );
  lines.push(language === 'en' ? '- Stress scenarios' : '- 压力场景');
  lines.push(`  - ${language === 'en' ? 'State' : '状态'}：${stressState}`);
  if (scenarioCount != null) lines.push(`  - ${language === 'en' ? 'Scenario count' : '场景数'}：${numberLabel(scenarioCount, 0)}`);
  if (scenarioCount != null && scenarioCount > 0) lines.push(`  - ${language === 'en' ? 'Worst scenario' : '最差场景'}：${worstScenarioLabel}`);

  const scenarioDetailLines = stressScenarios
    .map((scenario, index) => {
      const record = asObjectRecord(scenario);
      const metrics = asObjectRecord(getObjectField(record, 'metrics'));
      const totalReturn = getFiniteNumber(getObjectField(metrics, 'totalReturnPct'));
      const sharpe = getFiniteNumber(getObjectField(metrics, 'sharpeRatio'));
      const drawdown = getFiniteNumber(getObjectField(metrics, 'maxDrawdownPct'));
      const detailParts = [
        totalReturn != null ? `${language === 'en' ? 'return' : '收益'} ${pctLabel(totalReturn)}` : null,
        sharpe != null ? `Sharpe ${numberLabel(sharpe, 2)}` : null,
        drawdown != null ? `${language === 'en' ? 'drawdown' : '回撤'} ${drawdownPctLabel(drawdown)}` : null,
      ].filter(Boolean);
      if (detailParts.length === 0) return null;
      const label = getStressScenarioFriendlyLabel(
        getObjectField(record, 'scenarioKey'),
        getObjectField(record, 'label'),
        language,
        index,
      );
      return `  - ${label}：${detailParts.join(' · ')}`;
    })
    .filter((line): line is string => Boolean(line));

  if (scenarioDetailLines.length > 0) {
    lines.push(...scenarioDetailLines);
  } else {
    lines.push(`  - ${language === 'en' ? 'No stress detail is available yet' : '样本不足，暂无可展示的压力场景明细。'}`);
  }

  return lines;
}

export function describeRuleRunNarrative(
  run: Pick<RuleBacktestRunResponse, 'benchmarkMode' | 'benchmarkCode' | 'benchmarkReturnPct' | 'buyAndHoldReturnPct' | 'excessReturnVsBenchmarkPct' | 'excessReturnVsBuyAndHoldPct' | 'maxDrawdownPct' | 'tradeCount' | 'winRatePct' | 'avgTradeReturnPct' | 'code'>,
  language: BacktestLanguage = 'zh',
): RuleRunNarrative {
  const benchmarkMode = (run.benchmarkMode as Parameters<typeof getBenchmarkModeLabel>[0]) || 'auto';
  const benchmarkLabel = getBenchmarkModeLabel(benchmarkMode, run.code, run.benchmarkCode || undefined, language);
  const benchmarkDelta = asFiniteNumber(run.excessReturnVsBenchmarkPct);
  const buyHoldDelta = asFiniteNumber(run.excessReturnVsBuyAndHoldPct);
  const relativeDelta = benchmarkDelta ?? buyHoldDelta;
  const relativeTarget = benchmarkDelta != null ? benchmarkLabel : (language === 'en' ? 'hold reference' : '持有参照');
  let verdict = language === 'en' ? 'Near the benchmark' : '接近基准';
  if (relativeDelta != null) {
    if (relativeDelta >= 1) verdict = language === 'en' ? `Outperformed ${relativeTarget}` : `跑赢 ${relativeTarget}`;
    else if (relativeDelta <= -1) verdict = language === 'en' ? `Lagged ${relativeTarget}` : `落后于 ${relativeTarget}`;
  }

  const drawdownLabel = getDrawdownLabel(run.maxDrawdownPct, language);
  const activityLabel = getTradeActivityLabel(Number(run.tradeCount ?? 0), language);
  const qualityLabel = getQualityLabel(run, language);
  const deltaLabel = relativeDelta == null
    ? (language === 'en' ? 'No comparable benchmark is available yet' : '暂无可比较基准')
    : `${verdict} ${pctLabel(relativeDelta)}`;

  return {
    verdict,
    headline: language === 'en'
      ? `${deltaLabel}, with ${drawdownLabel.toLowerCase()} and a ${activityLabel.toLowerCase()} trading rhythm.`
      : `${deltaLabel}，${drawdownLabel}，${activityLabel}交易节奏。`,
    benchmarkLabel,
    drawdownLabel,
    activityLabel,
    qualityLabel,
    detail: language === 'en'
      ? [
        `Relative performance: ${deltaLabel}`,
        `Risk: ${drawdownLabel} (max drawdown ${pctLabel(run.maxDrawdownPct)})`,
        `Activity: ${activityLabel} (${run.tradeCount || 0} trades)`,
        `Quality: ${qualityLabel}`,
      ].join(' ')
      : [
        `相对表现：${deltaLabel}`,
        `风险：${drawdownLabel}（最大回撤 ${pctLabel(run.maxDrawdownPct)}）`,
        `活跃度：${activityLabel}（交易 ${run.tradeCount || 0} 次）`,
        `质量：${qualityLabel}`,
      ].join(' '),
  };
}

export function getRuleRunExecutionNotes(
  run: Pick<RuleBacktestRunResponse, 'executionTrace' | 'benchmarkSummary' | 'noResultMessage' | 'parsedStrategy' | 'warnings'>,
  language: BacktestLanguage = 'zh',
): string[] {
  const notes = [
    trimText(run.executionTrace?.fallback?.note) === '标准执行路径'
      ? (language === 'en' ? 'Standard execution path' : '标准执行路径')
      : trimText(run.executionTrace?.fallback?.note),
    trimText(run.executionTrace?.assumptionsDefaults?.summaryText),
    trimText(run.benchmarkSummary?.unavailableReason),
    trimText(run.noResultMessage) === '回测窗口内没有触发任何入场信号。'
      ? (language === 'en' ? 'No entry signal was triggered during the backtest window.' : '回测窗口内没有触发任何入场信号。')
      : trimText(run.noResultMessage),
    ...((run.parsedStrategy.parseWarnings || []).map((item) => trimText(item.message || item.reason || item.code))),
    ...((run.warnings || []).map((item) => trimText(item.message || item.reason || item.code))),
  ].filter(Boolean);

  return Array.from(new Set(notes)).slice(0, 4);
}

export function buildRuleRunComparisonWarnings(
  runs: Array<Pick<RuleBacktestRunResponse, 'startDate' | 'endDate' | 'lookbackBars' | 'feeBps' | 'slippageBps' | 'benchmarkMode' | 'benchmarkCode' | 'code' | 'parsedStrategy'>>,
  language: BacktestLanguage = 'zh',
): string[] {
  if (runs.length <= 1) return [];
  const warnings: string[] = [];
  const signatures = {
    dateRange: new Set(runs.map((run) => `${run.startDate || '--'}:${run.endDate || '--'}`)),
    costs: new Set(runs.map((run) => `${Number(run.feeBps ?? 0).toFixed(2)}:${Number(run.slippageBps ?? 0).toFixed(2)}`)),
    benchmark: new Set(runs.map((run) => `${run.benchmarkMode || 'auto'}:${run.benchmarkCode || ''}`)),
    lookback: new Set(runs.map((run) => String(run.lookbackBars || '--'))),
    family: new Set(runs.map((run) => getParsedStrategyFamily(run))),
  };

  if (signatures.dateRange.size > 1) warnings.push(language === 'en' ? 'Compared runs use different date windows, so return and drawdown are not perfectly side-by-side comparable.' : '比较项使用了不同日期区间，收益与回撤不完全可直接横比。');
  if (signatures.costs.size > 1) warnings.push(language === 'en' ? 'Compared runs use different fee or slippage assumptions, which can amplify net-return differences.' : '比较项的手续费或滑点假设不同，净收益差异会放大。');
  if (signatures.benchmark.size > 1) warnings.push(language === 'en' ? 'Compared runs use different benchmark settings, so excess return is only directly comparable under the same benchmark basis.' : '比较项使用了不同基准设置，超额收益只适合在相同基准下直接对照。');
  if (signatures.lookback.size > 1) warnings.push(language === 'en' ? 'Compared runs use different lookback warmup windows, which can change technical-signal initialization.' : '比较项的 lookback 初始化窗口不同，技术信号 warmup 结果可能不同。');
  if (signatures.family.size > 1) warnings.push(language === 'en' ? 'Compared runs span different strategy families, so they are better for style comparison than simple winner/loser judgments.' : '比较项跨了不同策略族，更适合看风格差异而不是只看单一胜负。');
  return warnings;
}

export function buildRuleRunReportMarkdown(args: {
  run: RuleBacktestRunResponse;
  normalized: DeterministicBacktestNormalizedResult;
  comparedRuns?: RuleBacktestRunResponse[];
  language?: BacktestLanguage;
}): string {
  const { run, normalized, comparedRuns = [], language = 'zh' } = args;
  const narrative = describeRuleRunNarrative(run, language);
  const setupHighlights = getRuleRunSetupHighlights(run, language);
  const executionNotes = getRuleRunExecutionNotes(run, language);
  const comparisonWarnings = buildRuleRunComparisonWarnings([run, ...comparedRuns], language);
  const comparedSummary = comparedRuns.length > 0
    ? comparedRuns.map((item) => {
      const label = `#${item.id} · ${getRuleStrategyTypeLabel(item.parsedStrategy, undefined, language)} · ${pctLabel(item.totalReturnPct)}`;
      return language === 'en'
        ? `- ${label} · Excess ${pctLabel(item.excessReturnVsBenchmarkPct ?? item.excessReturnVsBuyAndHoldPct)} · Drawdown ${pctLabel(item.maxDrawdownPct)}`
        : `- ${label} · 超额 ${pctLabel(item.excessReturnVsBenchmarkPct ?? item.excessReturnVsBuyAndHoldPct)} · 回撤 ${pctLabel(item.maxDrawdownPct)}`;
    }).join('\n')
    : (language === 'en' ? '- No additional comparison runs attached yet' : '- 暂未附加其他比较对象');
  const robustnessAppendix = buildRobustnessAppendix(run, language);
  const drawdownAttributionAppendix = buildDrawdownAttributionAppendix(run, language);

  return language === 'en' ? [
    `# Deterministic Backtest Summary #${run.id}`,
    '',
    `- Ticker: ${run.code}`,
    `- Strategy: ${getRuleStrategyTypeLabel(run.parsedStrategy, undefined, language)}`,
    `- Window: ${run.startDate || '--'} -> ${run.endDate || '--'}`,
    `- Benchmark: ${run.benchmarkSummary?.label || narrative.benchmarkLabel}`,
    `- Conclusion: ${narrative.headline}`,
    '',
    '## Decision summary',
    '',
    `- Total return: ${pctLabel(normalized.metrics.totalReturnPct)}`,
    `- Relative to benchmark: ${pctLabel(normalized.metrics.excessReturnVsBenchmarkPct ?? normalized.metrics.excessReturnVsBuyAndHoldPct)}`,
    `- Max drawdown: ${pctLabel(normalized.metrics.maxDrawdownPct)} (${narrative.drawdownLabel})`,
    `- Trades: ${normalized.metrics.tradeCount} (${narrative.activityLabel})`,
    `- Win rate: ${pctLabel(normalized.metrics.winRatePct)}`,
    `- Ending equity: ${moneyLabel(normalized.metrics.finalEquity)}`,
    '',
    '## Key setup',
    '',
    ...setupHighlights.map((item) => `- ${item}`),
    '',
    '## Execution and interpretation',
    '',
    ...(executionNotes.length > 0 ? executionNotes.map((item) => `- ${item}`) : ['- No extra execution notes']),
    '',
    '## Comparison reference',
    '',
    comparedSummary,
    '',
    ...(comparisonWarnings.length > 0
      ? [
        '## Comparison notes',
        '',
        ...comparisonWarnings.map((item) => `- ${item}`),
        '',
      ]
      : []),
    '## Deep data',
    '',
    '- The detailed execution trace still lives in CSV / JSON exports.',
    '- For chart interpretation, start with cumulative return, drawdown, and benchmark comparison.',
    ...(robustnessAppendix ? ['', ...robustnessAppendix] : []),
    '',
    ...drawdownAttributionAppendix,
  ].join('\n') : [
    `# 确定性回测决策摘要 #${run.id}`,
    '',
    `- 标的：${run.code}`,
    `- 策略：${getRuleStrategyTypeLabel(run.parsedStrategy)}`,
    `- 区间：${run.startDate || '--'} -> ${run.endDate || '--'}`,
    `- 基准：${run.benchmarkSummary?.label || narrative.benchmarkLabel}`,
    `- 结论：${narrative.headline}`,
    '',
    '## 决策摘要',
    '',
    `- 总收益：${pctLabel(normalized.metrics.totalReturnPct)}`,
    `- 相对基准：${pctLabel(normalized.metrics.excessReturnVsBenchmarkPct ?? normalized.metrics.excessReturnVsBuyAndHoldPct)}`,
    `- 最大回撤：${pctLabel(normalized.metrics.maxDrawdownPct)}（${narrative.drawdownLabel}）`,
    `- 交易次数：${normalized.metrics.tradeCount}（${narrative.activityLabel}）`,
    `- 胜率：${pctLabel(normalized.metrics.winRatePct)}`,
    `- 期末权益：${moneyLabel(normalized.metrics.finalEquity)}`,
    '',
    '## 关键配置',
    '',
    ...setupHighlights.map((item) => `- ${item}`),
    '',
    '## 执行与解释',
    '',
    ...(executionNotes.length > 0 ? executionNotes.map((item) => `- ${item}`) : ['- 暂无额外执行备注']),
    '',
    '## 对比参考',
    '',
    comparedSummary,
    '',
    ...(comparisonWarnings.length > 0
      ? [
        '## 比较提醒',
        '',
        ...comparisonWarnings.map((item) => `- ${item}`),
        '',
      ]
      : []),
    '## 深层数据',
    '',
    '- 详细执行轨迹仍以 CSV / JSON 导出为准。',
    '- 图表解读优先查看收益曲线、回撤曲线和基准对照。',
    ...(robustnessAppendix ? ['', ...robustnessAppendix] : []),
    '',
    ...drawdownAttributionAppendix,
  ].join('\n');
}

export function createRuleBacktestPresetFromRun(
  run: Pick<RuleBacktestRunResponse, 'id' | 'code' | 'strategyText' | 'startDate' | 'endDate' | 'lookbackBars' | 'initialCapital' | 'feeBps' | 'slippageBps' | 'benchmarkMode' | 'benchmarkCode' | 'parsedStrategy'>,
  options?: { kind?: 'saved' | 'recent'; name?: string },
): RuleBacktestPreset {
  const kind = options?.kind || 'saved';
  const familyLabel = getRuleStrategyTypeLabel(run.parsedStrategy);
  return {
    id: `${kind}-${run.id ?? 'draft'}-${Date.now()}`,
    kind,
    name: trimText(options?.name) || `${run.code} · ${familyLabel}`,
    savedAt: new Date().toISOString(),
    sourceRunId: run.id ?? null,
    code: run.code,
    strategyText: run.strategyText,
    startDate: run.startDate || '',
    endDate: run.endDate || '',
    lookbackBars: String(run.lookbackBars ?? 252),
    initialCapital: String(run.initialCapital ?? 100000),
    feeBps: String(run.feeBps ?? 0),
    slippageBps: String(run.slippageBps ?? 0),
    benchmarkMode: run.benchmarkMode || 'auto',
    benchmarkCode: run.benchmarkCode || '',
  };
}

export function loadRuleBacktestPresets(): RuleBacktestPreset[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(RULE_BACKTEST_PRESET_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((item): item is RuleBacktestPreset => Boolean(item && typeof item === 'object' && item.id))
      .sort((left, right) => String(right.savedAt || '').localeCompare(String(left.savedAt || '')));
  } catch {
    return [];
  }
}

function persistRuleBacktestPresets(items: RuleBacktestPreset[]): RuleBacktestPreset[] {
  const saved = items.filter((item) => item.kind === 'saved').slice(0, MAX_SAVED_PRESETS);
  const recent = items.filter((item) => item.kind === 'recent').slice(0, MAX_RECENT_PRESETS);
  const next = [...saved, ...recent].sort((left, right) => String(right.savedAt || '').localeCompare(String(left.savedAt || '')));
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(RULE_BACKTEST_PRESET_STORAGE_KEY, JSON.stringify(next));
  }
  return next;
}

export function saveRuleBacktestPreset(preset: RuleBacktestPreset): RuleBacktestPreset[] {
  const existing = loadRuleBacktestPresets();
  const filtered = existing.filter((item) => item.id !== preset.id);
  if (preset.kind === 'recent') {
    const signature = `${preset.code}:${preset.strategyText}:${preset.startDate}:${preset.endDate}:${preset.lookbackBars}:${preset.initialCapital}:${preset.feeBps}:${preset.slippageBps}:${preset.benchmarkMode}:${preset.benchmarkCode}`;
    const deduped = filtered.filter((item) => {
      if (item.kind !== 'recent') return true;
      const itemSignature = `${item.code}:${item.strategyText}:${item.startDate}:${item.endDate}:${item.lookbackBars}:${item.initialCapital}:${item.feeBps}:${item.slippageBps}:${item.benchmarkMode}:${item.benchmarkCode}`;
      return itemSignature !== signature;
    });
    return persistRuleBacktestPresets([preset, ...deduped]);
  }
  return persistRuleBacktestPresets([preset, ...filtered]);
}

export function deleteRuleBacktestPreset(presetId: string): RuleBacktestPreset[] {
  const existing = loadRuleBacktestPresets();
  return persistRuleBacktestPresets(existing.filter((item) => item.id !== presetId));
}

function createScenarioRequest(
  run: RuleBacktestRunResponse,
  label: string,
  overrides: Partial<RuleBacktestRunRequest>,
  parsedStrategyOverride?: RuleBacktestRunRequest['parsedStrategy'],
): RuleScenarioVariant {
  const strategyText = trimText(overrides.strategyText) || `${run.strategyText}\n[P6 variant] ${label}`;
  return {
    id: label.toLowerCase().replace(/\s+/g, '-'),
    label,
    description: trimText(overrides.strategyText) || label,
    request: {
      code: run.code,
      strategyText,
      parsedStrategy: parsedStrategyOverride ?? cloneJson(run.parsedStrategy),
      startDate: run.startDate || undefined,
      endDate: run.endDate || undefined,
      lookbackBars: overrides.lookbackBars ?? run.lookbackBars,
      initialCapital: overrides.initialCapital ?? run.initialCapital,
      feeBps: overrides.feeBps ?? run.feeBps,
      slippageBps: overrides.slippageBps ?? run.slippageBps,
      benchmarkMode: overrides.benchmarkMode ?? run.benchmarkMode ?? 'auto',
      benchmarkCode: overrides.benchmarkCode ?? run.benchmarkCode ?? undefined,
      confirmed: true,
      waitForCompletion: false,
    },
  };
}

function withUpdatedParsedStrategy(
  run: RuleBacktestRunResponse,
  updater: (spec: Record<string, unknown>) => void,
  textSuffix: string,
): RuleScenarioVariant | null {
  const parsedStrategy = cloneJson(run.parsedStrategy);
  const spec = getRuleStrategySpec(parsedStrategy);
  if (!spec) return null;
  updater(spec);
  parsedStrategy.strategySpec = spec;
  return createScenarioRequest(run, textSuffix, {
    strategyText: `${run.strategyText}\n[P6 variant] ${textSuffix}`,
  }, parsedStrategy);
}

export function getRuleScenarioPlans(run: RuleBacktestRunResponse): RuleScenarioPlan[] {
  const plans: RuleScenarioPlan[] = [];
  const autoBenchmarkMode = getAutoBenchmarkMode(run.code);
  const benchmarkVariants = dedupeVariants([
    createScenarioRequest(run, 'Auto Benchmark', { benchmarkMode: 'auto', benchmarkCode: undefined }),
    createScenarioRequest(run, 'No Benchmark', { benchmarkMode: 'none', benchmarkCode: undefined }),
    createScenarioRequest(run, 'Hold Reference Benchmark', { benchmarkMode: 'same_symbol_buy_and_hold', benchmarkCode: undefined }),
    createScenarioRequest(run, 'Market Benchmark', {
      benchmarkMode: autoBenchmarkMode,
      benchmarkCode: undefined,
    }),
  ]).filter((item) => item.request.benchmarkMode !== run.benchmarkMode || (item.request.benchmarkCode || '') !== (run.benchmarkCode || ''));

  if (benchmarkVariants.length > 0) {
    plans.push({
      id: 'benchmark_modes',
      label: '基准情景',
      description: '快速比较当前策略在不同 benchmark context 下的超额表现。',
      variants: benchmarkVariants.slice(0, 3),
    });
  }

  plans.push({
    id: 'cost_stress',
    label: '费用/滑点压力',
    description: '对同一策略做轻量摩擦压力测试，观察净收益对成本的敏感度。',
    variants: dedupeVariants([
      createScenarioRequest(run, 'Base Cost', {}),
      createScenarioRequest(run, 'Cost +5bp', {
        feeBps: Number(run.feeBps ?? 0) + 5,
        slippageBps: Number(run.slippageBps ?? 0) + 5,
      }),
      createScenarioRequest(run, 'Cost +10bp', {
        feeBps: Number(run.feeBps ?? 0) + 10,
        slippageBps: Number(run.slippageBps ?? 0) + 10,
      }),
    ]).filter((item) => !(item.request.feeBps === run.feeBps && item.request.slippageBps === run.slippageBps)).slice(0, 2),
  });

  plans.push({
    id: 'lookback_window',
    label: 'Lookback 窗口',
    description: '用更短/更长 warmup 窗口验证策略初始化对结果的影响。',
    variants: dedupeVariants([
      createScenarioRequest(run, 'Lookback 126', { lookbackBars: Math.max(63, Math.min(126, run.lookbackBars)) }),
      createScenarioRequest(run, `Lookback ${run.lookbackBars + 126}`, { lookbackBars: run.lookbackBars + 126 }),
    ]).filter((item) => item.request.lookbackBars !== run.lookbackBars).slice(0, 2),
  });

  const family = getParsedStrategyFamily(run);
  if (family === 'moving_average_crossover') {
    const maFastVariant = withUpdatedParsedStrategy(run, (spec) => {
      const currentFast = asFiniteNumber(getStrategySpecValue(spec, ['signal', 'fast_period'])) ?? 5;
      const currentSlow = asFiniteNumber(getStrategySpecValue(spec, ['signal', 'slow_period'])) ?? 20;
      const nextFast = Math.max(2, currentFast - 2);
      const nextSlow = Math.max(nextFast + 3, currentSlow - 5);
      if (spec.signal && typeof spec.signal === 'object') {
        (spec.signal as Record<string, unknown>).fast_period = nextFast;
        (spec.signal as Record<string, unknown>).slow_period = nextSlow;
      }
    }, 'MA Faster');
    const maSlowVariant = withUpdatedParsedStrategy(run, (spec) => {
      const currentFast = asFiniteNumber(getStrategySpecValue(spec, ['signal', 'fast_period'])) ?? 5;
      const currentSlow = asFiniteNumber(getStrategySpecValue(spec, ['signal', 'slow_period'])) ?? 20;
      if (spec.signal && typeof spec.signal === 'object') {
        (spec.signal as Record<string, unknown>).fast_period = currentFast + 2;
        (spec.signal as Record<string, unknown>).slow_period = currentSlow + 5;
      }
    }, 'MA Slower');
    const variants = [maFastVariant, maSlowVariant].filter((item): item is RuleScenarioVariant => Boolean(item));
    if (variants.length > 0) {
      plans.push({
        id: 'ma_window_variants',
        label: '均线窗口变体',
        description: '围绕当前 fast/slow window 生成两组轻量 MA 变体，便于快速做 first-step iteration。',
        variants: dedupeVariants(variants),
      });
    }
  } else if (family === 'macd_crossover') {
    const fastVariant = withUpdatedParsedStrategy(run, (spec) => {
      if (spec.signal && typeof spec.signal === 'object') {
        const signal = spec.signal as Record<string, unknown>;
        signal.fast_period = 8;
        signal.slow_period = 21;
        signal.signal_period = 5;
      }
    }, 'MACD Fast');
    const slowVariant = withUpdatedParsedStrategy(run, (spec) => {
      if (spec.signal && typeof spec.signal === 'object') {
        const signal = spec.signal as Record<string, unknown>;
        signal.fast_period = 15;
        signal.slow_period = 30;
        signal.signal_period = 9;
      }
    }, 'MACD Slow');
    const variants = [fastVariant, slowVariant].filter((item): item is RuleScenarioVariant => Boolean(item));
    if (variants.length > 0) {
      plans.push({
        id: 'macd_signal_variants',
        label: 'MACD 参数变体',
        description: '固定策略结构，只比较更快/更慢的一组 MACD 周期组合。',
        variants: dedupeVariants(variants),
      });
    }
  } else if (family === 'rsi_threshold') {
    const aggressiveVariant = withUpdatedParsedStrategy(run, (spec) => {
      if (spec.signal && typeof spec.signal === 'object') {
        const signal = spec.signal as Record<string, unknown>;
        signal.period = 10;
        signal.lower_threshold = 35;
        signal.upper_threshold = 65;
      }
    }, 'RSI Aggressive');
    const patientVariant = withUpdatedParsedStrategy(run, (spec) => {
      if (spec.signal && typeof spec.signal === 'object') {
        const signal = spec.signal as Record<string, unknown>;
        signal.period = 18;
        signal.lower_threshold = 25;
        signal.upper_threshold = 75;
      }
    }, 'RSI Patient');
    const variants = [aggressiveVariant, patientVariant].filter((item): item is RuleScenarioVariant => Boolean(item));
    if (variants.length > 0) {
      plans.push({
        id: 'rsi_threshold_variants',
        label: 'RSI 阈值变体',
        description: '比较更激进与更耐心的 RSI 触发区间。',
        variants: dedupeVariants(variants),
      });
    }
  }

  return plans.filter((plan) => plan.variants.length > 0);
}
