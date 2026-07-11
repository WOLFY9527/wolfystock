import type React from 'react';
import { Suspense, lazy } from 'react';
import type { MarketOverviewTab } from '../../pages/MarketOverviewTabConfig';
import {
  ConsoleBoard,
  KeyLevelStrip,
} from '../linear/LinearPrimitives';
import { TerminalChip, TerminalDisclosure } from '../terminal/TerminalPrimitives';
import { cn } from '../../utils/cn';
import { MarketOverviewSparkline } from './marketOverviewPrimitives';
import type { MarketRegimeSynthesisHeaderView } from './MarketRegimeSynthesisHeader';
import { SynthesisEvidenceColumn } from '../common/SynthesisEvidenceColumn';
import type { OfficialMacroAuthorityRecord } from '../common/officialMacroAuthorityDiagnosticsData';
import type {
  MarketOverviewBriefingSummaryView,
  MarketOverviewDataStateStripView,
  MarketOverviewDecisionSemanticsLineView,
  MarketOverviewDecisionSemanticsView,
  MarketOverviewTemperatureSummaryView,
} from './marketOverviewDecisionTypes';
import { buildDataSourcesSetupHref, buildProviderOpsSetupHref } from '../../utils/productSetupSurface';
import { parseLocaleFromPathname } from '../../utils/localeRouting';
import {
  MARKET_DECISION_NOT_READY_NOTICE,
  decisionReadinessStateLabel,
  decisionReadinessVariant,
  joinMarketReasonLabels,
  marketIntelligenceReasonLabel,
  type DecisionReadinessState,
  type DecisionReadinessSummary,
  type MarketDirectionalSummary,
} from '../../utils/marketIntelligenceGuidance';
import {
  NextResearchAction,
  ObservationHead,
  ResearchDataQualityComposition,
  ResearchRiskLimits,
  type ResearchQualityFacet,
} from '../research/anatomy';
import { buildMarketOverviewResearchHandoffSteps } from './marketOverviewResearchHandoff';

export type {
  MarketOverviewBriefingSummaryView,
  MarketOverviewDataStateStripView,
  MarketOverviewDecisionSemanticsBoundaryView,
  MarketOverviewDecisionSemanticsLineView,
  MarketOverviewDecisionSemanticsView,
  MarketOverviewDirectionReadinessPillarView,
  MarketOverviewDirectionReadinessView,
  MarketOverviewTemperatureSummaryView,
} from './marketOverviewDecisionTypes';

const MARKET_OVERVIEW_DEBUG_DETAILS_FALLBACK_MIN_MS = 120;

const LazyMarketOverviewDecisionDebugDetails = lazy(async () => {
  const [module] = await Promise.all([
    import('./MarketOverviewDecisionDebugDetails'),
    new Promise((resolve) => setTimeout(resolve, MARKET_OVERVIEW_DEBUG_DETAILS_FALLBACK_MIN_MS)),
  ]);
  return { default: module.MarketOverviewDecisionDebugDetails };
});

export type MarketOverviewDecisionChipView = {
  label: string;
  value: string;
  variant: 'neutral' | 'success' | 'caution' | 'danger' | 'info';
};

export type MarketOverviewHeroAnchorView = {
  key: string;
  primaryLabel: string;
  secondaryLabel?: string;
  valueText: string;
  changeText: string;
  changeToneClass: string;
};

export type MarketOverviewVisualEvidencePointView = {
  key: string;
  label: string;
  valueText: string;
  changeText: string;
  toneClass: string;
  sparkline: number[];
};

export type MarketOverviewVisualEvidenceCardView = {
  id: string;
  eyebrow: string;
  title: string;
  summary: string;
  unavailableCopy?: string;
  points: MarketOverviewVisualEvidencePointView[];
};

export type MarketOverviewCategoryTabView = {
  key: MarketOverviewTab;
  label: string;
};

export type MarketOverviewRegimeSummaryView = {
  title: string;
  label: string;
  confidenceLabel: string;
  confidenceValueText: string;
  explanation: string;
  drivers: MarketOverviewDecisionSemanticsLineView[];
  blockers: MarketOverviewDecisionSemanticsLineView[];
  contradictions: MarketOverviewDecisionSemanticsLineView[];
  nextWatchItems: MarketOverviewDecisionSemanticsLineView[];
};

type MarketOverviewWorkbenchTopSurfaceProps = {
  heading: React.ReactNode;
  directionalSummary: MarketDirectionalSummary;
  regimeSynthesis?: MarketRegimeSynthesisHeaderView;
  regimeSummary?: MarketOverviewRegimeSummaryView;
  decisionText: string;
  decisionChips: MarketOverviewDecisionChipView[];
  decisionReliable: boolean;
  decisionSemantics?: MarketOverviewDecisionSemanticsView;
  dataState: MarketOverviewDataStateStripView;
  temperatureSummary: MarketOverviewTemperatureSummaryView;
  briefingSummary: MarketOverviewBriefingSummaryView;
  officialMacroRecords: OfficialMacroAuthorityRecord[];
  categoryTabs: MarketOverviewCategoryTabView[];
  activeCategory: MarketOverviewTab;
  onCategoryChange: (tab: MarketOverviewTab) => void;
  exportLabel: string;
  exportDisabled: boolean;
  onExportSummary: () => void;
  heroAnchors: MarketOverviewHeroAnchorView[];
  showAdminDiagnostics?: boolean;
};

type DirectionUsabilitySummary = {
  label: string;
  variant: 'success' | 'info' | 'caution';
  headline: string;
  detail: string;
};

type ConsumerConfidenceSummaryView = {
  value: string;
  detail: string;
  chipLabel: string;
};

type MarketNarrativeVerdictView = {
  label: '偏强观察' | '中性观察' | '偏弱观察' | '证据待补';
  variant: 'success' | 'info' | 'caution' | 'danger' | 'neutral';
  headline: string;
  detail: string;
};

type MarketNarrativeDriverView = {
  key: string;
  label: string;
  status: string;
  detail: string;
  variant: 'success' | 'info' | 'caution' | 'neutral';
};

const MARKET_OVERVIEW_SETUP_ACTION_CLASS = 'inline-flex min-h-8 items-center rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-input)] px-2.5 py-1 text-[11px] font-semibold text-[color:var(--wolfy-text-secondary)] transition-colors hover:border-[color:var(--wolfy-divider)] hover:bg-[color:var(--wolfy-surface-inset-lift)] hover:text-[color:var(--wolfy-text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--wolfy-accent-focus)]';

function marketOverviewConsumerCopy(text: string): string {
  return text
    .replace(/ETF flow proxy/gi, 'ETF 资金流指标')
    .replace(/Institutional pressure proxy/gi, '机构压力指标')
    .replace(/Industry breadth proxy/gi, '行业广度指标')
    .replace(/\bproxy\b/gi, '部分数据')
    .replace(/存在备用或代理证据负担/g, '当前为延迟可用或部分可用状态')
    .replace(/备用或代理证据/g, '延迟可用或部分可用状态')
    .replace(/代理证据/g, '观察线索')
    .replace(/来源覆盖/g, '证据覆盖')
    .replace(/评分级来源覆盖/g, '充分来源覆盖')
    .replace(/评分级支持证据/g, '充分支持信号')
    .replace(/评分级/g, '充分')
    .replace(/更高授权/g, '更多可靠')
    .replace(/高授权/g, '可靠')
    .replace(/缺口/g, '待补项')
    .replace(/回退/g, '最近一次可用')
    .replace(/缓存/g, '最近一次可用')
    .replace(/仅供界面演示/g, '仅作临时状态展示')
    .replace(/保持界面结构/g, '保持页面可读')
    .replace(/等待真实行情源/g, '等待更多市场数据');
}

function marketNarrativeCopy(text: string, fallback = '等待更多市场数据'): string {
  const normalized = marketOverviewConsumerCopy(String(text || '').trim() || fallback)
    .replace(/方向仅供观察/g, '方向线索待确认')
    .replace(/偏多观察/g, '偏强观察')
    .replace(/Official macro\/rates\/volatility/gi, '宏观 / 利率 / 波动率')
    .replace(/Rotation\/risk participation/gi, '轮动 / 风险参与')
    .replace(/Liquidity\/conditions/gi, '流动性条件')
    .replace(/Breadth health/gi, '宽度健康度')
    .replace(/Liquidity beta watch/gi, '流动性改善线索')
    .replace(/Rotation leadership watch/gi, '轮动主线延续')
    .replace(/Risk-on regime/gi, '风险偏好状态')
    .replace(/expanding liquidity/gi, '流动性扩张')
    .replace(/Primary regime remains observation-only/gi, '主线仍需确认')
    .replace(/Liquidity impulse should remain expanding/gi, '继续观察流动性是否保持扩张')
    .replace(/Remove the risk-on watch if liquidity turns (?:partial|mixed) or contracting\.?/gi, '如果流动性转弱，需要重新核对市场叙事。')
    .replace(/watch-only/gi, '背景观察')
    .replace(/observation[-_\s]?only/gi, '背景观察')
    .replace(/score[-_\s]?grade/gi, '充分')
    .replace(/，?但不构成交易指令。?/g, '')
    .replace(/不形成判断/g, '待确认')
    .replace(/不作广泛市场方向判断/g, '不升级为强方向结论')
    .replace(/当前信号置信度较低，仅供观察。/g, '当前信号置信度仍偏有限。')
    .replace(/仅供观察/g, '用于背景观察')
    .replace(/仅观察/g, '观察')
    .replace(/证据不足/g, '待补')
    .replace(/不可判断/g, '待确认')
    .replace(/评分已暂停/g, '评分待恢复');
  return normalized || fallback;
}

