import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import MarketRotationRadarPage from '../MarketRotationRadarPage';
import { marketRotationApi } from '../../api/marketRotation';
import type { MarketRotationRadarResponse } from '../../api/marketRotation';

vi.mock('../../api/marketRotation', () => ({
  marketRotationApi: {
    getRotationRadar: vi.fn(),
  },
}));

const forbiddenTradingActionPattern =
  /买入按钮|建议买入|建议卖出|卖出指令|立即交易|下单|提交订单|订单载荷|开仓|平仓|加仓|减仓|持仓建议|仓位建议|决策级|decision[-\s]?grade|buy now|sell now|place order|submit order|best contract|guaranteed/i;

const radarFixture = (): MarketRotationRadarResponse => ({
  endpoint: '/api/v1/market/rotation-radar',
  market: 'US',
  supportedMarkets: ['US', 'CN', 'HK', 'CRYPTO'],
  generatedAt: '2026-05-07T09:50:00Z',
  source: 'computed',
  sourceLabel: '主题篮子计算',
  freshness: 'delayed',
  isFallback: false,
  isStale: false,
  warning: null,
  noAdviceDisclosure: '仅用于观察资金轮动迹象，非买卖建议。',
  metadata: {
    noExternalCalls: true,
    schemaVersion: 'market_rotation_radar_phase4_v1',
    timeWindows: ['5m', '15m', '60m', '1d'],
    proxyQualityRequired: true,
    alertsAreReadOnlyEvidence: true,
    notificationDeliveryEnabled: false,
  },
  benchmarks: {
    QQQ: { symbol: 'QQQ', changePercent: 0.8, timeWindows: {}, freshness: 'delayed', isFallback: false, isStale: false },
    SPY: { symbol: 'SPY', changePercent: 0.4, timeWindows: {}, freshness: 'delayed', isFallback: false, isStale: false },
    IWM: { symbol: 'IWM', changePercent: 0.1, timeWindows: {}, freshness: 'delayed', isFallback: false, isStale: false },
    IGV: { symbol: 'IGV', changePercent: 0.6, timeWindows: {}, freshness: 'delayed', isFallback: false, isStale: false },
  },
  summary: {
    strongestThemes: [
      { id: 'ai_applications', name: 'AI 应用', rotationScore: 78, confidence: 0.72, stage: 'confirmed_rotation', freshness: 'delayed', isFallback: false, riskLabels: [] },
    ],
    acceleratingThemes: [
      { id: 'ai_applications', name: 'AI 应用', rotationScore: 78, confidence: 0.72, stage: 'confirmed_rotation', freshness: 'delayed', isFallback: false, riskLabels: [] },
    ],
    fadingThemes: [
      { id: 'robotics', name: '机器人', rotationScore: 38, confidence: 0.31, stage: 'weak_or_no_signal', freshness: 'fallback', isFallback: true, riskLabels: ['stale_or_incomplete_windows'] },
    ],
    watchlistSignals: [
      { themeId: 'ai_applications', themeName: 'AI 应用', symbol: 'APP', label: '关注候选', signal: 'confirmed_rotation', signalLabel: '确认轮动', confidence: 0.72, persistenceScore: 0.86, readOnly: true, deliveryEnabled: false, reasons: ['AI 应用：确认轮动'], sortExplanation: '按主题轮动强度、置信度、跨时窗持续证据、成员相对强弱和量能扩张排序；仅用于观察信号排队，非买卖建议。' },
    ],
    watchlistSortingExplanation: '关注候选按主题轮动强度、置信度、跨时窗持续证据和成员相对强弱排序；仅作为观察信号，非买卖建议。',
    safeWording: ['资金轮动迹象', '成交额扩张', '相对强势扩散', '板块同步性增强', '非买卖建议'],
  },
  themes: [
    {
      id: 'ai_applications',
      name: 'AI 应用',
      englishName: 'AI Applications',
      focus: '应用层软件、数据工作流与企业 AI 落地',
      benchmark: 'QQQ',
      sectorBenchmark: 'IGV',
      membersConfigured: ['APP', 'PLTR', 'CRM'],
      rotationScore: 78,
      confidence: 0.72,
      stage: 'confirmed_rotation',
      stageExplanation: '价格、量能、广度和同步性同时满足阈值。置信度 72%，3 个分钟级时窗可用。',
      riskLabels: ['gap_fade_risk'],
      riskExplanations: ['涨幅较大但 VWAP、量能或广度确认不足，需防止冲高回落。'],
      newslessRotation: true,
      newslessRotationEvidence: '无明显新闻的同步异动：未配置新闻催化证据。',
      persistenceScore: 0.86,
      persistenceEvidence: {
        score: 0.86,
        label: '跨时窗延续',
        availableWindows: ['5m', '15m', '60m', '1d'],
        missingWindows: [],
        staleOrFallbackWindows: [],
        positiveWindowCount: 4,
        negativeWindowCount: 0,
        sameDirectionWindowCount: 4,
        requiredWindows: ['5m', '15m', '60m', '1d'],
        explanation: '跨时窗延续：可用 5m/15m/60m/1d，缺失 无，备用/过期 无。',
      },
      alertCandidates: [
        { themeId: 'ai_applications', themeName: 'AI 应用', symbol: 'APP', label: '关注候选', signal: 'confirmed_rotation', signalLabel: '确认轮动', confidence: 0.72, persistenceScore: 0.86, persistenceLabel: '跨时窗延续', readOnly: true, deliveryEnabled: false, reasons: ['AI 应用：确认轮动'], sortExplanation: '按主题轮动强度、置信度、跨时窗持续证据、成员相对强弱和量能扩张排序；仅用于观察信号排队，非买卖建议。' },
      ],
      relativeStrength: {
        benchmark: 'QQQ',
        benchmarkChangePercent: 0.8,
        averageThemeChangePercent: 3.6,
        averageRelativeStrengthPercent: 2.8,
        vsBenchmarks: { QQQ: 2.8, SPY: 3.2, IWM: 3.5 },
      },
      proxyQuality: {
        label: 'ETF 代理完整',
        coveragePercent: 100,
        availableProxyCount: 4,
        totalProxyCount: 4,
        requiredProxies: ['QQQ', 'SPY', 'IWM', 'IGV'],
        freshness: 'delayed',
        hasMissingRequiredProxy: false,
        hasStaleProxy: false,
        missingReasons: {},
        explanation: 'ETF 代理完整：ETF 代理覆盖 4/4，缺口 无。',
      },
      benchmarkProxies: {
        QQQ: { symbol: 'QQQ', role: 'market_proxy', changePercent: 0.8, relativeStrength: 2.8, freshness: 'delayed', isFallback: false, isStale: false, sourceLabel: 'Unit Fixture', quality: { available: true, freshness: 'delayed', missingReason: null, qualityLabel: '可用代理', coverageContribution: 1 } },
        SPY: { symbol: 'SPY', role: 'market_proxy', changePercent: 0.4, relativeStrength: 3.2, freshness: 'delayed', isFallback: false, isStale: false, sourceLabel: 'Unit Fixture', quality: { available: true, freshness: 'delayed', missingReason: null, qualityLabel: '可用代理', coverageContribution: 1 } },
        IWM: { symbol: 'IWM', role: 'market_proxy', changePercent: 0.1, relativeStrength: 3.5, freshness: 'delayed', isFallback: false, isStale: false, sourceLabel: 'Unit Fixture', quality: { available: true, freshness: 'delayed', missingReason: null, qualityLabel: '可用代理', coverageContribution: 1 } },
        IGV: { symbol: 'IGV', role: 'sector_proxy', changePercent: 0.6, relativeStrength: 3.0, freshness: 'delayed', isFallback: false, isStale: false, sourceLabel: 'Unit Fixture', quality: { available: true, freshness: 'delayed', missingReason: null, qualityLabel: '可用代理', coverageContribution: 1 } },
      },
      timeWindows: {
        '5m': { window: '5m', label: '5分钟', available: true, changePercent: 0.8, relativeVolume: 1.3, freshness: 'delayed', isFallback: false, isStale: false, sourceLabel: 'Unit Fixture' },
        '15m': { window: '15m', label: '15分钟', available: true, changePercent: 1.4, relativeVolume: 1.5, freshness: 'delayed', isFallback: false, isStale: false, sourceLabel: 'Unit Fixture' },
        '60m': { window: '60m', label: '60分钟', available: true, changePercent: 2.2, relativeVolume: 1.7, freshness: 'delayed', isFallback: false, isStale: false, sourceLabel: 'Unit Fixture' },
        '1d': { window: '1d', label: '日内/日线', available: true, changePercent: 3.6, relativeVolume: 1.8, freshness: 'delayed', isFallback: false, isStale: false, sourceLabel: 'Unit Fixture' },
      },
      volume: { averageRelativeVolume: 1.8, availableMemberCount: 3, label: '成交额扩张明显' },
      breadth: {
        observedMembers: 3,
        configuredMembers: 3,
        coveragePercent: 100,
        percentUp: 100,
        percentOutperformingBenchmark: 100,
      },
      synchronization: { sameDirectionPercent: 100, aboveVwapPercent: 100, persistencePercent: 100, label: '板块同步性增强' },
      leadership: {
        leadershipConcentrationPercent: 36,
        broadParticipationPercent: 64,
        topMembers: [
          { symbol: 'APP', name: 'APP', changePercent: 5.1, relativeStrengthVsBenchmark: 4.3, volumeRatio: 2.2, freshness: 'delayed', isFallback: false },
          { symbol: 'PLTR', name: 'PLTR', changePercent: 4.6, relativeStrengthVsBenchmark: 3.8, volumeRatio: 2.0, freshness: 'delayed', isFallback: false },
        ],
      },
      themeDetail: {
        watchlistLabel: '观察清单证据',
        watchlistSafe: true,
        safeActionLabel: '仅观察，不构成买卖建议',
        leaderSectionLabel: '领先成员',
        laggardSectionLabel: '落后/待验证成员',
        leaderExplanation: '领先成员按相对强弱和量能扩张排序，仅代表观察信号强弱。',
        laggardExplanation: '落后/待验证成员用于观察扩散不足或分歧，不是买卖建议。',
        leadershipMembers: [
          { symbol: 'APP', name: 'APP', role: 'leader', roleLabel: '领先成员', changePercent: 5.1, relativeStrengthVsBenchmark: 4.3, freshness: 'delayed', freshnessLabel: '延迟', observed: true },
        ],
        laggardMembers: [
          { symbol: 'CRM', name: 'CRM', role: 'laggard', roleLabel: '落后成员', changePercent: 2.8, relativeStrengthVsBenchmark: 2.0, freshness: 'delayed', freshnessLabel: '延迟', observed: true },
        ],
        memberEvidence: [],
        freshnessLabel: '延迟',
        asOf: '2026-05-07T09:45:00Z',
        disclosure: '仅用于观察资金轮动迹象，非买卖建议。',
      },
      freshness: 'delayed',
      isFallback: false,
      isStale: false,
      source: 'computed',
      sourceLabel: '主题篮子计算',
      asOf: '2026-05-07T09:45:00Z',
      updatedAt: '2026-05-07T09:50:00Z',
      evidence: ['无明显新闻的同步异动', '成交额扩张迹象', '相对 QQQ 强弱 +2.80%'],
      members: [],
      noAdviceDisclosure: '仅用于观察资金轮动迹象，非买卖建议。',
    },
  ],
});

