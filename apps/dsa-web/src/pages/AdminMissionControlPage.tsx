import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowRight,
  Ban,
  CheckCircle2,
  FileCheck2,
  FileText,
  LockKeyhole,
  Radar,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react';
import { adminMissionControlApi, type MissionControlDomainSlice, type MissionControlResponse } from '../api/adminMissionControl';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { ApiErrorAlert } from '../components/common/ApiErrorAlert';
import AdminDrillThroughStrip from '../components/admin/AdminDrillThroughStrip';
import AdminOpsL0OverviewStrip from '../components/admin/AdminOpsL0OverviewStrip';
import {
  TerminalChip,
  TerminalEmptyState,
  TerminalMetric,
  TerminalNotice,
  TerminalPageShell,
  TerminalPanel,
} from '../components/terminal/TerminalPrimitives';
import { useProductSurface } from '../hooks/useProductSurface';
import { cn } from '../utils/cn';
import { formatDateTime, formatNumber } from '../utils/format';

type LoadState = {
  loading: boolean;
  error: ParsedApiError | null;
  data: MissionControlResponse | null;
};

type ChipVariant = React.ComponentProps<typeof TerminalChip>['variant'];

const TEXT_PRIMARY = 'text-[color:var(--wolfy-text-primary)]';
const TEXT_SECONDARY = 'text-[color:var(--wolfy-text-secondary)]';
const TEXT_MUTED = 'text-[color:var(--wolfy-text-muted)]';

const SAFE_VISIBLE_TEXT_PATTERN = /(https?:\/\/|www\.|\?|=|token|cookie|session|password|bearer|apikey|api_key|stack|trace|payload|prompt|credential|secret)/i;

function safeText(value?: string | number | null, fallback = '--'): string {
  if (value === null || value === undefined || value === '') return fallback;
  const text = String(value).trim();
  if (!text || SAFE_VISIBLE_TEXT_PATTERN.test(text)) return '已脱敏';
  return text.slice(0, 120);
}

function statusVariant(domain: MissionControlDomainSlice): ChipVariant {
  if (domain.posture.publicLaunchNoGo) return 'danger';
  if (domain.posture.approvalRequired || domain.posture.realOperatorEvidenceMissing) return 'caution';
  if (domain.posture.evidenceToolingExists) return 'info';
  return 'neutral';
}

function postureFlags(domain: MissionControlDomainSlice) {
  return [
    { key: 'landedFoundation', label: '基础已落地', active: domain.posture.landedFoundation },
    { key: 'evidenceToolingExists', label: '证据工具存在', active: domain.posture.evidenceToolingExists },
    { key: 'realOperatorEvidenceMissing', label: '缺真实证据', active: domain.posture.realOperatorEvidenceMissing },
    { key: 'approvalRequired', label: '需要审批', active: domain.posture.approvalRequired },
    { key: 'publicLaunchNoGo', label: 'NO-GO', active: domain.posture.publicLaunchNoGo },
  ];
}

function safeRefList(refs: MissionControlDomainSlice['evidenceRefs']): string {
  const visible = refs
    .map((ref) => safeText(ref.label || ref.kind))
    .filter((value) => value !== '--')
    .slice(0, 3);
  return visible.length ? visible.join(' / ') : '无可展示引用';
}

type OperatorSurfaceMode = 'loading' | 'error' | 'prototype_disabled' | 'unavailable' | 'active_nogo' | 'active_clear';

function resolveSurfaceMode(state: LoadState, prototypeDisabled: boolean): OperatorSurfaceMode {
  if (state.loading) return 'loading';
  if (state.error) return 'error';
  if (prototypeDisabled) return 'prototype_disabled';
  if (!state.data) return 'unavailable';
  if (state.data.launchVerdict === 'NO_GO' || (state.data.summary.publicLaunchNoGoCount || 0) > 0) {
    return 'active_nogo';
  }
  return 'active_clear';
}

