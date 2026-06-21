import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { ApiErrorAlert } from '../components/common/ApiErrorAlert';
import {
  ConsoleBoard,
  ConsoleContextRail,
  ConsoleStatusStrip,
  MetricStrip,
  ResearchConsoleShell,
  WolfyCommandBar,
} from '../components/linear/LinearPrimitives';
import { ConsumerWorkspacePageShell, ConsumerWorkspaceScope } from '../components/layout/ConsumerWorkspaceShell';
import { TerminalButton, TerminalChip, TerminalEmptyState } from '../components/terminal/TerminalPrimitives';
import { createParsedApiError, getParsedApiError, type ParsedApiError } from '../api/error';
import {
  marketDecisionCockpitApi,
  type MarketDecisionCockpitDriverScore,
  type MarketDecisionCockpitResponse,
} from '../api/marketDecisionCockpit';
import { scenarioLabApi, type ScenarioLabResponse } from '../api/scenarioLab';
import { useI18n } from '../contexts/UiLanguageContext';
import {
  getConsumerStatusLabel,
  mapConsumerStatusText,
  normalizeConsumerStatusToken,
} from '../utils/consumerStatusLabels';
import { buildLocalizedPath, parseLocaleFromPathname } from '../utils/localeRouting';
import { sanitizeUserFacingDataIssue } from '../utils/userFacingDataIssues';
import {
  RoughBulletList,
  RoughKeyValueRows,
  RoughScoreRows,
  RoughSectionCard,
  RoughSurfaceIntro,
} from './roughShellShared';

type Locale = 'zh' | 'en';

type ScenarioPreset = {
  key: string;
  scenarioName: string;
  label: Record<Locale, string>;
  summary: Record<Locale, string>;
};

const SCENARIO_PRESETS: ScenarioPreset[] = [
  {
    key: 'volatilitySpike',
    scenarioName: 'volatilitySpike',
    label: { zh: '波动冲击', en: 'Volatility shock' },
    summary: {
      zh: '观察波动结构突然转弱时，基准状态会如何退化。',
      en: 'Observe how the current regime degrades if volatility structure weakens abruptly.',
    },
  },
  {
    key: 'breadthBreakdown',
    scenarioName: 'breadthBreakdown',
    label: { zh: '广度失守', en: 'Breadth breakdown' },
    summary: {
      zh: '检查广度参与回落后，研究队列语境是否需要收缩。',
      en: 'Check whether the research frame contracts once breadth participation fades.',
    },
  },
  {
    key: 'liquidityStress',
    scenarioName: 'liquidityStress',
    label: { zh: '流动性压力', en: 'Liquidity stress' },
    summary: {
      zh: '观察流动性与跨资产风险同步走弱时的研究限制。',
      en: 'Observe the evidence limits when liquidity and cross-asset risk deteriorate together.',
    },
  },
  {
    key: 'gammaUnavailable',
    scenarioName: 'gammaUnavailable',
    label: { zh: 'Gamma 缺口', en: 'Gamma gap' },
    summary: {
      zh: '验证 Gamma 证据缺口下，情景结论应保持受限。',
      en: 'Verify that scenario outputs stay capped while gamma evidence is missing.',
    },
  },
];

const DRIVER_LABELS: Record<string, Record<Locale, string>> = {
  dealerGamma: { zh: 'Gamma 观察', en: 'Gamma observation' },
  breadthParticipation: { zh: '广度参与', en: 'Breadth participation' },
  volatilityStructure: { zh: '波动结构', en: 'Volatility structure' },
  ratesDollar: { zh: '利率与美元', en: 'Rates and USD' },
  liquidityCredit: { zh: '流动性与信用', en: 'Liquidity and credit' },
  crossAssetRisk: { zh: '跨资产风险', en: 'Cross-asset risk' },
  sectorThemeRotation: { zh: '主题轮动', en: 'Theme rotation' },
  eventCatalyst: { zh: '事件催化', en: 'Event catalyst' },
};

