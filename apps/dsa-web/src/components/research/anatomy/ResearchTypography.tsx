import type React from 'react';
import { cn } from '../../../utils/cn';

type TypographyBaseProps = {
  as?: keyof React.JSX.IntrinsicElements;
  className?: string;
  children: React.ReactNode;
  id?: string;
  'data-testid'?: string;
};

function renderTypography(
  defaultTag: keyof React.JSX.IntrinsicElements,
  roleClass: string,
  roleAttr: string,
  {
    as,
    className,
    children,
    id,
    'data-testid': dataTestId,
  }: TypographyBaseProps,
) {
  const Tag = (as || defaultTag) as React.ElementType;
  return (
    <Tag
      id={id}
      data-research-type-role={roleAttr}
      data-testid={dataTestId}
      className={cn(roleClass, className)}
    >
      {children}
    </Tag>
  );
}

/** Restrained serif display hierarchy for the single page observation title. */
export function ObservationTitle(props: TypographyBaseProps) {
  return renderTypography('h1', 'research-type-observation-title', 'observation-title', props);
}

/** Sans operational section hierarchy. */
export function SectionTitle(props: TypographyBaseProps) {
  return renderTypography('h2', 'research-type-section-title', 'section-title', props);
}

/** Compact meta / eyebrow labels. */
export function MetaLabel(props: TypographyBaseProps) {
  return renderTypography('p', 'research-type-meta-label', 'meta-label', props);
}

/** Mono metric and data values. */
export function MetricValue(props: TypographyBaseProps) {
  return renderTypography('span', 'research-type-metric-value', 'metric-value', props);
}

/** Readable lead / conclusion support copy. */
export function LeadText(props: TypographyBaseProps) {
  return renderTypography('p', 'research-type-lead-text', 'lead-text', props);
}
