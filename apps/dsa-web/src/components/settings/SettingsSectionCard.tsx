import type React from 'react';
import { cn } from '../../utils/cn';

interface SettingsSectionCardProps {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  actionsClassName?: string;
}

export const SettingsSectionCard: React.FC<SettingsSectionCardProps> = ({
  title,
  actions,
  children,
  className = '',
  actionsClassName = '',
}) => {
  return (
    <div className={cn('bg-[var(--wolfy-surface-console)] backdrop-blur-2xl border border-[color:var(--wolfy-border-subtle)] rounded-2xl p-5 md:p-6', className)}>
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 space-y-1">
          <h2 className="text-[1.125rem] font-normal tracking-[-0.02em] text-foreground md:text-[1.25rem]">{title}</h2>
        </div>
        {actions ? <div className={cn('flex shrink-0 flex-wrap items-center gap-2 sm:justify-end', actionsClassName)}>{actions}</div> : null}
      </div>
      <div className="space-y-5">{children}</div>
    </div>
  );
};
