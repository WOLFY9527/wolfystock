import { expect, type Page } from '@playwright/test';
import { installAdminAuthHarness, test as adminTest } from './fixtures/adminAuth';
import { test as appTest } from './fixtures/appSmoke';
import { installPortfolioSmokeHarness } from './fixtures/portfolioSmoke';
import { installProductAuthHarness, test as productTest } from './fixtures/productAuth';
import {
  assertUxDensityHardSafety,
  collectUxDensityMetric,
  createConsolePageErrorCollector,
  installUxDensityAuthenticatedSession,
  installUxDensityAdminMocks,
  installUxDensityPublicMocks,
  uxDensityRoutes,
  uxDensityViewports,
  waitForUxDensityRoute,
  writeUxDensityReport,
  type UxDensityMetric,
  type UxDensityRoute,
  type UxDensityViewport,
} from './fixtures/uxDensity';

const metrics: UxDensityMetric[] = [];

async function recordAuditMetric(
  page: Page,
  route: UxDensityRoute,
  viewport: UxDensityViewport,
  errors: string[],
  errorStart: number,
) {
  await waitForUxDensityRoute(page);
  const metric = await collectUxDensityMetric(page, route, viewport, errors.slice(errorStart));
  await assertUxDensityHardSafety(page, metric, route);
  metrics.push(metric);
  writeUxDensityReport(metrics);
}

const publicRoutes = uxDensityRoutes.filter((route) => route.harness === 'public');
const productRoutes = uxDensityRoutes.filter((route) => route.harness === 'product');
const portfolioRoutes = uxDensityRoutes.filter((route) => route.harness === 'portfolio');
const adminRoutes = uxDensityRoutes.filter((route) => route.harness === 'admin');

appTest.describe('UX density hard safety guard', () => {
  const guardViewport: UxDensityViewport = { width: 390, height: 844 };
  const consumerGuardRoute: UxDensityRoute = { path: '/zh/market/liquidity-monitor', label: 'Liquidity Monitor', harness: 'public' };
  const adminGuardRoute: UxDensityRoute = { path: '/zh/admin/market-providers', label: 'Admin Market Providers', harness: 'admin' };

  appTest('fails consumer first viewport strict backend diagnostic vocabulary', async ({ page }) => {
    await page.setViewportSize(guardViewport);
    await page.setContent('<main><h1>流动性监测</h1><p>sourceAuthorityAllowed reasonCode fallback_static</p></main>');

    const metric = await collectUxDensityMetric(page, consumerGuardRoute, guardViewport, []);
    let error: unknown;
    try {
      await assertUxDensityHardSafety(page, metric, consumerGuardRoute);
    } catch (caught) {
      error = caught;
    }

    expect(String(error)).toContain('/zh/market/liquidity-monitor');
    expect(String(error)).toContain('strict backend diagnostic vocabulary');
    expect(String(error)).toContain('sourceAuthorityAllowed');
    expect(String(error)).toContain('reasonCode');
    expect(String(error)).toContain('fallback_static');
  });

  appTest('allows admin diagnostic wording while keeping route-aware context', async ({ page }) => {
    await page.setViewportSize(guardViewport);
    await page.setContent('<main><h1>Admin Market Providers</h1><p>provider reason fallback sourceAuthorityAllowed</p></main>');

    const metric = await collectUxDensityMetric(page, adminGuardRoute, guardViewport, []);

    await assertUxDensityHardSafety(page, metric, adminGuardRoute);
  });

  appTest('fails admin first viewport raw unsafe payload leakage', async ({ page }) => {
    await page.setViewportSize(guardViewport);
    await page.setContent('<main><h1>Admin Market Providers</h1><p>raw JSON</p></main>');

    const metric = await collectUxDensityMetric(page, adminGuardRoute, guardViewport, []);
    let error: unknown;
    try {
      await assertUxDensityHardSafety(page, metric, adminGuardRoute);
    } catch (caught) {
      error = caught;
    }

    expect(String(error)).toContain('/zh/admin/market-providers');
    expect(String(error)).toContain('raw unsafe payload vocabulary');
    expect(String(error)).toContain('raw JSON');
  });
});

appTest.describe('UX density audit - public/product shell routes', () => {
  for (const route of publicRoutes) {
    appTest(`${route.path} reports first-viewport density without hard safety regressions`, async ({ page }) => {
      const errors = createConsolePageErrorCollector(page);
      await installUxDensityAuthenticatedSession(page);
      await installUxDensityPublicMocks(page);

      for (const viewport of uxDensityViewports) {
        await page.setViewportSize(viewport);
        const errorStart = errors.length;
        await page.goto(route.path);
        await recordAuditMetric(page, route, viewport, errors, errorStart);
      }
    });
  }
});

productTest.describe('UX density audit - options route', () => {
  for (const route of productRoutes) {
    productTest(`${route.path} reports first-viewport density without hard safety regressions`, async ({ page }) => {
      const errors = createConsolePageErrorCollector(page);
      await installProductAuthHarness(page);

      for (const viewport of uxDensityViewports) {
        await page.setViewportSize(viewport);
        const errorStart = errors.length;
        await page.goto(route.path);
        await recordAuditMetric(page, route, viewport, errors, errorStart);
      }

      await page.unrouteAll({ behavior: 'ignoreErrors' });
    });
  }
});

productTest.describe('UX density audit - portfolio route', () => {
  for (const route of portfolioRoutes) {
    productTest(`${route.path} reports first-viewport density without hard safety regressions`, async ({ page }) => {
      const errors = createConsolePageErrorCollector(page);
      await installPortfolioSmokeHarness(page);

      for (const viewport of uxDensityViewports) {
        await page.setViewportSize(viewport);
        const errorStart = errors.length;
        await page.goto(route.path);
        await recordAuditMetric(page, route, viewport, errors, errorStart);
      }

      await page.unrouteAll({ behavior: 'ignoreErrors' });
    });
  }
});

adminTest.describe('UX density audit - admin routes', () => {
  for (const route of adminRoutes) {
    adminTest(`${route.path} reports first-viewport density without hard safety regressions`, async ({ page }) => {
      const errors = createConsolePageErrorCollector(page);
      await installAdminAuthHarness(page, {
        capabilities: ['cost:observability:read', 'ops:logs:read', 'ops:providers:read'],
      });
      await installUxDensityAdminMocks(page);

      for (const viewport of uxDensityViewports) {
        await page.setViewportSize(viewport);
        const errorStart = errors.length;
        await page.goto(route.path);
        await recordAuditMetric(page, route, viewport, errors, errorStart);
      }

      await page.unrouteAll({ behavior: 'ignoreErrors' });
    });
  }
});
