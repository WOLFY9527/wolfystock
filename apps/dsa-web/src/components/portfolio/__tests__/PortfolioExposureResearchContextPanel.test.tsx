import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { PortfolioExposureResearchContextPanel } from '../PortfolioExposureResearchContextPanel';
import type { PortfolioExposureResearchContext } from '../../../types/portfolio';

const context: PortfolioExposureResearchContext = {
  dominantExposure: {
    type: 'position',
    symbol: 'AAPL',
    label: 'AAPL',
    market: 'us',
    currency: 'USD',
    marketValue: 1600,
    weightPct: 42,
    fxStatus: 'live',
  },
  concentrationContext: {
    state: 'partial',
    topWeightPct: 42,
    alert: true,
    holdingCount: 1,
    accountCount: 1,
    dominantType: 'position',
    dominantLabel: 'AAPL',
  },
  currencyContext: {
    state: 'partial',
    baseCurrency: 'CNY',
    fxFreshnessState: 'fresh',
    largestCurrency: {
      currency: 'USD',
      label: 'USD',
      weightPct: 66,
      fxStatus: 'live',
    },
    stalePairs: [],
  },
  marketContext: {
    state: 'stale',
    largestMarket: {
      market: 'us',
      label: 'US',
      weightPct: 66,
    },
    marketBreakdown: [],
    benchmarkMappingState: 'partial',
    factorMappingState: 'stale',
    sectorContextState: 'stale',
  },
  staleInputs: [
    { input: 'valuation_inputs', status: 'partial', reason: 'limited_valuation_inputs' },
    { input: 'freshness', status: 'stale', reason: 'freshness_stale' },
  ],
  evidenceGaps: ['valuation_inputs'],
  researchNextSteps: [],
  observationBoundary: {
    observationOnly: true,
    decisionGrade: false,
  },
};

describe('PortfolioExposureResearchContextPanel', () => {
  it('keeps partial and stale exposure states semantically distinct', () => {
    render(
      <PortfolioExposureResearchContextPanel
        context={context}
        lineageSummary={null}
        language="zh"
      />,
    );

    const panel = screen.getByTestId('portfolio-exposure-research-context');
    expect(panel).toHaveTextContent('证据不完整');
    expect(panel).toHaveTextContent('数据可能过期');
    expect(screen.getByTestId('portfolio-exposure-research-stale-inputs')).toHaveTextContent('估值输入 · 证据不完整');
    expect(screen.getByTestId('portfolio-exposure-research-stale-inputs')).toHaveTextContent('数据新鲜度 · 数据可能过期');
    expect(panel).not.toHaveTextContent('依据需复核');
  });
});
