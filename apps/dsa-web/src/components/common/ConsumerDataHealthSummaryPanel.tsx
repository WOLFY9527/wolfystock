import type React from 'react';
import { TerminalChip } from '../terminal/TerminalPrimitives';
import { cn } from '../../utils/cn';
import type {
  ConsumerDataHealthState,
  ConsumerDataHealthSummary,
} from '../../utils/consumerDataQualityViewModel';

type ConsumerDataHealthSummaryPanelProps = {
  summary: ConsumerDataHealthSummary;
  title?: string;
  testId?: string;
  className?: string;
};

function variantForState(state: ConsumerDataHealthState): React.ComponentProps<typeof TerminalChip>['variant'] {
  if (state === 'healthy') return 'success';
  if (state === 'partial') return 'info';
  if (state === 'stale') return 'caution';
  if (state === 'degraded') return 'caution';
  if (state === 'unavailable') return 'danger';
  return 'neutral';
}

const ConsumerDataHealthSummaryPanel: React.FC<ConsumerDataHealthSummaryPanelProps> = ({
  summary,
  title = '数据健康',
  testId,
  className,
}) => (
  <section
    data-testid={testId}
    className={cn(
      'rounded-lg border border-white/[0.08] bg-white/[0.025] px-3 py-2.5',
      className,
    )}
  >
    <div className="flex min-w-0 flex-wrap items-center gap-2">
      <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-white/42">
        {title}
      </span>
      <TerminalChip variant={variantForState(summary.overallState)}>
        {summary.items.find((item) => item.state === summary.overallState)?.stateLabel ?? summary.overallState}
      </TerminalChip>
    </div>
    <div className="mt-3 grid min-w-0 gap-2 lg:grid-cols-3">
      {summary.items.map((item) => (
        <article key={item.category} className="min-w-0 rounded-[7px] border border-white/[0.06] bg-white/[0.018] px-3 py-2.5">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <p className="min-w-0 break-words text-xs font-semibold text-white/76">{item.label}</p>
            <TerminalChip variant={variantForState(item.state)}>{item.stateLabel}</TerminalChip>
          </div>
          <p className="mt-2 min-w-0 break-words text-[11px] leading-5 text-white/56">{item.whyItMatters}</p>
          <p className="mt-1 min-w-0 break-words text-[11px] leading-5 text-white/62">{item.confidenceEffect}</p>
          <p className="mt-1 min-w-0 break-words text-[11px] leading-5 text-white/48">{item.nextResearchStep}</p>
        </article>
      ))}
    </div>
  </section>
);

export default ConsumerDataHealthSummaryPanel;
