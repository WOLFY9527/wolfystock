import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import {
  LeadText,
  MetaLabel,
  MetricValue,
  NextResearchAction,
  ObservationHead,
  ObservationTitle,
  RESEARCH_DENSITY_MODES,
  RESEARCH_NESTING_MAX_VISIBLE_FRAMES,
  ResearchDataQualityComposition,
  ResearchFrame,
  ResearchRiskLimits,
  SectionTitle,
  computeFrameDepth,
  countContributingFrames,
  isWithinNestingBudget,
  nestingBudgetViolation,
  normalizeResearchDensityMode,
} from '../anatomy';

const FORBIDDEN_ADVICE = /买入|卖出|持有|目标价|止损|加仓|减仓|仓位建议|buy\b|sell\b|hold\b|entry\b|exit\b|target price|stop loss|position sizing|trade now/i;

describe('research density modes', () => {
  it('supports exactly three shared modes', () => {
    expect(RESEARCH_DENSITY_MODES).toEqual(['editorial', 'research', 'workbench']);
    expect(normalizeResearchDensityMode('editorial')).toBe('editorial');
    expect(normalizeResearchDensityMode('workbench')).toBe('workbench');
    expect(normalizeResearchDensityMode('unknown')).toBe('research');
  });
});

describe('nesting budget', () => {
  it('allows board → section and treats content as non-contributing', () => {
    expect(RESEARCH_NESTING_MAX_VISIBLE_FRAMES).toBe(2);
    expect(countContributingFrames(['board', 'section', 'content'])).toBe(2);
    expect(isWithinNestingBudget(2)).toBe(true);
    expect(nestingBudgetViolation(['board', 'section', 'content'])).toEqual({ ok: true });
  });

  it('flags board → section → section as a budget violation', () => {
    const violation = nestingBudgetViolation(['board', 'section', 'section']);
    expect(violation).toEqual({ ok: false, depth: 3, max: 2 });
    expect(computeFrameDepth(2, 'section')).toBe(3);
    expect(computeFrameDepth(2, 'content')).toBe(2);
  });

  it('marks ResearchFrame depth for consumer scope only', () => {
    render(
      <ResearchFrame role="board" parentDepth={0} data-testid="board" density="research">
        <ResearchFrame role="section" parentDepth={1} data-testid="section">
          <ResearchFrame role="content" parentDepth={2} data-testid="content">
            rows
          </ResearchFrame>
        </ResearchFrame>
      </ResearchFrame>,
    );

    expect(screen.getByTestId('board')).toHaveAttribute('data-research-frame', 'board');
    expect(screen.getByTestId('board')).toHaveAttribute('data-research-frame-depth', '1');
    expect(screen.getByTestId('board')).toHaveAttribute('data-research-surface-scope', 'consumer');
    expect(screen.getByTestId('board')).toHaveAttribute('data-research-density', 'research');
    expect(screen.getByTestId('section')).toHaveAttribute('data-research-frame-depth', '2');
    expect(screen.getByTestId('content')).toHaveAttribute('data-research-frame', 'content');
    expect(screen.getByTestId('content')).toHaveAttribute('data-research-frame-depth', '2');
  });
});

describe('typography roles', () => {
  it('renders observation/section/meta/metric/lead roles with paper token classes', () => {
    render(
      <div>
        <ObservationTitle data-testid="obs">当前观察标题</ObservationTitle>
        <SectionTitle data-testid="sec">证据区</SectionTitle>
        <MetaLabel data-testid="meta">路由身份</MetaLabel>
        <MetricValue data-testid="metric">12.4%</MetricValue>
        <LeadText data-testid="lead">结构仍需确认，证据覆盖有限。</LeadText>
      </div>,
    );

    expect(screen.getByTestId('obs')).toHaveAttribute('data-research-type-role', 'observation-title');
    expect(screen.getByTestId('obs')).toHaveClass('research-type-observation-title');
    expect(screen.getByTestId('sec')).toHaveAttribute('data-research-type-role', 'section-title');
    expect(screen.getByTestId('meta')).toHaveAttribute('data-research-type-role', 'meta-label');
    expect(screen.getByTestId('metric')).toHaveAttribute('data-research-type-role', 'metric-value');
    expect(screen.getByTestId('metric')).toHaveClass('research-type-metric-value');
    expect(screen.getByTestId('lead')).toHaveAttribute('data-research-type-role', 'lead-text');
  });
});