function uniqueNarrativeStrings(items: Array<string | null | undefined>, limit: number, fallback: string): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  items.forEach((item) => {
    const value = marketNarrativeCopy(String(item || '').trim(), '').trim();
    if (!value || seen.has(value)) return;
    seen.add(value);
    result.push(value);
  });
  return result.length ? result.slice(0, limit) : [fallback];
}

function buildMarketNarrativeVerdict(params: {
  summary: DecisionReadinessSummary;
  statusSummary: DirectionUsabilitySummary;
  directionalSummary: MarketDirectionalSummary;
  view?: MarketOverviewDecisionSemanticsView;
}): MarketNarrativeVerdictView {
  const { summary, statusSummary, directionalSummary, view } = params;
  const readinessStatus = view?.directionReadiness?.status;
  const insufficient = Boolean(
    summary.state === 'unavailable'
    || summary.state === 'waiting'
    || view?.insufficient
    || readinessStatus === 'data_insufficient',
  );
  const directionText = [
    directionalSummary.currentLabel,
    directionalSummary.regimePhrase,
    directionalSummary.actionFrame,
    view?.postureLabel,
    view?.exposureBiasLabel,
    statusSummary.headline,
  ].filter(Boolean).join(' ');
  const weakBias = /偏弱|防守|压力|risk[-_\s]?control|risk[-_\s]?off|defensive|bearish/i.test(directionText);
  const strongBias = /偏强|偏多|偏暖|改善|修复|risk[-_\s]?on|offensive|bullish/i.test(directionText);
  const neutralBias = /中性|均衡|balanced|neutral/i.test(directionText);

  if (insufficient && summary.state === 'observe') {
    if (weakBias) {
      return {
        label: '偏弱观察',
        variant: 'caution',
        headline: '当前压力线索更清晰，关键确认仍待补齐。',
        detail: marketNarrativeCopy(summary.blockers[0] || directionalSummary.blockingDrivers[0] || statusSummary.detail || '主要压力仍待确认。'),
      };
    }
    if (strongBias) {
      return {
        label: '偏强观察',
        variant: 'info',
        headline: '当前偏强线索更清晰，关键确认仍待补齐。',
        detail: marketNarrativeCopy(summary.blockers[0] || directionalSummary.supportingDrivers[0] || statusSummary.detail || '主要驱动仍在跟踪。'),
      };
    }
    if (neutralBias || directionText.trim()) {
      return {
        label: '中性观察',
        variant: 'info',
        headline: '当前已返回中性线索，关键确认仍待补齐。',
        detail: marketNarrativeCopy(summary.blockers[0] || directionalSummary.blockingDrivers[0] || directionalSummary.supportingDrivers[0] || statusSummary.detail || '等待主线进一步清晰。'),
      };
    }
  }

  if (insufficient) {
    return {
      label: '证据待补',
      variant: summary.state === 'waiting' ? 'neutral' : 'caution',
      headline: '已返回部分市场线索，关键证据仍待补齐。',
      detail: marketNarrativeCopy(summary.blockers[0] || statusSummary.detail || '关键证据仍待补齐。'),
    };
  }
  if (weakBias) {
    return {
      label: '偏弱观察',
      variant: 'caution',
      headline: '风险压力占上风，先看压力是否缓和。',
      detail: marketNarrativeCopy(directionalSummary.blockingDrivers[0] || statusSummary.detail || '主要压力仍待确认。'),
    };
  }
  if (strongBias) {
    return {
      label: '偏强观察',
      variant: 'success',
      headline: '风险偏好线索改善，但仍需反证继续确认。',
      detail: marketNarrativeCopy(directionalSummary.supportingDrivers[0] || statusSummary.detail || '主要驱动仍在跟踪。'),
    };
  }
  return {
    label: '中性观察',
    variant: 'info',
    headline: '市场线索分化，当前以中性观察为主。',
    detail: marketNarrativeCopy(directionalSummary.blockingDrivers[0] || directionalSummary.supportingDrivers[0] || statusSummary.detail || '等待主线进一步清晰。'),
  };
}

function narrativeLineText(item?: MarketOverviewDecisionSemanticsLineView | null): string {
  if (!item) {
    return '';
  }
  return [item.label, item.meta].filter(Boolean).join(' · ');
}

function buildMarketNarrativeDrivers(params: {
  directionalSummary: MarketDirectionalSummary;
  regimeSummary?: MarketOverviewRegimeSummaryView;
  view?: MarketOverviewDecisionSemanticsView;
}): MarketNarrativeDriverView[] {
  const { directionalSummary, regimeSummary, view } = params;
  const supportLines = [
    ...(regimeSummary?.drivers || []).map(narrativeLineText),
    ...(view?.confirmationSignals || []).map(narrativeLineText),
    ...(view?.styleTilts || []).map(narrativeLineText),
    ...directionalSummary.supportingDrivers,
  ];
  const pressureLines = [
    ...(regimeSummary?.contradictions || []).map(narrativeLineText),
    ...(regimeSummary?.blockers || []).map(narrativeLineText),
    ...(view?.counterEvidence || []).map(narrativeLineText),
    ...(view?.dataGaps || []).map(narrativeLineText),
    ...directionalSummary.blockingDrivers,
  ];
  const allLines = [...supportLines, ...pressureLines]
    .map((line) => marketNarrativeCopy(line, '').trim())
    .filter(Boolean);
  const sourceForDomain = (patterns: RegExp[], preferred: string[], fallback: string) => {
    const match = preferred.find((line) => patterns.some((pattern) => pattern.test(line)))
      || allLines.find((line) => patterns.some((pattern) => pattern.test(line)));
    return marketNarrativeCopy(match || fallback);
  };
  const driverSpecs = [
    {
      key: 'index-breadth',
      label: '指数 / 宽度',
      patterns: [/指数|标普|纳指|道指|SPX|NDX|CSI|沪深|恒生|宽度|breadth|上涨|下跌/i],
      fallback: '等待指数与宽度证据补齐',
    },
    {
      key: 'volatility',
      label: '波动率',
      patterns: [/VIX|波动|volatility|risk pressure|风险压力/i],
      fallback: '等待波动压力证据补齐',
    },
    {
      key: 'rates',
      label: '利率 / 宏观',
      patterns: [/US10Y|US2Y|美国10年期|利率|收益率|美元|DXY|rates|macro|fed|credit/i],
      fallback: '等待利率与宏观证据补齐',
    },
    {
      key: 'liquidity',
      label: '流动性',
      patterns: [/流动性|资金|ETF|liquidity|fund|flow/i],
      fallback: '等待流动性证据补齐',
    },
    {
      key: 'rotation',
      label: '行业 / 轮动',
      patterns: [/轮动|行业|主题|成长|小盘|sector|rotation|theme/i],
      fallback: '等待行业轮动证据补齐',
    },
  ];

  return driverSpecs.map((spec) => {
    const detail = sourceForDomain(spec.patterns, supportLines, spec.fallback);
    const pressureMatch = pressureLines.some((line) => spec.patterns.some((pattern) => pattern.test(line)));
    const supportMatch = supportLines.some((line) => spec.patterns.some((pattern) => pattern.test(line)));
    const pending = detail === spec.fallback;
    return {
      key: spec.key,
      label: spec.label,
      status: pending ? '待补' : pressureMatch && !supportMatch ? '压力' : supportMatch ? '驱动' : '线索',
      detail,
      variant: pending ? 'neutral' : pressureMatch && !supportMatch ? 'caution' : supportMatch ? 'success' : 'info',
    };
  });
}

function buildNextObservationLine(params: {
  summary: DecisionReadinessSummary;
  directionalSummary: MarketDirectionalSummary;
  regimeSummary?: MarketOverviewRegimeSummaryView;
  view?: MarketOverviewDecisionSemanticsView;
}): string {
  const { summary, directionalSummary, regimeSummary, view } = params;
  const candidates = [
    narrativeLineText(regimeSummary?.nextWatchItems[0]),
    narrativeLineText(view?.invalidationTriggers[0]),
    summary.nextEvidence[0],
    directionalSummary.watchItems[0],
  ];
  return uniqueNarrativeStrings(candidates, 1, '等待下一项可验证信号')[0];
}

function anchorDisplayLabel(anchor: MarketOverviewHeroAnchorView): string {
  return marketNarrativeCopy(anchor.secondaryLabel ? `${anchor.primaryLabel} ${anchor.secondaryLabel}` : anchor.primaryLabel, anchor.key)
    .replace(/[()]/g, '')
    .trim();
}

function buildAnchorMoveFacts(anchors: MarketOverviewHeroAnchorView[]): string[] {
  const priority = new Map([
    ['VIX', 0],
    ['US10Y', 1],
    ['DXY', 2],
    ['BTC', 3],
  ]);
  return anchors
    .filter((anchor) => anchor.changeText && anchor.changeText !== '待确认')
    .sort((left, right) => (priority.get(left.key) ?? 10) - (priority.get(right.key) ?? 10))
    .map((anchor) => `${anchorDisplayLabel(anchor)} ${anchor.changeText}`)
    .slice(0, 6);
}

function buildWhatHappenedLine(params: {
  briefingSummary: MarketOverviewBriefingSummaryView;
  heroAnchors: MarketOverviewHeroAnchorView[];
  verdict: MarketNarrativeVerdictView;
}): string {
  const { briefingSummary, heroAnchors, verdict } = params;
  const lead = marketNarrativeCopy(briefingSummary.leadMessage, '').trim();
  const moveFacts = buildAnchorMoveFacts(heroAnchors);
  if (moveFacts.length) {
    return uniqueNarrativeStrings([
      lead && !/暂无简报/.test(lead) ? lead : '',
      `重点变化：${moveFacts.join('，')}。`,
    ], 2, verdict.headline).join(' ');
  }
  return marketNarrativeCopy(lead || verdict.headline, verdict.headline);
}

