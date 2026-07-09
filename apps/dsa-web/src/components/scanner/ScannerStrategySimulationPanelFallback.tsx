import { LineChart } from 'lucide-react';

export function ScannerStrategySimulationPanelFallback({
  language,
}: {
  language: 'zh' | 'en';
}) {
  return (
    <section
      data-testid="scanner-strategy-simulation-loading"
      aria-busy="true"
      className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3 text-xs"
    >
      <div className="flex min-w-0 items-center gap-2">
        <LineChart className="size-3.5 text-[color:var(--wolfy-text-muted)]" aria-hidden="true" />
        <h3 className="truncate text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">
          {language === 'en' ? 'Loading strategy experiment' : '正在加载策略实验'}
        </h3>
      </div>
      <div className="mt-2 grid gap-2">
        <div className="flex min-w-0 flex-wrap items-center gap-2 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-2 text-[11px] text-[color:var(--wolfy-text-muted)]">
          <span className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">
            {language === 'en' ? 'Workspace' : '实验区'}
          </span>
          <span>{language === 'en' ? 'Preparing simulation panel' : '正在准备模拟面板'}</span>
        </div>
        <div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]" aria-hidden="true">
          <div className="h-12 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)]" />
          <div className="h-12 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)]" />
          <div className="h-8 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] sm:self-end" />
        </div>
      </div>
    </section>
  );
}
