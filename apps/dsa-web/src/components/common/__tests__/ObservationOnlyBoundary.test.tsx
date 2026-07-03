import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import ObservationOnlyBoundary from '../ObservationOnlyBoundary';

describe('ObservationOnlyBoundary', () => {
  it('renders compact English research-boundary copy', () => {
    render(<ObservationOnlyBoundary language="en" />);

    const boundary = screen.getByTestId('observation-only-boundary');
    expect(boundary).toHaveTextContent('Research boundary summary');
    expect(boundary).toHaveTextContent('bounded model or rule outputs');
    expect(boundary).toHaveTextContent('verify suitability independently');
    expect(boundary.textContent || '').not.toMatch(/observation-only|buy\/sell\/hold|recommendation/i);
  });

  it('renders compact Chinese research-boundary copy', () => {
    render(<ObservationOnlyBoundary language="zh" />);

    const boundary = screen.getByTestId('observation-only-boundary');
    expect(boundary).toHaveTextContent('研究边界摘要');
    expect(boundary).toHaveTextContent('受边界约束的模型或规则输出');
    expect(boundary).toHaveTextContent('请独立核验适用性');
    expect(boundary.textContent || '').not.toMatch(/observation-only|交易建议|买入|卖出|持有/);
  });
});
