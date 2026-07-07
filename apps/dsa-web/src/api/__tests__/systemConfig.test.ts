import { beforeEach, describe, expect, expectTypeOf, it, vi } from 'vitest';
import type {
  SystemAdminActionResponse,
  SystemConfigFieldSchema,
  SystemConfigItem,
  SystemConfigResponse,
} from '../../types/systemConfig';

const { get, post, put } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
}));

vi.mock('../index', () => ({
  default: {
    get,
    post,
    put,
  },
}));

describe('systemConfigApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('preserves backend-required read contract fields without local partial defaults', async () => {
    const { systemConfigApi } = await import('../systemConfig');
    get.mockResolvedValueOnce({
      data: {
        config_version: 'cfg-v1',
        mask_token: '******',
        updated_at: '2026-06-12T08:00:00',
        items: [
          {
            key: 'ADMIN_AUTH_ENABLED',
            value: 'true',
            raw_value_exists: true,
            is_masked: false,
            raw_editable: false,
            ui_visibility: 'curated',
            managed_by: null,
            schema: {
              key: 'ADMIN_AUTH_ENABLED',
              category: 'system',
              data_type: 'boolean',
              ui_control: 'switch',
              is_sensitive: false,
              is_required: true,
              is_editable: false,
              options: [],
              validation: {},
              display_order: 10,
              raw_editable: false,
              ui_visibility: 'curated',
              managed_by: null,
            },
          },
        ],
      },
    });

    const result = await systemConfigApi.getConfig(true);

    expectTypeOf<SystemConfigItem['rawEditable']>().toEqualTypeOf<boolean>();
    expectTypeOf<SystemConfigItem['uiVisibility']>().toEqualTypeOf<'raw' | 'curated' | 'hidden' | 'advanced'>();
    expectTypeOf<SystemConfigFieldSchema['rawEditable']>().toEqualTypeOf<boolean>();
    expectTypeOf<SystemConfigFieldSchema['uiVisibility']>().toEqualTypeOf<'raw' | 'curated' | 'hidden' | 'advanced'>();
    expectTypeOf<SystemConfigResponse['items']>().toEqualTypeOf<SystemConfigItem[]>();
    expect(get).toHaveBeenCalledWith('/api/v1/system/config', {
      params: { include_schema: true },
    });
    expect(result.items[0].rawEditable).toBe(false);
    expect(result.items[0].uiVisibility).toBe('curated');
    expect(result.items[0].schema?.rawEditable).toBe(false);
    expect(result.items[0].schema?.uiVisibility).toBe('curated');
  });

  it('preserves mutation and bounded admin action response fields', async () => {
    const { systemConfigApi } = await import('../systemConfig');
    put.mockResolvedValueOnce({
      data: {
        success: true,
        config_version: 'cfg-v2',
        applied_count: 1,
        skipped_masked_count: 1,
        reload_triggered: true,
        updated_keys: ['STOCK_LIST'],
        warnings: ['runtime reload scheduled'],
      },
    });
    post.mockResolvedValueOnce({
      data: {
        success: true,
        action: 'reset_runtime_caches',
        message: 'Runtime provider/search caches were reset',
        cleared: ['data_fetcher_manager', 'search_service'],
        preserved: [],
        counts: {},
      },
    });

    const update = await systemConfigApi.update({
      configVersion: 'cfg-v1',
      maskToken: '******',
      reloadNow: true,
      items: [{ key: 'STOCK_LIST', value: 'AAPL' }],
    });
    const reset = await systemConfigApi.resetRuntimeCaches();

    expect(update).toEqual({
      success: true,
      configVersion: 'cfg-v2',
      appliedCount: 1,
      skippedMaskedCount: 1,
      reloadTriggered: true,
      updatedKeys: ['STOCK_LIST'],
      warnings: ['runtime reload scheduled'],
    });
    expectTypeOf<SystemAdminActionResponse['preserved']>().toEqualTypeOf<string[]>();
    expectTypeOf<SystemAdminActionResponse['counts']>().toEqualTypeOf<Record<string, number>>();
    expect(reset.preserved).toEqual([]);
    expect(reset.counts).toEqual({});
  });

  it('preserves backend error detail contracts through the canonical parser', async () => {
    const {
      systemConfigApi,
      SystemConfigConflictError,
      SystemConfigValidationError,
    } = await import('../systemConfig');

    put.mockRejectedValueOnce({
      response: {
        status: 400,
        data: {
          detail: {
            error: 'validation_failed',
            message: 'System configuration validation failed',
            issues: [
              {
                key: 'WEBUI_PORT',
                code: 'invalid_integer',
                message: 'WEBUI_PORT must be a valid integer',
                severity: 'error',
                expected: 'integer',
                actual: 'not-a-port',
              },
            ],
          },
        },
      },
    });

    await expect(systemConfigApi.update({
      configVersion: 'cfg-v1',
      maskToken: '******',
      reloadNow: true,
      items: [{ key: 'WEBUI_PORT', value: 'not-a-port' }],
    })).rejects.toMatchObject({
      name: 'SystemConfigValidationError',
      issues: [
        expect.objectContaining({
          key: 'WEBUI_PORT',
          code: 'invalid_integer',
          severity: 'error',
        }),
      ],
      parsedError: expect.objectContaining({
        message: expect.stringContaining('System configuration validation failed'),
        code: 'validation_failed',
      }),
    });

    put.mockRejectedValueOnce({
      response: {
        status: 409,
        data: {
          detail: {
            error: 'config_version_conflict',
            message: 'Configuration has changed, please reload and retry',
            current_config_version: 'cfg-v2',
          },
        },
      },
    });

    await expect(systemConfigApi.update({
      configVersion: 'cfg-v1',
      maskToken: '******',
      reloadNow: true,
      items: [{ key: 'STOCK_LIST', value: 'AAPL' }],
    })).rejects.toMatchObject({
      name: 'SystemConfigConflictError',
      currentConfigVersion: 'cfg-v2',
      parsedError: expect.objectContaining({
        message: expect.stringContaining('Configuration has changed, please reload and retry'),
        code: 'config_version_conflict',
      }),
    });

    expect(SystemConfigValidationError).toBeDefined();
    expect(SystemConfigConflictError).toBeDefined();
  });
});
