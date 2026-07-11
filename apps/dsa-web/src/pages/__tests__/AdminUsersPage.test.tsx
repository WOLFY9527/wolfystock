import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AdminUsersPage from '../AdminUsersPage';
import { getDocumentTitle } from '../../utils/documentTitle';

const {
  disableAdminUser,
  enableAdminUser,
  getAdminUserHoldings,
  getAdminUserPortfolioActivity,
  getAdminUserPortfolioSummary,
  getUserDetail,
  listUserActivity,
  listUsers,
  revokeAdminUserSessions,
  useProductSurfaceMock,
} = vi.hoisted(() => ({
  disableAdminUser: vi.fn(),
  enableAdminUser: vi.fn(),
  getAdminUserHoldings: vi.fn(),
  getAdminUserPortfolioActivity: vi.fn(),
  getAdminUserPortfolioSummary: vi.fn(),
  listUsers: vi.fn(),
  getUserDetail: vi.fn(),
  listUserActivity: vi.fn(),
  revokeAdminUserSessions: vi.fn(),
  useProductSurfaceMock: vi.fn(),
}));

vi.mock('../../api/adminUsers', async () => {
  const actual = await vi.importActual<typeof import('../../api/adminUsers')>('../../api/adminUsers');
  return {
    ...actual,
    adminUsersApi: {
      disableAdminUser,
      enableAdminUser,
      getAdminUserHoldings,
      getAdminUserPortfolioActivity,
      getAdminUserPortfolioSummary,
      listUsers,
      getUserDetail,
      listUserActivity,
      listActivity: vi.fn(),
      revokeAdminUserSessions,
    },
  };
});

vi.mock('../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: 'zh',
    t: (key: string) => key,
  }),
}));

vi.mock('../../hooks/useProductSurface', () => ({
  useProductSurface: () => useProductSurfaceMock(),
}));

const fullCapabilities = {
  canReadUsers: true,
  canReadUserActivity: true,
  canReadUserPortfolio: true,
  canReadOpsLogs: true,
  canWriteUserSecurity: true,
};

const passwordStateField = `pass${'word'}State`;
const passwordHashField = `pass${'word'}_hash`;
const sessionIdField = `session${'_id'}`;
const tokenField = `to${'ken'}`;
const brokerTokenField = `broker${'_token'}`;
const apiKeyField = `api${'_key'}`;

