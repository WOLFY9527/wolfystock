import { marketIntelligenceReasonLabel, sanitizeMarketGuidanceCopy } from './marketIntelligenceGuidance';

export type MarketIntelligenceEvidenceExportLocale = 'zh' | 'en';

export type MarketIntelligenceEvidenceExportItem = {
  label?: string | null;
  meta?: string | null;
};

export type MarketIntelligenceEvidenceExportInput = {
  title?: string | null;
  locale?: MarketIntelligenceEvidenceExportLocale;
  generatedAt?: string | Date | null;
  regimeObservation?: {
    title?: string | null;
    summary?: string | null;
    confidenceLabel?: string | null;
  } | null;
  evidenceUsed?: MarketIntelligenceEvidenceExportItem[];
  evidenceGaps?: Array<string | null | undefined>;
  dataFreshness?: {
    label?: string | null;
    asOf?: string | null;
    notes?: Array<string | null | undefined>;
  } | null;
  researchNextSteps?: Array<string | null | undefined>;
  noAdviceDisclosure?: string | null;
  maxEvidenceItems?: number;
  maxGapItems?: number;
  maxNextStepItems?: number;
};

const DEFAULT_TITLE = 'Market Intelligence Evidence Snapshot';
const DEFAULT_NO_ADVICE_DISCLOSURE = 'This snapshot is for research observation only. It is not an instruction to act.';

const INTERNAL_DIAGNOSTIC_PATTERN =
  /reasonCode|reasonCodes|reason_code|reason_codes|reasonFamilies|sourceRefId|sourceRefIds|source_ref_id|source_ref_ids|\braw\b|raw_result|rawResult|raw_ai_response|rawAiResponse|context_snapshot|contextSnapshot|rawPayload|raw_payload|rawRows|provider|backend|debug|diagnostic|diagnostics|trace|schema|cache|payload|prompt|model|fallback|MarketCache|synthetic_fixture|official_public|authorized_licensed_feed|public_proxy|unofficial_proxy|provider_timeout|provider_runtime|sourceAuthorityAllowed|scoreContributionAllowed|source_confidence|backend snake_case/i;

const ACTION_OR_ADVICE_PATTERN =
  /建议\s*(买入|卖出|加仓|减仓|持有)|买入|卖出|持有|推荐|目标价|目标位|目标区间|止损|止盈|仓位|buy|sell|hold|recommend|recommendation|target(?:\s+price|\s+zone)?|stop(?:\s+loss)?|position[-\s]?sizing|take[-\s]?profit/i;

function asCleanString(value: unknown): string {
  return String(value ?? '').replace(/\s+/g, ' ').trim();
}

function isSafeTimestamp(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}(?:[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:?\d{2}| ?UTC)?)?$/i.test(value);
}

function isReasonToken(value: string): boolean {
  return /^[a-z0-9_:-]+$/i.test(value) && /[_:]/.test(value);
}

function isGenericReasonLabel(value: string): boolean {
  return /Data boundary pending confirmation|数据边界待确认|Data availability unconfirmed|数据状态待确认/i.test(value);
}

function sanitizeExportText(
  value: unknown,
  fallback: string,
  locale: MarketIntelligenceEvidenceExportLocale,
): string {
  const rawText = asCleanString(value);
  if (!rawText) {
    return fallback;
  }
  if (INTERNAL_DIAGNOSTIC_PATTERN.test(rawText)) {
    return fallback;
  }
  if (isReasonToken(rawText)) {
    const reasonLabel = marketIntelligenceReasonLabel(rawText, locale);
    if (
      reasonLabel
      && reasonLabel !== rawText
      && !isGenericReasonLabel(reasonLabel)
      && !ACTION_OR_ADVICE_PATTERN.test(reasonLabel)
      && !INTERNAL_DIAGNOSTIC_PATTERN.test(reasonLabel)
    ) {
      return reasonLabel;
    }
  }

  const guidanceCopy = sanitizeMarketGuidanceCopy(rawText, fallback);
  if (ACTION_OR_ADVICE_PATTERN.test(guidanceCopy) || INTERNAL_DIAGNOSTIC_PATTERN.test(guidanceCopy)) {
    return fallback;
  }

  if (guidanceCopy !== rawText) {
    return guidanceCopy;
  }

  return isReasonToken(rawText) ? fallback : rawText;
}

function sanitizeTimestamp(value: string | Date | null | undefined, fallback: string): string {
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? fallback : value.toISOString();
  }
  const text = asCleanString(value);
  return text && isSafeTimestamp(text) ? text : fallback;
}

function boundedLimit(value: number | undefined, fallback: number): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return fallback;
  }
  return Math.max(1, Math.min(Math.floor(value), 8));
}

