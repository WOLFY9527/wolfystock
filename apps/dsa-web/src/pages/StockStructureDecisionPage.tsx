import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
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
import PeerCorrelationSnapshotBlock from '../components/common/PeerCorrelationSnapshotBlock';
import { StatusBadge } from '../components/ui/StatusBadge';
import { TerminalButton, TerminalChip, TerminalEmptyState } from '../components/terminal/TerminalPrimitives';
import { createParsedApiError, getParsedApiError, type ParsedApiError } from '../api/error';
import {
  stocksApi,
  type StockStructureDecisionResponse,
  type StockSymbolCompareEvidenceEntry,
  type StockSymbolCompareEvidencePacket,
  type StockSymbolCompareFreshness,
} from '../api/stocks';
import { useI18n } from '../contexts/UiLanguageContext';
import { buildLocalizedPath, parseLocaleFromPathname } from '../utils/localeRouting';
import {
  RoughBulletList,
  RoughKeyValueRows,
  RoughScoreRows,
  RoughSectionCard,
  RoughSurfaceIntro,
} from './roughShellShared';

const COMPONENT_LABELS = {
  trend: { zh: '趋势', en: 'Trend' },
  relativeStrength: { zh: '相对强弱', en: 'Relative strength' },
  volumePressure: { zh: '量能压力', en: 'Volume pressure' },
  volatilityCompression: { zh: '波动压缩', en: 'Volatility compression' },
  breakoutQuality: { zh: '突破质量', en: 'Breakout quality' },
  pullbackHealth: { zh: '回撤健康度', en: 'Pullback health' },
  riskExtension: { zh: '延展风险', en: 'Risk extension' },
  evidenceQuality: { zh: '证据质量', en: 'Evidence quality' },
} as const;

function localLabel(key: string, language: 'zh' | 'en'): string {
  const mapped = COMPONENT_LABELS[key as keyof typeof COMPONENT_LABELS];
  if (mapped) {
    return mapped[language];
  }
  return key.replace(/([a-z])([A-Z])/g, '$1 $2');
}

function confidenceLabel(value: string, language: 'zh' | 'en') {
  switch (value.toLowerCase()) {
    case 'high':
      return language === 'en' ? 'High' : '高';
    case 'medium':
      return language === 'en' ? 'Medium' : '中';
    case 'low':
      return language === 'en' ? 'Low' : '低';
    default:
      return value;
  }
}

function toneFor(value: string | null | undefined): string {
  const normalized = String(value || '').toLowerCase();
  if (['available', 'high', 'ready', 'complete', 'breakout'].includes(normalized)) return 'success';
  if (['medium', 'partial', 'range', 'neutral'].includes(normalized)) return 'warning';
  if (['low', 'unavailable', 'lowconfidence', 'low_confidence', 'blocked'].includes(normalized)) return 'error';
  return 'info';
}

