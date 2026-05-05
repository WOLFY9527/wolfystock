import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import {
  BookOpen,
  CheckCircle2,
  ChevronRight,
  PanelRightOpen,
  Play,
  RotateCw,
  ShieldCheck,
  Sparkles,
  XCircle,
} from 'lucide-react';
import { ApiErrorAlert, Drawer } from '../../components/common';
import type { RuleBacktestHistoryItem, RuleBacktestParseResponse } from '../../types/backtest';
import type { FlowProps, RuleWizardStep } from './DeterministicBacktestFlow';
import { RULE_BACKTEST_PRESET_STORAGE_KEY } from './ruleBacktestP6';
import {
  RULE_BENCHMARK_OPTIONS,
  getBenchmarkModeLabel,
  getStrategyPreviewSpec,
  getStrategySpecValue,
  type RuleBenchmarkMode,
} from './shared';
import { getStrategyCatalogGroups } from './strategyCatalog';

type BacktestLanguage = 'zh' | 'en';
type WorkspaceStep = 'assets' | 'strategy' | 'orders' | 'costs' | 'advanced';
type OrdersTab = 'routing' | 'guards';
type AdvancedTab = 'optimization' | 'robustness';

type StepStatusTone = 'done' | 'pending' | 'default' | 'modified' | 'off' | 'error';

type StepDefinition = {
  id: WorkspaceStep;
  number: string;
  title: string;
  description: string;
  testId: string;
  wizardStep: RuleWizardStep;
};

type ProBacktestWorkspaceProps = Omit<FlowProps, 'panelMode'> & {
  language: BacktestLanguage;
};

const ghostCardClass = 'bg-white/[0.02] border border-white/5 rounded-xl backdrop-blur-md transition-all hover:border-white/10';
const fieldClass = 'w-full min-w-0 min-h-[42px] rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2 text-sm leading-6 text-white outline-none transition-all focus:border-blue-500/50 focus:bg-white/[0.05]';
const checkboxClass = 'h-4 w-4 shrink-0 rounded border border-white/15 bg-white/[0.03] text-blue-300 accent-blue-400 disabled:opacity-45';
const labelClass = 'text-[10px] font-bold uppercase tracking-widest text-white/40';
const primaryButtonClass = 'inline-flex min-h-[42px] items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-blue-600 to-purple-600 px-4 py-2 text-sm font-semibold text-white shadow-[0_0_15px_rgba(139,92,246,0.3)] transition-all hover:from-blue-500 hover:to-purple-500 disabled:cursor-not-allowed disabled:opacity-45';
const secondaryButtonClass = 'inline-flex min-h-[38px] items-center justify-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm font-medium text-white/70 transition-all hover:bg-white/10 hover:text-white disabled:cursor-not-allowed disabled:opacity-45';
const chipButtonClass = 'inline-flex min-h-[34px] shrink-0 items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-white/70 transition-all hover:bg-white/10 hover:text-white';
const activeChipButtonClass = 'inline-flex min-h-[34px] shrink-0 items-center gap-2 rounded-lg border border-blue-400/35 bg-blue-500/10 px-3 py-1.5 text-xs font-semibold text-blue-100 shadow-[0_0_18px_rgba(59,130,246,0.12)]';

function getParsedExecutable(parsed: RuleBacktestParseResponse | null): boolean {
  if (!parsed) return false;
  if (typeof parsed.executable === 'boolean') return parsed.executable;
  return Boolean(parsed.parsedStrategy.executable);
}

function hasParsedStrategySpec(parsed: RuleBacktestParseResponse | null): boolean {
  return Boolean(parsed?.parsedStrategy.strategySpec);
}

function getSetupSourceLabel(parsed: RuleBacktestParseResponse | null, language: BacktestLanguage): string {
  if (!parsed) return language === 'en' ? 'No parse yet' : '尚未解析';
  if (hasParsedStrategySpec(parsed)) return language === 'en' ? 'Source · explicit strategy_spec' : '规格来源 · 显式 strategy_spec';
  if (parsed.parsedStrategy.setup) return language === 'en' ? 'Source · compat setup' : '规格来源 · 兼容 setup';
  return language === 'en' ? 'Source · parse summary' : '规格来源 · 解析摘要';
}

function getFirstLine(value: string): string {
  return value.trim().split(/\n+/)[0]?.trim() || '';
}

function formatPercent(value: unknown): string {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? `${numeric.toFixed(2)}%` : '--';
}

function formatBoolean(value: boolean, language: BacktestLanguage): string {
  if (language === 'en') return value ? 'On' : 'Off';
  return value ? '开启' : '关闭';
}

function readRiskControls(parsed: RuleBacktestParseResponse | null) {
  const spec = getStrategyPreviewSpec(parsed);
  const stopLoss = getStrategySpecValue(spec, ['risk_controls', 'stop_loss_pct'])
    ?? getStrategySpecValue(spec, ['riskControls', 'stopLossPct']);
  const takeProfit = getStrategySpecValue(spec, ['risk_controls', 'take_profit_pct'])
    ?? getStrategySpecValue(spec, ['riskControls', 'takeProfitPct']);
  const trailingStop = getStrategySpecValue(spec, ['risk_controls', 'trailing_stop_pct'])
    ?? getStrategySpecValue(spec, ['riskControls', 'trailingStopPct']);

  return [
    { key: 'stop-loss', label: '止损', value: stopLoss },
    { key: 'take-profit', label: '止盈', value: takeProfit },
    { key: 'trailing-stop', label: '移动止损', value: trailingStop },
  ].filter((item) => item.value != null && item.value !== '');
}

function getParseWarnings(parsed: RuleBacktestParseResponse | null): string[] {
  const topLevel = Array.isArray(parsed?.parseWarnings) ? parsed.parseWarnings : [];
  const nested = Array.isArray(parsed?.parsedStrategy.parseWarnings) ? parsed?.parsedStrategy.parseWarnings : [];
  return [...topLevel, ...nested]
    .map((item) => String((item as Record<string, unknown>).message || '').trim())
    .filter(Boolean);
}

function getAssumptionItems(parsed: RuleBacktestParseResponse | null, language: BacktestLanguage): string[] {
  const topLevel = Array.isArray(parsed?.assumptions) ? parsed.assumptions : [];
  const nested = Array.isArray(parsed?.parsedStrategy.assumptions) ? parsed?.parsedStrategy.assumptions : [];
  const assumptions = topLevel.length > 0 ? topLevel : nested;
  const formatted = assumptions.map((item) => {
    const record = item as Record<string, unknown>;
    const label = String(record.label || record.key || (language === 'en' ? 'Assumption' : '假设'));
    const value = record.value == null || record.value === '' ? '' : `${language === 'en' ? ': ' : '：'}${String(record.value)}`;
    const reason = String(record.reason || '').trim();
    return `${label}${value}${reason ? `${language === 'en' ? '. ' : '。'}${reason}` : ''}`;
  });
  return Array.from(new Set([...formatted, ...getParseWarnings(parsed)]));
}

function statusLabel(tone: StepStatusTone, language: BacktestLanguage): string {
  const zh: Record<StepStatusTone, string> = {
    done: '已完成',
    pending: '待确认',
    default: '默认',
    modified: '已修改',
    off: '关闭',
    error: '错误',
  };
  const en: Record<StepStatusTone, string> = {
    done: 'Done',
    pending: 'Review',
    default: 'Default',
    modified: 'Modified',
    off: 'Off',
    error: 'Error',
  };
  return language === 'en' ? en[tone] : zh[tone];
}

function statusClass(tone: StepStatusTone): string {
  if (tone === 'done') return 'border-emerald-400/25 bg-emerald-400/10 text-emerald-100';
  if (tone === 'error') return 'border-rose-400/25 bg-rose-400/10 text-rose-100';
  if (tone === 'modified') return 'border-blue-400/25 bg-blue-400/10 text-blue-100';
  if (tone === 'pending') return 'border-amber-400/25 bg-amber-400/10 text-amber-100';
  if (tone === 'off') return 'border-white/10 bg-white/[0.02] text-white/38';
  return 'border-white/10 bg-white/[0.03] text-white/50';
}

