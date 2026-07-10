import type React from 'react';
import { TerminalChip } from '../terminal/TerminalPrimitives';
import { cn } from '../../utils/cn';
import type { ScannerTopDownContextView } from '../../api/researchReadiness';

type ScannerTopDownContextStripProps = {
  context: ScannerTopDownContextView;
  title?: string;
  testId?: string;
  className?: string;
};

function variantForTone(
  tone: ScannerTopDownContextView['tone'],
): React.ComponentProps<typeof TerminalChip>['variant'] {
  if (tone === 'success') return 'success';
  if (tone === 'danger') return 'danger';
  if (tone === 'caution') return 'caution';
  if (tone === 'info') return 'info';
  return 'neutral';
}

const ScannerTopDownContextStrip: React.FC<ScannerTopDownContextStripProps> = ({
  context,
  title = '市场驱动因素',
  testId,
  className,
}) => (
  <section
    data-testid={testId}
    className={cn(
      'rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-rail)] px-3 py-2.5',
      className,
    )}
  >
    <div className="flex min-w-0 flex-wrap items-center gap-2">
      <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[color:var(--wolfy-text-muted)]">
        {title}
      </span>
      <TerminalChip variant={variantForTone(context.tone)}>
        {context.postureLabel}
      </TerminalChip>
      {context.chips.map((chip) => (
        <TerminalChip key={chip.key} variant="neutral">
          {chip.label}
        </TerminalChip>
      ))}
    </div>
    <p className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">
      {context.summaryLine}
    </p>
  </section>
);

export default ScannerTopDownContextStrip;
