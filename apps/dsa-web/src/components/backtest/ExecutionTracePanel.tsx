import type React from 'react';
import { useState } from 'react';
import { Button, Card } from '../../components/common';
import type { RuleBacktestExecutionTraceRowItem, RuleBacktestRunResponse } from '../../types/backtest';
import { formatDeterministicActionLabel } from './normalizeDeterministicBacktestResult';
import {
  Banner,
  Disclosure,
  SummaryStrip,
  formatNumber,
  pct,
} from './shared';
import {
  downloadExecutionTraceCsv,
  downloadExecutionTraceJson,
  getExecutionTracePayload,
  getExecutionTraceRows,
  getExecutionTraceSourceLabel,
} from './executionTraceUtils';
import { useI18n } from '../../contexts/UiLanguageContext';

const TRACE_PREVIEW_LIMIT = 18;

type TraceViewMode = 'highlights' | 'all';

function getTraceExplanation(row: RuleBacktestExecutionTraceRowItem): string {
  const parts = [row.fallback, row.notes, row.unavailableReason]
    .map((value) => String(value || '').trim())
    .filter(Boolean);
  return parts.length > 0 ? parts.join('；') : '--';
}

function isHighlightTraceRow(row: RuleBacktestExecutionTraceRowItem): boolean {
  const action = String(row.action || row.eventType || '').trim().toLowerCase();
  return action !== '' && action !== 'hold'
    || getTraceExplanation(row) !== '--';
}

