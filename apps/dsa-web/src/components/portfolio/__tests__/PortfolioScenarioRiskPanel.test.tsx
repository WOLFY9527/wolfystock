import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { UiLanguageProvider } from '../../../contexts/UiLanguageContext';
import { PortfolioScenarioRiskPanel } from '../PortfolioScenarioRiskPanel';

const positions = [
  {
    symbol: 'AAPL',
    marketValue: 1600,
    marketValueBase: 1600,
    currency: 'USD',
    bucketLabel: 'Main',
  },
  {
    symbol: 'BABA',
    marketValue: 400,
    marketValueBase: 400,
    currency: 'HKD',
    bucketLabel: 'Main',
  },
];

function renderPanel(runScenario = vi.fn()) {
  return render(
    <UiLanguageProvider>
      <PortfolioScenarioRiskPanel
        snapshotAsOf="2026-03-19"
        positions={positions}
        onRunScenario={runScenario}
      />
    </UiLanguageProvider>,
  );
}

describe('PortfolioScenarioRiskPanel', () => {
  it('shows inline validation for missing shock percent and does not run the API', async () => {
    const runScenario = vi.fn();
    renderPanel(runScenario);

    const disclosure = screen.getByTestId('portfolio-scenario-risk-disclosure');
    fireEvent.click(within(disclosure).getByRole('button', { name: '展开 查看压力情景' }));
    fireEvent.change(screen.getByLabelText('冲击幅度（%）'), { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: '运行压力情景' }));

    expect(await screen.findByText('请填写有效的冲击幅度')).toBeInTheDocument();
    expect(runScenario).not.toHaveBeenCalled();
  });

  it('renders impact, coverage, consumer-safe warnings, and advisory-only metadata from the scenario response', async () => {
    const runScenario = vi.fn().mockResolvedValue({
      readModelType: 'portfolio_scenario_risk_advisory_v1',
      advisoryOnly: true,
      executionReadiness: 'advisory_only_not_trade_execution',
      asOf: '2026-03-19T00:00:00Z',
      coverage: {
        totalPositions: 2,
        positionsWithUsableWeight: 2,
        positionsWithMarketValue: 2,
        effectiveWeightSum: 1,
        totalMarketValue: 2000,
        explicitExposureRows: 1,
        labelsWithExplicitCoverage: ['QQQ'],
      },
      scenarios: [
        {
          name: 'index_proxy_qqq_down_-6',
          portfolioImpactPct: -3.2,
          portfolioImpactAmount: -64,
          coveredWeight: 0.8,
          coveredMarketValue: 1600,
          warnings: ['coverage_partial', 'missing_scenario_coverage'],
          missingCoverage: [
            {
              label: 'QQQ',
              labelType: 'index_proxy',
              missingSymbols: ['BABA'],
            },
          ],
          positionContributions: [
            {
              symbol: 'AAPL',
              bucket: 'Main',
              weight: 0.8,
              marketValue: 1600,
              impactPct: -3.2,
              impactAmount: -64,
              contributionToScenarioLoss: 1,
              warnings: [],
              appliedShocks: [
                {
                  label: 'QQQ',
                  labelType: 'index_proxy',
                  shockPct: -6,
                  exposure: 1,
                  impactPct: -3.2,
                  impactAmount: -64,
                },
              ],
            },
          ],
          bucketContributions: [
            {
              bucket: 'Main',
              positionCount: 1,
              impactPct: -3.2,
              impactAmount: -64,
              contributionToScenarioLoss: 1,
            },
          ],
        },
      ],
      insufficientDataReasons: ['theme_mapping_pending', 'no_usable_scenario_shocks'],
      missingDataWarnings: ['scenario_coverage_incomplete', 'backend_debug_warning_token'],
      metadata: {
        sideEffectFree: true,
        noBrokerSync: true,
        noAccountingMutation: true,
        noOrderPlacement: true,
        notInvestmentAdvice: true,
      },
    });

    renderPanel(runScenario);

    const disclosure = screen.getByTestId('portfolio-scenario-risk-disclosure');
    fireEvent.click(within(disclosure).getByRole('button', { name: '展开 查看压力情景' }));
    fireEvent.change(screen.getByLabelText('情景类型'), { target: { value: 'index_proxy' } });
    fireEvent.change(screen.getByLabelText('映射标签'), { target: { value: 'QQQ' } });
    fireEvent.change(screen.getByLabelText('冲击幅度（%）'), { target: { value: '-6' } });
    fireEvent.click(screen.getByRole('button', { name: '运行压力情景' }));

    await waitFor(() => expect(runScenario).toHaveBeenCalledTimes(1));

    expect(runScenario).toHaveBeenCalledWith({
      asOf: '2026-03-19',
      positions: [
        {
          symbol: 'AAPL',
          weightPct: 80,
          marketValue: 1600,
          marketValueBase: 1600,
          bucketLabel: 'Main',
          currency: 'USD',
        },
        {
          symbol: 'BABA',
          weightPct: 20,
          marketValue: 400,
          marketValueBase: 400,
          bucketLabel: 'Main',
          currency: 'HKD',
        },
      ],
      exposures: [
        {
          symbol: 'AAPL',
          label: 'QQQ',
          labelType: 'index_proxy',
          exposure: 1,
        },
      ],
      scenarioShocks: [
        {
          name: 'index_proxy_qqq_down_-6',
          shocks: {
            QQQ: {
              shockPct: -6,
              labelType: 'index_proxy',
            },
          },
        },
      ],
    });

    expect(screen.getByTestId('portfolio-scenario-risk-result')).toHaveTextContent('预估影响');
    expect(screen.getByTestId('portfolio-scenario-risk-result')).toHaveTextContent('-3.2%');
    expect(screen.getByTestId('portfolio-scenario-risk-result')).toHaveTextContent('-64.00');
    expect(screen.getByTestId('portfolio-scenario-risk-result')).toHaveTextContent('覆盖情况');
    expect(screen.getByTestId('portfolio-scenario-risk-result')).toHaveTextContent('显式映射');
    expect(screen.getByTestId('portfolio-scenario-risk-result')).toHaveTextContent('1 行');
    expect(screen.getByTestId('portfolio-scenario-risk-result')).toHaveTextContent('情景风险仅供观察');
    expect(screen.getByTestId('portfolio-scenario-risk-result')).toHaveTextContent('风险读数受限');
    expect(screen.getByTestId('portfolio-scenario-risk-result')).toHaveTextContent('部分输入缺失');
    expect(screen.getByTestId('portfolio-scenario-risk-result')).toHaveTextContent('数据更新中 / 数据不足');
    expect(screen.getByTestId('portfolio-scenario-risk-result')).toHaveTextContent('数据不足 / 需补充映射');
    expect(screen.getByTestId('portfolio-scenario-risk-result')).toHaveTextContent('BABA');
    expect(screen.getByTestId('portfolio-scenario-risk-result')).not.toHaveTextContent('portfolio_scenario_risk_advisory_v1');
    expect(screen.getByTestId('portfolio-scenario-risk-result')).not.toHaveTextContent('advisory_only_not_trade_execution');
    expect(screen.getByTestId('portfolio-scenario-risk-result')).not.toHaveTextContent('coverage_partial');
    expect(screen.getByTestId('portfolio-scenario-risk-result')).not.toHaveTextContent('missing_scenario_coverage');
    expect(screen.getByTestId('portfolio-scenario-risk-result')).not.toHaveTextContent('theme_mapping_pending');
    expect(screen.getByTestId('portfolio-scenario-risk-result')).not.toHaveTextContent('scenario_coverage_incomplete');
    expect(screen.getByTestId('portfolio-scenario-risk-result')).not.toHaveTextContent('backend_debug_warning_token');
    expect(screen.getByTestId('portfolio-scenario-risk-result').textContent).not.toMatch(/\b[a-z]+(?:_[a-z0-9]+)+\b/);
    expect(screen.getByTestId('portfolio-scenario-risk-result')).toHaveTextContent('不触发经纪商同步');
    expect(screen.getByTestId('portfolio-scenario-risk-result')).toHaveTextContent('不改动账务结果');
    expect(screen.getByTestId('portfolio-scenario-risk-result')).toHaveTextContent('不触发任何下单');
    expect(screen.getByTestId('portfolio-scenario-risk-result')).toHaveTextContent('模型结果不可作为仓位建议');
  });
});
