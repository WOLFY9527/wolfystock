import type { Page, Route } from '@playwright/test';
import { expect, test } from './fixtures/appSmoke';

type JsonRecord = Record<string, unknown>;
type BrowserApiRequest = {
  method: string;
  pathname: string;
};

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
              raw_provider_payload: { unsafe: true },
              admin_diagnostics: { trace: 'hidden' },
              provider_route: 'polygon.news',
              authority_grant: false,
              provider: 'polygon',
              source: 'news_proxy',
              raw_category: 'provider_internal_only',
              raw_reason_codes: ['provider_internal_only'],
              debug: { enabled: true },
            },
            {
              id: 'catalyst:NVDA:us:news:1',
              symbol: 'NVDA',
              market: 'us',
              category: 'stored_news_catalyst_proxy',
              title: 'Stored news catalyst proxy',
              summary: 'Stored article summary references a potential demand catalyst.',
              evidence_status: 'proxy',
              evidence_labels: ['proxy', 'unverified'],
              as_of: '2026-05-17T20:00:00+00:00',
              published_at: '2026-05-17T13:00:00+00:00',
              reason_codes: ['observation_only', 'proxy_evidence_not_authoritative'],
              observation_only: true,
              source_authority_allowed: false,
              score_contribution_allowed: false,
              decision_grade: false,
              calendar_claim_allowed: false,
              provider_route: 'news.saved',
              provider: 'saved-news',
              source: 'stored_proxy',
            },
            {
              id: 'catalyst:NVDA:us:macro',
              symbol: 'NVDA',
              market: 'us',
              category: 'official_macro_cache_status',
              title: 'Official macro cache/status exposure',
              summary: 'Official macro cache/status is stale as diagnostic context only; no scheduled macro calendar authority is inferred.',
              evidence_status: 'stale',
              evidence_labels: ['stale'],
              as_of: '2026-05-17',
              reason_codes: ['observation_only', 'stale_evidence'],
              observation_only: true,
              source_authority_allowed: false,
              score_contribution_allowed: false,
              decision_grade: false,
              calendar_claim_allowed: false,
            },
            {
              id: 'catalyst:NVDA:us:news:2',
              symbol: 'NVDA',
              market: 'us',
              category: 'stored_news_catalyst_proxy',
              title: 'Extra hidden exposure',
              summary: 'This item should stay outside the bounded disclosure.',
              evidence_status: 'proxy',
              evidence_labels: ['proxy'],
              as_of: '2026-05-17T21:00:00+00:00',
              reason_codes: ['observation_only'],
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

function isForbiddenMapperBrowserRequest(request: BrowserApiRequest) {
  const pathname = request.pathname.toLowerCase();
  return pathname.includes('/leveraged-etf-mapper')
    || pathname.includes('/quote')
    || pathname.includes('/quotes')
    || pathname.includes('/provider')
    || pathname.includes('/providers')
    || pathname.includes('/broker')
    || pathname.includes('/brokers')
    || pathname.includes('/order')
    || pathname.includes('/orders')
    || pathname.includes('/trade')
    || pathname.includes('/trades')
    || (pathname.includes('/portfolio') && request.method !== 'GET');
}

test.describe('watchlist user alerts browser smoke', () => {
  test('watchlist detail rail keeps user alerts bounded and observation-only in the real route shell', async ({ page }) => {
    const createRuleRequests: JsonRecord[] = [];
    const browserApiRequests: BrowserApiRequest[] = [];

    page.on('request', (request) => {
      const url = new URL(request.url());
      if (!url.pathname.startsWith('/api/')) return;
      browserApiRequests.push({
        method: request.method(),
        pathname: url.pathname,
      });
    });

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

    const mapper = detailRail.getByTestId('leveraged-etf-mapper');
    await expandDisclosure(mapper);

    await expect(mapper).toContainText('手动输入');
    await expect(mapper).toContainText('同日线性情景');
    await expect(mapper).toContainText('每日重置、路径依赖、费用/融资、跟踪误差');
    await expect(mapper).toContainText('不是投资建议');
    await expect(mapper).toContainText('不是可执行或保证价格');

    await mapper.getByLabel('ETF 代码').fill('NVDL');
    await mapper.getByLabel('杠杆倍数 / 方向').fill('2');
    await mapper.getByLabel('正股/指数参考价').fill('100');
    await mapper.getByLabel('ETF 参考价').fill('10');
    await mapper.getByLabel('正股/指数情景上沿').fill('110');
    await mapper.getByLabel('ETF 情景上沿').fill('11');

    await expect(mapper.getByTestId('leveraged-etf-forward-output')).toContainText('NVDL');
    await expect(mapper.getByTestId('leveraged-etf-forward-output')).toContainText('12.00');
    await expect(mapper.getByTestId('leveraged-etf-reverse-output')).toContainText('NVDA');
    await expect(mapper.getByTestId('leveraged-etf-reverse-output')).toContainText('105.00');

    await mapper.getByLabel('杠杆倍数 / 方向').fill('0');

    await expect(mapper).toContainText('杠杆倍数不能为 0。');
    await expect(mapper).toContainText('修正上方输入后再显示映射结果。');
    await expect(mapper.getByTestId('leveraged-etf-forward-output')).toHaveCount(0);
    await expect(mapper.getByTestId('leveraged-etf-reverse-output')).toHaveCount(0);

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
    await expect(catalystExposures).toContainText('基本面线索');
    await expect(catalystExposures).toContainText('已保存新闻线索');
    await expect(catalystExposures).toContainText('宏观背景线索');
    await expect(catalystExposures).not.toContainText('Extra hidden exposure');
    await expect(catalystExposures).toContainText('仅供观察');
    await expect(catalystExposures).toContainText('更新延迟');
    await expect(catalystExposures).toContainText('线索待确认');
    await expect(catalystExposures).toContainText('较旧线索');
    await expect(catalystExposures).toContainText('时间范围 2026Q2');
    await expect(catalystExposures).toContainText('观察时间');
    await expect(catalystExposures).toContainText('发布时间');
    await expect(catalystExposures).toContainText('日程仍待确认');
    await expect(catalystExposures).toContainText('仅作线索');
    await expect(catalystExposures).toContainText('仅展示最近保存的线索');
    await expect(catalystExposures).not.toContainText('raw_provider_payload');
    await expect(catalystExposures).not.toContainText('admin_diagnostics');
    await expect(catalystExposures).not.toContainText('provider_route');
    await expect(catalystExposures).not.toContainText('source_authority_allowed');
    await expect(catalystExposures).not.toContainText('score_contribution_allowed');
    await expect(catalystExposures).not.toContainText('calendar_claim_allowed');
    await expect(catalystExposures).not.toContainText('authority_grant');
    await expect(catalystExposures).not.toContainText('provider_internal_only');
    await expect(catalystExposures).not.toContainText('polygon.news');
    await expect(catalystExposures).not.toContainText('saved-news');
    await expect(catalystExposures).not.toContainText('news_proxy');
    expect(browserApiRequests.filter(isForbiddenMapperBrowserRequest)).toEqual([]);

    await expectNoHorizontalOverflow(page);
  });

  test('empty watchlist shows non-persistent preview and manual research path', async ({ page }) => {
    let watchlistPostCount = 0;
    let analysisPayload: JsonRecord | null = null;

    await page.route('**/api/v1/watchlist/items', async (route) => {
      if (route.request().method() !== 'GET') {
        watchlistPostCount += 1;
        await fulfillJson(route, { error: 'not expected' }, 405);
        return;
      }
      await fulfillJson(route, { items: [] });
    });
    await page.route('**/api/v1/user-alerts/**', async (route) => {
      await fulfillJson(route, { items: [] });
    });
    await page.route('**/api/v1/analysis/analyze', async (route) => {
      analysisPayload = route.request().postDataJSON() as JsonRecord;
      await fulfillJson(route, {
        taskId: 'task-empty-tsla',
        status: 'accepted',
        message: 'Accepted',
      }, 202);
    });
    await page.route('**/api/v1/stocks/*/evidence**', async (route) => {
      await fulfillJson(route, {
        symbols: ['TSLA'],
        items: [],
        meta: {
          generated_at: '2026-06-09T08:00:00Z',
          source: null,
        },
      });
    });

    await page.setViewportSize({ width: 390, height: 844 });
    await signIn(page, '/zh/watchlist');

    const emptyState = page.getByTestId('watchlist-compact-empty-state');
    await expect(emptyState).toBeVisible({ timeout: 15_000 });
    await expect(emptyState).toContainText('还没有观察标的');
    await expect(emptyState).toContainText('首选研究路径');
    await expect(emptyState).toContainText('功能预览');
    await expect(emptyState).toContainText('示例预览');
    await expect(emptyState).toContainText('仅为演示样例');
    await expect(emptyState).toContainText('不会持久化');
    await expect(emptyState).toContainText('不计入观察名单数量');
    await expect(emptyState).toContainText('不会进入扫描器官方排名');
    await expect(emptyState).toContainText('这里优先保留单标的研究与明确保存观察的路径');
    await expect(emptyState).toContainText('手动研究代码');
    await expect(emptyState.getByRole('button', { name: /稍后打开扫描器/i })).toHaveCount(0);
    await expect(page.getByTestId('watchlist-detail-rail')).toHaveCount(0);
    await expect(page.getByTestId('watchlist-candidate-list')).toHaveCount(0);
    await expect(page.getByTestId('watchlist-secondary-deck')).toHaveCount(0);

    await emptyState.getByLabel('手动研究代码').fill('TSLA');
    await emptyState.getByRole('button', { name: '研究 TSLA' }).click();

    await expect.poll(() => analysisPayload).toMatchObject({
      stock_code: 'TSLA',
      report_type: 'detailed',
      stock_name: 'TSLA',
      original_query: 'TSLA',
      selection_source: 'manual',
    });
    expect(watchlistPostCount).toBe(0);

    const bodyText = await page.locator('body').innerText();
    expect(bodyText).not.toMatch(/买入|卖出|下单|立即交易|保证收益|best contract|AI recommends you buy/i);
    await expectNoHorizontalOverflow(page);
  });
});
