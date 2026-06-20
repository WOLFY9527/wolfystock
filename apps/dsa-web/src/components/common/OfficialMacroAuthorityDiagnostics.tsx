import type React from 'react';
import { TerminalChip, TerminalDisclosure, TerminalSectionHeader } from '../terminal/TerminalPrimitives';
import { cn } from '../../utils/cn';
import type { OfficialMacroAuthorityDiagnosticsView, OfficialMacroLocale } from './officialMacroAuthorityDiagnosticsData';
import { CHIP_LABELS } from './officialMacroAuthorityDiagnosticsData';

export const OfficialMacroAuthorityDiagnostics: React.FC<{
  testId: string;
  title: string;
  view: OfficialMacroAuthorityDiagnosticsView;
  locale?: OfficialMacroLocale;
}> = ({ testId, title, view, locale = 'zh' }) => {
  const resolvedCount = view.rows.filter((row) => !row.missing).length;
  const labels = CHIP_LABELS[locale];
  const countRowsWithChip = (label: string) => view.rows.filter((row) => row.chips.some((chip) => chip.label === label)).length;
  const officialCount = countRowsWithChip(labels.official);
  const proxyCount = countRowsWithChip(labels.proxyOnly);
  const fallbackCount = countRowsWithChip(labels.fallback);
  const rejectedCount = countRowsWithChip(labels.rejected);
  const observationOnlyCount = countRowsWithChip(labels.observationOnly);
  const scoreEligibleCount = countRowsWithChip(labels.scoreEligible);
  const gapCount = view.rows.filter((row) => row.missing).length;
  const hasGapsOrRejections = gapCount > 0 || rejectedCount > 0;

  return (
    <TerminalDisclosure
      data-testid={testId}
      title={title}
      summary={`可计分 ${scoreEligibleCount} · 官方 ${officialCount} · 代理/观察 ${proxyCount + observationOnlyCount} · 缺口 ${gapCount + rejectedCount}`}
      className="bg-white/[0.02]"
    >
      <div className="grid min-w-0 gap-3">
        <TerminalSectionHeader
          eyebrow="官方宏观"
          title="来源覆盖与 authority 细节"
          action={<TerminalChip variant="neutral">{`覆盖 ${resolvedCount}/${view.scopeSeries.length}`}</TerminalChip>}
        />

        <div className="flex min-w-0 flex-wrap gap-1.5">
          <TerminalChip variant="success">可计分 {scoreEligibleCount}</TerminalChip>
          <TerminalChip variant="info">官方覆盖 {officialCount}</TerminalChip>
          <TerminalChip variant="caution">代理/观察 {proxyCount + observationOnlyCount}</TerminalChip>
          <TerminalChip variant="caution">备用 {fallbackCount}</TerminalChip>
          <TerminalChip variant={hasGapsOrRejections ? 'danger' : 'neutral'}>
            {hasGapsOrRejections ? `缺口 ${gapCount + rejectedCount}` : '暂无缺口'}
          </TerminalChip>
        </div>

        <div className="flex min-w-0 flex-wrap gap-1.5">
          {view.scopeSeries.map((seriesId) => (
            <TerminalChip key={seriesId} variant="neutral" className="font-mono text-[10px]">
              {seriesId}
            </TerminalChip>
          ))}
        </div>
        {view.rows.map((row) => (
          <div
            key={row.key}
            className={cn(
              'rounded-lg border border-white/[0.06] bg-black/10 px-3 py-2.5',
              row.missing ? 'opacity-80' : '',
            )}
          >
            <div className="flex min-w-0 flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-white/84">{row.label}</p>
                <p className="truncate font-mono text-[10px] uppercase tracking-[0.18em] text-white/34">{row.seriesId}</p>
                <p className="mt-1 text-[11px] leading-5 text-white/45">{row.meta}</p>
                {row.reasonText ? (
                  <p className="mt-1 break-words font-mono text-[10px] leading-5 text-amber-200/80">{row.reasonText}</p>
                ) : null}
              </div>
              <div className="flex min-w-0 flex-wrap gap-1.5 lg:max-w-[42%] lg:justify-end">
                {row.chips.map((chip) => (
                  <TerminalChip key={`${row.key}-${chip.label}`} variant={chip.variant}>
                    {chip.label}
                  </TerminalChip>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    </TerminalDisclosure>
  );
};
