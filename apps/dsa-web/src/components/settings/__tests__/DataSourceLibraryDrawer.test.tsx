import { render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { settleDrawerOpen } from '../../common/__tests__/modalTestHelpers';
import { translate } from '../../../i18n/core';
import type { BuiltinDataSourceValidationResult, DataSourceLibraryEntry } from '../dataSourceLibraryShared';
import DataSourceLibraryDrawer from '../DataSourceLibraryDrawer';

const zh = (key: string, vars?: Record<string, string | number | undefined>) => translate('zh', key, vars);

function buildBuiltinEntry(): DataSourceLibraryEntry {
  return {
    key: 'twelve_data',
    label: 'Twelve Data',
    kind: 'builtin',
    builtin: true,
    baseUrl: '',
    configured: true,
    usable: true,
    validationState: 'partial',
    validationMessage: zh('settings.dataSourceValidationPartial'),
    routeUsage: ['market'],
    capabilityKeys: ['market'],
    capabilityLabels: [zh('settings.dataSourceCapability.market')],
    description: zh('settings.dataSourceCredentialDesc'),
    credentialRequired: true,
    credentialValue: 'td-s...-key',
    credentialSchema: 'single_key',
    management: {
      credentialSchema: 'single_key',
      fields: [
        {
          name: 'credential',
          labelKey: 'settings.dataSourceFieldApiKey',
          hintKey: 'settings.dataSourceFieldTwelveDataKeyHint',
        },
      ],
    },
  };
}

describe('DataSourceLibraryDrawer', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('explains known provider impact before a custom source is saved', async () => {
    render(
      <DataSourceLibraryDrawer
        adminLocked={false}
        isOpen
        isSaving={false}
        language="zh"
        deleteTarget={null}
        draft={{
          id: '',
          name: 'Polygon',
          credentialSchema: 'single_key',
          credential: '',
          secret: '',
          baseUrl: '',
          description: '',
          capabilities: [],
          validation: { status: 'pending' },
        }}
        entry={null}
        mode="create"
        managedBuiltinDraft={{ credential: '', secret: '', extraValue: '' }}
        onClose={vi.fn()}
        onDeleteTargetChange={vi.fn()}
        onDraftChange={vi.fn()}
        onManagedBuiltinDraftChange={vi.fn()}
        onSave={vi.fn()}
        onValidate={vi.fn()}
        onConfirmDelete={vi.fn()}
        t={zh}
      />,
    );

    await settleDrawerOpen();

    const panel = screen.getByTestId('data-source-impact-panel');
    expect(within(panel).getByText('配置后可能影响')).toBeInTheDocument();
    expect(within(panel).getByText('Market Overview')).toBeInTheDocument();
    expect(within(panel).getByText('Liquidity Monitor')).toBeInTheDocument();
    expect(within(panel).getByText('可解锁能力')).toBeInTheDocument();
    expect(within(panel).getByText('US breadth')).toBeInTheDocument();
    expect(within(panel).getByText(/grouped daily/)).toBeInTheDocument();
    expect(within(panel).getByText(/不是官方 NYSE\/Nasdaq/)).toBeInTheDocument();
    expect(within(panel).getByText(/不会自动变成可评分证据/)).toBeInTheDocument();
  });

  it('keeps unknown provider impact limited to Provider Ops without rendering secret or path text', async () => {
    render(
      <DataSourceLibraryDrawer
        adminLocked={false}
        isOpen
        isSaving={false}
        language="zh"
        deleteTarget={null}
        draft={{
          id: '',
          name: 'Mystery Local Feed',
          credentialSchema: 'single_key',
          credential: 'opaque-value',
          secret: '',
          baseUrl: '',
          description: 'local cache LOCAL_PRIVATE_FEED_PATH opaque=value',
          capabilities: ['news'],
          validation: { status: 'pending' },
        }}
        entry={null}
        mode="create"
        managedBuiltinDraft={{ credential: '', secret: '', extraValue: '' }}
        onClose={vi.fn()}
        onDeleteTargetChange={vi.fn()}
        onDraftChange={vi.fn()}
        onManagedBuiltinDraftChange={vi.fn()}
        onSave={vi.fn()}
        onValidate={vi.fn()}
        onConfirmDelete={vi.fn()}
        t={zh}
      />,
    );

    await settleDrawerOpen();

    const panel = screen.getByTestId('data-source-impact-panel');
    expect(within(panel).getByText('Provider Ops / system diagnostics')).toBeInTheDocument();
    expect(within(panel).queryByText('Market Overview')).not.toBeInTheDocument();
    expect(within(panel).queryByText('Liquidity Monitor')).not.toBeInTheDocument();
    expect(within(panel).queryByText(/opaque-value/i)).not.toBeInTheDocument();
    expect(within(panel).queryByText(/LOCAL_PRIVATE_FEED_PATH/i)).not.toBeInTheDocument();
  });

  it('renders the Twelve Data HK entitlement check as compact badges without exposing raw provider details', async () => {
    const validationResult: BuiltinDataSourceValidationResult = {
      provider: 'twelve_data',
      ok: false,
      status: 'partial',
      checkedAt: '2026-05-14T09:10:00+08:00',
      durationMs: 88,
      keyMasked: 'td-s...-key',
      checks: [
        {
          name: 'hk_quote_history',
          endpoint: '/quote + /time_series',
          ok: false,
          httpStatus: 429,
          durationMs: 88,
          errorType: 'quota_limited',
          message: 'quota exceeded token=SECRET https://api.twelvedata.test/raw',
        },
      ],
      summary: 'Twelve Data 已配置，但 HK quote/history 诊断命中额度或频率限制。',
      suggestion: '请检查 Twelve Data credits/quota/frequency limit，稍后重试或切换可用 key。',
    };

    render(
      <DataSourceLibraryDrawer
        adminLocked={false}
        isOpen
        isSaving={false}
        language="zh"
        deleteTarget={null}
        draft={{
          id: '',
          name: '',
          credentialSchema: 'single_key',
          credential: '',
          secret: '',
          baseUrl: '',
          description: '',
          capabilities: [],
          validation: { status: 'pending' },
        }}
        entry={buildBuiltinEntry()}
        mode="manage_builtin"
        managedBuiltinDraft={{ credential: '', secret: '', extraValue: '' }}
        onClose={vi.fn()}
        onDeleteTargetChange={vi.fn()}
        onDraftChange={vi.fn()}
        onManagedBuiltinDraftChange={vi.fn()}
        onSave={vi.fn()}
        onValidate={vi.fn()}
        onConfirmDelete={vi.fn()}
        t={zh}
        validationResult={validationResult}
      />,
    );

    await settleDrawerOpen();

    const panel = screen.getByTestId('builtin-data-source-validation-result');
    expect(within(panel).getByText('港股权限')).toBeInTheDocument();
    expect(within(panel).getByText('额度受限')).toBeInTheDocument();
    expect(within(panel).getByText('已配置')).toBeInTheDocument();
    expect(within(panel).queryByText(/hk_quote_history: HTTP 429/i)).not.toBeInTheDocument();
    expect(within(panel).queryByText(/quota exceeded/i)).not.toBeInTheDocument();
    expect(within(panel).queryByText(/https:\/\/api\.twelvedata\.test\/raw/i)).not.toBeInTheDocument();
    expect(within(panel).queryByText(/SECRET/i)).not.toBeInTheDocument();
  });
});
