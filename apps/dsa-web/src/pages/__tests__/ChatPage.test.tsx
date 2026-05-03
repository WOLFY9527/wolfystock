import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createMemoryRouter, MemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { historyApi } from '../../api/history';
import { translate } from '../../i18n/core';
import type { Message, ProgressStep } from '../../stores/agentChatStore';
import { ShellRailHarness } from '../../test-utils/ShellRailHarness';
import ChatPage from '../ChatPage';

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const mockLoadSessions = vi.fn();
const mockLoadInitialSession = vi.fn();
const mockSwitchSession = vi.fn();
const mockStartStream = vi.fn();
const mockStopStream = vi.fn();
const mockClearCompletionBadge = vi.fn();
const mockStartNewChat = vi.fn();
const { mockAddWatchlistItem, mockListWatchlistItems, mockGetSnapshot, mockGetRecentWatchlists, mockGetRuleBacktestRuns } = vi.hoisted(() => ({
  mockAddWatchlistItem: vi.fn(),
  mockListWatchlistItems: vi.fn(),
  mockGetSnapshot: vi.fn(),
  mockGetRecentWatchlists: vi.fn(),
  mockGetRuleBacktestRuns: vi.fn(),
}));
let currentLanguage: 'zh' | 'en' = 'zh';

const mockStoreState: {
  messages: Message[];
  loading: boolean;
  progressSteps: ProgressStep[];
  sessionId: string;
  sessions: Array<{
    session_id: string;
    title: string;
    message_count: number;
    created_at: string;
    last_active: string;
  }>;
  sessionsLoading: boolean;
  sessionLoadError: null;
  chatError: null;
  loadSessions: typeof mockLoadSessions;
  loadInitialSession: typeof mockLoadInitialSession;
  switchSession: typeof mockSwitchSession;
  startStream: typeof mockStartStream;
  stopStream: typeof mockStopStream;
  clearCompletionBadge: typeof mockClearCompletionBadge;
} = {
  messages: [],
  loading: false,
  progressSteps: [],
  sessionId: 'session-1',
  sessions: [
    {
      session_id: 'session-1',
      title: '请简要分析 600519',
      message_count: 2,
      created_at: '2026-03-15T09:00:00Z',
      last_active: '2026-03-15T09:05:00Z',
    },
  ],
  sessionsLoading: false,
  sessionLoadError: null,
  chatError: null,
  loadSessions: mockLoadSessions,
  loadInitialSession: mockLoadInitialSession,
  switchSession: mockSwitchSession,
  startStream: mockStartStream,
  stopStream: mockStopStream,
  clearCompletionBadge: mockClearCompletionBadge,
};

const canonicalBullTrendLabel = (language: 'zh' | 'en') => translate(language, 'chat.skills.labels.bull_trend');
const canonicalGeneralLabel = (language: 'zh' | 'en') => translate(language, 'chat.skills.general');

vi.mock('../../api/agent', () => ({
  agentApi: {
    getSkills: vi.fn().mockResolvedValue({
      skills: [
        { id: 'bull_trend', name: '趋势分析', description: '测试技能' },
        { id: 'ma_cross', name: '均线金叉', description: '均线测试' },
        { id: 'volume_breakout', name: '放量突破', description: '突破测试' },
        { id: 'leader_strategy', name: '龙头策略', description: '龙头测试' },
      ],
      default_skill_id: 'bull_trend',
    }),
    getModels: vi.fn().mockResolvedValue({
      models: [
        { deployment_id: 'auto', model: 'deepseek-chat', provider: 'DeepSeek', source: 'env', is_primary: true },
      ],
    }),
    getProviderHealth: vi.fn().mockResolvedValue({
      routingMode: 'AUTO',
      currentProvider: 'DeepSeek',
      currentModel: 'deepseek-chat',
      providers: [
        { id: 'deepseek', label: 'DeepSeek', status: 'available', model: 'deepseek-chat', selected: true },
        { id: 'openai', label: 'OpenAI', status: 'not_configured' },
        { id: 'gemini', label: 'Gemini', status: 'offline' },
        { id: 'local', label: 'Local', status: 'unknown' },
      ],
    }),
    deleteChatSession: vi.fn().mockResolvedValue(undefined),
    sendChat: vi.fn().mockResolvedValue({ success: true }),
  },
}));

vi.mock('../../api/watchlist', () => ({
  watchlistApi: {
    addWatchlistItem: mockAddWatchlistItem,
    listWatchlistItems: mockListWatchlistItems,
  },
}));

vi.mock('../../api/portfolio', () => ({
  portfolioApi: {
    getSnapshot: mockGetSnapshot,
  },
}));

vi.mock('../../api/scanner', () => ({
  scannerApi: {
    getRecentWatchlists: mockGetRecentWatchlists,
  },
}));

vi.mock('../../api/backtest', () => ({
  backtestApi: {
    getRuleBacktestRuns: mockGetRuleBacktestRuns,
  },
}));

vi.mock('../../api/history', () => ({
  historyApi: {
    getDetail: vi.fn().mockResolvedValue({}),
  },
}));

vi.mock('../../stores/agentChatStore', () => {
  const useAgentChatStore = (
    selector?: (state: typeof mockStoreState) => unknown
  ) => (typeof selector === 'function' ? selector(mockStoreState) : mockStoreState);

  useAgentChatStore.getState = () => ({
    startNewChat: mockStartNewChat,
  });

  return { useAgentChatStore };
});

