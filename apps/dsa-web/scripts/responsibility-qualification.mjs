import fs from 'node:fs';
import path from 'node:path';

import * as ts from 'typescript';

const RESPONSIBILITY_ORDER = [
  'route-composition',
  'presentation',
  'state-ownership',
  'effect-ownership',
  'request-orchestration',
  'stale-response-protection',
  'truth-projection',
  'domain-calculation',
  'cross-domain-dependency',
];

const BOUNDED_SIGNAL_KEYS = [
  'stateCalls',
  'effects',
  'apiCalls',
  'effectApiCalls',
  'truthCalls',
  'domainCalls',
];

const STALE_PROTECTION_STATUSES = new Set(['observed', 'not-observed', 'not-applicable']);
const API_PATH_RE = /(?:^|\/)api(?:\/|$)/;
const TRUTH_PATH_RE = /(?:^|\/)(?:productReadModelView|consumerDataQualityViewModel|consumerPresentationBoundary|evidenceDisplay|displayStatus|consumerDataStateVocabulary|consumerStatusLabels|dataTrustEvidenceDisplay|trustDisclosure|researchQueueConsumerCopy|marketIntelligenceGuidance)(?:\.|\/|$)/i;
const DOMAIN_CALL_RE = /^(?:calculate|compute|derive|normalize|aggregate|summarize|score|rank|select|build|resolve|map|project)/i;
const TRUTH_NAME_RE = /(?:readiness|freshness|provenance|authority|availability|dataState|evidenceQuality|consumerStatus|trust)/i;
const STALE_GUARD_BASES = new Set([
  'cancelled',
  'canceled',
  'active',
  'mounted',
  'alive',
  'ignored',
  'stale',
  'requestid',
  'requestkey',
  'requesttoken',
  'requestsequence',
  'sequence',
  'inflight',
  'activerequest',
]);
const REQUEST_NAME_RE = /^(?:get|fetch|load|request|run|create|update|delete|remove|save|sync|submit|execute|start|stop|search|list|post|put|patch|upload|import|export)[A-Z_]/;
const API_HELPER_MODULE_RE = /(?:^|\/)(?:error|path|reportNormalizer|researchReadiness)$/i;
const API_HELPER_NAME_RE = /^(?:build|normalize|extract|infer|format|parse|is|has|to|from|read|map)(?:[A-Z_]|$)/;
const TRUTH_HELPER_NAME_RE = /(?:consumer|readiness|freshness|provenance|authority|availability|dataState|evidence|status|trust)/i;

