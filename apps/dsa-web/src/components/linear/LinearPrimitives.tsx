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
export type LinearLayoutZone =
  | 'RouteConsole'
  | 'HeaderStrip'
  | 'CommandBar'
  | 'PrimaryWorkRegion'
  | 'ContextRail'
  | 'SecondaryDeck'
  | 'ChartWell'
  | 'MetricStrip'
  | 'KeyLevelStrip'
  | 'DetailDrawer'
  | 'FloatingPanel';
type LinearRailWidth = 'sm' | 'md' | 'lg';

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

const RAIL_GRID_TRACKS: Record<LinearRailWidth, string> = {
  sm: 'lg:grid-cols-[minmax(0,1fr)_clamp(16rem,19vw,19rem)]',
  md: 'lg:grid-cols-[minmax(0,1fr)_clamp(18rem,22vw,22.5rem)]',
  lg: 'lg:grid-cols-[minmax(0,1fr)_clamp(27rem,25vw,34rem)]',
};

const RAIL_WIDTHS: Record<LinearRailWidth, string> = {
  sm: 'lg:w-[clamp(16rem,19vw,19rem)]',
  md: 'lg:w-[clamp(18rem,22vw,22.5rem)]',
  lg: 'lg:w-[clamp(27rem,25vw,34rem)]',
};

type FixedRegionWrapperProps = React.HTMLAttributes<HTMLDivElement> & {
  children?: React.ReactNode;
  className?: string;
  'data-testid'?: string;
};

export function PrimaryWorkRegion({
  className,
  children,
  ...props
}: FixedRegionWrapperProps) {
  return (
    <div
      data-linear-primitive="primary-work-region"
      data-layout-zone="PrimaryWorkRegion"
      className={cn('min-w-0', className)}
      {...props}
    >
      {children}
    </div>
  );
}