function uniqueList(
  values: Array<string | null | undefined>,
  limit: number,
  fallback: string,
  locale: MarketIntelligenceEvidenceExportLocale,
): { lines: string[]; omitted: number } {
  const seen = new Set<string>();
  const lines: string[] = [];
  for (const value of values) {
    const safeValue = sanitizeExportText(value, '', locale);
    if (!safeValue || seen.has(safeValue)) {
      continue;
    }
    seen.add(safeValue);
    lines.push(safeValue);
  }
  if (!lines.length) {
    return { lines: [fallback], omitted: 0 };
  }
  return {
    lines: lines.slice(0, limit),
    omitted: Math.max(0, lines.length - limit),
  };
}

function evidenceLines(
  items: MarketIntelligenceEvidenceExportItem[] | undefined,
  limit: number,
  locale: MarketIntelligenceEvidenceExportLocale,
): { lines: string[]; omitted: number } {
  const sourceItems = Array.isArray(items) ? items : [];
  const lines = sourceItems.slice(0, limit).map((item, index) => {
    const label = sanitizeExportText(item.label, `Evidence item ${index + 1}`, locale);
    const meta = sanitizeExportText(item.meta, 'Evidence detail withheld.', locale);
    return label && meta ? `${label}: ${meta}` : label || meta;
  });

  return {
    lines: lines.length ? lines : ['Evidence detail not available.'],
    omitted: Math.max(0, sourceItems.length - limit),
  };
}

function bulletLines(lines: string[]): string[] {
  return lines.map((line) => `- ${line}`);
}

export function buildMarketIntelligenceEvidenceMarkdown(
  input: MarketIntelligenceEvidenceExportInput = {},
): string {
  const locale = input.locale ?? 'en';
  const evidenceLimit = boundedLimit(input.maxEvidenceItems, 6);
  const gapLimit = boundedLimit(input.maxGapItems, 5);
  const nextStepLimit = boundedLimit(input.maxNextStepItems, 5);
  const title = sanitizeExportText(input.title, DEFAULT_TITLE, locale);
  const generatedAt = sanitizeTimestamp(input.generatedAt, 'Timestamp pending confirmation.');
  const asOf = sanitizeTimestamp(input.dataFreshness?.asOf, 'Data timestamp pending confirmation.');

  const evidence = evidenceLines(input.evidenceUsed, evidenceLimit, locale);
  const gaps = uniqueList(
    input.evidenceGaps ?? [],
    gapLimit,
    'No material evidence gap was included in this snapshot.',
    locale,
  );
  const nextSteps = uniqueList(
    input.researchNextSteps ?? [],
    nextStepLimit,
    'Continue monitoring the same evidence set before forming a stronger view.',
    locale,
  );
  const freshnessNotes = uniqueList(
    input.dataFreshness?.notes ?? [],
    3,
    'No additional freshness note was included.',
    locale,
  );

  const omittedLines = [
    evidence.omitted > 0 ? `- ${evidence.omitted} item${evidence.omitted === 1 ? '' : 's'} omitted by export limit.` : '',
    gaps.omitted > 0 ? `- ${gaps.omitted} evidence gap${gaps.omitted === 1 ? '' : 's'} omitted by export limit.` : '',
    nextSteps.omitted > 0 ? `- ${nextSteps.omitted} research next step${nextSteps.omitted === 1 ? '' : 's'} omitted by export limit.` : '',
  ].filter(Boolean);

  return [
    `# ${title}`,
    '',
    '## Market regime observation',
    `- State: ${sanitizeExportText(input.regimeObservation?.title, 'Market regime observation pending confirmation.', locale)}`,
    `- Summary: ${sanitizeExportText(input.regimeObservation?.summary, 'Evidence is not sufficient for a stronger market regime observation.', locale)}`,
    `- Confidence: ${sanitizeExportText(input.regimeObservation?.confidenceLabel, 'Evidence strength pending confirmation.', locale)}`,
    '',
    '## Evidence used',
    ...bulletLines(evidence.lines),
    '',
    '## Evidence gaps',
    ...bulletLines(gaps.lines),
    '',
    '## Data freshness',
    `- Freshness: ${sanitizeExportText(input.dataFreshness?.label, 'Data freshness pending confirmation.', locale)}`,
    `- As of: ${asOf}`,
    ...bulletLines(freshnessNotes.lines),
    '',
    '## Research next steps',
    ...bulletLines(nextSteps.lines),
    '',
    '## No-advice disclosure',
    `- ${DEFAULT_NO_ADVICE_DISCLOSURE}`,
    '',
    '## Generated timestamp',
    `- Generated at: ${generatedAt}`,
    ...(omittedLines.length ? ['', ...omittedLines] : []),
  ].join('\n');
}