function normalizePath(relativePath) {
  return relativePath.split(path.sep).join('/').replace(/^\.\//, '');
}

function compareText(left, right) {
  return left < right ? -1 : left > right ? 1 : 0;
}

function isTestPath(relativePath) {
  const normalized = normalizePath(relativePath);
  return normalized.split('/').includes('__tests__')
    || /(?:^|\/)[^/]+\.test\.[cm]?[jt]sx?$/.test(normalized)
    || /(?:^|\/)[^/]+\.spec\.[cm]?[jt]sx?$/.test(normalized);
}

function isGeneratedPath(relativePath) {
  return normalizePath(relativePath).split('/').some((part) => part === 'generated');
}

export function classifyResponsibilityOwner(relativePath) {
  const normalized = normalizePath(relativePath);
  if (isTestPath(normalized)) {
    return { kind: 'test', production: false };
  }
  if (isGeneratedPath(normalized)) {
    return { kind: 'generated', production: false };
  }
  if (!/\.(?:ts|tsx)$/.test(normalized)) {
    return { kind: 'non-typescript', production: false };
  }
  if (/(?:^|\/)pages\/[^/]+Page\.tsx$/.test(normalized)) {
    return { kind: 'route-page', production: true };
  }
  if (/(?:^|\/)api\//.test(normalized)) {
    return { kind: 'api-transport', production: true };
  }
  const basename = normalized.split('/').pop() ?? '';
  if (/(?:^|\/)hooks\//.test(normalized) || /^use[A-Z]/.test(basename) || /Controller\.(?:ts|tsx)$/.test(basename)) {
    return { kind: 'controller', production: true };
  }
  if (/(?:^|\/)components\//.test(normalized) && normalized.endsWith('.tsx')) {
    return { kind: 'presentation-component', production: true };
  }
  if (/(?:^|\/)types\//.test(normalized)) {
    return { kind: 'schema', production: true };
  }
  if (/(?:^|\/)stores\//.test(normalized)) {
    return { kind: 'state-store', production: true };
  }
  if (/(?:^|\/)contexts\//.test(normalized)) {
    return { kind: 'context', production: true };
  }
  return { kind: 'shared-module', production: true };
}

function sourceModuleName(moduleSpecifier) {
  return moduleSpecifier.replace(/\\/g, '/').replace(/\.([cm]?[jt]sx?)$/, '');
}

function domainFromModule(moduleSpecifier) {
  const segments = sourceModuleName(moduleSpecifier)
    .replace(/([a-z0-9])([A-Z])/g, '$1-$2')
    .toLowerCase()
    .split('/');
  for (const segment of segments) {
    if (segment === 'market' || segment.startsWith('market-') || segment === 'liquidity-monitor') {
      return 'market';
    }
    if (segment === 'system-config' || segment === 'settings') {
      return 'settings';
    }
    for (const domain of ['admin', 'auth', 'backtest', 'options', 'portfolio', 'research', 'scanner', 'scenario', 'watchlist']) {
      if (segment === domain || segment.startsWith(`${domain}-`)) {
        return domain;
      }
    }
  }
  return null;
}

function isApiModule(moduleSpecifier) {
  return API_PATH_RE.test(sourceModuleName(moduleSpecifier));
}

function isTruthModule(moduleSpecifier) {
  return TRUTH_PATH_RE.test(sourceModuleName(moduleSpecifier));
}

function isRequestLikeName(name, moduleSpecifier) {
  const moduleName = sourceModuleName(moduleSpecifier);
  if (API_HELPER_MODULE_RE.test(moduleName) || API_HELPER_NAME_RE.test(name)) {
    return false;
  }
  return REQUEST_NAME_RE.test(name);
}

function isRequestLikeProperty(name) {
  return !/^(?:normalize|format|infer|extract|is|has|to|from)(?:[A-Z_]|$)/.test(name)
    && !/(?:Url|Path)$/.test(name);
}

function isRelativeModule(moduleSpecifier) {
  return moduleSpecifier.startsWith('.') || moduleSpecifier.startsWith('/');
}

function addBinding(map, localName, metadata) {
  if (localName) {
    map.set(localName, metadata);
  }
}

function collectImports(sourceFile) {
  const bindings = new Map();
  const hookNames = new Set(['useState', 'useReducer', 'useEffect', 'useLayoutEffect', 'useRef']);
  const apiNamespaces = new Set();
  const apiImports = new Set();
  const truthImports = new Set();
  const reactNamespaces = new Set();
  const domainImports = new Map();
  const dependencies = new Set();

  for (const statement of sourceFile.statements) {
    if (!ts.isImportDeclaration(statement) || !ts.isStringLiteral(statement.moduleSpecifier)) {
      continue;
    }
    const moduleSpecifier = statement.moduleSpecifier.text;
    const moduleName = sourceModuleName(moduleSpecifier);
    const apiModule = isApiModule(moduleSpecifier);
    const truthModule = isTruthModule(moduleSpecifier);
    const domain = domainFromModule(moduleSpecifier);
    if (domain && isRelativeModule(moduleSpecifier)) {
      dependencies.add(domain);
    }
    const clause = statement.importClause;
    if (!clause) {
      continue;
    }
    if (clause.isTypeOnly) {
      continue;
    }
    if (clause.name) {
      const local = clause.name.text;
      const kind = apiModule
        ? (local.endsWith('Api') ? 'api-namespace' : isRequestLikeName(local, moduleSpecifier) ? 'api' : 'other')
        : truthModule ? 'truth' : moduleName === 'react' ? 'react-namespace' : 'other';
      addBinding(bindings, local, { kind, moduleName });
      if (kind === 'react-namespace') {
        reactNamespaces.add(local);
      }
      if (apiModule) {
        apiImports.add(local);
        if (kind === 'api-namespace') {
          apiNamespaces.add(local);
        }
      }
      if (truthModule) {
        truthImports.add(local);
      }
      if (domain) {
        domainImports.set(local, { domain, moduleName });
      }
    }
    if (!clause.namedBindings) {
      continue;
    }
    if (ts.isNamespaceImport(clause.namedBindings)) {
      const local = clause.namedBindings.name.text;
      const kind = apiModule ? 'api-namespace' : truthModule ? 'truth-namespace' : moduleName === 'react' ? 'react-namespace' : 'other';
      addBinding(bindings, local, { kind, moduleName });
      if (kind === 'react-namespace') {
        reactNamespaces.add(local);
      }
      if (apiModule) {
        apiNamespaces.add(local);
        apiImports.add(local);
      }
      if (truthModule) {
        truthImports.add(local);
      }
      if (domain) {
        domainImports.set(local, { domain, moduleName });
      }
      continue;
    }
    for (const element of clause.namedBindings.elements) {
      const local = element.name.text;
      const imported = element.propertyName?.text ?? element.name.text;
      let kind = 'other';
      if (apiModule && (local.endsWith('Api') || imported.endsWith('Api'))) {
        kind = 'api-namespace';
        apiNamespaces.add(local);
        apiImports.add(local);
      } else if (apiModule && (isRequestLikeName(imported, moduleSpecifier) || isRequestLikeName(local, moduleSpecifier))) {
        kind = 'api';
        apiImports.add(local);
      } else if (apiModule) {
        apiImports.add(local);
        if (TRUTH_HELPER_NAME_RE.test(imported) || TRUTH_HELPER_NAME_RE.test(local)) {
          kind = 'truth';
          truthImports.add(local);
        }
      } else if (truthModule) {
        kind = 'truth';
        truthImports.add(local);
      } else if (moduleName === 'react' && hookNames.has(imported)) {
        kind = 'hook';
      }
      addBinding(bindings, local, { kind, imported, moduleName });
      if (domain) {
        domainImports.set(local, { domain, moduleName });
      }
    }
  }

  return { bindings, hookNames, reactNamespaces, apiNamespaces, apiImports, truthImports, domainImports, dependencies };
}

function propertyRootAndName(expression) {
  if (!ts.isPropertyAccessExpression(expression)) {
    return null;
  }
  let root = expression.expression;
  while (ts.isPropertyAccessExpression(root)) {
    root = root.expression;
  }
  return {
    root: ts.isIdentifier(root) ? root.text : null,
    property: expression.name.text,
  };
}

function isHookCall(expression, imports) {
  if (ts.isIdentifier(expression)) {
    const binding = imports.bindings.get(expression.text);
    return binding?.kind === 'hook' ? binding.imported : null;
  }
  const property = propertyRootAndName(expression);
  if (property && imports.reactNamespaces.has(property.root) && imports.hookNames.has(property.property)) {
    return property.property;
  }
  return null;
}

function isFunctionLikeNode(node) {
  return ts.isArrowFunction(node) || ts.isFunctionExpression(node) || ts.isFunctionDeclaration(node);
}

function guardTarget(expression) {
  if (ts.isIdentifier(expression)) {
    return expression.text;
  }
  if (ts.isPropertyAccessExpression(expression)
      && expression.name.text === 'current'
      && ts.isIdentifier(expression.expression)) {
    return expression.expression.text;
  }
  return null;
}

function isStaleGuardName(name) {
  const normalized = name.replace(/_/g, '').toLowerCase();
  const withoutIs = normalized.startsWith('is') ? normalized.slice(2) : normalized;
  const withoutRef = withoutIs.endsWith('ref') ? withoutIs.slice(0, -3) : withoutIs;
  return STALE_GUARD_BASES.has(withoutRef);
}

function isBooleanLiteral(node) {
  return node.kind === ts.SyntaxKind.TrueKeyword || node.kind === ts.SyntaxKind.FalseKeyword;
}

function isGuardInitializer(node) {
  if (isBooleanLiteral(node)) {
    return true;
  }
  if (!ts.isObjectLiteralExpression(node)) {
    return false;
  }
  return node.properties.some((property) => (
    ts.isPropertyAssignment(property)
    && property.name.getText() === 'current'
    && isBooleanLiteral(property.initializer)
  ));
}

function collectConditionalIdentifiers(node, names) {
  if (ts.isIdentifier(node)) {
    names.add(node.text);
  }
  ts.forEachChild(node, (child) => collectConditionalIdentifiers(child, names));
}

const ASSIGNMENT_OPERATOR_KINDS = new Set([
  ts.SyntaxKind.EqualsToken,
  ts.SyntaxKind.PlusEqualsToken,
  ts.SyntaxKind.MinusEqualsToken,
  ts.SyntaxKind.AsteriskEqualsToken,
  ts.SyntaxKind.SlashEqualsToken,
  ts.SyntaxKind.PercentEqualsToken,
  ts.SyntaxKind.AmpersandEqualsToken,
  ts.SyntaxKind.BarEqualsToken,
  ts.SyntaxKind.CaretEqualsToken,
  ts.SyntaxKind.LessThanLessThanEqualsToken,
  ts.SyntaxKind.GreaterThanGreaterThanEqualsToken,
  ts.SyntaxKind.GreaterThanGreaterThanGreaterThanEqualsToken,
  ts.SyntaxKind.QuestionQuestionEqualsToken,
]);

function analyzeEffectProtection(callback) {
  const guardDeclarations = new Set();
  const guardChecks = new Set();
  const guardMutations = new Set();
  const abortControllers = new Set();
  const abortCalls = new Set();
  const cleanupFunctions = [];
  const cleanupFunctionSet = new Set();

  function addCleanupFunction(cleanup) {
    cleanupFunctions.push(cleanup);
    cleanupFunctionSet.add(cleanup);
  }

  function visitOwnedDeclarations(node) {
    if (node !== callback.body && isFunctionLikeNode(node)) {
      return;
    }
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name)) {
      if (node.initializer && isStaleGuardName(node.name.text) && isGuardInitializer(node.initializer)) {
        guardDeclarations.add(node.name.text);
      }
      if (node.initializer
          && ts.isNewExpression(node.initializer)
          && ts.isIdentifier(node.initializer.expression)
          && node.initializer.expression.text === 'AbortController') {
        abortControllers.add(node.name.text);
      }
    }
    ts.forEachChild(node, visitOwnedDeclarations);
  }

  function visitChecks(node, nestedFunctionDepth = 0) {
    if (cleanupFunctionSet.has(node)) {
      return;
    }
    const nextDepth = isFunctionLikeNode(node) ? nestedFunctionDepth + 1 : nestedFunctionDepth;
    if (nestedFunctionDepth > 0 && ts.isIfStatement(node)) {
      collectConditionalIdentifiers(node.expression, guardChecks);
    } else if (nestedFunctionDepth > 0 && ts.isConditionalExpression(node)) {
      collectConditionalIdentifiers(node.condition, guardChecks);
    } else if (nestedFunctionDepth > 0 && (ts.isWhileStatement(node) || ts.isDoStatement(node))) {
      collectConditionalIdentifiers(node.expression, guardChecks);
    } else if (nestedFunctionDepth > 0 && ts.isForStatement(node) && node.condition) {
      collectConditionalIdentifiers(node.condition, guardChecks);
    } else if (nestedFunctionDepth > 0 && ts.isSwitchStatement(node)) {
      collectConditionalIdentifiers(node.expression, guardChecks);
    }
    ts.forEachChild(node, (child) => visitChecks(child, nextDepth));
  }

  function visitCleanupReturns(node) {
    if (ts.isReturnStatement(node) && node.expression && isFunctionLikeNode(node.expression)) {
      addCleanupFunction(node.expression);
      return;
    }
    if (isFunctionLikeNode(node)) {
      return;
    }
    ts.forEachChild(node, visitCleanupReturns);
  }

  function visitCleanup(node) {
    if (ts.isBinaryExpression(node) && ASSIGNMENT_OPERATOR_KINDS.has(node.operatorToken.kind)) {
      const target = guardTarget(node.left);
      if (target && isStaleGuardName(target)) {
        guardMutations.add(target);
      }
    }
    if (ts.isPrefixUnaryExpression(node) || ts.isPostfixUnaryExpression(node)) {
      const target = guardTarget(node.operand);
      if (target && isStaleGuardName(target)) {
        guardMutations.add(target);
      }
    }

    if (ts.isCallExpression(node)) {
      const property = propertyRootAndName(node.expression);
      if (property?.property === 'abort' && property.root) {
        abortCalls.add(property.root);
      }
    }
    ts.forEachChild(node, visitCleanup);
  }

  visitOwnedDeclarations(callback.body);
  if (isFunctionLikeNode(callback.body)) {
    addCleanupFunction(callback.body);
  } else {
    visitCleanupReturns(callback.body);
  }
  visitChecks(callback.body);
  for (const cleanup of cleanupFunctions) {
    visitCleanup(cleanup);
  }

  const guardedNames = [...guardDeclarations].filter((name) => guardChecks.has(name) && guardMutations.has(name));
  const abortedControllers = [...abortControllers].filter((name) => abortCalls.has(name));
  return {
    protected: guardedNames.length > 0 || abortedControllers.length > 0,
    evidence: guardedNames.length + (abortedControllers.length * 2),
  };
}

