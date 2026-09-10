import { describe, expect, it } from 'vitest';
import {
  buildResearchWorkspacePath,
  normalizeResearchWorkspaceScannerRunId,
  parseResearchWorkspaceSearch,
} from '../researchWorkspaceRoute';

describe('researchWorkspaceRoute Scanner lineage', () => {
  it('serializes only the bounded Scanner run pointer alongside lookup context', () => {
    const path = buildResearchWorkspacePath('stock-structure', 'en', {
      symbol: 'AAPL',
      market: 'US',
      source: 'scanner',
      scannerRunId: 84,
    });

    expect(path).toBe('/en/stocks/AAPL/structure-decision?symbol=AAPL&market=US&source=scanner&scannerRunId=84');
    expect(path).not.toMatch(/score|cutoff|readiness|authority|profile/i);
  });

  it('round-trips a valid Scanner run pointer across refreshable search state', () => {
    expect(parseResearchWorkspaceSearch('?symbol=AAPL&market=US&source=scanner&scannerRunId=84')).toEqual({
      symbol: 'AAPL',
      market: 'US',
      source: 'scanner',
      scannerRunId: 84,
    });
  });

  it.each(['', '0', '-1', '1.5', '1e3', 'abc', '9007199254740992'])(
    'fails closed for malformed Scanner run identity %j',
    (value) => {
      expect(normalizeResearchWorkspaceScannerRunId(value)).toBeNull();
      expect(parseResearchWorkspaceSearch(`?scannerRunId=${encodeURIComponent(value)}`).scannerRunId).toBeNull();
    },
  );
});
