import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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

  it('uses the home bento source, hides the dashboard before search, and reveals the paywalled preview after submit', async () => {
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

    expect(screen.getByTestId('home-bento-dashboard')).toBeInTheDocument();
    expect(screen.getByTestId('guest-home-clean-search')).toBeInTheDocument();
    expect(screen.queryByTestId('home-bento-grid')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'WolfyStock 分析面板' })).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-omnibar')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '分析' })).toBeEnabled();
    expect(screen.queryByTestId('guest-home-frosted-lock')).not.toBeInTheDocument();

    fireEvent.change(screen.getByTestId('home-bento-omnibar-input'), { target: { value: 'AAPL' } });
    fireEvent.submit(screen.getByTestId('home-bento-omnibar'));

    await waitFor(() => {
      expect(previewMock).toHaveBeenCalledWith({
        stockCode: 'AAPL',
        stockName: undefined,
        reportType: 'brief',
      });
    });

    expect(await screen.findByTestId('home-bento-grid')).toBeInTheDocument();
    expect(screen.queryByTestId('guest-home-clean-search')).not.toBeInTheDocument();
    expect(screen.getByText('Apple Inc.')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-decision-score-value')).toHaveTextContent('7.2');
    expect(screen.getAllByText('趋势延续但需要等待更好的介入点。').length).toBeGreaterThan(0);
    expect(screen.getAllByTestId('guest-home-frosted-lock')).toHaveLength(2);
    expect(screen.getAllByText('解锁完整 AI 量化策略与深度技术形态解析')).toHaveLength(2);
    expect(screen.getAllByRole('link', { name: '免费创建账户 (Create Free Account)' })).toHaveLength(2);
    expect(screen.getByTestId('home-bento-secondary-stack')).toContainElement(screen.getAllByTestId('guest-home-frosted-lock')[1]);
  });

  it('renders the English clean search funnel copy', () => {
    languageState.value = 'en';
    window.history.replaceState(window.history.state, '', '/en');

    renderGuest(['/en/guest']);

    expect(screen.getByRole('heading', { name: 'WolfyStock Analysis Center' })).toBeInTheDocument();
    expect(screen.getByText('Enter a ticker to generate an analysis view.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Analyze' })).toBeInTheDocument();
    expect(screen.queryByTestId('home-bento-grid')).not.toBeInTheDocument();
  });

  it('falls back to a local snapshot when the live preview API rate-limits', async () => {
    languageState.value = 'en';
    window.history.replaceState(window.history.state, '', '/en');
    previewMock.mockRejectedValueOnce(new Error('429 RateLimitError: upstream overloaded'));

    renderGuest(['/en/guest']);

    fireEvent.change(screen.getByTestId('home-bento-omnibar-input'), { target: { value: 'NVDA' } });
    fireEvent.click(screen.getByRole('button', { name: 'Analyze' }));

    expect(await screen.findByText('Live preview is temporarily unavailable. Loaded a local snapshot instead.')).toBeInTheDocument();
    expect(await screen.findByText('NVIDIA Corporation')).toBeInTheDocument();
    expect(screen.getAllByText('The local snapshot keeps the leadership trend intact, with momentum still driving the short-term structure.').length).toBeGreaterThan(0);
    expect(screen.getByTestId('home-bento-decision-score-value')).toHaveTextContent('8.4');
    expect(within(screen.getByTestId('home-bento-secondary-stack')).getByTestId('guest-home-frosted-lock')).toBeInTheDocument();
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
