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
  type StockPeerCorrelationSnapshot,
  type StockStructureDecisionResponse,
  type StockValidationResponse,
  type StockSymbolCompareEvidenceEntry,
  type StockSymbolCompareEvidencePacket,
  type StockSymbolCompareFreshness,
} from '../api/stocks';
import { EvidenceGapExplanationList } from '../components/research/EvidenceGapExplanation';
import { useI18n } from '../contexts/UiLanguageContext';
import { cn } from '../utils/cn';
import { getConsumerStatusLabel, mapConsumerStatusText } from '../utils/consumerStatusLabels';
import { buildLocalizedPath, parseLocaleFromPathname } from '../utils/localeRouting';
import { sanitizeUserFacingDataIssue } from '../utils/userFacingDataIssues';
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

const CONSUMER_COPY_UNSAFE_PATTERN =
  /\b(provider|debug|trace|raw|sourceRef|sourceRefId|reasonCode|requestId|cache|schemaVersion|runtime|payload|json|policyVersion|local_db|backend|buy now|sell now|hold|recommend(?:ation)?|target price|stop loss|position sizing)\b|买入|卖出|持有|推荐|目标价|止损|仓位建议/i;

function looksUnsafeForConsumer(value: string | null | undefined): boolean {
  const text = String(value || '').trim();
  if (!text) return false;
  return CONSUMER_COPY_UNSAFE_PATTERN.test(text) || /\b[a-z]+(?:_[a-z0-9]+)+\b/i.test(text);
}

function safeConsumerText(
  value: string | number | null | undefined,
  language: 'zh' | 'en',
  fallback: string,
): string {
  const text = String(value ?? '').trim();
  if (!text) return fallback;
  if (!looksUnsafeForConsumer(text)) return text;
  const sanitized = sanitizeUserFacingDataIssue(text, language);
  return looksUnsafeForConsumer(sanitized) ? fallback : sanitized;
}

function compactUnique(values: string[]): string[] {
  return values.filter((value, index, list) => value && list.indexOf(value) === index);
}

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
  if (looksUnsafeForConsumer(kind)) {
    return language === 'en' ? 'Evidence' : '证据';
  }
  const readable = normalized.replace(/[_-]+/g, ' ').trim();
  return readable || (language === 'en' ? 'Evidence' : '证据');
}

