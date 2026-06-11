import { sanitizeUserFacingDataIssue } from './userFacingDataIssues';

export type NormalizedEvidenceEngine =
  | 'scanner'
  | 'rotation'
  | 'options'
  | 'backtest'
  | 'portfolio_risk'
  | 'analysis'
  | 'unknown';

export type NormalizedEvidencePosture =
  | 'blocked'
  | 'observe_only'
  | 'review_required'
  | 'allowed_metadata_only'
  | 'unknown';

export type NormalizedEvidenceSummary = {
  engine: NormalizedEvidenceEngine;
  posture: NormalizedEvidencePosture;
  displayLabel: string;
  tone: 'neutral' | 'info' | 'warning' | 'danger' | 'success';
  confidenceCap?: number;
  freshnessLabel?: string;
  limitationLabels: string[];
  adminReasonCodes: string[];
  sourceRefCount?: number;
  diagnostics?: unknown;
};

type EvidenceAudience = 'user' | 'admin';

type NormalizeEvidenceOptions = {
  audience?: EvidenceAudience;
  includeDiagnostics?: boolean;
  maxLimitationLabels?: number;
};

const POSTURE_LABELS: Record<NormalizedEvidencePosture, string> = {
  blocked: '数据不足，禁止判断',
  observe_only: '仅供观察',
  review_required: '需人工复核',
  allowed_metadata_only: '依据需复核',
  unknown: '证据待确认',
};

const POSTURE_TONES: Record<NormalizedEvidencePosture, NormalizedEvidenceSummary['tone']> = {
  blocked: 'danger',
  observe_only: 'info',
  review_required: 'warning',
  allowed_metadata_only: 'neutral',
  unknown: 'neutral',
};

const DIRECT_LABEL_MAP: Record<string, string | null> = {
  blocked: '数据不足，禁止判断',
  '数据不足，禁止判断': '数据不足，禁止判断',
  '禁止判断': '数据不足，禁止判断',
  observe_only: '仅供观察',
  '仅观察': '仅供观察',
  '仅供观察': '仅供观察',
  '仅供风险观察': '仅供风险观察',
  review_required: '需人工复核',
  '需人工复核': '需人工复核',
  allowed_metadata_only: '依据需复核',
  '依据需复核': '依据需复核',
  '研究级回测': '研究级回测',
  '专业级条件未满足': '专业级条件未满足',
  '数据口径需复核': '数据口径需复核',
  '交易日历待确认': '交易日历待确认',
  '复权/公司行动待确认': '复权/公司行动待确认',
  '持仓来源待核验': '持仓来源待核验',
  '现金流水不完整': '现金流水不完整',
  '成本口径需复核': '成本口径需复核',
  '部分外部数据暂不可用': '部分外部数据暂不可用',
  '历史数据不足': '历史数据不足',
  '真实资金流暂缺': '真实资金流暂缺',
  read_only: '只读',
  readonly: '只读',
  'read-only': '只读',
  advisory_only: '仅提示',
  'advisory-only': '仅提示',
  dry_run: '试运行',
  'dry-run': '试运行',
  'dry run': '试运行',
  no_send: '不发送',
  'no-send': '不发送',
  no_live_quota: '保持观察边界',
  'no-live-quota': '保持观察边界',
  quota_dry_run: '保持观察边界',
  no_provider_blocking: '不改变数据通路',
  'no-provider-blocking': '不改变数据通路',
  no_external_calls: '不触发外部动作',
  'no-external-calls': '不触发外部动作',
  'FX 汇率已过期': 'FX 汇率已过期',
  'fx 汇率已过期': 'FX 汇率已过期',
  'FX 汇率缺失': 'FX 汇率缺失',
  'fx 汇率缺失': 'FX 汇率缺失',
  '基准映射暂缺': '基准映射暂缺',
  '因子映射暂缺': '因子映射暂缺',
  fallback: '备用数据',
  'fallback 数据': '备用数据',
  fallback_data: '备用数据',
  fixture: '演示数据',
  demo: '演示数据',
  mock: '演示数据',
  synthetic: '演示数据',
  stale: '数据已过期',
  'unknown freshness': '数据新鲜度未知',
  gap_fade_risk: '高开回落风险',
  thin_breadth: '广度偏薄',
  single_name_driven: '单一龙头驱动',
  stale_or_incomplete_windows: '时窗缺失/过期',
  not_enough_history: '历史数据不足',
  provider_timeout: '部分外部数据暂不可用',
  proxy_quote_missing: '部分外部数据暂不可用',
  proxy_stale: '数据已过期',
  proxy_windows_missing: '部分外部数据暂不可用',
  fx_rate_stale: 'FX 汇率已过期',
  fx_rate_missing: 'FX 汇率缺失',
  benchmark_mapping_missing: '基准映射暂缺',
  factor_mapping_missing: '因子映射暂缺',
  insufficient_evidence: '仅供观察',
  research_prototype: '研究级回测',
  unknown_or_mixed: '数据口径需复核',
  available_bars_only: '交易日历待确认',
  research_prototype_only: '研究级回测',
};

