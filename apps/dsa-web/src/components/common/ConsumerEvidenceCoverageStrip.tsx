import type React from 'react';
import { TerminalChip } from '../terminal';
import { cn } from '../../utils/cn';
import type {
  AnalysisEvidenceCoverageDomain,
  AnalysisEvidenceCoverageEntry,
  AnalysisEvidenceCoverageFrame,
} from '../../types/analysis';
import { sanitizeUserFacingDataIssue } from '../../utils/userFacingDataIssues';

type EvidenceCoverageLocale = 'zh' | 'en';

type ConsumerEvidenceCoverageStripProps = {
  frame: AnalysisEvidenceCoverageFrame | null | undefined;
  locale?: EvidenceCoverageLocale;
  title?: string;
  testId?: string;
  className?: string;
};

const PRIMARY_DOMAINS: AnalysisEvidenceCoverageDomain[] = [
  'technicals',
  'fundamentals',
  'news',
  'catalysts',
  'earnings',
  'valuation',
];

const SECONDARY_DOMAINS: AnalysisEvidenceCoverageDomain[] = [
  'priceHistory',
  'sentiment',
  'liquidityContext',
  'macroContext',
];

const DOMAIN_LABELS: Record<AnalysisEvidenceCoverageDomain, { zh: string; en: string }> = {
  priceHistory: { zh: '价格历史', en: 'Price history' },
  technicals: { zh: '技术面', en: 'Technicals' },
  fundamentals: { zh: '基本面', en: 'Fundamentals' },
  earnings: { zh: '财报', en: 'Earnings' },
  news: { zh: '新闻', en: 'News' },
  catalysts: { zh: '催化', en: 'Catalysts' },
  sentiment: { zh: '情绪', en: 'Sentiment' },
  valuation: { zh: '估值', en: 'Valuation' },
  liquidityContext: { zh: '流动性', en: 'Liquidity' },
  macroContext: { zh: '宏观', en: 'Macro' },
};

const STATUS_LABELS: Record<string, { zh: string; en: string }> = {
  available: { zh: '可用', en: 'Available' },
  degraded: { zh: '降级', en: 'Degraded' },
  missing: { zh: '缺失', en: 'Missing' },
  blocked: { zh: '阻断', en: 'Blocked' },
  pending: { zh: '待补', en: 'Pending' },
  not_applicable: { zh: '不适用', en: 'Not applicable' },
  unavailable: { zh: '不可用', en: 'Unavailable' },
  unknown: { zh: '待确认', en: 'Unconfirmed' },
};

const REASON_LABELS: Record<string, { zh: string; en: string }> = {
  evidence_missing: { zh: '关键证据缺失', en: 'Required evidence missing' },
  evidence_pending: { zh: '证据整理中', en: 'Evidence pending' },
  partial_coverage: { zh: '覆盖不完整', en: 'Coverage incomplete' },
  stale_evidence: { zh: '证据已延迟', en: 'Evidence delayed' },
  fallback_proxy_evidence: { zh: '仅有替代证据', en: 'Fallback evidence only' },
  weak_relevance: { zh: '相关性有限', en: 'Relevance limited' },
  missing_required_fields: { zh: '关键字段未补齐', en: 'Required fields missing' },
  provider_timeout: { zh: '外部证据暂不可用', en: 'External evidence temporarily unavailable' },
  provider_unavailable: { zh: '外部证据暂不可用', en: 'External evidence temporarily unavailable' },
  coverage_not_assembled: { zh: '证据尚未汇总', en: 'Coverage still assembling' },
};

function normalizeStatus(value: string | undefined): string {
  return String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_') || 'unknown';
}

function statusVariant(status: string): React.ComponentProps<typeof TerminalChip>['variant'] {
  if (status === 'available') return 'success';
  if (status === 'blocked') return 'danger';
  if (status === 'degraded') return 'caution';
  if (status === 'missing') return 'neutral';
  if (status === 'pending') return 'info';
  return 'neutral';
}

function domainLabel(domain: AnalysisEvidenceCoverageDomain, locale: EvidenceCoverageLocale): string {
  return DOMAIN_LABELS[domain][locale];
}

function statusLabel(status: string, locale: EvidenceCoverageLocale): string {
  return STATUS_LABELS[status]?.[locale] || STATUS_LABELS.unknown[locale];
}

function unique(values: Array<string | null | undefined>): string[] {
  const seen = new Set<string>();
  const items: string[] = [];
  values.forEach((value) => {
    const text = value?.trim();
    if (!text || seen.has(text)) return;
    seen.add(text);
    items.push(text);
  });
  return items;
}

