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
      className="rounded-xl border border-white/5 bg-white/[0.015] p-3 text-xs"
    >
      <div className="flex min-w-0 items-center gap-2">
        <LineChart className="h-3.5 w-3.5 text-white/38" aria-hidden="true" />
        <h3 className="truncate text-[10px] font-bold uppercase tracking-widest text-white/40">
          {language === 'en' ? 'Loading strategy experiment' : '正在加载策略实验'}
        </h3>
      </div>
      <div className="mt-2 grid gap-2">
        <div className="flex min-w-0 flex-wrap items-center gap-2 rounded-lg border border-white/5 bg-black/20 px-3 py-2 text-[11px] text-white/52">
          <span className="text-[10px] font-bold uppercase tracking-widest text-white/40">
            {language === 'en' ? 'Workspace' : '实验区'}
          </span>
          <span>{language === 'en' ? 'Preparing simulation panel' : '正在准备模拟面板'}</span>
        </div>
        <div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]" aria-hidden="true">
          <div className="h-12 rounded-lg border border-white/5 bg-black/20" />
          <div className="h-12 rounded-lg border border-white/5 bg-black/20" />
          <div className="h-8 rounded-lg border border-white/5 bg-black/20 sm:self-end" />
        </div>
      </div>
    </section>
  );
}
