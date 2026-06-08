import type { Page, Route } from '@playwright/test';
import { expect, test } from './fixtures/appSmoke';

const routePath = '/zh/market-overview';
const forbiddenInternalPattern = /raw|internal|debug|provider|cache|router|env|trace|credential/i;
const forbiddenExecutionPattern = /buy now|sell now|place order|submit order|broker|order payload|买入按钮|建议买入|建议卖出|立即交易|下单|提交订单|券商|经纪商/i;

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function signIn(page: Page, redirectPath: string) {
  await page.goto(`/login?redirect=${encodeURIComponent(redirectPath)}`);
  await page.locator('#username').fill('wolfy-user');
  await page.locator('#password').fill('mock-password');
  await Promise.all([
    page.waitForResponse((response) => response.url().includes('/api/v1/auth/login') && response.status() === 200),
    page.getByRole('button', { name: /sign in|登录继续|授权进入工作台|完成设置并登录/i }).click(),
  ]);
  await page.goto(redirectPath);
  await page.waitForLoadState('domcontentloaded');
}

function actionabilityReadyPayload() {
  return {
    source: 'computed',
    sourceLabel: '系统计算',
    updatedAt: '2026-06-04T09:00:00Z',
    asOf: '2026-06-04T09:00:00Z',
    freshness: 'cached',
    isFallback: false,
    isStale: false,
    confidence: 0.82,
    reliableInputCount: 12,
    requiredReliableInputCount: 5,
    reliablePanelCount: 5,
    requiredReliablePanelCount: 3,
    fallbackInputCount: 1,
    excludedInputCount: 1,
    isReliable: true,
    temperatureAvailable: true,
    disabledReason: null,
    unavailableReason: null,
    insufficientReliableInputs: false,
    trustLevel: 'reliable',
    sourceTier: 'unofficial_public_api',
    conclusionAllowed: true,
    marketActionabilityFrame: {
      contractVersion: 'market_intelligence_actionability_v1',
      verdict: 'observe_only',
      confidence: {
        value: 0.41,
        label: 'low',
        capReasons: ['observation_only'],
      },
      evidenceCoverage: {
        scoreGradeCount: 2,
        observationOnlyCount: 1,
        missingCount: 0,
        totalCount: 3,
      },
      missingEvidence: [],
      regimeContext: {
        primaryRegime: 'risk_on_liquidity_expansion',
        liquidityImpulse: 'expanding_liquidity',
        rotationPosture: 'leading',
        contradictionCount: 1,
        freshnessFloor: 'delayed',
      },
      sourceAuthority: 'observationOnly',
      freshness: 'delayed',
      noAdviceBoundary: true,
      nextResearchStep: '继续确认流动性是否保持扩张',
      debugRef: 'market:temperature:actionability',
    },
    marketIntelligenceEvidenceFrame: {
      contractVersion: 'market_intelligence_evidence_v1',
      frameState: 'observe_only',
      evidenceCoverage: {
        scoreGradeCount: 3,
        observationOnlyCount: 2,
        missingCount: 0,
        totalCount: 5,
      },
      regimeEvidence: {
        domain: 'macro',
        state: 'score_grade',
        freshness: 'delayed',
        primaryRegime: 'risk_on_liquidity_expansion',
        blockingReasons: [],
      },
      liquidityEvidence: {
        domain: 'liquidity',
        state: 'observation_only',
        freshness: 'delayed',
        likelyDestination: 'broad_equities',
        blockingReasons: ['observation_only'],
      },
      rotationEvidence: {
        domain: 'rotation',
        state: 'observation_only',
        freshness: 'delayed',
        leadingThemeCount: 2,
        blockingReasons: ['observation_only'],
      },
      breadthEvidence: {
        domain: 'breadth',
        state: 'score_grade',
        freshness: 'delayed',
        breadthValue: 1.7,
        blockingReasons: [],
      },
      scannerContextEvidence: {
        domain: 'scanner_context',
        state: 'score_grade',
        freshness: 'delayed',
        readinessState: 'ready',
        noAdviceBoundary: true,
        blockingReasons: [],
      },
      missingEvidence: [],
      blockingReasons: ['observation_only'],
      sourceAuthority: 'observationOnly',
      freshness: 'delayed',
      nextEvidenceNeeded: [],
      noAdviceBoundary: true,
      debugRef: 'market:temperature:evidence',
    },
    regimeSummary: {
      headline: '风险偏好改善但仍需确认',
      detail: '流动性与宽度改善，轮动仍偏观察。',
      riskLevel: 'medium',
    },
    marketRegimeSynthesis: {
      regime: 'risk_on_liquidity_expansion',
      summary: '流动性改善，风险偏好修复。',
      confidence: 0.64,
    },
    marketDecisionSemantics: {
      version: 'market_decision_semantics_v1',
      posture: 'offensive',
      postureConfidence: {
        value: 64,
        label: 'medium',
        capReasons: ['counter_evidence_present'],
      },
      exposureBias: 'risk_on_watch',
      directionReadiness: {
        status: 'direction_ready',
        confidenceLabel: 'medium',
        scoreGradePillars: {
          count: 3,
          items: [],
        },
      },
      claimBoundary: 'research_only',
      noAdviceBoundary: true,
      summary: '仅供研究观察，不构成交易指令。',
    },
    scores: {
      overall: { value: 62, label: '偏暖', trend: 'improving', description: '风险偏好改善，但宏观压力仍需关注。' },
      usRiskAppetite: { value: 68, label: '偏暖', trend: 'improving', description: '美股指数与风险情绪同步改善。' },
      cnMoneyEffect: { value: 55, label: '中性', trend: 'stable', description: '指数表现尚可，但市场宽度一般。' },
      macroPressure: { value: 58, label: '中性偏高', trend: 'rising', description: '美元与利率走强。' },
      liquidity: { value: 52, label: '中性', trend: 'stable', description: '资金环境整体平稳。' },
    },
  };
}