const themeNames = [
  'AI 应用',
  '半导体',
  '半导体设备',
  '网络安全',
  '云软件',
  '数据中心电力',
  '液冷散热',
  '机器人',
  '工业自动化',
  '国防航天',
  '医疗生物科技',
  '金融科技',
  '消费者互联网',
  '能源',
];

const marketThemeNames: Record<string, string[]> = {
  CN: ['AI算力', 'AI基建 / 液冷散热', '光模块 / CPO', '半导体设备', '国产芯片', '机器人', '低空经济', '新能源车链', '创新药', '证券金融'],
  HK: ['港股科技', '互联网平台', '港股生物科技', '新能源汽车', '金融保险', '能源资源', '消费服务', '高股息红利'],
  CRYPTO: ['Layer 1', 'Layer 2', 'DeFi', 'AI Crypto', 'Exchange / Platform', 'Stablecoin Infrastructure', 'Bitcoin Ecosystem', 'DePIN'],
};

function radarUniverseFixture(): MarketRotationRadarResponse {
  const fixture = radarFixture();
  const baseTheme = fixture.themes[0];
  const themes = themeNames.map((name, index) => {
    const score = 88 - index * 4;
    const isWeak = score < 56;
    const leaderSymbol = name === '机器人' ? 'BOTZ' : index === 0 ? 'APP' : `US${index}`;
    return {
      ...baseTheme,
      id: index === 0 ? 'ai_applications' : `theme_${index}`,
      name,
      englishName: name === '机器人' ? 'Robotics' : `${name} Cluster`,
      rotationScore: score,
      confidence: Math.max(0.18, 0.84 - index * 0.05),
      stage: isWeak ? 'weak_or_no_signal' : index > 7 ? 'cooling_watch' : baseTheme.stage,
      stageExplanation: `${name} 当前以相对强弱、成交额扩张、广度和同步性作为观察依据。`,
      focus: `${name} 代表性成员与代理观察`,
      riskLabels: isWeak ? ['thin_breadth'] : index % 3 === 0 ? ['gap_fade_risk'] : [],
      riskExplanations: isWeak ? ['广度偏薄，暂不放大解释。'] : [],
      relativeStrength: {
        ...baseTheme.relativeStrength,
        averageRelativeStrengthPercent: 3.8 - index * 0.35,
      },
      volume: {
        ...baseTheme.volume,
        averageRelativeVolume: Math.max(0.75, 1.9 - index * 0.08),
      },
      breadth: {
        ...baseTheme.breadth,
        percentUp: Math.max(25, 96 - index * 5),
        percentOutperformingBenchmark: Math.max(20, 92 - index * 5),
      },
      synchronization: {
        ...baseTheme.synchronization,
        sameDirectionPercent: Math.max(20, 94 - index * 6),
      },
      leadership: {
        ...baseTheme.leadership,
        leadershipConcentrationPercent: Math.min(78, 28 + index * 4),
        broadParticipationPercent: Math.max(18, 76 - index * 4),
        topMembers: [
          { symbol: leaderSymbol, name: leaderSymbol, changePercent: 5.1 - index * 0.2, relativeStrengthVsBenchmark: 4.3 - index * 0.2, volumeRatio: 2.2, freshness: 'delayed', isFallback: false },
        ],
      },
      evidence: [`${name} 观察证据`, '成交额扩张迹象'],
      alertCandidates: index < 2 ? [
        {
          ...baseTheme.alertCandidates?.[0],
          themeId: index === 0 ? 'ai_applications' : `theme_${index}`,
          themeName: name,
          symbol: index === 0 ? 'APP' : 'BOTZ',
          label: '关注候选',
          signalLabel: isWeak ? '信号较弱' : '确认轮动',
        },
      ] : [],
    };
  });
  fixture.themes = themes;
  fixture.summary = {
    ...fixture.summary,
    strongestThemes: themes.slice(0, 3),
    acceleratingThemes: themes.slice(0, 2),
    fadingThemes: themes.slice(-3),
    watchlistSignals: [
      { themeId: 'ai_applications', themeName: 'AI 应用', symbol: 'APP', label: '关注候选', signal: 'confirmed_rotation', signalLabel: '确认轮动', confidence: 0.84, readOnly: true, deliveryEnabled: false },
      { themeId: 'theme_7', themeName: '机器人', symbol: 'BOTZ', label: '关注候选', signal: 'confirmed_rotation', signalLabel: '确认轮动', confidence: 0.79, readOnly: true, deliveryEnabled: false },
    ],
  };
  return fixture;
}

