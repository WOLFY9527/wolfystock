import type React from 'react';
import {
  TerminalChip,
  TerminalMetric,
  TerminalPageHeading,
  TerminalPageShell,
} from '../components/terminal/TerminalPrimitives';
import SettingsPage from './SettingsPage';

const SYSTEM_SETTINGS_OVERVIEW = [
  {
    label: '当前状态',
    value: '等待配置快照',
    note: '由下方控制台加载系统健康、路由与凭证摘要',
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

const SystemSettingsPage: React.FC = () => {
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
          先确认全局风险、待处理配置和下一步安全动作；深层配置、原始字段和危险系统动作留在下方控制台。
        </p>
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
        <SettingsPage />
      </div>
    </TerminalPageShell>
  );
};

export default SystemSettingsPage;
