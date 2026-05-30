import type { ReactNode } from 'react';
import {
  BookmarkCheck,
  BookmarkPlus,
  ChevronDown,
  ChevronRight,
  Copy,
  Download,
  Play,
  TestTubeDiagonal,
} from 'lucide-react';
import { EvidenceChips } from '../evidence/EvidenceChips';
import type { NormalizedEvidenceSummary } from '../../utils/evidenceDisplay';
import type {
  ScannerCandidate,
  ScannerCandidateDiagnostic,
  ScannerLabeledValue,
} from '../../types/scanner';
import type { ScannerBacktestItem } from './scannerBacktestShared';
import { ScannerActionButton as ActionButton } from './ScannerActionButton';
import { ScannerBacktestResultStrip } from './ScannerBacktestResultStrip';
import {
  AdvancedDisclosure,
  DetailSection,
  FieldChip,
  LabeledValueGrid,
  NotesList,
} from './ScannerDisplayAtoms';
import { ScannerScoreTrustStrip } from './ScannerScoreTrustStrip';
import { TerminalButton } from '../terminal/TerminalPrimitives';

type CandidateDetailOutcomeItem = {
  label: string;
  value: string;
};

type ScannerWatchlistState = {
  tracked: boolean;
  pending: boolean;
  authBlocked: boolean;
  label: string;
  title?: string;
  onTrack: () => void;
};

type ScannerAnalyzeAction = {
  label: string;
  disabled: boolean;
  onAnalyze: () => void;
};

type ScannerCopyAction = {
  label: string;
  copied: boolean;
  onCopy: () => void;
};

type ScannerExportAction = {
  label?: string;
  onExport: () => void;
};

type ScannerBacktestAction = {
  item?: ScannerBacktestItem;
  label: string;
  title?: string;
  disabled?: boolean;
  onBacktest: () => void;
};

type ScannerRowState = {
  selected: boolean;
  expanded: boolean;
  moreOpen: boolean;
};

function BoardDetailSection({
  title,
  children,
  className,
}: {
  title: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`min-w-0 border-t border-white/8 py-2 ${className || ''}`.trim()}>
      <h5 className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-white/36">{title}</h5>
      {children}
    </section>
  );
}

