import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Button, Disclosure, GlassCard, Input } from '../common';
import { getApiErrorMessage } from '../../api/error';
import {
  describeSettingsDuckDBDataMode,
  describeSettingsDuckDBDiagnosticStatus,
  describeSettingsEnabledState,
} from '../../utils/displayStatus';
import {
  quantApi,
  type QuantDuckDBBenchmarkResponse,
  type QuantDuckDBBuildFactorsResponse,
  type QuantDuckDBCompareRuntimeContextResponse,
  type QuantDuckDBCoverageResponse,
  type QuantDuckDBFactorSnapshotResponse,
  type QuantDuckDBHealthResponse,
  type QuantDuckDBInitResponse,
  type QuantDuckDBValidateFactorPathResponse,
} from '../../api/quant';
import { cn } from '../../utils/cn';
import { formatDurationMs, formatNumber } from '../../utils/format';

type DuckDBQuantPanelProps = {
  configEnabledState: 'enabled' | 'disabled' | 'unknown';
};

type ActionKey = 'refresh' | 'init' | 'benchmark' | 'snapshot' | 'validate' | 'compare' | 'build';

const DEFAULT_SYMBOLS = 'AAPL,MSFT';
const DEFAULT_MIN_FACTOR_ROWS = 1;
const DEFAULT_LOOKBACK_DAYS = 5;
const DEFAULT_BENCHMARK_SYMBOL_LIMIT = 2;
const BUTTON_CLASS = 'rounded-lg px-3 py-1.5 text-xs';
const CHIP_CLASS = 'inline-flex items-center rounded-full border px-2 py-1 text-[10px] font-semibold';
const PANEL_CLASS = 'rounded-xl border border-white/5 bg-black/20 px-3 py-3';

function parseSymbolInput(value: string): string[] {
  return Array.from(new Set(
    value
      .split(/[,\s]+/)
      .map((item) => item.trim().toUpperCase())
      .filter(Boolean),
  )).slice(0, 5);
}

function compactPath(value?: string | null): string {
  const text = String(value || '').trim();
  if (!text) return '--';
  const withoutHome = text.replace(/\/Users\/[^/]+/g, '~');
  const parts = withoutHome.split('/').filter(Boolean);
  const compact = parts.length > 2 ? `.../${parts.slice(-2).join('/')}` : withoutHome;
  return compact.length > 48 ? `${compact.slice(0, 18)}...${compact.slice(-24)}` : compact;
}

function formatDateRange(start?: string | null, end?: string | null): string {
  if (!start && !end) return '--';
  if (start && end) return `${start} -> ${end}`;
  return start || end || '--';
}

function formatCount(value?: number | null): string {
  return typeof value === 'number' && Number.isFinite(value) ? formatNumber(value, 0) : '--';
}

function stringifyDetail(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return '{}';
  }
}

function detailWithCompactPaths<T extends { databasePath?: string | null; parquetRoot?: string | null } | null>(value: T): T {
  if (!value) return value;
  return {
    ...value,
    databasePath: compactPath(value.databasePath),
    parquetRoot: compactPath(value.parquetRoot),
  };
}

const MetricTile: React.FC<{ label: string; value: string; detail?: string }> = ({ label, value, detail }) => (
  <div className="min-w-0 rounded-xl border border-white/5 bg-white/[0.02] px-3 py-3">
    <p className="truncate text-[10px] font-semibold uppercase text-white/35">{label}</p>
    <p className="mt-2 truncate text-sm font-semibold text-white tabular-nums">{value}</p>
    {detail ? <p className="mt-1 truncate text-[11px] text-white/45">{detail}</p> : null}
  </div>
);

