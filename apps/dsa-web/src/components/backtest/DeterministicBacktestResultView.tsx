import type React from 'react';
import { Suspense, lazy } from 'react';
import { Button } from '../common/Button';
import { Card } from '../common/Card';
import type { RuleBacktestRunResponse } from '../../types/backtest';
import {
  getDeterministicResultDensityCssVars,
  type DeterministicResultDensityConfig,
  useDeterministicResultDensity,
} from './deterministicResultDensity';
import { formatNumber, pct } from './shared';
import {
  formatDeterministicActionLabel,
  normalizeDeterministicBacktestResult,
  type DeterministicBacktestNormalizedResult,
  type DeterministicBacktestNormalizedRow,
  type DeterministicBacktestTradeEvent,
} from './normalizeDeterministicBacktestResult';
import {
  downloadExecutionTraceCsv,
  downloadExecutionTraceJson,
  hasExecutionTraceRows,
} from './executionTraceUtils';
import { useI18n } from '../../contexts/UiLanguageContext';
import { translate } from '../../i18n/core';
import { isCanonicalNoEntrySignalMessage } from './shared';

type BacktestLanguage = 'zh' | 'en';

const DeterministicBacktestChartWorkspace = lazy(() => import('./DeterministicBacktestChartWorkspace').then((module) => ({
  default: module.DeterministicBacktestChartWorkspace,
})));

function bt(language: BacktestLanguage, key: string, vars?: Record<string, string | number | undefined>): string {
  return translate(language, `backtest.${key}`, vars);
}

type RiskMetricCard = {
  key: string;
  label: string;
  value: string;
  tone: 'positive' | 'negative' | 'default';
};

function getRiskMetricTone(value: number | null | undefined, negativeIsRisk = false): 'positive' | 'negative' | 'default' {
  if (value == null || !Number.isFinite(value)) return 'default';
  if (negativeIsRisk) return Math.abs(value) > 0 ? 'negative' : 'default';
  if (value > 0) return 'positive';
  if (value < 0) return 'negative';
  return 'default';
}

function getRiskMetricCards(
  run: RuleBacktestRunResponse,
  normalized: DeterministicBacktestNormalizedResult,
  language: BacktestLanguage,
): RiskMetricCard[] {
  const cards: RiskMetricCard[] = [];
  const { metrics } = normalized;

  if (metrics.totalReturnPct != null) {
    cards.push({
      key: 'total-return',
      label: language === 'en' ? 'Total return' : '总收益',
      value: pct(metrics.totalReturnPct),
      tone: getRiskMetricTone(metrics.totalReturnPct),
    });
  }
  if (metrics.sharpeRatio != null) {
    cards.push({
      key: 'sharpe',
      label: 'Sharpe',
      value: formatNumber(metrics.sharpeRatio),
      tone: getRiskMetricTone(metrics.sharpeRatio),
    });
  }
  if (metrics.maxDrawdownPct != null) {
    const drawdownValue = metrics.maxDrawdownPct > 0 ? -metrics.maxDrawdownPct : metrics.maxDrawdownPct;
    cards.push({
      key: 'max-drawdown',
      label: language === 'en' ? 'Max DD' : '最大回撤',
      value: pct(drawdownValue),
      tone: getRiskMetricTone(drawdownValue, true),
    });
  }
  if (metrics.winRatePct != null) {
    cards.push({
      key: 'win-rate',
      label: language === 'en' ? 'Win rate' : '胜率',
      value: pct(metrics.winRatePct),
      tone: getRiskMetricTone(metrics.winRatePct),
    });
  }
  if (metrics.finalEquity != null) {
    cards.push({
      key: 'final-equity',
      label: language === 'en' ? 'Final equity' : '期末权益',
      value: formatNumber(metrics.finalEquity),
      tone: getRiskMetricTone(metrics.finalEquity - (run.initialCapital ?? metrics.finalEquity)),
    });
  }

  return cards.slice(0, 5);
}

