import type React from 'react';
import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
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
 * Prefer RoughResearchSection + row primitives for new migrations.
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

/**
 * Low-chrome research section for de-cardified migrations.
 * Uses divider hierarchy instead of nested bordered cards.
 */
export function RoughResearchSection({
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
    <section
      data-testid={dataTestId}
      data-rough-variant="research-section"
      data-research-frame="section"
      className={cn(
        'research-rough-section flex min-w-0 flex-col border-b border-[color:var(--wolfy-divider)] last:border-b-0',
        className,
      )}
    >
      <div className="flex min-w-0 items-start justify-between gap-3 px-4 py-3 md:px-5">
        <div className="min-w-0">
          {eyebrow ? (
            <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">{eyebrow}</p>
          ) : null}
          <h2 className="mt-0.5 text-sm font-medium text-[color:var(--wolfy-text-primary)]">{title}</h2>
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      <div className="min-w-0 px-4 pb-3 md:px-5">{children}</div>
    </section>
  );
}

/**
 * Divided research rows without per-item card chrome.
 */
export function RoughResearchRows({
  rows,
  emptyText,
  className,
  'data-testid': dataTestId,
}: {
  rows: Array<{
    key?: React.Key;
    leading?: React.ReactNode;
    title?: React.ReactNode;
    body?: React.ReactNode;
    trailing?: React.ReactNode;
  }>;
  emptyText?: React.ReactNode;
  className?: string;
  'data-testid'?: string;
}) {
  if (!rows.length) {
    return <TerminalEmptyState data-testid={dataTestId}>{emptyText ?? '暂无可展示条目。'}</TerminalEmptyState>;
  }

  return (
    <div
      data-testid={dataTestId}
      data-rough-variant="research-rows"
      data-research-frame="content"
      className={cn('divide-y divide-[color:var(--wolfy-divider)]', className)}
    >
      {rows.map((row, index) => (
        <div
          key={row.key ?? index}
          className="flex min-w-0 items-start justify-between gap-3 py-2.5"
        >
          <div className="min-w-0 flex-1">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              {row.leading ? <div className="shrink-0">{row.leading}</div> : null}
              {row.title ? (
                <div className="text-sm text-[color:var(--wolfy-text-primary)]">{row.title}</div>
              ) : null}
            </div>
            {row.body ? (
              <div className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">{row.body}</div>
            ) : null}
          </div>
          {row.trailing ? <div className="shrink-0">{row.trailing}</div> : null}
        </div>
      ))}
    </div>
  );
}

/**
 * Grouped evidence rows under a quiet group label.
 */
export function RoughEvidenceGroup({
  label,
  children,
  className,
  'data-testid': dataTestId,
}: {
  label?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  'data-testid'?: string;
}) {
  return (
    <div
      data-testid={dataTestId}
      data-rough-variant="evidence-group"
      data-research-frame="content"
      className={cn('research-rough-evidence-group min-w-0', className)}
    >
      {label ? (
        <p className="mb-1.5 text-[11px] font-medium text-[color:var(--wolfy-text-muted)]">{label}</p>
      ) : null}
      <div className="min-w-0 border-t border-[color:var(--wolfy-divider)]">{children}</div>
    </div>
  );
}

/**
 * Compact key-value evidence (alias-compatible extension of RoughKeyValueRows presentation).
 */
export function RoughCompactKeyValue({
  rows,
  emptyText,
  className,
  'data-testid': dataTestId,
}: {
  rows: Array<{
    key: React.Key;
    label: React.ReactNode;
    value: React.ReactNode;
    detail?: React.ReactNode;
  }>;
  emptyText?: React.ReactNode;
  className?: string;
  'data-testid'?: string;
}) {
  if (!rows.length) {
    return <TerminalEmptyState data-testid={dataTestId}>{emptyText ?? '暂无可展示条目。'}</TerminalEmptyState>;
  }

  return (
    <dl
      data-testid={dataTestId}
      data-rough-variant="compact-key-value"
      data-research-frame="content"
      className={cn('divide-y divide-[color:var(--wolfy-divider)]', className)}
    >
      {rows.map((row) => (
        <div
          key={row.key}
          className="grid gap-1 py-2 sm:grid-cols-[minmax(0,9rem)_minmax(0,1fr)] sm:gap-3"
        >
          <dt className="text-[11px] text-[color:var(--wolfy-text-muted)]">{row.label}</dt>
          <dd className="min-w-0">
            <div className="break-words font-mono text-sm text-[color:var(--wolfy-text-primary)]">{row.value}</div>
            {row.detail ? (
              <div className="mt-0.5 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{row.detail}</div>
            ) : null}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/**
 * Disclosure section for secondary research detail without nested card chrome.
 */
export function RoughDisclosureSection({
  title,
  summary,
  defaultOpen = false,
  children,
  className,
  'data-testid': dataTestId,
}: {
  title: React.ReactNode;
  summary?: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
  className?: string;
  'data-testid'?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const titleText = typeof title === 'string' ? title : '';

  return (
    <div
      data-testid={dataTestId}
      data-rough-variant="disclosure-section"
      data-research-frame="content"
      className={cn(
        'border-t border-[color:var(--wolfy-divider)] bg-transparent px-0 py-2.5',
        className,
      )}
    >
      <div className="flex min-w-0 items-center justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-xs font-medium text-[color:var(--wolfy-text-secondary)]">{title}</h3>
          {summary ? (
            <p className="mt-0.5 truncate text-[11px] text-[color:var(--wolfy-text-muted)]">{summary}</p>
          ) : null}
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
      {open ? (
        <div className="mt-2 border-t border-[color:var(--wolfy-divider)] pt-2">{children}</div>
      ) : null}
    </div>
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
