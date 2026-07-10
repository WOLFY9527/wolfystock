import { Link } from 'react-router-dom';
import type { ScannerBacktestItem } from './scannerBacktestShared';
import { buildLocalizedPath } from '../../utils/localeRouting';

type Language = 'zh' | 'en';

function formatPercent(value?: number | null): string {
  if (value == null || !Number.isFinite(value)) return '--';
  return `${value > 0 ? '+' : ''}${value.toFixed(1)}%`;
}

function formatMetricNumber(value?: number | null, digits = 2): string {
  if (value == null || !Number.isFinite(value)) return '--';
  return value.toFixed(digits);
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
    <div data-testid={`scanner-backtest-status-${item.symbol}`} className="mt-2 flex min-w-0 flex-wrap items-center gap-1.5 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-2 py-1.5 text-[11px] text-[color:var(--wolfy-text-muted)]">
      <span className="shrink-0 rounded border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-rail)] px-1.5 py-0.5 font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{statusLabel}</span>
      {item.status === 'completed' || item.status === 'skipped_existing' ? (
        <>
          <span className={item.totalReturnPct != null && item.totalReturnPct >= 0 ? 'font-mono text-[color:var(--state-success-text)] ' : 'font-mono text-[color:var(--state-danger-text)] '}>
            {formatPercent(item.totalReturnPct)}
          </span>
          <span className="font-mono text-[color:var(--state-danger-text)]">{formatPercent(item.maxDrawdownPct)}</span>
          <span className="font-mono text-[color:var(--wolfy-text-secondary)]">{formatMetricNumber(item.sharpe)}</span>
          {resultHref ? <Link className="shrink-0 text-blue-200 hover:text-blue-100" to={resultHref}>{language === 'en' ? 'Report' : '查看报告'}</Link> : null}
        </>
      ) : null}
      {item.status === 'failed' && item.error ? <span className="min-w-0 truncate text-[color:var(--state-danger-text)]" title={item.error}>{item.error}</span> : null}
    </div>
  );
}
