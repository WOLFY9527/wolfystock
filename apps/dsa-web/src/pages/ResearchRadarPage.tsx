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
import { StatusBadge } from '../components/ui/StatusBadge';
import { TerminalButton, TerminalChip, TerminalEmptyState } from '../components/terminal/TerminalPrimitives';
import { createParsedApiError, getParsedApiError, type ParsedApiError } from '../api/error';
import { researchRadarApi, type ResearchRadarResponse } from '../api/researchRadar';
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
  relativeStrength: { zh: '相对强弱', en: 'Relative strength' },
  themeAlignment: { zh: '主题匹配', en: 'Theme alignment' },
  regimeFit: { zh: '市场匹配', en: 'Regime fit' },
  volumeSupport: { zh: '量能支持', en: 'Volume support' },
  structureQuality: { zh: '结构质量', en: 'Structure quality' },
  eventReadiness: { zh: '事件就绪度', en: 'Event readiness' },
  evidenceQuality: { zh: '证据质量', en: 'Evidence quality' },
} as const;

function toneFor(value: string | null | undefined): string {
  const normalized = String(value || '').toLowerCase();
  if (['high', 'ready', 'strong', 'supportive', 'complete'].includes(normalized)) return 'success';
  if (['medium', 'mixed', 'partial', 'neutral'].includes(normalized)) return 'warning';
  if (['low', 'degraded', 'unavailable', 'thin'].includes(normalized)) return 'error';
  return 'info';
}

function driverLabel(key: string, language: 'zh' | 'en') {
  const mapped = DRIVER_LABELS[key as keyof typeof DRIVER_LABELS];
  if (mapped) {
    return mapped[language];
  }
  return key.replace(/([a-z])([A-Z])/g, '$1 $2');
}

