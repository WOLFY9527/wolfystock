import { useState } from 'react';
import { Input } from '../common/Input';
import { PillBadge } from '../common/PillBadge';
import { Select } from '../common/Select';
import { useI18n } from '../../contexts/UiLanguageContext';
import type {
  PortfolioScenarioRiskRequest,
  PortfolioScenarioRiskResponse,
} from '../../types/portfolio';
import {
  TerminalButton,
  TerminalDisclosure,
  TerminalEmptyState,
  TerminalNotice,
  TerminalPanel,
} from '../terminal/TerminalPrimitives';

type ScenarioKind = 'symbol' | 'index_proxy' | 'theme_proxy';

export interface PortfolioScenarioRiskVisiblePosition {
  symbol: string;
  marketValue?: number | null;
  marketValueBase?: number | null;
  bucketLabel?: string | null;
  currency?: string | null;
}

interface PortfolioScenarioRiskPanelProps {
  snapshotAsOf?: string | null;
  positions: PortfolioScenarioRiskVisiblePosition[];
  onRunScenario: (payload: PortfolioScenarioRiskRequest) => Promise<PortfolioScenarioRiskResponse>;
}

const FIELD_LABEL_CLASS = '!mb-1 text-[11px] font-medium tracking-normal text-[color:var(--wolfy-text-secondary)]';
const INPUT_CLASS = 'h-10 rounded-lg border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-2.5 text-sm text-[color:var(--wolfy-text-primary)] placeholder:text-[color:var(--wolfy-text-muted)] outline-none focus:border-emerald-500/50';
const SELECT_CLASS = 'min-w-0';
const SIGNED_AMOUNT_FORMATTER = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
  signDisplay: 'always',
});
const PERCENT_FORMATTER = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 1,
});
const DECIMAL_FORMATTER = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

type LocalizedCopy = {
  zh: string;
  en: string;
};

const SCENARIO_RISK_OBSERVATION_ONLY: LocalizedCopy = {
  zh: '情景风险仅供观察',
  en: 'Scenario risk is observation-only',
};
const SCENARIO_RISK_LIMITED: LocalizedCopy = {
  zh: '风险读数受限',
  en: 'Risk reading limited',
};
const SCENARIO_RISK_PARTIAL_INPUT: LocalizedCopy = {
  zh: '部分输入缺失',
  en: 'Some inputs missing',
};
const SCENARIO_RISK_NOT_POSITION_ADVICE: LocalizedCopy = {
  zh: '模型结果仅供观察，不作为行动依据。',
  en: 'Model output is for observation only and is not an action basis.',
};
const SCENARIO_RISK_UPDATING: LocalizedCopy = {
  zh: '数据正在准备',
  en: 'Data is being prepared',
};
const SCENARIO_RISK_STALE: LocalizedCopy = {
  zh: '数据可能延迟但仍可观察',
  en: 'Data may be delayed but remains readable',
};
const SCENARIO_RISK_INSUFFICIENT: LocalizedCopy = {
  zh: '证据不足，需补充输入',
  en: 'Insufficient evidence; more input is needed',
};
const SCENARIO_RISK_UNAVAILABLE: LocalizedCopy = {
  zh: '数据暂不可用',
  en: 'Data unavailable',
};
const SCENARIO_RISK_EMPTY: LocalizedCopy = {
  zh: '暂无可推演结果',
  en: 'No scenario result yet',
};
const SCENARIO_RISK_SAMPLE_ONLY: LocalizedCopy = {
  zh: '仅样例结构，不能形成观察',
  en: 'Sample structure only; no observation is formed',
};
const SCENARIO_RISK_OBSERVATION_BOUNDARY: LocalizedCopy = {
  zh: '仅做观察性推演，不改变当前组合状态。',
  en: 'Observation-only projection; current portfolio state is unchanged.',
};

