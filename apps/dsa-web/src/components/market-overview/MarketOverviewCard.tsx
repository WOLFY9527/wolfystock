import type React from 'react';
import type { MarketOverviewPanel } from '../../api/marketOverview';
import { useI18n } from '../../contexts/UiLanguageContext';
import { cn } from '../../utils/cn';
import { TerminalChip } from '../terminal/TerminalPrimitives';
import { isRenderableMarketOverviewItem } from './marketOverviewUtils';
import {
  MarketOverviewCardFrame,
  MarketOverviewDataRow,
  MarketOverviewDenseQuoteItem,
  MarketOverviewPanelFooter,
  MarketOverviewRefreshButton,
} from './marketOverviewPrimitives';

type MarketOverviewProviderState = 'unconfigured' | 'refreshing' | 'refreshFailed' | 'stale' | 'noData' | null;

function hasNotConfiguredReason(panel?: MarketOverviewPanel): boolean {
  if (!panel) return false;
  const reasons = [
    panel.degradationReason,
    panel.sourceAuthorityReason,
    panel.providerFreshness?.degradationReason,
    ...(panel.routeRejectedReasonCodes || []),
    ...(panel.reasonCodes || []),
    ...(panel.items || []).flatMap((item) => [
      item.degradationReason,
      item.sourceAuthorityReason,
      ...(item.routeRejectedReasonCodes || []),
      ...(item.reasonCodes || []),
    ]),
  ];
  return reasons.some((reason) => /(^|[_-])(not_configured|provider_not_configured|provider_missing)([_-]|$)/i.test(String(reason || '')));
}

function hasProviderFailure(panel?: MarketOverviewPanel): boolean {
  if (!panel) return false;
  return Boolean(
    panel.status === 'failure'
      || panel.errorMessage
      || panel.refreshError
      || panel.lastError
      || panel.providerHealth?.status === 'error'
      || panel.providerHealth?.errorSummary,
  );
}

function hasStaleSnapshot(panel?: MarketOverviewPanel): boolean {
  if (!panel) return false;
  return Boolean(
    panel.isStale
      || panel.freshness === 'stale'
      || panel.freshness === 'cached'
      || panel.providerHealth?.status === 'stale'
      || panel.providerHealth?.isStale,
  );
}

function resolveMarketOverviewProviderState(
  panel: MarketOverviewPanel | undefined,
  hasUsableData: boolean,
  refreshing: boolean,
): MarketOverviewProviderState {
  if (hasNotConfiguredReason(panel)) return 'unconfigured';
  if (refreshing || panel?.isRefreshing || panel?.providerHealth?.isRefreshing) return 'refreshing';
  if (!hasUsableData) return 'noData';
  if (hasProviderFailure(panel)) return 'refreshFailed';
  if (hasStaleSnapshot(panel)) return 'stale';
  return hasUsableData ? null : 'noData';
}

export const MarketOverviewPanelStateNotice: React.FC<{
  panel?: MarketOverviewPanel;
  hasUsableData: boolean;
  refreshing?: boolean;
}> = ({ panel, hasUsableData, refreshing = false }) => {
  const { language } = useI18n();
  const state = resolveMarketOverviewProviderState(panel, hasUsableData, refreshing);
  if (!state) {
    return null;
  }
  const failure = hasProviderFailure(panel);
  const isEnglish = language === 'en';
  const copy = isEnglish
    ? {
        unconfigured: 'Market data provider not configured',
        refreshingWithData: 'Refreshing; showing the latest available data',
        refreshingWithoutData: 'Refreshing market data',
        refreshFailed: 'Refresh failed; showing the retained usable snapshot',
        stale: 'Data is stale; showing the latest snapshot',
        noDataAfterFailure: 'Refresh failed; no usable data',
        noData: 'No usable market data',
      }
    : {
        unconfigured: '市场数据源未配置',
        refreshingWithData: '正在刷新，当前显示最近可用数据',
        refreshingWithoutData: '正在刷新市场数据',
        refreshFailed: '刷新失败，继续显示可用快照',
        stale: '数据已过期，显示最近快照',
        noDataAfterFailure: '刷新失败，暂无可用数据',
        noData: '暂无可用数据',
      };

  let message: string;
  let badge: string;
  let variant: 'neutral' | 'caution' | 'info';
  if (state === 'unconfigured') {
    message = copy.unconfigured;
    badge = isEnglish ? 'Not configured' : '未配置';
    variant = 'caution';
  } else if (state === 'refreshing') {
    message = hasUsableData ? copy.refreshingWithData : copy.refreshingWithoutData;
    badge = isEnglish ? 'Refreshing' : '刷新中';
    variant = 'info';
  } else if (state === 'noData') {
    message = failure ? copy.noDataAfterFailure : copy.noData;
    badge = isEnglish ? 'Unavailable' : '不可用';
    variant = 'caution';
  } else if (state === 'stale') {
    message = copy.stale;
    badge = isEnglish ? 'Latest snapshot' : '最近快照';
    variant = 'neutral';
  } else {
    message = copy.refreshFailed;
    badge = isEnglish ? 'Refresh failed' : '刷新失败';
    variant = 'caution';
  }

  return (
    <div data-testid="market-overview-provider-state" className="flex min-w-0 items-center gap-2">
      <TerminalChip variant={variant} className="px-2 py-1 text-[10px] font-semibold tracking-widest">
        {badge}
      </TerminalChip>
      <span className="min-w-0 truncate text-[10px] text-[color:var(--wolfy-text-muted)]">{message}</span>
    </div>
  );
};

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

