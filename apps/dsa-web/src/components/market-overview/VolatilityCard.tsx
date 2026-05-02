import type React from 'react';
import type { MarketOverviewItem, MarketOverviewPanel } from '../../api/marketOverview';
import { useI18n } from '../../contexts/UiLanguageContext';
import { GlassCard } from '../common';
import { isRenderableMarketOverviewItem } from './marketOverviewUtils';
import {
  MARKET_OVERVIEW_CARD_TITLE_CLASS,
  MARKET_OVERVIEW_GHOST_CARD_CLASS,
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
    <GlassCard as="section" data-testid="market-overview-dense-quote-card" className={`${MARKET_OVERVIEW_GHOST_CARD_CLASS} flex h-full flex-col p-3.5`}>
      <div className="flex h-full flex-col gap-3">
        <div className="mb-1 flex items-center justify-between gap-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-white/40">{t('marketOverviewPage.cards.volatility.eyebrow')}</p>
            <h2 className={`${MARKET_OVERVIEW_CARD_TITLE_CLASS} mt-2 mb-1 text-sm normal-case tracking-normal text-white/82`}>{title}</h2>
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

        <div data-testid="market-overview-dense-quote-grid" className="flex flex-col border-y border-white/[0.045]">
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
    </GlassCard>
  );
};
