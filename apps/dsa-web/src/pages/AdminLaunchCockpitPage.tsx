import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Ban, CheckCircle2, FileText, ShieldAlert } from 'lucide-react';
import {
  adminOpsStatusApi,
  type AdminOpsCockpitDomain,
  type AdminOpsCockpitMaintenanceQueueItem,
  type AdminOpsStatusResponse,
} from '../api/adminOpsStatus';
import AdminOpsL0OverviewStrip from '../components/admin/AdminOpsL0OverviewStrip';
import {
  TerminalChip,
  TerminalMetric,
  TerminalNestedBlock,
  TerminalNotice,
  TerminalPageHeading,
  TerminalPageShell,
  TerminalPanel,
} from '../components/terminal/TerminalPrimitives';
import { cn } from '../utils/cn';

function boolChip(value: boolean, trueLabel: string, falseLabel: string, invert = false) {
  const variant = value
    ? (invert ? 'danger' : 'success')
    : (invert ? 'success' : 'neutral');
  return <TerminalChip variant={variant}>{value ? trueLabel : falseLabel}</TerminalChip>;
}

function compactItems(items: string[] | undefined, max = 2): string[] {
  return Array.isArray(items) ? items.filter(Boolean).slice(0, max) : [];
}

function domainStatusVariant(domain: AdminOpsCockpitDomain): React.ComponentProps<typeof TerminalChip>['variant'] {
  if (domain.publicLaunchNoGo) return domain.realOperatorEvidenceMissing ? 'danger' : 'caution';
  if (domain.approvalRequired) return 'caution';
  return 'success';
}

function priorityVariant(priorityTier: string): React.ComponentProps<typeof TerminalChip>['variant'] {
  if (priorityTier === 'critical') return 'danger';
  if (priorityTier === 'high') return 'caution';
  if (priorityTier === 'medium') return 'info';
  return 'neutral';
}

function StatusBadgeRow({ domain }: { domain: AdminOpsCockpitDomain }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {boolChip(domain.foundationLanded, 'Foundation landed', 'Foundation partial')}
      {boolChip(domain.evidenceToolingPresent, 'Evidence tooling present', 'Evidence tooling missing')}
      {boolChip(domain.realOperatorEvidenceMissing, 'Real evidence missing', 'Real evidence present', true)}
      {boolChip(domain.approvalRequired, 'Manual approval required', 'Approval not required', true)}
      {boolChip(domain.publicLaunchNoGo, 'Public launch NO-GO', 'Public launch cleared', true)}
    </div>
  );
}

function DomainCard({ domain }: { domain: AdminOpsCockpitDomain }) {
  const evidenceRefs = compactItems(domain.evidenceRefs, 3);
  const blockerRefs = compactItems(domain.blockerRefs, 2);
  const nextActions = compactItems(domain.safeNextActions, 2);
  const proposals = domain.followUpProposals.slice(0, 1);

  return (
    <TerminalPanel
      as="article"
      data-testid="admin-launch-cockpit-domain-card"
      className="min-w-0 space-y-4"
    >
      <div className="flex min-w-0 flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-white/34">
            {domain.domainKey}
          </p>
          <h2 className="mt-1 text-base font-semibold text-white">{domain.label}</h2>
          <p className="mt-1 text-xs leading-5 text-white/58">{domain.statusLabel}</p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-1.5 xl:justify-end">
          <TerminalChip variant={priorityVariant(domain.priorityTier)}>#{domain.priorityRank}</TerminalChip>
          <TerminalChip variant={priorityVariant(domain.priorityTier)}>{domain.priorityTier}</TerminalChip>
          <TerminalChip variant={domainStatusVariant(domain)} className="justify-center">
            {domain.publicLaunchNoGo ? 'NO-GO' : domain.status}
          </TerminalChip>
        </div>
      </div>

      <StatusBadgeRow domain={domain} />

      <TerminalNestedBlock className="min-w-0">
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-white/34">Recommended next action</p>
        <p className="mt-2 text-xs leading-5 text-white/72">{domain.recommendedNextAction}</p>
        <p className="mt-1 text-[11px] leading-5 text-white/52">{domain.blockingReasonSummary}</p>
      </TerminalNestedBlock>

      <div className="grid gap-3 lg:grid-cols-3">
        <TerminalNestedBlock className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-white/34">Evidence refs</p>
          <div className="mt-2 space-y-1.5">
            {evidenceRefs.map((item) => (
              <p key={item} className="break-words font-mono text-[11px] leading-5 text-white/68">{item}</p>
            ))}
          </div>
        </TerminalNestedBlock>
        <TerminalNestedBlock className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-white/34">Blocker refs</p>
          <div className="mt-2 space-y-1.5">
            {blockerRefs.map((item) => (
              <p key={item} className="break-words font-mono text-[11px] leading-5 text-white/68">{item}</p>
            ))}
          </div>
        </TerminalNestedBlock>
        <TerminalNestedBlock className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-white/34">Safe next actions</p>
          <div className="mt-2 space-y-1.5">
            {nextActions.map((item) => (
              <p key={item} className="text-xs leading-5 text-white/68">{item}</p>
            ))}
          </div>
        </TerminalNestedBlock>
      </div>

      {proposals.length > 0 ? (
        <div className="rounded-lg border border-amber-300/16 bg-amber-300/[0.04] p-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-amber-100">
            <ShieldAlert className="size-4" />
            <span>Approval-required follow-up</span>
          </div>
          {proposals.map((proposal) => (
            <div key={proposal.proposalKey} className="mt-2 space-y-1 text-xs leading-5 text-white/64">
              <p className="font-medium text-white/82">{proposal.title}</p>
              <p>Risk: {proposal.risk}</p>
              {proposal.likelyFiles.slice(0, 2).map((file) => (
                <p key={file} className="break-words font-mono text-[11px] text-white/58">{file}</p>
              ))}
            </div>
          ))}
        </div>
      ) : null}

      <Link
        to={domain.detailRoute}
        className="inline-flex min-h-[40px] items-center gap-2 rounded-md border border-white/[0.08] bg-white/[0.03] px-3 text-xs font-medium text-white/74 transition-colors hover:border-white/18 hover:text-white"
      >
        <FileText className="size-4" />
        <span>Open read-only detail</span>
        <ArrowRight className="size-4" />
      </Link>
    </TerminalPanel>
  );
}

