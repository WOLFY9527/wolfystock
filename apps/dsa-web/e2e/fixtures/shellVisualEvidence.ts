import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import type { Page } from '@playwright/test';

type ShellEvidenceViewport = {
  width: number;
  height: number;
};

export async function captureShellVisualEvidence(
  page: Page,
  routeId: string,
  viewport?: ShellEvidenceViewport,
) {
  const evidenceDir = process.env.DSA_WEB_SHELL_EVIDENCE_DIR;
  if (!evidenceDir) {
    return;
  }

  const size = viewport ?? page.viewportSize();
  const suffix = size ? `${size.width}x${size.height}` : 'viewport';
  await page.locator('output[aria-label="WolfyStock research workspace loading"]').waitFor({
    state: 'detached',
    timeout: 4_000,
  }).catch(() => undefined);
  await mkdir(evidenceDir, { recursive: true });
  await page.screenshot({
    path: path.join(evidenceDir, `${routeId}-${suffix}.png`),
    fullPage: true,
    animations: 'disabled',
  });
}
