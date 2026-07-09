import type React from 'react';
import { Link } from 'react-router-dom';
import { cn } from '../../../utils/cn';
import { densityDataAttributes, normalizeResearchDensityMode } from './researchDensity';
import { MetaLabel, SectionTitle } from './ResearchTypography';
import type {
  NextResearchActionItem,
  NextResearchActionKind,
  ResearchDensityMode,
  ResearchLocale,
} from './types';

export type NextResearchActionProps = {
  title?: React.ReactNode;
  steps: NextResearchActionItem[];
  density?: ResearchDensityMode;
  locale?: ResearchLocale;
  compact?: boolean;
  className?: string;
  'data-testid'?: string;
};

const DEFAULT_TITLE: Record<ResearchLocale, string> = {
  zh: '下一步研究',
  en: 'Next research step',
};

const KIND_LABEL: Record<NextResearchActionKind, Record<ResearchLocale, string>> = {
  inspect: { zh: '查看证据', en: 'Inspect evidence' },
  compare: { zh: '比较', en: 'Compare' },
  validate: { zh: '验证', en: 'Validate' },
  handoff: { zh: '继续研究', en: 'Continue research' },
  continue: { zh: '下一步检查', en: 'Next check' },
  gap: { zh: '检查缺口', en: 'Inspect gaps' },
};

/**
 * Research workflow continuation surface — navigation, not advice.
 * Preferred language: 下一步检查 / 继续研究 / 查看证据 / 比较 / 验证 / 检查缺口.
 * Never trade action copy.
 */
export function NextResearchAction({
  title,
  steps,
  density = 'research',
  locale = 'zh',
  compact = false,
  className,
  'data-testid': dataTestId = 'next-research-action',
}: NextResearchActionProps) {
  const resolvedDensity = normalizeResearchDensityMode(density);
  const resolvedTitle = title ?? DEFAULT_TITLE[locale];
  const visibleSteps = steps.filter(Boolean);

  if (!visibleSteps.length) return null;

  return (
    <nav
      data-testid={dataTestId}
      data-research-anatomy="next-research-action"
      aria-label={typeof resolvedTitle === 'string' ? resolvedTitle : DEFAULT_TITLE[locale]}
      {...densityDataAttributes(resolvedDensity)}
      className={cn(
        'research-next-action',
        compact && 'research-next-action--compact',
        className,
      )}
    >
      {compact ? (
        <MetaLabel className="research-next-action__title">{resolvedTitle}</MetaLabel>
      ) : (
        <SectionTitle as="h3" className="research-next-action__title">
          {resolvedTitle}
        </SectionTitle>
      )}
      <ul className="research-next-action__list">
        {visibleSteps.map((step, index) => {
          const kind = step.kind;
          const kindLabel = kind ? KIND_LABEL[kind][locale] : null;
          const content = (
            <>
              <div className="research-next-action__row-head">
                {kindLabel ? (
                  <span className="research-next-action__kind" data-next-action-kind={kind}>
                    {kindLabel}
                  </span>
                ) : null}
                <span className="research-next-action__label">{step.label}</span>
              </div>
              {step.description ? (
                <p className="research-next-action__description">{step.description}</p>
              ) : null}
            </>
          );

          const rowClass = 'research-next-action__item';
          const key = step.key ?? index;

          if (step.href) {
            const isExternal = step.external || /^https?:\/\//i.test(step.href);
            if (isExternal) {
              return (
                <li key={key} className={rowClass}>
                  <a
                    href={step.href}
                    className="research-next-action__control"
                    target="_blank"
                    rel="noreferrer"
                    onClick={step.onClick}
                  >
                    {content}
                  </a>
                </li>
              );
            }
            return (
              <li key={key} className={rowClass}>
                <Link to={step.href} className="research-next-action__control" onClick={step.onClick}>
                  {content}
                </Link>
              </li>
            );
          }

          if (step.onClick) {
            return (
              <li key={key} className={rowClass}>
                <button type="button" className="research-next-action__control" onClick={step.onClick}>
                  {content}
                </button>
              </li>
            );
          }

          return (
            <li key={key} className={rowClass}>
              <div className="research-next-action__static">{content}</div>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
