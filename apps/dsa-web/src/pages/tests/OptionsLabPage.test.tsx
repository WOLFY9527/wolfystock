// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const source = readFileSync(resolve(process.cwd(), 'src/pages/OptionsLabPage.tsx'), 'utf8');

describe('OptionsLabPage research-trust copy sentinels', () => {
  it('keeps visible framing analytical and no-decision grade', () => {
    expect(source).toContain('只读观察');
    expect(source).toContain('不构成买卖建议');
    expect(source).toContain('不可用于真实交易判断');
    expect(source).toContain('不会提交订单');
    expect(source).toContain('不连接经纪商');
    expect(source).toContain('不改动投资组合');
    expect(source).toContain('options-lab-consumer-availability');
    expect(source).toContain('观察结构样例');
    expect(source).toContain('首个观察结构');
    expect(source).toContain('样例顺序 #');
    expect(source).toContain('情景上沿');
    expect(source).toContain('目标价下情景估算');
    expect(source).toContain('未设上沿，不代表可获利');
    expect(source).toContain('假设价格');
    expect(source).toContain('专业结构：');

    [
      'trade quality',
      '决策实验室',
      '可成交性',
      '有条件可交易',
      '候选策略',
      '首个候选',
      '观察排序 #',
      '先看排序靠前的结构',
      '最大收益',
      '情景收益',
      '上涨情景',
      '下跌情景',
      '目标价格',
      '再决定是否继续跟踪',
    ].forEach((forbidden) => {
      expect(source).not.toContain(forbidden);
    });
  });
});
