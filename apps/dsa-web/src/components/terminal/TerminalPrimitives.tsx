import React, { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '../../utils/cn';
import { WolfyShellSurface } from '../linear';

type PrimitiveProps<T extends HTMLElement = HTMLElement> = React.HTMLAttributes<T> & {
  children?: React.ReactNode;
  'data-testid'?: string;
};

type PanelProps = PrimitiveProps & {
  as?: 'div' | 'section' | 'article' | 'aside';
  dense?: boolean;
};

// Legacy-compatible names; new user-facing work should prefer components/linear.
export function TerminalPageShell({ className, children, ...props }: PrimitiveProps<HTMLDivElement>) {
  return (
    <div
      data-terminal-primitive="page-shell"
      className={cn('w-full max-w-[1600px] mx-auto px-4 xl:px-8 flex flex-col gap-5 text-[color:var(--wolfy-text-primary)]', className)}
      {...props}
    >
      {children}
    </div>
  );
}

export function TerminalGrid({ className, children, ...props }: PrimitiveProps<HTMLDivElement>) {
  return (
    <div
      data-terminal-primitive="grid"
      className={cn('grid grid-cols-1 xl:grid-cols-12 gap-6 items-start', className)}
      {...props}
    >
      {children}
    </div>
  );
}

export function TerminalPanel({ as = 'div', dense = false, className, children, ...props }: PanelProps) {
  return (
    <WolfyShellSurface
      as={as}
      data-terminal-primitive="panel"
      variant="console"
      padding={dense ? 'sm' : 'md'}
      className={cn('transition-colors hover:border-[color:var(--wolfy-divider)]', className)}
      {...props}
    >
      {children}
    </WolfyShellSurface>
  );
}

export function TerminalNestedBlock({ className, children, ...props }: PrimitiveProps<HTMLDivElement>) {
  return (
    <WolfyShellSurface
      as="div"
      data-terminal-primitive="nested-block"
      variant="input"
      padding="sm"
      className={cn('rounded-md', className)}
      {...props}
    >
      {children}
    </WolfyShellSurface>
  );
}

export function TerminalSectionHeader({
  eyebrow,
  title,
  action,
  className,
}: {
  eyebrow?: React.ReactNode;
  title: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div data-terminal-primitive="section-header" className={cn('flex min-w-0 items-start justify-between gap-3', className)}>
      <div className="min-w-0">
        {eyebrow ? <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">{eyebrow}</p> : null}
        <h2 className="mt-1 truncate text-sm font-medium text-[color:var(--wolfy-text-primary)]">{title}</h2>
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

export function TerminalPageHeading({
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
    <div
      data-testid={dataTestId}
      data-terminal-primitive="page-heading"
      className={cn('flex min-w-0 items-start justify-between gap-3', className)}
    >
      <div className="min-w-0">
        {eyebrow ? <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">{eyebrow}</p> : null}
        <h1 className="mt-1 truncate text-xl font-semibold text-[color:var(--wolfy-text-primary)] md:text-2xl">{title}</h1>
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

export function TerminalMetric({
  label,
  value,
  subvalue,
  valueClassName,
  className,
  'data-testid': dataTestId,
  ...props
}: PrimitiveProps<HTMLDivElement> & {
  label: React.ReactNode;
  value: React.ReactNode;
  subvalue?: React.ReactNode;
  valueClassName?: string;
}) {
  return (
    <TerminalNestedBlock data-testid={dataTestId} className={className} {...props}>
      <div className="text-[11px] text-[color:var(--wolfy-text-muted)]">{label}</div>
      <div className={cn('mt-1 font-mono tracking-tight text-[color:var(--wolfy-text-primary)]', valueClassName)}>{value}</div>
      {subvalue ? <div className="mt-1 text-xs text-[color:var(--wolfy-text-muted)]">{subvalue}</div> : null}
    </TerminalNestedBlock>
  );
}

type TerminalButtonVariant = 'primary' | 'secondary' | 'compact' | 'danger';

const TERMINAL_BUTTON_CLASSES: Record<TerminalButtonVariant, string> = {
  primary: 'border border-[color:var(--wolfy-accent)] bg-[var(--wolfy-accent)] text-[#f7f8ff] font-medium px-5 py-2.5 rounded-md transition-colors hover:bg-[#6f79dc] disabled:opacity-50 disabled:cursor-not-allowed',
  secondary: 'border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] text-[color:var(--wolfy-text-secondary)] hover:text-[color:var(--wolfy-text-primary)] hover:border-[color:var(--wolfy-divider)] px-4 py-2.5 rounded-md transition-colors',
  compact: 'border border-[color:var(--wolfy-border-subtle)] bg-transparent text-[color:var(--wolfy-text-secondary)] hover:text-[color:var(--wolfy-text-primary)] px-3 py-1.5 rounded-md text-xs transition-colors',
  danger: 'border border-[color:color-mix(in_srgb,var(--wolfy-market-down)_34%,transparent)] bg-transparent text-[color:var(--wolfy-market-down)] hover:bg-[color:color-mix(in_srgb,var(--wolfy-market-down)_10%,transparent)] px-3 py-1.5 rounded-md text-xs transition-colors',
};

export const TerminalButton = /* @__PURE__ */ React.forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: TerminalButtonVariant;
}>(({ variant = 'secondary', className, type = 'button', children, ...props }, ref) => (
  <button
    ref={ref}
    type={type}
    data-terminal-primitive="button"
    className={cn('inline-flex max-w-full items-center justify-center gap-2 whitespace-nowrap', TERMINAL_BUTTON_CLASSES[variant], className)}
    {...props}
  >
    {children}
  </button>
));
TerminalButton.displayName = 'TerminalButton';

type TerminalChipVariant = 'neutral' | 'success' | 'caution' | 'danger' | 'info';

const TERMINAL_CHIP_CLASSES: Record<TerminalChipVariant, string> = {
  neutral: 'bg-[var(--wolfy-surface-input)] border border-[color:var(--wolfy-border-subtle)] text-[color:var(--wolfy-text-muted)] text-xs font-mono px-2.5 py-1 rounded-md',
  success: 'bg-transparent border border-[color:color-mix(in_srgb,var(--wolfy-market-up)_32%,transparent)] text-[color:var(--wolfy-market-up)] text-xs px-2.5 py-1 rounded-md',
  caution: 'bg-transparent border border-amber-300/25 text-amber-200 text-xs px-2.5 py-1 rounded-md',
  danger: 'bg-transparent border border-[color:color-mix(in_srgb,var(--wolfy-market-down)_32%,transparent)] text-[color:var(--wolfy-market-down)] text-xs px-2.5 py-1 rounded-md',
  info: 'bg-transparent border border-[color:color-mix(in_srgb,var(--wolfy-accent)_36%,transparent)] text-[color:var(--wolfy-accent)] text-xs px-2.5 py-1 rounded-md',
};

export function TerminalChip({
  variant = 'neutral',
  className,
  children,
  ...props
}: PrimitiveProps<HTMLSpanElement> & { variant?: TerminalChipVariant }) {
  return (
    <span data-terminal-primitive="chip" className={cn('inline-flex max-w-full items-center gap-1', TERMINAL_CHIP_CLASSES[variant], className)} {...props}>
      {children}
    </span>
  );
}

export function TerminalEmptyState({
  title,
  action,
  className,
  'data-testid': dataTestId,
  children,
  ...props
}: PrimitiveProps<HTMLDivElement> & {
  title?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div
      data-testid={dataTestId || 'terminal-empty-state'}
      data-terminal-primitive="empty-state"
      className={cn('flex min-h-[72px] items-center justify-between gap-3 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-4 py-3 text-xs text-[color:var(--wolfy-text-muted)]', className)}
      {...props}
    >
      <div className="min-w-0">
        {title ? <p className="text-xs text-[color:var(--wolfy-text-secondary)]">{title}</p> : null}
        {children ? <div className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{children}</div> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

type NoticeVariant = 'neutral' | 'info' | 'caution' | 'danger';

const NOTICE_CLASSES: Record<NoticeVariant, string> = {
  neutral: 'border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] text-[color:var(--wolfy-text-secondary)]',
  info: 'border-[color:color-mix(in_srgb,var(--wolfy-accent)_34%,transparent)] bg-transparent text-[color:var(--wolfy-accent)]',
  caution: 'border-amber-300/20 bg-amber-300/5 text-amber-100/80',
  danger: 'border-[color:color-mix(in_srgb,var(--wolfy-market-down)_34%,transparent)] bg-transparent text-[color:var(--wolfy-market-down)]',
};

export function TerminalNotice({
  variant = 'neutral',
  className,
  children,
  ...props
}: PrimitiveProps<HTMLDivElement> & { variant?: NoticeVariant }) {
  return (
    <div data-terminal-primitive="notice" className={cn('rounded-xl border px-3 py-2 text-xs leading-5', NOTICE_CLASSES[variant], className)} {...props}>
      {children}
    </div>
  );
}

export function TerminalDenseList({ className, children, ...props }: PrimitiveProps<HTMLDivElement>) {
  return (
    <div data-terminal-primitive="dense-list" className={cn('flex flex-col gap-1.5 text-xs', className)} {...props}>
      {children}
    </div>
  );
}

export function TerminalDenseTable({ className, children, ...props }: PrimitiveProps<HTMLDivElement>) {
  return (
    <div data-terminal-primitive="dense-table" className={cn('overflow-x-auto no-scrollbar rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] text-xs', className)} {...props}>
      {children}
    </div>
  );
}

export function TerminalDisclosure({
  title,
  summary,
  children,
  defaultOpen = false,
  className,
  'data-testid': dataTestId,
  ...props
}: PrimitiveProps<HTMLDetailsElement> & {
  title: React.ReactNode;
  summary?: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const titleText = typeof title === 'string' ? title : '';
  const actionLabel = open ? `收起 ${titleText}` : `展开 ${titleText}`;
  return (
    <details
      data-testid={dataTestId || 'terminal-disclosure'}
      data-terminal-primitive="disclosure"
      open={open}
      className={cn('rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-2.5 py-2 text-xs transition-colors hover:border-[color:var(--wolfy-divider)]', className)}
      {...props}
    >
      <div className="flex min-w-0 items-center justify-between gap-2">
        <div className="min-w-0">
          <h3 className="truncate text-xs font-medium text-[color:var(--wolfy-text-secondary)]">{title}</h3>
          {summary ? <p className="mt-0.5 truncate text-[11px] text-[color:var(--wolfy-text-muted)]">{summary}</p> : null}
        </div>
        <button
          type="button"
          aria-expanded={open}
          aria-label={actionLabel}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-[color:var(--wolfy-border-subtle)] bg-transparent px-2 py-1 text-[11px] text-[color:var(--wolfy-text-secondary)] hover:text-[color:var(--wolfy-text-primary)]"
          onClick={() => setOpen((current) => !current)}
        >
          {open ? <ChevronDown className="size-3.5" aria-hidden="true" /> : <ChevronRight className="size-3.5" aria-hidden="true" />}
          <span>{open ? '收起' : '展开'}</span>
        </button>
      </div>
      {open ? <div className="mt-2">{children}</div> : null}
    </details>
  );
}
