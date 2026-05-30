import type React from 'react';
import { useEffect, useState } from 'react';
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
import { ApiErrorAlert } from '../common/ApiErrorAlert';
import { Drawer } from '../common/Drawer';
import type { RuleBacktestHistoryItem, RuleBacktestParseResponse } from '../../types/backtest';
import type { FlowProps, RuleWizardStep } from './DeterministicBacktestFlow';
import { RULE_BACKTEST_PRESET_STORAGE_KEY } from './ruleBacktestP6';
import {
  RULE_BENCHMARK_OPTIONS,
  getBenchmarkModeLabel,
  parsePositiveInt,
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

function getVisibleWorkspaceStep(currentStep: RuleWizardStep, activeStep: WorkspaceStep): WorkspaceStep {
  if (currentStep === 'symbol') {
    return 'assets';
  }
  if (currentStep === 'strategy') {
    return 'strategy';
  }
  if (currentStep === 'run') {
    return 'advanced';
  }
  if (currentStep === 'confirm') {
    return activeStep === 'costs' ? 'costs' : 'orders';
  }
  return activeStep;
}

type ProBacktestWorkspaceProps = Omit<FlowProps, 'panelMode'> & {
  language: BacktestLanguage;
  monteCarloEnabled: boolean;
  onToggleMonteCarloEnabled: (nextEnabled: boolean) => void;
  monteCarloSimulationCount: string;
  onMonteCarloSimulationCountChange: (value: string) => void;
  onMonteCarloSimulationCountBlur: () => void;
  walkForwardPresetEnabled: boolean;
  onToggleWalkForwardPresetEnabled: (nextEnabled: boolean) => void;
};

const ghostCardClass = 'bg-white/[0.02] border border-white/5 rounded-xl backdrop-blur-md transition-all hover:border-white/10';
const fieldClass = 'w-full min-w-0 min-h-[42px] rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2 text-sm leading-6 text-white outline-none transition-all focus:border-blue-500/50 focus:bg-white/[0.05]';
const checkboxClass = 'size-4 shrink-0 rounded border border-white/15 bg-white/[0.03] text-blue-300 accent-blue-400 disabled:opacity-45';
const labelClass = 'text-[10px] font-bold uppercase tracking-widest text-white/40';
const primaryButtonClass = 'inline-flex min-h-[42px] items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-blue-600 to-purple-600 px-4 py-2 text-sm font-semibold text-white shadow-[0_0_15px_rgba(139,92,246,0.3)] transition-all hover:from-blue-500 hover:to-purple-500 disabled:cursor-not-allowed disabled:opacity-45';
const secondaryButtonClass = 'inline-flex min-h-[38px] items-center justify-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm font-medium text-white/70 transition-all hover:bg-white/10 hover:text-white disabled:cursor-not-allowed disabled:opacity-45';
const chipButtonClass = 'inline-flex min-h-[34px] shrink-0 items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-white/70 transition-all hover:bg-white/10 hover:text-white';
const activeChipButtonClass = 'inline-flex min-h-[34px] shrink-0 items-center gap-2 rounded-lg border border-blue-400/35 bg-blue-500/10 px-3 py-1.5 text-xs font-semibold text-blue-100 shadow-[0_0_18px_rgba(59,130,246,0.12)]';
const plannedCardClass = 'rounded-lg border border-dashed border-white/10 bg-black/20 p-3';
const monteCarloSimulationDefault = 12;
const monteCarloSimulationMin = 1;
const monteCarloSimulationMax = 64;

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

function clampInteger(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}

function getSubmittedMonteCarloSimulationCount(value: string): number {
  return clampInteger(
    parsePositiveInt(value, monteCarloSimulationDefault, monteCarloSimulationMin),
    monteCarloSimulationMin,
    monteCarloSimulationMax,
  );
}

function formatPercent(value: unknown): string {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? `${numeric.toFixed(2)}%` : '--';
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
  return [...topLevel, ...nested].reduce<string[]>((acc, item) => {
    const msg = String((item as Record<string, unknown>).message || '').trim();
    if (msg) acc.push(msg);
    return acc;
  }, []);
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

const StepField: React.FC<{ label: string; control: React.ReactNode; className?: string }> = ({
  label,
  control,
  className = '',
}) => (
  <label className={`flex min-w-0 flex-col gap-2 ${className}`}>
    <span className={labelClass}>{label}</span>
    {control}
  </label>
);

const PlannedCapability: React.FC<{ title: string; description: string; testId?: string; language?: BacktestLanguage }> = ({
  title,
  description,
  testId,
  language = 'zh',
}) => (
  <div data-testid={testId} className={plannedCardClass}>
    <div className="flex min-w-0 items-center justify-between gap-3">
      <p className="truncate text-sm font-semibold text-white/78">{title}</p>
      <span className="shrink-0 rounded-full border border-amber-400/20 bg-amber-400/10 px-2.5 py-1 text-[11px] text-amber-100">
        {language === 'en' ? 'Planned' : '计划中'}
      </span>
    </div>
    <p className="mt-2 text-sm text-white/52">{description}</p>
  </div>
);

const StepHeader: React.FC<{ step: StepDefinition; chips: string[]; language: BacktestLanguage }> = ({ step, chips, language }) => (
  <div className="flex min-w-0 flex-col gap-3 border-b border-white/5 pb-4 md:flex-row md:items-start md:justify-between">
    <div className="min-w-0">
      <p className={labelClass}>{language === 'en' ? 'CURRENT STEP' : '当前步骤'}</p>
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
  monteCarloEnabled,
  onToggleMonteCarloEnabled,
  monteCarloSimulationCount,
  onMonteCarloSimulationCountChange,
  onMonteCarloSimulationCountBlur,
  walkForwardPresetEnabled,
  onToggleWalkForwardPresetEnabled,
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
  const [resultsOpen, setResultsOpen] = useState(false);
  const [catalogToast, setCatalogToast] = useState<string | null>(null);
  const [isCatalogDrawerOpen, setIsCatalogDrawerOpen] = useState(false);
  const [catalogGroupId, setCatalogGroupId] = useState<string>('basic');

  const parsedExecutable = getParsedExecutable(parsedStrategy);
  const strategySpec = getStrategyPreviewSpec(parsedStrategy);
  const riskRows = readRiskControls(parsedStrategy);
  const assumptionItems = getAssumptionItems(parsedStrategy, language);
  const strategyCatalogGroups = getStrategyCatalogGroups();
  const activeCatalogGroup = strategyCatalogGroups.find((group) => group.id === catalogGroupId) || strategyCatalogGroups[0];
  const latestHistory = historyItems[0] as RuleBacktestHistoryItem | undefined;
  const visibleActiveStep = getVisibleWorkspaceStep(currentStep, activeStep);

  useEffect(() => {
    if (!catalogToast) return undefined;
    const timer = window.setTimeout(() => setCatalogToast(null), 3200);
    return () => window.clearTimeout(timer);
  }, [catalogToast]);

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
  const robustnessEnabled = monteCarloEnabled || walkForwardPresetEnabled;
  const submittedMonteCarloSimulationCount = getSubmittedMonteCarloSimulationCount(monteCarloSimulationCount);
  const robustnessSummaryItems = !robustnessEnabled
    ? [language === 'en' ? 'No optional robustness diagnostics' : '本次不附加额外稳健性诊断']
    : [
      ...(monteCarloEnabled
        ? [language === 'en'
          ? `Monte Carlo · ${submittedMonteCarloSimulationCount} simulations`
          : `Monte Carlo · ${submittedMonteCarloSimulationCount} 次仿真`]
        : []),
      ...(walkForwardPresetEnabled
        ? [language === 'en' ? 'Walk-forward · fixed-window preset' : '滚动样本外 · 固定窗口预设']
        : []),
    ];

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
    orders: riskRows.length > 0 ? 'done' : 'default',
    costs: Number(feeBps) > 0 || Number(slippageBps) > 0 || benchmarkMode === 'custom_code' ? 'modified' : 'default',
    advanced: robustnessEnabled ? 'modified' : 'off',
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
    const active = visibleActiveStep === step.id;
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

  const plannedCapabilityNote = language === 'en'
    ? 'Planned. Not wired into the current backtest run.'
    : '计划中，尚未接入当前回测执行。';

  const renderAssetsStep = () => (
    <section data-testid="pro-step-assets" className="flex min-w-0 flex-col gap-4">
      <StepHeader step={stepDefinitions[0]} language={language} chips={[
        code || '--',
        getBenchmarkModeLabel(benchmarkMode, code, benchmarkCode, language),
      ]} />
      <div className={`${ghostCardClass} p-4 md:p-5`}>
        <div className="grid min-w-0 grid-cols-1 gap-4 md:grid-cols-2">
          <StepField label={language === 'en' ? 'Ticker' : '标的代码'} control={(
            <input
              type="text"
              className={fieldClass}
              value={code}
              onChange={(event) => onCodeChange(event.target.value.toUpperCase())}
              onKeyDown={onCodeEnter}
              placeholder="ORCL / AAPL / 600519"
              aria-label={language === 'en' ? 'Ticker' : '标的代码'}
            />
          )} />
          <StepField label={language === 'en' ? 'Benchmark' : '对比基准'} control={(
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
          )} />
          {benchmarkMode === 'custom_code' ? <StepField label={language === 'en' ? 'Custom benchmark code' : '自定义基准代码'} control={(
            <input
              type="text"
              className={fieldClass}
              value={benchmarkCode}
              onChange={(event) => onBenchmarkCodeChange(event.target.value.toUpperCase())}
              placeholder="QQQ / SPY / 000300"
              aria-label={language === 'en' ? 'Custom benchmark code' : '自定义基准代码'}
            />
          )} className="md:col-span-2" /> : null}
          <StepField label={language === 'en' ? 'Start date' : '开始日期'} control={(
            <input
              type="date"
              className={fieldClass}
              value={startDate}
              onChange={(event) => onStartDateChange(event.target.value)}
              aria-label={language === 'en' ? 'Start date' : '开始日期'}
            />
          )} />
          <StepField label={language === 'en' ? 'End date' : '结束日期'} control={(
            <input
              type="date"
              className={fieldClass}
              value={endDate}
              onChange={(event) => onEndDateChange(event.target.value)}
              aria-label={language === 'en' ? 'End date' : '结束日期'}
            />
          )} />
          <StepField label={language === 'en' ? 'Initial capital' : '初始资金'} control={(
            <input
              type="number"
              className={`${fieldClass} font-mono`}
              min={1}
              value={initialCapital}
              onChange={(event) => onInitialCapitalChange(event.target.value)}
              aria-label={language === 'en' ? 'Initial capital' : '初始资金'}
            />
          )} className="md:col-span-2" />
        </div>
      </div>
      <details className={`${ghostCardClass} p-4`}>
        <summary className="cursor-pointer text-sm font-semibold text-white/72">
          {language === 'en' ? 'Advanced portfolio settings (planned)' : '高级组合设置（计划中）'}
        </summary>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <PlannedCapability
            title={language === 'en' ? 'Portfolio shell' : '组合壳层'}
            description={language === 'en'
              ? 'Multi-asset portfolio execution is not wired here. Current runs still execute one parsed strategy per symbol.'
              : '多资产组合执行尚未在此接线，当前运行仍按单标的已解析策略执行。'}
            testId="pro-planned-portfolio-shell"
            language={language}
          />
          <PlannedCapability
            title={language === 'en' ? 'Rebalance cadence' : '再平衡频率'}
            description={language === 'en'
              ? 'Rebalance scheduling is shown as a future capability and does not alter the current run payload.'
              : '再平衡调度仅作为后续能力预留，当前不会改写运行 payload。'}
            testId="pro-planned-rebalance"
            language={language}
          />
          <p className="md:col-span-2 text-xs text-white/42">{plannedCapabilityNote}</p>
        </div>
      </details>
    </section>
  );

  const rulePreviewEntry = parsedStrategy?.summary?.entry || parsedStrategy?.parsedStrategy.summary?.entry || '--';
  const rulePreviewExit = parsedStrategy?.summary?.exit || parsedStrategy?.parsedStrategy.summary?.exit || '--';
  const rulePreviewStrategy = parsedStrategy?.summary?.strategy || parsedStrategy?.coreIntentSummary || parsedStrategy?.parsedStrategy.coreIntentSummary || getFirstLine(strategyText) || '--';
  const rulePreviewSetupSource = getSetupSourceLabel(parsedStrategy, language);
  const rulePreview = (
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
            <p className={labelClass}>{language === 'en' ? 'STRATEGY' : '策略'}</p>
            <p className="mt-2 truncate text-sm text-white/72">{rulePreviewStrategy}</p>
            <p className="mt-1 text-xs text-white/38">{rulePreviewSetupSource}</p>
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
              <p className="mt-2 text-sm text-white/72">{rulePreviewEntry}</p>
            </div>
            <div className="rounded-lg border border-white/5 bg-black/20 p-3">
              <p className={labelClass}>{language === 'en' ? 'Sell rules' : '卖出规则'}</p>
              <p className="mt-2 text-sm text-white/72">{rulePreviewExit}</p>
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

  const renderStrategyStep = () => (
    <section data-testid="pro-step-strategy" className="flex min-w-0 flex-col gap-4">
      <StepHeader step={stepDefinitions[1]} language={language} chips={[
        parseStale ? (language === 'en' ? 'stale' : '需要重新解析') : parsedStrategy ? (language === 'en' ? 'parsed' : '已解析') : (language === 'en' ? 'draft' : '草稿'),
        confirmed ? (language === 'en' ? 'confirmed' : '已确认') : (language === 'en' ? 'pending confirm' : '待确认'),
      ]} />
      <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
        <div className={`${ghostCardClass} flex min-w-0 flex-col gap-4 p-4 md:p-5`}>
          <StepField label={language === 'en' ? 'Strategy text' : '策略文本'} control={(
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
          )} />
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <button type="button" className={secondaryButtonClass} onClick={() => setIsCatalogDrawerOpen(true)} data-testid="pro-open-template-drawer">
              <PanelRightOpen className="size-4" />
              {language === 'en' ? 'Templates' : '从模板库导入...'}
            </button>
            <button type="button" className={secondaryButtonClass} onClick={() => void handleParse()} disabled={isParsing || !strategyText.trim()}>
              <Sparkles className="size-4" />
              {isParsing ? (language === 'en' ? 'Parsing...' : '解析中...') : (language === 'en' ? 'Parse strategy' : '解析策略')}
            </button>
            <button type="button" className={secondaryButtonClass} onClick={onReset}>
              <RotateCw className="size-4" />
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
          {rulePreview}
          <label className="flex items-center gap-2.5 rounded-lg border border-white/5 bg-white/[0.02] p-3 text-sm text-white/70">
            <input
              type="checkbox"
              aria-label={language === 'en' ? 'Confirm parse result' : '确认解析结果'}
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
      <StepHeader step={stepDefinitions[2]} language={language} chips={[
        language === 'en' ? 'parsed strategy execution' : '按解析策略执行',
        riskRows.length > 0
          ? `${language === 'en' ? 'parsed risk' : '解析风险'} ${riskRows.length}`
          : (language === 'en' ? 'local overrides planned' : '本地覆盖计划中'),
      ]} />
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
            <PlannedCapability
              title={language === 'en' ? 'Execution routing override' : '执行路由覆盖（计划中）'}
              description={language === 'en'
                ? 'Event-driven routing, stop-loss routing, and take-profit routing are not wired into the current executor.'
                : '事件驱动、止损路由、止盈路由尚未接入当前执行器。'}
              testId="pro-planned-routing-overrides"
              language={language}
            />
            <PlannedCapability
              title={language === 'en' ? 'Trailing stop route' : '追踪止损路由（计划中）'}
              description={language === 'en'
                ? 'Trailing-stop route configuration is reserved for a future execution lane and does not trigger backend behavior today.'
                : '追踪止损路由仅为后续执行通道预留，当前不会触发后端行为。'}
              testId="pro-planned-trailing-route"
              language={language}
            />
          </div>
        ) : (
          <div className="mt-5 grid gap-4">
            <PlannedCapability
              title={language === 'en' ? 'Portfolio-level guard overrides' : '组合级风控覆盖（计划中）'}
              description={language === 'en'
                ? 'Max position, exposure, drawdown, and per-trade risk limits are not wired into this run payload.'
                : '最大仓位、敞口、回撤、单笔风险等组合级限制尚未接入当前运行 payload。'}
              testId="pro-planned-portfolio-guards"
              language={language}
            />
            <PlannedCapability
              title={language === 'en' ? 'Concurrent holdings cap' : '最大同时持仓（计划中）'}
              description={language === 'en'
                ? 'Concurrent-holdings caps remain a planned control and do not change the current backend execution.'
                : '最大同时持仓仍为计划中控件，当前不会改变后端执行。'}
              testId="pro-planned-max-holdings"
              language={language}
            />
          </div>
        )}
        <div data-testid="pro-risk-controls-summary" className="mt-4 rounded-lg border border-white/5 bg-black/20 p-3">
          <p className={labelClass}>{language === 'en' ? 'PARSED RISK' : '风险解析'}</p>
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
      <StepHeader step={stepDefinitions[3]} language={language} chips={[
        `${language === 'en' ? 'fees' : '手续费'} ${feeBps || 0} BP`,
        `${language === 'en' ? 'slippage' : '滑点'} ${slippageBps || 0} BP`,
      ]} />
      <div className={`${ghostCardClass} p-4 md:p-5`}>
        <div className="grid min-w-0 gap-4 md:grid-cols-2">
          <StepField label={language === 'en' ? 'Lookback window' : '回看范围'} control={(
            <input type="number" min={10} max={5000} value={lookbackBars} onChange={(event) => onLookbackBarsChange(event.target.value)} className={fieldClass} aria-label={language === 'en' ? 'Lookback window' : '回看范围'} />
          )} />
          <StepField label={language === 'en' ? 'Fees BP' : '手续费 BP'} control={(
            <input type="number" min={0} max={500} value={feeBps} onChange={(event) => onFeeBpsChange(event.target.value)} className={fieldClass} aria-label={language === 'en' ? 'Fees BP' : '手续费 BP'} />
          )} />
          <StepField label={language === 'en' ? 'Slippage BP' : '滑点 BP'} control={(
            <input type="number" min={0} max={500} value={slippageBps} onChange={(event) => onSlippageBpsChange(event.target.value)} className={fieldClass} aria-label={language === 'en' ? 'Slippage BP' : '滑点 BP'} />
          )} />
          <StepField label={language === 'en' ? 'Benchmark override' : '基准覆盖'} control={(
            <input value={benchmarkCode} onChange={(event) => onBenchmarkCodeChange(event.target.value.toUpperCase())} placeholder="QQQ / SPY / 000300" className={fieldClass} aria-label={language === 'en' ? 'Benchmark override' : '基准覆盖'} />
          )} />
        </div>
        <p className="mt-4 truncate text-xs text-white/38">{language === 'en' ? 'Compact cost assumptions only; full result attribution remains on the result route.' : '这里只保留紧凑成本假设；完整归因留在结果页。'}</p>
      </div>
    </section>
  );

  const renderAdvancedStep = () => (
    <section data-testid="pro-step-advanced" className="flex min-w-0 flex-col gap-4">
      <StepHeader step={stepDefinitions[4]} language={language} chips={[
        advancedTab === 'optimization' ? (language === 'en' ? 'optimization' : '优化') : (language === 'en' ? 'robustness' : '稳健性'),
        advancedTab === 'optimization'
          ? (language === 'en' ? 'planned only' : '计划中')
          : robustnessEnabled
            ? (language === 'en' ? 'diagnostics enabled' : '诊断已启用')
            : (language === 'en' ? 'diagnostics optional' : '诊断可选'),
      ]} />
      <div className={`${ghostCardClass} p-4 md:p-5`}>
        <div className="flex min-w-0 flex-wrap gap-2">
          <button type="button" onClick={() => setAdvancedTab('optimization')} className={advancedTab === 'optimization' ? activeChipButtonClass : chipButtonClass}>{language === 'en' ? 'Optimization' : '优化'}</button>
          <button type="button" onClick={() => setAdvancedTab('robustness')} className={advancedTab === 'robustness' ? activeChipButtonClass : chipButtonClass}>{language === 'en' ? 'Robustness' : '稳健性'}</button>
        </div>
        <div className="mt-5 grid gap-3">
          <div className={plannedCardClass}>
            <p className="text-sm font-semibold text-white/78">
              {language === 'en' ? 'Current truth label' : '当前能力说明'}
            </p>
            <p className="mt-2 text-sm text-white/52">
              {advancedTab === 'optimization'
                ? (language === 'en'
                  ? 'The current professional run only uses basic parameters plus the parsed executable strategy. Optimization controls below remain planned placeholders.'
                  : '当前专业模式实际只会提交基础参数与已解析的可执行策略；下方优化控件仍是计划中的占位能力。')
                : (language === 'en'
                  ? 'Robustness diagnostics are opt-in. When disabled, no extra diagnostics config is sent. When enabled, only the fixed walk-forward preset and chosen Monte Carlo simulation count are added, without changing the primary strategy logic.'
                  : '稳健性诊断为可选项。关闭时不会附加额外诊断参数；启用后只会追加固定滚动样本外预设和你选择的 Monte Carlo 仿真次数，不会改动主策略逻辑。')}
            </p>
          </div>
          {advancedTab === 'optimization' ? (
            <>
              <PlannedCapability
                title={language === 'en' ? 'Grid Search (planned)' : '网格搜索（计划中）'}
                description={language === 'en'
                  ? 'Parameter sweeps are not wired into the current professional executor.'
                  : '参数网格扫描尚未接入当前专业执行流。'}
                testId="pro-advanced-grid-search"
                language={language}
              />
              <PlannedCapability
                title={language === 'en' ? 'Bayesian Search (planned)' : '贝叶斯搜索（计划中）'}
                description={language === 'en'
                  ? 'Bayesian optimization remains a future capability and does not trigger backend actions today.'
                  : '贝叶斯优化仍为后续能力，当前不会触发后端动作。'}
                testId="pro-advanced-bayesian"
                language={language}
              />
            </>
          ) : (
            <>
              <div
                data-testid="pro-robustness-selection-summary"
                className="rounded-lg border border-white/5 bg-white/[0.02] p-3"
              >
                <p className="text-sm font-semibold text-white/78">
                  {language === 'en' ? 'Diagnostics included with this professional run' : '将随本次专业回测提交的诊断配置'}
                </p>
                <div className="mt-3 flex min-w-0 flex-wrap gap-2">
                  {robustnessSummaryItems.map((item) => (
                    <span
                      key={item}
                      className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${
                        robustnessEnabled
                          ? 'border-blue-400/25 bg-blue-400/10 text-blue-100'
                          : 'border-white/10 bg-white/[0.03] text-white/55'
                      }`}
                    >
                      {item}
                    </span>
                  ))}
                </div>
              </div>
              <details className={plannedCardClass} data-testid="pro-robustness-monte-carlo-panel">
                <summary className="cursor-pointer text-sm font-semibold text-white/78">
                  {language === 'en' ? 'Monte Carlo robustness diagnostics' : 'Monte Carlo 稳健性诊断'}
                </summary>
                <div className="mt-4 grid gap-4">
                  <label className="flex items-start gap-3 rounded-lg border border-white/5 bg-white/[0.02] p-3 text-sm text-white/72">
                    <input
                      type="checkbox"
                      className={checkboxClass}
                      checked={monteCarloEnabled}
                      onChange={(event) => onToggleMonteCarloEnabled(event.target.checked)}
                      aria-label={language === 'en' ? 'Enable Monte Carlo robustness diagnostics' : '启用 Monte Carlo 稳健性诊断'}
                      data-testid="pro-robustness-monte-carlo-toggle"
                    />
                    <span className="min-w-0">
                      <span className="block font-semibold text-white/82">
                      {language === 'en' ? 'Opt in to Monte Carlo diagnostics' : '按需启用 Monte Carlo 诊断'}
                      </span>
                      <span className="mt-1 block text-xs leading-5 text-white/48">
                        {language === 'en'
                          ? 'Used only for robustness diagnostics in Professional mode. It does not require re-parsing and does not change the primary execution logic.'
                          : '仅用于专业模式下的稳健性诊断，不需要重新解析策略，也不会改变主执行逻辑。'}
                      </span>
                    </span>
                  </label>
                  {monteCarloEnabled ? (
                    <div className="grid gap-3 md:grid-cols-[minmax(0,220px)_minmax(0,1fr)]">
                      <StepField label={language === 'en' ? 'Simulation count' : '仿真次数'} control={(
                        <input
                          type="number"
                          min={1}
                          max={64}
                          step={1}
                          inputMode="numeric"
                          className={`${fieldClass} font-mono`}
                          value={monteCarloSimulationCount}
                          onChange={(event) => onMonteCarloSimulationCountChange(event.target.value)}
                          onBlur={onMonteCarloSimulationCountBlur}
                          aria-label={language === 'en' ? 'Monte Carlo simulation count' : 'Monte Carlo 仿真次数'}
                          data-testid="pro-robustness-simulation-count-input"
                        />
                      )} />
                      <div className="rounded-lg border border-white/5 bg-black/20 p-3 text-sm text-white/58">
                        <p className="font-semibold text-white/74">
                          {language === 'en' ? 'Diagnostic scope' : '诊断范围'}
                        </p>
                        <p className="mt-2 leading-6">
                          {language === 'en'
                            ? 'Range 1-64. This first release exposes simulation count only; other Monte Carlo diagnostics remain hidden.'
                            : '范围 1-64。首个版本只暴露仿真次数，其余 Monte Carlo 诊断项暂不开放。'}
                        </p>
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-white/42">
                      {language === 'en'
                        ? 'Disabled by default. The professional run request stays unchanged until you opt in.'
                        : '默认关闭；未启用前，专业模式运行请求保持不变。'}
                    </p>
                  )}
                </div>
              </details>
              <details className={plannedCardClass} data-testid="pro-robustness-walk-forward-panel">
                <summary className="cursor-pointer text-sm font-semibold text-white/78">
                  {language === 'en' ? 'Walk-forward robustness preset' : '滚动样本外稳健性预设'}
                </summary>
                <div className="mt-4 grid gap-4">
                  <label className="flex items-start gap-3 rounded-lg border border-white/5 bg-white/[0.02] p-3 text-sm text-white/72">
                    <input
                      type="checkbox"
                      className={checkboxClass}
                      checked={walkForwardPresetEnabled}
                      onChange={(event) => onToggleWalkForwardPresetEnabled(event.target.checked)}
                      aria-label={language === 'en' ? 'Enable walk-forward robustness preset' : '启用滚动样本外稳健性预设'}
                      data-testid="pro-robustness-walk-forward-toggle"
                    />
                    <span className="min-w-0">
                      <span className="block font-semibold text-white/82">
                        {language === 'en' ? 'Opt in to a fixed walk-forward sample-out preset' : '按需启用固定滚动样本外诊断预设'}
                      </span>
                      <span className="mt-1 block text-xs leading-5 text-white/48">
                        {language === 'en'
                          ? 'Professional-mode diagnostics only. This uses fixed train/test windows to inspect sample-out stability, without changing primary strategy logic or requiring a re-parse.'
                          : '仅用于专业模式下的固定窗口样本外诊断，用训练窗/测试窗观察稳健性，不改变主策略逻辑，也不需要重新解析。'}
                      </span>
                    </span>
                  </label>
                  {walkForwardPresetEnabled ? (
                    <div className="grid gap-3 md:grid-cols-[minmax(0,220px)_minmax(0,1fr)]">
                      <div className="rounded-lg border border-white/5 bg-black/20 p-3 text-sm text-white/58">
                        <p className="font-semibold text-white/74">
                          {language === 'en' ? 'Fixed preset' : '固定预设'}
                        </p>
                        <p className="mt-2 font-mono text-base text-white">24 / 12 / 12 / 4</p>
                        <p className="mt-1 text-xs leading-5 text-white/42">
                          {language === 'en'
                            ? 'Fixed train / test / step / max windows'
                            : '固定训练窗 / 测试窗 / 步长 / 最大窗口'}
                        </p>
                      </div>
                      <div className="rounded-lg border border-white/5 bg-black/20 p-3 text-sm text-white/58">
                        <p className="font-semibold text-white/74">
                          {language === 'en' ? 'Diagnostic scope' : '诊断范围'}
                        </p>
                        <p className="mt-2 leading-6">
                          {language === 'en'
                            ? 'First release is preset-only. No per-field editing is exposed here, and no extra strategy parser work is required when you toggle it.'
                            : '首个版本只开放固定预设，不在这里暴露逐项数值编辑；切换开关时也不需要重新解析策略。'}
                        </p>
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-white/42">
                      {language === 'en'
                        ? 'Disabled by default. The professional run request adds no walk-forward config until you opt in.'
                        : '默认关闭；未启用前，专业模式运行请求不会附加滚动样本外配置。'}
                    </p>
                  )}
                </div>
              </details>
            </>
          )}
        </div>
      </div>
    </section>
  );

  const activeStepDefinition = stepDefinitions.find((step) => step.id === visibleActiveStep) || stepDefinitions[0];
  const activeStepContent = visibleActiveStep === 'strategy'
    ? renderStrategyStep()
    : visibleActiveStep === 'orders'
      ? renderOrdersStep()
      : visibleActiveStep === 'costs'
        ? renderCostsStep()
        : visibleActiveStep === 'advanced'
          ? renderAdvancedStep()
          : renderAssetsStep();

  const createExecutionRailContent = (readinessTestId: string) => (
    <>
      <div>
        <p className={labelClass}>{language === 'en' ? 'EXECUTION SUMMARY' : '执行摘要'}</p>
        <div className="mt-3 grid gap-2 text-xs">
          {[
            [language === 'en' ? 'SYMBOL' : '标的', code || '--'],
            [language === 'en' ? 'BENCHMARK' : '基准', getBenchmarkModeLabel(benchmarkMode, code, benchmarkCode, language)],
            [language === 'en' ? 'DATE RANGE' : '日期区间', `${startDate || '--'} -> ${endDate || '--'}`],
            [language === 'en' ? 'CAPITAL' : '初始资金', initialCapital || '--'],
          ].map(([label, value]) => (
            <div key={label} className="flex min-w-0 items-center justify-between gap-3 rounded-lg border border-white/5 bg-black/20 px-3 py-2">
              <span className="shrink-0 text-white/35">{label}</span>
              <span className="min-w-0 truncate font-mono text-white/72">{value}</span>
            </div>
          ))}
        </div>
      </div>
      <div>
        <p className={labelClass}>{language === 'en' ? 'STRATEGY' : '策略'}</p>
        <div className="mt-3 grid gap-2 text-xs">
          <div className="flex items-center justify-between gap-3 rounded-lg border border-white/5 bg-black/20 px-3 py-2">
            <span className="text-white/35">{language === 'en' ? 'PARSE' : '解析'}</span>
            <span className="truncate text-white/72">{parseStale ? (language === 'en' ? 'stale' : '需要重新解析') : parsedStrategy ? (language === 'en' ? 'synced' : '已同步') : (language === 'en' ? 'pending' : '待解析')}</span>
          </div>
          <div className="flex items-center justify-between gap-3 rounded-lg border border-white/5 bg-black/20 px-3 py-2">
            <span className="text-white/35">{language === 'en' ? 'ENGINE' : '引擎'}</span>
            <span className="truncate text-white/72">{String(getStrategySpecValue(strategySpec, ['strategy_type']) || parsedStrategy?.parsedStrategy.strategyKind || 'deterministic')}</span>
          </div>
          <div className="flex items-center justify-between gap-3 rounded-lg border border-white/5 bg-black/20 px-3 py-2">
            <span className="text-white/35">{language === 'en' ? 'CONFIRM' : '确认'}</span>
            <span className="truncate text-white/72">{confirmed ? (language === 'en' ? 'confirmed' : '已确认') : (language === 'en' ? 'pending' : '待确认')}</span>
          </div>
        </div>
      </div>
      <div>
        <p className={labelClass}>{language === 'en' ? 'RISK' : '风险'}</p>
        <div className="mt-3 grid gap-2 text-xs">
          {[
            [language === 'en' ? 'SOURCE' : '来源', parsedStrategy ? (language === 'en' ? 'parsed strategy spec' : '解析策略规格') : (language === 'en' ? 'waiting for parse' : '等待解析')],
            [language === 'en' ? 'PARSED RISK' : '解析风险', riskRows.length > 0 ? `${riskRows.length}` : (language === 'en' ? 'default only' : '仅默认值')],
            [language === 'en' ? 'LOCAL OVERRIDES' : '本地覆盖', language === 'en' ? 'planned' : '计划中'],
            [language === 'en' ? 'ROUTING CONTROLS' : '路由控件', language === 'en' ? 'not wired' : '未接线'],
          ].map(([label, value]) => (
            <div key={label} className="flex min-w-0 items-center justify-between gap-3 rounded-lg border border-white/5 bg-black/20 px-3 py-2">
              <span className="text-white/35">{label}</span>
              <span className="truncate text-white/72">{value}</span>
            </div>
          ))}
        </div>
      </div>
      <div data-testid={readinessTestId}>
        <p className={labelClass}>{language === 'en' ? 'READINESS' : '就绪度'}</p>
        <div className="mt-3 grid gap-2">
          {readiness.map((item) => (
            <div key={item.key} className="flex items-center gap-2 text-xs text-white/60">
              {item.ready ? <CheckCircle2 className="size-3.5 text-emerald-300" /> : <XCircle className="size-3.5 text-rose-300" />}
              <span>{item.label}</span>
            </div>
          ))}
        </div>
        <p className={`mt-3 rounded-lg border px-3 py-2 text-xs ${canRun ? 'border-emerald-400/15 bg-emerald-400/10 text-emerald-100' : 'border-amber-400/15 bg-amber-400/10 text-amber-100'}`}>
          {readinessNote}
        </p>
      </div>
      <div>
        <p className={labelClass}>{language === 'en' ? 'ACTIONS' : '操作'}</p>
        <div className="mt-3 grid gap-2">
          <button
            type="button"
            className={primaryButtonClass}
            onClick={() => void handleRun()}
            disabled={!canRun || isSubmitting}
          >
            <Play className="size-4" />
            {isSubmitting ? (language === 'en' ? 'Opening result...' : '正在打开结果...') : (language === 'en' ? 'Execute backtest task' : '执行回测任务')}
          </button>
          <button type="button" className={secondaryButtonClass} onClick={() => goToStep(stepDefinitions[2])}>
            <ShieldCheck className="size-4" />
            {language === 'en' ? 'Review risk' : '查看风控'}
          </button>
          <button type="button" className={secondaryButtonClass} onClick={() => goToStep(stepDefinitions[1])}>
            <Sparkles className="size-4" />
            {language === 'en' ? 'Edit strategy' : '编辑策略'}
          </button>
        </div>
      </div>
      {runError ? <ApiErrorAlert error={runError} /> : null}
      {latestHistory ? (
        <div className="border-t border-white/5 pt-4">
          <p className={labelClass}>{language === 'en' ? 'LAST RUN' : '最近运行'}</p>
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
    </>
  );
  const desktopExecutionRail = (
    <aside
      data-testid="pro-execution-rail"
      className={`${ghostCardClass} lg:sticky lg:top-6 max-h-[calc(100vh-6rem)] overflow-y-auto no-scrollbar p-4 flex min-w-0 flex-col gap-4`}
    >
      {createExecutionRailContent('pro-execution-readiness')}
    </aside>
  );
  const mobileExecutionRail = (
    <aside
      data-testid="pro-mobile-execution-summary"
      className={`${ghostCardClass} p-4 flex min-w-0 flex-col gap-4`}
    >
      {createExecutionRailContent('pro-mobile-execution-readiness')}
    </aside>
  );

  const presetDrawerRawPresets = (() => {
    try {
      return JSON.parse(window.localStorage.getItem(RULE_BACKTEST_PRESET_STORAGE_KEY) || '[]') as Array<Record<string, unknown>>;
    } catch {
      return [];
    }
  })();

  const presetDrawerItems = presetDrawerRawPresets.length === 0 ? null : (
    <div data-testid="backtest-setup-presets" className="grid gap-2 border-t border-white/5 pt-3">
      <p className={labelClass}>{language === 'en' ? 'Preset shortcuts' : '快速预设'}</p>
      {presetDrawerRawPresets.slice(0, 3).map((preset) => (
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

  const resultsDrawer = (
    <section data-testid="pro-results-history-drawer" className={`${ghostCardClass} p-4`}>
      <div className="flex min-w-0 flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="min-w-0">
          <p className={labelClass}>{language === 'en' ? 'RESULTS & HISTORY' : '结果与历史'}</p>
          <p className="mt-1 truncate text-sm text-white/52">
            {latestHistory
              ? `${latestHistory.code || '--'} · ${latestHistory.status || '--'} · ${latestHistory.runAt?.slice(0, 10) || '--'}`
              : (language === 'en' ? 'No deterministic result selected' : '暂无当前结果')}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className={secondaryButtonClass} onClick={() => setResultsOpen((value) => !value)}>
            <ChevronRight className="size-4" />
            {resultsOpen ? (language === 'en' ? 'Collapse' : '收起') : (language === 'en' ? 'Expand result' : '展开结果')}
          </button>
          <button type="button" className={secondaryButtonClass} onClick={() => setResultsOpen(true)}>
            <BookOpen className="size-4" />
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
        {presetDrawerItems}
      </div>
    </section>
  );

  return (
    <>
      <section
        data-testid="pro-backtest-workspace"
        data-module="rule"
        className="flex w-full min-w-0 flex-col gap-4 pb-12 lg:pb-0"
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
              <p className={labelClass}>{language === 'en' ? 'WORKFLOW RAIL' : '工作流导航'}</p>
            </div>
            <div className="flex min-w-0 flex-col gap-1">
              {stepDefinitions.map((step) => renderStepButton(step))}
            </div>
            {latestHistory ? (
              <div className="mt-auto border-t border-white/5 pt-3">
                <p className={labelClass}>{language === 'en' ? 'LAST RUN' : '最近运行'}</p>
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
              {activeStepContent}
            </AnimateStep>
          </main>

          <div className="hidden lg:block">
            {desktopExecutionRail}
          </div>
        </div>

        <div className="lg:hidden">
          {mobileExecutionRail}
        </div>

        {resultsDrawer}

        <div className="fixed inset-x-0 bottom-0 z-40 border-t border-white/10 bg-black/90 px-4 py-3 backdrop-blur-xl lg:hidden">
          <button
            type="button"
            className={`${primaryButtonClass} w-full`}
            onClick={() => void handleRun()}
            disabled={!canRun || isSubmitting}
          >
            <Play className="size-4" />
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
