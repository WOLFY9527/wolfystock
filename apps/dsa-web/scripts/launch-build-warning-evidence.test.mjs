import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

function webPath(...segments) {
  const cwd = process.cwd();
  const webRoot = cwd.endsWith('/apps/dsa-web') ? cwd : join(cwd, 'apps/dsa-web');
  return join(webRoot, ...segments);
}

function readWebFile(...segments) {
  return readFileSync(webPath(...segments), 'utf8');
}

describe('launch build warning evidence', () => {
  it('keeps the Vite large-chunk warning visible instead of suppressing it', () => {
    const packageJson = JSON.parse(readWebFile('package.json'));
    const viteConfig = readWebFile('vite.config.ts');

    expect(packageJson.scripts.build).toBe('tsc -b && vite build');
    expect(viteConfig).not.toMatch(/chunkSizeWarningLimit/);
  });

  it('keeps the known chart-size source isolated to the lazy deterministic chart workspace', () => {
    const appSource = readWebFile('src/App.tsx');
    const chartWorkspaceSource = readWebFile('src/components/backtest/DeterministicBacktestChartWorkspace.tsx');

    expect(appSource).toContain("const DeterministicBacktestResultPage = lazy(() => import('./pages/DeterministicBacktestResultPage'))");
    expect(chartWorkspaceSource).toContain("import * as echarts from 'echarts/core'");
    expect(chartWorkspaceSource).toContain("import { BarChart, LineChart } from 'echarts/charts'");
    expect(chartWorkspaceSource).toContain("import { CanvasRenderer } from 'echarts/renderers'");
    expect(chartWorkspaceSource).toContain('data-chart-engine="echarts"');
  });
});