const SCENARIO_UNAVAILABLE_COPY: Record<Locale, {
  stateTitle: string;
  stateBody: string;
  nextStep: string;
  boundaryNote: string;
  summaryFallback: string;
  evidenceFallback: string;
  primaryCta: string;
  secondaryCta: string;
}> = {
  zh: {
    stateTitle: '情景待更新',
    stateBody: '基准待确认，暂不展开输出。',
    nextStep: '待补证据：市场框架、驱动证据、数据新鲜度。',
    boundaryNote: '研究观察',
    summaryFallback: '情景待更新',
    evidenceFallback: '待补证据：市场框架、驱动证据、数据新鲜度。',
    primaryCta: '查看市场概览',
    secondaryCta: '返回研究雷达',
  },
  en: {
    stateTitle: 'Scenario pending',
    stateBody: 'Baseline pending; output stays compact.',
    nextStep: 'Next evidence: market frame, driver evidence, freshness.',
    boundaryNote: 'Research observation',
    summaryFallback: 'Scenario pending',
    evidenceFallback: 'Next evidence: market frame, driver evidence, freshness.',
    primaryCta: 'Open Market Overview',
    secondaryCta: 'Back to Research Radar',
  },
};

const FALLBACK_BASELINE_READINESS_SUMMARY = {
  baselineSnapshot: '基线证据待补齐',
  marketFrame: '市场框架待补齐',
  driverInputs: '驱动证据待补齐',
  boundary: '仅观察 / 非决策级',
} as const;

function presetForKey(raw: string | null): ScenarioPreset {
  return SCENARIO_PRESETS.find((item) => item.key === raw || item.scenarioName === raw) ?? SCENARIO_PRESETS[0];
}

function humanizeToken(value: string | null | undefined): string {
  if (!value) {
    return '--';
  }
  const safe = getConsumerStatusLabel(value, 'zh');
  if (safe) {
    return safe;
  }
  return value.replace(/([a-z])([A-Z])/g, '$1 $2').replace(/[_-]+/g, ' ');
}

function labelForDriver(key: string, locale: Locale): string {
  return DRIVER_LABELS[key]?.[locale] ?? humanizeToken(key);
}

function scenarioDriverEvidenceStateLabel(value: string | null | undefined, locale: Locale): string {
  const normalized = normalizeConsumerStatusToken(value);
  if (normalized === 'score_grade') {
    return locale === 'en' ? 'Evidence prepared' : '证据已整理';
  }
  return mapConsumerStatusText(value, locale);
}

function sanitizeScenarioNarrativeText(value: string | null | undefined, locale: Locale): string {
  const raw = String(value || '').trim();
  if (!raw) {
    return '';
  }

  const mapped = mapConsumerStatusText(raw, locale);
  if (mapped !== raw) {
    return mapped;
  }

  const sanitized = sanitizeUserFacingDataIssue(raw, locale);
  if (sanitized !== raw) {
    return sanitized;
  }

  return raw;
}

function sanitizeScenarioNarrativeList(values: string[] | null | undefined, locale: Locale): string[] {
  const seen = new Set<string>();
  const next: string[] = [];

  for (const value of values ?? []) {
    const safe = sanitizeScenarioNarrativeText(value, locale);
    if (!safe || seen.has(safe)) continue;
    seen.add(safe);
    next.push(safe);
  }

  return next;
}

function statusTone(value: string | null | undefined): 'success' | 'caution' | 'danger' | 'info' {
  const normalized = String(value || '').toLowerCase();
  if (['high', 'riskon', 'available', 'complete'].includes(normalized)) return 'success';
  if (['medium', 'mixed', 'partial', 'rangebound'].includes(normalized)) return 'caution';
  if (['low', 'unavailable', 'riskoff', 'downsideaccelerationrisk', 'lowconfidence'].includes(normalized)) return 'danger';
  return 'info';
}

