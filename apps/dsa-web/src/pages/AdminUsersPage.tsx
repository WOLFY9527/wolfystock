import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  Clock3,
  ExternalLink,
  Fingerprint,
  LockKeyhole,
  Search,
  ShieldCheck,
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
import { ApiErrorAlert, Badge, Button, Checkbox, Disclosure, GlassCard, Input, Select } from '../components/common';
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

function riskTone(severity?: string): string {
  if (severity === 'critical') return 'border-rose-300/35 bg-rose-500/12 text-rose-100';
  if (severity === 'warning') return 'border-amber-300/30 bg-amber-400/10 text-amber-100';
  return 'border-cyan-300/20 bg-cyan-400/8 text-cyan-100';
}

function statusTone(value?: string | null): string {
  const normalized = String(value || '').toLowerCase();
  if (['active', 'success', 'ok'].includes(normalized)) return 'border-emerald-300/25 bg-emerald-400/10 text-emerald-100';
  if (['failed', 'revoked', 'inactive'].includes(normalized)) return 'border-rose-300/30 bg-rose-500/12 text-rose-100';
  if (['partial', 'warning', 'expired', 'timeout'].includes(normalized)) return 'border-amber-300/25 bg-amber-400/10 text-amber-100';
  return 'border-white/10 bg-white/[0.04] text-white/62';
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

const ReadOnlyBadges: React.FC = () => (
  <div className="flex flex-wrap gap-2">
    <Badge variant="info" className="border-cyan-300/25 bg-cyan-400/10 text-cyan-100">只读</Badge>
    <Badge variant="success" className="border-emerald-300/25 bg-emerald-400/10 text-emerald-100">无安全控制</Badge>
    <Badge variant="default" className="border-white/10 bg-white/[0.04] text-white/58">敏感字段脱敏</Badge>
  </div>
);

const SummaryTile: React.FC<{
  label: string;
  value: React.ReactNode;
  tone?: 'neutral' | 'good' | 'warn' | 'danger' | 'info';
}> = ({ label, value, tone = 'neutral' }) => {
  const toneClass = {
    neutral: 'text-white',
    good: 'text-emerald-300',
    warn: 'text-amber-200',
    danger: 'text-rose-200',
    info: 'text-cyan-200',
  }[tone];
  return (
    <div className="min-w-0 rounded-2xl border border-white/5 bg-black/20 px-4 py-3">
      <p className="truncate text-[10px] font-bold uppercase tracking-[0.18em] text-white/34">{label}</p>
      <p className={cn('mt-2 font-mono text-xl font-semibold leading-none', toneClass)}>{value}</p>
    </div>
  );
};

const PageHeader: React.FC<{
  mode: PageMode;
  user?: AdminUserListItem | null;
  currentState: string;
  nextAction: string;
}> = ({ mode, user, currentState, nextAction }) => (
  <GlassCard as="section" className="p-5 md:p-6">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0">
        <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-100/55">Admin Data Control</p>
        <h1 className="mt-2 text-2xl font-semibold text-white md:text-3xl">
          {mode === 'directory' ? '用户数据控制中心' : text(user?.displayName || user?.username, '用户详情')}
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-white/55">账号、会话、组合投影与审计线索的管理员工作台。</p>
      </div>
      <ReadOnlyBadges />
    </div>
    <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-3">
      <div className="min-w-0 rounded-2xl border border-white/5 bg-black/20 px-4 py-3">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/34">页面用途</p>
        <p className="mt-2 text-sm font-semibold text-white">核对账号与会话风险</p>
        <p className="mt-1 text-xs leading-5 text-white/42">用户目录、详情、组合只读投影</p>
      </div>
      <div className="min-w-0 rounded-2xl border border-white/5 bg-black/20 px-4 py-3">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/34">当前状态</p>
        <p className="mt-2 text-sm font-semibold text-white">{currentState}</p>
        <p className="mt-1 text-xs leading-5 text-white/42">敏感字段不进入界面</p>
      </div>
      <div className="min-w-0 rounded-2xl border border-white/5 bg-black/20 px-4 py-3">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/34">下一步</p>
        <p className="mt-2 text-sm font-semibold text-white">{nextAction}</p>
        <p className="mt-1 text-xs leading-5 text-white/42">安全操作需要显式权限与确认</p>
      </div>
    </div>
  </GlassCard>
);

const FilterRail: React.FC<{
  filters: AdminUserListParams;
  onChange: (next: AdminUserListParams) => void;
  onRefresh: () => void;
}> = ({ filters, onChange, onRefresh }) => (
  <GlassCard as="aside" className="p-4 md:p-5">
    <div className="flex items-start gap-3">
      <Search className="mt-1 h-4 w-4 text-cyan-200" aria-hidden="true" />
      <div>
        <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">过滤</p>
        <h2 className="mt-1 text-base font-semibold text-white">安全搜索</h2>
      </div>
    </div>
    <div className="mt-5 grid gap-4">
      <Input
        label="关键词"
        value={filters.q || ''}
        placeholder="用户 ID / 用户名 / 展示名"
        onChange={(event) => onChange({ ...filters, q: event.target.value, offset: 0 })}
      />
      <Select
        label="角色"
        value={filters.role || ''}
        options={ROLE_OPTIONS}
        onChange={(role) => onChange({ ...filters, role, offset: 0 })}
      />
      <Select
        label="状态"
        value={filters.status || 'all'}
        options={USER_STATUS_OPTIONS}
        onChange={(status) => onChange({ ...filters, status, offset: 0 })}
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
        onChange={(sort) => onChange({ ...filters, sort, offset: 0 })}
      />
      <button
        type="button"
        className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm font-semibold text-white/70 transition hover:border-cyan-300/25 hover:text-cyan-100"
        onClick={onRefresh}
      >
        刷新目录
      </button>
      <p className="rounded-2xl border border-cyan-300/10 bg-cyan-400/8 px-3 py-3 text-xs leading-5 text-cyan-50/70">
        查看用户目录会记录管理员访问范围，不记录搜索原文或凭证值。
      </p>
    </div>
  </GlassCard>
);

const UserRow: React.FC<{ user: AdminUserListItem; locale: 'zh' | 'en'; canReadOpsLogs: boolean }> = ({ user, locale, canReadOpsLogs }) => {
  const href = locale === 'en' ? `/en/admin/users/${encodeURIComponent(user.id)}` : `/zh/admin/users/${encodeURIComponent(user.id)}`;
  const adminLogs = canReadOpsLogs ? adminLogHref(user.links?.adminLogs, locale) : null;
  return (
    <article className="min-w-0 rounded-2xl border border-white/5 bg-black/20 p-4 transition hover:border-white/10 hover:bg-white/[0.03]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Link to={href} className="group inline-flex min-w-0 items-center gap-2">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-cyan-300/15 bg-cyan-400/10 text-cyan-100">
              <UserRound className="h-4 w-4" aria-hidden="true" />
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
          <span className={cn('inline-flex min-h-6 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold', statusTone(user.isActive ? 'active' : 'inactive'))}>
            {user.isActive ? '活跃' : '停用'}
          </span>
          <span className="inline-flex min-h-6 rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-0.5 text-[11px] font-semibold text-white/62">
            {user.role === 'admin' ? '管理员' : user.role}
          </span>
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
            <span key={`${badge.code}-${badge.label}`} className={cn('inline-flex min-h-6 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold', riskTone(badge.severity))}>
              {badge.label}
            </span>
          )) : (
            <span className="text-xs text-white/38">暂无风险标签</span>
          )}
        </div>
        {adminLogs ? (
          <Link to={adminLogs} className="inline-flex min-h-8 items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[11px] font-semibold text-white/62 transition hover:border-cyan-300/25 hover:text-cyan-100">
            Admin Logs
            <ExternalLink className="h-3 w-3" aria-hidden="true" />
          </Link>
        ) : null}
      </div>
    </article>
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
    <div className="grid min-h-0 grid-cols-1 gap-5 xl:grid-cols-12">
      <div className="xl:col-span-3">
        <FilterRail filters={filters} onChange={setFilters} onRefresh={reload} />
      </div>
      <div className="min-w-0 xl:col-span-9">
        <GlassCard as="section" className="p-4 md:p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">Directory</p>
              <h2 className="mt-1 text-lg font-semibold text-white">用户目录</h2>
            </div>
            <Badge variant="default" className="border-white/10 bg-white/[0.04] text-white/58">
              {state.data ? `${state.data.total} users` : '读取中'}
            </Badge>
          </div>
          {state.error ? (
            <div className="mt-4">
              <p className="mb-2 text-sm font-semibold text-rose-100">读取用户目录失败</p>
              <ApiErrorAlert error={state.error} />
            </div>
          ) : null}
          {state.loading ? (
            <div className="mt-4 grid gap-3">
              {[0, 1, 2].map((item) => <div key={item} className="h-32 animate-pulse rounded-2xl border border-white/5 bg-white/[0.025]" />)}
            </div>
          ) : users.length === 0 && !state.error ? (
            <div className="mt-4 rounded-2xl border border-white/5 bg-black/20 px-4 py-8 text-sm text-white/50">暂无符合条件的用户</div>
          ) : (
            <div className="mt-4 grid gap-3">
              {users.map((user) => <UserRow key={user.id} user={user} locale={language} canReadOpsLogs={canReadOpsLogs} />)}
            </div>
          )}
        </GlassCard>
      </div>
    </div>
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
        <span key={item.key} className="inline-flex min-h-9 shrink-0 items-center rounded-lg border border-white/5 bg-white/[0.02] px-3 text-xs font-semibold text-white/25">
          {item.label} · 后续
        </span>
      ) : (
        <Link
          key={item.key}
          to={item.href}
          className={cn(
            'inline-flex min-h-9 shrink-0 items-center rounded-lg border px-3 text-xs font-semibold transition',
            (active === 'activity' && item.key === 'activity') || (active === 'detail' && activeDetailTab === item.key)
              ? 'border-cyan-300/25 bg-cyan-400/10 text-cyan-100'
              : 'border-white/10 bg-white/[0.03] text-white/60 hover:border-white/20 hover:text-white',
          )}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
};

