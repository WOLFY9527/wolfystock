import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AdminMissionControlPage from '../AdminMissionControlPage';

const { getSnapshot, capabilityState } = vi.hoisted(() => ({
  getSnapshot: vi.fn(),
  capabilityState: { canReadOpsLogs: true },
}));

vi.mock('../../api/adminMissionControl', () => ({
  adminMissionControlApi: {
    getSnapshot,
  },
}));

vi.mock('../../hooks/useProductSurface', () => ({
  useProductSurface: () => capabilityState,
}));

const domains = [
  ['security_rbac_mfa', 'Security / RBAC / MFA'],
  ['quota_cost', 'Quota / Cost'],
  ['provider_reliability', 'Provider Reliability'],
  ['storage_restore', 'Storage / Restore'],
  ['ws2_async', 'WS2 / Async'],
  ['notifications', 'Notifications'],
  ['portfolio_backtest', 'Portfolio / Backtest'],
  ['route_classification', 'Route Classification'],
  ['private_beta_readiness', 'Private-beta Readiness'],
].map(([id, title]) => ({
  id,
  title,
  status: 'no_go',
  statusLabel: 'requires operator evidence',
  summary: `${title} is visible as a sanitized readiness slice.`,
  posture: {
    landedFoundation: true,
    evidenceToolingExists: true,
    realOperatorEvidenceMissing: true,
    approvalRequired: true,
    publicLaunchNoGo: true,
  },
  readOnly: true,
  noExternalCalls: true,
  liveEnforcement: false,
  runtimeBehaviorChanged: false,
  dataSources: ['safe_summary'],
  evidenceRefs: [{ kind: 'doc', label: `${title} evidence`, ref: 'docs/operations/release.md' }],
  blockerRefs: [{ kind: 'doc', label: 'Release blockers', ref: 'docs/operations/release.md#highest-risk-blockers' }],
  approvalRefs: [{ kind: 'script', label: 'Manual review', ref: 'scripts/manual_release_approval_evidence_check.py' }],
  linkedAdminRoutes: ['/admin/evidence-workflow'],
  opsStatus: null,
  limitations: ['read_only'],
}));

const payload = {
  generatedAt: '2026-06-11T10:20:00+08:00',
  readOnly: true,
  noExternalCalls: true,
  liveEnforcement: false,
  runtimeBehaviorChanged: false,
  publicLaunchApproved: false,
  releaseApproved: false,
  launchVerdict: 'NO_GO',
  prototypeGate: {
    enabled: true,
    status: 'enabled',
    reasonCode: null,
    featureFlag: 'WOLFYSTOCK_ADMIN_MISSION_CONTROL_PROTOTYPE_ENABLED',
    readOnly: true,
    advisoryOnly: true,
    noExternalCalls: true,
    liveEnforcement: false,
  },
  opsSnapshotAvailable: true,
  summary: {
    domainCount: 9,
    landedFoundationCount: 9,
    evidenceToolingCount: 9,
    realOperatorEvidenceMissingCount: 9,
    approvalRequiredCount: 9,
    publicLaunchNoGoCount: 9,
  },
  domains,
  postureLegend: {},
  metadata: {
    mutationPaths: [],
    externalCallsMade: false,
  },
};

function renderPage() {
  return render(
    <MemoryRouter>
      <AdminMissionControlPage />
    </MemoryRouter>,
  );
}

