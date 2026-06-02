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

    [
      'trade quality',
      '决策实验室',
      '可成交性',
      '有条件可交易',
    ].forEach((forbidden) => {
      expect(source).not.toContain(forbidden);
    });
  });
});
