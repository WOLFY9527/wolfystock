import type React from 'react';
import type { MarketOverviewPanel } from '../../api/marketOverview';
import { DataFreshnessBadge, MarketOverviewCardFrame } from './marketOverviewPrimitives';
import {
  ConsoleBoard,
  ConsoleContextRail,
  ConsoleDisclosure,
} from '../linear';
import { TerminalChip, TerminalGrid } from '../terminal';
import { cn } from '../../utils/cn';

export type MarketOverviewCoverageRailView = {
  label: string;
  real: number;
  mixed: number;
  fallback: number;
  total: number;
};

export type MarketOverviewQualityRailView = {
  status: string;
  availableCount: number;
  fallbackCount: number;
  staleCount: number;
  errorCount: number;
  hasConcern: boolean;
};

export type MarketOverviewSignalWatchRailItem = {
  label: string;
  changeText: string;
  changeToneClass: string;
};

export type MarketOverviewActionHintView = {
  title: string;
  line: string;
};

export type MarketOverviewExecutiveGroupView = {
  id: string;
  label: string;
  focus: string;
  valueText: string;
  changeText: string;
  changeToneClass: string;
  freshness: MarketOverviewPanel['freshness'];
  coverage: 'real' | 'mixed' | 'fallback';
};

type MarketOverviewWorkbenchGridProps = {
  heroRows: React.ReactNode[];
  secondaryRows: React.ReactNode[];
  deepRows: React.ReactNode[];
  showDeepSection: boolean;
  showCoverageRail: boolean;
  showQualityRail: boolean;
  showSignalWatchRail: boolean;
  showActionHintRail: boolean;
  coverageRail: MarketOverviewCoverageRailView;
  qualityRail: MarketOverviewQualityRailView;
  signalWatchItems: MarketOverviewSignalWatchRailItem[];
  actionHint: MarketOverviewActionHintView;
  executiveGroups: MarketOverviewExecutiveGroupView[];
  showExecutiveGroups: boolean;
};

const RailSummaryBlock: React.FC<{
  testId: string;
  eyebrow: string;
  title: string;
  children: React.ReactNode;
}> = ({ testId, eyebrow, title, children }) => (
  <div
    data-testid={testId}
    className="min-w-0 rounded-md border border-[color:var(--wolfy-divider)] bg-[color:var(--wolfy-surface-input)] px-3 py-2"
  >
    <p className="truncate text-[10px] font-bold uppercase tracking-widest text-white/38">{eyebrow}</p>
    <p className="mt-1 truncate text-sm font-semibold text-white/80">{title}</p>
    <div className="mt-2 min-w-0 text-[11px] leading-4 text-white/48">
      {children}
    </div>
  </div>
);

const RuntimeDetailsRail: React.FC<{
  coverageRail: MarketOverviewCoverageRailView;
  qualityRail: MarketOverviewQualityRailView;
}> = ({ coverageRail, qualityRail }) => (
  <section data-testid="market-overview-runtime-details" className="flex min-w-0 flex-col gap-3">
    <RailSummaryBlock
      testId="market-overview-rail-coverage"
      eyebrow="覆盖"
      title={`${coverageRail.label}数据覆盖`}
    >
      <span data-testid="market-overview-coverage-summary">
        <span className="text-white/62">{coverageRail.label}数据覆盖：</span>
        <span className="font-mono">真实 {coverageRail.real} · 混合 {coverageRail.mixed} · 备用 {coverageRail.fallback}</span>
      </span>
    </RailSummaryBlock>
    <RailSummaryBlock
      testId="market-overview-rail-quality"
      eyebrow="质量"
      title={`数据质量：${qualityRail.status}`}
    >
      <div className="space-y-1">
        <span data-testid="market-data-quality">可用快照 · 备用 {qualityRail.fallbackCount}</span>
        <div className="font-mono">过期 {qualityRail.staleCount} · 缺失 {qualityRail.errorCount}</div>
      </div>
    </RailSummaryBlock>
    <ConsoleDisclosure
      title="数据来源与运行细节"
      summary={`${coverageRail.label} ${coverageRail.real}/${coverageRail.total} · ${qualityRail.status}`}
    >
      <div className="space-y-3 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">
        <div className="rounded-md border border-[color:var(--wolfy-divider)] bg-[color:var(--wolfy-surface-console)] px-3 py-2">
          <p className="text-[10px] uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">覆盖拆分</p>
          <p className="mt-1 font-mono text-sm text-[color:var(--wolfy-text-primary)]">
            真实 {coverageRail.real} · 混合 {coverageRail.mixed} · 备用 {coverageRail.fallback}
          </p>
        </div>
        <div className="rounded-md border border-[color:var(--wolfy-divider)] bg-[color:var(--wolfy-surface-console)] px-3 py-2">
          <p className="text-[10px] uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">运行质量</p>
          <p className="mt-1 font-mono text-sm text-[color:var(--wolfy-text-primary)]">
            可用 {qualityRail.availableCount} · 备用 {qualityRail.fallbackCount} · 过期 {qualityRail.staleCount} · 缺失 {qualityRail.errorCount}
          </p>
        </div>
      </div>
    </ConsoleDisclosure>
  </section>
);

