import type { ScannerCandidateResearchPacket as ScannerCandidateResearchPacketView } from '../../types/scanner';
import { consumerSafeReportText } from '../../utils/homeReportIdentity';
import { sanitizeUserFacingDataIssue } from '../../utils/userFacingDataIssues';
import { TerminalChip } from '../terminal/TerminalPrimitives';
import { FieldChip } from './ScannerDisplayAtoms';

type ResearchPacketVariant = 'row' | 'detail';
type ResearchSignalLabel = {
  label: string;
  tone?: 'neutral' | 'warning';
};

const PACKET_INTERNAL_COPY_PATTERN =
  /clean research handoff|evidence famil(?:y|ies)|business-quality review|peer group metadata|daily ohlcv|observation-only research readiness|personalized financial advice/i;

function safePacketText(value: unknown, language: 'zh' | 'en'): string | null {
  const raw = String(value ?? '').trim();
  const text = consumerSafeReportText(value, '').trim();
  if (!text || text === '--') return null;
  if (!raw || text !== raw) return text;
  if (PACKET_INTERNAL_COPY_PATTERN.test(raw)) {
    return sanitizeUserFacingDataIssue(raw, language);
  }
  return text;
}

function safePacketList(value: string[] | null | undefined, language: 'zh' | 'en', limit = 4): string[] {
  if (!Array.isArray(value)) return [];
  const result: string[] = [];
  value.forEach((item) => {
    const text = safePacketText(item, language);
    if (text && !result.includes(text) && result.length < limit) {
      result.push(text);
    }
  });
  return result;
}

function hasVisiblePacket(packet: ScannerCandidateResearchPacketView | null | undefined, language: 'zh' | 'en'): boolean {
  return Boolean(
    safePacketText(packet?.whySurfaced, language)
    || safePacketText(packet?.researchNextStep, language)
    || safePacketText(packet?.rejectedOrLimitedReasonSafeLabel, language)
    || safePacketList(packet?.primaryEvidence, language, 1).length
    || safePacketList(packet?.limitingEvidence, language, 1).length
    || safePacketList(packet?.dataQualityNotes, language, 1).length,
  );
}

function textIncludesAny(value: string, patterns: Array<string | RegExp>): boolean {
  return patterns.some((pattern) => (typeof pattern === 'string' ? value.includes(pattern) : pattern.test(value)));
}

function countMatching(items: string[], patterns: Array<string | RegExp>): number {
  return items.filter((item) => textIncludesAny(item.toLowerCase(), patterns)).length;
}

function buildResearchSignalLabels({
  primaryEvidence,
  limitingEvidence,
  dataQualityNotes,
  observationOnly,
  language,
}: {
  primaryEvidence: string[];
  limitingEvidence: string[];
  dataQualityNotes: string[];
  observationOnly: boolean;
  language: 'zh' | 'en';
}): ResearchSignalLabel[] {
  const allPrimary = primaryEvidence.join(' ').toLowerCase();
  const allNotes = dataQualityNotes.join(' ').toLowerCase();
  const availableCount = primaryEvidence.length;
  const missingCount = limitingEvidence.length;
  const partialCount = countMatching(dataQualityNotes, [/partial/i, /部分/]);
  const staleCount = countMatching(dataQualityNotes, [/stale/i, /过期|较早/]);
  const quoteDelayed = textIncludesAny(allNotes, [/delayed/i, /延迟|可能延迟/]);
  const quoteAvailable = textIncludesAny(allPrimary, [/quote/i, /报价/]);
  const contextAvailable = textIncludesAny(allPrimary, [/sector/i, /\betf\b/i, /theme/i, /行业|板块|主题|ETF/]);

  if (language === 'en') {
    return [
      {
        label: availableCount ? `Evidence available ${availableCount}` : 'Evidence pending',
      },
      ...(partialCount ? [{ label: `Evidence partial ${partialCount}`, tone: 'warning' as const }] : []),
      ...(staleCount ? [{ label: `Older evidence ${staleCount}`, tone: 'warning' as const }] : []),
      {
        label: missingCount ? `Evidence pending ${missingCount}` : 'Evidence available',
        tone: missingCount ? 'warning' : 'neutral',
      },
      {
        label: quoteDelayed
          ? 'Quote may be delayed'
          : quoteAvailable
            ? 'Quote available'
            : 'Quote pending',
        tone: quoteAvailable || quoteDelayed ? 'neutral' : 'warning',
      },
      {
        label: contextAvailable
          ? 'Sector/ETF context available'
          : 'Sector/ETF context pending',
        tone: contextAvailable ? 'neutral' : 'warning',
      },
      { label: 'Research brief available' },
      ...(observationOnly
        ? [
          { label: 'Observation only', tone: 'warning' as const },
          { label: 'Score pending', tone: 'warning' as const },
        ]
        : [{ label: 'Evidence available' }]),
    ];
  }

  return [
    {
      label: availableCount ? `证据可用 ${availableCount}` : '证据待补',
    },
    ...(partialCount ? [{ label: `证据部分可用 ${partialCount}`, tone: 'warning' as const }] : []),
    ...(staleCount ? [{ label: `较早证据 ${staleCount}`, tone: 'warning' as const }] : []),
    {
      label: missingCount ? `待补证据 ${missingCount}` : '证据可用',
      tone: missingCount ? 'warning' : 'neutral',
    },
    {
        label: quoteDelayed
          ? '报价可能延迟'
          : quoteAvailable
            ? '报价可用'
            : '报价待补',
        tone: quoteAvailable || quoteDelayed ? 'neutral' : 'warning',
      },
      {
        label: contextAvailable
          ? '行业/ETF线索可用'
          : '行业/ETF线索待补',
        tone: contextAvailable ? 'neutral' : 'warning',
      },
    { label: '研究包可用' },
    ...(observationOnly
      ? [
        { label: '仅观察', tone: 'warning' as const },
        { label: '评分待确认', tone: 'warning' as const },
      ]
      : [{ label: '证据可用' }]),
  ];
}

