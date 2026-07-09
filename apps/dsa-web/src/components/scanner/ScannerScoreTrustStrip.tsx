import type {
  ScannerCandidate,
  ScannerCandidateDiagnostic,
} from '../../types/scanner';
import type { DataTrustEvidenceState } from '../../utils/dataTrustEvidenceDisplay';
import { DataTrustEvidenceChips } from '../evidence/DataTrustEvidenceChips';
import { TerminalChip } from '../terminal/TerminalPrimitives';

type TrustSource = ScannerCandidate | ScannerCandidateDiagnostic | null | undefined;

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function getRecord(parent: Record<string, unknown> | null, ...keys: string[]) {
  for (const key of keys) {
    const value = parent?.[key];
    if (isRecord(value)) return value;
  }
  return null;
}

function getString(parent: Record<string, unknown> | null, ...keys: string[]) {
  for (const key of keys) {
    const value = parent?.[key];
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return null;
}

function getNumber(parent: Record<string, unknown> | null, ...keys: string[]) {
  for (const key of keys) {
    const value = parent?.[key];
    if (typeof value === 'number' && Number.isFinite(value)) return value;
  }
  return null;
}

function getBoolean(parent: Record<string, unknown> | null, ...keys: string[]) {
  for (const key of keys) {
    const value = parent?.[key];
    if (typeof value === 'boolean') return value;
  }
  return null;
}

function unique<T>(items: T[]): T[] {
  return items.filter((item, index) => items.indexOf(item) === index);
}

function normalizeKey(value?: string | null): string {
  return String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
}

function localizeReason(reason: string | null, language: 'zh' | 'en') {
  const normalized = normalizeKey(reason);
  const labels: Record<string, { zh: string; en: string }> = {
    fallback_source: { zh: '置信度受限', en: 'Confidence limited' },
    stale_source: { zh: '数据过期', en: 'Stale data' },
    partial_coverage: { zh: '覆盖不完整', en: 'Partial coverage' },
    proxy_quote_source_capped: { zh: '代理证据', en: 'Proxy evidence' },
    public_proxy_not_score_grade: { zh: '仅观察', en: 'Observe only' },
    observation_only: { zh: '仅观察', en: 'Observe only' },
    cache_stale: { zh: '数据过期', en: 'Stale data' },
    provider_timeout: { zh: '当前证据不足', en: 'Current evidence insufficient' },
    quote_unavailable: { zh: '报价数据不足', en: 'Quote data insufficient' },
    history_insufficient: { zh: '历史样本不足', en: 'Historical sample insufficient' },
  };
  if (labels[normalized]) return labels[normalized][language];
  if (!normalized) return null;
  return language === 'en' ? 'Confidence limited' : '置信度受限';
}

function localizeFreshness(value: string | null, language: 'zh' | 'en') {
  const normalized = normalizeKey(value);
  if (normalized === 'fallback') return language === 'en' ? 'Fallback data' : '备用数据';
  if (normalized === 'stale') return language === 'en' ? 'Stale data' : '数据过期';
  if (normalized === 'partial') return language === 'en' ? 'Partial coverage' : '覆盖不完整';
  if (normalized === 'delayed') return language === 'en' ? 'Delayed' : '延迟';
  if (normalized === 'fresh' || normalized === 'live') return language === 'en' ? 'Live' : '较新';
  if (!normalized) return null;
  return value;
}

function displaySourceLabel(value: string | null, language: 'zh' | 'en'): string | null {
  if (!value) return null;
  const normalized = normalizeKey(value);
  if (normalized.includes('fallback')) return language === 'en' ? 'Fallback data' : '备用数据';
  if (normalized.includes('proxy')) return language === 'en' ? 'Proxy evidence' : '代理证据';
  if (normalized.includes('stale')) return language === 'en' ? 'Stale data' : '数据过期';
  if (normalized.includes('partial')) return language === 'en' ? 'Partial coverage' : '覆盖不完整';
  return value;
}

function getTrustRecords(sources: TrustSource[]) {
  for (const source of sources) {
    const root = isRecord(source) ? source : null;
    const diagnostics = getRecord(root, 'diagnostics');
    const metadata = getRecord(root, 'metadata');
    const explainability = getRecord(diagnostics, 'scoreExplainability', 'score_explainability')
      || getRecord(metadata, 'scoreExplainability', 'score_explainability');
    const evidencePacket = getRecord(diagnostics, 'evidencePacket', 'evidence_packet')
      || getRecord(metadata, 'evidencePacket', 'evidence_packet');
    const sourceConfidence = getRecord(explainability, 'sourceConfidence', 'source_confidence')
      || getRecord(evidencePacket, 'sourceConfidence', 'source_confidence');
    const providerObservation = getRecord(evidencePacket, 'providerObservation', 'provider_observation');
    if (explainability || evidencePacket || sourceConfidence || providerObservation) {
      return {
        explainability,
        evidencePacket,
        sourceConfidence,
        providerObservation,
      };
    }
  }
  return {
    explainability: null,
    evidencePacket: null,
    sourceConfidence: null,
    providerObservation: null,
  };
}

function confidenceTier(scoreConfidence: number | null, hasCap: boolean) {
  if (hasCap) return 'capped';
  if (scoreConfidence == null) return 'unknown';
  if (scoreConfidence >= 0.9) return 'high';
  if (scoreConfidence >= 0.7) return 'medium';
  return 'low';
}

function confidenceChip(tier: string, language: 'zh' | 'en') {
  if (tier === 'capped') {
    return {
      label: language === 'en' ? 'Confidence limited' : '置信度受限',
      variant: 'caution' as const,
    };
  }
  if (tier === 'high') {
    return {
      label: language === 'en' ? 'High confidence' : '高置信',
      variant: 'success' as const,
    };
  }
  if (tier === 'medium') {
    return {
      label: language === 'en' ? 'Medium confidence' : '中置信',
      variant: 'info' as const,
    };
  }
  if (tier === 'low') {
    return {
      label: language === 'en' ? 'Confidence limited' : '置信度受限',
      variant: 'caution' as const,
    };
  }
  return {
    label: language === 'en' ? 'Confidence limited' : '置信度受限',
    variant: 'caution' as const,
  };
}

export function ScannerScoreTrustStrip({
  sources,
  language,
  className,
  testId,
}: {
  sources: TrustSource[];
  language: 'zh' | 'en';
  className?: string;
  testId?: string;
}) {
  const { explainability, evidencePacket, sourceConfidence, providerObservation } = getTrustRecords(sources);
  if (!explainability && !evidencePacket && !sourceConfidence && !providerObservation) return null;

  const scoreConfidence = getNumber(explainability, 'scoreConfidence', 'score_confidence')
    ?? getNumber(evidencePacket, 'scoreConfidence', 'score_confidence')
    ?? getNumber(sourceConfidence, 'confidenceWeight', 'confidence_weight');
  const capReason = getString(explainability, 'capReason', 'cap_reason')
    ?? getString(evidencePacket, 'capReason', 'cap_reason')
    ?? getString(sourceConfidence, 'capReason', 'cap_reason');
  const degradationReason = getString(explainability, 'degradationReason', 'degradation_reason')
    ?? getString(evidencePacket, 'degradationReason', 'degradation_reason')
    ?? getString(sourceConfidence, 'degradationReason', 'degradation_reason');
  const scoreGradeAllowed = getBoolean(explainability, 'scoreGradeAllowed', 'score_grade_allowed');
  const scoreContributionAllowed = getBoolean(sourceConfidence, 'scoreContributionAllowed', 'score_contribution_allowed')
    ?? getBoolean(providerObservation, 'scoreContributionAllowed', 'score_contribution_allowed');
  const inferredObservationOnly = scoreGradeAllowed === false || scoreContributionAllowed === false;
  const observationOnly = getBoolean(sourceConfidence, 'observationOnly', 'observation_only')
    ?? getBoolean(providerObservation, 'observationOnly', 'observation_only')
    ?? inferredObservationOnly;
  const inferredFallbackFlag = normalizeKey(getString(sourceConfidence, 'freshness')) === 'fallback'
    || normalizeKey(getString(evidencePacket, 'freshnessState', 'freshness_state')) === 'fallback'
    || /fallback/.test(normalizeKey(capReason))
    || /fallback/.test(normalizeKey(degradationReason));
  const fallbackFlag = getBoolean(sourceConfidence, 'isFallback', 'is_fallback')
    ?? inferredFallbackFlag;
  const staleFlag = getBoolean(sourceConfidence, 'isStale', 'is_stale')
    ?? (normalizeKey(getString(evidencePacket, 'freshnessState', 'freshness_state')) === 'stale');
  const partialFlag = getBoolean(sourceConfidence, 'isPartial', 'is_partial')
    ?? (normalizeKey(getString(evidencePacket, 'dataQualityState', 'data_quality_state')) === 'partial');
  const inferredProxyFlag = /proxy/.test(normalizeKey(capReason))
    || /proxy/.test(normalizeKey(degradationReason))
    || /proxy/.test(normalizeKey(getString(sourceConfidence, 'source', 'sourceLabel', 'source_label')));
  const proxyFlag = getBoolean(sourceConfidence, 'proxyOnly', 'proxy_only') ?? inferredProxyFlag;
  const sourceLabel = getString(sourceConfidence, 'sourceLabel', 'source_label', 'source');
  const quoteFreshnessRaw = getString(getRecord(evidencePacket, 'freshnessDetail', 'freshness_detail'), 'quoteState', 'quote_state')
    ?? getString(sourceConfidence, 'freshness');
  const historyFreshnessRaw = getString(getRecord(evidencePacket, 'freshnessDetail', 'freshness_detail'), 'historyState', 'history_state');
  const quoteFreshness = localizeFreshness(
    quoteFreshnessRaw,
    language,
  );
  const historyFreshness = localizeFreshness(
    historyFreshnessRaw,
    language,
  );
  const freshnessLabel = unique([quoteFreshness, historyFreshness].filter((item): item is string => Boolean(item))).join(' / ');
  const confidenceTierValue = confidenceTier(scoreConfidence, Boolean(capReason));
  const confidenceBadge = confidenceChip(confidenceTierValue, language);
  const confidenceLimited = ['capped', 'low', 'unknown'].includes(confidenceTierValue);
  const cautionReason = localizeReason(capReason, language) || localizeReason(degradationReason, language);
  const dataTrustStates: DataTrustEvidenceState[] = unique([
    partialFlag ? 'partial' : null,
    staleFlag ? 'stale' : null,
    fallbackFlag || proxyFlag ? 'fallback' : null,
    observationOnly ? 'observation-only' : null,
  ].filter((state): state is DataTrustEvidenceState => Boolean(state)));
  const displaySource = displaySourceLabel(sourceLabel, language);
  const summaryParts = unique([
    cautionReason,
    displaySource ? `${language === 'en' ? 'Source' : '来源'} ${displaySource}` : null,
    freshnessLabel ? `${language === 'en' ? 'Freshness' : '时效'} ${freshnessLabel}` : null,
    scoreConfidence != null ? `${language === 'en' ? 'Confidence' : '可信'} ${scoreConfidence.toFixed(2)}` : null,
    observationOnly || capReason ? (language === 'en' ? 'Observation only' : '仅供观察') : null,
  ].filter((item): item is string => Boolean(item)));
  const resolvedClassName = ['flex min-w-0 flex-col gap-1', className || ''].filter(Boolean).join(' ');

  return (
    <div data-testid={testId} className={resolvedClassName}>
      <div className="flex min-w-0 flex-wrap items-center gap-1">
        {!confidenceLimited ? (
          <TerminalChip variant={confidenceBadge.variant} className="px-1.5 py-0.5 text-[10px] font-semibold tracking-[0.02em]">
            {confidenceBadge.label}
          </TerminalChip>
        ) : null}
        <DataTrustEvidenceChips
          input={{
            locale: language,
            states: dataTrustStates,
          }}
          maxStates={5}
          className="gap-1"
        />
      </div>
      {summaryParts.length ? (
        <p className="text-[11px] leading-relaxed text-[color:var(--wolfy-text-muted)]">
          {summaryParts.join(language === 'en' ? ' | ' : ' ｜ ')}
        </p>
      ) : null}
    </div>
  );
}
