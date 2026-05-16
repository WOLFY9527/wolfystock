import React from 'react';
import { cn } from '../../utils/cn';
import {
  TerminalDisclosure,
  TerminalEmptyState,
  TerminalPageHeading,
} from './TerminalPrimitives';

type DensePrimitiveProps<T extends HTMLElement = HTMLElement> = React.HTMLAttributes<T> & {
  children?: React.ReactNode;
  'data-testid'?: string;
};

type DenseStatusItem = {
  label: React.ReactNode;
  value: React.ReactNode;
  key?: React.Key;
};

export function DensePageHeader({
  eyebrow,
  title,
  action,
  className,
  'data-testid': dataTestId,
}: {
  eyebrow?: React.ReactNode;
  title: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
  'data-testid'?: string;
}) {
  return (
    <header
      data-testid={dataTestId}
      data-terminal-primitive="dense-page-header"
      className={cn('flex min-w-0 flex-col gap-3 border-b border-white/10 pb-3 md:flex-row md:items-start md:justify-between', className)}
    >
      <TerminalPageHeading eyebrow={eyebrow} title={title} action={action} />
    </header>
  );
}

export function DenseStatusStrip({
  items,
  ariaLabel,
  className,
  'data-testid': dataTestId,
  ...props
}: Omit<DensePrimitiveProps<HTMLElement>, 'children'> & {
  items: DenseStatusItem[];
  ariaLabel?: string;
}) {
  return (
    <section
      data-testid={dataTestId}
      data-terminal-primitive="dense-status-strip"
      className={cn('flex min-w-0 flex-wrap items-center gap-x-4 gap-y-2 border-y border-white/10 bg-white/[0.015] px-3 py-2 text-xs', className)}
      aria-label={ariaLabel}
      {...props}
    >
      {items.map((item, index) => (
        <div key={item.key ?? index} className="flex min-w-0 items-baseline gap-1.5 border-r border-white/10 pr-4 last:border-r-0">
          <span className="shrink-0 text-[10px] font-bold uppercase tracking-widest text-white/35">{item.label}</span>
          <span className="truncate font-mono text-sm font-semibold text-white">{item.value}</span>
        </div>
      ))}
    </section>
  );
}

export function DenseTableShell({
  className,
  children,
  variant = 'panel',
  ...props
}: DensePrimitiveProps<HTMLElement> & {
  variant?: 'panel' | 'board';
}) {
  return (
    <section
      data-terminal-primitive="dense-table-shell"
      className={cn(
        'flex min-w-0 flex-col overflow-hidden',
        variant === 'board'
          ? 'border-y border-white/10 bg-black/[0.08]'
          : 'rounded-[14px] border border-white/10 bg-black/10 shadow-[0_20px_80px_rgba(0,0,0,0.22)]',
        className,
      )}
      {...props}
    >
      {children}
    </section>
  );
}

export function DenseCommandBar({
  heading,
  summary,
  notice,
  progress,
  actions,
  className,
  children,
  ...props
}: DensePrimitiveProps<HTMLDivElement> & {
  heading?: React.ReactNode;
  summary?: React.ReactNode;
  notice?: React.ReactNode;
  progress?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div
      data-terminal-primitive="dense-command-bar"
      className={cn('flex min-w-0 flex-wrap items-center justify-between gap-3 border-b border-white/10 bg-black/20 px-3 py-2.5', className)}
      {...props}
    >
      <div className="min-w-0 flex-1 space-y-1">
        {heading ? <p className="text-[10px] font-bold uppercase tracking-widest text-white/40">{heading}</p> : null}
        {summary ? <p className="truncate text-xs text-white/45">{summary}</p> : null}
        {notice}
        {progress}
        {children}
      </div>
      {actions ? <div className="flex min-w-0 flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function DenseTableFrame({ className, children, ...props }: DensePrimitiveProps<HTMLDivElement>) {
  return (
    <div data-terminal-primitive="dense-table-frame" className={cn('overflow-hidden', className)} {...props}>
      <div className="overflow-x-auto no-scrollbar">
        {children}
      </div>
    </div>
  );
}

export function CompactEmptyRow({
  className,
  children,
  ...props
}: React.ComponentProps<typeof TerminalEmptyState>) {
  return (
    <TerminalEmptyState
      className={cn('min-h-[72px] items-start text-left sm:items-center', className)}
      {...props}
    >
      {children}
    </TerminalEmptyState>
  );
}

export function DenseSecondaryDisclosure({
  className,
  children,
  variant = 'panel',
  ...props
}: React.ComponentProps<typeof TerminalDisclosure> & {
  variant?: 'panel' | 'row';
}) {
  return (
    <TerminalDisclosure
      className={cn(
        variant === 'row'
          ? 'rounded-none border-x-0 border-b-0 border-t border-white/10 bg-transparent px-0 py-2.5 backdrop-blur-0 hover:border-white/10'
          : 'border-white/10 bg-white/[0.015]',
        className,
      )}
      {...props}
    >
      {children}
    </TerminalDisclosure>
  );
}
