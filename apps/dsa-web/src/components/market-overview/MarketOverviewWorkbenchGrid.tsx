import type React from 'react';
import type { MarketOverviewPanel } from '../../api/marketOverview';
import { DataFreshnessBadge, MarketOverviewCardFrame } from './marketOverviewPrimitives';
import {
  ConsoleBoard,
  ConsoleContextRail,
} from '../linear';
import { TerminalGrid } from '../terminal';
import { cn } from '../../utils/cn';

export type MarketOverviewContextHighlightView = {
  id: string;
  eyebrow: string;
  title: string;
  detail: string;
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
  showContextRail: boolean;
  contextHighlights: MarketOverviewContextHighlightView[];
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

const ContextHighlightsRail: React.FC<{
  items: MarketOverviewContextHighlightView[];
}> = ({ items }) => (
  <section data-testid="market-overview-context-rail" className="flex min-w-0 flex-col gap-3">
    {items.map((item) => {
      const railTestId = item.id === 'next-watch'
        ? 'market-overview-rail-action-hint'
        : item.id === 'data-status'
          ? 'market-overview-rail-quality'
          : `market-overview-context-${item.id}`;
      return (
        <RailSummaryBlock
          key={item.id}
          testId={railTestId}
          eyebrow={item.eyebrow}
          title={item.title}
        >
          {item.id === 'next-watch' ? (
            <span data-testid="market-overview-rail-signal-watch">{item.detail}</span>
          ) : item.id === 'data-status' ? (
            <span data-testid="market-overview-coverage-summary">
              <span data-testid="market-data-quality">{item.title}</span>
              <span className="block mt-1">{item.detail}</span>
            </span>
          ) : (
            item.detail
          )}
        </RailSummaryBlock>
      );
    })}
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
  showContextRail,
  contextHighlights,
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
          {showContextRail ? <ContextHighlightsRail items={contextHighlights} /> : null}
        </div>
      </ConsoleContextRail>
    </aside>
  </TerminalGrid>
);
