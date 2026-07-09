import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { AccessGatePage } from '../AccessGatePage';

describe('AccessGatePage', () => {
  it('renders compact gate identity, state, boundary, and action hierarchy', () => {
    render(
      <MemoryRouter>
        <AccessGatePage
          eyebrow="Registered User Only"
          title="Sign in to continue"
          description="This workflow requires a real account."
          bullets={[
            'Saved history belongs to authenticated users.',
            'Guest mode stays in preview only.',
          ]}
          statusLabel="Guest Preview Only"
          note="After sign-in, you will return to this workflow automatically."
          primaryAction={{ label: 'Sign in', to: '/login?redirect=%2Fchat' }}
          secondaryAction={{ label: 'Create account', to: '/login?mode=create&redirect=%2Fchat' }}
          tertiaryAction={{ label: 'Back home', to: '/' }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByTestId('access-gate-page')).toBeInTheDocument();
    expect(screen.getByTestId('access-gate-eyebrow')).toHaveTextContent('Registered User Only');
    expect(screen.getByRole('heading', { level: 1, name: 'Sign in to continue' })).toBeInTheDocument();
    expect(screen.getByTestId('access-gate-status-pill')).toHaveTextContent('Guest Preview Only');
    expect(screen.getByTestId('access-gate-state-band')).toBeInTheDocument();
    expect(screen.getByTestId('access-gate-reason')).toHaveTextContent('This workflow requires a real account.');
    expect(screen.getByTestId('access-gate-boundary')).toHaveTextContent('Saved history belongs to authenticated users.');
    expect(screen.getByTestId('access-gate-primary-action')).toHaveAttribute('href', '/login?redirect=%2Fchat');
    expect(screen.getByTestId('access-gate-secondary-action')).toHaveAttribute(
      'href',
      '/login?mode=create&redirect=%2Fchat',
    );
    expect(screen.getByTestId('access-gate-tertiary-action')).toHaveAttribute('href', '/');
    expect(screen.getByTestId('access-gate-note')).toHaveTextContent(
      'After sign-in, you will return to this workflow automatically.',
    );

    const header = screen.getByRole('banner');
    expect(header).toHaveAttribute('data-header-density', 'compact');
    expect(header.className).toContain('workspace-header-panel--compact');
  });

  it('keeps prototype-disabled state honest without fabricating healthy status', () => {
    render(
      <MemoryRouter>
        <AccessGatePage
          eyebrow="Prototype Gated"
          title="Admin Mission Control prototype is disabled"
          description="This cockpit is hidden by default and only opens when the explicit prototype flag is enabled for admin review."
          bullets={[
            'Default navigation does not advertise this cockpit.',
            'The backend disabled response does not aggregate ops summaries.',
          ]}
          statusLabel="Prototype Disabled"
          note="Set VITE_WOLFYSTOCK_ADMIN_MISSION_CONTROL_PROTOTYPE_ENABLED=true only for bounded prototype review."
          primaryAction={{ label: 'Open personal settings', to: '/settings' }}
          secondaryAction={{ label: 'Open system settings', to: '/settings/system' }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: 'Admin Mission Control prototype is disabled' })).toBeInTheDocument();
    expect(screen.getByTestId('access-gate-status-pill')).toHaveTextContent(/Prototype Disabled/i);
    expect(screen.queryByText(/ready|healthy|available/i)).not.toBeInTheDocument();
    expect(screen.getByTestId('access-gate-primary-action')).toHaveAttribute('href', '/settings');
    expect(screen.getByTestId('access-gate-secondary-action')).toHaveAttribute('href', '/settings/system');
  });
});
