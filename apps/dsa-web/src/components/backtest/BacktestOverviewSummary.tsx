import type React from 'react';
import { useState } from 'react';
import { SummaryStrip, AssumptionList, pct } from './shared';
import type { DeterministicBacktestNormalizedResult } from './normalizeDeterministicBacktestResult';
import type { RuleBacktestRunResponse } from '../../types/backtest';
import { useI18n } from '../../contexts/UiLanguageContext';
import {
  TerminalButton,
  TerminalChip,
  TerminalDisclosure,
  TerminalMetric,
  TerminalNestedBlock,
  TerminalPanel,
  TerminalSectionHeader,
} from '../terminal/TerminalPrimitives';

type TranslateFn = (key: string, vars?: Record<string, string | number | undefined>) => string;

export type BacktestWalkForwardOverview = {
  stateKey: 'available' | 'partial' | 'unavailable' | 'insufficient_history';
  stateLabel: string;
  windowSummary: string | null;
  meanReturn: string | null;
  maxDrawdown: string | null;
};

type BacktestOverviewSummaryProps = {
  resultPage: TranslateFn;
  run: RuleBacktestRunResponse;
  normalized: DeterministicBacktestNormalizedResult;
  selectedBenchmarkLabel: string;
  buyAndHoldLabel: string;
  benchmarkStatusNote: string;
  walkForwardOverview: BacktestWalkForwardOverview;
  decisionReportMarkdown: string;
  onExportDecisionReport: (format: 'md' | 'html') => void;
};