vi.mock('../../contexts/UiLanguageContext', async () => {
  const actual = await vi.importActual<typeof import('../../i18n/core')>('../../i18n/core');
  return {
    useI18n: () => ({
      language: currentLanguage,
      t: (key: string, vars?: Record<string, string | number | undefined>) => actual.translate(currentLanguage, key, vars),
      setLanguage: vi.fn(),
      toggleLanguage: vi.fn(),
    }),
  };
});

beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query === '(prefers-color-scheme: dark)',
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });

  Object.defineProperty(window, 'requestAnimationFrame', {
    writable: true,
    value: (callback: FrameRequestCallback) => window.setTimeout(() => callback(0), 0),
  });

  Object.defineProperty(window, 'cancelAnimationFrame', {
    writable: true,
    value: (handle: number) => window.clearTimeout(handle),
  });

  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
    writable: true,
    value: vi.fn(),
  });
});

beforeEach(() => {
  vi.clearAllMocks();
  currentLanguage = 'zh';
  mockStoreState.messages = [];
  mockStoreState.loading = false;
  mockStoreState.progressSteps = [];
  mockStoreState.sessionId = 'session-1';
  mockStoreState.sessions = [
    {
      session_id: 'session-1',
      title: '请简要分析 600519',
      message_count: 2,
      created_at: '2026-03-15T09:00:00Z',
      last_active: '2026-03-15T09:05:00Z',
    },
  ];
  mockStoreState.sessionsLoading = false;
  mockStoreState.sessionLoadError = null;
  mockStoreState.chatError = null;
  mockStoreState.stopStream = mockStopStream;
  mockAddWatchlistItem.mockResolvedValue({
    id: 1,
    symbol: 'ORCL',
    market: 'us',
    source: 'chat',
  });
  mockListWatchlistItems.mockResolvedValue({
    items: [
      {
        id: 11,
        symbol: 'ORCL',
        market: 'us',
        source: 'scanner',
        intelligence: {
          scanner: { status: 'selected', lastRank: 3, lastScore: 82.1, lastScannedAt: '2026-05-02T10:00:00Z' },
          backtest: { lastResultId: 34, totalReturnPct: 12.3, testedAt: '2026-05-01T10:00:00Z' },
        },
      },
    ],
  });
  mockGetSnapshot.mockResolvedValue({
    asOf: '2026-05-03',
    accounts: [
      {
        accountId: 1,
        accountName: 'Main',
        positions: [
          { symbol: 'AAPL', market: 'us', quantity: 3, lastPrice: 200, marketValueBase: 600 },
        ],
      },
    ],
  });
  mockGetRecentWatchlists.mockResolvedValue({
    items: [
      { id: 7, market: 'us', status: 'completed', runAt: '2026-05-02T10:00:00Z', topSymbols: ['ORCL', 'NVDA'] },
    ],
  });
  mockGetRuleBacktestRuns.mockResolvedValue({
    total: 1,
    page: 1,
    limit: 1,
    items: [
      { id: 34, code: 'ORCL', status: 'completed', totalReturnPct: 12.3, maxDrawdownPct: -4.2, completedAt: '2026-05-01T10:00:00Z' },
    ],
  });
});

