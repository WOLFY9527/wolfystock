import { describe, expect, it } from 'vitest';

import { consumerPresentationDataState, consumerPresentationText } from '../consumerPresentationBoundary';

const INTERNAL_LEAK_PATTERN = /provider|runtime|debug|raw|payload|cache|fallback|sourceAuthorityAllowed|scoreContributionAllowed|reasonCodes|routeRejectedReasonCodes|Polygon|Tushare/i;

describe('consumerPresentationDataState', () => {
  it('preserves bounded consumer data-state distinctions without exposing raw diagnostics', () => {
    const cases = [
      {
        input: { status: 'available', freshness: 'fresh', confidence: 0.92, sourceAuthorityAllowed: true, scoreContributionAllowed: true },
        state: 'available',
        label: '可用',
      },
      {
        input: { status: 'partial', freshness: 'fresh', coverage: 0.64, sourceAuthorityAllowed: true, scoreContributionAllowed: true },
        state: 'partial',
        label: '部分可用',
      },
      {
        input: { status: 'available', freshness: 'stale', isStale: true, sourceAuthorityAllowed: true, scoreContributionAllowed: true },
        state: 'stale',
        label: '已延迟',
      },
      {
        input: { status: 'missing', freshness: 'unavailable', providerDiagnostics: { raw_code: 'provider_timeout' } },
        state: 'unavailable',
        label: '不可用',
      },
      {
        input: { status: 'ready', freshness: 'fresh', confidence: 0.24, sourceAuthorityAllowed: true, scoreContributionAllowed: true },
        state: 'insufficient',
        label: '证据不足',
      },
      {
        input: { status: 'blocked', sourceAuthorityAllowed: false, routeRejectedReasonCodes: ['source_authority_denied'] },
        state: 'blocked',
        label: '已阻断',
      },
      {
        input: { status: 'loading', freshness: 'pending', isRefreshing: true },
        state: 'initializing',
        label: '初始化中',
      },
      {
        input: { status: 'provider_error', diagnostics: { providerName: 'Polygon', rawPayload: true } },
        state: 'error',
        label: '读取异常',
      },
    ] as const;

    const views = cases.map(({ input }) => consumerPresentationDataState(input, 'zh'));

    expect(views.map((view) => view.state)).toEqual(cases.map((item) => item.state));
    expect(views.map((view) => view.label)).toEqual(cases.map((item) => item.label));
    expect(JSON.stringify(views)).not.toMatch(INTERNAL_LEAK_PATTERN);
  });

  it('localizes state presentation through the same boundary', () => {
    expect(consumerPresentationDataState({ status: 'blocked' }, 'en')).toMatchObject({
      state: 'blocked',
      label: 'Blocked',
      tone: 'danger',
    });
  });

  it('reuses status-label mappings so raw state tokens stay bounded at the consumer boundary', () => {
    expect(consumerPresentationText('available', 'zh')).toBe('数据可用');
    expect(consumerPresentationText('insufficient', 'zh')).toBe('证据不足');
    expect(consumerPresentationText('initializing', 'zh')).toBe('初始化中');
    expect(consumerPresentationText('error', 'zh')).toBe('数据读取异常');
  });
});
