import type React from 'react';
import { Suspense, lazy } from 'react';
import type { MarketOverviewTab } from '../../pages/MarketOverviewTabConfig';
import {
  ConsoleBoard,
  KeyLevelStrip,
} from '../linear';
import { TerminalChip, TerminalDisclosure } from '../terminal';
import { cn } from '../../utils/cn';
import type { MarketRegimeSynthesisHeaderView } from './MarketRegimeSynthesisHeader';
import type { OfficialMacroAuthorityRecord } from '../common/officialMacroAuthorityDiagnosticsData';
import { TrustDisclosureChips } from '../evidence/TrustDisclosureChips';
import { ProductSetupPath } from '../market-intelligence/ProductSetupPath';
import type { TrustDisclosureBucket } from '../../utils/trustDisclosure';
import {
  MARKET_DECISION_NOT_READY_NOTICE,
  decisionReadinessStateLabel,
  decisionReadinessVariant,
  joinMarketReasonLabels,
  marketIntelligenceReasonLabel,
  type DecisionReadinessState,
  type DecisionReadinessSummary,
  type MarketDirectionalSummary,
} from '../../utils/marketIntelligenceGuidance';

const MARKET_OVERVIEW_DEBUG_DETAILS_FALLBACK_MIN_MS = 120;

const LazyMarketOverviewDecisionDebugDetails = lazy(async () => {
  const [module] = await Promise.all([
    import('./MarketOverviewDecisionDebugDetails'),
    new Promise((resolve) => setTimeout(resolve, MARKET_OVERVIEW_DEBUG_DETAILS_FALLBACK_MIN_MS)),
  ]);
  return { default: module.MarketOverviewDecisionDebugDetails };
});

export type MarketOverviewDecisionChipView = {
  label: string;
  value: string;
  variant: 'neutral' | 'success' | 'caution' | 'danger' | 'info';
};

export type MarketOverviewHeroAnchorView = {
  key: string;
  primaryLabel: string;
  secondaryLabel?: string;
  valueText: string;
  changeText: string;
  changeToneClass: string;
};

export type MarketOverviewDataStateStripView = {
  availableCount: number;
  fallbackCount: number;
  staleCount: number;
  hasUnavailable: boolean;
  unavailableCount: number;
  hasFallback: boolean;
  needsRefresh: boolean;
  isRefreshing: boolean;
  updatedAtLabel: string;
  variant: 'neutral' | 'info' | 'caution';
};

export type MarketOverviewTemperatureSummaryView = {
  reliable: boolean;
  valueText: string;
  toneClass: string;
  label: string;
  confidenceLabel: string;
  reliableInputCount: number;
  fallbackInputCount: number;
  excludedInputCount: number;
};

export type MarketOverviewBriefingSummaryView = {
  confidenceLabel: string;
  toneClass: string;
  leadMessage: string;
  warning?: string;
};

export type MarketOverviewCategoryTabView = {
  key: MarketOverviewTab;
  label: string;
};

export type MarketOverviewDecisionSemanticsLineView = {
  key: string;
  label: string;
  meta?: string;
};

export type MarketOverviewDecisionSemanticsBoundaryView = {
  key: string;
  label: string;
  allowed: boolean;
  reasonCode?: string;
};

export type MarketOverviewDirectionReadinessPillarView = {
  key: string;
  label: string;
  reasonCode?: string;
};

export type MarketOverviewDirectionReadinessView = {
  status: 'direction_ready' | 'partial_context_only' | 'data_insufficient' | string;
  statusLabel: string;
  statusVariant: 'neutral' | 'success' | 'caution' | 'danger' | 'info';
  confidenceLabel: string;
  scoreGradeCount: number;
  observationOnlyCount: number;
  missingCount: number;
  scoreGradePillars: MarketOverviewDirectionReadinessPillarView[];
  observationOnlyPillars: MarketOverviewDirectionReadinessPillarView[];
  missingPillars: MarketOverviewDirectionReadinessPillarView[];
  blockingReasons: string[];
  notInvestmentAdvice: boolean;
};

