import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { ArrowUp, Download, Lightbulb, PanelRightOpen, SendHorizontal } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { agentApi } from '../api/agent';
import { ApiErrorAlert, ConfirmDialog, Drawer, GlassCard, TypewriterText } from '../components/common';
import { CARD_BUTTON_CLASS } from '../components/home-bento';
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
  getSafariReadySurfaceClassName,
  shouldApplySafariA11yGuard,
  useSafariRenderReady,
  useSafariWarmActivation,
} from '../hooks/useSafariInteractionReady';
import { translate } from '../i18n/core';

const assistantMarkdownComponents = {
  h1: ({ children }: React.PropsWithChildren) => <h1 className="mb-3 text-lg font-bold text-white">{children}</h1>,
  h2: ({ children }: React.PropsWithChildren) => <h2 className="mb-3 mt-4 text-base font-semibold text-white">{children}</h2>,
  h3: ({ children }: React.PropsWithChildren) => <h3 className="mb-2 mt-4 text-base font-semibold text-white">{children}</h3>,
  p: ({ children }: React.PropsWithChildren) => <p className="mb-2 leading-[1.6] last:mb-0">{children}</p>,
  ul: ({ children }: React.PropsWithChildren) => <ul className="my-2 list-disc space-y-1 pl-5 last:mb-0">{children}</ul>,
  ol: ({ children }: React.PropsWithChildren) => <ol className="my-2 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>,
  li: ({ children }: React.PropsWithChildren) => <li className="mb-1 break-words leading-[1.6]">{children}</li>,
  strong: ({ children }: React.PropsWithChildren) => <strong className="font-semibold text-white">{children}</strong>,
  a: ({ children, href }: React.PropsWithChildren<{ href?: string }>) => (
    <a className="text-[hsl(var(--accent-primary-hsl))] underline-offset-2 hover:underline" href={href} target="_blank" rel="noreferrer">
      {children}
    </a>
  ),
  blockquote: ({ children }: React.PropsWithChildren) => (
    <blockquote className="my-3 text-white/72 first:mt-0 last:mb-0">{children}</blockquote>
  ),
  code: ({ children, className }: React.PropsWithChildren<{ className?: string }>) => {
    if (className) {
      return <code className={className}>{children}</code>;
    }
    return (
      <code className="rounded bg-white/[0.08] px-1.5 py-0.5 text-xs text-[hsl(var(--accent-primary-hsl))] break-all">
        {children}
      </code>
    );
  },
  pre: ({ children }: React.PropsWithChildren) => (
    <pre className="mb-3 overflow-x-auto no-scrollbar rounded-xl border border-white/8 bg-black/30 p-3 text-[13px] leading-6 text-white/88 last:mb-0">
      {children}
    </pre>
  ),
  table: ({ children }: React.PropsWithChildren) => (
    <div className="mb-4 overflow-x-auto no-scrollbar last:mb-0">
      <table className="w-full min-w-max border-collapse text-sm">{children}</table>
    </div>
  ),
  th: ({ children }: React.PropsWithChildren) => <th className="border border-white/10 bg-white/[0.05] px-3 py-1.5 text-left font-medium text-white">{children}</th>,
  td: ({ children }: React.PropsWithChildren) => <td className="border border-white/10 px-3 py-1.5 align-top">{children}</td>,
  hr: () => <hr className="my-4 border-white/10" />,
} satisfies React.ComponentProps<typeof Markdown>['components'];

type StarterPromptCard = {
  id: string;
  skill: string;
};

type QuickQuestion = {
  id: string;
  skill: string;
};

type ChatConsoleMode = 'engines' | 'history';

const STARTER_PROMPT_CARDS: StarterPromptCard[] = [
  { id: 'entryDecision', skill: 'bull_trend' },
  { id: 'positionReview', skill: 'bull_trend' },
  { id: 'eventFollowUp', skill: 'bull_trend' },
];

