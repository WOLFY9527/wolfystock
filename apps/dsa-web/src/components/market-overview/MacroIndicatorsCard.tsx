import type React from 'react';
import type { MarketOverviewPanel } from '../../api/marketOverview';
import { useI18n } from '../../contexts/UiLanguageContext';
import { MarketOverviewCard } from './MarketOverviewCard';

export const MacroIndicatorsCard: React.FC<{
  panel?: MarketOverviewPanel;
  loading?: boolean;
  refreshing?: boolean;
  onRefresh: () => void;
}> = ({ panel, loading, refreshing = false, onRefresh }) => {
  const { t } = useI18n();

  return (
    <MarketOverviewCard
      title={t('marketOverviewPage.cards.macro.title')}
      eyebrow={t('marketOverviewPage.cards.macro.eyebrow')}
      description={t('marketOverviewPage.cards.macro.description')}
      sourceLabel={t('marketOverviewPage.cards.macro.source')}
      panel={panel}
      loading={loading}
      refreshing={refreshing}
      onRefresh={onRefresh}
      variant="denseQuote"
    />
  );
};