export type MarketOverviewDecisionSemanticsView = {
  postureLabel: string;
  confidenceLabel: string;
  confidenceValueText: string;
  exposureBiasLabel: string;
  insufficient: boolean;
  capReasons: string[];
  styleTilts: MarketOverviewDecisionSemanticsLineView[];
  confirmationSignals: MarketOverviewDecisionSemanticsLineView[];
  invalidationTriggers: MarketOverviewDecisionSemanticsLineView[];
  counterEvidence: MarketOverviewDecisionSemanticsLineView[];
  dataGaps: MarketOverviewDecisionSemanticsLineView[];
  directionReadiness?: MarketOverviewDirectionReadinessView;
  claimBoundaries: MarketOverviewDecisionSemanticsBoundaryView[];
  notInvestmentAdvice: boolean;
};

type MarketOverviewWorkbenchTopSurfaceProps = {
  heading: React.ReactNode;
  directionalSummary: MarketDirectionalSummary;
  regimeSynthesis: MarketRegimeSynthesisHeaderView;
  decisionText: string;
  decisionChips: MarketOverviewDecisionChipView[];
  decisionReliable: boolean;
  decisionSemantics?: MarketOverviewDecisionSemanticsView;
  dataState: MarketOverviewDataStateStripView;
  temperatureSummary: MarketOverviewTemperatureSummaryView;
  briefingSummary: MarketOverviewBriefingSummaryView;
  officialMacroRecords: OfficialMacroAuthorityRecord[];
  categoryTabs: MarketOverviewCategoryTabView[];
  activeCategory: MarketOverviewTab;
  onCategoryChange: (tab: MarketOverviewTab) => void;
  exportLabel: string;
  onExportSummary: () => void;
  heroAnchors: MarketOverviewHeroAnchorView[];
};

