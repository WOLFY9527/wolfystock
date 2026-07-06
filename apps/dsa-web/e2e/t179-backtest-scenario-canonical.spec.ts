import type { Locator, Page, Route } from '@playwright/test';
import { expect, test } from './fixtures/appSmoke';

const desktopViewport = { width: 1440, height: 1000 };
const narrowViewport = { width: 390, height: 844 };
const timestamp = '2026-06-15T09:30:00Z';

const forbiddenInternalPattern =
  /raw\s+(payload|response|schema|prompt|trace)|debug\s+(payload|response|schema|prompt|panel)|provider\s+(route|payload|response)|cache\s+(router|payload|response)|stack\s+trace|traceback|sourceAuthority|providerRoute|api[_\s-]?key\s*[=:]|password\s*[=:]|session[_\s-]?id\s*[=:]|secret\s*[=:]|bearer\s+[a-z0-9._-]+|sk-[a-z0-9_-]{12,}/i;
const forbiddenExecutionPattern =
  /建议买入|建议卖出|立即交易|提交订单|连接券商|连接经纪商|真实下单|立即下单|place order|submit order|connect broker|must buy|must sell|buy now|sell now|AI recommends/i;

const signedInUser = {
  id: 'user-1',
  username: 'wolfy-user',
  displayName: 'Wolfy User',
  role: 'user',
  isAdmin: false,
  isAuthenticated: true,
  transitional: false,
  authEnabled: true,
};

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function installSignedInSessionRoutes(page: Page) {
  await page.route('**/api/v1/auth/status**', async (route) => {
    await fulfillJson(route, {
      authEnabled: true,
      loggedIn: true,
      passwordSet: true,
      passwordChangeable: true,
      setupState: 'enabled',
      currentUser: signedInUser,
    });
  });

  await page.route('**/api/v1/auth/me**', async (route) => {
    await fulfillJson(route, signedInUser);
  });
}

async function expectNoHorizontalOverflow(page: Page) {
  await expect
    .poll(async () => page.evaluate(() => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)))
    .toBeLessThanOrEqual(1);
}

async function expectConsumerSafeText(locator: Locator) {
  const text = await locator.innerText();
  expect(text).not.toMatch(forbiddenInternalPattern);
  expect(text).not.toMatch(forbiddenExecutionPattern);
}

function observeMutationRequests(page: Page) {
  const requests: string[] = [];
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (!url.pathname.startsWith('/api/v1/')) return;
    if (request.method() === 'GET' || request.method() === 'HEAD' || request.method() === 'OPTIONS') return;
    requests.push(`${request.method()} ${url.pathname}`);
  });
  return requests;
}

function cockpitPayload() {
  return {
    schemaVersion: 'market_decision_cockpit.v1',
    generatedAt: timestamp,
    marketRegimeDecision: {
      regime: 'riskOn',
      confidence: 'medium',
      confidenceScore: 0.68,
      driverScores: {
        dealerGamma: { score: 0, evidenceState: 'unavailable' },
        breadthParticipation: { score: 58, evidenceState: 'score_grade' },
        volatilityStructure: { score: 72, evidenceState: 'score_grade' },
        crossAssetRisk: { score: 28, evidenceState: 'score_grade' },
      },
    },
    researchQueuePreview: {
      topCandidates: [],
      queueQuality: 'mixed',
      evidenceGaps: [],
      previewOnly: true,
    },
    optionsStructureStatus: {
      gammaEvidenceStatus: 'unavailable',
      observationOnly: true,
      decisionGrade: false,
      missingEvidence: [],
      blockedReasonCodes: [],
    },
    cockpitSummary: {
      whatChanged: [],
      whyItMatters: [],
      whatToWatch: [],
      confidenceLimits: [],
    },
    noAdviceDisclosure: 'Research context only.',
    dataQuality: { status: 'partial' },
  };
}

