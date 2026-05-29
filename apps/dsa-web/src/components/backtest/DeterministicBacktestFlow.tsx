import type React from 'react';
import { useState } from 'react';
import { AnimatePresence, domAnimation, LazyMotion, m } from 'motion/react';
import { ApiErrorAlert } from '../common/ApiErrorAlert';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import type { ParsedApiError } from '../../api/error';
import type {
  AssumptionMap,
  RuleBacktestHistoryItem,
  RuleBacktestParseResponse,
} from '../../types/backtest';
import {
  AssumptionList,
  Banner,
  RULE_BENCHMARK_OPTIONS,
  SectionEyebrow,
  buildPeriodicAssumptionLabels,
  getBenchmarkModeLabel,
  type RuleBenchmarkMode,
  getStrategyPreviewSpec,
  getStrategySpecValue,
} from './shared';
import {
  buildRuleStrategySummaryRows,
  formatRuleNormalizationStateLabel,
  getRuleStrategySpecSourceLabel,
  getRuleStrategyTypeLabel,
} from './strategyInspectability';
import {
  deleteRuleBacktestPreset,
  loadRuleBacktestPresets,
  type RuleBacktestPreset,
} from './ruleBacktestP6';
import { useI18n } from '../../contexts/UiLanguageContext';

export type RuleWizardStep = 'symbol' | 'setup' | 'strategy' | 'confirm' | 'run';

type BacktestLanguage = 'zh' | 'en';

const STRATEGY_EXAMPLES: Record<BacktestLanguage, string[]> = {
  zh: [
    'MACD 金叉买入，死叉卖出',
    '5日均线上穿20日均线买入，下穿卖出',
    '从2025-01-01到2025-12-31，每月定投1000美元AAPL',
    'RSI 小于 30 买入，大于 70 卖出',
  ],
  en: [
    'Buy on a MACD bullish crossover and sell on a bearish crossover',
    'Buy when the 5-day moving average crosses above the 20-day average, and sell on the reverse crossover',
    'Invest 1000 USD into AAPL every month from 2025-01-01 to 2025-12-31',
    'Buy when RSI drops below 30 and sell when it rises above 70',
  ],
};

const FLOW_PANEL_TRANSITION = {
  duration: 0.24,
  ease: [0.22, 1, 0.36, 1] as const,
};

type ParseState = 'empty' | 'ready' | 'assumed' | 'unsupported' | 'stale';

type StrategyFieldSource = 'explicit' | 'derived' | 'compat';
type StrategyPreviewRow = { label: string; value: string; source?: StrategyFieldSource | null; numericValue?: number | null };
type StrategyPreviewCardGroup = { label: string; items: string[] };
type StrategyFieldSourceHint = {
  specPaths?: string[][];
  setupKeys?: string[];
  assumptionKeys?: string[];
  assumptionKeywords?: string[];
  warningCodes?: string[];
  warningKeywords?: string[];
};

function getParsedExecutable(parsed: RuleBacktestParseResponse | null): boolean {
  if (!parsed) return false;
  if (typeof parsed.executable === 'boolean') return parsed.executable;
  return Boolean(parsed.parsedStrategy.executable);
}

function getParsedNormalizationState(parsed: RuleBacktestParseResponse | null): string {
  if (!parsed) return 'pending';
  return String(parsed.normalizationState || parsed.parsedStrategy.normalizationState || 'pending');
}

function getParsedAssumptionRecords(parsed: RuleBacktestParseResponse | null): Array<Record<string, unknown>> {
  if (!parsed) return [];
  const topLevel = Array.isArray(parsed.assumptions) ? parsed.assumptions : [];
  if (topLevel.length > 0) return topLevel;
  return Array.isArray(parsed.parsedStrategy.assumptions) ? parsed.parsedStrategy.assumptions : [];
}

function getParsedAssumptionGroups(parsed: RuleBacktestParseResponse | null): Array<Record<string, unknown>> {
  if (!parsed) return [];
  const topLevel = Array.isArray(parsed.assumptionGroups) ? parsed.assumptionGroups : [];
  if (topLevel.length > 0) return topLevel;
  return Array.isArray(parsed.parsedStrategy.assumptionGroups) ? parsed.parsedStrategy.assumptionGroups : [];
}

function getUnsupportedReason(parsed: RuleBacktestParseResponse | null): string | null {
  if (!parsed) return null;
  return String(parsed.unsupportedReason || parsed.parsedStrategy.unsupportedReason || '') || null;
}

function getUnsupportedDetails(parsed: RuleBacktestParseResponse | null): Array<Record<string, unknown>> {
  if (!parsed) return [];
  const topLevel = Array.isArray(parsed.unsupportedDetails) ? parsed.unsupportedDetails : [];
  if (topLevel.length > 0) return topLevel;
  return Array.isArray(parsed.parsedStrategy.unsupportedDetails) ? parsed.parsedStrategy.unsupportedDetails : [];
}

function getUnsupportedExtensions(parsed: RuleBacktestParseResponse | null): Array<Record<string, unknown>> {
  if (!parsed) return [];
  const topLevel = Array.isArray(parsed.unsupportedExtensions) ? parsed.unsupportedExtensions : [];
  if (topLevel.length > 0) return topLevel;
  return Array.isArray(parsed.parsedStrategy.unsupportedExtensions) ? parsed.parsedStrategy.unsupportedExtensions : [];
}

function getDetectedStrategyFamily(parsed: RuleBacktestParseResponse | null): string | null {
  if (!parsed) return null;
  return String(parsed.detectedStrategyFamily || parsed.parsedStrategy.detectedStrategyFamily || '') || null;
}

function getCoreIntentSummary(parsed: RuleBacktestParseResponse | null): string | null {
  if (!parsed) return null;
  return String(parsed.coreIntentSummary || parsed.parsedStrategy.coreIntentSummary || '') || null;
}

function getSupportedPortionSummary(parsed: RuleBacktestParseResponse | null): string | null {
  if (!parsed) return null;
  return String(parsed.supportedPortionSummary || parsed.parsedStrategy.supportedPortionSummary || '') || null;
}

function getRewriteSuggestions(parsed: RuleBacktestParseResponse | null): Array<Record<string, unknown>> {
  if (!parsed) return [];
  const topLevel = Array.isArray(parsed.rewriteSuggestions) ? parsed.rewriteSuggestions : [];
  if (topLevel.length > 0) return topLevel;
  return Array.isArray(parsed.parsedStrategy.rewriteSuggestions) ? parsed.parsedStrategy.rewriteSuggestions : [];
}

function getParseWarnings(parsed: RuleBacktestParseResponse | null): Array<Record<string, unknown>> {
  if (!parsed) return [];
  const topLevel = Array.isArray(parsed.parseWarnings) ? parsed.parseWarnings : [];
  if (topLevel.length > 0) return topLevel;
  return Array.isArray(parsed.parsedStrategy.parseWarnings) ? parsed.parsedStrategy.parseWarnings : [];
}

function hasMeaningfulNode(node: unknown): boolean {
  if (!node || typeof node !== 'object') return false;
  const candidate = node as { type?: string; rules?: unknown[] };
  if (candidate.type === 'comparison') return true;
  if (candidate.type === 'group' && Array.isArray(candidate.rules)) {
    return candidate.rules.some((child) => hasMeaningfulNode(child));
  }
  return false;
}

function getLocalizedStrategyTypeLabel(parsed: RuleBacktestParseResponse | null, language: BacktestLanguage): string {
  return getRuleStrategyTypeLabel(parsed?.parsedStrategy, getDetectedStrategyFamily(parsed), language);
}

function getStrategySpecSourceLabel(parsed: RuleBacktestParseResponse | null, language: BacktestLanguage): string {
  return getRuleStrategySpecSourceLabel(parsed?.parsedStrategy, language);
}

function formatAssumptionRecord(item: Record<string, unknown>, language: BacktestLanguage): string {
  const label = String(item.label || item.key || (language === 'en' ? 'Assumption' : '假设'));
  const value = item.value == null || item.value === '' ? '' : `${language === 'en' ? ': ' : '：'}${String(item.value)}`;
  const reason = String(item.reason || '').trim();
  return `${label}${value}${reason ? `${language === 'en' ? '. ' : '。'}${reason}` : ''}`;
}