function resolveMetaStatus(meta?: Pick<MarketOverviewPanel, 'providerHealth' | 'isRefreshing' | 'source' | 'freshness' | 'isFallback' | 'isStale' | 'isUnavailable'>): string {
  if (meta?.providerHealth?.status) {
    return meta.providerHealth.status;
  }
  if (meta?.isRefreshing) {
    return 'refreshing';
  }
  if (meta?.isUnavailable || meta?.source === 'unavailable' || meta?.freshness === 'unavailable') {
    return 'unavailable';
  }
  if (meta?.freshness === 'error') {
    return 'error';
  }
  if (meta?.isFallback || meta?.source === 'fallback' || meta?.freshness === 'fallback' || meta?.freshness === 'mock') {
    return 'fallback';
  }
  if (meta?.isStale || meta?.freshness === 'stale') {
    return 'stale';
  }
  if (meta?.freshness === 'live') {
    return 'live';
  }
  return 'cache';
}

function shouldSuppressRepeatedItemState(panel: MarketOverviewPanel | undefined, item: MarketOverviewPanel['items'][number]): boolean {
  const panelStatus = resolveMetaStatus(panel);
  if (!['fallback', 'stale', 'refreshing', 'error', 'unavailable', 'partial'].includes(panelStatus)) {
    return false;
  }
  return resolveMetaStatus(item) === panelStatus;
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
  const visibleItems = items.slice(0, 5);
  const hiddenItemCount = Math.max(items.length - visibleItems.length, 0);

  return (
    <MarketOverviewCardFrame
      testId={denseQuote ? 'market-overview-dense-quote-card' : undefined}
      size={denseQuote ? 'list' : 'standard'}
      className={cn('h-full', fallbackOnly ? 'border-orange-300/12' : '', className)}
    >
      <div className={cn('flex min-h-0 h-full flex-col', denseQuote ? 'gap-3' : 'gap-4')}>
        <div className="flex shrink-0 items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{eyebrow}</p>
            <h2 className="mt-1 truncate text-sm font-semibold text-[color:var(--wolfy-text-secondary)]">{title}</h2>
            <p className={cn('mt-1 max-w-xl text-[color:var(--wolfy-text-muted)]', denseQuote ? 'line-clamp-1 text-[11px] leading-4' : 'text-sm')}>{description}</p>
          </div>
          <MarketOverviewRefreshButton
            label={t('marketOverviewPage.refreshCard', { title })}
            refreshing={refreshing}
            onRefresh={onRefresh}
          />
        </div>

        <MarketOverviewPanelStateNotice
          panel={panel}
          hasUsableData={items.length > 0}
          refreshing={refreshing || loading}
        />

        {denseQuote ? (
          <div
            data-testid="market-overview-dense-quote-grid"
            className="flex min-h-0 flex-col overflow-y-auto no-scrollbar border-y border-[color:var(--wolfy-border-subtle)] ui-scroll-y-quiet"
          >
            {visibleItems.map((item) => (
              <MarketOverviewDenseQuoteItem
                key={item.symbol}
                item={item}
                neutralLabel={t('marketOverviewPage.direction.neutral')}
                suppressFreshnessBadge={shouldSuppressRepeatedItemState(panel, item)}
              />
            ))}
          </div>
        ) : (
          <div className="min-h-0 overflow-y-auto no-scrollbar ui-scroll-y-quiet">
            {visibleItems.map((item) => (
              <MarketOverviewDataRow
                key={item.symbol}
                item={item}
                neutralLabel={t('marketOverviewPage.direction.neutral')}
                suppressFreshnessBadge={shouldSuppressRepeatedItemState(panel, item)}
              />
            ))}
          </div>
        )}

        {hiddenItemCount > 0 ? (
          <p className="text-[10px] text-[color:var(--wolfy-text-muted)]">
            已优先显示关键 {visibleItems.length} 项，其余 {hiddenItemCount} 项已折叠。
          </p>
        ) : null}

        {loading ? (
          <div className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-input)] p-4 text-sm text-[color:var(--wolfy-text-muted)]">
            {t('marketOverviewPage.loading')}
          </div>
        ) : null}

        <MarketOverviewPanelFooter panel={panel} sourceLabel={sourceLabel} />
      </div>
    </MarketOverviewCardFrame>
  );
};
