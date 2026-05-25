import type React from 'react';
import { BookOpenText } from 'lucide-react';
import { cn } from '../../utils/cn';

export type MetricNarrativeCardProps = {
  label: string;
  value: React.ReactNode;
  meaning: string;
  freshnessNote: string;
  glossaryTerm?: string;
  tone?: 'positive' | 'negative' | 'caution' | 'info' | 'neutral';
  className?: string;
};

const VALUE_TONE_CLASS: Record<NonNullable<MetricNarrativeCardProps['tone']>, string> = {
  positive: 'text-emerald-300 drop-shadow-[0_0_8px_rgba(52,211,153,0.28)]',
  negative: 'text-rose-300 drop-shadow-[0_0_8px_rgba(251,113,133,0.28)]',
  caution: 'text-amber-200',
  info: 'text-cyan-200',
  neutral: 'text-white',
};

export function MetricNarrativeCard({
  label,
  value,
  meaning,
  freshnessNote,
  glossaryTerm,
  tone = 'neutral',
  className,
}: MetricNarrativeCardProps) {
  return (
    <article
      className={cn(
        'rounded-[16px] border border-white/5 bg-white/[0.02] p-4 backdrop-blur-md',
        'transition-colors hover:border-white/10 hover:bg-white/[0.03]',
        className,
      )}
    >
      <div className="flex min-w-0 items-start justify-between gap-3">
        <p className="min-w-0 text-[11px] font-semibold uppercase tracking-[0.14em] text-white/42">{label}</p>
        {glossaryTerm ? (
          <span className="inline-flex min-h-7 shrink-0 items-center gap-1 rounded-lg border border-cyan-200/15 bg-cyan-300/10 px-2 py-1 text-[11px] font-medium text-cyan-100">
            <BookOpenText className="size-3.5" aria-hidden="true" />
            {glossaryTerm}
          </span>
        ) : null}
      </div>
      <p className={cn('mt-3 break-words font-mono text-3xl font-semibold leading-none tabular-nums', VALUE_TONE_CLASS[tone])}>
        {value}
      </p>
      <p className="mt-3 text-sm leading-6 text-white/74">{meaning}</p>
      <p className="mt-3 border-t border-white/[0.04] pt-3 text-xs leading-5 text-white/42">{freshnessNote}</p>
    </article>
  );
}
