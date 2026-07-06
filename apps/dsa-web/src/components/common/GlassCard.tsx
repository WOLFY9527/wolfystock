import React from 'react';
import { cn } from '../../utils/cn';

type GlassCardProps = React.HTMLAttributes<HTMLElement> & {
  as?: React.ElementType;
  children: React.ReactNode;
};

const GLASS_CARD_BASE_CLASS = 'rounded-[var(--theme-panel-radius-md)] border border-[color:var(--line)] bg-[var(--wolfy-surface-input)]';

export const GlassCard: React.FC<GlassCardProps> = ({
  as: Component = 'div',
  children,
  className,
  ...props
}) => React.createElement(
  Component,
  {
    ...props,
    className: cn(GLASS_CARD_BASE_CLASS, className),
  },
  children,
);