function MaintenanceQueue({ items }: { items: AdminOpsCockpitMaintenanceQueueItem[] }) {
  if (items.length === 0) {
    return null;
  }

  return (
    <section data-testid="admin-launch-cockpit-maintenance-queue" className="space-y-3">
      <div className="flex items-center gap-2">
        <ShieldAlert className="size-4 text-amber-200" />
        <h2 className="text-sm font-semibold text-white">Recommended maintenance queue</h2>
      </div>
      <div className="grid gap-3 lg:grid-cols-3">
        {items.map((item) => (
          <TerminalPanel
            key={item.domainKey}
            data-testid="admin-launch-cockpit-queue-item"
            className="space-y-2"
          >
            <div className="flex flex-wrap items-center gap-1.5">
              <TerminalChip variant={priorityVariant(item.priorityTier)}>#{item.priorityRank}</TerminalChip>
              <TerminalChip variant={priorityVariant(item.priorityTier)}>{item.priorityTier}</TerminalChip>
              <TerminalChip variant="neutral">{item.impactLevel}</TerminalChip>
            </div>
            <h3 className="text-sm font-semibold text-white">{item.label}</h3>
            <p className="text-xs leading-5 text-white/66">{item.recommendedNextAction}</p>
            <p className="text-[11px] leading-5 text-white/48">{item.blockingReasonSummary}</p>
          </TerminalPanel>
        ))}
      </div>
    </section>
  );
}