function reasonLabel(reason: string, locale: EvidenceCoverageLocale): string {
  const normalized = String(reason || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
  return REASON_LABELS[normalized]?.[locale] || sanitizeUserFacingDataIssue(reason, locale);
}

function buildNote(
  domain: AnalysisEvidenceCoverageDomain,
  entry: AnalysisEvidenceCoverageEntry | null | undefined,
  locale: EvidenceCoverageLocale,
): string | null {
  const status = normalizeStatus(entry?.status);
  if (status === 'available' || status === 'not_applicable') return null;
  const nextEvidence = unique(entry?.nextEvidenceNeeded || []);
  if (nextEvidence.length) {
    return `${domainLabel(domain, locale)}：${nextEvidence[0]}`;
  }
  const reasons = unique((entry?.missingReasons || []).map((reason) => reasonLabel(reason, locale)));
  if (reasons.length) {
    return `${domainLabel(domain, locale)}：${reasons[0]}`;
  }
  return null;
}

function domainEntry(
  frame: AnalysisEvidenceCoverageFrame,
  domain: AnalysisEvidenceCoverageDomain,
): AnalysisEvidenceCoverageEntry {
  return frame[domain] || { status: 'missing', missingReasons: ['evidence_missing'] };
}

const ConsumerEvidenceCoverageStrip: React.FC<ConsumerEvidenceCoverageStripProps> = ({
  frame,
  locale = 'zh',
  title,
  testId,
  className,
}) => {
  const isEnglish = locale === 'en';
  const resolvedTitle = title || (isEnglish ? 'Evidence coverage' : '证据覆盖');

  if (!frame || Object.keys(frame).length === 0) {
    return (
      <section
        data-testid={testId}
        className={cn(
          'rounded-lg border border-white/[0.08] bg-white/[0.025] px-3 py-2.5',
          className,
        )}
      >
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-white/42">
            {resolvedTitle}
          </span>
          <TerminalChip variant="danger">
            {isEnglish ? 'Coverage unavailable' : '覆盖不可用'}
          </TerminalChip>
        </div>
        <p className="mt-2 text-xs leading-5 text-white/64">
          {isEnglish
            ? 'Evidence coverage is unavailable. Do not treat the current conclusion as research-ready.'
            : '证据覆盖暂不可用，当前结论不能视为研究就绪。'}
        </p>
      </section>
    );
  }

  const primaryEntries = PRIMARY_DOMAINS.map((domain) => ({
    domain,
    entry: domainEntry(frame, domain),
    status: normalizeStatus(domainEntry(frame, domain).status),
  }));
  const secondaryEntries = SECONDARY_DOMAINS
    .map((domain) => {
      const entry = frame[domain];
      return entry ? { domain, entry, status: normalizeStatus(entry.status) } : null;
    })
    .filter((item): item is NonNullable<typeof item> => Boolean(item));
  const notes = unique([
    ...primaryEntries.map((item) => buildNote(item.domain, item.entry, locale)),
    ...secondaryEntries.map((item) => buildNote(item.domain, item.entry, locale)),
  ]);
  const summaryLine = notes.length
    ? notes.slice(0, 2).join(isEnglish ? ' · ' : '；')
    : (isEnglish ? 'Primary research evidence is available within the current consumer boundary.' : '主要研究证据已按当前消费边界给出。');
  const showDisclosure = notes.length > 2 || secondaryEntries.length > 0;

  return (
    <section
      data-testid={testId}
      className={cn(
        'rounded-lg border border-white/[0.08] bg-white/[0.025] px-3 py-2.5',
        className,
      )}
    >
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-white/42">
          {resolvedTitle}
        </span>
        {primaryEntries.map(({ domain, status }) => (
          <TerminalChip key={domain} variant={statusVariant(status)}>
            {domainLabel(domain, locale)}
            {' '}
            {statusLabel(status, locale)}
          </TerminalChip>
        ))}
      </div>
      <p className="mt-2 text-xs leading-5 text-white/64">
        {summaryLine}
      </p>
      {showDisclosure ? (
        <details className="mt-2 rounded-[10px] border border-white/[0.06] bg-white/[0.015] px-3 py-2.5">
          <summary className="cursor-pointer list-none text-[11px] font-medium text-white/52 marker:hidden">
            {isEnglish ? 'More evidence details' : '更多证据细节'}
          </summary>
          <div className="mt-2 flex min-w-0 flex-col gap-2">
            {secondaryEntries.length ? (
              <div className="flex min-w-0 flex-wrap gap-2">
                {secondaryEntries.map(({ domain, status }) => (
                  <TerminalChip key={domain} variant={statusVariant(status)}>
                    {domainLabel(domain, locale)}
                    {' '}
                    {statusLabel(status, locale)}
                  </TerminalChip>
                ))}
              </div>
            ) : null}
            {notes.length ? (
              <div className="space-y-1.5">
                {notes.map((note) => (
                  <p key={note} className="text-[11px] leading-5 text-white/60">
                    {note}
                  </p>
                ))}
              </div>
            ) : null}
          </div>
        </details>
      ) : null}
    </section>
  );
};

export default ConsumerEvidenceCoverageStrip;
