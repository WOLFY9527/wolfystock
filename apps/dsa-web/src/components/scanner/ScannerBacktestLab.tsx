import type { MouseEvent, ReactNode } from 'react';
import { LineChart, TestTubeDiagonal } from 'lucide-react';
import { Link } from 'react-router-dom';
import { TerminalButton, TerminalChip } from '../terminal';
import { buildLocalizedPath } from '../../utils/localeRouting';
import type {
  ScannerBacktestBatchSource,
  ScannerBacktestItem,
} from './useScannerBacktestLab';
import { getScannerBacktestConfig } from './useScannerBacktestLab';

type Language = 'zh' | 'en';

function formatPercent(value?: number | null): string {
  if (value == null || !Number.isFinite(value)) return '--';
  return `${value > 0 ? '+' : ''}${value.toFixed(1)}%`;
}

function formatMetricNumber(value?: number | null, digits = 2): string {
  if (value == null || !Number.isFinite(value)) return '--';
  return value.toFixed(digits);
}

function BacktestActionButton({
  label,
  icon,
  onClick,
  disabled = false,
  variant = 'compact',
}: {
  label: string;
  icon?: ReactNode;
  onClick?: (event: MouseEvent<HTMLButtonElement>) => void;
  disabled?: boolean;
  variant?: 'secondary' | 'compact';
}) {
  const sizeClass = variant === 'secondary' ? 'px-3 py-1.5 text-xs' : 'px-2.5 py-1 text-xs';
  return (
    <TerminalButton
      type="button"
      variant={variant}
      className={`min-w-0 ${sizeClass}`.trim()}
      onClick={(event) => {
        event.stopPropagation();
        onClick?.(event);
      }}
      disabled={disabled}
    >
      {icon}
      <span className="truncate">{label}</span>
    </TerminalButton>
  );
}

function BacktestFieldChip({ label, value }: { label: string; value: string }) {
  return (
    <TerminalChip variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
      <span className="shrink-0 text-white/36">{label}</span>
      <span className="min-w-0 truncate">{value}</span>
    </TerminalChip>
  );
}

