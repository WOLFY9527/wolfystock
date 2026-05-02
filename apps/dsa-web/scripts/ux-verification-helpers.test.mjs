import { describe, expect, it } from 'vitest';

import {
  buildPreferredScannerConfigs,
  diffTableCounts,
  isRetryableScannerValidationError,
  summarizeFlowOutcomes,
} from './ux-verification-helpers.mjs';

describe('ux-verification-helpers', () => {
  it('diffTableCounts reports inserts and removes for tracked tables', () => {
    const before = {
      app_users: 4,
      analysis_history: 10,
      conversation_messages: 25,
      portfolio_trades: 3,
    };
    const after = {
      app_users: 5,
      analysis_history: 12,
      conversation_messages: 25,
      portfolio_trades: 2,
    };

    expect(diffTableCounts(before, after)).toEqual({
      app_users: { before: 4, after: 5, delta: 1, direction: 'up' },
      analysis_history: { before: 10, after: 12, delta: 2, direction: 'up' },
      portfolio_trades: { before: 3, after: 2, delta: -1, direction: 'down' },
    });
  });

  it('summarizeFlowOutcomes classifies pass partial fail counts', () => {
    const summary = summarizeFlowOutcomes([
      { name: 'auth', status: 'pass' },
      { name: 'home', status: 'pass' },
      { name: 'scanner', status: 'partial' },
      { name: 'chat', status: 'fail' },
    ]);

    expect(summary).toEqual({
      total: 4,
      passed: 2,
      partial: 1,
      failed: 1,
      overallStatus: 'partial',
    });
  });

  it('buildPreferredScannerConfigs prioritizes US before fallback markets', () => {
    expect(buildPreferredScannerConfigs()).toEqual([
      { market: 'us', profile: 'us_preopen_v1' },
      { market: 'hk', profile: 'hk_preopen_v1' },
      { market: 'cn', profile: 'cn_preopen_v1' },
    ]);
  });

  it('isRetryableScannerValidationError detects scanner validation payloads', () => {
    expect(isRetryableScannerValidationError({
      status: 400,
      responseBody: '{"detail":{"error":"validation_error","message":"A 股全市场快照不可用。"}}',
    })).toBe(true);
    expect(isRetryableScannerValidationError({
      status: 500,
      responseBody: '{"detail":{"error":"internal_error"}}',
    })).toBe(false);
  });
});