const MarketOverviewDirectionSummary: React.FC<{ summary: MarketDirectionalSummary }> = ({ summary }) => (
  <section
    data-testid="market-overview-direction-summary"
    className="relative overflow-hidden border-t border-[color:var(--wolfy-divider)] bg-white/[0.022] px-3 py-3 md:px-4"
  >
    <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-cyan-400/0 via-cyan-200/38 to-sky-400/0" aria-hidden="true" />
    <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
      <div className="min-w-0">
        <p className="text-[10px] font-medium tracking-[0.24em] text-white/38">{summary.title}</p>
        <h2 className="mt-2 text-base font-semibold leading-6 text-white/92 md:text-lg">
          {summary.currentLabel}
        </h2>
        <div className="mt-2 flex min-w-0 flex-wrap gap-2">
          <TerminalChip variant={summary.biasVariant}>{summary.regimePhrase}</TerminalChip>
          <TerminalChip variant={summary.confidenceVariant}>{summary.confidenceLabel}</TerminalChip>
          <TerminalChip variant={summary.biasVariant}>{summary.actionFrame}</TerminalChip>
        </div>
      </div>
    </div>
    <div className="mt-4 grid min-w-0 grid-cols-1 gap-3 xl:grid-cols-3">
      {[
        { key: 'supporting', title: summary.supportingTitle, items: summary.supportingDrivers, tone: 'text-emerald-200' },
        { key: 'blocking', title: summary.blockingTitle, items: summary.blockingDrivers, tone: 'text-amber-200' },
        { key: 'watch', title: summary.watchTitle, items: summary.watchItems, tone: 'text-cyan-100' },
      ].map((block) => (
        <div key={block.key} className="min-w-0 rounded-lg border border-white/[0.06] bg-black/10 px-3 py-3">
          <p className="text-[11px] font-medium text-white/48">{block.title}</p>
          <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
            {block.items.map((item) => (
              <span key={item} className={cn('max-w-full truncate rounded-md border border-white/[0.06] bg-white/[0.025] px-2 py-1 text-[11px] font-semibold', block.tone)}>
                {item}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  </section>
);

const CrossAssetHeroRibbon: React.FC<{ anchors: MarketOverviewHeroAnchorView[] }> = ({ anchors }) => (
  <KeyLevelStrip
    data-testid="market-overview-hero-ribbon"
    className="rounded-none border-x-0"
    levels={anchors.map((anchor) => ({
      key: anchor.key,
      testId: `market-overview-hero-${anchor.key}`,
      label: anchor.secondaryLabel ? `${anchor.primaryLabel} (${anchor.secondaryLabel})` : anchor.primaryLabel,
      value: (
        <span className="flex min-w-0 flex-col">
          <span className="truncate font-mono text-[22px] font-semibold leading-none text-white md:text-2xl">
            {anchor.valueText}
          </span>
          <span className={cn('mt-1 truncate font-mono text-xs font-semibold', anchor.changeToneClass)}>
            {anchor.changeText}
          </span>
        </span>
      ),
      valueClassName: 'text-left text-inherit',
      className: 'py-2.5',
    }))}
  />
);

const MarketDecisionSemanticsList: React.FC<{
  testId: string;
  label: string;
  emptyLabel: string;
  items: MarketOverviewDecisionSemanticsLineView[];
}> = ({ testId, label, emptyLabel, items }) => (
  <div className="min-w-0">
    <p className="text-[11px] font-medium text-white/48">{label}</p>
    <div
      data-testid={testId}
      className="mt-2 flex max-h-32 min-w-0 flex-col gap-1.5 overflow-y-auto pr-1 text-[11px] leading-5 text-white/58 ui-scroll-y-quiet"
    >
      {items.length ? items.map((item) => (
        <p key={item.key} className="min-w-0">
          <span className="font-semibold text-white/72">{item.label}</span>
          {item.meta ? <span className="text-white/42"> · {item.meta}</span> : null}
        </p>
      )) : <p className="text-white/34">{emptyLabel}</p>}
    </div>
  </div>
);

function directionUsabilitySummary(view: MarketOverviewDecisionSemanticsView): {
  label: string;
  variant: 'success' | 'info' | 'caution';
  headline: string;
  detail: string;
} {
  const readiness = view.directionReadiness;
  const reasonText = joinMarketReasonLabels(
    [...view.capReasons, ...(readiness?.blockingReasons || [])],
    'zh',
    3,
    '数据边界仍待确认',
  );

  if (readiness?.status === 'direction_ready' && !view.insufficient) {
    return {
      label: '可参考',
      variant: 'success',
      headline: '当前方向判断可参考',
      detail: `主要依据已满足方向门槛，仍需继续核对反证与缺失证据。`,
    };
  }

  if (readiness?.status === 'partial_context_only') {
    return {
      label: '部分可参考',
      variant: 'info',
      headline: '当前方向仅可部分参考',
      detail: `主要因为${reasonText}。`,
    };
  }

  return {
    label: '方向不可用',
    variant: 'caution',
    headline: '当前不能形成可靠方向判断',
    detail: `主要因为${reasonText}。`,
  };
}

function uniqueReadinessItems(items: Array<string | null | undefined>, limit: number, fallback: string): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  items.forEach((item) => {
    const value = String(item || '').trim();
    if (!value || seen.has(value)) return;
    seen.add(value);
    result.push(value);
  });
  return result.length ? result.slice(0, limit) : [fallback];
}

function overviewReadinessState(params: {
  view?: MarketOverviewDecisionSemanticsView;
  decisionReliable: boolean;
  dataState: MarketOverviewDataStateStripView;
}): DecisionReadinessState {
  const { view, decisionReliable, dataState } = params;
  const readiness = view?.directionReadiness;
  const scoreGradeCount = readiness?.scoreGradeCount ?? (decisionReliable ? 3 : 0);
  const observationOnlyCount = readiness?.observationOnlyCount ?? 0;
  const missingCount = readiness?.missingCount ?? 0;

  if (dataState.isRefreshing && dataState.availableCount === 0) {
    return 'waiting';
  }
  if (
    readiness?.status === 'direction_ready'
    && decisionReliable
    && !view?.insufficient
    && scoreGradeCount >= 3
  ) {
    return 'ready';
  }
  if (
    readiness?.status === 'data_insufficient'
    && scoreGradeCount <= 0
    && (missingCount > 0 || dataState.hasFallback || dataState.hasUnavailable)
  ) {
    return 'unavailable';
  }
  if (
    readiness?.status === 'partial_context_only'
    || scoreGradeCount > 0
    || observationOnlyCount > 0
    || dataState.availableCount > 0
  ) {
    return 'observe';
  }
  return 'unavailable';
}

function buildOverviewDecisionReadiness(params: {
  view?: MarketOverviewDecisionSemanticsView;
  decisionReliable: boolean;
  dataState: MarketOverviewDataStateStripView;
  decisionText: string;
}): DecisionReadinessSummary {
  const { view, decisionReliable, dataState, decisionText } = params;
  const readiness = view?.directionReadiness;
  const state = overviewReadinessState({ view, decisionReliable, dataState });
  const scoreGradeCount = readiness?.scoreGradeCount ?? (decisionReliable ? 3 : 0);
  const observationOnlyCount = readiness?.observationOnlyCount ?? 0;
  const missingCount = readiness?.missingCount ?? 0;
  const rawBlockers = [
    ...(view?.capReasons || []).map((reason) => marketIntelligenceReasonLabel(reason)),
    ...(readiness?.blockingReasons || []).map((reason) => marketIntelligenceReasonLabel(reason)),
    ...(readiness?.missingPillars || []).map((pillar) => pillar.label),
    ...(view?.dataGaps || []).map((gap) => gap.label),
    dataState.hasFallback ? '存在 fallback / proxy 负担' : '',
    dataState.staleCount > 0 ? '存在过期数据' : '',
    dataState.hasUnavailable ? '存在不可用来源' : '',
  ];
  const nextEvidence = [
    ...(readiness?.missingPillars || []).map((pillar) => pillar.label),
    ...(view?.dataGaps || []).map((gap) => gap.label),
    ...(view?.invalidationTriggers || []).map((item) => item.label),
    state === 'ready' ? '继续确认反证是否进入评分级' : '',
  ];

  return {
    state,
    stateLabel: decisionReadinessStateLabel(state),
    stateVariant: decisionReadinessVariant(state),
    qualityLabel: `评分级 ${scoreGradeCount} · 观察 ${observationOnlyCount} · 缺失 ${missingCount}`,
    blockers: uniqueReadinessItems(rawBlockers, 4, state === 'ready' ? '暂无关键阻塞' : '关键证据仍待补齐'),
    nextEvidence: uniqueReadinessItems(nextEvidence, 3, '补齐评分级来源覆盖'),
    conclusion: state === 'ready'
      ? decisionText
      : MARKET_DECISION_NOT_READY_NOTICE,
  };
}

const DecisionReadinessBand: React.FC<{
  testId: string;
  summary: DecisionReadinessSummary;
}> = ({ testId, summary }) => (
  <section
    data-testid={testId}
    className="min-w-0 border-b border-[color:var(--wolfy-divider)] bg-white/[0.014] px-3 py-3 md:px-4"
  >
    <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
      <div className="min-w-0">
        <p className="text-[11px] font-semibold text-white/45">判断可用性</p>
        <h2 className="mt-1 text-base font-semibold leading-6 text-white/92 md:text-lg">
          {summary.stateLabel}
        </h2>
        <p className="mt-2 max-w-4xl text-sm leading-6 text-white/58">{summary.conclusion}</p>
      </div>
      <div className="flex min-w-0 flex-wrap gap-2 lg:justify-end">
        <TerminalChip variant={summary.stateVariant}>{summary.stateLabel}</TerminalChip>
        <TerminalChip variant="neutral">{summary.qualityLabel}</TerminalChip>
      </div>
    </div>
    <div className="mt-4 grid min-w-0 grid-cols-1 gap-3 xl:grid-cols-2">
      <div className="min-w-0 rounded-lg border border-white/[0.06] bg-black/10 px-3 py-3">
        <p className="text-[11px] font-medium text-white/48">阻塞项</p>
        <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
          {summary.blockers.map((item) => (
            <TerminalChip key={item} variant={summary.state === 'ready' ? 'neutral' : 'caution'}>{item}</TerminalChip>
          ))}
        </div>
      </div>
      <div className="min-w-0 rounded-lg border border-white/[0.06] bg-black/10 px-3 py-3">
        <p className="text-[11px] font-medium text-white/48">下一项证据</p>
        <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
          {summary.nextEvidence.map((item) => (
            <TerminalChip key={item} variant="info">{item}</TerminalChip>
          ))}
        </div>
      </div>
    </div>
    {summary.state !== 'ready' ? (
      <ProductSetupPath surface="market_overview" testId="market-overview-setup-path" />
    ) : null}
  </section>
);

const MarketDecisionSemanticsStrip: React.FC<{
  directionalSummary: MarketDirectionalSummary;
  view?: MarketOverviewDecisionSemanticsView;
  decisionText: string;
  decisionChips: MarketOverviewDecisionChipView[];
  decisionReliable: boolean;
  dataState: MarketOverviewDataStateStripView;
  regimeSynthesis: MarketRegimeSynthesisHeaderView;
  temperatureSummary: MarketOverviewTemperatureSummaryView;
  briefingSummary: MarketOverviewBriefingSummaryView;
  officialMacroRecords: OfficialMacroAuthorityRecord[];
}> = ({
  directionalSummary,
  view,
  decisionText,
  decisionChips,
  decisionReliable,
  dataState,
  regimeSynthesis,
  temperatureSummary,
  briefingSummary,
  officialMacroRecords,
}) => {
  const supportingEvidence = view ? [
    ...view.styleTilts.slice(0, 1),
    ...view.confirmationSignals,
  ].slice(0, 3) : [];
  const counterEvidence = view?.counterEvidence.slice(0, 3) || [];
  const missingEvidence = view?.dataGaps.slice(0, 5) || [];
  const watchNext = view ? (view.invalidationTriggers.length ? view.invalidationTriggers : view.dataGaps).slice(0, 3) : [];
  const statusSummary = view
    ? directionUsabilitySummary(view)
    : {
      label: decisionReliable ? '可参考' : '方向不可用',
      variant: decisionReliable ? 'success' as const : 'caution' as const,
      headline: decisionReliable ? decisionText : '当前暂不形成方向结论',
      detail: decisionReliable ? '等待更多支持与反证继续确认。' : '关键支持与反证尚未整理完成，先保持观察。',
    };
  const confidenceSummary = view?.confidenceValueText
    ? `${view.confidenceLabel}（${view.confidenceValueText}）`
    : (view?.confidenceLabel || temperatureSummary.confidenceLabel);
  const rawDebugCodes = [
    ...(view?.capReasons || []),
    ...(view?.directionReadiness?.blockingReasons || []),
    ...((view?.claimBoundaries || []).map((boundary) => boundary.reasonCode || '').filter(Boolean)),
  ];
  const visibleDecisionChips = decisionChips.slice(0, 2);
  const summarySentence = decisionReliable
    ? decisionText
    : `${statusSummary.detail} ${decisionText}`.trim();
  const readinessSummary = buildOverviewDecisionReadiness({
    view,
    decisionReliable,
    dataState,
    decisionText,
  });
  const snapshotLabel = dataState.updatedAtLabel
    ? `更新 ${dataState.updatedAtLabel}`
    : (dataState.isRefreshing ? '刷新中' : '待刷新');
  const trustBuckets: Array<TrustDisclosureBucket | null> = [
    (!decisionReliable || view?.insufficient || statusSummary.variant === 'caution') ? 'confidence' : null,
    dataState.hasFallback ? 'fallback' : null,
    dataState.staleCount > 0 ? 'stale' : null,
    (view?.directionReadiness?.observationOnlyCount ?? 0) > 0 ? 'observe-only' : null,
    view?.insufficient || dataState.hasUnavailable || (view?.directionReadiness?.missingCount ?? 0) > 0 ? 'insufficient' : null,
    view?.notInvestmentAdvice ? 'non-advice' : null,
  ];

  return (
    <section
      data-testid="market-decision-semantics-strip"
      data-market-research-flow="decision-semantics"
      className={cn(
        'relative overflow-hidden border-t border-[color:var(--wolfy-divider)] bg-white/[0.018] px-3 py-3 md:px-4',
        view?.insufficient ? 'opacity-85' : '',
      )}
    >
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-cyan-400/0 via-cyan-200/45 to-sky-400/0" aria-hidden="true" />
      <div className="min-w-0">
        <DecisionReadinessBand
          testId="market-overview-decision-readiness"
          summary={readinessSummary}
        />
        <MarketOverviewDirectionSummary summary={directionalSummary} />
        <div className="flex min-w-0 flex-col gap-3 border-b border-[color:var(--wolfy-divider)] pb-4">
          <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[10px] font-medium tracking-[0.24em] text-white/38">市场判断摘要</p>
              <p
                data-testid="market-decision-semantics-advice-boundary"
                className="mt-2 text-base font-semibold leading-6 text-white/90 md:text-lg"
              >
                {statusSummary.headline}
              </p>
              <p className="mt-2 max-w-4xl text-sm leading-6 text-white/58">{summarySentence}</p>
            </div>
            <div data-testid="market-command-chips" className="flex min-w-0 flex-wrap justify-end gap-2">
              <TerminalChip
                data-testid="market-decision-semantics-posture-chip"
                variant={statusSummary.variant}
                className="px-2.5 py-1 text-[10px]"
              >
                {statusSummary.label}
              </TerminalChip>
              <TerminalChip variant="neutral" className="px-2.5 py-1 text-[10px]">
                置信度
                <span className="tracking-normal">{confidenceSummary}</span>
              </TerminalChip>
              <TerminalChip variant={dataState.hasUnavailable || dataState.hasFallback ? 'caution' : 'neutral'} className="px-2.5 py-1 text-[10px]">
                证据快照
                <span className="tracking-normal">{snapshotLabel}</span>
              </TerminalChip>
              {visibleDecisionChips.map((chip) => (
                <TerminalChip
                  key={`${chip.label}-${chip.value}`}
                  variant={chip.variant}
                  className="px-2.5 py-1 text-[10px]"
                >
                  <span className="text-white/36">{chip.label}</span>
                  <span className="tracking-normal">{chip.value}</span>
                </TerminalChip>
              ))}
              <TrustDisclosureChips
                buckets={trustBuckets}
                chipClassName="px-2.5 py-1 text-[10px]"
              />
            </div>
          </div>

          <div className="flex min-w-0 flex-wrap gap-2">
            <TerminalChip variant={view?.directionReadiness?.scoreGradeCount ? 'success' : 'neutral'}>
              可计分证据 {view?.directionReadiness?.scoreGradeCount ?? 0}
            </TerminalChip>
            <TerminalChip variant={view?.directionReadiness?.observationOnlyCount ? 'info' : 'neutral'}>
              观察证据 {view?.directionReadiness?.observationOnlyCount ?? 0}
            </TerminalChip>
            <TerminalChip variant={view?.directionReadiness?.missingCount ? 'caution' : 'neutral'}>
              缺失证据 {view?.directionReadiness?.missingCount ?? 0}
            </TerminalChip>
            <TerminalChip variant="neutral">观察重心 {view?.exposureBiasLabel || '待补齐'}</TerminalChip>
          </div>
        </div>

        <div className="mt-4 grid min-w-0 grid-cols-1 gap-3 xl:grid-cols-3">
          <MarketDecisionSemanticsList
            testId="market-decision-semantics-supporting-evidence"
            label="支持证据"
            emptyLabel="等待评分级支持证据"
            items={supportingEvidence}
          />
          <MarketDecisionSemanticsList
            testId="market-decision-semantics-counter-evidence"
            label="反证 / 风险"
            emptyLabel="暂无反证"
            items={counterEvidence}
          />
          <MarketDecisionSemanticsList
            testId="market-decision-semantics-data-gaps"
            label="缺失证据"
            emptyLabel="暂无显式缺口"
            items={missingEvidence}
          />
        </div>

        <div className="mt-4 rounded-lg border border-white/[0.06] bg-black/10 px-3 py-3">
          <p className="text-[11px] font-medium text-white/48">下一步观察</p>
          <div
            data-testid="market-decision-semantics-watch-next"
            className="mt-2 flex min-w-0 flex-wrap gap-1.5 text-[11px] leading-5 text-white/60"
          >
            {watchNext.length ? watchNext.map((item) => (
              <span key={item.key} className="rounded-md border border-white/[0.06] bg-white/[0.025] px-2 py-1">
                <span className="font-semibold text-white/78">{item.label}</span>
                {item.meta ? <span className="text-white/42"> · {item.meta}</span> : null}
              </span>
            )) : <span className="text-white/34">等待下一项可验证信号</span>}
          </div>
        </div>

        <p className="mt-3 text-[11px] leading-5 text-white/42">
          仅供研究观察，非投资建议。{view?.insufficient ? ' 当前可靠证据不足，暂不形成方向结论。' : ''}
        </p>
        <TerminalDisclosure
          data-testid="market-decision-debug-details"
          title="技术细节 / Details"
          summary="方向 readiness、来源覆盖、运行快照与原始 reason code 默认折叠"
          className="mt-3 bg-black/10"
        >
          <Suspense fallback={<MarketDecisionDebugLoadingFallback />}>
            <LazyMarketOverviewDecisionDebugDetails
              regimeSynthesis={regimeSynthesis}
              temperatureSummary={temperatureSummary}
              briefingSummary={briefingSummary}
              dataState={dataState}
              officialMacroRecords={officialMacroRecords}
              directionReadiness={view?.directionReadiness}
              claimBoundaries={view?.claimBoundaries || []}
              rawDebugCodes={rawDebugCodes}
            />
          </Suspense>
        </TerminalDisclosure>
      </div>
    </section>
  );
};

const MarketDecisionDebugLoadingFallback: React.FC = () => (
  <div
    data-testid="market-decision-debug-loading"
    role="status"
    aria-live="polite"
    aria-busy="true"
    className="rounded-lg border border-white/[0.06] bg-black/10 px-3 py-3"
  >
    <p className="text-[11px] font-semibold text-white/72">正在加载技术细节</p>
    <p className="mt-1 text-[11px] leading-5 text-white/42">
      保留当前方向摘要，补充 readiness、来源覆盖与 reason code。
    </p>
  </div>
);

const MarketOverviewCategoryControls: React.FC<{
  categoryTabs: MarketOverviewCategoryTabView[];
  activeCategory: MarketOverviewTab;
  onCategoryChange: (tab: MarketOverviewTab) => void;
  exportLabel: string;
  onExportSummary: () => void;
}> = ({ categoryTabs, activeCategory, onCategoryChange, exportLabel, onExportSummary }) => (
  <div data-market-research-flow="controls">
    <div
      data-testid="market-overview-category-tabs"
      data-selector-position="static-safe"
      data-mobile-order="controls"
      className="flex w-full min-w-0 flex-col gap-2 rounded-xl border border-white/8 bg-white/[0.02] p-2 backdrop-blur-md md:flex-row md:items-center md:justify-between"
    >
      <div className="flex min-w-0 items-center gap-2">
        <span className="shrink-0 rounded-md border border-white/[0.06] bg-white/[0.025] px-2 py-1 text-[10px] font-semibold text-white/42">
          筛选
        </span>
        <div className="ui-scroll-x-quiet min-w-0">
          <div className="flex w-max gap-2">
            {categoryTabs.map((tab) => (
              <button
                key={tab.key}
                type="button"
                aria-pressed={activeCategory === tab.key}
                className={`ui-truncate shrink-0 whitespace-nowrap rounded-md px-3 py-2 text-xs font-semibold transition ${
                  activeCategory === tab.key
                    ? 'bg-white/10 text-white shadow-sm'
                    : 'bg-transparent text-white/45 hover:text-white/75'
                }`}
                onClick={() => onCategoryChange(tab.key)}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>
      <button
        type="button"
        data-testid="market-overview-export-summary"
        className="w-fit rounded-md border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-xs font-semibold text-white/62 transition hover:bg-white/[0.06] hover:text-white"
        onClick={onExportSummary}
      >
        {exportLabel}
      </button>
    </div>
  </div>
);

export const MarketOverviewWorkbenchTopSurface: React.FC<MarketOverviewWorkbenchTopSurfaceProps> = ({
  heading,
  directionalSummary,
  regimeSynthesis,
  decisionText,
  decisionChips,
  decisionReliable,
  decisionSemantics,
  dataState,
  temperatureSummary,
  briefingSummary,
  officialMacroRecords,
  categoryTabs,
  activeCategory,
  onCategoryChange,
  exportLabel,
  onExportSummary,
  heroAnchors,
}) => {
  return (
    <section data-testid="market-overview-pulse-header" className="flex w-full min-w-0 flex-col gap-4">
      {heading}
      <section data-testid="market-overview-market-monitor" className="flex w-full min-w-0 flex-col gap-4">
        <ConsoleBoard data-testid="market-overview-primary-board">
          <div data-testid="market-overview-top-stack" className="flex w-full min-w-0 flex-col">
            <MarketDecisionSemanticsStrip
              directionalSummary={directionalSummary}
              view={decisionSemantics}
              decisionText={decisionText}
              decisionChips={decisionChips}
              decisionReliable={decisionReliable}
              dataState={dataState}
              regimeSynthesis={regimeSynthesis}
              temperatureSummary={temperatureSummary}
              briefingSummary={briefingSummary}
              officialMacroRecords={officialMacroRecords}
            />
            <div className="border-t border-[color:var(--wolfy-divider)] px-3 py-3 md:px-4">
              <MarketOverviewCategoryControls
                categoryTabs={categoryTabs}
                activeCategory={activeCategory}
                onCategoryChange={onCategoryChange}
                exportLabel={exportLabel}
                onExportSummary={onExportSummary}
              />
            </div>
            <div data-market-research-flow="pulse" className="border-t border-[color:var(--wolfy-divider)]">
              <CrossAssetHeroRibbon anchors={heroAnchors} />
            </div>
          </div>
        </ConsoleBoard>
      </section>
    </section>
  );
};