function hasConditionalBody(node) {
  let result = false;
  function visit(child) {
    if (result) {
      return;
    }
    if (ts.isIfStatement(child) || ts.isSwitchStatement(child) || ts.isConditionalExpression(child)) {
      result = true;
      return;
    }
    ts.forEachChild(child, visit);
  }
  visit(node);
  return result;
}

function collectLocalSemanticNames(sourceFile) {
  const truth = [];
  const domain = [];
  function visit(node) {
    if (ts.isFunctionDeclaration(node) && node.name) {
      if (TRUTH_NAME_RE.test(node.name.text) && hasConditionalBody(node.body)) {
        truth.push(node.name.text);
      }
      if (DOMAIN_CALL_RE.test(node.name.text) && hasConditionalBody(node.body)) {
        domain.push(node.name.text);
      }
    }
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) {
      if (TRUTH_NAME_RE.test(node.name.text) && hasConditionalBody(node.initializer)) {
        truth.push(node.name.text);
      }
      if (DOMAIN_CALL_RE.test(node.name.text) && hasConditionalBody(node.initializer)) {
        domain.push(node.name.text);
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(sourceFile);
  return { truth, domain };
}

function parseSourceFile(relativePath, text) {
  const scriptKind = relativePath.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
  const sourceFile = ts.createSourceFile(relativePath, text, ts.ScriptTarget.Latest, true, scriptKind);
  const diagnostics = sourceFile.parseDiagnostics ?? [];
  if (diagnostics.length > 0) {
    const detail = diagnostics.map((diagnostic) => ts.flattenDiagnosticMessageText(diagnostic.messageText, ' ')).join('; ');
    const error = new Error(`TypeScript parse failed for ${relativePath}: ${detail}`);
    error.code = 'RESPONSIBILITY_PARSE_ERROR';
    error.diagnostics = diagnostics;
    throw error;
  }
  return sourceFile;
}

export function analyzeResponsibilitySource({ relativePath, text }) {
  const normalizedPath = normalizePath(relativePath);
  const owner = classifyResponsibilityOwner(normalizedPath);
  if (!owner.production) {
    return {
      path: normalizedPath,
      ownerKind: owner.kind,
      production: false,
      responsibilities: [],
      dependencies: [],
      signals: {
        stateCalls: 0,
        effects: 0,
        apiImports: 0,
        apiCalls: 0,
        effectApiCalls: 0,
        truthCalls: 0,
        domainCalls: 0,
        jsxNodes: 0,
        staleProtection: { status: 'not-applicable', evidence: 0 },
      },
    };
  }

  const sourceFile = parseSourceFile(normalizedPath, text);
  const imports = collectImports(sourceFile);
  const localSemanticNames = collectLocalSemanticNames(sourceFile);
  const signals = {
    stateCalls: 0,
    effects: 0,
    apiImports: imports.apiImports.size,
    apiCalls: 0,
    effectApiCalls: 0,
    truthCalls: 0,
    domainCalls: 0,
    jsxNodes: 0,
    staleEvidence: 0,
  };
  const effectProtectionStatuses = [];

  function visit(node, effectContext = null) {
    if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node) || ts.isJsxFragment(node)) {
      signals.jsxNodes += 1;
    }
    if (ts.isCallExpression(node)) {
      const hook = isHookCall(node.expression, imports);
      if (hook === 'useState' || hook === 'useReducer') {
        signals.stateCalls += 1;
      }
      if (hook === 'useEffect' || hook === 'useLayoutEffect') {
        signals.effects += 1;
        const callback = node.arguments[0];
        if (callback && isFunctionLikeNode(callback)) {
          const nestedEffectContext = { apiCalls: 0 };
          visit(callback, nestedEffectContext);
          const protection = analyzeEffectProtection(callback);
          signals.staleEvidence += protection.evidence;
          if (nestedEffectContext.apiCalls > 0) {
            signals.effectApiCalls += nestedEffectContext.apiCalls;
            effectProtectionStatuses.push(protection.protected);
          }
        } else if (callback) {
          visit(callback);
        }
        for (const argument of node.arguments.slice(1)) {
          visit(argument);
        }
        return;
      }

      let apiCall = false;
      if (ts.isIdentifier(node.expression)) {
        const binding = imports.bindings.get(node.expression.text);
        if (binding?.kind === 'api' || binding?.kind === 'api-namespace' || node.expression.text === 'fetch') {
          signals.apiCalls += 1;
          apiCall = true;
        }
        if (binding?.kind === 'truth') {
          signals.truthCalls += 1;
        }
        const domainBinding = imports.domainImports.get(node.expression.text);
        if (domainBinding && DOMAIN_CALL_RE.test(binding?.imported ?? node.expression.text)) {
          signals.domainCalls += 1;
        }
      } else {
        const property = propertyRootAndName(node.expression);
        if (property && imports.apiNamespaces.has(property.root) && isRequestLikeProperty(property.property)) {
          signals.apiCalls += 1;
          apiCall = true;
        }
        if (property && imports.truthImports.has(property.root)) {
          signals.truthCalls += 1;
        }
        if (property && imports.domainImports.has(property.root) && DOMAIN_CALL_RE.test(property.property)) {
          signals.domainCalls += 1;
        }
      }
      if (apiCall && effectContext) {
        effectContext.apiCalls += 1;
      }
    }
    ts.forEachChild(node, (child) => visit(child, effectContext));
  }
  visit(sourceFile);

  signals.truthCalls += localSemanticNames.truth.length;
  signals.domainCalls += localSemanticNames.domain.length;
  const staleStatus = signals.effectApiCalls === 0
    ? 'not-applicable'
    : effectProtectionStatuses.length > 0 && effectProtectionStatuses.every(Boolean)
      ? 'observed'
      : 'not-observed';
  const staleProtection = { status: staleStatus, evidence: signals.staleEvidence };
  const dependencies = [...imports.dependencies].sort();
  const responsibilities = [];
  if (owner.kind === 'route-page' && signals.jsxNodes > 0) responsibilities.push('route-composition');
  if (signals.jsxNodes > 0) responsibilities.push('presentation');
  if (signals.stateCalls > 0) responsibilities.push('state-ownership');
  if (signals.effects > 0) responsibilities.push('effect-ownership');
  if (signals.apiCalls > 0) responsibilities.push('request-orchestration');
  if (staleStatus === 'observed') responsibilities.push('stale-response-protection');
  if (signals.truthCalls > 0) responsibilities.push('truth-projection');
  if (signals.domainCalls > 0) responsibilities.push('domain-calculation');
  if (dependencies.length > 1) responsibilities.push('cross-domain-dependency');

  return {
    path: normalizedPath,
    ownerKind: owner.kind,
    production: true,
    responsibilities: RESPONSIBILITY_ORDER.filter((item) => responsibilities.includes(item)),
    dependencies,
    signals: {
      ...signals,
      staleProtection,
    },
  };
}

