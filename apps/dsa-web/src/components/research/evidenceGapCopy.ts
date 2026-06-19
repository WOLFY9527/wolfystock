export type EvidenceGapExplanationLocale = 'zh' | 'en';

export type EvidenceGapInput = string | {
  kind?: string | null;
  code?: string | null;
  field?: string | null;
  message?: string | null;
  reason?: string | null;
};

export type EvidenceGapFamily =
  | 'benchmark'
  | 'company'
  | 'peer'
  | 'media'
  | 'event'
  | 'recency'
  | 'options'
  | 'breadth'
  | 'priceHistoryStale'
  | 'dataDegraded'
  | 'insufficient'
  | 'staleInputs'
  | 'confidenceCapped'
  | 'evidenceConflict'
  | 'unknown';

export type EvidenceGapExplanationView = {
  key: EvidenceGapFamily;
  title: string;
  explanation: string;
  whyItMatters: string;
  suggestedResearchStep: string;
  confidenceImpact: string;
  observationBoundary: string;
  tone: 'neutral' | 'caution' | 'danger' | 'info';
};

const OBSERVATION_BOUNDARY: Record<EvidenceGapExplanationLocale, string> = {
  zh: '仅作观察，不构成操作结论。',
  en: 'Research observation only, not an action conclusion.',
};

const UNKNOWN_COPY: Record<EvidenceGapExplanationLocale, Omit<EvidenceGapExplanationView, 'key' | 'tone'>> = {
  zh: {
    title: '证据暂不可用',
    explanation: '部分证据暂不可用，因此当前结论只适合作为观察线索。',
    whyItMatters: '缺少可核对的输入时，页面无法说明结论是否仍被完整证据支持。',
    suggestedResearchStep: '先查看相邻研究入口，等待或补齐缺口后再复核。',
    confidenceImpact: '置信度受限：当前只适合低置信观察。',
    observationBoundary: OBSERVATION_BOUNDARY.zh,
  },
  en: {
    title: 'Evidence temporarily unavailable',
    explanation: 'Part of the evidence is unavailable, so the current conclusion is only an observation clue.',
    whyItMatters: 'Without verifiable inputs, the page cannot show whether the conclusion is fully supported.',
    suggestedResearchStep: 'Check nearby research surfaces, then refresh or fill the gap before reviewing again.',
    confidenceImpact: 'Confidence is limited: treat this as a low-confidence observation.',
    observationBoundary: OBSERVATION_BOUNDARY.en,
  },
};

