import { TerminalChip } from '../terminal/TerminalPrimitives';
import type {
  ResearchReadinessState,
  ResearchReadinessV1,
} from '../../types/researchReadiness';

type CandidateEvidenceVariant = 'row' | 'detail';

type CandidateEvidenceDomain = {
  state?: string | null;
  observationOnly?: boolean | null;
  scoreGradeAllowed?: boolean | null;
};

export type CandidateEvidenceFrame = {
  contractVersion?: string;
  coverageState?: string | null;
  domains?: Record<string, CandidateEvidenceDomain> | null;
  coverage?: {
    availableCount?: number | null;
    partialCount?: number | null;
    observeOnlyCount?: number | null;
    missingCount?: number | null;
    totalCount?: number | null;
  } | null;
  noAdviceBoundary?: boolean | null;
};

const DOMAIN_ORDER = [
  'technicals',
  'priceHistory',
  'liquidity',
  'volume',
  'trend',
  'theme',
  'fundamentals',
  'newsCatalyst',
] as const;

const DOMAIN_LABELS: Record<string, { zh: string; en: string }> = {
  technicals: { zh: '技术面', en: 'Technicals' },
  priceHistory: { zh: '价格历史', en: 'Price history' },
  liquidity: { zh: '流动性', en: 'Liquidity' },
  volume: { zh: '成交量', en: 'Volume' },
  trend: { zh: '趋势', en: 'Trend' },
  theme: { zh: '主题', en: 'Theme' },
  fundamentals: { zh: '基本面', en: 'Fundamentals' },
  newsCatalyst: { zh: '新闻催化', en: 'News catalyst' },
  news: { zh: '新闻催化', en: 'News catalyst' },
  catalyst: { zh: '新闻催化', en: 'News catalyst' },
};

function normalizeState(value?: string | null): string {
  return String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
}

function verdictLabel(
  readiness: ResearchReadinessV1 | null | undefined,
  language: 'zh' | 'en',
): string {
  if (readiness?.verdictLabel?.trim()) return readiness.verdictLabel.trim();
  const state = normalizeState(readiness?.readinessState);
  const labels: Record<string, { zh: string; en: string }> = {
    ready: { zh: '证据可用', en: 'Evidence ready' },
    observe_only: { zh: '仅观察', en: 'Observe only' },
    insufficient: { zh: '证据不足', en: 'Evidence insufficient' },
    blocked: { zh: '阻断', en: 'Blocked' },
    waiting: { zh: '等待更新', en: 'Waiting' },
  };
  return labels[state]?.[language] || (language === 'en' ? 'Evidence pending' : '证据待确认');
}

function toneClass(state: ResearchReadinessState | string | undefined): string {
  const normalized = normalizeState(state);
  if (normalized === 'ready') return 'border-emerald-400/25 bg-emerald-400/10 text-emerald-100';
  if (normalized === 'blocked') return 'border-rose-400/25 bg-rose-400/10 text-rose-100';
  if (normalized === 'insufficient') return 'border-amber-400/25 bg-amber-400/10 text-amber-100';
  if (normalized === 'observe_only') return 'border-blue-400/25 bg-blue-400/10 text-blue-100';
  return 'border-white/10 bg-white/[0.04] text-white/70';
}

function domainStateLabel(state: string | null | undefined, observationOnly: boolean, language: 'zh' | 'en'): string {
  if (observationOnly) return language === 'en' ? 'Observe only' : '仅观察';
  const normalized = normalizeState(state);
  if (normalized === 'available' || normalized === 'ready') return language === 'en' ? 'Available' : '可用';
  if (normalized === 'partial' || normalized === 'mixed') return language === 'en' ? 'Partial' : '部分';
  if (normalized === 'blocked') return language === 'en' ? 'Blocked' : '阻断';
  if (normalized === 'missing' || normalized === 'unavailable' || normalized === 'insufficient') return language === 'en' ? 'Missing' : '缺失';
  return language === 'en' ? 'Pending' : '待补';
}

function localizedDomainLabel(code: string, language: 'zh' | 'en'): string {
  return DOMAIN_LABELS[code]?.[language] || code;
}

function summarizeMissingEvidence(
  readiness: ResearchReadinessV1 | null | undefined,
  language: 'zh' | 'en',
): string | null {
  const missing = Array.from(new Set(
    (readiness?.missingEvidence || [])
      .map((item) => localizedDomainLabel(item, language))
      .filter(Boolean),
  ));
  if (!missing.length) return null;
  return language === 'en'
    ? `Missing ${missing.slice(0, 2).join(' / ')}`
    : `待补 ${missing.slice(0, 2).join(' / ')}`;
}

export function ScannerCandidateEvidenceStrip({
  frame,
  readiness,
  language,
  variant = 'row',
  testId,
}: {
  frame?: CandidateEvidenceFrame | null;
  readiness?: ResearchReadinessV1 | null;
  language: 'zh' | 'en';
  variant?: CandidateEvidenceVariant;
  testId?: string;
}) {
  const domains = frame?.domains || {};
  const orderedDomains = DOMAIN_ORDER
    .map((key) => {
      const item = domains[key];
      if (!item) return null;
      const state = domainStateLabel(item.state, item.observationOnly === true, language);
      return {
        key,
        label: localizedDomainLabel(key, language),
        state,
        toneClass: item.observationOnly
          ? 'border-blue-400/20 bg-blue-400/10 text-blue-100'
          : normalizeState(item.state) === 'missing' || normalizeState(item.state) === 'blocked'
            ? 'border-amber-400/20 bg-amber-400/10 text-amber-100'
            : 'border-white/10 bg-white/[0.04] text-white/72',
      };
    })
    .filter((item): item is NonNullable<typeof item> => Boolean(item));

  const summary = summarizeMissingEvidence(readiness, language);
  if (!readiness && !orderedDomains.length) return null;

  if (variant === 'row') {
    return (
      <div data-testid={testId} className="mt-1.5 flex min-w-0 flex-wrap items-center gap-1.5">
        <span className={`inline-flex max-w-full rounded border px-1.5 py-0.5 text-[10px] font-semibold ${toneClass(readiness?.readinessState)}`}>
          <span className="truncate">{verdictLabel(readiness, language)}</span>
        </span>
        {summary ? (
          <span className="truncate text-[10px] text-white/52" title={summary}>
            {summary}
          </span>
        ) : null}
      </div>
    );
  }

  return (
    <section data-testid={testId} className="space-y-2">
      <div className="flex min-w-0 flex-wrap items-center gap-1.5">
        <span className={`inline-flex max-w-full rounded border px-1.5 py-0.5 text-[10px] font-semibold ${toneClass(readiness?.readinessState)}`}>
          <span className="truncate">{verdictLabel(readiness, language)}</span>
        </span>
        {summary ? (
          <span className="text-xs leading-relaxed text-white/60">{summary}</span>
        ) : null}
      </div>
      <div className="flex min-w-0 flex-wrap gap-1.5">
        {orderedDomains.map((domain) => (
          <TerminalChip key={domain.key} variant="neutral" className={`px-1.5 py-0.5 text-[10px] font-sans ${domain.toneClass}`}>
            <span className="text-white/48">{domain.label}</span>
            <span>{domain.state}</span>
          </TerminalChip>
        ))}
      </div>
    </section>
  );
}
