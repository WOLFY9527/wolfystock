import type React from 'react';
import type {
  MarketActionabilityFrame,
  MarketIntelligenceEvidenceDomainFrame,
  MarketIntelligenceEvidenceFrame,
} from '../../api/market';
import { TerminalChip } from '../terminal/TerminalPrimitives';
import { cn } from '../../utils/cn';

type MarketIntelligenceActionabilityStripProps = {
  actionability: MarketActionabilityFrame;
  evidence: MarketIntelligenceEvidenceFrame;
  title?: string;
  testId?: string;
  className?: string;
};

type DomainTone = React.ComponentProps<typeof TerminalChip>['variant'];

type DomainSummary = {
  key: string;
  label: string;
  stateLabel: string;
  variant: DomainTone;
};

const DOMAIN_LABELS: Record<string, string> = {
  macro: '宏观',
  liquidity: '流动性',
  rotation: '轮动',
  breadth: '宽度',
  scanner_context: '扫描上下文',
};

const MISSING_EVIDENCE_LABELS: Record<string, string> = {
  macro: '宏观证据',
  liquidity: '流动性证据',
  technical: '技术确认',
  rotation: '轮动证据',
  breadth: '宽度证据',
  scanner_context: '扫描上下文证据',
  freshness: '新鲜度证据',
};

const BLOCKING_REASON_LABELS: Record<string, string> = {
  missing_required_evidence: '关键证据待补',
  observation_only: '当前仅能观察',
  stale_evidence: '新鲜度不足',
  fallback_evidence: '回退证据未解除',
  freshness_missing: '新鲜度待确认',
  source_authority_not_score_grade: '高授权证据不足',
  consumer_action_blocked: '当前不支持更强结论',
};

function verdictVariant(verdict: string): DomainTone {
  if (verdict === 'ready') return 'success';
  if (verdict === 'observe_only') return 'info';
  if (verdict === 'blocked') return 'danger';
  if (verdict === 'waiting') return 'neutral';
  return 'caution';
}

function verdictLabel(verdict: string): string {
  if (verdict === 'ready') return '研究可参考';
  if (verdict === 'observe_only') return '仅观察';
  if (verdict === 'blocked') return '暂时阻断';
  if (verdict === 'waiting') return '等待更新';
  return '证据不足';
}

function confidenceLabel(label: string): string {
  if (label === 'high') return '高把握';
  if (label === 'medium') return '中等把握';
  if (label === 'low') return '低把握';
  return '把握不足';
}

function freshnessLabel(freshness: string): string {
  if (freshness === 'live') return '实时';
  if (freshness === 'fresh') return '较新';
  if (freshness === 'delayed') return '延迟';
  if (freshness === 'cached') return '缓存';
  if (freshness === 'stale') return '陈旧';
  if (freshness === 'fallback') return '回退';
  if (freshness === 'unknown') return '待确认';
  return '待确认';
}

function sourceAuthorityLabel(authority: string): string {
  if (authority === 'scoreGradeAllowed') return '高授权';
  if (authority === 'observationOnly') return '观察级';
  return '证据不足';
}

function domainStateLabel(state: string): string {
  if (state === 'score_grade') return '可参考';
  if (state === 'observation_only') return '仅观察';
  if (state === 'degraded') return '已降级';
  if (state === 'waiting') return '等待更新';
  if (state === 'blocked') return '已阻断';
  return '待补';
}

function domainStateVariant(state: string): DomainTone {
  if (state === 'score_grade') return 'success';
  if (state === 'observation_only') return 'info';
  if (state === 'degraded') return 'caution';
  if (state === 'blocked') return 'danger';
  return 'neutral';
}

function summarizeDomain(key: string, frame: MarketIntelligenceEvidenceDomainFrame): DomainSummary {
  return {
    key,
    label: DOMAIN_LABELS[key] || '证据',
    stateLabel: domainStateLabel(frame.state),
    variant: domainStateVariant(frame.state),
  };
}

function unique(items: Array<string | null | undefined>): string[] {
  const seen = new Set<string>();
  const values: string[] = [];
  items.forEach((item) => {
    const value = String(item || '').trim();
    if (!value || seen.has(value)) return;
    seen.add(value);
    values.push(value);
  });
  return values;
}

