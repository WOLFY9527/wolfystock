import type { KeyboardEvent as ReactKeyboardEvent, ReactNode } from 'react';
import {
  BookmarkCheck,
  BookmarkPlus,
  Copy,
  Download,
  Play,
  TestTubeDiagonal,
} from 'lucide-react';
import { EvidenceChips } from '../evidence/EvidenceChips';
import {
  ScannerCandidateEvidenceStrip,
  type CandidateEvidenceFrame,
} from './ScannerCandidateEvidenceStrip';
import ScannerCandidateResearchSummary, {
  type ScannerCandidateResearchSummaryFrame,
} from './ScannerCandidateResearchSummary';
import type { SourceProvenanceSummary } from '../../types/analysis';
import type { NormalizedEvidenceSummary } from '../../utils/evidenceDisplay';
import type { ResearchReadinessV1 } from '../../types/researchReadiness';
import type {
  InvestorSignalContract,
  ScannerCandidate,
  ScannerCandidateDiagnostic,
  ScannerLabeledValue,
} from '../../types/scanner';
import type { ScannerBacktestItem } from './scannerBacktestShared';
import { ScannerActionButton as ActionButton } from './ScannerActionButton';
import { ScannerBacktestResultStrip } from './ScannerBacktestResultStrip';
import {
  AdvancedDisclosure,
  FieldChip,
  LabeledValueGrid,
  NotesList,
} from './ScannerDisplayAtoms';
import { ScannerScoreTrustStrip } from './ScannerScoreTrustStrip';

type CandidateDetailOutcomeItem = {
  label: string;
  value: string;
};

type ScannerCandidateWithEvidence = ScannerCandidate & {
  candidateEvidenceFrame?: CandidateEvidenceFrame | null;
  candidateResearchReadiness?: ResearchReadinessV1 | null;
  candidateResearchSummaryFrame?: ScannerCandidateResearchSummaryFrame | null;
  candidateSourceProvenanceFrame?: SourceProvenanceSummary | null;
};

function asScannerCandidateWithEvidence(candidate: ScannerCandidate): ScannerCandidateWithEvidence {
  return candidate as ScannerCandidateWithEvidence;
}

const INVESTOR_SIGNAL_REASON_LABELS_ZH: Record<string, string> = {
  source_authority_missing: '来源确认待补齐',
  score_rights_missing: '暂不进入评分',
  observation_only: '仅作观察',
  partial_source: '部分数据仍待补齐',
  stale_source: '部分线索已过期',
  fallback_source: '当前仅保留最近一次可用线索',
};

const INVESTOR_SIGNAL_REASON_LABELS_EN: Record<string, string> = {
  source_authority_missing: 'Source confirmation pending',
  score_rights_missing: 'Score stays observational',
  observation_only: 'Observation only',
  partial_source: 'Some source coverage is still partial',
  stale_source: 'Some supporting inputs are stale',
  fallback_source: 'Using the latest available signal only',
};

const INVESTOR_SIGNAL_CONTRADICTION_LABELS_ZH: Record<string, string> = {
  btc_not_confirming_growth_absorption: 'BTC 未确认当前吸纳',
  rates_not_easing_broadly: '利率线索尚未同步转松',
};

const INVESTOR_SIGNAL_CONTRADICTION_LABELS_EN: Record<string, string> = {
  btc_not_confirming_growth_absorption: 'BTC not confirming current absorption',
  rates_not_easing_broadly: 'Rates are not easing broadly yet',
};

function formatInvestorSignalCodeLabel(
  value: string,
  language: 'zh' | 'en',
  labelsZh: Record<string, string>,
  labelsEn: Record<string, string>,
): string {
  const normalized = value.trim().toLowerCase();
  if (!normalized) return '';
  const mapped = language === 'en' ? labelsEn[normalized] : labelsZh[normalized];
  if (mapped) return mapped;
  return normalized
    .split('_')
    .filter(Boolean)
    .map((part) => (part === 'btc' || part === 'ai' ? part.toUpperCase() : part))
    .join(' ');
}