function localizedRegime(value: string | null | undefined, locale: Locale): string {
  switch (String(value || '').toLowerCase()) {
    case 'riskon':
    case 'risk_on':
      return locale === 'en' ? 'Risk-on observation' : '风险偏好观察';
    case 'riskoff':
    case 'risk_off':
      return locale === 'en' ? 'Risk-off observation' : '风险规避观察';
    case 'mixed':
      return locale === 'en' ? 'Mixed observation' : '混合观察';
    case 'rangebound':
    case 'range_bound':
      return locale === 'en' ? 'Range-bound observation' : '区间观察';
    case 'downsideaccelerationrisk':
    case 'downside_acceleration_risk':
      return locale === 'en' ? 'Downside acceleration risk' : '下行加速风险';
    case 'lowconfidence':
    case 'low_confidence':
      return locale === 'en' ? 'Low-confidence observation' : '低置信观察';
    default:
      return value || '--';
  }
}

function localizedConfidence(value: string | null | undefined, locale: Locale): string {
  switch (String(value || '').toLowerCase()) {
    case 'high':
      return locale === 'en' ? 'High' : '高';
    case 'medium':
      return locale === 'en' ? 'Medium' : '中';
    case 'low':
      return locale === 'en' ? 'Low' : '低';
    default:
      return value || '--';
  }
}

function formatDelta(value: number | null | undefined): string {
  const numeric = Number(value ?? 0);
  if (!Number.isFinite(numeric)) {
    return '--';
  }
  return `${numeric > 0 ? '+' : ''}${numeric}`;
}

function buildScenarioBaseRegime(cockpit: MarketDecisionCockpitResponse | null) {
  const decision = cockpit?.marketRegimeDecision;
  const driverScores = Object.fromEntries(
    Object.entries(decision?.driverScores ?? {}).map(([key, value]) => {
      const typed = (value ?? {}) as MarketDecisionCockpitDriverScore;
      return [key, {
        score: typed.score ?? 0,
        evidenceState: typed.evidenceState ?? 'unavailable',
      }];
    }),
  );

  return {
    regime: decision?.regime ?? null,
    confidence: decision?.confidence ?? null,
    confidenceScore: decision?.confidenceScore ?? null,
    driverScores,
  };
}

