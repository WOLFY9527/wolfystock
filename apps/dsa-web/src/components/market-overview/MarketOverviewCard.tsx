import type React from 'react';
import type { MarketOverviewPanel } from '../../api/marketOverview';
import { useI18n } from '../../contexts/UiLanguageContext';
import { cn } from '../../utils/cn';
import { isRenderableMarketOverviewItem } from './marketOverviewUtils';
import {
  MarketOverviewCardFrame,
  MarketOverviewDataRow,
  MarketOverviewDenseQuoteItem,
  MarketOverviewPanelFooter,
  MarketOverviewRefreshButton,
} from './marketOverviewPrimitives';

function isFallbackOnlyPanel(panel?: MarketOverviewPanel): boolean {
  if (!panel) {
    return false;
  }
  const panelFallback = panel.isFallback || panel.freshness === 'fallback' || panel.source === 'fallback';
  const items = panel.items || [];
  return Boolean(panelFallback && items.length > 0 && items.every((item) => (
    item.isFallback || item.freshness === 'fallback' || item.source === 'fallback'
  )));
}

type MarketOverviewCardProps = {
  title: string;
  eyebrow: string;
  description: string;
  sourceLabel: string;
  panel?: MarketOverviewPanel;
  loading?: boolean;
  refreshing?: boolean;
  onRefresh: () => void;
  className?: string;
  variant?: 'default' | 'denseQuote';
};

export const MarketOverviewCard: React.FC<MarketOverviewCardProps> = ({
  title,
  eyebrow,
  description,
  sourceLabel,
  panel,
  loading = false,
  refreshing = false,
  onRefresh,
  className,
  variant = 'default',
}) => {
  const { t } = useI18n();
  const items = (panel?.items || []).filter(isRenderableMarketOverviewItem);
  const fallbackOnly = isFallbackOnlyPanel(panel);
  const denseQuote = variant === 'denseQuote';
  const visibleItems = denseQuote ? items.slice(0, 5) : items;
  const hiddenItemCount = denseQuote ? Math.max(items.length - visibleItems.length, 0) : 0;

  return (
    <MarketOverviewCardFrame
      testId={denseQuote ? 'market-overview-dense-quote-card' : undefined}
      size={denseQuote ? 'list' : 'standard'}
      className={cn('h-full', fallbackOnly ? 'border-orange-300/12' : '', className)}
    >
      <div className={cn('flex min-h-0 h-full flex-col', denseQuote ? 'gap-3' : 'gap-4')}>
        <div className="flex shrink-0 items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-white/40">{eyebrow}</p>
            <h2 className="mt-1 truncate text-sm font-semibold text-white/84">{title}</h2>
            <p className={cn('mt-1 max-w-xl text-white/55', denseQuote ? 'line-clamp-1 text-[11px] leading-4' : 'text-sm')}>{description}</p>
          </div>
          <MarketOverviewRefreshButton
            label={t('marketOverviewPage.refreshCard', { title })}
            refreshing={refreshing}
            onRefresh={onRefresh}
          />
        </div>

        {panel?.errorMessage ? (
          <div className="rounded-xl border border-rose-300/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
            {panel.errorMessage}
          </div>
        ) : null}

        {fallbackOnly && !denseQuote ? (
          <div className="rounded-lg border border-orange-300/20 bg-orange-400/8 px-3 py-2 text-xs leading-5 text-orange-100/85" data-testid="market-overview-fallback-only-notice">
            <p className="font-semibold">暂未接入真实数据源</p>
            <p className="text-orange-100/70">当前为备用示例数据，不参与市场温度评分</p>
          </div>
        ) : null}

        {denseQuote ? (
          <div
            data-testid="market-overview-dense-quote-grid"
            className="flex min-h-0 flex-col overflow-y-auto border-y border-white/[0.045] ui-scroll-y-quiet"
          >
            {visibleItems.map((item) => (
              <MarketOverviewDenseQuoteItem
                key={item.symbol}
                item={item}
                neutralLabel={t('marketOverviewPage.direction.neutral')}
              />
            ))}
          </div>
        ) : (
          <div className="min-h-0 overflow-y-auto ui-scroll-y-quiet">
            {visibleItems.map((item) => (
              <MarketOverviewDataRow
                key={item.symbol}
                item={item}
                neutralLabel={t('marketOverviewPage.direction.neutral')}
              />
            ))}
          </div>
        )}

        {hiddenItemCount > 0 ? (
          <p className="text-[10px] text-white/38">
            已优先显示关键 {visibleItems.length} 项，其余 {hiddenItemCount} 项保留在数据源快照中。
          </p>
        ) : null}

        {loading ? (
          <div className="rounded-xl border border-white/8 bg-white/[0.03] p-4 text-sm text-white/60">
            {t('marketOverviewPage.loading')}
          </div>
        ) : null}

        <MarketOverviewPanelFooter panel={panel} sourceLabel={sourceLabel} />
      </div>
    </MarketOverviewCardFrame>
  );
};
