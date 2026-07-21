import { defineConfig, devices } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path, { dirname } from 'node:path';

const explicitPortEnv = 'DSA_WEB_PLAYWRIGHT_PORT';
const resolvedPortEnv = 'DSA_WEB_PLAYWRIGHT_RESOLVED_PORT';
const localPreviewPort = 4173;
const ciPreviewPortBase = 42_000;
const ciPreviewPortRange = 10_000;
const configRoot = dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(configRoot, '../..');
const artifactScript = path.resolve(repoRoot, 'scripts/web_build_artifact.py');

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

function resolveCandidateSha(): string {
  const configured = process.env.WOLFYSTOCK_RELEASE_CANDIDATE_SHA?.trim();
  const candidateSha = configured || execFileSync('git', ['rev-parse', 'HEAD'], { cwd: repoRoot, encoding: 'utf8' }).trim();
  if (!/^[0-9a-f]{40}$/.test(candidateSha)) {
    throw new Error('WOLFYSTOCK_RELEASE_CANDIDATE_SHA must identify the exact 40-character source candidate SHA.');
  }
  return candidateSha;
}

function previewCommand(port: number, candidateSha: string, hasPrebuiltArtifact: boolean, artifactRoot: string): string {
  const preview = `npm run preview -- --host 127.0.0.1 --port ${port} --outDir ${artifactRoot}`;
  return hasPrebuiltArtifact
    ? preview
    : `npm run build:playwright-artifact -- --expected-sha ${candidateSha} && ${preview}`;
}

const previewPort = resolvePreviewPort();
const reuseExistingServer = process.env.DSA_WEB_PLAYWRIGHT_REUSE === '1' && !process.env.CI;
const baseURL = process.env.DSA_WEB_PLAYWRIGHT_BASE_URL || `http://127.0.0.1:${previewPort}`;
const usesExternalServer = process.env.DSA_WEB_PLAYWRIGHT_EXTERNAL_SERVER === '1';
const prebuiltArtifact = process.env.DSA_WEB_PLAYWRIGHT_ARTIFACT;
const managedChromiumExecutable = process.env.WOLFYSTOCK_MANAGED_CHROMIUM_EXECUTABLE?.trim();
const managedFrontendOutput = process.env.WOLFYSTOCK_FRONTEND_OUTPUT_DIR?.trim();
const candidateSha = resolveCandidateSha();
const outputDir = process.env.PLAYWRIGHT_OUTPUT_DIR || path.join(managedFrontendOutput || '', 'playwright');
const prebuiltArtifactPath = prebuiltArtifact ? path.resolve(repoRoot, prebuiltArtifact) : undefined;
const artifactRoot = prebuiltArtifactPath
  ? dirname(prebuiltArtifactPath)
  : path.join(managedFrontendOutput || '', 'playwright-web-artifact');
const reporter = process.env.PLAYWRIGHT_HTML_REPORT
  ? ([
      ['list'],
      ['html', { outputFolder: process.env.PLAYWRIGHT_HTML_REPORT, open: 'never' }],
    ] as const)
  : 'list';

if (
  !managedChromiumExecutable ||
  !path.isAbsolute(managedChromiumExecutable) ||
  !existsSync(managedChromiumExecutable)
) {
  throw new Error(
    'WOLFYSTOCK_MANAGED_CHROMIUM_EXECUTABLE must identify a verified absolute executable; ' +
    'run Playwright through ./wolfy exec --profile test',
  );
}

if (!managedFrontendOutput || !path.isAbsolute(managedFrontendOutput)) {
  throw new Error(
    'WOLFYSTOCK_FRONTEND_OUTPUT_DIR must identify the managed run-scoped frontend output directory; ' +
    'run Playwright through ./wolfy exec --profile test',
  );
}

if (prebuiltArtifact) {
  execFileSync(process.env.PYTHON || 'python', [
    artifactScript,
    'verify',
    '--repo-root', repoRoot,
    '--artifact', prebuiltArtifactPath,
    '--expected-sha', candidateSha,
  ], { stdio: 'inherit' });
}

export default defineConfig({
  testDir: './e2e',
  outputDir,
  fullyParallel: false,
  retries: process.env.CI ? 2 : 0,
  reporter,
  ...(usesExternalServer ? {} : {
    webServer: {
      command: previewCommand(previewPort, candidateSha, Boolean(prebuiltArtifact), artifactRoot),
      cwd: configRoot,
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
      testIgnore: '**/*.release.spec.ts',
      use: { ...devices['Desktop Chrome'], executablePath: managedChromiumExecutable },
    },
    {
      name: 'chromium-mobile',
      testIgnore: '**/*.release.spec.ts',
      use: { ...devices['Pixel 5'], executablePath: managedChromiumExecutable },
    },
    {
      name: 'release-real-runtime',
      testMatch: '**/release-real-runtime.release.spec.ts',
      retries: 0,
      use: {
        ...devices['Desktop Chrome'],
        executablePath: managedChromiumExecutable,
        trace: 'retain-on-failure',
      },
    },
  ],
});