function taxonomyMarketFixture(market: 'CN' | 'HK' | 'CRYPTO'): MarketRotationRadarResponse {
  const fixture = radarFixture();
  const names = marketThemeNames[market];
  fixture.market = market;
  fixture.source = 'local_taxonomy';
  fixture.sourceLabel = '静态主题库';
  fixture.freshness = 'fallback';
  fixture.isFallback = true;
  fixture.warning = '当前为静态主题库，本地行情覆盖后可计算轮动强度。不代表实时买卖信号。';
  fixture.metadata = {
    ...fixture.metadata,
    taxonomyOnlyThemeCount: names.length,
  };
  const baseTheme = fixture.themes[0];
  fixture.themes = names.map((name, index) => ({
    ...baseTheme,
    id: `${market}:theme_cluster:${index}`,
    market,
    name,
    englishName: market === 'CRYPTO' ? `${name} Theme` : `${name} Cluster`,
    focus: `${name} 静态主题分类观察`,
    benchmark: `${market}_LOCAL_TAXONOMY`,
    sectorBenchmark: null,
    membersConfigured: market === 'CN' ? ['寒武纪', '中科曙光', '工业富联'] : market === 'HK' ? ['0700.HK', '9988.HK'] : ['BTC', 'ETH'],
    rotationScore: 18,
    confidence: 0.12,
    confidenceLabel: '待行情确认',
    dataQuality: 'taxonomy_only',
    dataCoverage: 'taxonomy_only',
    staticThemeOnly: true,
    taxonomyType: 'theme_cluster',
    stage: 'weak_or_no_signal',
    stageExplanation: '主题库已载入，行情评分待本地数据覆盖，仅作分类观察。',
    riskLabels: ['stale_or_incomplete_windows'],
    riskExplanations: ['行情评分待本地数据覆盖。'],
    newslessRotation: false,
    alertCandidates: [],
    relativeStrength: {},
    benchmarkProxies: {},
    proxyQuality: { label: '静态主题库', coveragePercent: 0, availableProxyCount: 0, totalProxyCount: 0 },
    timeWindows: {},
    volume: { averageRelativeVolume: null, availableMemberCount: 0, label: '待接入本地行情' },
    breadth: { observedMembers: 0, configuredMembers: 0, coveragePercent: 0, percentUp: null, percentOutperformingBenchmark: null },
    synchronization: { sameDirectionPercent: null, aboveVwapPercent: null, persistencePercent: null, label: '分类观察' },
    leadership: { leadershipConcentrationPercent: null, broadParticipationPercent: null, topMembers: [] },
    themeDetail: {
      watchlistSafe: true,
      safeActionLabel: '仅观察，不构成买卖建议',
      mappedConcepts: names.slice(0, 3),
      representativeLabels: market === 'CN' ? ['寒武纪', '中科曙光'] : market === 'HK' ? ['0700.HK', '9988.HK'] : ['BTC', 'ETH'],
      dataStateLabel: '待接入本地行情',
      nextStep: '本地行情覆盖后可计算轮动强度。',
      disclosure: '仅用于观察资金轮动迹象，非买卖建议。',
    },
    freshness: 'fallback',
    isFallback: true,
    source: 'local_taxonomy',
    sourceLabel: '静态主题库',
    evidence: ['主题库已载入', '行情评分待本地数据覆盖', '仅作分类观察'],
    members: [],
  }));
  fixture.summary = {
    ...fixture.summary,
    strongestThemes: [],
    acceleratingThemes: [],
    fadingThemes: [],
    watchlistSignals: [],
  };
  return fixture;
}

