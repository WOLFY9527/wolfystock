import type { ReactElement } from 'react';
import { TerminalChip } from '../terminal/TerminalPrimitives';
import type {
  ScannerCandidate,
  ScannerCoverageSummary,
  ScannerProviderDiagnostics,
  ScannerRunDetail,
} from '../../types/scanner';
import {
  isRawConsumerDataStateText,
  sanitizeConsumerDataStateText,
} from '../../utils/consumerDataStateVocabulary';
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

function formatUniverseNote(note: string, language: 'zh' | 'en'): string | null {
  const text = note.trim();
  if (!text) return null;
  const themeMatch = text.match(/^theme\s+universe:\s*(.+?)(?:\s*·\s*(\d+)\s*symbols?)?\.?$/i);
  if (themeMatch) {
    const theme = themeMatch[1]?.trim() || (language === 'en' ? 'selected theme' : '所选主题');
    const count = themeMatch[2]?.trim();
    return language === 'en'
      ? `Theme scope: ${theme}${count ? ` · ${count} names` : ''}.`
      : `主题标的范围：${theme}${count ? ` · ${count} 个标的` : ''}。`;
  }
  const cleaned = text
    .replace(/\bprofile\s+default\s+universe\b/gi, language === 'en' ? 'default scope' : '默认标的范围')
    .replace(/\bcustom\s+symbol\s+universe\b/gi, language === 'en' ? 'custom symbol scope' : '自定义标的范围')
    .replace(/\buniverse\b/gi, language === 'en' ? 'scope' : '标的范围')
    .replace(/\bsymbols?\b/gi, language === 'en' ? 'names' : '个标的')
    .replace(/\s+\./g, '.');
  return sanitizeScannerDiagnosticNote(cleaned, language);
}

function sanitizeScannerDiagnosticNote(note: string, language: 'zh' | 'en'): string | null {
  const text = note.trim();
  if (!text) return null;
  if (isRawConsumerDataStateText(text)) {
    return sanitizeConsumerDataStateText(text, 'missing');
  }
  const sanitized = sanitizeUserFacingDataIssue(text, language);
  return sanitized || null;
}

function toDisplayText(value: unknown): string | null {
  if (value == null) return null;
  if (typeof value === 'string') return value.trim() || null;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return null;
}

const restrictedDiagnosticTextPattern = /(?:synthetic_(?:provider_url|cache_key|request_id|debug_reason|score_trace|diagnostic_window|provider_payload_label)|\b(?:provider_url|cache_key|request_id|debug_reason|score_trace|diagnostic_window|provider_payload|raw_payload|raw_provider_payload)\b|https?:\/\/|\?token=|\b(?:traceback|stack trace|authorization|bearer|cookie|api[_-]?key|secret|credential|sourceAuthorityAllowed|scoreContributionAllowed)\b)/i;

type AiDiagnosticDisplayEntry = {
  key: string;
  label: string;
  value: string;
};

function isRestrictedDiagnosticEntry(key: string, value: string | null): boolean {
  const normalizedKey = key.trim();
  const text = `${normalizedKey} ${value || ''}`;
  return normalizedKey.includes('_') || restrictedDiagnosticTextPattern.test(text);
}

function restrictedDiagnosticLabel(language: 'zh' | 'en'): AiDiagnosticDisplayEntry {
  return {
    key: 'restricted-diagnostics',
    label: language === 'en' ? 'Diagnostic details retained' : '诊断详情已保留',
    value: language === 'en' ? 'Operator review only' : '仅限运维核查',
  };
}

