import type React from 'react';
import { TerminalChip, TerminalEmptyState } from '../terminal/TerminalPrimitives';
import { cn } from '../../utils/cn';
import type {
  ConsumerResearchEmptyStateLocale,
  ConsumerResearchEmptyStateSeverity,
  ConsumerResearchEmptyStateView,
} from './researchEmptyStateModel';

function severityChipVariant(
  severity: ConsumerResearchEmptyStateSeverity,
): React.ComponentProps<typeof TerminalChip>['variant'] {
  if (severity === 'limited') return 'caution';
  if (severity === 'unavailable') return 'info';
  return 'neutral';
}

function severityLabel(
  severity: ConsumerResearchEmptyStateSeverity,
  locale: ConsumerResearchEmptyStateLocale,
) {
  const labels: Record<ConsumerResearchEmptyStateSeverity, Record<ConsumerResearchEmptyStateLocale, string>> = {
    neutral: { zh: '观察', en: 'Observe' },
    limited: { zh: '有限', en: 'Limited' },
    unavailable: { zh: '暂不可用', en: 'Unavailable' },
  };
  return labels[severity][locale];
}

export function ConsumerResearchEmptyState({
  state,
  locale = 'zh',
  className,
  'data-testid': dataTestId,
}: {
  state: ConsumerResearchEmptyStateView;
  locale?: ConsumerResearchEmptyStateLocale;
  className?: string;
  'data-testid'?: string;
}) {
  return (
    <TerminalEmptyState
      data-testid={dataTestId || 'consumer-research-empty-state'}
      data-severity={state.severity}
      aria-live={state.severity === 'neutral' ? 'polite' : undefined}
      className={cn('items-start', className)}
      title={state.title}
    >
      <div className="space-y-1">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <TerminalChip variant={severityChipVariant(state.severity)}>
            {severityLabel(state.severity, locale)}
          </TerminalChip>
        </div>
        <p>{state.body}</p>
        {state.nextResearchStep ? (
          <p>
            <span className="font-medium text-[color:var(--wolfy-text-secondary)]">
              {locale === 'en' ? 'Next research step: ' : '下一步研究：'}
            </span>
            {state.nextResearchStep}
          </p>
        ) : null}
      </div>
    </TerminalEmptyState>
  );
}