function finding(rule, analysis, extra = {}) {
  return {
    rule,
    file: analysis.path,
    line: 1,
    excerpt: Array.isArray(analysis.responsibilities)
      ? analysis.responsibilities.join(', ') || 'no responsibility signals observed'
      : 'responsibility analysis incomplete',
    ...extra,
  };
}

function responsibilityCompletenessFindings(analysis) {
  const findings = [];
  if (!Array.isArray(analysis.responsibilities)) {
    findings.push(finding('responsibility-analysis-incomplete', analysis, {
      signal: 'responsibilities',
      actual: analysis.responsibilities ?? 'missing',
      hint: 'Missing responsibility classification is blocking and is never interpreted as an empty owner.',
    }));
  }
  if (!Array.isArray(analysis.dependencies)) {
    findings.push(finding('responsibility-analysis-incomplete', analysis, {
      signal: 'dependencies',
      actual: analysis.dependencies ?? 'missing',
      hint: 'Missing dependency classification is blocking and is never interpreted as no coupling.',
    }));
  }
  for (const signal of BOUNDED_SIGNAL_KEYS) {
    const actual = analysis.signals?.[signal];
    if (!Number.isInteger(actual) || actual < 0) {
      findings.push(finding('responsibility-analysis-incomplete', analysis, {
        signal,
        actual: actual ?? 'missing',
        hint: 'Missing or invalid analysis signals are blocking and are never interpreted as zero responsibility.',
      }));
    }
  }
  const staleProtection = analysis.signals?.staleProtection;
  if (!staleProtection || !STALE_PROTECTION_STATUSES.has(staleProtection.status)) {
    findings.push(finding('responsibility-analysis-incomplete', analysis, {
      signal: 'staleProtection',
      actual: staleProtection?.status ?? 'missing',
      hint: 'Missing stale-response analysis is blocking and is never interpreted as not applicable.',
    }));
  }
  return findings;
}

