import React from 'react';
import { cn } from '../../utils/cn';

type BadgeVariant = 'default' | 'success' | 'warning' | 'danger' | 'info' | 'history';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: 'sm' | 'md';
  className?: string;
}

/**
 * Badge component with multiple variants owned by shared consumer state tokens.
 */
export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'default',
  size = 'sm',
  className = '',
}) => {
  const sizeStyles = size === 'sm' ? 'min-h-6 px-2.5 py-0.5 text-[11px]' : 'min-h-7 px-3 py-1 text-sm';

  return (
    <span
      data-variant={variant}
      data-control-state="readonly"
      className={cn(
        'theme-badge inline-flex items-center justify-center gap-1 border font-medium leading-none',
        sizeStyles,
        className,
      )}
    >
      {children}
    </span>
  );
};
