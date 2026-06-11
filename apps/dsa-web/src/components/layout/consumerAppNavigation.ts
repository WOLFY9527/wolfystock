import type { UiLanguage } from '../../i18n/core';

export type ConsumerNavGroupKey = 'start' | 'markets' | 'research' | 'account' | 'validate';
export type ConsumerNavItemKey =
  | 'home'
  | 'market-overview'
  | 'liquidity-monitor'
  | 'rotation-radar'
  | 'scanner'
  | 'watchlist'
  | 'portfolio'
  | 'backtest'
  | 'options-lab';

export type ConsumerNavItem = {
  key: ConsumerNavItemKey;
  labelKey: string;
  to: string;
  group: ConsumerNavGroupKey;
  requiresAuth?: boolean;
};

export type ConsumerRouteStoryCopy = {
  eyebrow: string;
  title: string;
  purpose: string;
  nextStep: string;
  evidence: string;
  boundary: string;
  primaryAction?: string;
  secondaryAction?: string;
};

export type ConsumerRouteStory = {
  routeKey: ConsumerNavItemKey;
  group: ConsumerNavGroupKey;
  copy: Record<UiLanguage, ConsumerRouteStoryCopy>;
  primaryTo?: string;
  secondaryTo?: string;
};

export const CONSUMER_NAV_GROUPS: Array<{
  key: ConsumerNavGroupKey;
  label: Record<UiLanguage, string>;
}> = [
  { key: 'start', label: { zh: '起点', en: 'Start' } },
  { key: 'markets', label: { zh: '市场', en: 'Markets' } },
  { key: 'research', label: { zh: '研究', en: 'Research' } },
  { key: 'account', label: { zh: '账户', en: 'Account' } },
  { key: 'validate', label: { zh: '验证', en: 'Validate' } },
];

export const CONSUMER_NAV_ITEMS: ConsumerNavItem[] = [
  { key: 'home', labelKey: 'nav.home', to: '/', group: 'start' },
  { key: 'market-overview', labelKey: 'nav.marketOverview', to: '/market-overview', group: 'markets' },
  { key: 'liquidity-monitor', labelKey: 'nav.liquidityMonitor', to: '/market/liquidity-monitor', group: 'markets' },
  { key: 'rotation-radar', labelKey: 'nav.rotationRadar', to: '/market/rotation-radar', group: 'markets' },
  { key: 'scanner', labelKey: 'nav.scanner', to: '/scanner', group: 'research', requiresAuth: true },
  { key: 'watchlist', labelKey: 'nav.watchlist', to: '/watchlist', group: 'research', requiresAuth: true },
  { key: 'portfolio', labelKey: 'nav.portfolio', to: '/portfolio', group: 'account', requiresAuth: true },
  { key: 'backtest', labelKey: 'nav.backtest', to: '/backtest', group: 'validate', requiresAuth: true },
  { key: 'options-lab', labelKey: 'nav.optionsLab', to: '/options-lab', group: 'validate', requiresAuth: true },
];

