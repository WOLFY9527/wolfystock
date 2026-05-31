/* eslint-disable react-refresh/only-export-components */
import type React from 'react';
import { Button } from '../common/Button';
import { Checkbox } from '../common/Checkbox';
import { Disclosure } from '../common/Disclosure';
import { useI18n } from '../../contexts/UiLanguageContext';
import { translate } from '../../i18n/core';
import {
  formatDateTime as formatDateTimeValue,
  formatNumber as formatNumberValue,
  formatPercent as formatPercentValue,
} from '../../utils/format';
import { StatusBadge } from '../ui/StatusBadge';
import type {
  AssumptionMap,
  BacktestResultItem,
  BacktestRunHistoryItem,
  BacktestRunResponse,
  RuleBacktestHistoryItem,
  RuleBacktestParseResponse,
  RuleBacktestRunResponse,
  RuleBacktestTradeItem,
} from '../../types/backtest';

const TERMINAL_RULE_STATUSES = new Set(['completed', 'failed', 'cancelled']);
const CANCELLABLE_RULE_STATUSES = new Set(['queued', 'parsing', 'running', 'summarizing']);

type BacktestLanguage = 'zh' | 'en';

function bt(language: BacktestLanguage, key: string, vars?: Record<string, string | number | undefined>): string {
  return translate(language, `backtest.${key}`, vars);
}

export function isCanonicalNoEntrySignalMessage(message?: string | null): boolean {
  if (!message) return false;
  return message === bt('zh', 'runStatusBanner.noEntrySignal') || message === bt('en', 'runStatusBanner.noEntrySignal');
}

function getRuleStatusText(status?: string, language: BacktestLanguage = 'zh'): string {
  const normalized = String(status || 'queued').trim().toLowerCase();
  const label = bt(language, `ruleStatus.${normalized}`);
  return label === `backtest.ruleStatus.${normalized}` ? normalized : label;
}

function getHistoricalStatusText(status?: string, language: BacktestLanguage = 'zh'): string {
  const normalized = String(status || 'completed').trim().toLowerCase();
  const label = bt(language, `historicalStatus.${normalized}`);
  return label === `backtest.historicalStatus.${normalized}` ? normalized : label;
}

export { Disclosure };

export function pct(value?: number | null): string {
  return formatPercentValue(value, { digits: 2 });
}

export function formatNumber(value?: number | null, digits = 2): string {
  return formatNumberValue(value, digits);
}

export function formatDateTime(value?: string | null): string {
  return formatDateTimeValue(value);
}

function toDateInputValue(value: Date): string {
  return value.toISOString().slice(0, 10);
}

export function getDefaultRuleDateRange(): { startDate: string; endDate: string } {
  const end = new Date();
  const start = new Date(end);
  start.setFullYear(end.getFullYear() - 1);
  return {
    startDate: toDateInputValue(start),
    endDate: toDateInputValue(end),
  };
}

export type RuleBenchmarkMode =
  | 'auto'
  | 'none'
  | 'same_symbol_buy_and_hold'
  | 'index_hs300'
  | 'index_csi500'
  | 'index_ndx100'
  | 'etf_qqq'
  | 'index_sp500'
  | 'etf_spy'
  | 'custom_code';

export const RULE_BENCHMARK_OPTIONS: Array<{ value: RuleBenchmarkMode; label: string }> = [
  { value: 'auto', label: translate('zh', 'backtest.benchmarkMode.auto') },
  { value: 'none', label: translate('zh', 'backtest.benchmarkMode.none') },
  { value: 'same_symbol_buy_and_hold', label: translate('zh', 'backtest.benchmarkMode.same_symbol_buy_and_hold') },
  { value: 'index_hs300', label: translate('zh', 'backtest.benchmarkMode.index_hs300') },
  { value: 'index_csi500', label: translate('zh', 'backtest.benchmarkMode.index_csi500') },
  { value: 'index_ndx100', label: translate('zh', 'backtest.benchmarkMode.index_ndx100') },
  { value: 'etf_qqq', label: 'QQQ' },
  { value: 'index_sp500', label: translate('zh', 'backtest.benchmarkMode.index_sp500') },
  { value: 'etf_spy', label: 'SPY' },
  { value: 'custom_code', label: translate('zh', 'backtest.benchmarkMode.custom_code') },
];

