import { LineChart, TestTubeDiagonal } from 'lucide-react';
import { Link } from 'react-router-dom';
import { TerminalChip } from '../terminal/TerminalPrimitives';
import { buildLocalizedPath } from '../../utils/localeRouting';
import type {
  ScannerBacktestBatchSource,
  ScannerBacktestItem,
} from './scannerBacktestShared';
import { getScannerBacktestConfig } from './scannerBacktestShared';
import { ScannerActionButton } from './ScannerActionButton';
type Language = 'zh' | 'en';

function formatPercent(value?: number | null): string {
  if (value == null || !Number.isFinite(value)) return '--';
  return `${value > 0 ? '+' : ''}${value.toFixed(1)}%`;
}

function formatMetricNumber(value?: number | null, digits = 2): string {
  if (value == null || !Number.isFinite(value)) return '--';
  return value.toFixed(digits);
}

export function ScannerBacktestLab({
  language,
  items,
  isRunning,
  onRunBatch,
  onCopySymbol,
  counts,
}: {
  language: Language;
  items: ScannerBacktestItem[];
  isRunning: boolean;
  onRunBatch: (source: ScannerBacktestBatchSource) => void;
  onCopySymbol: (symbol: string) => void;
  counts: Record<ScannerBacktestBatchSource, number>;
}) {
  const config = getScannerBacktestConfig();
  const requested = items.length;
  const running = items.filter((item) => item.status === 'queued' || item.status === 'running').length;
  const completed = items.filter((item) => item.status === 'completed').length;
  const failed = items.filter((item) => item.status === 'failed').length;
  const skipped = items.filter((item) => item.status === 'skipped_existing').length;
  const statusText = language === 'en'
    ? `requested ${requested} / running ${running} / completed ${completed} / failed ${failed} / skipped ${skipped}`
    : `请求 ${requested} / 运行 ${running} / 完成 ${completed} / 失败 ${failed} / 复用 ${skipped}`;

  return (
    <section data-testid="scanner-backtest-lab" className="grid gap-3 rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-rail)] p-3 text-xs">
      <div className="flex min-w-0 items-center gap-2">
        <LineChart className="size-3.5 text-[color:var(--wolfy-text-muted)]" aria-hidden="true" />
        <h3 className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{language === 'en' ? 'Backtest Lab' : '回测实验室'}</h3>
      </div>
      <div className="grid gap-3 text-xs">
        <div className="grid gap-2 rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3 sm:grid-cols-2 xl:grid-cols-4">
          {[
            [language === 'en' ? 'Mode' : '模式', language === 'en' ? 'Candidate single-symbol backtest' : '候选单标的回测'],
            [language === 'en' ? 'Range' : '区间', `${config.startDate} - ${config.endDate}`],
            [language === 'en' ? 'Capital' : '资金', String(config.initialCapital)],
            [language === 'en' ? 'Benchmark' : '基准', config.benchmarkMode],
            [language === 'en' ? 'Fee/slip' : '费用/滑点', `${config.feeBps}/${config.slippageBps} bps`],
            [language === 'en' ? 'Strategy' : '策略', language === 'en' ? 'Default MA deterministic template' : '默认均线确定性模板'],
          ].map(([label, value]) => (
            <TerminalChip key={`${label}-${value}`} variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-[color:var(--wolfy-text-secondary)]">
              <span className="shrink-0 text-[color:var(--wolfy-text-muted)]">{label}</span>
              <span className="min-w-0 truncate">{value}</span>
            </TerminalChip>
          ))}
        </div>
        <div className="flex max-w-full flex-wrap gap-1.5">
          <ScannerActionButton label={language === 'en' ? 'Official selected' : '回测官方入选'} icon={<TestTubeDiagonal className="size-3.5" />} onClick={() => onRunBatch('official_selected')} disabled={isRunning || counts.official_selected === 0} variant="secondary" />
          <ScannerActionButton label={language === 'en' ? 'Preview selected' : '回测预览入选'} icon={<TestTubeDiagonal className="size-3.5" />} onClick={() => onRunBatch('preview_selected')} disabled={isRunning || counts.preview_selected === 0} />
          <ScannerActionButton label={language === 'en' ? 'Top 5' : '回测前 5 名'} icon={<TestTubeDiagonal className="size-3.5" />} onClick={() => onRunBatch('top_5')} disabled={isRunning || counts.top_5 === 0} />
          <ScannerActionButton label={language === 'en' ? 'Filtered' : '回测当前筛选'} icon={<TestTubeDiagonal className="size-3.5" />} onClick={() => onRunBatch('current_filter')} disabled={isRunning || counts.current_filter === 0} />
        </div>
        <div className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-2 font-mono text-[11px] text-[color:var(--wolfy-text-muted)]">{statusText}</div>
        {items.length ? (
          <div className="overflow-x-auto no-scrollbar rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-rail)]">
            <table className="min-w-[720px] w-full text-left text-[11px]">
              <thead className="border-b border-[color:var(--wolfy-border-subtle)] text-[10px] uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">
                <tr>
                  <th className="p-2">{language === 'en' ? 'Symbol' : '代码'}</th>
                  <th className="p-2">{language === 'en' ? 'Status' : '状态'}</th>
                  <th className="p-2">{language === 'en' ? 'Return' : '收益'}</th>
                  <th className="p-2">{language === 'en' ? 'Drawdown' : '回撤'}</th>
                  <th className="p-2">{language === 'en' ? 'Sharpe' : '夏普'}</th>
                  <th className="p-2">{language === 'en' ? 'Trades' : '交易'}</th>
                  <th className="p-2">{language === 'en' ? 'Actions' : '操作'}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const resultHref = item.resultId ? buildLocalizedPath(`/backtest/results/${item.resultId}`, language) : null;
                  return (
                    <tr key={item.symbol} className="border-b border-[color:var(--wolfy-border-subtle)] text-[color:var(--wolfy-text-secondary)]">
                      <td className="p-2 font-mono text-[color:var(--wolfy-text-primary)]">{item.symbol}</td>
                      <td className="p-2">{item.status}</td>
                      <td className="p-2 font-mono">{formatPercent(item.totalReturnPct)}</td>
                      <td className="p-2 font-mono">{formatPercent(item.maxDrawdownPct)}</td>
                      <td className="p-2 font-mono">{formatMetricNumber(item.sharpe)}</td>
                      <td className="p-2 font-mono">{item.tradeCount ?? '--'}</td>
                      <td className="p-2">
                        <div className="flex gap-1.5">
                          {resultHref ? <Link className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-2 py-1 text-[color:var(--wolfy-text-secondary)] hover:bg-[var(--wolfy-surface-rail)]" to={resultHref}>{language === 'en' ? 'Report' : '查看报告'}</Link> : null}
                          <button type="button" className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-2 py-1 text-[color:var(--wolfy-text-secondary)] hover:bg-[var(--wolfy-surface-rail)]" onClick={() => onCopySymbol(item.symbol)}>{language === 'en' ? 'Copy' : '复制'}</button>
                        </div>
                        {item.status === 'failed' && item.error ? <p className="mt-1 max-w-[220px] truncate text-[color:var(--state-danger-text)]" title={item.error}>{item.error}</p> : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </section>
  );
}
