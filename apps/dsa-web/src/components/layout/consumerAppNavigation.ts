import type { UiLanguage } from '../../i18n/core';
import { stripLocalePrefix } from '../../utils/localeRouting';
import { PRIMARY_CONSUMER_ROUTES } from './coreProductRoutes';

export type ConsumerNavGroupKey = 'cockpit' | 'research' | 'context' | 'observe';
export type ConsumerNavItemKey =
  | 'decision-cockpit'
  | 'market-overview'
  | 'research-radar'
  | 'stock-structure'
  | 'scanner'
  | 'watchlist'
  | 'portfolio'
  | 'backtest'
  | 'scenario-lab';
export type ConsumerRouteKey = ConsumerNavItemKey | 'home' | 'guest' | 'liquidity-monitor' | 'rotation-radar' | 'backtest' | 'options-lab';

export type ConsumerNavItem = {
  key: ConsumerNavItemKey;
  labelKey: string;
  to: string;
  group: ConsumerNavGroupKey;
  /**
   * Mirrors route-level guest gating in App.tsx.
   */
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
  routeKey: ConsumerRouteKey;
  group: ConsumerNavGroupKey;
  to: string;
  exact?: boolean;
  copy: Record<UiLanguage, ConsumerRouteStoryCopy>;
  primaryTo?: string;
  secondaryTo?: string;
};

export const CONSUMER_NAV_GROUPS: Array<{
  key: ConsumerNavGroupKey;
  label: Record<UiLanguage, string>;
}> = [
  { key: 'cockpit', label: { zh: '市场结构', en: 'Market Structure' } },
  { key: 'research', label: { zh: '研究队列', en: 'Research Queue' } },
  { key: 'context', label: { zh: '研究上下文', en: 'Research Context' } },
  { key: 'observe', label: { zh: '观察验证', en: 'Observation' } },
];

export const CONSUMER_NAV_ITEMS: ConsumerNavItem[] = [
  ...PRIMARY_CONSUMER_ROUTES.map((route) => ({
    key: route.key,
    labelKey: route.labelKey,
    to: route.path,
    group: route.group,
    requiresAuth: route.requiresAuth,
  })),
];