function isAshareLikeCode(code: string): boolean {
  const normalized = String(code || '').trim().toUpperCase();
  return /^\d{6}$/.test(normalized);
}

function isUsLikeCode(code: string): boolean {
  const normalized = String(code || '').trim().toUpperCase();
  return /^[A-Z^]{1,5}(\.[A-Z])?$/.test(normalized);
}

export function getAutoBenchmarkMode(code: string): RuleBenchmarkMode {
  if (isAshareLikeCode(code)) return 'index_hs300';
  if (isUsLikeCode(code)) return 'etf_qqq';
  return 'same_symbol_buy_and_hold';
}

export function getBenchmarkModeLabel(mode: RuleBenchmarkMode, code?: string, customCode?: string, language: BacktestLanguage = 'zh'): string {
  if (mode === 'auto') {
    return bt(language, 'benchmarkMode.autoResolved', {
      label: getBenchmarkModeLabel(getAutoBenchmarkMode(code || ''), code, customCode, language),
    });
  }
  if (mode === 'custom_code') {
    const normalizedCustomCode = String(customCode || '').trim().toUpperCase();
    return normalizedCustomCode
      ? bt(language, 'benchmarkMode.customResolved', { code: normalizedCustomCode })
      : bt(language, 'benchmarkMode.custom_code');
  }
  const label = bt(language, `benchmarkMode.${mode}`);
  return label === `backtest.benchmarkMode.${mode}` ? bt(language, 'benchmarkMode.fallback') : label;
}

export function parsePositiveInt(value: string, fallback: number, minimum = 1): number {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(minimum, parsed);
}

function getSetupValue(setup: Record<string, unknown> | undefined, key: string): unknown {
  if (!setup) return undefined;
  if (key in setup) return setup[key];
  const camelKey = key.replace(/_([a-z])/g, (_, ch: string) => ch.toUpperCase());
  if (camelKey in setup) return setup[camelKey];
  return undefined;
}

export function getStrategySpecValue(spec: Record<string, unknown> | undefined, path: string[]): unknown {
  let current: unknown = spec;
  for (const segment of path) {
    if (!current || typeof current !== 'object') {
      return undefined;
    }
    const record = current as Record<string, unknown>;
    const camelSegment = segment.replace(/_([a-z])/g, (_, ch: string) => ch.toUpperCase());
    if (segment in record) {
      current = record[segment];
      continue;
    }
    if (camelSegment in record) {
      current = record[camelSegment];
      continue;
    }
    return undefined;
  }
  return current;
}

export function getStrategyPreviewSpec(parsed: RuleBacktestParseResponse | null): Record<string, unknown> | undefined {
  const direct = parsed?.parsedStrategy.strategySpec;
  if (direct && typeof direct === 'object') return direct;
  const fallback = parsed?.parsedStrategy.setup;
  return fallback && typeof fallback === 'object' ? fallback : undefined;
}

function getSetupString(setup: Record<string, unknown> | undefined, key: string): string {
  const value = getSetupValue(setup, key);
  if (value == null || value === '') return '--';
  return String(value);
}