type DrillItem = {
  label: string;
  target: 'evidence' | 'logs' | 'marketProviders' | 'cost';
  evidenceType: string;
  reason: string;
  params: Record<string, string>;
  href: string;
  primary?: boolean;
};

const DRILL_ITEMS: DrillItem[] = [
  {
    label: '查看证据工作流',
    target: 'evidence',
    evidenceType: 'operator evidence',
    reason: '从总控进入脱敏证据、模板和人工复核路径。',
    params: { ref: 'mission_control' },
    href: '/zh/admin/evidence-workflow?ref=mission_control',
    primary: true,
  },
  {
    label: '查看系统日志',
    target: 'logs',
    evidenceType: 'ops status',
    reason: '回看 mission-control 相关的只读运行证据。',
    params: { tab: 'business', query: 'mission control', since: '24h' },
    href: '/zh/admin/logs?tab=business&query=mission%20control&since=24h',
  },
  {
    label: '查看数据源运维',
    target: 'marketProviders',
    evidenceType: 'provider readiness',
    reason: '继续检查数据源覆盖、fallback 和 readiness 缺口。',
    params: { surface: 'market_overview' },
    href: '/zh/admin/market-providers?surface=market_overview',
  },
  {
    label: '查看成本观测',
    target: 'cost',
    evidenceType: 'quota cost',
    reason: '确认成本与配额仍是观测态而非 live enforcement。',
    params: { window: '24h', area: 'all' },
    href: '/zh/admin/cost-observability?window=24h&area=all',
  },
];

const DomainQueueItem: React.FC<{ domain: MissionControlDomainSlice; rank: number }> = ({ domain, rank }) => (
  <li>
    <article
      data-testid="admin-mission-domain-card"
      aria-label={`${domain.title}：${domain.statusLabel}`}
      className={cn(
        'min-w-0 rounded-lg border px-3 py-3',
        domain.posture.publicLaunchNoGo
          ? 'border-[color:color-mix(in_srgb,var(--wolfy-market-down)_30%,var(--wolfy-border-subtle))] bg-[color:color-mix(in_srgb,var(--wolfy-market-down)_5%,var(--wolfy-surface-console))]'
          : 'border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)]',
      )}
    >
      <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <span
              aria-hidden="true"
              className={cn(
                'flex h-6 w-6 items-center justify-center rounded-md border text-[11px] font-semibold',
                domain.posture.publicLaunchNoGo
                  ? 'border-[color:color-mix(in_srgb,var(--wolfy-market-down)_40%,transparent)] text-[color:var(--wolfy-market-down)]'
                  : 'border-[color:var(--wolfy-border-subtle)] text-[color:var(--wolfy-text-muted)]',
              )}
            >
              {rank}
            </span>
            <span aria-hidden="true" className={cn('text-xs font-semibold', domain.posture.publicLaunchNoGo ? 'text-[color:var(--wolfy-market-down)]' : TEXT_MUTED)}>
              {domain.posture.publicLaunchNoGo ? '■' : '○'}
            </span>
            <p className={cn('text-sm font-semibold', TEXT_PRIMARY)}>{domain.title}</p>
            <TerminalChip variant={statusVariant(domain)}>
              {domain.posture.publicLaunchNoGo ? (
                <>
                  <span aria-hidden="true" className="mr-1">■</span>
                  {safeText(domain.statusLabel)}
                </>
              ) : (
                safeText(domain.statusLabel)
              )}
            </TerminalChip>
          </div>
          <p className={cn('mt-1.5 break-words text-xs leading-5', TEXT_SECONDARY)}>{safeText(domain.summary)}</p>
          <div className="mt-2 flex flex-wrap gap-1.5" aria-label={`${domain.title} posture flags`}>
            {postureFlags(domain).map((flag) => (
              <TerminalChip key={flag.key} variant={flag.active ? (flag.key === 'publicLaunchNoGo' ? 'danger' : 'caution') : 'neutral'}>
                {flag.label}
              </TerminalChip>
            ))}
          </div>
          <dl className="mt-2 grid gap-2 text-xs sm:grid-cols-2">
            <div className="min-w-0">
              <dt className={cn('text-[10px] font-semibold uppercase tracking-[0.14em]', TEXT_MUTED)}>只读边界</dt>
              <dd className={cn('mt-0.5', TEXT_SECONDARY)}>
                {domain.readOnly && domain.noExternalCalls && !domain.liveEnforcement ? '只读 / 无外呼 / 无执行' : '需复核'}
              </dd>
            </div>
            <div className="min-w-0">
              <dt className={cn('text-[10px] font-semibold uppercase tracking-[0.14em]', TEXT_MUTED)}>证据引用</dt>
              <dd className={cn('mt-0.5 break-words', TEXT_SECONDARY)}>{safeRefList(domain.evidenceRefs)}</dd>
            </div>
          </dl>
        </div>
      </div>
    </article>
  </li>
);