const AdminLaunchCockpitPage: React.FC = () => {
  const [snapshot, setSnapshot] = useState<AdminOpsStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    adminOpsStatusApi.getStatus()
      .then((payload) => {
        if (!cancelled) {
          setSnapshot(payload);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSnapshot(null);
          setLoadFailed(true);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const cockpit = snapshot?.launchCockpit;
  const counts = cockpit?.summaryCounts ?? {};
  const generatedAt = snapshot?.generatedAt || 'not loaded';
  const sortedDomains = useMemo(
    () => [...(cockpit?.domains ?? [])].sort((left, right) => {
      const leftRank = left.priorityRank || Number.MAX_SAFE_INTEGER;
      const rightRank = right.priorityRank || Number.MAX_SAFE_INTEGER;
      return leftRank - rightRank || left.label.localeCompare(right.label);
    }),
    [cockpit?.domains],
  );
  const maintenanceQueue = useMemo(
    () => [...(cockpit?.recommendedMaintenanceQueue ?? [])].sort((left, right) => {
      const leftRank = left.priorityRank || Number.MAX_SAFE_INTEGER;
      const rightRank = right.priorityRank || Number.MAX_SAFE_INTEGER;
      return leftRank - rightRank || left.label.localeCompare(right.label);
    }),
    [cockpit?.recommendedMaintenanceQueue],
  );

  return (
    <TerminalPageShell
      data-testid="admin-launch-cockpit-page"
      className="min-h-0 flex-1 overflow-x-hidden py-5 text-white md:py-6"
    >
      <TerminalPageHeading
        eyebrow="Admin/Ops private beta"
        title="Private Beta Launch Cockpit"
        action={(
          <div className="flex flex-wrap gap-2">
            <TerminalChip variant="danger">Public launch NO-GO</TerminalChip>
            <TerminalChip variant="info">Read-only advisory</TerminalChip>
            <TerminalChip variant="neutral">No external calls</TerminalChip>
          </div>
        )}
      />

      <p className="max-w-4xl text-sm leading-6 text-white/58">
        Operator view for readiness, evidence, blockers, and safe next actions. It does not approve launch,
        execute validators, change runtime behavior, send notifications, call providers, or run storage actions.
      </p>

      <AdminOpsL0OverviewStrip
        dataTestId="admin-launch-cockpit-l0-overview-strip"
        language="en"
        systemTrustState="blocked"
        impact="Security, quota, provider reliability, storage, WS2, notifications, portfolio/backtest, route classification, and frontend safety."
        recommendedAction="Review missing real evidence and approval-required follow-ups; keep public launch blocked."
        evidenceRef={cockpit?.contract || 'admin_ops_launch_cockpit_v1'}
        lastUpdated={generatedAt}
      />

      {loadFailed ? (
        <TerminalNotice data-testid="admin-launch-cockpit-error" variant="danger">
          Unable to load cockpit snapshot. Keep launch blocked and use existing admin evidence pages until the
          read-only snapshot is available.
        </TerminalNotice>
      ) : null}

      {isLoading ? (
        <TerminalNotice variant="info">Loading read-only cockpit snapshot...</TerminalNotice>
      ) : null}

      <div className="grid gap-3 md:grid-cols-4">
        <TerminalMetric label="Domains" value={String(counts.domainCount ?? sortedDomains.length)} subvalue="readiness slices" />
        <TerminalMetric label="NO-GO domains" value={String(counts.publicLaunchNoGoCount ?? 0)} subvalue="public launch blocked" />
        <TerminalMetric label="Evidence missing" value={String(counts.realEvidenceMissingCount ?? 0)} subvalue="real operator proof" />
        <TerminalMetric label="Approval required" value={String(counts.approvalRequiredCount ?? 0)} subvalue="manual review gate" />
      </div>

      <TerminalPanel data-testid="admin-launch-cockpit-safety" className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Ban className="size-4 text-[color:var(--wolfy-market-down)]" />
          <p className="text-sm font-semibold text-white">Invariant checks</p>
          {boolChip(Boolean(cockpit?.publicLaunchApproved), 'Launch approved', 'Launch not approved', true)}
          {boolChip(Boolean(cockpit?.liveEnforcement), 'Live enforcement on', 'Live enforcement off', true)}
          {boolChip(Boolean(cockpit?.runtimeBehaviorChanged), 'Runtime changed', 'Runtime unchanged', true)}
        </div>
        <div className="grid gap-2 md:grid-cols-3">
          {Object.entries(cockpit?.unsafeActionStates ?? {}).map(([key, value]) => (
            <TerminalNestedBlock key={key} className={cn('min-w-0', value ? 'border-red-300/20' : '')}>
              <p className="break-words font-mono text-[11px] text-white/56">{key}</p>
              <div className="mt-2">
                {boolChip(Boolean(value), 'enabled', 'disabled', true)}
              </div>
            </TerminalNestedBlock>
          ))}
        </div>
      </TerminalPanel>

      <MaintenanceQueue items={maintenanceQueue} />

      <section data-testid="admin-launch-cockpit-blockers" className="space-y-3">
        <div className="flex items-center gap-2">
          <ShieldAlert className="size-4 text-amber-200" />
          <h2 className="text-sm font-semibold text-white">NO-GO blockers</h2>
        </div>
        <div className="grid gap-3 lg:grid-cols-2">
          {(cockpit?.blockers ?? []).map((blocker) => (
            <TerminalPanel key={blocker.blockerKey} className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <TerminalChip variant="danger">{blocker.severity}</TerminalChip>
                <TerminalChip variant="caution">Approval required</TerminalChip>
              </div>
              <h3 className="text-sm font-semibold text-white">{blocker.title}</h3>
              <p className="text-xs leading-5 text-white/62">{blocker.nextAction}</p>
              {compactItems(blocker.evidenceRefs, 2).map((item) => (
                <p key={item} className="break-words font-mono text-[11px] leading-5 text-white/52">{item}</p>
              ))}
            </TerminalPanel>
          ))}
        </div>
      </section>

      <section data-testid="admin-launch-cockpit-domain-grid" className="grid gap-4 xl:grid-cols-2">
        {sortedDomains.map((domain) => (
          <DomainCard key={domain.domainKey} domain={domain} />
        ))}
      </section>

      <TerminalPanel className="space-y-2">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="size-4 text-[color:var(--wolfy-market-up)]" />
          <p className="text-sm font-semibold text-white">Safe next actions</p>
        </div>
        <div className="grid gap-2 md:grid-cols-3">
          {(cockpit?.safeNextActions ?? []).map((item) => (
            <TerminalNestedBlock key={item} className="text-xs leading-5 text-white/68">
              {item}
            </TerminalNestedBlock>
          ))}
        </div>
      </TerminalPanel>
    </TerminalPageShell>
  );
};

export default AdminLaunchCockpitPage;
