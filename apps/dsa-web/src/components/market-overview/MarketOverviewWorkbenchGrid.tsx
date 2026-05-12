import type React from 'react';
import type { MarketOverviewPanel } from '../../api/marketOverview';
import { DataFreshnessBadge, MarketOverviewCardFrame } from './marketOverviewPrimitives';
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

const CompactRailCard: React.FC<{
  railKey: string;
  testId: string;
  eyebrow: string;
  title: string;
  value?: string;
  tone?: string;
  lines: React.ReactNode[];
}> = ({ railKey, testId, eyebrow, title, value, tone = 'text-white', lines }) => (
  <MarketOverviewCardFrame
    size="rail"
    testId="market-overview-compact-rail-card"
    railKey={railKey}
    className="min-w-0 overflow-hidden"
  >
    <div data-testid={testId} className="flex h-full min-w-0 flex-col gap-2">
      <div className="flex min-w-0 items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-[10px] font-bold uppercase tracking-widest text-white/40">{eyebrow}</p>
          <p className="mt-1 truncate text-sm font-semibold text-white/80">{title}</p>
        </div>
        {value ? <p className={cn('shrink-0 text-right font-mono text-lg font-semibold leading-none tabular-nums', tone)}>{value}</p> : null}
      </div>
      <div className="min-w-0 space-y-1 text-[11px] leading-4 text-white/46">
        {lines.slice(0, 4).map((line, index) => (
          <div key={index} className="truncate">{line}</div>
        ))}
      </div>
    </div>
  </MarketOverviewCardFrame>
);

const CategoryCoverageSummary: React.FC<{
  summary: MarketOverviewCoverageRailView;
}> = ({ summary }) => (
  <CompactRailCard
    railKey="coverage"
    testId="market-overview-rail-coverage"
    eyebrow="覆盖"
    title={`${summary.label}数据覆盖`}
    value={`${summary.real}/${summary.total}`}
    lines={[
      <span key="coverage" data-testid="market-overview-coverage-summary"><span className="text-white/62">{summary.label}数据覆盖：</span><span className="font-mono">真实 {summary.real} · 混合 {summary.mixed} · 备用 {summary.fallback}</span></span>,
    ]}
  />
);

const SignalWatchRailCard: React.FC<{ items: MarketOverviewSignalWatchRailItem[] }> = ({ items }) => (
  <MarketOverviewCardFrame
    size="rail"
    testId="market-overview-compact-rail-card"
    railKey="signal-watch"
    className="min-w-0 overflow-hidden"
  >
    <div data-testid="market-overview-rail-signal-watch" className="flex h-full min-w-0 flex-col gap-2">
      <div className="min-w-0">
        <p className="truncate text-[10px] font-bold tracking-widest text-white/40">信号观察</p>
        <p className="mt-1 truncate text-sm font-semibold text-white/80">关键观测</p>
      </div>
      <div className="flex min-w-0 flex-wrap gap-1.5 overflow-hidden">
        {items.map((item) => (
          <TerminalChip key={item.label} variant="neutral" className="max-w-full px-2 py-1 text-[10px] font-bold uppercase tracking-widest text-white/48">
            <span className="shrink-0">{item.label}</span>
            <span className={cn('min-w-0 truncate font-mono tracking-normal', item.changeToneClass)}>
              {item.changeText}
            </span>
          </TerminalChip>
        ))}
      </div>
    </div>
  </MarketOverviewCardFrame>
);

const ActionHintRailCard: React.FC<{ actionHint: MarketOverviewActionHintView }> = ({ actionHint }) => (
  <CompactRailCard
    railKey="action-hint"
    testId="market-overview-rail-action-hint"
    eyebrow="观察提示"
    title={actionHint.title}
    lines={[actionHint.line]}
  />
);

const DataQualityCompactRailCard: React.FC<{ summary: MarketOverviewQualityRailView }> = ({ summary }) => (
  <CompactRailCard
    railKey="quality"
    testId="market-overview-rail-quality"
    eyebrow="质量"
    title={`数据质量：${summary.status}`}
    value={`${summary.availableCount}`}
    tone={summary.hasConcern ? 'text-amber-200' : 'text-emerald-300'}
    lines={[
      <span key="quality" data-testid="market-data-quality">可用快照 · 备用 {summary.fallbackCount}</span>,
      <span key="risk" className="font-mono">过期 {summary.staleCount} · 缺失 {summary.errorCount}</span>,
    ]}
  />
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
  <TerminalGrid data-testid="market-overview-main-grid" data-workbench-split="9:3" className="gap-4">
    <section
      data-testid="market-overview-primary-rail"
      data-mobile-order="main"
      className="flex min-w-0 flex-col gap-4 xl:col-span-9"
    >
      <div data-testid="market-overview-main-stack" className="flex min-w-0 flex-col gap-4">
        <section data-testid="market-overview-hero-lane" data-card-tier="hero" className="min-w-0">
          {heroRows}
        </section>
        <section data-testid="market-overview-secondary-grid" data-card-tier="secondary" className="flex min-w-0 flex-col gap-4">
          {secondaryRows}
        </section>
      </div>
    </section>
    <aside data-testid="market-overview-side-rail" data-mobile-order="rail" className="flex min-w-0 flex-col gap-3 xl:col-span-3">
      <div data-testid="market-overview-rail" className="flex min-w-0 flex-col gap-3">
        {showCoverageRail ? <CategoryCoverageSummary summary={coverageRail} /> : null}
        {showQualityRail ? <DataQualityCompactRailCard summary={qualityRail} /> : null}
        {showSignalWatchRail ? <SignalWatchRailCard items={signalWatchItems} /> : null}
        {showActionHintRail ? <ActionHintRailCard actionHint={actionHint} /> : null}
      </div>
    </aside>
    {showDeepSection ? (
      <section
        data-testid="market-overview-deep-panels"
        data-panel-grouping="deterministic-rows"
        data-mobile-order="deep"
        data-card-tier="deep"
        className="flex min-w-0 flex-col gap-4 xl:col-span-9"
      >
        {deepRows}
        {showExecutiveGroups ? <ExecutiveSecondaryGroups groups={executiveGroups} /> : null}
      </section>
    ) : null}
  </TerminalGrid>
);
