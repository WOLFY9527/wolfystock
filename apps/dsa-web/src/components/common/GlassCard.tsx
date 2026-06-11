import React from 'react';
import { cn } from '../../utils/cn';

type GlassCardProps = React.HTMLAttributes<HTMLElement> & {
  as?: React.ElementType;
  children: React.ReactNode;
};

// Radius aligned to the shared --wolfy-radius-lg (16px) so glass surfaces match Card/SectionShell.
const GLASS_CARD_BASE_CLASS = 'rounded-2xl border border-white/5 bg-white/[0.02] backdrop-blur-sm';

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
