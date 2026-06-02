import type { Page, Route } from '@playwright/test';
import { expect, test } from './fixtures/appSmoke';

type JsonRecord = Record<string, unknown>;

const initialRule = {
  id: 1,
  contract_version: 'user_alert_contract_v1',
  rule_type: 'watchlist_price_threshold',
  symbol: 'NVDA',
  direction: 'above',
  threshold_price: 1000.5,
  enabled: true,
  note: '突破后观察',
  delivery_mode: 'in_app',
  in_app_only: true,
  owner_scoped: true,
  created_at: '2026-06-01T08:00:00Z',
  updated_at: '2026-06-01T08:00:00Z',
};

function makeWatchlistItemsPayload() {
  return {
    items: [
      {
        id: 1,
        symbol: 'NVDA',
        market: 'us',
        name: 'NVIDIA',
        source: 'scanner',
        scanner_run_id: 42,
        scanner_rank: 1,
        scanner_score: 94,
        last_scored_at: '2026-05-01T12:30:00Z',
        score_source: 'scanner_run',
        score_profile: 'us_preopen_v1',
        score_reason: 'Latest scanner score.',
        score_status: 'fresh',
        theme_id: 'ai-momentum',
        universe_type: 'theme',
        notes: 'Scanner observation: watch follow-through after the next catalyst.',
        intelligence: {
          scanner: {
            last_score: 94,
            last_rank: 1,
            status: 'selected',
            reason: 'Latest scanner score.',
            last_scanned_at: '2026-05-01T12:30:00Z',
            investor_signal: {
              contract_version: 'investor_signal_contract_v1',
              diagnostic_only: true,
              observation_only: true,
              authority_grant: false,
              decision_grade: false,
              source_authority_allowed: false,
              score_contribution_allowed: false,
              market_regime: 'mixed',
              market_regime_label: '信号分化',
              confidence_label: 'blocked',
              confidence_text: '禁止判断',
              freshness: 'cached',
              reason_codes: ['source_authority_missing', 'score_rights_missing'],
              contradiction_codes: ['theme_rotation_mismatch'],
              explanation: '主题强弱仍然分化，当前只保留观察意义。',
            },
          },
          strategy_simulation: {
            lookback_days: 90,
            forward_days: 5,
            avg_forward_return_pct: 3.2,
            hit_rate: 0.56,
            avg_excess_return_pct: 2.1,
            selection_count: 5,
            data_coverage: 0.83,
            status: 'ready',
          },
          backtest: {
            last_result_id: 33,
            total_return_pct: 24.6,
            max_drawdown_pct: -8.2,
            sharpe: 1.34,
            trade_count: 6,
            tested_at: '2026-05-01T13:30:00Z',
          },
          catalyst_exposures: [
            {
              id: 'catalyst:NVDA:us:fundamental',
              symbol: 'NVDA',
              market: 'us',
              category: 'earnings_fundamental_snapshot',
              title: 'Fundamental snapshot exposure',
              summary: 'Quarterly revenue and margin snapshot is available.',
              evidence_status: 'delayed',
              evidence_labels: ['delayed'],
              as_of: '2026-05-17T20:00:00+00:00',
              timeframe: '2026Q2',
              reason_codes: ['observation_only', 'delayed_evidence', 'not_earnings_calendar'],
              observation_only: true,
              source_authority_allowed: false,
              score_contribution_allowed: false,
              decision_grade: false,
              calendar_claim_allowed: false,
            },
          ],
        },
        created_at: '2026-04-30T08:00:00Z',
        updated_at: '2026-04-30T09:00:00Z',
      },
    ],
  };
}

function makeRuleListPayload(items = [initialRule]) {
  return {
    contract_version: 'user_alert_contract_v1',
    delivery_mode: 'in_app',
    in_app_only: true,
    owner_scoped: true,
    items,
  };
}

