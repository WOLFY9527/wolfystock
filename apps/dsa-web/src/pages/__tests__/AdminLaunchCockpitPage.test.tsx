import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AdminLaunchCockpitPage from '../AdminLaunchCockpitPage';
import type { AdminOpsStatusResponse } from '../../api/adminOpsStatus';

const { getStatus } = vi.hoisted(() => ({
  getStatus: vi.fn(),
}));

vi.mock('../../api/adminOpsStatus', () => ({
  adminOpsStatusApi: {
    getStatus,
  },
}));

const forbiddenVisibleCopy =
  /raw-owner-user-id|raw-session-id|provider_payload|raw_payload|request_body|response_body|access-token|authorization|bearer|cookie|api_key|secret|credential|traceback|https:\/\/|\?token=|reserve_quota|consume_reservation|release_reservation/i;

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
    launchCockpit: {
      contract: 'admin_ops_launch_cockpit_v1',
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
      domains: [
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
          followUpProposals: [],
        },
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
    },
  };
}

describe('AdminLaunchCockpitPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
    expect(within(blockerPanel).getByText('Public launch remains NO-GO')).toBeInTheDocument();
    expect(page).toHaveTextContent('Foundation landed');
    expect(page).toHaveTextContent('Evidence tooling present');
    expect(page).toHaveTextContent('Real evidence missing');
    expect(page).toHaveTextContent('Manual approval required');
    expect(page).toHaveTextContent('scripts/security_mfa_operator_evidence_check.py');
    expect(page).toHaveTextContent('api/v1/endpoints/analysis.py');
    expect(page).not.toHaveTextContent(forbiddenVisibleCopy);
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
