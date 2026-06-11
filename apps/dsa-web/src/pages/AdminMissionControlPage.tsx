import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, FileCheck2, LockKeyhole, Radar, ShieldCheck } from 'lucide-react';
import { adminMissionControlApi, type MissionControlDomainSlice, type MissionControlResponse } from '../api/adminMissionControl';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { ApiErrorAlert } from '../components/common/ApiErrorAlert';
import AdminDrillThroughStrip from '../components/admin/AdminDrillThroughStrip';
import AdminOpsL0OverviewStrip from '../components/admin/AdminOpsL0OverviewStrip';
import {
  TerminalChip,
  TerminalEmptyState,
  TerminalGrid,
  TerminalMetric,
  TerminalNotice,
  TerminalPageHeading,
  TerminalPageShell,
  TerminalPanel,
  TerminalSectionHeader,
} from '../components/terminal/TerminalPrimitives';
import { formatDateTime, formatNumber } from '../utils/format';

type LoadState = {
  loading: boolean;
  error: ParsedApiError | null;
  data: MissionControlResponse | null;
};

type ChipVariant = React.ComponentProps<typeof TerminalChip>['variant'];

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

const DomainCard: React.FC<{ domain: MissionControlDomainSlice }> = ({ domain }) => (
  <article
    data-testid="admin-mission-domain-card"
    aria-label={`${domain.title}：${domain.statusLabel}`}
    className="min-w-0 rounded-xl border border-white/[0.08] bg-white/[0.025] p-3"
  >
    <div className="flex min-w-0 items-start justify-between gap-3">
      <div className="min-w-0">
        <p className="break-words text-sm font-semibold leading-5 text-white/88">{domain.title}</p>
        <p className="mt-1 break-words text-[11px] leading-5 text-white/46">{safeText(domain.summary)}</p>
      </div>
      <TerminalChip variant={statusVariant(domain)} className="shrink-0">
        {safeText(domain.statusLabel)}
      </TerminalChip>
    </div>

    <div className="mt-3 flex flex-wrap gap-1.5" aria-label={`${domain.title} posture flags`}>
      {postureFlags(domain).map((flag) => (
        <TerminalChip key={flag.key} variant={flag.active ? (flag.key === 'publicLaunchNoGo' ? 'danger' : 'caution') : 'neutral'}>
          {flag.label}
        </TerminalChip>
      ))}
    </div>

    <dl className="mt-3 grid gap-2 text-xs md:grid-cols-2">
      <div className="min-w-0 rounded-lg border border-white/[0.06] bg-black/10 px-2.5 py-2">
        <dt className="text-[10px] font-semibold uppercase tracking-[0.14em] text-white/34">只读边界</dt>
        <dd className="mt-1 text-white/70">{domain.readOnly && domain.noExternalCalls && !domain.liveEnforcement ? '只读 / 无外呼 / 无执行' : '需复核'}</dd>
      </div>
      <div className="min-w-0 rounded-lg border border-white/[0.06] bg-black/10 px-2.5 py-2">
        <dt className="text-[10px] font-semibold uppercase tracking-[0.14em] text-white/34">证据引用</dt>
        <dd className="mt-1 break-words text-white/70">{safeRefList(domain.evidenceRefs)}</dd>
      </div>
    </dl>
  </article>
);

