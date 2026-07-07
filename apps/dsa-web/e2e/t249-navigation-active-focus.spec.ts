import type { Page, Route } from '@playwright/test';
import { expect, expectNoHorizontalOverflow, installAdminAuthHarness, test } from './fixtures/adminAuth';

const timestamp = '2026-07-07T10:30:00+08:00';

async function fulfillJson(route: Route, payload: unknown) {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

function userActivityPayload() {
  return {
    items: [
      {
        id: 'activity-t249',
        timestamp,
        actor: { type: 'admin', user_id: 'admin-1', label: 'Admin', role: 'admin' },
        target_user: { id: 'user-123', label: 'Alice' },
        family: 'auth',
        action: 'session_review',
        entity: { type: 'session', id_hash: 'session-hash', label: 'Session review' },
        status: 'success',
        outcome: 'ok',
        request_id_hash: 'request-hash',
        session_id_hash: 'session-hash',
        source: { kind: 'admin_audit', table: 'admin_activity', confidence: 'confirmed' },
        redacted_metadata: { read_only: true, raw_payload_omitted: true },
        log_links: [],
      },
    ],
    total: 1,
    limit: 50,
    offset: 0,
    has_more: false,
    window: { from: timestamp, to: timestamp, max_days: 30 },
    limitations: ['mocked_browser_harness_no_raw_session_values'],
  };
}

async function installT249AdminHarness(page: Page) {
  await installAdminAuthHarness(page);
  await page.route('**/api/v1/admin/users/user-123/activity?**', (route) => fulfillJson(route, userActivityPayload()));
}

async function getPrimaryNav(page: Page, isMobile: boolean, openMenuLabel: RegExp) {
  if (isMobile) {
    await page.getByRole('button', { name: openMenuLabel }).click();
  }
  const nav = page.getByTestId('shell-admin-primary-nav');
  await expect(nav).toBeVisible();
  return nav;
}

async function focusNavItemByKeyboard(page: Page, label: string) {
  for (let index = 0; index < 32; index += 1) {
    const activeLabel = await page.evaluate(() => {
      const active = document.activeElement;
      if (!(active instanceof HTMLElement)) return '';
      return active.getAttribute('aria-label') || active.textContent?.replace(/\s+/g, ' ').trim() || '';
    });
    if (activeLabel === label) {
      return;
    }
    await page.keyboard.press('Tab');
  }
  throw new Error(`Keyboard focus did not reach ${label}`);
}

async function collectFocusMetrics(page: Page, label: string, useKeyboardFocus: boolean) {
  if (useKeyboardFocus) {
    await focusNavItemByKeyboard(page, label);
  }

  return page.evaluate(async (targetLabel) => {
    const link = Array.from(document.querySelectorAll<HTMLAnchorElement>('[data-testid="shell-admin-primary-nav"] a'))
      .find((node) => node.getAttribute('aria-label') === targetLabel || node.textContent?.trim() === targetLabel);
    if (!link) {
      return { found: false };
    }

    const nav = link.closest<HTMLElement>('[data-testid="shell-admin-primary-nav"]');
    if (!nav) {
      return { found: false };
    }

    nav.scrollLeft = 0;
    if (document.activeElement !== link) {
      link.focus({ preventScroll: false });
    }
    await new Promise((resolve) => requestAnimationFrame(resolve));

    const linkRect = link.getBoundingClientRect();
    const navRect = nav.getBoundingClientRect();
    const style = window.getComputedStyle(link);

    return {
      found: true,
      focused: document.activeElement === link,
      focusVisible: link.matches(':focus-visible') || style.outlineStyle !== 'none' || style.boxShadow !== 'none',
      linkLeft: Math.round(linkRect.left),
      linkRight: Math.round(linkRect.right),
      navLeft: Math.round(navRect.left),
      navRight: Math.round(navRect.right),
      documentScrollLeft: document.documentElement.scrollLeft,
      documentOverflow: Math.max(0, Math.round(document.documentElement.scrollWidth - document.documentElement.clientWidth)),
    };
  }, label);
}

test.describe('T249 navigation active state and focus closure', () => {
  const cases = [
    {
      name: 'zh desktop system settings',
      viewport: { width: 1280, height: 900 },
      path: '/zh/settings/system',
      readyTestId: 'system-settings-page',
      currentLabel: '运维总览/系统设置',
      focusLabel: '通知通道',
      openMenuLabel: /打开导航菜单/,
      isMobile: false,
    },
    {
      name: 'en desktop user activity',
      viewport: { width: 1280, height: 900 },
      path: '/en/admin/users/user-123/activity',
      readyTestId: 'admin-users-page-shell',
      currentLabel: 'User Governance',
      focusLabel: 'Notification Channels',
      openMenuLabel: /Open menu|Open navigation/i,
      isMobile: false,
    },
    {
      name: 'zh mobile system settings',
      viewport: { width: 390, height: 844 },
      path: '/zh/settings/system',
      readyTestId: 'system-settings-page',
      currentLabel: '运维总览/系统设置',
      focusLabel: '通知通道',
      openMenuLabel: /打开导航菜单/,
      isMobile: true,
    },
    {
      name: 'en mobile user activity',
      viewport: { width: 390, height: 844 },
      path: '/en/admin/users/user-123/activity',
      readyTestId: 'admin-users-page-shell',
      currentLabel: 'User Governance',
      focusLabel: 'Notification Channels',
      openMenuLabel: /Open menu|Open navigation/i,
      isMobile: true,
    },
  ] as const;

  for (const scenario of cases) {
    test(`${scenario.name} exposes one current route and reveals focused nav`, async ({ page }) => {
      await page.setViewportSize(scenario.viewport);
      await installT249AdminHarness(page);
      await page.goto(scenario.path);
      await page.waitForLoadState('domcontentloaded');
      await expect(page.getByTestId(scenario.readyTestId)).toBeVisible({ timeout: 15_000 });

      const adminNav = await getPrimaryNav(page, scenario.isMobile, scenario.openMenuLabel);
      const currentLink = adminNav.getByRole('link', { name: scenario.currentLabel });

      await expect(currentLink).toHaveAttribute('aria-current', 'page');
      await expect(currentLink).toHaveClass(/is-active/);
      await expect(adminNav.locator('[aria-current="page"]')).toHaveCount(1);
      await expect(page.getByTestId('shell-consumer-primary-nav')).toHaveCount(0);

      const focusMetrics = await collectFocusMetrics(page, scenario.focusLabel, scenario.isMobile);
      expect(focusMetrics).toMatchObject({
        found: true,
        focused: true,
        focusVisible: true,
        documentScrollLeft: 0,
        documentOverflow: 0,
      });
      expect(focusMetrics.linkLeft).toBeGreaterThanOrEqual(focusMetrics.navLeft - 1);
      expect(focusMetrics.linkRight).toBeLessThanOrEqual(focusMetrics.navRight + 1);
      await expectNoHorizontalOverflow(page);
    });
  }
});
