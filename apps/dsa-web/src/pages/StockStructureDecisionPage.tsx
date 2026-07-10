import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import { Copy, Download } from 'lucide-react';
import { ApiErrorAlert } from '../components/common/ApiErrorAlert';
import {
  ConsoleBoard,
  ConsoleContextRail,
  ResearchConsoleShell,
  WolfyCommandBar,
} from '../components/linear/LinearPrimitives';
import { ConsumerWorkspacePageShell, ConsumerWorkspaceScope } from '../components/layout/ConsumerWorkspaceShell';
import PeerCorrelationSnapshotBlock from '../components/common/PeerCorrelationSnapshotBlock';
import ProductReadModelStatusStrip from '../components/common/ProductReadModelStatusStrip';
import { CoreMarketChart, type CoreMarketChartPoint } from '../components/charts/CoreMarketChart';
import { StatusBadge } from '../components/ui/StatusBadge';
import { TerminalButton, TerminalChip, TerminalEmptyState } from '../components/terminal/TerminalPrimitives';
import { createParsedApiError, getParsedApiError, type ParsedApiError } from '../api/error';
import {
  stocksApi,
  type StockHistoryPoint,
  type StockHistoryResponse,
  type StockQuote,
  type StockTechnicalIndicatorsResponse,
  type SymbolResearchPacket,
  type StockPeerCorrelationSnapshot,
  type StockStructureDecisionResponse,
  type StockValidationResponse,
  type StockSymbolCompareEvidenceEntry,
  type StockSymbolCompareEvidencePacket,
  type StockSymbolCompareFreshness,
} from '../api/stocks';
import { stockEvidenceApi } from '../api/stockEvidence';
import { optionsLabApi, type OptionsStructureSummary, type OptionContractStructureRow } from '../api/optionsLab';
import type { StockEvidenceItem, StockEvidenceResponse } from '../types/stockEvidence';
import { EvidenceGapExplanationList } from '../components/research/EvidenceGapExplanation';
import ResearchWorkspaceFlowPanel from '../components/research/ResearchWorkspaceFlowPanel';
import { useI18n } from '../contexts/UiLanguageContext';
import { useProductSurface } from '../hooks/useProductSurface';
import { getConsumerStatusLabel, mapConsumerStatusText } from '../utils/consumerStatusLabels';
import { consumerPresentationText } from '../utils/consumerPresentationBoundary';
import { buildLocalizedPath, parseLocaleFromPathname } from '../utils/localeRouting';
import {
  productReadClassificationDisplayState,
  productReadFreshnessLabel,
  productReadModelTone,
  productReadProvenanceLine,
  productReadStrongConclusionAllowed,
  productReadStateLabel,
} from '../utils/productReadModelView';
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
  if (!looksUnsafeForConsumer(text)) return consumerPresentationText(text, language, fallback);
  const sanitized = consumerPresentationText(text, language, fallback);
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

function formatStockMarketLabel(value: string | null | undefined, language: 'zh' | 'en'): string {
  const market = String(value || '').trim().toUpperCase();
  if (market === 'US') return 'US';
  if (market === 'CN') return language === 'en' ? 'CN' : 'A股';
  if (market === 'HK') return language === 'en' ? 'HK' : '港股';
  return market || '--';
}