function hasMeaningfulValue(value: unknown): boolean {
  if (value == null) return false;
  if (typeof value === 'string') return value.trim().length > 0;
  if (Array.isArray(value)) return value.length > 0;
  return true;
}

function getLegacySetupValue(setup: Record<string, unknown> | undefined, key: string): unknown {
  if (!setup) return undefined;
  if (key in setup) return setup[key];
  const camelKey = key.replace(/_([a-z])/g, (_, ch: string) => ch.toUpperCase());
  if (camelKey in setup) return setup[camelKey];
  return undefined;
}

function matchesKeyword(text: string, keywords: string[]): boolean {
  const normalized = text.trim().toLowerCase();
  if (!normalized) return false;
  return keywords.some((keyword) => normalized.includes(keyword.trim().toLowerCase()));
}

function containsCjk(value: string): boolean {
  return /[\u4e00-\u9fff]/.test(value);
}

function resolveFieldSource(
  parsed: RuleBacktestParseResponse | null,
  hint: StrategyFieldSourceHint,
): StrategyFieldSource | null {
  if (!parsed) return null;

  const assumptionItems = getParsedAssumptionRecords(parsed);
  const warnings = getParseWarnings(parsed);

  if (hint.assumptionKeys?.length || hint.assumptionKeywords?.length) {
    const hasAssumptionMatch = assumptionItems.some((item) => {
      const key = String(item.key || '').trim();
      const text = [item.label, item.reason, item.value].map((value) => String(value || '')).join(' ');
      return (hint.assumptionKeys?.includes(key) ?? false)
        || (hint.assumptionKeywords ? matchesKeyword(text, hint.assumptionKeywords) : false);
    });
    if (hasAssumptionMatch) return 'derived';
  }

  if (hint.warningCodes?.length || hint.warningKeywords?.length) {
    const hasWarningMatch = warnings.some((item) => {
      const code = String(item.code || '').trim();
      const text = String(item.message || '');
      return (hint.warningCodes?.includes(code) ?? false)
        || (hint.warningKeywords ? matchesKeyword(text, hint.warningKeywords) : false);
    });
    if (hasWarningMatch) return 'derived';
  }

  const directSpec = parsed.parsedStrategy.strategySpec;
  if (directSpec && typeof directSpec === 'object') {
    const hasSpecValue = (hint.specPaths || []).some((path) => hasMeaningfulValue(getStrategySpecValue(directSpec as Record<string, unknown>, path)));
    if (hasSpecValue) return 'explicit';
  }

  const setup = parsed.parsedStrategy.setup;
  const hasSetupValue = (hint.setupKeys || []).some((key) => hasMeaningfulValue(getLegacySetupValue(setup, key)));
  if (hasSetupValue || (!directSpec && setup && typeof setup === 'object')) {
    return 'compat';
  }

  return null;
}

function getFieldSourceLabel(source: StrategyFieldSource | null | undefined, language: BacktestLanguage = 'zh'): string | null {
  if (source === 'explicit') return language === 'en' ? 'Explicit spec' : '显式结构化';
  if (source === 'derived') return language === 'en' ? 'Derived / defaulted' : '默认/推断';
  if (source === 'compat') return language === 'en' ? 'Compat setup' : '兼容 setup';
  return null;
}

function row(
  label: string,
  value: string,
  parsed: RuleBacktestParseResponse | null,
  hint: StrategyFieldSourceHint,
): StrategyPreviewRow {
  return {
    label,
    value,
    source: resolveFieldSource(parsed, hint),
  };
}

function buildConfirmationRows(
  parsed: RuleBacktestParseResponse | null,
  currentCode: string,
  startDate: string,
  endDate: string,
  language: BacktestLanguage,
): StrategyPreviewRow[] {
  if (!parsed) return [];
  const sourceHints: Record<string, StrategyFieldSourceHint> = {
    strategy_family: { specPaths: [['strategy_type']] },
    symbol: { specPaths: [['symbol']], setupKeys: ['symbol'] },
    date_range: { specPaths: [['date_range', 'start_date'], ['date_range', 'end_date']], setupKeys: ['start_date', 'end_date'] },
    initial_capital: { specPaths: [['capital', 'initial_capital']], setupKeys: ['initial_capital'] },
    frequency: { specPaths: [['schedule', 'frequency'], ['execution', 'frequency']], setupKeys: ['execution_frequency'] },
    entry: {
      specPaths: [['entry'], ['signal']],
      setupKeys: ['order_mode', 'quantity_per_trade', 'amount_per_trade', 'indicator_family', 'fast_period', 'slow_period', 'signal_period', 'period', 'lower_threshold', 'upper_threshold'],
      warningCodes: ['default_macd_periods'],
      warningKeywords: ['默认使用', '未显式写出'],
    },
    fill_timing: {
      specPaths: [['entry', 'price_basis'], ['execution', 'fill_timing']],
      setupKeys: ['execution_price_basis'],
      assumptionKeys: ['fill_timing', 'entry_fill_timing', 'simulated_entry_timing'],
      assumptionKeywords: ['成交时点', '开盘执行', '下一根开盘'],
    },
    exit: { specPaths: [['exit'], ['end_behavior', 'policy']], setupKeys: ['exit_policy'] },
    cash_policy: { specPaths: [['position_behavior', 'cash_policy']], setupKeys: ['cash_policy'] },
    signal_timing: {
      specPaths: [['execution', 'signal_timing']],
      assumptionKeys: ['analysis_signal_timing', 'signal_evaluation_timing'],
      assumptionKeywords: ['信号时点', '收盘后判定'],
    },
    end_behavior: { specPaths: [['end_behavior', 'policy']] },
    costs: { specPaths: [['costs', 'fee_bps'], ['costs', 'slippage_bps']], setupKeys: ['fee_bps', 'slippage_bps'] },
  };

  return buildRuleStrategySummaryRows(parsed.parsedStrategy, currentCode, startDate, endDate, getDetectedStrategyFamily(parsed), language)
    .map((item) => row(item.label, item.value, parsed, sourceHints[item.key] || {}));
}

function getUnsupportedMessages(parsed: RuleBacktestParseResponse, language: BacktestLanguage): string[] {
  const details = getUnsupportedDetails(parsed);
  if (details.length > 0) {
    return details.slice(0, 3).map((item) => String(item.message || item.title || (language === 'en' ? 'This setup is not supported yet.' : '当前不支持。')));
  }
  const unsupportedReason = getUnsupportedReason(parsed);
  if (unsupportedReason) {
    return [
      unsupportedReason,
      language === 'en'
        ? 'Add the missing fields or rewrite the setup into a supported deterministic single-instrument rule.'
        : '请补齐关键字段，或改写成当前已支持的确定性单标的规则。',
    ];
  }
  const messages = parsed.ambiguities
    .slice(0, 3)
    .flatMap((item) => { const v = String(item.message || item.suggestion || '').trim(); return v ? [v] : []; });

  if (messages.length > 0) return messages;
  return language === 'en'
    ? ['The current input has not been normalized into an executable deterministic rule yet.', 'Tighten the wording, or switch to a supported single-instrument accumulation or simple rule-based strategy.']
    : ['当前输入还没有被归一化成可执行的确定性规则。', '请收紧表达，或改用当前已支持的单标的区间定投 / 简单条件规则。'];
}

function getParseState(parsed: RuleBacktestParseResponse | null, parseStale: boolean): ParseState {
  if (!parsed) return 'empty';
  if (parseStale) return 'stale';

  const normalizationState = getParsedNormalizationState(parsed);
  if (normalizationState === 'ready') return 'ready';
  if (normalizationState === 'assumed') return 'assumed';
  if (normalizationState === 'unsupported') return 'unsupported';

  const spec = getStrategyPreviewSpec(parsed);
  const strategyType = String(getStrategySpecValue(spec, ['strategy_type']) || parsed.parsedStrategy.strategyKind || '');
  const executable = getParsedExecutable(parsed) || strategyType === 'periodic_accumulation'
    || (strategyType === 'rule_conditions' && hasMeaningfulNode(parsed.parsedStrategy.entry) && hasMeaningfulNode(parsed.parsedStrategy.exit));
  if (!executable) return 'unsupported';

  const unsupportedCodes = new Set(['missing_symbol', 'unknown_operand', 'unparsed_atom', 'missing_exit', 'empty_rule']);
  const hasUnsupportedAmbiguity = parsed.ambiguities.some((item) => unsupportedCodes.has(String(item.code || '')));
  if (hasUnsupportedAmbiguity) return 'unsupported';

  if (parsed.needsConfirmation || parsed.ambiguities.length > 0 || parsed.confidence < 0.9) return 'assumed';
  return 'ready';
}

