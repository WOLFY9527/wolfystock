import { describe, expect, it } from 'vitest';
import {
  DOMAIN_EDUCATION_CATEGORIES,
  DOMAIN_EDUCATION_ENTRIES,
  type DomainEducationCategory,
} from '../domainEducation';

const forbiddenTradingAdvicePattern =
  /应该买|应该卖|应该开仓|应该下单|建议买入|建议卖出|立即交易|下单|提交订单|订单载荷|开仓执行|加仓建议|减仓建议|仓位建议|持仓建议|必买|稳赚|保证收益|guaranteed|best contract|AI recommends you buy|buy now|sell now|place order|submit order/i;

const credentialLikePattern =
  /(?:\bsk-[A-Za-z0-9_-]{12,}\b|\b[A-Z0-9]{20,}\b|(?:api[_-]?key|token|secret|password|passwd|cookie|session[_-]?id|bearer)\s*[:=]\s*\S+)/;

const chineseLength = (value: string) => Array.from(value).length;

const validCategories = new Set<DomainEducationCategory>(DOMAIN_EDUCATION_CATEGORIES);

const serializeEntry = (entry: unknown) => JSON.stringify(entry);

describe('DOMAIN_EDUCATION_ENTRIES', () => {
  it('contains at least 60 reusable education copy entries', () => {
    expect(DOMAIN_EDUCATION_ENTRIES.length).toBeGreaterThanOrEqual(60);
  });

  it('uses unique ids and valid categories', () => {
    const ids = new Set<string>();

    for (const entry of DOMAIN_EDUCATION_ENTRIES) {
      expect(ids.has(entry.id), `duplicate id: ${entry.id}`).toBe(false);
      ids.add(entry.id);
      expect(validCategories.has(entry.category), `invalid category for ${entry.id}`).toBe(true);
    }
  });

  it('keeps beginner-facing fields inside copy length budgets', () => {
    for (const entry of DOMAIN_EDUCATION_ENTRIES) {
      expect(chineseLength(entry.shortZh), `${entry.id} shortZh`).toBeLessThanOrEqual(60);
      expect(chineseLength(entry.explainZh), `${entry.id} explainZh`).toBeLessThanOrEqual(160);
      expect(chineseLength(entry.beginnerExampleZh), `${entry.id} beginnerExampleZh`).toBeLessThanOrEqual(120);
      expect(chineseLength(entry.caveatZh), `${entry.id} caveatZh`).toBeLessThanOrEqual(120);
    }
  });

  it('does not contain direct trading advice phrases', () => {
    for (const entry of DOMAIN_EDUCATION_ENTRIES) {
      expect(serializeEntry(entry), entry.id).not.toMatch(forbiddenTradingAdvicePattern);
    }
  });

  it('does not contain credential-like strings', () => {
    for (const entry of DOMAIN_EDUCATION_ENTRIES) {
      expect(serializeEntry(entry), entry.id).not.toMatch(credentialLikePattern);
    }
  });
});
