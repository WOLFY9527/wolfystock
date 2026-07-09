import type React from 'react';
import { Drawer } from '../common/Drawer';
import { cn } from '../../utils/cn';
import { getToneTextClass, getToneTextStyle, type SignalTone } from './theme';

export type DeepReportMetric = {
  label: string;
  value: React.ReactNode;
  details?: React.ReactNode;
  tone?: SignalTone;
  glow?: boolean;
};

export type DeepReportModule = {
  id: string;
  eyebrow: string;
  title: string;
  summary?: React.ReactNode;
  metrics: DeepReportMetric[];
  footnote?: React.ReactNode;
};

type DeepReportDrawerProps = {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  modules: DeepReportModule[];
  testId?: string;
};

export const DeepReportDrawer: React.FC<DeepReportDrawerProps> = ({
  isOpen,
  onClose,
  title,
  modules,
  testId = 'home-bento-drawer',
}) => (
  <Drawer
    isOpen={isOpen}
    onClose={onClose}
    title={title}
    width="max-w-[min(96vw,72rem)]"
  >
    <div
      data-testid={testId}
      className="space-y-6 rounded-l-[40px] rounded-r-[24px] border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] p-6 text-[color:var(--wolfy-text-primary)] backdrop-blur-3xl sm:p-8"
    >
      <div className="grid gap-4">
        {modules.map((module) => (
          <section
            key={module.id}
            data-testid={`${testId}-${module.id}`}
            className="rounded-[32px] border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-inset)] p-6 backdrop-blur-3xl"
          >
            <p className="text-[10px] font-semibold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{module.eyebrow}</p>
            <h3 className="mt-3 text-2xl font-semibold tracking-[-0.03em] text-[color:var(--wolfy-text-primary)]">{module.title}</h3>
            {module.summary ? (
              <p className="mt-4 text-sm leading-relaxed text-[color:var(--wolfy-text-secondary)]">{module.summary}</p>
            ) : null}

            <div className="mt-7 space-y-5">
              {module.metrics.map((metric) => {
                const tone = metric.tone || 'neutral';
                return (
                  <div
                    key={`${module.id}-${metric.label}`}
                    className="border-t border-[color:var(--wolfy-divider)] pt-5 first:border-t-0 first:pt-0"
                  >
                    <p className="text-[10px] font-semibold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{metric.label}</p>
                    <p
                      className={cn('mt-3 text-xl font-medium leading-relaxed', getToneTextClass(tone))}
                      style={getToneTextStyle(tone, metric.glow === true)}
                    >
                      {metric.value}
                    </p>
                    {metric.details ? (
                      <p className="mt-2 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
                        {metric.details}
                      </p>
                    ) : null}
                  </div>
                );
              })}
            </div>

            {module.footnote ? (
              <p className="mt-6 text-[11px] uppercase tracking-[0.16em] text-[color:var(--wolfy-text-muted)]">{module.footnote}</p>
            ) : null}
          </section>
        ))}
      </div>
    </div>
  </Drawer>
);
