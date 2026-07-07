import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { UiPreferencesProvider } from '../../contexts/UiPreferencesContext';
import GuestHomePage from '../GuestHomePage';

const { previewMock, marketBriefingMock, languageState, useAuthMock } = vi.hoisted(() => ({
  previewMock: vi.fn(),
  marketBriefingMock: vi.fn(),
  languageState: { value: 'zh' as 'zh' | 'en' },
  useAuthMock: vi.fn(),
}));

vi.mock('../../api/publicAnalysis', () => ({
  publicAnalysisApi: {
    preview: (...args: unknown[]) => previewMock(...args),
  },
}));

vi.mock('../../api/market', () => ({
  marketApi: {
    getMarketBriefing: (...args: unknown[]) => marketBriefingMock(...args),
  },
  normalizeMarketBriefingConsumerCopy: <T,>(value: T) => value,
}));

vi.mock('../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: languageState.value,
    t: (key: string) => key,
  }),
}));

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock('../../hooks/useTaskStream', () => ({
  useTaskStream: vi.fn(() => ({
    isConnected: false,
    reconnect: vi.fn(),
    disconnect: vi.fn(),
  })),
}));

const GUEST_PREVIEW_FAILURE_FORBIDDEN_COPY_PATTERN =
  /\b(buy|sell|hold|target price|stop loss|position sizing|recommendation|action grade|local research snapshot|local snapshot|leadership trend|momentum still driving|high-volatility|trend up|constructive consolidation|conviction|score)\b|买入|卖出|持有|目标价|止损|仓位建议|推荐|本地研究快照|本地快照|趋势上行|偏强震荡|高波动震荡|置信度|评分/i;

const renderGuest = (initialEntries = ['/guest']) => render(
  <MemoryRouter initialEntries={initialEntries}>
    <UiPreferencesProvider>
      <GuestHomePage />
    </UiPreferencesProvider>
  </MemoryRouter>,
);

