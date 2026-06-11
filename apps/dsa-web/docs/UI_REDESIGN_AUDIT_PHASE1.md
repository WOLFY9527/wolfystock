# WolfyStock 前端 UI 重构审计报告 — 第一阶段

**审计日期**: 2026-06-10
**审计人**: ArchitectUX Agent
**当前 commit**: `c77042db fix(quota): remove raw reservation metadata`
**分支**: `claude/ui-redesign-v1`

---

## 1. 测试账号验证

| 账号 | 角色 | 状态 |
|------|------|------|
| `testuser` / `TestUser2024!` | 普通用户 | ✅ 已创建并验证 |
| `admin` / `852258` | 管理员 | ✅ 可登录 |

### 权限对比验证

| API 端点 | testuser | admin |
|----------|----------|-------|
| `/api/v1/auth/me` | ✅ 完整用户信息 | ✅ 完整管理员信息 |
| `/api/v1/scanner/status` | ❌ `admin_required` | ✅ 完整状态 |
| `/api/v1/scanner/themes` | ✅ 主题列表 | ✅ 主题列表 |
| `/api/v1/watchlist/items` | ✅ 自选列表 | ✅ 自选列表 |
| `/api/v1/portfolio/snapshot` | ✅ 持仓快照 | ✅ 持仓快照 |
| `/api/v1/portfolio/risk` | ✅ 风险分析 | ✅ 风险分析 |
| `/api/v1/quant/duckdb/health` | ❌ `admin_required` | ✅ 数据库健康 |
| `/api/v1/usage/summary` | ❌ `admin_required` | ✅ 用量统计 |

**结论**: 后端 RBAC 已到位，testuser 的 `canReadProviders: false` 等权限正确执行。

---

## 2. 主要 UI 问题清单（按严重程度）

### 🔴 严重 (P0)

#### 2.1 CSS 架构失控 — 17,006 行单文件
`index.css` 包含 **1,432 处** `html[data-theme='spacex']` 选择器。多层冗余覆盖导致：
- 同一属性可能被覆盖 3-5 次
- 改动任何 token 有不可预测的级联影响
- 无法区分"有意覆盖"和"冗余覆盖"

#### 2.2 双 Token 体系并行冲突
```
--wolfy-canvas / --wolfy-surface-console / --wolfy-text-primary  (Wolfy 体系)
--bg-page-hsl / --text-primary-hsl / --accent-primary-hsl          (HSL 体系)
```
两套体系被不同组件引用，无统一事实来源。组件开发者需猜测用哪套。

#### 2.3 双图表库并存 — ECharts 5 + Recharts 3
`package.json` 同时依赖 `echarts@5` 和 `recharts@3`。导致：
- 图表视觉风格不统一
- ECharts vendor chunk: 526 KB gzip ~175 KB
- Recharts 散落在页面 chunk 中

#### 2.4 无用户主题偏好支持
`index.html` 硬编码 `data-theme="spacex"`。`ThemeProvider.tsx` 仅支持 `RootThemeName = 'spacex'`。用户无法选择 light/dark/system 主题。

#### 2.5 导航 9 项等权重平铺
所有导航项（Home, Scanner, Portfolio, Market Overview, Liquidity, Rotation Radar, Watchlist, Backtest, Options Lab）以相同视觉权重平铺。用户无法快速区分核心功能和高级工具。

#### 2.6 GuestHomePage 无专属 Landing 体验
`GuestHomePage.tsx` 直接渲染 `<HomeBentoDashboardPage isGuest />`。游客和已登录用户看到相同 dashboard 结构，无产品价值主张传达，无 CTA。

### 🟡 中等 (P1)

#### 2.7 Market Overview `UsBreadthTruthStrip` 对消费者可见
`MarketOverviewWorkbench.tsx:2490` 的 `insightStrip={<UsBreadthTruthStrip panel={panels.usBreadth} />}` **无管理员守卫**。向所有用户展示 source/freshness/coverage 标签（REAL/MIXED/FALLBACK/REGIME）。虽有 `MARKET_OVERVIEW_CONSUMER_UNSAFE_PATTERN` 正则过滤，但过滤的是文本内容而非 DOM 渲染本身。

#### 2.8 Scanner 诊断面板对所有用户可见
`UserScannerPage.tsx:4400-4440` 的 "数据说明" AdvancedDisclosure 对所有用户展示：
- 评估/入选/淘汰统计
- rejection buckets（淘汰原因分布）
- ScannerDiagnosticsPanel（每个候选标的的诊断详情）

无 `isAdminMode` 守卫。普通用户看到"为什么没入选"的后端诊断细节。

#### 2.9 Liquidity Monitor 直接使用 coverageDiagnostics
`LiquidityMonitorPage.tsx:590-630` 直接访问 `indicator.coverageDiagnostics` 对象，包含：
- `configuredProviderAvailable`
- `realSourceAvailable`
- `sourceAuthorityRouteRejected`
- `missingInputs`
- `scoreExclusionReason`, `capReason`, `degradationReason`

