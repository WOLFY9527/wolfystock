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
      'rounded-lg border border-[color:var(--line)] bg-[color:var(--surface-2)] px-3 py-2.5',
      className,
    )}
  >
    <div className="flex min-w-0 flex-wrap items-center gap-2">
      <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[color:var(--wolfy-text-muted)]">
        {title}
      </span>
      <TerminalChip variant={variantForState(summary.overallState)}>
        {summary.items.find((item) => item.state === summary.overallState)?.stateLabel ?? summary.overallState}
      </TerminalChip>
    </div>
    <div className="mt-3 grid min-w-0 gap-2 lg:grid-cols-3">
      {summary.items.map((item) => (
        <article key={item.category} className="min-w-0 rounded-[7px] border border-[color:var(--line)] bg-[color:var(--surface)] px-3 py-2.5">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <p className="min-w-0 break-words text-xs font-semibold text-[color:var(--wolfy-text-primary)]">{item.label}</p>
            <TerminalChip variant={variantForState(item.state)}>{item.stateLabel}</TerminalChip>
          </div>
          <p className="mt-2 min-w-0 break-words text-[11px] leading-5 text-[color:var(--wolfy-text-secondary)]">{item.whyItMatters}</p>
          {item.supportingNotes?.length ? (
            <ul className="mt-2 space-y-1">
              {item.supportingNotes.map((note) => (
                <li key={note} className="min-w-0 break-words text-[11px] leading-5 text-[color:var(--wolfy-text-secondary)]">
                  {note}
                </li>
              ))}
            </ul>
          ) : null}
          <p className="mt-1 min-w-0 break-words text-[11px] leading-5 text-[color:var(--wolfy-text-secondary)]">{item.confidenceEffect}</p>
          <p className="mt-1 min-w-0 break-words text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">{item.nextResearchStep}</p>
        </article>
      ))}
    </div>
  </section>
);

export default ConsumerDataHealthSummaryPanel;
