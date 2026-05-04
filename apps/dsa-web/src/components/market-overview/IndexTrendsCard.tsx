import type React from 'react';
import type { MarketOverviewPanel } from '../../api/marketOverview';
import { useI18n } from '../../contexts/UiLanguageContext';
import { GlassCard } from '../common';
import { isRenderableMarketOverviewItem } from './marketOverviewUtils';
import {
  MARKET_OVERVIEW_CARD_TITLE_CLASS,
  MARKET_OVERVIEW_GHOST_CARD_CLASS,
  MarketOverviewDataRow,
  MarketOverviewPanelFooter,
  MarketOverviewRefreshButton,
} from './marketOverviewPrimitives';

export const IndexTrendsCard: React.FC<{
  panel?: MarketOverviewPanel;
  loading?: boolean;
  refreshing?: boolean;
  onRefresh: () => void;
}> = ({ panel, loading, refreshing = false, onRefresh }) => {
  const { t } = useI18n();
  const items = (panel?.items || []).filter(isRenderableMarketOverviewItem);
  const title = t('marketOverviewPage.cards.indexTrends.title');

  return (
    <GlassCard as="section" className={`${MARKET_OVERVIEW_GHOST_CARD_CLASS} flex h-full flex-col`}>
      <div className="flex h-full flex-col gap-5">
        <div className="mb-6 flex items-center justify-between gap-4">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-white/40">{t('marketOverviewPage.cards.indexTrends.eyebrow')}</p>
            <h2 className={`${MARKET_OVERVIEW_CARD_TITLE_CLASS} mt-2`}>{title}</h2>
            <p className="mt-1 text-sm text-white/55">{t('marketOverviewPage.cards.indexTrends.description')}</p>
          </div>
          <MarketOverviewRefreshButton
            label={t('marketOverviewPage.refreshCard', { title })}
            refreshing={refreshing}
            onRefresh={onRefresh}
          />
        </div>

        {panel?.errorMessage ? (
          <div className="flex min-w-0 items-center gap-2" title={panel.errorMessage}>
            <span data-testid="market-overview-compact-error-badge" className="rounded-md border border-amber-300/20 bg-amber-400/10 px-2 py-1 text-[10px] font-bold uppercase tracking-widest text-amber-100/78">
              {panel.isStale || panel.isFromSnapshot ? '过期' : '数据异常'}
            </span>
            <span className="min-w-0 truncate text-[10px] text-white/38">刷新失败，保留最近快照</span>
          </div>
        ) : null}

        <div className="flex flex-col">
          {items.map((item) => (
            <MarketOverviewDataRow
              key={item.symbol}
              item={item}
              neutralLabel={t('marketOverviewPage.direction.neutral')}
              valueClassName="text-xl"
            />
          ))}
        </div>

        {loading ? (
          <div className="rounded-xl border border-white/8 bg-white/[0.03] p-4 text-sm text-white/60">
            {t('marketOverviewPage.loading')}
          </div>
        ) : null}

        <MarketOverviewPanelFooter panel={panel} sourceLabel={t('marketOverviewPage.cards.indexTrends.source')} />
      </div>
    </GlassCard>
  );
};
