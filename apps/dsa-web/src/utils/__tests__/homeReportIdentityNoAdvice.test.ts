import { describe, expect, it } from 'vitest';
import type { AnalysisReport } from '../../types/analysis';
import { buildInstitutionalReportMarkdown, consumerSafeReportText } from '../homeReportIdentity';

const forbiddenConsumerReportPattern =
  /小仓试错|第二笔|25%-35%|强行交易|投资结论|买入|卖出|理想买点|次级买点|止损|止盈|目标价|目标位|目标区间|仓位建议|仓位|\bAction\b|Ideal buy|Secondary entry|Stop loss|Take profit|Target 1|Target 2|Target zone|Position sizing|battle plan|sniper|holding advice|empty-position advice|reasonCode|sourceRefId|raw_result|raw_ai_response|context_snapshot|raw_result_marker|raw_ai_response_marker|context_snapshot_marker|provider_timeout|fallback_cache|Yahoo Finance|Finnhub|backend snake_case/i;

function buildUnsafeReportFixture(): AnalysisReport {
  return {
    meta: {
      queryId: 't1162',
      stockCode: 'ORCL',
      stockName: 'Oracle',
      companyName: 'Oracle',
      reportType: 'full',
      createdAt: '2026-06-07T08:00:00Z',
      reportGeneratedAt: '2026-06-07T08:01:00Z',
    },
    summary: {
      analysisSummary: '建议买入，目标价看 133.50。',
      operationAdvice: '买入',
      trendPrediction: '上行后卖出',
      sentimentScore: 74,
      sentimentLabel: 'Bullish',
    },
    strategy: {
      idealBuy: '121.80 - 124.60（理想买点）',
      secondaryBuy: '119.50（次级买点）',
      stopLoss: '117.40（止损）',
      takeProfit: '133.50（目标价）',
    },
    details: {
      rawResult: {
        raw_result_marker: 'raw_result_marker must not export',
        dashboard: {
          data_perspective: {
            alpha_vantage: {
              backend_snake_case: 'backend snake_case must not export',
            },
          },
        },
        items: [
          {
            stockEvidencePacket: {
              notInvestmentAdvice: true,
              confidenceCap: {
                value: 40,
                reasonCodes: ['provider_timeout'],
              },
              dataGaps: [
                {
                  evidenceClass: 'news',
                  reasonCode: 'provider_timeout',
                  detail: 'backend snake_case diagnostic',
                },
              ],
              sourceRefs: [
                {
                  sourceRefId: 'quote:fallback_cache',
                  provider: 'Yahoo Finance',
                  status: 'fallback',
                },
              ],
              claimBoundaries: [
                {
                  claim: 'direct_trade_action',
                  allowed: false,
                  reasonCode: 'not_investment_advice',
                },
              ],
              rawPayload: 'raw_ai_response_marker',
            },
          },
        ],
      },
      rawAiResponse: 'raw_ai_response_marker',
      contextSnapshot: { context_snapshot_marker: true },
      standardReport: {
        summaryPanel: {
          stock: 'Oracle',
          ticker: 'ORCL',
          score: 74,
          operationAdvice: '买入',
          trendPrediction: '卖出',
          oneSentence: '目标价 133.50，建议买入。',
        },
        decisionPanel: {
          confidence: '中',
          marketStructure: '短线',
          idealEntry: '121.80 - 124.60（理想买点）',
          backupEntry: '119.50（次级买点）',
          stopLoss: '117.40（止损）',
          target: '133.50（目标价）',
          positionSizing: '仓位建议 20%',
          buildStrategy: '小仓试错，第二笔在确认后加仓。',
          riskControlStrategy: '25%-35% 仓位，跌破后止损，避免强行交易。',
          noPositionAdvice: '空仓建议等待理想买点。',
          holderAdvice: '持仓建议继续加仓。',
          executionReminders: ['不要强行交易，也不要把 provider_timeout 暴露给消费者。'],
        },
        reasonLayer: {
          coreReasons: ['价格仍需继续跟踪。'],
          topRisk: '止损线 117.40。',
        },
        technicalFields: [
          { label: '理想买点', value: '121.80 - 124.60' },
          { label: 'MACD', value: '二次扩张' },
        ],
        battleFields: [
          { label: '止损', value: '117.40（止损）' },
          { label: '目标价', value: '133.50（目标价）' },
        ],
        battlePlanCompact: {
          cards: [
            { label: '仓位建议', value: '20%' },
          ],
          notes: [
            { label: 'entry', value: 'battle plan sniper entry: 买入后持有。' },
          ],
        },
        coverageNotes: {
          dataSources: ['Yahoo Finance provider detail'],
          coverageGaps: ['provider_timeout'],
          conflictNotes: ['reasonCode=provider_timeout'],
          methodNotes: ['raw_result_marker'],
        },
        checklistItems: [
          { status: 'pass', icon: 'ok', text: '买入动作已确认' },
        ],
      },
    },
    decisionTrace: {
      symbol: 'ORCL',
      market: 'US',
      dataSources: [
        { name: 'quote', status: 'fallback', provider: 'Finnhub' },
      ],
    },
    dataQualityReport: {
      confidenceCap: 40,
      reasonCodes: ['provider_timeout'],
    },
  };
}

describe('buildInstitutionalReportMarkdown no-advice guard', () => {
  it('projects isolated legacy full-report action phrases to observation copy', () => {
    const projected = consumerSafeReportText('小仓试错，第二笔 25%-35%，避免强行交易。');

    expect(projected).toBe('当前研究包仍不完整，仅支持继续跟踪。');
    expect(projected).not.toMatch(forbiddenConsumerReportPattern);
  });

  it('maps action report fields to observation language and suppresses raw fields', () => {
    const markdown = buildInstitutionalReportMarkdown(buildUnsafeReportFixture());

    expect(markdown).toContain('研究包完整度');
    expect(markdown).toContain('继续跟踪');
    expect(markdown).toContain('数据不足');
    expect(markdown).toContain('参考区间');
    expect(markdown).toContain('上方观察区');
    expect(markdown).toContain('风险边界');
    expect(markdown).toContain('关键价格区间');
    expect(markdown).toContain('121.80 - 124.60');
    expect(markdown).toContain('117.40');
    expect(markdown).toContain('133.50');
    expect(markdown).not.toMatch(forbiddenConsumerReportPattern);
  });
});
