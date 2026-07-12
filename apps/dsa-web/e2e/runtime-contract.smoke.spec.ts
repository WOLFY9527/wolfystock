import { expect, test } from '@playwright/test';
import {
  expectRuntimeBaseUrl,
  expectSmokeArtifactPath,
  forbiddenLogPatternForRuntimeSmoke,
  installRuntimeSmokeCapture,
} from './fixtures/runtimeSmoke';

const configuredBaseUrl = process.env.DSA_WEB_PLAYWRIGHT_BASE_URL;

test.describe('frontend smoke runtime contract', () => {
  test('loads the app shell through the configured base URL', async ({ page, baseURL }, testInfo) => {
    const capture = installRuntimeSmokeCapture(page);
    const expectedBaseUrl = configuredBaseUrl || baseURL;
    expect(expectedBaseUrl).toBeTruthy();

    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    await expectRuntimeBaseUrl(page, expectedBaseUrl!);
    await expect(page.locator('#root')).not.toBeEmpty({ timeout: 15_000 });
    await expect(page.locator('body')).toContainText(/WolfyStock|股票研究工作区|Stock Research Workspace|Guest Preview Mode/, {
      timeout: 15_000,
    });
    if (process.env.DSA_WEB_PLAYWRIGHT_EXTERNAL_SERVER === '1') {
      await expectSmokeArtifactPath(testInfo.outputPath('runtime-contract-artifact.txt'));
    }

    expect(capture.apiRequests.some((entry) => entry.endsWith('/api/v1/auth/status'))).toBe(true);
    capture.expectNoSensitiveLogLeaks();
  });

  test('captures failed requests and console errors without exposing secrets', async ({ page }) => {
    const capture = installRuntimeSmokeCapture(page);
    await page.route('**/__smoke_failed_request__.json', async (route) => {
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'synthetic_smoke_failure' }),
      });
    });

    await page.goto('/');
    await page.evaluate(() => {
      console.error('smoke harness synthetic console error with redacted credential sentinel');
      void fetch('/__smoke_failed_request__.json').catch(() => undefined);
    });
    await expect.poll(() => capture.failedRequests.some((entry) => entry.includes('/__smoke_failed_request__.json'))).toBe(true);

    expect(capture.consoleErrors).toContain('smoke harness synthetic console error with redacted credential sentinel');
    expect(capture.apiRequests.some((entry) => entry.endsWith('/api/v1/auth/status'))).toBe(true);
    expect([...capture.consoleErrors, ...capture.failedRequests].join('\n')).not.toMatch(forbiddenLogPatternForRuntimeSmoke());
    await page.unroute('**/__smoke_failed_request__.json');
  });
});