这些字段用于判断指标可见性和阻塞原因，但字段名直接暴露 provider/source authority 概念。

#### 2.10 Primitive 层三层重叠
```
LinearPrimitives.tsx (591行)
  └─ TerminalPrimitives.tsx (306行) — 注释 "Legacy-compatible names"
       └─ DenseWorkbenchPrimitives.tsx (167行)
```
三个 Primitive 文件互相引用，命名前缀混用，页面代码同时从三个文件导入同类组件。

#### 2.11 移动端断点缺少系统化覆盖
仅少数页面使用 `lg:` 断点，缺少 `md:` 和 `sm:` 系统性覆盖。390px 宽度下布局行为未经测试。

### 🟢 低 (P2)

#### 2.12 Home Dashboard 首屏缺乏焦点
`HomeBentoDashboardPage.tsx` 单文件将: market briefing, candlestick chart, evidence coverage/packet/research readiness strips, history panel, deep report drawer 全部渲染在首屏。用户进入后无主视觉锚点。

#### 2.13 CSS 无 name-spacing 分层
所有 CSS 类名（shell-*, wolfy-*, terminal-*）散落在单一 `index.css` 中，无 `@layer` 组织。

#### 2.14 Vite chunks 过大
`index.js`: 510 KB (gzip 168 KB), `vendor-echarts.js`: 526 KB (gzip 175 KB)

---

## 3. 页面审计详情

### 3.1 GuestHomePage (`GuestHomePage.tsx`)
- **问题**: 直接复用 `HomeBentoDashboardPage isGuest`，完全无 landing 体验
- **缺少**: 产品价值主张、特性介绍、CTA 按钮
- **建议**: 新建独立 Landing Page，强调市场总览/扫描/持仓/回测四大能力

### 3.2 LoginPage (`LoginPage.tsx`)
- **状态**: 结构完整，有 hero section + copy 区分 setup/create/login 三种模式
- **问题**: 无主题切换，纯 dark theme
- **建议**: 保留结构，视觉 polish 即可

### 3.3 HomeBentoDashboardPage (`HomeBentoDashboardPage.tsx`)
- **状态**: 功能丰富但信息混杂
- **导入的诊断组件**: ConsumerEvidenceCoverageStrip, ConsumerEvidencePacketStrip, ConsumerResearchReadinessStrip
- **建议**: 首屏精简为 market briefing + 快速入口 + top 3 分析摘要

### 3.4 MarketOverviewPage (`MarketOverviewPage.tsx`)
- **workbench**: 3007 行超大组件
- **诊断守卫**: `showAdminDiagnostics={isAdminMode && canReadProviders}` ✅ 正确
- **问题**: `UsBreadthTruthStrip` 对所有用户可见 🔴
- **建议**: insightStrip 移至 `showAdminDiagnostics` 守卫内

### 3.5 UserScannerPage (`UserScannerPage.tsx`)
- **问题**: scanner-diagnostics-disclosure 对所有用户可见 🔴
- **建议**: 诊断详情加 `isAdminMode` 守卫，普通用户只看到入选理由

### 3.6 WatchlistPage (`WatchlistPage.tsx`)
- **状态**: 功能完整
- **建议**: 增加 table 主视图选项，详情进抽屉

### 3.7 PortfolioPage (`PortfolioPage.tsx`)
- **状态**: 功能完整，使用 PortfolioTrustStrip 展示信任指标
- **建议**: 持仓风险/集中度信息前置

### 3.8 BacktestPage (`BacktestPage.tsx`)
- **状态**: 功能边界清晰，无 admin diagnostic 暴露 ✅
- **建议**: 区分"标准评估"vs"规则回测"入口

### 3.9 LiquidityMonitorPage (`LiquidityMonitorPage.tsx`)
- **问题**: coverageDiagnostics 直接用于页面逻辑 🔴
- **建议**: 提取 proxy 函数，前端不直接读取 provider 字段

### 3.10 MarketRotationRadarPage — 无诊断暴露 ✅
### 3.11 OptionsLabPage — 无诊断暴露 ✅

---

## 4. Shell / 布局分析

### 当前 Shell 结构
```
Shell.tsx
├── SidebarNav.tsx (header 模式: top bar nav)
└── Outlet (内容区, max-w-[1880px])
    └── ConsumerWorkspaceShell
        └── ConsumerWorkspaceScope + ConsumerWorkspacePageShell
```

### 关键问题
- **9 项导航等权重**: 无法区分核心/高级
- **无主题切换按钮**: 硬编码 dark theme
- **header nav 模式**: 和 sidebar 模式通过 CSS 切换，无用户可配置项
- **Admin 区域隔离**: admin nav items 通过 `isAdminOpsRoute()` 正确隔离 ✅

### 建议导航重组
```
核心 (3):
  Home / Scanner / Portfolio

分析工具 (4):
  Market Overview / Watchlist / Backtest

高级 (3):
  Liquidity / Rotation / Options → 合并为 "Markets" 下拉
```

---

## 5. 组件清单

