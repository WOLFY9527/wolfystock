import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { useProductSurfaceMock, loadUserScannerPageMock } = vi.hoisted(() => ({
  useProductSurfaceMock: vi.fn(),
  loadUserScannerPageMock: vi.fn(),
}));

vi.mock('../../hooks/useProductSurface', () => ({
  useProductSurface: () => useProductSurfaceMock(),
}));

vi.mock('../../components/auth/AuthGuardOverlay', () => ({
  AuthGuardOverlay: ({ moduleName }: { moduleName: string }) => <div>{`auth-guard:${moduleName}`}</div>,
}));

vi.mock('../UserScannerPage', () => ({
  ...(() => {
    loadUserScannerPageMock();
    return {
      default: () => <div>user scanner page</div>,
    };
  })(),
}));

describe('ScannerSurfacePage', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  async function renderScannerSurfacePage() {
    const { default: ScannerSurfacePage } = await import('../ScannerSurfacePage');
    render(<ScannerSurfacePage />);
  }

  it('renders the auth guard placeholder for guests on scanner without loading the signed-in scanner module', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: true, isAdminMode: false });
    await renderScannerSurfacePage();
    expect(screen.getByText('auth-guard:全市场扫描仪')).toBeInTheDocument();
    expect(loadUserScannerPageMock).not.toHaveBeenCalled();
  });

  it('renders user scanner surface for normal signed-in users', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false, isAdminMode: false });
    await renderScannerSurfacePage();
    expect(await screen.findByText('user scanner page')).toBeInTheDocument();
  });

  it('renders the normal user scanner surface for admin accounts too', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false, isAdmin: true });
    await renderScannerSurfacePage();
    expect(await screen.findByText('user scanner page')).toBeInTheDocument();
  });
});
