import type React from 'react';
import { useI18n } from '../../contexts/UiLanguageContext';
import { useUiPreferences, type UiFontSize } from '../../contexts/UiPreferencesContext';
import { cn } from '../../utils/cn';

const OPTIONS: UiFontSize[] = ['xs', 's', 'm', 'l', 'xl'];

export const FontSizeSettingsCard: React.FC = () => {
  const { language, t } = useI18n();
  const { fontSize, setFontSize } = useUiPreferences();

  return (
    <div data-testid="font-size-card" className="grid gap-3 p-4 md:grid-cols-[180px_minmax(0,1fr)] xl:grid-cols-[220px_minmax(0,1fr)]">
      <div className="min-w-0">
        <p className="text-sm font-medium text-[color:var(--wolfy-text-primary)]">{t('settings.fontSizeTitle')}</p>
        <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
          {language === 'en' ? 'Scale dense tables, reports, and controls without leaving this route.' : '在当前路由内统一调整表格、报告和控件的字体密度。'}
        </p>
      </div>
      <div className="min-w-0">
        <div className="grid grid-cols-5 gap-2" role="group" aria-label={t('settings.fontSizeTitle')}>
          {OPTIONS.map((option) => (
            <button
              key={option}
              type="button"
              className={cn(
                'min-h-9 rounded-md border px-2 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--wolfy-accent)]',
                fontSize === option
                  ? 'border-[color:var(--wolfy-accent)] bg-[var(--wolfy-surface-console)] text-[color:var(--wolfy-text-primary)] shadow-[inset_0_0_0_1px_var(--wolfy-accent)]'
                  : 'border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] text-[color:var(--wolfy-text-secondary)] hover:border-[color:var(--wolfy-divider)] hover:text-[color:var(--wolfy-text-primary)]',
              )}
              onClick={() => setFontSize(option)}
              aria-pressed={fontSize === option}
            >
              {t(`settings.fontSize${option.toUpperCase()}`)}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};
