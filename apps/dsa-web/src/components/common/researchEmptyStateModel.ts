export const CONSUMER_RESEARCH_EMPTY_STATE_CASES = [
  'insufficientEvidence',
  'staleEvidence',
  'unavailableData',
  'missingResearchPacket',
  'noQueueItems',
  'partialCoverage',
  'loading',
] as const;

export type ConsumerResearchEmptyStateCase = typeof CONSUMER_RESEARCH_EMPTY_STATE_CASES[number];
export type ConsumerResearchEmptyStateLocale = 'zh' | 'en';
export type ConsumerResearchEmptyStateSeverity = 'neutral' | 'limited' | 'unavailable';

export interface ConsumerResearchEmptyStateView {
  title: string;
  body: string;
  nextResearchStep?: string;
  severity: ConsumerResearchEmptyStateSeverity;
  observationOnly: true;
}

type ConsumerResearchEmptyStateCopy = Omit<ConsumerResearchEmptyStateView, 'observationOnly'>;

const EMPTY_STATE_COPY: Record<ConsumerResearchEmptyStateCase, Record<ConsumerResearchEmptyStateLocale, ConsumerResearchEmptyStateCopy>> = {
  insufficientEvidence: {
    zh: {
      title: '证据暂不足',
      body: '当前研究资料还不完整，先作为观察线索阅读。',
      nextResearchStep: '先核对覆盖缺口，再补充公开资料。',
      severity: 'limited',
    },
    en: {
      title: 'Evidence is still insufficient',
      body: 'The research material is incomplete, so read this as observation context only.',
      nextResearchStep: 'Review the visible coverage gaps before interpreting the context.',
      severity: 'limited',
    },
  },
  staleEvidence: {
    zh: {
      title: '证据时效有限',
      body: '当前可见资料可能不是最新状态，先等待下一轮更新后再解读。',
      nextResearchStep: '刷新研究资料后再比较变化。',
      severity: 'limited',
    },
    en: {
      title: 'Evidence freshness is limited',
      body: 'The visible material may not reflect the latest state, so keep it in observation mode.',
      nextResearchStep: 'Refresh the research material before comparing changes.',
      severity: 'limited',
    },
  },
  unavailableData: {
    zh: {
      title: '数据暂不可用',
      body: '当前页面没有可展示的稳定研究资料，请稍后重试。',
      nextResearchStep: '也可以先查看相邻研究入口的公开线索。',
      severity: 'unavailable',
    },
    en: {
      title: 'Data is temporarily unavailable',
      body: 'This page does not have stable research material to display right now.',
      nextResearchStep: 'Use a nearby research entry while this page refreshes.',
      severity: 'unavailable',
    },
  },
  missingResearchPacket: {
    zh: {
      title: '研究包未就绪',
      body: '该入口还没有可读取的研究包，请先完成基础研究流程。',
      nextResearchStep: '从市场概览、扫描器或观察列表整理线索。',
      severity: 'unavailable',
    },
    en: {
      title: 'Research packet is not ready',
      body: 'This entry does not have a readable research packet yet.',
      nextResearchStep: 'Build context from Market Overview, Scanner, or Watchlist first.',
      severity: 'unavailable',
    },
  },
  noQueueItems: {
    zh: {
      title: '暂无研究队列',
      body: '还没有进入队列的研究对象，先从上游研究入口整理线索。',
      nextResearchStep: '从市场概览、扫描器或观察列表开始。',
      severity: 'neutral',
    },
    en: {
      title: 'No research queue items yet',
      body: 'No research object has entered the queue yet; start from an upstream research entry.',
      nextResearchStep: 'Begin with Market Overview, Scanner, or Watchlist.',
      severity: 'neutral',
    },
  },
  partialCoverage: {
    zh: {
      title: '覆盖仍不完整',
      body: '部分资料已可阅读，但覆盖范围有限，解读前先确认缺口。',
      nextResearchStep: '优先补齐缺口最高的资料。',
      severity: 'limited',
    },
    en: {
      title: 'Coverage is still partial',
      body: 'Review the visible gaps before reading the research context.',
      nextResearchStep: 'Start with the evidence area that has the widest gap.',
      severity: 'limited',
    },
  },
  loading: {
    zh: {
      title: '正在整理研究资料',
      body: '页面仍在加载研究资料，请等待当前更新完成。',
      severity: 'neutral',
    },
    en: {
      title: 'Research material is loading',
      body: 'This page is still loading research material; wait for the current update to finish.',
      severity: 'neutral',
    },
  },
};

export function buildConsumerResearchEmptyState(
  emptyCase: ConsumerResearchEmptyStateCase,
  locale: ConsumerResearchEmptyStateLocale = 'zh',
): ConsumerResearchEmptyStateView {
  return {
    ...EMPTY_STATE_COPY[emptyCase][locale],
    observationOnly: true,
  };
}
