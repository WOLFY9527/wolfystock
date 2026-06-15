import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
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
import { StatusBadge } from '../components/ui/StatusBadge';
import { TerminalButton, TerminalChip, TerminalEmptyState } from '../components/terminal/TerminalPrimitives';
import { createParsedApiError, getParsedApiError, type ParsedApiError } from '../api/error';
import { marketDecisionCockpitApi, type MarketDecisionCockpitResponse } from '../api/marketDecisionCockpit';
import { useI18n } from '../contexts/UiLanguageContext';
import { buildLocalizedPath, parseLocaleFromPathname } from '../utils/localeRouting';
import { formatDateTime } from '../utils/format';
import {
  RoughBulletList,
  RoughKeyValueRows,
  RoughScoreRows,
  RoughSectionCard,
  RoughSurfaceIntro,
} from './roughShellShared';

const DRIVER_LABELS = {
  dealerGamma: { zh: 'Gamma 观察', en: 'Gamma observation' },
  breadthParticipation: { zh: '广度参与', en: 'Breadth participation' },
  volatilityStructure: { zh: '波动结构', en: 'Volatility structure' },
  ratesDollar: { zh: '利率与美元', en: 'Rates and USD' },
  liquidityCredit: { zh: '流动性与信用', en: 'Liquidity and credit' },
  crossAssetRisk: { zh: '跨资产风险', en: 'Cross-asset risk' },
  sectorThemeRotation: { zh: '主题轮动', en: 'Theme rotation' },
  eventCatalyst: { zh: '事件催化', en: 'Event catalyst' },
} as const;

function labelFromKey(
  key: string,
  language: 'zh' | 'en',
): string {
  const mapped = DRIVER_LABELS[key as keyof typeof DRIVER_LABELS];
  if (mapped) {
    return mapped[language];
  }
  return key.replace(/([a-z])([A-Z])/g, '$1 $2');
}

function confidenceLabel(value: string | null | undefined, language: 'zh' | 'en'): string {
  switch (String(value || '').toLowerCase()) {
    case 'high':
      return language === 'en' ? 'High' : '高';
    case 'medium':
      return language === 'en' ? 'Medium' : '中';
    case 'low':
      return language === 'en' ? 'Low' : '低';
    default:
      return value || '--';
  }
}

function regimeLabel(value: string | null | undefined, language: 'zh' | 'en'): string {
  switch (String(value || '').toLowerCase()) {
    case 'riskon':
    case 'risk_on':
      return language === 'en' ? 'Risk-on observation' : '风险偏好观察';
    case 'riskoff':
    case 'risk_off':
      return language === 'en' ? 'Risk-off observation' : '风险规避观察';
    case 'neutral':
      return language === 'en' ? 'Neutral observation' : '中性观察';
    case 'lowconfidence':
    case 'low_confidence':
      return language === 'en' ? 'Low-confidence observation' : '低置信观察';
    default:
      return value || '--';
  }
}

function statusTone(value: string | null | undefined): string {
  const normalized = String(value || '').toLowerCase();
  if (['ready', 'high', 'strong', 'available', 'complete', 'success', 'riskon', 'supportive'].includes(normalized)) {
    return 'success';
  }
  if (['medium', 'mixed', 'partial', 'thin', 'warning', 'neutral', 'preview'].includes(normalized)) {
    return 'warning';
  }
  if (['blocked', 'degraded', 'unavailable', 'low', 'empty', 'low_evidence'].includes(normalized)) {
    return 'error';
  }
  return 'info';
}

function sortDriverScores(payload: MarketDecisionCockpitResponse['marketRegimeDecision']['driverScores']) {
  return Object.entries(payload || {})
    .sort(([, left], [, right]) => (right?.score ?? 0) - (left?.score ?? 0));
}