function uniqueInvestorSignalLabels(items: string[]): string[] {
  return items.filter((item, index, array) => item && array.indexOf(item) === index);
}

function formatInvestorSignalState(signal?: InvestorSignalContract | null): string | null {
  const label = signal?.capitalFlowLabel || signal?.themeFlowLabel || signal?.marketRegimeLabel;
  if (typeof label === 'string' && label.trim()) return label.trim();
  const fallback = signal?.capitalFlowRegime || signal?.themeFlowState || signal?.marketRegime;
  if (typeof fallback !== 'string' || !fallback.trim()) return null;
  return fallback
    .trim()
    .split('_')
    .map((part) => (part === 'ai' ? 'AI' : part))
    .join(' ');
}

function formatInvestorSignalConfidence(signal?: InvestorSignalContract | null): string | null {
  const label = String(signal?.confidenceText || signal?.confidenceLabel || '').trim();
  if (label) return label;
  const raw = signal?.confidence;
  if (typeof raw === 'number' && Number.isFinite(raw)) {
    return `${Math.round(raw <= 1 ? raw * 100 : raw)}%`;
  }
  if (typeof raw === 'string') {
    const numeric = Number(raw);
    if (Number.isFinite(numeric)) {
      return `${Math.round(numeric <= 1 ? numeric * 100 : numeric)}%`;
    }
    return raw.trim() || null;
  }
  return null;
}

function formatInvestorSignalFreshness(value?: string | null, language: 'zh' | 'en' = 'zh'): string | null {
  const normalized = String(value || '').trim().toLowerCase();
  if (!normalized) return null;
  const labelsZh: Record<string, string> = {
    live: '实时',
    cached: '缓存',
    delayed: '延迟',
    partial: '部分',
    stale: '过期',
    fallback: '最近一次可用',
  };
  const labelsEn: Record<string, string> = {
    live: 'Live',
    cached: 'Cached',
    delayed: 'Delayed',
    partial: 'Partial',
    stale: 'Stale',
    fallback: 'Latest available',
  };
  return language === 'en' ? (labelsEn[normalized] || normalized) : (labelsZh[normalized] || normalized);
}

function handleSelectableContainerKeyDown(
  event: ReactKeyboardEvent<HTMLElement>,
  onSelect: () => void,
) {
  if (event.target !== event.currentTarget) {
    return;
  }
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault();
    onSelect();
  }
}

function investorSignalReasonLabels(signal?: InvestorSignalContract | null, language: 'zh' | 'en' = 'zh'): string[] {
  const codes = Array.isArray(signal?.reasonCodes) ? signal.reasonCodes : [];
  return uniqueInvestorSignalLabels(
    codes
      .flatMap((code) => {
        const label = formatInvestorSignalCodeLabel(String(code || ''), language, INVESTOR_SIGNAL_REASON_LABELS_ZH, INVESTOR_SIGNAL_REASON_LABELS_EN);
        return label ? [label] : [];
      }),
  ).slice(0, 3);
}

function investorSignalContradictionLabels(signal?: InvestorSignalContract | null, language: 'zh' | 'en' = 'zh'): string[] {
  const codes = Array.isArray(signal?.contradictionCodes) ? signal.contradictionCodes : [];
  return uniqueInvestorSignalLabels(
    codes
      .flatMap((code) => {
        const label = formatInvestorSignalCodeLabel(String(code || ''), language, INVESTOR_SIGNAL_CONTRADICTION_LABELS_ZH, INVESTOR_SIGNAL_CONTRADICTION_LABELS_EN);
        return label ? [label] : [];
      }),
  ).slice(0, 3);
}

