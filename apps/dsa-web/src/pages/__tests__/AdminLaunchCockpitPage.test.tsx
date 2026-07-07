import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AdminLaunchCockpitPage from '../AdminLaunchCockpitPage';
import type { AdminOpsStatusResponse, AdminOpsStatusSection } from '../../api/adminOpsStatus';

const { getStatus, getScannerUniverseReadiness, requestScannerUniverseRefresh } = vi.hoisted(() => ({
  getStatus: vi.fn(),
  getScannerUniverseReadiness: vi.fn(),
  requestScannerUniverseRefresh: vi.fn(),
}));

vi.mock('../../api/adminOpsStatus', () => ({
  adminOpsStatusApi: {
    getStatus,
    getScannerUniverseReadiness,
    requestScannerUniverseRefresh,
  },
}));

const forbiddenVisibleCopy =
  /raw-owner-user-id|raw-session-id|provider_payload|raw_payload|request_body|response_body|access-token|authorization|bearer|cookie|api_key|secret|credential|traceback|https:\/\/|\?token=|reserve_quota|consume_reservation|release_reservation/i;

function statusSection(
  service: string,
  status: string,
  message: string,
  overrides: Partial<AdminOpsStatusSection> = {},
): AdminOpsStatusSection {
  return {
    available: status !== 'unavailable',
    status,
    service,
    configured: status !== 'unavailable',
    lastCheckedAt: status === 'unavailable' ? null : '2026-06-11T08:00:00',
    message,
    label: 'bounded_admin_diagnostic',
    reasonCode: null,
    readOnly: true,
    noExternalCalls: true,
    advisoryOnly: true,
    liveEnforcement: false,
    enforcementEnabled: false,
    runtimeBehaviorChanged: false,
    consumerVisible: false,
    providerBehaviorChanged: false,
    marketCacheBehaviorChanged: false,
    deleteAllowed: false,
    dataSources: [],
    summary: {},
    limitations: [],
    ...overrides,
  };
}

