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
import type { ScannerBacktestItem } from './useScannerBacktestLab';
import { ScannerActionButton as ActionButton } from './ScannerActionButton';
import {
  ScannerBacktestResultStrip,
} from './ScannerBacktestLab';
import {
  AdvancedDisclosure,
  DetailSection,
  FieldChip,
  LabeledValueGrid,
  NotesList,
} from './ScannerDisplayAtoms';
import { TerminalButton } from '../terminal';

type CandidateDetailOutcomeItem = {
  label: string;
  value: string;
};

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
  onAnalyze,
  onCopy,
  onExport,
  onTrack,
  onBacktest,
  isAnalyzing,
  isCopied,
  isTracked,
  isTrackPending,
  isWatchlistAuthBlocked,
  watchlistActionLabel,
  watchlistActionTitle,
  backtestLabel,
  backtestTitle,
  backtestItem,
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
  onAnalyze: () => void;
  onCopy: () => void;
  onExport: () => void;
  onTrack: () => void;
  onBacktest: () => void;
  isAnalyzing: boolean;
  isCopied: boolean;
  isTracked: boolean;
  isTrackPending: boolean;
  isWatchlistAuthBlocked: boolean;
  watchlistActionLabel: string;
  watchlistActionTitle?: string;
  backtestLabel: string;
  backtestTitle?: string;
  backtestItem?: ScannerBacktestItem;
}) {
  const aiAvailable = Boolean(candidate.aiInterpretation?.available);

  return (
    <div
      data-testid={`scanner-result-detail-${candidateIdentity}`}
      className="mt-2 grid gap-2 rounded-xl border border-white/8 bg-black/24 p-3 md:grid-cols-4"
    >
      <DetailSection title={language === 'en' ? 'Conclusion' : '结论'}>
        <p className="text-xs leading-relaxed text-white/68">{selectionNotes[0] || candidate.reasonSummary || keyMetricItems[0]?.value || aiUnavailableText}</p>
      </DetailSection>
      <DetailSection title={language === 'en' ? 'Reason' : '理由'}>
        <NotesList notes={selectionNotes.slice(0, 2)} empty={language === 'en' ? 'No selection notes provided' : '未提供入选说明'} />
      </DetailSection>
      <DetailSection title={language === 'en' ? 'Risk' : '风险'}>
        <NotesList notes={riskNotes.slice(0, 2)} empty={language === 'en' ? 'No risk notes provided' : '未提供风险说明'} />
      </DetailSection>
      <DetailSection title={language === 'en' ? 'Next step' : '下一步'}>
        <div className="flex flex-wrap gap-1.5">
          {entryRange ? <FieldChip label={language === 'en' ? 'Entry' : '建仓'} value={entryRange} /> : null}
          {targetPrice ? <FieldChip label={language === 'en' ? 'Target' : '目标'} value={targetPrice} /> : null}
          {stopLoss ? <FieldChip label={language === 'en' ? 'Stop' : '止损'} value={stopLoss} /> : null}
          {!entryRange && !targetPrice && !stopLoss ? (
            <p className="text-xs text-white/36">{language === 'en' ? 'Analyze or backtest before acting.' : '先分析或回测，再执行操作。'}</p>
          ) : null}
        </div>
      </DetailSection>
      <DetailSection title={language === 'en' ? 'Key metrics' : '关键指标'}>
        <LabeledValueGrid items={keyMetricItems.slice(0, 5)} empty={language === 'en' ? 'No key metrics provided' : '未提供关键指标'} />
      </DetailSection>
      {outcomeItems.length ? (
        <DetailSection title={language === 'en' ? 'Realized outcome' : '实际表现'}>
          <div className="flex flex-wrap gap-2">
            {outcomeItems.map((item) => (
              <FieldChip key={`${item.label}-${item.value}`} label={item.label} value={item.value} />
            ))}
          </div>
        </DetailSection>
      ) : null}
      <div className="md:col-span-4 flex flex-wrap items-center gap-1.5 border-t border-white/5 pt-2">
        <ActionButton
          label={isAnalyzing ? (language === 'en' ? 'Analyzing...' : '分析中...') : (language === 'en' ? 'Analyze' : '分析')}
          icon={<Play className="h-3.5 w-3.5" />}
          onClick={() => onAnalyze()}
          disabled={isAnalyzing}
          variant="compact"
        />
        <ActionButton
          label={watchlistActionLabel}
          icon={isTracked ? <BookmarkCheck className="h-3.5 w-3.5" /> : <BookmarkPlus className="h-3.5 w-3.5" />}
          onClick={() => onTrack()}
          disabled={isTrackPending || isTracked || isWatchlistAuthBlocked}
          variant="compact"
          title={watchlistActionTitle}
        />
        <ActionButton
          label={backtestLabel}
          icon={<TestTubeDiagonal className="h-3.5 w-3.5" />}
          onClick={() => onBacktest()}
          disabled={!candidate.symbol || backtestItem?.status === 'running' || backtestItem?.status === 'queued'}
          title={backtestTitle}
        />
        <ActionButton
          label={isCopied ? (language === 'en' ? 'Copied' : '已复制') : (language === 'en' ? 'Copy symbol' : '复制代码')}
          icon={<Copy className="h-3.5 w-3.5" />}
          onClick={() => onCopy()}
        />
        <ActionButton
          label={language === 'en' ? 'Export candidate' : '导出该候选'}
          icon={<Download className="h-3.5 w-3.5" />}
          onClick={() => onExport()}
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
              <DetailSection title={language === 'en' ? 'Evidence status' : '证据状态'}>
                <EvidenceChips summary={evidenceSummary} maxLabels={2} />
              </DetailSection>
            ) : null}
            {featureSignalItems.length ? (
              <DetailSection title={language === 'en' ? 'Feature signals' : '特征信号'}>
                <LabeledValueGrid items={featureSignalItems.slice(0, 4)} empty={language === 'en' ? 'No feature signals provided' : '未提供特征信号'} />
              </DetailSection>
            ) : null}
            {aiAvailable ? (
              <DetailSection title={language === 'en' ? 'AI interpretation' : 'AI 解读'}>
                <div className="space-y-2 text-xs leading-relaxed text-white/64">
                  {aiLines.length ? aiLines.slice(0, 3).map((line) => <p key={line}>{line}</p>) : <p>{candidate.aiInterpretation?.status}</p>}
                </div>
              </DetailSection>
            ) : null}
            {providerNotes ? (
              <DetailSection title={language === 'en' ? 'Source' : '来源'}>
                <p className="text-xs leading-relaxed text-white/64">{providerNotes}</p>
              </DetailSection>
            ) : null}
          </div>
        </AdvancedDisclosure>
      ) : null}
      <div className="md:col-span-4">
        <ScannerBacktestResultStrip item={backtestItem} language={language} />
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
  onCopy,
  onExport,
  onTrack,
  isCopied,
  isTracked,
  isTrackPending,
  isWatchlistAuthBlocked,
  watchlistActionLabel,
  watchlistActionTitle,
  backtestItem,
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
  onCopy: () => void;
  onExport: () => void;
  onTrack: () => void;
  isCopied: boolean;
  isTracked: boolean;
  isTrackPending: boolean;
  isWatchlistAuthBlocked: boolean;
  watchlistActionLabel: string;
  watchlistActionTitle?: string;
  backtestItem?: ScannerBacktestItem;
  testId?: string;
}) {
  return (
    <aside
      data-testid={testId}
      className="flex max-h-full min-h-0 flex-col overflow-hidden rounded-xl border border-white/5 bg-white/[0.02] text-sm backdrop-blur-md transition-all hover:border-white/10"
    >
      <div className="border-b border-white/5 px-3 py-3">
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
              label={isCopied ? (language === 'en' ? 'Copied' : '已复制') : (language === 'en' ? 'Copy symbol' : '复制代码')}
              icon={<Copy className="h-3.5 w-3.5" />}
              onClick={() => onCopy()}
            />
            <ActionButton
              label={language === 'en' ? 'Export' : '导出'}
              icon={<Download className="h-3.5 w-3.5" />}
              onClick={() => onExport()}
            />
            <ActionButton
              label={watchlistActionLabel}
              icon={isTracked ? <BookmarkCheck className="h-3.5 w-3.5" /> : <BookmarkPlus className="h-3.5 w-3.5" />}
              onClick={() => onTrack()}
              disabled={isTracked || isTrackPending || isWatchlistAuthBlocked}
              title={watchlistActionTitle}
            />
          </div>
          <ScannerBacktestResultStrip item={backtestItem} language={language} />
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
  language,
  isSelectedCandidate,
  isInspectorActive,
  isExpanded,
  isMoreOpen,
  previewLabel,
  previewBadgeClassName,
  friendlyReason,
  dataQualityLabel,
  evidenceSummary,
  scoreLabel,
  scoreDelta,
  comparisonLabel,
  statusLabel,
  missingCount,
  failedRuleNotes,
  missingFieldNotes,
  watchlistActionLabel,
  watchlistActionTitle,
  copyLabel,
  isTracked,
  isTrackPending,
  isWatchlistAuthBlocked,
  backtestLabel,
  backtestTitle,
  backtestItem,
  onSelect,
  onViewEvidence,
  onToggleMore,
  onBacktest,
  onTrack,
  onCopy,
  onExport,
}: {
  candidate: ScannerCandidateDiagnostic;
  language: 'zh' | 'en';
  isSelectedCandidate: boolean;
  isInspectorActive: boolean;
  isExpanded: boolean;
  isMoreOpen: boolean;
  previewLabel: string;
  previewBadgeClassName: string;
  friendlyReason: string;
  dataQualityLabel: string;
  evidenceSummary: NormalizedEvidenceSummary | null;
  scoreLabel: string;
  scoreDelta?: string | null;
  comparisonLabel?: string | null;
  statusLabel: string;
  missingCount: number;
  failedRuleNotes: string[];
  missingFieldNotes: string[];
  watchlistActionLabel: string;
  watchlistActionTitle?: string;
  copyLabel: string;
  isTracked: boolean;
  isTrackPending: boolean;
  isWatchlistAuthBlocked: boolean;
  backtestLabel: string;
  backtestTitle?: string;
  backtestItem?: ScannerBacktestItem;
  onSelect: () => void;
  onViewEvidence: () => void;
  onToggleMore: () => void;
  onBacktest: () => void;
  onTrack: () => void;
  onCopy: () => void;
  onExport: () => void;
}) {
  return (
    <article
      data-testid={`scanner-candidate-row-${candidate.symbol}`}
      data-selected={isSelectedCandidate ? 'true' : undefined}
      onClick={() => onSelect()}
      className={`rounded-lg border px-3 py-2 text-sm transition-all ${isSelectedCandidate ? 'border-emerald-400/20 bg-emerald-400/[0.04] shadow-[inset_2px_0_0_rgba(52,211,153,0.28)]' : isInspectorActive ? 'border-cyan-400/16 bg-cyan-400/[0.03]' : 'border-white/7 bg-white/[0.014] hover:border-white/12 hover:bg-white/[0.024]'}`}
    >
      <div className="grid min-w-0 grid-cols-1 gap-2 md:grid-cols-[minmax(52px,0.35fr)_minmax(92px,0.7fr)_minmax(76px,0.5fr)_minmax(80px,0.55fr)_minmax(0,1.7fr)_minmax(120px,0.8fr)_auto] md:items-center">
        <div className="font-mono text-[11px] text-white/42">{candidate.rank ? `#${candidate.rank}` : '--'}</div>
        <div className="min-w-0">
          <p className={`truncate font-mono text-sm font-semibold ${isSelectedCandidate ? 'text-emerald-50' : 'text-white/86'}`}>{candidate.symbol || '--'}</p>
          <p className="truncate text-[11px] text-white/32">{candidate.name || candidate.symbol || '--'}</p>
        </div>
        <div className={`font-mono text-xs font-semibold ${isSelectedCandidate ? 'text-emerald-100' : 'text-white/78'}`}>
          {scoreLabel}
          {scoreDelta ? <span className="ml-1 text-[10px] text-white/42">{scoreDelta}</span> : null}
          {comparisonLabel ? <span className="ml-1 rounded border border-white/8 bg-white/[0.035] px-1 py-0.5 font-sans text-[10px] font-medium text-white/58">{comparisonLabel}</span> : null}
        </div>
        <div className="min-w-0">
          <p className={`inline-flex max-w-full rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-[0.1em] ${previewBadgeClassName}`}>
            <span className="truncate">{previewLabel}</span>
          </p>
        </div>
        <div className="min-w-0">
          <p className="truncate text-xs text-white/68" title={friendlyReason}>{friendlyReason}</p>
        </div>
        <div className="min-w-0">
          <p className="truncate text-[11px] text-white/58" title={dataQualityLabel}>{dataQualityLabel}</p>
        </div>
        <ActionButton label={language === 'en' ? 'Detail' : '详情'} onClick={() => onViewEvidence()} />
        <div className="relative">
          <ActionButton label={language === 'en' ? 'More' : '更多'} onClick={() => onToggleMore()} />
        </div>
      </div>
      {isMoreOpen ? (
        <div data-testid={`scanner-candidate-row-more-${candidate.symbol}`} className="mt-2 grid gap-1.5 rounded-xl border border-white/5 bg-black/20 p-2 sm:grid-cols-2 xl:grid-cols-4">
          <ActionButton
            label={backtestLabel}
            onClick={() => onBacktest()}
            disabled={!candidate.symbol || backtestItem?.status === 'running' || backtestItem?.status === 'queued'}
            title={backtestTitle}
          />
          <ActionButton
            label={watchlistActionLabel}
            onClick={() => onTrack()}
            disabled={isTracked || isTrackPending || isWatchlistAuthBlocked}
            title={watchlistActionTitle}
          />
          <ActionButton
            label={copyLabel}
            onClick={() => onCopy()}
          />
          <ActionButton
            label={language === 'en' ? 'Export' : '导出'}
            onClick={() => onExport()}
          />
        </div>
      ) : null}
      {isExpanded ? (
        <div data-testid={`scanner-candidate-detail-${candidate.symbol}`} className="mt-2 grid gap-2 border-t border-white/5 pt-2 text-xs text-white/58 md:grid-cols-3">
          {evidenceSummary ? (
            <DetailSection title={language === 'en' ? 'Evidence status' : '证据状态'}>
              <EvidenceChips summary={evidenceSummary} maxLabels={2} />
            </DetailSection>
          ) : null}
          <DetailSection title={language === 'en' ? 'Rule result' : '规则结果'}>
            <NotesList notes={failedRuleNotes} empty={language === 'en' ? 'No additional notes' : '暂无额外说明'} />
          </DetailSection>
          <DetailSection title={language === 'en' ? 'Missing fields' : '缺失字段'}>
            <NotesList notes={missingFieldNotes} empty={language === 'en' ? 'No missing data notes' : '暂无缺失数据说明'} />
          </DetailSection>
          <DetailSection title={language === 'en' ? 'Data status' : '数据状态'}>
            <div className="flex flex-wrap gap-1.5">
              <FieldChip label={language === 'en' ? 'Quality' : '质量'} value={dataQualityLabel} />
              <FieldChip label={language === 'en' ? 'Status' : '状态'} value={statusLabel} />
              <FieldChip label={language === 'en' ? 'Missing' : '缺失'} value={String(missingCount)} />
            </div>
          </DetailSection>
        </div>
      ) : null}
    </article>
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
    <article
      data-testid={`scanner-result-card-${candidateIdentity}`}
      onClick={() => onSelect()}
      className="rounded-xl border border-white/5 bg-white/[0.02] p-3 transition-colors hover:border-white/16 hover:bg-white/[0.04]"
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
          {isExpanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
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
            <div className="text-[10px] text-white/40 mb-1 uppercase">{language === 'en' ? 'Watch range' : '观察区间'}</div>
            <div className="truncate text-xs text-white font-medium">{entryRange || '--'}</div>
          </div>
          <div>
            <div className="text-[10px] text-white/40 mb-1 uppercase">{language === 'en' ? 'Upper watch' : '上方观察'}</div>
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
            icon={isTracked ? <BookmarkCheck className="h-3.5 w-3.5" /> : <BookmarkPlus className="h-3.5 w-3.5" />}
            onClick={() => onTrack()}
            disabled={isTracked || isTrackPending}
            variant="compact"
            title={watchlistActionTitle}
          />
          <ActionButton
            label={language === 'en' ? 'View evidence' : '查看证据'}
            icon={isExpanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
            onClick={() => onViewEvidence()}
          />
        </div>
        <ScannerBacktestResultStrip item={backtestItem} language={language} />
      </div>

      {isExpanded ? detailPanel : null}
    </article>
  );
}

export function ScannerCandidateTableRow({
  candidate,
  candidateIdentity,
  language,
  isExpanded,
  keyReason,
  riskSummary,
  sourceBadge,
  scoreBadgeClassName,
  watchlistActionLabel,
  watchlistActionTitle,
  copyLabel,
  backtestLabel,
  backtestTitle,
  isTracked,
  isTrackPending,
  isAnalyzing,
  isBacktestDisabled,
  isMoreOpen,
  detailPanel,
  onSelect,
  onAnalyze,
  onTrack,
  onCopy,
  onToggleDetail,
  onToggleMore,
  onBacktest,
}: {
  candidate: ScannerCandidate;
  candidateIdentity: string;
  language: 'zh' | 'en';
  isExpanded: boolean;
  keyReason: string;
  riskSummary: string;
  sourceBadge: string;
  scoreBadgeClassName: string;
  watchlistActionLabel: string;
  watchlistActionTitle?: string;
  copyLabel: string;
  backtestLabel: string;
  backtestTitle?: string;
  isTracked: boolean;
  isTrackPending: boolean;
  isAnalyzing: boolean;
  isBacktestDisabled: boolean;
  isMoreOpen: boolean;
  detailPanel?: ReactNode;
  onSelect: () => void;
  onAnalyze: () => void;
  onTrack: () => void;
  onCopy: () => void;
  onToggleDetail: () => void;
  onToggleMore: () => void;
  onBacktest: () => void;
}) {
  return (
    <>
      <tr
        data-testid={`scanner-result-row-${candidateIdentity}`}
        className="cursor-pointer border-b border-white/5 text-white/72 hover:bg-white/[0.035]"
        onClick={() => onSelect()}
      >
        <td className="w-[64px] px-3 py-2 text-white/45">#{candidate.rank}</td>
        <td className="min-w-[180px] px-3 py-2">
          <p className="font-mono text-sm font-semibold text-white">{candidate.symbol}</p>
          <p className="mt-0.5 max-w-[260px] truncate text-[11px] text-white/45">{candidate.companyName || candidate.name}</p>
        </td>
        <td className="w-[118px] px-3 py-2">
          <span className={`inline-flex rounded border px-1.5 py-0.5 text-[10px] font-bold tabular-nums ${scoreBadgeClassName}`}>
            {candidate.score}/100
          </span>
        </td>
        <td className="w-[118px] px-3 py-2">
          <span className="inline-flex rounded border border-emerald-400/20 bg-emerald-400/10 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-widest text-emerald-100">
            {language === 'en' ? 'Official' : '官方'}
          </span>
        </td>
        <td className="min-w-[260px] px-3 py-2">
          <p className="line-clamp-2 text-xs leading-relaxed text-white/68">{keyReason}</p>
          <p className="mt-0.5 truncate text-[11px] text-white/38">{riskSummary}</p>
        </td>
        <td className="min-w-[150px] px-3 py-2 text-white/50">{sourceBadge}</td>
        <td className="min-w-[190px] px-3 py-2">
          <div className="flex flex-wrap justify-end gap-1.5">
            <ActionButton
              label={language === 'en' ? 'Analyze' : '分析'}
              onClick={() => onAnalyze()}
              disabled={isAnalyzing}
              variant="compact"
            />
            <ActionButton label={language === 'en' ? 'Detail' : '详情'} onClick={() => onToggleDetail()} />
            <ActionButton label={language === 'en' ? 'More' : '更多'} onClick={() => onToggleMore()} />
          </div>
          {isMoreOpen ? (
            <div data-testid={`scanner-result-row-more-${candidateIdentity}`} className="mt-2 grid gap-1.5 rounded-lg border border-white/5 bg-black/35 p-2 sm:grid-cols-2">
              <ActionButton
                label={watchlistActionLabel}
                icon={isTracked ? <BookmarkCheck className="h-3.5 w-3.5" /> : <BookmarkPlus className="h-3.5 w-3.5" />}
                onClick={() => onTrack()}
                disabled={isTracked || isTrackPending}
                variant="compact"
                title={watchlistActionTitle}
              />
              <ActionButton label={copyLabel} onClick={() => onCopy()} />
              <ActionButton
                label={backtestLabel}
                onClick={() => onBacktest()}
                disabled={isBacktestDisabled}
                title={backtestTitle}
              />
            </div>
          ) : null}
        </td>
      </tr>
      {isExpanded ? (
        <tr>
          <td colSpan={7} className="border-b border-white/5 px-3 pb-4">
            {detailPanel}
          </td>
        </tr>
      ) : null}
    </>
  );
}
