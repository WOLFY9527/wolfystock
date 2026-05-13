import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { UiLanguageProvider } from '../../../contexts/UiLanguageContext';
import BacktestSupportExportsDisclosure from '../BacktestSupportExportsDisclosure';

const {
  getRuleBacktestSupportExportIndex,
  getRuleBacktestSupportBundleManifest,
  getRuleBacktestSupportBundleReproducibilityManifest,
  getRuleBacktestRobustnessEvidenceJson,
  getRuleBacktestExecutionTraceJson,
  getRuleBacktestExecutionTraceCsv,
} = vi.hoisted(() => ({
  getRuleBacktestSupportExportIndex: vi.fn(),
  getRuleBacktestSupportBundleManifest: vi.fn(),
  getRuleBacktestSupportBundleReproducibilityManifest: vi.fn(),
  getRuleBacktestRobustnessEvidenceJson: vi.fn(),
  getRuleBacktestExecutionTraceJson: vi.fn(),
  getRuleBacktestExecutionTraceCsv: vi.fn(),
}));

vi.mock('../../../api/backtest', () => ({
  backtestApi: {
    getRuleBacktestSupportExportIndex,
    getRuleBacktestSupportBundleManifest,
    getRuleBacktestSupportBundleReproducibilityManifest,
    getRuleBacktestRobustnessEvidenceJson,
    getRuleBacktestExecutionTraceJson,
    getRuleBacktestExecutionTraceCsv,
  },
}));

function renderDisclosure() {
  return render(
    <UiLanguageProvider>
      <BacktestSupportExportsDisclosure runId={99} code="ORCL" />
    </UiLanguageProvider>,
  );
}

