import type React from 'react';
import { TerminalDenseList } from '../terminal/TerminalPrimitives';
import { cn } from '../../utils/cn';

export type SynthesisEvidenceItem = {
  key: string;
  label: string;
  meta: string;
  toneClass?: string;
};

export const SynthesisEvidenceColumn: React.FC<{
  testId: string;
  title: string;
  emptyLabel: string;
  items: SynthesisEvidenceItem[];
  accentClassName?: string;
}> = ({ testId, title, emptyLabel, items, accentClassName = 'text-[color:var(--wolfy-text-secondary)]' }) => (
  <section
    data-testid={testId}
    className="research-evidence-surface min-w-0 p-3"
  >
    <div className="flex min-w-0 items-center justify-between gap-2">
      <p className="research-evidence-eyebrow truncate text-[10px] font-bold uppercase tracking-[0.22em]">
        {title}
      </p>
      <span className="research-evidence-muted shrink-0 font-mono text-[10px]">{items.length}</span>
    </div>
    {items.length > 0 ? (
      <TerminalDenseList className="mt-3 space-y-2">
        {items.map((item) => (
          <div
            key={item.key}
            className="min-w-0 border-t border-[color:var(--wolfy-border-faint)] pt-2 first:border-t-0 first:pt-0"
          >
            <p className={cn('truncate text-sm font-semibold', accentClassName, item.toneClass)}>
              {item.label}
            </p>
            <p className="research-evidence-muted truncate text-[11px] leading-5">{item.meta}</p>
          </div>
        ))}
      </TerminalDenseList>
    ) : (
      <p className="research-evidence-muted mt-3 text-[11px] leading-5">{emptyLabel}</p>
    )}
  </section>
);
