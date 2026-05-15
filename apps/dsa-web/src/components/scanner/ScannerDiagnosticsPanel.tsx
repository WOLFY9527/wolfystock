import type { ReactElement, ReactNode } from 'react';
import { TerminalChip, TerminalPanel } from '../terminal';
import type {
  ScannerCandidate,
  ScannerCoverageSummary,
  ScannerProviderDiagnostics,
  ScannerRunDetail,
} from '../../types/scanner';
import { sanitizeUserFacingDataIssue } from '../../utils/userFacingDataIssues';

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function hasReviewSummary(review?: ScannerRunDetail['reviewSummary'] | null): boolean {
  return Boolean(review?.available || review?.reviewedCount || review?.candidateCount);
}

function hasComparison(comparison?: ScannerRunDetail['comparisonToPrevious'] | null): boolean {
  return Boolean(comparison?.available || comparison?.newCount || comparison?.retainedCount || comparison?.droppedCount);
}

function formatPercent(value?: number | null): string {
  if (value == null || !Number.isFinite(value)) return '--';
  return `${value > 0 ? '+' : ''}${value.toFixed(1)}%`;
}

function DiagnosticsFieldChip({ label, value }: { label: string; value: string }) {
  return (
    <TerminalChip variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
      <span className="shrink-0 text-white/36">{label}</span>
      <span className="min-w-0 truncate">{value}</span>
    </TerminalChip>
  );
}

function DiagnosticsSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <TerminalPanel as="section" dense className="p-2.5">
      <h5 className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-white/38">{title}</h5>
      {children}
    </TerminalPanel>
  );
}

function DiagnosticsNotes({ notes }: { notes: string[] }) {
  return (
    <ul className="space-y-1">
      {notes.map((note) => (
        <li key={note} className="text-xs leading-relaxed text-white/64">
          {note}
        </li>
      ))}
    </ul>
  );
}

function toDisplayText(value: unknown): string | null {
  if (value == null) return null;
  if (typeof value === 'string') return value.trim() || null;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return null;
}

function getRunCoverageSummary(runDetail: ScannerRunDetail): ScannerCoverageSummary | null {
  const diagnostics = runDetail.diagnostics || {};
  return isRecord(diagnostics.coverageSummary) ? diagnostics.coverageSummary as unknown as ScannerCoverageSummary : null;
}

function getProviderDiagnostics(
  value?: ScannerRunDetail['diagnostics'] | ScannerCandidate['diagnostics'],
): ScannerProviderDiagnostics | null {
  if (!value) return null;
  const diagnostics = value as Record<string, unknown>;
  return isRecord(diagnostics.providerDiagnostics) ? diagnostics.providerDiagnostics as unknown as ScannerProviderDiagnostics : null;
}

function getRunProviderDiagnostics(runDetail: ScannerRunDetail): ScannerProviderDiagnostics | null {
  return getProviderDiagnostics(runDetail.diagnostics);
}

function getAiDiagnostics(runDetail: ScannerRunDetail): Record<string, unknown> | null {
  const diagnostics = runDetail.diagnostics || {};
  return isRecord(diagnostics.aiInterpretation) ? diagnostics.aiInterpretation : null;
}

function formatProviderDiagnostics(provider: ScannerProviderDiagnostics | null, language: 'zh' | 'en'): string | null {
  if (!provider) return null;
  const hasExternalIssue = Boolean(provider.providerFailureCount || provider.providerWarnings?.length);
  const hasMissingData = Boolean(provider.missingDataSymbolCount);
  return [
    hasExternalIssue ? sanitizeUserFacingDataIssue('provider_timeout', language) : null,
    hasMissingData ? sanitizeUserFacingDataIssue('missing_data', language) : null,
    provider.fallbackOccurred ? (language === 'en' ? 'Fallback data' : '备用数据') : null,
    !hasExternalIssue && !hasMissingData && !provider.fallbackOccurred
      ? (language === 'en' ? 'Data ready for observation' : '数据可用于观察')
      : null,
  ].filter(Boolean).join(' · ');
}