export function ScannerCandidateResearchPacket({
  packet,
  language,
  variant = 'detail',
  testId,
}: {
  packet?: ScannerCandidateResearchPacketView | null;
  language: 'zh' | 'en';
  variant?: ResearchPacketVariant;
  testId?: string;
}) {
  if (!packet || !hasVisiblePacket(packet, language)) return null;

  const title = language === 'en' ? 'Research brief' : '研究资料';
  const whySurfaced = safePacketText(packet.whySurfaced, language);
  const primaryEvidence = safePacketList(packet.primaryEvidence, language);
  const limitingEvidence = safePacketList(packet.limitingEvidence, language);
  const dataQualityNotes = safePacketList(packet.dataQualityNotes, language);
  const safeLabel = safePacketText(packet.rejectedOrLimitedReasonSafeLabel, language);
  const researchNextStep = safePacketText(packet.researchNextStep, language);
  const boundaryLabel = language === 'en' ? 'Research only' : '仅研究观察';
  const researchSignalTitle = language === 'en' ? 'Research signal' : '研究信号';
  const researchSignalLabels = buildResearchSignalLabels({
    primaryEvidence,
    limitingEvidence,
    dataQualityNotes,
    observationOnly: packet.observationOnly === true,
    language,
  });

  if (variant === 'row') {
    return (
      <div data-testid={testId} className="mt-1.5 space-y-1.5">
        <div className="flex min-w-0 flex-wrap items-center gap-1.5">
          <span className="text-[10px] font-semibold uppercase text-[color:var(--wolfy-text-muted)]">{researchSignalTitle}</span>
          <span className="text-[10px] font-semibold uppercase text-[color:var(--wolfy-text-muted)]">{title}</span>
          {packet.observationOnly ? (
            <TerminalChip variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-[color:var(--wolfy-text-primary)]">
              {boundaryLabel}
            </TerminalChip>
          ) : null}
        </div>
        {whySurfaced ? (
          <p className="line-clamp-2 text-[11px] leading-relaxed text-[color:var(--wolfy-text-secondary)]">
            {whySurfaced}
          </p>
        ) : null}
        <div className="flex min-w-0 flex-wrap gap-1.5 text-[10px] text-[color:var(--wolfy-text-muted)]">
          {researchSignalLabels.map((item) => (
            <TerminalChip
              key={`signal-${item.label}`}
              variant="neutral"
              className={`px-1.5 py-0.5 text-[10px] font-sans ${
                item.tone === 'warning' ? 'text-[color:var(--state-warning-text)]' : 'text-[color:var(--wolfy-text-primary)]'
              }`}
            >
              {item.label}
            </TerminalChip>
          ))}
        </div>
        <div className="flex min-w-0 flex-wrap gap-1.5 text-[10px] text-[color:var(--wolfy-text-muted)]">
          {primaryEvidence.slice(0, 1).map((item) => (
            <TerminalChip key={`primary-${item}`} variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-[color:var(--wolfy-text-primary)]">
              {item}
            </TerminalChip>
          ))}
          {limitingEvidence.slice(0, 1).map((item) => (
            <TerminalChip key={`limit-${item}`} variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-[color:var(--wolfy-text-primary)]">
              {item}
            </TerminalChip>
          ))}
          {!primaryEvidence.length && safeLabel ? <span className="truncate">{safeLabel}</span> : null}
        </div>
      </div>
    );
  }

  return (
    <section data-testid={testId} className="grid gap-2 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3">
      <div className="flex min-w-0 items-center justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase text-[color:var(--wolfy-text-muted)]">
          {title}
        </p>
        {packet.observationOnly ? (
          <TerminalChip variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-[color:var(--wolfy-text-primary)]">
            {boundaryLabel}
          </TerminalChip>
        ) : null}
      </div>
      <div className="grid gap-1 rounded-md border border-[color:var(--wolfy-border-subtle)] bg-black/10 p-2">
        <p className="text-[10px] font-semibold uppercase text-[color:var(--wolfy-text-muted)]">
          {researchSignalTitle}
        </p>
        <div className="flex min-w-0 flex-wrap gap-1.5">
          {researchSignalLabels.map((item) => (
            <TerminalChip
              key={`signal-${item.label}`}
              variant="neutral"
              className={`px-1.5 py-0.5 text-[10px] font-sans ${
                item.tone === 'warning' ? 'text-[color:var(--state-warning-text)]' : 'text-[color:var(--wolfy-text-primary)]'
              }`}
            >
              {item.label}
            </TerminalChip>
          ))}
        </div>
      </div>
      {whySurfaced ? (
        <div className="grid gap-1">
          <p className="text-[10px] font-semibold uppercase text-[color:var(--wolfy-text-muted)]">
            {language === 'en' ? 'Why surfaced' : '为什么出现'}
          </p>
          <p className="text-xs leading-relaxed text-[color:var(--wolfy-text-primary)]">{whySurfaced}</p>
        </div>
      ) : null}
      {primaryEvidence.length ? (
        <div className="grid gap-1">
          <p className="text-[10px] font-semibold uppercase text-[color:var(--wolfy-text-muted)]">
            {language === 'en' ? 'Primary evidence' : '主要证据'}
          </p>
          <div className="flex min-w-0 flex-wrap gap-1.5">
            {primaryEvidence.map((item) => (
              <TerminalChip key={item} variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-[color:var(--wolfy-text-primary)]">
                {item}
              </TerminalChip>
            ))}
          </div>
        </div>
      ) : null}
      {limitingEvidence.length ? (
        <div className="grid gap-1">
          <p className="text-[10px] font-semibold uppercase text-[color:var(--wolfy-text-muted)]">
            {language === 'en' ? 'Limits' : '限制因素'}
          </p>
          <div className="flex min-w-0 flex-wrap gap-1.5">
            {limitingEvidence.map((item) => (
              <TerminalChip key={item} variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-[color:var(--wolfy-text-primary)]">
                {item}
              </TerminalChip>
            ))}
          </div>
        </div>
      ) : null}
      {dataQualityNotes.length || safeLabel ? (
        <div className="flex min-w-0 flex-wrap gap-1.5">
          {dataQualityNotes.slice(0, 3).map((item) => (
            <FieldChip key={item} label={language === 'en' ? 'Data quality' : '数据质量'} value={item} />
          ))}
          {safeLabel ? <FieldChip label={language === 'en' ? 'Status' : '状态'} value={safeLabel} /> : null}
        </div>
      ) : null}
      {researchNextStep ? (
        <p className="text-xs leading-relaxed text-[color:var(--wolfy-text-secondary)]">
          <span className="text-[color:var(--wolfy-text-muted)]">{language === 'en' ? 'Next:' : '下一步：'}</span>
          {researchNextStep}
        </p>
      ) : null}
    </section>
  );
}

export default ScannerCandidateResearchPacket;