const SCENARIO_RISK_WARNING_LABELS: Record<string, LocalizedCopy> = {
  coverage_partial: SCENARIO_RISK_LIMITED,
  missing_scenario_coverage: SCENARIO_RISK_PARTIAL_INPUT,
  scenario_coverage_incomplete: SCENARIO_RISK_PARTIAL_INPUT,
  theme_mapping_pending: SCENARIO_RISK_PARTIAL_INPUT,
  no_positions: SCENARIO_RISK_EMPTY,
  no_usable_scenario_shocks: SCENARIO_RISK_INSUFFICIENT,
  insufficient: SCENARIO_RISK_INSUFFICIENT,
  insufficient_data: SCENARIO_RISK_INSUFFICIENT,
  unavailable: SCENARIO_RISK_UNAVAILABLE,
  data_unavailable: SCENARIO_RISK_UNAVAILABLE,
  updating: SCENARIO_RISK_UPDATING,
  initializing: SCENARIO_RISK_UPDATING,
  stale: SCENARIO_RISK_STALE,
  delayed: SCENARIO_RISK_STALE,
  empty: SCENARIO_RISK_EMPTY,
  sample: SCENARIO_RISK_SAMPLE_ONLY,
};

function localizedCopy(copy: LocalizedCopy, isEnglish: boolean): string {
  return isEnglish ? copy.en : copy.zh;
}

function normalizeScenarioRiskToken(value: string): string {
  return value.trim().toLowerCase().replace(/[\s.-]+/g, '_');
}

function formatScenarioRiskReadModel(value: string | undefined, isEnglish: boolean): string {
  const token = normalizeScenarioRiskToken(value ?? '');
  if (!token || token.includes('scenario_risk') || token.includes('advisory')) {
    return localizedCopy(SCENARIO_RISK_OBSERVATION_ONLY, isEnglish);
  }
  return localizedCopy(SCENARIO_RISK_LIMITED, isEnglish);
}

function classifyScenarioRiskWarning(value: string, isEnglish: boolean): string | null {
  const token = normalizeScenarioRiskToken(value);
  if (!token) return null;

  const directLabel = SCENARIO_RISK_WARNING_LABELS[token];
  if (directLabel) return localizedCopy(directLabel, isEnglish);

  if (/(advisory|not_trade|investment|order|broker|accounting|mutation|execution)/.test(token)) {
    return localizedCopy(SCENARIO_RISK_NOT_POSITION_ADVICE, isEnglish);
  }
  if (/(updating|initializing|preparing|refreshing)/.test(token)) {
    return localizedCopy(SCENARIO_RISK_UPDATING, isEnglish);
  }
  if (/(stale|delayed|expired)/.test(token)) {
    return localizedCopy(SCENARIO_RISK_STALE, isEnglish);
  }
  if (/(unavailable|disabled|not_configured)/.test(token)) {
    return localizedCopy(SCENARIO_RISK_UNAVAILABLE, isEnglish);
  }
  if (/(empty|no_positions|no_result)/.test(token)) {
    return localizedCopy(SCENARIO_RISK_EMPTY, isEnglish);
  }
  if (/(sample|example|demo)/.test(token)) {
    return localizedCopy(SCENARIO_RISK_SAMPLE_ONLY, isEnglish);
  }
  if (/(insufficient|no_usable|too_few|coverage_gap)/.test(token)) {
    return localizedCopy(SCENARIO_RISK_INSUFFICIENT, isEnglish);
  }
  if (/(missing|incomplete|pending|mapping|input)/.test(token)) {
    return localizedCopy(SCENARIO_RISK_PARTIAL_INPUT, isEnglish);
  }
  return localizedCopy(SCENARIO_RISK_LIMITED, isEnglish);
}

function buildConsumerWarningRows(values: string[], isEnglish: boolean): string[] {
  return Array.from(
    new Set(
      values
        .map((value) => classifyScenarioRiskWarning(value, isEnglish))
        .filter((value): value is string => Boolean(value)),
    ),
  );
}