function scenarioPayload(scenarioName: string) {
  const unavailable = scenarioName === 'gammaUnavailable';
  return {
    schemaVersion: 'market_scenario_lab_engine.v1',
    contractStatus: {
      state: unavailable ? 'blocked' : 'degraded',
      label: unavailable ? 'Scenario pending' : 'Scenario constrained by evidence gaps',
      message: unavailable
        ? 'Scenario output is blocked until baseline evidence improves.'
        : 'Scenario comparison is available, but incomplete evidence keeps the result observation-only.',
    },
    selectedScenario: {
      presetId: scenarioName,
      name: scenarioName,
      label: unavailable ? 'Gamma gap' : scenarioName === 'liquidityStress' ? 'Liquidity stress observation' : 'Volatility stress observation',
      category: unavailable ? 'Evidence gap' : 'Stress frame',
      description: 'Stress selected drivers to compare research-context sensitivity.',
      inputAssumptions: [
        'Uses market context supplied with the request.',
        'Compares deterministic driver changes without fetching fresh market data.',
      ],
      expectedDriverImpacts: [
        { driver: 'Volatility structure', direction: 'pressure', magnitude: 'high' },
        { driver: 'Breadth participation', direction: 'pressure', magnitude: 'medium' },
      ],
      evidenceLimits: ['Breadth and volatility observations need fresh confirmation before the frame can strengthen.'],
    },
    baseMarketContext: {
      label: 'Decision Cockpit market context',
      message: 'Base regime context was supplied by the request and is treated as observation-only evidence.',
      evidenceState: 'degraded',
      scoringDriverCount: 6,
    },
    baseRegime: {
      regime: unavailable ? 'lowConfidence' : 'riskOn',
      confidence: unavailable ? 'low' : 'medium',
      confidenceScore: unavailable ? 0 : 0.68,
    },
    scenarioRegime: {
      regime: unavailable ? 'lowConfidence' : 'mixed',
      confidence: unavailable ? 'low' : 'low',
      confidenceScore: unavailable ? 0 : 0.43,
      status: unavailable ? 'unavailable' : undefined,
    },
    baselineReadiness: unavailable
      ? {
          status: 'blocked',
          baselineSnapshot: {
            state: 'missing',
            available: false,
            affectedComponents: ['baselineSnapshot'],
          },
          marketFrame: {
            state: 'missing',
            available: false,
            affectedComponents: ['marketFrame'],
          },
          driverInputs: {
            state: 'missing',
            availableDriverKeys: [],
            partialDriverKeys: [],
            missingDriverKeys: ['dealerGamma'],
            affectedDriverKeys: ['dealerGamma'],
          },
          evidenceCompleteness: {
            state: 'partial',
            gaps: ['baselineSnapshot', 'marketFrame', 'dealerGamma'],
          },
          observationOnly: true,
          blocked: true,
          affectedBaselineComponents: ['baselineSnapshot', 'marketFrame'],
          affectedDriverKeys: ['dealerGamma'],
          evidenceGaps: ['baselineSnapshot', 'marketFrame', 'dealerGamma'],
          lastUpdated: timestamp,
        }
      : {
          status: 'partial',
          baselineSnapshot: {
            state: 'partial',
            available: false,
            lastUpdated: timestamp,
            affectedComponents: ['baselineSnapshot'],
          },
          marketFrame: {
            state: 'available',
            available: true,
            lastUpdated: timestamp,
            affectedComponents: [],
          },
          driverInputs: {
            state: 'partial',
            availableDriverKeys: ['breadthParticipation', 'volatilityStructure'],
            partialDriverKeys: [],
            missingDriverKeys: ['dealerGamma'],
            affectedDriverKeys: ['dealerGamma'],
          },
          evidenceCompleteness: {
            state: 'partial',
            gaps: ['baselineSnapshot', 'dealerGamma'],
          },
          observationOnly: true,
          blocked: false,
          affectedBaselineComponents: ['baselineSnapshot'],
          affectedDriverKeys: ['dealerGamma'],
          evidenceGaps: ['baselineSnapshot', 'dealerGamma'],
          lastUpdated: timestamp,
        },
    confidenceDelta: unavailable ? 0 : -0.25,
    driverDeltas: unavailable ? {} : { breadthParticipation: -75, volatilityStructure: -145 },
    changedDrivers: unavailable ? [] : ['breadthParticipation', 'volatilityStructure'],
    scenarioSummary: unavailable
      ? ['Scenario lab is unavailable because base regime evidence is missing.']
      : ['Breadth participation weakens quickly under the selected stress.'],
    whatWouldConfirm: ['Score-grade evidence would need to show stressed drivers moving together.'],
    whatWouldInvalidate: ['The scenario frame weakens if score-grade evidence does not move with the selected shocks.'],
    evidenceLimits: unavailable
      ? ['Base regime evidence is missing or below the minimum driver coverage for scenario analysis.']
      : ['Breadth and volatility observations need fresh confirmation before the frame can strengthen.'],
    noAdviceDisclosure: 'Research planning only.',
  };
}

