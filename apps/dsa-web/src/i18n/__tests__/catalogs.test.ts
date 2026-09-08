import { createHash } from 'node:crypto';
import { describe, expect, it } from 'vitest';
import { enCatalog } from '../catalogs/en';
import { zhCatalog } from '../catalogs/zh';

type CatalogEntry = readonly [key: string, value: string];

const CATALOG_FINGERPRINT = {
      en: { entryCount: 3070, sha256: '6e38898b90dd99f1fdcc30e83a596707fdacf18914392c464e966e27db7611e0' },
      zh: { entryCount: 3070, sha256: '79a9f2129569d29d20dd353c89a0b30c8261874272ca90ccd59ec18ca342883f' },
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