function formatStockPrice(value: number | null | undefined, market: string | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '--';
  const abs = Math.abs(value);
  const decimals = abs >= 1000 ? 0 : abs >= 100 ? 1 : 2;
  const formatted = new Intl.NumberFormat('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
  const normalizedMarket = String(market || '').trim().toUpperCase();
  if (normalizedMarket === 'US') return `$${formatted}`;
  if (normalizedMarket === 'HK') return `HK$${formatted}`;
  if (normalizedMarket === 'CN') return `¥${formatted}`;
  return formatted;
}

function formatSignedPercent(value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '--';
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}

function toneFor(value: string | null | undefined): string {
  const normalized = String(value || '').toLowerCase();
  if (['available', 'high', 'ready', 'complete', 'breakout'].includes(normalized)) return 'success';
  if (['medium', 'partial', 'stale', 'degraded', 'pending', 'range', 'neutral'].includes(normalized)) return 'warning';
  if (['low', 'unavailable', 'insufficient', 'no_evidence', 'rejected', 'withheld', 'lowconfidence', 'low_confidence', 'blocked'].includes(normalized)) return 'error';
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
    low_confidence: { zh: '证据不足', en: 'Evidence incomplete' },
    mixed: { zh: '结构分化', en: 'Mixed structure' },
    neutral: { zh: '结构中性', en: 'Neutral structure' },
    pullback: { zh: '回撤观察', en: 'Pullback watch' },
    range: { zh: '区间震荡', en: 'Range-bound' },
    withheld: { zh: '暂不形成强结论', en: 'Strong conclusion withheld' },
    insufficient_evidence: { zh: '证据不足', en: 'Evidence incomplete' },
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

/** DESIGN.md show / compact / hide for optional evidence modules. */
type ModuleDensity = 'full' | 'compact' | 'hide';

function resolveModuleDensity(meaningfulFieldCount: number): ModuleDensity {
  if (meaningfulFieldCount >= 3) return 'full';
  if (meaningfulFieldCount >= 1) return 'compact';
  return 'hide';
}

function isPlaceholderMetricValue(value: string | null | undefined, language: 'zh' | 'en'): boolean {
  const text = String(value || '').trim();
  if (!text) return true;
  const missing = optionsMissingValue(language);
  return text === missing || text === '--' || text === '—' || text === 'N/A' || text === 'n/a';
}

function buildOptionsStructureMetrics(
  structure: OptionsStructureSummary,
  language: 'zh' | 'en',
): OptionsStructureMetricRow[] {
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

  // Only real values — never wall empty cells with 待补 scaffolding.
  return [
    gex ? {
      key: 'gex',
      label: 'GEX',
      value: gex,
      detail: 'Dealer gamma exposure',
    } : null,
    gammaFlip ? {
      key: 'gamma-flip',
      label: 'Gamma flip',
      value: gammaFlip,
      detail: language === 'en' ? 'Flip level populated' : '翻转位置已填充',
    } : null,
    vanna ? {
      key: 'vanna',
      label: 'Vanna',
      value: vanna,
      detail: language === 'en' ? 'Contract values summed' : '合约值汇总',
    } : null,
    charm ? {
      key: 'charm',
      label: 'Charm',
      value: charm,
      detail: language === 'en' ? 'Contract values summed' : '合约值汇总',
    } : null,
    zeroDteValue ? {
      key: 'zero-dte',
      label: language === 'en' ? '0DTE concentration' : '0DTE 集中度',
      value: zeroDteValue,
      detail: structure.zeroDte.state === 'available'
        ? (language === 'en'
          ? `${structure.zeroDte.expiration || 'nearest'} · ${structure.zeroDte.contractCount} contracts`
          : `${structure.zeroDte.expiration || '最近到期'} · ${structure.zeroDte.contractCount} 张合约`)
        : (language === 'en' ? '0DTE bucket not present' : '0DTE 桶暂缺'),
    } : null,
    hasOiVolume ? {
      key: 'oi-volume',
      label: language === 'en' ? 'OI / volume' : 'OI / 成交',
      value: `${formatOptionsInteger(totalOi, language)} / ${formatOptionsInteger(totalVolume, language)}`,
      detail: language === 'en' ? 'Expiration summaries' : '到期汇总',
    } : null,
  ].filter((row): row is OptionsStructureMetricRow => Boolean(row));
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
  const metrics = buildOptionsStructureMetrics(structure, language)
    .filter((metric) => !isPlaceholderMetricValue(metric.value, language));
  const density = resolveModuleDensity(metrics.length);
  const isCompact = density !== 'full';

  return (
    <div
      className="p-3 md:p-4"
      data-testid="stock-options-structure-surface"
      data-module-density={density === 'hide' ? 'bounded-empty' : density}
    >
      <RoughSectionCard
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
        {density === 'hide' ? (
          <p
            className="mt-3 rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-muted)] px-3 py-2 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]"
            data-testid="stock-options-structure-metrics"
            data-module-density="bounded-empty"
          >
            {language === 'en'
              ? 'No authorized options metrics are populated yet. Empty metric cells are not shown.'
              : '尚未填充授权期权指标。不展示空指标格。'}
          </p>
        ) : (
          <div
            className={isCompact
              ? 'mt-3 grid gap-2 sm:grid-cols-2'
              : 'mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-3'}
            data-testid="stock-options-structure-metrics"
            data-module-density={density}
          >
            {metrics.map((metric) => (
              <div key={metric.key} className="rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-subtle)] p-3">
                <div className="text-[11px] font-semibold uppercase tracking-normal text-[color:var(--wolfy-text-muted)]">{metric.label}</div>
                <div className="mt-1 text-lg font-semibold tabular-nums text-[color:var(--wolfy-text-primary)]">{metric.value}</div>
                <div className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">{metric.detail}</div>
              </div>
            ))}
          </div>
        )}
      </RoughSectionCard>
    </div>
  );
}

function normalizeQuoteBoundaryToken(value: string | null | undefined): string {
  return String(value || '').trim().toLowerCase().replace(/[-\s]+/g, '_');
}

function hasQuoteCurrentPrice(quote: StockQuote | null | undefined): boolean {
  return typeof quote?.currentPrice === 'number' && Number.isFinite(quote.currentPrice);
}

function quoteBoundaryStateLabel(quote: StockQuote, language: 'zh' | 'en'): { label: string; variant: QuoteBoundaryChipVariant } {
  const sourceConfidence = quote.sourceConfidence;
  const freshness = normalizeQuoteBoundaryToken(sourceConfidence?.freshness || quote.freshness);
  const synthetic = Boolean(sourceConfidence?.isSynthetic || quote.isSynthetic || freshness === 'synthetic');
  const stale = Boolean(sourceConfidence?.isStale || quote.isStale || freshness === 'stale' || freshness === 'delayed');
  const unavailable = Boolean(sourceConfidence?.isUnavailable || quote.isUnavailable || freshness === 'unavailable' || !hasQuoteCurrentPrice(quote));
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
  if (normalizeQuoteBoundaryToken(quote.freshness) || hasQuoteCurrentPrice(quote)) {
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
  if (sourceConfidence?.isUnavailable || quote.isUnavailable || freshness === 'unavailable' || !hasQuoteCurrentPrice(quote)) {
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
  if (/\bohlcv\b\s*证据缺失时/i.test(raw)) {
    return safeConsumerText(raw, language, fallback);
  }
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

type StockHistoryComputationState = {
  label: string;
  detail: string;
  tone: 'success' | 'caution' | 'danger' | 'neutral';
};

type EvidenceStackBucket = 'available' | 'missing' | 'partial' | 'stale';

type EvidenceStackRow = {
  key: string;
  label: string;
  value: string;
  bucket: EvidenceStackBucket;
};

type StockEvidenceLedgerRow = {
  key: string;
  identity: string;
  state: string;
  status: string;
  freshness: string;
  asOf: string;
  scope: string;
  limitation: string;
  provenance: string;
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

type StockResearchConclusionView = {
  interpretation: string;
  supportingEvidence: string[];
  uncertainty: string[];
  invalidation: string[];
  nextAction: string;
};

function StockWorkspaceSection({
  eyebrow,
  title,
  children,
  testId,
  className = '',
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
  testId: string;
  className?: string;
}) {
  return (
    <section
      className={`stock-workspace-section min-w-0 ${className}`}
      data-testid={testId}
    >
      <div className="stock-workspace-section__header">
        <div className="min-w-0">
          <p className="stock-workspace-section__eyebrow">{eyebrow}</p>
          <h3 className="stock-workspace-section__title">{title}</h3>
        </div>
      </div>
      <div className="stock-workspace-section__body">
        {children}
      </div>
    </section>
  );
}

function StockCurrentConclusionPanel({
  view,
  language,
}: {
  view: StockResearchConclusionView;
  language: 'zh' | 'en';
}) {
  const isEnglish = language === 'en';
  return (
    <section
      className="stock-current-conclusion"
      data-testid="stock-current-research-conclusion"
      aria-labelledby="stock-current-research-conclusion-title"
    >
      <div className="stock-current-conclusion__header">
        <p className="stock-current-conclusion__eyebrow">{isEnglish ? 'Current Research Conclusion' : '当前研究结论'}</p>
        <h3 id="stock-current-research-conclusion-title" className="stock-current-conclusion__title">
          {view.interpretation}
        </h3>
      </div>
      <div className="stock-current-conclusion__grid">
        <div className="stock-current-conclusion__item stock-current-conclusion__item--primary">
          <span>{isEnglish ? 'Supporting evidence' : '支持证据'}</span>
          <RoughBulletList
            items={view.supportingEvidence}
            emptyText={isEnglish ? 'No supporting evidence is listed yet.' : '暂未列出支持证据。'}
          />
        </div>
        <div className="stock-current-conclusion__item">
          <span>{isEnglish ? 'Uncertainty' : '不确定性'}</span>
          <RoughBulletList
            items={view.uncertainty}
            emptyText={isEnglish ? 'No uncertainty note is listed yet.' : '暂未列出不确定性。'}
          />
        </div>
        <div className="stock-current-conclusion__item">
          <span>{isEnglish ? 'Invalidation / risk' : '失效 / 风险条件'}</span>
          <RoughBulletList
            items={view.invalidation}
            emptyText={isEnglish ? 'No invalidation condition is listed yet.' : '暂未列出失效条件。'}
          />
        </div>
        <div className="stock-current-conclusion__item">
          <span>{isEnglish ? 'Next research action' : '下一步研究动作'}</span>
          <p>{view.nextAction}</p>
        </div>
      </div>
    </section>
  );
}

function StockFactorEvidencePanel({
  scoreRows,
  packet,
  language,
}: {
  scoreRows: Array<{ key: string; label: string; value: number }>;
  packet: SymbolResearchPacket | null;
  language: 'zh' | 'en';
}) {
  const isEnglish = language === 'en';
  const stackRows = packet ? buildEvidenceStackRows(packet, language) : [];
  const readinessRows = stackRows.filter((row) => row.key !== 'quote' && row.key !== 'history');
  const availableReadiness = readinessRows.filter((row) => row.bucket === 'available' || row.bucket === 'partial' || row.bucket === 'stale');
  const meaningfulCount = scoreRows.length + availableReadiness.length;
  const density = resolveModuleDensity(meaningfulCount);

  if (density === 'hide' && !readinessRows.length) {
    return (
      <div
        className="stock-factor-evidence stock-factor-evidence--bounded-empty"
        data-testid="stock-factor-evidence-panel"
        data-module-density="bounded-empty"
      >
        <p className="rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-muted)] px-3 py-2 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
          {isEnglish
            ? 'No scored factor dimension is available for this packet.'
            : '当前研究包没有可展示的评分因子维度。'}
        </p>
      </div>
    );
  }

  return (
    <div
      className="stock-factor-evidence"
      data-testid="stock-factor-evidence-panel"
      data-module-density={density === 'hide' ? 'compact' : density}
    >
      {scoreRows.length ? (
        <RoughSectionCard eyebrow={isEnglish ? 'Factor evidence' : '因子证据'} title={isEnglish ? 'Component evidence by relevance' : '按相关性排列的组件证据'}>
          <RoughScoreRows
            items={scoreRows}
            emptyText={isEnglish ? 'No component score yet.' : '暂无组件评分。'}
          />
        </RoughSectionCard>
      ) : density === 'compact' ? (
        <p className="rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-muted)] px-3 py-2 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
          {isEnglish ? 'Factor scores pending; readiness state below is not treated as neutral evidence.' : '因子评分待确认；下方就绪度不按中性证据处理。'}
        </p>
      ) : null}
      {readinessRows.length ? (
        <RoughSectionCard eyebrow={isEnglish ? 'Data state' : '数据状态'} title={isEnglish ? 'Ready, partial, stale, unavailable' : '可用、部分、延迟、不可用'}>
          <RoughKeyValueRows
            rows={readinessRows.map((row) => ({
              key: row.key,
              label: row.label,
              value: row.value,
            }))}
          />
        </RoughSectionCard>
      ) : null}
    </div>
  );
}

function StockRiskTriggersPanel({
  data,
  missingSummary,
  language,
}: {
  data: StockStructureDecisionResponse;
  missingSummary: string | null;
  language: 'zh' | 'en';
}) {
  const isEnglish = language === 'en';
  const observedRisks = safeConsumerList([
    ...(data.riskObservations ?? []),
    ...(data.researchNotes.riskFlags ?? []),
  ], language).map((item) => mapConsumerStatusText(item, language));
  const invalidationRows = safeConsumerList(data.explanation.whatInvalidatesIt ?? [], language);
  const unknownEvidence = compactUnique([
    missingSummary,
    ...safeConsumerList(data.researchNotes.needsMoreEvidence ?? [], language),
    ...safeConsumerList(data.evidenceGaps ?? [], language),
  ].filter(Boolean) as string[]);

  const sections = [
    observedRisks.length ? {
      key: 'observed',
      eyebrow: isEnglish ? 'Observed risk evidence' : '已观察风险证据',
      title: isEnglish ? 'What is already visible' : '当前已经可见',
      items: observedRisks,
    } : null,
    invalidationRows.length ? {
      key: 'invalidation',
      eyebrow: isEnglish ? 'Invalidation context' : '失效条件',
      title: isEnglish ? 'What would change the interpretation' : '什么会改变当前解释',
      items: invalidationRows,
    } : null,
    unknownEvidence.length ? {
      key: 'unknown',
      eyebrow: isEnglish ? 'Unknown evidence' : '未知 / 待补证据',
      title: isEnglish ? 'Not inferred as neutral' : '不按中性值处理',
      items: unknownEvidence,
    } : null,
  ].filter(Boolean) as Array<{ key: string; eyebrow: string; title: string; items: string[] }>;

  const meaningfulCount = sections.reduce((total, section) => total + section.items.length, 0);
  const density = resolveModuleDensity(meaningfulCount);

  if (!sections.length) {
    return (
      <div
        className="stock-risk-triggers stock-risk-triggers--bounded-empty"
        data-testid="stock-risk-triggers-panel"
        data-module-density="bounded-empty"
      >
        <p className="rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-muted)] px-3 py-2 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
          {isEnglish
            ? 'No observed risk, invalidation, or unknown-evidence item is listed yet.'
            : '暂未列出已观察风险、失效条件或未知证据。'}
        </p>
      </div>
    );
  }

  return (
    <div
      className="stock-risk-triggers"
      data-testid="stock-risk-triggers-panel"
      data-module-density={density}
    >
      {sections.map((section) => (
        <RoughSectionCard key={section.key} eyebrow={section.eyebrow} title={section.title}>
          <RoughBulletList items={section.items} emptyText="" />
        </RoughSectionCard>
      ))}
    </div>
  );
}

function StockWorkspaceFactStrip({
  items,
  testId,
}: {
  items: { key: string; label: string; value: ReactNode }[];
  testId: string;
}) {
  if (!items.length) return null;
  return (
    <dl className="stock-workspace-fact-strip" data-testid={testId}>
      {items.map((item) => (
        <div key={item.key} className="stock-workspace-fact-strip__item">
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

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
    ? (language === 'en' ? 'Catalyst leads ready' : '催化线索可用')
    : (language === 'en' ? 'Earnings / catalyst evidence needed' : '财报 / 催化证据待补');
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
    ? (language === 'en' ? 'Research brief pending' : '研究资料待生成')
    : (language === 'en' ? 'Research brief ready' : '研究资料可用');
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
      label: language === 'en' ? 'Earnings / catalysts' : '财报 / 催化',
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
      label: language === 'en' ? 'Research brief' : '研究资料',
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

function formatLedgerFallback(language: 'zh' | 'en'): string {
  return language === 'en' ? 'Not available' : '暂不可用';
}

function stockEvidenceItemForSymbol(
  response: StockEvidenceResponse | null,
  symbol: string,
): StockEvidenceItem | null {
  const normalized = symbol.trim().toUpperCase();
  return response?.items.find((item) => item.symbol.trim().toUpperCase() === normalized)
    || response?.items[0]
    || null;
}

function readinessTierLabel(value: string | null | undefined, language: 'zh' | 'en'): string {
  const token = normalizeStockConsumerToken(value);
  if (token === 'sufficient') return language === 'en' ? 'Sufficient' : '足够';
  if (token === 'partial') return language === 'en' ? 'Partial' : '部分可用';
  if (token === 'insufficient') return language === 'en' ? 'Insufficient' : '证据不足';
  return formatLedgerFallback(language);
}

function readinessTierStatus(value: string | null | undefined): string {
  const token = normalizeStockConsumerToken(value);
  if (token === 'sufficient') return 'success';
  if (token === 'partial') return 'warning';
  if (token === 'insufficient') return 'error';
  return 'unknown';
}

function objectPresenceLabel(value: Record<string, unknown> | null | undefined, language: 'zh' | 'en'): string {
  if (value && Object.keys(value).length > 0) {
    return language === 'en' ? 'Returned' : '已返回';
  }
  if (value === null) {
    return language === 'en' ? 'Unavailable' : '不可用';
  }
  return formatLedgerFallback(language);
}

function objectPresenceStatus(value: Record<string, unknown> | null | undefined): string {
  if (value && Object.keys(value).length > 0) return 'success';
  if (value === null) return 'error';
  return 'warning';
}

function firstSafeLedgerText(values: Array<string | null | undefined>, language: 'zh' | 'en', fallback: string): string {
  return safeConsumerList(values, language)[0] || fallback;
}

function buildStockEvidenceLedgerRows({
  data,
  quote,
  quoteFailed,
  history,
  historyFailed,
  technicalIndicators,
  technicalFailed,
  researchPacket,
  researchPacketFailed,
  stockEvidence,
  stockEvidenceFailed,
  language,
}: {
  data: StockStructureDecisionResponse;
  quote: StockQuote | null;
  quoteFailed: boolean;
  history: StockHistoryResponse | null;
  historyFailed: boolean;
  technicalIndicators: StockTechnicalIndicatorsResponse | null;
  technicalFailed: boolean;
  researchPacket: SymbolResearchPacket | null;
  researchPacketFailed: boolean;
  stockEvidence: StockEvidenceResponse | null;
  stockEvidenceFailed: boolean;
  language: 'zh' | 'en';
}): StockEvidenceLedgerRow[] {
  const fallback = formatLedgerFallback(language);
  const evidenceItem = stockEvidenceItemForSymbol(stockEvidence, data.ticker);
  const evidenceReadiness = evidenceItem?.symbolEvidenceReadiness;
  const quoteFreshness = quote ? quoteBoundaryFreshnessLabel(quote, language) : null;
  const quoteState = quote ? quoteBoundaryStateLabel(quote, language) : null;
  const quoteTimestamp = formatQuoteTimestamp(
    quote?.sourceConfidence?.asOf || quote?.marketTimestamp || quote?.observedAt || quote?.updateTime || researchPacket?.quote.asOf || null,
    language,
  );
  const historyState = stockHistoryReadinessState({ history, failed: historyFailed, data, language });
  const technicalState = technicalIndicators
    ? technicalStatusLabel(technicalIndicators.status, language)
    : {
      label: technicalFailed ? (language === 'en' ? 'Indicators unavailable' : '指标暂不可用') : (language === 'en' ? 'Indicators pending' : '指标待确认'),
      status: technicalFailed ? 'error' : 'warning',
    };
  const structureReadModel = data.productReadModel || researchPacket?.productReadModel || null;
  const structureReadyState = productReadStateLabel(structureReadModel?.state || data.dataQuality.status, language);
  const structureProvenance = productReadProvenanceLine(structureReadModel, language) || (language === 'en' ? 'Structure read model' : '结构读模型');
  const structureWithheld = !productReadStrongConclusionAllowed(structureReadModel);
  const researchState = researchPacket
    ? statusLabel(researchPacket.researchStatus, language)
    : researchPacketFailed ? (language === 'en' ? 'Research packet unavailable' : '研究包暂不可用') : fallback;
  const researchStatus = researchPacket
    ? toneFor(researchPacket.researchStatus)
    : researchPacketFailed ? 'error' : 'warning';
  const evidenceState = evidenceReadiness
    ? readinessTierLabel(evidenceReadiness.readinessTier, language)
    : stockEvidenceFailed ? (language === 'en' ? 'Evidence API unavailable' : '证据接口暂不可用') : fallback;
  const evidenceStatus = evidenceReadiness
    ? readinessTierStatus(evidenceReadiness.readinessTier)
    : stockEvidenceFailed ? 'error' : 'warning';
  const historyAsOf = latestHistoryDate(history) || history?.sourceConfidence?.asOf || '';
  const technicalAsOf = technicalIndicators ? technicalAsOfLabel(technicalIndicators, language) : null;
  const packetFreshness = productReadFreshnessLabel(researchPacket?.productReadModel || null, language);
  const stockEvidenceAsOf = stockEvidence?.meta?.generatedAt ? formatQuoteTimestamp(stockEvidence.meta.generatedAt, language) : '';

  const rows: StockEvidenceLedgerRow[] = [
    {
      key: 'quote',
      identity: language === 'en' ? 'Quote' : '报价',
      state: quoteState?.label || (quoteFailed ? (language === 'en' ? 'Quote unavailable' : '报价暂不可用') : fallback),
      status: quote ? toneFor(quote.sourceConfidence?.freshness || quote.freshness || 'available') : (quoteFailed ? 'error' : 'warning'),
      freshness: quoteFreshness?.label || fallback,
      asOf: quoteTimestamp || fallback,
      scope: language === 'en' ? 'Latest available price' : '最新可用价格',
      limitation: quoteState?.label || (quoteFailed ? (language === 'en' ? 'Quote request failed.' : '报价请求失败。') : fallback),
      provenance: language === 'en' ? 'Quote read boundary' : '报价读取边界',
    },
    {
      key: 'history',
      identity: language === 'en' ? 'Price history' : '价格历史',
      state: historyState.label,
      status: historyToneStatus(historyState.tone),
      freshness: stockHistoryFreshnessLabel(history, historyFailed, language),
      asOf: historyAsOf || fallback,
      scope: language === 'en' ? 'Daily bars for chart and structure context' : '用于图表与结构语境的日线 K 线',
      limitation: historyState.detail,
      provenance: language === 'en' ? 'History read model' : '历史读模型',
    },
    {
      key: 'technical',
      identity: language === 'en' ? 'Technical indicators' : '技术指标',
      state: technicalState.label,
      status: technicalState.status,
      freshness: technicalIndicators ? technicalFreshnessLabel(technicalIndicators, language) : fallback,
      asOf: technicalAsOf || fallback,
      scope: language === 'en' ? 'Indicators derived from returned price history' : '基于已返回历史行情计算的指标',
      limitation: technicalIndicators
        ? firstSafeLedgerText([technicalIndicators.noAdviceDisclosure, technicalIndicators.dataQuality.status], language, language === 'en' ? 'No additional limitation listed.' : '未列出额外限制。')
        : (technicalFailed ? (language === 'en' ? 'Indicator request failed.' : '指标请求失败。') : fallback),
      provenance: language === 'en' ? 'Technical read model' : '技术读模型',
    },
    {
      key: 'structure',
      identity: language === 'en' ? 'Structure observation' : '结构观察',
      state: structureReadyState,
      status: productReadModelTone(structureReadModel?.state || data.dataQuality.status),
      freshness: productReadFreshnessLabel(structureReadModel, language) || fallback,
      asOf: structureReadModel?.freshness?.asOf || structureReadModel?.provenance?.asOf || fallback,
      scope: language === 'en' ? 'Consumer-visible structure state' : '消费者可见结构状态',
      limitation: structureWithheld
        ? (language === 'en' ? 'Strong conclusion withheld by the product read model.' : '产品读模型要求暂不形成强结论。')
        : firstSafeLedgerText(data.confidenceState?.reasons ?? [], language, language === 'en' ? 'Observation remains research-only.' : '当前仍为研究观察。'),
      provenance: structureProvenance,
    },
    {
      key: 'research-packet',
      identity: language === 'en' ? 'Research packet' : '研究包',
      state: researchState,
      status: researchStatus,
      freshness: packetFreshness || fallback,
      asOf: researchPacket?.quote.asOf || researchPacket?.productReadModel?.freshness?.asOf || fallback,
      scope: language === 'en' ? 'Identity, quote, history, fundamentals, events, and peer context' : '标识、报价、历史、基本面、事件与同业语境',
      limitation: researchPacket
        ? (buildEvidenceGapLabels(researchPacket, language)[0] || firstSafeLedgerText([researchPacket.nextDataAction, researchPacket.noAdviceDisclosure], language, language === 'en' ? 'Observation only.' : '仅观察。'))
        : (researchPacketFailed ? (language === 'en' ? 'Research packet request failed.' : '研究包请求失败。') : fallback),
      provenance: language === 'en' ? 'Product read model' : '产品读模型',
    },
    {
      key: 'stock-evidence',
      identity: language === 'en' ? 'Evidence readiness' : '证据就绪度',
      state: evidenceState,
      status: evidenceStatus,
      freshness: evidenceReadiness?.staleInputs.length
        ? (language === 'en' ? 'Some inputs may be stale' : '部分输入可能延迟')
        : stockEvidenceAsOf || fallback,
      asOf: stockEvidenceAsOf || fallback,
      scope: language === 'en' ? 'Stock Evidence consumer packet' : 'Stock Evidence 消费者证据包',
      limitation: evidenceReadiness
        ? firstSafeLedgerText([
          ...evidenceReadiness.evidenceMissing,
          ...evidenceReadiness.staleInputs,
          ...evidenceReadiness.dataQualityNotes,
          evidenceReadiness.noAdviceDisclosure,
        ], language, language === 'en' ? 'No evidence blocker listed.' : '未列出证据阻塞。')
        : (stockEvidenceFailed ? (language === 'en' ? 'Evidence packet request failed.' : '证据包请求失败。') : fallback),
      provenance: language === 'en' ? 'Stock Evidence read model' : 'Stock Evidence 读模型',
    },
    {
      key: 'fundamentals',
      identity: language === 'en' ? 'Fundamentals' : '基本面',
      state: researchPacket ? fundamentalsEvidenceLabel(researchPacket.fundamentals.state, language) : objectPresenceLabel(evidenceItem?.fundamental, language),
      status: researchPacket ? toneFor(researchPacket.fundamentals.state) : objectPresenceStatus(evidenceItem?.fundamental),
      freshness: evidenceItem?.stockEvidencePacket?.fundamentalsSummary?.freshness || fallback,
      asOf: evidenceItem?.stockEvidencePacket?.fundamentalsSummary?.period || fallback,
      scope: language === 'en' ? 'Financial and valuation fields where available' : '可用时展示财务与估值字段',
      limitation: evidenceItem?.stockEvidencePacket?.fundamentalsSummary?.missingFields?.length
        ? (language === 'en'
          ? `Missing fields: ${evidenceItem.stockEvidencePacket.fundamentalsSummary.missingFields.slice(0, 3).join(', ')}`
          : `缺失字段：${evidenceItem.stockEvidencePacket.fundamentalsSummary.missingFields.slice(0, 3).join('、')}`)
        : (researchPacket ? (buildEvidenceGapLabels(researchPacket, language).find((item) => /fundamental|基本面/i.test(item)) || fallback) : fallback),
      provenance: language === 'en' ? 'Fundamentals summary' : '基本面摘要',
    },
    {
      key: 'events',
      identity: language === 'en' ? 'Events / catalysts' : '事件 / 催化',
      state: researchPacket ? newsEvidenceLabel(researchPacket.events.state, researchPacket.events.latest.length > 0, language) : objectPresenceLabel(evidenceItem?.news, language),
      status: researchPacket ? toneFor(researchPacket.events.state) : objectPresenceStatus(evidenceItem?.news),
      freshness: typeof researchPacket?.events.latest[0]?.date === 'string' ? researchPacket.events.latest[0].date : fallback,
      asOf: typeof researchPacket?.events.latest[0]?.date === 'string' ? researchPacket.events.latest[0].date : fallback,
      scope: language === 'en' ? 'Earnings and catalyst leads' : '财报与催化线索',
      limitation: researchPacket?.events.latest.length
        ? firstSafeLedgerText(researchPacket.events.latest.map((item) => (typeof item.title === 'string' ? item.title : null)), language, fallback)
        : (researchPacket ? (buildEvidenceGapLabels(researchPacket, language).find((item) => /news|catalyst|事件|催化/i.test(item)) || fallback) : fallback),
      provenance: language === 'en' ? 'Event evidence boundary' : '事件证据边界',
    },
  ];

  return rows.filter((row) => row.identity && row.state);
}

function fundamentalsCategoryLabel(value: string, language: 'zh' | 'en'): string {
  const labels: Record<string, { zh: string; en: string }> = {
    companyProfile: { zh: '公司画像', en: 'Company profile' },
    financialStatements: { zh: '财报主字段', en: 'Financial statements' },
    margins: { zh: '利润率', en: 'Margins' },
    valuation: { zh: '估值字段', en: 'Valuation' },
    balanceSheet: { zh: '资产负债表', en: 'Balance sheet' },
    earnings: { zh: '财报日期', en: 'Earnings' },
    ownershipFlows: { zh: '持有人 / 资金流', en: 'Ownership / flows' },
  };
  return labels[value]?.[language] ?? value;
}

function fundamentalsCategoryStateLabel(value: string | null | undefined, language: 'zh' | 'en'): string {
  const token = normalizeStockConsumerToken(value);
  if (token === 'available') return language === 'en' ? 'ready' : '可用';
  if (token === 'stale' || token === 'delayed') return language === 'en' ? 'delayed' : '延迟';
  if (token === 'not_configured') return language === 'en' ? 'not configured' : '待配置';
  if (token === 'insufficient_permissions') return language === 'en' ? 'permission needed' : '权限待补';
  return language === 'en' ? 'needed' : '待补';
}

function safeFundamentalsAction(value: string | null | undefined, language: 'zh' | 'en'): string {
  const fallback = language === 'en'
    ? 'Connect a fundamentals data path before showing financial or valuation fields.'
    : '补齐基本面数据路径后再展示财务或估值字段。';
  if (!value || looksUnsafeForConsumer(value)) return fallback;
  return safeConsumerText(value, language, fallback);
}

function formatFundamentalsFields(fields: string[], language: 'zh' | 'en'): string {
  if (!fields.length) return language === 'en' ? 'No missing fields listed' : '未列出缺失字段';
  return fields.slice(0, 5).join(', ');
}

function buildFundamentalsReadinessRows(packet: SymbolResearchPacket, language: 'zh' | 'en'): Array<{
  key: string;
  label: string;
  value: string;
  detail?: string;
}> {
  const categories = packet.fundamentals.categories ?? {};
  return Object.entries(categories)
    .map(([key, category]) => ({
      key,
      label: fundamentalsCategoryLabel(key, language),
      value: `${fundamentalsCategoryLabel(key, language)}${fundamentalsCategoryStateLabel(category.state, language)}`,
      detail: formatFundamentalsFields(
        [
          ...(category.missingFields ?? []),
          ...(category.blockedFields ?? []),
          ...(category.staleFields ?? []),
        ],
        language,
      ),
    }))
    .slice(0, 6);
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
    !hasQuoteCurrentPrice(quote)
    || quote.sourceConfidence?.isUnavailable
    || quote.sourceConfidence?.isSynthetic
    || quote.isSynthetic
    || quote.isUnavailable
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
      className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3"
    >
      <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{entry.label}</h3>
            <TerminalChip variant={canExport ? 'success' : 'caution'}>
              {canExport ? (language === 'en' ? 'Available' : '可用') : (language === 'en' ? 'Pending evidence' : '待补证')}
            </TerminalChip>
          </div>
          <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">{entry.description}</p>
          <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
            {entry.contents.map((item) => (
              <TerminalChip key={item} variant="neutral">{item}</TerminalChip>
            ))}
          </div>
          {status ? (
            <p className="mt-2 text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">{status}</p>
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

function positiveInteger(value: unknown): number | null {
  const numeric = Number(value);
  return Number.isInteger(numeric) && numeric >= 0 ? numeric : null;
}

function historyBarsCount(history: StockHistoryResponse | null, data: StockStructureDecisionResponse): number {
  if (history?.data.length) return history.data.length;
  return positiveInteger(data.dataQuality.usableBars) ?? positiveInteger(data.dataQuality.observedBars) ?? 0;
}

function requiredHistoryBars(history: StockHistoryResponse | null, data: StockStructureDecisionResponse): number {
  return positiveInteger(data.dataQuality.requestedDays)
    ?? positiveInteger(history?.diagnostics?.requestedDays)
    ?? 90;
}

function historyMissingBars(history: StockHistoryResponse | null, data: StockStructureDecisionResponse): number {
  return Math.max(requiredHistoryBars(history, data) - historyBarsCount(history, data), 0);
}

function latestHistoryDate(history: StockHistoryResponse | null): string | null {
  const latest = history?.data.at(-1)?.date || history?.sourceConfidence?.asOf || history?.diagnostics?.localFallback?.latestTradeDate;
  return safeOptionalConsumerText(latest, 'en');
}

function stockHistorySourceLabel(history: StockHistoryResponse | null, language: 'zh' | 'en'): string {
  const source = normalizeStockConsumerToken(history?.source || history?.diagnostics?.source);
  const explicit = safeOptionalConsumerText(history?.sourceConfidence?.sourceLabel, language);
  const explicitToken = normalizeStockConsumerToken(explicit);
  if (source.includes('local') || source.includes('cache') || explicitToken.includes('local')) {
    return language === 'en' ? 'Local history data' : '本地历史数据';
  }
  if (explicit) return explicit;
  if (source.includes('yahoo')) {
    return 'Yahoo Finance';
  }
  if (source.includes('alpaca')) {
    return 'Alpaca';
  }
  return language === 'en' ? 'History source pending' : '历史来源待确认';
}

function stockHistoryFreshnessLabel(history: StockHistoryResponse | null, failed: boolean, language: 'zh' | 'en'): string {
  if (failed) return language === 'en' ? 'Quote delayed/unavailable' : '报价延迟/不可用';
  const token = normalizeStockConsumerToken(history?.sourceConfidence?.freshness || history?.diagnostics?.status);
  if (['fresh', 'current', 'live', 'available', 'success'].includes(token)) {
    return language === 'en' ? 'History available' : '历史数据可用';
  }
  if (['stale', 'delayed', 'cached', 'partial'].includes(token) || history?.sourceConfidence?.isStale || history?.sourceConfidence?.isPartial) {
    return language === 'en' ? 'Quote delayed/unavailable' : '报价延迟/不可用';
  }
  if (history?.data.length) {
    return language === 'en' ? 'History available' : '历史数据可用';
  }
  return language === 'en' ? 'Quote delayed/unavailable' : '报价延迟/不可用';
}

function chartCoverageLabel(availableBars: number, requiredBars: number, language: 'zh' | 'en'): string {
  return language === 'en'
    ? `${availableBars} / ${requiredBars} bars`
    : `${availableBars} / ${requiredBars} 根`;
}

function historyRangeLabel(points: StockHistoryPoint[], language: 'zh' | 'en'): string {
  const first = points[0]?.date;
  const last = points.at(-1)?.date;
  if (!first || !last) return language === 'en' ? 'Range pending' : '区间待确认';
  return `${first} → ${last}`;
}

function normalizeChartPoints(points: StockHistoryPoint[]): CoreMarketChartPoint[] {
  return points
    .filter((point) => Number.isFinite(point.close))
    .map((point) => ({
      date: point.date,
      open: point.open,
      high: point.high,
      low: point.low,
      close: point.close,
      volume: point.volume,
    }));
}

function stockConfidenceExplanation(
  confidence: string | null | undefined,
  language: 'zh' | 'en',
): string {
  const normalized = String(confidence || '').trim().toLowerCase();
  if (normalized === 'high') {
    return language === 'en'
      ? 'Confidence is high: quote, history, structure, and supporting evidence are mostly available, while freshness still needs routine review.'
      : '置信度为高：报价、历史、结构与辅助证据较完整，但仍需例行核验新鲜度。';
  }
  if (normalized === 'medium') {
    return language === 'en'
      ? 'Confidence is medium: quote, history, and structure evidence are available, but fundamentals, events, or peer evidence still limit conclusion strength.'
      : '置信度为中：报价、历史与结构证据可用，但基本面、事件或同业证据仍限制结论强度。';
  }
  return language === 'en'
    ? 'Confidence is low: key price, history, or structure evidence is limited, so the page keeps only verifiable facts.'
    : '置信度为低：关键价格、历史或结构证据不足，页面只保留可核验事实。';
}

function stockConsumerSummarySentence({
  data,
  quote,
  history,
  historyFailed,
  language,
}: {
  data: StockStructureDecisionResponse;
  quote: StockQuote | null;
  history: StockHistoryResponse | null;
  historyFailed: boolean;
  language: 'zh' | 'en';
}): string {
  const hasHistory = historyBarsCount(history, data) > 0;
  if (!hasHistory || historyFailed) {
    return language === 'en'
      ? 'Historical data is not available yet, so the price history visual is unavailable.'
      : '历史数据暂缺，价格走势图暂不可用。';
  }
  const displayState = productReadStrongConclusionAllowed(data.productReadModel)
    ? data.structureState
    : (productReadClassificationDisplayState(data.productReadModel) || 'withheld');
  const state = stockStructureStateLabel(displayState, language) || (language === 'en' ? 'under review' : '待确认');
  const freshness = quote ? quoteBoundaryFreshnessLabel(quote, language).label : (language === 'en' ? 'pending' : '待确认');
  return language === 'en'
    ? `${data.ticker} is currently ${state}; quote freshness is ${freshness}, and historical bars can be reviewed for price context.`
    : `${data.ticker} 当前呈现${state}，报价${freshness}，历史 K 线可用于查看走势。`;
}

function stockTechnicalTrustLabel(
  indicators: StockTechnicalIndicatorsResponse | null,
  failed: boolean,
  language: 'zh' | 'en',
): string {
  if (indicators) return technicalStatusLabel(indicators.status, language).label;
  if (failed) return language === 'en' ? 'Indicators unavailable' : '指标暂不可用';
  return language === 'en' ? 'Indicators pending' : '指标待确认';
}

function evidencePackTrustLabel(entry: SingleStockEvidencePackEntry | null, language: 'zh' | 'en'): string {
  if (!entry) return language === 'en' ? 'Pending' : '待生成';
  if (entry.state === 'available') return language === 'en' ? 'Available' : '可用';
  return language === 'en' ? 'Not ready yet' : '暂不可用';
}

function buildStockResearchConclusionView({
  data,
  quote,
  history,
  historyFailed,
  researchPacket,
  topScore,
  language,
}: {
  data: StockStructureDecisionResponse;
  quote: StockQuote | null;
  history: StockHistoryResponse | null;
  historyFailed: boolean;
  researchPacket: SymbolResearchPacket | null;
  topScore: { label: string; value: number } | undefined;
  language: 'zh' | 'en';
}): StockResearchConclusionView {
  const displayStructureState = productReadStrongConclusionAllowed(data.productReadModel)
    ? data.structureState
    : (productReadClassificationDisplayState(data.productReadModel) || 'withheld');
  const structureState = stockStructureStateLabel(displayStructureState, language)
    || (language === 'en' ? 'Under review' : '待确认');
  const confidenceValue = data.productReadModel?.confidence?.label || data.confidence;
  const confidence = confidenceLabel(confidenceValue, language);
  const availableBars = historyBarsCount(history, data);
  const requiredBars = requiredHistoryBars(history, data);
  const historyState = stockHistoryReadinessState({ history, failed: historyFailed, data, language });
  const quoteFreshness = quote ? quoteBoundaryFreshnessLabel(quote, language).label : null;
  const confirms = safeConsumerList(data.explanation.whatConfirmsIt ?? [], language);
  const risks = safeConsumerList([
    ...(data.explanation.whatInvalidatesIt ?? []),
    ...(data.riskObservations ?? []),
    ...(data.researchNotes.riskFlags ?? []),
  ], language).map((item) => mapConsumerStatusText(item, language));
  const gaps = compactUnique([
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
    ...safeConsumerList(data.researchNotes.needsMoreEvidence ?? [], language),
    ...safeConsumerList(data.evidenceGaps ?? [], language),
  ]);
  const nextAction = safeConsumerList(data.researchNotes.watchNext ?? [], language)[0]
    || safeOptionalConsumerText(researchPacket?.nextDataAction, language)
    || (language === 'en' ? 'Recheck after the next data refresh.' : '下一次数据刷新后复核。');

  return {
    interpretation: language === 'en'
      ? `${data.ticker} is in ${structureState}; confidence is ${confidence}.`
      : `${data.ticker} 当前为${structureState}；置信度为${confidence}。`,
    supportingEvidence: compactUnique([
      quoteFreshness ? (language === 'en' ? `Quote: ${quoteFreshness}` : `报价：${quoteFreshness}`) : null,
      availableBars > 0 ? chartCoverageLabel(availableBars, requiredBars, language) : historyState.label,
      topScore ? `${topScore.label} ${topScore.value}` : null,
      ...confirms,
    ].filter(Boolean) as string[]).slice(0, 4),
    uncertainty: compactUnique([
      ...gaps,
      productReadStrongConclusionAllowed(data.productReadModel || researchPacket?.productReadModel || null)
        ? null
        : (language === 'en' ? 'Strong conclusion is withheld by the product read model.' : '产品读模型要求暂不形成强结论。'),
    ].filter(Boolean) as string[]).slice(0, 4),
    invalidation: risks.length ? risks.slice(0, 4) : [
      language === 'en' ? 'No invalidation condition is listed yet.' : '暂未列出明确失效条件。',
    ],
    nextAction,
  };
}

function StockAnalystMemo({
  language,
  observation,
  why,
  reliability,
  nextCheck,
  limitations,
}: {
  language: 'zh' | 'en';
  observation: string;
  why: string;
  reliability: string;
  nextCheck: string;
  limitations: string[];
}) {
  const items = [
    {
      key: 'observation',
      label: language === 'en' ? 'Current observation' : '当前观察',
      value: observation,
    },
    {
      key: 'why',
      label: language === 'en' ? 'Why' : '为什么',
      value: why,
    },
    {
      key: 'reliability',
      label: language === 'en' ? 'Is the data reliable enough?' : '数据是否足够可靠',
      value: reliability,
    },
    {
      key: 'next',
      label: language === 'en' ? 'Next research check' : '下一步检查什么',
      value: nextCheck,
    },
  ];

  return (
    <section className="stock-analyst-memo" data-testid="stock-analyst-memo" aria-labelledby="stock-analyst-memo-title">
      <div className="stock-analyst-memo__header">
        <p className="stock-analyst-memo__eyebrow">{language === 'en' ? 'Analyst Memo' : 'Analyst Memo'}</p>
        <h3 id="stock-analyst-memo-title" className="stock-analyst-memo__title">
          {language === 'en' ? 'Observation brief' : '研究简报'}
        </h3>
      </div>
      <dl className="stock-analyst-memo__list">
        {items.map((item) => (
          <div key={item.key} className="stock-analyst-memo__item">
            <dt>{item.label}</dt>
            <dd>{item.value}</dd>
          </div>
        ))}
      </dl>
      <div className="stock-analyst-memo__limitations">
        <p>{language === 'en' ? 'Limitations / evidence gaps' : 'limitations / evidence gaps'}</p>
        {limitations.length ? (
          <ul>
            {limitations.slice(0, 4).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : (
          <span>{language === 'en' ? 'No additional evidence gap is listed.' : '当前未列出额外证据缺口。'}</span>
        )}
      </div>
    </section>
  );
}

function StockEvidenceLedger({
  rows,
  language,
}: {
  rows: StockEvidenceLedgerRow[];
  language: 'zh' | 'en';
}) {
  return (
    <section className="stock-evidence-ledger" data-testid="stock-evidence-ledger" aria-labelledby="stock-evidence-ledger-title">
      <div className="stock-evidence-ledger__header">
        <div>
          <p className="stock-evidence-ledger__eyebrow">{language === 'en' ? 'Evidence Ledger' : 'Evidence Ledger'}</p>
          <h3 id="stock-evidence-ledger-title" className="stock-evidence-ledger__title">
            {language === 'en' ? 'Evidence, freshness, and limitations' : '证据、新鲜度与限制'}
          </h3>
        </div>
        <p className="stock-evidence-ledger__note">
          {language === 'en'
            ? 'Rows remain separate when timestamps or evidence families differ.'
            : '不同证据族与时间戳保持分行展示。'}
        </p>
      </div>
      {rows.length ? (
        <div
          className="stock-evidence-ledger__scroll overflow-x-auto overscroll-x-contain no-scrollbar focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--wolfy-accent-focus)]"
          data-testid="stock-evidence-ledger-scroll"
          role="region"
          tabIndex={0}
          aria-label={language === 'en' ? 'Scrollable stock evidence ledger' : '可横向滚动的个股证据账本'}
        >
          <table className="stock-evidence-ledger__table product-table">
            <caption className="sr-only">
              {language === 'en' ? 'Stock research evidence ledger' : '个股研究证据账本'}
            </caption>
            <thead>
              <tr>
                <th scope="col">{language === 'en' ? 'Evidence' : '证据'}</th>
                <th scope="col">{language === 'en' ? 'State' : '状态'}</th>
                <th scope="col">{language === 'en' ? 'Freshness' : '新鲜度'}</th>
                <th scope="col">{language === 'en' ? 'As of' : '截至'}</th>
                <th scope="col">{language === 'en' ? 'Scope' : '范围'}</th>
                <th scope="col">{language === 'en' ? 'Limitation' : '限制'}</th>
                <th scope="col">{language === 'en' ? 'Provenance' : '来源边界'}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.key}>
                  <th scope="row">{row.identity}</th>
                  <td>
                    <StatusBadge status={row.status} label={row.state} size="sm" />
                  </td>
                  <td>{row.freshness}</td>
                  <td className="stock-evidence-ledger__mono">{row.asOf}</td>
                  <td>{row.scope}</td>
                  <td>{row.limitation}</td>
                  <td>{row.provenance}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <TerminalEmptyState title={language === 'en' ? 'Evidence ledger pending' : '证据账本待生成'}>
          {language === 'en'
            ? 'No meaningful evidence row is available for this symbol yet.'
            : '当前标的暂无可呈现的证据行。'}
        </TerminalEmptyState>
      )}
    </section>
  );
}

function StockConsumerResearchSummary({
  data,
  quote,
  history,
  historyFailed,
  technicalIndicators,
  technicalFailed,
  researchPacket,
  evidenceEntry,
  language,
  localize,
}: {
  data: StockStructureDecisionResponse;
  quote: StockQuote | null;
  history: StockHistoryResponse | null;
  historyFailed: boolean;
  technicalIndicators: StockTechnicalIndicatorsResponse | null;
  technicalFailed: boolean;
  researchPacket: SymbolResearchPacket | null;
  evidenceEntry: SingleStockEvidencePackEntry | null;
  language: 'zh' | 'en';
  localize: (path: string) => string;
}) {
  const market = formatStockMarketLabel(researchPacket?.market || '', language);
  const exchange = safeOptionalConsumerText(researchPacket?.identity?.exchange, language);
  const name = safeOptionalConsumerText(researchPacket?.identity?.name || quote?.stockName, language);
  const price = formatStockPrice(quote?.currentPrice ?? researchPacket?.quote.price ?? null, researchPacket?.market || market);
  const change = formatSignedPercent(quote?.changePercent ?? researchPacket?.quote.changePercent ?? null);
  const timestamp = formatQuoteTimestamp(
    quote?.sourceConfidence?.asOf || quote?.marketTimestamp || quote?.observedAt || quote?.updateTime || researchPacket?.quote.asOf || null,
    language,
  );
  const displayStructureState = productReadStrongConclusionAllowed(data.productReadModel)
    ? data.structureState
    : (productReadClassificationDisplayState(data.productReadModel) || 'withheld');
  const structureState = stockStructureStateLabel(displayStructureState, language) || (language === 'en' ? 'Under review' : '待确认');
  const summary = stockConsumerSummarySentence({ data, quote, history, historyFailed, language });
  const confidenceValue = data.productReadModel?.confidence?.label || data.confidence;
  const confidence = confidenceLabel(confidenceValue, language);
  const confidenceText = stockConfidenceExplanation(confidenceValue, language);
  const productFreshness = productReadFreshnessLabel(data.productReadModel || researchPacket?.productReadModel || null, language);
  const canCopyEvidence = Boolean(evidenceEntry?.exportContent);
  const availableBars = historyBarsCount(history, data);
  const requiredBars = requiredHistoryBars(history, data);
  const missingBars = historyMissingBars(history, data);
  const historyState = stockHistoryReadinessState({ history, failed: historyFailed, data, language });
  const technicalTrust = stockTechnicalTrustLabel(technicalIndicators, technicalFailed, language);
  const evidenceTrust = evidencePackTrustLabel(evidenceEntry, language);
  const quoteTrust = quote ? quoteBoundaryFreshnessLabel(quote, language).label : (language === 'en' ? 'Quote pending' : '报价待确认');
  const topScore = Object.entries(data.componentScores ?? {})
    .sort(([, left], [, right]) => (right ?? 0) - (left ?? 0))
    .map(([key, value]) => ({
      label: localLabel(key, language),
      value,
    }))[0];
  const conclusionView = buildStockResearchConclusionView({
    data,
    quote,
    history,
    historyFailed,
    researchPacket,
    topScore,
    language,
  });
  const keyEvidence = [
    availableBars > 0 ? (language === 'en' ? `${availableBars} historical bars` : `${availableBars} 根历史 K 线`) : null,
    topScore ? `${topScore.label} ${topScore.value}` : null,
    safeConsumerList(data.explanation.whatConfirmsIt ?? [], language)[0] || null,
  ].filter(Boolean) as string[];
  const limitation = (
    missingBars > 0 && availableBars > 0
      ? (language === 'en' ? 'History sample is still short for the full structure window.' : '历史样本仍短于完整结构窗口。')
      : buildMissingDataSummary(data, language)
        || safeConsumerList(data.researchNotes.needsMoreEvidence ?? [], language)[0]
        || (language === 'en' ? 'No major limitation is listed in the visible packet.' : '当前可见研究包未列出主要限制。')
  );
  const nextCheck = safeConsumerList(data.researchNotes.watchNext ?? [], language)[0]
    || safeConsumerList(data.researchNotes.needsMoreEvidence ?? [], language)[0]
    || (language === 'en' ? 'Recheck after the next data refresh.' : '下一次数据刷新后复核。');
  const whyText = safeOptionalConsumerText(data.explanation.whyThisStructure, language)
    || keyEvidence[0]
    || (language === 'en' ? 'The page only has enough evidence for a bounded observation.' : '当前页面只足以形成有边界的观察。');
  const reliabilityText = productReadStrongConclusionAllowed(data.productReadModel || researchPacket?.productReadModel || null)
    ? confidenceText
    : (language === 'en'
      ? `${confidenceText} Strong conclusion is withheld by the product read model.`
      : `${confidenceText} 产品读模型要求暂不形成强结论。`);
  const limitationItems = compactUnique([
    limitation,
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
    ...safeConsumerList(data.researchNotes.needsMoreEvidence ?? [], language),
  ]).slice(0, 5);
  const disclosure = language === 'en'
    ? 'Research observation, not investment advice.'
    : '研究观察，不构成投资建议。';

  const handleCopyEvidence = () => {
    if (!evidenceEntry?.exportContent || typeof navigator === 'undefined' || !navigator.clipboard) return;
    void navigator.clipboard.writeText(evidenceEntry.exportContent);
  };

  const trustItems = [
    { key: 'quote', label: language === 'en' ? 'Quote' : '报价', value: quoteTrust, meaningful: Boolean(quote) },
    {
      key: 'history',
      label: language === 'en' ? 'History' : '历史',
      value: availableBars > 0 ? chartCoverageLabel(availableBars, requiredBars, language) : (language === 'en' ? 'History pending' : '历史待补'),
      meaningful: availableBars > 0,
    },
    {
      key: 'technical',
      label: language === 'en' ? 'Technicals' : '技术指标',
      value: technicalTrust,
      meaningful: Boolean(technicalIndicators) && !technicalFailed,
    },
    {
      key: 'evidence',
      label: language === 'en' ? 'Evidence' : '证据',
      value: evidenceTrust,
      meaningful: evidenceEntry?.state === 'available',
    },
  ];
  // Always surface trust chips that carry real readiness; pending-only chips stay compact (max 4, never empty wall).
  const trustDensity = resolveModuleDensity(trustItems.filter((item) => item.meaningful).length);

  return (
    <section
      className="stock-research-hero p-3 md:p-4"
      data-testid="stock-consumer-research-summary"
      data-research-sequence="identity-price-path-memo-metrics-limitation-next"
      data-first-screen-priority="conclusion-first"
    >
      <div className="stock-research-identity-header rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-muted)] p-4" data-testid="stock-research-identity-header">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <h2 className="stock-research-identity-header__ticker text-2xl font-semibold text-[color:var(--wolfy-text-primary)]">{data.ticker}</h2>
          {name ? <span className="text-sm text-[color:var(--wolfy-text-secondary)]">{name}</span> : null}
          <TerminalChip variant="neutral">{[market, exchange].filter(Boolean).join(' · ') || '--'}</TerminalChip>
          <TerminalChip variant="neutral">{timestamp ? `${language === 'en' ? 'Updated' : '更新'} ${timestamp}` : (language === 'en' ? 'Update time pending' : '更新时间待确认')}</TerminalChip>
        </div>
        <div className="mt-3 flex min-w-0 flex-wrap items-end gap-3">
          <span className="stock-research-identity-header__price text-3xl font-semibold tabular-nums text-[color:var(--wolfy-text-primary)]">{price}</span>
          <span className={change.startsWith('-') ? 'stock-price-change stock-price-change--down' : 'stock-price-change stock-price-change--up'}>{change}</span>
          <StatusBadge status={toneFor(confidenceValue)} label={`${language === 'en' ? 'Confidence' : '置信度'}：${confidence}`} size="sm" />
          <StatusBadge status={toneFor(displayStructureState)} label={structureState} size="sm" />
        </div>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.65fr)_minmax(360px,0.85fr)]">
        <div className="min-w-0 space-y-3">
          <div data-testid="stock-price-history-visual-block" data-primary-analytical-surface="price-path">
            <StockHistoryCoreChart
              history={history}
              failed={historyFailed}
              data={data}
              language={language}
            />
          </div>
          <StockCurrentConclusionPanel view={conclusionView} language={language} />
        </div>
        <aside className="stock-research-memo-panel min-w-0 rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-input)] p-4" data-testid="stock-first-viewport-summary-panel">
          <div className="flex flex-wrap gap-2">
            <StatusBadge status={toneFor(confidenceValue)} label={`${language === 'en' ? 'Research state' : '研究状态'}：${confidence}`} size="sm" />
            <StatusBadge status={historyToneStatus(historyState.tone)} label={historyState.label} size="sm" />
          </div>
          <ProductReadModelStatusStrip
            model={data.productReadModel || researchPacket?.productReadModel || null}
            language={language}
            title={language === 'en' ? 'Structure readiness' : '结构读模型'}
            testId="stock-structure-product-read-model"
            className="mt-3"
          />
          <StockAnalystMemo
            language={language}
            observation={summary}
            why={whyText}
            reliability={reliabilityText}
            nextCheck={nextCheck}
            limitations={limitationItems}
          />
          <div
            className={trustDensity === 'full'
              ? 'mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-1'
              : 'mt-4 grid gap-2 sm:grid-cols-2'}
            data-testid="stock-data-trust-row"
            data-module-density={trustDensity === 'hide' ? 'compact' : trustDensity}
          >
            {trustItems.map((item) => (
              <div key={item.key} className="rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-muted)] px-3 py-2">
                <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">{item.label}</p>
                <p className="mt-1 text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{item.value}</p>
              </div>
            ))}
          </div>
          <p className="mt-4 rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-muted)] px-3 py-2 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]" data-testid="stock-compact-no-advice">
            {disclosure}
          </p>
          {productFreshness ? (
            <p className="mt-3 rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-muted)] px-3 py-2 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]" data-testid="stock-product-read-model-freshness">
              {productFreshness}
            </p>
          ) : null}
          <p className="mt-3 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">{confidenceText}</p>
          <div className="mt-4 flex flex-wrap gap-2" data-testid="stock-first-viewport-next-actions">
            <Link
              to={localize('/research/radar')}
              className="rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-primary)] hover:border-[color:var(--wolfy-accent)]"
            >
              {language === 'en' ? 'Open Research Radar' : '查看研究雷达'}
            </Link>
            <Link
              to={localize(`/backtest?symbol=${encodeURIComponent(data.ticker)}`)}
              className="rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-primary)] hover:border-[color:var(--wolfy-accent)]"
            >
              {language === 'en' ? 'Open Backtest' : '打开回测'}
            </Link>
            <button
              type="button"
              className="rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-primary)] hover:border-[color:var(--wolfy-accent)] disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!canCopyEvidence}
              onClick={handleCopyEvidence}
              data-testid="stock-first-viewport-copy-evidence"
            >
              {language === 'en' ? 'Copy evidence' : '复制证据'}
            </button>
          </div>
        </aside>
      </div>
    </section>
  );
}

function hasDisabledHistoryBoundary(history: StockHistoryResponse | null, failed: boolean): boolean {
  if (failed) return true;
  if (!history) return false;
  if (history.sourceConfidence?.isUnavailable) return true;
  const boundaryText = [
    history.diagnostics?.status,
    history.diagnostics?.reason,
    history.diagnostics?.message,
    history.diagnostics?.error,
    history.sourceConfidence?.degradationReason,
    history.sourceConfidence?.capReason,
  ].filter(Boolean).join(' ').toLowerCase();
  return /disabled|unavailable|not_configured|not configured|cache_miss|cache miss|missing|provider/.test(boundaryText)
    && history.data.length === 0;
}

function stockHistoryReadinessState({
  history,
  failed,
  data,
  language,
}: {
  history: StockHistoryResponse | null;
  failed: boolean;
  data: StockStructureDecisionResponse;
  language: 'zh' | 'en';
}): StockHistoryComputationState {
  const isEnglish = language === 'en';
  const bars = historyBarsCount(history, data);
  const missing = historyMissingBars(history, data);
  if (bars > 0) {
    return {
      label: isEnglish ? 'History available' : '历史数据可用',
      detail: missing > 0
        ? (isEnglish
          ? 'Historical bars are present, but the structure read still needs more bars.'
          : '历史 K 线已返回，但结构计算仍缺少部分样本。')
        : (isEnglish
          ? 'Historical bars are present for this symbol.'
          : '该标的已有历史 K 线可用于页面展示。'),
      tone: missing > 0 ? 'caution' : 'success',
    };
  }
  if (hasDisabledHistoryBoundary(history, failed)) {
    return {
      label: isEnglish ? 'History source disabled' : '历史来源未启用',
      detail: isEnglish
        ? 'No historical bars were returned from the configured source or local store.'
        : '当前历史来源或本地存储未返回 K 线数据。',
      tone: 'danger',
    };
  }
  return {
    label: isEnglish ? 'History missing' : '历史数据待补',
    detail: isEnglish
      ? 'The page did not receive historical bars for this symbol.'
      : '页面暂未收到该标的历史 K 线。',
    tone: 'caution',
  };
}

function structureComputationState(
  data: StockStructureDecisionResponse,
  missingBars: number,
  language: 'zh' | 'en',
): StockHistoryComputationState {
  const isEnglish = language === 'en';
  const status = normalizeStockConsumerToken(data.dataQuality.status);
  const reason = normalizeStockConsumerToken(data.dataQuality.reason);
  if (/timeout|timed_out/.test(reason) || /timeout|timed_out/.test(status)) {
    return {
      label: isEnglish ? 'Computation timed out' : '结构计算超时',
      detail: isEnglish
        ? 'The structure service returned a timed-out or partial computation state.'
        : '结构服务返回超时或部分计算状态。',
      tone: 'danger',
    };
  }
  if (missingBars > 0) {
    return {
      label: isEnglish ? 'History insufficient for structure' : '结构样本不足',
      detail: isEnglish
        ? 'The page shows available history but does not infer structure from the short sample.'
        : '页面展示已有历史数据，但不会用短样本推断结构。',
      tone: 'caution',
    };
  }
  if (['degraded', 'partial', 'unavailable', 'blocked'].includes(status)) {
    return {
      label: isEnglish ? 'Computation degraded' : '结构计算降级',
      detail: isEnglish
        ? 'The structure response is present, but its data quality state is constrained.'
        : '结构响应已返回，但数据质量状态仍受约束。',
      tone: 'caution',
    };
  }
  return {
    label: isEnglish ? 'Structure computation populated' : '结构计算已返回',
    detail: isEnglish
      ? 'Structure fields came from the structure decision API.'
      : '结构字段来自结构决策接口。',
    tone: 'success',
  };
}

function historyToneStatus(tone: StockHistoryComputationState['tone']) {
  if (tone === 'success') return 'success';
  if (tone === 'danger') return 'error';
  if (tone === 'caution') return 'warning';
  return 'info';
}

function formatCompactNumber(value: number | null | undefined, language: 'zh' | 'en'): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '--';
  return new Intl.NumberFormat(language === 'en' ? 'en-US' : 'zh-CN', {
    maximumFractionDigits: 2,
  }).format(value);
}

function formatTechnicalValue(value: number | null | undefined, language: 'zh' | 'en'): string | null {
  if (typeof value !== 'number' || !Number.isFinite(value)) return null;
  return new Intl.NumberFormat(language === 'en' ? 'en-US' : 'zh-CN', {
    maximumFractionDigits: 3,
  }).format(value);
}

function technicalIndicatorValue(
  indicators: StockTechnicalIndicatorsResponse | null,
  key: keyof StockTechnicalIndicatorsResponse['indicators'],
  language: 'zh' | 'en',
): string | null {
  return formatTechnicalValue(indicators?.indicators[key]?.value ?? null, language);
}

function technicalStatusLabel(status: string | null | undefined, language: 'zh' | 'en'): { label: string; status: 'success' | 'warning' | 'error' | 'info' } {
  const token = normalizeStockConsumerToken(status);
  if (token === 'available' || token === 'ready') {
    return { label: language === 'en' ? 'Indicators available' : '指标可用', status: 'success' };
  }
  if (token === 'missing_cache' || token === 'missing') {
    return { label: language === 'en' ? 'Price history missing' : '本地行情待补', status: 'warning' };
  }
  if (token === 'insufficient_history' || token === 'insufficient') {
    return { label: language === 'en' ? 'History insufficient' : '历史样本不足', status: 'warning' };
  }
  if (token === 'error' || token === 'failed') {
    return { label: language === 'en' ? 'Indicators unavailable' : '指标暂不可用', status: 'error' };
  }
  return { label: language === 'en' ? 'Indicators pending' : '指标待确认', status: 'info' };
}

function technicalFreshnessLabel(
  indicators: StockTechnicalIndicatorsResponse,
  language: 'zh' | 'en',
): string {
  const freshness = normalizeStockConsumerToken(indicators.freshness || indicators.dataQuality.freshness || indicators.dataQuality.freshnessState);
  if (freshness === 'current' || freshness === 'fresh' || freshness === 'live') {
    return language === 'en' ? 'Latest available' : '最新可用';
  }
  if (freshness === 'stale' || freshness === 'delayed') {
    return language === 'en' ? 'May be delayed' : '可能延迟';
  }
  const timestamp = formatQuoteTimestamp(indicators.asOf, language);
  if (timestamp) return `${language === 'en' ? 'Updated' : '更新'} ${timestamp}`;
  return language === 'en' ? 'Freshness pending' : '新鲜度待确认';
}

function technicalAsOfLabel(
  indicators: StockTechnicalIndicatorsResponse,
  language: 'zh' | 'en',
): string | null {
  const timestamp = formatQuoteTimestamp(indicators.asOf, language);
  if (!timestamp) return null;
  return `${language === 'en' ? 'Updated' : '更新'} ${timestamp}`;
}

function StockHistoryCoreChart({
  history,
  failed,
  data,
  language,
}: {
  history: StockHistoryResponse | null;
  failed: boolean;
  data: StockStructureDecisionResponse;
  language: 'zh' | 'en';
}) {
  const isEnglish = language === 'en';
  const availableBars = historyBarsCount(history, data);
  const requiredBars = requiredHistoryBars(history, data);
  const missingBars = historyMissingBars(history, data);
  const latestDate = latestHistoryDate(history);
  const chartPoints = history?.data ?? [];
  const chartStatusLabel = availableBars > 0
    ? (isEnglish ? 'History available' : '历史数据可用')
    : (isEnglish ? 'History missing' : '历史数据待补');
  const insufficientLabel = missingBars > 0 && availableBars > 0
    ? (isEnglish ? 'History sample insufficient' : '历史样本不足')
    : null;

  if (!chartPoints.length) {
    return (
      <TerminalEmptyState
        className="min-h-[320px] items-start justify-center rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-muted)] md:min-h-[430px]"
        data-testid="stock-history-empty-chart-state"
        title={isEnglish ? 'Chart unavailable' : '图表暂不可用'}
      >
        {isEnglish
          ? 'History missing. No historical bars were returned, so the page shows readiness counts only.'
          : '历史数据待补。未返回历史 K 线，页面仅展示就绪度计数。'}
      </TerminalEmptyState>
    );
  }

  return (
    <CoreMarketChart
      testId="stock-history-core-chart"
      chartKind="stock-history"
      title={isEnglish ? `${data.ticker} price and volume history` : `${data.ticker} 价格与成交量历史`}
      subtitle={isEnglish ? 'Returned price and volume bars only. Missing days are not filled.' : '仅使用接口返回的价格与成交量 K 线，缺失日期不补齐。'}
      points={normalizeChartPoints(chartPoints)}
      language={language}
      statusLabel={chartStatusLabel}
      statusTone={missingBars > 0 ? 'warning' : 'success'}
      sourceLabel={stockHistorySourceLabel(history, language)}
      freshnessLabel={stockHistoryFreshnessLabel(history, failed, language)}
      rangeLabel={historyRangeLabel(chartPoints, language)}
      latestLabel={latestDate || undefined}
      coverageLabel={chartCoverageLabel(availableBars, requiredBars, language)}
      warningLabel={insufficientLabel}
      emptyTitle={isEnglish ? 'Chart unavailable' : '图表暂不可用'}
      emptyDetail={isEnglish ? 'Historical bars are unavailable, so no price line is drawn.' : '历史 K 线暂不可用，因此不绘制价格线。'}
      showVolume
    />
  );
}

function technicalSourceBoundaryLabel(
  indicators: StockTechnicalIndicatorsResponse,
  language: 'zh' | 'en',
): string {
  const safeLabel = safeOptionalConsumerText(indicators.sourceLabel, language);
  if (safeLabel) return safeLabel;
  return language === 'en' ? 'Local price-history boundary' : '本地价格历史边界';
}

function technicalHistoryRows(
  indicators: StockTechnicalIndicatorsResponse | null,
  language: 'zh' | 'en',
) {
  const quality = indicators?.dataQuality ?? {};
  const required = quality.requiredBars;
  const observed = quality.observedBars ?? quality.usableBars;
  const missing = quality.missingBars ?? (
    typeof required === 'number' && typeof observed === 'number'
      ? Math.max(required - observed, 0)
      : null
  );
  return [
    {
      key: 'required-bars',
      label: language === 'en' ? 'Required history' : '所需历史',
      value: typeof required === 'number' ? formatCompactNumber(required, language) : (language === 'en' ? 'not listed' : '未列明'),
    },
    {
      key: 'observed-bars',
      label: language === 'en' ? 'Observed history' : '已观察历史',
      value: typeof observed === 'number' ? formatCompactNumber(observed, language) : (language === 'en' ? 'not received' : '未收到'),
    },
    {
      key: 'missing-bars',
      label: language === 'en' ? 'History gap' : '历史缺口',
      value: typeof missing === 'number' ? formatCompactNumber(missing, language) : (language === 'en' ? 'unknown' : '待补证'),
    },
  ];
}

function technicalMetricRows(
  indicators: StockTechnicalIndicatorsResponse,
  language: 'zh' | 'en',
) {
  return [
    ['sma20', 'SMA 20'],
    ['sma50', 'SMA 50'],
    ['sma200', 'SMA 200'],
    ['ema12', 'EMA 12'],
    ['ema26', 'EMA 26'],
    ['rsi14', 'RSI 14'],
    ['macd', 'MACD'],
    ['macdSignal', language === 'en' ? 'MACD signal' : 'MACD 信号线'],
    ['macdHistogram', language === 'en' ? 'MACD histogram' : 'MACD 柱'],
    ['bollingerUpper', language === 'en' ? 'Bollinger upper' : '布林带上轨'],
    ['bollingerMiddle', language === 'en' ? 'Bollinger middle' : '布林带中轨'],
    ['bollingerLower', language === 'en' ? 'Bollinger lower' : '布林带下轨'],
  ].map(([key, label]) => ({
    key,
    label,
    value: technicalIndicatorValue(indicators, key as keyof StockTechnicalIndicatorsResponse['indicators'], language),
  })).filter((row): row is { key: string; label: string; value: string } => Boolean(row.value));
}

function StockTechnicalIndicatorsPanel({
  indicators,
  failed,
  loading,
  language,
}: {
  indicators: StockTechnicalIndicatorsResponse | null;
  failed: boolean;
  loading: boolean;
  language: 'zh' | 'en';
}) {
  const isEnglish = language === 'en';

  if (loading && !indicators && !failed) {
    return (
      <div className="border-t border-[color:var(--wolfy-divider)] p-3" data-testid="stock-technical-indicators-panel">
        <RoughSectionCard eyebrow={isEnglish ? 'Technical indicators' : '技术指标'} title={isEnglish ? 'Loading indicators' : '正在读取技术指标'}>
          <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
            {isEnglish ? 'Loading cached price-history indicator context.' : '正在读取本地价格历史指标上下文。'}
          </p>
        </RoughSectionCard>
      </div>
    );
  }

  if (failed) {
    return (
      <div className="border-t border-[color:var(--wolfy-divider)] p-3" data-testid="stock-technical-indicators-panel">
        <RoughSectionCard eyebrow={isEnglish ? 'Technical indicators' : '技术指标'} title={isEnglish ? 'Indicators unavailable' : '技术指标暂不可用'}>
          <div className="mb-3 flex flex-wrap gap-2">
            <StatusBadge status="error" label={isEnglish ? 'Endpoint unavailable' : '接口暂不可用'} size="sm" />
            <TerminalChip variant="neutral">{isEnglish ? 'Research observation only' : '仅研究观察'}</TerminalChip>
          </div>
          <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
            {isEnglish
              ? 'The page received a safe error state and does not infer indicator values.'
              : '页面收到安全错误状态，不展示原始诊断，也不推断指标。'}
          </p>
        </RoughSectionCard>
      </div>
    );
  }

  if (!indicators) return null;

  const status = technicalStatusLabel(indicators.status, language);
  const statusToken = normalizeStockConsumerToken(indicators.status);
  const rows = technicalMetricRows(indicators, language);
  const isAvailable = statusToken === 'available' || statusToken === 'ready';
  const timeframe = periodLabel(indicators.timeframe, language) || indicators.timeframe || (isEnglish ? 'Daily' : '日线');
  const boundaryChips = [
    technicalSourceBoundaryLabel(indicators, language),
    technicalFreshnessLabel(indicators, language),
    technicalAsOfLabel(indicators, language),
    timeframe,
    isEnglish ? 'Research observation only' : '仅研究观察',
  ].filter(Boolean) as string[];

  if (isAvailable && rows.length) {
    return (
      <div className="border-t border-[color:var(--wolfy-divider)] p-3" data-testid="stock-technical-indicators-panel">
        <RoughSectionCard eyebrow={isEnglish ? 'Technical indicators' : '技术指标'} title={isEnglish ? 'Cached price-history indicators' : '本地价格历史技术指标'}>
          <div className="mb-3 flex flex-wrap gap-2">
            <StatusBadge status={status.status} label={status.label} size="sm" />
            {boundaryChips.map((label) => (
              <TerminalChip key={label} variant="neutral">{label}</TerminalChip>
            ))}
          </div>
          <RoughKeyValueRows rows={rows} />
          <p className="mt-3 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
            {isEnglish
              ? 'Research-only context from cached price history. No action instruction is generated.'
              : '仅作研究观察上下文，来自本地价格历史，不生成操作指令。'}
          </p>
        </RoughSectionCard>
      </div>
    );
  }

  const title = statusToken === 'missing_cache'
    ? (isEnglish ? 'Cached price history not available' : '本地价格历史暂不可用')
    : statusToken === 'insufficient_history'
      ? (isEnglish ? 'History is insufficient for indicators' : '历史样本不足，暂不计算指标')
      : (isEnglish ? 'Indicators not populated' : '技术指标待补证');
  const detail = statusToken === 'missing_cache'
    ? (isEnglish
      ? 'The cached price-history input is not available, so SMA, EMA, RSI, MACD, and Bollinger values are not shown.'
      : '本地价格历史暂不可用，因此不展示 SMA、EMA、RSI、MACD 与布林带数值。')
    : statusToken === 'insufficient_history'
      ? (isEnglish
        ? 'The observed history is shorter than the required window. The page does not calculate partial indicator values.'
        : '已观察历史短于所需窗口，页面不会计算部分或替代指标值。')
      : (isEnglish
        ? 'Indicator values are not present in the current contract.'
        : '当前合约未提供可展示的指标值。');

  return (
    <div className="border-t border-[color:var(--wolfy-divider)] p-3" data-testid="stock-technical-indicators-panel">
      <RoughSectionCard eyebrow={isEnglish ? 'Technical indicators' : '技术指标'} title={title}>
        <div className="mb-3 flex flex-wrap gap-2">
          <StatusBadge status={status.status} label={status.label} size="sm" />
          <TerminalChip variant="neutral">{isEnglish ? 'No inferred values' : '不推断指标'}</TerminalChip>
          <TerminalChip variant="neutral">{isEnglish ? 'Research observation only' : '仅研究观察'}</TerminalChip>
        </div>
        <RoughKeyValueRows rows={technicalHistoryRows(indicators, language)} />
        <p className="mt-3 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">{detail}</p>
      </RoughSectionCard>
    </div>
  );
}

function StockHistoryReadinessPanel({
  history,
  failed,
  data,
  language,
  showChart = true,
}: {
  history: StockHistoryResponse | null;
  failed: boolean;
  data: StockStructureDecisionResponse;
  language: 'zh' | 'en';
  showChart?: boolean;
}) {
  const isEnglish = language === 'en';
  const availableBars = historyBarsCount(history, data);
  const requiredBars = requiredHistoryBars(history, data);
  const missingBars = historyMissingBars(history, data);
  const historyState = stockHistoryReadinessState({ history, failed, data, language });
  const computationState = structureComputationState(data, missingBars, language);
  const latestDate = latestHistoryDate(history);

  return (
    <div className="border-t border-[color:var(--wolfy-divider)] p-3" data-testid="stock-history-readiness-panel">
      <RoughSectionCard
        eyebrow={isEnglish ? 'Price / volume history' : '价格与成交量历史'}
        title={isEnglish ? `${data.ticker} history readiness` : `${data.ticker} 历史数据就绪度`}
      >
        <div className="mb-3 flex flex-wrap gap-2">
          <StatusBadge status={historyToneStatus(historyState.tone)} label={historyState.label} size="sm" />
          <StatusBadge status={historyToneStatus(computationState.tone)} label={computationState.label} size="sm" />
          <TerminalChip variant="neutral">{periodLabel(history?.period || data.dataQuality.period, language) || (isEnglish ? 'Daily' : '日线')}</TerminalChip>
        </div>
        <RoughKeyValueRows
          rows={[
            {
              key: 'available-bars',
              label: isEnglish ? 'Available bars' : '可用 K 线',
              value: formatCompactNumber(availableBars, language),
            },
            {
              key: 'required-bars',
              label: isEnglish ? 'Required bars' : '所需 K 线',
              value: formatCompactNumber(requiredBars, language),
            },
            {
              key: 'missing-bars',
              label: isEnglish ? 'Missing bars' : '缺口 K 线',
              value: formatCompactNumber(missingBars, language),
            },
            {
              key: 'latest-date',
              label: isEnglish ? 'Latest history date' : '最新历史日期',
              value: latestDate || (isEnglish ? 'not received' : '未收到'),
            },
            {
              key: 'history-state',
              label: isEnglish ? 'History state' : '历史状态',
              value: historyState.detail,
            },
            {
              key: 'computation-state',
              label: isEnglish ? 'Structure computation' : '结构计算',
              value: computationState.detail,
            },
          ]}
        />
        {showChart ? (
          <div className="mt-4" data-testid="stock-price-history-visual-block">
            <StockHistoryCoreChart
              history={history}
              failed={failed}
              data={data}
              language={language}
            />
          </div>
        ) : null}
      </RoughSectionCard>
    </div>
  );
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

/**
 * Page-local fail-closed adapter for incomplete structure payloads.
 * Keeps required nested objects present without inventing bars/scores/evidence.
 * Lives here (not only API layer) so incomplete mock/runtime shapes cannot NPE render.
 */
function toStructureDecisionViewModel(
  payload: StockStructureDecisionResponse | null | undefined,
): StockStructureDecisionResponse | null {
  if (!payload || typeof payload !== 'object') return null;
  const dataQuality = payload.dataQuality && typeof payload.dataQuality === 'object'
    ? payload.dataQuality
    : {};
  const explanation = payload.explanation && typeof payload.explanation === 'object'
    ? payload.explanation
    : {};
  const researchNotes = payload.researchNotes && typeof payload.researchNotes === 'object'
    ? payload.researchNotes
    : {};

  return {
    ...payload,
    componentScores: payload.componentScores && typeof payload.componentScores === 'object'
      ? payload.componentScores
      : {},
    explanation: {
      whyThisStructure: explanation.whyThisStructure ?? null,
      whatConfirmsIt: Array.isArray(explanation.whatConfirmsIt) ? explanation.whatConfirmsIt : [],
      whatInvalidatesIt: Array.isArray(explanation.whatInvalidatesIt) ? explanation.whatInvalidatesIt : [],
      keyLevels: Array.isArray(explanation.keyLevels) ? explanation.keyLevels : [],
    },
    researchNotes: {
      watchNext: Array.isArray(researchNotes.watchNext) ? researchNotes.watchNext : [],
      needsMoreEvidence: Array.isArray(researchNotes.needsMoreEvidence) ? researchNotes.needsMoreEvidence : [],
      riskFlags: Array.isArray(researchNotes.riskFlags) ? researchNotes.riskFlags : [],
    },
    keyLevels: Array.isArray(payload.keyLevels) ? payload.keyLevels : [],
    evidenceNotes: Array.isArray(payload.evidenceNotes) ? payload.evidenceNotes : [],
    riskObservations: Array.isArray(payload.riskObservations) ? payload.riskObservations : [],
    evidenceGaps: Array.isArray(payload.evidenceGaps) ? payload.evidenceGaps : [],
    dataQuality: {
      status: dataQuality.status ?? null,
      source: dataQuality.source ?? null,
      period: dataQuality.period ?? null,
      // Preserve null/undefined — do not coerce missing bars to 0.
      requestedDays: dataQuality.requestedDays ?? null,
      observedBars: dataQuality.observedBars ?? null,
      usableBars: dataQuality.usableBars ?? null,
      reason: dataQuality.reason ?? null,
    },
    historicalOhlcvReadiness: payload.historicalOhlcvReadiness ?? null,
    missingEvidence: Array.isArray(payload.missingEvidence) ? payload.missingEvidence : [],
    degradedInputs: Array.isArray(payload.degradedInputs) ? payload.degradedInputs : [],
    consumerIssues: Array.isArray(payload.consumerIssues) ? payload.consumerIssues : [],
    drilldownLinks: Array.isArray(payload.drilldownLinks) ? payload.drilldownLinks : [],
  };
}

function hasMinimumResearchPacket(
  data: StockStructureDecisionResponse,
  scoreRows: Array<{ key: string; label: string; value: number }>,
  language: 'zh' | 'en',
): boolean {
  // Null-safe: incomplete structure payloads may omit dataQuality / nested sections.
  const usableBars = numericValue(data.dataQuality?.usableBars);
  const hasUsablePriceHistory = usableBars !== null && usableBars > 0;
  const hasStructureState = Boolean(safeOptionalConsumerText(data.structureState, language))
    && !isUnavailableStructureState(data.structureState);
  const explanation = data.explanation ?? { whyThisStructure: null, whatConfirmsIt: [], whatInvalidatesIt: [], keyLevels: [] };
  const researchNotes = data.researchNotes ?? { watchNext: [], needsMoreEvidence: [], riskFlags: [] };
  const hasExplanation = Boolean(safeOptionalConsumerText(explanation.whyThisStructure, language))
    || safeConsumerList(explanation.whatConfirmsIt ?? [], language).length > 0
    || safeConsumerList(explanation.whatInvalidatesIt ?? [], language).length > 0;
  const hasResearchNotes = safeConsumerList(researchNotes.watchNext ?? [], language).length > 0
    || safeConsumerList(researchNotes.riskFlags ?? [], language).length > 0;
  const hasKeyLevels = (explanation.keyLevels ?? []).some((level) => (
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
  facts,
  language,
}: {
  facts: StockResearchFact[];
  language: 'zh' | 'en';
}) {
  const isEnglish = language === 'en';

  return (
    <div className="grid gap-3" data-testid="stock-minimum-research-packet">
      <RoughSectionCard
        eyebrow={isEnglish ? 'Baseline research packet' : '基础研究包'}
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
      <div className="grid gap-3" data-testid="stock-research-packet-panel">
        <RoughSectionCard eyebrow={isEnglish ? 'Research brief' : '研究资料'} title={isEnglish ? 'Research brief pending' : '研究资料待更新'}>
          <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
            {isEnglish ? 'Refresh the research view after the stock data endpoint updates.' : '待个股数据接口更新后再复核。'}
          </p>
        </RoughSectionCard>
      </div>
    );
  }

  if (!packet) return null;

  const stackRows = buildEvidenceStackRows(packet, language);
  const displayRows = stackRows.filter((row) => row.key !== 'quote' && row.key !== 'history');
  const counts = evidenceStackCounts(displayRows);
  const countLabels = evidenceCountLabels(counts, language);
  const authorityLabels = evidenceAuthorityLabels(packet, language);
  const gapLabels = buildEvidenceGapLabels(packet, language);
  const fundamentalsRows = buildFundamentalsReadinessRows(packet, language);
  const fundamentalsCopy = safeOptionalConsumerText(packet.fundamentals.consumerSafeCopy, language);
  const fundamentalsAction = safeFundamentalsAction(packet.fundamentals.providerNeutralNextDataAction, language);
  const identityLabel = [
    safeOptionalConsumerText(packet.identity.name, language),
    safeOptionalConsumerText(packet.market, language),
  ].filter(Boolean).join(' · ') || packet.symbol;

  return (
    <div className="grid gap-3" data-testid="stock-research-packet-panel">
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
          rows={displayRows.map((row) => ({
            key: row.key,
            label: row.label,
            value: row.value,
          }))}
        />
      </RoughSectionCard>
      {(fundamentalsRows.length || fundamentalsCopy || fundamentalsAction) ? (
        <RoughSectionCard
          eyebrow={isEnglish ? 'Fundamentals boundary' : '基本面数据边界'}
          title={isEnglish ? 'Missing fundamentals are explicit' : '基本面缺口明确标记'}
        >
          {fundamentalsCopy ? (
            <p className="mb-3 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">{fundamentalsCopy}</p>
          ) : null}
          {fundamentalsRows.length ? (
            <RoughKeyValueRows rows={fundamentalsRows} />
          ) : null}
          <p className="mt-3 text-xs leading-5 text-[color:var(--wolfy-text-tertiary)]">{fundamentalsAction}</p>
        </RoughSectionCard>
      ) : null}
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

function catalystReadinessLabel(
  packet: SymbolResearchPacket | null,
  language: 'zh' | 'en',
): { label: string; status: 'success' | 'warning' | 'error' | 'info' } {
  if (!packet) return { label: language === 'en' ? 'Readiness pending' : '就绪度待确认', status: 'info' };
  const bucket = packet.events.latest.length > 0 ? 'available' : evidenceStateBucket(packet.events.state);
  if (bucket === 'available') return { label: language === 'en' ? 'Catalyst leads ready' : '催化线索可用', status: 'success' };
  if (bucket === 'stale') return { label: language === 'en' ? 'Catalyst leads may be delayed' : '催化线索可能延迟', status: 'warning' };
  if (bucket === 'partial') return { label: language === 'en' ? 'Catalyst evidence partial' : '催化证据部分可用', status: 'warning' };
  return { label: language === 'en' ? 'Earnings / catalyst evidence needed' : '财报 / 催化证据待补', status: 'warning' };
}

function StockEarningsCatalystReadinessPanel({
  packet,
  failed,
  language,
}: {
  packet: SymbolResearchPacket | null;
  failed: boolean;
  language: 'zh' | 'en';
}) {
  const isEnglish = language === 'en';
  const readiness = catalystReadinessLabel(packet, language);
  const latestCount = packet?.events.latest.length ?? 0;
  const eventGap = packet ? hasMissingData(packet, ['events', 'filing_event_catalyst']) : false;
  const nextAction = safeOptionalConsumerText(packet?.nextDataAction, language);
  const meaningfulCount = (latestCount > 0 ? 1 : 0)
    + (eventGap ? 1 : 0)
    + (nextAction ? 1 : 0)
    + (failed ? 0 : 1);
  const density = latestCount > 0 ? 'full' : resolveModuleDensity(Math.min(meaningfulCount, 2));
  const nextGapText = eventGap
    ? (isEnglish ? 'Filing, earnings, or catalyst evidence is still needed.' : '仍需补齐公告、财报或催化证据。')
    : (nextAction || (isEnglish ? 'No catalyst-specific gap is listed.' : '暂未列出财报 / 催化专项缺口。'));

  if (density !== 'full') {
    return (
      <div
        className="p-3 md:p-4"
        data-testid="stock-earnings-catalyst-readiness-panel"
        data-module-density={density === 'hide' ? 'bounded-empty' : 'compact'}
      >
        <RoughSectionCard
          eyebrow={isEnglish ? 'Earnings / catalysts' : '财报 / 催化'}
          title={isEnglish ? 'Catalyst readiness' : '催化就绪度'}
        >
          <div className="mb-2 flex flex-wrap gap-2">
            <StatusBadge status={failed ? 'warning' : readiness.status} label={failed ? (isEnglish ? 'Packet pending' : '研究包待更新') : readiness.label} size="sm" />
            <TerminalChip variant="neutral">{isEnglish ? 'No inferred events' : '不推断事件'}</TerminalChip>
          </div>
          <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
            {failed
              ? (isEnglish ? 'Catalyst packet pending; no events inferred.' : '催化研究包待更新，不推断事件。')
              : nextGapText}
          </p>
        </RoughSectionCard>
      </div>
    );
  }

  const rows = [
    {
      key: 'events-state',
      label: isEnglish ? 'Readiness' : '就绪度',
      value: readiness.label,
    },
    {
      key: 'latest-items',
      label: isEnglish ? 'Visible items' : '可见条目',
      value: String(latestCount),
    },
    {
      key: 'next-data',
      label: isEnglish ? 'Next missing data' : '下一缺口',
      value: nextGapText,
    },
  ];

  return (
    <div className="p-3 md:p-4" data-testid="stock-earnings-catalyst-readiness-panel" data-module-density="full">
      <RoughSectionCard
        eyebrow={isEnglish ? 'Earnings / catalysts' : '财报 / 催化'}
        title={isEnglish ? 'Catalyst readiness' : '催化就绪度'}
      >
        <div className="mb-3 flex flex-wrap gap-2">
          <StatusBadge status={failed ? 'warning' : readiness.status} label={failed ? (isEnglish ? 'Packet pending' : '研究包待更新') : readiness.label} size="sm" />
          <TerminalChip variant="neutral">{isEnglish ? 'No inferred events' : '不推断事件'}</TerminalChip>
        </div>
        <RoughKeyValueRows rows={rows} />
      </RoughSectionCard>
    </div>
  );
}

function buildMissingDataNextStepItems({
  data,
  packet,
  missingSummary,
  optionsStructure,
  optionsFailed,
  technicalIndicators,
  technicalFailed,
  history,
  historyFailed,
  language,
}: {
  data: StockStructureDecisionResponse;
  packet: SymbolResearchPacket | null;
  missingSummary: string | null;
  optionsStructure: OptionsStructureSummary | null;
  optionsFailed: boolean;
  technicalIndicators: StockTechnicalIndicatorsResponse | null;
  technicalFailed: boolean;
  history: StockHistoryResponse | null;
  historyFailed: boolean;
  language: 'zh' | 'en';
}): string[] {
  const isEnglish = language === 'en';
  const historyState = stockHistoryReadinessState({ history, failed: historyFailed, data, language });
  const technicalStatus = technicalIndicators ? technicalStatusLabel(technicalIndicators.status, language).label : null;
  const optionsReasons = optionsStructure ? optionsStructureReasonLabels(optionsStructure, language) : [];
  const items = [
    missingSummary,
    ...(packet ? buildEvidenceGapLabels(packet, language) : []),
    ...safeConsumerList(data.researchNotes.needsMoreEvidence ?? [], language),
    historyState.tone === 'success' ? null : historyState.label,
    technicalFailed ? (isEnglish ? 'Technical indicators are unavailable; no values are inferred.' : '技术指标暂不可用，不推断数值。') : null,
    technicalIndicators && !['available', 'ready'].includes(normalizeStockConsumerToken(technicalIndicators.status)) ? technicalStatus : null,
    optionsFailed ? (isEnglish ? 'Options structure is unavailable; no metrics are inferred.' : '期权结构暂不可用，不推断指标。') : null,
    ...optionsReasons,
  ];
  return compactUnique(items
    .map((item) => safeOptionalConsumerText(item, language))
    .filter(Boolean) as string[]).slice(0, 6);
}

function StockMissingDataNextStepsPanel({
  data,
  packet,
  missingSummary,
  optionsStructure,
  optionsFailed,
  technicalIndicators,
  technicalFailed,
  history,
  historyFailed,
  language,
  showAdminReadinessCue,
  symbol,
  localize,
}: {
  data: StockStructureDecisionResponse;
  packet: SymbolResearchPacket | null;
  missingSummary: string | null;
  optionsStructure: OptionsStructureSummary | null;
  optionsFailed: boolean;
  technicalIndicators: StockTechnicalIndicatorsResponse | null;
  technicalFailed: boolean;
  history: StockHistoryResponse | null;
  historyFailed: boolean;
  language: 'zh' | 'en';
  showAdminReadinessCue: boolean;
  symbol: string;
  localize: (path: string) => string;
}) {
  const isEnglish = language === 'en';
  const items = buildMissingDataNextStepItems({
    data,
    packet,
    missingSummary,
    optionsStructure,
    optionsFailed,
    technicalIndicators,
    technicalFailed,
    history,
    historyFailed,
    language,
  });
  const adminReadinessPath = localize(`/admin/market-providers?surface=stock_structure&symbol=${encodeURIComponent(symbol)}`);

  return (
    <div className="p-3 md:p-4" data-testid="stock-missing-data-next-steps-panel">
      <RoughSectionCard
        eyebrow={isEnglish ? 'Missing data' : '缺失资料'}
        title={isEnglish ? 'Next data to complete' : '下一步补齐资料'}
      >
        <RoughBulletList
          items={items}
          emptyText={isEnglish
            ? 'No additional missing-data item is listed for the current packet.'
            : '当前研究包暂未列出额外缺失资料。'}
        />
        {showAdminReadinessCue && items.length ? (
          <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-[color:var(--wolfy-divider)] pt-3">
            <TerminalChip variant="info">{isEnglish ? 'Admin only' : '仅管理员可见'}</TerminalChip>
            <Link
              to={adminReadinessPath}
              className="inline-flex min-h-9 items-center justify-center rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs font-medium text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)]"
            >
              {isEnglish ? 'Open data readiness diagnostics' : '打开数据就绪诊断'}
            </Link>
          </div>
        ) : null}
      </RoughSectionCard>
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
        eyebrow={language === 'en' ? 'Supporting evidence' : '支持证据'}
        title={language === 'en' ? 'Compare supporting evidence' : '对比支持证据'}
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
              <div key={`missing-${symbol}`} className="rounded-xl border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] px-3 py-2.5">
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
  const { isAdmin, isAdminAccount } = useProductSurface();
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
  const [history, setHistory] = useState<StockHistoryResponse | null>(null);
  const [historyFailed, setHistoryFailed] = useState(false);
  const [quote, setQuote] = useState<StockQuote | null>(null);
  const [quoteFailed, setQuoteFailed] = useState(false);
  const [technicalIndicators, setTechnicalIndicators] = useState<StockTechnicalIndicatorsResponse | null>(null);
  const [technicalIndicatorsFailed, setTechnicalIndicatorsFailed] = useState(false);
  const [stockEvidence, setStockEvidence] = useState<StockEvidenceResponse | null>(null);
  const [stockEvidenceFailed, setStockEvidenceFailed] = useState(false);
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
    setHistory(null);
    setHistoryFailed(false);
    setQuote(null);
    setQuoteFailed(false);
    setTechnicalIndicators(null);
    setTechnicalIndicatorsFailed(false);
    setStockEvidence(null);
    setStockEvidenceFailed(false);
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
        setData(toStructureDecisionViewModel(response.items[0] ?? null));
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
          setHistory(null);
          setHistoryFailed(false);
          setTechnicalIndicators(null);
          setTechnicalIndicatorsFailed(false);
          setStockEvidence(null);
          setStockEvidenceFailed(false);
          setComparePacket(null);
          setSymbolNotFound({
            symbol: validation.normalizedSymbol || validation.stockCode || primarySymbol,
          });
          return;
        }
        const [quoteResult, packetResult, responseResult, optionsResult, historyResult, technicalResult, stockEvidenceResult] = await Promise.allSettled([
          stocksApi.getQuote(primarySymbol),
          stocksApi.getResearchPacket(primarySymbol),
          stocksApi.getStructureDecision(primarySymbol),
          optionsLabApi.getOptionsStructure(primarySymbol),
          stocksApi.getHistory(primarySymbol, { period: 'daily', days: 180 }),
          stocksApi.getTechnicalIndicators(primarySymbol),
          stockEvidenceApi.getStockEvidence(primarySymbol),
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
        if (historyResult.status === 'fulfilled') {
          setHistory(historyResult.value);
          setHistoryFailed(false);
        } else {
          setHistoryFailed(true);
        }
        if (technicalResult.status === 'fulfilled') {
          setTechnicalIndicators(technicalResult.value);
          setTechnicalIndicatorsFailed(false);
        } else {
          setTechnicalIndicatorsFailed(true);
        }
        if (stockEvidenceResult.status === 'fulfilled') {
          setStockEvidence(stockEvidenceResult.value);
          setStockEvidenceFailed(false);
        } else {
          setStockEvidenceFailed(true);
        }
        if (responseResult.status === 'rejected') {
          throw responseResult.reason;
        }
        const response = responseResult.value;
        setData(toStructureDecisionViewModel(response));
        setComparePacket(null);
      }
    } catch (err) {
      setComparePacket(null);
      setSymbolNotFound(null);
      setError(getParsedApiError(err) || createParsedApiError({
        title: locale === 'en' ? 'Stock research pending' : '个股研究暂不可用',
        message: locale === 'en' ? 'Please retry after the stock research API responds again.' : '请在个股研究接口恢复后重试。',
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
  const safeWatchNext = data ? safeConsumerList(data.researchNotes.watchNext ?? [], locale) : [];
  const quoteBoundaryView = useMemo(
    () => buildQuoteBoundaryView(quote, quoteFailed, locale),
    [locale, quote, quoteFailed],
  );
  const stockWorkflowKnownEvidence = data ? safeConsumerList([
    data.structureState ? (locale === 'en' ? `Structure: ${stockStructureStateLabel(data.structureState, locale)}` : `结构：${stockStructureStateLabel(data.structureState, locale)}`) : null,
    quoteBoundaryView?.title,
    data.dataQuality.usableBars != null
      ? (locale === 'en' ? `Usable bars: ${data.dataQuality.usableBars}` : `可用 K 线：${data.dataQuality.usableBars}`)
      : null,
    researchPacket ? (locale === 'en' ? 'Research packet returned.' : '研究包已返回。') : null,
  ], locale) : [];
  const stockWorkflowMissingEvidence = data ? safeConsumerList([
    ...((data.missingEvidence ?? []).map((item) => item.message || item.kind)),
    ...(data.researchNotes.needsMoreEvidence ?? []),
    missingDataSummary,
  ], locale) : [];
  const stockWorkflowStateNotes = data ? safeConsumerList([
    data.noAdviceDisclosure,
    quoteBoundaryView?.detail,
    data.confidenceCap?.label,
    ...(data.confidenceCap?.reasons ?? []),
    statusLabel(data.dataQuality.status, locale),
  ], locale) : [];
  const stockWorkflowNextSteps = data ? safeConsumerList([
    ...(data.researchNotes.watchNext ?? []),
    locale === 'en' ? 'Compare queue context in Research Radar.' : '到研究雷达对比队列上下文。',
    locale === 'en' ? 'Track only if ongoing observation is needed.' : '只有需要持续观察时，再加入观察列表。',
    locale === 'en' ? 'Use Backtest for read-only validation before scenario review.' : '需要验证假设时，先用回测做只读复核。',
  ], locale) : [];
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
  const stockEvidenceLedgerRows = useMemo(
    () => (data ? buildStockEvidenceLedgerRows({
      data,
      quote,
      quoteFailed,
      history,
      historyFailed,
      technicalIndicators,
      technicalFailed: technicalIndicatorsFailed,
      researchPacket,
      researchPacketFailed,
      stockEvidence,
      stockEvidenceFailed,
      language: locale,
    }) : []),
    [
      data,
      history,
      historyFailed,
      locale,
      quote,
      quoteFailed,
      researchPacket,
      researchPacketFailed,
      stockEvidence,
      stockEvidenceFailed,
      technicalIndicators,
      technicalIndicatorsFailed,
    ],
  );
  const compareWithPeerPath = data && comparablePeerSymbol && !isCompareRequest
    ? localize(buildComparePath([data.ticker || primarySymbol, comparablePeerSymbol]))
    : null;
  const showAdminReadinessCue = Boolean(isAdmin || isAdminAccount);
  const introTitle = symbolNotFound
    ? (locale === 'en' ? 'Symbol not found' : '标的未找到')
    : (locale === 'en' ? `${titleSymbol} research workspace` : `${titleSymbol} 研究工作区`);
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
              eyebrow={locale === 'en' ? 'Stock research' : '个股研究'}
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
                <TerminalEmptyState title={locale === 'en' ? 'Loading stock research' : '正在整理个股研究'}>
                  {locale === 'en' ? 'Loading stock research.' : '正在载入个股研究。'}
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
              <div
                className="stock-workspace-product-flow"
                data-testid="stock-workspace-product-flow"
                data-product-flow="identity-data-state-current-conclusion-price-evidence-path-analyst-memo-factor-evidence-risk-triggers-peer-theme-context-evidence-ledger-data-limitations"
              >
                <StockConsumerResearchSummary
                  data={data}
                  quote={quote}
                  history={history}
                  historyFailed={historyFailed}
                  technicalIndicators={technicalIndicators}
                  technicalFailed={technicalIndicatorsFailed}
                  researchPacket={researchPacket}
                  evidenceEntry={singleStockEvidencePackEntry}
                  language={locale}
                  localize={localize}
                />

                <div className="stock-workspace-grid stock-workspace-grid--evidence" data-testid="stock-identity-data-state-workspace">
                  <StockWorkspaceSection
                    eyebrow={locale === 'en' ? 'Identity and data state' : '标的身份与数据状态'}
                    title={locale === 'en' ? 'Current instrument and bounded data state' : '当前标的与有边界的数据状态'}
                    testId="stock-known-facts-panel"
                  >
                    {quoteBoundaryView ? (
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
                    ) : null}
                    {hasResearchPacket ? (
                      <StockWorkspaceFactStrip
                        testId="stock-baseline-fact-strip"
                        items={[
                          {
                            key: 'ticker',
                            label: locale === 'en' ? 'Ticker' : '标的',
                            value: data.ticker,
                          },
                          {
                            key: 'data-status',
                            label: locale === 'en' ? 'Data status' : '数据状态',
                            value: <StatusBadge status={toneFor(data.dataQuality.status)} label={statusLabel(data.dataQuality.status, locale)} size="sm" />,
                          },
                          {
                            key: 'period',
                            label: locale === 'en' ? 'Period' : '周期',
                            value: periodLabel(data.dataQuality.period, locale) || (locale === 'en' ? 'not listed' : '未列明'),
                          },
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
                    ) : null}
                    <StockMinimumResearchPacket facts={packetFacts} language={locale} />
                  </StockWorkspaceSection>

                  <StockWorkspaceSection
                    eyebrow={locale === 'en' ? 'Price and evidence path' : '价格与证据路径'}
                    title={locale === 'en' ? 'Market path and technical evidence' : '市场路径与技术证据'}
                    testId="stock-history-technical-workspace"
                    className="stock-workspace-section--wide"
                  >
                    {!isCompareRequest && !symbolNotFound ? (
                      <>
                        <StockHistoryReadinessPanel
                          history={history}
                          failed={historyFailed}
                          data={data}
                          language={locale}
                          showChart={false}
                        />
                        <StockTechnicalIndicatorsPanel
                          indicators={technicalIndicators}
                          failed={technicalIndicatorsFailed}
                          loading={loading && !technicalIndicators && !technicalIndicatorsFailed}
                          language={locale}
                        />
                      </>
                    ) : (
                      <TerminalEmptyState title={locale === 'en' ? 'Price path unavailable' : '价格路径暂不可用'}>
                        {locale === 'en' ? 'Compare mode keeps the price path in each symbol evidence row.' : '对比模式下，价格路径保留在各标的证据行中。'}
                      </TerminalEmptyState>
                    )}
                  </StockWorkspaceSection>

                  <StockWorkspaceSection
                    eyebrow={locale === 'en' ? 'Catalyst / options evidence' : '催化 / 期权证据'}
                    title={locale === 'en' ? 'Supporting evidence readiness' : '支持证据就绪度'}
                    testId="stock-catalyst-options-workspace"
                    className="stock-workspace-section--wide"
                  >
                    <StockEarningsCatalystReadinessPanel
                      packet={researchPacket}
                      failed={researchPacketFailed}
                      language={locale}
                    />
                    {!isCompareRequest && !symbolNotFound ? (
                      <OptionsStructureSurface
                        structure={optionsStructure}
                        failed={optionsStructureFailed}
                        loading={loading && !optionsStructure && !optionsStructureFailed}
                        language={locale}
                      />
                    ) : null}
                  </StockWorkspaceSection>
                </div>

                <StockWorkspaceSection
                  eyebrow={locale === 'en' ? 'Analyst memo' : '分析备忘'}
                  title={locale === 'en' ? 'Research narrative and evidence stack' : '研究叙事与证据栈'}
                  testId="stock-analyst-memo-workspace"
                  className="stock-workspace-section--workflow"
                >
                  <StockResearchPacketPanel
                    packet={researchPacket}
                    failed={researchPacketFailed}
                    language={locale}
                  />
                  {isCompareRequest || comparePacket ? (
                    <SymbolCompareEvidencePacketPanel
                      packet={comparePacket}
                      language={locale}
                      requestedSymbols={requestedSymbols}
                    />
                  ) : null}
                  {hasResearchPacket ? (
                    <div className="grid gap-3 p-3 md:grid-cols-2">
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
                      {keyLevelRows.length ? (
                        <RoughSectionCard eyebrow={locale === 'en' ? 'Reference levels' : '参考位置'} title={locale === 'en' ? 'Key levels' : '关键位置'}>
                          <RoughKeyValueRows rows={keyLevelRows} />
                        </RoughSectionCard>
                      ) : null}
                    </div>
                  ) : (
                    <StockStructureCannotResearchState
                      data={data}
                      language={locale}
                      localize={localize}
                    />
                  )}
                </StockWorkspaceSection>

                <div className="stock-workspace-grid stock-workspace-grid--structure" data-testid="stock-structure-interpretation-workspace">
                  <StockWorkspaceSection
                    eyebrow={locale === 'en' ? 'Factor evidence' : '因子证据'}
                    title={locale === 'en' ? 'Meaningful factor evidence' : '按含义组织的因子证据'}
                    testId="stock-factor-evidence-workspace"
                  >
                    <StockFactorEvidencePanel
                      scoreRows={scoreRows}
                      packet={researchPacket}
                      language={locale}
                    />
                  </StockWorkspaceSection>

                  <StockWorkspaceSection
                    eyebrow={locale === 'en' ? 'Risk triggers' : '风险触发'}
                    title={locale === 'en' ? 'Observed risk and invalidation triggers' : '已观察风险与失效条件'}
                    testId="stock-risk-triggers-workspace"
                  >
                    <StockRiskTriggersPanel
                      data={data}
                      missingSummary={missingDataSummary}
                      language={locale}
                    />
                  </StockWorkspaceSection>

                  <StockWorkspaceSection
                    eyebrow={locale === 'en' ? 'Peer and theme context' : '同业与主题语境'}
                    title={locale === 'en' ? 'Supporting context, not a widget cluster' : '作为支持证据，而非零散组件'}
                    testId="stock-peer-theme-context-workspace"
                    className="stock-workspace-section--wide"
                  >
                    {hasPeerCorrelationContent(data.peerCorrelationSnapshot) ? (
                      <>
                        <PeerCorrelationSnapshotBlock
                          snapshot={data.peerCorrelationSnapshot}
                          locale={locale}
                          testId="stock-structure-peer-correlation-snapshot"
                        />
                        {compareWithPeerPath && comparablePeerSymbol ? (
                          <div className="p-3">
                            <CompareWithPeerLink
                              language={locale}
                              to={compareWithPeerPath}
                              peerSymbol={comparablePeerSymbol}
                            />
                          </div>
                        ) : null}
                      </>
                    ) : (
                      <p
                        className="rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-muted)] px-3 py-2 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]"
                        data-module-density="bounded-empty"
                        data-testid="stock-peer-theme-bounded-empty"
                      >
                        {locale === 'en'
                          ? 'Peer or theme evidence is not available yet; it is not treated as neutral.'
                          : '同业或主题证据暂不可用，不按中性证据处理。'}
                      </p>
                    )}
                  </StockWorkspaceSection>
                </div>

                <div className="stock-workspace-grid stock-workspace-grid--evidence" data-testid="stock-evidence-workspace">
                  <StockWorkspaceSection
                    eyebrow={locale === 'en' ? 'Evidence ledger' : '证据账本'}
                    title={locale === 'en' ? 'Lineage, freshness, and limitations' : '血缘、新鲜度与限制'}
                    testId="stock-evidence-ledger-workspace"
                    className="stock-workspace-section--wide stock-workspace-section--ledger"
                  >
                    <StockEvidenceLedger rows={stockEvidenceLedgerRows} language={locale} />
                  </StockWorkspaceSection>

                  <StockWorkspaceSection
                    eyebrow={locale === 'en' ? 'Evidence package' : '证据包'}
                    title={locale === 'en' ? 'Copyable research packet' : '可复制的研究证据'}
                    testId="stock-evidence-package-workspace"
                  >
                    {singleStockEvidencePackEntry ? (
                      <SingleStockEvidencePackControls
                        entry={singleStockEvidencePackEntry}
                        language={locale}
                      />
                    ) : (
                      <p
                        className="rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-muted)] px-3 py-2 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]"
                        data-testid="stock-evidence-package-unavailable-state"
                        data-module-density="bounded-empty"
                      >
                        {locale === 'en'
                          ? 'Evidence package unavailable. The visible record does not yet contain a copyable evidence package.'
                          : '证据包暂不可用。当前可见记录还没有可复制的证据包。'}
                      </p>
                    )}
                  </StockWorkspaceSection>

                  <StockWorkspaceSection
                    eyebrow={locale === 'en' ? 'Data limitations' : '数据限制'}
                    title={locale === 'en' ? 'Explicit limitations and next checks' : '明确限制与下一步检查'}
                    testId="stock-next-research-checks"
                  >
                    <StockMissingDataNextStepsPanel
                      data={data}
                      packet={researchPacket}
                      missingSummary={missingDataSummary}
                      optionsStructure={optionsStructure}
                      optionsFailed={optionsStructureFailed}
                      technicalIndicators={technicalIndicators}
                      technicalFailed={technicalIndicatorsFailed}
                      history={history}
                      historyFailed={historyFailed}
                      language={locale}
                      showAdminReadinessCue={showAdminReadinessCue}
                      symbol={data.ticker || primarySymbol}
                      localize={localize}
                    />
                  </StockWorkspaceSection>
                </div>

                <StockWorkspaceSection
                  eyebrow={locale === 'en' ? 'Workflow continuity' : '工作流连续性'}
                  title={locale === 'en' ? 'Research handoff' : '研究流转'}
                  testId="stock-workflow-continuity"
                  className="stock-workspace-section--workflow"
                >
                  <ResearchWorkspaceFlowPanel
                    language={locale}
                    current="stock-structure"
                    symbol={data.ticker || primarySymbol}
                    source="stock-structure"
                    title={locale === 'en' ? 'Beta research journey' : 'Beta 研究旅程'}
                    summary={locale === 'en'
                      ? 'Investigate this symbol, compare evidence, track only as a research record, then continue with validation surfaces.'
                      : '在这里研究单个标的，再对比证据；只有作为研究记录需要持续观察时才跟踪，并继续进入验证工作台。'}
                    knownEvidence={stockWorkflowKnownEvidence}
                    missingEvidence={stockWorkflowMissingEvidence}
                    stateNotes={stockWorkflowStateNotes}
                    nextSteps={stockWorkflowNextSteps}
                    testId="stock-research-workspace-flow"
                  />
                </StockWorkspaceSection>
              </div>
            ) : null}
          </ConsoleBoard>
        </ResearchConsoleShell>
      </ConsumerWorkspacePageShell>
    </ConsumerWorkspaceScope>
  );
}