const ProBacktestWorkspace: React.FC<ProBacktestWorkspaceProps> = ({
  language,
  code,
  onCodeChange,
  onCodeEnter,
  strategyText,
  onStrategyTextChange,
  startDate,
  onStartDateChange,
  endDate,
  onEndDateChange,
  initialCapital,
  onInitialCapitalChange,
  lookbackBars,
  onLookbackBarsChange,
  feeBps,
  onFeeBpsChange,
  slippageBps,
  onSlippageBpsChange,
  benchmarkMode,
  onBenchmarkModeChange,
  benchmarkCode,
  onBenchmarkCodeChange,
  parsedStrategy,
  confirmed,
  onToggleConfirmed,
  isParsing,
  parseError,
  onParse,
  isSubmitting,
  runError,
  onRun,
  onReset,
  historyItems,
  historyTotal,
  historyPage,
  selectedRunId,
  isLoadingHistory,
  historyError,
  onRefreshHistory,
  onOpenHistoryRun,
  currentStep,
  onStepChange,
  parseStale,
  onApplyRewriteSuggestion,
  appliedRewriteText,
}) => {
  const [activeStep, setActiveStep] = useState<WorkspaceStep>('assets');
  const [ordersTab, setOrdersTab] = useState<OrdersTab>('routing');
  const [advancedTab, setAdvancedTab] = useState<AdvancedTab>('optimization');
  const [portfolioMode, setPortfolioMode] = useState<'single' | 'multi'>('single');
  const [rebalanceCadence, setRebalanceCadence] = useState('monthly');
  const [eventDriven, setEventDriven] = useState(true);
  const [enableStopLoss, setEnableStopLoss] = useState(true);
  const [enableTakeProfit, setEnableTakeProfit] = useState(true);
  const [enableTrailingStop, setEnableTrailingStop] = useState(false);
  const [maxPositionPct, setMaxPositionPct] = useState('25');
  const [maxExposurePct, setMaxExposurePct] = useState('80');
  const [maxDrawdownPct, setMaxDrawdownPct] = useState('15');
  const [perTradeRiskPct, setPerTradeRiskPct] = useState('2');
  const [maxHoldings, setMaxHoldings] = useState('5');
  const [enableGridSearch, setEnableGridSearch] = useState(false);
  const [enableBayesianSearch, setEnableBayesianSearch] = useState(false);
  const [enableWalkForward, setEnableWalkForward] = useState(false);
  const [enableRobustness, setEnableRobustness] = useState(false);
  const [resultsOpen, setResultsOpen] = useState(false);
  const [catalogToast, setCatalogToast] = useState<string | null>(null);
  const [isCatalogDrawerOpen, setIsCatalogDrawerOpen] = useState(false);
  const [catalogGroupId, setCatalogGroupId] = useState<string>('basic');

  const parsedExecutable = getParsedExecutable(parsedStrategy);
  const strategySpec = getStrategyPreviewSpec(parsedStrategy);
  const riskRows = readRiskControls(parsedStrategy);
  const assumptionItems = getAssumptionItems(parsedStrategy, language);
  const strategyCatalogGroups = getStrategyCatalogGroups();
  const activeCatalogGroup = useMemo(
    () => strategyCatalogGroups.find((group) => group.id === catalogGroupId) || strategyCatalogGroups[0],
    [catalogGroupId, strategyCatalogGroups],
  );
  const latestHistory = historyItems[0] as RuleBacktestHistoryItem | undefined;

  useEffect(() => {
    if (!catalogToast) return undefined;
    const timer = window.setTimeout(() => setCatalogToast(null), 3200);
    return () => window.clearTimeout(timer);
  }, [catalogToast]);

  useEffect(() => {
    if (currentStep === 'symbol') setActiveStep('assets');
    if (currentStep === 'strategy') setActiveStep('strategy');
    if (currentStep === 'confirm' && activeStep !== 'orders' && activeStep !== 'costs') setActiveStep('orders');
    if (currentStep === 'run' && activeStep !== 'advanced') setActiveStep('advanced');
  // Keep the current visible workspace stable when confirm/run is reached from a local step.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentStep]);

  const stepDefinitions: StepDefinition[] = [
    {
      id: 'assets',
      number: '01',
      title: language === 'en' ? 'Assets' : '标的与组合',
      description: language === 'en' ? 'Symbol, benchmark, window, capital.' : '标的、基准、区间与资金。',
      testId: 'pro-workflow-step-assets',
      wizardStep: 'symbol',
    },
    {
      id: 'strategy',
      number: '02',
      title: language === 'en' ? 'Strategy' : '策略与引擎',
      description: language === 'en' ? 'Editor, parse, rule preview.' : '策略编辑、解析与规则预览。',
      testId: 'pro-workflow-step-strategy',
      wizardStep: 'strategy',
    },
    {
      id: 'orders',
      number: '03',
      title: language === 'en' ? 'Orders' : '订单与风控',
      description: language === 'en' ? 'Routing and risk guards.' : '执行路由与风险护栏。',
      testId: 'pro-workflow-step-orders',
      wizardStep: 'confirm',
    },
    {
      id: 'costs',
      number: '04',
      title: language === 'en' ? 'Costs' : '成本与滑点',
      description: language === 'en' ? 'Lookback, fees, slippage.' : '回看、手续费与滑点。',
      testId: 'pro-workflow-step-costs',
      wizardStep: 'confirm',
    },
    {
      id: 'advanced',
      number: '05',
      title: language === 'en' ? 'Advanced' : '高级分析',
      description: language === 'en' ? 'Optimization and robustness.' : '优化与稳健性分析。',
      testId: 'pro-workflow-step-advanced',
      wizardStep: 'run',
    },
  ];

  const capitalNumber = Number.parseFloat(initialCapital);
  const feeNumber = Number.parseFloat(feeBps);
  const slippageNumber = Number.parseFloat(slippageBps);
  const dateValid = Boolean(startDate && endDate && startDate <= endDate);
  const capitalValid = Number.isFinite(capitalNumber) && capitalNumber > 0;
  const costValid = Number.isFinite(feeNumber) && feeNumber >= 0 && Number.isFinite(slippageNumber) && slippageNumber >= 0;
  const benchmarkValid = benchmarkMode !== 'custom_code' || Boolean(benchmarkCode.trim());
  const symbolValid = Boolean(code.trim());
  const strategyReady = Boolean(parsedStrategy && parsedExecutable && !parseStale && confirmed);
  const canRun = symbolValid && dateValid && capitalValid && costValid && benchmarkValid && strategyReady;

  const readiness = [
    { key: 'symbol', label: language === 'en' ? 'symbol valid' : 'symbol valid', ready: symbolValid },
    { key: 'date', label: language === 'en' ? 'date valid' : 'date valid', ready: dateValid },
    { key: 'strategy', label: language === 'en' ? 'strategy parsed' : 'strategy parsed', ready: Boolean(parsedStrategy && !parseStale && parsedExecutable) },
    { key: 'capital', label: language === 'en' ? 'capital set' : 'capital set', ready: capitalValid },
    { key: 'cost', label: language === 'en' ? 'cost/slippage set' : 'cost/slippage set', ready: costValid },
    { key: 'risk', label: language === 'en' ? 'risk checked or default' : 'risk checked or default', ready: true },
  ];

  const firstNotReady = readiness.find((item) => !item.ready);
  const readinessNote = !benchmarkValid
    ? (language === 'en' ? 'Custom benchmark code required' : '需要填写自定义基准代码')
    : parseStale
      ? (language === 'en' ? 'Inputs changed. Parse again.' : '输入已变更，请重新解析')
      : !confirmed && parsedStrategy
        ? (language === 'en' ? 'Confirm parsed strategy before launch' : '运行前请确认解析结果')
        : firstNotReady
          ? (language === 'en' ? `Waiting for ${firstNotReady.label}` : `等待 ${firstNotReady.label}`)
          : (language === 'en' ? 'Ready to execute' : '可以执行');

  const stepStatuses: Record<WorkspaceStep, StepStatusTone> = {
    assets: !symbolValid || !dateValid || !capitalValid || !benchmarkValid ? 'error' : 'done',
    strategy: parseStale ? 'error' : confirmed ? 'done' : parsedStrategy ? 'pending' : 'pending',
    orders: enableStopLoss || enableTakeProfit || enableTrailingStop || eventDriven ? 'modified' : 'default',
    costs: Number(feeBps) > 0 || Number(slippageBps) > 0 || benchmarkMode === 'custom_code' ? 'modified' : 'default',
    advanced: enableGridSearch || enableBayesianSearch || enableWalkForward || enableRobustness ? 'modified' : 'off',
  };

  const goToStep = (step: StepDefinition) => {
    setActiveStep(step.id);
    onStepChange(step.wizardStep);
  };

  const applyCatalogTemplate = (nextStrategyText: string) => {
    onStrategyTextChange(nextStrategyText);
    onToggleConfirmed(false);
    setActiveStep('strategy');
    onStepChange('strategy');
    setIsCatalogDrawerOpen(false);
  };

  const handleCatalogTemplateAction = (nextStrategyText: string, executable: boolean) => {
    applyCatalogTemplate(nextStrategyText);
    if (!executable) {
      setCatalogToast(
        language === 'en'
          ? 'Reference only. Edit before running.'
          : '当前模板暂不支持直接运行，请在编辑器中修改后再执行',
      );
    }
  };

  const handleParse = async () => {
    setActiveStep('strategy');
    onStepChange('strategy');
    await onParse();
  };

  const handleRun = async () => {
    if (!canRun) return;
    onStepChange('run');
    await onRun();
  };

  const renderStepButton = (step: StepDefinition, mobile = false) => {
    const active = activeStep === step.id;
    const status = stepStatuses[step.id];
    return (
      <button
        key={`${mobile ? 'mobile' : 'desktop'}-${step.id}`}
        type="button"
        className={mobile
          ? active ? activeChipButtonClass : chipButtonClass
          : `group flex w-full min-w-0 items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-all ${
            active
              ? 'border-blue-400/25 bg-blue-500/10 text-white'
              : 'border-transparent bg-transparent text-white/62 hover:border-white/10 hover:bg-white/[0.03]'
          }`}
        data-testid={mobile ? `${step.testId}-mobile` : step.testId}
        aria-current={active ? 'step' : undefined}
        onClick={() => goToStep(step)}
      >
        <span className="font-mono text-[11px] text-white/38">{step.number}</span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-semibold">{step.title}</span>
          {!mobile ? <span className="block truncate text-[11px] text-white/35">{step.description}</span> : null}
        </span>
        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${statusClass(status)}`}>
          {statusLabel(status, language)}
        </span>
      </button>
    );
  };

  const renderField = (
    label: string,
    control: React.ReactNode,
    className = '',
  ) => (
    <label className={`flex min-w-0 flex-col gap-2 ${className}`}>
      <span className={labelClass}>{label}</span>
      {control}
    </label>
  );

  const renderStepHeader = (step: StepDefinition, chips: string[]) => (
    <div className="flex min-w-0 flex-col gap-3 border-b border-white/5 pb-4 md:flex-row md:items-start md:justify-between">
      <div className="min-w-0">
        <p className={labelClass}>CURRENT STEP</p>
        <h2 className="mt-2 truncate text-xl font-semibold text-white">{step.title}</h2>
        <p className="mt-1 truncate text-sm text-white/48">{step.description}</p>
      </div>
      <div className="flex min-w-0 flex-wrap gap-2">
        {chips.map((chip) => (
          <span key={chip} className="max-w-[220px] truncate rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-white/52">
            {chip}
          </span>
        ))}
      </div>
    </div>
  );

  const renderAssetsStep = () => (
    <section data-testid="pro-step-assets" className="flex min-w-0 flex-col gap-4">
      {renderStepHeader(stepDefinitions[0], [
        code || '--',
        getBenchmarkModeLabel(benchmarkMode, code, benchmarkCode, language),
      ])}
      <div className={`${ghostCardClass} p-4 md:p-5`}>
        <div className="grid min-w-0 grid-cols-1 gap-4 md:grid-cols-2">
          {renderField(language === 'en' ? 'Ticker' : '标的代码', (
            <input
              type="text"
              className={fieldClass}
              value={code}
              onChange={(event) => onCodeChange(event.target.value.toUpperCase())}
              onKeyDown={onCodeEnter}
              placeholder="ORCL / AAPL / 600519"
              aria-label={language === 'en' ? 'Ticker' : '标的代码'}
            />
          ))}
          {renderField(language === 'en' ? 'Benchmark' : '对比基准', (
            <select
              className={`${fieldClass} appearance-none pr-10 truncate`}
              value={benchmarkMode}
              onChange={(event) => onBenchmarkModeChange(event.target.value as RuleBenchmarkMode)}
              aria-label={language === 'en' ? 'Benchmark' : '对比基准'}
            >
              {RULE_BENCHMARK_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {getBenchmarkModeLabel(option.value, code, benchmarkCode, language)}
                </option>
              ))}
            </select>
          ))}
          {benchmarkMode === 'custom_code' ? renderField(language === 'en' ? 'Custom benchmark code' : '自定义基准代码', (
            <input
              type="text"
              className={fieldClass}
              value={benchmarkCode}
              onChange={(event) => onBenchmarkCodeChange(event.target.value.toUpperCase())}
              placeholder="QQQ / SPY / 000300"
              aria-label={language === 'en' ? 'Custom benchmark code' : '自定义基准代码'}
            />
          ), 'md:col-span-2') : null}
          {renderField(language === 'en' ? 'Start date' : '开始日期', (
            <input
              type="date"
              className={fieldClass}
              value={startDate}
              onChange={(event) => onStartDateChange(event.target.value)}
              aria-label={language === 'en' ? 'Start date' : '开始日期'}
            />
          ))}
          {renderField(language === 'en' ? 'End date' : '结束日期', (
            <input
              type="date"
              className={fieldClass}
              value={endDate}
              onChange={(event) => onEndDateChange(event.target.value)}
              aria-label={language === 'en' ? 'End date' : '结束日期'}
            />
          ))}
          {renderField(language === 'en' ? 'Initial capital' : '初始资金', (
            <input
              type="number"
              className={`${fieldClass} font-mono`}
              min={1}
              value={initialCapital}
              onChange={(event) => onInitialCapitalChange(event.target.value)}
              aria-label={language === 'en' ? 'Initial capital' : '初始资金'}
            />
          ), 'md:col-span-2')}
        </div>
      </div>
      <details className={`${ghostCardClass} p-4`}>
        <summary className="cursor-pointer text-sm font-semibold text-white/72">{language === 'en' ? 'Advanced portfolio settings' : '高级组合设置'}</summary>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          {renderField(language === 'en' ? 'Asset scope' : '资产范围', (
            <select className={`${fieldClass} appearance-none pr-10 truncate`} value={portfolioMode} onChange={(event) => setPortfolioMode(event.target.value as 'single' | 'multi')}>
              <option value="single">{language === 'en' ? 'Single asset' : '单资产'}</option>
              <option value="multi">{language === 'en' ? 'Portfolio shell' : '组合壳层'}</option>
            </select>
          ))}
          {renderField(language === 'en' ? 'Rebalance cadence' : '再平衡频率', (
            <select className={`${fieldClass} appearance-none pr-10 truncate`} value={rebalanceCadence} onChange={(event) => setRebalanceCadence(event.target.value)}>
              <option value="monthly">{language === 'en' ? 'Monthly' : '每月'}</option>
              <option value="weekly">{language === 'en' ? 'Weekly' : '每周'}</option>
              <option value="quarterly">{language === 'en' ? 'Quarterly' : '每季度'}</option>
            </select>
          ))}
        </div>
      </details>
    </section>
  );

  const renderRulePreview = () => {
    const entry = parsedStrategy?.summary?.entry || parsedStrategy?.parsedStrategy.summary?.entry || '--';
    const exit = parsedStrategy?.summary?.exit || parsedStrategy?.parsedStrategy.summary?.exit || '--';
    const strategy = parsedStrategy?.summary?.strategy || parsedStrategy?.coreIntentSummary || parsedStrategy?.parsedStrategy.coreIntentSummary || getFirstLine(strategyText) || '--';
    const setupSource = getSetupSourceLabel(parsedStrategy, language);
    return (
      <div data-testid="pro-rule-preview" className={`${ghostCardClass} flex min-w-0 flex-col gap-4 p-4 md:p-5`}>
        <div className="flex min-w-0 items-start justify-between gap-3">
          <div className="min-w-0">
            <p className={labelClass}>{language === 'en' ? 'Rule preview' : '规则预览'}</p>
            <p className="mt-2 truncate text-sm font-semibold text-white">{parsedStrategy ? '策略已解析' : (language === 'en' ? 'Waiting for parse' : '等待解析')}</p>
          </div>
          <span className={`rounded-full border px-2.5 py-1 text-[11px] ${statusClass(parseStale ? 'error' : parsedStrategy ? (parsedExecutable ? 'done' : 'pending') : 'pending')}`}>
            {parseStale ? (language === 'en' ? 'Stale' : '输入已变更，请重新解析') : parsedStrategy ? (parsedExecutable ? (language === 'en' ? 'Runnable' : '可执行') : '当前不支持') : (language === 'en' ? 'Draft' : '草稿')}
          </span>
        </div>
        <div data-testid="pro-parsed-summary" className="grid min-w-0 gap-3">
          <div className="rounded-lg border border-white/5 bg-black/20 p-3">
            <p className={labelClass}>STRATEGY</p>
            <p className="mt-2 truncate text-sm text-white/72">{strategy}</p>
            <p className="mt-1 text-xs text-white/38">{setupSource}</p>
          </div>
          <div className="rounded-lg border border-white/5 bg-black/20 p-3">
            <p className={labelClass}>{language === 'en' ? 'Executable spec' : '实际执行内容'}</p>
            <div className="mt-2 flex flex-wrap gap-2">
              <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-xs text-white/62">{language === 'en' ? 'Every trading day' : '每个交易日'}</span>
              <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-xs text-white/62">100 股 / 次</span>
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-lg border border-white/5 bg-black/20 p-3">
              <p className={labelClass}>{language === 'en' ? 'Buy rules' : '买入规则'}</p>
              <p className="mt-2 text-sm text-white/72">{entry}</p>
            </div>
            <div className="rounded-lg border border-white/5 bg-black/20 p-3">
              <p className={labelClass}>{language === 'en' ? 'Sell rules' : '卖出规则'}</p>
              <p className="mt-2 text-sm text-white/72">{exit}</p>
            </div>
          </div>
          <div className="rounded-lg border border-white/5 bg-black/20 p-3">
            <p className={labelClass}>{language === 'en' ? 'Filters' : '过滤条件'}</p>
            <p className="mt-2 truncate text-sm text-white/58">{String(getStrategySpecValue(strategySpec, ['filter']) || getStrategySpecValue(strategySpec, ['filters']) || (language === 'en' ? 'None' : '无'))}</p>
          </div>
        </div>
        {assumptionItems.length > 0 ? (
          <div data-testid="pro-assumption-summary" className="rounded-lg border border-white/5 bg-black/20 p-3">
            <p className={labelClass}>{language === 'en' ? 'Assumptions' : '默认补全与提醒'}</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {assumptionItems.map((item, index) => (
                <span key={`${item}-${index}`} className="max-w-full truncate rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-xs text-white/58">{item}</span>
              ))}
            </div>
          </div>
        ) : null}
        {parsedStrategy && !parsedExecutable ? (
          <div data-testid="pro-unsupported-guidance" className="rounded-lg border border-amber-400/20 bg-amber-400/10 p-3">
            <p className="text-sm font-semibold text-amber-100">当前不支持</p>
            <p className="mt-1 text-sm text-amber-50/70">{parsedStrategy.unsupportedReason || parsedStrategy.parsedStrategy.unsupportedReason || '当前解析结果需要改写后再执行。'}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {(parsedStrategy.rewriteSuggestions || parsedStrategy.parsedStrategy.rewriteSuggestions || []).map((item) => {
                const record = item as Record<string, unknown>;
                const label = String(record.label || '改写成当前可执行版本');
                const nextStrategyText = String(record.strategyText || record.strategy_text || '');
                if (!nextStrategyText) return null;
                return (
                  <button
                    key={nextStrategyText}
                    type="button"
                    className={secondaryButtonClass}
                    onClick={() => onApplyRewriteSuggestion(nextStrategyText)}
                  >
                    {label}: {nextStrategyText}
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}
      </div>
    );
  };

  const renderStrategyStep = () => (
    <section data-testid="pro-step-strategy" className="flex min-w-0 flex-col gap-4">
      {renderStepHeader(stepDefinitions[1], [
        parseStale ? (language === 'en' ? 'stale' : '需要重新解析') : parsedStrategy ? (language === 'en' ? 'parsed' : '已解析') : (language === 'en' ? 'draft' : '草稿'),
        confirmed ? (language === 'en' ? 'confirmed' : '已确认') : (language === 'en' ? 'pending confirm' : '待确认'),
      ])}
      <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
        <div className={`${ghostCardClass} flex min-w-0 flex-col gap-4 p-4 md:p-5`}>
          {renderField(language === 'en' ? 'Strategy text' : '策略文本', (
            <textarea
              value={strategyText}
              onChange={(event) => {
                onStrategyTextChange(event.target.value);
                onToggleConfirmed(false);
              }}
              rows={10}
              className={`${fieldClass} min-h-[230px] resize-y leading-6`}
              aria-label={language === 'en' ? 'Strategy text' : '策略文本'}
            />
          ))}
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <button type="button" className={secondaryButtonClass} onClick={() => setIsCatalogDrawerOpen(true)} data-testid="pro-open-template-drawer">
              <PanelRightOpen className="h-4 w-4" />
              {language === 'en' ? 'Templates' : '从模板库导入...'}
            </button>
            <button type="button" className={secondaryButtonClass} onClick={() => void handleParse()} disabled={isParsing || !strategyText.trim()}>
              <Sparkles className="h-4 w-4" />
              {isParsing ? (language === 'en' ? 'Parsing...' : '解析中...') : (language === 'en' ? 'Parse strategy' : '解析策略')}
            </button>
            <button type="button" className={secondaryButtonClass} onClick={onReset}>
              <RotateCw className="h-4 w-4" />
              {language === 'en' ? 'Reset' : '重置'}
            </button>
          </div>
          <div className="flex min-w-0 flex-wrap gap-2">
            {strategyCatalogGroups.flatMap((group) => group.templates).slice(0, 4).map((template, index) => (
              <button
                key={template.id}
                type="button"
                className={chipButtonClass}
                aria-label={template.name[language]}
                onClick={() => applyCatalogTemplate(template.editorText[language])}
              >
                {index === 0 ? 'MACD' : index === 1 ? 'SMA/EMA' : index === 2 ? 'RSI' : 'DCA'}
              </button>
            ))}
          </div>
          {catalogToast ? <p data-testid="pro-strategy-catalog-toast" role="status" className="rounded-lg border border-amber-400/20 bg-amber-400/10 px-3 py-2 text-sm text-amber-100">{catalogToast}</p> : null}
          {appliedRewriteText ? <p className="rounded-lg border border-blue-400/20 bg-blue-400/10 px-3 py-2 text-sm text-blue-100">已应用建议改写</p> : null}
          {parseError ? <ApiErrorAlert error={parseError} /> : null}
        </div>
        <div className="flex min-w-0 flex-col gap-4">
          {renderRulePreview()}
          <label className="flex items-center gap-2.5 rounded-lg border border-white/5 bg-white/[0.02] p-3 text-sm text-white/70">
            <input
              type="checkbox"
              className={checkboxClass}
              checked={confirmed}
              disabled={!parsedStrategy || !parsedExecutable || parseStale}
              onChange={(event) => onToggleConfirmed(event.target.checked)}
            />
            <span>{language === 'en' ? 'I reviewed the current parse result and execution assumptions.' : '我已确认当前解析结果与执行假设。'}</span>
          </label>
          <details className={`${ghostCardClass} p-4`}>
            <summary className="cursor-pointer text-sm font-semibold text-white/72">{language === 'en' ? 'Advanced engine settings' : '高级引擎设置'}</summary>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {['Signal confirmation period', 'Cooldown', 'Max signal frequency', 'Conflict handling'].map((label) => (
                <div key={label} className="rounded-lg border border-white/5 bg-black/20 p-3 text-sm text-white/58">
                  {language === 'en' ? label : {
                    'Signal confirmation period': '信号确认周期',
                    Cooldown: '冷却期',
                    'Max signal frequency': '最大信号频率',
                    'Conflict handling': '冲突处理',
                  }[label]}
                </div>
              ))}
            </div>
          </details>
        </div>
      </div>
    </section>
  );

  const renderOrdersStep = () => (
    <section data-testid="pro-step-orders" className="flex min-w-0 flex-col gap-4">
      {renderStepHeader(stepDefinitions[2], [
        `${language === 'en' ? 'event-driven' : '事件驱动'} ${formatBoolean(eventDriven, language)}`,
        `${language === 'en' ? 'risk' : '风险'} ${riskRows.length || 'default'}`,
      ])}
      <div className={`${ghostCardClass} p-4 md:p-5`}>
        <div className="flex min-w-0 flex-wrap gap-2">
          <button
            type="button"
            className={ordersTab === 'routing' ? activeChipButtonClass : chipButtonClass}
            aria-pressed={ordersTab === 'routing'}
            onClick={() => setOrdersTab('routing')}
          >
            {language === 'en' ? 'Execution routing' : '执行路由'}
          </button>
          <button
            type="button"
            className={ordersTab === 'guards' ? activeChipButtonClass : chipButtonClass}
            aria-pressed={ordersTab === 'guards'}
            onClick={() => setOrdersTab('guards')}
          >
            {language === 'en' ? 'Risk guards' : '风险护栏'}
          </button>
        </div>
        {ordersTab === 'routing' ? (
          <div className="mt-5 grid gap-3 md:grid-cols-2">
            {[
              { label: language === 'en' ? 'Event-driven execution' : '事件驱动执行', value: eventDriven, setter: setEventDriven },
              { label: language === 'en' ? 'Stop-loss route' : '止损路由', value: enableStopLoss, setter: setEnableStopLoss },
              { label: language === 'en' ? 'Take-profit route' : '止盈路由', value: enableTakeProfit, setter: setEnableTakeProfit },
            ].map((item) => (
              <label key={item.label} className="flex items-center gap-2.5 rounded-lg border border-white/5 bg-black/20 p-3 text-sm text-white/70">
                <input type="checkbox" className={checkboxClass} checked={item.value} onChange={(event) => item.setter(event.target.checked)} />
                <span>{item.label}</span>
              </label>
            ))}
            <details className="rounded-lg border border-white/5 bg-black/20 p-3 md:col-span-2">
              <summary className="cursor-pointer text-sm font-semibold text-white/70">{language === 'en' ? 'Advanced route details' : '高级路由细节'}</summary>
              <label className="mt-3 flex items-center gap-2.5 text-sm text-white/62">
                <input type="checkbox" className={checkboxClass} checked={enableTrailingStop} onChange={(event) => setEnableTrailingStop(event.target.checked)} />
                <span>{language === 'en' ? 'Trailing stop route' : '追踪止损路由'}</span>
              </label>
            </details>
          </div>
        ) : (
          <div className="mt-5 grid gap-4">
            <div className="grid gap-3 md:grid-cols-2">
              {renderField(language === 'en' ? 'Max position' : '最大仓位', (
                <input value={maxPositionPct} onChange={(event) => setMaxPositionPct(event.target.value)} className={fieldClass} />
              ))}
              {renderField(language === 'en' ? 'Max exposure' : '最大组合敞口', (
                <input value={maxExposurePct} onChange={(event) => setMaxExposurePct(event.target.value)} className={fieldClass} />
              ))}
              {renderField(language === 'en' ? 'Max drawdown stop' : '最大回撤停止', (
                <input value={maxDrawdownPct} onChange={(event) => setMaxDrawdownPct(event.target.value)} className={fieldClass} />
              ))}
              {renderField(language === 'en' ? 'Per-trade risk' : '单笔风险', (
                <input value={perTradeRiskPct} onChange={(event) => setPerTradeRiskPct(event.target.value)} className={fieldClass} />
              ))}
              {renderField(language === 'en' ? 'Max concurrent holdings' : '最大同时持仓', (
                <input value={maxHoldings} onChange={(event) => setMaxHoldings(event.target.value)} className={fieldClass} />
              ), 'md:col-span-2')}
            </div>
          </div>
        )}
        <div data-testid="pro-risk-controls-summary" className="mt-4 rounded-lg border border-white/5 bg-black/20 p-3">
          <p className={labelClass}>PARSED RISK</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {riskRows.length > 0 ? riskRows.map((row) => (
              <span key={row.key} className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-white/62">
                <span>{row.label}</span>
                <span>{formatPercent(row.value)}</span>
              </span>
            )) : (
              <span className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-white/45">
                {language === 'en' ? 'Default guard rails' : '默认护栏'}
              </span>
            )}
          </div>
        </div>
      </div>
    </section>
  );

  const renderCostsStep = () => (
    <section data-testid="pro-step-costs" className="flex min-w-0 flex-col gap-4">
      {renderStepHeader(stepDefinitions[3], [
        `${language === 'en' ? 'fees' : '手续费'} ${feeBps || 0} BP`,
        `${language === 'en' ? 'slippage' : '滑点'} ${slippageBps || 0} BP`,
      ])}
      <div className={`${ghostCardClass} p-4 md:p-5`}>
        <div className="grid min-w-0 gap-4 md:grid-cols-2">
          {renderField(language === 'en' ? 'Lookback window' : '回看范围', (
            <input type="number" min={10} max={5000} value={lookbackBars} onChange={(event) => onLookbackBarsChange(event.target.value)} className={fieldClass} aria-label={language === 'en' ? 'Lookback window' : '回看范围'} />
          ))}
          {renderField(language === 'en' ? 'Fees BP' : '手续费 BP', (
            <input type="number" min={0} max={500} value={feeBps} onChange={(event) => onFeeBpsChange(event.target.value)} className={fieldClass} aria-label={language === 'en' ? 'Fees BP' : '手续费 BP'} />
          ))}
          {renderField(language === 'en' ? 'Slippage BP' : '滑点 BP', (
            <input type="number" min={0} max={500} value={slippageBps} onChange={(event) => onSlippageBpsChange(event.target.value)} className={fieldClass} aria-label={language === 'en' ? 'Slippage BP' : '滑点 BP'} />
          ))}
          {renderField(language === 'en' ? 'Benchmark override' : '基准覆盖', (
            <input value={benchmarkCode} onChange={(event) => onBenchmarkCodeChange(event.target.value.toUpperCase())} placeholder="QQQ / SPY / 000300" className={fieldClass} />
          ))}
        </div>
        <p className="mt-4 truncate text-xs text-white/38">{language === 'en' ? 'Compact cost assumptions only; full result attribution remains on the result route.' : '这里只保留紧凑成本假设；完整归因留在结果页。'}</p>
      </div>
    </section>
  );

  const renderAdvancedStep = () => (
    <section data-testid="pro-step-advanced" className="flex min-w-0 flex-col gap-4">
      {renderStepHeader(stepDefinitions[4], [
        advancedTab === 'optimization' ? (language === 'en' ? 'optimization' : '优化') : (language === 'en' ? 'robustness' : '稳健性'),
        stepStatuses.advanced === 'off' ? (language === 'en' ? 'off' : '关闭') : (language === 'en' ? 'modified' : '已修改'),
      ])}
      <div className={`${ghostCardClass} p-4 md:p-5`}>
        <div className="flex min-w-0 flex-wrap gap-2">
          <button type="button" onClick={() => setAdvancedTab('optimization')} className={advancedTab === 'optimization' ? activeChipButtonClass : chipButtonClass}>{language === 'en' ? 'Optimization' : '优化'}</button>
          <button type="button" onClick={() => setAdvancedTab('robustness')} className={advancedTab === 'robustness' ? activeChipButtonClass : chipButtonClass}>{language === 'en' ? 'Robustness' : '稳健性'}</button>
        </div>
        <div className="mt-5 grid gap-3">
          {advancedTab === 'optimization' ? (
            <>
              <details data-testid="pro-advanced-grid-search" className="rounded-lg border border-white/5 bg-black/20 p-3">
                <summary className="cursor-pointer text-sm font-semibold text-white/70">Grid Search</summary>
                <label className="mt-3 flex items-center gap-2.5 text-sm text-white/62">
                  <input aria-label="启用 Grid Search" type="checkbox" className={checkboxClass} checked={enableGridSearch} onChange={(event) => setEnableGridSearch(event.target.checked)} />
                  <span>{language === 'en' ? 'Enable Grid Search' : '启用 Grid Search'}</span>
                </label>
                {enableGridSearch ? <div className="mt-3 rounded-lg border border-white/5 bg-white/[0.02] p-3 text-sm text-white/52">MA window / RSI threshold / risk grid</div> : null}
              </details>
              <details data-testid="pro-advanced-bayesian" className="rounded-lg border border-white/5 bg-black/20 p-3">
                <summary className="cursor-pointer text-sm font-semibold text-white/70">Bayesian Search</summary>
                <label className="mt-3 flex items-center gap-2.5 text-sm text-white/62">
                  <input type="checkbox" className={checkboxClass} checked={enableBayesianSearch} onChange={(event) => setEnableBayesianSearch(event.target.checked)} />
                  <span>{language === 'en' ? 'Enable Bayesian Search' : '启用 Bayesian Search'}</span>
                </label>
                {enableBayesianSearch ? <div className="mt-3 rounded-lg border border-white/5 bg-white/[0.02] p-3 text-sm text-white/52">Trials / acquisition / bounds</div> : null}
              </details>
            </>
          ) : (
            <>
              <details className="rounded-lg border border-white/5 bg-black/20 p-3">
                <summary className="cursor-pointer text-sm font-semibold text-white/70">Walk-forward</summary>
                <label className="mt-3 flex items-center gap-2.5 text-sm text-white/62">
                  <input type="checkbox" className={checkboxClass} checked={enableWalkForward} onChange={(event) => setEnableWalkForward(event.target.checked)} />
                  <span>{language === 'en' ? 'Enable walk-forward validation' : '启用 Walk-forward 验证'}</span>
                </label>
              </details>
              <details className="rounded-lg border border-white/5 bg-black/20 p-3">
                <summary className="cursor-pointer text-sm font-semibold text-white/70">Robustness</summary>
                <label className="mt-3 flex items-center gap-2.5 text-sm text-white/62">
                  <input type="checkbox" className={checkboxClass} checked={enableRobustness} onChange={(event) => setEnableRobustness(event.target.checked)} />
                  <span>{language === 'en' ? 'Enable robustness sweep' : '启用稳健性扫描'}</span>
                </label>
              </details>
            </>
          )}
        </div>
      </div>
    </section>
  );

  const activeStepDefinition = stepDefinitions.find((step) => step.id === activeStep) || stepDefinitions[0];
  const renderActiveStep = () => {
    if (activeStep === 'strategy') return renderStrategyStep();
    if (activeStep === 'orders') return renderOrdersStep();
    if (activeStep === 'costs') return renderCostsStep();
    if (activeStep === 'advanced') return renderAdvancedStep();
    return renderAssetsStep();
  };

  const renderExecutionRail = (mobile = false) => (
    <aside
      data-testid={mobile ? 'pro-mobile-execution-summary' : 'pro-execution-rail'}
      className={`${ghostCardClass} ${mobile ? 'p-4' : 'lg:sticky lg:top-6 max-h-[calc(100vh-6rem)] overflow-y-auto no-scrollbar p-4'} flex min-w-0 flex-col gap-4`}
    >
      <div>
        <p className={labelClass}>EXECUTION SUMMARY</p>
        <div className="mt-3 grid gap-2 text-xs">
          {[
            ['SYMBOL', code || '--'],
            ['BENCHMARK', getBenchmarkModeLabel(benchmarkMode, code, benchmarkCode, language)],
            ['DATE RANGE', `${startDate || '--'} -> ${endDate || '--'}`],
            ['CAPITAL', initialCapital || '--'],
          ].map(([label, value]) => (
            <div key={label} className="flex min-w-0 items-center justify-between gap-3 rounded-lg border border-white/5 bg-black/20 px-3 py-2">
              <span className="shrink-0 text-white/35">{label}</span>
              <span className="min-w-0 truncate font-mono text-white/72">{value}</span>
            </div>
          ))}
        </div>
      </div>
      <div>
        <p className={labelClass}>STRATEGY</p>
        <div className="mt-3 grid gap-2 text-xs">
          <div className="flex items-center justify-between gap-3 rounded-lg border border-white/5 bg-black/20 px-3 py-2">
            <span className="text-white/35">PARSE</span>
            <span className="truncate text-white/72">{parseStale ? (language === 'en' ? 'stale' : '需要重新解析') : parsedStrategy ? (language === 'en' ? 'synced' : '已同步') : (language === 'en' ? 'pending' : '待解析')}</span>
          </div>
          <div className="flex items-center justify-between gap-3 rounded-lg border border-white/5 bg-black/20 px-3 py-2">
            <span className="text-white/35">ENGINE</span>
            <span className="truncate text-white/72">{String(getStrategySpecValue(strategySpec, ['strategy_type']) || parsedStrategy?.parsedStrategy.strategyKind || 'deterministic')}</span>
          </div>
          <div className="flex items-center justify-between gap-3 rounded-lg border border-white/5 bg-black/20 px-3 py-2">
            <span className="text-white/35">CONFIRM</span>
            <span className="truncate text-white/72">{confirmed ? (language === 'en' ? 'confirmed' : '已确认') : (language === 'en' ? 'pending' : '待确认')}</span>
          </div>
        </div>
      </div>
      <div>
        <p className={labelClass}>RISK</p>
        <div className="mt-3 grid gap-2 text-xs">
          {[
            ['STOP LOSS', formatBoolean(enableStopLoss, language)],
            ['TAKE PROFIT', formatBoolean(enableTakeProfit, language)],
            ['TRAILING', formatBoolean(enableTrailingStop, language)],
            ['LEVEL', riskRows.length > 1 ? (language === 'en' ? 'guarded' : '护栏') : (language === 'en' ? 'default' : '默认')],
          ].map(([label, value]) => (
            <div key={label} className="flex min-w-0 items-center justify-between gap-3 rounded-lg border border-white/5 bg-black/20 px-3 py-2">
              <span className="text-white/35">{label}</span>
              <span className="truncate text-white/72">{value}</span>
            </div>
          ))}
        </div>
      </div>
      <div data-testid={mobile ? 'pro-mobile-execution-readiness' : 'pro-execution-readiness'}>
        <p className={labelClass}>READINESS</p>
        <div className="mt-3 grid gap-2">
          {readiness.map((item) => (
            <div key={item.key} className="flex items-center gap-2 text-xs text-white/60">
              {item.ready ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-300" /> : <XCircle className="h-3.5 w-3.5 text-rose-300" />}
              <span>{item.label}</span>
            </div>
          ))}
        </div>
        <p className={`mt-3 rounded-lg border px-3 py-2 text-xs ${canRun ? 'border-emerald-400/15 bg-emerald-400/10 text-emerald-100' : 'border-amber-400/15 bg-amber-400/10 text-amber-100'}`}>
          {readinessNote}
        </p>
      </div>
      <div>
        <p className={labelClass}>ACTIONS</p>
        <div className="mt-3 grid gap-2">
          <button
            type="button"
            className={primaryButtonClass}
            onClick={() => void handleRun()}
            disabled={!canRun || isSubmitting}
          >
            <Play className="h-4 w-4" />
            {isSubmitting ? (language === 'en' ? 'Opening result...' : '正在打开结果...') : (language === 'en' ? 'Execute backtest task' : '执行回测任务')}
          </button>
          <button type="button" className={secondaryButtonClass} onClick={() => goToStep(stepDefinitions[2])}>
            <ShieldCheck className="h-4 w-4" />
            {language === 'en' ? 'Review risk' : '查看风控'}
          </button>
          <button type="button" className={secondaryButtonClass} onClick={() => goToStep(stepDefinitions[1])}>
            <Sparkles className="h-4 w-4" />
            {language === 'en' ? 'Edit strategy' : '编辑策略'}
          </button>
        </div>
      </div>
      {runError ? <ApiErrorAlert error={runError} /> : null}
      {latestHistory ? (
        <div className="border-t border-white/5 pt-4">
          <p className={labelClass}>LAST RUN</p>
          <div className="mt-3 rounded-lg border border-white/5 bg-black/20 p-3">
            <div className="flex min-w-0 items-center justify-between gap-2">
              <span className="truncate font-mono text-sm text-white">{latestHistory.code || '--'}</span>
              <span className="truncate text-xs text-white/45">{latestHistory.status || '--'}</span>
            </div>
            <div className="mt-1 truncate text-xs text-white/35">{latestHistory.runAt?.slice(0, 10) || '--'}</div>
            <button type="button" className={`${secondaryButtonClass} mt-3 w-full`} onClick={() => onOpenHistoryRun(latestHistory)}>
              {language === 'en' ? 'Open' : '查看'}
            </button>
          </div>
        </div>
      ) : null}
    </aside>
  );

  const renderResultsDrawer = () => (
    <section data-testid="pro-results-history-drawer" className={`${ghostCardClass} p-4`}>
      <div className="flex min-w-0 flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="min-w-0">
          <p className={labelClass}>RESULTS & HISTORY</p>
          <p className="mt-1 truncate text-sm text-white/52">
            {latestHistory
              ? `${latestHistory.code || '--'} · ${latestHistory.status || '--'} · ${latestHistory.runAt?.slice(0, 10) || '--'}`
              : (language === 'en' ? 'No deterministic result selected' : '暂无当前结果')}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className={secondaryButtonClass} onClick={() => setResultsOpen((value) => !value)}>
            <ChevronRight className="h-4 w-4" />
            {resultsOpen ? (language === 'en' ? 'Collapse' : '收起') : (language === 'en' ? 'Expand result' : '展开结果')}
          </button>
          <button type="button" className={secondaryButtonClass} onClick={() => setResultsOpen(true)}>
            <BookOpen className="h-4 w-4" />
            {language === 'en' ? 'History' : '历史记录'}
          </button>
        </div>
      </div>
      <div data-testid="pro-results-history-content" hidden={!resultsOpen} className="mt-4 grid gap-3">
        {historyError ? <ApiErrorAlert error={historyError} /> : null}
        <div className="flex items-center justify-between gap-3 text-xs text-white/40">
          <span>{language === 'en' ? `${historyTotal} runs · page ${historyPage}` : `历史 ${historyTotal} 条 · 第 ${historyPage} 页`}</span>
          <button type="button" className={secondaryButtonClass} onClick={onRefreshHistory} disabled={isLoadingHistory}>
            {isLoadingHistory ? (language === 'en' ? 'Refreshing...' : '刷新中...') : (language === 'en' ? 'Refresh' : '刷新')}
          </button>
        </div>
        {historyItems.length > 0 ? (
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {historyItems.slice(0, 6).map((item) => (
              <article key={item.id} className={`rounded-lg border bg-black/20 p-3 ${selectedRunId === item.id ? 'border-blue-400/35' : 'border-white/5'}`}>
                <div className="flex min-w-0 items-center justify-between gap-2">
                  <span className="truncate font-mono text-sm text-white">{item.code || '--'}</span>
                  <span className="shrink-0 rounded-full border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[10px] text-white/45">#{item.id}</span>
                </div>
                <p className="mt-1 truncate text-xs text-white/38">{item.runAt?.slice(0, 10) || '--'} · {item.status || '--'}</p>
                <button type="button" className={`${secondaryButtonClass} mt-3 w-full`} onClick={() => onOpenHistoryRun(item)}>
                  {language === 'en' ? 'Open' : '查看'}
                </button>
              </article>
            ))}
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-white/10 bg-white/[0.02] p-4 text-sm text-white/45">
            {language === 'en' ? 'No saved deterministic runs yet.' : '当前还没有已保存的确定性回测。'}
          </div>
        )}
        {renderPresetDrawerItems()}
      </div>
    </section>
  );

  const renderPresetDrawerItems = () => {
    const rawPresets = (() => {
      try {
        return JSON.parse(window.localStorage.getItem(RULE_BACKTEST_PRESET_STORAGE_KEY) || '[]') as Array<Record<string, unknown>>;
      } catch {
        return [];
      }
    })();
    if (rawPresets.length === 0) return null;
    return (
      <div data-testid="backtest-setup-presets" className="grid gap-2 border-t border-white/5 pt-3">
        <p className={labelClass}>{language === 'en' ? 'Preset shortcuts' : '快速预设'}</p>
        {rawPresets.slice(0, 3).map((preset) => (
          <button
            key={String(preset.id || preset.name)}
            type="button"
            className={secondaryButtonClass}
            onClick={() => {
              if (typeof preset.code === 'string') onCodeChange(preset.code);
              if (typeof preset.strategyText === 'string') onStrategyTextChange(preset.strategyText);
              if (typeof preset.startDate === 'string') onStartDateChange(preset.startDate);
              if (typeof preset.endDate === 'string') onEndDateChange(preset.endDate);
              if (typeof preset.lookbackBars === 'string') onLookbackBarsChange(preset.lookbackBars);
              if (typeof preset.initialCapital === 'string') onInitialCapitalChange(preset.initialCapital);
              if (typeof preset.feeBps === 'string') onFeeBpsChange(preset.feeBps);
              if (typeof preset.slippageBps === 'string') onSlippageBpsChange(preset.slippageBps);
              if (typeof preset.benchmarkMode === 'string') onBenchmarkModeChange(preset.benchmarkMode as RuleBenchmarkMode);
              if (typeof preset.benchmarkCode === 'string') onBenchmarkCodeChange(preset.benchmarkCode);
              onToggleConfirmed(false);
              setResultsOpen(false);
              setActiveStep('assets');
              onStepChange('symbol');
            }}
          >
            {language === 'en' ? 'Apply' : '应用'}
          </button>
        ))}
      </div>
    );
  };

  return (
    <>
      <section
        data-testid="pro-backtest-workspace"
        data-module="rule"
        className="mx-auto flex w-full max-w-[1600px] min-w-0 flex-col gap-4 pb-20 lg:pb-0"
      >
        <div data-testid="pro-run-summary-strip" className={`${ghostCardClass} flex min-w-0 flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between`}>
          <div className="min-w-0">
            <p className={labelClass}>{language === 'en' ? 'Professional deterministic workspace' : '专业确定性回测工作台'}</p>
            <p className="mt-1 truncate text-sm text-white/62">
              {(code || '--')} · {startDate || '--'} {'->'} {endDate || '--'} · <span className="font-mono">{initialCapital || '--'}</span>
            </p>
          </div>
          <div className="flex min-w-0 flex-wrap gap-2">
            <span className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-white/52">{parsedStrategy ? (language === 'en' ? 'parsed' : '已解析') : (language === 'en' ? 'draft' : '草稿')}</span>
            <span className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-white/52">{readinessNote}</span>
          </div>
        </div>

        <nav data-testid="pro-mobile-step-chips" className="flex min-w-0 gap-2 overflow-x-auto no-scrollbar lg:hidden" aria-label={language === 'en' ? 'Professional steps' : '专业步骤'}>
          {stepDefinitions.map((step) => renderStepButton(step, true))}
        </nav>

        <div data-testid="pro-workspace-grid" className="grid min-w-0 grid-cols-1 gap-4 lg:grid-cols-[220px_minmax(0,1fr)_320px] lg:items-start">
          <aside data-testid="pro-workflow-rail" className={`${ghostCardClass} hidden min-w-0 flex-col gap-3 p-3 lg:sticky lg:top-6 lg:flex`}>
            <div className="px-1">
              <p className={labelClass}>WORKFLOW RAIL</p>
            </div>
            <div className="flex min-w-0 flex-col gap-1">
              {stepDefinitions.map((step) => renderStepButton(step))}
            </div>
            {latestHistory ? (
              <div className="mt-auto border-t border-white/5 pt-3">
                <p className={labelClass}>LAST RUN</p>
                <button type="button" aria-label={language === 'en' ? 'Open' : '查看'} className="mt-2 flex w-full min-w-0 items-center justify-between gap-2 rounded-lg border border-white/5 bg-black/20 px-3 py-2 text-left" onClick={() => onOpenHistoryRun(latestHistory)}>
                  <span className="min-w-0">
                    <span className="block truncate font-mono text-sm text-white">{latestHistory.code || '--'}</span>
                    <span className="block truncate text-[11px] text-white/35">{latestHistory.runAt?.slice(0, 10) || '--'}</span>
                  </span>
                  <span className="shrink-0 text-xs text-white/58">{language === 'en' ? 'Open' : '查看'}</span>
                </button>
              </div>
            ) : null}
          </aside>

          <main data-testid="pro-step-workspace" className={`${ghostCardClass} min-w-0 p-4 md:p-5`}>
            <AnimateStep activeStep={activeStepDefinition.id}>
              {renderActiveStep()}
            </AnimateStep>
          </main>

          <div className="hidden lg:block">
            {renderExecutionRail(false)}
          </div>
        </div>

        <div className="lg:hidden">
          {renderExecutionRail(true)}
        </div>

        {renderResultsDrawer()}

        <div className="fixed inset-x-0 bottom-0 z-40 border-t border-white/10 bg-black/90 px-4 py-3 backdrop-blur-xl lg:hidden">
          <button
            type="button"
            className={`${primaryButtonClass} w-full`}
            onClick={() => void handleRun()}
            disabled={!canRun || isSubmitting}
          >
            <Play className="h-4 w-4" />
            {language === 'en' ? 'Execute backtest task' : '执行回测任务'}
          </button>
        </div>
      </section>

      <Drawer
        isOpen={isCatalogDrawerOpen}
        onClose={() => setIsCatalogDrawerOpen(false)}
        title={language === 'en' ? 'Template library' : '模板库'}
        width="w-full max-w-[40rem]"
      >
        <div data-testid="pro-strategy-catalog-drawer" className="flex min-h-0 flex-col gap-6">
          <div className="space-y-2">
            <h3 className="text-lg font-semibold text-white">{language === 'en' ? 'Built-in template catalog' : '内置模板目录'}</h3>
            <p className="text-sm leading-6 text-white/58">
              {language === 'en'
                ? 'Browse one category at a time, then inject a template back into the strategy editor.'
                : '一次只浏览一个类别，确认后再把模板注入回策略编辑器。'}
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            {strategyCatalogGroups.map((group) => (
              <button
                key={group.id}
                type="button"
                className={activeCatalogGroup?.id === group.id ? activeChipButtonClass : chipButtonClass}
                onClick={() => setCatalogGroupId(group.id)}
              >
                {group.title[language]}
              </button>
            ))}
          </div>

          {activeCatalogGroup ? (
            <div data-testid="pro-strategy-catalog" className="flex flex-col gap-4">
              <div>
                <h4 className="text-base font-semibold text-white">{activeCatalogGroup.title[language]}</h4>
                <p className="mt-1 text-sm text-white/52">{activeCatalogGroup.description[language]}</p>
              </div>
              <div className="grid gap-4">
                {activeCatalogGroup.templates.map((template) => (
                  <article key={template.id} className={`${ghostCardClass} p-4`}>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h5 className="truncate text-base font-semibold text-white">{template.name[language]}</h5>
                        <p className="mt-1 text-sm leading-6 text-white/60">{template.description[language]}</p>
                      </div>
                      <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${
                        template.executable
                          ? 'border-blue-400/30 bg-blue-400/10 text-blue-100'
                          : 'border-amber-500/30 bg-amber-500/10 text-amber-100'
                      }`}
                      >
                        {template.executable
                          ? (language === 'en' ? 'Executable' : '可执行')
                          : (language === 'en' ? 'Not supported yet' : '当前不支持')}
                      </span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-white/70">{template.logicSummary[language]}</p>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {template.defaultParameters.map((parameter) => (
                        <span key={`${template.id}-${parameter.key}`} className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-[11px] text-white/58">
                          {parameter.label[language]}: {parameter.value}
                        </span>
                      ))}
                    </div>
                    <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-white/6 pt-4">
                      <p className="text-xs leading-5 text-white/45">
                        {template.executable
                          ? (language === 'en'
                            ? 'Maps to the current deterministic engine.'
                            : '该模板可直接映射到当前 deterministic 引擎。')
                          : (language === 'en'
                            ? 'Reference only. Edit before running.'
                            : '仅作参考模板。执行前请先在编辑器中修改。')}
                      </p>
                      <button
                        type="button"
                        className={template.executable ? secondaryButtonClass : 'inline-flex min-h-[38px] items-center justify-center gap-2 rounded-lg border border-amber-500/25 bg-amber-500/10 px-3 py-2 text-sm font-medium text-amber-100 transition-all hover:bg-amber-500/15'}
                        onClick={() => handleCatalogTemplateAction(template.editorText[language], template.executable)}
                      >
                        {template.executable
                          ? (language === 'en' ? 'Load into editor' : '填入编辑器')
                          : (language === 'en' ? 'Load as reference' : '载入参考模板')}
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </Drawer>
    </>
  );
};

const AnimateStep: React.FC<{ activeStep: WorkspaceStep; children: React.ReactNode }> = ({ activeStep, children }) => (
  <div key={activeStep} className="min-w-0">
    {children}
  </div>
);

export default ProBacktestWorkspace;