const AdminMissionControlPage: React.FC = () => {
  const [state, setState] = useState<LoadState>({ loading: true, error: null, data: null });

  useEffect(() => {
    let active = true;
    setState((current) => ({ ...current, loading: true, error: null }));
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
  }, []);

  const data = state.data;
  const noGoDomains = useMemo(
    () => data?.domains.filter((domain) => domain.posture.publicLaunchNoGo) || [],
    [data],
  );

  return (
    <div
      data-testid="admin-mission-control-page"
      className="min-h-0 w-full flex-1 overflow-x-hidden overflow-y-auto no-scrollbar text-white"
    >
      <TerminalPageShell className="py-5 md:py-6">
        <TerminalPanel as="section" className="relative overflow-hidden">
          <TerminalPageHeading
            eyebrow="Admin Mission Control"
            title="运维任务总控"
            action={(
              <div className="flex flex-wrap gap-2">
                <TerminalChip variant="info">只读</TerminalChip>
                <TerminalChip variant="danger">Public launch NO-GO</TerminalChip>
              </div>
            )}
          />
          <AdminOpsL0OverviewStrip
            dataTestId="admin-mission-l0-overview-strip"
            className="mt-4"
            systemTrustState="blocked"
            impact="覆盖安全、成本、数据源、存储、WS2、通知、组合/回测、路由和 private-beta posture。"
            recommendedAction="补齐真实操作员证据与人工审批；不要从本页执行运行时控制。"
            evidenceRef="admin_mission_control_v1"
            lastUpdated={data ? formatDateTime(data.generatedAt) : state.loading ? '读取中' : '不可用'}
          />
          <AdminDrillThroughStrip
            className="mt-4"
            items={[
              {
                label: '查看证据工作流',
                target: 'evidence',
                evidenceType: 'operator evidence',
                reason: '从总控进入脱敏证据、模板和人工复核路径。',
                params: { ref: 'mission_control' },
              },
              {
                label: '查看系统日志',
                target: 'logs',
                evidenceType: 'ops status',
                reason: '回看 mission-control 相关的只读运行证据。',
                params: { tab: 'business', query: 'mission control', since: '24h' },
              },
              {
                label: '查看数据源运维',
                target: 'marketProviders',
                evidenceType: 'provider readiness',
                reason: '继续检查数据源覆盖、fallback 和 readiness 缺口。',
                params: { surface: 'market_overview' },
              },
              {
                label: '查看成本观测',
                target: 'cost',
                evidenceType: 'quota cost',
                reason: '确认成本与配额仍是观测态而非 live enforcement。',
                params: { window: '24h', area: 'all' },
              },
            ]}
          />
        </TerminalPanel>

        {state.error ? <ApiErrorAlert error={state.error} /> : null}

        <TerminalGrid>
          <TerminalPanel as="section" className="xl:col-span-8">
            <TerminalSectionHeader
              eyebrow="L1 Readiness overview"
              title="跨域 readiness posture"
              action={<TerminalChip variant={data?.launchVerdict === 'NO_GO' ? 'danger' : 'neutral'}>{data?.launchVerdict || 'LOADING'}</TerminalChip>}
            />
            {state.loading ? (
              <TerminalEmptyState title="正在读取 Mission Control">
                正在读取只读 posture projection。
              </TerminalEmptyState>
            ) : data ? (
              <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2" data-testid="admin-mission-domain-grid">
                {data.domains.map((domain) => (
                  <DomainCard key={domain.id} domain={domain} />
                ))}
              </div>
            ) : (
              <TerminalEmptyState title="Mission Control 暂不可用">
                只读 projection 未返回数据。
              </TerminalEmptyState>
            )}
          </TerminalPanel>

          <TerminalPanel as="aside" className="xl:col-span-4">
            <TerminalSectionHeader
              eyebrow="L1 System posture"
              title="发射门禁摘要"
              action={<LockKeyhole className="size-4 text-amber-200" aria-hidden="true" />}
            />
            <div className="mt-4 grid grid-cols-2 gap-2" data-testid="admin-mission-summary-metrics">
              <TerminalMetric
                label="覆盖域"
                value={formatNumber(data?.summary.domainCount || 0, 0)}
                subvalue="目标 9 个"
                valueClassName="text-white"
              />
              <TerminalMetric
                label="Public NO-GO"
                value={formatNumber(data?.summary.publicLaunchNoGoCount || 0, 0)}
                subvalue="无审批提升"
                valueClassName="text-rose-300"
              />
              <TerminalMetric
                label="缺真实证据"
                value={formatNumber(data?.summary.realOperatorEvidenceMissingCount || 0, 0)}
                subvalue="需操作员材料"
                valueClassName="text-amber-200"
              />
              <TerminalMetric
                label="证据工具"
                value={formatNumber(data?.summary.evidenceToolingCount || 0, 0)}
                subvalue="只读/离线"
                valueClassName="text-cyan-200"
              />
            </div>

            <div className="mt-4 space-y-2" data-testid="admin-mission-boundary-list">
              {[
                { icon: ShieldCheck, text: data?.readOnly ? '数据只读' : '只读状态待确认', variant: 'success' as ChipVariant },
                { icon: Radar, text: data?.noExternalCalls ? '无外部调用' : '外部调用状态待确认', variant: 'info' as ChipVariant },
                { icon: AlertTriangle, text: data?.liveEnforcement === false ? '无 live enforcement' : '需要复核执行边界', variant: 'caution' as ChipVariant },
                { icon: FileCheck2, text: data?.releaseApproved === false ? 'releaseApproved=false' : '审批状态需复核', variant: 'danger' as ChipVariant },
              ].map(({ icon: Icon, text, variant }) => (
                <div key={text} className="flex min-w-0 items-center gap-2 rounded-lg border border-white/[0.06] bg-black/10 px-3 py-2">
                  <Icon className="size-4 shrink-0 text-white/46" aria-hidden="true" />
                  <TerminalChip variant={variant}>{text}</TerminalChip>
                </div>
              ))}
            </div>

            <TerminalNotice variant="danger" className="mt-4">
              本页不会批准 public launch，也不会执行配额、provider、通知、restore、cleanup、migration 或 auth 行为。
            </TerminalNotice>

            {noGoDomains.length ? (
              <div className="mt-4 rounded-xl border border-white/[0.06] bg-white/[0.02] p-3" data-testid="admin-mission-nogo-list">
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-white/34">NO-GO domains</p>
                <ul className="mt-2 space-y-1.5 text-xs text-white/68">
                  {noGoDomains.slice(0, 6).map((domain) => (
                    <li key={domain.id} className="break-words">
                      <CheckCircle2 className="mr-1.5 inline size-3.5 text-rose-300" aria-hidden="true" />
                      {domain.title}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </TerminalPanel>
        </TerminalGrid>
      </TerminalPageShell>
    </div>
  );
};

export default AdminMissionControlPage;
