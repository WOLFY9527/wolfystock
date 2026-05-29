import type React from 'react';
import { lazy, Suspense, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { History, Lock, MoreHorizontal, Search, Star, Upload } from 'lucide-react';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { publicAnalysisApi } from '../api/publicAnalysis';
import { normalizeReportQuality } from '../api/reportNormalizer';
import { withFallback } from '../api/withFallback';
import {
  DeepReportDrawer,
  type SignalTone,
} from '../components/home-bento/DeepReportDrawer';
import type { HomeCandlestickChartContext } from '../components/home-bento/HomeCandlestickChart';
import {
  CompactFilterBar,
  FixedRegionGrid,
  MetricStrip,
} from '../components/linear/LinearPrimitives';
import { Button, ConfirmDialog, Drawer } from '../components/common';
import { useI18n } from '../contexts/UiLanguageContext';
import { useUiPreferences } from '../contexts/UiPreferencesContext';
import {
  getSafariReadySurfaceClassName,
  shouldApplySafariA11yGuard,
  useSafariRenderReady,
  useSafariWarmActivation,
} from '../hooks/useSafariInteractionReady';
import { useDashboardLifecycle } from '../hooks/useDashboardLifecycle';
import type { AnalysisReport, DataQualityReport, DecisionTrace, HistoryItem, ReportQuality, StandardReport, StandardReportField, TaskProgressModule } from '../types/analysis';
import type { PublicAnalysisPreviewResponse } from '../types/publicAnalysis';
import { purgeZombieDashboardStorage, useStockPoolStore } from '../stores';
import {
  buildInstitutionalReportMarkdown,
  getCompanyDisplayName,
  getCompanyWithTicker,
  normalizeCompanyNameCandidate,
  readObjectField,
} from '../utils/homeReportIdentity';
import { cn } from '../utils/cn';
import { getToneColor } from '../utils/marketColors';
import { createPublicAnalysisFallbackPreview } from '../utils/publicAnalysisFallback';
import { sanitizeUserFacingDataIssue } from '../utils/userFacingDataIssues';

type DrawerMetric = {
  label: string;
  value: string;
  details?: string;
  tone?: SignalTone;
  glow?: boolean;
};

type DrawerModule = {
  id: string;
  eyebrow: string;
  title: string;
  summary?: string;
  metrics: DrawerMetric[];
  footnote?: string;
};

type DrawerPayload = {
  title: string;
  modules: DrawerModule[];
};

type DashboardLocale = 'zh' | 'en';
type DetailDrawerKey = 'decision' | 'strategy' | 'tech' | 'fundamentals';
type PendingHistoryDelete =
  | { mode: 'single'; recordIds: number[] }
  | { mode: 'visible'; recordIds: number[] };

type HomeBentoDashboardPageProps = {
  isGuest?: boolean;
};

const LazyFullDecisionReportDrawer = lazy(() => import('../components/home-bento/FullDecisionReportDrawer'));
const LazyHomeCandlestickChart = lazy(() =>
  import('../components/home-bento/HomeCandlestickChart').then((module) => ({
    default: module.HomeCandlestickChart,
  })),
);
const DEFAULT_HOME_TICKER = 'ORCL';
const HOME_CHART_FALLBACK_TIMEFRAMES = ['1D', '1W', '1M'];
const HOME_CHART_FALLBACK_INDICATORS = ['MA5', 'MA10', 'MA20', 'MA60', 'VWAP'];
const HOME_CHART_FALLBACK_GRID_ROWS = ['price-top', 'price-upper', 'price-mid', 'volume'];
const HOME_CHART_IDLE_TIMEOUT_MS = 240;

const HISTORY_TIMESTAMP_FMT_EN = new Intl.DateTimeFormat('en-US', {
  timeZone: 'Asia/Shanghai',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});
const HISTORY_TIMESTAMP_FMT_ZH = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

function useDeferredHomeChartMount() {
  const [shouldRenderChart, setShouldRenderChart] = useState(false);

  useEffect(() => {
    let isCancelled = false;
    let idleHandle: number | null = null;
    let timeoutHandle: number | null = null;

    const revealChart = () => {
      if (!isCancelled) {
        setShouldRenderChart(true);
      }
    };

    if (typeof window.requestIdleCallback === 'function') {
      idleHandle = window.requestIdleCallback(revealChart, { timeout: HOME_CHART_IDLE_TIMEOUT_MS });
    } else {
      timeoutHandle = window.setTimeout(revealChart, 0);
    }

    return () => {
      isCancelled = true;
      if (idleHandle !== null && typeof window.cancelIdleCallback === 'function') {
        window.cancelIdleCallback(idleHandle);
      }
      if (timeoutHandle !== null) {
        window.clearTimeout(timeoutHandle);
      }
    };
  }, []);

  return shouldRenderChart;
}

function HomeCandlestickChartFallback({
  className,
  style,
  statusLabel,
}: {
  className?: string;
  style?: React.CSSProperties;
  statusLabel: string;
}) {
  return (
    <output
      className={cn(
        'block home-chart-well min-w-0 rounded-[14px] border border-[color:var(--wolfy-border-faint)] bg-[var(--wolfy-surface-inset)] px-3 py-2.5 shadow-[var(--wolfy-shadow-panel)]',
        className,
      )}
      style={style}
      data-testid="home-candlestick-chart-fallback"
      aria-live="polite"
      aria-atomic="true"
      aria-busy="true"
      aria-label={statusLabel}
    >
      <span className="sr-only">{statusLabel}</span>
      <div aria-hidden="true">
        <div className="mb-2.5 flex min-w-0 flex-col gap-2.5">
          <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <div className="flex items-center gap-0.5 rounded-full border border-[color:var(--wolfy-border-faint)] bg-white/[0.025] p-0.5">
                {HOME_CHART_FALLBACK_TIMEFRAMES.map((label, index) => (
                  <span
                    key={label}
                    className={cn(
                      'h-[22px] rounded-full px-2.5 py-1 text-[10px] font-medium',
                      index === 0 ? 'bg-[var(--wolfy-accent-soft)] text-transparent' : 'text-transparent',
                    )}
                  >
                    {label}
                  </span>
                ))}
              </div>
              <span className="hidden h-3 w-10 rounded-full bg-white/[0.04] sm:inline" />
            </div>
            <span className="h-3 w-24 rounded-full bg-white/[0.04]" />
          </div>
          <div className="flex min-w-0 flex-wrap items-center gap-1.5">
            {HOME_CHART_FALLBACK_INDICATORS.map((label) => (
              <span
                key={label}
                className="h-[24px] w-14 rounded-full border border-white/[0.05] bg-white/[0.012]"
              />
            ))}
          </div>
        </div>
        <div className="relative h-[216px] min-w-[280px] overflow-hidden rounded-[12px] border border-[color:var(--wolfy-border-faint)] bg-[linear-gradient(180deg,rgba(17,22,38,0.92),rgba(13,18,32,0.98))] sm:h-[228px] xl:h-[242px]">
          <div className="pointer-events-none absolute inset-x-4 top-6 h-px bg-gradient-to-r from-transparent via-white/14 to-transparent" />
          <div className="absolute inset-x-4 bottom-5 top-10 grid grid-rows-4 gap-4">
            {HOME_CHART_FALLBACK_GRID_ROWS.map((row) => (
              <span key={row} className="border-t border-white/[0.045]" />
            ))}
          </div>
        </div>
      </div>
    </output>
  );
}

function buildDecisionTraceFixtureReport(): AnalysisReport {
  return {
    meta: {
      queryId: 'fixture-analysis-trace-tem',
      stockCode: 'TEM',
      stockName: 'Tempus AI',
      companyName: 'Tempus AI',
      reportType: 'detailed',
      reportLanguage: 'zh',
      createdAt: '2026-05-04T09:00:00Z',
      reportGeneratedAt: '2026-05-04T09:00:00Z',
      currentPrice: 130.2,
      changePct: -0.4,
      modelUsed: 'fixture-model',
      isTest: true,
    },
    summary: {
      analysisSummary: 'Fixture result only; not investment advice. ORCL is waiting for a controlled pullback before any add.',
      operationAdvice: '等待回踩',
      trendPrediction: '短线震荡，等待量能确认。',
      sentimentScore: 58,
      sentimentLabel: 'Neutral',
    },
    strategy: {
      idealBuy: '128.50',
      secondaryBuy: '126.20',
      stopLoss: '121.00',
      takeProfit: '136.00-138.00',
    },
    details: {
      standardReport: {
        summaryPanel: {
          stock: 'Tempus AI',
          ticker: 'TEM',
          score: 3.6,
          currentPrice: '130.20',
          changePct: '-0.40%',
          operationAdvice: '等待回踩',
          trendPrediction: '短线震荡',
          oneSentence: 'Fixture result only; not investment advice.',
          tags: [
            { label: 'Fixture', value: 'Decision Trace' },
            { label: 'Mode', value: 'Hybrid' },
          ],
        },
        decisionContext: {
          shortTermView: 'Momentum is mixed while price holds above the stop band.',
          compositeView: 'Rule-stabilized wait/pullback state with incomplete fundamentals.',
          adjustmentReason: 'Fixture keeps deterministic browser smoke independent from live providers.',
        },
        decisionPanel: {
          setupType: 'Wait for pullback',
          confidence: '0.64',
          keyAction: 'wait_pullback',
          analysisPrice: 130.2,
          idealEntry: '128.50',
          idealEntryCenter: 128.5,
          backupEntry: '126.20',
          backupEntryCenter: 126.2,
          stopLoss: '121.00',
          stopLossLevel: 121,
          target: '136.00-138.00',
          targetZone: '136.00-138.00',
          buildStrategy: 'Use fixture data only to verify Home rendering and trace drawer behavior.',
          riskControlStrategy: 'Stop required if the fixture support band fails.',
          executionReminders: ['Do not treat fixture data as live analysis.'],
        },
        reasonLayer: {
          coreReasons: [
            'Rule-stabilized action for fixture verification.',
            'Fundamental data intentionally incomplete.',
          ],
          topRisk: 'Fixture warning: action and plan require position-context separation.',
          checklistSummary: 'Data source states include used, missing, and unknown.',
        },
        technicalFields: [
          { label: 'MA alignment', value: 'mixed', source: 'technical_rule' },
          { label: 'Risk control', value: 'stop required', source: 'rule' },
        ],
        fundamentalFields: [
          { label: 'Revenue Growth', value: 'N/A', status: 'missing' },
          { label: 'Free Cash Flow', value: '-', status: 'missing' },
        ],
        coverageNotes: {
          dataSources: ['quote: used', 'fundamental: missing', 'scanner: unknown'],
          coverageGaps: ['Fundamental data intentionally incomplete.'],
          conflictNotes: ['Fixture warning: action and plan require position-context separation.'],
          methodNotes: ['No live LLM/provider call is required for this fixture.'],
        },
      },
    },
    decisionTrace: {
      engineVersion: 'analysis_decision_trace_v1',
      mode: 'hybrid',
      endpoint: '/fixture/home-analysis-trace',
      taskId: 'fixture-analysis-trace-tem',
      symbol: 'TEM',
      market: 'US',
      generatedAt: '2026-05-04T09:00:00Z',
      decisionFields: {
        action: {
          value: 'wait_pullback',
          source: 'rule',
          confidence: 0.64,
          notes: 'Rule-stabilized action for fixture verification.',
        },
        score: {
          value: 5.8,
          source: 'rule',
          scale: '0-10',
        },
        confidence: {
          value: 0.64,
          source: 'blended',
        },
        entry: {
          value: 128.5,
          source: 'technical_rule',
        },
        target: {
          value: '136.00-138.00',
          source: 'llm',
        },
        stop: {
          value: 121.0,
          source: 'technical_rule',
        },
      },
      dataSources: [
        {
          name: 'quote',
          status: 'used',
          provider: 'fixture',
          notes: 'Fixture quote context.',
        },
        {
          name: 'fundamental',
          status: 'missing',
          provider: 'fixture',
          notes: 'Fundamental fields intentionally incomplete.',
        },
        {
          name: 'scanner',
          status: 'unknown',
          provider: 'fixture',
        },
      ],
      signals: [
        {
          name: 'MA alignment',
          value: 'mixed',
          impact: 'neutral',
          source: 'technical_rule',
        },
        {
          name: 'Risk control',
          value: 'stop required',
          impact: 'warning',
          source: 'rule',
        },
      ],
      llm: {
        used: true,
        provider: 'fixture-provider',
        model: 'fixture-model',
        template: 'stock_analysis_trace_fixture_v1',
        structuredOutput: true,
        schemaValidated: true,
        promptExposed: false,
      },
      conflicts: [
        {
          type: 'action_plan_mismatch',
          severity: 'warning',
          message: 'Fixture warning: action and plan require position-context separation.',
        },
      ],
      limitations: [
        'Fixture result only; not investment advice.',
        'Fundamental data intentionally incomplete.',
      ],
    },
  };
}

function formatTraceValue(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '--';
  }
  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No';
  }
  return String(value);
}

function TraceBadge({ children, tone = 'neutral' }: { children: React.ReactNode; tone?: 'neutral' | 'used' | 'warning' | 'missing' }) {
  const toneClass = tone === 'used'
    ? 'border-emerald-300/20 bg-emerald-300/10 text-emerald-100'
    : tone === 'warning'
      ? 'border-amber-300/20 bg-amber-300/10 text-amber-100'
      : tone === 'missing'
        ? 'border-rose-300/20 bg-rose-300/10 text-rose-100'
        : 'border-white/10 bg-white/[0.04] text-white/62';
  return (
    <span className={`inline-flex min-w-0 max-w-full items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] ${toneClass}`}>
      <span className="truncate">{children}</span>
    </span>
  );
}

function traceStatusTone(status?: string): 'neutral' | 'used' | 'warning' | 'missing' {
  const normalized = String(status || '').toLowerCase();
  if (normalized === 'used') {
    return 'used';
  }
  if (normalized === 'fallback' || normalized === 'stale') {
    return 'warning';
  }
  if (normalized === 'missing') {
    return 'missing';
  }
  return 'neutral';
}

function traceStatusLabel(status?: string | null): string {
  const normalized = String(status || '').trim().toLowerCase();
  if (normalized === 'used' || normalized === 'available') return '可用';
  if (normalized === 'fallback') return '备用';
  if (normalized === 'stale') return '陈旧';
  if (normalized === 'missing') return '缺失';
  if (normalized === 'partial') return '部分可用';
  if (normalized === 'error') return '异常';
  if (normalized === 'unknown' || !normalized) return '未知';
  return status || '未知';
}

function traceSourceLabel(source?: string | null, locale: DashboardLocale = 'zh'): string {
  const normalized = String(source || '').trim().toLowerCase();
  if (locale === 'en') {
    if (normalized === 'llm') return 'AI summary';
    if (normalized === 'rule' || normalized === 'technical_rule') return 'System basis';
    if (normalized === 'frontend') return 'Workspace';
    if (normalized === 'blended') return 'Blended';
    if (normalized === 'fallback') return 'Fallback';
    return normalized ? 'Data basis' : 'Unknown';
  }
  if (normalized === 'llm') return 'AI 整理';
  if (normalized === 'rule' || normalized === 'technical_rule') return '系统依据';
  if (normalized === 'frontend') return '前端';
  if (normalized === 'blended') return '综合';
  if (normalized === 'fallback') return '备用';
  if (normalized === 'unknown' || !normalized) return '未知';
  return '数据依据';
}

function traceFieldLabel(name: string, locale: DashboardLocale): string {
  if (locale === 'en') {
    return name;
  }
  const labels: Record<string, string> = {
    action: '分析状态',
    score: '评分',
    confidence: '置信度',
    entry: '观察区',
    target: '上方观察',
    stop: '风险线',
  };
  return labels[name.trim().toLowerCase()] || name;
}

function traceDataSourceLabel(name?: string | null, locale: DashboardLocale = 'zh'): string {
  const value = String(name || '').trim();
  if (locale === 'en') {
    return value || 'source';
  }
  const labels: Record<string, string> = {
    market: '行情',
    fundamentals: '基本面',
    fundamental: '基本面',
    news: '新闻',
    sentiment: '情绪',
    technical: '技术面',
    quote: '报价',
  };
  return labels[value.toLowerCase()] || value || '数据源';
}

function userFacingDataSourceLabel(name?: string | null, locale: DashboardLocale = 'zh'): string {
  const value = String(name || '').trim();
  const normalized = value.toLowerCase();
  const isEnglish = locale === 'en';
  if (!normalized) {
    return isEnglish ? 'Unconfirmed data' : '待确认数据';
  }
  if (normalized.includes('quote') || normalized.includes('market') || normalized.includes('price') || normalized.includes('行情')) {
    return isEnglish ? 'Quote data' : '行情数据';
  }
  if (normalized.includes('candle') || normalized.includes('technical') || normalized.includes('indicator') || normalized.includes('技术')) {
    return isEnglish ? 'Technical data' : '技术数据';
  }
  if (normalized.includes('fundamental') || normalized.includes('financial') || normalized.includes('eps') || normalized.includes('fmp') || normalized.includes('基本面')) {
    return isEnglish ? 'Fundamental data' : '基本面数据';
  }
  if (normalized.includes('earnings') || normalized.includes('财报')) {
    return isEnglish ? 'Earnings data' : '财报数据';
  }
  if (normalized.includes('news') || normalized.includes('gnews') || normalized.includes('headline') || normalized.includes('新闻')) {
    return isEnglish ? 'News data' : '新闻数据';
  }
  if (normalized.includes('sentiment') || normalized.includes('情绪')) {
    return isEnglish ? 'Sentiment data' : '情绪数据';
  }
  return traceDataSourceLabel(value, locale);
}

function localizeTraceMessage(value: string | undefined, type: string | undefined, locale: DashboardLocale): string {
  const text = String(value || '').trim();
  if (locale === 'en') {
    return text || type || 'trace warning';
  }
  const normalizedType = String(type || '').toLowerCase();
  if (normalizedType === 'action_plan_mismatch') {
    return '分析状态与后续计划存在不一致，已在决策来源中标注。';
  }
  if (!text) {
    return '决策链路存在需要复核的提示。';
  }
  return containsCjk(text) ? text : '决策链路存在需要复核的提示。';
}

function localizeTraceLimitation(value: string, locale: DashboardLocale): string {
  const text = String(value || '').trim();
  if (locale === 'en' || containsCjk(text)) {
    return text;
  }
  if (/fundamental.*partial/i.test(text)) {
    return '基本面数据缺失';
  }
  if (/fundamental.*incomplete/i.test(text)) {
    return '基本面数据缺失';
  }
  if (/not investment advice/i.test(text)) {
    return 'AI 洞察仅供参考，不构成投资建议。';
  }
  return '存在数据覆盖限制';
}

function localizeTraceNote(value: string | null | undefined, locale: DashboardLocale): string {
  const text = String(value || '').trim();
  if (!text || locale === 'en' || containsCjk(text)) {
    return text;
  }
  if (/score/i.test(text)) {
    return '评分路径已稳定';
  }
  if (/rule/i.test(text)) {
    return '规则层已参与校验';
  }
  return '已记录来源说明';
}

function safeReportValue(value: unknown): string {
  const text = String(value ?? '').trim();
  return text && text !== '-' && !/^n\/?a$/i.test(text) ? text : '--';
}

function fieldValue(fields: StandardReportField[] | undefined, aliases: string[]): string {
  const field = findStandardField(fields, aliases);
  return field ? safeReportValue(field.value) : '';
}

function reportQualityFallback(): ReportQuality {
  return {
    level: 'unknown',
    schemaStatus: 'unknown',
    traceStatus: 'unknown',
    summaryStatus: 'missing',
    reportStatus: 'missing',
    hasDecisionTrace: false,
    hasStandardReport: false,
    hasAnalysisResult: false,
    hasAction: false,
    hasScore: false,
    hasConfidence: false,
    hasTradingPlan: false,
    missingFields: [],
    userLabel: '状态未知',
    userHint: '暂未确认报告完整性。',
  };
}

function getReportQuality(report: AnalysisReport | null | undefined): ReportQuality {
  if (!report) {
    return reportQualityFallback();
  }
  return report.reportQuality || normalizeReportQuality(report);
}

function reportQualityUserLabel(label: string | undefined, locale: DashboardLocale = 'zh'): string {
  const normalized = String(label || '').trim();
  if (locale === 'en') {
    if (normalized === '完整') return 'Data: complete';
    if (normalized === '可用') return 'Data: usable';
    if (normalized === '旧版记录') return 'Data: legacy';
    if (normalized === '分析失败') return 'Data: failed';
    return 'Data: pending';
  }
  if (normalized === '完整') return '数据：完整';
  if (normalized === '可用') return '数据：可用';
  if (normalized === '旧版记录') return '数据：旧版';
  if (normalized === '分析失败') return '数据：失败';
  return '数据：待确认';
}

function traceQualityLabel(status: ReportQuality['traceStatus'], locale: DashboardLocale = 'zh'): string {
  if (locale === 'en') {
    if (status === 'present') return 'Source: attached';
    if (status === 'partial') return 'Source: partial';
    if (status === 'missing') return 'Source: missing';
    return 'Source: pending';
  }
  if (status === 'present') return '来源：已附';
  if (status === 'partial') return '来源：部分';
  if (status === 'missing') return '来源：缺失';
  return '来源：待确认';
}

function schemaQualityLabel(status: ReportQuality['schemaStatus'], locale: DashboardLocale = 'zh'): string {
  if (locale === 'en') {
    if (status === 'ok') return 'Structure: ready';
    if (status === 'unconfirmed') return 'Structure: review';
    if (status === 'missing') return 'Structure: missing';
    return 'Structure: review';
  }
  if (status === 'ok') return '结构：完整';
  if (status === 'unconfirmed') return '结构：待复核';
  if (status === 'missing') return '结构：缺失';
  return '结构：待复核';
}

function summaryQualityLabel(status: ReportQuality['summaryStatus'], locale: DashboardLocale = 'zh'): string {
  if (locale === 'en') {
    if (status === 'complete') return 'Summary: ready';
    if (status === 'partial') return 'Summary: partial';
    return 'Summary: missing';
  }
  if (status === 'complete') return '摘要：完整';
  if (status === 'partial') return '摘要：部分';
  return '摘要：缺失';
}

function reportQualityLabel(status: ReportQuality['reportStatus'], locale: DashboardLocale = 'zh'): string {
  if (locale === 'en') {
    if (status === 'complete') return 'Report: ready';
    if (status === 'partial') return 'Report: partial';
    return 'Report: missing';
  }
  if (status === 'complete') return '报告：完整';
  if (status === 'partial') return '报告：部分';
  return '报告：缺失';
}

function qualityChipTone(label: string): 'neutral' | 'used' | 'warning' | 'missing' {
  if (/(完整|充分|稳定|无冲突|complete|ready|stable|clear|attached)/.test(label) && !/(部分|待确认|待复核|partial|review|pending)/.test(label)) {
    return 'used';
  }
  if (/(缺失|失败|不足|missing|failed|limited)/.test(label)) {
    return 'missing';
  }
  if (/(部分|旧版|未确认|未知|复核|待整理|partial|legacy|unknown|review|pending)/.test(label)) {
    return 'warning';
  }
  return 'neutral';
}

function ReportQualityChip({ label }: { label: string }) {
  return <TraceBadge tone={qualityChipTone(label)}>{label}</TraceBadge>;
}

function buildQualityStatusSummary(quality: ReportQuality, locale: DashboardLocale): string {
  return [
    reportQualityUserLabel(quality.userLabel, locale),
    traceQualityLabel(quality.traceStatus, locale),
    schemaQualityLabel(quality.schemaStatus, locale),
    summaryQualityLabel(quality.summaryStatus, locale),
  ].join(' · ');
}

function buildTraceSummary(trace: DecisionTrace | undefined, quality: ReportQuality | undefined, locale: DashboardLocale): string {
  const isEnglish = locale === 'en';
  const qualitySummary = quality ? buildQualityStatusSummary(quality, locale) : '';
  if (!trace) {
    return qualitySummary || (isEnglish ? 'Source: unavailable' : '来源：未附');
  }
  const provenance = Array.from(new Set(
    (trace.dataSources || []).reduce<string[]>((acc, source) => {
      if (!['missing', 'unknown'].includes(String(source.status || '').trim().toLowerCase())) {
        const label = traceDataSourceLabel(source.name, locale);
        if (label) acc.push(label);
      }
      return acc;
    }, []),
  )).slice(0, 4);
  const sourceCount = trace.dataSources?.length || 0;
  const usedCount = (trace.dataSources || []).filter((source) => String(source.status || '').toLowerCase() === 'used').length;
  const conflictCount = trace.conflicts?.length || 0;
  const sourceLabel = provenance.length
    ? `${isEnglish ? 'Source' : '来源'}：${provenance.join(' / ')}`
    : traceQualityLabel(quality?.traceStatus || 'unknown', locale);
  const dataLabel = sourceCount === 0
    ? (isEnglish ? 'Coverage: pending' : '覆盖：待确认')
    : usedCount === 0
      ? (isEnglish ? 'Coverage: limited' : '覆盖：不足')
      : usedCount < sourceCount
        ? (isEnglish ? 'Coverage: partial' : '覆盖：部分')
        : (isEnglish ? 'Coverage: complete' : '覆盖：完整');
  const conflictLabel = conflictCount > 0
    ? (isEnglish ? 'Evidence: review' : '证据：待复核')
    : null;
  const schemaLabel = trace.llm?.schemaValidated ? null : schemaQualityLabel('unconfirmed', locale);
  return [
    sourceLabel,
    dataLabel,
    conflictLabel,
    schemaLabel,
  ].filter(Boolean).join(' · ');
}

