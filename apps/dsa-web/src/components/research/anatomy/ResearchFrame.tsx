import type React from 'react';
import { cn } from '../../../utils/cn';
import {
  computeFrameDepth,
  researchFrameDataAttributes,
  type ResearchSurfaceScope,
} from './researchNesting';
import type { ResearchDensityMode, ResearchFrameRole } from './types';
import { densityDataAttributes, normalizeResearchDensityMode } from './researchDensity';

type ResearchFrameProps = React.HTMLAttributes<HTMLElement> & {
  role?: ResearchFrameRole;
  /** Parent contributing frame depth; omit at the outermost board. */
  parentDepth?: number;
  density?: ResearchDensityMode;
  scope?: ResearchSurfaceScope;
  as?: 'div' | 'section' | 'article' | 'aside' | 'header';
  children?: React.ReactNode;
  'data-testid'?: string;
};

/**
 * Lightweight frame marker for nesting budget and density adoption.
 * Does not introduce heavy card chrome — board/section use restrained surfaces;
 * content role is divider-friendly and unframed.
 */
export function ResearchFrame({
  role = 'section',
  parentDepth = 0,
  density,
  scope = 'consumer',
  as = 'section',
  className,
  children,
  'data-testid': dataTestId,
  ...props
}: ResearchFrameProps) {
  const depth = computeFrameDepth(parentDepth, role);
  const Tag = as;
  const resolvedDensity = density ? normalizeResearchDensityMode(density) : undefined;

  return (
    <Tag
      data-testid={dataTestId}
      data-research-anatomy="frame"
      {...researchFrameDataAttributes(role, depth, scope)}
      {...(resolvedDensity ? densityDataAttributes(resolvedDensity) : {})}
      className={cn(
        'research-frame min-w-0',
        role === 'board' && 'research-frame--board',
        role === 'section' && 'research-frame--section',
        role === 'content' && 'research-frame--content',
        className,
      )}
      {...props}
    >
      {children}
    </Tag>
  );
}