function renderMissingEvidence(items: string[]): string {
  const labels = unique(items.map((item) => MISSING_EVIDENCE_LABELS[item] || '待补证据'));
  return labels.length ? labels.join(' / ') : '暂无';
}

function renderBlockingReasons(items: string[]): string {
  const labels = unique(items.map((item) => BLOCKING_REASON_LABELS[item] || '当前仅能观察'));
  return labels.length ? labels.join(' / ') : '暂无';
}

const MarketIntelligenceActionabilityStrip: React.FC<MarketIntelligenceActionabilityStripProps> = ({
  actionability,
  evidence,
  title = '市场研判可用性',
  testId,
  className,
}) => {
  const domains = [
    summarizeDomain('macro', evidence.regimeEvidence),
    summarizeDomain('liquidity', evidence.liquidityEvidence),
    summarizeDomain('rotation', evidence.rotationEvidence),
    summarizeDomain('breadth', evidence.breadthEvidence),
    summarizeDomain('scanner_context', evidence.scannerContextEvidence),
  ];
  const evidenceMissingCount = evidence.missingEvidence.length;

  const summaryLine = actionability.nextResearchStep || (actionability.verdict === 'ready'
    ? '继续围绕当前主线补充研究证据。'
    : '等待关键证据补齐后再更新判断。');

  return (
    <section
      data-testid={testId}
      className={cn(
        'mx-4 shrink-0 rounded-lg border border-white/[0.08] bg-white/[0.025] px-3 py-3 md:mx-6',
        className,
      )}
    >
      <div className="flex min-w-0 flex-col gap-3">
        <div className="flex min-w-0 flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-white/42">
                {title}
              </span>
              <TerminalChip variant={verdictVariant(actionability.verdict)}>
                {verdictLabel(actionability.verdict)}
              </TerminalChip>
              <TerminalChip variant="neutral">
                {confidenceLabel(actionability.confidence.label)}
              </TerminalChip>
              <TerminalChip variant="neutral">
                仅供研究观察，不作为执行依据
              </TerminalChip>
            </div>
            <p className="mt-2 text-sm leading-6 text-white/78">
              {summaryLine}
            </p>
          </div>
          <div className="flex min-w-0 flex-wrap gap-2">
            <TerminalChip variant="neutral">
              证据覆盖 {actionability.evidenceCoverage.scoreGradeCount}/{actionability.evidenceCoverage.observationOnlyCount}/{actionability.evidenceCoverage.missingCount}
            </TerminalChip>
            <TerminalChip variant="neutral">
              证据覆盖 {evidence.evidenceCoverage.totalCount > 0
                ? `${evidence.evidenceCoverage.scoreGradeCount}/${evidence.evidenceCoverage.totalCount}`
                : '0/0'}
            </TerminalChip>
            <TerminalChip variant="neutral">
              {sourceAuthorityLabel(actionability.sourceAuthority)}
            </TerminalChip>
            <TerminalChip variant="neutral">
              {freshnessLabel(actionability.freshness)}
            </TerminalChip>
          </div>
        </div>

        <div className="flex min-w-0 flex-wrap gap-2" aria-label="Market intelligence evidence domains">
          {domains.map((domain) => (
            <TerminalChip key={domain.key} variant={domain.variant}>
              {domain.label} {domain.stateLabel}
            </TerminalChip>
          ))}
        </div>

        <details className="rounded-[10px] border border-white/[0.06] bg-white/[0.015] px-3 py-2.5">
          <summary className="cursor-pointer list-none text-[11px] font-medium text-white/52 marker:hidden">
            更多证据细节
          </summary>
          <div className="mt-2 grid gap-2 text-[11px] leading-5 text-white/62 md:grid-cols-2">
            <p>缺口 {evidenceMissingCount}</p>
            <p>新鲜度 {freshnessLabel(evidence.freshness)}</p>
            <p>来源级别 {sourceAuthorityLabel(evidence.sourceAuthority)}</p>
            <p>下一步 {evidence.nextEvidenceNeeded[0] || actionability.nextResearchStep || '继续观察证据更新'}</p>
            <p className="md:col-span-2">待补证据 {renderMissingEvidence(evidence.missingEvidence)}</p>
            <p className="md:col-span-2">限制因素 {renderBlockingReasons(evidence.blockingReasons)}</p>
          </div>
        </details>
      </div>
    </section>
  );
};

export default MarketIntelligenceActionabilityStrip;