function statusFixture(): AdminOpsStatusResponse {
  return {
    generatedAt: '2026-06-11T08:00:00',
    readOnly: true,
    noExternalCalls: true,
    liveEnforcement: false,
    runtimeBehaviorChanged: false,
    consumerVisible: false,
    advisoryVsEnforcement: {
      label: 'advisory_snapshot',
      enforcementLabel: 'not_launch_control',
      sourceUnavailableBehavior: 'degrade_to_unavailable',
      readOnly: true,
      noExternalCalls: true,
      liveEnforcement: false,
      runtimeBehaviorChanged: false,
      consumerVisible: false,
    },
    providerStatusSummary: statusSection('provider_reliability', 'degraded', 'Provider reliability requires operator evidence review'),
    quotaCostAdvisoryStatusSummary: statusSection('quota_cost', 'blocked', 'Quota controls remain advisory and approval-gated'),
    storageReadinessSummary: statusSection('storage', 'ok', 'Storage readiness evidence is available'),
    taskQueueStatusSummary: statusSection('task_queue', 'ok', 'Task queue accepts bounded local work'),
    adminLogEvidenceSummary: statusSection('admin_logs', 'ok', 'Admin log evidence is available'),
    runtimeLogSinkSummary: statusSection('runtime_log_sink', 'degraded', 'Runtime log sink requires retention review'),
    retentionPolicyStatus: statusSection('retention_policy', 'blocked', 'Retention policy requires operator review'),
    executionLogRetentionRisk: statusSection('execution_log_retention', 'unavailable', 'Execution log retention evidence unavailable'),
    dbSizeRisk: statusSection('db_size', 'ok', 'Database size within bounded threshold'),
    adminRoleAssignmentStatus: statusSection('admin_role_assignment', 'degraded', 'Admin role assignment needs staged evidence'),
    durableTaskBacklogStatus: statusSection('durable_task_backlog', 'ok', 'Durable task backlog within threshold'),
    recommendedMaintenanceActions: ['Review sanitized admin launch evidence'],
    buildProvenance: {
      contract: 'admin_build_provenance_v1',
      readOnly: true,
      noExternalCalls: true,
      runtimeBehaviorChanged: false,
      consumerVisible: false,
      backendGitSha: '69068d1',
      backendBranch: 'codex/t227-adminops-contract-alignment',
      backendCommitTimestamp: null,
      backendRuntimeStartedAt: null,
      frontendMainAssetFilename: null,
      frontendMainAssetHash: null,
      frontendAssetManifestHash: null,
      frontendAssetManifestSource: null,
      frontendStaticBuildTimestamp: null,
      staticAssetMode: 'unknown',
      staticAssetRootProvenance: 'unknown',
      staticAssetRootLabel: null,
      staticAssetRootExists: false,
      staticIndexPresent: false,
      freshnessStatus: 'unknown',
      comparisonBasis: null,
      stale: null,
      reasonCodes: ['frontend_build_not_checked'],
    },
    launchCockpit: {
      contract: 'admin_ops_launch_cockpit_v1',
      status: 'blocked',
      lastCheckedAt: '2026-06-11T08:00:00',
      message: 'Public launch remains blocked pending operator evidence',
      readOnly: true,
      advisoryOnly: true,
      noExternalCalls: true,
      publicLaunchApproved: false,
      publicLaunchNoGo: true,
      liveEnforcement: false,
      runtimeBehaviorChanged: false,
      approvalRequired: true,
      summaryCounts: {
        domainCount: 2,
        foundationLandedCount: 2,
        evidenceToolingPresentCount: 2,
        realEvidenceMissingCount: 1,
        approvalRequiredCount: 2,
        publicLaunchNoGoCount: 2,
        blockerCount: 1,
      },
      unsafeActionStates: {
        quotaLiveBlockingEnabled: false,
        providerCircuitBlockingEnabled: false,
        notificationSendEnabled: false,
      },
      recommendedMaintenanceQueue: [
        {
          domainKey: 'security_rbac_mfa',
          label: 'Security / RBAC / MFA',
          priorityRank: 1,
          priorityTier: 'critical',
          impactLevel: 'critical',
          recommendedNextAction: 'Review sanitized MFA/RBAC operator evidence before changing access posture.',
          blockingReasonSummary: 'Staged operator evidence is missing for the access-control launch gate.',
          ownerSurface: 'security_access_control',
          remediationSurface: '/admin/users',
        },
        {
          domainKey: 'quota_cost',
          label: 'Quota / Cost',
          priorityRank: 2,
          priorityTier: 'critical',
          impactLevel: 'critical',
          recommendedNextAction: 'Inspect cost observability and quota evidence without creating reservations.',
          blockingReasonSummary: 'Quota enforcement remains approval-gated and real operator evidence is incomplete.',
          ownerSurface: 'cost_controls',
          remediationSurface: '/admin/cost-observability',
        },
      ],
      domains: [
        {
          domainKey: 'quota_cost',
          label: 'Quota / Cost',
          status: 'advisory_no_go',
          statusLabel: 'Advisory helpers present; live quota enforcement not approved',
          detailRoute: '/admin/cost-observability',
          foundationLanded: true,
          evidenceToolingPresent: true,
          realOperatorEvidenceMissing: false,
          approvalRequired: true,
          publicLaunchNoGo: true,
          readOnly: true,
          advisoryOnly: true,
          noExternalCalls: true,
          liveEnforcement: false,
          runtimeBehaviorChanged: false,
          providerRuntimeChanged: false,
          externalActionsEnabled: false,
          evidenceRefs: ['scripts/quota_reserve_release_operator_evidence_check.py'],
          blockerRefs: ['docs/audits/public-launch-gap-register.md#costquota'],
          safeNextActions: ['Inspect cost observability and quota evidence without creating reservations.'],
          limitations: ['live_route_enforcement_missing'],
          priorityRank: 2,
          priorityTier: 'critical',
          impactLevel: 'critical',
          recommendedNextAction: 'Inspect cost observability and quota evidence without creating reservations.',
          blockingReasonSummary: 'Quota enforcement remains approval-gated and real operator evidence is incomplete.',
          ownerSurface: 'cost_controls',
          remediationSurface: '/admin/cost-observability',
          followUpProposals: [
            {
              proposalKey: 'quota_route_pilot_approval',
              title: 'Pilot one low-risk quota route only after explicit approval',
              approvalNeeded: true,
              likelyFiles: ['api/v1/endpoints/analysis.py'],
              risk: 'public_usage_without_hard_spend_caps',
              validation: ['reserve/release lifecycle tests'],
            },
          ],
        },
        {
          domainKey: 'security_rbac_mfa',
          label: 'Security / RBAC / MFA',
          status: 'approval_required_no_go',
          statusLabel: 'Foundation and tooling present; staged operator evidence missing',
          detailRoute: '/admin/users',
          foundationLanded: true,
          evidenceToolingPresent: true,
          realOperatorEvidenceMissing: true,
          approvalRequired: true,
          publicLaunchNoGo: true,
          readOnly: true,
          advisoryOnly: true,
          noExternalCalls: true,
          liveEnforcement: false,
          runtimeBehaviorChanged: false,
          providerRuntimeChanged: false,
          externalActionsEnabled: false,
          evidenceRefs: ['scripts/security_mfa_operator_evidence_check.py'],
          blockerRefs: ['docs/audits/public-launch-gap-register.md#securityrbac'],
          safeNextActions: ['Review route inventory and sanitized MFA/RBAC operator evidence.'],
          limitations: ['real_staged_mfa_pilot_evidence_missing'],
          priorityRank: 1,
          priorityTier: 'critical',
          impactLevel: 'critical',
          recommendedNextAction: 'Review sanitized MFA/RBAC operator evidence before changing access posture.',
          blockingReasonSummary: 'Staged operator evidence is missing for the access-control launch gate.',
          ownerSurface: 'security_access_control',
          remediationSurface: '/admin/users',
          followUpProposals: [],
        },
      ],
      blockers: [
        {
          blockerKey: 'public_launch_no_go',
          title: 'Public launch remains NO-GO',
          severity: 'critical',
          publicLaunchNoGo: true,
          approvalRequired: true,
          affectedDomains: ['security_rbac_mfa', 'quota_cost'],
          evidenceRefs: ['docs/audits/public-launch-readiness-master.md'],
          nextAction: 'Collect missing real operator evidence and complete manual release review outside cockpit.',
        },
      ],
      safeNextActions: ['Open domain detail pages for read-only evidence review.'],
      limitations: ['cockpit_does_not_approve_public_launch'],
      prioritySummary: {
        criticalPriorityCount: 2,
        highPriorityCount: 0,
        mediumPriorityCount: 0,
        watchPriorityCount: 0,
      },
    },
  };
}

