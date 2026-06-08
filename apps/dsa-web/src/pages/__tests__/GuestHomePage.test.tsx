import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { UiPreferencesProvider } from '../../contexts/UiPreferencesContext';
import GuestHomePage from '../GuestHomePage';

const { previewMock, languageState, useAuthMock } = vi.hoisted(() => ({
  previewMock: vi.fn(),
  languageState: { value: 'zh' as 'zh' | 'en' },
  useAuthMock: vi.fn(),
}));

vi.mock('../../api/publicAnalysis', () => ({
  publicAnalysisApi: {
    preview: (...args: unknown[]) => previewMock(...args),
  },
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
    useAuthMock.mockReturnValue({
      loggedIn: false,
      isLoading: false,
    });
    window.history.replaceState(window.history.state, '', '/zh');
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
    const capabilityStrip = screen.getByTestId('guest-home-capability-strip');
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
    expect(capabilityStrip).toHaveTextContent('登录后继续');
    expect(capabilityStrip).toHaveTextContent('保存报告');
    expect(capabilityStrip).toHaveTextContent('回看历史');
    expect(capabilityStrip).toHaveTextContent('组合工作台');
    expect(capabilityStrip).toHaveTextContent('全市场扫描');
    expect(screen.getByTestId('guest-home-registration-link')).toHaveAttribute('href', '/login?mode=create&redirect=%2F');
    expect(trustStrip).toHaveTextContent('研究边界');
    expect(trustStrip).toHaveTextContent('不等于买卖建议');
    expect(previewStrip).toHaveTextContent('登录后下一步');
    expect(previewStrip).toHaveTextContent('回到上次研究现场');
    expect(screen.queryByTestId('guest-home-frosted-lock')).not.toBeInTheDocument();
    expect(guestFirstScreen).not.toHaveTextContent('WolfyStock 分析面板');
    expect(guestFirstScreen).not.toHaveTextContent('输入股票代码，搜索后生成 AI 分析面板。');
    expect(guestFirstScreen).not.toHaveTextContent(/买入|卖出|推荐|目标价|止损/);

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
    expect(screen.getAllByText('解锁完整研究框架、观察区间与技术形态解读')).toHaveLength(2);
    expect(screen.getAllByRole('link', { name: '免费创建账户' })).toHaveLength(2);
    expect(screen.getByTestId('home-research-context-rail')).toContainElement(screen.getAllByTestId('guest-home-frosted-lock')[1]);
  });

  it('renders the English clean search funnel copy', () => {
    languageState.value = 'en';
    window.history.replaceState(window.history.state, '', '/en');

    renderGuest(['/en/guest']);

    expect(screen.getByRole('heading', { name: 'WolfyStock Research Console' })).toBeInTheDocument();
    expect(screen.getByText('WolfyStock is a stock research workspace for self-directed investors and research-oriented users. Start with one ticker preview now, then sign in to save reports, reopen history, and continue into portfolio or scanner workflows.')).toBeInTheDocument();
    expect(screen.getByTestId('guest-home-trust-strip')).toHaveTextContent('not a trading instruction');
    expect(screen.getByRole('button', { name: 'Analyze' })).toBeInTheDocument();
    expect(screen.queryByTestId('home-research-console')).not.toBeInTheDocument();
  });

  it('falls back to a local snapshot when the live preview API rate-limits', async () => {
    languageState.value = 'en';
    window.history.replaceState(window.history.state, '', '/en');
    previewMock.mockRejectedValueOnce(new Error('429 RateLimitError: upstream overloaded'));

    renderGuest(['/en/guest']);

    fireEvent.change(screen.getByTestId('home-bento-omnibar-input'), { target: { value: 'NVDA' } });
    fireEvent.click(screen.getByRole('button', { name: 'Analyze' }));

    expect(await screen.findByText('Live preview is unavailable right now. Loaded a local research snapshot instead.')).toBeInTheDocument();
    expect(await screen.findByText('NVIDIA Corporation')).toBeInTheDocument();
    expect(screen.getAllByText('The local snapshot keeps the leadership trend intact, with momentum still driving the short-term structure.').length).toBeGreaterThan(0);
    expect(screen.getByTestId('home-research-score-strip')).toHaveTextContent('8.4');
    expect(screen.queryByTestId('home-bento-decision-score-value')).not.toBeInTheDocument();
    expect(within(screen.getByTestId('home-research-context-rail')).getByTestId('guest-home-frosted-lock')).toBeInTheDocument();
  });

  it('resolves guest search to a bounded local snapshot when the preview request never settles', async () => {
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
      });

      expect(screen.getByText('Live preview is unavailable right now. Loaded a local research snapshot instead.')).toBeInTheDocument();
      expect(screen.getByTestId('home-research-console')).toBeInTheDocument();
      expect(screen.getByText('Tesla, Inc.')).toBeInTheDocument();
      expect(screen.getByTestId('home-research-score-strip')).toHaveTextContent('6.3');
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
