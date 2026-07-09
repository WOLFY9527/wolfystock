import type React from 'react';
import { cn } from '../../utils/cn';

type WorkspacePageHeaderProps = {
  eyebrow?: React.ReactNode;
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
  contentClassName?: string;
  titleClassName?: string;
  descriptionClassName?: string;
  /**
   * `compact` is for boundary/gate surfaces that need route identity without
   * marketing-scale hero typography. Default leaves normal workbench headers unchanged.
   */
  density?: 'default' | 'compact';
};

export const WorkspacePageHeader: React.FC<WorkspacePageHeaderProps> = ({
  eyebrow,
  title,
  description,
  actions,
  children,
  className,
  contentClassName,
  titleClassName,
  descriptionClassName,
  density = 'default',
}) => (
  <header
    className={cn(
      'workspace-header-panel',
      density === 'compact' && 'workspace-header-panel--compact',
      className,
    )}
    data-header-density={density}
  >
    <div className={cn('workspace-header-layout', contentClassName)}>
      <div className="workspace-header-copy">
        {eyebrow ? (
          <p className="workspace-header-eyebrow">{eyebrow}</p>
        ) : null}
        <h1 className={cn('workspace-header-title', titleClassName)}>
          {title}
        </h1>
        {description ? (
          <p className={cn('workspace-header-description', descriptionClassName)}>
            {description}
          </p>
        ) : null}
      </div>
      {actions ? (
        <div className="workspace-header-actions workspace-header-actions--end">
          {actions}
        </div>
      ) : null}
    </div>
    {children ? <div className="mt-4 space-y-3 md:mt-5">{children}</div> : null}
  </header>
);