export const ROUTE_STORIES: ConsumerRouteStory[] = [
  {
    routeKey: 'home',
    group: 'cockpit',
    to: '/',
    exact: true,
    primaryTo: '/market/decision-cockpit',
    secondaryTo: '/research/radar',
    copy: {
      zh: {
        eyebrow: '首页 / 研究起点',
        title: '从市场结构驾驶舱开始，再进入个股研究。',
        purpose: '首页保留标的搜索、最近观察和继续研究入口；主要市场入口迁移到决策驾驶舱。',
        nextStep: '先打开决策驾驶舱确认市场结构，再进入研究雷达查看队列。',
        evidence: '证据边界：摘要、图表与报告状态会标明覆盖度。',
        boundary: '当前内容只用于研究观察，不产生外部动作，也不会改变持仓记录。',
        primaryAction: '打开决策驾驶舱',
        secondaryAction: '查看研究雷达',
      },
      en: {
        eyebrow: 'Home / Research Start',
        title: 'Start from the market-structure cockpit, then move into single-name research.',
        purpose: 'Home keeps ticker search, recent observations, and continuation entry points; the primary market entry is the Decision Cockpit.',
        nextStep: 'Open Decision Cockpit first, then use Research Radar for the queue.',
        evidence: 'Evidence boundary: summaries, charts, and reports expose coverage status.',
        boundary: 'Content is for research observation only; it creates no external action and does not change holdings.',
        primaryAction: 'Open Decision Cockpit',
        secondaryAction: 'Review Research Radar',
      },
    },
  },
  {
    routeKey: 'guest',
    group: 'cockpit',
    to: '/guest',
    exact: true,
    primaryTo: '/market-overview',
    secondaryTo: '/login',
    copy: {
      zh: {
        eyebrow: '游客 / 公开预览',
        title: '游客路由保留独立入口，只展示公开安全的研究预览。',
        purpose: '游客页用于在登录前查看产品预览、公开市场观察和受限能力说明。',
        nextStep: '继续查看市场总览，或登录后恢复个人研究上下文。',
        evidence: '证据边界：公开预览会标明可用、降级或本地快照状态。',
        boundary: '游客预览只用于了解研究流程，不保存个人记录，也不触发外部动作。',
        primaryAction: '打开市场总览',
        secondaryAction: '登录',
      },
      en: {
        eyebrow: 'Guest / Public Preview',
        title: 'The guest route remains a dedicated public-safe preview entry.',
        purpose: 'Guest mode shows product preview, public market observation, and limited-capability context before sign-in.',
        nextStep: 'Continue to Market Overview, or sign in to restore personal research context.',
        evidence: 'Evidence boundary: public previews expose ready, degraded, or local snapshot states.',
        boundary: 'Guest preview is for understanding the research flow only; it saves no personal record and creates no external action.',
        primaryAction: 'Open Market Overview',
        secondaryAction: 'Sign in',
      },
    },
  },
  {
    routeKey: 'decision-cockpit',
    group: 'cockpit',
    to: '/market/decision-cockpit',
    primaryTo: '/research/radar',
    secondaryTo: '/market-overview',
    copy: {
      zh: {
        eyebrow: '市场结构 / 决策驾驶舱',
        title: '把市场状态、研究队列和置信边界放在第一屏。',
        purpose: '决策驾驶舱是市场入口，用于判断今天应先看结构、流动性、主题扩散还是证据缺口。',
        nextStep: '继续进入研究雷达，或回到市场总览查看更细的市场地图。',
        evidence: '证据边界：Gamma/期权信号保持观察级，不上升为判断级结论。',
        boundary: '驾驶舱只做市场结构观察，不产生外部动作，也不形成个性化判断。',
        primaryAction: '打开研究雷达',
        secondaryAction: '打开市场总览',
      },
      en: {
        eyebrow: 'Market Structure / Decision Cockpit',
        title: 'Put regime, research queue, and confidence limits in the first viewport.',
        purpose: 'Decision Cockpit is the market entry for deciding whether structure, liquidity, theme breadth, or evidence gaps need attention first.',
        nextStep: 'Continue to Research Radar, or open Market Overview for the wider market map.',
        evidence: 'Evidence boundary: Gamma/options signals remain observation-level and do not become decision-grade conclusions.',
        boundary: 'The cockpit is market-structure observation only; it creates no external action and no personalized decision.',
        primaryAction: 'Open Research Radar',
        secondaryAction: 'Open Market Overview',
      },
    },
  },
  {
    routeKey: 'research-radar',
    group: 'research',
    to: '/research/radar',
    primaryTo: '/stocks/structure-decision',
    secondaryTo: '/scanner',
    copy: {
      zh: {
        eyebrow: '研究队列 / 雷达',
        title: '把市场结构线索转成可复核的个股研究队列。',
        purpose: '研究雷达承接驾驶舱，把优先级、研究偏向、验证项和风险标记放在同一队列。',
        nextStep: '选择队列条目进入个股结构，或回到扫描器补充候选来源。',
        evidence: '证据边界：队列展示原因、待验证事项、失效观察和数据质量，不暴露底层诊断细节。',
        boundary: '研究雷达只排序研究关注点，不触发提醒、账户动作或外部执行。',
        primaryAction: '打开个股结构',
        secondaryAction: '查看扫描器',
      },
      en: {
        eyebrow: 'Research Queue / Radar',
        title: 'Translate market-structure clues into a reviewable single-name queue.',
        purpose: 'Research Radar follows the cockpit with priority, research bias, verification items, and risk flags.',
        nextStep: 'Open Stock Structure for a queue item, or return to Scanner for candidate context.',
        evidence: 'Evidence boundary: queue rationale, verification items, invalidation observations, and data quality are shown without lower-level diagnostic detail.',
        boundary: 'Research Radar ranks research attention only; it triggers no alert, account action, or external execution.',
        primaryAction: 'Open Stock Structure',
        secondaryAction: 'Review Scanner',
      },
    },
  },
  {
    routeKey: 'stock-structure',
    group: 'research',
    to: '/stocks/structure-decision',
    primaryTo: '/research/radar',
    secondaryTo: '/watchlist',
    copy: {
      zh: {
        eyebrow: '个股研究 / 结构',
        title: '先看结构状态、证据缺口和失效观察，再沉淀到上下文。',
        purpose: '个股结构入口用于进入具体标的结构页，并把趋势、相对强弱、关键位置和研究备注组织到同一工作区。',
        nextStep: '从研究雷达选择标的，或把需要持续观察的对象沉淀到观察列表。',
        evidence: '证据边界：结构页显示可用 K 线、缺失证据和 no-advice 披露。',
        boundary: '结构状态是研究观察，不是外部动作、记录变更或个性化建议。',
        primaryAction: '返回研究雷达',
        secondaryAction: '打开观察列表',
      },
      en: {
        eyebrow: 'Single-name Research / Structure',
        title: 'Read structure state, evidence gaps, and invalidation observations before adding context.',
        purpose: 'Stock Structure opens a specific ticker workspace with trend, relative strength, key levels, and research notes.',
        nextStep: 'Choose a ticker from Research Radar, or keep ongoing names in Watchlist.',
        evidence: 'Evidence boundary: the structure page exposes usable bars, missing evidence, and no-advice disclosure.',
        boundary: 'Structure state is research observation, not external action, record mutation, or personalized advice.',
        primaryAction: 'Back to Research Radar',
        secondaryAction: 'Open Watchlist',
      },
    },
  },
  {
    routeKey: 'scanner',
    group: 'context',
    to: '/scanner',
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
    routeKey: 'portfolio',
    group: 'context',
    to: '/portfolio',
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
    routeKey: 'market-overview',
    group: 'cockpit',
    to: '/market-overview',
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
    group: 'cockpit',
    to: '/market/liquidity-monitor',
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
    group: 'cockpit',
    to: '/market/rotation-radar',
    primaryTo: '/scanner',
    secondaryTo: '/market-overview',
    copy: {
      zh: {
        eyebrow: '市场 / 轮动',
        title: '从主题扩散和退潮中找到下一批研究对象。',
        purpose: '轮动雷达把主题、家族和强弱状态整理成观察队列。',
        nextStep: '确认主题后，继续查看扫描器中的可复核候选。',
        evidence: '证据边界：只展示当前可解释的主题支持与限制。',
        boundary: '轮动状态仅用于研究排序和情景复核，不产生外部动作。',
        primaryAction: '查看扫描器',
        secondaryAction: '返回市场总览',
      },
      en: {
        eyebrow: 'Markets / Rotation',
        title: 'Use theme broadening and cooling to find the next research queue.',
        purpose: 'Rotation Radar organizes themes, families, and strength states into an observation queue.',
        nextStep: 'After confirming a theme, continue to Scanner for reviewable candidates.',
        evidence: 'Evidence boundary: only explainable theme support and limits are shown.',
        boundary: 'Rotation states support research ranking and scenario review only; they create no external action.',
        primaryAction: 'Review Scanner',
        secondaryAction: 'Back to Overview',
      },
    },
  },
  {
    routeKey: 'watchlist',
    group: 'context',
    to: '/watchlist',
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
    routeKey: 'backtest',
    group: 'observe',
    to: '/backtest',
    primaryTo: '/watchlist',
    secondaryTo: '/market-overview',
    copy: {
      zh: {
        eyebrow: '验证 / 回测',
        title: '把研究假设放进确定性验证，而不是直接改动记录。',
        purpose: '回测页用于比较规则、窗口、结果摘要和可解释限制。',
        nextStep: '验证后回到观察列表沉淀研究对象，或回到市场总览确认背景。',
        evidence: '证据边界：结果、质量说明和导出细节默认保持可复核。',
        boundary: '回测结果只用于只读验证，不改变任何记录或持仓状态。',
        primaryAction: '回到观察列表',
        secondaryAction: '回到市场总览',
      },
      en: {
        eyebrow: 'Validate / Backtest',
        title: 'Put research assumptions into deterministic validation before scenario review.',
        purpose: 'Backtest compares rules, windows, result summaries, and explainable limits.',
        nextStep: 'After validation, return to Watchlist for research context or Market Overview for the backdrop.',
        evidence: 'Evidence boundary: results, quality notes, and export details stay reviewable.',
        boundary: 'Backtest output is read-only validation; it does not change records or holdings.',
        primaryAction: 'Back to Watchlist',
        secondaryAction: 'Back to Market Overview',
      },
    },
  },
  {
    routeKey: 'options-lab',
    group: 'observe',
    to: '/options-lab',
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
  {
    routeKey: 'scenario-lab',
    group: 'observe',
    to: '/scenario-lab',
    primaryTo: '/market/decision-cockpit',
    secondaryTo: '/market-overview',
    copy: {
      zh: {
        eyebrow: '观察验证 / Scenario Lab',
        title: 'Scenario Lab 当前先作为研究入口，保留只读情景对照。',
        purpose: '该入口预留给后续跨市场、个股和期权证据的只读情景对照。',
        nextStep: '当前先回到决策驾驶舱或市场总览查看已有观察面。',
        evidence: '证据边界：当前入口不读取底层数据通道、账户通道或原始诊断内容。',
        boundary: 'Scenario Lab 当前不运行额外模型、不写入记录，也不形成个性化判断。',
        primaryAction: '打开决策驾驶舱',
        secondaryAction: '回到市场总览',
      },
      en: {
        eyebrow: 'Observation / Scenario Lab',
        title: 'Scenario Lab currently stays as a read-only scenario entry for bounded research review.',
        purpose: 'The entry is reserved for future read-only scenario comparison across market, single-name, and options evidence.',
        nextStep: 'Use Decision Cockpit or Market Overview for the currently available observation surfaces.',
        evidence: 'Evidence boundary: the page reads no lower-level data channel, account channel, or raw diagnostic payload.',
        boundary: 'Scenario Lab currently runs no extra model, writes no record, and creates no personalized decision.',
        primaryAction: 'Open Decision Cockpit',
        secondaryAction: 'Back to Market Overview',
      },
    },
  },
];

export function getConsumerGroupLabel(group: ConsumerNavGroupKey, language: UiLanguage): string {
  return CONSUMER_NAV_GROUPS.find((item) => item.key === group)?.label[language] || group;
}

function normalizeConsumerPathname(pathname: string): string {
  const [withoutHash = '/'] = String(pathname || '/').trim().split('#', 1);
  const [withoutSearch = '/'] = withoutHash.split('?', 1);
  return stripLocalePrefix(withoutSearch || '/');
}

function isPathMatch(pathname: string, target: string, exact = false): boolean {
  const normalizedPathname = normalizeConsumerPathname(pathname);
  if (target === '/') {
    return normalizedPathname === '/' || normalizedPathname === '';
  }
  if (exact) {
    return normalizedPathname === target;
  }
  return normalizedPathname === target || normalizedPathname.startsWith(`${target}/`);
}

export function resolveConsumerNavItem(pathname: string): ConsumerNavItem | null {
  return CONSUMER_NAV_ITEMS.find((item) => isPathMatch(pathname, item.to, item.to === '/')) || null;
}

export function resolveConsumerRouteStory(pathname: string): ConsumerRouteStory | null {
  return ROUTE_STORIES.find((story) => isPathMatch(pathname, story.to, story.exact)) || null;
}
