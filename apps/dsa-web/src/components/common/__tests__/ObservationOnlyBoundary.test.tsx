import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import ObservationOnlyBoundary from '../ObservationOnlyBoundary';

describe('ObservationOnlyBoundary', () => {
  it('renders compact English observation-only copy', () => {
    render(<ObservationOnlyBoundary language="en" />);

    const boundary = screen.getByTestId('observation-only-boundary');
    expect(boundary).toHaveTextContent('observation-only');
    expect(boundary).toHaveTextContent('evidence summary');
    expect(boundary).toHaveTextContent('not investment advice');
    expect(boundary).toHaveTextContent('not a buy/sell/hold recommendation');
    expect(boundary).toHaveTextContent('Verify data freshness and suitability independently.');
  });

  it('renders compact Chinese observation-only copy', () => {
    render(<ObservationOnlyBoundary language="zh" />);

    const boundary = screen.getByTestId('observation-only-boundary');
    expect(boundary).toHaveTextContent('observation-only');
    expect(boundary).toHaveTextContent('证据摘要');
    expect(boundary).toHaveTextContent('不构成交易建议');
    expect(boundary).toHaveTextContent('不提供买入、卖出、持有指令');
    expect(boundary).toHaveTextContent('请独立核验数据新鲜度与适用性。');
  });
});