function makeEventsPayload() {
  return {
    contract_version: 'user_alert_contract_v1',
    delivery_mode: 'in_app',
    in_app_only: true,
    owner_scoped: true,
    total: 0,
    limit: 20,
    offset: 0,
    items: [],
  };
}

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function signIn(page: Page, redirectPath: string) {
  await page.goto(`/login?redirect=${encodeURIComponent(redirectPath)}`);
  await page.locator('#username').fill('wolfy-user');
  await page.locator('#password').fill('mock-password');
  await Promise.all([
    page.waitForResponse((response) => response.url().includes('/api/v1/auth/login') && response.status() === 200),
    page.getByRole('button', { name: /sign in|登录继续|授权进入工作台|完成设置并登录/i }).click(),
  ]);
  await page.waitForURL(/\/$/);
  await page.goto(redirectPath);
}

async function expectNoHorizontalOverflow(page: Page) {
  await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

async function expandDisclosure(panel: ReturnType<Page['getByTestId']>) {
  const toggle = panel.locator('button').first();
  await toggle.evaluate((element) => {
    element.scrollIntoView({ block: 'center', inline: 'nearest' });
  });
  await toggle.evaluate((element) => {
    (element as HTMLButtonElement).click();
  });
}

test.describe('watchlist user alerts browser smoke', () => {
  test('watchlist detail rail keeps user alerts bounded and observation-only in the real route shell', async ({ page }) => {
    const createRuleRequests: JsonRecord[] = [];

    await page.route('**/api/v1/watchlist/items', async (route) => {
      await fulfillJson(route, makeWatchlistItemsPayload());
    });
    await page.route('**/api/v1/user-alerts/rules', async (route) => {
      const request = route.request();
      if (request.method() === 'GET') {
        await fulfillJson(route, makeRuleListPayload([
          initialRule,
          {
            ...initialRule,
            id: 2,
            symbol: 'TSM',
            threshold_price: 900.1,
            note: '不应显示',
          },
        ]));
        return;
      }

      if (request.method() === 'POST') {
        const payload = request.postDataJSON() as JsonRecord;
        createRuleRequests.push(payload);
        await fulfillJson(route, {
          id: 9,
          contract_version: 'user_alert_contract_v1',
          rule_type: 'watchlist_price_threshold',
          symbol: String(payload.symbol || 'NVDA'),
          direction: String(payload.direction || 'below'),
          threshold_price: Number(payload.threshold_price || 123.45),
          enabled: Boolean(payload.enabled),
          note: payload.note ?? null,
          delivery_mode: 'in_app',
          in_app_only: true,
          owner_scoped: true,
          created_at: '2026-06-02T08:00:00Z',
          updated_at: '2026-06-02T08:00:00Z',
        });
        return;
      }

      await fulfillJson(route, { error: `Unsupported method ${request.method()}` }, 405);
    });
    await page.route('**/api/v1/user-alerts/events**', async (route) => {
      await fulfillJson(route, makeEventsPayload());
    });

    await page.setViewportSize({ width: 1440, height: 1000 });
    await signIn(page, '/zh/watchlist');

    await expect(page.getByTestId('watchlist-page')).toBeVisible();
    await expect(page.getByTestId('watchlist-detail-rail')).toBeVisible();

    const detailRail = page.getByTestId('watchlist-detail-rail');
    const alertsPanel = detailRail.getByTestId('user-alerts-rail-panel');
    await expect(alertsPanel).toContainText('站内提醒');
    await expect(alertsPanel.locator('button').first()).toHaveAttribute('aria-expanded', 'false');
    await expect(alertsPanel.getByText('突破后观察')).toHaveCount(0);

    await expect(detailRail.getByTestId('watchlist-data-notes')).toBeVisible();
    await expect(detailRail.getByTestId('watchlist-investor-signal')).toBeVisible();
    await expect(detailRail.getByTestId('watchlist-catalyst-exposures')).toBeVisible();
    await expect(detailRail.getByTestId('leveraged-etf-mapper')).toBeVisible();

    await expandDisclosure(alertsPanel);

    await expect(alertsPanel.locator('button').first()).toHaveAttribute('aria-expanded', 'true');
    await expect(alertsPanel).toContainText('突破后观察');
    await expect(alertsPanel).not.toContainText('不应显示');
    await expect(alertsPanel).toContainText('仅当前账户可见');
    await expect(alertsPanel).toContainText('仅观察');
    await expect(alertsPanel).toContainText('不构成投资建议');
    await expect(alertsPanel).toContainText('不会下单或触发交易动作');
    await expect(alertsPanel).toContainText('不会发送邮件/短信/浏览器推送/Webhook/管理员通知通道');

    await alertsPanel.getByRole('button', { name: '新建提醒' }).click();
    await alertsPanel.getByLabel('阈值价格').fill('0');
    await alertsPanel.getByRole('button', { name: '保存提醒' }).click();

    await expect(alertsPanel).toContainText('阈值价格必须大于 0。');
    expect(createRuleRequests).toEqual([]);

    await alertsPanel.getByLabel('方向').selectOption('below');
    await alertsPanel.getByLabel('阈值价格').fill('123.45');
    await alertsPanel.getByRole('checkbox', { name: '启用提醒' }).click();
    await alertsPanel.getByLabel('备注（可选）').fill('跌破后只做观察');
    await alertsPanel.getByRole('button', { name: '保存提醒' }).click();

    await expect(alertsPanel).toContainText('低于 123.45');
    await expect(alertsPanel).toContainText('跌破后只做观察');
    expect(createRuleRequests).toHaveLength(1);

    const createPayload = createRuleRequests[0];
    expect(Object.keys(createPayload).sort()).toEqual(['direction', 'enabled', 'note', 'symbol', 'threshold_price']);
    expect({
      symbol: createPayload.symbol,
      direction: createPayload.direction,
      thresholdPrice: createPayload.threshold_price,
      enabled: createPayload.enabled,
      note: createPayload.note,
    }).toEqual({
      symbol: 'NVDA',
      direction: 'below',
      thresholdPrice: 123.45,
      enabled: false,
      note: '跌破后只做观察',
    });
    for (const forbiddenKey of [
      'account',
      'account_id',
      'accountId',
      'broker',
      'broker_id',
      'brokerId',
      'order',
      'order_id',
      'orderId',
      'provider',
      'provider_id',
      'providerId',
      'delivery_mode',
      'deliveryMode',
      'in_app_only',
      'inAppOnly',
      'owner_scoped',
      'ownerScoped',
      'push',
      'push_notification',
      'pushNotification',
      'email',
      'sms',
      'webhook',
      'webhook_url',
      'webhookUrl',
      'admin',
      'admin_notification',
      'adminNotification',
    ]) {
      expect(createPayload).not.toHaveProperty(forbiddenKey);
    }

    const dataNotes = detailRail.getByTestId('watchlist-data-notes');
    await expandDisclosure(dataNotes);
    await expect(dataNotes.getByTestId('watchlist-saved-note')).toContainText('Scanner observation: watch follow-through after the next catalyst.');

    const investorSignal = detailRail.getByTestId('watchlist-investor-signal');
    await expandDisclosure(investorSignal);
    await expect(investorSignal).toContainText('信号分化');
    await expect(investorSignal).toContainText('禁止判断');
    await expect(investorSignal.getByTestId('watchlist-investor-signal-explanation')).toContainText('主题强弱仍然分化，当前只保留观察意义。');

    const catalystExposures = detailRail.getByTestId('watchlist-catalyst-exposures');
    await expandDisclosure(catalystExposures);
    await expect(catalystExposures).toContainText('Fundamental snapshot exposure');
    await expect(catalystExposures).toContainText('仅观察');

    await expectNoHorizontalOverflow(page);
  });
});