export function ScannerCandidateDetailPanel({
  candidate,
  candidateIdentity,
  language,
  evidenceSummary,
  keyMetricItems,
  featureSignalItems,
  riskNotes,
  entryRange,
  targetPrice,
  stopLoss,
  selectionNotes,
  aiLines,
  aiUnavailableText,
  outcomeItems,
  providerNotes,
  watchlistState,
  analyzeAction,
  copyAction,
  exportAction,
  backtestAction,
}: {
  candidate: ScannerCandidate;
  candidateIdentity: string;
  language: 'zh' | 'en';
  evidenceSummary: NormalizedEvidenceSummary | null;
  keyMetricItems: ScannerLabeledValue[];
  featureSignalItems: ScannerLabeledValue[];
  riskNotes: string[];
  entryRange: string | null;
  targetPrice: string | null;
  stopLoss: string | null;
  selectionNotes: string[];
  aiLines: string[];
  aiUnavailableText: string;
  outcomeItems: CandidateDetailOutcomeItem[];
  providerNotes: string | null;
  watchlistState: ScannerWatchlistState;
  analyzeAction: ScannerAnalyzeAction;
  copyAction: ScannerCopyAction;
  exportAction: ScannerExportAction;
  backtestAction: ScannerBacktestAction;
}) {
  const aiAvailable = Boolean(candidate.aiInterpretation?.available);

  return (
    <div
      data-testid={`scanner-result-detail-${candidateIdentity}`}
      className="mt-1 grid gap-x-3 gap-y-0 border-t border-white/10 bg-black/[0.14] px-2 py-1 md:grid-cols-4"
    >
      <BoardDetailSection title={language === 'en' ? 'Conclusion' : '结论'}>
        <p className="text-xs leading-relaxed text-white/68">{selectionNotes[0] || candidate.reasonSummary || keyMetricItems[0]?.value || aiUnavailableText}</p>
      </BoardDetailSection>
      <BoardDetailSection title={language === 'en' ? 'Reason' : '理由'}>
        <NotesList notes={selectionNotes.slice(0, 2)} empty={language === 'en' ? 'No selection notes provided' : '未提供入选说明'} />
      </BoardDetailSection>
      <BoardDetailSection title={language === 'en' ? 'Risk' : '风险'}>
        <NotesList notes={riskNotes.slice(0, 2)} empty={language === 'en' ? 'No risk notes provided' : '未提供风险说明'} />
      </BoardDetailSection>
      <BoardDetailSection title={language === 'en' ? 'Next step' : '下一步'}>
        <div className="flex flex-wrap gap-1.5">
          {entryRange ? <FieldChip label={language === 'en' ? 'Observation zone' : '观察区'} value={entryRange} /> : null}
          {targetPrice ? <FieldChip label={language === 'en' ? 'Reference range' : '参考区间'} value={targetPrice} /> : null}
          {stopLoss ? <FieldChip label={language === 'en' ? 'Risk boundary' : '风险边界'} value={stopLoss} /> : null}
          {!entryRange && !targetPrice && !stopLoss ? (
            <p className="text-xs text-white/36">{language === 'en' ? 'Review source evidence before treating this as evidence.' : '先复核来源证据，再作为证据。'}</p>
          ) : null}
        </div>
      </BoardDetailSection>
      <BoardDetailSection title={language === 'en' ? 'Key metrics' : '关键指标'}>
        <LabeledValueGrid items={keyMetricItems.slice(0, 5)} empty={language === 'en' ? 'No key metrics provided' : '未提供关键指标'} />
      </BoardDetailSection>
      {outcomeItems.length ? (
        <BoardDetailSection title={language === 'en' ? 'Realized outcome' : '实际表现'}>
          <div className="flex flex-wrap gap-2">
            {outcomeItems.map((item) => (
              <FieldChip key={`${item.label}-${item.value}`} label={item.label} value={item.value} />
            ))}
          </div>
        </BoardDetailSection>
      ) : null}
      <div className="md:col-span-4 flex flex-wrap items-center gap-1.5 border-t border-white/8 py-2">
        <ActionButton
          label={analyzeAction.label}
          icon={<Play className="size-3.5" />}
          onClick={analyzeAction.onAnalyze}
          disabled={analyzeAction.disabled}
          variant="compact"
        />
        <ActionButton
          label={watchlistState.label}
          icon={watchlistState.tracked ? <BookmarkCheck className="size-3.5" /> : <BookmarkPlus className="size-3.5" />}
          onClick={watchlistState.onTrack}
          disabled={watchlistState.pending || watchlistState.tracked || watchlistState.authBlocked}
          variant="compact"
          title={watchlistState.title}
        />
        <ActionButton
          label={backtestAction.label}
          icon={<TestTubeDiagonal className="size-3.5" />}
          onClick={backtestAction.onBacktest}
          disabled={backtestAction.disabled ?? (!candidate.symbol || backtestAction.item?.status === 'running' || backtestAction.item?.status === 'queued')}
          title={backtestAction.title}
        />
        <ActionButton
          label={copyAction.label}
          icon={<Copy className="size-3.5" />}
          onClick={copyAction.onCopy}
        />
        <ActionButton
          label={exportAction.label || (language === 'en' ? 'Export candidate' : '导出该候选')}
          icon={<Download className="size-3.5" />}
          onClick={exportAction.onExport}
        />
      </div>
      {evidenceSummary || featureSignalItems.length || aiAvailable || providerNotes ? (
        <AdvancedDisclosure
          testId={`scanner-result-detail-secondary-${candidateIdentity}`}
          title={language === 'en' ? 'Secondary notes' : '次要说明'}
          summary={language === 'en' ? 'Evidence, signals, source notes' : '证据、信号、来源说明'}
          icon="more"
        >
          <div className="grid gap-2 md:grid-cols-2">
            {evidenceSummary ? (
              <BoardDetailSection title={language === 'en' ? 'Evidence status' : '证据状态'}>
                <EvidenceChips summary={evidenceSummary} maxLabels={2} />
              </BoardDetailSection>
            ) : null}
            {featureSignalItems.length ? (
              <BoardDetailSection title={language === 'en' ? 'Feature signals' : '特征信号'}>
                <LabeledValueGrid items={featureSignalItems.slice(0, 4)} empty={language === 'en' ? 'No feature signals provided' : '未提供特征信号'} />
              </BoardDetailSection>
            ) : null}
            {aiAvailable ? (
              <BoardDetailSection title={language === 'en' ? 'AI interpretation' : 'AI 解读'}>
                <div className="space-y-2 text-xs leading-relaxed text-white/64">
                  {aiLines.length ? aiLines.slice(0, 3).map((line) => <p key={line}>{line}</p>) : <p>{candidate.aiInterpretation?.status}</p>}
                </div>
              </BoardDetailSection>
            ) : null}
            {providerNotes ? (
              <BoardDetailSection title={language === 'en' ? 'Source' : '来源'}>
                <p className="text-xs leading-relaxed text-white/64">{providerNotes}</p>
              </BoardDetailSection>
            ) : null}
          </div>
        </AdvancedDisclosure>
      ) : null}
      <div className="md:col-span-4">
        <ScannerBacktestResultStrip item={backtestAction.item} language={language} />
      </div>
    </div>
  );
}

