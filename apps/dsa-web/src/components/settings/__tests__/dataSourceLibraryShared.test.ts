import { describe, expect, it } from 'vitest';
import { translate } from '../../../i18n/core';
import {
  buildDataCoverageGaps,
  buildDataSourceImpactView,
  type DataCoverageGapView,
  type DataSourceLibraryEntry,
} from '../dataSourceLibraryShared';

const zh = (key: string, vars?: Record<string, string | number | undefined>) => translate('zh', key, vars);

const textFor = (gap: DataCoverageGapView): string => [
  gap.missing,
  gap.impact,
  ...gap.surfaces,
].join(' ');

const findLineageGap = (): DataCoverageGapView => {
  const gap = buildDataCoverageGaps([], zh).find((candidate) => (
    candidate.surfaces.includes('Portfolio')
      && candidate.surfaces.includes('Watchlist')
      && candidate.surfaces.includes('Backtest')
  ));

  expect(gap).toBeDefined();
  return gap as DataCoverageGapView;
};

const configuredSource = (key: string, label: string): DataSourceLibraryEntry => ({
  key,
  label,
  kind: 'builtin',
  builtin: true,
  baseUrl: '',
  configured: true,
  usable: true,
  validationState: 'configured_pending',
  validationMessage: '',
  routeUsage: ['market'],
  capabilityKeys: ['market'],
  capabilityLabels: [],
  description: '',
  credentialRequired: true,
  credentialValue: '',
  credentialSchema: 'single_key',
});

describe('dataSourceLibraryShared setup guidance metadata', () => {
  it('keeps Portfolio setup guidance cache/provenance first instead of paid quote provider first', () => {
    const text = textFor(findLineageGap());

    expect(text).toContain('stored portfolio snapshots');
    expect(text).toContain('price provenance');
    expect(text).toContain('FX/cache evidence');
    expect(text).toContain('configured local/cache evidence');
    expect(text).toContain('actual close-date');
    expect(text).not.toMatch(/Finnhub|FMP|Twelve Data|API Key|可能需付费/);
  });

  it('points Watchlist setup guidance to persisted Scanner evidence and local OHLCV provenance', () => {
    const text = textFor(findLineageGap());

    expect(text).toContain('persisted Scanner evidence');
    expect(text).toContain('score freshness');
    expect(text).toContain('local OHLCV provenance');
    expect(text).not.toMatch(/付费行情|live quote|paid quote/i);
  });

  it('points Backtest setup guidance to local/cache dataset lineage and reproducibility manifests', () => {
    const text = textFor(findLineageGap());

    expect(text).toContain('local/cache dataset lineage');
    expect(text).toContain('repro manifests');
    expect(text).toContain('local OHLCV coverage');
  });

  it('does not overclaim live official or score-grade authority for the lineage guidance', () => {
    const text = textFor(findLineageGap());

    expect(text).not.toMatch(/实时|官方|可评分证据|score-grade|decision-grade|live|official/i);
  });

  it('keeps existing known and unknown provider impact behavior stable', () => {
    const polygon = buildDataSourceImpactView({
      key: 'polygon',
      label: 'Polygon',
      configured: false,
      credentialRequired: true,
      capabilityKeys: ['market'],
    }, zh);

    expect(polygon.known).toBe(true);
    expect(polygon.surfaces).toEqual([
      'Market Overview',
      'Liquidity Monitor',
      'Rotation Radar',
      'Scanner',
      'Provider Ops / system diagnostics',
    ]);
    expect(polygon.capabilities).toEqual(['quotes', 'US breadth']);
    expect(polygon.summary).toContain('grouped daily');

    const unknown = buildDataSourceImpactView({
      key: 'private_csv',
      label: 'Private CSV',
      configured: true,
      credentialRequired: false,
      capabilityKeys: ['local'],
    }, zh);

    expect(unknown.known).toBe(false);
    expect(unknown.surfaces).toEqual(['Provider Ops / system diagnostics']);
    expect(unknown.capabilities).toEqual(['diagnostics']);

    const gapKeys = buildDataCoverageGaps([configuredSource('polygon', 'Polygon')], zh)
      .map((gap) => gap.key);

    expect(gapKeys).not.toContain('market_breadth');
    expect(gapKeys).not.toContain('options_lab');
    expect(gapKeys).toContain('portfolio_watchlist_backtest_lineage');
  });
});
