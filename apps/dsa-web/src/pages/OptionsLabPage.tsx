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
  '本模块不提供下单或保证性收益建议。',
];

const EMPTY_CONTRACTS: OptionContract[] = [];
const EMPTY_EXPIRATIONS: OptionsExpiration[] = [];

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
  if (value === 'wide_spread_watch') return '价差观察';
  if (value === 'low_oi_watch') return 'OI 偏低';
  return value.replace(/_/g, ' ');
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

  useEffect(() => {
    let ignored = false;

    async function load() {
      try {
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
        setState({ loading: false, error: null, summary, expirations, chain });
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
  const topPut = useMemo(() => puts[0], [puts]);

  return (
    <main className="min-h-screen w-full bg-[#050505] px-4 py-5 text-white md:px-8 xl:px-10">
      <div className="mx-auto flex w-full max-w-[1720px] flex-col gap-5">
        <header className="flex flex-col gap-4 rounded-[24px] border border-white/5 bg-white/[0.02] p-5 backdrop-blur-md md:flex-row md:items-end md:justify-between md:p-6">
          <div className="min-w-0">
            <p className="text-[11px] font-bold uppercase tracking-[0.22em] text-cyan-200/70">Options Lab Phase 2</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-normal text-white md:text-5xl">期权实验室</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-white/58">
              前端只读实验台：用模拟期权链展示情景假设、合约表、排序占位、策略比较占位与风险披露，不接入交易或实时供应商调用。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Pill tone="good">Read-only</Pill>
            <Pill tone="info">Mocked Chain</Pill>
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

        <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
          <PlaceholderPanel
            eyebrow="Ranking"
            title="候选合约排序"
            icon={CircleDollarSign}
            body={topCall ? `当前仅展示占位排序：${topCall.contractSymbol} 的流动性与价差结构较清晰；后续分析仍需使用显式假设与风险预算。` : '等待合约链后展示情景排序占位。'}
          />
          <PlaceholderPanel
            eyebrow="Strategy"
            title="策略比较"
            icon={Layers3}
            body={topCall && topPut ? `比较长 Call、长 Put 与定义风险价差结构。当前占位参考 ${topCall.contractSymbol} / ${topPut.contractSymbol}，不提供执行建议。` : '等待合约链后展示策略比较占位。'}
          />
          <PlaceholderPanel
            eyebrow="Scenario"
            title="情景收益结构"
            icon={BarChart3}
            body={`目标价 ${targetPrice || '--'}，目标日 ${targetDate || '--'}，预算 ${riskBudget || '--'}。后续 payoff 图应仅表达假设下结构，不表达确定收益。`}
          />
        </div>

        <RiskWarnings />
        <DeveloperDetails state={state} />
      </div>
    </main>
  );
};

export default OptionsLabPage;