const SignalWatchDisclosure: React.FC<{ items: MarketOverviewSignalWatchRailItem[] }> = ({ items }) => (
  <section data-testid="market-overview-signal-disclosure" className="flex min-w-0 flex-col gap-3">
    <div data-testid="market-overview-rail-signal-watch" className="flex min-w-0 flex-wrap gap-1.5">
      {items.map((item) => (
        <TerminalChip key={item.label} variant="neutral" className="max-w-full px-2 py-1 text-[10px] font-bold uppercase tracking-widest text-white/48">
          <span className="shrink-0">{item.label}</span>
          <span className={cn('min-w-0 truncate font-mono tracking-normal', item.changeToneClass)}>
            {item.changeText}
          </span>
        </TerminalChip>
      ))}
    </div>
    <ConsoleDisclosure
      title="关键观测"
      summary={`${items.length} 个跨资产观测点`}
    >
      <div className="space-y-2 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">
        {items.map((item) => (
          <div
            key={item.label}
            className="flex items-center justify-between gap-3 rounded-md border border-[color:var(--wolfy-divider)] bg-[color:var(--wolfy-surface-console)] px-3 py-2"
          >
            <span className="text-[color:var(--wolfy-text-primary)]">{item.label}</span>
            <span className={cn('font-mono', item.changeToneClass)}>{item.changeText}</span>
          </div>
        ))}
      </div>
    </ConsoleDisclosure>
  </section>
);

const ActionHintDisclosure: React.FC<{ actionHint: MarketOverviewActionHintView }> = ({ actionHint }) => (
  <section data-testid="market-overview-action-disclosure" className="flex min-w-0 flex-col gap-3">
    <RailSummaryBlock
      testId="market-overview-rail-action-hint"
      eyebrow="观察提示"
      title={actionHint.title}
    >
      {actionHint.line}
    </RailSummaryBlock>
    <ConsoleDisclosure
      title="观察提示"
      summary={actionHint.title}
    >
      <div className="rounded-md border border-[color:var(--wolfy-divider)] bg-[color:var(--wolfy-surface-console)] px-3 py-2 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">
        {actionHint.line}
      </div>
    </ConsoleDisclosure>
  </section>
);

const ExecutiveSecondaryGroups: React.FC<{
  groups: MarketOverviewExecutiveGroupView[];
}> = ({ groups }) => (
  <section
    data-testid="market-overview-executive-secondary-groups"
    className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4"
  >
    {groups.map((group) => (
      <MarketOverviewCardFrame
        key={group.id}
        size="compact"
        testId={`market-overview-secondary-group-${group.id}`}
        className="h-full"
      >
        <div className="flex h-full min-w-0 flex-col justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-widest text-white/40">{group.label}</p>
            <p className="mt-1 truncate text-sm font-semibold text-white/80">{group.focus}</p>
          </div>
          <div className="flex min-w-0 items-end justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate font-mono text-lg font-semibold leading-none text-white">
                {group.valueText}
              </p>
              <p className={cn('mt-1 truncate font-mono text-[11px] font-bold', group.changeToneClass)}>
                {group.changeText}
              </p>
            </div>
            <div className="flex shrink-0 flex-col items-end gap-1">
              <DataFreshnessBadge
                freshness={(group.freshness || (group.coverage === 'fallback' ? 'fallback' : 'cached')) as MarketOverviewPanel['freshness']}
                status={group.coverage === 'mixed' ? 'partial' : undefined}
                className="px-1.5 text-[9px]"
              />
              <span className="font-mono text-[10px] uppercase text-white/32">{group.coverage}</span>
            </div>
          </div>
        </div>
      </MarketOverviewCardFrame>
    ))}
  </section>
);

export const MarketOverviewWorkbenchGrid: React.FC<MarketOverviewWorkbenchGridProps> = ({
  heroRows,
  secondaryRows,
  deepRows,
  showDeepSection,
  showCoverageRail,
  showQualityRail,
  showSignalWatchRail,
  showActionHintRail,
  coverageRail,
  qualityRail,
  signalWatchItems,
  actionHint,
  executiveGroups,
  showExecutiveGroups,
}) => (
  <TerminalGrid
    data-testid="market-overview-main-grid"
    data-workbench-split="9:3"
    data-market-monitor-layout="board-plus-context"
    className="gap-4"
  >
    <section
      data-testid="market-overview-primary-rail"
      data-mobile-order="main"
      className="flex min-w-0 flex-col gap-4 xl:col-span-9"
    >
      <ConsoleBoard className="h-full">
        <div data-testid="market-overview-main-stack" className="flex min-w-0 flex-col gap-4 p-3 md:p-4">
          <section data-testid="market-overview-hero-lane" data-card-tier="hero" className="min-w-0">
            {heroRows}
          </section>
          <section data-testid="market-overview-secondary-grid" data-card-tier="secondary" className="flex min-w-0 flex-col gap-4">
            {secondaryRows}
          </section>
          {showDeepSection ? (
            <section
              data-testid="market-overview-deep-panels"
              data-panel-grouping="deterministic-rows"
              data-mobile-order="deep"
              data-card-tier="deep"
              className="flex min-w-0 flex-col gap-4"
            >
              {deepRows}
              {showExecutiveGroups ? <ExecutiveSecondaryGroups groups={executiveGroups} /> : null}
            </section>
          ) : null}
        </div>
      </ConsoleBoard>
    </section>
    <aside data-testid="market-overview-side-rail" data-mobile-order="rail" className="flex min-w-0 flex-col gap-3 xl:col-span-3">
      <ConsoleContextRail>
        <div data-testid="market-overview-rail" className="flex min-w-0 flex-col gap-3">
          {showCoverageRail || showQualityRail ? (
            <RuntimeDetailsRail coverageRail={coverageRail} qualityRail={qualityRail} />
          ) : null}
          {showSignalWatchRail ? <SignalWatchDisclosure items={signalWatchItems} /> : null}
          {showActionHintRail ? <ActionHintDisclosure actionHint={actionHint} /> : null}
        </div>
      </ConsoleContextRail>
    </aside>
  </TerminalGrid>
);
