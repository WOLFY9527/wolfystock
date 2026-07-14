import type React from 'react';
import { cn } from '../../../utils/cn';
import { densityDataAttributes, normalizeResearchDensityMode } from './researchDensity';
import { ResearchFrame } from './ResearchFrame';
import { LeadText, MetaLabel, ObservationTitle } from './ResearchTypography';
import type {
  ResearchDensityMode,
  ResearchLocale,
  ResearchObservationFact,
} from './types';

export type ObservationHeadProps = {
  eyebrow?: React.ReactNode;
  title: React.ReactNode;
  titleAs?: keyof React.JSX.IntrinsicElements;
  lead?: React.ReactNode;
  known?: ResearchObservationFact[] | React.ReactNode;
  unknown?: ResearchObservationFact[] | React.ReactNode;
  changing?: ResearchObservationFact[] | React.ReactNode;
  contradictory?: ResearchObservationFact[] | React.ReactNode;
  /** Optional status adjacency (readiness chip, regime pill, etc.). */
  status?: React.ReactNode;
  density?: ResearchDensityMode;
  locale?: ResearchLocale;
  className?: string;
  children?: React.ReactNode;
  'data-testid'?: string;
};

const FACT_LABELS: Record<
  'known' | 'unknown' | 'changing' | 'contradictory',
  Record<ResearchLocale, string>
> = {
  known: { zh: '已知', en: 'Known' },
  unknown: { zh: '未知', en: 'Unknown' },
  changing: { zh: '变化中', en: 'Changing' },
  contradictory: { zh: '矛盾点', en: 'Contradictory' },
};

function renderFactBlock(
  kind: keyof typeof FACT_LABELS,
  value: ResearchObservationFact[] | React.ReactNode | undefined,
  locale: ResearchLocale,
): React.ReactNode {
  if (value == null || value === false) return null;

  if (Array.isArray(value)) {
    if (!value.length) return null;
    return (
      <div
        className="research-observation-fact-block"
        data-observation-fact={kind}
      >
        <MetaLabel className="research-observation-fact-label">
          {FACT_LABELS[kind][locale]}
        </MetaLabel>
        <ul className="research-observation-fact-list">
          {value.map((item, index) => (
            <li key={item.key ?? index} className="research-observation-fact-item">
              {item.label ? (
                <span className="research-observation-fact-item-label">{item.label}</span>
              ) : null}
              <span className="research-observation-fact-item-body">{item.body}</span>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <div
      className="research-observation-fact-block"
      data-observation-fact={kind}
    >
      <MetaLabel className="research-observation-fact-label">
        {FACT_LABELS[kind][locale]}
      </MetaLabel>
      <div className="research-observation-fact-freeform">{value}</div>
    </div>
  );
}

/**
 * Page-level research conclusion surface.
 * Supports: eyebrow → primary observation → lead → known/unknown/changing/contradictory.
 * No investment recommendation props or language.
 */
export function ObservationHead({
  eyebrow,
  title,
  titleAs,
  lead,
  known,
  unknown,
  changing,
  contradictory,
  status,
  density = 'research',
  locale = 'zh',
  className,
  children,
  'data-testid': dataTestId = 'observation-head',
}: ObservationHeadProps) {
  const resolvedDensity = normalizeResearchDensityMode(density);
  const factEntries: Array<{ key: string; node: React.ReactNode }> = [
    { key: 'known', node: renderFactBlock('known', known, locale) },
    { key: 'unknown', node: renderFactBlock('unknown', unknown, locale) },
    { key: 'changing', node: renderFactBlock('changing', changing, locale) },
    { key: 'contradictory', node: renderFactBlock('contradictory', contradictory, locale) },
  ].filter((entry) => entry.node != null);

  return (
    <ResearchFrame
      role="section"
      parentDepth={1}
      density={resolvedDensity}
      as="header"
      data-testid={dataTestId}
      data-research-anatomy="observation-head"
      aria-labelledby={`${dataTestId}-title`}
      className={cn('research-observation-head', className)}
      {...densityDataAttributes(resolvedDensity)}
    >
      <div className="research-observation-head__primary">
        {eyebrow ? (
          <MetaLabel className="research-observation-head__eyebrow">{eyebrow}</MetaLabel>
        ) : null}
        <ObservationTitle
          id={`${dataTestId}-title`}
          as={titleAs}
          className="research-observation-head__title"
        >
          {title}
        </ObservationTitle>
        {status ? (
          <div className="research-observation-head__status" data-observation-status>
            {status}
          </div>
        ) : null}
        {lead ? (
          <LeadText className="research-observation-head__lead">{lead}</LeadText>
        ) : null}
      </div>

      {factEntries.length > 0 ? (
        <div
          className="research-observation-head__facts"
          data-observation-facts
        >
          {factEntries.map((entry) => (
            <div key={entry.key}>{entry.node}</div>
          ))}
        </div>
      ) : null}

      {children ? (
        <div className="research-observation-head__extra">{children}</div>
      ) : null}
    </ResearchFrame>
  );
}