function hasRunDiagnosticsContent(runDetail: ScannerRunDetail): boolean {
  const coverage = getRunCoverageSummary(runDetail);
  const provider = getRunProviderDiagnostics(runDetail);
  const aiDiagnostics = getAiDiagnostics(runDetail);
  return Boolean(
    coverage
      || provider
      || runDetail.universeNotes.length
      || runDetail.scoringNotes.length
      || hasReviewSummary(runDetail.reviewSummary)
      || hasComparison(runDetail.comparisonToPrevious)
      || aiDiagnostics,
  );
}

type ScannerDiagnosticsPanelProps = {
  runDetail: ScannerRunDetail;
  language: 'zh' | 'en';
};

type ScannerDiagnosticsPanelComponent = ((props: ScannerDiagnosticsPanelProps) => ReactElement | null) & {
  toDisplayText: typeof toDisplayText;
  getRunCoverageSummary: typeof getRunCoverageSummary;
  getProviderDiagnostics: typeof getProviderDiagnostics;
  getRunProviderDiagnostics: typeof getRunProviderDiagnostics;
  getAiDiagnostics: typeof getAiDiagnostics;
  formatProviderDiagnostics: typeof formatProviderDiagnostics;
  hasRunDiagnosticsContent: typeof hasRunDiagnosticsContent;
};

