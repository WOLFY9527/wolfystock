import { Suspense, lazy, type FC } from 'react';
import {
  TerminalChip,
  TerminalMetric,
  TerminalPageHeading,
  TerminalPageShell,
} from '../components/terminal/TerminalPrimitives';
import AdminOpsL0OverviewStrip from '../components/admin/AdminOpsL0OverviewStrip';

const SettingsPage = lazy(() => import('./SettingsPage'));

const SYSTEM_SETTINGS_OVERVIEW = [
  {
    label: '当前状态',
    value: '等待配置快照',
    note: '由下方运维中心加载系统健康、配置域与凭证摘要',
  },
  {
    label: '需关注',
    value: '凭证、调度、缓存、危险动作',
    note: '危险动作在二级区域并带确认流程',
  },
  {
    label: '下一步',
    value: '先看总览，再进入具体域',
    note: '原始配置字段默认通过抽屉处理',
  },
] as const;

const settingsConsoleFallback = (
  <section
    role="status"
    aria-busy="true"
    aria-live="polite"
    data-testid="system-settings-loading"
    className="min-h-[220px] rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-4 text-sm text-[color:var(--wolfy-text-secondary)]"
  >
    <div className="flex min-w-0 flex-col gap-2">
      <span className="text-xs font-medium text-[color:var(--wolfy-text-primary)]">正在加载系统运维中心</span>
      <span className="text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
        外层风险总览已就绪，配置快照与操作面板正在进入运维中心。
      </span>
    </div>
    <div className="mt-4 grid gap-2" aria-hidden="true">
      <span className="h-3 w-1/2 rounded-full bg-[color:color-mix(in_srgb,var(--wolfy-text-primary)_12%,transparent)]" />
      <span className="h-3 w-2/3 rounded-full bg-[color:color-mix(in_srgb,var(--wolfy-text-primary)_9%,transparent)]" />
      <span className="h-3 w-1/3 rounded-full bg-[color:color-mix(in_srgb,var(--wolfy-text-primary)_7%,transparent)]" />
    </div>
  </section>
);

const SystemSettingsPage: FC = () => {
  return (
    <TerminalPageShell
      data-testid="system-settings-page"
      className="min-h-0 flex-1 overflow-x-hidden py-5 text-white md:py-6"
    >
      <div data-testid="system-settings-shell-header" className="flex min-w-0 flex-col gap-4">
        <TerminalPageHeading
          data-testid="system-settings-heading"
          eyebrow="系统风险总览"
          title="系统设置"
          action={(
            <div className="flex flex-wrap gap-2">
              <TerminalChip variant="info">管理员只读入口优先</TerminalChip>
              <TerminalChip variant="caution">变更需保存确认</TerminalChip>
            </div>
          )}
        />
        <p className="max-w-3xl text-sm leading-6 text-white/58">
          先确认全局风险、待处理配置和下一步安全动作；深层配置、原始字段和危险系统动作留在下方运维中心。
        </p>
        <AdminOpsL0OverviewStrip
          dataTestId="system-settings-l0-overview-strip"
          systemTrustState="unknown"
          impact="凭证、调度、缓存与危险动作仍需结合运维中心快照确认。"
          recommendedAction="先看系统运维摘要，再进入具体配置域。"
          evidenceRef="System operations / 下方运维中心"
          lastUpdated="配置快照加载后更新"
        />
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {SYSTEM_SETTINGS_OVERVIEW.map(({ label, value, note }) => (
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
        <Suspense fallback={settingsConsoleFallback}>
          <SettingsPage />
        </Suspense>
      </div>
    </TerminalPageShell>
  );
};

export default SystemSettingsPage;
