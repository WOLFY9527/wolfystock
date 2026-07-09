import { cn } from '../../utils/cn';

export type SectionIntroStatus = {
  label: string;
  tone?: 'ready' | 'watch' | 'risk' | 'neutral';
};

export type SectionIntroProps = {
  purpose: string;
  summary: string;
  nextStep?: string;
  status?: SectionIntroStatus;
  className?: string;
};

const STATUS_TONE_CLASS: Record<NonNullable<SectionIntroStatus['tone']>, string> = {
  ready: 'border-emerald-300/25 bg-emerald-400/10 text-emerald-100',
  watch: 'border-amber-300/25 bg-amber-300/10 text-amber-100',
  risk: 'border-rose-300/25 bg-rose-400/10 text-rose-100',
  neutral: 'border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] text-[color:var(--wolfy-text-secondary)]',
};

export function SectionIntro({
  purpose,
  summary,
  nextStep,
  status,
  className,
}: SectionIntroProps) {
  const statusTone = status?.tone ?? 'neutral';

  return (
    <section
      className={cn(
        'relative overflow-hidden rounded-[16px] border border-white/5 bg-white/[0.02] p-4 backdrop-blur-md md:p-5',
        'shadow-[0_18px_60px_rgba(0,0,0,0.22)]',
        className,
      )}
    >
      <div className="pointer-events-none absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-cyan-200/20 to-transparent" />
      <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-cyan-100/55">{purpose}</p>
          <p className="mt-2 text-base font-medium leading-7 text-[color:var(--wolfy-text-primary)] md:text-lg">{summary}</p>
        </div>
        {status ? (
          <span
            className={cn(
              'inline-flex min-h-7 shrink-0 items-center rounded-lg border px-2.5 py-1 text-[11px] font-semibold',
              STATUS_TONE_CLASS[statusTone],
            )}
          >
            {status.label}
          </span>
        ) : null}
      </div>
      {nextStep ? (
        <p className="mt-3 max-w-3xl text-sm leading-6 text-[color:var(--wolfy-text-muted)]">
          <span className="text-[color:var(--wolfy-text-muted)]">下一步：</span>
          {nextStep}
        </p>
      ) : null}
    </section>
  );
}