function formatSignedAmount(value?: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '--';
  return SIGNED_AMOUNT_FORMATTER.format(value);
}

function formatPercent(value?: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '--';
  return `${PERCENT_FORMATTER.format(value)}%`;
}

function formatDecimal(value?: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '--';
  return DECIMAL_FORMATTER.format(value);
}

function buildScenarioName(kind: ScenarioKind, target: string, shockPercentRaw: string): string {
  const slug = target.trim().toLowerCase().replace(/\s+/g, '_');
  const direction = Number(shockPercentRaw) >= 0 ? 'up' : 'down';
  return `${kind}_${slug}_${direction}_${shockPercentRaw.trim()}`;
}

function toScenarioPositions(positions: PortfolioScenarioRiskVisiblePosition[]) {
  const totalMarketValue = positions.reduce((sum, position) => {
    const value = position.marketValueBase ?? position.marketValue ?? 0;
    return sum + (Number.isFinite(value) ? Number(value) : 0);
  }, 0);

  return positions.map((position) => {
    const marketValue = position.marketValueBase ?? position.marketValue ?? 0;
    const weightPct = totalMarketValue > 0 ? Number(((marketValue / totalMarketValue) * 100).toFixed(4)) : undefined;
    return {
      symbol: position.symbol,
      ...(weightPct != null ? { weightPct } : {}),
      marketValue,
      marketValueBase: marketValue,
      ...(position.bucketLabel ? { bucketLabel: position.bucketLabel } : {}),
      ...(position.currency ? { currency: position.currency } : {}),
    };
  });
}

