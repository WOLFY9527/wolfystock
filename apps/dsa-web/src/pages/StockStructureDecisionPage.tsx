import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import { Copy, Download } from 'lucide-react';
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
  type StockQuote,
  type SymbolResearchPacket,
  type StockPeerCorrelationSnapshot,
  type StockStructureDecisionResponse,
  type StockValidationResponse,
  type StockSymbolCompareEvidenceEntry,
  type StockSymbolCompareEvidencePacket,
  type StockSymbolCompareFreshness,
} from '../api/stocks';
import { optionsLabApi, type OptionsStructureSummary, type OptionContractStructureRow } from '../api/optionsLab';
import { EvidenceGapExplanationList } from '../components/research/EvidenceGapExplanation';
import { useI18n } from '../contexts/UiLanguageContext';
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
  /\b(sourceAuthority|source_authority|score-grade|score_grade|proxy-only|proxy_only|provider|debug|trace|traceId|raw|sourceRef|sourceRefId|reasonCode|requestId|cache|schema|schemaVersion|runtime|payload|json|policyVersion|local_db|backend|fallback|observation-only|observation_only|evidence families|evidence_families|insufficient_evidence|ohlcv|buy now|sell now|hold|recommend(?:ation)?|target price|stop loss|position sizing)\b|买入|卖出|持有|推荐|目标价|止损|仓位建议/i;

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

function safeOptionalConsumerText(
  value: string | number | null | undefined,
  language: 'zh' | 'en',
): string | null {
  const text = String(value ?? '').trim();
  if (!text || text === '--') return null;
  const safe = safeConsumerText(text, language, '');
  return safe.trim() || null;
}

function safeConsumerList(values: Array<string | null | undefined>, language: 'zh' | 'en'): string[] {
  return compactUnique(values
    .map((value) => safeOptionalConsumerText(value, language))
    .filter(Boolean) as string[]);
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

function confidenceCapLabel(value: unknown, language: 'zh' | 'en'): string {
  if (value == null || value === '') return '--';
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  return confidenceLabel(String(value), language);
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
    daily_ohlcv: { zh: '日线数据', en: 'Daily price history' },
    benchmark_ohlcv: { zh: '基准日线数据', en: 'Benchmark price history' },
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
    available: { zh: '可用', en: 'Ready' },
    partial: { zh: '部分可用', en: 'Partial' },
    unavailable: { zh: '不可用', en: 'Not ready' },
    degraded: { zh: '降级', en: 'Degraded' },
  };
  const mapped = labels[normalized]?.[language];
  if (mapped) return mapped;
  if (looksUnsafeForConsumer(status)) {
    return language === 'en' ? 'not ready' : '暂未就绪';
  }
  return status || '--';
}

function normalizeStockConsumerToken(value: string | null | undefined): string {
  return String(value || '')
    .trim()
    .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
    .toLowerCase()
    .replace(/[:=./\\\s-]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '');
}

function stockStructureStateLabel(value: string | null | undefined, language: 'zh' | 'en'): string | null {
  const token = normalizeStockConsumerToken(value);
  if (!token) return null;
  const labels: Record<string, { zh: string; en: string }> = {
    accumulation: { zh: '吸筹阶段', en: 'Accumulation phase' },
    breakdown: { zh: '结构走弱', en: 'Structure under pressure' },
    breakout: { zh: '突破观察', en: 'Breakout watch' },
    distribution: { zh: '派发压力', en: 'Distribution pressure' },
    low_confidence: { zh: '证据不足', en: 'Evidence limited' },
    mixed: { zh: '结构分化', en: 'Mixed structure' },
    neutral: { zh: '结构中性', en: 'Neutral structure' },
    pullback: { zh: '回撤观察', en: 'Pullback watch' },
    range: { zh: '区间震荡', en: 'Range-bound' },
    insufficient_evidence: { zh: '证据不足', en: 'Evidence limited' },
    unavailable: { zh: '数据暂缺', en: 'Data temporarily missing' },
  };
  const mapped = labels[token]?.[language];
  if (mapped) return mapped;
  return safeOptionalConsumerText(mapConsumerStatusText(value, language), language);
}

function periodLabel(period: string | null | undefined, language: 'zh' | 'en'): string | null {
  if (!period) return null;
  const normalized = String(period).toLowerCase();
  if (normalized === 'daily') return language === 'en' ? 'Daily' : '日线';
  if (normalized === 'weekly') return language === 'en' ? 'Weekly' : '周线';
  return String(period);
}

const QUOTE_TIMESTAMP_FORMATTERS = {
  en: new Intl.DateTimeFormat('en-US', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }),
  zh: new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }),
} as const;

type QuoteBoundaryChipVariant = 'success' | 'caution' | 'danger' | 'info' | 'neutral';

type QuoteBoundaryChip = {
  label: string;
  variant: QuoteBoundaryChipVariant;
};

type QuoteBoundaryView = {
  title: string;
  detail: string;
  chips: QuoteBoundaryChip[];
};

function formatQuoteTimestamp(value: string | null | undefined, language: 'zh' | 'en'): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return QUOTE_TIMESTAMP_FORMATTERS[language].format(date);
}

const OPTIONS_STRUCTURE_NUMBER_FORMATTERS = {
  en: new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }),
  zh: new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }),
} as const;

const OPTIONS_STRUCTURE_INTEGER_FORMATTERS = {
  en: new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }),
  zh: new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 0 }),
} as const;

const OPTIONS_STRUCTURE_PERCENT_FORMATTERS = {
  en: new Intl.NumberFormat('en-US', { style: 'percent', maximumFractionDigits: 1 }),
  zh: new Intl.NumberFormat('zh-CN', { style: 'percent', maximumFractionDigits: 1 }),
} as const;

type OptionsStructureMetricRow = {
  key: string;
  label: string;
  value: string;
  detail: string;
};

function formatOptionsNumber(value: number | null | undefined, language: 'zh' | 'en'): string | null {
  return typeof value === 'number' && Number.isFinite(value)
    ? OPTIONS_STRUCTURE_NUMBER_FORMATTERS[language].format(value)
    : null;
}

function formatOptionsInteger(value: number | null | undefined, language: 'zh' | 'en'): string | null {
  return typeof value === 'number' && Number.isFinite(value)
    ? OPTIONS_STRUCTURE_INTEGER_FORMATTERS[language].format(value)
    : null;
}

function formatOptionsPercent(value: number | null | undefined, language: 'zh' | 'en'): string | null {
  return typeof value === 'number' && Number.isFinite(value)
    ? OPTIONS_STRUCTURE_PERCENT_FORMATTERS[language].format(value)
    : null;
}

function optionsMissingValue(language: 'zh' | 'en'): string {
  return language === 'en' ? 'Needs evidence' : '待补证';
}

function optionsStructureStatusCopy(
  structure: OptionsStructureSummary,
  language: 'zh' | 'en',
): { label: string; detail: string; badge: QuoteBoundaryChipVariant } {
  const status = normalizeStockConsumerToken(structure.status);
  if (status === 'available') {
    return {
      label: language === 'en' ? 'Structure available' : '结构可用',
      detail: language === 'en'
        ? 'Options structure analytics are populated from the current contract.'
        : '期权结构指标已由当前合约填充。',
      badge: 'success',
    };
  }
  if (status === 'degraded') {
    return {
      label: language === 'en' ? 'Structure degraded' : '结构降级',
      detail: language === 'en'
        ? 'Some professional metrics are present, but missing inputs still cap the read.'
        : '部分专业指标可见，但仍有输入缺口。',
      badge: 'caution',
    };
  }
  return {
    label: language === 'en' ? 'Structure not available' : '结构暂不可用',
    detail: structure.providerConfigured
      ? (language === 'en'
        ? 'The structure endpoint is reachable, but usable metrics are not present.'
        : '结构接口已返回，但可用指标暂未出现。')
      : (language === 'en'
        ? 'An authorized options structure source is still needed before metrics populate.'
        : '仍需配置授权期权结构来源后才会填充指标。'),
    badge: 'caution',
  };
}

function optionsStructureSourceLabel(structure: OptionsStructureSummary, language: 'zh' | 'en'): string {
  return structure.providerConfigured
    ? (language === 'en' ? 'Structure source configured' : '结构来源已配置')
    : (language === 'en' ? 'Structure source needed' : '结构来源待配置');
}

function optionsStructureFreshnessLabel(structure: OptionsStructureSummary, language: 'zh' | 'en'): string {
  const timestamp = formatQuoteTimestamp(structure.asOf || structure.snapshot.asOf || null, language);
  const freshness = normalizeStockConsumerToken(structure.freshness || structure.snapshot.freshness);
  if (timestamp) return `${language === 'en' ? 'Updated' : '更新'} ${timestamp}`;
  if (freshness && freshness !== 'unknown') {
    if (freshness === 'live' || freshness === 'fresh') return language === 'en' ? 'Latest available' : '最新可用';
    if (freshness === 'stale' || freshness === 'delayed') return language === 'en' ? 'May be delayed' : '可能延迟';
  }
  return language === 'en' ? 'Freshness pending' : '新鲜度待确认';
}

