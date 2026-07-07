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
  },
  {
    key: 'research-radar',
    labelKey: 'nav.researchRadar',
    path: '/research/radar',
    group: 'research',
    requiresAuth: true,
    primaryNav: true,
    pageIdentity: { zh: '今日观察队列', en: 'Today’s observation queue' },
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
  },
  {
    key: 'watchlist',
    labelKey: 'nav.watchlist',
    path: '/watchlist',
    group: 'context',
    requiresAuth: true,
    primaryNav: true,
    pageIdentity: { zh: '观察监控板', en: 'Watchlist monitoring board' },
  },
  {
    key: 'portfolio',
    labelKey: 'nav.portfolio',
    path: '/portfolio',
    group: 'context',
    requiresAuth: true,
    primaryNav: false,
    pageIdentity: { zh: '持仓管理', en: 'Holdings and portfolio exposure' },
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
