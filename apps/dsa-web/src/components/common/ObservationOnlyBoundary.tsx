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
    title: 'observation-only evidence summary',
    body: 'This page summarizes data, evidence, and model or rule outputs. It is not investment advice and not a buy/sell/hold recommendation. Verify data freshness and suitability independently.',
  },
  zh: {
    title: 'observation-only 证据摘要',
    body: '本页面汇总数据、证据与模型或规则输出，不构成交易建议，不提供买入、卖出、持有指令。请独立核验数据新鲜度与适用性。',
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
