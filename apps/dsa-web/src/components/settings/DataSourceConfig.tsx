import type React from 'react';
import { Button } from '../common/Button';
import { GlassCard } from '../common/GlassCard';
import { StatusBadge } from '../ui/StatusBadge';
import { ApiSourceCard } from './ApiSourceCard';
import { SettingsSectionCard } from './SettingsSectionCard';
import {
  buildDataCoverageGaps,
  buildDataSourceImpactView,
  sourceToneClass,
  type DataCoverageGapView,
  type DataRouteKey,
  type DataSourceLibraryEntry,
  type DataSourceValidationState,
} from './dataSourceLibraryShared';
import type { ProductSetupSurface } from '../../utils/productSetupSurface';

type TranslateFn = (key: string, vars?: Record<string, string | number | undefined>) => string;

type DataRoutingGroup = {
  key: DataRouteKey;
  role: string;
  values: string[];
  available: string[];
};

type DataSourceConfigProps = {
  t: TranslateFn;
  dataRoutingGroups: DataRoutingGroup[];
  dataSourceLibrary: DataSourceLibraryEntry[];
  adminLocked: boolean;
  isSaving: boolean;
  prettySourceLabel: (value: string) => string;
  onOpenDataRoutingDrawer: (key: DataRouteKey) => void;
  onOpenCreateDataSourceDrawer: () => void;
  onOpenEditDataSourceDrawer: (sourceId: string) => void;
  onValidateDataSource: (sourceId: string) => void;
  surfaceFocus?: ProductSetupSurface | null;
};

const CONTROL_GHOST_BUTTON_CLASS = 'px-3 py-1.5 rounded-lg bg-[var(--wolfy-surface-input)] border border-[color:var(--wolfy-border-subtle)] hover:bg-[var(--wolfy-surface-input)] text-xs transition-colors';
const GHOST_TAG_CLASS = 'inline-flex items-center px-1.5 py-0.5 rounded text-[10px] uppercase tracking-widest font-bold bg-[var(--wolfy-surface-input)] text-[color:var(--wolfy-text-muted)] border border-[color:var(--wolfy-border-subtle)]';
const SECTION_HEADER_CLASS = 'mt-8 mb-3 border-b border-[color:var(--wolfy-border-subtle)] pb-2 text-xs font-bold uppercase tracking-[0.2em] text-[color:var(--wolfy-text-muted)] first:mt-0';
const ROW_CLASS = 'flex items-center justify-between gap-4 border-b border-[color:var(--wolfy-border-subtle)] py-3 transition-colors hover:bg-[var(--wolfy-surface-console)]';

const priorityLabel = (index: number): string => {
  if (index === 0) return 'P1';
  if (index === 1) return 'P2';
  if (index === 2) return 'P3';
  return `P${index + 1}`;
};

const DATA_SOURCE_LIBRARY_GROUPS: Array<{
  key: string;
  title: string;
  matches: (source: DataSourceLibraryEntry) => boolean;
}> = [
  {
    key: 'market',
    title: 'MARKET DATA',
    matches: (source) => source.capabilityKeys.includes('market'),
  },
  {
    key: 'fundamentals',
    title: 'FUNDAMENTALS',
    matches: (source) => source.capabilityKeys.includes('fundamentals'),
  },
  {
    key: 'news',
    title: 'NEWS & SENTIMENT',
    matches: (source) => source.capabilityKeys.includes('news')
      || source.capabilityKeys.includes('sentiment')
      || source.capabilityKeys.includes('local'),
  },
];

const groupedDataSources = (sources: DataSourceLibraryEntry[]) => {
  const assigned = new Set<string>();
  return DATA_SOURCE_LIBRARY_GROUPS.reduce<Array<typeof DATA_SOURCE_LIBRARY_GROUPS[number] & { items: DataSourceLibraryEntry[] }>>((acc, group) => {
    const items = sources.filter((source) => {
      if (assigned.has(source.key) || !group.matches(source)) {
        return false;
      }
      assigned.add(source.key);
      return true;
    });
    if (items.length > 0) acc.push({ ...group, items });
    return acc;
  }, []);
};

function getValidationBadgeStatus(state: DataSourceValidationState): string {
  if (state === 'validated') return 'success';
  if (state === 'failed') return 'failed';
  if (state === 'partial') return 'partial';
  if (state === 'missing_key' || state === 'unsupported') return 'warning';
  if (state === 'loading') return 'running';
  if (state === 'configured_pending') return 'pending';
  if (state === 'builtin') return 'info';
  return 'disabled';
}

const StatusDot: React.FC<{ active: boolean }> = ({ active }) => (
  <span
    className={active
      ? 'size-1.5 shrink-0 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]'
      : 'size-1.5 shrink-0 rounded-full bg-white/20'}
    aria-hidden="true"
  />
);

