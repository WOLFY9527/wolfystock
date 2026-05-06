import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AdminUsersPage from '../AdminUsersPage';

const { listUsers, getUserDetail, listUserActivity } = vi.hoisted(() => ({
  listUsers: vi.fn(),
  getUserDetail: vi.fn(),
  listUserActivity: vi.fn(),
}));

vi.mock('../../api/adminUsers', async () => {
  const actual = await vi.importActual<typeof import('../../api/adminUsers')>('../../api/adminUsers');
  return {
    ...actual,
    adminUsersApi: {
      listUsers,
      getUserDetail,
      listUserActivity,
      listActivity: vi.fn(),
    },
  };
});

vi.mock('../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: 'zh',
    t: (key: string) => key,
  }),
}));

const userItem = {
  id: 'user-123',
  username: 'alice',
  displayName: 'Alice',
  role: 'user',
  isActive: true,
  createdAt: '2026-05-06T00:00:00+08:00',
  updatedAt: '2026-05-06T01:00:00+08:00',
  passwordState: 'set',
  lastSeenAt: '2026-05-06T08:00:00+08:00',
  sessionSummary: {
    activeCount: 1,
    expiredCount: 0,
    revokedCount: 0,
    lastSeenAt: '2026-05-06T08:00:00+08:00',
    nextExpiresAt: '2026-05-07T08:00:00+08:00',
  },
  riskBadges: [{ code: 'sessionless', label: 'No sessions', severity: 'info', source: 'session' }],
  links: {
    self: '/api/v1/admin/users/user-123',
    adminLogs: '/api/v1/admin/logs?user_id=user-123',
    activity: '/api/v1/admin/users/user-123/activity',
  },
  password_hash: 'pbkdf2-secret-never-render',
  session_id: 'raw-session-id-never-render',
};

const detailPayload = {
  user: userItem,
  sessions: [
    {
      sessionHandle: 'sess_4f8a1c9b',
      status: 'active',
      createdAt: '2026-05-06T07:00:00+08:00',
      lastSeenAt: '2026-05-06T08:00:00+08:00',
      expiresAt: '2026-05-07T08:00:00+08:00',
      revokedAt: null,
      session_id: 'raw-session-detail-never-render',
    },
  ],
  dataLinks: {
    adminLogs: '/api/v1/admin/logs?user_id=user-123',
    activity: '/api/v1/admin/users/user-123/activity',
  },
  limitations: ['failed_login_count_unavailable'],
};