export function ScannerCandidateInspector({
  candidate,
  language,
  evidenceSummary,
  statusLabel,
  statusClassName,
  officialStatusCopy,
  previewStatusCopy,
  dataQualityLabel,
  comparisonLabel,
  comparisonDelta,
  whySelectedNotes,
  riskNotes,
  failedRuleNotes,
  missingFieldNotes,
  missingCount,
  watchlistState,
  copyAction,
  exportAction,
  backtestAction,
  testId = 'scanner-candidate-inspector',
}: {
  candidate: ScannerCandidateDiagnostic;
  language: 'zh' | 'en';
  evidenceSummary: NormalizedEvidenceSummary | null;
  statusLabel: string;
  statusClassName: string;
  officialStatusCopy: string;
  previewStatusCopy: string;
  dataQualityLabel: string;
  comparisonLabel?: string | null;
  comparisonDelta?: string | null;
  whySelectedNotes: string[];
  riskNotes: string[];
  failedRuleNotes: string[];
  missingFieldNotes: string[];
  missingCount: number;
  watchlistState: ScannerWatchlistState;
  copyAction: ScannerCopyAction;
  exportAction: ScannerExportAction;
  backtestAction?: Pick<ScannerBacktestAction, 'item'>;
  testId?: string;
}) {
  return (
    <aside
      data-testid={testId}
      className="flex max-h-full min-h-0 flex-col overflow-hidden rounded-xl border border-white/5 bg-white/[0.02] text-sm backdrop-blur-md transition-all hover:border-white/10"
    >
      <div className="border-b border-white/5 p-3">
        <div className="flex min-w-0 items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex min-w-0 items-center gap-2">
              <span className="truncate font-mono text-lg font-bold text-white">{candidate.symbol || '--'}</span>
              <span className={`inline-flex shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-widest ${statusClassName}`}>
                {statusLabel}
              </span>
            </div>
            <p className="mt-1 truncate text-xs text-white/40">{candidate.name || candidate.symbol || '--'}</p>
            <p className="mt-1 text-xs text-white/62">
              {officialStatusCopy}
              {candidate.score != null ? ` · ${candidate.score}/100` : ''}
            </p>
          </div>
          <div className="shrink-0 text-right">
            <p className="text-[10px] font-bold uppercase tracking-widest text-white/40">{language === 'en' ? 'Rank' : '排名'}</p>
            <p className="font-mono text-sm font-semibold text-white">{candidate.rank ? `#${candidate.rank}` : '--'}</p>
          </div>
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          <FieldChip label={language === 'en' ? 'Status' : '状态'} value={statusLabel} />
          <FieldChip label={language === 'en' ? 'Quality' : '质量'} value={dataQualityLabel} />
          <FieldChip label={language === 'en' ? 'Preview' : '预览'} value={previewStatusCopy} />
          <FieldChip label={language === 'en' ? 'Missing' : '缺失'} value={String(missingCount)} />
          {comparisonDelta ? <FieldChip label={language === 'en' ? 'Prev' : '较上次'} value={comparisonDelta} /> : null}
          {comparisonLabel ? <FieldChip label={language === 'en' ? 'Change' : '变化'} value={comparisonLabel} /> : null}
        </div>
      </div>

      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3 no-scrollbar">
        <DetailSection title={language === 'en' ? 'Why selected' : '为什么入选'}>
          <NotesList notes={whySelectedNotes} empty={language === 'en' ? 'No decision notes provided' : '未提供决策说明'} />
        </DetailSection>

        <DetailSection title={language === 'en' ? 'Main risks' : '主要风险'}>
          <NotesList notes={riskNotes} empty={language === 'en' ? 'No major risks provided' : '未提供主要风险'} />
        </DetailSection>

        {evidenceSummary ? (
          <DetailSection title={language === 'en' ? 'Evidence status' : '证据状态'}>
            <EvidenceChips summary={evidenceSummary} maxLabels={2} />
          </DetailSection>
        ) : null}

        <DetailSection title={language === 'en' ? 'Next step' : '下一步'}>
          <div className="grid grid-cols-2 gap-1.5">
            <ActionButton
              label={copyAction.label}
              icon={<Copy className="size-3.5" />}
              onClick={copyAction.onCopy}
            />
            <ActionButton
              label={exportAction.label || (language === 'en' ? 'Export' : '导出')}
              icon={<Download className="size-3.5" />}
              onClick={exportAction.onExport}
            />
            <ActionButton
              label={watchlistState.label}
              icon={watchlistState.tracked ? <BookmarkCheck className="size-3.5" /> : <BookmarkPlus className="size-3.5" />}
              onClick={watchlistState.onTrack}
              disabled={watchlistState.tracked || watchlistState.pending || watchlistState.authBlocked}
              title={watchlistState.title}
            />
          </div>
          <ScannerBacktestResultStrip item={backtestAction?.item} language={language} />
        </DetailSection>

        <AdvancedDisclosure
          testId={`${testId}-rules-disclosure`}
          title={language === 'en' ? 'Basis notes' : '依据说明'}
          summary={failedRuleNotes[0] || (language === 'en' ? 'No additional notes' : '暂无额外说明')}
          icon="info"
        >
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
            <NotesList notes={failedRuleNotes} empty={language === 'en' ? 'No additional notes' : '暂无额外说明'} />
            <NotesList notes={missingFieldNotes} empty={language === 'en' ? 'No missing data notes' : '暂无缺失数据说明'} />
          </div>
        </AdvancedDisclosure>

        <AdvancedDisclosure
          testId={`${testId}-quality-disclosure`}
          title={language === 'en' ? 'Data quality' : '数据质量'}
          summary={dataQualityLabel}
          icon="history"
        >
          <div className="flex flex-wrap gap-1.5">
            <FieldChip label={language === 'en' ? 'Status' : '状态'} value={statusLabel} />
            <FieldChip label={language === 'en' ? 'Quality' : '质量'} value={dataQualityLabel} />
            <FieldChip label={language === 'en' ? 'Missing' : '缺失'} value={String(missingCount)} />
          </div>
        </AdvancedDisclosure>
      </div>
    </aside>
  );
}

