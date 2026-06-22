import type React from 'react';
import { useState } from 'react';
import { AlertTriangle, Play, ShieldCheck } from 'lucide-react';
import { backtestApi } from '../../api/backtest';
import ResearchArtifactRegistry, { type ResearchArtifactRegistryEntry } from '../research/ResearchArtifactRegistry';
import type {
  RuleBacktestParameterSweepBar,
  RuleBacktestParameterSweepResponse,
  RuleBacktestParseResponse,
} from '../../types/backtest';

type BacktestLanguage = 'zh' | 'en';

type ParameterSweepPanelProps = {
  language: BacktestLanguage;
  code: string;
  strategyText: string;
  startDate: string;
  endDate: string;
  lookbackBars: string;
  initialCapital: string;
  feeBps: string;
  slippageBps: string;
  parsedStrategy: RuleBacktestParseResponse | null;
  confirmed: boolean;
  parseStale: boolean;
};

type PanelStatus = 'idle' | 'submitting' | 'diagnostic' | 'blocked';

type PanelState = {
  status: PanelStatus;
  message: string | null;
  reasonCode: string | null;
  response: RuleBacktestParameterSweepResponse | null;
  requestSnapshot: SweepEvidenceRequestSnapshot | null;
};

const containerClass = 'rounded-xl border border-white/5 bg-black/20 p-4';
const fieldClass = 'w-full min-w-0 min-h-[42px] rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2 text-sm leading-6 text-white outline-none transition-all focus:border-blue-500/50 focus:bg-white/[0.05]';
const labelClass = 'text-[10px] font-bold uppercase tracking-widest text-white/40';
const primaryButtonClass = 'inline-flex min-h-[42px] items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-blue-600 to-purple-600 px-4 py-2 text-sm font-semibold text-white shadow-[0_0_15px_rgba(139,92,246,0.3)] transition-all hover:from-blue-500 hover:to-purple-500 disabled:cursor-not-allowed disabled:opacity-45';
const UNKNOWN_ZH = '待补证';
const UNKNOWN_EN = 'unknown';

type SweepEvidenceRequestSnapshot = {
  symbol: string;
  strategy: {
    provided: boolean;
    confirmed: boolean;
    parseFresh: boolean;
    parsedVersion: string;
    timeframe: string;
    executable: boolean | string;
  };
  dateRange: {
    startDate: string;
    endDate: string;
  };
  executionInputs: {
    lookbackBars: number;
    initialCapital: number;
    feeBps: number;
    slippageBps: number;
  };
  parameterGrid: Record<string, Array<string | number | boolean | null>>;
  maxCombinations: number;
  requestedCombinations: number;
  suppliedBars: {
    rowCount: number;
    firstDate: string;
    lastDate: string;
  };
};

const missingLineageFieldLabels: Record<string, { zh: string; en: string }> = {
  adjustedBasis: { zh: '复权基础', en: 'adjustment basis' },
  corporateActionPolicy: { zh: '公司行为政策', en: 'corporate action policy' },
  calendarSessionPolicy: { zh: '交易日历策略', en: 'calendar session policy' },
  pointInTimeMembershipStatus: { zh: 'PIT 会员状态', en: 'point-in-time membership' },
  survivorshipBiasMarker: { zh: '存活偏差标记', en: 'survivorship bias marker' },
  sourceAuthority: { zh: '来源校验', en: 'source validation' },
  datasetId: { zh: '数据集身份', en: 'dataset identity' },
  symbolUniverseId: { zh: '标的宇宙身份', en: 'symbol universe identity' },
  symbolIdentity: { zh: '标的身份', en: 'symbol identity' },
  marketExchange: { zh: '市场交易所', en: 'market exchange' },
  barSource: { zh: 'bar 来源', en: 'bar source' },
  asOfTimestamp: { zh: '截止时间戳', en: 'as-of timestamp' },
  sweepDatasetReference: { zh: '扫描数据集引用', en: 'sweep dataset reference' },
};

const forbiddenExportKeyPattern = /request(id|_id)?$|trace|debug|raw|payload|provider|credential|secret|token|cache/i;
const forbiddenResultKeyPattern = /request|trace|debug|raw|payload|provider|credential|secret|token|cache|target|stop|position|recommend|winner|optimal|best/i;

function formatHash(value: unknown): string {
  const text = String(value || '').trim();
  if (!text) return '--';
  return text.length > 16 ? `${text.slice(0, 12)}…${text.slice(-6)}` : text;
}

function toSafeLabel(field: string, language: BacktestLanguage): string {
  return missingLineageFieldLabels[field]?.[language] || (language === 'en' ? 'other lineage gap' : '其他谱系缺口');
}

