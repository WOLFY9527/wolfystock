import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { WorkspacePageHeader } from '../WorkspacePageHeader';

describe('WorkspacePageHeader', () => {
  it('uses default density for normal workbench pages', () => {
    render(
      <WorkspacePageHeader
        eyebrow="Workbench"
        title="Market Overview"
        description="Research surface"
      />,
    );

    const header = screen.getByRole('banner');
    expect(header).toHaveAttribute('data-header-density', 'default');
    expect(header.className).not.toContain('workspace-header-panel--compact');
    expect(screen.getByRole('heading', { level: 1, name: 'Market Overview' })).toBeInTheDocument();
  });

  it('supports explicit compact density for gate surfaces without changing default consumers', () => {
    render(
      <WorkspacePageHeader
        density="compact"
        eyebrow="Prototype Gated"
        title="Admin Mission Control prototype is disabled"
      />,
    );

    const header = screen.getByRole('banner');
    expect(header).toHaveAttribute('data-header-density', 'compact');
    expect(header.className).toContain('workspace-header-panel--compact');
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Admin Mission Control prototype is disabled',
    );
  });
});