export function ScannerBacktestResultStrip({
  item,
  language,
}: {
  item?: ScannerBacktestItem;
  language: Language;
}) {
  if (!item || item.status === 'idle') return null;
  const statusLabel = {
    queued: language === 'en' ? 'Queued' : '排队',
    running: language === 'en' ? 'Running' : '运行中',
    completed: language === 'en' ? 'Completed' : '完成',
    failed: language === 'en' ? 'Failed' : '失败',
    skipped_existing: language === 'en' ? 'Reused' : '复用',
    idle: language === 'en' ? 'Idle' : '空闲',
  }[item.status];
  const resultHref = item.resultId ? buildLocalizedPath(`/backtest/results/${item.resultId}`, language) : null;
  return (
    <div data-testid={`scanner-backtest-status-${item.symbol}`} className="mt-2 flex min-w-0 flex-wrap items-center gap-1.5 rounded-lg border border-white/5 bg-black/20 px-2 py-1.5 text-[11px] text-white/52">
      <span className="shrink-0 rounded border border-white/10 bg-white/[0.04] px-1.5 py-0.5 font-bold uppercase tracking-widest text-white/45">{statusLabel}</span>
      {item.status === 'completed' || item.status === 'skipped_existing' ? (
        <>
          <span className={item.totalReturnPct != null && item.totalReturnPct >= 0 ? 'font-mono text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.4)]' : 'font-mono text-rose-400 drop-shadow-[0_0_8px_rgba(251,113,133,0.4)]'}>
            {formatPercent(item.totalReturnPct)}
          </span>
          <span className="font-mono text-rose-400 drop-shadow-[0_0_8px_rgba(251,113,133,0.4)]">{formatPercent(item.maxDrawdownPct)}</span>
          <span className="font-mono text-white/70">{formatMetricNumber(item.sharpe)}</span>
          {resultHref ? <Link className="shrink-0 text-blue-200 hover:text-blue-100" to={resultHref}>{language === 'en' ? 'Report' : '查看报告'}</Link> : null}
        </>
      ) : null}
      {item.status === 'failed' && item.error ? <span className="min-w-0 truncate text-rose-300" title={item.error}>{item.error}</span> : null}
    </div>
  );
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
    <section data-testid="scanner-backtest-lab" className="grid gap-3 rounded-xl border border-white/5 bg-white/[0.015] p-3 text-xs">
      <div className="flex min-w-0 items-center gap-2">
        <LineChart className="h-3.5 w-3.5 text-white/38" aria-hidden="true" />
        <h3 className="text-[10px] font-bold uppercase tracking-widest text-white/40">{language === 'en' ? 'Backtest Lab' : '回测实验室'}</h3>
      </div>
      <div className="grid gap-3 text-xs">
        <div className="grid gap-2 rounded-xl border border-white/5 bg-black/20 p-3 sm:grid-cols-2 xl:grid-cols-4">
          <BacktestFieldChip label={language === 'en' ? 'Mode' : '模式'} value={language === 'en' ? 'Candidate single-symbol backtest' : '候选单标的回测'} />
          <BacktestFieldChip label={language === 'en' ? 'Range' : '区间'} value={`${config.startDate} - ${config.endDate}`} />
          <BacktestFieldChip label={language === 'en' ? 'Capital' : '资金'} value={String(config.initialCapital)} />
          <BacktestFieldChip label={language === 'en' ? 'Benchmark' : '基准'} value={config.benchmarkMode} />
          <BacktestFieldChip label={language === 'en' ? 'Fee/slip' : '费用/滑点'} value={`${config.feeBps}/${config.slippageBps} bps`} />
          <BacktestFieldChip label={language === 'en' ? 'Strategy' : '策略'} value={language === 'en' ? 'Default MA deterministic template' : '默认均线确定性模板'} />
        </div>
        <div className="flex max-w-full flex-wrap gap-1.5">
          <BacktestActionButton label={language === 'en' ? 'Official selected' : '回测官方入选'} icon={<TestTubeDiagonal className="h-3.5 w-3.5" />} onClick={() => onRunBatch('official_selected')} disabled={isRunning || counts.official_selected === 0} variant="secondary" />
          <BacktestActionButton label={language === 'en' ? 'Preview selected' : '回测预览入选'} icon={<TestTubeDiagonal className="h-3.5 w-3.5" />} onClick={() => onRunBatch('preview_selected')} disabled={isRunning || counts.preview_selected === 0} />
          <BacktestActionButton label={language === 'en' ? 'Top 5' : '回测前 5 名'} icon={<TestTubeDiagonal className="h-3.5 w-3.5" />} onClick={() => onRunBatch('top_5')} disabled={isRunning || counts.top_5 === 0} />
          <BacktestActionButton label={language === 'en' ? 'Filtered' : '回测当前筛选'} icon={<TestTubeDiagonal className="h-3.5 w-3.5" />} onClick={() => onRunBatch('current_filter')} disabled={isRunning || counts.current_filter === 0} />
        </div>
        <div className="rounded-lg border border-white/5 bg-black/20 px-3 py-2 font-mono text-[11px] text-white/45">{statusText}</div>
        {items.length ? (
          <div className="overflow-x-auto no-scrollbar rounded-xl border border-white/5 bg-white/[0.02]">
            <table className="min-w-[720px] w-full text-left text-[11px]">
              <thead className="border-b border-white/5 text-[10px] uppercase tracking-widest text-white/40">
                <tr>
                  <th className="px-2 py-2">{language === 'en' ? 'Symbol' : '代码'}</th>
                  <th className="px-2 py-2">{language === 'en' ? 'Status' : '状态'}</th>
                  <th className="px-2 py-2">{language === 'en' ? 'Return' : '收益'}</th>
                  <th className="px-2 py-2">{language === 'en' ? 'Drawdown' : '回撤'}</th>
                  <th className="px-2 py-2">{language === 'en' ? 'Sharpe' : '夏普'}</th>
                  <th className="px-2 py-2">{language === 'en' ? 'Trades' : '交易'}</th>
                  <th className="px-2 py-2">{language === 'en' ? 'Actions' : '操作'}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const resultHref = item.resultId ? buildLocalizedPath(`/backtest/results/${item.resultId}`, language) : null;
                  return (
                    <tr key={item.symbol} className="border-b border-white/5 text-white/62">
                      <td className="px-2 py-2 font-mono text-white">{item.symbol}</td>
                      <td className="px-2 py-2">{item.status}</td>
                      <td className="px-2 py-2 font-mono">{formatPercent(item.totalReturnPct)}</td>
                      <td className="px-2 py-2 font-mono">{formatPercent(item.maxDrawdownPct)}</td>
                      <td className="px-2 py-2 font-mono">{formatMetricNumber(item.sharpe)}</td>
                      <td className="px-2 py-2 font-mono">{item.tradeCount ?? '--'}</td>
                      <td className="px-2 py-2">
                        <div className="flex gap-1.5">
                          {resultHref ? <Link className="rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-white/70 hover:bg-white/10" to={resultHref}>{language === 'en' ? 'Report' : '查看报告'}</Link> : null}
                          <button type="button" className="rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-white/70 hover:bg-white/10" onClick={() => onCopySymbol(item.symbol)}>{language === 'en' ? 'Copy' : '复制'}</button>
                        </div>
                        {item.status === 'failed' && item.error ? <p className="mt-1 max-w-[220px] truncate text-rose-300" title={item.error}>{item.error}</p> : null}
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
