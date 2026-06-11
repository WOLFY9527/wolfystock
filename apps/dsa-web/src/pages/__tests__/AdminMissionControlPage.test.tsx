import { render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AdminMissionControlPage from '../AdminMissionControlPage';

const { getSnapshot } = vi.hoisted(() => ({
  getSnapshot: vi.fn(),
}));

vi.mock('../../api/adminMissionControl', () => ({
  adminMissionControlApi: {
    getSnapshot,
  },
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
  evidenceRefs: [{ kind: 'doc', label: `${title} evidence`, ref: 'docs/audits/public-launch-readiness-master.md' }],
  blockerRefs: [{ kind: 'doc', label: 'Launch blocker register', ref: 'docs/audits/public-launch-gap-register.md' }],
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

describe('AdminMissionControlPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSnapshot.mockResolvedValue(payload);
  });

  it('renders the mission control readiness overview for all required domains', async () => {
    render(<AdminMissionControlPage />);

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

  it('separates foundation, evidence tooling, missing evidence, approval, and NO-GO labels', async () => {
    render(<AdminMissionControlPage />);

    const firstCard = (await screen.findAllByTestId('admin-mission-domain-card'))[0];
    expect(within(firstCard).getByText('基础已落地')).toBeInTheDocument();
    expect(within(firstCard).getByText('证据工具存在')).toBeInTheDocument();
    expect(within(firstCard).getByText('缺真实证据')).toBeInTheDocument();
    expect(within(firstCard).getByText('需要审批')).toBeInTheDocument();
    expect(within(firstCard).getByText('NO-GO')).toBeInTheDocument();
  });

  it('shows read-only system posture without mutation or approval controls', async () => {
    render(<AdminMissionControlPage />);

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

  it('renders sanitized drill-through links only to existing admin read surfaces', async () => {
    render(<AdminMissionControlPage />);

    await screen.findByTestId('admin-mission-control-page');
    expect(screen.getByRole('link', { name: /查看证据工作流/i })).toHaveAttribute('href', '/zh/admin/evidence-workflow?ref=mission_control');
    expect(screen.getByRole('link', { name: /查看系统日志/i })).toHaveAttribute('href', '/zh/admin/logs?tab=business&query=mission%20control&since=24h');
    expect(screen.getByRole('link', { name: /查看数据源运维/i })).toHaveAttribute('href', '/zh/admin/market-providers?surface=market_overview');
    expect(screen.getByRole('link', { name: /查看成本观测/i })).toHaveAttribute('href', '/zh/admin/cost-observability?window=24h&area=all');
    const text = screen.getByTestId('admin-mission-control-page').textContent || '';
    expect(text).not.toMatch(/token|secret|payload|credential|stack trace/i);
  });

  it('shows a sanitized error state when the projection fails', async () => {
    getSnapshot.mockRejectedValueOnce(new Error('raw token stack trace should not render'));

    render(<AdminMissionControlPage />);

    await waitFor(() => expect(screen.getByText('读取 Mission Control 失败')).toBeInTheDocument());
    expect(screen.getByTestId('admin-mission-control-page')).not.toHaveTextContent('raw token stack trace');
  });
});
