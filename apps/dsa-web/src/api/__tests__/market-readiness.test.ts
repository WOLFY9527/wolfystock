import { beforeEach, describe, expect, it, vi } from 'vitest';

const { get } = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock('../index', () => ({
  default: {
    get,
  },
}));

describe('marketApi.getDataReadiness', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads and normalizes the read-only market data readiness diagnostics response', async () => {
    const { marketApi } = await import('../market');
    get.mockResolvedValueOnce({
      data: {
        readiness_status: 'partial',
        diagnostic_only: true,
        provider_runtime_called: false,
        network_calls_enabled: false,
        representative_symbols: ['AAPL', 'SPY', 'BTC-USD'],
        checks: [
          {
            id: 'tushare_token',
            status: 'missing',
            severity: 'warning',
            user_facing_message: 'Tushare token is not configured.',
            remediation_hint: 'Set TUSHARE_TOKEN for local CN/HK diagnostics.',
            affects_surfaces: ['market_overview', 'liquidity_monitor'],
            secret_configured: false,
          },
          {
            id: 'optional_provider_dependencies',
            status: 'partial',
            severity: 'warning',
            user_facing_message: 'Some optional local provider dependencies are not importable.',
            remediation_hint: 'Install the missing local provider SDKs when required.',
            affects_surfaces: ['market_overview', 'liquidity_monitor'],
            details: {
              available_modules: ['tushare'],
              missing_modules: ['pytdx', 'akshare'],
            },
          },
        ],
        consumer_evidence_readiness_matrix: {
          contract_version: 'consumer_evidence_readiness_matrix_v1',
          diagnostic_only: true,
          network_calls_enabled: false,
          mutation_enabled: false,
          items: [
            {
              surface: 'market_overview',
              evidence_family: 'market_regime',
              required_inputs: ['macro context', 'liquidity context'],
              fulfilled_inputs: ['market overview read model'],
              missing_inputs: ['macro context'],
              stale_inputs: [],
              blocked_inputs: ['liquidity context'],
              observation_only_inputs: ['rotation context'],
              score_grade_inputs: ['market overview read model'],
              readiness_state: 'score_grade',
              confidence_cap_reason: 'Supporting families still cap confidence.',
              source_authority_reason: 'Supporting families need stronger display authority.',
              freshness_reason: 'Freshness is measured by each existing market surface before this matrix is shown.',
              next_diagnostic: 'Compare overview evidence families against current safe surface snapshots.',
              consumer_safe_summary: 'Market overview has one score-grade input, while supporting evidence remains capped or observational.',
            },
          ],
        },
      },
    });

    const payload = await marketApi.getDataReadiness({ symbols: ['AAPL', 'SPY', 'BTC-USD'] });

    expect(get).toHaveBeenCalledWith('/api/v1/market/data-readiness', {
      params: { symbols: 'AAPL,SPY,BTC-USD' },
    });
    expect(payload.readinessStatus).toBe('partial');
    expect(payload.diagnosticOnly).toBe(true);
    expect(payload.providerRuntimeCalled).toBe(false);
    expect(payload.networkCallsEnabled).toBe(false);
    expect(payload.representativeSymbols).toEqual(['AAPL', 'SPY', 'BTC-USD']);
    expect(payload.checks[0].secretConfigured).toBe(false);
    expect(payload.checks[1].details?.missingModules).toEqual(['pytdx', 'akshare']);
    expect(payload.consumerEvidenceReadinessMatrix?.contractVersion).toBe('consumer_evidence_readiness_matrix_v1');
    expect(payload.consumerEvidenceReadinessMatrix?.diagnosticOnly).toBe(true);
    expect(payload.consumerEvidenceReadinessMatrix?.items[0]).toMatchObject({
      surface: 'market_overview',
      evidenceFamily: 'market_regime',
      readinessState: 'score_grade',
      missingInputs: ['macro context'],
      blockedInputs: ['liquidity context'],
      observationOnlyInputs: ['rotation context'],
      scoreGradeInputs: ['market overview read model'],
      nextDiagnostic: 'Compare overview evidence families against current safe surface snapshots.',
    });
  });

  it('builds compact consumer evidence boundary labels without exposing matrix internals', async () => {
    const { buildConsumerEvidenceBoundaryView } = await import('../market');

    const view = buildConsumerEvidenceBoundaryView({
      contractVersion: 'consumer_evidence_readiness_matrix_v1',
      diagnosticOnly: true,
      networkCallsEnabled: false,
      mutationEnabled: false,
      items: [
        {
          surface: 'market_overview',
          evidenceFamily: 'market_regime',
          requiredInputs: ['market overview read model', 'market breadth context', 'rotation context', 'macro context', 'liquidity context'],
          fulfilledInputs: ['market overview read model'],
          missingInputs: ['market breadth context'],
          staleInputs: ['rotation context'],
          blockedInputs: ['macro context'],
          observationOnlyInputs: ['liquidity context'],
          scoreGradeInputs: ['market overview read model'],
          readinessState: 'score_grade',
          confidenceCapReason: 'internal cap reason',
          sourceAuthorityReason: 'source_authority_router_rejected',
          freshnessReason: 'freshness stale',
          nextDiagnostic: 'Compare raw provider cache diagnostics.',
          consumerSafeSummary: 'Market overview evidence summary.',
        },
      ],
    });

    expect(view.label).toBe('证据可用');
    expect(view.chips.map((chip) => chip.label)).toEqual([
      '证据可用',
      '市场总览读数可用',
      '市场广度待补',
      '板块轮动待更新',
      '风险状态仅观察',
    ]);
    expect(view.nextEvidence).toBe('下一步：补齐市场广度、宏观背景');
    expect(JSON.stringify(view)).not.toMatch(
      /contractVersion|market_overview|market_regime|confidenceCapReason|sourceAuthority|nextDiagnostic|consumerSafeSummary|provider|cache|debug|raw|buy|sell|target price|position sizing|买入|卖出|目标价|止损|仓位/i,
    );
  });

  it('keeps absent consumer evidence readiness fail-closed', async () => {
    const { buildConsumerEvidenceBoundaryView } = await import('../market');

    const view = buildConsumerEvidenceBoundaryView(undefined);

    expect(view.label).toBe('证据边界待确认');
    expect(view.chips.map((chip) => chip.label)).toContain('市场总览待补');
    expect(view.chips.map((chip) => chip.label)).toContain('广度待补');
    expect(view.chips.map((chip) => chip.label)).toContain('板块轮动待补');
    expect(view.chips.map((chip) => chip.label)).toContain('风险状态待补');
    expect(JSON.stringify(view)).not.toMatch(/证据可用|provider|cache|debug|raw|buy|sell|买入|卖出|目标价|止损|仓位/i);
  });
});