function optionsStructureReasonLabel(value: string, language: 'zh' | 'en'): string {
  const token = normalizeStockConsumerToken(value);
  const labels: Record<string, { zh: string; en: string }> = {
    options_structure_provider_missing: { zh: '结构来源待配置', en: 'Structure source needed' },
    configure_authorized_options_structure_provider: { zh: '待配置授权结构来源', en: 'Authorized structure source needed' },
    not_available: { zh: '结构暂不可用', en: 'Structure not available' },
    degraded: { zh: '结构降级', en: 'Structure degraded' },
    missing_inputs: { zh: '关键输入待补', en: 'Inputs needed' },
  };
  return labels[token]?.[language] ?? (language === 'en' ? 'Evidence needed' : '证据待补');
}

function optionsStructureReasonLabels(structure: OptionsStructureSummary, language: 'zh' | 'en'): string[] {
  return compactUnique([
    ...structure.blockingReasons,
    ...structure.warnings,
    ...structure.nextEvidenceNeeded,
  ].map((value) => optionsStructureReasonLabel(value, language))).slice(0, 4);
}

function sumContractMetric(
  contracts: OptionContractStructureRow[],
  key: 'charm' | 'vanna',
): number | null {
  const values = contracts
    .map((contract) => contract[key])
    .filter((value): value is number => typeof value === 'number' && Number.isFinite(value));
  if (!values.length) return null;
  return values.reduce((total, value) => total + value, 0);
}

function sumExpirationMetric(
  structure: OptionsStructureSummary,
  key: 'callOpenInterest' | 'putOpenInterest' | 'callVolume' | 'putVolume',
): number | null {
  if (!structure.expirationSummaries.length) return null;
  return structure.expirationSummaries.reduce((total, row) => total + (row[key] || 0), 0);
}

function buildOptionsStructureMetrics(
  structure: OptionsStructureSummary,
  language: 'zh' | 'en',
): OptionsStructureMetricRow[] {
  const missing = optionsMissingValue(language);
  const gex = formatOptionsNumber(structure.totalDealerGammaExposure, language);
  const gammaFlip = structure.gammaFlipLevel.state === 'available'
    ? formatOptionsNumber(structure.gammaFlipLevel.level, language)
    : null;
  const vanna = formatOptionsNumber(sumContractMetric(structure.snapshot.contracts, 'vanna'), language);
  const charm = formatOptionsNumber(sumContractMetric(structure.snapshot.contracts, 'charm'), language);
  const zeroDteOiShare = formatOptionsPercent(structure.zeroDte.openInterestShare, language);
  const zeroDteVolumeShare = formatOptionsPercent(structure.zeroDte.volumeShare, language);
  const zeroDteValue = structure.zeroDte.state === 'available'
    ? [
      zeroDteOiShare ? `OI ${zeroDteOiShare}` : null,
      zeroDteVolumeShare ? `${language === 'en' ? 'Vol' : '成交'} ${zeroDteVolumeShare}` : null,
    ].filter(Boolean).join(' · ') || formatOptionsInteger(structure.zeroDte.contractCount, language)
    : null;
  const callOpenInterest = sumExpirationMetric(structure, 'callOpenInterest') ?? 0;
  const putOpenInterest = sumExpirationMetric(structure, 'putOpenInterest') ?? 0;
  const callVolume = sumExpirationMetric(structure, 'callVolume') ?? 0;
  const putVolume = sumExpirationMetric(structure, 'putVolume') ?? 0;
  const totalOi = callOpenInterest + putOpenInterest;
  const totalVolume = callVolume + putVolume;
  const hasOiVolume = totalOi > 0 || totalVolume > 0;

  return [
    {
      key: 'gex',
      label: 'GEX',
      value: gex ?? missing,
      detail: gex ? 'Dealer gamma exposure' : (language === 'en' ? 'Awaiting authorized inputs' : '等待授权输入'),
    },
    {
      key: 'gamma-flip',
      label: 'Gamma flip',
      value: gammaFlip ?? missing,
      detail: gammaFlip ? (language === 'en' ? 'Flip level populated' : '翻转位置已填充') : (language === 'en' ? 'Methodology evidence needed' : '方法与输入待补'),
    },
    {
      key: 'vanna',
      label: 'Vanna',
      value: vanna ?? missing,
      detail: vanna ? (language === 'en' ? 'Contract values summed' : '合约值汇总') : (language === 'en' ? 'Vanna not present' : 'Vanna 暂缺'),
    },
    {
      key: 'charm',
      label: 'Charm',
      value: charm ?? missing,
      detail: charm ? (language === 'en' ? 'Contract values summed' : '合约值汇总') : (language === 'en' ? 'Charm not present' : 'Charm 暂缺'),
    },
    {
      key: 'zero-dte',
      label: language === 'en' ? '0DTE concentration' : '0DTE 集中度',
      value: zeroDteValue ?? missing,
      detail: structure.zeroDte.state === 'available'
        ? (language === 'en'
          ? `${structure.zeroDte.expiration || 'nearest'} · ${structure.zeroDte.contractCount} contracts`
          : `${structure.zeroDte.expiration || '最近到期'} · ${structure.zeroDte.contractCount} 张合约`)
        : (language === 'en' ? '0DTE bucket not present' : '0DTE 桶暂缺'),
    },
    {
      key: 'oi-volume',
      label: language === 'en' ? 'OI / volume' : 'OI / 成交',
      value: hasOiVolume
        ? `${formatOptionsInteger(totalOi, language)} / ${formatOptionsInteger(totalVolume, language)}`
        : missing,
      detail: language === 'en' ? 'Expiration summaries' : '到期汇总',
    },
  ];
}

function OptionsStructureSurface({
  structure,
  failed,
  loading,
  language,
}: {
  structure: OptionsStructureSummary | null;
  failed: boolean;
  loading: boolean;
  language: 'zh' | 'en';
}) {
  if (loading) {
    return (
      <div className="p-3 md:p-4">
        <RoughSectionCard
          data-testid="stock-options-structure-surface"
          eyebrow={language === 'en' ? 'Options structure' : '期权结构'}
          title={language === 'en' ? 'Loading options structure' : '正在载入期权结构'}
        >
          <div className="grid gap-2 sm:grid-cols-3">
            {[0, 1, 2].map((item) => (
              <div key={item} className="h-16 rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-subtle)]" />
            ))}
          </div>
        </RoughSectionCard>
      </div>
    );
  }

  if (failed) {
    return (
      <div className="p-3 md:p-4">
        <RoughSectionCard
          data-testid="stock-options-structure-surface"
          eyebrow={language === 'en' ? 'Options structure' : '期权结构'}
          title={language === 'en' ? 'Options structure unavailable' : '期权结构暂不可用'}
        >
          <div className="flex flex-wrap gap-2">
            <StatusBadge status="caution" label={language === 'en' ? 'Endpoint unavailable' : '接口暂不可用'} size="sm" />
            <StatusBadge status="neutral" label={language === 'en' ? 'No metrics inferred' : '不推断指标'} size="sm" />
          </div>
          <p className="mt-3 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
            {language === 'en'
              ? 'The options structure endpoint did not return. GEX, gamma flip, vanna, charm, 0DTE, OI, and volume remain empty.'
              : '期权结构接口未返回。GEX、gamma flip、vanna、charm、0DTE、OI 与成交量均保持待补。'}
          </p>
        </RoughSectionCard>
      </div>
    );
  }

  if (!structure) return null;

  const status = optionsStructureStatusCopy(structure, language);
  const reasons = optionsStructureReasonLabels(structure, language);
  const metrics = buildOptionsStructureMetrics(structure, language);

  return (
    <div className="p-3 md:p-4">
      <RoughSectionCard
        data-testid="stock-options-structure-surface"
        eyebrow={language === 'en' ? 'Options structure' : '期权结构'}
        title={language === 'en' ? 'Professional structure metrics' : '专业结构指标'}
      >
        <div className="flex flex-wrap gap-2">
          <StatusBadge status={status.badge} label={status.label} size="sm" />
          <StatusBadge status={structure.providerConfigured ? 'success' : 'caution'} label={optionsStructureSourceLabel(structure, language)} size="sm" />
          <StatusBadge status="neutral" label={optionsStructureFreshnessLabel(structure, language)} size="sm" />
          {structure.observationOnly || !structure.decisionGrade ? (
            <StatusBadge status="neutral" label={language === 'en' ? 'Observation only' : '仅观察'} size="sm" />
          ) : null}
        </div>
        <p className="mt-3 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">{status.detail}</p>
        {reasons.length ? (
          <div className="mt-3 flex flex-wrap gap-2" data-testid="stock-options-structure-reasons">
            {reasons.map((reason) => (
              <StatusBadge key={reason} status="caution" label={reason} size="sm" />
            ))}
          </div>
        ) : null}
        <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-3" data-testid="stock-options-structure-metrics">
          {metrics.map((metric) => (
            <div key={metric.key} className="rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-subtle)] p-3">
              <div className="text-[11px] font-semibold uppercase tracking-normal text-[color:var(--wolfy-text-muted)]">{metric.label}</div>
              <div className="mt-1 text-lg font-semibold text-[color:var(--wolfy-text-primary)]">{metric.value}</div>
              <div className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">{metric.detail}</div>
            </div>
          ))}
        </div>
      </RoughSectionCard>
    </div>
  );
}

