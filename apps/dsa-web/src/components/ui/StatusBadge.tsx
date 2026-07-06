import { cn } from '../../utils/cn';
import {
  getStatusLabel,
  getStatusTone,
  normalizeStatus,
  type StatusBadgeProps,
  type StatusBadgeTone,
} from './StatusBadge.helpers';

const SIZE_CLASS: Record<NonNullable<StatusBadgeProps['size']>, string> = {
  sm: 'min-h-6 px-2.5 py-0.5 text-[11px]',
  md: 'min-h-7 px-3 py-1 text-sm',
};

const SOFT_TONE_CLASS: Record<StatusBadgeTone, string> = {
  success: 'border-[color:var(--state-success-border)] bg-[var(--state-success-bg)] text-[color:var(--state-success-text)]',
  danger: 'border-[color:var(--state-danger-border)] bg-[var(--state-danger-bg)] text-[color:var(--state-danger-text)]',
  warning: 'border-[color:var(--state-warning-border)] bg-[var(--state-warning-bg)] text-[color:var(--state-warning-text)]',
  info: 'border-[color:var(--state-info-border)] bg-[var(--state-info-bg)] text-[color:var(--state-info-text)]',
  default: 'border-[color:var(--line)] bg-[var(--wolfy-surface-input)] text-[color:var(--wolfy-text-muted)]',
};

const SOLID_TONE_CLASS: Record<StatusBadgeTone, string> = {
  success: 'border-[color:var(--state-success-border)] bg-[var(--state-success-text)] text-white',
  danger: 'border-[color:var(--state-danger-border)] bg-[var(--state-danger-text)] text-white',
  warning: 'border-[color:var(--state-warning-border)] bg-[var(--state-warning-text)] text-white',
  info: 'border-[color:var(--state-info-border)] bg-[var(--state-info-text)] text-white',
  default: 'border-[color:var(--line-strong)] bg-[var(--ink-soft)] text-white',
};

const OUTLINE_TONE_CLASS: Record<StatusBadgeTone, string> = {
  success: 'border-[color:var(--state-success-border)] bg-transparent text-[color:var(--state-success-text)]',
  danger: 'border-[color:var(--state-danger-border)] bg-transparent text-[color:var(--state-danger-text)]',
  warning: 'border-[color:var(--state-warning-border)] bg-transparent text-[color:var(--state-warning-text)]',
  info: 'border-[color:var(--state-info-border)] bg-transparent text-[color:var(--state-info-text)]',
  default: 'border-[color:var(--line)] bg-transparent text-[color:var(--wolfy-text-muted)]',
};

export function StatusBadge({
  status,
  label,
  size = 'sm',
  variant = 'soft',
  className,
}: StatusBadgeProps) {
  const normalized = normalizeStatus(status);
  const tone = getStatusTone(status);
  const variantClass = variant === 'solid'
    ? SOLID_TONE_CLASS[tone]
    : variant === 'outline'
      ? OUTLINE_TONE_CLASS[tone]
      : SOFT_TONE_CLASS[tone];

  return (
    <span
      data-status={normalized}
      data-tone={tone}
      data-variant={variant}
      className={cn(
        'inline-flex items-center justify-center rounded-full border font-medium leading-none whitespace-nowrap',
        SIZE_CLASS[size],
        variantClass,
        className,
      )}
    >
      {label || getStatusLabel(status)}
    </span>
  );
}