export function ScannerCandidateDiagnosticRow({
  candidate,
  trustSources,
  language,
  rowState,
  displayName,
  keyReason,
  previewLabel,
  previewBadgeClassName,
  dataQualityLabel,
  watchSummary,
  rangeSummary,
  evidenceSummary,
  scoreLabel,
  scoreDelta,
  comparisonLabel,
  statusLabel,
  watchlistState,
  analyzeAction,
  backtestAction,
  copyAction,
  exportAction,
  detailPanel,
  onSelect,
  onToggleMore,
}: {
  candidate: ScannerCandidateDiagnostic;
  trustSources?: Array<ScannerCandidate | ScannerCandidateDiagnostic | null | undefined>;
  language: 'zh' | 'en';
  rowState: ScannerRowState;
  displayName: string;
  keyReason: string;
  previewLabel: string;
  previewBadgeClassName: string;
  dataQualityLabel: string;
  watchSummary: string;
  rangeSummary: string;
  evidenceSummary: NormalizedEvidenceSummary | null;
  scoreLabel: string;
  scoreDelta?: string | null;
  comparisonLabel?: string | null;
  statusLabel: string;
  watchlistState: ScannerWatchlistState;
  analyzeAction: ScannerAnalyzeAction;
  backtestAction: ScannerBacktestAction;
  copyAction: ScannerCopyAction;
  exportAction: ScannerExportAction;
  detailPanel?: ReactNode;
  onSelect: () => void;
  onToggleMore: () => void;
}) {
  const resolvedTrustSources = trustSources?.length ? trustSources : [candidate];
  return (
    <button
      type="button"
      data-testid={`scanner-ranked-row-${candidate.symbol}`}
      data-selected={rowState.selected ? 'true' : undefined}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onSelect();
        }
      }}
      className={`cursor-pointer appearance-none border-b border-white/7 px-3 py-2.5 text-left text-sm transition-colors ${
        rowState.selected
          ? 'bg-emerald-400/[0.045] shadow-[inset_2px_0_0_rgba(52,211,153,0.32)]'
          : 'bg-transparent hover:bg-white/[0.028]'
      }`}
    >
      <div data-testid={`scanner-result-card-${candidate.symbol}`} className="contents">
        <div data-testid={`scanner-result-row-${candidate.symbol}`} className="contents">
          <div data-testid={`scanner-candidate-row-${candidate.symbol}`} className="contents">
          <div className="hidden min-w-0 items-center gap-3 md:grid md:grid-cols-[64px_minmax(180px,1fr)_92px_110px_minmax(220px,1.3fr)_minmax(150px,0.9fr)_minmax(190px,1fr)_auto]">
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-white/30">{language === 'en' ? 'Rank' : '排名'}</p>
              <p className={`mt-1 font-mono text-sm font-semibold ${rowState.selected ? 'text-emerald-50' : 'text-white/72'}`}>
                {candidate.rank ? `#${candidate.rank}` : '--'}
              </p>
            </div>
            <div className="min-w-0">
              <p className={`truncate font-mono text-sm font-semibold ${rowState.selected ? 'text-emerald-50' : 'text-white'}`}>
                {candidate.symbol || '--'}
              </p>
              <p className="truncate text-[11px] text-white/38">{displayName}</p>
              {comparisonLabel ? <p className="mt-1 truncate text-[10px] text-cyan-100/70">{comparisonLabel}</p> : null}
            </div>
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-white/30">{language === 'en' ? 'Score' : '评分'}</p>
              <p className={`mt-1 font-mono text-sm font-semibold ${rowState.selected ? 'text-emerald-100' : 'text-white/78'}`}>{scoreLabel}</p>
              {scoreDelta ? <p className="text-[10px] text-white/36">{scoreDelta}</p> : null}
              <ScannerScoreTrustStrip sources={resolvedTrustSources} language={language} className="mt-1.5" testId={`scanner-score-trust-${candidate.symbol}`} />
            </div>
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-white/30">{language === 'en' ? 'Status' : '状态'}</p>
              <div className="mt-1 flex flex-wrap items-center gap-1.5">
                <span className={`inline-flex max-w-full rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-[0.1em] ${previewBadgeClassName}`}>
                  <span className="truncate">{previewLabel}</span>
                </span>
                <span className="inline-flex rounded border border-white/10 bg-white/[0.04] px-1.5 py-0.5 text-[10px] font-medium text-white/62">
                  {statusLabel}
                </span>
              </div>
            </div>
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-white/30">{language === 'en' ? 'Key reason' : '关键原因'}</p>
              <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-white/68" title={keyReason}>{keyReason}</p>
            </div>
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-white/30">{language === 'en' ? 'Data quality' : '数据质量'}</p>
              <p className="mt-1 truncate text-xs text-white/62" title={dataQualityLabel}>{dataQualityLabel}</p>
              {evidenceSummary ? <EvidenceChips summary={evidenceSummary} maxLabels={1} className="mt-1" /> : null}
            </div>
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-white/30">{language === 'en' ? 'Watch / risk' : '观察 / 风险'}</p>
              <p className="mt-1 truncate text-xs text-white/72" title={watchSummary}>{watchSummary}</p>
              <p className="truncate text-[11px] text-white/38" title={rangeSummary}>{rangeSummary}</p>
            </div>
            <div className="flex min-w-0 flex-wrap justify-end gap-1.5">
              <ActionButton
                label={language === 'en' ? 'Detail' : '详情'}
                onClick={onSelect}
                variant="compact"
              />
              <ActionButton
                label={language === 'en' ? 'More' : '更多'}
                onClick={onToggleMore}
                variant="compact"
              />
            </div>
          </div>

          <div className="grid gap-2 md:hidden">
            <div className="flex min-w-0 items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex min-w-0 items-center gap-2">
                  <span className={`font-mono text-sm font-semibold ${rowState.selected ? 'text-emerald-50' : 'text-white'}`}>
                    {candidate.symbol || '--'}
                  </span>
                  <span className={`inline-flex max-w-full rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-[0.1em] ${previewBadgeClassName}`}>
                    <span className="truncate">{previewLabel}</span>
                  </span>
                </div>
                <p className="mt-1 truncate text-[11px] text-white/38">{displayName}</p>
              </div>
              <div className="shrink-0 text-right">
                <p className="font-mono text-sm font-semibold text-white/78">{scoreLabel}</p>
                <p className="text-[10px] text-white/36">{candidate.rank ? `#${candidate.rank}` : '--'}</p>
              </div>
            </div>
            <div className="grid gap-1.5 text-xs text-white/66">
              <p title={keyReason}>{keyReason}</p>
              <p title={dataQualityLabel}>{dataQualityLabel}</p>
              <p title={watchSummary}>{watchSummary}</p>
              <p className="text-[11px] text-white/38" title={rangeSummary}>{rangeSummary}</p>
              <ScannerScoreTrustStrip sources={resolvedTrustSources} language={language} className="pt-0.5" testId={`scanner-score-trust-mobile-${candidate.symbol}`} />
              {evidenceSummary ? <EvidenceChips summary={evidenceSummary} maxLabels={2} /> : null}
            </div>
            <div className="flex flex-wrap gap-1.5">
              <ActionButton
                label={language === 'en' ? 'Detail' : '详情'}
                onClick={onSelect}
                variant="compact"
              />
              <ActionButton
                label={language === 'en' ? 'More' : '更多'}
                onClick={onToggleMore}
                variant="compact"
              />
            </div>
          </div>
          </div>
        </div>
      </div>
      {rowState.moreOpen ? (
        <div data-testid={`scanner-candidate-row-more-${candidate.symbol}`} className="mt-1.5 flex flex-wrap gap-1.5 border-t border-white/8 pt-1.5">
          <ActionButton
            label={analyzeAction.label}
            onClick={analyzeAction.onAnalyze}
            disabled={analyzeAction.disabled}
          />
          <ActionButton
            label={backtestAction.label}
            onClick={backtestAction.onBacktest}
            disabled={backtestAction.disabled ?? (!candidate.symbol || backtestAction.item?.status === 'running' || backtestAction.item?.status === 'queued')}
            title={backtestAction.title}
          />
          <ActionButton
            label={watchlistState.label}
            onClick={watchlistState.onTrack}
            disabled={watchlistState.tracked || watchlistState.pending || watchlistState.authBlocked}
            title={watchlistState.title}
          />
          <ActionButton
            label={copyAction.label}
            onClick={copyAction.onCopy}
          />
          <ActionButton
            label={exportAction.label || (language === 'en' ? 'Export' : '导出')}
            onClick={exportAction.onExport}
          />
        </div>
      ) : null}
      {rowState.expanded && detailPanel ? (
        <div data-testid={`scanner-candidate-detail-${candidate.symbol}`} className="mt-3 border-t border-white/8 pt-3">
          {detailPanel}
        </div>
      ) : null}
    </button>
  );
}

