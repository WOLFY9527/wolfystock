import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';
import type { UiLanguage } from '../../i18n/core';
import { DocumentTitleLifecycle } from '../DocumentTitleLifecycle';
import { getDocumentTitle } from '../documentTitle';

function LifecycleHarness() {
  const navigate = useNavigate();
  const [language, setLanguage] = useState<UiLanguage>('zh');

  return (
    <>
      <DocumentTitleLifecycle language={language} />
      <button type="button" onClick={() => navigate('/stocks/TSLA/structure-decision')}>TSLA</button>
      <button type="button" onClick={() => navigate('/market-overview')}>Market overview</button>
      <button type="button" onClick={() => navigate('/market/liquidity-monitor')}>Liquidity monitor</button>
      <button type="button" onClick={() => navigate(-1)}>Back</button>
      <button type="button" onClick={() => navigate(1)}>Forward</button>
      <button type="button" onClick={() => setLanguage('en')}>English</button>
    </>
  );
}

describe('document title route identity', () => {
  it.each([
    ['/market-overview', 'zh', '市场总览 - WolfyStock'],
    ['/research/radar', 'en', 'Research Radar - WolfyStock'],
    ['/scenario-lab', 'zh', '情景实验室 - WolfyStock'],
    ['/options-lab', 'en', 'Options Lab - WolfyStock'],
    ['/settings/system', 'zh', '系统设置 - WolfyStock'],
    ['/admin/launch-cockpit', 'en', 'Launch Cockpit - WolfyStock'],
    ['/admin/evidence-workflow', 'zh', '证据工作流 - WolfyStock'],
    ['/admin/provider-circuits', 'en', 'Circuit Diagnostics - WolfyStock'],
    ['/admin/cost-observability', 'zh', '成本观测 - WolfyStock'],
    ['/backtest/compare', 'en', 'Rule Backtest Comparison - WolfyStock'],
    ['/backtest/results/42', 'zh', '确定性回测结果 #42 - WolfyStock'],
    ['/backtest/results/invalid', 'en', 'Deterministic Backtest Result - WolfyStock'],
    ['/stocks/aapl/structure-decision', 'zh', 'AAPL 个股研究 - WolfyStock'],
    ['/stocks/tsla/structure-decision', 'en', 'TSLA Stock Research - WolfyStock'],
    ['/market', 'en', 'Market Overview - WolfyStock'],
    ['/stock/aapl', 'zh', 'AAPL 个股研究 - WolfyStock'],
    ['/admin/evidence', 'en', 'Evidence Workflow - WolfyStock'],
    ['/admin/users/user-42/activity', 'zh', '用户治理 - WolfyStock'],
    ['/guest/scanner', 'en', 'Market Scanner - WolfyStock'],
    ['/zh/market-overview', 'en', '市场总览 - WolfyStock'],
    ['/en/market-overview', 'zh', 'Market Overview - WolfyStock'],
    ['/missing-route', 'en', 'Page Not Found - WolfyStock'],
  ] as const)('resolves %s in %s', (pathname, language, expected) => {
    expect(getDocumentTitle(pathname, language)).toBe(expected);
  });

  it('updates dynamic, locale, and memory-history titles without retaining a prior route title', () => {
    render(
      <MemoryRouter initialEntries={['/stocks/AAPL/structure-decision']}>
        <LifecycleHarness />
      </MemoryRouter>,
    );

    expect(document.title).toBe('AAPL 个股研究 - WolfyStock');

    fireEvent.click(screen.getByRole('button', { name: 'TSLA' }));
    expect(document.title).toBe('TSLA 个股研究 - WolfyStock');

    fireEvent.click(screen.getByRole('button', { name: 'Back' }));
    expect(document.title).toBe('AAPL 个股研究 - WolfyStock');

    fireEvent.click(screen.getByRole('button', { name: 'Forward' }));
    expect(document.title).toBe('TSLA 个股研究 - WolfyStock');

    fireEvent.click(screen.getByRole('button', { name: 'Market overview' }));
    expect(document.title).toBe('市场总览 - WolfyStock');

    fireEvent.click(screen.getByRole('button', { name: 'English' }));
    expect(document.title).toBe('Market Overview - WolfyStock');

    fireEvent.click(screen.getByRole('button', { name: 'Liquidity monitor' }));
    expect(document.title).toBe('Liquidity Monitor - WolfyStock');
  });
});
