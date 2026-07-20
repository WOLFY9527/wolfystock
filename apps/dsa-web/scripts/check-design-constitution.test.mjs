import fs from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import { scanSourceText } from './check-design-constitution.mjs';
import {
  analyzeResponsibilitySource,
  classifyResponsibilityOwner,
  compareResponsibilityBoundary,
  qualifyResponsibilityAnalysis,
  scanResponsibilityProject,
  validateResponsibilityManifest,
} from './responsibility-qualification.mjs';

describe('design constitution guard', () => {
  it('blocks solid gray Tailwind background surfaces', () => {
    const result = scanSourceText({
      relativePath: 'src/Example.tsx',
      text: '<section className="bg-gray-900 text-white">内容</section>',
    });

    expect(result.blocking).toEqual([
      expect.objectContaining({
        rule: 'no-solid-gray-bg',
        line: 1,
      }),
    ]);
  });

  it('does not block gray text utilities', () => {
    const result = scanSourceText({
      relativePath: 'src/Example.tsx',
      text: '<span className="text-gray-400">metadata</span>',
    });

    expect(result.blocking).toHaveLength(0);
  });

  it('warns on raw provider status copy that would be visible by default', () => {
    const result = scanSourceText({
      relativePath: 'src/Example.tsx',
      text: '<Badge>provider_down</Badge>',
    });

    expect(result.warnings).toEqual([
      expect.objectContaining({
        rule: 'raw-debug-copy',
        line: 1,
      }),
    ]);
  });

  it('warns on obvious English fallback labels in visible UI copy', () => {
    const result = scanSourceText({
      relativePath: 'src/Example.tsx',
      text: '<span>UNKNOWN</span>',
    });

    expect(result.warnings).toEqual([
      expect.objectContaining({
        rule: 'localized-ui-copy',
        line: 1,
      }),
    ]);
  });

  it('allows raw terms inside collapsed developer details', () => {
    const result = scanSourceText({
      relativePath: 'src/Example.tsx',
      text: [
        '<details>',
        '  <summary>开发者字段</summary>',
        '  <pre>provider_down</pre>',
        '</details>',
      ].join('\n'),
    });

    expect(result.blocking).toHaveLength(0);
    expect(result.warnings).toHaveLength(0);
  });

  it('blocks retired consumer theme language', () => {
    const result = scanSourceText({
      relativePath: 'src/Example.tsx',
      text: '<section className="spacex-neon-shell">内容</section>',
    });

    expect(result.blocking).toEqual([
      expect.objectContaining({
        rule: 'legacy-consumer-theme',
        line: 1,
      }),
    ]);
  });

  it('blocks retired glow helper classes without banning chart glow ids', () => {
    const bad = scanSourceText({
      relativePath: 'src/Example.tsx',
      text: '<div className="glow-cyan animate-pulse-glow" />',
    });
    const chart = scanSourceText({
      relativePath: 'src/Chart.tsx',
      text: '<linearGradient id="backtest-equity-glow" />',
    });

    expect(bad.blocking).toEqual([
      expect.objectContaining({ rule: 'dead-glow-helper' }),
    ]);
    expect(chart.blocking).toHaveLength(0);
  });

  it('blocks broad CSS utility neutralizers', () => {
    const result = scanSourceText({
      relativePath: 'src/Example.css',
      text: "html[data-theme-style='paper'] [class*='text-white'] { color: var(--ink); }",
    });

    expect(result.blocking).toEqual([
      expect.objectContaining({
        rule: 'broad-utility-neutralizer',
        line: 1,
      }),
    ]);
  });

  it('blocks old charcoal, workspace aliases, and UI-sans root defaults', () => {
    const result = scanSourceText({
      relativePath: 'src/index.css',
      text: [
        ':root {',
        '  --wolfy-canvas: #080a0d;',
        '  --wolfy-surface-console: #0d1015;',
        '  --font-display:',
        '    var(--font-stack-sans);',
        '}',
        'html[data-theme] {',
        '  --theme-heading-font: var(--font-ui);',
        '  --background: var(--color-charcoal-950);',
        '  --foreground: var(--color-white);',
        '  --theme-shell-bg: var(--wolfy-canvas);',
        '  --workspace-bg: var(--color-charcoal-950);',
        '  --workspace-text-muted: var(--color-gray-400);',
        '  --workspace-card-bg: rgba(255, 255, 255, 0.04);',
        '  --workspace-canvas: radial-gradient(circle at top, #080a0d, transparent);',
        '}',
      ].join('\n'),
    });

    expect(result.blocking).toEqual(expect.arrayContaining([
      expect.objectContaining({ rule: 'old-theme-default', line: 2 }),
      expect.objectContaining({ rule: 'old-theme-default', line: 4 }),
      expect.objectContaining({ rule: 'old-theme-default', line: 8 }),
      expect.objectContaining({ rule: 'old-theme-default', line: 12 }),
      expect.objectContaining({ rule: 'old-theme-default', line: 13 }),
    ]));
  });

  it('allows canonical paper root and shared theme aliases', () => {
    const result = scanSourceText({
      relativePath: 'src/index.css',
      text: [
        ':root {',
        '  --font-display: var(--font-stack-display);',
        '  --wolfy-canvas: var(--paper);',
        '  --wolfy-surface-console: rgb(251 248 243 / 0.76);',
        '  --cohere-black: var(--ink);',
        '  --cohere-white: var(--surface);',
        '}',
        'html[data-theme] {',
        '  --theme-heading-font: var(--font-display);',
        '  --background: var(--bg-page-hsl);',
        '  --foreground: var(--text-primary-hsl);',
        '  --theme-shell-bg: var(--wolfy-canvas);',
        '}',
      ].join('\n'),
    });

    expect(result.blocking.filter((finding) => finding.rule === 'old-theme-default')).toHaveLength(0);
  });

  it('blocks direct dark material in shared primitive owners', () => {
    const result = scanSourceText({
      relativePath: 'src/pages/roughShellShared.tsx',
      text: '<li className="rounded-xl border border-white/8 bg-black/10 px-3 py-2">内容</li>',
    });

    expect(result.blocking).toEqual([
      expect.objectContaining({
        rule: 'shared-primitive-paper-material',
        line: 1,
      }),
    ]);
  });

  it('blocks ConsumerWorkspaceShell from importing TerminalPageShell', () => {
    const result = scanSourceText({
      relativePath: 'src/components/layout/ConsumerWorkspaceShell.tsx',
      text: "import { TerminalPageShell } from '../terminal/TerminalPrimitives';",
    });

    expect(result.blocking).toEqual([
      expect.objectContaining({
        rule: 'consumer-shell-terminal-lock-in',
        line: 1,
      }),
    ]);
  });
});

