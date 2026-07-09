import type React from 'react';
import { cn } from '../../utils/cn';

export type DensityRailItem = {
  id: string;
  label: string;
  value: React.ReactNode;
  helper?: string;
  tone?: 'positive' | 'negative' | 'caution' | 'info' | 'neutral';
};

export type DensityRailProps = {
  items: DensityRailItem[];
  title?: string;
  className?: string;
};

const VALUE_TONE_CLASS: Record<NonNullable<DensityRailItem['tone']>, string> = {
  positive: 'text-emerald-200',
  negative: 'text-rose-200',
  caution: 'text-amber-100',
  info: 'text-cyan-100',
  neutral: 'text-[color:var(--wolfy-text-primary)]',
};

export function DensityRail({
  items,
  title = '辅助上下文',
  className,
}: DensityRailProps) {
  return (
    <aside
      className={cn(
        'rounded-[16px] border border-white/5 bg-white/[0.02] p-3 backdrop-blur-md',
        'md:max-w-[280px]',
        className,
      )}
      aria-label={title}
    >
      <p className="px-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--wolfy-text-muted)]">{title}</p>
      <dl className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 md:grid-cols-1">
        {items.map((item) => (
          <div key={item.id} className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-2.5">
            <dt className="text-[11px] leading-4 text-[color:var(--wolfy-text-muted)]">{item.label}</dt>
            <dd className={cn('mt-1 break-words text-sm font-semibold leading-5', VALUE_TONE_CLASS[item.tone ?? 'neutral'])}>
              {item.value}
            </dd>
            {item.helper ? <dd className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{item.helper}</dd> : null}
          </div>
        ))}
      </dl>
    </aside>
  );
}