function unknownLabel(language: BacktestLanguage): string {
  return language === 'en' ? UNKNOWN_EN : UNKNOWN_ZH;
}

function valueOrUnknown(value: unknown, language: BacktestLanguage): unknown {
  if (value == null || value === '') return unknownLabel(language);
  return value;
}

function booleanOrUnknown(value: unknown, language: BacktestLanguage): boolean | string {
  return typeof value === 'boolean' ? value : unknownLabel(language);
}

function sortedRecord<T>(record: Record<string, T>): Record<string, T> {
  return Object.keys(record)
    .sort((left, right) => left.localeCompare(right))
    .reduce<Record<string, T>>((acc, key) => {
      acc[key] = record[key];
      return acc;
    }, {});
}

function safePrimitiveRecord(record: unknown, options: { allowForbiddenKeys?: boolean } = {}): Record<string, unknown> {
  if (!record || typeof record !== 'object' || Array.isArray(record)) return {};
  return sortedRecord(Object.entries(record as Record<string, unknown>).reduce<Record<string, unknown>>((acc, [key, value]) => {
    if (!options.allowForbiddenKeys && forbiddenResultKeyPattern.test(key)) return acc;
    if (isPrimitiveValue(value)) {
      acc[key] = value;
    }
    return acc;
  }, {}));
}

function buildRequestSnapshot(params: {
  code: string;
  startDate: string;
  endDate: string;
  lookbackBars: number;
  initialCapital: number;
  feeBps: number;
  slippageBps: number;
  parameterGrid: Record<string, Array<string | number | boolean | null>>;
  maxCombinations: number;
  bars: RuleBacktestParameterSweepBar[];
  parsedStrategy: RuleBacktestParseResponse;
  confirmed: boolean;
  parseStale: boolean;
  strategyText: string;
}): SweepEvidenceRequestSnapshot {
  const sortedGrid = sortedRecord(params.parameterGrid);
  return {
    symbol: params.code.trim().toUpperCase(),
    strategy: {
      provided: Boolean(params.strategyText.trim()),
      confirmed: params.confirmed,
      parseFresh: !params.parseStale,
      parsedVersion: params.parsedStrategy.parsedStrategy?.version || UNKNOWN_ZH,
      timeframe: params.parsedStrategy.parsedStrategy?.timeframe || UNKNOWN_ZH,
      executable: typeof params.parsedStrategy.executable === 'boolean' ? params.parsedStrategy.executable : UNKNOWN_ZH,
    },
    dateRange: {
      startDate: params.startDate || UNKNOWN_ZH,
      endDate: params.endDate || UNKNOWN_ZH,
    },
    executionInputs: {
      lookbackBars: params.lookbackBars,
      initialCapital: params.initialCapital,
      feeBps: params.feeBps,
      slippageBps: params.slippageBps,
    },
    parameterGrid: sortedGrid,
    maxCombinations: params.maxCombinations,
    requestedCombinations: countCombinations(sortedGrid),
    suppliedBars: {
      rowCount: params.bars.length,
      firstDate: params.bars[0]?.date || UNKNOWN_ZH,
      lastDate: params.bars.at(-1)?.date || UNKNOWN_ZH,
    },
  };
}

function canExportEvidencePack(state: PanelState): state is PanelState & {
  response: RuleBacktestParameterSweepResponse;
  requestSnapshot: SweepEvidenceRequestSnapshot;
} {
  return state.status === 'diagnostic'
    && Boolean(state.response)
    && Boolean(state.requestSnapshot)
    && state.response?.state !== 'rejected'
    && state.response?.datasetLineageReadiness?.readinessState !== 'blocked'
    && !state.response?.failClosedReasonCode;
}

