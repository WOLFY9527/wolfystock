import type React from 'react';
import { useI18n } from '../../contexts/UiLanguageContext';
import { getCategoryTitle } from '../../utils/systemConfigI18n';
import type { SystemConfigCategorySchema, SystemConfigItem } from '../../types/systemConfig';
import { cn } from '../../utils/cn';

interface SettingsCategoryNavProps {
  categories: SystemConfigCategorySchema[];
  itemsByCategory: Record<string, SystemConfigItem[]>;
  activeCategory: string;
  onSelect: (category: string) => void;
  disabled?: boolean;
  hideHeader?: boolean;
}

export const SettingsCategoryNav: React.FC<SettingsCategoryNavProps> = ({
  categories,
  itemsByCategory,
  activeCategory,
  onSelect,
  disabled = false,
  hideHeader = false,
}) => {
  const { language, t } = useI18n();
  return (
    <div className="flex h-full flex-col gap-1">
      {!hideHeader ? (
        <div className="px-3 pb-2">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-white/36">{t('settings.categoriesTitle')}</p>
        </div>
      ) : null}

      <div className="flex-1 overflow-y-auto no-scrollbar p-1 scroll-p-2">
        {categories.map((category) => {
          const isActive = category.category === activeCategory;
          const count = (itemsByCategory[category.category] || []).length;
          const title = getCategoryTitle(language, category.category, category.title);

          return (
            <button
              key={category.category}
              type="button"
              className={cn(
                'flex w-full items-center justify-between rounded-lg px-3 py-2 text-left transition-colors',
                isActive
                  ? 'bg-white/[0.05] text-white'
                  : 'text-white/60 hover:bg-white/[0.02] hover:text-white',
                disabled ? 'pointer-events-none opacity-60' : '',
              )}
              onClick={() => {
                if (disabled) {
                  return;
                }
                onSelect(category.category);
              }}
              disabled={disabled}
            >
              <div className="min-w-0 flex-1">
                <p className={cn('text-[12px] font-semibold tracking-wide uppercase', isActive ? 'text-white' : 'text-inherit')}>
                  {title}
                </p>
              </div>
              <span className={cn(
                'ml-3 rounded px-1.5 py-0.5 text-[10px] font-mono',
                isActive ? 'bg-white/[0.08] text-white/70' : 'bg-white/[0.03] text-white/40',
              )}
              >
                {count}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
};
