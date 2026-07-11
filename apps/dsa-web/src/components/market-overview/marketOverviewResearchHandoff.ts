import { buildLocalizedPath } from '../../utils/localeRouting';
import type { NextResearchActionItem } from '../research/anatomy';

/**
 * Journey handoff after market observation -> path -> metrics -> drivers -> data state.
 * Uses onClick navigation so page unit harnesses without Router still exercise controls.
 */
export function buildMarketOverviewResearchHandoffSteps(
  routeLocale: 'zh' | 'en' | null = null,
): NextResearchActionItem[] {
  const isEnglishRoute = routeLocale === 'en';
  const assign = (path: string) => {
    const href = routeLocale ? buildLocalizedPath(path, routeLocale) : path;
    if (typeof window !== 'undefined') {
      window.location.assign(href);
    }
  };
  return [
    {
      key: 'research-radar',
      kind: 'inspect',
      label: isEnglishRoute ? 'Research Radar' : '研究雷达',
      description: isEnglishRoute
        ? 'Inspect Research Radar priorities against the current market observation.'
        : '查看研究雷达优先级，对照当前市场观察。',
      onClick: () => assign('/research/radar'),
    },
    {
      key: 'watchlist',
      kind: 'handoff',
      label: isEnglishRoute ? 'Watchlist' : '观察列表',
      description: isEnglishRoute
        ? 'Carry market context into the research task ledger.'
        : '把市场上下文带入观察列表研究任务账本。',
      onClick: () => assign('/watchlist'),
    },
    {
      key: 'stock-structure',
      kind: 'validate',
      label: isEnglishRoute ? 'Stock Search' : '搜索个股',
      description: isEnglishRoute
        ? 'Validate single-name structure against this market context.'
        : '用结构页在当前市场背景下验证个股证据。',
      onClick: () => assign('/stocks/structure-decision'),
    },
    {
      key: 'decision-cockpit',
      kind: 'compare',
      label: isEnglishRoute ? 'Decision Cockpit' : '决策驾驶舱',
      description: isEnglishRoute
        ? 'Compare Decision Cockpit evidence without implying a trade decision.'
        : '比较决策驾驶舱证据，不升级为交易结论。',
      onClick: () => assign('/market/decision-cockpit'),
    },
    {
      key: 'scanner',
      kind: 'handoff',
      label: isEnglishRoute ? 'Scanner' : '扫描器',
      description: isEnglishRoute
        ? 'Continue research screening under the same observation constraints.'
        : '继续到扫描器，在同一观察约束下筛选研究候选。',
      onClick: () => assign('/scanner'),
    },
  ];
}
