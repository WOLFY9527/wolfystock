import type React from 'react';
import { MarketRegimeSynthesisHeader, type MarketRegimeSynthesisHeaderView } from './MarketRegimeSynthesisHeader';
import type {
  MarketOverviewBriefingSummaryView,
  MarketOverviewDataStateStripView,
  MarketOverviewDecisionSemanticsBoundaryView,
  MarketOverviewDirectionReadinessView,
  MarketOverviewTemperatureSummaryView,
} from './marketOverviewDecisionTypes';
import { OfficialMacroAuthorityDiagnostics } from '../common/OfficialMacroAuthorityDiagnostics';
import { buildOfficialMacroAuthorityDiagnosticsView, type OfficialMacroAuthorityRecord } from '../common/officialMacroAuthorityDiagnosticsData';
import { TerminalChip, TerminalDenseList, TerminalNotice, TerminalPanel, TerminalSectionHeader } from '../terminal/TerminalPrimitives';
import { cn } from '../../utils/cn';
import { TrustDisclosureChips } from '../evidence/TrustDisclosureChips';
import { marketIntelligenceReasonLabel, marketIntelligenceReasonLabels } from '../../utils/marketIntelligenceGuidance';

type MarketOverviewDecisionDebugDetailsProps = {
  regimeSynthesis?: MarketRegimeSynthesisHeaderView;
  temperatureSummary: MarketOverviewTemperatureSummaryView;
  briefingSummary: MarketOverviewBriefingSummaryView;
  dataState: MarketOverviewDataStateStripView;
  officialMacroRecords: OfficialMacroAuthorityRecord[];
  directionReadiness?: MarketOverviewDirectionReadinessView;
  claimBoundaries: MarketOverviewDecisionSemanticsBoundaryView[];
  rawDebugCodes: string[];
};

const CompactStatusTile: React.FC<{
  testId: string;
  eyebrow: string;
  title: string;
  value: string;
  meta: React.ReactNode;
  tone?: string;
}> = ({ testId, eyebrow, title, value, meta, tone = 'text-[color:var(--wolfy-text-primary)]' }) => (
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
    <div className="mt-2 min-w-0 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{meta}</div>
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
        <span className="font-semibold text-[color:var(--wolfy-text-muted)]">{summary.label}</span>
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
        <p data-testid="market-briefing-card" className="truncate text-[color:var(--wolfy-text-muted)]">{summary.leadMessage}</p>
        {summary.warning ? <p data-testid="market-briefing-warning" className="truncate text-[color:var(--state-warning-text)]/70">{summary.warning}</p> : null}
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
          className="mt-2 min-w-0 text-[11px] leading-4 text-[color:var(--wolfy-text-muted)]"
        >
          <span className="truncate font-mono">
            可用 {dataState.availableCount} · 备用数据 {dataState.fallbackCount} · 数据过期 {dataState.staleCount}
            {dataState.hasUnavailable ? ` · 证据不足 ${dataState.unavailableCount}` : ''}
          </span>
        </TerminalDenseList>
      </div>
      <div className="flex min-w-0 flex-wrap items-center gap-2 xl:max-w-[60%] xl:justify-end">
        <TrustDisclosureChips
          buckets={[
            dataState.hasFallback ? 'fallback' : null,
            dataState.staleCount > 0 ? 'stale' : null,
            dataState.hasUnavailable ? 'insufficient' : null,
          ]}
          chipClassName="text-[11px]"
        />
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
      className="mt-3 min-w-0 rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-input)] px-3 py-2"
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
          <span className="font-mono text-[11px] text-[color:var(--wolfy-text-muted)]">
            评分级 {view.scoreGradeCount} · 仅观察 {view.observationOnlyCount} · 证据不足 {view.missingCount}
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
        <div className="mt-2 flex min-w-0 flex-wrap gap-1.5 text-[10px] font-semibold text-[color:var(--wolfy-text-muted)]">
          {pillarSummary.map((pillar) => (
            <span
              key={pillar.key}
              className="max-w-full truncate rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-input)] px-2 py-1"
            >
              {pillar.label}
              {pillar.reasonCode && pillar.reasonCode !== 'score_grade_evidence' ? ` · ${marketIntelligenceReasonLabel(pillar.reasonCode)}` : ''}
            </span>
          ))}
        </div>
      ) : null}
      {view.notInvestmentAdvice ? (
        <p className="mt-2 text-[10px] font-semibold text-[color:var(--wolfy-text-muted)]">不构成交易指令</p>
      ) : null}
    </div>
  );
};

export const MarketOverviewDecisionDebugDetails: React.FC<MarketOverviewDecisionDebugDetailsProps> = ({
  regimeSynthesis,
  temperatureSummary,
  briefingSummary,
  dataState,
  officialMacroRecords,
  directionReadiness,
  claimBoundaries,
  rawDebugCodes,
}) => {
  const officialMacroDiagnostics = buildOfficialMacroAuthorityDiagnosticsView(officialMacroRecords);

  return (
    <div className="grid gap-3">
      {regimeSynthesis ? (
        <div className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-input)] p-3">
          <MarketRegimeSynthesisHeader view={regimeSynthesis} />
        </div>
      ) : null}
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
      <MarketDirectionReadinessStrip view={directionReadiness} />
      <div
        data-testid="market-decision-semantics-claim-boundaries"
        className="flex min-w-0 flex-wrap gap-1.5"
      >
        {claimBoundaries.map((boundary) => (
          <span
            key={boundary.key}
            className={cn(
              'rounded-md border px-2 py-1 text-[10px] font-semibold',
              boundary.allowed
                ? 'border-[color:var(--state-success-border)] bg-[var(--state-success-bg)] text-[color:var(--state-success-text)]/70'
                : 'border-amber-300/14 bg-amber-300/[0.06] text-amber-100/70',
            )}
          >
            {boundary.label} · {boundary.allowed ? '允许' : '禁止'}
            {boundary.reasonCode ? ` · ${marketIntelligenceReasonLabel(boundary.reasonCode)}` : ''}
          </span>
        ))}
      </div>
      <TerminalDenseList className="font-mono text-[10px] leading-4 text-[color:var(--wolfy-text-muted)]">
        {rawDebugCodes.length ? rawDebugCodes.map((code, index) => (
          <span key={`${code}-${index}`}>{code}</span>
        )) : <span>暂无原始代码</span>}
      </TerminalDenseList>
    </div>
  );
};
