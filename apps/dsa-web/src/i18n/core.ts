export type UiLanguage = 'zh' | 'en';

export const UI_LANGUAGE_STORAGE_KEY = 'dsa-ui-language';

const RESOURCES = {
  zh: {
    nav: {
      home: '首页',
      scanner: '扫描器',
      portfolio: '持仓',
      marketOverview: '市场总览',
      watchlist: '观察列表',
      backtest: '回测',
      optionsLab: '期权实验室',
      settings: '设置',
      signIn: '登录',
      terminal: '工作区',
      independentConsole: '控制台',
      notifications: '通知',
      marketProviders: '数据源运维',
      providerCircuits: '熔断诊断',
      userGovernance: '用户治理',
      costObservability: '成本观测',
      logout: '退出',
      logoutTitle: '退出登录',
      logoutMessage: '确认退出当前登录状态吗？退出后需要重新输入密码。',
      logoutConfirm: '确认退出',
      logoutCancel: '取消',
      theme: '主题',
      language: '语言',
    },
    marketOverviewPage: {
      header: {
        eyebrow: '跨市场监控台',
        title: '大市全景监控',
        description: '把核心指数、波动率压力、情绪温度、资金流向与宏观流动性压缩到同一监控视角。',
        refresh: '同步最新行情',
        lastUpdated: '最后更新: {timestamp}',
        pending: '等待同步',
      },
      refreshCard: '刷新 {title}',
      status: {
        success: '同步完成',
        failure: '同步失败',
        loading: '同步中',
      },
      loading: '正在拉取最新市场数据...',
      temperature: {
        eyebrow: '市场温度计',
        title: '市场温度总览',
        overall: '综合市场温度',
        usRiskAppetite: '美股风险偏好',
        cnMoneyEffect: 'A股赚钱效应',
        macroPressure: '全球宏观压力',
        liquidity: '流动性环境',
        veryCold: '极冷',
        cold: '偏冷',
        neutral: '中性',
        warm: '偏暖',
        overheated: '过热',
      },
      briefing: {
        eyebrow: '规则化解读',
        title: '今日市场解读',
      },
      categories: {
        all: '全部',
        us: '美股',
        cn: 'A股/港股',
        macro: '全球宏观',
        crypto: '加密货币',
      },
      cards: {
        indexTrends: {
          eyebrow: '全球指数扫描',
          title: '全球核心指数走势',
          description: '跨市场指数压缩为高密度扫描视图，优先暴露方向、斜率与相对强弱。',
          source: '数据驱动: YFINANCE',
        },
        volatility: {
          eyebrow: '风险压力',
          title: '波动率与风险压力',
          primaryLabel: '波动率中枢',
          primaryMeta: 'VIX 实时脉搏',
          left: '平静',
          right: '警戒',
          source: '数据驱动: CBOE',
        },
        crypto: {
          eyebrow: '数字资产脉搏',
          title: '加密货币行情',
          description: '跟踪 BTC、ETH、BNB 的现价、24H 涨跌和 7D 走势，失败时回退到最近一次有效快照。',
          source: '数据驱动: BINANCE',
        },
        sentiment: {
          eyebrow: '市场情绪',
          title: '情绪与资金面',
          primaryLabel: '贪婪与恐慌指数',
          gaugeLeft: '防守',
          gaugeRight: '进攻',
          source: '数据驱动: CNN / ALTERNATIVE',
          labels: {
            putcall: '24H 变化',
            bullbear: '7D 变化',
            aaii: '数据源状态',
          },
          states: {
            neutral: '中性',
            greed: '贪婪',
            riskOn: '偏进攻',
            balanced: '均衡',
            defensive: '偏防守',
            fear: '恐慌',
          },
        },
        fundsFlow: {
          eyebrow: '流动性监测',
          title: 'ETF 资金流向',
          description: '用 ETF、机构与行业代理流追踪增配还是撤退，观察风险偏好的真资金表达。',
          source: '数据驱动: YFINANCE',
        },
        macro: {
          eyebrow: '利率与流动性',
          title: '宏观经济与流动性',
          description: '把收益率曲线、美元、黄金、原油、通胀与信用利差收敛到同一宏观风险框架。',
          source: '数据驱动: YFINANCE / FRED',
        },
        cnIndices: {
          eyebrow: '中国资产',
          title: 'A股与港股指数',
          description: '上证、深成指、创业板、科创、宽基、恒指、恒生科技与富时A50期货的核心脉搏。',
          source: '数据来源: 备用 / 公开',
        },
        cnBreadth: {
          eyebrow: '赚钱效应',
          title: '市场宽度与赚钱效应',
          description: '跟踪上涨家数、下跌家数、涨跌停、新高新低和上涨比例，判断指数背后的真实参与度。',
          source: '数据来源: 备用 / 公开',
        },
        cnFlows: {
          eyebrow: '跨境与杠杆资金',
          title: '资金流向',
          description: '北向资金、南向资金、主力资金、ETF 净申购与融资余额变化压缩到一张资金温度卡。',
          source: '数据来源: 备用 / 公开',
        },
        sectorRotation: {
          eyebrow: '主题强弱',
          title: '行业与主题强弱',
          description: '按相对强弱排名展示 AI / 算力、半导体、机器人、低空经济、港股科技等方向。',
          source: '数据来源: 备用 / 公开',
        },
        rates: {
          eyebrow: '利率曲线',
          title: '利率与债券市场',
          description: '美债 2Y/10Y/30Y、利差、中国10年国债、DR007、SHIBOR 与 LPR 的利率环境。',
          source: '数据来源: 备用 / 公开',
        },
        fxCommodities: {
          eyebrow: '美元、人民币与商品',
          title: '商品与外汇',
          description: 'DXY、USD/CNH、主要外汇、黄金、原油与铜，观察全球风险资产的外部压力。',
          source: '数据来源: 备用 / 公开',
        },
        futures: {
          eyebrow: '盘前风向',
          title: '期货与盘前风向',
          description: '纳指、标普、道指、罗素、富时A50、恒指与日经期货的跨市场开盘前方向。',
          source: '数据来源',
        },
        cnShortSentiment: {
          eyebrow: '短线接力',
          title: 'A股短线情绪',
          score: '短线情绪评分',
          source: '数据来源',
          metrics: {
            limitUpCount: '涨停家数',
            limitDownCount: '跌停家数',
            failedLimitUpRate: '炸板率',
            maxConsecutiveLimitUps: '连板高度',
            yesterdayLimitUpPerformance: '昨日涨停表现',
            firstBoardCount: '首板',
            secondBoardCount: '二板',
            highBoardCount: '高位连板',
            twentyCmLimitUpCount: '20cm 涨停',
          },
        },
      },
      footer: {
        lastRefresh: '最近更新: {timestamp}',
        pending: '等待同步',
        refreshingSnapshot: '正在刷新快照',
      },
      direction: {
        increasing: '升温',
        decreasing: '缓和',
        neutral: '中性',
      },
    },
    shell: {
      openMenu: '打开导航菜单',
      drawerTitle: '导航菜单',
      workspaceShell: 'Workspace Shell',
      workspaceShellBody: '统一导航与内容对齐。全模块共享一致的产品节奏。',
      workspaceShellFoot: '导航、界面与内容 Rail 共用统一桌面壳层宽度。',
      noRail: '当前页面无附加 Rail，沿用统一壳层与移动端抽屉行为。',
      retry: '重试',
      archiveEyebrow: '研究档案',
      archiveTitle: '分析档案',
      archiveDesc: '已完成分析记录。默认轻量阅读态；批量操作需切换管理模式。',
      archiveShort: '档案',
    },
    adminNav: {
      eyebrow: '管理工作区',
      title: '管理员导航',
      description: '将系统控制面与日志入口保持在同一个独立管理层，避免重新混入个人设置。',
      logs: '管理员日志',
    },
    preview: {
      eyebrow: '预览',
      shellTitle: '报告界面',
      shellNote: '预览壳层',
      shellAction: '报告界面',
      shellBody: '复用生产环境 SpaceX 结构语言的开发态预览壳层，用于校验报告层级与响应式行为。',
      workspaceEyebrow: 'WolfyStock 预览工作区',
      reportTitle: '报告预览',
      reportDesc: '响应式预览页，校验桌面与移动端的层级、结构和主题表现。',
      fullDrawerTitle: '完整报告抽屉预览',
      fullDrawerDesc: '校验完整报告抽屉在各端的阅读宽度、层级节奏与可读性。',
      fullModeTitle: '完整报告展示模式',
      fullModeBody: '打开完整报告抽屉，检查长文档在统一容器策略下的阅读体验。',
      openChinese: '打开中文完整报告',
      openEnglish: '打开英文完整报告',
    },
    previewReport: {
      documentTitle: '报告预览 - WolfyStock',
      eyebrow: 'WolfyStock 预览工作区',
      title: '报告预览',
      description: '响应式预览页，校验桌面与移动端的层级、结构和主题表现。',
    },
    previewFullReport: {
      documentTitle: '完整报告抽屉预览 - WolfyStock',
      eyebrow: 'WolfyStock 预览工作区',
      title: '完整报告抽屉预览',
      description: '校验完整报告抽屉在各端的阅读宽度、层级节奏与可读性。',
      fullModeTitle: '完整报告展示模式',
      fullModeBody: '打开完整报告抽屉，检查长文档在统一容器策略下的阅读体验。',
      openChinese: '打开中文完整报告',
      openEnglish: '打开英文完整报告',
      stockName: '英伟达',
      markdown: `# NVIDIA（NVDA）完整研究报告

## 一、结论摘要
当前建议维持“等待回踩确认后分批试仓”的执行框架。核心判断来自价格结构仍偏多，但短线动量与上方压力位尚未完成再平衡。

## 二、执行层（可操作）
### 2.1 当前动作
- 优先观察回踩 MA20 附近是否出现承接。
- 若成交量放大但价格未失守关键支撑，可考虑首笔试仓。
- 若价格快速跌破支撑并放量，暂停执行，进入防守模式。

### 2.2 新开仓计划
1. 理想买入区间：120-121。
2. 次优买入点：118。
3. 止损位：115。
4. 目标区间：132-138。

## 三、证据层（行情与结构）
### 3.1 市场结构
当前 MA5/10/20/60 结构仍支持中期趋势框架，但短线斜率边际转弱，说明交易层面仍需等待回踩确认而非追高。

### 3.2 催化与风险
- 利好：数据中心需求回暖、AI 订单延续。
- 风险：估值偏高、前高压力仍在。
- 观察：若新增公司级催化不足，短线更依赖技术结构确认。

### 3.3 数据证据表
| 字段 | 数值 | 口径 |
| --- | --- | --- |
| Analysis Price | 125.30 | Intraday snapshot |
| Change % | 1.87% | Session vs Prev Close |
| MA20 | 120.99 | FMP API |
| RSI14 | 56.78 | FMP API |
| VWAP | NA（字段待接入） | Coverage gap |
| 盘后成交额 | NA（会话不适用） | Session rule |

## 四、覆盖与审计
### 4.1 缺失字段说明
- VWAP：NA（字段待接入）
- Beta：NA（接口未返回）
- 盘后成交额：NA（会话不适用）

### 4.2 覆盖审计备注
> 该报告保留所有缺失字段与原因归类，用于后续 API 接入与数据源排期，不作为删除内容的依据。

## 五、附录
### 5.1 方法说明
标准技术指标优先采用 API 原始值；冲突字段按统一口径重算并保留备注。

### 5.2 风险提示
本报告用于研究讨论，不构成投资建议。`,
    },
    notFound: {
      documentTitle: '页面未找到 - WolfyStock',
      eyebrow: '页面状态',
      title: '页面未找到',
      body: '当前地址不存在或已经迁移。返回首页后，可以继续进入研究、持仓或回测区域。',
      cta: '返回首页',
    },
    language: {
      toggle: '切换语言',
      zh: '中文',
      en: 'EN',
      current: '当前语言',
    },
    theme: {
      label: '切换主题',
      menu: '主题模式',
      spacex: 'Workspace Shell',
      spacexDesc: '已锁定为单一、受控的极简研究工作区壳层。',
      terminal: 'Paper',
      terminalDesc: '明亮主界面：白色画布、克制边框与清晰层级。',
      cyber: 'Dusk',
      cyberDesc: '深色主界面：保留一致版式与交互规则。',
      hacker: 'Midnight',
      hackerDesc: '高对比深色界面：遵循统一卡片与排版节奏。',
    },
    common: {
      processing: '处理中...',
      show: '显示',
      hide: '隐藏',
      showContent: '显示内容',
      hideContent: '隐藏内容',
      selectPlaceholder: '请选择',
      confirm: '确认',
      cancel: '取消',
      closeDrawer: '关闭抽屉',
      confirmationRequired: '需要确认',
      confirmAction: '确认操作',
      stockSearchPlaceholder: '输入股票代码或名称',
      apiError: {
        close: '关闭',
        details: '查看详情',
        guidance: {
          localConnection1: '确认后端服务已启动且 Web 前端可访问 API。',
          localConnection2: '检查网络连通性或反向代理配置。',
          localConnection3: '刷新重试；或重新登录以刷新会话。',
          ssl1: '如果是 webhook / HTTPS 地址，请检查证书链、主机名和受信任 CA 是否匹配。',
          ssl2: '自签名证书、过期证书或中间代理改写 TLS 证书链都可能导致校验失败。',
          ssl3: '若仍失败，请在服务器或代理侧先确认该 URL 的 TLS 握手可以通过。',
          upstream1: '外部模型或数据源不可用，请稍后重试。',
          upstream2: '检查代理、DNS、API 配置或服务配额。',
          analysisConflict: '同一标的已有任务运行，请等待完成后重试。',
        },
      },
    },
    home: {
      documentTitle: '每日选股分析 - WolfyStock',
      eyebrow: '统一研究工作区',
      title: '股票研究工作区',
      subtitle: '高度结构化的分析流。聚焦结论、计划与报告，消除无关噪音。',
      commandLabel: '输入研究标的',
      openArchive: '打开档案',
      historyTitle: '历史记录',
      placeholder: '输入股票代码或名称，如 600519、贵州茅台、AAPL',
      analyze: '分析',
      analyzing: '分析中',
      followAi: '追问 AI',
      viewFullReport: '完整研究报告',
      latestPendingTitle: '最新报告待手动打开',
      latestPendingBody: '报告已就绪。使用下方动作重新打开最新报告。',
      viewLatestReport: '查看最新报告',
      loadingReport: '加载报告中...',
      loadingTitle: '正在同步报告上下文',
      loadingBody: '结论、计划与图表按顺序载入工作区。非阻塞式渲染。',
      emptyEyebrow: '等待新的研究任务',
      emptyTitle: '开始分析',
      emptyBody: '输入代码启动研究，或从档案加载。内容依序展开：总览、行情、技术、基本面、财报、计划。',
      deleteTitle: '删除历史记录',
      deleteSingle: '确认删除这条历史记录吗？删除后将不可恢复。',
      deleteMultiple: '确认删除选中的 {count} 条历史记录吗？删除后将不可恢复。',
      deleteConfirm: '确认删除',
      deleting: '删除中...',
      deleteAll: '全部删除',
      deleteOne: '删除记录',
      visibleCount: '当前可见记录',
      cancel: '取消',
      toastTitle: '最新报告已打开',
      toastBody: '已自动切换至最新报告并高亮记录。',
      currentViewing: '当前查看：{code}',
      mobileHistory: '历史记录',
      inputRequired: '请输入股票代码',
      invalidInput: '请输入有效的股票代码或股票名称',
      duplicateTask: '股票 {stockCode} 正在分析中，请等待完成',
      progressEyebrow: '分析进度',
      progressOverall: '总进度',
      progressMessage: 'Analysis in progress',
      progressStage: '阶段',
      progressPending: '待开始',
      progressRunning: '进行中',
      progressCompleted: '已完成',
      progressFailed: '失败',
      analysisProgress: 'Analysis in progress',
      finalAnalysisEyebrow: '分析结果',
      finalAnalysisTitle: '最终分析',
      analysisScore: '评分',
      analysisTarget: '目标位',
      analysisStopLoss: '止损位',
      progressStateCopy: {
        pending: '等待进入该阶段',
        running: '该阶段正在处理中',
        completed: '该阶段已完成',
        failed: '该阶段已中断',
      },
      progressBadge: {
        pending: 'Pending',
        running: 'Running',
        completed: 'Completed',
        failed: 'Failed',
      },
      decision: {
        eyebrow: '决策摘要',
        action: '动作',
        trend: '趋势',
        score: '评分',
        status: '状态',
        progress: '进度',
        updated: '最近更新',
        state: '状态',
        awaitingTarget: '等待研究目标',
        pendingAnalysis: '待分析',
        ready: '待开始',
        liveDraftBody: '实时研究草稿组装中，将在此收敛为最终结构化报告。',
      },
    },
    guestHome: {
      documentTitle: '游客预览 - WolfyStock',
      eyebrow: '游客预览',
      title: '游客预览模式',
      description: '先看一份简版分析，再决定是否登录继续。游客预览不会保存历史，也不会创建个人数据。',
      previewSubtitle: '受限价值',
      inputLabel: '输入标的',
      inputPlaceholder: '输入股票代码或名称，如 600519、贵州茅台、AAPL',
      submit: '生成简版判断',
      submitting: '生成中...',
      helper: '游客可以先查看一份简版分析；完整报告、后续交流、回测、持仓和历史记录需要登录后使用。',
      previewTitle: '即时分析预览',
      previewNote: '该结果仅用于游客预览，不写入历史记录，也不开放后续交流。',
      previewDrawerAction: '打开预览说明',
      decisionPanelEyebrow: 'WOLFY AI 决断',
      decisionSnapshot: '决策快照',
      unlockTitle: '登录后继续完整功能',
      unlockSubtitle: '继续深入',
      unlockBody: '登录后，你的分析结果、交流记录、持仓、回测和历史都会保存在你自己的账户下。',
      strategyPanelTitle: '执行策略',
      strategyPositionLabel: '仓位节奏',
      strategyPositionBody: '建仓区间、止损位和目标位会在登录后变成可执行建议，因为那时系统才能把你的分析历史和风险决策稳定绑定到你自己的账户。',
      techPanelTitle: '技术形态',
      techSignalMacd: '零轴上方金叉',
      techSignalMa: 'MA20 / MA60 扩张',
      techSignalVolume: '回踩缩量，突破放量',
      fundamentalsPanelTitle: '基本面画像',
      fundamentalMetricGrowth: '收入增速',
      fundamentalMetricCashFlow: '自由现金流',
      fundamentalMetricMargin: '毛利率',
      frostedLockTitle: '解锁高阶策略与深度指标',
      frostedLockBody: '登录后获取建仓点位、止损建议和完整基本面上下文，并把每次查询都保存在你自己的历史里。',
      frostedLockCta: '立即登录 / 注册',
      drawerSummary: '游客模式保留左侧决策面板可用，但高阶模块会在真实账户接管前保持毛玻璃锁定。',
      drawerBulletDecision: '左侧 Wolfy AI 决断面板保持可交互，游客可以输入股票代码并立即看到核心评分。',
      drawerBulletLock: '执行策略、技术形态和基本面画像保持可见但模糊，所有点击都会被上层遮罩拦截。',
      drawerBulletRedirect: '受保护路由仍会在任何个人化或可保存页面加载前，把游客打回这个转化漏斗。',
      decision: '动作建议',
      trend: '趋势判断',
      score: '情绪分数',
      entry: '理想介入',
      stopLoss: '止损位',
      target: '目标位',
      noValue: '待生成',
      signIn: '登录解锁',
      createAccount: '创建账户',
      unlockPrimary: '登录后继续完整使用',
      unlockSecondary: '创建账户后，完整报告、问股、观察名单、回测与持仓都会按你的身份保存。',
      lockedLabel: '已锁定',
      cards: {
        fullReports: {
          title: '完整分析报告',
          body: '登录后查看完整报告层级、证据链、图表与执行计划。',
        },
        followUp: {
          title: '后续交流',
          body: '从已保存报告继续交流，并把会话记录保存在你自己的账户下。',
        },
        portfolio: {
          title: '持仓',
          body: '将交易、仓位、资金流水与风险分析绑定到你的个人账户。',
        },
        backtests: {
          title: '回测',
          body: '运行确定性回测与规则回测，并将结果保存到你自己的账户中。',
        },
        history: {
          title: '历史与复盘',
          body: '查看你自己的分析历史、扫描记录与后续复盘，不会和其他账户混在一起。',
          cta: '查看扫描器预告',
        },
      },
      limits: {
        title: '游客限制',
        subtitle: '游客权限保持受限',
        accountIsolation: '游客预览不会创建账户记录，也不会解锁跨页面保存的功能。',
        persistence: '持仓、扫描器、回测、问股与历史等持久化流程仍然严格绑定到已认证用户身份。',
        admin: '系统配置、调度、通知通道与管理员日志仍然保留在游客页面之外。',
      },
    },
    app: {
      loading: '加载中',
      loadingBrand: '正在加载 WolfyStock...',
      retry: '重试',
      workspaceEyebrow: '研究工作区',
    },
  },
  en: {
    nav: {
      home: 'Home',
      scanner: 'Scanner',
      portfolio: 'Holdings',
      marketOverview: 'Market',
      watchlist: 'Watchlist',
      backtest: 'Backtest',
      optionsLab: 'Options Lab',
      settings: 'Settings',
      signIn: 'Sign in',
      terminal: 'Workspace',
      independentConsole: 'Console',
      notifications: 'Notifications',
      marketProviders: 'Provider Ops',
      providerCircuits: 'Circuit Diagnostics',
      userGovernance: 'User Governance',
      costObservability: 'Cost Observability',
      logout: 'Log out',
      logoutTitle: 'Log out',
      logoutMessage: 'Sign out of the current session? You will need to enter the password again.',
      logoutConfirm: 'Log out',
      logoutCancel: 'Cancel',
      theme: 'Theme',
      language: 'Language',
    },
    marketOverviewPage: {
      header: {
        eyebrow: 'Cross-Market Monitor',
        title: 'Cross-Market Monitor',
        description: 'A single monitoring surface for core indices, volatility pressure, sentiment, fund flow, and macro liquidity.',
        refresh: 'Sync latest market',
        lastUpdated: 'Last update: {timestamp}',
        pending: 'Pending sync',
      },
      refreshCard: 'Refresh {title}',
      status: {
        success: 'Synced',
        failure: 'Sync failed',
        loading: 'Syncing',
      },
      loading: 'Pulling the latest market data...',
      temperature: {
        eyebrow: 'Market thermometer',
        title: 'Market Temperature',
        overall: 'Overall Temperature',
        usRiskAppetite: 'US Risk Appetite',
        cnMoneyEffect: 'China Money Effect',
        macroPressure: 'Macro Pressure',
        liquidity: 'Liquidity',
        veryCold: 'Very Cold',
        cold: 'Cold',
        neutral: 'Neutral',
        warm: 'Warm',
        overheated: 'Overheated',
      },
      briefing: {
        eyebrow: 'Rule-based readout',
        title: 'Market Briefing',
      },
      categories: {
        all: 'All',
        us: 'US',
        cn: 'China/HK',
        macro: 'Global Macro',
        crypto: 'Crypto',
      },
      cards: {
        indexTrends: {
          eyebrow: 'Global index scan',
          title: 'Index Trends',
          description: 'Cross-market tape compressed into a high-density scan for direction, slope, and relative strength.',
          source: 'DATA SOURCE: YAHOO FINANCE',
        },
        volatility: {
          eyebrow: 'Risk pressure',
          title: 'Volatility',
          primaryLabel: 'Volatility index',
          primaryMeta: 'VIX live pulse',
          left: 'Complacent',
          right: 'Panic',
          source: 'DATA SOURCE: CBOE',
        },
        crypto: {
          eyebrow: 'Digital asset pulse',
          title: 'Crypto Prices',
          description: 'Track BTC, ETH, and BNB spot price, 24H change, and 7D tape with stale-data fallback on refresh failures.',
          source: 'DATA SOURCE: BINANCE',
        },
        sentiment: {
          eyebrow: 'Market sentiment',
          title: 'Sentiment & positioning',
          primaryLabel: 'Fear & greed index',
          gaugeLeft: 'Fear',
          gaugeRight: 'Greed',
          source: 'DATA SOURCE: CNN / ALTERNATIVE',
          labels: {
            putcall: '24H delta',
            bullbear: '7D delta',
            aaii: 'Provider state',
          },
          states: {
            neutral: 'Neutral',
            greed: 'Greed',
            riskOn: 'Risk-on',
            balanced: 'Balanced',
            defensive: 'Defensive',
            fear: 'Fear',
          },
        },
        fundsFlow: {
          eyebrow: 'Liquidity tape',
          title: 'Funds Flow',
          description: 'ETF, institutional, and industry flow proxies show whether capital is adding risk or leaving.',
          source: 'DATA SOURCE: YAHOO FINANCE',
        },
        macro: {
          eyebrow: 'Rates + liquidity',
          title: 'Macro Indicators',
          description: 'Yield curve, DXY, gold, oil, inflation, and credit spread context in one macro frame.',
          source: 'DATA SOURCE: YAHOO FINANCE / FRED',
        },
        cnIndices: {
          eyebrow: 'China assets',
          title: 'China & Hong Kong Indices',
          description: 'Shanghai, Shenzhen, ChiNext, STAR 50, broad CN indices, Hang Seng, HSTECH, and FTSE A50 futures.',
          source: 'DATA SOURCE: FALLBACK / PUBLIC',
        },
        cnBreadth: {
          eyebrow: 'Market breadth',
          title: 'Breadth & Participation',
          description: 'Advancers, decliners, limit-up/down, new highs/lows, and participation score behind the index move.',
          source: 'DATA SOURCE: FALLBACK / PUBLIC',
        },
        cnFlows: {
          eyebrow: 'Cross-border capital',
          title: 'Capital Flow',
          description: 'Northbound, southbound, main-board active flow, ETF creation, and margin balance changes.',
          source: 'DATA SOURCE: FALLBACK / PUBLIC',
        },
        sectorRotation: {
          eyebrow: 'Theme strength',
          title: 'Sector & Theme Rotation',
          description: 'Relative strength ranking across AI compute, semis, robotics, low-altitude economy, HK tech, and cyclicals.',
          source: 'DATA SOURCE: FALLBACK / PUBLIC',
        },
        rates: {
          eyebrow: 'Yield curves',
          title: 'Rates & Bonds',
          description: 'US 2Y/10Y/30Y, curve spreads, China 10Y CGB, DR007, SHIBOR, and LPR liquidity context.',
          source: 'DATA SOURCE: FALLBACK / PUBLIC',
        },
        fxCommodities: {
          eyebrow: 'Dollar, CNH, commodities',
          title: 'FX & Commodities',
          description: 'DXY, USD/CNH, major FX, gold, crude, and copper as external pressure gauges for risk assets.',
          source: 'DATA SOURCE: FALLBACK / PUBLIC',
        },
        futures: {
          eyebrow: 'Premarket tape',
          title: 'Futures & Premarket',
          description: 'Nasdaq, S&P 500, Dow, Russell, FTSE A50, Hang Seng, and Nikkei futures before the cash session.',
          source: 'DATA SOURCE',
        },
        cnShortSentiment: {
          eyebrow: 'Short-term tape',
          title: 'China Short-term Sentiment',
          score: 'Sentiment score',
          source: 'DATA SOURCE',
          metrics: {
            limitUpCount: 'Limit-ups',
            limitDownCount: 'Limit-downs',
            failedLimitUpRate: 'Failed Limit-up Rate',
            maxConsecutiveLimitUps: 'Consecutive Limit-up Height',
            yesterdayLimitUpPerformance: 'Previous Limit-up Performance',
            firstBoardCount: 'First Boards',
            secondBoardCount: 'Second Boards',
            highBoardCount: 'High Boards',
            twentyCmLimitUpCount: '20cm Limit-ups',
          },
        },
      },
      footer: {
        lastRefresh: 'Last refresh: {timestamp}',
        pending: 'Pending sync',
        refreshingSnapshot: 'Refreshing snapshot',
      },
      direction: {
        increasing: 'Rising',
        decreasing: 'Easing',
        neutral: 'Neutral',
      },
    },
    shell: {
      openMenu: 'Open navigation',
      drawerTitle: 'Navigation',
      workspaceShell: 'Workspace Shell',
      workspaceShellBody: 'Unified navigation and content alignment. Consistent rhythm across all core modules.',
      workspaceShellFoot: 'Shared shell width for navigation, interface modes, and content rails.',
      noRail: 'No extra rail active. Retains unified shell width and mobile behavior.',
      retry: 'Retry',
      archiveEyebrow: 'Research archive',
      archiveTitle: 'Analysis archive',
      archiveDesc: 'Completed analyses. Lightweight reading mode by default; enter manage mode for bulk actions.',
      archiveShort: 'Archive',
    },
    adminNav: {
      eyebrow: 'Admin Workspace',
      title: 'Admin navigation',
      description: 'Keep the control plane and logs on the same dedicated admin layer instead of drifting back into personal settings.',
      logs: 'Admin logs',
    },
    preview: {
      eyebrow: 'Preview',
      shellTitle: 'Report Surface',
      shellNote: 'Preview Shell',
      shellAction: 'Report Surface',
      shellBody: 'Development shell reuses production SpaceX structure to verify report and responsive behavior.',
      workspaceEyebrow: 'WolfyStock Preview Workspace',
      reportTitle: 'Report preview',
      reportDesc: 'Responsive preview page for validating hierarchy, chart structure, and theme behavior.',
      fullDrawerTitle: 'Full report drawer preview',
      fullDrawerDesc: 'Validate full-report drawer readability, rhythm, and audit-section clarity.',
      fullModeTitle: 'Full report presentation mode',
      fullModeBody: 'Open full report drawer to verify document presentation in unified container strategy.',
      openChinese: 'Open Chinese full report',
      openEnglish: 'Open English full report',
    },
    previewReport: {
      documentTitle: 'Report Preview - WolfyStock',
      eyebrow: 'WolfyStock Preview Workspace',
      title: 'Report preview',
      description: 'Responsive preview page for validating hierarchy, chart structure, and theme behavior.',
    },
    previewFullReport: {
      documentTitle: 'Full Report Drawer Preview - WolfyStock',
      eyebrow: 'WolfyStock Preview Workspace',
      title: 'Full report drawer preview',
      description: 'Validate full-report drawer readability, rhythm, and audit-section clarity.',
      fullModeTitle: 'Full report presentation mode',
      fullModeBody: 'Open full report drawer to verify document presentation in unified container strategy.',
      openChinese: 'Open Chinese full report',
      openEnglish: 'Open English full report',
      stockName: 'NVIDIA',
      markdown: `# NVIDIA (NVDA) Full Research Memo

## 1. Executive Summary
The current stance remains "wait for pullback confirmation, then scale in gradually." The trend structure is still constructive, while short-term momentum and overhead resistance are not fully resolved.

## 2. Execution Layer
### 2.1 Immediate Actions
- Watch for demand response near MA20.
- Consider the first probe position only if support holds with healthy volume.
- If support breaks with expanding volume, pause execution and switch to defense.

### 2.2 New Position Plan
1. Ideal entry range: 120-121.
2. Secondary entry: 118.
3. Stop loss: 115.
4. Target zone: 132-138.

## 3. Evidence Layer
### 3.1 Structure
MA5/10/20/60 still supports the medium-term trend framework, but short-term slope is flattening. This supports a pullback-first approach rather than chasing strength.

### 3.2 Catalysts and Risks
- Bullish: data-center demand recovery, sustained AI orders.
- Risks: elevated valuation, overhead resistance near previous highs.
- Watch item: in the absence of new company-level catalysts, setup quality depends more on technical confirmation.

### 3.3 Data Table
| Field | Value | Basis |
| --- | --- | --- |
| Analysis Price | 125.30 | Intraday snapshot |
| Change % | 1.87% | Session vs Prev Close |
| MA20 | 120.99 | FMP API |
| RSI14 | 56.78 | FMP API |
| VWAP | NA (not integrated yet) | Coverage gap |
| After-hours turnover | NA (not applicable in this session) | Session rule |

## 4. Coverage and Audit
### 4.1 Missing Fields
- VWAP: NA (not integrated yet)
- Beta: NA (integrated but unavailable)
- After-hours turnover: NA (not applicable in this session)

### 4.2 Audit Notes
> Missing fields and classified reasons are intentionally preserved for API integration planning and traceability.

## 5. Appendix
### 5.1 Method Notes
Technical indicators prioritize original API values. Conflicting fields are normalized with explicit basis notes.

### 5.2 Risk Notice
This memo is for research discussion and does not constitute investment advice.`,
    },
    notFound: {
      documentTitle: 'Page Not Found - WolfyStock',
      eyebrow: 'Page State',
      title: 'Page not found',
      body: 'This address does not exist or has moved. Go back home to continue into research, portfolio, or backtest areas.',
      cta: 'Back to home',
    },
    language: {
      toggle: 'Switch language',
      zh: '中文',
      en: 'EN',
      current: 'Current language',
    },
    theme: {
      label: 'Switch theme',
      menu: 'Theme presets',
      spacex: 'Workspace Shell',
      spacexDesc: 'Locked to one controlled minimal research-workspace shell.',
      terminal: 'Paper',
      terminalDesc: 'Bright workspace: restrained white canvas, soft borders, clean hierarchy.',
      cyber: 'Dusk',
      cyberDesc: 'Dark workspace: consistent layout rhythm, surfaces, and rules.',
      hacker: 'Midnight',
      hackerDesc: 'High-contrast dark mode: unified component language and rhythm.',
    },
    common: {
      processing: 'Processing...',
      show: 'Show',
      hide: 'Hide',
      showContent: 'Show content',
      hideContent: 'Hide content',
      selectPlaceholder: 'Select an option',
      confirm: 'Confirm',
      cancel: 'Cancel',
      closeDrawer: 'Close drawer',
      confirmationRequired: 'Confirmation required',
      confirmAction: 'Confirm action',
      stockSearchPlaceholder: 'Enter a stock code or company name',
      apiError: {
        close: 'Close',
        details: 'View details',
        guidance: {
          localConnection1: 'Verify backend service is active and API endpoint is reachable.',
          localConnection2: 'Verify network connectivity and reverse proxy settings.',
          localConnection3: 'Refresh and retry. Relogin if session expired.',
          ssl1: 'For webhook / HTTPS targets, verify the certificate chain, hostname, and trusted CA.',
          ssl2: 'Self-signed, expired, or proxy-rewritten TLS certificates can all trigger verification failures.',
          ssl3: 'If it still fails, confirm the TLS handshake succeeds from the server or proxy that reaches the URL.',
          upstream1: 'Upstream models/providers unavailable. Retry later.',
          upstream2: 'Check proxy, DNS, API key, or provider quota.',
          analysisConflict: 'Target analysis already active. Await completion.',
        },
      },
    },
    home: {
      documentTitle: 'Daily Stock Analysis - WolfyStock',
      eyebrow: 'Unified research workspace',
      title: 'Stock Research Workspace',
      subtitle: 'Structured analysis workflow. Focused conclusions, execution plans, and full reports.',
      commandLabel: 'Research target',
      openArchive: 'Open archive',
      historyTitle: 'History',
      placeholder: 'Enter a stock code or company name, for example 600519, Kweichow Moutai, AAPL',
      analyze: 'Analyze',
      analyzing: 'Analyzing',
      followAi: 'Ask AI',
      viewFullReport: 'Full Research Report',
      latestPendingTitle: 'Latest report needs a manual open',
      latestPendingBody: 'Report ready. History sync delayed. Reopen newest report below.',
      viewLatestReport: 'View latest report',
      loadingReport: 'Loading report...',
      loadingTitle: 'Syncing report context',
      loadingBody: 'Layers load sequentially into the workspace. Non-blocking interface.',
      emptyEyebrow: 'Awaiting a new research run',
      emptyTitle: 'Start an analysis',
      emptyBody: 'Enter ticker to start analysis, or load from archive. Expands: Overview, Market, Technicals, Fundamentals, Earnings, Plan.',
      deleteTitle: 'Delete history',
      deleteSingle: 'Delete this history record? This action cannot be undone.',
      deleteMultiple: 'Delete the selected {count} history records? This action cannot be undone.',
      deleteConfirm: 'Delete',
      deleting: 'Deleting...',
      deleteAll: 'Delete all',
      deleteOne: 'Delete record',
      visibleCount: 'Visible records',
      cancel: 'Cancel',
      toastTitle: 'Latest report opened',
      toastBody: 'Latest report loaded and highlighted in history.',
      currentViewing: 'Viewing: {code}',
      mobileHistory: 'History',
      inputRequired: 'Enter a stock code',
      invalidInput: 'Enter a valid stock code or stock name',
      duplicateTask: '{stockCode} is already being analyzed. Please wait for the current run to finish.',
      progressEyebrow: 'Analysis Progress',
      progressOverall: 'Overall Progress',
      progressMessage: 'Analysis in progress',
      progressStage: 'Stage',
      progressPending: 'Pending',
      progressRunning: 'Running',
      progressCompleted: 'Completed',
      progressFailed: 'Failed',
      analysisProgress: 'Analysis in progress',
      finalAnalysisEyebrow: 'Analysis Result',
      finalAnalysisTitle: 'Final Analysis',
      analysisScore: 'Score',
      analysisTarget: 'Target',
      analysisStopLoss: 'Stop Loss',
      progressStateCopy: {
        pending: 'Waiting for this stage to start.',
        running: 'This stage is currently running.',
        completed: 'This stage has completed.',
        failed: 'This stage stopped before completion.',
      },
      progressBadge: {
        pending: 'Pending',
        running: 'Running',
        completed: 'Completed',
        failed: 'Failed',
      },
      decision: {
        eyebrow: 'Decision Brief',
        action: 'Action',
        trend: 'Trend',
        score: 'Score',
        status: 'Status',
        progress: 'Progress',
        updated: 'Updated',
        state: 'State',
        awaitingTarget: 'Awaiting target',
        pendingAnalysis: 'Pending analysis',
        ready: 'Ready',
        liveDraftBody: 'Building a live draft. It will resolve into the final structured report.',
      },
    },
    guestHome: {
      documentTitle: 'Guest Preview - WolfyStock',
      eyebrow: 'Guest Preview',
      title: 'Guest Preview Mode',
      description: 'Start with a lightweight analysis snapshot, then sign in if you want to keep going. Guest previews are never saved to an account.',
      previewSubtitle: 'Limited Value',
      inputLabel: 'Enter a symbol',
      inputPlaceholder: 'Enter a stock code or company name, for example 600519, Kweichow Moutai, AAPL',
      submit: 'Generate snapshot',
      submitting: 'Generating...',
      helper: 'Guests can generate one lightweight analysis snapshot. Full reports, follow-up chat, backtests, portfolio tools, and saved history unlock after sign-in.',
      previewTitle: 'Instant Analysis Snapshot',
      previewNote: 'This preview is intentionally limited. It is not saved and does not unlock follow-up chat.',
      previewDrawerAction: 'Open preview guide',
      decisionPanelEyebrow: 'WOLFY AI DECISION',
      decisionSnapshot: 'Decision Snapshot',
      unlockTitle: 'Sign in for the full app',
      unlockSubtitle: 'Next Step',
      unlockBody: 'Once you sign in, your analysis, chat history, portfolio, backtests, and saved history stay attached to your own account.',
      strategyPanelTitle: 'Execution Strategy',
      strategyPositionLabel: 'Position Plan',
      strategyPositionBody: 'Entry, stop-loss, and target levels become actionable only after sign-in, when the app can keep your analysis history and risk decisions under your own account.',
      techPanelTitle: 'Technical Structure',
      techSignalMacd: 'Bullish crossover above zero line',
      techSignalMa: 'MA20 / MA60 expanding',
      techSignalVolume: 'Quiet pullback, strong breakout volume',
      fundamentalsPanelTitle: 'Fundamental Profile',
      fundamentalMetricGrowth: 'Revenue Growth',
      fundamentalMetricCashFlow: 'Free Cash Flow',
      fundamentalMetricMargin: 'Gross Margin',
      frostedLockTitle: 'Unlock advanced strategy and deep indicators',
      frostedLockBody: 'Sign in to reveal entry zones, stop-loss guidance, and full fundamental context, then keep every query attached to your own history.',
      frostedLockCta: 'Sign in / Register now',
      drawerSummary: 'Guest mode keeps the decision panel live, but advanced modules stay behind a frosted lock until the session belongs to a real account.',
      drawerBulletDecision: 'The left-side Wolfy AI decision panel stays interactive, so guests can test a ticker and see the core score immediately.',
      drawerBulletLock: 'Execution strategy, technical structure, and fundamentals remain visible but blurred, with all clicks intercepted by the paywall overlay.',
      drawerBulletRedirect: 'Protected routes still bounce guests back into this funnel before any personal or saved surfaces load.',
      decision: 'Action',
      trend: 'Trend',
      score: 'Sentiment',
      entry: 'Entry',
      stopLoss: 'Stop loss',
      target: 'Target',
      noValue: 'Waiting',
      signIn: 'Sign in',
      createAccount: 'Create account',
      unlockPrimary: 'Unlock saved reports, chat, portfolio, and backtests',
      unlockSecondary: 'Create an account to save reports, chats, watchlists, backtests, and portfolio data under your own name.',
      lockedLabel: 'Locked',
      cards: {
        fullReports: {
          title: 'Full Analysis Reports',
          body: 'Unlock full reports, supporting evidence, charts, and a detailed action plan.',
        },
        followUp: {
          title: 'Follow-up Chat',
          body: 'Continue from a saved report with follow-up chat and session memory under your own account.',
        },
        portfolio: {
          title: 'Portfolio',
          body: 'Connect trades, positions, cash events, and portfolio risk to your own account.',
        },
        backtests: {
          title: 'Backtests',
          body: 'Run deterministic and rule backtests, then save the results to your own account.',
        },
        history: {
          title: 'Saved History and Reviews',
          body: 'Review your own analysis history, scanner runs, and follow-up decisions without mixing with other accounts.',
          cta: 'Preview scanner',
        },
      },
      limits: {
        title: 'Guest limits',
        subtitle: 'Guest access stays limited',
        accountIsolation: 'Guest previews do not create an account record and do not unlock saved cross-page features.',
        persistence: 'Portfolio, scanner, backtest, chat, and saved history remain tied to a signed-in account.',
        admin: 'System settings, schedules, notification channels, and admin logs remain outside guest pages.',
      },
    },
    app: {
      loading: 'Loading',
      loadingBrand: 'Loading WolfyStock...',
      retry: 'Retry',
      workspaceEyebrow: 'Research Workspace',
    },
  },
} as const;

