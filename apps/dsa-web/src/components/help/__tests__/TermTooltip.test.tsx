import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { GlossaryTerm } from '../GlossaryTerm';
import { HelpHint } from '../HelpHint';
import { TermTooltip } from '../TermTooltip';

describe('TermTooltip', () => {
  it('opens on hover and exposes an accessible tooltip relationship', () => {
    render(
      <TermTooltip
        label="波动率"
        explanation="价格上下波动的幅度，常用于理解不确定性。"
        professionalNote="通常以收益率标准差或隐含波动率表达。"
        caveat="只能描述波动，不代表方向。"
      />,
    );

    const trigger = screen.getByRole('button', { name: '波动率 术语说明' });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();

    fireEvent.mouseEnter(trigger);

    const tooltip = screen.getByRole('tooltip');
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    expect(trigger).toHaveAttribute('aria-describedby', tooltip.id);
    expect(tooltip).toHaveTextContent('价格上下波动的幅度');
    expect(tooltip).toHaveTextContent('专业口径');
    expect(tooltip).toHaveTextContent('使用边界');
  });

  it('opens on focus, closes on Escape, and stays keyboard reachable', () => {
    render(<GlossaryTerm termId="max-drawdown" />);

    const trigger = screen.getByRole('button', { name: '最大回撤 术语说明' });
    trigger.focus();
    fireEvent.focus(trigger);
    expect(screen.getByRole('tooltip')).toHaveTextContent('从阶段高点到低点的最大跌幅');

    fireEvent.keyDown(trigger, { key: 'Escape' });
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it('toggles on click for touch/mobile style usage', () => {
    render(
      <TermTooltip
        label="SLA"
        explanation="服务承诺的可用性或响应目标。"
        professionalNote="常用于衡量系统稳定性和故障恢复要求。"
      />,
    );

    const trigger = screen.getByRole('button', { name: 'SLA 术语说明' });
    fireEvent.click(trigger);
    expect(screen.getByRole('tooltip')).toHaveTextContent('服务承诺');

    fireEvent.click(trigger);
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });

  it('renders a compact icon hint with a non-native tooltip', () => {
    render(
      <HelpHint
        label="数据可信度"
        explanation="数据是否足够新、完整、来源清晰。"
        professionalNote="用于区分可解释的降级状态和不可用数据。"
      />,
    );

    const trigger = screen.getByRole('button', { name: '数据可信度 术语说明' });
    expect(trigger).not.toHaveAttribute('title');

    fireEvent.focus(trigger);
    expect(screen.getByRole('tooltip')).toHaveTextContent('数据是否足够新');
  });
});
