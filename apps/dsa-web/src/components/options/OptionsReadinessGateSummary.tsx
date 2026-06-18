import type React from 'react';
import { ConsoleDisclosure } from '../linear/LinearPrimitives';
import { TerminalChip } from '../terminal/TerminalPrimitives';
import { cn } from '../../utils/cn';
import type { OptionsResearchReadiness } from '../../types/researchReadiness';

type OptionsReadinessGateSummaryProps = {
  readiness?: OptionsResearchReadiness | null;
  testId?: string;
  className?: string;
};

const FAIL_CLOSED_READINESS: OptionsResearchReadiness = {
  optionsResearchReady: false,
  readinessState: 'blocked',
  dataQualityTier: 'insufficient',
  decisionGrade: false,
  providerAuthority: 'unavailable',
  liquidityGate: 'blocked',
  ivGreeksGate: 'blocked',
  spreadGate: 'blocked',
  scenarioCoverage: 'missing_chain_data',
  noTradingBoundary: {
    analyticalOnly: true,
    noBrokerExecution: true,
    noOrderPlacement: true,
    noPortfolioMutation: true,
    noTradingRecommendation: true,
  },
  blockingReasons: ['missing_options_readiness'],
  nextEvidenceNeeded: ['补齐期权链、IV / Greeks 与流动性证据'],
};

const IV_GREEKS_LABEL = 'IV / 希腊值';

type GateVariant = React.ComponentProps<typeof TerminalChip>['variant'];

type GateItem = {
  key: string;
  label: string;
  value: string;
  variant: GateVariant;
};

function normalizeReadiness(readiness?: OptionsResearchReadiness | null): OptionsResearchReadiness {
  if (!readiness?.readinessState) return FAIL_CLOSED_READINESS;
  return {
    ...FAIL_CLOSED_READINESS,
    ...readiness,
    noTradingBoundary: readiness.noTradingBoundary ?? FAIL_CLOSED_READINESS.noTradingBoundary,
    blockingReasons: Array.isArray(readiness.blockingReasons) ? readiness.blockingReasons : FAIL_CLOSED_READINESS.blockingReasons,
    nextEvidenceNeeded: Array.isArray(readiness.nextEvidenceNeeded) ? readiness.nextEvidenceNeeded : FAIL_CLOSED_READINESS.nextEvidenceNeeded,
  };
}

function gateVariant(status: string): GateVariant {
  if (status === '已通过' || status === '可用') return 'success';
  if (status === '人工复核' || status === '仅观察' || status === '演示/延迟' || status === '延迟可观察') return 'caution';
  if (status === '已阻断' || status === '证据不足' || status === '待补证' || status === '未通过') return 'danger';
  return 'neutral';
}

function humanizeDataQualityTier(value?: string | null): string {
  if (value === 'live_usable') return '实时可用';
  if (value === 'delayed_usable') return '延迟可观察';
  if (value === 'synthetic_demo_only') return '演示/延迟';
  return '证据不足';
}

function humanizeProviderAuthority(value?: string | null): string {
  if (value === 'scoreGradeAllowed') return '授权链路';
  if (value === 'observationOnly') return '观察级';
  return '待补证';
}

function humanizeGateStatus(value?: string | null): string {
  if (value === 'clear') return '已通过';
  if (value === 'manual_review') return '人工复核';
  if (value === 'observe_only') return '仅观察';
  return '已阻断';
}

function humanizeScenarioCoverage(value?: string | null): string {
  if (value === 'single_contract') return '单合约';
  if (value === 'strategy_compare_ready') return '策略对比';
  return '缺少链路';
}

function executionBoundaryLabel(boundary?: OptionsResearchReadiness['noTradingBoundary'] | null): string {
  if (
    boundary?.analyticalOnly !== false
    && boundary?.noBrokerExecution !== false
    && boundary?.noOrderPlacement !== false
    && boundary?.noPortfolioMutation !== false
    && boundary?.noTradingRecommendation !== false
  ) {
    return '只读无执行';
  }
  return '按只读处理';
}

function uniqueStrings(values: Array<string | null | undefined>): string[] {
  return [...new Set(values.filter((value): value is string => Boolean(value && value.trim())))];
}

