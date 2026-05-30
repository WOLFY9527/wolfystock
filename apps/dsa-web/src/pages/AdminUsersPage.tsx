import type React from 'react';
import { useEffect, useEffectEvent, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import {
  AlertTriangle,
  Clock3,
  ExternalLink,
  Search,
  UserRound,
} from 'lucide-react';
import {
  adminUsersApi,
  type AdminActivityEvent,
  type AdminActivityParams,
  type AdminActivityResponse,
  type AdminHoldingListResponse,
  type AdminMoneyAmount,
  type AdminPortfolioActivityResponse,
  type AdminPortfolioSummaryResponse,
  type AdminSecurityActionResponse,
  type AdminSessionSummary,
  type AdminUserDetailResponse,
  type AdminUserListItem,
  type AdminUserListParams,
  type AdminUserListResponse,
} from '../api/adminUsers';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { ApiErrorAlert } from '../components/common/ApiErrorAlert';
import { Checkbox } from '../components/common/Checkbox';
import { Input } from '../components/common/Input';
import { Select } from '../components/common/Select';
import {
  TerminalButton,
  TerminalChip,
  TerminalDenseList,
  TerminalDenseTable,
  TerminalDisclosure,
  TerminalEmptyState,
  TerminalGrid,
  TerminalMetric,
  TerminalNestedBlock,
  TerminalNotice,
  TerminalPageHeading,
  TerminalPageShell,
  TerminalPanel,
  TerminalSectionHeader,
} from '../components/terminal/TerminalPrimitives';
import { useI18n } from '../contexts/UiLanguageContext';
import { useProductSurface } from '../hooks/useProductSurface';
import { cn } from '../utils/cn';
import { formatCurrency, formatDateTime, formatNumber } from '../utils/format';

type PageMode = 'directory' | 'detail' | 'activity';
type DetailTabKey = 'detail' | 'portfolio' | 'security';
type LoadState<T> = {
  loading: boolean;
  error: ParsedApiError | null;
  data: T | null;
};
type SecurityActionKey = 'disable' | 'enable' | 'revoke_sessions';
type SecurityActionFormState = {
  reason: string;
  confirm: string;
  revokeSessions: boolean;
  loading: boolean;
  error: ParsedApiError | null;
  result: AdminSecurityActionResponse | null;
};

const USER_LIMIT = 50;
const ACTIVITY_LIMIT = 50;
const SENSITIVE_KEY_RE = /(password|passwd|hash|salt|cookie|token|secret|credential|authorization|api[_-]?key|session[_-]?id|sessionid|raw[_-]?(prompt|message|body|request|payload|stack)|provider[_-]?payload|stack[_-]?trace)/i;
const SECRET_TEXT_RE = /(bearer\s+[a-z0-9._-]+|authorization\s*[:=]\s*[^,\s]+|api[_-]?key\s*[:=]\s*[^,\s]+|token\s*[:=]\s*[^,\s]+|secret\s*[:=]\s*[^,\s]+|password\s*[:=]\s*[^,\s]+|cookie\s*[:=]\s*[^,\s]+)/gi;

const USER_STATUS_OPTIONS = [
  { value: 'all', label: '全部状态' },
  { value: 'active', label: '活跃' },
  { value: 'inactive', label: '停用' },
  { value: 'needs_password', label: '待初始化密码' },
  { value: 'sessionless', label: '无会话' },
  { value: 'stale_session', label: '会话过期' },
];

const ROLE_OPTIONS = [
  { value: '', label: '全部角色' },
  { value: 'admin', label: '管理员' },
  { value: 'user', label: '普通用户' },
];

const ACTIVITY_FAMILY_OPTIONS = [
  { value: '', label: '全部族群' },
  { value: 'auth', label: '认证' },
  { value: 'analysis', label: '分析' },
  { value: 'scanner', label: 'Scanner' },
  { value: 'backtest', label: 'Backtest' },
  { value: 'portfolio', label: '组合' },
  { value: 'admin', label: '管理审计' },
  { value: 'system', label: '系统' },
];

const ACTIVITY_STATUS_OPTIONS = [
  { value: '', label: '全部结果' },
  { value: 'success', label: '成功' },
  { value: 'failed', label: '失败' },
  { value: 'partial', label: '部分' },
  { value: 'running', label: '运行中' },
  { value: 'skipped', label: '跳过' },
  { value: 'unknown', label: '未知' },
];

const ACTOR_TYPE_OPTIONS = [
  { value: '', label: '全部发起方' },
  { value: 'admin', label: '管理员' },
  { value: 'user', label: '用户' },
  { value: 'guest', label: '游客' },
  { value: 'anonymous', label: '匿名' },
  { value: 'system', label: '系统' },
];

const ENTITY_TYPE_OPTIONS = [
  { value: '', label: '全部对象' },
  { value: 'auth_session', label: '认证会话' },
  { value: 'analysis_history', label: '分析记录' },
  { value: 'scanner_run', label: 'Scanner Run' },
  { value: 'backtest_run', label: 'Backtest Run' },
  { value: 'portfolio_account', label: '组合账户' },
  { value: 'admin_view', label: '管理访问' },
  { value: 'provider_operation', label: '数据源运维' },
];

const TERMINAL_LINK_ACTION_CLASSNAME = 'inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-white/70 transition-all duration-300 hover:border-white/20 hover:bg-white/10 hover:text-white';
const TERMINAL_DISABLED_TAB_CLASSNAME = 'inline-flex min-h-9 shrink-0 items-center rounded-lg border border-white/8 bg-white/[0.02] px-3 py-1.5 text-xs font-medium text-white/25';
const TERMINAL_IDLE_TAB_CLASSNAME = 'border-white/10 bg-white/[0.03] text-white/60 hover:border-white/20 hover:bg-white/[0.07] hover:text-white';
const TERMINAL_ACTIVE_TAB_CLASSNAME = 'border-cyan-300/20 bg-cyan-400/5 text-cyan-100 shadow-[0_0_0_1px_rgba(34,211,238,0.04)]';
const TERMINAL_ACTIVE_TOGGLE_CLASSNAME = 'border-cyan-300/20 bg-cyan-400/5 text-cyan-100 hover:border-cyan-300/30 hover:bg-cyan-400/10 hover:text-cyan-50';

function text(value: unknown, fallback = '--'): string {
  const normalized = String(value ?? '').trim();
  return normalized || fallback;
}

function formatDate(value?: string | null): string {
  return value ? formatDateTime(value) : '--';
}

function statusLabel(value?: string | null): string {
  const normalized = String(value || '').toLowerCase();
  if (normalized === 'active') return '活跃';
  if (normalized === 'inactive') return '停用';
  if (normalized === 'expired') return '过期';
  if (normalized === 'revoked') return '已撤销';
  if (normalized === 'success') return '成功';
  if (normalized === 'failed') return '失败';
  if (normalized === 'partial') return '部分';
  if (normalized === 'running') return '运行中';
  if (normalized === 'skipped') return '跳过';
  if (normalized === 'cancelled') return '取消';
  if (normalized === 'ok') return '正常';
  if (normalized === 'warning') return '告警';
  if (normalized === 'timeout') return '超时';
  return value ? String(value) : '未知';
}

function passwordStateLabel(value?: string | null): string {
  if (value === 'set') return '已设置';
  if (value === 'unset') return '未初始化';
  return '未知';
}

type TerminalChipVariant = React.ComponentProps<typeof TerminalChip>['variant'];

function riskChipVariant(severity?: string): TerminalChipVariant {
  if (severity === 'critical') return 'danger';
  if (severity === 'warning') return 'caution';
  return 'info';
}

function statusChipVariant(value?: string | null): TerminalChipVariant {
  const normalized = String(value || '').toLowerCase();
  if (['active', 'success', 'ok'].includes(normalized)) return 'success';
  if (['failed', 'revoked', 'inactive'].includes(normalized)) return 'danger';
  if (['partial', 'warning', 'expired', 'timeout'].includes(normalized)) return 'caution';
  return 'neutral';
}

function metricValueTone(tone: 'neutral' | 'good' | 'warn' | 'danger' | 'info' = 'neutral'): string {
  return {
    neutral: 'text-white',
    good: 'text-emerald-300',
    warn: 'text-amber-300',
    danger: 'text-rose-300',
    info: 'text-cyan-300',
  }[tone];
}

function tabFromSearch(search: string): DetailTabKey {
  const value = new URLSearchParams(search).get('tab');
  if (value === 'portfolio' || value === 'security') return value;
  return 'detail';
}

function formatMoney(value?: AdminMoneyAmount | null): string {
  if (!value) return '--';
  return formatCurrency(value.amount, { currency: value.currency || 'USD' });
}

function compactNumber(value?: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '--';
  return formatNumber(value, 2);
}

function limitationText(value: string): string {
  if (value === 'read_only_projection') return '只读投影';
  if (value === 'raw_payloads_excluded') return '原始载荷已排除';
  if (value === 'broker_credentials_excluded') return '经纪商凭证已排除';
  if (value === 'partial_data') return '部分数据';
  if (value === 'forbidden') return '权限不足';
  return value.replace(/_/g, ' ');
}

function sanitizedActionError(error: unknown): ParsedApiError {
  const parsed = getParsedApiError(error);
  return {
    ...parsed,
    title: '安全操作失败',
    message: '操作未完成。请检查权限、目标用户状态、是否为自身账户或最后一个管理员保护。',
    rawMessage: '',
  };
}

function sanitizedPortfolioError(error: unknown): ParsedApiError {
  const parsed = getParsedApiError(error);
  return {
    ...parsed,
    title: '读取组合数据失败',
    message: parsed.status === 403 ? '当前权限不能查看该用户组合状态。' : '组合安全投影暂不可用，请稍后重试。',
    rawMessage: '',
  };
}

function freshSecurityActionState(): SecurityActionFormState {
  return {
    reason: '',
    confirm: '',
    revokeSessions: false,
    loading: false,
    error: null,
    result: null,
  };
}

const LoadingBar: React.FC<{ className?: string }> = ({ className }) => (
  <div aria-hidden="true" className={cn('animate-pulse rounded-full bg-white/[0.08]', className)} />
);

const LoadingNestedCard: React.FC<{ className?: string; 'data-testid'?: string }> = ({ className, 'data-testid': dataTestId }) => (
  <TerminalNestedBlock data-testid={dataTestId} className={className}>
    <div className="grid gap-3">
      <LoadingBar className="h-3 w-20" />
      <LoadingBar className="h-5 w-36 max-w-full" />
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        {[0, 1, 2, 3].map((item) => <LoadingBar key={item} className="h-10 w-full" />)}
      </div>
    </div>
  </TerminalNestedBlock>
);

function adminLogHref(raw?: string | null, locale = 'zh'): string | null {
  if (!raw) return null;
  const prefix = locale === 'en' ? '/en' : '/zh';
  const cleaned = raw.replace(/^\/api\/v1/, '');
  if (cleaned.startsWith('/admin/logs')) {
    return `${prefix}${cleaned}`;
  }
  return cleaned.startsWith('/') ? `${prefix}${cleaned}` : raw;
}

function sanitizeScalar(value: unknown): string {
  if (value == null) return '--';
  if (typeof value === 'string') return value.replace(SECRET_TEXT_RE, () => '***');
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return '[已折叠]';
}

function safeMetadataEntries(metadata?: Record<string, unknown>): Array<[string, string]> {
  if (!metadata) return [];
  return Object.entries(metadata)
    .filter(([key]) => !SENSITIVE_KEY_RE.test(key))
    .slice(0, 12)
    .map(([key, value]) => [key, sanitizeScalar(value)]);
}

function sensitiveFieldCount(metadata?: Record<string, unknown>): number {
  if (!metadata) return 0;
  return Object.keys(metadata).filter((key) => SENSITIVE_KEY_RE.test(key)).length;
}

const PageHeader: React.FC<{
  mode: PageMode;
  user?: AdminUserListItem | null;
  currentState: string;
  nextAction: string;
}> = ({ mode, user, currentState, nextAction }) => {
  const title = mode === 'directory'
    ? '用户目录'
    : mode === 'activity'
    ? `${text(user?.displayName || user?.username, '用户活动')} · 活动`
    : text(user?.displayName || user?.username, '用户详情');
  return (
    <TerminalPanel as="section" className="overflow-hidden">
      <div className="flex flex-col gap-4">
        <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 flex-1">
            <TerminalPageHeading
              eyebrow="WolfyStock 用户治理终端"
              title={title}
              action={(
                <div className="flex flex-wrap justify-end gap-2">
                  <TerminalChip variant="info">只读投影</TerminalChip>
                  <TerminalChip variant="neutral">敏感字段脱敏</TerminalChip>
                  <TerminalChip variant="caution">显式安全确认保留</TerminalChip>
                </div>
              )}
            />
            <p className="mt-2 max-w-3xl text-sm leading-6 text-white/52">
              账号、会话、组合投影与审计线索共用同一套紧凑运维终端节奏；敏感凭证材料、原始会话标识和底层调试载荷默认不进入界面。
            </p>
          </div>
        </div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <TerminalMetric
            label="页面用途"
            value="核对账号与会话风险"
            subvalue="目录、详情、活动与组合只读投影"
            valueClassName="text-sm font-semibold tracking-normal"
          />
          <TerminalMetric
            label="当前状态"
            value={currentState}
            subvalue="无原始凭证或敏感元数据直出"
            valueClassName="text-sm font-semibold tracking-normal"
          />
          <TerminalMetric
            label="下一步"
            value={nextAction}
            subvalue="危险操作区独立隔离并保留确认短语"
            valueClassName="text-sm font-semibold tracking-normal"
          />
        </div>
      </div>
    </TerminalPanel>
  );
};

const UserRow: React.FC<{ user: AdminUserListItem; locale: 'zh' | 'en'; canReadOpsLogs: boolean }> = ({ user, locale, canReadOpsLogs }) => {
  const href = locale === 'en' ? `/en/admin/users/${encodeURIComponent(user.id)}` : `/zh/admin/users/${encodeURIComponent(user.id)}`;
  const adminLogs = canReadOpsLogs ? adminLogHref(user.links?.adminLogs, locale) : null;
  return (
    <TerminalNestedBlock className="min-w-0 transition hover:border-white/10 hover:bg-white/[0.03]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Link to={href} className="group inline-flex min-w-0 items-center gap-2">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-xl border border-cyan-300/15 bg-cyan-400/10 text-cyan-100">
              <UserRound className="size-4" aria-hidden="true" />
            </span>
            <span className="min-w-0">
              <span className="block truncate text-base font-semibold text-white group-hover:text-cyan-100">
                {text(user.displayName || user.username)}
              </span>
              <span className="block truncate font-mono text-[11px] text-white/42">{user.id}</span>
            </span>
          </Link>
        </div>
        <div className="flex flex-wrap justify-end gap-1.5">
          <TerminalChip variant={statusChipVariant(user.isActive ? 'active' : 'inactive')}>{user.isActive ? '活跃' : '停用'}</TerminalChip>
          <TerminalChip variant="neutral">{user.role === 'admin' ? '管理员' : user.role}</TerminalChip>
        </div>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2 text-[11px] text-white/44 md:grid-cols-4">
        <p className="min-w-0">密码 <span className="block truncate text-white/70">{passwordStateLabel(user.passwordState)}</span></p>
        <p className="min-w-0">活跃会话 <span className="block font-mono text-white/70">{user.sessionSummary.activeCount}</span></p>
        <p className="min-w-0">最近活动 <span className="block truncate font-mono text-white/70">{formatDate(user.lastSeenAt)}</span></p>
        <p className="min-w-0">创建时间 <span className="block truncate font-mono text-white/70">{formatDate(user.createdAt)}</span></p>
      </div>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 flex-wrap gap-1.5">
          {user.riskBadges.length > 0 ? user.riskBadges.map((badge) => (
            <TerminalChip key={`${badge.code}-${badge.label}`} variant={riskChipVariant(badge.severity)}>{badge.label}</TerminalChip>
          )) : (
            <span className="text-xs text-white/38">暂无风险标签</span>
          )}
        </div>
        {adminLogs ? (
          <Link to={adminLogs} className={TERMINAL_LINK_ACTION_CLASSNAME}>
            Admin Logs
            <ExternalLink className="size-3" aria-hidden="true" />
          </Link>
        ) : null}
      </div>
    </TerminalNestedBlock>
  );
};

const DirectoryView: React.FC<{
  state: LoadState<AdminUserListResponse>;
  filters: AdminUserListParams;
  setFilters: (next: AdminUserListParams) => void;
  reload: () => void;
  canReadOpsLogs: boolean;
}> = ({ state, filters, setFilters, reload, canReadOpsLogs }) => {
  const { language } = useI18n();
  const users = state.data?.items || [];
  return (
    <TerminalGrid className="min-h-0">
      <div className="xl:col-span-3">
        <TerminalPanel as="aside" dense className="sticky top-0">
          <TerminalSectionHeader eyebrow="过滤" title="安全搜索" />
          <div className="mt-4 grid gap-4">
            <Input
              label="关键词"
              value={filters.q || ''}
              placeholder="用户 ID / 用户名 / 展示名"
              onChange={(event) => setFilters({ ...filters, q: event.target.value, offset: 0 })}
            />
            <Select
              label="角色"
              value={filters.role || ''}
              options={ROLE_OPTIONS}
              onChange={(role) => setFilters({ ...filters, role, offset: 0 })}
            />
            <Select
              label="状态"
              value={filters.status || 'all'}
              options={USER_STATUS_OPTIONS}
              onChange={(status) => setFilters({ ...filters, status, offset: 0 })}
            />
            <Select
              label="排序"
              value={filters.sort || 'created_at_desc'}
              options={[
                { value: 'created_at_desc', label: '创建时间倒序' },
                { value: 'created_at_asc', label: '创建时间正序' },
                { value: 'updated_at_desc', label: '更新时间倒序' },
                { value: 'username_asc', label: '用户名 A-Z' },
                { value: 'last_seen_desc', label: '最近活动倒序' },
              ]}
              onChange={(sort) => setFilters({ ...filters, sort, offset: 0 })}
            />
            <TerminalButton type="button" variant="secondary" className="h-10 text-sm" onClick={reload}>
              <Search className="size-4" aria-hidden="true" />
              刷新目录
            </TerminalButton>
            <TerminalNotice variant="info">
              查看目录只记录管理员访问范围，不记录搜索原文或凭证值。
            </TerminalNotice>
          </div>
        </TerminalPanel>
      </div>
      <div className="min-w-0 xl:col-span-9">
        <TerminalPanel as="section" dense className="min-h-0">
            <TerminalSectionHeader
            eyebrow="目录"
            title="用户目录"
            action={<TerminalChip variant="neutral">{state.data ? `${state.data.total} 名用户` : '读取中'}</TerminalChip>}
          />
          <TerminalNotice variant="neutral" className="mt-3">
            目录只展示脱敏摘要、状态标签和可审计的跳转线索，不展示敏感凭证字段、会话原文或底层调试载荷。
          </TerminalNotice>
          {state.error ? (
            <div className="mt-4">
              <p className="mb-2 text-sm font-semibold text-rose-100">读取用户目录失败</p>
              <ApiErrorAlert error={state.error} />
            </div>
          ) : null}
          {state.loading ? (
            <div className="mt-4 grid gap-3">
              {[0, 1, 2].map((item) => <LoadingNestedCard key={item} data-testid="admin-users-loading-directory-card" />)}
            </div>
          ) : users.length === 0 && !state.error ? (
            <TerminalEmptyState className="mt-4" title="暂无符合条件的用户">
              调整筛选条件或刷新目录后重试。
            </TerminalEmptyState>
          ) : (
            <TerminalDenseList className="mt-4 gap-3">
              {users.map((user) => <UserRow key={user.id} user={user} locale={language} canReadOpsLogs={canReadOpsLogs} />)}
            </TerminalDenseList>
          )}
        </TerminalPanel>
      </div>
    </TerminalGrid>
  );
};

const DetailTabs: React.FC<{
  active: PageMode;
  activeDetailTab: DetailTabKey;
  userId: string;
  locale: 'zh' | 'en';
  canReadUserActivity: boolean;
  canReadUserPortfolio: boolean;
  canWriteUserSecurity: boolean;
}> = ({ active, activeDetailTab, userId, locale, canReadUserActivity, canReadUserPortfolio, canWriteUserSecurity }) => {
  const base = locale === 'en' ? `/en/admin/users/${encodeURIComponent(userId)}` : `/zh/admin/users/${encodeURIComponent(userId)}`;
  const items = [
    { key: 'detail', label: '概览', href: base, disabled: false },
    { key: 'activity', label: '活动', href: `${base}/activity`, disabled: !canReadUserActivity },
    { key: 'portfolio', label: '组合', href: `${base}?tab=portfolio`, disabled: !canReadUserPortfolio },
    { key: 'security', label: '安全', href: `${base}?tab=security`, disabled: !canWriteUserSecurity },
    { key: 'analysis', label: '分析', href: '#analysis', disabled: true },
    { key: 'scanner', label: 'Scanner', href: '#scanner', disabled: true },
    { key: 'backtest', label: 'Backtest', href: '#backtest', disabled: true },
    { key: 'audit', label: '管理审计', href: '#audit', disabled: true },
  ];
  return (
    <nav className="flex gap-2 overflow-x-auto no-scrollbar" aria-label="用户详情标签">
      {items.map((item) => item.disabled ? (
        <span key={item.key} className={TERMINAL_DISABLED_TAB_CLASSNAME}>
          {item.label} · 后续
        </span>
      ) : (
        <Link
          key={item.key}
          to={item.href}
          className={cn(
            'inline-flex min-h-9 shrink-0 items-center rounded-lg border px-3 py-1.5 text-xs font-medium transition-all duration-300',
            (active === 'activity' && item.key === 'activity') || (active === 'detail' && activeDetailTab === item.key)
              ? TERMINAL_ACTIVE_TAB_CLASSNAME
              : TERMINAL_IDLE_TAB_CLASSNAME,
          )}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
};

const SessionList: React.FC<{ sessions: AdminSessionSummary[] }> = ({ sessions }) => (
  <TerminalPanel as="section" dense>
    <TerminalSectionHeader eyebrow="会话" title="最近脱敏会话" />
    {sessions.length === 0 ? (
      <TerminalEmptyState className="mt-4" title="暂无会话摘要" />
    ) : (
      <TerminalDenseList className="mt-4 gap-3">
        {sessions.map((session) => (
          <TerminalNestedBlock key={session.sessionHandle}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-mono text-sm font-semibold text-white">{session.sessionHandle}</span>
              <TerminalChip variant={statusChipVariant(session.status)}>{statusLabel(session.status)}</TerminalChip>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-white/44 md:grid-cols-4">
              <p>创建 <span className="block truncate font-mono text-white/68">{formatDate(session.createdAt)}</span></p>
              <p>最近 <span className="block truncate font-mono text-white/68">{formatDate(session.lastSeenAt)}</span></p>
              <p>过期 <span className="block truncate font-mono text-white/68">{formatDate(session.expiresAt)}</span></p>
              <p>撤销 <span className="block truncate font-mono text-white/68">{formatDate(session.revokedAt)}</span></p>
            </div>
          </TerminalNestedBlock>
        ))}
      </TerminalDenseList>
    )}
  </TerminalPanel>
);

const FuturePlaceholders: React.FC = () => (
  <TerminalPanel as="section" dense>
    <TerminalSectionHeader eyebrow="边界" title="后续能力占位" />
    <div className="mt-4 grid gap-3">
      <TerminalNotice variant="neutral">安全控制只保留本阶段允许的只读与显式确认能力，不扩展到重置密码或 RBAC 变更。</TerminalNotice>
      <TerminalDisclosure title="后续阶段占位" summary="默认收起">
        <div className="grid gap-2 text-xs leading-5 text-white/48">
          <p>组合、分析、Scanner、Backtest 管理视图等待独立后端合同。</p>
          <p>原始数据库浏览器、原始 prompt、provider 载荷与堆栈明细不在本阶段展示。</p>
        </div>
      </TerminalDisclosure>
    </div>
  </TerminalPanel>
);

const PortfolioTab: React.FC<{
  summaryState: LoadState<AdminPortfolioSummaryResponse>;
  holdingsState: LoadState<AdminHoldingListResponse>;
  activityState: LoadState<AdminPortfolioActivityResponse>;
}> = ({ summaryState, holdingsState, activityState }) => {
  const summary = summaryState.data;
  const holdings = holdingsState.data?.items || [];
  const activities = activityState.data?.items || [];
  const brokerStatuses = Object.entries(summary?.brokerSyncSummary.statuses || {});
  return (
    <TerminalGrid className="min-h-0">
      <div className="min-w-0 xl:col-span-8">
        <TerminalPanel as="section" dense>
          <TerminalSectionHeader
            eyebrow="组合投影"
            title="组合只读总览"
            action={<TerminalChip variant="info">只读投影</TerminalChip>}
          />
          <p className="mt-3 max-w-2xl text-xs leading-5 text-white/46">仅展示账户、估值、持仓和账本活动的安全投影；不会触发同步、导入、重放、汇率刷新或组合数据修改。</p>
          {summaryState.error ? (
            <div className="mt-4">
              <ApiErrorAlert error={summaryState.error} />
            </div>
          ) : null}
          {summaryState.loading && !summary ? (
            <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
              {[0, 1, 2, 3].map((item) => <LoadingNestedCard key={item} className="min-h-[80px]" />)}
            </div>
          ) : summary ? (
            <>
              <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
                <TerminalMetric label="账户数" value={`${summary.accountCount} / ${summary.activeAccountCount}`} valueClassName={cn('text-xl font-semibold', metricValueTone('info'))} />
                <TerminalMetric label="现金" value={formatMoney(summary.totalCash)} valueClassName={cn('text-xl font-semibold', metricValueTone('neutral'))} />
                <TerminalMetric label="市值" value={formatMoney(summary.totalMarketValue)} valueClassName={cn('text-xl font-semibold', metricValueTone('good'))} />
                <TerminalMetric label="权益" value={formatMoney(summary.totalEquity)} valueClassName={cn('text-xl font-semibold', metricValueTone('good'))} />
                <TerminalMetric label="已实现 P&L" value={formatMoney(summary.realizedPnl)} valueClassName={cn('text-xl font-semibold', metricValueTone(summary.realizedPnl.amount >= 0 ? 'good' : 'danger'))} />
                <TerminalMetric label="未实现 P&L" value={formatMoney(summary.unrealizedPnl)} valueClassName={cn('text-xl font-semibold', metricValueTone(summary.unrealizedPnl.amount >= 0 ? 'good' : 'danger'))} />
                <TerminalMetric label="交易/现金/公司行动" value={`${summary.ledgerCounts.trades}/${summary.ledgerCounts.cashEvents}/${summary.ledgerCounts.corporateActions}`} valueClassName={cn('text-xl font-semibold', metricValueTone('info'))} />
                <TerminalMetric label="币种" value={summary.baseCurrencies.join(' / ') || '--'} valueClassName={cn('text-xl font-semibold', metricValueTone('neutral'))} />
              </div>
              {summary.accountCount === 0 ? (
                <TerminalEmptyState className="mt-5" title="该用户暂无组合账户" />
              ) : (
                <div className="mt-5">
                  <TerminalSectionHeader eyebrow="账户" title="组合账户" />
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    {summary.accounts.map((account) => (
                      <TerminalNestedBlock key={account.id}>
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p className="truncate text-sm font-semibold text-white">{account.name}</p>
                            <p className="mt-1 truncate font-mono text-[11px] text-white/42">{text(account.brokerAccountHandle, '已脱敏')}</p>
                          </div>
                          <TerminalChip variant={statusChipVariant(account.isActive ? 'active' : 'inactive')}>{account.isActive ? '活跃' : '停用'}</TerminalChip>
                        </div>
                        <div className="mt-3 grid grid-cols-3 gap-2 text-[11px] text-white/44">
                          <span>券商 <b className="block truncate text-white/70">{text(account.broker)}</b></span>
                          <span>市场 <b className="block truncate text-white/70">{text(account.market)}</b></span>
                          <span>币种 <b className="block truncate text-white/70">{text(account.baseCurrency)}</b></span>
                        </div>
                      </TerminalNestedBlock>
                    ))}
                  </div>
                </div>
              )}
              <TerminalNotice variant="info" className="mt-5">
                经纪商同步摘要：{summary.brokerSyncSummary.connections} 条连接 · 最近同步 {formatDate(summary.brokerSyncSummary.lastSyncAt)} · 汇率 {summary.brokerSyncSummary.fxStale ? '过期' : '最新'}
                {brokerStatuses.length ? ` · ${brokerStatuses.map(([key, value]) => `${key}:${value}`).join(' ')}` : ''}
              </TerminalNotice>
              {summary.limitations.length ? (
                <div className="mt-4 flex flex-wrap gap-2">
                  {summary.limitations.map((item) => <TerminalChip key={item} variant="neutral">{limitationText(item)}</TerminalChip>)}
                </div>
              ) : null}
            </>
          ) : null}
        </TerminalPanel>
      </div>
      <div className="grid min-w-0 gap-5 xl:col-span-4">
        <TerminalPanel as="section" dense>
          <TerminalSectionHeader eyebrow="护栏" title="限制 / 审计感知" />
          <div className="mt-4 grid gap-2">
            <TerminalNotice variant="neutral">组合视图只读，不提供修正、导入、同步、重放或外部调用按钮。</TerminalNotice>
            <TerminalNotice variant="info">经纪商账户仅显示脱敏 handle；底层同步细节和凭证材料不会进入界面。</TerminalNotice>
          </div>
        </TerminalPanel>
      </div>
      <div className="min-w-0 xl:col-span-7">
        <TerminalPanel as="section" dense>
          <TerminalSectionHeader eyebrow="持仓" title="持仓明细" />
          {holdingsState.error ? <div className="mt-3"><ApiErrorAlert error={holdingsState.error} /></div> : null}
          {holdingsState.loading && holdings.length === 0 ? (
            <LoadingNestedCard className="mt-4" />
          ) : holdings.length === 0 ? (
            <TerminalEmptyState className="mt-4" title="暂无持仓" />
          ) : (
            <TerminalDenseTable className="mt-4 border-white/6 bg-black/15">
              <table className="w-full min-w-[620px] text-left text-xs">
                <thead className="text-white/34">
                  <tr>
                    <th className="py-2 pr-3">标的</th>
                    <th className="py-2 pr-3">账户</th>
                    <th className="py-2 pr-3">数量</th>
                    <th className="py-2 pr-3">市值</th>
                    <th className="py-2 pr-3">未实现 P&L</th>
                    <th className="py-2">汇率</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 text-white/62">
                  {holdings.map((item) => (
                    <tr key={`${item.accountId}-${item.symbol}`}>
                      <td className="py-3 pr-3 font-mono text-white">{item.symbol}</td>
                      <td className="py-3 pr-3">{item.accountName}</td>
                      <td className="py-3 pr-3 font-mono">{compactNumber(item.quantity)}</td>
                      <td className="py-3 pr-3 font-mono">{formatCurrency(item.marketValueBase, { currency: item.valuationCurrency || item.currency || 'USD' })}</td>
                      <td className={cn('py-3 pr-3 font-mono', item.unrealizedPnlBase >= 0 ? 'text-emerald-300' : 'text-rose-300')}>{formatCurrency(item.unrealizedPnlBase, { currency: item.valuationCurrency || item.currency || 'USD' })}</td>
                      <td className="py-3">{item.fxStatus}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TerminalDenseTable>
          )}
        </TerminalPanel>
      </div>
      <div className="min-w-0 xl:col-span-5">
        <TerminalPanel as="section" dense>
          <TerminalSectionHeader eyebrow="活动" title="组合活动" />
          {activityState.error ? <div className="mt-3"><ApiErrorAlert error={activityState.error} /></div> : null}
          {activityState.loading && activities.length === 0 ? (
            <LoadingNestedCard className="mt-4" />
          ) : activities.length === 0 ? (
            <TerminalEmptyState className="mt-4" title="暂无组合活动" />
          ) : (
            <TerminalDenseList className="mt-4 gap-3">
              {activities.slice(0, 8).map((item) => (
                <TerminalNestedBlock key={item.idHash}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-mono text-sm font-semibold text-white">{item.symbol || item.type}</p>
                      <p className="mt-1 text-[11px] text-white/42">{item.accountName} · {formatDate(item.eventDate)}</p>
                    </div>
                    <TerminalChip variant="neutral">{item.type}</TerminalChip>
                  </div>
                  <p className="mt-2 truncate text-[11px] text-white/50">
                    {text(item.side || item.direction || item.actionType, 'activity')} · 数量 {text(item.quantity)} · 金额 {text(item.amount)}
                  </p>
                </TerminalNestedBlock>
              ))}
            </TerminalDenseList>
          )}
        </TerminalPanel>
      </div>
    </TerminalGrid>
  );
};

const UnavailableAdminCapability: React.FC<{ title: string; description: string }> = ({ title, description }) => (
  <TerminalPanel as="section" dense>
    <TerminalSectionHeader eyebrow="权限边界" title={title} />
    <TerminalNotice variant="caution" className="mt-4">{description}</TerminalNotice>
  </TerminalPanel>
);

const SecurityActionCard: React.FC<{
  actionKey: SecurityActionKey;
  title: string;
  description: string;
  confirmPhrase: string;
  buttonLabel: string;
  available: boolean;
  danger?: boolean;
  state: SecurityActionFormState;
  onChange: (patch: Partial<SecurityActionFormState>) => void;
  onSubmit: () => void;
}> = ({ actionKey, title, description, confirmPhrase, buttonLabel, available, danger = false, state, onChange, onSubmit }) => {
  const canSubmit = available && state.reason.trim().length > 0 && state.confirm === confirmPhrase && !state.loading;
  return (
    <TerminalNestedBlock data-testid={`security-action-${actionKey.replace('_sessions', '-sessions')}`} className={danger ? 'border-rose-400/16' : ''}>
      <TerminalSectionHeader
        eyebrow="安全操作"
        title={title}
        action={<TerminalChip variant={available ? (danger ? 'danger' : 'caution') : 'neutral'}>{available ? '可执行' : '当前状态不可用'}</TerminalChip>}
      />
      <p className="mt-3 max-w-xl text-xs leading-5 text-white/46">{description}</p>
      <TerminalNotice variant={danger ? 'danger' : 'neutral'} className="mt-3">
        操作需要填写审计原因并输入确认短语；响应仅返回脱敏结果和审计事件编号。
      </TerminalNotice>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <Input
          label="操作原因"
          value={state.reason}
          disabled={!available || state.loading}
          placeholder="请输入审计原因"
          onChange={(event) => onChange({ reason: event.target.value })}
        />
        <Input
          label={`输入 ${confirmPhrase} 确认`}
          value={state.confirm}
          disabled={!available || state.loading}
          placeholder={confirmPhrase}
          onChange={(event) => onChange({ confirm: event.target.value })}
        />
      </div>
      {actionKey === 'disable' ? (
        <Checkbox
          label="同时撤销活跃会话"
          checked={state.revokeSessions}
          disabled={!available || state.loading}
          containerClassName="mt-4"
          onChange={(event) => onChange({ revokeSessions: event.target.checked })}
        />
      ) : null}
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <TerminalButton type="button" variant={danger ? 'danger' : 'secondary'} disabled={!canSubmit} onClick={onSubmit}>
          {buttonLabel}
        </TerminalButton>
        {!available ? <span className="text-xs text-white/35">账户当前状态不适用该操作。</span> : null}
      </div>
      {state.error ? (
        <div className="mt-4">
          <ApiErrorAlert error={state.error} />
        </div>
      ) : null}
      {state.result ? (
        <TerminalNotice variant="neutral" className="mt-4">
          <div className="flex flex-wrap items-center gap-2">
            <TerminalChip variant="success">已记录审计结果</TerminalChip>
            <p>状态: {statusLabel(state.result.status)} · 会话撤销 {state.result.sessionsRevoked}</p>
          </div>
          {state.result.auditEventId ? <p className="mt-1 font-mono text-emerald-100">{state.result.auditEventId}</p> : null}
        </TerminalNotice>
      ) : null}
    </TerminalNestedBlock>
  );
};

const SecurityTab: React.FC<{
  detail: AdminUserDetailResponse;
  actionState: Record<SecurityActionKey, SecurityActionFormState>;
  updateAction: (key: SecurityActionKey, patch: Partial<SecurityActionFormState>) => void;
  submitAction: (key: SecurityActionKey) => void;
}> = ({ detail, actionState, updateAction, submitAction }) => {
  const user = detail.user;
  return (
    <TerminalGrid className="min-h-0">
      <div className="min-w-0 xl:col-span-4">
        <TerminalPanel as="section" dense>
          <TerminalSectionHeader eyebrow="安全 S1" title="安全控制 S1" />
          <div className="mt-5 grid grid-cols-2 gap-3">
            <TerminalMetric label="账户状态" value={user.isActive ? '活跃' : '停用'} valueClassName={cn('text-xl font-semibold', metricValueTone(user.isActive ? 'good' : 'danger'))} />
            <TerminalMetric label="活跃会话" value={user.sessionSummary.activeCount} valueClassName={cn('text-xl font-semibold', metricValueTone('info'))} />
            <TerminalMetric label="密码状态" value={passwordStateLabel(user.passwordState)} valueClassName={cn('text-xl font-semibold', metricValueTone(user.passwordState === 'unset' ? 'warn' : 'neutral'))} />
            <TerminalMetric label="角色" value={user.role === 'admin' ? '管理员' : user.role} valueClassName={cn('text-xl font-semibold', metricValueTone('neutral'))} />
          </div>
          <TerminalNotice variant="info" className="mt-4">
            安全状态查看和控制操作都会被审计；响应不会返回敏感凭证字段、原始会话标识或底层调试材料。
          </TerminalNotice>
          <TerminalDisclosure title="后续阶段占位" summary="默认收起" className="mt-4">
            <div className="grid gap-2 text-xs text-white/42">
              <p>reset-password 后续阶段，不在本次实现。</p>
              <p>force-password-change 后续阶段，不在本次实现。</p>
              <p>unlock / RBAC capability model 后续阶段，不在本次实现。</p>
            </div>
          </TerminalDisclosure>
        </TerminalPanel>
      </div>
      <div className="grid min-w-0 gap-5 xl:col-span-8">
        <TerminalPanel as="section" dense>
          <TerminalSectionHeader eyebrow="危险区" title="安全操作区" action={<TerminalChip variant="danger">隔离显示</TerminalChip>} />
          <TerminalNotice variant="danger" className="mt-3">
            危险操作与状态查看分区显示。禁用、启用和撤销会话保留原有权限、确认短语和审计链路，不暴露原始会话或凭证材料。
          </TerminalNotice>
          <div className="mt-4 grid gap-4">
        {user.isActive ? (
          <SecurityActionCard
            actionKey="disable"
            title="禁用账户"
            description="停用目标用户账户。可选择同步撤销活跃会话；不会展示任何凭证或原始会话值。"
            confirmPhrase="DISABLE"
            buttonLabel="禁用账户"
            available
            danger
            state={actionState.disable}
            onChange={(patch) => updateAction('disable', patch)}
            onSubmit={() => submitAction('disable')}
          />
        ) : (
          <SecurityActionCard
            actionKey="enable"
            title="启用账户"
            description="恢复目标用户账户访问状态。该操作仍需审计原因和确认短语。"
            confirmPhrase="ENABLE"
            buttonLabel="启用账户"
            available
            state={actionState.enable}
            onChange={(patch) => updateAction('enable', patch)}
            onSubmit={() => submitAction('enable')}
          />
        )}
        <SecurityActionCard
          actionKey="revoke_sessions"
          title="撤销全部会话"
          description="撤销目标用户全部应用会话，仅返回数量和审计结果，不返回任何原始会话标识。"
          confirmPhrase="REVOKE_SESSIONS"
          buttonLabel="撤销全部会话"
          available
          danger
          state={actionState.revoke_sessions}
          onChange={(patch) => updateAction('revoke_sessions', patch)}
          onSubmit={() => submitAction('revoke_sessions')}
        />
          </div>
        </TerminalPanel>
      </div>
    </TerminalGrid>
  );
};

const DetailOverview: React.FC<{ detail: AdminUserDetailResponse; locale: 'zh' | 'en'; canReadOpsLogs: boolean }> = ({ detail, locale, canReadOpsLogs }) => {
  const { user } = detail;
  const adminLogs = canReadOpsLogs ? adminLogHref(detail.dataLinks.adminLogs || user.links?.adminLogs, locale) : null;
  return (
    <TerminalGrid className="min-h-0">
      <div className="min-w-0 xl:col-span-8">
        <TerminalPanel as="section" dense>
          <TerminalSectionHeader
            eyebrow="身份总览"
            title={text(user.displayName || user.username)}
            action={(
              <div className="flex flex-wrap gap-2">
                <TerminalChip variant={statusChipVariant(user.isActive ? 'active' : 'inactive')}>{user.isActive ? '活跃' : '停用'}</TerminalChip>
                <TerminalChip variant="neutral">{user.role === 'admin' ? '管理员' : user.role}</TerminalChip>
              </div>
            )}
          />
          <p className="mt-1 truncate font-mono text-xs text-white/42">{user.id}</p>
          <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
            <TerminalMetric label="活跃会话" value={user.sessionSummary.activeCount} valueClassName={cn('text-xl font-semibold', metricValueTone('good'))} />
            <TerminalMetric label="过期会话" value={user.sessionSummary.expiredCount} valueClassName={cn('text-xl font-semibold', metricValueTone('warn'))} />
            <TerminalMetric label="撤销会话" value={user.sessionSummary.revokedCount} valueClassName={cn('text-xl font-semibold', metricValueTone('info'))} />
            <TerminalMetric label="密码状态" value={passwordStateLabel(user.passwordState)} valueClassName={cn('text-xl font-semibold', metricValueTone(user.passwordState === 'unset' ? 'warn' : 'neutral'))} />
          </div>
          <div className="mt-5 grid grid-cols-1 gap-3 text-sm text-white/52 md:grid-cols-2">
            <TerminalNestedBlock>创建时间 <span className="block font-mono text-white/72">{formatDate(user.createdAt)}</span></TerminalNestedBlock>
            <TerminalNestedBlock>更新时间 <span className="block font-mono text-white/72">{formatDate(user.updatedAt)}</span></TerminalNestedBlock>
            <TerminalNestedBlock>最近活动 <span className="block font-mono text-white/72">{formatDate(user.lastSeenAt)}</span></TerminalNestedBlock>
            <TerminalNestedBlock>下一会话过期 <span className="block font-mono text-white/72">{formatDate(user.sessionSummary.nextExpiresAt)}</span></TerminalNestedBlock>
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            {user.riskBadges.length > 0 ? user.riskBadges.map((badge) => (
              <TerminalChip key={badge.code} variant={riskChipVariant(badge.severity)}>{badge.label}</TerminalChip>
            )) : <span className="text-xs text-white/38">暂无风险标签</span>}
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            {adminLogs ? (
              <Link to={adminLogs} className={TERMINAL_LINK_ACTION_CLASSNAME}>
                查看 Admin Logs
                <ExternalLink className="size-3" aria-hidden="true" />
              </Link>
            ) : null}
            <TerminalChip variant="neutral">当前面板只读</TerminalChip>
          </div>
        </TerminalPanel>
      </div>
      <div className="grid min-w-0 gap-5 xl:col-span-4">
        <TerminalPanel as="section" dense>
          <TerminalSectionHeader eyebrow="审计" title="访问提示" />
          <TerminalNotice variant="info" className="mt-4">
            打开用户详情会记录目标用户和管理员身份。响应不包含敏感凭证字段、原始会话值或底层调试材料。
          </TerminalNotice>
        </TerminalPanel>
        <TerminalPanel as="section" dense>
          <TerminalSectionHeader eyebrow="限制" title="已知限制" />
          {detail.limitations.length > 0 ? (
            <TerminalDisclosure title="限制条目" summary={`${detail.limitations.length} 项，默认收起`} className="mt-4">
              <div className="grid gap-2">
                {detail.limitations.map((item) => (
                  <TerminalNotice key={item} variant="neutral">{item.replace(/_/g, ' ')}</TerminalNotice>
                ))}
              </div>
            </TerminalDisclosure>
          ) : (
            <TerminalEmptyState className="mt-4" title="暂无限制说明" />
          )}
        </TerminalPanel>
      </div>
      <div className="min-w-0 xl:col-span-7"><SessionList sessions={detail.sessions} /></div>
      <div className="min-w-0 xl:col-span-5"><FuturePlaceholders /></div>
    </TerminalGrid>
  );
};

const ActivityFilters: React.FC<{
  filters: AdminActivityParams;
  onChange: (next: AdminActivityParams) => void;
  onRefresh: () => void;
}> = ({ filters, onChange, onRefresh }) => {
  const toggle = (key: 'includeAdmin' | 'includeSystem') => onChange({ ...filters, [key]: !filters[key], offset: 0 });
  return (
    <TerminalPanel as="aside" dense className="sticky top-0">
      <TerminalSectionHeader eyebrow="时间线" title="活动筛选" />
      <div className="mt-5 grid gap-4">
        <Input label="安全查询" value={filters.q || ''} placeholder="action / symbol / hash" onChange={(event) => onChange({ ...filters, q: event.target.value, offset: 0 })} />
        <Select label="事件族群" value={filters.family || ''} options={ACTIVITY_FAMILY_OPTIONS} onChange={(family) => onChange({ ...filters, family, offset: 0 })} />
        <Select label="结果" value={filters.status || ''} options={ACTIVITY_STATUS_OPTIONS} onChange={(status) => onChange({ ...filters, status, offset: 0 })} />
        <Select label="对象类型" value={filters.entityType || ''} options={ENTITY_TYPE_OPTIONS} onChange={(entityType) => onChange({ ...filters, entityType, offset: 0 })} />
        <Select label="发起方" value={filters.actorType || ''} options={ACTOR_TYPE_OPTIONS} onChange={(actorType) => onChange({ ...filters, actorType, offset: 0 })} />
        <div className="grid grid-cols-2 gap-2">
          <TerminalButton type="button" variant="compact" aria-pressed={filters.includeAdmin} className={filters.includeAdmin ? TERMINAL_ACTIVE_TOGGLE_CLASSNAME : ''} onClick={() => toggle('includeAdmin')}>
            管理访问
          </TerminalButton>
          <TerminalButton type="button" variant="compact" aria-pressed={filters.includeSystem} className={filters.includeSystem ? TERMINAL_ACTIVE_TOGGLE_CLASSNAME : ''} onClick={() => toggle('includeSystem')}>
            系统事件
          </TerminalButton>
        </div>
        <TerminalButton type="button" variant="secondary" className="h-10 text-sm" onClick={onRefresh}>
          刷新活动
        </TerminalButton>
        <TerminalNotice variant="info">
          访问活动时间线会写入目标用户级审计事件。
        </TerminalNotice>
      </div>
    </TerminalPanel>
  );
};

const ActivityEventCard: React.FC<{ event: AdminActivityEvent }> = ({ event }) => {
  const entries = safeMetadataEntries(event.redactedMetadata);
  const hiddenCount = sensitiveFieldCount(event.redactedMetadata);
  return (
    <TerminalNestedBlock className="relative">
      <div className="absolute left-5 top-5 size-2.5 rounded-full border border-cyan-200/60 bg-cyan-300 shadow-[0_0_18px_rgba(103,232,249,0.28)]" aria-hidden="true" />
      <div className="pl-7">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="font-mono text-[11px] text-white/42">{formatDate(event.timestamp)}</p>
            <h3 className="mt-1 truncate text-base font-semibold text-white">{event.action}</h3>
            <p className="mt-1 truncate text-sm text-white/50">
              {text(event.actor.label || event.actor.type)} {'->'} {text(event.entity.label || event.entity.symbol || event.entity.type)}
            </p>
          </div>
          <div className="flex flex-wrap justify-end gap-1.5">
            <TerminalChip variant="info">{event.family}</TerminalChip>
            <TerminalChip variant={statusChipVariant(event.status)}>{statusLabel(event.status)}</TerminalChip>
          </div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-2 text-[11px] text-white/44 md:grid-cols-4">
          <p>对象 <span className="block truncate text-white/68">{event.entity.type}</span></p>
          <p>结果 <span className="block truncate text-white/68">{statusLabel(event.outcome)}</span></p>
          <p>请求哈希 <span className="block truncate font-mono text-white/68">{text(event.requestIdHash)}</span></p>
          <p>会话哈希 <span className="block truncate font-mono text-white/68">{text(event.sessionIdHash)}</span></p>
        </div>
        <TerminalDisclosure title="脱敏元数据" summary="默认收起" className="mt-4">
          {entries.length === 0 && hiddenCount === 0 ? (
            <p className="text-xs text-white/42">暂无可展示元数据</p>
          ) : (
            <dl className="grid gap-2 text-[11px] leading-5 text-white/50 sm:grid-cols-2">
              {entries.map(([key, value]) => (
                <div key={key} className="min-w-0">
                  <dt className="truncate text-white/34">{key}</dt>
                  <dd className="break-words font-mono text-white/62">{value}</dd>
                </div>
              ))}
              {hiddenCount > 0 ? (
                <div className="min-w-0">
                  <dt className="text-white/34">脱敏</dt>
                  <dd className="text-amber-100/72">{hiddenCount} 个敏感字段已屏蔽</dd>
                </div>
              ) : null}
            </dl>
          )}
        </TerminalDisclosure>
      </div>
    </TerminalNestedBlock>
  );
};

const ActivityTimeline: React.FC<{
  state: LoadState<AdminActivityResponse>;
  filters: AdminActivityParams;
  setFilters: (next: AdminActivityParams) => void;
  reload: () => void;
}> = ({ state, filters, setFilters, reload }) => {
  const items = state.data?.items || [];
  return (
    <TerminalGrid className="min-h-0">
      <div className="xl:col-span-3"><ActivityFilters filters={filters} onChange={setFilters} onRefresh={reload} /></div>
      <div className="min-w-0 xl:col-span-9">
        <TerminalPanel as="section" dense>
          <TerminalSectionHeader
            eyebrow="活动"
            title="活动时间线"
            action={<TerminalChip variant="neutral">{state.data ? `${state.data.total} 条事件` : '读取中'}</TerminalChip>}
          />
          {state.data?.window ? (
            <TerminalNotice variant="neutral" className="mt-3">
              {formatDate(state.data.window.from)} - {formatDate(state.data.window.to)}
            </TerminalNotice>
          ) : null}
          {state.error ? (
            <div className="mt-4">
              <p className="mb-2 text-sm font-semibold text-rose-100">读取活动时间线失败</p>
              <ApiErrorAlert error={state.error} />
            </div>
          ) : null}
          {state.loading ? (
            <div className="mt-4 grid gap-3">
              {[0, 1, 2].map((item) => <LoadingNestedCard key={item} className="min-h-[96px]" />)}
            </div>
          ) : items.length === 0 && !state.error ? (
            <TerminalEmptyState className="mt-4" title="当前时间窗口内暂无活动" />
          ) : (
            <TerminalDenseList className="mt-4 gap-3">
              {items.map((event) => <ActivityEventCard key={event.id} event={event} />)}
            </TerminalDenseList>
          )}
          {state.data?.limitations?.length ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {state.data.limitations.map((item) => (
                <TerminalChip key={item} variant="neutral">{item.replace(/_/g, ' ')}</TerminalChip>
              ))}
            </div>
          ) : null}
        </TerminalPanel>
      </div>
    </TerminalGrid>
  );
};

const AdminUsersPage: React.FC = () => {
  const { userId } = useParams<{ userId?: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const { language } = useI18n();
  const {
    canReadUsers,
    canReadUserActivity,
    canReadUserPortfolio,
    canReadOpsLogs,
    canWriteUserSecurity,
  } = useProductSurface();
  const mode: PageMode = userId ? (location.pathname.endsWith('/activity') ? 'activity' : 'detail') : 'directory';
  const activeDetailTab = mode === 'detail' ? tabFromSearch(location.search) : 'detail';
  const [filters, setFilters] = useState<AdminUserListParams>({ status: 'all', sort: 'created_at_desc', limit: USER_LIMIT, offset: 0 });
  const [activityFilters, setActivityFilters] = useState<AdminActivityParams>({ limit: ACTIVITY_LIMIT, offset: 0, includeAdmin: false, includeSystem: false });
  const [usersState, setUsersState] = useState<LoadState<AdminUserListResponse>>({ loading: false, error: null, data: null });
  const [detailState, setDetailState] = useState<LoadState<AdminUserDetailResponse>>({ loading: false, error: null, data: null });
  const [activityState, setActivityState] = useState<LoadState<AdminActivityResponse>>({ loading: false, error: null, data: null });
  const [portfolioSummaryState, setPortfolioSummaryState] = useState<LoadState<AdminPortfolioSummaryResponse>>({ loading: false, error: null, data: null });
  const [holdingsState, setHoldingsState] = useState<LoadState<AdminHoldingListResponse>>({ loading: false, error: null, data: null });
  const [portfolioActivityState, setPortfolioActivityState] = useState<LoadState<AdminPortfolioActivityResponse>>({ loading: false, error: null, data: null });
  const [securityActionState, setSecurityActionState] = useState<Record<SecurityActionKey, SecurityActionFormState>>({
    disable: freshSecurityActionState(),
    enable: freshSecurityActionState(),
    revoke_sessions: freshSecurityActionState(),
  });

  const loadUsers = () => {
    if (!canReadUsers) return;
    setUsersState((state) => ({ ...state, loading: true, error: null }));
    void adminUsersApi.listUsers(filters)
      .then((data) => setUsersState({ loading: false, error: null, data }))
      .catch((error) => setUsersState({ loading: false, error: getParsedApiError(error), data: null }));
  };

  const loadDetail = (targetUserId: string) => {
    if (!canReadUsers) return;
    setDetailState((state) => ({ ...state, loading: true, error: null }));
    void adminUsersApi.getUserDetail(targetUserId)
      .then((data) => setDetailState({ loading: false, error: null, data }))
      .catch((error) => setDetailState({ loading: false, error: getParsedApiError(error), data: null }));
  };

  const loadActivity = (targetUserId: string) => {
    if (!canReadUserActivity) return;
    setActivityState((state) => ({ ...state, loading: true, error: null }));
    void adminUsersApi.listUserActivity(targetUserId, activityFilters)
      .then((data) => setActivityState({ loading: false, error: null, data }))
      .catch((error) => setActivityState({ loading: false, error: getParsedApiError(error), data: null }));
  };

  const loadPortfolio = (targetUserId: string) => {
    if (!canReadUserPortfolio) return;
    setPortfolioSummaryState((state) => ({ ...state, loading: true, error: null }));
    setHoldingsState((state) => ({ ...state, loading: true, error: null }));
    setPortfolioActivityState((state) => ({ ...state, loading: true, error: null }));
    void adminUsersApi.getAdminUserPortfolioSummary(targetUserId, { includeInactive: true })
      .then((data) => setPortfolioSummaryState({ loading: false, error: null, data }))
      .catch((error) => setPortfolioSummaryState({ loading: false, error: sanitizedPortfolioError(error), data: null }));
    void adminUsersApi.getAdminUserHoldings(targetUserId, { limit: 50, offset: 0 })
      .then((data) => setHoldingsState({ loading: false, error: null, data }))
      .catch((error) => setHoldingsState({ loading: false, error: sanitizedPortfolioError(error), data: null }));
    void adminUsersApi.getAdminUserPortfolioActivity(targetUserId, { limit: 30, offset: 0 })
      .then((data) => setPortfolioActivityState({ loading: false, error: null, data }))
      .catch((error) => setPortfolioActivityState({ loading: false, error: sanitizedPortfolioError(error), data: null }));
  };

  const updateSecurityAction = (key: SecurityActionKey, patch: Partial<SecurityActionFormState>) => {
    setSecurityActionState((state) => ({
      ...state,
      [key]: { ...state[key], ...patch, error: patch.error === undefined ? state[key].error : patch.error },
    }));
  };

  const loadUsersForEffect = useEffectEvent(() => {
    loadUsers();
  });

  const loadDetailForEffect = useEffectEvent((targetUserId: string) => {
    loadDetail(targetUserId);
  });

  const loadActivityForEffect = useEffectEvent((targetUserId: string) => {
    loadActivity(targetUserId);
  });

  const loadPortfolioForEffect = useEffectEvent((targetUserId: string) => {
    loadPortfolio(targetUserId);
  });

  const submitSecurityAction = (key: SecurityActionKey) => {
    if (!userId) return;
    const current = securityActionState[key];
    const reason = current.reason.trim();
    setSecurityActionState((state) => ({ ...state, [key]: { ...state[key], loading: true, error: null, result: null } }));
    const request = key === 'disable'
      ? adminUsersApi.disableAdminUser(userId, { reason, confirm: current.confirm, revokeSessions: current.revokeSessions })
      : key === 'enable'
      ? adminUsersApi.enableAdminUser(userId, { reason, confirm: current.confirm })
      : adminUsersApi.revokeAdminUserSessions(userId, { reason, confirm: current.confirm, scope: 'all' });
    void request
      .then((result) => {
        setSecurityActionState((state) => ({
          ...state,
          [key]: { ...state[key], loading: false, error: null, result },
        }));
        loadDetail(userId);
      })
      .catch((error) => setSecurityActionState((state) => ({
        ...state,
        [key]: { ...state[key], loading: false, error: sanitizedActionError(error), result: null },
      })));
  };

  useEffect(() => {
    if (userId) return;
    const timer = window.setTimeout(() => loadUsersForEffect(), 0);
    return () => window.clearTimeout(timer);
  }, [canReadUsers, filters, userId]);

  useEffect(() => {
    if (!userId) return;
    const timer = window.setTimeout(() => loadDetailForEffect(userId), 0);
    return () => window.clearTimeout(timer);
  }, [canReadUsers, userId]);

  useEffect(() => {
    if (!userId || mode !== 'activity') return;
    const timer = window.setTimeout(() => loadActivityForEffect(userId), 0);
    return () => window.clearTimeout(timer);
  }, [activityFilters, canReadUserActivity, mode, userId]);

  useEffect(() => {
    if (!userId || mode !== 'detail' || activeDetailTab !== 'portfolio') return;
    const timer = window.setTimeout(() => loadPortfolioForEffect(userId), 0);
    return () => window.clearTimeout(timer);
  }, [activeDetailTab, canReadUserPortfolio, mode, userId]);

  const activeUser = detailState.data?.user || null;
  const directoryPath = language === 'en' ? '/en/admin/users' : '/zh/admin/users';
  const directoryActiveSessions = (usersState.data?.items || []).reduce((sum, user) => sum + (user.sessionSummary?.activeCount || 0), 0);
  const headerCurrentState = userId
    ? activeUser
      ? `${activeUser.isActive ? '活跃' : '停用'} · ${activeUser.sessionSummary.activeCount} 个活跃会话`
      : detailState.loading
      ? '读取用户详情'
      : '等待用户详情'
    : usersState.data
    ? `${usersState.data.total} 个用户 / ${directoryActiveSessions} 个活跃会话`
    : usersState.loading
    ? '读取用户目录'
    : '等待目录快照';
  const headerNextAction = userId
    ? activeDetailTab === 'security'
      ? '核对审计原因与确认短语'
      : activeDetailTab === 'portfolio'
      ? '核对组合只读投影'
      : mode === 'activity'
      ? '筛选活动时间线'
      : '查看活动、组合或安全页签'
    : '打开用户详情或审计日志';

  const content = (() => {
    if (!userId) {
      return <DirectoryView state={usersState} filters={filters} setFilters={setFilters} reload={loadUsers} canReadOpsLogs={canReadOpsLogs} />;
    }
    if (!canReadUsers) {
      return <UnavailableAdminCapability title="不可查看用户资料" description="当前账号缺少用户治理读取权限，前端不会请求或渲染用户详情。后端授权仍是最终边界。" />;
    }
    if (detailState.loading && !detailState.data) {
      return (
        <TerminalPanel as="section" data-testid="admin-users-loading-detail">
          <div className="grid gap-4">
            <div className="flex flex-wrap gap-2">
              <LoadingBar className="h-6 w-24" />
              <LoadingBar className="h-6 w-20" />
            </div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {[0, 1, 2, 3].map((item) => <LoadingNestedCard key={item} data-testid="admin-users-loading-detail-card" className="min-h-[128px]" />)}
            </div>
          </div>
        </TerminalPanel>
      );
    }
    if (detailState.error) {
      return (
        <TerminalPanel as="section">
          <p className="mb-2 text-sm font-semibold text-rose-100">读取用户详情失败</p>
          <ApiErrorAlert error={detailState.error} />
          <TerminalButton type="button" variant="secondary" className="mt-4 w-fit px-3 text-sm" onClick={() => navigate(directoryPath)}>
            返回用户目录
          </TerminalButton>
        </TerminalPanel>
      );
    }
    if (!detailState.data) return null;
    return (
      <div className="grid gap-5">
        <DetailTabs
          active={mode}
          activeDetailTab={activeDetailTab}
          userId={userId}
          locale={language}
          canReadUserActivity={canReadUserActivity}
          canReadUserPortfolio={canReadUserPortfolio}
          canWriteUserSecurity={canWriteUserSecurity}
        />
        {mode === 'activity'
          ? canReadUserActivity
            ? <ActivityTimeline state={activityState} filters={activityFilters} setFilters={setActivityFilters} reload={() => loadActivity(userId)} />
            : <UnavailableAdminCapability title="不可查看用户活动" description="当前账号缺少用户活动读取权限，前端不会请求或渲染活动时间线。" />
          : activeDetailTab === 'portfolio'
          ? canReadUserPortfolio
            ? <PortfolioTab summaryState={portfolioSummaryState} holdingsState={holdingsState} activityState={portfolioActivityState} />
            : <UnavailableAdminCapability title="不可查看用户组合" description="当前账号缺少组合读取权限，前端不会请求或渲染组合账户、持仓或活动数据。" />
          : activeDetailTab === 'security'
          ? canWriteUserSecurity
            ? <SecurityTab detail={detailState.data} actionState={securityActionState} updateAction={updateSecurityAction} submitAction={submitSecurityAction} />
            : <UnavailableAdminCapability title="不可执行安全操作" description="当前账号缺少用户安全写入权限，前端不会渲染禁用、启用或撤销会话按钮。" />
          : <DetailOverview detail={detailState.data} locale={language} canReadOpsLogs={canReadOpsLogs} />}
      </div>
    );
  })();

  return (
    <div className="flex min-h-0 w-full min-w-0 flex-1 flex-col overflow-y-auto no-scrollbar">
      <TerminalPageShell data-testid="admin-users-page-shell" className="min-h-0 flex-1 overflow-x-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3">
          {userId ? (
            <TerminalButton type="button" variant="secondary" className="px-3 text-xs" onClick={() => navigate(directoryPath)}>
              返回用户目录
            </TerminalButton>
          ) : <span />}
        <div className="flex flex-wrap items-center gap-2">
          <TerminalChip variant="info">
            <Clock3 className="size-3.5" aria-hidden="true" />
              只读 F1/F2
          </TerminalChip>
          <TerminalChip variant="neutral">无原始凭证</TerminalChip>
        </div>
        </div>
        <PageHeader mode={mode} user={activeUser} currentState={headerCurrentState} nextAction={headerNextAction} />
        {content}
        <TerminalNotice variant="caution">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 size-4 text-amber-200" aria-hidden="true" />
            <p className="text-xs leading-5 text-white/46">
              本页面只展示账号、会话和活动的安全投影；凭证材料、原始会话材料、底层调试载荷、模型上下文、第三方原始响应和异常堆栈均不进入界面。
            </p>
          </div>
        </TerminalNotice>
      </TerminalPageShell>
    </div>
  );
};

export default AdminUsersPage;