export function qualifyResponsibilityAnalysis(analysis, { boundary = null } = {}) {
  if (!analysis.production) {
    return [];
  }
  const findings = responsibilityCompletenessFindings(analysis);
  if (findings.length > 0) {
    return findings;
  }
  const has = (responsibility) => analysis.responsibilities.includes(responsibility);
  const isLegacy = boundary?.profile === 'legacy-concentrated' || boundary?.profile === 'cohesive-owner';

  if (analysis.ownerKind === 'presentation-component' && has('request-orchestration') && !isLegacy) {
    findings.push(finding('presentation-orchestration-mix', analysis, {
      hint: 'Presentation components must consume controller/view-model outputs; move API orchestration to a controller owner.',
    }));
  }
  if (analysis.signals.effectApiCalls > 0 && analysis.signals.staleProtection.status === 'not-observed' && !isLegacy) {
    findings.push(finding('unguarded-effect-request', analysis, {
      hint: 'Effect-owned requests need observable cancellation or stale-response protection; analysis is not treated as zero.',
    }));
  }
  if (analysis.ownerKind === 'route-page' && !isLegacy) {
    if (has('state-ownership') && analysis.signals.effectApiCalls > 0) {
      findings.push(finding('route-request-lifecycle-concentration', analysis, {
        hint: 'Keep route composition separate from state/effect/request lifecycle ownership in a controller or hook.',
      }));
    }
    if (has('request-orchestration') && (has('truth-projection') || has('domain-calculation')) && has('presentation')) {
      findings.push(finding('route-projection-presentation-concentration', analysis, {
        hint: 'Pages compose consumer view models; request, truth projection, and domain calculation belong to their existing owners.',
      }));
    }
  }
  return findings;
}

