import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, BarChart3, ChevronDown, Layers3, LineChart, Search, ShieldCheck } from 'lucide-react';
import {
  optionsLabApi,
  type OptionContract,
  type OptionsDecisionResponse,
  type OptionsChainResponse,
  type OptionsDirection,
  type OptionsExpiration,
  type OptionsExpirationsResponse,
  type OptionsRiskProfile,
  type OptionsStrategyCompareResponse,
  type OptionsStrategyComparison,
  type OptionsStrategyType,
  type OptionsUnderlyingSummaryResponse,
} from '../api/optionsLab';
import {
  CompactFilterBar,
  ConsoleDisclosure,
  DataWorkbenchFrame,
  DenseRows,
  WolfyShellSurface,
} from '../components/linear';
import {
  TerminalButton,
  TerminalChip,
  TerminalEmptyState,
  TerminalNotice,
  TerminalPageHeading,
  TerminalPageShell,
  TerminalSectionHeader,
} from '../components/terminal';
import { ConsumerWorkspacePageShell, ConsumerWorkspaceScope } from '../components/layout/ConsumerWorkspaceShell';
import { cn } from '../utils/cn';
import { normalizeOptionsEvidence } from '../utils/evidenceDisplay';
import { formatNumber, formatPercent } from '../utils/format';

type LoadState = {
  loading: boolean;
  error: string | null;
  summary: OptionsUnderlyingSummaryResponse | null;
  expirations: OptionsExpirationsResponse | null;
  chain: OptionsChainResponse | null;
};

type ComparisonState = {
  loading: boolean;
  error: string | null;
  comparison: OptionsStrategyCompareResponse | null;
};

type DecisionState = {
  loading: boolean;
  error: string | null;
  decision: OptionsDecisionResponse | null;
};

const DIRECTION_OPTIONS: Array<{ value: OptionsDirection; label: string }> = [
  { value: 'bullish', label: '上涨情景' },
  { value: 'bearish', label: '下跌情景' },
  { value: 'neutral', label: '区间情景' },
  { value: 'volatility', label: '波动扩张' },
];

const RISK_PROFILE_OPTIONS: Array<{ value: OptionsRiskProfile; label: string }> = [
  { value: 'conservative', label: '保守' },
  { value: 'balanced', label: '均衡' },
  { value: 'aggressive', label: '进取' },
];

const EMPTY_CONTRACTS: OptionContract[] = [];
const EMPTY_EXPIRATIONS: OptionsExpiration[] = [];
const COMPARISON_LOADING_TIMEOUT_MS = 12000;
const COMPARISON_EMPTY_MESSAGE = '先选择可用到期日并加载合约后，再进入策略对比。';
const OPTIONS_LAB_CRASH_FALLBACK = '期权实验室暂时无法加载，请刷新或稍后重试。';
const OPTIONS_MODULE_PAUSED_COPY = '期权数据暂不可用，本模块已暂停生成策略。';
const OPTIONS_INSUFFICIENT_COPY = '当前期权信号数据不足，仅供观察。';
const OPTIONS_UPDATING_COPY = '数据更新中，稍后将自动刷新。';
const OPTIONS_UNAVAILABLE_COPY = '本模块暂不可用，请稍后重试。';
const OPTIONS_DEMO_BOUNDARY_COPY = '演示数据：当前数据延迟，仅用于界面与情景验证，不可用于真实交易判断。';

const fieldShellClass = 'group flex min-h-[4rem] min-w-0 flex-col justify-center gap-1.5 rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[color:color-mix(in_srgb,var(--wolfy-surface-input)_92%,transparent)] px-3 py-2 transition-colors focus-within:border-[color:var(--wolfy-accent)]';
const fieldClass = 'h-6 w-full border-0 bg-transparent p-0 font-mono text-sm text-[color:var(--wolfy-text-primary)] outline-none placeholder:text-[color:var(--wolfy-text-muted)]';
const labelClass = 'text-[10px] font-bold uppercase tracking-[0.18em] text-[color:var(--wolfy-text-muted)]';
const panelClass = 'min-w-0 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-4 md:p-5';
const innerBlockClass = 'rounded-md border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)]';

function money(value?: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '--';
  return `$${formatNumber(value, 2)}`;
}

function ratio(value?: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '--';
  return formatPercent(value, { digits: 1, mode: value > 1 ? 'percent' : 'ratio' });
}

function number(value?: number | null, digits = 0): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '--';
  return formatNumber(value, digits);
}

function asArray<T>(value: T[] | null | undefined): T[] {
  return Array.isArray(value) ? value : [];
}

