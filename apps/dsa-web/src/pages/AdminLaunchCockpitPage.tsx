import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Ban, CheckCircle2, FileText, RefreshCw, ShieldAlert } from 'lucide-react';
import {
  adminOpsStatusApi,
  type AdminOpsCockpitDomain,
  type AdminOpsCockpitMaintenanceQueueItem,
  type AdminScannerUniverseReadinessResponse,
  type AdminScannerUniverseRefreshResponse,
  type AdminOpsStatusResponse,
} from '../api/adminOpsStatus';
import AdminOpsL0OverviewStrip from '../components/admin/AdminOpsL0OverviewStrip';
import {
  TerminalButton,
  TerminalChip,
  TerminalMetric,
  TerminalNestedBlock,
  TerminalNotice,
  TerminalPageHeading,
  TerminalPageShell,
  TerminalPanel,
} from '../components/terminal/TerminalPrimitives';
import { cn } from '../utils/cn';

const TEXT_PRIMARY = 'text-[color:var(--wolfy-text-primary)]';
const TEXT_SECONDARY = 'text-[color:var(--wolfy-text-secondary)]';
const TEXT_MUTED = 'text-[color:var(--wolfy-text-muted)]';

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

type ScannerMarket = 'us' | 'cn';

const SCANNER_MARKETS: ScannerMarket[] = ['us', 'cn'];

function scannerStatusVariant(status: string): React.ComponentProps<typeof TerminalChip>['variant'] {
  if (status === 'ready') return 'success';
  if (status === 'stale' || status === 'manual_action_required') return 'caution';
  if (status === 'missing' || status === 'not_configured' || status === 'unavailable') return 'danger';
  return 'neutral';
}

function readinessList(
  readiness: AdminScannerUniverseReadinessResponse | null | undefined,
  key: string,
): string[] {
  const value = readiness?.scannerUniverseReadiness?.[key];
  return Array.isArray(value)
    ? value.flatMap((item) => {
      const text = String(item || '').trim();
      return text ? [text] : [];
    })
    : [];
}