const HIDDEN_USER_PATTERNS = [
  /marketcache/i,
  /\braw\b/i,
  /\bdebug\b/i,
  /\bschema\b/i,
  /\btrace\b/i,
];

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function normalizeKey(value?: string | null): string {
  return String(value || '').trim().toLowerCase().replace(/[\s/-]+/g, '_');
}

function asString(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed || null;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => asString(item))
    .filter((item): item is string => Boolean(item));
}

function asNumber(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  return undefined;
}

function firstRecord(value: unknown, keys: string[]): Record<string, unknown> | null {
  if (isRecord(value)) {
    for (const key of keys) {
      const nested = value[key];
      if (isRecord(nested)) return nested;
    }
  }
  return isRecord(value) ? value : null;
}

function firstValue(value: unknown, keys: string[]): unknown {
  if (!isRecord(value)) return undefined;
  for (const key of keys) {
    if (value[key] != null) return value[key];
  }
  return undefined;
}

function collectStrings(...values: unknown[]): string[] {
  return values.flatMap((value) => {
    if (Array.isArray(value)) return asStringArray(value);
    const direct = asString(value);
    return direct ? [direct] : [];
  });
}

function unique(values: string[]): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    if (seen.has(value)) continue;
    seen.add(value);
    result.push(value);
  }
  return result;
}

function shouldHideFromUser(normalized: string): boolean {
  return HIDDEN_USER_PATTERNS.some((pattern) => pattern.test(normalized));
}

const PRIVATE_BETA_LABEL_MAP: Record<string, string> = {
  read_only: '只读',
  read_only_projection: '只读',
  readonly: '只读',
  advisory_only: '仅提示',
  advisory_only_contract: '仅提示',
  suggestion_only: '仅提示',
  dry_run: '试运行',
  dry_run_preview: '试运行',
  dryrun: '试运行',
  no_send: '不发送',
  nosend: '不发送',
  no_notification: '不发送',
  notification_disabled: '不发送',
  delivery_disabled: '不发送',
  no_live_quota: '保持观察边界',
  nolivequota: '保持观察边界',
  quota_dry_run: '保持观察边界',
  live_enforcement_false: '保持观察边界',
  'liveenforcement=false': '保持观察边界',
  no_provider_blocking: '不改变数据通路',
  noproviderblocking: '不改变数据通路',
  no_provider_enforcement: '不改变数据通路',
  provider_blocking_false: '不改变数据通路',
  'providerblocking=false': '不改变数据通路',
  would_block_call_false: '不改变数据通路',
  'wouldblockcall=false': '不改变数据通路',
  no_external_calls: '不触发外部动作',
  'noexternalcalls=true': '不触发外部动作',
  demo_only: '演示数据',
  provider_fixture_not_decision_grade: '演示数据',
  synthetic_or_fixture_data_not_decision_grade: '演示数据',
};

