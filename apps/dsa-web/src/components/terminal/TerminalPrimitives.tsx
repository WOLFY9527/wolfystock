import React, { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '../../utils/cn';

type PrimitiveProps<T extends HTMLElement = HTMLElement> = React.HTMLAttributes<T> & {
  children?: React.ReactNode;
  'data-testid'?: string;
};

type PanelProps = PrimitiveProps & {
  as?: 'div' | 'section' | 'article' | 'aside';
  dense?: boolean;
};

export function TerminalPageShell({ className, children, ...props }: PrimitiveProps<HTMLDivElement>) {
  return (
    <div
      data-terminal-primitive="page-shell"
      className={cn('w-full max-w-[1600px] mx-auto px-4 xl:px-8 flex flex-col gap-6', className)}
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
  const Component = as;
  return (
    <Component
      data-terminal-primitive="panel"
      className={cn(
        'bg-white/[0.02] border border-white/5 backdrop-blur-md rounded-[16px] transition-all hover:border-white/10',
        dense ? 'p-4' : 'p-5',
        className,
      )}
      {...props}
    >
      {children}
    </Component>
  );
}

export function TerminalNestedBlock({ className, children, ...props }: PrimitiveProps<HTMLDivElement>) {
  return (
    <div
      data-terminal-primitive="nested-block"
      className={cn('bg-black/20 border border-white/[0.02] rounded-xl p-3', className)}
      {...props}
    >
      {children}
    </div>
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
        {eyebrow ? <p className="text-[10px] font-bold uppercase tracking-widest text-white/40">{eyebrow}</p> : null}
        <h2 className="mt-1 truncate text-sm font-medium text-white/90">{title}</h2>
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
        {eyebrow ? <p className="text-[10px] font-bold uppercase tracking-widest text-white/40">{eyebrow}</p> : null}
        <h1 className="mt-1 truncate text-xl font-semibold tracking-tight text-white md:text-2xl">{title}</h1>
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
      <div className="text-[10px] uppercase tracking-widest text-white/35">{label}</div>
      <div className={cn('mt-1 font-mono tracking-tight text-white', valueClassName)}>{value}</div>
      {subvalue ? <div className="mt-1 text-xs text-white/35">{subvalue}</div> : null}
    </TerminalNestedBlock>
  );
}

type TerminalButtonVariant = 'primary' | 'secondary' | 'compact' | 'danger';

const TERMINAL_BUTTON_CLASSES: Record<TerminalButtonVariant, string> = {
  primary: 'bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white font-medium shadow-[0_0_15px_rgba(139,92,246,0.3)] px-6 py-2.5 rounded-lg transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed',
  secondary: 'bg-white/5 border border-white/10 text-white/70 hover:bg-white/10 hover:text-white hover:border-white/20 px-5 py-2.5 rounded-lg transition-all duration-300',
  compact: 'bg-white/[0.03] border border-white/10 text-white/60 hover:bg-white/[0.07] hover:text-white px-3 py-1.5 rounded-lg text-xs transition-all',
  danger: 'bg-rose-500/5 border border-rose-400/20 text-rose-300 hover:bg-rose-500/10 hover:border-rose-400/30 px-3 py-1.5 rounded-lg text-xs transition-all',
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
  neutral: 'bg-white/5 border border-white/10 text-white/50 text-xs font-mono px-2.5 py-1 rounded-md',
  success: 'bg-emerald-400/5 border border-emerald-400/20 text-emerald-300 text-xs px-2.5 py-1 rounded-md',
  caution: 'bg-amber-300/5 border border-amber-300/20 text-amber-300 text-xs px-2.5 py-1 rounded-md',
  danger: 'bg-rose-500/5 border border-rose-400/20 text-rose-300 text-xs px-2.5 py-1 rounded-md',
  info: 'bg-cyan-400/5 border border-cyan-300/20 text-cyan-300 text-xs px-2.5 py-1 rounded-md',
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
      className={cn('flex min-h-[88px] items-center justify-between gap-3 rounded-xl border border-white/[0.03] bg-black/10 px-4 py-3 text-xs text-white/30', className)}
      {...props}
    >
      <div className="min-w-0">
        {title ? <p className="text-xs text-white/45">{title}</p> : null}
        {children ? <div className="mt-1 text-xs leading-5 text-white/30">{children}</div> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

type NoticeVariant = 'neutral' | 'info' | 'caution' | 'danger';

const NOTICE_CLASSES: Record<NoticeVariant, string> = {
  neutral: 'border-white/[0.05] bg-white/[0.02] text-white/55',
  info: 'border-cyan-300/20 bg-cyan-400/5 text-cyan-100/80',
  caution: 'border-amber-300/20 bg-amber-300/5 text-amber-100/80',
  danger: 'border-rose-400/20 bg-rose-500/5 text-rose-100/80',
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
    <div data-terminal-primitive="dense-table" className={cn('overflow-x-auto no-scrollbar rounded-xl border border-white/5 bg-white/[0.02] text-xs', className)} {...props}>
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
      className={cn('rounded-xl border border-white/5 bg-white/[0.02] px-2.5 py-2 text-xs backdrop-blur-md transition-all hover:border-white/10', className)}
      {...props}
    >
      <div className="flex min-w-0 items-center justify-between gap-2">
        <div className="min-w-0">
          <h3 className="truncate text-[10px] font-bold uppercase tracking-widest text-white/40">{title}</h3>
          {summary ? <p className="mt-0.5 truncate text-[11px] text-white/38">{summary}</p> : null}
        </div>
        <button
          type="button"
          aria-expanded={open}
          aria-label={actionLabel}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-white/8 bg-white/[0.035] px-2 py-1 text-[11px] text-white/58 hover:bg-white/[0.07] hover:text-white"
          onClick={() => setOpen((current) => !current)}
        >
          {open ? <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" /> : <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />}
          <span>{open ? '收起' : '展开'}</span>
        </button>
      </div>
      {open ? <div className="mt-2">{children}</div> : null}
    </details>
  );
}
