import type React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useI18n } from '../../contexts/UiLanguageContext';
import { buildLocalizedPath } from '../../utils/localeRouting';
import { ConsumerWorkspacePageShell, ConsumerWorkspaceScope } from './ConsumerWorkspaceShell';

type ConsumerEnglishPresentationBoundaryProps = {
  surface: 'liquidity-monitor' | 'options-lab';
  title: string;
  children: React.ReactNode;
};

/**
 * Keeps a Chinese-only consumer implementation from leaking mixed-language
 * product copy into an English route. The source surface remains available at
 * its Chinese route; this boundary does not translate or alter its data.
 */
export function ConsumerEnglishPresentationBoundary({
  surface,
  title,
  children,
}: ConsumerEnglishPresentationBoundaryProps) {
  const { language } = useI18n();
  const location = useLocation();

  if (language !== 'en') {
    return <>{children}</>;
  }

  const currentPath = `${location.pathname}${location.search}${location.hash}`;
  const chinesePath = buildLocalizedPath(currentPath, 'zh');

  return (
    <ConsumerWorkspaceScope
      data-testid="consumer-english-presentation-boundary"
      data-consumer-surface={surface}
    >
      <ConsumerWorkspacePageShell>
        <section
          aria-labelledby={`${surface}-english-presentation-title`}
          aria-live="polite"
          className="theme-panel-glass max-w-3xl p-5 md:p-6"
          data-testid={`consumer-english-presentation-${surface}`}
          role="status"
        >
          <div className="flex min-w-0 flex-col gap-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-[color:var(--wolfy-text-muted)]">
              English presentation
            </p>
            <div className="flex min-w-0 flex-col gap-2">
              <h1
                className="text-xl font-semibold text-[color:var(--wolfy-text-primary)] md:text-2xl"
                id={`${surface}-english-presentation-title`}
              >
                {title}
              </h1>
              <p className="max-w-2xl text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
                This consumer surface does not yet have a complete English presentation. To prevent mixed-language product copy, its localized content is not shown here.
              </p>
              <p className="max-w-2xl text-sm leading-6 text-[color:var(--wolfy-text-muted)]">
                No market, portfolio, scanner, or account state is changed.
              </p>
            </div>
            <div>
              <Link className="btn-primary" to={chinesePath}>
                Open this surface in Chinese
              </Link>
            </div>
          </div>
        </section>
      </ConsumerWorkspacePageShell>
    </ConsumerWorkspaceScope>
  );
}
