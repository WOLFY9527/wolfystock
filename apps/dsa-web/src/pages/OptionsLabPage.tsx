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
import { cn } from '../utils/cn';
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

const fieldClass = 'h-10 w-full rounded-lg border border-white/10 bg-white/[0.02] px-3 font-mono text-sm text-white outline-none transition-all placeholder:text-white/20 focus:border-emerald-400/50 focus:bg-white/[0.05]';
const labelClass = 'text-[10px] font-bold uppercase tracking-widest text-white/40';
const panelClass = 'min-w-0 rounded-[16px] border border-white/5 bg-white/[0.02] p-5 backdrop-blur-md';
const innerBlockClass = 'rounded-xl border border-white/[0.02] bg-black/20';
const primaryButtonClass = 'rounded-lg bg-gradient-to-r from-blue-600 to-purple-600 px-6 py-2.5 text-sm font-medium text-white shadow-[0_0_15px_rgba(139,92,246,0.3)] transition-all duration-300 hover:from-blue-500 hover:to-purple-500 disabled:cursor-not-allowed disabled:opacity-50';

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

function dataTierLabel(value?: string | null): string {
  if (value === 'live_usable') return '实时可分析';
  if (value === 'delayed_usable') return '行情延迟，可观察';
  if (value === 'synthetic_demo_only') return '演示/延迟数据';
  if (value === 'insufficient') return '数据不足';
  return '--';
}