const AdminMissionControlPage: React.FC = () => {
  const { canReadOpsLogs } = useProductSurface();
  const [state, setState] = useState<LoadState>({ loading: true, error: null, data: null });

  useEffect(() => {
    if (!canReadOpsLogs) {
      return;
    }
    let active = true;
    adminMissionControlApi.getSnapshot()
      .then((data) => {
        if (active) setState({ loading: false, error: null, data });
      })
      .catch((error: unknown) => {
        if (!active) return;
        const parsed = getParsedApiError(error);
        setState({
          loading: false,
          data: null,
          error: {
            ...parsed,
            title: '读取 Mission Control 失败',
            message: parsed.message || 'Admin Mission Control 暂不可用。',
            rawMessage: '',
            details: undefined,
          },
        });
      });
    return () => {
      active = false;
    };
  }, [canReadOpsLogs]);

  const data = state.data;
  const prototypeDisabled = data?.prototypeGate?.enabled === false;
  const surfaceMode = resolveSurfaceMode(state, Boolean(prototypeDisabled));
  const noGoDomains = useMemo(
    () => (prototypeDisabled ? [] : data?.domains.filter((domain) => domain.posture.publicLaunchNoGo) || []),
    [data, prototypeDisabled],
  );
  const rankedDomains = useMemo(() => {
    if (prototypeDisabled || !data?.domains?.length) return [];
    return [...data.domains].sort((left, right) => {
      const leftScore = (left.posture.publicLaunchNoGo ? 0 : 2)
        + (left.posture.realOperatorEvidenceMissing ? 0 : 1)
        + (left.posture.approvalRequired ? 0 : 1);
      const rightScore = (right.posture.publicLaunchNoGo ? 0 : 2)
        + (right.posture.realOperatorEvidenceMissing ? 0 : 1)
        + (right.posture.approvalRequired ? 0 : 1);
      return leftScore - rightScore || left.title.localeCompare(right.title);
    });
  }, [data, prototypeDisabled]);

  const highestConcern = noGoDomains[0] || rankedDomains[0] || null;
  const evidenceMissing = data?.summary.realOperatorEvidenceMissingCount ?? 0;
  const domainCount = data?.summary.domainCount ?? 0;
  const evidenceAvailable = !prototypeDisabled && (data?.summary.evidenceToolingCount ?? 0) > 0;
  const primaryDrill = DRILL_ITEMS.find((item) => item.primary) || DRILL_ITEMS[0];

  const stateCopy = useMemo(() => {
    switch (surfaceMode) {
      case 'loading':
        return {
          eyebrow: '系统状态',
          title: '正在读取 Mission Control',
          detail: '正在读取只读 posture projection，不执行任何控制动作。',
          ownership: 'Admin Mission Control · 只读',
          evidence: '证据尚未汇总',
          severity: '读取中',
          marker: '○' as const,
          bandClass: 'border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)]',
          titleClass: TEXT_PRIMARY,
          icon: Radar,
        };
      case 'error':
        return {
          eyebrow: '系统状态',
          title: 'Mission Control 不可用',
          detail: state.error?.message || '只读 projection 读取失败。',
          ownership: 'Admin Mission Control · 故障面',
          evidence: '本页无可用证据摘要',
          severity: '不可用',
          marker: '■' as const,
          bandClass: 'border-[color:color-mix(in_srgb,var(--wolfy-market-down)_36%,var(--wolfy-border-subtle))] bg-[color:color-mix(in_srgb,var(--wolfy-market-down)_8%,var(--wolfy-surface-console))]',
          titleClass: 'text-[color:var(--wolfy-market-down)]',
          icon: Ban,
        };
      case 'prototype_disabled':
        return {
          eyebrow: '系统状态 · Prototype',
          title: 'Mission Control prototype 未启用',
          detail: data?.prototypeGate?.reasonCode
            ? `默认关闭（${safeText(data.prototypeGate.reasonCode)}）。未聚合 provider、quota、storage、task 或 admin-log 摘要。`
            : '默认关闭；未聚合 provider、quota、storage、task 或 admin-log 摘要。',
          ownership: 'Prototype gate · 管理员只读复核',
          evidence: 'ops 摘要未聚合 · 无 domain readiness',
          severity: 'Prototype 未启用',
          marker: '▲' as const,
          bandClass: 'border-[color:color-mix(in_srgb,var(--state-warning-border)_80%,var(--wolfy-border-subtle))] bg-[color:color-mix(in_srgb,var(--state-warning-bg)_70%,var(--wolfy-surface-console))]',
          titleClass: TEXT_PRIMARY,
          icon: ShieldAlert,
        };
      case 'unavailable':
        return {
          eyebrow: '系统状态',
          title: 'Mission Control 暂不可用',
          detail: '只读 projection 未返回数据。不要假定系统健康。',
          ownership: 'Admin Mission Control · 无快照',
          evidence: '无可用证据',
          severity: '不可用',
          marker: '■' as const,
          bandClass: 'border-[color:color-mix(in_srgb,var(--wolfy-market-down)_36%,var(--wolfy-border-subtle))] bg-[color:color-mix(in_srgb,var(--wolfy-market-down)_8%,var(--wolfy-surface-console))]',
          titleClass: 'text-[color:var(--wolfy-market-down)]',
          icon: Ban,
        };
      case 'active_clear':
        return {
          eyebrow: '系统状态',
          title: '发射门禁：暂无 NO-GO 域',
          detail: '仍保持只读 advisory；本页不会批准 public launch 或执行控制动作。',
          ownership: highestConcern?.title || '跨域 readiness',
          evidence: evidenceAvailable ? `证据工具 ${formatNumber(data?.summary.evidenceToolingCount || 0, 0)} 项` : '证据工具未报告',
          severity: data?.launchVerdict || 'CLEAR',
          marker: '●' as const,
          bandClass: 'border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)]',
          titleClass: TEXT_PRIMARY,
          icon: ShieldCheck,
        };
      case 'active_nogo':
      default:
        return {
          eyebrow: '系统状态 · 最高严重度',
          title: `Public launch 保持 NO-GO`,
          detail: highestConcern
            ? `最高关注域：${highestConcern.title} — ${safeText(highestConcern.statusLabel)}。缺真实证据 ${formatNumber(evidenceMissing, 0)} 项。`
            : `跨域 readiness 仍为 NO-GO；缺真实证据 ${formatNumber(evidenceMissing, 0)} 项。`,
          ownership: highestConcern?.title || '跨域 readiness',
          evidence: evidenceAvailable
            ? `证据工具 ${formatNumber(data?.summary.evidenceToolingCount || 0, 0)} · 缺真实证据 ${formatNumber(evidenceMissing, 0)}`
            : '证据不足',
          severity: data?.launchVerdict || 'NO_GO',
          marker: '■' as const,
          bandClass: 'border-[color:color-mix(in_srgb,var(--wolfy-market-down)_36%,var(--wolfy-border-subtle))] bg-[color:color-mix(in_srgb,var(--wolfy-market-down)_8%,var(--wolfy-surface-console))]',
          titleClass: TEXT_PRIMARY,
          icon: Ban,
        };
    }
  }, [surfaceMode, state.error, data, highestConcern, evidenceMissing, evidenceAvailable]);

  const StateIcon = stateCopy.icon;
  const primaryActionHref = surfaceMode === 'prototype_disabled' || surfaceMode === 'error' || surfaceMode === 'unavailable'
    ? '/zh/settings/system'
    : primaryDrill.href;
  const primaryActionLabel = surfaceMode === 'prototype_disabled' || surfaceMode === 'error' || surfaceMode === 'unavailable'
    ? '打开系统设置'
    : '安全主路径：证据工作流';
  const primaryActionHint = surfaceMode === 'prototype_disabled'
    ? '仅在有边界的管理员 prototype 复核中显式启用；默认路径保持隐藏。本页不执行启用。'
    : surfaceMode === 'error' || surfaceMode === 'unavailable'
      ? '改用系统设置与既有运维面，不要在本页执行控制。'
      : '补齐真实操作员证据与人工审批；不要从本页执行运行时控制。';

  if (!canReadOpsLogs) {
    return (
      <div
        data-testid="admin-mission-control-page"
        className="min-h-0 w-full flex-1 overflow-x-hidden overflow-y-auto no-scrollbar text-[color:var(--wolfy-text-primary)]"
      >
        <TerminalPageShell className="space-y-3 py-3 md:space-y-4 md:py-4">
          <TerminalNotice data-testid="admin-mission-capability-denied" variant="danger">
            Mission Control is fail-closed because this account is missing the ops log capability.
          </TerminalNotice>
        </TerminalPageShell>
      </div>
    );
  }

  return (
    <div
      data-testid="admin-mission-control-page"
      className="min-h-0 w-full flex-1 overflow-x-hidden overflow-y-auto no-scrollbar text-[color:var(--wolfy-text-primary)]"
    >
      <TerminalPageShell className="space-y-3 py-3 md:space-y-4 md:py-4">
        {/* Compact identity — not a hero canvas */}
        <header data-testid="admin-mission-identity" className="flex min-w-0 flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <p className={cn('text-[11px] font-medium uppercase tracking-[0.14em]', TEXT_MUTED)}>Admin Mission Control</p>
            <h1 className={cn('mt-0.5 text-base font-semibold leading-6 md:text-lg', TEXT_PRIMARY)}>运维任务总控</h1>
            <p className={cn('mt-1 max-w-3xl text-xs leading-5', TEXT_SECONDARY)}>
              只读 posture 投影：系统状态 → 最高严重度 → 责任域 → 证据 → 安全动作 → 诊断。
            </p>
          </div>
          <div className="flex flex-wrap gap-1.5" data-testid="admin-mission-identity-chips">
            <TerminalChip variant="info">只读</TerminalChip>
            {prototypeDisabled ? (
              <span
                data-testid="admin-mission-prototype-pill"
                className="inline-flex min-h-[28px] items-center gap-1 rounded-md border border-[color:color-mix(in_srgb,var(--state-warning-border)_90%,var(--wolfy-border-subtle))] bg-[var(--wolfy-surface-console)] px-2.5 py-1 text-xs font-semibold text-[color:var(--wolfy-text-primary)]"
              >
                <span aria-hidden="true" className="text-[color:var(--state-warning-text)]">▲</span>
                Prototype gate disabled
              </span>
            ) : null}
            <TerminalChip variant="danger">
              <span aria-hidden="true" className="mr-1">■</span>
              Public launch NO-GO
            </TerminalChip>
          </div>
        </header>

        {/* A/B — First viewport operator decision band */}
        <section
          data-testid="admin-mission-state-band"
          aria-label="Mission Control operator state"
          className={cn('rounded-xl border px-3 py-3 md:px-4 md:py-3.5', stateCopy.bandClass)}
        >
          <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div className="flex min-w-0 items-start gap-2.5">
              <StateIcon
                className={cn(
                  'mt-0.5 size-5 shrink-0',
                  surfaceMode === 'active_nogo' || surfaceMode === 'error' || surfaceMode === 'unavailable'
                    ? 'text-[color:var(--wolfy-market-down)]'
                    : surfaceMode === 'prototype_disabled'
                      ? 'text-[color:var(--state-warning-text)]'
                      : 'text-[color:var(--wolfy-text-muted)]',
                )}
                aria-hidden="true"
              />
              <div className="min-w-0">
                <p className={cn('text-[11px] font-semibold uppercase tracking-[0.16em]', TEXT_MUTED)}>{stateCopy.eyebrow}</p>
                <h2
                  data-testid="admin-mission-primary-state"
                  className={cn('mt-1 text-base font-semibold leading-6 md:text-lg', stateCopy.titleClass)}
                >
                  <span aria-hidden="true" className="mr-1.5">{stateCopy.marker}</span>
                  {stateCopy.title}
                </h2>
                <p data-testid="admin-mission-state-detail" className={cn('mt-1 text-sm leading-6', TEXT_SECONDARY)}>
                  {stateCopy.detail}
                </p>
                <dl className="mt-3 grid gap-2 sm:grid-cols-3">
                  <div className="min-w-0 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[color:color-mix(in_srgb,var(--wolfy-surface-console)_80%,transparent)] px-2.5 py-2">
                    <dt className={cn('text-[10px] font-semibold uppercase tracking-[0.14em]', TEXT_MUTED)}>责任域</dt>
                    <dd data-testid="admin-mission-ownership" className={cn('mt-1 text-xs font-medium leading-5', TEXT_PRIMARY)}>
                      {stateCopy.ownership}
                    </dd>
                  </div>
                  <div className="min-w-0 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[color:color-mix(in_srgb,var(--wolfy-surface-console)_80%,transparent)] px-2.5 py-2">
                    <dt className={cn('text-[10px] font-semibold uppercase tracking-[0.14em]', TEXT_MUTED)}>证据可用性</dt>
                    <dd data-testid="admin-mission-evidence-availability" className={cn('mt-1 text-xs font-medium leading-5', TEXT_PRIMARY)}>
                      {stateCopy.evidence}
                    </dd>
                  </div>
                  <div className="min-w-0 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[color:color-mix(in_srgb,var(--wolfy-surface-console)_80%,transparent)] px-2.5 py-2">
                    <dt className={cn('text-[10px] font-semibold uppercase tracking-[0.14em]', TEXT_MUTED)}>严重度标签</dt>
                    <dd data-testid="admin-mission-severity-label" className={cn('mt-1 text-xs font-semibold leading-5', TEXT_PRIMARY)}>
                      <span aria-hidden="true" className="mr-1">{stateCopy.marker}</span>
                      {stateCopy.severity}
                    </dd>
                  </div>
                </dl>
              </div>
            </div>

            {/* C — Primary safe action */}
            <div
              data-testid="admin-mission-primary-action"
              className="flex w-full min-w-[12rem] shrink-0 flex-col gap-2 lg:w-auto lg:max-w-xs"
            >
              <p className={cn('text-[10px] font-semibold uppercase tracking-[0.14em]', TEXT_MUTED)}>安全下一步</p>
              <Link
                to={primaryActionHref}
                data-testid="admin-mission-primary-action-link"
                className="theme-primary-action inline-flex min-h-[44px] items-center justify-center gap-2 rounded-md border border-[color:var(--theme-button-primary-border)] bg-[var(--theme-button-primary-bg)] px-4 text-sm font-medium transition-colors hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--wolfy-accent-focus)]"
              >
                <span>{primaryActionLabel}</span>
                <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
              <p className={cn('text-[11px] leading-5', TEXT_MUTED)}>{primaryActionHint}</p>
            </div>
          </div>
        </section>

        {state.error ? <ApiErrorAlert error={state.error} /> : null}

        <AdminOpsL0OverviewStrip
          dataTestId="admin-mission-l0-overview-strip"
          systemTrustState={
            surfaceMode === 'error' || surfaceMode === 'unavailable'
              ? 'unknown'
              : surfaceMode === 'prototype_disabled'
                ? 'review_required'
                : 'blocked'
          }
          impact={prototypeDisabled
            ? 'Prototype 默认关闭；未聚合 provider、quota、storage、task 或 admin-log 摘要。'
            : '覆盖安全、成本、数据源、存储、WS2、通知、组合/回测、路由和 private-beta posture。'}
          recommendedAction={prototypeDisabled
            ? '仅在有边界的管理员 prototype 复核中显式启用；默认路径保持隐藏。'
            : '补齐真实操作员证据与人工审批；不要从本页执行运行时控制。'}
          evidenceRef="admin_mission_control_v1"
          lastUpdated={data ? formatDateTime(data.generatedAt) : state.loading ? '读取中' : '不可用'}
        />

        {/* Compact posture metrics — supporting, not hero */}
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4" data-testid="admin-mission-summary-metrics">
          <TerminalMetric
            label="覆盖域"
            value={formatNumber(domainCount, 0)}
            subvalue="目标 9 个"
            valueClassName="text-[color:var(--wolfy-text-primary)]"
          />
          <TerminalMetric
            label="Public NO-GO"
            value={formatNumber(data?.summary.publicLaunchNoGoCount || 0, 0)}
            subvalue="无审批提升"
            valueClassName="text-[color:var(--wolfy-market-down)]"
          />
          <TerminalMetric
            label="缺真实证据"
            value={formatNumber(evidenceMissing, 0)}
            subvalue="需操作员材料"
            valueClassName="text-[color:var(--wolfy-text-primary)]"
          />
          <TerminalMetric
            label="证据工具"
            value={formatNumber(data?.summary.evidenceToolingCount || 0, 0)}
            subvalue="只读/离线"
            valueClassName="text-[color:var(--state-info-text)]"
          />
        </div>

        {/* C — Action hierarchy: primary already above; secondary diagnostics below */}
        <section data-testid="admin-mission-action-hierarchy" className="space-y-2" aria-label="Operator action hierarchy">
          <div className="flex items-center gap-2">
            <FileText className={cn('size-4', TEXT_MUTED)} aria-hidden="true" />
            <h2 className={cn('text-sm font-semibold', TEXT_PRIMARY)}>诊断与只读跳转</h2>
            <span className={cn('text-[11px]', TEXT_MUTED)}>次级 · 非破坏</span>
          </div>
          {!prototypeDisabled ? (
            <AdminDrillThroughStrip
              dataTestId="admin-mission-secondary-actions"
              className="mt-1"
              title="次级诊断下钻"
              items={DRILL_ITEMS.map(({ label, target, evidenceType, reason, params }) => ({
                label,
                target,
                evidenceType,
                reason,
                params,
              }))}
            />
          ) : (
            <TerminalNotice variant="caution" data-testid="admin-mission-disabled-diagnostics">
              Prototype 关闭时不提供 domain 诊断跳转墙。安全下一步是打开系统设置或保持默认隐藏路径。
            </TerminalNotice>
          )}
        </section>

        {/* Domain readiness queue — diagnostics, severity-ranked */}
        <TerminalPanel as="section" data-testid="admin-mission-domain-section" className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <ShieldAlert className="size-4 text-[color:var(--state-warning-text)]" aria-hidden="true" />
              <h2 className={cn('text-sm font-semibold', TEXT_PRIMARY)}>跨域 readiness 队列</h2>
            </div>
            <TerminalChip variant={data?.launchVerdict === 'NO_GO' ? 'danger' : 'neutral'}>
              {data?.launchVerdict || (state.loading ? 'LOADING' : '—')}
            </TerminalChip>
          </div>

          {state.loading ? (
            <TerminalEmptyState title="正在读取 Mission Control">
              正在读取只读 posture projection。
            </TerminalEmptyState>
          ) : prototypeDisabled ? (
            <TerminalEmptyState title="Mission Control prototype 未启用" data-testid="admin-mission-prototype-empty">
              默认关闭；未聚合 provider、quota、storage、task 或 admin-log 摘要。
            </TerminalEmptyState>
          ) : rankedDomains.length ? (
            <ol className="space-y-2" data-testid="admin-mission-domain-grid" aria-label="Domain readiness queue">
              {rankedDomains.map((domain, index) => (
                <DomainQueueItem key={domain.id} domain={domain} rank={index + 1} />
              ))}
            </ol>
          ) : (
            <TerminalEmptyState title="Mission Control 暂不可用">
              只读 projection 未返回数据。
            </TerminalEmptyState>
          )}
        </TerminalPanel>

        {/* Supporting boundary evidence — not first fold dominance */}
        <TerminalPanel as="aside" data-testid="admin-mission-boundary-panel" className="space-y-3">
          <div className="flex items-center gap-2">
            <LockKeyhole className="size-4 text-[color:var(--wolfy-text-muted)]" aria-hidden="true" />
            <h2 className={cn('text-sm font-semibold', TEXT_PRIMARY)}>发射门禁与边界</h2>
          </div>
          <div className="space-y-2" data-testid="admin-mission-boundary-list">
            {[
              { icon: ShieldCheck, text: data?.readOnly ? '数据只读' : '只读状态待确认', variant: 'success' as ChipVariant },
              { icon: Radar, text: data?.noExternalCalls ? '无外部调用' : '外部调用状态待确认', variant: 'info' as ChipVariant },
              { icon: AlertTriangle, text: data?.liveEnforcement === false ? '无 live enforcement' : '需要复核执行边界', variant: 'caution' as ChipVariant },
              { icon: FileCheck2, text: data?.releaseApproved === false ? 'releaseApproved=false' : '审批状态需复核', variant: 'danger' as ChipVariant },
            ].map(({ icon: Icon, text, variant }) => (
              <div key={text} className="flex min-w-0 items-center gap-2 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] px-3 py-2">
                <Icon className="size-4 shrink-0 text-[color:var(--wolfy-text-muted)]" aria-hidden="true" />
                <TerminalChip variant={variant}>{text}</TerminalChip>
              </div>
            ))}
          </div>

          <TerminalNotice variant="danger" className="mt-1">
            本页不会批准 public launch，也不会执行配额、provider、通知、restore、cleanup、migration 或 auth 行为。
          </TerminalNotice>

          {noGoDomains.length ? (
            <div className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-3" data-testid="admin-mission-nogo-list">
              <p className={cn('text-[10px] font-semibold uppercase tracking-[0.16em]', TEXT_MUTED)}>NO-GO domains</p>
              <ul className="mt-2 space-y-1.5 text-xs text-[color:var(--wolfy-text-secondary)]">
                {noGoDomains.slice(0, 6).map((domain) => (
                  <li key={domain.id} className="break-words">
                    <CheckCircle2 className="mr-1.5 inline size-3.5 text-[color:var(--wolfy-market-down)]" aria-hidden="true" />
                    {domain.title}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </TerminalPanel>
      </TerminalPageShell>
    </div>
  );
};

export default AdminMissionControlPage;