function InvestorSignalDetailSection({
  signal,
  language,
  candidateIdentity,
}: {
  signal?: InvestorSignalContract | null;
  language: 'zh' | 'en';
  candidateIdentity: string;
}) {
  const stateLabel = formatInvestorSignalState(signal);
  const confidenceLabel = formatInvestorSignalConfidence(signal);
  const freshnessLabel = formatInvestorSignalFreshness(signal?.freshness, language);
  const reasonLabels = investorSignalReasonLabels(signal, language);
  const contradictionLabels = investorSignalContradictionLabels(signal, language);
  const explanation = typeof signal?.explanation === 'string' && signal.explanation.trim()
    ? signal.explanation.trim()
    : null;
  const hasVisibleContent = Boolean(stateLabel || confidenceLabel || freshnessLabel || reasonLabels.length || contradictionLabels.length || explanation);

  if (!hasVisibleContent) {
    return null;
  }

  return (
    <BoardDetailSection title={language === 'en' ? 'Investor signal' : '投资者信号'}>
      <div data-testid={`scanner-investor-signal-${candidateIdentity}`} className="space-y-2">
        <div className="flex flex-wrap gap-1.5">
          {stateLabel ? <FieldChip label={language === 'en' ? 'State' : '状态'} value={stateLabel} /> : null}
          {confidenceLabel ? <FieldChip label={language === 'en' ? 'Confidence' : '置信度'} value={confidenceLabel} /> : null}
          {freshnessLabel ? <FieldChip label={language === 'en' ? 'Freshness' : '时效'} value={freshnessLabel} /> : null}
        </div>
        {reasonLabels.length ? (
          <div className="space-y-1">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-white/36">
              {language === 'en' ? 'Why constrained' : '为什么受限'}
            </p>
            <NotesList notes={reasonLabels} empty="" />
          </div>
        ) : null}
        {contradictionLabels.length ? (
          <div className="space-y-1">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-white/36">
              {language === 'en' ? 'Counter cues' : '反向线索'}
            </p>
            <NotesList notes={contradictionLabels} empty="" />
          </div>
        ) : null}
        {explanation ? (
          <div className="space-y-1">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-white/36">
              {language === 'en' ? 'Explanation' : '说明'}
            </p>
            <p className="text-xs leading-relaxed text-white/64">{explanation}</p>
          </div>
        ) : null}
      </div>
    </BoardDetailSection>
  );
}

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
  const candidateWithEvidence = asScannerCandidateWithEvidence(candidate);
  const aiAvailable = Boolean(candidate.aiInterpretation?.available);
  const investorSignal = candidate.consumerDiagnostics?.investorSignal;

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
      {candidateWithEvidence.candidateEvidenceFrame || candidateWithEvidence.candidateResearchReadiness ? (
        <BoardDetailSection title={language === 'en' ? 'Evidence coverage' : '证据覆盖'}>
          <ScannerCandidateEvidenceStrip
            frame={candidateWithEvidence.candidateEvidenceFrame}
            provenanceFrame={candidateWithEvidence.candidateSourceProvenanceFrame}
            readiness={candidateWithEvidence.candidateResearchReadiness}
            language={language}
            variant="detail"
            testId={`scanner-candidate-evidence-detail-${candidateIdentity}`}
          />
        </BoardDetailSection>
      ) : null}
      {outcomeItems.length ? (
        <BoardDetailSection title={language === 'en' ? 'Realized outcome' : '实际表现'}>
          <div className="flex flex-wrap gap-2">
            {outcomeItems.map((item) => (
              <FieldChip key={`${item.label}-${item.value}`} label={item.label} value={item.value} />
            ))}
          </div>
        </BoardDetailSection>
      ) : null}
      <div className="md:col-span-4 flex flex-wrap items-center gap-2 border-t border-white/8 py-2">
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
              <BoardDetailSection title={language === 'en' ? 'Evidence status' : '证据状态'}>
                <EvidenceChips summary={evidenceSummary} maxLabels={2} />
              </BoardDetailSection>
            ) : null}
            <InvestorSignalDetailSection
              signal={investorSignal}
              language={language}
              candidateIdentity={candidateIdentity}
            />
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
        <ScannerBacktestResultStrip item={backtestItem} language={language} />
      </div>
    </div>
  );
}

