import React, { useMemo, useState } from 'react';
import {
  Activity,
  BarChart3,
  ChevronDown,
  MoreHorizontal,
  Play,
  Radar,
  SlidersHorizontal,
  TrendingUp,
} from 'lucide-react';

type DensityMode = 'normal' | 'compact' | 'expanded';

type BoardCandidate = {
  rank: number;
  symbol: string;
  name: string;
  score: number;
  trend: string;
  strength: number;
  reason: string;
  risk: string;
  quality: string;
  liquidity: string;
  trigger: string;
  pullback: string;
};

const BOARD_CANDIDATES: BoardCandidate[] = [
  {
    rank: 1,
    symbol: 'NVDA',
    name: 'NVIDIA',
    score: 96,
    trend: '加速上行',
    strength: 94,
    reason: '量能放大后重新站回短期均线。',
    risk: '财报窗口',
    quality: 'A',
    liquidity: '极高',
    trigger: '突破 1,066 后延续',
    pullback: '1,018 附近失守降级',
  },
  {
    rank: 2,
    symbol: 'ARM',
    name: 'Arm Holdings',
    score: 89,
    trend: '突破确认',
    strength: 87,
    reason: '高位横盘收敛，买盘仍在抬升。',
    risk: '估值敏感',
    quality: 'A-',
    liquidity: '高',
    trigger: '站稳 139.5',
    pullback: '回落 131 下方',
  },
  {
    rank: 3,
    symbol: 'MU',
    name: 'Micron',
    score: 84,
    trend: '趋势修复',
    strength: 82,
    reason: '存储链强度回升，回撤承接较好。',
    risk: '周期波动',
    quality: 'B+',
    liquidity: '高',
    trigger: '放量越过 132',
    pullback: '跌回 125',
  },
  {
    rank: 4,
    symbol: 'VRT',
    name: 'Vertiv',
    score: 80,
    trend: '相对强势',
    strength: 79,
    reason: '数据中心电力链继续跑赢指数。',
    risk: '换手偏热',
    quality: 'B+',
    liquidity: '中高',
    trigger: '维持 97 上方',
    pullback: '跌破 92',
  },
  {
    rank: 5,
    symbol: 'TSM',
    name: 'TSMC',
    score: 76,
    trend: '稳步抬升',
    strength: 74,
    reason: '晶圆代工龙头低波动上移。',
    risk: '汇率扰动',
    quality: 'A',
    liquidity: '极高',
    trigger: '收复 184',
    pullback: '176 附近观察',
  },
];

const MARKET_OPTIONS = ['US', 'HK', 'CN'];
const THEME_OPTIONS = ['AI 半导体', '云基础设施', '高股息'];
const DEPTH_OPTIONS = ['Top 25', 'Top 50', 'Top 100'];

const densityCopy: Record<DensityMode, string> = {
  normal: '正常',
  compact: '紧凑',
  expanded: '展开',
};

function cn(...values: Array<string | false | null | undefined>): string {
  return values.filter(Boolean).join(' ');
}

function scoreTone(score: number): string {
  if (score >= 90) return 'text-emerald-200';
  if (score >= 82) return 'text-cyan-200';
  return 'text-white/78';
}

function ScoreBar({ score, emphasized = false }: { score: number; emphasized?: boolean }) {
  return (
    <div className="min-w-0">
      <div className="flex items-baseline justify-end gap-1">
        <span className={cn('font-mono font-semibold tabular-nums', emphasized ? 'text-3xl' : 'text-xl', scoreTone(score))}>{score}</span>
        <span className="text-[10px] font-semibold uppercase tracking-widest text-white/32">pts</span>
      </div>
      <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-white/[0.08]">
        <div className="h-full rounded-full bg-emerald-300/75" style={{ width: `${score}%` }} />
      </div>
    </div>
  );
}

function MetricLine({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-white/32">{label}</p>
      <div className="mt-1 truncate text-sm font-medium text-white/82">{value}</div>
    </div>
  );
}

