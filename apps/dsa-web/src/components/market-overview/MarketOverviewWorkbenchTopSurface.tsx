import type React from 'react';
import type { MarketOverviewTab } from '../../pages/MarketOverviewTabConfig';
import {
  ConsoleBoard,
  ConsoleStatusStrip,
  KeyLevelStrip,
} from '../linear';
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
}) => {
  const regimeStripItems = [
    { key: 'regime', label: '状态', value: decisionReliable ? temperatureSummary.label : '数据不足' },
    { key: 'temperature', label: '温度', value: temperatureSummary.valueText },
    { key: 'confidence', label: '可信度', value: temperatureSummary.confidenceLabel },
    {
      key: 'coverage',
      label: '覆盖',
      value: `可用 ${dataState.availableCount} · 备用 ${dataState.fallbackCount} · 过期 ${dataState.staleCount}`,
    },
    {
      key: 'updatedAt',
      label: '更新时间',
      value: dataState.updatedAtLabel || (dataState.isRefreshing ? '刷新中' : '待刷新'),
    },
  ];

  return (
    <section data-testid="market-overview-pulse-header" className="flex w-full min-w-0 flex-col gap-4">
      {heading}
      <section data-testid="market-overview-market-monitor" className="flex w-full min-w-0 flex-col gap-4">
        <ConsoleStatusStrip
          data-testid="market-overview-regime-strip"
          items={regimeStripItems}
        />
        <ConsoleBoard data-testid="market-overview-primary-board">
          <div data-testid="market-overview-top-stack" className="flex w-full min-w-0 flex-col">
            <MarketDecisionStrip text={decisionText} chips={decisionChips} reliable={decisionReliable} />
            <div className="border-t border-[color:var(--wolfy-divider)] px-3 py-3 md:px-4">
              <MarketOverviewCategoryControls
                categoryTabs={categoryTabs}
                activeCategory={activeCategory}
                onCategoryChange={onCategoryChange}
                exportLabel={exportLabel}
                onExportSummary={onExportSummary}
              />
            </div>
            <section
              data-testid="market-overview-summary-band"
              data-mobile-order="summary"
              data-market-research-flow="trust"
              className="min-w-0 border-t border-[color:var(--wolfy-divider)] px-3 py-3 md:px-4"
            >
              <MarketOverviewStatusStrip
                temperatureSummary={temperatureSummary}
                briefingSummary={briefingSummary}
              />
            </section>
            <div data-market-research-flow="pulse" className="border-t border-[color:var(--wolfy-divider)]">
              <CrossAssetHeroRibbon anchors={heroAnchors} />
            </div>
            <div className="border-t border-[color:var(--wolfy-divider)] px-3 py-3 md:px-4">
              <MarketOverviewDataStateStrip dataState={dataState} />
            </div>
          </div>
        </ConsoleBoard>
      </section>
    </section>
  );
};
