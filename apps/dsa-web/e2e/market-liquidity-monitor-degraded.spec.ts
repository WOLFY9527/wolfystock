import type { Page, Route } from '@playwright/test';
import { expect, test } from './fixtures/appSmoke';
import { openAuthenticatedRouteSmoke } from './fixtures/authenticatedRouteSmoke';

const viewports = [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
];

async function fulfillJson(route: Route, payload: unknown) {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function installDegradedLiquidityMonitorPayload(page: Page) {
  await page.route('**/api/v1/market/liquidity-monitor', async (route) => {
    await fulfillJson(route, {
      endpoint: '/api/v1/market/liquidity-monitor',
      generatedAt: '2026-05-20T09:30:00+08:00',
      score: {
        value: 50,
        regime: 'unavailable',
        confidence: 0.18,
        includedIndicatorCount: 0,
        possibleIndicatorWeight: 43,
        includedIndicatorWeight: 0,
      },
      freshness: {
        status: 'fallback',
        weakestIndicatorFreshness: 'unavailable',
        latestAsOf: '2026-05-20T09:30:00+08:00',
      },
      indicators: [
        {
          key: 'usd_pressure',
          label: 'DXY / 美元压力',
          status: 'partial',
          freshness: 'delayed',
          includedInScore: false,
          scoreContribution: 0,
          scoreWeight: 0,
          summary: '仅有 yfinance_proxy 代理观察，缺少 official_or_authorized.fx_dxy，当前不计分。',
          updatedAt: '2026-05-20T09:30:00+08:00',
        },
        {
          key: 'us_etf_flow_proxy',
          label: 'US ETF 资金代理',
          status: 'partial',
          freshness: 'delayed',
          includedInScore: false,
          scoreContribution: 0,
          scoreWeight: 0,
          summary: '仅有 ETF 代理观察，未取得授权资金流证据，当前不计分。',
          updatedAt: '2026-05-20T09:30:00+08:00',
        },
        {
          key: 'crypto_funding',
          label: 'Crypto Funding',
          status: 'unavailable',
          freshness: 'unavailable',
          includedInScore: false,
          scoreContribution: 0,
          scoreWeight: 0,
          summary: '缺少 Binance funding 快照，仅保留缺口披露。',
          updatedAt: '2026-05-20T09:30:00+08:00',
        },
      ],
      liquidityImpulseSynthesis: {
        liquidityImpulse: 'expanding_liquidity',
        impulseLabel: 'Liquidity appears to be expanding',
        subtype: 'crypto_beta_expansion',
        confidence: 0.32,
        confidenceLabel: 'low',
        pillarScores: {
          dollar_pressure: 0,
          equity_flow_proxy: 0,
          crypto_liquidity_beta: 0,
          funding_stress: 0,
        },
        directionScore: 0.24,
        dominantDrivers: [
          {
            key: 'liquidity_monitor:usd_pressure',
            label: 'DXY proxy observation',
            pillar: 'dollar_pressure',
            direction: 'supports_expansion',
            signal: 0.24,
            weight: 0.2,
            impact: 0.05,
            source: 'yfinance_proxy',
            sourceTier: 'unofficial_public_api',
            trustLevel: 'usable_with_caution',
            freshness: 'delayed',
            observationOnly: true,
            scoreContributionAllowed: false,
            includedInScore: false,
            proxyOnly: true,
            discountReasons: ['proxy_only_discount', 'score_contribution_not_allowed'],
            degradationReason: 'proxy_only_missing_real_source',
          },
        ],
        counterEvidence: [],
        dataGaps: [
          {
            key: 'liquidity_monitor:crypto_funding',
            label: 'Crypto Funding',
            pillar: 'funding_stress',
            reason: 'missing_direction_or_magnitude',
            source: 'unavailable',
            sourceTier: 'unavailable',
            trustLevel: 'unavailable',
            freshness: 'unavailable',
            observationOnly: true,
            scoreContributionAllowed: false,
            includedInScore: false,
            proxyOnly: false,
            degradationReason: 'provider_unavailable',
          },
          {
            key: 'missing:equity_flow_proxy',
            label: 'Missing scoring evidence for equity_flow_proxy',
            pillar: 'equity_flow_proxy',
            reason: 'missing_scoring_evidence',
          },
        ],
        narrativeBullets: [
          'Proxy-only inputs and unavailable funding data were not promoted into a reliable liquidity expansion call.',
        ],
        evidenceQuality: {
          version: 'liquidity_impulse_synthesis_v1',
          inputCount: 3,
          scoringEvidenceCount: 0,
          scoringPillarCount: 0,
          coveredPillars: [],
          missingPillars: ['dollar_pressure', 'equity_flow_proxy', 'crypto_liquidity_beta', 'funding_stress'],
          discountedEvidenceCount: 1,
          observationOnlyEvidenceCount: 1,
          scoreBlockedEvidenceCount: 3,
          proxyOnlyScoringCount: 1,
          realScoringEvidenceCount: 0,
          allScoringEvidenceProxyOnly: true,
          dataGapCount: 2,
        },
        notInvestmentAdvice: true,
      },
      advisoryDisclosure: '仅用于观察市场流动性环境，非买卖建议，不触发扫描、回测或组合动作。',
      sourceMetadata: {
        externalProviderCalls: false,
        providerRuntimeChanged: false,
        marketCacheMutation: false,
      },
    });
  });
}

async function expectNoHorizontalOverflow(page: Page) {
  await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

async function expectNoRawDebugFields(page: Page) {
  const bodyText = await page.locator('body').innerText();
  expect(bodyText).not.toMatch(
    /raw[_\s-]?(payload|response)|provider[_\s-]?(payload|debug)|coverageDiagnostics|liquidityImpulseSynthesis|evidenceQuality|scoreContributionAllowed|sourceMetadata|providerRuntimeChanged|marketCacheMutation/i,
  );
}

test.describe('Liquidity Monitor degraded proxy-only state', () => {
  for (const viewport of viewports) {
    test(`renders consumer-safe degraded states at ${viewport.width}x${viewport.height}`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await installDegradedLiquidityMonitorPayload(page);
      const smoke = await openAuthenticatedRouteSmoke(page, '/zh/market/liquidity-monitor');

      try {
        await expect(page.getByRole('heading', { name: '流动性监测' })).toBeVisible({ timeout: 15_000 });
        const guidancePanel = page.getByTestId('liquidity-monitor-guidance-panel');
        await expect(guidancePanel).toContainText('本模块暂不可用，请稍后重试。');
        await expect(guidancePanel).toContainText('评分已暂停');
        await expect(guidancePanel).toContainText('暂不可用');
        await expect(guidancePanel).toContainText('当前受限模块');
        await expect(guidancePanel).toContainText('已使用最近一次可用数据');
        await expect(page.getByTestId('liquidity-decision-readiness')).toContainText('数据更新');
        await expect(page.getByTestId('liquidity-decision-readiness')).toContainText('最近更新');
        await expect(page.getByTestId('liquidity-decision-readiness')).toContainText('评分状态');
        await expect(page.getByTestId('liquidity-decision-readiness')).toContainText('流动性状态');
        await expect(page.getByTestId('liquidity-decision-readiness')).not.toContainText('不计分');
        await expect(page.locator('body')).not.toContainText(/guaranteed|decision-grade|强结论|主结论|provider_unavailable|scoreContributionAllowed|proxy-only|Binance|official_or_authorized|yfinance_proxy|外部调用|运行顺序|缓存写入/i);
        await expect(page.getByRole('button', { name: '展开 技术细节' })).toHaveCount(0);
        await expect(page.getByTestId('liquidity-monitor-guidance-panel')).not.toContainText('流动性方向待确认');
        await expect(page.getByTestId('liquidity-monitor-guidance-panel')).not.toContainText('不升级为真实扩张或收缩结论');

        await expectNoRawDebugFields(page);
        await expectNoHorizontalOverflow(page);
        smoke.expectNoConsolePageErrors();
      } finally {
        await smoke.cleanup();
      }
    });
  }
});