export default function ScannerBoardPrototypePage() {
  const [density, setDensity] = useState<DensityMode>('normal');
  const [selectedSymbol, setSelectedSymbol] = useState(BOARD_CANDIDATES[0].symbol);
  const [market, setMarket] = useState(MARKET_OPTIONS[0]);
  const [theme, setTheme] = useState(THEME_OPTIONS[0]);
  const [depth, setDepth] = useState(DEPTH_OPTIONS[1]);
  const [diagnosticsOpen, setDiagnosticsOpen] = useState(false);

  const selected = useMemo(
    () => BOARD_CANDIDATES.find((candidate) => candidate.symbol === selectedSymbol) ?? BOARD_CANDIDATES[0],
    [selectedSymbol],
  );
  const isCompact = density === 'compact';
  const isExpanded = density === 'expanded';

  const boardSummary = `${market} · ${theme} · ${depth} · ${BOARD_CANDIDATES.length} 个候选`;

  return (
    <main
      data-testid="scanner-board-prototype-page"
      className="-mx-4 flex min-h-0 w-[calc(100%+2rem)] min-w-0 flex-1 flex-col overflow-hidden bg-[#020403] text-white md:-mx-6 md:w-[calc(100%+3rem)] xl:-mx-8 xl:w-[calc(100%+4rem)]"
    >
      <section className="flex min-h-0 w-full min-w-0 flex-1 flex-col px-2 pb-4 pt-2 sm:px-3 lg:px-4">
        <header className="flex min-w-0 flex-col gap-3 border-b border-white/[0.07] pb-3 xl:flex-row xl:items-end xl:justify-between">
          <div className="min-w-0">
            <div className="flex min-w-0 flex-wrap items-center gap-2 text-[10px] font-semibold uppercase tracking-widest text-white/38">
              <span>Dev Prototype</span>
              <span className="h-1 w-1 rounded-full bg-emerald-300/70" />
              <span>Scanner Trading Board</span>
            </div>
            <h1 className="mt-2 text-2xl font-semibold tracking-normal text-white sm:text-3xl">
              现代扫描交易板
            </h1>
          </div>

          <div className="grid min-w-0 grid-cols-2 gap-2 xl:flex xl:items-center">
            <div className="flex min-w-0 items-center gap-1 rounded-md bg-white/[0.045] p-1">
              {MARKET_OPTIONS.map((option) => (
                <button
                  key={option}
                  type="button"
                  className={cn(
                    'min-h-8 flex-1 rounded px-2 text-xs font-semibold text-white/48 transition hover:bg-white/[0.07] hover:text-white sm:px-3 xl:flex-none',
                    market === option && 'bg-white/[0.12] text-white shadow-sm',
                  )}
                  onClick={() => setMarket(option)}
                >
                  {option}
                </button>
              ))}
            </div>

            <div className="flex min-w-0 items-center gap-1 rounded-md bg-white/[0.045] p-1">
              {(['normal', 'compact', 'expanded'] as DensityMode[]).map((option) => (
                <button
                  key={option}
                  type="button"
                  className={cn(
                    'min-h-8 flex-1 rounded px-2 text-xs font-semibold text-white/48 transition hover:bg-white/[0.07] hover:text-white sm:px-3 xl:flex-none',
                    density === option && 'bg-emerald-300/16 text-emerald-100 shadow-sm',
                  )}
                  onClick={() => setDensity(option)}
                >
                  {densityCopy[option]}
                </button>
              ))}
            </div>
          </div>
        </header>

        <div className="mt-3 flex min-w-0 flex-col gap-3 border-b border-white/[0.06] pb-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="grid min-w-0 grid-cols-2 gap-2 xl:flex xl:items-center">
            <div className="flex min-w-0 items-center gap-2 rounded-md bg-white/[0.035] px-2 py-2">
              <SlidersHorizontal className="h-4 w-4 text-white/36" aria-hidden="true" />
              <span className="hidden shrink-0 text-[10px] font-semibold uppercase tracking-widest text-white/34 sm:inline">主题</span>
              <div className="flex min-w-0 flex-wrap gap-1">
                <button
                  type="button"
                  className="rounded px-2.5 py-1 text-xs font-medium text-white/80 transition hover:bg-white/[0.07] sm:hidden"
                  onClick={() => {
                    const nextIndex = (THEME_OPTIONS.indexOf(theme) + 1) % THEME_OPTIONS.length;
                    setTheme(THEME_OPTIONS[nextIndex]);
                  }}
                >
                  {theme}
                </button>
                {THEME_OPTIONS.map((option) => (
                  <button
                    key={option}
                    type="button"
                    className={cn(
                      'hidden rounded px-2.5 py-1 text-xs font-medium text-white/46 transition hover:bg-white/[0.07] hover:text-white sm:inline-flex',
                      theme === option && 'bg-white/[0.1] text-white',
                    )}
                    onClick={() => setTheme(option)}
                  >
                    {option}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex min-w-0 items-center gap-2 rounded-md bg-white/[0.035] px-2 py-2">
              <BarChart3 className="h-4 w-4 text-white/36" aria-hidden="true" />
              <span className="hidden shrink-0 text-[10px] font-semibold uppercase tracking-widest text-white/34 sm:inline">深度</span>
              <div className="flex min-w-0 flex-wrap gap-1">
                <button
                  type="button"
                  className="rounded px-2.5 py-1 text-xs font-medium text-white/80 transition hover:bg-white/[0.07] sm:hidden"
                  onClick={() => {
                    const nextIndex = (DEPTH_OPTIONS.indexOf(depth) + 1) % DEPTH_OPTIONS.length;
                    setDepth(DEPTH_OPTIONS[nextIndex]);
                  }}
                >
                  {depth}
                </button>
                {DEPTH_OPTIONS.map((option) => (
                  <button
                    key={option}
                    type="button"
                    className={cn(
                      'hidden rounded px-2.5 py-1 text-xs font-medium text-white/46 transition hover:bg-white/[0.07] hover:text-white sm:inline-flex',
                      depth === option && 'bg-white/[0.1] text-white',
                    )}
                    onClick={() => setDepth(option)}
                  >
                    {option}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <button
            type="button"
            className="inline-flex min-h-9 items-center justify-center gap-2 rounded-md bg-emerald-300 px-4 text-xs font-bold uppercase tracking-widest text-black transition hover:bg-emerald-200 xl:min-w-[8rem]"
          >
            <Play className="h-4 w-4" aria-hidden="true" />
            运行扫描
          </button>
        </div>

        <section className="mt-3 flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          <div className="flex min-w-0 items-center justify-between gap-3 border-b border-white/[0.06] bg-white/[0.025] px-3 py-2">
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-white/34">Ranked Board</p>
              <p className="mt-0.5 truncate text-sm text-white/66">{boardSummary}</p>
            </div>
            <div className="hidden min-w-0 items-center gap-5 text-right sm:flex">
              <MetricLine label="强度中位" value="83" />
              <MetricLine label="一号分数" value={<span className="text-emerald-200">{BOARD_CANDIDATES[0].score}</span>} />
              <MetricLine label="刷新" value="09:31" />
            </div>
          </div>

          <div className="hidden border-b border-white/[0.06] px-3 py-2 text-[10px] font-semibold uppercase tracking-widest text-white/34 xl:grid xl:grid-cols-[3.5rem_minmax(11rem,1fr)_7rem_7rem_minmax(14rem,1.35fr)_7rem_7rem_6.5rem] xl:gap-3">
            <span>Rank</span>
            <span>Asset</span>
            <span className="text-right">Score</span>
            <span>Trend</span>
            <span>Reason</span>
            <span>Risk</span>
            <span>Quality</span>
            <span className="text-right">Action</span>
          </div>

          <div className="min-h-0 min-w-0 flex-1 overflow-y-auto no-scrollbar" data-testid="scanner-board-prototype-list">
            {BOARD_CANDIDATES.map((candidate) => {
              const selectedRow = candidate.symbol === selected.symbol;
              const leader = candidate.rank === 1;
              return (
                <div
                  key={candidate.symbol}
                  data-testid={`scanner-board-row-${candidate.symbol}`}
                  className={cn(
                    'group relative grid min-w-0 grid-cols-[minmax(0,1fr)_5.75rem] gap-3 border-b border-white/[0.055] px-3 transition',
                    'hover:bg-white/[0.045] xl:grid-cols-[3.5rem_minmax(11rem,1fr)_7rem_7rem_minmax(14rem,1.35fr)_7rem_7rem_6.5rem] xl:items-center xl:gap-3',
                    isCompact ? 'py-2' : 'py-3',
                    leader && 'bg-emerald-300/[0.045]',
                    selectedRow && 'bg-cyan-300/[0.055]',
                  )}
                >
                  <div
                    className={cn(
                      'absolute bottom-2 left-0 top-2 w-[3px] rounded-r-full',
                      leader ? 'bg-emerald-300' : selectedRow ? 'bg-cyan-300/80' : 'bg-transparent',
                    )}
                  />

                  <div className="hidden min-w-0 items-center gap-2 xl:flex">
                    <span className={cn('font-mono text-sm font-semibold', leader ? 'text-emerald-200' : 'text-white/56')}>
                      #{candidate.rank}
                    </span>
                    {leader ? <Radar className="h-4 w-4 text-emerald-200" aria-hidden="true" /> : null}
                  </div>

                  <div className="min-w-0">
                    <button
                      type="button"
                      className="block min-w-0 text-left"
                      onClick={() => setSelectedSymbol(candidate.symbol)}
                      aria-pressed={selectedRow}
                    >
                      <span className="flex min-w-0 items-baseline gap-2">
                        <span className={cn('font-mono font-semibold tracking-normal', leader ? 'text-2xl text-white' : 'text-xl text-white/88')}>
                          {candidate.symbol}
                        </span>
                        <span className="truncate text-sm text-white/42">{candidate.name}</span>
                      </span>
                    </button>
                    <div className="mt-1 flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-xs text-white/48 xl:hidden">
                      <span className="font-mono text-white/58">#{candidate.rank}</span>
                      <span>{candidate.trend}</span>
                      <span>{candidate.risk}</span>
                    </div>
                    {!isCompact ? <p className="mt-1 line-clamp-1 text-sm text-white/62 xl:hidden">{candidate.reason}</p> : null}
                  </div>

                  <ScoreBar score={candidate.score} emphasized={leader} />

                  <div className="hidden min-w-0 xl:block">
                    <div className="flex items-center gap-2">
                      <TrendingUp className="h-4 w-4 text-emerald-200/80" aria-hidden="true" />
                      <span className="truncate text-sm font-medium text-white/76">{candidate.trend}</span>
                    </div>
                    {!isCompact ? (
                      <p className="mt-1 font-mono text-xs text-white/38">{candidate.strength} strength</p>
                    ) : null}
                  </div>

                  <p className="hidden min-w-0 truncate text-sm text-white/68 xl:block">{candidate.reason}</p>

                  <div className="hidden min-w-0 xl:block">
                    <p className="truncate text-sm text-amber-100/76">{candidate.risk}</p>
                  </div>

                  <div className="hidden min-w-0 xl:block">
                    <p className="font-mono text-sm font-semibold text-white/78">{candidate.quality}</p>
                    {!isCompact ? <p className="mt-1 truncate text-xs text-white/36">{candidate.liquidity}</p> : null}
                  </div>

                  <div className="col-span-2 flex min-w-0 items-center justify-between gap-2 xl:col-span-1 xl:justify-end">
                    <button
                      type="button"
                      className="inline-flex h-8 items-center justify-center rounded-md bg-white/[0.1] px-3 text-xs font-semibold text-white/86 transition hover:bg-white/[0.16]"
                    >
                      分析
                    </button>
                    <button
                      type="button"
                      className="inline-flex h-8 w-8 items-center justify-center rounded-md bg-white/[0.045] text-white/48 transition hover:bg-white/[0.1] hover:text-white"
                      aria-label={`${candidate.symbol} 更多操作`}
                      title="更多操作"
                    >
                      <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          <section
            data-testid="scanner-board-selected-panel"
            className={cn(
              'border-t border-white/[0.075] bg-black/25 px-3 transition',
              isExpanded ? 'py-4' : 'py-2',
            )}
          >
            <div className="flex min-w-0 flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
              <div className="min-w-0">
                <div className="flex min-w-0 flex-wrap items-baseline gap-2">
                  <span className="font-mono text-2xl font-semibold text-white">{selected.symbol}</span>
                  <span className="text-sm text-white/46">{selected.name}</span>
                  <span className="text-[10px] font-semibold uppercase tracking-widest text-emerald-200/70">Selected</span>
                </div>
                <p className={cn('mt-1 max-w-3xl text-sm text-white/62', isCompact && 'line-clamp-1')}>{selected.reason}</p>
              </div>
              <div className={cn('min-w-0 grid-cols-2 gap-3 sm:grid sm:grid-cols-4 xl:w-[32rem]', isCompact ? 'hidden sm:grid' : 'grid')}>
                <MetricLine label="触发" value={selected.trigger} />
                <MetricLine label="撤退" value={selected.pullback} />
                <MetricLine label="风险" value={selected.risk} />
                <MetricLine label="质量" value={selected.quality} />
              </div>
            </div>

            {isExpanded ? (
              <div className="mt-4 grid min-w-0 gap-3 xl:grid-cols-[1.2fr_0.8fr_0.8fr]">
                <div className="min-w-0 border-l border-emerald-300/45 bg-white/[0.025] px-3 py-3">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-white/34">Trade Read</p>
                  <p className="mt-2 text-sm leading-6 text-white/68">
                    一号候选用更高对比度和左侧能量线突出。交易员先读分数、趋势与触发价，再决定是否加入观察或进入详细分析。
                  </p>
                </div>
                <div className="min-w-0 bg-white/[0.025] px-3 py-3">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-white/34">Tape</p>
                  <div className="mt-2 flex items-center gap-3">
                    <Activity className="h-4 w-4 text-cyan-200/80" aria-hidden="true" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-white/76">强度 {selected.strength}</p>
                      <p className="text-xs text-white/42">趋势、成交和相对强度合并观察。</p>
                    </div>
                  </div>
                </div>
                <div className="min-w-0 bg-white/[0.025] px-3 py-3">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-white/34">Next Move</p>
                  <p className="mt-2 text-sm text-white/72">{selected.trigger}</p>
                  <p className="mt-1 text-xs text-white/42">{selected.pullback}</p>
                </div>
              </div>
            ) : null}
          </section>

          <section className="border-t border-white/[0.055] bg-white/[0.018]">
            <button
              type="button"
              className="flex w-full min-w-0 items-center justify-between gap-3 px-3 py-2 text-left text-xs text-white/48"
              onClick={() => setDiagnosticsOpen((value) => !value)}
              aria-expanded={diagnosticsOpen}
            >
              <span className="min-w-0 truncate">市场覆盖 50 · 新鲜度 09:31 · 候选质量 A- · 仅作视觉原型</span>
              <ChevronDown className={cn('h-4 w-4 shrink-0 transition', diagnosticsOpen && 'rotate-180')} aria-hidden="true" />
            </button>
            {diagnosticsOpen ? (
              <div className="grid gap-3 border-t border-white/[0.055] px-3 py-3 text-xs text-white/52 sm:grid-cols-3">
                <span>覆盖：美股大型与高流动性成长股。</span>
                <span>排序：分数优先，风险只做降噪提示。</span>
                <span>界面：原型路由，不进入主导航。</span>
              </div>
            ) : null}
          </section>
        </section>
      </section>
    </main>
  );
}
