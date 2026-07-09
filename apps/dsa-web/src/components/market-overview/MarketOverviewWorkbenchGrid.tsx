import type React from 'react';
import type { MarketOverviewPanel } from '../../api/marketOverview';
import { DataFreshnessBadge, MarketOverviewCardFrame } from './marketOverviewPrimitives';
import {
  ConsoleBoard,
  ConsoleContextRail,
} from '../linear/LinearPrimitives';
import { TerminalGrid } from '../terminal/TerminalPrimitives';
import { MetaLabel, SectionTitle } from '../research/anatomy';
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

export type MarketOverviewEvidenceGroupView = {
  id: string;
  role:
    | 'regime-breadth'
    | 'volatility-risk'
    | 'liquidity-funding'
    | 'sentiment-positioning'
    | 'cross-asset'
    | 'supporting'
    | 'deep';
  tier: 'secondary' | 'deep';
  label: string;
  claim: string;
  rows: React.ReactNode[];
};

type MarketOverviewWorkbenchGridProps = {
  secondaryRows: React.ReactNode[];
  deepRows: React.ReactNode[];
  evidenceGroups?: MarketOverviewEvidenceGroupView[];
  showDeepSection: boolean;
  showContextRail: boolean;
  contextHighlights: MarketOverviewContextHighlightView[];
  executiveGroups: MarketOverviewExecutiveGroupView[];
  showExecutiveGroups: boolean;
};

const EXECUTIVE_COVERAGE_LABELS: Record<MarketOverviewExecutiveGroupView['coverage'], string> = {
  real: '可用',
  mixed: '部分可用',
  fallback: '延迟可用',
};

const RailSummaryBlock: React.FC<{
  testId: string;
  eyebrow: string;
  title: string;
  children: React.ReactNode;
}> = ({ testId, eyebrow, title, children }) => (
  <div
    data-testid={testId}
    className="min-w-0 rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-input)] px-3 py-2"
  >
    <p className="truncate text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{eyebrow}</p>
    <p className="mt-1 truncate text-sm font-semibold text-[color:var(--wolfy-text-secondary)]">{title}</p>
    <div className="mt-2 min-w-0 text-[11px] leading-4 text-[color:var(--wolfy-text-muted)]">
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
              <span className="mt-1 block">{item.detail}</span>
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
            <p className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{group.label}</p>
            <p className="mt-1 truncate text-sm font-semibold text-[color:var(--wolfy-text-secondary)]">{group.focus}</p>
          </div>
          <div className="flex min-w-0 items-end justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate font-mono text-lg font-semibold leading-none text-[color:var(--wolfy-text-primary)]">
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
              <span className="font-mono text-[10px] uppercase text-[color:var(--wolfy-text-muted)]">
                {EXECUTIVE_COVERAGE_LABELS[group.coverage]}
              </span>
            </div>
          </div>
        </div>
      </MarketOverviewCardFrame>
    ))}
  </section>
);

const EvidenceGroupSection: React.FC<{
  group: MarketOverviewEvidenceGroupView;
}> = ({ group }) => {
  if (!group.rows.length) {
    return null;
  }
  return (
    <section
      data-testid={`market-overview-evidence-group-${group.id}`}
      data-evidence-group-role={group.role}
      data-market-research-flow="evidence-group"
      className="flex min-w-0 flex-col gap-3 border-t border-[color:var(--wolfy-divider)] pt-3 first:border-t-0 first:pt-0"
    >
      <div className="flex min-w-0 flex-col gap-1">
        <MetaLabel>{group.label}</MetaLabel>
        <SectionTitle as="h2" className="text-base">
          {group.claim}
        </SectionTitle>
      </div>
      <div className="flex min-w-0 flex-col gap-4">
        {group.rows}
      </div>
    </section>
  );
};

export const MarketOverviewWorkbenchGrid: React.FC<MarketOverviewWorkbenchGridProps> = ({
  secondaryRows,
  deepRows,
  evidenceGroups,
  showDeepSection,
  showContextRail,
  contextHighlights,
  executiveGroups,
  showExecutiveGroups,
}) => {
  const secondaryGroups = (evidenceGroups || []).filter((group) => group.tier === 'secondary' && group.rows.length > 0);
  const deepGroups = (evidenceGroups || []).filter((group) => group.tier === 'deep' && group.rows.length > 0);
  const hasStructuredGroups = secondaryGroups.length > 0 || deepGroups.length > 0;
  const showDeepPanels = showDeepSection && (deepGroups.length > 0 || deepRows.length > 0 || showExecutiveGroups);

  return (
    <TerminalGrid
      data-testid="market-overview-main-grid"
      data-workbench-split="9:3"
      data-market-monitor-layout="drivers-plus-ledger"
      data-market-research-flow="drivers-ledger"
      data-market-overview-composition="grouped-evidence"
      className="gap-4"
    >
      <section
        data-testid="market-overview-primary-rail"
        data-mobile-order="main"
        className="flex min-w-0 flex-col gap-4 xl:col-span-9"
      >
        <ConsoleBoard className="h-full">
          <div data-testid="market-overview-main-stack" className="flex min-w-0 flex-col gap-4 p-3 md:p-4">
            <section
              data-testid="market-overview-secondary-grid"
              data-card-tier="secondary"
              data-market-research-flow="key-drivers"
              data-evidence-composition={hasStructuredGroups ? 'grouped' : 'rows'}
              className="flex min-w-0 flex-col gap-4"
            >
              {hasStructuredGroups
                ? secondaryGroups.map((group) => <EvidenceGroupSection key={group.id} group={group} />)
                : secondaryRows}
            </section>
            {showDeepPanels ? (
              <section
                data-testid="market-overview-deep-panels"
                data-panel-grouping={hasStructuredGroups ? 'grouped-evidence' : 'deterministic-rows'}
                data-mobile-order="deep"
                data-card-tier="deep"
                data-evidence-composition={hasStructuredGroups ? 'grouped' : 'rows'}
                className="flex min-w-0 flex-col gap-4 border-t border-[color:var(--wolfy-divider)] pt-4"
              >
                {hasStructuredGroups
                  ? deepGroups.map((group) => <EvidenceGroupSection key={group.id} group={group} />)
                  : deepRows}
                {showExecutiveGroups ? (
                  <div className="flex min-w-0 flex-col gap-3">
                    <div className="flex min-w-0 flex-col gap-1">
                      <MetaLabel>跨资产确认</MetaLabel>
                      <SectionTitle as="h2" className="text-base">
                        用区域与资产线索交叉核对
                      </SectionTitle>
                    </div>
                    <ExecutiveSecondaryGroups groups={executiveGroups} />
                  </div>
                ) : null}
              </section>
            ) : null}
          </div>
        </ConsoleBoard>
      </section>
      <aside
        data-testid="market-overview-side-rail"
        data-mobile-order="rail"
        data-market-research-flow="freshness-ledger"
        aria-label="Freshness and data-quality ledger"
        className="flex min-w-0 flex-col gap-3 xl:col-span-3"
      >
        <ConsoleContextRail>
          <div data-testid="market-overview-rail" className="flex min-w-0 flex-col gap-3">
            {showContextRail ? <ContextHighlightsRail items={contextHighlights} /> : null}
          </div>
        </ConsoleContextRail>
      </aside>
    </TerminalGrid>
  );
};
