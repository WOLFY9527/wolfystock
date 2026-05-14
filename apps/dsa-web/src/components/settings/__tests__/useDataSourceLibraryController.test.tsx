import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { systemConfigApi } from '../../../api/systemConfig';
import { useDataSourceLibraryController } from '../useDataSourceLibraryController';

vi.mock('../../../api/systemConfig', () => ({
  systemConfigApi: {
    testBuiltinDataSource: vi.fn(),
    testCustomDataSource: vi.fn(),
  },
}));

const ALL_ITEM_MAP = new Map<string, string>([
  ['TWELVE_DATA_API_KEY', 'td-sample-key'],
  ['FINNHUB_API_KEY', 'fh-sample-key'],
]);

const DATA_SUMMARY = {
  market: ['twelve_data', 'finnhub'],
  fundamentals: [],
  news: [],
  sentiment: [],
} as const;

const DATA_PRIORITY_KEYS = {
  market: 'REALTIME_SOURCE_PRIORITY',
  fundamentals: 'FUNDAMENTAL_SOURCE_PRIORITY',
  news: 'NEWS_SOURCE_PRIORITY',
  sentiment: 'SENTIMENT_SOURCE_PRIORITY',
} as const;

const SAVE_EXTERNAL_ITEMS = vi.fn(async () => {});
const DELETE_SOURCE = vi.fn();
const PRETTY_SOURCE_LABEL = (value: string) => value;
const T = (key: string) => key;

function Harness() {
  const controller = useDataSourceLibraryController({
    allItemMap: ALL_ITEM_MAP,
    dataSummary: DATA_SUMMARY,
    dataPriorityKeys: DATA_PRIORITY_KEYS,
    saveExternalItems: SAVE_EXTERNAL_ITEMS,
    onDeleteSourceFromRoutes: DELETE_SOURCE,
    prettySourceLabel: PRETTY_SOURCE_LABEL,
    t: T,
  });

  return (
    <div>
      <button type="button" onClick={() => void controller.validateDataSourceEntry('twelve_data')}>
        validate twelve
      </button>
      <button type="button" onClick={() => void controller.validateDataSourceEntry('finnhub')}>
        validate finnhub
      </button>
    </div>
  );
}

describe('useDataSourceLibraryController', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('uses an HK sample symbol only for Twelve Data built-in validation', async () => {
    vi.mocked(systemConfigApi.testBuiltinDataSource).mockResolvedValue({
      provider: 'twelve_data',
      ok: true,
      status: 'success',
      checkedAt: '2026-05-14T09:10:00+08:00',
      durationMs: 32,
      keyMasked: 'td-s...-key',
      checks: [],
      summary: 'ok',
      suggestion: 'ok',
    });

    render(<Harness />);

    fireEvent.click(screen.getByRole('button', { name: 'validate twelve' }));

    await waitFor(() => {
      expect(systemConfigApi.testBuiltinDataSource).toHaveBeenCalledWith({
        provider: 'twelve_data',
        symbol: 'HK00700',
        credential: 'td-sample-key',
        secret: '',
        timeoutSeconds: 5,
      });
    });
  });

  it('keeps the existing non-HK symbol for other built-in providers', async () => {
    vi.mocked(systemConfigApi.testBuiltinDataSource).mockResolvedValue({
      provider: 'finnhub',
      ok: true,
      status: 'success',
      checkedAt: '2026-05-14T09:10:00+08:00',
      durationMs: 32,
      keyMasked: 'fh-s...-key',
      checks: [],
      summary: 'ok',
      suggestion: 'ok',
    });

    render(<Harness />);

    fireEvent.click(screen.getByRole('button', { name: 'validate finnhub' }));

    await waitFor(() => {
      expect(systemConfigApi.testBuiltinDataSource).toHaveBeenCalledWith({
        provider: 'finnhub',
        symbol: 'MSFT',
        credential: 'fh-sample-key',
        secret: '',
        timeoutSeconds: 5,
      });
    });
  });
});