function mapPrivateBetaBoundaryLabel(normalized: string): string | null {
  if (PRIVATE_BETA_LABEL_MAP[normalized]) {
    return PRIVATE_BETA_LABEL_MAP[normalized];
  }
  if (normalized.includes('演示数据')) {
    return '演示数据';
  }
  return null;
}

function mapKnownLabel(value?: string | null): string | null {
  const raw = asString(value);
  if (!raw) return null;

  if (DIRECT_LABEL_MAP[raw] != null) {
    return DIRECT_LABEL_MAP[raw];
  }

  const normalized = normalizeKey(raw);
  if (Object.prototype.hasOwnProperty.call(DIRECT_LABEL_MAP, normalized)) {
    return DIRECT_LABEL_MAP[normalized] ?? null;
  }
  if (shouldHideFromUser(normalized)) {
    return null;
  }
  const privateBetaBoundaryLabel = mapPrivateBetaBoundaryLabel(normalized);
  if (privateBetaBoundaryLabel) {
    return privateBetaBoundaryLabel;
  }
  if (normalized.includes('provider_timeout') || normalized.includes('provider') || normalized.includes('timeout')) {
    return '部分外部数据暂不可用';
  }
  if (normalized.includes('history') || normalized.includes('not_enough_history')) {
    return '历史数据不足';
  }
  if (normalized.includes('fallback')) {
    return '备用数据';
  }
  if (
    normalized.includes('dry_run')
    || normalized.includes('fixture')
    || normalized.includes('mock')
    || normalized.includes('synthetic')
  ) {
    return '演示数据';
  }
  if (normalized.includes('stale') || normalized.includes('expired')) {
    return '数据已过期';
  }
  if (normalized.includes('freshness_unknown')) {
    return '数据新鲜度未知';
  }
  if (normalized.includes('fx') && normalized.includes('stale')) {
    return 'FX 汇率已过期';
  }
  if (normalized.includes('fx') && (normalized.includes('missing') || normalized.includes('unavailable'))) {
    return 'FX 汇率缺失';
  }
  if (normalized.includes('benchmark') && normalized.includes('mapping')) {
    return '基准映射暂缺';
  }
  if (normalized.includes('factor') && normalized.includes('mapping')) {
    return '因子映射暂缺';
  }
  if (normalized.includes('holdings') && normalized.includes('lineage')) {
    return '持仓来源待核验';
  }
  if (normalized.includes('cash') && normalized.includes('ledger')) {
    return '现金流水不完整';
  }
  if (normalized.includes('cost') && (normalized.includes('basis') || normalized.includes('model'))) {
    return '成本口径需复核';
  }
  if (normalized.includes('research_prototype')) {
    return '研究级回测';
  }
  if (normalized.includes('calendar')) {
    return '交易日历待确认';
  }
  if (normalized.includes('corporate') || normalized.includes('adjusted')) {
    return '复权/公司行动待确认';
  }
  if (normalized.includes('review')) {
    return '需人工复核';
  }
  if (normalized.includes('blocked') || normalized.includes('forbid')) {
    return '数据不足，禁止判断';
  }
  if (normalized.includes('observe') || normalized.includes('proxy_only')) {
    return '仅供观察';
  }
  if (normalized.includes('gap_fade')) {
    return '高开回落风险';
  }
  if (normalized.includes('thin_breadth')) {
    return '广度偏薄';
  }
  if (normalized.includes('single_name_driven')) {
    return '单一龙头驱动';
  }
  if (normalized.includes('fund_flow')) {
    return '真实资金流暂缺';
  }
  if (/_/.test(normalized) || /^[a-z0-9]+$/.test(normalized)) {
    return sanitizeUserFacingDataIssue(raw, 'zh');
  }

  return raw;
}

