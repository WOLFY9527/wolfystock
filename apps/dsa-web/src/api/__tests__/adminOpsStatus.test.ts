import { beforeEach, describe, expect, it, vi } from 'vitest';

const { get } = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock('../index', () => ({
  default: {
    get,
  },
}));

describe('adminOpsStatusApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('normalizes launch cockpit rows without exposing unsafe defaults', async () => {
    const { adminOpsStatusApi } = await import('../adminOpsStatus');
    get.mockResolvedValueOnce({
      data: {
        generated_at: '2026-06-11T08:00:00',
        read_only: true,
        no_external_calls: true,
        live_enforcement: false,
        launch_cockpit: {
          contract: 'admin_ops_launch_cockpit_v1',
          read_only: true,
          advisory_only: true,
          no_external_calls: true,
          public_launch_approved: false,
          public_launch_no_go: true,
          approval_required: true,
          summary_counts: {
            domain_count: 1,
            public_launch_no_go_count: 1,
            real_evidence_missing_count: 1,
          },
          unsafe_action_states: {
            quota_live_blocking_enabled: false,
            notification_send_enabled: false,
          },
          domains: [
            {
              domain_key: 'quota_cost',
              label: 'Quota / Cost',
              status: 'advisory_no_go',
              status_label: 'Advisory only',
              detail_route: '/admin/cost-observability',
              foundation_landed: true,
              evidence_tooling_present: true,
              real_operator_evidence_missing: true,
              approval_required: true,
              public_launch_no_go: true,
              read_only: true,
              advisory_only: true,
              no_external_calls: true,
              live_enforcement: false,
              evidence_refs: ['scripts/quota_reserve_release_operator_evidence_check.py'],
              blocker_refs: ['docs/audits/public-launch-gap-register.md#costquota'],
              safe_next_actions: ['Review only'],
              limitations: ['live_route_enforcement_missing'],
              follow_up_proposals: [
                {
                  proposal_key: 'quota_route_pilot_approval',
                  title: 'Pilot one route',
                  approval_needed: true,
                  likely_files: ['api/v1/endpoints/analysis.py'],
                  risk: 'spend cap missing',
                  validation: ['quota tests'],
                },
              ],
            },
          ],
          blockers: [
            {
              blocker_key: 'public_launch_no_go',
              title: 'Public launch remains NO-GO',
              severity: 'critical',
              public_launch_no_go: true,
              approval_required: true,
              affected_domains: ['quota_cost'],
              evidence_refs: ['docs/audits/public-launch-readiness-master.md'],
              next_action: 'Collect evidence',
            },
          ],
          safe_next_actions: ['Open detail pages'],
          limitations: ['cockpit_does_not_approve_public_launch'],
        },
      },
    });

    const result = await adminOpsStatusApi.getStatus();

    expect(get).toHaveBeenCalledWith('/api/v1/admin/ops/status');
    expect(result.launchCockpit.publicLaunchApproved).toBe(false);
    expect(result.launchCockpit.publicLaunchNoGo).toBe(true);
    expect(result.launchCockpit.summaryCounts.domainCount).toBe(1);
    expect(result.launchCockpit.unsafeActionStates.quotaLiveBlockingEnabled).toBe(false);
    expect(result.launchCockpit.domains[0]).toEqual(expect.objectContaining({
      domainKey: 'quota_cost',
      detailRoute: '/admin/cost-observability',
      publicLaunchNoGo: true,
      liveEnforcement: false,
      evidenceRefs: ['scripts/quota_reserve_release_operator_evidence_check.py'],
    }));
    expect(result.launchCockpit.domains[0].followUpProposals[0].approvalNeeded).toBe(true);
    expect(result.launchCockpit.blockers[0].blockerKey).toBe('public_launch_no_go');
  });
});
