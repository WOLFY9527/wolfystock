import type React from 'react';
import { TerminalChip } from '../terminal/TerminalPrimitives';
import { cn } from '../../utils/cn';

type PortfolioTrustChipVariant = 'neutral' | 'success' | 'caution' | 'danger' | 'info';

export type PortfolioTrustChipItem = {
  key: string;
  label: string;
  variant?: PortfolioTrustChipVariant;
};

export function PortfolioTrustStrip({
  title,
  items,
  children,
  className,
  chipsClassName,
  'data-testid': dataTestId,
}: {
  title?: string;
  items: PortfolioTrustChipItem[];
  children?: React.ReactNode;
  className?: string;
  chipsClassName?: string;
  'data-testid'?: string;
}) {
  if (!items.length && !children) return null;

  return (
    <div
      data-testid={dataTestId}
      className={cn('flex min-w-0 flex-col gap-1.5 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-2', className)}
    >
      {title ? <div className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{title}</div> : null}
      {children}
      <div className={cn('flex min-w-0 flex-wrap items-center gap-1.5', chipsClassName)}>
        {items.map((item) => (
          <TerminalChip key={item.key} variant={item.variant ?? 'neutral'}>
            {item.label}
          </TerminalChip>
        ))}
      </div>
    </div>
  );
}
