import type React from 'react';
import type { MarketOverviewTab } from '../../pages/MarketOverviewTabConfig';
import {
  ConsoleBoard,
  KeyLevelStrip,
} from '../linear';
import { TerminalChip, TerminalDenseList, TerminalDisclosure, TerminalNotice, TerminalPanel, TerminalSectionHeader } from '../terminal';
import { cn } from '../../utils/cn';
import { MarketRegimeSynthesisHeader, type MarketRegimeSynthesisHeaderView } from './MarketRegimeSynthesisHeader';
import { OfficialMacroAuthorityDiagnostics } from '../common/OfficialMacroAuthorityDiagnostics';
import type { OfficialMacroAuthorityDiagnosticsView } from '../common/officialMacroAuthorityDiagnosticsData';
import { joinMarketReasonLabels, marketIntelligenceReasonLabel, marketIntelligenceReasonLabels, type MarketDirectionalSummary } from '../../utils/marketIntelligenceGuidance';

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
  officialMacroDiagnostics: OfficialMacroAuthorityDiagnosticsView;
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

const MarketDirectionReadinessStrip: React.FC<{
  view?: MarketOverviewDirectionReadinessView;
}> = ({ view }) => {
  if (!view) {
    return null;
  }

  const pillarSummary = [
    ...view.scoreGradePillars,
    ...view.observationOnlyPillars,
    ...view.missingPillars,
  ].slice(0, 3);

  return (
    <div
      data-testid="market-direction-readiness-strip"
      className="mt-3 min-w-0 rounded-md border border-white/[0.07] bg-black/10 px-3 py-2"
    >
      <div className="flex min-w-0 flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <TerminalChip
            variant={view.statusVariant}
            className="px-2.5 py-1 text-[10px] font-bold uppercase tracking-widest"
          >
            {view.statusLabel}
          </TerminalChip>
          <TerminalChip variant="neutral" className="px-2.5 py-1 text-[10px] font-bold uppercase tracking-widest">
            {view.confidenceLabel}
          </TerminalChip>
          <span className="font-mono text-[11px] text-white/55">
            评分级 {view.scoreGradeCount} · 观察级 {view.observationOnlyCount} · 缺口 {view.missingCount}
          </span>
        </div>
        {view.blockingReasons.length ? (
          <p
            data-testid="market-direction-readiness-reasons"
            className="min-w-0 break-words font-mono text-[10px] leading-4 text-amber-100/62 lg:max-w-[48%] lg:text-right"
          >
            {marketIntelligenceReasonLabels(view.blockingReasons, 'zh', 3).join(' · ')}
          </p>
        ) : null}
      </div>
      {pillarSummary.length ? (
        <div className="mt-2 flex min-w-0 flex-wrap gap-1.5 text-[10px] font-semibold text-white/48">
          {pillarSummary.map((pillar) => (
            <span
              key={pillar.key}
              className="max-w-full truncate rounded-md border border-white/[0.06] bg-white/[0.025] px-2 py-1"
            >
              {pillar.label}
              {pillar.reasonCode && pillar.reasonCode !== 'score_grade_evidence' ? ` · ${marketIntelligenceReasonLabel(pillar.reasonCode)}` : ''}
            </span>
          ))}
        </div>
      ) : null}
      {view.notInvestmentAdvice ? (
        <p className="mt-2 text-[10px] font-semibold text-white/34">非投资建议</p>
      ) : null}
    </div>
  );
};

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
  officialMacroDiagnostics: OfficialMacroAuthorityDiagnosticsView;
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
  officialMacroDiagnostics,
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
  const snapshotLabel = dataState.updatedAtLabel
    ? `更新 ${dataState.updatedAtLabel}`
    : (dataState.isRefreshing ? '刷新中' : '待刷新');

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
          <div className="grid gap-3">
            <div className="rounded-lg border border-white/[0.06] bg-black/10 p-3">
              <MarketRegimeSynthesisHeader view={regimeSynthesis} />
            </div>
            <MarketOverviewStatusStrip
              temperatureSummary={temperatureSummary}
              briefingSummary={briefingSummary}
            />
            <MarketOverviewDataStateStrip dataState={dataState} />
            <OfficialMacroAuthorityDiagnostics
              testId="market-overview-official-macro-diagnostics"
              title="来源覆盖诊断"
              view={officialMacroDiagnostics}
            />
            {view?.directionReadiness ? <MarketDirectionReadinessStrip view={view.directionReadiness} /> : null}
            <div
              data-testid="market-decision-semantics-claim-boundaries"
              className="flex min-w-0 flex-wrap gap-1.5"
            >
              {(view?.claimBoundaries || []).map((boundary) => (
                <span
                  key={boundary.key}
                  className={cn(
                    'rounded-md border px-2 py-1 text-[10px] font-semibold',
                    boundary.allowed
                      ? 'border-emerald-300/14 bg-emerald-300/[0.06] text-emerald-100/70'
                      : 'border-amber-300/14 bg-amber-300/[0.06] text-amber-100/70',
                  )}
                >
                  {boundary.label} · {boundary.allowed ? '允许' : '禁止'}
                  {boundary.reasonCode ? ` · ${marketIntelligenceReasonLabel(boundary.reasonCode)}` : ''}
                </span>
              ))}
            </div>
            <TerminalDenseList className="font-mono text-[10px] leading-4 text-white/46">
              {rawDebugCodes.length ? rawDebugCodes.map((code, index) => (
                <span key={`${code}-${index}`}>{code}</span>
              )) : <span>暂无原始代码</span>}
            </TerminalDenseList>
          </div>
        </TerminalDisclosure>
      </div>
    </section>
  );
};