function ScannerDiagnosticsPanelComponentImpl({ runDetail, language }: ScannerDiagnosticsPanelProps) {
  const coverage = getRunCoverageSummary(runDetail);
  const provider = getRunProviderDiagnostics(runDetail);
  const aiDiagnostics = getAiDiagnostics(runDetail);
  const hasAnyDiagnostics = hasRunDiagnosticsContent(runDetail);

  if (!hasAnyDiagnostics) return null;

  return (
    <section data-testid="scanner-diagnostics-panel" className="mt-3 rounded-xl border border-white/5 bg-white/[0.015] p-3">
      <h3 className="text-[10px] font-bold uppercase tracking-widest text-white/40">
        {language === 'en' ? 'Data status' : '数据状态'}
      </h3>
      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        {coverage ? (
          <DiagnosticsSection title={language === 'en' ? 'Coverage summary' : '覆盖摘要'}>
            <div className="flex flex-wrap gap-2">
              <DiagnosticsFieldChip label={language === 'en' ? 'Input' : '输入'} value={String(coverage.inputUniverseSize)} />
              <DiagnosticsFieldChip label={language === 'en' ? 'Liquidity' : '流动性后'} value={String(coverage.eligibleAfterLiquidityFilter)} />
              <DiagnosticsFieldChip label={language === 'en' ? 'Data OK' : '数据可用'} value={String(coverage.eligibleAfterDataAvailabilityFilter)} />
              <DiagnosticsFieldChip label={language === 'en' ? 'Ranked' : '已排名'} value={String(coverage.rankedCandidateCount)} />
              <DiagnosticsFieldChip label={language === 'en' ? 'Selected' : '入选'} value={String(coverage.shortlistedCount)} />
              {coverage.likelyBottleneckLabel || coverage.likelyBottleneck ? (
                <DiagnosticsFieldChip
                  label={language === 'en' ? 'Bottleneck' : '瓶颈'}
                  value={coverage.likelyBottleneckLabel || coverage.likelyBottleneck || ''}
                />
              ) : null}
            </div>
          </DiagnosticsSection>
        ) : null}
        {provider ? (
          <DiagnosticsSection title={language === 'en' ? 'Source' : '来源'}>
            <p className="text-xs leading-relaxed text-white/64">{formatProviderDiagnostics(provider, language)}</p>
          </DiagnosticsSection>
        ) : null}
        {runDetail.universeNotes.length ? (
          <DiagnosticsSection title={language === 'en' ? 'Universe' : '范围'}>
            <DiagnosticsNotes notes={runDetail.universeNotes} />
          </DiagnosticsSection>
        ) : null}
        {runDetail.scoringNotes.length ? (
          <DiagnosticsSection title={language === 'en' ? 'Scoring' : '评分'}>
            <DiagnosticsNotes notes={runDetail.scoringNotes} />
          </DiagnosticsSection>
        ) : null}
        {hasReviewSummary(runDetail.reviewSummary) ? (
          <DiagnosticsSection title={language === 'en' ? 'Review' : '复盘'}>
            <div className="flex flex-wrap gap-2">
              <DiagnosticsFieldChip label={language === 'en' ? 'Status' : '状态'} value={runDetail.reviewSummary.reviewStatus} />
              <DiagnosticsFieldChip
                label={language === 'en' ? 'Reviewed' : '已复盘'}
                value={`${runDetail.reviewSummary.reviewedCount}/${runDetail.reviewSummary.candidateCount}`}
              />
              {runDetail.reviewSummary.hitRatePct != null ? (
                <DiagnosticsFieldChip label={language === 'en' ? 'Hit rate' : '命中率'} value={formatPercent(runDetail.reviewSummary.hitRatePct)} />
              ) : null}
              {runDetail.reviewSummary.avgReviewWindowReturnPct != null ? (
                <DiagnosticsFieldChip
                  label={language === 'en' ? 'Avg return' : '平均收益'}
                  value={formatPercent(runDetail.reviewSummary.avgReviewWindowReturnPct)}
                />
              ) : null}
            </div>
          </DiagnosticsSection>
        ) : null}
        {hasComparison(runDetail.comparisonToPrevious) ? (
          <DiagnosticsSection title={language === 'en' ? 'Previous run' : '相对上次'}>
            <div className="flex flex-wrap gap-2">
              <DiagnosticsFieldChip label={language === 'en' ? 'New' : '新增'} value={String(runDetail.comparisonToPrevious.newCount)} />
              <DiagnosticsFieldChip label={language === 'en' ? 'Retained' : '保留'} value={String(runDetail.comparisonToPrevious.retainedCount)} />
              <DiagnosticsFieldChip label={language === 'en' ? 'Dropped' : '移出'} value={String(runDetail.comparisonToPrevious.droppedCount)} />
            </div>
          </DiagnosticsSection>
        ) : null}
        {aiDiagnostics ? (
          <DiagnosticsSection title={language === 'en' ? 'AI' : 'AI'}>
            <div className="flex flex-wrap gap-2">
              {Object.entries(aiDiagnostics)
                .map(([key, value]) => [key, toDisplayText(value)] as const)
                .filter((entry): entry is readonly [string, string] => Boolean(entry[1]))
                .slice(0, 6)
                .map(([key, value]) => <DiagnosticsFieldChip key={key} label={key} value={value} />)}
            </div>
          </DiagnosticsSection>
        ) : null}
      </div>
    </section>
  );
}

export const ScannerDiagnosticsPanel = ScannerDiagnosticsPanelComponentImpl as ScannerDiagnosticsPanelComponent;

ScannerDiagnosticsPanel.toDisplayText = toDisplayText;
ScannerDiagnosticsPanel.getRunCoverageSummary = getRunCoverageSummary;
ScannerDiagnosticsPanel.getProviderDiagnostics = getProviderDiagnostics;
ScannerDiagnosticsPanel.getRunProviderDiagnostics = getRunProviderDiagnostics;
ScannerDiagnosticsPanel.getAiDiagnostics = getAiDiagnostics;
ScannerDiagnosticsPanel.formatProviderDiagnostics = formatProviderDiagnostics;
ScannerDiagnosticsPanel.hasRunDiagnosticsContent = hasRunDiagnosticsContent;