function statusLabel(status: string | null | undefined, language: 'zh' | 'en'): string {
  const consumerLabel = getConsumerStatusLabel(status, language);
  if (consumerLabel) {
    return consumerLabel;
  }
  const normalized = String(status || '').toLowerCase();
  const labels: Record<string, { zh: string; en: string }> = {
    available: { zh: '可用', en: 'available' },
    partial: { zh: '部分可用', en: 'partial' },
    unavailable: { zh: '不可用', en: 'unavailable' },
    degraded: { zh: '降级', en: 'degraded' },
  };
  const mapped = labels[normalized]?.[language];
  if (mapped) return mapped;
  if (looksUnsafeForConsumer(status)) {
    return language === 'en' ? 'not ready' : '暂未就绪';
  }
  return status || '--';
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

function safeEvidenceValue(value: string | number | null | undefined, language: 'zh' | 'en'): string {
  return safeConsumerText(value, language, language === 'en' ? 'Evidence unavailable' : '证据暂不可用');
}

function missingEvidenceCopy(
  symbol: string,
  gap: StockStructureDecisionResponse['missingEvidence'][number],
  language: 'zh' | 'en',
): string {
  const gapKey = String(gap.kind || gap.code || gap.field || '').toLowerCase();
  if (gapKey === 'symbol_validation' || gapKey === 'symbol_not_found' || gapKey === 'invalid_symbol') {
    return language === 'en'
      ? `${symbol} was not found. Check the code, or return to search and choose again.`
      : '标的未找到。未找到该标的，请检查代码是否正确，或返回搜索重新选择。';
  }
  const fallback = language === 'en'
    ? `${symbol} has missing compare evidence.`
    : `${symbol} 的部分对比证据暂未就绪。`;
  const raw = gap.message || gap.kind || gap.code || gap.field || '';
  if (!raw) return fallback;
  if (looksUnsafeForConsumer(raw)) return fallback;
  return safeConsumerText(raw || evidenceKindLabel(gap.kind, language), language, fallback);
}

function safeResearchNextSteps(values: string[], language: 'zh' | 'en'): string[] {
  const fallback = language === 'en'
    ? 'Complete comparable-symbol evidence before reviewing the comparison again.'
    : '补齐可比较标的的基础证据后再复核。';
  return compactUnique(values.map((value) => (
    looksUnsafeForConsumer(value) ? fallback : safeConsumerText(value, language, fallback)
  ))).slice(0, 4);
}

function hasPeerCorrelationContent(snapshot: StockPeerCorrelationSnapshot | null | undefined): snapshot is StockPeerCorrelationSnapshot {
  if (!snapshot) return false;
  return Boolean(
    snapshot.peerGroup.symbols.length
      || snapshot.peerEvidence.length
      || snapshot.divergenceEvidence.length
      || snapshot.staleInputs.length
      || snapshot.missingInputs.length
      || snapshot.researchNextSteps.length,
  );
}

function firstComparablePeerSymbol(
  snapshot: StockPeerCorrelationSnapshot | null | undefined,
  primarySymbol: string,
): string | null {
  if (!snapshot) return null;
  const primary = primarySymbol.toUpperCase();
  return snapshot.peerGroup.symbols
    .map((symbol) => symbol.trim().toUpperCase())
    .find((symbol) => symbol && symbol !== primary) ?? null;
}

function buildComparePath(symbols: string[]): string {
  return `/stocks/${symbols.map((symbol) => encodeURIComponent(symbol)).join(',')}/structure-decision`;
}

function buildCompareEntryPath(symbol: string): string {
  const params = new URLSearchParams();
  if (symbol.trim()) {
    params.set('symbols', symbol.trim().toUpperCase());
  }
  const query = params.toString();
  return query ? `/stocks/structure-decision?${query}` : '/stocks/structure-decision';
}

type SymbolNotFoundState = {
  symbol: string;
};

function isSymbolNotFoundValidation(
  validation: StockValidationResponse | null | undefined,
): validation is StockValidationResponse {
  if (!validation) return false;
  if (validation.exists || validation.valid) return false;
  return ['invalid_format', 'unsupported_market', 'ambiguous', 'not_found'].includes(String(validation.status || ''));
}

function StockStructureSymbolNotFoundState({
  language,
  symbol,
  localize,
}: {
  language: 'zh' | 'en';
  symbol: string;
  localize: (path: string) => string;
}) {
  const isEnglish = language === 'en';
  const actions = [
    {
      to: localize('/research/radar'),
      label: isEnglish ? 'Back to Research Radar' : '返回研究雷达',
    },
    {
      to: localize('/watchlist'),
      label: isEnglish ? 'Back to watchlist' : '返回观察列表',
    },
    {
      to: localize('/'),
      label: isEnglish ? 'Back home' : '返回首页',
    },
  ];

  return (
    <div className="p-4 md:p-5">
      <TerminalEmptyState
        className="items-start md:items-center"
        data-testid="stock-structure-symbol-not-found-state"
        title={isEnglish ? 'Symbol not found' : '标的未找到'}
        action={(
          <div className="flex shrink-0 flex-wrap justify-end gap-2">
            {actions.map((action) => (
              <Link
                key={action.to}
                to={action.to}
                className="inline-flex min-h-9 items-center justify-center rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)]"
              >
                {action.label}
              </Link>
            ))}
          </div>
        )}
      >
        <div className="space-y-1">
          <p>
            {isEnglish
              ? `${symbol || 'The symbol'} was not found. Check the code, or return to search and choose again.`
              : '未找到该标的，请检查代码是否正确，或返回搜索重新选择。'}
          </p>
          <p>
            {isEnglish
              ? 'This means the symbol cannot currently be confirmed, which is different from data that is temporarily missing.'
              : '这表示当前无法确认该标的存在，不等同于数据暂时不可用。'}
          </p>
          <p>
            {isEnglish
              ? 'This is a research observation state only; no investment conclusion is being made.'
              : '仅作研究观察，不生成投资结论。'}
          </p>
        </div>
      </TerminalEmptyState>
    </div>
  );
}

function StockPeerCorrelationEmptyState({
  language,
  localize,
  primarySymbol,
  className,
  testId,
}: {
  language: 'zh' | 'en';
  localize: (path: string) => string;
  primarySymbol: string;
  className?: string;
  testId: string;
}) {
  const isEnglish = language === 'en';
  return (
    <TerminalEmptyState
      className={cn('items-start md:col-span-2 md:items-center', className)}
      data-testid={testId}
      title={isEnglish ? 'No peer evidence entries yet' : '暂无同业证据条目'}
      action={(
        <div className="flex shrink-0 flex-wrap justify-end gap-2">
          <Link
            to={localize(buildCompareEntryPath(primarySymbol))}
            className="inline-flex min-h-9 items-center justify-center rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)]"
          >
            {isEnglish ? 'Add compare symbol' : '添加对比标的'}
          </Link>
          <Link
            to={localize('/research/radar')}
            className="inline-flex min-h-9 items-center justify-center rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)]"
          >
            {isEnglish ? 'Back to Research Radar' : '返回研究雷达'}
          </Link>
        </div>
      )}
    >
      <div className="space-y-1">
        <p>
          {isEnglish
            ? 'Comparable peer evidence is currently unavailable, so the page cannot form a structural difference view across peers yet.'
            : '当前缺少可比较同业证据，因此无法形成同业结构差异观察。'}
        </p>
        <p>
          {isEnglish
            ? 'Add another symbol for structure comparison, or return to Research Radar and enter again from the existing research queue.'
            : '可添加另一个标的进行结构对比，或返回研究雷达从现有研究队列进入。'}
        </p>
        <p>
          {isEnglish
            ? 'This does not rank symbols or imply any investment preference.'
            : '这不表示当前标的优先于其他标的，也不形成投资偏好。'}
        </p>
      </div>
    </TerminalEmptyState>
  );
}

function CompareWithPeerLink({
  language,
  to,
  peerSymbol,
}: {
  language: 'zh' | 'en';
  to: string;
  peerSymbol: string;
}) {
  return (
    <Link
      to={to}
      className="inline-flex w-fit max-w-full items-center justify-center rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)]"
    >
      {language === 'en' ? `Compare evidence with ${peerSymbol}` : `与 ${peerSymbol} 对比证据`}
    </Link>
  );
}

function SymbolCompareEvidencePacketPanel({
  packet,
  language,
  requestedSymbols,
}: {
  packet: StockSymbolCompareEvidencePacket | null;
  language: 'zh' | 'en';
  requestedSymbols: string[];
}) {
  const comparedSymbols = (packet?.comparedSymbols ?? [])
    .map((symbol) => symbol.trim().toUpperCase())
    .filter(Boolean);
  const displaySymbols = [...new Set([
    ...requestedSymbols,
    ...comparedSymbols,
    ...Object.keys(packet?.missingEvidenceBySymbol ?? {}),
    ...Object.keys(packet?.freshnessBySymbol ?? {}),
  ].map((symbol) => symbol.trim().toUpperCase()).filter(Boolean))];

  if (!packet || displaySymbols.length <= 1) {
    const symbolLabel = displaySymbols[0] ?? (language === 'en' ? 'one symbol' : '一个标的');
    const isSingleSymbol = displaySymbols.length <= 1;
    return (
      <div className="grid gap-3 border-t border-[color:var(--wolfy-divider)] p-3" data-testid="symbol-compare-evidence-packet">
        <TerminalEmptyState
          title={isSingleSymbol
            ? (language === 'en' ? 'At least two comparable symbols are required' : '需要至少两个可比较标的')
            : (language === 'en' ? 'Compare evidence is not ready yet' : '对比证据暂未就绪')}
        >
          <div className="space-y-1">
            <p>
              {isSingleSymbol
                ? (language === 'en'
                  ? `Only ${symbolLabel} is available, so shared evidence or divergence evidence cannot be formed yet.`
                  : `当前只有 ${symbolLabel}，暂时不能形成标的间共享证据或分歧证据。`)
                : (language === 'en'
                  ? 'Shared evidence or divergence evidence is still missing for this symbol set.'
                  : '这组标的的共享证据或分歧证据仍缺失。')}
            </p>
            <p>
              {isSingleSymbol
                ? (language === 'en'
                  ? 'Add a comparable peer symbol before reviewing compare evidence.'
                  : '添加同业标的后再查看对比证据。')
                : (language === 'en'
                  ? 'Check stock evidence gaps first, then review the comparison again.'
                  : '先检查个股证据缺口，补齐可比较标的后再复核。')}
            </p>
          </div>
        </TerminalEmptyState>
      </div>
    );
  }

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
          {displaySymbols.map((symbol) => (
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
        {confidenceCapValue != null ? (
          <EvidenceGapExplanationList
            className="mt-3"
            gaps={['confidence_capped']}
            locale={language}
            title={language === 'en' ? 'Confidence impact' : '置信度影响'}
          />
        ) : null}
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
              .map(([symbol, value]) => `${symbol}: ${safeEvidenceValue(value, language)}`)
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
        <div className="grid gap-3">
          {displaySymbols.map((symbol) => {
            const gaps = packet.missingEvidenceBySymbol[symbol] ?? [];
            return (
              <div key={`missing-${symbol}`} className="rounded-xl border border-[color:var(--wolfy-divider)] bg-black/10 px-3 py-2.5">
                <div className="mb-2 font-mono text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{symbol}</div>
                {gaps.length ? (
                  <p className="mb-2 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
                    {gaps.map((gap) => missingEvidenceCopy(symbol, gap, language)).join(language === 'en' ? ' ' : '')}
                  </p>
                ) : null}
                <EvidenceGapExplanationList
                  gaps={gaps}
                  locale={language}
                  title={language === 'en' ? 'Gap explanation' : '缺口解释'}
                  emptyText={language === 'en' ? 'No gap listed' : '暂无缺口'}
                />
              </div>
            );
          })}
        </div>
      </RoughSectionCard>

      <RoughSectionCard title={language === 'en' ? 'Freshness by symbol' : '新鲜度'}>
        <RoughKeyValueRows
          emptyText={language === 'en' ? 'No freshness summary available yet.' : '暂无新鲜度摘要。'}
          rows={displaySymbols.map((symbol) => ({
            key: `freshness-${symbol}`,
            label: symbol,
            value: freshnessMeta(packet.freshnessBySymbol[symbol], language),
          }))}
        />
      </RoughSectionCard>

      <RoughSectionCard className="md:col-span-2" title={language === 'en' ? 'Next research steps' : '后续研究'}>
        <RoughBulletList
          items={safeResearchNextSteps(packet.researchNextSteps, language)}
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
  const [symbolNotFound, setSymbolNotFound] = useState<SymbolNotFoundState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setSymbolNotFound(null);
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
        let validation: StockValidationResponse | null = null;
        try {
          validation = await stocksApi.verifyTickerExists(primarySymbol);
        } catch {
          validation = null;
        }
        if (isSymbolNotFoundValidation(validation)) {
          setData(null);
          setComparePacket(null);
          setSymbolNotFound({
            symbol: validation.normalizedSymbol || validation.stockCode || primarySymbol,
          });
          return;
        }
        const response = await stocksApi.getStructureDecision(primarySymbol);
        setData(response);
        setComparePacket(null);
      }
    } catch (err) {
      setComparePacket(null);
      setSymbolNotFound(null);
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
  const comparablePeerSymbol = useMemo(
    () => firstComparablePeerSymbol(data?.peerCorrelationSnapshot, data?.ticker || primarySymbol),
    [data?.peerCorrelationSnapshot, data?.ticker, primarySymbol],
  );
  const compareWithPeerPath = data && comparablePeerSymbol && !isCompareRequest
    ? localize(buildComparePath([data.ticker || primarySymbol, comparablePeerSymbol]))
    : null;
  const introTitle = symbolNotFound
    ? (locale === 'en' ? 'Symbol not found' : '标的未找到')
    : (locale === 'en' ? `${titleSymbol} structure workspace` : `${titleSymbol} 结构工作区`);
  const introDescription = symbolNotFound
    ? (locale === 'en'
      ? 'Check the code or return to a research entrypoint; this is different from evidence that is temporarily missing.'
      : '请检查代码是否正确，或返回研究入口重新选择；这不同于证据暂时缺失。')
    : (locale === 'en'
      ? 'This panel keeps structure state, confidence, component scores, research notes, and evidence gaps together before the name moves into watchlist or portfolio context.'
      : '这个面板把结构状态、置信度、组件评分、研究备注与证据缺口放在同一页，再决定是否沉淀到观察列表或组合上下文。');

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
                <EvidenceGapExplanationList
                  gaps={data?.missingEvidence ?? []}
                  locale={locale}
                  title={locale === 'en' ? 'Gap explanation' : '缺口解释'}
                  emptyText={locale === 'en' ? 'No explicit gap' : '暂无明确缺口'}
                />
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
              title={introTitle}
              description={introDescription}
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
            {!loading && !error && symbolNotFound ? (
              <StockStructureSymbolNotFoundState
                language={locale}
                symbol={symbolNotFound.symbol}
                localize={localize}
              />
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
                      value: <StatusBadge status={toneFor(data.dataQuality.status)} label={statusLabel(data.dataQuality.status, locale)} size="sm" />,
                    },
                    {
                      label: locale === 'en' ? 'Period' : '周期',
                      value: periodLabel(data.dataQuality.period, locale) || '--',
                    },
                  ]}
                />
                <MetricStrip
                  items={[
                    {
                      key: 'state',
                      label: locale === 'en' ? 'Structure state' : '结构状态',
                      value: safeConsumerText(data.structureState, locale, locale === 'en' ? 'Under review' : '待确认'),
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
                <SymbolCompareEvidencePacketPanel
                  packet={comparePacket}
                  language={locale}
                  requestedSymbols={requestedSymbols}
                />
                <div className="grid gap-3 p-3 md:grid-cols-2">
                  <RoughSectionCard
                    className="md:col-span-2"
                    eyebrow={locale === 'en' ? 'Boundary' : '边界'}
                    title={locale === 'en' ? 'Evidence gap explanations' : '证据缺口解释'}
                  >
                    <EvidenceGapExplanationList
                      data-testid="stock-structure-evidence-gap-explanations"
                      gaps={data.missingEvidence ?? []}
                      locale={locale}
                      title={locale === 'en' ? 'Gap explanation' : '缺口解释'}
                      emptyText={locale === 'en' ? 'No explicit gap' : '暂无明确缺口'}
                    />
                  </RoughSectionCard>
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Scores' : '评分'} title={locale === 'en' ? 'Component scores' : '组件评分'}>
                    <RoughScoreRows
                      items={scoreRows}
                      emptyText={locale === 'en' ? 'No component score yet.' : '暂无组件评分。'}
                    />
                  </RoughSectionCard>
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Structure logic' : '结构逻辑'} title={locale === 'en' ? 'Why this structure' : '结构解释'}>
                    <RoughKeyValueRows
                      emptyText={locale === 'en' ? 'No structure explanation available yet.' : '暂无结构解释。'}
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
                      emptyText={locale === 'en' ? 'No research note available yet.' : '暂无研究备注。'}
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
                          value: (data.researchNotes.riskFlags ?? []).map((flag) => mapConsumerStatusText(flag, locale)).join('；') || '--',
                        },
                      ]}
                    />
                  </RoughSectionCard>
                  {hasPeerCorrelationContent(data.peerCorrelationSnapshot) ? (
                    <>
                      <PeerCorrelationSnapshotBlock
                        snapshot={data.peerCorrelationSnapshot}
                        locale={locale}
                        testId="stock-structure-peer-correlation-snapshot"
                        className="md:col-span-2"
                      />
                      {compareWithPeerPath && comparablePeerSymbol ? (
                        <div className="md:col-span-2">
                          <CompareWithPeerLink
                            language={locale}
                            to={compareWithPeerPath}
                            peerSymbol={comparablePeerSymbol}
                          />
                        </div>
                      ) : null}
                    </>
                  ) : (
                    <StockPeerCorrelationEmptyState
                      language={locale}
                      localize={localize}
                      primarySymbol={data.ticker || primarySymbol}
                      testId="stock-structure-peer-correlation-snapshot"
                      className="md:col-span-2"
                    />
                  )}
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Reference levels' : '参考位置'} title={locale === 'en' ? 'Key levels' : '关键位置'}>
                    <RoughKeyValueRows
                      emptyText={locale === 'en' ? 'No key level available yet.' : '暂无关键位置。'}
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
