import React, { Suspense } from 'react';
import { AuthGuardOverlay } from '../components/auth/AuthGuardOverlay';
import { useI18n } from '../contexts/UiLanguageContext';
import { useProductSurface } from '../hooks/useProductSurface';

const UserScannerPage = React.lazy(() => import('./UserScannerPage'));

const ScannerSurfacePage: React.FC = () => {
  const { isGuest } = useProductSurface();
  const { language } = useI18n();

  if (isGuest) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center">
        <AuthGuardOverlay moduleName={language === 'en' ? 'Market Scanner' : '全市场扫描仪'} />
      </div>
    );
  }

  return (
    <Suspense
      fallback={
        <div className="flex min-h-[220px] w-full items-center justify-center px-6 py-10">
          <div
            className="rounded-[16px] border border-white/5 bg-white/[0.02] px-5 py-4 text-center text-sm text-white/60 backdrop-blur-md"
            role="status"
          >
            {language === 'en' ? 'Loading scanner workspace...' : '正在加载扫描工作台...'}
          </div>
        </div>
      }
    >
      <UserScannerPage />
    </Suspense>
  );
};

export default ScannerSurfacePage;