function reasonCategory(value: string): 'authority' | 'iv' | 'liquidity' | 'chain' | 'demo' | null {
  if (value.includes('provider') || value.includes('authority')) return 'authority';
  if (value.includes('missing_iv') || value.includes('missing_greeks') || value.includes('greeks')) return 'iv';
  if (value.includes('volume') || value.includes('open_interest') || value.includes('spread') || value.includes('liquidity')) return 'liquidity';
  if (value.includes('chain') || value.includes('contract') || value.includes('bid_ask')) return 'chain';
  if (value.includes('fixture') || value.includes('synthetic') || value.includes('demo')) return 'demo';
  return null;
}

function summaryLine(readiness: OptionsResearchReadiness, rawReadiness?: OptionsResearchReadiness | null): string {
  if (!rawReadiness?.readinessState) return '当前缺少就绪度回执，先按证据不足处理。';
  if (readiness.optionsResearchReady && readiness.dataQualityTier === 'delayed_usable') {
    return '延迟链路可用于观察，结论仍保持只读边界。';
  }
  if (readiness.optionsResearchReady) {
    return '当前门控已通过，但仍仅用于研究观察与人工复核。';
  }
  const categories = new Set(
    uniqueStrings(readiness.blockingReasons ?? []).map(reasonCategory).filter((value): value is NonNullable<ReturnType<typeof reasonCategory>> => value !== null),
  );
  const parts: string[] = [];
  if (categories.has('authority') || readiness.providerAuthority !== 'scoreGradeAllowed') parts.push('授权');
  if (categories.has('iv') || readiness.ivGreeksGate !== 'clear') parts.push(IV_GREEKS_LABEL);
  if (
    categories.has('liquidity')
    || categories.has('chain')
    || readiness.liquidityGate !== 'clear'
    || readiness.spreadGate !== 'clear'
  ) parts.push('流动性');
  if (!parts.length && readiness.dataQualityTier !== 'live_usable') parts.push('数据完整性');
  if (parts.length === 3) {
    return `当前仍受${parts[0]}、${parts[1]}与${parts[2]}证据限制。`;
  }
  if (parts.length === 2) {
    return `当前仍受${parts[0]}与${parts[1]}证据限制。`;
  }
  return `当前仍受${parts[0]}证据限制。`;
}

function humanizeNextEvidence(values: string[]): string {
  if (!values.length) return '下一步：继续保留只读观察边界。';
  if (values.some((value) => value.includes('期权链、IV / Greeks 与流动性证据'))) {
    return `下一步：补齐期权链、${IV_GREEKS_LABEL}与流动性证据。`;
  }
  if (values.some((value) => value.includes('更高新鲜度'))) return '下一步：等待更高新鲜度链路。';
  const needsAuthority = values.some((value) => value.includes('provider authority') || value.includes('live chain'));
  const needsIv = values.some((value) => value.includes('Greeks') || value.includes('IV'));
  const needsLiquidity = values.some((value) => value.includes('OI/成交量') || value.includes('价差') || value.includes('流动性'));
  const items = uniqueStrings([
    needsAuthority ? '授权链路' : null,
    needsIv ? IV_GREEKS_LABEL : null,
    needsLiquidity ? 'OI / 成交量与更紧价差' : null,
  ]);
  if (!items.length) return `下一步：${values[0].replace(/[。.]$/, '')}。`;
  return `下一步：补齐${items.join('、')}证据。`;
}

function disclosureReason(value: string): string {
  if (value.includes('provider') || value.includes('authority')) return '授权链路仍待验证';
  if (value.includes('missing_iv') || value.includes('missing_greeks') || value.includes('greeks')) return `${IV_GREEKS_LABEL}仍不完整`;
  if (value.includes('volume') || value.includes('open_interest')) return 'OI / 成交量证据不足';
  if (value.includes('spread')) return '买卖价差仍偏宽';
  if (value.includes('chain') || value.includes('contract') || value.includes('bid_ask')) return '期权链路仍不完整';
  if (value.includes('fixture') || value.includes('synthetic') || value.includes('demo')) return '当前仍是演示或延迟证据';
  return '仍需补充更多证据';
}

