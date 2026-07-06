import type React from 'react';
import { TerminalChip } from '../terminal/TerminalPrimitives';
import { cn } from '../../utils/cn';
import type { ConsumerResearchReadinessView } from '../../types/researchReadiness';

type ConsumerResearchReadinessStripProps = {
  readiness: ConsumerResearchReadinessView;
  title?: string;
  testId?: string;
  className?: string;
};

function variantForTone(
  tone: ConsumerResearchReadinessView['tone'],
): React.ComponentProps<typeof TerminalChip>['variant'] {
  if (tone === 'success') return 'success';
  if (tone === 'danger') return 'danger';
  if (tone === 'caution') return 'caution';
  if (tone === 'info') return 'info';
  return 'neutral';
}

const ConsumerResearchReadinessStrip: React.FC<ConsumerResearchReadinessStripProps> = ({
  readiness,
  title = '研究就绪度',
  testId,
  className,
}) => (
  <section
    data-testid={testId}
    className={cn(
      'rounded-lg border border-[color:var(--line)] bg-[var(--wolfy-surface-input)] px-3 py-2.5',
      className,
    )}
  >
    <div className="flex min-w-0 flex-wrap items-center gap-2">
      <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[color:var(--wolfy-text-muted)]">
        {title}
      </span>
      <TerminalChip variant={variantForTone(readiness.tone)}>
        {readiness.verdictLabel}
      </TerminalChip>
      {readiness.chips.map((chip) => (
        <TerminalChip key={chip.key} variant="neutral">
          {chip.label}
        </TerminalChip>
      ))}
    </div>
    <p className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">
      {readiness.summaryLine}
    </p>
  </section>
);

export default ConsumerResearchReadinessStrip;
