import { describe, expect, it } from 'vitest';

import {
  createConsumerDataQualityGlossaryEntry,
  type ConsumerDataQualityGlossaryEntry,
} from '../consumerDataQualityGlossary';

const RAW_TOKEN_PATTERN = /stale|partial|unavailable|degraded|fallback|demo|proxy|sample|missing|sourceAuthority|scoreContribution|freshness|sourceRefs?|reasonCodes?|debug|provider|cache|runtime|raw|official_public|public_proxy|synthetic_fixture/i;

function expectSafeGlossaryOutput(entry: ConsumerDataQualityGlossaryEntry): void {
  expect(Object.keys(entry).sort()).toEqual([
    'observationOnly',
    'safeLabel',
    'severity',
    'shortExplanation',
  ]);
  expect(entry.safeLabel).toBeTruthy();
  expect(entry.shortExplanation).toBeTruthy();
  expect(JSON.stringify(entry)).not.toMatch(RAW_TOKEN_PATTERN);
}

describe('consumerDataQualityGlossary', () => {
  it('maps the v1 data quality vocabulary into safe Chinese explanations', () => {
    const cases = [
      {
        rawState: 'stale',
        safeLabel: '数据有延迟',
        shortExplanation: '当前展示的是最近一次可用信息，时效性需要复核。',
        severity: 'warning',
        observationOnly: true,
      },
      {
        rawState: 'partial',
        safeLabel: '证据不完整',
        shortExplanation: '部分信息暂缺，当前结论只能作为观察线索。',
        severity: 'warning',
        observationOnly: true,
      },
      {
        rawState: 'unavailable',
        safeLabel: '数据暂不可用',
        shortExplanation: '当前模块缺少足够信息，请稍后刷新后再查看。',
        severity: 'critical',
        observationOnly: true,
      },
      {
        rawState: 'degraded',
        safeLabel: '质量受限',
        shortExplanation: '当前信息完整度或稳定性不足，需要降低解读强度。',
        severity: 'warning',
        observationOnly: true,
      },
      {
        rawState: 'fallback',
        safeLabel: '使用替代信息',
        shortExplanation: '当前使用最近可用或替代来源的信息，不代表实时状态。',
        severity: 'warning',
        observationOnly: true,
      },
      {
        rawState: 'demo',
        safeLabel: '演示信息',
        shortExplanation: '当前内容仅用于功能展示，不能作为真实市场依据。',
        severity: 'info',
        observationOnly: true,
      },
      {
        rawState: 'proxy_or_sample_evidence',
        safeLabel: '替代证据',
        shortExplanation: '当前证据来自替代或样例信息，只适合做方向性观察。',
        severity: 'warning',
        observationOnly: true,
      },
      {
        rawState: 'missing_evidence',
        safeLabel: '证据缺口',
        shortExplanation: '关键证据仍在补齐，暂不形成进一步判断。',
        severity: 'critical',
        observationOnly: true,
      },
      {
        rawState: 'sourceAuthorityAllowed=false',
        safeLabel: '来源待确认',
        shortExplanation: '当前来源条件未完全确认，先保持观察。',
        severity: 'warning',
        observationOnly: true,
      },
      {
        rawState: 'scoreContributionAllowed=false',
        safeLabel: '评分暂不启用',
        shortExplanation: '当前信息未进入评分口径，不能提升结论强度。',
        severity: 'warning',
        observationOnly: true,
      },
      {
        rawState: 'freshness_limitation',
        safeLabel: '时效待确认',
        shortExplanation: '当前时效状态仍需确认，解读时请保留不确定性。',
        severity: 'warning',
        observationOnly: true,
      },
    ] as const;

    for (const item of cases) {
      const entry = createConsumerDataQualityGlossaryEntry(item.rawState);

      expect(entry).toEqual({
        safeLabel: item.safeLabel,
        shortExplanation: item.shortExplanation,
        severity: item.severity,
        observationOnly: item.observationOnly,
      });
      expectSafeGlossaryOutput(entry);
    }
  });

  it('normalizes common raw-ish provider/debug variants without echoing tokens', () => {
    const variants = [
      'fallback_static',
      'synthetic_fixture',
      'public_proxy',
      'provider_timeout',
      'sourceRefs',
      'reasonCodes',
      'freshness=unavailable',
      'cache_stale',
      'provider_runtime_debug',
      'raw_payload_missing',
    ];

    for (const variant of variants) {
      expectSafeGlossaryOutput(createConsumerDataQualityGlossaryEntry(variant));
    }
  });
});