function ResultStatePanel({
  run,
  normalized,
}: {
  run: RuleBacktestRunResponse;
  normalized: DeterministicBacktestNormalizedResult;
}) {
  const { language } = useI18n();
  const isCompleted = run.status === 'completed';
  const hasRows = normalized.rows.length > 0;
  const noEntryMessage = isCanonicalNoEntrySignalMessage(run.noResultMessage)
    ? bt(language, 'resultPage.noEntrySignal')
    : null;
  const title = isCompleted
    ? (language === 'en' ? 'No simulation result to visualize' : '暂无可视化结果')
    : (language === 'en' ? 'Simulation result pending' : '结果生成中');
  const body = isCompleted
    ? (
      noEntryMessage
      || run.noResultMessage
      || (language === 'en'
        ? 'This run finished without a displayable equity, drawdown, or risk summary.'
        : '本次研究回测完成后，未生成可展示的权益、回撤或风险摘要。')
    )
    : (
      language === 'en'
        ? 'Assembling results'
        : '正在整理结果'
    );
  const chips = [
    { key: 'status', label: language === 'en' ? 'Status' : '状态', value: String(run.status || '--') },
    { key: 'rows', label: language === 'en' ? 'Visible rows' : '可视行数', value: String(normalized.viewerMeta.rowCount || 0) },
    { key: 'trades', label: language === 'en' ? 'Simulated trades' : '模拟交易', value: String(normalized.metrics.tradeCount || 0) },
  ];

  if (hasRows) return null;

  return (
    <section
      className="backtest-display-section"
      data-testid={isCompleted ? 'deterministic-result-empty-state' : 'deterministic-result-pending-state'}
    >
      <div className="backtest-void-workspace">
        <div className="backtest-void-workspace__chart-card min-h-[320px] border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-rail)] px-5 py-6">
          <div className="flex h-full flex-col justify-between gap-5">
            <div className="space-y-3">
              <p className="backtest-void-workspace__eyebrow">
                {language === 'en' ? 'Research simulation only' : '仅供研究模拟'}
              </p>
              <div>
                <h3 className="text-base font-semibold text-[color:var(--wolfy-text-primary)]">{title}</h3>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">{body}</p>
              </div>
            </div>
            <div className="grid gap-3 md:grid-cols-3">
              {chips.map((chip) => (
                <div
                  key={chip.key}
                  className="rounded-[1rem] border border-[color:var(--wolfy-border-subtle)] bg-[rgba(15,23,42,0.32)] px-3 py-3"
                >
                  <p className="metric-card__label">{chip.label}</p>
                  <p className="mt-1 text-sm font-medium text-[color:var(--wolfy-text-primary)]">{chip.value}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function ChartWorkspaceLoadingPlaceholder() {
  return (
    <section
      className="backtest-void-workspace"
      data-testid="deterministic-backtest-chart-loading"
      aria-busy="true"
    >
      <div className="backtest-void-workspace__body">
        <div className="backtest-void-workspace__chart-card min-h-[340px] items-center justify-center border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] px-5 py-8">
          <div className="flex flex-col items-center gap-3 text-center">
            <div className="h-2 w-28 overflow-hidden rounded-full bg-[var(--wolfy-surface-rail)]">
              <div className="h-full w-1/2 rounded-full bg-[var(--wolfy-accent)]" />
            </div>
            <p className="text-xs font-medium text-[color:var(--wolfy-text-secondary)]">图表加载中</p>
          </div>
        </div>
      </div>
    </section>
  );
}

export function DeterministicAuditTable({
  run,
  rows,
}: {
  run: RuleBacktestRunResponse;
  rows: DeterministicBacktestNormalizedRow[];
}) {
  const { language } = useI18n();
  return (
    <Card
      title={bt(language, 'resultPage.auditTable.title')}
      subtitle={bt(language, 'resultPage.auditTable.subtitle')}
      className="product-section-card product-section-card--backtest-standard"
    >
      <div className="backtest-audit-table__header">
        <p className="product-section-copy">{bt(language, 'resultPage.auditTable.description')}</p>
        <div className="product-action-row">
          <Button variant="secondary" onClick={() => downloadExecutionTraceCsv(run)} disabled={!hasExecutionTraceRows(run)}>{bt(language, 'resultPage.statusCard.exportCsv')}</Button>
          <Button variant="ghost" onClick={() => downloadExecutionTraceJson(run)} disabled={!hasExecutionTraceRows(run)}>{bt(language, 'resultPage.auditTable.exportJson')}</Button>
        </div>
      </div>
      {rows.length === 0 ? (
        <div className="product-empty-state product-empty-state--compact">{bt(language, 'resultPage.auditTable.exportEmpty')}</div>
      ) : (
        <div className="product-table-shell">
          <table className="product-table product-table--audit">
            <thead>
              <tr>
                <th>{bt(language, 'tables.date')}</th>
                <th>{bt(language, 'common.action')}</th>
                <th className="product-table__align-right">{bt(language, 'resultPage.auditTable.close')}</th>
                <th className="product-table__align-right">{bt(language, 'resultPage.auditTable.benchmarkClose')}</th>
                <th className="product-table__align-right">{bt(language, 'resultPage.auditTable.fillPrice')}</th>
                <th className="product-table__align-right">{bt(language, 'resultPage.auditTable.shares')}</th>
                <th className="product-table__align-right">{bt(language, 'resultPage.auditTable.cash')}</th>
                <th className="product-table__align-right">{bt(language, 'resultPage.auditTable.totalEquity')}</th>
                <th className="product-table__align-right">{bt(language, 'resultPage.auditTable.dailyPnl')}</th>
                <th className="product-table__align-right">{bt(language, 'resultPage.auditTable.dailyReturn')}</th>
                <th className="product-table__align-right">{bt(language, 'resultPage.auditTable.strategyCumulative')}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`audit-${row.date}`}>
                  <td>{row.date}</td>
                  <td>{formatDeterministicActionLabel(row.action, language)}</td>
                  <td className="product-table__align-right">{formatNumber(row.symbolClose)}</td>
                  <td className="product-table__align-right">{formatNumber(row.benchmarkClose)}</td>
                  <td className="product-table__align-right">{formatNumber(row.fillPrice)}</td>
                  <td className="product-table__align-right">{formatNumber(row.shares, 4)}</td>
                  <td className="product-table__align-right">{formatNumber(row.cash)}</td>
                  <td className="product-table__align-right">{formatNumber(row.totalValue)}</td>
                  <td className="product-table__align-right">{formatNumber(row.dailyPnl)}</td>
                  <td className="product-table__align-right">{pct(row.dailyReturn)}</td>
                  <td className="product-table__align-right">{pct(row.strategyCumReturn)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

export function DeterministicTradeEventTable({ events }: { events: DeterministicBacktestTradeEvent[] }) {
  const { language } = useI18n();
  return (
    <Card title={bt(language, 'resultPage.tradeEventTable.title')} subtitle={bt(language, 'resultPage.tradeEventTable.subtitle')} className="product-section-card product-section-card--backtest-standard">
      {events.length === 0 ? (
        <div className="product-empty-state product-empty-state--compact">{bt(language, 'resultPage.tradeEventTable.empty')}</div>
      ) : (
        <div className="product-table-shell">
          <table className="product-table product-table--audit">
            <thead>
              <tr>
                <th>{bt(language, 'tables.date')}</th>
                <th>{bt(language, 'common.action')}</th>
                <th className="product-table__align-right">{bt(language, 'resultPage.tradeEventTable.fillPrice')}</th>
                <th className="product-table__align-right">{bt(language, 'resultPage.tradeEventTable.shares')}</th>
                <th className="product-table__align-right">{bt(language, 'resultPage.tradeEventTable.cash')}</th>
                <th className="product-table__align-right">{bt(language, 'resultPage.tradeEventTable.totalEquity')}</th>
                <th>{bt(language, 'resultPage.tradeEventTable.signalOrTrigger')}</th>
                <th className="product-table__align-right">{bt(language, 'tables.return')}</th>
                <th>{bt(language, 'resultPage.tradeEventTable.source')}</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={event.key}>
                  <td>{event.date}</td>
                  <td>{formatDeterministicActionLabel(event.action, language)}</td>
                  <td className="product-table__align-right">{formatNumber(event.fillPrice)}</td>
                  <td className="product-table__align-right">{formatNumber(event.shares, 4)}</td>
                  <td className="product-table__align-right">{formatNumber(event.cash)}</td>
                  <td className="product-table__align-right">{formatNumber(event.totalValue)}</td>
                  <td>{event.signalSummary || event.trigger || '--'}</td>
                  <td className="product-table__align-right">{pct(event.returnPct)}</td>
                  <td>{event.source === 'row' ? bt(language, 'resultPage.tradeEventTable.auditRow') : bt(language, 'resultPage.tradeEventTable.tradeLog')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

export const DeterministicBacktestResultView: React.FC<{
  run: RuleBacktestRunResponse;
  normalized?: DeterministicBacktestNormalizedResult;
  densityConfig?: DeterministicResultDensityConfig;
}> = ({ run, normalized: providedNormalized, densityConfig }) => {
  const { language } = useI18n();
  const fallbackDensityConfig = useDeterministicResultDensity();
  const resolvedDensity = densityConfig ?? fallbackDensityConfig;
  const normalized = providedNormalized ?? normalizeDeterministicBacktestResult(run, language);
  const { viewerMeta } = normalized;
  const workspaceKey = `${viewerMeta.runId}:${viewerMeta.rowCount}:${viewerMeta.firstDate ?? 'empty'}:${viewerMeta.lastDate ?? 'empty'}`;
  const riskMetricCards = getRiskMetricCards(run, normalized, language);
  const hasChartRows = normalized.rows.length > 0;

  return (
    <div
      className="backtest-result-viewer"
      data-testid="deterministic-backtest-result-view"
      data-run-id={run.id}
      data-row-count={viewerMeta.rowCount}
      data-main-series-length={viewerMeta.strategySeriesLength}
      data-daily-pnl-series-length={viewerMeta.dailyPnlSeriesLength}
      data-position-series-length={viewerMeta.positionSeriesLength}
      data-kpi-count={riskMetricCards.length}
      data-density={resolvedDensity.mode}
      style={getDeterministicResultDensityCssVars(resolvedDensity)}
    >
      {riskMetricCards.length ? (
        <section className="backtest-display-section" data-testid="deterministic-result-risk-strip">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            {riskMetricCards.map((card) => (
              <div
                key={card.key}
                className="rounded-[1rem] border border-[color:var(--wolfy-border-subtle)] bg-[rgba(15,23,42,0.24)] px-3 py-3"
              >
                <p className="metric-card__label">{card.label}</p>
                <p
                  className={`mt-1 text-sm font-semibold ${
                    card.tone === 'positive'
                      ? 'text-[color:var(--state-success-text)]'
                      : card.tone === 'negative'
                        ? 'text-[color:var(--state-danger-text)]'
                        : 'text-[color:var(--wolfy-text-primary)]'
                  }`}
                >
                  {card.value}
                </p>
                <p className="mt-1 text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">
                  {language === 'en' ? 'Historical simulation only.' : '仅反映历史模拟结果。'}
                </p>
              </div>
            ))}
          </div>
        </section>
      ) : null}
      <ResultStatePanel run={run} normalized={normalized} />
      {hasChartRows ? (
        <section className="backtest-display-section" data-testid="backtest-display-section-dashboard">
          <div data-testid="deterministic-result-dashboard">
            <div
              className="backtest-result-viewer__chart-stage backtest-result-viewer__chart-stage--void"
              data-testid="deterministic-result-chart-shell"
            >
              <Suspense fallback={<ChartWorkspaceLoadingPlaceholder />}>
                <DeterministicBacktestChartWorkspace key={workspaceKey} normalized={normalized} run={run} densityConfig={resolvedDensity} />
              </Suspense>
            </div>
          </div>
        </section>
      ) : null}
    </div>
  );
};