function validateSignalMap(maxSignals) {
  if (!maxSignals || typeof maxSignals !== 'object' || Array.isArray(maxSignals)) {
    throw new Error('maxSignals must be an object');
  }
  for (const [signal, value] of Object.entries(maxSignals)) {
    if (!BOUNDED_SIGNAL_KEYS.includes(signal) || !Number.isInteger(value) || value < 0) {
      throw new Error(`invalid maxSignals.${signal}`);
    }
  }
  const missingSignals = BOUNDED_SIGNAL_KEYS.filter((signal) => !(signal in maxSignals));
  if (missingSignals.length > 0) {
    throw new Error(`maxSignals is missing ${missingSignals.join(', ')}`);
  }
}

export function validateResponsibilityManifest(manifest, { knownFiles = null } = {}) {
  if (!manifest || typeof manifest !== 'object' || manifest.schemaVersion !== 1 || !Array.isArray(manifest.owners)) {
    throw new Error('responsibility manifest must declare schemaVersion 1 and owners');
  }
  if (manifest.signalModel !== 'frontend-responsibility-signals-v1') {
    throw new Error('responsibility manifest requires signalModel frontend-responsibility-signals-v1');
  }
  if (!manifest.acceptedBase
      || !/^[0-9a-f]{40}$/.test(manifest.acceptedBase.commit ?? '')
      || !/^[0-9a-f]{40}$/.test(manifest.acceptedBase.tree ?? '')) {
    throw new Error('responsibility manifest requires acceptedBase commit and tree identities');
  }
  const seen = new Set();
  let previousPath = null;
  for (const owner of manifest.owners) {
    if (!owner || typeof owner !== 'object' || typeof owner.path !== 'string') {
      throw new Error('owner path is required');
    }
    const normalized = normalizePath(owner.path);
    if (normalized !== owner.path) {
      throw new Error(`owner path must be normalized: ${owner.path}`);
    }
    if (seen.has(normalized)) {
      throw new Error(`duplicate owner ${normalized}`);
    }
    if (previousPath !== null && normalized < previousPath) {
      throw new Error(`owners must be lexically sorted: ${normalized} follows ${previousPath}`);
    }
    seen.add(normalized);
    previousPath = normalized;
    if (!owner.maxSignals || !Array.isArray(owner.allowedResponsibilities) || !Array.isArray(owner.allowedDependencies)) {
      throw new Error(`owner ${normalized} requires maxSignals, allowedResponsibilities, and allowedDependencies`);
    }
    validateSignalMap(owner.maxSignals);
    if (owner.allowedResponsibilities.some((item) => !RESPONSIBILITY_ORDER.includes(item))
        || new Set(owner.allowedResponsibilities).size !== owner.allowedResponsibilities.length) {
      throw new Error(`owner ${normalized} has invalid allowedResponsibilities`);
    }
    const orderedResponsibilities = RESPONSIBILITY_ORDER.filter((item) => owner.allowedResponsibilities.includes(item));
    if (orderedResponsibilities.some((item, index) => item !== owner.allowedResponsibilities[index])) {
      throw new Error(`owner ${normalized} allowedResponsibilities must follow semantic order`);
    }
    if (owner.allowedDependencies.some((item) => typeof item !== 'string' || !/^[a-z][a-z0-9-]*$/.test(item))
        || new Set(owner.allowedDependencies).size !== owner.allowedDependencies.length
        || owner.allowedDependencies.some((item, index) => index > 0 && item < owner.allowedDependencies[index - 1])) {
      throw new Error(`owner ${normalized} has invalid or unsorted allowedDependencies`);
    }
    if (!STALE_PROTECTION_STATUSES.has(owner.staleProtection)) {
      throw new Error(`owner ${normalized} has invalid staleProtection`);
    }
    if (!['legacy-concentrated', 'cohesive-owner'].includes(owner.profile)) {
      throw new Error(`owner ${normalized} has invalid profile`);
    }
    if (typeof owner.rationale !== 'string' || owner.rationale.trim() === '' || typeof owner.retirementCondition !== 'string' || owner.retirementCondition.trim() === '') {
      throw new Error(`owner ${normalized} requires rationale and retirementCondition`);
    }
    const classified = classifyResponsibilityOwner(normalized);
    if (!classified.production) {
      throw new Error(`owner ${normalized} is not a production owner`);
    }
    if (knownFiles && !knownFiles.has(normalized)) {
      throw new Error(`unknown owner ${normalized}`);
    }
  }
  return manifest;
}

