import type React from 'react';
import { Button } from './Button';
import { cn } from '../../utils/cn';

interface SegmentedControlOption {
  value: string;
  label: React.ReactNode;
}

interface SegmentedControlProps {
  label?: string;
  value: string;
  options: SegmentedControlOption[];
  onChange: (value: string) => void;
  className?: string;
  listClassName?: string;
  buttonClassName?: string;
  activeButtonClassName?: string;
  inactiveButtonClassName?: string;
  size?: 'sm' | 'md';
}

export const SegmentedControl: React.FC<SegmentedControlProps> = ({
  label,
  value,
  options,
  onChange,
  className,
  listClassName,
  buttonClassName,
  activeButtonClassName,
  inactiveButtonClassName,
  size = 'sm',
}) => (
  <div className={cn('space-y-2 min-w-0', className)}>
    {label ? <p className="label-uppercase text-secondary-text">{label}</p> : null}
    <div className={cn('theme-panel-subtle ui-scroll-x-quiet flex min-w-0 max-w-full items-center gap-1 rounded-[var(--theme-panel-radius-md)] p-1', listClassName)}>
      {options.map((option) => {
        const active = option.value === value;
        return (
          <Button
            key={option.value}
            type="button"
            variant={active ? 'secondary' : 'ghost'}
            size={size}
            aria-pressed={active}
            onClick={() => onChange(option.value)}
            className={cn(
              'min-w-0 shrink-0 flex-1 text-secondary-text',
              active
                ? 'bg-[var(--pill-active-bg)] text-foreground shadow-soft-card'
                : 'border-transparent hover:bg-[var(--overlay-hover)] hover:text-foreground',
              buttonClassName,
              active ? activeButtonClassName : inactiveButtonClassName,
            )}
          >
            <span className="ui-truncate block w-full">{option.label}</span>
          </Button>
        );
      })}
    </div>
  </div>
);
