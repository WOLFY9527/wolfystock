import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = path.resolve(SCRIPT_DIR, '..');
const SRC_DIR = path.join(ROOT_DIR, 'src');

const SCANNED_EXTENSIONS = new Set(['.tsx', '.ts', '.css', '.js']);
const EXTRA_SCAN_FILES = [
  'tailwind.config.js',
];
const EXCLUDED_PARTS = new Set([
  'node_modules',
  'dist',
  'build',
  'coverage',
  'test-results',
  'playwright-report',
  'generated',
  'assets',
  'images',
  'tmp',
]);

const RULES = [
  {
    id: 'no-solid-gray-bg',
    severity: 'blocking',
    hint: 'Use DESIGN.md paper tokens and shared research primitives such as Linear/Terminal surfaces, not page-local gray slabs.',
  },
  {
    id: 'raw-debug-copy',
    severity: 'warning',
    hint: 'Map raw/debug/provider/schema terms to user-facing Chinese copy, or hide them under collapsed developer details.',
  },
  {
    id: 'localized-ui-copy',
    severity: 'warning',
    hint: 'Use Chinese labels for default UI; keep English only for tickers, providers, metrics, currencies, and developer-only details.',
  },
  {
    id: 'native-ui',
    severity: 'warning',
    hint: 'Use no-scrollbar on visible scroll containers and shared paper-token form controls.',
  },
  {
    id: 'legacy-consumer-theme',
    severity: 'blocking',
    hint: 'Consumer frontend must not reintroduce SpaceX/cyberpunk/neon theme language.',
  },
  {
    id: 'dead-glow-helper',
    severity: 'blocking',
    hint: 'Use canonical paper shadows and semantic state tokens, not retired neon/glow helper classes.',
  },
  {
    id: 'broad-utility-neutralizer',
    severity: 'blocking',
    hint: 'Do not use broad [class*=...] recoloring neutralizers; fix semantic token owners instead.',
  },
  {
    id: 'old-theme-default',
    severity: 'blocking',
    hint: 'Root consumer defaults must stay paper-first with display font ownership, not charcoal/UI-sans legacy defaults.',
  },
  {
    id: 'consumer-shell-terminal-lock-in',
    severity: 'blocking',
    hint: 'ConsumerWorkspaceShell must own the consumer page shell instead of importing TerminalPageShell.',
  },
  {
    id: 'shared-primitive-paper-material',
    severity: 'blocking',
    hint: 'Shared consumer primitives must use paper tokens instead of direct black/white slabs or legacy glow shadows.',
  },
];