export function PortfolioScenarioRiskPanel({
  snapshotAsOf,
  positions,
  onRunScenario,
}: PortfolioScenarioRiskPanelProps) {
  const { language } = useI18n();
  const isEnglish = language === 'en';
  const hasPositions = positions.length > 0;
  const [scenarioKind, setScenarioKind] = useState<ScenarioKind>('symbol');
  const [selectedSymbol, setSelectedSymbol] = useState('');
  const [mappingLabel, setMappingLabel] = useState('');
  const [shockPercent, setShockPercent] = useState('');
  const [shockError, setShockError] = useState<string | null>(null);
  const [mappingError, setMappingError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<PortfolioScenarioRiskResponse | null>(null);

  const symbolOptions = positions.map((position) => ({ value: position.symbol, label: position.symbol }));
  const effectiveSelectedSymbol = positions.some((position) => position.symbol === selectedSymbol)
    ? selectedSymbol
    : (positions[0]?.symbol ?? '');
  const scenarioResult = result?.scenarios?.[0] ?? null;
  const warningRows = [
    ...(result?.insufficientDataReasons ?? []),
    ...(result?.missingDataWarnings ?? []),
    ...(scenarioResult?.warnings ?? []),
  ];
  const consumerWarningRows = buildConsumerWarningRows(warningRows, isEnglish);
  const metadataRows = [
    result?.metadata?.sideEffectFree
      || result?.metadata?.noBrokerSync
      || result?.metadata?.noAccountingMutation
      || result?.metadata?.noOrderPlacement
      ? localizedCopy(SCENARIO_RISK_OBSERVATION_BOUNDARY, isEnglish)
      : null,
    result?.metadata?.notInvestmentAdvice ? localizedCopy(SCENARIO_RISK_NOT_POSITION_ADVICE, isEnglish) : null,
  ].filter(Boolean) as string[];

  const handleRunScenario = async () => {
    setShockError(null);
    setMappingError(null);
    setSubmitError(null);

    const parsedShock = Number(shockPercent);
    if (!shockPercent.trim() || !Number.isFinite(parsedShock) || Math.abs(parsedShock) > 100) {
      setShockError(isEnglish ? 'Enter a valid shock percent.' : '请填写有效的冲击幅度');
      return;
    }

    const trimmedLabel = mappingLabel.trim();
    if (scenarioKind !== 'symbol' && !trimmedLabel) {
      setMappingError(isEnglish ? 'Enter a coverage label.' : '请填写映射标签');
      return;
    }

    if (!snapshotAsOf || !hasPositions || !effectiveSelectedSymbol) {
      setSubmitError(isEnglish ? 'Visible holdings are not ready for scenario projection.' : '当前可见持仓尚未准备好，暂时无法推演。');
      return;
    }

    const targetLabel = scenarioKind === 'symbol' ? effectiveSelectedSymbol : trimmedLabel;
    const payload: PortfolioScenarioRiskRequest = {
      asOf: snapshotAsOf,
      positions: toScenarioPositions(positions),
      exposures: scenarioKind === 'symbol'
        ? []
        : [
          {
            symbol: effectiveSelectedSymbol,
            label: targetLabel,
            labelType: scenarioKind,
            exposure: 1,
          },
        ],
      scenarioShocks: [
        {
          name: buildScenarioName(scenarioKind, targetLabel, shockPercent),
          shocks: {
            [targetLabel]: scenarioKind === 'symbol'
              ? { shockPct: parsedShock }
              : { shockPct: parsedShock, labelType: scenarioKind },
          },
        },
      ],
    };

    try {
      setRunning(true);
      const response = await onRunScenario(payload);
      setResult(response);
    } catch (error) {
      const message = error instanceof Error && error.message
        ? error.message
        : (isEnglish ? 'Scenario projection is unavailable right now.' : '当前暂时无法完成情景推演。');
      setSubmitError(message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <TerminalDisclosure
      title={isEnglish ? 'Scenario projection' : '查看压力情景'}
      summary={isEnglish ? 'Collapsed by default; uses current visible holdings only.' : '默认折叠，只使用当前页面可见持仓。'}
      data-testid="portfolio-scenario-risk-disclosure"
      className="border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)]"
    >
      <div data-testid="portfolio-scenario-risk-panel" className="flex flex-col gap-4">
        <TerminalNotice variant="neutral">
          {isEnglish
            ? 'Observation-only projection based on current visible holdings; current portfolio state is unchanged.'
            : '仅做观察性推演，基于当前页面可见持仓，不改变当前组合状态。'}
        </TerminalNotice>

        {!hasPositions ? (
          <TerminalEmptyState
            title={isEnglish ? 'No visible holdings yet' : '暂无可推演持仓'}
            data-testid="portfolio-scenario-risk-empty"
          >
            {isEnglish
              ? 'Add or sync holdings first, then run a bounded scenario projection here.'
              : '请先让当前页面出现持仓，再在这里运行受限的情景推演。'}
          </TerminalEmptyState>
        ) : (
          <>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <Select
                label={isEnglish ? 'Scenario type' : '情景类型'}
                labelClassName={FIELD_LABEL_CLASS}
                value={scenarioKind}
                onChange={(value) => {
                  setScenarioKind(value as ScenarioKind);
                  setResult(null);
                  setMappingError(null);
                }}
                options={[
                  { value: 'symbol', label: isEnglish ? 'Symbol shock' : '标的冲击' },
                  { value: 'index_proxy', label: isEnglish ? 'Index proxy shock' : '指数代理冲击' },
                  { value: 'theme_proxy', label: isEnglish ? 'Theme proxy shock' : '主题代理冲击' },
                ]}
                className={SELECT_CLASS}
                controlClassName="rounded-lg"
              />
              <Select
                label={isEnglish ? 'Visible holding' : '可见持仓'}
                labelClassName={FIELD_LABEL_CLASS}
                value={effectiveSelectedSymbol}
                onChange={(value) => {
                  setSelectedSymbol(value);
                  setResult(null);
                }}
                options={symbolOptions}
                className={SELECT_CLASS}
                controlClassName="rounded-lg"
              />
              {scenarioKind !== 'symbol' ? (
                <Input
                  label={isEnglish ? 'Coverage label' : '映射标签'}
                  labelClassName={FIELD_LABEL_CLASS}
                  value={mappingLabel}
                  onChange={(event) => {
                    setMappingLabel(event.target.value);
                    setResult(null);
                  }}
                  placeholder={isEnglish ? 'Example: QQQ or AI theme' : '例如：QQQ / AI 主题'}
                  className={INPUT_CLASS}
                  error={mappingError ?? undefined}
                />
              ) : null}
              <Input
                type="number"
                label={isEnglish ? 'Shock percent (%)' : '冲击幅度（%）'}
                labelClassName={FIELD_LABEL_CLASS}
                value={shockPercent}
                onChange={(event) => {
                  setShockPercent(event.target.value);
                  setResult(null);
                }}
                placeholder={isEnglish ? 'Example: -8' : '例如：-8'}
                className={INPUT_CLASS}
                error={shockError ?? undefined}
              />
            </div>

            {submitError ? <TerminalNotice variant="caution">{submitError}</TerminalNotice> : null}

            <div className="flex flex-wrap gap-2">
              <TerminalButton
                type="button"
                variant="primary"
                className="h-9 px-3"
                onClick={() => void handleRunScenario()}
                disabled={running}
              >
                {running
                  ? (isEnglish ? 'Running...' : '推演中...')
                  : (isEnglish ? 'Run scenario projection' : '运行压力情景')}
              </TerminalButton>
              <TerminalButton
                type="button"
                variant="secondary"
                onClick={() => {
                  setResult(null);
                  setShockError(null);
                  setMappingError(null);
                  setSubmitError(null);
                }}
                disabled={running}
              >
                {isEnglish ? 'Clear result' : '清空结果'}
              </TerminalButton>
            </div>
          </>
        )}

        {result && scenarioResult ? (
          <TerminalPanel
            as="section"
            data-testid="portfolio-scenario-risk-result"
            className="min-w-0 flex flex-col gap-4 border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)]"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="text-[10px] font-bold uppercase tracking-[0.18em] text-[color:var(--wolfy-text-muted)]">
                  {isEnglish ? 'Estimated impact' : '预估影响'}
                </h3>
                <p className="mt-1 text-sm text-[color:var(--wolfy-text-muted)]">
                  {isEnglish
                    ? 'Coverage and missing mappings stay explicit. No hidden exposure is inferred.'
                    : '覆盖范围与缺口会显式展示，不会替你推断缺失暴露。'}
                </p>
              </div>
              <div className="text-right">
                <div className="font-mono text-xl text-[color:var(--wolfy-text-primary)]">{formatPercent(scenarioResult.portfolioImpactPct)}</div>
                <div className="mt-1 text-xs text-[color:var(--wolfy-text-muted)]">{formatSignedAmount(scenarioResult.portfolioImpactAmount)}</div>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-3">
                <div className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{isEnglish ? 'Coverage' : '覆盖情况'}</div>
                <div className="mt-2 text-sm text-[color:var(--wolfy-text-primary)]">{formatPercent(scenarioResult.coveredWeight != null ? scenarioResult.coveredWeight * 100 : null)}</div>
                <div className="mt-1 text-xs text-[color:var(--wolfy-text-muted)]">
                  {isEnglish ? 'Covered market value' : '覆盖市值'} {formatDecimal(scenarioResult.coveredMarketValue)}
                </div>
              </div>
              <div className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-3">
                <div className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{isEnglish ? 'Visible positions' : '可见持仓'}</div>
                <div className="mt-2 text-sm text-[color:var(--wolfy-text-primary)]">{result.coverage.totalPositions ?? positions.length}</div>
                <div className="mt-1 text-xs text-[color:var(--wolfy-text-muted)]">
                  {isEnglish ? 'Usable weight rows' : '有效权重行'} {result.coverage.positionsWithUsableWeight ?? '--'}
                </div>
              </div>
              <div className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-3">
                <div className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{isEnglish ? 'Explicit mappings' : '显式映射'}</div>
                <div className="mt-2 text-sm text-[color:var(--wolfy-text-primary)]">{isEnglish ? `${result.coverage.explicitExposureRows ?? 0} rows` : `${result.coverage.explicitExposureRows ?? 0} 行`}</div>
                <div className="mt-1 text-xs text-[color:var(--wolfy-text-muted)]">
                  {(result.coverage.labelsWithExplicitCoverage ?? []).join(', ') || (isEnglish ? 'Current run only' : '仅当前输入')}
                </div>
              </div>
              <div className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-3">
                <div className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{isEnglish ? 'Scenario status' : '情景风险状态'}</div>
                <div className="mt-2 text-sm text-[color:var(--wolfy-text-primary)]">{formatScenarioRiskReadModel(result.readModelType, isEnglish)}</div>
                <div className="mt-1 text-xs text-[color:var(--wolfy-text-muted)]">{result.asOf || snapshotAsOf || '--'}</div>
              </div>
            </div>

            {consumerWarningRows.length ? (
              <div className="flex flex-wrap gap-1.5">
                {consumerWarningRows.map((warning) => (
                  <PillBadge key={warning} variant="warning" className="normal-case tracking-normal text-[color:var(--wolfy-text-secondary)]">
                    {warning}
                  </PillBadge>
                ))}
              </div>
            ) : null}

            {scenarioResult.missingCoverage?.length ? (
              <div className="rounded-xl border border-amber-300/20 bg-amber-300/5 px-3 py-3">
                <div className="text-[10px] font-bold uppercase tracking-widest text-amber-100/80">
                  {isEnglish ? 'Missing coverage' : '数据不足 / 需补充映射'}
                </div>
                <div className="mt-2 flex flex-col gap-2 text-sm text-amber-100/80">
                  {scenarioResult.missingCoverage.map((entry) => (
                    <div key={`${entry.label}-${entry.labelType || 'plain'}`}>
                      <div className="font-medium">{entry.label}</div>
                      <div className="text-xs text-amber-100/70">
                        {(entry.missingSymbols ?? []).join(', ') || (isEnglish ? 'Coverage details pending' : '缺口明细待补充')}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)]">
              <div className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-3">
                <div className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">
                  {isEnglish ? 'Contribution rows' : '贡献拆解'}
                </div>
                <div className="mt-2 flex flex-col gap-2">
                  {(scenarioResult.positionContributions ?? []).map((entry) => (
                    <div key={`${scenarioResult.name}-${entry.symbol}`} className="flex items-start justify-between gap-3 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-2">
                      <div className="min-w-0">
                        <div className="font-medium text-[color:var(--wolfy-text-primary)]">{entry.symbol}</div>
                        <div className="mt-1 text-xs text-[color:var(--wolfy-text-muted)]">
                          {entry.bucket || '--'}
                          {' · '}
                          {formatPercent(entry.weight != null ? entry.weight * 100 : null)}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-mono text-sm text-[color:var(--wolfy-text-primary)]">{formatPercent(entry.impactPct)}</div>
                        <div className="mt-1 text-xs text-[color:var(--wolfy-text-muted)]">{formatSignedAmount(entry.impactAmount)}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-3">
                <div className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">
                  {isEnglish ? 'Advisory boundaries' : '观察边界'}
                </div>
                <div className="mt-2 flex flex-col gap-2 text-sm text-[color:var(--wolfy-text-secondary)]">
                  {metadataRows.map((row) => (
                    <div key={row} className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-2">
                      {row}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </TerminalPanel>
        ) : null}
      </div>
    </TerminalDisclosure>
  );
}
