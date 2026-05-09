import type React from 'react';
import type { MarketOverviewItem, MarketOverviewPanel } from '../../api/marketOverview';
import { useI18n } from '../../contexts/UiLanguageContext';
import { TerminalChip } from '../terminal';
import { isRenderableMarketOverviewItem } from './marketOverviewUtils';
import {
  MarketOverviewCardFrame,
  MarketOverviewDenseQuoteItem,
  MarketOverviewPanelFooter,
  MarketOverviewRefreshButton,
} from './marketOverviewPrimitives';

function resolvePrimaryItem(items: MarketOverviewItem[]): MarketOverviewItem | undefined {
  return items.find((item) => item.symbol.toUpperCase() === 'VIX') || items[0];
}

export const VolatilityCard: React.FC<{
  panel?: MarketOverviewPanel;
  loading?: boolean;
  refreshing?: boolean;
  onRefresh: () => void;
}> = ({ panel, loading, refreshing = false, onRefresh }) => {
  const { t } = useI18n();
  const items = (panel?.items || []).filter(isRenderableMarketOverviewItem);
  const primary = resolvePrimaryItem(items);
  const title = t('marketOverviewPage.cards.volatility.title');
  const compactItems = [
    ...(primary ? [primary] : []),
    ...items.filter((item) => item.symbol !== primary?.symbol),
  ].slice(0, 4);
  const hiddenItemCount = Math.max(items.length - compactItems.length, 0);

  return (
    <MarketOverviewCardFrame testId="market-overview-dense-quote-card" size="list" className="h-full">
      <div className="flex min-h-0 h-full flex-col gap-3">
        <div className="flex shrink-0 items-center justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-white/40">{t('marketOverviewPage.cards.volatility.eyebrow')}</p>
            <h2 className="mt-1 truncate text-sm font-semibold text-white/84">{title}</h2>
          </div>
          <MarketOverviewRefreshButton
            label={t('marketOverviewPage.refreshCard', { title })}
            refreshing={refreshing}
            onRefresh={onRefresh}
          />
        </div>

        {panel?.errorMessage ? (
          <div className="flex min-w-0 items-center gap-2" title={panel.errorMessage}>
            <TerminalChip
              data-testid="market-overview-compact-error-badge"
              variant={panel.isStale || panel.isFromSnapshot ? 'neutral' : 'caution'}
              className="px-2 py-1 text-[10px] font-semibold tracking-widest"
            >
              {panel.isStale || panel.isFromSnapshot ? '最近快照' : '待刷新'}
            </TerminalChip>
            <span className="min-w-0 truncate text-[10px] text-white/38">刷新失败，保留最近快照</span>
          </div>
        ) : null}

        <div data-testid="market-overview-dense-quote-grid" className="flex min-h-0 flex-col overflow-y-auto no-scrollbar border-y border-white/[0.045] ui-scroll-y-quiet">
          {compactItems.map((item) => (
            <MarketOverviewDenseQuoteItem
              key={item.symbol}
              item={item}
              neutralLabel={t('marketOverviewPage.direction.neutral')}
              valueDigitsBelowHundred={item.symbol === 'FGI' ? 1 : 2}
            />
          ))}
        </div>

        {hiddenItemCount > 0 ? (
          <p className="text-[10px] text-white/38">
            已优先显示关键 {compactItems.length} 项，其余 {hiddenItemCount} 项保留在数据源快照中。
          </p>
        ) : null}

        {loading ? (
          <div className="rounded-xl border border-white/8 bg-white/[0.03] p-4 text-sm text-white/60">
            {t('marketOverviewPage.loading')}
          </div>
        ) : null}

        <MarketOverviewPanelFooter panel={panel} sourceLabel={t('marketOverviewPage.cards.volatility.source')} />
      </div>
    </MarketOverviewCardFrame>
  );
};
