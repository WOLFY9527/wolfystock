import type { ScannerCandidateResearchPacket as ScannerCandidateResearchPacketView } from '../../types/scanner';
import { consumerSafeReportText } from '../../utils/homeReportIdentity';
import { TerminalChip } from '../terminal/TerminalPrimitives';
import { FieldChip } from './ScannerDisplayAtoms';

type ResearchPacketVariant = 'row' | 'detail';

function safePacketText(value: unknown): string | null {
  const text = consumerSafeReportText(value, '').trim();
  return text && text !== '--' ? text : null;
}

function safePacketList(value?: string[] | null, limit = 4): string[] {
  if (!Array.isArray(value)) return [];
  const result: string[] = [];
  value.forEach((item) => {
    const text = safePacketText(item);
    if (text && !result.includes(text) && result.length < limit) {
      result.push(text);
    }
  });
  return result;
}

function hasVisiblePacket(packet?: ScannerCandidateResearchPacketView | null): boolean {
  return Boolean(
    safePacketText(packet?.whySurfaced)
    || safePacketText(packet?.researchNextStep)
    || safePacketText(packet?.rejectedOrLimitedReasonSafeLabel)
    || safePacketList(packet?.primaryEvidence, 1).length
    || safePacketList(packet?.limitingEvidence, 1).length
    || safePacketList(packet?.dataQualityNotes, 1).length,
  );
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
  if (!packet || !hasVisiblePacket(packet)) return null;

  const title = language === 'en' ? 'Research packet' : '研究包';
  const whySurfaced = safePacketText(packet.whySurfaced);
  const primaryEvidence = safePacketList(packet.primaryEvidence);
  const limitingEvidence = safePacketList(packet.limitingEvidence);
  const dataQualityNotes = safePacketList(packet.dataQualityNotes);
  const safeLabel = safePacketText(packet.rejectedOrLimitedReasonSafeLabel);
  const researchNextStep = safePacketText(packet.researchNextStep);
  const boundaryLabel = language === 'en' ? 'Research only' : '仅研究观察';

  if (variant === 'row') {
    return (
      <div data-testid={testId} className="mt-1.5 space-y-1.5">
        <div className="flex min-w-0 flex-wrap items-center gap-1.5">
          <span className="text-[10px] font-semibold uppercase text-white/36">{title}</span>
          {packet.observationOnly ? (
            <TerminalChip variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
              {boundaryLabel}
            </TerminalChip>
          ) : null}
        </div>
        {whySurfaced ? (
          <p className="line-clamp-2 text-[11px] leading-relaxed text-white/58">
            {whySurfaced}
          </p>
        ) : null}
        <div className="flex min-w-0 flex-wrap gap-1.5 text-[10px] text-white/46">
          {primaryEvidence.slice(0, 1).map((item) => (
            <TerminalChip key={`primary-${item}`} variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
              {item}
            </TerminalChip>
          ))}
          {limitingEvidence.slice(0, 1).map((item) => (
            <TerminalChip key={`limit-${item}`} variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
              {item}
            </TerminalChip>
          ))}
          {!primaryEvidence.length && safeLabel ? <span className="truncate">{safeLabel}</span> : null}
        </div>
      </div>
    );
  }

  return (
    <section data-testid={testId} className="grid gap-2 rounded-lg border border-white/8 bg-white/[0.015] p-3">
      <div className="flex min-w-0 items-center justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase text-white/40">
          {title}
        </p>
        {packet.observationOnly ? (
          <TerminalChip variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
            {boundaryLabel}
          </TerminalChip>
        ) : null}
      </div>
      {whySurfaced ? (
        <div className="grid gap-1">
          <p className="text-[10px] font-semibold uppercase text-white/36">
            {language === 'en' ? 'Why surfaced' : '为什么出现'}
          </p>
          <p className="text-xs leading-relaxed text-white/72">{whySurfaced}</p>
        </div>
      ) : null}
      {primaryEvidence.length ? (
        <div className="grid gap-1">
          <p className="text-[10px] font-semibold uppercase text-white/36">
            {language === 'en' ? 'Primary evidence' : '主要证据'}
          </p>
          <div className="flex min-w-0 flex-wrap gap-1.5">
            {primaryEvidence.map((item) => (
              <TerminalChip key={item} variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
                {item}
              </TerminalChip>
            ))}
          </div>
        </div>
      ) : null}
      {limitingEvidence.length ? (
        <div className="grid gap-1">
          <p className="text-[10px] font-semibold uppercase text-white/36">
            {language === 'en' ? 'Limits' : '限制因素'}
          </p>
          <div className="flex min-w-0 flex-wrap gap-1.5">
            {limitingEvidence.map((item) => (
              <TerminalChip key={item} variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
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
        <p className="text-xs leading-relaxed text-white/62">
          <span className="text-white/42">{language === 'en' ? 'Next:' : '下一步：'}</span>
          {researchNextStep}
        </p>
      ) : null}
    </section>
  );
}

export default ScannerCandidateResearchPacket;