describe('ObservationHead', () => {
  it('renders conclusion-first anatomy with density and fact blocks', () => {
    render(
      <ObservationHead
        eyebrow="晨间研究"
        title="广度回升，但量能仍待确认"
        lead="当前观察支持继续研究，不支持直接行动。"
        known={[{ body: '主要指数日内回升' }]}
        unknown={[{ body: '成交量是否持续放大' }]}
        changing={[{ body: '成长板块相对强弱' }]}
        contradictory={[{ body: '风险偏好与波动结构不完全一致' }]}
        status={<span data-testid="status-pill">部分可用</span>}
        density="editorial"
        locale="zh"
      />,
    );

    const head = screen.getByTestId('observation-head');
    expect(head.tagName).toBe('HEADER');
    expect(head).toHaveAttribute('data-research-anatomy', 'observation-head');
    expect(head).toHaveAttribute('data-research-density', 'editorial');
    expect(head).toHaveAttribute('aria-labelledby', 'observation-head-title');
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('广度回升，但量能仍待确认');
    expect(screen.getByText('已知')).toBeInTheDocument();
    expect(screen.getByText('未知')).toBeInTheDocument();
    expect(screen.getByText('变化中')).toBeInTheDocument();
    expect(screen.getByText('矛盾点')).toBeInTheDocument();
    expect(screen.getByTestId('status-pill')).toBeInTheDocument();
    expect(head.textContent || '').not.toMatch(FORBIDDEN_ADVICE);
  });

  it('stacks fact labels in English and avoids recommendation language', () => {
    render(
      <ObservationHead
        eyebrow="Structure"
        title="Structure still needs confirmation"
        lead="Evidence supports continued observation only."
        known="Price held the recent range."
        density="research"
        locale="en"
      />,
    );

    expect(screen.getByText('Known')).toBeInTheDocument();
    expect(screen.getByTestId('observation-head').textContent || '').not.toMatch(FORBIDDEN_ADVICE);
  });
});

