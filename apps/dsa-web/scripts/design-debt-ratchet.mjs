import fs from 'node:fs';
import path from 'node:path';

// This inventory intentionally recognizes only literal visual values. Bracket syntax
// is also how Tailwind consumes our CSS-variable tokens, so raw bracket counting
// would make the design system itself look like debt.
export const DEBT_CATEGORIES = [
  'literalFontSize',
  'literalRadius',
  'literalColor',
  'arbitraryShadow',
  'otherLiteralNumeric',
];

const LITERAL_FONT_SIZE = /\btext-\[(-?(?:\d*\.)?\d+(?:px|pt|em|rem))\]/g;
const LITERAL_RADIUS = /\brounded(?:-[trbl]{1,2})?-\[(-?(?:\d*\.)?\d+(?:px|rem|em|%))\]/g;
const LITERAL_COLOR = /\b(?:bg|text|border|outline|ring|fill|stroke|from|via|to)-\[(?!(?:color:)?var\()(#[0-9a-f]{3,8}|rgba?\([^\]]*|hsla?\([^\]]*|oklch\([^\]]*|lab\([^\]]*|lch\([^\]]*)\]/gi;
const ARBITRARY_SHADOW = /\b(?:shadow|drop-shadow)-\[(?!var\()([^\]]+)\]/g;
const ARBITRARY_NUMERIC = /\b(?:[a-z-]+)-\[(-?(?:\d*\.)?\d+(?:px|rem|em|vh|vw|%|deg|ms|s))\]/g;

function lineFor(text, offset) {
  return text.slice(0, offset).split(/\r?\n/).length;
}

function collect(text, regex, category, seen) {
  const items = [];
  regex.lastIndex = 0;
  let match;
  while ((match = regex.exec(text)) !== null) {
    const key = `${match.index}:${match[0]}`;
    if (!seen.has(key)) {
      seen.add(key);
      items.push({ category, utility: match[0], line: lineFor(text, match.index) });
    }
  }
  return items;
}

export function classifyDesignDebtText(text) {
  const seen = new Set();
  const items = [
    ...collect(text, LITERAL_FONT_SIZE, 'literalFontSize', seen),
    ...collect(text, LITERAL_RADIUS, 'literalRadius', seen),
    // A token can be wrapped in a CSS color function (for example
    // `text-[hsl(var(--state-info-hsl))]`), not only used as `var(...)`.
    // It remains a semantic consumption rather than a page-local literal.
    ...collect(text, LITERAL_COLOR, 'literalColor', seen).filter((item) => !item.utility.includes('var(')),
    ...collect(text, ARBITRARY_SHADOW, 'arbitraryShadow', seen).filter((item) => !item.utility.includes('var(')),
  ];
  const specificallyClassified = new Set(items.map((item) => item.utility));
  for (const item of collect(text, ARBITRARY_NUMERIC, 'otherLiteralNumeric', seen)) {
    if (!specificallyClassified.has(item.utility)) items.push(item);
  }
  return items;
}

export function inventoryDesignDebt(files, { rootDir } = {}) {
  const inventory = Object.fromEntries(DEBT_CATEGORIES.map((category) => [category, 0]));
  const findings = [];
  for (const file of files) {
    const text = fs.readFileSync(file, 'utf8');
    for (const finding of classifyDesignDebtText(text)) {
      inventory[finding.category] += 1;
      findings.push({ ...finding, file: path.relative(rootDir, file).split(path.sep).join('/') });
    }
  }
  return { inventory, findings };
}

export function qualifyDesignDebt({ candidate, baseline, changedFiles = [], changedBaseline = null }) {
  const blocking = [];
  for (const category of DEBT_CATEGORIES) {
    const actual = candidate[category] ?? 0;
    const maximum = baseline[category];
    if (!Number.isInteger(maximum) || maximum < 0) {
      blocking.push({ rule: 'design-debt-baseline-invalid', category, actual, expected: maximum });
    } else if (actual > maximum) {
      blocking.push({ rule: 'design-debt-growth', category, actual, expected: maximum });
    }
  }
  if (changedBaseline) {
    for (const category of ['literalFontSize', 'literalRadius', 'literalColor', 'arbitraryShadow']) {
      const actual = changedFiles[category] ?? 0;
      const previous = changedBaseline[category] ?? 0;
      if (actual > previous) blocking.push({ rule: 'changed-file-high-priority-debt', category, actual, expected: previous });
    }
  }
  return blocking;
}
