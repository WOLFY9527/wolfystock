import type React from 'react';
import { translate, type UiLanguage } from '../../i18n/core';
import type { TaskProgressModule } from '../../types/analysis';
import { BentoCard } from './BentoCard';

type TaskProgressCardProps = {
  language: UiLanguage;
  taskLabel: string;
  progress: number;
  modules: TaskProgressModule[];
};

function statusTone(status: TaskProgressModule['status']): string {
  switch (status) {
    case 'completed':
      return 'border-emerald-400/25 bg-emerald-400/12 text-emerald-100';
    case 'failed':
      return 'border-rose-400/25 bg-rose-400/12 text-rose-100';
    case 'running':
      return 'border-sky-300/25 bg-sky-500/12 text-sky-100 shadow-[0_0_0_1px_rgba(125,211,252,0.08)]';
    default:
      return 'border-white/8 bg-white/[0.03] text-white/62';
  }
}

function statusLabel(language: UiLanguage, status: TaskProgressModule['status']): string {
  switch (status) {
    case 'completed':
      return translate(language, 'home.progressCompleted');
    case 'failed':
      return translate(language, 'home.progressFailed');
    case 'running':
      return translate(language, 'home.progressRunning');
    default:
      return translate(language, 'home.progressPending');
  }
}

const TaskProgressCard: React.FC<TaskProgressCardProps> = ({
  language,
  taskLabel,
  progress,
  modules,
}) => {
  const clampedProgress = Math.max(0, Math.min(progress, 100));

  return (
    <BentoCard
      testId="home-bento-task-progress-card"
      eyebrow={translate(language, 'home.progressEyebrow')}
      title={taskLabel}
      subtitle={translate(language, 'home.progressMessage')}
      className="rounded-[36px] border-white/6 bg-[radial-gradient(circle_at_top,rgba(78,166,255,0.18),transparent_42%),rgba(255,255,255,0.03)]"
      contentClassName="gap-1"
      accentGlow
    >
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <p className="text-[11px] uppercase tracking-[0.18em] text-white/42">
            {translate(language, 'home.progressOverall')}
          </p>
          <p className="mt-2 text-5xl font-semibold tracking-[-0.04em] text-white">{clampedProgress}%</p>
        </div>
        <p className="rounded-full border border-white/10 bg-black/20 px-4 py-2 text-sm text-white/68">
          {translate(language, 'home.analysisProgress')}
        </p>
      </div>

      <div className="mt-6 h-3 overflow-hidden rounded-full bg-white/[0.06]" aria-hidden="true">
        <div
          className="h-full rounded-full bg-[linear-gradient(90deg,rgba(125,211,252,0.98),rgba(96,165,250,0.94),rgba(52,211,153,0.96))] transition-[width] duration-700 ease-out"
          style={{ width: `${clampedProgress}%` }}
        />
      </div>

      <div className="mt-6 grid gap-3 md:grid-cols-5">
        {modules.map((module) => (
          <div
            key={module.key}
            className={`rounded-[28px] border p-4 transition-all duration-500 ${statusTone(module.status)}`}
            data-testid={`home-bento-progress-module-${module.key}`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-[10px] uppercase tracking-[0.18em] text-white/42">
                  {translate(language, 'home.progressStage')}
                </p>
                <p className="mt-2 text-base font-semibold text-white">{module.name}</p>
              </div>
              {module.status === 'running' ? (
                <span className="mt-1 inline-flex size-2.5 animate-pulse rounded-full bg-sky-200" aria-hidden="true" />
              ) : null}
            </div>
            <p className="mt-5 text-[11px] font-semibold uppercase tracking-[0.18em] text-current">
              {statusLabel(language, module.status)}
            </p>
          </div>
        ))}
      </div>
    </BentoCard>
  );
};

export default TaskProgressCard;
