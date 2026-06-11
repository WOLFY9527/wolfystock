import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { DataTrustEvidenceChips } from '../DataTrustEvidenceChips';

describe('DataTrustEvidenceChips', () => {
  it('renders bounded canonical chips and hides raw input terms', () => {
    render(
      <DataTrustEvidenceChips
        data-testid="data-trust"
        input={{
          locale: 'zh',
          states: ['fallback', 'observation-only'],
          terms: ['providerRuntime', 'routeRejected', '/api/v1/admin/providers'],
          confidenceCap: 45,
        }}
      />,
    );

    const strip = screen.getByTestId('data-trust');
    expect(strip).toHaveTextContent('备用数据');
    expect(strip).toHaveTextContent('仅供观察');
    expect(strip).toHaveTextContent('不构成投资建议');
    expect(strip).toHaveTextContent('置信上限 45');
    expect(strip).not.toHaveTextContent(/providerRuntime|routeRejected|api\/v1/i);
  });

  it('renders nothing for an empty model when safety copy is disabled', () => {
    const { container } = render(
      <DataTrustEvidenceChips
        input={{
          states: [],
          includeSafetyState: false,
        }}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('does not render unsafe asOf diagnostics in the chip strip', () => {
    render(
      <DataTrustEvidenceChips
        data-testid="data-trust"
        input={{
          locale: 'en',
          states: ['authoritative'],
          asOf: '/api/v1/admin/providers?debugRef=providerRuntime',
        }}
      />,
    );

    const strip = screen.getByTestId('data-trust');
    expect(strip).toHaveTextContent('Authoritative');
    expect(strip).not.toHaveTextContent(/api\/v1|debugRef|providerRuntime/i);
  });

  it('rebuilds provided view models with bounded labels before rendering', () => {
    render(
      <DataTrustEvidenceChips
        data-testid="data-trust"
        showMessage
        viewModel={{
          primaryState: 'fallback',
          states: ['fallback', 'not-investment-advice'],
          chips: [
            {
              state: 'fallback',
              label: 'providerRuntime routeRejected /api/v1/admin/providers',
              message: 'rawProviderPayload stack trace prompt debugRef',
              tone: 'danger',
            },
          ],
          message: 'rawProviderPayload stack trace prompt debugRef',
          locale: 'en',
          asOf: '/api/v1/admin/providers?debugRef=providerRuntime',
        }}
      />,
    );

    const strip = screen.getByTestId('data-trust');
    expect(strip).toHaveTextContent('Fallback');
    expect(strip).toHaveTextContent('Not investment advice');
    expect(strip).toHaveTextContent('Fallback evidence is in use');
    expect(strip).not.toHaveTextContent(/providerRuntime|routeRejected|api\/v1|rawProviderPayload|stack trace|prompt|debugRef/i);
  });
});
