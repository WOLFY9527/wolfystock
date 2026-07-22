import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { MarketOverviewPanel } from '../../../api/marketOverview';
import { MarketOverviewCard } from '../MarketOverviewCard';
import { MarketSentimentCard } from '../MarketSentimentCard';
import { VolatilityCard } from '../VolatilityCard';

const languageState = vi.hoisted(() => ({ current: 'zh' as 'zh' | 'en' }));

vi.mock('../../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: languageState.current,
    t: (key: string) => key,
  }),
}));

const usableItem = {
  symbol: 'VIX',
  label: 'VIX',
  value: 18.4,
  changePct: 1.2,
  riskDirection: 'increasing' as const,
  source: 'market-provider',
  freshness: 'delayed' as const,
};

function panel(overrides: Partial<MarketOverviewPanel> = {}): MarketOverviewPanel {
  return {
    panelName: 'TestMarketCard',
    lastRefreshAt: '2026-07-22T08:00:00Z',
    status: 'success',
    source: 'market-provider',
    sourceLabel: 'Market provider',
    updatedAt: '2026-07-22T08:00:00Z',
    freshness: 'delayed',
    items: [usableItem],
    ...overrides,
  };
}

type CardVariant = {
  name: string;
  renderCard: (statePanel: MarketOverviewPanel, refreshing?: boolean) => ReturnType<typeof render>;
};

const cardVariants: CardVariant[] = [
  {
    name: 'volatility card',
    renderCard: (statePanel, refreshing = false) => render(
      <VolatilityCard panel={statePanel} refreshing={refreshing} onRefresh={() => undefined} />,
    ),
  },
  {
    name: 'sentiment card',
    renderCard: (statePanel, refreshing = false) => render(
      <MarketSentimentCard panel={statePanel} refreshing={refreshing} onRefresh={() => undefined} />,
    ),
  },
  ...(['default', 'denseQuote'] as const).map((variant): CardVariant => ({
    name: `market overview ${variant} card`,
    renderCard: (statePanel, refreshing = false) => render(
      <MarketOverviewCard
        title="Test card"
        eyebrow="Test"
        description="Test market data"
        sourceLabel="Market provider"
        panel={statePanel}
        refreshing={refreshing}
        variant={variant}
        onRefresh={() => undefined}
      />,
    ),
  })),
];

const stateCases = [
  {
    name: 'provider not configured',
    panel: panel({
      status: 'unavailable',
      source: 'unavailable',
      freshness: 'unavailable',
      isUnavailable: true,
      degradationReason: 'provider_not_configured',
      routeRejectedReasonCodes: ['provider_not_configured'],
      errorMessage: 'provider unavailable',
      providerHealth: {
        provider: 'market-provider',
        status: 'unavailable',
        isFallback: false,
        isStale: false,
        isRefreshing: false,
        sourceLabel: 'Market provider',
      },
      items: [],
    }),
    refreshing: false,
    zh: '市场数据源未配置',
    en: 'Market data provider not configured',
    excludesRefreshFailure: true,
  },
  {
    name: 'refresh failure with retained usable snapshot',
    panel: panel({
      status: 'failure',
      freshness: 'cached',
      isFromSnapshot: true,
      errorMessage: 'provider timeout',
      refreshError: 'provider timeout',
    }),
    refreshing: false,
    zh: '刷新失败，继续显示可用快照',
    en: 'Refresh failed; showing the retained usable snapshot',
  },
  {
    name: 'stale retained snapshot',
    panel: panel({
      freshness: 'stale',
      isStale: true,
      isFromSnapshot: true,
      providerHealth: {
        provider: 'market-provider',
        status: 'stale',
        isFallback: false,
        isStale: true,
        isRefreshing: false,
        sourceLabel: 'Market provider',
      },
    }),
    refreshing: false,
    zh: '数据已过期，显示最近快照',
    en: 'Data is stale; showing the latest snapshot',
  },
  {
    name: 'no usable data after a provider failure',
    panel: panel({
      status: 'failure',
      freshness: 'error',
      isUnavailable: true,
      errorMessage: 'provider timeout',
      refreshError: 'provider timeout',
      items: [],
    }),
    refreshing: false,
    zh: '刷新失败，暂无可用数据',
    en: 'Refresh failed; no usable data',
  },
  {
    name: 'active refresh',
    panel: panel(),
    refreshing: true,
    zh: '正在刷新，当前显示最近可用数据',
    en: 'Refreshing; showing the latest available data',
  },
] as const;

afterEach(() => {
  cleanup();
  languageState.current = 'zh';
});

describe.each(['zh', 'en'] as const)('%s market provider state copy', (language) => {
  it.each(cardVariants)('shows all five truthful states in the $name', ({ renderCard }) => {
    languageState.current = language;

    for (const stateCase of stateCases) {
      renderCard(stateCase.panel, stateCase.refreshing);
      const notice = screen.getByTestId('market-overview-provider-state');
      expect(notice, stateCase.name).toHaveTextContent(stateCase[language]);
      if ('excludesRefreshFailure' in stateCase && stateCase.excludesRefreshFailure) {
        expect(notice).not.toHaveTextContent(/刷新失败|refresh failed/i);
      }
      cleanup();
    }
  });
});

it('does not add a provider-state notice to a healthy usable panel', () => {
  render(
    <MarketOverviewCard
      title="Test card"
      eyebrow="Test"
      description="Test market data"
      sourceLabel="Market provider"
      panel={panel()}
      onRefresh={() => undefined}
    />,
  );

  expect(screen.queryByTestId('market-overview-provider-state')).not.toBeInTheDocument();
});

it('does not render an unavailable sentiment score as a zero-width numeric gauge value', () => {
  const { container } = render(
    <MarketSentimentCard
      panel={panel({ items: [{ ...usableItem, symbol: 'FGI', value: null }] })}
      onRefresh={() => undefined}
    />,
  );

  expect(screen.getByText('N/A')).toBeInTheDocument();
  expect(container.querySelector('[style*="width: 0%"]')).toBeNull();
});
