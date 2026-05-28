import type React from 'react';
import { TerminalDenseList } from '../terminal';
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
}> = ({ testId, title, emptyLabel, items, accentClassName = 'text-white/72' }) => (
  <section
    data-testid={testId}
    className="min-w-0 rounded-xl border border-white/[0.06] bg-black/10 p-3"
  >
    <div className="flex min-w-0 items-center justify-between gap-2">
      <p className="truncate text-[10px] font-bold uppercase tracking-[0.22em] text-white/38">
        {title}
      </p>
      <span className="shrink-0 font-mono text-[10px] text-white/28">{items.length}</span>
    </div>
    {items.length > 0 ? (
      <TerminalDenseList className="mt-3 space-y-2">
        {items.map((item) => (
          <div
            key={item.key}
            className="min-w-0 border-t border-white/[0.04] pt-2 first:border-t-0 first:pt-0"
          >
            <p className={cn('truncate text-sm font-semibold', accentClassName, item.toneClass)}>
              {item.label}
            </p>
            <p className="truncate text-[11px] leading-5 text-white/42">{item.meta}</p>
          </div>
        ))}
      </TerminalDenseList>
    ) : (
      <p className="mt-3 text-[11px] leading-5 text-white/38">{emptyLabel}</p>
    )}
  </section>
);
