import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { AxiosResponse } from 'axios';
import apiClient from '../index';
import { optionsLabApi } from '../optionsLab';

vi.mock('../index', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

function httpError(status: number, data: unknown): Error & { response: AxiosResponse } {
  return {
    name: 'AxiosError',
    message: `HTTP ${status}`,
    response: {
      data,
      status,
      statusText: String(status),
      headers: {},
      config: {},
    } as AxiosResponse,
  };
}

describe('optionsLabApi fixture fallback boundaries', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('keeps local fixture fallback for backend-unavailable read probes', async () => {
    vi.mocked(apiClient.get).mockRejectedValueOnce(new Error('Network Error'));

    await expect(optionsLabApi.getUnderlyingSummary('tem')).resolves.toMatchObject({
      symbol: 'TEM',
      metadata: {
        readOnly: true,
      },
    });
  });

  it('does not mask authenticated or unsupported-symbol HTTP responses with fixtures', async () => {
    vi.mocked(apiClient.get).mockRejectedValueOnce(httpError(401, {
      error: 'unauthorized',
      message: 'Login required',
    }));

    await expect(optionsLabApi.getUnderlyingSummary('TEM')).rejects.toMatchObject({
      response: {
        status: 401,
      },
    });

    vi.mocked(apiClient.get).mockRejectedValueOnce(httpError(404, {
      detail: {
        error: 'unsupported_symbol',
        message: 'Options Lab Phase 1 supports fixture-backed US listed equity options only.',
      },
    }));

    await expect(optionsLabApi.getExpirations('HK00700')).rejects.toMatchObject({
      response: {
        status: 404,
      },
    });
  });

  it('posts decision evaluation and keeps network-error fallback demo-only', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        symbol: 'TEM',
        strategy: 'long_call',
        data_quality: {
          data_quality_score: 25,
          data_quality_tier: 'synthetic_demo_only',
          source_type: 'synthetic',
          blocking_reasons: ['synthetic_or_fixture_data_not_decision_grade'],
        },
        liquidity: {
          liquidity_score: 50,
          spread_pct: 12,
          liquidity_warnings: [],
        },
        iv_greeks: {
          iv_readiness: 60,
          iv_rank_status: 'unavailable',
          warnings: ['iv_rank_unavailable'],
        },
        breakeven: {
          breakeven: 57.7,
          required_move_pct: 10.11,
          target_price_status: 'target_above_breakeven',
          score: 70,
        },
        risk_reward: {
          max_loss: 270,
          max_gain: null,
          risk_reward_ratio: null,
          score: 50,
        },
        trade_quality_score: 35,
        decision_label: '数据不足，禁止判断',
        primary_reasons: ['当前为 synthetic delayed / 演示数据'],
        risk_warnings: ['不可用于真实交易判断'],
        no_advice_disclosure: 'Analytical output only; not personalized financial advice.',
        freshness: {
          source: 'synthetic_options_lab_fixture',
          freshness: 'synthetic_delayed',
        },
        metadata: {
          read_only: true,
          no_external_calls: true,
        },
      },
    } as never);

    await expect(optionsLabApi.evaluateDecision({
      symbol: 'tem',
      strategy: 'long_call',
      targetPrice: 65,
    })).resolves.toMatchObject({
      symbol: 'TEM',
      decisionLabel: '数据不足，禁止判断',
      dataQuality: {
        dataQualityTier: 'synthetic_demo_only',
      },
    });
    expect(apiClient.post).toHaveBeenCalledWith('/api/v1/options/decision/evaluate', expect.objectContaining({
      symbol: 'TEM',
      strategy: 'long_call',
    }));

    vi.mocked(apiClient.post).mockRejectedValueOnce(new Error('Network Error'));
    await expect(optionsLabApi.evaluateDecision({
      symbol: 'TEM',
      strategy: 'bull_call_spread',
    })).resolves.toMatchObject({
      decisionLabel: '数据不足，禁止判断',
      dataQuality: {
        dataQualityTier: 'synthetic_demo_only',
      },
    });
  });
});
