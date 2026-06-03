import type React from 'react';
import { useState } from 'react';
import { Menu } from 'lucide-react';
import { BrandLogo, BRAND_WORDMARK_CLASSNAME } from '../common/BrandLogo';
import { Drawer } from '../common/Drawer';
import { useI18n } from '../../contexts/UiLanguageContext';
import { useIsDesktopViewport } from './useIsDesktopViewport';

type PreviewShellProps = {
  children: React.ReactNode;
};

const PreviewRail: React.FC = () => {
  const { t } = useI18n();
  return (
    <div className="shell-context-panel">
      <div className="shell-context-panel__header">
        <p className="shell-context-panel__eyebrow">{t('preview.eyebrow')}</p>
        <h2 className="shell-context-panel__title">{t('preview.shellTitle')}</h2>
        <p className="shell-context-panel__body">{t('preview.shellBody')}</p>
      </div>
    </div>
  );
};

export const PreviewShell: React.FC<PreviewShellProps> = ({ children }) => {
  const { t } = useI18n();
  const isDesktop = useIsDesktopViewport();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="theme-shell flex h-screen flex-col overflow-hidden text-foreground" data-testid="preview-shell">
      <header className="shell-masthead shrink-0 w-full">
        <div className="shell-masthead__inner w-full">
          {isDesktop ? (
            <div className="shell-nav-strip">
              <div className="shell-nav-brand">
                <span className="inline-flex min-w-0 items-center gap-3">
                  <BrandLogo className="size-8" />
                  <span className={`shell-wordmark ${BRAND_WORDMARK_CLASSNAME}`}>WolfyStock</span>
                </span>
                <span className="shell-nav-brand-note">{t('preview.shellNote')}</span>
              </div>
              <div className="shell-nav-actions">
                <button type="button" className="shell-nav-utility">
                  {t('preview.shellAction')}
                </button>
              </div>
            </div>
          ) : (
            <div className="shell-mobile-strip">
              <button
                type="button"
                className="shell-mobile-button"
                onClick={() => setMobileOpen(true)}
                aria-label={t('shell.openMenu')}
              >
                <Menu className="size-4" />
              </button>
              <div className="shell-mobile-brand">
                <span className="inline-flex min-w-0 items-center gap-3">
                  <BrandLogo className="size-8" />
                  <span className={`shell-wordmark ${BRAND_WORDMARK_CLASSNAME}`}>{t('preview.eyebrow')}</span>
                </span>
                <span className="shell-mobile-brand__note">{t('preview.shellTitle')}</span>
              </div>
              <span className="shell-mobile-placeholder" aria-hidden="true" />
            </div>
          )}
        </div>
      </header>

      <div className="shell-content-frame shell-content-frame--wide flex flex-1 min-h-0 min-w-0 w-full overflow-hidden">
        <main className="theme-main-lane shell-main-column flex-1 min-h-0 min-w-0 w-full overflow-hidden">
          <div className="theme-page-transition flex h-full min-h-0 min-w-0 w-full flex-col">
            {children}
          </div>
        </main>
      </div>

      {!isDesktop ? (
        <Drawer
          isOpen={mobileOpen}
          onClose={() => setMobileOpen(false)}
          title={t('shell.drawerTitle')}
          width="max-w-xs"
          zIndex={90}
          side="left"
        >
          <PreviewRail />
        </Drawer>
      ) : null}
    </div>
  );
};
