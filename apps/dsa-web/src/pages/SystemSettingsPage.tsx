import { Suspense, lazy, type FC, type MouseEvent as ReactMouseEvent, useRef, useState } from 'react';
import {
  TerminalChip,
  TerminalMetric,
  TerminalPageHeading,
  TerminalPageShell,
} from '../components/terminal/TerminalPrimitives';
import AdminOpsL0OverviewStrip from '../components/admin/AdminOpsL0OverviewStrip';
import { ConfirmDialog } from '../components/common/ConfirmDialog';

const SettingsPage = lazy(() => import('./SettingsPage'));

const FACTORY_RESET_ACTION_SELECTOR = '[data-system-settings-reset-action="factory_reset"]';
type ResetIntent = 'draft_reset' | 'factory_reset';

function normalizeButtonText(value: string | null | undefined): string {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

const SystemSettingsPage: FC = () => {
  const [pendingResetIntent, setPendingResetIntent] = useState<ResetIntent | null>(null);
  const pendingResetButtonRef = useRef<HTMLButtonElement | null>(null);
  const bypassResetInterceptRef = useRef(false);
  const isEnglish = typeof window !== 'undefined' && /^\/en(?:\/|$)/.test(window.location.pathname);
  const pageCopy = isEnglish
    ? {
      eyebrow: 'Admin control entry',
      title: 'System Settings',
      adminLandingChip: 'Default admin landing',
      confirmChip: 'Changes require confirmation',
      resetButtonLabel: 'Reset',
      description:
        'This page is the default landing for admin settings and control work, not a missing standalone dashboard. Review overall risk, pending setup, and safe next steps before opening the control center below.',
      overview: [
        {
          label: 'Current status',
          value: 'Needs review: access setup, schedules, and system state require confirmation',
          note: 'This is a frontend operator entry verdict. The control center below loads the latest snapshot.',
        },
        {
          label: 'Watch items',
          value: 'Access readiness, schedules, system state, risky actions',
          note: 'Risky actions stay in secondary areas and still require confirmation.',
        },
        {
          label: 'Next step',
          value: 'Start with the overview, then open a specific domain',
          note: 'Detailed settings stay inside the control center below.',
        },
      ],
      l0Impact: 'Access setup, schedules, system state, and risky actions need step-by-step confirmation in the control center.',
      l0RecommendedAction: 'Review the system summary first, then open the relevant settings domain.',
      l0EvidenceRef: 'System control center / summary below',
      l0LastUpdated: 'Updates after the snapshot loads',
      boundaryEyebrow: 'Visual boundary',
      boundaryTitle: 'Separate normal settings from destructive maintenance',
      boundaryDescription:
        'Daily configuration stays in the normal workspace. Destructive maintenance stays grouped in a dedicated secondary danger zone with the existing confirmation chain.',
      ordinaryZoneTitle: 'Normal settings workspace',
      ordinaryZoneSummary: 'Use this area for routine configuration and review.',
      ordinaryZoneItems: [
        'AI model, route, and notification settings',
        'Data source setup, system summary, and compatibility checks',
        'Standard save flow remains separate from maintenance actions',
      ],
      dangerZoneTitle: 'Danger zone',
      dangerZoneSummary: 'High-risk maintenance remains visually isolated before you enter it.',
      dangerZoneItems: [
        'Runtime maintenance cleanup controls',
        'Factory reset and system initialization paths',
        'Other action-level flows that still require explicit confirmation',
      ],
      dangerZoneNote: 'Open this area only when needed; it is not presented as a normal configuration step.',
      loadingTitle: 'Loading system control center',
      loadingBody: 'The top-level risk summary is ready. The latest snapshot and settings workspace are loading below.',
      highestIssueLabel: 'Highest issue',
      highestIssueValue: 'Access setup, schedules, and system state need step-by-step confirmation',
      nextDomainLabel: 'Next configuration domain',
      nextDomainValue: 'Open overview, then pick the domain that owns the open issue',
    }
    : {
      eyebrow: '管理员控制入口',
      title: '系统设置',
      adminLandingChip: '管理员默认落点',
      confirmChip: '变更需保存确认',
      resetButtonLabel: '重置',
      description:
        '这里是管理员进入系统配置与控制事项的默认落点，不是缺失的独立仪表盘。请先确认全局风险、待处理配置和安全下一步，再进入下方运维中心。',
      overview: [
        {
          label: '当前状态',
          value: '需要关注：凭证、调度、系统状态需逐项确认',
          note: '这是前端运维入口判断；最新配置快照由下方运维中心加载。',
        },
        {
          label: '需关注',
          value: '凭证、调度、系统状态、高风险操作',
          note: '高风险操作保留在二级区域，并继续要求确认。',
        },
        {
          label: '下一步',
          value: '先看总览，再进入具体配置域',
          note: '详细配置项保留在下方运维中心。',
        },
      ],
      l0Impact: '凭证、调度、系统状态与高风险操作需要在运维中心逐项确认。',
      l0RecommendedAction: '先看系统运维摘要，再进入相关配置域。',
      l0EvidenceRef: '系统运维中心 / 下方摘要',
      l0LastUpdated: '配置快照加载后更新',
      boundaryEyebrow: '视觉边界',
      boundaryTitle: '将常规配置与危险维护动作分开呈现',
      boundaryDescription:
        '日常配置保留在常规工作区，缓存清理、系统初始化等高风险维护动作统一归入独立危险操作区，并继续沿用现有确认链路。',
      ordinaryZoneTitle: '常规配置区',
      ordinaryZoneSummary: '先在这里处理日常配置与系统检查。',
      ordinaryZoneItems: [
        'AI 模型、路由与通知配置',
        '数据源设置、系统摘要与兼容性检查',
        '标准保存流程与维护动作保持分离',
      ],
      dangerZoneTitle: '危险操作区',
      dangerZoneSummary: '高风险维护动作在进入前就保持独立的视觉边界。',
      dangerZoneItems: [
        '运行态维护清理与维护控制',
        '工厂重置与系统初始化路径',
        '其他仍需显式确认的高风险动作',
      ],
      dangerZoneNote: '仅在确有需要时进入，不作为日常配置步骤并列展示。',
      loadingTitle: '正在加载系统运维中心',
      loadingBody: '外层风险总览已就绪，最新快照与配置工作区正在下方加载。',
      highestIssueLabel: '最高优先级问题',
      highestIssueValue: '凭证、调度、系统状态需逐项确认',
      nextDomainLabel: '下一配置域',
      nextDomainValue: '先看总览，再进入对应配置域处理',
    };
  const resetDialogCopy = isEnglish
    ? {
      draft_reset: {
        title: 'Confirm reset?',
        message: 'All unsaved changes will be lost.',
        cancel: 'Cancel',
        confirm: 'Confirm reset',
      },
      factory_reset: {
        title: 'Confirm system settings reset?',
        message: 'All unsaved changes will be lost. System initialization will still require the existing confirmation step.',
        cancel: 'Cancel',
        confirm: 'Continue',
      },
    }
    : {
      draft_reset: {
        title: '确认重置？',
        message: '所有未保存更改将丢失。',
        cancel: '取消',
        confirm: '确认重置',
      },
      factory_reset: {
        title: '确认重置系统设置？',
        message: '所有未保存更改将丢失，系统初始化仍会进入现有确认步骤。',
        cancel: '取消',
        confirm: '继续',
      },
    };

  const handleResetActionCapture = (event: ReactMouseEvent<HTMLElement>) => {
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }

    if (bypassResetInterceptRef.current) {
      bypassResetInterceptRef.current = false;
      return;
    }

    const factoryResetButton = target.closest(FACTORY_RESET_ACTION_SELECTOR) as HTMLButtonElement | null;
    if (factoryResetButton) {
      event.preventDefault();
      event.stopPropagation();
      pendingResetButtonRef.current = factoryResetButton;
      setPendingResetIntent('factory_reset');
      return;
    }

    const resetButton = target.closest('button') as HTMLButtonElement | null;
    if (!resetButton) {
      return;
    }

    if (normalizeButtonText(resetButton.textContent) !== pageCopy.resetButtonLabel) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    pendingResetButtonRef.current = resetButton;
    setPendingResetIntent('draft_reset');
  };

  const handleCancelResetConfirm = () => {
    pendingResetButtonRef.current = null;
    setPendingResetIntent(null);
  };

  const handleConfirmReset = () => {
    const resetButton = pendingResetButtonRef.current;
    pendingResetButtonRef.current = null;
    setPendingResetIntent(null);
    if (!resetButton) {
      return;
    }
    bypassResetInterceptRef.current = true;
    resetButton.click();
  };

  const activeDialogCopy = resetDialogCopy[pendingResetIntent ?? 'draft_reset'];

  return (
    <TerminalPageShell
      data-testid="system-settings-page"
      className="min-h-0 flex-1 overflow-x-hidden py-5 text-[color:var(--wolfy-text-primary)] md:py-6"
      onClickCapture={handleResetActionCapture}
    >
      <div data-testid="system-settings-shell-header" className="flex min-w-0 flex-col gap-3">
        <TerminalPageHeading
          data-testid="system-settings-heading"
          eyebrow={pageCopy.eyebrow}
          title={pageCopy.title}
          action={(
            <div className="flex flex-wrap gap-2">
              <TerminalChip variant="info">{pageCopy.adminLandingChip}</TerminalChip>
              <TerminalChip variant="caution">{pageCopy.confirmChip}</TerminalChip>
            </div>
          )}
        />
        <p className="max-w-3xl text-sm leading-6 text-[color:var(--wolfy-text-muted)]">
          {pageCopy.description}
        </p>

        {/* Compact operator status → highest issue → next domain (not five equal tiles + metric wall) */}
        <AdminOpsL0OverviewStrip
          dataTestId="system-settings-l0-overview-strip"
          systemTrustState="review_required"
          language={isEnglish ? 'en' : 'zh'}
          impact={pageCopy.l0Impact}
          recommendedAction={pageCopy.l0RecommendedAction}
          evidenceRef={pageCopy.l0EvidenceRef}
          lastUpdated={pageCopy.l0LastUpdated}
        />

        <section
          data-testid="system-settings-operator-priority"
          className="grid min-w-0 gap-2 rounded-lg border border-[color:color-mix(in_srgb,var(--state-warning-border)_70%,var(--wolfy-border-subtle))] bg-[color:color-mix(in_srgb,var(--state-warning-bg)_55%,var(--wolfy-surface-console))] px-3 py-2.5 md:grid-cols-2"
        >
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[color:var(--wolfy-text-muted)]">
              {pageCopy.highestIssueLabel}
            </p>
            <p className="mt-1 text-sm font-semibold leading-5 text-[color:var(--wolfy-text-primary)]">
              <span aria-hidden="true" className="mr-1.5 text-[color:var(--state-warning-text)]">▲</span>
              {pageCopy.highestIssueValue}
            </p>
          </div>
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[color:var(--wolfy-text-muted)]">
              {pageCopy.nextDomainLabel}
            </p>
            <p className="mt-1 text-sm font-semibold leading-5 text-[color:var(--wolfy-text-primary)]">
              {pageCopy.nextDomainValue}
            </p>
          </div>
        </section>

        <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
          {pageCopy.overview.map(({ label, value, note }) => (
            <TerminalMetric
              key={label}
              label={label}
              value={value}
              subvalue={note}
              className="min-w-0"
              valueClassName="text-sm font-semibold tracking-normal text-[color:var(--wolfy-text-primary)]"
            />
          ))}
        </div>

        <section
          data-testid="system-settings-visual-boundary"
          className="min-w-0 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-3 md:p-4"
        >
          <div className="flex min-w-0 flex-col gap-1.5">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[color:var(--wolfy-text-muted)]">
              {pageCopy.boundaryEyebrow}
            </p>
            <div className="min-w-0">
              <h2 className="text-sm font-semibold text-[color:var(--wolfy-text-primary)] md:text-base">{pageCopy.boundaryTitle}</h2>
              <p className="mt-1.5 max-w-4xl text-xs leading-6 text-[color:var(--wolfy-text-muted)] md:text-sm">
                {pageCopy.boundaryDescription}
              </p>
            </div>
          </div>
          <div className="mt-3 grid min-w-0 grid-cols-1 gap-2 xl:grid-cols-[minmax(0,1.08fr)_minmax(0,0.92fr)]">
            <article className="min-w-0 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3">
              <div className="flex min-w-0 flex-col gap-2">
                <div>
                  <p className="text-xs font-semibold text-[color:var(--wolfy-text-primary)]">{pageCopy.ordinaryZoneTitle}</p>
                  <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                    {pageCopy.ordinaryZoneSummary}
                  </p>
                </div>
                <ul className="space-y-1.5 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">
                  {pageCopy.ordinaryZoneItems.map((item) => (
                    <li key={item} className="flex min-w-0 items-start gap-2">
                      <span aria-hidden="true" className="mt-1 size-1.5 shrink-0 rounded-full bg-[color:var(--wolfy-market-up)]" />
                      <span className="min-w-0">{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </article>
            <article className="min-w-0 rounded-lg border border-[color:var(--state-warning-border)] bg-[color:color-mix(in_srgb,var(--state-warning-bg)_70%,var(--wolfy-surface-console))] p-3">
              <div className="border-l-2 border-[color:var(--state-warning-text)] pl-3">
                <div className="flex min-w-0 flex-col gap-2">
                  <div>
                    <p className="text-xs font-semibold text-[color:var(--state-warning-text)]">
                      <span aria-hidden="true" className="mr-1">▲</span>
                      {pageCopy.dangerZoneTitle}
                    </p>
                    <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">
                      {pageCopy.dangerZoneSummary}
                    </p>
                  </div>
                  <ul className="space-y-1.5 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">
                    {pageCopy.dangerZoneItems.map((item) => (
                      <li key={item} className="flex min-w-0 items-start gap-2">
                        <span aria-hidden="true" className="mt-1 size-1.5 shrink-0 rounded-full bg-[color:var(--state-warning-text)]" />
                        <span className="min-w-0">{item}</span>
                      </li>
                    ))}
                  </ul>
                  <p className="rounded-md border border-[color:var(--state-warning-border)] bg-[var(--wolfy-surface-input)] px-3 py-2 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">
                    {pageCopy.dangerZoneNote}
                  </p>
                </div>
              </div>
            </article>
          </div>
        </section>
      </div>
      <div className="min-h-0 flex-1 overflow-hidden">
        <Suspense
          fallback={(
            <section
              role="status"
              aria-busy="true"
              aria-live="polite"
              data-testid="system-settings-loading"
              className="min-h-[220px] rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-4 text-sm text-[color:var(--wolfy-text-secondary)]"
            >
              <div className="flex min-w-0 flex-col gap-2">
                <span className="text-xs font-medium text-[color:var(--wolfy-text-primary)]">{pageCopy.loadingTitle}</span>
                <span className="text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                  {pageCopy.loadingBody}
                </span>
              </div>
              <div className="mt-4 grid gap-2" aria-hidden="true">
                <span className="h-3 w-1/2 rounded-full bg-[color:color-mix(in_srgb,var(--wolfy-text-primary)_12%,transparent)]" />
                <span className="h-3 w-2/3 rounded-full bg-[color:color-mix(in_srgb,var(--wolfy-text-primary)_9%,transparent)]" />
                <span className="h-3 w-1/3 rounded-full bg-[color:color-mix(in_srgb,var(--wolfy-text-primary)_7%,transparent)]" />
              </div>
            </section>
          )}
        >
          <SettingsPage />
        </Suspense>
      </div>
      <ConfirmDialog
        isOpen={pendingResetIntent !== null}
        title={activeDialogCopy.title}
        message={activeDialogCopy.message}
        confirmText={activeDialogCopy.confirm}
        cancelText={activeDialogCopy.cancel}
        isDanger
        onConfirm={handleConfirmReset}
        onCancel={handleCancelResetConfirm}
      />
    </TerminalPageShell>
  );
};

export default SystemSettingsPage;