function buildEvidencePack(
  response: RuleBacktestParameterSweepResponse,
  requestSnapshot: SweepEvidenceRequestSnapshot,
  language: BacktestLanguage,
): Record<string, unknown> {
  const lineage = response.datasetLineageReadiness || {};
  const summary = response.summary || {};
  const parameterRows = Array.isArray(response.parameterRows) ? response.parameterRows : [];
  const rowCount = parameterRows.length;
  const scenarioCount = typeof summary.totalParameterSets === 'number'
    ? summary.totalParameterSets
    : (rowCount > 0 ? rowCount : unknownLabel(language));

  return {
    schemaVersion: 'backtest-sweep-evidence-pack.v1',
    generatedAt: new Date().toISOString(),
    appSurface: 'Backtest / Parameter Sweep',
    suppliedInputs: {
      symbol: requestSnapshot.symbol || unknownLabel(language),
      dateRange: requestSnapshot.dateRange,
      strategy: requestSnapshot.strategy,
      executionInputs: requestSnapshot.executionInputs,
      parameterGrid: requestSnapshot.parameterGrid,
      suppliedBars: requestSnapshot.suppliedBars,
    },
    parameterBounds: {
      maxCombinations: requestSnapshot.maxCombinations,
      requestedCombinations: requestSnapshot.requestedCombinations,
      parameterKeys: Object.keys(requestSnapshot.parameterGrid),
      constraints: {
        boundedSweep: true,
        externalHydration: false,
        storedRunIdentity: response.storage?.mode === 'response_only' ? 'response_only' : unknownLabel(language),
      },
    },
    datasetLineageReadiness: {
      readinessState: valueOrUnknown(lineage.readinessState, language),
      diagnosticOnly: booleanOrUnknown(lineage.diagnosticOnly ?? response.diagnosticOnly, language),
      decisionGrade: booleanOrUnknown(lineage.decisionGrade ?? response.decisionGrade, language),
      barBoundary: {
        suppliedBarsToRunner: booleanOrUnknown(lineage.barBoundary?.suppliedBarsToRunner, language),
        externalDataCallsExecuted: booleanOrUnknown(lineage.barBoundary?.providerCallsExecuted, language),
        localBars: booleanOrUnknown(lineage.barBoundary?.localBars, language),
        barCount: valueOrUnknown(lineage.barBoundary?.barCount ?? requestSnapshot.suppliedBars.rowCount, language),
      },
      provenanceState: valueOrUnknown(lineage.provenanceStatus?.state, language),
      missingLineageFields: Array.isArray(lineage.missingLineageFields) && lineage.missingLineageFields.length > 0
        ? lineage.missingLineageFields.map((field) => toSafeLabel(String(field), language))
        : [],
      reproducibility: {
        inputShapeHash: valueOrUnknown(lineage.reproducibility?.inputShapeHashSha256, language),
        gridDescriptorHash: valueOrUnknown(
          response.reproducibilityMetadata?.gridDescriptorHashSha256 || lineage.reproducibility?.gridDescriptorHashSha256,
          language,
        ),
      },
    },
    evidenceWarnings: {
      failClosedReasonCode: valueOrUnknown(response.failClosedReasonCode, language),
      missingLineageFields: Array.isArray(lineage.missingLineageFields) && lineage.missingLineageFields.length > 0
        ? lineage.missingLineageFields.map((field) => toSafeLabel(String(field), language))
        : [],
    },
    resultCounts: {
      rowCount,
      scenarioCount,
      runCount: valueOrUnknown(summary.runCount, language),
      executedCount: valueOrUnknown(summary.executedCount, language),
      completedCount: valueOrUnknown(summary.completedCount, language),
      blockedCount: valueOrUnknown(summary.blockedCount, language),
      failedCount: valueOrUnknown(summary.failedCount, language),
      skippedCount: valueOrUnknown(summary.skippedCount, language),
    },
    resultSummary: {
      state: valueOrUnknown(response.state, language),
      diagnosticOnly: Boolean(response.diagnosticOnly),
      researchOnly: Boolean(response.researchOnly),
      decisionGrade: Boolean(response.decisionGrade),
      sampleRows: parameterRows.slice(0, 5).map((row) => ({
        parameterSetId: valueOrUnknown(row.parameterSetId, language),
        state: valueOrUnknown(row.state, language),
        parameterValues: safePrimitiveRecord(row.parameterValues, { allowForbiddenKeys: true }),
        metrics: safePrimitiveRecord(row.metrics),
      })),
    },
    sourceStates: {
      externalHydration: false,
      storedReadback: booleanOrUnknown(lineage.provenanceStatus?.storedReadbackAvailable, language),
      dataHydration: booleanOrUnknown(lineage.provenanceStatus?.providerHydrationExecuted, language),
      unknownFieldsPolicy: unknownLabel(language),
    },
  };
}

function stringifyEvidencePack(pack: Record<string, unknown>): string {
  return JSON.stringify(pack, (key, value) => {
    if (forbiddenExportKeyPattern.test(key)) return undefined;
    return value;
  }, 2);
}

function formatLineageState(value: unknown, language: BacktestLanguage): string {
  const state = String(value || '').trim();
  if (state === 'blocked') return language === 'en' ? 'blocked' : '阻断';
  if (state === 'diagnostic-only') return language === 'en' ? 'diagnostic-only' : '诊断仅';
  return language === 'en' ? 'other' : '其他';
}

function parseJsonText(value: string): { ok: true; data: unknown } | { ok: false; message: string } {
  const trimmed = value.trim();
  if (!trimmed) {
    return { ok: false, message: 'empty' };
  }
  try {
    return { ok: true, data: JSON.parse(trimmed) as unknown };
  } catch {
    return { ok: false, message: 'invalid_json' };
  }
}

