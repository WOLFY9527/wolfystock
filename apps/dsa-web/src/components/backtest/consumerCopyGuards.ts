type BacktestLanguage = 'zh' | 'en';
type LocalizedReplacement = [RegExp, { zh: string; en: string }];

const RAW_DIAGNOSTIC_REPLACEMENTS: LocalizedReplacement[] = [
  [/professionalReady/gi, { zh: '研究状态', en: 'research status' }],
  [/sourceAuthorityAllowed/gi, { zh: '来源上下文已隐藏', en: 'source context hidden' }],
  [/scoreContributionAllowed/gi, { zh: '评分上下文已隐藏', en: 'score context hidden' }],
  [/reasonCode/gi, { zh: '状态说明', en: 'status note' }],
  [/diagnosticOnly/gi, { zh: '仅用于复核回放', en: 'review replay only' }],
  [/decisionGrade/gi, { zh: '复核状态', en: 'review status' }],
  [/runtimePathsExecuted/gi, { zh: '运行路径摘要已隐藏', en: 'runtime path summary hidden' }],
  [/blockingDimensionIds/gi, { zh: '缺失前置条件摘要已隐藏', en: 'missing prerequisite summary hidden' }],
  [/missingReasonCodes/gi, { zh: '缺失前置条件说明已隐藏', en: 'missing prerequisite notes hidden' }],
  [/provider[_\s-]*calls[_\s-]*executed/gi, { zh: '外部数据调用状态已隐藏', en: 'external data call status hidden' }],
  [/engine[_\s-]*math[_\s-]*changed/gi, { zh: '计算状态已隐藏', en: 'calculation status hidden' }],
  [/optimizer[_\s-]*executed/gi, { zh: '参数优化状态已隐藏', en: 'optimizer status hidden' }],
  [/parameter[_\s-]*sweep[_\s-]*executed/gi, { zh: '参数复核状态已隐藏', en: 'parameter review status hidden' }],
  [/strategy[_\s-]*parameters[_\s-]*mutated/gi, { zh: '策略参数状态已隐藏', en: 'strategy parameter status hidden' }],
  [/provider[_\s-]*timeout/gi, { zh: '数据暂不可用', en: 'data temporarily unavailable' }],
  [/fallback[_\s-]*static/gi, { zh: '近期可用数据', en: 'recent available data' }],
  [/stored[_\s-]*execution[_\s-]*trace/gi, { zh: '已存储复核材料', en: 'stored review evidence' }],
  [/trace\s+json/gi, { zh: '复核材料', en: 'review evidence' }],
  [/helper\s+metadata/gi, { zh: '复核上下文', en: 'review context' }],
  [/raw\s+json/gi, { zh: '复核详情', en: 'review details' }],
  [/\bprovider\b/gi, { zh: '数据来源细节', en: 'data source detail' }],
  [/\bbackend\b/gi, { zh: '系统细节', en: 'system detail' }],
  [/\bcache\b/gi, { zh: '新鲜度细节', en: 'freshness detail' }],
  [/\braw\b/gi, { zh: '复核', en: 'review' }],
];

const EN_ADVICE_REPLACEMENTS: Array<[RegExp, string]> = [
  [/execution-ready|trade-ready|professional-ready|institutional-ready/gi, 'research prototype'],
  [/\brunnable\b/gi, 'research-ready'],
  [/buy[\s-]?and[\s-]?hold/gi, 'same-instrument holding benchmark'],
  [/target price/gi, 'upper observation zone'],
  [/position sizing/gi, 'size assumption'],
  [/trailing[\s-]?stop/gi, 'moving risk threshold'],
  [/stop[\s-]?loss/gi, 'risk threshold'],
  [/take[\s-]?profit/gi, 'return threshold'],
  [/\bbuy\b/gi, 'observe trigger'],
  [/\bbuys\b/gi, 'marks observe triggers'],
  [/\bbuying\b/gi, 'observing triggers'],
  [/\bsell\b/gi, 'observe release'],
  [/\bsells\b/gi, 'marks observe releases'],
  [/\bselling\b/gi, 'observing releases'],
  [/\bentry\b/gi, 'observe trigger'],
  [/\bentries\b/gi, 'observe triggers'],
  [/\bentering\b/gi, 'observing trigger'],
  [/\bexit\b/gi, 'observe release'],
  [/\bexits\b/gi, 'marks observe releases'],
  [/\bexiting\b/gi, 'observing release'],
  [/\breduce\b/gi, 'lower observation exposure'],
  [/\breduces\b/gi, 'lowers observation exposure'],
  [/\breducing\b/gi, 'lowering observation exposure'],
  [/\btrade\b/gi, 'simulation event'],
  [/\btrading\b/gi, 'research simulation'],
];

const ZH_ADVICE_REPLACEMENTS: Array<[RegExp, string]> = [
  [/execution-ready|trade-ready|professional-ready|institutional-ready/gi, '研究原型'],
  [/\brunnable\b/gi, '研究模拟'],
  [/buy[\s-]?and[\s-]?hold/gi, '同标的持有基准'],
  [/target price/gi, '上方观察区'],
  [/position sizing/gi, '规模假设'],
  [/trailing[\s-]?stop/gi, '移动风险阈值'],
  [/stop[\s-]?loss/gi, '风险阈值'],
  [/take[\s-]?profit/gi, '收益阈值'],
  [/买入并持有|买入持有/g, '同标的持有基准'],
  [/可执行/g, '研究模拟'],
  [/仓位建议/g, '规模假设'],
  [/目标价/g, '上方观察区'],
  [/止损/g, '风险阈值'],
  [/止盈/g, '收益阈值'],
  [/买入/g, '观察触发'],
  [/卖出/g, '观察解除'],
  [/建仓/g, '建立观察记录'],
  [/加仓/g, '增加观察记录'],
  [/减仓/g, '降低观察记录'],
  [/调仓/g, '调整观察记录'],
  [/入场/g, '观察触发'],
  [/离场/g, '观察解除'],
  [/退出/g, '观察解除'],
  [/交易型/g, '研究型'],
];

function applyReplacements(text: string, replacements: Array<[RegExp, string]>): string {
  return replacements.reduce((current, [pattern, replacement]) => current.replace(pattern, replacement), text);
}

function applyLocalizedReplacements(text: string, replacements: LocalizedReplacement[], language: BacktestLanguage): string {
  return replacements.reduce((current, [pattern, replacement]) => current.replace(pattern, replacement[language]), text);
}

export function sanitizeBacktestConsumerCopy(value: unknown, language: BacktestLanguage = 'zh'): string {
  const source = value == null ? '' : String(value);
  const trimmed = source.trim();
  if (!trimmed) return '';

  const withoutDiagnostics = applyLocalizedReplacements(trimmed, RAW_DIAGNOSTIC_REPLACEMENTS, language);
  return applyReplacements(withoutDiagnostics, language === 'en' ? EN_ADVICE_REPLACEMENTS : ZH_ADVICE_REPLACEMENTS);
}

export function getBacktestObservationEventLabel(
  side: 'entry' | 'exit' | 'accumulate' | 'forced_close',
  language: BacktestLanguage,
): string {
  if (language === 'en') {
    if (side === 'entry') return 'Simulated observe trigger';
    if (side === 'exit') return 'Simulated observe release';
    if (side === 'accumulate') return 'Simulated periodic observe trigger';
    return 'End-of-window observe release';
  }
  if (side === 'entry') return '模拟观察触发';
  if (side === 'exit') return '模拟观察解除';
  if (side === 'accumulate') return '模拟定投触发';
  return '期末观察解除';
}