describe('MarketRotationRadarPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(marketRotationApi.getRotationRadar).mockImplementation((market?: string) => {
      if (market === 'CN' || market === 'HK' || market === 'CRYPTO') {
        return Promise.resolve(taxonomyMarketFixture(market));
      }
      return Promise.resolve(radarUniverseFixture());
    });
  });

  it('renders a compact top-N radar instead of a full theme card wall by default', async () => {
    render(<MarketRotationRadarPage />);

    const page = await screen.findByTestId('market-rotation-radar-page');
    expect(page).toHaveTextContent('资金轮动雷达');
    expect(screen.getByTestId('rotation-radar-summary-band')).toHaveTextContent('Top-N');
    expect(screen.getByTestId('rotation-radar-mode-controls')).toHaveTextContent('US');
    expect(screen.getByTestId('rotation-market-tab-US')).toHaveAttribute('aria-pressed', 'true');

    const leaderList = screen.getByTestId('rotation-radar-leader-list');
    expect(within(leaderList).getAllByTestId(/rotation-radar-leader-row-/)).toHaveLength(10);
    expect(within(leaderList).getByText('AI 应用')).toBeInTheDocument();
    expect(within(leaderList).queryByText('AI算力')).not.toBeInTheDocument();
    expect(within(leaderList).queryByText('Layer 1')).not.toBeInTheDocument();
    expect(screen.queryByTestId('rotation-theme-card-ai_applications')).not.toBeInTheDocument();
    expect(screen.queryByText('下一观察：')).not.toBeInTheDocument();

    expect(screen.getByTestId('rotation-theme-detail-panel')).toHaveTextContent('AI 应用');
    expect(screen.getByTestId('rotation-radar-universe-list')).toHaveTextContent('完整主题库');
    expect(screen.getByPlaceholderText('搜索主题、英文名或成员')).toBeInTheDocument();

    const bodyText = page.textContent?.toLowerCase() || '';
    expect(bodyText).not.toMatch(/raw_payload|provider_payload|api_key|password|session_id|cookie|secret/);
    expect(bodyText).not.toMatch(forbiddenTradingActionPattern);
  });

  it('switches market tabs to populated CN HK and Crypto taxonomy universes', async () => {
    render(<MarketRotationRadarPage />);

    await screen.findByTestId('market-rotation-radar-page');
    fireEvent.click(screen.getByTestId('rotation-market-tab-CN'));

    await waitFor(() => expect(marketRotationApi.getRotationRadar).toHaveBeenLastCalledWith('CN'));
    expect(screen.getByTestId('rotation-market-tab-CN')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('rotation-radar-leader-list')).toHaveTextContent('AI算力');
    expect(screen.getByTestId('rotation-radar-leader-list')).toHaveTextContent('待行情确认');
    expect(screen.getByTestId('rotation-theme-detail-panel')).toHaveTextContent('主题库已载入');
    expect(screen.getByTestId('rotation-theme-detail-panel')).toHaveTextContent('待接入本地行情');
    expect(screen.getByTestId('rotation-theme-detail-panel')).toHaveTextContent('寒武纪');
    expect(document.body.textContent || '').not.toMatch(/\bN\/A\b/g);

    fireEvent.click(screen.getByTestId('rotation-market-tab-HK'));
    await waitFor(() => expect(marketRotationApi.getRotationRadar).toHaveBeenLastCalledWith('HK'));
    expect(screen.getByTestId('rotation-radar-leader-list')).toHaveTextContent('港股科技');

    fireEvent.click(screen.getByTestId('rotation-market-tab-CRYPTO'));
    await waitFor(() => expect(marketRotationApi.getRotationRadar).toHaveBeenLastCalledWith('CRYPTO'));
    expect(screen.getByTestId('rotation-radar-leader-list')).toHaveTextContent('Layer 1');
    expect(screen.getByTestId('rotation-radar-universe-list')).toHaveTextContent('DeFi');
  });

  it('updates the single selected detail panel when a leader row is selected', async () => {
    render(<MarketRotationRadarPage />);

    await screen.findByTestId('market-rotation-radar-page');
    expect(screen.getByTestId('rotation-theme-detail-panel')).toHaveTextContent('AI 应用');

    fireEvent.click(screen.getByTestId('rotation-radar-leader-row-theme_7'));

    const detail = screen.getByTestId('rotation-theme-detail-panel');
    expect(detail).toHaveTextContent('机器人');
    expect(detail).toHaveTextContent('Robotics');
    expect(detail).toHaveTextContent('BOTZ');
    expect(detail).not.toHaveTextContent('AI 应用 当前以相对强弱');
  });

  it('keeps the full universe compact and searchable without noisy cards', async () => {
    render(<MarketRotationRadarPage />);

    await screen.findByTestId('market-rotation-radar-page');
    fireEvent.change(screen.getByPlaceholderText('搜索主题、英文名或成员'), { target: { value: '能源' } });

    const universe = screen.getByTestId('rotation-radar-universe-list');
    expect(universe).toHaveTextContent('能源');
    expect(universe).not.toHaveTextContent('半导体');
    expect(screen.queryByTestId('rotation-theme-card-theme_11')).not.toBeInTheDocument();
  });

  it('marks fallback radar data as fallback instead of live', async () => {
    vi.mocked(marketRotationApi.getRotationRadar).mockResolvedValueOnce({
      ...radarFixture(),
      source: 'fallback',
      sourceLabel: '备用数据',
      freshness: 'fallback',
      isFallback: true,
      warning: '未配置实时 quote provider，返回降级主题篮子。',
      summary: {
        strongestThemes: [],
        acceleratingThemes: [],
        fadingThemes: [],
        safeWording: ['资金轮动迹象', '非买卖建议'],
      },
      themes: [
        {
          ...radarFixture().themes[0],
          rotationScore: 34,
          confidence: 0.12,
          stage: 'weak_or_no_signal',
          freshness: 'fallback',
          isFallback: true,
          riskLabels: ['stale_or_incomplete_windows', 'thin_breadth'],
          alertCandidates: [],
          newslessRotation: false,
          evidence: ['静态主题篮子示例，未接入行情快照。'],
        },
      ],
    });

    render(<MarketRotationRadarPage />);

    await waitFor(() => expect(screen.getByTestId('rotation-radar-freshness')).toHaveTextContent('备用'));
    expect(screen.getByTestId('rotation-radar-leader-row-ai_applications')).toHaveTextContent('信号较弱');
    expect(screen.getByTestId('rotation-radar-leader-row-ai_applications')).toHaveTextContent('备用');
    expect(screen.getByTestId('rotation-radar-leader-row-ai_applications')).not.toHaveTextContent('实时');
  });

  it('keeps proxy diagnostics user-facing and omits developer diagnostics by default', async () => {
    const fixture = radarFixture();
    fixture.warning = 'provider_timeout';
    fixture.metadata = {
      ...fixture.metadata,
      raw_payload: { provider_payload: true, debug: true },
    };
    fixture.themes[0] = {
      ...fixture.themes[0],
      stageExplanation: 'not_enough_history',
      evidence: ['technical_indicators_unavailable'],
      riskExplanations: ['fundamentals_unavailable'],
      proxyQuality: {
        ...fixture.themes[0].proxyQuality,
        label: 'ETF 代理部分可用',
        coveragePercent: 50,
        availableProxyCount: 2,
        totalProxyCount: 4,
        freshness: 'stale',
        hasMissingRequiredProxy: true,
        hasStaleProxy: true,
        missingReasons: {
          IWM: 'proxy_stale',
          IGV: 'proxy_quote_missing',
        },
        explanation: 'ETF 代理部分可用：ETF 代理覆盖 2/4，缺口 IWM/IGV。',
      },
      benchmarkProxies: {
        ...fixture.themes[0].benchmarkProxies,
        IWM: {
          ...fixture.themes[0].benchmarkProxies?.IWM,
          symbol: 'IWM',
          freshness: 'stale',
          isStale: true,
          quality: {
            available: false,
            freshness: 'stale',
            missingReason: 'proxy_stale',
            qualityLabel: '代理过期',
            coverageContribution: 0,
          },
        },
        IGV: {
          ...fixture.themes[0].benchmarkProxies?.IGV,
          symbol: 'IGV',
          freshness: 'fallback',
          isFallback: true,
          quality: {
            available: false,
            freshness: 'fallback',
            missingReason: 'proxy_quote_missing',
            qualityLabel: '代理缺口',
            coverageContribution: 0,
          },
        },
      },
    };
    vi.mocked(marketRotationApi.getRotationRadar).mockResolvedValueOnce(fixture);

    render(<MarketRotationRadarPage />);

    const detail = await screen.findByTestId('rotation-theme-detail-panel');
    const quality = within(detail).getByTestId('rotation-proxy-quality-summary-ai_applications');
    expect(quality).toHaveTextContent('覆盖 2/4');
    expect(quality).toHaveTextContent('50.0%');
    expect(quality).toHaveTextContent('过期');
    expect(quality).toHaveTextContent('代理缺口');

    expect(screen.queryByTestId('rotation-proxy-row-IWM')).not.toBeInTheDocument();
    expect(screen.queryByText('schemaVersion')).not.toBeInTheDocument();
    expect(screen.queryByText('/api/v1/market/rotation-radar')).not.toBeInTheDocument();
    expect(screen.queryByText('proxy_quote_missing')).not.toBeInTheDocument();
    expect(screen.queryByText('proxy_stale')).not.toBeInTheDocument();
    expect(screen.getByText('部分外部数据暂不可用')).toBeInTheDocument();
    expect(document.body.textContent || '').toMatch(/历史数据不足|技术指标数据不足|基本面数据缺失/);

    const proxyDetails = within(detail).getByTestId('rotation-theme-proxy-details-ai_applications');
    expect(proxyDetails).not.toHaveAttribute('open');
    expect(screen.queryByTestId('rotation-radar-developer-details')).not.toBeInTheDocument();
    expect(document.body.textContent || '').not.toMatch(/开发者|Developer|schemaVersion|provider_payload|raw_payload|debug|trace/i);
  });

  it('renders derived rotation buckets and collapsed page mechanics', async () => {
    render(<MarketRotationRadarPage />);

    await screen.findByTestId('market-rotation-radar-page');
    const buckets = screen.getByTestId('rotation-radar-buckets');
    expect(buckets).toHaveTextContent('新近走强');
    expect(buckets).toHaveTextContent('走弱降温');
    expect(buckets).toHaveTextContent('广泛参与');
    expect(buckets).toHaveTextContent('窄幅龙头');

    const mechanics = screen.getByTestId('rotation-radar-mechanics-details');
    expect(mechanics).toHaveTextContent('数据说明');
    expect(mechanics).not.toHaveTextContent('schemaVersion');
  });
});
