import { describe, expect, it } from 'vitest';

import {
  formatCompareStateLabel,
  formatCompareStateWithRaw,
  getTerminalChipVariantFromState,
} from '../compareDisplayHelpers';

describe('compareDisplayHelpers', () => {
  it('preserves compare state labels and raw fallback boundaries', () => {
    expect(formatCompareStateLabel()).toBe('--');
    expect(formatCompareStateLabel('')).toBe('--');
    expect(formatCompareStateLabel('available')).toBe('可用');
    expect(formatCompareStateLabel('unavailable')).toBe('不可用');
    expect(formatCompareStateLabel('stored_compare_projection')).toBe('已完成比较结果');
    expect(formatCompareStateLabel('provider_runtime_scope')).toBe('比较边界需复核');
    expect(formatCompareStateLabel('plain label')).toBe('plain label');
    expect(formatCompareStateLabel('custom_status')).toBe('比较边界需复核');
    expect(formatCompareStateWithRaw('available')).toBe('可用');
    expect(formatCompareStateWithRaw('plain_label')).toBe('比较边界需复核');
    expect(formatCompareStateWithRaw('plain label')).toBe('plain label');
  });

  it('preserves terminal chip variants for every known state family', () => {
    expect(getTerminalChipVariantFromState()).toBe('neutral');
    expect(getTerminalChipVariantFromState('winner')).toBe('success');
    expect(getTerminalChipVariantFromState('aligned')).toBe('success');
    expect(getTerminalChipVariantFromState('direct')).toBe('success');
    expect(getTerminalChipVariantFromState('missing')).toBe('danger');
    expect(getTerminalChipVariantFromState('unavailable')).toBe('danger');
    expect(getTerminalChipVariantFromState('limited')).toBe('caution');
    expect(getTerminalChipVariantFromState('partial')).toBe('caution');
    expect(getTerminalChipVariantFromState('different_parameter')).toBe('info');
    expect(getTerminalChipVariantFromState('divergent')).toBe('info');
    expect(getTerminalChipVariantFromState('same_family_comparable')).toBe('info');
    expect(getTerminalChipVariantFromState('baseline')).toBe('neutral');
  });
});
