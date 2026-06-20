import { Link } from 'react-router-dom';
import { TerminalChip, TerminalPanel } from '../terminal/TerminalPrimitives';
import type { WatchlistResearchPriorityQueueItem } from '../../types/watchlist';
import { buildLocalizedPath } from '../../utils/localeRouting';
import { getResearchQueueConsumerCopy } from '../../utils/researchQueueConsumerCopy';

type WatchlistResearchQueuePanelProps = {
  queue: WatchlistResearchPriorityQueueItem[];
  language: 'zh' | 'en';
};

const DATE_FORMATTERS = {
  en: new Intl.DateTimeFormat('en-US', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }),
  zh: new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }),
} as const;

function formatReviewedAt(value: string | null | undefined, language: 'zh' | 'en'): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return DATE_FORMATTERS[language].format(parsed);
}

export default function WatchlistResearchQueuePanel({
  queue,
  language,
}: WatchlistResearchQueuePanelProps) {
  const boundedQueue = queue.slice(0, 5);
  const title = language === 'en' ? 'Research follow-up' : '后续研究';
  const countLabel = language === 'en'
    ? `${boundedQueue.length} saved symbols`
    : `${boundedQueue.length} 个已保存标的`;

  return (
    <TerminalPanel
      as="section"
      dense
      data-testid="watchlist-research-queue"
      className="grid min-w-0 gap-3 px-4 py-3"
      aria-label={title}
    >
      <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--wolfy-text-muted)]">
            {title}
          </p>
          <p className="mt-1 text-xs leading-5 text-white/58">
            {language === 'en'
              ? 'Compact follow-up list for saved symbols that need one more research check.'
              : '已保存标的的简要跟进清单，每项只保留一个待核对方向。'}
          </p>
        </div>
        <TerminalChip variant="neutral" className="font-mono">
          {countLabel}
        </TerminalChip>
      </div>

      {boundedQueue.length === 0 ? (
        <div className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-3 text-xs leading-5 text-white/58">
          <p className="font-medium text-white/72">
            {language === 'en' ? 'No follow-up research queue right now' : '暂无需要跟进的研究队列'}
          </p>
          <p className="mt-1 text-white/45">
            {language === 'en'
              ? 'Keep observing; this view does not create research jobs or change the watchlist.'
              : '继续保持观察，不会自动创建任务或更改观察列表。'}
          </p>
        </div>
      ) : (
        <div className="grid min-w-0 gap-2 lg:grid-cols-2">
          {boundedQueue.map((item) => {
            const reviewedAt = formatReviewedAt(item.evidenceAge.lastReviewedAt, language);
            const consumerCopy = getResearchQueueConsumerCopy({
              priorityTier: item.priorityTier,
              priorityReason: item.priorityReasonSafeLabel,
              evidenceState: item.evidenceAge.state,
              missingEvidence: item.missingEvidence,
              suggestedResearchPath: item.suggestedResearchPath,
            }, language);
            return (
              <article
                key={`${item.symbol}:${item.priorityTier}`}
                className="min-w-0 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-3"
              >
                <div className="flex min-w-0 flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-mono text-sm font-semibold text-white">{item.symbol}</p>
                    <p className="mt-1 text-xs leading-5 text-white/68">{consumerCopy.priorityReason}</p>
                  </div>
                  <div className="flex shrink-0 flex-wrap items-center justify-end gap-1.5">
                    <TerminalChip variant={consumerCopy.priorityVariant} className="font-mono">
                      {consumerCopy.priorityTierLabel}
                    </TerminalChip>
                  </div>
                </div>

                <div className="mt-3 flex min-w-0 flex-wrap items-center gap-1.5">
                  <TerminalChip variant="neutral">{consumerCopy.evidenceStateLabel}</TerminalChip>
                  {reviewedAt ? (
                    <span className="font-mono text-[11px] text-white/42">
                      {language === 'en' ? 'Reviewed ' : '复核 '}
                      {reviewedAt}
                    </span>
                  ) : null}
                </div>

                {consumerCopy.missingEvidence.length ? (
                  <p className="mt-3 text-xs leading-5 text-white/58">
                    {language === 'en' ? 'Needs check: ' : '待核对：'}
                    {consumerCopy.missingEvidence.slice(0, 2).join(language === 'en' ? ', ' : '、')}
                  </p>
                ) : null}

                {consumerCopy.suggestedResearchPath.length ? (
                  <div className="mt-3 space-y-2">
                    <p className="text-[11px] font-medium text-white/45">
                      {language === 'en' ? 'Next check' : '下一步核对'}
                    </p>
                    {item.suggestedResearchPath.map((path, index) => {
                      const safePath = consumerCopy.suggestedResearchPath[index];
                      return (
                        <Link
                          key={`${item.symbol}:path:${path.route}:${path.label}`}
                          to={buildLocalizedPath(path.route, language)}
                          className="block rounded-md border border-white/8 bg-black/20 px-2.5 py-2 text-xs leading-5 text-white/68 transition hover:border-white/18 hover:text-white"
                        >
                          <span className="font-medium text-white/78">{safePath?.label}</span>
                          {safePath?.reason ? <span className="ml-2 text-white/45">{safePath.reason}</span> : null}
                        </Link>
                      );
                    })}
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      )}
    </TerminalPanel>
  );
}