function actionabilityInsufficientPayload() {
  return {
    ...actionabilityReadyPayload(),
    marketActionabilityFrame: {
      ...actionabilityReadyPayload().marketActionabilityFrame,
      verdict: 'insufficient',
      confidence: {
        value: 0.16,
        label: 'insufficient',
        capReasons: ['stale_evidence', 'fallback_evidence'],
      },
      evidenceCoverage: {
        scoreGradeCount: 0,
        observationOnlyCount: 0,
        missingCount: 5,
        totalCount: 5,
      },
      sourceAuthority: 'insufficient',
      freshness: 'fallback',
      missingEvidence: ['macro', 'liquidity', 'rotation', 'breadth', 'scanner_context'],
      nextResearchStep: '等待更高授权流动性证据',
    },
    marketIntelligenceEvidenceFrame: {
      ...actionabilityReadyPayload().marketIntelligenceEvidenceFrame,
      frameState: 'insufficient',
      evidenceCoverage: {
        scoreGradeCount: 0,
        observationOnlyCount: 0,
        missingCount: 5,
        totalCount: 5,
      },
      regimeEvidence: {
        domain: 'macro',
        state: 'missing',
        freshness: 'fallback',
        blockingReasons: ['missing_required_evidence'],
      },
      liquidityEvidence: {
        domain: 'liquidity',
        state: 'missing',
        freshness: 'fallback',
        blockingReasons: ['missing_required_evidence'],
      },
      rotationEvidence: {
        domain: 'rotation',
        state: 'missing',
        freshness: 'fallback',
        blockingReasons: ['fallback_evidence'],
      },
      breadthEvidence: {
        domain: 'breadth',
        state: 'missing',
        freshness: 'fallback',
        blockingReasons: ['missing_required_evidence'],
      },
      scannerContextEvidence: {
        domain: 'scanner_context',
        state: 'missing',
        freshness: 'fallback',
        blockingReasons: ['missing_required_evidence'],
      },
      missingEvidence: ['macro', 'liquidity', 'rotation', 'breadth', 'scanner_context'],
      blockingReasons: ['missing_required_evidence', 'stale_evidence', 'fallback_evidence'],
      sourceAuthority: 'insufficient',
      freshness: 'fallback',
      nextEvidenceNeeded: ['等待更高授权流动性证据'],
    },
  };
}