export function ScannerCandidateCard({
  candidate,
  candidateIdentity,
  language,
  isExpanded,
  isTracked,
  isTrackPending,
  comparisonLabel,
  scoreBadgeClassName,
  keyReason,
  entryRange,
  targetPrice,
  stopLoss,
  evidenceSummary,
  featureSignalItems,
  keyMetricItems,
  watchlistActionLabel,
  watchlistActionTitle,
  onSelect,
  onToggleDetail,
  onViewEvidence,
  onTrack,
  detailPanel,
  backtestItem,
}: {
  candidate: ScannerCandidate;
  candidateIdentity: string;
  language: 'zh' | 'en';
  isExpanded: boolean;
  isTracked: boolean;
  isTrackPending: boolean;
  comparisonLabel?: string | null;
  scoreBadgeClassName: string;
  keyReason: string;
  entryRange: string | null;
  targetPrice: string | null;
  stopLoss: string | null;
  evidenceSummary: NormalizedEvidenceSummary | null;
  featureSignalItems: ScannerLabeledValue[];
  keyMetricItems: ScannerLabeledValue[];
  watchlistActionLabel: string;
  watchlistActionTitle?: string;
  onSelect: () => void;
  onToggleDetail: () => void;
  onViewEvidence: () => void;
  onTrack: () => void;
  detailPanel?: ReactNode;
  backtestItem?: ScannerBacktestItem;
}) {
  return (
    <button
      type="button"
      data-testid={`scanner-result-card-${candidateIdentity}`}
      onClick={() => onSelect()}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onSelect();
        }
      }}
      className="appearance-none rounded-xl border border-white/5 bg-white/[0.02] p-3 text-left transition-colors hover:border-white/16 hover:bg-white/[0.04]"
    >
      <div className="flex justify-between items-start gap-3">
        <div className="min-w-0 flex flex-col gap-1.5">
          <div className="flex flex-wrap items-baseline gap-2 min-w-0">
            <span className="rounded-md border border-white/10 bg-white/[0.06] px-1.5 py-0.5 text-[10px] text-white/58">#{candidate.rank}</span>
            <h3 className="text-lg font-bold text-white tracking-tight">{candidate.symbol}</h3>
            <span className="text-xs text-white/40 font-medium truncate max-w-[180px]">
              {candidate.companyName || candidate.name}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex rounded border border-emerald-400/25 bg-emerald-400/10 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-widest text-emerald-100">
              {language === 'en' ? 'Official' : '官方'}
            </span>
            <span className={`inline-flex rounded border px-1.5 py-0.5 text-[10px] font-bold ${scoreBadgeClassName}`}>
              {language === 'en' ? `scanner score ${candidate.score}/100` : `扫描评分 ${candidate.score}/100`}
            </span>
            {candidate.aiInterpretation?.available ? (
              <span className="inline-flex rounded border border-indigo-400/20 bg-indigo-400/10 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-100">
                {language === 'en' ? 'AI interpretation available' : 'AI 解读可用'}
              </span>
            ) : null}
            {comparisonLabel ? (
              <span className="inline-flex rounded border border-cyan-300/15 bg-cyan-300/[0.07] px-1.5 py-0.5 text-[10px] font-semibold text-cyan-100/80">
                {comparisonLabel}
              </span>
            ) : null}
            {isTracked ? (
              <span className="inline-flex rounded border border-emerald-400/20 bg-emerald-400/10 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-100">
                {language === 'en' ? 'Tracked' : '已追踪'}
              </span>
            ) : null}
          </div>
        </div>
        <TerminalButton
          type="button"
          variant="compact"
          className="shrink-0 px-2.5 py-1 text-xs"
          onClick={(event) => {
            event.stopPropagation();
            onToggleDetail();
          }}
        >
          {language === 'en' ? 'Detail' : '详情'}
          {isExpanded ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
        </TerminalButton>
      </div>

      <div className="mt-2.5 grid gap-2">
        <section>
          <p className="line-clamp-1 text-xs leading-relaxed text-white/66">{keyReason}</p>
          {evidenceSummary ? <EvidenceChips summary={evidenceSummary} maxLabels={2} className="mt-1.5" /> : null}
          {featureSignalItems.length ? (
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {featureSignalItems.slice(0, 2).map((signal) => (
                <FieldChip key={`${candidate.symbol}-${signal.label}-${signal.value}`} label={signal.label} value={signal.value} />
              ))}
            </div>
          ) : null}
        </section>

        <section className="grid grid-cols-3 gap-2 rounded-lg border border-white/5 bg-black/20 p-2">
          <div>
            <div className="text-[10px] text-white/40 mb-1 uppercase">{language === 'en' ? 'Observation zone' : '观察区'}</div>
            <div className="truncate text-xs text-white font-medium">{entryRange || '--'}</div>
          </div>
          <div>
            <div className="text-[10px] text-white/40 mb-1 uppercase">{language === 'en' ? 'Reference range' : '参考区间'}</div>
            <div className="truncate text-xs font-medium text-white">{targetPrice || '--'}</div>
          </div>
          <div>
            <div className="text-[10px] text-white/40 mb-1 uppercase">{language === 'en' ? 'Risk boundary' : '风险边界'}</div>
            <div className="truncate text-xs text-red-300 font-medium">{stopLoss || '--'}</div>
          </div>
        </section>

        {keyMetricItems.length ? (
          <section>
            <LabeledValueGrid items={keyMetricItems.slice(0, 3)} empty="" />
          </section>
        ) : null}

        <div className="flex flex-wrap gap-1.5 pt-0.5">
          <ActionButton
            label={watchlistActionLabel}
            icon={isTracked ? <BookmarkCheck className="size-3.5" /> : <BookmarkPlus className="size-3.5" />}
            onClick={() => onTrack()}
            disabled={isTracked || isTrackPending}
            variant="compact"
            title={watchlistActionTitle}
          />
          <ActionButton
            label={language === 'en' ? 'View evidence' : '查看证据'}
            icon={isExpanded ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
            onClick={() => onViewEvidence()}
          />
        </div>
        <ScannerBacktestResultStrip item={backtestItem} language={language} />
      </div>

      {isExpanded ? detailPanel : null}
    </button>
  );
}

