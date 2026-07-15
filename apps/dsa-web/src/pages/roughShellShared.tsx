import type React from 'react';
import { cn } from '../utils/cn';
import { WolfyShellSurface } from '../components/linear/LinearPrimitives';
import {
  TerminalChip,
  TerminalEmptyState,
  TerminalPageHeading,
  TerminalSectionHeader,
} from '../components/terminal/TerminalPrimitives';

export function RoughSurfaceIntro({
  eyebrow,
  title,
  description,
  action,
  className,
  'data-testid': dataTestId,
}: {
  eyebrow: React.ReactNode;
  title: React.ReactNode;
  description: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
  'data-testid'?: string;
}) {
  return (
    <div className={cn('border-b border-[color:var(--wolfy-divider)] px-4 py-4 md:px-5', className)}>
      <TerminalPageHeading eyebrow={eyebrow} title={title} action={action} data-testid={dataTestId} />
      <p className="mt-2 max-w-4xl text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">{description}</p>
    </div>
  );
}

/**
 * Legacy bordered section card. Preserved for Structure / Radar / Scenario / Cockpit.
 */
export function RoughSectionCard({
  eyebrow,
  title,
  action,
  children,
  className,
  'data-testid': dataTestId,
}: {
  eyebrow?: React.ReactNode;
  title: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  'data-testid'?: string;
}) {
  return (
    <WolfyShellSurface
      variant="input"
      padding="sm"
      className={cn('flex min-w-0 flex-col gap-3 rounded-[16px]', className)}
      data-testid={dataTestId}
      data-rough-variant="section-card"
    >
      <TerminalSectionHeader eyebrow={eyebrow} title={title} action={action} />
      <div className="min-w-0">{children}</div>
    </WolfyShellSurface>
  );
}

export function RoughBulletList({
  items,
  emptyText,
  className,
  /**
   * `cards` preserves legacy bordered item chrome (Structure/Radar/Scenario/Cockpit).
   * `rows` is the de-cardified migration path using dividers only.
   */
  variant = 'cards',
}: {
  items: Array<React.ReactNode>;
  emptyText: React.ReactNode;
  className?: string;
  variant?: 'cards' | 'rows';
}) {
  if (!items.length) {
    return (
      <TerminalEmptyState className={className}>
        {emptyText}
      </TerminalEmptyState>
    );
  }

  if (variant === 'rows') {
    return (
      <ul
        data-rough-variant="bullet-rows"
        data-research-frame="content"
        className={cn(
          'divide-y divide-[color:var(--wolfy-divider)] text-sm leading-6 text-[color:var(--wolfy-text-secondary)]',
          className,
        )}
      >
        {items.map((item, index) => (
          <li key={index} className="py-2">
            {item}
          </li>
        ))}
      </ul>
    );
  }

  return (
    <ul
      data-rough-variant="bullet-cards"
      className={cn('space-y-2 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]', className)}
    >
      {items.map((item, index) => (
        <li key={index} className="rounded-xl border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] px-3 py-2">
          {item}
        </li>
      ))}
    </ul>
  );
}

export function RoughKeyValueRows({
  rows,
  emptyText,
}: {
  rows: Array<{
    key: React.Key;
    label: React.ReactNode;
    value: React.ReactNode;
    detail?: React.ReactNode;
  }>;
  emptyText?: React.ReactNode;
}) {
  if (!rows.length) {
    return <TerminalEmptyState>{emptyText ?? '暂无可展示条目。'}</TerminalEmptyState>;
  }

  return (
    <div className="divide-y divide-[color:var(--wolfy-divider)]" data-rough-variant="key-value-rows">
      {rows.map((row) => (
        <div key={row.key} className="grid gap-2 py-2.5 md:grid-cols-[minmax(0,11rem)_minmax(0,1fr)]">
          <div className="text-xs text-[color:var(--wolfy-text-muted)]">{row.label}</div>
          <div className="min-w-0">
            <div className="break-words text-sm text-[color:var(--wolfy-text-primary)]">{row.value}</div>
            {row.detail ? <div className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{row.detail}</div> : null}
          </div>
        </div>
      ))}
    </div>
  );
}

export function RoughScoreRows({
  items,
  emptyText,
}: {
  items: Array<{
    key: React.Key;
    label: React.ReactNode;
    value: React.ReactNode;
    meta?: React.ReactNode;
    badge?: {
      label: React.ReactNode;
      variant?: 'neutral' | 'success' | 'caution' | 'danger' | 'info';
    };
  }>;
  emptyText: React.ReactNode;
}) {
  if (!items.length) {
    return <TerminalEmptyState>{emptyText}</TerminalEmptyState>;
  }

  return (
    <div className="divide-y divide-[color:var(--wolfy-divider)]" data-rough-variant="score-rows">
      {items.map((item) => (
        <div key={item.key} className="flex min-w-0 items-start justify-between gap-3 py-2.5">
          <div className="min-w-0">
            <div className="text-sm text-[color:var(--wolfy-text-primary)]">{item.label}</div>
            {item.meta ? <div className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{item.meta}</div> : null}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {item.badge ? <TerminalChip variant={item.badge.variant}>{item.badge.label}</TerminalChip> : null}
            <span className="font-mono text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{item.value}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
