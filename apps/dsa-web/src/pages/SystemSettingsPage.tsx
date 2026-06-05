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

const SystemSettingsPage: FC = () => {
  const [isFactoryResetConfirmOpen, setIsFactoryResetConfirmOpen] = useState(false);
  const pendingFactoryResetButtonRef = useRef<HTMLButtonElement | null>(null);
  const bypassFactoryResetInterceptRef = useRef(false);
  const isEnglish = typeof window !== 'undefined' && /^\/en(?:\/|$)/.test(window.location.pathname);
  const pageCopy = isEnglish
    ? {
      eyebrow: 'Admin control entry',
      title: 'System Settings',
      adminLandingChip: 'Default admin landing',
      confirmChip: 'Changes require confirmation',
      description:
        'This page is the default landing for admin settings and control work, not a missing standalone dashboard. Review overall risk, pending setup, and safe next steps before opening the control center below.',
      overview: [
        {
          label: 'Current status',
          value: 'Waiting for the latest snapshot',
          note: 'The control center below loads system health, config domains, and credential summaries.',
        },
        {
          label: 'Watch items',
          value: 'Credentials, schedules, system state, risky actions',
          note: 'Risky actions stay in secondary areas and still require confirmation.',
        },
        {
          label: 'Next step',
          value: 'Start with the overview, then open a specific domain',
          note: 'Detailed settings stay inside the control center below.',
        },
      ],
      l0Impact: 'Credentials, schedules, system state, and risky actions still need confirmation from the control center snapshot.',
      l0RecommendedAction: 'Review the system summary first, then open the relevant settings domain.',
      l0EvidenceRef: 'System control center / summary below',
      l0LastUpdated: 'Updates after the snapshot loads',
      loadingTitle: 'Loading system control center',
      loadingBody: 'The top-level risk summary is ready. The latest snapshot and settings workspace are loading below.',
    }
    : {
      eyebrow: '管理员控制入口',
      title: '系统设置',
      adminLandingChip: '管理员默认落点',
      confirmChip: '变更需保存确认',
      description:
        '这里是管理员进入系统配置与控制事项的默认落点，不是缺失的独立仪表盘。请先确认全局风险、待处理配置和安全下一步，再进入下方运维中心。',
      overview: [
        {
          label: '当前状态',
          value: '等待最新快照',
          note: '由下方运维中心加载系统健康、配置域与凭证摘要。',
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
      l0Impact: '凭证、调度、系统状态与高风险操作仍需结合运维中心快照确认。',
      l0RecommendedAction: '先看系统运维摘要，再进入相关配置域。',
      l0EvidenceRef: '系统运维中心 / 下方摘要',
      l0LastUpdated: '配置快照加载后更新',
      loadingTitle: '正在加载系统运维中心',
      loadingBody: '外层风险总览已就绪，最新快照与配置工作区正在下方加载。',
    };
  const factoryResetDialogCopy = isEnglish
    ? {
      title: 'Confirm system settings reset',
      message: 'This action may reset system-level settings and clear sessions, analysis/chat history, scanner/backtest/portfolio usage data, and notification targets related to system initialization. It may be difficult to undo.',
      cancel: 'Cancel',
      confirm: 'Confirm reset',
    }
    : {
      title: '确认重置系统设置',
      message: '该操作可能重置系统级设置，并清理与系统初始化相关的会话、分析与聊天历史、扫描/回测/持仓使用数据以及通知目标；执行后较难撤销。',
      cancel: '取消',
      confirm: '确认重置',
    };

  const handleFactoryResetActionCapture = (event: ReactMouseEvent<HTMLElement>) => {
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }

    const resetButton = target.closest(FACTORY_RESET_ACTION_SELECTOR) as HTMLButtonElement | null;
    if (!resetButton) {
      return;
    }

    if (bypassFactoryResetInterceptRef.current) {
      bypassFactoryResetInterceptRef.current = false;
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    pendingFactoryResetButtonRef.current = resetButton;
    setIsFactoryResetConfirmOpen(true);
  };

  const handleCancelFactoryResetConfirm = () => {
    pendingFactoryResetButtonRef.current = null;
    setIsFactoryResetConfirmOpen(false);
  };

  const handleConfirmFactoryReset = () => {
    const resetButton = pendingFactoryResetButtonRef.current;
    pendingFactoryResetButtonRef.current = null;
    setIsFactoryResetConfirmOpen(false);
    if (!resetButton) {
      return;
    }
    bypassFactoryResetInterceptRef.current = true;
    resetButton.click();
  };

  return (
    <TerminalPageShell
      data-testid="system-settings-page"
      className="min-h-0 flex-1 overflow-x-hidden py-5 text-white md:py-6"
      onClickCapture={handleFactoryResetActionCapture}
    >
      <div data-testid="system-settings-shell-header" className="flex min-w-0 flex-col gap-4">
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
        <p className="max-w-3xl text-sm leading-6 text-white/58">
          {pageCopy.description}
        </p>
        <AdminOpsL0OverviewStrip
          dataTestId="system-settings-l0-overview-strip"
          systemTrustState="unknown"
          language={isEnglish ? 'en' : 'zh'}
          impact={pageCopy.l0Impact}
          recommendedAction={pageCopy.l0RecommendedAction}
          evidenceRef={pageCopy.l0EvidenceRef}
          lastUpdated={pageCopy.l0LastUpdated}
        />
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {pageCopy.overview.map(({ label, value, note }) => (
            <TerminalMetric
              key={label}
              label={label}
              value={value}
              subvalue={note}
              className="min-w-0"
              valueClassName="text-sm font-semibold tracking-normal"
            />
          ))}
        </div>
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
        isOpen={isFactoryResetConfirmOpen}
        title={factoryResetDialogCopy.title}
        message={factoryResetDialogCopy.message}
        confirmText={factoryResetDialogCopy.confirm}
        cancelText={factoryResetDialogCopy.cancel}
        isDanger
        onConfirm={handleConfirmFactoryReset}
        onCancel={handleCancelFactoryResetConfirm}
      />
    </TerminalPageShell>
  );
};

export default SystemSettingsPage;
