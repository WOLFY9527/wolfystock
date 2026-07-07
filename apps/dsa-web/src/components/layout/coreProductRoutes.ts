import type { UiLanguage } from '../../i18n/core';

export type CoreProductRouteKey =
  | 'home'
  | 'decision-cockpit'
  | 'market-overview'
  | 'research-radar'
  | 'stock-structure'
  | 'scanner'
  | 'watchlist'
  | 'portfolio'
  | 'backtest'
  | 'scenario-lab'
  | 'options-lab';

export type CoreProductRoute = {
  key: CoreProductRouteKey;
  labelKey: string;
  path: string;
  group: 'cockpit' | 'research' | 'context' | 'observe';
  requiresAuth: boolean;
  primaryNav: boolean;
  pageIdentity: Record<UiLanguage, string>;
  ctaLabel?: Record<UiLanguage, string>;
  ctaDescription?: Record<UiLanguage, string>;
};

export const CORE_PRODUCT_ROUTES: CoreProductRoute[] = [
  {
    key: 'home',
    labelKey: 'nav.home',
    path: '/',
    group: 'cockpit',
    requiresAuth: false,
    primaryNav: true,
    pageIdentity: { zh: '首页', en: 'Home' },
  },
  {
    key: 'decision-cockpit',
    labelKey: 'nav.marketDecisionCockpit',
    path: '/market/decision-cockpit',
    group: 'cockpit',
    requiresAuth: false,
    primaryNav: false,
    pageIdentity: { zh: '市场决策驾驶舱', en: 'Decision Cockpit' },
  },
  {
    key: 'market-overview',
    labelKey: 'nav.marketOverview',
    path: '/market-overview',
    group: 'cockpit',
    requiresAuth: false,
    primaryNav: true,
    pageIdentity: { zh: '市场总览', en: 'Market State Overview' },
    ctaLabel: { zh: '先看市场概览', en: 'Start with Market Overview' },
    ctaDescription: {
      zh: '先阅读市场背景，再决定是否继续进入标的研究。',
      en: 'Read broad market context before choosing symbols.',
    },
  },
  {
    key: 'research-radar',
    labelKey: 'nav.researchRadar',
    path: '/research/radar',
    group: 'research',
    requiresAuth: true,
    primaryNav: true,
    pageIdentity: { zh: '今日观察队列', en: 'Today’s observation queue' },
    ctaLabel: { zh: '查看研究雷达', en: 'Review Research Radar' },
    ctaDescription: {
      zh: '在扫描或观察列表有活动后，再回来看研究队列。',
      en: 'Review the queue after scanner or watchlist activity.',
    },
  },
  {
    key: 'stock-structure',
    labelKey: 'nav.stockStructure',
    path: '/stocks/structure-decision',
    group: 'research',
    requiresAuth: false,
    primaryNav: true,
    pageIdentity: { zh: '个股研究入口', en: 'Stock Research Entry' },
  },
  {
    key: 'scanner',
    labelKey: 'nav.scanner',
    path: '/scanner',
    group: 'context',
    requiresAuth: true,
    primaryNav: false,
    pageIdentity: { zh: '扫描工作台', en: 'Scanner workspace' },
    ctaLabel: { zh: '运行 Scanner', en: 'Run Scanner' },
    ctaDescription: {
      zh: '由你手动运行扫描，形成可复核候选。',
      en: 'Run a user-triggered scan to create candidates.',
    },
  },
  {
    key: 'watchlist',
    labelKey: 'nav.watchlist',
    path: '/watchlist',
    group: 'context',
    requiresAuth: true,
    primaryNav: true,
    pageIdentity: { zh: '观察监控板', en: 'Watchlist monitoring board' },
    ctaLabel: { zh: '选择观察标的', en: 'Add Watchlist Symbol' },
    ctaDescription: {
      zh: '只在你想持续观察某个代码时再保存。',
      en: 'Choose a symbol only when you want to keep observing it.',
    },
  },
  {
    key: 'portfolio',
    labelKey: 'nav.portfolio',
    path: '/portfolio',
    group: 'context',
    requiresAuth: true,
    primaryNav: false,
    pageIdentity: { zh: '持仓管理', en: 'Holdings and portfolio exposure' },
    ctaLabel: { zh: '创建组合账户', en: 'Create portfolio account' },
    ctaDescription: {
      zh: '只有你明确想跟踪组合时才创建账户。',
      en: 'Create an account only when you want portfolio tracking.',
    },
  },
  {
    key: 'backtest',
    labelKey: 'nav.backtest',
    path: '/backtest',
    group: 'observe',
    requiresAuth: true,
    primaryNav: false,
    pageIdentity: { zh: '回测工作台', en: 'Backtest workbench' },
  },
  {
    key: 'scenario-lab',
    labelKey: 'nav.scenarioLab',
    path: '/scenario-lab',
    group: 'observe',
    requiresAuth: true,
    primaryNav: false,
    pageIdentity: { zh: '情景实验室：假设推演工作台', en: 'Scenario Lab what-if workbench' },
  },
  {
    key: 'options-lab',
    labelKey: 'nav.optionsLab',
    path: '/options-lab',
    group: 'observe',
    requiresAuth: true,
    primaryNav: false,
    pageIdentity: { zh: '期权实验室', en: 'Options Lab' },
  },
];

