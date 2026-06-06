import type { ComponentProps } from 'react';
import type { SourceProvenanceSummary } from '../../types/analysis';
import type {
  ResearchReadinessV1,
} from '../../types/researchReadiness';
import type {
  ScannerCandidate,
  ScannerCandidateDiagnostic,
  ScannerCandidateDiagnosticStatus,
  ScannerLabeledValue,
} from '../../types/scanner';
import type { TrustDisclosureBucket } from '../../utils/trustDisclosure';
import {
  CompactEmptyRow,
} from '../terminal/DenseWorkbenchPrimitives';
import {
  TerminalChip,
  TerminalNestedBlock,
  TerminalPanel,
} from '../terminal/TerminalPrimitives';
import {
  ScannerCandidateEvidenceStrip,
  type CandidateEvidenceFrame,
} from './ScannerCandidateEvidenceStrip';
import ScannerCandidateResearchSummary, {
  type ScannerCandidateResearchSummaryFrame,
} from './ScannerCandidateResearchSummary';
import {
  FieldChip,
} from './ScannerDisplayAtoms';

type ScannerCandidateWithEvidence = ScannerCandidate & {
  candidateEvidenceFrame?: CandidateEvidenceFrame | null;
  candidateResearchReadiness?: ResearchReadinessV1 | null;
  candidateResearchSummaryFrame?: ScannerCandidateResearchSummaryFrame | null;
  candidateSourceProvenanceFrame?: SourceProvenanceSummary | null;
};

function withCandidateEvidence(candidate: ScannerCandidate): ScannerCandidateWithEvidence {
  return candidate as ScannerCandidateWithEvidence;
}

function consumerTrustNoticeFromBuckets(buckets: TrustDisclosureBucket[], language: 'zh' | 'en'): string | null {
  if (buckets.includes('stale') || buckets.includes('fallback')) {
    return language === 'en'
      ? 'Some results use the latest available data.'
      : '部分结果使用最近一次可用数据。';
  }
  if (buckets.includes('partial') || buckets.includes('proxy')) {
    return language === 'en'
      ? 'Some scan data is temporarily unavailable; current results are for observation.'
      : '部分扫描数据暂不可用，当前结果仅供观察。';
  }
  if (buckets.includes('confidence') || buckets.includes('observe-only')) {
    return language === 'en'
      ? 'Current candidate confidence is low.'
      : '当前候选信号置信度较低。';
  }
  return null;
}

function normalizeDiagnosticStatus(status: ScannerCandidateDiagnostic['status']): ScannerCandidateDiagnosticStatus {
  return status || 'skipped';
}

function diagnosticStatusLabel(status: ScannerCandidateDiagnostic['status'], language: 'zh' | 'en'): string {
  const labels: Record<ScannerCandidateDiagnosticStatus, { zh: string; en: string }> = {
    selected: { zh: '入选', en: 'Selected' },
    rejected: { zh: '淘汰', en: 'Rejected' },
    data_failed: { zh: '数据受限', en: 'Limited data' },
    skipped: { zh: '跳过', en: 'Skipped' },
    error: { zh: '数据暂不可用', en: 'Data unavailable' },
    evaluated: { zh: '已评估', en: 'Evaluated' },
  };
  const normalizedStatus = normalizeDiagnosticStatus(status);
  return labels[normalizedStatus]?.[language] || normalizedStatus;
}

function workflowToneVariant(
  tone: 'neutral' | 'success' | 'caution' | 'danger' | 'info',
): ComponentProps<typeof TerminalChip>['variant'] {
  if (tone === 'success') return 'success';
  if (tone === 'danger') return 'danger';
  if (tone === 'caution') return 'caution';
  if (tone === 'info') return 'info';
  return 'neutral';
}

