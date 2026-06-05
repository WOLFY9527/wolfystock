import type { Page, Route } from '@playwright/test';

const googleFontStylesheetPattern = 'https://fonts.googleapis.com/css2?*';

export async function installExternalStylesheetStubs(page: Page) {
  const handler = async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'text/css; charset=utf-8',
      body: '/* E2E font stylesheet stub: keep tests self-contained and offline-safe. */',
    });
  };
  await page.context().route(googleFontStylesheetPattern, handler);
  return async () => {
    await page.context().unroute(googleFontStylesheetPattern, handler);
  };
}
