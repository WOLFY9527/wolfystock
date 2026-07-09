import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import AdminOpsL0OverviewStrip from '../AdminOpsL0OverviewStrip';

describe('AdminOpsL0OverviewStrip', () => {
  it('renders a compact operator status line with all five fields without equal-weight tiles', () => {
    render(
      <AdminOpsL0OverviewStrip
        dataTestId="admin-ops-l0-overview-strip"
        systemTrustState="blocked"
        impact="Providers and access controls need review"
        recommendedAction="Open the highest-severity queue first"
        evidenceRef="ops_snapshot_v1"
        lastUpdated="2026-07-09T12:00:00Z"
      />,
    );

    const strip = screen.getByTestId('admin-ops-l0-overview-strip');
    expect(within(strip).getByText('L0 总览')).toBeInTheDocument();
    expect(within(strip).getByText('信任状态')).toBeInTheDocument();
    expect(within(strip).getByText('影响范围')).toBeInTheDocument();
    expect(within(strip).getByText('建议动作')).toBeInTheDocument();
    expect(within(strip).getByText('证据参考')).toBeInTheDocument();
    expect(within(strip).getByText('最近更新')).toBeInTheDocument();
    expect(within(strip).getByText('阻断')).toBeInTheDocument();
    expect(within(strip).getByText('Providers and access controls need review')).toBeInTheDocument();
    expect(within(strip).getByText('Open the highest-severity queue first')).toBeInTheDocument();
    expect(within(strip).getByText('ops_snapshot_v1')).toBeInTheDocument();
    // Compact status line: no five equal-weight field tiles
    expect(strip.querySelectorAll('.xl\\:grid-cols-5').length).toBe(0);
  });

  it('uses English field labels when language is en', () => {
    render(
      <AdminOpsL0OverviewStrip
        language="en"
        systemTrustState="review_required"
        impact="Impact"
        recommendedAction="Action"
        evidenceRef="ref"
        lastUpdated="now"
      />,
    );

    expect(screen.getByText('L0 Overview')).toBeInTheDocument();
    expect(screen.getByText('Trust state')).toBeInTheDocument();
    expect(screen.getByText('Review required')).toBeInTheDocument();
  });
});
