import type React from 'react';
import { SupportBanner } from '../common/SupportSurface';

export type BacktestRunFeedback = {
  tone: 'default' | 'warning' | 'success' | 'danger';
  title: string;
  body: string;
  details?: string[];
};

type BacktestRunFeedbackBannerProps = {
  feedback?: BacktestRunFeedback | null;
  className?: string;
};

const BacktestRunFeedbackBanner: React.FC<BacktestRunFeedbackBannerProps> = ({
  feedback,
  className = '',
}) => {
  if (!feedback) return null;

  return (
    <div data-testid="backtest-run-feedback" className={className}>
      <SupportBanner
        tone={feedback.tone}
        role={feedback.tone === 'danger' ? 'alert' : 'status'}
        title={feedback.title}
        body={feedback.body}
      >
        {feedback.details?.length ? (
          <ul className="grid gap-2 text-xs leading-5 text-secondary-text">
            {feedback.details.map((detail) => (
              <li key={detail} className="rounded-[var(--cohere-radius-medium)] border border-white/10 bg-black/10 px-3 py-2">
                {detail}
              </li>
            ))}
          </ul>
        ) : null}
      </SupportBanner>
    </div>
  );
};

export default BacktestRunFeedbackBanner;
