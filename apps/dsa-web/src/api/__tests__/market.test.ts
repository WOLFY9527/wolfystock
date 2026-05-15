import { describe, expect, it } from 'vitest';
import * as marketModule from '../market';

describe('market API path join hygiene', () => {
  it('normalizes market endpoint joins without introducing double slashes', () => {
    const buildMarketApiPath = (marketModule as { buildMarketApiPath?: (path: string) => string }).buildMarketApiPath;

    expect(buildMarketApiPath?.('/crypto')).toBe('/api/v1/market/crypto');
    expect(buildMarketApiPath?.('crypto')).toBe('/api/v1/market/crypto');
  });

  it('normalizes absolute market stream URLs without double slashes after /api/v1', () => {
    const buildMarketApiUrl = (marketModule as {
      buildMarketApiUrl?: (baseUrl: string, path: string) => string;
    }).buildMarketApiUrl;

    expect(buildMarketApiUrl?.('https://example.com/api/v1/', '/market/crypto/stream'))
      .toBe('https://example.com/api/v1/market/crypto/stream');
    expect(buildMarketApiUrl?.('https://example.com/api/v1', 'market/crypto/stream'))
      .toBe('https://example.com/api/v1/market/crypto/stream');
  });
});
