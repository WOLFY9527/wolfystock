import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, BarChart3, ChevronDown, Layers3, LineChart, Search, ShieldCheck } from 'lucide-react';
import {
  buildConsumerResearchReadinessView,
  convertOptionsReadiness,
  extractOptionsResearchReadiness,
  inferOptionsResearchReadiness,
} from '../api/researchReadiness';
import {
  optionsLabApi,
  type OptionContract,
  type OptionSide,
  type OptionsDecisionResponse,
  type OptionsChainResponse,
  type OptionsConsumerScenarioFrame,
  type OptionsDirection,
  type OptionsExpiration,
  type OptionsExpirationsResponse,
  type OptionsRiskProfile,
  type OptionsStructureSignalPacket,
  type OptionsStrategyCompareResponse,
  type OptionsStrategyComparison,
  type OptionsStrategyType,
  type OptionsUnderlyingSummaryResponse,
} from '../api/optionsLab';
import type { OptionsResearchReadiness } from '../types/researchReadiness';
import ConsumerResearchReadinessStrip from '../components/common/ConsumerResearchReadinessStrip';
import OptionsReadinessGateSummary from '../components/options/OptionsReadinessGateSummary';
import {
  CompactFilterBar,
  ConsoleDisclosure,
  DataWorkbenchFrame,
  DenseRows,
  WolfyShellSurface,
} from '../components/linear/LinearPrimitives';
import {
  TerminalButton,
  TerminalChip,
  TerminalEmptyState,
  TerminalNotice,
  TerminalPageHeading,
} from '../components/terminal/TerminalPrimitives';
import { ConsumerWorkspacePageShell, ConsumerWorkspaceScope } from '../components/layout/ConsumerWorkspaceShell';
import { cn } from '../utils/cn';
import { normalizeOptionsEvidence } from '../utils/evidenceDisplay';
import { formatNumber, formatPercent } from '../utils/format';
import { sanitizeUserFacingDataIssue } from '../utils/userFacingDataIssues';

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

type ScenarioEvidenceView = {
  frameState: string;
  frameTone: 'good' | 'warn' | 'risk' | 'info';
  scenarioCoverage: string;
  chainQuality: string;
  gateChips: Array<{ label: string; value: string; tone: 'good' | 'warn' | 'risk' | 'info' }>;
  payoffLines: string[];
  riskLines: string[];
  assumptionLines: string[];
  missingEvidence: string[];
  nextEvidenceNeeded: string[];
  boundaryLines: string[];
};

type CompactMetricListItem = {
  label: string;
  value: React.ReactNode;
  tone?: string;
};

const DIRECTION_OPTIONS: Array<{ value: OptionsDirection; label: string }> = [
  { value: 'bullish', label: '上行情景假设' },
  { value: 'bearish', label: '下行情景假设' },
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
const COMPARISON_EMPTY_MESSAGE = '先选择可用到期日并加载合约后，再进入结构样例比较。';
const OPTIONS_LAB_CRASH_FALLBACK = '期权实验室暂时无法加载，请刷新或稍后重试。';
const OPTIONS_MODULE_PAUSED_COPY = '期权数据暂不可用，情景分析已暂停。';
const OPTIONS_INSUFFICIENT_COPY = '当前期权信号数据不足，仅供观察。';
const OPTIONS_UPDATING_COPY = '数据更新中，稍后将自动刷新。';
const OPTIONS_UNAVAILABLE_COPY = '本模块暂不可用，请稍后重试。';
const OPTIONS_NO_CONCLUSION_COPY = '数据不足，暂不形成结论';
const OPTIONS_SAFE_INSTRUCTION_COPY = '仅做只读情景分析，不构成执行指令。';
const OPTIONS_NON_ADVICE_COPY = '不构成买卖建议';
const OPTIONS_NO_ORDER_COPY = '不会触发外部执行';
const OPTIONS_NO_BROKER_COPY = '不连接外部执行通道';
const OPTIONS_NO_PORTFOLIO_MUTATION_COPY = '不改动投资组合';
const OPTIONS_OBSERVE_ONLY_COPY = '仅供观察，不作为结论依据';
const OPTIONS_DEMO_BOUNDARY_COPY = '演示数据：当前数据延迟，仅用于界面与情景验证，不作为结论依据。';
const OPTIONS_DEMO_GREEKS_PLACEHOLDER = '敏感度暂未提供';
const OPTIONS_DEMO_GREEKS_EXPLANATION = '演示链未提供真实敏感度数值，仅保留结构与风险边界。';

const fieldShellClass = 'group flex min-h-[4rem] min-w-0 flex-col justify-center gap-1.5 rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[color:color-mix(in_srgb,var(--wolfy-surface-input)_92%,transparent)] px-3 py-2 transition-colors focus-within:border-[color:var(--wolfy-accent)]';
const fieldClass = 'h-6 w-full border-0 bg-transparent p-0 font-mono text-sm text-[color:var(--wolfy-text-primary)] outline-none placeholder:text-[color:var(--wolfy-text-muted)]';
const labelClass = 'text-[10px] font-bold uppercase tracking-[0.18em] text-[color:var(--wolfy-text-muted)]';
const panelClass = 'min-w-0 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-4 md:p-5';
const innerBlockClass = 'rounded-md border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)]';
const regionSectionClass = 'rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[color:color-mix(in_srgb,var(--wolfy-surface-console)_92%,transparent)] px-4 py-4 md:px-5 md:py-5';

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

function greekNumber(value?: number | null, digits = 0): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return OPTIONS_DEMO_GREEKS_PLACEHOLDER;
  return formatNumber(value, digits);
}

