import type { Page, Route } from '@playwright/test';
import { expect, test } from './fixtures/appSmoke';

const viewports = [
  { label: 'desktop', width: 1440, height: 900 },
  { label: 'tablet', width: 1024, height: 768 },
  { label: 'mobile', width: 390, height: 844 },
] as const;

type QueueMode = 'empty' | 'candidate';

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

function dashboardOverviewPayload(mode: QueueMode) {
  return {
    status: 'ready',
    asOf: '2026-07-07T09:30:00Z',
    marketPulse: {
      sp500: { label: 'S&P 500', value: '5,430', change: '+0.3%', status: 'ready' },
      nasdaq: { label: 'Nasdaq', value: '19,880', change: '+0.6%', status: 'ready' },
      russell2000: { label: 'Russell 2000', value: '2,240', change: '+0.1%', status: 'ready' },
      vix: { label: 'VIX', value: '13.8', change: '-0.4', status: 'ready' },
      tenYearYield: { label: '10Y', value: '4.12%', change: '-0.02', status: 'ready' },
      dollarIndex: { label: 'DXY', value: '103.6', change: '-0.2', status: 'ready' },
      marketBreadth: { summary: 'Participation is broadening across returned market groups.', status: 'ready' },
      liquidityState: 'stable',
    },
    marketBrief: {
      headline: 'Breadth leads the morning research map',
      summary: 'Participation improved while volatility cooled, so the first check is whether follow-through remains broad.',
      status: 'ready',
    },
    moneyFlow: {
      topInflows: ['Semiconductors', 'Software'],
      topOutflows: ['Defensives'],
      styleBias: 'Growth leadership broadening',
      offensiveDefensiveBias: 'Offensive groups leading',
      sourceStatus: 'ready',
      status: 'ready',
    },
    liquidityRisk: {
      summary: 'Liquidity pressure remains contained',
      volatilityTone: 'calm',
      fundingStress: 'low',
      dollarRatePressure: 'easing',
      status: 'ready',
    },
    sectorThemeRotation: {
      leadingThemes: ['AI infrastructure', 'Cloud software'],
      laggingThemes: ['Utilities'],
      diffusion: 'broadening',
      summary: 'Theme participation is expanding beyond the first leaders.',
      status: 'ready',
    },
    researchQueue: {
      status: 'ready',
      items: mode === 'candidate'
        ? [
            {
              title: 'Review semiconductor breadth follow-through',
              summary: 'Returned market evidence shows broader participation; inspect whether the move persists across the next research check.',
              action: 'Open Research Radar to compare breadth evidence',
              priority: 'High',
            },
          ]
        : [],
    },
    dataQuality: {
      state: 'ready',
      label: 'Research-ready evidence',
      summary: 'Returned market facts are complete enough for observation and freshness review.',
      sections: {
        marketPulse: 'ready',
        queue: 'ready',
        marketBrief: 'ready',
      },
    },
    productReadModel: {
      contractVersion: 'product_read_model_v1',
      surface: 'Dashboard',
      state: 'available',
      ready: true,
      blockingChildren: [],
      freshness: { state: 'available', asOf: '2026-07-07T09:30:00Z' },
      provenance: {
        sourceClass: 'dashboard_read_models',
        asOf: '2026-07-07T09:30:00Z',
        freshness: 'available',
        quality: 'available',
      },
    },
    noAdviceDisclosure: 'Research observation only.',
  };
}