describe('ResearchDataQualityComposition', () => {
  it('preserves distinct quality facets and reuses status slots', () => {
    render(
      <ResearchDataQualityComposition
        locale="zh"
        density="research"
        statusSlot={<div data-testid="existing-status-strip">读模型就绪</div>}
        facets={[
          { kind: 'freshness', label: '新鲜度', value: '最近可用' },
          { kind: 'stale', label: '陈旧', detail: 'stale != fresh' },
          { kind: 'unavailable', label: '不可用', detail: 'unavailable != zero' },
          { kind: 'authority', label: '权威性', detail: 'proxy != official' },
          { kind: 'observation-only', label: '仅观察' },
        ]}
      />,
    );

    const quality = screen.getByTestId('research-data-quality');
    expect(quality).toHaveAttribute('data-research-anatomy', 'data-quality');
    expect(screen.getByTestId('existing-status-strip')).toBeInTheDocument();
    expect(quality.querySelector('[data-quality-facet="stale"]')).not.toBeNull();
    expect(quality.querySelector('[data-quality-facet="unavailable"]')).not.toBeNull();
    expect(quality.querySelector('[data-quality-facet="authority"]')).not.toBeNull();
    expect(quality.querySelector('[data-quality-facet="observation-only"]')).not.toBeNull();
    expect(quality.textContent || '').toMatch(/stale != fresh/);
    expect(quality.textContent || '').toMatch(/unavailable != zero/);
    expect(quality.textContent || '').not.toMatch(FORBIDDEN_ADVICE);
  });

  it('returns null when empty', () => {
    const { container } = render(<ResearchDataQualityComposition />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe('ResearchRiskLimits', () => {
  it('renders compact summary groups without warning-card sprawl', () => {
    render(
      <ResearchRiskLimits
        locale="zh"
        placement="summary"
        cannotEstablish={['无法确认趋势反转']}
        invalidation={['量能回落并跌破关键区域']}
        missingEvidence={['缺少成交量确认']}
        modelLimitations={['模型仅使用已披露结构证据']}
        dataLimitations={['部分字段延迟']}
        confidenceCap="置信上限受覆盖限制"
      />,
    );

    const limits = screen.getByTestId('research-risk-limits');
    expect(limits).toHaveAttribute('data-risk-limits-placement', 'summary');
    expect(screen.getByText('当前证据不能成立')).toBeInTheDocument();
    expect(screen.getByText('失效条件')).toBeInTheDocument();
    expect(screen.getByText('置信上限')).toBeInTheDocument();
    expect(limits.className).not.toMatch(/bg-red|warning-card|alert-danger/);
    expect(limits.textContent || '').not.toMatch(FORBIDDEN_ADVICE);
  });

  it('supports disclosure placement', () => {
    render(
      <ResearchRiskLimits
        locale="en"
        placement="disclosure"
        defaultOpen={false}
        missingEvidence={['Volume confirmation missing']}
      />,
    );

    const limits = screen.getByTestId('research-risk-limits');
    expect(limits).toHaveAttribute('data-risk-limits-placement', 'disclosure');
    expect(screen.queryByText('Volume confirmation missing')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByText('Volume confirmation missing')).toBeInTheDocument();
  });
});

describe('NextResearchAction', () => {
  it('renders research workflow navigation, not trade actions', () => {
    render(
      <MemoryRouter>
        <NextResearchAction
          locale="zh"
          density="workbench"
          steps={[
            {
              kind: 'inspect',
              label: '打开结构证据',
              description: '核对关键区域与证据覆盖',
              href: '/stocks/structure-decision',
            },
            {
              kind: 'compare',
              label: '比较市场概览',
              href: '/market-overview',
            },
            {
              kind: 'validate',
              label: '继续验证扫描结果',
            },
            {
              kind: 'gap',
              label: '检查缺口',
            },
          ]}
        />
      </MemoryRouter>,
    );

    const nav = screen.getByTestId('next-research-action');
    expect(nav.tagName).toBe('NAV');
    expect(nav).toHaveAttribute('data-research-density', 'workbench');
    expect(screen.getByText('查看证据')).toBeInTheDocument();
    expect(screen.getByText('比较')).toBeInTheDocument();
    expect(screen.getByText('验证')).toBeInTheDocument();
    expect(nav.querySelector('[data-next-action-kind="gap"]')).toHaveTextContent('检查缺口');
    expect(screen.getByRole('link', { name: /打开结构证据/ })).toHaveAttribute(
      'href',
      '/stocks/structure-decision',
    );
    expect(nav.textContent || '').not.toMatch(FORBIDDEN_ADVICE);
  });
});

describe('consumer paper material assumptions', () => {
  it('does not hardcode white/black consumer foreground slabs in anatomy output', () => {
    const { container } = render(
      <ObservationHead title="观察" density="research" locale="zh" />,
    );
    const markup = container.innerHTML;
    expect(markup).not.toMatch(/text-white|bg-black\/|border-white\/|bg-white\//);
  });
});

describe('responsive / accessibility landmarks', () => {
  it('exposes heading and landmark structure for observation + next action', () => {
    render(
      <MemoryRouter>
        <ObservationHead title="第一观察" lead="简要说明" locale="zh" />
        <NextResearchAction
          locale="zh"
          steps={[{ kind: 'continue', label: '下一步检查量能' }]}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { level: 1, name: '第一观察' })).toBeInTheDocument();
    const nav = screen.getByRole('navigation', { name: '下一步研究' });
    expect(within(nav).getByText('下一步检查量能')).toBeInTheDocument();
  });
});
