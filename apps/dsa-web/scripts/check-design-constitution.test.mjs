import { describe, expect, it } from 'vitest';

import { scanSourceText } from './check-design-constitution.mjs';

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
