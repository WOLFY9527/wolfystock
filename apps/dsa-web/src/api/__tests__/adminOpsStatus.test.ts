import { beforeEach, describe, expect, it, vi } from 'vitest';

const { get, post } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock('../index', () => ({
  default: {
    get,
    post,
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
          recommended_maintenance_queue: [
            {
              domain_key: 'quota_cost',
              label: 'Quota / Cost',
              priority_rank: 1,
              priority_tier: 'critical',
              impact_level: 'critical',
              recommended_next_action: 'Review bounded quota evidence without creating reservations.',
              blocking_reason_summary: 'Live quota enforcement remains approval-gated.',
              owner_surface: 'cost_controls',
              remediation_surface: '/admin/cost-observability',
            },
          ],
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
              priority_rank: 1,
              priority_tier: 'critical',
              impact_level: 'critical',
              recommended_next_action: 'Review bounded quota evidence without creating reservations.',
              blocking_reason_summary: 'Live quota enforcement remains approval-gated.',
              owner_surface: 'cost_controls',
              remediation_surface: '/admin/cost-observability',
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
      priorityRank: 1,
      priorityTier: 'critical',
      impactLevel: 'critical',
      recommendedNextAction: 'Review bounded quota evidence without creating reservations.',
      blockingReasonSummary: 'Live quota enforcement remains approval-gated.',
      ownerSurface: 'cost_controls',
      remediationSurface: '/admin/cost-observability',
    }));
    expect(result.launchCockpit.recommendedMaintenanceQueue[0]).toEqual(expect.objectContaining({
      domainKey: 'quota_cost',
      priorityRank: 1,
      priorityTier: 'critical',
      recommendedNextAction: 'Review bounded quota evidence without creating reservations.',
    }));
    expect(result.launchCockpit.domains[0].followUpProposals[0].approvalNeeded).toBe(true);
    expect(result.launchCockpit.blockers[0].blockerKey).toBe('public_launch_no_go');
  });

  it('maps scanner universe readiness and deferred refresh responses honestly', async () => {
    const { adminOpsStatusApi } = await import('../adminOpsStatus');
    get.mockResolvedValueOnce({
      data: {
        contract_version: 'scanner_universe_operator_readiness_v1',
        status: 'stale',
        scanner_universe_status: 'stale',
        market: 'us',
        profile: 'us_premarket_v1',
        freshness_state: 'stale',
        universe_size: 4,
        affected_product_surfaces: ['Scanner', 'Research Radar', 'Backtest'],
        next_operator_action: 'Refresh the configured scanner universe through the approved operator workflow.',
        scanner_universe_readiness: {
          status: 'stale',
          available_data_classes: ['universe'],
          missing_data_families: ['historical_ohlcv', 'quote_snapshot'],
          missing_data_classes: ['quote_snapshot'],
        },
        candidate_generation_blockers: ['scanner_universe_stale'],
        read_only: true,
        no_external_calls: true,
        mutation_enabled: false,
        provider_calls_enabled: false,
      },
    });
    post.mockResolvedValueOnce({
      data: {
        contract_version: 'scanner_universe_operator_action_v1',
        status: 'manual_action_required',
        action_status: 'deferred',
        market: 'us',
        profile: 'us_premarket_v1',
        refresh_executed: false,
        mutation_enabled: false,
        no_external_calls: true,
        provider_calls_enabled: false,
        runtime_behavior_changed: false,
        next_operator_action: 'Use the approved scanner universe refresh workflow, then rerun this readiness check.',
      },
    });

    const readiness = await adminOpsStatusApi.getScannerUniverseReadiness('us');
    const refresh = await adminOpsStatusApi.requestScannerUniverseRefresh('us');

    expect(get).toHaveBeenCalledWith('/api/v1/admin/ops/scanner-universe-readiness?market=us');
    expect(post).toHaveBeenCalledWith('/api/v1/admin/ops/scanner-universe-refresh?market=us');
    expect(readiness.market).toBe('us');
    expect(readiness.affectedProductSurfaces).toEqual(['Scanner', 'Research Radar', 'Backtest']);
    expect(readiness.scannerUniverseReadiness.missingDataFamilies).toEqual(['historical_ohlcv', 'quote_snapshot']);
    expect(readiness.providerCallsEnabled).toBe(false);
    expect(refresh.status).toBe('manual_action_required');
    expect(refresh.actionStatus).toBe('deferred');
    expect(refresh.refreshExecuted).toBe(false);
    expect(refresh.providerCallsEnabled).toBe(false);
  });
});
