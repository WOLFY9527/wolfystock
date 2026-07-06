import { useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
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
import {
  consumerPresentationRouteHint,
  consumerPresentationText,
} from '../utils/consumerPresentationBoundary';
import { buildLocalizedPath, parseLocaleFromPathname } from '../utils/localeRouting';
import { validateStockCode } from '../utils/validation';
import { RoughBulletList, RoughSectionCard, RoughSurfaceIntro } from './roughShellShared';

function parseStockStructureSymbols(value: string | null | undefined): string[] {
  return [...new Set(String(value || '')
    .split(/[,\s;|+]+/)
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean))];
}

function normalizeDirectSymbolInput(value: string): string {
  return value.trim().toUpperCase();
}

export default function StockStructureDecisionEntryPage() {
  const { language } = useI18n();
  const locale = language === 'en' ? 'en' : 'zh';
  const location = useLocation();
  const navigate = useNavigate();
  const routeLocale = parseLocaleFromPathname(location.pathname);
  const localize = (path: string) => (routeLocale ? buildLocalizedPath(path, routeLocale) : path);
  const searchParams = new URLSearchParams(location.search);
  const requestedSymbols = parseStockStructureSymbols(searchParams.get('symbols'));
  const carriedSymbol = requestedSymbols[0] || '';
  const hasCarriedSymbol = Boolean(carriedSymbol);
  const [symbolInput, setSymbolInput] = useState(carriedSymbol);
  const [symbolError, setSymbolError] = useState('');

  const submitDirectSymbol = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalized = normalizeDirectSymbolInput(symbolInput);
    if (!normalized) {
      setSymbolError(locale === 'en' ? 'Enter a stock symbol.' : '请输入股票代码。');
      return;
    }
    const validation = validateStockCode(normalized);
    if (!validation.valid) {
      setSymbolError(locale === 'en'
        ? 'Use an existing app symbol format such as AAPL, 600519, or 0700.HK.'
        : validation.message || '股票代码格式不正确。');
      return;
    }
    setSymbolError('');
    navigate(localize(`/stocks/${encodeURIComponent(validation.normalized)}/structure-decision`));
  };

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
                  ? 'Enter a known symbol directly, or choose one from the research workflow.'
                  : '可直接输入已知标的，也可从研究工作流选择。'}
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
                    locale === 'en' ? 'Enter a symbol directly when you already know what to inspect.' : '已知道代码时，可直接输入标的进入结构视图。',
                    locale === 'en' ? 'Use Scanner, Watchlist, or Research Radar rows when exploring candidates.' : '探索候选时，可从 Scanner、观察列表或研究雷达进入。',
                    consumerPresentationRouteHint(locale),
                    locale === 'en' ? 'Missing or degraded price-history evidence stays visible on the detail page.' : '历史行情证据缺失或降级会在详情页可见。',
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
              eyebrow={locale === 'en' ? 'Stock Research' : '个股研究'}
              title={locale === 'en' ? 'Open stock research by symbol' : '输入标的进入个股研究'}
              description={locale === 'en'
                ? 'Enter a known symbol directly or continue from Market Overview, Research Radar, Watchlist, or secondary validation tools.'
                : '直接输入已知股票代码，或从市场总览、研究雷达、观察列表与二级验证工具继续进入。'}
            />
            <MetricStrip
              items={[
                { key: 'state', label: locale === 'en' ? 'Current state' : '当前状态', value: locale === 'en' ? 'Waiting for ticker' : '等待选择标的' },
                {
                  key: 'data-connection',
                  label: locale === 'en' ? 'Data read' : '数据读取',
                  value: locale === 'en' ? 'No request until a ticker is selected' : '选择标的后再读取数据',
                },
                { key: 'boundary', label: locale === 'en' ? 'Boundary' : '边界', value: locale === 'en' ? 'Research observation' : '研究观察' },
              ]}
            />
            <div className="grid gap-3 p-3 md:grid-cols-2">
              <RoughSectionCard eyebrow={locale === 'en' ? 'Direct entry' : '直接入口'} title={locale === 'en' ? 'Enter symbol' : '直接输入标的'}>
                <form className="space-y-3" onSubmit={submitDirectSymbol} noValidate>
                  <div className="space-y-2">
                    <label htmlFor="stock-structure-direct-symbol" className="text-xs font-semibold text-[color:var(--wolfy-text-secondary)]">
                      {locale === 'en' ? 'Stock symbol' : '股票代码'}
                    </label>
                    <div className="flex flex-col gap-2 sm:flex-row">
                      <input
                        id="stock-structure-direct-symbol"
                        value={symbolInput}
                        className="min-h-11 flex-1 rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface)] px-3 py-2 font-mono text-sm uppercase text-[color:var(--wolfy-text-primary)] outline-none transition-colors placeholder:normal-case placeholder:text-[color:var(--wolfy-text-muted)] focus:border-[color:var(--wolfy-accent)]"
                        onChange={(event) => {
                          setSymbolInput(event.target.value);
                          if (symbolError) setSymbolError('');
                        }}
                        placeholder={locale === 'en' ? 'AAPL, 600519, 0700.HK' : 'AAPL、600519、0700.HK'}
                        aria-invalid={Boolean(symbolError)}
                        aria-describedby={symbolError ? 'stock-structure-direct-symbol-error' : 'stock-structure-direct-symbol-help'}
                      />
                      <button
                        type="submit"
                        className="inline-flex min-h-11 items-center justify-center rounded-md border border-[color:var(--wolfy-accent)] bg-[var(--wolfy-accent)] px-4 py-2 text-sm font-semibold text-[color:var(--theme-button-primary-text)] transition-colors hover:border-[color:var(--wolfy-border-focus)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--wolfy-accent)]"
                      >
                        {locale === 'en' ? 'Open research' : '打开研究'}
                      </button>
                    </div>
                    {symbolError ? (
                      <p id="stock-structure-direct-symbol-error" role="alert" className="text-xs leading-5 text-[color:var(--state-danger-text)]">
                        {symbolError}
                      </p>
                    ) : (
                      <p id="stock-structure-direct-symbol-help" className="text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                        {locale === 'en'
                          ? 'Supports existing app symbol formats such as A-share codes, US tickers, and HK suffixes.'
                          : '支持应用现有代码形态，例如 A 股代码、美股 ticker 与港股后缀。'}
                      </p>
                    )}
                  </div>
                </form>
              </RoughSectionCard>
              <RoughSectionCard eyebrow={locale === 'en' ? 'Empty state' : '空状态'} title={locale === 'en' ? 'No ticker selected' : '尚未选择标的'}>
                <TerminalEmptyState title={locale === 'en' ? 'Choose an entry path' : '选择进入路径'}>
                  <div className="space-y-1">
                    <p>
                      {hasCarriedSymbol
                        ? (locale === 'en'
                          ? `${carriedSymbol} is already carried into this entry. Add another symbol to start a structure comparison.`
                          : `已带入 ${carriedSymbol}。输入或添加另一个标的后，可进行结构对比。`)
                        : (locale === 'en'
                          ? 'Enter a symbol directly, or choose a ticker from Scanner, Watchlist, or Research Radar.'
                          : '可以直接输入标的，也可以从 Scanner、观察列表或研究雷达选择标的后进入。')}
                    </p>
                    <p>
                      {locale === 'en'
                        ? 'Missing quote, fundamentals, catalyst, peer, or price-history evidence remains visible on the detail page.'
                        : '报价、基本面、催化、同业或历史行情证据缺失时，会在详情页继续显示就绪边界。'}
                    </p>
                  </div>
                </TerminalEmptyState>
                <div className="mt-3 flex flex-wrap gap-2">
                  <TerminalChip variant="info">{consumerPresentationText(locale === 'en' ? 'No raw payload' : '不展示' + '原始载荷', locale)}</TerminalChip>
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
