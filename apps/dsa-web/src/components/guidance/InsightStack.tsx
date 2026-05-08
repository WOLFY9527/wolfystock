import type React from 'react';
import { AlertTriangle, CheckCircle2, Info, Radar, ShieldAlert } from 'lucide-react';
import { cn } from '../../utils/cn';

export type InsightSeverity = 'critical' | 'warning' | 'info' | 'success';

export type InsightItem = {
  id: string;
  severity: InsightSeverity;
  title: string;
  explanation: string;
  detail?: React.ReactNode;
};

export type InsightStackProps = {
  insights: InsightItem[];
  title?: string;
  className?: string;
};

const SEVERITY_META: Record<InsightSeverity, { className: string; label: string; icon: React.ElementType }> = {
  critical: {
    className: 'border-rose-300/20 bg-rose-400/10 text-rose-100',
    label: '重点风险',
    icon: ShieldAlert,
  },
  warning: {
    className: 'border-amber-300/20 bg-amber-300/10 text-amber-100',
    label: '需要观察',
    icon: AlertTriangle,
  },
  info: {
    className: 'border-cyan-200/18 bg-cyan-300/10 text-cyan-100',
    label: '信息',
    icon: Info,
  },
  success: {
    className: 'border-emerald-300/20 bg-emerald-400/10 text-emerald-100',
    label: '已就绪',
    icon: CheckCircle2,
  },
};

export function InsightStack({
  insights,
  title = '优先洞察',
  className,
}: InsightStackProps) {
  const visibleInsights = insights.slice(0, 4);

  return (
    <section className={cn('rounded-[16px] border border-white/5 bg-white/[0.02] p-4 backdrop-blur-md', className)}>
      <div className="flex items-center gap-2">
        <Radar className="h-4 w-4 text-cyan-100/70" aria-hidden="true" />
        <h3 className="text-sm font-semibold text-white/86">{title}</h3>
      </div>
      <ol className="mt-4 space-y-3">
        {visibleInsights.map((insight, index) => {
          const meta = SEVERITY_META[insight.severity];
          const Icon = meta.icon;
          return (
            <li key={insight.id} className="rounded-xl border border-white/[0.04] bg-black/20 p-3">
              <div className="flex min-w-0 items-start gap-3">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-white/8 bg-white/[0.03] font-mono text-xs text-white/48">
                  {index + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <p className="min-w-0 text-sm font-semibold leading-5 text-white">{insight.title}</p>
                    <span className={cn('inline-flex min-h-6 shrink-0 items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] font-semibold', meta.className)}>
                      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                      {meta.label}
                    </span>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-white/64">{insight.explanation}</p>
                  {insight.detail ? <div className="mt-3 text-xs leading-5 text-white/45">{insight.detail}</div> : null}
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
