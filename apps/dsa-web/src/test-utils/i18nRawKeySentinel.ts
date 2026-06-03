import { expect } from 'vitest';

const DEFAULT_RAW_I18N_KEY_PATTERNS = [
  /\bauth\.login\.[A-Za-z0-9_]+/i,
  /\bsettings\.[A-Za-z0-9_]+/,
  /\bnavigation\.[A-Za-z0-9_]+/,
  /\broutes\.[A-Za-z0-9_]+/,
  /\bnav\.[A-Za-z0-9_]+/,
];

const RENDERED_TEXT_ATTRIBUTES = [
  'aria-label',
  'aria-description',
  'placeholder',
  'title',
  'alt',
];

type RawI18nKeySentinelOptions = {
  patterns?: RegExp[];
};

function collectRawI18nKeyMatches(
  root: ParentNode & Pick<Node, 'textContent'>,
  options: RawI18nKeySentinelOptions = {},
) {
  const patterns = options.patterns ?? DEFAULT_RAW_I18N_KEY_PATTERNS;
  const candidates: Array<{ source: string; value: string }> = [
    { source: 'textContent', value: root.textContent || '' },
  ];

  root.querySelectorAll<HTMLElement>('*').forEach((element) => {
    RENDERED_TEXT_ATTRIBUTES.forEach((attribute) => {
      const value = element.getAttribute(attribute);
      if (value) {
        candidates.push({ source: attribute, value });
      }
    });
  });

  const matches = new Set<string>();
  candidates.forEach(({ source, value }) => {
    patterns.forEach((pattern) => {
      const match = value.match(pattern);
      if (match?.[0]) {
        matches.add(`${source}: ${match[0]}`);
      }
    });
  });

  const sortedMatches = Array.from(matches);
  sortedMatches.sort();
  return sortedMatches;
}

export function expectNoRawI18nKeys(
  root: ParentNode & Pick<Node, 'textContent'>,
  options?: RawI18nKeySentinelOptions,
) {
  expect(collectRawI18nKeyMatches(root, options)).toEqual([]);
}