function ScannerUniverseReadinessPanel({
  readinessByMarket,
  refreshResults,
  refreshingMarket,
  onRefresh,
  loadFailed,
}: {
  readinessByMarket: Partial<Record<ScannerMarket, AdminScannerUniverseReadinessResponse>>;
  refreshResults: Partial<Record<ScannerMarket, AdminScannerUniverseRefreshResponse>>;
  refreshingMarket: ScannerMarket | null;
  onRefresh: (market: ScannerMarket) => void;
  loadFailed: boolean;
}) {
  return (
    <section data-testid="admin-scanner-universe-panel" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <ShieldAlert className="size-4 text-[color:var(--state-warning-text)]" aria-hidden="true" />
            <h2 className={cn('text-sm font-semibold', TEXT_PRIMARY)}>Scanner universe readiness</h2>
          </div>
          <p className={cn('mt-1 text-xs leading-5', TEXT_MUTED)}>
            Admin-only view of bounded US/CN scanner universe readiness and the existing safe refresh request.
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <TerminalChip variant="info">RBAC protected</TerminalChip>
          <TerminalChip variant="neutral">No provider calls</TerminalChip>
          <TerminalChip variant="neutral">No cache mutation</TerminalChip>
        </div>
      </div>

      {loadFailed ? (
        <TerminalNotice data-testid="admin-scanner-universe-error" variant="caution">
          Scanner universe readiness did not load. Keep Scanner and Research Radar readiness under manual review.
        </TerminalNotice>
      ) : null}

      <div className="grid gap-3 xl:grid-cols-2">
        {SCANNER_MARKETS.map((market) => {
          const readiness = readinessByMarket[market];
          const refresh = refreshResults[market];
          const missingFamilies = readinessList(readiness, 'missingDataFamilies');
          const missingClasses = readinessList(readiness, 'missingDataClasses');
          const availableClasses = readinessList(readiness, 'availableDataClasses');
          const blockingSurfaces = readinessList(readiness, 'blockedProductSurfaces');
          const affectedSurfaces = readiness?.affectedProductSurfaces ?? [];
          const isRefreshing = refreshingMarket === market;

          return (
            <TerminalPanel
              key={market}
              as="article"
              data-testid={`admin-scanner-universe-${market}`}
              className="space-y-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className={cn('text-[11px] font-semibold uppercase tracking-[0.16em]', TEXT_MUTED)}>
                    {market.toUpperCase()} scanner universe
                  </p>
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    <TerminalChip variant={scannerStatusVariant(readiness?.status || 'unavailable')}>
                      {readiness?.status || 'unavailable'}
                    </TerminalChip>
                    <TerminalChip variant="neutral">{readiness?.scannerUniverseStatus || 'unknown'}</TerminalChip>
                    <TerminalChip variant="neutral">{readiness?.profile || 'profile unknown'}</TerminalChip>
                  </div>
                </div>
                <TerminalButton
                  type="button"
                  variant="secondary"
                  aria-label={`Request ${market.toUpperCase()} scanner universe refresh`}
                  disabled={isRefreshing}
                  onClick={() => onRefresh(market)}
                  className="min-h-[40px] px-3 text-xs"
                >
                  <RefreshCw className={cn('size-4', isRefreshing ? 'animate-spin' : '')} aria-hidden="true" />
                  <span>{isRefreshing ? 'Requesting' : 'Request refresh'}</span>
                </TerminalButton>
              </div>

              <div className="grid gap-2 md:grid-cols-3">
                <TerminalMetric label="Universe" value={String(readiness?.universeSize ?? 0)} subvalue="symbols" />
                <TerminalMetric
                  label="Freshness"
                  value={readiness?.freshnessState || 'unknown'}
                  subvalue={readiness?.lastUpdatedAt || 'no timestamp'}
                  valueClassName="break-words text-xs leading-5"
                />
                <TerminalMetric
                  label="Candidate state"
                  value={readiness?.candidateGenerationState || 'unknown'}
                  subvalue="scanner generation"
                  valueClassName="break-words text-xs leading-5"
                />
              </div>

              <div className="grid gap-3 md:grid-cols-2">
                <TerminalNestedBlock className="min-w-0">
                  <p className={cn('text-[10px] font-semibold uppercase tracking-[0.16em]', TEXT_MUTED)}>Affected surfaces</p>
                  <p className={cn('mt-2 text-xs leading-5', TEXT_SECONDARY)}>
                    {(affectedSurfaces.length ? affectedSurfaces : ['Scanner', 'Research Radar']).join(' / ')}
                  </p>
                </TerminalNestedBlock>
                <TerminalNestedBlock className="min-w-0">
                  <p className={cn('text-[10px] font-semibold uppercase tracking-[0.16em]', TEXT_MUTED)}>Blocking surfaces</p>
                  <p className={cn('mt-2 text-xs leading-5', TEXT_SECONDARY)}>
                    {(blockingSurfaces.length ? blockingSurfaces : ['none reported']).join(' / ')}
                  </p>
                </TerminalNestedBlock>
                <TerminalNestedBlock className="min-w-0">
                  <p className={cn('text-[10px] font-semibold uppercase tracking-[0.16em]', TEXT_MUTED)}>Missing families</p>
                  <p className={cn('mt-2 break-words font-mono text-[11px] leading-5', TEXT_SECONDARY)}>
                    {(missingFamilies.length ? missingFamilies : ['none reported']).join(', ')}
                  </p>
                </TerminalNestedBlock>
                <TerminalNestedBlock className="min-w-0">
                  <p className={cn('text-[10px] font-semibold uppercase tracking-[0.16em]', TEXT_MUTED)}>Data classes</p>
                  <p className={cn('mt-2 break-words font-mono text-[11px] leading-5', TEXT_SECONDARY)}>
                    available: {(availableClasses.length ? availableClasses : ['none reported']).join(', ')}
                  </p>
                  <p className={cn('mt-1 break-words font-mono text-[11px] leading-5', TEXT_MUTED)}>
                    missing: {(missingClasses.length ? missingClasses : ['none reported']).join(', ')}
                  </p>
                </TerminalNestedBlock>
              </div>

              <TerminalNestedBlock className="min-w-0">
                <p className={cn('text-[10px] font-semibold uppercase tracking-[0.16em]', TEXT_MUTED)}>Next operator step</p>
                <p className={cn('mt-2 text-xs leading-5', TEXT_SECONDARY)}>{readiness?.nextOperatorAction || 'No operator step reported.'}</p>
                {readiness?.candidateGenerationBlockers?.length ? (
                  <p className={cn('mt-1 break-words font-mono text-[11px] leading-5', TEXT_MUTED)}>
                    blockers: {readiness.candidateGenerationBlockers.join(', ')}
                  </p>
                ) : null}
              </TerminalNestedBlock>

              {refresh ? (
                <TerminalNestedBlock data-testid={`admin-scanner-universe-refresh-${market}`} className="min-w-0 border-[color:color-mix(in_srgb,var(--state-warning-border)_80%,var(--wolfy-border-subtle))]">
                  <div className="flex flex-wrap gap-1.5">
                    <TerminalChip variant={scannerStatusVariant(refresh.status)}>{refresh.status}</TerminalChip>
                    <TerminalChip variant="caution">{refresh.actionStatus}</TerminalChip>
                    {boolChip(refresh.refreshExecuted, 'Refresh executed', 'Refresh deferred', true)}
                  </div>
                  <p className={cn('mt-2 text-xs leading-5', TEXT_SECONDARY)}>{refresh.nextOperatorAction}</p>
                </TerminalNestedBlock>
              ) : null}
            </TerminalPanel>
          );
        })}
      </div>
    </section>
  );
}

