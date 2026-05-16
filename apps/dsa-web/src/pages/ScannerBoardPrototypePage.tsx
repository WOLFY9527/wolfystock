import React, { useMemo, useState } from 'react';
import {
  Activity,
  BarChart3,
  ChevronDown,
  LineChart,
  MoreHorizontal,
  Play,
  Radar,
  Search,
  ShieldAlert,
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
  price: string;
  change: string;
  volume: string;
  sector: string;
  read: string;
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
    price: '1,064.8',
    change: '+3.8%',
    volume: '1.9x',
    sector: 'AI Compute',
    read: '趋势、资金和成交同步，仍是本轮扫描的主线资产。',
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
    price: '138.9',
    change: '+2.1%',
    volume: '1.4x',
    sector: 'Silicon IP',
    read: '强势横盘后再定价，适合等突破确认。',
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
    price: '129.7',
    change: '+1.6%',
    volume: '1.2x',
    sector: 'Memory',
    read: '周期弹性回升，但需要成交继续确认。',
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
    price: '98.3',
    change: '+0.9%',
    volume: '1.1x',
    sector: 'Data Center Power',
    read: '行业相对强度突出，追价风险略高。',
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
    price: '181.2',
    change: '+0.7%',
    volume: '0.9x',
    sector: 'Foundry',
    read: '低波动龙头，偏向稳健跟随而非爆发。',
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
        <span className="text-[10px] font-semibold uppercase text-white/32">pts</span>
      </div>
      <div className="mt-1 h-1 w-full overflow-clip rounded-full bg-white/[0.08]">
        <div className="h-full rounded-full bg-emerald-300/75" style={{ width: `${score}%` }} />
      </div>
    </div>
  );
}