export function ScannerCandidateTableRow({
  candidate,
  candidateIdentity,
  language,
  rowState,
  keyReason,
  riskSummary,
  sourceBadge,
  scoreBadgeClassName,
  watchlistState,
  analyzeAction,
  copyAction,
  backtestAction,
  detailPanel,
  onSelect,
  onToggleDetail,
  onToggleMore,
}: {
  candidate: ScannerCandidate;
  candidateIdentity: string;
  language: 'zh' | 'en';
  rowState: Pick<ScannerRowState, 'expanded' | 'moreOpen'>;
  keyReason: string;
  riskSummary: string;
  sourceBadge: string;
  scoreBadgeClassName: string;
  watchlistState: Pick<ScannerWatchlistState, 'tracked' | 'pending' | 'label' | 'title' | 'onTrack'>;
  analyzeAction: ScannerAnalyzeAction;
  copyAction: Pick<ScannerCopyAction, 'label' | 'onCopy'>;
  backtestAction: Pick<ScannerBacktestAction, 'label' | 'title' | 'onBacktest'> & { disabled: boolean };
  detailPanel?: ReactNode;
  onSelect: () => void;
  onToggleDetail: () => void;
  onToggleMore: () => void;
}) {
  return (
    <>
      <tr
        data-testid={`scanner-result-row-${candidateIdentity}`}
        className="cursor-pointer border-b border-white/7 text-white/72 hover:bg-white/[0.028]"
        onClick={() => onSelect()}
      >
        <td className="w-[54px] px-2.5 py-1.5 text-white/45">#{candidate.rank}</td>
        <td className="min-w-[170px] px-2.5 py-1.5">
          <p className="font-mono text-sm font-semibold text-white">{candidate.symbol}</p>
          <p className="max-w-[300px] truncate text-[11px] text-white/45">{candidate.companyName || candidate.name}</p>
        </td>
        <td className="w-[104px] px-2.5 py-1.5">
          <span className={`inline-flex rounded border px-1.5 py-0.5 text-[10px] font-bold tabular-nums ${scoreBadgeClassName}`}>
            {candidate.score}/100
          </span>
        </td>
        <td className="w-[108px] px-2.5 py-1.5">
          <span className="inline-flex rounded border border-emerald-400/20 bg-emerald-400/10 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-widest text-emerald-100">
            {language === 'en' ? 'Official' : '官方'}
          </span>
        </td>
        <td className="min-w-[280px] px-2.5 py-1.5">
          <p className="truncate text-xs text-white/68" title={keyReason}>{keyReason}</p>
          <p className="truncate text-[11px] text-white/38" title={riskSummary}>{riskSummary}</p>
        </td>
        <td className="min-w-[140px] px-2.5 py-1.5 text-white/50">{sourceBadge}</td>
        <td className="min-w-[178px] px-2.5 py-1.5">
          <div className="flex flex-nowrap justify-end gap-1">
            <ActionButton
              label={language === 'en' ? 'Analyze' : '分析'}
              onClick={analyzeAction.onAnalyze}
              disabled={analyzeAction.disabled}
              variant="compact"
            />
            <ActionButton label={language === 'en' ? 'Detail' : '详情'} onClick={() => onToggleDetail()} />
            <ActionButton label={language === 'en' ? 'More' : '更多'} onClick={() => onToggleMore()} />
          </div>
          {rowState.moreOpen ? (
            <div data-testid={`scanner-result-row-more-${candidateIdentity}`} className="mt-1.5 flex flex-wrap justify-end gap-1.5 border-t border-white/8 pt-1.5">
              <ActionButton
                label={watchlistState.label}
                icon={watchlistState.tracked ? <BookmarkCheck className="size-3.5" /> : <BookmarkPlus className="size-3.5" />}
                onClick={watchlistState.onTrack}
                disabled={watchlistState.tracked || watchlistState.pending}
                variant="compact"
                title={watchlistState.title}
              />
              <ActionButton label={copyAction.label} onClick={copyAction.onCopy} />
              <ActionButton
                label={backtestAction.label}
                onClick={backtestAction.onBacktest}
                disabled={backtestAction.disabled}
                title={backtestAction.title}
              />
            </div>
          ) : null}
        </td>
      </tr>
      {rowState.expanded ? (
        <tr>
          <td colSpan={7} className="border-b border-white/7 px-2.5 pb-2">
            {detailPanel}
          </td>
        </tr>
      ) : null}
    </>
  );
}
