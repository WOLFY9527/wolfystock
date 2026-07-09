import type React from 'react';
import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '../../../utils/cn';
import { densityDataAttributes, normalizeResearchDensityMode } from './researchDensity';
import { MetaLabel, SectionTitle } from './ResearchTypography';
import type {
  ResearchDensityMode,
  ResearchLocale,
  ResearchRiskLimitItem,
  ResearchRiskLimitsPlacement,
} from './types';

export type ResearchRiskLimitsProps = {
  /** What current evidence cannot establish. */
  cannotEstablish?: ResearchRiskLimitItem[] | React.ReactNode[];
  /** Invalidation conditions. */
  invalidation?: ResearchRiskLimitItem[] | React.ReactNode[];
  /** Missing evidence. */
  missingEvidence?: ResearchRiskLimitItem[] | React.ReactNode[];
  /** Model limitations. */
  modelLimitations?: ResearchRiskLimitItem[] | React.ReactNode[];
  /** Data limitations. */
  dataLimitations?: ResearchRiskLimitItem[] | React.ReactNode[];
  /** Confidence cap where available (display only; does not invent confidence). */
  confidenceCap?: React.ReactNode;
  placement?: ResearchRiskLimitsPlacement;
  density?: ResearchDensityMode;
  locale?: ResearchLocale;
  title?: React.ReactNode;
  defaultOpen?: boolean;
  className?: string;
  'data-testid'?: string;
};

type LimitGroupKey =
  | 'cannotEstablish'
  | 'invalidation'
  | 'missingEvidence'
  | 'modelLimitations'
  | 'dataLimitations';

const GROUP_LABELS: Record<LimitGroupKey, Record<ResearchLocale, string>> = {
  cannotEstablish: {
    zh: '当前证据不能成立',
    en: 'Current evidence cannot establish',
  },
  invalidation: {
    zh: '失效条件',
    en: 'Invalidation conditions',
  },
  missingEvidence: {
    zh: '缺失证据',
    en: 'Missing evidence',
  },
  modelLimitations: {
    zh: '模型限制',
    en: 'Model limitations',
  },
  dataLimitations: {
    zh: '数据限制',
    en: 'Data limitations',
  },
};

const DEFAULT_TITLE: Record<ResearchLocale, string> = {
  zh: '研究限制',
  en: 'Research limits',
};

function normalizeItems(
  items: ResearchRiskLimitItem[] | React.ReactNode[] | undefined,
): ResearchRiskLimitItem[] {
  if (!items?.length) return [];
  return items.map((item, index) => {
    if (item != null && typeof item === 'object' && 'body' in (item as ResearchRiskLimitItem)) {
      return item as ResearchRiskLimitItem;
    }
    return { key: index, body: item as React.ReactNode };
  });
}

function LimitList({
  items,
  emptyHidden = true,
}: {
  items: ResearchRiskLimitItem[];
  emptyHidden?: boolean;
}) {
  if (!items.length) {
    return emptyHidden ? null : null;
  }
  return (
    <ul className="research-risk-limits__list">
      {items.map((item, index) => (
        <li key={item.key ?? index} className="research-risk-limits__item">
          {item.body}
        </li>
      ))}
    </ul>
  );
}

/**
 * Reusable research-limits composition surface.
 * Suited for context rail, lower disclosure, or compact research summary.
 * Avoids warning-card sprawl — uses divided rows and quiet chrome.
 */
export function ResearchRiskLimits({
  cannotEstablish,
  invalidation,
  missingEvidence,
  modelLimitations,
  dataLimitations,
  confidenceCap,
  placement = 'summary',
  density = 'research',
  locale = 'zh',
  title,
  defaultOpen = placement !== 'disclosure',
  className,
  'data-testid': dataTestId = 'research-risk-limits',
}: ResearchRiskLimitsProps) {
  const resolvedDensity = normalizeResearchDensityMode(density);
  const resolvedTitle = title ?? DEFAULT_TITLE[locale];
  const groups = (
    [
      { key: 'cannotEstablish' as const, items: normalizeItems(cannotEstablish) },
      { key: 'invalidation' as const, items: normalizeItems(invalidation) },
      { key: 'missingEvidence' as const, items: normalizeItems(missingEvidence) },
      { key: 'modelLimitations' as const, items: normalizeItems(modelLimitations) },
      { key: 'dataLimitations' as const, items: normalizeItems(dataLimitations) },
    ] satisfies Array<{ key: LimitGroupKey; items: ResearchRiskLimitItem[] }>
  ).filter((group) => group.items.length > 0);

  const hasContent = groups.length > 0 || confidenceCap != null;
  const [open, setOpen] = useState(defaultOpen);

  if (!hasContent) return null;

  const body = (
    <div className="research-risk-limits__body">
      {confidenceCap != null ? (
        <div className="research-risk-limits__confidence" data-risk-limits="confidence-cap">
          <MetaLabel>
            {locale === 'en' ? 'Confidence cap' : '置信上限'}
          </MetaLabel>
          <p className="research-risk-limits__confidence-value">{confidenceCap}</p>
        </div>
      ) : null}
      {groups.map((group) => (
        <div
          key={group.key}
          className="research-risk-limits__group"
          data-risk-limits-group={group.key}
        >
          <MetaLabel className="research-risk-limits__group-label">
            {GROUP_LABELS[group.key][locale]}
          </MetaLabel>
          <LimitList items={group.items} />
        </div>
      ))}
    </div>
  );

  if (placement === 'disclosure') {
    return (
      <section
        data-testid={dataTestId}
        data-research-anatomy="risk-limits"
        data-risk-limits-placement={placement}
        {...densityDataAttributes(resolvedDensity)}
        className={cn('research-risk-limits research-risk-limits--disclosure', className)}
      >
        <button
          type="button"
          className="research-risk-limits__toggle"
          aria-expanded={open}
          onClick={() => setOpen((current) => !current)}
        >
          <SectionTitle as="span" className="research-risk-limits__title">
            {resolvedTitle}
          </SectionTitle>
          {open ? (
            <ChevronDown className="size-3.5 shrink-0" aria-hidden="true" />
          ) : (
            <ChevronRight className="size-3.5 shrink-0" aria-hidden="true" />
          )}
        </button>
        {open ? body : null}
      </section>
    );
  }

  return (
    <section
      data-testid={dataTestId}
      data-research-anatomy="risk-limits"
      data-risk-limits-placement={placement}
      {...densityDataAttributes(resolvedDensity)}
      className={cn(
        'research-risk-limits',
        placement === 'rail' && 'research-risk-limits--rail',
        placement === 'summary' && 'research-risk-limits--summary',
        className,
      )}
    >
      <SectionTitle as="h3" className="research-risk-limits__title">
        {resolvedTitle}
      </SectionTitle>
      {body}
    </section>
  );
}