function isPrimitiveValue(value: unknown): value is string | number | boolean | null {
  return value === null || ['string', 'number', 'boolean'].includes(typeof value);
}

function parseGrid(value: string): { ok: true; data: Record<string, Array<string | number | boolean | null>> } | { ok: false; message: string } {
  const parsed = parseJsonText(value);
  if (!parsed.ok) {
    return { ok: false, message: parsed.message === 'empty' ? 'empty_grid' : 'invalid_grid_json' };
  }
  if (!parsed.data || Array.isArray(parsed.data) || typeof parsed.data !== 'object') {
    return { ok: false, message: 'invalid_grid_shape' };
  }
  const next: Record<string, Array<string | number | boolean | null>> = {};
  for (const [key, rawValues] of Object.entries(parsed.data as Record<string, unknown>)) {
    if (!key.trim() || !Array.isArray(rawValues) || rawValues.length === 0) {
      return { ok: false, message: 'invalid_grid_shape' };
    }
    if (!rawValues.every((item) => isPrimitiveValue(item))) {
      return { ok: false, message: 'invalid_grid_shape' };
    }
    const nextValues = rawValues as Array<string | number | boolean | null>;
    next[key] = nextValues;
  }
  if (Object.keys(next).length === 0) {
    return { ok: false, message: 'empty_grid' };
  }
  return { ok: true, data: next };
}

function parseBars(value: string): { ok: true; data: RuleBacktestParameterSweepBar[] } | { ok: false; message: string } {
  const parsed = parseJsonText(value);
  if (!parsed.ok) {
    return { ok: false, message: parsed.message === 'empty' ? 'empty_bars' : 'invalid_bars_json' };
  }
  if (!Array.isArray(parsed.data) || parsed.data.length === 0) {
    return { ok: false, message: 'invalid_bars_shape' };
  }
  const next: RuleBacktestParameterSweepBar[] = [];
  for (const item of parsed.data) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) {
      return { ok: false, message: 'invalid_bars_shape' };
    }
    const record = item as Record<string, unknown>;
    const date = String(record.date || '').trim();
    const open = Number(record.open);
    const high = Number(record.high);
    const low = Number(record.low);
    const close = Number(record.close);
    const volume = record.volume == null || record.volume === '' ? null : Number(record.volume);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !Number.isFinite(open) || !Number.isFinite(high) || !Number.isFinite(low) || !Number.isFinite(close)) {
      return { ok: false, message: 'invalid_bars_shape' };
    }
    if (volume != null && !Number.isFinite(volume)) {
      return { ok: false, message: 'invalid_bars_shape' };
    }
    next.push({
      code: record.code == null || record.code === '' ? null : String(record.code),
      date,
      open,
      high,
      low,
      close,
      volume,
    });
  }
  return { ok: true, data: next };
}

function countCombinations(grid: Record<string, Array<string | number | boolean | null>>): number {
  const counts = Object.values(grid).map((values) => values.length);
  return counts.reduce((acc, count) => acc * count, 1);
}

function getStateTone(status: PanelStatus): 'success' | 'warning' | 'neutral' {
  if (status === 'diagnostic') return 'success';
  if (status === 'blocked') return 'warning';
  if (status === 'submitting') return 'neutral';
  return 'neutral';
}

function stateBadgeClass(status: PanelStatus): string {
  const tone = getStateTone(status);
  if (tone === 'success') return 'border-emerald-400/25 bg-emerald-400/10 text-emerald-100';
  if (tone === 'warning') return 'border-amber-400/25 bg-amber-400/10 text-amber-100';
  return 'border-white/10 bg-white/[0.03] text-white/58';
}

function getInitialState(): PanelState {
  return {
    status: 'idle',
    message: null,
    reasonCode: null,
    response: null,
    requestSnapshot: null,
  };
}

function makeBlockedState(message: string, reasonCode: string, response: RuleBacktestParameterSweepResponse | null = null): PanelState {
  return {
    status: 'blocked',
    message,
    reasonCode,
    response,
    requestSnapshot: null,
  };
}