describe('GuestHomePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    languageState.value = 'zh';
    marketBriefingMock.mockResolvedValue({
      source: 'computed',
      sourceLabel: '公开市场摘要',
      updatedAt: '2026-06-08T08:00:00Z',
      asOf: '2026-06-08T08:00:00Z',
      freshness: 'fresh',
      isFallback: false,
      isReliable: true,
      items: [
        {
          title: '市场广度改善',
          message: '主要宽度与资金线索继续支持观察。',
          severity: 'positive',
          category: 'risk',
          confidence: 0.8,
        },
        {
          title: '流动性保持稳定',
          message: '当前更适合先看结构，再决定是否继续深入。',
          severity: 'neutral',
          category: 'liquidity',
          confidence: 0.72,
        },
      ],
    });
    useAuthMock.mockReturnValue({
      loggedIn: false,
      isLoading: false,
    });
    window.history.replaceState(window.history.state, '', '/zh');
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders a compact guest research console before search and reveals the paywalled preview after submit', async () => {
    previewMock.mockResolvedValue({
      queryId: 'preview-q1',
      stockCode: 'AAPL',
      stockName: 'Apple',
      previewScope: 'guest',
      report: {
        meta: {
          queryId: 'preview-q1',
          stockCode: 'AAPL',
          stockName: 'Apple',
          reportType: 'brief',
          createdAt: '2026-04-14T10:00:00Z',
        },
        summary: {
          analysisSummary: '趋势延续但需要等待更好的介入点。',
          operationAdvice: '等待回踩',
          trendPrediction: '偏强震荡',
          sentimentScore: 72,
        },
      },
    });

    renderGuest();

    const guestFirstScreen = screen.getByTestId('guest-home-clean-search');
    const commandSurface = screen.getByTestId('guest-home-command-surface');
    const marketPreviewStrip = await screen.findByTestId('guest-home-market-preview-strip');
    const trustStrip = screen.getByTestId('guest-home-trust-strip');
    const previewStrip = screen.getByTestId('guest-home-preview-strip');

    expect(screen.getByTestId('home-bento-dashboard')).toBeInTheDocument();
    expect(guestFirstScreen).toBeInTheDocument();
    expect(screen.queryByTestId('home-research-console')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'WolfyStock 研究控制台' })).toBeInTheDocument();
    expect(commandSurface).toHaveAttribute('data-visual-role', 'guest-command-console');
    expect(screen.getByTestId('guest-home-command-workflow')).toHaveTextContent('搜索');
    expect(screen.getByTestId('guest-home-command-workflow')).toHaveTextContent('分析');
    expect(screen.getByTestId('guest-home-command-workflow')).toHaveTextContent('观察');
    expect(screen.getByTestId('guest-home-command-workflow')).toHaveTextContent('报告');
    expect(screen.getByTestId('home-bento-omnibar')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '分析' })).toBeEnabled();
    expect(screen.getByText('WolfyStock 是面向独立研究者与自驱投资者的股票研究工作区。你可以先查看单个标的预览，登录后再保存报告、回看历史，并继续进入组合或扫描工作台。')).toBeInTheDocument();
    expect(marketPreviewStrip).toHaveTextContent('当前市场观察');
    expect(marketPreviewStrip).toHaveTextContent('公开市场观察已准备');
    expect(marketPreviewStrip).toHaveTextContent('市场广度改善');
    expect(marketPreviewStrip).toHaveTextContent('研究观察，不构成投资建议。');
    expect(screen.getByTestId('guest-home-registration-link')).toHaveAttribute('href', '/zh/register?redirect=%2Fzh');
    expect(trustStrip).toHaveTextContent('安全下一步');
    expect(trustStrip).toHaveTextContent('先查看单个代码的研究入口');
    expect(previewStrip).toHaveTextContent('登录后可用');
    expect(previewStrip).toHaveTextContent('回到上次研究现场');
    expect(screen.queryByTestId('guest-home-frosted-lock')).not.toBeInTheDocument();
    expect(guestFirstScreen).not.toHaveTextContent('WolfyStock 分析面板');
    expect(guestFirstScreen).not.toHaveTextContent('输入股票代码，搜索后生成 AI 分析面板。');
    expect(guestFirstScreen).not.toHaveTextContent(/买入|卖出|推荐|目标价|止损/);
    expect(guestFirstScreen).not.toHaveTextContent(/\bNVDA\b|NVIDIA|TSLA|Tesla/i);

    fireEvent.change(screen.getByTestId('home-bento-omnibar-input'), { target: { value: 'AAPL' } });
    fireEvent.submit(screen.getByTestId('home-bento-omnibar'));

    await waitFor(() => {
      expect(previewMock).toHaveBeenCalledWith({
        stockCode: 'AAPL',
        stockName: undefined,
        reportType: 'brief',
      });
    });

    expect(await screen.findByTestId('home-research-console')).toBeInTheDocument();
    expect(screen.queryByTestId('guest-home-clean-search')).not.toBeInTheDocument();
    expect(screen.getByText('Apple Inc.')).toBeInTheDocument();
    expect(screen.getByTestId('home-research-score-strip')).toHaveTextContent('7.2');
    expect(screen.queryByTestId('home-bento-decision-score-value')).not.toBeInTheDocument();
    expect(screen.getAllByText('趋势延续但需要等待更好的介入点。').length).toBeGreaterThan(0);
    expect(screen.getAllByTestId('guest-home-frosted-lock')).toHaveLength(2);
    expect(screen.getAllByText('解锁完整研究框架、价格观察与技术形态解读')).toHaveLength(2);
    expect(screen.getAllByRole('link', { name: '免费创建账户' })).toHaveLength(2);
    expect(screen.getByTestId('home-research-context-rail')).toContainElement(screen.getAllByTestId('guest-home-frosted-lock')[1]);
    expect(screen.queryByTestId('guest-preview-unavailable-state')).not.toBeInTheDocument();
    expect(screen.queryByText(/local research snapshot|本地研究快照/i)).not.toBeInTheDocument();
  });

  it('renders the English clean search funnel copy', async () => {
    languageState.value = 'en';
    window.history.replaceState(window.history.state, '', '/en');

    renderGuest(['/en/guest']);

    expect(screen.getByRole('heading', { name: 'WolfyStock Research Console' })).toBeInTheDocument();
    expect(screen.getByText('WolfyStock is a stock research workspace for self-directed investors and research-oriented users. Start with one ticker preview now, then sign in to save reports, reopen history, and continue into portfolio or scanner workflows.')).toBeInTheDocument();
    expect(await screen.findByText('Public market observation ready')).toBeInTheDocument();
    expect(screen.getByTestId('guest-home-market-preview-strip')).toHaveTextContent('Current market observation');
    expect(screen.getByTestId('guest-home-trust-strip')).toHaveTextContent('Safe next step');
    expect(screen.getByRole('button', { name: 'Analyze' })).toBeInTheDocument();
    expect(screen.queryByTestId('home-research-console')).not.toBeInTheDocument();
  });

  it('keeps the guest first screen populated at 375px mobile width', async () => {
    window.innerWidth = 375;
    window.dispatchEvent(new Event('resize'));

    renderGuest();

    const firstScreen = screen.getByTestId('guest-home-clean-search');
    const commandSurface = screen.getByTestId('guest-home-command-surface');

    expect(firstScreen).toBeInTheDocument();
    expect(commandSurface).toHaveAttribute('data-visual-role', 'guest-command-console');
    expect(screen.getByRole('heading', { name: 'WolfyStock 研究控制台' })).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-omnibar-input')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '分析' })).toBeEnabled();
    expect(screen.getByTestId('guest-home-registration-link')).toHaveAttribute('href', '/zh/register?redirect=%2Fzh');
    expect(await screen.findByTestId('guest-home-market-preview-strip')).toHaveTextContent('研究观察，不构成投资建议。');
    expect(firstScreen.textContent?.trim().length).toBeGreaterThan(80);
    expect(firstScreen).not.toHaveTextContent(/^\s*$/);
  });

  it('keeps guest mobile entry actions wrap-safe instead of clipping the first screen at 375px', async () => {
    window.innerWidth = 375;
    window.dispatchEvent(new Event('resize'));

    renderGuest();

    const firstScreen = screen.getByTestId('guest-home-clean-search');
    const firstScreenStack = screen.getByTestId('guest-home-first-screen-stack');
    const commandSurface = screen.getByTestId('guest-home-command-surface');
    const marketPreviewStrip = await screen.findByTestId('guest-home-market-preview-strip');
    const registrationLink = screen.getByTestId('guest-home-registration-link');

    expect(firstScreen).toHaveClass('overflow-x-hidden');
    expect(firstScreenStack).toHaveClass('overflow-x-hidden');
    expect(commandSurface).toHaveClass('overflow-x-hidden');
    expect(marketPreviewStrip).toHaveClass('min-w-0');
    expect(registrationLink).toHaveClass('w-full', 'sm:w-auto');
  });

  it('shows an honest unavailable state when the market briefing cannot be loaded', async () => {
    languageState.value = 'en';
    window.history.replaceState(window.history.state, '', '/en');
    marketBriefingMock.mockRejectedValueOnce(new Error('market briefing unavailable'));

    renderGuest(['/en/guest']);

    const marketPreviewStrip = await screen.findByTestId('guest-home-market-preview-strip');
    await waitFor(() => {
      expect(marketPreviewStrip).toHaveTextContent('Public market observation unavailable right now');
    });

    expect(marketPreviewStrip).toHaveTextContent('Current market observation');
    expect(marketPreviewStrip).toHaveTextContent('Public market observation unavailable right now');
    expect(marketPreviewStrip).toHaveTextContent('Sign in to open Market Overview, Scanner, and saved research history once the public snapshot comes back.');
    expect(marketPreviewStrip).not.toHaveTextContent('Preparing public market observation');
    expect(marketPreviewStrip).not.toHaveTextContent('Loading a limited market snapshot using public-safe fields only');
    expect(marketPreviewStrip).not.toHaveTextContent(/\bNVDA\b|NVIDIA|TSLA|Tesla|AAPL|Apple/i);
  });

  it('shows bounded preview-unavailable copy when the live preview API rate-limits', async () => {
    languageState.value = 'en';
    window.history.replaceState(window.history.state, '', '/en');
    previewMock.mockRejectedValueOnce(new Error('429 RateLimitError: upstream overloaded'));

    renderGuest(['/en/guest']);

    fireEvent.change(screen.getByTestId('home-bento-omnibar-input'), { target: { value: 'NVDA' } });
    fireEvent.click(screen.getByRole('button', { name: 'Analyze' }));

    const unavailable = await screen.findByTestId('guest-preview-unavailable-state');
    expect(unavailable).toHaveTextContent('Public preview is temporarily unavailable');
    expect(unavailable).toHaveTextContent('No public research preview is available right now. Try again later, or sign in to continue with saved research workflows.');
    expect(screen.getByTestId('guest-home-clean-search')).toBeInTheDocument();
    expect(screen.queryByTestId('home-research-console')).not.toBeInTheDocument();
    expect(screen.queryByText('NVIDIA Corporation')).not.toBeInTheDocument();
    expect(screen.queryByText('The local snapshot keeps the leadership trend intact, with momentum still driving the short-term structure.')).not.toBeInTheDocument();
    expect(screen.queryByTestId('home-research-score-strip')).not.toBeInTheDocument();
    expect((screen.getByTestId('guest-home-clean-search').textContent || '')).not.toMatch(GUEST_PREVIEW_FAILURE_FORBIDDEN_COPY_PATTERN);
  });

  it('keeps the guest shell in a preview-unavailable state when the preview request never settles', async () => {
    languageState.value = 'en';
    window.history.replaceState(window.history.state, '', '/en');
    previewMock.mockImplementation(() => new Promise(() => {}));
    vi.useFakeTimers();

    try {
      renderGuest(['/en/guest']);

      fireEvent.change(screen.getByTestId('home-bento-omnibar-input'), { target: { value: 'TSLA' } });
      fireEvent.click(screen.getByRole('button', { name: 'Analyze' }));

      await act(async () => {
        await vi.advanceTimersByTimeAsync(4_100);
        await Promise.resolve();
      });

      const unavailable = screen.getByTestId('guest-preview-unavailable-state');
      expect(unavailable).toHaveTextContent('Public preview is temporarily unavailable');
      expect(screen.getByTestId('guest-home-clean-search')).toBeInTheDocument();
      expect(screen.queryByTestId('home-research-console')).not.toBeInTheDocument();
      expect(screen.queryByText('Tesla, Inc.')).not.toBeInTheDocument();
      expect(screen.queryByTestId('home-research-score-strip')).not.toBeInTheDocument();
      expect((screen.getByTestId('guest-home-clean-search').textContent || '')).not.toMatch(GUEST_PREVIEW_FAILURE_FORBIDDEN_COPY_PATTERN);
      expect(screen.queryByText(/Guest preview · live hook/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/WOLFY AI/i)).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it('redirects signed-in users away from /guest and back to home', async () => {
    useAuthMock.mockReturnValue({
      loggedIn: true,
      isLoading: false,
    });
    window.history.replaceState(window.history.state, '', '/guest');

    const LocationProbe = () => {
      const location = useLocation();
      return <div data-testid="location-path">{location.pathname}</div>;
    };

    render(
      <MemoryRouter initialEntries={['/guest']}>
        <Routes>
          <Route path="/guest" element={<><UiPreferencesProvider><GuestHomePage /></UiPreferencesProvider><LocationProbe /></>} />
          <Route path="/" element={<><div>home workspace</div><LocationProbe /></>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText('home workspace')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('location-path')).toHaveTextContent('/'));
    expect(screen.queryByTestId('guest-home-page')).not.toBeInTheDocument();
  });
});