export function ScannerCandidateDiagnosticRow({
  candidate,
  trustSources,
  language,
  isSelectedCandidate,
  isExpanded,
  isMoreOpen,
  displayName,
  keyReason,
  previewLabel,
  previewBadgeClassName,
  dataQualityLabel,
  watchSummary,
  rangeSummary,
  evidenceSummary,
  candidateEvidenceFrame,
  candidateResearchReadiness,
  candidateResearchSummaryFrame,
  candidateSourceProvenanceFrame,
  scoreLabel,
  scoreDelta,
  comparisonLabel,
  statusLabel,
  watchlistActionLabel,
  watchlistActionTitle,
  copyLabel,
  exportLabel,
  isTracked,
  isTrackPending,
  isWatchlistAuthBlocked,
  isAnalyzing,
  backtestLabel,
  backtestTitle,
  backtestItem,
  detailPanel,
  onSelect,
  onAnalyze,
  onBacktest,
  onTrack,
  onCopy,
  onExport,
  onToggleMore,
}: {
  candidate: ScannerCandidateDiagnostic;
  trustSources?: Array<ScannerCandidate | ScannerCandidateDiagnostic | null | undefined>;
  language: 'zh' | 'en';
  isSelectedCandidate: boolean;
  isExpanded: boolean;
  isMoreOpen: boolean;
  displayName: string;
  keyReason: string;
  previewLabel: string;
  previewBadgeClassName: string;
  dataQualityLabel: string;
  watchSummary: string;
  rangeSummary: string;
  evidenceSummary: NormalizedEvidenceSummary | null;
  candidateEvidenceFrame?: CandidateEvidenceFrame | null;
  candidateResearchReadiness?: ResearchReadinessV1 | null;
  candidateResearchSummaryFrame?: ScannerCandidateResearchSummaryFrame | null;
  candidateSourceProvenanceFrame?: SourceProvenanceSummary | null;
  scoreLabel: string;
  scoreDelta?: string | null;
  comparisonLabel?: string | null;
  statusLabel: string;
  watchlistActionLabel: string;
  watchlistActionTitle?: string;
  copyLabel: string;
  exportLabel: string;
  isTracked: boolean;
  isTrackPending: boolean;
  isWatchlistAuthBlocked: boolean;
  isAnalyzing: boolean;
  backtestLabel: string;
  backtestTitle?: string;
  backtestItem?: ScannerBacktestItem;
  detailPanel?: ReactNode;
  onSelect: () => void;
  onAnalyze: () => void;
  onBacktest: () => void;
  onTrack: () => void;
  onCopy: () => void;
  onExport: () => void;
  onToggleMore: () => void;
}) {
  const resolvedTrustSources = trustSources?.length ? trustSources : [candidate];
  return (
    <article
      data-testid={`scanner-ranked-row-${candidate.symbol}`}
      data-selected={isSelectedCandidate ? 'true' : undefined}
      onClick={onSelect}
      onKeyDown={(event) => handleSelectableContainerKeyDown(event, onSelect)}
      className={`cursor-pointer border-b border-white/7 px-3 py-2.5 text-sm transition-colors ${
        isSelectedCandidate
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
              <p className={`mt-1 font-mono text-sm font-semibold ${isSelectedCandidate ? 'text-emerald-50' : 'text-white/72'}`}>
                {candidate.rank ? `#${candidate.rank}` : '--'}
              </p>
            </div>
            <div className="min-w-0">
              <p className={`truncate font-mono text-sm font-semibold ${isSelectedCandidate ? 'text-emerald-50' : 'text-white'}`}>
                {candidate.symbol || '--'}
              </p>
              <p className="truncate text-[11px] text-white/38">{displayName}</p>
              {comparisonLabel ? <p className="mt-1 truncate text-[10px] text-cyan-100/70">{comparisonLabel}</p> : null}
            </div>
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-white/30">{language === 'en' ? 'Score' : '评分'}</p>
              <p className={`mt-1 font-mono text-sm font-semibold ${isSelectedCandidate ? 'text-emerald-100' : 'text-white/78'}`}>{scoreLabel}</p>
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
              {candidateResearchSummaryFrame ? (
                <ScannerCandidateResearchSummary
                  frame={candidateResearchSummaryFrame}
                  language={language}
                  variant="row"
                  testId={`scanner-candidate-summary-row-${candidate.symbol}`}
                />
              ) : null}
            </div>
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-white/30">{language === 'en' ? 'Data quality' : '数据质量'}</p>
              <p className="mt-1 truncate text-xs text-white/62" title={dataQualityLabel}>{dataQualityLabel}</p>
              {candidateEvidenceFrame || candidateResearchReadiness ? (
                <ScannerCandidateEvidenceStrip
                  frame={candidateEvidenceFrame}
                  provenanceFrame={candidateSourceProvenanceFrame}
                  readiness={candidateResearchReadiness}
                  language={language}
                  variant="row"
                  testId={`scanner-candidate-evidence-row-${candidate.symbol}`}
                />
              ) : null}
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
                  <span className={`font-mono text-sm font-semibold ${isSelectedCandidate ? 'text-emerald-50' : 'text-white'}`}>
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
              {candidateResearchSummaryFrame ? (
                <ScannerCandidateResearchSummary
                  frame={candidateResearchSummaryFrame}
                  language={language}
                  variant="row"
                  testId={`scanner-candidate-summary-mobile-row-${candidate.symbol}`}
                />
              ) : null}
              <p title={dataQualityLabel}>{dataQualityLabel}</p>
              {candidateEvidenceFrame || candidateResearchReadiness ? (
                <ScannerCandidateEvidenceStrip
                  frame={candidateEvidenceFrame}
                  provenanceFrame={candidateSourceProvenanceFrame}
                  readiness={candidateResearchReadiness}
                  language={language}
                  variant="row"
                  testId={`scanner-candidate-evidence-mobile-row-${candidate.symbol}`}
                />
              ) : null}
              <p title={watchSummary}>{watchSummary}</p>
              <p className="text-[11px] text-white/38" title={rangeSummary}>{rangeSummary}</p>
              <ScannerScoreTrustStrip sources={resolvedTrustSources} language={language} className="pt-0.5" testId={`scanner-score-trust-mobile-${candidate.symbol}`} />
              {evidenceSummary ? <EvidenceChips summary={evidenceSummary} maxLabels={2} /> : null}
            </div>
            <div className="flex flex-wrap gap-2">
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
      {isMoreOpen ? (
        <div data-testid={`scanner-candidate-row-more-${candidate.symbol}`} className="mt-1.5 flex flex-wrap gap-2 border-t border-white/8 pt-2">
          <ActionButton
            label={isAnalyzing ? (language === 'en' ? 'Analyzing...' : '分析中...') : (language === 'en' ? 'Analyze' : '分析')}
            onClick={onAnalyze}
            disabled={isAnalyzing}
          />
          <ActionButton
            label={backtestLabel}
            onClick={onBacktest}
            disabled={!candidate.symbol || backtestItem?.status === 'running' || backtestItem?.status === 'queued'}
            title={backtestTitle}
          />
          <ActionButton
            label={watchlistActionLabel}
            onClick={onTrack}
            disabled={isTracked || isTrackPending || isWatchlistAuthBlocked}
            title={watchlistActionTitle}
          />
          <ActionButton
            label={copyLabel}
            onClick={onCopy}
          />
          <ActionButton
            label={exportLabel}
            onClick={onExport}
          />
        </div>
      ) : null}
      {isExpanded && detailPanel ? (
        <div data-testid={`scanner-candidate-detail-${candidate.symbol}`} className="mt-3 border-t border-white/8 pt-3">
          {detailPanel}
        </div>
      ) : null}
    </article>
  );
}
