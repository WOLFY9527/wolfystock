import { beforeEach, describe, expect, expectTypeOf, it, vi } from 'vitest';
import type {
  AdminBuildProvenance,
  AdminOpsLaunchCockpit,
  AdminOpsStatusResponse,
  AdminOpsStatusSection,
  AdminScannerUniverseReadinessResponse,
} from '../adminOpsStatus';

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
        runtime_log_sink_summary: {
          available: true,
          status: 'degraded',
          service: 'runtime_log_sink',
          configured: true,
          last_checked_at: '2026-06-11T08:00:00',
          message: 'File sink active with retention review pending',
          label: 'bounded_admin_diagnostic',
          read_only: true,
          no_external_calls: true,
          advisory_only: true,
          live_enforcement: false,
          enforcement_enabled: false,
          runtime_behavior_changed: false,
          consumer_visible: false,
          provider_behavior_changed: false,
          market_cache_behavior_changed: false,
          delete_allowed: false,
          data_sources: [],
          summary: {},
          limitations: ['retention_review_pending'],
        },
        retention_policy_status: {
          available: true,
          status: 'blocked',
          service: 'retention_policy',
          configured: false,
          last_checked_at: null,
          message: 'Retention policy requires operator review',
          label: 'bounded_admin_diagnostic',
          read_only: true,
          no_external_calls: true,
          advisory_only: true,
          live_enforcement: false,
          enforcement_enabled: false,
          runtime_behavior_changed: false,
          consumer_visible: false,
          provider_behavior_changed: false,
          market_cache_behavior_changed: false,
          delete_allowed: false,
          data_sources: [],
          summary: {},
          limitations: ['manual_review_required'],
        },
        execution_log_retention_risk: {
          available: false,
          status: 'unavailable',
          service: 'execution_log_retention',
          configured: false,
          last_checked_at: null,
          message: 'Execution log retention evidence unavailable',
          label: 'bounded_admin_diagnostic',
          read_only: true,
          no_external_calls: true,
          advisory_only: true,
          live_enforcement: false,
          enforcement_enabled: false,
          runtime_behavior_changed: false,
          consumer_visible: false,
          provider_behavior_changed: false,
          market_cache_behavior_changed: false,
          delete_allowed: false,
          data_sources: [],
          summary: {},
          limitations: ['missing_evidence'],
        },
        db_size_risk: {
          available: true,
          status: 'ok',
          service: 'db_size',
          configured: true,
          last_checked_at: '2026-06-11T08:00:00',
          message: 'Database size within bounded operator threshold',
          label: 'bounded_admin_diagnostic',
          read_only: true,
          no_external_calls: true,
          advisory_only: true,
          live_enforcement: false,
          enforcement_enabled: false,
          runtime_behavior_changed: false,
          consumer_visible: false,
          provider_behavior_changed: false,
          market_cache_behavior_changed: false,
          delete_allowed: false,
          data_sources: [],
          summary: {},
          limitations: [],
        },
        admin_role_assignment_status: {
          available: true,
          status: 'degraded',
          service: 'admin_role_assignment',
          configured: true,
          last_checked_at: '2026-06-11T08:00:00',
          message: 'Admin role assignment needs staged evidence review',
          label: 'bounded_admin_diagnostic',
          read_only: true,
          no_external_calls: true,
          advisory_only: true,
          live_enforcement: false,
          enforcement_enabled: false,
          runtime_behavior_changed: false,
          consumer_visible: false,
          provider_behavior_changed: false,
          market_cache_behavior_changed: false,
          delete_allowed: false,
          data_sources: [],
          summary: {},
          limitations: ['staged_evidence_pending'],
        },
        durable_task_backlog_status: {
          available: true,
          status: 'ok',
          service: 'durable_task_backlog',
          configured: true,
          last_checked_at: '2026-06-11T08:00:00',
          message: 'Durable task backlog within operator threshold',
          label: 'bounded_admin_diagnostic',
          read_only: true,
          no_external_calls: true,
          advisory_only: true,
          live_enforcement: false,
          enforcement_enabled: false,
          runtime_behavior_changed: false,
          consumer_visible: false,
          provider_behavior_changed: false,
          market_cache_behavior_changed: false,
          delete_allowed: false,
          data_sources: [],
          summary: {},
          limitations: [],
        },
        recommended_maintenance_actions: ['Review retention policy evidence'],
        build_provenance: {
          contract: 'admin_build_provenance_v1',
          read_only: true,
          no_external_calls: true,
          runtime_behavior_changed: false,
          consumer_visible: false,
          backend_git_sha: '69068d1',
          backend_branch: 'codex/t227-adminops-contract-alignment',
          freshness_status: 'unknown',
          reason_codes: ['frontend_build_not_checked'],
        },
        launch_cockpit: {
          contract: 'admin_ops_launch_cockpit_v1',
          status: 'blocked',
          last_checked_at: '2026-06-11T08:00:00',
          message: 'Public launch remains blocked pending operator evidence',
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
    expectTypeOf<AdminOpsStatusResponse['providerStatusSummary']>().toEqualTypeOf<AdminOpsStatusSection>();
    expectTypeOf<AdminOpsStatusResponse['runtimeLogSinkSummary']>().toEqualTypeOf<AdminOpsStatusSection>();
    expectTypeOf<AdminOpsStatusResponse['buildProvenance']>().toEqualTypeOf<AdminBuildProvenance>();
    expectTypeOf<AdminOpsLaunchCockpit['status']>().toEqualTypeOf<string>();
    expect(result.runtimeLogSinkSummary.status).toBe('degraded');
    expect(result.retentionPolicyStatus.status).toBe('blocked');
    expect(result.executionLogRetentionRisk.status).toBe('unavailable');
    expect(result.recommendedMaintenanceActions).toEqual(['Review retention policy evidence']);
    expect(result.buildProvenance.freshnessStatus).toBe('unknown');
    expect(result.launchCockpit.status).toBe('blocked');
    expect(result.launchCockpit.message).toBe('Public launch remains blocked pending operator evidence');
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
        universe_version: 'scanner-universe-us-20260620',
        generated_at: '2026-06-20T00:01:00+00:00',
        as_of: '2026-06-20',
        source_class: 'local_bounded_us_parquet_universe',
        symbol_count: 4,
        freshness_state: 'stale',
        age: { days: 17 },
        minimum_coverage_threshold: 100,
        coverage_state: 'below_threshold',
        usable: false,
        blocking_reasons: ['scanner_universe_stale', 'below_minimum_coverage'],
        downstream_impact: {
          scanner: 'blocked',
          research_radar: 'blocked',
          backtest: 'degraded',
        },
        last_successful_activation: 'scanner-universe-us-20260601',
        last_rejected_import_reason: 'below_minimum_coverage',
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
    expect(get).not.toHaveBeenCalledWith(expect.stringContaining('/api/v1/admin/scanner/universe-readiness'));
    expect(post).not.toHaveBeenCalledWith(expect.stringContaining('/api/v1/admin/scanner/universe-refresh'));
    expectTypeOf<AdminScannerUniverseReadinessResponse['sourceClass']>().toEqualTypeOf<string | null>();
    expectTypeOf<AdminScannerUniverseReadinessResponse['blockingReasons']>().toEqualTypeOf<string[]>();
    expect(readiness.market).toBe('us');
    expect(readiness.generatedAt).toBe('2026-06-20T00:01:00+00:00');
    expect(readiness.asOf).toBe('2026-06-20');
    expect(readiness.sourceClass).toBe('local_bounded_us_parquet_universe');
    expect(readiness.symbolCount).toBe(4);
    expect(readiness.coverageState).toBe('below_threshold');
    expect(readiness.blockingReasons).toEqual(['scanner_universe_stale', 'below_minimum_coverage']);
    expect(readiness.downstreamImpact).toEqual({
      scanner: 'blocked',
      researchRadar: 'blocked',
      backtest: 'degraded',
    });
    expect(readiness.lastRejectedImportReason).toBe('below_minimum_coverage');
    expect(readiness.affectedProductSurfaces).toEqual(['Scanner', 'Research Radar', 'Backtest']);
    expect(readiness.scannerUniverseReadiness.missingDataFamilies).toEqual(['historical_ohlcv', 'quote_snapshot']);
    expect(readiness.providerCallsEnabled).toBe(false);
    expect(refresh.status).toBe('manual_action_required');
    expect(refresh.actionStatus).toBe('deferred');
    expect(refresh.refreshExecuted).toBe(false);
    expect(refresh.providerCallsEnabled).toBe(false);
  });
});
