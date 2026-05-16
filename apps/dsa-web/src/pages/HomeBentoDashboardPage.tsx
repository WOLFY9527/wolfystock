import type React from 'react';
import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Copy, FileSearch, Lock, RefreshCw, Search } from 'lucide-react';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { publicAnalysisApi } from '../api/publicAnalysis';
import { normalizeReportQuality } from '../api/reportNormalizer';
import { withFallback } from '../api/withFallback';
import {
  BENTO_SURFACE_ROOT_CLASS,
  DeepReportDrawer,
  type SignalTone,
} from '../components/home-bento';
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

function traceQualityLabel(status: ReportQuality['traceStatus']): string {
  if (status === 'present') return '决策依据可查看';
  if (status === 'partial') return '依据部分可用';
  if (status === 'missing') return '缺少决策依据';
  return '依据未确认';
}

function schemaQualityLabel(status: ReportQuality['schemaStatus']): string {
  if (status === 'ok') return '结果已整理';
  if (status === 'unconfirmed') return '依据需复核';
  if (status === 'missing') return '结果待整理';
  return '依据需复核';
}

function summaryQualityLabel(status: ReportQuality['summaryStatus']): string {
  if (status === 'complete') return '摘要可读';
  if (status === 'partial') return '摘要部分可用';
  return '摘要缺失';
}

function reportQualityLabel(status: ReportQuality['reportStatus']): string {
  if (status === 'complete') return '报告可读';
  if (status === 'partial') return '报告部分可用';
  return '报告缺失';
}

function qualityChipTone(label: string): 'neutral' | 'used' | 'warning' | 'missing' {
  if (/可信度较高|可查看|可读|已整理|可用/.test(label) && !/部分|未确认|复核/.test(label)) {
    return 'used';
  }
  if (/缺失|失败|缺少/.test(label)) {
    return 'missing';
  }
  if (/部分|旧版|未确认|未知|复核|待整理/.test(label)) {
    return 'warning';
  }
  return 'neutral';
}

function ReportQualityChip({ label }: { label: string }) {
  return <TraceBadge tone={qualityChipTone(label)}>{label}</TraceBadge>;
}

function buildQualityStatusSummary(quality: ReportQuality): string {
  return [
    quality.userLabel === '完整' ? '可信度较高' : quality.userLabel,
    traceQualityLabel(quality.traceStatus),
    schemaQualityLabel(quality.schemaStatus),
    summaryQualityLabel(quality.summaryStatus),
  ].join(' · ');
}

function buildTraceSummary(trace?: DecisionTrace, quality?: ReportQuality): string {
  const qualitySummary = quality ? buildQualityStatusSummary(quality) : '';
  if (!trace) {
    return qualitySummary || '未包含决策溯源';
  }
  const sourceCount = trace.dataSources?.length || 0;
  const usedCount = (trace.dataSources || []).filter((source) => String(source.status || '').toLowerCase() === 'used').length;
  const conflictCount = trace.conflicts?.length || 0;
  const dataLabel = sourceCount === 0
    ? '数据覆盖未确认'
    : usedCount === 0
      ? '数据不足，结论仅供观察'
      : usedCount < sourceCount
        ? '部分数据可用'
        : '数据覆盖较充分';
  const conflictLabel = conflictCount > 0 ? '存在需复核的证据冲突' : '未发现主要证据冲突';
  const schemaLabel = trace.llm?.schemaValidated ? null : '依据需复核';
  return [
    qualitySummary,
    dataLabel,
    conflictLabel,
    schemaLabel,
  ].filter(Boolean).join(' · ');
}