function freshnessLabel(value?: string | null): string {
  if (value === 'live') return '实时';
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

function metricTone(value?: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'text-white/75';
  if (value > 0) return 'text-emerald-300';
  if (value < 0) return 'text-rose-300';
  return 'text-white/75';
}

const Pill: React.FC<{ children: React.ReactNode; tone?: 'neutral' | 'info' | 'warn' | 'risk' | 'good' }> = ({ children, tone = 'neutral' }) => {
  const toneClass = {
    neutral: 'border-white/10 bg-white/5 text-white/50',
    info: 'border-cyan-300/20 bg-cyan-400/5 text-cyan-300',
    warn: 'border-amber-300/20 bg-amber-400/5 text-amber-300',
    risk: 'border-rose-400/20 bg-rose-500/5 text-rose-300',
    good: 'border-emerald-300/20 bg-emerald-400/5 text-emerald-300',
  }[tone];
  return <span className={cn('inline-flex rounded-md border px-2.5 py-1 font-mono text-xs tracking-tight', toneClass)}>{children}</span>;
};

const SectionHeader: React.FC<{
  eyebrow: string;
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  children?: React.ReactNode;
}> = ({ eyebrow, title, icon: Icon, children }) => (
  <div className="flex min-w-0 items-start justify-between gap-4">
    <div className="min-w-0">
      <div className="flex items-center gap-2">
        <Icon className="h-4 w-4 text-cyan-200" aria-hidden="true" />
        <p className={labelClass}>{eyebrow}</p>
      </div>
      <h2 className="mt-1 text-lg font-semibold text-white">{title}</h2>
    </div>
    {children}
  </div>
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
  <div className="grid grid-cols-2 gap-2 rounded-xl border border-white/[0.02] bg-black/20 p-1 sm:grid-cols-4" aria-label={ariaLabel}>
    {options.map((option) => (
      <button
        key={option.value}
        className={cn(
          'h-9 rounded-lg px-3 text-sm font-medium transition-all',
          option.value === value
            ? 'border border-white/10 bg-white/10 text-white shadow-[0_0_18px_rgba(34,211,238,0.12)]'
            : 'border border-transparent bg-transparent text-white/45 hover:bg-white/[0.04] hover:text-white/75',
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
  <section className={cn(panelClass, 'order-3 xl:order-none xl:col-span-4')} data-testid="options-lab-assumptions-panel">
    <SectionHeader eyebrow="假设输入" title="期权假设" icon={Search} />
    <div className="mt-6 grid grid-cols-1 gap-x-4 gap-y-6">
      <label className="flex flex-col gap-1.5">
        <span className={labelClass}>标的代码</span>
        <div className="flex gap-2">
          <input
            aria-label="标的代码"
            className={fieldClass}
            value={symbol}
            onChange={(event) => onSymbolChange(event.target.value.toUpperCase())}
            placeholder="TEM"
          />
          <button
            type="button"
            onClick={onSubmit}
            className={cn(primaryButtonClass, 'h-10 shrink-0 px-5 py-0')}
          >
            执行
          </button>
        </div>
      </label>
      <div className="flex flex-col gap-1.5">
        <span className={labelClass}>方向</span>
        <SegmentedButtons options={DIRECTION_OPTIONS} value={direction} onChange={onDirectionChange} ariaLabel="方向假设" />
      </div>
      <label className="flex flex-col gap-1.5">
        <span className={labelClass}>到期日</span>
        <div className="relative">
          <select
            aria-label="到期日"
            className="h-10 w-full truncate appearance-none rounded-lg border border-white/10 bg-white/[0.02] px-3 pr-10 font-mono text-sm text-white outline-none transition-all focus:border-emerald-400/50 focus:bg-white/[0.05]"
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
          <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/40" aria-hidden="true" />
        </div>
      </label>
      <div className="grid grid-cols-1 gap-x-4 gap-y-6 md:grid-cols-2">
        <label className="flex flex-col gap-1.5">
          <span className={labelClass}>目标价格</span>
          <input aria-label="目标价格" value={targetPrice} onChange={(event) => onTargetPriceChange(event.target.value)} className={fieldClass} inputMode="decimal" />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className={labelClass}>目标日期</span>
          <input aria-label="目标日期" value={targetDate} onChange={(event) => onTargetDateChange(event.target.value)} className={fieldClass} placeholder="2026-08-21" />
        </label>
        <label className="flex flex-col gap-1.5 md:col-span-2">
          <span className={labelClass}>风险预算</span>
          <input aria-label="风险预算" value={riskBudget} onChange={(event) => onRiskBudgetChange(event.target.value)} className={fieldClass} inputMode="decimal" />
        </label>
      </div>
      <div className="flex flex-col gap-1.5">
        <span className={labelClass}>风险偏好</span>
        <SegmentedButtons options={RISK_PROFILE_OPTIONS} value={riskProfile} onChange={onRiskProfileChange} ariaLabel="风险偏好" />
      </div>
    </div>
  </section>
);

function decisionStatusLabel(decision?: OptionsDecisionResponse | null): string {
  const label = decision?.decisionLabel || decision?.optimizer?.optimizerLabel;
  const tier = decision?.dataQuality?.dataQualityTier;
  if (label === '数据不足，禁止判断' || tier === 'synthetic_demo_only' || tier === 'insufficient') return '数据不足，禁止判断';
  if (label === '不建议' || label === '不建议交易') return '可观察，不建议开仓';
  if (label === '仅观察' || label === '可关注替代结构') return '可构建低风险观察策略';
  if (label === '有条件可交易') return '适合等待更好定价';
  return '仅供观察';
}

const SnapshotPanel: React.FC<{
  summary: OptionsUnderlyingSummaryResponse | null;
  chain: OptionsChainResponse | null;
  decision: OptionsDecisionResponse | null;
}> = ({ summary, chain, decision }) => {
  const underlying = summary?.underlying || chain?.underlying;
  const expectedMove = decision?.expectedMove;
  const ivRank = decision?.ivRank ?? decision?.ivGreeks?.ivRank;
  const ivPercentile = decision?.ivPercentile ?? decision?.ivGreeks?.ivPercentile;
  return (
    <section className={cn(panelClass, 'order-1 xl:order-none xl:col-span-12')} data-testid="options-lab-snapshot-panel">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,2fr)] xl:items-center">
        <SectionHeader eyebrow="标的快照" title="标的快照" icon={LineChart}>
          <Pill tone="info">只读观察</Pill>
        </SectionHeader>
        <div className={cn(innerBlockClass, 'px-3 py-2 text-sm leading-6 text-white/75 xl:text-right')}>
          <span className="text-cyan-100">{decisionStatusLabel(decision)}</span>
          <span className="mx-2 text-white/25">·</span>
          <span>不可作为交易信号</span>
        </div>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6" data-testid="options-lab-snapshot-metric-grid">
        <div className={cn(innerBlockClass, 'p-3')}>
          <p className={labelClass}>标的</p>
          <p className="mt-2 font-mono text-xl font-semibold tracking-tight text-white">{summary?.symbol || chain?.symbol || '--'}</p>
        </div>
        <div className={cn(innerBlockClass, 'p-3')}>
          <p className={labelClass}>最新价</p>
          <p className="mt-2 font-mono text-xl font-semibold tracking-tight text-white">{money(underlying?.price)}</p>
        </div>
        <div className={cn(innerBlockClass, 'p-3')}>
          <p className={labelClass}>涨跌幅</p>
          <p className="mt-2 font-mono text-xl font-semibold tracking-tight text-emerald-300">{ratio(underlying?.changePct)}</p>
        </div>
        <div className={cn(innerBlockClass, 'p-3')}>
          <p className={labelClass}>IV 分位</p>
          <p className="mt-2 font-mono text-xl font-semibold tracking-tight text-cyan-300">{ivRank == null ? '--' : number(ivRank, 1)} / {ivPercentile == null ? '--' : number(ivPercentile, 1)}</p>
        </div>
        <div className={cn(innerBlockClass, 'p-3')}>
          <p className={labelClass}>预期波动</p>
          <p className="mt-2 font-mono text-xl font-semibold tracking-tight text-white">{money(expectedMove?.expectedMoveAbs)}</p>
          <p className="mt-1 text-xs text-white/40">{ratio(expectedMove?.expectedMovePct)}</p>
        </div>
        <div className={cn(innerBlockClass, 'p-3')}>
          <p className={labelClass}>数据状态</p>
          <p className="mt-2 font-mono text-sm font-semibold tracking-tight text-cyan-300">{freshnessLabel(decision?.freshness?.freshness || underlying?.freshness)}</p>
          <p className="mt-1 truncate text-xs text-white/35">{underlying?.asOf || '--'}</p>
        </div>
      </div>
    </section>
  );
};

const ChainTable: React.FC<{ title: string; contracts: OptionContract[]; testId: string; className?: string }> = ({ title, contracts, testId, className }) => (
  <section className={cn(panelClass, 'min-h-[280px]', className)} data-testid="options-lab-chain-panel">
    <SectionHeader eyebrow="期权链" title={title} icon={BarChart3} />
    {contracts.length === 0 ? (
      <p className={cn(innerBlockClass, 'mt-5 px-4 py-5 text-sm text-white/45')}>暂无数据，保留假设面板与风险提示。</p>
    ) : (
      <div className="mt-4 overflow-x-auto no-scrollbar" data-testid={testId}>
        <table className="w-full min-w-[720px] border-separate border-spacing-y-1 text-left">
          <thead className="text-[10px] uppercase tracking-[0.16em] text-white/35">
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
              <tr key={contract.contractSymbol} className="rounded-xl border border-white/[0.03] bg-white/[0.015] text-xs text-white/72">
                <td className="rounded-l-xl px-3 py-2 font-mono text-xs text-white">{contract.contractSymbol}</td>
                <td className="px-3 py-2 font-mono">{money(contract.strike)}</td>
                <td className="px-3 py-2 font-mono">{money(contract.mid)}</td>
                <td className="px-3 py-2 font-mono">{money(contract.bid)} / {money(contract.ask)}</td>
                <td className="px-3 py-2 font-mono">{ratio(contract.impliedVolatility)}</td>
                <td className="px-3 py-2 font-mono">{number(contract.delta, 2)}</td>
                <td className="px-3 py-2 font-mono text-amber-200">{number(contract.theta, 2)}</td>
                <td className="px-3 py-2 font-mono">{number(contract.openInterest)} / {number(contract.volume)}</td>
                <td className="rounded-r-xl px-3 py-2">
                  <Pill tone={(contract.liquidityScore || 0) >= 75 ? 'good' : 'warn'}>
                    {number(contract.liquidityScore)}
                  </Pill>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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
  alternative?: RankedAlternative;
}> = ({ strategy, rank, highlighted, alternative }) => (
  <article
    data-testid={highlighted ? 'options-lab-primary-strategy-row' : undefined}
    className={cn(
      'grid min-w-0 gap-3 rounded-xl border px-3 py-2 text-sm transition-all xl:grid-cols-[minmax(0,1.4fr)_0.7fr_repeat(4,minmax(0,0.8fr))_minmax(0,1.5fr)] xl:items-center',
      highlighted
        ? 'border-cyan-300/25 bg-cyan-400/[0.06] shadow-[0_0_20px_rgba(34,211,238,0.08)]'
        : 'border-white/[0.03] bg-white/[0.015] hover:border-white/10 hover:bg-white/[0.03]',
    )}
  >
    <div className="min-w-0">
      <div className="flex items-center gap-2">
        <span className="font-mono text-xs text-white/35">#{rank}</span>
        {highlighted ? <Pill tone="info">首选观察</Pill> : null}
      </div>
      <h3 className="mt-1 truncate text-sm font-semibold text-white">{strategyChineseLabel(strategy.strategyType)}</h3>
      <p className="mt-0.5 truncate font-mono text-[11px] text-white/35">{strategyLabel(strategy.strategyType)}</p>
    </div>
    <div>
      <p className={labelClass}>状态</p>
      <p className="mt-1 text-xs font-semibold text-cyan-100">{strategyStatusLabel(strategy, alternative)}</p>
    </div>
    <div>
      <p className={labelClass}>最大亏损</p>
      <p className="mt-1 font-mono text-xs text-rose-300">{money(alternative?.maxLoss ?? strategy.maxLoss)}</p>
    </div>
    <div>
      <p className={labelClass}>最大收益</p>
      <p className="mt-1 font-mono text-xs text-emerald-300">{(alternative?.maxGain ?? strategy.maxGain) == null ? '不封顶' : money(alternative?.maxGain ?? strategy.maxGain)}</p>
    </div>
    <div>
      <p className={labelClass}>盈亏平衡</p>
      <p className="mt-1 font-mono text-xs text-white/80">{money(strategy.breakeven)}</p>
    </div>
    <div>
      <p className={labelClass}>情景收益</p>
      <p className={cn('mt-1 font-mono text-xs', metricTone(strategy.payoffAtTarget))}>{money(strategy.payoffAtTarget)}</p>
    </div>
    <div className="min-w-0">
      <p className={labelClass}>核心原因</p>
      <p className="mt-1 truncate text-xs text-white/62">{strategyPrimaryReason(strategy, alternative)}</p>
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
  const rankMap = new Map(rankedAlternatives.map((alternative, index) => [alternative.strategyKey, { alternative, index }]));
  const rankedStrategies = [...strategies].sort((left, right) => {
    const leftRank = rankMap.get(left.strategyType)?.index ?? Number.MAX_SAFE_INTEGER;
    const rightRank = rankMap.get(right.strategyType)?.index ?? Number.MAX_SAFE_INTEGER;
    if (leftRank !== rightRank) return leftRank - rightRank;
    return (right.riskRewardRatio || 0) - (left.riskRewardRatio || 0);
  });
  return (
    <section className={cn(panelClass, className)} data-testid="options-lab-strategy-comparison">
      <SectionHeader eyebrow="候选矩阵" title="策略候选" icon={Layers3}>
        <div className="flex flex-wrap justify-end gap-2">
          <Pill tone="info">{freshness ? `数据状态：${limitationLabel(String(freshness))}` : '数据状态：等待快照'}</Pill>
          <Pill tone="neutral">风险提示已合并</Pill>
        </div>
      </SectionHeader>
      {emptyMessage ? (
        <div className={cn(innerBlockClass, 'mt-5 border-dashed border-white/10 px-4 py-4 text-sm leading-6 text-white/55')}>
          <p className="text-sm font-semibold text-white/78">等待策略对比前提</p>
          <p className="mt-2">{emptyMessage}</p>
        </div>
      ) : null}
      {!emptyMessage && loading ? (
        <p className={cn(innerBlockClass, 'mt-5 px-4 py-5 font-mono text-sm text-cyan-100')}>正在计算策略对比...</p>
      ) : null}
      {!emptyMessage && !loading && comparisonState.error ? (
        <p className="mt-5 rounded-xl border border-rose-400/20 bg-rose-500/5 px-4 py-4 text-sm text-rose-300">{comparisonState.error}</p>
      ) : null}
      {!emptyMessage && !loading && !comparisonState.error && strategies.length === 0 ? (
        <p className={cn(innerBlockClass, 'mt-5 px-4 py-5 text-sm text-white/45')}>当前假设下暂无可比较策略。</p>
      ) : null}
      {!emptyMessage && !loading && !comparisonState.error && strategies.length > 0 ? (
        <div className="mt-5 grid gap-2">
          {rankedStrategies.map((strategy, index) => (
            <StrategyRow
              key={strategy.strategyType}
              strategy={strategy}
              rank={index + 1}
              highlighted={index === 0}
              alternative={rankMap.get(strategy.strategyType)?.alternative}
            />
          ))}
        </div>
      ) : null}
      <div className={cn(innerBlockClass, 'mt-5 p-4 text-sm leading-6 text-white/58')}>
        <span className={labelClass}>数据说明</span>
        <p className="mt-2">
          {limitations.length ? limitations.map(limitationLabel).join(' · ') : '当前数据可用于情景比较'}
        </p>
      </div>
    </section>
  );
};

const DecisionMetric: React.FC<{ label: string; value: string; tone?: string }> = ({ label, value, tone = 'text-white' }) => (
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
  const labelTone = label === '数据不足，禁止判断' || label === '不建议'
    ? 'text-rose-200'
    : label === '仅观察'
      ? 'text-cyan-100'
      : 'text-amber-100';
  const primaryStrategy = optimizer?.preferredStrategyKey || null;
  const observationCandidate = primaryStrategy || rankedAlternatives[0]?.strategyKey || decision?.betterAlternative?.strategyType || null;
  const decisionTags = [...new Set([
    dataTierLabel(decision?.dataQuality?.dataQualityTier),
    freshnessLabel(decision?.freshness?.freshness),
    ivRankStatus === 'available' ? 'IV 分位可用' : 'IV 分位不可用',
  ].filter((item) => item && item !== '--'))].slice(0, 3);
  return (
    <section className={cn(panelClass, className)} data-testid="options-lab-decision-engine">
      <SectionHeader eyebrow="决策中枢" title="策略决策" icon={ShieldCheck}>
        <div className="flex flex-wrap justify-end gap-2">
          <Pill tone={label.includes('禁止') || label.includes('不建议') ? 'risk' : 'warn'}>{label}</Pill>
          <Pill tone="info">{dataTierLabel(decision?.dataQuality?.dataQualityTier)}</Pill>
        </div>
      </SectionHeader>
      {emptyMessage ? (
        <p className={cn(innerBlockClass, 'mt-5 border-dashed border-white/10 px-4 py-4 text-sm text-white/55')}>{emptyMessage}</p>
      ) : null}
      {!emptyMessage && decisionState.loading ? (
        <p className={cn(innerBlockClass, 'mt-5 px-4 py-5 font-mono text-sm text-cyan-100')}>正在计算策略决策...</p>
      ) : null}
      {!emptyMessage && !decisionState.loading && decisionState.error ? (
        <p className="mt-5 rounded-xl border border-rose-400/20 bg-rose-500/5 px-4 py-4 text-sm text-rose-300">{decisionState.error}</p>
      ) : null}
      {!emptyMessage && !decisionState.loading && !decisionState.error && !decision ? (
        <p className={cn(innerBlockClass, 'mt-5 px-4 py-5 text-sm text-white/45')}>等待策略决策。</p>
      ) : null}
      {!emptyMessage && !decisionState.loading && !decisionState.error && decision ? (
        <div className="mt-5 grid gap-4">
          <div
            data-testid="options-lab-decision-summary"
            className="rounded-xl border border-cyan-300/10 bg-white/[0.02] p-4"
          >
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0">
                <p className={labelClass}>一线结论</p>
                <p className={cn('mt-2 text-xl font-semibold', labelTone)}>{decisionStatusLabel(decision)}</p>
                <p className="mt-2 text-sm leading-6 text-white/62">
                  {primaryStrategy
                    ? `主要策略：${strategyChineseLabel(primaryStrategy)}`
                    : '暂无可执行策略'}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {decisionTags.map((tag) => (
                  <Pill key={tag} tone={tag.includes('不足') || tag.includes('不可用') ? 'warn' : 'info'}>{tag}</Pill>
                ))}
              </div>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <DecisionMetric label="情景质量" value={number(decision?.tradeQualityScore)} />
              <DecisionMetric label="最大亏损" value={money(decision?.riskReward?.maxLoss)} tone="text-rose-300" />
              <DecisionMetric label="预期波动" value={money(expectedMove?.expectedMoveAbs)} />
              <DecisionMetric label="IV / 敏感度" value={number(decision?.ivGreeks?.ivReadiness)} tone="text-cyan-100" />
            </div>
            <div className={cn(innerBlockClass, 'mt-4 p-3')}>
              <p className={labelClass}>主要策略</p>
              <p className="mt-2 text-base font-semibold text-white">{observationCandidate ? strategyChineseLabel(observationCandidate) : '暂无可执行策略'}</p>
              <p className="mt-2 text-sm leading-6 text-cyan-100/70">
                {primaryStrategy
                  ? `可观察结构：${strategyChineseLabel(primaryStrategy)}`
                  : `不交易：${noTradeReasonLabel(optimizer?.noTradeReason)}`}
              </p>
            </div>
          </div>
          <div className="grid gap-3 lg:grid-cols-3">
            <div className={cn(innerBlockClass, 'p-4')}>
              <p className={labelClass}>盈亏平衡</p>
              <p className="mt-2 font-mono text-base font-semibold text-white">{money(decision?.breakeven?.breakeven)}</p>
              <p className="mt-1 text-sm text-white/52">所需波动：{ratio(decision?.breakeven?.requiredMovePct)}</p>
            </div>
            <div className={cn(innerBlockClass, 'p-4')}>
              <p className={labelClass}>IV 分位</p>
              {ivRankStatus === 'available' ? (
                <>
                  <p className="mt-2 font-mono text-base font-semibold tracking-tight text-cyan-300">{number(ivRank, 1)} / {number(ivPercentile, 1)}</p>
                  <p className="mt-1 text-sm text-white/52">来源已清理为用户可读状态</p>
                </>
              ) : (
                <>
                  <p className="mt-2 font-mono text-base font-semibold tracking-tight text-white/62">IV 分位不可用</p>
                  <p className="mt-1 text-sm text-white/52">缺少历史 IV 或代理序列，置信度降低。</p>
                </>
              )}
            </div>
            <div className={cn(innerBlockClass, 'p-4')}>
              <p className={labelClass}>预期波动</p>
              <p className="mt-2 font-mono text-base font-semibold tracking-tight text-white">{money(expectedMove?.expectedMoveAbs)}</p>
              <p className="mt-1 text-sm text-white/52">{ratio(expectedMove?.expectedMovePct)} · {expectedMoveSourceLabel(expectedMove?.expectedMoveSource)}</p>
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
    <section className={cn(panelClass, 'order-4 xl:order-none', className)} data-testid="options-lab-risk-boundary-panel">
      <SectionHeader eyebrow="风险控制" title="风险边界" icon={AlertTriangle}>
        <Pill tone={topState.includes('禁止') ? 'risk' : 'info'}>
          {topState}
        </Pill>
      </SectionHeader>
      <div className="mt-5 grid gap-3 text-sm">
        <div className="rounded-xl border border-rose-400/20 bg-rose-500/5 p-3">
          <p className={labelClass}>禁止判断</p>
          <p className="mt-2 text-sm font-semibold text-rose-200">{topState}</p>
          <p className="mt-1 text-xs leading-5 text-white/45">仅供观察，不可作为交易信号。</p>
        </div>
        <div className={cn(innerBlockClass, 'flex items-center justify-between gap-3 p-3')}>
          <span className={labelClass}>数据状态</span>
          <Pill tone={dataState.includes('不足') || dataState.includes('延迟') ? 'warn' : 'info'}>{dataState}</Pill>
        </div>
        <ul className="grid gap-2" aria-label="风险边界警示">
          {visibleWarnings.map((warning) => (
            <li
              key={warning}
              data-testid="options-lab-visible-risk-warning"
              className="flex gap-2 rounded-xl border border-amber-300/20 bg-amber-400/5 px-3 py-2 text-xs leading-5 text-amber-300"
            >
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-300" aria-hidden="true" />
              <span>{warningLabel(warning)}</span>
            </li>
          ))}
        </ul>
        {hiddenWarnings.length ? (
          <details className="rounded-xl border border-white/[0.03] bg-white/[0.015] px-3 py-2 text-xs text-white/48">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-white/55">
              <span>更多限制</span>
              <ChevronDown className="h-3.5 w-3.5 text-white/30" aria-hidden="true" />
            </summary>
            <div className="mt-2 flex flex-wrap gap-2">
              {hiddenWarnings.map((warning) => (
                <Pill key={warning} tone="neutral">{warningLabel(warning)}</Pill>
              ))}
            </div>
          </details>
        ) : (
          <details className="rounded-xl border border-white/[0.03] bg-white/[0.015] px-3 py-2 text-xs text-white/48">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-white/55">
              <span>更多限制</span>
              <ChevronDown className="h-3.5 w-3.5 text-white/30" aria-hidden="true" />
            </summary>
            <p className="mt-2">暂无更多可见限制，仍需人工复核。</p>
          </details>
        )}
        <p className="text-xs leading-5 text-white/35">
          仅供观察，不可作为交易信号。本页不接入交易执行、组合变更或通知路由。
        </p>
      </div>
    </section>
  );
};

const MethodologyDisclosure: React.FC<{
  state: LoadState;
  targetPrice: string;
  targetDate: string;
  riskBudget: string;
}> = ({ state, targetPrice, targetDate, riskBudget }) => (
  <details data-testid="options-lab-analysis-details" className={cn(panelClass, 'xl:col-span-12')}>
    <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-white/75">
      <span className="inline-flex items-center gap-2 text-sm font-semibold">
        <BarChart3 className="h-4 w-4 text-cyan-200" aria-hidden="true" />
        计算假设 / 数据说明 / 限制说明
      </span>
      <ChevronDown className="h-4 w-4 text-white/35" aria-hidden="true" />
    </summary>
    <div className="mt-5 grid grid-cols-1 gap-4 xl:grid-cols-3">
      <div className={cn(innerBlockClass, 'p-4 text-sm leading-6 text-white/58')}>
        <p className={labelClass}>计算假设</p>
        <p className="mt-2">目标价 {targetPrice || '--'}，目标日 {targetDate || '--'}，风险预算 {riskBudget || '--'}。收益结构只表达显式假设下的情景结果。</p>
      </div>
      <div className={cn(innerBlockClass, 'p-4 text-sm leading-6 text-white/58')}>
        <p className={labelClass}>数据说明</p>
        <p className="mt-2">
          {[...asArray(state.chain?.limitations), ...asArray(state.chain?.metadata?.limitations)].map(limitationLabel).join(' · ') || '当前数据可用于情景观察'}
        </p>
      </div>
      <div className={cn(innerBlockClass, 'p-4 text-sm leading-6 text-white/58')}>
        <p className={labelClass}>限制说明</p>
        <p className="mt-2">期权可能归零，IV、Theta、流动性与价差会改变到期前估值。本模块只做只读情景分析，不提供收益承诺。</p>
      </div>
    </div>
  </details>
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
      <main className="min-h-screen w-full bg-[#050505] px-4 py-5 text-white md:px-8 xl:px-10">
        <section className="mx-auto flex w-full max-w-[920px] flex-col gap-4 rounded-[24px] border border-rose-300/20 bg-white/[0.02] p-5 backdrop-blur-md md:p-6">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-1 h-5 w-5 shrink-0 text-amber-200" aria-hidden="true" />
            <div className="min-w-0">
              <p className={labelClass}>期权实验室</p>
              <h1 className="mt-2 text-xl font-semibold text-white">{OPTIONS_LAB_CRASH_FALLBACK}</h1>
              <p className="mt-3 text-sm leading-6 text-white/58">基础工作区仍保持只读。此处仅显示已清理的错误类别，不展示堆栈或供应商载荷。</p>
            </div>
          </div>
          <div className="rounded-2xl border border-white/5 bg-black/20 p-4 text-sm text-white/55">
            数据说明：暂时无法完成渲染，页面已隐藏内部错误详情。
          </div>
        </section>
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
          error: '策略决策暂不可用。请稍后重试或调整假设。',
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
    if (state.loading) return '正在加载基础数据，稍后将自动计算策略决策。';
    if (state.error) return '期权链暂不可用，策略决策已暂停。';
    const targetPriceValue = Number(targetPrice);
    if (!state.summary || !state.expirations || !state.chain || !hasChainRows) return '先加载合约链后，再进入策略决策。';
    if (!Number.isFinite(targetPriceValue) || targetPriceValue <= 0 || !targetDate.trim()) return '先补齐目标价格与目标日期。';
    return null;
  }, [hasChainRows, state.chain, state.error, state.expirations, state.loading, state.summary, targetDate, targetPrice]);

  return (
    <main className="w-full overflow-x-hidden py-4 text-white">
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 px-4 xl:px-8" data-testid="options-lab-page-root">
        <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-12" data-testid="options-lab-bento-grid">
          <SnapshotPanel summary={state.summary} chain={state.chain} decision={decisionState.decision} />
          <DecisionPanel decisionState={decisionState} emptyMessage={decisionEmptyMessage} className="order-2 xl:order-none xl:col-span-5" />
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
          <RiskBoundaryPanel
            decision={decisionState.decision}
            chain={state.chain}
            loading={state.loading || decisionState.loading}
            error={state.error || decisionState.error}
            className="xl:col-span-3"
          />
          <StrategyComparisonPanel
            comparisonState={comparisonState}
            decision={decisionState.decision}
            loading={comparisonState.loading}
            emptyMessage={comparisonEmptyMessage}
            chain={state.chain}
            className="order-5 xl:order-none xl:col-span-12"
          />

          {state.loading ? (
          <section className={cn(panelClass, 'order-6 xl:order-none xl:col-span-12')}>
            <p className="font-mono text-sm text-cyan-100">正在加载期权链快照...</p>
          </section>
          ) : null}
          {state.error ? (
          <section className="order-6 rounded-xl border border-rose-400/20 bg-rose-500/5 p-4 text-sm text-rose-300 xl:order-none xl:col-span-12">
            {state.error}
          </section>
          ) : null}

          {!state.loading && !state.error ? (
            <>
              <ChainTable title="Call 链" contracts={calls} testId="options-lab-calls-table" className="order-6 xl:order-none xl:col-span-6" />
              <ChainTable title="Put 链" contracts={puts} testId="options-lab-puts-table" className="order-7 xl:order-none xl:col-span-6" />
            </>
          ) : null}

          {!state.loading && !state.error && !hasChainRows ? (
            <section className={cn(panelClass, 'order-8 xl:order-none xl:col-span-12')}>
              <p className="text-sm text-white/50">暂无数据，保留假设面板与风险提示。</p>
            </section>
          ) : null}

          <MethodologyDisclosure state={state} targetPrice={targetPrice} targetDate={targetDate} riskBudget={riskBudget} />
        </div>
      </div>
    </main>
  );
};

const OptionsLabPage: React.FC = () => (
  <OptionsLabErrorBoundary>
    <OptionsLabPageContent />
  </OptionsLabErrorBoundary>
);

export default OptionsLabPage;