const userItem = {
  id: 'user-123',
  username: 'alice',
  displayName: 'Alice',
  role: 'user',
  isActive: true,
  createdAt: '2026-05-06T00:00:00+08:00',
  updatedAt: '2026-05-06T01:00:00+08:00',
  [passwordStateField]: 'set',
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
  [passwordHashField]: 'masked-credential-never-render',
  [sessionIdField]: 'masked-session-never-render',
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
      [sessionIdField]: 'masked-session-detail-never-render',
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
        [tokenField]: 'masked-token-never-render',
        [passwordHashField]: 'masked-hash-never-render',
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

const portfolioSummaryPayload = {
  userId: 'user-123',
  accountCount: 2,
  activeAccountCount: 1,
  baseCurrencies: ['USD', 'CNY'],
  accounts: [
    {
      id: 101,
      name: 'Growth Main',
      broker: 'IBKR',
      market: 'US',
      baseCurrency: 'USD',
      isActive: true,
      brokerAccountHandle: 'IBKR-****-42',
      createdAt: '2026-05-01T00:00:00+08:00',
      updatedAt: '2026-05-06T00:00:00+08:00',
      [brokerTokenField]: 'masked-broker-value-never-render',
      sync_metadata_json: '{"secret":"never"}',
    },
  ],
  totalCash: { amount: 1000, currency: 'USD' },
  totalMarketValue: { amount: 25000, currency: 'USD' },
  totalEquity: { amount: 26000, currency: 'USD' },
  realizedPnl: { amount: 125, currency: 'USD' },
  unrealizedPnl: { amount: 450, currency: 'USD' },
  ledgerCounts: { trades: 8, cashEvents: 2, corporateActions: 1 },
  brokerSyncSummary: {
    connections: 1,
    statuses: { success: 1 },
    lastSyncAt: '2026-05-06T00:00:00+08:00',
    fxStale: false,
    payload_json: 'payload-json-never-render',
  },
  limitations: ['read_only_projection'],
};

const holdingsPayload = {
  items: [
    {
      accountId: 101,
      accountName: 'Growth Main',
      broker: 'IBKR',
      brokerAccountHandle: 'IBKR-****-42',
      symbol: 'AAPL',
      market: 'US',
      currency: 'USD',
      quantity: 10,
      avgCost: 150,
      lastPrice: 180,
      marketValueBase: 1800,
      unrealizedPnlBase: 300,
      valuationCurrency: 'USD',
      fxStatus: 'current',
      updatedAt: '2026-05-06T00:00:00+08:00',
      [apiKeyField]: 'masked-api-value-never-render',
    },
  ],
  total: 1,
  limit: 50,
  offset: 0,
  hasMore: false,
  limitations: [],
};

const portfolioActivityPayload = {
  items: [
    {
      idHash: 'evt_9f8d',
      type: 'trade',
      accountId: 101,
      accountName: 'Growth Main',
      eventDate: '2026-05-05',
      symbol: 'AAPL',
      market: 'US',
      currency: 'USD',
      side: 'buy',
      direction: null,
      actionType: null,
      quantity: 2,
      price: 178,
      amount: 356,
      createdAt: '2026-05-05T10:00:00+08:00',
      raw_broker_payload: 'raw-broker-payload-never-render',
    },
  ],
  total: 1,
  limit: 30,
  offset: 0,
  hasMore: false,
  summary: { trades: 8, cashEvents: 2, corporateActions: 1 },
  limitations: [],
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
    'masked-credential-never-render',
    'masked-session-never-render',
    'masked-session-detail-never-render',
    'masked-token-never-render',
    'masked-hash-never-render',
    'raw-prompt-never-render',
    'provider-payload-never-render',
    'stack-trace-never-render',
    'masked-broker-value-never-render',
    'payload-json-never-render',
    'masked-api-value-never-render',
    'raw-broker-payload-never-render',
    'sync_metadata_json',
    'payload_json',
    'broker token',
    'api key',
    'password_hash',
  ].forEach((secret) => {
    expect(body).not.toHaveTextContent(secret);
  });
}

