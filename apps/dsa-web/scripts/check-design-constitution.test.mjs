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
});