async function installTemperatureOverride(page: Page, payload: unknown) {
  await page.route('**/api/v1/market/temperature', async (route) => {
    await fulfillJson(route, payload);
  });
}

test.describe('market intelligence actionability browser smoke', () => {
  test('keeps actionability diagnostics out of the default market overview surface', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await installTemperatureOverride(page, actionabilityReadyPayload());
    await signIn(page, routePath);

    await expect(page.getByTestId('market-overview-shell')).toBeVisible({ timeout: 15_000 });
    const visualStrip = page.getByTestId('market-overview-visual-evidence-strip');
    await expect(page.getByTestId('market-overview-research-readiness-strip')).toHaveCount(0);
    await expect(page.getByTestId('market-overview-main-grid')).toBeVisible();
    await expect(visualStrip).toBeVisible();
    await expect(visualStrip).toContainText('核心图表证据');
    await expect(page.getByTestId('market-overview-visual-card-core-trends')).toBeVisible();
    await expect(page.getByTestId('market-overview-visual-card-risk-pressure')).toBeVisible();
    await expect(page.getByTestId('market-overview-visual-card-flow-rotation')).toBeVisible();

    const order = await page.evaluate(() => {
      const mainGrid = document.querySelector('[data-testid="market-overview-main-grid"]') as HTMLElement | null;
      const visualEvidence = document.querySelector('[data-testid="market-overview-visual-evidence-strip"]') as HTMLElement | null;
      return mainGrid && visualEvidence
        ? mainGrid.compareDocumentPosition(visualEvidence)
        : null;
    });
    expect(order).toBe(4);

    await expect(page.getByTestId('market-decision-semantics-strip')).toContainText('不构成交易指令');
    const visualText = await visualStrip.innerText();
    const bodyText = await page.locator('body').innerText();
    expect(bodyText).not.toMatch(/研究就绪度|市场研判可用性|证据覆盖\s*\d+\/\d+|来源级别|高授权|观察级|评分级|缺口\s*\d+|更高授权|限制因素|回退|缓存|仅供界面演示|保持界面结构|等待真实行情源/);
    expect(bodyText).not.toMatch(forbiddenInternalPattern);
    expect(bodyText).not.toMatch(forbiddenExecutionPattern);
    expect(visualText).not.toMatch(forbiddenInternalPattern);
    expect(visualText).not.toMatch(forbiddenExecutionPattern);
    await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  });

  test('fail closes missing evidence without default diagnostic strips or trading language', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await installTemperatureOverride(page, actionabilityInsufficientPayload());
    await signIn(page, routePath);

    await expect(page.getByTestId('market-overview-shell')).toBeVisible({ timeout: 15_000 });
    const visualStrip = page.getByTestId('market-overview-visual-evidence-strip');
    await expect(page.getByTestId('market-overview-research-readiness-strip')).toHaveCount(0);
    await expect(page.getByTestId('market-overview-main-grid')).toBeVisible();
    await expect(visualStrip).toBeVisible();
    await expect(page.getByTestId('market-decision-semantics-strip')).toContainText('不构成交易指令');

    const visualText = await visualStrip.innerText();
    const bodyText = await page.locator('body').innerText();
    expect(bodyText).not.toMatch(/研究就绪度|市场研判可用性|证据覆盖\s*\d+\/\d+|来源级别|高授权|观察级|评分级|缺口\s*\d+|更高授权|限制因素|回退|缓存|仅供界面演示|保持界面结构|等待真实行情源/);
    expect(bodyText).not.toMatch(forbiddenInternalPattern);
    expect(bodyText).not.toMatch(forbiddenExecutionPattern);
    expect(visualText).not.toMatch(forbiddenInternalPattern);
    expect(visualText).not.toMatch(forbiddenExecutionPattern);
    await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  });
});