function normalizeQuoteBoundaryToken(value: string | null | undefined): string {
  return String(value || '').trim().toLowerCase().replace(/[-\s]+/g, '_');
}

function quoteBoundaryStateLabel(quote: StockQuote, language: 'zh' | 'en'): { label: string; variant: QuoteBoundaryChipVariant } {
  const sourceConfidence = quote.sourceConfidence;
  const freshness = normalizeQuoteBoundaryToken(sourceConfidence?.freshness || quote.freshness);
  const synthetic = Boolean(sourceConfidence?.isSynthetic || quote.isSynthetic || freshness === 'synthetic');
  const stale = Boolean(sourceConfidence?.isStale || quote.isStale || freshness === 'stale' || freshness === 'delayed');
  const unavailable = Boolean(sourceConfidence?.isUnavailable || freshness === 'unavailable');
  const partial = Boolean(sourceConfidence?.isPartial || quote.isPartial);

  if (synthetic) {
    return {
      label: language === 'en' ? 'Sample quote' : '样本报价',
      variant: 'info',
    };
  }
  if (unavailable) {
    return {
      label: language === 'en' ? 'Quote needed' : '报价待补',
      variant: 'caution',
    };
  }
  if (stale || partial) {
    return {
      label: language === 'en' ? 'Quote may be delayed' : '报价可能延迟',
      variant: 'caution',
    };
  }
  if (normalizeQuoteBoundaryToken(quote.freshness) || quote.currentPrice != null) {
    return {
      label: language === 'en' ? 'Quote ready' : '报价可用',
      variant: 'success',
    };
  }
  return {
    label: language === 'en' ? 'Quote pending' : '报价待确认',
    variant: 'caution',
  };
}

function quoteBoundarySourceLabel(quote: StockQuote, language: 'zh' | 'en'): { label: string; variant: QuoteBoundaryChipVariant } {
  const sourceConfidence = quote.sourceConfidence;
  if (!sourceConfidence) {
    return {
      label: language === 'en' ? 'Source pending' : '来源待确认',
      variant: 'caution',
    };
  }

  if (sourceConfidence.isSynthetic || normalizeQuoteBoundaryToken(sourceConfidence.freshness) === 'synthetic') {
    return {
      label: language === 'en' ? 'Sample / demo' : '样本 / 演示',
      variant: 'info',
    };
  }
  if (sourceConfidence.isUnavailable || sourceConfidence.isPartial) {
    return {
      label: language === 'en' ? 'Source pending' : '来源待确认',
      variant: 'caution',
    };
  }
  if (sourceConfidence.isStale || normalizeQuoteBoundaryToken(sourceConfidence.freshness) === 'stale') {
    return {
      label: language === 'en' ? 'Source may be delayed' : '来源可能延迟',
      variant: 'caution',
    };
  }
  return {
    label: language === 'en' ? 'Source confirmed' : '来源已确认',
    variant: 'success',
  };
}

function quoteBoundaryFreshnessLabel(quote: StockQuote, language: 'zh' | 'en'): { label: string; variant: QuoteBoundaryChipVariant } {
  const sourceConfidence = quote.sourceConfidence;
  const freshness = normalizeQuoteBoundaryToken(sourceConfidence?.freshness || quote.freshness);

  if (sourceConfidence?.isSynthetic || freshness === 'synthetic') {
    return {
      label: language === 'en' ? 'Sample / demo' : '样本 / 演示',
      variant: 'info',
    };
  }
  if (sourceConfidence?.isUnavailable || freshness === 'unavailable') {
    return {
      label: language === 'en' ? 'Unavailable' : '暂不可用',
      variant: 'danger',
    };
  }
  if (sourceConfidence?.isStale || quote.isStale || freshness === 'stale' || freshness === 'delayed') {
    return {
      label: language === 'en' ? 'May be delayed' : '可能延迟',
      variant: 'caution',
    };
  }
  if (freshness === 'live' || freshness === 'fresh') {
    return {
      label: language === 'en' ? 'Latest available' : '最新可用',
      variant: 'success',
    };
  }
  return {
    label: language === 'en' ? 'Freshness pending' : '新鲜度待确认',
    variant: 'caution',
  };
}

