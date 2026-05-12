import type React from 'react';
import type { MarketOverviewTab } from '../../pages/MarketOverviewTabConfig';
import { TerminalChip, TerminalDenseList, TerminalNotice, TerminalPanel, TerminalSectionHeader } from '../terminal';
import { cn } from '../../utils/cn';

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

type MarketOverviewWorkbenchTopSurfaceProps = {
  heading: React.ReactNode;
  decisionText: string;
  decisionChips: MarketOverviewDecisionChipView[];
  decisionReliable: boolean;
  dataState: MarketOverviewDataStateStripView;
  temperatureSummary: MarketOverviewTemperatureSummaryView;
  briefingSummary: MarketOverviewBriefingSummaryView;
  categoryTabs: MarketOverviewCategoryTabView[];
  activeCategory: MarketOverviewTab;
  onCategoryChange: (tab: MarketOverviewTab) => void;
  exportLabel: string;
  onExportSummary: () => void;
  heroAnchors: MarketOverviewHeroAnchorView[];
};

const CrossAssetHeroRibbon: React.FC<{ anchors: MarketOverviewHeroAnchorView[] }> = ({ anchors }) => (
  <TerminalPanel
    as="section"
    data-testid="market-overview-hero-ribbon"
    data-mobile-order="pulse"
    className="overflow-hidden p-0"
    aria-label="Cross asset hero ribbon"
  >
    <div className="grid grid-cols-[repeat(auto-fit,minmax(112px,1fr))] divide-x divide-y divide-white/5">
      {anchors.map((anchor) => (
        <div
          key={anchor.key}
          data-testid={`market-overview-hero-${anchor.key}`}
          className="min-w-0 bg-white/[0.02] px-4 py-3.5"
        >
          <p className="block truncate text-[10px] font-semibold uppercase tracking-widest text-white/50">
            {anchor.primaryLabel}
            {anchor.secondaryLabel ? <span className="ml-1 text-white/28">({anchor.secondaryLabel})</span> : null}
          </p>
          <p className="mt-1 truncate font-mono text-[22px] font-semibold leading-none text-white md:text-2xl">
            {anchor.valueText}
          </p>
          <p className={cn('mt-1 font-mono text-xs font-semibold', anchor.changeToneClass)}>
            {anchor.changeText}
          </p>
        </div>
      ))}
    </div>
  </TerminalPanel>
);

const MarketDecisionStrip: React.FC<{
  text: string;
  chips: MarketOverviewDecisionChipView[];
  reliable: boolean;
}> = ({ text, chips, reliable }) => (
  <TerminalPanel
    as="section"
    data-testid="market-decision-strip"
    data-command-bar="market-state"
    data-mobile-order="decision"
    data-market-research-flow="state"
    className="relative overflow-hidden p-0 shadow-[0_0_24px_rgba(59,130,246,0.10)]"
  >
    <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-blue-500/0 via-blue-400/45 to-purple-500/0" aria-hidden="true" />
    <div className="flex min-w-0 flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between">
      <div className="min-w-0">
        <p className="text-[10px] font-bold tracking-widest text-white/40">市场状态</p>
        <p data-testid="market-decision-text" className="mt-1 line-clamp-2 font-mono text-base font-semibold leading-6 text-white/88 md:truncate">
          {text}
        </p>
        {!reliable ? (
          <p data-testid="market-command-safe-state" className="mt-1 truncate text-[11px] font-semibold text-amber-200/78">
            当前不生成强判断，只显示可验证信号
          </p>
        ) : null}
      </div>
      <div data-testid="market-command-chips" className="ui-scroll-x-quiet -mx-1 flex min-w-0 max-w-full gap-2 px-1 md:mx-0 md:shrink-0 md:px-0">
        {chips.map((chip) => (
          <TerminalChip
            key={`${chip.label}-${chip.value}`}
            variant={chip.variant}
            className="shrink-0 px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-widest"
          >
            <span className="text-white/36">{chip.label}</span>
            <span className="max-w-[150px] truncate font-mono normal-case tracking-normal">{chip.value}</span>
          </TerminalChip>
        ))}
      </div>
    </div>
  </TerminalPanel>
);

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
        {!summary.reliable ? <span data-testid="market-temperature-unreliable-summary">真实输入不足，暂不生成综合判断</span> : null}
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
  decisionText,
  decisionChips,
  decisionReliable,
  dataState,
  temperatureSummary,
  briefingSummary,
  categoryTabs,
  activeCategory,
  onCategoryChange,
  exportLabel,
  onExportSummary,
  heroAnchors,
}) => (
  <section data-testid="market-overview-pulse-header" className="flex w-full min-w-0 flex-col gap-4">
    {heading}
    <div data-testid="market-overview-top-stack" className="flex w-full min-w-0 flex-col gap-4">
      <MarketDecisionStrip text={decisionText} chips={decisionChips} reliable={decisionReliable} />
      <MarketOverviewDataStateStrip dataState={dataState} />
      <section data-testid="market-overview-summary-band" data-mobile-order="summary" data-market-research-flow="trust" className="min-w-0">
        <MarketOverviewStatusStrip
          temperatureSummary={temperatureSummary}
          briefingSummary={briefingSummary}
        />
      </section>
      <MarketOverviewCategoryControls
        categoryTabs={categoryTabs}
        activeCategory={activeCategory}
        onCategoryChange={onCategoryChange}
        exportLabel={exportLabel}
        onExportSummary={onExportSummary}
      />
      <div data-market-research-flow="pulse">
        <CrossAssetHeroRibbon anchors={heroAnchors} />
      </div>
    </div>
  </section>
);
