import type React from 'react';
import { SupportBanner } from './SupportSurface';
import { cn } from '../../utils/cn';

type ObservationOnlyBoundaryProps = {
  language: 'zh' | 'en';
  surface: string;
  className?: string;
  testId?: string;
};

const COPY = {
  en: {
    title: 'Research boundary summary',
    body: 'This page summarizes research context, visible evidence, and bounded model or rule outputs. Conclusions remain limited by current freshness and coverage, so verify suitability independently.',
  },
  zh: {
    title: '研究边界摘要',
    body: '本页面汇总研究语境、可见证据与受边界约束的模型或规则输出。结论仍受当前时效与覆盖限制，请独立核验适用性。',
  },
} as const;

const ObservationOnlyBoundary: React.FC<ObservationOnlyBoundaryProps> = ({
  language,
  surface,
  className,
  testId = 'observation-only-boundary',
}) => {
  const copy = COPY[language];

  return (
    <SupportBanner
      data-observation-boundary-surface={surface}
      data-testid={testId}
      role="note"
      title={copy.title}
      body={copy.body}
      className={cn('py-3', className)}
      titleClassName="text-[0.82rem] font-semibold uppercase tracking-[0.08em]"
      bodyClassName="text-xs leading-5"
    />
  );
};

export default ObservationOnlyBoundary;