function staleStatusRank(status) {
  return status === 'observed' ? 2 : status === 'not-observed' ? 1 : 0;
}

export function compareResponsibilityBoundary(analysis, boundary) {
  const findings = [];
  if (analysis.ownerKind !== classifyResponsibilityOwner(boundary.path).kind) {
    findings.push(finding('responsibility-owner-kind-change', analysis, {
      expected: classifyResponsibilityOwner(boundary.path).kind,
      actual: analysis.ownerKind,
    }));
  }
  for (const [signal, maximum] of Object.entries(boundary.maxSignals)) {
    const actual = analysis.signals[signal];
    if (!Number.isInteger(actual) || actual < 0) {
      findings.push(finding('responsibility-analysis-incomplete', analysis, {
        signal,
        actual: actual ?? 'missing',
        hint: 'Missing or invalid analysis signals are blocking and are never interpreted as zero responsibility.',
      }));
      continue;
    }
    if (actual > maximum) {
      findings.push(finding('responsibility-debt-growth', analysis, {
        signal,
        expected: maximum,
        actual,
        hint: 'Existing debt is a ceiling for regression detection, not permission for unlimited growth.',
      }));
    } else if (actual < maximum) {
      findings.push(finding('responsibility-boundary-stale', analysis, {
        signal,
        expected: maximum,
        actual,
        hint: 'Lower the recorded ceiling in the same refactor so removed responsibility debt cannot return.',
      }));
    }
  }
  const unexpectedResponsibilities = analysis.responsibilities.filter((item) => !boundary.allowedResponsibilities.includes(item));
  if (unexpectedResponsibilities.length > 0) {
    findings.push(finding('responsibility-scope-growth', analysis, {
      responsibilities: unexpectedResponsibilities,
      hint: 'Register a deliberate owner move and preserve a single authority; do not hide new responsibilities in an existing debt entry.',
    }));
  }
  const retiredResponsibilities = boundary.allowedResponsibilities.filter((item) => (
    !analysis.responsibilities.includes(item)
    && !(item === 'stale-response-protection' && analysis.signals.effectApiCalls > 0)
  ));
  if (retiredResponsibilities.length > 0) {
    findings.push(finding('responsibility-boundary-stale', analysis, {
      responsibilities: retiredResponsibilities,
      hint: 'Remove retired responsibilities from the boundary so the accepted debt cannot be reintroduced.',
    }));
  }
  const unexpectedDependencies = analysis.dependencies.filter((item) => !boundary.allowedDependencies.includes(item));
  if (unexpectedDependencies.length > 0) {
    findings.push(finding('responsibility-dependency-growth', analysis, {
      dependencies: unexpectedDependencies,
      hint: 'Cross-domain dependencies must be explicit and owner-reviewed.',
    }));
  }
  const retiredDependencies = boundary.allowedDependencies.filter((item) => !analysis.dependencies.includes(item));
  if (retiredDependencies.length > 0) {
    findings.push(finding('responsibility-boundary-stale', analysis, {
      dependencies: retiredDependencies,
      hint: 'Remove retired dependencies from the boundary so cross-domain coupling cannot be reintroduced.',
    }));
  }
  const staleProtection = analysis.signals.staleProtection;
  if (!staleProtection || !STALE_PROTECTION_STATUSES.has(staleProtection.status)) {
    findings.push(finding('responsibility-analysis-incomplete', analysis, {
      signal: 'staleProtection',
      actual: staleProtection?.status ?? 'missing',
      hint: 'Missing stale-response analysis is blocking and is never interpreted as not applicable.',
    }));
    return findings;
  }
  const actualStale = staleProtection.status;
  if (analysis.signals.effectApiCalls > 0 && staleStatusRank(actualStale) < staleStatusRank(boundary.staleProtection)) {
    findings.push(finding('stale-protection-regression', analysis, {
      expected: boundary.staleProtection,
      actual: actualStale,
      hint: 'Cancellation/stale-response protection may not regress; not-observed is not passed.',
    }));
  } else if ((actualStale === 'observed' && boundary.staleProtection === 'not-observed')
      || (actualStale === 'not-applicable' && boundary.staleProtection !== 'not-applicable')) {
    findings.push(finding('responsibility-boundary-stale', analysis, {
      signal: 'staleProtection',
      expected: boundary.staleProtection,
      actual: actualStale,
      hint: 'Ratchet the recorded stale-response status after protection improves or effect-owned requests are removed.',
    }));
  }
  return findings;
}

