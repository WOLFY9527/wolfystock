import type React from 'react';
import SettingsPage from './SettingsPage';

const SystemSettingsPage: React.FC = () => {
  return (
    <div data-testid="system-settings-page" className="flex min-h-0 w-full flex-1 flex-col gap-5 overflow-hidden bg-[#050505] text-white">
      <section className="mx-4 mt-4 rounded-[24px] border border-white/5 bg-white/[0.02] px-4 py-5 backdrop-blur-md md:mx-6 md:px-6 xl:mx-8">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-200/70">系统风险总览</p>
            <h1 className="mt-3 text-2xl font-semibold tracking-normal text-white md:text-3xl">系统设置</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-white/58">
              先确认全局风险、待处理配置和下一步安全动作；深层配置、原始字段和危险系统动作留在下方控制台。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="rounded-full border border-cyan-300/20 bg-cyan-400/8 px-3 py-1 text-xs font-semibold text-cyan-100">管理员只读入口优先</span>
            <span className="rounded-full border border-amber-300/20 bg-amber-400/10 px-3 py-1 text-xs font-semibold text-amber-100">变更需保存确认</span>
          </div>
        </div>
        <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-3">
          {[
            ['当前状态', '等待配置快照', '由下方控制台加载系统健康、路由与凭证摘要'],
            ['需关注', '凭证、调度、缓存、危险动作', '危险动作在二级区域并带确认流程'],
            ['下一步', '先看总览，再进入具体域', '原始配置字段默认通过抽屉处理'],
          ].map(([label, value, note]) => (
            <div key={label} className="min-w-0 rounded-2xl border border-white/5 bg-black/20 px-4 py-3">
              <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/34">{label}</p>
              <p className="mt-2 text-sm font-semibold text-white">{value}</p>
              <p className="mt-1 text-xs leading-5 text-white/42">{note}</p>
            </div>
          ))}
        </div>
      </section>
      <div className="min-h-0 flex-1">
        <SettingsPage />
      </div>
    </div>
  );
};

export default SystemSettingsPage;
