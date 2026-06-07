import type React from 'react';
import { useState } from 'react';
import { Copy, Download, Printer } from 'lucide-react';
import { Drawer } from '../common/Drawer';
import type {
  AnalysisReport,
  StandardReport,
  StandardReportChecklistItem,
  StandardReportField,
} from '../../types/analysis';
import {
  buildInstitutionalReportMarkdown,
  consumerSafeReportPriceContext,
  consumerSafeReportStatus,
  consumerSafeReportText,
  getCompanyDisplayName,
  getCompanyWithTicker,
  getSymbolDisplay,
  readObjectField,
} from '../../utils/homeReportIdentity';

const REPORT_DATE_FORMATTER = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

type DashboardPayload = {
  ticker: string;
  decision: {
    company: string;
    heroValue: string;
    heroUnit?: string;
    confidenceValue?: string;
    signalLabel: string;
    scoreValue: string;
    summary: string;
    reasonBody: string;
  };
};

type FullDecisionReportDrawerProps = {
  dashboard: DashboardPayload;
  isOpen: boolean;
  onClose: () => void;
  report: AnalysisReport | null;
};

type FullReportSection = {
  id: string;
  title: string;
  rows?: Array<{ label: string; value: string }>;
  bullets?: string[];
  checklist?: Array<{ label: string; status: string }>;
};

type ReportIdentity = {
  companyName: string;
  ticker: string;
  companyWithTicker: string;
  generatedAt: string;
  market: string;
  currency: string;
  providers: string;
  horizon: string;
  dataStatus: string;
};

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

function safeReportValue(value: unknown): string {
  const text = String(value ?? '').trim();
  return text && text !== '-' && !/^n\/?a$/i.test(text) ? text : '--';
}

function normalizeDetailKey(value?: string): string {
  return String(value || '').toLowerCase().replace(/[\s/()%+.\-_:]+/g, '');
}

function findStandardField(fields: StandardReportField[] | undefined, aliases: string[]): StandardReportField | undefined {
  const normalizedAliases = aliases.map((alias) => normalizeDetailKey(alias));
  return (fields || []).find((field) => {
    const key = normalizeDetailKey(field.label);
    return normalizedAliases.some((alias) => key.includes(alias) || alias.includes(key));
  });
}

function fieldValue(fields: StandardReportField[] | undefined, aliases: string[]): string {
  const field = findStandardField(fields, aliases);
  return field ? consumerSafeReportText(field.value, '--') : '';
}

function priceFieldValue(fields: StandardReportField[] | undefined, aliases: string[]): string {
  const field = findStandardField(fields, aliases);
  return field ? consumerSafeReportPriceContext(field.value, '--') : '';
}

function getReportSource(report: AnalysisReport | null): StandardReport | undefined {
  return report?.details?.standardReport;
}

function listOrMissing(
  items?: Array<string | undefined | null>,
  fallback = '暂无明确记录',
  mode: 'text' | 'price' = 'text',
): string[] {
  const seen = new Set<string>();
  const values: string[] = [];
  for (const raw of items || []) {
    const item = mode === 'price'
      ? consumerSafeReportPriceContext(raw, '')
      : consumerSafeReportText(raw, '');
    if (!item) continue;
    const key = item.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    values.push(item);
  }
  return values.length ? values : [fallback];
}

function normalizeChecklistStatus(item: StandardReportChecklistItem | string): { label: string; status: string } {
  if (typeof item === 'string') {
    return { label: consumerSafeReportText(item, '研究包完整度待复核。'), status: '未知' };
  }
  const status = String(item.status || '').toLowerCase();
  const normalized = status === 'pass'
    ? 'PASS'
    : status === 'fail'
      ? 'FAIL'
      : status === 'warn'
        ? 'WARN'
        : status === 'na'
          ? 'N/A'
          : '未知';
  return { label: consumerSafeReportText(item.text, '研究包完整度待复核。'), status: normalized };
}

function formatReportDateTime(value?: string): string {
  const text = String(value || '').trim();
  if (!text) {
    return '--';
  }
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) {
    return text;
  }
  return REPORT_DATE_FORMATTER.format(date);
}