async function installT193MemberHomeFixture(page: Page, mode: QueueMode, requests: string[]) {
  await page.route('**/api/v1/auth/status**', async (route) => {
    requests.push(`${route.request().method()} ${new URL(route.request().url()).pathname}`);
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
    requests.push(`${route.request().method()} ${new URL(route.request().url()).pathname}`);
    await fulfillJson(route, signedInUser);
  });

  await page.route('**/api/v1/history?**', async (route) => {
    requests.push(`${route.request().method()} ${new URL(route.request().url()).pathname}`);
    await fulfillJson(route, { total: 0, page: 1, limit: 20, items: [] });
  });

  await page.route('**/api/v1/analysis/tasks?**', async (route) => {
    requests.push(`${route.request().method()} ${new URL(route.request().url()).pathname}`);
    await fulfillJson(route, { tasks: [], total: 0 });
  });

  await page.route('**/api/v1/dashboard/market-intelligence-overview**', async (route) => {
    requests.push(`${route.request().method()} ${new URL(route.request().url()).pathname}`);
    await fulfillJson(route, dashboardOverviewPayload(mode));
  });

  await page.route('**/api/v1/market/data-readiness**', async (route) => {
    requests.push(`${route.request().method()} ${new URL(route.request().url()).pathname}`);
    await fulfillJson(route, {
      readiness_status: 'ready',
      diagnostic_only: true,
      provider_runtime_called: false,
      network_calls_enabled: false,
      mutation_enabled: false,
      representative_symbols: ['SPY', 'QQQ'],
      checks: [],
      consumer_evidence_readiness_matrix: {
        contract_version: 'consumer_evidence_readiness_matrix_v1',
        diagnostic_only: true,
        items: [],
      },
      cross_asset_driver_readiness: {
        contract_version: 'cross_asset_driver_readiness_v1',
        consumer_safe: true,
        diagnostic_only: true,
        network_calls_enabled: false,
        external_provider_calls: false,
        mutation_enabled: false,
        consumer_summary: 'Cross-asset drivers are ready for route history qualification.',
        summary: {},
        drivers: [],
      },
    });
  });

  await page.route('**/api/v1/market/professional-data-capabilities**', async (route) => {
    requests.push(`${route.request().method()} ${new URL(route.request().url()).pathname}`);
    await fulfillJson(route, {
      consumer_safe: true,
      diagnostic_only: true,
      summary: {
        total_capabilities: 0,
        live_count: 0,
        degraded_count: 0,
        entitlement_required_count: 0,
        configured_missing_count: 0,
        not_implemented_count: 0,
      },
      capabilities: [],
    });
  });

  await page.route('**/api/v1/market/regime-read-model**', async (route) => {
    requests.push(`${route.request().method()} ${new URL(route.request().url()).pathname}`);
    await fulfillJson(route, {
      consumer_safe: true,
      no_advice: true,
      contract_version: 'market_regime_read_model_v1',
      source_evidence_contract_version: 'market_regime_source_evidence_v1',
      status: 'ready',
      market: 'US',
      symbols: ['SPY', 'QQQ'],
      benchmark_symbol: 'SPY',
      growth_proxy_symbol: 'QQQ',
      regime: { label: 'balanced', status: 'ready' },
      product_summary: 'Market regime evidence is available for route history qualification.',
      evidence_cards: [],
      symbol_context: [],
      data_quality: {
        adjusted_coverage_state: 'available',
        ohlcv_coverage: { state: 'available', required_bars: 60, available_symbols: ['SPY', 'QQQ'], missing_symbols: [] },
        quote_snapshot_coverage: { state: 'available', availability_state: 'available', freshness_state: 'available', available_symbols: ['SPY', 'QQQ'], missing_symbols: [], stale_symbols: [] },
        missing_data_families: [],
        blocked_product_surfaces: [],
        next_operator_action: 'Continue route qualification.',
        fail_closed_reasons: [],
      },
      readiness: {
        label: 'product_ready',
        status: 'ready',
        missing_data_families: [],
        blocked_product_surfaces: [],
        next_operator_action: 'Continue route qualification.',
      },
      surface_hints: [],
      missing_data_families: [],
      blocked_product_surfaces: [],
      next_operator_action: 'Continue route qualification.',
      network_calls_enabled: false,
    });
  });
}

async function expectNoHorizontalOverflow(page: Page) {
  await expect.poll(async () => page.evaluate(() => (
    Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) <= window.innerWidth + 1
  ))).toBe(true);
}

async function expectMemberSequence(page: Page) {
  const sequence = [
    page.getByTestId('member-home-morning-decision-note'),
    page.getByTestId('member-home-research-queue'),
    page.getByTestId('member-home-watch-changes'),
    page.getByTestId('member-home-index-path'),
    page.getByTestId('member-home-data-ledger'),
  ];

  for (const locator of sequence) {
    await expect(locator).toBeVisible({ timeout: 15_000 });
  }

  for (let index = 0; index < sequence.length - 1; index += 1) {
    const precedes = await sequence[index].evaluate((left, right) => (
      Boolean(left.compareDocumentPosition(right as Node) & Node.DOCUMENT_POSITION_FOLLOWING)
    ), await sequence[index + 1].elementHandle());
    expect(precedes).toBe(true);
  }
}

async function expectKeyboardReachable(page: Page, testId: string) {
  await page.keyboard.press('Home');
  for (let index = 0; index < 80; index += 1) {
    await page.keyboard.press('Tab');
    const reached = await page.evaluate((targetTestId) => {
      const active = document.activeElement as HTMLElement | null;
      return active?.dataset?.testid === targetTestId || Boolean(active?.closest(`[data-testid="${targetTestId}"]`));
    }, testId);
    if (reached) {
      return;
    }
  }
  throw new Error(`Keyboard focus did not reach ${testId}`);
}

