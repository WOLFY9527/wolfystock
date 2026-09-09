import { createHash } from 'node:crypto';
import { describe, expect, it } from 'vitest';
import { enCatalog } from '../catalogs/en';
import { zhCatalog } from '../catalogs/zh';

type CatalogEntry = readonly [key: string, value: string];

const CATALOG_FINGERPRINT = {
      en: { entryCount: 3076, sha256: '7d801af9ed8c10b2d5f2d504578086d358ee6d89c2947b2372bafa9d3de4eb87' },
      zh: { entryCount: 3076, sha256: 'f8e6489dad9a902dff76d561b52e232d08af6a13b0be9541eb19ec69044dbac4' },
} as const;

function collectCatalogEntries(value: unknown, prefix = ''): CatalogEntry[] {
  if (typeof value === 'string') {
    return [[prefix, value]];
  }
  if (!value || typeof value !== 'object') {
    return [];
  }

  return Object.entries(value)
    .flatMap(([key, child]) => collectCatalogEntries(child, prefix ? `${prefix}.${key}` : key));
}

function catalogFingerprint(catalog: unknown) {
  const entries = collectCatalogEntries(catalog).sort(([left], [right]) => (
    left < right ? -1 : left > right ? 1 : 0
  ));
  return {
    entryCount: entries.length,
    sha256: createHash('sha256').update(JSON.stringify(entries)).digest('hex'),
  };
}

describe('locale catalogs', () => {
  it('has the same complete translation key set in Chinese and English', () => {
    expect(collectCatalogEntries(enCatalog).map(([key]) => key).sort())
      .toEqual(collectCatalogEntries(zhCatalog).map(([key]) => key).sort());
  });

  it('preserves every current-main catalog key and value exactly', () => {
    expect({
      en: catalogFingerprint(enCatalog),
      zh: catalogFingerprint(zhCatalog),
    }).toEqual(CATALOG_FINGERPRINT);
  });
});