function getParseStateMeta(parseState: ParseState, language: BacktestLanguage = 'zh'): { tone: 'default' | 'success' | 'warning' | 'danger' | 'info'; label: string; title: string } {
  if (language === 'en') {
    if (parseState === 'ready') return { tone: 'success', label: 'Runnable', title: 'Normalization complete' };
    if (parseState === 'assumed') return { tone: 'warning', label: 'Needs review', title: 'Contains derived defaults' };
    if (parseState === 'unsupported') return { tone: 'danger', label: 'Unsupported', title: 'Not supported yet' };
    if (parseState === 'stale') return { tone: 'warning', label: 'Stale', title: 'Parse result is stale' };
    return { tone: 'info', label: 'Pending parse', title: 'Waiting for parse' };
  }
  if (parseState === 'ready') return { tone: 'success', label: '可运行', title: '已完成归一化' };
  if (parseState === 'assumed') return { tone: 'warning', label: '待确认', title: '含默认假设' };
  if (parseState === 'unsupported') return { tone: 'danger', label: '不支持', title: '当前不支持' };
  if (parseState === 'stale') return { tone: 'warning', label: '已过期', title: '解析结果已过期' };
  return { tone: 'info', label: '待解析', title: '等待解析' };
}

function StrategySpecSummaryCard({
  parsed,
  currentCode,
  startDate,
  endDate,
}: {
  parsed: RuleBacktestParseResponse | null;
  currentCode: string;
  startDate: string;
  endDate: string;
}) {
  const { language } = useI18n();
  const rows = buildConfirmationRows(parsed, currentCode, startDate, endDate, language);
  if (!rows.length) return <div className="product-empty-state product-empty-state--compact">{language === 'en' ? 'No strategy spec is available yet.' : '暂无策略规格。'}</div>;

  return (
    <div className="preview-grid">
      {rows.map((row) => (
        <div key={`${row.label}-${row.value}`} className="preview-card">
          <p className="metric-card__label">{row.label}</p>
          {getFieldSourceLabel(row.source, language) ? (
            <div className="product-chip-list product-chip-list--tight">
              <span className="product-chip">{getFieldSourceLabel(row.source, language)}</span>
            </div>
          ) : null}
          <p className="preview-card__text">{row.value}</p>
        </div>
      ))}
    </div>
  );
}

function getRiskControlRows(parsed: RuleBacktestParseResponse | null): StrategyPreviewRow[] {
  const strategySpec = getStrategyPreviewSpec(parsed);
  const controls = [
    {
      label: '止损',
      value: getStrategySpecValue(strategySpec, ['risk_controls', 'stop_loss_pct']),
    },
    {
      label: '止盈',
      value: getStrategySpecValue(strategySpec, ['risk_controls', 'take_profit_pct']),
    },
    {
      label: '移动止损',
      value: getStrategySpecValue(strategySpec, ['risk_controls', 'trailing_stop_pct']),
    },
  ];

  return controls.reduce<StrategyPreviewRow[]>((acc, item) => {
    if (typeof item.value === 'number' && Number.isFinite(item.value)) {
      acc.push({
        label: item.label,
        value: `${Number(item.value).toFixed(2)}%`,
        numericValue: Number(item.value),
        source: 'explicit',
      });
    }
    return acc;
  }, []);
}

function StrategyParseDetails({
  parsed,
}: {
  parsed: RuleBacktestParseResponse | null;
}) {
  const { language } = useI18n();
  if (!parsed) return <div className="product-empty-state product-empty-state--compact">{language === 'en' ? 'No parse detail is available yet.' : '暂无解析细节。'}</div>;

  const normalizedText = String(parsed.parsedStrategy.normalizedText || '').trim();
  const sourceText = String(parsed.parsedStrategy.sourceText || parsed.strategyText || '').trim();

  return (
    <div className="summary-block">
      <div className="summary-block__header">
        <div>
          <SectionEyebrow>{language === 'en' ? 'Parse detail' : '解析细节'}</SectionEyebrow>
          <h3 className="summary-block__title">{language === 'en' ? 'Source input and normalized expression' : '原始输入与归一化表达'}</h3>
        </div>
      </div>
      <div className="preview-grid">
        <div className="preview-card">
          <p className="metric-card__label">{language === 'en' ? 'Spec source' : '规格来源'}</p>
          <p className="preview-card__text">{getStrategySpecSourceLabel(parsed, language)}</p>
        </div>
        <div className="preview-card">
          <p className="metric-card__label">{language === 'en' ? 'Needs confirmation' : '需要确认'}</p>
          <p className="preview-card__text">{parsed.needsConfirmation ? (language === 'en' ? 'Yes' : '是') : (language === 'en' ? 'No' : '否')}</p>
        </div>
      </div>
      <div className="mt-4">
        <p className="metric-card__label">{language === 'en' ? 'Source input' : '原始输入'}</p>
        <p className="product-section-copy">{sourceText || '--'}</p>
      </div>
      <div className="mt-4">
        <p className="metric-card__label">{language === 'en' ? 'Normalized expression' : '归一化表达'}</p>
        <p className="product-section-copy">{normalizedText || '--'}</p>
      </div>
    </div>
  );
}

function buildAssumptionCards(
  assumptionGroups: Array<Record<string, unknown>>,
  assumptionItems: string[],
  parseWarnings: Array<Record<string, unknown>>,
  ambiguities: Array<Record<string, unknown>>,
  language: BacktestLanguage,
): StrategyPreviewCardGroup[] {
  const cards: StrategyPreviewCardGroup[] = [];

  if (assumptionGroups.length > 0) {
    cards.push(
      ...assumptionGroups.map((group, index) => ({
        label: String(group.label || (language === 'en' ? `Default assumption ${index + 1}` : `默认假设 ${index + 1}`)),
        items: (Array.isArray(group.items) ? group.items : [])
          .flatMap((item) => { const v = formatAssumptionRecord(item as Record<string, unknown>, language); return v ? [v] : []; }),
      })),
    );
  } else if (assumptionItems.length > 0) {
    cards.push({
      label: language === 'en' ? 'Default assumptions' : '默认假设',
      items: assumptionItems,
    });
  }

  const warningItems = [
    ...parseWarnings.slice(0, 4).map((item) => String(item.message || (language === 'en' ? 'Please review this manually.' : '请人工确认。'))),
    ...ambiguities.slice(0, 4).map((item) => String(item.message || item.suggestion || (language === 'en' ? 'Please review this manually.' : '请人工确认。'))),
  ].filter(Boolean);

  if (warningItems.length > 0) {
    cards.push({
      label: language === 'en' ? 'Derived notes and warnings' : '推断与提醒',
      items: warningItems,
    });
  }

  return cards.filter((card) => card.items.length > 0);
}