function detectPosture(...values: unknown[]): NormalizedEvidencePosture {
  const normalizedValues = collectStrings(...values).map((value) => normalizeKey(value));

  if (normalizedValues.some((value) => value.includes('数据不足') || value.includes('禁止判断') || value === 'blocked')) {
    return 'blocked';
  }
  if (normalizedValues.some((value) => value.includes('需人工复核') || value.includes('review_required'))) {
    return 'review_required';
  }
  if (normalizedValues.some((value) => value.includes('依据需复核') || value.includes('allowed_metadata_only'))) {
    return 'allowed_metadata_only';
  }
  if (
    normalizedValues.some((value) => (
      value.includes('仅观察')
      || value.includes('仅供观察')
      || value.includes('仅供风险观察')
      || value.includes('observe_only')
      || value.includes('research_prototype')
      || value.includes('proxy_only')
      || value.includes('insufficient_evidence')
    ))
  ) {
    return 'observe_only';
  }
  return 'unknown';
}

function buildLimitationLabels(values: string[], options: NormalizeEvidenceOptions): string[] {
  const mapped = unique(values.flatMap((value) => { const v = mapKnownLabel(value); return v ? [v] : []; }));
  const maxLimitationLabels = options.maxLimitationLabels ?? mapped.length;
  return mapped.slice(0, maxLimitationLabels);
}

function stateNeedsBadge(value: unknown, acceptedStates: string[]): boolean {
  const normalized = normalizeKey(asString(value));
  if (!normalized) return false;
  return !acceptedStates.includes(normalized);
}

function sourceRefCountFrom(payload: unknown): number | undefined {
  const sourceRefs = firstValue(payload, ['sourceRefs', 'source_refs']);
  return Array.isArray(sourceRefs) ? sourceRefs.length : undefined;
}

function confidenceCapFrom(payload: unknown): number | undefined {
  const direct = asNumber(firstValue(payload, ['confidenceCap', 'confidence_cap']));
  if (direct != null) return direct;
  const cap = firstRecord(firstValue(payload, ['confidenceCap', 'confidence_cap']), ['value']);
  return asNumber(cap?.value);
}

function freshnessLabelFrom(...values: unknown[]): string | undefined {
  const normalized = collectStrings(...values).map((value) => normalizeKey(value));
  if (normalized.some((value) => value.includes('stale') || value.includes('expired'))) return '数据已过期';
  if (normalized.some((value) => value.includes('unknown_freshness') || value.includes('freshness_unknown'))) return '数据新鲜度未知';
  if (normalized.some((value) => value.includes('fallback'))) return '备用数据';
  if (normalized.some((value) => value.includes('mock') || value.includes('fixture') || value.includes('synthetic') || value.includes('dry_run'))) return '演示数据';
  return undefined;
}

function baseSummary(
  engine: NormalizedEvidenceEngine,
  posture: NormalizedEvidencePosture,
  limitationLabels: string[],
  payload: unknown,
  options: NormalizeEvidenceOptions,
  diagnostics?: unknown,
  adminReasonCodes: string[] = [],
): NormalizedEvidenceSummary {
  const confidenceCap = confidenceCapFrom(payload);
  const freshnessLabel = freshnessLabelFrom(
    firstValue(payload, ['freshnessLabel', 'freshness_label', 'freshnessState', 'freshness_state', 'fxFreshnessState']),
    limitationLabels,
  );

  return {
    engine,
    posture,
    displayLabel: POSTURE_LABELS[posture],
    tone: POSTURE_TONES[posture],
    confidenceCap,
    freshnessLabel,
    limitationLabels,
    adminReasonCodes: options.audience === 'admin' ? unique(adminReasonCodes) : [],
    sourceRefCount: sourceRefCountFrom(payload),
    diagnostics: options.audience === 'admin' && options.includeDiagnostics ? diagnostics : undefined,
  };
}

export function normalizeScannerEvidence(payload: unknown, options: NormalizeEvidenceOptions = {}): NormalizedEvidenceSummary {
  const packet = firstRecord(payload, ['evidencePacket', 'evidence_packet']) ?? firstRecord(payload, []);
  if (!packet) return baseSummary('scanner', 'unknown', [], payload, options);

  const labels = collectStrings(
    packet.userFacingLabels,
    packet.user_facing_labels,
    packet.warningFlags,
    packet.warning_flags,
    packet.missingEvidence,
    packet.missing_evidence,
    packet.dataQualityState,
    packet.data_quality_state,
    packet.freshnessState,
    packet.freshness_state,
  );
  const posture = detectPosture(labels);
  const limitationLabels = buildLimitationLabels(labels, options);
  const diagnostics = firstValue(packet, ['diagnostics', 'adminDiagnostics', 'admin_diagnostics']);
  const adminReasonCodes = collectStrings(packet.adminReasonCodes, packet.admin_reason_codes);
  return baseSummary('scanner', posture, limitationLabels, packet, options, diagnostics, adminReasonCodes);
}

