import { useState, type ReactNode } from 'react';
import {
  BookmarkPlus,
  ChevronDown,
  ChevronRight,
  History,
  Info,
  LineChart,
  MoreHorizontal,
} from 'lucide-react';
import type { ScannerLabeledValue } from '../../types/scanner';

export type ScannerDisclosureIcon = 'info' | 'history' | 'backtest' | 'watchlist' | 'more';

function normalizeLabel(label?: string | null): string {
  return (label || '').trim().toLowerCase();
}

function safeScannerFieldLabel(label: string): string {
  const normalized = normalizeLabel(label);
  if (normalized === 'entry range' || normalized === 'entry' || normalized === '建仓' || normalized === '入场' || normalized === 'buy') {
    return '观察区';
  }
  if (normalized === 'target price' || normalized === 'target' || normalized === '目标' || normalized === '目标价') {
    return '参考区间';
  }
  if (normalized === 'stop loss' || normalized === '止损' || normalized === '止损位' || normalized === 'stop') {
    return '风险边界';
  }
  return label;
}

export function FieldChip({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex min-w-0 max-w-full items-center gap-1 rounded-md border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] px-1.5 py-0.5 text-[10px] font-medium text-[color:var(--wolfy-text-secondary)]">
      <span className="shrink-0 text-[color:var(--wolfy-text-muted)]">{safeScannerFieldLabel(label)}</span>
      <span className="min-w-0 truncate">{value}</span>
    </span>
  );
}

export function LabeledValueGrid({
  items,
  empty,
}: {
  items: ScannerLabeledValue[];
  empty: string;
}) {
  if (!items.length) {
    return <p className="text-xs text-[color:var(--wolfy-text-muted)]">{empty}</p>;
  }
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <FieldChip key={`${item.label}-${item.value}`} label={item.label} value={item.value} />
      ))}
    </div>
  );
}

export function NotesList({ notes, empty }: { notes: string[]; empty: string }) {
  if (!notes.length) {
    return <p className="text-xs text-[color:var(--wolfy-text-muted)]">{empty}</p>;
  }
  return (
    <ul className="space-y-1">
      {notes.map((note) => (
        <li key={note} className="text-xs leading-relaxed text-[color:var(--wolfy-text-secondary)]">
          {note}
        </li>
      ))}
    </ul>
  );
}

export function AdvancedDisclosure({
  title,
  summary,
  icon = 'info',
  children,
  testId,
  defaultOpen = false,
  open: controlledOpen,
  onToggle,
}: {
  title: string;
  summary?: string;
  icon?: ScannerDisclosureIcon;
  children: ReactNode;
  testId: string;
  defaultOpen?: boolean;
  open?: boolean;
  onToggle?: (nextOpen: boolean) => void;
}) {
  const [uncontrolledOpen, setUncontrolledOpen] = useState(defaultOpen);
  const open = controlledOpen ?? uncontrolledOpen;
  const iconClassName = 'size-3.5 shrink-0 text-[color:var(--wolfy-text-muted)]';
  const leadingIcon = {
    info: <Info className={iconClassName} aria-hidden="true" />,
    history: <History className={iconClassName} aria-hidden="true" />,
    backtest: <LineChart className={iconClassName} aria-hidden="true" />,
    watchlist: <BookmarkPlus className={iconClassName} aria-hidden="true" />,
    more: <MoreHorizontal className={iconClassName} aria-hidden="true" />,
  }[icon];
  const actionLabel = open
    ? (title.match(/[A-Za-z]/) ? `Collapse ${title}` : `收起 ${title}`)
    : (title.match(/[A-Za-z]/) ? `Expand ${title}` : `展开 ${title}`);

  return (
    <section
      data-testid={testId}
      className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-2.5 py-2 text-xs text-[color:var(--wolfy-text-secondary)]"
    >
      <div className="flex min-w-0 items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          {leadingIcon}
          <div className="min-w-0">
            <h3 className="truncate text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{title}</h3>
            {summary ? <p className="mt-0.5 truncate text-[11px] text-[color:var(--wolfy-text-muted)]">{summary}</p> : null}
          </div>
        </div>
        <button
          type="button"
          aria-expanded={open}
          aria-label={actionLabel}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-console)] px-2 py-1 text-[11px] text-[color:var(--wolfy-text-secondary)] hover:border-[color:var(--wolfy-border-subtle)] hover:text-[color:var(--wolfy-text-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--wolfy-accent)]"
          onClick={() => {
            const nextOpen = !open;
            if (controlledOpen == null) {
              setUncontrolledOpen(nextOpen);
            }
            onToggle?.(nextOpen);
          }}
        >
          {open ? <ChevronDown className="size-3.5" aria-hidden="true" /> : <ChevronRight className="size-3.5" aria-hidden="true" />}
          <span>{open ? (title.match(/[A-Za-z]/) ? 'Collapse' : '收起') : (title.match(/[A-Za-z]/) ? 'Expand' : '展开')}</span>
        </button>
      </div>
      {open ? <div className="mt-2">{children}</div> : null}
    </section>
  );
}
