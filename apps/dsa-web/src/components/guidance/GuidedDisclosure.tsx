import type React from 'react';
import { ChevronDown, Layers3 } from 'lucide-react';
import { cn } from '../../utils/cn';

export type GuidedDisclosureProps = {
  title: string;
  summary: string;
  beginner: React.ReactNode;
  professional: React.ReactNode;
  defaultOpen?: boolean;
  className?: string;
};

export function GuidedDisclosure({
  title,
  summary,
  beginner,
  professional,
  defaultOpen = false,
  className,
}: GuidedDisclosureProps) {
  return (
    <details
      className={cn(
        'group rounded-[16px] border border-white/5 bg-white/[0.02] backdrop-blur-md',
        'transition-colors open:border-cyan-200/15 open:bg-[var(--wolfy-surface-input)]',
        className,
      )}
      open={defaultOpen}
    >
      <summary
        className={cn(
          'flex min-h-[56px] cursor-pointer list-none items-center gap-3 px-4 py-3 text-left outline-none',
          'focus-visible:ring-2 focus-visible:ring-cyan-300/40 focus-visible:ring-offset-0',
          '[&::-webkit-details-marker]:hidden',
        )}
      >
        <span className="flex size-9 shrink-0 items-center justify-center rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] text-cyan-100/80">
          <Layers3 className="size-4" aria-hidden="true" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{title}</span>
          <span className="mt-1 block text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{summary}</span>
        </span>
        <ChevronDown className="size-4 shrink-0 text-[color:var(--wolfy-text-muted)] transition-transform group-open:rotate-180" aria-hidden="true" />
      </summary>
      <div className="grid gap-3 border-t border-[color:var(--wolfy-border-subtle)] px-4 pb-4 pt-3 md:grid-cols-2">
        <section className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-cyan-100/50">给新手看的解释</p>
          <div className="mt-2 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">{beginner}</div>
        </section>
        <section className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--wolfy-text-muted)]">专业细节</p>
          <div className="mt-2 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">{professional}</div>
        </section>
      </div>
    </details>
  );
}
