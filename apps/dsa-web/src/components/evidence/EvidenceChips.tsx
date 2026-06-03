import {
  TerminalChip,
  TerminalDisclosure,
} from '../terminal/TerminalPrimitives';
import type { NormalizedEvidenceSummary } from '../../utils/evidenceDisplay';
import { cn } from '../../utils/cn';

type EvidenceChipsProps = {
  summary: NormalizedEvidenceSummary | null | undefined;
  audience?: 'user' | 'admin';
  maxLabels?: number;
  className?: string;
  'data-testid'?: string;
};

function chipVariantFromTone(tone: NormalizedEvidenceSummary['tone']) {
  switch (tone) {
    case 'success':
      return 'success';
    case 'danger':
      return 'danger';
    case 'warning':
      return 'caution';
    case 'info':
      return 'info';
    default:
      return 'neutral';
  }
}

export function EvidenceChips({
  summary,
  audience = 'user',
  maxLabels,
  className,
  'data-testid': dataTestId,
}: EvidenceChipsProps) {
  if (!summary) return null;

  const limitationLimit = maxLabels ?? (audience === 'admin' ? summary.limitationLabels.length : 2);
  const visibleLimitations = summary.limitationLabels
    .filter((label) => label !== summary.displayLabel && label !== summary.freshnessLabel)
    .slice(0, limitationLimit);
  const hasAdminDetails = audience === 'admin' && (summary.adminReasonCodes.length || summary.diagnostics);

  return (
    <div data-testid={dataTestId} className={cn('flex min-w-0 flex-wrap items-center gap-1.5', className)}>
      <TerminalChip variant={chipVariantFromTone(summary.tone)}>
        {summary.displayLabel}
      </TerminalChip>
      {summary.confidenceCap != null ? (
        <TerminalChip variant="neutral">
          {`置信上限 ${summary.confidenceCap}`}
        </TerminalChip>
      ) : null}
      {summary.freshnessLabel ? (
        <TerminalChip variant={summary.tone === 'danger' ? 'caution' : 'neutral'}>
          {summary.freshnessLabel}
        </TerminalChip>
      ) : null}
      {visibleLimitations.map((label) => (
        <TerminalChip key={label} variant="neutral">
          {label}
        </TerminalChip>
      ))}
      {hasAdminDetails ? (
        <div className="basis-full">
          <TerminalDisclosure
            title="管理诊断"
            summary={summary.adminReasonCodes.length ? `${summary.adminReasonCodes.length} 个原因码` : '展开查看'}
            className="mt-1"
          >
            <div className="mt-1 flex min-w-0 flex-wrap gap-1.5">
              {summary.adminReasonCodes.map((code) => (
                <TerminalChip key={code} variant="neutral">
                  {code}
                </TerminalChip>
              ))}
            </div>
            {summary.diagnostics ? (
              <pre className="mt-2 overflow-x-auto rounded-lg border border-white/[0.04] bg-black/20 p-2 text-[11px] text-white/45 no-scrollbar">
                {JSON.stringify(summary.diagnostics, null, 2)}
              </pre>
            ) : null}
          </TerminalDisclosure>
        </div>
      ) : null}
    </div>
  );
}
