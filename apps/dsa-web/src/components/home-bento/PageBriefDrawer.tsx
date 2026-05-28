import type React from 'react';
import { Drawer } from '../common/Drawer';
import { getToneTextClass, getToneTextStyle, type SignalTone } from './theme';

export type PageBriefMetric = {
  label: string;
  value: React.ReactNode;
  tone?: SignalTone;
};

type PageBriefDrawerProps = {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  summary: React.ReactNode;
  bullets: React.ReactNode[];
  metrics?: PageBriefMetric[];
  footnote?: React.ReactNode;
  testId?: string;
  width?: string;
};

export const PageBriefDrawer: React.FC<PageBriefDrawerProps> = ({
  isOpen,
  onClose,
  title,
  summary,
  bullets,
  metrics,
  footnote,
  testId,
  width = 'max-w-[min(92vw,38rem)]',
}) => (
  <Drawer
    isOpen={isOpen}
    onClose={onClose}
    title={title}
    width={width}
  >
    <div
      data-testid={testId}
      className="space-y-5 rounded-[36px] border border-white/[0.08] bg-[#050505]/96 p-6 text-white backdrop-blur-xl"
    >
      <p className="text-sm leading-6 text-white/68">{summary}</p>

      {metrics?.length ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {metrics.map((metric) => {
            const tone = metric.tone || 'neutral';
            return (
              <div
                key={`${metric.label}-${String(metric.value)}`}
                className="rounded-[28px] border border-white/[0.08] bg-white/[0.02] px-5 py-4 backdrop-blur-xl"
              >
                <p className="text-[11px] uppercase tracking-[0.16em] text-white/40">{metric.label}</p>
                <p
                  className={`mt-2 text-base font-semibold ${getToneTextClass(tone)}`}
                  style={getToneTextStyle(tone, tone !== 'neutral')}
                >
                  {metric.value}
                </p>
              </div>
            );
          })}
        </div>
      ) : null}

      <div className="space-y-3">
        {bullets.map((bullet, index) => (
          <div
            key={index}
            className="rounded-[28px] border border-white/[0.08] bg-white/[0.02] px-5 py-4 text-sm leading-6 text-white/64 backdrop-blur-xl"
          >
            {bullet}
          </div>
        ))}
      </div>

      {footnote ? (
        <p className="text-[11px] uppercase tracking-[0.16em] text-white/36">{footnote}</p>
      ) : null}
    </div>
  </Drawer>
);