function buildReportIdentity(report: AnalysisReport | null, dashboard?: DashboardPayload, override?: Partial<ReportIdentity>): ReportIdentity {
  const ticker = override?.ticker || getSymbolDisplay(report) || dashboard?.ticker || '--';
  const companyName = override?.companyName || getCompanyDisplayName(report) || dashboard?.decision.company || ticker;
  const generatedAt = override?.generatedAt
    || report?.meta.reportGeneratedAt
    || report?.meta.createdAt
    || report?.decisionTrace?.generatedAt
    || '';
  const dataSources = report?.decisionTrace?.dataSources || [];
  const providerSeen = new Set<string>();
  const providerParts: string[] = [];
  for (const source of dataSources) {
    const provider = String(source.provider || source.name || '').trim();
    if (!provider) continue;
    const key = provider.toLowerCase();
    if (providerSeen.has(key)) continue;
    providerSeen.add(key);
    providerParts.push(provider);
  }
  const providers = providerParts.join(', ');
  const statuses = dataSources.flatMap((source) => source.status ? [source.status] : []);
  const sourceStatus = statuses.length
    ? statuses.map((status) => {
      const normalized = String(status || '').trim().toLowerCase();
      return consumerSafeReportStatus(normalized);
    }).join(' / ')
    : '数据覆盖未确认';

  return {
    companyName,
    ticker,
    companyWithTicker: getCompanyWithTicker(report || { companyName, symbol: ticker }),
    generatedAt: formatReportDateTime(generatedAt),
    market: override?.market || report?.decisionTrace?.market || '--',
    currency: override?.currency || safeReportValue(readObjectField(report, ['details', 'standardReport', 'summaryPanel', 'currency']) || readObjectField(report, ['details', 'standardReport', 'market', 'currency'])),
    providers: override?.providers || providers || '--',
    horizon: override?.horizon || safeReportValue(report?.details?.standardReport?.summaryPanel?.timeSensitivity || report?.details?.standardReport?.decisionPanel?.marketStructure || '短线 / 中短线'),
    dataStatus: override?.dataStatus || sourceStatus || '--',
  };
}