function buildWhatMattersLine(params: {
  drivers: MarketNarrativeDriverView[];
  verdict: MarketNarrativeVerdictView;
  directionalSummary: MarketDirectionalSummary;
}): string {
  const { drivers, verdict, directionalSummary } = params;
  const driverDetails = drivers
    .filter((driver) => driver.status !== '待补')
    .slice(0, 2)
    .map((driver) => `${driver.label}：${driver.detail}`);
  return uniqueNarrativeStrings([
    ...driverDetails,
    directionalSummary.blockingDrivers[0],
    verdict.detail,
  ], 2, verdict.detail).join('；');
}

function buildNextCheckLine(params: {
  nextObservation: string;
  missingButObservable: string[];
  summary: DecisionReadinessSummary;
  view?: MarketOverviewDecisionSemanticsView;
}): string {
  const { nextObservation, missingButObservable, summary, view } = params;
  if (summary.state === 'unavailable' || view?.insufficient) {
    return marketNarrativeCopy(`先看 ${nextObservation}；待补 ${missingButObservable.join(' / ')}。`);
  }
  return marketNarrativeCopy(`${nextObservation}；若该线索转弱或迟迟没有确认，需要重新核对市场叙事。`);
}

function buildCompactMissingSummary(params: {
  summary: DecisionReadinessSummary;
  view?: MarketOverviewDecisionSemanticsView;
  missingButObservable: string[];
}): string | null {
  const { summary, view, missingButObservable } = params;
  if (summary.state !== 'unavailable' && !view?.insufficient) {
    return null;
  }
  return marketNarrativeCopy(`可见事实有限：${missingButObservable.join(' / ')}；当前只保留已返回市场事实。`);
}

const MarketOverviewSetupPath: React.FC<{ testId: string }> = ({ testId }) => (
  <div
    data-testid={testId}
    className="mt-3 rounded-lg border border-[color:var(--wolfy-accent-soft-border,var(--wolfy-border-subtle))] bg-[color:var(--wolfy-surface-inset-lift)] p-3"
  >
    <div className="flex min-w-0 flex-col gap-3 md:flex-row md:items-start md:justify-between">
      <div className="min-w-0">
        <p className="text-[11px] font-semibold text-[color:var(--wolfy-text-secondary)]">查看数据状态说明</p>
        <p className="mt-1 max-w-3xl text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">
          补齐可用、部分可用与延迟可用状态；是否进入评分仍由现有证据门槛决定。
        </p>
      </div>
      <div className="flex shrink-0 flex-wrap gap-2">
        <a className={MARKET_OVERVIEW_SETUP_ACTION_CLASS} href={buildProviderOpsSetupHref('market_overview')}>
          查看数据状态
        </a>
        <a className={MARKET_OVERVIEW_SETUP_ACTION_CLASS} href={buildDataSourcesSetupHref('market_overview')}>
          前往数据设置
        </a>
      </div>
    </div>
  </div>
);