const ExecutionTracePanel: React.FC<{ run: RuleBacktestRunResponse }> = ({ run }) => {
  const { language } = useI18n();
  const [viewMode, setViewMode] = useState<TraceViewMode>('highlights');
  const trace = getExecutionTracePayload(run);
  const rows = getExecutionTraceRows(run);
  const highlightRows = rows.filter((row) => isHighlightTraceRow(row));
  const previewRows = (() => {
    const sourceRows = viewMode === 'highlights' ? highlightRows : rows;
    return [...sourceRows].reverse().slice(0, TRACE_PREVIEW_LIMIT);
  })();
  const fallbackNote = String(trace?.fallback?.note || '').trim();
  const assumptionsSummary = String(trace?.assumptionsDefaults?.summaryText || '').trim();
  const activeRowCount = viewMode === 'highlights' ? highlightRows.length : rows.length;

  return (
    <Card
      title={language === 'en' ? 'Execution trace' : '执行轨迹'}
      subtitle={language === 'en' ? 'Start with key checkpoints, then expand into the full trace when needed.' : '默认先看关键节点，完整轨迹按需展开'}
      className="product-section-card product-section-card--backtest-secondary"
    >
      <SummaryStrip
        items={[
          { label: language === 'en' ? 'Trace source' : '轨迹来源', value: getExecutionTraceSourceLabel(trace?.source) },
          { label: language === 'en' ? 'Total rows' : '轨迹总行数', value: String(rows.length) },
          { label: language === 'en' ? 'Key checkpoints' : '关键节点', value: String(highlightRows.length), note: language === 'en' ? 'Buys, sells, fallbacks, and exception notes' : '买卖动作 / 回退 / 异常说明' },
          {
            label: language === 'en' ? 'Fallback state' : '回退提示',
            value: trace?.fallback?.runFallback ? (language === 'en' ? 'Fallback used' : '存在回退') : trace?.fallback?.traceRebuilt ? (language === 'en' ? 'Trace rebuilt' : '已回补') : (language === 'en' ? 'Standard path' : '标准路径'),
            note: fallbackNote || (language === 'en' ? 'No extra note' : '无额外说明'),
          },
        ]}
      />

      {fallbackNote ? (
        <Banner
          tone={trace?.fallback?.runFallback ? 'warning' : 'info'}
          className="mt-4"
          title={language === 'en' ? 'Trace diagnostics' : '轨迹诊断'}
          body={fallbackNote}
        />
      ) : null}

      <div className="summary-block mt-4">
        <div className="summary-block__header">
          <div>
            <h3 className="summary-block__title">{language === 'en' ? 'Key checkpoint preview' : '关键节点预览'}</h3>
            <p className="product-section-copy">{language === 'en' ? 'The panel shows only recent checkpoints by default so the first screen is not flooded by daily hold rows. You can still switch to and export the full trace.' : '默认只显示最近的关键节点，避免首屏被逐日持有记录淹没；完整轨迹仍可切换和导出。'}</p>
          </div>
          <div className="product-action-row">
            <Button variant="secondary" onClick={() => downloadExecutionTraceCsv(run)} disabled={rows.length === 0}>
              {language === 'en' ? 'Export CSV' : '导出 CSV'}
            </Button>
            <Button variant="ghost" onClick={() => downloadExecutionTraceJson(run)} disabled={rows.length === 0}>
              {language === 'en' ? 'Export JSON' : '导出 JSON'}
            </Button>
          </div>
        </div>

        <div className="backtest-mode-toggle mt-4" role="tablist" aria-label={language === 'en' ? 'Execution trace view' : '执行轨迹视图'}>
          <button
            type="button"
            role="tab"
            aria-selected={viewMode === 'highlights'}
            className={`backtest-mode-toggle__button !min-h-[36px] md:!min-h-[32px]${viewMode === 'highlights' ? ' is-active' : ''}`}
            onClick={() => setViewMode('highlights')}
          >
            {language === 'en' ? 'Key checkpoints' : '关键节点'}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={viewMode === 'all'}
            className={`backtest-mode-toggle__button !min-h-[36px] md:!min-h-[32px]${viewMode === 'all' ? ' is-active' : ''}`}
            onClick={() => setViewMode('all')}
          >
            {language === 'en' ? 'Full trace' : '全部轨迹'}
          </button>
        </div>

        {previewRows.length === 0 ? (
          <div className="product-empty-state product-empty-state--compact mt-4">{language === 'en' ? 'No execution trace is available to display yet.' : '暂无可展示的执行轨迹。'}</div>
        ) : (
          <>
            <div className="product-table-shell mt-4">
              <table className="product-table">
                <thead>
                  <tr>
                    <th>{language === 'en' ? 'Date' : '日期'}</th>
                    <th>{language === 'en' ? 'Action' : '动作'}</th>
                    <th>{language === 'en' ? 'Signal / note' : '信号 / 说明'}</th>
                    <th className="product-table__align-right">{language === 'en' ? 'Strategy cumulative' : '策略累计'}</th>
                    <th className="product-table__align-right">{language === 'en' ? 'Total equity' : '总资产'}</th>
                    <th>{language === 'en' ? 'Remark' : '备注'}</th>
                  </tr>
                </thead>
                <tbody>
                  {previewRows.map((row, index) => (
                    <tr key={`${row.date || 'trace'}-${row.action || row.eventType || 'hold'}-${index}`}>
                      <td>{row.date || '--'}</td>
                      <td>
                        <div className="product-table__stack">
                          <span>{formatDeterministicActionLabel(row.action || row.eventType, language)}</span>
                          <span>{row.fillPrice != null ? (language === 'en' ? `Filled ${formatNumber(row.fillPrice)}` : `成交 ${formatNumber(row.fillPrice)}`) : (language === 'en' ? 'No fill price' : '无成交价')}</span>
                        </div>
                      </td>
                      <td>{row.signalSummary || '--'}</td>
                      <td className="product-table__align-right">{pct(row.cumulativeReturn)}</td>
                      <td className="product-table__align-right">{formatNumber(row.totalPortfolioValue)}</td>
                      <td>{getTraceExplanation(row)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="product-footnote mt-4">
              {language === 'en'
                ? `Showing ${previewRows.length} / ${activeRowCount} ${viewMode === 'highlights' ? 'checkpoint' : 'trace'} rows. Exports still include the complete dataset.`
                : `当前显示 ${previewRows.length} / ${activeRowCount} 行${viewMode === 'highlights' ? '关键节点' : '轨迹'}。导出会包含完整数据。`}
            </p>
          </>
        )}
      </div>

      {(assumptionsSummary || trace?.executionAssumptions || trace?.executionModel) ? (
        <Disclosure summary={language === 'en' ? 'View advanced execution-trace notes' : '查看执行轨迹高级说明'}>
          <div className="backtest-result-page__tab-stack">
            {assumptionsSummary ? <p className="product-section-copy">{assumptionsSummary}</p> : null}
            <div className="preview-grid">
              <div className="preview-card">
                <p className="metric-card__label">{language === 'en' ? 'Trace source' : '轨迹来源'}</p>
                <p className="preview-card__text">{getExecutionTraceSourceLabel(trace?.source)}</p>
              </div>
              <div className="preview-card">
                <p className="metric-card__label">{language === 'en' ? 'Fallback marker' : '回退标记'}</p>
                <p className="preview-card__text">{fallbackNote || (language === 'en' ? 'Standard execution path' : '标准执行路径')}</p>
              </div>
            </div>
          </div>
        </Disclosure>
      ) : null}
    </Card>
  );
};

export default ExecutionTracePanel;
