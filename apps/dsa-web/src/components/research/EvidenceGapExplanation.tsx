import type React from 'react';
import { TerminalChip, TerminalEmptyState } from '../terminal/TerminalPrimitives';
import { cn } from '../../utils/cn';
import {
  buildEvidenceGapExplanations,
  type EvidenceGapExplanationLocale,
  type EvidenceGapExplanationView,
  type EvidenceGapInput,
} from './evidenceGapCopy';

function toneChipVariant(tone: EvidenceGapExplanationView['tone']): React.ComponentProps<typeof TerminalChip>['variant'] {
  if (tone === 'danger') return 'danger';
  if (tone === 'caution') return 'caution';
  if (tone === 'info') return 'info';
  return 'neutral';
}

export function EvidenceGapExplanationList({
  gaps,
  locale = 'zh',
  title,
  emptyText,
  compact = false,
  className,
  'data-testid': dataTestId,
}: {
  gaps: Array<EvidenceGapInput | null | undefined> | null | undefined;
  locale?: EvidenceGapExplanationLocale;
  title?: string;
  emptyText?: string;
  compact?: boolean;
  className?: string;
  'data-testid'?: string;
}) {
  const explanations = buildEvidenceGapExplanations(gaps, locale);
  const resolvedTitle = title || (locale === 'en' ? 'Evidence gap explanations' : '证据缺口解释');
  const resolvedEmptyText = emptyText || (locale === 'en' ? 'No explicit evidence gap.' : '暂无明确证据缺口。');

  if (!explanations.length) {
    return (
      <TerminalEmptyState data-testid={dataTestId || 'evidence-gap-explanation-empty'} className={className}>
        {resolvedEmptyText}
      </TerminalEmptyState>
    );
  }

  return (
    <section
      data-testid={dataTestId || 'evidence-gap-explanation-list'}
      className={cn(
        'space-y-2 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]',
        className,
      )}
    >
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <span className="text-[11px] font-medium text-[color:var(--wolfy-text-muted)]">{resolvedTitle}</span>
        <TerminalChip variant="neutral">
          {locale === 'en' ? 'Observation only' : '仅作观察'}
        </TerminalChip>
      </div>
      <div className="grid gap-2">
        {explanations.map((item) => (
          <article
            key={item.key}
            className="min-w-0 rounded-xl border border-[color:var(--wolfy-divider)] bg-black/10 px-3 py-2.5"
          >
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <TerminalChip variant={toneChipVariant(item.tone)}>{item.title}</TerminalChip>
            </div>
            <p className="mt-2 text-sm leading-6 text-[color:var(--wolfy-text-primary)]">{item.explanation}</p>
            {compact ? null : (
              <div className="mt-2 grid gap-1.5 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                <p>
                  <span className="font-medium text-[color:var(--wolfy-text-secondary)]">
                    {locale === 'en' ? 'Why it matters: ' : '为什么重要：'}
                  </span>
                  {item.whyItMatters}
                </p>
                <p>
                  <span className="font-medium text-[color:var(--wolfy-text-secondary)]">
                    {locale === 'en' ? 'Research step: ' : '下一步研究：'}
                  </span>
                  {item.suggestedResearchStep}
                </p>
                <p>
                  <span className="font-medium text-[color:var(--wolfy-text-secondary)]">
                    {locale === 'en' ? 'Confidence impact: ' : '置信度影响：'}
                  </span>
                  {item.confidenceImpact}
                </p>
                <p>{item.observationBoundary}</p>
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