function buildFullReportSections(report: AnalysisReport | null, dashboard: DashboardPayload): FullReportSection[] {
  const standardReport = getReportSource(report);
  const summaryPanel = standardReport?.summaryPanel;
  const decisionPanel = standardReport?.decisionPanel;
  const reasonLayer = standardReport?.reasonLayer;
  const highlights = standardReport?.highlights;
  const market = standardReport?.market;
  const marketFields = [
    ...(market?.displayFields || []),
    ...(market?.regularFields || []),
    ...(market?.extendedFields || []),
  ];
  const technicalFields = standardReport?.technicalFields || standardReport?.tableSections?.technical?.fields || [];
  const fundamentalFields = standardReport?.fundamentalFields || standardReport?.tableSections?.fundamental?.fields || [];
  const earningsFields = standardReport?.earningsFields || standardReport?.tableSections?.earnings?.fields || [];
  const sentimentFields = standardReport?.sentimentFields || [];
  const battleFields = standardReport?.battleFields || [];
  const coverageNotes = standardReport?.coverageNotes;
  const checklistItems = (standardReport?.checklistItems || standardReport?.checklist || []).map(normalizeChecklistStatus);
  const battleCards = standardReport?.battlePlanCompact?.cards || [];
  const battleNotes = standardReport?.battlePlanCompact?.notes || [];

  return [
    {
      id: 'summary',
      title: '研究包完整度',
      rows: [
        { label: '继续跟踪', value: consumerSafeReportText(summaryPanel?.operationAdvice || report?.summary.operationAdvice || dashboard.decision.signalLabel, '继续跟踪') },
        { label: '评分', value: safeReportValue(summaryPanel?.score ?? dashboard.decision.heroValue) },
        { label: '情景参考', value: consumerSafeReportText(decisionPanel?.marketStructure || summaryPanel?.trendPrediction || report?.summary.trendPrediction || dashboard.decision.scoreValue, '情景参考') },
        { label: '研究摘要', value: consumerSafeReportText(summaryPanel?.oneSentence || report?.summary.analysisSummary || dashboard.decision.summary, '当前研究包仍不完整，仅支持继续跟踪。') },
        { label: '关键理由', value: consumerSafeReportText(reasonLayer?.coreReasons?.[0] || reasonLayer?.latestKeyUpdate || dashboard.decision.reasonBody, '价格与证据仍需继续跟踪。') },
      ],
    },
    {
      id: 'important-brief',
      title: '重要信息速览',
      rows: [
        { label: '舆情情绪', value: consumerSafeReportText(highlights?.sentimentSummary || reasonLayer?.sentimentSummary || fieldValue(sentimentFields, ['sentiment', '舆情', '情绪']) || report?.summary.sentimentLabel, '数据不足') },
        { label: '业绩预期', value: consumerSafeReportText(highlights?.earningsOutlook || fieldValue(earningsFields, ['earnings', '业绩', 'eps']), '数据不足') },
        { label: '最新动态', value: consumerSafeReportText(reasonLayer?.latestKeyUpdate || highlights?.latestNews?.[0], '数据不足') },
      ],
      bullets: listOrMissing(highlights?.latestNews, '暂无最新动态字段'),
    },
    {
      id: 'risks',
      title: '风险边界',
      bullets: listOrMissing([
        reasonLayer?.topRisk,
        ...(highlights?.riskAlerts || []),
        ...(highlights?.bearishFactors || []),
      ], '暂无明确风险条目', 'price'),
    },
    {
      id: 'catalysts',
      title: '情景参考',
      bullets: listOrMissing([
        reasonLayer?.topCatalyst,
        ...(highlights?.positiveCatalysts || []),
        ...(highlights?.bullishFactors || []),
      ], '暂无明确利好催化'),
    },
    {
      id: 'market',
      title: '当日行情',
      rows: [
        { label: '开盘', value: fieldValue(marketFields, ['open', '开盘']) || safeReportValue(market?.regularMetrics?.open) },
        { label: '最高', value: fieldValue(marketFields, ['high', '最高']) || safeReportValue(market?.regularMetrics?.high) },
        { label: '最低', value: fieldValue(marketFields, ['low', '最低']) || safeReportValue(market?.regularMetrics?.low) },
        { label: '收盘', value: fieldValue(marketFields, ['close', '收盘', 'current']) || safeReportValue(summaryPanel?.currentPrice || market?.regularMetrics?.close) },
        { label: '涨跌幅', value: fieldValue(marketFields, ['change pct', 'change%', '涨跌幅']) || safeReportValue(summaryPanel?.changePct || market?.regularMetrics?.changePct) },
        { label: '成交量', value: fieldValue(marketFields, ['volume', '成交量']) || safeReportValue(market?.regularMetrics?.volume) },
        { label: '成交额', value: fieldValue(marketFields, ['turnover', 'amount', '成交额']) || safeReportValue(market?.regularMetrics?.amount) },
        { label: '价格上下文', value: consumerSafeReportText(summaryPanel?.priceContextNote || summaryPanel?.priceBasis || summaryPanel?.priceBasisDetail, '数据不足') },
      ],
    },
    {
      id: 'data-lens',
      title: '数据透视',
      rows: [
        { label: 'MA alignment', value: fieldValue(technicalFields, ['MA ALIGNMENT', 'Moving Averages', '均线']) },
        { label: 'Current price', value: safeReportValue(summaryPanel?.currentPrice || decisionPanel?.analysisPrice) },
        { label: 'MA5', value: fieldValue(technicalFields, ['MA5', '5日']) },
        { label: 'MA10', value: fieldValue(technicalFields, ['MA10', '10日']) },
        { label: 'MA20', value: fieldValue(technicalFields, ['MA20', '20日']) },
        { label: 'MA60', value: fieldValue(technicalFields, ['MA60', '60日']) },
        { label: '关键价格区间', value: consumerSafeReportPriceContext(decisionPanel?.support || decisionPanel?.idealEntry || report?.strategy?.idealBuy, '数据不足') },
        { label: '情景参考', value: consumerSafeReportPriceContext(decisionPanel?.resistance || decisionPanel?.target || decisionPanel?.targetZone || report?.strategy?.takeProfit, '数据不足') },
        { label: 'Volume / turnover', value: fieldValue(technicalFields, ['VOLUME DYNAMICS', 'Volume', '量价', '成交量']) || fieldValue(marketFields, ['volume', 'turnover', 'amount', '成交']) },
        { label: '筹码观察', value: consumerSafeReportText(fieldValue(technicalFields, ['chip', '筹码']) || standardReport?.decisionContext?.compositeView, '数据不足') },
      ],
    },
    {
      id: 'technical',
      title: '技术透视',
      rows: [
        { label: '均线排列', value: fieldValue(technicalFields, ['MA ALIGNMENT', 'Moving Averages', '均线']) },
        { label: 'RSI', value: fieldValue(technicalFields, ['RSI-14', 'RSI14', 'RSI']) },
        { label: 'MACD', value: fieldValue(technicalFields, ['MACD']) },
        { label: '关键价格区间', value: consumerSafeReportPriceContext(decisionPanel?.support || decisionPanel?.idealEntry || report?.strategy?.idealBuy, '数据不足') },
        { label: '情景参考', value: consumerSafeReportPriceContext(decisionPanel?.resistance || decisionPanel?.target || report?.strategy?.takeProfit, '数据不足') },
        { label: '量价判断', value: fieldValue(technicalFields, ['VOLUME DYNAMICS', 'Volume', '量价', '成交量']) },
      ],
    },
    {
      id: 'fundamentals',
      title: '基本面摘要',
      rows: [
        { label: '营收', value: fieldValue(fundamentalFields, ['Revenue', 'Revenue Growth', '收入', '营收']) || '--' },
        { label: 'ROE', value: fieldValue(fundamentalFields, ['ROE']) || '--' },
        { label: '利润率', value: fieldValue(fundamentalFields, ['Margin', 'EBITDA MARGIN', '毛利率', '利润率']) || '--' },
        { label: 'EPS', value: fieldValue(fundamentalFields, ['EPS', 'LATEST EPS']) || '--' },
        { label: '估值', value: fieldValue(fundamentalFields, ['PE', 'Forward PE', '市盈率', '估值']) || '--' },
      ],
    },
    {
      id: 'observation-plan',
      title: '继续跟踪',
      rows: [
        { label: '关键价格区间', value: consumerSafeReportPriceContext(decisionPanel?.idealEntry || report?.strategy?.idealBuy || priceFieldValue(battleFields, ['ideal', '理想']), '数据不足') },
        { label: '情景参考', value: consumerSafeReportPriceContext(decisionPanel?.backupEntry || report?.strategy?.secondaryBuy || priceFieldValue(battleFields, ['secondary', '次级']), '数据不足') },
        { label: '风险边界', value: consumerSafeReportPriceContext(decisionPanel?.stopLoss || report?.strategy?.stopLoss || priceFieldValue(battleFields, ['stop', '止损']), '数据不足') },
        { label: '关键价格区间', value: consumerSafeReportPriceContext(decisionPanel?.target || decisionPanel?.targetZone || report?.strategy?.takeProfit || priceFieldValue(battleFields, ['target', '目标']), '数据不足') },
        { label: '风险边界说明', value: consumerSafeReportText(decisionPanel?.positionSizing || battleCards.find((item) => /position|仓位/i.test(item.label))?.value, '风险边界仅作情景约束。') },
        { label: '继续跟踪', value: consumerSafeReportText(decisionPanel?.buildStrategy || battleNotes.find((item) => /entry|建仓|入场/i.test(item.label))?.value, '继续跟踪，等待研究包补齐。') },
        { label: '风险边界', value: consumerSafeReportText(decisionPanel?.riskControlStrategy || decisionPanel?.stopReason, '风险边界用于说明不确定性。') },
        { label: '数据不足', value: consumerSafeReportText(decisionPanel?.noPositionAdvice, '数据不足，仅支持继续跟踪。') },
        { label: '继续跟踪说明', value: consumerSafeReportText(decisionPanel?.holderAdvice, '继续跟踪，不输出配置建议。') },
      ],
      bullets: listOrMissing(decisionPanel?.executionReminders, '暂无额外提醒'),
    },
    {
      id: 'checklist',
      title: '研究清单',
      checklist: checklistItems.length ? checklistItems : [
        { label: '研究包完整度待复核', status: '未知' },
        { label: '关键价格区间仅作背景', status: '未知' },
        { label: '风险边界明确', status: '未知' },
        { label: '数据覆盖充分', status: '未知' },
        { label: '冲突已标注', status: '未知' },
      ],
    },
    {
      id: 'data-notes',
      title: '研究包说明',
      bullets: [
        ...listOrMissing(coverageNotes?.coverageGaps || coverageNotes?.missingFieldNotes, '缺失字段显示为 --'),
        ...listOrMissing(coverageNotes?.conflictNotes, '暂无额外冲突说明'),
        ...listOrMissing(coverageNotes?.methodNotes, '本报告为 AI 辅助分析，不构成投资建议'),
      ],
    },
  ];
}