const SessionList: React.FC<{ sessions: AdminSessionSummary[] }> = ({ sessions }) => (
  <GlassCard as="section" className="p-4 md:p-5">
    <div className="flex items-start gap-3">
      <Fingerprint className="mt-1 h-4 w-4 text-cyan-200" aria-hidden="true" />
      <div>
        <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">Sessions</p>
        <h2 className="mt-1 text-base font-semibold text-white">最近脱敏会话</h2>
      </div>
    </div>
    {sessions.length === 0 ? (
      <p className="mt-5 rounded-2xl border border-white/5 bg-black/20 px-4 py-5 text-sm text-white/50">暂无会话摘要</p>
    ) : (
      <div className="mt-5 grid gap-3">
        {sessions.map((session) => (
          <div key={session.sessionHandle} className="rounded-2xl border border-white/5 bg-black/20 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-mono text-sm font-semibold text-white">{session.sessionHandle}</span>
              <span className={cn('inline-flex min-h-6 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold', statusTone(session.status))}>
                {statusLabel(session.status)}
              </span>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-white/44 md:grid-cols-4">
              <p>创建 <span className="block truncate font-mono text-white/68">{formatDate(session.createdAt)}</span></p>
              <p>最近 <span className="block truncate font-mono text-white/68">{formatDate(session.lastSeenAt)}</span></p>
              <p>过期 <span className="block truncate font-mono text-white/68">{formatDate(session.expiresAt)}</span></p>
              <p>撤销 <span className="block truncate font-mono text-white/68">{formatDate(session.revokedAt)}</span></p>
            </div>
          </div>
        ))}
      </div>
    )}
  </GlassCard>
);

