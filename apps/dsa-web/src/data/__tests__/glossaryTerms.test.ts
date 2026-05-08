import { describe, expect, it } from 'vitest';
import { getGlossaryTerm, glossaryTerms, glossaryTermsById, type GlossaryCategory } from '../glossaryTerms';

const requiredLabels = [
  '波动率',
  'IV',
  'Delta',
  'Theta',
  'Gamma',
  'OI',
  '成交量',
  '回撤',
  '最大回撤',
  '夏普比率',
  '胜率',
  '盈亏比',
  '回测',
  '样本外',
  '数据延迟',
  'fallback',
  'provider',
  'cache',
  '熔断',
  'SLA',
  '曝险',
  '可用现金',
  '持仓',
  '手工记账',
  '观察信号',
  '证据置信度',
  '数据可信度',
];

const requiredCategories: GlossaryCategory[] = [
  'market',
  'scanner',
  'options',
  'backtest',
  'portfolio',
  'risk',
  'provider/data',
  'admin/ops',
];

function chineseLength(value: string) {
  return Array.from(value).length;
}

describe('glossaryTerms', () => {
  it('covers the required launch guidance categories and initial terms', () => {
    expect(new Set(glossaryTerms.map((term) => term.category))).toEqual(new Set(requiredCategories));
    expect(requiredLabels.every((label) => glossaryTerms.some((term) => term.labelZh === label))).toBe(true);
  });

  it('keeps every item concise, typed, and advice-free', () => {
    const forbiddenCopy = /买入|卖出|下单|立即交易|必买|稳赚|保证收益|guaranteed|best contract|AI recommends you buy/i;
    const ids = new Set<string>();

    for (const term of glossaryTerms) {
      expect(term.id).toMatch(/^[a-z0-9-]+$/);
      expect(ids.has(term.id)).toBe(false);
      ids.add(term.id);
      expect(chineseLength(term.explanation)).toBeLessThanOrEqual(90);
      expect(chineseLength(term.professionalNote)).toBeLessThanOrEqual(140);
      expect(chineseLength(term.caveat ?? '')).toBeLessThanOrEqual(100);
      expect(`${term.explanation}${term.professionalNote}${term.caveat ?? ''}`).not.toMatch(forbiddenCopy);
    }
  });

  it('exports stable lookup helpers by id', () => {
    expect(glossaryTermsById['implied-volatility']?.labelZh).toBe('IV');
    expect(getGlossaryTerm('max-drawdown')?.labelZh).toBe('最大回撤');
    expect(getGlossaryTerm('missing-term')).toBeUndefined();
  });
});
