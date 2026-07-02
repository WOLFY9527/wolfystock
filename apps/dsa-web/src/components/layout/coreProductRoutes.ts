import type { UiLanguage } from '../../i18n/core';

export type CoreProductRouteKey =
  | 'decision-cockpit'
  | 'market-overview'
  | 'research-radar'
  | 'stock-structure'
  | 'scanner'
  | 'watchlist'
  | 'portfolio'
  | 'backtest'
  | 'scenario-lab';

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
    key: 'decision-cockpit',
    labelKey: 'nav.marketDecisionCockpit',
    path: '/market/decision-cockpit',
    group: 'cockpit',
    requiresAuth: false,
    primaryNav: true,
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
    pageIdentity: { zh: '个股结构入口', en: 'Stock Structure Entry' },
  },
  {
    key: 'scanner',
    labelKey: 'nav.scanner',
    path: '/scanner',
    group: 'context',
    requiresAuth: true,
    primaryNav: true,
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
    primaryNav: true,
    pageIdentity: { zh: '持仓管理', en: 'Holdings and portfolio exposure' },
  },
  {
    key: 'backtest',
    labelKey: 'nav.backtest',
    path: '/backtest',
    group: 'observe',
    requiresAuth: true,
    primaryNav: true,
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
];

export const PRIMARY_CONSUMER_ROUTES = CORE_PRODUCT_ROUTES.filter((route) => route.primaryNav);