async function installScenarioRoutes(page: Page, delayMs = 125) {
  const scenarioPosts: string[] = [];

  await page.route('**/api/v1/market/decision-cockpit**', async (route) => {
    await fulfillJson(route, cockpitPayload());
  });

  await page.route('**/api/v1/market/scenario-lab**', async (route) => {
    scenarioPosts.push(route.request().postData() ?? '');
    const body = route.request().postDataJSON() as { scenarioName?: string } | null;
    await new Promise((resolve) => setTimeout(resolve, delayMs));
    await fulfillJson(route, scenarioPayload(body?.scenarioName ?? 'volatilitySpike'));
  });

  return scenarioPosts;
}

test.describe('T179 Backtest and Scenario canonical workflow', () => {
  test('keeps Backtest setup passive and explicit across desktop and narrow states', async ({ page }) => {
    for (const viewport of [desktopViewport, narrowViewport]) {
      await page.setViewportSize(viewport);
      await installSignedInSessionRoutes(page);
      const mutationRequests = observeMutationRequests(page);

      await page.goto('/zh/backtest');
      await page.waitForLoadState('domcontentloaded');

      const shell = page.getByTestId('backtest-bento-page');
      const workspace = page.getByTestId('normal-backtest-workspace');
      const readiness = page.getByTestId('normal-backtest-execution-readiness');
      const preview = page.getByTestId('backtest-result-preview-panel');

      await expect(shell).toBeVisible({ timeout: 15_000 });
      await expect(workspace).toBeVisible();
      await expect(readiness).toBeVisible();
      await expect(preview).toBeVisible();
      await expect(preview).toContainText(/结果预览|Result preview/);
      expect(mutationRequests).toEqual([]);

      const symbolInput = page.getByLabel(/标的代码|Ticker/i).first();
      await symbolInput.focus();
      await expect(symbolInput).toBeFocused();
      await symbolInput.fill('');
      await expect(preview).toContainText(/未选择标的|No symbol/);
      await expect(readiness).toContainText(/等待样本状态|结果结构不可用|未选择标的|Incomplete|No symbol|unavailable/i);
      expect(mutationRequests).toEqual([]);

      const runButton = page.getByRole('button', { name: /执行回测任务|Execute backtest task|检查数据就绪度|Checking data readiness/i }).first();
      await expect(runButton).toBeVisible();
      await runButton.focus();
      await expect(runButton).toBeFocused();

      await expectConsumerSafeText(shell);
      if (viewport.width <= 390) {
        await expectNoHorizontalOverflow(page);
      }
    }
  });

  test('shows Backtest result and compare routes as research evidence without unsafe copy', async ({ page }) => {
    await page.setViewportSize(desktopViewport);
    await installSignedInSessionRoutes(page);

    await page.goto('/zh/backtest/results/34');
    await page.waitForLoadState('domcontentloaded');

    const resultPage = page.getByTestId('deterministic-backtest-result-page');
    const report = page.getByTestId('backtest-result-report');
    const summary = page.getByTestId('backtest-report-summary');
    const chart = page.getByTestId('backtest-report-chart');
    const chartWorkspace = page.getByTestId('deterministic-backtest-chart-workspace');
    const risk = page.getByTestId('backtest-report-risk-diagnostics');
    const assumptions = page.getByTestId('backtest-report-execution-assumptions');
    const dataQuality = page.getByTestId('backtest-report-data-quality');
    const trades = page.getByTestId('backtest-report-trade-table');
    const evidence = page.getByTestId('backtest-report-evidence-details');

    await expect(resultPage).toBeVisible({ timeout: 15_000 });
    await expect(report).toBeVisible();
    await expect(summary).toContainText('研究结论');
    await expect(summary).toContainText('非真实成交记录');
    await expect(chart).toBeVisible();
    await expect(chartWorkspace).toContainText(/权益曲线|回撤|日盈亏/);
    await expect(risk).toContainText(/最大回撤|回撤与压力解释/);
    await expect(trades).toBeVisible();
    await expect(dataQuality).toContainText(/数据质量|样本/);
    await expect(assumptions).toContainText(/执行假设|手续费|滑点|成本/);
    await expect(evidence).not.toHaveJSProperty('open', true);
    await expectConsumerSafeText(report);

    await page.setViewportSize(narrowViewport);
    await expectNoHorizontalOverflow(page);

    await page.goto('/zh/backtest/compare');
    await page.waitForLoadState('domcontentloaded');
    const compare = page.getByTestId('rule-backtest-compare-page');
    await expect(compare).toBeVisible({ timeout: 15_000 });
    await expect(compare).toContainText(/比较|Compare|回测/);
    await expectConsumerSafeText(compare);
    await expectNoHorizontalOverflow(page);
  });

  test('runs Scenario Lab only through explicit evaluation and clears stale results on preset change', async ({ page }) => {
    await page.setViewportSize(desktopViewport);
    await installSignedInSessionRoutes(page);
    const scenarioPosts = await installScenarioRoutes(page);

    await page.goto('/zh/scenario-lab');
    await page.waitForLoadState('domcontentloaded');

    const scenarioPage = page.getByTestId('scenario-lab-page');
    await expect(scenarioPage).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('scenario-lab-setup-idle')).toContainText('尚未执行情景评估');
    expect(scenarioPosts).toHaveLength(0);

    const idleEvaluate = page.getByTestId('scenario-lab-setup-idle').getByRole('button', { name: '评估情景' });
    await idleEvaluate.focus();
    await expect(idleEvaluate).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('button', { name: /评估中/ }).first()).toBeVisible();

    const firstRead = page.getByTestId('scenario-lab-first-read-summary');
    await expect(firstRead).toBeVisible({ timeout: 15_000 });
    await expect(firstRead).toHaveAttribute('role', 'region');
    await expect(firstRead).toHaveAttribute('aria-live', 'polite');
    await expect(firstRead).toContainText('情景摘要');
    await expect(firstRead).toContainText('证据边界');
    await expect(page.getByTestId('scenario-evidence-pack-registry')).toBeVisible();
    expect(scenarioPosts).toHaveLength(1);

    await page.getByRole('button', { name: '流动性压力' }).click();
    await expect(page.getByTestId('scenario-lab-setup-idle')).toContainText('流动性压力');
    await expect(page.getByTestId('scenario-lab-first-read-summary')).toHaveCount(0);
    expect(scenarioPosts).toHaveLength(1);

    await page.getByTestId('scenario-lab-setup-idle').getByRole('button', { name: '评估情景' }).click();
    await expect(page.getByTestId('scenario-lab-first-read-summary')).toContainText('流动性压力', { timeout: 15_000 });
    expect(scenarioPosts).toHaveLength(2);

    await page.goto('/zh/scenario-lab?scenario=gammaUnavailable');
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByTestId('scenario-lab-setup-idle')).toBeVisible({ timeout: 15_000 });
    const postsBeforeUnavailableRun = scenarioPosts.length;
    await page.getByTestId('scenario-lab-setup-idle').getByRole('button', { name: '评估情景' }).click();
    await expect(page.getByTestId('scenario-lab-unavailable-state')).toContainText('情景待更新', { timeout: 15_000 });
    expect(scenarioPosts).toHaveLength(postsBeforeUnavailableRun + 1);
    await expectConsumerSafeText(scenarioPage);

    await page.setViewportSize(narrowViewport);
    await expectNoHorizontalOverflow(page);
  });
});