export default function ResearchRadarPage() {
  const { language } = useI18n();
  const locale = language === 'en' ? 'en' : 'zh';
  const location = useLocation();
  const routeLocale = parseLocaleFromPathname(location.pathname);
  const [searchParams] = useSearchParams();
  const localize = useCallback((path: string) => (routeLocale ? buildLocalizedPath(path, routeLocale) : path), [routeLocale]);
  const [data, setData] = useState<ResearchRadarResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);

  const market = searchParams.get('market') || undefined;
  const profile = searchParams.get('profile') || undefined;
  const limit = searchParams.get('limit');
  const parsedLimit = limit ? Number(limit) : undefined;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await researchRadarApi.getResearchRadar({
        market,
        profile,
        limit: Number.isFinite(parsedLimit) ? parsedLimit : undefined,
      });
      setData(response);
    } catch (err) {
      setError(getParsedApiError(err) || createParsedApiError({
        title: locale === 'en' ? 'Research radar unavailable' : '研究雷达暂不可用',
        message: locale === 'en' ? 'Please retry after the queue API responds again.' : '请在队列接口恢复后重试。',
      }));
    } finally {
      setLoading(false);
    }
  }, [locale, market, parsedLimit, profile]);

  useEffect(() => {
    void load();
  }, [load]);

  const queueItems = useMemo(() => data?.researchQueue ?? [], [data?.researchQueue]);
  const firstItemScores = useMemo(
    () => Object.entries(queueItems[0]?.driverScores ?? {})
      .sort(([, left], [, right]) => (right ?? 0) - (left ?? 0))
      .map(([key, value]) => ({
        key,
        label: driverLabel(key, locale),
        value,
      })),
    [queueItems, locale],
  );

  return (
    <ConsumerWorkspaceScope className="flex min-h-0 flex-1">
      <ConsumerWorkspacePageShell className="flex min-h-0 flex-1 flex-col gap-4 md:gap-6">
        <ResearchConsoleShell
          className="flex-1"
          command={(
            <WolfyCommandBar
              leading={<span className="text-xs text-[color:var(--wolfy-text-muted)]">{locale === 'en' ? 'Research / Rough shell' : '研究 / 粗框架'}</span>}
              trailing={(
                <div className="flex flex-wrap items-center gap-2">
                  <Link
                    to={localize('/market/decision-cockpit')}
                    className="rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)]"
                  >
                    {locale === 'en' ? 'Market cockpit' : '市场驾驶舱'}
                  </Link>
                  <TerminalButton variant="compact" onClick={() => void load()}>
                    {locale === 'en' ? 'Refresh' : '刷新'}
                  </TerminalButton>
                </div>
              )}
            >
              <div className="text-xs text-[color:var(--wolfy-text-secondary)]">
                {locale === 'en' ? 'Authenticated queue for observation, verification, and evidence gaps.' : '面向登录用户的观察、验证与证据缺口队列。'}
              </div>
            </WolfyCommandBar>
          )}
          rail={(
            <ConsoleContextRail className="flex flex-col gap-3 p-3">
              <RoughSectionCard eyebrow={locale === 'en' ? 'Aggregate' : '汇总'} title={locale === 'en' ? 'Evidence gaps' : '证据缺口'}>
                <RoughBulletList
                  items={(data?.evidenceGaps ?? []).map((item) => item)}
                  emptyText={locale === 'en' ? 'No aggregate evidence gap.' : '暂无汇总证据缺口。'}
                />
              </RoughSectionCard>
              <RoughSectionCard eyebrow={locale === 'en' ? 'Queue state' : '队列状态'} title={locale === 'en' ? 'Priority counts' : '优先级计数'}>
                <RoughKeyValueRows
                  rows={Object.entries(data?.aggregateSummary.priorityCounts ?? {}).map(([key, value]) => ({
                    key,
                    label: key,
                    value,
                  }))}
                />
              </RoughSectionCard>
              <RoughSectionCard eyebrow={locale === 'en' ? 'Disclosure' : '披露'} title={locale === 'en' ? 'Observation-only note' : '观察型说明'}>
                <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
                  {data?.noAdviceDisclosure || (locale === 'en' ? 'Research queue only.' : '仅供研究队列观察。')}
                </p>
              </RoughSectionCard>
            </ConsoleContextRail>
          )}
        >
          <ConsoleBoard className="min-h-0" data-testid="research-radar-page">
            <RoughSurfaceIntro
              eyebrow={locale === 'en' ? 'Research radar' : '研究雷达'}
              title={locale === 'en' ? 'Queue rough shell for priority, bias, and evidence gaps' : '用于展示优先级、研究偏向与证据缺口的队列粗框架'}
              description={locale === 'en'
                ? 'This route keeps queue ranking, why-on-radar rationale, verify items, and risk flags together for a later visual redesign.'
                : '这个路由把队列排序、上榜原因、验证事项与风险标记放在一起，供后续视觉重构使用。'}
            />
            {error ? (
              <div className="p-4 md:p-5">
                <ApiErrorAlert error={error} actionLabel={locale === 'en' ? 'Retry' : '重试'} onAction={() => void load()} />
              </div>
            ) : null}
            {loading && !data ? (
              <div className="p-4 md:p-5">
                <TerminalEmptyState title={locale === 'en' ? 'Loading research radar' : '正在整理研究雷达'}>
                  {locale === 'en' ? 'The page is waiting for queue items, evidence gaps, and queue quality.' : '正在等待队列条目、证据缺口与队列质量。'}
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
                      value: <StatusBadge status={toneFor(data.dataQuality?.status)} label={data.dataQuality?.status || '--'} size="sm" />,
                    },
                    {
                      label: locale === 'en' ? 'Context fit' : '市场匹配',
                      value: data.marketContextFit || '--',
                    },
                  ]}
                />
                <MetricStrip
                  items={[
                    {
                      key: 'queue-quality',
                      label: locale === 'en' ? 'Queue quality' : '队列质量',
                      value: data.aggregateSummary.queueQuality || '--',
                    },
                    {
                      key: 'queue-size',
                      label: locale === 'en' ? 'Queue size' : '队列数量',
                      value: queueItems.length,
                    },
                    {
                      key: 'market',
                      label: locale === 'en' ? 'Market filter' : '市场过滤',
                      value: market || '--',
                    },
                  ]}
                />
                <div className="grid gap-3 p-3 md:grid-cols-2">
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Queue' : '队列'} title={locale === 'en' ? 'Research queue' : '研究队列'}>
                    {queueItems.length ? (
                      <div className="space-y-3">
                        {queueItems.map((item, index) => (
                          <div key={`${item.ticker || item.symbol || 'queue'}-${index}`} className="rounded-xl border border-[color:var(--wolfy-divider)] bg-black/10 p-3">
                            <div className="flex flex-wrap items-center justify-between gap-3">
                              <div className="min-w-0">
                                <div className="text-sm font-medium text-[color:var(--wolfy-text-primary)]">{item.ticker || item.symbol || '--'}</div>
                                <div className="mt-1 text-xs text-[color:var(--wolfy-text-muted)]">
                                  {(item.whyOnRadar ?? []).join('；') || (locale === 'en' ? 'Observation queue item.' : '观察队列条目。')}
                                </div>
                              </div>
                              <div className="flex flex-wrap items-center gap-2">
                                {item.priority ? <StatusBadge status={toneFor(item.priority)} label={item.priority} size="sm" /> : null}
                                {item.researchBias ? <TerminalChip variant="info">{item.researchBias}</TerminalChip> : null}
                              </div>
                            </div>
                            <div className="mt-3 flex flex-wrap gap-2">
                              {(item.riskFlags ?? []).length
                                ? (item.riskFlags ?? []).map((flag, riskIndex) => (
                                  <TerminalChip key={`${flag}-${riskIndex}`} variant="caution">{flag}</TerminalChip>
                                ))
                                : <TerminalChip variant="success">{locale === 'en' ? 'No explicit risk flag' : '暂无明确风险标记'}</TerminalChip>}
                            </div>
                            <div className="mt-3 flex gap-2">
                              {item.ticker ? (
                                <Link
                                  to={localize(`/stocks/${encodeURIComponent(item.ticker)}/structure-decision`)}
                                  className="rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)]"
                                >
                                  {locale === 'en' ? 'Open structure panel' : '打开结构面板'}
                                </Link>
                              ) : null}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <TerminalEmptyState title={locale === 'en' ? 'Queue unavailable' : '队列暂不可用'}>
                        {locale === 'en' ? 'Use this region for queue order, priority, and next verification steps.' : '这里用于展示队列顺序、优先级与下一步验证事项。'}
                      </TerminalEmptyState>
                    )}
                  </RoughSectionCard>
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Lead item' : '队首条目'} title={locale === 'en' ? 'Driver scores' : '驱动评分'}>
                    <RoughScoreRows
                      items={firstItemScores}
                      emptyText={locale === 'en' ? 'No lead item yet.' : '暂无线索条目。'}
                    />
                  </RoughSectionCard>
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Lead item' : '队首条目'} title={locale === 'en' ? 'What to verify' : '待验证事项'}>
                    <RoughBulletList
                      items={(queueItems[0]?.whatToVerify ?? []).map((item) => item)}
                      emptyText={locale === 'en' ? 'No verify item yet.' : '暂未整理验证事项。'}
                    />
                  </RoughSectionCard>
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Lead item' : '队首条目'} title={locale === 'en' ? 'Invalidation observations' : '失效观察'}>
                    <RoughBulletList
                      items={(queueItems[0]?.invalidationObservations ?? []).map((item) => item)}
                      emptyText={locale === 'en' ? 'No invalidation observation yet.' : '暂未整理失效观察。'}
                    />
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