export function normalizeRotationEvidence(payload: unknown, options: NormalizeEvidenceOptions = {}): NormalizedEvidenceSummary {
  const packet = firstRecord(payload, ['rotationStateEvidence', 'rotation_state_evidence']) ?? firstRecord(payload, []);
  if (!packet) return baseSummary('rotation', 'unknown', [], payload, options);

  const requiredData = firstRecord(firstValue(packet, ['requiredDataStatus', 'required_data_status']), []);
  const flowLanguageAllowed = firstValue(packet, ['flowLanguageAllowed', 'flow_language_allowed']);
  const flowBoundaryLabel = flowLanguageAllowed === false ? '真实资金流暂缺' : null;
  const evidenceBoundaryLabel = requiredData?.hasSufficientEvidence === false && !asString(requiredData?.summaryLabel) ? '证据不足' : null;
  const labels = collectStrings(
    packet.state,
    packet.stateLabel,
    requiredData?.summaryLabel,
    requiredData?.statusLabel,
    packet.flowEvidenceType,
    packet.flow_evidence_type,
    flowBoundaryLabel,
    evidenceBoundaryLabel,
    packet.riskLabels,
    packet.risk_labels,
  );
  const posture = detectPosture(labels);
  const limitationLabels = buildLimitationLabels(labels, options);
  const diagnostics = firstValue(packet, ['adminDiagnostics', 'admin_diagnostics']);
  const adminReasonCodes = collectStrings(packet.adminReasonCodes, packet.admin_reason_codes);
  return baseSummary('rotation', posture, limitationLabels, packet, options, diagnostics, adminReasonCodes);
}

export function normalizeOptionsEvidence(payload: unknown, options: NormalizeEvidenceOptions = {}): NormalizedEvidenceSummary {
  const packet = firstRecord(payload, []);
  if (!packet) return baseSummary('options', 'unknown', [], payload, options);

  const decisionGrade = firstValue(packet, ['decisionGrade', 'decision_grade']);
  const labels = collectStrings(
    packet.gateDecision,
    packet.gate_decision,
    packet.decisionLabel,
    packet.decision_label,
    packet.gateIssues,
    packet.gate_issues,
    packet.failClosedReasonCodes,
    packet.fail_closed_reason_codes,
    firstValue(packet, ['riskWarnings', 'risk_warnings']),
    decisionGrade === false ? '数据不足，禁止判断' : null,
  );
  const posture = detectPosture(labels);
  const limitationLabels = buildLimitationLabels(labels, options);
  const diagnostics = {
    dataQualityGates: firstValue(packet, ['dataQualityGates', 'data_quality_gates']),
    liquidityGates: firstValue(packet, ['liquidityGates', 'liquidity_gates']),
    gateIssues: firstValue(packet, ['gateIssues', 'gate_issues']),
  };
  const adminReasonCodes = collectStrings(packet.failClosedReasonCodes, packet.fail_closed_reason_codes);
  return baseSummary('options', posture, limitationLabels, packet, options, diagnostics, adminReasonCodes);
}