function hasAnyGreekValue(contract: OptionContract): boolean {
  return [contract.delta, contract.theta, contract.gamma, contract.vega, contract.rho]
    .some((value) => typeof value === 'number' && Number.isFinite(value));
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
  const safeLabel = sanitizeUserFacingDataIssue(value, 'zh');
  if (safeLabel !== value) {
    return safeLabel === '数据不足，结论仅供观察' ? '部分外部数据暂不可用' : safeLabel;
  }
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
  if (value === '不可作为交易信号') return OPTIONS_OBSERVE_ONLY_COPY;
  if (value === '不可用于真实交易判断') return OPTIONS_OBSERVE_ONLY_COPY;
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
    return { label: '判断条件较完整', tone: 'good' };
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
    : { label: '数据质量较完整', tone: 'good' };
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
    : { label: '流动性较完整', tone: 'good' };
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
        {chips.map((chip, index) => (
          <Pill key={`${chip.label}-${index}`} tone={chip.tone}>{chip.label}</Pill>
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
  if (value === 'live_usable') return '实时链路较完整';
  if (value === 'delayed_usable') return '行情延迟，可观察';
  if (value === 'synthetic_demo_only') return '演示/延迟数据';
  if (value === 'insufficient') return '数据不足';
  return '--';
}

function freshnessLabel(value?: string | null): string {
  if (value === 'live') return '更新状态：实时链路';
  if (value === 'mock') return '演示/延迟数据';
  if (value === 'synthetic_delayed') return '演示/延迟数据';
  if (value === 'fixture') return '浏览器验证数据';
  return value ? limitationLabel(value) : '--';
}

function marketLabel(value?: string | null): string {
  if (!value?.trim()) return '市场待确认';
  const normalized = value.trim().toUpperCase();
  if (normalized === 'US') return 'US';
  if (normalized === 'HK') return 'HK';
  if (normalized === 'CN' || normalized === 'A') return 'A 股';
  return normalized;
}

function sourceContextLabel(value?: string | null): string {
  if (!value?.trim()) return '来源待确认';
  const normalized = value.trim();
  const lower = normalized.toLowerCase();
  if (lower === 'fixture' || lower === 'mock' || lower.includes('fixture') || lower.includes('synthetic')) {
    return '演示/延迟数据';
  }
  return limitationLabel(normalized);
}

function underlyingDisplayName(summary: OptionsUnderlyingSummaryResponse | null, chain: OptionsChainResponse | null): string {
  const symbol = summary?.symbol || chain?.symbol || '--';
  const underlying = recordValue(summary?.underlying) || recordValue(chain?.underlying);
  const candidate = [underlying?.displayName, underlying?.name, underlying?.companyName]
    .find((value): value is string => typeof value === 'string' && value.trim().length > 0);
  return candidate ? `${symbol} · ${candidate.trim()}` : `${symbol} · 演示标的`;
}

function underlyingContextLine(summary: OptionsUnderlyingSummaryResponse | null, chain: OptionsChainResponse | null): string {
  const market = marketLabel(summary?.market);
  const source = sourceContextLabel(
    summary?.metadata?.sourceLabel
    || chain?.metadata?.sourceLabel
    || summary?.underlying?.source
    || chain?.underlying?.source
    || chain?.source,
  );
  return `${market} · ${source}`;
}

function expectedMoveSourceLabel(value?: string | null): string {
  if (value === 'straddle_mid') return '平值跨式中间价';
  if (value === 'iv_dte') return 'IV / DTE';
  if (value === 'unavailable') return '不可用';
  return '--';
}

function scenarioFrameStateLabel(value?: string | null): { label: string; tone: 'good' | 'warn' | 'risk' | 'info' } {
  if (value === 'ready') return { label: '可观察', tone: 'good' };
  if (value === 'observe_only') return { label: '仅观察', tone: 'warn' };
  if (value === 'insufficient') return { label: '证据不足', tone: 'warn' };
  if (value === 'blocked') return { label: '已阻断', tone: 'risk' };
  return { label: '等待证据更新', tone: 'info' };
}

function scenarioCoverageLabel(value?: string | null): string {
  if (value === 'strategy_compare_ready') return '策略比较覆盖';
  if (value === 'single_contract') return '单合约覆盖';
  if (value === 'missing_chain_data') return '缺少链路';
  if (value === 'decision_ready') return '判断级覆盖';
  return '等待证据更新';
}

function scenarioGateLabel(value?: string | null): string {
  if (value === 'clear') return '已通过';
  if (value === 'manual_review') return '人工复核';
  if (value === 'blocked') return '已阻断';
  return '待补证';
}

function scenarioMissingEvidenceLabel(value: string): string {
  if (value === 'provider authority') return '授权链路待补证';
  if (value === 'live chain') return '实时链路待补证';
  if (value === 'iv greeks') return '波动率与敏感度待补证';
  if (value === 'bid ask') return '双边报价待补证';
  if (value === 'volume') return '成交量待补证';
  if (value === 'open interest') return '持仓量待补证';
  const safeLabel = sanitizeUserFacingDataIssue(value, 'zh');
  if (safeLabel !== value) return safeLabel;
  return '证据待补充';
}

function scenarioNextEvidenceLabel(value: string): string {
  if (value.includes('provider authority')) return '补齐授权链路与实时链路证据';
  if (value.includes('Greeks') || value.includes('IV')) return '补齐波动率与敏感度证据';
  if (value.includes('OI') || value.includes('成交量') || value.includes('价差')) return '补齐成交深度与更紧价差证据';
  return '等待证据更新';
}

function structureCoverageLabel(value?: string | null): string {
  if (value === 'covered') return '已覆盖';
  if (value === 'partial') return '部分覆盖';
  if (value === 'missing') return '待补证';
  return '等待证据更新';
}

function structureLiquidityLabel(value?: string | null): string {
  if (value === 'complete') return '覆盖较完整';
  if (value === 'partial') return '部分可观察';
  if (value === 'missing') return '待补证';
  return '等待证据更新';
}

function structureExpirationLabel(value?: string | null): string {
  if (value === 'single_expiration') return '单一到期日';
  if (value === 'multi_expiration') return '多个到期日';
  if (value === 'missing') return '待补证';
  return '等待证据更新';
}

function structureBoundaryLabel(value?: string | null): string {
  if (value === 'demo_or_stale') return '不形成可用于判断的结论';
  if (value === 'live') return '仅供研究观察';
  return '仅供研究观察';
}

function structureNextStepLabel(value: string): string {
  const normalized = value.toLowerCase();
  if (normalized.includes('non-demo') || normalized.includes('freshness')) return '确认非演示链路新鲜度';
  if (normalized.includes('thin') || normalized.includes('liquidity')) return '复核低流动性合约行';
  if (normalized.includes('greek') || normalized.includes('iv')) return '补齐 IV 与敏感度证据';
  return '等待证据更新';
}

function scenarioAssumptionLines(assumptions?: Record<string, unknown> | null): string[] {
  if (!assumptions) return [];

  const lines: string[] = [];
  const inputMode = typeof assumptions.inputMode === 'string' ? assumptions.inputMode : null;
  const direction = typeof assumptions.direction === 'string' ? assumptions.direction : null;
  const targetPrice = typeof assumptions.targetPrice === 'number' ? assumptions.targetPrice : null;
  const targetDate = typeof assumptions.targetDate === 'string' ? assumptions.targetDate : null;
  const riskProfile = typeof assumptions.riskProfile === 'string' ? assumptions.riskProfile : null;
  const targetPriceStatus = typeof assumptions.targetPriceStatus === 'string' ? assumptions.targetPriceStatus : null;

  if (inputMode === 'decision') lines.push('当前来自判断回执');
  if (inputMode === 'strategy_compare') lines.push('当前来自观察结构样例比较');
  if (inputMode === 'scenario') lines.push('当前来自单结构情景推演');
  if (direction === 'bullish' || direction === 'bearish' || direction === 'neutral' || direction === 'volatility') {
    lines.push(`方向：${directionSummaryLabel(direction)}`);
  }
  if (typeof targetPrice === 'number' && Number.isFinite(targetPrice)) {
    lines.push(`假设价格：${money(targetPrice)}`);
  }
  if (targetDate) {
    lines.push(`目标日：${targetDate}`);
  }
  if (riskProfile === 'conservative' || riskProfile === 'balanced' || riskProfile === 'aggressive') {
    lines.push(`风险偏好：${RISK_PROFILE_OPTIONS.find((item) => item.value === riskProfile)?.label || '待确认'}`);
  }
  if (targetPriceStatus === 'target_above_breakeven') lines.push('假设价格仍在盈亏平衡线之上');
  if (targetPriceStatus === 'target_below_breakeven') lines.push('假设价格仍在盈亏平衡线之下');

  return lines.slice(0, 4);
}

function scenarioChainQualityLine(frame?: OptionsConsumerScenarioFrame | null): string {
  const chain = frame?.chainQuality;
  if (!chain) return '等待链路证据';

  const parts: string[] = [];
  if (chain.hasChain === true) parts.push('链路已加载');
  if (typeof chain.contractCount === 'number') parts.push(`${number(chain.contractCount)} 份合约`);
  if (typeof chain.callCount === 'number' || typeof chain.putCount === 'number') {
    parts.push(`Call ${number(chain.callCount)} / Put ${number(chain.putCount)}`);
  }
  if (chain.freshness === 'synthetic_delayed' || chain.freshness === 'mock' || chain.freshness === 'delayed') {
    parts.push('演示/延迟');
  } else if (chain.freshness === 'live') {
    parts.push('较新快照');
  }

  return parts.length ? parts.join(' · ') : '等待链路证据';
}

function buildScenarioEvidenceView(frame?: OptionsConsumerScenarioFrame | null): ScenarioEvidenceView | null {
  if (!frame) return null;

  const frameState = scenarioFrameStateLabel(frame.frameState);
  const missingEvidence = [...new Set(asArray(frame.missingEvidence).map(scenarioMissingEvidenceLabel))].slice(0, 4);
  const nextEvidenceNeeded = [...new Set(asArray(frame.nextEvidenceNeeded).map(scenarioNextEvidenceLabel))].slice(0, 3);
  const payoffLines = [
    typeof frame.payoffEvidence?.expectedMoveAbs === 'number' ? `预期波动：${money(frame.payoffEvidence.expectedMoveAbs)}` : null,
    typeof frame.payoffEvidence?.expectedMovePct === 'number' ? `预期波动幅度：${ratio(frame.payoffEvidence.expectedMovePct)}` : null,
    typeof frame.payoffEvidence?.payoffAtTarget === 'number' ? `假设价格下情景估算：${money(frame.payoffEvidence.payoffAtTarget)}` : null,
    frame.payoffEvidence?.expectedMoveSource ? `波动来源：${expectedMoveSourceLabel(frame.payoffEvidence.expectedMoveSource)}` : null,
  ].filter((item): item is string => Boolean(item)).slice(0, 4);
  const riskLines = [
    typeof frame.riskEvidence?.premiumAtRisk === 'number' ? `权利金风险：${money(frame.riskEvidence.premiumAtRisk)}` : null,
    typeof frame.riskEvidence?.maxLoss === 'number' ? `最大亏损：${money(frame.riskEvidence.maxLoss)}` : null,
    typeof frame.riskEvidence?.maxGain === 'number' ? `情景上沿：${money(frame.riskEvidence.maxGain)}` : null,
    typeof frame.riskEvidence?.breakeven === 'number' ? `盈亏平衡：${money(frame.riskEvidence.breakeven)}` : null,
    typeof frame.riskEvidence?.requiredMovePct === 'number' ? `所需波动：${ratio(frame.riskEvidence.requiredMovePct)}` : null,
  ].filter((item): item is string => Boolean(item)).slice(0, 4);
  const boundaryLines = [
    frame.frameState === 'observe_only' || frame.frameState === 'blocked' || frame.frameState === 'insufficient' ? '仅观察' : null,
    frame.noTradingBoundary?.noOrderPlacement ? '不触发执行动作' : null,
    frame.noTradingBoundary?.noPortfolioMutation ? '不改动现有持仓' : null,
    frame.noTradingBoundary?.analyticalOnly || frame.noTradingBoundary?.noTradingRecommendation ? '结论仅用于研究记录' : null,
  ].filter((item): item is string => Boolean(item));

  return {
    frameState: frameState.label,
    frameTone: frameState.tone,
    scenarioCoverage: scenarioCoverageLabel(frame.scenarioCoverage),
    chainQuality: scenarioChainQualityLine(frame),
    gateChips: [
      { label: '流动性', value: scenarioGateLabel(frame.liquidityGate), tone: frame.liquidityGate === 'clear' ? 'good' : frame.liquidityGate === 'blocked' ? 'risk' : 'warn' },
      { label: 'IV / Greeks', value: scenarioGateLabel(frame.ivGreeksGate), tone: frame.ivGreeksGate === 'clear' ? 'good' : frame.ivGreeksGate === 'blocked' ? 'risk' : 'warn' },
      { label: '价差', value: scenarioGateLabel(frame.spreadGate), tone: frame.spreadGate === 'clear' ? 'good' : frame.spreadGate === 'blocked' ? 'risk' : 'warn' },
    ],
    payoffLines,
    riskLines,
    assumptionLines: scenarioAssumptionLines(frame.assumptions),
    missingEvidence,
    nextEvidenceNeeded,
    boundaryLines,
  };
}

function noTradeReasonLabel(value?: string | null): string {
  if (value === 'data_quality_not_decision_grade') return '数据质量未达到可判断等级';
  if (value === 'all_candidates_have_weak_edge_or_unfavorable_risk_reward') return '观察结构样例边际优势或风险回报不足';
  if (value === 'no_supported_strategy_candidates') return '暂无可比较观察结构样例';
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
  if (isNonDecisionGrade(decision)) return '未达到可判断等级，仅供情景观察，暂不形成结论。';
  if (isDemoOrDelayedDecision(decision)) return OPTIONS_DEMO_BOUNDARY_COPY;
  return null;
}

function hasDemoOrStalePayload(
  summary: OptionsUnderlyingSummaryResponse | null,
  chain: OptionsChainResponse | null,
  decision: OptionsDecisionResponse | null,
): boolean {
  const markers = [
    summary?.underlying?.freshness,
    summary?.underlying?.source,
    summary?.metadata?.sourceLabel,
    summary?.optionsAvailability?.provider,
    ...asArray(summary?.metadata?.limitations),
    chain?.underlying?.freshness,
    chain?.underlying?.source,
    chain?.source,
    chain?.metadata?.sourceLabel,
    ...asArray(chain?.limitations),
    ...asArray(chain?.metadata?.limitations),
    decision?.freshness?.freshness,
    decision?.freshness?.source,
    decision?.dataQuality?.dataQualityTier,
    decision?.dataQuality?.sourceType,
    ...(decision?.metadata?.fixtureBacked ? ['fixture'] : []),
    ...(decision?.metadata?.syntheticData ? ['synthetic'] : []),
  ]
    .filter((value): value is string => typeof value === 'string' && value.trim().length > 0)
    .map((value) => value.toLowerCase());

  return markers.some((value) => (
    value.includes('fixture')
    || value.includes('mock')
    || value.includes('synthetic')
    || value.includes('demo')
    || value.includes('stale')
    || value.includes('delayed')
    || value.includes('fallback')
    || value.includes('cached')
  ));
}

const DataQualityBanner: React.FC<{
  availability: ConsumerAvailabilitySummary;
  summary: OptionsUnderlyingSummaryResponse | null;
  chain: OptionsChainResponse | null;
  decision: OptionsDecisionResponse | null;
}> = ({ availability, summary, chain, decision }) => {
  if (!hasDemoOrStalePayload(summary, chain, decision)) return null;

  return (
    <div
      data-testid="options-lab-data-quality-banner"
      className="mt-4 rounded-lg border border-amber-300/25 bg-amber-300/[0.07] px-3 py-3"
    >
      <div className="flex flex-wrap gap-2">
        <Pill tone="warn">仅供观察</Pill>
        <Pill tone="warn">当前不是实时期权链</Pill>
        <Pill tone="neutral">{availability.freshnessLabel}</Pill>
        <Pill tone="risk">不形成可用于判断的结论</Pill>
      </div>
      <p className="mt-2 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
        当前显示演示、延迟或本地验证快照；可用于理解页面结构与情景边界，不用于真实判断或外部执行。
      </p>
    </div>
  );
};

type ConsumerAvailabilityTone = 'neutral' | 'info' | 'warn' | 'risk' | 'good';
type ConsumerAvailabilityStateKey = 'UPDATING' | 'PAUSED' | 'UNAVAILABLE' | 'INSUFFICIENT' | 'PARTIAL' | 'AVAILABLE';

type ConsumerAvailabilitySummary = {
  stateKey: ConsumerAvailabilityStateKey;
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
      stateKey: 'UPDATING',
      stateLabel: '等待数据整理',
      stateTone: 'info',
      confidenceLabel: '置信度更新中',
      confidenceTone: 'info',
      freshnessLabel: freshness,
      explanation: OPTIONS_UPDATING_COPY,
    };
  }

  if (loadState.error) {
    return {
      stateKey: 'PAUSED',
      stateLabel: '情景分析已暂停',
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
      stateKey: hasChainRows ? 'PARTIAL' : 'UNAVAILABLE',
      stateLabel: hasChainRows ? '等待数据确认' : '数据暂不可用',
      stateTone: hasChainRows ? 'warn' : 'risk',
      confidenceLabel: '有限置信度',
      confidenceTone: 'warn',
      freshnessLabel: freshness,
      explanation: hasChainRows ? OPTIONS_INSUFFICIENT_COPY : OPTIONS_UNAVAILABLE_COPY,
    };
  }

  if (!hasChainRows || tier === 'insufficient') {
    return {
      stateKey: 'INSUFFICIENT',
      stateLabel: '等待数据确认',
      stateTone: 'warn',
      confidenceLabel: '有限置信度',
      confidenceTone: 'warn',
      freshnessLabel: freshness,
      explanation: OPTIONS_INSUFFICIENT_COPY,
    };
  }

  if (isNonDecisionGrade(decision)) {
    return {
      stateKey: tier === 'synthetic_demo_only' ? 'PAUSED' : 'PARTIAL',
      stateLabel: '等待数据确认',
      stateTone: 'warn',
      confidenceLabel: '有限置信度',
      confidenceTone: 'warn',
      freshnessLabel: freshness,
      explanation: tier === 'synthetic_demo_only' ? OPTIONS_MODULE_PAUSED_COPY : OPTIONS_INSUFFICIENT_COPY,
    };
  }

  if (!decision) {
    return {
      stateKey: 'PARTIAL',
      stateLabel: '等待数据确认',
      stateTone: 'warn',
      confidenceLabel: '置信度待确认',
      confidenceTone: 'warn',
      freshnessLabel: freshness,
      explanation: OPTIONS_INSUFFICIENT_COPY,
    };
  }

  return {
    stateKey: tier === 'delayed_usable' ? 'PARTIAL' : 'AVAILABLE',
    stateLabel: tier === 'delayed_usable' ? '等待数据确认' : '情景观察可继续',
    stateTone: tier === 'delayed_usable' ? 'warn' : 'good',
    confidenceLabel: confidenceCap != null ? `有限置信度 ${confidenceCap}` : '置信度较完整',
    confidenceTone: confidenceCap != null ? 'warn' : 'good',
    freshnessLabel: freshness,
    explanation: tier === 'delayed_usable' ? '已使用最近一次可用数据。' : '当前情景证据较完整，可继续做只读观察。',
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
  <div
    data-terminal-primitive="section-header"
    className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"
  >
    <div className="min-w-0 max-w-full">
      <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">
        <span className="inline-flex min-w-0 items-center gap-2">
        <Icon className="h-4 w-4 text-[color:var(--wolfy-accent)]" aria-hidden="true" />
        <span>{eyebrow}</span>
        </span>
      </p>
      <h2 className="mt-1 max-w-full break-words text-sm font-medium leading-6 text-[color:var(--wolfy-text-primary)]">
        {title}
      </h2>
    </div>
    {children ? <div className="min-w-0 sm:shrink-0">{children}</div> : null}
  </div>
);

const CompactMetricList: React.FC<{
  title: string;
  items: CompactMetricListItem[];
  testId?: string;
  className?: string;
  desktopColumnsClassName?: string;
  desktopContents?: boolean;
}> = ({ title, items, testId, className, desktopColumnsClassName = 'lg:grid-cols-3', desktopContents = false }) => (
  <div
    data-testid={testId}
    className={cn(
      innerBlockClass,
      'min-w-0 p-3',
      desktopContents ? 'lg:contents' : 'lg:border-0 lg:bg-transparent lg:p-0',
      className,
    )}
  >
    <p className={cn(labelClass, 'lg:hidden')}>{title}</p>
    <dl className={cn('mt-3 grid gap-2', desktopContents ? 'lg:contents' : cn('lg:mt-0', desktopColumnsClassName))}>
      {items.map((item) => (
        <div
          key={item.label}
          className="grid min-w-0 grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] gap-3 border-t border-[color:var(--wolfy-divider)] pt-2 first:border-t-0 first:pt-0 lg:block lg:rounded-md lg:border lg:border-[color:var(--wolfy-divider)] lg:bg-[var(--wolfy-surface-input)] lg:p-3 lg:first:border lg:first:pt-3"
        >
          <dt className={labelClass}>{item.label}</dt>
          <dd className={cn('min-w-0 text-right font-mono text-sm font-semibold leading-5 text-[color:var(--wolfy-text-primary)] lg:mt-2 lg:text-left', item.tone)}>
            {item.value}
          </dd>
        </div>
      ))}
    </dl>
  </div>
);

const WorkspaceRegion: React.FC<{
  eyebrow: string;
  title: string;
  summary: string;
  icon: React.ComponentType<{ className?: string }>;
  testId: string;
  children: React.ReactNode;
}> = ({ eyebrow, title, summary, icon, testId, children }) => (
  <section data-testid={testId} className={regionSectionClass}>
    <SectionHeader eyebrow={eyebrow} title={title} icon={icon} />
    <p className="mt-3 max-w-4xl text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
      {summary}
    </p>
    <div className="mt-5 grid gap-5">
      {children}
    </div>
  </section>
);

type PayoffChartPoint = {
  price: number;
  payoff: number;
  label?: string;
  tone?: 'neutral' | 'target' | 'boundary';
};

type PayoffVisualModel = {
  points: PayoffChartPoint[];
  minPrice: number;
  maxPrice: number;
  minPayoff: number;
  maxPayoff: number;
};

type IvVisualPoint = {
  strike: number;
  iv: number;
  side: OptionSide;
  contractSymbol: string;
};

type IvVisualModel = {
  points: IvVisualPoint[];
  minStrike: number;
  maxStrike: number;
  minIv: number;
  maxIv: number;
};

function finiteNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function padDomain(minimum: number, maximum: number, ratioValue: number, fallback = 1): [number, number] {
  const span = Math.abs(maximum - minimum);
  const padding = Math.max(span * ratioValue, fallback);
  if (span === 0) {
    return [Math.max(0, minimum - padding), maximum + padding];
  }
  return [Math.max(0, minimum - padding), maximum + padding];
}

function payoffBoundaryLabel(strategyType: OptionsStrategyType): string {
  if (strategyType === 'long_call') return '单腿多头情景上沿未设上沿，不代表可获利；图形仅示意边界变化。';
  if (strategyType === 'long_put') return '单腿多头收益受标的下行限制，图形仅示意边界变化。';
  if (strategyType === 'bull_call_spread') return '定义风险结构：亏损与收益边界都已封顶。';
  return '定义风险结构：下行收益与风险边界都已封顶。';
}

function buildPayoffVisualModel(
  strategy: OptionsStrategyComparison | null,
  underlyingPrice?: number | null,
  targetPrice?: number | null,
): PayoffVisualModel | null {
  if (!strategy) return null;

  const breakeven = finiteNumber(strategy.breakeven);
  const maxLoss = finiteNumber(strategy.maxLoss);
  const payoffAtTarget = finiteNumber(strategy.payoffAtTarget);
  const strikes = strategy.legs
    .map((leg) => finiteNumber(leg.strike))
    .filter((value): value is number => value != null)
    .sort((left, right) => left - right);

  if (breakeven == null || maxLoss == null || payoffAtTarget == null || strikes.length === 0) {
    return null;
  }

  const lowStrike = strikes[0];
  const highStrike = strikes[strikes.length - 1];
  const target = finiteNumber(targetPrice);
  const spot = finiteNumber(underlyingPrice);
  const maxGain = finiteNumber(strategy.maxGain);

  const priceAnchors = [lowStrike, highStrike, breakeven, target, spot].filter((value): value is number => value != null);
  const [minPrice, maxPrice] = padDomain(Math.min(...priceAnchors), Math.max(...priceAnchors), 0.18, 2);

  const points: PayoffChartPoint[] = [];
  const pushPoint = (price: number, payoff: number, label?: string, tone: PayoffChartPoint['tone'] = 'neutral') => {
    if (!Number.isFinite(price) || !Number.isFinite(payoff)) return;
    points.push({ price, payoff, label, tone });
  };

  switch (strategy.strategyType) {
    case 'long_call':
      pushPoint(minPrice, -Math.abs(maxLoss), '低位风险', 'boundary');
      pushPoint(breakeven, 0, '盈亏平衡');
      if (target != null) pushPoint(target, payoffAtTarget, '假设情景', 'target');
      else pushPoint(maxPrice, Math.max(payoffAtTarget, 0), '高位观察');
      break;
    case 'long_put':
      if (target != null) pushPoint(target, payoffAtTarget, '假设情景', 'target');
      else pushPoint(minPrice, Math.max(payoffAtTarget, 0), '下行观察', 'boundary');
      pushPoint(breakeven, 0, '盈亏平衡');
      pushPoint(maxPrice, -Math.abs(maxLoss), '高位风险', 'boundary');
      break;
    case 'bull_call_spread':
      pushPoint(minPrice, -Math.abs(maxLoss), '低位风险', 'boundary');
      pushPoint(lowStrike, -Math.abs(maxLoss));
      pushPoint(breakeven, 0, '盈亏平衡');
      pushPoint(highStrike, maxGain ?? payoffAtTarget, '收益上沿', 'boundary');
      pushPoint(maxPrice, maxGain ?? payoffAtTarget);
      if (target != null) pushPoint(target, payoffAtTarget, '假设情景', 'target');
      break;
    case 'bear_put_spread':
      pushPoint(minPrice, maxGain ?? payoffAtTarget, '收益上沿', 'boundary');
      pushPoint(lowStrike, maxGain ?? payoffAtTarget);
      if (target != null) pushPoint(target, payoffAtTarget, '假设情景', 'target');
      pushPoint(breakeven, 0, '盈亏平衡');
      pushPoint(highStrike, -Math.abs(maxLoss));
      pushPoint(maxPrice, -Math.abs(maxLoss), '高位风险', 'boundary');
      break;
  }

  const sortedPoints = points
    .sort((left, right) => left.price - right.price || left.payoff - right.payoff)
    .filter((point, index, items) => index === 0 || point.price !== items[index - 1].price || point.payoff !== items[index - 1].payoff);

  if (sortedPoints.length < 2) return null;

  const payoffValues = sortedPoints.map((point) => point.payoff);
  const [minPayoff, maxPayoff] = padDomain(Math.min(...payoffValues, 0), Math.max(...payoffValues, 0), 0.14, 40);

  return {
    points: sortedPoints,
    minPrice,
    maxPrice,
    minPayoff,
    maxPayoff,
  };
}

function buildIvVisualModel(chain: OptionsChainResponse | null): IvVisualModel | null {
  if (!chain) return null;

  const points = [...asArray(chain.calls), ...asArray(chain.puts)]
    .map((contract) => {
      const strike = finiteNumber(contract.strike);
      const iv = finiteNumber(contract.impliedVolatility);
      if (strike == null || iv == null) return null;
      return {
        strike,
        iv,
        side: contract.side,
        contractSymbol: contract.contractSymbol,
      } satisfies IvVisualPoint;
    })
    .filter((item): item is IvVisualPoint => item != null)
    .sort((left, right) => left.strike - right.strike);

  if (points.length === 0) return null;

  const strikes = points.map((point) => point.strike);
  const ivs = points.map((point) => point.iv);
  const [minStrike, maxStrike] = padDomain(Math.min(...strikes), Math.max(...strikes), 0.08, 1);
  const [minIv, maxIv] = padDomain(Math.min(...ivs), Math.max(...ivs), 0.16, 0.02);

  return {
    points,
    minStrike,
    maxStrike,
    minIv,
    maxIv,
  };
}

function selectedComparisonStrategy(
  decision?: OptionsDecisionResponse | null,
  comparison?: OptionsStrategyCompareResponse | null,
): OptionsStrategyComparison | null {
  const preferred = firstObservationStrategy(decision, comparison);
  const strategies = asArray(comparison?.strategies);
  if (!strategies.length) return null;
  if (!preferred) return strategies[0] ?? null;
  return strategies.find((strategy) => strategy.strategyType === preferred) ?? strategies[0] ?? null;
}

function scaleValue(value: number, minValue: number, maxValue: number, length: number): number {
  if (maxValue <= minValue) return length / 2;
  return ((value - minValue) / (maxValue - minValue)) * length;
}

function axisPrice(value: number): string {
  return `$${formatNumber(value, value >= 100 ? 0 : 2)}`;
}

const CompactVisualEmptyState: React.FC<{
  title: string;
  body: string;
  testId: string;
}> = ({ title, body, testId }) => (
  <div
    data-testid={testId}
    className="flex min-h-[13rem] flex-col justify-center rounded-md border border-dashed border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] px-4 py-5 text-center"
  >
    <p className="text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{title}</p>
    <p className="mt-2 text-xs leading-6 text-[color:var(--wolfy-text-secondary)]">{body}</p>
  </div>
);

const StrategyPayoffVisual: React.FC<{
  strategy: OptionsStrategyComparison | null;
  underlyingPrice?: number | null;
  targetPrice?: number | null;
}> = ({ strategy, underlyingPrice, targetPrice }) => {
  const model = buildPayoffVisualModel(strategy, underlyingPrice, targetPrice);

  if (!strategy || !model) {
    return (
      <CompactVisualEmptyState
        testId="options-lab-payoff-empty"
        title="收益边界待补证"
        body="当前缺少可绘制的收益边界。等待观察结构样例、腿部行权价与假设价格下情景估算同时可用后，再显示图形示意。"
      />
    );
  }

  const width = 420;
  const height = 220;
  const paddingLeft = 36;
  const paddingRight = 14;
  const paddingTop = 16;
  const paddingBottom = 28;
  const plotWidth = width - paddingLeft - paddingRight;
  const plotHeight = height - paddingTop - paddingBottom;
  const zeroY = paddingTop + (plotHeight - scaleValue(0, model.minPayoff, model.maxPayoff, plotHeight));
  const path = model.points.map((point, index) => {
    const x = paddingLeft + scaleValue(point.price, model.minPrice, model.maxPrice, plotWidth);
    const y = paddingTop + (plotHeight - scaleValue(point.payoff, model.minPayoff, model.maxPayoff, plotHeight));
    return `${index === 0 ? 'M' : 'L'} ${x} ${y}`;
  }).join(' ');
  const tickPrices = [model.minPrice, finiteNumber(targetPrice), model.maxPrice]
    .filter((value): value is number => value != null)
    .filter((value, index, items) => items.findIndex((item) => Math.abs(item - value) < 0.001) === index);

  return (
    <div data-testid="options-lab-payoff-visual" className="grid gap-3">
      <DataWorkbenchFrame>
        <div className="relative overflow-x-auto overscroll-x-contain">
          <div className="min-w-[20rem] p-3 sm:min-w-[26rem] sm:p-4">
            <svg
              viewBox={`0 0 ${width} ${height}`}
              role="img"
              aria-label={`到期收益示意，${strategyChineseLabel(strategy.strategyType)}`}
              className="h-auto w-full"
            >
              {[0.25, 0.5, 0.75].map((ratioValue) => {
                const y = paddingTop + plotHeight * ratioValue;
                return (
                  <line
                    key={ratioValue}
                    x1={paddingLeft}
                    y1={y}
                    x2={width - paddingRight}
                    y2={y}
                    stroke="rgba(148, 163, 184, 0.14)"
                    strokeDasharray="4 6"
                  />
                );
              })}
              <line x1={paddingLeft} y1={zeroY} x2={width - paddingRight} y2={zeroY} stroke="rgba(226,232,240,0.28)" />
              <path d={path} fill="none" stroke="rgba(129,140,248,0.95)" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />
              {model.points.map((point) => {
                const x = paddingLeft + scaleValue(point.price, model.minPrice, model.maxPrice, plotWidth);
                const y = paddingTop + (plotHeight - scaleValue(point.payoff, model.minPayoff, model.maxPayoff, plotHeight));
                const fill = point.tone === 'target'
                  ? 'rgba(52, 211, 153, 0.95)'
                  : point.tone === 'boundary'
                    ? 'rgba(251, 191, 36, 0.9)'
                    : 'rgba(226, 232, 240, 0.9)';
                return (
                  <g key={`${point.price}-${point.payoff}-${point.label || 'point'}`}>
                    <circle cx={x} cy={y} r="4.5" fill={fill} />
                    {point.label ? (
                      <text
                        x={x}
                        y={y - 10}
                        textAnchor="middle"
                        fill="rgba(226,232,240,0.78)"
                        fontSize="10"
                      >
                        {point.label}
                      </text>
                    ) : null}
                  </g>
                );
              })}
              {tickPrices.map((price) => {
                const x = paddingLeft + scaleValue(price, model.minPrice, model.maxPrice, plotWidth);
                return (
                  <g key={price}>
                    <line x1={x} y1={paddingTop + plotHeight} x2={x} y2={paddingTop + plotHeight + 5} stroke="rgba(226,232,240,0.32)" />
                    <text x={x} y={height - 6} textAnchor="middle" fill="rgba(148,163,184,0.78)" fontSize="10">
                      {axisPrice(price)}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
          <span aria-hidden="true" className="pointer-events-none absolute inset-y-0 right-0 w-8 bg-gradient-to-l from-[var(--wolfy-surface-console)] to-transparent sm:hidden" />
        </div>
      </DataWorkbenchFrame>
      <div className="grid gap-2 sm:grid-cols-3">
        <div className={cn(innerBlockClass, 'p-3')}>
          <p className={labelClass}>专业结构</p>
          <p className="mt-2 text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{strategyChineseLabel(strategy.strategyType)}</p>
        </div>
        <div className={cn(innerBlockClass, 'p-3')}>
          <p className={labelClass}>假设价格下情景估算</p>
          <p className={cn('mt-2 font-mono text-sm font-semibold', metricTone(strategy.payoffAtTarget))}>{money(strategy.payoffAtTarget)}</p>
        </div>
        <div className={cn(innerBlockClass, 'p-3')}>
          <p className={labelClass}>边界说明</p>
          <p className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">{payoffBoundaryLabel(strategy.strategyType)}</p>
        </div>
      </div>
    </div>
  );
};

const IvSmileVisual: React.FC<{ chain: OptionsChainResponse | null }> = ({ chain }) => {
  const model = buildIvVisualModel(chain);

  if (!model) {
    return (
      <CompactVisualEmptyState
        testId="options-lab-iv-empty"
        title="IV / 行权价快照待补证"
        body="当前缺少可绘制的 IV / 行权价快照。等待链上 IV 与行权价同时可用后，再显示 smile / skew 示意。"
      />
    );
  }

  const width = 420;
  const height = 220;
  const paddingLeft = 36;
  const paddingRight = 16;
  const paddingTop = 16;
  const paddingBottom = 28;
  const plotWidth = width - paddingLeft - paddingRight;
  const plotHeight = height - paddingTop - paddingBottom;
  const callPoints = model.points.filter((point) => point.side === 'call');
  const putPoints = model.points.filter((point) => point.side === 'put');
  const buildPath = (points: IvVisualPoint[]) => points.map((point, index) => {
    const x = paddingLeft + scaleValue(point.strike, model.minStrike, model.maxStrike, plotWidth);
    const y = paddingTop + (plotHeight - scaleValue(point.iv, model.minIv, model.maxIv, plotHeight));
    return `${index === 0 ? 'M' : 'L'} ${x} ${y}`;
  }).join(' ');

  return (
    <div data-testid="options-lab-iv-visual" className="grid gap-3">
      <DataWorkbenchFrame>
        <div className="relative overflow-x-auto overscroll-x-contain">
          <div className="min-w-[20rem] p-3 sm:min-w-[26rem] sm:p-4">
            <svg
              viewBox={`0 0 ${width} ${height}`}
              role="img"
              aria-label="IV 与行权价示意"
              className="h-auto w-full"
            >
              {[0.25, 0.5, 0.75].map((ratioValue) => {
                const y = paddingTop + plotHeight * ratioValue;
                return (
                  <line
                    key={ratioValue}
                    x1={paddingLeft}
                    y1={y}
                    x2={width - paddingRight}
                    y2={y}
                    stroke="rgba(148, 163, 184, 0.14)"
                    strokeDasharray="4 6"
                  />
                );
              })}
              {callPoints.length > 1 ? (
                <path d={buildPath(callPoints)} fill="none" stroke="rgba(96, 165, 250, 0.92)" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
              ) : null}
              {putPoints.length > 1 ? (
                <path d={buildPath(putPoints)} fill="none" stroke="rgba(248, 113, 113, 0.92)" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
              ) : null}
              {model.points.map((point) => {
                const x = paddingLeft + scaleValue(point.strike, model.minStrike, model.maxStrike, plotWidth);
                const y = paddingTop + (plotHeight - scaleValue(point.iv, model.minIv, model.maxIv, plotHeight));
                const fill = point.side === 'call' ? 'rgba(96, 165, 250, 0.95)' : 'rgba(248, 113, 113, 0.95)';
                return <circle key={point.contractSymbol} cx={x} cy={y} r="4" fill={fill} />;
              })}
              {[model.minStrike, model.maxStrike].map((strike) => {
                const x = paddingLeft + scaleValue(strike, model.minStrike, model.maxStrike, plotWidth);
                return (
                  <g key={strike}>
                    <line x1={x} y1={paddingTop + plotHeight} x2={x} y2={paddingTop + plotHeight + 5} stroke="rgba(226,232,240,0.32)" />
                    <text x={x} y={height - 6} textAnchor="middle" fill="rgba(148,163,184,0.78)" fontSize="10">
                      {axisPrice(strike)}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
          <span aria-hidden="true" className="pointer-events-none absolute inset-y-0 right-0 w-8 bg-gradient-to-l from-[var(--wolfy-surface-console)] to-transparent sm:hidden" />
        </div>
      </DataWorkbenchFrame>
      <div className="grid gap-2 sm:grid-cols-3">
        <div className={cn(innerBlockClass, 'p-3')}>
          <p className={labelClass}>Call / Put 点位</p>
          <p className="mt-2 text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{number(callPoints.length)} / {number(putPoints.length)}</p>
        </div>
        <div className={cn(innerBlockClass, 'p-3')}>
          <p className={labelClass}>IV 区间</p>
          <p className="mt-2 font-mono text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{ratio(model.minIv)} - {ratio(model.maxIv)}</p>
        </div>
        <div className={cn(innerBlockClass, 'p-3')}>
          <p className={labelClass}>图形说明</p>
          <p className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">仅反映当前链快照中的 IV / 行权价分布，不单独形成方向或执行结论。</p>
        </div>
      </div>
    </div>
  );
};

const ResearchVisualsPanel: React.FC<{
  decision: OptionsDecisionResponse | null;
  comparison: OptionsStrategyCompareResponse | null;
  chain: OptionsChainResponse | null;
  targetPrice?: number | null;
  className?: string;
}> = ({ decision, comparison, chain, targetPrice, className }) => {
  const strategy = selectedComparisonStrategy(decision, comparison);
  const underlyingPrice = chain?.underlying?.price;

  return (
    <section className={cn(panelClass, className)} data-testid="options-lab-visuals-panel">
      <SectionHeader eyebrow="图形证据" title="收益边界与 IV 快照" icon={LineChart}>
        <div className="flex flex-wrap gap-2">
          <Pill tone="info">只读观察</Pill>
          <Pill tone="warn">示意图</Pill>
        </div>
      </SectionHeader>
      <p className="mt-3 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
        先用现有观察结构样例与链快照观察收益边界和 IV 分布，再回到门控、缺口与风险约束做交叉复核。
      </p>
      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        <div className={cn(innerBlockClass, 'p-4')}>
          <p className={labelClass}>到期收益示意</p>
          <p className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">基于当前观察结构样例的现有收益边界字段绘制，仅用于情景观察。</p>
          <div className="mt-4">
            <StrategyPayoffVisual strategy={strategy} underlyingPrice={underlyingPrice} targetPrice={targetPrice} />
          </div>
        </div>
        <div className={cn(innerBlockClass, 'p-4')}>
          <p className={labelClass}>IV 偏斜示意</p>
          <p className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">基于当前期权链的 IV / 行权价点位绘制，仅反映快照形状，不延伸为交易结论。</p>
          <div className="mt-4">
            <IvSmileVisual chain={chain} />
          </div>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2 text-xs text-[color:var(--wolfy-text-muted)]">
        {[OPTIONS_SAFE_INSTRUCTION_COPY, OPTIONS_NON_ADVICE_COPY, OPTIONS_NO_ORDER_COPY, OPTIONS_NO_BROKER_COPY, OPTIONS_NO_PORTFOLIO_MUTATION_COPY].map((line) => (
          <Pill key={line} tone="neutral">{line}</Pill>
        ))}
      </div>
    </section>
  );
};

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
          控制区只记录假设；数据是否可判断以后续准备度和风险边界为准，不构成执行指令。
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
              <span className={labelClass}>假设价格</span>
              <input aria-label="假设价格" value={targetPrice} onChange={(event) => onTargetPriceChange(event.target.value)} className={fieldClass} inputMode="decimal" />
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
  if (!label?.trim()) return OPTIONS_NO_CONCLUSION_COPY;
  if (label === '数据不足，禁止判断' || tier === 'synthetic_demo_only' || tier === 'insufficient') return OPTIONS_NO_CONCLUSION_COPY;
  if (label === '不建议' || label === '不建议交易') return '观察边界明确';
  if (label === '仅观察' || label === '可关注替代结构') return '可记录低风险观察结构';
  return '仅供观察';
}

function directionSummaryLabel(value: OptionsDirection): string {
  if (value === 'bullish') return '上行情景假设';
  if (value === 'bearish') return '下行情景假设';
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
  if (!hasChainRows) return '先加载可用期权链，再进入观察结构样例与风险边界。';
  if (availability.stateKey === 'UPDATING') return '正在整理情景输入、样例结构与风险边界。';
  if (availability.stateKey === 'UNAVAILABLE' || availability.stateKey === 'PAUSED') {
    return '当前不形成判断，先保留输入与风险预算，等待下一次数据刷新。';
  }

  const observationStrategy = firstObservationStrategy(decision, comparison);
  if (isNonDecisionGrade(decision)) {
    return observationStrategy
      ? '当前只显示观察结构样例，判断等级未满足，需等待更完整的数据。'
      : '当前只满足观察条件，先记录风险边界与触发条件。';
  }

  if (observationStrategy) {
    return '当前显示样例顺序靠前的观察结构，先复核最大亏损、盈亏平衡与流动性边界。';
  }

  return availability.explanation;
}

function heroPrimaryTask(
  availability: ConsumerAvailabilitySummary,
  decision: OptionsDecisionResponse | null,
  comparison: OptionsStrategyCompareResponse | null,
  hasChainRows: boolean,
): string {
  if (!hasChainRows) return '先补齐可用到期日与期权链，再进入结构样例观察。';
  if (availability.stateKey === 'UPDATING') return '等待当前情景刷新完成，再阅读结构样例与风险边界。';
  if (availability.stateKey === 'UNAVAILABLE' || availability.stateKey === 'PAUSED') {
    return '先保留输入与风险预算，等待下一次数据刷新。';
  }

  const observationStrategy = firstObservationStrategy(decision, comparison);
  if (isNonDecisionGrade(decision)) {
    return observationStrategy
      ? '先看首个观察结构的最大亏损、盈亏平衡与流动性。'
      : '先完成情景输入，再等待可观察结构出现。';
  }

  if (observationStrategy) {
    return '先复核样例顺序靠前结构的风险边界，再下钻图形与链表。';
  }

  return '先设定情景参数，再等待结构样例与风险边界生成。';
}

function heroObservationScope(
  hasChainRows: boolean,
  decision: OptionsDecisionResponse | null,
  comparison: OptionsStrategyCompareResponse | null,
): string {
  if (!hasChainRows) return '当前可观察内容会在链表可用后显示。';
  if (firstObservationStrategy(decision, comparison)) {
    return '当前可先观察：结构样例、最大亏损、盈亏平衡与流动性边界。';
  }
  return '当前可先观察：期权链快照、风险边界与 IV 分布示意。';
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
  readinessGates: OptionsResearchReadiness | null;
  readiness: ReturnType<typeof buildConsumerResearchReadinessView>;
}> = ({ availability, summary, chain, decision, comparison, hasChainRows, readinessGates, readiness }) => {
  const underlying = summary?.underlying || chain?.underlying;
  const changeClass = metricTone(underlying?.changePct);
  const summaryLine = heroSummaryLine(availability, decision, comparison, hasChainRows);
  const primaryTask = heroPrimaryTask(availability, decision, comparison, hasChainRows);
  const observationScope = heroObservationScope(hasChainRows, decision, comparison);
  const displayName = underlyingDisplayName(summary, chain);
  const contextLine = underlyingContextLine(summary, chain);

  return (
    <section
      data-testid="options-lab-product-hero"
      className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[color:color-mix(in_srgb,var(--wolfy-surface-console)_94%,transparent)] px-4 py-4 md:px-5"
    >
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className={labelClass}>情景分析台</p>
            <Pill tone={availability.stateTone}>{availability.stateLabel}</Pill>
            <Pill tone={availability.confidenceTone}>{availability.confidenceLabel}</Pill>
          </div>
          <ConsumerResearchReadinessStrip
            readiness={readiness}
            title="研究就绪度"
            testId="options-lab-research-readiness-strip"
            className="mt-3"
          />
          <OptionsReadinessGateSummary
            readiness={readinessGates}
            testId="options-lab-readiness-gate-summary"
            className="mt-4"
          />
          <DataQualityBanner
            availability={availability}
            summary={summary}
            chain={chain}
            decision={decision}
          />
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <div className="min-w-0">
              <p className={labelClass}>当前标的</p>
              <p className="mt-1 text-lg font-semibold tracking-tight text-[color:var(--wolfy-text-primary)] md:text-xl">
                {displayName}
              </p>
              <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{contextLine}</p>
            </div>
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
          <div className={cn(innerBlockClass, 'p-3')} data-testid="options-lab-consumer-availability">
            <p className={labelClass}>当前主任务</p>
            <p className="mt-2 text-sm font-semibold text-[color:var(--wolfy-text-primary)]">
              {primaryTask}
            </p>
            <p className="mt-1 text-xs text-[color:var(--wolfy-text-muted)]">
              当前状态：{availability.explanation}
            </p>
            <p className="mt-1 text-xs text-[color:var(--wolfy-text-muted)]">
              {observationScope}
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

const ChainMetric: React.FC<{ label: string; value: string; className?: string }> = ({ label, value, className }) => (
  <div
    className={cn(
      'min-w-0 rounded-md border border-[color:var(--wolfy-divider)] bg-[color:color-mix(in_srgb,var(--wolfy-surface-input)_82%,transparent)] px-2.5 py-2',
      className,
    )}
  >
    <p className={labelClass}>{label}</p>
    <p className="mt-1 break-words font-mono text-sm text-[color:var(--wolfy-text-primary)]">{value}</p>
  </div>
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
        {(() => {
          const hasUnavailableGreekContracts = contracts.some((contract) => !hasAnyGreekValue(contract));

          return (
            <>
        <div className="max-h-[22rem] overflow-y-auto no-scrollbar md:hidden">
          <div className="grid gap-2" data-testid={`${testId}-mobile-list`}>
            {contracts.map((contract) => {
              const hasGreekValue = hasAnyGreekValue(contract);
              const greekMetrics = [
                { label: 'Delta', value: greekNumber(contract.delta, 2) },
                { label: 'Theta', value: greekNumber(contract.theta, 2), className: 'text-amber-200' },
                { label: 'Gamma', value: greekNumber(contract.gamma, 3) },
                { label: 'Vega', value: greekNumber(contract.vega, 2) },
                { label: 'Rho', value: greekNumber(contract.rho, 2) },
              ];

              return (
                <article
                  key={contract.contractSymbol}
                  data-testid={`${testId}-mobile-card-${contract.contractSymbol}`}
                  className="min-w-0 rounded-md border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] p-3 text-sm text-[color:var(--wolfy-text-secondary)]"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className={labelClass}>合约</p>
                      <p className="mt-1 break-all font-mono text-sm text-[color:var(--wolfy-text-primary)]">{contract.contractSymbol}</p>
                    </div>
                    <div className="shrink-0 text-right">
                      <p className={labelClass}>流动性</p>
                      <div className="mt-1">
                        <Pill tone={(contract.liquidityScore || 0) >= 75 ? 'good' : 'warn'}>
                          {number(contract.liquidityScore)}
                        </Pill>
                      </div>
                    </div>
                  </div>
                  <div className="mt-3 grid min-w-0 grid-cols-2 gap-2">
                    <ChainMetric label="行权价" value={money(contract.strike)} />
                    <ChainMetric label="中间价" value={money(contract.mid)} />
                    <ChainMetric label="买价 / 卖价" value={`${money(contract.bid)} / ${money(contract.ask)}`} className="col-span-2" />
                    <ChainMetric label="IV" value={ratio(contract.impliedVolatility)} />
                    <ChainMetric label="OI / 成交量" value={`${number(contract.openInterest)} / ${number(contract.volume)}`} />
                    {hasGreekValue ? (
                      greekMetrics.map((metric) => (
                        <ChainMetric
                          key={`${contract.contractSymbol}-${metric.label}`}
                          label={metric.label}
                          value={metric.value}
                          className={metric.className}
                        />
                      ))
                    ) : (
                      <ChainMetric label="Greeks" value={OPTIONS_DEMO_GREEKS_PLACEHOLDER} className="col-span-2" />
                    )}
                  </div>
                  {!hasGreekValue ? (
                    <p className="mt-3 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{OPTIONS_DEMO_GREEKS_EXPLANATION}</p>
                  ) : null}
                </article>
              );
            })}
          </div>
        </div>
        <div className="hidden max-h-[22rem] overflow-auto no-scrollbar md:block">
          <table data-testid={`${testId}-desktop-table`} className="w-full min-w-[720px] border-separate border-spacing-y-1 text-left">
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
                  <td className="px-3 py-2 font-mono">{greekNumber(contract.delta, 2)}</td>
                  <td className="px-3 py-2 font-mono text-amber-200">{greekNumber(contract.theta, 2)}</td>
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
        {hasUnavailableGreekContracts ? (
          <p className="mt-3 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{OPTIONS_DEMO_GREEKS_EXPLANATION}</p>
        ) : null}
            </>
          );
        })()}
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

type LabelSummary = {
  label: string;
  count: number;
};

function summarizeLabels(values: string[], mapLabel: (value: string) => string): LabelSummary[] {
  const counts = new Map<string, number>();
  values.forEach((value) => {
    const label = mapLabel(value);
    counts.set(label, (counts.get(label) ?? 0) + 1);
  });
  return Array.from(counts, ([label, count]) => ({ label, count }));
}

function formatLabelSummary(item: LabelSummary): string {
  return item.count > 1 ? `${item.label}（${item.count}项）` : item.label;
}

const StrategyRow: React.FC<{
  strategy: OptionsStrategyComparison;
  rank: number;
  highlighted: boolean;
  gateBlocked: boolean;
  alternative?: RankedAlternative;
}> = ({ strategy, rank, highlighted, gateBlocked, alternative }) => {
  const metrics: CompactMetricListItem[] = [
    {
      label: '最大亏损',
      value: money(alternative?.maxLoss ?? strategy.maxLoss),
      tone: 'text-[color:var(--wolfy-market-down)]',
    },
    {
      label: '情景上沿',
      value: (alternative?.maxGain ?? strategy.maxGain) == null ? '未设上沿，不代表可获利' : money(alternative?.maxGain ?? strategy.maxGain),
      tone: 'text-[color:var(--wolfy-market-up)]',
    },
    {
      label: '盈亏平衡',
      value: money(strategy.breakeven),
    },
    {
      label: '假设价格下情景估算',
      value: money(strategy.payoffAtTarget),
      tone: metricTone(strategy.payoffAtTarget),
    },
  ];

  return (
    <article
      data-testid={highlighted ? 'options-lab-primary-strategy-row' : undefined}
      className={cn(
        'min-w-0 rounded-lg border px-4 py-4 text-sm transition-colors',
        highlighted
          ? 'border-[color:color-mix(in_srgb,var(--wolfy-accent)_42%,transparent)] bg-[color:color-mix(in_srgb,var(--wolfy-accent)_10%,transparent)]'
          : 'border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] hover:border-[color:var(--wolfy-border-subtle)]',
      )}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs text-[color:var(--wolfy-text-muted)]">#{rank}</span>
            {highlighted ? <Pill tone={gateBlocked ? 'warn' : 'info'}>{gateBlocked ? `样例顺序 #${rank}` : '样例顺序靠前'}</Pill> : null}
          </div>
          <h3 className="mt-1 text-base font-semibold text-[color:var(--wolfy-text-primary)]">观察结构样例 #{rank}</h3>
          <p className="mt-1 break-words font-mono text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">
            专业结构：{strategyChineseLabel(strategy.strategyType)} · {strategyLabel(strategy.strategyType)}
          </p>
        </div>
        <div className="sm:shrink-0 sm:text-right">
          <p className={labelClass}>状态</p>
          <div className="mt-2">
            <Pill tone={gateBlocked ? 'warn' : 'info'}>
              {gateBlocked ? '未达判断等级' : strategyStatusLabel(strategy, alternative)}
            </Pill>
          </div>
        </div>
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        <CompactMetricList title="风险指标" items={metrics} testId="options-lab-strategy-metric-list" desktopContents />
        <div className={cn(innerBlockClass, 'p-3 lg:col-span-2')}>
          <p className={labelClass}>核心原因</p>
          <p className="mt-2 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">{strategyPrimaryReason(strategy, alternative)}</p>
        </div>
      </div>
    </article>
  );
};

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
  const limitationSummary = summarizeLabels(limitations, limitationLabel);
  return (
    <section className={cn(panelClass, className)} data-testid="options-lab-strategy-comparison">
      <SectionHeader eyebrow="主工作区" title="观察结构样例" icon={Layers3}>
        <div className="flex flex-wrap justify-end gap-2">
          <Pill tone="info">{freshness ? limitationLabel(String(freshness)) : '等待快照'}</Pill>
        </div>
      </SectionHeader>
      <p className="mt-3 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
        先把样例结构作为风险剖面阅读，再复核最大亏损、盈亏平衡与流动性边界。
      </p>
      {emptyMessage ? (
        <div className={cn(innerBlockClass, 'mt-5 border-dashed px-4 py-4 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]')}>
          <p className="text-sm font-semibold text-[color:var(--wolfy-text-primary)]">等待结构比较前提</p>
          <p className="mt-2">{emptyMessage}</p>
        </div>
      ) : null}
      {!emptyMessage && loading ? (
        <p className={cn(innerBlockClass, 'mt-5 px-4 py-5 font-mono text-sm text-[color:var(--wolfy-accent-soft)]')}>正在计算结构样例比较...</p>
      ) : null}
      {!emptyMessage && !loading && comparisonState.error ? (
        <TerminalNotice variant="danger" className="mt-5">{comparisonState.error}</TerminalNotice>
      ) : null}
      {!emptyMessage && !loading && !comparisonState.error && strategies.length === 0 ? (
        <TerminalEmptyState title="暂无可比较结构样例" className="mt-5">
          当前假设下暂无可比较结构样例。
        </TerminalEmptyState>
      ) : null}
      {!emptyMessage && !loading && !comparisonState.error && strategies.length > 0 ? (
        <DenseRows data-testid="options-lab-strategy-grid" className="mt-5 grid gap-4 divide-y-0 space-y-0 2xl:grid-cols-2">
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
        <span className={labelClass}>样例约束</span>
        <p className="mt-2">
          {limitationSummary.length ? limitationSummary.map(formatLabelSummary).join(' · ') : '当前数据可用于情景比较'}
        </p>
      </div>
    </section>
  );
};

const ScenarioEvidencePanel: React.FC<{
  frame: OptionsConsumerScenarioFrame;
  className?: string;
}> = ({ frame, className }) => {
  const view = buildScenarioEvidenceView(frame);
  if (!view) return null;

  return (
    <section className={cn(panelClass, className)} data-testid="options-lab-scenario-evidence">
      <SectionHeader eyebrow="证据工作区" title="情景证据" icon={LineChart}>
        <Pill tone={view.frameTone}>{view.frameState}</Pill>
      </SectionHeader>
      <p className="mt-3 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
        先确认覆盖范围、链路质量与缺口，再读收益/风险证据；当前结论始终停留在只读观察边界内。
      </p>
      <div className="mt-5 grid gap-3 xl:grid-cols-2">
        <div className={cn(innerBlockClass, 'p-4')}>
          <p className={labelClass}>证据状态</p>
          <p className="mt-2 text-base font-semibold text-[color:var(--wolfy-text-primary)]">{view.frameState}</p>
        </div>
        <div className={cn(innerBlockClass, 'p-4')}>
          <p className={labelClass}>情景覆盖</p>
          <p className="mt-2 text-base font-semibold text-[color:var(--wolfy-text-primary)]">{view.scenarioCoverage}</p>
        </div>
      </div>
      <div className="mt-3 grid gap-3 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <div className={cn(innerBlockClass, 'p-4')}>
          <p className={labelClass}>链路质量</p>
          <p className="mt-2 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">{view.chainQuality}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {view.gateChips.map((chip) => (
              <Pill key={`${chip.label}-${chip.value}`} tone={chip.tone}>{chip.label}：{chip.value}</Pill>
            ))}
          </div>
        </div>
        <div className={cn(innerBlockClass, 'p-4')}>
          <p className={labelClass}>假设摘要</p>
          <div className="mt-2 space-y-1.5 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
            {view.assumptionLines.length ? view.assumptionLines.map((line) => (
              <p key={line}>{line}</p>
            )) : <p>当前假设仍待补齐。</p>}
          </div>
        </div>
      </div>
      <div className="mt-3 grid gap-3 xl:grid-cols-2">
        <div className={cn(innerBlockClass, 'p-4')}>
          <p className={labelClass}>收益证据</p>
          <div className="mt-2 space-y-1.5 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
            {view.payoffLines.length ? view.payoffLines.map((line) => (
              <p key={line}>{line}</p>
            )) : <p>当前缺少可读的收益证据。</p>}
          </div>
        </div>
        <div className={cn(innerBlockClass, 'p-4')}>
          <p className={labelClass}>风险证据</p>
          <div className="mt-2 space-y-1.5 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
            {view.riskLines.length ? view.riskLines.map((line) => (
              <p key={line}>{line}</p>
            )) : <p>当前缺少可读的风险证据。</p>}
          </div>
        </div>
      </div>
      <div className={cn(innerBlockClass, 'mt-3 p-4')}>
        <p className={labelClass}>补证与只读边界</p>
        <div className="mt-3 grid gap-4 xl:grid-cols-3">
          <div className="min-w-0">
            <p className="text-xs font-semibold text-[color:var(--wolfy-text-primary)]">缺失证据</p>
            <div className="mt-2 space-y-1.5 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
              {view.missingEvidence.length ? view.missingEvidence.map((line) => (
                <p key={line}>{line}</p>
              )) : <p>当前未发现额外缺口。</p>}
            </div>
          </div>
          <div className="min-w-0">
            <p className="text-xs font-semibold text-[color:var(--wolfy-text-primary)]">下一步补证</p>
            <div className="mt-2 space-y-1.5 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
              {view.nextEvidenceNeeded.length ? view.nextEvidenceNeeded.map((line) => (
                <p key={line}>{line}</p>
              )) : <p>等待下一次证据更新。</p>}
            </div>
          </div>
          <div className="min-w-0">
            <p className="text-xs font-semibold text-[color:var(--wolfy-text-primary)]">只读边界</p>
            <div className="mt-2 space-y-1.5 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
              {view.boundaryLines.length ? view.boundaryLines.map((line) => (
                <p key={line}>{line}</p>
              )) : <p>当前仅保留研究记录边界。</p>}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

const StructureSignalPacketPanel: React.FC<{
  packet?: OptionsStructureSignalPacket | null;
  className?: string;
}> = ({ packet, className }) => {
  if (!packet) return null;

  const nextSteps = [...new Set(asArray(packet.researchNextSteps).map(structureNextStepLabel))].slice(0, 3);
  const missingGreeksCount = asArray(packet.missingGreeks).length;
  const skewSpread = finiteNumber(packet.skewObservation?.callPutIvSpread);
  const liquidity = packet.liquidityObservation;
  const expiration = packet.expirationCoverage;
  const metrics: CompactMetricListItem[] = [
    {
      label: 'Gamma 覆盖',
      value: structureCoverageLabel(packet.gammaCoverageState),
      tone: packet.gammaCoverageState === 'covered' ? 'text-[color:var(--wolfy-market-up)]' : 'text-amber-200',
    },
    {
      label: 'IV 覆盖',
      value: structureCoverageLabel(packet.ivCoverageState),
      tone: packet.ivCoverageState === 'covered' ? 'text-[color:var(--wolfy-market-up)]' : 'text-amber-200',
    },
    {
      label: '偏斜观察',
      value: skewSpread == null ? '等待证据更新' : `Call / Put IV 差 ${ratio(skewSpread)}`,
    },
    {
      label: '流动性观察',
      value: structureLiquidityLabel(liquidity?.state),
      tone: liquidity?.state === 'complete' ? 'text-[color:var(--wolfy-market-up)]' : 'text-amber-200',
    },
    {
      label: '到期覆盖',
      value: structureExpirationLabel(expiration?.state),
    },
    {
      label: '演示/延迟边界',
      value: structureBoundaryLabel(packet.staleOrDemoBoundary?.state),
      tone: packet.staleOrDemoBoundary?.state === 'demo_or_stale' ? 'text-amber-200' : undefined,
    },
  ];

  return (
    <section className={cn(panelClass, className)} data-testid="options-lab-structure-signal-packet">
      <SectionHeader eyebrow="结构观察" title="结构信号包" icon={Layers3}>
        <div className="flex flex-wrap justify-end gap-2">
          <Pill tone="info">仅供研究观察</Pill>
          <Pill tone="warn">不触发执行</Pill>
        </div>
      </SectionHeader>
      <p className="mt-3 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
        基于当前已加载期权链汇总 Gamma、IV、偏斜、流动性与到期覆盖；只描述证据覆盖，不形成可用于判断的结论。
      </p>
      <div className="mt-5">
        <CompactMetricList
          title="结构信号包"
          items={metrics}
          testId="options-lab-structure-signal-metrics"
          desktopColumnsClassName="lg:grid-cols-3"
        />
      </div>
      <div className="mt-4 grid gap-3 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
        <div className={cn(innerBlockClass, 'p-4')}>
          <p className={labelClass}>覆盖摘要</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Pill tone="neutral">合约 {number(liquidity?.contractCount)}</Pill>
            <Pill tone={Number(liquidity?.thinLiquidityCount || 0) > 0 ? 'warn' : 'good'}>
              低流动性 {number(liquidity?.thinLiquidityCount)}
            </Pill>
            <Pill tone={missingGreeksCount > 0 ? 'warn' : 'good'}>
              敏感度缺口 {number(missingGreeksCount)}
            </Pill>
            <Pill tone="neutral">最近 DTE {number(expiration?.nearestDte)}</Pill>
          </div>
        </div>
        <div className={cn(innerBlockClass, 'p-4')}>
          <p className={labelClass}>观察边界</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {packet.observationBoundary?.researchOnly ? <Pill tone="info">仅供研究观察</Pill> : null}
            {packet.observationBoundary?.orderPlacement === false ? <Pill tone="warn">不触发执行</Pill> : null}
            {packet.observationBoundary?.brokerExecution === false ? <Pill tone="warn">不连接外部执行通道</Pill> : null}
            {packet.observationBoundary?.portfolioMutation === false ? <Pill tone="neutral">不改动投资组合</Pill> : null}
          </div>
        </div>
      </div>
      <div className={cn(innerBlockClass, 'mt-4 p-4')}>
        <p className={labelClass}>下一步补证</p>
        <div className="mt-2 space-y-1.5 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
          {nextSteps.length ? nextSteps.map((line) => (
            <p key={line}>{line}</p>
          )) : <p>当前先保留观察记录，等待证据更新。</p>}
        </div>
      </div>
    </section>
  );
};

const DecisionPanel: React.FC<{ decisionState: DecisionState; emptyMessage: string | null; className?: string }> = ({ decisionState, emptyMessage, className }) => {
  const decision = decisionState.decision;
  const label = decisionStatusLabel(decision);
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
  const labelTone = label === OPTIONS_NO_CONCLUSION_COPY || label === '不建议'
    ? 'text-[color:var(--wolfy-market-down)]'
    : label === '仅观察'
      ? 'text-[color:var(--wolfy-accent-soft)]'
      : 'text-amber-100';
  const primaryStrategy = isNonDecisionGrade(decision) ? null : optimizer?.preferredStrategyKey || null;
  const observationCandidate = primaryStrategy || rankedAlternatives[0]?.strategyKey || decision?.betterAlternative?.strategyType || null;
  const boundaryReason = noTradeReasonLabel(optimizer?.noTradeReason);
  const observationDetail = observationCandidate
    ? `专业结构：${strategyChineseLabel(observationCandidate)}${boundaryReason !== '暂无' ? ` · 边界原因：${boundaryReason}` : ''}`
    : `边界原因：${boundaryReason}`;
  const decisionTags = [...new Set([
    freshnessLabel(decision?.freshness?.freshness),
    ivRankStatus === 'available' ? 'IV 分位可用' : 'IV 分位不可用',
  ].filter((item) => item && item !== '--'))].slice(0, 3);
  const decisionMetrics: CompactMetricListItem[] = [
    {
      label: '情景质量',
      value: number(decision?.tradeQualityScore),
    },
    {
      label: '最大亏损',
      value: money(decision?.riskReward?.maxLoss),
      tone: 'text-[color:var(--wolfy-market-down)]',
    },
    {
      label: '预期波动',
      value: money(expectedMove?.expectedMoveAbs),
    },
    {
      label: 'IV / 敏感度',
      value: number(decision?.ivGreeks?.ivReadiness),
      tone: 'text-[color:var(--wolfy-accent-soft)]',
    },
  ];
  return (
    <section className={cn(panelClass, className)} data-testid="options-lab-decision-engine">
      <SectionHeader eyebrow="判断内容" title="情景判断" icon={ShieldCheck}>
        <div className="flex flex-wrap justify-end gap-2">
          <Pill tone={label === OPTIONS_NO_CONCLUSION_COPY || label.includes('不建议') ? 'risk' : 'warn'}>{label}</Pill>
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
                    ? '观察结构样例已满足基础边界，仍需复核风险字段。'
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
            <CompactMetricList
              title="判断指标"
              items={decisionMetrics}
              testId="options-lab-decision-metric-list"
              className="mt-4"
              desktopColumnsClassName="xl:grid-cols-4"
            />
            <div className={cn(innerBlockClass, 'mt-4 p-3')}>
              <p className={labelClass}>观察结构样例</p>
              <p className="mt-2 text-base font-semibold text-[color:var(--wolfy-text-primary)]">{observationCandidate ? '观察结构样例' : '暂无可判断结构'}</p>
              <p className="mt-2 text-sm leading-6 text-[color:var(--wolfy-accent-soft)]/80">
                {observationDetail}
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
    ...asArray(decision?.failClosedReasonCodes),
    ...asArray(chain?.limitations),
    ...asArray(chain?.metadata?.limitations),
  ];
  const liquidityWarnings = asArray(decision?.liquidity?.liquidityWarnings);
  const ivWarnings = [
    ...asArray(decision?.ivGreeks?.warnings),
    ...asArray(decision?.expectedMove?.expectedMoveWarnings),
  ];
  const riskWarnings = asArray(decision?.riskWarnings);
  const warningSummary = summarizeLabels([
    loading ? '等待快照' : null,
    error ? '部分外部数据暂不可用' : null,
    decision?.dataQuality?.dataQualityTier === 'synthetic_demo_only' ? '不可作为交易信号' : null,
    ...dataWarnings,
    ...liquidityWarnings,
    ...ivWarnings,
    ...riskWarnings,
    '需人工复核',
  ].filter(Boolean) as string[], warningLabel);
  const visibleWarnings = warningSummary.slice(0, 3);
  const hiddenWarnings = warningSummary.slice(3);
  const dataState = loading
    ? '等待快照'
    : error
      ? '部分外部数据暂不可用'
      : dataTierLabel(decision?.dataQuality?.dataQualityTier);
  const topState = decisionStatusLabel(decision);
  return (
    <section className={cn(panelClass, className)} data-testid="options-lab-risk-boundary-panel">
      <SectionHeader eyebrow="风险控制" title="风险边界" icon={AlertTriangle}>
        <Pill tone={topState === OPTIONS_NO_CONCLUSION_COPY ? 'risk' : 'info'}>
          {topState}
        </Pill>
      </SectionHeader>
      <div className="mt-5 grid gap-3 text-sm">
        <div className="rounded-md border border-[color:color-mix(in_srgb,var(--wolfy-market-down)_34%,transparent)] bg-[color:color-mix(in_srgb,var(--wolfy-market-down)_10%,transparent)] p-3">
          <p className={labelClass}>观察边界</p>
          <p className="mt-2 text-sm font-semibold text-[color:var(--wolfy-market-down)]">{topState}</p>
          <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{boundaryCopy || '仅供观察，暂不形成结论。'}</p>
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
              key={warning.label}
              data-testid="options-lab-visible-risk-warning"
              className="flex gap-2 rounded-md border border-amber-300/20 bg-amber-300/5 px-3 py-2 text-xs leading-5 text-amber-200"
            >
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-200" aria-hidden="true" />
              <span>{formatLabelSummary(warning)}</span>
            </li>
          ))}
        </ul>
        <ConsoleDisclosure title="更多限制" summary="默认折叠，避免打断主工作区">
          {hiddenWarnings.length ? (
            <div className="flex flex-wrap gap-2">
              {hiddenWarnings.map((warning) => (
                <Pill key={warning.label} tone="neutral">{formatLabelSummary(warning)}</Pill>
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
    return '流动性与敏感度都有限时，先看最大亏损与价差，再决定是否保留研究记录。';
  }
  if (hasLiquidity) {
    return '价差偏宽或成交深度不足时，名义上沿不等于实际可实现结果，先观察定义风险结构。';
  }
  if (hasSensitivity) {
    return 'IV 分位或 Greeks 不完整时，只能看方向边界，不能把到期前收益当成稳定结论。';
  }
  return '优先同时看价差、OI、IV 与 Theta，再决定是否保留研究记录。';
}

function nextActionCopy(
  loading: boolean,
  error: string | null,
  hasChainRows: boolean,
  decision: OptionsDecisionResponse | null,
): string {
  if (loading) return '等待链表、观察结构样例与风险边界刷新完成。';
  if (error) return '稍后重试或更换标的，当前不要扩展判断。';
  if (!hasChainRows) return '先加载可用到期日与期权链，再进入结构样例比较。';
  if (isNonDecisionGrade(decision)) return '先记录观察结构与风险预算，等待更完整数据后再复核。';
  return '先复核首个观察结构的最大亏损、盈亏平衡与流动性，再决定是否保留研究记录。';
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
  className?: string;
}> = ({ state, targetPrice, targetDate, riskBudget, className }) => (
  <ConsoleDisclosure
    data-testid="options-lab-analysis-details"
    title="数据注记"
    summary="默认折叠，仅在需要时展开方法与限制。"
    className={cn('border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)]', className)}
  >
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
      <div className={cn(innerBlockClass, 'p-4 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]')}>
        <p className={labelClass}>输入摘要</p>
        <p className="mt-2">假设价格 {targetPrice || '--'}，目标日 {targetDate || '--'}，风险预算 {riskBudget || '--'}。</p>
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
        <ConsumerWorkspaceScope className="min-h-0 flex-1">
          <ConsumerWorkspacePageShell>
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
          </ConsumerWorkspacePageShell>
        </ConsumerWorkspaceScope>
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
          error: '结构样例比较暂不可用。请稍后重试或调整假设。',
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
          error: '结构样例比较暂不可用。请稍后重试或调整假设。',
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
    if (state.loading) return '正在加载基础数据，稍后将自动计算结构样例比较。';
    if (state.error) return '期权链暂不可用，结构样例比较已暂停。';
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
    if (!Number.isFinite(targetPriceValue) || targetPriceValue <= 0 || !targetDate.trim()) return '先补齐假设价格与目标日期。';
    return null;
  }, [hasChainRows, state.chain, state.error, state.expirations, state.loading, state.summary, targetDate, targetPrice]);
  const consumerAvailability = useMemo(
    () => consumerAvailabilitySummary(state, comparisonState, decisionState, hasChainRows),
    [comparisonState, decisionState, hasChainRows, state],
  );
  const summaryStripItems = useMemo<SummaryStripItem[]>(() => {
    const topCandidate = firstObservationStrategy(decisionState.decision, comparisonState.comparison);
    const maxLoss = decisionState.decision?.riskReward?.maxLoss;
    const scenarioMeta = targetDate.trim() ? `目标日 ${targetDate}` : '补齐目标日后可比较结构样例';
    const candidateMeta = topCandidate ? `专业结构：${strategyChineseLabel(topCandidate)}` : '当前未形成可判断结构';
    const riskValue = typeof maxLoss === 'number' && Number.isFinite(maxLoss)
      ? `最大亏损 ${money(maxLoss)}`
      : noTradeReasonLabel(decisionState.decision?.optimizer?.noTradeReason);

    return [
      {
        label: '输入情景',
        value: `${directionSummaryLabel(direction)} · 假设价格 ${targetPrice || '--'}`,
        meta: scenarioMeta,
      },
      {
        label: '当前可观察',
        value: topCandidate ? '观察结构样例' : '暂无可判断结构',
        meta: candidateMeta,
      },
      {
        label: '风险边界',
        value: riskValue,
        meta: riskBudget ? `风险预算 ${riskBudget}` : '先定义可承受亏损',
      },
    ];
  }, [comparisonState.comparison, decisionState.decision, direction, riskBudget, targetDate, targetPrice]);
  const optionsResearchReadiness = useMemo(
    () => extractOptionsResearchReadiness(
      state.summary as Record<string, unknown> | null | undefined,
      state.expirations as Record<string, unknown> | null | undefined,
      state.chain as Record<string, unknown> | null | undefined,
      comparisonState.comparison as Record<string, unknown> | null | undefined,
      decisionState.decision as Record<string, unknown> | null | undefined,
    ),
    [comparisonState.comparison, decisionState.decision, state.chain, state.expirations, state.summary],
  );
  const optionsResearchReadinessView = useMemo(
    () => buildConsumerResearchReadinessView(
      convertOptionsReadiness(optionsResearchReadiness) || inferOptionsResearchReadiness(decisionState.decision),
      'zh',
    ),
    [decisionState.decision, optionsResearchReadiness],
  );
  const scenarioEvidenceFrame = useMemo(
    () => decisionState.decision?.optionsConsumerScenarioFrame || comparisonState.comparison?.optionsConsumerScenarioFrame || null,
    [comparisonState.comparison, decisionState.decision],
  );

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
                <Pill tone="warn">不构成执行指令</Pill>
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
              readinessGates={optionsResearchReadiness}
              readiness={optionsResearchReadinessView}
            />

            <WorkspaceRegion
              testId="options-lab-input-region"
              eyebrow="工作流起点"
              title="情景参数"
              summary="先设定标的、方向、假设价格、目标日期与风险预算；这里仅记录研究输入，不直接形成执行结论。"
              icon={Search}
            >
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
              <div className="border-t border-[color:var(--wolfy-divider)] pt-5">
                <DecisionSummaryStrip items={summaryStripItems} />
              </div>
            </WorkspaceRegion>

            <WorkspaceRegion
              testId="options-lab-output-region"
              eyebrow="研究工作区"
              title="分析结果"
              summary="输出区统一承载观察结构样例、情景判断、图形证据、链表与风险边界。先看结构与风险，再下钻图形和明细。"
              icon={BarChart3}
            >
              <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(18rem,0.82fr)] xl:items-start">
                <StrategyComparisonPanel
                  comparisonState={comparisonState}
                  decision={decisionState.decision}
                  loading={comparisonState.loading}
                  emptyMessage={comparisonEmptyMessage}
                  chain={state.chain}
                  className="xl:col-start-1 xl:row-start-1"
                />
                <DecisionPanel
                  decisionState={decisionState}
                  emptyMessage={decisionEmptyMessage}
                  className="xl:col-start-1 xl:row-start-2"
                />
                <RiskBoundaryPanel
                  decision={decisionState.decision}
                  chain={state.chain}
                  loading={state.loading || decisionState.loading}
                  error={state.error || decisionState.error}
                  className="xl:col-start-2 xl:row-start-1"
                />
                <ContextRailPanel
                  decision={decisionState.decision}
                  loading={state.loading || comparisonState.loading || decisionState.loading}
                  error={state.error || comparisonState.error || decisionState.error}
                  hasChainRows={hasChainRows}
                  className="xl:col-start-2 xl:row-start-2"
                />
                <ResearchVisualsPanel
                  decision={decisionState.decision}
                  comparison={comparisonState.comparison}
                  chain={state.chain}
                  targetPrice={Number.isFinite(Number(targetPrice)) ? Number(targetPrice) : null}
                  className="xl:col-start-1 xl:row-start-3"
                />
                <StructureSignalPacketPanel
                  packet={state.chain?.optionsStructureSignalPacket}
                  className="xl:col-start-2 xl:row-start-3"
                />
                {scenarioEvidenceFrame ? (
                  <ScenarioEvidencePanel frame={scenarioEvidenceFrame} className="xl:col-start-1 xl:row-start-4" />
                ) : null}

                <WolfyShellSurface variant="console" padding="sm" className="overflow-hidden xl:col-start-1 xl:row-start-5">
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
                        保留输入、观察结构样例与风险边界，等待下一次数据更新。
                      </TerminalEmptyState>
                    </div>
                  ) : null}
                </WolfyShellSurface>

                <MethodologyDisclosure
                  state={state}
                  targetPrice={targetPrice}
                  targetDate={targetDate}
                  riskBudget={riskBudget}
                  className="xl:col-start-1 xl:row-start-6"
                />
              </div>
            </WorkspaceRegion>
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