const FuturePlaceholders: React.FC = () => (
  <GlassCard as="section" className="p-4 md:p-5">
    <div className="flex items-start gap-3">
      <LockKeyhole className="mt-1 h-4 w-4 text-amber-200" aria-hidden="true" />
      <div>
        <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">Scope Guard</p>
        <h2 className="mt-1 text-base font-semibold text-white">后续能力占位</h2>
      </div>
    </div>
    <div className="mt-4 grid gap-2 text-sm text-white/55">
      {['安全控制只读占位，未提供禁用、重置、撤销操作。', '组合、分析、Scanner、Backtest 管理视图等待独立后端合同。', '原始数据库浏览器、原始 prompt、provider payload 与堆栈明细不在本阶段展示。'].map((item) => (
        <p key={item} className="rounded-2xl border border-white/5 bg-black/20 px-3 py-3">{item}</p>
      ))}
    </div>
  </GlassCard>
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
    <div className="grid min-h-0 grid-cols-1 gap-5 xl:grid-cols-12">
      <div className="min-w-0 xl:col-span-8">
        <GlassCard as="section" className="p-4 md:p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">Portfolio</p>
              <h2 className="mt-1 text-lg font-semibold text-white">组合只读总览</h2>
              <p className="mt-1 max-w-2xl text-xs leading-5 text-white/46">仅展示账户、估值、持仓和账本活动的安全投影；不会触发同步、导入、重放、FX 刷新或组合数据修改。</p>
            </div>
            <Badge variant="info" className="border-cyan-300/25 bg-cyan-400/10 text-cyan-100">只读投影</Badge>
          </div>
          {summaryState.error ? (
            <div className="mt-4">
              <ApiErrorAlert error={summaryState.error} />
            </div>
          ) : null}
          {summaryState.loading && !summary ? (
            <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
              {[0, 1, 2, 3].map((item) => <div key={item} className="h-20 animate-pulse rounded-2xl border border-white/5 bg-white/[0.025]" />)}
            </div>
          ) : summary ? (
            <>
              <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
                <SummaryTile label="账户数" value={`${summary.accountCount} / ${summary.activeAccountCount}`} tone="info" />
                <SummaryTile label="现金" value={formatMoney(summary.totalCash)} tone="neutral" />
                <SummaryTile label="市值" value={formatMoney(summary.totalMarketValue)} tone="good" />
                <SummaryTile label="权益" value={formatMoney(summary.totalEquity)} tone="good" />
                <SummaryTile label="已实现 P&L" value={formatMoney(summary.realizedPnl)} tone={summary.realizedPnl.amount >= 0 ? 'good' : 'danger'} />
                <SummaryTile label="未实现 P&L" value={formatMoney(summary.unrealizedPnl)} tone={summary.unrealizedPnl.amount >= 0 ? 'good' : 'danger'} />
                <SummaryTile label="交易/现金/公司行动" value={`${summary.ledgerCounts.trades}/${summary.ledgerCounts.cashEvents}/${summary.ledgerCounts.corporateActions}`} tone="info" />
                <SummaryTile label="币种" value={summary.baseCurrencies.join(' / ') || '--'} tone="neutral" />
              </div>
              {summary.accountCount === 0 ? (
                <p className="mt-5 rounded-2xl border border-white/5 bg-black/20 px-4 py-6 text-sm text-white/50">该用户暂无组合账户</p>
              ) : (
                <div className="mt-5">
                  <h3 className="text-sm font-semibold text-white">组合账户</h3>
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    {summary.accounts.map((account) => (
                      <article key={account.id} className="rounded-2xl border border-white/5 bg-black/20 p-3">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p className="truncate text-sm font-semibold text-white">{account.name}</p>
                            <p className="mt-1 truncate font-mono text-[11px] text-white/42">{text(account.brokerAccountHandle, 'masked')}</p>
                          </div>
                          <span className={cn('inline-flex min-h-6 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold', statusTone(account.isActive ? 'active' : 'inactive'))}>
                            {account.isActive ? '活跃' : '停用'}
                          </span>
                        </div>
                        <div className="mt-3 grid grid-cols-3 gap-2 text-[11px] text-white/44">
                          <span>Broker <b className="block truncate text-white/70">{text(account.broker)}</b></span>
                          <span>Market <b className="block truncate text-white/70">{text(account.market)}</b></span>
                          <span>Currency <b className="block truncate text-white/70">{text(account.baseCurrency)}</b></span>
                        </div>
                      </article>
                    ))}
                  </div>
                </div>
              )}
              <div className="mt-5 rounded-2xl border border-cyan-300/10 bg-cyan-400/8 px-4 py-3 text-xs leading-5 text-cyan-50/70">
                Broker sync summary: {summary.brokerSyncSummary.connections} connections · last sync {formatDate(summary.brokerSyncSummary.lastSyncAt)} · FX {summary.brokerSyncSummary.fxStale ? 'stale' : 'current'}
                {brokerStatuses.length ? ` · ${brokerStatuses.map(([key, value]) => `${key}:${value}`).join(' ')}` : ''}
              </div>
              {summary.limitations.length ? (
                <div className="mt-4 flex flex-wrap gap-2">
                  {summary.limitations.map((item) => <Badge key={item} variant="default" className="border-white/10 bg-white/[0.04] text-white/58">{limitationText(item)}</Badge>)}
                </div>
              ) : null}
            </>
          ) : null}
        </GlassCard>
      </div>
      <div className="grid min-w-0 gap-5 xl:col-span-4">
        <GlassCard as="section" className="p-4 md:p-5">
          <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">Guardrails</p>
          <h2 className="mt-1 text-base font-semibold text-white">限制 / 审计感知</h2>
          <div className="mt-4 grid gap-2 text-xs leading-5 text-white/50">
            <p className="rounded-xl border border-white/5 bg-black/20 px-3 py-2">组合视图只读，不提供修正、导入、同步、重放或外部调用按钮。</p>
            <p className="rounded-xl border border-white/5 bg-black/20 px-3 py-2">经纪商账户仅显示 masked handle；原始 payload、sync metadata 和凭证不会进入界面。</p>
          </div>
        </GlassCard>
      </div>
      <div className="min-w-0 xl:col-span-7">
        <GlassCard as="section" className="p-4 md:p-5">
          <h2 className="text-base font-semibold text-white">持仓明细</h2>
          {holdingsState.error ? <div className="mt-3"><ApiErrorAlert error={holdingsState.error} /></div> : null}
          {holdingsState.loading && holdings.length === 0 ? (
            <div className="mt-4 h-32 animate-pulse rounded-2xl border border-white/5 bg-white/[0.025]" />
          ) : holdings.length === 0 ? (
            <p className="mt-4 rounded-2xl border border-white/5 bg-black/20 px-4 py-6 text-sm text-white/50">暂无持仓</p>
          ) : (
            <div className="mt-4 overflow-x-auto no-scrollbar">
              <table className="w-full min-w-[620px] text-left text-xs">
                <thead className="text-white/34">
                  <tr>
                    <th className="py-2 pr-3">标的</th>
                    <th className="py-2 pr-3">账户</th>
                    <th className="py-2 pr-3">数量</th>
                    <th className="py-2 pr-3">市值</th>
                    <th className="py-2 pr-3">未实现 P&L</th>
                    <th className="py-2">FX</th>
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
            </div>
          )}
        </GlassCard>
      </div>
      <div className="min-w-0 xl:col-span-5">
        <GlassCard as="section" className="p-4 md:p-5">
          <h2 className="text-base font-semibold text-white">组合活动</h2>
          {activityState.error ? <div className="mt-3"><ApiErrorAlert error={activityState.error} /></div> : null}
          {activityState.loading && activities.length === 0 ? (
            <div className="mt-4 h-32 animate-pulse rounded-2xl border border-white/5 bg-white/[0.025]" />
          ) : activities.length === 0 ? (
            <p className="mt-4 rounded-2xl border border-white/5 bg-black/20 px-4 py-6 text-sm text-white/50">暂无组合活动</p>
          ) : (
            <div className="mt-4 grid gap-3">
              {activities.slice(0, 8).map((item) => (
                <article key={item.idHash} className="rounded-2xl border border-white/5 bg-black/20 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-mono text-sm font-semibold text-white">{item.symbol || item.type}</p>
                      <p className="mt-1 text-[11px] text-white/42">{item.accountName} · {formatDate(item.eventDate)}</p>
                    </div>
                    <Badge variant="default" className="border-white/10 bg-white/[0.04] text-white/58">{item.type}</Badge>
                  </div>
                  <p className="mt-2 truncate text-[11px] text-white/50">
                    {text(item.side || item.direction || item.actionType, 'activity')} · qty {text(item.quantity)} · amount {text(item.amount)}
                  </p>
                </article>
              ))}
            </div>
          )}
        </GlassCard>
      </div>
    </div>
  );
};