export function SecondaryDeck({
  className,
  children,
  ...props
}: FixedRegionWrapperProps) {
  return (
    <div
      data-linear-primitive="secondary-deck"
      data-layout-zone="SecondaryDeck"
      className={cn(
        'min-w-0 border-t border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-console)]',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

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
        'min-w-0 rounded-[var(--theme-panel-radius-md)] shadow-none',
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

export function FixedRegionGrid({
  header,
  primary,
  rail,
  secondary,
  railWidth = 'md',
  className,
  headerClassName,
  primaryClassName,
  railClassName,
  secondaryClassName,
  railTestId,
  secondaryTestId,
  children,
  ...props
}: LinearPrimitiveProps<HTMLDivElement> & {
  header?: React.ReactNode;
  primary?: React.ReactNode;
  rail?: React.ReactNode;
  secondary?: React.ReactNode;
  railWidth?: LinearRailWidth;
  headerClassName?: string;
  primaryClassName?: string;
  railClassName?: string;
  secondaryClassName?: string;
  railTestId?: string;
  secondaryTestId?: string;
}) {
  const primaryContent = primary ?? children;
  return (
    <div
      data-linear-primitive="fixed-region-grid"
      data-layout-contract="fixed-region-grid"
      className={cn('grid min-w-0 gap-0 overflow-hidden', className)}
      {...props}
    >
      {header ? (
        <div data-layout-zone="HeaderStrip" className={cn('min-w-0', headerClassName)}>
          {header}
        </div>
      ) : null}
      <div className={cn('grid min-w-0 gap-0', rail ? RAIL_GRID_TRACKS[railWidth] : '')}>
        <div
          data-linear-primitive="primary-work-region"
          data-layout-zone="PrimaryWorkRegion"
          className={cn('min-w-0', primaryClassName)}
        >
          {primaryContent}
        </div>
        {rail ? (
          <div
            data-linear-primitive="context-rail"
            data-layout-zone="ContextRail"
            data-testid={railTestId}
            className={cn(
              'flex min-w-0 flex-col divide-y divide-[color:var(--wolfy-divider)] overflow-hidden border-t border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-rail)] lg:border-l lg:border-t-0',
              railClassName,
            )}
          >
            {rail}
          </div>
        ) : null}
      </div>
      {secondary ? (
        <SecondaryDeck
          data-testid={secondaryTestId}
          className={secondaryClassName}
        >
          {secondary}
        </SecondaryDeck>
      ) : null}
    </div>
  );
}

export function ScrollPanel({
  zone = 'PrimaryWorkRegion',
  maxHeight,
  className,
  style,
  children,
  ...props
}: LinearPrimitiveProps<HTMLDivElement> & {
  zone?: LinearLayoutZone;
  maxHeight?: React.CSSProperties['maxHeight'];
}) {
  return (
    <div
      data-linear-primitive="scroll-panel"
      data-layout-zone={zone}
      className={cn('min-w-0 overflow-y-auto overscroll-contain no-scrollbar', className)}
      style={{ maxHeight, ...style }}
      {...props}
    >
      {children}
    </div>
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
        'flex min-h-11 w-full min-w-0 flex-wrap items-center gap-2 rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-2 text-[color:var(--wolfy-text-primary)] shadow-none',
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

export function CompactFilterBar({
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
      data-linear-primitive="compact-filter-bar"
      data-layout-zone="CommandBar"
      className={cn(
        'flex min-h-11 w-full min-w-0 flex-wrap items-center gap-2 rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-2.5 py-2 text-[color:var(--wolfy-text-primary)] shadow-none md:flex-nowrap md:px-3',
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
      data-layout-zone="RouteConsole"
      data-route-console="ResearchConsole"
      data-visual-tier="dominant"
      className={cn(
        'relative isolate flex w-full min-w-0 flex-col gap-3 overflow-hidden rounded-[var(--theme-panel-radius-lg)] border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-2.5 shadow-[var(--shadow-tight)] md:p-3',
        className,
      )}
      {...props}
    >
      {command}
      <div
        className={cn(
          'grid min-w-0 overflow-hidden rounded-[var(--theme-panel-radius-md)] border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-console)]',
          rail ? 'lg:grid-cols-[minmax(0,1fr)_320px]' : '',
        )}
      >
        <div className="min-w-0">{children}</div>
        {rail ? <div className="min-w-0 border-t border-[color:var(--wolfy-divider)] lg:border-l lg:border-t-0">{rail}</div> : null}
      </div>
    </div>
  );
}

function RailPanel({
  railWidth = 'md',
  className,
  children,
  ...props
}: LinearPrimitiveProps<HTMLElement> & {
  railWidth?: LinearRailWidth;
}) {
  return (
    <WolfyShellSurface
      data-linear-primitive="rail-panel"
      data-layout-zone="ContextRail"
      variant="rail"
      padding="sm"
      className={cn(
        'flex min-w-0 flex-col divide-y divide-[color:var(--wolfy-divider)] overflow-hidden',
        RAIL_WIDTHS[railWidth],
        className,
      )}
      {...props}
    >
      {children}
    </WolfyShellSurface>
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
    <RailPanel
      data-linear-primitive="context-rail"
      className={className}
      {...props}
    >
      {children}
    </RailPanel>
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

export function MetricStrip({
  items,
  className,
  ...props
}: Omit<LinearPrimitiveProps<HTMLDivElement>, 'children'> & {
  items: Array<{ label: React.ReactNode; value: React.ReactNode; key?: React.Key; testId?: string; className?: string }>;
}) {
  return (
    <div
      data-linear-primitive="metric-strip"
      className={cn(
        'grid min-w-0 gap-0 border-y border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] text-xs sm:grid-cols-3',
        className,
      )}
      {...props}
    >
      {items.map((item, index) => (
        <div
          key={item.key ?? index}
          className={cn(
            'min-w-0 px-3 py-2.5 sm:border-l sm:border-[color:var(--wolfy-divider)] sm:first:border-l-0',
            item.className,
          )}
          data-testid={item.testId}
        >
          <div className="truncate text-[11px] text-[color:var(--wolfy-text-muted)]">{item.label}</div>
          <div className="mt-0.5 truncate font-mono text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{item.value}</div>
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
          {open ? <ChevronDown className="size-3.5" aria-hidden="true" /> : <ChevronRight className="size-3.5" aria-hidden="true" />}
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
  levels: Array<{
    label: React.ReactNode;
    value: React.ReactNode;
    tone?: 'neutral' | 'up' | 'down';
    key?: React.Key;
    testId?: string;
    className?: string;
    valueClassName?: string;
    valueStyle?: React.CSSProperties;
  }>;
}) {
  return (
    <div
      data-linear-primitive="key-level-strip"
      className={cn('grid min-w-0 gap-2 border-y border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] p-2 sm:grid-cols-3', className)}
      {...props}
    >
      {levels.map((level, index) => (
        <div key={level.key ?? index} className={cn('min-w-0 px-2 py-1', level.className)} data-testid={level.testId}>
          <div className="text-[11px] text-[color:var(--wolfy-text-muted)]">{level.label}</div>
          <div
            className={cn(
              'mt-0.5 truncate font-mono text-sm font-semibold',
              level.valueClassName
                ? level.valueClassName
                : [
                  level.tone === 'up' && 'text-[color:var(--wolfy-market-up)]',
                  level.tone === 'down' && 'text-[color:var(--wolfy-market-down)]',
                  (!level.tone || level.tone === 'neutral') && 'text-[color:var(--wolfy-text-primary)]',
                ],
            )}
            style={level.valueStyle}
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
  emptyTestId,
  className,
  ...props
}: Omit<LinearPrimitiveProps<HTMLDivElement>, 'children'> & {
  items: Array<{ title: React.ReactNode; meta?: React.ReactNode; status?: React.ReactNode; key?: React.Key; testId?: string }>;
  emptyText?: React.ReactNode;
  emptyTestId?: string;
}) {
  return (
    <div
      data-linear-primitive="catalyst-rows"
      className={cn('divide-y divide-[color:var(--wolfy-divider)] text-xs', className)}
      {...props}
    >
      {items.length ? items.map((item, index) => (
        <div key={item.key ?? index} className="grid min-w-0 gap-1 py-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center" data-testid={item.testId}>
          <div className="min-w-0">
            <p className="truncate text-[color:var(--wolfy-text-primary)]">{item.title}</p>
            {item.meta ? <p className="mt-0.5 truncate text-[color:var(--wolfy-text-muted)]">{item.meta}</p> : null}
          </div>
          {item.status ? <div className="text-[color:var(--wolfy-text-secondary)]">{item.status}</div> : null}
        </div>
      )) : (
        <div className="py-2 text-[color:var(--wolfy-text-muted)]" data-testid={emptyTestId}>{emptyText}</div>
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

export function DataRows({ className, children, ...props }: LinearPrimitiveProps<HTMLDivElement>) {
  return (
    <div
      data-linear-primitive="data-rows"
      className={cn('divide-y divide-[color:var(--wolfy-divider)] text-xs text-[color:var(--wolfy-text-secondary)]', className)}
      {...props}
    >
      {children}
    </div>
  );
}

export function DenseRows(props: LinearPrimitiveProps<HTMLDivElement>) {
  return <DataRows data-linear-primitive="dense-rows" {...props} />;
}

export function FloatingDetailPanel({
  className,
  children,
  ...props
}: LinearPrimitiveProps<HTMLElement>) {
  return (
    <WolfyShellSurface
      data-linear-primitive="floating-detail-panel"
      data-layout-zone="FloatingPanel"
      variant="rail"
      padding="md"
      className={cn('max-h-[min(72vh,42rem)] overflow-y-auto no-scrollbar', className)}
      {...props}
    >
      {children}
    </WolfyShellSurface>
  );
}
