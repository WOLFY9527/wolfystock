import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import ConsumerEvidenceCoverageStrip from '../ConsumerEvidenceCoverageStrip';
import ConsumerEvidencePacketStrip from '../ConsumerEvidencePacketStrip';
import { OfficialMacroAuthorityDiagnostics } from '../OfficialMacroAuthorityDiagnostics';
import PeerCorrelationSnapshotBlock from '../PeerCorrelationSnapshotBlock';
import { SynthesisEvidenceColumn } from '../SynthesisEvidenceColumn';
import { buildOfficialMacroAuthorityDiagnosticsView } from '../officialMacroAuthorityDiagnosticsData';

describe('shared visual foundation surfaces', () => {
  it('renders consumer evidence packet with light-surface foreground ownership', () => {
    render(
      <ConsumerEvidencePacketStrip
        testId="packet"
        packet={{
          packetState: 'degraded',
          priceHistory: { status: 'available' },
          technicals: { status: 'available' },
          fundamentals: { status: 'degraded' },
          earnings: { status: 'missing' },
          news: { status: 'pending' },
          catalysts: { status: 'pending' },
          valuation: { status: 'blocked' },
          fundamentalsEarnings: {
            normalizerState: 'degraded',
            missingEvidence: ['missing fundamentals'],
          },
          newsCatalysts: {
            extractionState: 'pending',
          },
        }}
      />,
    );

    const packet = screen.getByTestId('packet');
    expect(packet).toHaveClass('research-evidence-surface');
    expect(packet.className).not.toMatch(/text-white|bg-black|bg-white|border-white/);
    expect(screen.getByText('证据包摘要')).toHaveClass('research-evidence-eyebrow');
    expect(screen.getByText(/仅供观察/)).toHaveClass('research-evidence-muted');
  });

  it('keeps unavailable evidence coverage visually distinct from success', () => {
    render(<ConsumerEvidenceCoverageStrip testId="coverage" frame={null} />);

    const coverage = screen.getByTestId('coverage');
    expect(coverage).toHaveClass('research-evidence-surface');
    expect(screen.getByText('覆盖不可用')).toHaveClass('text-[color:var(--wolfy-market-down)]');
    expect(screen.getByText(/当前结论不能视为研究就绪/)).toHaveClass('research-evidence-copy');
  });

  it('uses shared evidence surfaces for macro diagnostics rows', () => {
    const view = buildOfficialMacroAuthorityDiagnosticsView([
      {
        key: 'vix',
        label: 'VIX',
        sourceAuthorityAllowed: true,
        scoreContributionAllowed: true,
        officialSeriesId: 'VIXCLS',
        sourceLabel: 'FRED',
        freshness: 'fresh',
      },
    ]);

    render(
      <OfficialMacroAuthorityDiagnostics
        testId="macro-diagnostics"
        title="宏观来源覆盖"
        view={view}
      />,
    );

    expect(screen.getByTestId('macro-diagnostics')).toHaveClass('bg-[var(--wolfy-surface-muted)]');
    fireEvent.click(screen.getByRole('button', { name: /展开 宏观来源覆盖/ }));
    const rowSeriesLabel = screen.getAllByText('VIXCLS')
      .find((element) => element.classList.contains('research-evidence-eyebrow'));
    expect(rowSeriesLabel?.closest('.research-evidence-surface')).not.toBeNull();
    expect(rowSeriesLabel).toHaveClass('research-evidence-eyebrow');
  });

  it('uses token-owned nested evidence surfaces for synthesis and peer blocks', () => {
    render(
      <>
        <SynthesisEvidenceColumn
          testId="synthesis"
          title="证据摘要"
          emptyLabel="暂无证据"
          items={[{ key: 'a', label: '覆盖有限', meta: '等待补证' }]}
        />
        <PeerCorrelationSnapshotBlock
          testId="peer"
          locale="zh"
          snapshot={{
            symbol: 'AAPL',
            correlationState: 'insufficient_evidence',
            confidenceCap: 'low',
            peerGroup: { status: 'available', label: '同业篮子', symbols: ['AAA'] },
            peerEvidence: [{
              symbol: 'AAA',
              state: 'insufficient_evidence',
              overlapDays: 12,
              summary: 'peer behavior remains bounded by current evidence',
            }],
            divergenceEvidence: [],
            staleInputs: [],
            missingInputs: [],
            researchNextSteps: ['补齐同业数据'],
            observationBoundary: '仅供同业观察。',
          }}
        />
      </>,
    );

    expect(screen.getByTestId('synthesis')).toHaveClass('research-evidence-surface');
    expect(screen.getByText('证据摘要')).toHaveClass('research-evidence-eyebrow');
    expect(screen.getByTestId('peer')).toHaveClass('research-evidence-surface');
    expect(screen.getByText('同业证据').closest('.research-evidence-surface--nested')).not.toBeNull();
  });
});