describe('AdminMissionControlPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    capabilityState.canReadOpsLogs = true;
    getSnapshot.mockResolvedValue(payload);
  });

  it('fails closed without ops log capability and does not fetch mission control data', () => {
    capabilityState.canReadOpsLogs = false;

    renderPage();

    expect(screen.getByTestId('admin-mission-capability-denied')).toBeInTheDocument();
    expect(getSnapshot).not.toHaveBeenCalled();
  });

  it('renders the mission control readiness overview for all required domains', async () => {
    renderPage();

    expect(await screen.findByText('运维任务总控')).toBeInTheDocument();
    expect(getSnapshot).toHaveBeenCalledTimes(1);
    const overview = screen.getByTestId('admin-mission-l0-overview-strip');
    expect(within(overview).getByText('阻断')).toBeInTheDocument();
    expect(within(overview).getByText('admin_mission_control_v1')).toBeInTheDocument();

    const grid = screen.getByTestId('admin-mission-domain-grid');
    expect(within(grid).getAllByTestId('admin-mission-domain-card')).toHaveLength(9);
    domains.forEach((domain) => {
      expect(within(grid).getByText(domain.title)).toBeInTheDocument();
    });
  });

  it('surfaces operator state before domain diagnostics', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId('admin-mission-primary-state')).toHaveTextContent(/NO-GO/);
    });

    const stateBand = screen.getByTestId('admin-mission-state-band');
    const domainSection = screen.getByTestId('admin-mission-domain-section');
    const stateTop = stateBand.getBoundingClientRect().top;
    const domainTop = domainSection.getBoundingClientRect().top;
    expect(stateTop).toBeLessThanOrEqual(domainTop);

    expect(within(stateBand).getByTestId('admin-mission-primary-state')).toHaveTextContent(/NO-GO/);
    expect(within(stateBand).getByTestId('admin-mission-ownership')).toBeInTheDocument();
    expect(within(stateBand).getByTestId('admin-mission-evidence-availability')).toBeInTheDocument();
    expect(within(stateBand).getByTestId('admin-mission-primary-action-link')).toHaveAttribute(
      'href',
      '/zh/admin/evidence-workflow?ref=mission_control',
    );
  });

  it('separates foundation, evidence tooling, missing evidence, approval, and NO-GO labels', async () => {
    renderPage();

    const firstCard = (await screen.findAllByTestId('admin-mission-domain-card'))[0];
    expect(within(firstCard).getByText('基础已落地')).toBeInTheDocument();
    expect(within(firstCard).getByText('证据工具存在')).toBeInTheDocument();
    expect(within(firstCard).getByText('缺真实证据')).toBeInTheDocument();
    expect(within(firstCard).getByText('需要审批')).toBeInTheDocument();
    expect(within(firstCard).getByText('NO-GO')).toBeInTheDocument();
  });

  it('shows read-only system posture without mutation or approval controls', async () => {
    renderPage();

    const metrics = await screen.findByTestId('admin-mission-summary-metrics');
    expect(within(metrics).getByText('覆盖域')).toBeInTheDocument();
    expect(within(metrics).getByText('目标 9 个')).toBeInTheDocument();
    expect(screen.getByText('数据只读')).toBeInTheDocument();
    expect(screen.getByText('无外部调用')).toBeInTheDocument();
    expect(screen.getByText('无 live enforcement')).toBeInTheDocument();
    expect(screen.getByText('releaseApproved=false')).toBeInTheDocument();
    expect(screen.getByText(/本页不会批准 public launch/)).toBeInTheDocument();
    expect(document.querySelector('form')).not.toBeInTheDocument();
    expect(document.querySelector('input, textarea, select, [contenteditable="true"]')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /approve|批准|提交|保存|send|发送|cleanup|restore|migration/i })).not.toBeInTheDocument();
  });

  it('shows a bounded disabled prototype state without readiness domains', async () => {
    getSnapshot.mockResolvedValueOnce({
      ...payload,
      prototypeGate: {
        enabled: false,
        status: 'disabled',
        reasonCode: 'prototype_gate_disabled_by_default',
        featureFlag: 'WOLFYSTOCK_ADMIN_MISSION_CONTROL_PROTOTYPE_ENABLED',
        readOnly: true,
        advisoryOnly: true,
        noExternalCalls: true,
        liveEnforcement: false,
      },
      opsSnapshotAvailable: false,
      summary: {
        domainCount: 0,
        landedFoundationCount: 0,
        evidenceToolingCount: 0,
        realOperatorEvidenceMissingCount: 0,
        approvalRequiredCount: 0,
        publicLaunchNoGoCount: 0,
      },
      domains: [],
      metadata: {
        ...payload.metadata,
        opsAggregationAttempted: false,
        highRiskSummariesAggregated: false,
      },
    });

    renderPage();

    expect(await screen.findByTestId('admin-mission-primary-state')).toHaveTextContent('Mission Control prototype 未启用');
    expect(screen.getByTestId('admin-mission-prototype-pill')).toHaveTextContent(/Prototype gate disabled/i);
    expect(screen.getByTestId('admin-mission-primary-action-link')).toHaveAttribute('href', '/zh/settings/system');
    expect(screen.getAllByText(/默认关闭/).length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByTestId('admin-mission-domain-grid')).not.toBeInTheDocument();
    expect(screen.queryAllByTestId('admin-mission-domain-card')).toHaveLength(0);
    expect(screen.queryByTestId('admin-mission-secondary-actions')).not.toBeInTheDocument();
  });

  it('renders sanitized drill-through links only to existing admin read surfaces', async () => {
    renderPage();

    await screen.findByTestId('admin-mission-control-page');
    expect(screen.getByRole('link', { name: /查看证据工作流/i })).toHaveAttribute('href', '/zh/admin/evidence-workflow?ref=mission_control');
    expect(screen.getByRole('link', { name: /查看系统日志/i })).toHaveAttribute('href', '/zh/admin/logs?tab=business&query=mission%20control&since=24h');
    expect(screen.getByRole('link', { name: /查看数据源运维/i })).toHaveAttribute('href', '/zh/admin/market-providers?surface=market_overview');
    expect(screen.getByRole('link', { name: /查看成本观测/i })).toHaveAttribute('href', '/zh/admin/cost-observability?window=24h&area=all');
    const text = screen.getByTestId('admin-mission-control-page').textContent || '';
    expect(text).not.toMatch(/token|secret|payload|credential|stack trace/i);
  });

  it('keeps primary action above secondary diagnostics', async () => {
    renderPage();

    const primary = await screen.findByTestId('admin-mission-primary-action');
    const secondary = await screen.findByTestId('admin-mission-action-hierarchy');
    expect(primary.getBoundingClientRect().top).toBeLessThanOrEqual(secondary.getBoundingClientRect().top);
    expect(within(primary).getByTestId('admin-mission-primary-action-link')).toBeInTheDocument();
    expect(within(secondary).getByTestId('admin-mission-secondary-actions')).toBeInTheDocument();
  });

  it('shows a sanitized error state when the projection fails', async () => {
    getSnapshot.mockRejectedValueOnce(new Error('raw token stack trace should not render'));

    renderPage();

    await waitFor(() => expect(screen.getByText('读取 Mission Control 失败')).toBeInTheDocument());
    expect(screen.getByTestId('admin-mission-control-page')).not.toHaveTextContent('raw token stack trace');
    expect(screen.getByTestId('admin-mission-primary-state')).toHaveTextContent(/不可用/);
  });
});