function getSetupNumber(setup: Record<string, unknown> | undefined, key: string): number | null {
  const value = getSetupValue(setup, key);
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export function getPeriodicString(source: Record<string, unknown> | undefined, key: string): string {
  const strategyType = getStrategySpecValue(source, ['strategy_type']);
  if (strategyType === 'periodic_accumulation') {
    const fromSpec = {
      symbol: getStrategySpecValue(source, ['symbol']),
      start_date: getStrategySpecValue(source, ['date_range', 'start_date']),
      end_date: getStrategySpecValue(source, ['date_range', 'end_date']),
      execution_frequency: getStrategySpecValue(source, ['schedule', 'frequency']),
      execution_price_basis: getStrategySpecValue(source, ['entry', 'price_basis']),
      cash_policy: getStrategySpecValue(source, ['position_behavior', 'cash_policy']),
      exit_policy: getStrategySpecValue(source, ['exit', 'policy']),
      execution_timing: getStrategySpecValue(source, ['schedule', 'timing']),
    }[key];
    if (fromSpec != null && fromSpec !== '') return String(fromSpec);
  }
  return getSetupString(source, key);
}

export function getPeriodicNumber(source: Record<string, unknown> | undefined, key: string): number | null {
  const strategyType = getStrategySpecValue(source, ['strategy_type']);
  if (strategyType === 'periodic_accumulation') {
    const fromSpec = {
      initial_capital: getStrategySpecValue(source, ['capital', 'initial_capital']),
      quantity_per_trade: getStrategySpecValue(source, ['entry', 'order', 'quantity']),
      amount_per_trade: getStrategySpecValue(source, ['entry', 'order', 'amount']),
      fee_bps: getStrategySpecValue(source, ['costs', 'fee_bps']),
      slippage_bps: getStrategySpecValue(source, ['costs', 'slippage_bps']),
    }[key];
    if (fromSpec != null && fromSpec !== '') {
      const parsed = Number(fromSpec);
      return Number.isFinite(parsed) ? parsed : null;
    }
  }
  return getSetupNumber(source, key);
}

export function formatDraftOrder(source: Record<string, unknown> | undefined): string {
  return formatDraftOrderLabel(source, 'zh');
}

export function formatCashPolicy(source: Record<string, unknown> | undefined): string {
  return formatCashPolicyLabel(source, 'zh');
}

export function formatDraftOrderLabel(source: Record<string, unknown> | undefined, language: BacktestLanguage = 'zh'): string {
  const orderMode = String(getStrategySpecValue(source, ['entry', 'order', 'mode']) || getSetupString(source, 'order_mode'));
  if (orderMode === 'fixed_amount') {
    const amount = getPeriodicNumber(source, 'amount_per_trade');
    if (amount == null) return '--';
    return bt(language, 'periodic.fixedAmountOrder', { amount });
  }
  const quantity = getPeriodicNumber(source, 'quantity_per_trade');
  if (quantity == null) return '--';
  return bt(language, 'periodic.fixedShareOrder', { quantity });
}

export function formatCashPolicyLabel(source: Record<string, unknown> | undefined, language: BacktestLanguage = 'zh'): string {
  const value = getPeriodicString(source, 'cash_policy');
  if (value === 'stop_when_insufficient_cash') return bt(language, 'periodic.stopWhenCashInsufficient');
  if (value === 'skip_when_insufficient_cash') return bt(language, 'periodic.skipWhenCashInsufficient');
  return '--';
}

export function formatExecutionPriceBasisLabel(source: Record<string, unknown> | undefined, language: BacktestLanguage = 'zh'): string {
  const value = getPeriodicString(source, 'execution_price_basis');
  if (value === 'open') return bt(language, 'periodic.sameDayOpen');
  if (value === 'next_bar_open') return bt(language, 'periodic.nextBarOpen');
  if (value === 'close') return bt(language, 'periodic.close');
  return '--';
}

export function formatExitPolicyLabel(source: Record<string, unknown> | undefined, language: BacktestLanguage = 'zh'): string {
  const value = getPeriodicString(source, 'exit_policy');
  if (value === 'close_at_end') return bt(language, 'periodic.closeAtEnd');
  return '--';
}

export function buildPeriodicAssumptionLabels(
  source: Record<string, unknown> | undefined,
  language: BacktestLanguage = 'zh',
): string[] {
  const items: string[] = [];
  if (getPeriodicString(source, 'execution_price_basis') === 'open') {
    items.push(bt(language, 'periodic.openExecutionAssumption'));
  }
  if (getPeriodicString(source, 'execution_frequency') === 'daily') {
    items.push(bt(language, 'periodic.dailyAccumulationAssumption'));
  }
  if (getPeriodicString(source, 'cash_policy') === 'stop_when_insufficient_cash') {
    items.push(bt(language, 'periodic.cashStopAssumption'));
  }
  if (getPeriodicString(source, 'exit_policy') === 'close_at_end') {
    items.push(bt(language, 'periodic.closeAtEndAssumption'));
  }
  return items;
}

export function formatExecutionPriceBasis(source: Record<string, unknown> | undefined): string {
  return formatExecutionPriceBasisLabel(source, 'zh');
}

export function formatExitPolicy(source: Record<string, unknown> | undefined): string {
  return formatExitPolicyLabel(source, 'zh');
}

export function buildPeriodicAssumptions(source: Record<string, unknown> | undefined): string[] {
  return buildPeriodicAssumptionLabels(source, 'zh');
}

function formatIndicatorEntries(snapshot?: Record<string, unknown>): Array<{ key: string; value: string }> {
  return Object.entries(snapshot || {})
    .filter(([, value]) => value != null)
    .slice(0, 6)
    .map(([key, value]) => ({
      key,
      value: typeof value === 'number' ? value.toFixed(2) : String(value),
    }));
}

export function isRuleRunTerminal(status?: string): boolean {
  return TERMINAL_RULE_STATUSES.has(String(status || '').trim().toLowerCase());
}

export function canCancelRuleRun(status?: string): boolean {
  return CANCELLABLE_RULE_STATUSES.has(String(status || '').trim().toLowerCase());
}

export function getRuleRunStatusDescription(status?: string, language: BacktestLanguage = 'zh'): string {
  const normalized = String(status || '').trim().toLowerCase();
  const key = normalized ? `ruleRunStatusDescription.${normalized}` : 'ruleRunStatusDescription.default';
  const description = bt(language, key);
  return description === `backtest.${key}` ? bt(language, 'ruleRunStatusDescription.default') : description;
}

function getRuleRunStatusTone(status?: string): 'default' | 'success' | 'warning' | 'danger' | 'info' {
  const normalized = String(status || '').trim().toLowerCase();
  if (normalized === 'completed') return 'success';
  if (normalized === 'failed') return 'danger';
  if (normalized === 'summarizing') return 'info';
  if (normalized === 'cancelled') return 'warning';
  if (normalized === 'running' || normalized === 'queued' || normalized === 'parsing') return 'warning';
  return 'default';
}

export function getHistoricalStatusBadge(status?: string) {
  const normalized = status || 'completed';
  const label = getHistoricalStatusText(normalized);
  return <StatusBadge status={normalized} label={label} variant="soft" size="sm" />;
}

export function getRuleStatusBadge(status?: string) {
  const normalized = status || 'queued';
  const label = getRuleStatusText(normalized);
  return <StatusBadge status={normalized} label={label} variant="soft" size="sm" />;
}

export function getRuleRunStatusLabel(status?: string, language: BacktestLanguage = 'zh'): string {
  return getRuleStatusText(status, language);
}

export function getHistoricalRequestedModeLabel(mode?: string | null, language: BacktestLanguage = 'zh'): string {
  const normalized = String(mode || '').trim().toLowerCase();
  if (!normalized) return '--';
  if (normalized === 'local_first') return bt(language, 'historicalSource.requestedLocalFirst');
  if (normalized === 'api_first') return bt(language, 'historicalSource.requestedApiFirst');
  if (normalized === 'auto') return bt(language, 'historicalSource.requestedAuto');
  return String(mode);
}

export function getHistoricalResolvedSourceLabel(source?: string | null, language: BacktestLanguage = 'zh'): string {
  const normalized = String(source || '').trim();
  if (normalized === 'LocalParquet') return bt(language, 'historicalSource.localParquet');
  if (normalized === 'DatabaseCache') return bt(language, 'historicalSource.databaseCache');
  if (normalized === 'YfinanceFetcher') return bt(language, 'historicalSource.yfinanceFetcher');
  if (normalized === 'MixedFallback') return bt(language, 'historicalSource.mixedFallback');
  if (normalized === 'Unknown') return bt(language, 'historicalSource.unknown');
  return normalized || '--';
}

export function getHistoricalFallbackLabel(value?: boolean | null, language: BacktestLanguage = 'zh'): string {
  if (value == null) return '--';
  return value ? bt(language, 'historicalSource.fallbackUsed') : bt(language, 'historicalSource.fallbackNotUsed');
}

export function describeHistoricalDataSource(meta: {
  requestedMode?: string | null;
  resolvedSource?: string | null;
  fallbackUsed?: boolean | null;
}, language: BacktestLanguage = 'zh'): {
  tone: 'success' | 'warning' | 'info';
  title: string;
  body: string;
  detail: string;
} {
  const requestedLabel = getHistoricalRequestedModeLabel(meta.requestedMode, language);
  const resolvedLabel = getHistoricalResolvedSourceLabel(meta.resolvedSource, language);
  const fallbackLabel = getHistoricalFallbackLabel(meta.fallbackUsed, language);

  if (meta.resolvedSource === 'LocalParquet' && meta.fallbackUsed === false) {
    return {
      tone: 'success',
      title: bt(language, 'historicalSource.localHitTitle'),
      body: bt(language, 'historicalSource.localHitBody'),
      detail: bt(language, 'historicalSource.detail', { requested: requestedLabel, resolved: resolvedLabel, fallback: fallbackLabel }),
    };
  }

  if (meta.fallbackUsed) {
    return {
      tone: 'warning',
      title: bt(language, 'historicalSource.fallbackTitle', { source: resolvedLabel }),
      body: bt(language, 'historicalSource.fallbackBody'),
      detail: bt(language, 'historicalSource.detail', { requested: requestedLabel, resolved: resolvedLabel, fallback: fallbackLabel }),
    };
  }

  if (meta.resolvedSource) {
    return {
      tone: 'info',
      title: bt(language, 'historicalSource.usingTitle', { source: resolvedLabel }),
      body: bt(language, 'historicalSource.usingBody'),
      detail: bt(language, 'historicalSource.detail', { requested: requestedLabel, resolved: resolvedLabel, fallback: fallbackLabel }),
    };
  }

  return {
    tone: 'info',
    title: bt(language, 'historicalSource.waitingTitle'),
    body: bt(language, 'historicalSource.waitingBody'),
    detail: bt(language, 'historicalSource.detail', { requested: requestedLabel, resolved: resolvedLabel, fallback: fallbackLabel }),
  };
}

function renderDirectionBadge(correct?: boolean | null, expected?: string | null, language: BacktestLanguage = 'zh') {
  if (correct === true) return <span className="product-direction product-direction--positive">✓ {expected || bt(language, 'direction.matched')}</span>;
  if (correct === false) return <span className="product-direction product-direction--negative">✕ {expected || bt(language, 'direction.missed')}</span>;
  return <span className="product-direction">--</span>;
}

export const SectionEyebrow: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <span className="product-kicker">{children}</span>
);

