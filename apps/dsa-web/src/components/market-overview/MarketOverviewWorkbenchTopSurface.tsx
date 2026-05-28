import type React from 'react';
import { Suspense, lazy } from 'react';
import type { MarketOverviewTab } from '../../pages/MarketOverviewTabConfig';
import {
  ConsoleBoard,
  KeyLevelStrip,
} from '../linear';
import { TerminalChip, TerminalDisclosure, TerminalNotice } from '../terminal';
import { cn } from '../../utils/cn';
import type { MarketRegimeSynthesisHeaderView } from './MarketRegimeSynthesisHeader';
import type { OfficialMacroAuthorityRecord } from '../common/officialMacroAuthorityDiagnosticsData';
import { buildDataSourcesSetupHref, buildProviderOpsSetupHref } from '../../utils/productSetupSurface';
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
  showAdminDiagnostics?: boolean;
};

type DirectionUsabilitySummary = {
  label: string;
  variant: 'success' | 'info' | 'caution';
  headline: string;
  detail: string;
};

type ConsumerDataQualityNoticeView = {
  message: string;
  variant: 'neutral' | 'info' | 'caution';
};

const MARKET_OVERVIEW_SETUP_ACTION_CLASS = 'inline-flex min-h-8 items-center rounded-md border border-white/[0.08] bg-white/[0.035] px-2.5 py-1 text-[11px] font-semibold text-white/72 transition-colors hover:border-cyan-200/25 hover:bg-white/[0.06] hover:text-white';

const MarketOverviewSetupPath: React.FC<{ testId: string }> = ({ testId }) => (
  <div
    data-testid={testId}
    className="mt-3 rounded-lg border border-cyan-200/12 bg-cyan-300/[0.035] p-3"
  >
    <div className="flex min-w-0 flex-col gap-3 md:flex-row md:items-start md:justify-between">
      <div className="min-w-0">
        <p className="text-[11px] font-semibold text-cyan-100/82">查看需配置的数据源</p>
        <p className="mt-1 max-w-3xl text-[11px] leading-5 text-white/52">
          补齐官方或授权来源、减少备用或代理证据；是否进入评分仍由现有来源门槛决定。
        </p>
      </div>
      <div className="flex shrink-0 flex-wrap gap-2">
        <a className={MARKET_OVERVIEW_SETUP_ACTION_CLASS} href={buildProviderOpsSetupHref('market_overview')}>
          查看提供方运维
        </a>
        <a className={MARKET_OVERVIEW_SETUP_ACTION_CLASS} href={buildDataSourcesSetupHref('market_overview')}>
          前往数据源设置
        </a>
      </div>
    </div>
  </div>
);

