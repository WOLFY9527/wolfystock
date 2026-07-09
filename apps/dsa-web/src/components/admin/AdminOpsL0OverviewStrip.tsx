import type React from 'react';
import { TerminalChip } from '../terminal/TerminalPrimitives';
import { cn } from '../../utils/cn';

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
  operatorSafe: string;
}> = {
  zh: {
    stripLabel: 'L0 总览',
    trustState: '信任状态',
    impact: '影响范围',
    recommendedAction: '建议动作',
    evidenceRef: '证据参考',
    lastUpdated: '最近更新',
    operatorSafe: '运维安全摘要',
  },
  en: {
    stripLabel: 'L0 Overview',
    trustState: 'Trust state',
    impact: 'Impact',
    recommendedAction: 'Recommended action',
    evidenceRef: 'Evidence reference',
    lastUpdated: 'Last updated',
    operatorSafe: 'Operator-safe summary',
  },
};

function trustStateVariant(state: AdminOpsTrustState): React.ComponentProps<typeof TerminalChip>['variant'] {
  if (state === 'healthy') return 'success';
  if (state === 'observe') return 'info';
  if (state === 'degraded' || state === 'review_required') return 'caution';
  if (state === 'blocked') return 'danger';
  return 'neutral';
}

function trustStateIcon(state: AdminOpsTrustState): string {
  if (state === 'healthy') return '●';
  if (state === 'observe' || state === 'unknown') return '○';
  if (state === 'degraded' || state === 'review_required') return '▲';
  if (state === 'blocked') return '■';
  return '○';
}

const AdminOpsL0OverviewStrip: React.FC<AdminOpsL0OverviewStripProps> = ({
  systemTrustState,
  impact,
  recommendedAction,
  evidenceRef,
  lastUpdated,
  language = 'zh',
  dataTestId = 'admin-ops-l0-overview-strip',
  className,
}) => {
  const copy = FIELD_COPY[language];
  const trustStateLabel = TRUST_STATE_COPY[language][systemTrustState];
  const isSevere = systemTrustState === 'blocked' || systemTrustState === 'degraded' || systemTrustState === 'review_required';

  return (
    <section
      data-testid={dataTestId}
      className={cn(
        'rounded-lg border px-3 py-2.5',
        isSevere
          ? 'border-[color:color-mix(in_srgb,var(--wolfy-market-down)_28%,var(--wolfy-border-subtle))] bg-[color:color-mix(in_srgb,var(--wolfy-market-down)_6%,var(--wolfy-surface-console))]'
          : 'border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)]',
        className,
      )}
      aria-label={copy.stripLabel}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[color:var(--wolfy-text-muted)]">
            {copy.stripLabel}
          </p>
          <span className="text-[color:var(--wolfy-text-muted)]" aria-hidden="true">·</span>
          <span className="text-[10px] font-medium text-[color:var(--wolfy-text-muted)]">{copy.trustState}</span>
          <TerminalChip
            variant={trustStateVariant(systemTrustState)}
            className="max-w-full justify-center font-semibold"
          >
            <span aria-hidden="true" className="mr-1">{trustStateIcon(systemTrustState)}</span>
            {trustStateLabel}
          </TerminalChip>
          <TerminalChip variant="neutral">{copy.operatorSafe}</TerminalChip>
        </div>
        <p className="min-w-0 font-mono text-[11px] text-[color:var(--wolfy-text-muted)]">
          <span className="mr-1.5 font-sans text-[10px] uppercase tracking-[0.12em]">{copy.lastUpdated}</span>
          {lastUpdated}
        </p>
      </div>

      <div className="mt-2 grid min-w-0 gap-1.5 text-xs leading-5 md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <p className="min-w-0 text-[color:var(--wolfy-text-secondary)]">
          <span className="mr-1.5 font-medium text-[color:var(--wolfy-text-muted)]">{copy.impact}</span>
          <span className="break-words text-[color:var(--wolfy-text-primary)]">{impact}</span>
        </p>
        <p className="min-w-0 text-[color:var(--wolfy-text-secondary)]">
          <span className="mr-1.5 font-medium text-[color:var(--wolfy-text-muted)]">{copy.recommendedAction}</span>
          <span className="break-words text-[color:var(--wolfy-text-primary)]">{recommendedAction}</span>
        </p>
      </div>

      <p className="mt-1.5 min-w-0 font-mono text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">
        <span className="mr-1.5 font-sans text-[10px] uppercase tracking-[0.12em]">{copy.evidenceRef}</span>
        <span className="break-words">{evidenceRef}</span>
      </p>
    </section>
  );
};

export default AdminOpsL0OverviewStrip;