export type FlowProps = {
  code: string;
  onCodeChange: (value: string) => void;
  onCodeEnter: (event: React.KeyboardEvent<HTMLInputElement>) => void;
  strategyText: string;
  onStrategyTextChange: (value: string) => void;
  startDate: string;
  onStartDateChange: (value: string) => void;
  endDate: string;
  onEndDateChange: (value: string) => void;
  initialCapital: string;
  onInitialCapitalChange: (value: string) => void;
  lookbackBars: string;
  onLookbackBarsChange: (value: string) => void;
  feeBps: string;
  onFeeBpsChange: (value: string) => void;
  slippageBps: string;
  onSlippageBpsChange: (value: string) => void;
  benchmarkMode: RuleBenchmarkMode;
  onBenchmarkModeChange: (value: RuleBenchmarkMode) => void;
  benchmarkCode: string;
  onBenchmarkCodeChange: (value: string) => void;
  parsedStrategy: RuleBacktestParseResponse | null;
  confirmed: boolean;
  onToggleConfirmed: (value: boolean) => void;
  isParsing: boolean;
  parseError: ParsedApiError | null;
  onParse: () => Promise<void>;
  isSubmitting: boolean;
  runError: ParsedApiError | null;
  onRun: () => Promise<void>;
  onReset: () => void;
  historyItems: RuleBacktestHistoryItem[];
  historyTotal: number;
  historyPage: number;
  selectedRunId: number | null;
  isLoadingHistory: boolean;
  historyError: ParsedApiError | null;
  onRefreshHistory: () => void;
  onOpenHistoryRun: (run: RuleBacktestHistoryItem) => void;
  previewAssumptions: AssumptionMap;
  currentStep: RuleWizardStep;
  onStepChange: (step: RuleWizardStep) => void;
  parseStale: boolean;
  onApplyRewriteSuggestion: (value: string) => void;
  appliedRewriteText: string | null;
  panelMode: 'normal' | 'professional';
};

