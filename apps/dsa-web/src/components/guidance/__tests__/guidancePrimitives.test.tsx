import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { DensityRail } from '../DensityRail';
import { GuidedDisclosure } from '../GuidedDisclosure';
import { InsightStack } from '../InsightStack';
import { SectionIntro } from '../SectionIntro';

describe('guidance primitives', () => {
  it('renders a SectionIntro with summary-first hierarchy and optional status', () => {
    render(
      <SectionIntro
        purpose="组合风险"
        summary="先看敞口是否集中，再决定是否进入明细。"
        nextStep="查看行业和货币分布。"
        status={{ label: '部分可用', tone: 'watch' }}
      />,
    );

    expect(screen.getByText('组合风险')).toBeInTheDocument();
    expect(screen.getByText('先看敞口是否集中，再决定是否进入明细。')).toBeInTheDocument();
    expect(screen.getByText('部分可用')).toBeInTheDocument();
    expect(screen.getByText(/查看行业和货币分布。/)).toBeInTheDocument();
  });

  it('renders at most four prioritized insights with severity labels', () => {
    render(
      <InsightStack
        insights={[
          { id: 'a', severity: 'critical', title: '先处理风险', explanation: '风险解释。' },
          { id: 'b', severity: 'warning', title: '等待确认', explanation: '确认解释。' },
          { id: 'c', severity: 'info', title: '补充信息', explanation: '信息解释。' },
          { id: 'd', severity: 'success', title: '条件满足', explanation: '就绪解释。' },
          { id: 'e', severity: 'info', title: '第五条', explanation: '不应默认显示。' },
        ]}
      />,
    );

    expect(screen.getByText('先处理风险')).toBeInTheDocument();
    expect(screen.getByText('重点风险')).toBeInTheDocument();
    expect(screen.getByText('需要观察')).toBeInTheDocument();
    expect(screen.getByText('已就绪')).toBeInTheDocument();
    expect(screen.queryByText('第五条')).not.toBeInTheDocument();
  });

  it('keeps GuidedDisclosure collapsed by default and toggles with native summary activation', () => {
    render(
      <GuidedDisclosure
        title="为什么折叠"
        summary="先保留结论，再打开证据。"
        beginner={<p>新手解释。</p>}
        professional={<p>专业证据。</p>}
      />,
    );

    const disclosure = screen.getByText('为什么折叠').closest('details');
    expect(disclosure).not.toHaveAttribute('open');
    expect(screen.getByText('新手解释。')).toBeInTheDocument();

    fireEvent.click(screen.getByText('为什么折叠'));

    expect(disclosure).toHaveAttribute('open');
    expect(screen.getByText('专业证据。')).toBeInTheDocument();
  });

  it('renders DensityRail as labelled secondary context without taking over the main story', () => {
    render(
      <DensityRail
        title="扫描上下文"
        items={[
          { id: 'market', label: '市场', value: '美股', helper: '仅用于解释候选范围。' },
          { id: 'freshness', label: '新鲜度', value: '等待快照', tone: 'caution' },
        ]}
      />,
    );

    const rail = screen.getByLabelText('扫描上下文');
    expect(rail.tagName.toLowerCase()).toBe('aside');
    expect(within(rail).getByText('市场')).toBeInTheDocument();
    expect(within(rail).getByText('等待快照')).toBeInTheDocument();
  });
});