function scannerReadinessFixture(market: 'us' | 'cn', status = 'stale') {
  return {
    contractVersion: 'scanner_universe_operator_readiness_v1',
    status,
    scannerUniverseStatus: status,
    market,
    profile: market === 'us' ? 'us_premarket_v1' : 'cn_preopen_v1',
    universeVersion: market === 'us' ? 'scanner-universe-us-20260620' : 'scanner-universe-cn-20260620',
    generatedAt: '2026-06-20T00:01:00+00:00',
    asOf: '2026-06-20',
    sourceClass: market === 'us' ? 'local_bounded_us_parquet_universe' : 'scanner_universe_lifecycle_active',
    symbolCount: market === 'us' ? 4 : 300,
    freshnessState: market === 'us' ? 'stale' : 'universe_modified:2026-06-20',
    age: { days: 17 },
    minimumCoverageThreshold: market === 'us' ? 100 : 300,
    coverageState: status === 'available' ? 'sufficient' : 'below_threshold',
    usable: status === 'available',
    blockingReasons: ['scanner_universe_stale'],
    downstreamImpact: {
      scanner: 'blocked',
      researchRadar: 'blocked',
      backtest: 'degraded',
    },
    lastSuccessfulActivation: 'scanner-universe-20260601',
    lastRejectedImportReason: null,
    lastUpdatedAt: '2026-06-20T00:00:00+00:00',
    universeSize: market === 'us' ? 4 : 300,
    affectedProductSurfaces: ['Scanner', 'Research Radar', 'Backtest'],
    nextOperatorAction: 'Refresh the configured scanner universe through the approved operator workflow.',
    scannerUniverseReadiness: {
      status,
      availableDataClasses: ['universe'],
      missingDataFamilies: ['historical_ohlcv', 'quote_snapshot'],
      missingDataClasses: ['quote_snapshot'],
      blockedProductSurfaces: ['Scanner', 'Research Radar'],
    },
    candidateGenerationState: 'blocked',
    candidateGenerationBlockers: ['scanner_universe_stale'],
    readOnly: true,
    noExternalCalls: true,
    mutationEnabled: false,
    providerCallsEnabled: false,
    consumerVisible: false,
  };
}

function scannerRefreshFixture(market: 'us' | 'cn') {
  return {
    contractVersion: 'scanner_universe_operator_action_v1',
    status: 'manual_action_required',
    actionStatus: 'deferred',
    market,
    profile: market === 'us' ? 'us_premarket_v1' : 'cn_preopen_v1',
    refreshExecuted: false,
    mutationEnabled: false,
    noExternalCalls: true,
    providerCallsEnabled: false,
    runtimeBehaviorChanged: false,
    nextOperatorAction: 'Use the approved scanner universe refresh workflow, then rerun this readiness check.',
    before: {},
    after: {},
  };
}

