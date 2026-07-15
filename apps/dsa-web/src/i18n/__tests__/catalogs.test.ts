import { describe, expect, it } from 'vitest';
import { enCatalog } from '../catalogs/en';
import { zhCatalog } from '../catalogs/zh';

function collectCatalogKeys(value: unknown, prefix = ''): string[] {
  if (typeof value === 'string') {
    return [prefix];
  }
  if (!value || typeof value !== 'object') {
    return [];
  }

  return Object.entries(value)
    .flatMap(([key, child]) => collectCatalogKeys(child, prefix ? `${prefix}.${key}` : key));
}

describe('locale catalogs', () => {
  it('has the same complete translation key set in Chinese and English', () => {
    expect(collectCatalogKeys(enCatalog).sort()).toEqual(collectCatalogKeys(zhCatalog).sort());
  });
});