export const PRIMARY_CONSUMER_ROUTES = CORE_PRODUCT_ROUTES.filter((route) => route.primaryNav);
export const SECONDARY_CONSUMER_ROUTES = CORE_PRODUCT_ROUTES.filter((route) => !route.primaryNav);

export function normalizeConsumerRoutePath(pathname: string): string {
  const withoutQuery = String(pathname || '/').split(/[?#]/, 1)[0] || '/';
  const normalized = withoutQuery.replace(/\/+$/, '') || '/';
  return normalized === '/' ? normalized : normalized.toLowerCase();
}

function stripConsumerLocale(pathname: string): string {
  const normalized = normalizeConsumerRoutePath(pathname);
  const match = normalized.match(/^\/(zh|en)(?:\/(.*))?$/);
  if (!match) return normalized;
  return match[2] ? `/${match[2]}` : '/';
}

export function consumerRouteMatches(pathname: string, route: CoreProductRoute): boolean {
  const normalizedPathname = stripConsumerLocale(pathname);
  const target = normalizeConsumerRoutePath(route.path);

  if (target === '/') {
    return normalizedPathname === '/';
  }
  if (route.key === 'stock-structure') {
    return normalizedPathname === target
      || /^\/stocks\/[^/]+\/structure-decision$/i.test(normalizedPathname);
  }
  if (route.key === 'decision-cockpit') {
    return normalizedPathname === '/cockpit'
      || normalizedPathname === '/decision-cockpit'
      || normalizedPathname === target
      || normalizedPathname.startsWith(`${target}/`);
  }
  if (route.key === 'research-radar') {
    return normalizedPathname === '/radar'
      || normalizedPathname === '/research-radar'
      || normalizedPathname === target
      || normalizedPathname.startsWith(`${target}/`);
  }
  if (route.key === 'portfolio') {
    return normalizedPathname === '/holdings'
      || normalizedPathname === target
      || normalizedPathname.startsWith(`${target}/`);
  }

  return normalizedPathname === target || normalizedPathname.startsWith(`${target}/`);
}

export function resolveCurrentConsumerRoute(pathname: string): CoreProductRoute | null {
  return CORE_PRODUCT_ROUTES.find((route) => consumerRouteMatches(pathname, route)) ?? null;
}

export function resolveCurrentConsumerRouteKey(pathname: string): CoreProductRouteKey | null {
  return resolveCurrentConsumerRoute(pathname)?.key ?? null;
}

export function getCoreProductRouteByKey(key: CoreProductRouteKey): CoreProductRoute {
  const route = CORE_PRODUCT_ROUTES.find((item) => item.key === key);
  if (!route) {
    throw new Error(`Unknown core product route: ${key}`);
  }
  return route;
}

export function resolveCoreProductRouteByCanonicalPath(pathname: string): CoreProductRoute | null {
  const normalizedPathname = stripConsumerLocale(pathname);
  return CORE_PRODUCT_ROUTES.find((route) => normalizeConsumerRoutePath(route.path) === normalizedPathname) ?? null;
}