const MarketOverviewDirectionSummary: React.FC<{ summary: MarketDirectionalSummary }> = ({ summary }) => (
  <section
    data-testid="market-overview-direction-summary"
    className="relative overflow-hidden border-t border-[color:var(--wolfy-divider)] bg-[color:var(--wolfy-surface-input)] p-2.5 md:px-3"
  >
    <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[color:var(--wolfy-divider)] to-transparent" aria-hidden="true" />
    <div className="flex min-w-0 flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
      <div className="min-w-0">
        <p className="text-[10px] font-medium tracking-[0.24em] text-[color:var(--wolfy-text-muted)]">
          {summary.currentLabel.startsWith('当前') ? '市场方向摘要' : summary.title}
        </p>
        <h2 className="mt-1 text-sm font-semibold leading-5 text-[color:var(--wolfy-text-primary)] md:text-base">
          {summary.currentLabel}
        </h2>
        <div className="mt-1.5 flex min-w-0 flex-wrap gap-1.5">
          <TerminalChip variant={summary.biasVariant}>{summary.regimePhrase}</TerminalChip>
          <TerminalChip variant={summary.confidenceVariant}>{summary.confidenceLabel}</TerminalChip>
          <TerminalChip variant={summary.biasVariant}>{summary.actionFrame}</TerminalChip>
        </div>
      </div>
    </div>
    <div className="sr-only">
      {[
        { key: 'supporting', title: summary.supportingTitle, items: summary.supportingDrivers, tone: 'text-[color:var(--state-success-text)]' },
        { key: 'blocking', title: summary.blockingTitle, items: summary.blockingDrivers, tone: 'text-[color:var(--state-warning-text)]' },
        { key: 'watch', title: summary.watchTitle, items: summary.watchItems, tone: 'text-[color:var(--wolfy-text-secondary)]' },
      ].map((block) => (
        <div key={block.key} className="min-w-0 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-input)] p-2">
          <p className="text-[11px] font-medium text-[color:var(--wolfy-text-muted)]">{block.title}</p>
          <div className="mt-1.5 flex min-w-0 flex-wrap gap-1">
            {block.items.map((item, index) => (
              <span key={`${block.key}-${item}-${index}`} className={cn('max-w-full truncate rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-input)] px-2 py-1 text-[11px] font-semibold', block.tone)}>
                {marketNarrativeCopy(item)}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  </section>
);

const CrossAssetHeroRibbon: React.FC<{ anchors: MarketOverviewHeroAnchorView[] }> = ({ anchors }) => (
  <KeyLevelStrip
    data-testid="market-overview-hero-ribbon"
    className="rounded-none border-x-0 py-1"
    levels={anchors.map((anchor) => ({
      key: anchor.key,
      testId: `market-overview-hero-${anchor.key}`,
      label: anchor.secondaryLabel ? `${anchor.primaryLabel} (${anchor.secondaryLabel})` : anchor.primaryLabel,
      value: (
        <span className="flex min-w-0 flex-col">
          <span className="truncate font-mono text-base font-semibold leading-none text-[color:var(--wolfy-text-primary)] md:text-lg">
            {anchor.valueText}
          </span>
          <span className={cn('mt-0.5 truncate font-mono text-[10px] font-semibold', anchor.changeToneClass)}>
            {anchor.changeText}
          </span>
        </span>
      ),
      valueClassName: 'text-left text-inherit',
      className: 'py-1.5',
    }))}
  />
);

export const MarketOverviewVisualEvidenceStrip: React.FC<{
  cards: MarketOverviewVisualEvidenceCardView[];
}> = ({ cards }) => {
  const withPoints = cards.filter((card) => card.points.length > 0);
  const withoutPoints = cards.filter((card) => card.points.length === 0);
  const meaningfulCount = withPoints.length;
  const density = meaningfulCount >= 3 ? 'full' : meaningfulCount >= 1 ? 'compact' : 'bounded-empty';

  return (
    <section
      data-testid="market-overview-visual-evidence-strip"
      data-module-density={density}
      data-evidence-group-count={meaningfulCount}
      className="border-t border-[color:var(--wolfy-divider)] px-3 py-3 md:px-4"
    >
      <div className="mb-3 flex min-w-0 items-end justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-[color:var(--wolfy-text-muted)]">核心图表证据</p>
          <p className="mt-1 text-sm text-[color:var(--wolfy-text-muted)]">只展示当前已有市场证据，不扩展结论边界。</p>
        </div>
        <TerminalChip variant="neutral" className="shrink-0">
          {density === 'bounded-empty' ? '证据待补' : density === 'compact' ? '部分可用' : '图形证据'}
        </TerminalChip>
      </div>

      {density === 'bounded-empty' ? (
        <div
          data-testid="market-overview-visual-evidence-bounded-empty"
          className="rounded-lg border border-dashed border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-input)] px-3 py-3"
        >
          <p className="text-sm font-medium text-[color:var(--wolfy-text-secondary)]">
            当前没有可渲染的图形证据
          </p>
          <p className="mt-1 text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">
            不补推断图形。缺失项保持观察边界，可继续使用上方市场论点与下一研究入口。
          </p>
          <ul className="mt-2 space-y-1 text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">
            {withoutPoints.map((card) => (
              <li
                key={card.id}
                data-testid={`market-overview-visual-card-${card.id}-unavailable`}
              >
                <span
                  data-testid={`market-overview-visual-card-${card.id}`}
                  className="font-medium text-[color:var(--wolfy-text-secondary)]"
                >
                  <span data-testid={`market-overview-visual-card-eyebrow-${card.id}`} className="break-words whitespace-normal">{card.eyebrow}</span>
                  {' · '}
                  <span data-testid={`market-overview-visual-card-title-${card.id}`} className="break-words whitespace-normal">{card.title}</span>
                </span>
                {' — '}
                {card.unavailableCopy || '图形证据暂缺，当前保持观察。'}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <div className={cn(
          'grid min-w-0 gap-3',
          withPoints.length >= 3 ? 'grid-cols-1 xl:grid-cols-3' : withPoints.length === 2 ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-1',
        )}
        >
          {withPoints.map((card) => (
            <article
              key={card.id}
              data-testid={`market-overview-visual-card-${card.id}`}
              className="min-w-0 rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-input)] px-3 py-3"
            >
              <p
                data-testid={`market-overview-visual-card-eyebrow-${card.id}`}
                className="break-words whitespace-normal text-[10px] font-semibold uppercase tracking-widest text-[color:var(--wolfy-text-muted)] md:truncate"
              >
                {card.eyebrow}
              </p>
              <h3
                data-testid={`market-overview-visual-card-title-${card.id}`}
                className="mt-1 break-words whitespace-normal text-sm font-semibold text-[color:var(--wolfy-text-secondary)] md:truncate"
              >
                {card.title}
              </h3>
              <p className="mt-1 text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">{card.summary}</p>
              <div
                data-testid={`market-overview-visual-card-${card.id}-points`}
                className="mt-3 grid min-w-0 grid-cols-1 gap-2"
              >
                {card.points.map((point) => (
                  <div
                    key={point.key}
                    data-testid={`market-overview-visual-point-${point.key}`}
                    className="grid min-w-0 grid-cols-[minmax(0,1fr)_88px] items-center gap-3 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-input)] px-2.5 py-2"
                  >
                    <div className="min-w-0">
                      <div className="flex min-w-0 items-center justify-between gap-3">
                        <p className="break-words whitespace-normal text-[11px] font-semibold text-[color:var(--wolfy-text-secondary)] md:truncate">{point.label}</p>
                        <p className="shrink-0 font-mono text-[11px] text-[color:var(--wolfy-text-muted)]">{point.valueText}</p>
                      </div>
                      <div className="mt-1 flex min-w-0 items-center gap-3">
                        <div className="min-w-0 flex-1">
                          <MarketOverviewSparkline values={point.sparkline} tone={point.toneClass} className="h-6" />
                        </div>
                        <p className={cn('shrink-0 font-mono text-[10px] font-semibold', point.toneClass)}>{point.changeText}</p>
                      </div>
                    </div>
                    <div className="flex h-full items-center justify-end">
                      <div className={cn('h-9 w-1.5 rounded-full bg-current opacity-80', point.toneClass)} aria-hidden="true" />
                    </div>
                  </div>
                ))}
              </div>
            </article>
          ))}
          {withoutPoints.length > 0 ? (
            <div
              data-testid="market-overview-visual-evidence-missing-compact"
              className={cn(
                'min-w-0 rounded-xl border border-dashed border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-input)] px-3 py-3',
                withPoints.length >= 2 ? 'md:col-span-2 xl:col-span-1' : '',
              )}
            >
              <p className="text-[10px] font-semibold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">待补图形</p>
              <ul className="mt-2 space-y-1.5 text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">
                {withoutPoints.map((card) => (
                  <li key={card.id} data-testid={`market-overview-visual-card-${card.id}-unavailable`}>
                    <span
                      data-testid={`market-overview-visual-card-${card.id}`}
                      className="font-medium text-[color:var(--wolfy-text-secondary)]"
                    >
                      <span data-testid={`market-overview-visual-card-eyebrow-${card.id}`} className="break-words whitespace-normal">{card.eyebrow}</span>
                      {' · '}
                      <span data-testid={`market-overview-visual-card-title-${card.id}`} className="break-words whitespace-normal">{card.title}</span>
                    </span>
                    {' — '}
                    {card.unavailableCopy || '图形证据暂缺，当前保持观察。'}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
};

const MarketDecisionSemanticsList: React.FC<{
  testId: string;
  label: string;
  emptyLabel: string;
  items: MarketOverviewDecisionSemanticsLineView[];
}> = ({ testId, label, emptyLabel, items }) => (
  <div className="min-w-0">
    <p className="text-[11px] font-medium text-[color:var(--wolfy-text-muted)]">{label}</p>
    <div
      data-testid={testId}
      className="mt-2 flex max-h-32 min-w-0 flex-col gap-1.5 overflow-y-auto no-scrollbar pr-1 text-[11px] leading-5 text-[color:var(--wolfy-text-muted)] ui-scroll-y-quiet"
    >
      {items.length ? items.map((item) => (
        <p key={item.key} className="min-w-0">
          <span className="font-semibold text-[color:var(--wolfy-text-secondary)]">{item.label}</span>
          {item.meta ? <span className="text-[color:var(--wolfy-text-muted)]"> · {item.meta}</span> : null}
        </p>
      )) : <p className="text-[color:var(--wolfy-text-muted)]">{emptyLabel}</p>}
    </div>
  </div>
);

const MarketOverviewRegimeSummaryBlock: React.FC<{ view: MarketOverviewRegimeSummaryView }> = ({ view }) => {
  const lists = [
    { testId: 'market-overview-regime-summary-drivers', label: '驱动', emptyLabel: '暂无显式驱动', items: view.drivers },
    { testId: 'market-overview-regime-summary-blockers', label: '阻断', emptyLabel: '暂无显式阻断', items: view.blockers },
    { testId: 'market-overview-regime-summary-contradictions', label: '反证', emptyLabel: '暂无显式反证', items: view.contradictions },
    { testId: 'market-overview-regime-summary-next-watch', label: '下一观察', emptyLabel: '等待下一项确认信号', items: view.nextWatchItems },
  ] as const;
  const meaningfulLists = lists.filter((list) => list.items.length > 0);
  const density = meaningfulLists.length >= 3 ? 'full' : meaningfulLists.length >= 1 ? 'compact' : 'bounded-empty';

  return (
  <section
    data-testid="market-overview-regime-summary"
    data-module-density={density}
    className="mt-4 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-input)] px-3 py-3"
  >
    <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
      <div className="min-w-0">
        <p className="text-[11px] font-medium text-[color:var(--wolfy-text-muted)]">市场温度摘要</p>
        <h3
          data-testid="market-overview-regime-summary-title"
          className="mt-1 text-sm font-semibold leading-6 text-[color:var(--wolfy-text-secondary)]"
        >
          {view.title}
        </h3>
        <p className="mt-2 max-w-4xl text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">{view.explanation}</p>
      </div>
      <div className="flex min-w-0 shrink-0 flex-wrap gap-2 lg:justify-end">
        <TerminalChip variant="neutral">{view.label}</TerminalChip>
        <TerminalChip variant="info">
          {view.confidenceLabel}
          {view.confidenceValueText ? ` · ${view.confidenceValueText}` : ''}
        </TerminalChip>
      </div>
    </div>
    {density === 'bounded-empty' ? (
      <div className="mt-3 rounded-md border border-dashed border-[color:var(--wolfy-border-subtle)] px-3 py-2 text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">
        驱动 / 阻断 / 反证 / 下一观察暂无显式条目；保持观察，不扩展结论。
        {/* Preserve test anchors for empty semantics lists without a 4-card wall. */}
        <span className="sr-only">
          {lists.map((list) => (
            <span key={list.testId} data-testid={list.testId}>{list.emptyLabel}</span>
          ))}
        </span>
      </div>
    ) : (
    <div className={cn('mt-4 grid min-w-0 gap-3', density === 'full' ? 'grid-cols-1 xl:grid-cols-2' : 'grid-cols-1 md:grid-cols-2')}>
      {(density === 'full' ? lists : meaningfulLists).map((list) => (
        <MarketDecisionSemanticsList
          key={list.testId}
          testId={list.testId}
          label={list.label}
          emptyLabel={list.emptyLabel}
          items={list.items}
        />
      ))}
      {density === 'compact' && meaningfulLists.length < lists.length ? (
        <p className="md:col-span-2 text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">
          其余语义列暂无显式条目，不扩展为空卡片。
        </p>
      ) : null}
    </div>
    )}
  </section>
  );
};

function directionUsabilitySummary(view: MarketOverviewDecisionSemanticsView): DirectionUsabilitySummary {
  const readiness = view.directionReadiness;
  const reasonText = joinMarketReasonLabels(
    [...view.capReasons, ...(readiness?.blockingReasons || [])],
    'zh',
    3,
    '数据边界仍待确认',
  );

  if (readiness?.status === 'direction_ready' && !view.insufficient) {
    return {
      label: '可参考',
      variant: 'success',
      headline: '当前方向判断可参考',
      detail: `主要依据已满足方向门槛，仍需继续核对反证与缺失证据。`,
    };
  }

  if (readiness?.status === 'partial_context_only') {
    return {
      label: '部分可参考',
      variant: 'info',
      headline: '已有主线线索返回，当前先按观察路径继续跟踪。',
      detail: `当前仍需补齐${reasonText}。`,
    };
  }

  return {
    label: '方向不可用',
    variant: 'caution',
    headline: '已返回部分市场线索，但还不能升级为可靠方向判断。',
    detail: `当前仍需补齐${reasonText}。`,
  };
}

function uniqueReadinessItems(items: Array<string | null | undefined>, limit: number, fallback: string): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  items.forEach((item) => {
    const value = String(item || '').trim();
    if (!value || seen.has(value)) return;
    seen.add(value);
    result.push(value);
  });
  return result.length ? result.slice(0, limit) : [fallback];
}

function overviewReadinessState(params: {
  view?: MarketOverviewDecisionSemanticsView;
  decisionReliable: boolean;
  dataState: MarketOverviewDataStateStripView;
}): DecisionReadinessState {
  const { view, decisionReliable, dataState } = params;
  const readiness = view?.directionReadiness;
  const scoreGradeCount = readiness?.scoreGradeCount ?? (decisionReliable ? 3 : 0);
  const observationOnlyCount = readiness?.observationOnlyCount ?? 0;
  const missingCount = readiness?.missingCount ?? 0;

  if (dataState.isRefreshing && dataState.availableCount === 0) {
    return 'waiting';
  }
  if (
    readiness?.status === 'direction_ready'
    && decisionReliable
    && !view?.insufficient
    && scoreGradeCount >= 3
  ) {
    return 'ready';
  }
  if (
    readiness?.status === 'data_insufficient'
    && scoreGradeCount <= 0
  ) {
    if (dataState.availableCount > 0 && !dataState.hasUnavailable) {
      return 'observe';
    }
    if (missingCount > 0 || dataState.hasFallback || dataState.hasUnavailable) {
      return 'unavailable';
    }
  }
  if (
    readiness?.status === 'partial_context_only'
    || scoreGradeCount > 0
    || observationOnlyCount > 0
    || dataState.availableCount > 0
  ) {
    return 'observe';
  }
  return 'unavailable';
}

function buildOverviewDecisionReadiness(params: {
  view?: MarketOverviewDecisionSemanticsView;
  decisionReliable: boolean;
  dataState: MarketOverviewDataStateStripView;
  decisionText: string;
}): DecisionReadinessSummary {
  const { view, decisionReliable, dataState, decisionText } = params;
  const readiness = view?.directionReadiness;
  const state = overviewReadinessState({ view, decisionReliable, dataState });
  const scoreGradeCount = readiness?.scoreGradeCount ?? (decisionReliable ? 3 : 0);
  const observationOnlyCount = readiness?.observationOnlyCount ?? 0;
  const missingCount = readiness?.missingCount ?? 0;
  const rawBlockers = [
    ...(view?.capReasons || []).map((reason) => marketIntelligenceReasonLabel(reason)),
    ...(readiness?.blockingReasons || []).map((reason) => marketIntelligenceReasonLabel(reason)),
    ...(readiness?.missingPillars || []).map((pillar) => pillar.label),
    ...(view?.dataGaps || []).map((gap) => gap.label),
    dataState.hasFallback ? '当前为延迟可用或部分可用状态' : '',
    dataState.staleCount > 0 ? '存在过期数据' : '',
    dataState.hasUnavailable ? '部分数据暂不可用' : '',
  ];
  const nextEvidence = [
    ...(readiness?.missingPillars || []).map((pillar) => pillar.label),
    ...(view?.dataGaps || []).map((gap) => gap.label),
    ...(view?.invalidationTriggers || []).map((item) => item.label),
    state === 'ready' ? '继续确认反证是否进入可用状态' : '',
  ];

  return {
    state,
    stateLabel: decisionReadinessStateLabel(state),
    stateVariant: decisionReadinessVariant(state),
    qualityLabel: `可用 ${scoreGradeCount} · 背景线索 ${observationOnlyCount} · 待补 ${missingCount}`,
    blockers: uniqueReadinessItems(rawBlockers, 4, state === 'ready' ? '暂无关键阻塞' : '关键证据仍待补齐'),
    nextEvidence: uniqueReadinessItems(nextEvidence, 3, '补齐可用状态覆盖'),
    conclusion: state === 'ready'
      ? decisionText
      : MARKET_DECISION_NOT_READY_NOTICE,
  };
}

function normalizeConfidenceValue(label?: string | null): '较充分' | '中等' | '有限' {
  const normalized = String(label || '').trim();
  if (normalized === '高') {
    return '较充分';
  }
  if (normalized === '中') {
    return '中等';
  }
  return '有限';
}

function buildConsumerConfidenceSummary(
  summary: DecisionReadinessSummary,
  view?: MarketOverviewDecisionSemanticsView,
): ConsumerConfidenceSummaryView {
  const failClosedDirection = view?.insufficient || view?.directionReadiness?.status === 'data_insufficient';

  if (summary.state === 'waiting') {
    return {
      value: '更新中',
      detail: '等待当前批次数据完成后，再更新方向观察依据。',
      chipLabel: '信心水平：更新中',
    };
  }

  if (summary.state === 'unavailable') {
    return {
      value: '待补',
      detail: '关键数据暂不可用，仍可观察已返回的市场线索。',
      chipLabel: '信心状态：待补',
    };
  }

  if (failClosedDirection) {
    return {
      value: '待补',
      detail: '关键依据仍待补齐，先跟踪已返回线索。',
      chipLabel: '信心状态：待补',
    };
  }

  if (summary.state === 'observe') {
    return {
      value: '有限',
      detail: '现有线索只足够支持观察，需等待关键证据延续。',
      chipLabel: '信心水平：有限',
    };
  }

  const confidenceValue = normalizeConfidenceValue(
    view?.directionReadiness?.confidenceLabel || view?.confidenceLabel,
  );
  if (confidenceValue === '较充分') {
    return {
      value: confidenceValue,
      detail: '主要依据较完整，当前方向可继续用于研究观察。',
      chipLabel: `信心水平：${confidenceValue}`,
    };
  }
  if (confidenceValue === '中等') {
    return {
      value: confidenceValue,
      detail: '已有主要依据，但仍需继续核对反证与后续更新。',
      chipLabel: `信心水平：${confidenceValue}`,
    };
  }
  return {
    value: confidenceValue,
    detail: '部分依据仍待补齐，先跟踪最清晰的市场线索。',
    chipLabel: `信心水平：${confidenceValue}`,
  };
}

function dataStatusLabel(summary: DecisionReadinessSummary, dataState: MarketOverviewDataStateStripView): string {
  if (summary.state === 'waiting' || dataState.isRefreshing) {
    return '正在更新';
  }
  if (summary.state === 'unavailable') {
    return '部分可用';
  }
  if (dataState.hasUnavailable) {
    return '部分可用';
  }
  if (dataState.staleCount > 0 || dataState.hasFallback) {
    return '延迟可用';
  }
  return '可用';
}

function buildMarketOverviewQualityFacets(params: {
  summary: DecisionReadinessSummary;
  dataState: MarketOverviewDataStateStripView;
  confidenceSummary: ConsumerConfidenceSummaryView;
  locale: 'zh' | 'en';
}): ResearchQualityFacet[] {
  const { summary, dataState, confidenceSummary, locale } = params;
  const facets: ResearchQualityFacet[] = [
    {
      key: 'freshness',
      kind: dataState.staleCount > 0 ? 'stale' : dataState.isRefreshing ? 'freshness' : 'freshness',
      tone: dataState.staleCount > 0 ? 'caution' : dataState.isRefreshing ? 'info' : 'success',
      label: locale === 'en' ? 'Freshness' : '新鲜度',
      value: dataStatusLabel(summary, dataState),
      detail: dataState.updatedAtLabel
        ? (locale === 'en' ? `Updated ${dataState.updatedAtLabel}` : `最近更新 ${dataState.updatedAtLabel}`)
        : undefined,
    },
    {
      key: 'coverage',
      kind: dataState.hasUnavailable || dataState.unavailableCount > 0
        ? 'partial'
        : dataState.hasFallback
          ? 'partial'
          : 'coverage',
      tone: dataState.hasUnavailable ? 'caution' : dataState.hasFallback ? 'info' : 'success',
      label: locale === 'en' ? 'Coverage' : '覆盖',
      value: locale === 'en'
        ? `${dataState.availableCount} available · ${dataState.fallbackCount} delayed · ${dataState.unavailableCount} unavailable`
        : `${dataState.availableCount} 可用 · ${dataState.fallbackCount} 延迟 · ${dataState.unavailableCount} 不可用`,
    },
    {
      key: 'observation-only',
      kind: summary.state === 'observe' || summary.state === 'unavailable' ? 'observation-only' : 'authority',
      tone: summary.state === 'unavailable' ? 'caution' : summary.state === 'observe' ? 'info' : 'neutral',
      label: locale === 'en' ? 'Use posture' : '使用口径',
      value: confidenceSummary.chipLabel || confidenceSummary.value,
      detail: confidenceSummary.detail,
    },
  ];

  if (dataState.hasFallback) {
    facets.push({
      key: 'delayed',
      kind: 'delayed',
      tone: 'caution',
      label: locale === 'en' ? 'Delayed / proxy' : '延迟 / 代理',
      value: locale === 'en'
        ? `${dataState.fallbackCount} delayed or partial modules`
        : `${dataState.fallbackCount} 个延迟或部分可用模块`,
    });
  }

  if (dataState.hasUnavailable || dataState.unavailableCount > 0) {
    facets.push({
      key: 'unavailable',
      kind: 'unavailable',
      tone: 'danger',
      label: locale === 'en' ? 'Unavailable' : '不可用',
      value: locale === 'en'
        ? `${dataState.unavailableCount} modules unavailable`
        : `${dataState.unavailableCount} 个模块暂不可用`,
    });
  }

  return facets;
}

const MarketOverviewConclusionLayer: React.FC<{
  testId: string;
  summary: DecisionReadinessSummary;
  statusSummary: DirectionUsabilitySummary;
  dataState: MarketOverviewDataStateStripView;
  directionalSummary: MarketDirectionalSummary;
  regimeSummary?: MarketOverviewRegimeSummaryView;
  view?: MarketOverviewDecisionSemanticsView;
  briefingSummary: MarketOverviewBriefingSummaryView;
  heroAnchors: MarketOverviewHeroAnchorView[];
}> = ({ testId, summary, statusSummary, dataState, directionalSummary, regimeSummary, view, briefingSummary, heroAnchors }) => {
  const routeLocale = typeof window !== 'undefined' ? parseLocaleFromPathname(window.location.pathname) : null;
  const isEnglishRoute = routeLocale === 'en';
  const researchLocale = isEnglishRoute ? 'en' : 'zh';
  const confidenceSummary = buildConsumerConfidenceSummary(summary, view);
  const verdict = buildMarketNarrativeVerdict({
    summary,
    statusSummary,
    directionalSummary,
    view,
  });
  const drivers = buildMarketNarrativeDrivers({
    directionalSummary,
    regimeSummary,
    view,
  });
  const nextObservation = buildNextObservationLine({
    summary,
    directionalSummary,
    regimeSummary,
    view,
  });
  const missingButObservable = uniqueNarrativeStrings([
    summary.blockers[0],
    view?.dataGaps[0]?.label,
    regimeSummary?.blockers[0]?.label,
    directionalSummary.blockingDrivers[0],
  ], 2, '暂无关键阻断');
  const missingSummary = buildCompactMissingSummary({ summary, view, missingButObservable });
  const whatHappened = buildWhatHappenedLine({ briefingSummary, heroAnchors, verdict });
  const whatMatters = buildWhatMattersLine({ drivers, verdict, directionalSummary });
  const nextCheck = buildNextCheckLine({ nextObservation, missingButObservable, summary, view });
  const narrativeFacts = [
    {
      key: 'what-happened',
      label: isEnglishRoute ? 'What happened' : '现在市场发生了什么',
      value: whatHappened,
      detail: verdict.headline,
    },
    {
      key: 'what-matters',
      label: isEnglishRoute ? 'Why it matters' : '为什么',
      value: whatMatters,
      detail: marketNarrativeCopy(
        isEnglishRoute
          ? `Data state: ${dataStatusLabel(summary, dataState)}; confidence ${confidenceSummary.value}.`
          : `数据状态：${dataStatusLabel(summary, dataState)}；信心水平：${confidenceSummary.value}。`,
      ),
    },
    {
      key: 'next',
      label: isEnglishRoute ? 'What to check next' : '接下来观察什么',
      value: nextCheck,
      detail: isEnglishRoute
        ? 'Research check order only — not a stronger conclusion.'
        : '只作为研究核对顺序，不升级为更强结论。',
    },
  ];

  const contradictoryLines = uniqueNarrativeStrings([
    ...(regimeSummary?.contradictions || []).map(narrativeLineText),
    ...(view?.counterEvidence || []).map(narrativeLineText),
    ...directionalSummary.blockingDrivers,
  ], 3, '');

  const qualityFacets = buildMarketOverviewQualityFacets({
    summary,
    dataState,
    confidenceSummary,
    locale: researchLocale,
  });

  // Next-research handoff is rendered after path / metrics / drivers / data state
  // (MarketOverviewResearchHandoff) so first viewport stays market observation + path.

  return (
    <section
      data-testid={testId}
      data-market-research-flow="market-thesis"
      data-market-overview-anatomy="observation-composition"
      className="min-w-0 border-b border-[color:var(--wolfy-divider)] bg-[color:var(--wolfy-surface-console)]"
    >
      <ObservationHead
        density="research"
        locale={researchLocale}
        data-testid="market-overview-observation-head"
        eyebrow={isEnglishRoute ? 'Market thesis' : '市场论点'}
        title={isEnglishRoute ? 'Market State Overview' : '市场状态概览'}
        lead={(
          <span className="flex min-w-0 flex-col gap-1">
            <span
              data-testid="market-decision-semantics-advice-boundary"
              className="break-words whitespace-normal text-base font-semibold text-[color:var(--wolfy-text-primary)] md:text-lg"
            >
              <span data-testid="market-overview-top-verdict" className="break-words whitespace-normal">
                {verdict.label}
              </span>
            </span>
            <span>{verdict.headline}</span>
          </span>
        )}
        status={(
          <div className="flex min-w-0 flex-wrap items-center gap-1.5">
            <TerminalChip variant={verdict.variant === 'neutral' ? 'neutral' : verdict.variant} className="px-2 py-1 text-[10px] font-semibold">
              {verdict.label}
            </TerminalChip>
            <TerminalChip
              variant={dataState.variant === 'caution' ? 'caution' : dataState.isRefreshing ? 'info' : 'neutral'}
              className="px-2 py-1 text-[10px] font-semibold"
            >
              {dataStatusLabel(summary, dataState)}
            </TerminalChip>
            <TerminalChip variant="neutral" className="px-2 py-1 text-[10px] font-semibold">
              {isEnglishRoute ? `Confidence ${confidenceSummary.value}` : `信心 ${confidenceSummary.value}`}
            </TerminalChip>
            <span
              data-testid="market-overview-status-line"
              className="min-w-0 text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]"
            >
              {marketNarrativeCopy(
                `${verdict.label === '证据待补' ? (isEnglishRoute ? 'Limited facts' : '事实有限') : verdict.label} · ${dataStatusLabel(summary, dataState)} · ${isEnglishRoute ? 'confidence' : '信心水平'} ${confidenceSummary.value}`,
              )}
            </span>
          </div>
        )}
        known={[
          {
            key: 'what-happened',
            label: isEnglishRoute ? 'Observation' : '观察',
            body: marketNarrativeCopy(whatHappened),
          },
        ]}
        changing={[
          {
            key: 'what-matters',
            label: isEnglishRoute ? 'Drivers' : '驱动',
            body: marketNarrativeCopy(whatMatters),
          },
        ]}
        unknown={missingButObservable.filter(Boolean).length ? [{
          key: 'unknown',
          label: isEnglishRoute ? 'Open items' : '待确认',
          body: marketNarrativeCopy(missingButObservable.join(' / ')),
        }] : undefined}
        contradictory={contradictoryLines.length ? [{
          key: 'contradictory',
          label: isEnglishRoute ? 'Tension' : '张力',
          body: marketNarrativeCopy(contradictoryLines.join('；')),
        }] : undefined}
      >
        <section
          data-testid="market-overview-summary-strip"
          aria-label={isEnglishRoute ? 'First-read summary' : '首读摘要'}
          className="grid min-w-0 grid-cols-1 gap-1.5 md:grid-cols-3"
        >
          {narrativeFacts.map((fact) => (
            <div
              key={fact.key}
              className="min-w-0 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-input)] px-2.5 py-2"
            >
              <p className="text-[11px] font-medium text-[color:var(--wolfy-text-muted)]">{fact.label}</p>
              <p className="mt-1 line-clamp-2 text-xs font-semibold leading-5 text-[color:var(--wolfy-text-primary)]">
                {marketNarrativeCopy(fact.value)}
              </p>
              <p className="mt-1 line-clamp-2 text-[11px] leading-4 text-[color:var(--wolfy-text-muted)]">
                {marketNarrativeCopy(fact.detail)}
              </p>
            </div>
          ))}
        </section>
        {missingSummary ? (
          <p
            data-testid="market-overview-missing-summary"
            className="mt-3 rounded-lg border border-[color:var(--state-warning-border)] bg-[color:var(--state-warning-bg)] px-3 py-2 text-[11px] leading-5 text-[color:var(--state-warning-text)]"
          >
            {missingSummary}
          </p>
        ) : null}
      </ObservationHead>

      <div className="flex min-w-0 flex-col gap-2 border-t border-[color:var(--wolfy-divider)] px-2.5 py-2.5 md:px-3">
        <section
          data-testid="market-overview-key-drivers"
          className="sr-only"
          aria-label={isEnglishRoute ? 'Key market drivers' : '关键市场驱动'}
        >
          {drivers.map((driver) => (
            <span key={driver.key}>{driver.label}</span>
          ))}
        </section>
        <p data-testid="market-overview-next-observation" className="sr-only">
          {isEnglishRoute ? 'Next observation' : '下一观察'}：{nextObservation}
        </p>
        <ResearchDataQualityComposition
          title={isEnglishRoute ? 'Evidence coverage / confidence' : '证据覆盖 / 置信度'}
          density="research"
          locale={researchLocale}
          compact
          data-testid="market-overview-data-quality-composition"
          facets={qualityFacets}
        />

        <ResearchRiskLimits
          density="research"
          locale={researchLocale}
          placement="disclosure"
          data-testid="market-overview-research-risk-limits"
          title={isEnglishRoute ? 'Research limits' : '研究限制'}
          cannotEstablish={[
            isEnglishRoute
              ? 'Current market evidence cannot establish trade timing, position size, or investment advice.'
              : '当前市场证据不能成立交易时机、仓位规模或投资建议。',
            verdict.label === '证据待补' || summary.state === 'unavailable'
              ? (isEnglishRoute
                ? 'Directional confidence remains capped while critical confirmation is missing.'
                : '关键确认仍缺失时，方向置信保持上限约束。')
              : (isEnglishRoute
                ? 'A single module move does not prove a durable market regime shift.'
                : '单一模块变动不能证明稳定的市场状态切换。'),
          ]}
          missingEvidence={missingButObservable.map((body, index) => ({ key: `missing-${index}`, body: marketNarrativeCopy(body) }))}
          dataLimitations={[
            dataState.hasFallback
              ? (isEnglishRoute
                ? 'Some modules are delayed, cached, or partial and must not be treated as live authority.'
                : '部分模块为延迟、缓存或部分可用，不能当作实时权威。')
              : null,
            dataState.staleCount > 0
              ? (isEnglishRoute
                ? 'Stale timestamps limit how far the current observation can be extended.'
                : '过期时间戳限制当前观察可延伸的范围。')
              : null,
            dataState.hasUnavailable
              ? (isEnglishRoute
                ? 'Unavailable coverage leaves cross-asset confirmation incomplete.'
                : '不可用覆盖使跨资产确认不完整。')
              : null,
          ].filter(Boolean).map((body, index) => ({ key: `data-limit-${index}`, body: body as string }))}
          modelLimitations={[
            isEnglishRoute
              ? 'Regime and temperature labels are observation readiness signals, not scored recommendations.'
              : '状态与温度标签是观察就绪信号，不是评分化推荐。',
          ]}
        />

        <p className="text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">
          {isEnglishRoute ? 'Research observation, not investment advice.' : '研究观察，不构成投资建议。'}
        </p>
      </div>
    </section>
  );
};

export const MarketOverviewResearchHandoff: React.FC<{
  locale?: 'zh' | 'en';
  className?: string;
}> = ({ locale, className }) => {
  const routeLocale = locale
    ?? (typeof window !== 'undefined' ? parseLocaleFromPathname(window.location.pathname) : null);
  const isEnglishRoute = routeLocale === 'en';
  const researchLocale = isEnglishRoute ? 'en' : 'zh';
  const researchSteps = buildMarketOverviewResearchHandoffSteps(routeLocale);

  return (
    <section
      data-testid="market-overview-quick-actions"
      data-market-research-flow="next-research-handoff"
      data-market-journey-step="next-research-handoff"
      className={cn(
        'min-w-0 rounded-xl border border-[color:var(--wolfy-divider)] bg-[color:var(--wolfy-surface-panel)] px-2.5 py-2 md:px-3',
        className,
      )}
    >
      <p className="text-[11px] font-medium text-[color:var(--wolfy-text-muted)]">
        {isEnglishRoute ? 'Continue from market context' : '从市场上下文继续'}
      </p>
      <p className="mt-0.5 text-xs font-semibold text-[color:var(--wolfy-text-primary)]">
        {isEnglishRoute
          ? 'Next research handoff — real routes only'
          : '下一步研究交接 — 仅真实路由'}
      </p>
      <p className="sr-only">
        {isEnglishRoute
          ? 'After observation, path, metrics, drivers, and data state — open Radar, Watchlist, Stock Research, or Scanner without inventing candidates.'
          : '在完成观察、路径、指标、驱动与数据状态后，进入雷达、观察列表、个股研究或扫描器；不编造候选。'}
      </p>
      <div className="mt-1.5 min-w-0">
        <NextResearchAction
          density="research"
          locale={researchLocale}
          compact
          data-testid="market-overview-next-research-action"
          title={isEnglishRoute ? 'Next research step' : '下一步研究'}
          steps={researchSteps}
        />
      </div>
    </section>
  );
};

const MarketRegimeSynthesisResearchBlock: React.FC<{
  view?: MarketRegimeSynthesisHeaderView;
}> = ({ view }) => {
  if (!view) {
    return null;
  }

  const supportiveEvidence = (view.supportiveEvidence?.length ? view.supportiveEvidence : view.topDrivers).slice(0, 3);
  const contradictoryEvidence = (view.contradictoryEvidence?.length ? view.contradictoryEvidence : view.counterEvidence).slice(0, 3);
  const missingEvidence = (view.missingEvidence?.length ? view.missingEvidence : view.dataGaps).slice(0, 3);
  const nextSteps = (view.researchNextSteps || []).slice(0, 3);

  return (
    <section
      data-testid="market-regime-synthesis-research-block"
      data-market-research-flow="regime-summary"
      className="mt-4 min-w-0 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-input)] p-3"
    >
      <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-medium text-[color:var(--wolfy-text-muted)]">市场状态综合</p>
          <p className="mt-1 text-sm font-semibold leading-5 text-[color:var(--wolfy-text-primary)]">{view.title}</p>
          <p className="mt-1 max-w-3xl text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">{view.summary}</p>
        </div>
        <div className="flex min-w-0 flex-wrap gap-1.5 lg:max-w-[46%] lg:justify-end">
          <TerminalChip variant={view.stateChipVariant} className="px-2 py-1 text-[10px] font-semibold">
            {view.postureLabel || view.stateChipLabel}
          </TerminalChip>
          <TerminalChip variant="neutral" className="px-2 py-1 text-[10px] font-semibold">
            <span className="text-[color:var(--wolfy-text-muted)]">置信上限</span>
            <span>{[view.confidenceCapLabel, view.confidenceCapValueText].filter(Boolean).join(' · ') || view.confidenceLabel}</span>
          </TerminalChip>
          {view.freshnessLabel ? (
            <TerminalChip variant="neutral" className="px-2 py-1 text-[10px] font-semibold">
              <span className="text-[color:var(--wolfy-text-muted)]">时效</span>
              <span>{view.freshnessLabel}</span>
            </TerminalChip>
          ) : null}
        </div>
      </div>

      {view.evidenceFamilies?.length ? (
        <div className="mt-3 min-w-0">
          <p className="text-[11px] font-medium text-[color:var(--wolfy-text-muted)]">证据家族</p>
          <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
            {view.evidenceFamilies.slice(0, 5).map((family) => (
              <TerminalChip
                key={family.key}
                variant={family.stateVariant}
                className="px-2 py-1 text-[10px] font-semibold"
              >
                <span>{family.label}</span>
                <span className="text-[color:var(--wolfy-text-muted)]">{family.stateLabel}</span>
                {family.freshnessLabel ? <span className="text-[color:var(--wolfy-text-muted)]">{family.freshnessLabel}</span> : null}
              </TerminalChip>
            ))}
          </div>
        </div>
      ) : null}

      <div className="mt-3 grid min-w-0 grid-cols-1 gap-3 xl:grid-cols-3">
        <SynthesisEvidenceColumn
          testId="market-regime-synthesis-supportive-evidence"
          title="支持证据"
          emptyLabel="等待支持证据"
          items={supportiveEvidence}
          accentClassName="text-[color:var(--state-success-text)]"
        />
        <SynthesisEvidenceColumn
          testId="market-regime-synthesis-contradictory-evidence"
          title="反证"
          emptyLabel="暂无反证"
          items={contradictoryEvidence}
          accentClassName="text-[color:var(--state-warning-text)]"
        />
        <SynthesisEvidenceColumn
          testId="market-regime-synthesis-missing-evidence"
          title="缺失证据"
          emptyLabel="暂无显式缺口"
          items={missingEvidence}
          accentClassName="text-sky-200"
        />
      </div>

      <div className="mt-3 min-w-0 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-input)] px-3 py-2.5">
        <p className="text-[11px] font-medium text-[color:var(--wolfy-text-muted)]">下一步研究</p>
        <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
          {nextSteps.length ? nextSteps.map((step) => (
            <span
              key={step.key}
              className="max-w-full rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-input)] px-2 py-1 text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]"
            >
              <span className="font-semibold text-[color:var(--wolfy-text-secondary)]">{step.label}</span>
              {step.meta ? <span className="text-[color:var(--wolfy-text-muted)]"> · {step.meta}</span> : null}
            </span>
          )) : (
            <span className="text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">继续观察同一证据家族是否延续确认</span>
          )}
        </div>
      </div>
    </section>
  );
};

const MarketOverviewDataNotesDisclosure: React.FC<{
  decisionChips: MarketOverviewDecisionChipView[];
  supportingEvidence: MarketOverviewDecisionSemanticsLineView[];
  counterEvidence: MarketOverviewDecisionSemanticsLineView[];
  missingEvidence: MarketOverviewDecisionSemanticsLineView[];
  showEvidenceBoundary: boolean;
  watchNext: MarketOverviewDecisionSemanticsLineView[];
}> = ({
  decisionChips,
  supportingEvidence,
  counterEvidence,
  missingEvidence,
  showEvidenceBoundary,
  watchNext,
}) => (
  <TerminalDisclosure
    data-testid="market-overview-evidence-disclosure"
    title="数据说明"
    summary="更新时效、证据、风险与下一步观察默认折叠"
    className="mt-3 bg-[color:var(--wolfy-surface-input)]"
  >
    <span className="sr-only">市场方向摘要</span>
    {showEvidenceBoundary || missingEvidence.length ? (
      <p data-testid="market-overview-evidence-boundary-summary" className="mt-3 text-[11px] font-semibold text-[color:var(--state-warning-text)]">
        当前市场：证据不足
      </p>
    ) : null}
    {decisionChips.length ? (
      <div data-testid="market-overview-decision-chip-details" className="mt-3 flex min-w-0 flex-wrap gap-2">
        {decisionChips.slice(0, 5).map((chip) => (
          <TerminalChip
            key={`${chip.label}-${chip.value}`}
            variant={chip.variant}
            className="px-2.5 py-1 text-[10px]"
          >
            <span className="text-[color:var(--wolfy-text-muted)]">{chip.label}</span>
            <span className="tracking-normal">{chip.value}</span>
          </TerminalChip>
        ))}
      </div>
    ) : null}
    <div className="mt-4 grid min-w-0 grid-cols-1 gap-3 xl:grid-cols-3">
      <MarketDecisionSemanticsList
        testId="market-decision-semantics-supporting-evidence"
        label="支持证据"
        emptyLabel="等待评分级支持证据"
        items={supportingEvidence}
      />
      <MarketDecisionSemanticsList
        testId="market-decision-semantics-counter-evidence"
        label="反证 / 风险"
        emptyLabel="暂无反证"
        items={counterEvidence}
      />
      <MarketDecisionSemanticsList
        testId="market-decision-semantics-data-gaps"
        label="缺失证据"
        emptyLabel="暂无显式缺口"
        items={missingEvidence}
      />
    </div>

    <div className="mt-4 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-input)] p-3">
      <p className="text-[11px] font-medium text-[color:var(--wolfy-text-muted)]">下一步观察</p>
      <div
        data-testid="market-decision-semantics-watch-next"
        className="mt-2 flex min-w-0 flex-wrap gap-1.5 text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]"
      >
        {watchNext.length ? watchNext.map((item) => (
          <span key={item.key} className="rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-input)] px-2 py-1">
            <span className="font-semibold text-[color:var(--wolfy-text-secondary)]">{item.label}</span>
            {item.meta ? <span className="text-[color:var(--wolfy-text-muted)]"> · {item.meta}</span> : null}
          </span>
        )) : <span className="text-[color:var(--wolfy-text-muted)]">等待下一项可验证信号</span>}
      </div>
    </div>
  </TerminalDisclosure>
);

const MarketDecisionSemanticsStrip: React.FC<{
  directionalSummary: MarketDirectionalSummary;
  view?: MarketOverviewDecisionSemanticsView;
  decisionText: string;
  decisionChips: MarketOverviewDecisionChipView[];
  decisionReliable: boolean;
  dataState: MarketOverviewDataStateStripView;
  regimeSynthesis?: MarketRegimeSynthesisHeaderView;
  regimeSummary?: MarketOverviewRegimeSummaryView;
  temperatureSummary: MarketOverviewTemperatureSummaryView;
  briefingSummary: MarketOverviewBriefingSummaryView;
  officialMacroRecords: OfficialMacroAuthorityRecord[];
  heroAnchors: MarketOverviewHeroAnchorView[];
  showAdminDiagnostics: boolean;
}> = ({
  directionalSummary,
  view,
  decisionText,
  decisionChips,
  decisionReliable,
  dataState,
  regimeSynthesis,
  regimeSummary,
  temperatureSummary,
  briefingSummary,
  officialMacroRecords,
  heroAnchors,
  showAdminDiagnostics,
}) => {
  const supportingEvidence = view ? [
    ...view.styleTilts.slice(0, 1),
    ...view.confirmationSignals,
  ].slice(0, 3) : [];
  const counterEvidence = view?.counterEvidence.slice(0, 3) || [];
  const missingEvidence = view?.dataGaps.slice(0, 5) || [];
  const watchNext = view ? (view.invalidationTriggers.length ? view.invalidationTriggers : view.dataGaps).slice(0, 3) : [];
  const statusSummary = view
    ? directionUsabilitySummary(view)
    : {
      label: decisionReliable ? '可参考' : '方向不可用',
      variant: decisionReliable ? 'success' as const : 'caution' as const,
      headline: decisionReliable ? decisionText : '当前暂不形成方向结论',
      detail: decisionReliable ? '等待更多支持与反证继续确认。' : '关键支持与反证尚未整理完成，先保持观察。',
    };
  const rawDebugCodes = [
    ...(view?.capReasons || []),
    ...(view?.directionReadiness?.blockingReasons || []),
    ...((view?.claimBoundaries || []).flatMap((boundary) => { const v = boundary.reasonCode || ''; return v ? [v] : []; })),
  ];
  const readinessSummary = buildOverviewDecisionReadiness({
    view,
    decisionReliable,
    dataState,
    decisionText,
  });

  return (
    <section
      data-testid="market-decision-semantics-strip"
      data-market-research-flow="research-workbench"
      className={cn(
        'relative overflow-visible border-t border-[color:var(--wolfy-divider)] bg-[color:var(--wolfy-surface-input)] p-2 md:px-3',
        view?.insufficient ? 'opacity-85' : '',
      )}
    >
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[color:var(--wolfy-divider)] to-transparent" aria-hidden="true" />
      <div className="min-w-0">
        <MarketOverviewConclusionLayer
          testId="market-overview-decision-readiness"
          summary={readinessSummary}
          statusSummary={statusSummary}
          dataState={dataState}
          directionalSummary={directionalSummary}
          regimeSummary={regimeSummary}
          view={view}
          briefingSummary={briefingSummary}
          heroAnchors={heroAnchors}
        />
        <section
          data-testid="market-overview-regime-summary-lane"
          data-market-research-flow="regime-summary"
          className="sr-only"
        >
          <MarketOverviewDirectionSummary summary={directionalSummary} />
          {regimeSummary ? (
            <div className="sr-only">
              <MarketOverviewRegimeSummaryBlock view={regimeSummary} />
            </div>
          ) : null}
            <div className="sr-only">
              <MarketRegimeSynthesisResearchBlock view={regimeSynthesis} />
            </div>
        </section>
        <MarketOverviewDataNotesDisclosure
          decisionChips={decisionChips}
          supportingEvidence={supportingEvidence}
          counterEvidence={counterEvidence}
          missingEvidence={missingEvidence}
          showEvidenceBoundary={readinessSummary.state !== 'ready'}
          watchNext={watchNext}
        />

        {showAdminDiagnostics ? (
          <TerminalDisclosure
            data-testid="market-decision-debug-details"
            title="技术细节"
            summary="管理员模式下可查看更细的方向可用性与数据状态"
            className="mt-3 bg-[color:var(--wolfy-surface-input)]"
          >
            {readinessSummary.state !== 'ready' ? (
              <MarketOverviewSetupPath testId="market-overview-setup-path" />
            ) : null}
            <Suspense fallback={<MarketDecisionDebugLoadingFallback />}>
              <LazyMarketOverviewDecisionDebugDetails
                regimeSynthesis={regimeSynthesis}
                temperatureSummary={temperatureSummary}
                briefingSummary={briefingSummary}
                dataState={dataState}
                officialMacroRecords={officialMacroRecords}
                directionReadiness={view?.directionReadiness}
                claimBoundaries={view?.claimBoundaries || []}
                rawDebugCodes={rawDebugCodes}
              />
            </Suspense>
          </TerminalDisclosure>
        ) : null}
      </div>
    </section>
  );
};

const MarketDecisionDebugLoadingFallback: React.FC = () => (
  <output
    data-testid="market-decision-debug-loading"
    aria-live="polite"
    aria-busy="true"
    className="block rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-input)] p-3"
  >
    <p className="text-[11px] font-semibold text-[color:var(--wolfy-text-secondary)]">正在加载技术细节</p>
    <p className="mt-1 text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">
      保留当前方向摘要，补充可用性与数据状态。
    </p>
  </output>
);

const MarketOverviewCategoryControls: React.FC<{
  categoryTabs: MarketOverviewCategoryTabView[];
  activeCategory: MarketOverviewTab;
  onCategoryChange: (tab: MarketOverviewTab) => void;
  exportLabel: string;
  exportDisabled: boolean;
  onExportSummary: () => void;
}> = ({ categoryTabs, activeCategory, onCategoryChange, exportLabel, exportDisabled, onExportSummary }) => (
  <div data-market-research-flow="controls">
    <div
      data-testid="market-overview-category-tabs"
      data-selector-position="static-safe"
      data-mobile-order="controls"
      className="flex w-full min-w-0 flex-col gap-1 overflow-visible rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-input)] p-1 md:flex-row md:items-center md:justify-between"
    >
      <div className="flex w-full min-w-0 items-center gap-2 overflow-visible md:w-auto">
        <span className="shrink-0 rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-input)] px-2 py-0.5 text-[10px] font-semibold text-[color:var(--wolfy-text-muted)]">
          筛选
        </span>
        <div className="ui-scroll-x-quiet min-w-0 max-w-full overflow-x-auto overscroll-x-contain p-0.5 scroll-px-1">
          <div className="flex w-max gap-1.5">
            {categoryTabs.map((tab) => (
              <button
                key={tab.key}
                type="button"
                aria-pressed={activeCategory === tab.key}
                className={`ui-truncate scroll-m-3 shrink-0 whitespace-nowrap rounded-md px-2.5 py-1 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--wolfy-accent-focus)] ${
                  activeCategory === tab.key
                    ? 'bg-[color:var(--wolfy-surface-input)] text-[color:var(--wolfy-text-primary)] shadow-sm'
                    : 'bg-transparent text-[color:var(--wolfy-text-muted)] hover:text-[color:var(--wolfy-text-secondary)]'
                }`}
                onClick={() => onCategoryChange(tab.key)}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>
      <button
        type="button"
        data-testid="market-overview-export-summary"
        aria-label={exportLabel}
        aria-live="polite"
        disabled={exportDisabled}
        className="scroll-m-3 w-fit rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-input)] px-2.5 py-1 text-xs font-semibold text-[color:var(--wolfy-text-muted)] transition hover:bg-[color:var(--wolfy-surface-input)] hover:text-[color:var(--wolfy-text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--wolfy-accent-focus)] disabled:cursor-not-allowed disabled:border-[color:var(--wolfy-border-subtle)] disabled:bg-[color:var(--wolfy-surface-input)] disabled:text-[color:var(--wolfy-text-muted)] disabled:hover:bg-[color:var(--wolfy-surface-input)] disabled:hover:text-[color:var(--wolfy-text-muted)]"
        onClick={onExportSummary}
      >
        {exportLabel}
      </button>
    </div>
  </div>
);

export const MarketOverviewWorkbenchTopSurface: React.FC<MarketOverviewWorkbenchTopSurfaceProps> = ({
  heading,
  directionalSummary,
  regimeSynthesis,
  regimeSummary,
  decisionText,
  decisionChips,
  decisionReliable,
  decisionSemantics,
  dataState,
  temperatureSummary,
  briefingSummary,
  officialMacroRecords,
  categoryTabs,
  activeCategory,
  onCategoryChange,
  exportLabel,
  exportDisabled,
  onExportSummary,
  heroAnchors,
  showAdminDiagnostics = false,
}) => {
  return (
    <section data-testid="market-overview-pulse-header" className="flex w-full min-w-0 flex-col gap-4">
      {heading}
      <section data-testid="market-overview-market-monitor" className="flex w-full min-w-0 flex-col gap-4">
        <ConsoleBoard data-testid="market-overview-primary-board">
          <div data-testid="market-overview-top-stack" className="flex w-full min-w-0 flex-col">
            <MarketDecisionSemanticsStrip
              directionalSummary={directionalSummary}
              view={decisionSemantics}
              decisionText={decisionText}
              decisionChips={decisionChips}
              decisionReliable={decisionReliable}
              dataState={dataState}
              regimeSynthesis={regimeSynthesis}
              regimeSummary={regimeSummary}
              temperatureSummary={temperatureSummary}
              briefingSummary={briefingSummary}
              officialMacroRecords={officialMacroRecords}
              heroAnchors={heroAnchors}
              showAdminDiagnostics={showAdminDiagnostics}
            />
            <div className="border-t border-[color:var(--wolfy-divider)] p-1.5 md:px-2">
              <MarketOverviewCategoryControls
                categoryTabs={categoryTabs}
                activeCategory={activeCategory}
                onCategoryChange={onCategoryChange}
                exportLabel={exportLabel}
                exportDisabled={exportDisabled}
                onExportSummary={onExportSummary}
              />
            </div>
            <div data-market-research-flow="pulse" className="border-t border-[color:var(--wolfy-divider)]">
              <CrossAssetHeroRibbon anchors={heroAnchors} />
            </div>
            <p className="sr-only">ETF 资金流指标 · 机构压力指标 · 行业广度指标</p>
          </div>
        </ConsoleBoard>
      </section>
    </section>
  );
};
