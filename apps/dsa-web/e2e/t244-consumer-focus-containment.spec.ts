import type { Locator, Page } from '@playwright/test';
import { expect, test } from './fixtures/appSmoke';

type FocusMeasurement = {
  label: string;
  role: string | null;
  testId: string | null;
  tagName: string;
  text: string;
  href: string | null;
  focused: {
    left: number;
    top: number;
    right: number;
    bottom: number;
    width: number;
    height: number;
  };
  clippingAncestor: {
    tagName: string;
    testId: string | null;
    className: string;
    overflowX: string;
    overflowY: string;
    left: number;
    top: number;
    right: number;
    bottom: number;
  } | null;
  clippedByAncestor: boolean;
  clippedByViewport: boolean;
  documentOverflowX: number;
  focusableReachable: boolean;
};

const MARKET_VIEWPORTS = [
  { label: 'zh-390x844', path: '/zh/market-overview', width: 390, height: 844 },
  { label: 'en-390x844', path: '/en/market-overview', width: 390, height: 844 },
  { label: 'zh-320x800', path: '/zh/market-overview', width: 320, height: 800 },
  { label: 'en-320x800', path: '/en/market-overview', width: 320, height: 800 },
  { label: 'zh-tablet-768x900', path: '/zh/market-overview', width: 768, height: 900 },
  { label: 'en-desktop-1440x1000', path: '/en/market-overview', width: 1440, height: 1000 },
] as const;

const BACKTEST_VIEWPORTS = [
  { label: 'en-320x800', path: '/en/backtest/results/34', width: 320, height: 800 },
  { label: 'zh-320x800', path: '/zh/backtest/results/34', width: 320, height: 800 },
  { label: 'en-390x844', path: '/en/backtest/results/34', width: 390, height: 844 },
  { label: 'en-desktop-1440x1000', path: '/en/backtest/results/34', width: 1440, height: 1000 },
] as const;

async function gotoSurface(page: Page, path: string, width: number, height: number) {
  await page.setViewportSize({ width, height });
  await page.goto(path);
  await page.waitForLoadState('domcontentloaded');
}

async function signIn(page: Page, redirectPath: string) {
  await page.goto(`/login?redirect=${encodeURIComponent(redirectPath)}`);
  await page.locator('#username').fill('wolfy-user');
  await page.locator('#password').fill('mock-password');
  await Promise.all([
    page.waitForResponse((response) => response.url().includes('/api/v1/auth/login') && response.status() === 200),
    page.getByRole('button', { name: /sign in|登录继续|授权进入工作台|完成设置并登录/i }).click(),
  ]);
  await page.waitForURL((url) => url.pathname === '/' || url.pathname === redirectPath);
}

async function expectNoPageOverflow(page: Page) {
  await expect
    .poll(async () => page.evaluate(() => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)))
    .toBeLessThanOrEqual(1);
}

async function scrollIntoView(locator: Locator) {
  await locator.evaluate((element) => {
    const target = element as HTMLElement;
    const html = document.documentElement;
    const previousScrollBehavior = html.style.scrollBehavior;
    html.style.scrollBehavior = 'auto';

    let ancestor = target.parentElement;
    while (ancestor && ancestor !== document.body && ancestor !== html) {
      const style = window.getComputedStyle(ancestor);
      const scrollsY = /(auto|scroll)/.test(style.overflowY) && ancestor.scrollHeight > ancestor.clientHeight;
      const scrollsX = /(auto|scroll)/.test(style.overflowX) && ancestor.scrollWidth > ancestor.clientWidth;
      if (scrollsY || scrollsX) {
        const targetRect = target.getBoundingClientRect();
        const ancestorRect = ancestor.getBoundingClientRect();
        if (scrollsY) {
          ancestor.scrollTop += targetRect.top - ancestorRect.top - (ancestor.clientHeight - targetRect.height) / 2;
        }
        if (scrollsX) {
          ancestor.scrollLeft += targetRect.left - ancestorRect.left - (ancestor.clientWidth - targetRect.width) / 2;
        }
      }
      ancestor = ancestor.parentElement;
    }

    const rect = target.getBoundingClientRect();
    window.scrollTo({
      top: Math.max(0, window.scrollY + rect.top - (window.innerHeight - rect.height) / 2),
      left: Math.max(0, window.scrollX + rect.left - (window.innerWidth - rect.width) / 2),
      behavior: 'auto',
    });
    html.style.scrollBehavior = previousScrollBehavior;
  });
  await locator.page().waitForFunction((element) => {
    const rect = (element as HTMLElement).getBoundingClientRect();
    return rect.top >= -1 && rect.bottom <= window.innerHeight + 1;
  }, await locator.elementHandle(), { timeout: 1_000 });
}

