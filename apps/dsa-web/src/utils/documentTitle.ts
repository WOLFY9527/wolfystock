import { translate, type UiLanguage } from '../i18n/core';
import { parseLocaleFromPathname, stripLocalePrefix } from './localeRouting';

const BRAND = 'WolfyStock';

type LocalizedTitle = Record<UiLanguage, string>;

const ROUTE_TITLES: Record<string, LocalizedTitle> = {
  '/': { zh: BRAND, en: BRAND },
  '/guest': { zh: '游客预览', en: 'Guest Preview' },
  '/scanner': { zh: '市场扫描', en: 'Market Scanner' },
  '/portfolio': { zh: '持仓', en: 'Portfolio' },
  '/market-overview': { zh: '市场总览', en: 'Market Overview' },
  '/market/decision-cockpit': { zh: '市场决策驾驶舱', en: 'Decision Cockpit' },
  '/market/liquidity-monitor': { zh: '流动性监测', en: 'Liquidity Monitor' },
  '/market/rotation-radar': { zh: '板块轮动', en: 'Sector Rotation' },
  '/stocks/structure-decision': { zh: '个股研究', en: 'Stock Research' },
  '/research/radar': { zh: '研究雷达', en: 'Research Radar' },
  '/scenario-lab': { zh: '情景实验室', en: 'Scenario Lab' },
  '/watchlist': { zh: '观察列表', en: 'Watchlist' },
  '/backtest': { zh: '回测', en: 'Backtest' },
  '/options-lab': { zh: '期权实验室', en: 'Options Lab' },
  '/backtest/compare': { zh: '规则回测比较工作台', en: 'Rule Backtest Comparison' },
  '/settings': { zh: '账户中心', en: 'Account Center' },
  '/settings/system': { zh: '系统设置', en: 'System Settings' },
  '/admin/launch-cockpit': { zh: '发布驾驶舱', en: 'Launch Cockpit' },
  '/admin/mission-control': { zh: '任务指挥中心', en: 'Mission Control' },
  '/admin/logs': { zh: '管理日志', en: 'Admin Logs' },
  '/admin/evidence-workflow': { zh: '证据工作流', en: 'Evidence Workflow' },
  '/admin/notifications': { zh: '管理通知', en: 'Admin Notifications' },
  '/admin/market-providers': { zh: '数据源运维', en: 'Provider Ops' },
  '/admin/provider-circuits': { zh: '熔断诊断', en: 'Circuit Diagnostics' },
  '/admin/users': { zh: '用户治理', en: 'User Governance' },
  '/admin/cost-observability': { zh: '成本观测', en: 'Cost Observability' },
  '/login': { zh: '登录', en: 'Login' },
  '/register': { zh: '登录', en: 'Login' },
  '/reset-password': { zh: '重置密码', en: 'Reset Password' },
};

const ALIASES: Record<string, string> = {
  '/guest/scanner': '/scanner',
  '/user/scanner': '/scanner',
  '/market': '/market-overview',
  '/admin': '/settings/system',
  '/admin/system': '/settings/system',
  '/admin/provider': '/admin/market-providers',
  '/admin/providers': '/admin/market-providers',
  '/admin/provider-operations': '/admin/market-providers',
  '/admin/evidence': '/admin/evidence-workflow',
  '/admin/costs': '/admin/cost-observability',
  '/admin/ai': '/settings/system',
  '/admin/system-logs': '/admin/logs',
  '/cockpit': '/market/decision-cockpit',
  '/decision-cockpit': '/market/decision-cockpit',
  '/radar': '/research/radar',
  '/research': '/research/radar',
  '/research-radar': '/research/radar',
  '/holdings': '/portfolio',
  '/liquidity': '/market/liquidity-monitor',
  '/rotation': '/market/rotation-radar',
  '/options': '/options-lab',
  '/chat': '/market-overview',
};

function titleFor(label: string): string {
  return label === BRAND ? BRAND : `${label} - ${BRAND}`;
}

function normalizeSymbol(rawSymbol: string): string {
  try {
    return decodeURIComponent(rawSymbol).trim().toUpperCase();
  } catch {
    return rawSymbol.trim().toUpperCase();
  }
}

function canonicalPath(pathname: string): string {
  const path = stripLocalePrefix(pathname).replace(/\/+$/, '') || '/';
  if (ALIASES[path]) return ALIASES[path];

  const legacyStockMatch = path.match(/^\/stock\/([^/]+)(?:\/structure-decision)?$/);
  if (legacyStockMatch) return `/stocks/${legacyStockMatch[1]}/structure-decision`;

  return path;
}

export function getDocumentTitle(pathname: string, language: UiLanguage): string {
  const routeLocale = parseLocaleFromPathname(pathname);
  const effectiveLanguage = routeLocale || language;
  const path = canonicalPath(pathname);
  const stockMatch = path.match(/^\/stocks\/([^/]+)\/structure-decision$/);
  if (stockMatch) {
    const symbol = normalizeSymbol(stockMatch[1]);
    return titleFor(effectiveLanguage === 'en' ? `${symbol} Stock Research` : `${symbol} 个股研究`);
  }

  const backtestResultMatch = path.match(/^\/backtest\/results\/([^/]+)$/);
  if (backtestResultMatch) {
    const runId = Number.parseInt(backtestResultMatch[1], 10);
    const label = translate(effectiveLanguage, 'backtest.resultPage.documentTitle');
    return titleFor(Number.isFinite(runId) && runId > 0 ? `${label} #${runId}` : label);
  }

  if (/^\/admin\/users(?:\/[^/]+){1,2}$/.test(path)) {
    return titleFor(ROUTE_TITLES['/admin/users'][effectiveLanguage]);
  }

  const title = ROUTE_TITLES[path];
  return titleFor(title ? title[effectiveLanguage] : effectiveLanguage === 'en' ? 'Page Not Found' : '页面未找到');
}
