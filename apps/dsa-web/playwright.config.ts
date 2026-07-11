import { defineConfig, devices } from '@playwright/test';

const explicitPortEnv = 'DSA_WEB_PLAYWRIGHT_PORT';
const resolvedPortEnv = 'DSA_WEB_PLAYWRIGHT_RESOLVED_PORT';
const localPreviewPort = 4173;
const ciPreviewPortBase = 42_000;
const ciPreviewPortRange = 10_000;

function parsePreviewPort(value: string | undefined, envName: string): number | undefined {
  if (!value) {
    return undefined;
  }

  const port = Number(value);
  if (!Number.isInteger(port) || port < 1 || port > 65_535) {
    throw new Error(`${envName} must be an integer TCP port from 1 to 65535. Received: ${value}`);
  }

  return port;
}

function hashPortSeed(seed: string): number {
  let hash = 2166136261;
  for (const char of seed) {
    hash ^= char.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function resolvePreviewPort(): number {
  const explicitPort = parsePreviewPort(process.env[explicitPortEnv], explicitPortEnv);
  if (explicitPort) {
    process.env[resolvedPortEnv] = String(explicitPort);
    return explicitPort;
  }

  const inheritedPort = parsePreviewPort(process.env[resolvedPortEnv], resolvedPortEnv);
  if (inheritedPort) {
    process.env[explicitPortEnv] = String(inheritedPort);
    return inheritedPort;
  }

  const generatedPort = process.env.CI
    ? ciPreviewPortBase +
      (hashPortSeed(`${process.cwd()}:${process.pid}:${Date.now()}:${Math.random()}`) % ciPreviewPortRange)
    : localPreviewPort;

  process.env[explicitPortEnv] = String(generatedPort);
  process.env[resolvedPortEnv] = String(generatedPort);
  return generatedPort;
}

const previewPort = resolvePreviewPort();
const reuseExistingServer = process.env.DSA_WEB_PLAYWRIGHT_REUSE === '1' && !process.env.CI;
const baseURL = process.env.DSA_WEB_PLAYWRIGHT_BASE_URL || `http://127.0.0.1:${previewPort}`;
const outputDir = process.env.PLAYWRIGHT_OUTPUT_DIR || 'test-results';
const usesExternalServer = process.env.DSA_WEB_PLAYWRIGHT_EXTERNAL_SERVER === '1';
const reporter = process.env.PLAYWRIGHT_HTML_REPORT
  ? ([
      ['list'],
      ['html', { outputFolder: process.env.PLAYWRIGHT_HTML_REPORT, open: 'never' }],
    ] as const)
  : 'list';

export default defineConfig({
  testDir: './e2e',
  outputDir,
  fullyParallel: false,
  retries: process.env.CI ? 2 : 0,
  reporter,
  ...(usesExternalServer ? {} : {
    webServer: {
      command: `npm run build && npm run preview -- --host 127.0.0.1 --port ${previewPort}`,
      port: previewPort,
      reuseExistingServer,
      timeout: 180_000,
    },
  }),
  use: {
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], channel: 'chromium' },
    },
    {
      name: 'chromium-mobile',
      use: { ...devices['Pixel 5'], channel: 'chromium' },
    },
  ],
});