const MarketOverviewDirectionSummary: React.FC<{ summary: MarketDirectionalSummary }> = ({ summary }) => (
  <section
    data-testid="market-overview-direction-summary"
    className="relative overflow-hidden border-t border-[color:var(--wolfy-divider)] bg-white/[0.022] p-3 md:px-4"
  >
    <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-cyan-400/0 via-cyan-200/38 to-sky-400/0" aria-hidden="true" />
    <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
      <div className="min-w-0">
        <p className="text-[10px] font-medium tracking-[0.24em] text-white/38">
          {summary.currentLabel.startsWith('当前') ? '市场方向摘要' : summary.title}
        </p>
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
        <div key={block.key} className="min-w-0 rounded-lg border border-white/[0.06] bg-black/10 p-3">
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
      className="mt-2 flex max-h-32 min-w-0 flex-col gap-1.5 overflow-y-auto no-scrollbar pr-1 text-[11px] leading-5 text-white/58 ui-scroll-y-quiet"
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

function directionUsabilitySummary(view: MarketOverviewDecisionSemanticsView): DirectionUsabilitySummary {
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
  ) {
    if (dataState.availableCount > 0 && !dataState.hasUnavailable) {
      return 'observe';
    }
    if (missingCount > 0 || dataState.hasFallback || dataState.hasUnavailable) {
      return 'unavailable';
    }
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
    dataState.hasFallback ? '存在备用或代理证据负担' : '',
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

function conclusionCanJudgeDetail(summary: DecisionReadinessSummary): string {
  switch (summary.state) {
    case 'ready':
      return '当前方向判断可参考，仍需继续观察后续更新。';
    case 'observe':
      return '当前信号置信度较低，仅供观察。';
    case 'waiting':
      return '数据更新中，稍后将自动刷新。';
    case 'unavailable':
    default:
      return '部分数据暂不可用，当前评分已暂停。';
  }
}

function conclusionDirectionValue(summary: DecisionReadinessSummary, statusSummary: DirectionUsabilitySummary): string {
  if (summary.state === 'ready') {
    return statusSummary.headline;
  }
  if (summary.state === 'waiting') {
    return '等待数据完成后再判断';
  }
  return '暂不形成方向结论';
}

function buildConsumerDataQualityNotice(summary: DecisionReadinessSummary, dataState: MarketOverviewDataStateStripView): ConsumerDataQualityNoticeView | null {
  if (summary.state === 'unavailable') {
    return {
      message: '部分数据暂不可用，当前评分已暂停。',
      variant: 'caution',
    };
  }
  if (summary.state === 'waiting' || (dataState.isRefreshing && dataState.availableCount === 0)) {
    return {
      message: '数据更新中，稍后将自动刷新。',
      variant: 'info',
    };
  }
  if (summary.state === 'observe') {
    return {
      message: '当前信号置信度较低，仅供观察。',
      variant: 'info',
    };
  }
  if (dataState.staleCount > 0 || dataState.hasFallback) {
    return {
      message: '已使用最近一次可用数据。',
      variant: 'neutral',
    };
  }
  return null;
}

function confidenceStatusLabel(summary: DecisionReadinessSummary): string {
  switch (summary.state) {
    case 'ready':
      return '当前信号可参考';
    case 'waiting':
      return '更新中';
    case 'observe':
      return '仅供观察';
    case 'unavailable':
    default:
      return '评分暂停';
  }
}

function dataStatusLabel(summary: DecisionReadinessSummary, dataState: MarketOverviewDataStateStripView): string {
  if (summary.state === 'waiting' || dataState.isRefreshing) {
    return '更新中';
  }
  if (summary.state === 'unavailable') {
    return '部分不可用';
  }
  if (dataState.hasUnavailable) {
    return '部分可用';
  }
  if (dataState.staleCount > 0 || dataState.hasFallback) {
    return '最近一次可用数据';
  }
  return '数据可用';
}

const MarketOverviewConclusionLayer: React.FC<{
  testId: string;
  summary: DecisionReadinessSummary;
  statusSummary: DirectionUsabilitySummary;
  dataState: MarketOverviewDataStateStripView;
  directionalSummary: MarketDirectionalSummary;
}> = ({ testId, summary, statusSummary, dataState, directionalSummary }) => {
  const notice = buildConsumerDataQualityNotice(summary, dataState);
  const updatedAtText = dataState.updatedAtLabel || '待刷新';
  const summaryFacts = [
    {
      key: 'state',
      label: '市场状态',
      value: summary.stateLabel,
      detail: conclusionCanJudgeDetail(summary),
    },
    {
      key: 'driver',
      label: '主驱动',
      value: directionalSummary.supportingDrivers[0] || directionalSummary.regimePhrase,
      detail: directionalSummary.supportingTitle,
    },
    {
      key: 'coverage',
      label: '数据覆盖',
      value: dataStatusLabel(summary, dataState),
      detail: `最近更新：${updatedAtText}`,
    },
  ];

  return (
    <section
      data-testid={testId}
      data-market-research-flow="conclusion"
      className="min-w-0 border-b border-[color:var(--wolfy-divider)] bg-white/[0.018] p-3 md:px-4"
    >
      <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-white/38">市场状态</p>
          <h2
            data-testid="market-decision-semantics-advice-boundary"
            className="mt-2 text-xl font-semibold leading-7 text-white/92 md:text-[28px]"
          >
            {conclusionDirectionValue(summary, statusSummary)}
          </h2>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-white/58">
            {summary.conclusion}
          </p>
          <p className="mt-2 max-w-3xl text-[11px] leading-5 text-white/42">
            {statusSummary.detail}
          </p>
        </div>
        <div data-testid="market-command-chips" className="flex min-w-0 flex-wrap gap-2 lg:justify-end">
          <TerminalChip variant={summary.stateVariant}>{summary.stateLabel}</TerminalChip>
          <TerminalChip variant="neutral">{confidenceStatusLabel(summary)}</TerminalChip>
          <TerminalChip variant="neutral">{dataStatusLabel(summary, dataState)}</TerminalChip>
        </div>
      </div>
      {notice ? (
        <TerminalNotice
          variant={notice.variant}
          data-testid="market-overview-consumer-data-quality-notice"
          className="mt-4"
        >
          {notice.message}
        </TerminalNotice>
      ) : null}
      <div
        data-testid="market-overview-summary-strip"
        className="mt-4 grid min-w-0 grid-cols-1 gap-2 xl:grid-cols-3"
      >
        {summaryFacts.map((fact) => (
          <div key={fact.key} className="min-w-0 rounded-lg border border-white/[0.06] bg-black/10 px-3 py-2.5">
            <p className="text-[11px] font-medium text-white/48">{fact.label}</p>
            <p className="mt-1 text-sm font-semibold text-white/88">{fact.value}</p>
            <p className="mt-1 text-[11px] leading-5 text-white/50">{fact.detail}</p>
          </div>
        ))}
      </div>
    </section>
  );
};

const MarketOverviewDataNotesDisclosure: React.FC<{
  directionalSummary: MarketDirectionalSummary;
  decisionChips: MarketOverviewDecisionChipView[];
  supportingEvidence: MarketOverviewDecisionSemanticsLineView[];
  counterEvidence: MarketOverviewDecisionSemanticsLineView[];
  missingEvidence: MarketOverviewDecisionSemanticsLineView[];
  watchNext: MarketOverviewDecisionSemanticsLineView[];
}> = ({
  directionalSummary,
  decisionChips,
  supportingEvidence,
  counterEvidence,
  missingEvidence,
  watchNext,
}) => (
  <TerminalDisclosure
    data-testid="market-overview-evidence-disclosure"
    title="数据说明"
    summary="更新时效、证据、风险与下一步观察默认折叠"
    className="mt-3 bg-black/10"
  >
    <MarketOverviewDirectionSummary summary={directionalSummary} />
    {decisionChips.length ? (
      <div data-testid="market-overview-decision-chip-details" className="mt-3 flex min-w-0 flex-wrap gap-2">
        {decisionChips.slice(0, 5).map((chip) => (
          <TerminalChip
            key={`${chip.label}-${chip.value}`}
            variant={chip.variant}
            className="px-2.5 py-1 text-[10px]"
          >
            <span className="text-white/36">{chip.label}</span>
            <span className="tracking-normal">{chip.value}</span>
          </TerminalChip>
        ))}
      </div>
    ) : null}
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

    <div className="mt-4 rounded-lg border border-white/[0.06] bg-black/10 p-3">
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
  </TerminalDisclosure>
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
  showAdminDiagnostics: boolean;
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
  showAdminDiagnostics,
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
  const rawDebugCodes = [
    ...(view?.capReasons || []),
    ...(view?.directionReadiness?.blockingReasons || []),
    ...((view?.claimBoundaries || []).flatMap((boundary) => { const v = boundary.reasonCode || ''; return v ? [v] : []; })),
  ];
  const readinessSummary = buildOverviewDecisionReadiness({
    view,
    decisionReliable,
    dataState,
    decisionText,
  });
  const summarySentence = readinessSummary.state === 'ready'
    ? decisionText
    : conclusionCanJudgeDetail(readinessSummary);

  return (
    <section
      data-testid="market-decision-semantics-strip"
      data-market-research-flow="decision-semantics"
      className={cn(
        'relative overflow-hidden border-t border-[color:var(--wolfy-divider)] bg-white/[0.018] p-3 md:px-4',
        view?.insufficient ? 'opacity-85' : '',
      )}
    >
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-cyan-400/0 via-cyan-200/45 to-sky-400/0" aria-hidden="true" />
      <div className="min-w-0">
        <MarketOverviewConclusionLayer
          testId="market-overview-decision-readiness"
          summary={readinessSummary}
          statusSummary={statusSummary}
          dataState={dataState}
          directionalSummary={directionalSummary}
        />
        <MarketOverviewDataNotesDisclosure
          directionalSummary={directionalSummary}
          decisionChips={decisionChips}
          supportingEvidence={supportingEvidence}
          counterEvidence={counterEvidence}
          missingEvidence={missingEvidence}
          watchNext={watchNext}
        />

        <p className="mt-3 text-[11px] leading-5 text-white/42">
          仅供研究观察，不构成交易指令。{summarySentence !== decisionText ? ` ${summarySentence}` : ''}
        </p>
        {showAdminDiagnostics ? (
          <TerminalDisclosure
            data-testid="market-decision-debug-details"
            title="技术细节"
            summary="管理员模式下可查看方向可用性、来源覆盖与原始原因代码"
            className="mt-3 bg-black/10"
          >
            {readinessSummary.state !== 'ready' ? (
              <MarketOverviewSetupPath testId="market-overview-setup-path" />
            ) : null}
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
        ) : null}
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
    className="rounded-lg border border-white/[0.06] bg-black/10 p-3"
  >
    <p className="text-[11px] font-semibold text-white/72">正在加载技术细节</p>
    <p className="mt-1 text-[11px] leading-5 text-white/42">
      保留当前方向摘要，补充可用性、来源覆盖与原因代码。
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
  showAdminDiagnostics = false,
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
              showAdminDiagnostics={showAdminDiagnostics}
            />
            <div className="border-t border-[color:var(--wolfy-divider)] p-3 md:px-4">
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