describe('frontend responsibility qualification', () => {
  const concentratedPage = [
    "import { useEffect, useState } from 'react';",
    "import { getOverview } from '../api/marketOverview';",
    "import { projectDataState } from '../utils/productReadModelView';",
    "import { calculateTrend } from '../components/market-overview/marketOverviewUtils';",
    '',
    'export default function MarketOverviewPage() {',
    '  const [state, setState] = useState({ value: null });',
    '  useEffect(() => {',
    '    const controller = new AbortController();',
    '    void getOverview({ signal: controller.signal }).then((payload) => {',
    '      setState(projectDataState(calculateTrend(payload)));',
    '    });',
    '    return () => controller.abort();',
    '  }, []);',
    '  return <section>{state.value}</section>;',
    '}',
  ].join('\n');

  it('classifies semantic responsibilities without using file size as a proxy', () => {
    const analysis = analyzeResponsibilitySource({
      relativePath: 'src/pages/MarketOverviewPage.tsx',
      text: concentratedPage,
    });

    expect(analysis.ownerKind).toBe('route-page');
    expect(analysis.responsibilities).toEqual(expect.arrayContaining([
      'route-composition',
      'presentation',
      'state-ownership',
      'effect-ownership',
      'request-orchestration',
      'stale-response-protection',
      'truth-projection',
      'domain-calculation',
    ]));
    expect(analysis.signals.apiCalls).toBe(1);
    expect(analysis.signals.effectApiCalls).toBe(1);
    expect(analysis.signals.apiImports).toBe(1);
    expect(analysis.signals.staleProtection).toEqual({ status: 'observed', evidence: 2 });
    expect(analysis.dependencies).toEqual(['market']);
  });

  it('does not treat an unused API import as orchestration', () => {
    const analysis = analyzeResponsibilitySource({
      relativePath: 'src/components/MarketSummary.tsx',
      text: [
        "import { getOverview } from '../api/marketOverview';",
        'export function MarketSummary() {',
        '  return <div>已有数据</div>;',
        '}',
      ].join('\n'),
    });

    expect(analysis.signals.apiImports).toBe(1);
    expect(analysis.signals.apiCalls).toBe(0);
    expect(analysis.responsibilities).not.toContain('request-orchestration');
  });

  it('counts invoked API object endpoints independent of verb and excludes URL helpers', () => {
    const endpointAnalysis = analyzeResponsibilitySource({
      relativePath: 'src/hooks/useSession.ts',
      text: [
        "import { authApi } from '../api/auth';",
        'export function useSession() {',
        "  void authApi.login({ password: 'test-only' });",
        '}',
      ].join('\n'),
    });
    const helperAnalysis = analyzeResponsibilitySource({
      relativePath: 'src/hooks/useTaskStreamUrl.ts',
      text: [
        "import { analysisApi } from '../api/analysis';",
        'export function useTaskStreamUrl() {',
        '  return analysisApi.getTaskStreamUrl();',
        '}',
      ].join('\n'),
    });

    expect(endpointAnalysis.signals.apiImports).toBe(1);
    expect(endpointAnalysis.signals.apiCalls).toBe(1);
    expect(endpointAnalysis.signals.effectApiCalls).toBe(0);
    expect(endpointAnalysis.signals.staleProtection.status).toBe('not-applicable');
    expect(endpointAnalysis.responsibilities).toContain('request-orchestration');
    expect(helperAnalysis.signals.apiImports).toBe(1);
    expect(helperAnalysis.signals.apiCalls).toBe(0);
    expect(helperAnalysis.responsibilities).not.toContain('request-orchestration');
  });

  it('normalizes camel-case API modules into explicit domain dependencies', () => {
    const analysis = analyzeResponsibilitySource({
      relativePath: 'src/hooks/useResearchDecision.ts',
      text: [
        "import { marketDecisionCockpitApi } from '../api/marketDecisionCockpit';",
        "import { researchRadarApi } from '../api/researchRadar';",
        'export function useResearchDecision() {',
        '  void marketDecisionCockpitApi.getDecisionCockpit();',
        '  void researchRadarApi.getResearchRadar();',
        '}',
      ].join('\n'),
    });

    expect(analysis.dependencies).toEqual(['market', 'research']);
    expect(analysis.responsibilities).toContain('cross-domain-dependency');
  });

  it('does not infer React state ownership from an unrelated local function name', () => {
    const analysis = analyzeResponsibilitySource({
      relativePath: 'src/utils/localStateName.ts',
      text: [
        'function useState() { return 1; }',
        'export const value = useState();',
      ].join('\n'),
    });

    expect(analysis.signals.stateCalls).toBe(0);
    expect(analysis.responsibilities).not.toContain('state-ownership');
  });

  it('keeps effect presence separate from request lifecycle semantics', () => {
    const analysis = analyzeResponsibilitySource({
      relativePath: 'src/components/DocumentTitle.tsx',
      text: [
        "import { useEffect } from 'react';",
        'export function DocumentTitle() {',
        "  useEffect(() => { document.title = '研究'; }, []);",
        '  return <span>研究</span>;',
        '}',
      ].join('\n'),
    });

    expect(analysis.signals.effects).toBe(1);
    expect(analysis.signals.apiCalls).toBe(0);
    expect(analysis.signals.effectApiCalls).toBe(0);
    expect(analysis.signals.staleProtection.status).toBe('not-applicable');
    expect(analysis.responsibilities).not.toContain('request-orchestration');
  });

  it('does not link an event request to an unrelated effect', () => {
    const analysis = analyzeResponsibilitySource({
      relativePath: 'src/hooks/useMarketAction.ts',
      text: [
        "import { useEffect } from 'react';",
        "import { marketApi } from '../api/market';",
        'export function useMarketAction() {',
        "  useEffect(() => { document.title = 'market'; }, []);",
        '  return () => marketApi.getTemperature();',
        '}',
      ].join('\n'),
    });

    expect(analysis.signals.effects).toBe(1);
    expect(analysis.signals.apiCalls).toBe(1);
    expect(analysis.signals.effectApiCalls).toBe(0);
    expect(analysis.signals.staleProtection.status).toBe('not-applicable');
    expect(qualifyResponsibilityAnalysis(analysis)).not.toEqual(expect.arrayContaining([
      expect.objectContaining({ rule: 'unguarded-effect-request' }),
    ]));
  });

  it('requires a complete active guard lifecycle for effect-owned requests', () => {
    const analyzeEffect = (guardLines) => analyzeResponsibilitySource({
      relativePath: 'src/hooks/useMarketSnapshot.ts',
      text: [
        "import { useEffect } from 'react';",
        "import { marketApi } from '../api/market';",
        'export function useMarketSnapshot() {',
        '  useEffect(() => {',
        ...guardLines,
        '  }, []);',
        '}',
      ].join('\n'),
    });
    const unguarded = analyzeEffect(['    void marketApi.getTemperature();']);
    const declarationOnly = analyzeEffect([
      '    let active = true;',
      '    void marketApi.getTemperature();',
    ]);
    const checkedOnlyBeforeRequest = analyzeEffect([
      '    let active = true;',
      '    if (!active) return;',
      '    void marketApi.getTemperature();',
      '    return () => { active = false; };',
    ]);
    const guarded = analyzeEffect([
      '    let active = true;',
      '    void marketApi.getTemperature().then(() => {',
      '      if (!active) return;',
      '    });',
      '    return () => { active = false; };',
    ]);

    expect(unguarded.signals.effectApiCalls).toBe(1);
    expect(unguarded.signals.staleProtection.status).toBe('not-observed');
    expect(qualifyResponsibilityAnalysis(unguarded)).toEqual(expect.arrayContaining([
      expect.objectContaining({ rule: 'unguarded-effect-request' }),
    ]));
    expect(declarationOnly.signals.staleProtection.status).toBe('not-observed');
    expect(qualifyResponsibilityAnalysis(declarationOnly)).toEqual(expect.arrayContaining([
      expect.objectContaining({ rule: 'unguarded-effect-request' }),
    ]));
    expect(checkedOnlyBeforeRequest.signals.staleProtection.status).toBe('not-observed');
    expect(guarded.signals.staleProtection.status).toBe('observed');
    expect(qualifyResponsibilityAnalysis(guarded)).not.toEqual(expect.arrayContaining([
      expect.objectContaining({ rule: 'unguarded-effect-request' }),
    ]));
  });

  it('does not let one guarded effect hide another unguarded request effect', () => {
    const analysis = analyzeResponsibilitySource({
      relativePath: 'src/hooks/useMarketSnapshot.ts',
      text: [
        "import { useEffect } from 'react';",
        "import { marketApi } from '../api/market';",
        'export function useMarketSnapshot() {',
        '  useEffect(() => {',
        '    let cancelled = false;',
        '    void marketApi.getTemperature().then(() => {',
        '      if (cancelled) return;',
        '    });',
        '    return () => { cancelled = true; };',
        '  }, []);',
        '  useEffect(() => {',
        '    void marketApi.getBreadth();',
        '  }, []);',
        '}',
      ].join('\n'),
    });

    expect(analysis.signals.effectApiCalls).toBe(2);
    expect(analysis.signals.staleProtection.status).toBe('not-observed');
    expect(qualifyResponsibilityAnalysis(analysis)).toEqual(expect.arrayContaining([
      expect.objectContaining({ rule: 'unguarded-effect-request' }),
    ]));
  });

  it('requires an AbortController to be aborted before it counts as lifecycle protection', () => {
    const analyzeEffect = (cleanupLine) => analyzeResponsibilitySource({
      relativePath: 'src/hooks/useMarketSnapshot.ts',
      text: [
        "import { useEffect } from 'react';",
        "import { marketApi } from '../api/market';",
        'export function useMarketSnapshot() {',
        '  useEffect(() => {',
        '    const controller = new AbortController();',
        '    void marketApi.getTemperature({ signal: controller.signal });',
        cleanupLine,
        '  }, []);',
        '}',
      ].filter(Boolean).join('\n'),
    });

    expect(analyzeEffect('').signals.staleProtection.status).toBe('not-observed');
    expect(analyzeEffect('    controller.abort();').signals.staleProtection.status).toBe('not-observed');
    expect(analyzeEffect('    return () => controller.abort();').signals.staleProtection.status).toBe('observed');
  });

  it('fails visibly when TypeScript parsing fails', () => {
    expect(() => analyzeResponsibilitySource({
      relativePath: 'src/pages/BrokenPage.tsx',
      text: 'export const value = ;',
    })).toThrowError(expect.objectContaining({
      code: 'RESPONSIBILITY_PARSE_ERROR',
    }));
  });

  it('blocks missing signals for unregistered production owners instead of treating them as zero', () => {
    const analysis = analyzeResponsibilitySource({
      relativePath: 'src/hooks/useMarketSnapshot.ts',
      text: 'export function useMarketSnapshot() { return null; }',
    });
    delete analysis.signals.apiCalls;

    expect(qualifyResponsibilityAnalysis(analysis)).toEqual(expect.arrayContaining([
      expect.objectContaining({
        rule: 'responsibility-analysis-incomplete',
        signal: 'apiCalls',
        actual: 'missing',
      }),
    ]));
  });

  it('does not classify tests or generated files as production owners', () => {
    expect(classifyResponsibilityOwner('src/pages/__tests__/HomePage.test.tsx')).toEqual({
      kind: 'test',
      production: false,
    });
    expect(classifyResponsibilityOwner('src/generated/client.ts')).toEqual({
      kind: 'generated',
      production: false,
    });
  });

  it('blocks presentation components that call API orchestration directly', () => {
    const analysis = analyzeResponsibilitySource({
      relativePath: 'src/components/MarketCard.tsx',
      text: [
        "import { loadMarket } from '../api/market';",
        'export function MarketCard() {',
        '  void loadMarket();',
        '  return <article>市场</article>;',
        '}',
      ].join('\n'),
    });

    expect(qualifyResponsibilityAnalysis(analysis)).toEqual(expect.arrayContaining([
      expect.objectContaining({ rule: 'presentation-orchestration-mix' }),
    ]));
  });

  it('allows a controller-named component to own request orchestration', () => {
    const analysis = analyzeResponsibilitySource({
      relativePath: 'src/components/MarketCardController.tsx',
      text: [
        "import { loadMarket } from '../api/market';",
        'export function MarketCardController() {',
        '  void loadMarket();',
        '  return <article>市场</article>;',
        '}',
      ].join('\n'),
    });

    expect(qualifyResponsibilityAnalysis(analysis)).toEqual([]);
  });

  it('blocks route composition that mixes requests, domain calculation, and presentation', () => {
    const analysis = analyzeResponsibilitySource({
      relativePath: 'src/pages/ScenarioPage.tsx',
      text: [
        "import { scenarioLabApi } from '../api/scenarioLab';",
        "import { calculateScenario } from '../components/scenario/calculateScenario';",
        'export function ScenarioPage() {',
        '  void scenarioLabApi.runScenarioLab();',
        '  const scenario = calculateScenario();',
        '  return <main>{scenario}</main>;',
        '}',
      ].join('\n'),
    });

    expect(qualifyResponsibilityAnalysis(analysis)).toEqual(expect.arrayContaining([
      expect.objectContaining({ rule: 'route-projection-presentation-concentration' }),
    ]));
  });

  it('blocks growth above an owner-specific accepted ceiling but allows reductions', () => {
    const baseline = {
      path: 'src/pages/MarketOverviewPage.tsx',
      maxSignals: { stateCalls: 1, effects: 1, apiCalls: 1, effectApiCalls: 1 },
      allowedResponsibilities: ['route-composition', 'presentation', 'state-ownership', 'effect-ownership', 'request-orchestration'],
      allowedDependencies: ['market'],
      staleProtection: 'observed',
    };
    const grown = {
      ownerKind: 'route-page',
      responsibilities: baseline.allowedResponsibilities,
      dependencies: ['market'],
      signals: { stateCalls: 2, effects: 1, apiCalls: 1, effectApiCalls: 1, staleProtection: { status: 'observed', evidence: 1 } },
    };
    const reduced = { ...grown, signals: { ...grown.signals, stateCalls: 1 } };

    expect(compareResponsibilityBoundary(grown, baseline)).toEqual(expect.arrayContaining([
      expect.objectContaining({ rule: 'responsibility-debt-growth', signal: 'stateCalls' }),
    ]));
    expect(compareResponsibilityBoundary(reduced, baseline)).toEqual([]);

    const incomplete = {
      ...reduced,
      signals: {
        stateCalls: 1,
        effects: 1,
        effectApiCalls: 0,
        staleProtection: { status: 'not-applicable', evidence: 0 },
      },
    };
    expect(compareResponsibilityBoundary(incomplete, baseline)).toEqual(expect.arrayContaining([
      expect.objectContaining({ rule: 'responsibility-analysis-incomplete', signal: 'apiCalls' }),
    ]));
  });

  it('requires complete manifest metadata and rejects unknown production owners', () => {
    expect(() => validateResponsibilityManifest({
      schemaVersion: 1,
      owners: [],
    })).toThrowError(/acceptedBase|signalModel/);

    expect(() => validateResponsibilityManifest({
      schemaVersion: 1,
      signalModel: 'frontend-responsibility-signals-v1',
      acceptedBase: {
        commit: 'ee91023cc51084fc63c288fbe47729db14527117',
        tree: '32a8a4f843180dbf4e99ae041f20ef660b3f046d',
      },
      owners: [{ path: 'src/pages/HomePage.tsx' }],
    })).toThrowError(/maxSignals|allowedResponsibilities|staleProtection/);
    expect(() => validateResponsibilityManifest({
      schemaVersion: 1,
      signalModel: 'frontend-responsibility-signals-v1',
      acceptedBase: {
        commit: 'ee91023cc51084fc63c288fbe47729db14527117',
        tree: '32a8a4f843180dbf4e99ae041f20ef660b3f046d',
      },
      owners: [{
        path: 'src/pages/HomePage.tsx',
        maxSignals: { stateCalls: 0, effects: 0, apiCalls: 0, effectApiCalls: 0, truthCalls: 0, domainCalls: 0 },
        allowedResponsibilities: [],
        allowedDependencies: [],
        staleProtection: 'not-applicable',
        profile: 'cohesive-owner',
        rationale: 'test owner metadata',
        retirementCondition: 'remove when test completes',
      }],
    }, { knownFiles: new Set(['src/pages/OtherPage.tsx']) })).toThrowError(/unknown owner/);
  });

  it('treats request removal as an improvement and requires the boundary to ratchet down', () => {
    const baseline = {
      path: 'src/hooks/useMarketData.ts',
      maxSignals: { apiCalls: 1, effectApiCalls: 1 },
      allowedResponsibilities: ['request-orchestration', 'stale-response-protection'],
      allowedDependencies: ['market'],
      staleProtection: 'observed',
    };
    const reduced = {
      ownerKind: 'controller',
      responsibilities: [],
      dependencies: [],
      signals: {
        apiCalls: 0,
        effectApiCalls: 0,
        staleProtection: { status: 'not-applicable', evidence: 0 },
      },
    };

    const findings = compareResponsibilityBoundary(reduced, baseline);
    expect(findings).toEqual(expect.arrayContaining([
      expect.objectContaining({ rule: 'responsibility-boundary-stale', signal: 'apiCalls' }),
      expect.objectContaining({ rule: 'responsibility-boundary-stale', signal: 'effectApiCalls' }),
    ]));
    expect(findings).not.toEqual(expect.arrayContaining([
      expect.objectContaining({ rule: 'stale-protection-regression' }),
    ]));
  });

  it('requires manifest owners to be lexically ordered for deterministic qualification', () => {
    const owner = (ownerPath) => ({
      path: ownerPath,
      maxSignals: { stateCalls: 0, effects: 0, apiCalls: 0, effectApiCalls: 0, truthCalls: 0, domainCalls: 0 },
      allowedResponsibilities: [],
      allowedDependencies: [],
      staleProtection: 'not-applicable',
      profile: 'cohesive-owner',
      rationale: 'test owner metadata',
      retirementCondition: 'remove when test completes',
    });

    expect(() => validateResponsibilityManifest({
      schemaVersion: 1,
      signalModel: 'frontend-responsibility-signals-v1',
      acceptedBase: {
        commit: 'ee91023cc51084fc63c288fbe47729db14527117',
        tree: '32a8a4f843180dbf4e99ae041f20ef660b3f046d',
      },
      owners: [owner('src/pages/ZPage.tsx'), owner('src/pages/APage.tsx')],
    })).toThrowError(/lexically sorted/);
  });

  it('sorts project analysis deterministically and reports parse failure as blocking', () => {
    const fixtureRoot = fs.mkdtempSync(path.join(process.cwd(), '.responsibility-test-'));
    const acceptedBase = {
      commit: 'ee91023cc51084fc63c288fbe47729db14527117',
      tree: '32a8a4f843180dbf4e99ae041f20ef660b3f046d',
    };
    const manifestPath = path.join(fixtureRoot, 'responsibility-boundaries.json');
    const files = ['src/hooks/useZeta.ts', 'src/hooks/useAlpha.ts'];

    try {
      fs.mkdirSync(path.join(fixtureRoot, 'src/hooks'), { recursive: true });
      for (const relativePath of files) {
        fs.writeFileSync(path.join(fixtureRoot, relativePath), 'export const value = 1;\n');
      }
      fs.writeFileSync(manifestPath, JSON.stringify({
        schemaVersion: 1,
        signalModel: 'frontend-responsibility-signals-v1',
        acceptedBase,
        owners: [],
      }));

      const forward = scanResponsibilityProject({
        rootDir: fixtureRoot,
        files,
        allFiles: files,
        manifestPath,
      });
      const reverse = scanResponsibilityProject({
        rootDir: fixtureRoot,
        files: [...files].reverse(),
        allFiles: [...files].reverse(),
        manifestPath,
      });
      expect(forward).toEqual(reverse);
      expect(forward.analyses.map((analysis) => analysis.path)).toEqual([
        'src/hooks/useAlpha.ts',
        'src/hooks/useZeta.ts',
      ]);

      const brokenPath = 'src/hooks/useBroken.ts';
      fs.writeFileSync(path.join(fixtureRoot, brokenPath), 'export const value = ;\n');
      const failed = scanResponsibilityProject({
        rootDir: fixtureRoot,
        files: [brokenPath],
        allFiles: [brokenPath],
        manifestPath,
      });
      expect(failed.filesScanned).toBe(0);
      expect(failed.blocking).toEqual([
        expect.objectContaining({ rule: 'responsibility-analysis-failure', file: brokenPath }),
      ]);

      const presentationPath = 'src/components/MarketCard.tsx';
      fs.mkdirSync(path.join(fixtureRoot, 'src/components'), { recursive: true });
      fs.mkdirSync(path.join(fixtureRoot, 'src/api'), { recursive: true });
      fs.writeFileSync(path.join(fixtureRoot, presentationPath), [
        "import { loadMarket } from '../api/market';",
        'export function MarketCard() {',
        '  void loadMarket();',
        '  return <article>market</article>;',
        '}',
      ].join('\n'));
      const forbidden = scanResponsibilityProject({
        rootDir: fixtureRoot,
        files: [presentationPath],
        allFiles: [presentationPath],
        manifestPath,
      });
      expect(forbidden.blocking).toEqual([
        expect.objectContaining({ rule: 'presentation-orchestration-mix', file: presentationPath }),
      ]);
    } finally {
      fs.rmSync(fixtureRoot, { recursive: true, force: true });
    }
  });
});
