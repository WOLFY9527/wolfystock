import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = path.resolve(SCRIPT_DIR, '..');
const SRC_DIR = path.join(ROOT_DIR, 'src');

const SCANNED_EXTENSIONS = new Set(['.tsx', '.ts', '.css']);
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
];

const SOLID_GRAY_BG_RE = /\bbg-(?:gray|zinc|slate|neutral)-[A-Za-z0-9[\]_/.-]+/g;

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
  });

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
  const sourceDir = path.join(rootDir, 'src');
  const scanFiles = files ?? listSourceFiles(sourceDir);
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