const activityPayload = {
  items: [
    {
      id: 'act_1',
      timestamp: '2026-05-06T08:00:00+08:00',
      actor: { type: 'user', userId: 'user-123', label: 'Alice', sessionIdHash: 'sha256:actor' },
      targetUser: { id: 'user-123', label: 'Alice' },
      family: 'analysis',
      action: 'analysis.completed',
      entity: { type: 'analysis_history', idHash: 'sha256:entity', label: 'AAPL standard report', symbol: 'AAPL' },
      status: 'success',
      outcome: 'ok',
      requestIdHash: 'sha256:req',
      sessionIdHash: 'sha256:sess',
      source: { kind: 'execution_log_session', table: 'execution_log_sessions', confidence: 'confirmed' },
      redactedMetadata: {
        reportType: 'standard',
        token: 'token=sk-live-secret',
        password_hash: 'hash-never-render',
        rawPrompt: 'raw-prompt-never-render',
        providerPayload: 'provider-payload-never-render',
        stackTrace: 'stack-trace-never-render',
      },
      logLinks: [{ kind: 'admin_logs.business_event', idHash: 'sha256:log' }],
    },
  ],
  total: 1,
  limit: 50,
  offset: 0,
  hasMore: false,
  window: { from: '2026-05-05T08:00:00+08:00', to: '2026-05-06T08:00:00+08:00', maxDays: 90 },
  limitations: ['raw_payloads_excluded'],
};

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/zh/admin/users" element={<AdminUsersPage />} />
        <Route path="/zh/admin/users/:userId" element={<AdminUsersPage />} />
        <Route path="/zh/admin/users/:userId/activity" element={<AdminUsersPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function expectNoSecrets() {
  const body = document.body;
  [
    'pbkdf2-secret-never-render',
    'raw-session-id-never-render',
    'raw-session-detail-never-render',
    'sk-live-secret',
    'hash-never-render',
    'raw-prompt-never-render',
    'provider-payload-never-render',
    'stack-trace-never-render',
    'password_hash',
  ].forEach((secret) => {
    expect(body).not.toHaveTextContent(secret);
  });
}

describe('AdminUsersPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the user directory with safe fields and no raw secrets', async () => {
    listUsers.mockResolvedValue({ items: [userItem], total: 1, limit: 50, offset: 0, hasMore: false });

    renderAt('/zh/admin/users');

    expect(screen.getByText('用户数据控制中心')).toBeInTheDocument();
    expect(await screen.findByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('安全搜索')).toBeInTheDocument();
    expect(screen.getByText('用户目录')).toBeInTheDocument();
    expect(screen.getByText('只读')).toBeInTheDocument();
    expect(screen.getByText('Admin Logs')).toHaveAttribute('href', '/zh/admin/logs?user_id=user-123');
    expectNoSecrets();
  });

  it('renders empty and error states for the directory', async () => {
    listUsers.mockResolvedValueOnce({ items: [], total: 0, limit: 50, offset: 0, hasMore: false });
    const { unmount } = renderAt('/zh/admin/users');
    expect(await screen.findByText('暂无符合条件的用户')).toBeInTheDocument();
    unmount();

    listUsers.mockRejectedValueOnce(new Error('admin required'));
    renderAt('/zh/admin/users');
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
    expect(screen.getByText('读取用户目录失败')).toBeInTheDocument();
  });

  it('renders the user detail overview with redacted session handles and disabled future tabs', async () => {
    getUserDetail.mockResolvedValue(detailPayload);

    renderAt('/zh/admin/users/user-123');

    expect(await screen.findByText('Identity')).toBeInTheDocument();
    expect(screen.getByText('sess_4f8a1c9b')).toBeInTheDocument();
    expect(screen.getByText('安全 · 后续')).toBeInTheDocument();
    expect(screen.getByText('组合 · 后续')).toBeInTheDocument();
    expect(screen.getByText('安全操作后续开放')).toBeDisabled();
    expectNoSecrets();
  });

  it('renders detail API errors as sanitized failures', async () => {
    getUserDetail.mockRejectedValue(new Error('not found'));

    renderAt('/zh/admin/users/missing-user');

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
    expect(screen.getByText('读取用户详情失败')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: '返回用户目录' }).length).toBeGreaterThan(0);
  });

  it('renders activity filters and hides secret-like metadata from the DOM', async () => {
    getUserDetail.mockResolvedValue(detailPayload);
    listUserActivity.mockResolvedValue(activityPayload);

    renderAt('/zh/admin/users/user-123/activity');

    expect(await screen.findByText('活动时间线')).toBeInTheDocument();
    expect(screen.getByText('analysis.completed')).toBeInTheDocument();
    expect(screen.getByText('standard')).toBeInTheDocument();
    expect(screen.getByText('5 个敏感字段已屏蔽')).toBeInTheDocument();
    expect(screen.getByText('脱敏元数据').closest('details')).not.toHaveAttribute('open');
    expectNoSecrets();
  });

  it('renders activity empty state', async () => {
    getUserDetail.mockResolvedValue(detailPayload);
    listUserActivity.mockResolvedValue({ ...activityPayload, items: [], total: 0 });

    renderAt('/zh/admin/users/user-123/activity');

    expect(await screen.findByText('当前时间窗口内暂无活动')).toBeInTheDocument();
  });
});