describe('AdminLaunchCockpitPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getScannerUniverseReadiness.mockImplementation((market: 'us' | 'cn') => Promise.resolve(scannerReadinessFixture(market)));
    requestScannerUniverseRefresh.mockImplementation((market: 'us' | 'cn') => Promise.resolve(scannerRefreshFixture(market)));
  });

  it('renders a read-only private beta cockpit with NO-GO and evidence states first', async () => {
    getStatus.mockResolvedValueOnce(statusFixture());

    render(
      <MemoryRouter initialEntries={['/admin/launch-cockpit']}>
        <AdminLaunchCockpitPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole('heading', { name: 'Private Beta Launch Cockpit' })).toBeInTheDocument();
    const page = screen.getByTestId('admin-launch-cockpit-page');
    const l0 = screen.getByTestId('admin-launch-cockpit-l0-overview-strip');
    const domainGrid = screen.getByTestId('admin-launch-cockpit-domain-grid');
    const blockerPanel = screen.getByTestId('admin-launch-cockpit-blockers');

    expect(within(l0).getByText('Blocked')).toBeInTheDocument();
    expect(page).toHaveTextContent('Public launch NO-GO');
    expect(page).toHaveTextContent('Read-only advisory');
    expect(page).toHaveTextContent('No external calls');
    expect(page).toHaveTextContent('Approval required');
    expect(page).toHaveTextContent('Security / RBAC / MFA');
    expect(page).toHaveTextContent('Quota / Cost');
    expect(within(domainGrid).getAllByTestId('admin-launch-cockpit-domain-card')).toHaveLength(2);
    const cards = within(domainGrid).getAllByTestId('admin-launch-cockpit-domain-card');
    expect(cards[0]).toHaveTextContent('#1');
    expect(cards[0]).toHaveTextContent('Security / RBAC / MFA');
    expect(cards[0]).toHaveTextContent('Review sanitized MFA/RBAC operator evidence before changing access posture.');
    expect(cards[1]).toHaveTextContent('#2');
    expect(cards[1]).toHaveTextContent('Quota / Cost');
    const queue = screen.getByTestId('admin-launch-cockpit-maintenance-queue');
    expect(within(queue).getAllByTestId('admin-launch-cockpit-queue-item')[0]).toHaveTextContent('Security / RBAC / MFA');
    expect(within(queue).getAllByTestId('admin-launch-cockpit-queue-item')[1]).toHaveTextContent('Quota / Cost');
    expect(within(blockerPanel).getByText('Public launch remains NO-GO')).toBeInTheDocument();
    expect(page).toHaveTextContent('Foundation landed');
    expect(page).toHaveTextContent('Evidence tooling present');
    expect(page).toHaveTextContent('Real evidence missing');
    expect(page).toHaveTextContent('Manual approval required');
    expect(page).toHaveTextContent('scripts/security_mfa_operator_evidence_check.py');
    expect(page).toHaveTextContent('api/v1/endpoints/analysis.py');
    const scannerPanel = await screen.findByTestId('admin-scanner-universe-panel');
    expect(scannerPanel).toHaveTextContent('Scanner universe readiness');
    expect(within(scannerPanel).getByTestId('admin-scanner-universe-us')).toHaveTextContent('US scanner universe');
    expect(within(scannerPanel).getByTestId('admin-scanner-universe-us')).toHaveTextContent('Research Radar');
    expect(within(scannerPanel).getByTestId('admin-scanner-universe-us')).toHaveTextContent('historical_ohlcv, quote_snapshot');
    expect(within(scannerPanel).getByTestId('admin-scanner-universe-cn')).toHaveTextContent('CN scanner universe');
    expect(within(scannerPanel).getByTestId('admin-scanner-universe-cn')).toHaveTextContent('quote_snapshot');
    expect(page).not.toHaveTextContent(forbiddenVisibleCopy);
  });

  it('shows the scanner universe refresh result as deferred manual action', async () => {
    getStatus.mockResolvedValueOnce(statusFixture());

    render(
      <MemoryRouter initialEntries={['/admin/launch-cockpit']}>
        <AdminLaunchCockpitPage />
      </MemoryRouter>,
    );

    const usPanel = await screen.findByTestId('admin-scanner-universe-us');
    fireEvent.click(within(usPanel).getByRole('button', { name: 'Request US scanner universe refresh' }));

    const refreshResult = await screen.findByTestId('admin-scanner-universe-refresh-us');
    expect(requestScannerUniverseRefresh).toHaveBeenCalledWith('us');
    expect(refreshResult).toHaveTextContent('manual_action_required');
    expect(refreshResult).toHaveTextContent('deferred');
    expect(refreshResult).toHaveTextContent('Refresh deferred');
    expect(refreshResult).toHaveTextContent('approved scanner universe refresh workflow');
  });

  it('keeps the cockpit advisory when the API source is unavailable', async () => {
    getStatus.mockRejectedValueOnce(new Error('raw-session-id access-token provider_payload traceback'));

    render(
      <MemoryRouter initialEntries={['/admin/launch-cockpit']}>
        <AdminLaunchCockpitPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('admin-launch-cockpit-error')).toBeInTheDocument();
    });
    expect(screen.getByTestId('admin-launch-cockpit-page')).toHaveTextContent('Unable to load cockpit snapshot');
    expect(screen.getByTestId('admin-launch-cockpit-page')).not.toHaveTextContent(forbiddenVisibleCopy);
  });
});
