import { describe, expect, it } from 'vitest';
import { classifyDesignDebtText, qualifyDesignDebt } from './design-debt-ratchet.mjs';
import { shouldScanFile } from './check-design-constitution.mjs';

const zero = { literalFontSize: 0, literalRadius: 0, literalColor: 0, arbitraryShadow: 0, otherLiteralNumeric: 0 };

describe('design debt ratchet', () => {
  it('does not misclassify semantic CSS-variable arbitrary utilities', () => {
    expect(classifyDesignDebtText('text-[color:var(--wolfy-text-secondary)] bg-[var(--wolfy-surface)] text-[hsl(var(--state-info-hsl))] shadow-[0_0_8px_hsl(var(--state-info-hsl))]').length).toBe(0);
  });

  it('classifies literal typography, radius, colors, and shadows', () => {
    const categories = classifyDesignDebtText('text-[11px] rounded-[7px] bg-[#123456] shadow-[0_0_8px_#000] w-[23px]').map((item) => item.category);
    expect(categories).toEqual(expect.arrayContaining(['literalFontSize', 'literalRadius', 'literalColor', 'arbitraryShadow', 'otherLiteralNumeric']));
  });

  it('rejects candidate growth and accepts reductions', () => {
    expect(qualifyDesignDebt({ candidate: { ...zero, literalFontSize: 2 }, baseline: { ...zero, literalFontSize: 1 } })).toEqual(expect.arrayContaining([expect.objectContaining({ rule: 'design-debt-growth' })]));
    expect(qualifyDesignDebt({ candidate: zero, baseline: { ...zero, literalFontSize: 1 } })).toEqual([]);
  });

  it('rejects high-priority debt introduced in changed production files', () => {
    expect(qualifyDesignDebt({ candidate: zero, baseline: zero, changedFiles: { ...zero, literalRadius: 1 }, changedBaseline: zero })).toEqual(expect.arrayContaining([expect.objectContaining({ rule: 'changed-file-high-priority-debt', category: 'literalRadius' })]));
  });

  it('excludes test, generated, and artifact fixtures from production inventory', () => {
    expect(shouldScanFile('src/pages/Example.tsx')).toBe(true);
    expect(shouldScanFile('src/pages/__tests__/Example.test.tsx')).toBe(false);
    expect(shouldScanFile('src/generated/Example.tsx')).toBe(false);
    expect(shouldScanFile('dist/assets/Example.js')).toBe(false);
  });
});
