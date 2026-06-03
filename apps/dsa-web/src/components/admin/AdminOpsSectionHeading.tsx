import type React from 'react';
import { TerminalSectionHeader } from '../terminal';
import { cn } from '../../utils/cn';

type AdminOpsSectionHeadingProps = {
  eyebrow: string;
  title: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
  dataTestId?: string;
};

const AdminOpsSectionHeading: React.FC<AdminOpsSectionHeadingProps> = ({
  eyebrow,
  title,
  description,
  action,
  className,
  dataTestId,
}) => (
  <div data-testid={dataTestId} className={cn('col-span-12 min-w-0', className)}>
    <TerminalSectionHeader eyebrow={eyebrow} title={title} action={action} />
    {description ? (
      <p className="mt-2 text-[11px] leading-5 text-white/46">
        {description}
      </p>
    ) : null}
  </div>
);

export default AdminOpsSectionHeading;