function DecisionTracePanel({
  trace,
  locale,
  quality,
  dataQualityReport,
  sourceSummary,
}: {
  trace?: DecisionTrace;
  locale: DashboardLocale;
  quality?: ReportQuality;
  dataQualityReport?: DataQualityReport;
  sourceSummary?: string;
}) {
  if (!trace) {
    return (
      <div className="min-w-0 space-y-3" data-testid="home-bento-decision-trace-panel">
        <div className="min-w-0 rounded-2xl border border-white/8 bg-white/[0.025] p-4 text-sm text-white/56">
          当前分析未包含决策溯源
        </div>
        <DecisionSourceDetailsPanel report={dataQualityReport} locale={locale} trace={trace} sourceSummary={sourceSummary} />
        {quality ? (
          <div
            className="rounded-2xl border border-amber-300/15 bg-amber-300/8 p-4 text-sm text-amber-50/80"
            data-testid="home-bento-decision-trace-data-note"
          >
            {quality.missingFields.length
              ? quality.missingFields.map((item) => sanitizeUserFacingDataIssue(item, locale)).join('、')
              : '数据：不足'}
          </div>
        ) : null}
      </div>
    );
  }

  const decisionFields = Object.entries(trace.decisionFields || {});
  const dataSources = trace.dataSources || [];
  const conflicts = trace.conflicts || [];
  const limitations = trace.limitations || [];
  const sectionTitleClass = 'text-[11px] font-semibold tracking-[0] text-white/70';
  const isEnglish = locale === 'en';

  return (
    <div className="flex min-w-0 flex-col gap-4" data-testid="home-bento-decision-trace-panel">
      <DecisionSourceDetailsPanel report={dataQualityReport} locale={locale} trace={trace} sourceSummary={sourceSummary} />
      <div className="rounded-2xl border border-white/8 bg-white/[0.025] p-4">
        <p className={sectionTitleClass}>{isEnglish ? 'Decision Fields' : '决策字段'}</p>
        <div className="mt-3 grid min-w-0 grid-cols-1 gap-2 sm:grid-cols-2">
          {decisionFields.map(([name, field]) => (
            <div key={name} className="min-w-0 rounded-xl border border-white/6 bg-[rgba(10,16,28,0.28)] px-3 py-2">
              <div className="flex min-w-0 items-center justify-between gap-2">
                <span className="truncate text-xs font-semibold text-white/72">{traceFieldLabel(name, locale)}</span>
                <TraceBadge>{traceSourceLabel(field.source, locale)}</TraceBadge>
              </div>
              <p className="mt-1 break-words text-sm text-white">{formatTraceValue(field.value)}</p>
              {field.notes ? <p className="mt-1 line-clamp-2 text-xs text-white/42">{localizeTraceNote(field.notes, locale)}</p> : null}
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-2xl border border-white/8 bg-white/[0.025] p-4">
        <p className={sectionTitleClass}>{isEnglish ? 'Data Used' : '使用的数据'}</p>
        <div className="mt-3 flex min-w-0 flex-col gap-2">
          {dataSources.length ? dataSources.map((source, index) => (
            <div key={`${source.name}-${index}`} className="flex min-w-0 flex-wrap items-center justify-between gap-2 rounded-xl border border-white/6 bg-[rgba(10,16,28,0.28)] px-3 py-2">
              <span className="truncate text-xs font-semibold text-white/72">{traceDataSourceLabel(source.name, locale)}</span>
              <div className="flex min-w-0 flex-wrap justify-end gap-2">
                <TraceBadge tone={traceStatusTone(source.status)}>{traceStatusLabel(source.status)}</TraceBadge>
              </div>
            </div>
          )) : <p className="text-sm text-white/48">{isEnglish ? 'No source metadata available.' : '暂无数据源元信息。'}</p>}
        </div>
      </div>

      <div className="rounded-2xl border border-white/8 bg-white/[0.025] p-4">
        <p className={sectionTitleClass}>{isEnglish ? 'Conflicts & Limitations' : '冲突与限制'}</p>
        <div className="mt-3 flex flex-col gap-2 text-sm text-white/66">
          {conflicts.length ? conflicts.map((conflict, index) => (
            <div key={`${conflict.type}-${index}`} className="rounded-xl border border-amber-300/15 bg-amber-300/8 px-3 py-2 text-amber-50/86">
              {localizeTraceMessage(conflict.message, conflict.type, locale)}
            </div>
          )) : <p>{locale === 'en' ? 'No obvious conflicts detected.' : '未检测到明显冲突'}</p>}
          {limitations.map((item) => (
            <p key={item} className="text-white/46">{localizeTraceLimitation(item, locale)}</p>
          ))}
        </div>
      </div>
    </div>
  );
}

function getDataQualityReport(report: AnalysisReport | null): DataQualityReport | undefined {
  if (!report) return undefined;
  return report.dataQualityReport
    || report.details?.dataQualityReport
    || report.meta.dataQualityReport
    || (readObjectField(report, ['details', 'analysisResult', 'dataQualityReport']) as DataQualityReport | undefined);
}

function dataQualityTierLabel(tier: string | undefined, locale: DashboardLocale): string {
  const normalized = String(tier || '').trim();
  const zh: Record<string, string> = {
    decision_grade: '决策级',
    analysis_grade: '分析级',
    partial: '部分数据',
    insufficient: '数据不足',
  };
  const en: Record<string, string> = {
    decision_grade: 'Decision grade',
    analysis_grade: 'Analysis grade',
    partial: 'Partial data',
    insufficient: 'Insufficient',
  };
  return (locale === 'en' ? en : zh)[normalized] || (locale === 'en' ? 'Unknown' : '未确认');
}

function summarizeEnrichmentGaps(report: DataQualityReport): string[] {
  const sources = [
    ...(report.pendingSources || []),
    ...(report.failedSources || []),
    ...(report.skippedSources || []),
  ].filter(Boolean);
  return Array.from(new Set(sources)).slice(0, 5);
}

function compactDataIssueLabel(label: string, locale: DashboardLocale): string {
  if (locale === 'en') {
    if (label === 'Data insufficient, observe only') return 'Data: limited';
    return label;
  }
  if (label === '数据不足，结论仅供观察') return '覆盖不足';
  return label;
}

function dataQualityFieldLabel(value: string, locale: DashboardLocale): string {
  const normalized = String(value || '').trim().toLowerCase();
  if (!normalized) return locale === 'en' ? 'Unconfirmed data gap' : '数据缺口未确认';
  return compactDataIssueLabel(sanitizeUserFacingDataIssue(normalized, locale), locale);
}

function dataQualityReasonLabel(value: string, locale: DashboardLocale): string {
  const normalized = String(value || '').trim().toLowerCase();
  if (!normalized) return locale === 'en' ? 'Reason unconfirmed' : '原因未确认';
  return compactDataIssueLabel(sanitizeUserFacingDataIssue(normalized, locale), locale);
}

function summarizeEnrichmentReasons(report: DataQualityReport): string[] {
  const reasonMap = report.enrichmentReasons || {};
  const reasons = Object.values(reasonMap).flat().filter(Boolean);
  return Array.from(new Set(reasons)).slice(0, 5);
}

function hasDataQualityGaps(report: DataQualityReport): boolean {
  return report.requiredAvailable === false
    || Boolean(report.importantMissing?.length)
    || Boolean(report.optionalMissing?.length)
    || Boolean(report.providerTimeouts?.length)
    || Boolean(report.providerCooldowns?.length)
    || report.dataQualityTier === 'partial'
    || report.dataQualityTier === 'analysis_grade';
}

function dataQualityChipTone(report: DataQualityReport): 'used' | 'warning' | 'missing' {
  if (report.requiredAvailable === false || report.dataQualityTier === 'insufficient') {
    return 'missing';
  }
  return hasDataQualityGaps(report) ? 'warning' : 'used';
}

function buildDataQualityPreview(report: DataQualityReport, locale: DashboardLocale): string {
  const isEnglish = locale === 'en';
  if (report.requiredAvailable === false) {
    return isEnglish ? 'Critical market data missing' : '关键行情数据缺失';
  }
  if (report.importantMissing?.length) {
    return `${isEnglish ? 'Critical gap' : '关键缺口'}：${report.importantMissing.slice(0, 2).map((item) => dataQualityFieldLabel(item, locale)).join('、')}`;
  }
  if (report.providerTimeouts?.length || report.providerCooldowns?.length) {
    return isEnglish ? 'External feeds temporarily degraded' : '外部数据源暂时降级';
  }
  if (report.optionalMissing?.length || report.pendingSources?.length || report.failedSources?.length || report.skippedSources?.length) {
    return isEnglish ? 'Optional enrichment still incomplete' : '可选增强仍未补齐';
  }
  return isEnglish ? 'Coverage stable' : '覆盖稳定';
}

function uniqueCompactLabels(values: Array<string | undefined | null>, limit = 4): string[] {
  return Array.from(new Set(values.flatMap((item) => { const v = String(item || '').trim(); return v ? [v] : []; }))).slice(0, limit);
}

function buildAvailableDataCopy(report: DataQualityReport | undefined, trace: DecisionTrace | undefined, locale: DashboardLocale): string {
  const isEnglish = locale === 'en';
  const traceSources = (trace?.dataSources || []).reduce<string[]>((acc, item) => {
    if (['used', 'fallback'].includes(String(item.status || '').trim().toLowerCase())) {
      const label = userFacingDataSourceLabel(item.name, locale);
      acc.push(String(item.status || '').trim().toLowerCase() === 'fallback'
        ? (isEnglish ? `${label} fallback` : `${label}（备用数据）`)
        : label);
    }
    return acc;
  }, []);
  const completedSources = (report?.completedSources || []).map((item) => userFacingDataSourceLabel(item, locale));
  const available = uniqueCompactLabels([...traceSources, ...completedSources], 4);
  return available.length ? available.join(isEnglish ? ' / ' : '、') : (isEnglish ? 'No confirmed source yet' : '暂无已确认可用数据');
}

function buildMissingDataCopy(report: DataQualityReport | undefined, locale: DashboardLocale): string {
  const isEnglish = locale === 'en';
  if (!report) {
    return isEnglish ? 'Quality report unavailable' : '暂无结构化质量报告';
  }
  const rawGaps = [
    ...(report.importantMissing || []),
    ...(report.optionalMissing || []),
    ...(report.pendingSources || []),
    ...(report.failedSources || []),
    ...(report.skippedSources || []),
    ...(report.providerTimeouts || []),
    ...(report.providerCooldowns || []),
  ];
  const gaps = uniqueCompactLabels(rawGaps.map((item) => dataQualityFieldLabel(item, locale)), 4);
  return gaps.length ? gaps.join(isEnglish ? ' / ' : '、') : (isEnglish ? 'No prominent gap' : '暂无突出缺口');
}

function hasPositiveTechnicalEvidence(dashboard: DashboardPayload): boolean {
  return dashboard.decision.signalTone === 'bullish'
    || dashboard.tech.signals.some((signal) => {
      const text = `${signal.label} ${signal.value} ${signal.details || ''}`;
      return signal.tone === 'bullish' || /偏强|多头|上方|突破|扩张|金叉|bull|above|constructive|strong|expand/i.test(text);
    });
}

function buildDataQualityImpactCopy(
  report: DataQualityReport | undefined,
  dashboard: DashboardPayload,
  locale: DashboardLocale,
): string {
  const isEnglish = locale === 'en';
  const positiveTechnical = hasPositiveTechnicalEvidence(dashboard);
  if (!report) {
    return isEnglish
      ? 'Quality evidence is not structured, so the view stays observation-only.'
      : '缺少结构化质量报告，当前结论保持仅观察。';
  }
  if (report.requiredAvailable === false) {
    return isEnglish
      ? 'Key quote or candle evidence is missing; keep the conclusion observation-only.'
      : '关键行情或 K 线缺失，当前结论只能保持仅观察。';
  }
  if (hasDataQualityGaps(report)) {
    return positiveTechnical
      ? (isEnglish
        ? 'Technical evidence is constructive, but incomplete coverage prevents an action conclusion.'
        : '技术证据偏强，但覆盖不完整，不能升格为行动结论。')
      : (isEnglish
        ? 'Coverage is incomplete, so the conclusion remains bounded.'
        : '覆盖仍不完整，结论需要保持受限。');
  }
  return isEnglish
    ? 'Coverage is usable; still verify with follow-up evidence.'
    : '覆盖可用，仍需用后续证据复核。';
}

function buildResearchFrameworkRows(
  locale: DashboardLocale,
  dashboard: DashboardPayload,
  dataQualityReport: DataQualityReport | undefined,
): Array<{ label: string; value: string; tone?: SignalTone }> {
  const isEnglish = locale === 'en';
  const positiveTechnical = hasPositiveTechnicalEvidence(dashboard);
  const hasGaps = dataQualityReport ? hasDataQualityGaps(dataQualityReport) : true;
  const stanceLabel = resolveLinearStanceLabel(locale, dashboard.decision.signalLabel, dashboard.decision.signalTone);
  const supportSignals = uniqueCompactLabels(
    dashboard.tech.signals.reduce<string[]>((acc, signal) => {
      if (signal.tone === 'bullish' || /偏强|多头|上方|突破|扩张|bull|above|constructive|strong|expand/i.test(`${signal.label} ${signal.value} ${signal.details || ''}`)) {
        acc.push(signal.label);
      }
      return acc;
    }, []),
    2,
  );
  const missingCopy = buildMissingDataCopy(dataQualityReport, locale);
  const hasMissingCopy = !/(暂无突出缺口|No prominent gap)/i.test(missingCopy);

  return [
    {
      label: isEnglish ? 'Current conclusion' : '当前结论',
      value: isEnglish
        ? positiveTechnical && hasGaps
          ? `${stanceLabel}: technical evidence is constructive, but incomplete evidence keeps this observation-only.`
          : `${stanceLabel}: keep the conclusion bounded by the available evidence.`
        : positiveTechnical && hasGaps
          ? `${stanceLabel}：技术证据偏强，但新闻/基本面覆盖不完整，不能升格为行动结论。`
          : `${stanceLabel}：当前只表达研究观察，仍需后续证据复核。`,
    },
    {
      label: isEnglish ? 'Support' : '支持因素',
      value: supportSignals.length
        ? (isEnglish ? `${supportSignals.join(' / ')} support the technical view.` : `${supportSignals.join('、')}提供正向技术证据。`)
        : (isEnglish ? 'No strong support factor is confirmed yet.' : '暂未形成稳定支撑因素。'),
      tone: positiveTechnical ? 'bullish' : 'neutral',
    },
    {
      label: isEnglish ? 'Limits' : '限制因素',
      value: hasMissingCopy
        ? (isEnglish ? `${missingCopy}; conclusion remains constrained.` : `${missingCopy}，结论仍受证据覆盖限制。`)
        : (isEnglish ? 'No prominent missing field, but follow-up evidence is still needed.' : '暂无突出缺口，但仍需后续证据复核。'),
    },
    {
      label: isEnglish ? 'Next confirmation' : '下一步确认',
      value: hasMissingCopy
        ? (isEnglish ? 'Confirm the missing data before upgrading the thesis.' : '先补齐缺失数据，再复核技术偏强是否延续。')
        : (isEnglish ? 'Track the next candle and event evidence.' : '跟踪下一根 K 线与事件证据。'),
    },
  ];
}

function resolveJudgmentGateCopy(
  locale: DashboardLocale,
  dashboard: DashboardPayload,
  dataQualityReport: DataQualityReport | undefined,
): string {
  const isEnglish = locale === 'en';
  if (!dataQualityReport || dataQualityReport.requiredAvailable === false || dataQualityReport.dataQualityTier === 'insufficient') {
    return isEnglish ? 'Evidence insufficient' : '证据不足';
  }
  if (hasDataQualityGaps(dataQualityReport)) {
    return isEnglish ? 'Research judgment, evidence-limited' : '可以形成研究判断，但证据受限';
  }
  if (dashboard.decision.signalTone === 'neutral') {
    return isEnglish ? 'Observe only' : '仅观察';
  }
  return isEnglish ? 'Research judgment available' : '可以形成研究判断';
}

function buildSupportFactorCopy(locale: DashboardLocale, dashboard: DashboardPayload): string {
  const isEnglish = locale === 'en';
  const supportSignals = uniqueCompactLabels(
    dashboard.tech.signals.reduce<string[]>((acc, signal) => {
      if (signal.tone === 'bullish' || /偏强|多头|上方|突破|扩张|bull|above|constructive|strong|expand/i.test(`${signal.label} ${signal.value} ${signal.details || ''}`)) {
        acc.push(signal.label);
      }
      return acc;
    }, []),
    3,
  );
  if (supportSignals.length) {
    return isEnglish
      ? `${supportSignals.join(' / ')} support the technical evidence.`
      : `${supportSignals.join('、')}提供关键支撑证据。`;
  }
  return isEnglish ? 'No stable support factor is confirmed yet.' : '暂未形成稳定支撑因素。';
}

function HomeConclusionFirstConsole({
  locale,
  dashboard,
  dataQualityReport,
  decisionTrace,
  sourceSummary,
  stanceLabel,
  thesisCopy,
  confidenceVisual,
}: {
  locale: DashboardLocale;
  dashboard: DashboardPayload;
  dataQualityReport?: DataQualityReport;
  decisionTrace?: DecisionTrace;
  sourceSummary?: string;
  stanceLabel: string;
  thesisCopy: string;
  confidenceVisual: ReturnType<typeof resolveConfidenceVisual>;
}) {
  const isEnglish = locale === 'en';
  const frameworkRows = buildResearchFrameworkRows(locale, dashboard, dataQualityReport);
  const currentConclusion = frameworkRows[0]?.value || thesisCopy;
  const supportCopy = buildSupportFactorCopy(locale, dashboard);
  const riskCopy = frameworkRows[2]?.value || buildDataQualityImpactCopy(dataQualityReport, dashboard, locale);
  const nextCopy = frameworkRows[3]?.value || (isEnglish ? 'Track follow-up evidence.' : '继续跟踪后续证据。');
  const qualityPreview = dataQualityReport
    ? buildDataQualityPreview(dataQualityReport, locale)
    : sourceSummary || (isEnglish ? 'Data quality not yet confirmed.' : '数据质量仍待确认。');
  const availableCopy = buildAvailableDataCopy(dataQualityReport, decisionTrace, locale);
  const missingCopy = buildMissingDataCopy(dataQualityReport, locale);
  const qualityImpactCopy = buildDataQualityImpactCopy(dataQualityReport, dashboard, locale);
  const judgmentGateCopy = resolveJudgmentGateCopy(locale, dashboard, dataQualityReport);
  const dataQualityLabel = dataQualityReport
    ? dataQualityTierLabel(dataQualityReport.dataQualityTier, locale)
    : (isEnglish ? 'Unconfirmed' : '未确认');
  const scoreDisplayValue = displaySlotValue(
    dashboard.decision.heroValue,
    locale,
    isEnglish ? 'Pending' : '待补充数据',
  );
  const confidenceTone: 'neutral' | 'used' | 'warning' | 'missing' = dataQualityReport
    ? dataQualityChipTone(dataQualityReport)
    : 'neutral';

  return (
    <section
      className="home-research-conclusion-console min-w-0 overflow-hidden rounded-[8px] border border-[color:var(--wolfy-divider)] bg-[linear-gradient(135deg,rgba(16,24,38,0.96),rgba(18,28,42,0.88)_48%,rgba(34,38,38,0.92))]"
      data-testid="home-research-conclusion-console"
      data-first-screen-priority="conclusion-first"
      data-visual-role="conclusion-research-console"
    >
      <div className="min-w-0 p-5 md:px-6">
        <div
          className="mb-4 flex min-w-0 flex-wrap items-center gap-2"
          data-testid="home-research-judgment-gate"
        >
          <TraceBadge tone={dataQualityReport ? dataQualityChipTone(dataQualityReport) : 'neutral'}>
            {judgmentGateCopy}
          </TraceBadge>
          <TraceBadge tone="neutral">
            {isEnglish ? 'State' : '状态'}
            {' · '}
            {stanceLabel}
          </TraceBadge>
          <TraceBadge tone={confidenceTone}>
            {isEnglish ? 'Confidence' : '可信度'}
            {' · '}
            {confidenceVisual.label}
          </TraceBadge>
        </div>

        <div className="min-w-0" data-testid="home-research-current-conclusion">
          <p className="text-[12px] font-semibold tracking-[0] text-white/52">
            {isEnglish ? 'Current conclusion' : '当前结论'}
          </p>
          <div className="mt-2 flex min-w-0 flex-col gap-2" data-testid="home-bento-decision-action">
            <p
              className="text-white text-[34px] font-semibold leading-none tracking-[0] md:text-[42px]"
              data-testid="home-bento-decision-signal-hero"
            >
              {stanceLabel}
            </p>
            <p className="max-w-[64rem] min-w-0 break-words text-sm leading-6 text-white/68">
              {currentConclusion}
            </p>
          </div>
          <div className="mt-3" data-testid="home-bento-decision-insight">
            <span className="sr-only">{isEnglish ? 'Research thesis' : '研究结论依据'}</span>
            <p className="max-w-[72rem] min-w-0 break-words text-[13px] leading-[1.65] text-white/66 whitespace-normal" data-testid="home-bento-decision-insight-copy">
              {thesisCopy}
            </p>
          </div>
        </div>

        <div className="mt-5 grid min-w-0 gap-0 overflow-hidden rounded-[8px] border border-white/[0.07] md:grid-cols-3">
          <div className="min-w-0 border-b border-white/[0.07] px-4 py-3 md:border-b-0 md:border-r" data-testid="home-research-support-factors">
            <p className="text-[11px] font-semibold tracking-[0] text-white/42">{isEnglish ? 'Key support factors' : '关键支撑因素'}</p>
            <p className="mt-2 break-words text-xs font-semibold leading-[1.55] text-white/76">{supportCopy}</p>
          </div>
          <div className="min-w-0 border-b border-white/[0.07] px-4 py-3 md:border-b-0 md:border-r" data-testid="home-research-risk-boundaries">
            <p className="text-[11px] font-semibold tracking-[0] text-white/42">{isEnglish ? 'Main risks / invalidation' : '主要风险 / 失效条件'}</p>
            <p className="mt-2 break-words text-xs font-semibold leading-[1.55] text-white/76">{riskCopy}</p>
          </div>
          <div className="min-w-0 px-4 py-3" data-testid="home-research-next-actions">
            <p className="text-[11px] font-semibold tracking-[0] text-white/42">{isEnglish ? 'Next watch point' : '下一步关注点'}</p>
            <p className="mt-2 break-words text-xs font-semibold leading-[1.55] text-white/76">{nextCopy}</p>
          </div>
        </div>

        <MetricStrip
          className="mt-3 overflow-hidden rounded-[10px] border border-white/[0.07] bg-white/[0.02] sm:grid-cols-3"
          items={[
            {
              key: 'score',
              label: isEnglish ? 'Research score' : '研究评分',
              value: scoreDisplayValue,
              testId: 'home-research-score-strip',
            },
            {
              key: 'confidence',
              label: isEnglish ? 'Confidence' : '可信度',
              value: confidenceVisual.label,
              testId: 'home-research-confidence-strip',
            },
            {
              key: 'data-state',
              label: isEnglish ? 'Data state' : '数据状态',
              value: dataQualityLabel,
              testId: 'home-research-data-state-strip',
            },
          ]}
        />

        <details
          className="group mt-4 min-w-0 rounded-[10px] border border-white/[0.06] bg-white/[0.015] px-3 py-2.5"
          data-testid="home-research-trust-strip"
        >
          <summary
            className="flex cursor-pointer list-none items-center justify-between gap-3 text-[11px] font-medium text-white/58 marker:hidden"
            data-testid="home-research-boundary-disclosure"
          >
            <span>{isEnglish ? 'View research boundary' : '查看研究边界'}</span>
            <span className="text-white/28 transition-transform group-open:rotate-180">{isEnglish ? '▾' : '▾'}</span>
          </summary>
          <div className="mt-2.5 divide-y divide-white/[0.06] border-t border-white/[0.06] text-[11px]">
            <div className="flex min-w-0 items-start justify-between gap-4 py-2.5">
              <span className="shrink-0 text-white/36">{isEnglish ? 'Data state' : '数据状态'}</span>
              <span
                className="min-w-0 break-words text-right text-white/60 whitespace-normal"
                data-testid="home-research-boundary-summary"
              >
                {qualityPreview}
              </span>
            </div>
            <div className="flex min-w-0 items-start justify-between gap-4 py-2.5">
              <span className="shrink-0 text-white/36">{isEnglish ? 'Research boundary' : '研究边界'}</span>
              <span className="min-w-0 break-words text-right text-white/60 whitespace-normal">
                {dataQualityLabel}
              </span>
            </div>
            {[
              { label: isEnglish ? 'Available data' : '已可用数据', value: availableCopy },
              { label: isEnglish ? 'Missing data' : '仍缺失数据', value: missingCopy },
              { label: isEnglish ? 'Impact' : '对结论的影响', value: qualityImpactCopy },
            ].map((item) => (
              <div key={item.label} className="flex min-w-0 items-start justify-between gap-4 py-2.5">
                <span className="shrink-0 text-white/36">{item.label}</span>
                <span className="min-w-0 break-words text-right text-white/60 whitespace-normal">{displaySlotValue(item.value, locale)}</span>
              </div>
            ))}
          </div>
        </details>
      </div>
    </section>
  );
}

function DecisionSourceDetailsPanel({
  report,
  locale,
  trace,
  sourceSummary,
}: {
  report: DataQualityReport | undefined;
  locale: DashboardLocale;
  trace?: DecisionTrace;
  sourceSummary?: string;
}) {
  if (!report && !sourceSummary && !trace) return null;

  const isEnglish = locale === 'en';
  const quickDecisionText = report?.requiredAvailable === false
    ? (isEnglish ? 'Key data: limited' : '关键数据：受限')
    : (isEnglish ? 'Key data: usable' : '关键数据：可用');
  const sourceEntries = Array.from(new Set(
    (trace?.dataSources || []).reduce<string[]>((acc, item) => {
      if (!['missing', 'unknown'].includes(String(item.status || '').trim().toLowerCase())) {
        const label = traceDataSourceLabel(item.name, locale);
        if (label) acc.push(label);
      }
      return acc;
    }, []),
  )).slice(0, 4);
  const missingCritical = !report
    ? (isEnglish ? 'No structured quality report' : '暂无结构化质量报告')
    : report.requiredAvailable === false
      ? (isEnglish ? 'Required quote or candle data missing' : '缺失关键行情或 K 线数据')
      : report.importantMissing?.slice(0, 3).map((item) => dataQualityFieldLabel(item, locale)).join('、') || (isEnglish ? 'No critical gaps' : '暂无关键缺口');
  const missingFields = report ? Array.from(new Set([
    ...(report.importantMissing || []),
    ...(report.optionalMissing || []),
  ])).map((item) => dataQualityFieldLabel(item, locale)).slice(0, 6) : [];
  const enrichmentGaps = report ? summarizeEnrichmentGaps(report) : [];
  const enrichmentReasons = report ? summarizeEnrichmentReasons(report).map((item) => dataQualityReasonLabel(item, locale)) : [];
  const degradedSources = Array.from(new Set(
    (trace?.dataSources || []).reduce<string[]>((acc, item) => {
      if (['fallback', 'stale'].includes(String(item.status || '').trim().toLowerCase())) {
        const label = traceDataSourceLabel(item.name, locale);
        if (label) acc.push(label);
      }
      return acc;
    }, []),
  )).slice(0, 4);
  const sourceText = sourceEntries.length
    ? sourceEntries.join(' / ')
    : sourceSummary || (isEnglish ? 'No source summary yet' : '暂无来源摘要');
  const degradationNotes = [
    degradedSources.length
      ? `${isEnglish ? 'Fallback / stale' : '备用 / 陈旧'}：${degradedSources.join(' / ')}`
      : null,
    report?.providerTimeouts?.length || report?.providerCooldowns?.length
      ? (isEnglish ? 'External feed temporarily degraded' : '外部数据源暂时降级')
      : null,
    enrichmentGaps.length
      ? `${isEnglish ? 'Pending gaps' : '待补缺口'}：${enrichmentGaps.map((item) => dataQualityFieldLabel(item, locale)).join('、')}`
      : null,
    enrichmentReasons.length
      ? `${isEnglish ? 'Notes' : '说明'}：${enrichmentReasons.join('、')}`
      : null,
  ].filter(Boolean).join(' · ');

  return (
    <section className="rounded-2xl border border-white/8 bg-white/[0.025] p-4" data-testid="home-bento-decision-source-details">
      <div className="flex min-w-0 items-center justify-between gap-3">
        <p className="text-[11px] font-semibold tracking-[0] text-white/70">
          {isEnglish ? 'Source and gaps' : '来源与缺口'}
        </p>
        {report?.requiredAvailable === false || report?.importantMissing?.length ? (
          <TraceBadge tone={report?.requiredAvailable === false ? 'missing' : 'warning'}>
            {isEnglish ? 'Key gap' : '关键缺口'}
          </TraceBadge>
        ) : null}
      </div>
      <div className="mt-3 min-w-0 divide-y divide-white/[0.055] border-t border-white/[0.055]" data-testid="home-bento-analysis-diagnostics-panel">
          <div className="grid min-w-0 gap-1 py-2.5 sm:grid-cols-[9rem_minmax(0,1fr)]">
            <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-white/38">
              {isEnglish ? 'Sources' : '来源'}
            </p>
            <p className="min-w-0 break-words text-xs leading-5 text-white/68">{sourceText}</p>
          </div>
          <div className="grid min-w-0 gap-1 py-2.5 sm:grid-cols-[9rem_minmax(0,1fr)]">
            <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-white/38">
              {isEnglish ? 'Missing' : '缺口'}
            </p>
            <div className="min-w-0">
              <p className="text-xs font-semibold text-emerald-200/80">{quickDecisionText}</p>
              <p className="mt-1 break-words text-xs leading-5 text-white/68">
                {missingFields.length ? missingFields.join('、') : missingCritical}
              </p>
            </div>
          </div>
          {degradationNotes ? (
            <div className="grid min-w-0 gap-1 py-2.5 sm:grid-cols-[9rem_minmax(0,1fr)]">
              <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-white/38">
                {isEnglish ? 'Stale / fallback' : '降级 / 陈旧'}
              </p>
              <p className="min-w-0 break-words text-xs leading-5 text-white/68">{degradationNotes}</p>
            </div>
          ) : null}
      </div>
    </section>
  );
}

function isEmptyDashboardValue(value?: string | null): boolean {
  const text = String(value || '').trim();
  return !text || text === EMPTY_FIELD_VALUE || /^n\/?a$/i.test(text);
}

function displaySlotValue(value: string | undefined | null, locale: DashboardLocale, fallback?: string): string {
  if (!isEmptyDashboardValue(value)) {
    return String(value).trim();
  }
  if (fallback) {
    return fallback;
  }
  return pendingDataText(locale);
}

function pendingDataText(locale: DashboardLocale): string {
  return locale === 'en' ? 'Pending data' : '待补充数据';
}

function resolveLinearSectorTrail(locale: DashboardLocale, sector?: string): string {
  const normalized = String(sector || '').trim();
  const lower = normalized.toLowerCase();
  if (locale === 'en') {
    if (!normalized || lower === 'unclassified') {
      return 'Single-name analysis / unclassified';
    }
    if (lower === 'technology') {
      return 'Single-name analysis / technology / software / application software';
    }
    return `Single-name analysis / ${normalized}`;
  }
  if (!normalized || lower === 'unclassified') {
    return '单标的分析 / 未分类';
  }
  if (lower === 'technology') {
    return '单标的分析 / 科技 / 软件 / 应用软件';
  }
  const zhLabels: Record<string, string> = {
    'communication services': '通信服务',
    'consumer cyclical': '可选消费',
    'consumer defensive': '必需消费',
    energy: '能源',
    financials: '金融',
    healthcare: '医疗保健',
    industrials: '工业',
    'real estate': '房地产',
    utilities: '公用事业',
  };
  return `单标的分析 / ${zhLabels[lower] || normalized}`;
}

function resolveConfidenceVisual(value: string | undefined, locale: DashboardLocale): {
  label: string;
  numeric: number | null;
  isMissing: boolean;
} {
  if (isEmptyDashboardValue(value)) {
    return {
      label: pendingDataText(locale),
      numeric: null,
      isMissing: true,
    };
  }

  const label = String(value || '').trim();
  const parsed = Number.parseFloat(label.replace(/[^\d.-]/g, ''));
  const numeric = Number.isFinite(parsed)
    ? Math.max(0, Math.min(100, parsed <= 1 ? parsed * 100 : parsed))
    : null;

  return { label, numeric, isMissing: false };
}

function resolveLinearStanceLabel(locale: DashboardLocale, signalLabel: string, tone: SignalTone): string {
  const text = String(signalLabel || '').trim();
  if (isEmptyDashboardValue(text)) {
    return pendingDataText(locale);
  }
  if (/hold|neutral|wait|observe|持有|中性|观望|观察|等待|仅观察/i.test(text)) {
    return locale === 'en' ? 'Observe' : '仅观察';
  }
  if (/sell|short|bear|reduce|trim|卖|空|看空|减仓|风险|不建议/i.test(text) || tone === 'bearish') {
    return locale === 'en' ? 'Not ready' : '不建议判断';
  }
  if (/buy|long|bull|watchlist|constructive|买|多|看多|乐观|偏多|有条件/i.test(text) || tone === 'bullish') {
    return locale === 'en' ? 'Watchlist' : '有条件观察';
  }
  return text;
}

function toneTextClass(tone: SignalTone | undefined, convention: ReturnType<typeof useUiPreferences>['marketColorConvention']): string {
  if (!tone || tone === 'neutral') {
    return 'text-white/76';
  }
  return getToneColor(tone, convention).textClass;
}

function toneTextStyle(tone: SignalTone | undefined, convention: ReturnType<typeof useUiPreferences>['marketColorConvention']): React.CSSProperties {
  if (!tone || tone === 'neutral') {
    return {};
  }
  return { textShadow: getToneColor(tone, convention).glowShadow };
}

function metricValueClass(metric: DashboardField, convention: ReturnType<typeof useUiPreferences>['marketColorConvention']): string {
  if (isEmptyDashboardValue(metric.value)) {
    return 'text-white/28';
  }
  return toneTextClass(metric.tone || 'neutral', convention);
}

function getMetricLabelForStrip(locale: DashboardLocale, label: string): string {
  if (label === '观察区间' || label === '建仓区间') {
    return '价格触发';
  }
  if (label === '上方观察区' || label === '目标位') {
    return '下一关注区间';
  }
  if (label === '风险失效线' || label === '止损位') {
    return '失效位';
  }
  if (label === 'Watch Zone' || label === 'Entry Zone') {
    return 'Trigger';
  }
  if (label === 'Upper Watch Zone' || label === 'Target') {
    return 'Next Zone';
  }
  if (label === 'Invalidation Line' || label === 'Stop') {
    return 'Invalidation';
  }
  return locale === 'en' ? label : label;
}

function buildLinearLevelMetrics(metrics: DashboardField[], locale: DashboardLocale): DashboardField[] {
  const slots = locale === 'en'
    ? [
        { aliases: ['watch zone', 'entry zone'], fallback: { label: 'Watch Zone', value: EMPTY_FIELD_VALUE, tone: 'neutral' as const } },
        { aliases: ['invalidation line', 'stop'], fallback: { label: 'Invalidation Line', value: EMPTY_FIELD_VALUE, tone: 'neutral' as const } },
        { aliases: ['upper watch zone', 'target'], fallback: { label: 'Upper Watch Zone', value: EMPTY_FIELD_VALUE, tone: 'neutral' as const } },
      ]
    : [
        { aliases: ['观察区间', '建仓区间'], fallback: { label: '观察区间', value: EMPTY_FIELD_VALUE, tone: 'neutral' as const } },
        { aliases: ['风险失效线', '止损位'], fallback: { label: '风险失效线', value: EMPTY_FIELD_VALUE, tone: 'neutral' as const } },
        { aliases: ['上方观察区', '目标位'], fallback: { label: '上方观察区', value: EMPTY_FIELD_VALUE, tone: 'neutral' as const } },
      ];
  const normalizeLabel = (value: string) => value.trim().toLowerCase();
  const findByAliases = (aliases: string[]) => metrics.find((metric) => {
    const label = normalizeLabel(metric.label);
    return aliases.some((alias) => label === normalizeLabel(alias));
  });
  return slots.map((slot) => findByAliases(slot.aliases) || slot.fallback);
}

function buildChartConclusionCopy(locale: DashboardLocale, signals: DashboardSignal[]): string {
  const hasBullishSignal = signals.some((signal) => signal.tone === 'bullish'
    || /偏强|多头|上方|突破|扩张|金叉|bull|above|constructive|strong|expand/i.test(`${signal.label} ${signal.value} ${signal.details || ''}`));
  const hasMissingSignal = signals.some((signal) => isEmptyDashboardValue(signal.value));
  if (locale === 'en') {
    if (hasBullishSignal) {
      return hasMissingSignal
        ? 'Chart conclusion: technical evidence is constructive, but missing metrics keep the view observational.'
        : 'Chart conclusion: technical structure is constructive; confirm it with follow-up evidence.';
    }
    return 'Chart conclusion: price structure still needs more evidence.';
  }
  if (hasBullishSignal) {
    return hasMissingSignal
      ? '图表结论：技术证据偏强，但缺失指标未补齐，仍保持仅观察。'
      : '图表结论：技术结构偏强，仍需后续证据确认。';
  }
  return '图表结论：价格结构仍需更多证据确认。';
}

function LinearKeyLevelsStrip({
  metrics,
  locale,
}: {
  metrics: DashboardField[];
  locale: DashboardLocale;
}) {
  const { marketColorConvention } = useUiPreferences();
  const levels = buildLinearLevelMetrics(metrics, locale);
  return (
    <div
      data-testid="home-research-key-levels"
      data-linear-primitive="key-level-strip"
      data-layout-zone="KeyLevelStrip"
      className="home-research-key-level-strip grid min-w-0 overflow-hidden rounded-[12px] border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] text-xs sm:grid-cols-[7rem_repeat(3,minmax(0,1fr))]"
    >
      <div className="home-research-key-level-label flex min-w-0 items-center border-b border-[color:var(--wolfy-divider)] px-3.5 py-2.5 sm:border-b-0 sm:border-r">
        <span className="truncate text-sm font-semibold text-white/88">{locale === 'en' ? 'Key levels' : '关键价位'}</span>
      </div>
      {levels.map((metric, index) => (
        <div
          key={metric.label}
          className={cn(
            'home-research-key-level-cell min-w-0 border-b border-[color:var(--wolfy-divider)] px-3.5 py-2.5 last:border-b-0 sm:border-b-0 sm:border-r sm:last:border-r-0',
          )}
          data-testid={`home-bento-strategy-metric-${metric.label}`}
          data-key-level-order={String(index + 1)}
        >
          <div className="truncate text-[11px] text-[color:var(--wolfy-text-muted)]">{getMetricLabelForStrip(locale, metric.label)}</div>
          <div
            className={cn('mt-1 truncate font-mono text-sm font-semibold', metricValueClass(metric, marketColorConvention))}
            style={toneTextStyle(metric.tone || 'neutral', marketColorConvention)}
          >
            {displaySlotValue(metric.value, locale)}
          </div>
        </div>
      ))}
    </div>
  );
}

function LinearTechnicalStructure({
  locale,
  ticker,
  currentPrice,
  signals,
  isGuest,
  shouldRenderHomeChart,
  homeChartLoadingLabel,
  guestPaywall,
  onOpenDetails,
  detailLabel,
  onChartContextChange,
}: {
  locale: DashboardLocale;
  ticker: string;
  currentPrice?: number | null;
  signals: DashboardSignal[];
  isGuest: boolean;
  shouldRenderHomeChart: boolean;
  homeChartLoadingLabel: string;
  guestPaywall?: React.ReactNode;
  onOpenDetails: () => void;
  detailLabel: string;
  onChartContextChange?: (context: HomeCandlestickChartContext | null) => void;
}) {
  const { marketColorConvention } = useUiPreferences();
  const isEnglish = locale === 'en';
  const chartConclusion = buildChartConclusionCopy(locale, signals);
  const signalRows: Array<DashboardSignal & { placeholderKey?: string }> = signals.slice(0, 6);
  while (signalRows.length < 6) {
    signalRows.push({
      label: isEnglish ? 'Pending metric' : '待补指标',
      value: EMPTY_FIELD_VALUE,
      rawValue: EMPTY_FIELD_VALUE,
      tone: 'neutral',
      details: EMPTY_FIELD_VALUE,
      placeholderKey: `pending-${signalRows.length + 1}`,
    });
  }
  const {
    ref: openDetailsButtonRef,
    onClick: handleOpenDetailsClick,
    onPointerUp: handleOpenDetailsPointerUp,
  } = useSafariWarmActivation<HTMLButtonElement>(onOpenDetails);

  return (
    <section
      className="home-research-chart-section relative min-w-0"
      data-layout-zone="PrimaryWorkRegion"
      data-visual-role="primary-chart-region"
      data-testid="home-bento-card-tech"
      data-research-card="risk-context"
    >
      <div className="mb-1.5 flex min-w-0 flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold tracking-[0] text-white/90">{locale === 'en' ? 'Technical Structure' : '技术结构'}</p>
          <p className="mt-1 text-xs leading-5 text-white/46" data-testid="home-linear-chart-conclusion">{chartConclusion}</p>
        </div>
        <button
          ref={openDetailsButtonRef}
          type="button"
          className="home-research-action-button rounded-lg border px-2.5 py-1 text-[11px] font-medium text-white/54 transition-colors hover:text-white/78"
          data-testid="home-bento-drawer-trigger-tech"
          onClick={handleOpenDetailsClick}
          onPointerUp={handleOpenDetailsPointerUp}
        >
          {detailLabel}
        </button>
      </div>
      <div
        className={cn(
          'grid min-w-0 overflow-hidden rounded-[8px] border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-inset)]',
          isGuest ? 'pointer-events-none opacity-80' : '',
        )}
        data-testid="home-research-chart-workspace"
      >
        {shouldRenderHomeChart ? (
          <Suspense
            fallback={(
              <HomeCandlestickChartFallback
                className="rounded-none border-0 bg-transparent shadow-none"
                style={{ background: 'transparent', borderColor: 'transparent', boxShadow: 'none' }}
                statusLabel={homeChartLoadingLabel}
              />
            )}
          >
            <LazyHomeCandlestickChart
              ticker={ticker}
              currentPrice={currentPrice}
              isLocked={isGuest}
              onContextChange={onChartContextChange}
              className="rounded-none border-0 bg-transparent shadow-none"
              style={{ background: 'transparent', borderColor: 'transparent', boxShadow: 'none' }}
            />
          </Suspense>
        ) : (
          <HomeCandlestickChartFallback
            className="rounded-none border-0 bg-transparent shadow-none"
            style={{ background: 'transparent', borderColor: 'transparent', boxShadow: 'none' }}
            statusLabel={homeChartLoadingLabel}
          />
        )}
        <div
          className="home-research-signal-rail hidden min-w-0 content-start overflow-hidden border-t border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] xl:border-l"
          data-testid="home-bento-decision-support-grid"
          data-visual-role="chart-adjacent-metrics"
        >
          {signalRows.map((signal) => {
            const muted = isEmptyDashboardValue(signal.value);
            const valueClass = muted ? 'text-white/28' : toneTextClass(signal.tone, marketColorConvention);
            const rowKey = signal.placeholderKey || signal.label;
            return (
              <div
                key={rowKey}
                className="home-research-signal-row flex min-w-0 flex-col gap-1 border-b border-[color:var(--wolfy-divider)] px-3 py-2 last:border-b-0"
                data-testid={`home-bento-tech-signal-${rowKey}`}
              >
                <div className="flex min-w-0 items-center justify-between gap-3">
                  <span className="truncate text-[11px] font-medium tracking-[0] text-white/38">{signal.label}</span>
                  <span
                    className={cn('min-w-0 break-words text-right text-xs font-semibold whitespace-normal', valueClass)}
                    style={toneTextStyle(signal.tone, marketColorConvention)}
                  >
                    {displaySlotValue(signal.value, locale)}
                  </span>
                </div>
                {signal.details && !isEmptyDashboardValue(signal.details) ? (
                  <p
                    className="block w-full overflow-hidden text-ellipsis whitespace-nowrap text-xs text-white/38"
                    data-testid={`home-bento-tech-signal-detail-${signal.label}`}
                    title={signal.details}
                  >
                    {signal.details}
                  </p>
                ) : null}
              </div>
            );
          })}
        </div>
      </div>
      {isGuest ? guestPaywall : null}
    </section>
  );
}

function LinearObservationPanel({
  locale,
  dashboard,
  dataQualityReport,
  isGuest,
  guestPaywall,
  onOpenStrategy,
  onOpenFundamentals,
}: {
  locale: DashboardLocale;
  dashboard: DashboardPayload;
  dataQualityReport?: DataQualityReport;
  isGuest: boolean;
  guestPaywall?: React.ReactNode;
  onOpenStrategy: () => void;
  onOpenFundamentals: () => void;
}) {
  const {
    ref: openStrategyButtonRef,
    onClick: handleOpenStrategyClick,
    onPointerUp: handleOpenStrategyPointerUp,
  } = useSafariWarmActivation<HTMLButtonElement>(onOpenStrategy);
  const {
    ref: openFundamentalsButtonRef,
    onClick: handleOpenFundamentalsClick,
    onPointerUp: handleOpenFundamentalsPointerUp,
  } = useSafariWarmActivation<HTMLButtonElement>(onOpenFundamentals);
  const isEnglish = locale === 'en';
  const observationRows = buildResearchFrameworkRows(locale, dashboard, dataQualityReport);
  const actionCopy = displaySlotValue(
    dashboard.strategy.positionBody || observationRows[0]?.value,
    locale,
    isEnglish ? 'Wait for the next clean setup.' : '等待下一次更干净的确认信号。',
  );
  const riskCopy = displaySlotValue(
    observationRows[2]?.value,
    locale,
    isEnglish ? 'Recheck the thesis if support fails.' : '若关键支撑失效，需要重新评估当前判断。',
  );
  const nextCopy = displaySlotValue(
    observationRows[3]?.value,
    locale,
    isEnglish ? 'Track the next candle and event evidence.' : '继续跟踪下一根 K 线与事件证据。',
  );

  return (
    <div className="home-research-rail-body relative flex min-w-0 flex-col gap-3 p-0">
      <section
        className="home-research-rail-card min-w-0 rounded-[8px] border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-panel)] px-5 py-4"
        data-testid="home-bento-card-strategy"
        data-research-card="research-actions"
        data-rail-section="current-action"
      >
        <div className="flex min-w-0 items-center justify-between gap-3">
          <p className="text-sm font-semibold tracking-[0] text-white">{isEnglish ? 'Current action' : '当前动作'}</p>
          <button
            ref={openStrategyButtonRef}
            type="button"
            className="home-research-action-button rounded-lg border px-2.5 py-1 text-[11px] font-medium text-white/48 transition-colors hover:text-white/72"
            data-testid="home-bento-drawer-trigger-strategy"
            onClick={handleOpenStrategyClick}
            onPointerUp={handleOpenStrategyPointerUp}
          >
            {dashboard.strategy.detailLabel}
          </button>
        </div>
        <p className="mt-2 line-clamp-2 min-w-0 break-words text-xs leading-[1.65] text-white/72">
          {actionCopy}
        </p>
      </section>

      <section
        className="home-research-rail-card min-w-0 rounded-[8px] border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-panel)] px-5 py-4"
        data-testid="home-bento-card-fundamentals"
        data-research-card="risk-boundary"
        data-rail-section="main-risk"
      >
        <div className="flex min-w-0 items-center justify-between gap-3">
          <p className="text-sm font-semibold tracking-[0] text-white">{isEnglish ? 'Main risk' : '主要风险'}</p>
          <button
            ref={openFundamentalsButtonRef}
            type="button"
            className="home-research-action-button rounded-lg border px-2.5 py-1 text-[11px] font-medium text-white/48 transition-colors hover:text-white/72"
            data-testid="home-bento-drawer-trigger-fundamentals"
            onClick={handleOpenFundamentalsClick}
            onPointerUp={handleOpenFundamentalsPointerUp}
          >
            {dashboard.fundamentals.detailLabel}
          </button>
        </div>
        <p className="mt-2 line-clamp-2 min-w-0 break-words text-xs leading-[1.65] text-white/72">
          {riskCopy}
        </p>
      </section>
      <section
        className="home-research-rail-card min-w-0 rounded-[8px] border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-panel)] px-5 py-4"
        data-testid="home-linear-quant-snapshot"
        data-research-card="next-step"
        data-rail-section="next-step"
      >
        <p className="text-sm font-semibold tracking-[0] text-white">{isEnglish ? 'Next step' : '下一步'}</p>
        <p className="mt-2 line-clamp-2 min-w-0 break-words text-xs leading-[1.65] text-white/72">
          {nextCopy}
        </p>
      </section>
      {isGuest ? <div className="min-w-0 py-2 last:pb-0">{guestPaywall}</div> : null}
    </div>
  );
}

type HomeCatalystEvent = {
  label: string;
  title: string;
  detail: string;
  importance: 'high' | 'medium';
  time: string;
};

function catalystImpactLabel(event: HomeCatalystEvent, locale: DashboardLocale): string {
  if (/分红|dividend/i.test(event.title) || /回购|buyback/i.test(event.title)) {
    return locale === 'en' ? 'Positive' : '利多';
  }
  if (/财报|earnings|results?/i.test(event.title) || /财报|earnings|results?/i.test(event.label)) {
    return locale === 'en' ? 'Positive' : '利多';
  }
  return locale === 'en' ? 'Neutral' : '中性';
}

function catalystDaysRemaining(event: HomeCatalystEvent, locale: DashboardLocale): string {
  const normalized = String(event.time || '').trim();
  const dateMatch = normalized.match(/20\d{2}[-/.年]\d{1,2}(?:[-/.月]\d{1,2})?/);
  if (!dateMatch) {
    return locale === 'en' ? 'Pending' : '待补充';
  }
  const parts = dateMatch[0].replace(/[年月]/g, '-').replace(/日/g, '').replace(/[/.]/g, '-').split('-');
  const [year, month, day] = parts.map((item) => Number.parseInt(item, 10));
  if (!year || !month || !day) {
    return locale === 'en' ? 'Pending' : '待补充';
  }
  const target = Date.UTC(year, month - 1, day);
  const base = Date.UTC(2026, 4, 17);
  const diffDays = Math.ceil((target - base) / 86_400_000);
  if (!Number.isFinite(diffDays) || diffDays < 0) {
    return locale === 'en' ? 'Pending' : '待补充';
  }
  return locale === 'en' ? `${diffDays}d` : `${diffDays} 天`;
}

const CATALYST_EVENT_RE = /财报|业绩会|公告|发布|新品|产品|基础设施|监管|批准|反垄断|诉讼|合作|伙伴|客户|订单|合同|并购|收购|宏观|行业|板块|降息|加息|CPI|PPI|FOMC|非农|评级|目标价|上调|下调|earnings|results?|announcement|announces?|launch|release|product|infrastructure|regulatory|approval|lawsuit|partnership|customer|order|contract|acquisition|macro|sector|rate cut|rate hike|rating|target price|upgrade|downgrade/i;
const CATALYST_DATE_RE = /\b(?:20\d{2}[-/.年]\d{1,2}(?:[-/.月]\d{1,2}日?)?|\d{1,2}[-/.月]\d{1,2}(?:日)?|Q[1-4]\s*20\d{2}|FY\s*20\d{2})\b/i;
const CATALYST_FILLER_RE = /均线|MA\d+|moving average|技术结构|technical structure|技术形态|MACD|RSI|K线|支撑|压力|阻力|止损|目标位|数据状态|数据缺失|缺失|fallback|降级|报告主线|综合建议|结论|摘要|继续跟踪|财报跟踪$|financial follow-up|data status|missing data|report conclusion|thesis/i;

function cleanCatalystText(value: unknown): string {
  return String(value ?? '').replace(/\s+/g, ' ').trim();
}

function isVerifiedCatalystText(value: unknown, requireDate = false): boolean {
  const text = cleanCatalystText(value);
  if (!text || text === EMPTY_FIELD_VALUE || isPendingMetricValue(text)) {
    return false;
  }
  if (CATALYST_FILLER_RE.test(text)) {
    return false;
  }
  if (requireDate && !CATALYST_DATE_RE.test(text)) {
    return false;
  }
  return CATALYST_EVENT_RE.test(text) || CATALYST_DATE_RE.test(text);
}

function buildHomeCatalystEvents(report: AnalysisReport | null | undefined, locale: DashboardLocale): HomeCatalystEvent[] {
  const isEnglish = locale === 'en';
  const standardReport = report?.details?.standardReport;
  const highlights = standardReport?.highlights;
  const reasonLayer = standardReport?.reasonLayer;
  const earningsFields = [
    ...(standardReport?.earningsFields || []),
    ...(standardReport?.tableSections?.earnings?.fields || []),
  ];
  const candidates: HomeCatalystEvent[] = [];
  const pushCandidate = (
    label: string,
    title: unknown,
    detail: unknown,
    importance: HomeCatalystEvent['importance'] = 'medium',
    requireDate = false,
  ) => {
    const titleText = cleanCatalystText(title);
    const detailText = cleanCatalystText(detail);
    const combined = [titleText, detailText].filter(Boolean).join(' ');
    if (!isVerifiedCatalystText(combined, requireDate)) {
      return;
    }
    candidates.push({
      label,
      title: titleText || detailText,
      detail: detailText && detailText !== titleText ? detailText : (isEnglish ? 'Verified event input' : '已验证事件线索'),
      importance,
      time: CATALYST_DATE_RE.test(combined) ? (combined.match(CATALYST_DATE_RE)?.[0] || (isEnglish ? 'Dated' : '有日期')) : (isEnglish ? 'Latest' : '最新'),
    });
  };

  (highlights?.latestNews || []).forEach((item) => {
    pushCandidate(isEnglish ? 'News' : '新闻', item, '', 'high');
  });
  (highlights?.positiveCatalysts || []).forEach((item) => {
    pushCandidate(isEnglish ? 'Catalyst' : '催化', item, '', 'medium');
  });
  pushCandidate(isEnglish ? 'Company update' : '公司动态', reasonLayer?.latestKeyUpdate, '', 'medium');
  pushCandidate(isEnglish ? 'Catalyst' : '催化', reasonLayer?.topCatalyst, '', 'medium');
  pushCandidate(isEnglish ? 'Earnings' : '财报', highlights?.earningsOutlook, '', 'medium', true);
  earningsFields.forEach((field) => {
    pushCandidate(isEnglish ? 'Earnings' : '财报', field.label, field.value, 'medium', true);
  });

  const seen = new Set<string>();
  return candidates.filter((event) => {
    const key = `${event.label}:${event.title}:${event.detail}`;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  }).slice(0, 4);
}

function LinearEventsStrip({
  locale,
  report,
}: {
  locale: DashboardLocale;
  report?: AnalysisReport | null;
}) {
  const isEnglish = locale === 'en';
  const events = buildHomeCatalystEvents(report, locale);
  const placeholderRows = Array.from({ length: 3 }, (_, index) => index);
  const pendingText = pendingDataText(locale);

  return (
    <div
      className="min-w-0"
      data-testid="home-linear-events"
      data-visual-role="attached-event-deck"
    >
      <div className="flex min-w-0 items-center justify-between gap-3 pb-1.5">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-white/88">{isEnglish ? 'Recent catalysts / events' : '近期催化剂 / 事件'}</h2>
          <p className="mt-0.5 text-xs text-white/42" data-testid="home-linear-events-evidence-note">
            {isEnglish ? 'Evidence only: dated or explicit company/market events.' : '事件证据：仅展示带日期或明确公司/市场线索的事项。'}
          </p>
        </div>
        <span className="text-[11px] text-white/34">{events.length ? `${events.length}${isEnglish ? ' rows' : ' 条'}` : pendingText}</span>
      </div>
      <div
        className="home-research-event-table min-w-0 overflow-hidden border-t border-[color:var(--wolfy-divider)] text-xs"
        data-testid="home-linear-events-table"
      >
        {events.length ? events.map((event, index) => (
          <div
            key={`${event.label}-${index}`}
            className="home-research-event-row flex min-w-0 items-start justify-between gap-3 border-b border-[color:var(--wolfy-divider)] py-3 last:border-b-0"
            data-testid={`home-linear-event-row-${index}`}
          >
            <div className="min-w-0 flex-1">
              <p className="min-w-0 truncate text-[color:var(--wolfy-text-primary)]">
                {displaySlotValue(event.title, locale, isEnglish ? 'No verified event' : '暂无已验证事件')}
              </p>
              <div className="mt-1 flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-white/46">
                <span>{event.label}</span>
                <span
                  className={cn(
                    catalystImpactLabel(event, locale) === '利多' || catalystImpactLabel(event, locale) === 'Positive'
                      ? 'text-[color:var(--wolfy-market-up)]'
                      : 'text-white/52',
                  )}
                >
                  {catalystImpactLabel(event, locale)}
                </span>
                <span>{event.importance === 'high' ? '高优先' : '中优先'}</span>
              </div>
            </div>
            <div className="shrink-0 text-right text-[11px] text-white/44">
              <p className="font-mono text-white/58">{displaySlotValue(event.time, locale)}</p>
              <p className="mt-1 font-mono">{catalystDaysRemaining(event, locale)}</p>
            </div>
          </div>
        )) : (
          <div data-testid="home-linear-events-empty">
            {placeholderRows.map((index) => (
              <div
                key={`home-event-placeholder-${index}`}
                className="home-research-event-row flex min-w-0 items-start justify-between gap-3 border-b border-[color:var(--wolfy-divider)] py-3 text-[color:var(--wolfy-text-muted)] last:border-b-0"
                data-testid={`home-linear-event-placeholder-row-${index}`}
              >
                <div className="min-w-0 flex-1">
                  <span className="block min-w-0 truncate">{pendingText}</span>
                  <span className="mt-1 block min-w-0 truncate text-[11px]">{pendingText}</span>
                </div>
                <div className="shrink-0 text-right text-[11px]">
                  <span className="block font-mono">{pendingText}</span>
                  <span className="mt-1 block font-mono">{pendingText}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      {events.length ? (
        <details className="group mt-3 min-w-0 rounded-[10px] border border-white/[0.06] bg-white/[0.015] px-3 py-2.5" data-testid="home-linear-events-disclosure">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-[11px] font-medium text-white/50 marker:hidden">
            <span>{isEnglish ? 'View event notes' : '查看事件说明'}</span>
            <span className="text-white/28 transition-transform group-open:rotate-180">{isEnglish ? '▾' : '▾'}</span>
          </summary>
          <div className="mt-2.5 divide-y divide-white/[0.06] border-t border-white/[0.06]">
            {events.map((event, index) => (
              <div key={`${event.label}-detail-${index}`} className="py-2.5">
                <p className="text-[11px] font-semibold text-white/66">{event.title}</p>
                <p className="mt-1 text-xs leading-[1.55] text-white/52">{displaySlotValue(event.detail, locale, pendingText)}</p>
              </div>
            ))}
          </div>
        </details>
      ) : null}
    </div>
  );
}

type DashboardField = {
  label: string;
  value: string;
  rawValue?: string;
  tone?: SignalTone;
  details?: string;
};

type DashboardSignal = DashboardField & {
  tone: SignalTone;
};

type HomePriceCurrency = 'usd' | 'cny' | 'hkd' | 'crypto' | 'unknown';

type HomePriceDisplayContext = {
  currency: HomePriceCurrency;
  cryptoUnit?: string;
};

type HomePriceContextReport = {
  meta?: unknown;
  details?: { standardReport?: unknown } | null;
  decisionTrace?: { market?: unknown } | null;
};

type DesiredFieldSpec = {
  aliases: string[];
  fallback: DashboardField;
};

const CJK_TEXT_RE = /[\u3400-\u9FFF]/;
const TICKER_FORMAT_RE = /^[A-Z]{1,5}$|^\d{6}$/;
const EMPTY_FIELD_VALUE = '-';
const UNTRUSTED_SCAN_SKIP_KEYS = new Set([
  'rawResult',
  'raw_result',
  'contextSnapshot',
  'context_snapshot',
]);

function normalizeDetailKey(value?: string): string {
  return String(value || '').toLowerCase().replace(/[\s/()%+.\-_:]+/g, '');
}

function containsCjk(value?: string): boolean {
  return CJK_TEXT_RE.test(String(value || ''));
}

function isPendingMetricValue(value?: string): boolean {
  const normalized = String(value || '').trim().toLowerCase();
  return normalized === ''
    || normalized === '--'
    || normalized === '-'
    || /^(na|n\/a)[（(]?(字段待接入|field pending)?[）)]?$/i.test(normalized)
    || /字段待接入|field pending/i.test(normalized);
}

function sanitizeMetricValue(value?: string): string {
  return isPendingMetricValue(value) ? '-' : String(value || '').trim();
}

function isPeLikeMetric(label: string): boolean {
  const key = normalizeDetailKey(label);
  return key === 'pe'
    || key.includes('市盈率')
    || key.includes('预期pe')
    || key.includes('peratio')
    || key.includes('pettm')
    || key.includes('forwardpe')
    || key.includes('pegratio')
    || key.includes('peg比率');
}

function isZombieStockLabel(value: unknown): boolean {
  const text = String(value || '').trim();
  const normalized = text.toLowerCase();
  return normalized === '待确认股票' || normalized === 'unknown' || normalized === 'unnamed stock' || /^股票[A-Z0-9.]+$/i.test(text);
}

function hasTrustedNormalizedHomeContent(report: AnalysisReport): boolean {
  const standardReport = report.details?.standardReport;
  const summaryPanel = standardReport?.summaryPanel;
  const decisionPanel = standardReport?.decisionPanel;
  const battleCards = standardReport?.battlePlanCompact?.cards || [];
  const analysisResult = readObjectField(report, ['details', 'analysisResult']) as Record<string, unknown> | undefined;
  const trace = getDecisionTrace(report);

  return Boolean(
    trace?.decisionFields && Object.keys(trace.decisionFields).length > 0
    || summaryPanel?.score !== undefined
    || summaryPanel?.oneSentence
    || decisionPanel?.confidence
    || decisionPanel?.idealEntry
    || decisionPanel?.target
    || decisionPanel?.stopLoss
    || battleCards.length > 0
    || analysisResult?.score !== undefined
    || analysisResult?.confidence
    || analysisResult?.entryPrice
    || analysisResult?.takeProfit
    || analysisResult?.stopLoss,
  );
}

function hasFailedAnalysisText(value: unknown): boolean {
  if (typeof value !== 'string') {
    return false;
  }

  return /all llm models failed|serviceunavailable|rate limit|ratelimiterror|timeout|timed out|分析过程出错|llm.*failed/i.test(value);
}

function hasUntrustedReportMarker(payload: unknown): boolean {
  if (!payload || typeof payload !== 'object') {
    return false;
  }

  for (const [key, value] of Object.entries(payload)) {
    if (UNTRUSTED_SCAN_SKIP_KEYS.has(key)) {
      continue;
    }
    if (/stock(name)?$/i.test(key) && isZombieStockLabel(value)) {
      return true;
    }
    if (hasFailedAnalysisText(value)) {
      return true;
    }
    if (typeof value === 'object' && value !== null && hasUntrustedReportMarker(value)) {
      return true;
    }
  }

  return false;
}

function neutralFieldValue(label: string): string {
  return isPeLikeMetric(label) ? 'N/A' : EMPTY_FIELD_VALUE;
}

function neutralizeDashboardFields(fields: DashboardField[]): DashboardField[] {
  return fields.map((field) => {
    const value = neutralFieldValue(field.label);
    return {
      ...field,
      value,
      rawValue: value,
      tone: 'neutral',
      details: value,
    };
  });
}

function neutralizeDashboardSignals(signals: DashboardSignal[]): DashboardSignal[] {
  return signals.map((signal) => ({
    ...signal,
    value: EMPTY_FIELD_VALUE,
    rawValue: EMPTY_FIELD_VALUE,
    tone: 'neutral',
    details: EMPTY_FIELD_VALUE,
  }));
}

const COMPANY_PROFILES: Record<string, { company: string; sector: string }> = {
  AAPL: { company: 'Apple Inc.', sector: 'Technology' },
  AMD: { company: 'Advanced Micro Devices, Inc.', sector: 'Technology' },
  APP: { company: 'AppLovin Corporation', sector: 'Technology' },
  MSFT: { company: 'Microsoft Corporation', sector: 'Technology' },
  NFLX: { company: 'Netflix Inc.', sector: 'Communication Services' },
  NVDA: { company: 'NVIDIA Corporation', sector: 'Technology' },
  ORCL: { company: 'Oracle Corporation', sector: 'Technology' },
  TSLA: { company: 'Tesla, Inc.', sector: 'Consumer Cyclical' },
};

function resolveCompanyProfile(ticker: string, rawCompany?: string): { company: string; sector: string } {
  const normalizedTicker = normalizeTickerQuery(ticker);
  const knownProfile = COMPANY_PROFILES[normalizedTicker];
  const cleanedCompany = normalizeCompanyNameCandidate(rawCompany, normalizedTicker);

  if (knownProfile) {
    return knownProfile;
  }

  return {
    company: cleanedCompany || normalizedTicker || EMPTY_FIELD_VALUE,
    sector: 'Unclassified',
  };
}

function isGenericInsightText(value?: string): boolean {
  return /综合建议|结合技术|基本面与情绪|继续跟踪|多维数据|综合评估|建议关注/i.test(String(value || ''));
}

function buildTechnicalInsightFallback(
  locale: DashboardLocale,
  tone: SignalTone,
  technicalFields?: StandardReportField[],
): string {
  const fieldText = (technicalFields || [])
    .map((field) => `${field.label} ${field.value}`)
    .join(' ');
  const hasOverbought = /rsi\s*:?\s*(6[8-9]|[7-9]\d)|RSI[^\d]*(6[8-9]|[7-9]\d)|超买/i.test(fieldText);
  const hasBullishMa = /多头|MA5|MA10|MA20|MA60|above|lifting|bull/i.test(fieldText);
  const hasBearishMa = /下压|跌破|below|bear|weak/i.test(fieldText);

  if (locale === 'en') {
    if (tone === 'bearish' || hasBearishMa) {
      return 'Trend tape is losing sponsorship: moving-average pressure remains overhead, downside confirmation is not fully priced, and risk should be cut before adding exposure.';
    }
    if (tone === 'bullish' || hasBullishMa) {
      return hasOverbought
        ? 'The tape remains in bullish moving-average alignment with acceptable volume confirmation, but RSI is stretched into an overbought band, so near-term strength should be trimmed rather than chased.'
        : 'The tape is holding bullish moving-average alignment with improving momentum confirmation; pullbacks into the short-term support cluster remain the cleaner execution window.';
    }
    return 'The setup is still a repair trade: short-term averages are stabilizing, but momentum confirmation is incomplete, so wait for a second volume expansion before increasing risk.';
  }

  if (tone === 'bearish' || hasBearishMa) {
    return '技术面仍受均线压制，空头动能尚未完全释放，量价结构没有给出有效反包信号，短线应先降风险而不是补仓。';
  }
  if (tone === 'bullish' || hasBullishMa) {
    return hasOverbought
      ? '技术面呈现均线多头排列，量价配合理想，但 RSI 已进入超买区，短线更适合逢高减仓而不是追价。'
      : '技术面维持均线多头排列，动能确认仍在，回踩短期支撑簇时更适合分批试仓，放量跌破则立即收缩风险。';
  }
  return '技术面处于均线修复段，短线动能尚未完全失效，但量价确认不足，当前以等待二次放量和支撑回踩确认为主。';
}

function resolveInsightBody(
  locale: DashboardLocale,
  tone: SignalTone,
  candidates: Array<string | undefined>,
  technicalFields?: StandardReportField[],
): string {
  const normalizedCandidates = candidates.flatMap((value) => { const v = String(value || '').trim(); return v ? [v] : []; });
  const primary = normalizedCandidates.find((value) => value !== EMPTY_FIELD_VALUE && !isGenericInsightText(value));
  if (!primary) {
    return buildTechnicalInsightFallback(locale, tone, technicalFields);
  }
  return primary;
}

const CONTENT: Record<DashboardLocale, {
    documentTitle: string;
  eyebrow: string;
  heading: string;
  description: string;
    omnibarPlaceholder: string;
  analyzeButton: string;
  instrument: string;
  ticker: string;
  sessionBadge: string;
  regimeBadge: string;
  decision: {
    eyebrow: string;
    company: string;
    heroValue: string;
    heroUnit: string;
    heroLabel: string;
    confidenceValue?: string;
    signalLabel: string;
    signalTone: SignalTone;
    scoreLabel: string;
    scoreValue: string;
    badge: string;
    chartLabel: string;
    sector?: string;
    summary: string;
    reasonTitle: string;
    reasonBody: string;
    detailLabel: string;
  };
  strategy: {
    title: string;
    subtitle?: string;
    metrics: DashboardField[];
    positionLabel: string;
    positionBody: string;
    detailLabel: string;
  };
  tech: {
    title: string;
    signals: DashboardSignal[];
    detailLabel: string;
  };
  fundamentals: {
    title: string;
    metrics: DashboardField[];
    detailLabel: string;
  };
  drawers: {
    decision: DrawerPayload;
    strategy: DrawerPayload;
    tech: DrawerPayload;
    fundamentals: DrawerPayload;
  };
}> = {
  zh: {
    documentTitle: '首页 - WolfyStock',
    eyebrow: 'SYSTEM VIEW',
    heading: 'WolfyStock 分析面板',
    description: '',
    omnibarPlaceholder: '输入代码唤醒 AI (如 ORCL)...',
    analyzeButton: '分析',
    instrument: '英伟达',
    ticker: 'NVDA',
    sessionBadge: '美股 AI 基础设施',
    regimeBadge: '动量回升',
    decision: {
      eyebrow: 'WOLFY AI 分析',
      company: '英伟达',
      heroValue: '8.6',
      heroUnit: '/10',
      heroLabel: '置信度',
      signalLabel: '有条件观察',
      signalTone: 'bullish',
      scoreLabel: '信号方向',
      scoreValue: '72H 继续偏强',
      badge: '动能回升 · 机构跟进',
      chartLabel: '突破完成',
      summary: '订单动能回升，价格重新贴近强趋势区间，适合继续等待回踩确认。',
      reasonTitle: '最近报告归因',
      reasonBody: '盘中监测到大级别资金吸筹，价格成功站稳 MA60 关键支撑位，并伴随 MACD 零轴上方金叉，确认箱体突破有效。',
      detailLabel: '完整报告',
    },
    strategy: {
      title: '观察框架',
      metrics: [
        { label: '观察区间', value: '118.40 - 121.00', tone: 'neutral' },
        { label: '上方观察区', value: '136.00', tone: 'bullish' },
        { label: '风险失效线', value: '111.80', tone: 'bearish' },
      ],
      positionLabel: '跟踪节奏',
      positionBody: '先记录小样本观察假设，只有确认站稳后再提高关注级别；若放量跌破关键支撑，优先回到等待状态。',
      detailLabel: '查看观察细节',
    },
    tech: {
      title: '技术形态',
      signals: [
        { label: '均线结构', value: '多头排列', tone: 'bullish' },
        { label: 'RSI-14', value: '65.4 (强势区)', tone: 'neutral' },
        { label: 'MACD', value: '零轴上方金叉', tone: 'bullish' },
        { label: '量价动态', value: '放量突破', tone: 'bullish' },
      ],
      detailLabel: '查看结构细节',
    },
    fundamentals: {
      title: '基本面画像',
      metrics: [
        { label: 'ROE', value: '31.8%', tone: 'bullish' },
        { label: 'EBITDA 利润率', value: '42.5%', tone: 'bullish' },
        { label: '最新 EPS', value: '$1.24 (超预期 +12%)', tone: 'bullish' },
        { label: '营收', value: '$26.0B (不及预期 -2%)', tone: 'neutral' },
        { label: '预期 P/E', value: '35.2x', tone: 'neutral' },
        { label: 'PEG 比率', value: '1.15', tone: 'neutral' },
      ],
      detailLabel: '查看基本面细节',
    },
    drawers: {
      decision: { title: '', modules: [] },
      strategy: { title: '', modules: [] },
      tech: { title: '', modules: [] },
      fundamentals: { title: '', modules: [] },
    },
  },
  en: {
    documentTitle: 'Home - WolfyStock',
    eyebrow: 'SYSTEM VIEW',
    heading: 'WolfyStock Analysis Center',
    description: '',
    omnibarPlaceholder: 'Enter a ticker to wake the AI (for example ORCL)...',
    analyzeButton: 'Analyze',
    instrument: 'NVIDIA',
    ticker: 'NVDA',
    sessionBadge: 'US AI infrastructure',
    regimeBadge: 'Momentum rebuilding',
    decision: {
      eyebrow: 'WOLFY AI ANALYSIS',
      company: 'NVIDIA',
      heroValue: '8.6',
      heroUnit: '/10',
      heroLabel: 'Conviction',
      signalLabel: 'Watchlist',
      signalTone: 'bullish',
      scoreLabel: 'Signal Direction',
      scoreValue: 'Bias stays constructive for 72H',
      badge: 'Momentum rebuild · institutional follow-through',
      chartLabel: 'Breakout Confirmed',
      summary: 'Order momentum is improving and price is moving back into a strong-trend zone, so the cleaner plan is to wait for pullback confirmation.',
      reasonTitle: 'Latest Report Context',
      reasonBody: 'Intraday flow points to institutional accumulation, price reclaimed MA60 support, and the MACD bullish cross stayed above zero to validate the range escape.',
      detailLabel: 'Open Decision Brief',
    },
    strategy: {
      title: 'Observation Framework',
      metrics: [
        { label: 'Watch Zone', value: '118.40 - 121.00', tone: 'neutral' },
        { label: 'Upper Watch Zone', value: '136.00', tone: 'bullish' },
        { label: 'Invalidation Line', value: '111.80', tone: 'bearish' },
      ],
      positionLabel: 'Tracking Rhythm',
      positionBody: 'Keep this as an observation hypothesis, then raise attention only after the reclaim holds. If support breaks on volume, return to waiting.',
      detailLabel: 'Open Observation Brief',
    },
    tech: {
      title: 'Technical Structure',
      signals: [
        { label: 'MA ALIGNMENT', value: 'Bullish Alignment', tone: 'bullish' },
        { label: 'RSI-14', value: '65.4 (Strong Zone)', tone: 'neutral' },
        { label: 'MACD', value: 'Bullish Crossover Above Zero', tone: 'bullish' },
        { label: 'VOLUME DYNAMICS', value: 'High Vol Breakout', tone: 'bullish' },
      ],
      detailLabel: 'Open Technical Brief',
    },
    fundamentals: {
      title: 'Fundamental Profile',
      metrics: [
        { label: 'ROE', value: '31.8%', tone: 'bullish' },
        { label: 'EBITDA MARGIN', value: '42.5%', tone: 'bullish' },
        { label: 'LATEST EPS', value: '$1.24 (Beat +12%)', tone: 'bullish' },
        { label: 'REVENUE', value: '$26.0B (Miss -2%)', tone: 'neutral' },
        { label: 'FORWARD PE', value: '35.2x', tone: 'neutral' },
        { label: 'PEG RATIO', value: '1.15', tone: 'neutral' },
      ],
      detailLabel: 'Open Fundamental Brief',
    },
    drawers: {
      decision: { title: '', modules: [] },
      strategy: { title: '', modules: [] },
      tech: { title: '', modules: [] },
      fundamentals: { title: '', modules: [] },
    },
  },
};

type DashboardPayload = (typeof CONTENT)['zh'];
type DashboardVariant = DashboardPayload;

type HomeNormalizedAnalysisResult = {
  action?: string;
  score?: string;
  confidence?: string;
  entry?: string;
  target?: string;
  stop?: string;
  summary?: string;
  scoreContext?: string;
  badge?: string;
  reason?: string;
  positionBody?: string;
  technicalFields: StandardReportField[];
  fundamentalFields?: StandardReportField[];
};

function getDecisionTrace(report: AnalysisReport): DecisionTrace | undefined {
  const trace = report.decisionTrace || (report as unknown as Record<string, DecisionTrace | undefined>).decision_trace;
  const traceSymbol = normalizeTickerQuery(trace?.symbol);
  const reportSymbol = normalizeTickerQuery(report.meta.stockCode);
  if (traceSymbol && reportSymbol && traceSymbol !== reportSymbol) {
    return undefined;
  }
  return trace;
}

function normalizeScoreValue(value: unknown): string | undefined {
  if (value === null || value === undefined || value === '') {
    return undefined;
  }
  if (typeof value === 'number') {
    return Number.isFinite(value) ? String(Math.round(value * 10) / 10) : undefined;
  }
  const text = String(value).trim();
  return text && !isPendingMetricValue(text) ? text : undefined;
}

function normalizeDecisionAction(value: unknown, locale: DashboardLocale): string | undefined {
  const text = String(value ?? '').trim();
  if (!text || isPendingMetricValue(text)) {
    return undefined;
  }
  const normalized = text.toLowerCase();
  const zhLabels: Record<string, string> = {
    buy: '有条件观察',
    hold: '仅观察',
    sell: '不建议判断',
    reduce: '风险复核',
  };
  const enLabels: Record<string, string> = {
    buy: 'Watchlist',
    hold: 'Observe',
    sell: 'Not ready',
    reduce: 'Risk review',
  };
  if (normalized in zhLabels) {
    return locale === 'en' ? enLabels[normalized] : zhLabels[normalized];
  }
  return text;
}

function firstMeaningfulValue(values: unknown[]): string | undefined {
  for (const value of values) {
    const text = String(value ?? '').trim();
    if (text && !isPendingMetricValue(text)) {
      return text;
    }
  }
  return undefined;
}

function findBattlePlanValue(standardReport: StandardReport | undefined, aliases: string[]): string | undefined {
  const field = fieldValue(standardReport?.battleFields, aliases);
  if (field && !isPendingMetricValue(field)) {
    return field;
  }
  const normalizedAliases = aliases.map((alias) => normalizeDetailKey(alias));
  const items = [
    ...(standardReport?.battlePlanCompact?.cards || []),
    ...(standardReport?.battlePlanCompact?.notes || []),
  ];
  return items
    .find((item) => normalizedAliases.some((alias) => normalizeDetailKey(item.label).includes(alias) || alias.includes(normalizeDetailKey(item.label))))
    ?.value;
}

function normalizeHomeAnalysisResult(report: AnalysisReport, locale: DashboardLocale): HomeNormalizedAnalysisResult {
  const standardReport = report.details?.standardReport;
  const summaryPanel = standardReport?.summaryPanel;
  const reportTitle = standardReport?.title;
  const titleScore = readObjectField(reportTitle, ['score']);
  const titleSignalText = readObjectField(reportTitle, ['signalText']);
  const titleOperationAdvice = readObjectField(reportTitle, ['operationAdvice']);
  const titleTrendPrediction = readObjectField(reportTitle, ['trendPrediction']);
  const titleOneSentence = readObjectField(reportTitle, ['oneSentence']);
  const decisionPanel = standardReport?.decisionPanel;
  const decisionContext = standardReport?.decisionContext;
  const reasonLayer = standardReport?.reasonLayer;
  const trace = getDecisionTrace(report);
  const traceFields = trace?.decisionFields || {};
  const analysisResult = readObjectField(report, ['details', 'analysisResult']) as Record<string, unknown> | undefined;
  const rawResult = report.details?.rawResult as Record<string, unknown> | undefined;
  const rawDashboard = (rawResult?.dashboard as Record<string, unknown> | undefined) || {};
  const rawDataPerspective = (rawDashboard.dataPerspective as Record<string, unknown> | undefined) || {};
  const rawStructuredAnalysis = (rawDashboard.structuredAnalysis as Record<string, unknown> | undefined) || {};
  const rawTechnicals = (rawStructuredAnalysis.technicals as Record<string, unknown> | undefined) || {};
  const rawTrendStatus = (rawDataPerspective.trendStatus as Record<string, unknown> | undefined) || {};
  const rawVolumeAnalysis = (rawDataPerspective.volumeAnalysis as Record<string, unknown> | undefined) || {};
  const rawAlphaVantage = (rawDataPerspective.alphaVantage as Record<string, unknown> | undefined) || {};
  const technicalFields = [...(standardReport?.technicalFields || standardReport?.tableSections?.technical?.fields || [])];

  if (!findStandardField(technicalFields, ['MACD'])) {
    const macdValue = readMetricNodeValue(rawTechnicals.macd);
    if (macdValue !== undefined) {
      technicalFields.push({ label: 'MACD', value: macdValue });
    }
  }
  if (!findStandardField(technicalFields, ['RSI-14', 'RSI14', 'RSI'])) {
    const rsiValue = readMetricNodeValue(rawTechnicals.rsi14)
      ?? readMetricNodeValue(rawTechnicals.rsi)
      ?? readMetricNodeValue(rawAlphaVantage.rsi14)
      ?? readMetricNodeValue(rawAlphaVantage.rsi);
    if (rsiValue !== undefined) {
      technicalFields.push({ label: 'RSI14', value: rsiValue });
    }
  }
  if (!findStandardField(technicalFields, ['MA ALIGNMENT', 'Moving Averages', '均线结构', '均线系统', '多头/空头排列'])) {
    const maAlignment = rawTrendStatus.maAlignment;
    if (maAlignment !== undefined) {
      technicalFields.push({ label: '多头/空头排列', value: String(maAlignment) });
    }
  }
  if (!findStandardField(technicalFields, ['VOLUME DYNAMICS', 'Volume Profile', '量价配合', '量价判断', '成交量', 'Volume'])) {
    const volumeMeaning = rawVolumeAnalysis.volumeMeaning;
    if (volumeMeaning !== undefined) {
      technicalFields.push({ label: '量价判断', value: String(volumeMeaning) });
    }
  }

  const score = normalizeScoreValue(firstMeaningfulValue([
    traceFields.score?.value,
    summaryPanel?.score,
    titleScore,
    report.contractMeta?.hasExplicitSentimentScore === true ? report.summary.sentimentScore : undefined,
    analysisResult?.score,
    readObjectField(report, ['summary', 'score']),
    readObjectField(rawDashboard, ['summary', 'score']),
  ]));

  return {
    action: normalizeDecisionAction(firstMeaningfulValue([
      traceFields.action?.value,
      titleSignalText,
      summaryPanel?.operationAdvice,
      standardReport?.decisionPanel?.keyAction,
      analysisResult?.action,
      analysisResult?.decision,
      report.summary.sentimentLabel,
      report.summary.operationAdvice,
      readObjectField(rawDashboard, ['summary', 'operation_advice']),
    ]), locale),
    score,
    confidence: firstMeaningfulValue([
      traceFields.confidence?.value,
      decisionPanel?.confidence,
      analysisResult?.confidence,
      analysisResult?.confidenceLevel,
      readObjectField(rawDashboard, ['summary', 'confidence']),
    ]),
    entry: firstMeaningfulValue([
      traceFields.entry?.value,
      decisionPanel?.idealEntry,
      decisionPanel?.support,
      report.strategy?.idealBuy,
      findBattlePlanValue(standardReport, ['entry', 'ideal', '理想', '建仓', '入场']),
      analysisResult?.entryPrice,
      analysisResult?.secondaryEntryPrice,
    ]),
    target: firstMeaningfulValue([
      traceFields.target?.value,
      decisionPanel?.target,
      decisionPanel?.targetZone,
      report.strategy?.takeProfit,
      findBattlePlanValue(standardReport, ['target', '目标']),
      analysisResult?.takeProfit,
    ]),
    stop: firstMeaningfulValue([
      traceFields.stop?.value,
      decisionPanel?.stopLoss,
      report.strategy?.stopLoss,
      findBattlePlanValue(standardReport, ['stop', '止损']),
      analysisResult?.stopLoss,
    ]),
    summary: firstMeaningfulValue([
      titleOneSentence,
      summaryPanel?.oneSentence,
      report.summary.analysisSummary,
      analysisResult?.summary,
      reasonLayer?.latestKeyUpdate,
    ]),
    scoreContext: firstMeaningfulValue([
      decisionContext?.shortTermView,
      summaryPanel?.trendPrediction,
      titleTrendPrediction,
      report.summary.trendPrediction,
      report.summary.operationAdvice,
      analysisResult?.strategy,
    ]),
    badge: firstMeaningfulValue([
      summaryPanel?.operationAdvice,
      titleOperationAdvice,
      reasonLayer?.topCatalyst,
      reasonLayer?.newsValueTier,
    ]),
    reason: firstMeaningfulValue([
      titleOneSentence,
      summaryPanel?.oneSentence,
      report.summary.analysisSummary,
      analysisResult?.fullReasoning,
      reasonLayer?.coreReasons?.[0],
      reasonLayer?.topCatalyst,
      reasonLayer?.latestKeyUpdate,
    ]),
    positionBody: firstMeaningfulValue([
      decisionPanel?.buildStrategy,
      decisionPanel?.holderAdvice,
      decisionPanel?.noPositionAdvice,
      readObjectField(rawDashboard, ['coreConclusion', 'positionAdvice', 'noPosition']),
      readObjectField(rawDashboard, ['coreConclusion', 'positionAdvice', 'hasPosition']),
      report.summary.operationAdvice,
    ]),
    technicalFields,
    fundamentalFields: standardReport?.fundamentalFields || standardReport?.tableSections?.fundamental?.fields,
  };
}

const DASHBOARD_VARIANTS: Record<DashboardLocale, Record<string, DashboardVariant>> = {
  zh: {
    NVDA: {
      ...CONTENT.zh,
    },
    ORCL: {
      ...CONTENT.zh,
      instrument: '甲骨文',
      ticker: 'ORCL',
      sessionBadge: '企业软件云',
      regimeBadge: '平台上修',
      decision: {
        ...CONTENT.zh.decision,
        company: '甲骨文',
        heroValue: '7.8',
        signalLabel: '有条件观察',
        signalTone: 'bullish',
        scoreValue: '财报驱动后维持上沿强势',
        badge: '云订单抬升 · 企业 IT 预算回流',
        chartLabel: '平台上破',
        summary: '云业务订单与数据库续费提供中线托底，回踩不破时更适合继续观察确认。',
        reasonBody: '财报后资金没有快速撤离，价格保持在前高之上，企业软件主线继续提供趋势支撑。',
      },
      strategy: {
        ...CONTENT.zh.strategy,
        metrics: [
          { label: '观察区间', value: '121.80 - 124.60', tone: 'neutral' },
          { label: '上方观察区', value: '133.50', tone: 'bullish' },
          { label: '风险失效线', value: '117.40', tone: 'bearish' },
        ],
        positionBody: '先观察财报后的强势平台是否保持，确认回踩缩量后再提高关注级别。',
      },
      tech: {
        ...CONTENT.zh.tech,
        signals: [
          { label: '均线结构', value: '多头排列', tone: 'bullish' },
          { label: 'RSI-14', value: '61.2 (强势区)', tone: 'neutral' },
          { label: 'MACD', value: '零轴上方二次扩张', tone: 'bullish' },
          { label: '量价动态', value: '突破后量能维持', tone: 'bullish' },
        ],
      },
      fundamentals: {
        ...CONTENT.zh.fundamentals,
        metrics: [
          { label: 'ROE', value: '109.3%', tone: 'bullish' },
          { label: 'EBITDA 利润率', value: '46.1%', tone: 'bullish' },
          { label: '最新 EPS', value: '$1.47 (超预期 +9%)', tone: 'bullish' },
          { label: '营收', value: '$14.1B (超预期 +3%)', tone: 'bullish' },
          { label: '预期 P/E', value: '31.2x', tone: 'neutral' },
          { label: 'PEG 比率', value: '1.08', tone: 'neutral' },
        ],
      },
    },
    TSLA: {
      ...CONTENT.zh,
      instrument: '特斯拉',
      ticker: 'TSLA',
      sessionBadge: '高波动成长',
      regimeBadge: '反弹验证',
      decision: {
        ...CONTENT.zh.decision,
        company: '特斯拉',
        heroValue: '6.9',
        signalLabel: '等待确认',
        signalTone: 'neutral',
        scoreValue: '事件驱动后仍需量能确认',
        badge: '波动放大 · 需要二次确认',
        chartLabel: '反弹测试',
        summary: '价格快速反抽后进入验证区，若量能跟不上，更适合等待第二次确认。',
        reasonBody: '高波动资产的反弹更多依赖事件催化，当前结构尚未给出完全顺滑的趋势延续信号。',
      },
      strategy: {
        ...CONTENT.zh.strategy,
        metrics: [
          { label: '观察区间', value: '166.00 - 171.50', tone: 'neutral' },
          { label: '上方观察区', value: '183.00', tone: 'bullish' },
          { label: '风险失效线', value: '159.20', tone: 'bearish' },
        ],
        positionBody: '只在确认量能延续时提高关注级别，否则保持试错假设，避免在事件回落中被动扩大风险。',
      },
      tech: {
        ...CONTENT.zh.tech,
        signals: [
          { label: '均线结构', value: '跌破 MA60', tone: 'bearish' },
          { label: 'RSI-14', value: '54.8 (修复区)', tone: 'neutral' },
          { label: 'MACD', value: '零轴下方收敛', tone: 'neutral' },
          { label: '量价动态', value: '反弹放量，续航待定', tone: 'neutral' },
        ],
      },
      fundamentals: {
        ...CONTENT.zh.fundamentals,
        metrics: [
          { label: 'ROE', value: '18.9%', tone: 'neutral' },
          { label: 'EBITDA 利润率', value: '12.8%', tone: 'bearish' },
          { label: '最新 EPS', value: '$0.52 (不及预期 -6%)', tone: 'bearish' },
          { label: '营收', value: '$25.2B (不及预期 -2%)', tone: 'neutral' },
          { label: '预期 P/E', value: '55.8x', tone: 'neutral' },
          { label: 'PEG 比率', value: '2.04', tone: 'bearish' },
        ],
      },
    },
  },
  en: {
    NVDA: {
      ...CONTENT.en,
    },
    ORCL: {
      ...CONTENT.en,
      instrument: 'Oracle',
      ticker: 'ORCL',
      sessionBadge: 'Enterprise cloud software',
      regimeBadge: 'Platform bid',
      decision: {
        ...CONTENT.en.decision,
        company: 'Oracle',
        heroValue: '7.8',
        signalLabel: 'Constructive',
        signalTone: 'bullish',
        scoreValue: 'Post-earnings strength still holds the upper rail',
        badge: 'Cloud demand lift · enterprise budgets returning',
        chartLabel: 'Platform Break',
        summary: 'Cloud backlog and database renewals keep the medium-term floor intact, so pullbacks remain the cleaner way to participate.',
        reasonBody: 'Post-earnings sponsorship has not faded quickly, price is holding above the prior ceiling, and enterprise software remains a clean trend anchor.',
      },
      strategy: {
        ...CONTENT.en.strategy,
        metrics: [
          { label: 'Watch Zone', value: '121.80 - 124.60', tone: 'neutral' },
          { label: 'Upper Watch Zone', value: '133.50', tone: 'bullish' },
          { label: 'Invalidation Line', value: '117.40', tone: 'bearish' },
        ],
        positionBody: 'Start light into the earnings-led base, then add only if the pullback stays orderly on lighter volume.',
      },
      tech: {
        ...CONTENT.en.tech,
        signals: [
          { label: 'MA ALIGNMENT', value: 'Bullish Alignment', tone: 'bullish' },
          { label: 'RSI-14', value: '61.2 (Strong Zone)', tone: 'neutral' },
          { label: 'MACD', value: 'Second Expansion Above Zero', tone: 'bullish' },
          { label: 'VOLUME DYNAMICS', value: 'Breakout Volume Intact', tone: 'bullish' },
        ],
      },
      fundamentals: {
        ...CONTENT.en.fundamentals,
        metrics: [
          { label: 'ROE', value: '109.3%', tone: 'bullish' },
          { label: 'EBITDA MARGIN', value: '46.1%', tone: 'bullish' },
          { label: 'LATEST EPS', value: '$1.47 (Beat +9%)', tone: 'bullish' },
          { label: 'REVENUE', value: '$14.1B (Beat +3%)', tone: 'bullish' },
          { label: 'FORWARD PE', value: '31.2x', tone: 'neutral' },
          { label: 'PEG RATIO', value: '1.08', tone: 'neutral' },
        ],
      },
    },
    TSLA: {
      ...CONTENT.en,
      instrument: 'Tesla',
      ticker: 'TSLA',
      sessionBadge: 'High-beta growth',
      regimeBadge: 'Bounce validation',
      decision: {
        ...CONTENT.en.decision,
        company: 'Tesla',
        heroValue: '6.9',
        signalLabel: 'Neutral to bullish',
        signalTone: 'neutral',
        scoreValue: 'Catalyst bounce still needs volume confirmation',
        badge: 'Volatility expansion · second confirmation needed',
        chartLabel: 'Bounce Test',
        summary: 'Price snapped back fast but is still in a proof zone, so the cleaner move is to wait for a second confirmation instead of chasing the first spike.',
        reasonBody: 'This rebound is still highly event-driven, and the structure has not yet converted into a smooth trend continuation setup.',
      },
      strategy: {
        ...CONTENT.en.strategy,
        metrics: [
          { label: 'Watch Zone', value: '166.00 - 171.50', tone: 'neutral' },
          { label: 'Upper Watch Zone', value: '183.00', tone: 'bullish' },
          { label: 'Invalidation Line', value: '159.20', tone: 'bearish' },
        ],
        positionBody: 'Add only when follow-through volume confirms. Otherwise keep risk in probe size and avoid forcing size into a news-driven retrace.',
      },
      tech: {
        ...CONTENT.en.tech,
        signals: [
          { label: 'MA ALIGNMENT', value: 'Below MA60', tone: 'bearish' },
          { label: 'RSI-14', value: '54.8 (Repair Zone)', tone: 'neutral' },
          { label: 'MACD', value: 'Compression Below Zero', tone: 'neutral' },
          { label: 'VOLUME DYNAMICS', value: 'Bounce Expanded, Follow-through Pending', tone: 'neutral' },
        ],
      },
      fundamentals: {
        ...CONTENT.en.fundamentals,
        metrics: [
          { label: 'ROE', value: '18.9%', tone: 'neutral' },
          { label: 'EBITDA MARGIN', value: '12.8%', tone: 'bearish' },
          { label: 'LATEST EPS', value: '$0.52 (Miss -6%)', tone: 'bearish' },
          { label: 'REVENUE', value: '$25.2B (Miss -2%)', tone: 'neutral' },
          { label: 'FORWARD PE', value: '55.8x', tone: 'neutral' },
          { label: 'PEG RATIO', value: '2.04', tone: 'bearish' },
        ],
      },
    },
  },
};

const TICKER_ALIASES: Record<string, string> = {
  NVIDIA: 'NVDA',
  '英伟达': 'NVDA',
  ORACLE: 'ORCL',
  '甲骨文': 'ORCL',
  TESLA: 'TSLA',
  '特斯拉': 'TSLA',
};

function normalizeTickerQuery(rawValue?: string): string {
  const trimmed = String(rawValue || '').trim();
  if (!trimmed) {
    return '';
  }

  return TICKER_ALIASES[trimmed.toUpperCase()] || TICKER_ALIASES[trimmed] || trimmed.toUpperCase();
}

function parseHomeChartPrice(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number(value.replace(/[%,$\s]/g, ''));
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function readHomePriceContextHint(report: HomePriceContextReport, stockCode: string): string {
  const standardReport = report.details?.standardReport;
  const values = [
    stockCode,
    report.decisionTrace?.market,
    readObjectField(report, ['meta', 'market']),
    readObjectField(report, ['meta', 'currency']),
    readObjectField(standardReport, ['summaryPanel', 'market']),
    readObjectField(standardReport, ['summaryPanel', 'currency']),
    readObjectField(standardReport, ['summaryPanel', 'priceLabel']),
    readObjectField(standardReport, ['summaryPanel', 'priceContextNote']),
    readObjectField(standardReport, ['market', 'currency']),
  ];
  return values.flatMap((value) => { const v = String(value || '').trim(); return v ? [v] : []; }).join(' ');
}

function resolveHomePriceDisplayContext(report: HomePriceContextReport, stockCode: string): HomePriceDisplayContext {
  const hint = readHomePriceContextHint(report, stockCode).toLowerCase();
  const code = stockCode.trim().toUpperCase();
  const cryptoUnit = hint.match(/\b(USDT|USDC|BTC|ETH|USD)\b/i)?.[1]?.toUpperCase();

  if (/crypto|bitcoin|ethereum|数字货币|加密|usdt|usdc|btc|eth/.test(hint)) {
    return { currency: 'crypto', cryptoUnit };
  }
  if (/\b(hk|hkd|hong kong)\b|港股|港元|^hk\d+/i.test(hint) || /^HK\d{4,5}$/i.test(code) || /^\d{4,5}\.HK$/i.test(code)) {
    return { currency: 'hkd' };
  }
  if (/\b(cn|cny|rmb|sh|sz)\b|人民币|a股|沪|深/i.test(hint) || /^\d{6}(?:\.(?:SH|SZ))?$/.test(code)) {
    return { currency: 'cny' };
  }
  if (/\b(us|usa|usd|nyse|nasdaq|amex)\b|美元|美股/.test(hint) || /^[A-Z]{1,5}(?:[.-][A-Z])?$/.test(code)) {
    return { currency: 'usd' };
  }
  return { currency: 'unknown' };
}

function formatHomePriceNumber(
  value: number,
  locale: DashboardLocale,
  context: HomePriceDisplayContext,
  includeNeutralPrefix: boolean,
): string {
  const formatted = value.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  if (context.currency === 'usd') {
    return `$${formatted}`;
  }
  if (context.currency === 'cny') {
    return `${formatted} 元`;
  }
  if (context.currency === 'hkd') {
    return `${formatted} 港元`;
  }
  if (context.currency === 'crypto') {
    return context.cryptoUnit ? `${formatted} ${context.cryptoUnit}` : formatted;
  }
  return includeNeutralPrefix ? `${locale === 'en' ? 'Price' : '价格'} ${formatted}` : formatted;
}

function formatHomePriceLevelValue(
  locale: DashboardLocale,
  raw: string | undefined,
  context: HomePriceDisplayContext,
  fallback: string,
): string {
  const value = sanitizeMetricValue(raw);
  if (!value || value === EMPTY_FIELD_VALUE) {
    return fallback;
  }

  const noteMatch = value.match(/[（(].*$/);
  const note = noteMatch?.[0] || '';
  const priceSegment = noteMatch?.index !== undefined ? value.slice(0, noteMatch.index).trim() : value;
  const matches = priceSegment.match(/(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?/g) || [];
  if (!matches.length) {
    return value;
  }

  const isRange = matches.length > 1 || /[-~至到–—]/.test(priceSegment);
  const numbers = matches
    .slice(0, isRange ? 2 : 1)
    .reduce<number[]>((acc, item) => {
      const n = Number.parseFloat(item.replace(/,/g, ''));
      if (Number.isFinite(n)) acc.push(n);
      return acc;
    }, []);
  if (!numbers.length) {
    return value;
  }

  const formatted = numbers
    .map((item, index) => formatHomePriceNumber(item, locale, context, index === 0))
    .join(' - ');
  return `${formatted}${note ? note : ''}`;
}

function polishHomeNarrativeCopy(locale: DashboardLocale, raw: string, context: HomePriceDisplayContext): string {
  const value = String(raw || '').trim();
  if (!value || value === EMPTY_FIELD_VALUE) {
    return value;
  }

  const pricePattern = /((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*元/g;
  const relabeledCurrency = context.currency === 'cny'
    ? value
    : value
      .replace(new RegExp(`(股价|价格|价位)\\s*${pricePattern.source}`, 'g'), (_match, label: string, numeric: string) => {
        const parsed = Number.parseFloat(numeric.replace(/,/g, ''));
        return Number.isFinite(parsed)
          ? `${label}${formatHomePriceNumber(parsed, locale, context, false)}`
          : _match;
      })
      .replace(pricePattern, (_match, numeric: string) => {
        const parsed = Number.parseFloat(numeric.replace(/,/g, ''));
        return Number.isFinite(parsed)
          ? formatHomePriceNumber(parsed, locale, context, true)
          : _match;
      });

  if (locale === 'en') {
    return relabeledCurrency
      .replace(/\brecommend(?:s|ed|ation)?\b/gi, 'research note')
      .replace(/\bguaranteed\b/gi, 'unconfirmed');
  }

  return relabeledCurrency
    .replace(/建议观望等待/g, '当前仍以观察为主，等待')
    .replace(/建议继续观望/g, '当前结论仍是继续观察')
    .replace(/建议观望/g, '当前结论仍是观察')
    .replace(/建议等待/g, '当前仍需等待')
    .replace(/建议/g, '研究提示');
}

function formatHistoryTimestamp(value?: string, locale: DashboardLocale = 'zh'): string {
  const text = String(value || '').trim();
  if (!text) {
    return '';
  }

  const date = new Date(text);
  if (Number.isNaN(date.getTime())) {
    return text;
  }

  const parts = (locale === 'en' ? HISTORY_TIMESTAMP_FMT_EN : HISTORY_TIMESTAMP_FMT_ZH).formatToParts(date);
  const get = (type: string) => parts.find((part) => part.type === type)?.value || '';
  return `${get('month')}/${get('day')} ${get('hour')}:${get('minute')}`;
}

function resolveHistoryGeneratedAt(historyItem: HistoryItem, locale: DashboardLocale): string {
  return formatHistoryTimestamp(historyItem.generatedAt || historyItem.createdAt, locale);
}

function resolveHistoryCompanyLabel(historyItem: HistoryItem): string {
  return getCompanyWithTicker(historyItem);
}

function buildInPlacePlaceholderDashboard(
  locale: DashboardLocale,
  ticker?: string | null,
): DashboardPayload {
  const normalizedTicker = normalizeTickerQuery(ticker ?? undefined) || DEFAULT_HOME_TICKER;
  const base = DASHBOARD_VARIANTS[locale].NVDA;
  const companyProfile = resolveCompanyProfile(normalizedTicker);
  const neutralStrategyMetrics = neutralizeDashboardFields(base.strategy.metrics);
  const neutralTechSignals = neutralizeDashboardSignals(base.tech.signals);
  const neutralFundamentals = neutralizeDashboardFields(base.fundamentals.metrics);

  return enrichDashboardPayload(locale, {
    ...base,
    instrument: normalizedTicker,
    ticker: normalizedTicker,
    decision: {
      ...base.decision,
      company: companyProfile.company,
      sector: companyProfile.sector,
      heroValue: EMPTY_FIELD_VALUE,
      heroUnit: '',
      heroLabel: locale === 'en' ? 'Status' : '当前状态',
      signalLabel: EMPTY_FIELD_VALUE,
      signalTone: 'neutral',
      scoreLabel: locale === 'en' ? 'Signal Direction' : '信号方向',
      scoreValue: EMPTY_FIELD_VALUE,
      badge: EMPTY_FIELD_VALUE,
      chartLabel: EMPTY_FIELD_VALUE,
      summary: EMPTY_FIELD_VALUE,
      reasonBody: EMPTY_FIELD_VALUE,
    },
    strategy: {
      ...base.strategy,
      metrics: neutralStrategyMetrics,
      positionBody: EMPTY_FIELD_VALUE,
    },
    tech: {
      ...base.tech,
      signals: neutralTechSignals,
    },
    fundamentals: {
      ...base.fundamentals,
      metrics: neutralFundamentals,
    },
  });
}

function toneFromScore(score?: number): SignalTone {
  if (typeof score !== 'number') {
    return 'neutral';
  }

  if (score >= 70) {
    return 'bullish';
  }

  if (score <= 40) {
    return 'bearish';
  }

  return 'neutral';
}

function toneFromFieldValue(value?: string): SignalTone {
  const normalized = String(value || '').toLowerCase();
  if (/(bull|up|break|expand|strong|beat|above|lifting|乐观|偏多|看多|金叉|上行|突破|超预期)/.test(normalized)) {
    return 'bullish';
  }
  if (/(bear|down|weak|risk|fall|miss|below|悲观|看空|下压|回落|破位|不及预期)/.test(normalized)) {
    return 'bearish';
  }
  return 'neutral';
}

const REPORT_TEXT_EN_BY_KEY: Record<string, string> = {
  中性偏多: 'Neutral to bullish',
  乐观: 'Bullish',
  偏多: 'Constructive',
  回踩支撑确认: 'Pullback support confirmed',
  字段待接入: 'field pending',
  技术失效位: 'Technical invalidation',
  持有: 'Hold',
  技术面与基本面相互印证综合建议以持有为主: 'Technical and fundamental signals align, so the composite stance remains Hold.',
  持有技术结构价格仍位于ma20上方防守位在17548近期支撑ma簇一带若回踩企稳趋势延续概率更高方向偏多置信度中: 'Hold · Structure still sits above MA20, with defense near 175.48 (recent support / MA cluster). Trend continuation improves if the pullback stabilizes, and the directional bias remains constructive with medium conviction.',
  理想做法是回踩支撑簇小仓试错若站回ma5ma10再做第二笔: 'Start with probe size on a pullback into the support cluster, then add only if price reclaims MA5 and MA10.',
  短线技术偏强均线结构偏强价格位于ma20上方价格位于ma60上方: 'Short-term technical posture remains constructive, with price holding above both MA20 and MA60.',
  目标区间: 'Target zone',
  近期支撑ma簇: 'recent support / MA cluster',
};

function convertChineseUnits(value: string): string {
  return value
    .replace(/(\d+(?:\.\d+)?)亿/g, (_, amount: string) => `${(Number(amount) / 10).toFixed(Number(amount) >= 100 ? 2 : 1).replace(/\.0$/, '')}B`)
    .replace(/(\d+(?:\.\d+)?)万/g, (_, amount: string) => `${(Number(amount) / 100).toFixed(Number(amount) >= 1000 ? 1 : 2).replace(/\.0$/, '')}M`);
}

function replaceEnglishFragments(raw: string): string {
  return raw
    .replace(/分析过程出错[:：]\s*/g, 'Analysis process hit an error: ')
    .replace(/NA[（(]字段待接入[）)]/g, 'N/A (field pending)')
    .replace(/[（(]回踩支撑确认[）)]/g, ' (Pullback support confirmed)')
    .replace(/[（(]目标区间[）)]/g, ' (Target zone)')
    .replace(/[（(]技术失效位[）)]/g, ' (Technical invalidation)');
}

function localizeSentimentLabel(locale: DashboardLocale, raw: string | undefined, fallback: string): string {
  const value = String(raw || '').trim();
  if (!value) {
    return fallback;
  }
  if (locale === 'zh') {
    return value;
  }
  return REPORT_TEXT_EN_BY_KEY[normalizeDetailKey(value)] || (containsCjk(value) ? fallback : value);
}

function localizeMetricValue(locale: DashboardLocale, raw: string | undefined, fallback: string): string {
  const value = sanitizeMetricValue(raw);
  if (!value) {
    return fallback;
  }
  if (value === '-') {
    return '-';
  }
  if (locale === 'zh') {
    return value;
  }
  const exact = REPORT_TEXT_EN_BY_KEY[normalizeDetailKey(value)];
  if (exact) {
    return exact;
  }
  const localized = convertChineseUnits(replaceEnglishFragments(value)).replace(/\s+/g, ' ').trim();
  if (!containsCjk(localized)) {
    return localized;
  }
  return fallback;
}

function localizeNarrativeText(locale: DashboardLocale, raw: string | undefined, fallback: string): string {
  const value = String(raw || '').trim();
  if (!value) {
    return fallback;
  }
  if (/all llm models failed|ratelimiterror|分析过程出错/i.test(value)) {
    return fallback;
  }
  if (locale === 'zh') {
    if (!containsCjk(value)) {
      if (/fixture result only; not investment advice/i.test(value)) {
        return '固定样例仅用于界面验证，不代表实时研究结论。';
      }
      if (/orcl is waiting .*controlled pullback/i.test(value)) {
        return '固定样例显示仍需等待回踩和量能证据。';
      }
      if (/momentum is mixed/i.test(value)) {
        return '动量信号分歧，仍需量能确认。';
      }
      if (/rule-stabilized/i.test(value)) {
        return '规则层将该样例保持在等待复核状态。';
      }
      if (/fundamental data intentionally incomplete/i.test(value)) {
        return '基本面数据刻意保持不完整。';
      }
      if (/fixture keeps deterministic/i.test(value)) {
        return '该样例用于固定浏览器验证，不依赖实时提供商。';
      }
      if (/data source states include/i.test(value)) {
        return '数据来源包含可用、缺失与未知状态。';
      }
      if (/no live llm|provider call/i.test(value)) {
        return '该样例不需要实时模型或数据源调用。';
      }
      return value;
    }
    return value;
  }
  const exact = REPORT_TEXT_EN_BY_KEY[normalizeDetailKey(value)];
  if (exact) {
    return exact;
  }
  const localized = convertChineseUnits(replaceEnglishFragments(value)).replace(/\s+/g, ' ').trim();
  if (!containsCjk(localized)) {
    return localized;
  }
  return fallback;
}

function findStandardField(fields: StandardReportField[] | undefined, aliases: string[]): StandardReportField | undefined {
  for (const alias of aliases) {
    const aliasKey = normalizeDetailKey(alias);
    for (const field of (fields || [])) {
      if ((normalizeDetailKey(field.label).includes(aliasKey) || aliasKey.includes(normalizeDetailKey(field.label))) && field?.label) {
        return field;
      }
    }
  }
  return undefined;
}

function findFieldNumber(fields: StandardReportField[] | undefined, label: string): number | null {
  const field = (fields || []).find((item) => normalizeDetailKey(item.label) === normalizeDetailKey(label));
  const numeric = Number.parseFloat(String(field?.value || '').replace(/,/g, ''));
  return Number.isFinite(numeric) ? numeric : null;
}

function deriveMaAlignment(locale: DashboardLocale, fields: StandardReportField[] | undefined): DashboardField | null {
  const ma5 = findFieldNumber(fields, 'MA5');
  const ma10 = findFieldNumber(fields, 'MA10');
  const ma20 = findFieldNumber(fields, 'MA20');
  const ma60 = findFieldNumber(fields, 'MA60');

  if (ma5 === null || ma10 === null || ma20 === null || ma60 === null) {
    return null;
  }

  const isBullish = ma5 > ma10 && ma10 > ma20 && ma20 > ma60;
  const isBearish = ma5 < ma10 && ma10 < ma20 && ma20 < ma60;
  const tone: SignalTone = isBullish ? 'bullish' : isBearish ? 'bearish' : 'neutral';
  const value = locale === 'en'
    ? isBullish
      ? 'Bullish Alignment'
      : isBearish
        ? 'Bearish Alignment'
        : 'Mixed Alignment'
    : isBullish
      ? '多头排列'
      : isBearish
        ? '空头排列'
        : '均线混合';

  return {
    label: locale === 'en' ? 'MA ALIGNMENT' : '均线结构',
    value,
    rawValue: value,
    tone,
    details: value,
  };
}

function localizeDashboardFieldLabel(locale: DashboardLocale, label: string): string {
  if (locale === 'en') {
    return label;
  }

  const key = normalizeDetailKey(label);
  const labels: Record<string, string> = {
    ebitdamargin: 'EBITDA 利润率',
    forwardpe: '预期 P/E',
    latesteps: '最新 EPS',
    maalignment: '均线结构',
    pegratio: 'PEG 比率',
    revenue: '营收',
    revenuegrowth: '收入增速',
    volumedynamics: '量价动态',
    volumeprofile: '量价动态',
  };

  return labels[key] || label;
}

function formatDesiredMetricValue(label: string, value: string): string {
  const normalizedLabel = normalizeDetailKey(label);
  if (normalizedLabel === 'forwardpe' && /^-?\d+(?:\.\d+)?$/.test(value)) {
    return `${value}x`;
  }
  return value;
}

function compactMetricSurprise(value: string): string {
  return String(value || '').replace(/\s*[（(][^）)]*[）)]\s*$/u, '').trim();
}

function readMetricNodeValue(value: unknown): string | undefined {
  if (value === null || value === undefined) {
    return undefined;
  }
  if (typeof value === 'object' && !Array.isArray(value)) {
    const nodeValue = (value as Record<string, unknown>).value;
    if (nodeValue === null || nodeValue === undefined) {
      return undefined;
    }
    return String(nodeValue);
  }
  return String(value);
}

function compactTechSignalValue(locale: DashboardLocale, label: string, value: string): string {
  const compact = compactMetricSurprise(value);
  if (isPendingMetricValue(compact)) {
    return EMPTY_FIELD_VALUE;
  }

  const key = normalizeDetailKey(label);
  if (key === 'rsi14' || key === 'rsi') {
    const numericMatch = compact.match(/-?\d+(?:\.\d+)?/);
    return numericMatch ? numericMatch[0] : compact;
  }

  if (key === 'macd') {
    if (/zero|零轴/.test(compact) && /cross|金叉/.test(compact)) {
      return locale === 'en' ? 'Bullish Cross' : '零轴上金叉';
    }
    if (/zero|零轴/.test(compact) && /compress|收敛/.test(compact)) {
      return locale === 'en' ? 'Below Zero' : '零轴下收敛';
    }
    if (/second expansion|二次扩张/i.test(compact)) {
      return locale === 'en' ? '2nd Expansion' : '二次扩张';
    }
  }

  if (key === 'volumedynamics' || key === 'volumeprofile') {
    if (/high vol breakout|放量突破/i.test(compact)) {
      return locale === 'en' ? 'Breakout Vol' : '放量突破';
    }
    if (/breakout volume intact|突破后量能维持/i.test(compact)) {
      return locale === 'en' ? 'Vol Intact' : '量能维持';
    }
    if (/follow-through pending|续航待定/i.test(compact)) {
      return locale === 'en' ? 'Follow-through Pending' : '续航待定';
    }
  }

  if (key === 'maalignment' || key === 'movingaverages') {
    if (/bullish alignment|多头排列/i.test(compact)) {
      return locale === 'en' ? 'Bullish Alignment' : '多头排列';
    }
    if (/bearish alignment|空头排列/i.test(compact)) {
      return locale === 'en' ? 'Bearish Alignment' : '空头排列';
    }
    if (/mixed alignment|均线混合/i.test(compact)) {
      return locale === 'en' ? 'Mixed Alignment' : '均线混合';
    }
    if (/below ma60|跌破生命线/i.test(compact)) {
      return locale === 'en' ? 'Below MA60' : '跌破 MA60';
    }
    const maComparison = compact.match(/(MA\d+)\s*(?:lifting|above|over|>|站上|高于)\s*(MA\d+)/i);
    if (maComparison) {
      return `${maComparison[1].toUpperCase()} > ${maComparison[2].toUpperCase()}`;
    }
  }

  return compact;
}

function compactFundamentalMetricValue(value: string): string {
  const compact = compactMetricSurprise(value);
  if (String(compact).trim().toUpperCase() === 'N/A') {
    return 'N/A';
  }
  return isPendingMetricValue(compact) ? EMPTY_FIELD_VALUE : compact;
}

function mapDesiredFields(
  locale: DashboardLocale,
  fields: StandardReportField[] | undefined,
  specs: DesiredFieldSpec[],
): DashboardField[] {
  return specs.map((spec) => {
    const field = findStandardField(fields, spec.aliases);
    if (!field) {
      if (normalizeDetailKey(spec.fallback.label) === 'maalignment') {
        return deriveMaAlignment(locale, fields) || spec.fallback;
      }
      return spec.fallback;
    }

    const localizedValue = formatDesiredMetricValue(
      spec.fallback.label,
      localizeMetricValue(locale, field.value, spec.fallback.value || EMPTY_FIELD_VALUE),
    );
    const isEmpty = isPendingMetricValue(localizedValue);
    return {
      ...spec.fallback,
      value: localizedValue,
      rawValue: localizedValue,
      tone: isEmpty ? 'neutral' : toneFromFieldValue(field.value || localizedValue),
      details: isEmpty ? spec.fallback.details : undefined,
    };
  });
}

function compactDashboardSignals(locale: DashboardLocale, signals: DashboardSignal[]): DashboardSignal[] {
  return signals.map((signal) => {
    const compactValue = compactTechSignalValue(locale, signal.label, signal.value);
    return {
      ...signal,
      label: localizeDashboardFieldLabel(locale, signal.label),
      value: compactValue,
      rawValue: signal.rawValue || signal.value,
    };
  });
}

function compactDashboardMetrics(locale: DashboardLocale, metrics: DashboardField[]): DashboardField[] {
  return metrics.map((metric) => {
    const compactValue = compactFundamentalMetricValue(metric.value);
    return {
      ...metric,
      label: localizeDashboardFieldLabel(locale, metric.label),
      value: compactValue,
      rawValue: compactValue,
    };
  });
}

function getTechnicalFieldSpecs(locale: DashboardLocale): DesiredFieldSpec[] {
  const isEnglish = locale === 'en';
  return [
    {
      aliases: ['MA ALIGNMENT', 'Moving Averages', '均线结构', '均线系统', '多头/空头排列'],
      fallback: { label: isEnglish ? 'MA ALIGNMENT' : '均线结构', value: EMPTY_FIELD_VALUE, rawValue: EMPTY_FIELD_VALUE, tone: 'neutral', details: EMPTY_FIELD_VALUE },
    },
    {
      aliases: ['RSI-14', 'RSI14', 'RSI'],
      fallback: { label: 'RSI-14', value: EMPTY_FIELD_VALUE, rawValue: EMPTY_FIELD_VALUE, tone: 'neutral', details: EMPTY_FIELD_VALUE },
    },
    {
      aliases: ['MACD', '趋势与反转'],
      fallback: { label: 'MACD', value: EMPTY_FIELD_VALUE, rawValue: EMPTY_FIELD_VALUE, tone: 'neutral', details: EMPTY_FIELD_VALUE },
    },
    {
      aliases: ['VOLUME DYNAMICS', 'Volume Profile', '量价配合', '量价判断', '成交量', 'Volume'],
      fallback: {
        label: isEnglish ? 'VOLUME DYNAMICS' : '量价动态',
        value: EMPTY_FIELD_VALUE,
        rawValue: EMPTY_FIELD_VALUE,
        tone: 'neutral',
        details: isEnglish ? 'Volume signal pending' : '量价信号待接入',
      },
    },
  ];
}

function getFundamentalFieldSpecs(locale: DashboardLocale): DesiredFieldSpec[] {
  const isEnglish = locale === 'en';
  return [
    {
      aliases: ['ROE', '净资产收益率'],
      fallback: { label: 'ROE', value: EMPTY_FIELD_VALUE, rawValue: EMPTY_FIELD_VALUE, tone: 'neutral', details: EMPTY_FIELD_VALUE },
    },
    {
      aliases: ['EBITDA Margin', 'EBITDA MARGIN', 'EBITDA利润率'],
      fallback: { label: isEnglish ? 'EBITDA MARGIN' : 'EBITDA 利润率', value: EMPTY_FIELD_VALUE, rawValue: EMPTY_FIELD_VALUE, tone: 'neutral', details: EMPTY_FIELD_VALUE },
    },
    {
      aliases: ['Latest EPS', 'LATEST EPS', 'EPS', '最新季报'],
      fallback: { label: isEnglish ? 'LATEST EPS' : '最新 EPS', value: EMPTY_FIELD_VALUE, rawValue: EMPTY_FIELD_VALUE, tone: 'neutral', details: EMPTY_FIELD_VALUE },
    },
    {
      aliases: ['Revenue', 'Revenue Growth', '营收', '收入增速'],
      fallback: { label: isEnglish ? 'REVENUE' : '营收', value: EMPTY_FIELD_VALUE, rawValue: EMPTY_FIELD_VALUE, tone: 'neutral', details: EMPTY_FIELD_VALUE },
    },
    {
      aliases: ['Forward PE', 'Forward P/E', '远期市盈率', '预期市盈率', 'PE一致预期'],
      fallback: { label: isEnglish ? 'FORWARD PE' : '预期 P/E', value: isEnglish ? 'N/A' : 'N/A', rawValue: 'N/A', tone: 'neutral', details: 'N/A' },
    },
    {
      aliases: ['PEG Ratio', 'PEG RATIO', 'PEG'],
      fallback: { label: isEnglish ? 'PEG RATIO' : 'PEG 比率', value: 'N/A', rawValue: 'N/A', tone: 'neutral', details: 'N/A' },
    },
  ];
}

function buildTechSignalDetails(locale: DashboardLocale, ticker: string, label: string, value: string): string {
  const key = normalizeDetailKey(label);
  const rawValue = sanitizeMetricValue(value);
  const isEnglish = locale === 'en';

  if (rawValue === '-' || rawValue === 'N/A') {
    return rawValue;
  }

  if (key === 'macd') {
    if (ticker === 'TSLA') {
      return isEnglish
        ? 'Below zero; downside momentum is fading.'
        : '零轴下方，空头动能衰减。';
    }
    if (ticker === 'ORCL') {
      return isEnglish
        ? 'Above zero and re-accelerating.'
        : '零轴上方，动能再扩张。';
    }
    return isEnglish
      ? 'Bullish cross above zero.'
      : '零轴上方金叉延续。';
  }

  if (key === '均线结构' || key === 'movingaverages' || key === 'ma20ma60') {
    if (ticker === 'TSLA') {
      return isEnglish
        ? 'MA20 still caps the rebound.'
        : 'MA20 仍压制反弹。';
    }
    return isEnglish
      ? 'Short-term MA leads higher.'
      : '短期均线牵引上行。';
  }

  if (key === '量价配合' || key === 'volumeprofile') {
    if (ticker === 'TSLA') {
      return isEnglish
        ? 'Volume rebound needs follow-through.'
        : '反弹放量，续航待确认。';
    }
    return isEnglish
      ? 'Pullback volume contracted; breakout volume expanded.'
      : '回踩缩量，突破放量。';
  }

  if (key === 'rsi') {
    return isEnglish
      ? `RSI ${rawValue}, firm but not exhausted.`
      : `RSI ${rawValue}，强势未透支。`;
  }

  if (key === '波动率' || key === 'volatility') {
    return isEnglish
      ? `Realized vol ${rawValue}; keep risk bands wide.`
      : `波动率 ${rawValue}，风险带放宽。`;
  }

  return rawValue;
}

function buildFundamentalMetricDetails(locale: DashboardLocale, ticker: string, label: string, value: string): string {
  const key = normalizeDetailKey(label);
  if (String(value || '').trim().toUpperCase() === 'N/A') {
    return 'N/A';
  }
  const rawValue = sanitizeMetricValue(value);
  const isEnglish = locale === 'en';

  if (rawValue === '-') {
    return '-';
  }

  if (key === '收入增速' || key === 'revenuegrowth') {
    if (ticker === 'TSLA') {
      return isEnglish
        ? 'Auto delivery growth is slowing and that is capping the top-line pace, while the higher-margin energy storage line is carrying a larger share of the earnings support.'
        : '汽车交付量放缓拖累整体营收增速，但储能业务的高毛利贡献正在抬升，对冲了汽车主业的增速压力。';
    }
    return isEnglish
      ? `Revenue growth is running at ${rawValue}, which still supports the current thesis as long as demand conversion remains ahead of cost pressure.`
      : `收入增速为 ${rawValue}，只要需求兑现继续快于成本压力，这个读数就仍然支撑当前主线判断。`;
  }

  if (key === '自由现金流' || key === 'freecashflow') {
    return isEnglish
      ? `Free cash flow at ${rawValue} keeps financing pressure contained and gives the company room to absorb volatility without breaking the medium-term thesis.`
      : `自由现金流达到 ${rawValue}，说明公司仍有能力承受阶段波动，不至于因为融资压力打断中期逻辑。`;
  }

  if (key === '毛利率' || key === 'grossmargin') {
    return isEnglish
      ? `Gross margin at ${rawValue} is the cleanest read on pricing power versus cost pressure, so this line is critical for validating whether the earnings base is expanding or compressing.`
      : `毛利率为 ${rawValue}，这是检验定价权和成本压力最直接的指标，决定利润底盘是在扩张还是收缩。`;
  }

  if (key === 'roe') {
    return isEnglish
      ? `ROE at ${rawValue} measures how efficiently equity is being converted into earnings, which matters for judging whether the current valuation premium has operating support.`
      : `ROE 为 ${rawValue}，反映股东权益转化为利润的效率，用来判断当前估值溢价是否有经营效率支撑。`;
  }

  if (key === '市盈率pe' || key === 'pe') {
    return isEnglish
      ? `A PE of ${rawValue} means the market is still paying for forward growth; unless growth durability improves, the rerating room stays bounded.`
      : `市盈率约为 ${rawValue}，说明市场仍在为未来成长付费；如果增长持续性没有继续抬升，估值扩张空间会受到约束。`;
  }

  if (key === '机构持仓' || key === 'institutionalownership') {
    return isEnglish
      ? `Institutional ownership at ${rawValue} helps gauge sponsorship stability; higher stickiness usually lowers the probability of purely retail-driven air pockets.`
      : `机构持仓约为 ${rawValue}，用来判断筹码稳定性；机构黏性越高，纯情绪性踩踏的概率通常越低。`;
  }

  return isEnglish
    ? `${label} is currently ${rawValue}, and the supporting note should remain attached to that same fundamental observation.`
    : `${label} 当前为 ${rawValue}，支撑说明需要继续绑定在这条基本面观测本身。`;
}

function buildStrategyMetricDetails(locale: DashboardLocale, label: string, value: string): string {
  const key = normalizeDetailKey(label);
  const rawValue = sanitizeMetricValue(value);
  const isEnglish = locale === 'en';

  if (rawValue === EMPTY_FIELD_VALUE) {
    return EMPTY_FIELD_VALUE;
  }

  if (key === '观察区间' || key === '建仓区间' || key === 'entryzone' || key === 'watchzone') {
    return isEnglish
      ? `Use ${value} as the preferred observation band. Treat it as a readiness condition, not an instruction.`
      : `以 ${value} 作为优先观察带，只有当日内结构维持有序、没有失控放量时，才提高关注级别。`;
  }

  if (key === '上方观察区' || key === '目标位' || key === 'target') {
    return isEnglish
      ? `${value} maps to the next supply zone or rerating band, so the observation thesis should be reassessed near that area.`
      : `${value} 对应下一层压力带或估值修复上沿，价格接近该区间时要重新评估观察假设。`;
  }

  if (key === '风险失效线' || key === '止损位' || key === 'stop') {
    return isEnglish
      ? `${value} is the structure invalidation line. A decisive break means the thesis should be reviewed from scratch.`
      : `${value} 是结构失效线；一旦有效跌破，应该重新评估分析假设。`;
  }

  return isEnglish
    ? `${label} is currently set to ${value}, and the analysis should keep that same constraint visible.`
    : `${label} 当前设定为 ${value}，分析层需要继续保留这一条约束。`;
}

function enrichDashboardPayload(locale: DashboardLocale, payload: DashboardVariant | DashboardPayload): DashboardPayload {
  return {
    ...payload,
    strategy: {
      ...payload.strategy,
      metrics: payload.strategy.metrics.map((metric) => ({
        ...metric,
        details: metric.details || buildStrategyMetricDetails(locale, metric.label, metric.value),
      })),
    },
    tech: {
      ...payload.tech,
      signals: payload.tech.signals.map((signal) => ({
        ...signal,
        rawValue: signal.rawValue || signal.value,
        details: signal.details || buildTechSignalDetails(locale, payload.ticker, signal.label, signal.rawValue || signal.value),
      })),
    },
    fundamentals: {
      ...payload.fundamentals,
      metrics: payload.fundamentals.metrics.map((metric) => ({
        ...metric,
        rawValue: metric.rawValue || metric.value,
        details: metric.details || buildFundamentalMetricDetails(locale, payload.ticker, metric.label, metric.rawValue || metric.value),
      })),
    },
  };
}

function buildDrawerPayload(locale: DashboardLocale, dashboard: DashboardPayload, drawerKey: DetailDrawerKey): DrawerPayload {
  const isEnglish = locale === 'en';
  const titleMap: Record<DetailDrawerKey, string> = {
    decision: isEnglish ? `${dashboard.ticker} Decision Drill-down` : `${dashboard.ticker} 决策下钻`,
    strategy: isEnglish ? `${dashboard.ticker} Observation Drill-down` : `${dashboard.ticker} 观察下钻`,
    tech: isEnglish ? `${dashboard.ticker} Technical Drill-down` : `${dashboard.ticker} 技术下钻`,
    fundamentals: isEnglish ? `${dashboard.ticker} Fundamental Drill-down` : `${dashboard.ticker} 基本面下钻`,
  };

  if (drawerKey === 'decision') {
    return {
      title: titleMap.decision,
      modules: [
        {
          id: 'decision',
          eyebrow: dashboard.decision.eyebrow,
          title: isEnglish ? 'Supporting Evidence' : '支撑证据',
          metrics: [
            {
              label: isEnglish ? 'Signal Bias' : '信号方向',
              value: dashboard.decision.signalLabel,
              details: dashboard.decision.scoreValue,
              tone: dashboard.decision.signalTone,
              glow: true,
            },
            {
              label: isEnglish ? 'Analysis Thesis' : '分析主线',
              value: dashboard.decision.summary,
              details: dashboard.decision.reasonBody,
              tone: 'neutral',
            },
            {
              label: isEnglish ? 'Catalyst Tag' : '催化标签',
              value: dashboard.decision.badge,
              details: dashboard.decision.chartLabel,
              tone: dashboard.decision.signalTone,
            },
          ],
        },
      ],
    };
  }

  if (drawerKey === 'strategy') {
    return {
      title: titleMap.strategy,
      modules: [
        {
          id: 'strategy',
          eyebrow: dashboard.strategy.title,
          title: isEnglish ? 'Observation Constraints' : '观察约束',
          metrics: [
            ...dashboard.strategy.metrics.map((metric) => ({
              label: metric.label,
              value: metric.value,
              details: metric.details,
              tone: metric.tone || 'neutral',
            })),
            {
              label: dashboard.strategy.positionLabel,
              value: isEnglish ? 'Staggered Sizing' : '分批仓位',
              details: dashboard.strategy.positionBody,
              tone: 'neutral',
            },
          ],
        },
      ],
    };
  }

  if (drawerKey === 'tech') {
    return {
      title: titleMap.tech,
      modules: [
        {
          id: 'tech',
          eyebrow: dashboard.tech.title,
          title: isEnglish ? 'Signal Stack' : '信号栈',
          metrics: dashboard.tech.signals.map((signal, index) => ({
            label: signal.label,
            value: signal.value,
            details: signal.details,
            tone: signal.tone,
            glow: index === 0,
          })),
        },
      ],
    };
  }

  return {
    title: titleMap.fundamentals,
    modules: [
      {
        id: 'fundamentals',
        eyebrow: dashboard.fundamentals.title,
        title: isEnglish ? 'Fundamental Support' : '基本面支撑',
        metrics: dashboard.fundamentals.metrics.map((metric, index) => ({
          label: metric.label,
          value: metric.value,
          details: metric.details,
          tone: metric.tone || 'neutral',
          glow: index === 0 && metric.tone === 'bullish',
        })),
      },
    ],
  };
}

function buildDashboardFromReport(locale: DashboardLocale, report: AnalysisReport): DashboardPayload {
  const stockCode = normalizeTickerQuery(report.meta.stockCode || 'NVDA');
  if (hasUntrustedReportMarker(report) && !hasTrustedNormalizedHomeContent(report)) {
    return buildInPlacePlaceholderDashboard(locale, stockCode);
  }

  const seed = buildInPlacePlaceholderDashboard(locale, stockCode);
  const normalized = normalizeHomeAnalysisResult(report, locale);
  const scoreNumber = normalized.score ? Number.parseFloat(normalized.score) : undefined;
  const sentimentTone = toneFromScore(Number.isFinite(scoreNumber) ? scoreNumber : undefined);
  const scoreText = normalized.score || EMPTY_FIELD_VALUE;
  const reasonBody = resolveInsightBody(
    locale,
    sentimentTone,
    [normalized.reason],
    normalized.technicalFields,
  );
  const rawCompany = getCompanyDisplayName(report);
  const companyProfile = resolveCompanyProfile(stockCode, rawCompany);
  const rawSignalLabel = normalized.action || report.summary.sentimentLabel || EMPTY_FIELD_VALUE;
  const rawScoreValue = normalized.scoreContext || EMPTY_FIELD_VALUE;
  const rawSummary = normalized.summary || EMPTY_FIELD_VALUE;
  const entryValue = normalized.entry || EMPTY_FIELD_VALUE;
  const targetValue = normalized.target || EMPTY_FIELD_VALUE;
  const stopValue = normalized.stop || EMPTY_FIELD_VALUE;
  const positionBody = normalized.positionBody || EMPTY_FIELD_VALUE;
  const priceDisplayContext = resolveHomePriceDisplayContext(report, stockCode);
  const localizedEntryValue = localizeMetricValue(
    locale,
    formatHomePriceLevelValue(locale, entryValue, priceDisplayContext, EMPTY_FIELD_VALUE),
    EMPTY_FIELD_VALUE,
  );
  const localizedTargetValue = localizeMetricValue(
    locale,
    formatHomePriceLevelValue(locale, targetValue, priceDisplayContext, EMPTY_FIELD_VALUE),
    EMPTY_FIELD_VALUE,
  );
  const localizedStopValue = localizeMetricValue(
    locale,
    formatHomePriceLevelValue(locale, stopValue, priceDisplayContext, EMPTY_FIELD_VALUE),
    EMPTY_FIELD_VALUE,
  );
  const localizedScoreContext = polishHomeNarrativeCopy(
    locale,
    localizeNarrativeText(locale, rawScoreValue, EMPTY_FIELD_VALUE),
    priceDisplayContext,
  );
  const localizedSummary = polishHomeNarrativeCopy(
    locale,
    localizeNarrativeText(locale, rawSummary, EMPTY_FIELD_VALUE),
    priceDisplayContext,
  );
  const localizedReasonBody = polishHomeNarrativeCopy(
    locale,
    localizeNarrativeText(locale, reasonBody, EMPTY_FIELD_VALUE),
    priceDisplayContext,
  );
  const localizedPositionBody = polishHomeNarrativeCopy(
    locale,
    localizeNarrativeText(locale, positionBody, EMPTY_FIELD_VALUE),
    priceDisplayContext,
  );

  return enrichDashboardPayload(locale, {
    ...seed,
    ticker: stockCode,
    decision: {
      ...seed.decision,
      company: companyProfile.company,
      sector: companyProfile.sector,
      heroValue: scoreText,
      heroUnit: scoreText === EMPTY_FIELD_VALUE ? '' : '/100',
      heroLabel: locale === 'en' ? 'Score' : '评分',
      signalLabel: localizeSentimentLabel(locale, rawSignalLabel, EMPTY_FIELD_VALUE),
      signalTone: sentimentTone,
      scoreValue: localizedScoreContext,
      badge: localizeNarrativeText(locale, normalized.badge, EMPTY_FIELD_VALUE),
      summary: localizedSummary,
      reasonTitle: locale === 'en' ? 'Latest Report Context' : '最近报告归因',
      reasonBody: localizedReasonBody,
      confidenceValue: normalized.confidence,
    },
    strategy: {
      ...seed.strategy,
      metrics: [
        {
          label: locale === 'en' ? 'Watch Zone' : '观察区间',
          value: localizedEntryValue,
          tone: 'neutral',
        },
        {
          label: locale === 'en' ? 'Upper Watch Zone' : '上方观察区',
          value: localizedTargetValue,
          tone: isPendingMetricValue(localizedTargetValue) ? 'neutral' : 'bullish',
        },
        {
          label: locale === 'en' ? 'Invalidation Line' : '风险失效线',
          value: localizedStopValue,
          tone: isPendingMetricValue(localizedStopValue) ? 'neutral' : 'bearish',
        },
      ],
      positionBody: localizedPositionBody,
    },
    tech: {
      ...seed.tech,
      signals: compactDashboardSignals(
        locale,
        mapDesiredFields(locale, normalized.technicalFields, getTechnicalFieldSpecs(locale)).map((item) => ({ ...item, tone: item.tone || 'neutral' })),
      ),
    },
    fundamentals: {
      ...seed.fundamentals,
      metrics: compactDashboardMetrics(locale, mapDesiredFields(locale, normalized.fundamentalFields, getFundamentalFieldSpecs(locale))),
    },
  });
}

function buildGuestDashboardFromPreview(
  locale: DashboardLocale,
  preview: PublicAnalysisPreviewResponse,
): DashboardPayload {
  const stockCode = normalizeTickerQuery(preview.report.meta.stockCode || preview.stockCode || 'AAPL');
  const seed = buildInPlacePlaceholderDashboard(locale, stockCode);
  const summary = preview.report.summary;
  const score = typeof summary.sentimentScore === 'number' ? summary.sentimentScore : 68;
  const sentimentTone = toneFromScore(score);
  const scoreText = (score / 10).toFixed(1);
  const rawCompany = getCompanyDisplayName(preview.report) || preview.stockName || stockCode;
  const companyProfile = resolveCompanyProfile(stockCode, rawCompany);
  const priceDisplayContext = resolveHomePriceDisplayContext(preview.report, stockCode);
  const actionText = polishHomeNarrativeCopy(
    locale,
    localizeNarrativeText(locale, summary.operationAdvice, seed.decision.scoreValue),
    priceDisplayContext,
  );
  const trendText = polishHomeNarrativeCopy(
    locale,
    localizeNarrativeText(locale, summary.trendPrediction, actionText),
    priceDisplayContext,
  );
  const summaryText = polishHomeNarrativeCopy(
    locale,
    localizeNarrativeText(locale, summary.analysisSummary, seed.decision.summary),
    priceDisplayContext,
  );

  return enrichDashboardPayload(locale, {
    ...seed,
    instrument: companyProfile.company,
    ticker: stockCode,
    decision: {
      ...seed.decision,
      company: companyProfile.company,
      sector: companyProfile.sector,
      heroValue: scoreText,
      heroUnit: '/10',
      heroLabel: locale === 'en' ? 'Conviction' : '置信度',
      signalLabel: actionText,
      signalTone: sentimentTone,
      scoreValue: trendText,
      badge: locale === 'en' ? 'Guest preview · live hook' : '游客预览 · 实时诱饵',
      chartLabel: locale === 'en' ? 'Preview generated' : '预览已生成',
      summary: summaryText,
      reasonTitle: locale === 'en' ? 'Guest Preview Context' : '游客预览归因',
      reasonBody: summaryText,
    },
    strategy: {
      ...seed.strategy,
      metrics: seed.strategy.metrics.map((metric) => ({
        ...metric,
        value: metric.value === EMPTY_FIELD_VALUE ? (locale === 'en' ? 'Unlock after account creation' : '创建账户后解锁') : metric.value,
      })),
      positionBody: locale === 'en'
        ? 'Observation bands, risk boundaries, and pacing notes unlock after a free account is created.'
        : '观察区间、风险边界与跟踪节奏会在免费创建账户后解锁。',
    },
  });
}

const SKELETON_LINE_CLASS = 'rounded-full bg-white/[0.08]';

function SkeletonLine({ className = '' }: { className?: string }) {
  return <div className={`${SKELETON_LINE_CLASS} ${className}`} />;
}

type AnalysisTimelineStage = {
  key: string;
  label: string;
  aliases: string[];
};

function getAnalysisTimelineStages(locale: DashboardLocale): AnalysisTimelineStage[] {
  return locale === 'en'
    ? [
        { key: 'market', label: 'Market ID', aliases: ['market', 'detect', 'symbol'] },
        { key: 'quote-tech', label: 'Quote / Technicals', aliases: ['quote', 'price', 'technical', 'candle', 'indicator', '行情', '技术'] },
        { key: 'fundamentals', label: 'Fundamentals', aliases: ['fundamental', 'earnings', '财报', 'basic'] },
        { key: 'news-risk', label: 'News / Risk', aliases: ['news', 'risk', 'sentiment', 'headline'] },
        { key: 'ai', label: 'AI Synthesis', aliases: ['ai', 'llm', 'reason', 'decision', 'analysis'] },
        { key: 'report', label: 'Report Build', aliases: ['report', 'summary', 'output', 'final'] },
      ]
    : [
        { key: 'market', label: '市场识别', aliases: ['market', 'detect', 'symbol', '市场'] },
        { key: 'quote-tech', label: '行情/技术面', aliases: ['quote', 'price', 'technical', 'candle', 'indicator', '行情', '技术', 'k线'] },
        { key: 'fundamentals', label: '基本面', aliases: ['fundamental', 'earnings', '财报', '基本面'] },
        { key: 'news-risk', label: '新闻/风险', aliases: ['news', 'risk', 'sentiment', '新闻', '风险'] },
        { key: 'ai', label: 'AI 综合', aliases: ['ai', 'llm', 'reason', 'decision', 'analysis', '综合'] },
        { key: 'report', label: '报告生成', aliases: ['report', 'summary', 'output', 'final', '报告'] },
      ];
}

function resolveTimelineStageIndex(module: TaskProgressModule, stages: AnalysisTimelineStage[]): number {
  const haystack = `${module.key || ''} ${module.name || ''} ${module.detail || ''}`.toLowerCase();
  const matchedIndex = stages.findIndex((stage) => stage.aliases.some((alias) => haystack.includes(alias.toLowerCase())));
  return matchedIndex >= 0 ? matchedIndex : -1;
}

function buildTimelineProgressState(
  locale: DashboardLocale,
  progressModules: TaskProgressModule[] | undefined,
  message: string | undefined,
  progress: number | undefined,
  phaseTick: number,
): Array<{ key: string; label: string; status: 'pending' | 'running' | 'completed' | 'failed'; detail?: string }> {
  const stages = getAnalysisTimelineStages(locale);
  const timeline: Array<{ key: string; label: string; status: 'pending' | 'running' | 'completed' | 'failed'; detail?: string }> = stages.map((stage) => ({
    key: stage.key,
    label: stage.label,
    status: 'pending',
    detail: undefined as string | undefined,
  }));
  const visibleModules = Array.isArray(progressModules) ? progressModules.filter(Boolean) : [];

  visibleModules.forEach((module) => {
    const stageIndex = resolveTimelineStageIndex(module, stages);
    if (stageIndex < 0) {
      return;
    }
    const normalizedStatus = module.status === 'failed'
      ? 'failed'
      : module.status === 'completed'
        ? 'completed'
        : module.status === 'running'
          ? 'running'
          : 'pending';
    const current = timeline[stageIndex];
    if (current.status !== 'failed') {
      if (normalizedStatus === 'failed' || normalizedStatus === 'running' || (normalizedStatus === 'completed' && current.status === 'pending')) {
        current.status = normalizedStatus;
      }
    }
    if (module.detail && !current.detail) {
      current.detail = module.detail;
    }
  });

  const hasExplicitModuleState = timeline.some((stage) => stage.status !== 'pending');
  if (!hasExplicitModuleState) {
    const coarseIndex = typeof progress === 'number' && progress > 0
      ? Math.max(0, Math.min(stages.length - 1, Math.floor((Math.min(progress, 99) / 100) * stages.length)))
      : phaseTick % stages.length;
    timeline.forEach((stage, index) => {
      stage.status = index < coarseIndex ? 'completed' : index === coarseIndex ? 'running' : 'pending';
    });
  } else if (!timeline.some((stage) => stage.status === 'running')) {
    const lastCompletedIndex = Math.max(...timeline.map((stage, index) => (stage.status === 'completed' ? index : -1)));
    const nextIndex = Math.min(stages.length - 1, Math.max(0, lastCompletedIndex + 1));
    if (timeline[nextIndex].status === 'pending') {
      timeline[nextIndex].status = 'running';
    }
  }

  const activeIndex = timeline.findIndex((stage) => stage.status === 'running');
  if (message && activeIndex >= 0 && !timeline[activeIndex].detail) {
    timeline[activeIndex].detail = message;
  }
  return timeline;
}

function timelineStatusLabel(status: 'pending' | 'running' | 'completed' | 'failed', locale: DashboardLocale): string {
  if (locale === 'en') {
    if (status === 'completed') return 'done';
    if (status === 'running') return 'live';
    if (status === 'failed') return 'risk';
    return 'queued';
  }
  if (status === 'completed') return '完成';
  if (status === 'running') return '进行中';
  if (status === 'failed') return '异常';
  return '待执行';
}

function timelineDotTone(status: 'pending' | 'running' | 'completed' | 'failed'): string {
  if (status === 'completed') return 'bg-emerald-300 shadow-[0_0_14px_rgba(110,231,183,0.45)]';
  if (status === 'running') return 'bg-indigo-200 shadow-[0_0_18px_rgba(165,180,252,0.55)] animate-pulse';
  if (status === 'failed') return 'bg-rose-300 shadow-[0_0_14px_rgba(251,113,133,0.45)]';
  return 'bg-white/18';
}

function buildTimelineLeadCopy(locale: DashboardLocale, activeDetail?: string, message?: string): string {
  if (activeDetail) return activeDetail;
  if (message) return message;
  return locale === 'en' ? 'Wolfy AI is advancing through staged checks.' : 'Wolfy AI 正在按阶段推进分析。';
}

function InPlaceDecisionSkeleton({
  locale,
  ticker,
  progressModules = [],
  message,
  progress,
}: {
  locale: DashboardLocale;
  ticker: string;
  progressModules?: TaskProgressModule[];
  message?: string;
  progress?: number;
}) {
  const [phaseTick, setPhaseTick] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => {
      setPhaseTick((current) => current + 1);
    }, 1200);
    return () => window.clearInterval(timer);
  }, []);

  const timelineStages = buildTimelineProgressState(locale, progressModules, message, progress, phaseTick);
  const activeStage = timelineStages.find((stage) => stage.status === 'running') || timelineStages[0];
  const leadCopy = buildTimelineLeadCopy(locale, activeStage?.detail, message);

  return (
    <section
      className="min-w-0"
      data-testid="home-bento-card-decision"
    >
      <div className="flex min-h-[520px] flex-col gap-5" data-testid="home-bento-inplace-loading-decision">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs text-white/42">{locale === 'en' ? 'Single-name analysis' : '单标的分析'}</p>
            <div className="mt-4 flex items-center gap-3">
              <SkeletonLine className="h-7 w-40" />
              <span className="font-mono text-sm text-white/35">{ticker}</span>
            </div>
          </div>
          <span className="rounded-md border border-[#3B82F6]/24 bg-[#3B82F6]/10 px-2 py-1 text-[11px] font-medium text-[#93C5FD]">
            {locale === 'en' ? 'Running' : '分析中'}
          </span>
        </div>

        <div className="grid gap-6 md:grid-cols-[12rem_minmax(0,1fr)]">
          <div>
            <p className="text-[11px] text-white/42">{locale === 'en' ? 'Stance' : '投资立场'}</p>
            <SkeletonLine className="mt-3 h-10 w-28" />
          </div>
          <div>
            <p className="text-[11px] text-white/42">{locale === 'en' ? 'Score' : '综合评分'}</p>
            <div className="mt-3 flex items-end gap-2">
              <SkeletonLine className="h-10 w-16" />
              <span className="pb-1 text-xs text-white/34">/100</span>
            </div>
            <div className="mt-4 h-1 overflow-hidden rounded-full bg-white/[0.08]">
              <div className="h-full w-1/2 rounded-full bg-[#3B82F6]" />
            </div>
          </div>
        </div>

        <div className="max-w-3xl">
          <p className="text-[11px] text-white/42">{locale === 'en' ? 'Thesis' : '核心观点'}</p>
          <p className="mt-2 text-sm leading-6 text-white/62">{leadCopy}</p>
        </div>

        <div className="rounded-lg border border-white/[0.07] bg-white/[0.02] px-4 py-3">
          <div className="grid gap-2" data-testid="home-bento-progress-timeline">
            {timelineStages.map((stage, index) => {
              const isRunning = stage.status === 'running';
              return (
                <div
                  key={stage.key}
                  className="relative grid grid-cols-[1.5rem_minmax(0,1fr)_4.5rem] items-start gap-3 border-b border-white/[0.06] py-2 last:border-b-0"
                  data-testid={`home-bento-progress-stage-${stage.key}`}
                >
                  <span className={`mt-1.5 size-2 rounded-full ${timelineDotTone(stage.status)}`} />
                  <div className="min-w-0">
                    <p className={cn('truncate text-sm font-medium', isRunning ? 'text-white' : 'text-white/58')}>{stage.label}</p>
                    {stage.detail ? <p className="mt-1 truncate text-xs text-white/40">{stage.detail}</p> : null}
                  </div>
                  <span className="text-right text-[10px] font-medium text-white/38">
                    {String(index + 1).padStart(2, '0')} {timelineStatusLabel(stage.status, locale)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}

function InPlaceStrategySkeleton({ locale }: { locale: DashboardLocale }) {
  return (
    <section className="min-w-0" data-testid="home-bento-card-strategy">
      <div className="min-w-0" data-testid="home-bento-inplace-loading-strategy">
        <div className="mb-4 flex items-center justify-between">
          <p className="text-sm font-semibold text-white">{locale === 'en' ? 'Observation Framework' : '观察框架'}</p>
          <SkeletonLine className="h-3 w-16" />
        </div>
        <div className="divide-y divide-white/[0.07]">
          {Array.from({ length: 5 }).map((_, index) => (
            <div key={`strategy-line-${index}`} className="flex items-center justify-between gap-4 py-3">
              <SkeletonLine className="h-3 w-24" />
              <SkeletonLine className="h-3 w-20" />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function InPlaceListSkeleton({
  locale,
  kind,
}: {
  locale: DashboardLocale;
  kind: 'tech' | 'fundamentals';
}) {
  const title = kind === 'tech'
    ? (locale === 'en' ? 'Technical Structure' : '技术结构')
    : (locale === 'en' ? 'Fundamental Profile' : '基本面画像');

  return (
    <section
      className="min-w-0 rounded-lg border border-white/[0.07] bg-white/[0.018] p-3"
      data-testid={kind === 'tech' ? 'home-bento-card-tech' : 'home-bento-card-fundamentals'}
    >
      <p className="text-sm font-semibold text-white">{title}</p>
      <div
        className={kind === 'tech' ? 'mt-3 space-y-3' : 'mt-3 grid grid-cols-2 gap-x-5 gap-y-4'}
        data-testid={`home-bento-inplace-loading-${kind}`}
      >
        {Array.from({ length: kind === 'tech' ? 4 : 6 }).map((_, index) => (
          <div
            key={`${kind}-skeleton-${index}`}
            className={kind === 'tech' ? 'grid gap-2 border-b border-white/[0.07] pb-3 last:border-b-0 last:pb-0' : 'min-w-0'}
          >
            <SkeletonLine className="h-3 w-20" />
            <SkeletonLine className="mt-2 h-5 w-full" />
          </div>
        ))}
      </div>
    </section>
  );
}

function GuestPaywallOverlay({ locale, registrationPath }: { locale: DashboardLocale; registrationPath: string }) {
  return (
    <div
      className="absolute inset-0 z-20 flex flex-col items-center justify-center rounded-xl bg-[rgba(8,12,24,0.58)] px-6 text-center backdrop-blur-[8px]"
      data-testid="guest-home-frosted-lock"
    >
      <Lock className="size-7 text-white/85 drop-shadow-[0_0_14px_rgba(99,102,241,0.55)]" />
      <p className="mt-4 max-w-xs text-sm font-medium leading-6 text-white/80">
        解锁完整 AI 量化策略与深度技术形态解析
      </p>
      <Link
        to={registrationPath}
        className="mt-5 inline-flex items-center justify-center rounded-full bg-gradient-to-r from-blue-500 to-purple-600 px-8 py-3 text-sm font-medium text-white shadow-[0_0_20px_rgba(99,102,241,0.4)] transition-all hover:from-blue-400 hover:to-purple-500"
      >
        {locale === 'en' ? 'Create free account' : '免费创建账户'}
      </Link>
    </div>
  );
}

function FullDecisionReportDrawerFallback({ onClose }: { onClose: () => void }) {
  return (
    <Drawer
      isOpen
      onClose={onClose}
      title="完整报告"
      width="max-w-[min(100vw,65rem)]"
      zIndex={90}
      bodyClassName="overflow-x-hidden"
    >
      <section
        className="min-w-0 rounded-l-[28px] border border-white/[0.08] bg-[#080B10]/92 p-6 text-white shadow-2xl"
        data-testid="home-bento-full-report-drawer-fallback"
      >
        <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-white/42">WOLFY AI EQUITY RESEARCH</p>
        <h2 className="mt-3 text-xl font-semibold tracking-[0] text-white">完整报告加载中</h2>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-white/58">
          正在按需加载完整报告视图，报告内容、复制、导出和打印行为保持不变。
        </p>
        <div className="mt-5 space-y-3">
          {[0, 1, 2].map((item) => (
            <div
              key={item}
              className="h-14 rounded-2xl border border-white/[0.06] bg-white/[0.03]"
            />
          ))}
        </div>
      </section>
    </Drawer>
  );
}

const HomeBentoDashboardPage: React.FC<HomeBentoDashboardPageProps> = ({ isGuest = false }) => {
  const { surfaceRef } = useSafariRenderReady();
  const [searchParams] = useSearchParams();
  const shouldGuardA11y = shouldApplySafariA11yGuard();
  const { language, t } = useI18n();
  const shouldRenderHomeChart = useDeferredHomeChartMount();
  const locale: DashboardLocale = language === 'en' ? 'en' : 'zh';
  const [activeDrawer, setActiveDrawer] = useState<DetailDrawerKey | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTicker, setActiveTicker] = useState<string | null>(null);
  const [pendingAnalysisTicker, setPendingAnalysisTicker] = useState<string | null>(null);
  const [hasHydratedInitialTicker, setHasHydratedInitialTicker] = useState(false);
  const [isDashboardLoading, setDashboardLoading] = useState(false);
  const [statusToast, setStatusToast] = useState<{ message: string; tone: 'error' | 'warning' } | null>(null);
  const [guestPreview, setGuestPreview] = useState<PublicAnalysisPreviewResponse | null>(null);
  const [guestError, setGuestError] = useState<ParsedApiError | null>(null);
  const [guestFallbackNotice, setGuestFallbackNotice] = useState<string | null>(null);
  const [pendingHistoryDelete, setPendingHistoryDelete] = useState<PendingHistoryDelete | null>(null);
  const [hydratedRouteTaskId, setHydratedRouteTaskId] = useState<string | null>(null);
  const [isTraceDrawerOpen, setTraceDrawerOpen] = useState(false);
  const [isFullReportDrawerOpen, setFullReportDrawerOpen] = useState(false);
  const [mainCopyState, setMainCopyState] = useState<'idle' | 'copied' | 'failed'>('idle');
  const [homeChartContext, setHomeChartContext] = useState<HomeCandlestickChartContext | null>(null);
  const routeTaskId = searchParams.get('task_id') || searchParams.get('taskId') || null;
  const routeSymbol = normalizeTickerQuery(searchParams.get('symbol') || undefined);
  const routeSource = searchParams.get('source') || null;
  const traceFixtureReport = (!isGuest && (import.meta.env.DEV || import.meta.env.MODE === 'test') && searchParams.get('fixture') === 'analysis-trace')
    ? buildDecisionTraceFixtureReport()
    : null;
  const isAnalyzing = useStockPoolStore((state) => state.isAnalyzing);
  const historyItems = useStockPoolStore((state) => state.historyItems);
  const selectedReport = useStockPoolStore((state) => state.selectedReport);
  const [isHistoryDrawerOpen, setHistoryDrawerOpen] = useState(false);
  const refreshHistory = useStockPoolStore((state) => state.refreshHistory);
  const focusLatestHistoryForStock = useStockPoolStore((state) => state.focusLatestHistoryForStock);
  const selectHistoryItem = useStockPoolStore((state) => state.selectHistoryItem);
  const selectCachedHistoryForStock = useStockPoolStore((state) => state.selectCachedHistoryForStock);
  const deleteHistoryRecords = useStockPoolStore((state) => state.deleteHistoryRecords);
  const isDeletingHistory = useStockPoolStore((state) => state.isDeletingHistory);
  const submitAnalysis = useStockPoolStore((state) => state.submitAnalysis);
  const clearError = useStockPoolStore((state) => state.clearError);
  const loadInitialHistory = useStockPoolStore((state) => state.loadInitialHistory);
  const hydrateRecentTasks = useStockPoolStore((state) => state.hydrateRecentTasks);
  const activeTasks = useStockPoolStore((state) => state.activeTasks);
  const syncTaskCreated = useStockPoolStore((state) => state.syncTaskCreated);
  const syncTaskUpdated = useStockPoolStore((state) => state.syncTaskUpdated);
  const syncTaskFailed = useStockPoolStore((state) => state.syncTaskFailed);
  const refreshTaskProgress = useStockPoolStore((state) => state.refreshTaskProgress);
  const {
    ref: openHistoryDrawerButtonRef,
    onClick: handleOpenHistoryDrawerClick,
    onPointerUp: handleOpenHistoryDrawerPointerUp,
  } = useSafariWarmActivation<HTMLButtonElement>(() => setHistoryDrawerOpen(true));
  const registrationPath = '/login?mode=create&redirect=%2F';
  const homeChartLoadingLabel = language === 'en' ? 'Loading home price chart' : '正在加载首页价格图表';
  const recentHistoryItems = historyItems.filter((item) => !item.isTest).slice(0, 8);
  const hasRunningTasks = activeTasks.some((task) => task.status === 'pending' || task.status === 'processing');
  const selectedTicker = normalizeTickerQuery(selectedReport?.meta.stockCode);
  const completedTaskReport = (() => {
    if (routeTaskId) {
      return activeTasks.find(
        (task) => task.taskId === routeTaskId && task.status === 'completed' && task.result?.report,
      )?.result?.report || null;
    }
    const taskTicker = pendingAnalysisTicker || activeTicker;
    if (!taskTicker) {
      return null;
    }
    return activeTasks.find(
      (task) => normalizeTickerQuery(task.stockCode) === taskTicker && task.status === 'completed' && task.result?.report,
    )?.result?.report || null;
  })();
  const focusedTask = (() => {
    if (routeTaskId) {
      const matchedById = activeTasks.find((task) => task.taskId === routeTaskId);
      if (matchedById) {
        return matchedById;
      }
    }
    const taskTicker = pendingAnalysisTicker || activeTicker;
    if (taskTicker) {
      const matched = activeTasks.find((task) => normalizeTickerQuery(task.stockCode) === taskTicker);
      if (matched) {
        return matched;
      }
    }
    return activeTasks[0] || null;
  })();
  const isTaskAnalyzing = Boolean(
    (pendingAnalysisTicker || routeTaskId)
    && focusedTask
    && (focusedTask.status === 'pending' || focusedTask.status === 'processing'),
  );
  const isGuestAnalyzing = isGuest && isDashboardLoading;
  const isHomeAnalyzing = isGuestAnalyzing || (!isGuest && (isAnalyzing || isTaskAnalyzing || Boolean(pendingAnalysisTicker && isDashboardLoading)));
  const isBusy = isHomeAnalyzing || isDashboardLoading;
  const dashboardData: DashboardPayload = (() => {
    if (traceFixtureReport) {
      return buildDashboardFromReport(locale, traceFixtureReport);
    }

    if (isGuest) {
      return guestPreview
        ? buildGuestDashboardFromPreview(locale, guestPreview)
        : buildInPlacePlaceholderDashboard(locale, activeTicker);
    }

    const effectiveTicker = routeSymbol || activeTicker || selectedTicker || normalizeTickerQuery(recentHistoryItems[0]?.stockCode) || DEFAULT_HOME_TICKER;

    if (
      completedTaskReport
      && effectiveTicker
      && normalizeTickerQuery(completedTaskReport.meta.stockCode) === effectiveTicker
    ) {
      return buildDashboardFromReport(locale, completedTaskReport);
    }

    if (selectedReport && effectiveTicker && selectedTicker === effectiveTicker) {
      return buildDashboardFromReport(locale, selectedReport);
    }

    if (pendingAnalysisTicker && effectiveTicker === pendingAnalysisTicker) {
      return buildInPlacePlaceholderDashboard(locale, effectiveTicker);
    }

    return buildInPlacePlaceholderDashboard(locale, effectiveTicker);
  })();
  const activeTraceReport: AnalysisReport | null = (() => {
    if (traceFixtureReport) {
      return traceFixtureReport;
    }

    const effectiveTicker = routeSymbol || activeTicker || selectedTicker || null;
    if (
      completedTaskReport
      && effectiveTicker
      && normalizeTickerQuery(completedTaskReport.meta.stockCode) === effectiveTicker
    ) {
      return completedTaskReport;
    }
    if (selectedReport && (!effectiveTicker || selectedTicker === effectiveTicker)) {
      return selectedReport;
    }
    return completedTaskReport || selectedReport || null;
  })();
  const copy = dashboardData;
  const standbyCopy = locale === 'en'
    ? {
      analyzeButton: 'Analyze',
      omnibarPlaceholder: 'Enter a valid ticker...',
    }
    : {
      analyzeButton: '分析',
      omnibarPlaceholder: '输入有效股票代码...',
    };
  const activeDrawerPayload = activeDrawer && copy ? buildDrawerPayload(locale, copy, activeDrawer) : null;
  const activeDecisionTrace = activeTraceReport ? getDecisionTrace(activeTraceReport) : undefined;
  const activeReportQuality = getReportQuality(activeTraceReport);
  const activeDataQualityReport = getDataQualityReport(activeTraceReport);
  const sourceSummary = buildTraceSummary(activeDecisionTrace, activeReportQuality, locale);
  const hasActiveTraceReport = Boolean(activeTraceReport);
  const reportTicker = normalizeTickerQuery(activeTraceReport?.meta.stockCode);
  const reanalysisCandidate = reportTicker || (hasActiveTraceReport ? '' : normalizeTickerQuery(dashboardData.ticker));
  const reanalysisTicker = TICKER_FORMAT_RE.test(reanalysisCandidate) ? reanalysisCandidate : '';
  const shouldRenderDashboardPanels = !isGuest || Boolean(guestPreview || pendingAnalysisTicker);
  const guestPaywall = isGuest ? <GuestPaywallOverlay locale={locale} registrationPath={registrationPath} /> : null;
  const deleteCopy = {
    title: t('home.deleteTitle'),
    single: t('home.deleteSingle'),
    multiple: (count: number) => t('home.deleteMultiple', { count }),
    confirm: t('home.deleteConfirm'),
    deleting: t('home.deleting'),
    cancel: t('home.cancel'),
    clearVisible: t('home.deleteAll'),
    deleteOne: t('home.deleteOne'),
    visibleCount: t('home.visibleCount'),
  };

  useEffect(() => {
    document.title = copy.documentTitle;
  }, [copy.documentTitle]);

  useEffect(() => {
    if (traceFixtureReport && searchParams.get('trace') === 'open' && !isTraceDrawerOpen) {
      setTraceDrawerOpen(true);
    }
  }, [isTraceDrawerOpen, searchParams, traceFixtureReport]);

  useEffect(() => {
    if (traceFixtureReport && searchParams.get('report') === 'open' && !isFullReportDrawerOpen) {
      setFullReportDrawerOpen(true);
    }
  }, [isFullReportDrawerOpen, searchParams, traceFixtureReport]);

  useEffect(() => {
    if (mainCopyState === 'idle') {
      return undefined;
    }
    const timer = window.setTimeout(() => setMainCopyState('idle'), 1800);
    return () => window.clearTimeout(timer);
  }, [mainCopyState]);

  useEffect(() => {
    purgeZombieDashboardStorage();
  }, []);

  useDashboardLifecycle({
    loadInitialHistory,
    refreshHistory,
    hydrateRecentTasks,
    syncTaskCreated,
    syncTaskUpdated,
    syncTaskFailed,
    enabled: !isGuest,
    hasRunningTasks: !isGuest && hasRunningTasks,
  });

  useEffect(() => {
    if (isGuest || !routeTaskId || !routeSymbol || routeSource !== 'watchlist') {
      return;
    }
    if (hydratedRouteTaskId === routeTaskId) {
      return;
    }
    setActiveTicker(routeSymbol);
    setPendingAnalysisTicker(routeSymbol);
    setDashboardLoading(true);
    setHasHydratedInitialTicker(true);
    setHydratedRouteTaskId(routeTaskId);
    syncTaskCreated({
      taskId: routeTaskId,
      stockCode: routeSymbol,
      status: 'pending',
      progress: 0,
      message: locale === 'en' ? `WOLFY AI analyzing ${routeSymbol}...` : `WOLFY AI 正在分析 ${routeSymbol}...`,
      reportType: 'detailed',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      originalQuery: routeSymbol,
      selectionSource: 'manual',
    });
    void refreshTaskProgress(routeTaskId);
  }, [hydratedRouteTaskId, isGuest, locale, refreshTaskProgress, routeSource, routeSymbol, routeTaskId, syncTaskCreated]);

  const focusedTaskId = focusedTask?.taskId;
  const focusedTaskStatus = focusedTask?.status;

  useEffect(() => {
    if (!focusedTaskId || focusedTaskStatus === 'completed' || focusedTaskStatus === 'failed') {
      return undefined;
    }

    void refreshTaskProgress(focusedTaskId);
    if (import.meta.env.MODE === 'test') {
      return undefined;
    }
    const timer = window.setInterval(() => {
      void refreshTaskProgress(focusedTaskId);
    }, 1500);

    return () => {
      window.clearInterval(timer);
    };
  }, [focusedTaskId, focusedTaskStatus, refreshTaskProgress]);

  useEffect(() => {
    if (hasHydratedInitialTicker) {
      return;
    }
    if (pendingAnalysisTicker) {
      return;
    }

    if (isGuest) {
      return;
    }

    const nextTicker = normalizeTickerQuery(selectedReport?.meta.stockCode) || normalizeTickerQuery(recentHistoryItems[0]?.stockCode) || DEFAULT_HOME_TICKER;

    const frame = window.requestAnimationFrame(() => {
      setActiveTicker(nextTicker);
      setHasHydratedInitialTicker(true);
    });

    return () => window.cancelAnimationFrame(frame);
  }, [hasHydratedInitialTicker, isGuest, pendingAnalysisTicker, recentHistoryItems, selectedReport?.meta.stockCode]);

  useEffect(() => {
    if (isGuest || pendingAnalysisTicker) {
      return;
    }

    if (selectedTicker && !activeTicker) {
      setActiveTicker(selectedTicker);
      return;
    }

  }, [activeTicker, isGuest, pendingAnalysisTicker, selectedTicker]);

  useEffect(() => {
    if (!routeTaskId && pendingAnalysisTicker && selectedTicker === pendingAnalysisTicker) {
      setPendingAnalysisTicker(null);
      setDashboardLoading(false);
    }
  }, [pendingAnalysisTicker, routeTaskId, selectedTicker]);

  useEffect(() => {
    if (!statusToast) {
      return undefined;
    }

    const timer = window.setTimeout(() => {
      setStatusToast(null);
    }, 3200);

    return () => window.clearTimeout(timer);
  }, [statusToast]);

  useEffect(() => {
    if (!pendingAnalysisTicker && !routeTaskId) {
      return;
    }

    const completedTask = routeTaskId
      ? activeTasks.find((task) => task.taskId === routeTaskId && task.status === 'completed' && task.result?.report)
      : activeTasks.find(
        (task) => normalizeTickerQuery(task.stockCode) === pendingAnalysisTicker && task.status === 'completed' && task.result?.report,
      );
    if (!completedTask) {
      return;
    }

    const completedTicker = normalizeTickerQuery(completedTask.stockCode) || pendingAnalysisTicker || routeSymbol;
    setActiveTicker(completedTicker);
    setPendingAnalysisTicker(null);
    setDashboardLoading(false);
    void refreshHistory(true);
    if (completedTicker) {
      void focusLatestHistoryForStock(completedTicker);
    }
  }, [activeTasks, focusLatestHistoryForStock, pendingAnalysisTicker, refreshHistory, routeSymbol, routeTaskId]);

  const handleAnalyze = async (tickerOverride?: string) => {
    const rawQuery = (tickerOverride ?? searchQuery).trim();
    if (!rawQuery) {
      return;
    }

    const normalizedTicker = rawQuery.toUpperCase();
    if (!TICKER_FORMAT_RE.test(normalizedTicker)) {
      setStatusToast({
        message: locale === 'en' ? 'Please enter a correctly formatted ticker.' : '请输入格式正确的股票代码',
        tone: 'error',
      });
      return;
    }

    setStatusToast(null);
    setDashboardLoading(true);
    setActiveTicker(normalizedTicker);
    setPendingAnalysisTicker(normalizedTicker);
    setHasHydratedInitialTicker(true);
    setSearchQuery('');

    if (isGuest) {
      setGuestError(null);
      setGuestFallbackNotice(null);
      try {
        const response = await withFallback(
          () => publicAnalysisApi.preview({
            stockCode: normalizedTicker,
            stockName: undefined,
            reportType: 'brief',
          }),
          {
            fallback: () => createPublicAnalysisFallbackPreview(normalizedTicker, language),
          },
        );
        setGuestPreview(response.data);
        setPendingAnalysisTicker(null);
        if (response.fallback) {
          setGuestFallbackNotice(language === 'en'
            ? 'Live preview is temporarily unavailable. Loaded a local snapshot instead.'
            : '实时预览暂时不可用，已切换到本地快照。');
        }
      } catch (err) {
        setGuestError(getParsedApiError(err));
        setPendingAnalysisTicker(null);
      } finally {
        setDashboardLoading(false);
      }
      return;
    }

    clearError();

    try {
      const result = await submitAnalysis({
        stockCode: normalizedTicker,
        originalQuery: normalizedTicker,
        selectionSource: 'manual',
      });

      if (result.ok) {
        setActiveTicker(result.stockCode);
        void refreshHistory(true);
        return;
      }

      if (result.duplicate) {
        return;
      }

      setPendingAnalysisTicker(null);
      setStatusToast({
        message: result.error?.message || (locale === 'en' ? 'LLM analysis failed. Please try again later.' : 'LLM 分析失败，请稍后重试'),
        tone: 'error',
      });
    } catch (error) {
      const parsedError = getParsedApiError(error);
      setPendingAnalysisTicker(null);
      setStatusToast({
        message: parsedError.message || (locale === 'en' ? 'LLM analysis failed. Please try again later.' : 'LLM 分析失败，请稍后重试'),
        tone: 'error',
      });
    } finally {
      setDashboardLoading(false);
    }
  };

  const handleHistoryClick = async (historyItem: HistoryItem) => {
    const normalizedTicker = normalizeTickerQuery(historyItem.stockCode);
    if (!normalizedTicker) {
      return;
    }

    setHistoryDrawerOpen(false);
    setStatusToast(null);
    setPendingAnalysisTicker(null);
    clearError();
    setActiveTicker(normalizedTicker);

    // Local snapshots are only a visual bridge; the persisted history detail remains the source of truth.
    const hasCachedSnapshot = selectCachedHistoryForStock(normalizedTicker);
    if (!hasCachedSnapshot) {
      setDashboardLoading(true);
    }

    try {
      await selectHistoryItem(historyItem.id);
    } finally {
      setDashboardLoading(false);
    }
  };

  const handleConfirmDeleteHistory = async () => {
    if (!pendingHistoryDelete || isDeletingHistory) {
      return;
    }

    try {
      await deleteHistoryRecords(
        pendingHistoryDelete.recordIds,
        pendingHistoryDelete.mode === 'visible' ? { deleteAll: true } : undefined,
      );
      setHistoryDrawerOpen(false);
    } finally {
      setPendingHistoryDelete(null);
    }
  };

  const handleCopyActiveReport = async () => {
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error('clipboard_unavailable');
      }
      await navigator.clipboard.writeText(buildInstitutionalReportMarkdown(activeTraceReport));
      setMainCopyState('copied');
    } catch {
      setMainCopyState('failed');
    }
  };

  const reportActionButtons = !isGuest ? (
    <>
      <button
        type="button"
        aria-label={locale === 'en' ? 'Copy report' : '复制报告'}
        className="home-research-action-button inline-flex min-h-9 min-w-0 items-center gap-2 rounded-[7px] border px-3.5 py-1.5 text-xs font-medium text-white/72 transition-colors hover:text-white/90"
        onClick={() => { void handleCopyActiveReport(); }}
      >
        <Star className="size-3.5 shrink-0" />
        <span className="truncate">{mainCopyState === 'copied' ? (locale === 'en' ? 'Added' : '已加入') : (locale === 'en' ? 'Watch' : '加入观察')}</span>
      </button>
      <button
        type="button"
        aria-label={locale === 'en' ? 'Full Report' : '完整报告'}
        className="home-research-action-button home-research-action-button--primary inline-flex min-h-9 min-w-0 items-center gap-2 rounded-[7px] border px-3.5 py-1.5 text-xs font-medium text-white/82 transition-colors hover:text-white"
        onClick={() => setFullReportDrawerOpen(true)}
      >
        <Upload className="size-3.5 shrink-0" />
        <span className="truncate">{locale === 'en' ? 'Generate report' : '生成报告'}</span>
      </button>
      <button
        type="button"
        className="home-research-action-button inline-flex min-size-9 items-center justify-center rounded-[7px] border text-white/58 transition-colors hover:text-white/82"
        onClick={() => setTraceDrawerOpen(true)}
        data-testid="home-bento-decision-trace-trigger"
        aria-label={locale === 'en' ? 'Sources' : '决策来源'}
      >
        <MoreHorizontal className="size-4" />
      </button>
      <button
        type="button"
        className="sr-only"
        disabled={isBusy || !reanalysisTicker}
        title={!reanalysisTicker ? '缺少股票代码' : undefined}
        onClick={() => { void handleAnalyze(reanalysisTicker); }}
      >
        {!reanalysisTicker ? '缺少股票代码' : locale === 'en' ? 'Rerun' : '重新分析'}
      </button>
    </>
  ) : null;
  const guestCommandConsoleCopy = locale === 'en'
    ? {
        eyebrow: 'Guest Research Console',
        title: 'WolfyStock Research Console',
        subtitle: 'Enter a ticker or name to start a research pass. Sign in to save watch items, generate reports, and open portfolio or scanner workflows.',
        commandLabel: 'Command entry',
        commandHint: 'Examples: AAPL / Tencent / 600519',
        unlockTitle: 'Unlock after sign-in',
        unlockItems: ['Save watch items', 'Generate reports', 'Portfolio workspace', 'Market scanner'],
        unlockAction: 'Create free account',
        previewTitle: 'Guest preview scope',
        previewBody: 'Guests can open a compact research preview first. Full reports, saved observation history, portfolio, and scanner remain locked behind the existing sign-in flow.',
        trustTitle: 'Research boundary',
        trustBody: 'Data confidence and evidence coverage affect the conclusion strength. Current output is for research observation only, not a trading instruction.',
        workflow: ['Search', 'Analyze', 'Observe', 'Report'],
      }
    : {
        eyebrow: '游客研究控制台',
        title: 'WolfyStock 研究控制台',
        subtitle: '输入股票代码或标的名称，先启动研究命令。登录后可保存观察、生成报告，并进入组合或扫描工作台。',
        commandLabel: '研究命令入口',
        commandHint: '示例：AAPL / 腾讯控股 / 600519',
        unlockTitle: '登录后解锁',
        unlockItems: ['保存观察', '生成报告', '组合工作台', '全市场扫描'],
        unlockAction: '免费创建账户',
        previewTitle: '游客预览范围',
        previewBody: '游客可先查看简版研究预览；完整报告、观察历史、组合与扫描能力仍保持既有登录链路解锁。',
        trustTitle: '研究边界',
        trustBody: '数据可信度与证据覆盖会直接影响结论强度；当前输出仅用于研究观察，不等于买卖建议。',
        workflow: ['搜索', '分析', '观察', '报告'],
      };

  const omnibarModule = (
    <div className="w-full shrink-0" data-testid="home-bento-omnibar-shell">
      <form
        className="w-full min-w-0"
        data-testid="home-bento-omnibar"
        onSubmit={(event) => {
          event.preventDefault();
          void handleAnalyze();
        }}
      >
        <CompactFilterBar
          data-testid="home-research-command-bar"
          data-surface-system="reflect-linear-console"
          className="home-research-command-bar min-h-12 items-stretch gap-2 rounded-xl bg-[var(--wolfy-surface-input)] px-2.5 py-2 sm:flex-nowrap"
          trailing={(
            <>
              <button
                type="submit"
                disabled={isBusy}
                aria-label={locale === 'en' ? 'Analyze' : '分析'}
                className="min-h-10 shrink-0 rounded-lg border border-[color:var(--wolfy-border-focus)] bg-[var(--wolfy-accent)] px-5 text-sm font-semibold text-white shadow-[0_0_22px_rgba(118,109,219,0.18)] transition-colors hover:bg-[#8178e7] disabled:cursor-wait disabled:bg-white/[0.05] disabled:text-white/42"
                data-testid="home-bento-analyze-button"
              >
                {isHomeAnalyzing ? (locale === 'en' ? 'Analyzing...' : '分析中...') : (copy?.analyzeButton || standbyCopy.analyzeButton)}
              </button>
              {!isGuest ? (
                <button
                  ref={openHistoryDrawerButtonRef}
                  type="button"
                  aria-label={locale === 'en' ? 'History' : '历史记录'}
                  onClick={handleOpenHistoryDrawerClick}
                  onPointerUp={handleOpenHistoryDrawerPointerUp}
                  disabled={isBusy}
                  className="home-research-action-button flex min-h-10 shrink-0 items-center justify-center rounded-lg border px-4 text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)] disabled:cursor-wait disabled:text-white/34"
                  data-testid="home-bento-history-drawer-trigger"
                >
                  <History className="size-4" aria-hidden="true" />
                </button>
              ) : null}
            </>
          )}
        >
          <div
            className="group relative flex min-h-10 min-w-0 flex-1 items-center overflow-hidden rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] shadow-[inset_0_1px_0_rgba(255,255,255,0.03)] transition-colors focus-within:border-[color:var(--wolfy-border-focus)] focus-within:bg-[var(--wolfy-surface-panel)]"
            data-testid="home-bento-omnibar-input-shell"
          >
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-4">
              <Search className="size-4 text-white/40" />
            </div>
            <input
              data-testid="home-bento-omnibar-input"
              type="text"
              className="h-full min-h-10 min-w-0 flex-1 bg-transparent pl-11 pr-4 text-sm leading-none text-white caret-[#93C5FD] outline-none [appearance:textfield] placeholder:text-white/30"
              value={searchQuery}
              onChange={(event) => {
                setSearchQuery(event.target.value);
              }}
              autoComplete="off"
              disabled={isBusy}
              placeholder={copy?.omnibarPlaceholder || standbyCopy.omnibarPlaceholder}
            />
          </div>
        </CompactFilterBar>
      </form>
      {guestFallbackNotice ? (
        <p className="mt-3 text-xs text-white/50">{guestFallbackNotice}</p>
      ) : null}
      {guestError ? (
        <p className="mt-3 text-xs font-medium text-rose-200">{guestError.message}</p>
      ) : null}
    </div>
  );

  return (
    <div
      ref={surfaceRef}
      data-testid="home-bento-dashboard"
      data-route-surface="ResearchConsole"
      data-home-surface-role={isGuest ? 'guest' : 'member'}
      aria-live={shouldGuardA11y ? 'polite' : undefined}
      className={getSafariReadySurfaceClassName(
        true,
        'relative isolate w-full flex-1 flex flex-col min-h-0 min-w-0 overflow-x-hidden bg-transparent',
      )}
    >
      {statusToast ? (
        <div className="pointer-events-none fixed right-6 top-24 z-50" data-testid="home-bento-fallback-toast">
          <div className={statusToast.tone === 'warning'
            ? 'rounded-2xl border border-amber-300/35 bg-amber-950/82 px-4 py-3 text-sm font-semibold text-amber-50 shadow-[0_18px_50px_rgba(120,53,15,0.35)] backdrop-blur-xl'
            : 'rounded-2xl border border-rose-400/35 bg-rose-950/82 px-4 py-3 text-sm font-semibold text-rose-50 shadow-[0_18px_50px_rgba(251,113,133,0.22)] backdrop-blur-xl'}>
            {statusToast.message}
          </div>
        </div>
      ) : null}
      <main className="w-full flex-1 flex flex-col min-h-0 min-w-0" data-testid="home-bento-main">
        {!shouldRenderDashboardPanels ? (
          <section
            className="mx-auto flex w-full max-w-[1880px] flex-1 min-w-0 flex-col p-3 sm:px-4 xl:px-6 2xl:px-8"
            data-testid="guest-home-clean-search"
          >
            <div className="flex w-full min-w-0 flex-col gap-3" data-testid="guest-home-first-screen-stack">
              <section
                className="min-w-0 rounded-[12px] border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-panel)] p-4 sm:px-5 sm:py-5"
                data-testid="guest-home-command-surface"
                data-layout-zone="RouteConsole"
                data-visual-role="guest-command-console"
              >
                <div className="flex min-w-0 flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                  <div className="min-w-0 max-w-3xl">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-white/40">
                      {guestCommandConsoleCopy.eyebrow}
                    </p>
                    <h1 className="mt-2 text-[28px] font-semibold tracking-[0] text-white sm:text-[32px]">
                      {guestCommandConsoleCopy.title}
                    </h1>
                    <p className="mt-2 max-w-2xl text-sm leading-6 text-white/62 sm:text-[15px]">
                      {guestCommandConsoleCopy.subtitle}
                    </p>
                  </div>
                  <div
                    className="grid min-w-0 grid-cols-2 overflow-hidden rounded-[8px] border border-white/[0.06] text-[11px] sm:grid-cols-4 xl:max-w-[21rem]"
                    data-testid="guest-home-command-workflow"
                  >
                    {guestCommandConsoleCopy.workflow.map((item, index) => (
                      <div key={item} className="min-w-0 border-b border-r border-white/[0.06] px-3 py-2.5 last:border-r-0 even:border-r-0 sm:border-b-0 sm:even:border-r sm:last:border-r-0">
                        <span className="block font-mono text-[10px] text-white/26">0{index + 1}</span>
                        <span className="mt-1 block truncate font-semibold text-white/72">{item}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="mt-4 grid min-w-0 gap-3 xl:grid-cols-[minmax(0,1fr)_17rem]">
                  <div className="min-w-0">
                    <div className="mb-2 flex min-w-0 flex-wrap items-center justify-between gap-2">
                      <p className="text-[11px] font-medium text-white/40">{guestCommandConsoleCopy.commandLabel}</p>
                      <p className="text-[11px] text-white/30">{guestCommandConsoleCopy.commandHint}</p>
                    </div>
                    {omnibarModule}
                  </div>
                  <aside
                    className="min-w-0 rounded-[8px] border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] px-4 py-3"
                    data-testid="guest-home-capability-strip"
                  >
                    <p className="text-[11px] font-medium text-white/40">{guestCommandConsoleCopy.unlockTitle}</p>
                    <div className="mt-3 flex min-w-0 flex-wrap gap-2">
                      {guestCommandConsoleCopy.unlockItems.map((item) => (
                        <span
                          key={item}
                          className="inline-flex min-h-8 items-center rounded-full border border-white/[0.07] bg-white/[0.03] px-3 text-xs font-medium text-white/72"
                        >
                          {item}
                        </span>
                      ))}
                    </div>
                    <Link
                      to={registrationPath}
                      className="mt-3 inline-flex min-h-10 items-center justify-center rounded-lg border border-[color:var(--wolfy-border-focus)] bg-[var(--wolfy-accent)] px-4 text-sm font-semibold text-white transition-colors hover:bg-[#8178e7]"
                      data-testid="guest-home-registration-link"
                    >
                      {guestCommandConsoleCopy.unlockAction}
                    </Link>
                  </aside>
                </div>
              </section>

              <div className="grid min-w-0 gap-3 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
                <section
                  className="min-w-0 rounded-[12px] border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-panel)] px-4 py-3.5 sm:px-5"
                  data-testid="guest-home-trust-strip"
                >
                  <p className="text-[11px] font-medium text-white/40">{guestCommandConsoleCopy.trustTitle}</p>
                  <p className="mt-2 text-sm leading-6 text-white/62">
                    {guestCommandConsoleCopy.trustBody}
                  </p>
                </section>
                <section
                  className="min-w-0 rounded-[12px] border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-panel)] px-4 py-3.5 sm:px-5"
                  data-testid="guest-home-preview-strip"
                >
                  <p className="text-[11px] font-medium text-white/40">{guestCommandConsoleCopy.previewTitle}</p>
                  <p className="mt-2 text-sm leading-6 text-white/62">
                    {guestCommandConsoleCopy.previewBody}
                  </p>
                </section>
              </div>
            </div>
          </section>
        ) : (() => {
          const readyCopy = dashboardData;
          const technicalSignals = homeChartContext
            ? [
                {
                  label: locale === 'en' ? 'TIMEFRAME' : '当前周期',
                  value: homeChartContext.timeframe,
                  rawValue: homeChartContext.timeframe,
                  tone: 'neutral' as const,
                  details: homeChartContext.sourceHint,
                },
                ...readyCopy.tech.signals,
              ]
            : readyCopy.tech.signals;
          const confidenceVisual = resolveConfidenceVisual(readyCopy.decision.confidenceValue, locale);
          const thesisCopy = readyCopy.decision.reasonBody || readyCopy.decision.summary || EMPTY_FIELD_VALUE;
          const stanceLabel = resolveLinearStanceLabel(locale, readyCopy.decision.signalLabel, readyCopy.decision.signalTone);
          const contextRailContent = isHomeAnalyzing ? (
            <div className="relative min-w-0 px-4 py-5 lg:px-5 lg:py-6">
              <InPlaceStrategySkeleton locale={locale} />
              <div className="grid gap-4 pt-4" data-testid="home-research-rail-loading-stack">
                <InPlaceListSkeleton locale={locale} kind="tech" />
                <InPlaceListSkeleton locale={locale} kind="fundamentals" />
              </div>
            </div>
          ) : (
            <LinearObservationPanel
              locale={locale}
              dashboard={readyCopy}
              dataQualityReport={activeDataQualityReport}
              isGuest={Boolean(isGuest)}
              guestPaywall={guestPaywall}
              onOpenStrategy={() => setActiveDrawer('strategy')}
              onOpenFundamentals={() => setActiveDrawer('fundamentals')}
            />
          );
          return (
            <div
              className="home-research-stage mx-auto flex w-full max-w-[1880px] min-w-0 flex-col gap-2.5 p-3 sm:px-4 xl:px-6 2xl:px-8"
              data-testid="home-research-stage"
            >
              {omnibarModule}
              <section
                data-testid="home-research-console"
                data-linear-primitive="research-console-shell"
                data-layout-zone="RouteConsole"
                data-route-console="ResearchConsole"
                data-visual-tier="dominant"
                data-surface-system="reflect-linear-console"
                className="relative isolate w-full max-w-full min-w-0 overflow-visible rounded-none border border-transparent bg-transparent shadow-none"
              >
                <div
                  className="relative z-10 min-w-0 overflow-visible"
                  data-linear-primitive="console-board"
                  data-surface-system="reflect-linear-console"
                  data-testid="home-research-board"
                >
                <FixedRegionGrid
                  className="home-research-fixed-grid w-full min-w-0 gap-3 overflow-visible"
                  data-surface-system="reflect-linear-console"
                  rail={contextRailContent}
                  railTestId="home-research-context-rail"
                  railWidth="lg"
                  primaryClassName="lg:pr-3"
                  railClassName="home-research-context-rail divide-y-0 self-start overflow-visible bg-transparent lg:border-l-0"
                  primary={(
                    <>
                    {!isHomeAnalyzing ? (
                      <div
                        className="mb-2.5 min-w-0 rounded-[8px] border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-panel)] px-5 py-4"
                        data-layout-zone="HeaderStrip"
                        data-testid="home-research-header-strip"
                      >
                        <div
                          className="flex min-w-0 flex-wrap items-start justify-between gap-4"
                          data-testid="home-bento-decision-company-header"
                        >
                          <div className="flex min-w-0 items-start gap-4">
                            {readyCopy.ticker === 'ORCL' ? (
                              <div
                                className="home-research-company-mark-oracle flex size-[72px] shrink-0 items-center justify-center rounded-[14px] border border-red-300/10 bg-[linear-gradient(145deg,#ff5b2d,#b51915)] shadow-[inset_0_1px_0_rgba(255,255,255,0.18),0_14px_34px_rgba(185,25,21,0.18)]"
                                data-testid="home-research-company-mark"
                                data-company-mark="oracle-logo"
                                aria-label="Oracle"
                              >
                                <span className="sr-only">{readyCopy.ticker.slice(0, 2)}</span>
                                <span className="h-5 w-11 rounded-full border-[5px] border-white/92" />
                              </div>
                            ) : (
                              <div
                                className="flex size-[72px] shrink-0 items-center justify-center rounded-[14px] border border-[color:var(--wolfy-border-subtle)] bg-[linear-gradient(145deg,rgba(118,109,219,0.34),rgba(23,31,54,0.92)_48%,rgba(75,94,172,0.28))] font-mono text-sm font-semibold text-white/88 shadow-[inset_0_1px_0_rgba(255,255,255,0.16)]"
                                data-testid="home-research-company-mark"
                                data-company-mark="fallback-monogram"
                                aria-hidden="true"
                              >
                                {readyCopy.ticker.slice(0, 2)}
                              </div>
                            )}
                            <div className="min-w-0 pt-1.5">
                              <div className="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-1">
                                <h1 className="min-w-0 truncate text-[30px] font-medium tracking-[0] text-white md:text-[34px]">
                                  {readyCopy.decision.company}
                                </h1>
                                <span
                                  className="font-mono text-sm text-white/42"
                                  data-testid="home-bento-decision-ticker"
                                >
                                  {readyCopy.ticker}
                                </span>
                              </div>
                              <p
                                className="mt-2 text-[12px] leading-5 text-white/42"
                                data-testid="home-bento-decision-sector"
                              >
                                {[resolveLinearSectorTrail(locale, readyCopy.decision.sector), readyCopy.sessionBadge, readyCopy.regimeBadge].filter(Boolean).join(' / ')}
                              </p>
                            </div>
                          </div>
                          {reportActionButtons ? (
                            <div
                              className="flex min-w-0 flex-wrap justify-start gap-2 lg:max-w-[28rem] lg:justify-end"
                              data-testid="home-bento-decision-header-actions"
                            >
                              <span className="sr-only">
                                {locale === 'en' ? 'Full Report Sources Copy report Rerun' : '完整报告 决策来源 复制报告 重新分析'}
                              </span>
                              {reportActionButtons}
                            </div>
                          ) : null}
                        </div>
                      </div>
                    ) : null}
                    <div
                      className="min-w-0 rounded-none border-0 bg-transparent p-0"
                      data-testid="home-research-primary-workspace"
                    >
                      {isHomeAnalyzing ? (
                        <InPlaceDecisionSkeleton
                          locale={locale}
                          ticker={pendingAnalysisTicker || activeTicker || readyCopy.ticker}
                          progressModules={focusedTask?.progressModules}
                          message={focusedTask?.message}
                          progress={focusedTask?.progress}
                        />
                      ) : (
                        <>
                        <div
                          className="min-w-0"
                          data-testid="home-bento-card-decision"
                          data-research-card="decision"
                        >
                          <div data-testid={completedTaskReport ? 'home-bento-analysis-result-card' : undefined}>
                            <HomeConclusionFirstConsole
                              locale={locale}
                              dashboard={readyCopy}
                              dataQualityReport={activeDataQualityReport}
                              decisionTrace={activeDecisionTrace}
                              sourceSummary={sourceSummary}
                              stanceLabel={stanceLabel}
                              thesisCopy={thesisCopy}
                              confidenceVisual={confidenceVisual}
                            />

                            <div className="mt-2.5" data-testid="home-bento-research-state-row">
                              <LinearKeyLevelsStrip metrics={readyCopy.strategy.metrics} locale={locale} />
                            </div>
                          </div>
                        </div>
                        {!isHomeAnalyzing ? (
                          <div className="mt-3 px-0" data-testid="home-research-chart-section">
                              <LinearTechnicalStructure
                                locale={locale}
                                ticker={readyCopy.ticker}
                                currentPrice={parseHomeChartPrice(activeTraceReport?.meta.currentPrice ?? activeTraceReport?.details?.standardReport?.summaryPanel?.currentPrice)}
                                signals={technicalSignals}
                                isGuest={Boolean(isGuest)}
                                shouldRenderHomeChart={shouldRenderHomeChart}
                                homeChartLoadingLabel={homeChartLoadingLabel}
                                guestPaywall={guestPaywall}
                                onOpenDetails={() => setActiveDrawer('tech')}
                                detailLabel={readyCopy.tech.detailLabel}
                                onChartContextChange={setHomeChartContext}
                              />
                          </div>
                        ) : null}
                        {!isHomeAnalyzing ? (
                          <div
                            className="home-research-secondary-deck mt-3 min-w-0 rounded-[14px] border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-panel)] px-4 py-2.5 md:px-5 md:py-2.5"
                            data-testid="home-research-secondary-deck"
                            data-linear-primitive="secondary-deck"
                            data-layout-zone="SecondaryDeck"
                          >
                            <LinearEventsStrip
                              locale={locale}
                              report={activeTraceReport}
                            />
                          </div>
                        ) : null}
                        </>
                      )}
                    </div>
                    </>
                  )}
                />
                </div>
              </section>
            </div>
          );
        })()}
      </main>

      <DeepReportDrawer
        isOpen={Boolean(activeDrawerPayload)}
        onClose={() => setActiveDrawer(null)}
        title={activeDrawerPayload?.title || ''}
        modules={activeDrawerPayload?.modules || []}
        testId="home-bento-drawer"
      />

      {isFullReportDrawerOpen ? (
        <Suspense fallback={<FullDecisionReportDrawerFallback onClose={() => setFullReportDrawerOpen(false)} />}>
          <LazyFullDecisionReportDrawer
            isOpen={isFullReportDrawerOpen}
            onClose={() => setFullReportDrawerOpen(false)}
            report={activeTraceReport}
            dashboard={dashboardData}
          />
        </Suspense>
      ) : null}

      <Drawer
        isOpen={isTraceDrawerOpen}
        onClose={() => setTraceDrawerOpen(false)}
        title={locale === 'en' ? 'Decision Trace' : '决策来源'}
        width="max-w-xl"
        zIndex={90}
        bodyClassName="overflow-x-hidden"
      >
        <DecisionTracePanel
          trace={activeDecisionTrace}
          locale={locale}
          quality={activeReportQuality}
          dataQualityReport={activeDataQualityReport}
          sourceSummary={sourceSummary}
        />
      </Drawer>

      <Drawer
        isOpen={isHistoryDrawerOpen}
        onClose={() => setHistoryDrawerOpen(false)}
        title={locale === 'en' ? 'Analysis History' : '历史记录'}
        width="max-w-lg"
      >
        <div className="flex flex-col gap-3" data-testid="home-bento-history-drawer">
          {recentHistoryItems.length > 0 ? (
            <div className="flex items-center justify-between gap-3 rounded-2xl border border-white/5 bg-white/[0.02] px-4 py-3">
              <div className="min-w-0">
                <p className="text-[11px] uppercase tracking-[0.18em] text-white/40">
                  {deleteCopy.visibleCount}
                </p>
                <p className="mt-1 text-sm text-white/72">
                  {recentHistoryItems.length}
                </p>
              </div>
              <Button
                type="button"
                variant="danger-subtle"
                size="sm"
                disabled={isDeletingHistory}
                className="shrink-0"
                onClick={() => setPendingHistoryDelete({
                  mode: 'visible',
                  recordIds: recentHistoryItems.map((item) => item.id),
                })}
                data-testid="home-bento-history-delete-all"
              >
                {isDeletingHistory ? deleteCopy.deleting : deleteCopy.clearVisible}
              </Button>
            </div>
          ) : null}
          {recentHistoryItems.length > 0 ? recentHistoryItems.map((item) => {
            const ticker = normalizeTickerQuery(item.stockCode);
            const isSelected = selectedReport?.meta.id === item.id;
            const generatedAt = resolveHistoryGeneratedAt(item, locale);
            const companyLabel = resolveHistoryCompanyLabel(item);
            const shouldShowTickerMeta = ticker && companyLabel.toUpperCase() !== ticker;
            const itemQuality = item.reportQuality || reportQualityFallback();
            const historyQualityLabels = [
              reportQualityUserLabel(itemQuality.userLabel, locale),
              traceQualityLabel(itemQuality.traceStatus, locale),
              reportQualityLabel(itemQuality.reportStatus, locale),
              itemQuality.schemaStatus === 'ok' || itemQuality.schemaStatus === 'unconfirmed'
                ? schemaQualityLabel(itemQuality.schemaStatus, locale)
                : null,
            ].filter(Boolean) as string[];
            return (
              <div
                key={item.id}
                className={`flex min-w-0 items-center gap-3 rounded-2xl border p-3 transition-colors ${
                  isSelected
                    ? 'border-white/15 bg-white/[0.08] text-white'
                    : 'border-white/5 bg-white/[0.02] text-white/72 hover:bg-white/[0.05]'
                }`}
              >
                <button
                  type="button"
                  className="flex min-w-0 flex-1 items-center justify-between gap-4 text-left"
                  onClick={() => { void handleHistoryClick(item); }}
                  data-testid={`home-bento-history-item-${item.id}`}
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold">{companyLabel}</p>
                    <p className="mt-1 truncate text-[11px] uppercase tracking-[0.16em] text-white/40">
                      {shouldShowTickerMeta ? `${ticker} · ` : ''}{locale === 'en' ? 'Recent analysis' : '最近分析'}
                    </p>
                    {generatedAt ? (
                      <p className="mt-1 truncate text-[11px] text-white/45">
                        {generatedAt}
                      </p>
                    ) : null}
                    <div className="mt-2 flex min-w-0 max-w-full flex-wrap gap-1.5" data-testid={`home-bento-history-quality-${item.id}`}>
                      {historyQualityLabels.map((label) => (
                        <ReportQualityChip key={`${item.id}-${label}`} label={label} />
                      ))}
                    </div>
                  </div>
                  <span className="shrink-0 text-[10px] uppercase tracking-[0.16em] text-white/35">
                    {isSelected ? (locale === 'en' ? 'Loaded' : '当前') : (locale === 'en' ? 'Open' : '打开')}
                  </span>
                </button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={isDeletingHistory}
                  className="shrink-0 border border-white/8 bg-white/[0.03] px-3 text-white/62 hover:border-rose-400/30 hover:bg-rose-400/10 hover:text-rose-100"
                  onClick={() => setPendingHistoryDelete({ mode: 'single', recordIds: [item.id] })}
                  data-testid={`home-bento-history-delete-${item.id}`}
                >
                  {deleteCopy.deleteOne}
                </Button>
              </div>
            );
          }) : (
            <div className="rounded-2xl border border-white/5 bg-white/[0.02] px-4 py-5 text-sm text-white/48">
              {locale === 'en' ? 'No synced analysis history yet.' : '历史分析尚未同步。'}
            </div>
          )}
        </div>
      </Drawer>

      <ConfirmDialog
        isOpen={Boolean(pendingHistoryDelete)}
        title={deleteCopy.title}
        message={
          pendingHistoryDelete
            ? pendingHistoryDelete.mode === 'single'
              ? deleteCopy.single
              : deleteCopy.multiple(pendingHistoryDelete.recordIds.length)
            : deleteCopy.single
        }
        confirmText={isDeletingHistory ? deleteCopy.deleting : deleteCopy.confirm}
        cancelText={deleteCopy.cancel}
        isDanger
        onConfirm={() => { void handleConfirmDeleteHistory(); }}
        onCancel={() => {
          if (!isDeletingHistory) {
            setPendingHistoryDelete(null);
          }
        }}
      />
    </div>
  );
};

export default HomeBentoDashboardPage;