function recordValue(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function gateIssueReasonValues(value: unknown): string[] {
  if (typeof value === 'string') return [value];
  if (Array.isArray(value)) return value.flatMap(gateIssueReasonValues);

  const issue = recordValue(value);
  if (!issue) return [];

  return [issue.code, issue.label]
    .filter((item): item is string => typeof item === 'string' && item.trim().length > 0);
}

function limitationLabel(value: string): string {
  if (value === 'provider_validation_required') return '数据待验证';
  if (value === 'mocked_frontend_shell') return '浏览器验证数据';
  if (value === 'mocked_chain') return '演示链';
  if (value === 'mock') return '演示数据';
  if (value === 'fixture') return '本地验证数据';
  if (value === 'wide_spread_watch') return '价差观察';
  if (value === 'low_oi_watch') return 'OI 偏低';
  if (value === 'fixture_backed_defined_risk_only') return '本地定义风险模型';
  if (value === 'analytical_only_not_advice') return '仅供情景分析';
  if (value === 'thin_liquidity_in_one_or_more_legs') return '至少一腿流动性偏薄';
  if (value === 'wide_bid_ask_spread_in_one_or_more_legs') return '至少一腿买卖价差偏宽';
  if (value === 'iv_and_theta_can_change_strategy_value_before_expiration') return 'IV 与 Theta 会改变到期前估值';
  if (value === 'high_implied_volatility_in_one_or_more_legs') return '至少一腿隐含波动率偏高';
  if (value === 'comparison_uses_user_assumptions_and_fixture_mid_prices') return '使用用户假设与中间价估算';
  if (value === 'defined_risk_debit_spread_caps_loss_and_gain') return '借方价差同时限制亏损与收益';
  if (value === 'direction_assumption_bullish') return '方向假设：看涨';
  if (value === 'direction_assumption_bearish') return '方向假设：看跌';
  if (value === 'direction_assumption_neutral') return '方向假设：中性';
  if (value === 'direction_assumption_volatility') return '方向假设：波动';
  if (value === 'risk_profile_conservative') return '风险偏好：保守';
  if (value === 'risk_profile_balanced') return '风险偏好：均衡';
  if (value === 'risk_profile_aggressive') return '风险偏好：进取';
  return '部分外部数据暂不可用';
}

function strategyLabel(value: OptionsStrategyType): string {
  const labels: Record<OptionsStrategyType, string> = {
    long_call: 'Call 多头',
    long_put: 'Put 多头',
    bull_call_spread: 'Call 借方价差',
    bear_put_spread: 'Put 借方价差',
  };
  return labels[value];
}

function strategyChineseLabel(value: OptionsStrategyType): string {
  const labels: Record<OptionsStrategyType, string> = {
    long_call: '看涨期权多头',
    long_put: '看跌期权多头',
    bull_call_spread: '牛市看涨价差',
    bear_put_spread: '熊市看跌价差',
  };
  return labels[value];
}

function warningLabel(value: string): string {
  if (value.includes('synthetic delayed')) return '当前为演示/延迟数据';
  if (value === 'expected_move_uses_fixture_mid_prices') return '预期波动使用延迟中间价估算';
  if (value === 'expected_move_unavailable') return '预期波动暂不可用';
  if (value === 'expected_move_unavailable_degrade_confidence') return '预期波动缺失降低可信度';
  if (value === 'iv_rank_unavailable_degrade_confidence') return 'IV 分位缺失降低可信度';
  if (value === 'wide_bid_ask_spread') return '买卖价差过宽';
  if (value === 'missing_greeks') return '敏感度缺失';
  if (value === 'missing_greeks_degrade_confidence') return '敏感度缺失降低可信度';
  if (value.includes('Greeks 缺失')) return '敏感度缺失，无法评估时间价值与敏感度';
  if (value === 'low_or_missing_volume') return '成交量不足或缺失';
  if (value === 'low_or_missing_open_interest') return 'OI 不足或缺失';
  if (value === 'breakeven_requires_large_underlying_move') return '盈亏平衡需要较大标的波动';
  if (value === 'max_gain_not_defined_for_long_option') return '单腿多头收益边界不固定';
  if (value === 'iv_rank_unavailable') return 'IV 分位不可用';
  if (value === 'synthetic_or_fixture_data_not_decision_grade') return '演示数据不可用于真实判断';
  if (value === '不可作为交易信号') return '不可作为交易信号';
  if (value === '不可用于真实交易判断') return '不可作为交易信号';
  if (value === '需人工复核') return '需人工复核';
  return limitationLabel(value);
}

function gateRecord(value?: OptionsDecisionResponse['dataQualityGates'] | OptionsDecisionResponse['liquidityGates']): Record<string, unknown> | null {
  return value && typeof value === 'object' ? value as Record<string, unknown> : null;
}

function gateStatus(value?: OptionsDecisionResponse['dataQualityGates'] | OptionsDecisionResponse['liquidityGates']): string | null {
  const status = gateRecord(value)?.status;
  return typeof status === 'string' ? status : null;
}

function gateBoolean(record: Record<string, unknown> | null, key: string): boolean | null {
  const value = record?.[key];
  return typeof value === 'boolean' ? value : null;
}

function gateReasonSummary(value: string): string | null {
  if (!value) return null;
  if (
    value === 'synthetic_or_fixture_data_not_decision_grade'
    || value.includes('synthetic delayed')
    || value.includes('演示数据')
  ) return '演示/延迟数据';
  if (
    value === 'wide_bid_ask_spread'
    || value === 'wide_bid_ask_spread_in_one_or_more_legs'
    || value === 'wide_spread_watch'
    || value.includes('价差')
  ) return '价差偏宽';
  if (
    value === 'thin_liquidity_in_one_or_more_legs'
    || value === 'low_or_missing_open_interest'
    || value === 'low_or_missing_volume'
    || value === 'liquidity_below_threshold'
    || value === 'low_oi_watch'
  ) return '成交深度不足';
  if (
    value === 'missing_greeks'
    || value === 'missing_greeks_degrade_confidence'
    || value === 'iv_rank_unavailable'
    || value === 'iv_rank_unavailable_degrade_confidence'
    || value === 'expected_move_unavailable'
    || value === 'expected_move_unavailable_degrade_confidence'
  ) return '关键信号不完整';
  if (value === 'provider_validation_required') return '数据待验证';
  if (value === '需人工复核') return '仍需人工复核';
  if (value === '不可作为交易信号' || value === '不可用于真实交易判断') return '仅观察';
  if (value === 'data_quality_not_decision_grade') return '数据质量受限';

  const label = warningLabel(value);
  return label === '部分外部数据暂不可用' ? '部分外部数据暂不可用' : label;
}

type ReadinessChip = {
  label: string;
  tone: 'neutral' | 'info' | 'warn' | 'risk' | 'good';
};

function readinessDecisionChip(decision?: OptionsDecisionResponse | null): ReadinessChip {
  if (decision?.decisionGrade === true && decision?.gateDecision !== 'blocked') {
    return { label: '通过基础门控', tone: 'good' };
  }
  if (isNonDecisionGrade(decision)) {
    return { label: '未达判断等级', tone: 'risk' };
  }
  return { label: '仅观察', tone: 'warn' };
}

function readinessObservationChip(decision?: OptionsDecisionResponse | null): ReadinessChip {
  return decision?.decisionGrade === true && decision?.gateDecision !== 'blocked'
    ? { label: '仍需人工复核', tone: 'warn' }
    : { label: '仅观察', tone: 'warn' };
}

function readinessDataChip(decision?: OptionsDecisionResponse | null): ReadinessChip {
  const gates = gateRecord(decision?.dataQualityGates);
  const status = gateStatus(decision?.dataQualityGates);
  const gateDecisionGrade = gateBoolean(gates, 'decisionGrade');
  const tier = typeof gates?.tier === 'string' ? gates.tier : decision?.dataQuality?.dataQualityTier;
  const restricted = status === 'blocked'
    || status === 'restricted'
    || gateDecisionGrade === false
    || tier === 'synthetic_demo_only'
    || tier === 'insufficient'
    || decision?.decisionGrade === false;
  return restricted
    ? { label: '数据质量受限', tone: 'risk' }
    : { label: '数据质量通过', tone: 'good' };
}

function readinessLiquidityChip(decision?: OptionsDecisionResponse | null): ReadinessChip {
  const gates = gateRecord(decision?.liquidityGates);
  const status = gateStatus(decision?.liquidityGates);
  const passed = gateBoolean(gates, 'passed');
  const scoreValue = typeof gates?.liquidityScore === 'number'
    ? gates.liquidityScore
    : decision?.liquidity?.liquidityScore;
  const restricted = status === 'blocked'
    || status === 'restricted'
    || passed === false
    || asArray(decision?.liquidity?.liquidityWarnings).length > 0
    || (typeof scoreValue === 'number' && scoreValue < 60);
  return restricted
    ? { label: '流动性受限', tone: 'warn' }
    : { label: '流动性通过', tone: 'good' };
}

function readinessReasonSummaries(decision?: OptionsDecisionResponse | null): string[] {
  const summaries = [
    ...asArray(decision?.failClosedReasonCodes),
    ...gateIssueReasonValues(decision?.gateIssues),
  ]
    .map(gateReasonSummary)
    .filter((value): value is string => Boolean(value));
  return [...new Set(summaries)].slice(0, 2);
}

const ReadinessGateStrip: React.FC<{
  decision?: OptionsDecisionResponse | null;
  testId?: string;
  className?: string;
}> = ({ decision, testId, className }) => {
  if (!decision) return null;

  const chips = [
    readinessDecisionChip(decision),
    readinessObservationChip(decision),
    readinessDataChip(decision),
    readinessLiquidityChip(decision),
  ];
  const reasonSummaries = readinessReasonSummaries(decision);

  return (
    <div
      data-testid={testId}
      className={cn(
        'rounded-md border border-[color:var(--wolfy-divider)] bg-[color:color-mix(in_srgb,var(--wolfy-surface-input)_88%,transparent)] px-3 py-2',
        className,
      )}
    >
      <div className="flex flex-wrap gap-2">
        {chips.map((chip) => (
          <Pill key={chip.label} tone={chip.tone}>{chip.label}</Pill>
        ))}
      </div>
      {reasonSummaries.length ? (
        <p className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">
          {reasonSummaries.join(' · ')}
        </p>
      ) : null}
    </div>
  );
};

function dataTierLabel(value?: string | null): string {
  if (value === 'live_usable') return '数据门控通过';
  if (value === 'delayed_usable') return '行情延迟，可观察';
  if (value === 'synthetic_demo_only') return '演示/延迟数据';
  if (value === 'insufficient') return '数据不足';
  return '--';
}

function freshnessLabel(value?: string | null): string {
  if (value === 'live') return '数据标记：实时';
  if (value === 'mock') return '演示/延迟数据';
  if (value === 'synthetic_delayed') return '演示/延迟数据';
  if (value === 'fixture') return '浏览器验证数据';
  return value ? limitationLabel(value) : '--';
}

function expectedMoveSourceLabel(value?: string | null): string {
  if (value === 'straddle_mid') return '平值跨式中间价';
  if (value === 'iv_dte') return 'IV / DTE';
  if (value === 'unavailable') return '不可用';
  return '--';
}

function noTradeReasonLabel(value?: string | null): string {
  if (value === 'data_quality_not_decision_grade') return '数据质量未达到可判断等级';
  if (value === 'all_candidates_have_weak_edge_or_unfavorable_risk_reward') return '候选结构边际优势或风险回报不足';
  if (value === 'no_supported_strategy_candidates') return '暂无可比较候选结构';
  return value ? limitationLabel(value) : '暂无';
}

function isNonDecisionGrade(decision?: OptionsDecisionResponse | null): boolean {
  if (!decision) return false;
  return decision.decisionGrade === false
    || decision.gateDecision === 'blocked'
    || asArray(decision.failClosedReasonCodes).length > 0
    || decision.dataQuality?.dataQualityTier === 'synthetic_demo_only'
    || decision.dataQuality?.dataQualityTier === 'insufficient';
}

function isDemoOrDelayedDecision(decision?: OptionsDecisionResponse | null): boolean {
  const freshness = decision?.freshness?.freshness;
  const tier = decision?.dataQuality?.dataQualityTier;
  return freshness === 'synthetic_delayed'
    || freshness === 'mock'
    || freshness === 'delayed'
    || tier === 'synthetic_demo_only'
    || tier === 'delayed_usable';
}

function observationBoundaryCopy(decision?: OptionsDecisionResponse | null): string | null {
  if (isNonDecisionGrade(decision)) return '未达到可判断等级，仅供情景观察，不可作为交易信号。';
  if (isDemoOrDelayedDecision(decision)) return OPTIONS_DEMO_BOUNDARY_COPY;
  return null;
}

type ConsumerAvailabilityTone = 'neutral' | 'info' | 'warn' | 'risk' | 'good';

type ConsumerAvailabilitySummary = {
  stateLabel: string;
  stateTone: ConsumerAvailabilityTone;
  confidenceLabel: string;
  confidenceTone: ConsumerAvailabilityTone;
  freshnessLabel: string;
  explanation: string;
};

function lastUpdatedLabel(value?: string | null): string {
  return value ? `最后更新：${value}` : '等待更新';
}

function consumerFreshnessLabel(
  summary: OptionsUnderlyingSummaryResponse | null,
  chain: OptionsChainResponse | null,
  decision: OptionsDecisionResponse | null,
): string {
  const updatedAt = decision?.freshness?.asOf
    || chain?.chainAsOf
    || chain?.underlying?.asOf
    || summary?.underlying?.asOf
    || summary?.metadata?.updatedAt;
  return lastUpdatedLabel(updatedAt);
}

function consumerAvailabilitySummary(
  loadState: Pick<LoadState, 'loading' | 'error' | 'summary' | 'chain'>,
  comparisonState: Pick<ComparisonState, 'loading' | 'error'>,
  decisionState: Pick<DecisionState, 'loading' | 'error' | 'decision'>,
  hasChainRows: boolean,
): ConsumerAvailabilitySummary {
  const freshness = consumerFreshnessLabel(loadState.summary, loadState.chain, decisionState.decision);

  if (loadState.loading || comparisonState.loading || decisionState.loading) {
    return {
      stateLabel: 'UPDATING',
      stateTone: 'info',
      confidenceLabel: '置信度更新中',
      confidenceTone: 'info',
      freshnessLabel: freshness,
      explanation: OPTIONS_UPDATING_COPY,
    };
  }

  if (loadState.error) {
    return {
      stateLabel: 'PAUSED',
      stateTone: 'risk',
      confidenceLabel: '不可判断',
      confidenceTone: 'risk',
      freshnessLabel: freshness,
      explanation: OPTIONS_MODULE_PAUSED_COPY,
    };
  }

  const decision = decisionState.decision;
  const tier = decision?.dataQuality?.dataQualityTier;
  const confidenceCap = normalizeOptionsEvidence(decision)?.confidenceCap;

  if (decisionState.error) {
    return {
      stateLabel: hasChainRows ? 'PARTIAL' : 'UNAVAILABLE',
      stateTone: hasChainRows ? 'warn' : 'risk',
      confidenceLabel: '有限置信度',
      confidenceTone: 'warn',
      freshnessLabel: freshness,
      explanation: hasChainRows ? OPTIONS_INSUFFICIENT_COPY : OPTIONS_UNAVAILABLE_COPY,
    };
  }

  if (!hasChainRows || tier === 'insufficient') {
    return {
      stateLabel: 'INSUFFICIENT',
      stateTone: 'warn',
      confidenceLabel: '有限置信度',
      confidenceTone: 'warn',
      freshnessLabel: freshness,
      explanation: OPTIONS_INSUFFICIENT_COPY,
    };
  }

  if (isNonDecisionGrade(decision)) {
    return {
      stateLabel: tier === 'synthetic_demo_only' ? 'PAUSED' : 'PARTIAL',
      stateTone: 'warn',
      confidenceLabel: '有限置信度',
      confidenceTone: 'warn',
      freshnessLabel: freshness,
      explanation: tier === 'synthetic_demo_only' ? OPTIONS_MODULE_PAUSED_COPY : OPTIONS_INSUFFICIENT_COPY,
    };
  }

  if (!decision) {
    return {
      stateLabel: 'PARTIAL',
      stateTone: 'warn',
      confidenceLabel: '置信度待确认',
      confidenceTone: 'warn',
      freshnessLabel: freshness,
      explanation: OPTIONS_INSUFFICIENT_COPY,
    };
  }

  return {
    stateLabel: tier === 'delayed_usable' ? 'PARTIAL' : 'AVAILABLE',
    stateTone: tier === 'delayed_usable' ? 'warn' : 'good',
    confidenceLabel: confidenceCap != null ? `有限置信度 ${confidenceCap}` : '置信度可用',
    confidenceTone: confidenceCap != null ? 'warn' : 'good',
    freshnessLabel: freshness,
    explanation: tier === 'delayed_usable' ? '已使用最近一次可用数据。' : '当前期权信号可用于只读情景观察。',
  };
}

function metricTone(value?: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'text-[color:var(--wolfy-text-secondary)]';
  if (value > 0) return 'text-[color:var(--wolfy-market-up)]';
  if (value < 0) return 'text-[color:var(--wolfy-market-down)]';
  return 'text-[color:var(--wolfy-text-secondary)]';
}

const Pill: React.FC<{ children: React.ReactNode; tone?: 'neutral' | 'info' | 'warn' | 'risk' | 'good' }> = ({ children, tone = 'neutral' }) => {
  const variant = {
    neutral: 'neutral',
    info: 'info',
    warn: 'caution',
    risk: 'danger',
    good: 'success',
  }[tone] as React.ComponentProps<typeof TerminalChip>['variant'];
  return (
    <TerminalChip variant={variant} className="font-mono tracking-tight">
      {children}
    </TerminalChip>
  );
};

const SectionHeader: React.FC<{
  eyebrow: string;
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  children?: React.ReactNode;
}> = ({ eyebrow, title, icon: Icon, children }) => (
  <TerminalSectionHeader
    eyebrow={(
      <span className="inline-flex items-center gap-2">
        <Icon className="h-4 w-4 text-[color:var(--wolfy-accent)]" aria-hidden="true" />
        <span>{eyebrow}</span>
      </span>
    )}
    title={title}
    action={children}
  />
);

const SegmentedButtons = <T extends string>({
  options,
  value,
  onChange,
  ariaLabel,
}: {
  options: Array<{ value: T; label: string }>;
  value: T;
  onChange: (value: T) => void;
  ariaLabel: string;
}) => (
  <div className="mt-1 grid grid-cols-2 gap-2 rounded-md border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] p-1 sm:grid-cols-4" aria-label={ariaLabel}>
    {options.map((option) => (
      <button
        key={option.value}
        className={cn(
          'h-9 rounded-md px-3 text-sm font-medium transition-colors',
          option.value === value
            ? 'border border-[color:var(--wolfy-accent)] bg-[color:color-mix(in_srgb,var(--wolfy-accent)_12%,transparent)] text-[color:var(--wolfy-text-primary)]'
            : 'border border-transparent bg-transparent text-[color:var(--wolfy-text-muted)] hover:bg-[var(--wolfy-surface-console)] hover:text-[color:var(--wolfy-text-secondary)]',
        )}
        type="button"
        onClick={() => onChange(option.value)}
      >
        {option.label}
      </button>
    ))}
  </div>
);

const AssumptionPanel: React.FC<{
  symbol: string;
  direction: OptionsDirection;
  riskProfile: OptionsRiskProfile;
  targetPrice: string;
  targetDate: string;
  riskBudget: string;
  expirations: OptionsExpiration[];
  selectedExpiration: string;
  onSymbolChange: (value: string) => void;
  onSubmit: () => void;
  onDirectionChange: (value: OptionsDirection) => void;
  onRiskProfileChange: (value: OptionsRiskProfile) => void;
  onTargetPriceChange: (value: string) => void;
  onTargetDateChange: (value: string) => void;
  onRiskBudgetChange: (value: string) => void;
  onExpirationSelect: (value: string) => void;
}> = ({
  symbol,
  direction,
  riskProfile,
  targetPrice,
  targetDate,
  riskBudget,
  expirations,
  selectedExpiration,
  onSymbolChange,
  onSubmit,
  onDirectionChange,
  onRiskProfileChange,
  onTargetPriceChange,
  onTargetDateChange,
  onRiskBudgetChange,
  onExpirationSelect,
}) => (
  <section className="xl:col-span-12" data-testid="options-lab-assumptions-panel">
    <WolfyShellSurface variant="console" padding="sm" className="overflow-hidden">
      <div className="border-b border-[color:var(--wolfy-divider)] px-1 pb-3">
        <SectionHeader eyebrow="情景控制台" title="期权情景输入" icon={Search}>
          <div className="flex flex-wrap gap-2">
            <Pill tone="info">只读观察</Pill>
            <Pill tone="neutral">门控优先</Pill>
          </div>
        </SectionHeader>
        <p className="mt-2 text-sm text-[color:var(--wolfy-text-secondary)]">
          控制区只记录假设；数据是否可判断以后续准备度和风险边界为准，不构成买卖建议。
        </p>
      </div>

      <div className="mt-3 grid gap-3 xl:grid-cols-[minmax(0,1.45fr)_minmax(0,1fr)]">
        <CompactFilterBar
          className="min-h-0 items-stretch gap-3 p-3"
          trailing={(
            <TerminalButton type="button" variant="primary" className="min-h-10 px-5" onClick={onSubmit}>
              刷新情景
            </TerminalButton>
          )}
        >
          <div className="grid gap-3 lg:grid-cols-[minmax(0,0.95fr)_repeat(2,minmax(0,0.7fr))]">
            <label className={fieldShellClass}>
              <span className={labelClass}>标的代码</span>
              <input
                aria-label="标的代码"
                className={fieldClass}
                value={symbol}
                onChange={(event) => onSymbolChange(event.target.value.toUpperCase())}
                placeholder="TEM"
              />
            </label>
            <label className={fieldShellClass}>
              <span className={labelClass}>目标价格</span>
              <input aria-label="目标价格" value={targetPrice} onChange={(event) => onTargetPriceChange(event.target.value)} className={fieldClass} inputMode="decimal" />
            </label>
            <label className={fieldShellClass}>
              <span className={labelClass}>目标日期</span>
              <input aria-label="目标日期" value={targetDate} onChange={(event) => onTargetDateChange(event.target.value)} className={fieldClass} placeholder="2026-08-21" />
            </label>
          </div>
        </CompactFilterBar>

        <div className="grid gap-3 md:grid-cols-2">
          <label className={fieldShellClass}>
            <span className={labelClass}>到期日</span>
            <div className="relative">
              <select
                aria-label="到期日"
                className={cn(fieldClass, 'appearance-none pr-8')}
                value={selectedExpiration}
                onChange={(event) => onExpirationSelect(event.target.value)}
              >
                {expirations.length === 0 ? (
                  <option value={selectedExpiration}>暂无可用到期日</option>
                ) : expirations.map((expiration) => (
                  <option key={expiration.date} value={expiration.date}>
                    {expiration.date} · {expiration.dte} DTE
                  </option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-0 top-1/2 h-4 w-4 -translate-y-1/2 text-[color:var(--wolfy-text-muted)]" aria-hidden="true" />
            </div>
          </label>
          <label className={fieldShellClass}>
            <span className={labelClass}>风险预算</span>
            <input aria-label="风险预算" value={riskBudget} onChange={(event) => onRiskBudgetChange(event.target.value)} className={fieldClass} inputMode="decimal" />
          </label>
        </div>
      </div>

      <div className="mt-3 grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,0.92fr)]">
        <div className="min-w-0">
          <span className={labelClass}>方向</span>
          <SegmentedButtons options={DIRECTION_OPTIONS} value={direction} onChange={onDirectionChange} ariaLabel="方向假设" />
        </div>
        <div className="min-w-0">
          <span className={labelClass}>风险偏好</span>
          <SegmentedButtons options={RISK_PROFILE_OPTIONS} value={riskProfile} onChange={onRiskProfileChange} ariaLabel="风险偏好" />
        </div>
      </div>
    </WolfyShellSurface>
  </section>
);

function decisionStatusLabel(decision?: OptionsDecisionResponse | null): string {
  const label = decision?.decisionLabel || decision?.optimizer?.optimizerLabel;
  const tier = decision?.dataQuality?.dataQualityTier;
  if (label === '数据不足，禁止判断' || tier === 'synthetic_demo_only' || tier === 'insufficient') return '数据不足，禁止判断';
  if (label === '不建议' || label === '不建议交易') return '观察边界明确';
  if (label === '仅观察' || label === '可关注替代结构') return '可记录低风险观察结构';
  if (label === '有条件可交易') return '定价条件需继续观察';
  return '仅供观察';
}

function directionSummaryLabel(value: OptionsDirection): string {
  if (value === 'bullish') return '上涨情景';
  if (value === 'bearish') return '下跌情景';
  if (value === 'neutral') return '区间情景';
  return '波动扩张';
}

function firstObservationStrategy(
  decision?: OptionsDecisionResponse | null,
  comparison?: OptionsStrategyCompareResponse | null,
): OptionsStrategyType | null {
  const preferred = decision?.optimizer?.preferredStrategyKey;
  if (preferred) return preferred;

  const rankedAlternatives = asArray(decision?.rankedAlternatives).length
    ? asArray(decision?.rankedAlternatives)
    : asArray(decision?.optimizer?.alternatives);
  const ranked = rankedAlternatives[0]?.strategyKey;
  if (ranked) return ranked;

  const alternative = decision?.betterAlternative?.strategyType;
  if (alternative) return alternative;

  return asArray(comparison?.strategies)[0]?.strategyType ?? null;
}

function heroSummaryLine(
  availability: ConsumerAvailabilitySummary,
  decision: OptionsDecisionResponse | null,
  comparison: OptionsStrategyCompareResponse | null,
  hasChainRows: boolean,
): string {
  if (!hasChainRows) return '先加载可用期权链，再进入候选策略与风险边界。';
  if (availability.stateLabel === 'UPDATING') return '正在整理情景输入、候选结构与风险边界。';
  if (availability.stateLabel === 'UNAVAILABLE' || availability.stateLabel === 'PAUSED') {
    return '当前不形成判断，先保留输入与风险预算，等待下一次数据刷新。';
  }

  const observationStrategy = firstObservationStrategy(decision, comparison);
  if (isNonDecisionGrade(decision)) {
    return observationStrategy
      ? `当前先观察 ${strategyChineseLabel(observationStrategy)}，但判断等级未满足，需等待更完整的数据。`
      : '当前只满足观察条件，先记录风险边界与触发条件。';
  }

  if (observationStrategy) {
    return `当前优先跟踪 ${strategyChineseLabel(observationStrategy)}，先复核最大亏损、盈亏平衡与可成交性。`;
  }

  return availability.explanation;
}

type SummaryStripItem = {
  label: string;
  value: string;
  meta?: string;
};

const ProductHero: React.FC<{
  availability: ConsumerAvailabilitySummary;
  summary: OptionsUnderlyingSummaryResponse | null;
  chain: OptionsChainResponse | null;
  decision: OptionsDecisionResponse | null;
  comparison: OptionsStrategyCompareResponse | null;
  hasChainRows: boolean;
}> = ({ availability, summary, chain, decision, comparison, hasChainRows }) => {
  const underlying = summary?.underlying || chain?.underlying;
  const changeClass = metricTone(underlying?.changePct);
  const summaryLine = heroSummaryLine(availability, decision, comparison, hasChainRows);

  return (
    <section
      data-testid="options-lab-product-hero"
      className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[color:color-mix(in_srgb,var(--wolfy-surface-console)_94%,transparent)] px-4 py-4 md:px-5"
    >
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className={labelClass}>决策实验室</p>
            <Pill tone={availability.stateTone}>{availability.stateLabel}</Pill>
            <Pill tone={availability.confidenceTone}>{availability.confidenceLabel}</Pill>
          </div>
          <div className="mt-3 flex flex-wrap items-end gap-3">
            <h2 className="text-2xl font-semibold tracking-tight text-[color:var(--wolfy-text-primary)] md:text-3xl">
              {summary?.symbol || chain?.symbol || '--'}
            </h2>
            <span className="rounded-full border border-[color:color-mix(in_srgb,var(--wolfy-accent)_32%,transparent)] bg-[color:color-mix(in_srgb,var(--wolfy-accent)_10%,transparent)] px-3 py-1 text-sm font-medium text-[color:var(--wolfy-text-primary)]">
              {decisionStatusLabel(decision)}
            </span>
          </div>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
            {summaryLine}
          </p>
          <p className="mt-2 text-xs text-[color:var(--wolfy-text-muted)]">{availability.freshnessLabel}</p>
        </div>

        <div className="grid min-w-0 gap-3 sm:grid-cols-2 xl:min-w-[21rem]">
          <div className={cn(innerBlockClass, 'p-3')}>
            <p className={labelClass}>标的价格</p>
            <p className="mt-2 font-mono text-xl font-semibold tracking-tight text-[color:var(--wolfy-text-primary)]">
              {money(underlying?.price)}
            </p>
            <p className={cn('mt-1 text-sm', changeClass)}>{ratio(underlying?.changePct)}</p>
          </div>
          <div className={cn(innerBlockClass, 'p-3')}>
            <p className={labelClass}>当前说明</p>
            <p className="mt-2 text-sm font-semibold text-[color:var(--wolfy-text-primary)]">
              {availability.explanation}
            </p>
            <p className="mt-1 text-xs text-[color:var(--wolfy-text-muted)]">
              仅做只读情景分析，不构成买卖建议。
            </p>
          </div>
        </div>
      </div>
    </section>
  );
};

const DecisionSummaryStrip: React.FC<{ items: SummaryStripItem[] }> = ({ items }) => (
  <section
    data-testid="options-lab-summary-strip"
    className="grid gap-3 md:grid-cols-3"
    aria-label="期权实验室摘要"
  >
    {items.slice(0, 3).map((item) => (
      <div
        key={item.label}
        className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[color:color-mix(in_srgb,var(--wolfy-surface-console)_88%,transparent)] px-4 py-3"
      >
        <p className={labelClass}>{item.label}</p>
        <p className="mt-2 text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{item.value}</p>
        {item.meta ? <p className="mt-1 text-xs text-[color:var(--wolfy-text-muted)]">{item.meta}</p> : null}
      </div>
    ))}
  </section>
);

const ChainTable: React.FC<{ title: string; contracts: OptionContract[]; testId: string; className?: string }> = ({ title, contracts, testId, className }) => (
  <section className={cn('min-h-[280px] min-w-0', className)} data-testid="options-lab-chain-panel">
    <div className="mb-3">
      <SectionHeader eyebrow="期权链" title={title} icon={BarChart3} />
    </div>
    {contracts.length === 0 ? (
      <TerminalEmptyState title="暂无合约数据" className="min-h-[160px]">
        保留假设命令区与风险边界，等待下一次数据更新。
      </TerminalEmptyState>
    ) : (
      <DataWorkbenchFrame data-testid={testId}>
        <div className="max-h-[22rem] overflow-auto no-scrollbar">
          <table className="w-full min-w-[720px] border-separate border-spacing-y-1 text-left">
            <thead className="text-[10px] uppercase tracking-[0.16em] text-[color:var(--wolfy-text-muted)]">
              <tr>
                <th className="px-3 py-2">合约</th>
                <th className="px-3 py-2">行权价</th>
                <th className="px-3 py-2">中间价</th>
                <th className="px-3 py-2">买价 / 卖价</th>
                <th className="px-3 py-2">IV</th>
                <th className="px-3 py-2">Delta</th>
                <th className="px-3 py-2">Theta</th>
                <th className="px-3 py-2">OI / 成交量</th>
                <th className="px-3 py-2">流动性</th>
              </tr>
            </thead>
            <tbody>
              {contracts.map((contract) => (
                <tr key={contract.contractSymbol} className="rounded-md border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] text-xs text-[color:var(--wolfy-text-secondary)]">
                  <td className="rounded-l-md px-3 py-2 font-mono text-xs text-[color:var(--wolfy-text-primary)]">{contract.contractSymbol}</td>
                  <td className="px-3 py-2 font-mono">{money(contract.strike)}</td>
                  <td className="px-3 py-2 font-mono">{money(contract.mid)}</td>
                  <td className="px-3 py-2 font-mono">{money(contract.bid)} / {money(contract.ask)}</td>
                  <td className="px-3 py-2 font-mono">{ratio(contract.impliedVolatility)}</td>
                  <td className="px-3 py-2 font-mono">{number(contract.delta, 2)}</td>
                  <td className="px-3 py-2 font-mono text-amber-200">{number(contract.theta, 2)}</td>
                  <td className="px-3 py-2 font-mono">{number(contract.openInterest)} / {number(contract.volume)}</td>
                  <td className="rounded-r-md px-3 py-2">
                    <Pill tone={(contract.liquidityScore || 0) >= 75 ? 'good' : 'warn'}>
                      {number(contract.liquidityScore)}
                    </Pill>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </DataWorkbenchFrame>
    )}
  </section>
);

type RankedAlternative = NonNullable<NonNullable<OptionsDecisionResponse['optimizer']>['alternatives']>[number];

function strategyStatusLabel(strategy: OptionsStrategyComparison, alternative?: RankedAlternative): string {
  if (alternative?.decisionLabel === '数据不足，禁止判断' || alternative?.dataQualityTier === 'synthetic_demo_only') return '不可用';
  if (asArray(strategy.liquidityWarnings).length || asArray(strategy.ivThetaNotes).length > 1) return '需复核';
  if ((strategy.maxLoss || 0) > 500 || (strategy.requiredMovePct || 0) > 10) return '风险偏高';
  return '可观察';
}

function strategyPrimaryReason(strategy: OptionsStrategyComparison, alternative?: RankedAlternative): string {
  const altReason = asArray(alternative?.primaryReasons)[0];
  if (altReason) return warningLabel(altReason);
  const suitability = asArray(strategy.suitabilityNotes)[0];
  if (suitability) return limitationLabel(suitability);
  const warning = [...asArray(strategy.liquidityWarnings), ...asArray(strategy.ivThetaNotes)][0];
  return warning ? limitationLabel(warning) : '需结合假设继续观察';
}

const StrategyRow: React.FC<{
  strategy: OptionsStrategyComparison;
  rank: number;
  highlighted: boolean;
  gateBlocked: boolean;
  alternative?: RankedAlternative;
}> = ({ strategy, rank, highlighted, gateBlocked, alternative }) => (
  <article
    data-testid={highlighted ? 'options-lab-primary-strategy-row' : undefined}
    className={cn(
      'grid min-w-0 gap-3 rounded-md border px-3 py-2 text-sm transition-colors xl:grid-cols-[minmax(0,1.4fr)_0.7fr_repeat(4,minmax(0,0.8fr))_minmax(0,1.5fr)] xl:items-center',
      highlighted
        ? 'border-[color:color-mix(in_srgb,var(--wolfy-accent)_42%,transparent)] bg-[color:color-mix(in_srgb,var(--wolfy-accent)_10%,transparent)]'
        : 'border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] hover:border-[color:var(--wolfy-border-subtle)]',
    )}
  >
    <div className="min-w-0">
      <div className="flex items-center gap-2">
        <span className="font-mono text-xs text-[color:var(--wolfy-text-muted)]">#{rank}</span>
        {highlighted ? <Pill tone={gateBlocked ? 'warn' : 'info'}>{gateBlocked ? `观察排序 #${rank}` : '观察排序靠前'}</Pill> : null}
      </div>
      <h3 className="mt-1 truncate text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{strategyChineseLabel(strategy.strategyType)}</h3>
      <p className="mt-0.5 truncate font-mono text-[11px] text-[color:var(--wolfy-text-muted)]">{strategyLabel(strategy.strategyType)}</p>
    </div>
    <div>
      <p className={labelClass}>状态</p>
      <p className="mt-1 text-xs font-semibold text-[color:var(--wolfy-accent-soft)]">{gateBlocked ? '未达判断等级' : strategyStatusLabel(strategy, alternative)}</p>
    </div>
    <div>
      <p className={labelClass}>最大亏损</p>
      <p className="mt-1 font-mono text-xs text-[color:var(--wolfy-market-down)]">{money(alternative?.maxLoss ?? strategy.maxLoss)}</p>
    </div>
    <div>
      <p className={labelClass}>最大收益</p>
      <p className="mt-1 font-mono text-xs text-[color:var(--wolfy-market-up)]">{(alternative?.maxGain ?? strategy.maxGain) == null ? '不封顶' : money(alternative?.maxGain ?? strategy.maxGain)}</p>
    </div>
    <div>
      <p className={labelClass}>盈亏平衡</p>
      <p className="mt-1 font-mono text-xs text-[color:var(--wolfy-text-primary)]">{money(strategy.breakeven)}</p>
    </div>
    <div>
      <p className={labelClass}>情景收益</p>
      <p className={cn('mt-1 font-mono text-xs', metricTone(strategy.payoffAtTarget))}>{money(strategy.payoffAtTarget)}</p>
    </div>
    <div className="min-w-0">
      <p className={labelClass}>核心原因</p>
      <p className="mt-1 truncate text-xs text-[color:var(--wolfy-text-secondary)]">{strategyPrimaryReason(strategy, alternative)}</p>
    </div>
  </article>
);

const StrategyComparisonPanel: React.FC<{
  comparisonState: ComparisonState;
  decision: OptionsDecisionResponse | null;
  loading: boolean;
  emptyMessage: string | null;
  chain: OptionsChainResponse | null;
  className?: string;
}> = ({ comparisonState, decision, loading, emptyMessage, chain, className }) => {
  const comparison = comparisonState.comparison;
  const comparisonMetadata = comparison?.metadata ?? {};
  const strategies = asArray(comparison?.strategies);
  const limitations = asArray(comparison?.limitations);
  const freshness = chain?.underlying?.freshness || (comparisonMetadata.fixtureBacked ? 'fixture' : null);
  const rankedAlternatives = asArray(decision?.rankedAlternatives).length
    ? asArray(decision?.rankedAlternatives)
    : asArray(decision?.optimizer?.alternatives);
  const gateBlocked = isNonDecisionGrade(decision);
  const rankMap = new Map(rankedAlternatives.map((alternative, index) => [alternative.strategyKey, { alternative, index }]));
  const rankedStrategies = [...strategies].sort((left, right) => {
    const leftRank = rankMap.get(left.strategyType)?.index ?? Number.MAX_SAFE_INTEGER;
    const rightRank = rankMap.get(right.strategyType)?.index ?? Number.MAX_SAFE_INTEGER;
    if (leftRank !== rightRank) return leftRank - rightRank;
    return (right.riskRewardRatio || 0) - (left.riskRewardRatio || 0);
  });
  return (
    <section className={cn(panelClass, className)} data-testid="options-lab-strategy-comparison">
      <SectionHeader eyebrow="主工作区" title="候选策略" icon={Layers3}>
        <div className="flex flex-wrap justify-end gap-2">
          <Pill tone="info">{freshness ? limitationLabel(String(freshness)) : '等待快照'}</Pill>
        </div>
      </SectionHeader>
      <p className="mt-3 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
        先看排序靠前的结构，再复核最大亏损、盈亏平衡与可成交性。
      </p>
      {emptyMessage ? (
        <div className={cn(innerBlockClass, 'mt-5 border-dashed px-4 py-4 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]')}>
          <p className="text-sm font-semibold text-[color:var(--wolfy-text-primary)]">等待策略对比前提</p>
          <p className="mt-2">{emptyMessage}</p>
        </div>
      ) : null}
      {!emptyMessage && loading ? (
        <p className={cn(innerBlockClass, 'mt-5 px-4 py-5 font-mono text-sm text-[color:var(--wolfy-accent-soft)]')}>正在计算策略对比...</p>
      ) : null}
      {!emptyMessage && !loading && comparisonState.error ? (
        <TerminalNotice variant="danger" className="mt-5">{comparisonState.error}</TerminalNotice>
      ) : null}
      {!emptyMessage && !loading && !comparisonState.error && strategies.length === 0 ? (
        <TerminalEmptyState title="暂无可比较策略" className="mt-5">
          当前假设下暂无可比较策略。
        </TerminalEmptyState>
      ) : null}
      {!emptyMessage && !loading && !comparisonState.error && strategies.length > 0 ? (
        <DenseRows className="mt-5 divide-y-0 space-y-2">
          {rankedStrategies.map((strategy, index) => (
            <StrategyRow
              key={strategy.strategyType}
              strategy={strategy}
              rank={index + 1}
              highlighted={index === 0}
              gateBlocked={gateBlocked}
              alternative={rankMap.get(strategy.strategyType)?.alternative}
            />
          ))}
        </DenseRows>
      ) : null}
      <div className={cn(innerBlockClass, 'mt-5 p-4 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]')}>
        <span className={labelClass}>候选约束</span>
        <p className="mt-2">
          {limitations.length ? limitations.map(limitationLabel).join(' · ') : '当前数据可用于情景比较'}
        </p>
      </div>
    </section>
  );
};

const DecisionMetric: React.FC<{ label: string; value: string; tone?: string }> = ({ label, value, tone = 'text-[color:var(--wolfy-text-primary)]' }) => (
  <div className={cn(innerBlockClass, 'min-w-0 p-3')}>
    <p className={labelClass}>{label}</p>
    <p className={cn('mt-2 truncate font-mono text-base font-semibold tracking-tight', tone)}>{value}</p>
  </div>
);

const DecisionPanel: React.FC<{ decisionState: DecisionState; emptyMessage: string | null; className?: string }> = ({ decisionState, emptyMessage, className }) => {
  const decision = decisionState.decision;
  const label = decision?.decisionLabel || '数据不足，禁止判断';
  const expectedMove = decision?.expectedMove;
  const optimizer = decision?.optimizer;
  const rankedAlternatives = asArray(decision?.rankedAlternatives).length
    ? asArray(decision?.rankedAlternatives)
    : asArray(optimizer?.alternatives);
  const ivRankStatus = decision?.ivRankStatus || decision?.ivGreeks?.ivRankStatus;
  const ivRank = decision?.ivRank ?? decision?.ivGreeks?.ivRank;
  const ivPercentile = decision?.ivPercentile ?? decision?.ivGreeks?.ivPercentile;
  const boundaryCopy = observationBoundaryCopy(decision);
  const demoBoundaryCopy = isDemoOrDelayedDecision(decision)
    ? OPTIONS_DEMO_BOUNDARY_COPY
    : null;
  const labelTone = label === '数据不足，禁止判断' || label === '不建议'
    ? 'text-[color:var(--wolfy-market-down)]'
    : label === '仅观察'
      ? 'text-[color:var(--wolfy-accent-soft)]'
      : 'text-amber-100';
  const primaryStrategy = isNonDecisionGrade(decision) ? null : optimizer?.preferredStrategyKey || null;
  const observationCandidate = primaryStrategy || rankedAlternatives[0]?.strategyKey || decision?.betterAlternative?.strategyType || null;
  const decisionTags = [...new Set([
    freshnessLabel(decision?.freshness?.freshness),
    ivRankStatus === 'available' ? 'IV 分位可用' : 'IV 分位不可用',
  ].filter((item) => item && item !== '--'))].slice(0, 3);
  return (
    <section className={cn(panelClass, className)} data-testid="options-lab-decision-engine">
      <SectionHeader eyebrow="判断内容" title="情景判断" icon={ShieldCheck}>
        <div className="flex flex-wrap justify-end gap-2">
          <Pill tone={label.includes('禁止') || label.includes('不建议') ? 'risk' : 'warn'}>{label}</Pill>
          {decision?.dataQuality?.dataQualityTier ? <Pill tone="info">{dataTierLabel(decision.dataQuality.dataQualityTier)}</Pill> : null}
        </div>
      </SectionHeader>
      {emptyMessage ? (
        <p className={cn(innerBlockClass, 'mt-5 border-dashed px-4 py-4 text-sm text-[color:var(--wolfy-text-secondary)]')}>{emptyMessage}</p>
      ) : null}
      {!emptyMessage && decisionState.loading ? (
        <p className={cn(innerBlockClass, 'mt-5 px-4 py-5 font-mono text-sm text-[color:var(--wolfy-accent-soft)]')}>正在计算情景准备度...</p>
      ) : null}
      {!emptyMessage && !decisionState.loading && decisionState.error ? (
        <TerminalNotice variant="danger" className="mt-5">{decisionState.error}</TerminalNotice>
      ) : null}
      {!emptyMessage && !decisionState.loading && !decisionState.error && !decision ? (
        <TerminalEmptyState title="等待情景准备度" className="mt-5">
          先完成合约链加载，再进入收益/风险工作区。
        </TerminalEmptyState>
      ) : null}
      {!emptyMessage && !decisionState.loading && !decisionState.error && decision ? (
        <div className="mt-5 grid gap-4">
          <div
            data-testid="options-lab-decision-summary"
            className="rounded-md border border-[color:color-mix(in_srgb,var(--wolfy-accent)_34%,transparent)] bg-[color:color-mix(in_srgb,var(--wolfy-accent)_8%,transparent)] p-4"
          >
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0">
                <p className={labelClass}>判断状态</p>
                <p className={cn('mt-2 text-xl font-semibold', labelTone)}>{decisionStatusLabel(decision)}</p>
                <p className="mt-2 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
                  {boundaryCopy || (primaryStrategy
                    ? `观察结构：${strategyChineseLabel(primaryStrategy)}`
                    : '暂无可判断结构')}
                </p>
                {demoBoundaryCopy && demoBoundaryCopy !== boundaryCopy ? (
                  <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{demoBoundaryCopy}</p>
                ) : null}
              </div>
              <div className="flex flex-wrap gap-2">
                {decisionTags.map((tag) => (
                  <Pill key={tag} tone={tag.includes('不足') || tag.includes('不可用') ? 'warn' : 'info'}>{tag}</Pill>
                ))}
              </div>
            </div>
            <ReadinessGateStrip decision={decision} testId="options-lab-decision-readiness-strip" className="mt-4" />
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <DecisionMetric label="情景质量" value={number(decision?.tradeQualityScore)} tone="text-[color:var(--wolfy-text-primary)]" />
              <DecisionMetric label="最大亏损" value={money(decision?.riskReward?.maxLoss)} tone="text-[color:var(--wolfy-market-down)]" />
              <DecisionMetric label="预期波动" value={money(expectedMove?.expectedMoveAbs)} tone="text-[color:var(--wolfy-text-primary)]" />
              <DecisionMetric label="IV / 敏感度" value={number(decision?.ivGreeks?.ivReadiness)} tone="text-[color:var(--wolfy-accent-soft)]" />
            </div>
            <div className={cn(innerBlockClass, 'mt-4 p-3')}>
              <p className={labelClass}>观察结构</p>
              <p className="mt-2 text-base font-semibold text-[color:var(--wolfy-text-primary)]">{observationCandidate ? strategyChineseLabel(observationCandidate) : '暂无可判断结构'}</p>
              <p className="mt-2 text-sm leading-6 text-[color:var(--wolfy-accent-soft)]/80">
                {primaryStrategy
                  ? `观察结构：${strategyChineseLabel(primaryStrategy)}`
                  : `边界原因：${noTradeReasonLabel(optimizer?.noTradeReason)}`}
              </p>
            </div>
          </div>
          <div className="grid gap-3 lg:grid-cols-3">
            <div className={cn(innerBlockClass, 'p-4')}>
              <p className={labelClass}>盈亏平衡</p>
              <p className="mt-2 font-mono text-base font-semibold text-[color:var(--wolfy-text-primary)]">{money(decision?.breakeven?.breakeven)}</p>
              <p className="mt-1 text-sm text-[color:var(--wolfy-text-muted)]">所需波动：{ratio(decision?.breakeven?.requiredMovePct)}</p>
            </div>
            <div className={cn(innerBlockClass, 'p-4')}>
              <p className={labelClass}>IV 分位</p>
              {ivRankStatus === 'available' ? (
                <>
                  <p className="mt-2 font-mono text-base font-semibold tracking-tight text-[color:var(--wolfy-accent-soft)]">{number(ivRank, 1)} / {number(ivPercentile, 1)}</p>
                  <p className="mt-1 text-sm text-[color:var(--wolfy-text-muted)]">可与预期波动一起复核</p>
                </>
              ) : (
                <>
                  <p className="mt-2 font-mono text-base font-semibold tracking-tight text-[color:var(--wolfy-text-secondary)]">IV 分位不可用</p>
                  <p className="mt-1 text-sm text-[color:var(--wolfy-text-muted)]">关键信号暂不完整，置信度降低。</p>
                </>
              )}
            </div>
            <div className={cn(innerBlockClass, 'p-4')}>
              <p className={labelClass}>预期波动</p>
              <p className="mt-2 font-mono text-base font-semibold tracking-tight text-[color:var(--wolfy-text-primary)]">{money(expectedMove?.expectedMoveAbs)}</p>
              <p className="mt-1 text-sm text-[color:var(--wolfy-text-muted)]">{ratio(expectedMove?.expectedMovePct)} · {expectedMoveSourceLabel(expectedMove?.expectedMoveSource)}</p>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
};

const RiskBoundaryPanel: React.FC<{
  decision: OptionsDecisionResponse | null;
  chain: OptionsChainResponse | null;
  loading: boolean;
  error: string | null;
  className?: string;
}> = ({ decision, chain, loading, error, className }) => {
  const boundaryCopy = observationBoundaryCopy(decision);
  const dataWarnings = [
    ...asArray(decision?.dataQuality?.blockingReasons),
    ...asArray(decision?.dataQuality?.warnings),
    ...asArray(chain?.limitations),
    ...asArray(chain?.metadata?.limitations),
  ];
  const liquidityWarnings = asArray(decision?.liquidity?.liquidityWarnings);
  const ivWarnings = [
    ...asArray(decision?.ivGreeks?.warnings),
    ...asArray(decision?.expectedMove?.expectedMoveWarnings),
  ];
  const riskWarnings = asArray(decision?.riskWarnings);
  const allWarnings = [...new Set([
    loading ? '等待快照' : null,
    error ? '部分外部数据暂不可用' : null,
    decision?.dataQuality?.dataQualityTier === 'synthetic_demo_only' ? '不可作为交易信号' : null,
    ...dataWarnings,
    ...liquidityWarnings,
    ...ivWarnings,
    ...riskWarnings,
    '需人工复核',
  ].filter(Boolean) as string[])];
  const visibleWarnings = allWarnings.slice(0, 3);
  const hiddenWarnings = allWarnings.slice(3);
  const dataState = loading
    ? '等待快照'
    : error
      ? '部分外部数据暂不可用'
      : dataTierLabel(decision?.dataQuality?.dataQualityTier);
  const topState = decisionStatusLabel(decision);
  return (
    <section className={cn(panelClass, className)} data-testid="options-lab-risk-boundary-panel">
      <SectionHeader eyebrow="风险控制" title="风险边界" icon={AlertTriangle}>
        <Pill tone={topState.includes('禁止') ? 'risk' : 'info'}>
          {topState}
        </Pill>
      </SectionHeader>
      <div className="mt-5 grid gap-3 text-sm">
        <div className="rounded-md border border-[color:color-mix(in_srgb,var(--wolfy-market-down)_34%,transparent)] bg-[color:color-mix(in_srgb,var(--wolfy-market-down)_10%,transparent)] p-3">
          <p className={labelClass}>观察边界</p>
          <p className="mt-2 text-sm font-semibold text-[color:var(--wolfy-market-down)]">{topState}</p>
          <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{boundaryCopy || '仅供观察，不可作为交易信号。'}</p>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <div className={cn(innerBlockClass, 'p-3')}>
            <p className={labelClass}>数据状态</p>
            <p className="mt-2 text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{dataState}</p>
          </div>
          <div className={cn(innerBlockClass, 'p-3')}>
            <p className={labelClass}>最大亏损</p>
            <p className="mt-2 font-mono text-sm font-semibold text-[color:var(--wolfy-market-down)]">
              {money(decision?.riskReward?.maxLoss)}
            </p>
          </div>
        </div>
        <ul className="grid gap-2" aria-label="风险边界警示">
          {visibleWarnings.map((warning) => (
            <li
              key={warning}
              data-testid="options-lab-visible-risk-warning"
              className="flex gap-2 rounded-md border border-amber-300/20 bg-amber-300/5 px-3 py-2 text-xs leading-5 text-amber-200"
            >
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-200" aria-hidden="true" />
              <span>{warningLabel(warning)}</span>
            </li>
          ))}
        </ul>
        <ConsoleDisclosure title="更多限制" summary="默认折叠，避免打断主工作区">
          {hiddenWarnings.length ? (
            <div className="flex flex-wrap gap-2">
              {hiddenWarnings.map((warning) => (
                <Pill key={warning} tone="neutral">{warningLabel(warning)}</Pill>
              ))}
            </div>
          ) : (
            <p className="text-[color:var(--wolfy-text-secondary)]">暂无额外限制，仍需人工复核。</p>
          )}
        </ConsoleDisclosure>
      </div>
    </section>
  );
};

function liquiditySensitivityNote(decision: OptionsDecisionResponse | null): string {
  const liquidityWarnings = asArray(decision?.liquidity?.liquidityWarnings);
  const ivWarnings = [
    ...asArray(decision?.ivGreeks?.warnings),
    ...asArray(decision?.expectedMove?.expectedMoveWarnings),
  ];

  const hasLiquidity = liquidityWarnings.some((warning) => warning.includes('spread') || warning.includes('liquidity') || warning.includes('open_interest') || warning.includes('volume'));
  const hasSensitivity = ivWarnings.some((warning) => warning.includes('iv') || warning.includes('greeks') || warning.includes('expected_move'));

  if (hasLiquidity && hasSensitivity) {
    return '流动性与敏感度都有限时，先看最大亏损与价差，再决定是否继续跟踪该结构。';
  }
  if (hasLiquidity) {
    return '价差偏宽或成交深度不足时，名义收益不等于可成交结果，先观察定义风险结构。';
  }
  if (hasSensitivity) {
    return 'IV 分位或 Greeks 不完整时，只能看方向边界，不能把到期前收益当成稳定结论。';
  }
  return '优先同时看价差、OI、IV 与 Theta，再决定是否继续跟踪该结构。';
}

function nextActionCopy(
  loading: boolean,
  error: string | null,
  hasChainRows: boolean,
  decision: OptionsDecisionResponse | null,
): string {
  if (loading) return '等待链表、候选结构与风险边界刷新完成。';
  if (error) return '稍后重试或更换标的，当前不要扩展判断。';
  if (!hasChainRows) return '先加载可用到期日与期权链，再进入策略比较。';
  if (isNonDecisionGrade(decision)) return '先记录观察结构与风险预算，等待更完整数据后再复核。';
  return '先复核首个候选的最大亏损、盈亏平衡与流动性，再决定是否继续跟踪。';
}

const ContextRailPanel: React.FC<{
  decision: OptionsDecisionResponse | null;
  loading: boolean;
  error: string | null;
  hasChainRows: boolean;
  className?: string;
}> = ({ decision, loading, error, hasChainRows, className }) => (
  <section className={cn(panelClass, className)} data-testid="options-lab-context-rail-panel">
    <SectionHeader eyebrow="观察提示" title="流动性与下一步" icon={LineChart} />
    <div className="mt-5 grid gap-3">
      <div className={cn(innerBlockClass, 'p-4')}>
        <p className={labelClass}>流动性 / 敏感度</p>
        <p className="mt-2 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
          {liquiditySensitivityNote(decision)}
        </p>
      </div>
      <div className={cn(innerBlockClass, 'p-4')}>
        <p className={labelClass}>下一步</p>
        <p className="mt-2 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
          {nextActionCopy(loading, error, hasChainRows, decision)}
        </p>
      </div>
    </div>
  </section>
);

const MethodologyDisclosure: React.FC<{
  state: LoadState;
  targetPrice: string;
  targetDate: string;
  riskBudget: string;
}> = ({ state, targetPrice, targetDate, riskBudget }) => (
  <ConsoleDisclosure
    data-testid="options-lab-analysis-details"
    title="数据注记"
    summary="默认折叠，仅在需要时展开方法与限制。"
    className="border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)]"
  >
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
      <div className={cn(innerBlockClass, 'p-4 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]')}>
        <p className={labelClass}>输入摘要</p>
        <p className="mt-2">目标价 {targetPrice || '--'}，目标日 {targetDate || '--'}，风险预算 {riskBudget || '--'}。</p>
      </div>
      <div className={cn(innerBlockClass, 'p-4 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]')}>
        <p className={labelClass}>数据说明</p>
        <p className="mt-2">
          {[...asArray(state.chain?.limitations), ...asArray(state.chain?.metadata?.limitations)].map(limitationLabel).join(' · ') || '当前数据可用于情景观察'}
        </p>
      </div>
      <div className={cn(innerBlockClass, 'p-4 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]')}>
        <p className={labelClass}>方法边界</p>
        <p className="mt-2">期权可能归零，IV、Theta、流动性与价差会改变到期前估值。本模块仅做只读情景分析。</p>
      </div>
    </div>
  </ConsoleDisclosure>
);

type OptionsLabErrorBoundaryState = {
  hasError: boolean;
  errorName: string;
};

export class OptionsLabErrorBoundary extends React.Component<{ children: React.ReactNode }, OptionsLabErrorBoundaryState> {
  state: OptionsLabErrorBoundaryState = {
    hasError: false,
    errorName: '',
  };

  static getDerivedStateFromError(error: unknown): OptionsLabErrorBoundaryState {
    return {
      hasError: true,
      errorName: error instanceof Error && error.name ? error.name : 'RenderError',
    };
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    return (
      <main className="w-full overflow-x-hidden text-white">
        <TerminalPageShell>
          <section className="mx-auto flex w-full max-w-[920px] flex-col gap-4 rounded-lg border border-[color:color-mix(in_srgb,var(--wolfy-market-down)_34%,transparent)] bg-[var(--wolfy-surface-console)] p-5 md:p-6">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-1 h-5 w-5 shrink-0 text-amber-200" aria-hidden="true" />
              <div className="min-w-0">
                <p className={labelClass}>期权实验室</p>
                <h1 className="mt-2 text-xl font-semibold text-[color:var(--wolfy-text-primary)]">{OPTIONS_LAB_CRASH_FALLBACK}</h1>
                <p className="mt-3 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">仅显示用户态错误分类。</p>
              </div>
            </div>
            <div className="rounded-md border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] p-4 text-sm text-[color:var(--wolfy-text-secondary)]">
              暂时无法完成渲染，内部错误详情已隐藏。
            </div>
          </section>
        </TerminalPageShell>
      </main>
    );
  }
}

const OptionsLabPageContent: React.FC = () => {
  const [symbolInput, setSymbolInput] = useState('TEM');
  const [activeSymbol, setActiveSymbol] = useState('TEM');
  const [direction, setDirection] = useState<OptionsDirection>('bullish');
  const [riskProfile, setRiskProfile] = useState<OptionsRiskProfile>('balanced');
  const [targetPrice, setTargetPrice] = useState('65');
  const [targetDate, setTargetDate] = useState('2026-08-21');
  const [riskBudget, setRiskBudget] = useState('1000');
  const [selectedExpiration, setSelectedExpiration] = useState('2026-06-19');
  const [reloadKey, setReloadKey] = useState(0);
  const [state, setState] = useState<LoadState>({
    loading: true,
    error: null,
    summary: null,
    expirations: null,
    chain: null,
  });
  const [comparisonState, setComparisonState] = useState<ComparisonState>({
    loading: false,
    error: null,
    comparison: null,
  });
  const [decisionState, setDecisionState] = useState<DecisionState>({
    loading: false,
    error: null,
    decision: null,
  });

  useEffect(() => {
    let ignored = false;

    async function load() {
      try {
        setState((current) => ({
          ...current,
          loading: true,
          error: null,
        }));
        const [summary, expirations] = await Promise.all([
          optionsLabApi.getUnderlyingSummary(activeSymbol),
          optionsLabApi.getExpirations(activeSymbol),
        ]);
        const expirationItems = asArray(expirations.expirations);
        const nextExpiration = expirationItems.some((item) => item.date === selectedExpiration)
          ? selectedExpiration
          : expirationItems[0]?.date || selectedExpiration;
        const chain = await optionsLabApi.getOptionChain(activeSymbol, nextExpiration);
        if (ignored) return;
        setSelectedExpiration(nextExpiration);
        setState((current) => ({
          ...current,
          loading: false,
          error: null,
          summary,
          expirations,
          chain,
        }));
      } catch {
        if (ignored) return;
        setState((current) => ({
          ...current,
          loading: false,
          error: '期权链暂不可用。请稍后重试或调整标的。',
          chain: null,
        }));
      }
    }

    void load();

    return () => {
      ignored = true;
    };
  }, [activeSymbol, reloadKey, selectedExpiration]);

  useEffect(() => {
    let ignored = false;
    let timeoutId: number | undefined;

    async function loadComparison() {
      const targetPriceValue = Number(targetPrice);
      const hasTargetPrice = Number.isFinite(targetPriceValue) && targetPriceValue > 0;
      const hasTargetDate = targetDate.trim().length > 0;
      const hasExpirations = asArray(state.expirations?.expirations).length > 0;
      const hasContracts = Boolean(asArray(state.chain?.calls).length || asArray(state.chain?.puts).length);
      const baseReady = !state.loading && !state.error && state.summary && state.expirations && state.chain;
      const comparisonReady = Boolean(baseReady && hasTargetPrice && hasTargetDate && hasExpirations && hasContracts);

      if (!comparisonReady) {
        return;
      }

      setComparisonState({
        loading: true,
        error: null,
        comparison: null,
      });

      timeoutId = window.setTimeout(() => {
        if (ignored) return;
        setComparisonState({
          loading: false,
          error: '策略对比暂不可用。请稍后重试或调整假设。',
          comparison: null,
        });
      }, COMPARISON_LOADING_TIMEOUT_MS);

      try {
        const comparison = await optionsLabApi.compareStrategies({
          symbol: activeSymbol,
          direction,
          targetPrice: targetPriceValue,
          targetDate,
          maxPremium: Number(riskBudget) > 0 ? Number(riskBudget) : undefined,
          riskProfile,
          strategies: ['long_call', 'long_put', 'bull_call_spread', 'bear_put_spread'],
          forceRefresh: true,
        });
        if (ignored) return;
        window.clearTimeout(timeoutId);
        setComparisonState({
          loading: false,
          error: null,
          comparison,
        });
      } catch {
        if (ignored) return;
        window.clearTimeout(timeoutId);
        setComparisonState({
          loading: false,
          error: '策略对比暂不可用。请稍后重试或调整假设。',
          comparison: null,
        });
      }
    }

    void loadComparison();

    return () => {
      ignored = true;
      if (timeoutId !== undefined) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [
    activeSymbol,
    direction,
    riskBudget,
    riskProfile,
    state.chain,
    state.error,
    state.expirations,
    state.loading,
    state.summary,
    targetDate,
    targetPrice,
  ]);

  useEffect(() => {
    let ignored = false;

    async function loadDecision() {
      const targetPriceValue = Number(targetPrice);
      const riskBudgetValue = Number(riskBudget);
      const hasTargetPrice = Number.isFinite(targetPriceValue) && targetPriceValue > 0;
      const hasTargetDate = targetDate.trim().length > 0;
      const hasContracts = Boolean(asArray(state.chain?.calls).length || asArray(state.chain?.puts).length);
      const baseReady = !state.loading && !state.error && state.summary && state.expirations && state.chain;
      if (!baseReady || !hasTargetPrice || !hasTargetDate || !hasContracts) {
        setDecisionState({ loading: false, error: null, decision: null });
        return;
      }

      setDecisionState({ loading: true, error: null, decision: null });
      try {
        const decision = await optionsLabApi.evaluateDecision({
          symbol: activeSymbol,
          strategy: 'bull_call_spread',
          expiration: selectedExpiration,
          targetPrice: targetPriceValue,
          targetDate,
          riskBudget: Number.isFinite(riskBudgetValue) && riskBudgetValue > 0 ? riskBudgetValue : undefined,
          forceRefresh: true,
        });
        if (ignored) return;
        setDecisionState({ loading: false, error: null, decision });
      } catch {
        if (ignored) return;
        setDecisionState({
          loading: false,
          error: '情景准备度暂不可用。请稍后重试或调整假设。',
          decision: null,
        });
      }
    }

    void loadDecision();

    return () => {
      ignored = true;
    };
  }, [
    activeSymbol,
    riskBudget,
    selectedExpiration,
    state.chain,
    state.error,
    state.expirations,
    state.loading,
    state.summary,
    targetDate,
    targetPrice,
  ]);

  const handleSubmit = useCallback(() => {
    const normalized = symbolInput.trim().toUpperCase() || 'TEM';
    setSymbolInput(normalized);
    setState((current) => ({ ...current, loading: true, error: null }));
    if (normalized === activeSymbol) {
      setReloadKey((current) => current + 1);
      return;
    }
    setActiveSymbol(normalized);
  }, [activeSymbol, symbolInput]);

  const handleExpirationSelect = useCallback((expiration: string) => {
    setState((current) => ({ ...current, loading: true, error: null }));
    setSelectedExpiration(expiration);
  }, []);

  const expirations = asArray(state.expirations?.expirations).length ? asArray(state.expirations?.expirations) : EMPTY_EXPIRATIONS;
  const calls = asArray(state.chain?.calls).length ? asArray(state.chain?.calls) : EMPTY_CONTRACTS;
  const puts = asArray(state.chain?.puts).length ? asArray(state.chain?.puts) : EMPTY_CONTRACTS;
  const hasChainRows = calls.length > 0 || puts.length > 0;
  const comparisonEmptyMessage = useMemo(() => {
    if (state.loading) return '正在加载基础数据，稍后将自动计算策略对比。';
    if (state.error) return '期权链暂不可用，策略对比已暂停。';
    const targetPriceValue = Number(targetPrice);
    const hasTargetPrice = Number.isFinite(targetPriceValue) && targetPriceValue > 0;
    const hasTargetDate = targetDate.trim().length > 0;
    const hasExpirations = expirations.length > 0;
    const hasContracts = hasChainRows;
    if (!state.summary || !state.expirations || !state.chain) return COMPARISON_EMPTY_MESSAGE;
    if (!hasTargetPrice || !hasTargetDate || !hasExpirations || !hasContracts) return COMPARISON_EMPTY_MESSAGE;
    return null;
  }, [expirations.length, hasChainRows, state.chain, state.error, state.expirations, state.loading, state.summary, targetDate, targetPrice]);
  const decisionEmptyMessage = useMemo(() => {
    if (state.loading) return '正在加载基础数据，稍后将自动计算情景准备度。';
    if (state.error) return '期权链暂不可用，情景准备度已暂停。';
    const targetPriceValue = Number(targetPrice);
    if (!state.summary || !state.expirations || !state.chain || !hasChainRows) return '先加载合约链后，再进入情景准备度。';
    if (!Number.isFinite(targetPriceValue) || targetPriceValue <= 0 || !targetDate.trim()) return '先补齐目标价格与目标日期。';
    return null;
  }, [hasChainRows, state.chain, state.error, state.expirations, state.loading, state.summary, targetDate, targetPrice]);
  const consumerAvailability = useMemo(
    () => consumerAvailabilitySummary(state, comparisonState, decisionState, hasChainRows),
    [comparisonState, decisionState, hasChainRows, state],
  );
  const summaryStripItems = useMemo<SummaryStripItem[]>(() => {
    const topCandidate = firstObservationStrategy(decisionState.decision, comparisonState.comparison);
    const maxLoss = decisionState.decision?.riskReward?.maxLoss;
    const scenarioMeta = targetDate.trim() ? `目标日 ${targetDate}` : '补齐目标日后可比较策略';
    const candidateMeta = topCandidate ? '优先复核最大亏损与盈亏平衡' : '当前未形成可判断结构';
    const riskValue = typeof maxLoss === 'number' && Number.isFinite(maxLoss)
      ? `最大亏损 ${money(maxLoss)}`
      : noTradeReasonLabel(decisionState.decision?.optimizer?.noTradeReason);

    return [
      {
        label: '输入情景',
        value: `${directionSummaryLabel(direction)} · 目标价 ${targetPrice || '--'}`,
        meta: scenarioMeta,
      },
      {
        label: '首个候选',
        value: topCandidate ? strategyChineseLabel(topCandidate) : '暂无可判断结构',
        meta: candidateMeta,
      },
      {
        label: '风险边界',
        value: riskValue,
        meta: riskBudget ? `风险预算 ${riskBudget}` : '先定义可承受亏损',
      },
    ];
  }, [comparisonState.comparison, decisionState.decision, direction, riskBudget, targetDate, targetPrice]);

  return (
    <main className="w-full overflow-x-hidden text-white">
      <ConsumerWorkspaceScope className="min-h-0 flex-1">
      <ConsumerWorkspacePageShell data-testid="options-lab-page-root">
        <TerminalPageHeading
          data-testid="options-lab-page-heading"
          eyebrow="只读情景分析"
          title="期权实验室"
          action={(
            <div className="flex flex-wrap justify-end gap-2">
              <Pill tone="info">门控优先</Pill>
              <Pill tone="warn">不构成买卖建议</Pill>
            </div>
          )}
        />
        <div className="mt-5 grid gap-6" data-testid="options-lab-bento-grid">
          <ProductHero
            availability={consumerAvailability}
            summary={state.summary}
            chain={state.chain}
            decision={decisionState.decision}
            comparison={comparisonState.comparison}
            hasChainRows={hasChainRows}
          />
          <DecisionSummaryStrip items={summaryStripItems} />

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1.55fr)_minmax(0,0.85fr)]">
            <div className="grid min-w-0 gap-6">
              <AssumptionPanel
                symbol={symbolInput}
                direction={direction}
                riskProfile={riskProfile}
                targetPrice={targetPrice}
                targetDate={targetDate}
                riskBudget={riskBudget}
                expirations={expirations}
                selectedExpiration={selectedExpiration}
                onSymbolChange={setSymbolInput}
                onSubmit={handleSubmit}
                onDirectionChange={setDirection}
                onRiskProfileChange={setRiskProfile}
                onTargetPriceChange={setTargetPrice}
                onTargetDateChange={setTargetDate}
                onRiskBudgetChange={setRiskBudget}
                onExpirationSelect={handleExpirationSelect}
              />

              <StrategyComparisonPanel
                comparisonState={comparisonState}
                decision={decisionState.decision}
                loading={comparisonState.loading}
                emptyMessage={comparisonEmptyMessage}
                chain={state.chain}
              />
              <DecisionPanel decisionState={decisionState} emptyMessage={decisionEmptyMessage} />

              <WolfyShellSurface variant="console" padding="sm" className="overflow-hidden">
                <SectionHeader eyebrow="链表工作区" title="Call / Put 链" icon={BarChart3} />
                {state.loading ? (
                  <TerminalNotice variant="info" className="mt-4">正在加载期权链快照...</TerminalNotice>
                ) : null}
                {state.error ? (
                  <TerminalNotice variant="danger" className="mt-4">{state.error}</TerminalNotice>
                ) : null}
                {!state.loading && !state.error && hasChainRows ? (
                  <div className="mt-4 grid gap-4 xl:grid-cols-2">
                    <ChainTable title="Call 链" contracts={calls} testId="options-lab-calls-table" />
                    <ChainTable title="Put 链" contracts={puts} testId="options-lab-puts-table" />
                  </div>
                ) : null}
                {!state.loading && !state.error && !hasChainRows ? (
                  <div className="mt-4">
                    <TerminalEmptyState title="暂无数据">
                      保留输入、候选结构与风险边界，等待下一次数据更新。
                    </TerminalEmptyState>
                  </div>
                ) : null}
              </WolfyShellSurface>

              <MethodologyDisclosure state={state} targetPrice={targetPrice} targetDate={targetDate} riskBudget={riskBudget} />
            </div>

            <div className="grid min-w-0 gap-6 self-start">
              <RiskBoundaryPanel
                decision={decisionState.decision}
                chain={state.chain}
                loading={state.loading || decisionState.loading}
                error={state.error || decisionState.error}
              />
              <ContextRailPanel
                decision={decisionState.decision}
                loading={state.loading || comparisonState.loading || decisionState.loading}
                error={state.error || comparisonState.error || decisionState.error}
                hasChainRows={hasChainRows}
              />
            </div>
          </div>
        </div>
      </ConsumerWorkspacePageShell>
      </ConsumerWorkspaceScope>
    </main>
  );
};

const OptionsLabPage: React.FC = () => (
  <OptionsLabErrorBoundary>
    <OptionsLabPageContent />
  </OptionsLabErrorBoundary>
);

export default OptionsLabPage;
