import { expect, test, type Page, type Route } from '@playwright/test';

const viewports = [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
];

const forbiddenTradeActionPattern =
  /买入按钮|下单|立即交易|必买|稳赚|保证收益|guaranteed|best contract|AI recommends you buy|must buy|must sell|buy now|sell now|place order|you should buy|you should sell/i;
const rawProviderDebugPattern = /raw\s+(payload|provider)|debug\s+(payload|schema)|provider\s+payload|api[_\s-]?key|secret\s*[=:]|bearer\s+[a-z0-9._-]+/i;

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function installAiResearchHarness(page: Page) {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (method === 'GET' && path === '/api/v1/auth/status') {
      return fulfillJson(route, {
        authEnabled: true,
        loggedIn: true,
        passwordSet: true,
        passwordChangeable: true,
        setupState: 'enabled',
        currentUser: {
          id: 'user-1',
          username: 'wolfy-user',
          displayName: 'Wolfy User',
          role: 'user',
          isAdmin: false,
          isAuthenticated: true,
          transitional: false,
          authEnabled: true,
        },
      });
    }
    if (method === 'GET' && path === '/api/v1/auth/me') {
      return fulfillJson(route, {
        id: 'user-1',
        username: 'wolfy-user',
        displayName: 'Wolfy User',
        role: 'user',
        isAdmin: false,
        isAuthenticated: true,
        transitional: false,
        authEnabled: true,
      });
    }
    if (method === 'GET' && path === '/api/v1/history') {
      return fulfillJson(route, { total: 0, page: 1, limit: 20, items: [] });
    }
    if (method === 'GET' && path === '/api/v1/analysis/tasks') {
      return fulfillJson(route, { tasks: [], total: 0 });
    }
    if (method === 'GET' && path === '/api/v1/analysis/tasks/stream') {
      return route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: 'event: heartbeat\ndata: {}\n\n',
      });
    }
    if (method === 'GET' && path === '/api/v1/agent/skills') {
      return fulfillJson(route, {
        skills: [
          { id: 'bull_trend', name: '趋势观察', description: '只读趋势观察' },
          { id: 'ma_cross', name: '均线系统', description: '均线结构复核' },
          { id: 'leader_strategy', name: '龙头策略', description: '相对强度观察' },
        ],
        default_skill_id: 'bull_trend',
      });
    }
    if (method === 'GET' && path === '/api/v1/agent/models') {
      return fulfillJson(route, {
        models: [{ deployment_id: 'auto', model: 'research-auto', provider: 'Wolfy', source: 'fixture', is_primary: true }],
      });
    }
    if (method === 'GET' && path === '/api/v1/agent/provider-health') {
      return fulfillJson(route, {
        routingMode: 'AUTO',
        currentProvider: 'Wolfy',
        currentModel: 'research-auto',
        providers: [{ id: 'wolfy', label: 'Wolfy', status: 'available', model: 'research-auto', selected: true }],
      });
    }
    if (method === 'GET' && path === '/api/v1/watchlist') {
      return fulfillJson(route, { items: [] });
    }
    if (method === 'GET' && path === '/api/v1/portfolio/snapshot') {
      return fulfillJson(route, { asOf: '2026-05-09', accounts: [] });
    }
    if (method === 'GET' && path === '/api/v1/scanner/recent-watchlists') {
      return fulfillJson(route, { items: [] });
    }
    if (method === 'GET' && path === '/api/v1/backtest/runs') {
      return fulfillJson(route, { total: 0, page: 1, limit: 1, items: [] });
    }

    return fulfillJson(route, { error: `Unhandled AI research harness route: ${method} ${path}` }, 500);
  });
}

async function expectNoHorizontalOverflow(page: Page) {
  await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

async function expectCleanLaunchText(page: Page) {
  const firstViewportText = await page.locator('body').innerText();
  expect(firstViewportText).not.toMatch(forbiddenTradeActionPattern);
  expect(firstViewportText).not.toMatch(rawProviderDebugPattern);
}

test.describe('AI research entry launch surfaces', () => {
  test.beforeEach(async ({ page }) => {
    await installAiResearchHarness(page);
  });

  test('home and report drawer stay research-first across launch viewports', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error' && !message.text().includes('favicon.ico')) {
        consoleErrors.push(message.text());
      }
    });
    page.on('response', (response) => {
      if (response.status() >= 500) {
        consoleErrors.push(`${response.status()} ${response.url()}`);
      }
    });
    page.on('pageerror', (error) => consoleErrors.push(error.message));

    for (const viewport of viewports) {
      await page.setViewportSize(viewport);

      await page.goto('/zh');
      await page.waitForLoadState('domcontentloaded');
      await expect(page.getByTestId('home-bento-dashboard')).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('home-bento-research-state-row')).toBeVisible();
      await expect(page.getByTestId('home-bento-card-strategy')).toHaveAttribute('data-research-card', 'opportunity');
      await expect(page.getByTestId('home-bento-card-tech')).toHaveAttribute('data-research-card', 'risk-context');
      await expectNoHorizontalOverflow(page);
      await expectCleanLaunchText(page);

      await page.getByRole('button', { name: '完整报告' }).click();
      await expect(page.getByTestId('home-bento-full-report-drawer')).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('home-bento-report-executive-summary')).toBeVisible();
      await expect(page.getByTestId('home-bento-full-report-technical-details')).not.toHaveAttribute('open');
      await expectNoHorizontalOverflow(page);
      await expectCleanLaunchText(page);
    }

    expect(consoleErrors).toEqual([]);
  });
});