const CoverageGapsPanel: React.FC<{ gaps: DataCoverageGapView[]; t: TranslateFn }> = ({ gaps, t }) => (
  <GlassCard className="p-4">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.1em] text-secondary-text">
          {t('settings.dataCoverageGapsTitle')}
        </p>
        <p className="mt-1 text-sm font-semibold text-foreground">{t('settings.dataCoverageGapsDesc')}</p>
      </div>
      <span className={GHOST_TAG_CLASS}>{t('settings.dataCoverageGapProxyLabel')}</span>
    </div>
    <div className="mt-3 grid gap-2 md:grid-cols-2" data-testid="data-coverage-gaps">
      {gaps.map((gap) => (
        <div key={gap.key} className="min-w-0 border-t border-[color:var(--wolfy-border-subtle)] pt-2">
          <div className="flex flex-wrap gap-1.5">
            {gap.surfaces.map((surface) => (
              <span key={`${gap.key}-${surface}`} className={GHOST_TAG_CLASS}>{surface}</span>
            ))}
          </div>
          <p className="mt-1 text-xs font-semibold text-[color:var(--wolfy-text-secondary)]">
            {t('settings.dataCoverageGapMissingProviderLabel')}: {gap.missing}
          </p>
          <p className="mt-1 text-[11px] text-[color:var(--wolfy-text-muted)]">
            {t('settings.dataCoverageGapImproveLabel')}: {gap.impact}
          </p>
        </div>
      ))}
    </div>
  </GlassCard>
);

