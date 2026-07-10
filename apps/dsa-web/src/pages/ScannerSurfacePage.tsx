import React, { Suspense } from 'react';
import { ConsumerProtectedFrame } from '../components/layout/ConsumerWorkspaceShell';
import { useI18n } from '../contexts/UiLanguageContext';
import { useProductSurface } from '../hooks/useProductSurface';

const UserScannerPage = React.lazy(() => import('./UserScannerPage'));

const ScannerSurfacePage: React.FC = () => {
  const { isGuest } = useProductSurface();
  const { language } = useI18n();

  if (isGuest) {
    return <ConsumerProtectedFrame moduleName={language === 'en' ? 'Market Scanner' : '全市场扫描仪'} />;
  }

  return (
    <Suspense
      fallback={
        <div className="flex min-h-[220px] w-full items-center justify-center px-6 py-10">
          <output
            className="block rounded-[16px] border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-rail)] px-5 py-4 text-center text-sm text-[color:var(--wolfy-text-muted)]"
          >
            {language === 'en' ? 'Loading scanner workspace...' : '正在加载扫描工作台...'}
          </output>
        </div>
      }
    >
      <UserScannerPage />
    </Suspense>
  );
};

export default ScannerSurfacePage;