export default function MarketDecisionCockpitPage() {
  const { language } = useI18n();
  const locale = language === 'en' ? 'en' : 'zh';
  const location = useLocation();
  const routeLocale = parseLocaleFromPathname(location.pathname);
  const localize = useCallback((path: string) => (routeLocale ? buildLocalizedPath(path, routeLocale) : path), [routeLocale]);
  const [data, setData] = useState<MarketDecisionCockpitResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await marketDecisionCockpitApi.getDecisionCockpit();
      setData(response);
    } catch (err) {
      setError(getParsedApiError(err) || createParsedApiError({
        title: locale === 'en' ? 'Market decision cockpit unavailable' : '市场决策驾驶舱暂不可用',
        message: locale === 'en' ? 'Please retry after the API becomes available.' : '请在接口恢复后重试。',
      }));
    } finally {
      setLoading(false);
    }
  }, [locale]);

  useEffect(() => {
    void load();
  }, [load]);

  const driverRows = useMemo(
    () => sortDriverScores(data?.marketRegimeDecision.driverScores).map(([key, value]) => ({
      key,
      label: labelFromKey(key, locale),
      value: value?.score ?? '--',
      meta: value?.reasons?.join(' · ') || value?.evidenceState || (locale === 'en' ? 'Observation signal' : '观察信号'),
      badge: value?.evidenceState
        ? {
          label: value.evidenceState,
          variant: value.evidenceState === 'unavailable' ? ('caution' as const) : ('info' as const),
        }
        : undefined,
    })),
    [data?.marketRegimeDecision.driverScores, locale],
  );

  const previewCandidates = data?.researchQueuePreview.topCandidates ?? [];
  const cockpitSummary = data?.cockpitSummary;
  const priorities = data?.marketRegimeDecision.researchPriorities;
  const optionsStatus = data?.optionsStructureStatus;

  return (
    <ConsumerWorkspaceScope className="flex min-h-0 flex-1">
      <ConsumerWorkspacePageShell className="flex min-h-0 flex-1 flex-col gap-4 md:gap-6">
        <ResearchConsoleShell
          className="flex-1"
          command={(
            <WolfyCommandBar
              leading={<span className="text-xs text-[color:var(--wolfy-text-muted)]">{locale === 'en' ? 'Market / Rough shell' : '市场 / 粗框架'}</span>}
              trailing={(
                <div className="flex flex-wrap items-center gap-2">
                  <Link
                    to={localize('/research/radar')}
                    className="rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)]"
                  >
                    {locale === 'en' ? 'Research radar' : '研究雷达'}
                  </Link>
                  <TerminalButton variant="compact" onClick={() => void load()}>
                    {locale === 'en' ? 'Refresh' : '刷新'}
                  </TerminalButton>
                </div>
              )}
            >
              <div className="text-xs text-[color:var(--wolfy-text-secondary)]">
                {locale === 'en' ? 'Observation-only market frame for Open Design information architecture.' : '仅用于 Open Design 信息架构的市场观察型框架。'}
              </div>
            </WolfyCommandBar>
          )}
          rail={(
            <ConsoleContextRail className="flex flex-col gap-3 p-3">
              <RoughSectionCard eyebrow={locale === 'en' ? 'Summary' : '摘要'} title={locale === 'en' ? 'What changed' : '发生了什么'}>
                <RoughBulletList
                  items={(cockpitSummary?.whatChanged ?? []).map((item) => item)}
                  emptyText={locale === 'en' ? 'No change summary yet.' : '暂未整理变化摘要。'}
                />
              </RoughSectionCard>
              <RoughSectionCard eyebrow={locale === 'en' ? 'Boundary' : '边界'} title={locale === 'en' ? 'Confidence limits' : '置信边界'}>
                <RoughBulletList
                  items={(cockpitSummary?.confidenceLimits ?? []).map((item) => item)}
                  emptyText={locale === 'en' ? 'No explicit confidence limit yet.' : '暂未整理明确的置信边界。'}
                />
              </RoughSectionCard>
              <RoughSectionCard eyebrow={locale === 'en' ? 'Disclosure' : '披露'} title={locale === 'en' ? 'Observation-only note' : '观察型说明'}>
                <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
                  {data?.noAdviceDisclosure || (locale === 'en'
                    ? 'Research context only.'
                    : '仅供研究语境参考。')}
                </p>
              </RoughSectionCard>
            </ConsoleContextRail>
          )}
        >
          <ConsoleBoard className="min-h-0" data-testid="market-decision-cockpit-page">
            <RoughSurfaceIntro
              eyebrow={locale === 'en' ? 'Market decision cockpit' : '市场决策驾驶舱'}
              title={locale === 'en' ? 'Rough shell for regime, queue, and confidence limits' : '用于展示市场状态、研究队列与置信边界的粗框架'}
              description={locale === 'en'
                ? 'This surface keeps market regime, queue preview, what to watch, and gamma observation status on one route without redesigning the current frontend.'
                : '这个页面把市场状态、研究队列预览、关注点与 Gamma 观察状态放在同一路由中，不重做现有前端视觉体系。'}
            />
            {error ? (
              <div className="p-4 md:p-5">
                <ApiErrorAlert
                  error={error}
                  actionLabel={locale === 'en' ? 'Retry' : '重试'}
                  onAction={() => void load()}
                />
              </div>
            ) : null}
            {loading && !data ? (
              <div className="p-4 md:p-5">
                <TerminalEmptyState title={locale === 'en' ? 'Loading market frame' : '正在整理市场框架'}>
                  {locale === 'en' ? 'The page is waiting for market regime, queue preview, and options observation status.' : '正在等待市场状态、研究队列预览与期权观察状态。'}
                </TerminalEmptyState>
              </div>
            ) : null}
            {data ? (
              <>
                <ConsoleStatusStrip
                  items={[
                    {
                      label: locale === 'en' ? 'Updated' : '更新时间',
                      value: formatDateTime(data.generatedAt, { locale: locale === 'en' ? 'en-US' : 'zh-CN' }),
                    },
                    {
                      label: locale === 'en' ? 'Data quality' : '数据质量',
                      value: <StatusBadge status={statusTone(data.dataQuality?.status)} label={data.dataQuality?.status || '--'} size="sm" />,
                    },
                    {
                      label: locale === 'en' ? 'Preview mode' : '预览模式',
                      value: data.researchQueuePreview.previewOnly ? (locale === 'en' ? 'Preview only' : '仅预览') : '--',
                    },
                  ]}
                />
                <MetricStrip
                  items={[
                    {
                      key: 'regime',
                      label: locale === 'en' ? 'Regime' : '市场状态',
                      value: regimeLabel(data.marketRegimeDecision.regime, locale),
                    },
                    {
                      key: 'confidence',
                      label: locale === 'en' ? 'Confidence' : '置信度',
                      value: confidenceLabel(data.marketRegimeDecision.confidence, locale),
                    },
                    {
                      key: 'queue',
                      label: locale === 'en' ? 'Queue quality' : '队列质量',
                      value: data.researchQueuePreview.queueQuality || '--',
                    },
                  ]}
                />
                <div className="grid gap-3 p-3 md:grid-cols-2">
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Drivers' : '驱动'} title={locale === 'en' ? 'Driver scores' : '驱动评分'}>
                    <RoughScoreRows
                      items={driverRows}
                      emptyText={locale === 'en' ? 'No driver scores yet.' : '暂无驱动评分。'}
                    />
                  </RoughSectionCard>
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Regime logic' : '状态逻辑'} title={locale === 'en' ? 'Why this regime' : '为什么形成当前状态'}>
                    <RoughKeyValueRows
                      rows={[
                        {
                          key: 'why',
                          label: locale === 'en' ? 'Why this regime' : '形成原因',
                          value: (data.marketRegimeDecision.explanation?.whyThisRegime ?? []).join('；') || '--',
                        },
                        {
                          key: 'confirm',
                          label: locale === 'en' ? 'What confirms it' : '确认信号',
                          value: (data.marketRegimeDecision.explanation?.whatConfirmsIt ?? []).join('；') || '--',
                        },
                        {
                          key: 'invalidate',
                          label: locale === 'en' ? 'What invalidates it' : '失效观察',
                          value: (data.marketRegimeDecision.invalidationConditions ?? []).join('；') || '--',
                        },
                      ]}
                    />
                  </RoughSectionCard>
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Next steps' : '下一步'} title={locale === 'en' ? 'What to watch and verify' : '关注点与验证项'}>
                    <RoughKeyValueRows
                      rows={[
                        {
                          key: 'watch',
                          label: locale === 'en' ? 'What to watch' : '今日关注',
                          value: (cockpitSummary?.whatToWatch ?? priorities?.watchToday ?? []).join('；') || '--',
                        },
                        {
                          key: 'evidence',
                          label: locale === 'en' ? 'Needs more evidence' : '待补证据',
                          value: (priorities?.needsMoreEvidence ?? data.researchQueuePreview.evidenceGaps ?? []).join('；') || '--',
                        },
                        {
                          key: 'next',
                          label: locale === 'en' ? 'Investigate next' : '下一步研究',
                          value: (priorities?.investigateNext ?? []).join('；') || '--',
                        },
                      ]}
                    />
                  </RoughSectionCard>
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Options / gamma' : '期权 / Gamma'} title={locale === 'en' ? 'Observation-only status' : '仅观察状态'}>
                    <RoughKeyValueRows
                      rows={[
                        {
                          key: 'gamma',
                          label: locale === 'en' ? 'Gamma evidence' : 'Gamma 证据',
                          value: optionsStatus?.gammaEvidenceStatus || '--',
                        },
                        {
                          key: 'observation',
                          label: locale === 'en' ? 'Boundary' : '边界',
                          value: optionsStatus?.observationOnly
                            ? (locale === 'en' ? 'Observation only · decisionGrade=false' : '仅观察 · decisionGrade=false')
                            : '--',
                        },
                        {
                          key: 'blocked',
                          label: locale === 'en' ? 'Blocked reasons' : '阻塞原因',
                          value: (optionsStatus?.blockedReasonCodes ?? []).join('；') || '--',
                        },
                      ]}
                    />
                    <div className="mt-3 flex flex-wrap gap-2">
                      {(optionsStatus?.missingEvidence ?? []).map((item, index) => (
                        <TerminalChip key={`${item.code || item.kind || 'missing'}-${index}`} variant="caution">
                          {item.code || item.kind || item.field || (locale === 'en' ? 'Missing evidence' : '缺失证据')}
                        </TerminalChip>
                      ))}
                    </div>
                  </RoughSectionCard>
                </div>
                <div className="border-t border-[color:var(--wolfy-divider)] p-3">
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Research queue' : '研究队列'} title={locale === 'en' ? 'Queue preview' : '队列预览'}>
                    {previewCandidates.length ? (
                      <div className="space-y-3">
                        {previewCandidates.map((candidate, index) => (
                          <div key={`${candidate.ticker || candidate.symbol || 'candidate'}-${index}`} className="rounded-xl border border-[color:var(--wolfy-divider)] bg-black/10 p-3">
                            <div className="flex flex-wrap items-center justify-between gap-3">
                              <div>
                                <div className="text-sm font-medium text-[color:var(--wolfy-text-primary)]">
                                  {candidate.ticker || candidate.symbol || '--'}
                                </div>
                                <div className="mt-1 text-xs text-[color:var(--wolfy-text-muted)]">
                                  {(candidate.whyOnRadar ?? []).join('；') || (locale === 'en' ? 'Research queue preview item.' : '研究队列预览条目。')}
                                </div>
                              </div>
                              <div className="flex flex-wrap items-center gap-2">
                                {candidate.priority ? <StatusBadge status={statusTone(candidate.priority)} label={candidate.priority} size="sm" /> : null}
                                {candidate.researchBias ? <TerminalChip variant="info">{candidate.researchBias}</TerminalChip> : null}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <TerminalEmptyState title={locale === 'en' ? 'Queue preview unavailable' : '队列预览暂不可用'}>
                        {locale === 'en' ? 'Use this area for top candidates, evidence gaps, and degraded queue notes.' : '这里用于展示重点候选、证据缺口与降级说明。'}
                      </TerminalEmptyState>
                    )}
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