export function normalizeUiLanguage(value?: string | null): UiLanguage {
  return value === 'en' ? 'en' : 'zh';
}

function getByPath(target: Record<string, unknown>, path: string): string | undefined {
  return path.split('.').reduce<unknown>((current, key) => {
    if (current && typeof current === 'object') {
      return (current as Record<string, unknown>)[key];
    }
    return undefined;
  }, target) as string | undefined;
}

function interpolate(template: string, vars?: Record<string, string | number | undefined>): string {
  if (!vars) {
    return template;
  }
  return template.replace(/\{(\w+)\}/g, (_, key: string) => String(vars[key] ?? ''));
}

export function getStoredUiLanguage(): UiLanguage {
  if (typeof window === 'undefined') {
    return 'zh';
  }
  return normalizeUiLanguage(window.localStorage.getItem(UI_LANGUAGE_STORAGE_KEY));
}

export function setStoredUiLanguage(language: UiLanguage): void {
  if (typeof window === 'undefined') {
    return;
  }
  window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, language);
}

export function translate(
  language: UiLanguage,
  key: string,
  vars?: Record<string, string | number | undefined>,
): string {
  const localized = getByPath(RESOURCES[language] as unknown as Record<string, unknown>, key)
    ?? getByPath(RESOURCES.zh as unknown as Record<string, unknown>, key)
    ?? key;
  return interpolate(localized, vars);
}

export function translateForCurrentLanguage(
  key: string,
  vars?: Record<string, string | number | undefined>,
): string {
  return translate(getStoredUiLanguage(), key, vars);
}