const SOLID_GRAY_BG_RE = /\bbg-(?:gray|zinc|slate|neutral)-[A-Za-z0-9[\]_/.-]+/g;
const LEGACY_CONSUMER_THEME_RE = /\b(?:spacex|cyberpunk|neon)\b/i;
const DEAD_GLOW_HELPER_RE = /\b(?:glow-cyan|glow-purple|animate-pulse-glow|pulse-glow|gauge-glow|data-sentiment-glow)\b/i;
const BROAD_UTILITY_NEUTRALIZER_RE = /\[class\*=['"](?:border-white|bg-white|bg-black|text-white|shadow-|drop-shadow|glow)['"]\]/;
const CONSUMER_SHELL_PATH = 'src/components/layout/ConsumerWorkspaceShell.tsx';
const SHARED_PRIMITIVE_OWNER_PATHS = new Set([
  'src/components/layout/ConsumerWorkspaceShell.tsx',
  'src/components/linear/LinearPrimitives.tsx',
  'src/components/terminal/TerminalPrimitives.tsx',
  'src/pages/roughShellShared.tsx',
]);
const SHARED_PRIMITIVE_LEGACY_MATERIAL_RE = /\b(?:bg-black\/|bg-white\/|border-white\/|text-white\/|backdrop-blur-(?:sm|md|lg|xl)|drop-shadow|shadow-\[var\(--wolfy-(?:shadow-console|glow-bloom|glow-focus)\)\]|from-\[#080a0d\]|to-\[#0d1015\])/i;
const WORKSPACE_TOKEN_NAMES = new Set([
  '--workspace-bg',
  '--workspace-text',
  '--workspace-text-muted',
  '--workspace-card-bg',
  '--workspace-card-border',
  '--workspace-canvas',
]);
const SHARED_TOKEN_NAMES = new Set([
  '--background',
  '--foreground',
  '--font-display',
  '--theme-heading-font',
  '--theme-shell-bg',
  '--wolfy-canvas',
  '--wolfy-surface-console',
  '--cohere-black',
  '--cohere-white',
  ...WORKSPACE_TOKEN_NAMES,
]);
const LEGACY_TOKEN_ALIAS_RE = /var\(--(?:color-charcoal-\d+|color-white|color-gray-\d+|font-sans|font-stack-sans|font-ui)\)/i;
const LEGACY_TOKEN_LITERAL_RE = /#(?:080a0d|0d1015|11151c|0b0e13|000000|ffffff)\b/i;
const LEGACY_WORKSPACE_VALUE_RE = /rgba?\(\s*255\s*,\s*255\s*,\s*255\s*,\s*0\.0[2-9]\s*\)|rgb\(\s*255\s+255\s+255\s*\/\s*0\.0[2-9]\s*\)|radial-gradient\(/i;
const PAPER_REQUIRED_DECLARATIONS = [
  {
    selector: ':root',
    token: '--font-display',
    expected: /(?:var\(--font-stack-display\)|"Noto Serif SC")/i,
    excerpt: ':root --font-display must use the paper display font.',
  },
  {
    selector: ':root',
    token: '--wolfy-canvas',
    expected: /var\(--paper\)/i,
    excerpt: ':root --wolfy-canvas must resolve to the paper canvas.',
  },
  {
    selector: ':root',
    token: '--wolfy-surface-console',
    expected: /(?:251\s+248\s+243|var\(--surface)/i,
    excerpt: ':root --wolfy-surface-console must resolve to the paper surface.',
  },
  {
    selector: 'html[data-theme]',
    token: '--theme-heading-font',
    expected: /var\(--font-display\)/i,
    excerpt: 'html[data-theme] --theme-heading-font must use --font-display.',
  },
  {
    selector: 'html[data-theme]',
    token: '--background',
    expected: /var\(--bg-page-hsl\)/i,
    excerpt: 'html[data-theme] --background must use --bg-page-hsl.',
  },
  {
    selector: 'html[data-theme]',
    token: '--foreground',
    expected: /var\(--text-primary-hsl\)/i,
    excerpt: 'html[data-theme] --foreground must use --text-primary-hsl.',
  },
  {
    selector: 'html[data-theme]',
    token: '--theme-shell-bg',
    expected: /var\(--(?:wolfy-canvas|wolfy-app-background)\)/i,
    excerpt: 'html[data-theme] --theme-shell-bg must use a paper canvas token.',
  },
];

const RAW_COPY_TERMS = [
  'RAW',
  'DEBUG',
  'SCHEMA',
  'PROVIDER',
  'provider_down',
  'provider_error',
  'raw metadata',
  'schema internals',
  'system prompt',
  'API key',
];

const LOCALIZED_COPY_TERMS = [
  'UNKNOWN',
  'Key Metrics',
  'Data Quality',
  'Execution Assumptions',
  'Advanced Details',
  'SCANNER CANDIDATES',
  'Critical',
  'Provider Down',
  'Provider Error',
];

const DEVELOPER_DETAIL_MARKERS = [
  '开发者字段',
  '原始诊断',
  '数据质量',
  '执行假设',
  '调试信息',
  'Developer Details',
  'Raw Diagnostics',
];

function printHelp() {
  console.log(`Usage: node scripts/check-design-constitution.mjs [--files <path...>] [--files-from PATH]

WolfyStock design constitution guard. By default, scans all frontend source
files. Use --files or --files-from for changed-file validation tiers.

Options:
  --files <path...>    Limit scan to explicit app-relative, repo-relative, or absolute files.
  --files-from PATH    Read newline-delimited file paths from PATH ("-" for stdin).
  -h, --help           Show this help text.
`);
}

function shouldScanFile(relativePath) {
  const parts = relativePath.split(path.sep);
  if (parts.some((part) => EXCLUDED_PARTS.has(part))) {
    return false;
  }
  if (parts.includes('__tests__') || /\.test\.[cm]?[jt]sx?$/.test(relativePath)) {
    return false;
  }
  return SCANNED_EXTENSIONS.has(path.extname(relativePath));
}

function readFilesFrom(filePath) {
  if (filePath === '-') {
    return fs.readFileSync(0, 'utf8').split(/\r?\n/);
  }
  const resolved = path.isAbsolute(filePath) ? filePath : path.resolve(ROOT_DIR, filePath);
  return fs.readFileSync(resolved, 'utf8').split(/\r?\n/);
}

function normalizeCandidateFile(candidate, rootDir = ROOT_DIR) {
  const raw = candidate.trim();
  if (!raw) {
    return null;
  }

  let absolutePath;
  if (path.isAbsolute(raw)) {
    absolutePath = raw;
  } else if (raw.split(/[\\/]/).slice(0, 2).join('/') === 'apps/dsa-web') {
    absolutePath = path.resolve(rootDir, '..', '..', raw);
  } else {
    absolutePath = path.resolve(rootDir, raw);
  }

  const relativePath = path.relative(rootDir, absolutePath);
  if (relativePath.startsWith('..') || path.isAbsolute(relativePath)) {
    return null;
  }
  if (!shouldScanFile(relativePath)) {
    return null;
  }
  if (!fs.existsSync(absolutePath) || !fs.statSync(absolutePath).isFile()) {
    return null;
  }
  return absolutePath;
}

function listLimitedSourceFiles({ files = [], filesFrom = [], rootDir = ROOT_DIR } = {}) {
  const candidates = [...files];
  for (const fileList of filesFrom) {
    candidates.push(...readFilesFrom(fileList));
  }
  return [...new Set(candidates.map((candidate) => normalizeCandidateFile(candidate, rootDir)).filter(Boolean))].sort();
}

function listSourceFiles(dir = SRC_DIR) {
  const files = [];
  if (!fs.existsSync(dir)) {
    return files;
  }

  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const absolutePath = path.join(dir, entry.name);
    const relativePath = path.relative(ROOT_DIR, absolutePath);
    if (entry.isDirectory()) {
      if (!relativePath.split(path.sep).some((part) => EXCLUDED_PARTS.has(part))) {
        files.push(...listSourceFiles(absolutePath));
      }
      continue;
    }
    if (entry.isFile() && shouldScanFile(relativePath)) {
      files.push(absolutePath);
    }
  }

  return files.sort();
}

function listProjectSourceFiles(rootDir = ROOT_DIR) {
  const sourceFiles = listSourceFiles(path.join(rootDir, 'src'));
  const extraFiles = EXTRA_SCAN_FILES
    .map((relativePath) => path.join(rootDir, relativePath))
    .filter((absolutePath) => fs.existsSync(absolutePath) && fs.statSync(absolutePath).isFile());
  return [...new Set([...sourceFiles, ...extraFiles])].sort();
}

function makeFinding({ rule, severity, relativePath, line, excerpt, hint }) {
  return {
    rule,
    severity,
    file: relativePath,
    line,
    excerpt: excerpt.trim(),
    hint,
  };
}

function isLikelyVisibleCopyLine(line, term) {
  const escapedTerm = escapeRegExp(term);
  return [
    new RegExp(`>[^<{}]*${escapedTerm}[^<{}]*<`, term === term.toUpperCase() ? '' : 'i'),
    new RegExp(`\\b(?:aria-label|title|placeholder|label|emptyText|helperText)=["'][^"']*${escapedTerm}`, 'i'),
    new RegExp(`\\b(?:label|title|placeholder|description|summary|text|message):\\s*["'][^"']*${escapedTerm}`, 'i'),
  ].some((pattern) => pattern.test(line));
}

function isInsideDeveloperDetailsState(line, state) {
  if (line.includes('<details')) {
    state.inDetails = true;
    state.detailsIsDeveloper = false;
  }
  if (state.inDetails && DEVELOPER_DETAIL_MARKERS.some((marker) => line.includes(marker))) {
    state.detailsIsDeveloper = true;
  }
  return state.inDetails && state.detailsIsDeveloper;
}

function updateDeveloperDetailsState(line, state) {
  if (line.includes('</details>')) {
    state.inDetails = false;
    state.detailsIsDeveloper = false;
  }
}

function scanVisibleTerms({ lines, relativePath, terms, rule, hint }) {
  const findings = [];
  if (!relativePath.endsWith('.tsx')) {
    return findings;
  }

  const state = { inDetails: false, detailsIsDeveloper: false };
  lines.forEach((line, index) => {
    const inDeveloperDetails = isInsideDeveloperDetailsState(line, state);
    if (!inDeveloperDetails) {
      for (const term of terms) {
        if (line.includes(term) && isLikelyVisibleCopyLine(line, term)) {
          findings.push(makeFinding({
            rule,
            severity: 'warning',
            relativePath,
            line: index + 1,
            excerpt: line,
            hint,
          }));
          break;
        }
      }
    }
    updateDeveloperDetailsState(line, state);
  });

  return findings;
}

function scanNativeUi({ lines, relativePath }) {
  const findings = [];
  if (!relativePath.endsWith('.tsx')) {
    return findings;
  }

  lines.forEach((line, index) => {
    if (/\boverflow-(?:y-)?auto\b/.test(line) && !hasHiddenScrollbarStyle(line)) {
      findings.push(makeFinding({
        rule: 'native-ui',
        severity: 'warning',
        relativePath,
        line: index + 1,
        excerpt: line,
        hint: 'Visible scroll containers should use overflow-y-auto no-scrollbar.',
      }));
    }
  });

  for (const tag of collectOpeningTags(lines, ['input', 'button', 'select'])) {
    if (tag.name === 'select' && (!/className=/.test(tag.source) || !/\bappearance-none\b/.test(tag.source))) {
      findings.push(makeFinding({
        rule: 'native-ui',
        severity: 'warning',
        relativePath,
        line: tag.line,
        excerpt: tag.source.split(/\r?\n/)[0],
        hint: 'Select triggers should use ghost styles plus appearance-none, pr-10, and truncate.',
      }));
    }

    if ((tag.name === 'input' || tag.name === 'button') && !/className=/.test(tag.source)) {
      findings.push(makeFinding({
        rule: 'native-ui',
        severity: 'warning',
        relativePath,
        line: tag.line,
        excerpt: tag.source.split(/\r?\n/)[0],
        hint: 'Native controls need existing project primitives or explicit WolfyStock ghost styles.',
      }));
    }
  }

  return findings;
}

function hasHiddenScrollbarStyle(line) {
  return /\bno-scrollbar\b|\[scrollbar-width:none\]|\[&::?-webkit-scrollbar\]/.test(line);
}

function collectOpeningTags(lines, tagNames) {
  const tags = [];
  const tagRe = new RegExp(`<(${tagNames.join('|')})\\b`);

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const match = line.match(tagRe);
    if (!match) {
      continue;
    }

    const tagLines = [line];
    for (let next = index + 1; next < Math.min(lines.length, index + 24); next += 1) {
      if (tagLines.join('\n').includes('>')) {
        break;
      }
      tagLines.push(lines[next]);
    }
    tags.push({
      name: match[1],
      line: index + 1,
      source: tagLines.join('\n'),
    });
  }

  return tags;
}

function lineNumberForOffset(text, offset) {
  if (offset < 0) {
    return 1;
  }
  return text.slice(0, offset).split(/\r?\n/).length;
}

function normalizeCssValue(value) {
  return value.replace(/\s+/g, ' ').trim();
}

function collectCssVariableDeclarations(text, baseOffset = 0) {
  const declarations = [];
  const declarationRe = /(--[-\w]+)\s*:\s*([^;]+);/g;
  let match;
  while ((match = declarationRe.exec(text)) !== null) {
    declarations.push({
      token: match[1],
      value: normalizeCssValue(match[2]),
      raw: match[0],
      offset: baseOffset + match.index,
      line: lineNumberForOffset(text, match.index),
    });
  }
  return declarations;
}

function findCssBlockEnd(text, openBraceIndex) {
  let depth = 0;
  for (let index = openBraceIndex; index < text.length; index += 1) {
    const char = text[index];
    if (char === '{') {
      depth += 1;
    } else if (char === '}') {
      depth -= 1;
      if (depth === 0) {
        return index;
      }
    }
  }
  return -1;
}

function collectSelectorVariableDeclarations(text, selector) {
  const declarations = [];
  const selectorRe = new RegExp(`(^|\\n)\\s*${escapeRegExp(selector)}\\s*\\{`, 'g');
  let match;
  while ((match = selectorRe.exec(text)) !== null) {
    const openBraceIndex = match.index + match[0].lastIndexOf('{');
    const closeBraceIndex = findCssBlockEnd(text, openBraceIndex);
    if (closeBraceIndex < 0) {
      break;
    }
    const bodyStart = openBraceIndex + 1;
    const body = text.slice(bodyStart, closeBraceIndex);
    declarations.push(...collectCssVariableDeclarations(body, bodyStart));
    selectorRe.lastIndex = closeBraceIndex + 1;
  }
  return declarations;
}

function isLegacySharedTokenValue(token, value) {
  if (LEGACY_TOKEN_ALIAS_RE.test(value)) {
    return true;
  }
  if (/charcoal|spacex|cyberpunk|neon/i.test(value)) {
    return true;
  }
  if ((token === '--font-display' || token === '--theme-heading-font') && /var\(--font-(?:sans|stack-sans|ui)\)/i.test(value)) {
    return true;
  }
  if (WORKSPACE_TOKEN_NAMES.has(token) && (LEGACY_TOKEN_LITERAL_RE.test(value) || LEGACY_WORKSPACE_VALUE_RE.test(value))) {
    return true;
  }
  if ((token === '--wolfy-canvas' || token === '--wolfy-surface-console' || token === '--background' || token === '--foreground' || token === '--cohere-black' || token === '--cohere-white') && LEGACY_TOKEN_LITERAL_RE.test(value)) {
    return true;
  }
  return false;
}

function makeOldThemeDefaultFinding({ relativePath, text, declaration, excerpt }) {
  return makeFinding({
    rule: 'old-theme-default',
    severity: 'blocking',
    relativePath,
    line: declaration ? lineNumberForOffset(text, declaration.offset) : 1,
    excerpt: excerpt ?? declaration?.raw ?? 'missing canonical paper token declaration',
    hint: RULES.find((rule) => rule.id === 'old-theme-default').hint,
  });
}

function scanIndexCssTokenOwnership({ relativePath, text }) {
  const findings = [];
  const declarations = collectCssVariableDeclarations(text);

  for (const declaration of declarations) {
    if (!SHARED_TOKEN_NAMES.has(declaration.token)) {
      continue;
    }
    if (isLegacySharedTokenValue(declaration.token, declaration.value)) {
      findings.push(makeOldThemeDefaultFinding({
        relativePath,
        text,
        declaration,
      }));
    }
  }

  const declarationsBySelector = new Map();
  for (const requirement of PAPER_REQUIRED_DECLARATIONS) {
    if (!declarationsBySelector.has(requirement.selector)) {
      declarationsBySelector.set(requirement.selector, collectSelectorVariableDeclarations(text, requirement.selector));
    }
    const selectorDeclarations = declarationsBySelector.get(requirement.selector);
    const matchingDeclarations = selectorDeclarations.filter((declaration) => declaration.token === requirement.token);
    const hasExpectedDeclaration = matchingDeclarations.some((declaration) => requirement.expected.test(declaration.value));
    if (!hasExpectedDeclaration) {
      findings.push(makeOldThemeDefaultFinding({
        relativePath,
        text,
        declaration: matchingDeclarations[0],
        excerpt: matchingDeclarations[0]?.raw ?? requirement.excerpt,
      }));
    }
  }

  return findings;
}

function scanSharedPrimitivePaperMaterial({ lines, relativePath }) {
  const findings = [];
  if (!SHARED_PRIMITIVE_OWNER_PATHS.has(relativePath)) {
    return findings;
  }

  lines.forEach((line, index) => {
    if (SHARED_PRIMITIVE_LEGACY_MATERIAL_RE.test(line)) {
      findings.push(makeFinding({
        rule: 'shared-primitive-paper-material',
        severity: 'blocking',
        relativePath,
        line: index + 1,
        excerpt: line,
        hint: RULES.find((rule) => rule.id === 'shared-primitive-paper-material').hint,
      }));
    }
  });

  return findings;
}

export function scanSourceText({ relativePath, text }) {
  const blocking = [];
  const warnings = [];
  const lines = text.split(/\r?\n/);

  lines.forEach((line, index) => {
    for (const match of line.matchAll(SOLID_GRAY_BG_RE)) {
      blocking.push(makeFinding({
        rule: 'no-solid-gray-bg',
        severity: 'blocking',
        relativePath,
        line: index + 1,
        excerpt: match[0],
        hint: RULES.find((rule) => rule.id === 'no-solid-gray-bg').hint,
      }));
    }
    if (LEGACY_CONSUMER_THEME_RE.test(line)) {
      blocking.push(makeFinding({
        rule: 'legacy-consumer-theme',
        severity: 'blocking',
        relativePath,
        line: index + 1,
        excerpt: line,
        hint: RULES.find((rule) => rule.id === 'legacy-consumer-theme').hint,
      }));
    }
    if (DEAD_GLOW_HELPER_RE.test(line)) {
      blocking.push(makeFinding({
        rule: 'dead-glow-helper',
        severity: 'blocking',
        relativePath,
        line: index + 1,
        excerpt: line,
        hint: RULES.find((rule) => rule.id === 'dead-glow-helper').hint,
      }));
    }
    if (relativePath.endsWith('.css') && BROAD_UTILITY_NEUTRALIZER_RE.test(line)) {
      blocking.push(makeFinding({
        rule: 'broad-utility-neutralizer',
        severity: 'blocking',
        relativePath,
        line: index + 1,
        excerpt: line,
        hint: RULES.find((rule) => rule.id === 'broad-utility-neutralizer').hint,
      }));
    }
  });

  blocking.push(...scanSharedPrimitivePaperMaterial({ lines, relativePath }));

  if (relativePath === CONSUMER_SHELL_PATH && /\bTerminalPageShell\b/.test(text)) {
    blocking.push(makeFinding({
      rule: 'consumer-shell-terminal-lock-in',
      severity: 'blocking',
      relativePath,
      line: lineNumberForOffset(text, text.search(/\bTerminalPageShell\b/)),
      excerpt: 'TerminalPageShell',
      hint: RULES.find((rule) => rule.id === 'consumer-shell-terminal-lock-in').hint,
    }));
  }

  if (relativePath === 'src/index.css') {
    blocking.push(...scanIndexCssTokenOwnership({ relativePath, text }));
  }

  warnings.push(...scanVisibleTerms({
    lines,
    relativePath,
    terms: RAW_COPY_TERMS,
    rule: 'raw-debug-copy',
    hint: RULES.find((rule) => rule.id === 'raw-debug-copy').hint,
  }));
  warnings.push(...scanVisibleTerms({
    lines,
    relativePath,
    terms: LOCALIZED_COPY_TERMS,
    rule: 'localized-ui-copy',
    hint: RULES.find((rule) => rule.id === 'localized-ui-copy').hint,
  }));
  warnings.push(...scanNativeUi({ lines, relativePath }));

  return { blocking, warnings };
}

export function scanProject({ rootDir = ROOT_DIR, files = null } = {}) {
  const scanFiles = files ?? listProjectSourceFiles(rootDir);
  const result = {
    filesScanned: 0,
    blocking: [],
    warnings: [],
  };

  for (const file of scanFiles) {
    const relativePath = path.relative(rootDir, file);
    const text = fs.readFileSync(file, 'utf8');
    const fileResult = scanSourceText({ relativePath, text });
    result.filesScanned += 1;
    result.blocking.push(...fileResult.blocking);
    result.warnings.push(...fileResult.warnings);
  }

  return result;
}

function printFindings(title, findings) {
  if (findings.length === 0) {
    return;
  }

  const limit = 30;
  console.log(`\n${title} (${findings.length})`);
  for (const finding of findings.slice(0, limit)) {
    console.log(`- ${finding.file}:${finding.line} [${finding.rule}] ${finding.excerpt}`);
    console.log(`  ${finding.hint}`);
  }
  if (findings.length > limit) {
    console.log(`- ... ${findings.length - limit} more finding(s) omitted; rerun after addressing the first batch.`);
  }
}

function printReport(result) {
  console.log('WolfyStock design constitution guard');
  console.log(`Rules checked: ${RULES.map((rule) => `${rule.id} (${rule.severity})`).join(', ')}`);
  console.log(`Files scanned: ${result.filesScanned}`);

  printFindings('Blocking violations', result.blocking);
  printFindings('Design warnings', result.warnings);

  if (result.blocking.length > 0) {
    console.log('\nDesign guard failed. Fix blocking violations before merging.');
    return;
  }

  if (result.warnings.length > 0) {
    console.log('\nDesign guard passed with warnings. Review warning-only items during visual QA.');
    return;
  }

  console.log('\nDesign guard passed. No blocking violations or warnings found.');
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function parseCliArgs(argv) {
  const result = {
    help: false,
    files: [],
    filesFrom: [],
    hasFileLimit: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '-h' || arg === '--help') {
      result.help = true;
      continue;
    }
    if (arg === '--files-from') {
      const value = argv[index + 1];
      if (!value) {
        throw new Error('--files-from requires a path');
      }
      result.filesFrom.push(value);
      result.hasFileLimit = true;
      index += 1;
      continue;
    }
    if (arg === '--files') {
      result.hasFileLimit = true;
      for (let next = index + 1; next < argv.length; next += 1) {
        if (argv[next].startsWith('-')) {
          index = next - 1;
          break;
        }
        result.files.push(argv[next]);
        index = next;
      }
      continue;
    }
    throw new Error(`unknown argument: ${arg}`);
  }

  return result;
}

function isMissingPythonCommand(result) {
  const output = `${result.stdout || ''}\n${result.stderr || ''}`;
  return result.error?.code === 'ENOENT'
    || result.status === 9009
    || output.includes('Python was not found');
}

function runPythonGuard(pythonArgs) {
  const commands = ['python3', 'python'];
  let lastResult = null;

  for (const command of commands) {
    const result = spawnSync(command, pythonArgs, {
      cwd: path.resolve(ROOT_DIR, '..', '..'),
      encoding: 'utf8',
      stdio: 'pipe',
    });
    lastResult = result;
    if (isMissingPythonCommand(result)) {
      continue;
    }
    return result;
  }

  return lastResult;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  let cli;
  try {
    cli = parseCliArgs(process.argv.slice(2));
  } catch (error) {
    console.error(`[design-guard] ${error.message}`);
    printHelp();
    process.exit(2);
  }

  if (cli.help) {
    printHelp();
    process.exit(0);
  }

  const limitedFiles = cli.hasFileLimit ? listLimitedSourceFiles(cli) : null;
  const result = scanProject({ files: limitedFiles });
  printReport(result);
  const pythonGuard = path.resolve(ROOT_DIR, '..', '..', 'scripts', 'check_frontend_design_constitution.py');
  let pythonExitCode = 0;
  if (fs.existsSync(pythonGuard)) {
    const pythonArgs = [pythonGuard];
    if (limitedFiles) {
      pythonArgs.push(
        '--files',
        ...limitedFiles.map((file) => path.join('apps/dsa-web', path.relative(ROOT_DIR, file)).split(path.sep).join('/')),
      );
    }
    const pythonResult = runPythonGuard(pythonArgs);
    if (pythonResult.stdout) {
      process.stdout.write(`\n${pythonResult.stdout}`);
    }
    if (pythonResult.stderr) {
      process.stderr.write(pythonResult.stderr);
    }
    pythonExitCode = pythonResult.status ?? 1;
  }
  process.exitCode = result.blocking.length > 0 || pythonExitCode > 0 ? 1 : 0;
}
