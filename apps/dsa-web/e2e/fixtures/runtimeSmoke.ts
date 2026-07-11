import { expect, type Page, type Request } from '@playwright/test';

const forbiddenLogPattern =
  /(Bearer\s+[A-Za-z0-9._~+/=-]+|sk-[A-Za-z0-9_-]{12,}|ghp_[A-Za-z0-9_]{12,}|xox[baprs]-[A-Za-z0-9-]{12,}|(?:password|token|secret|api[_-]?key|authorization|cookie|session[_-]?id)\s*[:=]\s*[^\s]+)/i;

export type RuntimeSmokeCapture = {
  consoleErrors: string[];
  failedRequests: string[];
  apiRequests: string[];
  expectNoSensitiveLogLeaks: () => void;
};

export function installRuntimeSmokeCapture(page: Page): RuntimeSmokeCapture {
  const consoleErrors: string[] = [];
  const failedRequests: string[] = [];
  const apiRequests: string[] = [];

  page.on('console', (message) => {
    if (message.type() !== 'error') {
      return;
    }
    const text = message.text();
    if (text.includes('favicon.ico')) {
      return;
    }
    consoleErrors.push(text);
  });

  page.on('pageerror', (error) => {
    consoleErrors.push(error.message);
  });

  page.on('request', (request: Request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith('/api/')) {
      apiRequests.push(`${request.method()} ${url.pathname}`);
    }
  });

  page.on('requestfailed', (request: Request) => {
    const url = new URL(request.url());
    const failure = request.failure()?.errorText ?? 'unknown';
    failedRequests.push(`${request.method()} ${url.pathname}: ${failure}`);
  });

  page.on('response', (response) => {
    if (response.status() < 400) {
      return;
    }
    const request = response.request();
    const url = new URL(response.url());
    failedRequests.push(`${request.method()} ${url.pathname}: HTTP ${response.status()}`);
  });

  return {
    consoleErrors,
    failedRequests,
    apiRequests,
    expectNoSensitiveLogLeaks: () => {
      expect([...consoleErrors, ...failedRequests, ...apiRequests].join('\n')).not.toMatch(forbiddenLogPattern);
    },
  };
}

export async function expectRuntimeBaseUrl(page: Page, expectedBaseUrl: string) {
  const resolvedBaseUrl = new URL(expectedBaseUrl);
  await expect.poll(async () => page.evaluate(() => window.location.origin)).toBe(resolvedBaseUrl.origin);
}

export async function expectSmokeArtifactPath(testInfoOutputPath: string) {
  const normalizedPath = testInfoOutputPath.replaceAll('\\', '/');
  expect(normalizedPath).toContain('/frontend-smoke/');
  expect(normalizedPath).toContain('/test-results/');
}

export function forbiddenLogPatternForRuntimeSmoke() {
  return forbiddenLogPattern;
}
