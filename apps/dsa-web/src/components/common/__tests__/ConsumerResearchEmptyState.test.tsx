import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ConsumerResearchEmptyState } from '../ConsumerResearchEmptyState';
import {
  CONSUMER_RESEARCH_EMPTY_STATE_CASES,
  buildConsumerResearchEmptyState,
} from '../researchEmptyStateModel';
import { findConsumerRawLeakage } from '../../../test-utils/consumerRawLeakageGuard';

const forbiddenAdvicePattern = /买入|卖出|持有|推荐|目标价|止损|仓位建议|\b(?:buy|sell|hold|recommend(?:ed|ation)?|target price|stop loss|position sizing)\b/i;
const forbiddenIdentifierPattern = /request[_\s-]?id|trace[_\s-]?id|correlation[_\s-]?id|\breq-[a-z0-9-]{6,}\b|\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b/i;

describe('ConsumerResearchEmptyState', () => {
  it('covers the expected research empty-state cases with calm observation-only copy', () => {
    expect(CONSUMER_RESEARCH_EMPTY_STATE_CASES).toEqual([
      'insufficientEvidence',
      'staleEvidence',
      'unavailableData',
      'missingResearchPacket',
      'noQueueItems',
      'partialCoverage',
      'loading',
    ]);

    const expected = {
      insufficientEvidence: {
        title: '证据暂不足',
        severity: 'limited',
        hasStep: true,
      },
      staleEvidence: {
        title: '证据时效有限',
        severity: 'limited',
        hasStep: true,
      },
      unavailableData: {
        title: '数据暂不可用',
        severity: 'unavailable',
        hasStep: true,
      },
      missingResearchPacket: {
        title: '研究包未就绪',
        severity: 'unavailable',
        hasStep: true,
      },
      noQueueItems: {
        title: '暂无研究队列',
        severity: 'neutral',
        hasStep: true,
      },
      partialCoverage: {
        title: '覆盖仍不完整',
        severity: 'limited',
        hasStep: true,
      },
      loading: {
        title: '正在整理研究资料',
        severity: 'neutral',
        hasStep: false,
      },
    } as const;

    for (const emptyCase of CONSUMER_RESEARCH_EMPTY_STATE_CASES) {
      const state = buildConsumerResearchEmptyState(emptyCase, 'zh');
      expect(state).toMatchObject({
        title: expected[emptyCase].title,
        severity: expected[emptyCase].severity,
        observationOnly: true,
      });
      expect(Boolean(state.nextResearchStep)).toBe(expected[emptyCase].hasStep);

      const visibleCopy = [state.title, state.body, state.nextResearchStep].filter(Boolean).join(' ');
      expect(visibleCopy).not.toMatch(forbiddenAdvicePattern);
      expect(visibleCopy).not.toMatch(forbiddenIdentifierPattern);
      expect(findConsumerRawLeakage(visibleCopy)).toEqual([]);
    }
  });

  it('renders the display model without exposing raw diagnostics or the observationOnly field name', () => {
    render(
      <ConsumerResearchEmptyState
        state={buildConsumerResearchEmptyState('partialCoverage', 'en')}
        data-testid="consumer-research-empty-state"
      />,
    );

    const emptyState = screen.getByTestId('consumer-research-empty-state');
    expect(emptyState).toHaveAttribute('data-severity', 'limited');
    expect(emptyState).toHaveTextContent('Coverage is still partial');
    expect(emptyState).toHaveTextContent('Review the visible gaps before reading the research context.');
    expect(emptyState).toHaveTextContent('Start with the evidence area that has the widest gap.');

    const visibleText = emptyState.textContent || '';
    expect(visibleText).not.toMatch(/observationOnly|provider|cache|runtime|debug|trace|request id|trace id|schema|raw|fallback/i);
    expect(visibleText).not.toMatch(forbiddenAdvicePattern);
    expect(visibleText).not.toMatch(forbiddenIdentifierPattern);
    expect(findConsumerRawLeakage(visibleText)).toEqual([]);
  });

  it('keeps loading guidance distinct from failure copy', () => {
    render(
      <ConsumerResearchEmptyState
        state={buildConsumerResearchEmptyState('loading', 'zh')}
        data-testid="consumer-research-loading-state"
      />,
    );

    const emptyState = screen.getByTestId('consumer-research-loading-state');
    expect(emptyState).toHaveAttribute('data-severity', 'neutral');
    expect(emptyState).toHaveTextContent('正在整理研究资料');
    expect(emptyState).toHaveTextContent('页面仍在加载研究资料，请等待当前更新完成。');
    expect(emptyState).not.toHaveTextContent('下一步研究');
    expect(emptyState).not.toHaveTextContent(/失败|错误|不可用/);
  });
});