const QUICK_QUESTIONS: QuickQuestion[] = [
  { id: 'q1', skill: 'chan_theory' },
  { id: 'q2', skill: 'wave_theory' },
  { id: 'q3', skill: 'bull_trend' },
  { id: 'q4', skill: 'box_oscillation' },
  { id: 'q5', skill: 'bull_trend' },
  { id: 'q6', skill: 'emotion_cycle' },
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
  { value: 'engines', label: { zh: '引擎视角', en: 'Engines' } },
  { value: 'history', label: { zh: '历史记录', en: 'History' } },
];

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
    <div data-testid={dataTestId} className="flex w-full rounded-lg bg-white/[0.03] p-1">
      {CHAT_CONSOLE_TOGGLE_OPTIONS.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(option.value)}
            className={`appearance-none flex-1 rounded-md border-0 px-3 py-2 text-center text-sm font-medium transition-all duration-200 ${
              active
                ? 'bg-white/10 text-white shadow-sm'
                : 'bg-transparent text-white/40 hover:text-white/72'
            }`}
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

const ChatPage: React.FC = () => {
  const { isReady: isSafariReady, surfaceRef } = useSafariRenderReady();
  const shouldGuardA11y = shouldApplySafariA11yGuard();
  const { language, t } = useI18n();
  const [searchParams, setSearchParams] = useSearchParams();
  const [input, setInput] = useState('');
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [selectedSkill, setSelectedSkill] = useState<string>('');
  const [showSkillDesc, setShowSkillDesc] = useState<string | null>(null);
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
  const [animatedAssistantMessageId, setAnimatedAssistantMessageId] = useState<string | null>(null);
  const composerTextareaRef = useRef<HTMLTextAreaElement>(null);
  const isAutoScroll = useRef(true);
  const isMountedRef = useRef(true);
  const followUpHydrationTokenRef = useRef(0);
  const followUpContextRef = useRef<ChatFollowUpContext | null>(null);
  const seenAssistantMessageIdsRef = useRef<Set<string>>(new Set());
  const hasHydratedAssistantMessagesRef = useRef(false);
  const chat = useCallback(
    (key: string, vars?: Record<string, string | number | undefined>) => t(`chat.${key}`, vars),
    [t],
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
      const defaultId = res.default_skill_id || res.skills[0]?.id || '';
      setSelectedSkill(defaultId);
    } catch (error: unknown) {
      setSkillsLoadError(getParsedApiError(error));
      setSkills([]);
      setSelectedSkill('');
    }
  }, []);

  useEffect(() => {
    void loadSkills();
  }, [loadSkills]);

  const availableSkillIds = new Set(skills.map((skill) => skill.id));
  const starterPromptCards = STARTER_PROMPT_CARDS.filter(
    (card) => availableSkillIds.size === 0 || availableSkillIds.has(card.skill),
  );
  const quickQuestions = QUICK_QUESTIONS.filter(
    (question) => availableSkillIds.size === 0 || availableSkillIds.has(question.skill),
  );
  const engineSwitcherLabel = language === 'en' ? 'Analysis engines & perspectives' : '分析引擎与视角';
  const composerDisclaimer = language === 'en'
    ? 'AI insights are for reference only and are not investment advice. Confirm your risk tolerance before trading.'
    : 'AI 洞察仅供参考，不构成实质性投资建议。执行交易前请确认风险承受能力。';
  const chatConsoleTitle = language === 'en' ? 'Research console' : '综合控制台';
  const mobileConsoleTitle = language === 'en' ? 'Chat console' : '问股控制台';
  const hasMessages = messages.length > 0;
  const showEmptyState = !hasMessages && !loading;

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
        context: followUpContextRef.current ?? undefined,
      };
      followUpHydrationTokenRef.current += 1;
      followUpContextRef.current = null;
      setIsFollowUpContextLoading(false);
      setInput('');
      await startStream(payload, { skillName: usedSkillName });
    },
    [chat, input, loading, selectedSkill, sessionId, skills, startStream, t],
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
        aria-label={chat('thinking.toggleLabel')}
        onClick={() => toggleThinking(msg.id)}
        className="mb-2 flex w-full items-center gap-2 text-left text-xs text-muted-text transition-colors hover:text-secondary-text"
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
        className={`flex items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-sm font-medium text-white transition-colors hover:bg-white/[0.08] ${
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
            className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-secondary-text transition-colors hover:bg-white/[0.08] hover:text-foreground"
            title={chat('exportTitle')}
          >
            <Download className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => {
              void handleNotifySession();
            }}
            disabled={sending}
            className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-secondary-text transition-colors hover:bg-white/[0.08] hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
            title={chat('notifyTitle')}
          >
            {sending ? (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/25 border-t-white" />
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
          <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-3 py-4 text-xs text-secondary-text">
            {chat('loadingSessions')}
          </div>
        ) : sessions.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] px-3 py-4 text-xs text-secondary-text">
            {chat('emptySessions')}
          </div>
        ) : (
          groupedSessions.map(([bucketLabel, bucketSessions]) => (
            <section key={bucketLabel} className="flex flex-col gap-1.5 pb-3">
              <p className="px-2 text-[10px] uppercase tracking-[0.24em] text-white/30">{bucketLabel}</p>
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
                  className={`group rounded-2xl border px-3 py-3 transition-all ${
                    s.session_id === sessionId
                      ? 'border-white/14 bg-white/[0.07]'
                      : 'border-white/6 bg-white/[0.02] hover:bg-white/[0.05]'
                  }`}
                  aria-label={chat('switchToConversation', { title: s.title })}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-white/88">{s.title}</p>
                      <div className="mt-2 flex items-center gap-2 text-[11px] text-white/36">
                        <span>{chat('messageCount', { count: s.message_count })}</span>
                        {s.last_active ? <span className="h-1 w-1 rounded-full bg-white/14" /> : null}
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
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeleteConfirmId(s.session_id);
                      }}
                      className="rounded-lg p-1 text-white/28 opacity-0 transition-all hover:bg-white/10 hover:text-danger group-hover:opacity-100"
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

  const renderEngineList = (testId: string) => (
    <div data-testid={testId} className="flex flex-wrap gap-2.5">
      <button
        type="button"
        onClick={() => setSelectedSkill('')}
        className={`rounded-full border px-4 py-2 text-xs font-medium transition-all ${
          selectedSkill === ''
            ? 'border-white/12 bg-white/10 text-white shadow-sm'
            : 'border-transparent bg-transparent text-white/50 hover:bg-white/[0.05] hover:text-white/90'
        }`}
      >
        <span className="mr-1.5 inline-block h-1.5 w-1.5 rounded-full bg-current align-middle" />
        {chat('skills.general')}
      </button>
      {skills.map((s) => (
        <div
          key={s.id}
          className="relative"
          onMouseEnter={() => setShowSkillDesc(s.id)}
          onMouseLeave={() => setShowSkillDesc(null)}
        >
          <button
            type="button"
            onClick={() => setSelectedSkill(s.id)}
            className={`rounded-full border px-4 py-2 text-xs font-medium transition-all ${
              selectedSkill === s.id
                ? 'border-white/12 bg-white/10 text-white shadow-sm'
                : 'border-transparent bg-transparent text-white/50 hover:bg-white/[0.05] hover:text-white/90'
            }`}
          >
            <span className={`mr-1.5 inline-block h-1.5 w-1.5 rounded-full align-middle ${selectedSkill === s.id ? 'animate-pulse bg-white' : 'bg-white/35'}`} />
            {getLocalizedSkillNameById(s.id, s.name, t)}
          </button>
          {showSkillDesc === s.id && s.description ? (
            <div className="theme-menu-panel absolute left-0 top-full z-50 mt-2 w-64 rounded-lg p-2.5 text-xs leading-relaxed text-secondary-text shadow-xl animate-fade-in">
              <p className="mb-1 font-medium text-foreground">{getLocalizedSkillNameById(s.id, s.name, t)}</p>
              <p>{s.description}</p>
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );

  const renderComposerBody = () => (
    <>
      <div className="mb-3 flex items-center justify-between gap-3 lg:hidden">
        <button
          ref={startNewChatMobileButton.ref}
          type="button"
          onClick={startNewChatMobileButton.onClick}
          onPointerUp={startNewChatMobileButton.onPointerUp}
          aria-label={chat('newChatTitle')}
          className="flex h-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] px-3 text-sm font-medium text-white transition-colors hover:bg-white/[0.08]"
        >
          + {language === 'en' ? 'New chat' : '新对话'}
        </button>
        <button
          ref={openConsoleButton.ref}
          type="button"
          onClick={openConsoleButton.onClick}
          onPointerUp={openConsoleButton.onPointerUp}
          data-testid="chat-bento-brief-trigger"
          className={CARD_BUTTON_CLASS}
          title={language === 'en' ? 'Open console' : '打开控制台'}
        >
          <PanelRightOpen className="h-4 w-4" />
          <span>{language === 'en' ? 'Console' : '控制台'}</span>
        </button>
      </div>

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

      <div className="mx-auto w-full max-w-4xl">
        <div
          data-testid="chat-composer-omnibar"
          className="relative mx-auto w-full max-w-4xl rounded-3xl border border-white/[0.05] bg-white/[0.04] p-2 shadow-2xl backdrop-blur-2xl"
        >
          <textarea
            ref={composerTextareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={chat('inputPlaceholder')}
            disabled={loading}
            rows={1}
            className="min-h-[56px] max-h-48 w-full resize-none border-none bg-transparent px-4 py-3 pr-16 text-sm text-white outline-none ring-0 placeholder:text-white/30 disabled:cursor-not-allowed disabled:opacity-50"
            onInput={(e) => {
              const textarea = e.target as HTMLTextAreaElement;
              textarea.style.height = 'auto';
              textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
            }}
          />
          {isGenerating ? (
            <button
              type="button"
              onClick={handleStopGeneration}
              className="absolute bottom-2.5 right-2.5 flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-white transition-all active:scale-95 hover:bg-white/20"
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
              className="absolute bottom-2.5 right-2.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white text-black transition-all active:scale-95 hover:bg-white/90 disabled:cursor-not-allowed disabled:opacity-40"
              aria-label={chat('notifyAction')}
              title={chat('notifyAction')}
            >
              <ArrowUp className="h-4 w-4" />
            </button>
          )}
        </div>
        <p className="mt-3 text-center text-[10px] text-white/30">
          {composerDisclaimer}
        </p>
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
      ref={surfaceRef}
      data-testid="chat-bento-page"
      data-bento-surface="true"
      aria-hidden={shouldGuardA11y && !isSafariReady ? true : undefined}
      aria-live={shouldGuardA11y ? (isSafariReady ? 'polite' : 'off') : undefined}
      className={getSafariReadySurfaceClassName(
        isSafariReady,
        'gemini-bento-page bento-surface-root gemini-bento-page--chat flex h-full min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden bg-[#030303]',
      )}
    >
      <div
        data-testid="chat-workspace"
        className="flex h-full min-h-0 w-full min-w-0 flex-1 overflow-hidden bg-transparent"
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

        <div
          data-testid="chat-main-shell"
          className="flex h-full min-h-0 flex-1 min-w-0 overflow-hidden"
        >
          <section
            data-testid="chat-main-panel"
            className="relative flex h-full min-h-0 flex-1 min-w-0 flex-col lg:border-r lg:border-white/5"
          >
            {showEmptyState ? (
              <main
                id="chat-scroll-container"
                data-testid="chat-main"
                className="flex h-full flex-1 flex-col overflow-hidden"
              >
                <div
                  data-testid="chat-empty-state"
                  className="flex flex-1 flex-col items-center justify-center overflow-y-auto no-scrollbar"
                >
                  <div className="flex w-full max-w-5xl flex-col items-center gap-12 px-6 pt-6 text-center md:px-8 xl:px-12">
                    {skillsLoadError ? (
                      <ApiErrorAlert
                        error={skillsLoadError}
                        actionLabel={chat('retryLoadSkills')}
                        onAction={() => {
                          void loadSkills();
                        }}
                      />
                    ) : null}

                    <div className="flex w-full max-w-4xl flex-col items-center">
                      <div className="mb-3 flex items-center justify-center gap-3">
                        <Lightbulb className="h-6 w-6 text-white/80" aria-hidden="true" />
                        <h1 className="text-3xl font-bold text-white">{chat('emptyTitle')}</h1>
                      </div>
                      <p className="mt-3 max-w-3xl text-sm leading-relaxed text-white/62">
                        {chat('emptyBody')}
                      </p>
                    </div>

                    <div className="grid w-full max-w-5xl grid-cols-1 gap-6 lg:grid-cols-3">
                      {starterPromptCards.map((card) => (
                        <GlassCard
                          key={card.id}
                          as="button"
                          data-testid={`chat-starter-card-${card.id}`}
                          onClick={() => {
                            void handleSend(chat(`starterCards.${card.id}.prompt`), card.skill);
                          }}
                          className="flex min-w-0 flex-col items-center justify-center rounded-2xl border border-white/5 bg-white/[0.02] px-8 py-6 text-center transition-colors duration-150 hover:bg-white/[0.05]"
                        >
                          <div className="flex flex-col items-center justify-center gap-3">
                            <p className="break-words whitespace-normal text-sm font-bold text-white">{chat(`starterCards.${card.id}.title`)}</p>
                            <p className="break-words whitespace-normal text-xs leading-relaxed text-white/60">
                              {chat(`starterCards.${card.id}.description`)}
                            </p>
                            <p className="break-words whitespace-normal text-xs leading-relaxed text-white/38">
                              {chat(`starterCards.${card.id}.prompt`)}
                            </p>
                          </div>
                        </GlassCard>
                      ))}
                    </div>

                    {quickQuestions.length > 0 ? (
                      <div
                        data-testid="chat-quick-question-cloud"
                        className="flex flex-wrap justify-center gap-3"
                      >
                        {quickQuestions.map((q) => (
                          <button
                            key={q.id}
                            type="button"
                            onClick={() => handleQuickQuestion(q)}
                            className="inline-flex items-center justify-center whitespace-nowrap rounded-xl border border-white/5 bg-white/[0.02] px-5 py-2.5 text-xs text-white/60 transition-all hover:bg-white/[0.05] hover:text-white"
                          >
                            {chat(`quickQuestions.${q.id}`)}
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </div>

                <div data-testid="chat-input-shell" className="shrink-0 w-full">
                  <div data-testid="chat-input-gradient" className="w-full shrink-0 px-6 pb-6 pt-4 md:px-8 xl:px-12">
                    <div
                      data-testid="chat-console-inner"
                      className="w-full"
                    >
                      {renderComposerBody()}
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
                  <div
                    data-testid="chat-message-scroll"
                    className="w-full min-h-full"
                  >
                    <div
                      data-testid="chat-message-stream"
                      className="flex min-h-full w-full min-w-0 flex-col gap-8 px-6 pb-8 pt-6 md:px-8 xl:px-12"
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

                      <div className="flex w-full flex-col gap-6">
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
                            className="mb-6 flex w-full justify-end"
                          >
                            <div className="max-w-[80%] break-words rounded-2xl rounded-tr-[4px] border border-white/10 bg-white/[0.05] px-5 py-3.5 text-[15px] leading-relaxed text-white/90 shadow-lg backdrop-blur-md">
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
                            <div className="mt-1 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-white/[0.08] text-[11px] font-semibold text-white/72">
                              AI
                            </div>
                            <div className="flex-1 min-w-0 bg-transparent">
                              {msg.skillName ? (
                                <div className="mb-2">
                                  <span className="inline-flex items-center gap-1 rounded-full bg-white/[0.06] px-2 py-0.5 text-xs text-[hsl(var(--accent-primary-hsl))]">
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
                                <div className={ASSISTANT_MESSAGE_SURFACE_CLASS}>
                                  <Markdown components={assistantMarkdownComponents} remarkPlugins={[remarkGfm]}>
                                    {displayContent}
                                  </Markdown>
                                </div>
                              )}
                            </div>
                          </div>
                        );
                        })}
                      </div>

                      {loading ? (
                        <div className="flex w-full gap-4 pt-2">
                          <div className="mt-1 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-white/[0.08] text-[11px] font-semibold text-white/72">
                            AI
                          </div>
                          <div className="flex-1 min-w-0 overflow-hidden rounded-2xl bg-white/[0.03] px-5 py-4">
                            <div className="flex items-center gap-2.5 text-sm text-secondary-text">
                              <div className="relative h-4 w-4 flex-shrink-0">
                                <div className="absolute inset-0 rounded-full border-2 border-[hsl(var(--accent-primary-hsl)/0.2)]" />
                                <div className="absolute inset-0 rounded-full border-2 border-[hsl(var(--accent-primary-hsl))] border-t-transparent animate-spin" />
                              </div>
                              <span className="text-secondary-text">
                                {getCurrentStage(progressSteps)}
                              </span>
                            </div>
                          </div>
                        </div>
                      ) : null}
                    </div>
                  </div>
                </main>

                <footer data-testid="chat-input-shell" className="shrink-0 w-full">
                  <div data-testid="chat-input-gradient" className="w-full shrink-0 px-6 pb-6 pt-4 md:px-8 xl:px-12">
                    <div
                      data-testid="chat-console-inner"
                      className="w-full"
                    >
                      {renderComposerBody()}
                    </div>
                  </div>
                </footer>
              </>
            )}
          </section>

          <aside
            data-testid="chat-strategy-panel"
            className="hidden h-full min-h-0 w-full shrink-0 flex-col gap-5 overflow-y-auto border-l border-white/5 bg-gradient-to-b from-white/[0.01] to-transparent p-5 no-scrollbar lg:flex lg:w-[320px] xl:w-[360px]"
          >
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-[10px] uppercase tracking-[0.24em] text-white/30">{chatConsoleTitle}</p>
                <p className="mt-2 text-sm text-white/58">{consoleMode === 'engines' ? engineSwitcherLabel : chat('historyTitle')}</p>
              </div>
              {renderConsoleActions()}
            </div>

            <SeamlessSegmentedControl
              dataTestId="chat-console-mode-toggle"
              value={consoleMode}
              onChange={setConsoleMode}
              language={language}
            />

            <div className="min-h-0 flex-1 overflow-y-auto no-scrollbar pr-1">
              {consoleMode === 'engines' ? (
                <div className="flex flex-col gap-4">
                  <h3 className="text-xs font-bold uppercase tracking-[0.24em] text-white/50">{engineSwitcherLabel}</h3>
                  {renderEngineList('chat-strategy-grid')}
                </div>
              ) : (
                <div className="flex min-h-full flex-col gap-4">
                  <h3 className="text-xs font-bold uppercase tracking-[0.24em] text-white/50">{chat('historyTitle')}</h3>
                  {renderHistoryList('chat-history-list')}
                </div>
              )}
            </div>
          </aside>
        </div>
      </div>

      <Drawer
        isOpen={isMobileConsoleOpen}
        onClose={() => setIsMobileConsoleOpen(false)}
        title={mobileConsoleTitle}
        width="max-w-[min(92vw,30rem)]"
      >
        <div data-testid="chat-bento-drawer" className="flex h-full min-h-0 flex-col gap-5 text-white">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[10px] uppercase tracking-[0.24em] text-white/30">{chatConsoleTitle}</p>
              <p className="mt-2 text-sm text-white/58">{consoleMode === 'engines' ? engineSwitcherLabel : chat('historyTitle')}</p>
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
                <h3 className="text-xs font-bold uppercase tracking-[0.24em] text-white/50">{engineSwitcherLabel}</h3>
                {renderEngineList('chat-drawer-strategy-grid')}
              </div>
            ) : (
              <div className="flex min-h-full flex-col gap-4">
                <h3 className="text-xs font-bold uppercase tracking-[0.24em] text-white/50">{chat('historyTitle')}</h3>
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