export const MetricCard: React.FC<{
  label: string;
  value: string;
  tone?: 'default' | 'positive' | 'negative' | 'accent';
  note?: string;
}> = ({ label, value, tone = 'default', note }) => (
  <div className={`metric-card metric-card--${tone}`}>
    <p className="metric-card__label">{label}</p>
    <p className="metric-card__value">{value}</p>
    {note ? <p className="metric-card__note">{note}</p> : null}
  </div>
);

export const SummaryStrip: React.FC<{
  items: Array<{ label: string; value: string; note?: string }>;
}> = ({ items }) => (
  <ul className="summary-strip">
    {items.map((item) => (
      <li key={item.label} className="summary-strip__item">
        <p className="summary-strip__label">{item.label}</p>
        <p className="summary-strip__value">{item.value}</p>
        {item.note ? <p className="summary-strip__note">{item.note}</p> : null}
      </li>
    ))}
  </ul>
);

export const Banner: React.FC<{
  tone?: 'default' | 'success' | 'warning' | 'danger' | 'info';
  title: React.ReactNode;
  body?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}> = ({ tone = 'default', title, body, actions, className }) => (
  <div className={`product-banner product-banner--${tone}${className ? ` ${className}` : ''}`}>
    <div className="product-banner__copy">
      <p className="product-banner__title">{title}</p>
      {body ? <div className="product-banner__body">{body}</div> : null}
    </div>
    {actions ? <div className="product-banner__actions">{actions}</div> : null}
  </div>
);

