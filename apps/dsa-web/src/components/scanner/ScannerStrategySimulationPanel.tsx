import { Clock, Play } from 'lucide-react';
import type { ScannerStrategySimulationResult } from '../../types/scanner';
import { ScannerActionButton } from './ScannerActionButton';

function parseFirstNumericValue(value?: string | null): number | null {
  if (!value) return null;
  const matched = value.match(/-?\d+(?:\.\d+)?/);
  if (!matched) return null;
  const parsed = Number(matched[0]);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatPercent(value?: number | null): string {
  if (value == null || !Number.isFinite(value)) return '--';
  return `${value > 0 ? '+' : ''}${value.toFixed(1)}%`;
}

function formatMetricNumber(value?: number | null, digits = 2): string {
  if (value == null || !Number.isFinite(value)) return '--';
  return value.toFixed(digits);
}

function simulationToneClass(value?: number | null): string {
  if (value == null || !Number.isFinite(value)) return 'font-mono text-white/50';
  return value >= 0
    ? 'font-mono text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.4)]'
    : 'font-mono text-rose-400 drop-shadow-[0_0_8px_rgba(251,113,133,0.4)]';
}

function formatRatio(value?: number | null): string {
  if (value == null || !Number.isFinite(value)) return '--';
  return `${(value * 100).toFixed(0)}%`;
}

export function ScannerStrategySimulationPanel({
  language,
  lookbackDays,
  forwardDays,
  onLookbackDaysChange,
  onForwardDaysChange,
  onRun,
  result,
  isLoading,
  error,
  disabled,
}: {
  language: 'zh' | 'en';
  lookbackDays: number;
  forwardDays: number;
  onLookbackDaysChange: (value: number) => void;
  onForwardDaysChange: (value: number) => void;
  onRun: () => void;
  result: ScannerStrategySimulationResult | null;
  isLoading: boolean;
  error?: string | null;
  disabled: boolean;
}) {
  const statusLabel = result?.status === 'ready'
    ? (language === 'en' ? 'ready' : '就绪')
    : result?.status === 'partial'
      ? (language === 'en' ? 'partial' : '部分')
      : result?.status === 'insufficient_history'
        ? (language === 'en' ? 'insufficient history' : '历史不足')
        : result?.status === 'failed'
          ? (language === 'en' ? 'failed' : '失败')
          : (language === 'en' ? 'idle' : '待运行');
  const summary = result?.summary;
  const compactMessage = disabled
    ? (language === 'en' ? 'Run one scan first, then inspect strategy history.' : '先运行一次扫描，再查看策略历史模拟')
    : result?.status === 'insufficient_history'
      ? (result.warnings[0] || (language === 'en' ? `Insufficient scans · ${result.window.runCount} comparable runs` : `历史扫描不足 · 当前只有 ${result.window.runCount} 次可比较运行`))
      : null;

  return (
    <section
      data-testid="scanner-strategy-simulation"
      className="rounded-xl border border-white/5 bg-white/[0.015] p-3 text-xs"
    >
      <div className="flex min-w-0 items-center gap-2">
        <Clock className="h-3.5 w-3.5 text-white/38" aria-hidden="true" />
        <h3 className="truncate text-[10px] font-bold uppercase tracking-widest text-white/40">
          {language === 'en' ? `History sim · ${lookbackDays}D · Forward ${forwardDays}D` : `历史模拟 · 回看 ${lookbackDays}D · 持有 ${forwardDays}D`}
        </h3>
      </div>
      <div className="mt-2 grid gap-3" data-testid="scanner-strategy-simulation-body">
        <div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
          <div className="min-w-0">
            <span className="mb-1 block text-[10px] font-bold uppercase tracking-widest text-white/40">{language === 'en' ? 'Lookback' : '回看'}</span>
            <div className="ui-scroll-x-quiet flex gap-1 rounded-lg border border-white/5 bg-black/30 p-0.5">
              {[30, 90, 180].map((value) => (
                <button
                  key={value}
                  type="button"
                  className={`shrink-0 rounded-md px-2.5 py-1 font-mono text-[11px] ${lookbackDays === value ? 'bg-white/10 text-white' : 'text-white/45 hover:text-white/75'}`}
                  onClick={() => onLookbackDaysChange(value)}
                >
                  {value}D
                </button>
              ))}
            </div>
          </div>
          <div className="min-w-0">
            <span className="mb-1 block text-[10px] font-bold uppercase tracking-widest text-white/40">{language === 'en' ? 'Forward' : '持有'}</span>
            <div className="ui-scroll-x-quiet flex gap-1 rounded-lg border border-white/5 bg-black/30 p-0.5">
              {[1, 5, 10, 20].map((value) => (
                <button
                  key={value}
                  type="button"
                  className={`shrink-0 rounded-md px-2.5 py-1 font-mono text-[11px] ${forwardDays === value ? 'bg-white/10 text-white' : 'text-white/45 hover:text-white/75'}`}
                  onClick={() => onForwardDaysChange(value)}
                >
                  {value}D
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-end">
            <ScannerActionButton
              label={isLoading ? (language === 'en' ? 'Running' : '运行中') : (language === 'en' ? 'Run sim' : '运行模拟')}
              icon={<Play className="h-3.5 w-3.5" />}
              onClick={onRun}
              disabled={disabled || isLoading}
              variant="primary"
            />
          </div>
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-2 rounded-lg border border-white/5 bg-black/20 px-3 py-2">
          <span className="text-[10px] font-bold uppercase tracking-widest text-white/40">{language === 'en' ? 'Status' : '状态'}</span>
          <span className="font-mono text-white/72" data-testid="scanner-strategy-simulation-status">{statusLabel}</span>
          {compactMessage ? <span className="min-w-0 truncate text-white/50" data-testid="scanner-strategy-simulation-compact-message">{compactMessage}</span> : null}
          {error ? <span className="min-w-0 truncate text-rose-300" data-testid="scanner-strategy-simulation-error">{error}</span> : null}
        </div>
        {summary && result?.status !== 'insufficient_history' ? (
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-6" data-testid="scanner-strategy-simulation-summary">
            {[
              [language === 'en' ? 'Runs' : '历史批次', String(summary.historicalRuns)],
              [language === 'en' ? 'Events' : '入选事件', String(summary.selectionEvents)],
              [language === 'en' ? 'Avg fwd' : '平均远期', formatPercent(summary.avgForwardReturnPct)],
              [language === 'en' ? 'Hit' : '命中率', formatRatio(summary.hitRate)],
              [language === 'en' ? 'Excess' : '超额', formatPercent(summary.avgExcessReturnPct)],
              [language === 'en' ? 'Coverage' : '覆盖率', formatRatio(summary.dataCoverage)],
            ].map(([label, value]) => (
              <div key={label} className="min-w-0 rounded-xl border border-white/5 bg-black/20 px-3 py-2">
                <span className="block truncate text-[10px] font-bold uppercase tracking-widest text-white/40">{label}</span>
                <span className={`${String(label).includes('Avg') || String(label).includes('Excess') || String(label).includes('平均') || String(label).includes('超额') ? simulationToneClass(parseFirstNumericValue(value)) : 'font-mono text-white/78'} block truncate text-sm`}>{value}</span>
              </div>
            ))}
          </div>
        ) : null}
        {result?.warnings.length ? (
          <div className="grid gap-1 rounded-lg border border-amber-300/10 bg-amber-300/[0.04] px-3 py-2 text-[11px] text-amber-100/70" data-testid="scanner-strategy-simulation-warnings">
            {result.warnings.map((warning) => <span key={warning} className="truncate">{warning}</span>)}
          </div>
        ) : null}
        {result?.runs.length ? (
          <div className="overflow-x-auto no-scrollbar rounded-xl border border-white/5 bg-white/[0.02]" data-testid="scanner-strategy-simulation-runs">
            <table className="min-w-[720px] w-full text-left text-[11px]">
              <thead className="border-b border-white/5 text-[10px] uppercase tracking-widest text-white/40">
                <tr>
                  <th className="px-2 py-2">Run</th>
                  <th className="px-2 py-2">{language === 'en' ? 'Selected' : '入选'}</th>
                  <th className="px-2 py-2">{language === 'en' ? 'Rejected' : '淘汰'}</th>
                  <th className="px-2 py-2">{language === 'en' ? 'Symbols' : '标的'}</th>
                  <th className="px-2 py-2">Forward</th>
                  <th className="px-2 py-2">Benchmark</th>
                  <th className="px-2 py-2">Excess</th>
                </tr>
              </thead>
              <tbody>
                {result.runs.map((item) => (
                  <tr key={item.runId} className="border-b border-white/5 text-white/62">
                    <td className="px-2 py-2 font-mono text-white">#{item.runId}</td>
                    <td className="px-2 py-2 font-mono">{item.selectedCount}</td>
                    <td className="px-2 py-2 font-mono">{item.rejectedCount}</td>
                    <td className="max-w-[180px] truncate px-2 py-2 font-mono text-white/72" title={item.selectedSymbols.join(', ')}>{item.selectedSymbols.join(', ') || '--'}</td>
                    <td className={`px-2 py-2 ${simulationToneClass(item.avgForwardReturnPct)}`}>{formatPercent(item.avgForwardReturnPct)}</td>
                    <td className={`px-2 py-2 ${simulationToneClass(item.benchmarkReturnPct)}`}>{formatPercent(item.benchmarkReturnPct)}</td>
                    <td className={`px-2 py-2 ${simulationToneClass(item.excessReturnPct)}`}>{formatPercent(item.excessReturnPct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        {result?.symbols.length ? (
          <div className="overflow-x-auto no-scrollbar rounded-xl border border-white/5 bg-white/[0.02]" data-testid="scanner-strategy-simulation-symbols">
            <table className="min-w-[680px] w-full text-left text-[11px]">
              <thead className="border-b border-white/5 text-[10px] uppercase tracking-widest text-white/40">
                <tr>
                  <th className="px-2 py-2">Symbol</th>
                  <th className="px-2 py-2">{language === 'en' ? 'Count' : '次数'}</th>
                  <th className="px-2 py-2">Score</th>
                  <th className="px-2 py-2">Forward</th>
                  <th className="px-2 py-2">Hit</th>
                  <th className="px-2 py-2">Best</th>
                  <th className="px-2 py-2">Worst</th>
                </tr>
              </thead>
              <tbody>
                {result.symbols.map((item) => (
                  <tr key={item.symbol} className="border-b border-white/5 text-white/62">
                    <td className="px-2 py-2 font-mono text-white">{item.symbol}</td>
                    <td className="px-2 py-2 font-mono">{item.selectionCount}</td>
                    <td className="px-2 py-2 font-mono">{formatMetricNumber(item.avgScore, 1)}</td>
                    <td className={`px-2 py-2 ${simulationToneClass(item.avgForwardReturnPct)}`}>{formatPercent(item.avgForwardReturnPct)}</td>
                    <td className="px-2 py-2 font-mono">{formatRatio(item.hitRate)}</td>
                    <td className={`px-2 py-2 ${simulationToneClass(item.bestForwardReturnPct)}`}>{formatPercent(item.bestForwardReturnPct)}</td>
                    <td className={`px-2 py-2 ${simulationToneClass(item.worstForwardReturnPct)}`}>{formatPercent(item.worstForwardReturnPct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </section>
  );
}