const FullDecisionReportDrawer: React.FC<FullDecisionReportDrawerProps> = ({
  dashboard,
  isOpen,
  onClose,
  report,
}) => {
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>('idle');
  const sections = buildFullReportSections(report, dashboard);
  const identity = buildReportIdentity(report, dashboard);
  const markdown = buildInstitutionalReportMarkdown(report);
  const summarySection = sections.find((section) => section.id === 'summary');
  const riskSection = sections.find((section) => section.id === 'risks');
  const observationSection = sections.find((section) => section.id === 'observation-plan');
  const primaryReportSections = [riskSection, observationSection].filter((section): section is FullReportSection => Boolean(section));
  const technicalSections = sections.filter((section) => !['summary', 'risks', 'observation-plan'].includes(section.id));
  const summaryLine = summarySection?.rows?.find((row) => row.label === '研究摘要')?.value
    || consumerSafeReportText(dashboard.decision.summary, '当前研究包仍不完整，仅支持继续跟踪。')
    || '--';
  const observationLine = summarySection?.rows?.find((row) => row.label === '继续跟踪')?.value
    || consumerSafeReportText(dashboard.decision.signalLabel, '继续跟踪')
    || '--';
  const confidenceLine = dashboard.decision.confidenceValue || '--';
  const riskLine = riskSection?.bullets?.find((item) => item && item !== '--')
    || observationSection?.rows?.find((row) => row.label === '风险边界' || row.label === '风险边界说明')?.value
    || '--';
  const headerSignalLabel = consumerSafeReportText(dashboard.decision.signalLabel, '继续跟踪') || '继续跟踪';

  const handleCopyReport = async () => {
    if (!navigator.clipboard?.writeText) {
      setCopyState('failed');
      return;
    }
    const copyError = await navigator.clipboard.writeText(markdown)
      .then(() => null)
      .catch((error) => error);
    if (copyError) {
      setCopyState('failed');
      return;
    }
    setCopyState('copied');
  };

  const buildExportFileName = (extension: 'md'): string => {
    const safeCompany = identity.companyName.replace(/[^a-z0-9]+/gi, '-').replace(/^-+|-+$/g, '') || 'Report';
    const safeDate = identity.generatedAt.replace(/\D/g, '').slice(0, 8) || 'latest';
    return `WolfyStock_${safeCompany}_${identity.ticker}_${safeDate}.${extension}`;
  };

  const handleMarkdownExport = () => {
    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = buildExportFileName('md');
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  };

  const handlePrintReport = () => {
    const printWindow = window.open('', '_blank', 'width=960,height=1200');
    if (!printWindow) {
      window.print();
      return;
    }
    const escapedMarkdown = markdown
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    printWindow.document.write(`
      <!doctype html>
      <html>
        <head>
          <title>${identity.companyWithTicker} - Wolfy AI Equity Research</title>
          <style>
            body { margin: 0; background: #fff; color: #111827; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
            main { max-width: 820px; margin: 0 auto; padding: 40px 34px; }
            pre { white-space: pre-wrap; word-break: break-word; font-family: inherit; line-height: 1.58; font-size: 13px; }
            @media print { main { padding: 0; } }
          </style>
        </head>
        <body><main><pre>${escapedMarkdown}</pre></main></body>
      </html>
    `);
    printWindow.document.close();
    printWindow.focus();
    window.setTimeout(() => printWindow.print(), 80);
  };

  return (
    <Drawer
      isOpen={isOpen}
      onClose={onClose}
      title="完整报告"
      width="max-w-[min(100vw,65rem)]"
      zIndex={90}
      bodyClassName="overflow-x-hidden"
    >
      <article
        className="min-w-0 space-y-5 rounded-l-[28px] border border-white/[0.08] bg-[#080B10]/92 p-4 text-white shadow-2xl sm:p-7"
        data-testid="home-bento-full-report-drawer"
      >
        <header className="min-w-0 border-b border-white/8 pb-5">
          <div className="flex min-w-0 flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-white/42">WOLFY AI EQUITY RESEARCH</p>
              <h2 className="mt-2 break-words text-2xl font-semibold tracking-[0] text-white md:text-3xl">
                {identity.companyWithTicker}
              </h2>
              <div className="mt-4 grid min-w-0 grid-cols-1 gap-2 text-sm text-white/68 sm:grid-cols-2">
                <span>研究状态：{headerSignalLabel}</span>
                <span>评分：{dashboard.decision.heroValue}{dashboard.decision.heroUnit || ''}</span>
                <span>置信度：{dashboard.decision.confidenceValue || '--'}</span>
                <span>生成时间：{identity.generatedAt}</span>
                <span className="sm:col-span-2">覆盖状态：{identity.dataStatus}</span>
              </div>
            </div>
            <div className="flex min-w-0 flex-wrap gap-2">
              <button
                type="button"
                onClick={handleMarkdownExport}
                className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/[0.05] px-4 text-sm font-semibold text-white/72 transition-colors hover:border-white/20 hover:bg-white/[0.09] hover:text-white"
              >
                <Download className="size-4" />
                导出 Markdown
              </button>
              <button
                type="button"
                onClick={handlePrintReport}
                className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/[0.05] px-4 text-sm font-semibold text-white/72 transition-colors hover:border-white/20 hover:bg-white/[0.09] hover:text-white"
              >
                <Printer className="size-4" />
                导出 PDF
              </button>
              <button
                type="button"
                className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/[0.05] px-4 text-sm font-semibold text-white/72 transition-colors hover:border-white/20 hover:bg-white/[0.09] hover:text-white"
                onClick={() => { void handleCopyReport(); }}
              >
                <Copy className="size-4" />
                {copyState === 'copied' ? '已复制' : copyState === 'failed' ? '复制失败' : '复制报告'}
              </button>
            </div>
          </div>
          <div className="mt-4 grid min-w-0 grid-cols-2 gap-2 rounded-2xl border border-white/[0.06] bg-white/[0.025] p-3 text-xs text-white/56 md:grid-cols-4">
            <span>市场：{identity.market}</span>
            <span>币种：{identity.currency}</span>
            <span className="min-w-0 truncate">覆盖状态：{identity.dataStatus}</span>
            <span>周期：{identity.horizon}</span>
          </div>
          <p className="mt-4 rounded-xl border border-amber-300/18 bg-amber-300/8 px-3 py-2 text-sm text-amber-50/82">
            AI 洞察仅供参考，不构成投资建议。
          </p>
        </header>

        <section
          className="min-w-0 rounded-3xl border border-white/[0.08] bg-white/[0.03] p-4 sm:p-5"
          data-testid="home-bento-report-executive-summary"
        >
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-white/38">RESEARCH SUMMARY</p>
          <h3 className="mt-2 text-xl font-semibold tracking-[0] text-white">研究包完整度</h3>
          <div className="mt-3 flex flex-wrap gap-2 text-[10px] font-semibold tracking-[0.08em] text-white/42">
            {['继续跟踪', '情景参考', '数据不足'].map((label) => (
              <span key={label} className="rounded-full border border-white/[0.06] bg-black/20 px-2 py-1">{label}</span>
            ))}
          </div>
          <p className="mt-3 break-words text-sm leading-6 text-white/72">{summaryLine}</p>
          <div className="mt-4 grid min-w-0 grid-cols-1 gap-2 md:grid-cols-3">
            {[
              { label: '研究状态', value: observationLine },
              { label: '置信度', value: confidenceLine },
              { label: '风险边界', value: riskLine },
            ].map((item) => (
              <div key={item.label} className="min-w-0 rounded-2xl border border-white/[0.06] bg-black/20 p-3">
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-white/36">{item.label}</p>
                <p className="mt-1.5 break-words text-sm leading-6 text-white/76">{item.value}</p>
              </div>
            ))}
          </div>
        </section>

        <div className="grid min-w-0 grid-cols-1 gap-4 lg:grid-cols-2">
          {primaryReportSections.map((section) => (
            <section key={section.id} className="min-w-0 rounded-2xl border border-white/[0.07] bg-white/[0.025] p-4 sm:p-5" data-testid={`home-bento-full-report-section-${section.id}`}>
              <h3 className="text-base font-semibold tracking-[0] text-white">{section.title}</h3>
              {section.rows ? (
                <div className="mt-4 grid min-w-0 grid-cols-1 gap-2 sm:grid-cols-2">
                  {section.rows.map((row) => (
                    <div key={`${section.id}-${row.label}`} className="min-w-0 rounded-xl border border-white/[0.06] bg-black/16 px-3 py-2">
                      <p className="truncate text-[10px] font-semibold uppercase tracking-[0.14em] text-white/38">{row.label}</p>
                      <p className="mt-1 break-words text-sm leading-6 text-white/76">{row.value}</p>
                    </div>
                  ))}
                </div>
              ) : null}
              {section.bullets ? (
                <ul className="mt-4 space-y-2 text-sm leading-6 text-white/68">
                  {section.bullets.map((item) => (
                    <li key={`${section.id}-${item}`} className="break-words border-l border-white/10 pl-3">{item}</li>
                  ))}
                </ul>
              ) : null}
            </section>
          ))}
        </div>

        <details
          className="min-w-0 rounded-2xl border border-white/[0.07] bg-white/[0.02] p-4 sm:p-5"
          data-testid="home-bento-full-report-technical-details"
        >
          <summary className="cursor-pointer list-none text-sm font-semibold tracking-[0] text-white">
            技术细节
          </summary>
          <div className="mt-4 grid min-w-0 grid-cols-1 gap-4">
            {technicalSections.map((section) => (
              <section key={section.id} className="min-w-0 rounded-2xl border border-white/[0.07] bg-black/16 p-4" data-testid={`home-bento-full-report-section-${section.id}`}>
                <h3 className="text-base font-semibold tracking-[0] text-white">{section.title}</h3>
                {section.rows ? (
                  <div className="mt-4 grid min-w-0 grid-cols-1 gap-2 sm:grid-cols-2">
                    {section.rows.map((row) => (
                      <div key={`${section.id}-${row.label}`} className="min-w-0 rounded-xl border border-white/[0.06] bg-black/16 px-3 py-2">
                        <p className="truncate text-[10px] font-semibold uppercase tracking-[0.14em] text-white/38">{row.label}</p>
                        <p className="mt-1 break-words text-sm leading-6 text-white/76">{row.value}</p>
                      </div>
                    ))}
                  </div>
                ) : null}
                {section.bullets ? (
                  <ul className="mt-4 space-y-2 text-sm leading-6 text-white/68">
                    {section.bullets.map((item) => (
                      <li key={`${section.id}-${item}`} className="break-words border-l border-white/10 pl-3">{item}</li>
                    ))}
                  </ul>
                ) : null}
                {section.checklist ? (
                  <div className="mt-4 grid min-w-0 grid-cols-1 gap-2 sm:grid-cols-2">
                    {section.checklist.map((item) => (
                      <div key={`${section.id}-${item.label}`} className="flex min-w-0 items-center justify-between gap-3 rounded-xl border border-white/[0.06] bg-black/16 px-3 py-2 text-sm">
                        <span className="min-w-0 break-words text-white/72">{item.label}</span>
                        <TraceBadge tone={item.status === 'PASS' ? 'used' : item.status === 'FAIL' ? 'missing' : item.status === 'WARN' ? 'warning' : 'neutral'}>{item.status}</TraceBadge>
                      </div>
                    ))}
                  </div>
                ) : null}
              </section>
            ))}
          </div>
        </details>
      </article>
    </Drawer>
  );
};

export default FullDecisionReportDrawer;
