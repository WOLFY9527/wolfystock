import type React from 'react';
import type { MarketOverviewPanel } from '../../api/marketOverview';
import { useI18n } from '../../contexts/UiLanguageContext';
import { MarketOverviewCard } from './MarketOverviewCard';

export const FundsFlowCard: React.FC<{
  panel?: MarketOverviewPanel;
  loading?: boolean;
  refreshing?: boolean;
  onRefresh: () => void;
}> = ({ panel, loading, refreshing = false, onRefresh }) => {
  const { t } = useI18n();

  return (
    <MarketOverviewCard
      title={t('marketOverviewPage.cards.fundsFlow.title')}
      eyebrow={t('marketOverviewPage.cards.fundsFlow.eyebrow')}
      description={t('marketOverviewPage.cards.fundsFlow.description')}
      sourceLabel={t('marketOverviewPage.cards.fundsFlow.source')}
      panel={panel}
      loading={loading}
      refreshing={refreshing}
      onRefresh={onRefresh}
      variant="denseQuote"
    />
  );
};
