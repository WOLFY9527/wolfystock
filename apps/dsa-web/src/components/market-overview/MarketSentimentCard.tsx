import type React from 'react';
import type { MarketOverviewItem, MarketOverviewPanel } from '../../api/marketOverview';
import { useI18n } from '../../contexts/UiLanguageContext';
import { cn } from '../../utils/cn';
import {
  formatChangeSummary,
  formatMetricValue,
  getDirectionTone,
} from './marketOverviewUtils';
import {
  MarketOverviewCardFrame,
  MarketOverviewPanelFooter,
  MarketOverviewRefreshButton,
} from './marketOverviewPrimitives';

function resolvePrimaryItem(items: MarketOverviewItem[]): MarketOverviewItem | undefined {
  return items.find((item) => item.symbol.toUpperCase() === 'FGI') || items[0];
}

function describeSentiment(score: number | null | undefined, t: (key: string) => string): string {
  if (score === null || score === undefined) {
    return t('marketOverviewPage.cards.sentiment.states.neutral');
  }
  if (score >= 75) {
    return t('marketOverviewPage.cards.sentiment.states.greed');
  }
  if (score >= 55) {
    return t('marketOverviewPage.cards.sentiment.states.riskOn');
  }
  if (score >= 40) {
    return t('marketOverviewPage.cards.sentiment.states.balanced');
  }
  if (score >= 25) {
    return t('marketOverviewPage.cards.sentiment.states.defensive');
  }
  return t('marketOverviewPage.cards.sentiment.states.fear');
}

export const MarketSentimentCard: React.FC<{
  panel?: MarketOverviewPanel;
  loading?: boolean;
  refreshing?: boolean;
  onRefresh: () => void;
}> = ({ panel, loading, refreshing = false, onRefresh }) => {
  const { t } = useI18n();
  const sentimentLabels: Record<string, string> = {
    PUTCALL: t('marketOverviewPage.cards.sentiment.labels.putcall'),
    BULLBEAR: t('marketOverviewPage.cards.sentiment.labels.bullbear'),
    AAII: t('marketOverviewPage.cards.sentiment.labels.aaii'),
  };
  const items = panel?.items || [];
  const primary = resolvePrimaryItem(items);
  const supporting = items.filter((item) => item.symbol !== primary?.symbol).slice(0, 2);
  const score = primary?.value ?? 50;
  const gaugeRatio = Math.min(1, Math.max(0, score / 100));
  const title = t('marketOverviewPage.cards.sentiment.title');

  return (
    <MarketOverviewCardFrame size="standard" className="h-full">
      <div data-testid="market-sentiment-compact-card" className="flex min-h-0 h-full flex-col gap-2.5">
        <div className="flex shrink-0 items-center justify-between gap-4">
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-white/40">{t('marketOverviewPage.cards.sentiment.eyebrow')}</p>
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
            <span data-testid="market-overview-compact-error-badge" className="rounded-md border border-amber-300/20 bg-amber-400/10 px-2 py-1 text-[10px] font-bold uppercase tracking-widest text-amber-100/78">
              {panel.isStale || panel.isFromSnapshot ? '过期' : '数据异常'}
            </span>
            <span className="min-w-0 truncate text-[10px] text-white/38">刷新失败，保留最近快照</span>
          </div>
        ) : null}

        {primary ? (
          <div className="min-w-0 rounded-lg border border-white/[0.06] bg-white/[0.025] px-3 py-2">
            <div className="flex min-w-0 items-center justify-between gap-3">
              <div className="min-w-0 flex items-baseline gap-2">
                <p className="shrink-0 text-[10px] font-bold uppercase tracking-widest text-white/40">情绪</p>
                <p className="truncate font-mono text-lg font-bold leading-none text-white">{formatMetricValue(primary, 0)}</p>
                <p className="truncate text-xs font-semibold text-white/45">{describeSentiment(primary.value, t)}</p>
              </div>
              <span className={cn('shrink-0 text-right text-[11px] font-bold', getDirectionTone(primary.riskDirection))}>
                {formatChangeSummary(primary, t('marketOverviewPage.direction.neutral'))}
              </span>
            </div>

            <div className="mt-2 grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2 text-[9px] uppercase tracking-widest text-white/30">
              <span>{t('marketOverviewPage.cards.sentiment.gaugeLeft')}</span>
              <div className="h-1 min-w-0 overflow-hidden rounded-full bg-white/[0.06]">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-rose-400 via-sky-400 to-emerald-400"
                  style={{ width: `${gaugeRatio * 100}%` }}
                />
              </div>
              <span>{t('marketOverviewPage.cards.sentiment.gaugeRight')}</span>
            </div>
          </div>
        ) : null}

        <div className="grid min-h-0 grid-cols-1 gap-2 overflow-y-auto no-scrollbar sm:grid-cols-2 ui-scroll-y-quiet">
          {supporting.map((item) => (
            <div key={item.symbol} className="min-w-0 rounded-lg border border-white/[0.06] bg-white/[0.025] px-3 py-2">
              <div className="flex items-start justify-between gap-3">
                <p className="min-w-0 text-[10px] font-semibold uppercase tracking-widest text-white/40">
                  {sentimentLabels[item.symbol] || item.label}
                </p>
                <span className={cn('shrink-0 text-[11px] font-bold', getDirectionTone(item.riskDirection))}>
                  {formatChangeSummary(item, t('marketOverviewPage.direction.neutral'))}
                </span>
              </div>
              <p className="mt-2 truncate text-base font-mono text-white">{formatMetricValue(item)}</p>
              <div className="mt-2 flex items-center gap-2 text-[10px] uppercase tracking-widest text-white/24">
                {item.unit ? <span>{item.unit}</span> : null}
                <span>{item.symbol}</span>
              </div>
              {item.hoverDetails?.length ? (
                <div className="mt-2 flex flex-wrap gap-x-2 gap-y-1 text-[9px] uppercase tracking-widest text-white/32">
                  {item.hoverDetails.map((detail) => (
                    <span key={detail}>{detail}</span>
                  ))}
                </div>
              ) : null}
            </div>
          ))}
        </div>

        {loading ? (
          <div className="rounded-xl border border-white/8 bg-white/[0.03] p-4 text-sm text-white/60">
            {t('marketOverviewPage.loading')}
          </div>
        ) : null}

        <MarketOverviewPanelFooter panel={panel} sourceLabel={t('marketOverviewPage.cards.sentiment.source')} />
      </div>
    </MarketOverviewCardFrame>
  );
};
