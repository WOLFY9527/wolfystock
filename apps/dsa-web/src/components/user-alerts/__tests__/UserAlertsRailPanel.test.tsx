import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { UiLanguageProvider } from '../../../contexts/UiLanguageContext';
import UserAlertsRailPanel from '../UserAlertsRailPanel';
import type { UserAlertRule, UserAlertRuleListResponse } from '../../../types/userAlerts';

const { listRules, createRule, updateRule } = vi.hoisted(() => ({
  listRules: vi.fn(),
  createRule: vi.fn(),
  updateRule: vi.fn(),
}));

vi.mock('../../../api/userAlerts', () => ({
  userAlertsApi: {
    listRules,
    createRule,
    updateRule,
    deleteRule: vi.fn(),
    listEvents: vi.fn(),
  },
}));

function makeRule(overrides: Partial<UserAlertRule> = {}): UserAlertRule {
  return {
    id: 1,
    contractVersion: 'user_alert_contract_v1',
    ruleType: 'watchlist_price_threshold',
    symbol: 'NVDA',
    direction: 'above',
    thresholdPrice: 1000,
    enabled: true,
    note: null,
    deliveryMode: 'in_app',
    inAppOnly: true,
    ownerScoped: true,
    createdAt: '2026-06-01T08:00:00Z',
    updatedAt: '2026-06-01T08:00:00Z',
    ...overrides,
  };
}

function makeRuleListResponse(items: UserAlertRule[]): UserAlertRuleListResponse {
  return {
    contractVersion: 'user_alert_contract_v1',
    deliveryMode: 'in_app',
    inAppOnly: true,
    ownerScoped: true,
    items,
  };
}

function renderPanel(symbol = 'NVDA') {
  return render(
    <UiLanguageProvider>
      <UserAlertsRailPanel symbol={symbol} language="zh" />
    </UiLanguageProvider>,
  );
}

describe('UserAlertsRailPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listRules.mockResolvedValue(makeRuleListResponse([]));
    createRule.mockResolvedValue(makeRule());
    updateRule.mockResolvedValue(makeRule());
  });

  it('lists current-symbol rules only', async () => {
    listRules.mockResolvedValue(
      makeRuleListResponse([
        makeRule({ id: 1, symbol: 'NVDA', thresholdPrice: 1000.5, note: '突破后再确认' }),
        makeRule({ id: 2, symbol: 'TSM', thresholdPrice: 888.8, note: '不应显示' }),
      ]),
    );

    renderPanel('NVDA');

    const disclosure = await screen.findByTestId('user-alerts-rail-panel');
    fireEvent.click(within(disclosure).getByRole('button', { name: '展开 站内提醒' }));

    expect(within(disclosure).getByText('突破后再确认')).toBeInTheDocument();
    expect(within(disclosure).getByText('高于 1,000.50')).toBeInTheDocument();
    expect(within(disclosure).queryByText('TSM')).not.toBeInTheDocument();
    expect(within(disclosure).queryByText('不应显示')).not.toBeInTheDocument();
    expect(listRules).toHaveBeenCalledTimes(1);
  });

  it('serializes a valid below-threshold rule through userAlertsApi', async () => {
    createRule.mockResolvedValue(
      makeRule({
        id: 9,
        symbol: 'NVDA',
        direction: 'below',
        thresholdPrice: 123.45,
        enabled: false,
        note: '跌破后只做观察',
      }),
    );

    renderPanel('NVDA');

    const disclosure = await screen.findByTestId('user-alerts-rail-panel');
    fireEvent.click(within(disclosure).getByRole('button', { name: '展开 站内提醒' }));
    fireEvent.click(within(disclosure).getByRole('button', { name: '新建提醒' }));
    fireEvent.change(within(disclosure).getByLabelText('方向'), { target: { value: 'below' } });
    fireEvent.change(within(disclosure).getByLabelText('阈值价格'), { target: { value: '123.45' } });
    fireEvent.click(within(disclosure).getByRole('checkbox', { name: '启用提醒' }));
    fireEvent.change(within(disclosure).getByLabelText('备注（可选）'), { target: { value: '跌破后只做观察' } });
    fireEvent.click(within(disclosure).getByRole('button', { name: '保存提醒' }));

    await waitFor(() => expect(createRule).toHaveBeenCalledWith({
      symbol: 'NVDA',
      direction: 'below',
      thresholdPrice: 123.45,
      enabled: false,
      note: '跌破后只做观察',
    }));

    expect(within(disclosure).getByText('低于 123.45')).toBeInTheDocument();
    expect(within(disclosure).getByText('跌破后只做观察')).toBeInTheDocument();
  });

  it('shows an inline safe error for invalid threshold and does not call API', async () => {
    renderPanel('NVDA');

    const disclosure = await screen.findByTestId('user-alerts-rail-panel');
    fireEvent.click(within(disclosure).getByRole('button', { name: '展开 站内提醒' }));
    fireEvent.click(within(disclosure).getByRole('button', { name: '新建提醒' }));
    fireEvent.change(within(disclosure).getByLabelText('阈值价格'), { target: { value: '0' } });
    fireEvent.click(within(disclosure).getByRole('button', { name: '保存提醒' }));

    expect(await within(disclosure).findByText('阈值价格必须大于 0。')).toBeInTheDocument();
    expect(createRule).not.toHaveBeenCalled();
  });

  it('includes in-app-only, no-order, and no-advice semantics in copy', async () => {
    renderPanel('NVDA');

    const disclosure = await screen.findByTestId('user-alerts-rail-panel');
    fireEvent.click(within(disclosure).getByRole('button', { name: '展开 站内提醒' }));

    expect(disclosure).toHaveTextContent('站内提醒');
    expect(disclosure).toHaveTextContent('仅当前账户可见');
    expect(disclosure).toHaveTextContent('仅观察');
    expect(disclosure).toHaveTextContent('不构成投资建议');
    expect(disclosure).toHaveTextContent('不会下单或触发交易动作');
    expect(disclosure).toHaveTextContent('不会发送邮件/短信/浏览器推送/Webhook/管理员通知通道');
    expect(disclosure).toHaveTextContent('不承诺实时盯盘或固定触发时点');
  });
});
