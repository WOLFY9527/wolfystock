import type React from 'react';
import { Suspense, lazy, useMemo } from 'react';
import { Button, Card } from '../../components/common';
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

type BacktestLanguage = 'zh' | 'en';

const DeterministicBacktestChartWorkspace = lazy(() => import('./DeterministicBacktestChartWorkspace').then((module) => ({
  default: module.DeterministicBacktestChartWorkspace,
})));

function bt(language: BacktestLanguage, key: string, vars?: Record<string, string | number | undefined>): string {
  return translate(language, `backtest.${key}`, vars);
}

function ChartWorkspaceLoadingPlaceholder() {
  return (
    <section
      className="backtest-void-workspace"
      data-testid="deterministic-backtest-chart-loading"
      aria-busy="true"
    >
      <div className="backtest-void-workspace__body">
        <div className="backtest-void-workspace__chart-card min-h-[340px] items-center justify-center border-white/10 bg-white/[0.02] px-5 py-8 backdrop-blur-md">
          <div className="flex flex-col items-center gap-3 text-center">
            <div className="h-2 w-28 overflow-hidden rounded-full bg-white/[0.06]">
              <div className="h-full w-1/2 rounded-full bg-cyan-300/70 shadow-[0_0_18px_rgba(103,232,249,0.28)]" />
            </div>
            <p className="text-xs font-medium text-white/70">图表加载中</p>
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
  const normalized = useMemo(
    () => providedNormalized ?? normalizeDeterministicBacktestResult(run, language),
    [providedNormalized, run, language],
  );
  const { viewerMeta } = normalized;
  const workspaceKey = `${viewerMeta.runId}:${viewerMeta.rowCount}:${viewerMeta.firstDate ?? 'empty'}:${viewerMeta.lastDate ?? 'empty'}`;

  return (
    <div
      className="backtest-result-viewer"
      data-testid="deterministic-backtest-result-view"
      data-run-id={run.id}
      data-row-count={viewerMeta.rowCount}
      data-main-series-length={viewerMeta.strategySeriesLength}
      data-daily-pnl-series-length={viewerMeta.dailyPnlSeriesLength}
      data-position-series-length={viewerMeta.positionSeriesLength}
      data-kpi-count={6}
      data-density={resolvedDensity.mode}
      style={getDeterministicResultDensityCssVars(resolvedDensity)}
    >
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
    </div>
  );
};
