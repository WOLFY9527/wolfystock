import type { Page } from '@playwright/test';
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
  await assertUxDensityHardSafety(page, metric);
  metrics.push(metric);
  writeUxDensityReport(metrics);
}

const publicRoutes = uxDensityRoutes.filter((route) => route.harness === 'public');
const productRoutes = uxDensityRoutes.filter((route) => route.harness === 'product');
const portfolioRoutes = uxDensityRoutes.filter((route) => route.harness === 'portfolio');
const adminRoutes = uxDensityRoutes.filter((route) => route.harness === 'admin');

appTest.describe('UX density audit - public/product shell routes', () => {
  for (const route of publicRoutes) {
    appTest(`${route.path} reports first-viewport density without hard safety regressions`, async ({ page }) => {
      const errors = createConsolePageErrorCollector(page);
      await installUxDensityAuthenticatedSession(page);

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
