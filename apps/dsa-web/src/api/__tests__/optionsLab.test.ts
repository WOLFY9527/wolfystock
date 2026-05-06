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
});
