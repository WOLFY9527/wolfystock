import React, { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '../../utils/cn';

type LinearPrimitiveProps<T extends HTMLElement = HTMLElement> = React.HTMLAttributes<T> & {
  children?: React.ReactNode;
  'data-testid'?: string;
};

type LinearSurfaceElement = 'div' | 'section' | 'article' | 'aside' | 'header';
type LinearSurfaceVariant = 'console' | 'input' | 'rail' | 'flat';
type LinearSurfacePadding = 'none' | 'xs' | 'sm' | 'md' | 'lg';

const SURFACE_VARIANTS: Record<LinearSurfaceVariant, string> = {
  console: 'border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] text-[color:var(--wolfy-text-primary)]',
  input: 'border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] text-[color:var(--wolfy-text-primary)]',
  rail: 'border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-rail)] text-[color:var(--wolfy-text-primary)]',
  flat: 'border-0 bg-transparent text-[color:var(--wolfy-text-primary)]',
};

const SURFACE_PADDING: Record<LinearSurfacePadding, string> = {
  none: 'p-0',
  xs: 'p-2',
  sm: 'p-3',
  md: 'p-4 md:p-5',
  lg: 'p-5 md:p-6',
};

export function WolfyShellSurface({
  as = 'section',
  variant = 'console',
  padding = 'md',
  className,
  children,
  ...props
}: LinearPrimitiveProps<HTMLElement> & {
  as?: LinearSurfaceElement;
  variant?: LinearSurfaceVariant;
  padding?: LinearSurfacePadding;
}) {
  const Component = as;
  return (
    <Component
      data-linear-primitive="surface"
      className={cn(
        'min-w-0 rounded-lg shadow-none',
        SURFACE_VARIANTS[variant],
        SURFACE_PADDING[padding],
        className,
      )}
      {...props}
    >
      {children}
    </Component>
  );
}

export function WolfyCommandBar({
  className,
  children,
  leading,
  trailing,
  ...props
}: LinearPrimitiveProps<HTMLDivElement> & {
  leading?: React.ReactNode;
  trailing?: React.ReactNode;
}) {
  return (
    <div
      data-linear-primitive="command-bar"
      className={cn(
        'flex min-h-11 w-full min-w-0 flex-wrap items-center gap-2 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-2 text-[color:var(--wolfy-text-primary)] shadow-none',
        className,
      )}
      {...props}
    >
      {leading ? <div className="flex min-w-0 items-center gap-2">{leading}</div> : null}
      <div className="min-w-[12rem] flex-1">{children}</div>
      {trailing ? <div className="flex min-w-0 flex-wrap items-center justify-end gap-2">{trailing}</div> : null}
    </div>
  );
}

export function ResearchConsoleShell({
  command,
  rail,
  children,
  className,
  ...props
}: LinearPrimitiveProps<HTMLDivElement> & {
  command?: React.ReactNode;
  rail?: React.ReactNode;
}) {
  return (
    <div
      data-linear-primitive="research-console-shell"
      className={cn('flex w-full min-w-0 flex-col gap-4', className)}
      {...props}
    >
      {command}
      <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0">{children}</div>
        {rail ? <div className="min-w-0">{rail}</div> : null}
      </div>
    </div>
  );
}

export function ConsoleBoard({ className, children, ...props }: LinearPrimitiveProps<HTMLElement>) {
  return (
    <WolfyShellSurface
      data-linear-primitive="console-board"
      variant="console"
      padding="none"
      className={cn('overflow-hidden', className)}
      {...props}
    >
      {children}
    </WolfyShellSurface>
  );
}

export function ConsoleContextRail({ className, children, ...props }: LinearPrimitiveProps<HTMLElement>) {
  return (
    <WolfyShellSurface
      data-linear-primitive="context-rail"
      variant="rail"
      padding="sm"
      className={cn('flex min-w-0 flex-col divide-y divide-[color:var(--wolfy-divider)]', className)}
      {...props}
    >
      {children}
    </WolfyShellSurface>
  );
}

export function ConsoleStatusStrip({
  items,
  className,
  ...props
}: Omit<LinearPrimitiveProps<HTMLDivElement>, 'children'> & {
  items: Array<{ label: React.ReactNode; value: React.ReactNode; key?: React.Key }>;
}) {
  return (
    <div
      data-linear-primitive="status-strip"
      className={cn(
        'flex min-w-0 flex-wrap items-center gap-x-4 gap-y-2 border-y border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] px-3 py-2 text-xs',
        className,
      )}
      {...props}
    >
      {items.map((item, index) => (
        <div key={item.key ?? index} className="flex min-w-0 items-baseline gap-1.5 border-r border-[color:var(--wolfy-divider)] pr-4 last:border-r-0">
          <span className="shrink-0 text-[11px] text-[color:var(--wolfy-text-muted)]">{item.label}</span>
          <span className="truncate font-mono text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{item.value}</span>
        </div>
      ))}
    </div>
  );
}

export function ConsoleDisclosure({
  title,
  summary,
  defaultOpen = false,
  children,
  className,
  ...props
}: LinearPrimitiveProps<HTMLDivElement> & {
  title: React.ReactNode;
  summary?: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const titleText = typeof title === 'string' ? title : '';
  return (
    <div
      data-linear-primitive="disclosure"
      className={cn('rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-2 text-xs', className)}
      {...props}
    >
      <div className="flex min-w-0 items-center justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-xs font-medium text-[color:var(--wolfy-text-secondary)]">{title}</h3>
          {summary ? <p className="mt-0.5 truncate text-[11px] text-[color:var(--wolfy-text-muted)]">{summary}</p> : null}
        </div>
        <button
          type="button"
          aria-expanded={open}
          aria-label={open ? `收起 ${titleText}` : `展开 ${titleText}`}
          className="inline-flex shrink-0 items-center gap-1 rounded-md border border-[color:var(--wolfy-border-subtle)] bg-transparent px-2 py-1 text-[11px] text-[color:var(--wolfy-text-secondary)] hover:text-[color:var(--wolfy-text-primary)]"
          onClick={() => setOpen((current) => !current)}
        >
          {open ? <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" /> : <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />}
          <span>{open ? '收起' : '展开'}</span>
        </button>
      </div>
      {open ? <div className="mt-3 border-t border-[color:var(--wolfy-divider)] pt-3">{children}</div> : null}
    </div>
  );
}

export function KeyLevelStrip({
  levels,
  className,
  ...props
}: Omit<LinearPrimitiveProps<HTMLDivElement>, 'children'> & {
  levels: Array<{ label: React.ReactNode; value: React.ReactNode; tone?: 'neutral' | 'up' | 'down'; key?: React.Key }>;
}) {
  return (
    <div
      data-linear-primitive="key-level-strip"
      className={cn('grid min-w-0 gap-2 border-y border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] p-2 sm:grid-cols-3', className)}
      {...props}
    >
      {levels.map((level, index) => (
        <div key={level.key ?? index} className="min-w-0 px-2 py-1">
          <div className="text-[11px] text-[color:var(--wolfy-text-muted)]">{level.label}</div>
          <div
            className={cn(
              'mt-0.5 truncate font-mono text-sm font-semibold',
              level.tone === 'up' && 'text-[color:var(--wolfy-market-up)]',
              level.tone === 'down' && 'text-[color:var(--wolfy-market-down)]',
              (!level.tone || level.tone === 'neutral') && 'text-[color:var(--wolfy-text-primary)]',
            )}
          >
            {level.value}
          </div>
        </div>
      ))}
    </div>
  );
}

export function CatalystRows({
  items,
  emptyText = '暂无已验证催化剂',
  className,
  ...props
}: Omit<LinearPrimitiveProps<HTMLDivElement>, 'children'> & {
  items: Array<{ title: React.ReactNode; meta?: React.ReactNode; status?: React.ReactNode; key?: React.Key }>;
  emptyText?: React.ReactNode;
}) {
  return (
    <div
      data-linear-primitive="catalyst-rows"
      className={cn('divide-y divide-[color:var(--wolfy-divider)] text-xs', className)}
      {...props}
    >
      {items.length ? items.map((item, index) => (
        <div key={item.key ?? index} className="grid min-w-0 gap-1 py-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
          <div className="min-w-0">
            <p className="truncate text-[color:var(--wolfy-text-primary)]">{item.title}</p>
            {item.meta ? <p className="mt-0.5 truncate text-[color:var(--wolfy-text-muted)]">{item.meta}</p> : null}
          </div>
          {item.status ? <div className="text-[color:var(--wolfy-text-secondary)]">{item.status}</div> : null}
        </div>
      )) : (
        <div className="py-2 text-[color:var(--wolfy-text-muted)]">{emptyText}</div>
      )}
    </div>
  );
}

export function DataWorkbenchFrame({ className, children, ...props }: LinearPrimitiveProps<HTMLElement>) {
  return (
    <WolfyShellSurface
      data-linear-primitive="data-workbench-frame"
      variant="console"
      padding="none"
      className={cn('overflow-hidden', className)}
      {...props}
    >
      <div className="overflow-x-auto no-scrollbar">{children}</div>
    </WolfyShellSurface>
  );
}

export function DenseRows({ className, children, ...props }: LinearPrimitiveProps<HTMLDivElement>) {
  return (
    <div
      data-linear-primitive="dense-rows"
      className={cn('divide-y divide-[color:var(--wolfy-divider)] text-xs text-[color:var(--wolfy-text-secondary)]', className)}
      {...props}
    >
      {children}
    </div>
  );
}
