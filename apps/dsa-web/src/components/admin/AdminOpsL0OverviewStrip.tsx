import type React from 'react';
import { TerminalChip } from '../terminal';

export type AdminOpsTrustState = 'healthy' | 'observe' | 'degraded' | 'blocked' | 'review_required' | 'unknown';

type AdminOpsL0OverviewStripProps = {
  systemTrustState: AdminOpsTrustState;
  impact: string;
  recommendedAction: string;
  evidenceRef: string;
  lastUpdated: string;
  language?: 'zh' | 'en';
  dataTestId?: string;
  className?: string;
};

const TRUST_STATE_COPY: Record<'zh' | 'en', Record<AdminOpsTrustState, string>> = {
  zh: {
    healthy: '健康',
    observe: '观察',
    degraded: '降级',
    blocked: '阻断',
    review_required: '需复核',
    unknown: '未汇总',
  },
  en: {
    healthy: 'Healthy',
    observe: 'Observe',
    degraded: 'Degraded',
    blocked: 'Blocked',
    review_required: 'Review required',
    unknown: 'Unknown',
  },
};

const FIELD_COPY: Record<'zh' | 'en', {
  stripLabel: string;
  trustState: string;
  impact: string;
  recommendedAction: string;
  evidenceRef: string;
  lastUpdated: string;
}> = {
  zh: {
    stripLabel: 'L0 总览',
    trustState: '信任状态',
    impact: '影响范围',
    recommendedAction: '建议动作',
    evidenceRef: '证据参考',
    lastUpdated: '最近更新',
  },
  en: {
    stripLabel: 'L0 Overview',
    trustState: 'Trust state',
    impact: 'Impact',
    recommendedAction: 'Recommended action',
    evidenceRef: 'Evidence reference',
    lastUpdated: 'Last updated',
  },
};

function trustStateVariant(state: AdminOpsTrustState): React.ComponentProps<typeof TerminalChip>['variant'] {
  if (state === 'healthy') return 'success';
  if (state === 'observe') return 'info';
  if (state === 'degraded' || state === 'review_required') return 'caution';
  if (state === 'blocked') return 'danger';
  return 'neutral';
}

const FieldBlock: React.FC<{
  label: string;
  value: React.ReactNode;
}> = ({ label, value }) => (
  <div className="min-w-0 rounded-md border border-white/[0.06] bg-black/10 px-3 py-2.5">
    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-white/34">{label}</p>
    <div className="mt-1.5 min-w-0 text-xs leading-5 text-white/78">{value}</div>
  </div>
);

const AdminOpsL0OverviewStrip: React.FC<AdminOpsL0OverviewStripProps> = ({
  systemTrustState,
  impact,
  recommendedAction,
  evidenceRef,
  lastUpdated,
  language = 'zh',
  dataTestId = 'admin-ops-l0-overview-strip',
  className = '',
}) => {
  const copy = FIELD_COPY[language];
  const trustStateLabel = TRUST_STATE_COPY[language][systemTrustState];
  const extraClassName = className ? ` ${className}` : '';

  return (
    <section
      data-testid={dataTestId}
      className={`rounded-xl border border-white/[0.08] bg-white/[0.03] px-3 py-3${extraClassName}`}
      aria-label={copy.stripLabel}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-white/34">{copy.stripLabel}</p>
        <TerminalChip variant="neutral">{language === 'en' ? 'Operator-safe summary' : '运维安全摘要'}</TerminalChip>
      </div>
      <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-5">
        <FieldBlock
          label={copy.trustState}
          value={<TerminalChip variant={trustStateVariant(systemTrustState)} className="max-w-full justify-center font-semibold">{trustStateLabel}</TerminalChip>}
        />
        <FieldBlock label={copy.impact} value={<p className="break-words">{impact}</p>} />
        <FieldBlock label={copy.recommendedAction} value={<p className="break-words">{recommendedAction}</p>} />
        <FieldBlock label={copy.evidenceRef} value={<p className="break-words font-mono text-[11px] text-white/62">{evidenceRef}</p>} />
        <FieldBlock label={copy.lastUpdated} value={<p className="break-words font-mono text-[11px] text-white/62">{lastUpdated}</p>} />
      </div>
    </section>
  );
};

export default AdminOpsL0OverviewStrip;
