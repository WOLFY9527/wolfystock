import type React from 'react';
import type { MarketOverviewItem, MarketOverviewPanel } from '../../api/marketOverview';
import { useI18n } from '../../contexts/UiLanguageContext';
import { GlassCard } from '../common';
import { cn } from '../../utils/cn';
import {
  formatChangeSummary,
  formatMetricValue,
  getDirectionTone,
} from './marketOverviewUtils';
import {
  MARKET_OVERVIEW_CARD_TITLE_CLASS,
  MARKET_OVERVIEW_GHOST_CARD_CLASS,
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
  const supporting = items.filter((item) => item.symbol !== primary?.symbol).slice(0, 3);
  const score = primary?.value ?? 50;
  const gaugeRatio = Math.min(1, Math.max(0, score / 100));
  const title = t('marketOverviewPage.cards.sentiment.title');

  return (
    <GlassCard as="section" className={`${MARKET_OVERVIEW_GHOST_CARD_CLASS} flex h-full flex-col`}>
      <div className="flex h-full flex-col gap-5">
        <div className="mb-6 flex items-center justify-between gap-4">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-white/40">{t('marketOverviewPage.cards.sentiment.eyebrow')}</p>
            <h2 className={`${MARKET_OVERVIEW_CARD_TITLE_CLASS} mt-2`}>{title}</h2>
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

        {primary ? (
          <div className={MARKET_OVERVIEW_GHOST_CARD_CLASS}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-white/40">{t('marketOverviewPage.cards.sentiment.primaryLabel')}</p>
                <p className="mt-2 text-3xl font-bold font-mono text-white">{formatMetricValue(primary, 0)}</p>
                <p className="mt-1 text-xs uppercase tracking-widest text-white/28">{describeSentiment(primary.value, t)}</p>
              </div>
              <span className={cn('pt-1 text-[11px] font-bold', getDirectionTone(primary.riskDirection))}>
                {formatChangeSummary(primary, t('marketOverviewPage.direction.neutral'))}
              </span>
            </div>

            <div className="mt-5 flex items-center justify-center">
              <svg viewBox="0 0 160 96" className="h-32 w-full max-w-[15rem]" aria-hidden="true">
                <path d="M 16 80 A 64 64 0 0 1 144 80" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="10" strokeLinecap="round" />
                <path
                  d="M 16 80 A 64 64 0 0 1 144 80"
                  fill="none"
                  stroke="url(#sentimentGauge)"
                  strokeWidth="10"
                  strokeLinecap="round"
                  strokeDasharray={`${gaugeRatio * 201} 201`}
                />
                <defs>
                  <linearGradient id="sentimentGauge" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#fb7185" />
                    <stop offset="50%" stopColor="#6366f1" />
                    <stop offset="100%" stopColor="#34d399" />
                  </linearGradient>
                </defs>
                <circle cx="80" cy="80" r="3" fill="rgba(255,255,255,0.9)" />
                <path
                  d={`M 80 80 L ${(80 - 58 * Math.cos(Math.PI * gaugeRatio)).toFixed(2)} ${(80 - 58 * Math.sin(Math.PI * gaugeRatio)).toFixed(2)}`}
                  stroke="rgba(255,255,255,0.92)"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
                <text x="16" y="94" fill="rgba(255,255,255,0.34)" fontSize="9" letterSpacing="1.6">{t('marketOverviewPage.cards.sentiment.gaugeLeft')}</text>
                <text x="111" y="94" fill="rgba(255,255,255,0.34)" fontSize="9" letterSpacing="1.6">{t('marketOverviewPage.cards.sentiment.gaugeRight')}</text>
              </svg>
            </div>
          </div>
        ) : null}

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {supporting.map((item) => (
            <div key={item.symbol} className={MARKET_OVERVIEW_GHOST_CARD_CLASS}>
              <div className="flex items-start justify-between gap-3">
                <p className="min-w-0 text-[10px] font-semibold uppercase tracking-widest text-white/40">
                  {sentimentLabels[item.symbol] || item.label}
                </p>
                <span className={cn('shrink-0 text-[11px] font-bold', getDirectionTone(item.riskDirection))}>
                  {formatChangeSummary(item, t('marketOverviewPage.direction.neutral'))}
                </span>
              </div>
              <p className="mt-3 truncate text-2xl font-mono text-white">{formatMetricValue(item)}</p>
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
    </GlassCard>
  );
};