async function openMemberHome(page: Page) {
  await page.goto('/zh');
  await page.waitForLoadState('domcontentloaded');
  await expect(page).toHaveURL(/\/zh$/);
  await expect(page.getByTestId('home-bento-dashboard')).toHaveAttribute('data-home-surface-role', 'member');
  await expect(page.getByTestId('home-bento-dashboard')).toHaveAttribute('data-route-identity', 'member-home');
  await expect(page).toHaveTitle(/WolfyStock 首页研究控制台/);
  await expect(page.getByTestId('member-home-market-brief')).toBeVisible({ timeout: 15_000 });
}

test.describe('T193 authenticated member Home composition qualification', () => {
  for (const viewport of viewports) {
    test(`qualifies empty member research sequence at ${viewport.label}`, async ({ page }) => {
      const requests: string[] = [];
      const passiveRequests: string[] = [];
      page.on('request', (request) => {
        const url = new URL(request.url());
        if (url.pathname.startsWith('/api/v1/') && !['GET', 'HEAD', 'OPTIONS'].includes(request.method())) {
          passiveRequests.push(`${request.method()} ${url.pathname}`);
        }
      });

      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await installT193MemberHomeFixture(page, 'empty', requests);
      await openMemberHome(page);

      await expectMemberSequence(page);
      await expect(page.getByTestId('member-home-morning-decision-note')).toContainText('Breadth leads the morning research map');
      await expect(page.getByTestId('member-home-morning-decision-note')).toContainText('first check');
      await expect(page.getByTestId('member-home-research-queue-empty')).toContainText('当前没有真实研究候选');
      await expect(page.getByTestId('member-home-research-queue-empty')).toContainText('研究队列已返回但没有候选');
      await expect(page.getByTestId('member-home-research-queue')).not.toContainText(/AAPL|NVDA|TSLA|ORCL|TEM|Score|分数|评分/);
      await expect(page.getByTestId('member-home-market-brief')).not.toContainText(/Limited Private Beta|Beta 反馈|沿着一条研究旅程|功能目录/);
      await expect(page.getByTestId('member-home-beta-entry')).toHaveCount(0);
      await expectNoHorizontalOverflow(page);
      await expectKeyboardReachable(page, 'member-home-research-queue-action');
      await expectKeyboardReachable(page, 'member-home-market-action-market-overview');
      expect(passiveRequests).toEqual([]);

      await page.reload();
      await page.waitForLoadState('domcontentloaded');
      await expectMemberSequence(page);
      await expect(page.getByTestId('home-bento-dashboard')).toHaveAttribute('data-home-surface-role', 'member');

      await page.getByTestId('member-home-market-action-market-overview').click();
      await expect(page).toHaveURL(/\/zh\/market-overview$/);
      await page.goBack();
      await expect(page).toHaveURL(/\/zh$/);
      await expectMemberSequence(page);
      await page.goForward();
      await expect(page).toHaveURL(/\/zh\/market-overview$/);

      expect(requests.filter((entry) => entry === 'GET /api/v1/dashboard/market-intelligence-overview').length).toBeGreaterThan(0);
    });
  }

  for (const viewport of viewports) {
    test(`qualifies candidate member research sequence at ${viewport.label}`, async ({ page }) => {
      const requests: string[] = [];
      const passiveRequests: string[] = [];
      page.on('request', (request) => {
        const url = new URL(request.url());
        if (url.pathname.startsWith('/api/v1/') && !['GET', 'HEAD', 'OPTIONS'].includes(request.method())) {
          passiveRequests.push(`${request.method()} ${url.pathname}`);
        }
      });

      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await installT193MemberHomeFixture(page, 'candidate', requests);
      await openMemberHome(page);

      await expectMemberSequence(page);
      await expect(page.getByTestId('member-home-research-queue-empty')).toHaveCount(0);
      await expect(page.getByTestId('member-home-research-queue-item-0')).toContainText('Review semiconductor breadth follow-through');
      await expect(page.getByTestId('member-home-research-queue-item-0')).toContainText('Open Research Radar to compare breadth evidence');
      await expect(page.getByTestId('member-home-research-queue-item-0')).not.toContainText(/AAPL|NVDA|TSLA|ORCL|TEM|Score|分数|评分/);
      await expect(page.getByTestId('member-home-market-brief')).not.toContainText(/Limited Private Beta|Beta 反馈|沿着一条研究旅程|功能目录/);
      await expectNoHorizontalOverflow(page);
      await expectKeyboardReachable(page, 'member-home-research-queue-action');
      expect(passiveRequests).toEqual([]);
      expect(requests.filter((entry) => entry === 'GET /api/v1/dashboard/market-intelligence-overview').length).toBeGreaterThan(0);
    });
  }
});
