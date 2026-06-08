import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { BrandedLoadingScreen } from '../BrandedLoadingScreen';

describe('BrandedLoadingScreen', () => {
  it('renders WolfyStock research loading copy without terminal boot narrative', () => {
    render(<BrandedLoadingScreen text="正在加载 WolfyStock 研究工作区..." subtext="加载中..." />);

    expect(screen.getByRole('status', { name: 'WolfyStock research workspace loading' })).toBeInTheDocument();
    expect(screen.getByText('WOLFYSTOCK')).toBeInTheDocument();
    expect(screen.getByText('正在加载 WolfyStock 研究工作区...')).toBeInTheDocument();
    expect(screen.getByText('加载中...')).toBeInTheDocument();
    expect(screen.queryByText('INITIALIZING WOLFY AI CORE...')).not.toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'WolfyStock logo' })).toHaveAttribute('src', '/wolfystock-logo-mark.png');
  });
});