export const AssumptionList: React.FC<{
  assumptions?: AssumptionMap;
  emptyText: string;
}> = ({ assumptions, emptyText }) => {
  const { language } = useI18n();
  const entries = Object.entries(assumptions || {}).reduce<Array<{ key: string; label: string; value: string }>>((acc, [key, value]) => {
    if (value != null && value !== '') {
      acc.push({
        key,
        label: (() => {
          const label = bt(language, `assumptionLabels.${key}`);
          return label === `backtest.assumptionLabels.${key}` ? key.replace(/_/g, ' ') : label;
        })(),
        value: typeof value === 'boolean'
          ? (value ? bt(language, 'common.yes') : bt(language, 'common.no'))
          : Array.isArray(value) ? value.join(', ') : String(value),
      });
    }
    return acc;
  }, []);

  if (entries.length === 0) {
    return <p className="product-empty-note">{emptyText}</p>;
  }

  return (
    <dl className="audit-grid">
      {entries.map((item) => (
        <div key={item.key} className="audit-grid__row">
          <dt className="audit-grid__label">{item.label}</dt>
          <dd className="audit-grid__value">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
};

export const HistoricalRunSummary: React.FC<{ data: BacktestRunResponse }> = ({ data }) => {
  const { language } = useI18n();

  return (
    <Banner
      tone="info"
      title={bt(language, 'historicalRunSummary.title')}
      body={(
        <>
          {bt(language, 'historicalRunSummary.body', {
            processed: data.processed,
            saved: data.saved,
            completed: data.completed,
          })}
          <span className="product-banner__meta">
            {bt(language, 'historicalRunSummary.meta', {
              insufficient: data.insufficient,
              errors: data.errors,
              candidateCount: data.candidateCount,
            })}
          </span>
          {data.noResultMessage ? <span className="product-banner__meta">{data.noResultMessage}</span> : null}
        </>
      )}
    />
  );
};

export const RuleRunStatusBanner: React.FC<{ run: RuleBacktestRunResponse }> = ({ run }) => {
  const { language } = useI18n();
  const latestStatusAt = run.statusHistory?.[run.statusHistory.length - 1]?.at;
  const tone = getRuleRunStatusTone(run.status);
  const statusDescription = getRuleRunStatusDescription(run.status, language);
  const localizedNoResultMessage = isCanonicalNoEntrySignalMessage(run.noResultMessage)
    ? bt(language, 'runStatusBanner.noEntrySignal')
    : null;

  return (
    <Banner
      tone={tone}
      title={(
        <span className="flex flex-wrap items-center gap-2">
          {bt(language, 'runStatusBanner.title')}
          <StatusBadge status={run.status} label={getRuleStatusText(run.status, language)} variant="soft" size="sm" />
        </span>
      )}
      body={(
        <>
          {statusDescription}
          <span className="product-banner__meta">
          {bt(language, 'runStatusBanner.run')} #{run.id} · {run.code} · {latestStatusAt ? formatDateTime(latestStatusAt) : '--'}
          </span>
          {localizedNoResultMessage ? <span className="product-banner__meta">{localizedNoResultMessage}</span> : null}
        </>
      )}
    />
  );
};

export const HistoricalResultsTable: React.FC<{ rows: BacktestResultItem[] }> = ({ rows }) => {
  const { language } = useI18n();
  if (rows.length === 0) {
    return <div className="product-empty-state">{bt(language, 'tables.noHistoricalResults')}</div>;
  }

  return (
    <div className="product-table-shell">
      <table className="product-table">
        <thead>
          <tr>
            <th>{bt(language, 'tables.date')}</th>
            <th>{bt(language, 'tables.code')}</th>
            <th>{bt(language, 'tables.advice')}</th>
            <th>{bt(language, 'tables.direction')}</th>
            <th className="product-table__align-right">{bt(language, 'tables.simulatedReturn')}</th>
            <th className="product-table__align-right">{bt(language, 'tables.instrumentReturn')}</th>
            <th>{bt(language, 'tables.marketSource')}</th>
            <th>{bt(language, 'common.status')}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.analysisHistoryId}>
              <td>{row.analysisDate || '--'}</td>
              <td className="product-table__mono">{row.code}</td>
              <td>{row.operationAdvice || '--'}</td>
              <td>{renderDirectionBadge(row.directionCorrect, row.directionExpected, language)}</td>
              <td className="product-table__align-right">{pct(row.simulatedReturnPct)}</td>
              <td className="product-table__align-right">{pct(row.stockReturnPct)}</td>
              <td>{row.marketDataSources.length > 0 ? row.marketDataSources.join(', ') : '--'}</td>
              <td><StatusBadge status={row.evalStatus} label={getHistoricalStatusText(row.evalStatus, language)} variant="soft" size="sm" /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export const HistoricalRunsTable: React.FC<{
  rows: BacktestRunHistoryItem[];
  selectedRunId: number | null;
  onOpen: (run: BacktestRunHistoryItem) => void;
}> = ({ rows, selectedRunId, onOpen }) => {
  const { language } = useI18n();
  if (rows.length === 0) {
    return <div className="product-empty-state">{bt(language, 'tables.noHistoricalRuns')}</div>;
  }

  return (
    <div className="product-table-shell">
      <table className="product-table">
        <thead>
          <tr>
            <th>{bt(language, 'tables.runTime')}</th>
            <th>{bt(language, 'tables.code')}</th>
            <th>{bt(language, 'tables.window')}</th>
            <th className="product-table__align-right">{bt(language, 'tables.candidates')}</th>
            <th className="product-table__align-right">{bt(language, 'tables.winRate')}</th>
            <th className="product-table__align-right">{bt(language, 'tables.averageSimulatedReturn')}</th>
            <th>{bt(language, 'common.status')}</th>
            <th className="product-table__align-right">{bt(language, 'common.action')}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} data-active={selectedRunId === row.id ? 'true' : 'false'}>
              <td>{formatDateTime(row.runAt)}</td>
              <td className="product-table__mono">{row.code || '--'}</td>
              <td>{row.evaluationWindowTradingBars || row.evalWindowDays} {bt(language, 'common.bars')} / {row.maturityCalendarDays || row.minAgeDays} {bt(language, 'common.days')}</td>
              <td className="product-table__align-right">{row.candidateCount}</td>
              <td className="product-table__align-right">{pct(row.winRatePct)}</td>
              <td className="product-table__align-right">{pct(row.avgSimulatedReturnPct)}</td>
              <td><StatusBadge status={row.status} label={getHistoricalStatusText(row.status, language)} variant="soft" size="sm" /></td>
              <td className="product-table__align-right">
                <Button size="sm" variant="ghost" onClick={() => onOpen(row)}>
                  {bt(language, 'common.open')}
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export const RuleBacktestTradeTable: React.FC<{ trades: RuleBacktestTradeItem[] }> = ({ trades }) => {
  const { language } = useI18n();
  if (trades.length === 0) {
    return <div className="product-empty-state">{bt(language, 'tables.noTradeDetail')}</div>;
  }

  return (
    <div className="product-table-shell">
      <table className="product-table product-table--wide">
        <thead>
          <tr>
            <th>{bt(language, 'tables.signalAndFills')}</th>
            <th>{bt(language, 'tables.entryTrigger')}</th>
            <th>{bt(language, 'tables.exitTrigger')}</th>
            <th>{bt(language, 'tables.indicatorSnapshot')}</th>
            <th className="product-table__align-right">{bt(language, 'tables.return')}</th>
            <th className="product-table__align-right">{bt(language, 'tables.holding')}</th>
            <th>{bt(language, 'tables.executionAudit')}</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((trade, index) => {
            const entryIndicators = formatIndicatorEntries(trade.entryIndicators);
            const exitIndicators = formatIndicatorEntries(trade.exitIndicators);
            return (
              <tr key={`${trade.code}-${trade.tradeIndex ?? index}`}>
                <td>
                  <div className="product-table__stack">
                    <span className="product-table__mono">{trade.entrySignalDate || trade.entryDate || '--'} → {trade.exitSignalDate || trade.exitDate || '--'}</span>
                    <span>{trade.entryDate || '--'} @ {formatNumber(trade.entryPrice)}</span>
                    <span>{trade.exitDate || '--'} @ {formatNumber(trade.exitPrice)}</span>
                  </div>
                </td>
                <td>{trade.entryTrigger || trade.entrySignal || '--'}</td>
                <td>{trade.exitTrigger || trade.exitSignal || '--'}</td>
                <td>
                  <div className="indicator-stack">
                    {entryIndicators.length > 0 ? (
                      <div>
                        <p className="metric-card__label">{bt(language, 'tables.entry')}</p>
                        <div className="product-chip-list product-chip-list--tight">
                          {entryIndicators.map((item) => (
                            <span key={`entry-${item.key}`} className="product-chip">
                              {item.key}: {item.value}
                            </span>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    {exitIndicators.length > 0 ? (
                      <div>
                        <p className="metric-card__label">{bt(language, 'tables.exit')}</p>
                        <div className="product-chip-list product-chip-list--tight">
                          {exitIndicators.map((item) => (
                            <span key={`exit-${item.key}`} className="product-chip">
                              {item.key}: {item.value}
                            </span>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </div>
                </td>
                <td className="product-table__align-right">{pct(trade.returnPct)}</td>
                <td className="product-table__align-right">
                  <div className="product-table__stack">
                    <span>{trade.holdingBars ?? trade.holdingDays ?? '--'} bars</span>
                    <span>{trade.holdingCalendarDays ?? '--'} {bt(language, 'common.days')}</span>
                  </div>
                </td>
                <td>
                  <div className="product-table__stack">
                    <span>{bt(language, 'tables.signalPriceBasis')}: {trade.signalPriceBasis || '--'}</span>
                    <span>{bt(language, 'tables.fillPriceBasis')}: {trade.priceBasis || '--'}</span>
                    <span>{bt(language, 'tables.feeSlippage')}: {formatNumber(trade.feeBps, 1)}bp / {formatNumber(trade.slippageBps, 1)}bp</span>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export const RuleRunsTable: React.FC<{
  rows: RuleBacktestHistoryItem[];
  selectedRunId: number | null;
  onOpen: (run: RuleBacktestHistoryItem) => void;
  compareSelection?: {
    selectedIds: number[];
    onToggle: (run: RuleBacktestHistoryItem) => void;
    maxSelections?: number;
  };
}> = ({ rows, selectedRunId, onOpen, compareSelection }) => {
  const { language } = useI18n();
  if (rows.length === 0) {
    return <div className="product-empty-state">{bt(language, 'tables.noRuleRuns')}</div>;
  }

  return (
    <div className="product-table-shell">
      <table className="product-table">
        <thead>
          <tr>
            <th>{bt(language, 'tables.runTime')}</th>
            <th>{bt(language, 'tables.code')}</th>
            <th>{bt(language, 'common.status')}</th>
            <th className="product-table__align-right">{bt(language, 'tables.lookback')}</th>
            <th className="product-table__align-right">{bt(language, 'tables.trades')}</th>
            <th className="product-table__align-right">{bt(language, 'tables.totalReturn')}</th>
            <th className="product-table__align-right">{bt(language, 'tables.excessReturn')}</th>
            {compareSelection ? <th className="product-table__align-right">{bt(language, 'common.compare')}</th> : null}
            <th className="product-table__align-right">{bt(language, 'common.action')}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} data-active={selectedRunId === row.id ? 'true' : 'false'}>
              <td>{formatDateTime(row.runAt)}</td>
              <td className="product-table__mono">{row.code}</td>
              <td>
                <div className="product-table__stack">
                  <StatusBadge status={row.status} label={getRuleStatusText(row.status, language)} variant="soft" size="sm" />
                  <span>{getRuleRunStatusDescription(row.status, language) || '--'}</span>
                </div>
              </td>
              <td className="product-table__align-right">{row.lookbackBars}</td>
              <td className="product-table__align-right">{row.tradeCount}</td>
              <td className="product-table__align-right">{pct(row.totalReturnPct)}</td>
              <td className="product-table__align-right">{pct(row.excessReturnVsBuyAndHoldPct)}</td>
              {compareSelection ? (
                <td className="product-table__align-right">
                  {row.id === selectedRunId ? (
                    <span className="product-chip">{bt(language, 'common.current')}</span>
                  ) : row.status !== 'completed' ? (
                    <span className="product-footnote">{bt(language, 'common.completedOnly')}</span>
                  ) : (
                    <Checkbox
                      aria-label={bt(language, 'tables.compareRunAria', { id: row.id })}
                      checked={compareSelection.selectedIds.includes(row.id)}
                      disabled={
                        !compareSelection.selectedIds.includes(row.id)
                        && compareSelection.selectedIds.length >= (compareSelection.maxSelections ?? 3)
                      }
                      onChange={() => compareSelection.onToggle(row)}
                    />
                  )}
                </td>
              ) : null}
              <td className="product-table__align-right">
                <Button size="sm" variant="ghost" onClick={() => onOpen(row)}>
                  {bt(language, 'common.open')}
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