const ParameterSweepPanel: React.FC<ParameterSweepPanelProps> = ({
  language,
  code,
  strategyText,
  startDate,
  endDate,
  lookbackBars,
  initialCapital,
  feeBps,
  slippageBps,
  parsedStrategy,
  confirmed,
  parseStale,
}) => {
  const [parameterGridText, setParameterGridText] = useState('');
  const [barsText, setBarsText] = useState('');
  const [maxCombinationsText, setMaxCombinationsText] = useState('10');
  const [state, setState] = useState<PanelState>(getInitialState());

  const response = state.response;
  const responseSummary = response?.summary || {};
  const lineage = response?.datasetLineageReadiness || {};
  const missingFields = Array.isArray(lineage.missingLineageFields) ? lineage.missingLineageFields : [];
  const reproducibility = response?.reproducibilityMetadata || {};
  const barBoundary = lineage.barBoundary || {};
  const provenance = lineage.provenanceStatus || {};
  const exportableEvidencePack = canExportEvidencePack(state)
    ? stringifyEvidencePack(buildEvidencePack(state.response, state.requestSnapshot, language))
    : null;
  const artifactState: ResearchArtifactRegistryEntry['state'] = exportableEvidencePack
    ? 'available'
    : (state.status === 'blocked' ? 'blocked' : 'unavailable');
  const artifactFileName = state.requestSnapshot?.symbol
    ? `backtest-sweep-evidence-pack-${state.requestSnapshot.symbol}.json`
    : 'backtest-sweep-evidence-pack.json';
  const artifactRegistryEntry: ResearchArtifactRegistryEntry = {
    packKey: 'backtest-sweep-evidence-pack',
    label: language === 'en' ? 'Backtest Sweep evidence pack' : 'Backtest Sweep 研究证据包',
    schemaVersion: 'backtest-sweep-evidence-pack.v1',
    sourceSurface: 'Backtest Sweep',
    state: artifactState,
    description: language === 'en'
      ? 'JSON export for supplied inputs, bounded parameters, lineage, warnings, and compact result counts.'
      : 'JSON 导出已输入条件、有界参数、谱系、告警与紧凑结果计数。',
    contents: language === 'en'
      ? ['supplied inputs', 'bounded parameters', 'lineage readiness', 'compact result counts']
      : ['已输入条件、有界参数、谱系、告警与紧凑结果计数'],
    exportContent: exportableEvidencePack,
    fileName: artifactFileName,
    copyLabel: language === 'en' ? 'Copy evidence pack' : '复制证据包',
    downloadLabel: language === 'en' ? 'Export evidence pack' : '导出研究证据包',
    copyTestId: 'pro-parameter-sweep-evidence-copy',
    downloadTestId: 'pro-parameter-sweep-evidence-download',
    blockedCopyTestId: 'pro-parameter-sweep-registry-copy-blocked',
  };

  const readinessChips = [
    response?.diagnosticOnly ? (language === 'en' ? 'diagnostic only' : '诊断仅') : null,
    response?.researchOnly ? (language === 'en' ? 'research only' : '研究仅') : null,
    response?.storage?.mode === 'response_only' ? (language === 'en' ? 'response only' : '仅响应') : null,
    provenance.providerHydrationExecuted === false ? (language === 'en' ? 'hydration off' : '补全关闭') : null,
    provenance.storedReadbackAvailable === false ? (language === 'en' ? 'no stored run identity' : '无存储身份') : null,
  ].filter((item): item is string => Boolean(item));

  const handleRun = async () => {
    const runApi = backtestApi.runRuleParameterSweep;
    if (typeof runApi !== 'function') {
      setState(makeBlockedState(
        language === 'en'
          ? 'Parameter sweep API is unavailable. No request was sent.'
          : '参数扫描接口暂不可用，未发送请求。',
        'api_unavailable',
      ));
      return;
    }
    if (!code.trim() || !strategyText.trim() || !parsedStrategy || !confirmed || parseStale) {
      setState(makeBlockedState(
        language === 'en'
          ? 'Parse and confirm the rule before running the sweep.'
          : '请先解析并确认规则，再提交扫描。',
        'missing_parse_confirmation',
      ));
      return;
    }
    if (!startDate || !endDate || startDate > endDate) {
      setState(makeBlockedState(
        language === 'en'
          ? 'Date range is invalid for the sweep request.'
          : '扫描请求的日期区间无效。',
        'invalid_date_range',
      ));
      return;
    }

    const lookback = Number.parseInt(lookbackBars.trim(), 10);
    const capital = Number.parseFloat(initialCapital.trim());
    const fee = Number.parseFloat(feeBps.trim());
    const slippage = Number.parseFloat(slippageBps.trim());
    const maxCombinations = Number.parseInt(maxCombinationsText.trim(), 10);
    if (!Number.isFinite(lookback) || lookback < 1
      || !Number.isFinite(capital) || capital <= 0
      || !Number.isFinite(fee) || fee < 0
      || !Number.isFinite(slippage) || slippage < 0
      || !Number.isFinite(maxCombinations) || maxCombinations < 1) {
      setState(makeBlockedState(
        language === 'en'
          ? 'Sweep inputs must be valid positive numbers.'
          : '扫描输入必须为有效正数。',
        'invalid_numeric_input',
      ));
      return;
    }

    const gridResult = parseGrid(parameterGridText);
    if (!gridResult.ok) {
      setState(makeBlockedState(
        language === 'en'
          ? 'Parameter grid must be valid JSON with non-empty arrays.'
          : '参数网格必须是包含非空数组的有效 JSON。',
        gridResult.message,
      ));
      return;
    }
    const barsResult = parseBars(barsText);
    if (!barsResult.ok) {
      setState(makeBlockedState(
        language === 'en'
          ? 'Supplied bars must be a non-empty JSON array of local OHLCV rows.'
          : '输入 bars 必须是非空的本地 OHLCV JSON 数组。',
        barsResult.message,
      ));
      return;
    }

    const combinationCount = countCombinations(gridResult.data);
    if (combinationCount > maxCombinations) {
      setState(makeBlockedState(
        language === 'en'
          ? 'Parameter grid exceeds the bounded sweep cap.'
          : '参数网格超过了本次有界扫描上限。',
        'max_combinations_rejected',
      ));
      return;
    }

    setState({
      status: 'submitting',
      message: null,
      reasonCode: null,
      response: null,
      requestSnapshot: null,
    });

    try {
      const requestSnapshot = buildRequestSnapshot({
        code,
        startDate,
        endDate,
        lookbackBars: lookback,
        initialCapital: capital,
        feeBps: fee,
        slippageBps: slippage,
        parameterGrid: gridResult.data,
        maxCombinations,
        bars: barsResult.data,
        parsedStrategy,
        confirmed,
        parseStale,
        strategyText,
      });
      const result = await runApi({
        code: code.trim().toUpperCase(),
        strategyText,
        parsedStrategy: parsedStrategy.parsedStrategy,
        startDate,
        endDate,
        lookbackBars: lookback,
        initialCapital: capital,
        feeBps: fee,
        slippageBps: slippage,
        confirmed: true,
        parameterGrid: gridResult.data,
        maxCombinations,
        bars: barsResult.data,
      });
      if (result.state === 'rejected' || result.datasetLineageReadiness?.readinessState === 'blocked' || result.failClosedReasonCode) {
        setState({
          status: 'blocked',
          message: language === 'en'
            ? 'Sweep returned a fail-closed diagnostic state.'
            : '扫描返回了 fail-closed 诊断状态。',
          reasonCode: result.failClosedReasonCode || result.datasetLineageReadiness?.stateReasonCode || 'blocked',
          response: result,
          requestSnapshot,
        });
        return;
      }
      setState({
        status: 'diagnostic',
        message: null,
        reasonCode: null,
        response: result,
        requestSnapshot,
      });
    } catch {
      setState(makeBlockedState(
        language === 'en'
          ? 'Sweep request failed. No result was stored.'
          : '扫描请求失败，未存储结果。',
        'request_unavailable',
      ));
    }
  };

  const renderRow = (label: string, value: React.ReactNode) => (
    <div className="rounded-lg border border-white/5 bg-white/[0.02] p-3">
      <p className={labelClass}>{label}</p>
      <div className="mt-2 text-sm text-white/78">{value}</div>
    </div>
  );

  const renderSummaryChip = (label: string, value: unknown) => (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-white/68">
      <span>{label}</span>
      <span>{String(value ?? '--')}</span>
    </span>
  );

  return (
    <section data-testid="pro-parameter-sweep-panel" className="flex min-w-0 flex-col gap-4">
      <div className={containerClass}>
        <div className="flex min-w-0 flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0">
            <p className={labelClass}>{language === 'en' ? 'Parameter sweep' : '参数扫描'}</p>
            <h3 className="mt-2 text-lg font-semibold text-white">
              {language === 'en' ? 'Bounded supplied-input sweep' : '有界的输入驱动参数扫描'}
            </h3>
            <p className="mt-1 text-sm text-white/52">
              {language === 'en'
                ? 'Research-only, diagnostic-only, no stored run identity, no external hydration.'
                : '仅用于研究与诊断，不生成存储运行身份，不执行外部补全。'}
            </p>
          </div>
          <div className="flex min-w-0 flex-wrap gap-2">
            {readinessChips.map((chip) => (
              <span key={chip} className={`rounded-full border px-2.5 py-1 text-[11px] ${stateBadgeClass(state.status)}`}>
                {chip}
              </span>
            ))}
          </div>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-[1.2fr_0.8fr]">
          <label className="flex min-w-0 flex-col gap-2 xl:col-span-1">
            <span className={labelClass}>{language === 'en' ? 'Parameter grid JSON' : '参数网格 JSON'}</span>
            <textarea
              className={`${fieldClass} min-h-[180px] resize-y font-mono text-xs leading-6`}
              value={parameterGridText}
              onChange={(event) => setParameterGridText(event.target.value)}
              placeholder={language === 'en'
                ? '{"strategy_spec.<path>":[...]}'
                : '{"strategy_spec.<路径>":[...]}'}
              aria-label={language === 'en' ? 'Parameter grid JSON' : '参数网格 JSON'}
            />
          </label>
          <label className="flex min-w-0 flex-col gap-2 xl:col-span-1">
            <span className={labelClass}>{language === 'en' ? 'Supplied bars JSON' : '输入 bars JSON'} </span>
            <textarea
              className={`${fieldClass} min-h-[180px] resize-y font-mono text-xs leading-6`}
              value={barsText}
              onChange={(event) => setBarsText(event.target.value)}
              placeholder={language === 'en'
                ? '[{"date":"YYYY-MM-DD","open":0,"high":0,"low":0,"close":0,"volume":0}]'
                : '[{"date":"YYYY-MM-DD","open":0,"high":0,"low":0,"close":0,"volume":0}]'}
              aria-label={language === 'en' ? 'Supplied bars JSON' : '输入 bars JSON'}
            />
          </label>
          <div className="grid gap-3 md:grid-cols-3 xl:col-span-2">
            <label className="flex min-w-0 flex-col gap-2">
              <span className={labelClass}>{language === 'en' ? 'Max combinations' : '最大组合数'}</span>
              <input
                type="number"
                min={1}
                max={10}
                step={1}
                className={`${fieldClass} font-mono`}
                value={maxCombinationsText}
                onChange={(event) => setMaxCombinationsText(event.target.value)}
                aria-label={language === 'en' ? 'Max combinations' : '最大组合数'}
              />
            </label>
            {renderRow(language === 'en' ? 'Sweep basis' : '扫描基准', (
              <div className="flex flex-wrap gap-2">
                <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-xs text-white/62">{code || '--'}</span>
                <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-xs text-white/62">{startDate || '--'}</span>
                <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-xs text-white/62">{endDate || '--'}</span>
              </div>
            ))}
            {renderRow(language === 'en' ? 'Execution guard' : '执行护栏', (
              <div className="flex flex-wrap gap-2">
                <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-xs text-white/62">{language === 'en' ? 'confirmed' : '已确认'}</span>
                <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-xs text-white/62">{language === 'en' ? 'research only' : '研究仅'}</span>
                <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-xs text-white/62">{parseStale ? (language === 'en' ? 'stale' : '已过期') : (language === 'en' ? 'fresh' : '最新')}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-4 flex min-w-0 flex-wrap gap-2">
          <button
            type="button"
            className={primaryButtonClass}
            onClick={() => void handleRun()}
            disabled={state.status === 'submitting'}
            data-testid="pro-parameter-sweep-run-button"
          >
            <Play className="size-4" />
            {state.status === 'submitting'
              ? (language === 'en' ? 'Running...' : '扫描中...')
              : (language === 'en' ? 'Run sweep' : '运行扫描')}
          </button>
          <span className={`inline-flex min-h-[42px] items-center gap-2 rounded-lg border px-3 py-2 text-sm ${stateBadgeClass(state.status)}`}>
            <ShieldCheck className="size-4" />
            {state.status === 'diagnostic'
              ? (language === 'en' ? 'diagnostic-only result' : '诊断仅结果')
              : state.status === 'blocked'
                ? (language === 'en' ? 'blocked' : '阻断')
                : state.status === 'submitting'
                  ? (language === 'en' ? 'submitting' : '提交中')
                  : (language === 'en' ? 'idle' : '待执行')}
          </span>
        </div>

        {state.status === 'blocked' ? (
          <div data-testid="pro-parameter-sweep-blocked" className="mt-4 rounded-lg border border-amber-400/20 bg-amber-400/10 p-3 text-sm text-amber-50">
            <div className="flex min-w-0 items-start gap-2">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" />
              <div className="min-w-0">
                <p className="font-semibold">
                  {language === 'en' ? 'Blocked diagnostic state' : '阻断的诊断状态'}
                </p>
                <p className="mt-1 text-amber-50/80">{state.message}</p>
                {state.reasonCode ? (
                  <p className="mt-1 text-xs text-amber-50/70">
                    {language === 'en' ? 'Reason code' : '原因码'}: {state.reasonCode}
                  </p>
                ) : null}
              </div>
            </div>
          </div>
        ) : null}

        {response ? (
          <div data-testid="pro-parameter-sweep-result" className="mt-4 grid gap-3">
            <div className="grid gap-3 md:grid-cols-4">
              {renderRow(language === 'en' ? 'State' : '状态', response.state || '--')}
              {renderRow(language === 'en' ? 'Run count' : '运行数', responseSummary.runCount)}
              {renderRow(language === 'en' ? 'Skipped count' : '跳过数', responseSummary.skippedCount)}
              {renderRow(language === 'en' ? 'Blocked count' : '阻断数', responseSummary.blockedCount)}
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {renderRow(language === 'en' ? 'Lineage state' : '谱系状态', formatLineageState(lineage.readinessState, language))}
              {renderRow(language === 'en' ? 'Bar boundary' : 'bar 边界', (
                <div className="flex flex-wrap gap-2">
                  <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-xs text-white/62">
                    {language === 'en' ? 'supplied bars' : '已输入 bars'}: {barBoundary.suppliedBarsToRunner === false ? 'false' : 'true'}
                  </span>
                  <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-xs text-white/62">
                    {language === 'en' ? 'hydration calls' : '补全调用'}: {barBoundary.providerCallsExecuted === false ? 'false' : 'true'}
                  </span>
                  <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-xs text-white/62">
                    {language === 'en' ? 'local bars' : '本地 bars'}: {barBoundary.localBars === false ? 'false' : 'true'}
                  </span>
                </div>
              ))}
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {renderRow(language === 'en' ? 'Missing lineage gaps' : '缺失谱系项', missingFields.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {missingFields.map((field) => (
                    <span key={field} className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-xs text-white/62">
                      {toSafeLabel(field, language)}
                    </span>
                  ))}
                </div>
              ) : (language === 'en' ? 'none' : '无'))}
              {renderRow(language === 'en' ? 'Reproducibility hashes' : '可复现性哈希', (
                <div className="flex flex-wrap gap-2">
                  <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-xs text-white/62">
                    {language === 'en' ? 'input shape' : '输入形状'}: {formatHash(lineage.reproducibility?.inputShapeHashSha256)}
                  </span>
                  <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-xs text-white/62">
                    {language === 'en' ? 'grid descriptor' : '网格描述'}: {formatHash(reproducibility.gridDescriptorHashSha256 || lineage.reproducibility?.gridDescriptorHashSha256)}
                  </span>
                </div>
              ))}
            </div>
            <div className="grid gap-3 md:grid-cols-3">
              {renderRow(language === 'en' ? 'Diagnostic only' : '诊断仅', String(Boolean(response.diagnosticOnly)))}
              {renderRow(language === 'en' ? 'Research only' : '研究仅', String(Boolean(response.researchOnly)))}
              {renderRow(language === 'en' ? 'No stored run identity' : '无存储身份', language === 'en' ? 'response only' : '仅响应')}
            </div>
            {response.failClosedReasonCode ? (
              <div className="rounded-lg border border-amber-400/20 bg-amber-400/10 p-3 text-sm text-amber-50">
                <p className="font-semibold">{language === 'en' ? 'Fail-closed response' : 'fail-closed 响应'}</p>
                <p className="mt-1 text-amber-50/80">{response.failClosedReasonCode}</p>
              </div>
            ) : null}
            <ResearchArtifactRegistry
              locale={language}
              entries={[artifactRegistryEntry]}
              testId="pro-parameter-sweep-artifact-registry"
            />
          </div>
        ) : null}
        {!response ? (
          <ResearchArtifactRegistry
            locale={language}
            entries={[artifactRegistryEntry]}
            testId="pro-parameter-sweep-artifact-registry"
            className="mt-4"
          />
        ) : null}
      </div>

      <div className="rounded-xl border border-white/5 bg-black/20 p-4">
        <p className={labelClass}>{language === 'en' ? 'Request scope' : '请求范围'}</p>
        <div className="mt-3 flex min-w-0 flex-wrap gap-2">
          {renderSummaryChip(language === 'en' ? 'code' : '代码', code || '--')}
          {renderSummaryChip(language === 'en' ? 'lookback' : '回看', lookbackBars || '--')}
          {renderSummaryChip(language === 'en' ? 'capital' : '资金', initialCapital || '--')}
          {renderSummaryChip(language === 'en' ? 'fee bp' : '手续费 bp', feeBps || '--')}
          {renderSummaryChip(language === 'en' ? 'slippage bp' : '滑点 bp', slippageBps || '--')}
          {renderSummaryChip(language === 'en' ? 'confirmed' : '已确认', confirmed ? 'true' : 'false')}
          {renderSummaryChip(language === 'en' ? 'parse fresh' : '解析最新', parseStale ? 'false' : 'true')}
        </div>
      </div>
    </section>
  );
};

export default ParameterSweepPanel;