function DomainStatusList({ domains }: { domains: AdminOpsCockpitDomain[] }) {
  if (domains.length === 0) return null;

  return (
    <section data-testid="admin-launch-cockpit-domain-grid" className="space-y-3">
      <div className="flex items-center gap-2">
        <FileText className={cn('size-4', TEXT_MUTED)} aria-hidden="true" />
        <h2 className={cn('text-sm font-semibold', TEXT_PRIMARY)}>Domain readiness queue</h2>
      </div>
      <ol className="space-y-2" aria-label="Launch domain readiness">
        {domains.map((domain) => {
          const evidenceRefs = compactItems(domain.evidenceRefs, 2);
          const nextActions = compactItems(domain.safeNextActions, 1);
          const proposals = domain.followUpProposals.slice(0, 1);
          return (
            <li key={domain.domainKey}>
              <article
                data-testid="admin-launch-cockpit-domain-card"
                className={cn(
                  'min-w-0 rounded-lg border px-3 py-3',
                  domain.publicLaunchNoGo
                    ? 'border-[color:color-mix(in_srgb,var(--wolfy-market-down)_30%,var(--wolfy-border-subtle))] bg-[color:color-mix(in_srgb,var(--wolfy-market-down)_5%,var(--wolfy-surface-console))]'
                    : 'border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)]',
                )}
              >
                <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span aria-hidden="true" className={cn('text-xs font-semibold', domain.publicLaunchNoGo ? 'text-[color:var(--wolfy-market-down)]' : TEXT_MUTED)}>
                        {domain.publicLaunchNoGo ? '■' : '○'}
                      </span>
                      <p className={cn('text-[11px] font-semibold uppercase tracking-[0.14em]', TEXT_MUTED)}>{domain.domainKey}</p>
                      <TerminalChip variant={priorityVariant(domain.priorityTier)}>#{domain.priorityRank}</TerminalChip>
                      <TerminalChip variant={priorityVariant(domain.priorityTier)}>{domain.priorityTier}</TerminalChip>
                      <TerminalChip variant={domainStatusVariant(domain)}>
                        {domain.publicLaunchNoGo ? 'NO-GO' : domain.status}
                      </TerminalChip>
                    </div>
                    <h3 className={cn('mt-1.5 text-sm font-semibold', TEXT_PRIMARY)}>{domain.label}</h3>
                    <p className={cn('mt-1 text-xs leading-5', TEXT_SECONDARY)}>{domain.statusLabel}</p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {boolChip(domain.foundationLanded, 'Foundation landed', 'Foundation partial')}
                      {boolChip(domain.evidenceToolingPresent, 'Evidence tooling present', 'Evidence tooling missing')}
                      {boolChip(domain.realOperatorEvidenceMissing, 'Real evidence missing', 'Real evidence present', true)}
                      {boolChip(domain.approvalRequired, 'Manual approval required', 'Approval not required', true)}
                      {boolChip(domain.publicLaunchNoGo, 'Public launch NO-GO', 'Public launch cleared', true)}
                    </div>
                    <p className={cn('mt-2 text-xs leading-5', TEXT_PRIMARY)}>
                      <span className={cn('mr-1 font-medium', TEXT_MUTED)}>Next:</span>
                      {domain.recommendedNextAction}
                    </p>
                    <p className={cn('mt-1 text-[11px] leading-5', TEXT_MUTED)}>{domain.blockingReasonSummary}</p>
                    {evidenceRefs.length ? (
                      <p className={cn('mt-1 break-words font-mono text-[11px] leading-5', TEXT_MUTED)}>
                        Evidence: {evidenceRefs.join(' · ')}
                      </p>
                    ) : null}
                    {nextActions.length ? (
                      <p className={cn('mt-1 text-[11px] leading-5', TEXT_SECONDARY)}>Safe action: {nextActions[0]}</p>
                    ) : null}
                    {proposals.map((proposal) => (
                      <div key={proposal.proposalKey} className={cn('mt-2 rounded-md border border-[color:color-mix(in_srgb,var(--state-warning-border)_70%,var(--wolfy-border-subtle))] px-2.5 py-2 text-xs leading-5', TEXT_SECONDARY)}>
                        <p className={cn('font-medium', TEXT_PRIMARY)}>{proposal.title}</p>
                        <p className="mt-1">Risk: {proposal.risk}</p>
                        {proposal.likelyFiles.slice(0, 2).map((file) => (
                          <p key={file} className={cn('break-words font-mono text-[11px]', TEXT_MUTED)}>{file}</p>
                        ))}
                      </div>
                    ))}
                  </div>
                  <Link
                    to={domain.detailRoute}
                    className="inline-flex min-h-[40px] shrink-0 items-center gap-2 rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 text-xs font-medium text-[color:var(--wolfy-text-secondary)] transition-colors hover:border-[color:var(--wolfy-divider)] hover:text-[color:var(--wolfy-text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--wolfy-accent-focus)]"
                  >
                    <FileText className="size-4" aria-hidden="true" />
                    <span>Open read-only detail</span>
                    <ArrowRight className="size-4" aria-hidden="true" />
                  </Link>
                </div>
              </article>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function MaintenanceQueue({ items }: { items: AdminOpsCockpitMaintenanceQueueItem[] }) {
  if (items.length === 0) {
    return null;
  }

  return (
    <section data-testid="admin-launch-cockpit-maintenance-queue" className="space-y-3">
      <div className="flex items-center gap-2">
        <ShieldAlert className="size-4 text-[color:var(--state-warning-text)]" aria-hidden="true" />
        <h2 className={cn('text-sm font-semibold', TEXT_PRIMARY)}>Recommended maintenance queue</h2>
      </div>
      <ol className="space-y-2" aria-label="Highest severity maintenance queue">
        {items.map((item, index) => (
          <li key={item.domainKey}>
            <article
              data-testid="admin-launch-cockpit-queue-item"
              className={cn(
                'rounded-lg border px-3 py-3',
                item.priorityTier === 'critical'
                  ? 'border-[color:color-mix(in_srgb,var(--wolfy-market-down)_32%,var(--wolfy-border-subtle))] bg-[color:color-mix(in_srgb,var(--wolfy-market-down)_6%,var(--wolfy-surface-console))]'
                  : 'border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)]',
              )}
            >
              <div className="flex flex-wrap items-center gap-1.5">
                <span
                  aria-hidden="true"
                  className={cn(
                    'flex h-6 w-6 items-center justify-center rounded-md border text-[11px] font-semibold',
                    item.priorityTier === 'critical'
                      ? 'border-[color:color-mix(in_srgb,var(--wolfy-market-down)_40%,transparent)] text-[color:var(--wolfy-market-down)]'
                      : 'border-[color:var(--wolfy-border-subtle)] text-[color:var(--wolfy-text-muted)]',
                  )}
                >
                  {index + 1}
                </span>
                <TerminalChip variant={priorityVariant(item.priorityTier)}>#{item.priorityRank}</TerminalChip>
                <TerminalChip variant={priorityVariant(item.priorityTier)}>{item.priorityTier}</TerminalChip>
                <TerminalChip variant="neutral">{item.impactLevel}</TerminalChip>
                {item.priorityTier === 'critical' ? (
                  <TerminalChip variant="danger">
                    <span aria-hidden="true" className="mr-1">■</span>
                    CRITICAL
                  </TerminalChip>
                ) : null}
              </div>
              <h3 className={cn('mt-2 text-sm font-semibold', TEXT_PRIMARY)} data-testid="admin-launch-cockpit-queue-title">
                {item.label}
              </h3>
              <p className={cn('mt-1 text-xs leading-5', TEXT_SECONDARY)}>{item.recommendedNextAction}</p>
              <p className={cn('mt-1 text-[11px] leading-5', TEXT_MUTED)}>{item.blockingReasonSummary}</p>
              <p className={cn('mt-1 font-mono text-[11px] leading-5', TEXT_MUTED)}>
                Owner: {item.ownerSurface} · Route: {item.remediationSurface}
              </p>
            </article>
          </li>
        ))}
      </ol>
    </section>
  );
}

const AdminLaunchCockpitPage: React.FC = () => {
  const [snapshot, setSnapshot] = useState<AdminOpsStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [scannerReadinessByMarket, setScannerReadinessByMarket] = useState<Partial<Record<ScannerMarket, AdminScannerUniverseReadinessResponse>>>({});
  const [scannerReadinessFailed, setScannerReadinessFailed] = useState(false);
  const [refreshResults, setRefreshResults] = useState<Partial<Record<ScannerMarket, AdminScannerUniverseRefreshResponse>>>({});
  const [refreshingMarket, setRefreshingMarket] = useState<ScannerMarket | null>(null);

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

  useEffect(() => {
    let cancelled = false;
    Promise.all(SCANNER_MARKETS.map(async (market) => {
      const payload = await adminOpsStatusApi.getScannerUniverseReadiness(market);
      return [market, payload] as const;
    }))
      .then((entries) => {
        if (!cancelled) {
          setScannerReadinessByMarket(Object.fromEntries(entries) as Record<ScannerMarket, AdminScannerUniverseReadinessResponse>);
          setScannerReadinessFailed(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setScannerReadinessByMarket({});
          setScannerReadinessFailed(true);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const requestScannerRefresh = (market: ScannerMarket) => {
    setRefreshingMarket(market);
    adminOpsStatusApi.requestScannerUniverseRefresh(market)
      .then((payload) => {
        setRefreshResults((current) => ({ ...current, [market]: payload }));
        return adminOpsStatusApi.getScannerUniverseReadiness(market);
      })
      .then((payload) => {
        setScannerReadinessByMarket((current) => ({ ...current, [market]: payload }));
        setScannerReadinessFailed(false);
      })
      .catch(() => {
        setScannerReadinessFailed(true);
      })
      .finally(() => {
        setRefreshingMarket(null);
      });
  };

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
  const publicLaunchBlocked = Boolean(cockpit?.publicLaunchNoGo ?? true);

  return (
    <TerminalPageShell
      data-testid="admin-launch-cockpit-page"
      className="min-h-0 flex-1 overflow-x-hidden py-5 text-[color:var(--wolfy-text-primary)] md:py-6"
    >
      <TerminalPageHeading
        eyebrow="Admin/Ops private beta"
        title="Private Beta Launch Cockpit"
        action={(
          <div className="flex flex-wrap gap-2">
            <TerminalChip variant="danger">
              <span aria-hidden="true" className="mr-1">■</span>
              Public launch NO-GO
            </TerminalChip>
            <TerminalChip variant="info">Read-only advisory</TerminalChip>
            <TerminalChip variant="neutral">No external calls</TerminalChip>
          </div>
        )}
      />

      <p className={cn('max-w-4xl text-sm leading-6', TEXT_MUTED)}>
        Operator view for readiness, evidence, blockers, and safe next actions. It does not approve launch,
        execute validators, change runtime behavior, send notifications, call providers, or run storage actions.
      </p>

      {/* 1. Launch state / NO-GO — dominant operator signal */}
      <TerminalPanel
        data-testid="admin-launch-cockpit-nogo-banner"
        className={cn(
          'space-y-3',
          publicLaunchBlocked
            ? 'border-[color:color-mix(in_srgb,var(--wolfy-market-down)_36%,var(--wolfy-border-subtle))] bg-[color:color-mix(in_srgb,var(--wolfy-market-down)_8%,var(--wolfy-surface-console))]'
            : '',
        )}
      >
        <div className="flex flex-wrap items-start gap-3">
          <Ban className="mt-0.5 size-5 shrink-0 text-[color:var(--wolfy-market-down)]" aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <p className={cn('text-[11px] font-semibold uppercase tracking-[0.16em]', TEXT_MUTED)}>Launch state</p>
            <h2 className={cn('mt-1 text-base font-semibold md:text-lg', TEXT_PRIMARY)}>
              {publicLaunchBlocked ? 'Public launch remains NO-GO' : 'Public launch cleared (advisory)'}
            </h2>
            <p className={cn('mt-1 text-sm leading-6', TEXT_SECONDARY)}>
              {cockpit?.message || 'Public launch remains blocked pending operator evidence.'}
            </p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {boolChip(Boolean(cockpit?.publicLaunchApproved), 'Launch approved', 'Launch not approved', true)}
              {boolChip(Boolean(cockpit?.liveEnforcement), 'Live enforcement on', 'Live enforcement off', true)}
              {boolChip(Boolean(cockpit?.runtimeBehaviorChanged), 'Runtime changed', 'Runtime unchanged', true)}
              <TerminalChip variant="danger">NO-GO domains: {String(counts.publicLaunchNoGoCount ?? 0)}</TerminalChip>
              <TerminalChip variant="caution">Evidence missing: {String(counts.realEvidenceMissingCount ?? 0)}</TerminalChip>
            </div>
          </div>
        </div>
      </TerminalPanel>

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

      {/* 2. Highest severity issues */}
      <section data-testid="admin-launch-cockpit-blockers" className="space-y-3">
        <div className="flex items-center gap-2">
          <ShieldAlert className="size-4 text-[color:var(--wolfy-market-down)]" aria-hidden="true" />
          <h2 className={cn('text-sm font-semibold', TEXT_PRIMARY)}>NO-GO blockers</h2>
        </div>
        <div className="grid gap-3 lg:grid-cols-2">
          {(cockpit?.blockers ?? []).map((blocker) => (
            <TerminalPanel key={blocker.blockerKey} className="space-y-2 border-[color:color-mix(in_srgb,var(--wolfy-market-down)_28%,var(--wolfy-border-subtle))]">
              <div className="flex flex-wrap items-center gap-2">
                <TerminalChip variant="danger">
                  <span aria-hidden="true" className="mr-1">■</span>
                  {blocker.severity}
                </TerminalChip>
                <TerminalChip variant="caution">Approval required</TerminalChip>
              </div>
              <h3 className={cn('text-sm font-semibold', TEXT_PRIMARY)}>{blocker.title}</h3>
              <p className={cn('text-xs leading-5', TEXT_SECONDARY)}>{blocker.nextAction}</p>
              {compactItems(blocker.evidenceRefs, 2).map((item) => (
                <p key={item} className={cn('break-words font-mono text-[11px] leading-5', TEXT_MUTED)}>{item}</p>
              ))}
            </TerminalPanel>
          ))}
        </div>
      </section>

      <MaintenanceQueue items={maintenanceQueue} />

      <TerminalPanel data-testid="admin-launch-cockpit-safety" className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Ban className="size-4 text-[color:var(--wolfy-market-down)]" aria-hidden="true" />
          <p className={cn('text-sm font-semibold', TEXT_PRIMARY)}>Invariant checks</p>
          {boolChip(Boolean(cockpit?.publicLaunchApproved), 'Launch approved', 'Launch not approved', true)}
          {boolChip(Boolean(cockpit?.liveEnforcement), 'Live enforcement on', 'Live enforcement off', true)}
          {boolChip(Boolean(cockpit?.runtimeBehaviorChanged), 'Runtime changed', 'Runtime unchanged', true)}
        </div>
        <div className="grid gap-2 md:grid-cols-3">
          {Object.entries(cockpit?.unsafeActionStates ?? {}).map(([key, value]) => (
            <TerminalNestedBlock key={key} className={cn('min-w-0', value ? 'border-[color:color-mix(in_srgb,var(--wolfy-market-down)_28%,var(--wolfy-border-subtle))]' : '')}>
              <p className={cn('break-words font-mono text-[11px]', TEXT_MUTED)}>{key}</p>
              <div className="mt-2">
                {boolChip(Boolean(value), 'enabled', 'disabled', true)}
              </div>
            </TerminalNestedBlock>
          ))}
        </div>
      </TerminalPanel>

      {/* 3–4. Ownership/domain queue + evidence */}
      <DomainStatusList domains={sortedDomains} />

      <ScannerUniverseReadinessPanel
        readinessByMarket={scannerReadinessByMarket}
        refreshResults={refreshResults}
        refreshingMarket={refreshingMarket}
        onRefresh={requestScannerRefresh}
        loadFailed={scannerReadinessFailed}
      />

      {/* 5. Safe operator next actions */}
      <TerminalPanel className="space-y-2">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="size-4 text-[color:var(--wolfy-market-up)]" aria-hidden="true" />
          <p className={cn('text-sm font-semibold', TEXT_PRIMARY)}>Safe next actions</p>
        </div>
        <div className="grid gap-2 md:grid-cols-3">
          {(cockpit?.safeNextActions ?? []).map((item) => (
            <TerminalNestedBlock key={item} className={cn('text-xs leading-5', TEXT_SECONDARY)}>
              {item}
            </TerminalNestedBlock>
          ))}
        </div>
      </TerminalPanel>
    </TerminalPageShell>
  );
};

export default AdminLaunchCockpitPage;
