import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, BarChart3, ChevronDown, CircleDollarSign, Layers3, LineChart, Search, ShieldCheck } from 'lucide-react';
import {
  optionsLabApi,
  type OptionContract,
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

const DIRECTION_OPTIONS: Array<{ value: OptionsDirection; label: string }> = [
  { value: 'bullish', label: '看涨' },
  { value: 'bearish', label: '看跌' },
  { value: 'neutral', label: '中性' },
  { value: 'volatility', label: '赌波动' },
];

const RISK_PROFILE_OPTIONS: Array<{ value: OptionsRiskProfile; label: string }> = [
  { value: 'conservative', label: '保守' },
  { value: 'balanced', label: '均衡' },
  { value: 'aggressive', label: '进取' },
];

const RISK_WARNINGS = [
  '期权可能归零，最大亏损可能达到全部权利金。',
  '评分表示情景假设下的风险收益结构，不代表确定收益。',
  'IV 偏高时，即使方向判断正确，合约仍可能亏损。',
  '价差过宽或 OI 较低的合约可能难以成交或滑点较大。',
  '本模块不提供交易执行或收益承诺。',
];

const EMPTY_CONTRACTS: OptionContract[] = [];
const EMPTY_EXPIRATIONS: OptionsExpiration[] = [];
const COMPARISON_LOADING_TIMEOUT_MS = 12000;
const COMPARISON_EMPTY_MESSAGE = '先选择可用到期日并加载合约后，再进入策略对比。';

const fieldClass = 'h-10 w-full rounded-xl border border-white/10 bg-white/[0.02] px-3 font-mono text-sm text-white outline-none transition-all placeholder:text-white/20 focus:border-emerald-400/50 focus:bg-white/[0.05]';
const labelClass = 'text-[10px] font-bold uppercase tracking-[0.18em] text-white/40';
const panelClass = 'min-w-0 rounded-2xl border border-white/5 bg-white/[0.02] p-4 backdrop-blur-md md:p-5';

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

function limitationLabel(value: string): string {
  if (value === 'provider_validation_required') return 'Provider 待验证';
  if (value === 'mocked_frontend_shell') return '前端 Fixture';
  if (value === 'mocked_chain') return '模拟链';
  if (value === 'mock') return '本地模拟';
  if (value === 'fixture') return '本地 Fixture';
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
  return value.replace(/_/g, ' ');
}

function strategyLabel(value: OptionsStrategyType): string {
  const labels: Record<OptionsStrategyType, string> = {
    long_call: 'Long Call',
    long_put: 'Long Put',
    bull_call_spread: 'Bull Call Spread',
    bear_put_spread: 'Bear Put Spread',
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

function metricTone(value?: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'text-white/75';
  if (value > 0) return 'text-emerald-300';
  if (value < 0) return 'text-rose-300';
  return 'text-white/75';
}

const Pill: React.FC<{ children: React.ReactNode; tone?: 'neutral' | 'info' | 'warn' | 'good' }> = ({ children, tone = 'neutral' }) => {
  const toneClass = {
    neutral: 'border-white/10 bg-white/[0.04] text-white/60',
    info: 'border-cyan-300/20 bg-cyan-400/8 text-cyan-100',
    warn: 'border-amber-300/25 bg-amber-400/10 text-amber-100',
    good: 'border-emerald-300/25 bg-emerald-400/10 text-emerald-100',
  }[tone];
  return <span className={cn('inline-flex rounded-full border px-2.5 py-1 text-[11px] font-medium', toneClass)}>{children}</span>;
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
  <div className="grid grid-cols-2 gap-2 rounded-2xl border border-white/5 bg-black/20 p-1 sm:grid-cols-4" aria-label={ariaLabel}>
    {options.map((option) => (
      <button
        key={option.value}
        className={cn(
          'h-9 rounded-xl px-3 text-sm font-semibold transition-all',
          option.value === value
            ? 'border border-cyan-300/25 bg-white/10 text-white shadow-[0_0_18px_rgba(34,211,238,0.14)]'
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
  onSymbolChange: (value: string) => void;
  onSubmit: () => void;
  onDirectionChange: (value: OptionsDirection) => void;
  onRiskProfileChange: (value: OptionsRiskProfile) => void;
  onTargetPriceChange: (value: string) => void;
  onTargetDateChange: (value: string) => void;
  onRiskBudgetChange: (value: string) => void;
}> = ({
  symbol,
  direction,
  riskProfile,
  targetPrice,
  targetDate,
  riskBudget,
  onSymbolChange,
  onSubmit,
  onDirectionChange,
  onRiskProfileChange,
  onTargetPriceChange,
  onTargetDateChange,
  onRiskBudgetChange,
}) => (
  <section className={cn(panelClass, 'xl:col-span-4')}>
    <SectionHeader eyebrow="Assumptions" title="情景假设" icon={Search} />
    <div className="mt-5 grid gap-4">
      <label className="grid gap-2">
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
            className="h-10 rounded-xl border border-white/10 bg-white/5 px-4 text-sm font-semibold text-white/70 transition-all hover:border-white/20 hover:bg-white/10 hover:text-white"
          >
            载入
          </button>
        </div>
      </label>
      <div className="grid gap-2">
        <span className={labelClass}>方向</span>
        <SegmentedButtons options={DIRECTION_OPTIONS} value={direction} onChange={onDirectionChange} ariaLabel="方向假设" />
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <label className="grid gap-2">
          <span className={labelClass}>目标价格</span>
          <input aria-label="目标价格" value={targetPrice} onChange={(event) => onTargetPriceChange(event.target.value)} className={fieldClass} inputMode="decimal" />
        </label>
        <label className="grid gap-2">
          <span className={labelClass}>目标日期</span>
          <input aria-label="目标日期" value={targetDate} onChange={(event) => onTargetDateChange(event.target.value)} className={fieldClass} placeholder="2026-08-21" />
        </label>
        <label className="grid gap-2">
          <span className={labelClass}>风险预算</span>
          <input aria-label="风险预算" value={riskBudget} onChange={(event) => onRiskBudgetChange(event.target.value)} className={fieldClass} inputMode="decimal" />
        </label>
      </div>
      <div className="grid gap-2">
        <span className={labelClass}>风险偏好</span>
        <SegmentedButtons options={RISK_PROFILE_OPTIONS} value={riskProfile} onChange={onRiskProfileChange} ariaLabel="风险偏好" />
      </div>
    </div>
  </section>
);

const SnapshotPanel: React.FC<{ summary: OptionsUnderlyingSummaryResponse | null; chain: OptionsChainResponse | null }> = ({ summary, chain }) => {
  const underlying = summary?.underlying || chain?.underlying;
  return (
    <section className={cn(panelClass, 'xl:col-span-8')}>
      <SectionHeader eyebrow="Underlying" title="标的快照" icon={LineChart}>
        <div className="flex flex-wrap justify-end gap-2">
          <Pill tone="good">只读</Pill>
          <Pill tone="info">不接入交易</Pill>
          <Pill tone="warn">分析支持</Pill>
        </div>
      </SectionHeader>
      <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
        <div className="rounded-2xl border border-white/5 bg-black/20 p-4">
          <p className={labelClass}>Symbol</p>
          <p className="mt-2 font-mono text-2xl font-semibold text-white">{summary?.symbol || chain?.symbol || '--'}</p>
        </div>
        <div className="rounded-2xl border border-white/5 bg-black/20 p-4">
          <p className={labelClass}>Last</p>
          <p className="mt-2 font-mono text-2xl font-semibold text-white">{money(underlying?.price)}</p>
        </div>
        <div className="rounded-2xl border border-white/5 bg-black/20 p-4">
          <p className={labelClass}>Change</p>
          <p className="mt-2 font-mono text-2xl font-semibold text-emerald-300">{ratio(underlying?.changePct)}</p>
        </div>
        <div className="rounded-2xl border border-white/5 bg-black/20 p-4">
          <p className={labelClass}>Freshness</p>
          <p className="mt-2 font-mono text-base font-semibold text-cyan-100">{underlying?.freshness || '--'}</p>
          <p className="mt-1 truncate text-xs text-white/35">{underlying?.asOf || '--'}</p>
        </div>
      </div>
      <p className="mt-4 rounded-2xl border border-cyan-300/10 bg-cyan-400/8 px-4 py-3 text-sm leading-6 text-cyan-100/78">
        分析支持 / 不构成投资建议。所有排序与对比只表示当前情景假设下的风险收益结构。
      </p>
    </section>
  );
};

const ExpirationPanel: React.FC<{
  expirations: OptionsExpiration[];
  selectedExpiration: string;
  onSelect: (value: string) => void;
}> = ({ expirations, selectedExpiration, onSelect }) => (
  <section className={cn(panelClass, 'xl:col-span-12')}>
    <SectionHeader eyebrow="Expiration Filters" title="到期日过滤" icon={Layers3} />
    <div className="mt-4 flex gap-2 overflow-x-auto no-scrollbar">
      {expirations.length === 0 ? (
        <p className="rounded-2xl border border-white/5 bg-black/20 px-4 py-3 text-sm text-white/45">暂无可用到期日。</p>
      ) : expirations.map((expiration) => (
        <button
          key={expiration.date}
          type="button"
          className={cn(
            'min-w-[150px] rounded-2xl border px-4 py-3 text-left transition-all',
            expiration.date === selectedExpiration
              ? 'border-cyan-300/25 bg-cyan-400/10 text-white'
              : 'border-white/5 bg-black/20 text-white/55 hover:border-white/10 hover:bg-white/[0.03]',
          )}
          onClick={() => onSelect(expiration.date)}
        >
          <span className="block font-mono text-sm font-semibold">{expiration.date}</span>
          <span className="mt-1 block text-xs text-white/40">{expiration.dte} DTE · {expiration.type}</span>
        </button>
      ))}
    </div>
  </section>
);

const ChainTable: React.FC<{ title: string; contracts: OptionContract[]; testId: string }> = ({ title, contracts, testId }) => (
  <section className={cn(panelClass, 'min-h-[360px]')}>
    <SectionHeader eyebrow="Option Chain" title={title} icon={BarChart3} />
    {contracts.length === 0 ? (
      <p className="mt-5 rounded-2xl border border-white/5 bg-black/20 px-4 py-5 text-sm text-white/45">暂无合约数据，保留假设面板与风险提示。</p>
    ) : (
      <div className="mt-5 overflow-x-auto no-scrollbar" data-testid={testId}>
        <table className="w-full min-w-[720px] border-separate border-spacing-y-2 text-left">
          <thead className="text-[10px] uppercase tracking-[0.16em] text-white/35">
            <tr>
              <th className="px-3 py-2">合约</th>
              <th className="px-3 py-2">Strike</th>
              <th className="px-3 py-2">Mid</th>
              <th className="px-3 py-2">Bid / Ask</th>
              <th className="px-3 py-2">IV</th>
              <th className="px-3 py-2">Delta</th>
              <th className="px-3 py-2">Theta</th>
              <th className="px-3 py-2">OI / Vol</th>
              <th className="px-3 py-2">流动性</th>
            </tr>
          </thead>
          <tbody>
            {contracts.map((contract) => (
              <tr key={contract.contractSymbol} className="rounded-2xl bg-black/20 text-sm text-white/72">
                <td className="rounded-l-2xl px-3 py-3 font-mono text-xs text-white">{contract.contractSymbol}</td>
                <td className="px-3 py-3 font-mono">{money(contract.strike)}</td>
                <td className="px-3 py-3 font-mono">{money(contract.mid)}</td>
                <td className="px-3 py-3 font-mono">{money(contract.bid)} / {money(contract.ask)}</td>
                <td className="px-3 py-3 font-mono">{ratio(contract.impliedVolatility)}</td>
                <td className="px-3 py-3 font-mono">{number(contract.delta, 2)}</td>
                <td className="px-3 py-3 font-mono text-amber-200">{number(contract.theta, 2)}</td>
                <td className="px-3 py-3 font-mono">{number(contract.openInterest)} / {number(contract.volume)}</td>
                <td className="rounded-r-2xl px-3 py-3">
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

const StrategyMetric: React.FC<{ label: string; value: string; tone?: string }> = ({ label, value, tone = 'text-white' }) => (
  <div className="min-w-0 rounded-2xl border border-white/5 bg-black/20 p-3">
    <p className={labelClass}>{label}</p>
    <p className={cn('mt-2 truncate font-mono text-lg font-semibold', tone)}>{value}</p>
  </div>
);

const StrategyCard: React.FC<{ strategy: OptionsStrategyComparison }> = ({ strategy }) => {
  const caveats = [...strategy.liquidityWarnings, ...strategy.ivThetaNotes];
  return (
    <article className="min-w-0 rounded-2xl border border-white/5 bg-black/20 p-4 transition-all hover:border-white/10 hover:bg-white/[0.03]">
      <div className="flex min-w-0 items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-mono text-xs font-semibold uppercase tracking-[0.16em] text-cyan-100/72">{strategyLabel(strategy.strategyType)}</p>
          <h3 className="mt-1 text-base font-semibold text-white">{strategyChineseLabel(strategy.strategyType)}</h3>
        </div>
        <Pill tone={strategy.maxGain == null ? 'info' : 'good'}>{strategy.maxGain == null ? '收益开放' : '定义风险'}</Pill>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3">
        <StrategyMetric label="净支出" value={money(strategy.netDebit)} />
        <StrategyMetric label="最大亏损" value={money(strategy.maxLoss)} tone="text-rose-300" />
        <StrategyMetric label="最大收益" value={strategy.maxGain == null ? '不封顶' : money(strategy.maxGain)} tone="text-emerald-300" />
        <StrategyMetric label="盈亏平衡" value={money(strategy.breakeven)} />
        <StrategyMetric label="目标价格收益" value={money(strategy.payoffAtTarget)} tone={metricTone(strategy.payoffAtTarget)} />
        <StrategyMetric label="风险收益比" value={strategy.riskRewardRatio == null ? '--' : `${formatNumber(strategy.riskRewardRatio, 2)}x`} />
      </div>
      <div className="mt-4 grid gap-2">
        <div className="rounded-2xl border border-white/5 bg-white/[0.02] p-3">
          <p className={labelClass}>流动性提示</p>
          <p className="mt-2 text-sm leading-6 text-white/62">
            {strategy.liquidityWarnings.length ? strategy.liquidityWarnings.map(limitationLabel).join(' · ') : '未触发额外流动性提示'}
          </p>
        </div>
        <div className="rounded-2xl border border-white/5 bg-white/[0.02] p-3">
          <p className={labelClass}>波动率 / 时间价值提示</p>
          <p className="mt-2 text-sm leading-6 text-white/62">
            {strategy.ivThetaNotes.length ? strategy.ivThetaNotes.map(limitationLabel).join(' · ') : '暂无额外 IV / Theta 提示'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {strategy.suitabilityNotes.slice(0, 3).map((note) => (
            <Pill key={note}>{limitationLabel(note)}</Pill>
          ))}
          {caveats.length > 0 ? <Pill tone="warn">需复核假设</Pill> : null}
        </div>
      </div>
    </article>
  );
};

const StrategyComparisonPanel: React.FC<{
  comparisonState: ComparisonState;
  loading: boolean;
  emptyMessage: string | null;
  chain: OptionsChainResponse | null;
}> = ({ comparisonState, loading, emptyMessage, chain }) => {
  const strategies = comparisonState.comparison?.strategies || [];
  const freshness = chain?.underlying?.freshness || (comparisonState.comparison?.metadata.fixtureBacked ? 'fixture' : null);
  return (
    <section className={cn(panelClass, 'xl:col-span-12')} data-testid="options-lab-strategy-comparison">
      <SectionHeader eyebrow="Phase 4" title="策略对比" icon={Layers3}>
        <div className="flex flex-wrap justify-end gap-2">
          <Pill tone="info">{freshness ? `数据状态：${limitationLabel(String(freshness))}` : '数据状态：等待快照'}</Pill>
          <Pill tone="warn">仅供情景分析，不构成交易建议</Pill>
        </div>
      </SectionHeader>
      <p className="mt-4 rounded-2xl border border-cyan-300/10 bg-cyan-400/8 px-4 py-3 text-sm leading-6 text-cyan-100/78">
        仅供情景分析，不构成交易建议。对比使用当前标的、到期日与目标价格假设，展示定义风险结构下的权利金、盈亏边界与风险收益关系。
      </p>
      {emptyMessage ? (
        <div className="mt-5 rounded-2xl border border-dashed border-white/10 bg-black/20 px-4 py-4 text-sm leading-6 text-white/55">
          <p className="text-sm font-semibold text-white/78">等待策略对比前提</p>
          <p className="mt-2">{emptyMessage}</p>
        </div>
      ) : null}
      {!emptyMessage && loading ? (
        <p className="mt-5 rounded-2xl border border-white/5 bg-black/20 px-4 py-5 font-mono text-sm text-cyan-100">正在计算策略对比...</p>
      ) : null}
      {!emptyMessage && !loading && comparisonState.error ? (
        <p className="mt-5 rounded-2xl border border-rose-300/20 bg-rose-500/10 px-4 py-4 text-sm text-rose-100">{comparisonState.error}</p>
      ) : null}
      {!emptyMessage && !loading && !comparisonState.error && strategies.length === 0 ? (
        <p className="mt-5 rounded-2xl border border-white/5 bg-black/20 px-4 py-5 text-sm text-white/45">当前假设下暂无可比较策略。</p>
      ) : null}
      {!emptyMessage && !loading && !comparisonState.error && strategies.length > 0 ? (
        <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-2 2xl:grid-cols-4">
          {strategies.map((strategy) => (
            <StrategyCard key={strategy.strategyType} strategy={strategy} />
          ))}
        </div>
      ) : null}
      <details data-testid="options-lab-strategy-developer-details" className="mt-5 rounded-2xl border border-white/5 bg-black/20 p-4 text-sm text-white/55">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-white/68">
          <span className="inline-flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-cyan-200" aria-hidden="true" />
            开发者字段 / 新鲜度
          </span>
          <ChevronDown className="h-4 w-4 text-white/35" aria-hidden="true" />
        </summary>
        <div className="mt-4 grid gap-2 text-xs leading-5 text-white/45">
          <p>策略引擎：{comparisonState.comparison?.metadata.strategyEngine || '--'}</p>
          <p>本地数据：{comparisonState.comparison?.metadata.fixtureBacked === false ? '未确认' : '是'}</p>
          <p>忽略强制刷新：{comparisonState.comparison?.metadata.forceRefreshIgnored ? '是' : '否'}</p>
          <p>假设：{comparisonState.comparison ? JSON.stringify(comparisonState.comparison.assumptions) : '--'}</p>
          <p>限制：{(comparisonState.comparison?.limitations || []).map(limitationLabel).join(' · ') || '--'}</p>
        </div>
      </details>
    </section>
  );
};

const PlaceholderPanel: React.FC<{
  title: string;
  eyebrow: string;
  icon: React.ComponentType<{ className?: string }>;
  body: string;
}> = ({ title, eyebrow, icon, body }) => (
  <section className={panelClass}>
    <SectionHeader eyebrow={eyebrow} title={title} icon={icon} />
    <div className="mt-5 rounded-2xl border border-dashed border-white/10 bg-black/20 px-4 py-8 text-sm leading-6 text-white/50">
      {body}
    </div>
  </section>
);

const RiskWarnings: React.FC = () => (
  <section className={cn(panelClass, 'border-amber-300/10 bg-amber-400/8')}>
    <SectionHeader eyebrow="Risk Controls" title="风险提示" icon={AlertTriangle} />
    <ul className="mt-5 grid gap-3">
      {RISK_WARNINGS.map((warning) => (
        <li key={warning} className="flex gap-3 rounded-2xl border border-amber-300/10 bg-black/20 px-4 py-3 text-sm leading-6 text-amber-50/84">
          <AlertTriangle className="mt-1 h-4 w-4 shrink-0 text-amber-200" aria-hidden="true" />
          <span>{warning}</span>
        </li>
      ))}
    </ul>
  </section>
);

const DeveloperDetails: React.FC<{ state: LoadState }> = ({ state }) => (
  <details data-testid="options-lab-developer-details" className="rounded-2xl border border-white/5 bg-white/[0.02] p-4 text-sm text-white/55">
    <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-white/68">
      <span className="inline-flex items-center gap-2">
        <ShieldCheck className="h-4 w-4 text-cyan-200" aria-hidden="true" />
        Freshness / Developer Details
      </span>
      <ChevronDown className="h-4 w-4 text-white/35" aria-hidden="true" />
    </summary>
    <div className="mt-4 grid gap-2 text-xs leading-5 text-white/45">
      <p>Source: {state.chain?.source || state.summary?.underlying.source || '--'}</p>
      <p>Chain as of: {state.chain?.chainAsOf || '--'}</p>
      <p>Read only: {state.chain?.metadata.readOnly === false ? 'unconfirmed' : 'true'}</p>
      <p>No external calls in tests: {state.chain?.metadata.noExternalCallsInTests === false ? 'unconfirmed' : 'true'}</p>
      <p>Limitations: {[...(state.chain?.limitations || []), ...(state.chain?.metadata.limitations || [])].map(limitationLabel).join(' · ') || '--'}</p>
    </div>
  </details>
);

const OptionsLabPage: React.FC = () => {
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
        const nextExpiration = expirations.expirations.some((item) => item.date === selectedExpiration)
          ? selectedExpiration
          : expirations.expirations[0]?.date || selectedExpiration;
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
      const hasExpirations = (state.expirations?.expirations.length || 0) > 0;
      const hasContracts = Boolean((state.chain?.calls.length || 0) || (state.chain?.puts.length || 0));
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

  const expirations = state.expirations?.expirations || EMPTY_EXPIRATIONS;
  const calls = state.chain?.calls || EMPTY_CONTRACTS;
  const puts = state.chain?.puts || EMPTY_CONTRACTS;
  const hasChainRows = calls.length > 0 || puts.length > 0;
  const topCall = useMemo(() => calls[0], [calls]);
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

  return (
    <main className="min-h-screen w-full bg-[#050505] px-4 py-5 text-white md:px-8 xl:px-10">
      <div className="mx-auto flex w-full max-w-[1720px] flex-col gap-5">
        <header className="flex flex-col gap-4 rounded-[24px] border border-white/5 bg-white/[0.02] p-5 backdrop-blur-md md:flex-row md:items-end md:justify-between md:p-6">
          <div className="min-w-0">
            <p className="text-[11px] font-bold uppercase tracking-[0.22em] text-cyan-200/70">Options Lab Phase 4</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-normal text-white md:text-5xl">期权实验室</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-white/58">
              前端只读实验台：用模拟期权链展示情景假设、合约表、策略对比与风险披露，不接入交易或实时供应商调用。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Pill tone="good">只读分析</Pill>
            <Pill tone="info">本地情景链</Pill>
            <Pill tone="warn">分析支持 / 不构成投资建议</Pill>
          </div>
        </header>

        <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
          <AssumptionPanel
            symbol={symbolInput}
            direction={direction}
            riskProfile={riskProfile}
            targetPrice={targetPrice}
            targetDate={targetDate}
            riskBudget={riskBudget}
            onSymbolChange={setSymbolInput}
            onSubmit={handleSubmit}
            onDirectionChange={setDirection}
            onRiskProfileChange={setRiskProfile}
            onTargetPriceChange={setTargetPrice}
            onTargetDateChange={setTargetDate}
            onRiskBudgetChange={setRiskBudget}
          />
          <SnapshotPanel summary={state.summary} chain={state.chain} />
          <ExpirationPanel expirations={expirations} selectedExpiration={selectedExpiration} onSelect={handleExpirationSelect} />
        </div>

        {state.loading ? (
          <section className={panelClass}>
            <p className="font-mono text-sm text-cyan-100">正在加载期权链快照...</p>
          </section>
        ) : null}
        {state.error ? (
          <section className="rounded-2xl border border-rose-300/20 bg-rose-500/10 p-4 text-sm text-rose-100">
            {state.error}
          </section>
        ) : null}

        {!state.loading && !state.error ? (
          <div className="grid grid-cols-1 gap-5 2xl:grid-cols-2">
            <ChainTable title="Calls 链表" contracts={calls} testId="options-lab-calls-table" />
            <ChainTable title="Puts 链表" contracts={puts} testId="options-lab-puts-table" />
          </div>
        ) : null}

        {!state.loading && !state.error && !hasChainRows ? (
          <section className={panelClass}>
            <p className="text-sm text-white/50">暂无合约数据，保留假设面板与风险提示。</p>
          </section>
        ) : null}

        <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
          <PlaceholderPanel
            eyebrow="Ranking"
            title="候选合约排序"
            icon={CircleDollarSign}
            body={topCall ? `当前仅展示占位排序：${topCall.contractSymbol} 的流动性与价差结构较清晰；后续分析仍需使用显式假设与风险预算。` : '等待合约链后展示情景排序占位。'}
          />
          <PlaceholderPanel
            eyebrow="Scenario"
            title="情景收益结构"
            icon={BarChart3}
            body={`目标价 ${targetPrice || '--'}，目标日 ${targetDate || '--'}，预算 ${riskBudget || '--'}。后续 payoff 图应仅表达假设下结构，不表达确定收益。`}
          />
        </div>

        <StrategyComparisonPanel comparisonState={comparisonState} loading={comparisonState.loading} emptyMessage={comparisonEmptyMessage} chain={state.chain} />

        <RiskWarnings />
        <DeveloperDetails state={state} />
      </div>
    </main>
  );
};

export default OptionsLabPage;
