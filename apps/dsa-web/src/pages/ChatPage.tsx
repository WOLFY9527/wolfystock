import React, { Suspense, lazy, useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { ArrowUp, Download, PanelRightOpen, SendHorizontal } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { agentApi, type AgentProviderHealthResponse, type AgentStockEvidenceItem } from '../api/agent';
import { watchlistApi } from '../api/watchlist';
import { portfolioApi } from '../api/portfolio';
import { scannerApi } from '../api/scanner';
import { backtestApi } from '../api/backtest';
import {
  ConsoleBoard,
  ConsoleContextRail,
  ConsoleDisclosure,
  ConsoleStatusStrip,
  WolfyCommandBar,
  WolfyShellSurface,
} from '../components/linear';
import { ApiErrorAlert, ConfirmDialog, Drawer, TypewriterText } from '../components/common';
import { GuidedDisclosure } from '../components/guidance';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import type { SkillInfo } from '../api/agent';
import {
  useAgentChatStore,
  type Message,
  type ProgressStep,
} from '../stores/agentChatStore';
import { downloadSession, formatSessionAsMarkdown } from '../utils/chatExport';
import type { ChatFollowUpContext } from '../utils/chatFollowUp';
import { buildFollowUpPrompt, resolveChatFollowUpContext } from '../utils/chatFollowUp';
import { normalizeAssistantMessageContent } from '../utils/chatTimeoutFallback';
import { useI18n } from '../contexts/UiLanguageContext';
import {
  useSafariWarmActivation,
} from '../hooks/useSafariInteractionReady';
import { translate } from '../i18n/core';

const AssistantMarkdownContent = lazy(() => import('../components/chat/AssistantMarkdownContent'));

type QuickQuestion = {
  id: string;
  skill: string;
};

const CHAT_COPY_OVERRIDES: Record<'zh' | 'en', Record<string, string>> = {
  zh: {
    documentTitle: 'AI 研究台 - WolfyStock',
    title: 'WOLFY AI 研究台',
    description: '用自然语言调用只读证据，形成分析观察与风险边界',
    emptyBody: '先明确观察结论，再继续细化风险、催化和数据可信度。',
    'starterCards.entryDecision.title': '观察条件检查',
    'starterCards.entryDecision.description': '基于只读证据复核当前是否具备继续观察的条件。',
    'starterCards.entryDecision.prompt': '请基于只读证据分析 NVDA 的观察条件、风险边界和需要等待的确认信号',
    'starterCards.positionReview.title': '持仓风险复盘',
    'starterCards.positionReview.description': '适合已有持仓时复核风险暴露、情景假设和后续观察条件。',
    'starterCards.positionReview.prompt': '我持有 TSLA，请复核当前风险暴露、需要观察的确认信号和情景分歧',
    'starterCards.eventFollowUp.description': '聚焦财报、催化、风险与情绪，不给出行动指令。',
    'starterCards.eventFollowUp.prompt': 'ORCL 财报后是否仍值得观察？请列出催化、风险和数据缺口',
    'quickQuestions.q1': '分析 ORCL 是否仍值得观察',
    'quickQuestions.q2': '我持有 AAPL，主要风险和确认信号是什么',
    'skills.general': '综合观察',
    inputPlaceholder: '例如：分析 600519 / 茅台当前观察条件是什么？（回车发送，Shift+回车换行）',
    suggestedFocus: '优先提问：观察条件、风险边界、数据可信度和催化。',
  },
  en: {
    documentTitle: 'AI Research Desk - WolfyStock',
    title: 'WOLFY AI Research Desk',
    description: 'Use natural language to call read-only evidence for observation analysis and risk boundaries.',
    emptyBody: 'Start with an observation thesis, then narrow into risk, catalysts, and data confidence.',
    'starterCards.entryDecision.title': 'Readiness check',
    'starterCards.entryDecision.description': 'Review read-only evidence for observation conditions and risk boundaries.',
    'starterCards.entryDecision.prompt': 'Use read-only evidence to analyze NVDA observation conditions, risk boundaries, and confirmation signals.',
    'starterCards.positionReview.description': 'For existing positions, review exposure, scenarios, and follow-up observation conditions.',
    'starterCards.positionReview.prompt': 'I hold TSLA. Review current risk exposure, confirmation signals to watch, and scenario disagreements.',
    'starterCards.eventFollowUp.description': 'Focus on catalysts, risks, and data gaps without action instructions.',
    'starterCards.eventFollowUp.prompt': 'After ORCL earnings, is it still worth observing? List catalysts, risks, and data gaps.',
    'quickQuestions.q1': 'Analyze whether ORCL is still worth observing',
    'quickQuestions.q2': 'I hold AAPL. What are the main risks and confirmation signals?',
    'skills.general': 'General observation',
    inputPlaceholder: 'Example: What are the current observation conditions for 600519 / Kweichow Moutai? (Enter to send, Shift+Enter for newline)',
    suggestedFocus: 'Suggested focus: observation conditions, risk boundaries, data confidence, and catalysts.',
  },
};

type ChatConsoleMode = 'engines' | 'history';
type StockMarket = 'US' | 'CN' | 'HK' | 'unknown';
type SmartRouteIntent =
  | 'buy_or_hold'
  | 'sell_or_reduce'
  | 'risk_check'
  | 'compare'
  | 'breakout'
  | 'trend'
  | 'position_management'
  | 'fundamental'
  | 'event'
  | 'general';

type SmartRouteResult = {
  symbols: string[];
  market: StockMarket;
  intent: SmartRouteIntent;
  intentLabel: string;
  recommendedLenses: string[];
  confidence: 'high' | 'medium' | 'low';
};

type DataEvidenceStatus = 'used' | 'available' | 'partial' | 'missing' | 'stale' | 'fallback' | 'unknown' | 'error';

type DataEvidenceItem = {
  key: string;
  label: string;
  status: DataEvidenceStatus;
  source?: string;
  updatedAt?: string;
  summary?: string;
  inWatchlist?: boolean;
  hasPosition?: boolean;
  resultId?: number;
  returnPct?: number;
  price?: number;
  changePct?: number;
  provider?: string;
  trend?: string;
  ma5?: number;
  ma10?: number;
  ma20?: number;
  ma60?: number;
  rsi14?: number;
  support?: number;
  resistance?: number;
  marketCap?: number;
  peTtm?: number;
  pb?: number;
  beta?: number;
  revenueTtm?: number;
  netIncomeTtm?: number;
  fcfTtm?: number;
  missingFields?: string[];
};

type AnalysisLens = {
  id: string;
  label: string;
  description: string;
  skillId?: string;
  advanced?: boolean;
};

const QUICK_QUESTIONS: QuickQuestion[] = [
  { id: 'q1', skill: 'chan_theory' },
  { id: 'q2', skill: 'wave_theory' },
  { id: 'q3', skill: 'bull_trend' },
  { id: 'q4', skill: 'box_oscillation' },
  { id: 'q5', skill: 'bull_trend' },
  { id: 'q6', skill: 'emotion_cycle' },
];

const STOCK_CHAT_ANSWER_SECTIONS = ['结论', '关键依据', '关键价位', '风险', '观察计划', '数据可信度'];

const PRIMARY_ANALYSIS_LENSES: AnalysisLens[] = [
  { id: 'general', label: '综合观察', description: '适合普通问股，综合趋势、风险、基本面与观察条件。' },
  { id: 'trend_following', label: '趋势跟踪', description: '判断趋势延续、回调、结构失效与趋势衰竭。', skillId: 'bull_trend' },
  { id: 'ma_system', label: '均线系统', description: '关注 MA5/10/20/60 排列、金叉死叉和支撑压力。', skillId: 'ma_cross' },
  { id: 'volume_breakout', label: '放量突破', description: '关注平台突破、成交量确认、假突破与回踩。', skillId: 'volume_breakout' },
  { id: 'range_box', label: '箱体震荡', description: '适合判断区间上沿/下沿、突破与跌破。', skillId: 'box_oscillation' },
  { id: 'emotion_cycle', label: '情绪周期', description: '适合题材股、短线强弱和市场情绪判断。', skillId: 'emotion_cycle' },
  { id: 'leader_strategy', label: '龙头策略', description: '关注板块地位、相对强度、资金承接和持续性。', skillId: 'leader_strategy' },
  { id: 'position_risk', label: '持仓风险', description: '结合成本、风险暴露、盈亏和风险线复核观察条件。', skillId: 'volume_pullback' },
  { id: 'fundamental_quality', label: '基本面质量', description: '关注收入、利润、估值、ROE、现金流和财报质量。' },
  { id: 'event_driven', label: '事件驱动', description: '关注财报、政策、产品、并购、宏观事件影响。' },
];

const ADVANCED_ANALYSIS_LENSES: AnalysisLens[] = [
  { id: 'chan_theory', label: '缠论回踩', description: '辅助观察中枢、背驰和回踩确认，不是确定性交易信号。', skillId: 'chan_theory', advanced: true },
  { id: 'wave_theory', label: '波浪理论', description: '辅助判断浪形和节奏，主观性较高，需结合价格确认。', skillId: 'wave_theory', advanced: true },
  { id: 'one_rise_three_fall', label: '一阳夹三阴', description: '辅助识别短线形态与反包可能，必须结合量价和风控。', skillId: 'one_rise_three_fall', advanced: true },
];

const DATA_CONTEXT_ITEMS: DataEvidenceItem[] = [
  { key: 'quote', label: '行情', status: 'unknown' },
  { key: 'technical', label: '技术指标', status: 'unknown' },
  { key: 'fundamental', label: '基本面', status: 'unknown' },
  { key: 'portfolio', label: '持仓', status: 'unknown' },
  { key: 'watchlist', label: '观察列表', status: 'unknown' },
  { key: 'scanner', label: '扫描器', status: 'unknown' },
  { key: 'backtest', label: '回测', status: 'unknown' },
  { key: 'news', label: '新闻', status: 'unknown' },
];

const CANONICAL_SKILL_IDS = [
  'bull_trend',
  'ma_cross',
  'volume_breakout',
  'volume_pullback',
  'box_oscillation',
  'bottom_rebound',
  'chan_theory',
  'wave_theory',
  'leader_strategy',
  'emotion_cycle',
  'one_rise_three_fall',
] as const;

const CANONICAL_SKILL_ID_SET = new Set<string>(CANONICAL_SKILL_IDS);

const SKILL_TEXT_ALIAS_TO_ID: Record<string, string> = CANONICAL_SKILL_IDS.reduce(
  (acc, skillId) => {
    acc[translate('zh', `chat.skills.labels.${skillId}`)] = skillId;
    acc[translate('en', `chat.skills.labels.${skillId}`)] = skillId;
    return acc;
  },
  {} as Record<string, string>,
);

const ASSISTANT_MESSAGE_SURFACE_CLASS = 'w-full markdown-body text-[15px] leading-[1.6] text-white/90 break-words [&>p]:mb-3 [&>ul]:my-2 [&>ul]:pl-5 [&>li]:mb-1 [&>h3]:text-base [&>h3]:font-bold [&>h3]:mt-4 [&>h3]:mb-2';
const STREAMING_ASSISTANT_MESSAGE_SURFACE_CLASS = `${ASSISTANT_MESSAGE_SURFACE_CLASS} whitespace-pre-wrap`;
const CHAT_CONSOLE_TOGGLE_OPTIONS: Array<{ value: ChatConsoleMode; label: { zh: string; en: string } }> = [
  { value: 'engines', label: { zh: '上下文', en: 'Context' } },
  { value: 'history', label: { zh: '历史记录', en: 'History' } },
];

const formatRouteLabel = (route: SmartRouteResult): string => {
  if (route.symbols.length === 0) return '先输入一个具体问题';
  return `${route.symbols.join(', ')} · ${route.market} · ${route.intentLabel}`;
};

const normalizeEvidenceSymbol = (symbol: string) => symbol.toUpperCase().replace(/^HK(?=\d)/, '').replace(/\.HK$/, '');

const toMarketParam = (market: StockMarket): 'cn' | 'us' | 'hk' => {
  if (market === 'CN') return 'cn';
  if (market === 'HK') return 'hk';
  return 'us';
};

const DATA_EVIDENCE_STATUS_LABEL: Record<string, string> = {
  available: '可用',
  used: '可用',
  partial: '部分',
  stale: '陈旧',
  fallback: '备用',
  missing: '缺失',
  error: '异常',
  unknown: '未知',
};

const formatDataEvidenceStatus = (status?: string): string => (
  DATA_EVIDENCE_STATUS_LABEL[String(status || '').toLowerCase()] || '未知'
);

const evidenceSummaryText = (item: DataEvidenceItem): string => {
  if (item.key === 'quote') return item.price != null ? `${item.price}${item.changePct != null ? ` (${item.changePct}%)` : ''}` : formatDataEvidenceStatus(item.status);
  if (item.key === 'technical') return item.rsi14 != null ? `RSI ${item.rsi14}${item.ma20 != null ? ` · MA20 ${item.ma20}` : ''}` : formatDataEvidenceStatus(item.status);
  if (item.key === 'fundamental') return item.missingFields?.length ? `缺 ${item.missingFields.slice(0, 2).join(', ')}` : formatDataEvidenceStatus(item.status);
  if (item.key === 'news') return formatDataEvidenceStatus(item.status);
  if (item.key === 'portfolio') return item.hasPosition ? '有持仓' : item.status === 'missing' ? '无' : formatDataEvidenceStatus(item.status);
  if (item.key === 'watchlist') return item.inWatchlist ? '已加入' : item.status === 'missing' ? '未加入' : formatDataEvidenceStatus(item.status);
  if (item.key === 'scanner') return item.summary || (item.status === 'available' ? '最近入选' : formatDataEvidenceStatus(item.status));
  if (item.key === 'backtest') return item.resultId ? '有' : item.status === 'missing' ? '无' : formatDataEvidenceStatus(item.status);
  return item.summary || formatDataEvidenceStatus(item.status);
};

const evidenceFooterSummaryText = (item: DataEvidenceItem): string => {
  if (item.key === 'technical' && (item.status === 'available' || item.status === 'used')) return '可用';
  if (item.key === 'fundamental' && item.status === 'partial') return '部分';
  if (item.key === 'fundamental' && (item.status === 'available' || item.status === 'used')) return '可用';
  return evidenceSummaryText(item);
};

const normalizeEvidenceStatus = (status?: string): DataEvidenceStatus => {
  const value = String(status || 'unknown').toLowerCase();
  if (['used', 'available', 'partial', 'missing', 'stale', 'fallback', 'unknown', 'error'].includes(value)) {
    return value as DataEvidenceStatus;
  }
  return 'unknown';
};

const firstKnown = <T,>(...values: Array<T | null | undefined>): T | undefined =>
  values.find((value): value is T => value !== null && value !== undefined);

const buildStockEvidencePatch = (key: string, items: AgentStockEvidenceItem[]): Partial<DataEvidenceItem> | null => {
  const primary = items[0];
  if (!primary) return null;
  if (key === 'quote') {
    const quote = primary.quote;
    if (!quote) return null;
    const comparison = items
      .map((item) => item.quote?.price != null ? `${item.symbol} ${item.quote.price}` : null)
      .filter(Boolean)
      .join(' · ');
    return {
      status: normalizeEvidenceStatus(quote.status),
      source: quote.provider || 'stock evidence',
      updatedAt: quote.updatedAt || undefined,
      price: firstKnown(quote.price),
      changePct: firstKnown(quote.changePct),
      provider: quote.provider || undefined,
      summary: comparison || undefined,
    };
  }
  if (key === 'technical') {
    const technical = primary.technical;
    if (!technical) return null;
    return {
      status: normalizeEvidenceStatus(technical.status),
      source: technical.provider || 'stock_daily',
      updatedAt: technical.updatedAt || undefined,
      trend: technical.trend || undefined,
      ma5: firstKnown(technical.ma5),
      ma10: firstKnown(technical.ma10),
      ma20: firstKnown(technical.ma20),
      ma60: firstKnown(technical.ma60),
      rsi14: firstKnown(technical.rsi14),
      support: firstKnown(technical.support),
      resistance: firstKnown(technical.resistance),
      summary: technical.rsi14 != null ? `RSI ${technical.rsi14}${technical.ma20 != null ? ` · MA20 ${technical.ma20}` : ''}` : technical.trend || undefined,
    };
  }
  if (key === 'fundamental') {
    const fundamental = primary.fundamental;
    if (!fundamental) return null;
    return {
      status: normalizeEvidenceStatus(fundamental.status),
      source: fundamental.provider || 'analysis_history',
      updatedAt: fundamental.updatedAt || undefined,
      marketCap: firstKnown(fundamental.marketCap),
      peTtm: firstKnown(fundamental.peTtm),
      pb: firstKnown(fundamental.pb),
      beta: firstKnown(fundamental.beta),
      revenueTtm: firstKnown(fundamental.revenueTtm),
      netIncomeTtm: firstKnown(fundamental.netIncomeTtm),
      fcfTtm: firstKnown(fundamental.fcfTtm),
      missingFields: fundamental.missingFields,
      summary: fundamental.missingFields?.length ? `缺 ${fundamental.missingFields.slice(0, 2).join(', ')}` : undefined,
    };
  }
  if (key === 'news') {
    const news = primary.news;
    if (!news) return null;
    return {
      status: normalizeEvidenceStatus(news.status),
      source: news.provider || undefined,
      summary: news.latestHeadline || undefined,
    };
  }
  return null;
};

const buildInitialEvidenceItems = (hasSymbol: boolean): DataEvidenceItem[] =>
  DATA_CONTEXT_ITEMS.map((item) => ({ ...item, status: hasSymbol ? item.status : 'unknown' }));

const inferMarket = (symbol: string): StockMarket => {
  const normalized = symbol.toUpperCase();
  if (/^\d{6}$/.test(normalized)) return 'CN';
  if (/^(?:HK)?\d{4,5}(?:\.HK)?$/.test(normalized)) return 'HK';
  if (/^[A-Z]{1,5}(?:\.[A-Z])?$/.test(normalized)) return 'US';
  return 'unknown';
};

const detectSymbols = (text: string): string[] => {
  const normalized = text.toUpperCase();
  const matches = normalized.match(/\b(?:HK)?\d{4,6}(?:\.HK)?\b|\b[A-Z]{1,5}(?:\.[A-Z])?\b/g) ?? [];
  const ignored = new Set(['MA', 'AI', 'US', 'CN', 'HK', 'ROE', 'ETF']);
  return Array.from(new Set(matches.map((item) => item.replace(/^HK(?=\d)/, '').replace(/\.HK$/, '.HK')).filter((item) => !ignored.has(item))));
};

const classifyIntent = (text: string, symbols: string[]): Pick<SmartRouteResult, 'intent' | 'intentLabel' | 'recommendedLenses' | 'confidence'> => {
  const value = text.toLowerCase();
  if (symbols.length > 1 || /哪个|谁更强|比较|compare|vs\.?|versus/.test(value)) {
    return { intent: 'compare', intentLabel: '对比', recommendedLenses: ['综合观察', '龙头策略'], confidence: symbols.length > 1 ? 'high' : 'medium' };
  }
  if (/持有|持仓|仓位|加仓|减仓|卖|sell|reduce|trim/.test(value)) {
    return { intent: 'position_management', intentLabel: '持仓管理', recommendedLenses: ['持仓风险', '趋势跟踪'], confidence: 'high' };
  }
  if (/突破|breakout|放量|有效/.test(value)) {
    return { intent: 'breakout', intentLabel: '突破确认', recommendedLenses: ['放量突破', '均线系统'], confidence: 'high' };
  }
  if (/风险|止损|回撤|risk/.test(value)) {
    return { intent: 'risk_check', intentLabel: '风险检查', recommendedLenses: ['持仓风险', '趋势跟踪'], confidence: 'high' };
  }
  if (/短线|趋势|回踩|破位|trend/.test(value)) {
    return { intent: 'trend', intentLabel: '趋势', recommendedLenses: ['趋势跟踪', '均线系统'], confidence: 'medium' };
  }
  if (/估值|财报|roe|利润|现金流|fundamental|valuation/.test(value)) {
    return { intent: 'fundamental', intentLabel: '基本面', recommendedLenses: ['基本面质量'], confidence: 'high' };
  }
  if (/新闻|事件|财报后|政策|并购|earnings|event|catalyst/.test(value)) {
    return { intent: 'event', intentLabel: '事件', recommendedLenses: ['事件驱动', '综合观察'], confidence: 'high' };
  }
  if (/买|还能|介入|持有|buy|hold/.test(value)) {
    return { intent: 'buy_or_hold', intentLabel: '观察复核', recommendedLenses: ['综合观察', '趋势跟踪'], confidence: 'high' };
  }
  return { intent: 'general', intentLabel: '普通问股', recommendedLenses: ['综合观察', '趋势跟踪'], confidence: symbols.length > 0 ? 'medium' : 'low' };
};

const routeStockQuestion = (text: string): SmartRouteResult => {
  const symbols = detectSymbols(text);
  const markets = Array.from(new Set(symbols.map(inferMarket).filter((market) => market !== 'unknown')));
  const market: StockMarket = markets.length === 1 ? markets[0] : symbols.length ? 'unknown' : 'unknown';
  return {
    symbols,
    market,
    ...classifyIntent(text, symbols),
  };
};

function SeamlessSegmentedControl({
  value,
  onChange,
  language,
  dataTestId,
}: {
  value: ChatConsoleMode;
  onChange: (value: ChatConsoleMode) => void;
  language: 'zh' | 'en';
  dataTestId?: string;
}) {
  return (
    <div
      data-testid={dataTestId}
      className="flex w-full rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-1"
    >
      {CHAT_CONSOLE_TOGGLE_OPTIONS.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            className={`appearance-none flex-1 rounded-md border-0 px-3 py-2 text-center text-sm font-medium transition-colors ${
              active
                ? 'bg-[var(--wolfy-surface-console)] text-[color:var(--wolfy-text-primary)]'
                : 'bg-transparent text-[color:var(--wolfy-text-muted)] hover:text-[color:var(--wolfy-text-secondary)]'
            }`}
            aria-pressed={active}
            onClick={() => onChange(option.value)}
          >
            {option.label[language]}
          </button>
        );
      })}
    </div>
  );
}

