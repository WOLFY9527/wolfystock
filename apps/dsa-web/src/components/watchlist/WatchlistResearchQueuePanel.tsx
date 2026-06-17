import { Link } from 'react-router-dom';
import { TerminalChip, TerminalPanel } from '../terminal/TerminalPrimitives';
import type { WatchlistResearchPriorityQueueItem } from '../../types/watchlist';
import { buildLocalizedPath } from '../../utils/localeRouting';

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

function formatEvidenceState(state: string, language: 'zh' | 'en'): string {
  const token = state.trim().toLowerCase();
  if (language === 'en') {
    if (token === 'no_evidence') return 'Evidence gap';
    if (token === 'stale_or_cached') return 'Needs review';
    if (token === 'ready') return 'Evidence ready';
    if (token === 'unavailable') return 'Temporarily unavailable';
    if (token === 'symbol_unknown') return 'Symbol needs check';
    if (token === 'unsupported_market') return 'Market needs check';
    return 'Evidence pending';
  }
  if (token === 'no_evidence') return '证据缺口';
  if (token === 'stale_or_cached') return '等待复核';
  if (token === 'ready') return '证据就绪';
  if (token === 'unavailable') return '暂不可用';
  if (token === 'symbol_unknown') return '代码待确认';
  if (token === 'unsupported_market') return '市场待确认';
  return '证据待确认';
}

function priorityVariant(tier: WatchlistResearchPriorityQueueItem['priorityTier']) {
  if (tier === 'attention') return 'caution';
  if (tier === 'follow_up') return 'info';
  return 'neutral';
}

export default function WatchlistResearchQueuePanel({
  queue,
  language,
}: WatchlistResearchQueuePanelProps) {
  const boundedQueue = queue.slice(0, 5);
  const title = language === 'en' ? 'Research queue' : '研究队列';
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
              ? 'Bounded follow-up list for research review only.'
              : '仅用于后续研究复核的有界列表。'}
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
            const evidenceLabel = formatEvidenceState(item.evidenceAge.state, language);
            return (
              <article
                key={`${item.symbol}:${item.priorityTier}`}
                className="min-w-0 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-3"
              >
                <div className="flex min-w-0 flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-mono text-sm font-semibold text-white">{item.symbol}</p>
                    <p className="mt-1 text-xs leading-5 text-white/68">{item.priorityReasonSafeLabel}</p>
                  </div>
                  <div className="flex shrink-0 flex-wrap items-center justify-end gap-1.5">
                    <TerminalChip variant={priorityVariant(item.priorityTier)} className="font-mono">
                      {item.priorityTier}
                    </TerminalChip>
                    <TerminalChip variant="neutral">
                      {language === 'en' ? 'Research only' : '仅作观察'}
                    </TerminalChip>
                  </div>
                </div>

                <div className="mt-3 flex min-w-0 flex-wrap items-center gap-1.5">
                  <TerminalChip variant="neutral">{evidenceLabel}</TerminalChip>
                  {reviewedAt ? (
                    <span className="font-mono text-[11px] text-white/42">
                      {language === 'en' ? 'Reviewed ' : '复核 '}
                      {reviewedAt}
                    </span>
                  ) : null}
                </div>

                {item.missingEvidence.length ? (
                  <div className="mt-3 space-y-1.5">
                    <p className="text-[11px] font-medium text-white/45">
                      {language === 'en' ? 'Evidence gaps' : '证据缺口'}
                    </p>
                    <div className="flex min-w-0 flex-wrap gap-1.5">
                      {item.missingEvidence.map((label) => (
                        <TerminalChip key={`${item.symbol}:missing:${label}`} variant="caution">
                          {label}
                        </TerminalChip>
                      ))}
                    </div>
                  </div>
                ) : null}

                {item.suggestedResearchPath.length ? (
                  <div className="mt-3 space-y-2">
                    <p className="text-[11px] font-medium text-white/45">
                      {language === 'en' ? 'Suggested research path' : '后续研究路径'}
                    </p>
                    {item.suggestedResearchPath.map((path) => (
                      <Link
                        key={`${item.symbol}:path:${path.route}:${path.label}`}
                        to={buildLocalizedPath(path.route, language)}
                        className="block rounded-md border border-white/8 bg-black/20 px-2.5 py-2 text-xs leading-5 text-white/68 transition hover:border-white/18 hover:text-white"
                      >
                        <span className="font-medium text-white/78">{path.label}</span>
                        {path.reason ? <span className="ml-2 text-white/45">{path.reason}</span> : null}
                      </Link>
                    ))}
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
