import type { ParsedApiError } from '../../api/error';
import { ApiErrorAlert } from '../common/ApiErrorAlert';
import { Drawer } from '../common/Drawer';
import { Pagination } from '../common/Pagination';
import { PillBadge } from '../common/PillBadge';
import { TerminalEmptyState } from '../terminal/TerminalPrimitives';

type Language = 'zh' | 'en';
type ChipVariant = 'success' | 'warning' | 'danger' | 'info' | 'history';

export type ScannerHistoryDrawerItem = {
  id: number;
  marketLabel: string;
  marketVariant: ChipVariant;
  statusLabel: string;
  statusVariant: ChipVariant;
  watchlistDateLabel: string | null;
  profileLabel: string;
  title: string;
  detail: string | null;
  shortlistSize: number;
  universeSize: number;
  evaluatedSize: number;
  runAtLabel: string;
  comparisonLabel: string | null;
  reviewLabel: string | null;
  matchedSymbols: string[];
  overflowSymbolCount: number;
};

export function ScannerHistoryDrawer({
  isOpen,
  onClose,
  language,
  historyError,
  isLoadingHistory,
  items,
  selectedRunId,
  emptyStateTitle,
  emptyStateBody,
  loadingLabel,
  shortlistMetricLabel,
  universeMetricLabel,
  evaluatedMetricLabel,
  historyPage,
  totalHistoryPages,
  onPageChange,
  onSelectRun,
}: {
  isOpen: boolean;
  onClose: () => void;
  language: Language;
  historyError: ParsedApiError | null;
  isLoadingHistory: boolean;
  items: ScannerHistoryDrawerItem[];
  selectedRunId: number | null;
  emptyStateTitle: string;
  emptyStateBody: string;
  loadingLabel: string;
  shortlistMetricLabel: string;
  universeMetricLabel: string;
  evaluatedMetricLabel: string;
  historyPage: number;
  totalHistoryPages: number;
  onPageChange: (page: number) => void;
  onSelectRun: (runId: number) => void;
}) {
  return (
    <Drawer
      isOpen={isOpen}
      onClose={onClose}
      title={language === 'en' ? 'Historical scan replay' : '历史扫描回放'}
      width="max-w-4xl"
    >
      <div data-testid="user-scanner-bento-drawer" className="ml-auto w-full max-w-4xl rounded-l-[40px] bg-transparent p-6 text-foreground sm:p-8">
        <div className="grid gap-6">
          <div>
            <p className="text-[11px] uppercase tracking-[0.18em] text-muted-text">{language === 'en' ? 'Historical scan replay' : '历史扫描回放'}</p>
            <h2 className="mt-1 text-xl text-foreground">{language === 'en' ? 'Recent scanner runs' : '近期扫描记录'}</h2>
          </div>

          {historyError ? <ApiErrorAlert error={historyError} /> : null}
          {isLoadingHistory ? <div className="theme-panel-subtle rounded-[28px] px-4 py-5 text-sm text-secondary-text">{loadingLabel}</div> : null}
          {!isLoadingHistory && items.length ? (
            <div className="space-y-3">
              {items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`w-full flex flex-col gap-3 bg-white/[0.02] border border-white/5 rounded-2xl p-5 hover:bg-white/[0.04] transition-colors text-left ${item.id === selectedRunId ? 'border-white/15 bg-white/[0.05]' : ''}`}
                  onClick={() => onSelectRun(item.id)}
                >
                  <div className="flex w-full max-w-full items-start gap-3 overflow-hidden">
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <PillBadge variant={item.marketVariant}>{item.marketLabel}</PillBadge>
                        <PillBadge variant={item.statusVariant}>{item.statusLabel}</PillBadge>
                        {item.watchlistDateLabel ? <PillBadge variant="history">{item.watchlistDateLabel}</PillBadge> : null}
                        <PillBadge variant="history">{item.profileLabel}</PillBadge>
                      </div>
                      <h4 className="mt-3 mb-2 w-full truncate font-bold text-white">
                        {item.title}
                      </h4>
                      {item.detail ? (
                        <p className="break-words whitespace-normal w-full text-sm text-white/70 leading-relaxed">
                          {item.detail}
                        </p>
                      ) : null}
                      <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-secondary-text">
                        <span>{`${shortlistMetricLabel}: ${item.shortlistSize}`}</span>
                        <span>{`${universeMetricLabel}: ${item.universeSize}`}</span>
                        <span>{`${evaluatedMetricLabel}: ${item.evaluatedSize}`}</span>
                        <span>{item.runAtLabel}</span>
                      </div>
                      {item.comparisonLabel || item.reviewLabel ? (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {item.comparisonLabel ? (
                            <span className="rounded border border-white/8 bg-white/[0.035] px-2 py-1 text-[10px] text-white/52">
                              {item.comparisonLabel}
                            </span>
                          ) : null}
                          {item.reviewLabel ? (
                            <span className="rounded border border-white/8 bg-white/[0.035] px-2 py-1 text-[10px] text-white/52">
                              {item.reviewLabel}
                            </span>
                          ) : null}
                        </div>
                      ) : null}
                      {item.matchedSymbols.length ? (
                        <div className="product-chip-list product-chip-list--tight mt-3 w-full" data-testid={`scanner-history-symbols-${item.id}`}>
                          {item.matchedSymbols.map((symbol) => (
                            <span
                              key={`${item.id}-${symbol}`}
                              className="product-chip shrink-0 text-[10px] px-2 py-1"
                            >
                              {symbol}
                            </span>
                          ))}
                          {item.overflowSymbolCount > 0 ? (
                            <span className="product-chip shrink-0 text-[10px] px-2 py-1">
                              +{item.overflowSymbolCount}
                            </span>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          ) : null}
          {!isLoadingHistory && !items.length ? (
            <TerminalEmptyState title={emptyStateTitle} className="w-full py-12">
              {emptyStateBody}
            </TerminalEmptyState>
          ) : null}
          {totalHistoryPages > 1 ? (
            <div className="pt-2">
              <Pagination currentPage={historyPage} totalPages={totalHistoryPages} onPageChange={onPageChange} />
            </div>
          ) : null}
        </div>
      </div>
    </Drawer>
  );
}
