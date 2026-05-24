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
  success: 'border-emerald-400/25 bg-emerald-500/10 text-emerald-200',
  danger: 'border-rose-400/30 bg-rose-500/10 text-rose-200',
  warning: 'border-amber-300/30 bg-amber-400/12 text-amber-100',
  info: 'border-sky-400/25 bg-sky-500/10 text-sky-200',
  default: 'border-white/10 bg-white/[0.05] text-white/68',
};

const SOLID_TONE_CLASS: Record<StatusBadgeTone, string> = {
  success: 'border-emerald-400/55 bg-emerald-500 text-emerald-950',
  danger: 'border-rose-400/55 bg-rose-500 text-rose-50',
  warning: 'border-amber-300/55 bg-amber-400 text-amber-950',
  info: 'border-sky-400/55 bg-sky-500 text-sky-950',
  default: 'border-white/18 bg-white/12 text-white',
};

const OUTLINE_TONE_CLASS: Record<StatusBadgeTone, string> = {
  success: 'border-emerald-400/35 bg-transparent text-emerald-200',
  danger: 'border-rose-400/35 bg-transparent text-rose-200',
  warning: 'border-amber-300/35 bg-transparent text-amber-100',
  info: 'border-sky-400/35 bg-transparent text-sky-200',
  default: 'border-white/12 bg-transparent text-white/72',
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