const DeterministicBacktestFlow: React.FC<FlowProps> = ({
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
  previewAssumptions,
  currentStep,
  onStepChange,
  parseStale,
  onApplyRewriteSuggestion,
  appliedRewriteText,
  panelMode,
}) => {
  const { language } = useI18n();
  const parseState = getParseState(parsedStrategy, parseStale);
  const parseMeta = getParseStateMeta(parseState, language);
  const strategySpec = getStrategyPreviewSpec(parsedStrategy);
  const riskControlRows = getRiskControlRows(parsedStrategy);
  const strongestRiskControl = riskControlRows.reduce((max, row) => Math.max(max, Number(row.numericValue || 0)), 0);
  const assumptionGroups = getParsedAssumptionGroups(parsedStrategy);
  const coreIntentSummary = getCoreIntentSummary(parsedStrategy);
  const supportedPortionSummary = getSupportedPortionSummary(parsedStrategy);
  const unsupportedExtensions = getUnsupportedExtensions(parsedStrategy);
  const rewriteSuggestions = getRewriteSuggestions(parsedStrategy);
  const parseWarnings = getParseWarnings(parsedStrategy);
  const assumptionItems = getParsedAssumptionRecords(parsedStrategy).length > 0
    ? getParsedAssumptionRecords(parsedStrategy).map((item) => formatAssumptionRecord(item, language))
    : (
      String(getStrategySpecValue(strategySpec, ['strategy_type']) || parsedStrategy?.parsedStrategy.strategyKind || '') === 'periodic_accumulation'
        ? buildPeriodicAssumptionLabels(strategySpec, language)
        : []
    );
  const assumptionCards = buildAssumptionCards(
    assumptionGroups,
    assumptionItems,
    parseWarnings,
    parsedStrategy?.ambiguities || [],
    language,
  );
  const canProceedFromBaseParams = Boolean(
    startDate
    && endDate
    && initialCapital
    && startDate <= endDate
    && (benchmarkMode !== 'custom_code' || benchmarkCode.trim()),
  );
  const canProceedFromConfirm = (parseState === 'ready' || parseState === 'assumed') && confirmed && !parseStale;
  const [presets, setPresets] = useState<RuleBacktestPreset[]>(() => loadRuleBacktestPresets());

  const handleApplyPreset = (preset: RuleBacktestPreset) => {
    onCodeChange(preset.code);
    onStrategyTextChange(preset.strategyText);
    onStartDateChange(preset.startDate);
    onEndDateChange(preset.endDate);
    onLookbackBarsChange(preset.lookbackBars);
    onInitialCapitalChange(preset.initialCapital);
    onFeeBpsChange(preset.feeBps);
    onSlippageBpsChange(preset.slippageBps);
    onBenchmarkModeChange((preset.benchmarkMode as RuleBenchmarkMode) || 'auto');
    onBenchmarkCodeChange(preset.benchmarkCode);
    onToggleConfirmed(false);
    onStepChange('symbol');
  };

  const handleDeletePreset = (presetId: string) => {
    setPresets(deleteRuleBacktestPreset(presetId));
  };

  const compactInputClass = 'w-full min-w-0 min-h-[44px] rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2.5 text-sm leading-6 text-white outline-none transition-all focus:border-emerald-500/50 focus:bg-white/[0.05]';
  const compactCheckboxClass = 'size-4 shrink-0 rounded border border-white/15 bg-white/[0.03] text-emerald-400 accent-emerald-400 disabled:opacity-45';
  const compactFieldLabelClass = 'mb-2 text-[10px] font-bold uppercase tracking-widest text-white/40';
  const denseCardClass = 'h-full bg-white/[0.02] border border-white/5 rounded-[24px] p-6 flex flex-col gap-5';
  const subCardClass = 'rounded-[24px] border border-white/5 bg-white/[0.02] p-6';
  const stickyStatusTitle = language === 'en'
    ? `Ready: ${code || 'Pending symbol'} ${parsedStrategy ? `· ${getLocalizedStrategyTypeLabel(parsedStrategy, language)}` : ''}`
    : `就绪: ${code || '--'} ${parsedStrategy ? getLocalizedStrategyTypeLabel(parsedStrategy, language) : '待解析策略'}`;
  const stickyStatusNote = isSubmitting
    ? (language === 'en' ? 'Submitting deterministic backtest and opening the dedicated result page.' : '正在提交确定性回测，并打开独立结果页。')
    : parseStale
      ? (language === 'en' ? 'Inputs changed. Parse again before launch.' : '输入已变更，启动前需要重新解析。')
      : (language === 'en' ? 'The result page still owns KPI, chart, audit, and trade inspection.' : '结果页仍然承载 KPI、图表、审计与交易明细。');

  const executionSettingsFields = (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <label className="product-field gap-1.5">
        <span className={compactFieldLabelClass}>{language === 'en' ? 'Lookback window' : '回看范围'}</span>
        <input
          type="number"
          className={compactInputClass}
          min={10}
          max={5000}
          value={lookbackBars}
          onChange={(event) => onLookbackBarsChange(event.target.value)}
          onFocus={() => onStepChange('confirm')}
          aria-label={language === 'en' ? 'Lookback window' : '回看范围'}
        />
      </label>
      <label className="product-field gap-1.5">
        <span className={compactFieldLabelClass}>{language === 'en' ? 'Fees (bp)' : '手续费 (bp)'}</span>
        <input
          type="number"
          className={compactInputClass}
          min={0}
          max={500}
          value={feeBps}
          onChange={(event) => onFeeBpsChange(event.target.value)}
          onFocus={() => onStepChange('confirm')}
          aria-label={language === 'en' ? 'Fee per side (bp)' : '单边手续费 (bp)'}
        />
      </label>
      <label className="product-field gap-1.5">
        <span className={compactFieldLabelClass}>{language === 'en' ? 'Slippage (bp)' : '滑点 (bp)'}</span>
        <input
          type="number"
          className={compactInputClass}
          min={0}
          max={500}
          value={slippageBps}
          onChange={(event) => onSlippageBpsChange(event.target.value)}
          onFocus={() => onStepChange('confirm')}
          aria-label={language === 'en' ? 'Slippage per side (bp)' : '单边滑点 (bp)'}
        />
      </label>
    </div>
  );

  const baseParamsSection = (
    <section
      id="backtest-control-section-symbol"
      className="min-w-0 xl:col-span-5"
      data-testid="backtest-control-section-symbol"
      data-active={currentStep === 'symbol' ? 'true' : 'false'}
    >
      <div className={denseCardClass}>
        <div className="flex items-start gap-3">
          <span className="mt-1 h-3 w-1 rounded-full bg-indigo-400" />
          <div>
            <h3 className="text-sm font-bold text-white">{language === 'en' ? 'Instrument and date window' : '基础标的与区间'}</h3>
            <p className="mt-1 text-sm text-white/45">{language === 'en' ? 'Keep the symbol and date window visible at a glance.' : '标的与时间窗口保持常驻可见，不再折叠切换。'}</p>
          </div>
        </div>
        <div className="backtest-base-params-layout grid grid-cols-1 gap-6 xl:grid-cols-4" data-testid="backtest-base-params-layout">
          <label className="product-field min-w-0 gap-1.5">
            <span className={compactFieldLabelClass}>{language === 'en' ? 'Ticker' : '标的代码'}</span>
            <input
              type="text"
              className={compactInputClass}
              value={code}
              onChange={(event) => onCodeChange(event.target.value.toUpperCase())}
              onFocus={() => onStepChange('symbol')}
              onKeyDown={onCodeEnter}
              placeholder={language === 'en' ? 'For example ORCL / AAPL / 600519' : '例如 ORCL / AAPL / 600519'}
              aria-label={language === 'en' ? 'Ticker' : '股票代码'}
            />
          </label>
          <div className="min-w-0">
            <label className="product-field min-w-0 gap-1.5">
              <span className={compactFieldLabelClass}>{language === 'en' ? 'Benchmark' : '对比基准'}</span>
              <select
                className={`${compactInputClass} appearance-none pr-10 truncate`}
                value={benchmarkMode}
                onChange={(event) => onBenchmarkModeChange(event.target.value as RuleBenchmarkMode)}
                onFocus={() => onStepChange('symbol')}
                aria-label={language === 'en' ? 'Benchmark' : '对比基准'}
              >
                {RULE_BENCHMARK_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {getBenchmarkModeLabel(option.value, code, benchmarkCode, language)}
                  </option>
                ))}
              </select>
            </label>
            {benchmarkMode === 'custom_code' ? (
              <label className="product-field mt-4 min-w-0 gap-1.5">
                <span className={compactFieldLabelClass}>{language === 'en' ? 'Custom benchmark code' : '自定义基准代码'}</span>
                <input
                  type="text"
                  className={compactInputClass}
                  value={benchmarkCode}
                  onChange={(event) => onBenchmarkCodeChange(event.target.value.toUpperCase())}
                  onFocus={() => onStepChange('symbol')}
                  placeholder={language === 'en' ? 'For example QQQ / SPY / ^NDX / 000300' : '例如 QQQ / SPY / ^NDX / 000300'}
                  aria-label={language === 'en' ? 'Custom benchmark code' : '自定义基准代码'}
                />
              </label>
            ) : null}
          </div>
          <div className="backtest-date-range-grid grid grid-cols-1 gap-4" data-testid="backtest-base-date-range">
            <label className="product-field gap-1.5">
              <span className={compactFieldLabelClass}>{language === 'en' ? 'Start date' : '开始日期'}</span>
              <input
                type="date"
                className={compactInputClass}
                value={startDate}
                onChange={(event) => onStartDateChange(event.target.value)}
                onFocus={() => onStepChange('symbol')}
                aria-label={language === 'en' ? 'Start date' : '开始日期'}
              />
            </label>
            <label className="product-field gap-1.5">
              <span className={compactFieldLabelClass}>{language === 'en' ? 'End date' : '结束日期'}</span>
              <input
                type="date"
                className={compactInputClass}
                value={endDate}
                onChange={(event) => onEndDateChange(event.target.value)}
                onFocus={() => onStepChange('symbol')}
                aria-label={language === 'en' ? 'End date' : '结束日期'}
              />
            </label>
          </div>
          <label className="product-field min-w-0 gap-1.5">
            <span className={compactFieldLabelClass}>{language === 'en' ? 'Initial capital' : '初始资金'}</span>
            <input
              type="number"
              className={compactInputClass}
              min={1}
              value={initialCapital}
              onChange={(event) => onInitialCapitalChange(event.target.value)}
              onFocus={() => onStepChange('symbol')}
              aria-label={language === 'en' ? 'Initial capital' : '初始资金'}
            />
          </label>
        </div>
        <div className="product-chip-list">
          <span className="product-chip">{language === 'en' ? 'Instrument' : '当前标的'}: {code || '--'}</span>
          <span className="product-chip">{language === 'en' ? 'Benchmark' : '当前基准'}: {getBenchmarkModeLabel(benchmarkMode, code, benchmarkCode, language)}</span>
        </div>
      </div>
    </section>
  );

  const strategyInputSection = (
    <section
      id="backtest-control-section-setup"
      className="min-w-0 xl:col-span-3"
      data-testid="backtest-control-section-setup"
      data-active={currentStep === 'setup' ? 'true' : 'false'}
    >
      <div className={denseCardClass}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex items-start gap-3">
            <span className="mt-1 h-3 w-1 rounded-full bg-rose-500" />
            <div>
              <h3 className="text-sm font-bold text-white">{language === 'en' ? 'Strategy engine and rule input' : '策略引擎与规则'}</h3>
              <p className="mt-1 text-sm text-white/45">{language === 'en' ? 'Write or rewrite the rule in natural language, then normalize it without leaving the board.' : '自然语言策略、改写建议、解析动作都在同一块工作区内完成。'}</p>
            </div>
          </div>
          <Button
            variant="secondary"
            onClick={() => void onParse()}
            isLoading={isParsing}
            loadingText={language === 'en' ? 'Parsing…' : '解析中…'}
            disabled={!canProceedFromBaseParams || !strategyText.trim()}
          >
            {appliedRewriteText ? (language === 'en' ? 'Parse again' : '重新解析') : (language === 'en' ? 'Parse strategy' : '解析策略')}
          </Button>
        </div>
        <label className="product-field product-field--full gap-1.5">
          <span className={compactFieldLabelClass}>{language === 'en' ? 'Natural-language strategy' : '自然语言策略'}</span>
          <LazyMotion features={domAnimation}>
            <AnimatePresence initial={false}>
              {appliedRewriteText ? (
                <m.div
                  key="rewrite-banner"
                  className="mb-4"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={FLOW_PANEL_TRANSITION}
                >
                  <Banner
                    tone="info"
                    title={language === 'en' ? 'Applied rewrite suggestion' : '已应用建议改写'}
                    body={language === 'en' ? 'The strategy text has been replaced with the suggested version. Parse it again before continuing.' : '策略文本已替换为建议版本。请重新解析后继续。'}
                  />
                </m.div>
              ) : null}
            </AnimatePresence>
          </LazyMotion>
          <textarea
            aria-label={language === 'en' ? 'Strategy text' : '策略文本'}
            value={strategyText}
            onChange={(event) => onStrategyTextChange(event.target.value)}
            onFocus={() => onStepChange('setup')}
            rows={8}
            className={`${compactInputClass} min-h-[220px] py-3 product-command-input--textarea`}
            placeholder={language === 'en' ? 'For example: Start with 100000, buy 100 shares of ORCL every trading day from 2025-01-01 to 2025-12-31, and stop when cash runs out' : '例如：资金100000，从2025-01-01到2025-12-31，每天买100股ORCL，买到资金耗尽为止'}
          />
        </label>
        <div className="product-chip-list wizard-example-chips">
          {STRATEGY_EXAMPLES[language].map((example) => (
            <button
              key={example}
              type="button"
              className="product-chip product-chip--button"
              onClick={() => {
                onStepChange('setup');
                onStrategyTextChange(example);
              }}
            >
              {example}
            </button>
          ))}
        </div>
        {parseError ? <ApiErrorAlert error={parseError} /> : null}
      </div>
    </section>
  );

  const executionSettingsSection = (
    <section
      id="backtest-control-section-confirm"
      className="min-w-0 xl:col-span-2"
      data-testid="backtest-control-section-confirm"
      data-active={currentStep === 'confirm' ? 'true' : 'false'}
    >
      <div className={denseCardClass}>
        <div className="flex items-start gap-3">
          <span className="mt-1 h-3 w-1 rounded-full bg-indigo-500" />
          <div>
            <h3 className="text-sm font-bold text-white">{language === 'en' ? 'Capital and execution settings' : '资金与执行设置'}</h3>
            <p className="mt-1 text-sm text-white/45">{language === 'en' ? 'Keep benchmark, fees, slippage, and execution defaults in the same card.' : '资金、基准、滑点和执行默认值在同一卡片内连续校对。'}</p>
          </div>
        </div>
        {executionSettingsFields}
        <div className={subCardClass}>
          <p className={compactFieldLabelClass}>{language === 'en' ? 'Execution defaults' : '执行默认值'}</p>
          <div className="mt-3">
            <AssumptionList assumptions={previewAssumptions} emptyText={language === 'en' ? 'No execution defaults are available yet.' : '暂无执行默认值。'} />
          </div>
        </div>
      </div>
    </section>
  );

  const parsedStrategySection = (
    <section
      id="backtest-control-section-strategy"
      className="min-w-0 xl:col-span-3"
      data-testid="backtest-control-section-strategy"
      data-active={currentStep === 'strategy' ? 'true' : 'false'}
    >
      <div className={denseCardClass}>
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <span className="mt-1 h-3 w-1 rounded-full bg-amber-400" />
            <div>
              <h3 className="text-sm font-bold text-white">{language === 'en' ? 'Parse review and executable spec' : '解析确认与可执行规格'}</h3>
              <p className="mt-1 text-sm text-white/45">{language === 'en' ? 'Review the normalized rule inline, without collapsing into a separate step.' : '解析状态、可执行规格、默认假设与限制说明全部平铺展开。'}</p>
            </div>
          </div>
          <Badge variant={parseMeta.tone === 'success' ? 'success' : parseMeta.tone === 'danger' ? 'danger' : parseMeta.tone === 'warning' ? 'warning' : 'default'}>
            {parseMeta.label}
          </Badge>
        </div>
        {parseState === 'empty' ? (
          <div className="product-empty-state product-empty-state--compact">
            {language === 'en' ? 'Parse the strategy first, then review the normalized rule and execution defaults.' : '先完成策略解析，再继续确认归一化结果和默认假设。'}
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <div className="summary-block" data-testid="confirm-status-section">
              <div className="summary-block__header">
                <div>
                  <SectionEyebrow>{language === 'en' ? 'Parse status' : '解析状态'}</SectionEyebrow>
                  <h3 className="summary-block__title">{language === 'en' ? 'Review the current parse' : '确认当前解析'}</h3>
                </div>
              </div>
              <Banner
                tone={parseMeta.tone}
                title={parseMeta.title}
                body={
                  parseState === 'unsupported'
                    ? getUnsupportedMessages(parsedStrategy as RuleBacktestParseResponse, language)[0]
                    : parseState === 'stale'
                      ? (language === 'en' ? 'The inputs changed. Parse again before continuing.' : '输入已变更。请重新解析后再继续。')
                      : parseState === 'assumed'
                        ? (language === 'en' ? 'The strategy is executable, but it still contains derived defaults or execution assumptions.' : '策略可执行，但包含默认值或执行假设。')
                        : (language === 'en' ? 'The strategy is normalized and ready to continue into the dedicated result page.' : '策略已归一化，可直接进入独立结果页流转。')
                }
              />
            </div>

            <div className="summary-block" data-testid="confirm-compact-summary-section">
              <div className="preview-grid">
                <div className="preview-card">
                  <p className="metric-card__label">{language === 'en' ? 'Strategy type' : '策略类型'}</p>
                  <p className="preview-card__text">{getLocalizedStrategyTypeLabel(parsedStrategy, language)}</p>
                </div>
                <div className="preview-card">
                  <p className="metric-card__label">{language === 'en' ? 'Ticker' : '标的'}</p>
                  <p className="preview-card__text">{code || '--'}</p>
                </div>
                <div className="preview-card">
                  <p className="metric-card__label">{language === 'en' ? 'Date range' : '区间'}</p>
                  <p className="preview-card__text">{startDate || '--'} {'->'} {endDate || '--'}</p>
                </div>
                <div className="preview-card">
                  <p className="metric-card__label">{language === 'en' ? 'Core intent' : '核心意图'}</p>
                  <p className="preview-card__text">{coreIntentSummary || supportedPortionSummary || (language === 'en' ? 'Needs review' : '待确认')}</p>
                </div>
              </div>
            </div>

            {riskControlRows.length ? (
              <div className="summary-block" data-testid="confirm-additive-dashboard">
                <div className="summary-block" data-testid="confirm-dashboard-risk-controls" title="查看确认页风险控制 additive 摘要">
                  <div className="summary-block__header">
                    <div>
                      <SectionEyebrow>Dashboard</SectionEyebrow>
                      <h3 className="summary-block__title">风险控制卡片 / Risk Controls</h3>
                    </div>
                    <div className="product-chip-list product-chip-list--tight">
                      <span className="product-chip">已启用 {riskControlRows.length} 项</span>
                      <span className="product-chip">最高阈值 {strongestRiskControl.toFixed(2)}%</span>
                    </div>
                  </div>
                  <div className="preview-grid">
                    {riskControlRows.map((row) => (
                      <div key={`confirm-dashboard-risk-${row.label}`} className="preview-card">
                        <p className="metric-card__label">{row.label}</p>
                        <p className="preview-card__text">{row.value}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : null}

            <div className="summary-block" data-testid="confirm-executable-spec-section">
              <div className="summary-block__header">
                <div>
                  <SectionEyebrow>{language === 'en' ? 'Executable spec' : '可执行规格'}</SectionEyebrow>
                  <h3 className="summary-block__title">{language === 'en' ? 'What will actually run' : '实际执行内容'}</h3>
                </div>
              </div>
              <p className="product-section-copy">
                {language === 'en' ? <>The fields below come from the current canonical <code>strategy_spec</code> and directly drive the deterministic backtest.</> : <>以下字段来自当前 canonical <code>strategy_spec</code>，会直接驱动确定性回测执行。</>}
              </p>
              <div className="product-chip-list mb-4">
                <span className="product-chip">{language === 'en' ? 'Strategy family' : '策略族'} · {getLocalizedStrategyTypeLabel(parsedStrategy, language)}</span>
                <span className="product-chip">{language === 'en' ? 'Spec source' : '规格来源'} · {getStrategySpecSourceLabel(parsedStrategy, language)}</span>
                <span className="product-chip">{language === 'en' ? 'Normalization' : '归一化'} · {formatRuleNormalizationStateLabel(getParsedNormalizationState(parsedStrategy), language)}</span>
                <span className="product-chip">{language === 'en' ? 'Needs confirmation' : '需要确认'} · {parsedStrategy?.needsConfirmation ? (language === 'en' ? 'Yes' : '是') : (language === 'en' ? 'No' : '否')}</span>
                <span className="product-chip">{language === 'en' ? 'Executable' : '可执行'} · {getParsedExecutable(parsedStrategy) ? (language === 'en' ? 'Yes' : '是') : (language === 'en' ? 'No' : '否')}</span>
              </div>
              <div className="product-chip-list product-chip-list--tight mb-4">
                <span className="product-chip">{language === 'en' ? 'Explicit spec' : '显式结构化'}</span>
                <span className="product-chip">{language === 'en' ? 'Derived / defaulted' : '默认/推断'}</span>
                <span className="product-chip">{language === 'en' ? 'Compat setup' : '兼容 setup'}</span>
              </div>
              <StrategySpecSummaryCard parsed={parsedStrategy} currentCode={code} startDate={startDate} endDate={endDate} />
              {riskControlRows.length ? (
                <div className="summary-block mt-4">
                  <div className="summary-block__header">
                    <div>
                      <SectionEyebrow>风险控制</SectionEyebrow>
                      <h3 className="summary-block__title">风险控制 / Risk Controls</h3>
                    </div>
                  </div>
                  <div className="preview-grid">
                    {riskControlRows.map((row) => (
                      <div key={`${row.label}-${row.value}`} className="preview-card">
                        <p className="metric-card__label">{row.label}</p>
                        <div className="product-chip-list product-chip-list--tight">
                          <span className="product-chip">{getFieldSourceLabel(row.source)}</span>
                        </div>
                        <p className="preview-card__text">{row.value}</p>
                      </div>
                    ))}
                  </div>
                  <div className="summary-block mt-4" data-testid="confirm-risk-controls-visualization">
                    <div className="summary-block__header">
                      <div>
                        <SectionEyebrow>保护摘要</SectionEyebrow>
                        <h3 className="summary-block__title">保护梯度 / Protection Ladder</h3>
                      </div>
                      <div className="product-chip-list product-chip-list--tight">
                        <span className="product-chip">已启用 {riskControlRows.length} 项</span>
                        <span className="product-chip">最高阈值 {strongestRiskControl.toFixed(2)}%</span>
                      </div>
                    </div>
                    <div className="space-y-3">
                      {riskControlRows.map((row) => {
                        const width = strongestRiskControl > 0 && row.numericValue
                          ? Math.max(16, (row.numericValue / strongestRiskControl) * 100)
                          : 0;
                        return (
                          <div key={`risk-ladder-${row.label}`} className="space-y-1.5">
                            <div className="flex items-center justify-between gap-3">
                              <span className="metric-card__label">{row.label}</span>
                              <span className="preview-card__text">{row.value}</span>
                            </div>
                            <div className="h-1.5 overflow-hidden rounded-full bg-[rgba(255,255,255,0.08)]">
                              <div
                                className="h-full rounded-full bg-[var(--backtest-accent,#7dd3fc)]"
                                style={{ width: `${width}%` }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              ) : null}
            </div>

            <StrategyParseDetails parsed={parsedStrategy} />

            {(supportedPortionSummary || unsupportedExtensions.length > 0 || rewriteSuggestions.length > 0) && (
              <div className="summary-block" data-testid="confirm-guidance-section">
                <div className="summary-block__header">
                  <div>
                    <SectionEyebrow>{language === 'en' ? 'Limits and rewrites' : '限制与改写'}</SectionEyebrow>
                    <h3 className="summary-block__title">{language === 'en' ? 'Rewrite suggestions and limits' : '改写建议与限制'}</h3>
                  </div>
                </div>
                {supportedPortionSummary && supportedPortionSummary !== coreIntentSummary ? (
                  <p className="product-section-copy">{supportedPortionSummary}</p>
                ) : null}
                {unsupportedExtensions.length > 0 ? (
                  <div className="product-chip-list mb-4">
                    {unsupportedExtensions.slice(0, 3).map((item, index) => (
                      <span key={`${String(item.code || index)}-unsupported`} className="product-chip">
                        {String(item.title || item.message || (language === 'en' ? 'Not supported yet' : '当前不支持'))}
                      </span>
                    ))}
                  </div>
                ) : null}
                {rewriteSuggestions.length > 0 ? (
                  <div className="product-chip-list wizard-example-chips">
                    {rewriteSuggestions.slice(0, 3).map((item, index) => {
                      const text = String(item.strategyText || '');
                      const label = String(item.label || text || (language === 'en' ? `Suggestion ${index + 1}` : `建议 ${index + 1}`));
                      if (!text) return null;
                      return (
                        <button
                          key={`${label}-${index}`}
                          type="button"
                          className="product-chip product-chip--button"
                          onClick={() => onApplyRewriteSuggestion(text)}
                        >
                          {label}: {text}
                        </button>
                      );
                    })}
                  </div>
                ) : null}
              </div>
            )}

            {assumptionCards.length > 0 ? (
              <div className="summary-block" data-testid="confirm-assumptions-section">
                <div className="summary-block__header">
                  <div>
                    <SectionEyebrow>{language === 'en' ? 'Defaults and assumptions' : '默认与推断'}</SectionEyebrow>
                    <h3 className="summary-block__title">{language === 'en' ? 'Defaults and review notes' : '默认补全与提醒'}</h3>
                  </div>
                </div>
                <p className="product-section-copy">{language === 'en' ? 'These are not explicit canonical execution fields from the user. They are system-filled defaults, derived values, or items that still need manual review.' : '这些内容不是用户显式写出的 canonical 执行字段，而是系统补全、默认或需要人工确认的部分。'}</p>
                <div className="preview-grid">
                  {assumptionCards.map((group, index) => (
                    <div key={`${group.label}-${index}`} className="preview-card">
                      <p className="metric-card__label">{group.label}</p>
                      <div className="product-chip-list">
                        {group.items.map((item, itemIndex) => (
                          <span key={`${group.label}-${itemIndex}`} className="product-chip">{item}</span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            <label className="product-checkbox-row mt-1">
              <input
                type="checkbox"
                aria-label={language === 'en' ? 'Confirm strategy parse result' : '确认策略解析结果'}
                className={compactCheckboxClass}
                checked={confirmed}
                disabled={parseState === 'unsupported' || parseState === 'stale'}
                onChange={(event) => {
                  onStepChange('strategy');
                  onToggleConfirmed(event.target.checked);
                }}
              />
              <span>{language === 'en' ? 'I reviewed the current parse result and execution assumptions.' : '我已确认当前解析结果与执行假设。'}</span>
            </label>
          </div>
        )}
      </div>
    </section>
  );

  const runControlsSection = (
    <section
      id="backtest-control-section-run"
      className="min-w-0 xl:col-span-2"
      data-testid="backtest-control-section-run"
      data-active={currentStep === 'run' ? 'true' : 'false'}
    >
      <div className={denseCardClass}>
        <div className="flex items-start gap-3">
          <span className="mt-1 h-3 w-1 rounded-full bg-cyan-400" />
          <div>
            <h3 className="text-sm font-bold text-white">{language === 'en' ? 'Launch rail and history handoff' : '发射协议与历史接力'}</h3>
            <p className="mt-1 text-sm text-white/45">{language === 'en' ? 'The config page only launches runs. Full inspection still lives on the dedicated result route.' : '配置页只负责发起运行，完整分析仍在独立结果页完成。'}</p>
          </div>
        </div>
        <output className="backtest-inline-status" aria-live="polite">
          <span className="backtest-inline-status__pill" data-tone={parseMeta.tone}>{language === 'en' ? 'Parse' : '解析'} · {parseMeta.label}</span>
          <span className="backtest-inline-status__pill" data-tone="info">{language === 'en' ? 'History' : '历史'} · {historyTotal}</span>
          {parseStale ? <span className="backtest-inline-status__pill" data-tone="warning">{language === 'en' ? 'Preview is stale' : '预览已过期'}</span> : null}
          {appliedRewriteText ? <span className="backtest-inline-status__pill" data-tone="info">{language === 'en' ? 'Rewrite applied' : '已应用改写'}</span> : null}
        </output>
        <div className="preview-grid">
          <div className="preview-card">
            <p className="metric-card__label">{language === 'en' ? 'Ticker' : '标的'}</p>
            <p className="preview-card__text">{code || '--'}</p>
          </div>
          <div className="preview-card">
            <p className="metric-card__label">{language === 'en' ? 'Date range' : '区间'}</p>
            <p className="preview-card__text">{startDate || '--'} {'->'} {endDate || '--'}</p>
          </div>
          <div className="preview-card">
            <p className="metric-card__label">{language === 'en' ? 'Initial capital' : '初始资金'}</p>
            <p className="preview-card__text">{initialCapital || '--'}</p>
          </div>
          <div className="preview-card">
            <p className="metric-card__label">{language === 'en' ? 'Benchmark' : '基准'}</p>
            <p className="preview-card__text">{getBenchmarkModeLabel(benchmarkMode, code, benchmarkCode, language)}</p>
          </div>
        </div>
        <div className="product-action-row">
          <Button variant="ghost" onClick={onReset}>{language === 'en' ? 'Reset' : '重置'}</Button>
          <Button variant="ghost" onClick={onRefreshHistory} disabled={isLoadingHistory}>
            {isLoadingHistory ? (language === 'en' ? 'Refreshing…' : '刷新中…') : (language === 'en' ? 'Refresh history' : '刷新历史')}
          </Button>
        </div>
      </div>
    </section>
  );


  const isEmptyHistory = historyItems.length === 0 && !isLoadingHistory && !historyError;
  const visiblePresets = presets.slice(0, 3);
  const visibleHistoryItems = historyItems.slice(0, 3);

  const renderPresetQuickList = () => (
    <div className="bg-white/[0.02] border border-white/5 rounded-[24px] p-6" data-testid="backtest-setup-presets">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <h3 className="text-xs font-bold text-white/40 uppercase tracking-[0.22em]">{language === 'en' ? 'Preset shortcuts' : '快速预设'}</h3>
          <p className="mt-2 text-sm text-white/50 leading-relaxed">
            {language === 'en' ? 'Apply a saved setup and continue editing in the launch panel.' : '直接复用最近预设，再在右侧发射台继续微调参数。'}
          </p>
        </div>
        <span className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-white/45">{presets.length}</span>
      </div>
      {visiblePresets.length === 0 ? (
        <div className="rounded-[24px] border border-dashed border-white/10 bg-white/[0.03] p-4 text-sm text-white/45">
          {language === 'en' ? 'No saved presets yet. Recent drafts will appear here after your first run.' : '当前还没有保存的预设。完成一次回测后，最近草稿会显示在这里。'}
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {visiblePresets.map((preset) => (
            <div key={preset.id} className="rounded-2xl border border-white/8 bg-white/[0.02] p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-white/35">
                    {preset.kind === 'saved' ? (language === 'en' ? 'Saved preset' : '已保存预设') : (language === 'en' ? 'Recent draft' : '最近草稿')}
                  </p>
                  <div className="mt-2 text-sm font-medium text-white">{language === 'en' && containsCjk(preset.name) ? preset.code : preset.name}</div>
                  <div className="mt-1 text-xs text-white/35">{preset.startDate || '--'} {'->'} {preset.endDate || '--'}</div>
                </div>
                <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[11px] text-white/55">{preset.code}</span>
              </div>
              <div className="product-action-row mt-4">
                <Button size="sm" variant="secondary" onClick={() => handleApplyPreset(preset)}>{language === 'en' ? 'Apply' : '应用'}</Button>
                {preset.kind === 'saved' ? (
                  <Button size="sm" variant="ghost" onClick={() => handleDeletePreset(preset.id)}>{language === 'en' ? 'Delete' : '删除'}</Button>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  const renderHistoryQuickList = () => (
    <div className="bg-white/[0.02] border border-white/5 rounded-[24px] p-6" data-testid="backtest-setup-history">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <h3 className="text-xs font-bold text-white/40 uppercase tracking-[0.22em]">{language === 'en' ? 'Recent history' : '最近历史回测'}</h3>
          <p className="mt-2 text-sm text-white/50 leading-relaxed">
            {language === 'en' ? 'Reopen the latest result pages directly from here.' : '最近完成的回测可以从这里直接重开独立结果页。'}
          </p>
        </div>
        <Button size="sm" variant="ghost" onClick={onRefreshHistory} disabled={isLoadingHistory}>
          {isLoadingHistory ? (language === 'en' ? 'Refreshing…' : '刷新中…') : (language === 'en' ? 'Refresh' : '刷新')}
        </Button>
      </div>
      {historyError ? <ApiErrorAlert error={historyError} className="mb-4" /> : null}
      {visibleHistoryItems.length === 0 ? (
        <div className="rounded-[24px] border border-dashed border-white/10 bg-white/[0.03] p-4 text-sm text-white/45">
          {isEmptyHistory
            ? (language === 'en' ? 'No saved rule-backtest runs yet. Your first completed run will appear here.' : '当前还没有已保存的规则回测记录。完成第一次回测后，最近历史会显示在这里。')
            : (language === 'en' ? 'History is loading or temporarily unavailable.' : '历史记录正在加载，或暂时不可用。')}
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {visibleHistoryItems.map((item) => (
            <div key={item.id} className={`rounded-2xl border bg-white/[0.02] p-4 ${selectedRunId === item.id ? 'border-indigo-400/40' : 'border-white/8'}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm font-medium text-white">{item.code || '--'} / {language === 'en' ? 'Rule backtest' : '规则回测'}</div>
                  <div className="mt-1 text-xs text-white/35">{item.runAt?.slice(0, 10) || '--'} {'->'} {item.completedAt?.slice(0, 10) || item.runAt?.slice(0, 10) || '--'}</div>
                  <div className="mt-2 text-xs text-white/45">{language === 'en' ? 'Status' : '状态'}: {item.status || '--'}</div>
                </div>
                <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[11px] text-white/55">#{item.id}</span>
              </div>
              <div className="product-action-row mt-4">
                <Button size="sm" variant="secondary" onClick={() => onOpenHistoryRun(item)}>
                  {language === 'en' ? 'Open' : '查看'}
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
      <p className="mt-4 text-xs text-white/35">
        {language === 'en' ? `${historyTotal} deterministic runs in history. Page ${historyPage}.` : `历史中共 ${historyTotal} 条确定性回测记录。当前页 ${historyPage}。`}
      </p>
    </div>
  );

  const renderSetupSidebar = () => (
    <aside className="w-full min-w-0 shrink-0 flex flex-col gap-6" data-testid="backtest-cockpit-console">
      <div className="bg-white/[0.02] border border-white/5 rounded-[24px] p-6" data-testid="backtest-entry-shell">
        <SectionEyebrow>{language === 'en' ? 'Deterministic lane' : '确定性链路'}</SectionEyebrow>
        <div className="mt-4 grid gap-3">
          <div className={subCardClass}>
            <p className={compactFieldLabelClass}>{language === 'en' ? 'Flow' : '流程'}</p>
            <p className="mt-2 text-sm text-white">{language === 'en' ? 'Setup -> Compile -> Execute' : '配置 -> 编译 -> 执行'}</p>
          </div>
          <div className={subCardClass}>
            <p className={compactFieldLabelClass}>{language === 'en' ? 'Current symbol' : '当前标的'}</p>
            <p className="mt-2 text-sm text-white">{code || '--'}</p>
          </div>
          <div className={subCardClass}>
            <p className={compactFieldLabelClass}>{language === 'en' ? 'Window' : '区间'}</p>
            <p className="mt-2 text-sm text-white">{startDate || '--'} {'->'} {endDate || '--'}</p>
          </div>
        </div>
      </div>
      {renderPresetQuickList()}
      {renderHistoryQuickList()}
    </aside>
  );

  return (
    <div className="w-full min-w-0 grid gap-8 xl:grid-cols-5 xl:items-start" data-testid="backtest-cockpit" data-module="rule" data-panel-mode={panelMode}>
      <div className="xl:col-span-1">
        {renderSetupSidebar()}
      </div>
      <main className="relative flex min-w-0 flex-col gap-6 rounded-[32px] border border-white/5 bg-white/[0.02] shadow-2xl backtest-setup-main xl:col-span-4" data-testid="backtest-cockpit-monitor">
        <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />
        <div className="p-6 md:p-8 xl:p-10" data-testid="backtest-setup-dashboard">
          <div className="flex flex-col gap-8 backtest-setup-form-stack">
            <div className="flex flex-col gap-3">
              <SectionEyebrow>{panelMode === 'professional' ? (language === 'en' ? 'Professional mode' : '专业模式') : (language === 'en' ? 'Execution board' : '执行面板')}</SectionEyebrow>
            </div>
            <div className="grid grid-cols-1 gap-8 xl:grid-cols-5 xl:items-stretch" data-testid="backtest-parameter-grid">
              {baseParamsSection}
              {executionSettingsSection}
              {strategyInputSection}
              {parsedStrategySection}
              {runControlsSection}
            </div>
          </div>
        </div>
        <div className="p-4 pt-0 md:p-6 md:pt-0" data-testid="backtest-sticky-action-bar">
          <div className="rounded-[24px] border border-white/10 bg-white/[0.05] p-4 shadow-2xl backdrop-blur-xl">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div className="min-w-0">
                <div className="text-sm font-bold text-white">{stickyStatusTitle}</div>
                <div className="mt-1 text-xs text-white/40">{stickyStatusNote}</div>
              </div>
              <div className="flex items-center gap-3">
                <Button variant="ghost" onClick={onReset}>{language === 'en' ? 'Reset' : '重置'}</Button>
                {parseStale ? (
                  <Button variant="secondary" onClick={() => void onParse()} disabled={isParsing || !strategyText.trim()}>
                    {language === 'en' ? 'Parse again' : '重新解析'}
                  </Button>
                ) : null}
                <Button
                  size="xl"
                  className="backtest-launch-button"
                  onClick={() => {
                    onStepChange('run');
                    void onRun();
                  }}
                  isLoading={isSubmitting}
                  loadingText={language === 'en' ? 'Opening result page…' : '正在打开结果页…'}
                  disabled={!canProceedFromConfirm}
                >
                  {language === 'en' ? 'Execute backtest task' : '执行回测任务'}
                </Button>
              </div>
            </div>
            {runError ? <ApiErrorAlert error={runError} className="mt-4" /> : null}
          </div>
        </div>
      </main>
    </div>
  );
};

export default DeterministicBacktestFlow;
