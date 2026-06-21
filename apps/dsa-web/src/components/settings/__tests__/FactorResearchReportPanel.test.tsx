import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import FactorResearchReportPanel from '../FactorResearchReportPanel';

const { buildFactorResearchReport } = vi.hoisted(() => ({
  buildFactorResearchReport: vi.fn(),
}));

vi.mock('../../../api/quant', () => ({
  quantApi: {
    buildFactorResearchReport,
  },
}));

function buildReportResponse() {
  return {
    status: 'partial',
    boundary: {
      purpose: 'diagnostic factor report',
      researchOnly: true,
      diagnosticOnly: true,
      suppliedObservationsOnly: true,
      portfolioOptimizer: false,
      professionalReadinessClaimed: false,
      forwardReturnsRequiredForPerformance: true,
      externalDataHydrationExecuted: false,
      liveQuoteHydrationExecuted: false,
      forwardReturnsComputed: false,
    },
    factorMetadata: [
      {
        factorId: 'momentum.momentum_21d',
        registryState: 'registered',
        label: 'Momentum 21D',
        description: 'Supplied-input research factor only.',
        family: 'momentum',
        direction: 'higher_is_better',
        unit: 'score',
        defaultLookbackDays: 21,
        tags: ['momentum', 'research'],
      },
      {
        factorId: 'trend.trend_strength_20d',
        registryState: 'registered',
        label: 'Trend Strength 20D',
        description: 'Peer factor for diagnostics.',
        family: 'trend',
        direction: 'higher_is_better',
        unit: 'score',
        defaultLookbackDays: 20,
        tags: ['trend'],
      },
    ],
    inputShape: {
      observationCount: 24,
      metricObservationCount: 24,
      forwardReturnObservationCount: 24,
      factorCount: 2,
      factorIds: ['momentum.momentum_21d', 'trend.trend_strength_20d'],
      symbolCount: 4,
      symbols: ['AAA', 'BBB', 'CCC', 'DDD'],
      asOfStart: '2026-05-01',
      asOfEnd: '2026-05-03',
      asOfCount: 3,
      forwardReturnHorizons: ['1d', '5d'],
      portfolioWeightCount: 4,
      longWeightCount: 2,
      shortWeightCount: 2,
      neutralizationAxes: ['sector'],
      minGroupSize: 2,
      marketCapBucketCount: 5,
      hashAlgorithm: 'sha256',
      inputContentHash: '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
    },
    report: {
      window: {
        asOfStart: '2026-05-01',
        asOfEnd: '2026-05-03',
        asOfCount: 3,
        observationCount: 24,
      },
      factorCoverage: [
        {
          factorId: 'momentum.momentum_21d',
          observationCount: 12,
          symbolCount: 4,
          window: {
            asOfStart: '2026-05-01',
            asOfEnd: '2026-05-03',
            asOfCount: 3,
            observationCount: 12,
          },
        },
      ],
      metricsSummary: [
        {
          factorId: 'momentum.momentum_21d',
          window: {
            asOfStart: '2026-05-01',
            asOfEnd: '2026-05-03',
            asOfCount: 3,
            observationCount: 12,
          },
          ic: [
            { horizon: '1d', value: 0.6, sampleSize: 3 },
            { horizon: '5d', value: 0.3, sampleSize: 3 },
          ],
          rankIc: [
            { horizon: '1d', value: 0.5, sampleSize: 3 },
            { horizon: '5d', value: 0.2, sampleSize: 3 },
          ],
          decay: [
            { horizon: '1d', icValue: 0.6, decayRatio: 1, sampleSize: 3 },
            { horizon: '5d', icValue: 0.3, decayRatio: 0.5, sampleSize: 3 },
          ],
          turnover: { value: 0.25, sampleSize: 2 },
          factorCorrelation: [
            { peerFactorId: 'trend.trend_strength_20d', value: -0.2, sampleSize: 3 },
          ],
        },
      ],
      neutralizationSummary: [
        {
          factorId: 'momentum.momentum_21d',
          axis: 'sector',
          neutralizationMethod: 'sector_residual',
          sampleSize: 12,
          totalObservations: 12,
          neutralizedObservations: 12,
          missingGroupMetadata: 0,
          insufficientGroupObservations: 0,
          invalidObservationValues: 0,
          warnings: [],
        },
      ],
      exposureSummary: [
        {
          scope: 'long_short',
          factorId: 'momentum.momentum_21d',
          exposure: 0.12,
          weightedExposure: 0.48,
          grossExposure: 0.52,
          netExposure: 0.48,
          sampleSize: 4,
          coverage: 1,
          missingFactorCount: 0,
          window: {
            asOfStart: '2026-05-01',
            asOfEnd: '2026-05-03',
            asOfCount: 3,
            observationCount: 12,
          },
          warnings: [],
          longExposure: 0.3,
          shortExposure: 0.18,
        },
      ],
      missingDataReasons: [
        {
          section: 'metrics',
          reason: 'missing_forward_returns',
          factorId: 'momentum.momentum_21d',
          context: 'ic:1d',
        },
      ],
      warnings: ['missing_forward_returns'],
    },
    missingDataReasons: [
      {
        section: 'metrics',
        reason: 'missing_forward_returns',
        factorId: 'momentum.momentum_21d',
        context: 'ic:1d',
      },
    ],
    warnings: ['missing_forward_returns'],
  };
}