const DataSourceConfig: React.FC<DataSourceConfigProps> = ({
  t,
  dataRoutingGroups,
  dataSourceLibrary,
  adminLocked,
  isSaving,
  prettySourceLabel,
  onOpenDataRoutingDrawer,
  onOpenCreateDataSourceDrawer,
  onOpenEditDataSourceDrawer,
  onValidateDataSource,
  surfaceFocus = null,
}) => {
  const coverageGaps = buildDataCoverageGaps(dataSourceLibrary, t);
  const focusedCoverageGaps = surfaceFocus
    ? coverageGaps.filter((gap) => gap.surfaces.includes(surfaceFocus.label))
    : [];

  return (
    <SettingsSectionCard
      title={t('settings.dataEffectiveTitle')}
      description={t('settings.dataEffectiveDesc')}
    >
      <div className="space-y-3">
        {surfaceFocus ? (
          <GlassCard className="px-4 py-3" data-testid="data-source-surface-context">
            <p className="text-sm font-semibold text-foreground">
              从 {surfaceFocus.label} 跳转：以下数据源可能改善证据覆盖
            </p>
            <p className="mt-1 text-xs leading-5 text-secondary-text">
              改善证据覆盖 / 减少 fallback/proxy / 可能提升为可评分证据。这里只引用现有 impact metadata 与 coverage gap map。
            </p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {(focusedCoverageGaps.length ? focusedCoverageGaps : coverageGaps.slice(0, 2)).map((gap) => (
                <span key={gap.key} className={GHOST_TAG_CLASS}>{gap.missing}</span>
              ))}
            </div>
          </GlassCard>
        ) : null}
        <CoverageGapsPanel gaps={coverageGaps} t={t} />
      <GlassCard className="p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.1em] text-secondary-text">
              {t('settings.dataRoutingLayerTitle')}
            </p>
            <p className="mt-1 text-sm font-semibold text-foreground">{t('settings.dataRoutingCompactTitle')}</p>
          </div>
        </div>
        <div className="mt-3 flex flex-col" data-testid="data-routing-list">
          {dataRoutingGroups.map((group) => (
            <div key={group.role} className={ROW_CLASS}>
              <div className="flex min-w-[13rem] items-center gap-3">
                <StatusDot active={group.values.length > 0} />
                <div className="min-w-0">
                  <p className="w-48 truncate text-sm font-bold text-[color:var(--wolfy-text-primary)]">{group.role}</p>
                  <p className="mt-1 text-[10px] uppercase tracking-[0.16em] text-[color:var(--wolfy-text-muted)]">
                    {group.available.length
                      ? t('settings.dataRoutingSelectableCount', { count: group.available.length })
                      : t('settings.dataSourceNoUsableSources')}
                  </p>
                </div>
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap gap-2">
                  <span className={GHOST_TAG_CLASS}>
                    {group.values.length ? t('settings.configuredNoPriority') : t('settings.notConfigured')}
                  </span>
                  {group.values.map((source, index) => (
                    <span
                      key={`${group.role}-${source}-${index}`}
                      className={GHOST_TAG_CLASS}
                    >
                      <span className={sourceToneClass(index)}>{priorityLabel(index)}</span>
                      {' · '}
                      {prettySourceLabel(source)}
                    </span>
                  ))}
                </div>
                <p className="mt-1 truncate text-[11px] text-[color:var(--wolfy-text-muted)]">
                  {group.values.length
                    ? group.values.map((source) => prettySourceLabel(source)).join(' -> ')
                    : (group.available.length
                      ? group.available.map((source) => prettySourceLabel(source)).join(' · ')
                      : t('settings.dataSourceNotRouted'))}
                </p>
              </div>
              <div className="flex shrink-0 items-center justify-end gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="settings-secondary"
                  className={CONTROL_GHOST_BUTTON_CLASS}
                  disabled={adminLocked || isSaving || group.available.length === 0}
                  data-testid={`data-routing-manage-${group.key}`}
                  onClick={() => onOpenDataRoutingDrawer(group.key)}
                >
                  {t('settings.dataSourceManageAction')}
                </Button>
              </div>
            </div>
          ))}
        </div>
      </GlassCard>

      <GlassCard className="p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.1em] text-secondary-text">
              {t('settings.dataLibraryLayerTitle')}
            </p>
            <p className="mt-1 text-sm font-semibold text-foreground">{t('settings.dataSourceLibraryCompactTitle')}</p>
          </div>
          <Button
            type="button"
            size="sm"
            variant="settings-primary"
            onClick={onOpenCreateDataSourceDrawer}
          >
            {t('settings.dataSourceAddAction')}
          </Button>
        </div>
        <div className="mt-3 flex flex-col" data-testid="data-source-library-list">
          {groupedDataSources(dataSourceLibrary).map((group) => (
            <section key={group.key} aria-label={group.title}>
              <h3 className={SECTION_HEADER_CLASS}>{group.title}</h3>
              <div className="flex flex-col">
                {group.items.map((source) => {
                  const impact = buildDataSourceImpactView(source, t);
                  return (
                    <ApiSourceCard
                      key={source.key}
                      testId={`data-source-card-${source.key}`}
                      label={source.label}
                      kindLabel={source.builtin ? t('settings.dataSourceBuiltinKind') : t('settings.dataSourceCustomKind')}
                      validationBadge={(
                        <StatusBadge
                          status={getValidationBadgeStatus(source.validationState)}
                          label={source.validationState === 'builtin'
                            ? t('settings.dataSourceValidationBuiltin')
                            : source.validationState === 'loading'
                              ? t('settings.dataSourceValidationChecking')
                            : source.validationState === 'validated'
                              ? t('settings.dataSourceValidated')
                              : source.validationState === 'partial'
                                ? t('settings.dataSourceValidationPartial')
                              : source.validationState === 'missing_key'
                                ? t('settings.dataSourceValidationMissingKey')
                              : source.validationState === 'unsupported'
                                ? t('settings.dataSourceValidationUnsupported')
                              : source.validationState === 'failed'
                                ? t('settings.dataSourceValidationFailed')
                                : source.configured
                                  ? t('settings.dataSourceConfiguredPending')
                                  : t('settings.notConfigured')}
                          variant="soft"
                          size="sm"
                        />
                      )}
                      isConfigured={source.usable || source.configured}
                      capabilities={source.capabilityLabels}
                      impactLabel={t('settings.dataSourceImpactLabel')}
                      impactSurfaces={impact.surfaces}
                      impactCapabilities={impact.capabilities}
                      impactStates={impact.states}
                      impactEvidenceText={impact.evidence}
                      statusText={source.configured
                        ? t('settings.dataSourceStatusConfigured')
                        : t('settings.dataSourceStatusMissing')}
                      validationMessage={source.validationMessage}
                      usedByText={`${t('settings.dataSourceUsedByLabel')}: ${source.routeUsage.length
                        ? source.routeUsage.map((routeKey) => t(`settings.dataRouteName.${routeKey}`)).join(' · ')
                        : t('settings.dataSourceNotRouted')}`}
                      endpointText={`${t('settings.dataSourceEndpointNameLabel')}: ${source.key}`}
                      internalFlagText={`${t('settings.dataSourceInternalFlagLabel')}: ${source.builtin
                        ? t('settings.dataSourceInternalFlagBuiltin')
                        : t('settings.dataSourceInternalFlagExternal')}`}
                      manageLabel={source.builtin ? t('settings.dataSourceManageAction') : t('settings.dataSourceEditAction')}
                      validateLabel={t('settings.dataSourceValidateAction')}
                      validateDisabled={source.validationState === 'loading'}
                      onManage={() => onOpenEditDataSourceDrawer(source.key)}
                      onValidate={() => onValidateDataSource(source.key)}
                    />
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      </GlassCard>
      </div>
    </SettingsSectionCard>
  );
};

export default DataSourceConfig;