function MetricLine({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <p className="text-[10px] font-semibold uppercase text-white/32">{label}</p>
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
      className="min-h-[100svh] w-full overflow-x-hidden bg-[#020403] text-white"
    >
      <section className="relative w-full min-w-0 px-3 py-4 sm:px-4 lg:px-6 xl:px-8 2xl:px-10">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-64 border-b border-emerald-300/[0.08] bg-[linear-gradient(180deg,rgba(13,27,21,0.92),rgba(2,4,3,0))]" />

        <header className="relative grid min-w-0 gap-4 border-b border-white/[0.08] pb-4 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-end">
          <div className="min-w-0 border-l-2 border-emerald-300/80 pl-3 sm:pl-4">
            <div className="flex min-w-0 flex-wrap items-center gap-2 text-[10px] font-semibold uppercase text-emerald-100/48">
              <span>Dev Prototype</span>
              <span className="h-1 w-1 rounded-full bg-emerald-300/80" />
              <span>Scanner Board</span>
            </div>
            <div className="mt-2 flex min-w-0 flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
              <div className="min-w-0">
                <h1 className="text-3xl font-semibold text-white sm:text-4xl">
                  现代扫描交易板
                </h1>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-white/54">
                  面向交易员的全宽候选面板：先读强度、触发、风险，再进入个股分析。
                </p>
              </div>
              <div className="hidden min-w-0 items-end gap-7 text-right lg:flex">
                <MetricLine label="Market Pulse" value={<span className="text-emerald-100">Risk-on</span>} />
                <MetricLine label="Breadth" value="34 / 50" />
                <MetricLine label="Last Scan" value="09:31" />
              </div>
            </div>
          </div>

          <div className="grid min-w-0 gap-2 sm:grid-cols-[auto_auto_1fr] xl:w-[42rem]">
            <div className="flex min-w-0 items-center gap-1 border border-white/[0.08] bg-white/[0.035] p-1">
              {MARKET_OPTIONS.map((option) => (
                <button
                  key={option}
                  type="button"
                  className={cn(
                    'min-h-8 flex-1 px-3 text-xs font-semibold text-white/48 transition hover:bg-white/[0.07] hover:text-white sm:flex-none',
                    market === option && 'bg-white/[0.14] text-white shadow-sm',
                  )}
                  onClick={() => setMarket(option)}
                >
                  {option}
                </button>
              ))}
            </div>

            <div className="flex min-w-0 items-center gap-1 border border-white/[0.08] bg-white/[0.035] p-1">
              {(['normal', 'compact', 'expanded'] as DensityMode[]).map((option) => (
                <button
                  key={option}
                  type="button"
                  className={cn(
                    'min-h-8 flex-1 px-2 text-xs font-semibold text-white/48 transition hover:bg-white/[0.07] hover:text-white sm:px-3',
                    density === option && 'bg-emerald-300/16 text-emerald-100 shadow-sm',
                  )}
                  onClick={() => setDensity(option)}
                >
                  {densityCopy[option]}
                </button>
              ))}
            </div>

            <button
              type="button"
              className="inline-flex min-h-10 items-center justify-center gap-2 bg-emerald-300 px-4 text-xs font-bold uppercase text-black transition hover:bg-emerald-200"
            >
              <Play className="h-4 w-4" aria-hidden="true" />
              运行扫描
            </button>
          </div>
        </header>

        <div className="relative mt-4 grid min-w-0 gap-3 border-b border-white/[0.07] pb-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
          <div className="grid min-w-0 gap-2 md:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
            <div className="flex min-w-0 items-center gap-3 border border-white/[0.07] bg-white/[0.025] px-3 py-2">
              <SlidersHorizontal className="h-4 w-4 shrink-0 text-white/40" aria-hidden="true" />
              <span className="hidden shrink-0 text-[10px] font-semibold uppercase text-white/36 sm:inline">主题</span>
              <div className="flex min-w-0 flex-wrap gap-1">
                <button
                  type="button"
                  className="px-2.5 py-1 text-xs font-medium text-white/84 transition hover:bg-white/[0.07] sm:hidden"
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
                      'hidden px-2.5 py-1 text-xs font-medium text-white/46 transition hover:bg-white/[0.07] hover:text-white sm:inline-flex',
                      theme === option && 'bg-white/[0.11] text-white',
                    )}
                    onClick={() => setTheme(option)}
                  >
                    {option}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex min-w-0 items-center gap-3 border border-white/[0.07] bg-white/[0.025] px-3 py-2">
              <Search className="h-4 w-4 shrink-0 text-white/40" aria-hidden="true" />
              <span className="hidden shrink-0 text-[10px] font-semibold uppercase text-white/36 sm:inline">深度</span>
              <div className="flex min-w-0 flex-wrap gap-1">
                <button
                  type="button"
                  className="px-2.5 py-1 text-xs font-medium text-white/84 transition hover:bg-white/[0.07] sm:hidden"
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
                      'hidden px-2.5 py-1 text-xs font-medium text-white/46 transition hover:bg-white/[0.07] hover:text-white sm:inline-flex',
                      depth === option && 'bg-white/[0.11] text-white',
                    )}
                    onClick={() => setDepth(option)}
                  >
                    {option}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="grid min-w-0 grid-cols-2 gap-2 text-xs sm:grid-cols-4 lg:w-[34rem]">
            <MetricLine label="Universe" value={depth} />
            <MetricLine label="Theme" value={theme} />
            <MetricLine label="Liquidity" value="High" />
            <MetricLine label="Mode" value={densityCopy[density]} />
          </div>
        </div>

        <section className="relative mt-4 min-w-0 border-y border-white/[0.08] bg-[#050806]/88 shadow-[0_24px_80px_rgba(0,0,0,0.32)]">
          <div className="grid min-w-0 gap-3 border-b border-white/[0.07] bg-white/[0.025] px-3 py-3 sm:px-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase text-white/34">Ranked Board</p>
              <p className="mt-1 truncate text-sm text-white/66">{boardSummary}</p>
            </div>
            <div className="grid min-w-0 grid-cols-3 gap-3 text-right sm:w-[27rem]">
              <MetricLine label="强度中位" value="83" />
              <MetricLine label="一号分数" value={<span className="text-emerald-200">{BOARD_CANDIDATES[0].score}</span>} />
              <MetricLine label="刷新" value="09:31" />
            </div>
          </div>

          <div className="hidden border-b border-white/[0.06] px-4 py-2 text-[10px] font-semibold uppercase text-white/34 xl:grid xl:grid-cols-[3.6rem_minmax(13rem,1.05fr)_7rem_7rem_minmax(16rem,1.28fr)_7rem_7rem_6.5rem] xl:gap-3 2xl:grid-cols-[4rem_minmax(17rem,1fr)_8rem_8rem_minmax(22rem,1.35fr)_8rem_8rem_7rem]">
            <span>Rank</span>
            <span>Asset</span>
            <span className="text-right">Score</span>
            <span>Trend</span>
            <span>Reason</span>
            <span>Risk</span>
            <span>Quality</span>
            <span className="text-right">Action</span>
          </div>

          <div className="min-w-0" data-testid="scanner-board-prototype-list">
            {BOARD_CANDIDATES.map((candidate) => {
              const selectedRow = candidate.symbol === selected.symbol;
              const leader = candidate.rank === 1;
              return (
                <div
                  key={candidate.symbol}
                  data-testid={`scanner-board-row-${candidate.symbol}`}
                  className={cn(
                    'group relative grid min-w-0 grid-cols-[minmax(0,1fr)_5.9rem] gap-3 border-b border-white/[0.055] px-3 transition sm:px-4',
                    'hover:bg-white/[0.045] xl:grid-cols-[3.6rem_minmax(13rem,1.05fr)_7rem_7rem_minmax(16rem,1.28fr)_7rem_7rem_6.5rem] xl:items-center xl:gap-3 2xl:grid-cols-[4rem_minmax(17rem,1fr)_8rem_8rem_minmax(22rem,1.35fr)_8rem_8rem_7rem]',
                    leader ? (isCompact ? 'py-3' : 'py-4 sm:py-5') : (isCompact ? 'py-2' : 'py-3'),
                    leader && 'bg-[linear-gradient(90deg,rgba(52,211,153,0.12),rgba(255,255,255,0.015)_48%,transparent)]',
                    selectedRow && 'bg-cyan-300/[0.055]',
                  )}
                >
                  <div
                    className={cn(
                      'absolute bottom-2 left-0 top-2 w-[3px] rounded-r-full',
                      leader ? 'bg-emerald-300 shadow-[0_0_18px_rgba(110,231,183,0.55)]' : selectedRow ? 'bg-cyan-300/80' : 'bg-transparent',
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
                        <span className={cn('font-mono font-semibold', leader ? 'text-2xl text-white' : 'text-xl text-white/88')}>
                          {candidate.symbol}
                        </span>
                        <span className="truncate text-sm text-white/42">{candidate.name}</span>
                      </span>
                    </button>
                    <div className="mt-1 flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-xs text-white/48">
                      <span className="font-mono text-white/58">#{candidate.rank}</span>
                      <span className="font-mono text-emerald-100/72">{candidate.change}</span>
                      <span>{candidate.price}</span>
                      <span>{candidate.trend}</span>
                      <span>{candidate.risk}</span>
                    </div>
                    {leader && !isCompact ? (
                      <p className="mt-2 line-clamp-2 max-w-3xl text-sm leading-5 text-emerald-50/72 xl:line-clamp-1">{candidate.read}</p>
                    ) : !isCompact ? (
                      <p className="mt-1 line-clamp-1 text-sm text-white/54 xl:hidden">{candidate.reason}</p>
                    ) : null}
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
                    {!isCompact ? <p className="mt-1 truncate text-xs text-white/36">{candidate.liquidity} · {candidate.volume}</p> : null}
                  </div>

                  <div className="col-span-2 flex min-w-0 items-center justify-between gap-2 xl:col-span-1 xl:justify-end">
                    <button
                      type="button"
                      className={cn(
                        'inline-flex h-8 items-center justify-center px-3 text-xs font-semibold transition',
                        leader ? 'bg-emerald-300 text-black hover:bg-emerald-200' : 'bg-white/[0.1] text-white/86 hover:bg-white/[0.16]',
                      )}
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
        </section>

        <section
          data-testid="scanner-board-selected-panel"
          className={cn(
            'mt-4 border-y border-white/[0.075] bg-[#050806]/78 px-3 transition sm:px-4',
            isExpanded ? 'py-5' : 'py-4',
          )}
        >
          <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(22rem,0.62fr)] xl:items-start">
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase text-white/34">Selected Candidate</p>
              <div className="mt-2 flex min-w-0 flex-wrap items-baseline gap-2">
                <span className="font-mono text-3xl font-semibold text-white">{selected.symbol}</span>
                <span className="text-sm text-white/46">{selected.name}</span>
                <span className="bg-emerald-300/12 px-2 py-1 text-[10px] font-semibold uppercase text-emerald-100/78">Rank #{selected.rank}</span>
              </div>
              <p className={cn('mt-2 max-w-5xl text-sm leading-6 text-white/64', isCompact && 'line-clamp-1')}>{selected.read}</p>
            </div>
            <div className="grid min-w-0 grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-2">
              <MetricLine label="触发" value={selected.trigger} />
              <MetricLine label="撤退" value={selected.pullback} />
              <MetricLine label="风险" value={selected.risk} />
              <MetricLine label="质量" value={selected.quality} />
            </div>
          </div>

          <div className={cn('mt-4 grid min-w-0 gap-3 xl:grid-cols-[1.25fr_0.9fr_0.85fr]', isCompact && 'hidden sm:grid')}>
            <div className="min-w-0 border-l-2 border-emerald-300/55 bg-white/[0.022] px-3 py-3">
              <p className="text-[10px] font-semibold uppercase text-white/34">Trade Read</p>
              <p className="mt-2 text-sm leading-6 text-white/68">
                一号候选用分数、趋势与成交强度建立优先级，后续候选保持紧凑可比。当前选择先看触发价，再确认风险是否可接受。
              </p>
            </div>
            <div className="min-w-0 border-l border-white/[0.07] bg-white/[0.018] px-3 py-3">
              <p className="text-[10px] font-semibold uppercase text-white/34">Tape</p>
              <div className="mt-2 flex items-center gap-3">
                <Activity className="h-4 w-4 shrink-0 text-cyan-200/80" aria-hidden="true" />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-white/76">强度 {selected.strength} · 量能 {selected.volume}</p>
                  <p className="text-xs text-white/42">{selected.sector}</p>
                </div>
              </div>
            </div>
            <div className="min-w-0 border-l border-white/[0.07] bg-white/[0.018] px-3 py-3">
              <p className="text-[10px] font-semibold uppercase text-white/34">Next Move</p>
              <p className="mt-2 text-sm text-white/72">{selected.trigger}</p>
              <p className="mt-1 text-xs text-white/42">{selected.pullback}</p>
            </div>
          </div>
        </section>

        <section className="mt-4 grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(18rem,0.42fr)]">
          <div className="min-w-0 border-y border-white/[0.07] bg-white/[0.018]">
            <div className="grid min-w-0 gap-3 px-3 py-3 sm:px-4 md:grid-cols-3">
              <div className="min-w-0">
                <p className="flex items-center gap-2 text-[10px] font-semibold uppercase text-white/34">
                  <LineChart className="h-4 w-4 text-emerald-200/70" aria-hidden="true" />
                  Market Context
                </p>
                <p className="mt-2 text-sm leading-6 text-white/66">AI 计算链仍领先，指数宽度改善但换手集中在前排资产。</p>
              </div>
              <div className="min-w-0">
                <p className="flex items-center gap-2 text-[10px] font-semibold uppercase text-white/34">
                  <ShieldAlert className="h-4 w-4 text-amber-200/70" aria-hidden="true" />
                  Risk Desk
                </p>
                <p className="mt-2 text-sm leading-6 text-white/66">财报与估值敏感度偏高，追突破需要更严格的撤退线。</p>
              </div>
              <div className="min-w-0">
                <p className="flex items-center gap-2 text-[10px] font-semibold uppercase text-white/34">
                  <BarChart3 className="h-4 w-4 text-cyan-200/70" aria-hidden="true" />
                  Rejected
                </p>
                <p className="mt-2 text-sm leading-6 text-white/66">12 个候选因量能不足或触发价太远暂缓，保留观察不进入主榜。</p>
              </div>
            </div>
          </div>

          <div className="min-w-0 border-y border-white/[0.07] bg-white/[0.018]">
            <button
              type="button"
              className="flex w-full min-w-0 items-center justify-between gap-3 px-3 py-3 text-left text-xs text-white/48 sm:px-4"
              onClick={() => setDiagnosticsOpen((value) => !value)}
              aria-expanded={diagnosticsOpen}
            >
              <span className="min-w-0 truncate">覆盖 50 · 新鲜度 09:31 · 候选质量 A-</span>
              <ChevronDown className={cn('h-4 w-4 shrink-0 transition', diagnosticsOpen && 'rotate-180')} aria-hidden="true" />
            </button>
            {diagnosticsOpen ? (
              <div className="grid gap-3 border-t border-white/[0.055] px-3 py-3 text-xs leading-5 text-white/52 sm:px-4">
                <span>覆盖：美股大型与高流动性成长股。</span>
                <span>排序：分数优先，风险只做降噪提示。</span>
                <span>界面：原型路由，不进入主导航。</span>
              </div>
            ) : null}
          </div>
        </section>

        <section className="mt-4 min-w-0 border-y border-white/[0.07] bg-[#050806]/64">
          <div className="grid min-w-0 gap-3 px-3 py-3 sm:px-4 lg:grid-cols-[auto_minmax(0,1fr)] lg:items-center">
            <p className="text-[10px] font-semibold uppercase text-white/34">Related Watch</p>
            <div className="grid min-w-0 gap-2 sm:grid-cols-3">
              {BOARD_CANDIDATES.slice(1, 4).map((candidate) => (
                <button
                  key={candidate.symbol}
                  type="button"
                  className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] gap-3 border-l border-white/[0.08] bg-white/[0.018] px-3 py-3 text-left transition hover:bg-white/[0.045]"
                  onClick={() => setSelectedSymbol(candidate.symbol)}
                >
                  <span className="min-w-0">
                    <span className="block truncate font-mono text-sm font-semibold text-white/84">{candidate.symbol}</span>
                    <span className="mt-1 block truncate text-xs text-white/42">{candidate.reason}</span>
                  </span>
                  <span className="font-mono text-sm font-semibold text-emerald-100/76">{candidate.score}</span>
                </button>
              ))}
            </div>
          </div>
        </section>

        <section className="mt-4 min-w-0 border-y border-white/[0.07] bg-white/[0.014]">
          <div className="grid min-w-0 gap-3 px-3 py-3 sm:px-4 xl:grid-cols-[12rem_minmax(0,1fr)]">
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase text-white/34">Reject Queue</p>
              <p className="mt-2 text-sm leading-6 text-white/54">保留可回看但不干扰主榜，证明页面使用文档级自然滚动。</p>
            </div>
            <div className="grid min-w-0 gap-2 md:grid-cols-2 xl:grid-cols-4">
              {[
                ['AMD', '强度回升但触发价偏远', 'Watch'],
                ['AVGO', '质量高，短线成交不足', 'Cooldown'],
                ['SMCI', '波动过大，等待收敛', 'Risk'],
                ['PLTR', '趋势仍强，估值噪声高', 'Observe'],
              ].map(([symbol, note, status]) => (
                <div key={symbol} className="min-w-0 border-l border-white/[0.08] bg-[#050806]/70 px-3 py-3">
                  <div className="flex min-w-0 items-baseline justify-between gap-3">
                    <span className="font-mono text-base font-semibold text-white/82">{symbol}</span>
                    <span className="text-[10px] font-semibold uppercase text-white/34">{status}</span>
                  </div>
                  <p className="mt-2 line-clamp-2 text-xs leading-5 text-white/52">{note}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      </section>
    </main>
  );
}