async function focusAndMeasure(locator: Locator): Promise<FocusMeasurement> {
  await scrollIntoView(locator);
  await locator.focus();
  return locator.evaluate((element) => {
    const focused = element as HTMLElement;
    const style = window.getComputedStyle(focused);
    const outlineWidth = Number.parseFloat(style.outlineWidth || '0') || 0;
    const outlineOffset = Number.parseFloat(style.outlineOffset || '0') || 0;
    const focusPad = Math.max(2, outlineWidth + Math.abs(outlineOffset));
    const rect = focused.getBoundingClientRect();
    const focusRect = {
      left: rect.left - focusPad,
      top: rect.top - focusPad,
      right: rect.right + focusPad,
      bottom: rect.bottom + focusPad,
      width: rect.width + focusPad * 2,
      height: rect.height + focusPad * 2,
    };

    let ancestor: HTMLElement | null = focused.parentElement;
    let clippingAncestor: FocusMeasurement['clippingAncestor'] = null;
    let clippedByAncestor = false;
    while (ancestor && ancestor !== document.body && ancestor !== document.documentElement) {
      const ancestorStyle = window.getComputedStyle(ancestor);
      const overflowX = ancestorStyle.overflowX;
      const overflowY = ancestorStyle.overflowY;
      if (/(hidden|clip|auto|scroll)/.test(`${overflowX} ${overflowY}`)) {
        const ancestorRect = ancestor.getBoundingClientRect();
        const clipsX = focusRect.left < ancestorRect.left - 1 || focusRect.right > ancestorRect.right + 1;
        const clipsY = focusRect.top < ancestorRect.top - 1 || focusRect.bottom > ancestorRect.bottom + 1;
        if (clipsX || clipsY) {
          clippedByAncestor = true;
          clippingAncestor = {
            tagName: ancestor.tagName.toLowerCase(),
            testId: ancestor.getAttribute('data-testid'),
            className: ancestor.className.toString(),
            overflowX,
            overflowY,
            left: ancestorRect.left,
            top: ancestorRect.top,
            right: ancestorRect.right,
            bottom: ancestorRect.bottom,
          };
          break;
        }
      }
      ancestor = ancestor.parentElement;
    }

    return {
      label: focused.getAttribute('aria-label') || focused.textContent?.trim() || focused.getAttribute('title') || '',
      role: focused.getAttribute('role'),
      testId: focused.getAttribute('data-testid'),
      tagName: focused.tagName.toLowerCase(),
      text: focused.textContent?.trim() || '',
      href: focused instanceof HTMLAnchorElement ? focused.href : null,
      focused: focusRect,
      clippingAncestor,
      clippedByAncestor,
      clippedByViewport:
        focusRect.left < -1
        || focusRect.top < -1
        || focusRect.right > window.innerWidth + 1
        || focusRect.bottom > window.innerHeight + 1,
      documentOverflowX: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
      focusableReachable: document.activeElement === focused,
    };
  });
}

async function measureLocators(locators: Locator[]): Promise<FocusMeasurement[]> {
  const measurements: FocusMeasurement[] = [];
  for (const locator of locators) {
    const count = await locator.count();
    for (let index = 0; index < count; index += 1) {
      const candidate = locator.nth(index);
      const visible = await candidate.evaluate((element) => element.getClientRects().length > 0).catch(() => false);
      if (!visible) continue;
      measurements.push(await focusAndMeasure(candidate));
    }
  }
  return measurements;
}

function clipped(measurements: FocusMeasurement[]) {
  return measurements.filter((item) => item.clippedByAncestor || item.clippedByViewport);
}