const CompactStatusTile: React.FC<{
  testId: string;
  eyebrow: string;
  title: string;
  value: string;
  meta: React.ReactNode;
  tone?: string;
}> = ({ testId, eyebrow, title, value, meta, tone = 'text-white' }) => (
  <TerminalPanel
    as="section"
    dense
    data-testid={testId}
    className="min-w-0"
  >
    <TerminalSectionHeader
      eyebrow={eyebrow}
      title={title}
      action={<p className={cn('shrink-0 text-right font-mono text-lg font-semibold leading-none tabular-nums', tone)}>{value}</p>}
    />
    <div className="mt-2 min-w-0 text-xs leading-5 text-white/45">{meta}</div>
  </TerminalPanel>
);

const MarketTemperatureCompactSummary: React.FC<{ summary: MarketOverviewTemperatureSummaryView }> = ({ summary }) => (
  <CompactStatusTile
    testId="market-overview-temperature-summary"
    eyebrow="温度"
    title="市场温度"
    value={summary.valueText}
    tone={summary.toneClass}
    meta={(
      <div data-testid="market-temperature-strip" className="flex min-w-0 flex-wrap items-center gap-2">
        <span className="font-semibold text-white/68">{summary.label}</span>
        <span>信号可信：{summary.confidenceLabel}</span>
        <span className="font-mono tabular-nums">
          真实 {summary.reliableInputCount} · 备用 {summary.fallbackInputCount} · 排除 {summary.excludedInputCount}
        </span>
        {!summary.reliable ? (
          <span data-testid="market-temperature-unreliable-summary">
            {summary.label === '可靠输入不足' ? '可靠输入不足，暂不生成综合判断' : '暂不判定，暂不生成综合判断'}
          </span>
        ) : null}
      </div>
    )}
  />
);

const MarketBriefingCompactSummary: React.FC<{ summary: MarketOverviewBriefingSummaryView }> = ({ summary }) => (
  <CompactStatusTile
    testId="market-overview-briefing-summary"
    eyebrow="简报"
    title="今日市场解读"
    value={summary.confidenceLabel}
    tone={summary.toneClass}
    meta={(
      <div className="min-w-0">
        <p data-testid="market-briefing-card" className="truncate text-white/55">{summary.leadMessage}</p>
        {summary.warning ? <p data-testid="market-briefing-warning" className="truncate text-amber-200/70">{summary.warning}</p> : null}
      </div>
    )}
  />
);

const MarketOverviewStatusStrip: React.FC<{
  temperatureSummary: MarketOverviewTemperatureSummaryView;
  briefingSummary: MarketOverviewBriefingSummaryView;
}> = ({ temperatureSummary, briefingSummary }) => (
  <section
    data-testid="market-overview-status-strip"
    className="grid w-full grid-cols-1 gap-3 xl:grid-cols-[1fr_1.35fr]"
  >
    <MarketTemperatureCompactSummary summary={temperatureSummary} />
    <MarketBriefingCompactSummary summary={briefingSummary} />
  </section>
);

const MarketOverviewDataStateStrip: React.FC<{
  dataState: MarketOverviewDataStateStripView;
}> = ({ dataState }) => (
  <TerminalNotice
    variant={dataState.variant}
    data-testid="market-overview-cache-status"
    data-market-research-flow="cache"
    data-mobile-order="cache-status"
    className="min-w-0"
  >
    <div
      data-testid="market-overview-data-state-strip"
      className="flex min-w-0 flex-col gap-3 xl:flex-row xl:items-start xl:justify-between"
    >
      <div className="min-w-0 flex-1">
        <TerminalSectionHeader eyebrow="状态" title="数据状态" />
        <TerminalDenseList
          data-testid="market-overview-data-state-summary"
          className="mt-2 min-w-0 text-[11px] leading-4 text-white/45"
        >
          <span className="truncate font-mono">
            可用 {dataState.availableCount} · 备用 {dataState.fallbackCount} · 过期 {dataState.staleCount}
            {dataState.hasUnavailable ? ` · 缺口 ${dataState.unavailableCount}` : ''}
          </span>
        </TerminalDenseList>
      </div>
      <div className="flex min-w-0 flex-wrap items-center gap-2 xl:max-w-[60%] xl:justify-end">
        {dataState.isRefreshing || dataState.needsRefresh ? (
          <TerminalChip
            data-testid="market-overview-data-state-refresh-chip"
            variant={dataState.isRefreshing ? 'info' : 'caution'}
          >
            {dataState.isRefreshing ? '刷新中' : '待刷新'}
          </TerminalChip>
        ) : null}
        {dataState.hasFallback ? (
          <TerminalChip
            data-testid="market-overview-data-state-fallback-chip"
            variant="caution"
          >
            备用数据
          </TerminalChip>
        ) : null}
        {dataState.hasUnavailable ? (
          <TerminalChip
            data-testid="market-overview-data-state-unavailable-chip"
            variant="caution"
          >
            部分外部数据暂不可用
          </TerminalChip>
        ) : null}
        <TerminalChip
          data-testid="market-overview-data-state-updated-chip"
          variant={dataState.updatedAtLabel ? 'neutral' : 'info'}
        >
          {dataState.updatedAtLabel ? <>更新时间 <span className="font-mono">{dataState.updatedAtLabel}</span></> : '待刷新'}
        </TerminalChip>
      </div>
    </div>
  </TerminalNotice>
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
  officialMacroDiagnostics,
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
              officialMacroDiagnostics={officialMacroDiagnostics}
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