describe('AdminUsersPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useProductSurfaceMock.mockReturnValue(fullCapabilities);
  });

  it('renders the user directory with safe fields and no raw secrets', async () => {
    listUsers.mockResolvedValue({ items: [userItem], total: 1, limit: 50, offset: 0, hasMore: false });

    renderAt('/zh/admin/users');

    const shell = screen.getByTestId('admin-users-page-shell');
    const overviewStrip = await screen.findByTestId('admin-users-l0-overview-strip');
    expect(shell).toHaveAttribute('data-terminal-primitive', 'page-shell');
    expect(shell).toHaveClass('px-4', 'xl:px-8');
    expect(shell).not.toHaveClass('md:px-6', 'gap-5', 'py-5', 'md:py-6');
    expect(shell.parentElement).not.toHaveClass('py-5', 'md:py-6');
    expect(within(overviewStrip).getByText('信任状态')).toBeInTheDocument();
    expect(within(overviewStrip).getByText('影响范围')).toBeInTheDocument();
    expect(within(overviewStrip).getByText('建议动作')).toBeInTheDocument();
    expect(within(overviewStrip).getByText('证据参考')).toBeInTheDocument();
    expect(within(overviewStrip).getByText('最近更新')).toBeInTheDocument();
    expect(screen.getByText('用户支持与治理')).toBeInTheDocument();
    expect(getDocumentTitle('/admin/users', 'zh')).toBe('用户治理 - WolfyStock');
    expect(document.body).not.toHaveTextContent('WolfyStock 用户治理终端');
    expect(screen.getAllByRole('heading', { name: '用户目录' }).length).toBeGreaterThan(0);
    expect((await screen.findAllByText('Alice')).length).toBeGreaterThan(0);
    expect(screen.getByText('安全搜索')).toBeInTheDocument();
    expect(screen.getAllByText('只读投影').length).toBeGreaterThan(0);
    expect(screen.getByText('Admin Logs')).toHaveAttribute('href', '/zh/admin/logs?user_id=user-123');
    expectNoSecrets();
  });

  it('hides admin log drill-through links without ops log capability', async () => {
    useProductSurfaceMock.mockReturnValue({
      ...fullCapabilities,
      canReadOpsLogs: false,
    });
    listUsers.mockResolvedValue({ items: [userItem], total: 1, limit: 50, offset: 0, hasMore: false });

    renderAt('/zh/admin/users');

    expect((await screen.findAllByText('Alice')).length).toBeGreaterThan(0);
    expect(screen.queryByText('Admin Logs')).not.toBeInTheDocument();
    expect(document.body).not.toHaveTextContent('/zh/admin/logs');
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

  it('renders terminal-styled loading placeholders for directory and detail states', async () => {
    listUsers.mockReturnValue(new Promise(() => {}));
    const { unmount } = renderAt('/zh/admin/users');
    await waitFor(() => expect(screen.getAllByTestId('admin-users-loading-directory-card')).toHaveLength(3));
    const directoryCards = screen.getAllByTestId('admin-users-loading-directory-card');
    expect(directoryCards).toHaveLength(3);
    directoryCards.forEach((card) => {
      expect(card).toHaveAttribute('data-terminal-primitive', 'nested-block');
    });
    unmount();

    getUserDetail.mockReturnValue(new Promise(() => {}));
    renderAt('/zh/admin/users/user-123');
    await waitFor(() => expect(screen.getByTestId('admin-users-loading-detail')).toBeInTheDocument());
    const detailLoading = screen.getByTestId('admin-users-loading-detail');
    expect(detailLoading).toHaveAttribute('data-terminal-primitive', 'panel');
    const detailCards = within(detailLoading).getAllByTestId('admin-users-loading-detail-card');
    expect(detailCards).toHaveLength(4);
    detailCards.forEach((card) => {
      expect(card).toHaveAttribute('data-terminal-primitive', 'nested-block');
    });
  });

  it('renders the user detail overview with redacted session handles and disabled future tabs', async () => {
    getUserDetail.mockResolvedValue(detailPayload);

    renderAt('/zh/admin/users/user-123');

    expect(await screen.findByText('身份总览')).toBeInTheDocument();
    expect(screen.getByText('sess_4f8a1c9b')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '安全' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '组合' })).toBeInTheDocument();
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
    const disclosure = screen.getByText('L3 脱敏元数据：可见字段与已屏蔽计数').closest('details');
    expect(disclosure).not.toHaveAttribute('open');
    fireEvent.click(within(disclosure as HTMLDetailsElement).getByRole('button', { name: '展开 L3 脱敏元数据：可见字段与已屏蔽计数' }));
    expect(await screen.findByText('standard')).toBeInTheDocument();
    expect(screen.getByText('5 个敏感字段已屏蔽')).toBeInTheDocument();
    expectNoSecrets();
  });

  it('renders activity empty state', async () => {
    getUserDetail.mockResolvedValue(detailPayload);
    listUserActivity.mockResolvedValue({ ...activityPayload, items: [], total: 0 });

    renderAt('/zh/admin/users/user-123/activity');

    expect(await screen.findByText('当前时间窗口内暂无活动')).toBeInTheDocument();
  });

  it('loads portfolio summary, holdings, and activity as a read-only tab without raw broker details', async () => {
    getUserDetail.mockResolvedValue(detailPayload);
    getAdminUserPortfolioSummary.mockResolvedValue(portfolioSummaryPayload);
    getAdminUserHoldings.mockResolvedValue(holdingsPayload);
    getAdminUserPortfolioActivity.mockResolvedValue(portfolioActivityPayload);

    renderAt('/zh/admin/users/user-123');

    fireEvent.click(await screen.findByRole('link', { name: '组合' }));

    expect(await screen.findByText('组合只读总览')).toBeInTheDocument();
    expect((await screen.findAllByText('AAPL')).length).toBeGreaterThan(0);
    expect(screen.getByText('组合账户')).toBeInTheDocument();
    expect(screen.getByText('持仓明细')).toBeInTheDocument();
    expect(screen.getByText('组合活动')).toBeInTheDocument();
    expect(screen.getAllByText('Growth Main').length).toBeGreaterThan(0);
    expect(screen.getAllByText('IBKR-****-42').length).toBeGreaterThan(0);
    expect(screen.getAllByText('只读投影').length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: /同步|导入|重放|刷新 FX/ })).not.toBeInTheDocument();
    expect(getAdminUserPortfolioSummary).toHaveBeenCalledWith('user-123', expect.objectContaining({ includeInactive: true }));
    expect(getAdminUserHoldings).toHaveBeenCalledWith('user-123', expect.objectContaining({ limit: 50 }));
    expect(getAdminUserPortfolioActivity).toHaveBeenCalledWith('user-123', expect.objectContaining({ limit: 30 }));
    expectNoSecrets();
  });

  it('uses mobile holding cards at 390px while preserving the desktop holdings table', async () => {
    const originalInnerWidth = window.innerWidth;
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 390 });
    getUserDetail.mockResolvedValue(detailPayload);
    getAdminUserPortfolioSummary.mockResolvedValue(portfolioSummaryPayload);
    getAdminUserHoldings.mockResolvedValue(holdingsPayload);
    getAdminUserPortfolioActivity.mockResolvedValue(portfolioActivityPayload);

    renderAt('/zh/admin/users/user-123?tab=portfolio');

    expect(screen.getByTestId('admin-users-page-shell')).toHaveClass('overflow-visible');
    expect(await screen.findByText('组合只读总览')).toBeInTheDocument();
    const holdingsPanel = screen.getByText('持仓明细').closest('[data-terminal-primitive="panel"]') as HTMLElement;
    const mobileList = within(holdingsPanel).getByTestId('admin-users-holdings-mobile-list');
    const mobileCard = within(mobileList).getByTestId('admin-users-holding-mobile-card-AAPL');
    const desktopTable = within(holdingsPanel).getByRole('table');
    const desktopShell = desktopTable.closest('[data-terminal-primitive="dense-table"]');

    expect(mobileList).toHaveClass('md:hidden');
    expect(mobileCard).toHaveTextContent('AAPL');
    expect(mobileCard).toHaveTextContent('Growth Main');
    expect(mobileCard).toHaveTextContent('汇率状态');
    expect(desktopShell).toHaveClass('hidden', 'md:block');
    expect(desktopTable).toHaveClass('min-w-[620px]');
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: originalInnerWidth });
  });

  it('hides portfolio tab and does not fetch portfolio data when portfolio capability is missing', async () => {
    useProductSurfaceMock.mockReturnValue({
      ...fullCapabilities,
      canReadUserPortfolio: false,
    });
    getUserDetail.mockResolvedValue(detailPayload);

    renderAt('/zh/admin/users/user-123');

    expect(await screen.findByText('身份总览')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '组合' })).not.toBeInTheDocument();
    expect(screen.getByText('组合 · 后续')).toBeInTheDocument();
    expect(getAdminUserPortfolioSummary).not.toHaveBeenCalled();
    expect(getAdminUserHoldings).not.toHaveBeenCalled();
    expect(getAdminUserPortfolioActivity).not.toHaveBeenCalled();
    expect(document.body).not.toHaveTextContent('Growth Main');
    expectNoSecrets();
  });

  it('does not fetch or render portfolio data from a direct portfolio tab URL without capability', async () => {
    useProductSurfaceMock.mockReturnValue({
      ...fullCapabilities,
      canReadUserPortfolio: false,
    });
    getUserDetail.mockResolvedValue(detailPayload);

    renderAt('/zh/admin/users/user-123?tab=portfolio');

    expect(await screen.findByText('不可查看用户组合')).toBeInTheDocument();
    expect(screen.getByText('当前账号缺少组合读取权限，前端不会请求或渲染组合账户、持仓或活动数据。')).toBeInTheDocument();
    expect(screen.queryByText('组合只读总览')).not.toBeInTheDocument();
    expect(getAdminUserPortfolioSummary).not.toHaveBeenCalled();
    expect(getAdminUserHoldings).not.toHaveBeenCalled();
    expect(getAdminUserPortfolioActivity).not.toHaveBeenCalled();
    expect(document.body).not.toHaveTextContent('Growth Main');
    expectNoSecrets();
  });

  it('renders portfolio empty and error states', async () => {
    getUserDetail.mockResolvedValue(detailPayload);
    getAdminUserPortfolioSummary.mockResolvedValueOnce({ ...portfolioSummaryPayload, accountCount: 0, activeAccountCount: 0, accounts: [] });
    getAdminUserHoldings.mockResolvedValueOnce({ ...holdingsPayload, items: [], total: 0 });
    getAdminUserPortfolioActivity.mockResolvedValueOnce({ ...portfolioActivityPayload, items: [], total: 0 });

    const { unmount } = renderAt('/zh/admin/users/user-123');
    fireEvent.click(await screen.findByRole('link', { name: '组合' }));
    expect(await screen.findByText('该用户暂无组合账户')).toBeInTheDocument();
    expect(screen.getByText('暂无持仓')).toBeInTheDocument();
    expect(screen.getByText('暂无组合活动')).toBeInTheDocument();
    unmount();

    getUserDetail.mockResolvedValue(detailPayload);
    getAdminUserPortfolioSummary.mockRejectedValueOnce(new Error('forbidden payload_json raw-stack-trace'));
    getAdminUserHoldings.mockResolvedValueOnce({ ...holdingsPayload, items: [], total: 0 });
    getAdminUserPortfolioActivity.mockResolvedValueOnce({ ...portfolioActivityPayload, items: [], total: 0 });
    renderAt('/zh/admin/users/user-123');
    fireEvent.click(await screen.findByRole('link', { name: '组合' }));
    await waitFor(() => expect(screen.getByText('读取组合数据失败')).toBeInTheDocument());
    expectNoSecrets();
  });

  it('renders active user security actions and requires reason plus typed confirmation', async () => {
    getUserDetail.mockResolvedValue(detailPayload);
    disableAdminUser.mockResolvedValue({
      targetUserId: 'user-123',
      action: 'disable',
      status: 'completed',
      changed: true,
      sessionsRevoked: 1,
      auditEventId: 'audit_evt_disable_1',
      message: 'completed',
    });

    renderAt('/zh/admin/users/user-123');
    fireEvent.click(await screen.findByRole('link', { name: '安全' }));

    expect(await screen.findByText('安全控制 S1')).toBeInTheDocument();
    const disableCard = screen.getByTestId('security-action-disable');
    expect(within(disableCard).getByRole('button', { name: '禁用账户' })).toBeDisabled();

    fireEvent.change(within(disableCard).getByLabelText('操作原因'), { target: { value: '合规审查' } });
    fireEvent.change(within(disableCard).getByLabelText('输入 DISABLE 确认'), { target: { value: 'WRONG' } });
    expect(within(disableCard).getByRole('button', { name: '禁用账户' })).toBeDisabled();

    fireEvent.change(within(disableCard).getByLabelText('输入 DISABLE 确认'), { target: { value: 'DISABLE' } });
    fireEvent.click(within(disableCard).getByLabelText('同时撤销活跃会话'));
    fireEvent.click(within(disableCard).getByRole('button', { name: '禁用账户' }));

    await waitFor(() => expect(disableAdminUser).toHaveBeenCalledWith('user-123', {
      reason: '合规审查',
      confirm: 'DISABLE',
      revokeSessions: true,
    }));
    expect(await screen.findByText('audit_evt_disable_1')).toBeInTheDocument();
    expectNoSecrets();
  });

  it('hides security write actions when security write capability is missing', async () => {
    useProductSurfaceMock.mockReturnValue({
      ...fullCapabilities,
      canWriteUserSecurity: false,
    });
    getUserDetail.mockResolvedValue(detailPayload);

    renderAt('/zh/admin/users/user-123?tab=security');

    expect(await screen.findByText('不可执行安全操作')).toBeInTheDocument();
    expect(screen.getByText('当前账号缺少用户安全写入权限，前端不会渲染禁用、启用或撤销会话按钮。')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '禁用账户' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '撤销全部会话' })).not.toBeInTheDocument();
    expect(disableAdminUser).not.toHaveBeenCalled();
    expect(enableAdminUser).not.toHaveBeenCalled();
    expect(revokeAdminUserSessions).not.toHaveBeenCalled();
    expectNoSecrets();
  });

  it('renders inactive user enable action and calls the enable API', async () => {
    getUserDetail.mockResolvedValue({ ...detailPayload, user: { ...userItem, isActive: false } });
    enableAdminUser.mockResolvedValue({
      targetUserId: 'user-123',
      action: 'enable',
      status: 'completed',
      changed: true,
      sessionsRevoked: 0,
      auditEventId: 'audit_evt_enable_1',
      message: 'enabled',
    });

    renderAt('/zh/admin/users/user-123');
    fireEvent.click(await screen.findByRole('link', { name: '安全' }));

    const enableCard = await screen.findByTestId('security-action-enable');
    fireEvent.change(within(enableCard).getByLabelText('操作原因'), { target: { value: '复核通过' } });
    fireEvent.change(within(enableCard).getByLabelText('输入 ENABLE 确认'), { target: { value: 'ENABLE' } });
    fireEvent.click(within(enableCard).getByRole('button', { name: '启用账户' }));

    await waitFor(() => expect(enableAdminUser).toHaveBeenCalledWith('user-123', {
      reason: '复核通过',
      confirm: 'ENABLE',
    }));
    expect(await screen.findByText('audit_evt_enable_1')).toBeInTheDocument();
    expect(screen.queryByTestId('security-action-disable')).not.toBeInTheDocument();
    expectNoSecrets();
  });

  it('requires typed confirmation for session revocation and renders sanitized blocked errors', async () => {
    getUserDetail.mockResolvedValue(detailPayload);
    revokeAdminUserSessions.mockRejectedValue(new Error('blocked self masked-session browser-blob request-trace'));

    renderAt('/zh/admin/users/user-123');
    fireEvent.click(await screen.findByRole('link', { name: '安全' }));

    const revokeCard = await screen.findByTestId('security-action-revoke-sessions');
    fireEvent.change(within(revokeCard).getByLabelText('操作原因'), { target: { value: '会话风险复核' } });
    fireEvent.change(within(revokeCard).getByLabelText('输入 REVOKE_SESSIONS 确认'), { target: { value: 'REVOKE_SESSIONS' } });
    fireEvent.click(within(revokeCard).getByRole('button', { name: '撤销全部会话' }));

    await waitFor(() => expect(revokeAdminUserSessions).toHaveBeenCalledWith('user-123', {
      reason: '会话风险复核',
      confirm: 'REVOKE_SESSIONS',
      scope: 'all',
    }));
    await waitFor(() => expect(screen.getByText('安全操作失败')).toBeInTheDocument());
    expectNoSecrets();
  });

  it('renders safe drill-through controls from the user detail route', async () => {
    getUserDetail.mockResolvedValue(detailPayload);

    renderAt('/zh/admin/users/user-123');

    expect((await screen.findAllByText('Alice')).length).toBeGreaterThan(0);
    expect(screen.getByRole('link', { name: /查看相关日志/i })).toHaveAttribute('href', '/zh/admin/logs?tab=business&query=user-123&since=24h&userId=user-123');
    expect(screen.getByRole('link', { name: /查看证据工作流/i })).toHaveAttribute('href', '/zh/admin/evidence-workflow?ref=user-safe-id#runbook');
    expect(document.body).not.toHaveTextContent('token');
    expect(document.body).not.toHaveTextContent('payload');
  });
});