function getLocalizedSkillLabel(rawLabel: string, t: (key: string, vars?: Record<string, string | number | undefined>) => string): string {
  const matchedSkillId = SKILL_TEXT_ALIAS_TO_ID[rawLabel];
  if (matchedSkillId) {
    return t(`chat.skills.labels.${matchedSkillId}`);
  }
  return rawLabel;
}

function getLocalizedSkillNameById(
  skillId: string,
  fallbackName: string,
  t: (key: string, vars?: Record<string, string | number | undefined>) => string,
): string {
  if (CANONICAL_SKILL_ID_SET.has(skillId)) return t(`chat.skills.labels.${skillId}`);
  return getLocalizedSkillLabel(fallbackName, t);
}

function getSessionBucketLabel(dateValue: string | null | undefined, language: 'zh' | 'en'): string {
  if (!dateValue) return language === 'en' ? 'Earlier' : '更早';

  const now = new Date();
  const target = new Date(dateValue);
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfTarget = new Date(target.getFullYear(), target.getMonth(), target.getDate());
  const diffDays = Math.round((startOfToday.getTime() - startOfTarget.getTime()) / 86400000);

  if (diffDays <= 0) return language === 'en' ? 'Today' : '今天';
  if (diffDays <= 7) return language === 'en' ? 'Last 7 days' : '近 7 天';
  if (diffDays <= 30) return language === 'en' ? 'Last 30 days' : '近 30 天';
  return language === 'en' ? 'Earlier' : '更早';
}

