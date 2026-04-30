import type React from 'react';
import type { MarketOverviewPanel } from '../../api/marketOverview';
import { useI18n } from '../../contexts/UiLanguageContext';
import { GlassCard } from '../common';
import { cn } from '../../utils/cn';
import { isRenderableMarketOverviewItem } from './marketOverviewUtils';
import {
  MARKET_OVERVIEW_CARD_TITLE_CLASS,
  MARKET_OVERVIEW_GHOST_CARD_CLASS,
  MarketOverviewDataRow,
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
}) => {
  const { t } = useI18n();
  const items = (panel?.items || []).filter(isRenderableMarketOverviewItem);
  const fallbackOnly = isFallbackOnlyPanel(panel);

  return (
    <GlassCard
      as="section"
      className={cn(
        MARKET_OVERVIEW_GHOST_CARD_CLASS,
        'flex h-full flex-col',
        fallbackOnly ? 'border-orange-300/12' : '',
        className || '',
      )}
    >
      <div className="flex h-full flex-col gap-5">
        <div className="mb-6 flex items-center justify-between gap-4">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-white/40">{eyebrow}</p>
            <h2 className={cn(MARKET_OVERVIEW_CARD_TITLE_CLASS, 'mt-2')}>{title}</h2>
            <p className="mt-1 max-w-xl text-sm text-white/55">{description}</p>
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

        {fallbackOnly ? (
          <div className="rounded-lg border border-orange-300/20 bg-orange-400/8 px-3 py-2 text-xs leading-5 text-orange-100/85" data-testid="market-overview-fallback-only-notice">
            <p className="font-semibold">暂未接入真实数据源</p>
            <p className="text-orange-100/70">当前为备用示例数据，不参与市场温度评分</p>
          </div>
        ) : null}

        <div className="flex flex-col">
          {items.map((item) => (
            <MarketOverviewDataRow
              key={item.symbol}
              item={item}
              neutralLabel={t('marketOverviewPage.direction.neutral')}
            />
          ))}
        </div>

        {loading ? (
          <div className="rounded-xl border border-white/8 bg-white/[0.03] p-4 text-sm text-white/60">
            {t('marketOverviewPage.loading')}
          </div>
        ) : null}

        <MarketOverviewPanelFooter panel={panel} sourceLabel={sourceLabel} />
      </div>
    </GlassCard>
  );
};