describe('FactorResearchReportPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders research metrics and diagnostics for a valid report response', async () => {
    buildFactorResearchReport.mockResolvedValueOnce(buildReportResponse());

    render(<FactorResearchReportPanel />);

    const panel = screen.getByTestId('factor-research-report-panel');
    fireEvent.change(screen.getByLabelText('输入 JSON'), {
      target: { value: '{"observations":[],"metricObservations":[]}' },
    });
    fireEvent.click(within(panel).getByRole('button', { name: '生成报表' }));

    await waitFor(() => expect(buildFactorResearchReport).toHaveBeenCalledTimes(1));
    expect(buildFactorResearchReport).toHaveBeenCalledWith({
      observations: [],
      metricObservations: [],
    });

    await waitFor(() => expect(panel).toHaveTextContent('部分完成'));

    expect(panel).toHaveTextContent('研究仅供观察');
    expect(panel).toHaveTextContent('Momentum 21D');
    expect(panel).toHaveTextContent('Trend Strength 20D');
    expect(panel).toHaveTextContent('IC');
    expect(panel).toHaveTextContent('Rank IC');
    expect(panel).toHaveTextContent('0.6000');
    expect(panel).toHaveTextContent('0.2500');
    expect(panel).toHaveTextContent('sector_residual');
    expect(panel).toHaveTextContent('long_short');
    expect(panel).toHaveTextContent('01234567');
    expect(panel).not.toHaveTextContent(/recommended|best factor|ranking|target price|stop loss|advice|requestId|traceId|debug|rawPayload|sourceAuthority/i);
  });

  it('fails closed on missing input without calling the API', () => {
    render(<FactorResearchReportPanel />);

    const panel = screen.getByTestId('factor-research-report-panel');
    expect(within(panel).getByRole('button', { name: '生成报表' })).toBeDisabled();
    expect(panel).toHaveTextContent('研究输入缺失');
    expect(buildFactorResearchReport).not.toHaveBeenCalled();
  });

  it('fails closed on invalid JSON without calling the API', async () => {
    render(<FactorResearchReportPanel />);

    const panel = screen.getByTestId('factor-research-report-panel');
    fireEvent.change(screen.getByLabelText('输入 JSON'), {
      target: { value: '{not-json' },
    });
    fireEvent.click(within(panel).getByRole('button', { name: '生成报表' }));

    await waitFor(() => expect(panel).toHaveTextContent('输入必须是有效 JSON。'));
    expect(buildFactorResearchReport).not.toHaveBeenCalled();
    expect(panel).not.toHaveTextContent(/recommended|best factor|ranking|target price|stop loss|advice|requestId|traceId|debug|rawPayload|sourceAuthority/i);
  });
});
