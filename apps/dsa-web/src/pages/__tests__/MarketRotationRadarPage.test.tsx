import { render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import MarketRotationRadarPage from '../MarketRotationRadarPage';
import { marketRotationApi } from '../../api/marketRotation';
import type { MarketRotationRadarResponse } from '../../api/marketRotation';

vi.mock('../../api/marketRotation', () => ({
  marketRotationApi: {
    getRotationRadar: vi.fn(),
  },
}));

const radarFixture = (): MarketRotationRadarResponse => ({
  endpoint: '/api/v1/market/rotation-radar',
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
    schemaVersion: 'market_rotation_radar_mvp_v1',
  },
  benchmarks: {
    QQQ: { symbol: 'QQQ', changePercent: 0.8, freshness: 'delayed', isFallback: false, isStale: false },
    SPY: { symbol: 'SPY', changePercent: 0.4, freshness: 'delayed', isFallback: false, isStale: false },
    IWM: { symbol: 'IWM', changePercent: 0.1, freshness: 'delayed', isFallback: false, isStale: false },
  },
  summary: {
    strongestThemes: [
      { id: 'ai_applications', name: 'AI 应用', rotationScore: 78, confidence: 0.72, stage: 'confirmed_rotation', freshness: 'delayed', isFallback: false, riskLabels: [] },
    ],
    acceleratingThemes: [
      { id: 'ai_applications', name: 'AI 应用', rotationScore: 78, confidence: 0.72, stage: 'confirmed_rotation', freshness: 'delayed', isFallback: false, riskLabels: [] },
    ],
    fadingThemes: [
      { id: 'robotics', name: '机器人', rotationScore: 38, confidence: 0.31, stage: 'weak_or_no_signal', freshness: 'fallback', isFallback: true, riskLabels: ['fallback_data'] },
    ],
    safeWording: ['资金轮动迹象', '成交额扩张', '相对强势扩散', '板块同步性增强', '非买卖建议'],
  },
  themes: [
    {
      id: 'ai_applications',
      name: 'AI 应用',
      englishName: 'AI Applications',
      focus: '应用层软件、数据工作流与企业 AI 落地',
      benchmark: 'QQQ',
      membersConfigured: ['APP', 'PLTR', 'CRM'],
      rotationScore: 78,
      confidence: 0.72,
      stage: 'confirmed_rotation',
      riskLabels: ['gap_fade_risk'],
      newslessRotation: true,
      newslessRotationEvidence: '无明显新闻的同步异动：未配置新闻催化证据。',
      relativeStrength: {
        benchmark: 'QQQ',
        benchmarkChangePercent: 0.8,
        averageThemeChangePercent: 3.6,
        averageRelativeStrengthPercent: 2.8,
        vsBenchmarks: { QQQ: 2.8, SPY: 3.2, IWM: 3.5 },
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

describe('MarketRotationRadarPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(marketRotationApi.getRotationRadar).mockResolvedValue(radarFixture());
  });

  it('renders safe Chinese rotation labels, freshness disclosure, and collapsed developer details', async () => {
    render(<MarketRotationRadarPage />);

    const page = await screen.findByTestId('market-rotation-radar-page');
    expect(page).toHaveTextContent('资金轮动雷达');
    expect(page).toHaveTextContent('今日轮动主题');
    expect(page).toHaveTextContent('轮动强度');
    expect(page).toHaveTextContent('相对强弱');
    expect(page).toHaveTextContent('成交额扩张');
    expect(page).toHaveTextContent('上涨广度');
    expect(page).toHaveTextContent('同步性');
    expect(page).toHaveTextContent('主导股票');
    expect(page).toHaveTextContent('风险标签');
    expect(page).toHaveTextContent('数据新鲜度');
    expect(page).toHaveTextContent('非买卖建议');

    const themeCard = screen.getByTestId('rotation-theme-card-ai_applications');
    expect(within(themeCard).getByText('AI 应用')).toBeInTheDocument();
    expect(within(themeCard).getByText('78')).toBeInTheDocument();
    expect(within(themeCard).getByText('无明显新闻的同步异动')).toBeInTheDocument();
    expect(within(themeCard).getByText('高开回落风险')).toBeInTheDocument();
    expect(screen.getByTestId('rotation-radar-developer-details')).not.toHaveAttribute('open');

    const bodyText = page.textContent?.toLowerCase() || '';
    expect(bodyText).not.toMatch(/raw_payload|provider_payload|api_key|password|session_id|cookie|secret/);
    expect(bodyText).not.toMatch(/建议买入|必买|稳赚|下单|buy now|sell now|guaranteed|best contract/i);
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
          riskLabels: ['fallback_data', 'thin_breadth'],
          newslessRotation: false,
          evidence: ['静态主题篮子示例，未接入行情快照。'],
        },
      ],
    });

    render(<MarketRotationRadarPage />);

    await waitFor(() => expect(screen.getByTestId('rotation-radar-freshness')).toHaveTextContent('备用'));
    expect(screen.getByTestId('rotation-theme-card-ai_applications')).toHaveTextContent('信号较弱');
    expect(screen.getByTestId('rotation-theme-card-ai_applications')).toHaveTextContent('备用数据');
    expect(screen.getByTestId('rotation-theme-card-ai_applications')).not.toHaveTextContent('实时');
  });
});