function DecisionTracePanel({ trace, locale, quality }: { trace?: DecisionTrace; locale: DashboardLocale; quality?: ReportQuality }) {
  if (!trace) {
    return (
      <div className="min-w-0 space-y-3" data-testid="home-bento-decision-trace-panel">
        <div className="min-w-0 rounded-2xl border border-white/8 bg-white/[0.025] p-4 text-sm text-white/56">
          当前分析未包含决策溯源
        </div>
        {quality ? (
          <div
            className="rounded-2xl border border-amber-300/15 bg-amber-300/8 p-4 text-sm text-amber-50/80"
            data-testid="home-bento-decision-trace-data-note"
          >
            {quality.missingFields.length
              ? quality.missingFields.map((item) => sanitizeUserFacingDataIssue(item, locale)).join('、')
              : '数据不足，结论仅供观察'}
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
      <div className="rounded-2xl border border-white/8 bg-white/[0.025] p-4">
        <p className={sectionTitleClass}>{isEnglish ? 'Decision Fields' : '决策字段'}</p>
        <div className="mt-3 grid min-w-0 grid-cols-1 gap-2 sm:grid-cols-2">
          {decisionFields.map(([name, field]) => (
            <div key={name} className="min-w-0 rounded-xl border border-white/6 bg-black/10 px-3 py-2">
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
            <div key={`${source.name}-${index}`} className="flex min-w-0 flex-wrap items-center justify-between gap-2 rounded-xl border border-white/6 bg-black/10 px-3 py-2">
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

function enrichmentStatusLabel(status: string | undefined, locale: DashboardLocale): string {
  const normalized = String(status || '').trim().toLowerCase();
  const zh: Record<string, string> = {
    pending: '增强数据补充中',
    partial: '部分缺失',
    complete: '已完成',
    skipped: '已跳过',
    failed: '部分缺失',
  };
  const en: Record<string, string> = {
    pending: 'Enrichment in progress',
    partial: 'Partially missing',
    complete: 'Complete',
    skipped: 'Skipped',
    failed: 'Partially missing',
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

function dataQualityFieldLabel(value: string, locale: DashboardLocale): string {
  const normalized = String(value || '').trim().toLowerCase();
  if (!normalized) return locale === 'en' ? 'Unconfirmed data gap' : '数据缺口未确认';
  return sanitizeUserFacingDataIssue(normalized, locale);
}

function dataQualityReasonLabel(value: string, locale: DashboardLocale): string {
  const normalized = String(value || '').trim().toLowerCase();
  if (!normalized) return locale === 'en' ? 'Reason unconfirmed' : '原因未确认';
  return sanitizeUserFacingDataIssue(normalized, locale);
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

function buildDataQualityChipLabel(report: DataQualityReport | undefined, locale: DashboardLocale, confidenceValue?: string): string | null {
  if (!report) return null;
  const isEnglish = locale === 'en';
  const qualityText = report.requiredAvailable === false || report.dataQualityTier === 'insufficient'
    ? (isEnglish ? 'Limited data' : '数据不足')
    : hasDataQualityGaps(report)
      ? (isEnglish ? 'Partial data' : '部分数据')
      : (isEnglish ? 'Ready data' : '数据充分');
  const confidenceText = String(confidenceValue || '').trim();
  if (!confidenceText || confidenceText === '-') {
    return qualityText;
  }
  return `${qualityText} / ${isEnglish ? 'conviction' : '置信度'}${confidenceText}`;
}

function buildDataQualityPreview(report: DataQualityReport, locale: DashboardLocale): string {
  const isEnglish = locale === 'en';
  if (report.requiredAvailable === false) {
    return isEnglish ? 'Critical market data is missing. Read the report as observation only.' : '关键行情数据缺失，当前结论仅供观察。';
  }
  if (report.importantMissing?.length) {
    return `${isEnglish ? 'Critical gap' : '关键缺口'}：${report.importantMissing.slice(0, 2).map((item) => dataQualityFieldLabel(item, locale)).join('、')}`;
  }
  if (report.providerTimeouts?.length || report.providerCooldowns?.length) {
    return isEnglish ? 'Some external feeds are temporarily degraded.' : '部分外部数据源暂时降级。';
  }
  if (report.optionalMissing?.length || report.pendingSources?.length || report.failedSources?.length || report.skippedSources?.length) {
    return isEnglish ? 'Optional enrichment is still incomplete.' : '可选增强数据仍未完全补齐。';
  }
  return isEnglish ? 'Data coverage looks stable.' : '当前数据覆盖稳定。';
}

function AnalysisDiagnosticsDisclosure({
  report,
  locale,
  sourceSummary,
}: {
  report: DataQualityReport | undefined;
  locale: DashboardLocale;
  sourceSummary?: string;
}) {
  const [isOpen, setIsOpen] = useState(false);
  if (!report && !sourceSummary) return null;

  const isEnglish = locale === 'en';
  const preview = report ? buildDataQualityPreview(report, locale) : sourceSummary || '';
  const quickDecisionText = report?.requiredAvailable === false
    ? (isEnglish ? 'Fast decision is limited' : '快速判断受限')
    : (isEnglish ? 'Fast decision complete' : '快速判断已完成');
  const missingCritical = !report
    ? (isEnglish ? 'No structured quality report' : '暂无结构化质量报告')
    : report.requiredAvailable === false
      ? (isEnglish ? 'Required quote/candle data missing' : '缺失关键行情或 K 线数据')
      : report.importantMissing?.slice(0, 3).map((item) => dataQualityFieldLabel(item, locale)).join('、') || (isEnglish ? 'No required gaps' : '关键数据已满足');
  const enrichmentGaps = report ? summarizeEnrichmentGaps(report) : [];
  const enrichmentReasons = report ? summarizeEnrichmentReasons(report).map((item) => dataQualityReasonLabel(item, locale)) : [];
  const optionalText = !report ? (sourceSummary || (isEnglish ? 'No enrichment notes' : '暂无增强说明')) : [
    enrichmentStatusLabel(report.enrichmentStatus, locale),
    enrichmentGaps.length
      ? `${isEnglish ? 'Missing' : '缺失项'}：${enrichmentGaps.map((item) => dataQualityFieldLabel(item, locale)).join('、')}`
      : (isEnglish ? 'No visible enrichment gaps' : '暂无可见增强缺口'),
    enrichmentReasons.length
      ? `${isEnglish ? 'Reasons' : '原因'}：${enrichmentReasons.join('、')}`
      : null,
    report.providerTimeouts?.length || report.providerCooldowns?.length
      ? (isEnglish ? 'Some external data is temporarily unavailable' : '部分外部数据暂不可用')
      : null,
  ].filter(Boolean).join(' · ');

  return (
    <section className="rounded-lg border border-white/[0.055] bg-white/[0.012] px-3 py-2.5" data-testid="home-bento-analysis-diagnostics">
      <button
        type="button"
        className="flex w-full min-w-0 flex-col gap-2 text-left sm:flex-row sm:items-center sm:justify-between"
        aria-expanded={isOpen}
        data-testid="home-bento-analysis-diagnostics-toggle"
        onClick={() => setIsOpen((current) => !current)}
      >
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-white/38">
            {isEnglish ? 'Data status' : '数据状态'}
          </p>
          <p className="mt-0.5 line-clamp-2 text-xs font-medium leading-5 tracking-[0] text-white/68">
            {preview}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {report ? (
            <>
              <TraceBadge tone={dataQualityChipTone(report)}>
                {dataQualityTierLabel(report.dataQualityTier, locale)}
              </TraceBadge>
              <TraceBadge tone={report.confidenceCap !== undefined && report.confidenceCap < 75 ? 'warning' : 'neutral'}>
                {isEnglish ? 'Cap' : '上限'} {report.confidenceCap ?? '--'}
              </TraceBadge>
            </>
          ) : null}
          <span className="text-[10px] font-semibold uppercase tracking-[0.22em] text-white/34">
            {isOpen ? (isEnglish ? 'Hide' : '收起') : (isEnglish ? 'Open' : '展开')}
          </span>
        </div>
      </button>

      {isOpen ? (
        <div className="mt-3 min-w-0 divide-y divide-white/[0.055] border-t border-white/[0.055]" data-testid="home-bento-analysis-diagnostics-panel">
          <div className="grid min-w-0 gap-1 py-2.5 sm:grid-cols-[9rem_minmax(0,1fr)]">
            <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-white/38">
              {isEnglish ? 'Critical gaps' : '关键缺失'}
            </p>
            <div className="min-w-0">
              <p className="text-xs font-semibold text-emerald-200/80">{quickDecisionText}</p>
              <p className="mt-1 break-words text-xs leading-5 text-white/68">{missingCritical}</p>
            </div>
          </div>
          <div className="grid min-w-0 gap-1 py-2.5 sm:grid-cols-[9rem_minmax(0,1fr)]">
            <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-white/38">
              {isEnglish ? 'Enrichment' : '增强状态'}
            </p>
            <p className="min-w-0 break-words text-xs leading-5 text-white/68">{optionalText}</p>
          </div>
          {sourceSummary ? (
            <div className="grid min-w-0 gap-1 py-2.5 sm:grid-cols-[9rem_minmax(0,1fr)]">
              <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-white/38">
                {isEnglish ? 'Source' : '来源'}
              </p>
              <p className="min-w-0 break-words text-xs leading-5 text-white/68">{sourceSummary}</p>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function isEmptyDashboardValue(value?: string | null): boolean {
  const text = String(value || '').trim();
  return !text || text === EMPTY_FIELD_VALUE || /^n\/?a$/i.test(text);
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

function normalizeLinearScore(value?: string): number {
  const numeric = Number.parseFloat(String(value || '').replace(/[^\d.-]/g, ''));
  if (!Number.isFinite(numeric)) {
    return 0;
  }
  return Math.max(0, Math.min(100, numeric));
}

function resolveLinearStanceLabel(locale: DashboardLocale, signalLabel: string, tone: SignalTone): string {
  const text = String(signalLabel || '').trim();
  if (isEmptyDashboardValue(text)) {
    return EMPTY_FIELD_VALUE;
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
  const entryAliases = locale === 'en' ? ['watch zone', 'entry zone'] : ['观察区间', '建仓区间'];
  const targetAliases = locale === 'en' ? ['upper watch zone', 'target'] : ['上方观察区', '目标位'];
  const stopAliases = locale === 'en' ? ['invalidation line', 'stop'] : ['风险失效线', '止损位'];
  const findByAliases = (aliases: string[]) => metrics.find((metric) => aliases.includes(metric.label.trim().toLowerCase()) || aliases.includes(metric.label.trim()));
  return [
    findByAliases(entryAliases),
    findByAliases(stopAliases),
    findByAliases(targetAliases),
  ].filter(Boolean) as DashboardField[];
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
      className="grid min-w-0 grid-cols-1 overflow-hidden rounded-md border border-white/[0.055] bg-white/[0.012] sm:grid-cols-3"
      data-testid="home-linear-key-levels"
    >
      {levels.map((metric, index) => (
        <div
          key={metric.label}
          className={cn(
            'min-w-0 px-4 py-3',
            index > 0 ? 'border-t border-white/[0.055] sm:border-l sm:border-t-0' : '',
          )}
          data-testid={`home-bento-strategy-metric-${metric.label}`}
        >
          <p className="truncate text-[11px] font-medium tracking-[0] text-white/42">{getMetricLabelForStrip(locale, metric.label)}</p>
          <p
            className={cn('mt-1 truncate font-mono text-sm font-semibold', metricValueClass(metric, marketColorConvention))}
            style={toneTextStyle(metric.tone || 'neutral', marketColorConvention)}
          >
            {metric.value}
          </p>
        </div>
      ))}
    </div>
  );
}

function LinearTechnicalStructure({
  locale,
  signals,
  isGuest,
  guestPaywall,
  onOpenDetails,
  detailLabel,
}: {
  locale: DashboardLocale;
  signals: DashboardSignal[];
  isGuest: boolean;
  guestPaywall?: React.ReactNode;
  onOpenDetails: () => void;
  detailLabel: string;
}) {
  const { marketColorConvention } = useUiPreferences();
  const {
    ref: openDetailsButtonRef,
    onClick: handleOpenDetailsClick,
    onPointerUp: handleOpenDetailsPointerUp,
  } = useSafariWarmActivation<HTMLButtonElement>(onOpenDetails);
  const chartTone = signals.find((signal) => signal.tone !== 'neutral')?.tone || 'neutral';
  const accentColor = chartTone === 'bearish' ? '#FB7185' : '#34D399';
  const chartTop = 28;
  const chartBottom = 176;
  const priceMin = 170;
  const priceMax = 210;
  const priceToY = (price: number) => chartBottom - ((price - priceMin) / (priceMax - priceMin)) * (chartBottom - chartTop);
  const chartTimeLabels = locale === 'en'
    ? ['Dec', '2024', 'Feb', 'Mar', 'Apr', 'May']
    : ['12月', '2024', '2月', '3月', '4月', '5月'];
  const candleSeries = [
    { x: 34, open: 179, close: 181, high: 183, low: 176 },
    { x: 58, open: 181, close: 178, high: 184, low: 176 },
    { x: 82, open: 178, close: 182, high: 184, low: 177 },
    { x: 106, open: 182, close: 186, high: 188, low: 180 },
    { x: 130, open: 186, close: 184, high: 189, low: 182 },
    { x: 154, open: 184, close: 188, high: 190, low: 183 },
    { x: 178, open: 188, close: 191, high: 194, low: 186 },
    { x: 202, open: 191, close: 193, high: 196, low: 190 },
    { x: 226, open: 193, close: 192, high: 197, low: 190 },
    { x: 250, open: 192, close: 196, high: 198, low: 190 },
    { x: 274, open: 196, close: 199, high: 202, low: 195 },
    { x: 298, open: 199, close: 201, high: 204, low: 197 },
    { x: 322, open: 201, close: 198, high: 203, low: 196 },
    { x: 346, open: 198, close: 200, high: 203, low: 195 },
    { x: 370, open: 200, close: 202, high: 205, low: 198 },
    { x: 394, open: 202, close: 198, high: 204, low: 196 },
    { x: 418, open: 198, close: 194, high: 199, low: 190 },
    { x: 442, open: 194, close: 190, high: 195, low: 187 },
    { x: 466, open: 190, close: 188, high: 192, low: 184 },
    { x: 490, open: 188, close: 192, high: 194, low: 186 },
    { x: 514, open: 192, close: 195, high: 197, low: 190 },
    { x: 538, open: 195, close: 193, high: 197, low: 191 },
    { x: 562, open: 193, close: 194, high: 196, low: 191 },
    { x: 586, open: 194, close: 196, high: 198, low: 193 },
  ];
  const currentPriceY = priceToY(196);

  return (
    <section
      className="relative min-w-0 border-t border-white/[0.055] pt-5"
      data-testid="home-bento-card-tech"
      data-research-card="risk-context"
    >
      <div className="mb-3 flex min-w-0 flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold tracking-[0] text-white">{locale === 'en' ? 'Technical Structure' : '技术结构'}</p>
          <p className="mt-1 text-xs text-white/40">{locale === 'en' ? 'Structure view, not a live tick chart.' : '结构视图，不替代实时分时图。'}</p>
        </div>
        <button
          ref={openDetailsButtonRef}
          type="button"
          className="text-xs font-medium text-white/42 transition-colors hover:text-white"
          data-testid="home-bento-drawer-trigger-tech"
          onClick={handleOpenDetailsClick}
          onPointerUp={handleOpenDetailsPointerUp}
        >
          {detailLabel}
        </button>
      </div>
      <div
        className={cn(
          'grid min-w-0 gap-4 md:grid-cols-[minmax(0,1fr)_minmax(210px,260px)]',
          isGuest ? 'pointer-events-none opacity-80' : '',
        )}
      >
        <div className="min-w-0 rounded-md border border-white/[0.055] bg-[#070b10]/82 px-3 py-3" data-testid="home-linear-technical-chart">
          <div className="mb-2 flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-[10px] font-medium text-white/46">
              {['1D', '1W', '1M', '3M', '1Y'].map((range, index) => (
                <span key={range} className={cn('rounded px-2 py-1', index === 0 ? 'bg-white/[0.08] text-white/82' : '')}>{range}</span>
              ))}
            </div>
            <div className="hidden items-center gap-3 text-[10px] text-white/38 sm:flex">
              <span><span className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-[#38BDF8]" />MA5</span>
              <span><span className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-[#F59E0B]" />MA20</span>
              <span><span className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-[#8B5CF6]" />MA60</span>
            </div>
          </div>
          <svg viewBox="0 0 640 218" role="img" aria-label={locale === 'en' ? 'Technical structure map' : '技术结构示意'} className="h-[190px] w-full overflow-visible">
            <defs>
              <linearGradient id="home-linear-chart-fill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor={accentColor} stopOpacity="0.18" />
                <stop offset="100%" stopColor={accentColor} stopOpacity="0" />
              </linearGradient>
            </defs>
            <rect x="0" y="18" width="600" height="166" rx="8" fill="rgba(255,255,255,.012)" />
            {[chartTop, 65, 102, 139, chartBottom].map((y) => (
              <line key={y} x1="16" x2="600" y1={y} y2={y} stroke="rgba(255,255,255,.055)" strokeWidth="1" />
            ))}
            {[210, 200, 190, 180].map((price) => (
              <text key={price} x="608" y={priceToY(price) + 3} fill="rgba(255,255,255,.42)" fontSize="10" fontFamily="ui-monospace, SFMono-Regular, Menlo, monospace">
                {price.toFixed(0)}
              </text>
            ))}
            {chartTimeLabels.map((label, index) => (
              <text key={label} x={34 + index * 104} y="207" fill="rgba(255,255,255,.36)" fontSize="10">
                {label}
              </text>
            ))}
            <line x1="16" x2="600" y1={currentPriceY} y2={currentPriceY} stroke={accentColor} strokeOpacity="0.48" strokeDasharray="3 5" />
            <rect x="558" y={currentPriceY - 10} width="42" height="17" rx="3" fill={accentColor} opacity="0.86" />
            <text x="564" y={currentPriceY + 2} fill="#061018" fontSize="10" fontFamily="ui-monospace, SFMono-Regular, Menlo, monospace" fontWeight="700">
              196.0
            </text>
            {candleSeries.map((candle) => {
              const up = candle.close >= candle.open;
              const highY = priceToY(candle.high);
              const lowY = priceToY(candle.low);
              const openY = priceToY(candle.open);
              const closeY = priceToY(candle.close);
              const bodyY = Math.min(openY, closeY);
              const bodyHeight = Math.max(3, Math.abs(openY - closeY));
              return (
                <g key={candle.x}>
                  <line x1={candle.x} x2={candle.x} y1={highY} y2={lowY} stroke={up ? '#34D399' : '#FB7185'} strokeOpacity="0.82" strokeWidth="1" />
                  <rect x={candle.x - 4} y={bodyY} width="8" height={bodyHeight} rx="1.5" fill={up ? '#34D399' : '#FB7185'} opacity="0.88" />
                </g>
              );
            })}
            <path d="M20 150 C86 146 132 136 188 129 C254 120 318 100 374 104 C442 110 512 129 600 118" fill="none" stroke="#38BDF8" strokeOpacity="0.86" strokeWidth="1.7" />
            <path d="M20 158 C96 150 166 143 236 132 C312 121 378 116 444 119 C512 122 560 124 600 116" fill="none" stroke="#F59E0B" strokeOpacity="0.78" strokeWidth="1.45" />
            <path d="M20 166 C96 160 170 154 246 145 C328 136 396 129 468 128 C530 127 570 124 600 120" fill="none" stroke="#8B5CF6" strokeOpacity="0.46" strokeWidth="1.25" />
          </svg>
        </div>
        <div
          className="min-w-0 divide-y divide-white/[0.055] rounded-md border border-white/[0.055] bg-white/[0.01] px-3 py-2"
          data-testid="home-bento-decision-support-grid"
        >
          {signals.map((signal) => {
            const muted = isEmptyDashboardValue(signal.value);
            const valueClass = muted ? 'text-white/28' : toneTextClass(signal.tone, marketColorConvention);
            return (
              <div
                key={signal.label}
                className="flex min-w-0 flex-col gap-1 py-2 first:pt-0 last:pb-0"
                data-testid={`home-bento-tech-signal-${signal.label}`}
              >
                <div className="flex min-w-0 items-center justify-between gap-3">
                  <span className="truncate text-[11px] font-medium tracking-[0] text-white/44">{signal.label}</span>
                  <span
                    className={cn('min-w-0 truncate text-right text-xs font-semibold', valueClass)}
                    style={toneTextStyle(signal.tone, marketColorConvention)}
                  >
                    {signal.value}
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
  sourceSummary,
  isGuest,
  guestPaywall,
  onOpenStrategy,
  onOpenFundamentals,
}: {
  locale: DashboardLocale;
  dashboard: DashboardPayload;
  dataQualityReport?: DataQualityReport;
  sourceSummary?: string;
  isGuest: boolean;
  guestPaywall?: React.ReactNode;
  onOpenStrategy: () => void;
  onOpenFundamentals: () => void;
}) {
  const { marketColorConvention } = useUiPreferences();
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
  const qualityPreview = dataQualityReport
    ? buildDataQualityPreview(dataQualityReport, locale)
    : sourceSummary || (isEnglish ? 'Data quality not yet confirmed.' : '数据质量仍待确认。');

  return (
    <aside
      className="relative min-w-0 border-t border-white/[0.055] px-4 py-5 lg:border-l lg:border-t-0 lg:px-7 lg:py-7"
      data-testid="home-bento-secondary-stack"
    >
      <section className="min-w-0" data-testid="home-bento-card-strategy" data-research-card="opportunity">
        <div className="mb-4 flex min-w-0 items-center justify-between gap-3">
          <h2 className="text-sm font-semibold tracking-[0] text-white">{isEnglish ? 'Observation Framework' : '观察框架'}</h2>
          <button
            ref={openStrategyButtonRef}
            type="button"
            className="text-xs font-medium text-white/42 transition-colors hover:text-white"
            data-testid="home-bento-drawer-trigger-strategy"
            onClick={handleOpenStrategyClick}
            onPointerUp={handleOpenStrategyPointerUp}
          >
            {dashboard.strategy.detailLabel}
          </button>
        </div>
        <div className="divide-y divide-white/[0.07]">
          {dashboard.strategy.metrics.map((metric) => (
            <div key={metric.label} className="flex min-w-0 items-center justify-between gap-4 py-3">
              <span className="truncate text-xs text-white/44">{getMetricLabelForStrip(locale, metric.label)}</span>
              <span
                className={cn('min-w-0 truncate text-right font-mono text-xs font-semibold', metricValueClass(metric, marketColorConvention))}
                style={toneTextStyle(metric.tone || 'neutral', marketColorConvention)}
              >
                {metric.value}
              </span>
            </div>
          ))}
          <div className="py-3">
            <p className="text-xs text-white/44">{dashboard.strategy.positionLabel}</p>
            <p className="mt-1 text-xs leading-5 text-white/62">{dashboard.strategy.positionBody}</p>
          </div>
        </div>
      </section>

      <section
        className="mt-5 min-w-0 border-t border-white/[0.055] pt-5"
        data-testid="home-bento-card-fundamentals"
        data-research-card="data-context"
      >
        <div className="mb-4 flex min-w-0 items-center justify-between gap-3">
          <h2 className="text-sm font-semibold tracking-[0] text-white">{isEnglish ? 'Data Quality' : '数据质量与说明'}</h2>
          <button
            ref={openFundamentalsButtonRef}
            type="button"
            className="text-xs font-medium text-white/42 transition-colors hover:text-white"
            data-testid="home-bento-drawer-trigger-fundamentals"
            onClick={handleOpenFundamentalsClick}
            onPointerUp={handleOpenFundamentalsPointerUp}
          >
            {dashboard.fundamentals.detailLabel}
          </button>
        </div>
        <div className="divide-y divide-white/[0.055] border-y border-white/[0.055]" data-testid="home-linear-quality-summary">
          <p className="py-2.5 text-xs leading-5 text-white/62">{qualityPreview}</p>
          {[
            { label: isEnglish ? 'Completeness' : '数据完整度', active: dataQualityReport?.requiredAvailable !== false },
            { label: isEnglish ? 'Reliability' : '覆盖可靠性', active: !dataQualityReport || !hasDataQualityGaps(dataQualityReport) },
            { label: isEnglish ? 'Actionable' : '财报有效性', active: Boolean(!dataQualityReport?.importantMissing?.length) },
          ].map((item) => (
            <div key={item.label} className="grid grid-cols-[6.5rem_minmax(0,1fr)_2.5rem] items-center gap-3 py-2.5 text-[11px]">
              <span className="truncate text-white/40">{item.label}</span>
              <span className="h-1 overflow-hidden rounded-full bg-white/[0.055]">
                <span className={cn('block h-full rounded-full', item.active ? 'w-4/5 bg-white/50' : 'w-2/5 bg-amber-300/58')} />
              </span>
              <span className="text-right text-white/54">{item.active ? (isEnglish ? 'High' : '高') : (isEnglish ? 'Mid' : '中')}</span>
            </div>
          ))}
        </div>
        <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3">
          {dashboard.fundamentals.metrics.map((metric) => (
            <div key={metric.label} className="min-w-0" data-testid={`home-bento-fundamental-metric-${metric.label}`}>
              <p className="truncate text-[11px] text-white/38">{metric.label}</p>
              <p className={cn('mt-1 truncate font-mono text-sm font-semibold', isEmptyDashboardValue(metric.value) ? 'text-white/28' : 'text-white/78')}>{metric.value}</p>
            </div>
          ))}
        </div>
      </section>
      {isGuest ? guestPaywall : null}
    </aside>
  );
}

function LinearEventsStrip({
  locale,
  dashboard,
  dataQualityReport,
  sourceSummary,
}: {
  locale: DashboardLocale;
  dashboard: DashboardPayload;
  dataQualityReport?: DataQualityReport;
  sourceSummary?: string;
}) {
  const isEnglish = locale === 'en';
  const qualityText = dataQualityReport ? buildDataQualityPreview(dataQualityReport, locale) : sourceSummary;
  const events = [
    {
      label: isEnglish ? 'Report thesis' : '报告主线',
      title: dashboard.decision.badge,
      detail: dashboard.decision.summary,
      importance: isEnglish ? 'High' : '高',
      time: isEnglish ? 'Current' : '当前',
    },
    {
      label: isEnglish ? 'Technical check' : '技术验证',
      title: dashboard.tech.signals[0]?.label || dashboard.tech.title,
      detail: dashboard.tech.signals[0]?.details || dashboard.tech.signals[0]?.value || EMPTY_FIELD_VALUE,
      importance: isEnglish ? 'Medium' : '中',
      time: isEnglish ? 'Watching' : '跟踪',
    },
    {
      label: isEnglish ? 'Data status' : '数据状态',
      title: dataQualityReport ? dataQualityTierLabel(dataQualityReport.dataQualityTier, locale) : (isEnglish ? 'Unconfirmed' : '未确认'),
      detail: qualityText || (isEnglish ? 'No structured quality notes yet.' : '暂无结构化质量说明。'),
      importance: isEnglish ? 'Medium' : '中',
      time: isEnglish ? 'Continuous' : '持续跟踪',
    },
  ];

  return (
    <section className="min-w-0 rounded-lg border border-white/[0.055] bg-white/[0.012] px-4 py-3" data-testid="home-linear-events">
      <div className="grid min-w-0 gap-1 border-b border-white/[0.055] pb-2 md:grid-cols-[minmax(0,1fr)_8rem_8rem]">
        <h2 className="text-sm font-semibold text-white">{isEnglish ? 'Events & Catalysts' : '关键事件与催化剂'}</h2>
        <span className="hidden text-xs text-white/40 md:block">{isEnglish ? 'Importance' : '重要性'}</span>
        <span className="hidden text-xs text-white/40 md:block">{isEnglish ? 'Time' : '时间'}</span>
      </div>
      <div className="divide-y divide-white/[0.055]">
        {events.map((event, index) => (
          <div key={`${event.label}-${index}`} className="grid min-w-0 gap-2 py-3 md:grid-cols-[minmax(0,1fr)_8rem_8rem]">
            <div className="min-w-0">
              <p className="text-[11px] text-white/36">{event.label}</p>
              <p className="mt-1 truncate text-sm font-medium text-white/78">{isEmptyDashboardValue(event.title) ? EMPTY_FIELD_VALUE : event.title}</p>
              <p className="mt-1 line-clamp-1 text-xs text-white/44">{event.detail}</p>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-white/58">
              <span className="h-1.5 w-1.5 rounded-full bg-[#3B82F6]" />
              <span className="h-1.5 w-1.5 rounded-full bg-[#3B82F6]" />
              <span className={cn('h-1.5 w-1.5 rounded-full', index === 0 ? 'bg-[#3B82F6]' : 'bg-white/24')} />
              <span className="ml-3">{event.importance}</span>
            </div>
            <p className="text-xs text-white/44">{event.time}</p>
          </div>
        ))}
      </div>
    </section>
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
  const normalizedCandidates = candidates.map((value) => String(value || '').trim()).filter(Boolean);
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

function formatHistoryTimestamp(value?: string, locale: DashboardLocale = 'zh'): string {
  const text = String(value || '').trim();
  if (!text) {
    return '';
  }

  const date = new Date(text);
  if (Number.isNaN(date.getTime())) {
    return text;
  }

  const parts = new Intl.DateTimeFormat(locale === 'en' ? 'en-US' : 'zh-CN', {
    timeZone: 'Asia/Shanghai',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(date);
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
  const normalizedTicker = normalizeTickerQuery(ticker ?? undefined) || EMPTY_FIELD_VALUE;
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
  return aliases
    .map((alias) => normalizeDetailKey(alias))
    .flatMap((aliasKey) => (fields || []).filter((field) => normalizeDetailKey(field.label).includes(aliasKey) || aliasKey.includes(normalizeDetailKey(field.label))))
    .find((field) => field?.label);
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
  const localizedEntryValue = localizeMetricValue(locale, entryValue, EMPTY_FIELD_VALUE);
  const localizedTargetValue = localizeMetricValue(locale, targetValue, EMPTY_FIELD_VALUE);
  const localizedStopValue = localizeMetricValue(locale, stopValue, EMPTY_FIELD_VALUE);

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
      scoreValue: localizeNarrativeText(locale, rawScoreValue, EMPTY_FIELD_VALUE),
      badge: localizeNarrativeText(locale, normalized.badge, EMPTY_FIELD_VALUE),
      summary: localizeNarrativeText(locale, rawSummary, EMPTY_FIELD_VALUE),
      reasonTitle: locale === 'en' ? 'Latest Report Context' : '最近报告归因',
      reasonBody: localizeNarrativeText(locale, reasonBody, EMPTY_FIELD_VALUE),
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
      positionBody: localizeNarrativeText(locale, positionBody, EMPTY_FIELD_VALUE),
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
  const actionText = localizeNarrativeText(locale, summary.operationAdvice, seed.decision.scoreValue);
  const trendText = localizeNarrativeText(locale, summary.trendPrediction, actionText);
  const summaryText = localizeNarrativeText(locale, summary.analysisSummary, seed.decision.summary);

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

  const timelineStages = useMemo(
    () => buildTimelineProgressState(locale, progressModules, message, progress, phaseTick),
    [locale, progressModules, message, progress, phaseTick],
  );
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
                  <span className={`mt-1.5 h-2 w-2 rounded-full ${timelineDotTone(stage.status)}`} />
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
      className="min-w-0 rounded-lg border border-white/[0.07] bg-white/[0.018] px-3 py-3"
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

function GuestPaywallOverlay({ registrationPath }: { registrationPath: string }) {
  return (
    <div
      className="absolute inset-0 z-20 flex flex-col items-center justify-center rounded-xl bg-black/40 px-6 text-center backdrop-blur-[8px]"
      data-testid="guest-home-frosted-lock"
    >
      <Lock className="h-7 w-7 text-white/85 drop-shadow-[0_0_14px_rgba(99,102,241,0.55)]" />
      <p className="mt-4 max-w-xs text-sm font-medium leading-6 text-white/80">
        解锁完整 AI 量化策略与深度技术形态解析
      </p>
      <Link
        to={registrationPath}
        className="mt-5 inline-flex items-center justify-center rounded-full bg-gradient-to-r from-blue-500 to-purple-600 px-8 py-3 text-sm font-medium text-white shadow-[0_0_20px_rgba(99,102,241,0.4)] transition-all hover:from-blue-400 hover:to-purple-500"
      >
        免费创建账户 (Create Free Account)
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
  const routeTaskId = searchParams.get('task_id') || searchParams.get('taskId') || null;
  const routeSymbol = normalizeTickerQuery(searchParams.get('symbol') || undefined);
  const routeSource = searchParams.get('source') || null;
  const traceFixtureReport = useMemo(
    () => (!isGuest && (import.meta.env.DEV || import.meta.env.MODE === 'test') && searchParams.get('fixture') === 'analysis-trace')
      ? buildDecisionTraceFixtureReport()
      : null,
    [isGuest, searchParams],
  );
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
  const openHistoryDrawerButton = useSafariWarmActivation<HTMLButtonElement>(() => setHistoryDrawerOpen(true));
  const registrationPath = '/login?mode=create&redirect=%2F';
  const recentHistoryItems = useMemo(
    () => historyItems.filter((item) => !item.isTest).slice(0, 8),
    [historyItems],
  );
  const hasRunningTasks = useMemo(
    () => activeTasks.some((task) => task.status === 'pending' || task.status === 'processing'),
    [activeTasks],
  );
  const selectedTicker = normalizeTickerQuery(selectedReport?.meta.stockCode);
  const completedTaskReport = useMemo(() => {
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
  }, [activeTasks, activeTicker, pendingAnalysisTicker, routeTaskId]);
  const focusedTask = useMemo(() => {
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
  }, [activeTasks, activeTicker, pendingAnalysisTicker, routeTaskId]);
  const isTaskAnalyzing = Boolean(
    (pendingAnalysisTicker || routeTaskId)
    && focusedTask
    && (focusedTask.status === 'pending' || focusedTask.status === 'processing'),
  );
  const isGuestAnalyzing = isGuest && isDashboardLoading;
  const isHomeAnalyzing = isGuestAnalyzing || (!isGuest && (isAnalyzing || isTaskAnalyzing || Boolean(pendingAnalysisTicker && isDashboardLoading)));
  const isBusy = isHomeAnalyzing || isDashboardLoading;
  const dashboardData = useMemo<DashboardPayload>(() => {
    if (traceFixtureReport) {
      return buildDashboardFromReport(locale, traceFixtureReport);
    }

    if (isGuest) {
      return guestPreview
        ? buildGuestDashboardFromPreview(locale, guestPreview)
        : buildInPlacePlaceholderDashboard(locale, activeTicker);
    }

    const effectiveTicker = routeSymbol || activeTicker || selectedTicker || normalizeTickerQuery(recentHistoryItems[0]?.stockCode) || null;

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
  }, [activeTicker, completedTaskReport, guestPreview, isGuest, locale, pendingAnalysisTicker, recentHistoryItems, routeSymbol, selectedReport, selectedTicker, traceFixtureReport]);
  const activeTraceReport = useMemo<AnalysisReport | null>(() => {
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
  }, [activeTicker, completedTaskReport, routeSymbol, selectedReport, selectedTicker, traceFixtureReport]);
  const copy = dashboardData;
  const standbyCopy = useMemo(() => (
    locale === 'en'
      ? {
        analyzeButton: 'Analyze',
        omnibarPlaceholder: 'Enter a valid ticker...',
      }
      : {
        analyzeButton: '分析',
        omnibarPlaceholder: '输入有效股票代码...',
      }
  ), [locale]);
  const activeDrawerPayload = activeDrawer && copy ? buildDrawerPayload(locale, copy, activeDrawer) : null;
  const activeDecisionTrace = useMemo(() => (activeTraceReport ? getDecisionTrace(activeTraceReport) : undefined), [activeTraceReport]);
  const activeReportQuality = useMemo(() => getReportQuality(activeTraceReport), [activeTraceReport]);
  const activeDataQualityReport = useMemo(() => getDataQualityReport(activeTraceReport), [activeTraceReport]);
  const sourceSummary = useMemo(() => buildTraceSummary(activeDecisionTrace, activeReportQuality), [activeDecisionTrace, activeReportQuality]);
  const reanalysisTicker = useMemo(() => {
    const candidate = normalizeTickerQuery(activeTraceReport?.meta.stockCode) || normalizeTickerQuery(dashboardData.ticker);
    return TICKER_FORMAT_RE.test(candidate) ? candidate : '';
  }, [activeTraceReport?.meta.stockCode, dashboardData.ticker]);
  const shouldRenderDashboardPanels = !isGuest || Boolean(guestPreview || pendingAnalysisTicker);
  const guestPaywall = isGuest ? <GuestPaywallOverlay registrationPath={registrationPath} /> : null;
  const deleteCopy = useMemo(() => ({
    title: t('home.deleteTitle'),
    single: t('home.deleteSingle'),
    multiple: (count: number) => t('home.deleteMultiple', { count }),
    confirm: t('home.deleteConfirm'),
    deleting: t('home.deleting'),
    cancel: t('home.cancel'),
    clearVisible: t('home.deleteAll'),
    deleteOne: t('home.deleteOne'),
    visibleCount: t('home.visibleCount'),
  }), [t]);

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

    const nextTicker = normalizeTickerQuery(selectedReport?.meta.stockCode) || normalizeTickerQuery(recentHistoryItems[0]?.stockCode);
    if (!nextTicker) {
      return;
    }

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
        className="inline-flex min-w-0 items-center gap-2 rounded-md border border-white/[0.07] bg-white/[0.035] px-2.5 py-1.5 text-xs font-medium text-white/74 transition-colors hover:border-white/14 hover:bg-white/[0.07] hover:text-white"
        onClick={() => setFullReportDrawerOpen(true)}
      >
        <span className="truncate">{locale === 'en' ? 'Full Report' : '完整报告'}</span>
      </button>
      <button
        type="button"
        className="inline-flex min-w-0 items-center gap-2 rounded-md border border-transparent bg-transparent px-2.5 py-1.5 text-xs font-medium text-white/50 transition-colors hover:border-white/10 hover:bg-white/[0.04] hover:text-white"
        onClick={() => setTraceDrawerOpen(true)}
        data-testid="home-bento-decision-trace-trigger"
      >
        <FileSearch className="h-3.5 w-3.5 shrink-0" />
        <span className="truncate">{locale === 'en' ? 'Sources' : '决策来源'}</span>
      </button>
      <button
        type="button"
        className="inline-flex min-w-0 items-center gap-2 rounded-md border border-transparent bg-transparent px-2.5 py-1.5 text-xs font-medium text-white/50 transition-colors hover:border-white/10 hover:bg-white/[0.04] hover:text-white"
        onClick={() => { void handleCopyActiveReport(); }}
      >
        <Copy className="h-3.5 w-3.5 shrink-0" />
        <span className="truncate">{mainCopyState === 'copied' ? '已复制' : mainCopyState === 'failed' ? '复制失败' : '复制报告'}</span>
      </button>
      <button
        type="button"
        className="inline-flex min-w-0 items-center gap-2 rounded-md border border-transparent bg-transparent px-2.5 py-1.5 text-xs font-medium text-white/50 transition-colors hover:border-white/10 hover:bg-white/[0.04] hover:text-white disabled:cursor-wait disabled:text-white/35"
        disabled={isBusy || !reanalysisTicker}
        title={!reanalysisTicker ? '缺少股票代码' : undefined}
        onClick={() => { void handleAnalyze(reanalysisTicker); }}
      >
        <RefreshCw className="h-3.5 w-3.5 shrink-0" />
        <span className="truncate">{!reanalysisTicker ? '缺少股票代码' : locale === 'en' ? 'Rerun' : '重新分析'}</span>
      </button>
    </>
  ) : null;

  const omnibarModule = (
    <div className="w-full shrink-0" data-testid="home-bento-omnibar-shell">
      <form
        className="flex min-h-11 w-full min-w-0 flex-col gap-2 sm:h-11 sm:flex-row"
        data-testid="home-bento-omnibar"
        onSubmit={(event) => {
          event.preventDefault();
          void handleAnalyze();
        }}
      >
        <div
          className="group relative flex min-h-11 min-w-0 flex-1 items-center overflow-hidden rounded-lg border border-white/[0.08] bg-[#0b1118]/80 transition-all focus-within:border-[#3B82F6]/45 focus-within:bg-[#0f1620]"
          data-testid="home-bento-omnibar-input-shell"
        >
          <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-4">
            <Search className="h-4 w-4 text-white/40" />
          </div>
          <input
            data-testid="home-bento-omnibar-input"
            type="text"
            className="h-full min-h-11 min-w-0 flex-1 bg-transparent pl-11 pr-4 text-sm leading-none text-white caret-[#93C5FD] outline-none [appearance:textfield] placeholder:text-white/30"
            value={searchQuery}
            onChange={(event) => {
              setSearchQuery(event.target.value);
            }}
            autoComplete="off"
            disabled={isBusy}
            placeholder={copy?.omnibarPlaceholder || standbyCopy.omnibarPlaceholder}
          />
        </div>
        <button
          type="submit"
          disabled={isBusy}
          className="min-h-11 shrink-0 rounded-lg border border-white/[0.09] bg-white/[0.045] px-5 text-sm font-semibold text-white/82 transition-colors hover:border-white/18 hover:bg-white/[0.08] hover:text-white disabled:cursor-wait disabled:text-white/48"
          data-testid="home-bento-analyze-button"
        >
          {isHomeAnalyzing ? (locale === 'en' ? 'Analyzing...' : '分析中...') : (copy?.analyzeButton || standbyCopy.analyzeButton)}
        </button>
        {!isGuest ? (
          <button
            ref={openHistoryDrawerButton.ref}
            type="button"
            aria-label={locale === 'en' ? 'History' : '历史记录'}
            onClick={openHistoryDrawerButton.onClick}
            onPointerUp={openHistoryDrawerButton.onPointerUp}
            disabled={isBusy}
            className="flex min-h-11 shrink-0 items-center justify-center rounded-lg border border-white/[0.08] bg-[#0b1118]/70 px-4 text-white/62 transition-colors hover:bg-white/[0.06] hover:text-white disabled:cursor-wait disabled:text-white/36"
            data-testid="home-bento-history-drawer-trigger"
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l2.5 2.5M21 12a9 9 0 1 1-3.2-6.9M21 4v5h-5" />
            </svg>
          </button>
        ) : null}
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
      data-bento-surface="true"
      aria-live={shouldGuardA11y ? 'polite' : undefined}
      className={getSafariReadySurfaceClassName(
        true,
        `${BENTO_SURFACE_ROOT_CLASS} w-full flex-1 flex flex-col gap-6 min-h-0 min-w-0 bg-transparent`,
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
            className="flex min-h-[min(62vh,620px)] w-full flex-col items-center justify-center gap-8 px-4 text-center"
            data-testid="guest-home-clean-search"
          >
            <div className="flex flex-col items-center gap-5">
              <img
                src="/wolfystock-logo-mark.png"
                alt="WolfyStock"
                className="h-16 w-16 rounded-full bg-white/[0.03] p-2 shadow-[0_0_38px_rgba(99,102,241,0.28)]"
              />
              <div>
                <h1 className="text-3xl font-black tracking-[0] text-white md:text-5xl">
                  {locale === 'en' ? 'WolfyStock Analysis Center' : 'WolfyStock 分析面板'}
                </h1>
                <p className="mt-3 text-sm text-white/45">
                  {locale === 'en' ? 'Enter a ticker to generate an analysis view.' : '输入股票代码，搜索后生成 AI 分析面板。'}
                </p>
              </div>
            </div>
            <div className="w-full max-w-3xl">
              {omnibarModule}
            </div>
          </section>
        ) : (() => {
          const readyCopy = dashboardData;
          const qualityChipLabel = !isGuest
            ? buildDataQualityChipLabel(activeDataQualityReport, locale, readyCopy.decision.confidenceValue)
            : null;
          const scorePercent = normalizeLinearScore(readyCopy.decision.heroValue);
          const thesisCopy = readyCopy.decision.reasonBody || readyCopy.decision.summary || EMPTY_FIELD_VALUE;
          const sourceLabel = sourceSummary || qualityChipLabel || '';
          const stanceLabel = resolveLinearStanceLabel(locale, readyCopy.decision.signalLabel, readyCopy.decision.signalTone);
          return (
            <div
              data-testid="home-bento-grid"
              data-bento-grid="true"
              className="flex w-full min-w-0 flex-col gap-3"
            >
              {omnibarModule}
              <div
                className="grid min-w-0 rounded-[14px] border border-white/[0.045] bg-[#080c12]/58 shadow-none lg:grid-cols-[minmax(0,1fr)_minmax(300px,390px)]"
                data-testid="home-linear-shell"
              >
                <div
                  className="min-w-0 px-4 py-6 md:px-8 md:py-8"
                  data-testid="home-bento-primary-stack"
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
                    <div
                      className="min-w-0"
                      data-testid="home-bento-card-decision"
                      data-research-card="decision"
                    >
                      <div data-testid={completedTaskReport ? 'home-bento-analysis-result-card' : undefined}>
                        <div
                          className="flex min-w-0 flex-wrap items-start justify-between gap-4"
                          data-testid="home-bento-decision-company-header"
                        >
                        <div className="min-w-0">
                          <p
                            className="text-xs leading-5 text-white/44"
                            data-testid="home-bento-decision-sector"
                          >
                            {resolveLinearSectorTrail(locale, readyCopy.decision.sector)}
                          </p>
                          <div className="mt-3 flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
                            <h1 className="min-w-0 truncate text-2xl font-semibold tracking-[0] text-white md:text-3xl">
                              {readyCopy.decision.company}
                            </h1>
                            <span className="font-mono text-sm text-white/40">({readyCopy.ticker})</span>
                          </div>
                        </div>
                        {reportActionButtons ? (
                          <div
                            className="flex min-w-0 flex-wrap justify-start gap-2.5 lg:max-w-[28rem] lg:justify-end"
                            data-testid="home-bento-decision-header-actions"
                          >
                            {reportActionButtons}
                          </div>
                        ) : null}
                      </div>

                        {sourceLabel ? (
                          <p className="mt-3 line-clamp-2 text-xs leading-5 text-white/42" data-testid="home-bento-decision-source-summary">
                            {sourceLabel}
                          </p>
                        ) : null}

                        <div
                          className="mt-8 grid gap-7 md:grid-cols-[12rem_16rem_minmax(10rem,13rem)]"
                          data-testid="home-bento-decision-hero-row"
                        >
                        <div className="min-w-0" data-testid="home-bento-decision-action">
                          <p className="text-xs font-medium tracking-[0] text-white/42">{locale === 'en' ? 'Stance' : '投资立场'}</p>
                          <p
                            className="mt-3 text-4xl font-semibold tracking-[0] text-white md:text-5xl"
                            data-testid="home-bento-decision-signal-hero"
                          >
                            {stanceLabel}
                          </p>
                        </div>

                        <div className="min-w-0" data-testid="home-bento-decision-score">
                          <p className="text-xs font-medium tracking-[0] text-white/42">{locale === 'en' ? 'Score' : '综合评分'}</p>
                          <div className="mt-3 flex items-end gap-2" data-testid="home-bento-decision-core-metrics">
                            <p
                              className="font-mono text-4xl font-semibold leading-none text-white md:text-5xl"
                              data-testid="home-bento-decision-score-value"
                            >
                              {readyCopy.decision.heroValue}
                            </p>
                            <span className="pb-1 text-sm text-white/42">{readyCopy.decision.heroUnit}</span>
                          </div>
                          <div className="mt-4 flex max-w-[220px] items-center gap-2">
                            <span className="h-1 w-full overflow-hidden rounded-full bg-white/[0.08]">
                              <span className="block h-full rounded-full bg-[#3B82F6]" style={{ width: `${scorePercent}%` }} />
                            </span>
                            <span className="h-1 w-10 rounded-full bg-white/[0.08]" />
                            <span className="h-1 w-8 rounded-full bg-white/[0.06]" />
                          </div>
                        </div>

                        <div className="min-w-0" data-testid="home-bento-decision-conviction">
                          <div className="flex min-w-0 items-center justify-between gap-3">
                            <p className="text-xs font-medium tracking-[0] text-white/42">{locale === 'en' ? 'Conviction' : '置信度'}</p>
                            {activeDataQualityReport ? (
                              <TraceBadge tone={dataQualityChipTone(activeDataQualityReport)}>
                                {dataQualityTierLabel(activeDataQualityReport.dataQualityTier, locale)}
                              </TraceBadge>
                            ) : null}
                          </div>
                          <p className="mt-3 font-mono text-2xl font-semibold text-white/82" data-testid="home-bento-decision-conviction-value">
                            {readyCopy.decision.confidenceValue || EMPTY_FIELD_VALUE}
                          </p>
                        </div>
                        </div>

                        <div className="mt-6 max-w-4xl text-sm leading-6 text-white/68">
                          <div data-testid="home-bento-decision-insight">
                            <p className="text-xs font-medium tracking-[0] text-white/42">{locale === 'en' ? 'Thesis' : '核心观点'}</p>
                            <p className="mt-2" data-testid="home-bento-decision-insight-copy">
                              {thesisCopy}
                            </p>
                          </div>
                        </div>

                        <div className="mt-5" data-testid="home-bento-research-state-row">
                          <LinearKeyLevelsStrip metrics={readyCopy.strategy.metrics} locale={locale} />
                        </div>

                        <div className="mt-5" data-testid="home-bento-secondary-grid">
                          <LinearTechnicalStructure
                            locale={locale}
                            signals={readyCopy.tech.signals}
                            isGuest={Boolean(isGuest)}
                            guestPaywall={guestPaywall}
                            onOpenDetails={() => setActiveDrawer('tech')}
                            detailLabel={readyCopy.tech.detailLabel}
                          />
                        </div>
                      </div>
                    </div>
                  )}
                </div>
                {isHomeAnalyzing ? (
                  <aside
                    className="min-w-0 border-t border-white/[0.055] px-4 py-5 lg:border-l lg:border-t-0 lg:px-7 lg:py-7"
                    data-testid="home-bento-secondary-stack"
                  >
                    <InPlaceStrategySkeleton locale={locale} />
                    <div className="mt-5 grid gap-4" data-testid="home-bento-secondary-grid">
                      <InPlaceListSkeleton locale={locale} kind="tech" />
                      <InPlaceListSkeleton locale={locale} kind="fundamentals" />
                    </div>
                  </aside>
                ) : (
                  <LinearObservationPanel
                    locale={locale}
                    dashboard={readyCopy}
                    dataQualityReport={activeDataQualityReport}
                    sourceSummary={sourceSummary}
                    isGuest={Boolean(isGuest)}
                    guestPaywall={guestPaywall}
                    onOpenStrategy={() => setActiveDrawer('strategy')}
                    onOpenFundamentals={() => setActiveDrawer('fundamentals')}
                  />
                )}
              </div>
              {!isHomeAnalyzing ? (
                <LinearEventsStrip
                  locale={locale}
                  dashboard={readyCopy}
                  dataQualityReport={activeDataQualityReport}
                  sourceSummary={sourceSummary}
                />
              ) : null}
              {!isHomeAnalyzing && !isGuest && (activeDataQualityReport || sourceSummary) ? (
                <div>
                  <AnalysisDiagnosticsDisclosure report={activeDataQualityReport} locale={locale} sourceSummary={sourceSummary} />
                </div>
              ) : null}
              <p className="px-2 text-center text-[11px] leading-5 text-white/32" data-testid="home-linear-footer-disclaimer">
                {locale === 'en'
                  ? 'For research reference only. Not investment advice. Data may be delayed, partial, or fallback-backed.'
                  : '本平台内容仅供研究参考，不构成投资建议。数据可能存在延迟、缺失或降级。'}
              </p>
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
        <DecisionTracePanel trace={activeDecisionTrace} locale={locale} quality={activeReportQuality} />
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
              itemQuality.userLabel === '完整' ? '可信度较高' : itemQuality.userLabel,
              traceQualityLabel(itemQuality.traceStatus),
              reportQualityLabel(itemQuality.reportStatus),
              itemQuality.schemaStatus === 'ok' || itemQuality.schemaStatus === 'unconfirmed'
                ? schemaQualityLabel(itemQuality.schemaStatus)
                : null,
            ].filter(Boolean) as string[];
            return (
              <div
                key={item.id}
                className={`flex min-w-0 items-center gap-3 rounded-2xl border px-3 py-3 transition-colors ${
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