const UnavailableAdminCapability: React.FC<{ title: string; description: string }> = ({ title, description }) => (
  <GlassCard as="section" className="p-5 md:p-6">
    <div className="flex items-start gap-3">
      <LockKeyhole className="mt-1 h-4 w-4 text-amber-200" aria-hidden="true" />
      <div>
        <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">Capability Required</p>
        <h2 className="mt-1 text-base font-semibold text-white">{title}</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-white/52">{description}</p>
      </div>
    </div>
  </GlassCard>
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
    <GlassCard as="section" className="p-4 md:p-5" data-testid={`security-action-${actionKey.replace('_sessions', '-sessions')}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">Security Action</p>
          <h3 className="mt-1 text-base font-semibold text-white">{title}</h3>
          <p className="mt-1 max-w-xl text-xs leading-5 text-white/46">{description}</p>
        </div>
        <span className={cn('inline-flex min-h-6 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold', available ? statusTone('warning') : 'border-white/10 bg-white/[0.04] text-white/35')}>
          {available ? '可执行' : '当前状态不可用'}
        </span>
      </div>
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
        <Button
          variant={danger ? 'danger-subtle' : 'gradient'}
          size="sm"
          isLoading={state.loading}
          disabled={!canSubmit}
          onClick={onSubmit}
        >
          {buttonLabel}
        </Button>
        {!available ? <span className="text-xs text-white/35">账户当前状态不适用该操作。</span> : null}
      </div>
      {state.error ? (
        <div className="mt-4">
          <ApiErrorAlert error={state.error} />
        </div>
      ) : null}
      {state.result ? (
        <div className="mt-4 rounded-2xl border border-emerald-300/20 bg-emerald-400/10 px-4 py-3 text-xs leading-5 text-emerald-50/80">
          <p>状态: {statusLabel(state.result.status)} · 会话撤销 {state.result.sessionsRevoked}</p>
          {state.result.auditEventId ? <p className="mt-1 font-mono text-emerald-100">{state.result.auditEventId}</p> : null}
        </div>
      ) : null}
    </GlassCard>
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
    <div className="grid min-h-0 grid-cols-1 gap-5 xl:grid-cols-12">
      <div className="min-w-0 xl:col-span-4">
        <GlassCard as="section" className="p-4 md:p-5">
          <div className="flex items-start gap-3">
            <ShieldCheck className="mt-1 h-4 w-4 text-cyan-200" aria-hidden="true" />
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">Security S1</p>
              <h2 className="mt-1 text-base font-semibold text-white">安全控制 S1</h2>
            </div>
          </div>
          <div className="mt-5 grid grid-cols-2 gap-3">
            <SummaryTile label="账户状态" value={user.isActive ? '活跃' : '停用'} tone={user.isActive ? 'good' : 'danger'} />
            <SummaryTile label="活跃会话" value={user.sessionSummary.activeCount} tone="info" />
            <SummaryTile label="密码状态" value={passwordStateLabel(user.passwordState)} tone={user.passwordState === 'unset' ? 'warn' : 'neutral'} />
            <SummaryTile label="角色" value={user.role === 'admin' ? '管理员' : user.role} tone="neutral" />
          </div>
          <p className="mt-4 rounded-2xl border border-cyan-300/10 bg-cyan-400/8 px-3 py-3 text-xs leading-5 text-cyan-50/70">
            安全状态查看和控制操作都会被审计；响应不会返回密码、哈希、Cookie、token 或原始 session id。
          </p>
          <Disclosure summary="后续阶段占位" className="mt-4" bodyClassName="rounded-xl border border-white/5 bg-white/[0.025] p-3">
            <div className="grid gap-2 text-xs text-white/42">
              <p>reset-password 后续阶段，不在本次实现。</p>
              <p>force-password-change 后续阶段，不在本次实现。</p>
              <p>unlock / RBAC capability model 后续阶段，不在本次实现。</p>
            </div>
          </Disclosure>
        </GlassCard>
      </div>
      <div className="grid min-w-0 gap-5 xl:col-span-8">
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
            description="恢复目标用户账户访问状态。该操作仍需审计原因和 typed confirmation。"
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
          description="撤销目标用户全部应用会话，仅返回数量和审计结果，不返回任何 raw session id。"
          confirmPhrase="REVOKE_SESSIONS"
          buttonLabel="撤销全部会话"
          available
          danger
          state={actionState.revoke_sessions}
          onChange={(patch) => updateAction('revoke_sessions', patch)}
          onSubmit={() => submitAction('revoke_sessions')}
        />
      </div>
    </div>
  );
};

const DetailOverview: React.FC<{ detail: AdminUserDetailResponse; locale: 'zh' | 'en'; canReadOpsLogs: boolean }> = ({ detail, locale, canReadOpsLogs }) => {
  const { user } = detail;
  const adminLogs = canReadOpsLogs ? adminLogHref(detail.dataLinks.adminLogs || user.links?.adminLogs, locale) : null;
  return (
    <div className="grid min-h-0 grid-cols-1 gap-5 xl:grid-cols-12">
      <div className="min-w-0 xl:col-span-8">
        <GlassCard as="section" className="p-4 md:p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">Identity</p>
              <h2 className="mt-1 truncate text-xl font-semibold text-white">{text(user.displayName || user.username)}</h2>
              <p className="mt-1 truncate font-mono text-xs text-white/42">{user.id}</p>
            </div>
            <div className="flex flex-wrap justify-end gap-1.5">
              <span className={cn('inline-flex min-h-6 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold', statusTone(user.isActive ? 'active' : 'inactive'))}>
                {user.isActive ? '活跃' : '停用'}
              </span>
              <span className="inline-flex min-h-6 rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-0.5 text-[11px] font-semibold text-white/62">
                {user.role === 'admin' ? '管理员' : user.role}
              </span>
            </div>
          </div>
          <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
            <SummaryTile label="活跃会话" value={user.sessionSummary.activeCount} tone="good" />
            <SummaryTile label="过期会话" value={user.sessionSummary.expiredCount} tone="warn" />
            <SummaryTile label="撤销会话" value={user.sessionSummary.revokedCount} tone="info" />
            <SummaryTile label="密码状态" value={passwordStateLabel(user.passwordState)} tone={user.passwordState === 'unset' ? 'warn' : 'neutral'} />
          </div>
          <div className="mt-5 grid grid-cols-1 gap-3 text-sm text-white/52 md:grid-cols-2">
            <p className="rounded-2xl border border-white/5 bg-black/20 px-4 py-3">创建时间 <span className="block font-mono text-white/72">{formatDate(user.createdAt)}</span></p>
            <p className="rounded-2xl border border-white/5 bg-black/20 px-4 py-3">更新时间 <span className="block font-mono text-white/72">{formatDate(user.updatedAt)}</span></p>
            <p className="rounded-2xl border border-white/5 bg-black/20 px-4 py-3">最近活动 <span className="block font-mono text-white/72">{formatDate(user.lastSeenAt)}</span></p>
            <p className="rounded-2xl border border-white/5 bg-black/20 px-4 py-3">下一会话过期 <span className="block font-mono text-white/72">{formatDate(user.sessionSummary.nextExpiresAt)}</span></p>
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            {user.riskBadges.length > 0 ? user.riskBadges.map((badge) => (
              <span key={badge.code} className={cn('inline-flex min-h-6 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold', riskTone(badge.severity))}>
                {badge.label}
              </span>
            )) : <span className="text-xs text-white/38">暂无风险标签</span>}
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            {adminLogs ? (
              <Link to={adminLogs} className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.03] px-3 text-xs font-semibold text-white/64 transition hover:border-cyan-300/25 hover:text-cyan-100">
                查看 Admin Logs
                <ExternalLink className="h-3 w-3" aria-hidden="true" />
              </Link>
            ) : null}
            <button type="button" disabled className="inline-flex min-h-9 cursor-not-allowed items-center rounded-lg border border-white/5 bg-white/[0.02] px-3 text-xs font-semibold text-white/25">
              安全操作后续开放
            </button>
          </div>
        </GlassCard>
      </div>
      <div className="grid min-w-0 gap-5 xl:col-span-4">
        <GlassCard as="section" className="p-4 md:p-5">
          <div className="flex items-start gap-3">
            <ShieldCheck className="mt-1 h-4 w-4 text-cyan-200" aria-hidden="true" />
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">Audit</p>
              <h2 className="mt-1 text-base font-semibold text-white">访问提示</h2>
            </div>
          </div>
          <p className="mt-4 rounded-2xl border border-cyan-300/10 bg-cyan-400/8 px-3 py-3 text-xs leading-5 text-cyan-50/70">
            打开用户详情会记录目标用户和管理员身份。响应不包含密码、哈希、Cookie、令牌或原始会话值。
          </p>
        </GlassCard>
        <GlassCard as="section" className="p-4 md:p-5">
          <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">Limitations</p>
          <h2 className="mt-1 text-base font-semibold text-white">已知限制</h2>
          <div className="mt-4 grid gap-2">
            {detail.limitations.length > 0 ? detail.limitations.map((item) => (
              <p key={item} className="rounded-xl border border-white/5 bg-black/20 px-3 py-2 text-xs text-white/48">{item.replace(/_/g, ' ')}</p>
            )) : <p className="text-xs text-white/40">暂无限制说明</p>}
          </div>
        </GlassCard>
      </div>
      <div className="min-w-0 xl:col-span-7"><SessionList sessions={detail.sessions} /></div>
      <div className="min-w-0 xl:col-span-5"><FuturePlaceholders /></div>
    </div>
  );
};

const ActivityFilters: React.FC<{
  filters: AdminActivityParams;
  onChange: (next: AdminActivityParams) => void;
  onRefresh: () => void;
}> = ({ filters, onChange, onRefresh }) => {
  const toggle = (key: 'includeAdmin' | 'includeSystem') => onChange({ ...filters, [key]: !filters[key], offset: 0 });
  return (
    <GlassCard as="aside" className="p-4 md:p-5">
      <div className="flex items-start gap-3">
        <Activity className="mt-1 h-4 w-4 text-cyan-200" aria-hidden="true" />
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">Timeline</p>
          <h2 className="mt-1 text-base font-semibold text-white">活动筛选</h2>
        </div>
      </div>
      <div className="mt-5 grid gap-4">
        <Input label="安全查询" value={filters.q || ''} placeholder="action / symbol / hash" onChange={(event) => onChange({ ...filters, q: event.target.value, offset: 0 })} />
        <Select label="事件族群" value={filters.family || ''} options={ACTIVITY_FAMILY_OPTIONS} onChange={(family) => onChange({ ...filters, family, offset: 0 })} />
        <Select label="结果" value={filters.status || ''} options={ACTIVITY_STATUS_OPTIONS} onChange={(status) => onChange({ ...filters, status, offset: 0 })} />
        <Select label="对象类型" value={filters.entityType || ''} options={ENTITY_TYPE_OPTIONS} onChange={(entityType) => onChange({ ...filters, entityType, offset: 0 })} />
        <Select label="发起方" value={filters.actorType || ''} options={ACTOR_TYPE_OPTIONS} onChange={(actorType) => onChange({ ...filters, actorType, offset: 0 })} />
        <div className="grid grid-cols-2 gap-2">
          <button type="button" className={cn('rounded-lg border px-3 py-2 text-xs font-semibold transition', filters.includeAdmin ? 'border-cyan-300/25 bg-cyan-400/10 text-cyan-100' : 'border-white/10 bg-white/[0.03] text-white/58')} onClick={() => toggle('includeAdmin')}>
            管理访问
          </button>
          <button type="button" className={cn('rounded-lg border px-3 py-2 text-xs font-semibold transition', filters.includeSystem ? 'border-cyan-300/25 bg-cyan-400/10 text-cyan-100' : 'border-white/10 bg-white/[0.03] text-white/58')} onClick={() => toggle('includeSystem')}>
            系统事件
          </button>
        </div>
        <button type="button" className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm font-semibold text-white/70 transition hover:border-cyan-300/25 hover:text-cyan-100" onClick={onRefresh}>
          刷新活动
        </button>
        <p className="rounded-2xl border border-cyan-300/10 bg-cyan-400/8 px-3 py-3 text-xs leading-5 text-cyan-50/70">
          访问活动时间线会写入目标用户级审计事件。
        </p>
      </div>
    </GlassCard>
  );
};

const ActivityEventCard: React.FC<{ event: AdminActivityEvent }> = ({ event }) => {
  const entries = safeMetadataEntries(event.redactedMetadata);
  const hiddenCount = sensitiveFieldCount(event.redactedMetadata);
  return (
    <article className="relative rounded-2xl border border-white/5 bg-black/20 p-4">
      <div className="absolute left-5 top-5 h-2.5 w-2.5 rounded-full border border-cyan-200/60 bg-cyan-300 shadow-[0_0_18px_rgba(103,232,249,0.28)]" aria-hidden="true" />
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
            <span className="inline-flex min-h-6 rounded-full border border-cyan-300/20 bg-cyan-400/8 px-2.5 py-0.5 text-[11px] font-semibold text-cyan-100">{event.family}</span>
            <span className={cn('inline-flex min-h-6 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold', statusTone(event.status))}>{statusLabel(event.status)}</span>
          </div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-2 text-[11px] text-white/44 md:grid-cols-4">
          <p>对象 <span className="block truncate text-white/68">{event.entity.type}</span></p>
          <p>结果 <span className="block truncate text-white/68">{statusLabel(event.outcome)}</span></p>
          <p>请求哈希 <span className="block truncate font-mono text-white/68">{text(event.requestIdHash)}</span></p>
          <p>会话哈希 <span className="block truncate font-mono text-white/68">{text(event.sessionIdHash)}</span></p>
        </div>
        <Disclosure
          summary="脱敏元数据"
          className="mt-4"
          bodyClassName="rounded-xl border border-white/5 bg-white/[0.025] p-3"
        >
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
                  <dt className="text-white/34">redaction</dt>
                  <dd className="text-amber-100/72">{hiddenCount} 个敏感字段已屏蔽</dd>
                </div>
              ) : null}
            </dl>
          )}
        </Disclosure>
      </div>
    </article>
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
    <div className="grid min-h-0 grid-cols-1 gap-5 xl:grid-cols-12">
      <div className="xl:col-span-3"><ActivityFilters filters={filters} onChange={setFilters} onRefresh={reload} /></div>
      <div className="min-w-0 xl:col-span-9">
        <GlassCard as="section" className="p-4 md:p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">Activity</p>
              <h2 className="mt-1 text-lg font-semibold text-white">活动时间线</h2>
              {state.data?.window ? (
                <p className="mt-1 text-xs text-white/42">
                  {formatDate(state.data.window.from)} - {formatDate(state.data.window.to)}
                </p>
              ) : null}
            </div>
            <Badge variant="default" className="border-white/10 bg-white/[0.04] text-white/58">
              {state.data ? `${state.data.total} events` : '读取中'}
            </Badge>
          </div>
          {state.error ? (
            <div className="mt-4">
              <p className="mb-2 text-sm font-semibold text-rose-100">读取活动时间线失败</p>
              <ApiErrorAlert error={state.error} />
            </div>
          ) : null}
          {state.loading ? (
            <div className="mt-4 grid gap-3">
              {[0, 1, 2].map((item) => <div key={item} className="h-36 animate-pulse rounded-2xl border border-white/5 bg-white/[0.025]" />)}
            </div>
          ) : items.length === 0 && !state.error ? (
            <div className="mt-4 rounded-2xl border border-white/5 bg-black/20 px-4 py-8 text-sm text-white/50">当前时间窗口内暂无活动</div>
          ) : (
            <div className="mt-4 grid gap-3">
              {items.map((event) => <ActivityEventCard key={event.id} event={event} />)}
            </div>
          )}
          {state.data?.limitations?.length ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {state.data.limitations.map((item) => (
                <span key={item} className="inline-flex min-h-6 rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-0.5 text-[11px] font-semibold text-white/46">
                  {item.replace(/_/g, ' ')}
                </span>
              ))}
            </div>
          ) : null}
        </GlassCard>
      </div>
    </div>
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

  const loadUsers = useCallback(() => {
    if (!canReadUsers) return;
    setUsersState((state) => ({ ...state, loading: true, error: null }));
    void adminUsersApi.listUsers(filters)
      .then((data) => setUsersState({ loading: false, error: null, data }))
      .catch((error) => setUsersState({ loading: false, error: getParsedApiError(error), data: null }));
  }, [canReadUsers, filters]);

  const loadDetail = useCallback((targetUserId: string) => {
    if (!canReadUsers) return;
    setDetailState((state) => ({ ...state, loading: true, error: null }));
    void adminUsersApi.getUserDetail(targetUserId)
      .then((data) => setDetailState({ loading: false, error: null, data }))
      .catch((error) => setDetailState({ loading: false, error: getParsedApiError(error), data: null }));
  }, [canReadUsers]);

  const loadActivity = useCallback((targetUserId: string) => {
    if (!canReadUserActivity) return;
    setActivityState((state) => ({ ...state, loading: true, error: null }));
    void adminUsersApi.listUserActivity(targetUserId, activityFilters)
      .then((data) => setActivityState({ loading: false, error: null, data }))
      .catch((error) => setActivityState({ loading: false, error: getParsedApiError(error), data: null }));
  }, [activityFilters, canReadUserActivity]);

  const loadPortfolio = useCallback((targetUserId: string) => {
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
  }, [canReadUserPortfolio]);

  const updateSecurityAction = useCallback((key: SecurityActionKey, patch: Partial<SecurityActionFormState>) => {
    setSecurityActionState((state) => ({
      ...state,
      [key]: { ...state[key], ...patch, error: patch.error === undefined ? state[key].error : patch.error },
    }));
  }, []);

  const submitSecurityAction = useCallback((key: SecurityActionKey) => {
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
  }, [loadDetail, securityActionState, userId]);

  useEffect(() => {
    if (userId) return;
    const timer = window.setTimeout(() => loadUsers(), 0);
    return () => window.clearTimeout(timer);
  }, [loadUsers, userId]);

  useEffect(() => {
    if (!userId) return;
    const timer = window.setTimeout(() => loadDetail(userId), 0);
    return () => window.clearTimeout(timer);
  }, [loadDetail, userId]);

  useEffect(() => {
    if (!userId || mode !== 'activity') return;
    const timer = window.setTimeout(() => loadActivity(userId), 0);
    return () => window.clearTimeout(timer);
  }, [loadActivity, mode, userId]);

  useEffect(() => {
    if (!userId || mode !== 'detail' || activeDetailTab !== 'portfolio') return;
    const timer = window.setTimeout(() => loadPortfolio(userId), 0);
    return () => window.clearTimeout(timer);
  }, [activeDetailTab, loadPortfolio, mode, userId]);

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

  const content = useMemo(() => {
    if (!userId) {
      return <DirectoryView state={usersState} filters={filters} setFilters={setFilters} reload={loadUsers} canReadOpsLogs={canReadOpsLogs} />;
    }
    if (!canReadUsers) {
      return <UnavailableAdminCapability title="不可查看用户资料" description="当前账号缺少用户治理读取权限，前端不会请求或渲染用户详情。后端授权仍是最终边界。" />;
    }
    if (detailState.loading && !detailState.data) {
      return <div className="h-64 animate-pulse rounded-[24px] border border-white/5 bg-white/[0.025]" />;
    }
    if (detailState.error) {
      return (
        <GlassCard as="section" className="p-5">
          <p className="mb-2 text-sm font-semibold text-rose-100">读取用户详情失败</p>
          <ApiErrorAlert error={detailState.error} />
          <button
            type="button"
            className="mt-4 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm font-semibold text-white/70 transition hover:border-cyan-300/25 hover:text-cyan-100"
            onClick={() => navigate(directoryPath)}
          >
            返回用户目录
          </button>
        </GlassCard>
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
  }, [activeDetailTab, activityFilters, activityState, canReadOpsLogs, canReadUserActivity, canReadUserPortfolio, canReadUsers, canWriteUserSecurity, detailState, directoryPath, filters, holdingsState, language, loadActivity, loadUsers, mode, navigate, portfolioActivityState, portfolioSummaryState, securityActionState, submitSecurityAction, updateSecurityAction, userId, usersState]);

  return (
    <div className="flex min-h-0 w-full min-w-0 flex-1 flex-col overflow-y-auto no-scrollbar py-5 md:py-6">
      <div className="mx-auto flex w-full max-w-[1680px] flex-col gap-5 px-4 md:px-6 xl:px-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          {userId ? (
            <button
              type="button"
              className="inline-flex min-h-9 items-center rounded-lg border border-white/10 bg-white/[0.03] px-3 text-xs font-semibold text-white/62 transition hover:border-white/20 hover:text-white"
              onClick={() => navigate(directoryPath)}
            >
              返回用户目录
            </button>
          ) : <span />}
          <div className="inline-flex items-center gap-2 rounded-full border border-white/5 bg-white/[0.02] px-3 py-1.5 text-[11px] text-white/40">
            <Clock3 className="h-3.5 w-3.5" aria-hidden="true" />
            Read-only F1/F2
          </div>
        </div>
        <PageHeader mode={mode} user={activeUser} currentState={headerCurrentState} nextAction={headerNextAction} />
        {content}
        <GlassCard as="section" className="p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-200" aria-hidden="true" />
            <p className="text-xs leading-5 text-white/46">
              本页面只展示账号、会话和活动的安全投影；凭证材料、原始会话材料、请求载荷、模型上下文、第三方原始响应和异常堆栈均不进入界面。
            </p>
          </div>
        </GlassCard>
      </div>
    </div>
  );
};

export default AdminUsersPage;