describe('ChatPage', () => {
  it('separates AI engine, analysis lens, and data context in the console', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    expect(await screen.findByTestId('chat-engine-section')).toBeInTheDocument();
    expect(screen.getByTestId('chat-lens-section')).toBeInTheDocument();
    expect(screen.getByTestId('chat-data-context-section')).toBeInTheDocument();
    expect(screen.getByText('AI 引擎')).toBeInTheDocument();
    expect(screen.getByText('分析视角')).toBeInTheDocument();
    expect(screen.getByText('数据上下文')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '引擎视角' })).not.toBeInTheDocument();
  });

  it('shows a concise description for the active analysis lens', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    await screen.findByTestId('chat-lens-section');
    expect(screen.getAllByText('综合判断').length).toBeGreaterThan(0);
    expect(screen.getByText('适合普通问股，综合趋势、风险、基本面与操作计划。')).toBeInTheDocument();
  });

  it('detects US tickers, buy/hold intent, and quick actions from the composer input', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    fireEvent.change(await screen.findByPlaceholderText(translate('zh', 'chat.inputPlaceholder')), {
      target: { value: 'ORCL 还能买吗？' },
    });

    expect(screen.getByTestId('chat-smart-route-strip')).toHaveTextContent('ORCL · US · 买入/持有');
    expect(screen.getByTestId('chat-smart-route-strip')).toHaveTextContent('综合判断 / 趋势跟踪');
    expect(screen.getAllByRole('link', { name: '回测 ORCL' })[0]).toHaveAttribute('href', '/backtest?symbol=ORCL&market=US&source=chat');
    await waitFor(() => expect(screen.getAllByRole('button', { name: '已在观察列表 ORCL' }).length).toBeGreaterThan(0));
    expect(screen.getAllByRole('link', { name: '查看持仓 ORCL' })[0]).toHaveAttribute('href', '/portfolio?symbol=ORCL');
    expect(screen.getAllByRole('link', { name: '查看扫描器证据 ORCL' })[0]).toHaveAttribute('href', '/scanner?symbol=ORCL&market=US');
  });

  it('renames the route surface to the AI decision desk without using generic ask-stock as the main label', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    expect(await screen.findByRole('heading', { name: 'WOLFY AI 决策台' })).toBeInTheDocument();
    expect(screen.getByText('用自然语言调用行情、持仓、扫描器与回测证据')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: '问股' })).not.toBeInTheDocument();
  });

  it('renders provider health states without exposing secrets', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    const engineSection = await screen.findByTestId('chat-engine-section');
    expect(engineSection).toHaveTextContent('AUTO → DeepSeek');
    expect(engineSection).toHaveTextContent('DeepSeek 可用');
    expect(engineSection).toHaveTextContent('OpenAI 未配置');
    expect(engineSection).toHaveTextContent('Gemini 离线');
    expect(engineSection).toHaveTextContent('Local UNKNOWN');
    expect(engineSection.textContent).not.toMatch(/api[_-]?key|secret|sk-/i);
  });

  it('looks up real read-only evidence for detected symbols and keeps unchecked categories unknown', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    fireEvent.change(await screen.findByPlaceholderText(translate('zh', 'chat.inputPlaceholder')), {
      target: { value: 'ORCL 还能买吗？' },
    });

    await waitFor(() => expect(mockListWatchlistItems).toHaveBeenCalled());
    expect(mockGetSnapshot).toHaveBeenCalled();
    expect(mockGetRecentWatchlists).toHaveBeenCalledWith({ market: 'us', limitDays: 7 });
    expect(mockGetRuleBacktestRuns).toHaveBeenCalledWith({ code: 'ORCL', page: 1, limit: 1 });

    const evidencePanel = screen.getByTestId('chat-evidence-panel');
    expect(evidencePanel).toHaveTextContent('持仓');
    expect(evidencePanel).toHaveTextContent('missing');
    expect(evidencePanel).toHaveTextContent('观察列表');
    expect(evidencePanel).toHaveTextContent('available');
    expect(evidencePanel).toHaveTextContent('扫描器');
    expect(evidencePanel).toHaveTextContent('available');
    expect(evidencePanel).toHaveTextContent('回测');
    expect(evidencePanel).toHaveTextContent('available');
    expect(evidencePanel).toHaveTextContent('行情');
    expect(evidencePanel).toHaveTextContent('unknown');
  });

  it('detects CN symbols and compare intent for multiple symbols', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    const inputBox = await screen.findByPlaceholderText(translate('zh', 'chat.inputPlaceholder'));
    fireEvent.change(inputBox, { target: { value: '用短线视角看 600519' } });
    expect(screen.getByTestId('chat-smart-route-strip')).toHaveTextContent('600519 · CN · 趋势');

    fireEvent.change(inputBox, { target: { value: 'NVDA 和 AMD 谁更强？' } });
    expect(screen.getByTestId('chat-smart-route-strip')).toHaveTextContent('NVDA, AMD · US · 对比');
    expect(screen.getByTestId('chat-smart-route-strip')).toHaveTextContent('综合判断 / 龙头策略');
  });

  it('recommends portfolio risk and breakout lenses from wording', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    const inputBox = await screen.findByPlaceholderText(translate('zh', 'chat.inputPlaceholder'));
    fireEvent.change(inputBox, { target: { value: '我持有 AAPL，要不要减仓？' } });
    expect(screen.getByTestId('chat-smart-route-strip')).toHaveTextContent('持仓风控 / 趋势跟踪');

    fireEvent.change(inputBox, { target: { value: 'WULF 是否突破有效？' } });
    expect(screen.getByTestId('chat-smart-route-strip')).toHaveTextContent('放量突破 / 均线系统');
  });

  it('sends structured stock answer metadata without dropping existing context', async () => {
    render(
      <MemoryRouter initialEntries={['/chat?stock=600519&name=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    expect(await screen.findByDisplayValue('请深入分析 贵州茅台(600519)')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'chat.notifyAction') }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenCalledWith(
        expect.objectContaining({
          context: expect.objectContaining({
            stock_code: '600519',
            stock_name: '贵州茅台',
              stock_chat: expect.objectContaining({
                response_mode: 'structured_stock_analysis_v1',
                stock_context: expect.objectContaining({
                  symbols: ['600519'],
                  evidence: expect.objectContaining({
                    portfolio: expect.objectContaining({ status: expect.any(String) }),
                    watchlist: expect.objectContaining({ status: expect.any(String) }),
                  }),
                }),
                answer_sections: ['结论', '关键依据', '关键价位', '风险', '操作计划', '数据可信度'],
              smart_route: expect.objectContaining({
                symbols: ['600519'],
                market: 'CN',
              }),
            }),
          }),
        }),
        expect.anything(),
      );
    });
  });

  it('sends evidence summary to the AgentExecutor request and renders an assistant evidence footer', async () => {
    mockStoreState.messages = [
      {
        id: 'assistant-evidence',
        role: 'assistant',
        content: '结论：谨慎观察',
        skillName: '综合判断',
        evidenceFooter: {
          provider: 'DeepSeek',
          model: 'deepseek-chat',
          lenses: ['综合判断', '趋势跟踪'],
          items: [
            { label: '行情', status: 'unknown' },
            { label: '持仓', status: 'missing', summary: '无' },
            { label: '观察列表', status: 'available', summary: '已加入' },
            { label: 'Scanner', status: 'available', summary: '最近入选' },
            { label: '回测', status: 'available', summary: '有' },
          ],
        },
      },
    ];

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    expect(await screen.findByTestId('chat-answer-evidence-footer-assistant-evidence')).toHaveTextContent('LLM: DeepSeek deepseek-chat');
    expect(screen.getByTestId('chat-answer-evidence-footer-assistant-evidence')).toHaveTextContent('数据: 行情 UNKNOWN · 持仓 无 · 观察列表 已加入 · Scanner 最近入选 · 回测 有');

    fireEvent.change(screen.getByPlaceholderText(translate('zh', 'chat.inputPlaceholder')), {
      target: { value: 'ORCL 还能买吗？' },
    });
    await waitFor(() => expect(mockGetRuleBacktestRuns).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'chat.notifyAction') }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenCalledWith(
        expect.objectContaining({
          context: expect.objectContaining({
            stock_chat: expect.objectContaining({
              stock_context: expect.objectContaining({
                symbols: ['ORCL'],
                evidence: expect.objectContaining({
                  watchlist: expect.objectContaining({ inWatchlist: true }),
                  portfolio: expect.objectContaining({ hasPosition: false }),
                  backtest: expect.objectContaining({ resultId: 34, returnPct: 12.3 }),
                }),
              }),
            }),
          }),
        }),
        expect.objectContaining({
          evidenceFooter: expect.objectContaining({ provider: 'DeepSeek' }),
        }),
      );
    });
  });

  it('shows evidence status safely and can add a detected symbol to watchlist', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    expect(await screen.findByTestId('chat-evidence-panel')).toHaveTextContent('先输入具体标的');

    fireEvent.change(screen.getByPlaceholderText(translate('zh', 'chat.inputPlaceholder')), {
      target: { value: 'ORCL 还能买吗？' },
    });
    await waitFor(() => expect(screen.getAllByRole('button', { name: '已在观察列表 ORCL' }).length).toBeGreaterThan(0));
    fireEvent.click(screen.getAllByRole('button', { name: '已在观察列表 ORCL' })[0]);

    expect(mockAddWatchlistItem).not.toHaveBeenCalled();
  });

  it('renders the compact mobile console content without desktop assumptions', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByTestId('chat-bento-brief-trigger'));

    expect(await screen.findByTestId('chat-bento-drawer')).toBeInTheDocument();
    expect(screen.getByTestId('chat-drawer-control-panel')).toHaveTextContent('AI 引擎');
    expect(screen.getByTestId('chat-drawer-control-panel')).toHaveTextContent('分析视角');
    expect(screen.getByTestId('chat-drawer-control-panel')).toHaveTextContent('数据上下文');
  });

  it('replaces persisted Gemini 429 failure notes with the timeout fallback copy', async () => {
    mockStoreState.messages = [
      {
        id: 'assistant-timeout',
        role: 'assistant',
        content: '[分析失败] Gemini 429: rate limit exceeded',
      },
    ];

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    expect(await screen.findByText('当前响应超时，请稍后刷新')).toBeInTheDocument();
    expect(screen.queryByText(/429|rate limit exceeded/i)).not.toBeInTheDocument();
  });

  it('renders a widened chat workspace with a right-side console toggle and non-overlay composer', async () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/chat']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    expect(await screen.findByTestId('chat-bento-page')).toHaveAttribute('data-bento-surface', 'true');
    expect(screen.getByTestId('chat-bento-page')).toHaveClass('bento-surface-root');
    expect(screen.getByTestId('chat-bento-page')).toHaveClass('flex', 'h-full', 'flex-col', 'overflow-hidden', 'bg-[#030303]', 'min-h-0', 'min-w-0');
    expect(screen.getByTestId('chat-bento-page')).not.toHaveClass('workspace-page--chat', 'px-6', 'md:px-8', 'xl:px-12', 'pt-6', 'pb-12', 'overflow-y-auto', 'no-scrollbar');
    expect(screen.getByTestId('chat-bento-page')).not.toHaveClass('min-h-full', 'gap-6');
    expect(container.querySelectorAll('main')).toHaveLength(1);
    expect(await screen.findByTestId('chat-workspace')).toBeInTheDocument();
    expect(screen.getByTestId('chat-workspace')).toHaveClass('w-full', 'flex', 'flex-1', 'min-h-0', 'overflow-hidden', 'bg-transparent');
    expect(screen.queryByTestId('chat-history-pane')).not.toBeInTheDocument();
    expect(screen.getByTestId('chat-main-shell')).toHaveClass('flex', 'h-full', 'min-h-0', 'flex-1', 'min-w-0', 'overflow-hidden');
    expect(screen.getByTestId('chat-main-panel')).toHaveClass('relative', 'flex', 'h-full', 'min-h-0', 'flex-1', 'min-w-0', 'flex-col');
    expect(screen.getByTestId('chat-main').tagName).toBe('MAIN');
    expect(screen.getByTestId('chat-main')).toHaveAttribute('id', 'chat-scroll-container');
    expect(screen.getByTestId('chat-main')).toHaveClass('flex-1', 'flex', 'flex-col', 'h-full', 'overflow-hidden');
    expect(screen.getByTestId('chat-main')).not.toHaveClass('relative');
    expect(screen.queryByTestId('chat-status-strip')).not.toBeInTheDocument();
    expect(screen.queryByTestId('chat-bento-hero-skill')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: translate('zh', 'chat.title') })).toBeInTheDocument();
    expect(screen.queryByTitle('查看摘要')).not.toBeInTheDocument();
    expect(screen.queryByTestId('chat-message-scroll')).not.toBeInTheDocument();
    expect(screen.queryByTestId('chat-message-stream')).not.toBeInTheDocument();
    expect(screen.getByTestId('chat-empty-state')).toHaveClass('flex-1', 'overflow-y-auto', 'flex', 'flex-col', 'items-center', 'justify-start');
    expect(screen.getByTestId('chat-empty-state')).not.toHaveClass('pb-10', 'pb-8', 'mb-8');
    expect(screen.getByTestId('chat-input-shell')).toHaveClass('w-full', 'shrink-0');
    expect(screen.getByTestId('chat-input-shell')).not.toHaveClass('mt-auto', 'pt-4', 'pb-8', 'pb-10', 'mb-8');
    expect(screen.getByTestId('chat-input-shell')).not.toHaveClass('absolute', 'bottom-0', 'left-0', 'z-50', 'pointer-events-none');
    expect(screen.getByTestId('chat-input-gradient')).toHaveClass('w-full', 'shrink-0', 'px-6', 'pb-6', 'pt-4', 'md:px-8', 'xl:px-12');
    expect(screen.getByTestId('chat-input-gradient')).not.toHaveClass('pb-20', 'mb-32');
    expect(screen.getByTestId('chat-console-inner')).toHaveClass('w-full');
    expect(screen.getByTestId('chat-console-inner')).not.toHaveClass('px-6', 'md:px-8', 'xl:px-12');
    expect(screen.getByTestId('chat-console-inner')).not.toHaveClass('max-w-4xl', 'mx-auto');
    expect(screen.getByTestId('chat-input-shell').parentElement).toBe(screen.getByTestId('chat-main'));
    expect(screen.getByTestId('chat-input-shell').parentElement).not.toBe(screen.getByTestId('chat-main-panel'));
    expect(screen.getByTestId('chat-composer-omnibar')).toHaveClass(
      'relative',
      'max-w-4xl',
      'mx-auto',
      'rounded-3xl',
      'border-white/[0.05]',
      'bg-white/[0.04]',
      'backdrop-blur-2xl',
      'border',
      'p-2',
      'shadow-2xl',
    );
    expect(screen.getByText('AI 洞察仅供参考，不构成实质性投资建议。执行交易前请确认风险承受能力。')).toHaveClass('mt-3', 'text-[10px]', 'text-center', 'text-white/30');
    expect(screen.queryByTestId('chat-skill-toolbar')).not.toBeInTheDocument();
    expect(screen.getByTestId('chat-strategy-panel')).toHaveClass('hidden', 'lg:flex', 'h-full', 'min-h-0', 'w-full', 'shrink-0', 'flex-col', 'gap-5', 'overflow-y-auto', 'border-l', 'border-white/5', 'bg-gradient-to-b', 'from-white/[0.01]', 'to-transparent', 'p-5', 'lg:w-[320px]', 'xl:w-[360px]');
    expect(screen.getByTestId('chat-console-mode-toggle')).toBeInTheDocument();
    expect(screen.getByTestId('chat-strategy-grid')).toHaveClass('grid', 'grid-cols-2', 'gap-2');
    expect(mockLoadInitialSession).toHaveBeenCalled();
    expect(mockClearCompletionBadge).toHaveBeenCalled();

    fireEvent.click(screen.getByTestId('chat-bento-brief-trigger'));
    expect(await screen.findByTestId('chat-bento-drawer')).toBeInTheDocument();
    expect(screen.getByRole('dialog', { name: '决策台控制台' })).toBeInTheDocument();
  });

  it('switches the right-side console between engines and history', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    expect(await screen.findByTestId('chat-console-mode-toggle')).toBeInTheDocument();
    expect(screen.getByTestId('chat-strategy-grid')).toBeInTheDocument();
    expect(screen.queryByTestId('chat-history-list')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '历史记录' }));

    expect(screen.getByTestId('chat-history-list')).toBeInTheDocument();
    expect(screen.queryByTestId('chat-strategy-grid')).not.toBeInTheDocument();
  });

  it('exposes a prominent new-chat action in the header and clears the current thread', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    const newChatButtons = await screen.findAllByRole('button', { name: translate('zh', 'chat.newChatTitle') });
    fireEvent.click(newChatButtons[0]);

    expect(mockStartNewChat).toHaveBeenCalledTimes(1);
  });

  it('removes the floating debug status strip from the workspace', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    expect(await screen.findByTestId('chat-workspace')).toBeInTheDocument();
    expect(screen.queryByText('技能模式')).not.toBeInTheDocument();
    expect(screen.queryByText('消息深度')).not.toBeInTheDocument();
    expect(screen.queryByText('跟踪对话')).not.toBeInTheDocument();
  });

  it('keeps the empty state anchored instead of auto-scrolling to the footer on first paint', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    expect(await screen.findByText(translate('zh', 'chat.emptyTitle'))).toBeInTheDocument();
    expect(HTMLElement.prototype.scrollIntoView).not.toHaveBeenCalled();
  });

  it('shows research-focused starter cards in the empty state', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    expect(await screen.findByText(translate('zh', 'chat.emptyTitle'))).toBeInTheDocument();
    expect(screen.getByTestId('chat-empty-state')).toHaveClass('flex-1', 'overflow-y-auto', 'flex', 'flex-col', 'items-center', 'justify-start');
    expect(screen.getByRole('heading', { name: translate('zh', 'chat.title') })).toHaveClass('text-xl', 'font-bold', 'text-white');
    const entryDecisionCard = screen.getByTestId('chat-starter-card-entryDecision');
    expect(entryDecisionCard).toHaveClass('flex', 'flex-col', 'items-center', 'justify-center', 'rounded-2xl', 'border', 'border-white/5', 'bg-white/[0.02]', 'px-4', 'py-3', 'text-center', 'hover:bg-white/[0.05]');
    expect(screen.getAllByText(translate('zh', 'chat.starterCards.entryDecision.title')).length).toBeGreaterThan(0);
    expect(screen.getAllByText(translate('zh', 'chat.starterCards.positionReview.title')).length).toBeGreaterThan(0);
    expect(screen.getByTestId('chat-mobile-template-eventFollowUp')).toBeInTheDocument();
    expect(screen.getByText(translate('zh', 'chat.description'))).toBeInTheDocument();
    expect(screen.getByTestId('chat-quick-question-cloud')).toHaveClass('hidden', 'flex-wrap', 'justify-center');
    expect(screen.getByText(translate('zh', 'chat.quickQuestions.q3'))).toHaveClass(
      'inline-flex',
      'items-center',
      'justify-center',
      'px-5',
      'py-2.5',
      'rounded-xl',
      'bg-white/[0.02]',
      'border-white/5',
      'text-xs',
      'text-white/60',
      'whitespace-nowrap',
    );
    expect(screen.queryByTestId('chat-footer-starter-strip')).not.toBeInTheDocument();
    expect(screen.queryByTestId('chat-footer-quick-questions')).not.toBeInTheDocument();
  });

  it('animates only the latest assistant reply while generation is active', async () => {
    vi.useFakeTimers();
    mockStoreState.messages = [
      {
        id: 'assistant-history',
        role: 'assistant',
        content: '历史回复保持完整显示',
        skillName: canonicalBullTrendLabel('zh'),
      },
    ];

    const view = render(
      <MemoryRouter initialEntries={['/chat']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    expect(screen.getByTestId('chat-main').textContent).toContain('历史回复保持完整显示');
    expect(screen.queryByTestId('chat-typewriter-assistant-history')).not.toBeInTheDocument();

    mockStoreState.messages = [
      ...mockStoreState.messages,
      {
        id: 'assistant-latest',
        role: 'assistant',
        content: '最新回复正在涌现，请继续观察成交量与关键价位变化',
        skillName: canonicalBullTrendLabel('zh'),
      },
    ];
    mockStoreState.loading = true;

    await act(async () => {
      view.rerender(
        <MemoryRouter initialEntries={['/chat']}>
          <ShellRailHarness>
            <ChatPage />
          </ShellRailHarness>
        </MemoryRouter>
      );
    });

    const streamingNode = screen.getByTestId('chat-typewriter-assistant-latest');

    await act(async () => {
      await vi.advanceTimersToNextTimerAsync();
    });

    const partialLength = streamingNode.textContent?.length ?? 0;
    expect(partialLength).toBeGreaterThan(0);
    expect(partialLength).toBeLessThan('最新回复正在涌现，请继续观察成交量与关键价位变化'.length);
    expect(screen.getByTestId('chat-main').textContent).toContain('历史回复保持完整显示');

    await act(async () => {
      view.rerender(
        <MemoryRouter initialEntries={['/chat']}>
          <ShellRailHarness>
            <ChatPage />
          </ShellRailHarness>
        </MemoryRouter>
      );
    });

    expect((streamingNode.textContent?.length ?? 0)).toBeGreaterThanOrEqual(partialLength);
    expect(HTMLElement.prototype.scrollIntoView).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1200);
    });

    expect(streamingNode).toHaveTextContent('最新回复正在涌现，请继续观察成交量与关键价位变化');
    expect(HTMLElement.prototype.scrollIntoView).not.toHaveBeenCalled();
    mockStoreState.loading = false;
    vi.useRealTimers();
  });

  it('keeps historical assistant replies static when generation is idle', async () => {
    mockStoreState.messages = [
      {
        id: 'assistant-history',
        role: 'assistant',
        content: '第一条历史回复',
        skillName: canonicalBullTrendLabel('zh'),
      },
      {
        id: 'assistant-latest',
        role: 'assistant',
        content: '最后一条历史回复也必须静态渲染',
        skillName: canonicalBullTrendLabel('zh'),
      },
    ];

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    expect(await screen.findByText('第一条历史回复')).toBeInTheDocument();
    expect(screen.getByText('最后一条历史回复也必须静态渲染')).toBeInTheDocument();
    expect(screen.queryByTestId('chat-typewriter-assistant-latest')).not.toBeInTheDocument();
  });

  it('renders full-width bubbles and removes quote rails from assistant content surfaces', async () => {
    mockStoreState.messages = [
      {
        id: 'user-1',
        role: 'user',
        content: '这是用户问题',
        skillName: canonicalBullTrendLabel('zh'),
      },
      {
        id: 'assistant-1',
        role: 'assistant',
        content: '> 不应再出现引用竖线\n\n普通段落',
        skillName: canonicalBullTrendLabel('zh'),
        thinkingSteps: [
          {
            type: 'tool_done',
            display_name: 'quote-check',
            success: true,
            duration: 0.1,
          },
        ],
      },
    ];

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    await screen.findByText('这是用户问题');
    const userBubble = screen.getByTestId('chat-user-message-user-1').firstElementChild;
    expect(userBubble).toHaveClass('max-w-[80%]', 'bg-white/[0.05]', 'backdrop-blur-md', 'border', 'border-white/10', 'text-white/90', 'px-5', 'py-3.5', 'rounded-2xl', 'rounded-tr-[4px]', 'shadow-lg', 'text-[15px]', 'leading-relaxed', 'break-words');

    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'chat.thinking.toggleLabel') }));

    const quoteText = screen.getByText('不应再出现引用竖线');
    const assistantBubble = screen.getByTestId('chat-assistant-message-assistant-1').lastElementChild;
    expect(assistantBubble).toHaveClass('flex-1', 'min-w-0', 'bg-transparent');

    const markdownSurface = quoteText.closest('div[class*="markdown-body"]');
    expect(markdownSurface).toHaveClass('text-[15px]', 'leading-[1.6]', 'text-white/90', 'break-words');
    expect(markdownSurface?.className).not.toContain('prose-blockquote:border');

    const thinkingStep = screen.getByText('quote-check (0.1s)');
    const thinkingDetails = thinkingStep.closest('div[class*="animate-fade-in"]');
    expect(thinkingDetails?.className).not.toContain('border-l');
  });

  it('switches session when clicking anywhere on the session card', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: '历史记录' }));

    const sessionCard = await screen.findByRole('button', {
      name: translate('zh', 'chat.switchToConversation', { title: '请简要分析 600519' }),
    });

    fireEvent.click(sessionCard);
    expect(mockSwitchSession).toHaveBeenCalledWith('session-1');
  });

  it('swaps the send button for a stop control while generation is active', async () => {
    mockStoreState.loading = true;

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    const stopButton = await screen.findByRole('button', { name: translate('zh', 'chat.stopGeneration') });
    expect(stopButton).toHaveAttribute('title', translate('zh', 'chat.stopGeneration'));
    expect(screen.queryByRole('button', { name: translate('zh', 'chat.notifyAction') })).not.toBeInTheDocument();

    fireEvent.click(stopButton);
    expect(mockStopStream).toHaveBeenCalledTimes(1);
  });

  it('allows sending with base follow-up context before report hydration completes', async () => {
    const deferred = createDeferred<Awaited<ReturnType<typeof historyApi.getDetail>>>();

    vi.mocked(historyApi.getDetail).mockImplementation(() => deferred.promise);

    render(
      <MemoryRouter initialEntries={['/chat?stock=600519&name=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0&recordId=1']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    expect(await screen.findByDisplayValue('请深入分析 贵州茅台(600519)')).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /综合判断/ })).toBeInTheDocument();

    const sendButton = screen.getByRole('button', {
      name: new RegExp(`${translate('zh', 'chat.notifyAction')}|${translate('zh', 'chat.notifySending').replace(/\./g, '\\.')}`),
    });
    expect(sendButton).not.toBeDisabled();
    expect(screen.getByText(translate('zh', 'chat.followUpContextLoading'))).toBeInTheDocument();

    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenCalledWith(
        expect.objectContaining({
          message: '请深入分析 贵州茅台(600519)',
          context: expect.objectContaining({
            stock_code: '600519',
            stock_name: '贵州茅台',
            stock_chat: expect.objectContaining({
              response_mode: 'structured_stock_analysis_v1',
            }),
          }),
          skills: undefined,
        }),
        expect.objectContaining({
          skillName: canonicalGeneralLabel('zh'),
        }),
      );
    });

    deferred.resolve({
      meta: {
        id: 1,
        queryId: 'q-1',
        stockCode: '600519',
        stockName: '贵州茅台',
        reportType: 'detailed',
        createdAt: '2026-03-18T08:00:00Z',
        currentPrice: 1523.6,
        changePct: 1.8,
      },
      summary: {
        analysisSummary: '趋势延续',
        operationAdvice: '继续观察',
        trendPrediction: '高位震荡',
        sentimentScore: 78,
      },
      strategy: {
        stopLoss: '1450',
      },
    });

    await waitFor(() => {
      expect(screen.queryByText(translate('zh', 'chat.followUpContextLoading'))).not.toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText(translate('zh', 'chat.inputPlaceholder')), {
      target: { value: '继续分析成交量' },
    });
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'chat.notifyAction') }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenLastCalledWith(
        expect.objectContaining({
          message: '继续分析成交量',
          context: expect.objectContaining({
            stock_chat: expect.objectContaining({
              response_mode: 'structured_stock_analysis_v1',
            }),
          }),
        }),
        expect.objectContaining({
          skillName: canonicalGeneralLabel('zh'),
        }),
      );
    });
  });

  it('uses hydrated report context when it finishes before sending', async () => {
    vi.mocked(historyApi.getDetail).mockResolvedValue({
      meta: {
        id: 1,
        queryId: 'q-1',
        stockCode: '600519',
        stockName: '贵州茅台',
        reportType: 'detailed',
        createdAt: '2026-03-18T08:00:00Z',
        currentPrice: 1523.6,
        changePct: 1.8,
      },
      summary: {
        analysisSummary: '趋势延续',
        operationAdvice: '继续观察',
        trendPrediction: '高位震荡',
        sentimentScore: 78,
      },
      strategy: {
        stopLoss: '1450',
      },
    });

    render(
      <MemoryRouter initialEntries={['/chat?stock=600519&name=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0&recordId=1']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    expect(await screen.findByDisplayValue('请深入分析 贵州茅台(600519)')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByText(translate('zh', 'chat.followUpContextLoading'))).not.toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'chat.notifyAction') }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenCalledWith(
        expect.objectContaining({
          message: '请深入分析 贵州茅台(600519)',
          context: expect.objectContaining({
            stock_code: '600519',
            stock_name: '贵州茅台',
            previous_price: 1523.6,
            previous_change_pct: 1.8,
            previous_strategy: expect.objectContaining({
              stopLoss: '1450',
            }),
          }),
        }),
        expect.objectContaining({
          skillName: canonicalGeneralLabel('zh'),
        }),
      );
    });
  });

  it('falls back to base stock context when recordId is missing', async () => {
    render(
      <MemoryRouter initialEntries={['/chat?stock=AAPL']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    expect(await screen.findByDisplayValue('请深入分析 AAPL')).toBeInTheDocument();
    await screen.findByRole('button', { name: /综合判断/ });

    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'chat.notifyAction') }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenCalledWith(
        expect.objectContaining({
          message: '请深入分析 AAPL',
          context: expect.objectContaining({
            stock_code: 'AAPL',
            stock_name: null,
            stock_chat: expect.objectContaining({
              response_mode: 'structured_stock_analysis_v1',
            }),
          }),
        }),
        expect.objectContaining({
          skillName: canonicalGeneralLabel('zh'),
        }),
      );
    });
    expect(historyApi.getDetail).not.toHaveBeenCalled();
  });

  it('reprocesses follow-up query params when navigating to the same chat route again', async () => {
    const firstDeferred = createDeferred<Awaited<ReturnType<typeof historyApi.getDetail>>>();
    const secondDeferred = createDeferred<Awaited<ReturnType<typeof historyApi.getDetail>>>();

    vi.mocked(historyApi.getDetail)
      .mockImplementationOnce(() => firstDeferred.promise)
      .mockImplementationOnce(() => secondDeferred.promise);

    const router = createMemoryRouter(
      [{ path: '/chat', element: <ShellRailHarness><ChatPage /></ShellRailHarness> }],
      {
        initialEntries: ['/chat?stock=600519&name=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0&recordId=1'],
      },
    );

    render(<RouterProvider router={router} />);

    expect(await screen.findByDisplayValue('请深入分析 贵州茅台(600519)')).toBeInTheDocument();
    expect(screen.getByText(translate('zh', 'chat.followUpContextLoading'))).toBeInTheDocument();

    await router.navigate('/chat?stock=AAPL&name=Apple&recordId=2');

    expect(await screen.findByDisplayValue('请深入分析 Apple(AAPL)')).toBeInTheDocument();

    firstDeferred.resolve({
      meta: {
        id: 1,
        queryId: 'q-1',
        stockCode: '600519',
        stockName: '贵州茅台',
        reportType: 'detailed',
        createdAt: '2026-03-18T08:00:00Z',
        currentPrice: 1523.6,
        changePct: 1.8,
      },
      summary: {
        analysisSummary: '趋势延续',
        operationAdvice: '继续观察',
        trendPrediction: '高位震荡',
        sentimentScore: 78,
      },
      strategy: {
        stopLoss: '1450',
      },
    });

    secondDeferred.resolve({
      meta: {
        id: 2,
        queryId: 'q-2',
        stockCode: 'AAPL',
        stockName: 'Apple',
        reportType: 'detailed',
        createdAt: '2026-03-18T09:00:00Z',
        currentPrice: 211.5,
        changePct: 2.4,
      },
      summary: {
        analysisSummary: '趋势走强',
        operationAdvice: '继续持有',
        trendPrediction: '短线偏强',
        sentimentScore: 81,
      },
      strategy: {
        stopLoss: '205',
      },
    });

    await waitFor(() => {
      expect(screen.queryByText(translate('zh', 'chat.followUpContextLoading'))).not.toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'chat.notifyAction') }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenCalledWith(
        expect.objectContaining({
          message: '请深入分析 Apple(AAPL)',
          context: expect.objectContaining({
            stock_code: 'AAPL',
            stock_name: 'Apple',
            previous_price: 211.5,
            previous_change_pct: 2.4,
            previous_strategy: expect.objectContaining({
              stopLoss: '205',
            }),
          }),
        }),
        expect.objectContaining({
          skillName: canonicalGeneralLabel('zh'),
        }),
      );
    });
  });

  it('updates document title when language is english', async () => {
    currentLanguage = 'en';
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    expect(await screen.findByTestId('chat-workspace')).toBeInTheDocument();
    expect(document.title).toBe('AI Decision Desk - WolfyStock');
  });

  it('updates hero and input copy immediately when language switches to english', async () => {
    currentLanguage = 'en';
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    expect(await screen.findByTestId('chat-workspace')).toBeInTheDocument();
    expect(screen.getByText('Start with a concrete question')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Example: Is 600519 / Kweichow Moutai a buy right now? (Enter to send, Shift+Enter for newline)')).toBeInTheDocument();
  });

  it('localizes session actions in english mode', async () => {
    currentLanguage = 'en';
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: 'History' }));

    expect((await screen.findAllByText(translate('en', 'chat.historyTitle'))).length).toBeGreaterThan(0);
    expect(screen.getByRole('button', {
      name: translate('en', 'chat.switchToConversation', { title: '请简要分析 600519' }),
    })).toBeInTheDocument();
    expect(screen.getByTitle(translate('en', 'chat.deleteConversationAction'))).toBeInTheDocument();
    expect(screen.getByText(translate('en', 'chat.messageCount', { count: 2 }))).toBeInTheDocument();
  });

  it('localizes assistant thinking labels in english mode', async () => {
    currentLanguage = 'en';
    mockStoreState.messages = [
      {
        id: 'assistant-1',
        role: 'assistant',
        content: 'Here is the analysis.',
        skillName: canonicalBullTrendLabel('zh'),
        thinkingSteps: [
          { type: 'thinking', step: 1, message: 'Reviewing the setup' },
          { type: 'tool_done', tool: 'quote_fetch', display_name: 'Quote fetch', duration: 1.2, success: true },
        ],
      },
    ];

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ShellRailHarness>
          <ChatPage />
        </ShellRailHarness>
      </MemoryRouter>
    );

    expect(await screen.findByRole('button', { name: /Thinking process/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Thinking process/i }));

    expect(screen.getByText('Reviewing the setup')).toBeInTheDocument();
    expect(screen.getByText('Quote fetch (1.2s)')).toBeInTheDocument();
  });
});
