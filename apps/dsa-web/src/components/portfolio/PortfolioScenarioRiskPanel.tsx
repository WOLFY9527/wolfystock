import { useEffect, useMemo, useState } from 'react';
import { Input, PillBadge, Select } from '../common';
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
} from '../terminal';

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

const FIELD_LABEL_CLASS = '!mb-1 text-[11px] font-medium tracking-normal text-white/55';
const INPUT_CLASS = 'h-10 rounded-lg border-white/10 bg-white/[0.02] px-3 py-2.5 text-sm text-white placeholder:text-white/20 outline-none focus:border-emerald-500/50';
const SELECT_CLASS = 'min-w-0';

function formatSignedAmount(value?: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '--';
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
    signDisplay: 'always',
  }).format(value);
}

function formatPercent(value?: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '--';
  return `${new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 1,
  }).format(value)}%`;
}

function formatDecimal(value?: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '--';
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value);
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
  const [selectedSymbol, setSelectedSymbol] = useState<string>(positions[0]?.symbol ?? '');
  const [mappingLabel, setMappingLabel] = useState('');
  const [shockPercent, setShockPercent] = useState('');
  const [shockError, setShockError] = useState<string | null>(null);
  const [mappingError, setMappingError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<PortfolioScenarioRiskResponse | null>(null);

  const symbolOptions = useMemo(
    () => positions.map((position) => ({ value: position.symbol, label: position.symbol })),
    [positions],
  );
  const scenarioResult = result?.scenarios?.[0] ?? null;
  const warningRows = [
    ...(result?.insufficientDataReasons ?? []),
    ...(result?.missingDataWarnings ?? []),
    ...(scenarioResult?.warnings ?? []),
  ];
  const metadataRows = [
    result?.metadata?.noBrokerSync ? (isEnglish ? 'No broker sync' : '不触发经纪商同步') : null,
    result?.metadata?.noAccountingMutation ? (isEnglish ? 'No accounting mutation' : '不改动账务结果') : null,
    result?.metadata?.noOrderPlacement ? (isEnglish ? 'No order placement' : '不触发任何下单') : null,
    result?.metadata?.notInvestmentAdvice ? (isEnglish ? 'Not investment advice' : '不构成投资建议') : null,
  ].filter(Boolean) as string[];

  useEffect(() => {
    if (!selectedSymbol && positions[0]?.symbol) {
      setSelectedSymbol(positions[0].symbol);
    }
  }, [positions, selectedSymbol]);

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

    if (!snapshotAsOf || !hasPositions || !selectedSymbol) {
      setSubmitError(isEnglish ? 'Visible holdings are not ready for scenario projection.' : '当前可见持仓尚未准备好，暂时无法推演。');
      return;
    }

    const targetLabel = scenarioKind === 'symbol' ? selectedSymbol : trimmedLabel;
    const payload: PortfolioScenarioRiskRequest = {
      asOf: snapshotAsOf,
      positions: toScenarioPositions(positions),
      exposures: scenarioKind === 'symbol'
        ? []
        : [
          {
            symbol: selectedSymbol,
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
      className="border-white/[0.05] bg-white/[0.02]"
    >
      <div data-testid="portfolio-scenario-risk-panel" className="flex flex-col gap-4">
        <TerminalNotice variant="neutral">
          {isEnglish
            ? 'Advisory-only projection. It reads current visible holdings and does not refresh providers, broker state, or accounting.'
            : '仅做观察性推演：读取当前页面可见持仓，不刷新外部数据，不触发经纪商或账务动作。'}
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
                value={selectedSymbol}
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
                  placeholder={isEnglish ? 'Example: QQQ or AI_THEME' : '例如：QQQ / AI_THEME'}
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
            className="min-w-0 flex flex-col gap-4 border-white/[0.05] bg-black/15"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/40">
                  {isEnglish ? 'Estimated impact' : '预估影响'}
                </h3>
                <p className="mt-1 text-sm text-white/45">
                  {isEnglish
                    ? 'Coverage and missing mappings stay explicit. No hidden exposure is inferred.'
                    : '覆盖范围与缺口会显式展示，不会替你推断缺失暴露。'}
                </p>
              </div>
              <div className="text-right">
                <div className="font-mono text-xl text-white">{formatPercent(scenarioResult.portfolioImpactPct)}</div>
                <div className="mt-1 text-xs text-white/45">{formatSignedAmount(scenarioResult.portfolioImpactAmount)}</div>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-xl border border-white/[0.03] bg-black/20 px-3 py-3">
                <div className="text-[10px] font-bold uppercase tracking-widest text-white/40">{isEnglish ? 'Coverage' : '覆盖情况'}</div>
                <div className="mt-2 text-sm text-white">{formatPercent(scenarioResult.coveredWeight != null ? scenarioResult.coveredWeight * 100 : null)}</div>
                <div className="mt-1 text-xs text-white/45">
                  {isEnglish ? 'Covered market value' : '覆盖市值'} {formatDecimal(scenarioResult.coveredMarketValue)}
                </div>
              </div>
              <div className="rounded-xl border border-white/[0.03] bg-black/20 px-3 py-3">
                <div className="text-[10px] font-bold uppercase tracking-widest text-white/40">{isEnglish ? 'Visible positions' : '可见持仓'}</div>
                <div className="mt-2 text-sm text-white">{result.coverage.totalPositions ?? positions.length}</div>
                <div className="mt-1 text-xs text-white/45">
                  {isEnglish ? 'Usable weight rows' : '有效权重行'} {result.coverage.positionsWithUsableWeight ?? '--'}
                </div>
              </div>
              <div className="rounded-xl border border-white/[0.03] bg-black/20 px-3 py-3">
                <div className="text-[10px] font-bold uppercase tracking-widest text-white/40">{isEnglish ? 'Explicit mappings' : '显式映射'}</div>
                <div className="mt-2 text-sm text-white">{isEnglish ? `${result.coverage.explicitExposureRows ?? 0} rows` : `${result.coverage.explicitExposureRows ?? 0} 行`}</div>
                <div className="mt-1 text-xs text-white/45">
                  {(result.coverage.labelsWithExplicitCoverage ?? []).join(', ') || (isEnglish ? 'Current run only' : '仅当前输入')}
                </div>
              </div>
              <div className="rounded-xl border border-white/[0.03] bg-black/20 px-3 py-3">
                <div className="text-[10px] font-bold uppercase tracking-widest text-white/40">{isEnglish ? 'Scenario read model' : '只读模型'}</div>
                <div className="mt-2 text-sm text-white">{result.readModelType || '--'}</div>
                <div className="mt-1 text-xs text-white/45">{result.asOf || snapshotAsOf || '--'}</div>
              </div>
            </div>

            {warningRows.length ? (
              <div className="flex flex-wrap gap-1.5">
                {warningRows.map((warning) => (
                  <PillBadge key={warning} variant="warning" className="normal-case tracking-normal text-white/70">
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
              <div className="rounded-xl border border-white/[0.03] bg-black/20 px-3 py-3">
                <div className="text-[10px] font-bold uppercase tracking-widest text-white/40">
                  {isEnglish ? 'Contribution rows' : '贡献拆解'}
                </div>
                <div className="mt-2 flex flex-col gap-2">
                  {(scenarioResult.positionContributions ?? []).map((entry) => (
                    <div key={`${scenarioResult.name}-${entry.symbol}`} className="flex items-start justify-between gap-3 rounded-lg border border-white/[0.04] bg-white/[0.02] px-3 py-2">
                      <div className="min-w-0">
                        <div className="font-medium text-white">{entry.symbol}</div>
                        <div className="mt-1 text-xs text-white/45">
                          {entry.bucket || '--'}
                          {' · '}
                          {formatPercent(entry.weight != null ? entry.weight * 100 : null)}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-mono text-sm text-white">{formatPercent(entry.impactPct)}</div>
                        <div className="mt-1 text-xs text-white/45">{formatSignedAmount(entry.impactAmount)}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-xl border border-white/[0.03] bg-black/20 px-3 py-3">
                <div className="text-[10px] font-bold uppercase tracking-widest text-white/40">
                  {isEnglish ? 'Advisory boundaries' : '观察边界'}
                </div>
                <div className="mt-2 flex flex-col gap-2 text-sm text-white/72">
                  {metadataRows.map((row) => (
                    <div key={row} className="rounded-lg border border-white/[0.04] bg-white/[0.02] px-3 py-2">
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