const BacktestOverviewSummary: React.FC<BacktestOverviewSummaryProps> = ({
  resultPage,
  run,
  normalized,
  selectedBenchmarkLabel,
  buyAndHoldLabel,
  benchmarkStatusNote,
  walkForwardOverview,
  decisionReportMarkdown,
  onExportDecisionReport,
}) => {
  const { language } = useI18n();
  const [copied, setCopied] = useState(false);

  const handleCopyReport = async () => {
    await navigator.clipboard.writeText(decisionReportMarkdown);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  };

  const walkForwardMetrics = [
    walkForwardOverview.windowSummary
      ? {
        key: 'windows',
        label: resultPage('overview.walkForwardWindowsLabel'),
        value: walkForwardOverview.windowSummary,
      }
      : null,
    walkForwardOverview.meanReturn
      ? {
        key: 'mean-return',
        label: resultPage('overview.walkForwardMeanReturnLabel'),
        value: walkForwardOverview.meanReturn,
      }
      : null,
    walkForwardOverview.maxDrawdown
      ? {
        key: 'drawdown',
        label: resultPage('overview.walkForwardDrawdownLabel'),
        value: walkForwardOverview.maxDrawdown,
      }
      : null,
  ].filter(Boolean) as Array<{ key: string; label: string; value: string }>;

  const walkForwardBody = walkForwardOverview.stateKey === 'insufficient_history'
    ? resultPage('overview.walkForwardInsufficientBody')
    : walkForwardMetrics.length
      ? resultPage('overview.walkForwardBody')
      : resultPage('overview.walkForwardUnavailableBody');

  const walkForwardStateVariant = walkForwardOverview.stateKey === 'available'
    ? 'success'
    : walkForwardOverview.stateKey === 'partial'
      ? 'caution'
      : walkForwardOverview.stateKey === 'insufficient_history'
        ? 'caution'
        : 'neutral';

  return (
    <section
      className="backtest-display-section"
      id="deterministic-result-tab-panel-overview"
      data-testid="deterministic-result-tab-panel-overview"
      role="tabpanel"
      aria-labelledby="deterministic-result-tab-overview"
    >
      <TerminalPanel className="product-section-card product-section-card--backtest-secondary flex flex-col gap-4">
        <TerminalSectionHeader
          eyebrow={resultPage('overview.subtitle')}
          title={resultPage('overview.title')}
        />
        <p className="text-sm leading-6 text-[color:var(--wolfy-text-muted)]">{resultPage('overview.intro')}</p>
        <SummaryStrip
          items={[
            { label: resultPage('overview.metricAuditRows'), value: String(normalized.viewerMeta.rowCount) },
            { label: resultPage('overview.metricTradeEvents'), value: String(normalized.tradeEvents.length) },
            { label: resultPage('overview.metricBenchmarkReturn'), value: pct(run.benchmarkReturnPct) },
            { label: resultPage('overview.metricBuyAndHold'), value: pct(run.buyAndHoldReturnPct) },
          ]}
        />
        <TerminalNestedBlock data-testid="overview-walk-forward-summary" className="flex flex-col gap-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">
                {resultPage('overview.walkForwardEyebrow')}
              </p>
              <h3 className="mt-1 text-sm font-medium text-[color:var(--wolfy-text-primary)]">{resultPage('overview.walkForwardTitle')}</h3>
              <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{walkForwardBody}</p>
            </div>
            <TerminalChip variant={walkForwardStateVariant}>{walkForwardOverview.stateLabel}</TerminalChip>
          </div>
          {walkForwardMetrics.length ? (
            <div className="grid gap-3 md:grid-cols-3">
              {walkForwardMetrics.map((item) => (
                <TerminalMetric
                  key={item.key}
                  label={item.label}
                  value={item.value}
                  valueClassName="text-sm font-semibold"
                />
              ))}
            </div>
          ) : null}
        </TerminalNestedBlock>
        <TerminalDisclosure title={resultPage('overview.benchmarkDisclosure')}>
          <div className="flex flex-col gap-4">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <TerminalMetric label={resultPage('overview.selectedBenchmark')} value={selectedBenchmarkLabel} valueClassName="truncate text-sm font-semibold" />
              <TerminalMetric label={resultPage('overview.vsBenchmark')} value={pct(run.excessReturnVsBenchmarkPct)} valueClassName="text-sm" />
              <TerminalMetric
                label={resultPage('overview.buyAndHold')}
                value={`${buyAndHoldLabel} · ${pct(run.buyAndHoldReturnPct)}`}
                valueClassName="text-xs font-semibold leading-5"
              />
              <TerminalMetric
                label={resultPage('overview.statusTimeline')}
                value={resultPage('overview.checkpoints', { count: run.statusHistory.length })}
                valueClassName="text-xs font-semibold leading-5"
              />
            </div>
            <p className="text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{benchmarkStatusNote}</p>
            <AssumptionList assumptions={run.executionAssumptions} emptyText={resultPage('overview.emptyExecutionAssumptions')} />
          </div>
        </TerminalDisclosure>
        <TerminalDisclosure title={resultPage('overview.exportSummaryDisclosure')}>
          <TerminalNestedBlock className="flex flex-col gap-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0">
                <h3 className="text-sm font-medium text-[color:var(--wolfy-text-primary)]">{resultPage('overview.resultSummaryTitle')}</h3>
                <p className="mt-2 text-sm leading-6 text-[color:var(--wolfy-text-muted)]">{resultPage('overview.resultSummaryBody')}</p>
              </div>
              <div className="flex flex-wrap gap-2 lg:justify-end">
                <TerminalButton variant="secondary" onClick={() => onExportDecisionReport('md')}>
                  {resultPage('overview.exportMarkdown')}
                </TerminalButton>
                <TerminalButton variant="compact" onClick={() => onExportDecisionReport('html')}>
                  {resultPage('overview.exportHtml')}
                </TerminalButton>
              </div>
            </div>
            <TerminalNestedBlock data-testid="decision-report-console" className="flex flex-col gap-3 overflow-hidden">
              <div className="flex justify-end">
                <TerminalButton
                  variant="compact"
                  onClick={() => void handleCopyReport()}
                  className="shrink-0"
                >
                  {copied
                    ? (language === 'en' ? 'Copied' : '已复制')
                    : (language === 'en' ? 'Copy full report' : '复制完整报告')}
                </TerminalButton>
              </div>
              <pre className="overflow-x-auto no-scrollbar rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3 text-xs leading-6 text-[color:var(--wolfy-text-secondary)]">
                {decisionReportMarkdown}
              </pre>
            </TerminalNestedBlock>
          </TerminalNestedBlock>
        </TerminalDisclosure>
      </TerminalPanel>
    </section>
  );
};

export default BacktestOverviewSummary;