function renderAssistantMarkdownFallback(messageId: string, language: 'zh' | 'en') {
  return (
    <div
      data-testid={`chat-assistant-markdown-fallback-${messageId}`}
      aria-busy="true"
      className={`${ASSISTANT_MESSAGE_SURFACE_CLASS} min-h-[1.5rem] text-white/48`}
    >
      {language === 'en' ? 'Loading response formatting...' : '正在载入回答格式...'}
    </div>
  );
}

const ChatPage: React.FC = () => {
  const { language, t } = useI18n();
  const [searchParams, setSearchParams] = useSearchParams();
  const [input, setInput] = useState('');
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [providerHealth, setProviderHealth] = useState<AgentProviderHealthResponse | null>(null);
  const [selectedSkill, setSelectedSkill] = useState<string>('');
  const [showSkillDesc, setShowSkillDesc] = useState<string | null>(null);
  const [watchlistAction, setWatchlistAction] = useState<{ symbol: string; type: 'success' | 'error'; message: string } | null>(null);
  const [expandedThinking, setExpandedThinking] = useState<Set<string>>(new Set());
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [isFollowUpContextLoading, setIsFollowUpContextLoading] = useState(false);
  const [sendToast, setSendToast] = useState<{
    type: 'success' | 'error';
    message: string;
  } | null>(null);
  const [skillsLoadError, setSkillsLoadError] = useState<ParsedApiError | null>(null);
  const [consoleMode, setConsoleMode] = useState<ChatConsoleMode>('engines');
  const [isMobileConsoleOpen, setIsMobileConsoleOpen] = useState(false);
  const [evidenceItems, setEvidenceItems] = useState<DataEvidenceItem[]>(buildInitialEvidenceItems(false));
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [animatedAssistantMessageId, setAnimatedAssistantMessageId] = useState<string | null>(null);
  const composerTextareaRef = useRef<HTMLTextAreaElement>(null);
  const isAutoScroll = useRef(true);
  const isMountedRef = useRef(true);
  const followUpHydrationTokenRef = useRef(0);
  const followUpContextRef = useRef<ChatFollowUpContext | null>(null);
  const seenAssistantMessageIdsRef = useRef<Set<string>>(new Set());
  const hasHydratedAssistantMessagesRef = useRef(false);
  const chat = useCallback(
    (key: string, vars?: Record<string, string | number | undefined>) => CHAT_COPY_OVERRIDES[language]?.[key] || t(`chat.${key}`, vars),
    [language, t],
  );

  useEffect(() => {
    document.title = chat('documentTitle');
  }, [chat]);

  useEffect(() => () => {
    isMountedRef.current = false;
  }, []);

  const {
    messages,
    loading,
    progressSteps,
    sessionId,
    sessions,
    sessionsLoading,
    sessionLoadError,
    chatError,
    loadSessions,
    loadInitialSession,
    switchSession,
    startStream,
    stopStream,
    clearCompletionBadge,
  } = useAgentChatStore();

  useEffect(() => {
    clearCompletionBadge();
  }, [clearCompletionBadge]);

  useEffect(() => {
    loadInitialSession();
  }, [loadInitialSession]);

  const loadSkills = useCallback(async () => {
    try {
      setSkillsLoadError(null);
      const res = await agentApi.getSkills();
      setSkills(res.skills);
      setSelectedSkill('');
    } catch (error: unknown) {
      setSkillsLoadError(getParsedApiError(error));
      setSkills([]);
      setSelectedSkill('');
    }
  }, []);

  useEffect(() => {
    void loadSkills();
  }, [loadSkills]);

  useEffect(() => {
    let cancelled = false;
    void agentApi.getProviderHealth().then((res) => {
      if (!cancelled) setProviderHealth(res);
    }).catch(() => {
      if (!cancelled) setProviderHealth(null);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const availableSkillIds = new Set(skills.map((skill) => skill.id));
  const quickQuestions = QUICK_QUESTIONS.filter(
    (question) => availableSkillIds.size === 0 || availableSkillIds.has(question.skill),
  );
  const smartRoute = useMemo(() => routeStockQuestion(input), [input]);
  const primarySymbol = smartRoute.symbols[0];
  const evidenceSymbolKey = useMemo(
    () => smartRoute.symbols.slice(0, 3).map(normalizeEvidenceSymbol).join(','),
    [smartRoute.symbols],
  );
  const selectedLens = useMemo(
    () => [...PRIMARY_ANALYSIS_LENSES, ...ADVANCED_ANALYSIS_LENSES].find((lens) => (lens.skillId || '') === selectedSkill)
      ?? PRIMARY_ANALYSIS_LENSES[0],
    [selectedSkill],
  );

  useEffect(() => {
    if (!evidenceSymbolKey) {
      setEvidenceItems(buildInitialEvidenceItems(false));
      setEvidenceLoading(false);
      return undefined;
    }

    const symbols = evidenceSymbolKey.split(',').filter(Boolean);
    const primary = symbols[0];
    const market = toMarketParam(smartRoute.market === 'unknown' ? inferMarket(primary) : smartRoute.market);
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setEvidenceLoading(true);
      const nextItems = buildInitialEvidenceItems(true);

      const setItem = (key: string, patch: Partial<DataEvidenceItem>) => {
        const index = nextItems.findIndex((item) => item.key === key);
        if (index >= 0) nextItems[index] = { ...nextItems[index], ...patch };
      };

      Promise.allSettled([
        agentApi.getStockEvidence(symbols),
        watchlistApi.listWatchlistItems(),
        portfolioApi.getSnapshot(),
        scannerApi.getRecentWatchlists({ market, limitDays: 7 }),
        backtestApi.getRuleBacktestRuns({ code: primary, page: 1, limit: 1 }),
      ]).then(([stockEvidenceResult, watchlistResult, portfolioResult, scannerResult, backtestResult]) => {
        if (cancelled) return;

        if (stockEvidenceResult.status === 'fulfilled') {
          const stockEvidenceItems = stockEvidenceResult.value.items || [];
          for (const key of ['quote', 'technical', 'fundamental', 'news']) {
            const patch = buildStockEvidencePatch(key, stockEvidenceItems);
            if (patch) setItem(key, patch);
          }
        } else {
          setItem('quote', { status: 'error', source: 'stock evidence' });
          setItem('technical', { status: 'unknown', source: 'stock evidence' });
          setItem('fundamental', { status: 'unknown', source: 'stock evidence' });
          setItem('news', { status: 'unknown', source: 'stock evidence' });
        }

        if (watchlistResult.status === 'fulfilled') {
          const match = (watchlistResult.value.items || []).find((item) => normalizeEvidenceSymbol(item.symbol) === primary);
          if (match) {
            setItem('watchlist', {
              status: 'available',
              source: 'watchlist',
              updatedAt: match.updatedAt || match.createdAt || undefined,
              inWatchlist: true,
              summary: '已加入',
            });
            const scannerIntel = match.intelligence?.scanner;
            if (scannerIntel?.status) {
              setItem('scanner', {
                status: scannerIntel.status === 'selected' ? 'available' : 'missing',
                source: 'watchlist intelligence',
                updatedAt: scannerIntel.lastScannedAt || undefined,
                summary: scannerIntel.status === 'selected' ? `最近入选 #${scannerIntel.lastRank ?? '-'}` : String(scannerIntel.status),
              });
            }
            const backtestIntel = match.intelligence?.backtest;
            if (backtestIntel?.lastResultId) {
              setItem('backtest', {
                status: 'available',
                source: 'watchlist intelligence',
                updatedAt: backtestIntel.testedAt || undefined,
                resultId: backtestIntel.lastResultId,
                returnPct: backtestIntel.totalReturnPct ?? undefined,
                summary: backtestIntel.totalReturnPct != null ? `${backtestIntel.totalReturnPct.toFixed(1)}%` : '有结果',
              });
            }
          } else {
            setItem('watchlist', { status: 'missing', source: 'watchlist', inWatchlist: false, summary: '未加入' });
          }
        } else {
          setItem('watchlist', { status: 'error', source: 'watchlist' });
        }

        if (portfolioResult.status === 'fulfilled') {
          const position = (portfolioResult.value.accounts || [])
            .flatMap((account) => account.positions || [])
            .find((item) => normalizeEvidenceSymbol(item.symbol) === primary && Number(item.quantity || 0) !== 0);
          setItem('portfolio', {
            status: position ? 'available' : 'missing',
            source: 'portfolio snapshot',
            updatedAt: portfolioResult.value.asOf,
            hasPosition: Boolean(position),
            summary: position ? `${position.quantity} 股` : '无持仓',
          });
        } else {
          setItem('portfolio', { status: 'error', source: 'portfolio snapshot' });
        }

        if (scannerResult.status === 'fulfilled') {
          const run = (scannerResult.value.items || []).find((item) => (item.topSymbols || []).map(normalizeEvidenceSymbol).includes(primary));
          if (run) {
            setItem('scanner', {
              status: 'available',
              source: `scanner run #${run.id}`,
              updatedAt: run.completedAt || run.runAt || undefined,
              summary: '最近入选',
            });
          } else if (nextItems.find((item) => item.key === 'scanner')?.status === 'unknown') {
            setItem('scanner', { status: 'missing', source: 'scanner recent', summary: '未入选' });
          }
        } else if (nextItems.find((item) => item.key === 'scanner')?.status === 'unknown') {
          setItem('scanner', { status: 'error', source: 'scanner recent' });
        }

        if (backtestResult.status === 'fulfilled') {
          const run = (backtestResult.value.items || []).find((item) => normalizeEvidenceSymbol(item.code || '') === primary);
          if (run) {
            setItem('backtest', {
              status: run.status === 'completed' ? 'available' : 'stale',
              source: `rule backtest #${run.id}`,
              updatedAt: run.completedAt || run.runAt || undefined,
              resultId: run.id,
              returnPct: run.totalReturnPct ?? undefined,
              summary: run.totalReturnPct != null ? `${run.totalReturnPct.toFixed(1)}%` : String(run.status),
            });
          } else if (nextItems.find((item) => item.key === 'backtest')?.status === 'unknown') {
            setItem('backtest', { status: 'missing', source: 'rule backtest history', summary: '无结果' });
          }
        } else if (nextItems.find((item) => item.key === 'backtest')?.status === 'unknown') {
          setItem('backtest', { status: 'error', source: 'rule backtest history' });
        }

        if (followUpContextRef.current?.previous_price != null) {
          if (nextItems.find((item) => item.key === 'quote')?.status === 'unknown') {
            setItem('quote', { status: 'available', source: 'previous report', summary: String(followUpContextRef.current.previous_price) });
          }
        }

        setEvidenceItems(nextItems);
      }).finally(() => {
        if (!cancelled) setEvidenceLoading(false);
      });
    }, 300);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [evidenceSymbolKey, smartRoute.market]);
  const contextPaneSummary = language === 'en' ? 'Source, lenses, and evidence' : '来源、视角与证据';
  const composerDisclaimer = language === 'en'
    ? 'For research only. Not investment advice.'
    : '仅供研究参考，不构成投资建议。';
  const chatConsoleTitle = language === 'en' ? 'Research context' : '研究上下文';
  const mobileConsoleTitle = language === 'en' ? 'Research context' : '研究上下文';
  const hasMessages = messages.length > 0;
  const showEmptyState = !hasMessages && !loading;

  const buildStructuredChatContext = useCallback(() => {
    const baseContext = followUpContextRef.current ? { ...followUpContextRef.current } : {};
    const evidenceByKey = Object.fromEntries(
      evidenceItems.map(({
        key,
        status,
        source,
        updatedAt,
        summary,
        inWatchlist,
        hasPosition,
        resultId,
        returnPct,
        price,
        changePct,
        provider,
        trend,
        ma5,
        ma10,
        ma20,
        ma60,
        rsi14,
        support,
        resistance,
        marketCap,
        peTtm,
        pb,
        beta,
        revenueTtm,
        netIncomeTtm,
        fcfTtm,
        missingFields,
      }) => [
        key,
        {
          status,
          source,
          updatedAt,
          summary,
          ...(inWatchlist != null ? { inWatchlist } : {}),
          ...(hasPosition != null ? { hasPosition } : {}),
          ...(resultId != null ? { resultId } : {}),
          ...(returnPct != null ? { returnPct } : {}),
          ...(price != null ? { price } : {}),
          ...(changePct != null ? { changePct } : {}),
          ...(provider != null ? { provider } : {}),
          ...(trend != null ? { trend } : {}),
          ...(ma5 != null ? { ma5 } : {}),
          ...(ma10 != null ? { ma10 } : {}),
          ...(ma20 != null ? { ma20 } : {}),
          ...(ma60 != null ? { ma60 } : {}),
          ...(rsi14 != null ? { rsi14 } : {}),
          ...(support != null ? { support } : {}),
          ...(resistance != null ? { resistance } : {}),
          ...(marketCap != null ? { marketCap } : {}),
          ...(peTtm != null ? { peTtm } : {}),
          ...(pb != null ? { pb } : {}),
          ...(beta != null ? { beta } : {}),
          ...(revenueTtm != null ? { revenueTtm } : {}),
          ...(netIncomeTtm != null ? { netIncomeTtm } : {}),
          ...(fcfTtm != null ? { fcfTtm } : {}),
          ...(missingFields != null ? { missingFields } : {}),
        },
      ]),
    );
    return {
      ...baseContext,
      stock_chat: {
        response_mode: 'structured_stock_analysis_v1',
        answer_sections: STOCK_CHAT_ANSWER_SECTIONS,
        instruction: '请用中文简洁输出：结论、关键依据、关键价位、风险、观察计划、数据可信度。数据缺失必须明确说明；不要承诺确定性收益。',
        selected_lens: selectedLens.label,
        data_context: evidenceItems.map(({ key, label, status, source, updatedAt }) => ({ key, label, status, source, updatedAt })),
        smart_route: {
          symbols: smartRoute.symbols,
          market: smartRoute.market,
          intent: smartRoute.intent,
          recommended_lenses: smartRoute.recommendedLenses,
          confidence: smartRoute.confidence,
        },
        stock_context: {
          symbols: smartRoute.symbols.slice(0, 3),
          market: smartRoute.market,
          intent: smartRoute.intent,
          recommended_lenses: smartRoute.recommendedLenses,
          evidence: evidenceByKey,
        },
      },
    };
  }, [evidenceItems, selectedLens.label, smartRoute]);

  const buildEvidenceFooter = useCallback(() => ({
    provider: providerHealth?.currentProvider || providerHealth?.providers.find((item) => item.selected)?.label || '自动/未知',
    model: providerHealth?.currentModel || providerHealth?.providers.find((item) => item.selected)?.model || undefined,
    lenses: smartRoute.recommendedLenses.length ? smartRoute.recommendedLenses : [selectedLens.label],
    items: evidenceItems
      .filter((item) => ['quote', 'technical', 'fundamental', 'news', 'portfolio', 'watchlist', 'scanner', 'backtest'].includes(item.key))
      .map((item) => ({
        label: item.key === 'scanner' ? 'Scanner' : item.key === 'technical' ? '技术' : item.label,
        status: item.status,
        summary: evidenceFooterSummaryText(item),
      })),
  }), [evidenceItems, providerHealth, selectedLens.label, smartRoute.recommendedLenses]);

  const handleStartNewChat = useCallback(() => {
    followUpContextRef.current = null;
    useAgentChatStore.getState().startNewChat();
  }, []);

  const handleSwitchSession = useCallback((targetSessionId: string) => {
    switchSession(targetSessionId);
  }, [switchSession]);

  const confirmDelete = useCallback(() => {
    if (!deleteConfirmId) return;
    agentApi.deleteChatSession(deleteConfirmId).then(() => {
      void loadSessions();
      if (deleteConfirmId === sessionId) {
        handleStartNewChat();
      }
    }).catch(() => {});
    setDeleteConfirmId(null);
  }, [deleteConfirmId, handleStartNewChat, loadSessions, sessionId]);

  useEffect(() => {
    const stock = searchParams.get('stock');
    const name = searchParams.get('name');
    const recordId = searchParams.get('recordId');
    if (!stock) return;

    const hydrationToken = ++followUpHydrationTokenRef.current;
    setInput(buildFollowUpPrompt(stock, name));
    followUpContextRef.current = {
      stock_code: stock,
      stock_name: name,
    };
    if (recordId) {
      setIsFollowUpContextLoading(true);
    }
    void resolveChatFollowUpContext({
      stockCode: stock,
      stockName: name,
      recordId: recordId ? Number(recordId) : undefined,
    }).then((context) => {
      if (!isMountedRef.current || followUpHydrationTokenRef.current !== hydrationToken) return;
      followUpContextRef.current = context;
    }).finally(() => {
      if (isMountedRef.current && followUpHydrationTokenRef.current === hydrationToken) {
        setIsFollowUpContextLoading(false);
      }
    });
    setSearchParams({}, { replace: true });
  }, [searchParams, setSearchParams]);

  const handleSend = useCallback(
    async (overrideMessage?: string, overrideSkill?: string) => {
      const msgText = overrideMessage || input.trim();
      if (!msgText || loading) return;
      isAutoScroll.current = true;
      const usedSkill = overrideSkill || selectedSkill;
      const skill = skills.find((s) => s.id === usedSkill);
      const usedSkillName = skill
        ? getLocalizedSkillNameById(skill.id, skill.name, t)
        : (usedSkill ? getLocalizedSkillLabel(usedSkill, t) : chat('skills.general'));

      const payload = {
        message: msgText,
        session_id: sessionId,
        skills: usedSkill ? [usedSkill] : undefined,
        context: buildStructuredChatContext(),
      };
      followUpHydrationTokenRef.current += 1;
      followUpContextRef.current = null;
      setIsFollowUpContextLoading(false);
      setInput('');
      await startStream(payload, { skillName: usedSkillName, evidenceFooter: buildEvidenceFooter() });
    },
    [buildEvidenceFooter, buildStructuredChatContext, chat, input, loading, selectedSkill, sessionId, skills, startStream, t],
  );

  const handleStopGeneration = useCallback(() => {
    stopStream();
  }, [stopStream]);

  const handleExportSession = useCallback(() => {
    downloadSession(messages);
  }, [messages]);

  const handleNotifySession = useCallback(async () => {
    if (sending) return;
    setSending(true);
    setSendToast(null);
    try {
      const content = formatSessionAsMarkdown(messages);
      await agentApi.sendChat(content);
      setSendToast({ type: 'success', message: chat('notifySuccess') });
      setTimeout(() => setSendToast(null), 3000);
    } catch (err) {
      const parsed = getParsedApiError(err);
      setSendToast({
        type: 'error',
        message: parsed.message || chat('notifyFailed'),
      });
      setTimeout(() => setSendToast(null), 5000);
    } finally {
      setSending(false);
    }
  }, [chat, messages, sending]);

  const startNewChatDesktopButton = useSafariWarmActivation<HTMLButtonElement>(handleStartNewChat);
  const startNewChatMobileButton = useSafariWarmActivation<HTMLButtonElement>(handleStartNewChat);
  const openConsoleButton = useSafariWarmActivation<HTMLButtonElement>(() => setIsMobileConsoleOpen(true));
  const sendMessageButton = useSafariWarmActivation<HTMLButtonElement>(() => {
    void handleSend();
  });

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  const handleQuickQuestion = (q: QuickQuestion) => {
    setSelectedSkill(q.skill);
    void handleSend(chat(`quickQuestions.${q.id}`), q.skill);
  };

  const handleSelectLens = (lens: AnalysisLens) => {
    setSelectedSkill(lens.skillId || '');
  };

  const handleAddWatchlist = useCallback(async (symbol: string, market: StockMarket) => {
    try {
      await watchlistApi.addWatchlistItem({
        symbol,
        market: market === 'unknown' ? 'us' : market.toLowerCase(),
        source: 'scanner',
        notes: language === 'zh' ? '来自问股智能路由' : 'From Stock Chat smart route',
      });
      setWatchlistAction({ symbol, type: 'success', message: `${symbol} 已加入观察列表` });
    } catch {
      setWatchlistAction({ symbol, type: 'error', message: `${symbol} 加入观察列表失败` });
    }
  }, [language]);

  const toggleThinking = (msgId: string) => {
    setExpandedThinking((prev) => {
      const next = new Set(prev);
      if (next.has(msgId)) next.delete(msgId);
      else next.add(msgId);
      return next;
    });
  };

  const getCurrentStage = (steps: ProgressStep[]): string => {
    if (steps.length === 0) return chat('stage.connecting');
    const last = steps[steps.length - 1];
    if (last.type === 'thinking') return last.message || chat('stage.thinking');
    if (last.type === 'tool_start') return chat('stage.toolRunning', { tool: last.display_name || last.tool });
    if (last.type === 'tool_done') return chat('stage.toolDone', { tool: last.display_name || last.tool });
    if (last.type === 'generating') return last.message || chat('stage.generating');
    return chat('stage.processing');
  };

  const renderThinkingBlock = (msg: Message) => {
    if (!msg.thinkingSteps || msg.thinkingSteps.length === 0) return null;
    const isExpanded = expandedThinking.has(msg.id);
    const toolSteps = msg.thinkingSteps.filter((s) => s.type === 'tool_done');
    const totalDuration = toolSteps.reduce((sum, s) => sum + (s.duration || 0), 0);
    const summary = chat('thinking.summary', { count: toolSteps.length, duration: totalDuration.toFixed(1) });

    return (
      <button
        type="button"
        className="mb-2 flex w-full items-center gap-2 text-left text-xs text-muted-text transition-colors hover:text-secondary-text"
        aria-label={chat('thinking.toggleLabel')}
        onClick={() => toggleThinking(msg.id)}
      >
        <svg
          className={`h-3 w-3 flex-shrink-0 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 5l7 7-7 7"
          />
        </svg>
        <span className="flex items-center gap-1.5">
          <span className="opacity-60">{chat('thinking.toggleLabel')}</span>
          <span className="text-muted-text/50">·</span>
          <span className="opacity-50">{summary}</span>
        </span>
      </button>
    );
  };

  const renderThinkingDetails = (steps: ProgressStep[]) => (
    <div className="mb-3 space-y-0.5 animate-fade-in">
      {steps.map((step, idx) => {
        let icon = '⋯';
        let text = '';
        let colorClass = 'text-muted-text';
        if (step.type === 'thinking') {
          icon = '🤔';
          text = step.message || chat('thinking.stepDefault', { step: step.step });
          colorClass = 'text-secondary-text';
        } else if (step.type === 'tool_start') {
          icon = '⚙️';
          text = chat('stage.toolRunning', { tool: step.display_name || step.tool });
          colorClass = 'text-secondary-text';
        } else if (step.type === 'tool_done') {
          icon = step.success ? '✅' : '❌';
          text = `${step.display_name || step.tool} (${step.duration}s)`;
          colorClass = step.success ? 'text-success' : 'text-danger';
        } else if (step.type === 'generating') {
          icon = '✍️';
          text = step.message || chat('thinking.generatingDefault');
          colorClass = 'text-[hsl(var(--accent-primary-hsl))]';
        }
        return (
          <div key={idx} className={`flex items-center gap-2 py-0.5 text-xs ${colorClass}`}>
            <span className="w-4 flex-shrink-0 text-center">{icon}</span>
            <span className="leading-relaxed">{text}</span>
          </div>
        );
      })}
    </div>
  );

  const renderEvidenceFooter = (msg: Message) => {
    const footer = msg.evidenceFooter;
    if (!footer) return null;
    const dataText = (footer.items || [])
      .map((item) => `${item.label} ${item.summary || formatDataEvidenceStatus(item.status)}`)
      .join(' · ');
    return (
      <details
        data-testid={`chat-answer-evidence-footer-${msg.id}`}
        className="mt-3 rounded-xl border border-white/8 bg-white/[0.025] px-3 py-2 text-[11px] text-white/46"
      >
        <summary className="cursor-pointer list-none font-mono text-[10px] uppercase tracking-widest text-white/40">
          本次使用
        </summary>
        <div className="mt-2 space-y-1">
          <p>分析方式: <span className="font-mono text-white/72">自动研究引擎</span></p>
          <p>视角: {(footer.lenses || []).join(' / ') || '综合观察'}</p>
          <p>数据: {dataText || '未知'}</p>
        </div>
      </details>
    );
  };

  const latestAssistantMessageId = useMemo(
    () => [...messages].reverse().find((msg) => msg.role === 'assistant')?.id ?? null,
    [messages],
  );

  const isGenerating = loading;

  const groupedSessions = useMemo(() => {
    const buckets = new Map<string, typeof sessions>();
    sessions.forEach((session) => {
      const label = getSessionBucketLabel(session.last_active || session.created_at, language);
      const existing = buckets.get(label) ?? [];
      existing.push(session);
      buckets.set(label, existing);
    });
    return Array.from(buckets.entries());
  }, [language, sessions]);

  useEffect(() => {
    const assistantIds = messages
      .filter((msg) => msg.role === 'assistant')
      .map((msg) => msg.id);
    const seenAssistantIds = seenAssistantMessageIdsRef.current;

    if (!hasHydratedAssistantMessagesRef.current) {
      assistantIds.forEach((id) => seenAssistantIds.add(id));
      hasHydratedAssistantMessagesRef.current = true;
      return;
    }

    const newAssistantIds = assistantIds.filter((id) => !seenAssistantIds.has(id));
    if (newAssistantIds.length > 0) {
      const newestAssistantId = newAssistantIds[newAssistantIds.length - 1];
      setAnimatedAssistantMessageId(newestAssistantId);
      newAssistantIds.forEach((id) => seenAssistantIds.add(id));
      return;
    }

    assistantIds.forEach((id) => seenAssistantIds.add(id));
  }, [messages]);

  useEffect(() => {
    const textarea = composerTextareaRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
  }, [input]);

  const renderConsoleActions = (compact = false) => (
    <div className={`flex items-center ${compact ? 'gap-2' : 'gap-2.5'}`}>
      <button
        ref={startNewChatDesktopButton.ref}
        type="button"
        onClick={startNewChatDesktopButton.onClick}
        onPointerUp={startNewChatDesktopButton.onPointerUp}
        aria-label={chat('newChatTitle')}
        className={`flex items-center justify-center rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] text-sm font-medium text-[color:var(--wolfy-text-primary)] transition-colors hover:border-[color:var(--wolfy-divider)] ${
          compact ? 'h-10 px-3' : 'px-4 py-2.5'
        }`}
      >
        + {language === 'en' ? 'New chat' : '新对话'}
      </button>
      {hasMessages ? (
        <>
          <button
            type="button"
            onClick={handleExportSession}
            className="flex h-10 w-10 items-center justify-center rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] text-[color:var(--wolfy-text-secondary)] transition-colors hover:border-[color:var(--wolfy-divider)] hover:text-[color:var(--wolfy-text-primary)]"
            title={chat('exportTitle')}
          >
            <Download className="h-4 w-4" />
          </button>
          <button
            type="button"
            className="flex h-10 w-10 items-center justify-center rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] text-[color:var(--wolfy-text-secondary)] transition-colors hover:border-[color:var(--wolfy-divider)] hover:text-[color:var(--wolfy-text-primary)] disabled:cursor-not-allowed disabled:opacity-50"
            onClick={() => {
              void handleNotifySession();
            }}
            disabled={sending}
            title={chat('notifyTitle')}
          >
            {sending ? (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-[color:var(--wolfy-divider)] border-t-[color:var(--wolfy-text-primary)]" />
            ) : (
              <SendHorizontal className="h-4 w-4" />
            )}
          </button>
        </>
      ) : null}
    </div>
  );

  const renderHistoryList = (testId: string) => (
    <>
      {sessionLoadError ? (
        <ApiErrorAlert
          error={sessionLoadError}
          className="mb-3"
          actionLabel={chat('retryLoadSessions')}
          onAction={() => {
            void loadSessions();
          }}
        />
      ) : null}

      <div
        data-testid={testId}
        className="flex flex-1 min-h-0 flex-col gap-1 overflow-y-auto no-scrollbar"
      >
        {sessionsLoading ? (
          <div className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-4 text-xs text-[color:var(--wolfy-text-muted)]">
            {chat('loadingSessions')}
          </div>
        ) : sessions.length === 0 ? (
          <div className="rounded-lg border border-dashed border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-4 text-xs text-[color:var(--wolfy-text-muted)]">
            {chat('emptySessions')}
          </div>
        ) : (
          groupedSessions.map(([bucketLabel, bucketSessions]) => (
            <section key={bucketLabel} className="flex flex-col gap-1.5 pb-3">
              <p className="px-2 text-[11px] text-[color:var(--wolfy-text-muted)]">{bucketLabel}</p>
              {bucketSessions.map((s) => (
                <div
                  key={s.session_id}
                  role="button"
                  tabIndex={0}
                  onClick={() => handleSwitchSession(s.session_id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleSwitchSession(s.session_id);
                    }
                  }}
                  className={`group rounded-lg border px-3 py-3 transition-colors ${
                    s.session_id === sessionId
                      ? 'border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-console)]'
                      : 'border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] hover:border-[color:var(--wolfy-divider)]'
                  }`}
                  aria-label={chat('switchToConversation', { title: s.title })}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-[color:var(--wolfy-text-primary)]">{s.title}</p>
                      <div className="mt-2 flex items-center gap-2 text-[11px] text-[color:var(--wolfy-text-muted)]">
                        <span>{chat('messageCount', { count: s.message_count })}</span>
                        {s.last_active ? <span className="h-1 w-1 rounded-full bg-[color:var(--wolfy-divider)]" /> : null}
                        {s.last_active ? (
                          <span>
                            {new Date(s.last_active).toLocaleDateString(language === 'en' ? 'en-US' : 'zh-CN', {
                              month: 'short',
                              day: 'numeric',
                            })}
                          </span>
                        ) : null}
                      </div>
                    </div>
                    <button
                      type="button"
                      className="rounded-md p-1 text-[color:var(--wolfy-text-muted)] opacity-0 transition-colors hover:bg-[var(--wolfy-surface-console)] hover:text-[color:var(--wolfy-market-down)] group-hover:opacity-100"
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeleteConfirmId(s.session_id);
                      }}
                      title={chat('deleteConversationAction')}
                    >
                      <svg
                        className="h-3.5 w-3.5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                        />
                      </svg>
                    </button>
                  </div>
                </div>
              ))}
            </section>
          ))
        )}
      </div>
    </>
  );

  const renderDataEvidencePanel = (testId = 'chat-evidence-panel') => (
    <section data-testid={testId} className="flex flex-col gap-0">
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-[11px] text-[color:var(--wolfy-text-secondary)]">
          {language === 'en' ? 'Data Evidence' : '数据证据'}
        </p>
        <p className="text-[10px] font-mono uppercase text-[color:var(--wolfy-text-muted)]">
          {evidenceLoading
            ? (language === 'en' ? 'checking' : '检查中')
            : smartRoute.symbols.length
              ? (language === 'en' ? 'read-only' : '只读')
              : (language === 'en' ? 'idle' : '待命')}
        </p>
      </div>
      {smartRoute.symbols.length === 0 ? (
        <div className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] px-3 py-2 text-xs text-[color:var(--wolfy-text-muted)]">
          先输入具体标的
        </div>
      ) : null}
      <div className="flex flex-col divide-y divide-[color:var(--wolfy-divider)] rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)]">
        {evidenceItems.map((item) => (
          <div key={item.key} className="min-w-0 px-3 py-2">
            <div className="flex min-w-0 items-center justify-between gap-2">
              <span className="truncate text-xs text-[color:var(--wolfy-text-secondary)]">{item.label}</span>
              <span className={`font-mono text-[10px] uppercase ${
                item.status === 'available'
                  || item.status === 'used'
                  ? 'text-[color:var(--wolfy-market-up)]'
                  : item.status === 'partial' || item.status === 'stale' || item.status === 'fallback'
                    ? 'text-amber-300'
                    : item.status === 'missing' || item.status === 'error'
                    ? 'text-[color:var(--wolfy-market-down)]'
                    : 'text-[color:var(--wolfy-text-muted)]'
              }`}>
                {formatDataEvidenceStatus(item.status)}
              </span>
            </div>
            <p className="mt-1 truncate text-[10px] text-[color:var(--wolfy-text-muted)]">{item.summary || (language === 'en' ? 'Data readiness noted' : '数据状态已标注')}</p>
          </div>
        ))}
      </div>
    </section>
  );

  const renderQuickActions = () => {
    if (!primarySymbol) return null;
    const symbolMarket = smartRoute.market === 'unknown' ? inferMarket(primarySymbol) : smartRoute.market;
    const encodedSymbol = encodeURIComponent(primarySymbol);
    const encodedMarket = encodeURIComponent(symbolMarket);
    const watchlistEvidence = evidenceItems.find((item) => item.key === 'watchlist');
    const portfolioEvidence = evidenceItems.find((item) => item.key === 'portfolio');
    const backtestEvidence = evidenceItems.find((item) => item.key === 'backtest');
    const isInWatchlist = watchlistEvidence?.inWatchlist === true;
    const hasPosition = portfolioEvidence?.hasPosition === true;
    const hasBacktest = Boolean(backtestEvidence?.resultId);
    return (
      <section
        data-testid="chat-quick-actions"
        className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3"
      >
        <p className="mb-2 text-[11px] text-[color:var(--wolfy-text-secondary)]">
          {language === 'en' ? 'Quick Actions' : '快捷操作'}
        </p>
        <div className="grid min-w-0 gap-2 sm:grid-cols-2">
          <a
            href={`/backtest?symbol=${encodedSymbol}&market=${encodedMarket}&source=chat`}
            className="rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] px-3 py-2 text-xs text-[color:var(--wolfy-text-secondary)] hover:border-[color:var(--wolfy-divider)] hover:text-[color:var(--wolfy-text-primary)]"
            aria-label={`回测 ${primarySymbol}`}
          >
            {hasBacktest ? '查看最近回测' : '运行回测'}
          </a>
          <button
            type="button"
            className="rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] px-3 py-2 text-left text-xs text-[color:var(--wolfy-text-secondary)] hover:border-[color:var(--wolfy-divider)] hover:text-[color:var(--wolfy-text-primary)] disabled:cursor-not-allowed disabled:opacity-50"
            onClick={() => {
              if (isInWatchlist) return;
              void handleAddWatchlist(primarySymbol, symbolMarket);
            }}
            disabled={isInWatchlist}
            aria-label={`${isInWatchlist ? '已在观察列表' : '加入观察列表'} ${primarySymbol}`}
          >
            {isInWatchlist ? '已在观察列表' : '加入观察列表'}
          </button>
          <a
            href={`/portfolio?symbol=${encodedSymbol}`}
            className="rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] px-3 py-2 text-xs text-[color:var(--wolfy-text-secondary)] hover:border-[color:var(--wolfy-divider)] hover:text-[color:var(--wolfy-text-primary)]"
            aria-label={`查看持仓 ${primarySymbol}`}
          >
            {hasPosition ? '查看持仓' : '未持仓'}
          </a>
          <a
            href={`/scanner?symbol=${encodedSymbol}&market=${encodedMarket}`}
            className="rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] px-3 py-2 text-xs text-[color:var(--wolfy-text-secondary)] hover:border-[color:var(--wolfy-divider)] hover:text-[color:var(--wolfy-text-primary)]"
            aria-label={`查看扫描器证据 ${primarySymbol}`}
          >
            扫描器证据
          </a>
          <a
            href={`/?symbol=${encodedSymbol}`}
            className="rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] px-3 py-2 text-xs text-[color:var(--wolfy-text-secondary)] hover:border-[color:var(--wolfy-divider)] hover:text-[color:var(--wolfy-text-primary)]"
            aria-label={`打开分析报告 ${primarySymbol}`}
          >
            分析报告
          </a>
        </div>
        {watchlistAction?.symbol === primarySymbol ? (
          <p className={`mt-2 text-xs ${watchlistAction.type === 'success' ? 'text-[color:var(--wolfy-market-up)]' : 'text-[color:var(--wolfy-market-down)]'}`}>
            {watchlistAction.message}
          </p>
        ) : null}
      </section>
    );
  };

  const renderContextBriefRail = (testId = 'chat-context-brief-rail') => {
    const availableCount = evidenceItems.filter((item) => item.status === 'available' || item.status === 'used').length;
    const partialCount = evidenceItems.filter((item) => item.status === 'partial' || item.status === 'stale' || item.status === 'fallback').length;
    const missingCount = evidenceItems.filter((item) => item.status === 'missing' || item.status === 'error').length;
    const routeText = smartRoute.symbols.length
      ? formatRouteLabel(smartRoute)
      : (language === 'en' ? 'Ask about a symbol or scenario' : '输入标的或情景后生成上下文');
    const lensText = smartRoute.symbols.length
      ? smartRoute.recommendedLenses.slice(0, 2).join(' / ')
      : selectedLens.label;
    return (
      <section
        data-testid={testId}
        className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3 text-left"
      >
        <p className="text-[11px] text-[color:var(--wolfy-text-secondary)]">
          {language === 'en' ? 'Research context' : '研究上下文'}
        </p>
        <div className="mt-3 grid gap-2">
          {[
            { label: language === 'en' ? 'Question' : '问题', value: smartRoute.symbols.length ? routeText : (language === 'en' ? 'Waiting for question' : '等待问题') },
            { label: language === 'en' ? 'Context' : '上下文', value: smartRoute.symbols.length ? lensText : (language === 'en' ? 'No context yet' : '暂无上下文') },
            {
              label: language === 'en' ? 'Data check' : '数据检查',
              value: smartRoute.symbols.length
                ? (language === 'en'
                  ? `${availableCount} ready · ${partialCount} partial · ${missingCount} missing`
                  : `${availableCount} 可用 · ${partialCount} 部分 · ${missingCount} 缺失`)
                : (language === 'en' ? 'Checks data during analysis' : '分析时检查数据'),
            },
          ].map((item) => (
            <div key={item.label} className="rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] px-3 py-2">
              <p className="text-[10px] text-[color:var(--wolfy-text-muted)]">{item.label}</p>
              <p className="mt-1 truncate text-sm font-medium text-[color:var(--wolfy-text-primary)]">{item.value}</p>
            </div>
          ))}
        </div>
      </section>
    );
  };

  const quoteEvidence = evidenceItems.find((item) => item.key === 'quote');
  const renderSmartRouteStrip = () => (
    <div data-testid="chat-smart-route-strip">
      <ConsoleStatusStrip
        items={[
          {
            label: language === 'en' ? 'Route' : '智能路由',
            value: formatRouteLabel(smartRoute),
          },
          {
            label: language === 'en' ? 'Lens' : '推荐视角',
            value: smartRoute.symbols.length > 0 ? smartRoute.recommendedLenses.join(' / ') : selectedLens.label,
          },
          {
            label: language === 'en' ? 'Price' : '价格',
            value: quoteEvidence?.price != null
              ? `${quoteEvidence.price}${quoteEvidence.changePct != null ? ` · ${quoteEvidence.changePct}%` : ''}`
              : (language === 'en' ? 'Waiting' : '等待标的'),
          },
        ]}
      />
    </div>
  );

  const renderLensButton = (lens: AnalysisLens) => {
    const isActive = selectedLens.id === lens.id;
    const isAvailable = !lens.skillId || availableSkillIds.size === 0 || availableSkillIds.has(lens.skillId);
    return (
      <button
        key={lens.id}
        type="button"
        className={`min-w-0 rounded-md border px-3 py-2 text-left transition-colors ${
          isActive
            ? 'border-[color:var(--wolfy-accent)] bg-[color:color-mix(in_srgb,var(--wolfy-accent)_12%,transparent)] text-[color:var(--wolfy-text-primary)]'
            : 'border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] text-[color:var(--wolfy-text-secondary)] hover:border-[color:var(--wolfy-divider)] hover:text-[color:var(--wolfy-text-primary)]'
        } disabled:cursor-not-allowed disabled:opacity-40`}
        onClick={() => handleSelectLens(lens)}
        disabled={!isAvailable}
        onMouseEnter={() => setShowSkillDesc(lens.id)}
        onMouseLeave={() => setShowSkillDesc(null)}
        title={lens.description}
      >
        <span className="block truncate text-xs font-semibold">{lens.label}</span>
        {isActive || showSkillDesc === lens.id ? (
          <span className="mt-1 block line-clamp-2 text-[10px] leading-relaxed text-[color:var(--wolfy-text-muted)]">{lens.description}</span>
        ) : null}
      </button>
    );
  };

  const renderControlPanel = (testId: string) => {
    const primaryVisibleLenses = PRIMARY_ANALYSIS_LENSES.slice(0, 4);
    const secondaryLenses = [...PRIMARY_ANALYSIS_LENSES.slice(4), ...ADVANCED_ANALYSIS_LENSES];
    return (
      <div data-testid={testId} className="flex flex-col gap-3">
        <section
          data-testid="chat-lens-section"
          className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3"
        >
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="text-[11px] text-[color:var(--wolfy-text-secondary)]">分析视角</p>
            <p className="truncate text-[10px] text-[color:var(--wolfy-text-muted)]">{selectedLens.label}</p>
          </div>
          <div data-testid="chat-strategy-grid" className="grid grid-cols-2 gap-2">
            {primaryVisibleLenses.map(renderLensButton)}
          </div>
          <GuidedDisclosure
            title={language === 'en' ? 'More lenses' : '更多视角'}
            summary={language === 'en' ? 'Advanced frameworks stay collapsed until needed.' : '高级框架默认折叠，只作辅助观察。'}
            className="mt-3"
            beginner={language === 'en'
              ? 'Choose one lens when you want the answer to emphasize a specific evidence style.'
              : '需要强调某类证据时，再切换特定研究视角。'}
            professional={(
              <div className="grid grid-cols-1 gap-2">
                {secondaryLenses.map(renderLensButton)}
              </div>
            )}
          />
        </section>

        <section
          data-testid="chat-data-context-section"
          className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3"
        >
          <p className="mb-2 text-[11px] text-[color:var(--wolfy-text-secondary)]">数据上下文</p>
          <div className="flex flex-wrap gap-1.5">
            {evidenceItems.slice(0, 5).map((item) => (
              <span key={item.key} className="rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] px-2 py-1 text-[10px] text-[color:var(--wolfy-text-secondary)]">
                {item.label} · <span className="text-[color:var(--wolfy-text-muted)]">{formatDataEvidenceStatus(item.status)}</span>
              </span>
            ))}
          </div>
        </section>

        <ConsoleDisclosure
          title={language === 'en' ? 'Evidence detail' : '证据明细'}
          summary={language === 'en' ? 'Open only when you need source-by-source readiness.' : '需要逐项查看证据状态时再展开。'}
          className="bg-[var(--wolfy-surface-input)]"
        >
          {renderDataEvidencePanel()}
        </ConsoleDisclosure>
        <div className="hidden lg:block">
          {renderQuickActions()}
        </div>
      </div>
    );
  };

  const renderMobileComposerActions = () => (
    <div className="mt-3 flex items-center justify-between gap-3 lg:hidden">
      <button
        ref={startNewChatMobileButton.ref}
        type="button"
        onClick={startNewChatMobileButton.onClick}
        onPointerUp={startNewChatMobileButton.onPointerUp}
        aria-label={chat('newChatTitle')}
        className="flex h-10 items-center justify-center rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 text-sm font-medium text-[color:var(--wolfy-text-primary)] transition-colors hover:border-[color:var(--wolfy-divider)]"
      >
        + {language === 'en' ? 'New chat' : '新对话'}
      </button>
      <button
        ref={openConsoleButton.ref}
        type="button"
        onClick={openConsoleButton.onClick}
        onPointerUp={openConsoleButton.onPointerUp}
        aria-label={language === 'en' ? 'Open research context' : '打开研究上下文'}
        data-testid="chat-mobile-context-trigger"
        className="inline-flex h-10 items-center gap-2 rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 text-sm text-[color:var(--wolfy-text-secondary)] transition-colors hover:border-[color:var(--wolfy-divider)] hover:text-[color:var(--wolfy-text-primary)]"
        title={language === 'en' ? 'Open context' : '打开研究上下文'}
      >
        <PanelRightOpen className="h-4 w-4" />
        <span>{language === 'en' ? 'Context' : '上下文'}</span>
      </button>
    </div>
  );

  const renderComposerBody = (showMobileActions = true) => (
    <>
      {sendToast ? (
        <p className={`mb-3 text-right text-xs ${sendToast.type === 'success' ? 'text-success' : 'text-danger'}`}>
          {sendToast.message}
        </p>
      ) : null}

      {chatError ? (
        <ApiErrorAlert
          error={chatError}
          className="mb-3"
          actionLabel={chatError.category === 'local_connection_failed' ? chat('reloadPageAction') : undefined}
          onAction={
            chatError.category === 'local_connection_failed'
              ? () => {
                  window.location.reload();
                }
              : undefined
          }
        />
      ) : null}

      <div className="w-full">
        {renderSmartRouteStrip()}
        <div className="mb-3 lg:hidden">
          {renderQuickActions()}
        </div>
        <div
          data-testid="chat-composer-omnibar"
          className="relative w-full"
        >
          <WolfyCommandBar
            className="items-end gap-3 rounded-lg px-3 py-3"
            trailing={isGenerating ? (
              <button
                type="button"
                onClick={handleStopGeneration}
                className="flex h-10 w-10 items-center justify-center rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] text-[color:var(--wolfy-text-primary)] transition-colors hover:border-[color:var(--wolfy-divider)]"
                aria-label={chat('stopGeneration')}
                title={chat('stopGeneration')}
              >
                <div className="h-3 w-3 rounded-sm bg-current transition-colors" />
              </button>
            ) : (
              <button
                ref={sendMessageButton.ref}
                type="button"
                onClick={sendMessageButton.onClick}
                onPointerUp={sendMessageButton.onPointerUp}
                disabled={!input.trim() || loading}
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-[color:var(--wolfy-accent)] bg-[var(--wolfy-accent)] text-[#f7f8ff] transition-colors hover:bg-[#6f79dc] disabled:cursor-not-allowed disabled:opacity-40"
                aria-label={chat('notifyAction')}
                title={chat('notifyAction')}
              >
                <ArrowUp className="h-4 w-4" />
              </button>
            )}
          >
            <div className="rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)]">
              <textarea
                ref={composerTextareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={chat('inputPlaceholder')}
                disabled={loading}
                rows={1}
                className="min-h-[56px] max-h-48 w-full resize-none border-none bg-transparent px-4 py-3 text-sm text-[color:var(--wolfy-text-primary)] outline-none ring-0 placeholder:text-[color:var(--wolfy-text-muted)] disabled:cursor-not-allowed disabled:opacity-50"
                onInput={(e) => {
                  const textarea = e.target as HTMLTextAreaElement;
                  textarea.style.height = 'auto';
                  textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
                }}
              />
            </div>
          </WolfyCommandBar>
        </div>
        <p className="mt-3 text-center text-[10px] text-white/30">
          {composerDisclaimer}
        </p>
        {quickQuestions.length > 0 ? (
          <div
            data-testid="chat-quick-question-cloud"
            className="mt-3 flex flex-wrap justify-center gap-2"
          >
            {quickQuestions.slice(0, 5).map((q) => (
              <button
                className="inline-flex max-w-full items-center justify-center rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-secondary)] transition-colors hover:border-[color:var(--wolfy-divider)] hover:text-[color:var(--wolfy-text-primary)]"
                key={q.id}
                type="button"
                onClick={() => handleQuickQuestion(q)}
              >
                <span className="truncate">{chat(`quickQuestions.${q.id}`)}</span>
              </button>
            ))}
          </div>
        ) : null}
        {showMobileActions ? renderMobileComposerActions() : null}
      </div>

      {isFollowUpContextLoading ? (
        <p className="mt-3 text-center text-xs text-secondary-text">
          {chat('followUpContextLoading')}
        </p>
      ) : null}
    </>
  );

  return (
    <div
      data-testid="chat-research-workspace"
      data-route-surface="ResearchConsole"
      className="flex h-full min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden bg-[var(--wolfy-canvas)] text-[color:var(--wolfy-text-primary)]"
    >
      <ConfirmDialog
        isOpen={Boolean(deleteConfirmId)}
        title={chat('deleteConversationTitle')}
        message={chat('deleteConversationMessage')}
        confirmText={chat('deleteConversationConfirm')}
        cancelText={chat('deleteConversationCancel')}
        isDanger
        onConfirm={confirmDelete}
        onCancel={() => setDeleteConfirmId(null)}
      />

      <div data-testid="chat-workspace" className="flex h-full min-h-0 w-full min-w-0 flex-1 flex-col gap-3 overflow-hidden">
        <WolfyShellSurface
          as="section"
          variant="console"
          padding="sm"
          data-testid="chat-workspace-command"
          className="shrink-0"
        >
          <WolfyCommandBar trailing={renderConsoleActions(true)} className="min-h-12 rounded-lg bg-[var(--wolfy-surface-input)] px-3 py-2">
            <div className="min-w-0">
              <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">{chatConsoleTitle}</p>
              <h1 className="mt-1 truncate text-lg font-semibold text-[color:var(--wolfy-text-primary)]">{chat('title')}</h1>
            </div>
          </WolfyCommandBar>
        </WolfyShellSurface>

        <div
          data-testid="chat-research-shell"
          className="grid h-full min-h-0 flex-1 min-w-0 gap-3 lg:grid-cols-[minmax(0,1fr)_320px] xl:grid-cols-[minmax(0,1fr)_340px]"
        >
          <div data-testid="chat-main-shell" className="flex h-full min-h-0 flex-1 min-w-0 overflow-hidden">
            <section
              data-testid="chat-main-panel"
              className="relative flex h-full min-h-0 flex-1 min-w-0 flex-col"
            >
              <ConsoleBoard
                data-testid="chat-conversation-board"
                className="flex h-full min-h-0 flex-1 min-w-0 flex-col rounded-lg"
              >
                {showEmptyState ? (
                  <main
                    id="chat-scroll-container"
                    data-testid="chat-main"
                    className="flex h-full flex-1 flex-col overflow-hidden"
                  >
                    <div
                      data-testid="chat-empty-state"
                      className="flex flex-1 flex-col items-center justify-start overflow-y-auto no-scrollbar"
                    >
                      <div className="flex min-h-0 w-full flex-1 flex-col gap-4 px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-4 md:px-5">
                        {skillsLoadError ? (
                          <ApiErrorAlert
                            error={skillsLoadError}
                            actionLabel={chat('retryLoadSkills')}
                            onAction={() => {
                              void loadSkills();
                            }}
                          />
                        ) : null}

                        <div
                          data-testid="chat-research-entry-grid"
                          className="flex min-h-0 flex-1 flex-col justify-between gap-4"
                        >
                          <WolfyShellSurface
                            as="section"
                            variant="input"
                            padding="md"
                            data-testid="chat-empty-research-stream"
                            className="flex min-h-[180px] flex-1 flex-col items-center justify-center text-center"
                          >
                            <p className="text-sm font-medium text-[color:var(--wolfy-text-primary)]">
                              {language === 'en' ? 'Waiting for a research question' : '等待问题'}
                            </p>
                            <p className="mt-2 text-xs text-[color:var(--wolfy-text-muted)]">
                              {language === 'en' ? 'No context yet. Data is checked during analysis.' : '暂无上下文。分析时检查数据。'}
                            </p>
                          </WolfyShellSurface>

                          <div data-testid="chat-input-shell" className="sticky bottom-0 w-full shrink-0 min-w-0">
                            <div data-testid="chat-input-gradient" className="w-full shrink-0">
                              <div data-testid="chat-console-inner" className="w-full">
                                {renderComposerBody(false)}
                              </div>
                            </div>
                          </div>

                          <div className="lg:hidden">
                            {renderMobileComposerActions()}
                          </div>
                        </div>
                      </div>
                    </div>
                  </main>
                ) : (
                  <>
                    <main
                      id="chat-scroll-container"
                      data-testid="chat-main"
                      onWheel={() => {
                        isAutoScroll.current = false;
                      }}
                      onTouchMove={() => {
                        isAutoScroll.current = false;
                      }}
                      onScroll={(e) => {
                        const target = e.target as HTMLElement;
                        if (target.scrollHeight - target.scrollTop - target.clientHeight < 50) {
                          isAutoScroll.current = true;
                        }
                      }}
                      className="min-h-0 w-full flex-1 overflow-y-auto no-scrollbar"
                    >
                      <div data-testid="chat-message-scroll" className="w-full min-h-full">
                        <div
                          data-testid="chat-message-stream"
                          className="flex min-h-full w-full min-w-0 flex-col gap-6 px-4 pb-6 pt-4 md:px-5"
                        >
                          {skillsLoadError ? (
                            <ApiErrorAlert
                              error={skillsLoadError}
                              actionLabel={chat('retryLoadSkills')}
                              onAction={() => {
                                void loadSkills();
                              }}
                            />
                          ) : null}

                          <div className="flex w-full flex-col gap-5">
                            {messages.map((msg, index) => {
                              const displayContent = msg.role === 'assistant'
                                ? normalizeAssistantMessageContent(msg.content)
                                : msg.content;
                              const isLast = index === messages.length - 1;
                              const shouldStream = isGenerating
                                && msg.role === 'assistant'
                                && isLast
                                && msg.id === latestAssistantMessageId
                                && msg.id === animatedAssistantMessageId;

                              return msg.role === 'user' ? (
                                <div
                                  key={msg.id}
                                  data-testid={`chat-user-message-${msg.id}`}
                                  className="flex w-full justify-end"
                                >
                                  <div className="max-w-[80%] break-words rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-4 py-3 text-[15px] leading-relaxed text-[color:var(--wolfy-text-primary)]">
                                    {displayContent.split('\n').map((line, i) => (
                                      <p key={i} className="mb-1 break-words whitespace-pre-wrap leading-relaxed last:mb-0">
                                        {line || '\u00A0'}
                                      </p>
                                    ))}
                                  </div>
                                </div>
                              ) : (
                                <div
                                  key={msg.id}
                                  data-testid={`chat-assistant-message-${msg.id}`}
                                  className="flex w-full gap-4"
                                >
                                  <div className="mt-1 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] text-[11px] font-semibold text-[color:var(--wolfy-text-secondary)]">
                                    AI
                                  </div>
                                  <div className="flex-1 min-w-0 bg-transparent">
                                    {msg.skillName ? (
                                      <div className="mb-2">
                                        <span className="inline-flex items-center gap-1 rounded-md border border-[color:color-mix(in_srgb,var(--wolfy-accent)_36%,transparent)] bg-[color:color-mix(in_srgb,var(--wolfy-accent)_10%,transparent)] px-2 py-0.5 text-xs text-[color:var(--wolfy-accent)]">
                                          <svg
                                            className="h-3 w-3"
                                            fill="none"
                                            stroke="currentColor"
                                            viewBox="0 0 24 24"
                                          >
                                            <path
                                              strokeLinecap="round"
                                              strokeLinejoin="round"
                                              strokeWidth={2}
                                              d="M13 10V3L4 14h7v7l9-11h-7z"
                                            />
                                          </svg>
                                          {getLocalizedSkillLabel(msg.skillName, t)}
                                        </span>
                                      </div>
                                    ) : null}
                                    {renderThinkingBlock(msg)}
                                    {expandedThinking.has(msg.id) && msg.thinkingSteps ? renderThinkingDetails(msg.thinkingSteps) : null}
                                    {shouldStream ? (
                                      <TypewriterText
                                        as="div"
                                        className={STREAMING_ASSISTANT_MESSAGE_SURFACE_CLASS}
                                        testId={`chat-typewriter-${msg.id}`}
                                        text={displayContent}
                                        autoScrollRef={isAutoScroll}
                                        onComplete={() => {
                                          setAnimatedAssistantMessageId((currentId) => (currentId === msg.id ? null : currentId));
                                        }}
                                      />
                                    ) : (
                                      <Suspense fallback={renderAssistantMarkdownFallback(msg.id, language)}>
                                        <AssistantMarkdownContent
                                          className={ASSISTANT_MESSAGE_SURFACE_CLASS}
                                          content={displayContent}
                                        />
                                      </Suspense>
                                    )}
                                    {renderEvidenceFooter(msg)}
                                  </div>
                                </div>
                              );
                            })}
                          </div>

                          {loading ? (
                            <div className="flex w-full gap-4 pt-2">
                              <div className="mt-1 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] text-[11px] font-semibold text-[color:var(--wolfy-text-secondary)]">
                                AI
                              </div>
                              <div className="flex-1 min-w-0 overflow-hidden rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-4 py-3">
                                <div className="flex items-center gap-2.5 text-sm text-[color:var(--wolfy-text-secondary)]">
                                  <div className="relative h-4 w-4 flex-shrink-0">
                                    <div className="absolute inset-0 rounded-full border-2 border-[color:var(--wolfy-divider)]" />
                                    <div className="absolute inset-0 rounded-full border-2 border-[color:var(--wolfy-accent)] border-t-transparent animate-spin" />
                                  </div>
                                  <span className="text-[color:var(--wolfy-text-secondary)]">
                                    {getCurrentStage(progressSteps)}
                                  </span>
                                </div>
                              </div>
                            </div>
                          ) : null}
                        </div>
                      </div>
                    </main>

                    <footer data-testid="chat-input-shell" className="shrink-0 w-full border-t border-[color:var(--wolfy-divider)]">
                      <div data-testid="chat-input-gradient" className="w-full shrink-0 px-4 py-4 md:px-5">
                        <div data-testid="chat-console-inner" className="w-full">
                          {renderComposerBody()}
                        </div>
                      </div>
                    </footer>
                  </>
                )}
              </ConsoleBoard>
            </section>
          </div>

          <aside
            data-testid="chat-context-rail"
            className="hidden h-full min-h-0 w-full shrink-0 flex-col lg:flex"
          >
            <ConsoleContextRail className="h-full rounded-lg bg-[var(--wolfy-surface-rail)] p-3 no-scrollbar">
              <div className="flex items-center justify-between gap-3 pb-3">
                <div className="min-w-0">
                  <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">{chatConsoleTitle}</p>
                  <p className="mt-1 text-sm text-[color:var(--wolfy-text-secondary)]">{consoleMode === 'engines' ? contextPaneSummary : chat('historyTitle')}</p>
                </div>
                {renderConsoleActions()}
              </div>

              <div className="py-3">
                <SeamlessSegmentedControl
                  dataTestId="chat-console-mode-toggle"
                  value={consoleMode}
                  onChange={setConsoleMode}
                  language={language}
                />
              </div>

              <div className="min-h-0 flex-1 overflow-y-auto no-scrollbar pt-3">
                {consoleMode === 'engines' ? (
                  <div className="flex flex-col gap-4">
                    {renderContextBriefRail()}
                    {renderControlPanel('chat-control-panel')}
                  </div>
                ) : (
                  <div className="flex min-h-full flex-col gap-4">
                    <h3 className="text-xs font-medium text-[color:var(--wolfy-text-secondary)]">{chat('historyTitle')}</h3>
                    {renderHistoryList('chat-history-list')}
                  </div>
                )}
              </div>
            </ConsoleContextRail>
          </aside>
        </div>
      </div>

      <Drawer
        isOpen={isMobileConsoleOpen}
        onClose={() => setIsMobileConsoleOpen(false)}
        title={mobileConsoleTitle}
        width="max-w-[min(92vw,30rem)]"
      >
        <div data-testid="chat-mobile-context-drawer" className="flex h-full min-h-0 flex-col gap-4 text-[color:var(--wolfy-text-primary)]">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">{chatConsoleTitle}</p>
              <p className="mt-1 text-sm text-[color:var(--wolfy-text-secondary)]">{consoleMode === 'engines' ? contextPaneSummary : chat('historyTitle')}</p>
            </div>
            {renderConsoleActions(true)}
          </div>

          <SeamlessSegmentedControl
            dataTestId="chat-drawer-mode-toggle"
            value={consoleMode}
            onChange={setConsoleMode}
            language={language}
          />

          <div className="min-h-0 flex-1 overflow-y-auto no-scrollbar">
            {consoleMode === 'engines' ? (
              <div className="flex flex-col gap-4">
                {renderContextBriefRail('chat-context-brief-rail-mobile')}
                {renderControlPanel('chat-drawer-control-panel')}
              </div>
            ) : (
              <div className="flex min-h-full flex-col gap-4">
                <h3 className="text-xs font-medium text-[color:var(--wolfy-text-secondary)]">{chat('historyTitle')}</h3>
                {renderHistoryList('chat-drawer-history-list')}
              </div>
            )}
          </div>
        </div>
      </Drawer>
    </div>
  );
};

export default ChatPage;
