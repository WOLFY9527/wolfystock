import { Link, useLocation } from 'react-router-dom';
import {
  ConsoleBoard,
  ConsoleContextRail,
  MetricStrip,
  ResearchConsoleShell,
  WolfyCommandBar,
} from '../components/linear/LinearPrimitives';
import { ConsumerWorkspacePageShell, ConsumerWorkspaceScope } from '../components/layout/ConsumerWorkspaceShell';
import { TerminalChip, TerminalEmptyState } from '../components/terminal/TerminalPrimitives';
import { useI18n } from '../contexts/UiLanguageContext';
import { buildLocalizedPath, parseLocaleFromPathname } from '../utils/localeRouting';
import { RoughBulletList, RoughSectionCard, RoughSurfaceIntro } from './roughShellShared';

function parseStockStructureSymbols(value: string | null | undefined): string[] {
  return [...new Set(String(value || '')
    .split(/[,\s;|+]+/)
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean))];
}

export default function StockStructureDecisionEntryPage() {
  const { language } = useI18n();
  const locale = language === 'en' ? 'en' : 'zh';
  const location = useLocation();
  const routeLocale = parseLocaleFromPathname(location.pathname);
  const localize = (path: string) => (routeLocale ? buildLocalizedPath(path, routeLocale) : path);
  const searchParams = new URLSearchParams(location.search);
  const requestedSymbols = parseStockStructureSymbols(searchParams.get('symbols'));
  const carriedSymbol = requestedSymbols[0] || '';
  const hasCarriedSymbol = Boolean(carriedSymbol);

  return (
    <ConsumerWorkspaceScope className="flex min-h-0 flex-1">
      <ConsumerWorkspacePageShell className="flex min-h-0 flex-1 flex-col gap-4 md:gap-6">
        <ResearchConsoleShell
          className="flex-1"
          command={(
            <WolfyCommandBar
              leading={<span className="text-xs text-[color:var(--wolfy-text-muted)]">{locale === 'en' ? 'Single-name research / Entry' : '个股研究 / 入口'}</span>}
              trailing={(
                <div className="flex flex-wrap items-center gap-2">
                  <Link
                    to={localize('/research/radar')}
                    className="rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)]"
                  >
                    {locale === 'en' ? 'Research radar' : '研究雷达'}
                  </Link>
                  <Link
                    to={localize('/watchlist')}
                    className="rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)]"
                  >
                    {locale === 'en' ? 'Watchlist context' : '观察列表上下文'}
                  </Link>
                </div>
              )}
            >
              <div className="text-xs text-[color:var(--wolfy-text-secondary)]">
                {locale === 'en'
                  ? 'Choose a ticker from Research Radar or open a known structure URL.'
                  : '从研究雷达选择标的，或打开已知结构 URL。'}
              </div>
            </WolfyCommandBar>
          )}
          rail={(
            <ConsoleContextRail className="flex flex-col gap-3 p-3">
              <RoughSectionCard eyebrow={locale === 'en' ? 'Boundary' : '边界'} title={locale === 'en' ? 'Observation-only' : '仅观察'}>
                <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
                  {locale === 'en'
                    ? 'Research context'
                    : '研究上下文'}
                </p>
              </RoughSectionCard>
              <RoughSectionCard eyebrow={locale === 'en' ? 'Routes' : '路由'} title={locale === 'en' ? 'How to open detail' : '如何进入详情'}>
                <RoughBulletList
                  items={[
                    locale === 'en' ? 'Use Research Radar queue rows when available.' : '优先从研究雷达队列条目进入。',
                    locale === 'en' ? 'Direct URL pattern: /stocks/{ticker}/structure-decision.' : '直接 URL 形态：/stocks/{ticker}/structure-decision。',
                    locale === 'en' ? 'Missing or degraded OHLCV evidence stays visible on the detail page.' : 'K 线证据缺失或降级会在详情页可见。',
                    locale === 'en'
                      ? 'After entering or adding another symbol, compare mode focuses on structural differences and evidence completeness only.'
                      : '输入或添加另一个标的后，可进行结构对比。',
                  ]}
                  emptyText=""
                />
              </RoughSectionCard>
            </ConsoleContextRail>
          )}
        >
          <ConsoleBoard className="min-h-0" data-testid="stock-structure-entry-page">
            <RoughSurfaceIntro
              eyebrow={locale === 'en' ? 'Stock Structure Decision' : '个股结构决策'}
              title={locale === 'en' ? 'Single-name structure starts from a research queue' : '个股结构从研究队列进入'}
              description={locale === 'en'
                ? 'Select a ticker to open the structure workspace.'
                : '选择标的后打开结构工作区。'}
            />
            <MetricStrip
              items={[
                { key: 'state', label: locale === 'en' ? 'Current state' : '当前状态', value: locale === 'en' ? 'Waiting for ticker' : '等待选择标的' },
                { key: 'api', label: locale === 'en' ? 'API call' : '接口调用', value: locale === 'en' ? 'None on entry' : '入口不调用' },
                { key: 'boundary', label: locale === 'en' ? 'Boundary' : '边界', value: locale === 'en' ? 'Research observation' : '研究观察' },
              ]}
            />
            <div className="grid gap-3 p-3 md:grid-cols-2">
              <RoughSectionCard eyebrow={locale === 'en' ? 'Primary path' : '主路径'} title={locale === 'en' ? 'Research workflow' : '研究工作流'}>
                <RoughBulletList
                  items={[
                    locale === 'en' ? 'Decision Cockpit frames the market structure.' : '决策驾驶舱先确认市场结构。',
                    locale === 'en' ? 'Research Radar provides the ticker queue.' : '研究雷达提供标的队列。',
                    locale === 'en' ? 'Stock Structure records structure state, evidence gaps, and invalidation observations.' : '个股结构承载结构状态、证据缺口与失效观察。'
                  ]}
                  emptyText=""
                />
              </RoughSectionCard>
              <RoughSectionCard eyebrow={locale === 'en' ? 'Empty state' : '空状态'} title={locale === 'en' ? 'No ticker selected' : '尚未选择标的'}>
                <TerminalEmptyState title={locale === 'en' ? 'Open Research Radar first' : '先打开研究雷达'}>
                  <div className="space-y-1">
                    <p>
                      {hasCarriedSymbol
                        ? (locale === 'en'
                          ? `${carriedSymbol} is already carried into this entry. Add another symbol to start a structure comparison.`
                          : `已带入 ${carriedSymbol}。输入或添加另一个标的后，可进行结构对比。`)
                        : (locale === 'en'
                          ? 'When the radar returns queue rows, each ticker can deep-link into this structure workspace.'
                          : '研究雷达返回队列后，每个标的都可以深链进入结构工作区。')}
                    </p>
                    <p>
                      {locale === 'en'
                        ? 'Compare mode focuses on structural differences and evidence completeness.'
                        : '对比仅展示结构差异和证据完整度。'}
                    </p>
                  </div>
                </TerminalEmptyState>
                <div className="mt-3 flex flex-wrap gap-2">
                  <TerminalChip variant="info">{locale === 'en' ? 'No raw payload' : '不展示原始载荷'}</TerminalChip>
                  <TerminalChip variant="info">{locale === 'en' ? 'No external action' : '不触发外部动作'}</TerminalChip>
                </div>
              </RoughSectionCard>
            </div>
          </ConsoleBoard>
        </ResearchConsoleShell>
      </ConsumerWorkspacePageShell>
    </ConsumerWorkspaceScope>
  );
}