export default function ScenarioLabPage() {
  const { language } = useI18n();
  const locale: Locale = language === 'en' ? 'en' : 'zh';
  const location = useLocation();
  const routeLocale = parseLocaleFromPathname(location.pathname);
  const [searchParams] = useSearchParams();
  const localize = useCallback((path: string) => (routeLocale ? buildLocalizedPath(path, routeLocale) : path), [routeLocale]);

  const initialPreset = presetForKey(searchParams.get('scenario'));
  const [selectedPreset, setSelectedPreset] = useState<ScenarioPreset>(initialPreset);
  const [cockpit, setCockpit] = useState<MarketDecisionCockpitResponse | null>(null);
  const [scenarioResult, setScenarioResult] = useState<ScenarioLabResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);

  useEffect(() => {
    setSelectedPreset(initialPreset);
  }, [initialPreset]);

  const load = useCallback(async (preset: ScenarioPreset) => {
    setLoading(true);
    setError(null);
    try {
      const cockpitPayload = await marketDecisionCockpitApi.getDecisionCockpit();
      setCockpit(cockpitPayload);
      const scenarioPayload = await scenarioLabApi.runScenarioLab({
        baseRegime: buildScenarioBaseRegime(cockpitPayload),
        scenarioName: preset.scenarioName,
      });
      setScenarioResult(scenarioPayload);
    } catch (err) {
      setError(getParsedApiError(err) || createParsedApiError({
        title: locale === 'en' ? 'Scenario lab pending' : '情景实验室待更新',
        message: locale === 'en'
          ? 'Please retry after the market context and scenario contract respond again.'
          : '请在市场上下文与情景契约恢复后重试。',
      }));
    } finally {
      setLoading(false);
    }
  }, [locale]);

  useEffect(() => {
    void load(selectedPreset);
  }, [load, selectedPreset]);

  const changedDriverRows = useMemo(
    () => Object.entries(scenarioResult?.driverDeltas ?? {})
      .filter(([, value]) => Number(value) !== 0)
      .sort(([, left], [, right]) => Math.abs(right) - Math.abs(left))
      .map(([key, value]) => ({
        key,
        label: labelForDriver(key, locale),
        value: formatDelta(value),
        badge: {
          label: value > 0
            ? (locale === 'en' ? 'Strengthens' : '增强')
            : (locale === 'en' ? 'Weakens' : '转弱'),
          variant: value > 0 ? 'success' as const : 'danger' as const,
        },
      })),
    [scenarioResult?.driverDeltas, locale],
  );
  const baselineReadinessSummary = scenarioResult?.baselineReadinessSummary ?? FALLBACK_BASELINE_READINESS_SUMMARY;

  const baseDriverRows = useMemo(
    () => Object.entries(cockpit?.marketRegimeDecision?.driverScores ?? {})
      .map(([key, value]) => {
        const typed = (value ?? {}) as MarketDecisionCockpitDriverScore;
        return {
          key,
          label: labelForDriver(key, locale),
          value: typed.score ?? '--',
          meta: typed.evidenceState ? scenarioDriverEvidenceStateLabel(typed.evidenceState, locale) : undefined,
        };
      }),
    [cockpit?.marketRegimeDecision?.driverScores, locale],
  );

  const scenarioUnavailable = scenarioResult?.scenarioRegime.status === 'unavailable' || !scenarioResult?.changedDrivers.length;
  const scenarioUnavailableCopy = SCENARIO_UNAVAILABLE_COPY[locale];
  const firstReadDriverText = scenarioUnavailable
    ? (locale === 'en' ? 'Scenario pending' : '情景待更新')
    : changedDriverRows.slice(0, 2).map((item) => `${item.label} ${item.value}`).join(' / ');
  const firstReadBoundaryText = scenarioUnavailable
    ? (locale === 'en' ? 'Baseline pending' : '基准待确认')
    : [
      localizedConfidence(scenarioResult?.baseRegime.confidence, locale),
      localizedConfidence(scenarioResult?.scenarioRegime.confidence, locale),
    ].filter(Boolean).join(' -> ');
  const firstReadNextEvidence = scenarioUnavailable
    ? (locale === 'en' ? 'Market frame, driver evidence, freshness' : '市场框架、驱动证据、数据新鲜度')
    : (
      sanitizeScenarioNarrativeList([
        ...(scenarioResult?.whatWouldConfirm ?? []),
        ...(scenarioResult?.evidenceLimits ?? []),
      ], locale)[0] ?? (locale === 'en' ? 'Continue evidence review' : '继续补充确认线索')
    );
  const readinessLabels = scenarioResult?.readinessLabels ?? [];
  const scenarioUnavailableActions = (
    <div className="flex flex-col gap-2 sm:flex-row">
      <Link
        to={localize('/market-overview')}
        className="inline-flex items-center justify-center rounded-md border border-[color:var(--wolfy-accent)] bg-[var(--wolfy-accent)] px-3 py-1.5 text-xs font-medium text-[#f7f8ff] transition-colors hover:bg-[#6f79dc]"
      >
        {scenarioUnavailableCopy.primaryCta}
      </Link>
      <Link
        to={localize('/research/radar')}
        className="inline-flex items-center justify-center rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)]"
      >
        {scenarioUnavailableCopy.secondaryCta}
      </Link>
    </div>
  );
  const selectedLabel = selectedPreset.label[locale];

  return (
    <ConsumerWorkspaceScope className="flex min-h-0 flex-1">
      <ConsumerWorkspacePageShell className="flex min-h-0 flex-1 flex-col gap-4 md:gap-6">
        <ResearchConsoleShell
          className="flex-1"
          command={(
            <WolfyCommandBar
              leading={<span className="text-xs text-[color:var(--wolfy-text-muted)]">{locale === 'en' ? 'Scenario Lab / Research Surface' : '情景实验室 / 研究面板'}</span>}
              trailing={(
                <div className="flex flex-wrap items-center gap-2">
                  <Link
                    to={localize('/market/decision-cockpit')}
                    className="rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)]"
                  >
                    {locale === 'en' ? 'Decision cockpit' : '决策驾驶舱'}
                  </Link>
                  <Link
                    to={localize('/research/radar')}
                    className="rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)]"
                  >
                    {locale === 'en' ? 'Research radar' : '研究雷达'}
                  </Link>
                  <TerminalButton variant="compact" onClick={() => void load(selectedPreset)}>
                    {locale === 'en' ? 'Refresh' : '刷新'}
                  </TerminalButton>
                </div>
              )}
            >
              <div className="text-xs text-[color:var(--wolfy-text-secondary)]">
                {locale === 'en'
                  ? 'Use bounded market scenarios to compare how the current research frame would degrade or stabilize.'
                  : '用有边界的市场情景，对照当前研究语境会如何退化或稳定。'}
              </div>
            </WolfyCommandBar>
          )}
          rail={(
            <ConsoleContextRail className="flex flex-col gap-3 p-3">
              <RoughSectionCard eyebrow={locale === 'en' ? 'Preset context' : '预设情景'} title={selectedLabel}>
                <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">{selectedPreset.summary[locale]}</p>
              </RoughSectionCard>
              <RoughSectionCard eyebrow={locale === 'en' ? 'Evidence limits' : '证据限制'} title={locale === 'en' ? 'Keep the surface bounded' : '保持边界'}>
                <RoughBulletList
                  items={scenarioUnavailable
                    ? [scenarioUnavailableCopy.evidenceFallback, scenarioUnavailableCopy.boundaryNote]
                    : sanitizeScenarioNarrativeList(scenarioResult?.evidenceLimits ?? [], locale)}
                  emptyText={locale === 'en' ? 'No explicit evidence limit is attached.' : '当前没有额外证据限制。'}
                />
              </RoughSectionCard>
              <RoughSectionCard eyebrow={locale === 'en' ? 'Disclosure' : '披露'} title={locale === 'en' ? 'Observation-only note' : '观察型说明'}>
                <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
                  {sanitizeScenarioNarrativeText(
                    scenarioResult?.noAdviceDisclosure || (locale === 'en' ? 'Research planning only.' : '仅供研究规划观察。'),
                    locale,
                  )}
                </p>
              </RoughSectionCard>
            </ConsoleContextRail>
          )}
        >
          <ConsoleBoard className="min-h-0" data-testid="scenario-lab-page">
            <RoughSurfaceIntro
              eyebrow={locale === 'en' ? 'Scenario Lab' : '情景实验室'}
              title={locale === 'en' ? 'Research scenario workbench' : '研究情景工作台'}
              description={locale === 'en'
                ? 'Apply bounded scenario shocks to the current market context.'
                : '对当前市场语境叠加有边界的情景冲击。'}
            />
            {error ? (
              <div className="p-4 md:p-5">
                <ApiErrorAlert error={error} actionLabel={locale === 'en' ? 'Retry' : '重试'} onAction={() => void load(selectedPreset)} />
              </div>
            ) : null}
            {loading && !scenarioResult ? (
              <div className="p-4 md:p-5">
                <TerminalEmptyState title={locale === 'en' ? 'Loading scenario workbench' : '正在载入情景工作台'}>
                  {locale === 'en'
                    ? 'Loading scenario output.'
                    : '正在载入情景输出。'}
                </TerminalEmptyState>
              </div>
            ) : null}
            {scenarioResult ? (
              <>
                <section
                  aria-label={locale === 'en' ? 'Scenario summary' : '情景摘要'}
                  className="p-3"
                  data-testid="scenario-lab-first-read-summary"
                >
                  <RoughSectionCard eyebrow={locale === 'en' ? 'First read' : '首读'} title={locale === 'en' ? 'Scenario summary' : '情景摘要'}>
                    <div className="grid gap-2 text-xs md:grid-cols-5">
                      <div className="rounded-xl border border-[color:var(--wolfy-divider)] bg-black/10 px-3 py-2">
                        <div className="text-[color:var(--wolfy-text-muted)]">{locale === 'en' ? 'Current frame' : '当前框架'}</div>
                        <div className="mt-1 font-semibold text-[color:var(--wolfy-text-primary)]">
                          {localizedRegime(scenarioResult.baseRegime.regime, locale)}
                        </div>
                        <div className="mt-0.5 text-[color:var(--wolfy-text-muted)]">
                          {localizedConfidence(scenarioResult.baseRegime.confidence, locale)}
                        </div>
                      </div>
                      <div className="rounded-xl border border-[color:var(--wolfy-divider)] bg-black/10 px-3 py-2">
                        <div className="text-[color:var(--wolfy-text-muted)]">{locale === 'en' ? 'Scenario' : '情景摘要'}</div>
                        <div className="mt-1 font-semibold text-[color:var(--wolfy-text-primary)]">{selectedLabel}</div>
                        <div className="mt-0.5 text-[color:var(--wolfy-text-muted)]">
                          {scenarioUnavailable ? scenarioUnavailableCopy.summaryFallback : localizedRegime(scenarioResult.scenarioRegime.regime, locale)}
                        </div>
                      </div>
                      <div className="rounded-xl border border-[color:var(--wolfy-divider)] bg-black/10 px-3 py-2">
                        <div className="text-[color:var(--wolfy-text-muted)]">{locale === 'en' ? 'Driver shifts' : '驱动变化'}</div>
                        <div className="mt-1 font-semibold text-[color:var(--wolfy-text-primary)]">
                          {firstReadDriverText || (locale === 'en' ? 'Scenario pending' : '情景待更新')}
                        </div>
                      </div>
                      <div className="rounded-xl border border-[color:var(--wolfy-divider)] bg-black/10 px-3 py-2">
                        <div className="text-[color:var(--wolfy-text-muted)]">{locale === 'en' ? 'Evidence boundary' : '证据边界'}</div>
                        <div className="mt-1 flex flex-wrap gap-1">
                          <TerminalChip variant={scenarioUnavailable ? 'caution' : 'info'}>
                            {firstReadBoundaryText || (locale === 'en' ? 'Baseline pending' : '基准待确认')}
                          </TerminalChip>
                          {readinessLabels.slice(0, 3).map((label) => (
                            <TerminalChip key={label} variant={label === '基准可用' || label === '当前框架可用' ? 'success' : 'caution'}>
                              {label}
                            </TerminalChip>
                          ))}
                          <TerminalChip variant="info">
                            {formatDelta(scenarioResult.confidenceDelta)}
                          </TerminalChip>
                        </div>
                        <div className="mt-2 grid gap-1 text-[11px] leading-5 text-[color:var(--wolfy-text-muted)] sm:grid-cols-2">
                          <div>{locale === 'en' ? 'Baseline snapshot' : '基线快照'}：{baselineReadinessSummary.baselineSnapshot}</div>
                          <div>{locale === 'en' ? 'Market frame' : '市场框架'}：{baselineReadinessSummary.marketFrame}</div>
                          <div>{locale === 'en' ? 'Driver evidence' : '驱动证据'}：{baselineReadinessSummary.driverInputs}</div>
                          <div>{locale === 'en' ? 'Boundary' : '边界'}：{baselineReadinessSummary.boundary}</div>
                        </div>
                      </div>
                      <div className="rounded-xl border border-[color:var(--wolfy-divider)] bg-black/10 px-3 py-2">
                        <div className="text-[color:var(--wolfy-text-muted)]">{locale === 'en' ? 'Next evidence' : '待补证据'}</div>
                        <div className="mt-1 font-semibold text-[color:var(--wolfy-text-primary)]">{firstReadNextEvidence}</div>
                      </div>
                    </div>
                  </RoughSectionCard>
                </section>
                <ConsoleStatusStrip
                  items={[
                    {
                      label: locale === 'en' ? 'Preset' : '当前预设',
                      value: selectedLabel,
                    },
                    {
                      label: locale === 'en' ? 'Base confidence' : '基准置信',
                      value: localizedConfidence(scenarioResult.baseRegime.confidence, locale),
                    },
                    {
                      label: locale === 'en' ? 'Scenario confidence' : '情景置信',
                      value: localizedConfidence(scenarioResult.scenarioRegime.confidence, locale),
                    },
                  ]}
                />
                <MetricStrip
                  items={[
                    {
                      key: 'mode',
                      label: locale === 'en' ? 'Mode' : '模式',
                      value: locale === 'en' ? 'Observation only' : '仅观察',
                    },
                    {
                      key: 'grade',
                      label: locale === 'en' ? 'Decision grade' : '判断等级',
                      value: locale === 'en' ? 'Non-decision' : '非决策级',
                    },
                    {
                      key: 'delta',
                      label: locale === 'en' ? 'Confidence delta' : '置信变化',
                      value: formatDelta(scenarioResult.confidenceDelta),
                    },
                  ]}
                />
                <div className="grid gap-3 p-3 md:grid-cols-2">
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Scenario presets' : '情景预设'} title={locale === 'en' ? 'Choose a bounded frame' : '选择一个有边界的框架'}>
                    <div className="flex flex-wrap gap-2">
                      {SCENARIO_PRESETS.map((preset) => {
                        const active = preset.key === selectedPreset.key;
                        return (
                          <TerminalButton
                            key={preset.key}
                            variant={active ? 'secondary' : 'compact'}
                            onClick={() => setSelectedPreset(preset)}
                            aria-pressed={active}
                          >
                            {preset.label[locale]}
                          </TerminalButton>
                        );
                      })}
                    </div>
                    <div className="mt-3 text-xs leading-6 text-[color:var(--wolfy-text-muted)]">
                      {selectedPreset.summary[locale]}
                    </div>
                  </RoughSectionCard>
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Base context' : '基准状态'} title={locale === 'en' ? 'Current market frame' : '当前市场框架'}>
                    <RoughKeyValueRows
                      emptyText={locale === 'en' ? 'No base context available yet.' : '暂无基准状态。'}
                      rows={[
                        {
                          key: 'regime',
                          label: locale === 'en' ? 'Base regime' : '基准状态',
                          value: localizedRegime(scenarioResult.baseRegime.regime, locale),
                        },
                        {
                          key: 'confidence',
                          label: locale === 'en' ? 'Confidence' : '置信',
                          value: localizedConfidence(scenarioResult.baseRegime.confidence, locale),
                          detail: scenarioResult.baseRegime.confidenceScore != null
                            ? `${locale === 'en' ? 'Score' : '分值'} ${scenarioResult.baseRegime.confidenceScore}`
                            : undefined,
                        },
                        {
                          key: 'scenario',
                          label: locale === 'en' ? 'Selected scenario' : '当前情景',
                          value: selectedLabel,
                        },
                      ]}
                    />
                  </RoughSectionCard>
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Scenario output' : '情景输出'} title={scenarioUnavailable
                    ? (locale === 'en' ? 'Scenario pending' : '情景待更新')
                    : (locale === 'en' ? 'Projected research frame' : '情景后的研究框架')}>
                    {scenarioUnavailable ? (
                      <TerminalEmptyState
                        title={scenarioUnavailableCopy.stateTitle}
                        action={scenarioUnavailableActions}
                        className="min-h-0 items-start"
                        data-testid="scenario-lab-unavailable-state"
                      >
                        <div className="space-y-0.5">
                          <p>{scenarioUnavailableCopy.stateBody}</p>
                          <p>{scenarioUnavailableCopy.nextStep}</p>
                          <p>{scenarioUnavailableCopy.boundaryNote}</p>
                        </div>
                      </TerminalEmptyState>
                    ) : (
                      <RoughKeyValueRows
                        emptyText={locale === 'en' ? 'No scenario output available yet.' : '暂无情景输出。'}
                        rows={[
                          {
                            key: 'scenario-regime',
                            label: locale === 'en' ? 'Scenario regime' : '情景状态',
                            value: localizedRegime(scenarioResult.scenarioRegime.regime, locale),
                          },
                          {
                            key: 'scenario-confidence',
                            label: locale === 'en' ? 'Scenario confidence' : '情景置信',
                            value: localizedConfidence(scenarioResult.scenarioRegime.confidence, locale),
                            detail: scenarioResult.scenarioRegime.confidenceScore != null
                              ? `${locale === 'en' ? 'Score' : '分值'} ${scenarioResult.scenarioRegime.confidenceScore}`
                              : undefined,
                          },
                          {
                            key: 'changed-drivers',
                            label: locale === 'en' ? 'Changed drivers' : '变化驱动',
                            value: scenarioResult.changedDrivers.length,
                          },
                        ]}
                      />
                    )}
                  </RoughSectionCard>
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Driver deltas' : '驱动变化'} title={locale === 'en' ? 'Where the frame moves' : '框架如何变化'}>
                    <RoughScoreRows
                      items={changedDriverRows}
                      emptyText={locale === 'en'
                        ? 'No bounded driver delta is available for this scenario.'
                        : '该情景当前没有可展示的驱动变化。'}
                    />
                  </RoughSectionCard>
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Generated scenario output' : '生成输出'} title={locale === 'en' ? 'What this scenario says' : '该情景下的观察'}>
                    <RoughBulletList
                      items={scenarioUnavailable
                        ? [scenarioUnavailableCopy.summaryFallback]
                        : sanitizeScenarioNarrativeList(scenarioResult.scenarioSummary ?? [], locale)}
                      emptyText={locale === 'en' ? 'No scenario summary is available.' : '当前没有可展示的情景摘要。'}
                    />
                  </RoughSectionCard>
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Evidence and risk context' : '证据与风险语境'} title={locale === 'en' ? 'What confirms or invalidates it' : '确认线索与失效信号'}>
                    <div className="space-y-3">
                      <div>
                        <div className="mb-2 text-xs text-[color:var(--wolfy-text-muted)]">{locale === 'en' ? 'What would confirm' : '哪些线索会继续确认'}</div>
                        <RoughBulletList
                          items={sanitizeScenarioNarrativeList(scenarioResult.whatWouldConfirm ?? [], locale)}
                          emptyText={locale === 'en' ? 'No explicit confirm path is attached.' : '当前没有额外确认条件。'}
                        />
                      </div>
                      <div>
                        <div className="mb-2 text-xs text-[color:var(--wolfy-text-muted)]">{locale === 'en' ? 'What would invalidate' : '哪些信号会削弱该情景'}</div>
                        <RoughBulletList
                          items={sanitizeScenarioNarrativeList(scenarioResult.whatWouldInvalidate ?? [], locale)}
                          emptyText={locale === 'en' ? 'No invalidation path is attached.' : '当前没有额外失效条件。'}
                        />
                      </div>
                    </div>
                  </RoughSectionCard>
                </div>
                <div className="grid gap-3 border-t border-[color:var(--wolfy-divider)] p-3 md:grid-cols-2">
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Base evidence scores' : '基准评分'} title={locale === 'en' ? 'Context inherited from cockpit' : '继承自驾驶舱的语境'}>
                    <RoughScoreRows
                      items={baseDriverRows}
                      emptyText={locale === 'en' ? 'No base driver score is available.' : '当前没有基准驱动评分。'}
                    />
                  </RoughSectionCard>
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Surface boundaries' : '页面边界'} title={locale === 'en' ? 'Keep it consumer-safe' : '保持观察边界'}>
                    <div className="flex flex-wrap gap-2">
                      <TerminalChip variant="info">{locale === 'en' ? 'Observation only' : '仅观察'}</TerminalChip>
                      <TerminalChip variant="info">{locale === 'en' ? 'No external action' : '不触发外部动作'}</TerminalChip>
                      {readinessLabels.slice(0, 5).map((label) => (
                        <TerminalChip key={label} variant={label === '基准可用' || label === '当前框架可用' ? 'success' : 'caution'}>
                          {label}
                        </TerminalChip>
                      ))}
                      <TerminalChip variant={statusTone(scenarioResult.scenarioRegime.status || scenarioResult.scenarioRegime.confidence)}>
                        {scenarioResult.scenarioRegime.status
                          ? mapConsumerStatusText(scenarioResult.scenarioRegime.status, locale)
                          : localizedConfidence(scenarioResult.scenarioRegime.confidence, locale)}
                      </TerminalChip>
                    </div>
                    <div className="mt-3 text-xs leading-6 text-[color:var(--wolfy-text-muted)]">
                      {locale === 'en'
                        ? 'Observation boundaries apply.'
                        : '观察边界适用。'}
                    </div>
                  </RoughSectionCard>
                </div>
              </>
            ) : null}
          </ConsoleBoard>
        </ResearchConsoleShell>
      </ConsumerWorkspacePageShell>
    </ConsumerWorkspaceScope>
  );
}