function cjkLabelLeakage(measurements: FocusMeasurement[]) {
  return measurements.filter((item) => /[\u3400-\u9FFF]/.test(`${item.label} ${item.text}`));
}

async function expectTabMovesFocus(page: Page, from: Locator, to: Locator) {
  await scrollIntoView(from);
  await from.focus();
  await page.keyboard.press('Tab');
  await expect
    .poll(async () => to.evaluate((element) => document.activeElement === element).catch(() => false))
    .toBe(true);
}

async function measureMarketOverviewFocusTargets(page: Page) {
  const shell = page.getByTestId('market-overview-shell');
  return measureLocators([
    page.getByTestId('market-decision-semantics-strip').getByRole('button'),
    page.getByTestId('market-overview-category-tabs').getByRole('button'),
    page.getByTestId('market-overview-export-summary'),
    shell.getByRole('button', { name: /^(刷新|Refresh)/ }),
  ]);
}

async function measureBacktestResultFocusTargets(page: Page) {
  return measureLocators([
    page.getByRole('navigation', { name: 'Backtest result sections' }).locator('a[href^="#backtest-report-"]'),
    page.getByTestId('backtest-report-detail-tabs').getByRole('tab'),
    page.getByTestId('backtest-report-key-metrics').getByRole('button'),
    page.getByTestId('backtest-report-trade-table').getByRole('button'),
    page.getByTestId('backtest-report-data-quality').getByRole('button'),
    page.getByTestId('backtest-report-execution-assumptions').getByRole('button'),
    page.getByTestId('backtest-report-advanced-details').getByRole('button'),
  ]);
}

test.describe('T244 consumer focus containment', () => {
  test('keeps Market Overview focus visible across narrow consumer viewports', async ({ page }) => {
    await signIn(page, MARKET_VIEWPORTS[0].path);
    for (const viewport of MARKET_VIEWPORTS) {
      await gotoSurface(page, viewport.path, viewport.width, viewport.height);
      const shell = page.getByTestId('market-overview-shell');
      await expect(shell).toBeVisible({ timeout: 15_000 });

      const measurements = await measureMarketOverviewFocusTargets(page);
      const clippedMeasurements = clipped(measurements);

      expect(
        clippedMeasurements,
        JSON.stringify({ viewport: viewport.label, clipped: clippedMeasurements }, null, 2),
      ).toEqual([]);
      expect(measurements.every((item) => item.focusableReachable)).toBe(true);
      if (viewport.path.startsWith('/en/')) {
        expect(cjkLabelLeakage(measurements)).toEqual([]);
      }
      if (viewport.label === 'zh-320x800') {
        const categoryButtons = page.getByTestId('market-overview-category-tabs').getByRole('button');
        await expectTabMovesFocus(page, categoryButtons.first(), categoryButtons.nth(1));
      }
      await expectNoPageOverflow(page);
    }
  });

  test('keeps Backtest Result Report focus visible on narrow consumer viewports', async ({ page }) => {
    await signIn(page, BACKTEST_VIEWPORTS[0].path);
    for (const viewport of BACKTEST_VIEWPORTS) {
      await gotoSurface(page, viewport.path, viewport.width, viewport.height);
      const shell = page.getByTestId('deterministic-backtest-result-page');
      await expect(shell).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('backtest-result-report')).toBeVisible();

      const measurements = await measureBacktestResultFocusTargets(page);
      const clippedMeasurements = clipped(measurements);

      expect(
        clippedMeasurements,
        JSON.stringify({ viewport: viewport.label, clipped: clippedMeasurements }, null, 2),
      ).toEqual([]);
      expect(measurements.every((item) => item.focusableReachable)).toBe(true);
      if (viewport.path.startsWith('/en/')) {
        expect(cjkLabelLeakage(measurements)).toEqual([]);
      }
      if (viewport.label === 'en-320x800') {
        const sectionLinks = page.getByRole('navigation', { name: 'Backtest result sections' }).locator('a[href^="#backtest-report-"]');
        await expectTabMovesFocus(page, sectionLinks.first(), sectionLinks.nth(1));
      }
      await expectNoPageOverflow(page);
    }
  });
});