export function loadResponsibilityManifest(manifestPath) {
  let parsed;
  try {
    parsed = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  } catch (error) {
    const wrapped = new Error(`Unable to read responsibility manifest ${manifestPath}: ${error.message}`);
    wrapped.code = 'RESPONSIBILITY_MANIFEST_ERROR';
    throw wrapped;
  }
  try {
    return validateResponsibilityManifest(parsed);
  } catch (error) {
    const wrapped = new Error(`Invalid responsibility manifest ${manifestPath}: ${error.message}`);
    wrapped.code = 'RESPONSIBILITY_MANIFEST_ERROR';
    throw wrapped;
  }
}

function responsibilityFile(relativePath, rootDir) {
  const absolute = path.isAbsolute(relativePath) ? relativePath : path.resolve(rootDir, relativePath);
  const normalized = normalizePath(path.relative(rootDir, absolute));
  return { absolute, normalized };
}

export function scanResponsibilityProject({ rootDir, files, allFiles = files, manifestPath }) {
  const selected = [...new Set(files.map((file) => responsibilityFile(file, rootDir).absolute))].sort();
  const knownFiles = new Set(allFiles
    .map((file) => responsibilityFile(file, rootDir).normalized)
    .filter((file) => classifyResponsibilityOwner(file).production));
  let manifest;
  try {
    manifest = loadResponsibilityManifest(manifestPath);
    validateResponsibilityManifest(manifest, { knownFiles });
  } catch (error) {
    return {
      filesScanned: 0,
      analyses: [],
      blocking: [{
        rule: error.code === 'RESPONSIBILITY_PARSE_ERROR' ? 'responsibility-analysis-failure' : 'responsibility-manifest-failure',
        file: path.relative(rootDir, manifestPath).split(path.sep).join('/'),
        line: 1,
        excerpt: error.message,
        hint: 'Responsibility qualification metadata and parser failures are blocking; missing information is not treated as zero.',
      }],
    };
  }

  const ownerPaths = manifest.owners.map((owner) => responsibilityFile(owner.path, rootDir).absolute);
  const analysisFiles = [...new Set([...selected, ...ownerPaths])].sort();
  const boundaries = new Map(manifest.owners.map((owner) => [normalizePath(owner.path), owner]));
  const analyses = [];
  const blocking = [];
  for (const file of analysisFiles) {
    const relativePath = normalizePath(path.relative(rootDir, file));
    if (!classifyResponsibilityOwner(relativePath).production) {
      continue;
    }
    let analysis;
    try {
      analysis = analyzeResponsibilitySource({ relativePath, text: fs.readFileSync(file, 'utf8') });
    } catch (error) {
      blocking.push({
        rule: 'responsibility-analysis-failure',
        file: relativePath,
        line: 1,
        excerpt: error.message,
        hint: 'TypeScript analysis failure is visible and blocking; it cannot be coerced to zero responsibility.',
      });
      continue;
    }
    analyses.push(analysis);
    const boundary = boundaries.get(relativePath);
    const qualification = qualifyResponsibilityAnalysis(analysis, { boundary });
    const findings = boundary && !qualification.some((item) => item.rule === 'responsibility-analysis-incomplete')
      ? [...qualification, ...compareResponsibilityBoundary(analysis, boundary)]
      : qualification;
    blocking.push(...findings);
  }
  return {
    filesScanned: analyses.length,
    analyses: analyses.sort((left, right) => compareText(left.path, right.path)),
    blocking: blocking.sort((left, right) => compareText(`${left.file}:${left.rule}`, `${right.file}:${right.rule}`)),
  };
}