const SummaryLine: React.FC<{ label: string; value: string; tone?: 'normal' | 'good' | 'warn' | 'muted' }> = ({
  label,
  value,
  tone = 'normal',
}) => (
  <div className="flex min-w-0 items-center justify-between gap-3 rounded-lg bg-white/[0.02] px-2 py-1.5 text-xs">
    <span className="shrink-0 text-white/40">{label}</span>
    <span
      className={cn(
        'min-w-0 truncate text-right tabular-nums',
        tone === 'good' ? 'text-emerald-300' : tone === 'warn' ? 'text-amber-300' : tone === 'muted' ? 'text-white/35' : 'text-white/70',
      )}
    >
      {value}
    </span>
  </div>
);

const DuckDBQuantPanel: React.FC<DuckDBQuantPanelProps> = ({ configEnabledState }) => {
  const [health, setHealth] = useState<QuantDuckDBHealthResponse | null>(null);
  const [coverage, setCoverage] = useState<QuantDuckDBCoverageResponse | null>(null);
  const [benchmark, setBenchmark] = useState<QuantDuckDBBenchmarkResponse | null>(null);
  const [snapshot, setSnapshot] = useState<QuantDuckDBFactorSnapshotResponse | null>(null);
  const [validation, setValidation] = useState<QuantDuckDBValidateFactorPathResponse | null>(null);
  const [comparison, setComparison] = useState<QuantDuckDBCompareRuntimeContextResponse | null>(null);
  const [initResult, setInitResult] = useState<QuantDuckDBInitResponse | null>(null);
  const [buildResult, setBuildResult] = useState<QuantDuckDBBuildFactorsResponse | null>(null);
  const [symbolInput, setSymbolInput] = useState(DEFAULT_SYMBOLS);
  const [busyAction, setBusyAction] = useState<ActionKey | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const explicitSymbols = useMemo(() => parseSymbolInput(symbolInput), [symbolInput]);
  const enabled = health?.enabled ?? configEnabledState === 'enabled';
  const disabled = !enabled;
  const status = health?.status || coverage?.status || (configEnabledState === 'disabled' ? 'disabled' : 'unknown');
  const statusDescriptor = describeSettingsDuckDBDiagnosticStatus(status);
  const dataModeDescriptor = describeSettingsDuckDBDataMode(benchmark?.dataMode || validation?.dataMode || comparison?.dataMode);
  const enabledDescriptor = describeSettingsEnabledState(disabled ? 'disabled' : 'enabled');
  const noWriteLabel = disabled ? '未写入文件' : '写入需显式点击';
  const productionRuntimeChanged = comparison?.diagnostics?.productionRuntimeChanged === true;

  const refreshReadOnly = useCallback(async () => {
    setBusyAction('refresh');
    setMessage(null);
    try {
      const [nextHealth, nextCoverage] = await Promise.all([
        quantApi.getDuckDBHealth(),
        quantApi.getDuckDBCoverage(),
      ]);
      setHealth(nextHealth);
      setCoverage(nextCoverage);
      setMessage('健康与覆盖已刷新');
    } catch (error) {
      setMessage(`刷新失败：${getApiErrorMessage(error)}`);
    } finally {
      setBusyAction(null);
    }
  }, []);

  useEffect(() => {
    void refreshReadOnly();
  }, [refreshReadOnly]);

  const runAction = useCallback(async (action: Exclude<ActionKey, 'refresh'>) => {
    setBusyAction(action);
    setMessage(null);
    try {
      if (action === 'init') {
        if (disabled) {
          setMessage('DuckDB 未启用，初始化已阻止');
          return;
        }
        setInitResult(await quantApi.initDuckDB());
        setMessage('初始化请求完成');
        await refreshReadOnly();
        return;
      }

      if (action === 'benchmark') {
        setBenchmark(await quantApi.runDuckDBBenchmark({ symbolLimit: DEFAULT_BENCHMARK_SYMBOL_LIMIT }));
        setMessage('基准诊断完成');
        return;
      }

      if (!explicitSymbols.length) {
        setMessage('请输入 1-5 个明确标的');
        return;
      }

      if (action === 'snapshot') {
        setSnapshot(await quantApi.getDuckDBFactorSnapshot({
          symbols: explicitSymbols,
          lookbackDays: DEFAULT_LOOKBACK_DAYS,
          factors: ['return_1d', 'factor_score'],
        }));
        setMessage('因子快照完成');
      } else if (action === 'validate') {
        setValidation(await quantApi.validateDuckDBFactorPath({
          symbols: explicitSymbols,
          minFactorRows: DEFAULT_MIN_FACTOR_ROWS,
        }));
        setMessage('因子路径校验完成');
      } else if (action === 'compare') {
        setComparison(await quantApi.compareDuckDBRuntimeContext({
          symbols: explicitSymbols,
          scannerSnapshot: Object.fromEntries(explicitSymbols.map((symbol) => [symbol, { score: 0 }])),
        }));
        setMessage('运行上下文比较完成');
      } else if (action === 'build') {
        if (disabled) {
          setMessage('DuckDB 未启用，构建已阻止');
          return;
        }
        setBuildResult(await quantApi.buildDuckDBFactors({ symbols: explicitSymbols }));
        setMessage('因子构建请求完成');
        await refreshReadOnly();
      }
    } catch (error) {
      setMessage(`动作失败：${getApiErrorMessage(error)}`);
    } finally {
      setBusyAction(null);
    }
  }, [disabled, explicitSymbols, refreshReadOnly]);

  return (
    <GlassCard className="px-4 py-4" data-testid="duckdb-quant-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase text-cyan-300">DuckDB 诊断</p>
          <h3 className="mt-1 text-sm font-semibold text-foreground">可选量化引擎控制面</h3>
          <p className="mt-1 max-w-3xl text-xs leading-5 text-white/45">
            诊断用途，不影响生产运行路径；不会接管扫描器、回测、组合、行情、AI 或通知。
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className={cn(CHIP_CLASS, disabled ? 'border-cyan-300/15 bg-cyan-300/[0.05] text-cyan-200' : 'border-emerald-300/20 bg-emerald-300/[0.06] text-emerald-300')}>
            {enabledDescriptor.label}
          </span>
          <span className={cn(CHIP_CLASS, 'border-white/10 bg-white/[0.03] text-white/50')}>可选能力</span>
          <span className={cn(CHIP_CLASS, 'border-white/10 bg-white/[0.03] text-white/50')}>{noWriteLabel}</span>
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <MetricTile label="状态" value={statusDescriptor.label} detail={dataModeDescriptor.label} />
        <MetricTile label="DB 路径" value={compactPath(health?.databasePath || coverage?.databasePath)} detail="已脱敏 / 截断" />
        <MetricTile label="OHLCV 行" value={formatCount(coverage?.totalOhlcvRows)} detail={`标的 ${formatCount(coverage?.symbolCount)}`} />
        <MetricTile label="因子行" value={formatCount(coverage?.totalFactorRows)} detail={`最新 ${coverage?.latestFactorDate || '--'}`} />
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,0.85fr)]">
        <div className={PANEL_CLASS}>
          <div className="grid gap-2 md:grid-cols-2">
            <SummaryLine label="日期范围" value={formatDateRange(coverage?.minTradeDate, coverage?.maxTradeDate)} />
            <SummaryLine label="覆盖样本" value={coverage?.symbols?.length ? coverage.symbols.map((item) => `${item.symbol}:${item.ohlcvRows}/${item.factorRows}`).join(' · ') : (coverage?.emptyReason || '暂无覆盖样本')} tone={coverage?.symbols?.length ? 'normal' : 'muted'} />
            <SummaryLine label="Benchmark" value={benchmark ? `${formatDurationMs(benchmark.durationMs || benchmark.elapsedMs)} · ${formatCount(benchmark.rowsScanned)} 行 · ${formatCount(benchmark.symbolsScanned)} 标的` : '--'} />
            <SummaryLine label="快照" value={snapshot ? `${describeSettingsDuckDBDiagnosticStatus(snapshot.status).label} · ${formatCount(snapshot.rowCount)} 行 · 缺失 ${snapshot.missingSymbols.length}` : '--'} />
            <SummaryLine label="校验" value={validation ? `${describeSettingsDuckDBDiagnosticStatus(validation.status).label} · 覆盖 ${validation.coverage.coveredSymbols}/${validation.coverage.requestedSymbols} · 不足 ${validation.insufficientSymbols.length}` : '--'} />
            <SummaryLine label="运行比较" value={comparison ? `productionRuntimeChanged=${productionRuntimeChanged ? 'true' : 'false'} · 诊断专用` : 'productionRuntimeChanged=false · 诊断专用'} tone={productionRuntimeChanged ? 'warn' : 'good'} />
          </div>
        </div>

        <div className={PANEL_CLASS}>
          <Input
            label="明确标的"
            value={symbolInput}
            onChange={(event) => setSymbolInput(event.target.value)}
            hint="最多 5 个，逗号或空格分隔"
            className="h-9 text-xs"
          />
          <div className="mt-3 grid grid-cols-2 gap-2">
            <Button type="button" size="sm" variant="settings-secondary" className={BUTTON_CLASS} onClick={() => void refreshReadOnly()} isLoading={busyAction === 'refresh'}>
              刷新
            </Button>
            <Button type="button" size="sm" variant="settings-secondary" className={BUTTON_CLASS} onClick={() => void runAction('benchmark')} isLoading={busyAction === 'benchmark'}>
              小样本基准
            </Button>
            <Button type="button" size="sm" variant="settings-secondary" className={BUTTON_CLASS} onClick={() => void runAction('snapshot')} isLoading={busyAction === 'snapshot'}>
              因子快照
            </Button>
            <Button type="button" size="sm" variant="settings-secondary" className={BUTTON_CLASS} onClick={() => void runAction('validate')} isLoading={busyAction === 'validate'}>
              路径校验
            </Button>
            <Button type="button" size="sm" variant="settings-secondary" className={BUTTON_CLASS} onClick={() => void runAction('compare')} isLoading={busyAction === 'compare'}>
              运行比较
            </Button>
            <Button type="button" size="sm" variant="settings-secondary" className={BUTTON_CLASS} onClick={() => void runAction('init')} disabled={disabled} isLoading={busyAction === 'init'}>
              初始化
            </Button>
            <Button type="button" size="sm" variant="settings-secondary" className={cn(BUTTON_CLASS, 'col-span-2')} onClick={() => void runAction('build')} disabled={disabled || !explicitSymbols.length} isLoading={busyAction === 'build'}>
              显式构建因子
            </Button>
          </div>
          {disabled ? <p className="mt-2 text-[11px] leading-5 text-cyan-200">未启用 / 可选能力 / 未写入文件。</p> : null}
          {message ? <p className="mt-2 text-[11px] leading-5 text-white/45" role="status">{message}</p> : null}
        </div>
      </div>

      <Disclosure
        summary={<span className="text-xs font-semibold text-white/55">开发者细节</span>}
        className="mt-3 rounded-xl border border-white/5 bg-white/[0.02]"
        summaryClassName="px-3 py-2"
        bodyClassName="px-3 pb-3"
      >
        <pre className="max-h-64 overflow-y-auto no-scrollbar whitespace-pre-wrap break-words rounded-lg bg-black/30 p-3 text-[11px] leading-5 text-white/45">
          {stringifyDetail({
            health: detailWithCompactPaths(health),
            coverage: detailWithCompactPaths(coverage),
            benchmark,
            snapshot,
            validation,
            comparison,
            initResult,
            buildResult,
            explicitSymbols,
          })}
        </pre>
      </Disclosure>
    </GlassCard>
  );
};

export default DuckDBQuantPanel;