function getAiDiagnosticDisplayEntries(
  aiDiagnostics: Record<string, unknown> | null,
  language: 'zh' | 'en',
): AiDiagnosticDisplayEntry[] {
  if (!aiDiagnostics) return [];
  let hasRestrictedDiagnostic = false;
  const entries = Object.entries(aiDiagnostics)
    .reduce<AiDiagnosticDisplayEntry[]>((items, [key, rawValue]) => {
      const value = toDisplayText(rawValue);
      if (isRestrictedDiagnosticEntry(key, value)) {
        hasRestrictedDiagnostic = true;
        return items;
      }
      if (!value) return items;
      items.push({ key, label: key, value });
      return items;
    }, [])
    .slice(0, 5);

  return hasRestrictedDiagnostic ? [restrictedDiagnosticLabel(language), ...entries].slice(0, 6) : entries;
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

export const ScannerDiagnosticsPanel = Object.assign(function ScannerDiagnosticsPanel({
  runDetail,
  language,
}: ScannerDiagnosticsPanelProps) {
  const universeNotes = runDetail.universeNotes
    .map((note) => formatUniverseNote(note, language))
    .filter((note): note is string => Boolean(note));
  const coverage = getRunCoverageSummary(runDetail);
  const provider = getRunProviderDiagnostics(runDetail);
  const aiDiagnostics = getAiDiagnostics(runDetail);
  const aiDiagnosticDisplayEntries = getAiDiagnosticDisplayEntries(aiDiagnostics, language);
  const hasAnyDiagnostics = hasRunDiagnosticsContent(runDetail);

  if (!hasAnyDiagnostics) return null;

  return (
    <section data-testid="scanner-diagnostics-panel" className="mt-2 border-t border-white/10 pt-1">
      <h3 className="text-[10px] font-bold uppercase tracking-widest text-white/40">
        {language === 'en' ? 'Data status' : '数据状态'}
      </h3>
      <div className="mt-1 grid gap-x-4 gap-y-0 lg:grid-cols-2">
        {coverage ? (
          <section className="min-w-0 border-t border-white/8 py-2">
            <h5 className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-white/38">
              {language === 'en' ? 'Coverage summary' : '覆盖摘要'}
            </h5>
            <div className="flex flex-wrap gap-2">
              <TerminalChip variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
                <span className="shrink-0 text-white/36">{language === 'en' ? 'Input' : '输入'}</span>
                <span className="min-w-0 truncate">{String(coverage.inputUniverseSize)}</span>
              </TerminalChip>
              <TerminalChip variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
                <span className="shrink-0 text-white/36">{language === 'en' ? 'Liquidity' : '流动性后'}</span>
                <span className="min-w-0 truncate">{String(coverage.eligibleAfterLiquidityFilter)}</span>
              </TerminalChip>
              <TerminalChip variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
                <span className="shrink-0 text-white/36">{language === 'en' ? 'Data OK' : '数据可用'}</span>
                <span className="min-w-0 truncate">{String(coverage.eligibleAfterDataAvailabilityFilter)}</span>
              </TerminalChip>
              <TerminalChip variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
                <span className="shrink-0 text-white/36">{language === 'en' ? 'Ranked' : '已排名'}</span>
                <span className="min-w-0 truncate">{String(coverage.rankedCandidateCount)}</span>
              </TerminalChip>
              <TerminalChip variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
                <span className="shrink-0 text-white/36">{language === 'en' ? 'Selected' : '入选'}</span>
                <span className="min-w-0 truncate">{String(coverage.shortlistedCount)}</span>
              </TerminalChip>
              {coverage.likelyBottleneckLabel || coverage.likelyBottleneck ? (
                <TerminalChip variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
                  <span className="shrink-0 text-white/36">{language === 'en' ? 'Bottleneck' : '瓶颈'}</span>
                  <span className="min-w-0 truncate">{coverage.likelyBottleneckLabel || coverage.likelyBottleneck || ''}</span>
                </TerminalChip>
              ) : null}
            </div>
          </section>
        ) : null}
        {provider ? (
          <section className="min-w-0 border-t border-white/8 py-2">
            <h5 className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-white/38">
              {language === 'en' ? 'Source' : '来源'}
            </h5>
            <p className="text-xs leading-relaxed text-white/64">{formatProviderDiagnostics(provider, language)}</p>
          </section>
        ) : null}
        {universeNotes.length ? (
          <section className="min-w-0 border-t border-white/8 py-2">
            <h5 className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-white/38">
              {language === 'en' ? 'Scope' : '范围'}
            </h5>
            <ul className="space-y-1">
              {universeNotes.map((note) => (
                <li key={note} className="text-xs leading-relaxed text-white/64">
                  {note}
                </li>
              ))}
            </ul>
          </section>
        ) : null}
        {runDetail.scoringNotes.length ? (
          <section className="min-w-0 border-t border-white/8 py-2">
            <h5 className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-white/38">
              {language === 'en' ? 'Scoring' : '评分'}
            </h5>
            <ul className="space-y-1">
              {runDetail.scoringNotes.map((note) => {
                const safeNote = sanitizeScannerDiagnosticNote(note, language);
                if (!safeNote) return null;
                return (
                  <li key={note} className="text-xs leading-relaxed text-white/64">
                    {safeNote}
                  </li>
                );
              })}
            </ul>
          </section>
        ) : null}
        {hasReviewSummary(runDetail.reviewSummary) ? (
          <section className="min-w-0 border-t border-white/8 py-2">
            <h5 className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-white/38">
              {language === 'en' ? 'Review' : '复盘'}
            </h5>
            <div className="flex flex-wrap gap-2">
              <TerminalChip variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
                <span className="shrink-0 text-white/36">{language === 'en' ? 'Status' : '状态'}</span>
                <span className="min-w-0 truncate">{runDetail.reviewSummary.reviewStatus}</span>
              </TerminalChip>
              <TerminalChip variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
                <span className="shrink-0 text-white/36">{language === 'en' ? 'Reviewed' : '已复盘'}</span>
                <span className="min-w-0 truncate">
                  {`${runDetail.reviewSummary.reviewedCount}/${runDetail.reviewSummary.candidateCount}`}
                </span>
              </TerminalChip>
              {runDetail.reviewSummary.hitRatePct != null ? (
                <TerminalChip variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
                  <span className="shrink-0 text-white/36">{language === 'en' ? 'Hit rate' : '命中率'}</span>
                  <span className="min-w-0 truncate">{formatPercent(runDetail.reviewSummary.hitRatePct)}</span>
                </TerminalChip>
              ) : null}
              {runDetail.reviewSummary.avgReviewWindowReturnPct != null ? (
                <TerminalChip variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
                  <span className="shrink-0 text-white/36">{language === 'en' ? 'Avg return' : '平均收益'}</span>
                  <span className="min-w-0 truncate">{formatPercent(runDetail.reviewSummary.avgReviewWindowReturnPct)}</span>
                </TerminalChip>
              ) : null}
            </div>
          </section>
        ) : null}
        {hasComparison(runDetail.comparisonToPrevious) ? (
          <section className="min-w-0 border-t border-white/8 py-2">
            <h5 className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-white/38">
              {language === 'en' ? 'Previous run' : '相对上次'}
            </h5>
            <div className="flex flex-wrap gap-2">
              <TerminalChip variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
                <span className="shrink-0 text-white/36">{language === 'en' ? 'New' : '新增'}</span>
                <span className="min-w-0 truncate">{String(runDetail.comparisonToPrevious.newCount)}</span>
              </TerminalChip>
              <TerminalChip variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
                <span className="shrink-0 text-white/36">{language === 'en' ? 'Retained' : '保留'}</span>
                <span className="min-w-0 truncate">{String(runDetail.comparisonToPrevious.retainedCount)}</span>
              </TerminalChip>
              <TerminalChip variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
                <span className="shrink-0 text-white/36">{language === 'en' ? 'Dropped' : '移出'}</span>
                <span className="min-w-0 truncate">{String(runDetail.comparisonToPrevious.droppedCount)}</span>
              </TerminalChip>
            </div>
          </section>
        ) : null}
        {aiDiagnostics ? (
          <section className="min-w-0 border-t border-white/8 py-2">
            <h5 className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-white/38">
              {language === 'en' ? 'AI' : 'AI'}
            </h5>
            <div className="flex flex-wrap gap-2">
              {aiDiagnosticDisplayEntries
                .map(({ key, label, value }) => (
                  <TerminalChip key={key} variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
                    <span className="shrink-0 text-white/36">{label}</span>
                    <span className="min-w-0 truncate">{value}</span>
                  </TerminalChip>
                ))}
            </div>
          </section>
        ) : null}
      </div>
    </section>
  );
}, {
  toDisplayText,
  getRunCoverageSummary,
  getProviderDiagnostics,
  getRunProviderDiagnostics,
  getAiDiagnostics,
  formatProviderDiagnostics,
  hasRunDiagnosticsContent,
}) as ScannerDiagnosticsPanelComponent;