function buildQuoteBoundaryView(
  quote: StockQuote | null,
  quoteFailed: boolean,
  language: 'zh' | 'en',
): QuoteBoundaryView | null {
  if (!quote && !quoteFailed) return null;
  if (!quote) {
    return {
      title: language === 'en' ? 'Quote boundary unavailable' : '报价边界暂不可用',
      detail: language === 'en'
        ? 'The quote boundary is unavailable, so keep this symbol in observation mode.'
        : '报价边界暂不可用，先按观察处理。',
      chips: [
        {
          label: language === 'en' ? 'Source pending' : '来源待确认',
          variant: 'caution',
        },
        {
          label: language === 'en' ? 'Observation only' : '仅观察',
          variant: 'neutral',
        },
      ],
    };
  }

  const state = quoteBoundaryStateLabel(quote, language);
  const source = quoteBoundarySourceLabel(quote, language);
  const freshness = quoteBoundaryFreshnessLabel(quote, language);
  const asOf = formatQuoteTimestamp(
    quote.sourceConfidence?.asOf || quote.marketTimestamp || quote.observedAt || quote.updateTime || null,
    language,
  );
  const detail = source.label === (language === 'en' ? 'Sample / demo' : '样本 / 演示')
    ? (language === 'en'
      ? 'Sample or demo data is visible for observation only.'
      : '当前为样本/演示数据，仅供观察。')
    : source.label === (language === 'en' ? 'Source pending' : '来源待确认')
      ? (language === 'en'
        ? 'The quote was returned, but the source boundary was not provided.'
        : '报价已返回，但来源边界未提供。')
      : state.label === (language === 'en' ? 'Quote may be delayed' : '报价可能延迟')
        ? (language === 'en'
          ? 'The quote boundary may be delayed, so read it as observation only.'
          : '报价边界可能延迟，先按观察处理。')
        : (language === 'en'
          ? 'This quote boundary is for research observation only.'
          : '该报价边界仅供研究观察。');

  return {
    title: language === 'en' ? 'Quote source and freshness' : '报价来源与新鲜度',
    detail,
    chips: [
      state,
      source,
      freshness,
      asOf ? {
        label: `${language === 'en' ? 'Updated' : '更新'} ${asOf}`,
        variant: 'neutral',
      } : null,
    ].filter(Boolean) as QuoteBoundaryChip[],
  };
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
  const mapped = typeof value === 'string' ? stockStructureStateLabel(value, language) : null;
  return mapped || safeConsumerText(value, language, language === 'en' ? 'Evidence pending' : '证据暂不可用');
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

type SymbolNotFoundState = {
  symbol: string;
};

type StockResearchFact = {
  key: string;
  label: string;
  value: string;
  detail?: string;
};

type EvidenceStackBucket = 'available' | 'missing' | 'partial' | 'stale';

type EvidenceStackRow = {
  key: string;
  label: string;
  value: string;
  bucket: EvidenceStackBucket;
};

type SingleStockEvidencePackEntry = {
  packKey: string;
  label: string;
  state: 'available' | 'unavailable';
  description: string;
  contents: string[];
  exportContent: string | null;
  fileName: string;
  copyLabel: string;
  downloadLabel: string;
  copyTestId: string;
  downloadTestId: string;
  blockedCopyTestId: string;
};

function evidenceStateBucket(value: string | null | undefined): EvidenceStackBucket {
  const token = normalizeStockConsumerToken(value);
  if (token === 'available' || token === 'ready') return 'available';
  if (token === 'stale' || token === 'delayed') return 'stale';
  if (token === 'partial' || token === 'insufficient') return 'partial';
  return 'missing';
}

function quoteEvidenceLabel(value: string | null | undefined, language: 'zh' | 'en'): string {
  const bucket = evidenceStateBucket(value);
  if (bucket === 'available') return language === 'en' ? 'Quote ready' : '报价可用';
  if (bucket === 'stale') return language === 'en' ? 'Quote may be delayed' : '报价可能延迟';
  return language === 'en' ? 'Quote needed' : '报价待补';
}

function historyEvidenceLabel(value: string | null | undefined, language: 'zh' | 'en'): string {
  const bucket = evidenceStateBucket(value);
  if (bucket === 'available') return language === 'en' ? 'History ready' : '历史可用';
  if (bucket === 'stale') return language === 'en' ? 'History may be stale' : '历史可能延迟';
  return language === 'en' ? 'History needed' : '历史待补';
}

function identityEvidenceLabel(bucket: EvidenceStackBucket, language: 'zh' | 'en'): string {
  return bucket === 'available'
    ? (language === 'en' ? 'Symbol context ready' : '标的上下文可用')
    : (language === 'en' ? 'Symbol context needed' : '标的上下文待补');
}

function fundamentalsEvidenceLabel(value: string | null | undefined, language: 'zh' | 'en'): string {
  return evidenceStateBucket(value) === 'available'
    ? (language === 'en' ? 'Fundamentals ready' : '基本面可用')
    : (language === 'en' ? 'Fundamentals needed' : '基本面待补');
}

function newsEvidenceLabel(value: string | null | undefined, hasLatest: boolean, language: 'zh' | 'en'): string {
  return evidenceStateBucket(value) === 'available' || hasLatest
    ? (language === 'en' ? 'News leads ready' : '新闻线索可用')
    : (language === 'en' ? 'News leads needed' : '新闻线索待补');
}

function riskEvidenceLabel(bucket: EvidenceStackBucket, language: 'zh' | 'en'): string {
  return bucket === 'available'
    ? (language === 'en' ? 'Risk source ready' : '风险来源可用')
    : (language === 'en' ? 'Risk source needed' : '风险来源待补');
}

function marketEvidenceLabel(bucket: EvidenceStackBucket, language: 'zh' | 'en'): string {
  return bucket === 'available'
    ? (language === 'en' ? 'Market context ready' : '市场线索可用')
    : (language === 'en' ? 'Market context needed' : '市场线索待补');
}

function researchPacketEvidenceLabel(value: string | null | undefined, language: 'zh' | 'en'): string {
  const token = normalizeStockConsumerToken(value);
  return token === 'blocked' || token === 'unknown'
    ? (language === 'en' ? 'Research packet pending' : '研究包待生成')
    : (language === 'en' ? 'Research packet ready' : '研究包可用');
}

function missingDataLabel(value: string, language: 'zh' | 'en'): string {
  const token = normalizeStockConsumerToken(value);
  const labels: Record<string, { zh: string; en: string }> = {
    quote: { zh: '报价', en: 'quote' },
    price_history: { zh: '历史', en: 'history' },
    history: { zh: '历史', en: 'history' },
    structure_analysis: { zh: '结构', en: 'structure' },
    structure: { zh: '结构', en: 'structure' },
    fundamentals: { zh: '基本面', en: 'fundamentals' },
    filing_event_catalyst: { zh: '事件', en: 'events' },
    events: { zh: '事件', en: 'events' },
    peer_benchmark: { zh: '同业', en: 'peer' },
    peer: { zh: '同业', en: 'peer' },
  };
  return labels[token]?.[language] ?? (language === 'en' ? 'data' : '资料');
}

function hasMissingData(packet: SymbolResearchPacket, tokens: string[]): boolean {
  const normalized = packet.missingData.map(normalizeStockConsumerToken);
  return tokens.some((token) => normalized.includes(token));
}

function buildEvidenceGapLabels(packet: SymbolResearchPacket, language: 'zh' | 'en'): string[] {
  const labels = packet.missingData.map((item) => {
    const token = normalizeStockConsumerToken(item);
    if (token === 'quote') return language === 'en' ? 'Quote needed' : '报价待补';
    if (token === 'history' || token === 'price_history') return language === 'en' ? 'History needed' : '历史待补';
    if (token === 'fundamentals') return language === 'en' ? 'Fundamentals needed' : '基本面待补';
    if (token === 'events' || token === 'filing_event_catalyst') return language === 'en' ? 'News leads needed' : '新闻线索待补';
    if (token === 'peer' || token === 'peer_benchmark' || token === 'market_context') return language === 'en' ? 'Market context needed' : '市场线索待补';
    if (token === 'structure' || token === 'risk') return language === 'en' ? 'Risk source needed' : '风险来源待补';
    return language === 'en' ? `${missingDataLabel(item, language)} needed` : `${missingDataLabel(item, language)}待补`;
  });
  return compactUnique(labels).slice(0, 5);
}

function buildEvidenceStackRows(packet: SymbolResearchPacket, language: 'zh' | 'en'): EvidenceStackRow[] {
  const hasSymbolContext = Boolean(
    packet.identity.name
      || packet.identity.exchange
      || packet.identity.sector
      || packet.identity.industry,
  );
  const hasMarketContext = Boolean(
    packet.identity.exchange
      || packet.identity.sector
      || packet.identity.industry
      || packet.peer.benchmark,
  ) && !hasMissingData(packet, ['peer_benchmark', 'market_context']);
  const riskBucket = evidenceStateBucket(packet.structure.state);
  const packetBucket = evidenceStateBucket(packet.researchStatus);
  return [
    {
      key: 'quote',
      label: language === 'en' ? 'Quote' : '报价',
      value: quoteEvidenceLabel(packet.quote.state, language),
      bucket: evidenceStateBucket(packet.quote.state),
    },
    {
      key: 'symbol-context',
      label: language === 'en' ? 'Symbol context' : '标的上下文',
      value: identityEvidenceLabel(hasSymbolContext ? 'available' : 'missing', language),
      bucket: hasSymbolContext ? 'available' : 'missing',
    },
    {
      key: 'history',
      label: language === 'en' ? 'History' : '历史',
      value: historyEvidenceLabel(packet.history.state, language),
      bucket: evidenceStateBucket(packet.history.state),
    },
    {
      key: 'fundamentals',
      label: language === 'en' ? 'Fundamentals' : '基本面',
      value: fundamentalsEvidenceLabel(packet.fundamentals.state, language),
      bucket: evidenceStateBucket(packet.fundamentals.state),
    },
    {
      key: 'news',
      label: language === 'en' ? 'News / events' : '新闻 / 事件',
      value: newsEvidenceLabel(packet.events.state, packet.events.latest.length > 0, language),
      bucket: packet.events.latest.length > 0 ? 'available' : evidenceStateBucket(packet.events.state),
    },
    {
      key: 'risk',
      label: language === 'en' ? 'Risk source' : '风险来源',
      value: riskEvidenceLabel(riskBucket, language),
      bucket: riskBucket,
    },
    {
      key: 'market-context',
      label: language === 'en' ? 'Market context' : '市场线索',
      value: marketEvidenceLabel(hasMarketContext ? 'available' : 'missing', language),
      bucket: hasMarketContext ? 'available' : 'missing',
    },
    {
      key: 'research-packet',
      label: language === 'en' ? 'Research packet' : '研究包',
      value: researchPacketEvidenceLabel(packet.researchStatus, language),
      bucket: packetBucket,
    },
  ];
}

function evidenceStackCounts(rows: EvidenceStackRow[]): Record<EvidenceStackBucket, number> {
  return rows.reduce<Record<EvidenceStackBucket, number>>((counts, row) => ({
    ...counts,
    [row.bucket]: counts[row.bucket] + 1,
  }), {
    available: 0,
    missing: 0,
    partial: 0,
    stale: 0,
  });
}

function evidenceCompletenessLabel(counts: Record<EvidenceStackBucket, number>, language: 'zh' | 'en'): string {
  const complete = counts.missing === 0 && counts.partial === 0 && counts.stale === 0;
  return complete
    ? (language === 'en' ? 'Evidence complete' : '证据完整')
    : (language === 'en' ? 'Evidence partially ready' : '证据部分可用');
}

function evidenceAuthorityLabels(packet: SymbolResearchPacket, language: 'zh' | 'en'): string[] {
  if (packet.observationOnly || !packet.decisionGrade) {
    return [
      language === 'en' ? 'Observation only' : '仅观察',
      language === 'en' ? 'Score needs confirmation' : '评分待确认',
    ];
  }
  return [language === 'en' ? 'Authoritative' : '权威证据可用'];
}

function evidenceCountLabels(counts: Record<EvidenceStackBucket, number>, language: 'zh' | 'en'): string[] {
  const labels = [
    [counts.available, language === 'en' ? 'ready' : '可用'],
    [counts.missing, language === 'en' ? 'needed' : '待补'],
    [counts.partial, language === 'en' ? 'partial' : '部分'],
    [counts.stale, language === 'en' ? 'delayed' : '延迟'],
  ] as const;
  return labels
    .filter(([count]) => count > 0)
    .map(([count, label]) => language === 'en' ? `${count} ${label}` : `${label} ${count}`);
}

function evidencePackUnknown(language: 'zh' | 'en'): string {
  return language === 'en' ? 'unknown' : '待补证';
}

function evidencePackValue<T extends string | number | boolean>(
  value: T | null | undefined,
  language: 'zh' | 'en',
): T | string {
  if (value === null || value === undefined || value === '') return evidencePackUnknown(language);
  return value;
}

function isQuoteExportable(quote: StockQuote | null): quote is StockQuote {
  if (!quote) return false;
  const freshness = normalizeQuoteBoundaryToken(quote.sourceConfidence?.freshness || quote.freshness);
  return !(
    quote.sourceConfidence?.isUnavailable
    || quote.sourceConfidence?.isSynthetic
    || quote.isSynthetic
    || freshness === 'unavailable'
    || freshness === 'synthetic'
  );
}

function compactEvidencePackSummary(facts: StockResearchFact[], language: 'zh' | 'en') {
  const rows = facts.map((fact) => ({
    label: fact.label,
    value: safeConsumerText(fact.value, language, evidencePackUnknown(language)),
  }));
  return rows.length ? rows : [
    {
      label: language === 'en' ? 'Research state' : '研究状态',
      value: evidencePackUnknown(language),
    },
  ];
}

function buildSingleStockEvidencePackContent({
  data,
  quote,
  researchPacket,
  facts,
  stackRows,
  counts,
  language,
}: {
  data: StockStructureDecisionResponse;
  quote: StockQuote;
  researchPacket: SymbolResearchPacket | null;
  facts: StockResearchFact[];
  stackRows: EvidenceStackRow[];
  counts: Record<EvidenceStackBucket, number>;
  language: 'zh' | 'en';
}): string {
  const sourceConfidence = quote.sourceConfidence;
  const asOf = sourceConfidence?.asOf || quote.marketTimestamp || quote.observedAt || quote.updateTime || researchPacket?.quote.asOf;
  const freshness = sourceConfidence?.freshness || quote.freshness;
  const warnings = compactUnique([
    ...buildEvidenceGapLabels(researchPacket ?? {
      symbol: data.ticker,
      market: '',
      identity: {},
      quote: { state: 'unknown' },
      history: { state: 'unknown' },
      structure: { state: 'unknown' },
      fundamentals: { state: 'unknown', fieldsAvailable: [] },
      events: { state: 'unknown', latest: [] },
      peer: { state: 'unknown' },
      missingData: [],
      researchStatus: 'unknown',
      nextDataAction: '',
      observationOnly: true,
      decisionGrade: false,
      noAdviceDisclosure: '',
    }, language),
    ...(data.confidenceState?.reasons ? safeConsumerList(data.confidenceState.reasons, language) : []),
    ...(data.researchNotes.needsMoreEvidence ? safeConsumerList(data.researchNotes.needsMoreEvidence, language).slice(0, 3) : []),
  ]);
  const stateLabels = stackRows.map((row) => ({
    key: row.key,
    label: row.label,
    state: row.value,
  }));
  const pack = {
    schemaVersion: 'single-stock-evidence-pack.v1',
    generatedAt: new Date().toISOString(),
    appSurface: 'Single Stock / Structure',
    symbol: data.ticker,
    suppliedSymbol: data.ticker,
    quoteLineage: {
      asOf: evidencePackValue(asOf, language),
      sourceLabel: evidencePackValue(safeOptionalConsumerText(sourceConfidence?.sourceLabel, language), language),
      freshness: evidencePackValue(freshness, language),
      confidenceWeight: evidencePackValue(sourceConfidence?.confidenceWeight, language),
      coverage: evidencePackValue(sourceConfidence?.coverage, language),
      stale: Boolean(sourceConfidence?.isStale || quote.isStale),
      partial: Boolean(sourceConfidence?.isPartial || quote.isPartial),
    },
    dataReadiness: {
      quoteState: researchPacket ? quoteEvidenceLabel(researchPacket.quote.state, language) : quoteBoundaryStateLabel(quote, language).label,
      researchState: evidenceCompletenessLabel(counts, language),
      evidenceStates: stateLabels,
      observationOnly: researchPacket?.observationOnly ?? true,
      decisionGrade: researchPacket?.decisionGrade ?? false,
    },
    warnings: warnings.length ? warnings : [evidencePackUnknown(language)],
    visibleResearchSummary: compactEvidencePackSummary(facts, language),
  };
  return JSON.stringify(pack, null, 2);
}

function buildSingleStockEvidencePackEntry({
  data,
  quote,
  quoteFailed,
  researchPacket,
  facts,
  language,
}: {
  data: StockStructureDecisionResponse;
  quote: StockQuote | null;
  quoteFailed: boolean;
  researchPacket: SymbolResearchPacket | null;
  facts: StockResearchFact[];
  language: 'zh' | 'en';
}): SingleStockEvidencePackEntry {
  const stackRows = researchPacket ? buildEvidenceStackRows(researchPacket, language) : [];
  const counts = evidenceStackCounts(stackRows);
  const canExport = isQuoteExportable(quote);
  const contents = [
    language === 'en' ? 'Quote lineage' : '报价',
    language === 'en' ? 'Freshness' : '新鲜度',
    language === 'en' ? 'Evidence state' : '证据状态',
    ...(quoteFailed || !quote ? [language === 'en' ? 'Pending quote evidence' : '报价待补证'] : []),
  ];

  return {
    packKey: 'single-stock-evidence-pack',
    label: language === 'en' ? 'Single stock evidence pack' : '个股证据包',
    state: canExport ? 'available' : 'unavailable',
    description: canExport
      ? (language === 'en'
        ? 'Copy or download a consumer-safe JSON artifact for this stock research view.'
        : '复制或导出该个股研究视图的消费者安全 JSON 证据包。')
      : (language === 'en'
        ? 'Quote evidence is pending, so no evidence artifact is generated.'
        : '报价证据待补证，不生成证据包。'),
    contents,
    exportContent: canExport
      ? buildSingleStockEvidencePackContent({
        data,
        quote,
        researchPacket,
        facts,
        stackRows,
        counts,
        language,
      })
      : null,
    fileName: `single-stock-evidence-pack-${data.ticker || 'symbol'}.json`,
    copyLabel: language === 'en' ? 'Copy stock evidence pack' : '复制个股证据包',
    downloadLabel: language === 'en' ? 'Export stock evidence pack' : '导出个股证据包',
    copyTestId: 'single-stock-evidence-pack-copy',
    downloadTestId: 'single-stock-evidence-pack-download',
    blockedCopyTestId: 'single-stock-evidence-pack-copy-blocked',
  };
}

function downloadSingleStockEvidencePack(filename: string, content: string): void {
  const blob = new Blob([content], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function SingleStockEvidencePackControls({
  entry,
  language,
}: {
  entry: SingleStockEvidencePackEntry;
  language: 'zh' | 'en';
}) {
  const [status, setStatus] = useState<string | null>(null);
  const canExport = entry.state === 'available' && Boolean(entry.exportContent);
  const actionClass = 'inline-flex min-h-9 items-center justify-center gap-1.5 rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs font-semibold text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)] disabled:cursor-not-allowed disabled:opacity-45';

  const copy = async () => {
    if (!canExport || !entry.exportContent || !navigator.clipboard?.writeText) {
      setStatus(language === 'en' ? 'Evidence pack pending; nothing copied.' : '证据包待补证，未复制。');
      return;
    }
    await navigator.clipboard.writeText(entry.exportContent);
    setStatus(language === 'en' ? 'Evidence pack copied.' : '证据包已复制。');
  };

  const download = () => {
    if (!canExport || !entry.exportContent) {
      setStatus(language === 'en' ? 'Evidence pack pending; nothing exported.' : '证据包待补证，未导出。');
      return;
    }
    downloadSingleStockEvidencePack(entry.fileName, entry.exportContent);
    setStatus(language === 'en' ? 'Evidence pack exported.' : '证据包已导出。');
  };

  return (
    <section
      data-testid="single-stock-evidence-pack-registry"
      className="rounded-lg border border-white/5 bg-white/[0.02] p-3"
    >
      <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <h4 className="text-sm font-semibold text-white/88">{entry.label}</h4>
            <TerminalChip variant={canExport ? 'success' : 'caution'}>
              {canExport ? (language === 'en' ? 'Available' : '可用') : (language === 'en' ? 'Pending evidence' : '待补证')}
            </TerminalChip>
          </div>
          <p className="mt-1 text-xs leading-5 text-white/58">{entry.description}</p>
          <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
            {entry.contents.map((item) => (
              <TerminalChip key={item} variant="neutral">{item}</TerminalChip>
            ))}
          </div>
          {status ? (
            <p className="mt-2 text-[11px] leading-5 text-white/52">{status}</p>
          ) : null}
        </div>
        <div className="flex min-w-0 flex-wrap gap-2">
          {canExport ? (
            <>
              <button type="button" className={actionClass} onClick={() => void copy()} data-testid={entry.copyTestId}>
                <Copy className="size-3.5" aria-hidden="true" />
                {entry.copyLabel}
              </button>
              <button type="button" className={actionClass} onClick={download} data-testid={entry.downloadTestId}>
                <Download className="size-3.5" aria-hidden="true" />
                {entry.downloadLabel}
              </button>
            </>
          ) : (
            <button type="button" className={actionClass} disabled data-testid={entry.blockedCopyTestId}>
              <Copy className="size-3.5" aria-hidden="true" />
              {language === 'en' ? 'Copy pending evidence' : '复制待补证'}
            </button>
          )}
        </div>
      </div>
    </section>
  );
}

function isSymbolNotFoundValidation(
  validation: StockValidationResponse | null | undefined,
): validation is StockValidationResponse {
  if (!validation) return false;
  if (validation.exists || validation.valid) return false;
  return ['invalid_format', 'unsupported_market', 'ambiguous', 'not_found'].includes(String(validation.status || ''));
}

function numericValue(value: unknown): number | null {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function isUnavailableStructureState(value: string | null | undefined): boolean {
  const normalized = String(value || '').trim().toLowerCase().replace(/[-\s]+/g, '_');
  return !normalized
    || ['lowconfidence', 'low_confidence', 'unavailable', 'unknown', 'insufficient_evidence', 'no_data', 'blocked'].includes(normalized);
}

function buildPacketFacts(
  data: StockStructureDecisionResponse,
  scoreRows: Array<{ key: string; label: string; value: number }>,
  language: 'zh' | 'en',
): StockResearchFact[] {
  const facts: StockResearchFact[] = [];
  const usableBars = numericValue(data.dataQuality.usableBars);
  const period = periodLabel(data.dataQuality.period, language);
  const status = statusLabel(data.dataQuality.status, language);
  const structureState = stockStructureStateLabel(data.structureState, language);
  const topScore = scoreRows[0];
  const riskFlags = safeConsumerList(data.researchNotes.riskFlags ?? [], language)
    .map((flag) => mapConsumerStatusText(flag, language))
    .filter(Boolean);
  const needsMoreEvidence = safeConsumerList(data.researchNotes.needsMoreEvidence ?? [], language);

  facts.push({
    key: 'symbol',
    label: language === 'en' ? 'Symbol' : '标的',
    value: safeConsumerText(data.ticker, language, language === 'en' ? 'Current symbol' : '当前标的'),
  });

  if (usableBars !== null && usableBars > 0) {
    facts.push({
      key: 'update-status',
      label: language === 'en' ? 'Update status' : '更新状态',
      value: [status, period, barsCountLabel(usableBars, language)].filter(Boolean).join(' · '),
    });
  }

  if (structureState && !isUnavailableStructureState(data.structureState)) {
    facts.push({
      key: 'structure-state',
      label: language === 'en' ? 'Technical state' : '技术状态',
      value: structureState,
    });
  }

  if (topScore) {
    facts.push({
      key: 'top-signal',
      label: language === 'en' ? 'Strongest component' : '主要结构线索',
      value: `${topScore.label}: ${topScore.value}`,
    });
  }

  if (riskFlags.length) {
    facts.push({
      key: 'risk',
      label: language === 'en' ? 'Risk / uncertainty' : '风险 / 不确定性',
      value: riskFlags.join(language === 'en' ? '; ' : '；'),
    });
  } else if (needsMoreEvidence.length) {
    facts.push({
      key: 'uncertainty',
      label: language === 'en' ? 'Risk / uncertainty' : '风险 / 不确定性',
      value: needsMoreEvidence.slice(0, 2).join(language === 'en' ? '; ' : '；'),
    });
  }

  return facts;
}

function hasMinimumResearchPacket(
  data: StockStructureDecisionResponse,
  scoreRows: Array<{ key: string; label: string; value: number }>,
  language: 'zh' | 'en',
): boolean {
  const usableBars = numericValue(data.dataQuality.usableBars);
  const hasUsablePriceHistory = usableBars !== null && usableBars > 0;
  const hasStructureState = Boolean(safeOptionalConsumerText(data.structureState, language))
    && !isUnavailableStructureState(data.structureState);
  const hasExplanation = Boolean(safeOptionalConsumerText(data.explanation.whyThisStructure, language))
    || safeConsumerList(data.explanation.whatConfirmsIt ?? [], language).length > 0
    || safeConsumerList(data.explanation.whatInvalidatesIt ?? [], language).length > 0;
  const hasResearchNotes = safeConsumerList(data.researchNotes.watchNext ?? [], language).length > 0
    || safeConsumerList(data.researchNotes.riskFlags ?? [], language).length > 0;
  const hasKeyLevels = (data.explanation.keyLevels ?? []).some((level) => (
    level.value != null || Boolean(safeOptionalConsumerText(level.description, language))
  ));

  return hasUsablePriceHistory
    || hasStructureState
    || scoreRows.length > 0
    || hasExplanation
    || hasResearchNotes
    || hasKeyLevels
    || hasPeerCorrelationContent(data.peerCorrelationSnapshot);
}

function buildMissingDataSummary(
  data: StockStructureDecisionResponse,
  language: 'zh' | 'en',
): string | null {
  const gaps = data.missingEvidence ?? [];
  const missingCopies = compactUnique(gaps.map((gap) => missingEvidenceCopy(data.ticker, gap, language)));
  if (missingCopies.length) {
    return missingCopies.slice(0, 2).join(language === 'en' ? ' ' : '');
  }
  if (data.confidenceState?.reasons?.length) {
    const reasons = safeConsumerList(data.confidenceState.reasons, language);
    if (reasons.length) return reasons.slice(0, 2).join(language === 'en' ? ' ' : '');
  }
  return null;
}

function StockStructureCannotResearchState({
  data,
  language,
  localize,
}: {
  data: StockStructureDecisionResponse;
  language: 'zh' | 'en';
  localize: (path: string) => string;
}) {
  const isEnglish = language === 'en';
  const summary = buildMissingDataSummary(data, language);

  return (
    <div className="p-4 md:p-5">
      <TerminalEmptyState
        className="items-start md:items-center"
        data-testid="stock-structure-unavailable-state"
        title={isEnglish ? `${data.ticker} cannot be researched yet` : `${data.ticker} 暂不能形成研究包`}
        action={(
          <div className="flex shrink-0 flex-wrap justify-end gap-2">
            <Link
              to={localize('/research/radar')}
              className="inline-flex min-h-9 items-center justify-center rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)]"
            >
              {isEnglish ? 'Back to Research Radar' : '返回研究雷达'}
            </Link>
            <Link
              to={localize('/watchlist')}
              className="inline-flex min-h-9 items-center justify-center rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)]"
            >
              {isEnglish ? 'Back to watchlist' : '返回观察列表'}
            </Link>
          </div>
        )}
      >
        <div className="space-y-1">
          <p>
            {isEnglish
              ? 'Limited facts for a research packet.'
              : '个股事实不足，暂不能组成研究包。'}
          </p>
          <p>
            {summary || (isEnglish
              ? 'Return after price or comparable evidence is ready.'
              : '价格或可比证据可用后，从研究队列重新进入。')}
          </p>
          <p>
            {isEnglish
              ? 'Research observation only.'
              : '仅研究观察。'}
          </p>
        </div>
      </TerminalEmptyState>
    </div>
  );
}

function StockMinimumResearchPacket({
  data,
  facts,
  language,
  missingSummary,
}: {
  data: StockStructureDecisionResponse;
  facts: StockResearchFact[];
  language: 'zh' | 'en';
  missingSummary: string | null;
}) {
  const isEnglish = language === 'en';
  const watchNext = safeConsumerList(data.researchNotes.watchNext ?? [], language);

  return (
    <div className="grid gap-3 border-t border-[color:var(--wolfy-divider)] p-3" data-testid="stock-minimum-research-packet">
      <RoughSectionCard
        eyebrow={isEnglish ? 'Minimum research packet' : '最低研究包'}
        title={isEnglish ? 'Known stock facts' : '已知个股事实'}
      >
        <RoughKeyValueRows
          rows={facts.map((fact) => ({
            key: fact.key,
            label: fact.label,
            value: fact.value,
            detail: fact.detail,
          }))}
        />
      </RoughSectionCard>
      {watchNext.length ? (
        <RoughSectionCard
          eyebrow={isEnglish ? 'Next check' : '下一步研究'}
          title={isEnglish ? 'What to verify next' : '下一步核对'}
        >
          <RoughBulletList
            items={watchNext.slice(0, 3)}
            emptyText={isEnglish ? 'No next check listed.' : '暂无下一步核对项。'}
          />
        </RoughSectionCard>
      ) : null}
      {missingSummary ? (
        <RoughSectionCard
          eyebrow={isEnglish ? 'Data boundary' : '数据边界'}
          title={isEnglish ? 'Missing data summarized once' : '缺失资料汇总'}
        >
          <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">{missingSummary}</p>
        </RoughSectionCard>
      ) : null}
    </div>
  );
}

function StockResearchPacketPanel({
  packet,
  failed,
  language,
}: {
  packet: SymbolResearchPacket | null;
  failed: boolean;
  language: 'zh' | 'en';
}) {
  const isEnglish = language === 'en';
  if (failed) {
    return (
      <div className="border-t border-[color:var(--wolfy-divider)] p-3" data-testid="stock-research-packet-panel">
        <RoughSectionCard eyebrow={isEnglish ? 'Research packet' : '研究包'} title={isEnglish ? 'Research packet pending' : '研究包待更新'}>
          <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
            {isEnglish ? 'Refresh the packet after the stock data endpoint updates.' : '待个股数据接口更新后再复核。'}
          </p>
        </RoughSectionCard>
      </div>
    );
  }

  if (!packet) return null;

  const stackRows = buildEvidenceStackRows(packet, language);
  const counts = evidenceStackCounts(stackRows);
  const countLabels = evidenceCountLabels(counts, language);
  const authorityLabels = evidenceAuthorityLabels(packet, language);
  const gapLabels = buildEvidenceGapLabels(packet, language);
  const identityLabel = [
    safeOptionalConsumerText(packet.identity.name, language),
    safeOptionalConsumerText(packet.market, language),
  ].filter(Boolean).join(' · ') || packet.symbol;

  return (
    <div className="grid gap-3 border-t border-[color:var(--wolfy-divider)] p-3" data-testid="stock-research-packet-panel">
      <RoughSectionCard
        eyebrow={isEnglish ? 'Evidence stack' : '证据栈'}
        title={evidenceCompletenessLabel(counts, language)}
      >
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <TerminalChip variant="info">{packet.symbol}</TerminalChip>
          <TerminalChip variant="neutral">{identityLabel}</TerminalChip>
          {authorityLabels.map((label) => (
            <TerminalChip key={label} variant="neutral">{label}</TerminalChip>
          ))}
          {countLabels.map((label) => (
            <TerminalChip key={label} variant="info">{label}</TerminalChip>
          ))}
        </div>
        <RoughKeyValueRows
          rows={stackRows.map((row) => ({
            key: row.key,
            label: row.label,
            value: row.value,
          }))}
        />
      </RoughSectionCard>
      {gapLabels.length ? (
        <RoughSectionCard eyebrow={isEnglish ? 'Next evidence gaps' : '下一证据缺口'} title={isEnglish ? 'What remains missing' : '仍需补齐'}>
          <div className="flex flex-wrap gap-2">
            {gapLabels.map((label) => (
              <TerminalChip key={label} variant="caution">{label}</TerminalChip>
            ))}
          </div>
        </RoughSectionCard>
      ) : null}
    </div>
  );
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
              ? `${symbol || 'The symbol'} cannot be confirmed; this differs from temporarily missing data.`
              : '当前无法确认该标的，不等同于数据暂时不可用。'}
          </p>
          <p>
            {isEnglish
              ? 'Research observation only.'
              : '仅研究观察。'}
          </p>
        </div>
      </TerminalEmptyState>
    </div>
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
                  ? `Only ${symbolLabel} is present, so shared evidence or divergence evidence cannot be formed yet.`
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
  const missingSymbols = displaySymbols.filter((symbol) => (packet.missingEvidenceBySymbol[symbol] ?? []).length > 0);

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
              ? `Confidence cap ${confidenceCapLabel(confidenceCapValue, language)}`
              : `置信上限 ${confidenceCapLabel(confidenceCapValue, language)}`}
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
          emptyText={language === 'en' ? 'No shared evidence is ready across these symbols yet.' : '这些标的之间暂无共同证据。'}
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
          emptyText={language === 'en' ? 'No divergence is ready in this packet.' : '当前证据包暂无分歧观察。'}
        />
      </RoughSectionCard>

      <RoughSectionCard title={language === 'en' ? 'Missing evidence' : '缺失证据'}>
        {missingSymbols.length ? (
          <div className="grid gap-3">
            {missingSymbols.map((symbol) => {
            const gaps = packet.missingEvidenceBySymbol[symbol] ?? [];
            return (
              <div key={`missing-${symbol}`} className="rounded-xl border border-[color:var(--wolfy-divider)] bg-black/10 px-3 py-2.5">
                <div className="mb-2 font-mono text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{symbol}</div>
                <p className="mb-2 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
                  {gaps.map((gap) => missingEvidenceCopy(symbol, gap, language)).join(language === 'en' ? ' ' : '')}
                </p>
                <EvidenceGapExplanationList
                  gaps={gaps}
                  locale={language}
                  title={language === 'en' ? 'Gap explanation' : '缺口解释'}
                />
              </div>
            );
            })}
          </div>
        ) : (
          <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
            {language === 'en' ? 'No missing compare item is listed for this symbol set.' : '这组标的暂无需要逐项展开的缺失资料。'}
          </p>
        )}
      </RoughSectionCard>

      <RoughSectionCard title={language === 'en' ? 'Freshness by symbol' : '新鲜度'}>
        <RoughKeyValueRows
          emptyText={language === 'en' ? 'No freshness summary yet.' : '暂无新鲜度摘要。'}
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
  const [researchPacket, setResearchPacket] = useState<SymbolResearchPacket | null>(null);
  const [researchPacketFailed, setResearchPacketFailed] = useState(false);
  const [quote, setQuote] = useState<StockQuote | null>(null);
  const [quoteFailed, setQuoteFailed] = useState(false);
  const [optionsStructure, setOptionsStructure] = useState<OptionsStructureSummary | null>(null);
  const [optionsStructureFailed, setOptionsStructureFailed] = useState(false);
  const [comparePacket, setComparePacket] = useState<StockSymbolCompareEvidencePacket | null>(null);
  const [symbolNotFound, setSymbolNotFound] = useState<SymbolNotFoundState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setSymbolNotFound(null);
    setResearchPacket(null);
    setResearchPacketFailed(false);
    setQuote(null);
    setQuoteFailed(false);
    setOptionsStructure(null);
    setOptionsStructureFailed(false);
    try {
      if (isCompareRequest) {
        const [packetResult, responseResult] = await Promise.allSettled([
          stocksApi.getResearchPacket(primarySymbol),
          stocksApi.getStructureDecisionsBatch({
            stockCodes: requestedSymbols,
            benchmark,
            maxItems,
          }),
        ]);
        if (packetResult.status === 'fulfilled') {
          setResearchPacket(packetResult.value);
        } else {
          setResearchPacketFailed(true);
        }
        if (responseResult.status === 'rejected') {
          throw responseResult.reason;
        }
        const response = responseResult.value;
        setData(response.items[0] ?? null);
        setComparePacket(response.symbolCompareEvidencePacket ?? null);
        setOptionsStructure(null);
        setOptionsStructureFailed(false);
      } else {
        let validation: StockValidationResponse | null = null;
        try {
          validation = await stocksApi.verifyTickerExists(primarySymbol);
        } catch {
          validation = null;
        }
        if (isSymbolNotFoundValidation(validation)) {
          setData(null);
          setResearchPacket(null);
          setResearchPacketFailed(false);
          setComparePacket(null);
          setSymbolNotFound({
            symbol: validation.normalizedSymbol || validation.stockCode || primarySymbol,
          });
          return;
        }
        const [quoteResult, packetResult, responseResult, optionsResult] = await Promise.allSettled([
          stocksApi.getQuote(primarySymbol),
          stocksApi.getResearchPacket(primarySymbol),
          stocksApi.getStructureDecision(primarySymbol),
          optionsLabApi.getOptionsStructure(primarySymbol),
        ]);
        if (quoteResult.status === 'fulfilled') {
          setQuote(quoteResult.value);
        } else {
          setQuoteFailed(true);
        }
        if (packetResult.status === 'fulfilled') {
          setResearchPacket(packetResult.value);
          setResearchPacketFailed(false);
        } else {
          setResearchPacketFailed(true);
        }
        if (optionsResult.status === 'fulfilled') {
          setOptionsStructure(optionsResult.value);
          setOptionsStructureFailed(false);
        } else {
          setOptionsStructureFailed(true);
        }
        if (responseResult.status === 'rejected') {
          throw responseResult.reason;
        }
        const response = responseResult.value;
        setData(response);
        setComparePacket(null);
      }
    } catch (err) {
      setComparePacket(null);
      setSymbolNotFound(null);
      setError(getParsedApiError(err) || createParsedApiError({
        title: locale === 'en' ? 'Structure panel pending' : '结构面板暂不可用',
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
  const hasResearchPacket = data ? hasMinimumResearchPacket(data, scoreRows, locale) : false;
  const packetFacts = useMemo(
    () => (data ? buildPacketFacts(data, scoreRows, locale) : []),
    [data, locale, scoreRows],
  );
  const missingDataSummary = data ? buildMissingDataSummary(data, locale) : null;
  const safeDisclosure = data
    ? safeConsumerText(
      data.noAdviceDisclosure,
      locale,
      locale === 'en' ? 'Research context only. No action instruction is generated.' : '仅供研究语境参考，不生成操作指令。',
    )
    : null;
  const safeWatchNext = data ? safeConsumerList(data.researchNotes.watchNext ?? [], locale) : [];
  const explainRows = data ? [
    {
      key: 'why',
      label: locale === 'en' ? 'Why this structure' : '形成原因',
      value: safeOptionalConsumerText(data.explanation.whyThisStructure, locale),
    },
    {
      key: 'confirm',
      label: locale === 'en' ? 'What confirms it' : '确认观察',
      value: safeConsumerList(data.explanation.whatConfirmsIt ?? [], locale).join(locale === 'en' ? '; ' : '；'),
    },
    {
      key: 'invalidate',
      label: locale === 'en' ? 'What changes it' : '变化条件',
      value: safeConsumerList(data.explanation.whatInvalidatesIt ?? [], locale).join(locale === 'en' ? '; ' : '；'),
    },
  ].filter((row) => row.value) : [];
  const researchRows = data ? [
    {
      key: 'more',
      label: locale === 'en' ? 'Needs more evidence' : '待补资料',
      value: safeConsumerList(data.researchNotes.needsMoreEvidence ?? [], locale).join(locale === 'en' ? '; ' : '；'),
    },
    {
      key: 'risk',
      label: locale === 'en' ? 'Risk flags' : '风险标记',
      value: safeConsumerList(data.researchNotes.riskFlags ?? [], locale)
        .map((flag) => mapConsumerStatusText(flag, locale))
        .join(locale === 'en' ? '; ' : '；'),
    },
  ].filter((row) => row.value) : [];
  const keyLevelRows = data ? (data.explanation.keyLevels ?? [])
    .map((level, index) => ({
      key: `${level.kind || 'level'}-${index}`,
      label: safeOptionalConsumerText(level.kind, locale) || (locale === 'en' ? 'Level' : '位置'),
      value: level.value ?? safeOptionalConsumerText(level.description, locale),
      detail: level.value != null ? safeOptionalConsumerText(level.description, locale) || undefined : undefined,
    }))
    .filter((row) => row.value != null && row.value !== '') : [];
  const quoteBoundaryView = useMemo(
    () => buildQuoteBoundaryView(quote, quoteFailed, locale),
    [locale, quote, quoteFailed],
  );
  const singleStockEvidencePackEntry = useMemo(
    () => (data ? buildSingleStockEvidencePackEntry({
      data,
      quote,
      quoteFailed,
      researchPacket,
      facts: packetFacts,
      language: locale,
    }) : null),
    [data, locale, packetFacts, quote, quoteFailed, researchPacket],
  );
  const compareWithPeerPath = data && comparablePeerSymbol && !isCompareRequest
    ? localize(buildComparePath([data.ticker || primarySymbol, comparablePeerSymbol]))
    : null;
  const introTitle = symbolNotFound
    ? (locale === 'en' ? 'Symbol not found' : '标的未找到')
    : (locale === 'en' ? `${titleSymbol} structure workspace` : `${titleSymbol} 结构工作区`);
  const introDescription = symbolNotFound
    ? (locale === 'en'
      ? 'Check the code or return to a research entrypoint.'
      : '请检查代码是否正确，或返回研究入口重新选择。')
    : (locale === 'en'
      ? 'Assembles known stock fact summaries.'
      : '汇总可用个股事实。');
  const railContent = data && hasResearchPacket ? (
    <ConsoleContextRail className="flex flex-col gap-3 p-3">
      {safeWatchNext.length ? (
        <RoughSectionCard eyebrow={locale === 'en' ? 'Research notes' : '研究备注'} title={locale === 'en' ? 'Watch next' : '下一步观察'}>
          <RoughBulletList
            items={safeWatchNext.slice(0, 3)}
            emptyText={locale === 'en' ? 'No next watch item yet.' : '暂未整理下一步观察项。'}
          />
        </RoughSectionCard>
      ) : null}
      {missingDataSummary ? (
        <RoughSectionCard eyebrow={locale === 'en' ? 'Boundary' : '边界'} title={locale === 'en' ? 'Data still missing' : '仍缺资料'}>
          <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">{missingDataSummary}</p>
        </RoughSectionCard>
      ) : null}
      {safeDisclosure ? (
        <RoughSectionCard eyebrow={locale === 'en' ? 'Disclosure' : '披露'} title={locale === 'en' ? 'Research boundary' : '研究边界'}>
          <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">{safeDisclosure}</p>
        </RoughSectionCard>
      ) : null}
    </ConsoleContextRail>
  ) : null;

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
                {locale === 'en' ? 'Research workspace for structure state, key levels, useful notes, and one compact data boundary.' : '结构研究工作区，集中呈现状态、关键位置、有效备注与一处数据边界。'}
              </div>
            </WolfyCommandBar>
          )}
          rail={railContent}
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
                  {locale === 'en' ? 'Loading structure panel.' : '正在载入结构面板。'}
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
            {quoteBoundaryView ? (
              <div className="p-3 md:p-4">
                <RoughSectionCard
                  data-testid="stock-quote-boundary-panel"
                  eyebrow={locale === 'en' ? 'Quote boundary' : '报价边界'}
                  title={quoteBoundaryView.title}
                >
                  <div className="flex flex-wrap gap-2">
                    {quoteBoundaryView.chips.map((chip) => (
                      <StatusBadge key={chip.label} status={chip.variant} label={chip.label} size="sm" />
                    ))}
                  </div>
                  <p className="mt-3 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
                    {quoteBoundaryView.detail}
                  </p>
                </RoughSectionCard>
              </div>
            ) : null}
            {!isCompareRequest && !symbolNotFound ? (
              <OptionsStructureSurface
                structure={optionsStructure}
                failed={optionsStructureFailed}
                loading={loading && !optionsStructure && !optionsStructureFailed}
                language={locale}
              />
            ) : null}
            {singleStockEvidencePackEntry ? (
              <div className="p-3 md:p-4">
                <SingleStockEvidencePackControls
                  entry={singleStockEvidencePackEntry}
                  language={locale}
                />
              </div>
            ) : null}
            {data ? (
              <>
                <StockResearchPacketPanel
                  packet={researchPacket}
                  failed={researchPacketFailed}
                  language={locale}
                />
                {hasResearchPacket ? (
                  <>
                    <ConsoleStatusStrip
                      items={[
                        {
                          label: locale === 'en' ? 'Ticker' : '标的',
                          value: data.ticker,
                        },
                        {
                          label: locale === 'en' ? 'Data status' : '数据状态',
                          value: <StatusBadge status={toneFor(data.dataQuality.status)} label={statusLabel(data.dataQuality.status, locale)} size="sm" />,
                        },
                        {
                          label: locale === 'en' ? 'Period' : '周期',
                          value: periodLabel(data.dataQuality.period, locale) || (locale === 'en' ? 'not listed' : '未列明'),
                        },
                      ]}
                    />
                    <MetricStrip
                      items={[
                        {
                          key: 'state',
                          label: locale === 'en' ? 'Structure state' : '结构状态',
                          value: stockStructureStateLabel(data.structureState, locale) || (locale === 'en' ? 'Under review' : '待确认'),
                        },
                        {
                          key: 'confidence',
                          label: locale === 'en' ? 'Confidence' : '置信度',
                          value: confidenceLabel(data.confidence, locale),
                        },
                        {
                          key: 'bars',
                          label: locale === 'en' ? 'Usable bars' : '可用 K 线',
                          value: data.dataQuality.usableBars ?? (locale === 'en' ? 'not listed' : '未列明'),
                        },
                      ]}
                    />
                    <StockMinimumResearchPacket
                      data={data}
                      facts={packetFacts}
                      language={locale}
                      missingSummary={missingDataSummary}
                    />
                    {isCompareRequest || comparePacket ? (
                      <SymbolCompareEvidencePacketPanel
                        packet={comparePacket}
                        language={locale}
                        requestedSymbols={requestedSymbols}
                      />
                    ) : null}
                    <div className="grid gap-3 p-3 md:grid-cols-2">
                      {scoreRows.length ? (
                        <RoughSectionCard eyebrow={locale === 'en' ? 'Scores' : '评分'} title={locale === 'en' ? 'Component scores' : '组件评分'}>
                          <RoughScoreRows
                            items={scoreRows}
                            emptyText={locale === 'en' ? 'No component score yet.' : '暂无组件评分。'}
                          />
                        </RoughSectionCard>
                      ) : null}
                      {explainRows.length ? (
                        <RoughSectionCard eyebrow={locale === 'en' ? 'Structure logic' : '结构逻辑'} title={locale === 'en' ? 'Why this structure' : '结构解释'}>
                          <RoughKeyValueRows rows={explainRows} />
                        </RoughSectionCard>
                      ) : null}
                      {researchRows.length ? (
                        <RoughSectionCard eyebrow={locale === 'en' ? 'Research notes' : '研究备注'} title={locale === 'en' ? 'What remains uncertain' : '仍需确认'}>
                          <RoughKeyValueRows rows={researchRows} />
                        </RoughSectionCard>
                      ) : null}
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
                      ) : null}
                      {keyLevelRows.length ? (
                        <RoughSectionCard eyebrow={locale === 'en' ? 'Reference levels' : '参考位置'} title={locale === 'en' ? 'Key levels' : '关键位置'}>
                          <RoughKeyValueRows rows={keyLevelRows} />
                        </RoughSectionCard>
                      ) : null}
                    </div>
                  </>
                ) : (
                  <StockStructureCannotResearchState
                    data={data}
                    language={locale}
                    localize={localize}
                  />
                )}
              </>
            ) : null}
          </ConsoleBoard>
        </ResearchConsoleShell>
      </ConsumerWorkspacePageShell>
    </ConsumerWorkspaceScope>
  );
}