function symbolSegmentFromPathname(pathname: string): string {
  const match = pathname.match(/\/stocks\/([^/?#]+)\/structure-decision/i);
  if (!match?.[1]) return '';
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return match[1];
  }
}

function parseStockStructureSymbols(value: string | null | undefined): string[] {
  return [...new Set(String(value || '')
    .split(/[,\s;|+]+/)
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean))];
}

function parsePositiveInteger(value: string | null): number | undefined {
  if (!value) return undefined;
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined;
}

function evidenceKindLabel(kind: string | null | undefined, language: 'zh' | 'en'): string {
  const normalized = String(kind || '').toLowerCase();
  const labels: Record<string, { zh: string; en: string }> = {
    daily_ohlcv: { zh: '日线数据', en: 'Daily OHLCV' },
    benchmark_ohlcv: { zh: '基准日线数据', en: 'Benchmark OHLCV' },
    structure_state: { zh: '结构状态', en: 'Structure state' },
    data_quality: { zh: '数据质量', en: 'Data quality' },
    relative_strength: { zh: '相对强弱证据', en: 'Relative strength evidence' },
  };
  const mapped = labels[normalized];
  if (mapped) return mapped[language];
  const readable = normalized.replace(/[_-]+/g, ' ').trim();
  return readable || (language === 'en' ? 'Evidence' : '证据');
}

function statusLabel(status: string | null | undefined, language: 'zh' | 'en'): string {
  const normalized = String(status || '').toLowerCase();
  const labels: Record<string, { zh: string; en: string }> = {
    available: { zh: '可用', en: 'available' },
    partial: { zh: '部分可用', en: 'partial' },
    unavailable: { zh: '不可用', en: 'unavailable' },
    degraded: { zh: '降级', en: 'degraded' },
  };
  return labels[normalized]?.[language] ?? (status || '--');
}

function periodLabel(period: string | null | undefined, language: 'zh' | 'en'): string | null {
  if (!period) return null;
  const normalized = String(period).toLowerCase();
  if (normalized === 'daily') return language === 'en' ? 'daily' : '日线';
  if (normalized === 'weekly') return language === 'en' ? 'weekly' : '周线';
  return String(period);
}

function barsRangeLabel(min: unknown, max: unknown, language: 'zh' | 'en'): string | null {
  const minValue = Number(min);
  const maxValue = Number(max);
  const hasMin = Number.isFinite(minValue);
  const hasMax = Number.isFinite(maxValue);
  if (!hasMin && !hasMax) return null;
  if (hasMin && hasMax && minValue !== maxValue) {
    return language === 'en' ? `${minValue}-${maxValue} usable bars` : `${minValue}-${maxValue} 根可用`;
  }
  const value = hasMin ? minValue : maxValue;
  return language === 'en' ? `${value} usable bars` : `${value} 根可用`;
}

function barsCountLabel(value: unknown, language: 'zh' | 'en'): string | null {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return null;
  return language === 'en' ? `${numeric} bars` : `${numeric} 根`;
}

function sharedEvidenceMeta(item: StockSymbolCompareEvidenceEntry, language: 'zh' | 'en'): string {
  return [
    statusLabel(item.status, language),
    periodLabel(item.period, language),
    barsRangeLabel(item.usableBarsMin, item.usableBarsMax, language),
  ].filter(Boolean).join(' · ');
}

function freshnessMeta(item: StockSymbolCompareFreshness | undefined, language: 'zh' | 'en'): string {
  if (!item) return language === 'en' ? 'No freshness summary' : '暂无新鲜度摘要';
  return [
    statusLabel(item.status, language),
    periodLabel(item.period, language),
    barsCountLabel(item.usableBars, language),
  ].filter(Boolean).join(' · ');
}

function evidenceValue(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '--';
  return String(value);
}

function SymbolCompareEvidencePacketPanel({
  packet,
  language,
}: {
  packet: StockSymbolCompareEvidencePacket | null;
  language: 'zh' | 'en';
}) {
  const comparedSymbols = (packet?.comparedSymbols ?? []).filter(Boolean);
  if (!packet || comparedSymbols.length <= 1) return null;

  const confidenceCapValue = packet.confidenceCap?.value;
  const boundary = packet.observationBoundary ?? {};
  const boundaryChips = [
    boundary.observationOnly ? (language === 'en' ? 'Research observation only' : '仅研究观察') : null,
    boundary.decisionGrade === false ? (language === 'en' ? 'Not decision grade' : '非判断等级') : null,
    boundary.rankingAllowed === false ? (language === 'en' ? 'No ordering output' : '不排序') : null,
    boundary.adviceAllowed === false ? (language === 'en' ? 'No action instruction' : '不生成行动指令') : null,
  ].filter(Boolean) as string[];

  return (
    <div className="grid gap-3 border-t border-[color:var(--wolfy-divider)] p-3 md:grid-cols-2" data-testid="symbol-compare-evidence-packet">
      <RoughSectionCard
        className="md:col-span-2"
        eyebrow={language === 'en' ? 'Evidence packet' : '证据包'}
        title={language === 'en' ? 'Compare evidence packet' : '对比证据包'}
      >
        <div className="flex flex-wrap items-center gap-2">
          {comparedSymbols.map((symbol) => (
            <TerminalChip key={symbol} variant="info">{symbol}</TerminalChip>
          ))}
          <TerminalChip variant="caution">
            {language === 'en'
              ? `Confidence cap ${confidenceCapValue ?? '--'}`
              : `置信上限 ${confidenceCapValue ?? '--'}`}
          </TerminalChip>
          {boundaryChips.map((label) => (
            <TerminalChip key={label} variant="neutral">{label}</TerminalChip>
          ))}
        </div>
      </RoughSectionCard>

      <RoughSectionCard title={language === 'en' ? 'Shared evidence' : '共享证据'}>
        <RoughBulletList
          items={packet.sharedEvidence.map((item, index) => (
            <span key={index}>
              <span className="font-medium text-[color:var(--wolfy-text-primary)]">{evidenceKindLabel(item.kind, language)}</span>
              <span className="ml-2 text-[color:var(--wolfy-text-muted)]">{sharedEvidenceMeta(item, language)}</span>
            </span>
          ))}
          emptyText={language === 'en' ? 'No shared evidence is available across these symbols yet.' : '这些标的之间暂无共同证据。'}
        />
      </RoughSectionCard>

      <RoughSectionCard title={language === 'en' ? 'Divergent evidence' : '分歧证据'}>
        <RoughBulletList
          items={packet.divergentEvidence.map((item, index) => {
            const values = item.values ?? {};
            const valueText = Object.entries(values)
              .map(([symbol, value]) => `${symbol}: ${evidenceValue(value)}`)
              .join(' · ');
            return (
              <span key={index}>
                <span className="font-medium text-[color:var(--wolfy-text-primary)]">{evidenceKindLabel(item.kind, language)}</span>
                {valueText ? <span className="ml-2 text-[color:var(--wolfy-text-muted)]">{valueText}</span> : null}
              </span>
            );
          })}
          emptyText={language === 'en' ? 'No divergence is available in this packet.' : '当前证据包暂无分歧观察。'}
        />
      </RoughSectionCard>

      <RoughSectionCard title={language === 'en' ? 'Missing evidence' : '缺失证据'}>
        <RoughKeyValueRows
          rows={comparedSymbols.map((symbol) => {
            const gaps = packet.missingEvidenceBySymbol[symbol] ?? [];
            return {
              key: `missing-${symbol}`,
              label: symbol,
              value: gaps.length
                ? gaps.map((gap) => gap.message || evidenceKindLabel(gap.kind, language)).join('；')
                : (language === 'en' ? 'No gap listed' : '暂无缺口'),
            };
          })}
        />
      </RoughSectionCard>

      <RoughSectionCard title={language === 'en' ? 'Freshness by symbol' : '新鲜度'}>
        <RoughKeyValueRows
          rows={comparedSymbols.map((symbol) => ({
            key: `freshness-${symbol}`,
            label: symbol,
            value: freshnessMeta(packet.freshnessBySymbol[symbol], language),
          }))}
        />
      </RoughSectionCard>

      <RoughSectionCard className="md:col-span-2" title={language === 'en' ? 'Next research steps' : '后续研究'}>
        <RoughBulletList
          items={packet.researchNextSteps}
          emptyText={language === 'en' ? 'No additional research step is listed.' : '暂无额外后续研究项。'}
        />
      </RoughSectionCard>
    </div>
  );
}

export default function StockStructureDecisionPage() {
  const { language } = useI18n();
  const locale = language === 'en' ? 'en' : 'zh';
  const { stockCode = '' } = useParams();
  const location = useLocation();
  const routeLocale = parseLocaleFromPathname(location.pathname);
  const localize = useCallback((path: string) => (routeLocale ? buildLocalizedPath(path, routeLocale) : path), [routeLocale]);
  const searchParams = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const symbolSegment = stockCode || symbolSegmentFromPathname(location.pathname);
  const requestedSymbols = useMemo(
    () => parseStockStructureSymbols(searchParams.get('symbols') || symbolSegment),
    [searchParams, symbolSegment],
  );
  const benchmark = searchParams.get('benchmark')?.trim().toUpperCase() || undefined;
  const maxItems = parsePositiveInteger(searchParams.get('maxItems'));
  const isCompareRequest = requestedSymbols.length > 1;
  const primarySymbol = requestedSymbols[0] || symbolSegment.toUpperCase();
  const titleSymbol = isCompareRequest ? requestedSymbols.join(' / ') : primarySymbol;
  const [data, setData] = useState<StockStructureDecisionResponse | null>(null);
  const [comparePacket, setComparePacket] = useState<StockSymbolCompareEvidencePacket | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (isCompareRequest) {
        const response = await stocksApi.getStructureDecisionsBatch({
          stockCodes: requestedSymbols,
          benchmark,
          maxItems,
        });
        setData(response.items[0] ?? null);
        setComparePacket(response.symbolCompareEvidencePacket ?? null);
      } else {
        const response = await stocksApi.getStructureDecision(primarySymbol);
        setData(response);
        setComparePacket(null);
      }
    } catch (err) {
      setComparePacket(null);
      setError(getParsedApiError(err) || createParsedApiError({
        title: locale === 'en' ? 'Structure panel unavailable' : '结构面板暂不可用',
        message: locale === 'en' ? 'Please retry after the stock structure API responds again.' : '请在个股结构接口恢复后重试。',
      }));
    } finally {
      setLoading(false);
    }
  }, [benchmark, isCompareRequest, locale, maxItems, primarySymbol, requestedSymbols]);

  useEffect(() => {
    void load();
  }, [load]);

  const scoreRows = useMemo(
    () => Object.entries(data?.componentScores ?? {})
      .sort(([, left], [, right]) => (right ?? 0) - (left ?? 0))
      .map(([key, value]) => ({
        key,
        label: localLabel(key, locale),
        value,
      })),
    [data?.componentScores, locale],
  );

  return (
    <ConsumerWorkspaceScope className="flex min-h-0 flex-1">
      <ConsumerWorkspacePageShell className="flex min-h-0 flex-1 flex-col gap-4 md:gap-6">
        <ResearchConsoleShell
          className="flex-1"
          command={(
            <WolfyCommandBar
              leading={<span className="text-xs text-[color:var(--wolfy-text-muted)]">{locale === 'en' ? 'Single-name Research / Structure' : '个股研究 / 结构'}</span>}
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
                {locale === 'en' ? 'Observation-only structure workspace for state, key levels, research notes, and evidence gaps.' : '仅观察结构工作区，集中呈现状态、关键位置、研究备注与证据缺口。'}
              </div>
            </WolfyCommandBar>
          )}
          rail={(
            <ConsoleContextRail className="flex flex-col gap-3 p-3">
              <RoughSectionCard eyebrow={locale === 'en' ? 'Research notes' : '研究备注'} title={locale === 'en' ? 'Watch next' : '下一步观察'}>
                <RoughBulletList
                  items={(data?.researchNotes.watchNext ?? []).map((item) => item)}
                  emptyText={locale === 'en' ? 'No next watch item yet.' : '暂未整理下一步观察项。'}
                />
              </RoughSectionCard>
              <RoughSectionCard eyebrow={locale === 'en' ? 'Boundary' : '边界'} title={locale === 'en' ? 'Missing evidence' : '缺失证据'}>
                <div className="flex flex-wrap gap-2">
                  {(data?.missingEvidence ?? []).map((item, index) => (
                    <TerminalChip key={`${item.kind || item.code || 'gap'}-${index}`} variant="caution">
                      {item.message || item.kind || item.code || (locale === 'en' ? 'Evidence gap' : '证据缺口')}
                    </TerminalChip>
                  ))}
                  {!(data?.missingEvidence ?? []).length ? (
                    <TerminalChip variant="success">{locale === 'en' ? 'No explicit gap' : '暂无明确缺口'}</TerminalChip>
                  ) : null}
                </div>
              </RoughSectionCard>
              <RoughSectionCard eyebrow={locale === 'en' ? 'Disclosure' : '披露'} title={locale === 'en' ? 'Observation-only note' : '观察型说明'}>
                <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
                  {data?.noAdviceDisclosure || (locale === 'en' ? 'Observation-only context.' : '仅供观察语境参考。')}
                </p>
              </RoughSectionCard>
            </ConsoleContextRail>
          )}
        >
          <ConsoleBoard className="min-h-0" data-testid="stock-structure-decision-page">
            <RoughSurfaceIntro
              eyebrow={locale === 'en' ? 'Stock structure panel' : '个股结构面板'}
              title={locale === 'en' ? `${titleSymbol} structure workspace` : `${titleSymbol} 结构工作区`}
              description={locale === 'en'
                ? 'This panel keeps structure state, confidence, component scores, research notes, and evidence gaps together before the name moves into watchlist or portfolio context.'
                : '这个面板把结构状态、置信度、组件评分、研究备注与证据缺口放在同一页，再决定是否沉淀到观察列表或组合上下文。'}
            />
            {error ? (
              <div className="p-4 md:p-5">
                <ApiErrorAlert error={error} actionLabel={locale === 'en' ? 'Retry' : '重试'} onAction={() => void load()} />
              </div>
            ) : null}
            {loading && !data ? (
              <div className="p-4 md:p-5">
                <TerminalEmptyState title={locale === 'en' ? 'Loading structure panel' : '正在整理结构面板'}>
                  {locale === 'en' ? 'The page is waiting for structure state, component scores, and evidence notes.' : '正在等待结构状态、组件评分与证据备注。'}
                </TerminalEmptyState>
              </div>
            ) : null}
            {data ? (
              <>
                <ConsoleStatusStrip
                  items={[
                    {
                      label: locale === 'en' ? 'Ticker' : '标的',
                      value: data.ticker,
                    },
                    {
                      label: locale === 'en' ? 'Data quality' : '数据质量',
                      value: <StatusBadge status={toneFor(data.dataQuality.status)} label={data.dataQuality.status || '--'} size="sm" />,
                    },
                    {
                      label: locale === 'en' ? 'Period' : '周期',
                      value: data.dataQuality.period || '--',
                    },
                  ]}
                />
                <MetricStrip
                  items={[
                    {
                      key: 'state',
                      label: locale === 'en' ? 'Structure state' : '结构状态',
                      value: data.structureState,
                    },
                    {
                      key: 'confidence',
                      label: locale === 'en' ? 'Confidence' : '置信度',
                      value: confidenceLabel(data.confidence, locale),
                    },
                    {
                      key: 'bars',
                      label: locale === 'en' ? 'Usable bars' : '可用 K 线',
                      value: data.dataQuality.usableBars ?? '--',
                    },
                  ]}
                />
                <SymbolCompareEvidencePacketPanel packet={comparePacket} language={locale} />
                <div className="grid gap-3 p-3 md:grid-cols-2">
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Scores' : '评分'} title={locale === 'en' ? 'Component scores' : '组件评分'}>
                    <RoughScoreRows
                      items={scoreRows}
                      emptyText={locale === 'en' ? 'No component score yet.' : '暂无组件评分。'}
                    />
                  </RoughSectionCard>
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Structure logic' : '结构逻辑'} title={locale === 'en' ? 'Why this structure' : '结构解释'}>
                    <RoughKeyValueRows
                      rows={[
                        {
                          key: 'why',
                          label: locale === 'en' ? 'Why this structure' : '形成原因',
                          value: data.explanation.whyThisStructure || '--',
                        },
                        {
                          key: 'confirm',
                          label: locale === 'en' ? 'What confirms it' : '确认观察',
                          value: (data.explanation.whatConfirmsIt ?? []).join('；') || '--',
                        },
                        {
                          key: 'invalidate',
                          label: locale === 'en' ? 'What invalidates it' : '失效观察',
                          value: (data.explanation.whatInvalidatesIt ?? []).join('；') || '--',
                        },
                      ]}
                    />
                  </RoughSectionCard>
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Research notes' : '研究备注'} title={locale === 'en' ? 'What to verify next' : '下一步验证'}>
                    <RoughKeyValueRows
                      rows={[
                        {
                          key: 'watch',
                          label: locale === 'en' ? 'Watch next' : '下一步观察',
                          value: (data.researchNotes.watchNext ?? []).join('；') || '--',
                        },
                        {
                          key: 'more',
                          label: locale === 'en' ? 'Needs more evidence' : '待补证据',
                          value: (data.researchNotes.needsMoreEvidence ?? []).join('；') || '--',
                        },
                        {
                          key: 'risk',
                          label: locale === 'en' ? 'Risk flags' : '风险标记',
                          value: (data.researchNotes.riskFlags ?? []).join('；') || '--',
                        },
                      ]}
                    />
                  </RoughSectionCard>
                  <PeerCorrelationSnapshotBlock
                    snapshot={data.peerCorrelationSnapshot}
                    locale={locale}
                    testId="stock-structure-peer-correlation-snapshot"
                    className="md:col-span-2"
                  />
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Reference levels' : '参考位置'} title={locale === 'en' ? 'Key levels' : '关键位置'}>
                    <RoughKeyValueRows
                      rows={(data.explanation.keyLevels ?? []).map((level, index) => ({
                        key: `${level.kind || 'level'}-${index}`,
                        label: level.kind || (locale === 'en' ? 'Level' : '位置'),
                        value: level.value ?? '--',
                        detail: level.description || undefined,
                      }))}
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