export const ROUTE_STORIES: ConsumerRouteStory[] = [
  {
    routeKey: 'home',
    group: 'start',
    primaryTo: '/market-overview',
    secondaryTo: '/scanner',
    copy: {
      zh: {
        eyebrow: '首页 / 研究起点',
        title: '先确认市场背景，再进入个股研究。',
        purpose: '首页用于输入标的、查看最近观察和继续未完成的研究流程。',
        nextStep: '从市场总览确认环境，或登录后运行扫描器生成观察队列。',
        evidence: '证据边界：摘要、图表与报告状态会标明覆盖度。',
        boundary: '当前内容只用于研究观察，不产生外部动作，也不会改变持仓记录。',
        primaryAction: '打开市场总览',
        secondaryAction: '查看扫描器',
      },
      en: {
        eyebrow: 'Home / Research Start',
        title: 'Confirm market context before single-name research.',
        purpose: 'Home starts ticker research, resumes recent observations, and keeps unfinished work visible.',
        nextStep: 'Use Market Overview for context, or sign in and review Scanner observations.',
        evidence: 'Evidence boundary: summaries, charts, and reports expose coverage status.',
        boundary: 'Content is for research observation only; it creates no external action and does not change holdings.',
        primaryAction: 'Open Market Overview',
        secondaryAction: 'Review Scanner',
      },
    },
  },
  {
    routeKey: 'market-overview',
    group: 'markets',
    primaryTo: '/market/liquidity-monitor',
    secondaryTo: '/market/rotation-radar',
    copy: {
      zh: {
        eyebrow: '市场 / 全景',
        title: '把大盘温度、宽度、资金与宏观压力放在同一张地图里。',
        purpose: '市场总览帮助判断今天应该先看风险、流动性还是主题分化。',
        nextStep: '继续查看流动性监测，或进入轮动雷达确认主题扩散。',
        evidence: '证据边界：卡片会展示刷新、降级和覆盖状态。',
        boundary: '这是市场观察视图，只支持情景复核，不产生外部动作。',
        primaryAction: '查看流动性',
        secondaryAction: '查看轮动',
      },
      en: {
        eyebrow: 'Markets / Overview',
        title: 'Put temperature, breadth, flows, and macro pressure on one map.',
        purpose: 'Market Overview helps decide whether risk, liquidity, or theme dispersion deserves attention first.',
        nextStep: 'Continue to Liquidity Monitor, or open Rotation Radar for theme breadth.',
        evidence: 'Evidence boundary: cards expose refresh, degraded, and coverage states.',
        boundary: 'This is a market observation view for scenario review; it creates no external action.',
        primaryAction: 'Open Liquidity',
        secondaryAction: 'Open Rotation',
      },
    },
  },
  {
    routeKey: 'liquidity-monitor',
    group: 'markets',
    primaryTo: '/market/rotation-radar',
    secondaryTo: '/market-overview',
    copy: {
      zh: {
        eyebrow: '市场 / 流动性',
        title: '先看资金环境，再判断研究优先级。',
        purpose: '流动性监测用于观察风险偏好、资金压力和市场脉冲是否同步。',
        nextStep: '若流动性支持度改善，再用轮动雷达查看主题是否扩散。',
        evidence: '证据边界：异常与降级会以用户可读状态展示。',
        boundary: '页面只呈现流动性观察，不改变持仓记录。',
        primaryAction: '查看轮动雷达',
        secondaryAction: '返回市场总览',
      },
      en: {
        eyebrow: 'Markets / Liquidity',
        title: 'Read the funding backdrop before setting research priority.',
        purpose: 'Liquidity Monitor tracks whether risk appetite, funding pressure, and market impulse align.',
        nextStep: 'If liquidity support improves, use Rotation Radar to check whether themes are broadening.',
        evidence: 'Evidence boundary: unavailable and degraded states are shown in user-facing language.',
        boundary: 'This page shows liquidity observation only and does not change holdings.',
        primaryAction: 'Open Rotation Radar',
        secondaryAction: 'Back to Overview',
      },
    },
  },
  {
    routeKey: 'rotation-radar',
    group: 'markets',
    primaryTo: '/scanner',
    secondaryTo: '/market-overview',
    copy: {
      zh: {
        eyebrow: '市场 / 轮动',
        title: '从主题扩散和退潮中找到下一批研究对象。',
        purpose: '轮动雷达把主题、家族和强弱状态整理成观察队列。',
        nextStep: '确认主题后，登录查看扫描器中的可复核候选。',
        evidence: '证据边界：只展示当前可解释的主题支持与限制。',
        boundary: '轮动状态仅用于研究排序和情景复核，不产生外部动作。',
        primaryAction: '查看扫描器',
        secondaryAction: '返回市场总览',
      },
      en: {
        eyebrow: 'Markets / Rotation',
        title: 'Use theme broadening and cooling to find the next research queue.',
        purpose: 'Rotation Radar organizes themes, families, and strength states into an observation queue.',
        nextStep: 'After confirming a theme, sign in to review Scanner candidates.',
        evidence: 'Evidence boundary: only explainable theme support and limits are shown.',
        boundary: 'Rotation states support research ranking and scenario review only; they create no external action.',
        primaryAction: 'Review Scanner',
        secondaryAction: 'Back to Overview',
      },
    },
  },
  {
    routeKey: 'scanner',
    group: 'research',
    primaryTo: '/watchlist',
    secondaryTo: '/market-overview',
    copy: {
      zh: {
        eyebrow: '研究 / 扫描',
        title: '把市场线索压缩成可复核的候选清单。',
        purpose: '扫描器用于生成候选、风险边界和后续研究入口。',
        nextStep: '运行后把候选作为手工观察记录，再进入组合或回测验证。',
        evidence: '证据边界：候选解释、运行事实和空结果原因会保持可见。',
        boundary: '候选只代表研究入口，不产生外部动作，也不改变持仓记录。',
        primaryAction: '查看观察列表',
        secondaryAction: '回到市场总览',
      },
      en: {
        eyebrow: 'Research / Scanner',
        title: 'Compress market clues into a reviewable candidate list.',
        purpose: 'Scanner creates candidates, risk boundaries, and follow-up research entry points.',
        nextStep: 'After a run, keep candidates as manual records before portfolio or backtest review.',
        evidence: 'Evidence boundary: candidate rationale, run facts, and empty reasons stay visible.',
        boundary: 'Candidates are research entry points; they create no external action and do not change holdings.',
        primaryAction: 'Review Watchlist',
        secondaryAction: 'Back to Market Overview',
      },
    },
  },
  {
    routeKey: 'watchlist',
    group: 'research',
    primaryTo: '/portfolio',
    secondaryTo: '/scanner',
    copy: {
      zh: {
        eyebrow: '研究 / 观察列表',
        title: '把候选沉淀为持续观察，而不是一次性页面。',
        purpose: '观察列表用于跟踪候选状态、提醒和下一步研究记录。',
        nextStep: '有手工持仓记录时进入组合总览；需要新候选时返回扫描器。',
        evidence: '证据边界：提醒、状态和数据说明会与列表同屏展示。',
        boundary: '观察列表是手工研究记录，不自动触发外部动作或通知。',
        primaryAction: '打开组合',
        secondaryAction: '返回扫描器',
      },
      en: {
        eyebrow: 'Research / Watchlist',
        title: 'Turn candidates into ongoing observation, not a one-off page.',
        purpose: 'Watchlist tracks candidate state, alerts, and follow-up research notes.',
        nextStep: 'Open Portfolio when manual holding records matter; return to Scanner when you need new candidates.',
        evidence: 'Evidence boundary: alerts, state, and data notes stay near the list.',
        boundary: 'Watchlist is a manual research record; it does not trigger external action or notifications by itself.',
        primaryAction: 'Open Portfolio',
        secondaryAction: 'Back to Scanner',
      },
    },
  },
  {
    routeKey: 'portfolio',
    group: 'account',
    primaryTo: '/watchlist',
    secondaryTo: '/backtest',
    copy: {
      zh: {
        eyebrow: '账户 / 组合',
        title: '把账户记录、风险和研究线索放在同一工作台。',
        purpose: '组合页用于查看手工记录、现金、持仓、风险和估值说明。',
        nextStep: '回到观察列表复核候选，或用回测做只读验证。',
        evidence: '证据边界：估值、外汇和风险置信度会展示可用状态。',
        boundary: '这里只维护手工记录，不连接外部账户通道，也不会改变真实持仓。',
        primaryAction: '打开观察列表',
        secondaryAction: '打开回测',
      },
      en: {
        eyebrow: 'Account / Portfolio',
        title: 'Keep account records, risk, and research context in one workspace.',
        purpose: 'Portfolio shows manual records, cash, holdings, risk, and valuation notes.',
        nextStep: 'Return to Watchlist for candidate review, or use Backtest for read-only validation.',
        evidence: 'Evidence boundary: valuation, FX, and risk confidence expose availability states.',
        boundary: 'This workspace keeps manual records only; it connects no external account channel and does not change live holdings.',
        primaryAction: 'Open Watchlist',
        secondaryAction: 'Open Backtest',
      },
    },
  },
  {
    routeKey: 'backtest',
    group: 'validate',
    primaryTo: '/options-lab',
    secondaryTo: '/watchlist',
    copy: {
      zh: {
        eyebrow: '验证 / 回测',
        title: '把研究假设放进确定性验证，而不是直接改动记录。',
        purpose: '回测页用于比较规则、窗口、结果摘要和可解释限制。',
        nextStep: '验证后回到观察列表，或进入期权实验室查看只读情景。',
        evidence: '证据边界：结果、质量说明和导出细节默认保持可复核。',
        boundary: '回测结果只用于只读验证，不改变任何记录或持仓状态。',
        primaryAction: '打开期权实验室',
        secondaryAction: '回到观察列表',
      },
      en: {
        eyebrow: 'Validate / Backtest',
        title: 'Put research assumptions into deterministic validation before scenario review.',
        purpose: 'Backtest compares rules, windows, result summaries, and explainable limits.',
        nextStep: 'After validation, return to Watchlist or open Options Lab for read-only scenarios.',
        evidence: 'Evidence boundary: results, quality notes, and export details stay reviewable.',
        boundary: 'Backtest output is read-only validation; it does not change records or holdings.',
        primaryAction: 'Open Options Lab',
        secondaryAction: 'Back to Watchlist',
      },
    },
  },
  {
    routeKey: 'options-lab',
    group: 'validate',
    primaryTo: '/backtest',
    secondaryTo: '/market-overview',
    copy: {
      zh: {
        eyebrow: '验证 / 期权',
        title: '只读比较期权情景，样例仅用于结构复核。',
        purpose: '期权实验室用于整理假设价格、到期日、风险预算与样例结构。',
        nextStep: '先用回测复核标的假设，再回到市场总览确认背景。',
        evidence: '证据边界：可用性、链数据和情景估算会标明限制。',
        boundary: '页面只做情景复核，不产生外部动作，也不改变持仓记录。',
        primaryAction: '打开回测',
        secondaryAction: '回到市场总览',
      },
      en: {
        eyebrow: 'Validate / Options',
        title: 'Compare read-only option scenarios as structure review only.',
        purpose: 'Options Lab organizes assumed price, date, risk budget, and sample structures.',
        nextStep: 'Use Backtest to review the underlying assumption, then return to Market Overview for context.',
        evidence: 'Evidence boundary: availability, chain data, and scenario estimates expose limits.',
        boundary: 'The page is scenario review only; it creates no external action and does not change holdings.',
        primaryAction: 'Open Backtest',
        secondaryAction: 'Back to Market Overview',
      },
    },
  },
];

export function getConsumerGroupLabel(group: ConsumerNavGroupKey, language: UiLanguage): string {
  return CONSUMER_NAV_GROUPS.find((item) => item.key === group)?.label[language] || group;
}

function isPathMatch(pathname: string, target: string): boolean {
  if (target === '/') {
    return pathname === '/' || pathname === '' || pathname === '/guest';
  }
  return pathname === target || pathname.startsWith(`${target}/`);
}

export function resolveConsumerNavItem(pathname: string): ConsumerNavItem | null {
  return CONSUMER_NAV_ITEMS.find((item) => isPathMatch(pathname, item.to)) || null;
}

export function resolveConsumerRouteStory(pathname: string): ConsumerRouteStory | null {
  const item = resolveConsumerNavItem(pathname);
  if (!item) {
    return null;
  }
  return ROUTE_STORIES.find((story) => story.routeKey === item.key) || null;
}