function buildGateItems(readiness: OptionsResearchReadiness): GateItem[] {
  const dataQuality = humanizeDataQualityTier(readiness.dataQualityTier);
  const authority = humanizeProviderAuthority(readiness.providerAuthority);
  const liquidity = humanizeGateStatus(readiness.liquidityGate);
  const ivGreeks = humanizeGateStatus(readiness.ivGreeksGate);
  const spread = humanizeGateStatus(readiness.spreadGate);
  const scenarioCoverage = humanizeScenarioCoverage(readiness.scenarioCoverage);
  const decisionGrade = readiness.decisionGrade === true ? '可用' : '未通过';
  const boundary = executionBoundaryLabel(readiness.noTradingBoundary);

  return [
    { key: 'data-quality', label: '数据层级', value: dataQuality, variant: gateVariant(dataQuality) },
    { key: 'provider-authority', label: '授权级别', value: authority, variant: gateVariant(authority) },
    { key: 'liquidity', label: '流动性', value: liquidity, variant: gateVariant(liquidity) },
    { key: 'iv-greeks', label: IV_GREEKS_LABEL, value: ivGreeks, variant: gateVariant(ivGreeks) },
    { key: 'spread', label: '价差', value: spread, variant: gateVariant(spread) },
    { key: 'scenario-coverage', label: '情景覆盖', value: scenarioCoverage, variant: gateVariant(scenarioCoverage) },
    { key: 'decision-grade', label: '判断等级', value: decisionGrade, variant: gateVariant(decisionGrade) },
    { key: 'boundary', label: '执行边界', value: boundary, variant: 'neutral' },
  ];
}

function compactGateItems(gateItems: GateItem[]): GateItem[] {
  const compactKeys = new Set(['data-quality', 'decision-grade', 'boundary']);
  return gateItems.filter((item) => compactKeys.has(item.key));
}

function detailGateItems(gateItems: GateItem[]): GateItem[] {
  const compactKeys = new Set(['data-quality', 'decision-grade', 'boundary']);
  return gateItems.filter((item) => !compactKeys.has(item.key));
}

const OptionsReadinessGateSummary: React.FC<OptionsReadinessGateSummaryProps> = ({
  readiness: rawReadiness,
  testId,
  className,
}) => {
  const readiness = normalizeReadiness(rawReadiness);
  const gateItems = buildGateItems(readiness);
  const primaryGateItems = compactGateItems(gateItems);
  const secondaryGateItems = detailGateItems(gateItems);
  const summary = summaryLine(readiness, rawReadiness);
  const nextEvidence = humanizeNextEvidence(uniqueStrings(readiness.nextEvidenceNeeded ?? []));
  const disclosureItems = uniqueStrings(readiness.blockingReasons ?? []).map(disclosureReason);
  const disclosureSummary = secondaryGateItems.map((item) => `${item.label}：${item.value}`).join(' · ');

  return (
    <section
      data-testid={testId}
      className={cn(
        'rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[color:color-mix(in_srgb,var(--wolfy-surface-console)_88%,transparent)] px-3 py-3',
        className,
      )}
    >
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[color:var(--wolfy-text-muted)]">
          门控摘要
        </span>
        {primaryGateItems.map((item) => (
          <TerminalChip key={item.key} variant={item.variant}>
            {item.label}：{item.value}
          </TerminalChip>
        ))}
      </div>
      <p className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">{summary}</p>
      <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{nextEvidence}</p>
      {secondaryGateItems.length || disclosureItems.length ? (
        <ConsoleDisclosure
          title="完整门控与补证"
          summary={disclosureSummary || disclosureItems.slice(0, 2).join(' · ')}
          className="mt-3"
        >
          {secondaryGateItems.length ? (
            <div className="flex flex-wrap gap-2">
              {secondaryGateItems.map((item) => (
                <TerminalChip key={item.key} variant={item.variant}>
                  {item.label}：{item.value}
                </TerminalChip>
              ))}
            </div>
          ) : null}
          {disclosureItems.length ? (
            <p className="text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">
              当前限制：{disclosureItems.join(' · ')}
            </p>
          ) : null}
          <p className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
            {nextEvidence}
          </p>
        </ConsoleDisclosure>
      ) : null}
    </section>
  );
};

export default OptionsReadinessGateSummary;
