import type React from 'react';
import { useState } from 'react';
import { AnimatePresence, domAnimation, LazyMotion, m } from 'motion/react';
import { ApiErrorAlert } from '../common/ApiErrorAlert';
import { Button } from '../common/Button';
import { Card } from '../common/Card';
import { Pagination } from '../common/Pagination';
import type { ParsedApiError } from '../../api/error';
import type {
  AssumptionMap,
  BacktestResultItem,
  BacktestRunHistoryItem,
  BacktestRunResponse,
  BacktestSampleStatusResponse,
  PrepareBacktestSamplesResponse,
} from '../../types/backtest';
import {
  AssumptionList,
  Banner,
  Disclosure,
  HistoricalResultsTable,
  HistoricalRunSummary,
  HistoricalRunsTable,
  SectionEyebrow,
  SummaryStrip,
  describeHistoricalDataSource,
  getHistoricalFallbackLabel,
  getHistoricalRequestedModeLabel,
  getHistoricalResolvedSourceLabel,
} from './shared';

type Props = {
  normalizedCode: string;
  codeFilter: string;
  onCodeChange: (value: string) => void;
  onCodeEnter: (event: React.KeyboardEvent<HTMLInputElement>) => void;
  evaluationBars: string;
  onEvaluationBarsChange: (value: string) => void;
  maturityDays: string;
  onMaturityDaysChange: (value: string) => void;
  samplePreset: string;
  onSamplePresetChange: (value: string) => void;
  customSampleCount: string;
  onCustomSampleCountChange: (value: string) => void;
  resolvedSampleCount: number;
  forceReplaceResults: boolean;
  onForceReplaceResultsChange: (value: boolean) => void;
  onFilter: () => void;
  onPrepareSamples: () => Promise<void>;
  onRebuildSamples: () => Promise<void>;
  onClearSamples: () => Promise<void>;
  onRunEvaluation: () => Promise<void>;
  onClearResults: () => Promise<void>;
  isPreparingSamples: boolean;
  isRunningHistoricalEval: boolean;
  runResult: BacktestRunResponse | null;
  runError: ParsedApiError | null;
  prepareResult: PrepareBacktestSamplesResponse | null;
  prepareError: ParsedApiError | null;
  sampleStatus: BacktestSampleStatusResponse | null;
  sampleStatusError: ParsedApiError | null;
  historicalAssumptions: AssumptionMap | null;
  historicalSourceMetadata: {
    requestedMode: string | null;
    resolvedSource: string | null;
    fallbackUsed: boolean | null;
  };
  historicalSampleTransparency: string;
  isLoadingSampleStatus: boolean;
  isLoadingPerf: boolean;
  historicalSummaryItems: Array<{ label: string; value: string; note?: string }>;
  performanceNotice: { tone: 'warning' | 'danger'; message: string } | null;
  results: BacktestResultItem[];
  totalResults: number;
  currentPage: number;
  pageSize: number;
  onChangeResultsPage: (page: number) => void;
  pageError: ParsedApiError | null;
  isLoadingResults: boolean;
  historyItems: BacktestRunHistoryItem[];
  historyTotal: number;
  historyPage: number;
  historyPageSize: number;
  onChangeHistoryPage: (page: number) => void;
  onOpenHistoricalRun: (run: BacktestRunHistoryItem) => Promise<void>;
  selectedRunId: number | null;
  historyError: ParsedApiError | null;
  isLoadingHistory: boolean;
  panelMode: 'normal' | 'professional';
};

type HistoricalWizardStep = 'scope' | 'params' | 'execute' | 'results';
const GHOST_FIELD_CLASS = 'w-full min-w-0 min-h-[44px] rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2.5 text-sm leading-6 text-white outline-none transition-all focus:border-emerald-500/50 focus:bg-white/[0.05]';
const GHOST_CHECKBOX_CLASS = 'h-4 w-4 shrink-0 rounded border border-white/15 bg-white/[0.03] text-emerald-400 accent-emerald-400';