const COPY: Record<EvidenceGapFamily, Record<EvidenceGapExplanationLocale, Omit<EvidenceGapExplanationView, 'key' | 'tone'>>> = {
  benchmark: {
    zh: {
      title: '基准证据缺失',
      explanation: '缺少基准或指数参照时，相对强弱和结构延续性只能作为线索。',
      whyItMatters: '没有市场参照，就难以区分相对强弱来自个股自身变化还是整体市场波动。',
      suggestedResearchStep: '先补充同周期基准表现，再比较标的与市场的相对变化。',
      confidenceImpact: '置信度受限：相对判断需要降级为观察线索。',
      observationBoundary: OBSERVATION_BOUNDARY.zh,
    },
    en: {
      title: 'Benchmark evidence missing',
      explanation: 'Without benchmark or index context, relative strength and structure follow-through remain clues only.',
      whyItMatters: 'A market reference is needed to separate single-name movement from broad market movement.',
      suggestedResearchStep: 'Add same-period benchmark performance, then compare the symbol against the market.',
      confidenceImpact: 'Confidence is limited: relative judgment stays observation-only.',
      observationBoundary: OBSERVATION_BOUNDARY.en,
    },
  },
  company: {
    zh: {
      title: '公司证据缺失',
      explanation: '缺少公司资料时，当前线索还不能和业务、盈利或估值背景互相验证。',
      whyItMatters: '没有公司层面的公开资料，就难以判断当前变化更接近短期波动还是基本面驱动。',
      suggestedResearchStep: '先补充主营业务、财务摘要或估值背景，再回来看当前线索是否仍成立。',
      confidenceImpact: '置信度受限：公司语境未补齐前，只能保留为观察线索。',
      observationBoundary: OBSERVATION_BOUNDARY.zh,
    },
    en: {
      title: 'Company evidence missing',
      explanation: 'Without company context, the current clue cannot be checked against business, earnings, or valuation background.',
      whyItMatters: 'Public company context is needed to tell whether the move is still only short-term noise or part of a broader business story.',
      suggestedResearchStep: 'Add business profile, financial summary, or valuation context, then review whether the clue still holds.',
      confidenceImpact: 'Confidence is limited: keep this as an observation clue until company context is filled in.',
      observationBoundary: OBSERVATION_BOUNDARY.en,
    },
  },
  peer: {
    zh: {
      title: '同业证据缺失',
      explanation: '缺少同业对照时，个股结构更容易受到单一标的噪声影响。',
      whyItMatters: '同业同步或背离可以帮助判断结构变化是否只是个股孤立现象。',
      suggestedResearchStep: '补充可比标的或行业篮子的同步走势，再复核结构是否仍成立。',
      confidenceImpact: '置信度受限：需要更多横向验证。',
      observationBoundary: OBSERVATION_BOUNDARY.zh,
    },
    en: {
      title: 'Peer evidence missing',
      explanation: 'Without peer comparison, the structure read can be overly shaped by single-name noise.',
      whyItMatters: 'Peer alignment or divergence helps test whether the structure is isolated or broader.',
      suggestedResearchStep: 'Add comparable names or sector basket movement, then review whether the structure still holds.',
      confidenceImpact: 'Confidence is limited: more cross-sectional evidence is needed.',
      observationBoundary: OBSERVATION_BOUNDARY.en,
    },
  },
  media: {
    zh: {
      title: '媒体语境缺失',
      explanation: '缺少媒体或公开报道语境时，当前线索无法确认是否已有公开信息跟进。',
      whyItMatters: '媒体语境能帮助判断市场是否已经看到同一条线索，或当前变化是否仍停留在早期观察阶段。',
      suggestedResearchStep: '先补充公开报道或公告摘要，再复核当前线索是否仍需要跟进。',
      confidenceImpact: '置信度受限：缺少媒体语境时，先保持观察边界。',
      observationBoundary: OBSERVATION_BOUNDARY.zh,
    },
    en: {
      title: 'Media context missing',
      explanation: 'Without media or public-report context, the current clue cannot show whether public information has already followed through.',
      whyItMatters: 'Media context helps test whether the same clue is already visible in public reporting or still early-stage observation only.',
      suggestedResearchStep: 'Add public reporting or announcement context, then review whether the clue still needs follow-up.',
      confidenceImpact: 'Confidence is limited: stay within observation boundaries until media context is filled in.',
      observationBoundary: OBSERVATION_BOUNDARY.en,
    },
  },
  event: {
    zh: {
      title: '事件语境缺失',
      explanation: '缺少事件线索时，当前变化无法和催化、日程或触发条件相互验证。',
      whyItMatters: '事件语境能帮助判断当前线索是否有明确触发点，还是仅仅处于观察阶段。',
      suggestedResearchStep: '先补充公告、财报、产品或行业事件，再复核当前线索是否延续。',
      confidenceImpact: '置信度受限：事件语境未补齐前，只保留为观察线索。',
      observationBoundary: OBSERVATION_BOUNDARY.zh,
    },
    en: {
      title: 'Event context missing',
      explanation: 'Without event context, the current move cannot be checked against catalysts, schedules, or trigger conditions.',
      whyItMatters: 'Event context helps test whether the clue has a clear trigger or remains only an observation.',
      suggestedResearchStep: 'Add filing, earnings, product, or industry event context, then review whether the clue continues.',
      confidenceImpact: 'Confidence is limited: keep this as an observation clue until event context is filled in.',
      observationBoundary: OBSERVATION_BOUNDARY.en,
    },
  },
  recency: {
    zh: {
      title: '时效复核缺失',
      explanation: '缺少时效复核时，页面还不能确认当前线索是否反映最新公开状态。',
      whyItMatters: '没有最近一次更新时间或复核记录，就难以判断当前线索是否已经变化或失效。',
      suggestedResearchStep: '先补做近期价格、公告或报道的时效复核，再比较当前线索是否仍成立。',
      confidenceImpact: '置信度受限：时效复核完成前，只能保留为观察线索。',
      observationBoundary: OBSERVATION_BOUNDARY.zh,
    },
    en: {
      title: 'Recency check missing',
      explanation: 'Without a recency review, the page cannot confirm whether the clue still reflects the latest public state.',
      whyItMatters: 'Without a recent review or timestamp check, the clue may already have changed or gone stale.',
      suggestedResearchStep: 'Review recent price, filing, or reporting freshness first, then compare whether the clue still holds.',
      confidenceImpact: 'Confidence is limited: keep this as an observation clue until recency is checked.',
      observationBoundary: OBSERVATION_BOUNDARY.en,
    },
  },
  options: {
    zh: {
      title: '期权证据缺失',
      explanation: '期权链、波动率或 Gamma 资料缺失时，衍生品压力只能保持观察。',
      whyItMatters: '缺少期权资料会限制对波动敏感路径和压力区间的理解。',
      suggestedResearchStep: '补充期权链、波动率或 Gamma 观察，再复核相关情景。',
      confidenceImpact: '置信度受限：期权相关结论保持观察级。',
      observationBoundary: OBSERVATION_BOUNDARY.zh,
    },
    en: {
      title: 'Options data missing',
      explanation: 'When options chain, volatility, or gamma evidence is missing, derivatives pressure stays observation-only.',
      whyItMatters: 'Missing options data limits context around volatility-sensitive paths and pressure zones.',
      suggestedResearchStep: 'Add options chain, volatility, or gamma observation before reviewing related scenarios.',
      confidenceImpact: 'Confidence is limited: options-related conclusions stay observational.',
      observationBoundary: OBSERVATION_BOUNDARY.en,
    },
  },
  breadth: {
    zh: {
      title: '广度证据缺失',
      explanation: '缺少市场广度输入时，个股或主题线索无法确认是否获得群体支持。',
      whyItMatters: '广度能帮助区分孤立变化和更广泛的参与。',
      suggestedResearchStep: '先查看市场概览或轮动页面，再复核参与度是否扩大。',
      confidenceImpact: '置信度受限：参与度不足时只保留为研究线索。',
      observationBoundary: OBSERVATION_BOUNDARY.zh,
    },
    en: {
      title: 'Breadth evidence missing',
      explanation: 'Without breadth inputs, symbol or theme clues cannot show whether participation is broad.',
      whyItMatters: 'Breadth helps separate isolated movement from wider participation.',
      suggestedResearchStep: 'Check Market Overview or rotation context, then review whether participation is broadening.',
      confidenceImpact: 'Confidence is limited: thin participation keeps the clue observational.',
      observationBoundary: OBSERVATION_BOUNDARY.en,
    },
  },
  priceHistoryStale: {
    zh: {
      title: '价格历史时效有限',
      explanation: '价格历史可能不是最新状态，结构信号需要先复核时效。',
      whyItMatters: '过期价格输入会影响趋势、突破、回撤和相对强弱观察。',
      suggestedResearchStep: '先刷新或补齐价格历史，再复核结构信号是否仍一致。',
      confidenceImpact: '置信度受限：时效复核前不宜提高判断等级。',
      observationBoundary: OBSERVATION_BOUNDARY.zh,
    },
    en: {
      title: 'Price history freshness limited',
      explanation: 'Price history may not be current, so structure signals need a freshness review first.',
      whyItMatters: 'Stale price inputs affect trend, breakout, pullback, and relative-strength observations.',
      suggestedResearchStep: 'Refresh or complete price history, then review whether the structure signal still matches.',
      confidenceImpact: 'Confidence is limited: keep the view below decision grade until freshness is reviewed.',
      observationBoundary: OBSERVATION_BOUNDARY.en,
    },
  },
  dataDegraded: {
    zh: {
      title: '数据来源暂时降级',
      explanation: '部分证据暂不可用，因此当前结论只适合作为观察线索。',
      whyItMatters: '降级输入会让页面无法完整确认证据覆盖和时效。',
      suggestedResearchStep: '稍后刷新，或从相邻研究页面核对同一线索是否仍存在。',
      confidenceImpact: '置信度受限：降级期间只保留研究线索。',
      observationBoundary: OBSERVATION_BOUNDARY.zh,
    },
    en: {
      title: 'Data source temporarily degraded',
      explanation: 'Part of the evidence is unavailable, so the current conclusion is only an observation clue.',
      whyItMatters: 'Degraded inputs limit confirmation of evidence coverage and freshness.',
      suggestedResearchStep: 'Refresh later or check a nearby research surface to see whether the same clue remains.',
      confidenceImpact: 'Confidence is limited: keep this as a research clue while inputs are degraded.',
      observationBoundary: OBSERVATION_BOUNDARY.en,
    },
  },
  insufficient: {
    zh: {
      title: '证据不足',
      explanation: '当前证据量不足，不能支撑更完整的研究解释。',
      whyItMatters: '样本、覆盖或验证项不足时，任何结论都容易受单一输入影响。',
      suggestedResearchStep: '先补齐缺失输入，或等待下一轮研究包更新后再复核。',
      confidenceImpact: '置信度受限：当前只能作为观察线索。',
      observationBoundary: OBSERVATION_BOUNDARY.zh,
    },
    en: {
      title: 'Evidence insufficient',
      explanation: 'The current evidence is too thin to support a fuller research explanation.',
      whyItMatters: 'Thin samples, coverage, or checks make conclusions overly dependent on one input.',
      suggestedResearchStep: 'Fill the missing input or wait for the next research packet update before reviewing again.',
      confidenceImpact: 'Confidence is limited: observation clue only for now.',
      observationBoundary: OBSERVATION_BOUNDARY.en,
    },
  },
  staleInputs: {
    zh: {
      title: '输入时效待更新',
      explanation: '部分输入需要刷新，当前页面还不能确认它们是否反映最新状态。',
      whyItMatters: '过期输入会让变化方向、风险标记和验证路径失真。',
      suggestedResearchStep: '刷新相关输入后，再比较更新前后的变化。',
      confidenceImpact: '置信度受限：刷新前保持低置信观察。',
      observationBoundary: OBSERVATION_BOUNDARY.zh,
    },
    en: {
      title: 'Inputs need freshness review',
      explanation: 'Some inputs need refresh, so the page cannot confirm whether they reflect the latest state.',
      whyItMatters: 'Stale inputs can distort direction, risk flags, and verification paths.',
      suggestedResearchStep: 'Refresh the relevant inputs, then compare the before and after changes.',
      confidenceImpact: 'Confidence is limited: low-confidence observation until refreshed.',
      observationBoundary: OBSERVATION_BOUNDARY.en,
    },
  },
  confidenceCapped: {
    zh: {
      title: '置信度受到上限约束',
      explanation: '当前证据还不足以支撑更高置信度，只能作为研究观察。',
      whyItMatters: '置信上限说明关键证据尚未补齐或质量仍有限。',
      suggestedResearchStep: '优先补齐缺口最大的输入，再复核置信度是否仍受限。',
      confidenceImpact: '置信度受限：不能升级为更强判断。',
      observationBoundary: OBSERVATION_BOUNDARY.zh,
    },
    en: {
      title: 'Confidence is capped',
      explanation: 'Current evidence does not support higher confidence, so treat it as research observation.',
      whyItMatters: 'A cap means key evidence is still missing or quality remains limited.',
      suggestedResearchStep: 'Fill the widest evidence gap first, then review whether confidence is still capped.',
      confidenceImpact: 'Confidence is limited: do not upgrade to a stronger judgment.',
      observationBoundary: OBSERVATION_BOUNDARY.en,
    },
  },
  evidenceConflict: {
    zh: {
      title: '证据存在分歧',
      explanation: '不同证据方向不一致，当前线索需要进一步交叉验证。',
      whyItMatters: '证据冲突会降低单一解释的可靠性。',
      suggestedResearchStep: '对照结构、基本面和市场语境，确认哪一类证据更稳定。',
      confidenceImpact: '置信度受限：冲突解除前保持观察级。',
      observationBoundary: OBSERVATION_BOUNDARY.zh,
    },
    en: {
      title: 'Evidence is conflicting',
      explanation: 'Evidence points in different directions, so the clue needs more cross-checking.',
      whyItMatters: 'Conflicting evidence reduces the reliability of a single explanation.',
      suggestedResearchStep: 'Compare structure, fundamentals, and market context to see which evidence is more stable.',
      confidenceImpact: 'Confidence is limited: stay observational until the conflict is resolved.',
      observationBoundary: OBSERVATION_BOUNDARY.en,
    },
  },
  unknown: UNKNOWN_COPY,
};

