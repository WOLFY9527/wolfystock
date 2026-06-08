import { describe, expect, it } from 'vitest';

import {
  createPortfolioResearchContextView,
  type PortfolioResearchContextView,
} from '../portfolioResearchContextView';

const FORBIDDEN_OUTPUT_TOKENS = [
  'quantity',
  'avgCost',
  'totalCost',
  'costBasis',
  'cash',
  'P&L',
  'marketValue',
  'totalMarketValue',
  'sourceAuthorityAllowed',
  'scoreContributionAllowed',
  'reasonCode',
  'debug',
  'cache',
  'backend',
  'provider',
  'raw',
  'broker',
  'scenario',
  'rebalance',
  'buy',
  'sell',
  'position-sizing',
  'stop-loss',
  '买入',
  '卖出',
  '止损',
  '调仓',
  '仓位',
  '盈亏',
  '成本',
  '现金',
  '市值',
  '券商',
  '同步',
] as const;

function expectConsumerSafe(view: PortfolioResearchContextView): void {
  const serialized = JSON.stringify(view);
  for (const token of FORBIDDEN_OUTPUT_TOKENS) {
    expect(serialized).not.toContain(token);
  }
}

function baseSnapshot() {
  return {
    asOf: '2026-06-08T09:30:00+08:00',
    accounts: [
      {
        accountName: '长期观察账户',
        market: 'us',
        baseCurrency: 'USD',
        totalCash: 10000,
        broker: 'hidden-broker',
        positions: [
          {
            symbol: 'AAPL',
            market: 'us',
            currency: 'USD',
            quantity: 12,
            avgCost: 120,
            marketValueBase: 2400,
            unrealizedPnlBase: 100,
            priceAsOf: '2026-06-07',
          },
          {
            symbol: 'MSFT',
            market: 'us',
            currency: 'USD',
            quantity: 5,
            avgCost: 200,
            marketValueBase: 1800,
            unrealizedPnlBase: -50,
            priceAsOf: '2026-06-07',
          },
        ],
      },
      {
        accountName: '港股观察账户',
        market: 'hk',
        baseCurrency: 'HKD',
        positions: [
          {
            symbol: '0700',
            market: 'hk',
            currency: 'HKD',
            quantity: 100,
            avgCost: 300,
            marketValueBase: 3800,
            unrealizedPnlBase: 200,
            priceAsOf: '2026-06-07',
          },
        ],
      },
    ],
    analytics: {
      risk: {
        largestPosition: {
          symbol: 'AAPL',
          percent: 42,
          marketValue: 2400,
        },
      },
    },
  };
}