const HistoricalEvaluationPanel: React.FC<Props> = ({
  normalizedCode,
  codeFilter,
  onCodeChange,
  onCodeEnter,
  evaluationBars,
  onEvaluationBarsChange,
  maturityDays,
  onMaturityDaysChange,
  samplePreset,
  onSamplePresetChange,
  customSampleCount,
  onCustomSampleCountChange,
  resolvedSampleCount,
  forceReplaceResults,
  onForceReplaceResultsChange,
  onFilter,
  onPrepareSamples,
  onRebuildSamples,
  onClearSamples,
  onRunEvaluation,
  onClearResults,
  isPreparingSamples,
  isRunningHistoricalEval,
  runResult,
  runError,
  prepareResult,
  prepareError,
  sampleStatus,
  sampleStatusError,
  historicalAssumptions,
  historicalSourceMetadata,
  historicalSampleTransparency,
  isLoadingSampleStatus,
  isLoadingPerf,
  historicalSummaryItems,
  performanceNotice,
  results,
  totalResults,
  currentPage,
  pageSize,
  onChangeResultsPage,
  pageError,
  isLoadingResults,
  historyItems,
  historyTotal,
  historyPage,
  historyPageSize,
  onChangeHistoryPage,
  onOpenHistoricalRun,
  selectedRunId,
  historyError,
  isLoadingHistory,
  panelMode,
}) => {
  const [currentStep, setCurrentStep] = useState<HistoricalWizardStep>('scope');
  const sourceSummary = describeHistoricalDataSource(historicalSourceMetadata);
  const modeSummaryItems = [
    {
      label: '评估范围',
      value: normalizedCode || '全部标的',
      note: normalizedCode ? '当前按单一标的过滤' : '当前查看整体汇总',
    },
    {
      label: '样本状态',
      value: isLoadingSampleStatus
        ? '同步中'
        : sampleStatus?.preparedCount != null
          ? String(sampleStatus.preparedCount)
          : prepareResult
            ? `+${prepareResult.prepared}`
            : '--',
      note: sampleStatus?.preparedStartDate && sampleStatus?.preparedEndDate
        ? `${sampleStatus.preparedStartDate} -> ${sampleStatus.preparedEndDate}`
        : '样本准备状态',
    },
    {
      label: '评估执行',
      value: isRunningHistoricalEval ? '运行中' : runResult ? '已有最新结果' : '等待执行',
      note: runResult?.runId ? `运行 #${runResult.runId}` : '等待执行',
    },
    {
      label: '结果视图',
      value: isLoadingResults ? '刷新中' : String(totalResults),
      note: selectedRunId ? `锁定运行 #${selectedRunId}` : '当前过滤结果',
    },
  ];
  const isProfessionalMode = panelMode === 'professional';

  const handleRunEvaluationClick = async () => {
    if (!isProfessionalMode) {
      setCurrentStep('results');
    }
    await onRunEvaluation();
  };

  const handleOpenHistoricalRun = async (run: BacktestRunHistoryItem) => {
    if (!isProfessionalMode) {
      setCurrentStep('results');
    }
    await onOpenHistoricalRun(run);
  };

  const scopeSamplesSection = (
    <section className="backtest-control-section" data-testid="historical-control-section-scope-samples" data-active={currentStep === 'scope' ? 'true' : 'false'}>
      <Card title="范围与样本" subtitle="步骤 1" className="product-section-card product-section-card--backtest-standard">
        {!isProfessionalMode ? (
          <p className="backtest-guided-step-helper">先确定标的范围和样本规模，再准备或重建历史评估样本。</p>
        ) : null}
        <label className="product-field">
          <span className="theme-field-label">股票代码</span>
          <input
            type="text"
            className={GHOST_FIELD_CLASS}
            value={codeFilter}
            onChange={(event) => onCodeChange(event.target.value.toUpperCase())}
            onKeyDown={onCodeEnter}
            placeholder="输入股票代码，如 AAPL 或 600519"
            aria-label="股票代码"
          />
          <span className="product-field-help">留空时查看整体汇总；准备样本、清理样本时建议指定单一股票。</span>
        </label>
        <label className="product-field">
          <span className="theme-field-label">分析样本数</span>
          <div className="product-inline-fields">
            <select
              className={`${GHOST_FIELD_CLASS} appearance-none pr-10 truncate`}
              value={samplePreset}
              onChange={(event) => onSamplePresetChange(event.target.value)}
              aria-label="分析样本数"
            >
              <option value="20">20</option>
              <option value="60">60</option>
              <option value="120">120</option>
              <option value="252">252</option>
              <option value="custom">自定义</option>
            </select>
            {samplePreset === 'custom' ? (
              <input
                type="number"
                className={GHOST_FIELD_CLASS}
                min={1}
                max={365}
                value={customSampleCount}
                onChange={(event) => onCustomSampleCountChange(event.target.value)}
                aria-label="自定义样本数"
              />
            ) : null}
          </div>
          <span className="product-field-help">表示要准备多少条分析样本，而不是天数。</span>
        </label>
        <div className="product-chip-list">
          <span className="product-chip">目标样本数: {resolvedSampleCount} 条</span>
        </div>
        <div className="product-action-row backtest-control-actions">
          <Button variant="secondary" onClick={onFilter}>应用筛选</Button>
          <Button variant="secondary" onClick={() => void onPrepareSamples()} isLoading={isPreparingSamples} disabled={!normalizedCode} loadingText="准备中…">
            准备分析样本
          </Button>
          <Button variant="outline" onClick={() => void onRebuildSamples()} disabled={isPreparingSamples || !normalizedCode}>
            重建样本
          </Button>
          <Button variant="ghost" onClick={() => void onClearSamples()} disabled={isPreparingSamples || !normalizedCode}>
            清理样本
          </Button>
        </div>
        {prepareResult ? (
          <Banner
            tone="success"
            title="样本准备完成"
            body={(
              <>
                新增 {prepareResult.prepared} 条样本，跳过 {prepareResult.skippedExisting} 条已有样本。
                {prepareResult.noResultMessage ? <span className="product-banner__meta">{prepareResult.noResultMessage}</span> : null}
              </>
            )}
            className="mt-4"
          />
        ) : null}
        {prepareError ? <ApiErrorAlert error={prepareError} className="mt-4" /> : null}
        <div className="product-action-row backtest-control-actions backtest-control-actions--footer">
          <Button onClick={() => setCurrentStep('params')}>继续</Button>
        </div>
      </Card>
    </section>
  );

  const paramsSection = (
    <section className="backtest-control-section" data-testid="historical-control-section-params" data-active={currentStep === 'params' ? 'true' : 'false'}>
      <Card title="评估参数" subtitle="步骤 2" className="product-section-card product-section-card--backtest-standard">
        {!isProfessionalMode ? (
          <p className="backtest-guided-step-helper">设置评估窗口、成熟期和覆盖策略，确保结果口径一致。</p>
        ) : null}
        <SummaryStrip items={modeSummaryItems} />
        <Banner
          tone={sourceSummary.tone}
          className="mt-4"
          title={sourceSummary.title}
          body={(
            <>
              {sourceSummary.body}
              <span className="product-banner__meta">{sourceSummary.detail}</span>
            </>
          )}
        />
        <Disclosure summary="查看数据可用性说明">
          <div className="preview-grid">
            <div className="preview-card">
              <p className="metric-card__label">请求方式</p>
              <p className="preview-card__text">{getHistoricalRequestedModeLabel(historicalSourceMetadata.requestedMode)}</p>
            </div>
            <div className="preview-card">
              <p className="metric-card__label">实际数据来源</p>
              <p className="preview-card__text">{getHistoricalResolvedSourceLabel(historicalSourceMetadata.resolvedSource)}</p>
            </div>
            <div className="preview-card">
              <p className="metric-card__label">备用数据状态</p>
              <p className="preview-card__text">{getHistoricalFallbackLabel(historicalSourceMetadata.fallbackUsed)}</p>
            </div>
          </div>
          <p className="product-footnote mt-4">{historicalSampleTransparency}</p>
        </Disclosure>
        <div className="product-field-grid backtest-control-grid">
          <label className="product-field">
            <span className="theme-field-label">评估窗口</span>
            <input
              type="number"
              className={GHOST_FIELD_CLASS}
              min={1}
              max={120}
              value={evaluationBars}
              onChange={(event) => onEvaluationBarsChange(event.target.value)}
              aria-label="评估窗口"
            />
            <span className="product-field-help">单位是交易窗口，例如 10 = 从分析日往后评估 10 根日线。</span>
          </label>
          <label className="product-field">
            <span className="theme-field-label">成熟期</span>
            <input
              type="number"
              className={GHOST_FIELD_CLASS}
              min={0}
              max={365}
              value={maturityDays}
              onChange={(event) => onMaturityDaysChange(event.target.value)}
              aria-label="成熟期"
            />
            <span className="product-field-help">单位是自然日，例如 14 = 仅评估 14 天前的分析记录。</span>
          </label>
        </div>
        <label className="product-checkbox-row">
          <input
            type="checkbox"
            className={GHOST_CHECKBOX_CLASS}
            checked={forceReplaceResults}
            onChange={(event) => onForceReplaceResultsChange(event.target.checked)}
            aria-label="覆盖已有同窗口结果"
          />
          <span>覆盖已有同窗口结果。这个开关只影响是否重算，不会改变窗口或成熟期定义。</span>
        </label>
        <div className="product-action-row backtest-control-actions backtest-control-actions--footer">
          <Button variant="ghost" onClick={() => setCurrentStep('scope')}>返回</Button>
          <Button onClick={() => setCurrentStep('execute')}>继续</Button>
        </div>
      </Card>
    </section>
  );

  const executeSection = (
    <section className="backtest-control-section" data-testid="historical-control-section-execute" data-active={currentStep === 'execute' ? 'true' : 'false'}>
      <Card title="执行评估" subtitle="步骤 3" className="product-section-card product-section-card--backtest-flow">
        {!isProfessionalMode ? (
          <p className="backtest-guided-step-helper">确认样本和参数后从这里执行历史评估，右侧显示板只负责展示结果。</p>
        ) : null}
        <p className="product-section-copy">用历史 AI 分析信号去验证后续价格窗口的表现，只做样本级评估，不做账户净值回测。</p>
        <Banner
          tone="warning"
          className="mt-4"
          title="这是历史信号验证，不是组合/账户回测。"
          body="只检查单条历史分析样本在未来窗口中的方向与收益表现，不生成资金曲线、持仓路径或净值回放。"
        />
        <div className="product-action-row backtest-control-actions backtest-control-actions--footer mt-4">
          <Button variant="ghost" onClick={() => setCurrentStep('params')}>返回</Button>
          <Button onClick={() => void handleRunEvaluationClick()} isLoading={isRunningHistoricalEval} loadingText="运行中…">
            运行历史评估
          </Button>
          <Button variant="ghost" onClick={() => void onClearResults()} disabled={isRunningHistoricalEval || !normalizedCode}>
            清理评估结果
          </Button>
        </div>
        {runError ? <ApiErrorAlert error={runError} className="mt-4" /> : null}
      </Card>
    </section>
  );

  const resultsSection = (
    <section className="backtest-control-section" data-testid="historical-control-section-results" data-active={currentStep === 'results' ? 'true' : 'false'}>
      <Card title="结果复查" subtitle="步骤 4" className="product-section-card product-section-card--backtest-standard">
        {!isProfessionalMode ? (
          <p className="backtest-guided-step-helper">这里保留结果复查和重跑入口，详细汇总、结果表和历史记录仍在右侧显示板。</p>
        ) : null}
        <div className="product-chip-list">
          <span className="product-chip">当前结果: {runResult?.runId ? `运行 #${runResult.runId}` : selectedRunId ? `历史 #${selectedRunId}` : '暂无'}</span>
          <span className="product-chip">结果数: {totalResults}</span>
          <span className="product-chip">历史运行: {historyTotal}</span>
        </div>
        <p className="product-footnote">右侧显示板会展示评估概览、结果表和历史记录。这个步骤只保留复查和重跑入口。</p>
        <div className="product-action-row backtest-control-actions backtest-control-actions--footer">
          <Button variant="ghost" onClick={() => setCurrentStep('execute')}>返回</Button>
          <Button onClick={() => void handleRunEvaluationClick()} isLoading={isRunningHistoricalEval} loadingText="运行中…">
            重新运行评估
          </Button>
        </div>
      </Card>
    </section>
  );

  const historicalSections: Record<HistoricalWizardStep, React.ReactNode> = {
    scope: scopeSamplesSection,
    params: paramsSection,
    execute: executeSection,
    results: resultsSection,
  };
  const inspectionTone = performanceNotice?.tone || sourceSummary.tone;
  const inspectionTitle = performanceNotice
    ? (performanceNotice.tone === 'danger' ? '当前结果存在阻断' : '当前结果需要复核')
    : sourceSummary.title;
  const inspectionBody = performanceNotice?.message || sourceSummary.body;
  const inspectionDetail = performanceNotice ? '请先处理数据完整性或执行状态，再继续判断样本表现。' : sourceSummary.detail;

  return (
    <div
      className="w-full min-w-0 flex flex-col gap-5"
      data-testid="backtest-unified-shell"
      data-module="historical"
      data-panel-mode={panelMode}
    >
      <div className="grid gap-3 min-w-0">
        <SectionEyebrow>Historical Evaluation</SectionEyebrow>
        <div className="grid gap-2 min-w-0">
          <h1 className="m-0 text-[clamp(1.5rem,1.1vw+1.2rem,2.2rem)] leading-tight text-[var(--text-primary)]">历史评估工作台</h1>
          <p className="m-0 text-sm leading-7 text-[var(--text-secondary)]">
            全宽工作台现在把样本控制、诊断说明和结果区彻底拆开。左侧专注操作，中间专注说明，右侧专注汇总与结果，
            不再把整块历史评估内容塞进 400px 的外层控制栏里。
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:gap-5 lg:grid-cols-12 items-start w-full min-w-0">
        <section
          className={`col-span-1 w-full min-w-0 flex flex-col gap-4 ${isProfessionalMode ? 'lg:col-span-12' : 'lg:col-span-3'}`}
          data-testid="backtest-control-panel"
          data-panel-mode={panelMode}
        >
          <div className="backtest-control-panel__header shrink-0">
            <SectionEyebrow>控制面板</SectionEyebrow>
            <h2 className="backtest-control-panel__title">历史评估</h2>
            <p className="backtest-control-panel__description">
              {isProfessionalMode
                ? '专业模式会展开全部历史评估控制区。'
                : '普通模式按步骤收口历史评估流程，先控制样本与参数，再执行并查看结果。'}
            </p>
          </div>

          {!isProfessionalMode ? (
            <nav className="backtest-control-stepper" aria-label="历史评估步骤">
              {[
                { key: 'scope', title: '范围与样本', short: '范围' },
                { key: 'params', title: '评估参数', short: '参数' },
                { key: 'execute', title: '执行评估', short: '执行' },
                { key: 'results', title: '结果复查', short: '结果' },
              ].map((step, index) => {
                const stepKey = step.key as HistoricalWizardStep;
                const stepOrder: HistoricalWizardStep[] = ['scope', 'params', 'execute', 'results'];
                const isDone = stepOrder.indexOf(stepKey) < stepOrder.indexOf(currentStep);
                return (
                  <button
                    key={step.key}
                    type="button"
                    className={`backtest-control-step${currentStep === stepKey ? ' is-active' : ''}${isDone ? ' is-done' : ''}`}
                    onClick={() => setCurrentStep(stepKey)}
                  >
                    <span className="backtest-control-step__index">{index + 1}</span>
                    <span className="backtest-control-step__copy">
                      <strong>{step.title}</strong>
                      <small>{step.short}</small>
                    </span>
                  </button>
                );
              })}
            </nav>
          ) : null}

          {isProfessionalMode ? (
            <div className="backtest-control-panel__stack backtest-control-panel__stack--professional" data-testid="backtest-control-panel-expanded">
              {scopeSamplesSection}
              {paramsSection}
              {executeSection}
              {resultsSection}
            </div>
          ) : (
            <div className="backtest-control-window" data-testid="backtest-control-window">
              <LazyMotion features={domAnimation}>
                <AnimatePresence mode="wait" initial={false}>
                  <m.div
                    key={currentStep}
                    className="backtest-control-window__frame"
                    initial={{ opacity: 0, x: 18 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -14 }}
                    transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
                  >
                    {historicalSections[currentStep]}
                  </m.div>
                </AnimatePresence>
              </LazyMotion>
            </div>
          )}
        </section>

        <section
          className={`col-span-1 w-full min-w-0 flex flex-col gap-4 bg-white/[0.02] border border-white/5 rounded-[24px] p-5 ${isProfessionalMode ? 'lg:col-span-5' : 'lg:col-span-4'}`}
          data-testid="historical-inspection-panel"
        >
          <div className="grid gap-3 min-w-0">
            <SectionEyebrow>Inspection</SectionEyebrow>
            <h2 className="m-0 text-[1.2rem] leading-tight text-[var(--text-primary)]">历史评估显示面板</h2>
            <p className="m-0 text-sm leading-7 text-[var(--text-secondary)]">
              这个中间栏只放说明、口径和假设，固定宽度后不再被右侧结果表和左侧控制区共同挤压。
            </p>
          </div>

          <Banner
            tone={inspectionTone}
            title={inspectionTitle}
            body={(
              <>
                {inspectionBody}
                <span className="product-banner__meta">{inspectionDetail}</span>
              </>
            )}
          />

          <SummaryStrip items={modeSummaryItems} />

          <Disclosure summary="查看数据可用性说明">
            <div className="preview-grid">
              <div className="preview-card">
                <p className="metric-card__label">请求方式</p>
                <p className="preview-card__text">{getHistoricalRequestedModeLabel(historicalSourceMetadata.requestedMode)}</p>
              </div>
              <div className="preview-card">
                <p className="metric-card__label">实际数据来源</p>
                <p className="preview-card__text">{getHistoricalResolvedSourceLabel(historicalSourceMetadata.resolvedSource)}</p>
              </div>
              <div className="preview-card">
                <p className="metric-card__label">备用数据状态</p>
                <p className="preview-card__text">{getHistoricalFallbackLabel(historicalSourceMetadata.fallbackUsed)}</p>
              </div>
            </div>
            <p className="product-footnote mt-4">{historicalSampleTransparency}</p>
          </Disclosure>

          <Disclosure summary="查看执行假设">
            <AssumptionList assumptions={historicalAssumptions || undefined} emptyText="暂无执行假设" />
          </Disclosure>
        </section>

        <section className={`col-span-1 w-full min-w-0 flex flex-col gap-4 ${isProfessionalMode ? 'lg:col-span-7' : 'lg:col-span-5'}`} data-testid="backtest-display-board">
          <div className="backtest-display-board__header shrink-0">
            <SectionEyebrow>显示面板</SectionEyebrow>
            <h2 className="backtest-display-board__title">结果与记录</h2>
            <p className="backtest-display-board__description">
              右侧吸收所有剩余宽度，承载汇总、结果表和历史记录，图表或大表格都只在这里伸展。
            </p>
          </div>

          <div className="backtest-display-board__stack flex flex-col min-w-0">
            <section className="backtest-display-section min-w-0" data-testid="historical-display-section-summary">
              <Card title="评估概览" subtitle="关键指标" className="product-section-card product-section-card--backtest-result">
                <p className="product-section-copy">这里只做历史信号验证，不展示账户权益曲线，也不表示完整策略盈亏回放。</p>
                {(isLoadingSampleStatus || isLoadingPerf)
                  ? <div className="product-empty-state product-empty-state--compact">正在汇总历史分析评估概览…</div>
                  : <SummaryStrip items={historicalSummaryItems} />}
                {sampleStatusError ? <ApiErrorAlert error={sampleStatusError} className="mt-4" /> : null}
                {runResult ? <HistoricalRunSummary data={runResult} /> : null}
              </Card>
            </section>

            <section className="backtest-display-section min-w-0" data-testid="historical-display-section-results">
              <Card
                title="评估结果"
                subtitle={selectedRunId ? `评估结果 #${selectedRunId}` : '结果表'}
                className="product-section-card product-section-card--backtest-result"
              >
                {pageError ? <ApiErrorAlert error={pageError} className="mb-4" /> : null}
                {isLoadingResults ? <div className="product-empty-state">正在加载历史分析评估结果…</div> : <HistoricalResultsTable rows={results} />}
                <Pagination
                  className="mt-5"
                  currentPage={currentPage}
                  totalPages={Math.max(1, Math.ceil(totalResults / pageSize))}
                  onPageChange={onChangeResultsPage}
                />
                <p className="product-footnote">共 {totalResults} 条历史分析评估结果。</p>
              </Card>
            </section>

            <section className="backtest-display-section min-w-0" data-testid="historical-display-section-history">
              <Card title="历史记录" subtitle="次级区域" className="product-section-card product-section-card--backtest-secondary">
                {historyError ? <ApiErrorAlert error={historyError} className="mb-4" /> : null}
                {isLoadingHistory ? (
                  <div className="product-empty-state">正在加载历史分析评估运行记录…</div>
                ) : (
                  <HistoricalRunsTable rows={historyItems} selectedRunId={selectedRunId} onOpen={(run) => void handleOpenHistoricalRun(run)} />
                )}
                <Pagination
                  className="mt-5"
                  currentPage={historyPage}
                  totalPages={Math.max(1, Math.ceil(historyTotal / historyPageSize))}
                  onPageChange={onChangeHistoryPage}
                />
                <p className="product-footnote">共 {historyTotal} 条历史分析评估运行记录。</p>
              </Card>
            </section>
          </div>
        </section>
      </div>
    </div>
  );
};

export default HistoricalEvaluationPanel;