function ScannerVisualSummaryBar({
  segments,
  testId,
}: {
  segments: Array<{
    key: string;
    label: string;
    count: number;
    toneClassName: string;
  }>;
  testId: string;
}) {
  const total = segments.reduce((sum, segment) => sum + segment.count, 0);
  if (!total) {
    return <div data-testid={testId} className="h-2 rounded-full bg-white/[0.05]" />;
  }
  return (
    <div data-testid={testId} className="flex h-2 overflow-hidden rounded-full bg-white/[0.05]">
      {segments.map((segment) => (
        <span
          key={segment.key}
          className={segment.toneClassName}
          style={{ width: `${(segment.count / total) * 100}%` }}
          title={`${segment.label}: ${segment.count}`}
        />
      ))}
    </div>
  );
}

export function PillTagGroup({
  label,
  value,
  options,
  onChange,
  variant = 'default',
  testId,
  compact = false,
}: {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (next: string) => void;
  variant?: 'default' | 'market';
  testId?: string;
  compact?: boolean;
}) {
  const isMarketGroup = variant === 'market';

  return (
    <fieldset className={compact ? 'flex min-w-0 flex-col gap-1 md:flex-row md:items-center md:gap-2' : 'flex min-w-0 flex-col gap-1.5'}>
      <legend className={compact ? 'shrink-0 text-[10px] uppercase tracking-[0.16em] text-white/40' : 'text-[10px] uppercase tracking-[0.16em] text-white/40'}>{label}</legend>
      <div
        className={isMarketGroup
          ? 'ui-scroll-x-quiet flex min-w-0 max-w-full rounded-xl border border-white/5 bg-black/40 p-1'
          : 'flex min-w-0 flex-wrap gap-1.5'}
        data-testid={testId}
      >
        {options.map((option) => {
          const isActive = option.value === value;
          return (
            <button
              key={option.value}
              type="button"
              aria-pressed={isActive}
              className={isActive
                ? isMarketGroup
                  ? 'min-w-0 shrink-0 rounded-lg bg-white/10 px-3 py-1 text-xs font-bold text-white shadow-[0_2px_10px_rgba(0,0,0,0.5)] transition-all'
                  : 'min-w-0 rounded-full border border-white/10 bg-white/10 px-2.5 py-1 text-xs text-white transition-colors'
                : isMarketGroup
                  ? 'min-w-0 shrink-0 rounded-lg bg-transparent px-3 py-1 text-xs font-medium text-white/40 transition-all hover:text-white/70'
                  : 'min-w-0 rounded-full border border-white/5 bg-transparent px-2.5 py-1 text-xs text-white/50 transition-colors hover:bg-white/[0.05]'}
              onClick={() => onChange(option.value)}
            >
              <span className="ui-truncate block max-w-full">{option.label}</span>
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

export function ScannerResultHistorySummary({
  currentSummary,
  recentSummary,
  previousSummary,
  comparisonItems,
  hasHistory,
  language,
}: {
  currentSummary: {
    title: string;
    statusLabel: string;
    bestCandidate: string;
    candidateCount: number;
    rejectedCount: number;
    failedCount: number;
    dataStatusLabel: string;
    durationLabel: string;
    runTimeLabel: string;
    errorSummary: string | null;
  } | null;
  recentSummary: {
    title: string;
    statusLabel: string;
    bestCandidate: string;
    candidateCount: number;
    rejectedCount: number;
    failedCount: number;
    dataStatusLabel: string;
    durationLabel: string;
    runTimeLabel: string;
    errorSummary: string | null;
  } | null;
  previousSummary: {
    title: string;
    statusLabel: string;
    bestCandidate: string;
    candidateCount: number;
    rejectedCount: number;
    failedCount: number;
    dataStatusLabel: string;
    durationLabel: string;
    runTimeLabel: string;
    errorSummary: string | null;
  } | null;
  comparisonItems: ScannerLabeledValue[];
  hasHistory: boolean;
  language: 'zh' | 'en';
}) {
  const visibleSummaries = [currentSummary, recentSummary, previousSummary]
    .filter((item, index, array): item is NonNullable<typeof item> => Boolean(item) && array.findIndex((other) => other?.title === item?.title) === index);

  return (
    <section data-testid="scanner-result-history-summary" className="shrink-0 border-b border-white/5 px-3 py-2">
      <TerminalPanel dense className="grid gap-2 p-2.5">
        <div className="flex min-w-0 items-center justify-between gap-2">
          <div className="min-w-0">
            <h3 className="truncate text-[10px] font-bold uppercase tracking-widest text-white/40">{language === 'en' ? 'Result history' : '结果历史'}</h3>
            <p className="mt-0.5 truncate text-[11px] text-white/42">{language === 'en' ? 'Current run, latest run, and previous comparable run' : '本次扫描、最近扫描与上次扫描对比'}</p>
          </div>
        </div>
        {visibleSummaries.length ? (
          <div className="grid gap-2 xl:grid-cols-3">
            {visibleSummaries.map((summary) => (
              <TerminalNestedBlock key={summary.title} className="min-w-0 p-2.5" data-testid={`scanner-run-summary-${summary.title}`}>
                <div className="flex min-w-0 items-center justify-between gap-2">
                  <span className="truncate text-[10px] font-bold uppercase tracking-widest text-white/40">{summary.title}</span>
                  <TerminalChip variant="neutral" className="shrink-0 px-1.5 py-0.5 text-[10px] font-sans text-white/62">{summary.statusLabel}</TerminalChip>
                </div>
                <div className="mt-2 grid grid-cols-2 gap-1.5 text-[11px] sm:grid-cols-3">
                  <FieldChip label="最佳候选" value={summary.bestCandidate} />
                  <FieldChip label="候选数量" value={String(summary.candidateCount)} />
                  <FieldChip label="淘汰数量" value={String(summary.rejectedCount)} />
                  <FieldChip label="失败数量" value={String(summary.failedCount)} />
                  <FieldChip label="数据状态" value={summary.dataStatusLabel} />
                  <FieldChip label="耗时" value={summary.durationLabel} />
                </div>
                <p className="mt-2 truncate text-[11px] text-white/42">
                  运行时间：<span className="font-mono text-white/58">{summary.runTimeLabel}</span>
                  {summary.errorSummary ? <span className="text-rose-200/80"> · {summary.errorSummary}</span> : null}
                </p>
              </TerminalNestedBlock>
            ))}
          </div>
        ) : null}
        {!hasHistory && !currentSummary ? (
          <CompactEmptyRow data-testid="scanner-history-empty-state" title={language === 'en' ? 'No scan history yet' : '暂无历史扫描'} className="min-h-[64px] px-3 py-2">
            {language === 'en' ? 'Run one scan to compare results.' : '运行一次扫描后可查看对比'}
          </CompactEmptyRow>
        ) : null}
        {currentSummary && !previousSummary ? (
          <CompactEmptyRow data-testid="scanner-previous-empty-state" className="min-h-[56px] px-3 py-2">
            {language === 'en' ? 'No previous scan · run once more to compare.' : '暂无历史扫描 · 运行一次扫描后可查看对比'}
          </CompactEmptyRow>
        ) : null}
        {comparisonItems.length ? (
          <div data-testid="scanner-run-comparison-compact" className="flex min-w-0 flex-wrap gap-1.5">
            {comparisonItems.map((item) => (
              <FieldChip key={`${item.label}-${item.value}`} label={item.label} value={item.value} />
            ))}
          </div>
        ) : null}
      </TerminalPanel>
    </section>
  );
}

export function ScannerVisualEvidenceSummaryPanel({
  model,
  language,
}: {
  model: {
    totalRows: number;
    scoreBands: Array<{
      key: string;
      label: string;
      count: number;
      toneClassName: string;
    }>;
    candidateCoverageSegments: Array<{
      key: string;
      label: string;
      count: number;
      toneClassName: string;
    }>;
    marketCoverageSegments: Array<{
      key: string;
      label: string;
      count: number;
      toneClassName: string;
    }>;
    candidateReadinessItems: ScannerLabeledValue[];
    nextEvidenceLabel: string | null;
  };
  language: 'zh' | 'en';
}) {
  const sections = [
    {
      key: 'score',
      title: language === 'en' ? 'Score distribution' : '评分分布',
      testId: 'scanner-visual-score-distribution',
      segments: model.scoreBands,
    },
    {
      key: 'candidate-coverage',
      title: language === 'en' ? 'Candidate evidence' : '候选证据覆盖',
      testId: 'scanner-visual-candidate-coverage',
      segments: model.candidateCoverageSegments,
    },
    {
      key: 'market-coverage',
      title: language === 'en' ? 'Market evidence' : '市场证据覆盖',
      testId: 'scanner-visual-market-coverage',
      segments: model.marketCoverageSegments,
    },
  ].filter((section) => section.segments.length > 0);

  if (!sections.length && !model.candidateReadinessItems.length && !model.nextEvidenceLabel) {
    return null;
  }

  return (
    <TerminalPanel dense data-testid="scanner-visual-evidence-summary" className="mb-3 grid gap-3 p-3">
      <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <h3 className="truncate text-[10px] font-bold uppercase tracking-widest text-white/40">
            {language === 'en' ? 'Visual evidence' : '视觉证据'}
          </h3>
          <p className="mt-0.5 text-[11px] text-white/42">
            {language === 'en'
              ? `Compact view across ${model.totalRows} ranked rows without changing row order.`
              : `基于 ${model.totalRows} 条候选的紧凑分布，不改变原有排序。`}
          </p>
        </div>
        {model.candidateReadinessItems.length ? (
          <div data-testid="scanner-visual-readiness-counts" className="flex min-w-0 flex-wrap gap-1.5">
            {model.candidateReadinessItems.map((item) => (
              <FieldChip key={`${item.label}-${item.value}`} label={item.label} value={item.value} />
            ))}
          </div>
        ) : null}
      </div>
      <div className="grid gap-3 lg:grid-cols-3">
        {sections.map((section) => (
          <div key={section.key} className="grid gap-2 rounded-xl border border-white/8 bg-white/[0.02] p-2.5">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-white/40">{section.title}</span>
            </div>
            <ScannerVisualSummaryBar segments={section.segments} testId={section.testId} />
            <div className="flex min-w-0 flex-wrap gap-1.5 text-[10px] text-white/55">
              {section.segments.map((segment) => (
                <span key={segment.key} className="inline-flex items-center gap-1 rounded-md border border-white/8 bg-white/[0.03] px-1.5 py-0.5">
                  <span className={`h-1.5 w-1.5 rounded-full ${segment.toneClassName}`} />
                  <span>{segment.label}</span>
                  <span className="font-mono text-white/78">{segment.count}</span>
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
      {model.nextEvidenceLabel ? (
        <p data-testid="scanner-visual-next-evidence" className="text-xs leading-relaxed text-white/58">
          <span className="text-white/40">{language === 'en' ? 'Next evidence:' : '下一步证据：'}</span>
          {model.nextEvidenceLabel}
        </p>
      ) : null}
    </TerminalPanel>
  );
}

export function ScannerHistoryFallbackPanel({
  summaries,
  emptyState,
  language,
}: {
  summaries: Array<{
    title: string;
    statusLabel: string;
    bestCandidate: string;
    candidateCount: number;
    rejectedCount: number;
    failedCount: number;
    dataStatusLabel: string;
    durationLabel: string;
    runTimeLabel: string;
    errorSummary: string | null;
  }>;
  emptyState: {
    title: string;
    body: string;
  };
  language: 'zh' | 'en';
}) {
  return (
    <TerminalPanel dense data-testid="scanner-empty-history-fallback" className="grid gap-3 p-3">
      <div className="min-w-0">
        <h3 className="truncate text-[10px] font-bold uppercase tracking-widest text-white/40">
          {language === 'en' ? 'No candidate this run' : '本次暂无候选'}
        </h3>
        <p className="mt-0.5 text-[11px] text-white/42">
          {language === 'en'
            ? 'Use the latest run summary before changing scope or waiting for the next scan.'
            : '先看最近一次扫描摘要，再决定调整范围或等待下一次扫描。'}
        </p>
      </div>
      {summaries.length ? (
        <div className="grid gap-2 xl:grid-cols-3">
          {summaries.map((summary) => (
            <TerminalNestedBlock key={summary.title} className="min-w-0 p-2.5" data-testid={`scanner-empty-summary-${summary.title}`}>
              <div className="flex min-w-0 items-center justify-between gap-2">
                <span className="truncate text-[10px] font-bold uppercase tracking-widest text-white/40">{summary.title}</span>
                <TerminalChip variant="neutral" className="shrink-0 px-1.5 py-0.5 text-[10px] font-sans text-white/62">{summary.statusLabel}</TerminalChip>
              </div>
              <div className="mt-2 grid grid-cols-2 gap-1.5 text-[11px] sm:grid-cols-3">
                <FieldChip label="最佳候选" value={summary.bestCandidate} />
                <FieldChip label="候选数量" value={String(summary.candidateCount)} />
                <FieldChip label="淘汰数量" value={String(summary.rejectedCount)} />
                <FieldChip label="失败数量" value={String(summary.failedCount)} />
                <FieldChip label="数据状态" value={summary.dataStatusLabel} />
                <FieldChip label="耗时" value={summary.durationLabel} />
              </div>
            </TerminalNestedBlock>
          ))}
        </div>
      ) : null}
      <CompactEmptyRow data-testid="scanner-workbench-empty-state" title={emptyState.title} className="m-0 min-h-[88px] px-3 py-2">
        {emptyState.body}
      </CompactEmptyRow>
    </TerminalPanel>
  );
}

export function ScannerConclusionBand({
  model,
  scopeLabel,
  dataStateLabel,
  latestLabel,
  language,
}: {
  model: {
    state: 'waiting' | 'top-candidate' | 'no-candidate' | 'insufficient';
    title: string;
    detail: string;
    candidateCount: number;
    trustSummary: {
      buckets: TrustDisclosureBucket[];
    };
    tone: 'neutral' | 'success' | 'caution' | 'danger';
  };
  scopeLabel: string;
  dataStateLabel: string;
  latestLabel: string;
  language: 'zh' | 'en';
}) {
  const toneVariant: ComponentProps<typeof TerminalChip>['variant'] = model.tone === 'success'
    ? 'success'
    : model.tone === 'danger'
      ? 'danger'
      : model.tone === 'caution'
        ? 'caution'
        : 'neutral';
  const trustNotice = consumerTrustNoticeFromBuckets(model.trustSummary.buckets, language);

  return (
    <TerminalPanel
      as="section"
      dense
      data-testid="scanner-conclusion-band"
      className="grid gap-3 px-3 py-3 md:grid-cols-[minmax(0,1fr)_minmax(220px,0.44fr)]"
    >
      <div className="min-w-0">
        <div className="flex min-w-0 flex-wrap items-center gap-1.5">
          <TerminalChip variant={toneVariant} className="shrink-0">
            {dataStateLabel}
          </TerminalChip>
          <TerminalChip variant="neutral" className="max-w-full font-mono">
            {scopeLabel}
          </TerminalChip>
          <TerminalChip variant="neutral" className="shrink-0 font-mono">
            {latestLabel}
          </TerminalChip>
        </div>
        <div className="mt-3 min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-white/40">
            {language === 'en' ? 'Candidate discovery surface' : '候选发现工作台'}
          </p>
          <div className="mt-1 flex min-w-0 flex-wrap items-end gap-2">
            <h2 className="truncate text-xl font-semibold text-white md:text-2xl">{model.title}</h2>
            <span className="text-xs text-white/44">
              {language === 'en' ? 'Candidates' : '候选'} {model.candidateCount}
            </span>
          </div>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-white/64">
            {model.detail}
          </p>
        </div>
      </div>
      <div className="grid gap-2 rounded-2xl border border-white/8 bg-white/[0.02] p-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-white/40">
            {language === 'en' ? 'Primary cue' : '当前提示'}
          </p>
          <p className="mt-1 text-sm leading-relaxed text-white/72">
            {model.state === 'top-candidate'
              ? (language === 'en' ? 'Review the ranked table first, then inspect the selected candidate rail.' : '先看排名主表，再查看右侧当前候选。')
              : model.state === 'waiting'
                ? (language === 'en' ? 'Choose the market scope, then run a scan or open history.' : '先确认市场范围，再启动扫描或打开历史记录。')
                : (language === 'en' ? 'Use the ranked rows as evidence and keep diagnostics collapsed until needed.' : '先使用候选行作为主证据，只有需要时再展开数据说明。')}
          </p>
        </div>
        {trustNotice ? (
          <div className="border-t border-white/8 pt-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-white/40">
              {language === 'en' ? 'Data cue' : '数据提示'}
            </p>
            <p className="mt-1 text-xs leading-relaxed text-white/58">
              {trustNotice}
            </p>
          </div>
        ) : null}
      </div>
    </TerminalPanel>
  );
}

export function ScannerWorkflowSummaryPanel({
  contextSummary,
  candidate,
  diagnostic,
  rankedRowCount,
  selectedCount,
  language,
}: {
  contextSummary: {
    tone: 'neutral' | 'success' | 'caution' | 'danger' | 'info';
    postureLabel: string;
    summaryLine: string;
    chips?: Array<{ key: string; label: string }>;
  } | null;
  candidate: ScannerCandidate | null;
  diagnostic: ScannerCandidateDiagnostic | null;
  rankedRowCount: number;
  selectedCount: number;
  language: 'zh' | 'en';
}) {
  if (!candidate || !diagnostic) return null;

  const candidateWithEvidence = withCandidateEvidence(candidate);
  const scoreLabel = diagnostic.score != null && Number.isFinite(diagnostic.score) ? `${diagnostic.score}/100` : '--';
  const rankLabel = diagnostic.rank ? `#${diagnostic.rank}` : '--';
  const statusLabel = diagnosticStatusLabel(diagnostic.status, language);
  const topDownTitle = language === 'en' ? 'Start with market drivers' : '先看市场驱动';
  const focusTitle = language === 'en' ? `Focus candidate ${candidate.symbol || '--'}` : `当前候选 ${candidate.symbol || '--'}`;
  const rankedRowsTitle = language === 'en' ? 'Review ranked rows' : '查看排名主表';
  const workflowStepLabel = language === 'en' ? 'Step' : '步骤';
  const rowCountLabel = language === 'en' ? 'Rows in view' : '当前行数';
  const selectedCountLabel = language === 'en' ? 'Selected' : '入选';

  return (
    <TerminalPanel dense data-testid="scanner-workflow-summary" className="mb-3 grid gap-2.5 p-3">
      <div className="min-w-0">
        <h3 className="text-[10px] font-bold uppercase tracking-widest text-white/40">
          {language === 'en' ? 'Scanner workflow' : '扫描流程'}
        </h3>
        <p className="mt-0.5 text-[11px] text-white/46">
          {language === 'en'
            ? 'Read the market context first, confirm the current candidate evidence, then compare ranked rows.'
            : '先确认市场上下文，再看当前候选证据，最后对比排名主表。'}
        </p>
      </div>
      <div className="grid gap-2.5 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.15fr)_minmax(0,0.9fr)]">
        <TerminalNestedBlock data-testid="scanner-workflow-step-topdown" className="grid gap-2 p-2.5">
          <div className="flex min-w-0 flex-wrap items-center gap-1.5">
            <TerminalChip variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
              {workflowStepLabel} 1
            </TerminalChip>
            <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-white/40">
              {topDownTitle}
            </span>
            {contextSummary ? (
              <TerminalChip variant={workflowToneVariant(contextSummary.tone)}>
                {contextSummary.postureLabel}
              </TerminalChip>
            ) : null}
          </div>
          <p className="text-xs leading-relaxed text-white/68">
            {contextSummary?.summaryLine || (language === 'en'
              ? 'Market context remains unavailable, so the scanner stays research-only.'
              : '市场上下文暂不可用，因此当前扫描保持研究观察边界。')}
          </p>
          {contextSummary?.chips?.length ? (
            <div className="flex min-w-0 flex-wrap gap-1.5">
              {contextSummary.chips.slice(0, 4).map((chip) => (
                <TerminalChip key={chip.key} variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
                  {chip.label}
                </TerminalChip>
              ))}
            </div>
          ) : null}
        </TerminalNestedBlock>

        <TerminalNestedBlock data-testid="scanner-workflow-step-focus-candidate" className="grid gap-2 p-2.5">
          <div className="flex min-w-0 flex-wrap items-center gap-1.5">
            <TerminalChip variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
              {workflowStepLabel} 2
            </TerminalChip>
            <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-white/40">
              {focusTitle}
            </span>
          </div>
          <div className="flex min-w-0 flex-wrap gap-1.5">
            <FieldChip label={language === 'en' ? 'Score' : '评分'} value={scoreLabel} />
            <FieldChip label={language === 'en' ? 'Rank' : '排名'} value={rankLabel} />
            <FieldChip label={language === 'en' ? 'Status' : '状态'} value={statusLabel} />
          </div>
          {candidateWithEvidence.candidateResearchSummaryFrame ? (
            <ScannerCandidateResearchSummary
              frame={candidateWithEvidence.candidateResearchSummaryFrame}
              language={language}
              variant="row"
              testId="scanner-workflow-candidate-summary"
            />
          ) : candidate.reasonSummary ? (
            <p className="text-[11px] leading-relaxed text-white/58">
              {candidate.reasonSummary}
            </p>
          ) : null}
          {candidateWithEvidence.candidateEvidenceFrame || candidateWithEvidence.candidateResearchReadiness ? (
            <ScannerCandidateEvidenceStrip
              frame={candidateWithEvidence.candidateEvidenceFrame}
              provenanceFrame={candidateWithEvidence.candidateSourceProvenanceFrame}
              readiness={candidateWithEvidence.candidateResearchReadiness}
              language={language}
              variant="row"
              testId="scanner-workflow-candidate-evidence"
            />
          ) : null}
        </TerminalNestedBlock>

        <TerminalNestedBlock data-testid="scanner-workflow-step-ranked-rows" className="grid gap-2 p-2.5">
          <div className="flex min-w-0 flex-wrap items-center gap-1.5">
            <TerminalChip variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
              {workflowStepLabel} 3
            </TerminalChip>
            <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-white/40">
              {rankedRowsTitle}
            </span>
          </div>
          <p className="text-xs leading-relaxed text-white/64">
            {language === 'en'
              ? 'Keep the ranked table as the comparison surface, then open detailed notes only when a row needs follow-up.'
              : '保持排名主表作为对比主面板，只有需要跟进某一行时再展开详细说明。'}
          </p>
          <div className="flex min-w-0 flex-wrap gap-1.5">
            <FieldChip label={rowCountLabel} value={String(rankedRowCount)} />
            <FieldChip label={selectedCountLabel} value={String(selectedCount)} />
          </div>
        </TerminalNestedBlock>
      </div>
    </TerminalPanel>
  );
}