### 已有 Layout 组件
| 组件 | 文件 | 行数 |
|------|------|------|
| Shell | `Shell.tsx` | ~700 |
| SidebarNav | `SidebarNav.tsx` | ~400 |
| ConsumerWorkspaceShell | `ConsumerWorkspaceShell.tsx` | ~80 |
| TerminalPageHeading | `TerminalPrimitives.tsx` | ~306 |
| DenseWorkbenchPrimitives | `DenseWorkbenchPrimitives.tsx` | ~167 |

### 缺少的通用组件
- `PageHeader` (统一 TerminalPageHeading + WorkspacePageHeader)
- `SummaryBar` (2-4 关键指标横向条)
- `DiagnosticsDisclosure` (统一诊断折叠组件，默认对普通用户隐藏)
- `EmptyState / LoadingState / ErrorState` (统一空态/加载态/错误态)
- `ThemeToggle` (light/dark/system)

### 已有 Visual 组件
| 组件 | 文件 |
|------|------|
| Button | `common/Button.tsx` |
| Input | `common/Input.tsx` |
| Select | `common/Select.tsx` |
| Checkbox | `common/Checkbox.tsx` |
| Drawer | `common/Drawer.tsx` |
| PillBadge | `common/PillBadge.tsx` |
| SegmentedControl | `common/SegmentedControl.tsx` |
| SectionShell | `common/SectionShell.tsx` |
| ConfirmDialog | `common/ConfirmDialog.tsx` |
| ApiErrorAlert | `common/ApiErrorAlert.tsx` |

---

## 6. 验证命令与结果

```
npm run lint      → ✅ 通过，0 警告
npm run typecheck → ✅ 通过，0 错误
npm run build     → ✅ 通过 (15.53s)
```

本地服务 `http://127.0.0.1:8000` 响应 200 OK。

---

## 7. 第二阶段实施入口（按依赖顺序）

### Step 0: CSS Token 梳理（不入第二阶段代码，先标记）
- 在 `index.css` 顶部加注释标记权威 `--wolfy-*` tokens
- 标记冗余的 `html[data-theme='spacex']` 覆盖
- 耗时: 1-2 小时，零风险

### Step 1: Shell 导航分层（优先）
- 修改 `SidebarNav.tsx`，将 9 项导航重组为分层结构
- 不改路由，不删功能
- 有 Playwright 测试覆盖，可安全改

### Step 2: PageHeader 统一
- 合并 `TerminalPageHeading` + `WorkspacePageHeader` → 统一 `PageHeader`
- 更新所有页面引用（typecheck 全量验证）

### Step 3: Truth Strip 消费者可见性修复
- `UsBreadthTruthStrip` 移至 `showAdminDiagnostics` 守卫
- Scanner 诊断面板加 `isAdminMode` 守卫

### Step 4: Theme Toggle 基础实现
- 扩展 `ThemeProvider.tsx` 支持 `RootThemeName = 'spacex-dark' | 'spacex-light'`
- 添加 preboot script 读 `localStorage.getItem('theme')`
- 在 Shell header 加切换按钮

### Step 5: 页面逐页重构
按 P0 → P1 优先级:
1. Home Dashboard 首屏精简
2. Market Overview 布局重组
3. Scanner 视图优化
4. Watchlist 列表/table 视图
5. Portfolio 摘要前置
6. Backtest 入口区分
7. Liquidity/Rotation/Options cockpit 视图
8. Guest Landing
9. Login/Register polish
10. Admin 页面整理

---

## 8. 明确边界声明

**本次审计未修改以下任何内容**:
- ✅ 后端 API / schema / 任何 Python 文件
- ✅ 数据库、storage、provider、auth、RBAC
- ✅ quota、backtest engine、task runtime
- ✅ package-lock.json、deployment config
- ✅ 任何路由逻辑
- ✅ API schema / contract

**未修改前端代码**: 本审计为只读分析，所有发现通过代码审查 + API 测试获得。

---

## 9. 剩余 UI Debt

| 债务项 | 影响 | 优先级 |
|--------|------|--------|
| 17K 行单一 CSS 文件 | 维护困难 | P0 |
| ECharts + Recharts 双库 | Bundle 体积 + 风格不一 | P1 |
| Primitive 三层重叠 | 代码理解成本 | P1 |
| 移动端断点缺失 | 390px 体验未知 | P1 |
| CSS 无 @layer 组织 | 覆盖顺序不确定 | P2 |
| Vite chunks >500KB | 首屏加载 | P2 |

---

## 10. 后续建议

1. **在改任何页面之前，先做 CSS 分层**: 将 `index.css` 拆为 `tokens.css` / `layout.css` / `components.css` / `pages/*.css`
2. **建立 component 命名规范**: 统一使用一种 primitive 层（建议用 `LinearPrimitives` 作为权威来源，其他标记 deprecated）
3. **修复 consumer diagnostic exposure 再改布局**: 保证安全问题优先处理
4. **引入 visual regression testing**: 已有 Playwright，可加 `toHaveScreenshot()` 断言