const FAMILY_TONE: Record<EvidenceGapFamily, EvidenceGapExplanationView['tone']> = {
  benchmark: 'caution',
  company: 'caution',
  peer: 'caution',
  media: 'caution',
  event: 'caution',
  recency: 'caution',
  options: 'caution',
  breadth: 'caution',
  priceHistoryStale: 'caution',
  dataDegraded: 'info',
  insufficient: 'danger',
  staleInputs: 'caution',
  confidenceCapped: 'caution',
  evidenceConflict: 'danger',
  unknown: 'info',
};

function normalizeGapText(value: unknown): string {
  return String(value || '')
    .trim()
    .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
    .toLowerCase()
    .replace(/[:=./\\\s-]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '');
}

function gapInputText(input: EvidenceGapInput | null | undefined): string {
  if (typeof input === 'string') return input;
  if (!input || typeof input !== 'object') return '';
  return [
    input.kind,
    input.code,
    input.field,
    input.reason,
    input.message,
  ].filter(Boolean).join(' ');
}

function normalizeGapFamily(input: EvidenceGapInput | null | undefined): EvidenceGapFamily {
  const normalized = normalizeGapText(gapInputText(input));
  if (!normalized) return 'unknown';
  if (normalized.includes('confidence_cap') || normalized.includes('confidence_capped') || normalized.includes('capped')) return 'confidenceCapped';
  if (normalized.includes('benchmark') || normalized.includes('index_context')) return 'benchmark';
  if (
    normalized.includes('fundamental')
    || normalized.includes('company')
    || normalized.includes('issuer')
    || normalized.includes('business_profile')
    || normalized.includes('financial_summary')
  ) return 'company';
  if (normalized.includes('peer') || normalized.includes('correlation') || normalized.includes('sector_basket')) return 'peer';
  if (normalized.includes('news') || normalized.includes('headline') || normalized.includes('media')) return 'media';
  if (normalized.includes('catalyst') || normalized.includes('event')) return 'event';
  if (normalized.includes('freshness') || normalized.includes('recency') || normalized.includes('staleevidence') || normalized.includes('asof')) return 'recency';
  if (normalized.includes('option') || normalized.includes('gamma') || normalized.includes('gex') || normalized.includes('contract')) return 'options';
  if (normalized.includes('breadth') || normalized.includes('participation')) return 'breadth';
  if ((normalized.includes('price') || normalized.includes('history') || normalized.includes('ohlcv')) && normalized.includes('stale')) return 'priceHistoryStale';
  if (normalized.includes('stale_input') || normalized.includes('stale_inputs') || normalized.includes('freshness')) return 'staleInputs';
  if (normalized.includes('conflict') || normalized.includes('divergent') || normalized.includes('divergence')) return 'evidenceConflict';
  if (normalized.includes('timeout') || normalized.includes('degraded')) return 'dataDegraded';
  if (normalized.includes('insufficient') || normalized.includes('missing') || normalized.includes('unavailable') || normalized.includes('not_enough')) return 'insufficient';
  return 'unknown';
}

export function buildEvidenceGapExplanation(
  gap: EvidenceGapInput | null | undefined,
  locale: EvidenceGapExplanationLocale = 'zh',
): EvidenceGapExplanationView {
  const family = normalizeGapFamily(gap);
  return {
    key: family,
    tone: FAMILY_TONE[family],
    ...COPY[family][locale],
  };
}

export function buildEvidenceGapExplanations(
  gaps: Array<EvidenceGapInput | null | undefined> | null | undefined,
  locale: EvidenceGapExplanationLocale = 'zh',
): EvidenceGapExplanationView[] {
  const seen = new Set<EvidenceGapFamily>();
  const explanations: EvidenceGapExplanationView[] = [];
  for (const gap of gaps ?? []) {
    const explanation = buildEvidenceGapExplanation(gap, locale);
    if (seen.has(explanation.key)) continue;
    seen.add(explanation.key);
    explanations.push(explanation);
  }
  return explanations;
}
