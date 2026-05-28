import type React from 'react';
import { useState } from 'react';
import { useI18n } from '../../contexts/UiLanguageContext';
import { translate, type UiLanguage } from '../../i18n/core';
import type { RuleBacktestRunResponse } from '../../types/backtest';
import { DeterministicBacktestResultView } from './DeterministicBacktestResultView';
import type { DeterministicResultDensityConfig } from './deterministicResultDensity';
import type { DeterministicBacktestNormalizedResult } from './normalizeDeterministicBacktestResult';
import { pct } from './shared';

export type CoverageTrackItem = {
  key: string;
  label: string;
  summary: string;
  detail: string;
  state: string;
  ratio: number;
};

export type RiskControlVisualRow = {
  key: 'stop-loss' | 'take-profit' | 'trailing-stop';
  label: string;
  value: number;
  valueLabel: string;
};

const COVERAGE_TRACK_COLORS = ['#7dd3fc', '#86efac', '#fbbf24'];

function btr(language: UiLanguage, key: string, vars?: Record<string, string | number | undefined>): string {
  return translate(language, `backtest.resultPage.${key}`, vars);
}

export function RobustnessCoverageTrack({
  rows,
}: {
  rows: CoverageTrackItem[];
}) {
  const { language } = useI18n();
  if (!rows.length) return null;

  const averageCoverage = rows.reduce((total, row) => total + row.ratio, 0) / rows.length;

  return (
    <div className="summary-block mt-4" data-testid="robustness-coverage-overview">
      <div className="summary-block__header">
        <div>
          <h3 className="summary-block__title">{btr(language, 'riskControls.coverageTrack')}</h3>
        </div>
        <div className="product-chip-list product-chip-list--tight">
          <span className="product-chip">{btr(language, 'riskControls.averageCoverage', { value: pct(averageCoverage * 100) })}</span>
        </div>
      </div>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-[rgba(255,255,255,0.08)]">
        {rows.map((row, index) => (
          <div
            key={`coverage-${row.key}`}
            className="h-full"
            style={{
              width: `${row.ratio * 100}%`,
              backgroundColor: COVERAGE_TRACK_COLORS[index % COVERAGE_TRACK_COLORS.length],
            }}
          />
        ))}
      </div>
      <div className="mt-3 grid gap-2 md:grid-cols-3">
        {rows.map((row, index) => (
          <div
            key={`coverage-card-${row.key}`}
            className="rounded-[1rem] border border-[var(--border-muted)] bg-[rgba(15,23,42,0.18)] px-3 py-2.5"
          >
            <div className="flex items-start justify-between gap-3">
              <p className="metric-card__label">{row.label}</p>
              <span
                className="inline-block size-2.5 rounded-full"
                style={{ backgroundColor: COVERAGE_TRACK_COLORS[index % COVERAGE_TRACK_COLORS.length] }}
              />
            </div>
            <p className="mt-1 preview-card__text">{row.summary}</p>
            <p className="mt-1 text-[11px] text-secondary">{row.detail}</p>
            <div className="mt-2 flex items-center justify-between gap-3 text-[11px] text-secondary">
              <span>{btr(language, 'riskControls.coverage', { value: pct(row.ratio * 100) })}</span>
              <span className="product-chip">{row.state}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function RiskControlsLadder({
  rows,
  activeRiskControlKey,
}: {
  rows: RiskControlVisualRow[];
  activeRiskControlKey: RiskControlVisualRow['key'] | null;
}) {
  const { language } = useI18n();
  if (!rows.length) return null;

  const strongestRiskControl = rows.reduce((currentMax, row) => Math.max(currentMax, row.value), 0);

  return (
    <div className="summary-block mt-4" data-testid="result-risk-controls-visualization">
      <div className="summary-block__header">
        <div>
          <h3 className="summary-block__title">{btr(language, 'riskControls.protectionLadder')}</h3>
        </div>
        <div className="product-chip-list product-chip-list--tight">
          <span className="product-chip">{btr(language, 'riskControls.enabledCount', { count: rows.length })}</span>
          <span className="product-chip">{btr(language, 'riskControls.highestThreshold', { value: strongestRiskControl.toFixed(2) })}</span>
        </div>
      </div>
      <div className="space-y-3">
        {rows.map((row) => {
          const width = strongestRiskControl > 0 ? Math.max(16, (row.value / strongestRiskControl) * 100) : 0;
          return (
            <div
              key={`risk-control-${row.key}`}
              className={`space-y-1.5 rounded-[0.85rem] px-2 py-1.5 transition-colors ${
                activeRiskControlKey === row.key ? 'bg-[rgba(125,211,252,0.1)]' : ''
              }`}
              data-linked-highlight={activeRiskControlKey === row.key ? 'true' : undefined}
              data-testid={`result-risk-controls-row-${row.key}`}
            >
              <div className="flex items-center justify-between gap-3">
                <span className="metric-card__label">{row.label}</span>
                <span className="preview-card__text">{row.valueLabel}</span>
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
  );
}

function AdditiveDashboardPanels({
  hasRobustnessAnalysis,
  robustnessLensRows,
  riskControlRows,
  activeRobustnessKey,
  activeRiskControlKey,
  onActiveRobustnessChange,
  onActiveRiskControlChange,
}: {
  hasRobustnessAnalysis: boolean;
  robustnessLensRows: CoverageTrackItem[];
  riskControlRows: RiskControlVisualRow[];
  activeRobustnessKey: string | null;
  activeRiskControlKey: RiskControlVisualRow['key'] | null;
  onActiveRobustnessChange: (key: string | null) => void;
  onActiveRiskControlChange: (key: RiskControlVisualRow['key'] | null) => void;
}) {
  const { language } = useI18n();
  const [hoveredRobustnessRow, setHoveredRobustnessRow] = useState<CoverageTrackItem | null>(null);
  const [hoveredRiskControlRow, setHoveredRiskControlRow] = useState<RiskControlVisualRow | null>(null);
  if (!hasRobustnessAnalysis && riskControlRows.length === 0) return null;

  const averageCoverage = robustnessLensRows.length
    ? robustnessLensRows.reduce((total, row) => total + row.ratio, 0) / robustnessLensRows.length
    : 0;
  const strongestRiskControl = riskControlRows.reduce((currentMax, row) => Math.max(currentMax, row.value), 0);
  const activateRobustnessRow = (row: CoverageTrackItem) => {
    setHoveredRobustnessRow(row);
    onActiveRobustnessChange(row.key);
  };
  const clearRobustnessRow = () => {
    setHoveredRobustnessRow(null);
    onActiveRobustnessChange(null);
  };
  const activateRiskControlRow = (row: RiskControlVisualRow) => {
    setHoveredRiskControlRow(row);
    onActiveRiskControlChange(row.key);
  };
  const clearRiskControlRow = () => {
    setHoveredRiskControlRow(null);
    onActiveRiskControlChange(null);
  };

  return (
    <div className="backtest-display-section mt-3" data-testid="result-additive-dashboard">
      <div className="preview-grid">
        {hasRobustnessAnalysis ? (
          <div
            className="summary-block"
            data-testid="dashboard-robustness-panel"
            title={btr(language, 'riskControls.robustnessPanelTitle')}
          >
            <div className="summary-block__header">
              <div>
                <h3 className="summary-block__title">{btr(language, 'riskControls.robustnessCard')}</h3>
              </div>
              <div className="product-chip-list product-chip-list--tight">
                <span
                  className="product-chip"
                  data-linked-highlight={activeRobustnessKey ? 'true' : undefined}
                >
                  {btr(language, 'riskControls.averageCoverage', { value: pct(averageCoverage * 100) })}
                </span>
              </div>
            </div>
            <div className="space-y-2.5">
              {robustnessLensRows.map((row) => (
                <div
                  key={`dashboard-${row.key}`}
                  className={`rounded-[1rem] px-3 py-2.5 transition-colors ${
                    activeRobustnessKey === row.key ? 'bg-[rgba(125,211,252,0.18)]' : 'bg-[rgba(15,23,42,0.18)]'
                  } focus:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(125,211,252,0.45)]`}
                  data-linked-highlight={activeRobustnessKey === row.key ? 'true' : undefined}
                  data-testid={`dashboard-robustness-row-${row.key}`}
                  tabIndex={0}
                  aria-label={`${row.label} ${row.summary} ${row.detail}`}
                  aria-describedby={hoveredRobustnessRow?.key === row.key ? 'dashboard-robustness-hover-tooltip' : undefined}
                  onMouseEnter={() => activateRobustnessRow(row)}
                  onMouseLeave={clearRobustnessRow}
                  onFocus={() => activateRobustnessRow(row)}
                  onBlur={clearRobustnessRow}
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="metric-card__label">{row.label}</p>
                    <span className="product-chip">{row.state}</span>
                  </div>
                  <p className="mt-1 preview-card__text">{row.summary}</p>
                  <p className="text-[11px] text-secondary">{row.detail}</p>
                </div>
              ))}
            </div>
            {hoveredRobustnessRow ? (
              <div
                className="relative z-10 mt-3 rounded-[0.9rem] border border-[rgba(125,211,252,0.28)] bg-[rgba(15,23,42,0.42)] px-3 py-2 text-[11px] text-secondary shadow-[0_12px_32px_rgba(15,23,42,0.18)] transition-all duration-150 ease-out motion-reduce:transition-none"
                data-testid="dashboard-robustness-hover-tooltip"
                id="dashboard-robustness-hover-tooltip"
                role="tooltip"
              >
                <span className="text-foreground">{hoveredRobustnessRow.label}</span>
                <span className="ml-1">{hoveredRobustnessRow.summary}</span>
                <span className="ml-1">{hoveredRobustnessRow.detail}</span>
              </div>
            ) : null}
          </div>
        ) : null}
        {riskControlRows.length ? (
          <div
            className="summary-block"
            data-testid="dashboard-risk-controls-panel"
            title={btr(language, 'riskControls.riskControlPanelTitle')}
          >
            <div className="summary-block__header">
              <div>
                <h3 className="summary-block__title">{btr(language, 'riskControls.riskControlCard')}</h3>
              </div>
              <div className="product-chip-list product-chip-list--tight">
                <span className="product-chip">{btr(language, 'riskControls.enabledCount', { count: riskControlRows.length })}</span>
                <span
                  className="product-chip"
                  data-linked-highlight={activeRiskControlKey ? 'true' : undefined}
                  data-testid="dashboard-risk-controls-threshold-summary"
                >
                  {btr(language, 'riskControls.highestThreshold', { value: strongestRiskControl.toFixed(2) })}
                </span>
              </div>
            </div>
            <div className="space-y-2.5">
              {riskControlRows.map((row) => (
                <div
                  key={`dashboard-risk-${row.key}`}
                  className={`rounded-[1rem] px-3 py-2.5 transition-colors ${
                    activeRiskControlKey === row.key ? 'bg-[rgba(125,211,252,0.18)]' : 'bg-[rgba(15,23,42,0.18)]'
                  } focus:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(125,211,252,0.45)]`}
                  data-linked-highlight={activeRiskControlKey === row.key ? 'true' : undefined}
                  data-testid={`dashboard-risk-controls-row-${row.key}`}
                  tabIndex={0}
                  aria-label={`${row.label} ${row.valueLabel}`}
                  aria-describedby={hoveredRiskControlRow?.key === row.key ? 'dashboard-risk-controls-hover-tooltip' : undefined}
                  onMouseEnter={() => activateRiskControlRow(row)}
                  onMouseLeave={clearRiskControlRow}
                  onFocus={() => activateRiskControlRow(row)}
                  onBlur={clearRiskControlRow}
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="metric-card__label">{row.label}</p>
                    <span className="preview-card__text">{row.valueLabel}</span>
                  </div>
                </div>
              ))}
            </div>
            {hoveredRiskControlRow ? (
              <div
                className="relative z-10 mt-3 rounded-[0.9rem] border border-[rgba(125,211,252,0.28)] bg-[rgba(15,23,42,0.42)] px-3 py-2 text-[11px] text-secondary shadow-[0_12px_32px_rgba(15,23,42,0.18)] transition-all duration-150 ease-out motion-reduce:transition-none"
                data-testid="dashboard-risk-controls-hover-tooltip"
                id="dashboard-risk-controls-hover-tooltip"
                role="tooltip"
              >
                <span className="text-foreground">{btr(language, 'riskControls.threshold', { label: hoveredRiskControlRow.label })}</span>
                <span className="ml-1 font-mono text-foreground">{hoveredRiskControlRow.valueLabel}</span>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}

type BacktestChartWorkspaceProps = {
  run: RuleBacktestRunResponse;
  normalized: DeterministicBacktestNormalizedResult;
  densityConfig: DeterministicResultDensityConfig;
  hasRobustnessAnalysis: boolean;
  robustnessLensRows: CoverageTrackItem[];
  riskControlRows: RiskControlVisualRow[];
  activeRobustnessKey: string | null;
  activeRiskControlKey: RiskControlVisualRow['key'] | null;
  onActiveRobustnessChange: (key: string | null) => void;
  onActiveRiskControlChange: (key: RiskControlVisualRow['key'] | null) => void;
};

const BacktestChartWorkspace: React.FC<BacktestChartWorkspaceProps> = ({
  run,
  normalized,
  densityConfig,
  hasRobustnessAnalysis,
  robustnessLensRows,
  riskControlRows,
  activeRobustnessKey,
  activeRiskControlKey,
  onActiveRobustnessChange,
  onActiveRiskControlChange,
}) => (
  <>
    <section className="backtest-display-section backtest-result-page__dashboard-stage" data-testid="deterministic-result-page-dashboard-stage">
      <DeterministicBacktestResultView run={run} normalized={normalized} densityConfig={densityConfig} />
    </section>
    <AdditiveDashboardPanels
      hasRobustnessAnalysis={hasRobustnessAnalysis}
      robustnessLensRows={robustnessLensRows}
      riskControlRows={riskControlRows}
      activeRobustnessKey={activeRobustnessKey}
      activeRiskControlKey={activeRiskControlKey}
      onActiveRobustnessChange={onActiveRobustnessChange}
      onActiveRiskControlChange={onActiveRiskControlChange}
    />
  </>
);

export default BacktestChartWorkspace;
