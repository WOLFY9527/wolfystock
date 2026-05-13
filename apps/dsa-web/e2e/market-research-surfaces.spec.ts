import type { Page, Route } from '@playwright/test';
import { expect, test } from './fixtures/appSmoke';

const routes = [
  {
    path: '/zh/market-overview',
    root: 'market-overview-shell',
    first: ['market-decision-strip', 'market-overview-summary-band'],
    collapsedDisclosures: [],
  },
  {
    path: '/zh/watchlist',
    root: 'watchlist-page',
    first: ['watchlist-candidate-list', 'watchlist-row-NVDA'],
    collapsedDisclosures: [],
  },
  {
    path: '/zh/market/rotation-radar',
    root: 'market-rotation-radar-page',
    first: ['rotation-radar-summary-band', 'rotation-radar-leader-list'],
    collapsedDisclosures: [
      { testId: 'rotation-theme-proxy-details-ai_applications', hiddenTestId: 'rotation-proxy-row-QQQ' },
      { testId: 'rotation-radar-mechanics-details', hiddenText: '当前为静态主题库，本地行情覆盖后可计算轮动强度。' },
    ],
  },
];

const viewports = [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
];

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

async function installWatchlistRows(page: Page) {
  await page.route('**/api/v1/watchlist/items', async (route) => {
    await fulfillJson(route, {
      items: [
        {
          id: 1,
          symbol: 'NVDA',
          market: 'us',
          name: 'NVIDIA',
          source: 'scanner',
          scannerRunId: 11,
          scannerRank: 1,
          scannerScore: 96,
          scoreStatus: 'fresh',
          lastScoredAt: '2026-05-02T09:00:00Z',
          intelligence: {
            scanner: {
              lastScore: 96,
              lastRank: 1,
              status: 'selected',
              themeLabel: 'AI Semiconductors',
              profile: 'us_preopen_v1',
              lastScannedAt: '2026-05-02T09:00:00Z',
            },
            strategySimulation: {
              status: 'ready',
              avgForwardReturnPct: 2.1,
              hitRate: 0.58,
            },
            backtest: {
              lastResultId: 34,
              totalReturnPct: 12.4,
              maxDrawdownPct: -4.2,
              sharpe: 1.2,
              tradeCount: 4,
              testedAt: '2026-05-02T09:10:00Z',
            },
          },
          themeId: 'ai_semis',
          universeType: 'theme',
          createdAt: '2026-05-02T08:50:00Z',
          updatedAt: '2026-05-02T09:10:00Z',
        },
      ],
    });
  });
}

test.describe('market research surfaces IA', () => {
  for (const viewport of viewports) {
    for (const route of routes) {
      test(`${route.path} prioritizes research flow at ${viewport.width}x${viewport.height}`, async ({ page }) => {
        await page.setViewportSize(viewport);
        await installWatchlistRows(page);
        await signIn(page, route.path);

        await expect(page.getByTestId(route.root)).toBeVisible({ timeout: 15_000 });
        if (route.root === 'market-rotation-radar-page') {
          expect((await page.getByTestId(route.root).getAttribute('class')) || '').not.toContain('bg-[#030303]');
          await expect(page.getByTestId('rotation-theme-detail-panel')).toBeVisible();
        }
        for (const testId of route.first) {
          await expect(page.getByTestId(testId)).toBeVisible();
        }
        for (const disclosure of route.collapsedDisclosures) {
          const disclosureRoot = page.getByTestId(disclosure.testId);
          await expect(disclosureRoot).toBeAttached();
          if ('hiddenTestId' in disclosure) {
            await expect(disclosureRoot.getByTestId(disclosure.hiddenTestId)).toBeHidden();
          }
          if ('hiddenText' in disclosure) {
            await expect(disclosureRoot.getByText(disclosure.hiddenText)).toBeHidden();
          }
        }

        await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
        await expect(page.getByText(/买入按钮|立即交易|下单|提交订单|best contract|guaranteed/i)).toHaveCount(0);
      });
    }
  }
});