describe('portfolioResearchContextView', () => {
  it('maps a held symbol into compact research context labels', () => {
    const view = createPortfolioResearchContextView({
      snapshot: baseSnapshot(),
      symbols: ['aapl'],
      riskEvidence: {
        posture: 'observe_only',
        displayLabel: '仅供观察',
        freshnessLabel: '价格快照',
        limitationLabels: ['持仓来源待核验'],
      },
    });

    expect(view).toMatchObject({
      isHeld: true,
      matchedSymbols: ['AAPL'],
      matchedHoldingsCount: 1,
      accountLabels: ['长期观察账户'],
      marketLabels: ['美股'],
      currencyLabels: ['USD'],
      concentrationLabel: '集中',
      freshnessLabel: '价格快照',
      asOf: '2026-06-08T09:30:00+08:00',
      evidencePosture: '仅供观察',
      boundaryCopy: '以下内容仅供观察，用于补充研究上下文，不构成个性化投资建议。',
    });
    expect(view.dataNotes).toEqual(expect.arrayContaining(['持仓数据待核验']));
    expectConsumerSafe(view);
  });

  it('fails closed for a symbol that is not currently held', () => {
    const view = createPortfolioResearchContextView({
      snapshot: baseSnapshot(),
      symbols: ['TSLA'],
      riskEvidence: {
        posture: 'allowed_metadata_only',
        displayLabel: '依据需复核',
        limitationLabels: [],
      },
    });

    expect(view).toMatchObject({
      isHeld: false,
      matchedSymbols: [],
      matchedHoldingsCount: 0,
      accountLabels: [],
      marketLabels: [],
      currencyLabels: [],
      concentrationLabel: '未持有该标的',
      evidencePosture: '依据需复核',
    });
    expect(view.dataNotes).toContain('未在当前持仓中识别到该研究标的。');
    expectConsumerSafe(view);
  });

  it('returns unavailable posture when portfolio data is missing', () => {
    const view = createPortfolioResearchContextView({
      snapshot: null,
      symbols: ['AAPL'],
    });

    expect(view).toEqual({
      isHeld: false,
      matchedSymbols: [],
      matchedHoldingsCount: 0,
      accountLabels: [],
      marketLabels: [],
      currencyLabels: [],
      concentrationLabel: '未连接持仓上下文',
      freshnessLabel: '未连接持仓上下文',
      evidencePosture: 'UNAVAILABLE',
      boundaryCopy: '持仓研究上下文暂不可用，仅展示独立研究信息。',
      dataNotes: ['未连接持仓上下文'],
    });
    expectConsumerSafe(view);
  });

  it('keeps partial and stale evidence observation-only with limited copy', () => {
    const staleSnapshot = {
      ...baseSnapshot(),
      isPartial: true,
      isStale: true,
      fxFreshnessState: 'stale',
      portfolioRiskEvidence: {
        freshnessLabel: 'provider_cache_stale_debug',
        limitationLabels: ['provider_timeout', 'raw_payload', 'fx_rate_stale'],
      },
    };

    const view = createPortfolioResearchContextView({
      snapshot: staleSnapshot,
      symbols: ['0700'],
      riskEvidence: {
        posture: 'observe_only',
        displayLabel: '仅供观察',
        freshnessLabel: '数据已过期',
        limitationLabels: ['provider_timeout', 'raw_payload', 'fx_rate_stale'],
      },
    });

    expect(view).toMatchObject({
      isHeld: true,
      matchedSymbols: ['0700'],
      matchedHoldingsCount: 1,
      evidencePosture: '仅供观察',
      freshnessLabel: '已使用最近一次可用数据',
      boundaryCopy: '以下内容仅供观察，用于补充研究上下文，不构成个性化投资建议。',
    });
    expect(view.dataNotes).toEqual(expect.arrayContaining([
      '当前信号置信度较低，仅供观察。',
      '部分数据暂不可用。',
      '已使用最近一次可用数据。',
    ]));
    expectConsumerSafe(view);
  });

  it('does not expose accounting, advice, provider, cache, or raw diagnostic vocabulary', () => {
    const view = createPortfolioResearchContextView({
      snapshot: {
        ...baseSnapshot(),
        sourceAuthorityAllowed: false,
        scoreContributionAllowed: false,
        reasonCode: 'debug_backend_cache_provider',
        raw: { marketValue: 9999 },
      },
      symbols: ['AAPL'],
      riskEvidence: {
        posture: 'review_required',
        displayLabel: 'provider cache debug raw reasonCode',
        freshnessLabel: 'backend_cache_stale',
        limitationLabels: [
          'sourceAuthorityAllowed',
          'scoreContributionAllowed',
          'reasonCode',
          'provider_timeout',
          'cache_debug',
          'rebalance_buy_sell_stop-loss_position-sizing',
          'quantity_avgCost_cash_marketValue_P&L',
        ],
      },
    });

    expect(Object.keys(view).sort()).toEqual([
      'accountLabels',
      'asOf',
      'boundaryCopy',
      'concentrationLabel',
      'currencyLabels',
      'dataNotes',
      'evidencePosture',
      'freshnessLabel',
      'isHeld',
      'marketLabels',
      'matchedHoldingsCount',
      'matchedSymbols',
    ]);
    expectConsumerSafe(view);
  });
});