describe('BacktestSupportExportsDisclosure', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('stays collapsed by default and only loads the export index after opening', async () => {
    getRuleBacktestSupportExportIndex.mockResolvedValue({
      runId: 99,
      status: 'completed',
      exports: [
        {
          key: 'support_bundle_manifest_json',
          available: true,
          availabilityReason: 'ready',
          format: 'json',
          mediaType: 'application/json',
          deliveryMode: 'api',
          endpointPath: '/api/v1/backtest/rule/runs/99/support-bundle-manifest',
          payloadClass: 'RuleBacktestSupportBundleManifestResponse',
        },
        {
          key: 'support_bundle_reproducibility_manifest_json',
          available: true,
          availabilityReason: 'ready',
          format: 'json',
          mediaType: 'application/json',
          deliveryMode: 'api',
          endpointPath: '/api/v1/backtest/rule/runs/99/support-bundle-reproducibility-manifest',
          payloadClass: 'RuleBacktestSupportBundleReproducibilityManifestResponse',
        },
        {
          key: 'execution_trace_json',
          available: true,
          availabilityReason: 'ready',
          format: 'json',
          mediaType: 'application/json',
          deliveryMode: 'api',
          endpointPath: '/api/v1/backtest/rule/runs/99/execution-trace.json',
          payloadClass: 'RuleBacktestExecutionTraceExportResponse',
        },
        {
          key: 'robustness_evidence_json',
          available: true,
          availabilityReason: 'ready',
          format: 'json',
          mediaType: 'application/json',
          deliveryMode: 'api',
          endpointPath: '/api/v1/backtest/rule/runs/99/robustness-evidence.json',
          payloadClass: 'RuleBacktestRobustnessEvidenceExportResponse',
        },
        {
          key: 'execution_trace_csv',
          available: false,
          availabilityReason: 'execution_trace_rows_missing',
          format: 'csv',
          mediaType: 'text/csv',
          deliveryMode: 'api',
          endpointPath: '/api/v1/backtest/rule/runs/99/execution-trace.csv',
          payloadClass: 'text/csv',
        },
      ],
    });

    renderDisclosure();

    expect(getRuleBacktestSupportExportIndex).not.toHaveBeenCalled();
    expect(screen.queryByText('支持包清单 JSON')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '展开 技术支持导出' }));

    await waitFor(() => {
      expect(getRuleBacktestSupportExportIndex).toHaveBeenCalledWith(99);
    });

    expect(screen.getByText('支持包清单 JSON')).toBeInTheDocument();
    expect(screen.getByText('复现清单 JSON')).toBeInTheDocument();
    expect(screen.getByText('稳健性证据')).toBeInTheDocument();
    expect(screen.getByText('执行轨迹 JSON')).toBeInTheDocument();
    expect(screen.getByText('执行轨迹 CSV')).toBeInTheDocument();
    expect(screen.getByText('这些导出只用于技术支持与复现实证，不替代结果摘要、图表或指标的主要结论口径。')).toBeInTheDocument();
    expect(screen.queryByText('/api/v1/backtest/rule/runs/99/support-bundle-manifest')).not.toBeInTheDocument();
    expect(screen.queryByText('RuleBacktestSupportBundleManifestResponse')).not.toBeInTheDocument();
    expect(screen.queryByText('stored_backtest_result')).not.toBeInTheDocument();
  });

  it('shows robustness evidence only when the export index marks it available', async () => {
    getRuleBacktestSupportExportIndex.mockResolvedValueOnce({
      runId: 99,
      status: 'completed',
      exports: [
        {
          key: 'support_bundle_manifest_json',
          available: true,
          availabilityReason: 'ready',
          format: 'json',
          mediaType: 'application/json',
          deliveryMode: 'api',
          payloadClass: 'RuleBacktestSupportBundleManifestResponse',
        },
        {
          key: 'robustness_evidence_json',
          available: false,
          availabilityReason: 'robustness_analysis_missing',
          format: 'json',
          mediaType: 'application/json',
          deliveryMode: 'api',
          endpointPath: '/api/v1/backtest/rule/runs/99/robustness-evidence.json',
          payloadClass: 'RuleBacktestRobustnessEvidenceExportResponse',
        },
      ],
    });

    renderDisclosure();

    fireEvent.click(screen.getByRole('button', { name: '展开 技术支持导出' }));

    await waitFor(() => {
      expect(getRuleBacktestSupportExportIndex).toHaveBeenCalledWith(99);
    });

    expect(screen.getByText('支持包清单 JSON')).toBeInTheDocument();
    expect(screen.queryByText('稳健性证据')).not.toBeInTheDocument();
    expect(screen.queryByText('下载稳健性证据 JSON')).not.toBeInTheDocument();
  });

  it('downloads support artifacts through the existing read-only client methods', async () => {
    getRuleBacktestSupportExportIndex.mockResolvedValue({
      runId: 99,
      status: 'completed',
      exports: [
        {
          key: 'support_bundle_manifest_json',
          available: true,
          availabilityReason: 'ready',
          format: 'json',
          mediaType: 'application/json',
          deliveryMode: 'api',
          payloadClass: 'RuleBacktestSupportBundleManifestResponse',
        },
        {
          key: 'support_bundle_reproducibility_manifest_json',
          available: true,
          availabilityReason: 'ready',
          format: 'json',
          mediaType: 'application/json',
          deliveryMode: 'api',
          payloadClass: 'RuleBacktestSupportBundleReproducibilityManifestResponse',
        },
        {
          key: 'execution_trace_json',
          available: true,
          availabilityReason: 'ready',
          format: 'json',
          mediaType: 'application/json',
          deliveryMode: 'api',
          payloadClass: 'RuleBacktestExecutionTraceExportResponse',
        },
        {
          key: 'robustness_evidence_json',
          available: true,
          availabilityReason: 'ready',
          format: 'json',
          mediaType: 'application/json',
          deliveryMode: 'api',
          payloadClass: 'RuleBacktestRobustnessEvidenceExportResponse',
        },
        {
          key: 'execution_trace_csv',
          available: true,
          availabilityReason: 'ready',
          format: 'csv',
          mediaType: 'text/csv',
          deliveryMode: 'api',
          payloadClass: 'text/csv',
        },
      ],
    });
    getRuleBacktestSupportBundleManifest.mockResolvedValue({
      manifestVersion: 'rule_backtest_support_bundle_manifest_v1',
      manifestKind: 'support_bundle_manifest',
      run: { runId: 99, code: 'ORCL' },
      runTiming: {},
      runDiagnostics: {},
      artifactAvailability: {},
      readbackIntegrity: {},
      resultAuthority: { source: 'stored_backtest_result' },
      artifactCounts: { tradeRows: 3 },
    });
    getRuleBacktestSupportBundleReproducibilityManifest.mockResolvedValue({
      manifestVersion: 'rule_backtest_support_bundle_reproducibility_manifest_v1',
      manifestKind: 'support_bundle_reproducibility_manifest',
      run: { runId: 99, code: 'ORCL' },
      runTiming: {},
      runDiagnostics: {},
      artifactAvailability: {},
      readbackIntegrity: {},
      executionAssumptionsFingerprint: { sha256: 'abc123' },
      resultAuthority: { source: 'stored_backtest_result' },
    });
    getRuleBacktestRobustnessEvidenceJson.mockResolvedValue({
      version: 'rule_backtest_robustness_evidence_export_v1',
      source: 'stored_robustness_analysis',
      robustnessAnalysis: {
        state: 'available',
        walkForward: { windows: 4 },
      },
    });
    getRuleBacktestExecutionTraceJson.mockResolvedValue({
      version: 'rule_backtest_execution_trace_export_v1',
      source: 'stored_execution_trace',
      completeness: 'full',
      missingFields: [],
      traceRows: [],
      assumptions: {},
      executionModel: {},
      executionAssumptions: {},
      benchmarkSummary: {},
      fallback: {},
    });
    getRuleBacktestExecutionTraceCsv.mockResolvedValue('date,event_type\n2026-05-12,buy\n');

    const createObjectUrlMock = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test');
    const revokeObjectUrlMock = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
    const clickMock = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

    renderDisclosure();

    fireEvent.click(screen.getByRole('button', { name: '展开 技术支持导出' }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '下载支持包清单 JSON' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: '下载支持包清单 JSON' }));
    fireEvent.click(screen.getByRole('button', { name: '下载复现清单 JSON' }));
    fireEvent.click(screen.getByRole('button', { name: '下载稳健性证据 JSON' }));
    fireEvent.click(screen.getByRole('button', { name: '下载执行轨迹 JSON' }));
    fireEvent.click(screen.getByRole('button', { name: '下载执行轨迹 CSV' }));

    await waitFor(() => {
      expect(getRuleBacktestSupportBundleManifest).toHaveBeenCalledWith(99);
      expect(getRuleBacktestSupportBundleReproducibilityManifest).toHaveBeenCalledWith(99);
      expect(getRuleBacktestRobustnessEvidenceJson).toHaveBeenCalledWith(99);
      expect(getRuleBacktestExecutionTraceJson).toHaveBeenCalledWith(99);
      expect(getRuleBacktestExecutionTraceCsv).toHaveBeenCalledWith(99);
    });

    expect(createObjectUrlMock).toHaveBeenCalledTimes(5);
    expect(clickMock).toHaveBeenCalledTimes(5);

    createObjectUrlMock.mockRestore();
    revokeObjectUrlMock.mockRestore();
    clickMock.mockRestore();
  });
});