export function normalizeBacktestReadiness(payload: unknown, options: NormalizeEvidenceOptions = {}): NormalizedEvidenceSummary {
  const packet = firstRecord(payload, ['professionalReadiness', 'professional_readiness']) ?? firstRecord(payload, []);
  if (!packet) return baseSummary('backtest', 'unknown', [], payload, options);

  const root = isRecord(payload) ? payload : {};
  const combined = { ...root, ...packet };
  const overallState = firstValue(combined, ['overallState', 'overall_state']);
  const professionalQuantReady = firstValue(combined, ['professionalQuantReady', 'professional_quant_ready']);
  const adjustedDataState = firstValue(combined, ['adjustedDataState', 'adjusted_data_state']);
  const corporateActionState = firstValue(combined, ['corporateActionState', 'corporate_action_state']);
  const tradingCalendarState = firstValue(combined, ['tradingCalendarState', 'trading_calendar_state']);
  const costModelState = firstValue(combined, ['costModelState', 'cost_model_state']);
  const reproducibilityState = firstValue(combined, ['reproducibilityState', 'reproducibility_state']);
  const backtestLabels = collectStrings(
    normalizeKey(asString(overallState)) === 'research_prototype' ? '研究级回测' : null,
    professionalQuantReady === false ? '专业级条件未满足' : null,
    stateNeedsBadge(adjustedDataState, ['ready', 'available', 'confirmed']) ? '数据口径需复核' : null,
    stateNeedsBadge(corporateActionState, ['ready', 'available', 'confirmed']) ? '复权/公司行动待确认' : null,
    stateNeedsBadge(tradingCalendarState, ['ready', 'available', 'confirmed', 'market_calendar_confirmed']) ? '交易日历待确认' : null,
    stateNeedsBadge(costModelState, ['ready', 'available', 'confirmed']) ? '成本口径需复核' : null,
    stateNeedsBadge(reproducibilityState, ['ready', 'available', 'confirmed', 'reproducible']) ? '数据口径需复核' : null,
  );
  const labels = collectStrings(
    firstValue(combined, ['overallState', 'overall_state']),
    firstValue(combined, ['summaryLabel', 'summary_label']),
    backtestLabels,
  );
  const posture = detectPosture(labels);
  const limitationLabels = buildLimitationLabels(labels, options);
  return baseSummary('backtest', posture, limitationLabels, combined, options);
}

export function normalizePortfolioRiskEvidence(payload: unknown, options: NormalizeEvidenceOptions = {}): NormalizedEvidenceSummary {
  const packet = firstRecord(payload, ['portfolioRiskEvidence', 'portfolio_risk_evidence']) ?? firstRecord(payload, []);
  if (!packet) return baseSummary('portfolio_risk', 'unknown', [], payload, options);

  const root = isRecord(payload) ? payload : {};
  const diagnosticsRecord = firstRecord(firstValue(root, ['riskDiagnostics', 'risk_diagnostics']), []);
  const combined = { ...diagnosticsRecord, ...root, ...packet };
  const cap = firstRecord(
    firstValue(root, ['confidenceCap', 'confidence_cap'])
      ?? firstValue(diagnosticsRecord, ['confidenceCap', 'confidence_cap'])
      ?? firstValue(packet, ['confidenceCap', 'confidence_cap', 'confidence_cap']),
    [],
  );
  const labels = collectStrings(
    combined.limitationLabels,
    combined.limitation_labels,
    cap?.limitationLabels,
    cap?.limitation_labels,
    combined.fxFreshnessState,
    combined.fx_freshness_state,
    combined.holdingsLineageState,
    combined.holdings_lineage_state,
    combined.cashLedgerCompletenessState,
    combined.cash_ledger_completeness_state,
    combined.sourceAuthorityState,
    combined.source_authority_state,
    combined.benchmarkMappingState,
    combined.benchmark_mapping_state,
    combined.factorMappingState,
    combined.factor_mapping_state,
    cap?.reasonCodes,
    cap?.reason_codes,
  );
  const posture = detectPosture(labels) === 'unknown' && labels.length ? 'review_required' : detectPosture(labels);
  const limitationLabels = buildLimitationLabels(labels, options);
  const diagnostics = firstValue(combined, ['diagnostics', 'adminDiagnostics', 'admin_diagnostics']);
  const adminReasonCodes = collectStrings(cap?.reasonCodes, cap?.reason_codes);
  return baseSummary('portfolio_risk', posture, limitationLabels, combined, options, diagnostics, adminReasonCodes);
}
